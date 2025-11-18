#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: health-check.sh
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Check health of all local development services

set -e

echo "=========================================="
echo "Catalyst Trading System - Health Check"
echo "=========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Determine which compose file to use
if [ -f "docker-compose.dev.yml" ] && docker-compose -f docker-compose.dev.yml ps | grep -q "catalyst.*dev"; then
  COMPOSE_FILE="docker-compose.dev.yml"
  ENV="DEVELOPMENT"
else
  COMPOSE_FILE="docker-compose.yml"
  ENV="PRODUCTION"
fi

echo ""
echo "Environment: $ENV"
echo "Compose File: $COMPOSE_FILE"
echo ""

# Check infrastructure services
echo "Infrastructure Services:"
echo "----------------------------------------"

# Check PostgreSQL
if [ "$COMPOSE_FILE" = "docker-compose.dev.yml" ]; then
  echo -n "PostgreSQL (Local): "
  if docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U catalyst_user > /dev/null 2>&1; then
    echo -e "${GREEN}✅ HEALTHY${NC}"
  else
    echo -e "${RED}❌ UNHEALTHY${NC}"
  fi
else
  echo "PostgreSQL (Cloud): ⚠️  Skipped (using DigitalOcean managed database)"
fi

# Check Redis
echo -n "Redis Cache: "
if docker-compose -f $COMPOSE_FILE exec -T redis redis-cli ping > /dev/null 2>&1; then
  echo -e "${GREEN}✅ HEALTHY${NC}"
else
  echo -e "${RED}❌ UNHEALTHY${NC}"
fi

echo ""
echo "Application Services:"
echo "----------------------------------------"

# Service endpoints to check
services=(
  "Orchestration:5000"
  "Scanner:5001"
  "Pattern:5002"
  "Technical:5003"
  "Risk Manager:5004"
  "Trading:5005"
  "Workflow:5006"
  "News:5008"
  "Reporting:5009"
)

healthy_count=0
total_count=${#services[@]}

for service_info in "${services[@]}"; do
  IFS=':' read -r name port <<< "$service_info"

  # Try to connect to the service
  response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:$port/health 2>/dev/null || echo "000")

  printf "%-20s (port %s): " "$name" "$port"

  if [ "$response" = "200" ]; then
    echo -e "${GREEN}✅ HEALTHY${NC}"
    healthy_count=$((healthy_count + 1))
  elif [ "$response" = "000" ]; then
    echo -e "${RED}❌ NOT RESPONDING${NC}"
  else
    echo -e "${YELLOW}⚠️  DEGRADED (HTTP $response)${NC}"
  fi
done

echo ""
echo "Container Status:"
echo "----------------------------------------"
docker-compose -f $COMPOSE_FILE ps

echo ""
echo "=========================================="
echo "Summary:"
echo "=========================================="
echo "Services Healthy: $healthy_count / $total_count"

if [ $healthy_count -eq $total_count ]; then
  echo -e "${GREEN}✅ All services are healthy!${NC}"
  exit 0
elif [ $healthy_count -gt 0 ]; then
  echo -e "${YELLOW}⚠️  Some services are unhealthy${NC}"
  exit 1
else
  echo -e "${RED}❌ All services are down${NC}"
  exit 2
fi
