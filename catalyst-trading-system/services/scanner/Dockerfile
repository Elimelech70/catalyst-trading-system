# Name of Application: Catalyst Trading System
# Name of file: services/scanner/Dockerfile
# Version: 4.1.0
# Last Updated: 2025-08-31
# Purpose: Docker container for Scanner Service v4.1

# REVISION HISTORY:
# v4.1.0 (2025-08-31) - Updated for v41 scanner service
# - Python 3.10 base with REST API support
# - FastAPI/Uvicorn runtime
# - Optimized dependencies

# Description of Service:
# Container for the scanner service that provides dynamic security scanning
# with news-based filtering and REST API endpoints

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the v41 service code
#COPY scanner-service-v41.py scanner-service.py
COPY *.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/health')" || exit 1

# Run the v41 service
CMD ["python", "-u", "scanner-service.py"]