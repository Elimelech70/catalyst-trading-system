#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: setup-dev-db.sh
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Setup and initialize local development database

set -e

echo "Setting up Catalyst Trading System Development Database..."

# Start PostgreSQL container if not running
docker-compose -f docker-compose.dev.yml up -d postgres

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker-compose -f docker-compose.dev.yml exec postgres pg_isready -U catalyst_user; do
  sleep 2
done

echo "PostgreSQL is ready!"

# Run schema initialization
echo "Initializing database schema..."
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev -f /docker-entrypoint-initdb.d/init.sql

echo "Database setup complete!"

# Show database info
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev -c "\dt"