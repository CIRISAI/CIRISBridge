#!/usr/bin/env bash
# scripts/daily-status.sh — the "is everything OK?" check.
#
# 30-second sanity sweep with green/yellow/red signals per axis.
# Designed to run from a systemd timer + post to lens (unattended), OR
# from a terminal (human-readable color output).
#
# Exit code: 0 if all green, 1 if any yellow, 2 if any red.
# Stdout: human-readable summary.
# Stderr: snapshot file path.
#
# For "what changed vs last week" use scripts/weekly-status.sh.
# For "is the deploy clean" use scripts/surface-scan.py --diff.

set -uo pipefail
cd "$(dirname "$0")/.."

# Color codes (auto-disabled if not a TTY)
if [[ -t 1 ]]; then
  G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; N=$'\033[0m'
else
  G=''; Y=''; R=''; B=''; N=''
fi
# Worst result tracker for exit code
WORST=0   # 0=green, 1=yellow, 2=red
pass() { printf "  ${G}✓${N} %s\n" "$1"; }
warn() { printf "  ${Y}⚠${N} %s\n" "$1"; [ $WORST -lt 1 ] && WORST=1; }
fail() { printf "  ${R}✗${N} %s\n" "$1"; WORST=2; }

NOW=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "${B}=== bridge daily status — ${NOW} ===${N}"
echo

# ─────────────────────────────────────────────────────────────
# 1. Surface scan (probes + TLS + internal)
# ─────────────────────────────────────────────────────────────
SNAPSHOT=/tmp/bridge-daily-$(date -u +%Y%m%d-%H%M).json
python3 scripts/surface-scan.py --internal --out "$SNAPSHOT" --quiet 2>/dev/null

python3 - "$SNAPSHOT" <<'PY'
import json, sys
G, Y, R, N = '\033[32m', '\033[33m', '\033[31m', '\033[0m'
import os
if not sys.stdout.isatty(): G=Y=R=N=''

with open(sys.argv[1]) as f:
    s = json.load(f)

probes = s.get("probes", [])
passed = sum(1 for p in probes if p.get("passed"))
total = len(probes)
if passed == total:
    print(f"  {G}✓{N} probes: {passed}/{total} passing")
else:
    failed = [p["site_id"] for p in probes if not p.get("passed")]
    print(f"  {R}✗{N} probes: {passed}/{total} passing — failing: {failed}")

tls = s.get("tls", {})
min_days = min((t.get("days_remaining", 0) for t in tls.values()), default=999)
near = [(d, t["days_remaining"]) for d, t in tls.items() if 0 < t.get("days_remaining", 999) < 30]
if not near and min_days > 30:
    print(f"  {G}✓{N} tls: {len(tls)}/{len(tls)} valid, min={min_days}d remaining")
elif near:
    print(f"  {Y}⚠{N} tls: {len(near)} cert(s) <30d: {near}")
else:
    print(f"  {R}✗{N} tls: cert expiry imminent or probe failed")

for h in s.get("internal", []):
    name = h["name"].upper()
    disk_pct = int(h.get("disk", {}).get("pct", "0%").rstrip("%") or 0)
    containers = h.get("container_count", 0)
    expected = 8 if h["name"] == "us" else 5
    spock = h.get("spock", "")
    spock_ok = "replicating" in str(spock).lower()

    if disk_pct < 70:
        print(f"  {G}✓{N} {name} disk:       {disk_pct}%")
    elif disk_pct < 85:
        print(f"  {Y}⚠{N} {name} disk:       {disk_pct}% (run runbooks/disk-cleanup.yml --tags docker-clean)")
    else:
        print(f"  {R}✗{N} {name} disk:       {disk_pct}% (critical — clean immediately)")

    if containers == expected:
        print(f"  {G}✓{N} {name} containers: {containers}/{expected}")
    else:
        print(f"  {R}✗{N} {name} containers: {containers}/{expected} (expected {expected})")

    if spock_ok:
        print(f"  {G}✓{N} {name} spock:      replicating")
    elif spock:
        print(f"  {Y}⚠{N} {name} spock:      {spock}")
PY
PY_EXIT=$?
[ $PY_EXIT -ne 0 ] && WORST=2

# ─────────────────────────────────────────────────────────────
# 2. Lens /health all-ready (US only)
# ─────────────────────────────────────────────────────────────
SSH_US="ssh -i $HOME/Desktop/ciris_transfer/.ciris_bridge_keys/cirisbridge_ed25519 -o StrictHostKeyChecking=no -o LogLevel=ERROR -o ConnectTimeout=5 root@108.61.242.236"

LENS_HEALTH=$($SSH_US 'curl -sS --max-time 5 http://localhost:8200/health 2>&1' 2>/dev/null || echo '{}')
ALL_READY=$(echo "$LENS_HEALTH" | python3 -c "import json,sys
try:
    d=json.load(sys.stdin); p=d.get('persist_engine',{})
    ok = all([p.get('scrubber_ready'),p.get('steward_ready'),p.get('steward_pqc_ready')]) and not p.get('init_error')
    print('1' if ok else '0')
except: print('0')" 2>/dev/null)
if [ "$ALL_READY" = "1" ]; then
  pass "lens /health: scrubber + steward + steward_pqc all ready"
else
  fail "lens /health: NOT all-ready"
fi

# ─────────────────────────────────────────────────────────────
# 3. Heartbeat freshness — both regions must have one in last 30 min
# ─────────────────────────────────────────────────────────────
HEARTBEATS=$($SSH_US "docker exec cirislens-db psql -U cirislens -d cirislens -tAc \"
SELECT server_id || ':' || EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))::int
FROM cirislens.service_logs
WHERE service_name='ciris-scheduler' AND server_id IN ('us','eu')
  AND timestamp > NOW() - INTERVAL '60 minutes'
GROUP BY server_id ORDER BY 1;\"" 2>/dev/null)

for region in us eu; do
  AGE_S=$(echo "$HEARTBEATS" | grep "^$region:" | cut -d: -f2)
  AGE_MIN=$(( ${AGE_S:-9999} / 60 ))
  if [ "$AGE_MIN" -lt 30 ]; then
    pass "$region heartbeat: ${AGE_MIN}min ago"
  elif [ "$AGE_MIN" -lt 60 ]; then
    warn "$region heartbeat: ${AGE_MIN}min ago (expected ≤20)"
  else
    fail "$region heartbeat: ${AGE_MIN}min ago (alert threshold breached)"
  fi
done

# ─────────────────────────────────────────────────────────────
# 4. Error rate (last 30min, container logs)
# ─────────────────────────────────────────────────────────────
SSH_EU="ssh -i $HOME/Desktop/ciris_transfer/.ciris_bridge_keys/cirisbridge_ed25519 -o StrictHostKeyChecking=no -o LogLevel=ERROR -o ConnectTimeout=5 root@46.224.81.217"

US_ERRS=$($SSH_US 'for c in ciris-billing ciris-proxy ciris-caddy cirislens-api ciris-billing-spock; do
  docker logs --since 30m $c 2>&1 | grep -ciE "error|exception|panic|fatal|aborted" | head -1
done | awk "{s+=\$1} END{print s+0}"' 2>/dev/null)
EU_ERRS=$($SSH_EU 'for c in ciris-billing ciris-proxy ciris-caddy ciris-billing-spock; do
  docker logs --since 30m $c 2>&1 | grep -ciE "error|exception|panic|fatal|aborted" | head -1
done | awk "{s+=\$1} END{print s+0}"' 2>/dev/null)

if [ "${US_ERRS:-0}" -lt 5 ] && [ "${EU_ERRS:-0}" -lt 5 ]; then
  pass "errors (30min): us=${US_ERRS:-?}  eu=${EU_ERRS:-?}"
elif [ "${US_ERRS:-0}" -lt 100 ] && [ "${EU_ERRS:-0}" -lt 100 ]; then
  warn "errors (30min): us=${US_ERRS:-?}  eu=${EU_ERRS:-?}  (drill: docker logs --since 30m <container> | grep -i error)"
else
  fail "errors (30min): us=${US_ERRS:-?}  eu=${EU_ERRS:-?}  (urgent)"
fi

# ─────────────────────────────────────────────────────────────
# 5. PII inventory canary — does the schema match PII_INVENTORY.md §1?
#    Catches schema additions that introduce new PII columns without
#    documentation update.
# ─────────────────────────────────────────────────────────────
PW=$(cd ansible && ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass ansible-vault view inventory/production.yml 2>/dev/null | grep -E "^\s*billing_db_password:" | head -1 | sed 's/.*: *"//; s/"$//')
if [ -n "$PW" ]; then
  PII_HITS=$($SSH_US "docker exec -e PGPASSWORD='$PW' ciris-billing-spock /opt/pgedge/pg15/bin/psql -p 5433 -U billing -d ciris_billing -tAc \"
    SELECT table_name || '.' || column_name
    FROM information_schema.columns
    WHERE table_schema='public'
      AND (column_name ILIKE '%email%'
        OR column_name ILIKE '%name%'
        OR column_name ILIKE '%phone%'
        OR column_name ILIKE '%address%'
        OR column_name ILIKE '%dob%'
        OR column_name ILIKE '%birth%'
        OR column_name ILIKE '%ssn%')
    ORDER BY 1;\"" 2>/dev/null)

  # Expected set per runbooks/PII_INVENTORY.md §1 as of 2026-05-13.
  # Update both files together when the schema changes.
  EXPECTED_PII="accounts.customer_email
accounts.display_name
accounts.plan_name
admin_audit_logs.ip_address
admin_users.email
admin_users.full_name
api_keys.name
credit_checks.plan_name
google_play_purchases.package_name
product_inventory.product_type
product_usage_logs.product_type"

  UNEXPECTED=$(echo "$PII_HITS" | grep -v '^$' | sort | comm -23 - <(echo "$EXPECTED_PII" | sort))
  if [ -z "$UNEXPECTED" ]; then
    pass "PII inventory: schema matches runbooks/PII_INVENTORY.md"
  else
    warn "PII inventory: new column(s) need documentation review: $(echo $UNEXPECTED | tr '\n' ' ')"
  fi
else
  warn "PII inventory: skipped (could not load billing_db_password from vault)"
fi

echo
echo "${B}snapshot: $SNAPSHOT${N}" >&2

# Final summary line for cron/log aggregator
case $WORST in
  0) echo "${G}${B}OVERALL: GREEN${N}";;
  1) echo "${Y}${B}OVERALL: YELLOW${N} (something needs attention but not urgent)";;
  2) echo "${R}${B}OVERALL: RED${N} (urgent investigation required)";;
esac

exit $WORST
