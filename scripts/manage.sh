################################################################################
# FILE 2: docker/scripts/manage.sh (CORRECTED)
# Save this to docker/scripts/manage.sh and chmod +x
################################################################################

#!/bin/bash
# Catalyst Trading System MCP - Management Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$PROJECT_ROOT"

# Print header
print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Catalyst Trading System MCP Manager          ║${NC}"
    echo -e "${BLUE}║     WebSocket Transport | Port 5000              ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
}

# Check prerequisites
check_env() {
    if [ ! -f ".env" ]; then
        echo -e "${RED}Error: .env file not found!${NC}"
        exit 1
    fi
    
    # Check if we can read the database URL
    if grep -q "DATABASE_URL=" .env && ! grep -q "YOUR_PASSWORD" .env; then
        echo -e "${GREEN}✓${NC} Environment configuration found"
    else
        echo -e "${RED}Error: DATABASE_URL not configured in .env${NC}"
        exit 1
    fi
}

# Build images
build() {
    echo -e "${YELLOW}Building Docker images...${NC}"
    docker-compose build --no-cache
    echo -e "${GREEN}✓ All images built successfully${NC}"
}

# Start services
start() {
    check_env
    echo -e "${YELLOW}Starting MCP services...${NC}"
    
    # Start Redis first
    echo "Starting Redis..."
    docker-compose up -d redis
    sleep 5
    
    # Start orchestration service
    echo "Starting Orchestration service (port 5000)..."
    docker-compose up -d orchestration-service
    sleep 5
    
    # Start data collection services
    echo "Starting News and Scanner services..."
    docker-compose up -d news-service scanner-service
    sleep 5
    
    # Start analysis services
    echo "Starting Pattern and Technical services..."
    docker-compose up -d pattern-service technical-service
    sleep 5
    
    # Start trading and reporting
    echo "Starting Trading and Reporting services..."
    docker-compose up -d trading-service reporting-service
    
    echo -e "${GREEN}✓ All MCP services started${NC}"
    echo -e "${YELLOW}Note: Services connect to DigitalOcean managed database${NC}"
}

# Stop services
stop() {
    echo -e "${YELLOW}Stopping all services...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ All services stopped${NC}"
}

# Restart services
restart() {
    echo -e "${YELLOW}Restarting services...${NC}"
    docker-compose restart
    echo -e "${GREEN}✓ Services restarted${NC}"
}

# Check health
health() {
    echo -e "${YELLOW}Checking service health...${NC}"
    echo ""
    
    # Check Redis
    echo -n "Redis..............."
    if docker-compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" ping &>/dev/null; then
        echo -e "${GREEN}HEALTHY${NC}"
    else
        echo -e "${RED}UNHEALTHY${NC}"
    fi
    
    # MCP Services with correct ports
    declare -A services=(
        ["orchestration"]="5000"
        ["news"]="5008"
        ["scanner"]="5001"
        ["pattern"]="5002"
        ["technical"]="5003"
        ["trading"]="5005"
        ["reporting"]="5009"
    )
    
    for service in "${!services[@]}"; do
        port="${services[$service]}"
        printf "%-20s" "${service^} Service..."
        
        if curl -sf "http://localhost:$port/health" &>/dev/null; then
            echo -e "${GREEN}HEALTHY${NC}"
        else
            echo -e "${RED}UNHEALTHY${NC}"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Database: Check DigitalOcean dashboard for status${NC}"
    echo -e "${YELLOW}MCP Transport: WebSocket (port 5000)${NC}"
}

# View logs
logs() {
    service=$1
    if [ -z "$service" ]; then
        docker-compose logs -f --tail=100
    else
        docker-compose logs -f --tail=100 "$service-service"
    fi
}

# Show status
status() {
    echo -e "${YELLOW}Service Status:${NC}"
    docker-compose ps
    echo ""
    echo -e "${YELLOW}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | grep catalyst || true
}

# Quick info
info() {
    print_header
    echo ""
    echo -e "${YELLOW}Configuration:${NC}"
    echo "  Database: DigitalOcean Managed PostgreSQL"
    echo "  Redis: Local container with password"
    echo "  MCP Transport: WebSocket"
    echo "  Orchestration Port: 5000"
    echo ""
    echo -e "${YELLOW}Service Endpoints:${NC}"
    echo "  Orchestration: http://localhost:5000 (ws://localhost:5000)"
    echo "  News Service: http://localhost:5008"
    echo "  Scanner: http://localhost:5001"
    echo "  Pattern: http://localhost:5002"
    echo "  Technical: http://localhost:5003"
    echo "  Trading: http://localhost:5005"
    echo "  Reporting: http://localhost:5009"
    echo ""
    echo -e "${YELLOW}Claude Desktop MCP:${NC}"
    echo "  Connect to: ws://localhost:5000/mcp"
}

# Main menu
case "$1" in
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    health)
        health
        ;;
    logs)
        logs "$2"
        ;;
    status)
        status
        ;;
    info)
        info
        ;;
    *)
        print_header
        echo ""
        echo "Usage: $0 {build|start|stop|restart|health|status|info|logs}"
        echo ""
        echo "Commands:"
        echo "  build    - Build Docker images"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  health   - Check service health"
        echo "  status   - Show service status"
        echo "  info     - Show configuration info"
        echo "  logs     - View logs (optional: service name)"
        echo ""
        echo "Examples:"
        echo "  $0 start              # Start all services"
        echo "  $0 logs trading       # View trading service logs"
        exit 1
        ;;
esac

################################################################################
# CORRECTED PORT ASSIGNMENTS
################################################################################
# 
# Service              Port
# -------------------- -----
# Orchestration        5000  ← Fixed!
# News                 5008
# Scanner              5001
# Pattern              5002
# Technical            5003
# Trading              5005
# Reporting            5009  ← No conflict!
# Redis                6379
#
# Claude Desktop connects to: ws://localhost:5000/mcp
#
################################################################################