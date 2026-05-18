"""
Name of Application: Catalyst Trading System
Name of file: moomoo.py
Version: 1.6.0
Last Updated: 2026-02-05
Purpose: Moomoo client for HKEX trading via OpenD gateway

REVISION HISTORY:
v1.6.0 (2026-02-05) - Symbol normalization
- Added normalize_symbol() module-level function for consistent symbol formatting
- Fixed get_quotes_batch() to return Dict[str, dict] instead of List[dict]
- Updated _parse_hk_symbol() and close_position() to use normalize_symbol()
- Eliminates phantom position mismatches (e.g., 0670 vs 670)

v1.5.0 (2026-02-04) - Order fill confirmation
- Added wait_for_fill() method to poll order status until filled
- Added is_order_filled() helper method
- execute_trade() now returns accurate fill status after confirmation
- New OrderFillResult dataclass for detailed fill information
- Configurable timeout for fill confirmation (default 30s paper, 60s live)
- Terminal status detection (CANCELLED, FAILED, DELETED)
- Rate limit aware polling with backoff

v1.4.0 (2026-01-08) - Symbol normalization fix
- Fixed close_position() to normalize symbol before matching
- Now accepts '700', '0700', or 'HK.00700' formats
- Positions store symbols without leading zeros (e.g., '700' not '0700')

v1.3.0 (2026-01-08) - Dynamic lot size support
- Added get_lot_size() method to fetch actual board lot from API
- Updated execute_trade() to use stock-specific lot size
- Fixes "odd lot" order rejection errors
- Different HKEX stocks have different lot sizes (100, 500, 1000, etc.)

v1.2.0 (2026-01-02) - Add historical data support
- Added get_historical_data() for OHLCV candlestick data
- Uses request_history_kline API with KLType mapping
- Fixes get_technicals and detect_patterns tools

v1.1.0 (2025-12-30) - Add batch quote support
- Added get_quotes_batch() for multiple symbols in one API call
- Fixes rate limiting issue (max 60 requests per 30 seconds)
- Batch API supports up to 400 symbols per request

v1.0.0 (2025-12-29) - Initial implementation
- Uses moomoo-api Python SDK (NOT futu-api)
- Connects to OpenD native binary gateway
- Simple password authentication (no 2FA)
- Real-time market data included
- HKEX tick size rounding
- Symbol format conversion (700 -> HK.00700)

Description:
This module provides the MoomooClient class for trading HKEX stocks via
Moomoo's OpenD gateway. It replaces the IBKR integration to eliminate
the authentication complexity of IB Gateway.

KEY CHANGES in v1.5.0:
- execute_trade() now waits for fill confirmation before returning
- New wait_for_fill() method with configurable timeout
- OrderResult.status now reflects ACTUAL fill status, not just submission
- Prevents phantom positions from being created for unfilled orders

Official Documentation:
- API Docs: https://openapi.moomoo.com/moomoo-api-doc/en/intro/intro.html
- OpenD Download: https://www.moomoo.com/download/OpenAPI
- Python SDK: https://pypi.org/project/moomoo-api/

Environment Variables:
    MOOMOO_HOST: OpenD host (default: 127.0.0.1)
    MOOMOO_PORT: OpenD port (default: 11111)
    MOOMOO_TRADE_PWD: Trade unlock password
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo

# CORRECT: Import from moomoo (NOT futu)
from moomoo import (
    OpenQuoteContext,
    OpenSecTradeContext,
    TrdMarket,
    TrdSide,
    OrderType,
    SecurityFirm,
    RET_OK,
    ModifyOrderOp,
    TrdEnv,
    KLType,
    Market,
    SecurityType,
)

logger = logging.getLogger(__name__)
HK_TZ = ZoneInfo("Asia/Hong_Kong")


# =============================================================================
# SYMBOL NORMALIZATION
# =============================================================================

def normalize_symbol(symbol: str) -> str:
    """
    Normalize HKEX symbol to canonical format without leading zeros.

    This function provides consistent symbol formatting across the entire
    trading system, preventing mismatches like '0670' vs '670'.

    Args:
        symbol: Stock symbol in any format ('700', '0700', 'HK.00700', '700.HK')

    Returns:
        Normalized symbol without leading zeros (e.g., '700', '5')

    Examples:
        >>> normalize_symbol('0700')
        '700'
        >>> normalize_symbol('HK.00700')
        '700'
        >>> normalize_symbol('700.HK')
        '700'
        >>> normalize_symbol('5')
        '5'
        >>> normalize_symbol('0005')
        '5'
    """
    if not symbol:
        return symbol

    s = str(symbol).upper()
    # Remove exchange prefixes and suffixes
    s = s.replace('HK.', '').replace('.HK', '')
    # Strip leading zeros, but keep at least one digit
    s = s.lstrip('0') or '0'

    return s


# =============================================================================
# ORDER STATUS CONSTANTS (from Moomoo API documentation)
# =============================================================================

class OrderStatus:
    """Moomoo order status constants."""
    # Working states
    WAITING_SUBMIT = "WAITING_SUBMIT"  # Futu server received, preparing to submit
    SUBMITTING = "SUBMITTING"           # Sent to exchange, being processed
    SUBMITTED = "SUBMITTED"             # Successfully submitted (working)
    
    # Filled states
    FILLED_PART = "FILLED_PART"         # Partially filled
    FILLED_ALL = "FILLED_ALL"           # Fully filled
    
    # Terminal states
    CANCELLED_PART = "CANCELLED_PART"   # Part filled, remainder cancelled
    CANCELLED_ALL = "CANCELLED_ALL"     # Fully cancelled
    FAILED = "FAILED"                   # Rejected by server
    DISABLED = "DISABLED"               # Deactivated
    DELETED = "DELETED"                 # Deleted
    
    # Status groups for checking
    FILLED_STATUSES = [FILLED_ALL, FILLED_PART]
    WORKING_STATUSES = [WAITING_SUBMIT, SUBMITTING, SUBMITTED]
    TERMINAL_STATUSES = [CANCELLED_PART, CANCELLED_ALL, FAILED, DISABLED, DELETED]


@dataclass
class OrderResult:
    """Result of an order submission."""
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    filled_price: Optional[float]
    filled_quantity: int
    message: str


@dataclass
class OrderFillResult:
    """Detailed result of order fill confirmation."""
    filled: bool
    order_id: str
    status: str
    filled_quantity: int
    filled_price: Optional[float]
    original_quantity: int
    message: str
    attempts: int
    elapsed_seconds: float


@dataclass
class Position:
    """A portfolio position."""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


# HKEX Tick Size Table
# Reference: https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Mechanism?sc_lang=en
HKEX_TICK_SIZES = [
    (0.25, 0.001),
    (0.50, 0.005),
    (10.00, 0.01),
    (20.00, 0.02),
    (100.00, 0.05),
    (200.00, 0.10),
    (500.00, 0.20),
    (1000.00, 0.50),
    (2000.00, 1.00),
    (5000.00, 2.00),
    (float('inf'), 5.00),
]


class MoomooClient:
    """Moomoo client for HKEX trading.

    This client connects to the OpenD gateway to execute trades on HKEX.
    It provides a simpler authentication model compared to IBKR.

    Example:
        client = MoomooClient(paper_trading=True)
        client.connect()
        quote = client.get_quote("700")
        print(f"Tencent last price: {quote['last_price']}")
        client.disconnect()
    """

    # Fill confirmation timeouts (seconds)
    FILL_TIMEOUT_PAPER = 30   # Paper trading fills quickly
    FILL_TIMEOUT_LIVE = 60    # Live trading may take longer
    POLL_INTERVAL_START = 1   # Start polling every 1 second
    POLL_INTERVAL_MAX = 5     # Max polling interval (with backoff)

    def __init__(
        self,
        host: str = None,
        port: int = None,
        trade_password: str = None,
        paper_trading: bool = True,
    ):
        """Initialize Moomoo client.

        Args:
            host: OpenD host (default: MOOMOO_HOST env or 127.0.0.1)
            port: OpenD port (default: MOOMOO_PORT env or 11111)
            trade_password: Trade unlock password
            paper_trading: Use paper trading environment
        """
        self.host = host or os.environ.get("MOOMOO_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("MOOMOO_PORT", "11111"))
        self.trade_password = trade_password or os.environ.get("MOOMOO_TRADE_PWD")
        self.trd_env = TrdEnv.SIMULATE if paper_trading else TrdEnv.REAL
        self.paper_trading = paper_trading

        self.quote_ctx = None
        self.trade_ctx = None
        self._connected = False
        self._trade_unlocked = False

        logger.info(
            f"MoomooClient initialized: host={self.host}, port={self.port}, "
            f"paper_trading={paper_trading}"
        )

    def connect(self) -> bool:
        """Connect to OpenD and unlock trading.

        Returns:
            True if connected successfully
        """
        try:
            # Connect quote context
            self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            logger.info("Quote context connected")

            # Connect trade context
            self.trade_ctx = OpenSecTradeContext(
                host=self.host,
                port=self.port,
                filter_trdmarket=TrdMarket.HK,
                security_firm=SecurityFirm.FUTUSECURITIES,
            )
            logger.info("Trade context connected")

            # Unlock trading if password provided and not paper trading
            if self.trade_password and self.trd_env == TrdEnv.REAL:
                ret, data = self.trade_ctx.unlock_trade(self.trade_password)
                if ret == RET_OK:
                    self._trade_unlocked = True
                    logger.info("Trade unlocked for REAL trading")
                else:
                    logger.warning(f"Failed to unlock trade: {data}")
            else:
                # Paper trading doesn't need unlock
                self._trade_unlocked = True

            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from OpenD."""
        if self.quote_ctx:
            self.quote_ctx.close()
            self.quote_ctx = None
        if self.trade_ctx:
            self.trade_ctx.close()
            self.trade_ctx = None
        self._connected = False
        self._trade_unlocked = False
        logger.info("Disconnected from OpenD")

    def _format_hk_symbol(self, symbol: str) -> str:
        """Convert symbol to Moomoo HK format.

        Args:
            symbol: Stock code (e.g., '700', '0700', 'HK.00700')

        Returns:
            Moomoo format (e.g., 'HK.00700')
        """
        if symbol.startswith("HK."):
            return symbol
        # Strip leading zeros and pad to 5 digits
        code = symbol.lstrip("0") or "0"
        return f"HK.{code.zfill(5)}"

    def _parse_hk_symbol(self, moomoo_symbol: str) -> str:
        """Convert Moomoo format back to simple code.

        Args:
            moomoo_symbol: Moomoo format (e.g., 'HK.00700')

        Returns:
            Simple code without leading zeros (e.g., '700')
        """
        return normalize_symbol(moomoo_symbol)

    def _round_to_tick(self, price: float) -> float:
        """Round price to valid HKEX tick size.

        Args:
            price: Raw price

        Returns:
            Price rounded to nearest valid tick
        """
        for threshold, tick in HKEX_TICK_SIZES:
            if price < threshold:
                return round(price / tick) * tick
        return price

    def get_lot_size(self, symbol: str) -> int:
        """Get the board lot size for a HKEX stock.

        Args:
            symbol: Stock code (e.g., '700')

        Returns:
            Board lot size (e.g., 100)
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        moomoo_symbol = self._format_hk_symbol(symbol)

        ret, data = self.quote_ctx.get_stock_basicinfo(
            market=Market.HK,
            stock_type=SecurityType.STOCK,
            code_list=[moomoo_symbol]
        )

        if ret == RET_OK and not data.empty:
            lot_size = int(data.iloc[0].get("lot_size", 100))
            logger.debug(f"Lot size for {symbol}: {lot_size}")
            return lot_size

        logger.warning(f"Could not get lot size for {symbol}, defaulting to 100")
        return 100

    # =========================================================================
    # ORDER FILL CONFIRMATION METHODS (NEW in v1.5.0)
    # =========================================================================

    def get_order_status(self, order_id: str) -> dict:
        """Get current status of a specific order.

        Args:
            order_id: Order ID to check

        Returns:
            Dict with order status details including:
            - order_id: str
            - status: str (SUBMITTED, FILLED_ALL, etc.)
            - filled_quantity: int (dealt_qty)
            - filled_price: float (dealt_avg_price)
            - original_quantity: int (qty)
            - error: str (if failed)
        """
        if not self._connected:
            return {"error": "Not connected to OpenD"}

        ret, data = self.trade_ctx.order_list_query(trd_env=self.trd_env)

        if ret != RET_OK:
            return {"error": str(data)}

        for _, row in data.iterrows():
            if str(row.get("order_id", "")) == str(order_id):
                return {
                    "order_id": order_id,
                    "status": str(row.get("order_status", "")),
                    "symbol": self._parse_hk_symbol(str(row.get("code", ""))),
                    "side": str(row.get("trd_side", "")),
                    "original_quantity": int(row.get("qty", 0)),
                    "filled_quantity": int(row.get("dealt_qty", 0)),
                    "price": float(row.get("price", 0)),
                    "filled_price": float(row.get("dealt_avg_price", 0)) or None,
                    "create_time": str(row.get("create_time", "")),
                    "update_time": str(row.get("updated_time", "")),
                    "last_err_msg": str(row.get("last_err_msg", "")),
                }

        return {"error": f"Order {order_id} not found"}

    def is_order_filled(self, order_id: str) -> Tuple[bool, dict]:
        """Check if an order is filled.

        Args:
            order_id: Order ID to check

        Returns:
            Tuple of (is_filled: bool, order_details: dict)
        """
        details = self.get_order_status(order_id)

        if "error" in details:
            return False, details

        status = details.get("status", "")
        filled_qty = details.get("filled_quantity", 0)

        # FILLED_ALL = fully filled
        # FILLED_PART with filled_qty > 0 = partially filled (counts as filled)
        is_filled = (
            status == OrderStatus.FILLED_ALL or 
            (status == OrderStatus.FILLED_PART and filled_qty > 0)
        )

        return is_filled, details

    def is_order_terminal(self, order_id: str) -> Tuple[bool, dict]:
        """Check if an order is in a terminal state (cancelled/failed).

        Args:
            order_id: Order ID to check

        Returns:
            Tuple of (is_terminal: bool, order_details: dict)
        """
        details = self.get_order_status(order_id)

        if "error" in details:
            return False, details

        status = details.get("status", "")
        is_terminal = status in OrderStatus.TERMINAL_STATUSES

        return is_terminal, details

    def wait_for_fill(
        self,
        order_id: str,
        timeout_seconds: int = None,
        poll_interval: float = None,
    ) -> OrderFillResult:
        """Wait for an order to be filled, with polling.

        This method polls order_list_query until:
        1. Order is filled (FILLED_ALL or FILLED_PART with dealt_qty > 0)
        2. Order reaches terminal state (CANCELLED, FAILED, DELETED)
        3. Timeout is reached

        Args:
            order_id: Order ID to wait for
            timeout_seconds: Max wait time (default: 30s paper, 60s live)
            poll_interval: Initial poll interval (default: 1s, backs off to 5s)

        Returns:
            OrderFillResult with fill details
        """
        if timeout_seconds is None:
            timeout_seconds = (
                self.FILL_TIMEOUT_PAPER if self.paper_trading 
                else self.FILL_TIMEOUT_LIVE
            )

        if poll_interval is None:
            poll_interval = self.POLL_INTERVAL_START

        start_time = time.time()
        attempts = 0
        last_status = ""
        last_details = {}

        logger.info(f"Waiting for fill on order {order_id} (timeout: {timeout_seconds}s)")

        while (time.time() - start_time) < timeout_seconds:
            attempts += 1
            
            try:
                is_filled, details = self.is_order_filled(order_id)
                last_details = details
                last_status = details.get("status", "")

                if is_filled:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"Order {order_id} FILLED after {elapsed:.1f}s "
                        f"({attempts} attempts): {details.get('filled_quantity')} @ "
                        f"{details.get('filled_price')}"
                    )
                    return OrderFillResult(
                        filled=True,
                        order_id=order_id,
                        status=last_status,
                        filled_quantity=details.get("filled_quantity", 0),
                        filled_price=details.get("filled_price"),
                        original_quantity=details.get("original_quantity", 0),
                        message="Order filled successfully",
                        attempts=attempts,
                        elapsed_seconds=elapsed,
                    )

                # Check for terminal states
                is_terminal, _ = self.is_order_terminal(order_id)
                if is_terminal:
                    elapsed = time.time() - start_time
                    logger.warning(
                        f"Order {order_id} reached terminal state: {last_status}"
                    )
                    return OrderFillResult(
                        filled=False,
                        order_id=order_id,
                        status=last_status,
                        filled_quantity=details.get("filled_quantity", 0),
                        filled_price=details.get("filled_price"),
                        original_quantity=details.get("original_quantity", 0),
                        message=f"Order terminated with status: {last_status}",
                        attempts=attempts,
                        elapsed_seconds=elapsed,
                    )

                # Log progress periodically
                if attempts % 5 == 0:
                    logger.debug(
                        f"Order {order_id} still pending ({last_status}), "
                        f"attempt {attempts}, elapsed {time.time() - start_time:.1f}s"
                    )

            except Exception as e:
                logger.warning(f"Error polling order status: {e}")

            # Sleep with backoff
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.2, self.POLL_INTERVAL_MAX)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning(
            f"Order {order_id} not filled after {elapsed:.1f}s "
            f"({attempts} attempts), last status: {last_status}"
        )
        return OrderFillResult(
            filled=False,
            order_id=order_id,
            status=last_status or "TIMEOUT",
            filled_quantity=last_details.get("filled_quantity", 0),
            filled_price=last_details.get("filled_price"),
            original_quantity=last_details.get("original_quantity", 0),
            message=f"Order not filled within {timeout_seconds} seconds",
            attempts=attempts,
            elapsed_seconds=elapsed,
        )

    # =========================================================================
    # QUOTE AND POSITION METHODS
    # =========================================================================

    def get_quote(self, symbol: str) -> dict:
        """Get real-time quote for a symbol.

        Args:
            symbol: Stock code (e.g., '700')

        Returns:
            Dict with quote data
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        moomoo_symbol = self._format_hk_symbol(symbol)

        ret, data = self.quote_ctx.get_market_snapshot([moomoo_symbol])

        if ret != RET_OK:
            raise RuntimeError(f"Failed to get quote: {data}")

        if data.empty:
            raise ValueError(f"No quote data for {symbol}")

        row = data.iloc[0]

        return {
            "symbol": symbol,
            "last_price": float(row.get("last_price", 0)),
            "bid_price": float(row.get("bid_price", 0)),
            "ask_price": float(row.get("ask_price", 0)),
            "high_price": float(row.get("high_price", 0)),
            "low_price": float(row.get("low_price", 0)),
            "open_price": float(row.get("open_price", 0)),
            "prev_close": float(row.get("prev_close_price", 0)),
            "volume": int(row.get("volume", 0)),
            "turnover": float(row.get("turnover", 0)),
            "update_time": str(row.get("update_time", "")),
        }

    def get_quotes_batch(self, symbols: List[str]) -> dict[str, dict]:
        """Get quotes for multiple symbols in one API call.

        Args:
            symbols: List of stock codes (any format accepted)

        Returns:
            Dict mapping normalized symbol to quote data.
            Keys are normalized symbols (e.g., '700' not '0700').
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        moomoo_symbols = [self._format_hk_symbol(s) for s in symbols]

        ret, data = self.quote_ctx.get_market_snapshot(moomoo_symbols)

        if ret != RET_OK:
            raise RuntimeError(f"Failed to get quotes: {data}")

        quotes_dict = {}
        for _, row in data.iterrows():
            symbol = self._parse_hk_symbol(str(row.get("code", "")))
            quotes_dict[symbol] = {
                "symbol": symbol,
                "last_price": float(row.get("last_price", 0)),
                "bid_price": float(row.get("bid_price", 0)),
                "ask_price": float(row.get("ask_price", 0)),
                "high_price": float(row.get("high_price", 0)),
                "low_price": float(row.get("low_price", 0)),
                "open_price": float(row.get("open_price", 0)),
                "prev_close": float(row.get("prev_close_price", 0)),
                "volume": int(row.get("volume", 0)),
                "turnover": float(row.get("turnover", 0)),
            }

        return quotes_dict

    def get_positions(self) -> List[Position]:
        """Get current positions.

        Returns:
            List of Position objects
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        ret, data = self.trade_ctx.position_list_query(trd_env=self.trd_env)

        if ret != RET_OK:
            logger.error(f"Failed to get positions: {data}")
            raise RuntimeError(f"Failed to get positions: {data}")

        positions = []
        for _, row in data.iterrows():
            qty = int(row.get("qty", 0))
            if qty == 0:
                continue

            positions.append(Position(
                symbol=self._parse_hk_symbol(str(row.get("code", ""))),
                quantity=qty,
                avg_cost=float(row.get("cost_price", 0)),
                current_price=float(row.get("nominal_price", 0)),
                unrealized_pnl=float(row.get("pl_val", 0)),
                unrealized_pnl_pct=float(row.get("pl_ratio", 0)) * 100,
            ))

        return positions

    def get_portfolio(self) -> dict:
        """Get portfolio summary.

        Returns:
            Dict with portfolio data
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        ret, data = self.trade_ctx.accinfo_query(trd_env=self.trd_env)

        if ret != RET_OK:
            raise RuntimeError(f"Failed to get portfolio: {data}")

        row = data.iloc[0] if not data.empty else {}

        positions = self.get_positions()
        market_value = sum(p.current_price * p.quantity for p in positions)

        return {
            "cash": float(row.get("cash", 0)),
            "total_assets": float(row.get("total_assets", 0)),
            "equity": float(row.get("total_assets", 0)),
            "market_value": market_value,
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                }
                for p in positions
            ],
            "position_count": len(positions),
            "unrealized_pnl": sum(p.unrealized_pnl for p in positions),
            "daily_pnl": float(row.get("today_pl_val", 0)),
            "daily_pnl_pct": float(row.get("today_pl_ratio", 0)) * 100,
            "currency": "HKD",
        }

    # =========================================================================
    # TRADING METHODS (ENHANCED in v1.5.0)
    # =========================================================================

    def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "limit",
        limit_price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        reason: str = "",
        wait_for_fill: bool = True,
        fill_timeout: int = None,
    ) -> OrderResult:
        """Execute a trade with fill confirmation.

        Args:
            symbol: Stock code (e.g., '700')
            side: 'buy' or 'sell'
            quantity: Number of shares (must be multiple of lot size for HKEX)
            order_type: 'market' or 'limit'
            limit_price: Required for limit orders
            stop_loss: Stop loss price (agent-managed, not native bracket)
            take_profit: Take profit price (agent-managed, not native bracket)
            reason: Reason for the trade (logged)
            wait_for_fill: If True, wait for fill confirmation (default: True)
            fill_timeout: Max seconds to wait for fill (default: auto)

        Returns:
            OrderResult with ACTUAL fill status (not just submission status)
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        # Paper trading (SIMULATE) doesn't require trade unlock
        if self.trd_env != TrdEnv.SIMULATE and not self._trade_unlocked:
            raise RuntimeError("Trading not unlocked (required for REAL trading)")

        # Validate lot size
        actual_lot_size = self.get_lot_size(symbol)
        if quantity % actual_lot_size != 0:
            logger.warning(f"Adjusting quantity {quantity} to nearest lot of {actual_lot_size}")
            quantity = (quantity // actual_lot_size) * actual_lot_size
            if quantity == 0:
                quantity = actual_lot_size

        moomoo_symbol = self._format_hk_symbol(symbol)

        # Map side
        trd_side = TrdSide.BUY if side.lower() == "buy" else TrdSide.SELL

        # Map order type and prepare price
        if order_type.lower() == "market":
            moomoo_order_type = OrderType.MARKET
            price = 0
        else:
            moomoo_order_type = OrderType.NORMAL  # Limit order
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            price = self._round_to_tick(limit_price)

        logger.info(
            f"Executing {side} {quantity} {symbol} @ {price} ({order_type}) - {reason}"
        )

        # Place the order
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=quantity,
            code=moomoo_symbol,
            trd_side=trd_side,
            order_type=moomoo_order_type,
            trd_env=self.trd_env,
        )

        if ret != RET_OK:
            logger.error(f"Order failed: {data}")
            return OrderResult(
                order_id="",
                status="FAILED",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=None,
                filled_quantity=0,
                message=str(data),
            )

        row = data.iloc[0]
        order_id = str(row.get("order_id", ""))
        initial_status = str(row.get("order_status", "SUBMITTED"))

        logger.info(f"Order placed: {order_id} (initial status: {initial_status})")

        # Log stop loss / take profit for agent to track
        if stop_loss:
            logger.info(f"Agent-managed SL for {order_id}: {stop_loss}")
        if take_profit:
            logger.info(f"Agent-managed TP for {order_id}: {take_profit}")

        # If not waiting for fill, return immediately with submission status
        if not wait_for_fill:
            return OrderResult(
                order_id=order_id,
                status=initial_status,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=float(row.get("dealt_avg_price", 0)) or None,
                filled_quantity=int(row.get("dealt_qty", 0)),
                message=f"Order {order_id} submitted (fill not confirmed)",
            )

        # Wait for fill confirmation
        fill_result = self.wait_for_fill(order_id, timeout_seconds=fill_timeout)

        if fill_result.filled:
            return OrderResult(
                order_id=order_id,
                status="FILLED",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=fill_result.filled_price,
                filled_quantity=fill_result.filled_quantity,
                message=f"Order {order_id} filled: {fill_result.filled_quantity} @ {fill_result.filled_price}",
            )
        else:
            # Order not filled within timeout or reached terminal state
            return OrderResult(
                order_id=order_id,
                status=fill_result.status,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=fill_result.filled_price,
                filled_quantity=fill_result.filled_quantity,
                message=fill_result.message,
            )

    def close_position(self, symbol: str, reason: str = "") -> OrderResult:
        """Close a specific position.

        Args:
            symbol: Stock code to close (accepts '700', '0700', 'HK.00700')
            reason: Reason for closing

        Returns:
            OrderResult with order details
        """
        positions = self.get_positions()
        # Normalize input symbol to match position format
        normalized_symbol = normalize_symbol(symbol)

        position = None
        for p in positions:
            if p.symbol == normalized_symbol:
                position = p
                break

        if not position:
            return OrderResult(
                order_id="",
                status="FAILED",
                symbol=symbol,
                side="sell",
                quantity=0,
                order_type="market",
                filled_price=None,
                filled_quantity=0,
                message=f"No position found for {symbol} (normalized: {normalized_symbol})",
            )

        return self.execute_trade(
            symbol=position.symbol,
            side="sell",
            quantity=position.quantity,
            order_type="market",
            reason=reason or f"Close position: {position.symbol}",
        )

    def close_all_positions(self, reason: str = "") -> List[OrderResult]:
        """Close all positions.

        Args:
            reason: Reason for closing all

        Returns:
            List of OrderResults
        """
        positions = self.get_positions()
        results = []

        for position in positions:
            result = self.close_position(
                symbol=position.symbol,
                reason=reason or "Emergency close all positions",
            )
            results.append(result)

        return results

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Dict with cancellation result
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        ret, data = self.trade_ctx.modify_order(
            modify_order_op=ModifyOrderOp.CANCEL,
            order_id=order_id,
            qty=0,
            price=0,
            trd_env=self.trd_env,
        )

        if ret != RET_OK:
            return {"success": False, "error": str(data)}

        return {"success": True, "order_id": order_id, "message": "Order cancelled"}

    def get_historical_data(
        self,
        symbol: str,
        duration: str = "5 D",
        bar_size: str = "15 mins",
    ) -> List[dict]:
        """Get historical OHLCV data for a symbol.

        Args:
            symbol: Stock code (e.g., '700')
            duration: Time period (e.g., '5 D', '1 M')
            bar_size: Bar size (e.g., '1 min', '5 mins', '15 mins', '1 D')

        Returns:
            List of OHLCV dicts
        """
        if not self._connected:
            raise RuntimeError("Not connected to OpenD")

        moomoo_symbol = self._format_hk_symbol(symbol)

        # Map bar size to KLType
        kl_type_map = {
            "1 min": KLType.K_1M,
            "5 mins": KLType.K_5M,
            "15 mins": KLType.K_15M,
            "30 mins": KLType.K_30M,
            "60 mins": KLType.K_60M,
            "1 hour": KLType.K_60M,
            "1 D": KLType.K_DAY,
            "1 day": KLType.K_DAY,
            "1 W": KLType.K_WEEK,
            "1 week": KLType.K_WEEK,
            "1 M": KLType.K_MON,
            "1 month": KLType.K_MON,
        }

        kl_type = kl_type_map.get(bar_size, KLType.K_15M)

        # Parse duration
        count = 100  # Default
        if "D" in duration.upper():
            days = int(duration.upper().replace("D", "").strip())
            if kl_type == KLType.K_15M:
                count = days * 26  # ~26 bars per day
            elif kl_type == KLType.K_DAY:
                count = days

        ret, data, _ = self.quote_ctx.request_history_kline(
            code=moomoo_symbol,
            ktype=kl_type,
            max_count=count,
        )

        if ret != RET_OK:
            raise RuntimeError(f"Failed to get historical data: {data}")

        bars = []
        for _, row in data.iterrows():
            bars.append({
                "timestamp": str(row.get("time_key", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            })

        return bars


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_moomoo_client: Optional[MoomooClient] = None


def init_moomoo_client(**kwargs) -> MoomooClient:
    """Initialize global Moomoo client."""
    global _moomoo_client
    _moomoo_client = MoomooClient(**kwargs)
    return _moomoo_client


def get_moomoo_client() -> Optional[MoomooClient]:
    """Get global Moomoo client."""
    return _moomoo_client
