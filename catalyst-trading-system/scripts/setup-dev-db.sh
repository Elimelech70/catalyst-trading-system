#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: setup-dev-db.sh
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Setup and initialize local development database

set -e

echo "=========================================="
echo "Catalyst Trading System - Dev DB Setup"
echo "=========================================="

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Start PostgreSQL and Redis containers
echo ""
echo "[1/5] Starting PostgreSQL and Redis containers..."
docker-compose -f docker-compose.dev.yml up -d postgres redis

# Wait for PostgreSQL to be ready
echo ""
echo "[2/5] Waiting for PostgreSQL to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

until docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U catalyst_user -d catalyst_trading_dev > /dev/null 2>&1; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "❌ ERROR: PostgreSQL failed to start after $MAX_RETRIES attempts"
    exit 1
  fi
  echo "   Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

echo "✅ PostgreSQL is ready!"

# Check if database exists
echo ""
echo "[3/5] Checking database status..."
DB_EXISTS=$(docker-compose -f docker-compose.dev.yml exec -T postgres psql -U catalyst_user -tAc "SELECT 1 FROM pg_database WHERE datname='catalyst_trading_dev'" 2>/dev/null || echo "")

if [ "$DB_EXISTS" = "1" ]; then
  echo "✅ Database 'catalyst_trading_dev' already exists"
else
  echo "⚠️  Database 'catalyst_trading_dev' does not exist, will be created by init script"
fi

# Run schema initialization
echo ""
echo "[4/5] Initializing database schema..."
if docker-compose -f docker-compose.dev.yml exec -T postgres psql -U catalyst_user -d catalyst_trading_dev < ./scripts/init-db.sql > /dev/null 2>&1; then
  echo "✅ Schema initialization complete"
else
  echo "⚠️  Schema initialization encountered issues (may be normal if already initialized)"
fi

# Show database info
echo ""
echo "[5/5] Database Summary:"
echo "----------------------------------------"
docker-compose -f docker-compose.dev.yml exec -T postgres psql -U catalyst_user -d catalyst_trading_dev -c "\dt" 2>/dev/null || echo "No tables found (init-db.sql may need schema)"

echo ""
echo "=========================================="
echo "✅ Development database setup complete!"
echo "=========================================="
echo ""
echo "Connection Details:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: catalyst_trading_dev"
echo "  Username: catalyst_user"
echo "  Password: catalyst_dev_password"
echo ""
echo "To connect manually:"
echo "  docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev"
echo ""