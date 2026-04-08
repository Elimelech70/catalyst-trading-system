"""
Name of Application: Catalyst Trading System
Name of file: config.py
Version: 2.0.0
Last Updated: 2026-04-08
Purpose: Shared configuration for agent body components

REVISION HISTORY:
v2.0.0 (2026-04-08) - v2.4 architecture alignment
- Added broker_type for multi-deployment (alpaca / moomoo)
- Added Moomoo broker credentials
- Added model paths (candle_model, news_model, fused_model)
- Added coordinator config (cycle_interval, market hours)
- Added market configuration
v1.0.0 (2026-03-03) - Initial creation
- AgentConfig dataclass with environment variable loading

Description:
Central configuration loaded from environment variables.
All components use AgentConfig.from_env() to get their settings.
Configuration documents (per-deployment) set these environment variables.
"""

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for agent body components."""

    # Database paths
    agent_db_path: str = "/var/lib/catalyst/db/agent.db"
    hippocampus_db_path: str = "/var/lib/catalyst/hippocampus/memory.db"

    # Broker selection (v2.4 multi-deployment)
    broker_type: str = "alpaca"  # alpaca | moomoo

    # Alpaca broker (US deployment)
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # Moomoo broker (Intl deployment)
    moomoo_api_key: str = ""
    moomoo_secret_key: str = ""
    moomoo_base_url: str = ""
    moomoo_market: str = "HKEX"

    # Trading mode
    paper_trading: bool = True

    # Anthropic API (PFC cognition -- called only for novel situations)
    anthropic_api_key: str = ""

    # Remote PostgreSQL (for trading data queries)
    database_url: str = ""

    # Agent settings
    agent_id: str = "big_bro"
    poll_interval: float = 2.0
    log_level: str = "INFO"

    # Market configuration
    market: str = "US"  # US | HKEX
    market_open_hour: int = 9       # ET for US, HKT for HKEX
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    market_timezone: str = "America/New_York"

    # Model paths (ONNX -- trained on laptop, deployed to droplet)
    candle_model_path: str = "/var/lib/catalyst/models/candle_model.onnx"
    news_model_path: str = "/var/lib/catalyst/models/news_model.onnx"
    fused_model_path: str = "/var/lib/catalyst/models/catalyst_net.onnx"

    # Coordinator cycle (v2.4)
    coordinator_cycle_interval: float = 30.0  # seconds between 6-layer cycles

    # Risk limits
    max_position_pct: float = 0.25   # max single position as % of equity
    max_daily_loss_pct: float = 0.03  # max daily loss as % of equity
    stop_loss_pct: float = 0.03      # default stop loss %

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            agent_db_path=os.getenv("AGENT_DB_PATH", "/var/lib/catalyst/db/agent.db"),
            hippocampus_db_path=os.getenv("HIPPOCAMPUS_DB_PATH", "/var/lib/catalyst/hippocampus/memory.db"),
            broker_type=os.getenv("BROKER_TYPE", "alpaca"),
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            alpaca_data_url=os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets"),
            moomoo_api_key=os.getenv("MOOMOO_API_KEY", ""),
            moomoo_secret_key=os.getenv("MOOMOO_SECRET_KEY", ""),
            moomoo_base_url=os.getenv("MOOMOO_BASE_URL", ""),
            moomoo_market=os.getenv("MOOMOO_MARKET", "HKEX"),
            paper_trading=os.getenv("PAPER_TRADING", "true").lower() == "true",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            database_url=os.getenv("DATABASE_URL", ""),
            agent_id=os.getenv("AGENT_ID", "big_bro"),
            poll_interval=float(os.getenv("POLL_INTERVAL", "2.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            market=os.getenv("MARKET", "US"),
            market_open_hour=int(os.getenv("MARKET_OPEN_HOUR", "9")),
            market_open_minute=int(os.getenv("MARKET_OPEN_MINUTE", "30")),
            market_close_hour=int(os.getenv("MARKET_CLOSE_HOUR", "16")),
            market_close_minute=int(os.getenv("MARKET_CLOSE_MINUTE", "0")),
            market_timezone=os.getenv("MARKET_TIMEZONE", "America/New_York"),
            candle_model_path=os.getenv("CANDLE_MODEL_PATH", "/var/lib/catalyst/models/candle_model.onnx"),
            news_model_path=os.getenv("NEWS_MODEL_PATH", "/var/lib/catalyst/models/news_model.onnx"),
            fused_model_path=os.getenv("FUSED_MODEL_PATH", "/var/lib/catalyst/models/catalyst_net.onnx"),
            coordinator_cycle_interval=float(os.getenv("COORDINATOR_CYCLE_INTERVAL", "30.0")),
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.25")),
            max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03")),
            stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.03")),
        )
