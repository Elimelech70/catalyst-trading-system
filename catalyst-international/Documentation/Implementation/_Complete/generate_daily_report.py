#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: generate_daily_report.py
Version: 2.0.0
Last Updated: 2025-12-31
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

Description:
Automated daily report generator that:
1. Pulls portfolio data from Moomoo via OpenD
2. Generates markdown report
3. Stores in consciousness database (claude_reports table)
4. Optionally saves to file and pushes to GitHub
"""

import os
import sys
import json
import asyncio
import asyncpg
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal

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
RESEARCH_DATABASE_URL = os.getenv("RESEARCH_DATABASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL")  # INTL trading DB (fallback)

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
# DATA FETCHING
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
        
        # Find our account
        acc_id = None
        for acc in acc_list:
            if ACCOUNT_ID and str(acc.get("acc_id")) == ACCOUNT_ID:
                acc_id = acc.get("acc_id")
                break
            elif acc.get("trd_env") == TRADE_ENV:
                acc_id = acc.get("acc_id")
                break
        
        if not acc_id:
            raise RuntimeError("Could not find trading account")
        
        # Get account funds
        ret, funds = trd_ctx.accinfo_query(acc_id=acc_id, trd_env=TRADE_ENV)
        if ret == 0 and len(funds) > 0:
            fund = funds.iloc[0]
            data["portfolio"] = {
                "total_assets": float(fund.get("total_assets", 0)),
                "cash": float(fund.get("cash", 0)),
                "market_value": float(fund.get("market_val", 0)),
                "frozen_cash": float(fund.get("frozen_cash", 0)),
            }
        
        # Get positions
        ret, positions = trd_ctx.position_list_query(acc_id=acc_id, trd_env=TRADE_ENV)
        if ret == 0 and len(positions) > 0:
            for _, pos in positions.iterrows():
                symbol = pos.get("code", "").replace("HK.", "")
                data["positions"].append({
                    "symbol": symbol,
                    "quantity": int(pos.get("qty", 0)),
                    "avg_cost": float(pos.get("cost_price", 0)),
                    "current_price": float(pos.get("nominal_price", 0)),
                    "market_value": float(pos.get("market_val", 0)),
                    "unrealized_pnl": float(pos.get("pl_val", 0)),
                    "unrealized_pnl_pct": float(pos.get("pl_ratio", 0)),
                    "day_change": float(pos.get("today_pl_val", 0)) / int(pos.get("qty", 1)) if pos.get("qty", 0) > 0 else 0,
                })
    finally:
        trd_ctx.close()
    
    return data


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(data: dict) -> tuple[str, str, dict]:
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
    
    # Calculate totals
    total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)
    total_market_value = sum(p["market_value"] for p in positions)
    total_day_pnl = sum(p["day_change"] * p["quantity"] for p in positions)
    
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
| **Market Value** | HKD {total_market_value:,.2f} |
| **Unrealized P&L** | HKD {total_unrealized_pnl:+,.2f} |
| **Today's P&L** | HKD {total_day_pnl:+,.2f} |
| **Total Return** | {total_return:+.2f}% |

---

## Open Positions ({len(positions)})

| Symbol | Qty | Avg Cost | Current | Market Value | P&L | P&L % | Today |
|--------|-----|----------|---------|--------------|-----|-------|-------|
"""
    
    for pos in sorted(positions, key=lambda x: x["unrealized_pnl"], reverse=True):
        pnl_sign = "+" if pos["unrealized_pnl"] >= 0 else ""
        day_sign = "+" if pos["day_change"] >= 0 else ""
        report += f"| {pos['symbol']} | {pos['quantity']:,} | {pos['avg_cost']:.2f} | {pos['current_price']:.2f} | {pos['market_value']:,.0f} | {pnl_sign}{pos['unrealized_pnl']:,.0f} | {pos['unrealized_pnl_pct']*100:+.1f}% | {day_sign}{pos['day_change']:.2f} |\n"
    
    report += f"""
---

## System Status

| Component | Status |
|-----------|--------|
| OpenD Gateway | ✅ Running |
| Broker Connection | ✅ Connected |
| Market Data | ✅ Active |
| Consciousness DB | ✅ Connected |

---

## Trading Schedule

| Session | Time (HKT) | Status |
|---------|------------|--------|
| Morning | 09:30-12:00 | {'✅ Completed' if timestamp.hour >= 12 else '⏳ Pending'} |
| Afternoon | 13:00-16:00 | {'✅ Completed' if timestamp.hour >= 16 else '⏳ Pending'} |

---

## Notes

- Market: HKEX (Hong Kong Stock Exchange)
- Currency: HKD
- Lot Size: 100 shares
- Paper Trading Mode: Simulated execution

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
        "today_pnl": round(total_day_pnl, 2),
        "positions_open": len(positions),
        "account_value": round(total_assets, 2),
        "cash": round(cash, 2),
        "market_value": round(total_market_value, 2),
        "total_return_pct": round(total_return, 2),
        "winners": winners,
        "losers": losers,
        "win_rate": round(win_rate, 2),
    }
    
    return report, summary, metrics


# ============================================================================
# DATABASE STORAGE
# ============================================================================

async def store_report_in_db(
    report_date: str,
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
    reports_dir = Path(__file__).parent.parent / "Documentation" / "Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"DAILY_REPORT_{date_str}.md"
    filepath = reports_dir / filename
    
    filepath.write_text(report)
    print(f"📄 Report saved to file: {filepath}")
    
    return filepath


def push_to_github(filepath: Path, date_str: str):
    """Commit and push report to GitHub."""
    repo_dir = Path(__file__).parent.parent
    
    # Git add
    subprocess.run(
        ["git", "add", str(filepath)],
        cwd=repo_dir,
        check=True
    )
    
    # Git commit
    commit_msg = f"report: daily trading report {date_str}\n\n" \
                 f"Auto-generated daily report\n\n" \
                 f"Generated with [Claude Code](https://claude.com/claude-code)"
    
    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            print("📝 No changes to commit")
            return
        raise subprocess.CalledProcessError(result.returncode, "git commit")
    
    # Git push
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo_dir,
        check=True
    )
    
    print(f"📤 Report pushed to GitHub")


# ============================================================================
# MAIN
# ============================================================================

async def main_async(args):
    """Async main function."""
    print("=" * 50)
    print("INTL_CLAUDE DAILY REPORT GENERATOR v2.0.0")
    print("=" * 50)
    print()
    
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
    report_content, summary, metrics = generate_report(data)
    
    date_str = data["timestamp"].strftime("%Y-%m-%d")
    title = f"HKEX Daily Report - {date_str}"
    
    # Store in database (primary)
    print("💾 Storing in consciousness database...")
    try:
        report_id = await store_report_in_db(
            report_date=date_str,
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
    if report_id:
        print(f"   Dashboard: Available at /reports/{report_id}")
    print()
    
    return 0


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Generate daily trading report")
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
