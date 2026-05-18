# Catalyst Neural — Quick Start

**Version:** 0.3.1
**Updated:** 2026-04-20

## Setup (one time)

```bash
# 1. Clone or copy this folder to your laptop
cd ~/catalyst/catalyst-neural

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install base dependencies
pip install -r requirements.txt

# 4. Install PyTorch with CUDA
# Check your CUDA version: nvidia-smi
# Then go to https://pytorch.org/get-started/locally/ and get the right command
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 5. Verify GPU
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}')"

# 6. Copy environment config and fill in API keys
cp .env.template .env
# Edit .env with your API keys (optional — candle collection works without them)

# 7. Initialize database
python run.py init

# 8. Install systemd services (auto-collection + weekly training pipeline)
sudo bash install-power.sh
```

## Configuration

All settings live in two places:

- **`.env`** — API keys, droplet IPs, training params (copy from `.env.template`)
- **`config/settings.py`** — market hours, macro instruments, sector ETFs, news tiers

### Required Environment Variables

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `CATALYST_US_DROPLET_IP` | US droplet (default: 68.183.177.11) | Has default |
| `CATALYST_INTL_DROPLET_IP` | Intl droplet (default: 209.38.87.27) | Has default |
| `CATALYST_SSH_KEY` | SSH key path (default: ~/.ssh/Catalyst-Linux-Claude) | Has default |
| `NEWSAPI_KEY` | NewsAPI.org headlines | Optional |
| `FINNHUB_KEY` | Finnhub company news | Optional |
| `ALPACA_API_KEY` | Alpaca market data | Optional |
| `FRED_API_KEY` | FRED economic data | Optional |
| `TRAINING_DEVICE` | Training device (default: cuda) | Has default |
| `TRAINING_EPOCHS` | Max epochs (default: 100) | Has default |

## Daily Operations

```bash
# Everything runs automatically via systemd, but here's the manual commands:

# Check what we have
python run.py status

# Collect data once
python run.py collect

# Continuous collection (market-hours aware, suspends between sessions)
python run.py watch

# Backfill historical data
python run.py backfill --days 30
```

## Training & Deployment

```bash
# Full automated pipeline: labels → train → export → deploy to BOTH droplets
python run.py pipeline

# Train + export only (no deploy)
python run.py pipeline --skip-deploy

# Manual steps if needed:
python run.py labels                              # Compute forward returns
python run.py train candle --epochs 50            # Train CandleModel
python run.py train candle --dry-run              # Check data + model without training
python run.py export candle models/candle_model_XXXX.pt  # Export to ONNX
bash deploy/deploy-neural.sh                      # Deploy to US droplet
bash deploy/deploy-intl.sh                        # Deploy to Intl droplet
```

## Systemd Services

| Service | Type | What it does |
|---------|------|--------------|
| `catalyst-neural.service` | Continuous | Runs `run.py watch` — collects data during market hours |
| `catalyst-pipeline.timer` | Weekly (Sun 20:00) | Runs `run.py pipeline` — retrain + deploy |
| `catalyst-power-shutdown.service` | Shutdown hook | Sets RTC wake alarm before poweroff |

```bash
# Check status
systemctl --user status catalyst-neural
systemctl --user list-timers

# Manual control
systemctl --user start catalyst-neural     # Start collection
systemctl --user stop catalyst-neural      # Stop collection
systemctl --user start catalyst-pipeline   # Run pipeline now
journalctl --user -u catalyst-neural -f    # View collection logs
journalctl --user -u catalyst-pipeline -e  # View pipeline logs
```

## Deployment Targets

Models deploy to **two droplets** with different architectures:

| Environment | IP | Architecture | Neural Integration |
|---|---|---|---|
| **US Droplet** | 68.183.177.11 | v8 Agent Body (SQLite, signal bus) | Standalone `catalyst-neural` container |
| **Intl Droplet** | 209.38.87.27 | MCP (PostgreSQL, Redis, Moomoo/OpenD) | `cerebellum.py` in coordinator |

## What Gets Collected

| Data | Source | Cost | Resolution |
|------|--------|------|------------|
| US candles | Yahoo Finance | Free | 1m, 5m, 15m |
| HKEX candles | Yahoo Finance | Free | 1m, 5m, 15m |
| Currencies (DXY, pairs) | Yahoo Finance | Free | Daily |
| Yields (10Y, 2Y, 30Y) & VIX | Yahoo Finance | Free | Daily |
| Sector ETFs (11 sectors) | Yahoo Finance | Free | Daily |
| Commodities (Gold, Oil) | Yahoo Finance | Free | Daily |
| Crypto (BTC/USD) | Yahoo Finance | Free | Daily |
| News headlines | NewsAPI / Finnhub | Free tier | Event-driven |

## Current Models

| Model | Params | Input | Output |
|-------|--------|-------|--------|
| **CandleModel v0.3** | 132K | 5m + 15m candles (60-bar lookback) | Direction (3-class) + returns (5m, 15m, 1h) + confidence |
| **CatalystNet** (legacy) | 1.6M | 5m candles + macro + news | 5-horizon returns + confidence |

## Project Structure

```
catalyst-neural/
├── run.py                        # CLI entry point (all commands)
├── .env                          # API keys + config (gitignored)
├── .env.template                 # Config template
├── requirements.txt              # Python dependencies
├── ARCHITECTURE.md               # System design document
├── config/
│   └── settings.py               # Settings loaded from .env
├── collectors/
│   ├── candle_collector.py       # OHLCV data (Yahoo Finance)
│   ├── news_collector.py         # Headlines + source provenance
│   ├── macro_collector.py        # Currencies, yields, sectors
│   └── security_picker.py       # Droplet polling + big mover scanning
├── storage/
│   └── database.py               # SQLite schema + helpers
├── training/
│   ├── dataset.py                # CandleDataset + CatalystDataset
│   ├── models.py                 # CandleModel + CatalystNet
│   ├── trainer.py                # CandleTrainer + Trainer
│   ├── report.py                 # Training report generation
│   ├── label_generator.py        # Forward return computation
│   └── export_onnx.py            # ONNX export for deployment
├── deploy/
│   ├── deploy-neural.sh          # Deploy to US droplet
│   ├── deploy-intl.sh            # Deploy to Intl droplet
│   └── neural/
│       ├── cortex.py             # Neural inference service (US droplet)
│       ├── Dockerfile            # Container spec
│       └── requirements.txt      # Container dependencies
├── catalyst-neural.service       # Systemd: collection daemon
├── catalyst-pipeline.service     # Systemd: training pipeline
├── catalyst-pipeline.timer       # Systemd: weekly trigger
├── catalyst-power                # Power management (wake/suspend)
├── catalyst-power-shutdown.service
├── install-power.sh              # One-time service installer
├── models/                       # Checkpoints, ONNX, reports (gitignored)
└── data/
    └── catalyst_neural.db        # SQLite database (gitignored)
```
