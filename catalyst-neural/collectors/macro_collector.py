"""
Catalyst Neural — Macro Collector

Currencies, yields, VIX, commodities, sector ETFs.
The kingdom contention scoreboard — updated continuously.

This data provides the macro CONTEXT that determines whether
micro-level candle patterns will resolve bullish or bearish.
Same candle pattern, different macro regime, different outcome.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
from storage.database import get_connection, store_macro, log_collection
from config.settings import MACRO_INSTRUMENTS, SECTOR_ETFS


def collect_macro_snapshot():
    """
    Collect current values for all macro instruments.
    Uses Yahoo Finance — free, no API key.
    """
    print(f"\nMacro Snapshot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("-" * 50)
    
    total = 0
    
    for name, config in MACRO_INSTRUMENTS.items():
        yf_symbol = config["yahoo"]
        inst_type = config["type"]
        
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="2d", interval="1d")
            
            if hist.empty:
                print(f"  {name}: no data")
                continue
            
            latest = hist.iloc[-1]
            timestamp = hist.index[-1].strftime("%Y-%m-%dT%H:%M:%S+00:00")
            value = float(latest["Close"])
            
            # Calculate change from previous if we have 2 days
            change_pct = None
            if len(hist) >= 2:
                prev = float(hist.iloc[-2]["Close"])
                if prev != 0:
                    change_pct = round(((value - prev) / prev) * 100, 4)
            
            store_macro(name, inst_type, timestamp, value, change_pct)
            
            direction = ""
            if change_pct is not None:
                direction = f" ({'+' if change_pct > 0 else ''}{change_pct}%)"
            print(f"  {name}: {value:.4f}{direction}")
            total += 1
            
        except Exception as e:
            print(f"  {name}: ERROR — {str(e)[:80]}")
        
        time.sleep(0.3)
    
    log_collection("macro", None, None, "success", total)
    return total


def collect_macro_history(days=30):
    """
    Backfill macro history. Daily resolution.
    """
    print(f"\nMacro Backfill — {days} days")
    print("-" * 50)
    
    total = 0
    
    for name, config in MACRO_INSTRUMENTS.items():
        yf_symbol = config["yahoo"]
        inst_type = config["type"]
        
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=f"{days}d", interval="1d")
            
            if hist.empty:
                continue
            
            stored = 0
            for idx, row in hist.iterrows():
                timestamp = idx.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                value = float(row["Close"])
                store_macro(name, inst_type, timestamp, value)
                stored += 1
            
            print(f"  {name}: {stored} data points")
            total += stored
            
        except Exception as e:
            print(f"  {name}: ERROR — {str(e)[:80]}")
        
        time.sleep(0.3)
    
    return total


def collect_sectors():
    """
    Collect sector ETF data — where is money flowing?
    """
    print(f"\nSector Snapshot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("-" * 50)
    
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    total = 0
    
    for symbol, name in SECTOR_ETFS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1d")
            
            if hist.empty:
                continue
            
            latest = hist.iloc[-1]
            timestamp = hist.index[-1].strftime("%Y-%m-%dT%H:%M:%S+00:00")
            close = float(latest["Close"])
            volume = float(latest.get("Volume", 0))
            
            change_pct = None
            if len(hist) >= 2:
                prev = float(hist.iloc[-2]["Close"])
                if prev != 0:
                    change_pct = round(((close - prev) / prev) * 100, 4)
            
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO sectors
                    (symbol, name, timestamp, close, volume, change_pct, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (symbol, name, timestamp, close, volume, change_pct, now))
                total += 1
            except Exception:
                pass
            
            direction = ""
            if change_pct is not None:
                direction = f" ({'+' if change_pct > 0 else ''}{change_pct}%)"
            print(f"  {symbol} ({name}): {close:.2f}{direction}")
            
        except Exception as e:
            print(f"  {symbol}: ERROR — {str(e)[:80]}")
        
        time.sleep(0.3)
    
    conn.commit()
    conn.close()
    log_collection("sector", None, None, "success", total)
    return total


def collect_sector_history(days=30):
    """Backfill sector ETF history."""
    print(f"\nSector Backfill — {days} days")
    print("-" * 50)
    
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    total = 0
    
    for symbol, name in SECTOR_ETFS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d", interval="1d")
            
            stored = 0
            for idx, row in hist.iterrows():
                timestamp = idx.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO sectors
                        (symbol, name, timestamp, close, volume, change_pct, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (symbol, name, timestamp, float(row["Close"]),
                          float(row.get("Volume", 0)), None, now))
                    stored += 1
                except Exception:
                    pass
            
            print(f"  {symbol}: {stored} data points")
            total += stored
            
        except Exception as e:
            print(f"  {symbol}: ERROR — {str(e)[:80]}")
        
        time.sleep(0.3)
    
    conn.commit()
    conn.close()
    return total


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect macro and sector data")
    parser.add_argument("--backfill", action="store_true", help="Backfill historical data")
    parser.add_argument("--days", type=int, default=30, help="Days of history for backfill")
    args = parser.parse_args()
    
    if args.backfill:
        collect_macro_history(args.days)
        collect_sector_history(args.days)
    else:
        collect_macro_snapshot()
        collect_sectors()
