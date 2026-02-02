#!/bin/bash
# Cerberus Backup Script
# Scheduled backup with retention management

set -euo pipefail

# Configuration
export BACKUP_DIR="${BACKUP_DIR:-/var/backups/cerberus}"
export S3_BUCKET="${S3_BUCKET:-cerberus-backups}"
export S3_ENDPOINT="${S3_ENDPOINT:-minio:9000}"
export PGHOST="${PGHOST:-postgres-primary}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"

# Timestamps
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="cerberus_${DATE}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Create backup directory
mkdir -p "${BACKUP_DIR}"

log "Starting backup: ${BACKUP_NAME}"

# 1. PostgreSQL backup with pgBackRest
log "Backing up PostgreSQL..."
if command -v pg_backrest &> /dev/null; then
    pg_backrest --stanza=cerberus backup --type=full
    log "PostgreSQL backup completed"
else
    # Fallback to pg_dump
    pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -Fc -f "${BACKUP_DIR}/${BACKUP_NAME}.pgdump" cerberus
    log "PostgreSQL dump completed"
fi

# 2. Backup Redis data
log "Backing up Redis..."
redis-cli BGSAVE
sleep 5
redis-cli LASTSAVE > "${BACKUP_DIR}/${BACKUP_NAME}_redis_last_save.txt"
redis-cli --rdb "${BACKUP_DIR}/${BACKUP_NAME}.rdb" 2>/dev/null || true
log "Redis backup completed"

# 3. Backup configuration files
log "Backing up configuration..."
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}_config.tar.gz" \
    /opt/cerberus/config/ \
    /opt/cerberus/docker-compose.yml \
    /opt/cerberus/k8s/ 2>/dev/null || true
log "Configuration backup completed"

# 4. Upload to S3/MinIO
log "Uploading backups to S3..."
MC_HOST_S3="http://${S3_ENDPOINT} ${S3_ACCESS_KEY}:${S3_SECRET_KEY}"
mc alias set s3 "${MC_HOST_S3}" 2>/dev/null || true

# Upload PostgreSQL backup
mc cp "${BACKUP_DIR}/${BACKUP_NAME}.pgdump" "s3/${S3_BUCKET}/postgresql/" 2>/dev/null || true

# Upload Redis backup
mc cp "${BACKUP_NAME}.rdb" "s3/${S3_BUCKET}/redis/" 2>/dev/null || true

# Upload config backup
mc cp "${BACKUP_DIR}/${BACKUP_NAME}_config.tar.gz" "s3/${S3_BUCKET}/config/" 2>/dev/null || true

log "S3 upload completed"

# 5. Cleanup old local backups
log "Cleaning up old local backups..."
find "${BACKUP_DIR}" -name "cerberus_*" -mtime +7 -delete
log "Local cleanup completed"

# 6. Verify backup integrity
log "Verifying backup integrity..."
if [ -f "${BACKUP_DIR}/${BACKUP_NAME}.pgdump" ]; then
    SIZE=$(stat -f%z "${BACKUP_DIR}/${BACKUP_NAME}.pgdump" 2>/dev/null || stat -c%s "${BACKUP_DIR}/${BACKUP_NAME}.pgdump")
    log "Backup size: ${SIZE} bytes"
fi

log "Backup completed successfully: ${BACKUP_NAME}"

# Send notification
if [ -n "${WEBHOOK_URL:-}" ]; then
    curl -X POST "${WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"Cerberus backup completed: ${BACKUP_NAME}\"}" 2>/dev/null || true
fi
