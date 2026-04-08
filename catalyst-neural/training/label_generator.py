"""
Catalyst Neural — Forward Returns Label Generator

Computes the TRUTH LABELS for training.
Given any point in time, what did the price actually do next?

This runs OFFLINE after data collection. It does not run during collection.
The network learns to predict these forward returns — that's the only objective.
No pattern names. No human interpretation. Just outcomes.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import get_connection, get_active_securities


# Forward horizons in minutes
HORIZONS = {
    "return_5m": 5,
    "return_15m": 15,
    "return_1h": 60,
    "return_4h": 240,
    "return_1d": 1440,
}

# Map candle timeframes to approximate minutes per candle
TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "1d": 1440,
}


def compute_forward_returns(symbol, market, timeframe="5m"):
    """
    For each candle of a security at a given timeframe,
    compute the forward return at each horizon.
    
    Forward return = (future_close - current_close) / current_close * 100
    """
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    
    # Get all candles for this security/timeframe, ordered by time
    candles = conn.execute("""
        SELECT id, timestamp, close FROM candles
        WHERE symbol = ? AND market = ? AND timeframe = ?
        ORDER BY timestamp ASC
    """, (symbol, market, timeframe)).fetchall()
    
    if len(candles) < 2:
        print(f"  {symbol} ({timeframe}): insufficient data ({len(candles)} candles)")
        conn.close()
        return 0
    
    candles = [dict(c) for c in candles]
    tf_minutes = TIMEFRAME_MINUTES.get(timeframe, 5)
    
    computed = 0
    
    for i, candle in enumerate(candles):
        current_close = candle["close"]
        current_ts = candle["timestamp"]
        
        if current_close == 0:
            continue
        
        returns = {}
        
        for label, horizon_minutes in HORIZONS.items():
            # How many candles forward for this horizon?
            candles_forward = horizon_minutes // tf_minutes
            
            if candles_forward == 0:
                candles_forward = 1
            
            future_idx = i + candles_forward
            
            if future_idx < len(candles):
                future_close = candles[future_idx]["close"]
                fwd_return = ((future_close - current_close) / current_close) * 100
                returns[label] = round(fwd_return, 6)
            else:
                returns[label] = None
        
        # Only store if we have at least some forward returns
        if any(v is not None for v in returns.values()):
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO forward_returns
                    (symbol, market, timestamp, timeframe,
                     return_5m, return_15m, return_1h, return_4h, return_1d,
                     computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, market, current_ts, timeframe,
                    returns.get("return_5m"),
                    returns.get("return_15m"),
                    returns.get("return_1h"),
                    returns.get("return_4h"),
                    returns.get("return_1d"),
                    now
                ))
                computed += 1
            except Exception as e:
                print(f"  Error computing return for {symbol} at {current_ts}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"  {symbol} ({timeframe}): {computed} forward returns computed")
    return computed


def compute_all(timeframe="5m"):
    """
    Compute forward returns for all active securities.
    """
    print(f"\n{'='*60}")
    print(f"Forward Returns Computation — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Timeframe: {timeframe}")
    print(f"{'='*60}\n")
    
    securities = get_active_securities()
    total = 0
    
    for sec in securities:
        total += compute_forward_returns(sec["symbol"], sec["market"], timeframe)
    
    print(f"\nTotal forward returns computed: {total}")
    return total


def show_stats():
    """Show statistics on computed labels."""
    conn = get_connection()
    
    stats = conn.execute("""
        SELECT symbol, market, timeframe, 
               COUNT(*) as total,
               SUM(CASE WHEN return_5m IS NOT NULL THEN 1 ELSE 0 END) as has_5m,
               SUM(CASE WHEN return_1h IS NOT NULL THEN 1 ELSE 0 END) as has_1h,
               SUM(CASE WHEN return_1d IS NOT NULL THEN 1 ELSE 0 END) as has_1d,
               AVG(return_5m) as avg_5m,
               AVG(return_1h) as avg_1h
        FROM forward_returns
        GROUP BY symbol, market, timeframe
        ORDER BY symbol
    """).fetchall()
    
    if not stats:
        print("No forward returns computed yet.")
        conn.close()
        return
    
    print(f"\n{'Symbol':<10} {'Market':<6} {'TF':<5} {'Total':<8} {'5m':<6} {'1h':<6} {'1d':<6} {'Avg 5m%':<10} {'Avg 1h%':<10}")
    print("-" * 75)
    
    for row in stats:
        r = dict(row)
        avg_5m = f"{r['avg_5m']:.4f}" if r['avg_5m'] else "—"
        avg_1h = f"{r['avg_1h']:.4f}" if r['avg_1h'] else "—"
        print(f"{r['symbol']:<10} {r['market']:<6} {r['timeframe']:<5} "
              f"{r['total']:<8} {r['has_5m']:<6} {r['has_1h']:<6} {r['has_1d']:<6} "
              f"{avg_5m:<10} {avg_1h:<10}")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compute forward return labels")
    parser.add_argument("--timeframe", type=str, default="5m", help="Timeframe to compute for")
    parser.add_argument("--stats", action="store_true", help="Show label statistics")
    parser.add_argument("--all-timeframes", action="store_true", help="Compute for all timeframes")
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.all_timeframes:
        for tf in ["1m", "5m", "15m"]:
            compute_all(tf)
    else:
        compute_all(args.timeframe)
