#!/bin/bash
# Cerberus Health Check Script
# Daily cron job for system health verification
# RTO: 15 minutes

set -euo pipefail

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
EMAIL_RECIPIENT="${EMAIL_RECIPIENT:-ops-team@example.com}"
LOG_FILE="/var/log/cerberus/health-check.log"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local message="$1"
    local severity="${2:-warning}"
    
    log "ALERT: $message"
    
    # Send to Slack
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H 'Content-type: application/json' \
            -d "{\"text\":\"[Cerberus $severity] $message\"}" || true
    fi
    
    # Send to webhook
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -s -X POST "$ALERT_WEBHOOK" \
            -H 'Content-type: application/json' \
            -d "{\"severity\":\"$severity\",\"message\":\"$message\",\"timestamp\":\"$(date -Iseconds)\"}" || true
    fi
    
    # Send email if critical
    if [ "$severity" = "critical" ] && [ -n "$EMAIL_RECIPIENT" ]; then
        echo "$message" | mail -s "[Cerberus CRITICAL] $message" "$EMAIL_RECIPIENT" || true
    fi
}

check_api() {
    local endpoint="$1"
    local expected_status="${2:-200}"
    local timeout="${3:-10}"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time "$timeout" \
        "$API_URL$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $endpoint (HTTP $response)"
        return 0
    else
        echo -e "${RED}✗${NC} $endpoint (HTTP $response, expected $expected_status)"
        return 1
    fi
}

check_database() {
    log "Checking database connection..."
    
    if command -v psql &> /dev/null; then
        result=$(PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST:-localhost}" \
            -U "${DB_USER:-postgres}" -d cerberus \
            -t -c "SELECT 1;" 2>/dev/null || echo "FAILED")
        
        if [ "$result" = "1" ]; then
            echo -e "${GREEN}✓${NC} Database connection"
            return 0
        else
            echo -e "${RED}✗${NC} Database connection failed"
            return 1
        fi
    else
        # Fallback to API check
        check_api "/health/database" "200"
    fi
}

check_redis() {
    log "Checking Redis connection..."
    
    if command -v redis-cli &> /dev/null; then
        result=$(redis-cli -h "${REDIS_HOST:-localhost}" ping 2>/dev/null || echo "FAILED")
        
        if [ "$result" = "PONG" ]; then
            echo -e "${GREEN}✓${NC} Redis connection"
            return 0
        else
            echo -e "${RED}✗${NC} Redis connection failed: $result"
            return 1
        fi
    else
        check_api "/health/cache" "200"
    fi
}

check_disk_space() {
    log "Checking disk space..."
    
    threshold="${DISK_THRESHOLD:-80}"
    usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$usage" -gt "$threshold" ]; then
        echo -e "${RED}✗${NC} Disk usage at ${usage}%"
        send_alert "Disk usage at ${usage}%" "warning"
        return 1
    else
        echo -e "${GREEN}✓${NC} Disk usage at ${usage}%"
        return 0
    fi
}

check_memory() {
    log "Checking memory..."
    
    threshold="${MEMORY_THRESHOLD:-80}"
    usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    
    if [ "$usage" -gt "$threshold" ]; then
        echo -e "${YELLOW}⚠${NC} Memory usage at ${usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} Memory usage at ${usage}%"
        return 0
    fi
}

check_cpu() {
    log "Checking CPU load..."
    
    threshold="${CPU_THRESHOLD:-80}"
    usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    
    if [ "$(echo "$usage > $threshold" | bc)" -eq 1 ]; then
        echo -e "${YELLOW}⚠${NC} CPU load at ${usage}%"
        return 1
    else
        echo -e "${GREEN}✓${NC} CPU load at ${usage}%"
        return 0
    fi
}

check_docker_containers() {
    log "Checking Docker containers..."
    
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}⚠${NC} Docker not available"
        return 0
    fi
    
    # Check for unhealthy containers
    unhealthy=$(docker ps --filter "health=unhealthy" -q 2>/dev/null | wc -l)
    
    if [ "$unhealthy" -gt 0 ]; then
        echo -e "${RED}✗${NC} $unhealthy unhealthy container(s)"
        send_alert "$unhealthy unhealthy Docker containers" "warning"
        return 1
    fi
    
    # Check for exited containers
    exited=$(docker ps -a --filter "status=exited" -q 2>/dev/null | wc -l)
    
    if [ "$exited" -gt 5 ]; then
        echo -e "${YELLOW}⚠${NC} $exited exited containers"
    fi
    
    echo -e "${GREEN}✓${NC} Containers healthy"
    return 0
}

check_kubernetes_pods() {
    log "Checking Kubernetes pods..."
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${YELLOW}⚠${NC} kubectl not available"
        return 0
    fi
    
    # Check for non-ready pods
    not_ready=$(kubectl get pods -n cerberus \
        --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l)
    
    if [ "$not_ready" -gt 0 ]; then
        echo -e "${RED}✗${NC} $not_ready pods not ready"
        send_alert "$not_ready Kubernetes pods not ready" "warning"
        return 1
    fi
    
    echo -e "${GREEN}✓${NC} All pods running"
    return 0
}

check_ssl_cert() {
    log "Checking SSL certificate..."
    
    domain="${DOMAIN:-localhost}"
    port="${SSL_PORT:-443}"
    
    expiry=$(echo | openssl s_client -servername "$domain" -connect "$domain:$port" 2>/dev/null | \
        openssl x509 -noout -enddate 2>/dev/null | sed 's/notAfter=//')
    
    if [ -z "$expiry" ]; then
        echo -e "${YELLOW}⚠${NC} Could not check SSL certificate"
        return 0
    fi
    
    days_left=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
    
    if [ "$days_left" -lt 30 ]; then
        echo -e "${RED}✗${NC} SSL certificate expires in $days_left days"
        send_alert "SSL certificate expires in $days_left days" "critical"
        return 1
    elif [ "$days_left" -lt 60 ]; then
        echo -e "${YELLOW}⚠${NC} SSL certificate expires in $days_left days"
        return 1
    else
        echo -e "${GREEN}✓${NC} SSL certificate valid ($days_left days)"
        return 0
    fi
}

check_backup_status() {
    log "Checking backup status..."
    
    # Check if last backup is less than 24 hours old
    last_backup=$(ls -la /var/backups/cerberus/*.dump 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
    
    if [ -z "$last_backup" ]; then
        echo -e "${YELLOW}⚠${NC} No backups found"
        return 1
    fi
    
    echo -e "${GREEN}✓${NC} Last backup: $last_backup"
    return 0
}

generate_report() {
    local status="$1"
    
    report="Cerberus Health Check Report
=================================
Date: $(date '+%Y-%m-%d %H:%M:%S')
Status: $status

System Information:
------------------
Hostname: $(hostname)
Uptime: $(uptime -p 2>/dev/null || echo "N/A")

Disk Usage:
$(df -h / | tail -1)

Memory Usage:
$(free -h)

Top Processes:
$(top -bn1 | head -5)

API Health:
$(check_api /health 2>&1)

Database Status:
$(check_database 2>&1)

Redis Status:
$(check_redis 2>&1)
"
    
    echo "$report" | tee -a "$LOG_FILE"
}

# Main execution
main() {
    log "Starting health check..."
    
    echo ""
    echo "Cerberus Health Check"
    echo "====================="
    echo ""
    
    all_checks_passed=true
    
    # Run checks
    echo "--- API Endpoints ---"
    check_api "/health" "200" || all_checks_passed=false
    check_api "/health/ready" "200" || all_checks_passed=false
    echo ""
    
    echo "--- Infrastructure ---"
    check_database || all_checks_passed=false
    check_redis || all_checks_passed=false
    echo ""
    
    echo "--- System Resources ---"
    check_disk_space || all_checks_passed=false
    check_memory || all_checks_passed=false
    check_cpu || all_checks_passed=false
    echo ""
    
    echo "--- Container Status ---"
    check_docker_containers || all_checks_passed=false
    check_kubernetes_pods || all_checks_passed=false
    echo ""
    
    echo "--- Security ---"
    check_ssl_cert || all_checks_passed=false
    echo ""
    
    echo "--- Backups ---"
    check_backup_status || all_checks_passed=false
    echo ""
    
    # Generate report
    if [ "$all_checks_passed" = true ]; then
        echo -e "${GREEN}All checks passed!${NC}"
        generate_report "HEALTHY"
        exit 0
    else
        echo -e "${RED}Some checks failed!${NC}"
        generate_report "DEGRADED"
        send_alert "Health check found issues - see logs" "warning"
        exit 1
    fi
}

# Run main
main "$@"
