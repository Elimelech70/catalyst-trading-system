#!/bin/bash
# Deploy CandleModel to the International droplet (HKEX)
# Usage: ./deploy-intl.sh

set -euo pipefail

DROPLET="root@209.38.87.27"
SSH_KEY="$HOME/.ssh/Catalyst-Linux-Claude"
SSH="ssh -i $SSH_KEY $DROPLET"
SCP="scp -i $SSH_KEY"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$(dirname "$SCRIPT_DIR")/models"
REMOTE_DIR="/root/Catalyst-Trading-System-International/catalyst-international"
REMOTE_MODELS="$REMOTE_DIR/models"

# Find candle model
CANDLE_MODEL="$MODELS_DIR/candle_model.onnx"

if [ ! -f "$CANDLE_MODEL" ]; then
    echo "ERROR: No candle model found at $CANDLE_MODEL"
    echo "Run: python run.py train candle && python run.py export candle <checkpoint.pt>"
    exit 1
fi

echo "=========================================="
echo "Deploying to International Droplet (HKEX)"
echo "=========================================="
echo "Candle:  $CANDLE_MODEL ($(du -h "$CANDLE_MODEL" | cut -f1))"
echo "Droplet: $DROPLET"
echo ""

# 1. Copy ONNX model + data file
echo ">>> Copying candle model..."
$SCP "$CANDLE_MODEL" "$DROPLET:$REMOTE_MODELS/candle_model.onnx"
if [ -f "${CANDLE_MODEL}.data" ]; then
    echo "    Copying external data..."
    $SCP "${CANDLE_MODEL}.data" "$DROPLET:$REMOTE_MODELS/candle_model.onnx.data"
fi

# 2. Update model_version.json
echo ">>> Updating model_version.json..."
VERSION_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
$SSH "cat > $REMOTE_MODELS/model_version.json" << EOF
{
  "version": "0.3.1",
  "deployed_at": "$VERSION_DATE",
  "model_type": "candle",
  "architecture": "CandleModel v0.3 (dual-input 5m+15m)",
  "parameters": 132103,
  "inputs": ["candles_5m (batch, 5, 60)", "candles_15m (batch, 5, 60)"],
  "outputs": ["direction_logits (batch, 3)", "pred_returns (batch, 3)", "confidence (batch, 1)"],
  "trained_on": "laptop RTX 4050",
  "deployed_by": "deploy-intl.sh"
}
EOF

# 3. Rebuild and restart coordinator
echo ">>> Rebuilding coordinator..."
$SSH "cd $REMOTE_DIR && docker compose build coordinator"

echo ">>> Restarting coordinator..."
$SSH "cd $REMOTE_DIR && docker compose up -d coordinator"

# 4. Verify
echo ""
echo ">>> Verifying deployment..."
sleep 5
$SSH "docker ps --filter name=catalyst-coordinator --format 'table {{.Names}}\t{{.Status}}'"
echo ""
$SSH "docker logs catalyst-coordinator --tail 10 2>&1"

echo ""
echo "=========================================="
echo "International droplet deployed!"
echo "=========================================="
echo ""
echo "Monitor:  ssh -i $SSH_KEY $DROPLET docker logs -f catalyst-coordinator"
echo "Restart:  ssh -i $SSH_KEY $DROPLET 'cd $REMOTE_DIR && docker compose restart coordinator'"
