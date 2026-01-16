# Name of Application: Catalyst Trading System
# Name of file: services/technical/Dockerfile
# Version: 5.0.2
# Last Updated: 2025-10-16
# Purpose: Docker container for Technical Service using pandas-ta

# REVISION HISTORY:
# v5.0.2 (2025-10-16) - Switched to pandas-ta for better compatibility
# v5.0.1 (2025-10-16) - Added proper TA-Lib C library installation
# v5.0.0 (2025-10-11) - Initial version

# Description of Service:
# Technical Analysis Service providing indicators and calculations
# using pandas for data manipulation and pandas-ta for technical analysis

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r catalyst && useradd -r -g catalyst catalyst

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
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