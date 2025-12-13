#!/bin/bash
# CIRISBridge Health Check Script
# Checks health of all services across both regions

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load IPs from Terraform state or environment
if [[ -f "$ROOT_DIR/terraform/terraform.tfstate" ]]; then
    VULTR_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw vultr_ip 2>/dev/null || echo "${VULTR_IP:-}")
    HETZNER_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw hetzner_ip 2>/dev/null || echo "${HETZNER_IP:-}")
fi

# Fallback to environment variables
VULTR_IP="${VULTR_IP:-}"
HETZNER_IP="${HETZNER_IP:-}"
PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-ciris-services-1.ai}"
SECONDARY_DOMAIN="${SECONDARY_DOMAIN:-ciris-services-2.ai}"

check_service() {
    local name=$1
    local url=$2
    local expected=${3:-200}

    local status_code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")

    if [[ "$status_code" == "$expected" ]]; then
        echo -e "  ${GREEN}✓${NC} $name: OK ($status_code)"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name: FAILED ($status_code)"
        return 1
    fi
}

check_dns() {
    local name=$1
    local server=$2
    local domain=$3

    local result
    result=$(dig +short @"$server" "$domain" 2>/dev/null || echo "")

    if [[ -n "$result" ]]; then
        echo -e "  ${GREEN}✓${NC} $name: $result"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name: No response"
        return 1
    fi
}

echo "========================================"
echo "CIRISBridge Health Check"
echo "========================================"
echo ""

ERRORS=0

# Check primary region (Vultr)
if [[ -n "$VULTR_IP" ]]; then
    echo "Primary Region (Vultr - $VULTR_IP):"
    check_service "Billing" "https://billing1.$PRIMARY_DOMAIN/health" || ((ERRORS++))
    check_service "Proxy" "https://proxy1.$PRIMARY_DOMAIN/health" || ((ERRORS++))
    check_dns "DNS" "$VULTR_IP" "billing1.$PRIMARY_DOMAIN" || ((ERRORS++))
    echo ""
else
    echo -e "${YELLOW}Primary region IPs not configured${NC}"
    echo ""
fi

# Check secondary region (Hetzner)
if [[ -n "$HETZNER_IP" ]]; then
    echo "Secondary Region (Hetzner - $HETZNER_IP):"
    check_service "Billing" "https://billing1.$SECONDARY_DOMAIN/health" || ((ERRORS++))
    check_service "Proxy" "https://proxy1.$SECONDARY_DOMAIN/health" || ((ERRORS++))
    check_dns "DNS" "$HETZNER_IP" "billing1.$SECONDARY_DOMAIN" || ((ERRORS++))
    echo ""
else
    echo -e "${YELLOW}Secondary region IPs not configured${NC}"
    echo ""
fi

# Check via public DNS (if domains are configured)
echo "Public DNS Resolution:"
check_dns "billing1.$PRIMARY_DOMAIN" "8.8.8.8" "billing1.$PRIMARY_DOMAIN" || ((ERRORS++))
check_dns "billing1.$SECONDARY_DOMAIN" "8.8.8.8" "billing1.$SECONDARY_DOMAIN" || ((ERRORS++))
echo ""

# Summary
echo "========================================"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS check(s) failed${NC}"
    exit 1
fi
