"""
Name of Application: Catalyst Trading System
Name of file: settings.py
Version: 1.0.0
Last Updated: 2025-12-09
Purpose: Application configuration using Pydantic Settings

REVISION HISTORY:
v1.0.0 (2025-12-09) - Initial implementation
- Pydantic settings with environment variable support
- Typed configuration for all components
- Validation and defaults

Description:
Centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Anthropic API
    # =========================================================================
    anthropic_api_key: str = Field(
        ...,
        description="Anthropic API key for Claude",
    )

    # =========================================================================
    # Database
    # =========================================================================
    database_url: Optional[str] = Field(
        default=None,
        description="Full database URL (overrides individual settings)",
    )
    db_host: str = Field(
        default="localhost",
        description="Database host",
    )
    db_port: int = Field(
        default=5432,
        description="Database port",
    )
    db_name: str = Field(
        default="catalyst_trading",
        description="Database name",
    )
    db_user: str = Field(
        default="catalyst",
        description="Database user",
    )
    db_password: str = Field(
        default="catalyst_password",
        description="Database password",
    )
    db_pool_min: int = Field(
        default=2,
        description="Minimum database connections",
    )
    db_pool_max: int = Field(
        default=10,
        description="Maximum database connections",
    )

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL."""
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # =========================================================================
    # Moomoo/Futu Broker
    # =========================================================================
    futu_host: str = Field(
        default="127.0.0.1",
        description="OpenD gateway host",
    )
    futu_port: int = Field(
        default=11111,
        description="OpenD API port",
    )
    futu_trade_pwd: Optional[str] = Field(
        default=None,
        description="Futu trade unlock password",
    )

    # =========================================================================
    # Alerts
    # =========================================================================
    alert_webhook: Optional[str] = Field(
        default=None,
        description="Webhook URL for alerts (Discord/Slack)",
    )
    alert_email: Optional[str] = Field(
        default=None,
        description="Email address for alerts",
    )
    smtp_host: str = Field(
        default="smtp.gmail.com",
        description="SMTP server host",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="SMTP username",
    )
    smtp_pass: Optional[str] = Field(
        default=None,
        description="SMTP password",
    )

    # =========================================================================
    # Claude Model Configuration
    # =========================================================================
    tactical_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for tactical decisions (fast)",
    )
    analytical_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for analytical thinking (daily)",
    )
    strategic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for strategic thinking (weekly)",
    )
    tactical_max_tokens: int = Field(
        default=2000,
        description="Max tokens for tactical responses",
    )
    analytical_max_tokens: int = Field(
        default=4000,
        description="Max tokens for analytical responses",
    )
    strategic_max_tokens: int = Field(
        default=8000,
        description="Max tokens for strategic responses",
    )

    # =========================================================================
    # Trading Parameters
    # =========================================================================
    max_positions: int = Field(
        default=5,
        description="Maximum simultaneous positions",
    )
    max_position_pct: float = Field(
        default=0.20,
        description="Maximum position size as fraction of portfolio",
    )
    max_daily_loss_pct: float = Field(
        default=0.02,
        description="Maximum daily loss before emergency stop",
    )
    min_risk_reward: float = Field(
        default=2.0,
        description="Minimum risk/reward ratio",
    )

    # =========================================================================
    # Market Configuration
    # =========================================================================
    exchange_code: str = Field(
        default="HKEX",
        description="Exchange code",
    )
    currency: str = Field(
        default="HKD",
        description="Trading currency",
    )
    timezone: str = Field(
        default="Asia/Hong_Kong",
        description="Exchange timezone",
    )
    morning_open: str = Field(
        default="09:30",
        description="Morning session open time",
    )
    morning_close: str = Field(
        default="12:00",
        description="Morning session close time",
    )
    afternoon_open: str = Field(
        default="13:00",
        description="Afternoon session open time",
    )
    afternoon_close: str = Field(
        default="16:00",
        description="Afternoon session close time",
    )

    # =========================================================================
    # Operational
    # =========================================================================
    environment: str = Field(
        default="paper",
        description="Environment (paper/live)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    loop_interval_ms: int = Field(
        default=100,
        description="Main loop interval in milliseconds",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is paper or live."""
        v = v.lower()
        if v not in ("paper", "live"):
            raise ValueError("Environment must be 'paper' or 'live'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        v = v.upper()
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(**kwargs) -> Settings:
    """Initialize settings with overrides."""
    global _settings
    _settings = Settings(**kwargs)
    return _settings
