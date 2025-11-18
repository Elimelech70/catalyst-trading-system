#!/bin/bash
# Catalyst Trading System - Production Manager
# Handles market hours automation, health checks, and maintenance

set -euo pipefail

# Configuration
COMPOSE_FILE="/root/catalyst-trading-mcp/docker-compose.yml"
LOG_DIR="/var/log/catalyst"
BACKUP_DIR="/backups/catalyst"
ALERT_EMAIL="${ALERT_EMAIL:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/production-manager.log"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
    log "SUCCESS: $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log "ERROR: $1"
}

print_status() {
    echo -e "${YELLOW}[INFO]${NC} $1"
    log "STATUS: $1"
}

# Check if we're in market hours (EST)
is_market_hours() {
    hour=$(TZ='America/New_York' date +%H)
    day=$(TZ='America/New_York' date +%u)  # 1=Monday, 7=Sunday

    # Monday-Friday (1-5), 9:30 AM - 4:00 PM EST
    if [ "$day" -le 5 ] && [ "$hour" -ge 9 ] && [ "$hour" -lt 16 ]; then
        return 0  # True
    else
        return 1  # False
    fi
}

# Start all services
start_system() {
    print_status "Starting Catalyst Trading System..."

    cd /root/catalyst-trading-mcp || exit 1

    # Start services
    docker-compose -f "$COMPOSE_FILE" up -d

    # Wait for services to be healthy
    sleep 30

    # Check health
    if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        print_success "All services started successfully"
    else
        print_error "Service health check failed"
        return 1
    fi
}

# Stop all services gracefully
stop_system() {
    print_status "Stopping Catalyst Trading System..."

    cd /root/catalyst-trading-mcp || exit 1

    docker-compose -f "$COMPOSE_FILE" down

    print_success "System stopped"
}

# Service health check
status_check() {
    print_status "Checking service health..."

    services=(
        "orchestration:5000"
        "workflow:5006"
        "scanner:5001"
        "pattern:5002"
        "technical:5003"
        "risk-manager:5004"
        "trading:5005"
        "news:5008"
        "reporting:5009"
    )

    failed=0

    for service in "${services[@]}"; do
        name="${service%%:*}"
        port="${service##*:}"

        if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
            print_success "$name service healthy"
        else
            print_error "$name service unhealthy"
            failed=$((failed + 1))
        fi
    done

    if [ $failed -eq 0 ]; then
        print_success "All services healthy"
        return 0
    else
        print_error "$failed services unhealthy"
        return 1
    fi
}

# Database backup
backup_database() {
    print_status "Creating database backup..."

    backup_file="$BACKUP_DIR/catalyst_backup_$(date +%Y%m%d_%H%M%S).sql"

    # Extract database URL components
    # Format: postgresql://user:pass@host:port/dbname
    if [ -f /root/catalyst-trading-mcp/.env ]; then
        source /root/catalyst-trading-mcp/.env

        # Use pg_dump with connection string
        if pg_dump "$DATABASE_URL" -f "$backup_file" 2>/dev/null; then

            print_success "Database backup created: $backup_file"

            # Compress backup
            gzip "$backup_file"
            print_success "Backup compressed: ${backup_file}.gz"

            # Clean old backups (keep last 30 days)
            find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

            return 0
        else
            print_error "Database backup failed"
            return 1
        fi
    else
        print_error ".env file not found"
        return 1
    fi
}

# Quick health check for cron
quick_health_check() {
    if ! curl -sf http://localhost:5000/health >/dev/null 2>&1; then
        print_error "Health check failed - attempting restart"

        # Log to separate alert file
        echo "[$(date)] ALERT: Health check failed, restarting system" >> "$LOG_DIR/alerts.log"

        # Attempt restart
        docker-compose -f "$COMPOSE_FILE" restart

        # Wait and recheck
        sleep 30

        if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
            print_success "System recovered after restart"
        else
            print_error "System still unhealthy after restart"

            # Send email alert if configured
            if [ -n "$ALERT_EMAIL" ]; then
                echo "Catalyst Trading System health check failed at $(date). Manual intervention required." | \
                    mail -s "CRITICAL: Catalyst System Down" "$ALERT_EMAIL"
            fi
        fi
    fi
}

# Market open notification
market_open_workflow() {
    print_status "Market open - Starting trading workflow..."

    # Trigger workflow via REST API
    response=$(curl -sf -X POST http://localhost:5006/api/v1/workflow/start \
        -H "Content-Type: application/json" \
        -d '{"mode": "normal", "max_positions": 5, "risk_per_trade": 0.01}')

    if [ $? -eq 0 ]; then
        print_success "Trading workflow started"
        log "Workflow response: $response"
    else
        print_error "Failed to start trading workflow"
    fi
}

# Market close operations
market_close_workflow() {
    print_status "Market close - Running end-of-day operations..."

    # Trigger end-of-day report
    curl -sf -X POST http://localhost:5009/api/v1/reports/daily >/dev/null 2>&1 || true

    print_success "End-of-day operations complete"
}

# Weekly maintenance
weekly_maintenance() {
    print_status "Running weekly maintenance..."

    # Backup database
    backup_database

    # Clean old logs (keep 30 days)
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete

    # Docker cleanup
    docker system prune -f

    # Restart services for fresh start
    print_status "Restarting services..."
    stop_system
    sleep 30
    start_system

    print_success "Weekly maintenance completed"
}

# Log rotation
rotate_logs() {
    print_status "Rotating logs..."

    # Find logs larger than 100MB
    find "$LOG_DIR" -name "*.log" -size +100M -exec gzip {} \;

    # Archive old compressed logs
    find "$LOG_DIR" -name "*.log.gz" -mtime +7 -exec mv {} "$LOG_DIR/archive/" \; 2>/dev/null || true

    print_success "Log rotation complete"
}

# Main command handler
case "${1:-}" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        stop_system
        sleep 10
        start_system
        ;;
    status)
        status_check
        ;;
    backup)
        backup_database
        ;;
    health)
        quick_health_check
        ;;
    market-open)
        market_open_workflow
        ;;
    market-close)
        market_close_workflow
        ;;
    weekly-maintenance)
        weekly_maintenance
        ;;
    rotate-logs)
        rotate_logs
        ;;
    *)
        echo "Catalyst Trading System - Production Manager"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start               - Start all services"
        echo "  stop                - Stop all services"
        echo "  restart             - Restart all services"
        echo "  status              - Check service health"
        echo "  backup              - Create database backup"
        echo "  health              - Quick health check (for cron)"
        echo "  market-open         - Market open workflow"
        echo "  market-close        - Market close workflow"
        echo "  weekly-maintenance  - Weekly maintenance tasks"
        echo "  rotate-logs         - Rotate and compress logs"
        exit 1
        ;;
esac