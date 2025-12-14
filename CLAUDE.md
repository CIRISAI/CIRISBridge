# CLAUDE.md - CIRISBridge

This file provides guidance for Claude Code when working on this repository.

## Core Philosophy: The Bridge Does Not Hack

**CIRISBridge is the orchestration layer.** It deploys and configures sibling services - it does NOT fix bugs in them.

### The Cardinal Rule

**NEVER make manual fixes, workarounds, or hacks to compensate for bugs in sibling repositories.**

When you encounter a bug in CIRISBilling, CIRISProxy, CIRISLens, or CIRISDNS:
1. **Document the bug clearly** (what's broken, expected behavior, actual behavior)
2. **Tell the user** what needs to be fixed in the sibling repo
3. **Wait for the fix** to be pushed to the sibling repo's container image
4. **Redeploy via Ansible** once the fix is available

Examples of what NOT to do:
- Creating dummy files to work around missing files in container images
- Manually editing deployed configs on servers (drift from IaC)
- Adding environment variables to mask application bugs
- SQL hacks to fix application-level issues

**Why?** CIRISBridge must remain a clean orchestration layer. Manual hacks create drift between IaC and deployed state, making the system unmaintainable.

## Project Context

CIRISBridge serves **Meta-Goal M-1** from the CIRIS Covenant:
> *Promote sustainable adaptive coherence - the living conditions under which diverse sentient beings may pursue their own flourishing in justice and wonder.*

Agents cannot serve this mission if users cannot reach them. CIRISBridge provides the minimum viable centralized infrastructure until Veilid is production-ready.

**This is temporary infrastructure designed to be retired.** Every component knows it will be replaced:
- DNS -> Veilid DHT peer discovery
- Proxy -> Veilid private routes
- Billing -> TBD (may persist longest)

## Sibling Repositories

| Repository | Purpose | Container Image |
|------------|---------|-----------------|
| CIRISBilling | Credits, payments, user auth | `ghcr.io/cirisai/cirisbilling:latest` |
| CIRISProxy | LLM routing with ZDR | `ghcr.io/cirisai/cirisproxy:latest` |
| CIRISLens | Observability, log aggregation | `ghcr.io/cirisai/cirislens:latest` |
| CIRISDNS | Authoritative DNS (Constellation) | `valeriansaliou/constellation:latest` |

## Current Infrastructure

### Nodes

| Node | Provider | IP | Role |
|------|----------|-----|------|
| US (vultr) | Vultr Chicago | 108.61.242.236 | Primary - Postgres primary, CIRISLens |
| EU (hetzner) | Hetzner Germany | 46.224.81.217 | Secondary - Postgres replica |

### Client Endpoints (Cloudflare DNS)

| Service | Endpoint | IP |
|---------|----------|-----|
| Billing US | `https://billing1.ciris-services-1.ai` | 108.61.242.236 |
| Billing EU | `https://billing1.ciris-services-2.ai` | 46.224.81.217 |
| Proxy US | `https://proxy1.ciris-services-1.ai` | 108.61.242.236 |
| Proxy EU | `https://proxy1.ciris-services-2.ai` | 46.224.81.217 |

### Internal Endpoints

| Service | Endpoint |
|---------|----------|
| CIRISLens | `https://lens.ciris-services-1.ai` (US only) |
| Agents API | `https://agents.ciris-services-1.ai` (alias for billing) |

### Internal Ports (per node)

| Port | Service | Notes |
|------|---------|-------|
| 53/udp,tcp | Constellation DNS | Public |
| 80/tcp | HTTP | ACME challenges only |
| 443/tcp | Caddy HTTPS | Public |
| 5432/tcp | PostgreSQL | Internal + replication |
| 6379/tcp | Redis | Internal only |
| 8000/tcp | Billing API | Via Caddy |
| 4000/tcp | Proxy API | Via Caddy |
| 8200/tcp | CIRISLens API | US only, via Caddy |
| 3001/tcp | Grafana | US only, via Caddy |

### CIRISLens API Endpoints

The CIRISLens API exposes these routes (via `/lens-api/*` prefix which strips the prefix):
- `/health` - Health check
- `/api/v1/logs/ingest` - Log ingestion (requires service token)
- `/api/admin/*` - Admin endpoints (requires Google OAuth)

Service tokens must be created in the `cirislens.service_tokens` table for billing/proxy to send logs.

## Key Files

| File | Purpose |
|------|---------|
| `terraform/main.tf` | Infrastructure provisioning (Vultr + Hetzner) |
| `terraform/variables.tf` | Configurable parameters |
| `ansible/playbooks/site.yml` | Full deployment playbook |
| `ansible/roles/*/tasks/main.yml` | Service-specific deployment |
| `ansible/roles/*/templates/*.j2` | Service configuration templates |
| `ansible/inventory/production.yml` | Secrets and node configuration |
| `FSD.md` | Locked specification (do not modify) |

## Build/Deploy Commands

```bash
# From ansible/ directory

# Deploy everything
ansible-playbook -i inventory/production.yml playbooks/site.yml

# Deploy specific service to all nodes
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags proxy
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags dns
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags lens

# Deploy to single node
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit us
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit eu

# Ad-hoc commands
ansible vultr -i inventory/production.yml -m shell -a 'docker ps'
ansible all -i inventory/production.yml -m shell -a 'docker logs ciris-billing --tail 20'
```

## Configuration Notes

### Password URL Encoding

Passwords containing special characters (especially `/`) must be URL-encoded in DATABASE_URL strings:
- `/` -> `%2F`
- Use `| regex_replace('/', '%2F')` in Jinja2 templates

### Docker Environment Variables

Docker Compose does NOT reload environment variables on `docker compose restart`. You must:
1. `docker compose down <service>`
2. `docker compose up -d <service>`

Or use Ansible handlers which do full restarts.

### Grafana Datasource UIDs

When provisioning Grafana datasources, the `uid` in the provisioning file must match:
1. Any alerting rules that reference the datasource
2. Any existing datasource in the Grafana database (or delete the DB first)

## Code Style

### Ansible
- Use YAML format consistently
- Template files end in `.j2`
- All secrets via inventory variables (gitignored production.yml)
- Use `become: true` for privileged operations
- Use handlers for service restarts (ensures restart on config change)

### Terraform
- Use `terraform fmt` before committing
- All sensitive values via variables (never hardcoded)
- Tag all resources with `cirisbridge` label

## Gotchas

1. **Terraform state**: Don't lose `terraform.tfstate` - contains current infra mapping
2. **Ansible inventory**: `production.yml` contains secrets - never commit
3. **PostgreSQL replication**: Replica promotion is manual
4. **DNS propagation**: Changes can take up to 24 hours globally
5. **TLS certs**: Caddy auto-renews, but first deploy needs ports 80/443 open
6. **Container restarts**: `docker compose restart` doesn't reload env vars

## Mission Alignment

From the CIRIS Covenant:

> *We vow not to freeze the music into marble, nor surrender the melody to chaos, but to keep the song singable for every voice yet unheard.*

Every change should consider:
1. **Cost**: Does this stay within $30/month budget?
2. **Simplicity**: Is this the simplest solution?
3. **Retirement**: Will this be easy to delete when Veilid is ready?
4. **Privacy**: Does this maintain ZDR compliance?
5. **Integrity**: Are we making proper fixes, not hacks?

**Do not add features that would make retirement harder.**

*This infrastructure exists to be deleted. That's not a bug - it's the mission.*
