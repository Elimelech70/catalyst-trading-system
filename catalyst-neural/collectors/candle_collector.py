"""
Catalyst Neural — Candle Collector

Collects raw OHLCV candle data for watched securities.
Uses Yahoo Finance (free, no API key) as primary source.
Alpaca available as upgrade for real-time US streaming.

This is a RECORDER. It captures what happened. No interpretation.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
from storage.database import (
    get_connection, store_candles, get_active_securities,
    log_collection, add_security
)
from config.settings import CANDLE_TIMEFRAMES, BACKFILL_DAYS


# Yahoo Finance timeframe mapping
YF_INTERVALS = {
    "1m": "1m",    # max 7 days history
    "5m": "5m",    # max 60 days history
    "15m": "15m",  # max 60 days history
    "1h": "1h",    # max 730 days history
    "1d": "1d",    # unlimited history
}

YF_MAX_DAYS = {
    "1m": 7,
    "5m": 60,
    "15m": 60,
    "1h": 730,
    "1d": 3650,
}


def yahoo_symbol(symbol, market):
    """Convert symbol to Yahoo Finance format."""
    if market == "HKEX":
        # HKEX symbols: pad to 4 digits, add .HK
        num = str(symbol).zfill(4)
        return f"{num}.HK"
    return symbol  # US symbols work as-is


def collect_candles_for_security(symbol, market, timeframe="5m", days=None):
    """
    Collect candle data for a single security.
    Returns number of candles stored.
    """
    yf_symbol = yahoo_symbol(symbol, market)
    
    if days is None:
        days = min(BACKFILL_DAYS, YF_MAX_DAYS.get(timeframe, 30))
    else:
        days = min(days, YF_MAX_DAYS.get(timeframe, 30))

    yf_interval = YF_INTERVALS.get(timeframe, "5m")
    
    try:
        ticker = yf.Ticker(yf_symbol)
        
        # Calculate period
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=yf_interval,
            auto_adjust=True
        )
        
        if df.empty:
            print(f"  No data for {yf_symbol} ({timeframe})")
            log_collection("candle", symbol, market, "partial", 0, "No data returned")
            return 0
        
        # Convert to our format
        candles = []
        for idx, row in df.iterrows():
            timestamp = idx.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            candles.append({
                "symbol": symbol,
                "market": market,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0)),
            })
        
        stored = store_candles(candles)
        log_collection("candle", symbol, market, "success", stored)
        print(f"  {yf_symbol} ({timeframe}): {stored} candles stored")
        return stored
        
    except Exception as e:
        error_msg = str(e)[:200]
        print(f"  ERROR {yf_symbol} ({timeframe}): {error_msg}")
        log_collection("candle", symbol, market, "error", 0, error_msg)
        return 0


def collect_all(timeframes=None, days=None, market=None):
    """
    Collect candle data for active securities across all timeframes.
    If market is specified, only collect for that market.
    """
    if timeframes is None:
        timeframes = CANDLE_TIMEFRAMES

    securities = get_active_securities(market=market)
    
    if not securities:
        print("No active securities in watch list.")
        print("Add securities first:")
        print("  from storage.database import add_security")
        print("  add_security('AAPL', 'US', name='Apple', source='manual')")
        return
    
    total_stored = 0
    
    print(f"\n{'='*60}")
    print(f"Candle Collection Run — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Securities: {len(securities)}, Timeframes: {timeframes}")
    print(f"{'='*60}\n")
    
    for sec in securities:
        symbol = sec["symbol"]
        market = sec["market"]
        print(f"\n[{symbol}] ({market})")
        
        for tf in timeframes:
            stored = collect_candles_for_security(symbol, market, tf, days)
            total_stored += stored
            time.sleep(0.5)  # rate limiting — be respectful
    
    print(f"\n{'='*60}")
    print(f"Collection complete. Total candles stored: {total_stored}")
    print(f"{'='*60}\n")
    
    return total_stored


def backfill(days=None):
    """
    Backfill historical data for all active securities.
    Uses maximum available history per timeframe.
    """
    if days is None:
        days = BACKFILL_DAYS
    
    print(f"Backfilling {days} days of historical data...")
    return collect_all(days=days)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect candle data")
    parser.add_argument("--backfill", action="store_true", help="Backfill historical data")
    parser.add_argument("--days", type=int, default=None, help="Days of history")
    parser.add_argument("--timeframe", type=str, default=None, help="Single timeframe (1m,5m,15m)")
    parser.add_argument("--add", type=str, default=None, help="Add security: SYMBOL:MARKET (e.g. AAPL:US)")
    args = parser.parse_args()
    
    if args.add:
        parts = args.add.split(":")
        if len(parts) == 2:
            add_security(parts[0].upper(), parts[1].upper(), source="manual")
        else:
            print("Format: SYMBOL:MARKET (e.g. AAPL:US or 9988:HKEX)")
    elif args.backfill:
        backfill(args.days)
    else:
        timeframes = [args.timeframe] if args.timeframe else None
        collect_all(timeframes=timeframes, days=args.days)
