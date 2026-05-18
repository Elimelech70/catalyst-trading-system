FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Hong_Kong

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY agents/requirements-mcp.txt /tmp/requirements-mcp.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcp.txt

# Copy tools.py for Claude API tool schemas
COPY tools.py /app/tools.py
COPY config/ /app/config/

# Copy cerebellum (neural inference)
COPY cerebellum.py /app/cerebellum.py

# Copy agent-specific code
COPY agents/coordinator/*.py /app/
COPY agents/coordinator/mcp_config.json /app/

CMD ["python", "coordinator.py"]
