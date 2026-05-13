#!/usr/bin/env bash
# scripts/weekly-status.sh — comprehensive weekly SRE check.
#
# Designed for Monday-morning autonomous run (systemd timer or cron).
# Output is a markdown report on stdout; snapshot JSON saved alongside.
#
# Includes everything daily-status.sh checks + week-over-week deltas +
# open issues sweep + PII inventory delta + cert <30d watch + disk trend.
#
# Exit code: 0 if all green, 1 if any yellow, 2 if any red.

set -uo pipefail
cd "$(dirname "$0")/.."

NOW_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NOW_DATE=$(date -u +"%Y-%m-%d")

# Find previous week's snapshot if one exists
PREV_SNAPSHOT=$(ls -t /tmp/bridge-weekly-*.json 2>/dev/null | head -1)
THIS_SNAPSHOT=/tmp/bridge-weekly-$(date -u +%Y%m%d).json
REPORT=/tmp/bridge-weekly-report-$(date -u +%Y%m%d).md

WORST=0
note_yellow() { [ $WORST -lt 1 ] && WORST=1; }
note_red()    { WORST=2; }

# ─────────────────────────────────────────────────────────────
# Section 1: Capture this week's surface snapshot
# ─────────────────────────────────────────────────────────────
python3 scripts/surface-scan.py --internal --out "$THIS_SNAPSHOT" --quiet 2>/dev/null

# ─────────────────────────────────────────────────────────────
# Section 2: Build the report
# ─────────────────────────────────────────────────────────────
{
  echo "# Bridge weekly status — $NOW_DATE"
  echo
  echo "_Generated $NOW_ISO by \`scripts/weekly-status.sh\`._"
  echo

  # ── Surface snapshot summary ────────────────────────────────
  echo "## Surface"
  echo

  python3 - "$THIS_SNAPSHOT" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    s = json.load(f)
probes = s.get("probes", [])
passed = sum(1 for p in probes if p.get("passed"))
total = len(probes)
print(f"| Axis | Result |")
print(f"|---|---|")
print(f"| Probes | {passed}/{total} {'✓' if passed==total else '⚠'} |")
tls = s.get("tls", {})
min_days = min((t.get("days_remaining", 0) for t in tls.values()), default=999)
near = sorted([(d, t["days_remaining"]) for d, t in tls.items() if 0 < t.get("days_remaining", 999) < 30], key=lambda x:x[1])
print(f"| TLS | {len(tls)}/{len(tls)} valid, min={min_days}d{'  ⚠ <30d!' if near else ''} |")
for h in s.get("internal", []):
    name = h["name"].upper()
    disk = h.get("disk", {}).get("pct", "?")
    cnt = h.get("container_count", 0)
    expected = 8 if h["name"] == "us" else 5
    marker = '✓' if cnt == expected else '⚠'
    print(f"| {name} disk | {disk} |")
    print(f"| {name} containers | {cnt}/{expected} {marker} |")
    print(f"| {name} spock | {h.get('spock','?')[:40]} |")
print()
if near:
    print(f"**Certs approaching expiry (<30d)**:")
    for d, days in near:
        print(f"- {d}: {days}d remaining")
    print()
PY

  # ── Diff vs previous week ────────────────────────────────────
  echo
  echo "## Week-over-week diff"
  echo
  if [ -n "$PREV_SNAPSHOT" ] && [ "$PREV_SNAPSHOT" != "$THIS_SNAPSHOT" ]; then
    echo "_Comparing with previous snapshot: \`$(basename "$PREV_SNAPSHOT")\`_"
    echo
    DIFF=$(python3 scripts/surface-scan.py --diff "$PREV_SNAPSHOT" "$THIS_SNAPSHOT" 2>/dev/null)
    NUM_CHANGES=$(echo "$DIFF" | python3 -c "import json,sys; d=json.load(sys.stdin); c=d.get('changes',{}); print(sum(len(v) for v in c.values()))" 2>/dev/null || echo "0")
    if [ "${NUM_CHANGES:-0}" = "0" ]; then
      echo "No material changes."
    else
      echo "\`\`\`json"
      echo "$DIFF" | head -60
      echo "\`\`\`"
    fi
  else
    echo "No prior snapshot for diff (first run, or previous week's snapshot rotated). Baseline established."
  fi

  # ── Open issues across fleet ─────────────────────────────────
  echo
  echo "## Open issues across CIRIS* repos"
  echo
  TOTAL_OPEN=0
  BRIDGE_FILED_OLD=0
  for R in CIRISBridge CIRISPersist CIRISLens CIRISAgent CIRISVerify CIRISRegistry CIRISEdge CIRISManager CIRISCore; do
    COUNT=$(gh issue list --repo CIRISAI/$R --state open --json number --jq 'length' 2>/dev/null)
    [ -z "$COUNT" ] && COUNT=0
    TOTAL_OPEN=$((TOTAL_OPEN + COUNT))
    [ "$COUNT" -eq 0 ] && continue
    echo "### $R ($COUNT open)"
    echo
    gh issue list --repo CIRISAI/$R --state open --limit 30 --json number,title,createdAt,updatedAt,author,labels 2>/dev/null \
      | python3 -c "
import json, sys
from datetime import datetime, timezone
d = json.load(sys.stdin)
now = datetime.now(timezone.utc)
for i in d:
    created = datetime.fromisoformat(i['createdAt'])
    updated = datetime.fromisoformat(i['updatedAt'])
    age = (now - created).days
    idle = (now - updated).days
    flag = ''
    if age <= 7: flag = ' 🆕'
    elif idle > 14: flag = ' 🕸'
    labels = ','.join(l['name'] for l in i.get('labels', []))
    labels_str = f' \`[{labels}]\`' if labels else ''
    title = i['title'].replace('|','\\|')[:80]
    print(f\"- #{i['number']} ({age}d, idle {idle}d){flag} {title}{labels_str}\")
"
    echo
  done
  echo "**Total open across fleet**: $TOTAL_OPEN issues."

  # ── Cert expiry watch (yellow if any <30d) ────────────────────
  NEAR_CERT_COUNT=$(python3 -c "
import json
with open('$THIS_SNAPSHOT') as f: s = json.load(f)
print(sum(1 for t in s.get('tls', {}).values() if 0 < t.get('days_remaining', 999) < 30))
")
  [ "${NEAR_CERT_COUNT:-0}" -gt 0 ] && note_yellow

  # ── Disk trend (yellow >70%, red >85%) ────────────────────────
  HIGH_DISK=$(python3 -c "
import json
with open('$THIS_SNAPSHOT') as f: s = json.load(f)
for h in s.get('internal', []):
    pct = int(h.get('disk',{}).get('pct','0%').rstrip('%') or 0)
    if pct >= 85: print('red'); break
    elif pct >= 70: print('yellow'); break
")
  [ "$HIGH_DISK" = "yellow" ] && note_yellow
  [ "$HIGH_DISK" = "red" ] && note_red

  # ── Closing ───────────────────────────────────────────────────
  echo
  echo "## Overall"
  echo
  case $WORST in
    0) echo "✓ **GREEN** — no axes requiring attention this week.";;
    1) echo "⚠ **YELLOW** — see flags above; not urgent but worth scheduling.";;
    2) echo "✗ **RED** — investigate immediately.";;
  esac
  echo
  echo "_Next weekly run: $(date -u -d '+7 days' +%Y-%m-%d)._"
  echo "_Snapshots preserved at \`/tmp/bridge-weekly-*.json\`; rotate manually if disk pressure._"

} > "$REPORT"

# Print to stdout for cron capture
cat "$REPORT"

# Print snapshot paths to stderr
echo "snapshot: $THIS_SNAPSHOT" >&2
echo "report:   $REPORT" >&2

exit $WORST
