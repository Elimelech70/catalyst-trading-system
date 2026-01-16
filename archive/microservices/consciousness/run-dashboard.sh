#!/bin/bash
# Consciousness Web Dashboard Runner
# Version: 1.0.0
# Last Updated: 2025-12-31

set -e

cd /root/catalyst-trading-system

# Export all variables from .env
set -a
source .env
set +a

# Run dashboard
exec python3 -m uvicorn services.consciousness.web_dashboard:app --host 0.0.0.0 --port 8088
