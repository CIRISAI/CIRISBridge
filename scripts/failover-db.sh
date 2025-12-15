#!/bin/bash
# PostgreSQL Failover Script
# Promotes replica to primary in case of primary failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    local msg="$1"
    echo -e "${GREEN}[INFO]${NC} $msg"
    return 0
}

log_warn() {
    local msg="$1"
    echo -e "${YELLOW}[WARN]${NC} $msg" >&2
    return 0
}

log_error() {
    local msg="$1"
    echo -e "${RED}[ERROR]${NC} $msg" >&2
    return 0
}

# Load IPs
if [[ -f "$ROOT_DIR/terraform/terraform.tfstate" ]]; then
    VULTR_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw vultr_ip 2>/dev/null || echo "${VULTR_IP:-}")
    HETZNER_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw hetzner_ip 2>/dev/null || echo "${HETZNER_IP:-}")
fi

VULTR_IP="${VULTR_IP:-}"
HETZNER_IP="${HETZNER_IP:-}"

if [[ -z "$VULTR_IP" ]] || [[ -z "$HETZNER_IP" ]]; then
    log_error "VULTR_IP and HETZNER_IP must be set"
    exit 1
fi

# Check current primary status
check_primary() {
    log_info "Checking primary (Vultr - $VULTR_IP)..."

    local status
    status=$(ssh -o ConnectTimeout=5 "root@$VULTR_IP" \
        "docker exec ciris-postgres pg_isready -U postgres" 2>/dev/null || echo "failed")

    if [[ "$status" == *"accepting connections"* ]]; then
        echo -e "  ${GREEN}✓${NC} Primary is healthy"
        return 0
    else
        echo -e "  ${RED}✗${NC} Primary is DOWN"
        return 1
    fi
}

# Check replica status
check_replica() {
    log_info "Checking replica (Hetzner - $HETZNER_IP)..."

    local status
    status=$(ssh -o ConnectTimeout=5 "root@$HETZNER_IP" \
        "docker exec ciris-postgres pg_isready -U postgres" 2>/dev/null || echo "failed")

    if [[ "$status" == *"accepting connections"* ]]; then
        echo -e "  ${GREEN}✓${NC} Replica is healthy"
        return 0
    else
        echo -e "  ${RED}✗${NC} Replica is DOWN"
        return 1
    fi
}

# Promote replica to primary
promote_replica() {
    log_warn "PROMOTING REPLICA TO PRIMARY"
    log_warn "This is a manual failover operation!"
    echo ""

    read -p "Are you sure you want to promote the replica? (yes/no) " -r
    echo ""

    if [[ "$REPLY" != "yes" ]]; then
        log_info "Failover cancelled"
        exit 0
    fi

    log_info "Promoting replica..."

    # Promote PostgreSQL replica
    ssh "root@$HETZNER_IP" "docker exec ciris-postgres pg_ctl promote -D /var/lib/postgresql/data"

    log_info "Replica promoted!"

    # Update application configs to point to new primary
    log_warn "MANUAL STEPS REQUIRED:"
    echo "  1. Update DNS records to point billing/proxy to Hetzner IP"
    echo "  2. Update application configs to use new primary"
    echo "  3. Reconfigure Vultr as new replica when recovered"
    echo ""

    log_info "Failover complete. See manual steps above."
    return 0
}

# Main
echo "========================================"
echo "CIRISBridge Database Failover"
echo "========================================"
echo ""

case "${1:-status}" in
    status)
        check_primary || true
        check_replica || true
        ;;
    promote)
        if check_primary; then
            log_warn "Primary is still healthy. Failover not recommended."
            read -p "Continue anyway? (yes/no) " -r
            if [[ "$REPLY" != "yes" ]]; then
                exit 0
            fi
        fi

        if ! check_replica; then
            log_error "Replica is not healthy. Cannot promote."
            exit 1
        fi

        promote_replica
        ;;
    *)
        echo "Usage: $0 [status|promote]"
        echo ""
        echo "Commands:"
        echo "  status  - Check primary and replica health"
        echo "  promote - Promote replica to primary (manual failover)"
        exit 1
        ;;
esac
