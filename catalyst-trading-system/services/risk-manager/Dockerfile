# ============================================================================
# Dockerfile
# ============================================================================
# File: services/risk-manager/Dockerfile

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY risk-manager-service.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; r = requests.get('http://localhost:5004/health', timeout=5); exit(0 if r.status_code == 200 else 1)"

# Run the service
CMD ["python", "-u", "risk-manager-service.py"]