#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: generate-daily-report.py
Version: 1.0.0
Last Updated: 2025-12-10
Purpose: Generate daily trading report and push to GitHub

REVISION HISTORY:
v1.0.0 (2025-12-10) - Initial version
- Query database for trading activity
- Query Alpaca API for account/positions
- Generate markdown report
- Commit and push to GitHub

Description:
Automated daily report generator that:
1. Pulls trading data from PostgreSQL
2. Gets account info from Alpaca API
3. Generates markdown report
4. Commits and pushes to GitHub repository
"""

import os
import sys
import asyncio
import asyncpg
import subprocess
from datetime import datetime, date, timedelta
from decimal import Decimal
import json

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("Warning: Alpaca SDK not available, will use database only")

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required")
    sys.exit(1)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

REPO_PATH = "/root/catalyst-trading-system"
REPORTS_DIR = f"{REPO_PATH}/Documentation/Reports/daily"


def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def get_trading_cycles(conn, report_date: date):
    """Get trading cycles for the report date"""
    # Cycles are named YYYYMMDD-NNN but stored timestamps may be previous day (US market hours)
    cycle_prefix = report_date.strftime("%Y%m%d")

    cycles = await conn.fetch("""
        SELECT
            cycle_id,
            mode,
            status,
            started_at AT TIME ZONE 'America/New_York' as started_et,
            stopped_at AT TIME ZONE 'America/New_York' as stopped_et
        FROM trading_cycles
        WHERE cycle_id LIKE $1
        ORDER BY started_at
    """, f"{cycle_prefix}%")

    return [dict(c) for c in cycles]


async def get_positions_opened(conn, report_date: date):
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
            p.alpaca_status,
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.cycle_id LIKE $1
        ORDER BY p.opened_at
    """, f"{cycle_prefix}%")

    return [dict(p) for p in positions]


async def get_scan_results(conn, report_date: date):
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


async def get_all_open_positions(conn):
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
            p.alpaca_status,
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.status = 'open'
        ORDER BY p.opened_at DESC
    """)

    return [dict(p) for p in positions]


def get_alpaca_account():
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


def get_alpaca_positions():
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


def generate_markdown_report(report_date: date, cycles: list, positions_opened: list,
                             scans: list, db_open_positions: list,
                             alpaca_account: dict, alpaca_positions: list) -> str:
    """Generate markdown report"""

    now = datetime.utcnow()
    report_lines = []

    # Header
    report_lines.append(f"# Daily Trading Report - {report_date.strftime('%Y-%m-%d')}")
    report_lines.append("")
    report_lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M')} UTC")
    report_lines.append("**System:** Catalyst Trading System")
    report_lines.append(f"**Mode:** {'Paper' if ALPACA_PAPER else 'Live'} Trading (Alpaca)")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Account Summary (from Alpaca)
    report_lines.append("## Account Summary")
    report_lines.append("")

    if alpaca_account:
        daily_change = alpaca_account['equity'] - alpaca_account['last_equity']
        daily_pct = (daily_change / alpaca_account['last_equity'] * 100) if alpaca_account['last_equity'] else 0

        report_lines.append("| Metric | Value |")
        report_lines.append("|--------|-------|")
        report_lines.append(f"| **Portfolio Value** | ${alpaca_account['portfolio_value']:,.2f} |")
        report_lines.append(f"| **Cash** | ${alpaca_account['cash']:,.2f} |")
        report_lines.append(f"| **Long Market Value** | ${alpaca_account['long_market_value']:,.2f} |")
        report_lines.append(f"| **Buying Power** | ${alpaca_account['buying_power']:,.2f} |")
        report_lines.append(f"| **Day Trade Count** | {alpaca_account['daytrade_count']} |")
        report_lines.append("")
        report_lines.append("### Daily Performance")
        report_lines.append("| Metric | Value |")
        report_lines.append("|--------|-------|")
        report_lines.append(f"| Last Equity | ${alpaca_account['last_equity']:,.2f} |")
        report_lines.append(f"| Current Equity | ${alpaca_account['equity']:,.2f} |")
        sign = "+" if daily_change >= 0 else ""
        report_lines.append(f"| **Daily Change** | **{sign}${daily_change:,.2f} ({sign}{daily_pct:.2f}%)** |")
    else:
        report_lines.append("*Alpaca account data unavailable*")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Trading Cycles
    report_lines.append("## Trading Cycles")
    report_lines.append("")

    if cycles:
        report_lines.append("| Cycle ID | Mode | Status | Started (ET) | Stopped (ET) |")
        report_lines.append("|----------|------|--------|--------------|--------------|")
        for c in cycles:
            started = c['started_et'].strftime('%H:%M:%S') if c['started_et'] else '-'
            stopped = c['stopped_et'].strftime('%H:%M:%S') if c['stopped_et'] else '-'
            report_lines.append(f"| {c['cycle_id']} | {c['mode']} | {c['status']} | {started} | {stopped} |")
    else:
        report_lines.append("*No trading cycles executed on this date*")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Positions Opened Today
    report_lines.append("## Positions Opened Today")
    report_lines.append("")

    if positions_opened:
        total_capital = sum(p['quantity'] * float(p['entry_price']) for p in positions_opened)
        report_lines.append(f"**Total Positions:** {len(positions_opened)} | **Capital Deployed:** ${total_capital:,.2f}")
        report_lines.append("")
        report_lines.append("| Cycle | Symbol | Side | Qty | Entry Price | Capital | Alpaca Status |")
        report_lines.append("|-------|--------|------|-----|-------------|---------|---------------|")
        for p in positions_opened:
            capital = p['quantity'] * float(p['entry_price'])
            report_lines.append(f"| {p['cycle_id']} | {p['symbol']} | {p['side']} | {p['quantity']} | ${float(p['entry_price']):,.2f} | ${capital:,.2f} | {p['alpaca_status'] or '-'} |")
    else:
        report_lines.append("*No positions opened on this date*")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Scan Results
    report_lines.append("## Scan Results")
    report_lines.append("")

    if scans:
        # Group by cycle
        cycles_scans = {}
        for s in scans:
            if s['cycle_id'] not in cycles_scans:
                cycles_scans[s['cycle_id']] = []
            cycles_scans[s['cycle_id']].append(s)

        for cycle_id, cycle_scans in cycles_scans.items():
            report_lines.append(f"### {cycle_id}")
            report_lines.append("")
            report_lines.append("| Rank | Symbol | Price | Volume | Selected |")
            report_lines.append("|------|--------|-------|--------|----------|")
            for s in cycle_scans:
                vol_str = f"{s['volume']:,.0f}" if s['volume'] else '-'
                selected = 'Yes' if s['selected_for_trading'] else 'No'
                report_lines.append(f"| {s['rank']} | {s['symbol']} | ${float(s['price']):,.2f} | {vol_str} | {selected} |")
            report_lines.append("")
    else:
        report_lines.append("*No scan results for this date*")

    report_lines.append("---")
    report_lines.append("")

    # Current Open Positions (from Alpaca)
    report_lines.append("## Current Open Positions")
    report_lines.append("")

    if alpaca_positions:
        total_value = sum(p['market_value'] for p in alpaca_positions)
        total_cost = sum(p['cost_basis'] for p in alpaca_positions)
        total_pnl = sum(p['unrealized_pl'] for p in alpaca_positions)

        # Sort by unrealized P&L
        sorted_positions = sorted(alpaca_positions, key=lambda x: x['unrealized_pl'], reverse=True)

        report_lines.append(f"**Total Positions:** {len(alpaca_positions)} | **Market Value:** ${total_value:,.2f} | **Unrealized P&L:** ${total_pnl:,.2f}")
        report_lines.append("")
        report_lines.append("| Symbol | Qty | Entry | Current | P&L | P&L % | Value |")
        report_lines.append("|--------|-----|-------|---------|-----|-------|-------|")

        winners = 0
        losers = 0
        for p in sorted_positions:
            sign = "+" if p['unrealized_pl'] >= 0 else ""
            pct_sign = "+" if p['unrealized_plpc'] >= 0 else ""
            report_lines.append(
                f"| {p['symbol']} | {int(p['qty'])} | ${p['avg_entry_price']:,.2f} | "
                f"${p['current_price']:,.2f} | {sign}${p['unrealized_pl']:,.2f} | "
                f"{pct_sign}{p['unrealized_plpc']*100:.2f}% | ${p['market_value']:,.2f} |"
            )
            if p['unrealized_pl'] >= 0:
                winners += 1
            else:
                losers += 1

        report_lines.append("")
        report_lines.append("### Position Summary")
        report_lines.append("| Metric | Value |")
        report_lines.append("|--------|-------|")
        report_lines.append(f"| Total Positions | {len(alpaca_positions)} |")
        report_lines.append(f"| Total Cost Basis | ${total_cost:,.2f} |")
        report_lines.append(f"| Total Market Value | ${total_value:,.2f} |")
        pnl_sign = "+" if total_pnl >= 0 else ""
        pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
        report_lines.append(f"| **Total Unrealized P&L** | **{pnl_sign}${total_pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)** |")
        report_lines.append(f"| Winning Positions | {winners} |")
        report_lines.append(f"| Losing Positions | {losers} |")
        win_rate = (winners / len(alpaca_positions) * 100) if alpaca_positions else 0
        report_lines.append(f"| Win Rate | {win_rate:.1f}% |")
    else:
        report_lines.append("*No open positions*")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Database vs Alpaca Reconciliation
    report_lines.append("## Database vs Alpaca Reconciliation")
    report_lines.append("")
    report_lines.append("| Source | Open Positions |")
    report_lines.append("|--------|----------------|")
    report_lines.append(f"| Alpaca (Broker) | {len(alpaca_positions)} |")
    report_lines.append(f"| Database | {len(db_open_positions)} |")
    diff = abs(len(db_open_positions) - len(alpaca_positions))
    if diff > 0:
        report_lines.append(f"| **Difference** | {diff} |")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Footer
    report_lines.append("*Report generated automatically by Catalyst Trading System*")
    report_lines.append("")

    return "\n".join(report_lines)


def git_commit_and_push(report_path: str, report_date: date):
    """Commit and push the report to GitHub"""
    try:
        os.chdir(REPO_PATH)

        # Add the file
        subprocess.run(["git", "add", report_path], check=True, capture_output=True)

        # Commit
        commit_msg = f"""docs(reports): Add daily trading report for {report_date.strftime('%Y-%m-%d')}

- Auto-generated daily report with trading activity
- Includes positions, scans, and account summary

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"""

        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("No changes to commit")
                return True
            print(f"Commit failed: {result.stderr}")
            return False

        # Push
        result = subprocess.run(
            ["git", "push"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Push failed: {result.stderr}")
            return False

        print(f"Successfully pushed report to GitHub")
        return True

    except Exception as e:
        print(f"Git error: {e}")
        return False


async def main():
    """Main function"""
    # Parse command line args for date override
    if len(sys.argv) > 1:
        try:
            report_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {sys.argv[1]}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        # Default to yesterday (since reports are usually generated after market close)
        report_date = date.today() - timedelta(days=1)

    print(f"Generating report for: {report_date}")

    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Connect to database
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

    try:
        # Gather data
        print("Fetching trading cycles...")
        cycles = await get_trading_cycles(conn, report_date)

        print("Fetching positions opened...")
        positions_opened = await get_positions_opened(conn, report_date)

        print("Fetching scan results...")
        scans = await get_scan_results(conn, report_date)

        print("Fetching all open positions from DB...")
        db_open_positions = await get_all_open_positions(conn)

        print("Fetching Alpaca account...")
        alpaca_account = get_alpaca_account()

        print("Fetching Alpaca positions...")
        alpaca_positions = get_alpaca_positions()

        # Generate report
        print("Generating markdown report...")
        report_content = generate_markdown_report(
            report_date, cycles, positions_opened, scans,
            db_open_positions, alpaca_account, alpaca_positions
        )

        # Write report
        report_filename = f"trading-report-{report_date.strftime('%Y-%m-%d')}.md"
        report_path = f"{REPORTS_DIR}/{report_filename}"

        with open(report_path, 'w') as f:
            f.write(report_content)

        print(f"Report written to: {report_path}")

        # Commit and push
        print("Committing and pushing to GitHub...")
        if git_commit_and_push(report_path, report_date):
            print("Done!")
        else:
            print("Report generated but git push failed")
            sys.exit(1)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
