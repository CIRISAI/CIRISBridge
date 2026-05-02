#!/usr/bin/env python3
"""
lens-steward federation bootstrap.

Inserts the self-signed `lens-steward` row into
`cirislens.federation_keys`. After this row exists, lens-side
`federation_mirror.put_public_key(...)` calls succeed (the FK target
exists); without this row, every mirror attempt hits `scrub_key_must_exist`.

This script is run from bridge ahead of lens-api consuming
`ciris-persist>=0.2.2`. Constructing `Engine` against the lens DB
auto-applies V001+V003+V004 (purely additive — V004 only CREATEs new
tables `federation_{keys,attestations,revocations}`); the legacy
`accord_public_keys` path keeps working for lens-api 0.1.x writes.

Cryptography:
  * Ed25519 hot path  — `engine.steward_sign(canonical_bytes)` (persist's
    keyring-managed steward identity, seed loaded from `STEWARD_KEY_PATH`).
  * ML-DSA-65 cold path — `dilithium_py.ml_dsa.ML_DSA_65.sign(sk,
    canonical || classical_sig)`. dilithium-py and the Rust
    `ml-dsa = 0.1.0-rc.3` crate (used by CIRISVerify + the persist
    cold-path verifier) are interoperable for both seed-derivation
    and signature verification — empirically confirmed against this
    same seed during bootstrap-prep.

Idempotent: if `lens-steward` already exists in `federation_keys` the
script reports + exits 0 without re-signing.

Required environment variables:
  LENS_DSN          postgres://… for lens DB
  STEWARD_KEY_ID    e.g. "lens-steward"
  STEWARD_KEY_PATH  path to 32-byte raw Ed25519 seed
  STEWARD_PUBKEY_PATH      path to 32-byte raw Ed25519 pubkey (sanity check)
  STEWARD_MLDSA_SEED_PATH  path to 32-byte raw ML-DSA-65 seed
  STEWARD_MLDSA_PUB_PATH   path to 1952-byte raw ML-DSA-65 pubkey

Optional:
  IDENTITY_REF      identity_ref column value (default "lens")
  ISSUER            issuer field stamped into envelope (default "ciris-bridge")
  DRY_RUN           if "1", canonicalize + sign but skip put_public_key
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ciris_persist import Engine
from dilithium_py.ml_dsa import ML_DSA_65
import psycopg


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def main() -> int:
    dsn = os.environ["LENS_DSN"]
    steward_key_id = os.environ["STEWARD_KEY_ID"]
    ed25519_seed_path = os.environ["STEWARD_KEY_PATH"]
    ed25519_pub_path = os.environ["STEWARD_PUBKEY_PATH"]
    mldsa_seed_path = os.environ["STEWARD_MLDSA_SEED_PATH"]
    mldsa_pub_path = os.environ["STEWARD_MLDSA_PUB_PATH"]
    identity_ref = os.environ.get("IDENTITY_REF", "lens")
    issuer = os.environ.get("ISSUER", "ciris-bridge")
    dry_run = os.environ.get("DRY_RUN") == "1"

    expected_ed_pub = Path(ed25519_pub_path).read_bytes()
    expected_mldsa_pub = Path(mldsa_pub_path).read_bytes()
    mldsa_seed = Path(mldsa_seed_path).read_bytes()
    if len(expected_ed_pub) != 32:
        sys.exit(f"ed25519 pubkey must be 32B, got {len(expected_ed_pub)}")
    if len(expected_mldsa_pub) != 1952:
        sys.exit(f"ml-dsa-65 pubkey must be 1952B, got {len(expected_mldsa_pub)}")
    if len(mldsa_seed) != 32:
        sys.exit(f"ml-dsa-65 seed must be 32B, got {len(mldsa_seed)}")

    # Idempotency check: skip if row exists. Uses a separate psycopg
    # connection rather than Engine — Engine.run_migrations() is the
    # part we want to defer until we're sure we'll insert.
    with psycopg.connect(dsn) as conn:
        cur = conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='cirislens' AND table_name='federation_keys'"
        )
        v004_applied = cur.fetchone() is not None
        if v004_applied:
            cur = conn.execute(
                "SELECT key_id, identity_type, identity_ref, "
                "pqc_completed_at IS NOT NULL AS pqc_done "
                "FROM cirislens.federation_keys WHERE key_id = %s",
                (steward_key_id,),
            )
            existing = cur.fetchone()
            if existing:
                print(f"lens-steward bootstrap: row already exists: {existing}")
                return 0

    # Engine.new() in v0.2.2 auto-runs migrations on connect. This is
    # how V004 gets applied if it wasn't already.
    engine = Engine(
        dsn,
        steward_key_id,            # signing_key_id reused; bootstrap path
                                   # only exercises steward_sign, not sign().
        steward_key_id=steward_key_id,
        steward_key_path=ed25519_seed_path,
    )

    # Sanity: persist-derived pubkey must match disk.
    ed_pub_b64 = engine.steward_public_key_b64()
    if ed_pub_b64 != b64(expected_ed_pub):
        sys.exit(
            "Ed25519 pubkey mismatch — engine.steward_public_key_b64() "
            "disagrees with disk pubkey."
        )

    # Verify ML-DSA-65 seed produces the disk pubkey.
    derived_mldsa_pub, mldsa_sk = ML_DSA_65.key_derive(mldsa_seed)
    if derived_mldsa_pub != expected_mldsa_pub:
        sys.exit(
            "ML-DSA-65 pubkey mismatch — keygen_with_seed disagrees with disk."
        )
    mldsa_pub_b64 = b64(expected_mldsa_pub)

    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    # Registration envelope: the canonical bytes that will be signed.
    # Lens-side verifiers re-canonicalize this object and re-derive
    # original_content_hash to recover the bytes that were signed.
    envelope = {
        "role": "lens-steward",
        "key_id": steward_key_id,
        "pubkey_ed25519_base64": ed_pub_b64,
        "pubkey_ml_dsa_65_base64": mldsa_pub_b64,
        "algorithm": "hybrid",
        "identity_type": "steward",
        "identity_ref": identity_ref,
        "valid_from": now,
        "issuer": issuer,
    }
    canonical = engine.canonicalize_envelope(json.dumps(envelope))

    classical_sig = engine.steward_sign(canonical)
    pqc_input = bytes(canonical) + bytes(classical_sig)
    pqc_sig = ML_DSA_65.sign(mldsa_sk, pqc_input)
    original_content_hash = hashlib.sha256(canonical).hexdigest()

    record = {
        "key_id": steward_key_id,
        "pubkey_ed25519_base64": ed_pub_b64,
        "pubkey_ml_dsa_65_base64": mldsa_pub_b64,
        "algorithm": "hybrid",
        "identity_type": "steward",
        "identity_ref": identity_ref,
        "valid_from": now,
        "registration_envelope": envelope,
        "original_content_hash": original_content_hash,
        "scrub_signature_classical": b64(classical_sig),
        "scrub_signature_pqc": b64(pqc_sig),
        "scrub_key_id": steward_key_id,  # self-signed bootstrap row
        "scrub_timestamp": now,
        "pqc_completed_at": now,
        "persist_row_hash": "",  # server-computed; ignored on insert
    }

    print(f"lens-steward bootstrap: prepared record")
    print(f"  key_id              {steward_key_id}")
    print(f"  identity            steward / {identity_ref}")
    print(f"  ed25519 pub         {ed_pub_b64}")
    print(f"  ml-dsa-65 pub       {mldsa_pub_b64[:32]}…  ({len(mldsa_pub_b64)} chars)")
    print(f"  canonical bytes     {len(canonical)}")
    print(f"  ed25519 sig         {len(classical_sig)} bytes")
    print(f"  ml-dsa-65 sig       {len(pqc_sig)} bytes")
    print(f"  original_content_hash {original_content_hash}")

    if dry_run:
        print("DRY_RUN=1 — skipping put_public_key")
        return 0

    engine.put_public_key(json.dumps({"record": record}))

    # Verify row landed.
    with psycopg.connect(dsn) as conn:
        cur = conn.execute(
            "SELECT key_id, identity_type, identity_ref, "
            "pqc_completed_at IS NOT NULL AS pqc_done, persist_row_hash "
            "FROM cirislens.federation_keys WHERE key_id = %s",
            (steward_key_id,),
        )
        row = cur.fetchone()
    if not row:
        sys.exit("post-insert verify failed: row not found")
    print(f"lens-steward bootstrap: inserted: {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
