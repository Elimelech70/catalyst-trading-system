"""
Compute 30-day realized volatility from 5m candles, store as snapshot.

Definition (per catalyst-cohort-experiments-architecture v0.2 Section 5.1):
    σ(symbol, t) = stdev{ ln(close_t / close_{t-1}) :
                          5m bars in [t - 30 trading days, t] }

Stored daily. The annualized form (σ × √(78 × 252)) is for human readability;
the raw 5m sigma is what cohort assignment uses.

Run nightly via cron — see Phase 2 of catalyst-cohort-experiments-implementation.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from storage.database import get_connection

WINDOW_TRADING_DAYS = 30
BARS_PER_DAY = 78                   # 5m bars in a 6.5h US session
MIN_BARS_REQUIRED = 500              # at least ~6 trading days


def compute_realized_vol_for_symbol(conn, symbol, market, as_of_date=None):
    """Return (realized_vol_30d_raw, n_bars_used) for one (symbol, market).
    None when insufficient bars."""
    if as_of_date is None:
        as_of_date = datetime.utcnow().strftime("%Y-%m-%d")
    # Pad lookback by 1.5x to account for weekends / holidays
    cutoff_str = (datetime.fromisoformat(as_of_date) -
                  timedelta(days=int(WINDOW_TRADING_DAYS * 1.5))).strftime("%Y-%m-%d")

    rows = conn.execute(
        "SELECT close FROM candles "
        "WHERE symbol=? AND market=? AND timeframe='5m' "
        "AND timestamp >= ? AND timestamp <= ? "
        "AND close > 0.0001 "                     # sanity filter
        "ORDER BY timestamp ASC",
        (symbol, market, cutoff_str, as_of_date)
    ).fetchall()

    if len(rows) < MIN_BARS_REQUIRED:
        return None, len(rows)

    closes = np.array([r["close"] for r in rows], dtype=np.float64)
    returns = np.diff(np.log(closes))
    if len(returns) < MIN_BARS_REQUIRED - 1:
        return None, len(returns)
    sigma = float(np.std(returns, ddof=1))
    return sigma, len(returns)


def run_vol_snapshot(as_of_date=None, markets=("US",)):
    """Compute and persist realized_vol_30d for all active securities in
    the given markets. Returns (n_ok, n_skipped)."""
    if as_of_date is None:
        as_of_date = datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_connection()

    market_filter = ",".join("?" for _ in markets)
    secs = conn.execute(
        f"SELECT symbol, market FROM securities "
        f"WHERE removed_at IS NULL AND market IN ({market_filter})",
        markets
    ).fetchall()
    n_ok = n_skip = 0
    for s in secs:
        sigma, n_bars = compute_realized_vol_for_symbol(
            conn, s["symbol"], s["market"], as_of_date
        )
        if sigma is None:
            n_skip += 1
            continue
        conn.execute(
            "UPDATE securities SET realized_vol_30d=?, realized_vol_snapshot_date=? "
            "WHERE symbol=? AND market=?",
            (sigma, as_of_date, s["symbol"], s["market"])
        )
        conn.execute(
            "INSERT OR REPLACE INTO realized_vol_history "
            "(symbol, market, snapshot_date, realized_vol_30d, n_bars_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (s["symbol"], s["market"], as_of_date, sigma, n_bars)
        )
        n_ok += 1
    conn.commit()
    conn.close()
    print(f"Vol snapshot {as_of_date}: {n_ok} updated, {n_skip} skipped (insufficient bars)")
    return n_ok, n_skip


def annualized(sigma_5m):
    """Convert raw 5m stdev to annualized vol for human reporting."""
    return sigma_5m * np.sqrt(BARS_PER_DAY * 252)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Realized volatility snapshot")
    p.add_argument("--as-of", default=None,
                  help="YYYY-MM-DD snapshot date (default today UTC)")
    p.add_argument("--markets", nargs="+", default=["US"],
                  help="Markets to snapshot (default: US)")
    args = p.parse_args()
    run_vol_snapshot(as_of_date=args.as_of, markets=tuple(args.markets))
