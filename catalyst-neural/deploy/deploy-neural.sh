#!/bin/bash
# Deploy CatalystNet neural cortex to the US droplet
# Usage: ./deploy-neural.sh [model.onnx]

set -euo pipefail

DROPLET="root@68.183.177.11"
SSH_KEY="$HOME/.ssh/Catalyst-Linux-Claude"
SSH="ssh -i $SSH_KEY $DROPLET"
SCP="scp -i $SSH_KEY"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$(dirname "$SCRIPT_DIR")/models"
AGENT_DIR="/root/catalyst-agent"

# Find models
CANDLE_MODEL="${1:-$MODELS_DIR/candle_model.onnx}"
FUSED_MODEL="${2:-$MODELS_DIR/catalyst_net.onnx}"

HAVE_CANDLE=false
HAVE_FUSED=false

if [ -f "$CANDLE_MODEL" ]; then
    HAVE_CANDLE=true
fi
if [ -f "$FUSED_MODEL" ]; then
    HAVE_FUSED=true
fi

if [ "$HAVE_CANDLE" = false ] && [ "$HAVE_FUSED" = false ]; then
    echo "ERROR: No models found."
    echo "  Candle: $CANDLE_MODEL"
    echo "  Fused:  $FUSED_MODEL"
    echo "Run: python run.py train candle && python run.py export candle <checkpoint.pt>"
    exit 1
fi

echo "=========================================="
echo "Deploying Neural Cortex to Droplet"
echo "=========================================="
if [ "$HAVE_CANDLE" = true ]; then
    echo "Candle:  $CANDLE_MODEL ($(du -h "$CANDLE_MODEL" | cut -f1))"
fi
if [ "$HAVE_FUSED" = true ]; then
    echo "Fused:   $FUSED_MODEL ($(du -h "$FUSED_MODEL" | cut -f1))"
fi
echo "Droplet: $DROPLET"
echo ""

# 1. Create directories on droplet
echo ">>> Creating directories..."
$SSH "mkdir -p $AGENT_DIR/neural/model"

# 2. Copy neural service files
echo ">>> Copying neural cortex files..."
$SCP "$SCRIPT_DIR/neural/cortex.py" "$DROPLET:$AGENT_DIR/neural/cortex.py"
$SCP "$SCRIPT_DIR/neural/requirements.txt" "$DROPLET:$AGENT_DIR/neural/requirements.txt"
$SCP "$SCRIPT_DIR/neural/Dockerfile" "$DROPLET:$AGENT_DIR/neural/Dockerfile"

# 3. Copy ONNX models (and external data files if present)
echo ">>> Copying ONNX models..."
if [ "$HAVE_CANDLE" = true ]; then
    echo "    Candle model..."
    $SCP "$CANDLE_MODEL" "$DROPLET:$AGENT_DIR/neural/model/candle_model.onnx"
    if [ -f "${CANDLE_MODEL}.data" ]; then
        $SCP "${CANDLE_MODEL}.data" "$DROPLET:$AGENT_DIR/neural/model/candle_model.onnx.data"
    fi
fi
if [ "$HAVE_FUSED" = true ]; then
    echo "    Fused model..."
    $SCP "$FUSED_MODEL" "$DROPLET:$AGENT_DIR/neural/model/catalyst_net.onnx"
    if [ -f "${FUSED_MODEL}.data" ]; then
        $SCP "${FUSED_MODEL}.data" "$DROPLET:$AGENT_DIR/neural/model/catalyst_net.onnx.data"
    fi
fi

# 4. Add NEURAL component to shared/models.py if not present
echo ">>> Updating shared models..."
$SSH "grep -q 'NEURAL' $AGENT_DIR/shared/models.py || \
    sed -i '/MONITOR = \"monitor\"/a\\    NEURAL = \"neural\"' $AGENT_DIR/shared/models.py"

# 5. Add neural service to docker-compose.yml if not present
echo ">>> Checking docker-compose.yml..."
if $SSH "grep -q 'catalyst-neural' $AGENT_DIR/docker-compose.yml"; then
    echo "    Neural service already in docker-compose.yml"
else
    echo "    Adding neural service to docker-compose.yml..."
    $SSH "cat >> $AGENT_DIR/docker-compose.yml" << 'COMPOSE'

  # =========================================================================
  # NEURAL CORTEX — Forward Return Prediction
  # Runs CatalystNet ONNX model for CPU inference.
  # Predicts 5-horizon forward returns (5m, 15m, 1h, 4h, 1d).
  # Publishes directional signals to the signal bus.
  # Trained on the laptop (RTX 4050), deployed here for production.
  # =========================================================================
  neural:
    build:
      context: .
      dockerfile: neural/Dockerfile
    container_name: catalyst-neural
    network_mode: host
    environment:
      AGENT_DB_PATH: /var/lib/catalyst/db/agent.db
      CANDLE_MODEL_PATH: /app/neural/model/candle_model.onnx
      FUSED_MODEL_PATH: /app/neural/model/catalyst_net.onnx
      POLL_INTERVAL: "2.0"
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
    volumes:
      - /var/lib/catalyst/db:/var/lib/catalyst/db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; c=sqlite3.connect('/var/lib/catalyst/db/agent.db'); c.execute('SELECT 1'); print('OK')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
COMPOSE
fi

# 6. Build and start the neural container
echo ">>> Building neural container..."
$SSH "cd $AGENT_DIR && docker compose build neural"

echo ">>> Starting neural container..."
$SSH "cd $AGENT_DIR && docker compose up -d neural"

# 7. Verify
echo ""
echo ">>> Verifying deployment..."
sleep 3
$SSH "docker ps --filter name=catalyst-neural --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo ""
$SSH "docker logs catalyst-neural --tail 10 2>&1"

echo ""
echo "=========================================="
echo "Neural cortex deployed successfully!"
echo "=========================================="
echo ""
echo "Monitor:  ssh -i $SSH_KEY $DROPLET docker logs -f catalyst-neural"
echo "Restart:  ssh -i $SSH_KEY $DROPLET 'cd $AGENT_DIR && docker compose restart neural'"
echo "Update:   ./deploy-neural.sh [new-model.onnx]"
