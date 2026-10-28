# CIRISBridge

Orchestration for the centralized services CIRIS agents depend on: credit
billing, the LLM proxy, and the US canonical federation node. CIRISBridge
deploys and configures these services; it does not contain them. Each service
lives in its own repository and ships as a container image or wheel.

This is transitional infrastructure. Each component is designed to step aside
as decentralized alternatives mature.

## Services

| Service | Repository | Runs on | Purpose |
|---------|------------|---------|---------|
| CIRISBilling | [CIRISBilling](https://github.com/CIRISAI/CIRISBilling) | US, EU | Credits, payments, user and API-key auth |
| CIRISProxy | [CIRISProxy](https://github.com/CIRISAI/CIRISProxy) | US, EU | LLM routing to zero-data-retention providers (LiteLLM) |
| Billing database | pgEdge Spock | US, EU | PostgreSQL 15, bidirectional multi-master replication |
| CIRISServer | [CIRISServer](https://github.com/CIRISAI/CIRISServer) | US | Canonical federation node `ciris-canonical-1` (Reticulum transport, read API, lens) |
| CIRISStatus | [CIRISStatus](https://github.com/CIRISAI/CIRISStatus) | US | Public status and scoring feed |
| Caddy | — | US, EU | TLS termination and routing |

Vault runs on both nodes as well; it belongs to CIRISCore and is not deployed
from this repository.

## Architecture

```
                      Clients and agents
                             │
                  Cloudflare DNS (GeoDNS)
                 ┌───────────┴───────────┐
                 ▼                       ▼
        ┌─────────────────┐     ┌─────────────────┐
        │ US · Vultr      │     │ EU · Hetzner    │
        │ Chicago         │     │ Nuremberg       │
        │ 108.61.242.236  │     │ 46.224.81.217   │
        ├─────────────────┤     ├─────────────────┤
        │ Caddy           │     │ Caddy           │
        │ CIRISBilling    │     │ CIRISBilling    │
        │ CIRISProxy      │     │ CIRISProxy      │
        │ Spock (5433) ◄──┼─────┼─► Spock (5433)  │
        │ CIRISServer     │     │                 │
        │ CIRISStatus     │     │                 │
        └─────────────────┘     └─────────────────┘
```

Billing and the proxy run active/active: either node serves any client, and
the billing database replicates both ways.

## Endpoints

| Hostname | Node | Serves |
|----------|------|--------|
| `billing1.ciris-services-1.ai` | US | Billing API |
| `billing1.ciris-services-2.ai` | EU | Billing API |
| `proxy1.ciris-services-1.ai`, `llm01.ciris-services-1.ai` | US | LLM proxy |
| `proxy1.ciris-services-2.ai`, `llm01.ciris-services-eu-1.com` | EU | LLM proxy |
| `agents.ciris-services-1.ai`, `billing.ciris.ai` | US | Billing API (aliases) |
| `lens.ciris-services-1.ai` | US | Canonical read API (`/v1/identity`, `/v1/federation/*`, `/lens/api/v1/*`) and status (`/status/*`, `/api/v1/scoring`) |

The proxy hostnames expose only the client API: `/v1/chat/completions`,
`/v1/models`, `/v1/status`, `/v1/status/simple` and `/v1/web/search`. Every
other path, including LiteLLM's admin API and UI, returns 404.

## Repository layout

```
CIRISBridge/
├── terraform/            Node provisioning (Vultr, Hetzner, test VPC)
├── ansible/
│   ├── inventory/        Hosts and secrets (production.yml is vault-encrypted, not committed)
│   ├── playbooks/        site.yml (production), spock-billing.yml, test stack
│   ├── roles/            One role per service
│   └── runbooks/         Operational and incident runbooks
├── runbooks/             Breach-notification playbook and PII inventory
├── scripts/              Status checks and surface scanner
└── tools/                SonarCloud CLI
```

## Deploying

From `ansible/`:

```bash
# Everything
ansible-playbook -i inventory/production.yml playbooks/site.yml

# One service, all nodes
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing

# One service, one node
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags billing --limit eu
```

Tags: `common`, `caddy`, `billing`, `proxy`, `ciris-server`, `ciris-status`,
`scheduler`. Node limits: `us`, `eu`. See [OPERATIONS.md](OPERATIONS.md) for day-to-day operation and
[SECURITY.md](SECURITY.md) for the security model.

## Health

```bash
./scripts/daily-status.sh     # probes, TLS, disk, containers, replication, errors; exit 0/1/2
./scripts/weekly-status.sh    # surface diff vs last week, cert expiry, disk trend
```

## Test environment

A disposable three-server stack in an isolated Vultr VPC exercises the full
path, agent → proxy → billing → LLM provider. It costs about $42/month while
running and nothing when destroyed. See
[ansible/runbooks/README.md](ansible/runbooks/README.md).

## Retirement

CIRISBridge is temporary. Peer discovery and private routing move to the
decentralized transport as it matures; billing may persist longest. Changes
here should keep the infrastructure simple, inexpensive and easy to remove.

## License

GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
