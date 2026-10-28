# CIRISBridge Operations Guide

Day-to-day operation of the production nodes. Commands run from `ansible/`
unless noted, and need the vault password for `inventory/production.yml`.

## Nodes

| Node | Inventory group | Provider | Location | IP |
|------|-----------------|----------|----------|----|
| US | `us` (`vultr`) | Vultr | Chicago | 108.61.242.236 |
| EU | `eu` (`hetzner`) | Hetzner | Nuremberg | 46.224.81.217 |

## Containers

| Container | Nodes | Port | Purpose |
|-----------|-------|------|---------|
| `ciris-caddy` | US, EU | 80, 443 | TLS termination and routing |
| `ciris-billing` | US, EU | 8000 (host network, behind Caddy) | Billing API |
| `ciris-proxy` | US, EU | 4000 (localhost, behind Caddy) | LLM proxy (LiteLLM) |
| `ciris-billing-spock` | US, EU | 5433 (peer node only) | Billing database, Spock multi-master |
| `ciris-server` | US | 4242 tcp/udp (Reticulum), 4243 (read API) | Canonical federation node |
| `ciris-status` | US | 4253 | Status and scoring feed |
| `ciris-vault` | US, EU | 8210–8211 (peers only) | Owned by CIRISCore; not managed here |

## Checking health

```bash
# From the repository root
./scripts/daily-status.sh         # GREEN / YELLOW / RED, exit 0 / 1 / 2
./scripts/weekly-status.sh        # weekly report: surface diff, issues, certs, disk
./scripts/surface-scan.py --internal --out before.json   # snapshot for a pre/post diff
./scripts/surface-scan.py --diff before.json after.json
```

The daily check covers external probes, TLS expiry, disk, container counts,
Spock replication, conntrack headroom, a PII-schema canary, and container
errors from the last 30 minutes. Errors are grouped by signature; known noise
(rejected unauthenticated proxy requests, expected un-routable client dials)
is reported but does not change the status.

Quick ad-hoc checks:

```bash
ansible all -i inventory/production.yml -m shell -a 'docker ps'
ansible all -i inventory/production.yml -m shell -a 'docker logs ciris-billing --tail 50'
curl -s https://billing1.ciris-services-1.ai/health
curl -s https://proxy1.ciris-services-1.ai/v1/status/simple
```

`/health` alone can pass while a dependency is down; use each service's own
`/v1/status` when a maintenance step depends on it.

## Deploying

```bash
ansible-playbook -i inventory/production.yml playbooks/site.yml                       # everything
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags proxy          # one service
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit eu
```

Deploy through Ansible rather than editing files on a node, so the nodes stay
identical to the repository. `docker compose restart` does not reload
environment variables; the roles recreate containers when configuration
changes.

### Billing

Each billing deploy saves the running image digest for rollback, pulls the new
image, waits for `/health`, runs migrations on the US node only, and
smoke-tests `/health`. To roll back:

```bash
ansible-playbook -i inventory/production.yml runbooks/billing-rollback.yml
ansible-playbook -i inventory/production.yml runbooks/billing-rollback.yml --limit us
```

### Canonical (ciris-server)

The version is pinned in `roles/ciris-server/defaults/main.yml`. Before a new
version goes to the canonical:

1. Run it in a capped acceptance harness: a copy of the live home, no network,
   the production 2 GiB memory limit, at least 12 minutes. It must stay
   announced and unhalted, keep the same transit keys, and log no errors.
2. Take a pinned pre-roll copy of `/data/cirisserver/data` (SQLite online
   backup) and `identity/`, outside the role's snapshot rotation, and tag the
   running image for rollback.
3. Deploy with `--tags ciris-server`. The role refuses a version that is not on
   PyPI, snapshots the home, rebuilds, and fails unless `/health` reports
   `canonical_announce = announced`.

The canonical's identity must persist byte-identically across upgrades; never
deploy with `ciris_server_fresh=true` against production.

## Billing database (Spock)

```bash
ansible-playbook -i inventory/production.yml playbooks/spock-billing.yml --tags status
ansible-playbook -i inventory/production.yml runbooks/backup-verify.yml
ansible-playbook -i inventory/production.yml runbooks/billing-ops.yml --tags status --limit us
```

Both subscriptions should report `replicating`. Schema migrations replicate
through `spock.replicate_ddl()`, and every billing deploy adds any public table
missing from the `default` replication set.

| Table | Conflict resolution |
|-------|---------------------|
| users, credits, api_keys | last update wins |
| charges, transactions | first update wins |

Sequences are partitioned per node, so inserts on either node never collide.

## Scheduled jobs

Systemd timers on each node (`systemctl list-timers | grep ciris`):

| Timer | Nodes | Schedule | Purpose |
|-------|-------|----------|---------|
| `ciris-daily-checks` | US, EU | 06:00 UTC | Certificates, replication, disk |
| `ciris-spock-backup` | US, EU | 03:00 UTC | Billing database backup |
| `ciris-weekly-security` | US, EU | Sun 04:00 UTC | Security posture scan |
| `ciris-weekly-cleanup` | US, EU | Sat 03:00 UTC | Docker and log cleanup |

On the US node, `ciris-oom-watchdog` and `ciris-readapi-watchdog` run as
services: they record OOM kills and restart a hung canonical read API.

Every job writes its results to the system journal:

```bash
journalctl -t ciris-scheduler --since today          # timer results
journalctl -t ciris-oom-watchdog -t ciris-readapi-watchdog -p crit
```

## Disk

```bash
ansible-playbook -i inventory/production.yml runbooks/disk-cleanup.yml --tags status
ansible-playbook -i inventory/production.yml runbooks/disk-cleanup.yml --tags docker-clean
```

Container logs are capped (json-file, 3 × 50 MB). Canonical upgrade snapshots
are pruned to the two most recent; pinned pre-roll copies are kept until
removed by hand.

## Incidents

| Situation | Runbook |
|-----------|---------|
| General service issue | `incident-response.yml` (`--tags diagnose`, `fix`, `close`) |
| Security incident | `intrusion-response.yml` |
| Provider outage | `provider-outage.yml` (`--tags detect`, `failover`, `failback`) |
| Personal-data breach | [runbooks/BREACH_NOTIFICATION.md](runbooks/BREACH_NOTIFICATION.md) |

### Rebooting a node

Both nodes also host CIRISCore's Vault, which seals when its container
restarts. Coordinate any reboot or Docker daemon restart with CIRISCore so it
can unseal Vault afterwards. Restart the EU node first, then the US node.

### Troubleshooting

- **A service won't start.** `docker logs <container> --tail 100`, then check
  its generated `.env` under `/opt/ciris/<service>/`.
- **Billing can't reach the database.** Check `ciris-billing-spock` is running
  and `spock.sub_show_status()` reports `replicating`.
- **TLS errors.** Caddy renews automatically. Check `docker logs ciris-caddy`,
  that DNS points at the node, and that ports 80 and 443 are open.
- **Containers can't resolve names after a reboot.** Containers inherit the
  host resolver at start; `/etc/docker/daemon.json` pins explicit DNS servers
  on every node.

## File locations

| Path | Contents |
|------|----------|
| `/opt/ciris/caddy/` | Caddyfile, compose file, certificates |
| `/opt/ciris/billing/` | Billing compose file and environment |
| `/opt/ciris/proxy/` | Proxy compose file and environment |
| `/opt/ciris/pgedge-billing/` | Spock database |
| `/opt/ciris/server/` | ciris-server build context and compose file (US) |
| `/data/cirisserver/` | Canonical home: `data/`, `identity/`, `logs/`, snapshots (US) |
| `/opt/ciris/status/` | CIRISStatus (US) |
| `/opt/ciris/scheduler/` | Timer scripts |
| `/var/log/caddy/` | Caddy access logs (JSON) |

## Repository

https://github.com/CIRISAI/CIRISBridge
