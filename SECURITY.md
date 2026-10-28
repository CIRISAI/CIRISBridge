# CIRISBridge Security Guide

The security model of the production nodes: what is exposed, how requests are
authenticated, what data is kept, and how secrets are handled.

## Network exposure

### Public

| Port | Node | Service |
|------|------|---------|
| 22/tcp | US, EU | SSH, keys only |
| 80/tcp | US, EU | Caddy (ACME challenges, redirect to HTTPS) |
| 443/tcp, 443/udp | US, EU | Caddy (HTTPS, HTTP/3) |
| 4242/tcp, 4242/udp | US | ciris-server Reticulum transport |
| 4243/tcp | US | ciris-server read API (signed, public data only) |
| 4253/tcp | US | CIRISStatus read API |

Ports published by Docker bypass UFW, so the exposure above is what Docker
publishes plus what UFW allows; `scripts/surface-scan.py` records it for
review.

### Internal

| Service | Reachable from |
|---------|----------------|
| Billing API (8000) | Caddy and local Docker networks |
| LiteLLM (4000) | localhost; Caddy forwards only the client routes |
| Spock (5433) | The other node's IP only |
| Vault (8210–8211) | Vault peers only; owned by CIRISCore |

### What Caddy forwards to the proxy

The proxy hostnames forward only `/v1/chat/completions`, `/v1/models`,
`/v1/status`, `/v1/status/simple` and `/v1/web/search`. LiteLLM's admin API,
admin UI, SSO login, OpenAPI documents and health routes all return 404 from
Caddy, so they are not reachable from the internet at all.

## TLS

Caddy obtains and renews Let's Encrypt certificates automatically, sends HSTS
(one year, preload), `X-Content-Type-Options: nosniff` and
`X-Frame-Options: DENY`, and removes the `Server` header. Cloudflare proxies
some hostnames; Caddy trusts Cloudflare's published ranges for the client IP.
The CA trust store is kept current on every node, and the canonical's image is
rebuilt on a freshly pulled base so its bundle is current too.

## Authentication

| Caller | Mechanism |
|--------|-----------|
| Mobile and web users | Google OAuth 2.0 ID tokens, verified against Google's keys and the allowed client IDs |
| Services and agents | API keys, stored as Argon2 hashes, verified by CIRISBilling |
| LLM requests | CIRISProxy delegates authentication to CIRISBilling |
| Admin panel | Google OAuth, restricted to named accounts |
| Federation | Hybrid Ed25519 + ML-DSA-65 signatures; the trust root is a 2-of-3 holder-signed bundle |

## Authorization

Every LLM request needs sufficient credit; billing checks and deducts per
request and refuses with 402 when the balance is exhausted. Rate limiting is
applied by the upstream LLM providers.

## Data protection

### Zero data retention

CIRISProxy routes only to providers configured for zero data retention (Groq,
Together AI, DeepInfra, OpenRouter) and runs with LiteLLM spend logging
disabled. Prompt and response content is never stored by CIRISBridge.

### Stored data

| Data | Where | Protection |
|------|-------|------------|
| Accounts, credits, charges | Spock (PostgreSQL 15) | Password auth; not exposed beyond the peer node |
| API keys | Spock | Argon2 hash |
| Federation keys and attestations | Canonical home (SQLite) | Public by design; private keys never leave the node |
| Access logs | `/var/log/caddy/` | Client IP, path, status; rotated by size |

[runbooks/PII_INVENTORY.md](runbooks/PII_INVENTORY.md) lists every personal-data
column and its row count; the daily status check fails if the schema drifts
from it.

### Not stored

- LLM prompts or responses
- Payment card details (Google Play handles payment)

## Secrets

All production secrets live in `ansible/inventory/production.yml`, which is
encrypted with Ansible Vault and never committed. Ansible renders each
service's `.env` from it at deploy time, mode 600. Provider API keys, database
passwords, OAuth credentials and the LiteLLM master key are all held there.

## Access

- SSH is key-only; password and keyboard-interactive login are disabled.
- fail2ban bans repeated SSH failures (three attempts, one hour).
- Ansible requires both SSH access and the vault password.

## Monitoring

`scripts/daily-status.sh` checks probes, certificates, containers, replication
and error signatures, and exits non-zero on anything that needs attention.
`scripts/surface-scan.py --diff` compares the exposed surface before and after
maintenance.

## Incident response

| Event | Runbook |
|-------|---------|
| Intrusion | `ansible/runbooks/intrusion-response.yml`: IP blocking, forensic collection to `./forensics/`, credential-rotation checklist |
| Personal-data breach | [runbooks/BREACH_NOTIFICATION.md](runbooks/BREACH_NOTIFICATION.md): GDPR Article 33 timeline, authorities, user notification |

## Known limitations

- No web application firewall or intrusion detection system.
- No application-level rate limiting.
- Root SSH is permitted (key-only).
- The canonical's keys are held in the software key tier; its hosts have no TPM.

## Reporting

Report security issues privately by email to `info@ciris.ai` with `SECURITY`
in the subject line, the same address the other CIRIS repositories use. Do not
open a public issue for a vulnerability.
