# PII Inventory — CIRISBridge production fleet

> **Living document.** Re-evaluated whenever bridge ships a schema change.
> Drives [`BREACH_NOTIFICATION.md`](BREACH_NOTIFICATION.md), the daily SRE
> canary, and any data-minimization (GDPR Art. 5(1)(c)) decision.
>
> Auto-refresh: `scripts/daily-status.sh` includes a PII canary that asserts
> the column set + count bounds match this document. Drift triggers a flag.

Last verified: **2026-05-13** by manual SQL audit against ciris-billing-spock
on bridge-us. Re-verify whenever any of the listed columns/tables changes.

---

## 1. PII inventory by table

### 1.1 `accounts` — primary user identity store

| Column | Type | Purpose | Population (2026-05-13) | PII class |
|---|---|---|---|---|
| `id` | uuid | Internal PK | 167 | Pseudonymous — only useful if joined |
| `oauth_provider` | varchar | `oauth:google` / `oauth:apple` | 167 | Indirect identifier (joined with `external_id`) |
| `external_id` | varchar | OAuth provider's stable user ID (Google `sub`, Apple `sub`) | 167 | **DIRECT IDENTIFIER** (Art. 4(1)) — links to identifiable user via OAuth provider |
| `customer_email` | varchar | OAuth-provided email | 141 | **DIRECT IDENTIFIER** — phishing target if exposed |
| `display_name` | varchar | OAuth-provided display name | 93 | **DIRECT IDENTIFIER** — captured from OAuth at signup |
| `agent_id` | varchar | Which agent this account is tied to | varies | Indirect — agent_id is not user identity |
| `wa_id`, `tenant_id` | varchar | Multi-tenant routing | sparse | Not PII alone |
| `balance_minor`, `paid_credits`, `free_uses_remaining`, etc. | numeric | Credit / usage state | 167 | Behavioral — PII by association via account_id |
| `marketing_opt_in`, `marketing_opt_in_at`, `_source` | bool/ts/varchar | Consent capture | 167 | Consent records (Art. 7) — must persist |
| `user_role`, `plan_name`, `status`, `currency` | varchar | Account state | 167 | Not PII alone |
| `created_at`, `updated_at` | timestamptz | | 167 | |

**Account totals**: 167 total. 138 Google OAuth, 29 Apple OAuth, 0 test. Oldest row: 2025-12-14.

### 1.2 `admin_users` — operator identities (~handful)

| Column | Purpose | PII class |
|---|---|---|
| `email` | Operator OAuth email | **DIRECT IDENTIFIER** |
| `full_name` | Operator display name | **DIRECT IDENTIFIER** — used in admin dashboard greeting |
| `google_id` | OAuth `sub` | DIRECT IDENTIFIER |
| `picture_url` | OAuth profile picture URL | Indirect (URL not data) |
| `role`, `is_active`, `created_at`, `last_login_at` | Operator state | Not PII alone |

### 1.3 Behavioral / transactional (PII by association via `account_id`)

| Table | Rows (2026-05-13) | What | Content | Retention |
|---|---|---|---|---|
| `charges` | 781 | Per-charge metadata. `description` is opaque hash (`LiteLLM interaction: <hex>`) | No prompts/responses | 5 months |
| `credit_checks` | 4,145 | Access-pattern log: oauth_provider + external_id + has_credit + denial_reason | No content | 5 months |
| `llm_usage_logs` | 12,835 | Models used + token counts + cost + duration_ms | No content | 5 months |
| `credits` | varies | Credit-grant ledger | No content | 5 months |
| `product_inventory` | per-account | Per-product credit state | No content | 5 months |
| `product_usage_logs` | varies | Per-product usage events | No content | 5 months |
| `apple_storekit_purchases` | varies | Purchase receipts (transaction_id, product_id, credits_added) | **No card data** — Apple owns it | indefinite |
| `google_play_purchases` | varies | Same shape | **No card data** — Google owns it | indefinite |
| `stripe_payment_intents` | varies | Stripe payment-intent metadata | **No card data** — Stripe owns it | indefinite |

### 1.4 Operational logs

| Table | Rows | Content | Notes |
|---|---|---|---|
| `admin_audit_logs` | 0 (today) | Admin action log incl. `ip_address` (inet) + `user_agent` | IP/UA are GDPR-PII case-by-case (Art. 4(1) + Breyer ECLI:EU:C:2016:779). Empty today; populated by admin actions. |
| `api_keys.last_used_ip` | per-key | Last IP that used each API key | Indirect; case-by-case PII |
| `api_keys.key_hash` | per-key | Hash of the API key | Not PII (it's a secret hash, not user identity) |
| `revoked_tokens` | per-token | Revoked admin session tokens | Not PII alone |

### 1.5 CIRISLens federation directory (US only)

| Table | What | PII scope |
|---|---|---|
| `accord_traces`, `trace_events` | **Opt-in published agent traces** | **OUT OF BREACH SCOPE** — consent-gated (`consent_timestamp`), intentionally published at `/api/v1/accord/repository/*` |
| `federation_keys` | Agent + steward signing keys | Cryptographic identity, not PII |
| `agent_logs`, `service_logs` | Internal ops telemetry | No user content; operator data |
| `manager_telemetry` | CIRISManager fleet telemetry | Agent-side, not user-side |

The opt-in trace repository is the only place that could be considered PII +
controller-held, and it's **deliberately public** by the user's consent
(`accord_api_v2.consent_timestamp`). Exposure ≠ breach.

---

## 2. What's NOT stored (load-bearing for breach risk profile)

- ❌ **Prompt content** — never persisted in bridge billing/proxy/lens
- ❌ **Response content** — proxy is ZDR (zero data retention); LLM providers similarly contractually-bound
- ❌ **Chat history / message bodies**
- ❌ **Payment card numbers, CVV, expiry** — Apple/Google/Stripe own card data
- ❌ **Bank account / IBAN** — same
- ❌ **Special-category data per Art. 9** (health, biometric, race, religion, location-precise, sexual orientation)
- ❌ **Device fingerprints / cross-site tracking**
- ❌ **Phone numbers, postal addresses, real-name verifications**
- ❌ **Geolocation precise enough to identify residence**

This list is the **defense** in any DPA notification — the actual harm
surface is bounded.

---

## 3. Data-minimization considerations (Art. 5(1)(c))

The current inventory is the canonical state. The following are **future
opportunities** for review, not in-flight changes — they only land in this
document's "current state" sections once a corresponding billing change has
shipped and been validated.

| Column / table | Current state | Future opportunity (not yet actioned) |
|---|---|---|
| `accounts.display_name` | Captured at OAuth signup, 93 rows populated | No production user-facing consumer was identified in a 2026-05-13 grep. Worth a billing-side audit to confirm + potentially drop the column. If dropped, removes 93 real names from blast radius. |
| `admin_users.full_name` | Used in admin dashboard greeting (`dashboard.js:43`, `admin_auth_routes.py:255`) | Could be replaced with email-only display in a future admin UI iteration. Small load-bearing UI change. |
| `credit_checks` (4,145 rows) | 5-month retention by default | Consider TTL-based purge for rows older than 90 days. Reduces behavioral-history blast radius. |

Anything moved out of this section into §1 means the change has shipped.
`accounts.marketing_opt_in_source` and `admin_audit_logs` stay as-is —
the former is required for Art. 7 consent records, the latter is required
for Art. 30 records-of-processing.

---

## 4. Re-verification ritual

The daily SRE script (`scripts/daily-status.sh`) includes a **PII canary**:

1. Query: list every column where `column_name LIKE '%email%' OR LIKE '%name%' OR LIKE '%phone%' OR LIKE '%address%' OR LIKE '%dob%'` across the billing schema
2. Compare against the column list in §1 above
3. Flag any new column appearing that isn't in §1 → drift, manual review required

This catches schema additions that introduce new PII columns without
explicit inventory update.

---

## 5. Update history

| Date | Change |
|---|---|
| 2026-05-13 | Initial inventory; flagged `accounts.display_name` for drop; opt-in lens repository scoped out by consent design |
