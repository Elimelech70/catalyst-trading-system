"""
Catalyst Neural — Configuration

All settings loaded from environment variables (with .env file support).
Copy .env.template to .env and fill in your API keys.
"""

import os
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Paths ──
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
DEPLOY_DIR = PROJECT_ROOT / "deploy"

# ── Deployment Droplets ──
US_DROPLET_IP = os.getenv("CATALYST_US_DROPLET_IP", "68.183.177.11")
INTL_DROPLET_IP = os.getenv("CATALYST_INTL_DROPLET_IP", "209.38.87.27")
SSH_KEY = os.getenv("CATALYST_SSH_KEY", "~/.ssh/Catalyst-Linux-Claude")

# Backward compat — old code references DROPLET_IP
DROPLET_IP = US_DROPLET_IP
DROPLET_MCP_PORT = 5000
CONSCIOUSNESS_URL = f"http://{DROPLET_IP}:{DROPLET_MCP_PORT}"

# Deployment paths on each droplet
DEPLOYMENT = {
    "US": {
        "ip": US_DROPLET_IP,
        "ssh": f"ssh -i {SSH_KEY} root@{US_DROPLET_IP}",
        "project_dir": "/root/catalyst-agent",
        "models_dir": "/root/catalyst-agent/neural/model",
        "neural_integration": "standalone container (catalyst-neural)",
        "deploy_script": str(DEPLOY_DIR / "deploy-neural.sh"),
    },
    "INTL": {
        "ip": INTL_DROPLET_IP,
        "ssh": f"ssh -i {SSH_KEY} root@{INTL_DROPLET_IP}",
        "project_dir": "/root/Catalyst-Trading-System-International/catalyst-international",
        "models_dir": "/root/Catalyst-Trading-System-International/catalyst-international/models",
        "neural_integration": "cerebellum.py embedded in coordinator",
        "deploy_script": str(DEPLOY_DIR / "deploy-intl.sh"),
    },
}

# ── Market Data APIs ──

# Alpaca (US market data — free paper account gives market data access)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
ALPACA_DATA_URL = "https://data.alpaca.markets"

# Yahoo Finance — no API key needed, used as fallback and for HKEX/macro
# Rate limit yourself: ~2 requests/second max

# ── News APIs ──

# NewsAPI.org (free tier: 100 requests/day)
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# Finnhub (free tier: 60 calls/minute)
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")

# ── Economic Data ──

# FRED API (Federal Reserve Economic Data — free)
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# ── News Source Tiers ──
# Based on Craig's news-sources-guide.md
# Tier 1: Wire services — ground truth, fastest
# Tier 2: Major outlets — reliable, slight delay
# Tier 3: Secondary — useful but verify
# Tier 4: Social/alternative — noise ratio high, but can signal Layer 3 leaks

NEWS_SOURCE_TIERS = {
    # Tier 1 — Wire services
    "reuters": 1, "associated press": 1, "ap": 1, "afp": 1, "bloomberg": 1,

    # Tier 2 — Major financial
    "financial times": 2, "wall street journal": 2, "wsj": 2,
    "economist": 2, "nikkei": 2, "scmp": 2,
    "south china morning post": 2, "bbc": 2, "al jazeera": 2,

    # Tier 3 — Secondary
    "cnbc": 3, "marketwatch": 3, "yahoo finance": 3,
    "seeking alpha": 3, "investopedia": 3, "barrons": 3,
    "cnn business": 3, "fortune": 3,

    # Tier 4 — Social / alternative
    "twitter": 4, "x": 4, "reddit": 4, "telegram": 4,
    "zerohedge": 4, "substack": 4,
}

def get_source_tier(source_name):
    """Look up source tier. Default to 3 if unknown."""
    if not source_name:
        return 3
    return NEWS_SOURCE_TIERS.get(source_name.lower().strip(), 3)


# ── Collection Parameters ──

# Candle timeframes to collect
CANDLE_TIMEFRAMES = ["1m", "5m", "15m"]

# How many historical candles to backfill on first run
BACKFILL_DAYS = 30

# Macro instruments to track
MACRO_INSTRUMENTS = {
    # Currencies — the kingdom contention scoreboard
    "DXY":     {"type": "index",    "yahoo": "DX-Y.NYB"},
    "USD/CNY": {"type": "currency", "yahoo": "CNY=X"},
    "USD/JPY": {"type": "currency", "yahoo": "JPY=X"},
    "USD/HKD": {"type": "currency", "yahoo": "HKD=X"},
    "EUR/USD": {"type": "currency", "yahoo": "EURUSD=X"},
    "GBP/USD": {"type": "currency", "yahoo": "GBPUSD=X"},
    "AUD/USD": {"type": "currency", "yahoo": "AUDUSD=X"},
    "USD/RUB": {"type": "currency", "yahoo": "RUB=X"},

    # Yields — the price of trust
    "US10Y":   {"type": "yield",    "yahoo": "^TNX"},
    "US02Y":   {"type": "yield",    "yahoo": "^IRX"},  # 13-week proxy
    "US30Y":   {"type": "yield",    "yahoo": "^TYX"},

    # Fear / Volatility
    "VIX":     {"type": "index",    "yahoo": "^VIX"},

    # Commodities — real assets
    "GOLD":    {"type": "commodity", "yahoo": "GC=F"},
    "OIL":     {"type": "commodity", "yahoo": "CL=F"},

    # Crypto — alternative store of value
    "BTC/USD": {"type": "crypto",   "yahoo": "BTC-USD"},
}

# Sector ETFs — where is money flowing?
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communications",
}

# FRED series for economic releases
FRED_SERIES = {
    "GDP": "GDP",
    "CPI": "CPIAUCSL",
    "UNEMPLOYMENT": "UNRATE",
    "FED_FUNDS": "FEDFUNDS",
    "M2_MONEY": "M2SL",
    "CONSUMER_SENTIMENT": "UMCSENT",
    "HOUSING_STARTS": "HOUST",
    "RETAIL_SALES": "RSXFS",
}

# ── Training Parameters ──

TRAINING = {
    "lookback_candles": 60,       # how many candles the network sees
    "forward_horizons": [5, 15, 60, 240, 1440],  # minutes
    "batch_size": int(os.getenv("TRAINING_BATCH_SIZE", "64")),
    "learning_rate": float(os.getenv("TRAINING_LR", "0.001")),
    "epochs": int(os.getenv("TRAINING_EPOCHS", "100")),
    "validation_split": 0.2,
    "device": os.getenv("TRAINING_DEVICE", "cuda"),  # RTX 4050
}

# ── Market Hours ──
# When to collect data for each market.
# Collection starts PRE_MARKET_BUFFER_MINUTES before open to capture opening moves.

MARKET_HOURS = {
    "US": {
        "open": time(9, 30),
        "close": time(16, 0),
        "tz": ZoneInfo("America/New_York"),
    },
    "HKEX": {
        "open": time(9, 30),
        "close": time(16, 0),
        "tz": ZoneInfo("Asia/Hong_Kong"),
    },
}

PRE_MARKET_BUFFER_MINUTES = 15


def is_market_open(market):
    """Check if a market is currently in session (including pre-market buffer)."""
    cfg = MARKET_HOURS.get(market)
    if not cfg:
        return False

    now = datetime.now(cfg["tz"])

    # Closed on weekends (Mon=0, Sun=6)
    if now.weekday() >= 5:
        return False

    buffered_open = datetime.combine(now.date(), cfg["open"], tzinfo=cfg["tz"]) \
                    - timedelta(minutes=PRE_MARKET_BUFFER_MINUTES)
    close = datetime.combine(now.date(), cfg["close"], tzinfo=cfg["tz"])

    return buffered_open <= now <= close


def active_markets():
    """Return list of markets currently in session."""
    return [m for m in MARKET_HOURS if is_market_open(m)]


def next_market_open():
    """
    Find the next market open time.
    Returns (market, aware_datetime, seconds_until) or None if nothing scheduled
    within the next 7 days (shouldn't happen).
    """
    best = None

    for market, cfg in MARKET_HOURS.items():
        tz = cfg["tz"]
        now = datetime.now(tz)
        candidate = datetime.combine(now.date(), cfg["open"], tzinfo=tz) \
                    - timedelta(minutes=PRE_MARKET_BUFFER_MINUTES)

        # If today's open already passed, try tomorrow
        if candidate <= now:
            candidate += timedelta(days=1)

        # Skip weekends
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)

        secs = (candidate - now).total_seconds()
        if best is None or secs < best[2]:
            best = (market, candidate, secs)

    return best
