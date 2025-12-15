#!/bin/bash
# Sync DNS records to Constellation instances
# Reads zones.yaml and pushes to both DNS servers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    local msg="$1"
    echo -e "${GREEN}[INFO]${NC} $msg"
    return 0
}

log_error() {
    local msg="$1"
    echo -e "${RED}[ERROR]${NC} $msg" >&2
    return 0
}

# Load configuration
if [[ -f "$ROOT_DIR/terraform/terraform.tfstate" ]]; then
    VULTR_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw vultr_ip 2>/dev/null || echo "${VULTR_IP:-}")
    HETZNER_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw hetzner_ip 2>/dev/null || echo "${HETZNER_IP:-}")
fi

VULTR_IP="${VULTR_IP:-}"
HETZNER_IP="${HETZNER_IP:-}"
CONSTELLATION_API_TOKEN="${CONSTELLATION_API_TOKEN:-}"

if [[ -z "$VULTR_IP" ]] || [[ -z "$HETZNER_IP" ]]; then
    log_error "VULTR_IP and HETZNER_IP must be set"
    exit 1
fi

# Zones file
ZONES_FILE="$ROOT_DIR/ansible/roles/constellation/templates/zones.yaml.j2"

if [[ ! -f "$ZONES_FILE" ]]; then
    log_error "Zones file not found: $ZONES_FILE"
    exit 1
fi

sync_record() {
    local server_ip=$1
    local zone=$2
    local name=$3
    local type=$4
    local value=$5
    local ttl=${6:-300}

    local url="http://$server_ip:8080/zone/$zone/record"
    local auth_header=""

    if [[ -n "$CONSTELLATION_API_TOKEN" ]]; then
        auth_header="-H 'Authorization: Bearer $CONSTELLATION_API_TOKEN'"
    fi

    # Constellation REST API format
    local payload
    payload=$(cat <<EOF
{
    "name": "$name",
    "type": "$type",
    "value": "$value",
    "ttl": $ttl
}
EOF
)

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$url" \
        -H "Content-Type: application/json" \
        $auth_header \
        -d "$payload" 2>/dev/null || echo "000")

    if [[ "$status" == "200" ]] || [[ "$status" == "201" ]]; then
        echo -e "  ${GREEN}✓${NC} $name.$zone -> $value"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name.$zone (status: $status)"
        return 1
    fi
}

log_info "Syncing DNS records..."

# Sync to Vultr (primary)
if [[ -n "$VULTR_IP" ]]; then
    log_info "Syncing to Vultr ($VULTR_IP)..."

    # Primary domain records
    sync_record "$VULTR_IP" "ciris-services-1.ai" "@" "A" "$VULTR_IP"
    sync_record "$VULTR_IP" "ciris-services-1.ai" "billing1" "A" "$VULTR_IP"
    sync_record "$VULTR_IP" "ciris-services-1.ai" "proxy1" "A" "$VULTR_IP"
    sync_record "$VULTR_IP" "ciris-services-1.ai" "ns1" "A" "$VULTR_IP"
    sync_record "$VULTR_IP" "ciris-services-1.ai" "agents" "A" "$VULTR_IP"

    # Secondary domain records (for cross-reference)
    sync_record "$VULTR_IP" "ciris-services-2.ai" "@" "A" "$HETZNER_IP"
    sync_record "$VULTR_IP" "ciris-services-2.ai" "billing1" "A" "$HETZNER_IP"
    sync_record "$VULTR_IP" "ciris-services-2.ai" "proxy1" "A" "$HETZNER_IP"
    sync_record "$VULTR_IP" "ciris-services-2.ai" "ns1" "A" "$HETZNER_IP"
fi

# Sync to Hetzner (secondary)
if [[ -n "$HETZNER_IP" ]]; then
    log_info "Syncing to Hetzner ($HETZNER_IP)..."

    # Primary domain records (for cross-reference)
    sync_record "$HETZNER_IP" "ciris-services-1.ai" "@" "A" "$VULTR_IP"
    sync_record "$HETZNER_IP" "ciris-services-1.ai" "billing1" "A" "$VULTR_IP"
    sync_record "$HETZNER_IP" "ciris-services-1.ai" "proxy1" "A" "$VULTR_IP"
    sync_record "$HETZNER_IP" "ciris-services-1.ai" "ns1" "A" "$VULTR_IP"

    # Secondary domain records
    sync_record "$HETZNER_IP" "ciris-services-2.ai" "@" "A" "$HETZNER_IP"
    sync_record "$HETZNER_IP" "ciris-services-2.ai" "billing1" "A" "$HETZNER_IP"
    sync_record "$HETZNER_IP" "ciris-services-2.ai" "proxy1" "A" "$HETZNER_IP"
    sync_record "$HETZNER_IP" "ciris-services-2.ai" "ns1" "A" "$HETZNER_IP"
    sync_record "$HETZNER_IP" "ciris-services-2.ai" "agents" "A" "$HETZNER_IP"
fi

log_info "DNS sync complete!"
