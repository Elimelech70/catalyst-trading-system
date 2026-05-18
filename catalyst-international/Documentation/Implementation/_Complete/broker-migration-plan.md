# Catalyst Trading System: IBKR → Moomoo/Futu Migration Plan

**Name of Application:** Catalyst Trading System International  
**Name of File:** broker-migration-plan.md  
**Version:** 1.0.0  
**Created:** 2025-12-20  
**Purpose:** Complete implementation plan for broker migration  

---

## Executive Summary

Migrating from Interactive Brokers (IBKR/IBGA) to Moomoo/Futu OpenAPI to eliminate authentication complexity and improve operational reliability.

| Aspect | IBKR (Current) | Moomoo/Futu (Target) |
|--------|----------------|----------------------|
| Gateway | IBGA Docker + Java + VNC | OpenD native binary |
| Authentication | IB Key 2FA + token | Username/password + MD5 unlock |
| Container deps | Docker, Java 17, JavaFX | None (native Linux binary) |
| Debug method | VNC into container | Simple log files |
| Reconnection | Manual re-auth often | Auto-reconnect built-in |

---

## Phase 1: Account Setup (Day 1)

### Priority: CRITICAL - Must complete before any coding

### Step 1.1: Open Moomoo Australia Account

1. **Download moomoo AU app** from App Store / Play Store
2. **Sign up with Australian ID**
   - AFSL 224663 regulated
   - Supports HKEX trading
3. **Complete verification**
   - Photo ID
   - Proof of address
4. **Fund account** (minimum for testing)
5. **Enable OpenAPI access**
   - Settings → OpenAPI → Enable
   - Note your moomoo ID

### Step 1.2: Verify API Access

```bash
# Check if your account type supports OpenAPI
# Moomoo AU may have limitations - verify with support
```

**⚠️ CRITICAL CHECK:** Contact Moomoo AU support to confirm:
- OpenAPI trading is available for AU accounts
- HKEX trading is supported via API
- Paper trading is available via API

**Fallback:** If Moomoo AU doesn't support API, open Futu HK account instead.

---

## Phase 2: Infrastructure Setup (Day 1-2)

### Step 2.1: Download OpenD Gateway

```bash
# SSH into International droplet
ssh root@your-droplet-ip

# Create directory
mkdir -p /root/opend
cd /root/opend

# Download OpenD for Ubuntu (check for latest version)
wget https://softwaredownload.futunn.com/FutuOpenD_8.0.1_Ubuntu.tar.gz

# Extract
tar -xzf FutuOpenD_8.0.1_Ubuntu.tar.gz
cd FutuOpenD
```

### Step 2.2: Configure OpenD

Create configuration file:

```xml
<!-- /root/opend/FutuOpenD/FutuOpenD.xml -->
<?xml version="1.0" encoding="utf-8"?>
<config>
    <!-- Login credentials -->
    <login_account>YOUR_MOOMOO_ID</login_account>
    <login_pwd_md5>YOUR_PASSWORD_MD5</login_pwd_md5>
    
    <!-- API Settings -->
    <api_port>11111</api_port>
    <push_proto_type>1</push_proto_type>
    
    <!-- Language -->
    <lang>en</lang>
    
    <!-- Logging -->
    <log_level>info</log_level>
</config>
```

Generate password MD5:

```bash
echo -n "your_password" | md5sum | cut -d' ' -f1
```

### Step 2.3: Install Python SDK

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate

# Install Futu/Moomoo API
pip install futu-api
# OR for Moomoo branding:
pip install moomoo-api
```

### Step 2.4: Create OpenD systemd Service

```ini
# /etc/systemd/system/opend.service
[Unit]
Description=Futu OpenD Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/opend/FutuOpenD
ExecStart=/root/opend/FutuOpenD/FutuOpenD
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable opend
sudo systemctl start opend
sudo systemctl status opend
```

### Step 2.5: Test Connection

```python
# /root/opend/test_connection.py
from futu import OpenQuoteContext, OpenSecTradeContext, TrdMarket, SecurityFirm

# Test quote connection
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
print("Quote connection:", quote_ctx.get_global_state())
quote_ctx.close()

# Test trade connection
trd_ctx = OpenSecTradeContext(
    filter_trdmarket=TrdMarket.HK,
    host='127.0.0.1',
    port=11111,
    security_firm=SecurityFirm.FUTUSECURITIES
)
ret, data = trd_ctx.unlock_trade(password='your_trade_password')
print("Trade unlock:", ret, data)
trd_ctx.close()
```

---

## Phase 3: Broker Client Implementation (Day 2-3)

### Step 3.1: Create FutuClient

**File:** `brokers/futu.py`

```python
"""
Name of Application: Catalyst Trading System
Name of file: futu.py
Version: 1.0.0
Last Updated: 2025-12-20
Purpose: Moomoo/Futu client for HKEX trading

REVISION HISTORY:
v1.0.0 (2025-12-20) - Initial implementation
- Migrated from IBKR to Futu OpenAPI
- Simpler authentication (no Docker/2FA)
- Native socket API via OpenD
"""

import logging
import os
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from futu import (
    OpenQuoteContext,
    OpenSecTradeContext,
    TrdMarket,
    TrdSide,
    OrderType,
    SecurityFirm,
    RET_OK,
    ModifyOrderOp,
    TrdEnv,
)

logger = logging.getLogger(__name__)
HK_TZ = ZoneInfo("Asia/Hong_Kong")


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
class Position:
    """A portfolio position."""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class FutuClient:
    """Moomoo/Futu client for HKEX trading."""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        trade_password: str = None,
        paper_trading: bool = True,
    ):
        """Initialize Futu client.
        
        Args:
            host: OpenD host (default: FUTU_HOST env or 127.0.0.1)
            port: OpenD port (default: FUTU_PORT env or 11111)
            trade_password: Trade unlock password
            paper_trading: Use paper trading environment
        """
        self.host = host or os.environ.get("FUTU_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("FUTU_PORT", "11111"))
        self.trade_password = trade_password or os.environ.get("FUTU_TRADE_PWD")
        self.trd_env = TrdEnv.SIMULATE if paper_trading else TrdEnv.REAL
        
        self.quote_ctx = None
        self.trade_ctx = None
        self._connected = False
        self._trade_unlocked = False
    
    def connect(self) -> bool:
        """Connect to OpenD and unlock trading."""
        try:
            # Quote context
            self.quote_ctx = OpenQuoteContext(
                host=self.host, 
                port=self.port
            )
            
            # Trade context for HK market
            self.trade_ctx = OpenSecTradeContext(
                filter_trdmarket=TrdMarket.HK,
                host=self.host,
                port=self.port,
                security_firm=SecurityFirm.FUTUSECURITIES
            )
            
            # Unlock trade
            if self.trade_password:
                ret, data = self.trade_ctx.unlock_trade(self.trade_password)
                if ret == RET_OK:
                    self._trade_unlocked = True
                    logger.info("Trade unlocked successfully")
                else:
                    logger.warning(f"Trade unlock failed: {data}")
            
            self._connected = True
            logger.info(f"Connected to OpenD at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenD: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from OpenD."""
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trade_ctx:
            self.trade_ctx.close()
        self._connected = False
        logger.info("Disconnected from OpenD")
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected
    
    def _format_hk_symbol(self, symbol: str) -> str:
        """Format symbol for HKEX (e.g., '700' -> 'HK.00700')."""
        # Strip leading zeros for comparison, then pad to 5 digits
        num = symbol.lstrip('0')
        return f"HK.{num.zfill(5)}"
    
    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        hk_symbol = self._format_hk_symbol(symbol)
        ret, data = self.quote_ctx.get_market_snapshot([hk_symbol])
        
        if ret != RET_OK:
            logger.error(f"Failed to get quote for {symbol}: {data}")
            return {}
        
        if data.empty:
            return {}
        
        row = data.iloc[0]
        return {
            "symbol": symbol,
            "last_price": row.get("last_price", 0),
            "bid": row.get("bid_price", 0),
            "ask": row.get("ask_price", 0),
            "volume": row.get("volume", 0),
            "turnover": row.get("turnover", 0),
            "high": row.get("high_price", 0),
            "low": row.get("low_price", 0),
            "open": row.get("open_price", 0),
            "prev_close": row.get("prev_close_price", 0),
        }
    
    def get_positions(self) -> list[Position]:
        """Get all open positions."""
        ret, data = self.trade_ctx.position_list_query(trd_env=self.trd_env)
        
        if ret != RET_OK:
            logger.error(f"Failed to get positions: {data}")
            return []
        
        positions = []
        for _, row in data.iterrows():
            positions.append(Position(
                symbol=row["code"].replace("HK.", "").lstrip("0"),
                quantity=int(row["qty"]),
                avg_cost=float(row["cost_price"]),
                current_price=float(row["market_val"] / row["qty"]) if row["qty"] else 0,
                unrealized_pnl=float(row["pl_val"]),
                unrealized_pnl_pct=float(row["pl_ratio"] * 100) if row["pl_ratio"] else 0,
            ))
        
        return positions
    
    def get_portfolio(self) -> dict:
        """Get portfolio summary."""
        ret, data = self.trade_ctx.accinfo_query(trd_env=self.trd_env)
        
        if ret != RET_OK:
            logger.error(f"Failed to get portfolio: {data}")
            return {}
        
        if data.empty:
            return {}
        
        row = data.iloc[0]
        return {
            "total_value": float(row.get("total_assets", 0)),
            "cash": float(row.get("cash", 0)),
            "market_value": float(row.get("market_val", 0)),
            "buying_power": float(row.get("power", 0)),
            "currency": "HKD",
        }
    
    def _round_to_tick(self, price: float) -> float:
        """Round price to valid HKEX tick size."""
        if price < 0.25:
            tick = 0.001
        elif price < 0.50:
            tick = 0.005
        elif price < 10.00:
            tick = 0.01
        elif price < 20.00:
            tick = 0.02
        elif price < 100.00:
            tick = 0.05
        elif price < 200.00:
            tick = 0.10
        elif price < 500.00:
            tick = 0.20
        elif price < 1000.00:
            tick = 0.50
        elif price < 2000.00:
            tick = 1.00
        elif price < 5000.00:
            tick = 2.00
        else:
            tick = 5.00
        
        return round(round(price / tick) * tick, 3)
    
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
    ) -> OrderResult:
        """Execute a trade with optional bracket orders.
        
        Args:
            symbol: Stock code (e.g., '700' for Tencent)
            side: 'buy' or 'sell'
            quantity: Number of shares
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            stop_loss: Stop loss price
            take_profit: Take profit price
            reason: Reason for trade (for logging)
        
        Returns:
            OrderResult with order details
        """
        if not self._trade_unlocked:
            return OrderResult(
                order_id="",
                status="REJECTED",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=None,
                filled_quantity=0,
                message="Trade not unlocked",
            )
        
        hk_symbol = self._format_hk_symbol(symbol)
        
        # Map side
        trd_side = TrdSide.BUY if side.lower() == "buy" else TrdSide.SELL
        
        # Map order type and round price
        if order_type.lower() == "market":
            futu_order_type = OrderType.MARKET
            price = 0
        else:
            futu_order_type = OrderType.NORMAL  # Limit order
            price = self._round_to_tick(limit_price) if limit_price else 0
        
        logger.info(
            f"Executing trade: {side} {quantity} {symbol} @ {price} "
            f"[SL: {stop_loss}, TP: {take_profit}] Reason: {reason}"
        )
        
        # Place main order
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=quantity,
            code=hk_symbol,
            trd_side=trd_side,
            order_type=futu_order_type,
            trd_env=self.trd_env,
            remark=reason[:64] if reason else "",
        )
        
        if ret != RET_OK:
            logger.error(f"Order failed: {data}")
            return OrderResult(
                order_id="",
                status="REJECTED",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=None,
                filled_quantity=0,
                message=str(data),
            )
        
        order_id = str(data.iloc[0]["order_id"])
        
        # Note: Futu doesn't have native bracket orders like IBKR
        # Stop loss and take profit would need to be managed separately
        # via conditional orders or monitoring
        if stop_loss or take_profit:
            logger.info(
                f"Note: SL={stop_loss}, TP={take_profit} must be managed manually "
                f"(Futu doesn't support bracket orders)"
            )
        
        return OrderResult(
            order_id=order_id,
            status="SUBMITTED",
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            filled_price=None,
            filled_quantity=0,
            message=f"Order submitted: {order_id}",
        )
    
    def get_orders(self) -> list[dict]:
        """Get open orders."""
        ret, data = self.trade_ctx.order_list_query(trd_env=self.trd_env)
        
        if ret != RET_OK:
            logger.error(f"Failed to get orders: {data}")
            return []
        
        orders = []
        for _, row in data.iterrows():
            orders.append({
                "order_id": str(row["order_id"]),
                "symbol": row["code"].replace("HK.", "").lstrip("0"),
                "side": "buy" if row["trd_side"] == TrdSide.BUY else "sell",
                "quantity": int(row["qty"]),
                "filled_quantity": int(row["dealt_qty"]),
                "price": float(row["price"]),
                "status": row["order_status"],
            })
        
        return orders
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        ret, data = self.trade_ctx.modify_order(
            ModifyOrderOp.CANCEL,
            order_id=order_id,
            qty=0,
            price=0,
            trd_env=self.trd_env,
        )
        
        if ret != RET_OK:
            logger.error(f"Failed to cancel order {order_id}: {data}")
            return False
        
        logger.info(f"Order {order_id} cancelled")
        return True


# Global client instance
_futu_client: Optional[FutuClient] = None


def init_futu_client(**kwargs) -> FutuClient:
    """Initialize global Futu client."""
    global _futu_client
    _futu_client = FutuClient(**kwargs)
    return _futu_client


def get_futu_client() -> Optional[FutuClient]:
    """Get global Futu client."""
    return _futu_client
```

### Step 3.2: Update Broker __init__.py

**File:** `brokers/__init__.py`

```python
"""
Broker integrations for the Catalyst Trading Agent.

This package provides broker connectivity for:
- Moomoo/Futu for HKEX trading (primary)
- Interactive Brokers for HKEX trading (deprecated)
"""

from brokers.futu import FutuClient, get_futu_client, init_futu_client

__all__ = ["FutuClient", "get_futu_client", "init_futu_client"]
```

---

## Phase 4: Integration Updates (Day 3)

### Step 4.1: Update settings.yaml

```yaml
# config/settings.yaml

# Broker Configuration - Moomoo/Futu via OpenD
broker:
  name: FUTU
  host: "${FUTU_HOST:-127.0.0.1}"
  port: ${FUTU_PORT:-11111}
  paper_trading: true  # Set false for live
  
  # Order settings
  order_types:
    - market
    - limit
  default_tif: DAY
```

### Step 4.2: Update agent.py Imports

```python
# Change from:
from brokers.ibkr import get_ibkr_client, init_ibkr_client

# To:
from brokers.futu import get_futu_client, init_futu_client
```

### Step 4.3: Update tool_executor.py

Update broker initialization and calls to use FutuClient methods.

### Step 4.4: Update Environment File

```bash
# .env additions/changes
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
FUTU_TRADE_PWD=your_trade_password

# Remove IBKR variables
# IBKR_HOST=...
# IBKR_PORT=...
```

---

## Phase 5: Stop Loss/Take Profit Implementation (Day 3-4)

### Issue: Futu Doesn't Support Native Bracket Orders

Unlike IBKR, Futu doesn't have parent-child linked orders. We need to implement SL/TP management.

### Option A: Conditional Orders (Recommended)

```python
def place_stop_loss(self, symbol: str, quantity: int, 
                    trigger_price: float) -> str:
    """Place a conditional stop loss order."""
    hk_symbol = self._format_hk_symbol(symbol)
    
    # Futu supports conditional orders
    ret, data = self.trade_ctx.place_order(
        price=self._round_to_tick(trigger_price * 0.99),  # Limit below trigger
        qty=quantity,
        code=hk_symbol,
        trd_side=TrdSide.SELL,
        order_type=OrderType.STOP,  # Stop order type
        aux_price=trigger_price,  # Trigger price
        trd_env=self.trd_env,
    )
    
    if ret == RET_OK:
        return str(data.iloc[0]["order_id"])
    return ""
```

### Option B: Agent-Managed Stops

Let Claude monitor positions and issue market sells when price hits stop level.

---

## Phase 6: Testing (Day 4-5)

### Step 6.1: Unit Tests

```python
# tests/test_futu_client.py
import pytest
from brokers.futu import FutuClient

def test_connection():
    client = FutuClient(paper_trading=True)
    assert client.connect() == True
    assert client.is_connected() == True
    client.disconnect()

def test_get_quote():
    client = FutuClient(paper_trading=True)
    client.connect()
    quote = client.get_quote("700")  # Tencent
    assert "last_price" in quote
    assert quote["last_price"] > 0
    client.disconnect()

def test_hk_symbol_format():
    client = FutuClient()
    assert client._format_hk_symbol("700") == "HK.00700"
    assert client._format_hk_symbol("0700") == "HK.00700"
    assert client._format_hk_symbol("9988") == "HK.09988"

def test_tick_rounding():
    client = FutuClient()
    assert client._round_to_tick(0.123) == 0.123  # <0.25, tick=0.001
    assert client._round_to_tick(0.333) == 0.335  # <0.50, tick=0.005
    assert client._round_to_tick(5.55) == 5.55    # <10, tick=0.01
    assert client._round_to_tick(15.33) == 15.34  # <20, tick=0.02
```

### Step 6.2: Integration Test

```bash
# Run paper trade test
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate
python -c "
from brokers.futu import FutuClient

client = FutuClient(paper_trading=True)
client.connect()

# Get quote
quote = client.get_quote('700')
print(f'Tencent quote: {quote}')

# Get portfolio
portfolio = client.get_portfolio()
print(f'Portfolio: {portfolio}')

# Execute test trade
result = client.execute_trade(
    symbol='700',
    side='buy',
    quantity=100,
    order_type='limit',
    limit_price=quote['last_price'],
    reason='Integration test'
)
print(f'Order result: {result}')

client.disconnect()
"
```

---

## Phase 7: Cleanup & Documentation (Day 5)

### Step 7.1: Remove IBGA Components

```bash
# Stop and remove IBGA
docker stop ibga
docker rm ibga
rm -rf /root/Catalyst-Trading-System-International/catalyst-international/ibga

# Remove unused dependencies
pip uninstall ib_async ib_insync

# Update requirements.txt
echo "futu-api>=8.0.0" >> requirements.txt
```

### Step 7.2: Update Architecture Docs

Update these files with new broker info:
- `architecture-international.md`
- `consolidated-architecture-v1.6.0.md`
- `CLAUDE.md`

### Step 7.3: Update Cron Jobs

No changes needed - cron calls `agent.py` which now uses Futu.

---

## Implementation Checklist

### Day 1: Account & Infrastructure
- [ ] Open Moomoo AU account (or Futu HK if needed)
- [ ] Verify OpenAPI access for HKEX
- [ ] Download and configure OpenD
- [ ] Create systemd service for OpenD
- [ ] Test basic connection

### Day 2-3: Code Implementation
- [ ] Create `brokers/futu.py`
- [ ] Update `brokers/__init__.py`
- [ ] Update `config/settings.yaml`
- [ ] Update `.env` file
- [ ] Update `agent.py` imports
- [ ] Update `tool_executor.py`

### Day 3-4: Stop Loss Implementation
- [ ] Implement conditional order support
- [ ] OR implement agent-managed stops
- [ ] Test SL/TP functionality

### Day 4-5: Testing
- [ ] Unit tests pass
- [ ] Integration test with paper trading
- [ ] Full agent cycle test
- [ ] Verify order execution
- [ ] Verify position management

### Day 5: Cleanup
- [ ] Remove IBGA Docker
- [ ] Remove ib_async dependency
- [ ] Update documentation
- [ ] Final paper trading run

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Moomoo AU doesn't support API | Use Futu HK account instead |
| OpenD disconnects | systemd auto-restart + connection retry in code |
| No bracket orders | Implement conditional orders or agent-managed stops |
| Different tick rules | Already implemented HKEX tick size rounding |
| Quote format differs | Symbol formatting function handles conversion |

---

## Expected Benefits After Migration

1. **No more 2FA nightmare** - Simple password auth
2. **No Docker complexity** - Native binary, systemd managed
3. **No VNC debugging** - Simple log files
4. **Faster connection** - No Java/JVM overhead
5. **Better HKEX support** - They're HK's #1 retail broker
6. **Real-time data included** - No subscription needed
7. **Cleaner codebase** - ~200 lines less infrastructure code

---

## Support Resources

- **Futu OpenAPI Docs:** https://openapi.futunn.com/futu-api-doc/en/
- **Python SDK:** https://pypi.org/project/futu-api/
- **GitHub Examples:** https://github.com/billpwchan/futu_algo
- **Moomoo AU Support:** support@moomoo.com.au
