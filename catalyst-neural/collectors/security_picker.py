"""
Catalyst Neural — Security Picker

Two sources of securities to watch:

1. DROPLET PICKS — what the Catalyst scanners (scanner.py) on the droplet
   are finding and what the agents are trading. These are the informed picks
   from the existing brain. Polled via the consciousness MCP API.

2. INDEPENDENT BIG MOVERS — since we're collecting training data (not trading),
   we cast a wider net. Scan for the biggest movers across US and HKEX markets.
   The network might discover patterns the current rule-based system misses.

Both sources feed into the local SQLite watch list. The candle collector
then streams data for everything on the watch list.

"You will know them by their fruits." — Matthew 7:16
We don't pre-judge which securities matter. We record them all. The network
learns which conditions around which securities produce which outcomes.
"""

import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
from storage.database import add_security, get_active_securities, get_connection
from config.settings import CONSCIOUSNESS_URL


# ─────────────────────────────────────────────────────────
# PATH 1: Droplet Picks — via Catalyst Consciousness API
# ─────────────────────────────────────────────────────────

def poll_droplet_picks():
    """
    Query the Catalyst consciousness API to find what securities
    the droplet scanners are watching and agents are trading.
    
    Sources:
    - Trading observations (what has been traded recently)
    - Market observations (what the scanner has flagged)
    - Active positions (what's currently held)
    """
    picks = []
    
    # 1. Get trading overview — see what positions exist
    try:
        resp = requests.post(
            f"{CONSCIOUSNESS_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_trading_overview",
                    "arguments": {}
                }
            },
            timeout=15
        )
        if resp.ok:
            data = resp.json()
            result = data.get("result", {})
            # Parse positions from the trading overview
            # The structure depends on the MCP server implementation
            if isinstance(result, dict):
                content = result.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        # Parse JSON response for position symbols
                        try:
                            import json
                            overview = json.loads(text)
                            # HKEX positions
                            hkex = overview.get("hkex_trading", {})
                            if hkex.get("open_positions", 0) > 0:
                                print(f"  Droplet: {hkex['open_positions']} HKEX positions open")
                            # US positions
                            us = overview.get("us_trading", {})
                            if us.get("open_positions", 0) > 0:
                                print(f"  Droplet: {us['open_positions']} US positions open")
                        except (json.JSONDecodeError, KeyError):
                            pass
            print("  Droplet trading overview checked")
    except requests.exceptions.ConnectionError:
        print("  Droplet not reachable — skipping droplet picks")
        return picks
    except Exception as e:
        print(f"  Droplet error: {str(e)[:100]}")
        return picks
    
    # 2. Get market observations — what have the scanners flagged?
    try:
        resp = requests.post(
            f"{CONSCIOUSNESS_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_observations",
                    "arguments": {
                        "observation_type": "market",
                        "limit": 20
                    }
                }
            },
            timeout=15
        )
        if resp.ok:
            data = resp.json()
            result = data.get("result", {})
            content = result.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    try:
                        import json
                        obs_data = json.loads(item.get("text", ""))
                        observations = obs_data.get("observations", [])
                        for obs in observations:
                            subject = obs.get("subject", "")
                            content_text = obs.get("content", "")
                            market = obs.get("market", "")
                            
                            # Extract symbols from observations
                            # Common patterns: "BUY 1024", "Exit 1024", "Trade Result: 1024"
                            symbols = extract_symbols_from_text(
                                f"{subject} {content_text}", market
                            )
                            for sym, mkt in symbols:
                                picks.append({
                                    "symbol": sym,
                                    "market": mkt,
                                    "source": "droplet_observation",
                                    "reason": subject[:100]
                                })
                    except (json.JSONDecodeError, KeyError):
                        pass
            print(f"  Droplet observations checked — {len(picks)} symbols found")
    except Exception as e:
        print(f"  Observation error: {str(e)[:100]}")
    
    return picks


def extract_symbols_from_text(text, market_hint=""):
    """
    Extract stock symbols from observation text.
    HKEX symbols are numeric (e.g. 1024, 9988).
    US symbols are alphabetic (e.g. AAPL, NVDA).
    """
    import re
    symbols = []
    
    # HKEX numeric symbols (3-5 digits)
    if market_hint == "HKEX" or not market_hint:
        hkex_matches = re.findall(r'\b(\d{3,5})\b', text)
        for match in hkex_matches:
            num = int(match)
            # Filter out unlikely stock codes (years, prices, etc.)
            if 1 <= num <= 9999 and num not in [2026, 2025, 2024, 2023]:
                symbols.append((match, "HKEX"))
    
    # US alphabetic symbols (1-5 uppercase letters)
    if market_hint == "US" or not market_hint:
        # Look for patterns like "BUY AAPL" or ticker mentions
        us_matches = re.findall(r'\b([A-Z]{1,5})\b', text)
        # Filter common non-ticker words
        noise = {"BUY", "SELL", "THE", "AND", "FOR", "NOT", "ALL", "NEW",
                 "HKD", "USD", "EUR", "CNY", "JPY", "GBP", "AUD",
                 "HKEX", "NYSE", "API", "MCP", "UTC", "EST", "PST",
                 "EXIT", "STOP", "LOSS", "TAKE", "PROFIT", "ORDER",
                 "NULL", "TRUE", "FALSE", "CRITICAL", "WARNING", "INFO"}
        for match in us_matches:
            if match not in noise and len(match) >= 2:
                symbols.append((match, "US"))
    
    return symbols


# ─────────────────────────────────────────────────────────
# PATH 2: Independent Big Mover Scan — via Yahoo Finance
# ─────────────────────────────────────────────────────────

# Well-known big movers and liquid stocks for training data
US_UNIVERSE = [
    # Mega-cap tech — most liquid, most reactive to news
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # Semiconductors — kingdom contention (US vs China)
    "AMD", "INTC", "AVGO", "TSM", "QCOM", "MU",
    # Finance — interest rate sensitive
    "JPM", "BAC", "GS", "MS", "WFC",
    # Energy — oil/geopolitics
    "XOM", "CVX", "COP", "SLB",
    # Defence — war/conflict sensitive
    "LMT", "RTX", "NOC", "GD",
    # Consumer — sentiment indicator
    "WMT", "COST", "TGT", "NKE",
    # Healthcare
    "UNH", "JNJ", "PFE", "LLY",
    # ETFs for sector tracking
    "SPY", "QQQ", "IWM", "DIA",
]

HKEX_UNIVERSE = [
    # Major tech — US-China dynamics
    "9988",  # Alibaba
    "9888",  # Baidu
    "9618",  # JD.com
    "3690",  # Meituan
    "1810",  # Xiaomi
    "2015",  # Li Auto
    "9866",  # NIO
    "9868",  # XPeng
    # Semiconductors
    "981",   # SMIC
    "2382",  # Sunny Optical
    "1347",  # Hua Hong Semi
    # Finance
    "1398",  # ICBC
    "3988",  # Bank of China
    "2318",  # Ping An
    # Property (distressed sector — telling indicator)
    "3333",  # Evergrande (if still trading)
    "2007",  # Country Garden
    # Telecoms
    "941",   # China Mobile
    "762",   # China Unicom
    # Energy
    "883",   # CNOOC
    "857",   # PetroChina
    # Index trackers
    "2800",  # Tracker Fund (HSI ETF)
    "2823",  # iShares FTSE A50
]


def scan_big_movers_us(min_change_pct=3.0, min_volume=1_000_000):
    """
    Scan US universe for big movers — securities with significant
    price change and volume. These are where the psychology is visible.
    """
    movers = []
    
    print(f"\n  Scanning US universe ({len(US_UNIVERSE)} securities)...")
    
    # Batch download for efficiency
    try:
        symbols_str = " ".join(US_UNIVERSE)
        data = yf.download(symbols_str, period="2d", interval="1d",
                          group_by="ticker", progress=False, threads=True)
        
        for symbol in US_UNIVERSE:
            try:
                if len(US_UNIVERSE) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[symbol]
                
                if ticker_data.empty or len(ticker_data) < 2:
                    continue
                
                latest = ticker_data.iloc[-1]
                previous = ticker_data.iloc[-2]
                
                close = float(latest["Close"])
                prev_close = float(previous["Close"])
                volume = float(latest.get("Volume", 0))
                
                if prev_close == 0:
                    continue
                
                change_pct = ((close - prev_close) / prev_close) * 100
                
                movers.append({
                    "symbol": symbol,
                    "market": "US",
                    "close": close,
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                    "is_big_mover": abs(change_pct) >= min_change_pct and volume >= min_volume
                })
                
            except (KeyError, IndexError):
                continue
        
    except Exception as e:
        print(f"  US scan error: {str(e)[:100]}")
    
    big = [m for m in movers if m["is_big_mover"]]
    print(f"  US: {len(movers)} scanned, {len(big)} big movers (>{min_change_pct}% change)")
    
    return movers


def scan_big_movers_hkex(min_change_pct=3.0, min_volume=500_000):
    """
    Scan HKEX universe for big movers.
    """
    movers = []
    
    print(f"\n  Scanning HKEX universe ({len(HKEX_UNIVERSE)} securities)...")
    
    # HKEX symbols need .HK suffix for Yahoo
    yf_symbols = [f"{s.zfill(4)}.HK" for s in HKEX_UNIVERSE]
    
    try:
        symbols_str = " ".join(yf_symbols)
        data = yf.download(symbols_str, period="2d", interval="1d",
                          group_by="ticker", progress=False, threads=True)
        
        for i, symbol in enumerate(HKEX_UNIVERSE):
            yf_sym = yf_symbols[i]
            try:
                if len(HKEX_UNIVERSE) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[yf_sym]
                
                if ticker_data.empty or len(ticker_data) < 2:
                    continue
                
                latest = ticker_data.iloc[-1]
                previous = ticker_data.iloc[-2]
                
                close = float(latest["Close"])
                prev_close = float(previous["Close"])
                volume = float(latest.get("Volume", 0))
                
                if prev_close == 0:
                    continue
                
                change_pct = ((close - prev_close) / prev_close) * 100
                
                movers.append({
                    "symbol": symbol,
                    "market": "HKEX",
                    "close": close,
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                    "is_big_mover": abs(change_pct) >= min_change_pct and volume >= min_volume
                })
                
            except (KeyError, IndexError):
                continue
        
    except Exception as e:
        print(f"  HKEX scan error: {str(e)[:100]}")
    
    big = [m for m in movers if m["is_big_mover"]]
    print(f"  HKEX: {len(movers)} scanned, {len(big)} big movers (>{min_change_pct}% change)")
    
    return movers


# ─────────────────────────────────────────────────────────
# COMBINED: Both paths feed into the watch list
# ─────────────────────────────────────────────────────────

def update_watch_list(
    include_droplet=True,
    include_movers=True,
    add_full_universe=False,
    mover_threshold=3.0
):
    """
    Update the local watch list from both sources.
    
    For training data, we want EVERYTHING that's moving.
    We're not trading — we're recording the field.
    """
    print(f"\n{'='*60}")
    print(f"Security Picker — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    
    added = 0
    
    # PATH 1: Droplet picks
    if include_droplet:
        print("\n--- Path 1: Droplet Picks ---")
        droplet_picks = poll_droplet_picks()
        for pick in droplet_picks:
            add_security(
                pick["symbol"], pick["market"],
                source=pick.get("source", "droplet"),
                reason=pick.get("reason", "")
            )
            added += 1
    
    # PATH 2: Independent big mover scan
    if include_movers:
        print("\n--- Path 2: Big Mover Scan ---")
        
        us_movers = scan_big_movers_us(min_change_pct=mover_threshold)
        for m in us_movers:
            if m["is_big_mover"]:
                add_security(
                    m["symbol"], "US",
                    source="mover_scan",
                    reason=f"Change: {m['change_pct']}%, Vol: {m['volume']:,.0f}"
                )
                added += 1
        
        hkex_movers = scan_big_movers_hkex(min_change_pct=mover_threshold)
        for m in hkex_movers:
            if m["is_big_mover"]:
                add_security(
                    m["symbol"], "HKEX",
                    source="mover_scan",
                    reason=f"Change: {m['change_pct']}%, Vol: {m['volume']:,.0f}"
                )
                added += 1
    
    # OPTION: Add entire universe for broad training data
    if add_full_universe:
        print("\n--- Adding Full Universe ---")
        for sym in US_UNIVERSE:
            add_security(sym, "US", source="universe", reason="US training universe")
        for sym in HKEX_UNIVERSE:
            add_security(sym, "HKEX", source="universe", reason="HKEX training universe")
        print(f"  Added {len(US_UNIVERSE)} US + {len(HKEX_UNIVERSE)} HKEX to universe")
    
    # Show current watch list
    print(f"\n--- Current Watch List ---")
    securities = get_active_securities()
    us = [s for s in securities if s["market"] == "US"]
    hkex = [s for s in securities if s["market"] == "HKEX"]
    print(f"  US: {len(us)} securities")
    print(f"  HKEX: {len(hkex)} securities")
    print(f"  Total: {len(securities)}")
    
    return added


def show_movers():
    """Show current big movers without adding to watch list."""
    print(f"\n{'='*60}")
    print(f"Market Movers — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    
    us = scan_big_movers_us()
    hkex = scan_big_movers_hkex()
    
    # Sort by absolute change
    all_movers = sorted(us + hkex, key=lambda x: abs(x["change_pct"]), reverse=True)
    
    print(f"\n{'Symbol':<10} {'Market':<6} {'Close':>10} {'Change%':>10} {'Volume':>15}")
    print("-" * 55)
    
    for m in all_movers[:30]:
        direction = "+" if m["change_pct"] > 0 else ""
        big = " ***" if m["is_big_mover"] else ""
        print(f"{m['symbol']:<10} {m['market']:<6} {m['close']:>10.2f} "
              f"{direction}{m['change_pct']:>9.2f}% {m['volume']:>14,.0f}{big}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pick securities for data collection")
    parser.add_argument("--movers", action="store_true", help="Show big movers (no add)")
    parser.add_argument("--droplet", action="store_true", help="Poll droplet only")
    parser.add_argument("--universe", action="store_true", help="Add full universe")
    parser.add_argument("--threshold", type=float, default=3.0,
                        help="Big mover threshold (default 3%%)")
    parser.add_argument("--update", action="store_true", help="Update watch list from all sources")
    args = parser.parse_args()
    
    if args.movers:
        show_movers()
    elif args.droplet:
        update_watch_list(include_droplet=True, include_movers=False)
    elif args.universe:
        update_watch_list(include_droplet=False, include_movers=False, add_full_universe=True)
    elif args.update:
        update_watch_list(
            include_droplet=True,
            include_movers=True,
            mover_threshold=args.threshold
        )
    else:
        # Default: show movers and update
        update_watch_list(mover_threshold=args.threshold)
