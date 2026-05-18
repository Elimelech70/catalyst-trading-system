# Report Generator Fixes - 2025-12-31

**Purpose:** Document fixes made to `generate_daily_report.py` v2.0.0 for replication on US Catalyst system

---

## Summary

Fixed Moomoo SDK compatibility issues in the daily report generator. These patterns apply to any code using the Moomoo/Futu SDK.

---

## Fix 1: DataFrame Iteration

**Problem:** Moomoo SDK returns pandas DataFrames, not lists of dicts.

```python
# ❌ WRONG - iterates over column names
for acc in acc_list:
    if acc.get("acc_id") == target:  # ERROR: str has no .get()

# ✅ CORRECT - iterate over rows
for _, acc in acc_list.iterrows():
    if acc["acc_id"] == target:  # Works
```

---

## Fix 2: Safe Float Conversion

**Problem:** Many Moomoo fields contain "N/A" strings instead of None/0.

```python
# ❌ WRONG - crashes on "N/A"
value = float(row.get("today_pl_val", 0))  # ERROR: could not convert 'N/A'

# ✅ CORRECT - add safe_float helper
def safe_float(value, default=0.0) -> float:
    """Safely convert value to float, handling 'N/A' and other non-numeric values."""
    if value == "N/A" or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

value = safe_float(row.get("today_pl_val", 0))  # Returns 0.0 for "N/A"
```

**Fields commonly returning "N/A":**
- `today_pl_val`, `today_buy_qty`, `today_sell_qty`
- `average_cost`, `unrealized_pl`, `realized_pl`
- `max_power_short`, `net_cash_power`, `fund_assets`
- `long_mv`, `short_mv`, `pending_asset`

---

## Fix 3: TrdEnv Enum Comparison

**Problem:** DataFrame returns string "SIMULATE", not `TrdEnv.SIMULATE` enum.

```python
# ❌ WRONG - comparing string to enum
TRADE_ENV = TrdEnv.SIMULATE
if acc["trd_env"] == TRADE_ENV:  # Never matches

# ✅ CORRECT - compare strings
if acc["trd_env"] == "SIMULATE":  # Paper trading
if acc["trd_env"] == "REAL":      # Live trading
```

---

## Fix 4: PostgreSQL Date Type

**Problem:** asyncpg expects date object, not string.

```python
# ❌ WRONG - passing string
report_date = "2025-12-31"
await conn.execute("INSERT ... VALUES ($1)", report_date)
# ERROR: 'str' object has no attribute 'toordinal'

# ✅ CORRECT - convert to date object
from datetime import datetime
date_obj = datetime.strptime(report_date, "%Y-%m-%d").date()
await conn.execute("INSERT ... VALUES ($1)", date_obj)
```

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/generate_daily_report.py` | All 4 fixes applied |

---

## Test Results (INTL)

```
==================================================
INTL_CLAUDE DAILY REPORT GENERATOR v2.0.0
==================================================

📊 Fetching portfolio data from Moomoo...
   Found 3 positions
📝 Generating report...
💾 Storing in consciousness database...
✅ Report stored in database (ID: 4)

==================================================
✅ REPORT COMPLETE
==================================================
   Date: 2025-12-31
   Positions: 3
   P&L: +HKD 5,802 · 3 positions
   Dashboard: Available at /reports/4
```

---

## Applicability to US System

If US Catalyst uses:
- **Alpaca API:** Different SDK, may not need these fixes
- **Moomoo/Futu:** Apply all 4 fixes
- **asyncpg:** Fix 4 (date type) applies regardless of broker

---

## Quick Reference

```python
# Add to top of file
def safe_float(value, default=0.0) -> float:
    if value == "N/A" or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# For DataFrame iteration
for _, row in dataframe.iterrows():
    val = safe_float(row.get("field"))

# For date to PostgreSQL
from datetime import datetime
date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
```

---

**END OF DOCUMENT**
