#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: show_positions.py
Version: 1.0.0
Last Updated: 2026-01-06
Purpose: Display current positions with bracket prices
"""

import sys
sys.path.insert(0, '/root/Catalyst-Trading-System-International/catalyst-international')

from brokers.moomoo import MoomooClient
from futu import OpenQuoteContext, RET_OK

# Bracket prices from database/logs
BRACKETS = {
    '9868': {'sl': 78.6, 'tp': 85.0},
    '1211': {'sl': 96.0, 'tp': 100.5},
    '1024': {'sl': 74.0, 'tp': 78.0},
    '2382': {'sl': None, 'tp': None},
}

def main():
    client = MoomooClient()
    client.connect()

    positions = client.get_positions()
    pos_dict = {p.symbol: p for p in positions}

    if not positions:
        print("No open positions")
        client.disconnect()
        return

    # Get live quotes
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    symbols = [f'HK.0{p.symbol}' if len(p.symbol) == 4 else f'HK.{p.symbol}' for p in positions]
    ret, data = quote_ctx.get_market_snapshot(symbols)

    # Header
    print()
    print("=" * 85)
    print("                         OPEN POSITIONS")
    print("=" * 85)
    print()
    print(f"{'Symbol':<8} {'Qty':>7} {'Avg':>9} {'Last':>9} {'SL':>9} {'TP':>9} {'P&L':>12}")
    print("-" * 85)

    total_pnl = 0
    if ret == RET_OK:
        for _, row in data.iterrows():
            sym = row['code'].replace('HK.', '').lstrip('0')
            if sym in pos_dict:
                p = pos_dict[sym]
                b = BRACKETS.get(sym, {})
                sl = b.get('sl')
                tp = b.get('tp')

                pnl = (row['last_price'] - p.avg_cost) * p.quantity
                total_pnl += pnl

                sl_str = f"{sl:.2f}" if sl else "-"
                tp_str = f"{tp:.2f}" if tp else "-"

                print(f"{sym:<8} {p.quantity:>7,} {p.avg_cost:>9.2f} {row['last_price']:>9.2f} {sl_str:>9} {tp_str:>9} {pnl:>+12,.0f}")

    print("-" * 85)
    print(f"{'TOTAL':<8} {'':<7} {'':<9} {'':<9} {'':<9} {'':<9} {total_pnl:>+12,.0f}")
    print("=" * 85)

    # Portfolio summary
    portfolio = client.get_portfolio()
    print()
    print(f"Cash:   HKD {portfolio['cash']:>15,.2f}")
    print(f"Equity: HKD {portfolio['equity']:>15,.2f}")
    print()

    quote_ctx.close()
    client.disconnect()

if __name__ == "__main__":
    main()
