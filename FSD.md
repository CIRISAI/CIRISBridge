# CIRISBridge Functional Specification Document

**Version:** 1.0  
**Status:** LOCKED  
**Author:** Eric Moore, CEO CIRIS L3C  
**Date:** December 12, 2025  

---

## Document Purpose

This FSD defines CIRISBridge - temporary centralized infrastructure enabling CIRIS services to operate during the transition to Veilid. Every component described here is designed to be retired.

**This document is LOCKED.** Changes require explicit versioning and justification.

---

## 1. Executive Summary

### 1.1 What Is CIRISBridge?

CIRISBridge is scaffolding. It provides the minimum viable centralized infrastructure required for CIRIS ethical agents to be accessible to users *today*, while the Veilid decentralized network matures.

### 1.2 Why Does It Exist?

CIRIS serves Meta-Goal M-1: *Promote sustainable adaptive coherence — the living conditions under which diverse sentient beings may pursue their own flourishing in justice and wonder.*

Agents cannot serve this mission if users cannot reach them. Veilid will eventually provide decentralized discovery and routing, but it is not production-ready for CIRIS's needs today. CIRISBridge fills this gap.

### 1.3 When Does It Go Away?

CIRISBridge components retire progressively as Veilid capabilities mature:

| Component | Retires When | Veilid Replacement |
|-----------|--------------|-------------------|
| DNS | Veilid DHT routing stable | Cryptographic peer discovery |
| Proxy | Veilid private routes mature | Direct agent-to-LLM tunnels |
| Billing | Veilid-native value exchange | TBD (may persist longest) |

**Target:** Full retirement within 18-24 months of Veilid production readiness.

---

## 2. Design Philosophy

### 2.1 Principles

1. **Temporary by Design** - Every component knows it will be replaced
2. **Minimal Footprint** - Only build what's necessary to bridge
3. **No Lock-in** - Avoid dependencies that complicate migration
4. **Cost Discipline** - $25-30/month ceiling; no VC pressure
5. **Fail Gracefully** - Users should always have a path to CIRIS

### 2.2 What We Are NOT Building

- A permanent cloud platform
- Vendor-specific integrations that don't port to Veilid
- Features that assume centralization is forever
- Infrastructure that requires scaling teams to maintain

### 2.3 The Veilid Destination

For context on where we're headed:

**Veilid provides:**
- DHT-based peer discovery (no DNS)
- End-to-end encrypted private routes (no proxy needed)
- Decentralized storage (no central database)
- Cryptographic identity (no traditional auth)

**CIRIS on Veilid:**
- Agents are Veilid nodes with route IDs
- Users connect via Veilid private routes
- Agent discovery through DHT, not DNS
- Economic layer TBD (possibly Veilid-native or hybrid)

---

## 3. Architecture Overview

### 3.1 High-Level Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              USER / CLIENT                   │
                    │  (Mobile App, Web App, CLI, CIRISAgent)     │
                    └─────────────────┬───────────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────────┐
                    │              CIRISBRIDGE                     │
                    │         (This Specification)                 │
                    │                                              │
                    │  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
                    │  │   DNS   │  │ BILLING │  │  PROXY  │      │
                    │  │         │  │         │  │         │      │
                    │  │ "Where" │  │ "Value" │  │ "Route" │      │
                    │  └─────────┘  └─────────┘  └─────────┘      │
                    │                                              │
                    └─────────────────┬───────────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────────┐
                    │           LLM PROVIDERS (ZDR)               │
                    │    Together, Groq, OpenRouter, Anthropic    │
                    └─────────────────────────────────────────────┘
```

### 3.2 The Three Services

| Service | Purpose | Veilid Replacement |
|---------|---------|-------------------|
| **DNS** | Clients find CIRIS endpoints | DHT peer discovery |
| **Billing** | Credits, payments, sustainability | TBD - may hybrid |
| **Proxy** | Route LLM requests with ZDR | Private routes direct to providers |

### 3.3 Multi-Provider Redundancy

```
         CLIENT
            │
     ┌──────┴──────┐
     │             │
     ▼             ▼
┌─────────┐   ┌─────────┐
│  VULTR  │   │ HETZNER │
│ US-East │   │ EU-West │
├─────────┤   ├─────────┤
│ DNS     │   │ DNS     │
│ Billing │   │ Billing │
│ Proxy   │   │ Proxy   │
│ Postgres│◄──►│Postgres │
│ (primary)   │(replica)│
└─────────┘   └─────────┘
```

**Redundancy Matrix:**

| Dimension | Provider A (Vultr) | Provider B (Hetzner) | Failure Mode |
|-----------|-------------------|---------------------|--------------|
| DNS | SOA @ services-1.ai | SOA @ services-2.ai | Client tries other domain |
| Compute | Active | Active | Automatic failover |
| Data | Postgres primary | Postgres sync replica | Manual promotion |
| IP | Direct IP | Direct IP | Client-side failover |

---

## 4. Service Specifications

### 4.1 DNS Service (Constellation)

**Purpose:** Self-hosted authoritative DNS so no third party can cut off access to CIRIS services.

**Technology:** [Constellation](https://github.com/valeriansaliou/constellation) + Redis

**Domains:**
- `ciris-services-1.ai` - SOA at Vultr (US)
- `ciris-services-2.ai` - SOA at Hetzner (EU)

**Features:**
- Authoritative DNS for both domains
- Geo-DNS routing (14 regions)
- Health-check based failover
- REST API for dynamic record management

**Ports:**
- 53/udp, 53/tcp - DNS (public)
- 8080 - REST API (internal only)

**Record Schema:**
```yaml
zones:
  ciris-services-1.ai:
    - name: billing1
      type: A
      value: <vultr-ip>
      ttl: 300
      health_check: https://billing1.ciris-services-1.ai/health
    - name: proxy1
      type: A
      value: <vultr-ip>
      ttl: 300
      health_check: https://proxy1.ciris-services-1.ai/health
```

**Retirement Path:**
1. Veilid DHT becomes stable for peer discovery
2. CIRIS agents register Veilid route IDs
3. Clients updated to resolve via Veilid first, DNS fallback
4. DNS retired when client migration complete

---

### 4.2 Billing Service (CIRISBilling)

**Purpose:** Enable sustainable operation without advertising or data monetization.

**Technology:** FastAPI + PostgreSQL + Stripe

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/v1/credits/{user_id}` | GET | Check balance |
| `/v1/credits/purchase` | POST | Initiate Stripe purchase |
| `/v1/credits/consume` | POST | Deduct credits (idempotent) |
| `/v1/usage/{user_id}` | GET | Usage history |

**Credit Model:**
- $0.05 per interaction (adjustable)
- Pre-purchased credits
- No subscriptions initially (simplicity)
- Idempotent consumption (exactly-once semantics)

**Data Model:**
```sql
-- Core tables
users (id, email, created_at)
credit_balances (user_id, balance, updated_at)
transactions (id, user_id, amount, type, idempotency_key, created_at)
stripe_events (event_id, processed_at, payload)
```

**Replication:**
- Vultr: Postgres primary
- Hetzner: Postgres sync replica
- Manual failover (automatic promotion too risky for financial data)

**Retirement Path:**
1. Billing may persist longest - value exchange needed regardless of transport
2. Potential Veilid-native value layer integration
3. May evolve rather than retire entirely
4. Consider: decentralized credit verification via Veilid DHT

---

### 4.3 Proxy Service (CIRISProxy)

**Purpose:** Route LLM inference requests to providers while maintaining Zero Data Retention guarantees.

**Technology:** [LiteLLM](https://github.com/BerriAI/litellm)

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/v1/chat/completions` | POST | OpenAI-compatible inference |
| `/v1/models` | GET | Available models |

**Provider Priority:**
1. Together AI (primary - ZDR by default)
2. Groq (fallback - fast inference)
3. OpenRouter (fallback - model variety)
4. Direct Anthropic/OpenAI (if user provides keys)

**ZDR Configuration:**
All providers configured with Zero Data Retention where available:
- Together: ZDR default
- Groq: Enterprise ZDR
- OpenRouter: Pass-through (provider-dependent)

**Request Flow:**
```
Client → Proxy → Credit Check (Billing) → LLM Provider → Response
                      │
                      └── Reject if insufficient credits
```

**Retirement Path:**
1. Veilid private routes mature
2. CIRIS agents establish direct Veilid tunnels to LLM providers
3. Proxy becomes optional optimization layer
4. Full retirement when direct routes prove reliable

---

## 5. Infrastructure Specification

### 5.1 Compute Resources

**Vultr (US-East, New Jersey):**
- Instance: VC2 - 2 vCPU, 4GB RAM, 80GB SSD
- Cost: ~$24/month
- Role: Primary (DNS SOA for services-1, Postgres primary)

**Hetzner (EU-West, Falkenstein):**
- Instance: CX22 - 2 vCPU, 4GB RAM, 40GB SSD
- Cost: ~€4/month (~$4.50)
- Role: Secondary (DNS SOA for services-2, Postgres replica)
- Block Storage: 20GB for Postgres (~€1/month)

**Total Target: $25-30/month**

### 5.2 Network Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         INTERNET                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
     ┌────────┐       ┌────────┐       ┌────────┐
     │ :53    │       │ :443   │       │ :443   │
     │  DNS   │       │Billing │       │ Proxy  │
     └────────┘       └────────┘       └────────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │   INTERNAL  │
                    │   NETWORK   │
                    ├─────────────┤
                    │ :5432 PG    │
                    │ :6379 Redis │
                    │ :8080 APIs  │
                    └─────────────┘
```

**Public Ports:**
- 53/udp, 53/tcp - DNS
- 443/tcp - HTTPS (Billing, Proxy)
- 22/tcp - SSH (restricted to admin IPs)

**Internal Only:**
- 5432 - PostgreSQL
- 6379 - Redis
- 8080 - Constellation REST API
- 4000 - LiteLLM internal

### 5.3 TLS/Certificates

- Let's Encrypt via Certbot
- Auto-renewal via cron
- Certificates for:
  - `billing1.ciris-services-1.ai`
  - `billing1.ciris-services-2.ai`
  - `proxy1.ciris-services-1.ai`
  - `proxy1.ciris-services-2.ai`

### 5.4 DNS Records

**ciris-services-1.ai (Vultr SOA):**
```
@       IN  SOA   ns1.ciris-services-1.ai. admin.ciris.ai. (
                  2025121201 ; serial
                  3600       ; refresh
                  600        ; retry
                  604800     ; expire
                  300 )      ; minimum
@       IN  NS    ns1.ciris-services-1.ai.
@       IN  NS    ns2.ciris-services-2.ai.
ns1     IN  A     <vultr-ip>
billing1 IN A     <vultr-ip>
proxy1  IN  A     <vultr-ip>
```

**ciris-services-2.ai (Hetzner SOA):**
```
@       IN  SOA   ns2.ciris-services-2.ai. admin.ciris.ai. (
                  2025121201 ; serial
                  3600       ; refresh
                  600        ; retry
                  604800     ; expire
                  300 )      ; minimum
@       IN  NS    ns1.ciris-services-1.ai.
@       IN  NS    ns2.ciris-services-2.ai.
ns2     IN  A     <hetzner-ip>
billing1 IN A     <hetzner-ip>
proxy1  IN  A     <hetzner-ip>
```

---

## 6. Data Architecture

### 6.1 PostgreSQL

**Primary:** Vultr  
**Replica:** Hetzner (synchronous replication)

**Databases:**
- `cirisbilling` - Credit management, transactions, users

**Replication Configuration:**
```
synchronous_commit = on
synchronous_standby_names = 'hetzner_replica'
```

**Backup Strategy:**
- pg_dump daily to encrypted S3-compatible storage
- WAL archiving for point-in-time recovery
- 30-day retention

### 6.2 Redis

**Purpose:** DNS record storage for Constellation

**Deployment:** Local to each region (no cross-region replication)

**Persistence:** RDB snapshots every 5 minutes

**Data:** DNS records only - ephemeral, reconstructable from zones.yaml

---

## 7. Security Specification

### 7.1 Authentication

| Service | Method |
|---------|--------|
| SSH | Key-based only, no password auth |
| Constellation API | Bearer token |
| Billing API | JWT (issued by Billing service) |
| Proxy API | JWT + credit verification |
| Postgres | Password + SSL required |
| Redis | Password + bind to localhost |

### 7.2 Secrets Management

**Never in repository:**
- API keys (Vultr, Hetzner, Stripe, LLM providers)
- Database passwords
- JWT signing keys
- Constellation API tokens

**Storage:**
- Environment variables in `.env` (not committed)
- Docker secrets for container deployment
- Consider HashiCorp Vault for Phase 2

### 7.3 Firewall Rules (UFW)

```bash
# Default deny
ufw default deny incoming
ufw default allow outgoing

# Public services
ufw allow 53/udp    # DNS
ufw allow 53/tcp    # DNS
ufw allow 443/tcp   # HTTPS

# Admin (restrict to known IPs)
ufw allow from <admin-ip> to any port 22

# Inter-region (restrict to peer IP)
ufw allow from <peer-ip> to any port 5432  # Postgres replication
```

### 7.4 Privacy Guarantees

From the CIRIS Comprehensive Guide:
> "Your conversations exist only on your local device."

CIRISBridge maintains this by:
1. **ZDR Providers:** All LLM providers configured for Zero Data Retention
2. **No Prompt Logging:** Proxy does not log request/response content
3. **Minimal Billing Data:** Only credits, not conversation content
4. **TLS Everywhere:** All traffic encrypted in transit

---

## 8. Deployment Specification

### 8.1 Technology Stack

| Layer | Technology |
|-------|------------|
| Provisioning | Terraform |
| Configuration | Ansible |
| Containers | Docker + docker-compose |
| Reverse Proxy | Caddy (auto TLS) |
| Process Manager | Docker restart policies |

### 8.2 Repository Structure

```
CIRISBridge/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── vultr.tf
│   └── hetzner.tf
├── ansible/
│   ├── inventory/
│   │   ├── production.yml
│   │   └── staging.yml
│   ├── playbooks/
│   │   ├── site.yml          # Full deployment
│   │   ├── dns.yml           # DNS only
│   │   ├── billing.yml       # Billing only
│   │   └── proxy.yml         # Proxy only
│   └── roles/
│       ├── common/           # Base setup, firewall, Docker
│       ├── constellation/    # DNS service
│       ├── billing/          # Billing service
│       ├── proxy/            # Proxy service
│       ├── postgres/         # Database
│       └── caddy/            # Reverse proxy
├── docker/
│   ├── docker-compose.yml    # All services
│   ├── constellation/
│   ├── billing/
│   └── proxy/
├── scripts/
│   ├── sync-records.sh       # Push DNS records
│   ├── health-check.sh       # Verify all services
│   ├── backup-db.sh          # Postgres backup
│   └── failover-db.sh        # Manual DB failover
├── records/
│   └── zones.yaml            # DNS record source of truth
├── docs/
│   └── adr/                  # Architecture Decision Records
├── tests/
│   ├── terraform/
│   └── integration/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── FSD.md                    # This document (LOCKED)
└── LICENSE
```

### 8.3 Deployment Workflow

```bash
# 1. Provision infrastructure
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 2. Configure servers
cd ../ansible
ansible-playbook -i inventory/production.yml playbooks/site.yml

# 3. Sync DNS records
./scripts/sync-records.sh

# 4. Verify deployment
./scripts/health-check.sh
```

### 8.4 CI/CD

**Phase 1 (Current):** Manual deployment via commands above

**Phase 2 (Future):**
- GitHub Actions for Terraform plan on PR
- Manual approval for apply
- Ansible deployment on merge to main
- Integration tests post-deploy

---

## 9. Monitoring & Observability

### 9.1 Health Endpoints

| Service | Endpoint | Expected |
|---------|----------|----------|
| DNS | `http://localhost:8080/health` | `{"status": "ok"}` |
| Billing | `https://billing1.../health` | `{"status": "healthy"}` |
| Proxy | `https://proxy1.../health` | `{"status": "healthy"}` |

### 9.2 External Monitoring

- UptimeRobot (or similar) for public endpoint checks
- Alert channels: Email, SMS for critical
- Check frequency: 1 minute

### 9.3 Metrics

| Service | Metrics Endpoint |
|---------|-----------------|
| Constellation | `/metrics` (Prometheus format) |
| Billing | `/metrics` (Prometheus format) |
| Proxy | LiteLLM built-in metrics |

**Key Metrics:**
- DNS: Queries/second, latency, cache hit rate
- Billing: Requests/second, credit operations, Stripe webhook latency
- Proxy: Requests/second, provider latency, error rate by provider

### 9.4 Logging

- All services log to stdout (Docker captures)
- Log levels: INFO in production, DEBUG for troubleshooting
- Retention: 14 days local, consider Loki for centralization (Phase 2)

### 9.5 Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Any region health check fails | Warning | Investigate within 1 hour |
| Both regions fail | Critical | Immediate response |
| Postgres replication lag > 10s | Warning | Check network |
| Postgres replication broken | Critical | Manual intervention |
| Credit balance negative | Critical | Investigate immediately |
| Cost exceeds $40/month | Warning | Review resource usage |

---

## 10. Failure Modes & Recovery

### 10.1 Failure Matrix

| Failure | Detection | Automatic Recovery | Manual Recovery |
|---------|-----------|-------------------|-----------------|
| Vultr DNS down | Health check | Client uses services-2 | Restart Constellation |
| Hetzner DNS down | Health check | Client uses services-1 | Restart Constellation |
| Vultr Billing down | Health check | Client fails to services-2 | Restart container |
| Postgres primary down | Replication monitor | None | Promote replica |
| Postgres replica down | Replication lag | None | Rebuild replica |
| Redis down | Constellation health | Docker restart | Check persistence |
| Certificate expired | Certbot cron | Auto-renewal | Manual certbot |
| Provider outage | External monitor | Client failover | Wait or migrate |

### 10.2 Postgres Failover Procedure

```bash
# On Hetzner (replica):
# 1. Verify primary is truly down
pg_isready -h <vultr-ip>

# 2. Promote replica
sudo -u postgres pg_ctl promote -D /var/lib/postgresql/data

# 3. Update application configs to point to new primary

# 4. Update DNS if needed
./scripts/sync-records.sh

# 5. When Vultr recovers, rebuild as new replica
```

### 10.3 Complete Region Failure

If one entire region fails:
1. All services continue on surviving region
2. Postgres may need promotion if primary region failed
3. DNS TTL determines client switchover time (300s default)
4. Monitor surviving region closely for overload

---

## 11. Cost Management

### 11.1 Budget

**Target:** $25-30/month  
**Hard Ceiling:** $40/month (triggers review)

### 11.2 Cost Breakdown

| Item | Provider | Monthly |
|------|----------|---------|
| Compute (US) | Vultr VC2 | ~$24 |
| Compute (EU) | Hetzner CX22 | ~€4 ($4.50) |
| Block Storage | Hetzner 20GB | ~€1 ($1.10) |
| Domains (2) | Annual ÷ 12 | ~$3 |
| **Total** | | **~$32.60** |

### 11.3 Cost Optimization Options

If budget pressure:
1. Downgrade Vultr to VC2 1vCPU/1GB (~$6) - DNS/Proxy only, Billing on Hetzner
2. Use single region (sacrifices redundancy)
3. Move more services to Hetzner (cheaper)

### 11.4 Why This Matters

From Mission-Driven Development:
> "Low cost = low barrier to operation. No need for aggressive monetization. Sustainable indefinitely without venture capital pressure."

CIRISBridge must remain affordable to operate even with zero revenue. This is ethical infrastructure, not a growth startup.

---

## 12. Migration Path to Veilid

### 12.1 Veilid Readiness Criteria

Before migrating each component:

| Component | Criteria |
|-----------|----------|
| DNS → DHT | Veilid DHT stable, peer discovery works across NAT |
| Proxy → Private Routes | Veilid private routes reliable, latency acceptable |
| Billing → ? | Value exchange mechanism defined on Veilid |

### 12.2 Migration Phases

**Phase V1: Hybrid Discovery**
- CIRIS agents register both DNS names AND Veilid route IDs
- Clients try Veilid first, fall back to DNS
- Monitor Veilid success rate

**Phase V2: Veilid Primary**
- Veilid becomes primary discovery mechanism
- DNS maintained for legacy clients
- New clients Veilid-only

**Phase V3: DNS Retirement**
- DNS shut down
- All discovery via Veilid DHT
- domains allowed to expire or redirect to documentation

**Phase V4: Proxy Retirement**
- Direct Veilid tunnels to LLM providers
- Proxy deprecated
- ZDR maintained via Veilid encryption

**Phase V5: Billing Evolution**
- TBD based on Veilid value exchange capabilities
- May evolve rather than retire
- Possibly decentralized credit verification

### 12.3 Success Metrics

Migration considered successful when:
- 95%+ of requests route via Veilid
- DNS receives < 5% of discovery traffic
- No increase in user-reported failures
- Cost reduced (no cloud infrastructure)

---

## 13. Phase Implementation

### 13.1 Phase 1: Minimum Viable Bridge (Current)

**Goal:** Get CIRIS services accessible to users

**Deliverables:**
- [ ] Terraform provisions both regions
- [ ] Ansible configures all services
- [ ] DNS resolves both domains
- [ ] Billing accepts credits and processes transactions
- [ ] Proxy routes to LLM providers with ZDR
- [ ] Postgres replication functional
- [ ] Health checks pass
- [ ] Basic monitoring active

**Timeline:** 2-3 weeks

### 13.2 Phase 2: Hardening

**Goal:** Production-ready reliability

**Deliverables:**
- [ ] External monitoring (UptimeRobot)
- [ ] Alerting configured
- [ ] Backup automation
- [ ] Failover procedures documented and tested
- [ ] Load testing completed
- [ ] Security audit (self-review)

**Timeline:** 2-3 weeks after Phase 1

### 13.3 Phase 3: Veilid Preparation

**Goal:** Ready to begin migration

**Deliverables:**
- [ ] Veilid integration research complete
- [ ] Hybrid discovery prototype
- [ ] Migration runbook drafted
- [ ] Client libraries support both discovery methods

**Timeline:** When Veilid is ready (external dependency)

---

## 14. Open Questions

### 14.1 Technical

1. **Postgres vs SQLite:** Is Postgres overkill for billing? SQLite + Litestream could reduce complexity.
2. **Redis necessity:** Could Constellation use embedded storage instead?
3. **Caddy vs Nginx:** Caddy simpler for auto-TLS, but Nginx more familiar.

### 14.2 Operational

1. **On-call:** Who responds to 3am alerts? (Current answer: Eric)
2. **Runbooks:** How detailed do failover procedures need to be?
3. **Staging:** Do we need a staging environment at this budget?

### 14.3 Strategic

1. **Billing on Veilid:** What does decentralized credit verification look like?
2. **Multi-tenant:** Will CIRISBridge serve multiple CIRIS deployments?
3. **Timeline:** When realistically is Veilid production-ready?

---

## 15. Appendices

### Appendix A: External Dependencies

| Dependency | Purpose | Risk if Unavailable |
|------------|---------|---------------------|
| Vultr | US compute | Failover to Hetzner |
| Hetzner | EU compute | Failover to Vultr |
| Stripe | Payments | Cannot purchase credits |
| Together AI | LLM inference | Failover to Groq |
| Groq | LLM inference | Failover to OpenRouter |
| Let's Encrypt | TLS certs | Manual cert management |
| MaxMind | Geo-IP database | Geo-DNS disabled |

### Appendix B: Related Documents

- **CIRIS Covenant** - Why CIRIS exists
- **CIRIS Comprehensive Guide** - What a CIRIS agent is
- **Mission-Driven Development** - How we build
- **CIRISAgent README** - The agent runtime

### Appendix C: Glossary

| Term | Definition |
|------|------------|
| DHT | Distributed Hash Table - Veilid's peer discovery mechanism |
| SOA | Start of Authority - DNS record designating authoritative server |
| ZDR | Zero Data Retention - Provider doesn't store prompts/responses |
| WAL | Write-Ahead Log - Postgres replication mechanism |
| Private Route | Veilid encrypted tunnel between peers |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-12 | Eric Moore | Initial specification |

---

*This infrastructure exists to be deleted. That's not a bug—it's the mission.*
