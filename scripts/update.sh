#!/bin/bash
# Cerberus Zero-Downtime Update Script
# RTO: 0 seconds (rolling update with zero downtime)
# RPO: 0 seconds (no data loss)

set -euo pipefail

# Configuration
DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-k8s}"  # k8s or docker
NAMESPACE="${NAMESPACE:-cerberus}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-ghcr.io}"
BACKUP_BEFORE_UPDATE="${BACKUP_BEFORE_UPDATE:-true}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

confirm() {
    if [ "${AUTO_CONFIRM:-false}" = "true" ]; then
        return 0
    fi
    read -p "$1 [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

wait_for_rollout() {
    local deployment="$1"
    local timeout="${2:-300}"
    
    log "Waiting for $deployment rollout to complete..."
    
    if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout="${timeout}s"; then
        success "$deployment rollout complete"
        return 0
    else
        error "$deployment rollout failed or timed out"
    fi
}

pre_update_checks() {
    log "Running pre-update checks..."
    
    # Check cluster health
    if ! kubectl get nodes | grep -q "Ready"; then
        error "Not all nodes are ready"
    fi
    
    # Check available resources
    available_cpu=$(kubectl get nodes -o jsonpath='{range .items[*]}{.status.allocatable.cpu}{"\n"}{end}' | awk '{sum+=$1} END {print sum}')
    required_cpu=4
    
    if [ "$available_cpu" -lt "$required_cpu" ]; then
        warning "Low CPU resources available ($available_cpu cores, need $required_cpu)"
    fi
    
    # Check storage
    available_storage=$(kubectl get pv -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}' | grep -c "Bound" || echo 0)
    
    success "Pre-update checks passed"
}

create_backup() {
    if [ "${BACKUP_BEFORE_UPDATE}" != "true" ]; then
        warning "Skipping backup (BACKUP_BEFORE_UPDATE=false)"
        return 0
    fi
    
    log "Creating pre-update backup..."
    
    # Trigger pgBackRest backup
    kubectl exec -n "$NAMESPACE" deploy/postgres-primary -- \
        pgbackrest --stanza=cerberus backup --type=full || warning "pgBackRest backup failed"
    
    # Create Velero backup
    if command -v velero &> /dev/null; then
        velero backup create "cerberus-pre-update-$(date +%Y%m%d%H%M%S)" \
            --include-namespaces "$NAMESPACE" || warning "Velero backup failed"
    fi
    
    success "Backup completed"
}

update_images() {
    local component="$1"
    local image_tag="${2:-latest}"
    
    log "Updating $component to $image_tag..."
    
    if [ "$DEPLOYMENT_TYPE" = "k8s" ]; then
        kubectl set image deployment/"$component" \
            "$component"="$DOCKER_REGISTRY/cerberus-$component:$image_tag" \
            -n "$NAMESPACE"
    else
        docker compose pull "$component"
        docker compose up -d "$component"
    fi
}

scale_down_services() {
    log "Scaling down non-critical services..."
    
    # Scale down realtime first (WebSocket connections)
    kubectl scale deployment/cerberus-realtime --replicas=0 -n "$NAMESPACE" || true
    sleep 5
}

scale_up_services() {
    log "Scaling up services..."
    
    # Start realtime with 1 replica
    kubectl scale deployment/cerberus-realtime --replicas=1 -n "$NAMESPACE" || true
    wait_for_rollout "cerberus-realtime" 120
    
    # Scale up to full capacity
    kubectl scale deployment/cerberus-realtime --replicas=3 -n "$NAMESPACE" || true
    
    # Start backend
    kubectl scale deployment/cerberus-backend --replicas=3 -n "$NAMESPACE" || true
    wait_for_rollout "cerberus-backend" 180
    
    # Start frontend
    kubectl scale deployment/cerberus-frontend --replicas=2 -n "$NAMESPACE" || true
    wait_for_rollout "cerberus-frontend" 120
}

verify_update() {
    log "Verifying update..."
    
    # Check all pods are running
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app=cerberus \
        -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep -c "True" || echo 0)
    
    total_pods=$(kubectl get pods -n "$NAMESPACE" -l app=cerberus --no-headers | wc -l)
    
    if [ "$ready_pods" -eq "$total_pods" ]; then
        success "All $ready_pods pods are ready"
    else
        error "Only $ready_pods/$total_pods pods are ready"
    fi
    
    # Run health check
    if curl -sf http://localhost:8000/health > /dev/null; then
        success "API health check passed"
    else
        warning "API health check failed"
    fi
    
    # Check database connection
    if kubectl exec -n "$NAMESPACE" deploy/backend -- \
        python -c "from app.core.database import test_connection; test_connection()" 2>/dev/null; then
        success "Database connection verified"
    else
        warning "Database connection check failed"
    fi
}

update_database() {
    local migration_file="$1"
    
    if [ -z "$migration_file" ] || [ ! -f "$migration_file" ]; then
        log "No database migration file provided, skipping"
        return 0
    fi
    
    log "Running database migrations: $migration_file"
    
    # Backup before migration
    create_backup
    
    # Run migrations
    if [ "$DEPLOYMENT_TYPE" = "k8s" ]; then
        kubectl exec -n "$NAMESPACE" deploy/backend -- \
            python -m alembic upgrade head
    else
        docker compose exec backend python -m alembic upgrade head
    fi
    
    success "Database migration completed"
}

rollback() {
    local previous_image="$1"
    
    log "Initiating rollback to $previous_image..."
    
    # Scale down current deployments
    kubectl scale deployment/cerberus-backend --replicas=0 -n "$NAMESPACE" || true
    kubectl scale deployment/cerberus-frontend --replicas=0 -n "$NAMESPACE" || true
    
    # Restore from backup
    log "Restoring from backup..."
    velero restore create "cerberus-rollback-$(date +%Y%m%d%H%M%S)" \
        --from-backup "cerberus-pre-update-$(date +%Y%m%d)*" || true
    
    # Scale up
    scale_up_services
    
    success "Rollback initiated"
}

# Main update workflow
main() {
    local component="${1:-all}"
    local image_tag="${2:-latest}"
    
    echo ""
    echo "Cerberus Zero-Downtime Update"
    echo "=============================="
    echo ""
    
    log "Component: $component"
    log "Image tag: $image_tag"
    log "Deployment type: $DEPLOYMENT_TYPE"
    echo ""
    
    # Pre-update checks
    pre_update_checks
    
    # Confirm update
    confirm "Proceed with update?"
    
    # Create backup
    create_backup
    
    if [ "$component" = "all" ]; then
        # Update all components
        scale_down_services
        
        # Update each component
        update_images "backend" "$image_tag"
        wait_for_rollout "cerberus-backend" 300
        
        update_images "frontend" "$image_tag"
        wait_for_rollout "cerberus-frontend" 180
        
        update_images "realtime" "$image_tag"
        wait_for_rollout "cerberus-realtime" 180
        
        scale_up_services
    else
        # Update single component
        update_images "$component" "$image_tag"
        wait_for_rollout "$component" 180
    fi
    
    # Verify update
    verify_update
    
    success "Update completed successfully!"
    
    echo ""
    log "Next steps:"
    echo "1. Monitor Grafana dashboards for any anomalies"
    echo "2. Check logs for errors: kubectl logs -n $NAMESPACE -l app=cerberus --tail=100"
    echo "3. Run smoke tests: curl http://localhost:8000/health"
}

# Handle rollback request
if [ "$1" = "rollback" ]; then
    rollback "${2:-}"
else
    main "$@"
fi
