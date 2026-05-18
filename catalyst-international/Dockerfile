# =============================================================================
# Name of Application: Catalyst Trading System
# Name of file: Dockerfile
# Version: 1.0.0
# Last Updated: 2025-12-09
# Purpose: Docker container for autonomous trading agent
# =============================================================================

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Hong_Kong

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 catalyst && \
    chown -R catalyst:catalyst /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=catalyst:catalyst . .

# Create logs directory
RUN mkdir -p /app/logs && chown -R catalyst:catalyst /app/logs

# Switch to non-root user
USER catalyst

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command - run the eternal loop agent
CMD ["python", "-m", "agent.main"]
