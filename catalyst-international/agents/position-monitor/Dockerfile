FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Hong_Kong

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install MCP dependencies
COPY agents/requirements-mcp.txt /tmp/requirements-mcp.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcp.txt

# Copy shared source files needed by monitor
COPY brokers/ /app/brokers/
COPY data/ /app/data/
COPY config/ /app/config/
COPY signals.py /app/signals.py
COPY safety.py /app/safety.py

# Copy agent-specific code
COPY agents/position-monitor/*.py /app/

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "mcp_server.py"]
