"""
Name of Application: Catalyst Trading System
Name of file: security_classifier.py
Version: 0.1.0
Last Updated: 2026-05-23
Purpose: Populate securities.sector, market_cap_tier, market_cap_usd via yfinance.

REVISION HISTORY:
v0.1.0 (2026-05-23) - Initial implementation. Phase 3 of v0.4 context-conditioned plan.
  - yfinance Ticker.info → sector + marketCap
  - Maps yfinance sector strings to 11 GICS-aligned IDs from the architecture doc
  - Disambiguates Healthcare: drug/biotech/medical device → BIO, insurance → FIN
  - ETFs (quoteType='ETF') left with NULL sector/cap_tier (architecture Sec 8.4
    "missing context → 'other' fallback")
  - Idempotent: re-runs update context_updated_at and refresh stale market caps

Reference: Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md Section 4
           Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md Phase 3
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import get_connection

warnings.filterwarnings("ignore")

CLASSIFIER_VERSION = "yfinance_v1"

# yfinance sector → 11-tier ID (architecture Section 4.2)
SECTOR_MAP = {
    "Technology": "TECH",
    "Financial Services": "FIN",
    "Consumer Cyclical": "CONS_D",
    "Consumer Defensive": "CONS_S",
    "Energy": "ENERGY",
    "Industrials": "INDUSTRIAL",
    "Basic Materials": "MATERIALS",
    "Utilities": "UTIL",
    "Communication Services": "COMMS",
    "Real Estate": "REAL_ESTATE",
    # Healthcare needs disambiguation below
}

# Healthcare industry keywords that route to FIN (insurance) instead of BIO.
HEALTHCARE_TO_FIN_INDUSTRY_HINTS = (
    "Insurance",
    "Healthcare Plans",
    "Medical Care Facilities",  # hospital chains — more services than therapeutics
)

# Cap-tier thresholds (architecture Section 4.3, USD)
def cap_tier(market_cap_usd: Optional[float]) -> Optional[str]:
    if market_cap_usd is None or market_cap_usd <= 0:
        return None
    if market_cap_usd < 300e6:
        return "MICRO"
    if market_cap_usd < 2e9:
        return "SMALL"
    if market_cap_usd < 10e9:
        return "MID"
    if market_cap_usd < 200e9:
        return "LARGE"
    return "MEGA"


def yfinance_symbol(symbol: str, market: str) -> str:
    """Convert (symbol, market) to a yfinance ticker string."""
    if market == "HKEX":
        # HKEX symbols are numeric; yfinance expects zero-padded 4-digit + .HK
        try:
            n = int(symbol)
            return f"{n:04d}.HK"
        except ValueError:
            return symbol
    return symbol


def _disambiguate_healthcare(industry: Optional[str]) -> str:
    """Healthcare → BIO unless industry text hints at insurance/services."""
    if industry:
        for hint in HEALTHCARE_TO_FIN_INDUSTRY_HINTS:
            if hint.lower() in industry.lower():
                return "FIN"
    return "BIO"


def classify_one(symbol: str, market: str) -> Dict:
    """
    Fetch info for one (symbol, market) and return a classification dict.
    Returns: {sector, market_cap_tier, market_cap_usd, quote_type, name, source}
    sector and cap_tier may be None for ETFs / unrecognized sectors / fetch failures.
    """
    yf_sym = yfinance_symbol(symbol, market)
    result = {
        "symbol": symbol, "market": market, "yf_symbol": yf_sym,
        "sector": None, "market_cap_tier": None, "market_cap_usd": None,
        "quote_type": None, "name": None, "source": "yfinance",
        "error": None,
    }
    try:
        info = yf.Ticker(yf_sym).info or {}
    except Exception as e:
        result["error"] = str(e)
        return result

    result["quote_type"] = info.get("quoteType")
    result["name"] = info.get("longName") or info.get("shortName")
    result["market_cap_usd"] = info.get("marketCap")
    result["market_cap_tier"] = cap_tier(result["market_cap_usd"])

    yf_sector = info.get("sector")
    if yf_sector:
        if yf_sector == "Healthcare":
            result["sector"] = _disambiguate_healthcare(info.get("industry"))
        else:
            result["sector"] = SECTOR_MAP.get(yf_sector)
            if result["sector"] is None:
                # Unknown sector string — record for later inspection
                result["error"] = f"unmapped sector: {yf_sector!r}"

    # ETFs have quoteType='ETF' and may not have a sector — leave as NULL.
    if result["quote_type"] == "ETF":
        result["sector"] = None  # ETF doesn't fit a single sector
        result["market_cap_tier"] = None  # cap tier doesn't apply
    return result


def populate(dry_run: bool = False, only_unclassified: bool = True, verbose: bool = True) -> Dict:
    """
    Populate sector + market_cap_tier + market_cap_usd for all active securities.

    only_unclassified: skip securities where sector is already set.
    dry_run: log what would change, don't write.

    Returns: {processed, updated, errors, by_sector, by_cap_tier, etfs}
    """
    conn = get_connection()
    where = " AND sector IS NULL " if only_unclassified else ""
    rows = conn.execute(
        f"SELECT DISTINCT symbol, market FROM securities "
        f"WHERE removed_at IS NULL{where} "
        f"ORDER BY market, symbol"
    ).fetchall()
    if verbose:
        print(f"Classifying {len(rows)} unique active securities "
              f"({'unclassified only' if only_unclassified else 'all active'})...")

    by_sector: Dict[str, int] = {}
    by_cap_tier: Dict[str, int] = {}
    errors = []
    etfs = []
    updated = 0
    now = datetime.utcnow().isoformat()

    for i, row in enumerate(rows, 1):
        symbol, market = row["symbol"], row["market"]
        res = classify_one(symbol, market)
        if res["error"]:
            errors.append((symbol, market, res["error"]))
        if res["quote_type"] == "ETF":
            etfs.append((symbol, market, res["name"]))
        if verbose:
            sec = res["sector"] or "-"
            tier = res["market_cap_tier"] or "-"
            mc = f"${(res['market_cap_usd'] or 0)/1e9:.1f}B" if res["market_cap_usd"] else "-"
            qt = res["quote_type"] or "?"
            print(f"  [{i:3d}/{len(rows)}] {market:4s} {symbol:6s} {qt:5s}  sector={sec:12s}  cap={tier:5s}  mc={mc}")

        if res["sector"]:
            by_sector[res["sector"]] = by_sector.get(res["sector"], 0) + 1
        if res["market_cap_tier"]:
            by_cap_tier[res["market_cap_tier"]] = by_cap_tier.get(res["market_cap_tier"], 0) + 1

        if not dry_run:
            # Update ALL rows for this (symbol, market) — duplicates are common
            # because securities get re-added when scanners flag them.
            conn.execute(
                """
                UPDATE securities SET
                    sector = COALESCE(?, sector),
                    market_cap_tier = ?,
                    market_cap_usd = ?,
                    context_updated_at = ?
                WHERE symbol = ? AND market = ?
                """,
                (res["sector"], res["market_cap_tier"], res["market_cap_usd"],
                 now, symbol, market),
            )
            updated += 1

    if not dry_run:
        conn.commit()
    conn.close()

    if verbose:
        print()
        print(f"Done. Processed {len(rows)} unique symbols, updated {updated} (dry_run={dry_run}).")
        print(f"Errors: {len(errors)}  ETFs (sector NULL): {len(etfs)}")
        print()
        print("By sector:")
        for s, n in sorted(by_sector.items(), key=lambda x: -x[1]):
            print(f"  {s:14s} {n}")
        print()
        print("By cap tier:")
        for t in ("MICRO", "SMALL", "MID", "LARGE", "MEGA"):
            n = by_cap_tier.get(t, 0)
            print(f"  {t:6s} {n}")
        if etfs:
            print()
            print("ETFs (sector left NULL):")
            for s, m, n in etfs:
                print(f"  {m} {s}  {n}")
        if errors:
            print()
            print("Errors:")
            for s, m, e in errors:
                print(f"  {m} {s}: {e}")

    return {
        "processed": len(rows), "updated": updated,
        "errors": errors, "by_sector": by_sector, "by_cap_tier": by_cap_tier,
        "etfs": etfs,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Classify securities (sector + cap tier) via yfinance")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--all", action="store_true", help="Re-classify already-tagged securities too")
    args = parser.parse_args()
    populate(dry_run=args.dry_run, only_unclassified=not args.all)
