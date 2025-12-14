# CIRISBridge Operations Guide

This guide covers day-to-day operations for the CIRISBridge infrastructure.

## Infrastructure Overview

CIRISBridge runs a multi-region deployment across two cloud providers:

| Region | Provider | Location | IP | Role |
|--------|----------|----------|-----|------|
| US | Vultr | Chicago | 108.61.242.236 | Primary (Postgres primary, CIRISLens) |
| EU | Hetzner | Germany | 46.224.81.217 | Secondary (Postgres replica) |

## Services

Each node runs the following containerized services:

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| CIRISBilling | `ciris-billing` | 8000 | Credits, payments, user authentication |
| CIRISProxy | `ciris-proxy` | 4000 | LLM routing with billing integration |
| PostgreSQL | `ciris-postgres` | 5432 | Database with bi-directional replication |
| Caddy | `ciris-caddy` | 80, 443 | TLS termination, reverse proxy |
| Constellation | `ciris-dns` | 53 | Authoritative DNS |

Additionally, the US node runs:
- **CIRISLens** (`ciris-lens`) - Centralized observability on port 8200
- **Grafana** - Dashboards on port 3001

## Common Operations

### Checking Service Status

```bash
# From ansible/ directory

# Check all containers on all nodes
ansible all -i inventory/production.yml -m shell -a 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# Check specific node
ansible vultr -i inventory/production.yml -m shell -a 'docker ps'
ansible hetzner -i inventory/production.yml -m shell -a 'docker ps'
```

### Viewing Logs

```bash
# Recent logs from a service
ansible vultr -i inventory/production.yml -m shell -a 'docker logs ciris-billing --tail 50'
ansible vultr -i inventory/production.yml -m shell -a 'docker logs ciris-proxy --tail 50'

# Follow logs in real-time (run on server directly)
ssh root@108.61.242.236 'docker logs -f ciris-billing'

# Search for errors
ansible all -i inventory/production.yml -m shell -a 'docker logs ciris-billing 2>&1 | grep -i error | tail -20'
```

### Health Checks

```bash
# Check all service health endpoints
ansible all -i inventory/production.yml -m uri -a 'url=http://localhost:8080/health'
ansible all -i inventory/production.yml -m uri -a 'url=http://localhost:4000/health/liveliness'

# Check database connectivity
ansible all -i inventory/production.yml -m shell -a 'docker exec ciris-postgres pg_isready -U postgres'

# Check external endpoints (from your machine)
curl -s https://billing1.ciris-services-1.ai/health | jq
curl -s https://proxy1.ciris-services-1.ai/health/liveliness
```

### Restarting Services

```bash
# Restart a single service (preserves data)
ansible vultr -i inventory/production.yml -m shell -a 'cd /opt/ciris/billing && docker compose down && docker compose up -d'

# Restart via Ansible playbook (recommended - ensures config sync)
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags proxy

# Restart all services on a node
ansible vultr -i inventory/production.yml -m shell -a 'cd /opt/ciris/billing && docker compose restart'
ansible vultr -i inventory/production.yml -m shell -a 'cd /opt/ciris/proxy && docker compose restart'
```

### Updating Container Images

```bash
# Pull latest images and restart
ansible all -i inventory/production.yml -m shell -a 'cd /opt/ciris/billing && docker compose pull && docker compose down && docker compose up -d'
ansible all -i inventory/production.yml -m shell -a 'cd /opt/ciris/proxy && docker compose pull && docker compose down && docker compose up -d'

# Or use Ansible playbook (pulls and restarts)
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags proxy
```

### Database Operations

```bash
# Connect to database
ansible vultr -i inventory/production.yml -m shell -a 'docker exec -it ciris-postgres psql -U postgres -d ciris_billing'

# Check replication status (on primary)
ansible vultr -i inventory/production.yml -m shell -a 'docker exec ciris-postgres psql -U postgres -c "SELECT * FROM pg_stat_replication;"'

# Check replication lag (on replica)
ansible hetzner -i inventory/production.yml -m shell -a 'docker exec ciris-postgres psql -U postgres -c "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(), pg_last_xact_replay_timestamp();"'

# Backup database
ansible vultr -i inventory/production.yml -m shell -a 'docker exec ciris-postgres pg_dump -U postgres ciris_billing > /tmp/backup.sql'
```

## Monitoring

### CIRISLens (Grafana)

Access Grafana at: https://lens.ciris-services-1.ai

Available dashboards:
- **Service Health** - Container status, health checks
- **Error Correlation** - Cross-service error tracking
- **Billing Analytics** - Credit usage, transactions

### Log Queries

Logs are stored in PostgreSQL (`cirislens.service_logs` table). Query via Grafana or directly:

```sql
-- Recent errors
SELECT timestamp, service_name, level, message
FROM cirislens.service_logs
WHERE level IN ('ERROR', 'CRITICAL')
ORDER BY timestamp DESC
LIMIT 50;

-- Errors by service (last hour)
SELECT service_name, COUNT(*) as error_count
FROM cirislens.service_logs
WHERE level IN ('ERROR', 'CRITICAL')
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY service_name;
```

### Alerts

Grafana alerts are configured for:
- Service errors detected (any ERROR/CRITICAL log)
- High error rate (>5 errors in 5 minutes)
- Billing service errors

Excluded from alerts:
- Play Integrity errors (expected for debug builds)
- Rate limit errors (normal operation)

## Deployment

### Full Deployment

```bash
cd ansible/
ansible-playbook -i inventory/production.yml playbooks/site.yml
```

### Service-Specific Deployment

```bash
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags proxy
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags dns
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags lens
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags caddy
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags postgres
```

### Single-Region Deployment

```bash
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit vultr
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit hetzner
```

## Incident Response

Use the runbooks in `ansible/runbooks/` for structured incident response:

| Situation | Runbook |
|-----------|---------|
| General service issues | `incident-response.yml` |
| Security incident | `intrusion-response.yml` |
| Provider outage | `provider-outage.yml` |
| Adding a region | `add-region.yml` |
| Removing a region | `remove-region.yml` |

Quick diagnostics:
```bash
ansible-playbook -i inventory/production.yml runbooks/incident-response.yml --tags diagnose
```

## Troubleshooting

### Service Won't Start

1. Check logs: `docker logs ciris-<service> --tail 100`
2. Check config: Verify `.env` file has all required variables
3. Check network: Ensure `postgres_ciris` Docker network exists
4. Check dependencies: Database must be running first

### Database Connection Issues

1. Verify PostgreSQL is running: `docker ps | grep postgres`
2. Check connection: `docker exec ciris-postgres pg_isready`
3. Verify credentials in `.env` match database
4. Check network connectivity between containers

### TLS Certificate Issues

Caddy auto-manages certificates. If issues occur:
1. Check Caddy logs: `docker logs ciris-caddy`
2. Verify DNS points to correct IP
3. Ensure ports 80/443 are open
4. Restart Caddy: `cd /opt/ciris/caddy && docker compose restart`

### Replication Lag

If replica is behind:
1. Check network between regions
2. Verify replication slot exists on primary
3. Check subscription status on replica
4. Monitor with: `SELECT * FROM pg_stat_subscription;`

## File Locations

On each node:

| Path | Contents |
|------|----------|
| `/opt/ciris/billing/` | Billing service docker-compose and env |
| `/opt/ciris/proxy/` | Proxy service docker-compose and env |
| `/opt/ciris/postgres/` | PostgreSQL docker-compose and data |
| `/opt/ciris/caddy/` | Caddy docker-compose and Caddyfile |
| `/opt/ciris/dns/` | Constellation DNS config |
| `/var/log/ciris/` | Service log directories |

## Contacts

- **Monitoring**: https://lens.ciris-services-1.ai
- **Repository**: https://github.com/CIRISAI/CIRISBridge
