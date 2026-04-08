# Catalyst Neural — Quick Start

## Setup (one time)

```bash
# 1. Clone or copy this folder to your laptop
cd ~/catalyst-neural

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install base dependencies
pip install -r requirements.txt

# 4. Install PyTorch with CUDA
# Check your CUDA version: nvidia-smi
# Then go to https://pytorch.org/get-started/locally/ and get the right command
# For RTX 4050 with CUDA 13.0, try:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 5. Verify GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"

# 6. Initialize database
python run.py init
```

## Add Securities to Watch

```bash
# US securities
python run.py add AAPL US --name "Apple"
python run.py add NVDA US --name "NVIDIA"
python run.py add TSLA US --name "Tesla"
python run.py add MSFT US --name "Microsoft"
python run.py add AMZN US --name "Amazon"

# HKEX securities (use stock code)
python run.py add 9988 HKEX --name "Alibaba"
python run.py add 9888 HKEX --name "Baidu"
python run.py add 1810 HKEX --name "Xiaomi"
python run.py add 981 HKEX --name "SMIC"
python run.py add 2382 HKEX --name "Sunny Optical"
```

## Collect Data

```bash
# Backfill 30 days of history (run once)
python run.py backfill --days 30

# Collect latest data (run periodically)
python run.py collect

# Or run continuous collection (every 5 minutes)
python run.py watch

# Check what we have
python run.py status
```

## Compute Training Labels

```bash
# After collecting data, compute forward returns
python run.py labels

# Check label statistics
python run.py labels --stats
```

## Set API Keys (optional, for news)

```bash
# Add to ~/.bashrc or run before collecting
export NEWSAPI_KEY="your-key-here"
export FINNHUB_KEY="your-key-here"
export ALPACA_API_KEY="your-key-here"
export ALPACA_SECRET_KEY="your-key-here"
```

## What Gets Collected

| Data | Source | Cost | Resolution |
|------|--------|------|------------|
| US candles | Yahoo Finance | Free | 1m, 5m, 15m |
| HKEX candles | Yahoo Finance | Free | 1m, 5m, 15m |
| Currencies | Yahoo Finance | Free | Daily+ |
| Yields & VIX | Yahoo Finance | Free | Daily+ |
| Sector ETFs | Yahoo Finance | Free | Daily+ |
| News | NewsAPI / Finnhub | Free tier | Event-driven |
| Commodities | Yahoo Finance | Free | Daily+ |

## Project Structure

```
catalyst-neural/
├── run.py                    # Main entry point
├── ARCHITECTURE.md           # System design document
├── requirements.txt          # Python dependencies
├── config/
│   └── settings.py           # API keys, parameters, source tiers
├── collectors/
│   ├── candle_collector.py   # OHLCV data (Yahoo Finance)
│   ├── news_collector.py     # Headlines + source provenance
│   └── macro_collector.py    # Currencies, yields, sectors
├── storage/
│   └── database.py           # SQLite schema + helpers
├── training/
│   └── label_generator.py    # Forward return computation
├── models/                   # Trained model files (.pt)
└── data/
    └── catalyst_neural.db    # SQLite database (created on init)
```
