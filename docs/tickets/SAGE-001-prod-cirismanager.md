# SAGE-001: Stand Up Production CIRISManager for SAGE GDPR Compliance Agent

**Priority:** High
**Type:** Infrastructure / New Service
**Component:** CIRISBridge
**Target:** sage.ciris.ai

---

## Summary

Deploy a production CIRISManager instance to host SAGE as the GDPR compliance agent for the CIRIS ecosystem. SAGE will provide automated DSAR (Data Subject Access Request) processing, data discovery, and cryptographic deletion verification for all CIRIS services.

---

## Background

### What is SAGE?
SAGE is a GDPR compliance management system built on CIRIS Agent that provides:
- **Multi-Source Discovery**: Locates user data across databases/services using privacy schemas
- **Instant DSARs**: Fulfills access, deletion, and portability requests in minutes
- **Cryptographic Proof**: Ed25519 signatures verify deletions with auditable compliance trails

### Why CIRISManager?
CIRISManager provides the orchestration layer for running CIRIS Agent instances with:
- Lifecycle management (start, stop, health monitoring)
- Configuration management
- Service discovery integration
- Credential/secret injection
- Log aggregation

---

## Scope

### In Scope
1. Provision CIRISManager on existing CIRISBridge infrastructure
2. Configure SAGE agent with GDPR compliance persona
3. Integrate with CIRISBilling for usage metering
4. Set up privacy schema connectors for CIRIS ecosystem services
5. Configure Ed25519 key management for deletion proofs
6. DNS entry: sage.ciris.ai

### Out of Scope
- External organization onboarding (Phase 2)
- Self-service privacy schema designer UI (Phase 2)
- Multi-tenant isolation (single-tenant for CIRIS ecosystem initially)

---

## Technical Requirements

### 1. Infrastructure

#### Option A: Colocate on Existing Nodes (Recommended)
Add CIRISManager to existing Vultr/Hetzner nodes:

```yaml
# Additional resources needed per node:
cpu: +1 vCPU dedicated to SAGE
memory: +2GB RAM
storage: +10GB for agent state and audit logs
```

**Pros:** Lower cost, uses existing HA setup
**Cons:** Resource contention with billing/proxy services

#### Option B: Dedicated Node
New Hetzner CX22 instance for SAGE workloads:

```yaml
# Estimated cost:
server: €6/mo (cx22)
volume: €1/mo (10GB for audit logs)
total: ~€7/mo
```

**Pros:** Isolated resources, independent scaling
**Cons:** Additional infrastructure complexity

### 2. New Ansible Role: `cirismanager`

Create `/ansible/roles/cirismanager/` with:

```
cirismanager/
├── tasks/
│   └── main.yml
├── handlers/
│   └── main.yml
├── templates/
│   ├── docker-compose.yml.j2
│   ├── manager-config.yml.j2
│   └── sage-agent-config.yml.j2
├── defaults/
│   └── main.yml
└── vars/
    └── main.yml
```

#### docker-compose.yml.j2 Template

```yaml
version: "3.8"

services:
  cirismanager:
    image: ghcr.io/cirisai/cirismanager:{{ cirismanager_version }}
    container_name: cirismanager
    restart: unless-stopped
    ports:
      - "127.0.0.1:{{ manager_port }}:8000"
    volumes:
      - ./config:/etc/cirismanager:ro
      - ./agents:/var/lib/cirismanager/agents
      - ./audit:/var/log/cirismanager/audit
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CIRISMANAGER_ENV=production
      - CIRISMANAGER_LOG_LEVEL=INFO
      - BILLING_API_URL={{ billing_internal_url }}
      - BILLING_API_KEY={{ billing_api_key }}
    networks:
      - cirisbridge
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  cirisbridge:
    external: true
```

### 3. SAGE Agent Configuration

#### sage-agent-config.yml.j2

```yaml
# SAGE GDPR Compliance Agent Configuration
agent:
  id: sage-gdpr-001
  name: "SAGE GDPR Compliance Agent"
  version: "1.0.0"

persona:
  type: gdpr_compliance
  capabilities:
    - dsar_processing
    - data_discovery
    - deletion_verification
    - portability_export
    - consent_management

# CIRIS Covenant Alignment
covenant:
  version: "1.0b"
  meta_goal: "M-1"  # Adaptive Coherence
  priority_principles:
    - non_maleficence  # Protect user data
    - autonomy         # Respect data subject rights
    - transparency     # Auditable operations
    - justice          # Fair processing

# Data Source Connectors
connectors:
  - name: cirisbilling
    type: postgresql
    privacy_schema: schemas/billing.privacy.yml
    endpoint: "{{ billing_db_url }}"

  - name: cirisproxy
    type: redis
    privacy_schema: schemas/proxy.privacy.yml
    endpoint: "{{ proxy_redis_url }}"

  - name: constellation
    type: redis
    privacy_schema: schemas/dns.privacy.yml
    endpoint: "{{ dns_redis_url }}"

# Cryptographic Configuration
crypto:
  signing_algorithm: Ed25519
  key_storage: vault  # or file for initial setup
  key_path: /etc/cirismanager/keys/sage-signing.key

# Audit Configuration
audit:
  enabled: true
  storage: postgresql
  retention_days: 2555  # 7 years per GDPR
  immutable: true

# Billing Integration
billing:
  enabled: true
  product_type: dsar_processing
  charge_per_request: true
  free_tier:
    requests_per_month: 10
```

### 4. Privacy Schema Examples

#### schemas/billing.privacy.yml

```yaml
# CIRISBilling Privacy Schema
version: "1.0"
service: cirisbilling

personal_data:
  accounts:
    table: accounts
    identifier_field: external_id
    fields:
      - name: external_id
        type: email
        category: identifier
        retention: active_plus_7_years

      - name: oauth_provider
        type: string
        category: technical
        retention: active_plus_7_years

      - name: balance_minor
        type: integer
        category: financial
        retention: active_plus_7_years

      - name: created_at
        type: timestamp
        category: metadata
        retention: active_plus_7_years

  charges:
    table: charges
    identifier_field: account_id
    fields:
      - name: amount_minor
        type: integer
        category: financial
        anonymize_on_delete: true

      - name: description
        type: string
        category: transactional
        retention: 7_years

      - name: metadata
        type: jsonb
        category: technical
        pii_fields:
          - request_id
          - channel_id

dsar_operations:
  access:
    - query: "SELECT * FROM accounts WHERE external_id = :subject_id"
    - query: "SELECT * FROM charges WHERE account_id IN (SELECT id FROM accounts WHERE external_id = :subject_id)"
    - query: "SELECT * FROM credits WHERE account_id IN (SELECT id FROM accounts WHERE external_id = :subject_id)"

  deletion:
    - operation: anonymize
      table: charges
      set: "metadata = '{}', description = '[DELETED]'"
      where: "account_id IN (SELECT id FROM accounts WHERE external_id = :subject_id)"

    - operation: delete
      table: accounts
      where: "external_id = :subject_id"

  portability:
    format: json
    include:
      - accounts
      - charges
      - credits
```

### 5. DNS Configuration

Add to Constellation zones:

```yaml
# In zones.yaml
sage:
  type: A
  value: "{{ vultr_ip }}"  # Or dedicated IP
  geo:
    us: "{{ vultr_ip }}"
    eu: "{{ hetzner_ip }}"
```

### 6. Caddy Configuration

Add to Caddyfile:

```caddyfile
sage.ciris.ai {
    reverse_proxy localhost:{{ manager_port }} {
        health_uri /health
        health_interval 30s
    }

    # DSAR API endpoints
    handle /api/v1/dsar/* {
        reverse_proxy localhost:{{ manager_port }}
    }

    # Admin dashboard
    handle /admin/* {
        reverse_proxy localhost:{{ manager_port }}
    }

    log {
        output file /var/log/caddy/sage.log
        format json
    }
}
```

---

## Implementation Phases

### Phase 1: Infrastructure Setup (Week 1)
- [ ] Create `cirismanager` Ansible role
- [ ] Deploy CIRISManager container
- [ ] Configure networking (internal bridge)
- [ ] Set up health checks
- [ ] DNS entry for sage.ciris.ai

### Phase 2: SAGE Agent Configuration (Week 2)
- [ ] Generate Ed25519 signing keypair
- [ ] Create privacy schemas for CIRISBilling
- [ ] Create privacy schemas for CIRISProxy
- [ ] Create privacy schemas for Constellation DNS
- [ ] Configure SAGE agent persona

### Phase 3: Integration (Week 3)
- [ ] Connect SAGE to CIRISBilling for usage metering
- [ ] Test DSAR access request flow
- [ ] Test DSAR deletion request flow
- [ ] Test deletion verification (cryptographic proof)
- [ ] Set up audit log retention

### Phase 4: Production Hardening (Week 4)
- [ ] Security audit of SAGE endpoints
- [ ] Rate limiting configuration
- [ ] Backup procedures for audit logs
- [ ] Monitoring and alerting
- [ ] Documentation

---

## New Ansible Playbook

Create `/ansible/playbooks/sage.yml`:

```yaml
# Deploy SAGE GDPR Compliance Agent
#
# Usage:
#   ansible-playbook playbooks/sage.yml

---
- name: Deploy SAGE
  hosts: all
  become: true

  roles:
    - common
    - cirismanager

  vars:
    cirismanager_agents:
      - sage

  post_tasks:
    - name: Wait for CIRISManager to start
      ansible.builtin.uri:
        url: "http://localhost:{{ manager_port }}/health"
        status_code: 200
      register: manager_health
      retries: 10
      delay: 5
      until: manager_health.status == 200

    - name: Verify SAGE agent is running
      ansible.builtin.uri:
        url: "http://localhost:{{ manager_port }}/api/v1/agents/sage-gdpr-001/status"
        status_code: 200
      register: sage_status
      retries: 5
      delay: 3

    - name: Display SAGE status
      ansible.builtin.debug:
        msg: "SAGE agent status: {{ sage_status.json }}"
```

---

## Environment Variables

Add to `.env`:

```bash
# CIRISManager
CIRISMANAGER_VERSION=latest
MANAGER_PORT=8090

# SAGE
SAGE_SIGNING_KEY_PATH=/opt/ciris/manager/keys/sage-signing.key
SAGE_AUDIT_DB_URL=postgresql://sage:${SAGE_DB_PASSWORD}@localhost:5432/sage_audit

# Billing Integration for SAGE
SAGE_BILLING_API_KEY=${SAGE_API_KEY}
```

---

## Testing Checklist

### Functional Tests
- [ ] DSAR access request returns all user data
- [ ] DSAR deletion request removes/anonymizes data
- [ ] Deletion proof is cryptographically valid
- [ ] Portability export generates valid JSON
- [ ] Billing charges are recorded for DSAR processing

### Integration Tests
- [ ] SAGE can query CIRISBilling database
- [ ] SAGE can query CIRISProxy Redis
- [ ] SAGE can query Constellation Redis
- [ ] Audit logs are written to PostgreSQL

### Security Tests
- [ ] API endpoints require authentication
- [ ] Signing key is not exposed
- [ ] Audit logs are immutable
- [ ] Rate limiting prevents abuse

---

## Rollback Plan

1. Stop CIRISManager container
2. Remove DNS entry for sage.ciris.ai
3. Remove Caddy configuration
4. Archive audit logs to cold storage

---

## Success Criteria

1. sage.ciris.ai responds to health checks
2. DSAR access request completes in < 30 seconds
3. DSAR deletion with proof completes in < 60 seconds
4. All operations produce audit log entries
5. Billing integration tracks DSAR usage

---

## References

- [SAGE Website](https://sage.ciris.ai)
- [CIRIS Covenant 1.0b](../CIRISAgent/covenant_1.0b.txt)
- [CIRISBilling Privacy Schema](../CIRISBilling/MISSION_ALIGNMENT.md)
- [GDPR Article 15-20](https://gdpr-info.eu/art-15-gdpr/) (Data Subject Rights)

---

**Created:** 2025-12-15
**Author:** Infrastructure Team
**Status:** Draft
