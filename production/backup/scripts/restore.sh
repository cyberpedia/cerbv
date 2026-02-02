#!/bin/bash
# Cerberus Restore Script
# RTO: 4 hours

set -euo pipefail

# Configuration
export RESTORE_SOURCE="${RESTORE_SOURCE:-s3://cerberus-backups/postgresql}"
export BACKUP_NAME="${1:-latest}"
export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
export BACKUP_DIR="${BACKUP_DIR:-/var/backups/cerberus}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [RESTORE] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
    exit 1
}

# Stop application
log "Stopping application services..."
kubectl scale deployment/cerberus-backend --replicas=0 -n cerberus 2>/dev/null || true
kubectl scale deployment/cerberus-frontend --replicas=0 -n cerberus 2>/dev/null || true
kubectl scale deployment/cerberus-realtime --replicas=0 -n cerberus 2>/dev/null || true

# PostgreSQL Restore
log "Restoring PostgreSQL..."

# Option 1: pgBackRest restore
if command -v pg_backrest &> /dev/null; then
    log "Stopping PostgreSQL..."
    pg_ctl -D "${PGDATA}" stop -m fast || true
    
    log "Removing old data directory..."
    rm -rf "${PGDATA}"/*
    
    log "Restoring from pgBackRest..."
    pg_backrest --stanza=cerberus restore
    
    log "Starting PostgreSQL..."
    pg_ctl -D "${PGDATA}" start
    
    log "Verifying PostgreSQL..."
    pg_isready -U postgres
    
# Option 2: pg_restore from pg_dump
else
    log "Using pg_restore..."
    
    # Find backup file
    if [ "${BACKUP_NAME}" = "latest" ]; then
        BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/cerberus_*.pgdump 2>/dev/null | head -1)
    else
        BACKUP_FILE="${BACKUP_DIR}/cerberus_${BACKUP_NAME}.pgdump"
    fi
    
    if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
        error "Backup file not found: ${BACKUP_FILE}"
    fi
    
    log "Dropping existing database..."
    dropdb -h postgres-primary -U postgres cerberus 2>/dev/null || true
    
    log "Creating database..."
    createdb -h postgres-primary -U postgres cerberus
    
    log "Restoring database..."
    pg_restore -h postgres-primary -U postgres -d cerberus -c "${BACKUP_FILE}"
fi

log "PostgreSQL restore completed"

# Redis Restore
log "Restoring Redis..."
redis-cli FLUSHALL || true
redis-cli --rdb "${BACKUP_DIR}/cerberus_latest.rdb" 2>/dev/null || true
log "Redis restore completed"

# Verify application can start
log "Verifying application health..."
kubectl apply -f k8s/base/backend/deployment.yaml
kubectl rollout status deployment/cerberus-backend -n cerberus --timeout=5m

log "Restore completed successfully!"

# Send notification
if [ -n "${WEBHOOK_URL:-}" ]; then
    curl -X POST "${WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"Cerberus restore completed from backup: ${BACKUP_NAME}\"}" 2>/dev/null || true
fi
