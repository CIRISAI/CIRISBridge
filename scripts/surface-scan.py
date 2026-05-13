#!/usr/bin/env python3
"""
Bridge surface scanner — captures the bridge production surface state into
a diff-able JSON snapshot.

Schema is compatible with CIRISCore's `surface.pre.json` (same top-level
keys + probe shape) so cross-team diffs work.

Usage:

    ./surface-scan.py                          # write /tmp/bridge-surface-<ts>.json
    ./surface-scan.py --out path.json
    ./surface-scan.py --manifest scripts/surface.yml
    ./surface-scan.py --diff a.json b.json     # diff two snapshots
    ./surface-scan.py --internal               # also capture SSH-side internal state

What's captured:
  - probes:    HTTP status, latency, body size + sha256 prefix per public endpoint
  - tls:       cert notAfter, days remaining, issuer per TLS host
  - internal:  (optional, with --internal) container states, Spock replication,
               federation_keys totals, disk %, memory % per node — via SSH

Designed for pre/post maintenance windows. Capture pre-snapshot, do the
maintenance, capture post-snapshot, then `--diff` to surface anything that
changed. Anything not in the diff is unchanged within probe granularity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    sys.exit("missing pyyaml: pip install pyyaml")

try:
    import requests
except ImportError:
    sys.exit("missing requests: pip install requests")


SCHEMA = "ciris-surface-snapshot/1"


def probe_http(probe: dict, timeout: float = 10.0) -> dict:
    """Capture HTTP probe result. Matches CIRISCore's probe shape."""
    url = probe["url"]
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path or "/"
    expect = probe.get("expect_status", 200)

    started = time.monotonic()
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=False)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        body = r.content or b""
        return {
            "site_id": probe["site_id"],
            "url": url,
            "domain": domain,
            "path": path,
            "status": r.status_code,
            "body_size": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest()[:16],
            "content_type": r.headers.get("content-type", "").split(";")[0],
            "latency_ms": elapsed_ms,
            "passed": r.status_code == expect,
            "expect_status": expect,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "site_id": probe["site_id"],
            "url": url,
            "domain": domain,
            "path": path,
            "status": 0,
            "body_size": 0,
            "body_sha256": "",
            "content_type": "",
            "latency_ms": elapsed_ms,
            "passed": False,
            "expect_status": expect,
            "error": str(e)[:200],
        }


def probe_tls(domain: str) -> dict:
    """Capture TLS cert metadata for the domain. Connects on 443, reads peer cert."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        # cert is a dict with subject, issuer, notAfter, notBefore, etc.
        not_after = cert.get("notAfter")  # 'May  9 23:46:44 2026 GMT'
        not_before = cert.get("notBefore")
        expiry_epoch = ssl.cert_time_to_seconds(not_after) if not_after else 0
        days_remaining = int((expiry_epoch - time.time()) / 86400) if expiry_epoch else 0
        issuer = dict(x[0] for x in cert.get("issuer", []) if x)
        subject = dict(x[0] for x in cert.get("subject", []) if x)
        return {
            "domain": domain,
            "days_remaining": days_remaining,
            "not_after": not_after,
            "not_before": not_before,
            "issuer_cn": issuer.get("commonName", ""),
            "issuer_o": issuer.get("organizationName", ""),
            "subject_cn": subject.get("commonName", ""),
            "passed": days_remaining > 0,
        }
    except Exception as e:
        return {
            "domain": domain,
            "days_remaining": -1,
            "passed": False,
            "error": str(e)[:200],
        }


def ssh_capture(host: dict) -> dict:
    """Capture internal state via SSH. Returns a dict per host."""
    ssh_cmd = [
        "ssh", "-i", str(Path(host["ssh_key"]).expanduser()),
        "-o", "StrictHostKeyChecking=no",
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=5",
        host["ssh"],
    ]
    out: dict = {"name": host["name"]}

    def run(cmd: str) -> str:
        try:
            r = subprocess.run(ssh_cmd + [cmd], capture_output=True, text=True, timeout=15)
            return r.stdout.strip()
        except Exception as e:
            return f"<error: {e}>"

    # containers
    raw = run('docker ps --format "{{.Names}}|{{.Status}}|{{.State}}"')
    containers = []
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) >= 2:
            containers.append({"name": parts[0], "status": parts[1]})
    out["containers"] = containers
    out["container_count"] = len(containers)
    out["all_healthy"] = all("healthy" in c["status"].lower() or "(healthy)" in c["status"]
                              for c in containers if "ciris" in c["name"])

    # disk + memory
    disk_raw = run('df -h / | awk "NR==2 {print \\$3, \\$2, \\$5}"')
    parts = disk_raw.split()
    if len(parts) == 3:
        out["disk"] = {"used": parts[0], "total": parts[1], "pct": parts[2]}

    mem_raw = run('free -h | awk "NR==2 {print \\$3, \\$2}"')
    parts = mem_raw.split()
    if len(parts) == 2:
        out["memory"] = {"used": parts[0], "total": parts[1]}

    # kernel + uptime
    out["kernel"] = run("uname -r")
    out["uptime"] = run('uptime -p').strip()

    # Spock subscription state (billing-spock is present on both)
    spock = run(
        "docker exec ciris-billing-spock /opt/pgedge/pg15/bin/psql -p 5433 -U billing -d ciris_billing -tAc "
        "\"SELECT subscription_name || '=' || status FROM spock.sub_show_status();\""
    )
    out["spock"] = spock if spock and "error" not in spock.lower() else None

    # lens-only: federation_keys count
    if host["name"] == "us":
        fk = run(
            "docker exec cirislens-db psql -U cirislens -d cirislens -tAc "
            "\"SELECT identity_type || '=' || COUNT(*) FROM cirislens.federation_keys GROUP BY 1 ORDER BY 1;\""
        )
        out["federation_keys"] = fk if fk else None
        pers = run(
            "docker exec cirislens-api python -c \"import ciris_persist; print(ciris_persist.__version__)\""
        )
        out["persist_version"] = pers if pers else None

    return out


def capture(manifest_path: Path, include_internal: bool = False, host_filter: str | None = None) -> dict:
    with open(manifest_path) as f:
        m = yaml.safe_load(f)

    snap = {
        "schema": SCHEMA,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "host_filter": host_filter,
        "probes": [],
        "tls": {},
    }

    for probe in m.get("probes", []):
        if host_filter and host_filter not in probe.get("site_id", ""):
            continue
        snap["probes"].append(probe_http(probe))

    for domain in m.get("tls", []):
        snap["tls"][domain] = probe_tls(domain)

    if include_internal and m.get("internal", {}).get("hosts"):
        snap["internal"] = []
        for h in m["internal"]["hosts"]:
            snap["internal"].append(ssh_capture(h))

    return snap


def diff_snapshots(a: dict, b: dict) -> dict:
    """Return a structured diff. Anything in the output changed; absent keys are unchanged."""
    out: dict = {"a_at": a.get("captured_at"), "b_at": b.get("captured_at"), "changes": {}}

    # probes — match by site_id
    a_probes = {p["site_id"]: p for p in a.get("probes", [])}
    b_probes = {p["site_id"]: p for p in b.get("probes", [])}
    probe_changes = []
    for sid in set(a_probes) | set(b_probes):
        pa = a_probes.get(sid)
        pb = b_probes.get(sid)
        if not pa or not pb:
            probe_changes.append({"site_id": sid, "kind": "added" if pb else "removed"})
            continue
        # compare important keys
        delta = {}
        for k in ("status", "body_size", "body_sha256", "passed"):
            if pa.get(k) != pb.get(k):
                delta[k] = {"a": pa.get(k), "b": pb.get(k)}
        if delta:
            probe_changes.append({"site_id": sid, "delta": delta})
    if probe_changes:
        out["changes"]["probes"] = probe_changes

    # tls — match by domain
    a_tls, b_tls = a.get("tls", {}), b.get("tls", {})
    tls_changes = []
    for d in set(a_tls) | set(b_tls):
        ta = a_tls.get(d, {})
        tb = b_tls.get(d, {})
        delta = {}
        for k in ("days_remaining", "not_after", "passed"):
            if ta.get(k) != tb.get(k):
                delta[k] = {"a": ta.get(k), "b": tb.get(k)}
        if delta:
            tls_changes.append({"domain": d, "delta": delta})
    if tls_changes:
        out["changes"]["tls"] = tls_changes

    # internal — match by host name
    a_int = {h["name"]: h for h in a.get("internal", [])}
    b_int = {h["name"]: h for h in b.get("internal", [])}
    int_changes = []
    for hn in set(a_int) | set(b_int):
        ha, hb = a_int.get(hn, {}), b_int.get(hn, {})
        delta = {}
        for k in ("container_count", "all_healthy", "kernel", "spock",
                  "federation_keys", "persist_version", "uptime"):
            if ha.get(k) != hb.get(k):
                delta[k] = {"a": ha.get(k), "b": hb.get(k)}
        # disk pct
        if ha.get("disk", {}).get("pct") != hb.get("disk", {}).get("pct"):
            delta["disk_pct"] = {"a": ha.get("disk", {}).get("pct"),
                                  "b": hb.get("disk", {}).get("pct")}
        if delta:
            int_changes.append({"host": hn, "delta": delta})
    if int_changes:
        out["changes"]["internal"] = int_changes

    return out


def summarize(snap: dict) -> str:
    lines = []
    lines.append(f"=== bridge surface snapshot @ {snap.get('captured_at')} ===")
    probes = snap.get("probes", [])
    passed = sum(1 for p in probes if p.get("passed"))
    lines.append(f"  probes:   {passed}/{len(probes)} passed")
    for p in probes:
        marker = "✓" if p.get("passed") else "✗"
        lines.append(f"    {marker} {p['site_id']:<40} {p['status']} ({p.get('latency_ms', 0)}ms)")
    tls = snap.get("tls", {})
    tls_passed = sum(1 for t in tls.values() if t.get("passed"))
    lines.append(f"  tls:      {tls_passed}/{len(tls)} valid")
    for d, t in sorted(tls.items()):
        days = t.get("days_remaining", -1)
        marker = "✓" if t.get("passed") else "✗"
        warn = " ⚠" if 0 < days < 14 else ""
        lines.append(f"    {marker} {d:<42} {days:>3}d{warn}")
    if "internal" in snap:
        for h in snap["internal"]:
            disk = h.get("disk", {}).get("pct", "?")
            healthy = "✓" if h.get("all_healthy") else "✗"
            lines.append(f"  internal {h['name']}: {healthy} containers={h.get('container_count')}, disk={disk}, kernel={h.get('kernel')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(Path(__file__).parent / "surface.yml"))
    ap.add_argument("--out", help="output path (default: /tmp/bridge-surface-<ts>.json)")
    ap.add_argument("--internal", action="store_true", help="capture internal state via SSH")
    ap.add_argument("--host-filter", help="filter probes by site_id substring")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"), help="diff two snapshots")
    ap.add_argument("--quiet", action="store_true", help="skip stdout summary")
    args = ap.parse_args()

    if args.diff:
        with open(args.diff[0]) as f:
            a = json.load(f)
        with open(args.diff[1]) as f:
            b = json.load(f)
        d = diff_snapshots(a, b)
        print(json.dumps(d, indent=2))
        if not d["changes"]:
            print("(no changes between snapshots)", file=sys.stderr)
        return 0

    manifest = Path(args.manifest)
    if not manifest.exists():
        sys.exit(f"manifest not found: {manifest}")

    snap = capture(manifest, include_internal=args.internal, host_filter=args.host_filter)

    if args.out:
        out_path = Path(args.out)
    else:
        ts = snap["captured_at"].replace(":", "").replace("-", "")[:15]
        out_path = Path(f"/tmp/bridge-surface-{ts}.json")
    out_path.write_text(json.dumps(snap, indent=2))

    if not args.quiet:
        print(summarize(snap))
        print()
    print(f"snapshot: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
