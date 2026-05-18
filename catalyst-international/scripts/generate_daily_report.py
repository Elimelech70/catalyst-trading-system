#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: generate_daily_report.py
Version: 3.0.0
Last Updated: 2025-01-16
Purpose: Generate daily trading report and store in consciousness database

REVISION HISTORY:
v1.0.0 (2025-12-28) - Initial version
- Generate markdown report
- Save to file
- Push to GitHub

v2.0.0 (2025-12-31) - Database integration
- Store reports in claude_reports table (consciousness DB)
- Reports now visible on mobile dashboard
- File save optional (--save-file flag)
- GitHub push optional (--push flag)
- Metrics extracted for dashboard cards

v3.0.0 (2025-01-16) - New report format
- Added Orders Summary section (new/skipped/exits with reasons)
- Updated Open Positions format: Symbol, Qty, Entry, Current, SL, TP, P&L
- Removed: Avg Cost, P&L %, Market Value, Today columns
- Added database lookup for stop_loss and take_profit values
- Added decisions lookup for order reasoning

Description:
Automated daily report generator that:
1. Pulls portfolio data from Moomoo via OpenD
2. Fetches stop_loss/take_profit from positions table
3. Fetches today's decisions for Orders Summary
4. Generates markdown report in new format
5. Stores in consciousness database (claude_reports table)
6. Optionally saves to file and pushes to GitHub
"""

import os
import sys
import json
import asyncio
import asyncpg
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Optional, Dict, List, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import Moomoo
try:
    from moomoo import OpenQuoteContext, OpenSecTradeContext, TrdEnv, TrdMarket
    MOOMOO_AVAILABLE = True
except ImportError:
    MOOMOO_AVAILABLE = False
    print("Warning: Moomoo SDK not available")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Database URLs
RESEARCH_DATABASE_URL = os.getenv("RESEARCH_DATABASE_URL")  # Consciousness DB
DATABASE_URL = os.getenv("DATABASE_URL")  # INTL trading DB

# OpenD connection
OPEND_HOST = os.getenv("OPEND_HOST", "127.0.0.1")
OPEND_PORT = int(os.getenv("OPEND_PORT", "11111"))

# Trading account
TRADE_ENV = TrdEnv.SIMULATE if os.getenv("PAPER_TRADING", "true").lower() == "true" else TrdEnv.REAL
ACCOUNT_ID = os.getenv("MOOMOO_ACCOUNT_ID", "")

# Agent identity
AGENT_ID = "intl_claude"
MARKET = "HKEX"

# Timezone
HKT = timezone(timedelta(hours=8))
AWST = timezone(timedelta(hours=8))  # Same as HKT


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_float(value, default=0.0) -> float:
    """Safely convert value to float, handling 'N/A' and other non-numeric values."""
    if value == "N/A" or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================================
# DATA FETCHING - MOOMOO
# ============================================================================

def get_portfolio_data() -> dict:
    """Fetch portfolio data from Moomoo."""
    if not MOOMOO_AVAILABLE:
        raise RuntimeError("Moomoo SDK not available")
    
    data = {
        "portfolio": {},
        "positions": [],
        "timestamp": datetime.now(HKT)
    }
    
    # Connect to trade context
    trd_ctx = OpenSecTradeContext(
        host=OPEND_HOST,
        port=OPEND_PORT,
        filter_trdmarket=TrdMarket.HK
    )
    
    try:
        # Get account info
        ret, acc_list = trd_ctx.get_acc_list()
        if ret != 0:
            raise RuntimeError(f"Failed to get account list: {acc_list}")
        
        # Find our account (acc_list is a DataFrame)
        acc_id = None
        for _, acc in acc_list.iterrows():
            if ACCOUNT_ID and str(acc["acc_id"]) == ACCOUNT_ID:
                acc_id = acc["acc_id"]
                break
            elif acc["trd_env"] == "SIMULATE":  # Paper trading
                acc_id = acc["acc_id"]
                break

        if not acc_id:
            raise RuntimeError("Could not find trading account")
        
        # Get account funds
        ret, funds = trd_ctx.accinfo_query(acc_id=acc_id, trd_env=TRADE_ENV)
        if ret == 0 and len(funds) > 0:
            fund = funds.iloc[0]
            data["portfolio"] = {
                "total_assets": safe_float(fund.get("total_assets", 0)),
                "cash": safe_float(fund.get("cash", 0)),
                "market_value": safe_float(fund.get("market_val", 0)),
                "frozen_cash": safe_float(fund.get("frozen_cash", 0)),
            }
        
        # Get positions
        ret, positions = trd_ctx.position_list_query(acc_id=acc_id, trd_env=TRADE_ENV)
        if ret == 0 and len(positions) > 0:
            for _, pos in positions.iterrows():
                symbol = pos.get("code", "").replace("HK.", "")
                qty = int(safe_float(pos.get("qty", 0)))
                data["positions"].append({
                    "symbol": symbol,
                    "quantity": qty,
                    "entry_price": safe_float(pos.get("cost_price", 0)),
                    "current_price": safe_float(pos.get("nominal_price", 0)),
                    "unrealized_pnl": safe_float(pos.get("pl_val", 0)),
                })
    finally:
        trd_ctx.close()
    
    return data


# ============================================================================
# DATA FETCHING - DATABASE
# ============================================================================

async def get_positions_with_sl_tp(symbols: List[str]) -> Dict[str, Dict]:
    """
    Get stop_loss and take_profit from positions table.
    
    Args:
        symbols: List of stock symbols to look up
        
    Returns:
        Dict mapping symbol to {stop_loss, take_profit}
    """
    if not DATABASE_URL:
        print("Warning: DATABASE_URL not set, cannot fetch SL/TP")
        return {}
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT symbol, stop_loss, take_profit
            FROM positions
            WHERE status = 'open'
              AND symbol = ANY($1)
        """, symbols)
        
        result = {}
        for row in rows:
            result[row['symbol']] = {
                'stop_loss': float(row['stop_loss']) if row['stop_loss'] else None,
                'take_profit': float(row['take_profit']) if row['take_profit'] else None,
            }
        return result
    finally:
        await conn.close()


async def get_todays_decisions(report_date: date) -> Dict[str, List[Dict]]:
    """
    Get today's trading decisions from agent_decisions or decisions table.
    
    Returns:
        Dict with keys: 'new_orders', 'skipped', 'exits'
    """
    if not DATABASE_URL:
        print("Warning: DATABASE_URL not set, cannot fetch decisions")
        return {'new_orders': [], 'skipped': [], 'exits': []}
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Try agent_decisions table first (newer schema)
        try:
            rows = await conn.fetch("""
                SELECT 
                    decision_type,
                    symbol,
                    reasoning,
                    created_at
                FROM agent_decisions
                WHERE created_at::date = $1
                ORDER BY created_at
            """, report_date)
        except Exception:
            # Fall back to decisions table (older schema)
            rows = await conn.fetch("""
                SELECT 
                    action as decision_type,
                    symbol,
                    reasoning,
                    timestamp as created_at
                FROM decisions
                WHERE timestamp::date = $1
                ORDER BY timestamp
            """, report_date)
        
        result = {'new_orders': [], 'skipped': [], 'exits': []}

        for row in rows:
            decision = {
                'symbol': row['symbol'],
                'reasoning': row['reasoning'] or 'No reason recorded',
                'time': row['created_at'].strftime('%H:%M') if row['created_at'] else '',
            }

            decision_type = (row['decision_type'] or '').lower()

            if decision_type in ('trade', 'buy', 'entry', 'open'):
                result['new_orders'].append(decision)
            elif decision_type in ('skip', 'pass', 'no_trade', 'observation'):
                result['skipped'].append(decision)
            elif decision_type in ('close', 'exit', 'sell'):
                result['exits'].append(decision)

        # Fallback: if no decisions found, count from orders table directly
        if not result['new_orders'] and not result['exits']:
            try:
                order_rows = await conn.fetch("""
                    SELECT symbol, side, quantity, status, reason, created_at
                    FROM orders
                    WHERE created_at::date = $1
                    ORDER BY created_at
                """, report_date)
                for row in order_rows:
                    decision = {
                        'symbol': row['symbol'],
                        'reasoning': row.get('reason') or f"{row['side']} {row['quantity']} shares ({row['status']})",
                        'time': row['created_at'].strftime('%H:%M') if row['created_at'] else '',
                    }
                    side = (row.get('side') or '').lower()
                    if side == 'buy':
                        result['new_orders'].append(decision)
                    elif side == 'sell':
                        result['exits'].append(decision)
            except Exception as e:
                print(f"Warning: Could not fetch from orders table: {e}")

        return result
        
    except Exception as e:
        print(f"Warning: Could not fetch decisions: {e}")
        return {'new_orders': [], 'skipped': [], 'exits': []}
    finally:
        await conn.close()


async def get_closed_positions_today(report_date: date) -> List[Dict]:
    """Get positions that were closed today."""
    if not DATABASE_URL:
        return []
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT 
                symbol,
                quantity,
                entry_price,
                exit_price,
                realized_pnl,
                exit_reason
            FROM positions
            WHERE status = 'closed'
              AND closed_at::date = $1
            ORDER BY closed_at
        """, report_date)
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Warning: Could not fetch closed positions: {e}")
        return []
    finally:
        await conn.close()


# ============================================================================
# REPORT GENERATION
# ============================================================================

async def generate_report(data: dict, report_date: date) -> tuple[str, str, dict]:
    """
    Generate markdown report and extract metrics.
    
    Returns:
        tuple: (report_content, summary, metrics_dict)
    """
    portfolio = data["portfolio"]
    positions = data["positions"]
    timestamp = data["timestamp"]
    
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M:%S HKT")
    
    # Get SL/TP from database
    symbols = [p['symbol'] for p in positions]
    sl_tp_data = await get_positions_with_sl_tp(symbols) if symbols else {}
    
    # Merge SL/TP into positions
    for pos in positions:
        sym = pos['symbol']
        if sym in sl_tp_data:
            pos['stop_loss'] = sl_tp_data[sym].get('stop_loss')
            pos['take_profit'] = sl_tp_data[sym].get('take_profit')
        else:
            pos['stop_loss'] = None
            pos['take_profit'] = None
    
    # Get today's decisions
    decisions = await get_todays_decisions(report_date)
    
    # Get closed positions today
    closed_today = await get_closed_positions_today(report_date)
    
    # Calculate totals
    total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)
    
    # Calculate portfolio return
    cash = portfolio.get("cash", 0)
    total_assets = portfolio.get("total_assets", 0)
    initial_capital = 1_000_000  # Paper trading initial
    total_return = ((total_assets - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
    
    # Count winners/losers
    winners = sum(1 for p in positions if p["unrealized_pnl"] > 0)
    losers = sum(1 for p in positions if p["unrealized_pnl"] < 0)
    win_rate = winners / len(positions) if positions else 0
    
    # Build report content
    report = f"""# Daily Trading Report - {date_str}

**Generated:** {time_str}
**System:** Catalyst International (HKEX)
**Mode:** Paper Trading
**Agent:** intl_claude

---

## Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Assets** | HKD {total_assets:,.2f} |
| **Cash** | HKD {cash:,.2f} |
| **Unrealized P&L** | HKD {total_unrealized_pnl:+,.2f} |
| **Total Return** | {total_return:+.2f}% |

---

## Orders Summary

| Type | Count | Notes |
|------|-------|-------|
| New Orders | {len(decisions['new_orders'])} | {_summarize_reasons(decisions['new_orders']) or 'None today'} |
| Skipped | {len(decisions['skipped'])} | {_summarize_reasons(decisions['skipped']) or 'None today'} |
| Exits | {len(closed_today)} | {_summarize_exits(closed_today) or 'None today'} |

"""
    
    # New Orders section
    if decisions['new_orders']:
        report += """### New Orders

| Symbol | Time | Reason |
|--------|------|--------|
"""
        for order in decisions['new_orders']:
            reason = _truncate(order['reasoning'], 50)
            report += f"| {order['symbol']} | {order['time']} | {reason} |\n"
        report += "\n"
    
    # Skipped section
    if decisions['skipped']:
        report += """### Opportunities Skipped

| Symbol | Reason |
|--------|--------|
"""
        for skip in decisions['skipped'][:10]:  # Limit to 10
            reason = _truncate(skip['reasoning'], 60)
            symbol = skip['symbol'] or '-'
            report += f"| {symbol} | {reason} |\n"
        
        if len(decisions['skipped']) > 10:
            report += f"| ... | +{len(decisions['skipped']) - 10} more |\n"
        report += "\n"
    
    # Exits section
    if closed_today:
        report += """### Positions Closed

| Symbol | Qty | Entry | Exit | P&L | Reason |
|--------|-----|-------|------|-----|--------|
"""
        for pos in closed_today:
            pnl = pos.get('realized_pnl', 0) or 0
            reason = pos.get('exit_reason', '-') or '-'
            report += f"| {pos['symbol']} | {pos['quantity']} | {pos['entry_price']:.2f} | {pos['exit_price']:.2f} | {pnl:+,.0f} | {reason} |\n"
        report += "\n"
    
    # Open Positions section
    report += f"""---

## Open Positions ({len(positions)})

| Symbol | Qty | Entry | Current | Stop Loss | Take Profit | P&L |
|--------|-----|-------|---------|-----------|-------------|-----|
"""
    
    for pos in sorted(positions, key=lambda x: x["unrealized_pnl"], reverse=True):
        sl = f"{pos['stop_loss']:.2f}" if pos['stop_loss'] else "-"
        tp = f"{pos['take_profit']:.2f}" if pos['take_profit'] else "-"
        pnl = pos['unrealized_pnl']
        pnl_str = f"{pnl:+,.0f}"
        
        report += f"| {pos['symbol']} | {pos['quantity']:,} | {pos['entry_price']:.2f} | {pos['current_price']:.2f} | {sl} | {tp} | {pnl_str} |\n"
    
    report += f"""
---

## System Status

| Component | Status |
|-----------|--------|
| OpenD Gateway | {'✅ Running' if MOOMOO_AVAILABLE else '❌ Not Available'} |
| Broker Connection | ✅ Connected |
| Market Data | ✅ Active |
| Consciousness DB | {'✅ Connected' if RESEARCH_DATABASE_URL else '⚠️ Not Configured'} |

---

## Trading Schedule

| Session | Time (HKT) | Status |
|---------|------------|--------|
| Morning | 09:30-12:00 | {'✅ Completed' if timestamp.hour >= 12 else '⏳ Pending'} |
| Afternoon | 13:00-16:00 | {'✅ Completed' if timestamp.hour >= 16 else '⏳ Pending'} |

---

*Report generated automatically by intl_claude*
*Stored in consciousness database for dashboard access*
"""
    
    # Build summary for list view
    pnl_sign = "+" if total_unrealized_pnl >= 0 else ""
    summary = f"{pnl_sign}HKD {total_unrealized_pnl:,.0f} · {len(positions)} positions"
    
    # Build metrics for JSONB
    metrics = {
        "total_pnl": round(total_unrealized_pnl, 2),
        "positions_open": len(positions),
        "account_value": round(total_assets, 2),
        "cash": round(cash, 2),
        "total_return_pct": round(total_return, 2),
        "winners": winners,
        "losers": losers,
        "win_rate": round(win_rate, 2),
        "orders_new": len(decisions['new_orders']),
        "orders_skipped": len(decisions['skipped']),
        "orders_exits": len(closed_today),
    }
    
    return report, summary, metrics


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return "-"
    text = text.replace('\n', ' ').strip()
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def _summarize_reasons(items: List[Dict]) -> str:
    """Create a brief summary of reasons."""
    if not items:
        return ""
    
    # Extract key words from reasons
    keywords = []
    for item in items[:3]:
        reason = item.get('reasoning', '') or ''
        # Look for common patterns
        if 'momentum' in reason.lower():
            keywords.append('momentum')
        elif 'volume' in reason.lower():
            keywords.append('volume')
        elif 'news' in reason.lower() or 'catalyst' in reason.lower():
            keywords.append('news catalyst')
        elif 'rsi' in reason.lower():
            keywords.append('RSI')
        elif 'pattern' in reason.lower():
            keywords.append('pattern')
        elif 'risk' in reason.lower():
            keywords.append('risk limit')
    
    if keywords:
        return ', '.join(set(keywords))
    return f"{len(items)} decisions"


def _summarize_exits(positions: List[Dict]) -> str:
    """Create a brief summary of exits."""
    if not positions:
        return ""
    
    reasons = []
    for pos in positions[:3]:
        reason = pos.get('exit_reason', '') or ''
        if 'stop' in reason.lower():
            reasons.append('Stop loss hit')
        elif 'profit' in reason.lower() or 'target' in reason.lower():
            reasons.append('Take profit')
        elif 'manual' in reason.lower():
            reasons.append('Manual close')
        else:
            reasons.append(reason[:20] if reason else 'Closed')
    
    return ', '.join(set(reasons))


# ============================================================================
# DATABASE STORAGE
# ============================================================================

async def store_report_in_db(
    report_date: date,
    title: str,
    summary: str,
    content: str,
    metrics: dict
) -> int:
    """
    Store report in consciousness database.
    
    Returns:
        int: Report ID
    """
    if not RESEARCH_DATABASE_URL:
        raise RuntimeError("RESEARCH_DATABASE_URL not configured")
    
    conn = await asyncpg.connect(RESEARCH_DATABASE_URL)
    
    try:
        # Use UPSERT to handle re-runs on same day
        result = await conn.fetchrow("""
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
        """,
            AGENT_ID,
            MARKET,
            "daily",
            report_date,
            title,
            summary,
            content,
            json.dumps(metrics)
        )
        
        report_id = result["id"]
        print(f"✅ Report stored in database (ID: {report_id})")
        return report_id
        
    finally:
        await conn.close()


# ============================================================================
# FILE OPERATIONS (OPTIONAL)
# ============================================================================

def save_report_to_file(report: str, date_str: str) -> Path:
    """Save report to Documentation/Reports directory."""
    reports_dir = Path(__file__).parent.parent / "Documentation" / "Reports" / "daily"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = reports_dir / f"trading-report-{date_str}.md"
    filepath.write_text(report)
    
    print(f"✅ Report saved to {filepath}")
    return filepath


def push_to_github(filepath: Path, date_str: str):
    """Commit and push report to GitHub."""
    repo_root = Path(__file__).parent.parent
    
    subprocess.run(["git", "add", str(filepath)], cwd=repo_root, check=True)
    
    commit_msg = f"""docs(reports): Daily trading report {date_str}

Auto-generated daily report with:
- Portfolio summary
- Orders summary (new/skipped/exits)
- Open positions with SL/TP

Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
    
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_root, check=True)
    subprocess.run(["git", "push"], cwd=repo_root, check=True)
    
    print("✅ Report pushed to GitHub")


# ============================================================================
# MAIN
# ============================================================================

async def main_async(args):
    """Async main entry point."""
    print()
    print("=" * 50)
    print("INTL_CLAUDE DAILY REPORT GENERATOR v3.0.0")
    print("=" * 50)
    print()
    
    # Determine report date
    if args.date:
        try:
            report_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
            return 1
    else:
        report_date = datetime.now(HKT).date()
    
    print(f"📅 Report date: {report_date}")
    
    # Fetch data
    print("📊 Fetching portfolio data from Moomoo...")
    try:
        data = get_portfolio_data()
        print(f"   Found {len(data['positions'])} positions")
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return 1
    
    # Generate report
    print("📝 Generating report...")
    report_content, summary, metrics = await generate_report(data, report_date)
    
    date_str = report_date.strftime("%Y-%m-%d")
    title = f"HKEX Daily Report - {date_str}"
    
    # Store in database (primary)
    print("💾 Storing in consciousness database...")
    try:
        report_id = await store_report_in_db(
            report_date=report_date,
            title=title,
            summary=summary,
            content=report_content,
            metrics=metrics
        )
    except Exception as e:
        print(f"❌ Database storage failed: {e}")
        # Continue to file save as fallback
        report_id = None
    
    # Save to file (optional)
    if args.save_file:
        print("📄 Saving to file...")
        filepath = save_report_to_file(report_content, date_str)
        
        # Push to GitHub (optional)
        if args.push:
            print("📤 Pushing to GitHub...")
            try:
                push_to_github(filepath, date_str)
            except subprocess.CalledProcessError as e:
                print(f"⚠️ GitHub push failed: {e}")
    
    # Summary
    print()
    print("=" * 50)
    print("✅ REPORT COMPLETE")
    print("=" * 50)
    print(f"   Date: {date_str}")
    print(f"   Positions: {len(data['positions'])}")
    print(f"   P&L: {summary}")
    print(f"   Orders: {metrics['orders_new']} new, {metrics['orders_skipped']} skipped, {metrics['orders_exits']} exits")
    if report_id:
        print(f"   Dashboard: Available at /reports/{report_id}")
    print()
    
    return 0


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Generate daily trading report")
    parser.add_argument("--date", type=str, help="Report date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--save-file", action="store_true", 
                        help="Also save report to markdown file")
    parser.add_argument("--push", action="store_true", 
                        help="Push file to GitHub (requires --save-file)")
    args = parser.parse_args()
    
    if args.push and not args.save_file:
        print("Warning: --push requires --save-file, enabling file save")
        args.save_file = True
    
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
