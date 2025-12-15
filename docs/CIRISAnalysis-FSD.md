# CIRISAnalysis - Functional Specification Document

**Version:** 1.0.0
**Status:** Draft
**License:** AGPL-3.0

---

## 1. Overview

### 1.1 Purpose

CIRISAnalysis provides automated log anomaly detection for CIRIS infrastructure. It analyzes logs aggregated by CIRISLens to identify irregular activity, security threats, and operational anomalies.

### 1.2 Mission Alignment

From the CIRIS Covenant (Meta-Goal M-1):
> *Promote sustainable adaptive coherence - the living conditions under which diverse sentient beings may pursue their own flourishing in justice and wonder.*

Agents cannot serve this mission if infrastructure is compromised. CIRISAnalysis provides early warning of threats while maintaining Zero Data Retention principles - we detect anomalies in patterns, not in content.

### 1.3 Design Principles

1. **Pattern-based, not content-based** - Analyze metadata, timing, frequency - never log content
2. **Sidecar architecture** - Runs alongside CIRISLens, not embedded in it
3. **Human-in-the-loop** - Alerts require human review before action
4. **Designed to be deleted** - Will be retired when decentralized monitoring matures

---

## 2. Architecture

### 2.1 Deployment Model

```
┌─────────────────────────────────────────────────────────┐
│                    CIRISLens Stack                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ cirislens-  │  │ cirislens-  │  │   cirislens-    │  │
│  │     api     │  │     db      │  │    grafana      │  │
│  └─────────────┘  └──────┬──────┘  └────────┬────────┘  │
│                          │                   │           │
│  ┌───────────────────────┴───────────────────┘          │
│  │                                                       │
│  │  ┌─────────────────────────────────────────────────┐ │
│  │  │              cirislens-analyzer                 │ │
│  │  │  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │ │
│  │  │  │ Ingester│  │ Detector │  │ Alert Manager │  │ │
│  │  │  └─────────┘  └──────────┘  └───────────────┘  │ │
│  │  └─────────────────────────────────────────────────┘ │
│  │                                                       │
└──┴───────────────────────────────────────────────────────┘
```

### 2.2 Components

| Component | Responsibility |
|-----------|----------------|
| **Ingester** | Polls TimescaleDB for new log entries, extracts features |
| **Detector** | Runs ML models to identify anomalies |
| **Alert Manager** | Deduplicates, prioritizes, and routes alerts |

### 2.3 Data Flow

1. CIRISBilling/CIRISProxy → CIRISLens (existing)
2. CIRISLens TimescaleDB → Analyzer Ingester (poll every 60s)
3. Ingester → Feature extraction (timing, frequency, error rates)
4. Features → Detector (anomaly scoring)
5. Anomalies → Alert Manager → Discord webhook / Grafana annotations

---

## 3. Functional Requirements

### 3.1 Anomaly Detection

#### 3.1.1 Baseline Learning
- **FR-001**: System SHALL establish baseline patterns from 7 days of historical data
- **FR-002**: Baselines SHALL be computed per-service (billing, proxy, dns)
- **FR-003**: Baselines SHALL account for time-of-day patterns

#### 3.1.2 Detection Rules

| Rule ID | Name | Trigger |
|---------|------|---------|
| AD-001 | Error Rate Spike | Error rate > 3σ from baseline |
| AD-002 | Request Volume Anomaly | Request count > 3σ or < -2σ from baseline |
| AD-003 | Latency Degradation | P95 latency > 2x baseline |
| AD-004 | Auth Failure Burst | >10 auth failures in 60s from single source |
| AD-005 | New Error Pattern | Error message not seen in baseline period |
| AD-006 | Geographic Anomaly | Requests from unexpected regions |

#### 3.1.3 ML Models
- **FR-004**: System SHALL support Isolation Forest for multivariate anomaly detection
- **FR-005**: System SHALL support time-series decomposition (ETS) for trend analysis
- **FR-006**: Models SHALL be retrained weekly on latest data

### 3.2 Alerting

#### 3.2.1 Alert Lifecycle
- **FR-007**: Alerts SHALL have states: `new`, `acknowledged`, `resolved`, `false_positive`
- **FR-008**: Duplicate alerts within 5 minutes SHALL be grouped
- **FR-009**: Alert severity SHALL be: `critical`, `warning`, `info`

#### 3.2.2 Alert Routing
- **FR-010**: Critical alerts SHALL notify Discord immediately
- **FR-011**: Warning alerts SHALL batch (max 5 min delay)
- **FR-012**: Info alerts SHALL appear in Grafana only (no push notification)

#### 3.2.3 Feedback Loop
- **FR-013**: Marking alert as `false_positive` SHALL update model weights
- **FR-014**: System SHALL track false positive rate per rule
- **FR-015**: Rules with >30% false positive rate SHALL be flagged for review

### 3.3 Privacy Requirements

- **FR-016**: System SHALL NOT store or analyze log message content
- **FR-017**: System SHALL only process: timestamps, service names, status codes, latencies, source IPs (hashed)
- **FR-018**: IP addresses SHALL be hashed before storage
- **FR-019**: All stored data SHALL have 30-day TTL

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Requirement |
|--------|-------------|
| Ingestion lag | < 2 minutes from log entry to analysis |
| Detection latency | < 30 seconds per batch |
| Memory footprint | < 512MB |
| CPU usage | < 0.5 vCPU average |

### 4.2 Reliability

- **NFR-001**: Analyzer crash SHALL NOT affect CIRISLens operation
- **NFR-002**: Missed analysis windows SHALL be backfilled on restart
- **NFR-003**: System SHALL gracefully degrade if TimescaleDB is unavailable

### 4.3 Observability

- **NFR-004**: Analyzer SHALL expose `/health` endpoint
- **NFR-005**: Analyzer SHALL report metrics to CIRISLens (meta-monitoring)
- **NFR-006**: All anomaly detections SHALL be logged with reasoning

---

## 5. Database Schema

### 5.1 New Tables (in CIRISLens DB)

```sql
-- Detected anomalies
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_id VARCHAR(20) NOT NULL,
    service VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    score FLOAT NOT NULL,
    metadata JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    false_positive BOOLEAN DEFAULT FALSE
);

-- Model baselines
CREATE TABLE baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(50) NOT NULL,
    metric VARCHAR(50) NOT NULL,
    hour_of_day INT,
    day_of_week INT,
    mean FLOAT NOT NULL,
    stddev FLOAT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sample_count INT NOT NULL,
    UNIQUE(service, metric, hour_of_day, day_of_week)
);

-- Alert history
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_id UUID REFERENCES anomalies(id),
    channel VARCHAR(50) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100)
);

-- Feedback for model improvement
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_id UUID REFERENCES anomalies(id),
    feedback_type VARCHAR(20) NOT NULL, -- 'false_positive', 'confirmed', 'adjusted'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT
);
```

---

## 6. API Specification

### 6.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/anomalies` | List recent anomalies |
| GET | `/api/v1/anomalies/:id` | Get anomaly details |
| POST | `/api/v1/anomalies/:id/acknowledge` | Acknowledge alert |
| POST | `/api/v1/anomalies/:id/resolve` | Mark resolved |
| POST | `/api/v1/anomalies/:id/false-positive` | Mark as false positive |
| GET | `/api/v1/baselines` | View current baselines |
| POST | `/api/v1/baselines/recompute` | Trigger baseline recalculation |
| GET | `/api/v1/rules` | List detection rules |
| GET | `/api/v1/stats` | Detection statistics |

### 6.2 Authentication

- Internal only (not exposed via Caddy)
- Service token from CIRISLens for Grafana integration
- Optional: Google OAuth for admin endpoints (shared with Lens)

---

## 7. Configuration

### 7.1 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://cirislens:pass@cirislens-db:5432/cirislens

# Analysis settings
ANALYSIS_INTERVAL_SECONDS=60
BASELINE_WINDOW_DAYS=7
ANOMALY_THRESHOLD_SIGMA=3.0

# Alerting
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_BATCH_SECONDS=300
CRITICAL_ALERT_IMMEDIATE=true

# Privacy
HASH_IP_ADDRESSES=true
DATA_RETENTION_DAYS=30

# Feature flags
ENABLE_ML_MODELS=true
ENABLE_GEOGRAPHIC_ANALYSIS=false
```

---

## 8. Docker Deployment

### 8.1 Image

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8300

CMD ["python", "-m", "analyzer.main"]
```

### 8.2 Compose Integration

```yaml
# Added to CIRISLens docker-compose.yml
cirislens-analyzer:
  image: ghcr.io/cirisai/cirislens-analyzer:latest
  container_name: cirislens-analyzer
  restart: unless-stopped
  depends_on:
    - cirislens-db
  environment:
    DATABASE_URL: postgresql://cirislens:${LENS_DB_PASSWORD}@cirislens-db:5432/cirislens
    DISCORD_WEBHOOK_URL: ${DISCORD_WEBHOOK_URL}
  networks:
    - cirislens
```

---

## 9. Grafana Integration

### 9.1 Dashboard Panels

1. **Anomaly Timeline** - Time series of detected anomalies by severity
2. **Active Alerts** - Table of unresolved anomalies
3. **Detection Stats** - True positive rate, false positive rate by rule
4. **Baseline Health** - Current baselines with confidence intervals

### 9.2 Annotations

Anomalies automatically create Grafana annotations on relevant service dashboards.

---

## 10. Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Basic ingester polling TimescaleDB
- [ ] Rule-based detection (AD-001 through AD-004)
- [ ] Discord alerting
- [ ] Health endpoint

### Phase 2: ML Enhancement
- [ ] Isolation Forest anomaly detection
- [ ] Baseline computation and storage
- [ ] Time-of-day pattern recognition
- [ ] Feedback loop for false positives

### Phase 3: Advanced Features
- [ ] Geographic anomaly detection
- [ ] Cross-service correlation
- [ ] Predictive alerting (trending toward anomaly)
- [ ] Grafana dashboard provisioning

---

## 11. Success Metrics

| Metric | Target |
|--------|--------|
| Mean time to detect (MTTD) | < 5 minutes |
| False positive rate | < 20% |
| Alert fatigue (alerts/day) | < 10 |
| Baseline accuracy | Within 1σ 68% of time |

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Alert fatigue from noisy rules | Feedback loop, auto-disable high FP rules |
| ML model drift | Weekly retraining, baseline monitoring |
| Privacy violation via metadata | Hash IPs, no content analysis, 30-day TTL |
| Single point of failure | Crash isolation, backfill on restart |

---

## 13. Future Considerations

- **Veilid integration**: When CIRISLens moves to decentralized logging, analyzer follows
- **Multi-region correlation**: Detect coordinated attacks across US/EU
- **Agent behavior analysis**: Extend to CIRIS agent telemetry (with consent)

---

*This infrastructure exists to protect systems that serve the mission. When better solutions emerge, it steps aside.*
