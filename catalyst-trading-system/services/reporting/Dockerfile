# Name of Application: Catalyst Trading System
# Name of file: services/reporting/Dockerfile
# Version: 4.1.1
# Last Updated: 2025-09-20
# Purpose: Docker container for Reporting Service - Fixed for single-file implementation

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code (single file implementation)
COPY *.py ./

# Create placeholder directories that the service might expect
RUN mkdir -p templates reports charts static logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_MODE=production
ENV SERVICE_PORT=5009

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5009/health')" || exit 1

# Run the service
CMD ["python", "-u", "reporting-service.py"]