"""
Sequence all 15 cohorts through CPCV, persist per-cohort artifacts and the
aggregated metrics back to the cohort_experiments table.

Resumable: cohorts whose `median_val_loss` is already populated are skipped,
so a re-run continues from where it stopped. To force a re-run of a specific
cohort, NULL out its median_val_loss first.

Per architecture v0.2: 15 cohorts × 5 folds = 75 fits, ~7.5 hours on RTX 4050.
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.database import get_connection
from training.cpcv_trainer import run_cpcv_for_cohort


def run_all_cohorts(draw_date=None, resume=True, only_strategy=None):
    """Loop through 15 cohorts. Resumable — skips already-complete cohorts.

    Args:
        draw_date: filter to one draw date; if None, the most recent.
        resume: if True, skip cohorts with non-NULL median_val_loss.
        only_strategy: if set ('A'..'E'), only run that strategy's cohorts.
    """
    conn = get_connection()

    where = []
    params = []
    if draw_date:
        where.append("draw_date = ?"); params.append(draw_date)
    if only_strategy:
        where.append("strategy_id = ?"); params.append(only_strategy)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    cohorts = conn.execute(
        f"SELECT cohort_id, strategy_id, instance_id, n_symbols, "
        f"       symbols_json, median_val_loss "
        f"FROM cohort_experiments {where_sql} "
        f"ORDER BY strategy_id, instance_id",
        params
    ).fetchall()

    if not cohorts:
        print("No cohorts found in cohort_experiments table.")
        print("Run `python storage/cohort_assignment.py` first.")
        return

    to_run = []
    skipped = []
    for c in cohorts:
        if resume and c["median_val_loss"] is not None:
            skipped.append(c["cohort_id"])
            continue
        if c["n_symbols"] == 0:
            skipped.append(f"{c['cohort_id']} (empty)")
            continue
        to_run.append(c)

    print(f"\n{'='*60}")
    print(f"Cohort experiment runner")
    print(f"{'='*60}")
    print(f"Total cohorts:    {len(cohorts)}")
    print(f"Already complete: {len(skipped)}")
    print(f"To run:           {len(to_run)}")
    if skipped:
        print(f"Skipped (resume): {', '.join(skipped[:6])}"
              f"{' ...' if len(skipped) > 6 else ''}")
    print()

    t0 = time.time()
    for i, c in enumerate(to_run, 1):
        elapsed_min = (time.time() - t0) / 60
        avg_min_per_cohort = elapsed_min / max(i - 1, 1) if i > 1 else 0
        eta_min = avg_min_per_cohort * (len(to_run) - i + 1)
        print(f"\n[{i}/{len(to_run)}] {c['cohort_id']}  "
              f"(elapsed {elapsed_min:.1f}m, ETA {eta_min:.0f}m)")

        symbols = [tuple(p) for p in json.loads(c["symbols_json"])]
        try:
            result = run_cpcv_for_cohort(symbols, c["cohort_id"])
        except Exception as e:
            print(f"  COHORT FAILED: {e}")
            import traceback; traceback.print_exc()
            continue

        if "error" in result:
            print(f"  cohort skipped: {result['error']}")
            continue

        conn.execute("""
            UPDATE cohort_experiments
            SET median_val_loss     = ?,
                median_dir_acc      = ?,
                median_val_mae      = ?,
                effective_sample_n  = ?,
                cohort_metrics_json = ?
            WHERE cohort_id = ?
        """, (result["median_val_loss"], result["median_dir_acc"],
              result["median_val_mae"], result["effective_sample_n"],
              json.dumps(result), c["cohort_id"]))
        conn.commit()

    conn.close()
    total_min = (time.time() - t0) / 60
    print(f"\n{'='*60}")
    print(f"Experiment finished in {total_min:.1f} min")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Cohort experiment runner")
    p.add_argument("--draw-date", default=None,
                  help="Filter to one draw date (default: all)")
    p.add_argument("--no-resume", action="store_true",
                  help="Re-run all cohorts even if already complete")
    p.add_argument("--strategy", default=None, choices=list("ABCDE"),
                  help="Only run cohorts of this strategy")
    args = p.parse_args()
    run_all_cohorts(draw_date=args.draw_date, resume=not args.no_resume,
                   only_strategy=args.strategy)
