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
timeout 120 python3 scripts/surface-scan.py --internal --out "$SNAPSHOT" --quiet 2>/dev/null || true

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
    # US count: 7 as of 2026-08-19 (ciris-server, ciris-status, ciris-proxy,
    # ciris-caddy, ciris-billing, ciris-billing-spock, ciris-vault).
    expected = 7 if h["name"] == "us" else 5
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
# 2. CIRISServer (Node A) liveness — container running check
# ─────────────────────────────────────────────────────────────
# /v1/identity HTTP check RETIRED 2026-08-19: trace shipping moved to CEG/RNS
# native; the read API (port 4243) is deprioritized when the event channel
# floods under load. Container liveness is covered by the containers count above.
SSH_US="ssh -i $HOME/Desktop/ciris_transfer/.ciris_bridge_keys/cirisbridge_ed25519 -o StrictHostKeyChecking=no -o LogLevel=ERROR -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 root@108.61.242.236"

SERVER_UP=$($SSH_US 'docker inspect -f "{{.State.Running}}" ciris-server 2>/dev/null' 2>/dev/null)
if [ "$SERVER_UP" = "true" ]; then
  pass "ciris-server: container running"
else
  fail "ciris-server: container not running (was: $SERVER_UP)"
fi

# ─────────────────────────────────────────────────────────────
# 3. Conntrack table (nf_conntrack_max is set in the common role)
#     Alert at >80% to give time to react before exhaustion.
# ─────────────────────────────────────────────────────────────
CT_COUNT=$($SSH_US 'cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null' 2>/dev/null)
CT_MAX=$($SSH_US 'cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null' 2>/dev/null)
if [ -n "$CT_COUNT" ] && [ -n "$CT_MAX" ] && [ "$CT_MAX" -gt 0 ]; then
  CT_PCT=$(( CT_COUNT * 100 / CT_MAX ))
  if [ "$CT_PCT" -lt 80 ]; then
    pass "conntrack (us): ${CT_COUNT}/${CT_MAX} (${CT_PCT}%)"
  elif [ "$CT_PCT" -lt 95 ]; then
    warn "conntrack (us): ${CT_COUNT}/${CT_MAX} (${CT_PCT}%) — approaching limit"
  else
    fail "conntrack (us): ${CT_COUNT}/${CT_MAX} (${CT_PCT}%) — near exhaustion (risk of network freeze)"
  fi
else
  warn "conntrack (us): could not read /proc/sys/net/netfilter/nf_conntrack_count"
fi

SSH_EU="ssh -i $HOME/Desktop/ciris_transfer/.ciris_bridge_keys/cirisbridge_ed25519 -o StrictHostKeyChecking=no -o LogLevel=ERROR -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 root@46.224.81.217"
CT_COUNT_EU=$($SSH_EU 'cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null' 2>/dev/null)
CT_MAX_EU=$($SSH_EU 'cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null' 2>/dev/null)
if [ -n "$CT_COUNT_EU" ] && [ -n "$CT_MAX_EU" ] && [ "$CT_MAX_EU" -gt 0 ]; then
  CT_PCT_EU=$(( CT_COUNT_EU * 100 / CT_MAX_EU ))
  if [ "$CT_PCT_EU" -lt 80 ]; then
    pass "conntrack (eu): ${CT_COUNT_EU}/${CT_MAX_EU} (${CT_PCT_EU}%)"
  elif [ "$CT_PCT_EU" -lt 95 ]; then
    warn "conntrack (eu): ${CT_COUNT_EU}/${CT_MAX_EU} (${CT_PCT_EU}%) — approaching limit"
  else
    fail "conntrack (eu): ${CT_COUNT_EU}/${CT_MAX_EU} (${CT_PCT_EU}%) — near exhaustion"
  fi
else
  warn "conntrack (eu): could not read conntrack count"
fi

# ─────────────────────────────────────────────────────────────
# 4. Errors (last 30min, container logs) — summarized, not just counted
#    Lines are normalized into signatures and grouped. Known noise (scanner
#    401s, expected un-routable dials) is reported but never drives the
#    status; only the remaining "real" errors do, and the top ones are shown.
# ─────────────────────────────────────────────────────────────
# Each remote emits "container<TAB>line". ciris-server is filtered by log
# level (its WARN lines routinely contain the word "error"); the Python
# services by keyword, as before.
ERR_COLLECT='strip() { sed "s/\x1b\[[0-9;]*m//g"; }
for c in $CONTAINERS; do
  docker logs --since 30m $c 2>&1 | strip | grep -iE "error|exception|panic|fatal|aborted" | sed "s/^/$c	/"
done
docker logs --since 30m ciris-server 2>/dev/null | strip | grep -E "^[0-9TZ:.-]+ +ERROR |panicked" | sed "s/^/ciris-server	/"
exit 0'
US_ERR_LINES=$($SSH_US "CONTAINERS='ciris-billing ciris-proxy ciris-caddy ciris-billing-spock ciris-status'; $ERR_COLLECT" 2>/dev/null); US_ERR_RC=$?
EU_ERR_LINES=$($SSH_EU "CONTAINERS='ciris-billing ciris-proxy ciris-caddy ciris-billing-spock'; $ERR_COLLECT" 2>/dev/null); EU_ERR_RC=$?
[ $US_ERR_RC -ne 0 ] && US_ERR_LINES="__unreadable__"
[ $EU_ERR_RC -ne 0 ] && EU_ERR_LINES="__unreadable__"

ERR_SUMMARY=$(US="$US_ERR_LINES" EU="$EU_ERR_LINES" python3 - <<'PY'
import os, re, collections

# Known noise: (label, regex). Counted and shown, never escalated.
KNOWN = [
    ("auth rejected (LiteLLM, no/bad token)",
     re.compile(r"Missing authorization token|Invalid proxy server token|"
                r"user_api_key_auth\(\)|ProxyException: Authentication Error")),
    ("un-routable dial (CIRISEdge#336)",
     re.compile(r"un-routable dest|log_dedup: .*sample=(dial|link_request) target has no route")),
]
# Traceback frames repeat the error they belong to; drop them.
FRAME = re.compile(r"^\s|^Traceback|^raise |^\.\.\.|^\)$")
FATAL = re.compile(r"panicked|\bfatal\b|\bpanic\b", re.I)

def signature(line):
    s = re.sub(r"^\S*\d{4}-\d\d-\d\d[T ][\d:.,]+Z?\s*", "", line)
    s = re.sub(r"^\d\d:\d\d:\d\d - ", "", s)                           # LiteLLM prefix
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "<uuid>", s)
    s = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}(:\d+)?\b", "<ip>", s)
    s = re.sub(r"\b[0-9a-f]{12,}\b|-(?=[a-z]*\d)[a-z0-9]{10}\b", "<id>", s)  # hashes, key_id fingerprints
    s = re.sub(r"\d+", "N", s)
    return s.strip()[:110]

out = []
worst = 0
for node in ("us", "eu"):
    raw = os.environ.get(node.upper(), "")
    if raw == "__unreadable__":
        out.append(("1", f"{node}: could not read container logs"))
        worst = max(worst, 1)
        continue
    known = collections.Counter()
    real = collections.Counter()
    fatal = False
    for row in raw.splitlines():
        cont, _, line = row.partition("\t")
        if not line or FRAME.search(line):
            continue
        label = next((l for l, rx in KNOWN if rx.search(line)), None)
        if label:
            known[label] += 1
        else:
            real[(cont, signature(line))] += 1
            fatal |= bool(FATAL.search(line))
    n = sum(real.values())
    lvl = 2 if fatal or n >= 100 else 1 if n >= 5 else 0
    worst = max(worst, lvl)
    noise = ", ".join(f"{v} {k}" for k, v in known.most_common()) or "none"
    out.append((str(lvl), f"{node}: {n} real; noise: {noise}"))
    for (cont, sig), v in real.most_common(3):
        out.append(("detail", f"{v:>5}  {cont}: {sig}"))
    if len(real) > 3:
        out.append(("detail", f"       … {len(real) - 3} more signature(s)"))

print(worst)
for lvl, text in out:
    print(f"{lvl}\t{text}")
PY
)
ERR_WORST=$(printf '%s\n' "$ERR_SUMMARY" | head -1)
ERR_HEAD="errors (30min)"
case "${ERR_WORST:-2}" in
  0) pass "$ERR_HEAD";;
  1) warn "$ERR_HEAD — drill: docker logs --since 30m <container>";;
  *) fail "$ERR_HEAD — urgent";;
esac
printf '%s\n' "$ERR_SUMMARY" | tail -n +2 | while IFS=$'\t' read -r lvl text; do
  if [ "$lvl" = "detail" ]; then printf "        %s\n" "$text"; else printf "      %s\n" "$text"; fi
done

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
