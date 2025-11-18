# Name of Application: Catalyst Trading System
# Name of file: services/orchestration/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-08-31
# Purpose: Docker container for Orchestration Service v4.1

# REVISION HISTORY:
# v4.1.0 (2025-08-31) - Updated for v41 orchestration service
# - MCP protocol support
# - HTTP client for service coordination
# - Enhanced async capabilities

# Description of Service:
# Container for the orchestration service that coordinates all trading
# system components via MCP protocol and REST APIs

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install the Anthropic MCP Python SDK
RUN pip install "mcp[cli]"

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the v41 service code
# COPY orchestration-service-v41.py orchestration-service.py
COPY *.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5000

# Health check using MCP protocol
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the v41 MCP service
CMD ["python", "-u", "orchestration-service.py"]