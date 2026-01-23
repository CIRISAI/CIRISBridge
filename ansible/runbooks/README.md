# CIRISBridge Runbooks

Operational runbooks for infrastructure management and testing.

## Test Environment

Complete end-to-end test stack for validating the full CIRIS pipeline:

```
User → Agent → Proxy → Billing → LLM Provider → Response
```

### Architecture

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

### Cost

| State | Monthly Cost |
|-------|--------------|
| Running | ~$42/month (3 servers) |
| Destroyed | $0/month |

### Quick Start

```bash
cd ansible

# 1. Spin up infrastructure (creates VMs + DNS records)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags up

# 2. Deploy all services
ansible-playbook -i inventory/test.yml playbooks/deploy-test-stack.yml

# 3. Setup automation (creates billing API key + test agent)
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags setup-e2e

# 4. Run end-to-end test
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags test

# 5. Spin down when done
ansible-playbook -i inventory/test.yml runbooks/test-env.yml --tags down
```

### Available Tags

| Tag | Purpose |
|-----|---------|
| `up` | Provision infrastructure (Terraform) + create DNS records |
| `down` | Destroy infrastructure + remove DNS records |
| `status` | Health check all services |
| `credentials` | Display test auth credentials |
| `setup-e2e` | Create billing API key and test agent |
| `test` | Run end-to-end test through agent |

### E2E Test Flow

1. **Setup** (`--tags setup-e2e`):
   - Creates service API key in CIRISBilling
   - Updates CIRISProxy with the new API key
   - Creates test agent via CIRISManager
   - Configures agent with billing integration

2. **Test** (`--tags test`):
   - Verifies billing, lens, and proxy health
   - Logs into the agent (admin/ciris_admin_password)
   - Sends test message through the agent
   - Agent routes through proxy → billing → LLM
   - Validates response received

### Test Endpoints

| Service | URL |
|---------|-----|
| Lens | https://lens-test.ciris-services-1.ai |
| Billing | https://billing-test.ciris-services-1.ai |
| Proxy | https://proxy-test.ciris-services-1.ai |
| Scout | https://scout-test.ciris-services-1.ai |

### Public Covenant Repository

Agent reasoning traces are publicly accessible (no auth required):

```bash
# Get recent traces (PII scrubbed)
curl "https://lens.ciris-services-1.ai/api/v1/covenant/repository/traces?limit=10"

# Get covenant statistics
curl "https://lens.ciris-services-1.ai/api/v1/covenant/repository/statistics"
```

### Configuration Files

| File | Purpose |
|------|---------|
| `inventory/test.yml` | Test environment secrets and config (gitignored) |
| `inventory/test-dynamic.yml` | Auto-generated IPs from Terraform (gitignored) |
| `playbooks/deploy-test-stack.yml` | Service deployment playbook |
| `runbooks/test-env.yml` | Spin up/down automation |

### Security Notes

- Test auth is ONLY enabled on test servers (never production)
- All servers in isolated VPC (10.0.0.0/24)
- SSH restricted to admin IP only
- Cloudflare API token stored in encrypted vault (`inventory/production.yml`)
- Test secrets in `inventory/test.yml` (gitignored)

---

## Other Runbooks

### Incident Response

| Runbook | Purpose |
|---------|---------|
| `incident-response.yml` | General incident management |
| `intrusion-response.yml` | Security incident handling |
| `provider-outage.yml` | Cloud provider failover |

### Operational

| Runbook | Purpose |
|---------|---------|
| `backup-verify.yml` | PostgreSQL backup health |
| `cert-status.yml` | TLS certificate expiration |
| `disk-cleanup.yml` | Docker/log cleanup |
| `security-scan.yml` | Security posture check |

### Service-Specific

| Runbook | Purpose |
|---------|---------|
| `billing-ops.yml` | Billing database queries |
| `billing-rollback.yml` | Rollback billing version |
| `scout-ops.yml` | Scout agent database queries |

See [CLAUDE.md](../../CLAUDE.md) for complete runbook documentation.
