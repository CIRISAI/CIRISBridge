#!/bin/bash
# PostgreSQL Backup Script
# Creates compressed backups of the billing database

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/opt/ciris/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ciris_billing_${TIMESTAMP}.sql.gz"

# Load IPs
if [[ -f "$ROOT_DIR/terraform/terraform.tfstate" ]]; then
    VULTR_IP=$(cd "$ROOT_DIR/terraform" && terraform output -raw vultr_ip 2>/dev/null || echo "${VULTR_IP:-}")
fi

VULTR_IP="${VULTR_IP:-localhost}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

if [[ -z "$POSTGRES_PASSWORD" ]]; then
    log_error "POSTGRES_PASSWORD must be set"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

log_info "Starting backup of ciris_billing..."

# Create backup via SSH to primary (Vultr)
if [[ "$VULTR_IP" == "localhost" ]]; then
    # Local backup
    docker exec ciris-postgres pg_dump -U postgres ciris_billing | gzip > "$BACKUP_DIR/$BACKUP_FILE"
else
    # Remote backup
    ssh "root@$VULTR_IP" "docker exec ciris-postgres pg_dump -U postgres ciris_billing" | gzip > "$BACKUP_DIR/$BACKUP_FILE"
fi

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
log_info "Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Clean up old backups
log_info "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "ciris_billing_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# List current backups
log_info "Current backups:"
ls -lh "$BACKUP_DIR"/ciris_billing_*.sql.gz 2>/dev/null || echo "  (none)"

log_info "Backup complete!"
