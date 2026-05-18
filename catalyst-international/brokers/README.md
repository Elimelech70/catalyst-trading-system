# Broker Integrations

**Last Updated:** 2025-12-20
**Current Broker:** Moomoo/Futu via OpenD

## Available Clients

### `futu.py` - Moomoo/Futu Client (Primary)
- **Status:** Active
- **Version:** 1.0.0
- **Exchange:** HKEX
- **Authentication:** Password + trade unlock (no 2FA)
- **Market Data:** Real-time (included)

## Migration Notes (Dec 2025)

Migrated from IBKR to Moomoo/Futu due to:
1. Constant IB Key 2FA authentication failures
2. Complex IBGA Docker + Java + VNC setup
3. 15-minute delayed market data (without paid subscription)

**Removed:** `ibkr.py` - Interactive Brokers client (deleted Dec 2025)

## Quick Start (Futu)

```python
from brokers.futu import FutuClient

# Initialize
client = FutuClient(
    host="127.0.0.1",
    port=11111,
    trade_password="your_trade_pwd",
    paper_trading=True
)

# Connect
client.connect()

# Get quote
quote = client.get_quote("700")  # Tencent
print(f"Last: {quote['last_price']}")

# Get portfolio
portfolio = client.get_portfolio()
print(f"Cash: {portfolio['cash']}")

# Execute trade
result = client.execute_trade(
    symbol="700",
    side="buy",
    quantity=100,  # Must be multiple of 100 for HKEX
    order_type="limit",
    limit_price=380.00,
    reason="Test trade"
)

# Disconnect
client.disconnect()
```

## Environment Variables

```bash
# For OpenD container
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
FUTU_TRADE_PWD=your_trade_password
```

## Symbol Format

| User Input | Futu Format | Exchange |
|------------|-------------|----------|
| `700` | `HK.00700` | HKEX |
| `0700` | `HK.00700` | HKEX |
| `9988` | `HK.09988` | HKEX |

## HKEX Tick Sizes

Futu/HKEX requires prices rounded to valid tick sizes:

| Price Range | Tick Size |
|-------------|-----------|
| < 0.25 | 0.001 |
| 0.25 - 0.50 | 0.005 |
| 0.50 - 10.00 | 0.01 |
| 10.00 - 20.00 | 0.02 |
| 20.00 - 100.00 | 0.05 |
| 100.00 - 200.00 | 0.10 |
| 200.00 - 500.00 | 0.20 |
| 500.00 - 1000.00 | 0.50 |
| 1000.00 - 2000.00 | 1.00 |
| 2000.00 - 5000.00 | 2.00 |
| > 5000.00 | 5.00 |

Use `client._round_to_tick(price)` to ensure compliance.

## Known Limitations

1. **No native bracket orders** - Futu doesn't support parent-child linked SL/TP orders
2. **Lot size** - HKEX requires trades in multiples of 100 shares
