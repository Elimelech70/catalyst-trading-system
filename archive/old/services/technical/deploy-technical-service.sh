#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: deploy-technical-service.sh
# Version: 1.0.0
# Last Updated: 2025-10-11
# Purpose: Build and deploy Technical Service v5.0.0

# REVISION HISTORY:
# v1.0.0 (2025-10-11) - Deploy script for Technical Service

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🚀 Deploying Technical Service v5.0.0"
echo "======================================"
echo ""

# Step 1: Create Dockerfile
echo -e "${YELLOW}Step 1: Creating Dockerfile${NC}"
echo "-----------------------------"

cd services/technical

cat > Dockerfile << 'EOF'
# Name of Application: Catalyst Trading System
# Service: Technical Service
# Version: 5.0.0

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r catalyst && useradd -r -g catalyst catalyst

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY technical-service.py .

# Create logs directory
RUN mkdir -p /app/logs && chown -R catalyst:catalyst /app

# Switch to non-root user
USER catalyst

# Environment variables
ENV SERVICE_PORT=5003
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Run the service
CMD ["python", "technical-service.py"]
EOF

echo "✅ Dockerfile created"

# Step 2: Create requirements.txt
echo ""
echo -e "${YELLOW}Step 2: Creating requirements.txt${NC}"
echo "---------------------------------"

cat > requirements.txt << 'EOF'
# Core
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.4.2

# Database
asyncpg==0.29.0

# HTTP
aiohttp==3.9.0
httpx==0.25.0

# Technical Analysis
numpy==1.24.3
pandas==2.0.3
ta-lib==0.4.28
yfinance==0.2.28

# Utilities
python-dotenv==1.0.0
python-json-logger==2.0.7
EOF

echo "✅ requirements.txt created"

# Step 3: Prepare test data
echo ""
echo -e "${YELLOW}Step 3: Preparing test data${NC}"
echo "---------------------------"

# Ensure we have some test symbols
psql $DATABASE_URL << EOF > /dev/null 2>&1
-- Ensure test symbols exist
SELECT get_or_create_security('AAPL');
SELECT get_or_create_security('MSFT');
SELECT get_or_create_security('GOOGL');
SELECT get_or_create_security('NVDA');
SELECT get_or_create_security('TSLA');

-- Insert some test price data if needed
INSERT INTO trading_history (security_id, time_id, timeframe, open_price, high_price, low_price, close_price, volume)
SELECT 
    get_or_create_security('AAPL'),
    get_or_create_time(NOW() - interval '1 hour' * s),
    '1h',
    180.00 + random() * 5,
    182.00 + random() * 5,
    179.00 + random() * 5,
    180.50 + random() * 5,
    1000000 + random() * 500000
FROM generate_series(1, 20) s
ON CONFLICT DO NOTHING;
EOF

echo "✅ Test data prepared"

# Step 4: Build Docker image
echo ""
echo -e "${YELLOW}Step 4: Building Docker image${NC}"
echo "-----------------------------"

docker build -t technical-service:5.0.0 .
echo -e "${GREEN}✅ Docker image built${NC}"

# Step 5: Stop old container if exists
echo ""
echo -e "${YELLOW}Step 5: Managing containers${NC}"
echo "---------------------------"

docker stop catalyst-technical 2>/dev/null || true
docker rm catalyst-technical 2>/dev/null || true
echo "✅ Old container removed"

# Step 6: Start new container
echo ""
echo -e "${YELLOW}Step 6: Starting Technical Service${NC}"
echo "----------------------------------"

docker run -d \
    --name catalyst-technical \
    -p 5003:5003 \
    -e DATABASE_URL="$DATABASE_URL" \
    -e SERVICE_PORT=5003 \
    --network catalyst-network \
    technical-service:5.0.0

echo "Waiting for service to start..."
sleep 10

# Step 7: Health check
echo ""
echo -e "${YELLOW}Step 7: Verifying service health${NC}"
echo "--------------------------------"

HEALTH=$(curl -s http://localhost:5003/health 2>/dev/null || echo "{}")
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Service is healthy!${NC}"
    echo "$HEALTH" | python3 -m json.tool
else
    echo -e "${RED}❌ Service health check failed${NC}"
    echo "Checking logs..."
    docker logs --tail 30 catalyst-technical
    exit 1
fi

# Step 8: Test endpoints
echo ""
echo -e "${YELLOW}Step 8: Testing endpoints${NC}"
echo "------------------------"

# Test calculate indicators
echo "Testing indicator calculation for AAPL..."
curl -s -X POST http://localhost:5003/api/v1/indicators/calculate \
    -H "Content-Type: application/json" \
    -d '{
        "symbol": "AAPL",
        "timeframe": "5min"
    }' | python3 -m json.tool | head -20

echo ""
echo "======================================"
echo -e "${GREEN}🎉 TECHNICAL SERVICE DEPLOYED!${NC}"
echo "======================================"
echo ""
echo "Service Details:"
echo "  Version: 5.0.0"
echo "  Port: 5003"
echo "  Status: Running"
echo ""
echo "Available Endpoints:"
echo "  POST /api/v1/indicators/calculate - Calculate indicators for symbol"
echo "  GET  /api/v1/indicators/{symbol}/latest - Get latest indicators"
echo "  POST /api/v1/indicators/batch - Calculate for multiple symbols"
echo "  GET  /api/v1/support-resistance/{symbol} - Get support/resistance levels"
echo ""
echo "Test commands:"
echo '  curl -X POST http://localhost:5003/api/v1/indicators/calculate \'
echo '    -H "Content-Type: application/json" \'
echo '    -d "{\"symbol\": \"AAPL\", \"timeframe\": \"5min\"}" | jq'
echo ""
echo "Next service to deploy: Pattern Service"
echo ""

cd ../..
