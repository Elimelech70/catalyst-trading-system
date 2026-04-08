#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: broker_base.py
Version: 1.0.0
Last Updated: 2026-04-08
Purpose: Broker-agnostic base class and data normalisation layer

REVISION HISTORY:
v1.0.0 (2026-04-08) - v2.4 architecture alignment
- StandardBroker ABC with normalised interface
- alpaca_to_standard() and moomoo_to_standard() converters
- One training run produces models that work on both deployments

Description:
The ONNX models are identical on both deployments. The cerebellum does not
know or care whether candles came from Alpaca or Moomoo. All broker-specific
data is normalised before it reaches the model.

    Alpaca bar --> alpaca_to_standard() --+
                                          +--> Standard OHLCV --> ONNX Model
    Moomoo bar --> moomoo_to_standard() --+
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from shared.models import StandardOHLCV

logger = logging.getLogger("cerebellum.broker_base")


# =============================================================================
# DATA NORMALISATION LAYER
# =============================================================================

def alpaca_to_standard(bar: Dict[str, Any], timeframe: str = "1d") -> StandardOHLCV:
    """
    Convert an Alpaca bar to StandardOHLCV format.
    Alpaca bars have: timestamp, open, high, low, close, volume.
    """
    ts = bar.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif not isinstance(ts, datetime):
        ts = datetime.now(timezone.utc)

    return StandardOHLCV(
        timestamp=ts,
        open=float(bar["open"]),
        high=float(bar["high"]),
        low=float(bar["low"]),
        close=float(bar["close"]),
        volume=float(bar["volume"]),
        timeframe=timeframe,
    )


def moomoo_to_standard(bar: Dict[str, Any], timeframe: str = "1d") -> StandardOHLCV:
    """
    Convert a Moomoo/Futu bar to StandardOHLCV format.
    Moomoo bars may use different field names (time_key, turnover, etc).
    """
    ts = bar.get("time_key") or bar.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif not isinstance(ts, datetime):
        ts = datetime.now(timezone.utc)

    return StandardOHLCV(
        timestamp=ts,
        open=float(bar.get("open", bar.get("open_price", 0))),
        high=float(bar.get("high", bar.get("high_price", 0))),
        low=float(bar.get("low", bar.get("low_price", 0))),
        close=float(bar.get("close", bar.get("close_price", 0))),
        volume=float(bar.get("volume", bar.get("turnover", 0))),
        timeframe=timeframe,
    )


def bars_to_standard(
    bars: List[Dict[str, Any]], broker_type: str, timeframe: str = "1d"
) -> List[StandardOHLCV]:
    """Convert a list of broker bars to standard format."""
    converter = alpaca_to_standard if broker_type == "alpaca" else moomoo_to_standard
    return [converter(bar, timeframe) for bar in bars]


# =============================================================================
# STANDARD BROKER INTERFACE
# =============================================================================

class StandardBroker(ABC):
    """
    Broker-agnostic interface -- v2.4 architecture.

    All broker implementations extend this. The coordinator and cerebellum
    interact only with this interface. Broker-specific details are hidden
    behind the normalisation layer.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker. Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self):
        """Clean up broker connection."""
        ...

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """
        Get account info in standard format:
        {buying_power, cash, equity, portfolio_value, status, currency}
        """
        ...

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get open positions in standard format:
        [{symbol, qty, side, avg_entry_price, current_price,
          unrealized_pl, unrealized_plpc, market_value, market}]
        """
        ...

    @abstractmethod
    def get_bars(
        self, symbol: str, timeframe: str = "1d", count: int = 60
    ) -> List[StandardOHLCV]:
        """Get historical bars as StandardOHLCV list."""
        ...

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Submit an order. Returns:
        {order_id, symbol, qty, side, type, status, submitted_at}
        or {error, symbol, side, qty} on failure.
        """
        ...

    @abstractmethod
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a specific position."""
        ...

    @abstractmethod
    def close_all_positions(self) -> Dict[str, Any]:
        """Emergency: close all positions."""
        ...

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if the market is currently open for trading."""
        ...
