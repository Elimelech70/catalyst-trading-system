"""
Backfill realized_vol_30d snapshots for every trading day in a historical
window. Each snapshot date uses the prior 30 trading days of candles.

This recovers the 60-day vol history needed for the architecture's
ELIGIBLE_MIN_VOL_DAYS=60 constraint without waiting 60 calendar days.
Uses the 5-year candle backfill already in place.

Run once after the Polygon backfill completes:
    python storage/backfill_vol_history.py --days 90
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.realized_vol import run_vol_snapshot


def backfill_history(days=90, market="US"):
    """Run run_vol_snapshot for each of the past `days` business days.
    Skips snapshots that already exist in realized_vol_history."""
    today = datetime.utcnow().date()
    # Walk backwards through calendar days; skip weekends (5 = Sat, 6 = Sun)
    snapshots_done = 0
    snapshots_skipped = 0
    for delta in range(0, days * 2):  # generous upper bound
        if snapshots_done + snapshots_skipped >= days:
            break
        d = today - timedelta(days=delta)
        if d.weekday() >= 5:
            continue
        date_str = d.strftime("%Y-%m-%d")
        print(f"\n>>> Snapshot {date_str} ({snapshots_done + snapshots_skipped + 1}/{days})")
        n_ok, n_skip = run_vol_snapshot(as_of_date=date_str, markets=(market,))
        if n_ok > 0:
            snapshots_done += 1
        else:
            snapshots_skipped += 1
    print(f"\nVol history backfill complete: {snapshots_done} dates populated, "
          f"{snapshots_skipped} dates skipped")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Backfill historical realized vol snapshots")
    p.add_argument("--days", type=int, default=90,
                  help="Number of trading days to backfill (default 90)")
    p.add_argument("--market", default="US")
    args = p.parse_args()
    backfill_history(days=args.days, market=args.market)
