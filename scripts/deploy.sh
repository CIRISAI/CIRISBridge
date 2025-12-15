#!/bin/bash
# CIRISBridge Deployment Script
# Usage: ./scripts/deploy.sh [all|infra|services|dns|billing|proxy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prereqs() {
    log_info "Checking prerequisites..."

    command -v terraform >/dev/null 2>&1 || { log_error "terraform required but not installed"; exit 1; }
    command -v ansible-playbook >/dev/null 2>&1 || { log_error "ansible required but not installed"; exit 1; }

    if [[ ! -f "$ROOT_DIR/terraform/terraform.tfvars" ]]; then
        log_error "terraform/terraform.tfvars not found. Copy from terraform.tfvars.example"
        exit 1
    fi

    if [[ ! -f "$ROOT_DIR/ansible/inventory/production.yml" ]]; then
        log_warn "ansible/inventory/production.yml not found. Will generate from Terraform."
    fi

    log_info "Prerequisites OK"
    return 0
}

# Deploy infrastructure with Terraform
deploy_infra() {
    log_info "Deploying infrastructure with Terraform..."

    cd "$ROOT_DIR/terraform"

    terraform init
    terraform plan -out=tfplan

    echo ""
    read -p "Apply Terraform plan? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        terraform apply tfplan

        # Generate Ansible inventory from Terraform output
        log_info "Generating Ansible inventory..."
        terraform output -raw ansible_inventory > "$ROOT_DIR/ansible/inventory/production.yml"

        log_info "Infrastructure deployed. IPs:"
        terraform output vultr_ip
        terraform output hetzner_ip
    else
        log_warn "Terraform apply cancelled"
    fi

    cd "$ROOT_DIR"
    return 0
}

# Deploy all services with Ansible
deploy_services() {
    log_info "Deploying services with Ansible..."

    cd "$ROOT_DIR/ansible"

    ansible-playbook playbooks/site.yml

    cd "$ROOT_DIR"
    log_info "Services deployed"
    return 0
}

# Deploy DNS only
deploy_dns() {
    log_info "Deploying DNS (Constellation)..."

    cd "$ROOT_DIR/ansible"
    ansible-playbook playbooks/dns.yml
    cd "$ROOT_DIR"

    log_info "DNS deployed"
    return 0
}

# Deploy billing only
deploy_billing() {
    log_info "Deploying CIRISBilling..."

    cd "$ROOT_DIR/ansible"
    ansible-playbook playbooks/billing.yml
    cd "$ROOT_DIR"

    log_info "Billing deployed"
    return 0
}

# Deploy proxy only
deploy_proxy() {
    log_info "Deploying CIRISProxy..."

    cd "$ROOT_DIR/ansible"
    ansible-playbook playbooks/proxy.yml
    cd "$ROOT_DIR"

    log_info "Proxy deployed"
    return 0
}

# Main
case "${1:-all}" in
    all)
        check_prereqs
        deploy_infra
        deploy_services
        ;;
    infra)
        check_prereqs
        deploy_infra
        ;;
    services)
        check_prereqs
        deploy_services
        ;;
    dns)
        check_prereqs
        deploy_dns
        ;;
    billing)
        check_prereqs
        deploy_billing
        ;;
    proxy)
        check_prereqs
        deploy_proxy
        ;;
    *)
        echo "Usage: $0 [all|infra|services|dns|billing|proxy]"
        exit 1
        ;;
esac

log_info "Deployment complete!"
