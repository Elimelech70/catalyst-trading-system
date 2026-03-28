"""
Name of Application: Catalyst Trading System
Name of file: config.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Shared configuration for agent body components

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- AgentConfig dataclass with environment variable loading

Description:
Central configuration loaded from environment variables.
All components use AgentConfig.from_env() to get their settings.
"""

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for agent body components."""

    # Database paths
    agent_db_path: str = "/var/lib/catalyst/db/agent.db"
    hippocampus_db_path: str = "/var/lib/catalyst/hippocampus/memory.db"

    # Alpaca broker
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    paper_trading: bool = True

    # Anthropic API (PFC cognition)
    anthropic_api_key: str = ""

    # Remote PostgreSQL (for trading data queries)
    database_url: str = ""

    # Agent settings
    agent_id: str = "big_bro"
    poll_interval: float = 2.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            agent_db_path=os.getenv("AGENT_DB_PATH", "/var/lib/catalyst/db/agent.db"),
            hippocampus_db_path=os.getenv("HIPPOCAMPUS_DB_PATH", "/var/lib/catalyst/hippocampus/memory.db"),
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            alpaca_data_url=os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets"),
            paper_trading=os.getenv("PAPER_TRADING", "true").lower() == "true",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            database_url=os.getenv("DATABASE_URL", ""),
            agent_id=os.getenv("AGENT_ID", "big_bro"),
            poll_interval=float(os.getenv("POLL_INTERVAL", "2.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
