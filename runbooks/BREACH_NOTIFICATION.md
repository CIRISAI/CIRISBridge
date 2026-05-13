# GDPR Article 33 Breach Notification — Operational Playbook

> *Operationalizes https://ciris.ai/safety-policy: "If a confirmed breach of
> personal data affects users in scope of GDPR, we follow Article 33:
> notification to the relevant supervisory authority within 72 hours of
> becoming aware. Affected users are notified without undue delay."*

This playbook is scaled to **the actual data we hold** — not a hypothetical
maximalist footprint. Inventory lives in [`PII_INVENTORY.md`](PII_INVENTORY.md);
this playbook references it and is re-evaluated whenever the inventory
changes materially.

Closes [CIRISBridge#2](https://github.com/CIRISAI/CIRISBridge/issues/2).
Cross-referenced in `SECURITY.md` §Incident Response and `OPERATIONS.md`.

---

## 1. What's in scope

Per the current inventory (see `PII_INVENTORY.md` for live counts):

**In scope of Art. 33** — bridge holds:
- ~141 real user email addresses (`accounts.customer_email`)
- ~93 real display names (`accounts.display_name`)
- ~167 OAuth provider IDs (`accounts.external_id`)
- Small set of admin user identities (`admin_users.email`, `full_name`, `google_id`)
- ~5 months of behavioral metadata tied to those identities (charges, credit
  checks, llm_usage_logs — counts + timestamps, **no content**)
- API-key last-used IPs

**Out of scope** by design:
- ❌ **Prompt content** — never stored anywhere in the fleet
- ❌ **Response content** — never stored (proxy is ZDR)
- ❌ **Payment instruments** — Apple/Google/Stripe own card data
- ❌ **Special-category data** (health, biometric, race, religion, location-precise)
- ❌ **Cross-site tracking / device fingerprints**

**Out of breach scope by consent** — the CIRISLens **opt-in trace repository**
is consent-gated (`accord_api_v2.consent_timestamp`) and intentionally
published at `https://lens.ciris-services-1.ai/api/v1/accord/repository/*`.
Exposure is not a "breach" because the data is by design public. The lawful
basis (Art. 6(1)(a) — consent) and erasure rights (Art. 17) still apply, but
those are separate workstreams from this playbook.

---

## 2. When the 72-hour clock starts

GDPR Art. 33(1) requires notification "not later than 72 hours after having
become aware." **Awareness is the trigger**, not "investigation complete."

### Awareness triggers (any starts the clock)

| Source | Signal | Threshold |
|---|---|---|
| CIRISLens anomaly alert | `category=data_breach` AND `confirmed=true` | Ops on-call ack timestamp |
| CIRISBilling auth-layer anomaly | Mass credential / session-token compromise pattern | First investigation confirming non-user-driven |
| CIRISProxy | Unauthorized access to LLM-call metadata logs | Confirmation access was unauthorized |
| Upstream provider (Vultr, Hetzner, Cloudflare, Stripe, Google, Apple) | Provider-issued breach notification | Moment notification arrives in any official channel |
| Operator discovery | Manual investigation surfacing unauthorized exfil / exposure | Moment confirmed real (not false-positive) |

### Does not start the clock

- Suspicion without confirmation
- Near-miss caught by access controls (no actual data accessed)
- Failed authentication attempts, regardless of volume
- Vulnerability disclosure with no exploitation evidence

### Time-zero is recorded

The ops on-call MUST create `/data/breach-log/<YYYY-MM-DD-incident-NN>/incident.md`
on bridge-us with: `clock_start_utc`, `awareness_source`, `awareness_signal`,
`initial_responder`, `dpo_of_record`. Append-only.

---

## 3. Supervisory authority

CIRIS has **no EU main establishment** → One-Stop-Shop (Art. 56) does not
apply. We notify each Member State's DPA that has affected residents.

Pre-flight the directory **before** an incident (don't lookup mid-72h window):

| User residence | Authority | Contact |
|---|---|---|
| 🇬🇧 UK | **ICO** | https://ico.org.uk/for-organisations/report-a-breach/ |
| 🇫🇷 France | **CNIL** | https://www.cnil.fr/en/notification-personal-data-breach |
| 🇩🇪 Germany | **BfDI** + relevant Land DPA | https://www.bfdi.bund.de/ |
| 🇮🇪 Ireland | **DPC** | https://forms.dataprotection.ie/report-a-breach-of-personal-data |
| 🇳🇱 Netherlands | **AP** | https://autoriteitpersoonsgegevens.nl/ |
| 🇪🇸 Spain | **AEPD** | https://sedeagpd.gob.es/ |
| 🇮🇹 Italy | **Garante** | https://www.garanteprivacy.it/ |
| Other EU/EEA | EDPB members directory | https://edpb.europa.eu/about-edpb/about-edpb/members_en |
| 🇨🇭 Switzerland (FADP) | **FDPIC** | https://www.edoeb.admin.ch/ |
| 🇺🇸 US users | Out of GDPR scope. Public commitment doesn't cover US state laws (CA, NY, MA, etc.) — those layer in separately if/when adopted. | — |

**One DPO-of-record** owns all DPA correspondence per incident. Concurrent
notifications by multiple operators create inconsistent narratives.

### Required content per Art. 33(3)

Even partial — include what's known within the 72h window:

1. Nature of the breach (categories of data subjects + approximate count; categories of personal-data records + approximate count)
2. DPO contact
3. Likely consequences
4. Measures taken / proposed

Art. 33(4) permits follow-up information beyond the 72h window — the window
itself cannot be extended.

---

## 4. Affected-user notification (Art. 34)

Required when the breach is "likely to result in a high risk to the rights
and freedoms" of the user. **Our defined "without undue delay" target:
within 5 business days of DPA notification.**

Channels:

| Channel | When | How |
|---|---|---|
| Email to account email | **Default** for our footprint (single channel; 141 emails total) | Via billing's SMTP path. Template below. |
| In-app banner | When email may be delayed | Set in CIRISBilling banner store |
| Warrant-canary update | When breach is broad enough that targeted email is incomplete | https://ciris.ai/canary, public-facing summary only |

**Dropped from earlier draft**: a "direct phone call for high-risk users"
tier. Disproportionate for a footprint where the maximum likely harm is
phishing-targetable email leak; email contact is the right channel.

Per Art. 34(2) the notification includes: nature, DPO contact, likely
consequences, measures taken, recommended user actions.

---

## 5. Roles + escalation

| Role | Responsibility |
|---|---|
| **DPO-of-record** | Single point of contact for DPA + user notifications this incident |
| **Technical lead** | Investigation, evidence preservation, root cause |
| **Communications** | Drafts user-facing messages |
| **Legal review** (when available) | Reviews correspondence before send — does NOT delay beyond Art. 33(1) / our 5-business-day commitment |

Out-of-hours: primary on-call acknowledges within 30min and defaults to
DPO-of-record if no other operator responds within 1h. Backup contacts in
vault `breach_escalation_contacts`. DPA portals accept emergency
notifications outside business hours.

---

## 6. Templates

### 6.1 DPA notification (Art. 33)

> **Subject**: Personal Data Breach Notification — CIRIS L3C — [INCIDENT-ID]
>
> Pursuant to Article 33 GDPR, CIRIS L3C notifies you of a personal data breach
> affecting users under your supervisory authority.
>
> **1. Nature**: [confidentiality/integrity/availability] incident affecting
> [data categories per `PII_INVENTORY.md`] for approximately [N] data subjects
> residing in [jurisdiction]. **The breach does NOT expose**: prompt content,
> response content, payment instruments, special-category data — those are not
> stored by CIRIS.
>
> **2. Time-zero**: [UTC from incident.md.clock_start_utc]; **Source**: [from incident.md]
>
> **3. DPO contact**: dpo@ciris.ai, +1-[number]
>
> **4. Likely consequences**: [Comms-drafted, DPO-signed]
>
> **5. Measures taken / proposed**: [Technical lead]
>
> Further information per Art. 33(4) will follow as the investigation progresses.
>
> [DPO-of-record name, role, CIRIS L3C, signed UTC timestamp]

### 6.2 User notification (Art. 34)

> **Subject**: Important: CIRIS Personal Data Notice — [INCIDENT-ID]
>
> Dear [user],
>
> On [date], CIRIS L3C became aware of a personal data incident that may have
> affected your account.
>
> **What happened**: [plain language]
>
> **What information was involved**: [from `PII_INVENTORY.md`, only the
> columns actually affected]. **Not involved**: your prompt or response
> content (we don't store it), your payment card details (handled by your
> app store, never stored by us), or anything you've explicitly opted in to
> publish to the federation traces (that data is already public by design).
>
> **What we are doing**: [steps]
>
> **What you can do**: [recommended actions — rotate Google/Apple session
> if external_id was involved, etc.]
>
> If you have questions, contact dpo@ciris.ai or +1-[number]. You may lodge a
> complaint with [authority name per jurisdiction], [URL].
>
> [DPO-of-record name, DPO, CIRIS L3C]

### 6.3 Warrant-canary (only when broad)

> ### Incident [INCIDENT-ID] — [date]
>
> CIRIS L3C is notifying users of a personal data incident affecting
> [count] accounts. We have notified [authority list] under GDPR Art. 33.
> Affected users are being notified individually via account email.
>
> Reference https://ciris.ai/incidents/[id] for the post-mortem once the
> investigation is complete.

---

## 7. Drills

Annual tabletop drill, real-time clock, mock authority notification, mock user
template fill. Identifies playbook gaps before real time pressure.

Next drill: **2026-11-13** (6mo from codification, then annual).

---

## 8. Out of scope (per CIRISBridge#2)

- HIPAA, NYDFS, US state-specific breach laws — not in the public commitment
- Detection layer (CIRISLensCore) — this playbook is post-detection
- Incident-response runbook for technical containment (`runbooks/incident-response.yml`) — separate workstream

---

## 9. Update history

| Date | Change | Notes |
|---|---|---|
| 2026-05-13 | Codified per CIRISBridge#2 | Initial draft scaled to actual inventory; opt-in lens traces excluded per consent + publication design |
