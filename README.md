# CIRISBridge

Temporary scaffolding infrastructure for CIRIS Agent services. Designed to be retired when Veilid DHT becomes production-ready.

## Overview

CIRISBridge provides multi-region infrastructure for:
- **CIRISBilling** - Credit-based usage gating
- **CIRISProxy** - LLM routing with Zero Data Retention
- **CIRISDNS** - Self-hosted authoritative DNS (Constellation)

## Architecture

```
         Clients
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌────────┐     ┌────────┐
│ Vultr  │     │Hetzner │
│  (US)  │◄───►│  (EU)  │
│Chicago │     │Germany │
└───┬────┘     └───┬────┘
    │              │
    │   Services   │
    ├──────────────┤
    │ Constellation│  DNS
    │ PostgreSQL   │  Database (primary/replica)
    │ CIRISBilling │  Credits API
    │ CIRISProxy   │  LLM Gateway
    │ Caddy        │  TLS termination
    └──────────────┘
```

## Quick Start

### Prerequisites

- Terraform >= 1.0
- Ansible >= 2.12
- SSH key pair

### 1. Configure Credentials

```bash
# Copy and edit Terraform variables
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
vim terraform/terraform.tfvars

# Copy and edit environment
cp .env.example .env
vim .env
```

### 2. Deploy Infrastructure

```bash
# Initialize and deploy
./scripts/deploy.sh infra

# This provisions:
# - Vultr VPS in Chicago (~$24/mo)
# - Hetzner VPS in Germany (~€6/mo)
# - Firewalls, SSH keys, networking
```

### 3. Deploy Services

```bash
# Deploy all services
./scripts/deploy.sh services

# Or deploy individually
./scripts/deploy.sh dns
./scripts/deploy.sh billing
./scripts/deploy.sh proxy
```

### 4. Verify Health

```bash
./scripts/health-check.sh
```

## Directory Structure

```
CIRISBridge/
├── terraform/           # Infrastructure as Code
│   ├── main.tf         # Provider config, resources
│   ├── variables.tf    # Input variables
│   └── outputs.tf      # Outputs (IPs, inventory)
├── ansible/             # Configuration Management
│   ├── inventory/      # Host definitions
│   ├── playbooks/      # Deployment playbooks
│   └── roles/          # Service roles
│       ├── common/     # Base OS setup
│       ├── constellation/ # DNS
│       ├── postgres/   # Database
│       ├── caddy/      # TLS
│       ├── billing/    # CIRISBilling
│       └── proxy/      # CIRISProxy
├── scripts/             # Operations scripts
│   ├── deploy.sh       # Main deployment
│   ├── health-check.sh # Service health
│   ├── sync-records.sh # DNS sync
│   ├── backup-db.sh    # Database backup
│   └── failover-db.sh  # Manual failover
└── docs/
```

## Cost Breakdown

| Item | Monthly Cost |
|------|-------------|
| Vultr VC2 (2 vCPU, 4GB) | ~$24 |
| Hetzner CX22 (2 vCPU, 4GB) | ~€6 |
| Hetzner Volume (20GB) | ~€1 |
| Domains (amortized) | ~$3 |
| **Total** | **~$34/month** |

## Operations

### Health Check

```bash
./scripts/health-check.sh
```

### Database Backup

```bash
POSTGRES_PASSWORD=xxx ./scripts/backup-db.sh
```

### Manual Failover

```bash
./scripts/failover-db.sh status   # Check health
./scripts/failover-db.sh promote  # Promote replica
```

### DNS Record Sync

```bash
./scripts/sync-records.sh
```

## DNS Configuration

After deployment, configure at your registrar:

**NS Records:**
```
ciris-services-1.ai  NS  ns1.ciris-services-1.ai
ciris-services-1.ai  NS  ns1.ciris-services-2.ai
```

**Glue Records:**
```
ns1.ciris-services-1.ai  A  <VULTR_IP>
ns1.ciris-services-2.ai  A  <HETZNER_IP>
```

## Retirement Path

CIRISBridge is temporary infrastructure. It will be retired when:

1. Veilid DHT is stable for peer discovery
2. CIRIS agents register Veilid route IDs
3. Clients migrate to Veilid-first resolution
4. Centralized DNS traffic drops below 5%

**Target: Full retirement within 18-24 months of Veilid production readiness.**

## Related Repositories

| Repo | Purpose |
|------|---------|
| [CIRISBilling](../CIRISBilling) | Credit management service |
| [CIRISProxy](../CIRISProxy) | LLM routing proxy |
| [CIRISDNS](../CIRISDNS) | DNS configuration |
| [CIRISAgent](../CIRISAgent) | Agent runtime |

## License

Apache 2.0 - See [LICENSE](LICENSE)

---

*This infrastructure exists to be deleted. That's not a bug—it's the mission.*
