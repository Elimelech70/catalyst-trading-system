#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: diagnose_services.sh
# Version: 1.0.0
# Last Updated: 2025-09-29
# Purpose: Diagnose service health issues
#
# REVISION HISTORY:
# v1.0.0 (2025-09-29) - Initial diagnostic script
# - Check which containers are running
# - Test health endpoints
# - Show container logs for failed services
#
# Description of Service:
# Comprehensive diagnostic tool to identify which services are failing
# and why the orchestration service reports 0/7 healthy services

echo "🎩 DevGenius Diagnostic Report - Catalyst Trading System"
echo "========================================================"
echo ""

echo "📊 STEP 1: Docker Container Status"
echo "-----------------------------------"
docker ps --filter "name=catalyst" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo "📊 STEP 2: Check All Expected Containers"
echo "-----------------------------------------"
expected_containers=(
    "catalyst-orchestration"
    "catalyst-scanner"
    "catalyst-pattern"
    "catalyst-technical"
    "catalyst-trading"
    "catalyst-news"
    "catalyst-reporting"
    "catalyst-redis"
)

for container in "${expected_containers[@]}"; do
    if docker ps --filter "name=$container" --format "{{.Names}}" | grep -q "$container"; then
        echo "✅ $container is running"
    else
        echo "❌ $container is NOT running"
        if docker ps -a --filter "name=$container" --format "{{.Names}}" | grep -q "$container"; then
            echo "   Container exists but is stopped. Status:"
            docker ps -a --filter "name=$container" --format "   Status: {{.Status}}"
            echo "   Last 20 log lines:"
            docker logs --tail 20 "$container" 2>&1 | sed 's/^/   /'
        else
            echo "   Container does not exist - needs to be created"
        fi
        echo ""
    fi
done

echo ""
echo "📊 STEP 3: Health Endpoint Tests"
echo "---------------------------------"

services=(
    "orchestration:5000"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "trading:5005"
    "news:5008"
    "reporting:5009"
)

for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    
    echo -n "Testing $name ($port)... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" 2>&1)
    
    if [ "$response" = "200" ]; then
        echo "✅ HEALTHY (HTTP 200)"
        curl -s "http://localhost:$port/health" | jq '.' 2>/dev/null || echo ""
    elif [ "$response" = "000" ]; then
        echo "❌ NOT RESPONDING (Connection refused)"
    else
        echo "❌ UNHEALTHY (HTTP $response)"
    fi
    echo ""
done

echo ""
echo "📊 STEP 4: Check Orchestration Service Logs"
echo "--------------------------------------------"
echo "Last 50 lines from orchestration service:"
docker logs catalyst-orchestration --tail 50 2>&1
echo ""

echo ""
echo "📊 STEP 5: Network Connectivity"
echo "--------------------------------"
echo "Checking if containers can communicate..."
docker exec catalyst-orchestration ping -c 2 catalyst-scanner 2>&1 || echo "Cannot ping scanner"
echo ""

echo ""
echo "📊 STEP 6: Environment Variables Check"
echo "---------------------------------------"
echo "Checking critical environment variables in orchestration:"
docker exec catalyst-orchestration env | grep -E "(DATABASE_URL|REDIS_URL|SCANNER_URL|PATTERN_URL)" || echo "Environment variables not set"
echo ""

echo ""
echo "🎯 SUMMARY & RECOMMENDATIONS"
echo "=============================="
echo ""
echo "Based on the diagnostics above:"
echo "1. Count how many services are actually running"
echo "2. For any stopped services, check their logs (shown above)"
echo "3. Common issues to look for:"
echo "   - Missing environment variables"
echo "   - Database connection failures"
echo "   - Port conflicts"
echo "   - Container crashed on startup"
echo ""
echo "Next steps:"
echo "   ./diagnose_services.sh > diagnostic_report.txt"
echo "   Review the report and focus on services that are NOT RESPONDING"
