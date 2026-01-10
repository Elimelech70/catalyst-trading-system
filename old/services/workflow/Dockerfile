# Name of Application: Catalyst Trading System
# Name of file: Dockerfile
# Service: Workflow Coordinator
# Version: 1.0.0
# Purpose: Docker image for workflow coordination service

FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY workflow-coordinator.py .

# Copy common utilities
COPY common/ ./common/

# Create non-root user for security
RUN useradd -m -u 1000 catalyst && \
    chown -R catalyst:catalyst /app

USER catalyst

# Expose service port
EXPOSE 5006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5006/health')" || exit 1

# Run the service
CMD ["python", "-u", "workflow-coordinator.py"]
