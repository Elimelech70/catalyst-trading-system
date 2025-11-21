#!/bin/bash
# Catalyst Trading System - Service Status Checker
# Quick health check for all services

echo "============================================"
echo "  Catalyst Trading System Status Check"
echo "============================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check services
echo "📊 Services Status:"
echo ""

services=(
  "5001:Scanner"
  "5002:News"
  "5003:Technical"
  "5004:Risk Manager"
  "5005:Trading"
  "5006:Workflow"
)

all_healthy=true

for service in "${services[@]}"; do
  port="${service%%:*}"
  name="${service##*:}"

  response=$(curl -s http://localhost:$port/health 2>/dev/null)

  if [ $? -eq 0 ] && [ -n "$response" ]; then
    status=$(echo "$response" | jq -r '.status // "unknown"')
    if [ "$status" = "healthy" ]; then
      printf "  ✓ Port %s %-20s ${GREEN}%s${NC}\n" "$port" "[$name]" "$status"
    else
      printf "  ✗ Port %s %-20s ${YELLOW}%s${NC}\n" "$port" "[$name]" "$status"
      all_healthy=false
    fi
  else
    printf "  ✗ Port %s %-20s ${RED}%s${NC}\n" "$port" "[$name]" "NOT RESPONDING"
    all_healthy=false
  fi
done

echo ""
echo "🗄️  Infrastructure:"
echo ""

# Check Docker containers
docker_status=$(docker-compose ps 2>/dev/null)
if [ $? -eq 0 ]; then
  echo "$docker_status" | grep -E "(postgres|redis)" | while read line; do
    if echo "$line" | grep -q "Up.*healthy"; then
      echo "  ✓ $line"
    else
      echo "  ✗ $line"
    fi
  done
else
  echo "  ⚠️  Docker Compose not available"
fi

echo ""
echo "⏰ Cron Status:"
echo ""

# Check cron service
if sudo service cron status >/dev/null 2>&1; then
  echo "  ✓ Cron service is running"
else
  echo "  ✗ Cron service is NOT running"
  all_healthy=false
fi

# Check if crontab is installed
if crontab -l >/dev/null 2>&1; then
  job_count=$(crontab -l | grep -v '^#' | grep -v '^$' | wc -l)
  echo "  ✓ Crontab installed ($job_count jobs)"
else
  echo "  ⚠️  No crontab configured"
fi

echo ""
echo "============================================"

if $all_healthy; then
  echo -e "${GREEN}✓ All services are healthy${NC}"
else
  echo -e "${YELLOW}⚠️  Some services need attention${NC}"
fi

echo "============================================"
echo ""
echo "Quick Commands:"
echo "  View logs:     tail -f /tmp/catalyst-cron/health-\$(date +%Y%m%d).log"
echo "  Trigger scan:  curl -X POST http://localhost:5001/api/v1/scan"
echo "  View services: ps aux | grep -E 'service.py' | grep -v grep"
echo ""
