#!/bin/bash
# Cerberus CTF Platform - MinIO Container Entrypoint
# Erasure coding setup with 4 drives on loopback for single-disk deployment

set -euo pipefail

# Configuration
MINIO_DATA_DIR="${MINIO_DATA_DIR:-/data}"
MINIO_DISKS="${MINIO_DISKS:-4}"
MINIO_LOOP_SIZE="${MINIO_LOOP_SIZE:-1G}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-cerberus-admin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-}"  # Must be provided via env

log() {
    echo "[$(date -Iseconds)] [MinIO Setup] $*"
}

error_exit() {
    echo "[$(date -Iseconds)] [ERROR] $*" >&2
    exit 1
}

# Validate required variables
if [[ -z "$MINIO_ROOT_PASSWORD" ]]; then
    error_exit "MINIO_ROOT_PASSWORD must be set"
fi

# Check if disks already exist
if [[ -d "${MINIO_DATA_DIR}/disk1" ]] && [[ -f "${MINIO_DATA_DIR}/disk1/.minio.sys/format.json" ]]; then
    log "MinIO data directories already initialized"
else
    log "Initializing MinIO erasure coding setup..."
    
    # Create disk directories
    for i in $(seq 1 $MINIO_DISKS); do
        mkdir -p "${MINIO_DATA_DIR}/disk${i}"
        log "Created disk directory: ${MINIO_DATA_DIR}/disk${i}"
    done
    
    # Set proper permissions
    chown -R minio:minio "${MINIO_DATA_DIR}"
    chmod 750 "${MINIO_DATA_DIR}"
    
    log "Disk initialization complete"
fi

# Export MinIO environment
export MINIO_ROOT_USER
export MINIO_ROOT_PASSWORD
export MINIO_VOLUMES=""

# Build volume string for erasure coding
for i in $(seq 1 $MINIO_DISKS); do
    if [[ -z "$MINIO_VOLUMES" ]]; then
        MINIO_VOLUMES="${MINIO_DATA_DIR}/disk${i}"
    else
        MINIO_VOLUMES="${MINIO_VOLUMES} ${MINIO_DATA_DIR}/disk${i}"
    fi
done

export MINIO_VOLUMES

# KMS Configuration (if available)
if [[ -n "${MINIO_KMS_SECRET_KEY:-}" ]]; then
    log "KMS encryption enabled"
    export MINIO_KMS_SECRET_KEY
fi

# Audit logging
if [[ -n "${MINIO_AUDIT_WEBHOOK_ENDPOINT:-}" ]]; then
    log "Audit logging enabled to: ${MINIO_AUDIT_WEBHOOK_ENDPOINT}"
    export MINIO_AUDIT_WEBHOOK_ENABLE
    export MINIO_AUDIT_WEBHOOK_ENDPOINT
fi

# Browser setting
export MINIO_BROWSER="${MINIO_BROWSER:-on}"

# Prometheus metrics
export MINIO_PROMETHEUS_AUTH_TYPE="${MINIO_PROMETHEUS_AUTH_TYPE:-public}"

# Console address
export MINIO_CONSOLE_ADDRESS="${MINIO_CONSOLE_ADDRESS:-:9001}"

# Server URL (for presigned URLs)
if [[ -n "${MINIO_SERVER_URL:-}" ]]; then
    export MINIO_SERVER_URL
fi

log "Starting MinIO server with erasure coding (${MINIO_DISKS} drives)..."
log "Volume configuration: ${MINIO_VOLUMES}"

# Health check verification delay
sleep 2

# Execute MinIO server
exec minio server ${MINIO_VOLUMES} \
    --address ":9000" \
    --console-address "${MINIO_CONSOLE_ADDRESS}"
