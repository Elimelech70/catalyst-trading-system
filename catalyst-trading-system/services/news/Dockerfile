# Name of Application: Catalyst Trading System
# Service: news
# Version: 1.0.0

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=news

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:PORT/health')" || exit 1

# Run the service
CMD ["python", "-u", "news-service.py"]
