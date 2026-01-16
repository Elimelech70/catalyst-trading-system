#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: generate_daily_report_db.py
Version: 2.0.1
Last Updated: 2026-01-16
Purpose: Generate daily US trading report and store in consciousness database

REVISION HISTORY:
v2.0.1 (2026-01-16) - Fix schema mismatch
- Changed stopped_at -> ended_at in trading_cycles query
- Aligns with catalyst_dev database schema

v2.0.0 (2026-01-01) - Database storage version
- Store reports in claude_reports table (not GitHub)
- Add structured metrics JSONB for dashboard
- Support both trading DB and research DB connections
- Called by public_claude agent or cron

v1.0.0 (2025-12-10) - Original GitHub version
- Generated markdown files
- Pushed to GitHub repository

Description:
Generates daily US trading report by:
1. Querying trading data from catalyst_public database
2. Getting account/positions from Alpaca API
3. Storing report in claude_reports table (catalyst_research)
4. Metrics available for dashboard display
"""

import os
import sys
import asyncio
import asyncpg
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
from typing import Optional, Dict, List, Any

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("Warning: Alpaca SDK not available")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Trading database (catalyst_public)
TRADING_DB_URL = os.getenv("DATABASE_URL")

# Research/consciousness database (catalyst_research)  
RESEARCH_DB_URL = os.getenv("RESEARCH_DATABASE_URL")

# Alpaca credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

# Agent identity
AGENT_ID = os.getenv("AGENT_ID", "public_claude")
MARKET = "US"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# =============================================================================
# DATA FETCHING - TRADING DATABASE
# =============================================================================

async def get_trading_cycles(conn: asyncpg.Connection, report_date: date) -> List[Dict]:
    """Get trading cycles for the report date"""
    cycle_prefix = report_date.strftime("%Y%m%d")
    
    cycles = await conn.fetch("""
        SELECT
            cycle_id,
            mode,
            status,
            started_at AT TIME ZONE 'America/New_York' as started_et,
            ended_at AT TIME ZONE 'America/New_York' as ended_et
        FROM trading_cycles
        WHERE cycle_id LIKE $1
        ORDER BY started_at
    """, f"{cycle_prefix}%")
    
    return [dict(c) for c in cycles]


async def get_positions_opened(conn: asyncpg.Connection, report_date: date) -> List[Dict]:
    """Get positions opened on the report date"""
    cycle_prefix = report_date.strftime("%Y%m%d")
    
    positions = await conn.fetch("""
        SELECT
            p.position_id,
            p.cycle_id,
            s.symbol,
            p.side,
            p.quantity,
            p.entry_price,
            p.exit_price,
            p.status,
            p.realized_pnl,
            p.unrealized_pnl,
            -- p.alpaca_status removed (column does not exist)
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.cycle_id LIKE $1
        ORDER BY p.opened_at
    """, f"{cycle_prefix}%")
    
    return [dict(p) for p in positions]


async def get_positions_closed(conn: asyncpg.Connection, report_date: date) -> List[Dict]:
    """Get positions closed on the report date"""
    positions = await conn.fetch("""
        SELECT
            p.position_id,
            p.cycle_id,
            s.symbol,
            p.side,
            p.quantity,
            p.entry_price,
            p.exit_price,
            p.realized_pnl,
            p.closed_at AT TIME ZONE 'America/New_York' as closed_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.status = 'closed'
          AND DATE(p.closed_at AT TIME ZONE 'America/New_York') = $1
        ORDER BY p.closed_at
    """, report_date)
    
    return [dict(p) for p in positions]


async def get_all_open_positions(conn: asyncpg.Connection) -> List[Dict]:
    """Get all currently open positions from database"""
    positions = await conn.fetch("""
        SELECT
            p.position_id,
            s.symbol,
            p.side,
            p.quantity,
            p.entry_price,
            p.status,
            p.unrealized_pnl,
            -- p.alpaca_status removed (column does not exist)
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.status = 'open'
        ORDER BY p.opened_at DESC
    """)
    
    return [dict(p) for p in positions]


async def get_scan_results(conn: asyncpg.Connection, report_date: date) -> List[Dict]:
    """Get scan results for the report date"""
    cycle_prefix = report_date.strftime("%Y%m%d")
    
    scans = await conn.fetch("""
        SELECT
            sr.cycle_id,
            s.symbol,
            sr.price,
            sr.volume,
            sr.rank,
            sr.selected_for_trading
        FROM scan_results sr
        JOIN securities s ON s.security_id = sr.security_id
        WHERE sr.cycle_id LIKE $1
        ORDER BY sr.cycle_id, sr.rank
    """, f"{cycle_prefix}%")
    
    return [dict(s) for s in scans]


# =============================================================================
# DATA FETCHING - ALPACA API
# =============================================================================

def get_alpaca_account() -> Optional[Dict]:
    """Get account info from Alpaca"""
    if not ALPACA_AVAILABLE or not ALPACA_API_KEY:
        return None
    
    try:
        client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "long_market_value": float(account.long_market_value),
            "short_market_value": float(account.short_market_value),
            "portfolio_value": float(account.portfolio_value),
            "last_equity": float(account.last_equity),
            "daytrade_count": account.daytrade_count,
        }
    except Exception as e:
        print(f"Error getting Alpaca account: {e}")
        return None


def get_alpaca_positions() -> List[Dict]:
    """Get positions from Alpaca"""
    if not ALPACA_AVAILABLE or not ALPACA_API_KEY:
        return []
    
    try:
        client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
        positions = client.get_all_positions()
        return [{
            "symbol": p.symbol,
            "qty": float(p.qty),
            "side": p.side.value if hasattr(p.side, 'value') else str(p.side),
            "market_value": float(p.market_value),
            "cost_basis": float(p.cost_basis),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
            "current_price": float(p.current_price),
            "avg_entry_price": float(p.avg_entry_price),
        } for p in positions]
    except Exception as e:
        print(f"Error getting Alpaca positions: {e}")
        return []


# =============================================================================
# REPORT GENERATION
# =============================================================================

def calculate_metrics(
    alpaca_account: Optional[Dict],
    alpaca_positions: List[Dict],
    positions_opened: List[Dict],
    positions_closed: List[Dict],
    cycles: List[Dict]
) -> Dict:
    """Calculate structured metrics for dashboard"""
    
    metrics = {
        "positions_open": len(alpaca_positions),
        "positions_opened_today": len(positions_opened),
        "positions_closed_today": len(positions_closed),
        "trading_cycles": len(cycles),
    }
    
    # Account metrics
    if alpaca_account:
        daily_change = alpaca_account['equity'] - alpaca_account['last_equity']
        metrics.update({
            "account_value": alpaca_account['portfolio_value'],
            "cash": alpaca_account['cash'],
            "buying_power": alpaca_account['buying_power'],
            "equity": alpaca_account['equity'],
            "daily_pnl": daily_change,
            "daily_pnl_pct": (daily_change / alpaca_account['last_equity'] * 100) if alpaca_account['last_equity'] else 0,
        })
    
    # Position P&L
    if alpaca_positions:
        total_unrealized = sum(p['unrealized_pl'] for p in alpaca_positions)
        winners = len([p for p in alpaca_positions if p['unrealized_pl'] > 0])
        metrics.update({
            "total_unrealized_pnl": total_unrealized,
            "winning_positions": winners,
            "losing_positions": len(alpaca_positions) - winners,
            "win_rate": winners / len(alpaca_positions) if alpaca_positions else 0,
        })
    
    # Realized P&L from closed positions
    if positions_closed:
        realized_pnl = sum(float(p['realized_pnl'] or 0) for p in positions_closed)
        metrics["realized_pnl_today"] = realized_pnl
    
    return metrics


def generate_report_content(
    report_date: date,
    cycles: List[Dict],
    positions_opened: List[Dict],
    positions_closed: List[Dict],
    scans: List[Dict],
    db_open_positions: List[Dict],
    alpaca_account: Optional[Dict],
    alpaca_positions: List[Dict]
) -> str:
    """Generate markdown report content"""
    
    now = datetime.utcnow()
    lines = []
    
    # Header
    lines.append(f"# US Daily Trading Report - {report_date.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append(f"**Agent:** {AGENT_ID}")
    lines.append(f"**Mode:** {'Paper' if ALPACA_PAPER else 'Live'} Trading (Alpaca)")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Account Summary
    lines.append("## Account Summary")
    lines.append("")
    
    if alpaca_account:
        daily_change = alpaca_account['equity'] - alpaca_account['last_equity']
        daily_pct = (daily_change / alpaca_account['last_equity'] * 100) if alpaca_account['last_equity'] else 0
        sign = "+" if daily_change >= 0 else ""
        
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Portfolio Value | ${alpaca_account['portfolio_value']:,.2f} |")
        lines.append(f"| Cash | ${alpaca_account['cash']:,.2f} |")
        lines.append(f"| Long Market Value | ${alpaca_account['long_market_value']:,.2f} |")
        lines.append(f"| Buying Power | ${alpaca_account['buying_power']:,.2f} |")
        lines.append(f"| **Daily P&L** | **{sign}${daily_change:,.2f} ({sign}{daily_pct:.2f}%)** |")
    else:
        lines.append("*Alpaca account data unavailable*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Trading Cycles
    lines.append("## Trading Cycles")
    lines.append("")
    
    if cycles:
        lines.append("| Cycle ID | Mode | Status | Started (ET) | Stopped (ET) |")
        lines.append("|----------|------|--------|--------------|--------------|")
        for c in cycles:
            started = c['started_et'].strftime('%H:%M:%S') if c['started_et'] else '-'
            ended = c['ended_et'].strftime('%H:%M:%S') if c['ended_et'] else '-'
            lines.append(f"| {c['cycle_id']} | {c['mode']} | {c['status']} | {started} | {ended} |")
    else:
        lines.append("*No trading cycles executed*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Positions Opened Today
    lines.append("## Positions Opened Today")
    lines.append("")
    
    if positions_opened:
        total_capital = sum(p['quantity'] * float(p['entry_price']) for p in positions_opened)
        lines.append(f"**Count:** {len(positions_opened)} | **Capital:** ${total_capital:,.2f}")
        lines.append("")
        lines.append("| Symbol | Side | Qty | Entry | Capital |")
        lines.append("|--------|------|-----|-------|---------|")
        for p in positions_opened:
            capital = p['quantity'] * float(p['entry_price'])
            lines.append(f"| {p['symbol']} | {p['side']} | {p['quantity']} | ${float(p['entry_price']):,.2f} | ${capital:,.2f} |")
    else:
        lines.append("*No positions opened*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Positions Closed Today
    lines.append("## Positions Closed Today")
    lines.append("")
    
    if positions_closed:
        total_realized = sum(float(p['realized_pnl'] or 0) for p in positions_closed)
        sign = "+" if total_realized >= 0 else ""
        lines.append(f"**Count:** {len(positions_closed)} | **Realized P&L:** {sign}${total_realized:,.2f}")
        lines.append("")
        lines.append("| Symbol | Side | Qty | Entry | Exit | P&L |")
        lines.append("|--------|------|-----|-------|------|-----|")
        for p in positions_closed:
            pnl = float(p['realized_pnl'] or 0)
            sign = "+" if pnl >= 0 else ""
            lines.append(f"| {p['symbol']} | {p['side']} | {p['quantity']} | ${float(p['entry_price']):,.2f} | ${float(p['exit_price'] or 0):,.2f} | {sign}${pnl:,.2f} |")
    else:
        lines.append("*No positions closed*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Current Open Positions (from Alpaca)
    lines.append("## Current Open Positions")
    lines.append("")
    
    if alpaca_positions:
        total_value = sum(p['market_value'] for p in alpaca_positions)
        total_pnl = sum(p['unrealized_pl'] for p in alpaca_positions)
        sign = "+" if total_pnl >= 0 else ""
        
        lines.append(f"**Count:** {len(alpaca_positions)} | **Value:** ${total_value:,.2f} | **Unrealized P&L:** {sign}${total_pnl:,.2f}")
        lines.append("")
        
        # Sort by P&L
        sorted_pos = sorted(alpaca_positions, key=lambda x: x['unrealized_pl'], reverse=True)
        
        lines.append("| Symbol | Qty | Entry | Current | Unrealized P&L |")
        lines.append("|--------|-----|-------|---------|----------------|")
        for p in sorted_pos:
            pnl = p['unrealized_pl']
            pct = p['unrealized_plpc'] * 100
            sign = "+" if pnl >= 0 else ""
            lines.append(f"| {p['symbol']} | {int(p['qty'])} | ${p['avg_entry_price']:,.2f} | ${p['current_price']:,.2f} | {sign}${pnl:,.2f} ({sign}{pct:.1f}%) |")
    else:
        lines.append("*No open positions*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Scan Results Summary
    lines.append("## Scan Results")
    lines.append("")
    
    if scans:
        # Group by cycle
        cycles_scans = {}
        for s in scans:
            if s['cycle_id'] not in cycles_scans:
                cycles_scans[s['cycle_id']] = []
            cycles_scans[s['cycle_id']].append(s)
        
        for cycle_id, cycle_scans in cycles_scans.items():
            selected = [s for s in cycle_scans if s['selected_for_trading']]
            lines.append(f"### {cycle_id}")
            lines.append(f"Scanned: {len(cycle_scans)} | Selected: {len(selected)}")
            lines.append("")
            if selected:
                lines.append("| Symbol | Price | Volume |")
                lines.append("|--------|-------|--------|")
                for s in selected:
                    vol = f"{s['volume']:,.0f}" if s['volume'] else '-'
                    lines.append(f"| {s['symbol']} | ${float(s['price']):,.2f} | {vol} |")
                lines.append("")
    else:
        lines.append("*No scan results*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Report stored in consciousness database by {AGENT_ID}*")
    
    return "\n".join(lines)


def generate_summary(
    alpaca_account: Optional[Dict],
    alpaca_positions: List[Dict],
    positions_opened: List[Dict],
    positions_closed: List[Dict]
) -> str:
    """Generate short summary for list view"""
    
    parts = []
    
    # Daily P&L
    if alpaca_account:
        daily_change = alpaca_account['equity'] - alpaca_account['last_equity']
        sign = "+" if daily_change >= 0 else ""
        parts.append(f"{sign}${daily_change:,.0f}")
    
    # Position counts
    parts.append(f"{len(alpaca_positions)} positions")
    
    # Activity
    if positions_opened:
        parts.append(f"{len(positions_opened)} opened")
    if positions_closed:
        parts.append(f"{len(positions_closed)} closed")
    
    return " · ".join(parts) if parts else "No activity"


# =============================================================================
# DATABASE STORAGE
# =============================================================================

async def store_report(
    conn: asyncpg.Connection,
    report_date: date,
    title: str,
    summary: str,
    content: str,
    metrics: Dict
) -> int:
    """Store report in claude_reports table"""
    
    report_id = await conn.fetchval("""
        INSERT INTO claude_reports (
            agent_id, market, report_type, report_date,
            title, summary, content, metrics
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (agent_id, report_type, report_date, market)
        DO UPDATE SET
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            content = EXCLUDED.content,
            metrics = EXCLUDED.metrics,
            created_at = NOW()
        RETURNING id
    """, AGENT_ID, MARKET, 'daily', report_date,
        title, summary, content, json.dumps(metrics))
    
    return report_id


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main entry point"""
    
    # Parse arguments
    if len(sys.argv) > 1:
        try:
            report_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        # Default to today (or yesterday if before market close)
        now = datetime.utcnow()
        if now.hour < 21:  # Before 4pm ET (21:00 UTC)
            report_date = date.today() - timedelta(days=1)
        else:
            report_date = date.today()
    
    print(f"Generating US daily report for: {report_date}")
    
    # Validate configuration
    if not TRADING_DB_URL:
        print("ERROR: DATABASE_URL environment variable required")
        sys.exit(1)
    
    if not RESEARCH_DB_URL:
        print("ERROR: RESEARCH_DATABASE_URL environment variable required")
        sys.exit(1)
    
    # Connect to trading database
    print("Connecting to trading database...")
    try:
        trading_conn = await asyncpg.connect(TRADING_DB_URL)
    except Exception as e:
        print(f"Trading database connection failed: {e}")
        sys.exit(1)
    
    # Connect to research database
    print("Connecting to research database...")
    try:
        research_conn = await asyncpg.connect(RESEARCH_DB_URL)
    except Exception as e:
        print(f"Research database connection failed: {e}")
        await trading_conn.close()
        sys.exit(1)
    
    try:
        # Gather data from trading database
        print("Fetching trading cycles...")
        cycles = await get_trading_cycles(trading_conn, report_date)
        
        print("Fetching positions opened...")
        positions_opened = await get_positions_opened(trading_conn, report_date)
        
        print("Fetching positions closed...")
        positions_closed = await get_positions_closed(trading_conn, report_date)
        
        print("Fetching scan results...")
        scans = await get_scan_results(trading_conn, report_date)
        
        print("Fetching all open positions from DB...")
        db_open_positions = await get_all_open_positions(trading_conn)
        
        # Gather data from Alpaca
        print("Fetching Alpaca account...")
        alpaca_account = get_alpaca_account()
        
        print("Fetching Alpaca positions...")
        alpaca_positions = get_alpaca_positions()
        
        # Generate report
        print("Generating report...")
        
        title = f"US Daily Report - {report_date.strftime('%Y-%m-%d')}"
        
        metrics = calculate_metrics(
            alpaca_account, alpaca_positions,
            positions_opened, positions_closed, cycles
        )
        
        content = generate_report_content(
            report_date, cycles, positions_opened, positions_closed,
            scans, db_open_positions, alpaca_account, alpaca_positions
        )
        
        summary = generate_summary(
            alpaca_account, alpaca_positions,
            positions_opened, positions_closed
        )
        
        # Store in database
        print("Storing report in database...")
        report_id = await store_report(
            research_conn, report_date,
            title, summary, content, metrics
        )
        
        print(f"✅ Report stored successfully!")
        print(f"   ID: {report_id}")
        print(f"   Title: {title}")
        print(f"   Summary: {summary}")
        
        # Print metrics summary
        if metrics:
            print(f"\n📊 Metrics:")
            if 'daily_pnl' in metrics:
                sign = "+" if metrics['daily_pnl'] >= 0 else ""
                print(f"   Daily P&L: {sign}${metrics['daily_pnl']:,.2f}")
            if 'positions_open' in metrics:
                print(f"   Open Positions: {metrics['positions_open']}")
            if 'account_value' in metrics:
                print(f"   Account Value: ${metrics['account_value']:,.2f}")
        
    finally:
        await trading_conn.close()
        await research_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
