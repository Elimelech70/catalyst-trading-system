#!/bin/bash
# PNS Heartbeat Runner
# Loads environment and runs heartbeat.py
# Version: 1.0.0
# Last Updated: 2025-12-31

set -e

cd /root/catalyst-trading-system

# Export all variables from .env
set -a
source .env
set +a

# Verify required variables
if [ -z "$RESEARCH_DATABASE_URL" ]; then
    echo "ERROR: RESEARCH_DATABASE_URL not set in .env"
    exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set in .env"
    echo "Please add: ANTHROPIC_API_KEY=sk-ant-xxx to .env"
    exit 1
fi

# Run heartbeat
python3 services/consciousness/heartbeat.py
