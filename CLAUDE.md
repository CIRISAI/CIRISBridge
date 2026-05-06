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
| ~~CIRISDNS~~ | ~~Authoritative DNS (Constellation)~~ — **decommissioned 2026-05-02** (Reticulum migration); containers stopped on both nodes, role preserved at `roles/constellation/` for reversibility | — |

### Sibling Repo Notes

**CIRISProxy (2025-12-17):** Now uses git submodule for CIRISLens SDK (`libs/cirislens/`).
- Includes resilience patterns: CircuitBreaker, ExponentialBackoff (fixes LENS-001)
- Clone with: `git clone --recurse-submodules`
- Update with: `git submodule update --init --recursive`

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

### Test Environment (Full E2E Stack)

Complete test stack with spin up/down capability for end-to-end testing.

**E2E Test Verified: 2026-01-23** - Full pipeline tested successfully:
- Scout Agent → CIRISProxy → CIRISBilling → LLM Providers (Groq/Together/OpenRouter)
- Test auth mode with `ciris_test_canary` user
- Billing charges recorded, LLM responses returned
- Agent made 30+ real LLM calls through proxy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TEST ENVIRONMENT (Vultr VPC: 10.0.0.0/24)                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ test-infra          │  │ test-services       │  │ test-scout          │ │
│  │ ~$12/mo             │  │ ~$24/mo             │  │ ~$6/mo              │ │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤ │
│  │ - PostgreSQL        │  │ - CIRISBilling      │  │ - CIRISManager      │ │
│  │ - CIRISLens         │  │   (test auth)       │  │ - CIRIS Agent       │ │
│  │ - Grafana           │  │ - CIRISProxy        │  │                     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                             │
│  DNS: lens-test / billing-test / proxy-test / scout-test .ciris-services-1.ai │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Full E2E Workflow:**
```bash
# 1. Spin UP infrastructure (~$42/month when running)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags up

# 2. Deploy services
ansible-playbook -i inventory/test.yml playbooks/deploy-test-stack.yml

# 3. Setup (create API key + test agent)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags setup-e2e

# 4. Run end-to-end test
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags test

# 5. Spin DOWN ($0/month when destroyed)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags down
```

Note: Cloudflare API token is loaded from `inventory/production.yml` vault.

See [ansible/runbooks/README.md](ansible/runbooks/README.md) for detailed test environment documentation.

**Manual Provisioning:**
```bash
# 1. Create infrastructure
cd terraform && terraform apply -var="create_test_env=true"

# 2. Add Cloudflare DNS records (from terraform output)
#    lens-test.ciris-services-1.ai    -> test_infra_ip
#    billing-test.ciris-services-1.ai -> test_services_ip
#    proxy-test.ciris-services-1.ai   -> test_services_ip
#    scout-test.ciris-services-1.ai   -> test_scout_ip

# 3. Deploy services
cd ../ansible
ansible-playbook -i inventory/test-dynamic.yml playbooks/deploy-test-stack.yml \
  --vault-password-file ~/.vault_pass

# 4. Destroy when done
cd ../terraform && terraform apply -var="create_test_env=false" -auto-approve
```

**Test Auth Usage:**
```bash
# Check credits
curl -X POST https://billing-test.ciris-services-1.ai/v1/billing/credits/check \
  -H "Authorization: Bearer <TEST_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"oauth_provider": "oauth:test", "external_id": "ciris_test_canary"}'

# LLM request through proxy
curl -X POST https://proxy-test.ciris-services-1.ai/v1/chat/completions \
  -H "Authorization: Bearer <TEST_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"model": "groq/llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hello!"}]}'
```

**Cost:**
| State | Monthly Cost |
|-------|--------------|
| Running | ~$42/month (3 servers) |
| Destroyed | $0/month |

**Security:**
- All servers in isolated VPC (10.0.0.0/24)
- SSH restricted to admin IP only
- Test auth ONLY enabled on test servers (never production)
- Test token stored in Ansible Vault
- Destroyed when not in use

### Legacy Infrastructure (Pending Migration)

These servers predate CIRISBridge and need DNS cutover. See `runbooks/legacy-migration.yml`.

| Server | IP | Vultr ID | Status | Purpose |
|--------|----|-----------| -------|---------|
| llm | 149.28.113.123 | fed95dff-... | Running | Old proxy for llm.ciris.ai |
| billing | 149.28.120.73 | 0d8a8c69-... | Running | Old billing for billing.ciris.ai |
| cirisnode0 | 108.61.119.117 | 47c2431c-... | **Stopped** | Deprecated |

**Migration plan:**
1. Update Cloudflare DNS: `llm.ciris.ai` CNAME → `proxy1.ciris-services-1.ai`
2. Update Cloudflare DNS: `billing.ciris.ai` CNAME → `billing1.ciris-services-1.ai`
3. Monitor traffic shift for 24-48h
4. Decommission legacy servers (~$30/month savings)

### Internal Ports (per node)

| Port | Service | Notes |
|------|---------|-------|
| 53/udp,tcp | Constellation DNS | Public |
| 80/tcp | HTTP | ACME challenges only |
| 443/tcp | Caddy HTTPS | Public |
| ~~5432/tcp~~ | ~~PostgreSQL legacy~~ | Decommissioned 2026-05-02 (Spock cutover); see Spock section |
| 5433/tcp | PostgreSQL (pgEdge Spock — billing) | Internal + multi-master replication |
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

**Public Accord Repository Endpoints (no auth required):**
These endpoints are accessible directly without the `/lens-api` prefix.
Canonical prefix is `/api/v1/accord/*` (renamed from `/covenant/*` in `sql/022_covenant_to_accord.sql`).
The `/api/v1/covenant/*` paths still resolve as deprecated aliases (200 OK + DEPRECATED warning); use `/accord/` in all new code.
- `/api/v1/accord/repository/traces` - Agent reasoning traces (PII scrubbed)
- `/api/v1/accord/repository/statistics` - Aggregate metrics

```bash
# Example: Get recent agent traces
curl "https://lens.ciris-services-1.ai/api/v1/accord/repository/traces?limit=10"

# Example: Get statistics
curl "https://lens.ciris-services-1.ai/api/v1/accord/repository/statistics"
```

Service tokens must be created in the `cirislens.service_tokens` table for billing/proxy to send logs.

## Key Files

| File | Purpose |
|------|---------|
| `terraform/main.tf` | Infrastructure provisioning (Vultr + Hetzner + Test VPC) |
| `terraform/variables.tf` | Configurable parameters |
| `ansible/playbooks/site.yml` | Full deployment playbook |
| `ansible/playbooks/deploy-test.yml` | Test environment deployment |
| `ansible/roles/*/tasks/main.yml` | Service-specific deployment |
| `ansible/roles/*/templates/*.j2` | Service configuration templates |
| `ansible/inventory/production.yml` | Production secrets and node config |
| `ansible/inventory/test.yml` | Test environment inventory |
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
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags scheduler

# Deploy to single node
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit us
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit eu

# Ad-hoc commands
ansible vultr -i inventory/production.yml -m shell -a 'docker ps'
ansible all -i inventory/production.yml -m shell -a 'docker logs ciris-billing --tail 20'

# Check scheduler timers
ansible all -i inventory/production.yml -m shell -a 'systemctl list-timers | grep ciris'

# Test Environment (full e2e workflow)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags up           # 1. Spin up infra
ansible-playbook -i inventory/test.yml playbooks/deploy-test-stack.yml           # 2. Deploy services
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags setup-e2e    # 3. Create API key + agent
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags test         # 4. Run e2e test
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags down         # 5. Spin down

# Spock Multi-Master Replication (migration in progress)
ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml         # Deploy pgEdge containers
ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags spock    # Initialize Spock
ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags status   # Check status
ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags migrate  # Migrate data
```

## Spock Multi-Master Replication

**Status: ✅ Live (cutover ~April 28, 2026). Legacy postgres decommissioned 2026-05-02.**

Billing connects exclusively to `ciris-billing-spock:5433` (multi-master via pgEdge Spock).
Bidirectional replication uses `spock.create_subscription`. Migrations replicate via
`spock.replicate_ddl()` (CIRISBilling#5 fix, migration 0020+) — and the bridge billing
role has a reconciliation task that adds any missed `public.*` tables to the `default`
repset on every deploy as a safety net.

The legacy `ciris-postgres:5432` container (and `ciris-pgbouncer:6432`) are stopped on
both nodes. Compose project lives at `/opt/ciris/postgres/` for rollback during the
30-day soak; final pg_dumps preserved at `/data/backups/legacy-postgres-decom/`. The
postgres role and the native-replication setup play in `playbooks/site.yml` are
commented out. After the soak: `docker compose down --volumes` and remove the role.

### Why Spock?

| Issue with Native Replication | Spock Solution |
|-------------------------------|----------------|
| Manual `origin=none` for loop prevention | Automatic origin tracking |
| Last-write-wins only | Per-table conflict resolution |
| Sequence collisions in multi-master | Built-in sequence offsets |
| Brittle slot management | Native multi-master support |

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPOCK MULTI-MASTER BILLING                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐              ┌─────────────────────────┐      │
│  │ US (Vultr)              │              │ EU (Hetzner)            │      │
│  │ 108.61.242.236:5433     │◄────────────►│ 46.224.81.217:5433      │      │
│  ├─────────────────────────┤   Spock      ├─────────────────────────┤      │
│  │ Container:              │   Bi-dir     │ Container:              │      │
│  │   ciris-billing-spock   │   Repl       │   ciris-billing-spock   │      │
│  │ Node: billing-us        │              │ Node: billing-eu        │      │
│  │ Sequences: odd (1,3,5)  │              │ Sequences: even (1M+)   │      │
│  └─────────────────────────┘              └─────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `ansible/roles/pgedge-postgres/` | pgEdge container deployment role |
| `ansible/group_vars/spock_billing.yml` | Spock configuration (conflict resolution, sequences) |
| `ansible/host_vars/vultr.yml` | US node Spock settings |
| `ansible/host_vars/hetzner.yml` | EU node Spock settings |
| `ansible/playbooks/spock-billing.yml` | Deployment and initialization playbook |

### Migration Steps

1. **Deploy pgEdge containers** (both nodes):
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml
   ```

2. **Initialize Spock replication** (creates nodes and subscriptions):
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags spock
   ```

3. **Verify replication status**:
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags status
   ```

4. **Migrate data from old postgres**:
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags migrate
   ```

5. **Switch billing service to new postgres** (update DATABASE_URL to port 5433)

6. **Decommission old postgres** (after validation period)

### Manual Verification

```bash
# Check Spock status on US
ssh root@108.61.242.236 "docker exec ciris-billing-spock /opt/pgedge/pg15/bin/psql -p 5433 -U billing -d ciris_billing -c \"SELECT * FROM spock.sub_show_status();\""

# Check Spock status on EU
ssh root@46.224.81.217 "docker exec ciris-billing-spock /opt/pgedge/pg15/bin/psql -p 5433 -U billing -d ciris_billing -c \"SELECT * FROM spock.sub_show_status();\""

# Expected output: status = 'replicating' for each subscription
```

### Conflict Resolution Strategy

| Table | Strategy | Rationale |
|-------|----------|-----------|
| users | last_update_wins | User metadata can be updated |
| credits | last_update_wins | Credit balances are mutable |
| charges | first_update_wins | Charges are immutable once created |
| transactions | first_update_wins | Transaction records are immutable |
| api_keys | last_update_wins | API keys can be rotated/updated |

## Billing Update Lifecycle

The billing role follows a structured deployment lifecycle:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. BACKUP  │ -> │  2. DEPLOY  │ -> │  3. MIGRATE │ -> │ 4. SMOKE    │ -> │  5. DONE    │
│  Save image │    │  Pull new   │    │  Run alembic│    │    TEST     │    │  or ROLLBACK│
│  for rollback    │  container  │    │  (US only)  │    │  Verify API │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

| Step | What Happens | On Failure |
|------|--------------|------------|
| Backup | Saves current image digest to `.rollback_info` | Continue |
| Deploy | Pull latest image, restart container | Fail deploy |
| Health Check | Wait for `/health` to return 200 (15 retries) | Fail deploy |
| Migrate | Run `alembic upgrade head` on US node only | Fail deploy |
| Smoke Test | Verify health=healthy, database=connected | Fail deploy |
| Rollback | Use `billing-rollback.yml` runbook | Manual |

**TODO:** OAuth-based smoke tests (new user signup, credit check, charge) pending test account setup.

## Scheduler (Automated Health Monitoring)

Both nodes run systemd timers that post health data to CIRISLens:

| Timer | Schedule | Purpose |
|-------|----------|---------|
| `ciris-heartbeat.timer` | Every 20 min | Node liveness heartbeat (3/hour, alert if <2) |
| `ciris-daily-checks.timer` | 06:00 UTC daily | Cert status, replication, disk |
| `ciris-weekly-security.timer` | Sun 04:00 UTC | Security posture scan |
| `ciris-weekly-cleanup.timer` | Sat 03:00 UTC | Docker/log cleanup |
| `ciris-lens-backup.timer` | 02:00 UTC daily | CIRISLens TimescaleDB backup (US only, 7-day retention) |

**Grafana Alerts:**
- `heartbeat-missing-us-alert` / `heartbeat-missing-eu-alert`: Fires if <2 heartbeats in 60 min
- Alerts use `noDataState: Alerting` - if CIRISLens can't query, it alerts

**Adding scheduler token for new deployments:**
```sql
-- Generate token, then add to cirislens.service_tokens:
INSERT INTO cirislens.service_tokens (service_name, token_hash, description)
VALUES ('ciris-scheduler', encode(sha256('YOUR_TOKEN'::bytea), 'hex'), 'Scheduler heartbeat');
```
Then add `scheduler_service_token: "YOUR_TOKEN"` to `inventory/production.yml`.

## SRE Runbooks

Operational runbooks for incident response and infrastructure management are in `ansible/runbooks/`.

### Available Runbooks

**Incident Response:**
| Runbook | Purpose |
|---------|---------|
| `incident-response.yml` | General incident management with diagnose, fix, escalate, close phases |
| `intrusion-response.yml` | Security incident handling with IP blocking and forensics collection |
| `provider-outage.yml` | Cloud provider failover/failback with DNS update guidance |

**Region Management:**
| Runbook | Purpose |
|---------|---------|
| `add-region.yml` | New region provisioning checklist |
| `remove-region.yml` | Region decommissioning with data archival |

**Operational (run via scheduler or manually):**
| Runbook | Purpose |
|---------|---------|
| `backup-verify.yml` | PostgreSQL backup and replication health |
| `cert-status.yml` | TLS certificate expiration check |
| `disk-cleanup.yml` | Docker/log cleanup with emergency mode |
| `security-scan.yml` | SSH hardening, firewall, updates check |
| `infra-status.yml` | Provider API status, bandwidth, anomaly detection |
| `traffic-monitor.yml` | Network traffic analysis |
| `log-audit.yml` | Service log analysis |
| `image-update.yml` | Container image updates |

**Service-Specific:**
| Runbook | Purpose |
|---------|---------|
| `billing-rollback.yml` | Rollback billing to previous version |
| `billing-ops.yml` | Billing database queries — `--tags status` is the canonical 24h ops report (new accounts by oauth_provider, LLM telemetry, model histogram, hourly distribution, top users, 7-day activity, container health). Also: lookup, usage, tools, transactions, stats. Connects to ciris-billing-spock:5433. |
| `legacy-migration.yml` | Migrate from legacy servers to CIRISBridge |
| `scout-ops.yml` | Scout agent database queries (stuck thoughts, stats) |
| `cert-rotate.yml` | Rotate SSL certs for multi-instance deployments |

**Test Environment:**
| Runbook | Purpose |
|---------|---------|
| `test-env.yml` | Spin up/down full e2e test stack (~$42/mo when running, $0 when destroyed) |
| `e2e-smoke-test.yml` | Production e2e smoke test with Google OAuth (requires refresh token setup) |

**Federation Bootstrap:**
| Runbook | Purpose |
|---------|---------|
| `lens-steward-bootstrap.yml` | One-time: insert self-signed `lens-steward` row into `cirislens.federation_keys` (auto-applies V004). Wires up the federation directory's trust root so lens's `federation_mirror.put_public_key()` calls have a valid FK target. Idempotent. Runs via ephemeral python:3.12 container with persist v0.2.2 + dilithium-py. `--tags verify` for read-only state check. |

### Common Runbook Commands

```bash
# From ansible/ directory

# Operational Health Checks
ansible-playbook -i inventory/production.yml runbooks/cert-status.yml
ansible-playbook -i inventory/production.yml runbooks/backup-verify.yml
ansible-playbook -i inventory/production.yml runbooks/security-scan.yml
ansible-playbook -i inventory/production.yml runbooks/disk-cleanup.yml --tags status
ansible-playbook -i inventory/production.yml runbooks/disk-cleanup.yml --tags cleanup  # Actually clean

# General Incident Response
ansible-playbook -i inventory/production.yml runbooks/incident-response.yml -e "severity=P1"
ansible-playbook -i inventory/production.yml runbooks/incident-response.yml --tags diagnose
ansible-playbook -i inventory/production.yml runbooks/incident-response.yml --tags fix -e "fix_action=restart_all"
ansible-playbook -i inventory/production.yml runbooks/incident-response.yml --tags close -e "resolution='Fixed by restarting service'"

# Provider Outage (detect, failover, failback)
ansible-playbook -i inventory/production.yml runbooks/provider-outage.yml --tags detect
ansible-playbook -i inventory/production.yml runbooks/provider-outage.yml --tags failover -e "failed_region=us"
ansible-playbook -i inventory/production.yml runbooks/provider-outage.yml --tags failback -e "recovered_region=us"

# Security Incident
ansible-playbook -i inventory/production.yml runbooks/intrusion-response.yml --limit vultr
ansible-playbook -i inventory/production.yml runbooks/intrusion-response.yml -e "block_ip=1.2.3.4"

# Region Management
ansible-playbook -i inventory/production.yml runbooks/add-region.yml -e "new_region=ap"
ansible-playbook -i inventory/production.yml runbooks/remove-region.yml -e "region=eu"
ansible-playbook -i inventory/production.yml runbooks/remove-region.yml -e "region=eu" -e "force=true"

# Infrastructure Status (Provider APIs)
ansible-playbook -i inventory/production.yml runbooks/infra-status.yml
ansible-playbook -i inventory/production.yml runbooks/infra-status.yml --tags vultr
ansible-playbook -i inventory/production.yml runbooks/infra-status.yml --tags hetzner
ansible-playbook -i inventory/production.yml runbooks/infra-status.yml --tags bandwidth

# Billing Rollback
ansible-playbook -i inventory/production.yml runbooks/billing-rollback.yml              # Both regions
ansible-playbook -i inventory/production.yml runbooks/billing-rollback.yml --limit us   # US only
ansible-playbook -i inventory/production.yml runbooks/billing-rollback.yml -e "rollback_image=ghcr.io/cirisai/cirisbilling:v0.0.9"

# Legacy Migration (llm.ciris.ai, billing.ciris.ai -> CIRISBridge)
ansible-playbook runbooks/legacy-migration.yml --tags validate      # Pre-cutover validation
ansible-playbook runbooks/legacy-migration.yml --tags monitor       # Post-cutover monitoring
VULTR_API_KEY=xxx ansible-playbook runbooks/legacy-migration.yml --tags decommission  # Delete legacy servers

# Scout Operations (managed Postgres)
ansible-playbook -i inventory/production.yml runbooks/scout-ops.yml --tags stuck                    # Check stuck thoughts
ansible-playbook -i inventory/production.yml runbooks/scout-ops.yml --tags cancel-stuck -e "confirm=yes"  # Cancel stuck
ansible-playbook -i inventory/production.yml runbooks/scout-ops.yml --tags stats                    # Thought/task statistics
ansible-playbook -i inventory/production.yml runbooks/scout-ops.yml --tags stats-by-occurrence      # Stats by agent occurrence

# Billing Operations
# --limit us recommended — Spock is multi-master, US/EU return identical data within sub-second lag
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags status --limit us         # 24h ops report
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags lookup -e "external_id=123" --limit us  # User lookup
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags usage -e "external_id=123" --limit us   # User usage history
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags tools -e "external_id=123" --limit us   # User tool credits
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags transactions -e "limit=20" --limit us   # Recent transactions
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags stats --limit us          # Full system stats (accounts, 7d LLM, tools)

# Test Environment (requires: export CLOUDFLARE_API_TOKEN=xxx)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags up         # Spin up (~$42/mo)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags down       # Spin down ($0/mo)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags status     # Health check
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags setup-e2e  # Create API key + agent
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags test       # Run e2e test

# Production E2E Smoke Test (requires: e2e_google_refresh_token in vault)
ansible-playbook -i inventory/production.yml runbooks/e2e-smoke-test.yml       # Test both regions
```

### Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| P1 | Critical: Complete outage, revenue impact | Immediate escalation, all hands |
| P2 | High: Major feature unavailable | Primary + backup on-call |
| P3 | Medium: Minor issue, workaround available | Primary on-call only |
| P4 | Low: Cosmetic, no user impact | Next business day |

### Runbook Outputs

- **Forensics**: `./forensics/` - Evidence archives from intrusion response
- **Incidents**: `./incidents/` - Incident reports and summaries
- **Archives**: `./archives/` - Data archives from region removal

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

## SPOF Analysis

**Redundant (no SPOF):**
- Compute: Active/Active on both nodes
- DNS: Dual Constellation nameservers (ns1/ns2)
- Billing/Proxy: Both nodes serve traffic via GeoDNS

**Single Points of Failure:**
| Component | Impact | Mitigation |
|-----------|--------|------------|
| CIRISLens | Observability blind | US-only; consider EU replica |
| PostgreSQL WAL | No disaster recovery | Add S3 WAL archival |
| Cloudflare DNS | Domain unresolvable | External dependency |
| GHCR | Deployments blocked | Pre-pull images locally |
| Let's Encrypt | Cert renewal fails | Monitor expiry, backup certs |

**Scheduler provides monitoring for:** cert expiry, replication health, disk space, node liveness.

## Gotchas

1. **Terraform state**: Don't lose `terraform.tfstate` - contains current infra mapping
2. **Ansible inventory**: `production.yml` contains secrets - never commit
3. **PostgreSQL replication**: Replica promotion is manual
4. **DNS propagation**: Changes can take up to 24 hours globally
5. **TLS certs**: Caddy auto-renews, but first deploy needs ports 80/443 open
6. **Container restarts**: `docker compose restart` doesn't reload env vars
7. **SSH config ordering**: OpenSSH uses first-match-wins; use `00-` prefix to override cloud-init
8. **CIRISLens API URL**: Must include `/lens-api` prefix (Caddy strips it before proxying)
9. **Grafana alerts**: Require Grafana restart after provisioning file changes
10. **Shell compatibility**: Runbook scripts must use POSIX sh, not bash arrays

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

*Transitional infrastructure—designed to step aside as decentralized alternatives mature.*
