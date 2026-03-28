FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc curl sqlite3 libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY hippocampus/requirements.txt /app/hippocampus/requirements.txt
RUN pip install --no-cache-dir -r /app/hippocampus/requirements.txt

COPY shared/ /app/shared/
COPY hippocampus/ /app/hippocampus/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sqlite3; c=sqlite3.connect('/var/lib/catalyst/hippocampus/memory.db'); c.execute('SELECT 1'); print('OK')" || exit 1

CMD ["python", "-u", "hippocampus/hippocampus.py"]
