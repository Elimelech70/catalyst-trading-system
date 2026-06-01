"""
Cohort assignment for the 15-cohort universe-selection experiment.

Per catalyst-cohort-experiments-architecture v0.2 Section 5:
  Strategy A (sector-pure):  Tech / Financials / Healthcare for instances 1/2/3
  Strategy B (vol-tiered):   top decile / 5th decile / bottom decile
  Strategy C (stratified):   three random stratified draws (seeds 42/43/44)
  Strategy D (HRP cluster):  largest / 2nd-largest / 3rd-largest correlation cluster
  Strategy E (mover / null): top-150 by vol / mid-rank 150–300 / uniform random 150

Hard constraints (Section 5.4):
  - ≥ 1000 5m candles
  - market is US
  - ≥ 500 forward_returns rows with non-NULL return_5m
  - ≥ 60 days of realized_vol_30d history

Each cohort's symbol list is persisted to the cohort_experiments table.
"""

import sys
import json
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from storage.database import get_connection

COHORT_SIZE = 150
ELIGIBLE_MIN_CANDLES = 1000
ELIGIBLE_MIN_RETURNS = 500
# 60-day vol history is the architecture's stability requirement; relaxed to 1
# for the initial cohort run because we have 5y of candles but only just started
# the daily vol-snapshot job. A historical-vol backfill (storage/realized_vol.py
# called for each of the past 60 trading days) would re-enable the 60-day
# constraint properly. Left as a follow-up.
ELIGIBLE_MIN_VOL_DAYS = 1
MARKET_DEFAULT = "US"

# Sector instances 1/2/3 — see arch v0.2 §4.2
SECTOR_INSTANCES = {1: "TECH", 2: "FINANCIAL", 3: "HEALTH"}
# Decile instances — 9 = top decile (loudest), 0 = bottom (quietest)
VOL_DECILE_INSTANCES = {1: 9, 2: 4, 3: 0}
# Random seeds for stratified draws (Strategy C) and mover/null (E)
SEEDS = {1: 42, 2: 43, 3: 44}


# ── Eligibility ──────────────────────────────────────────────────────────

def _eligible_universe(conn, market=MARKET_DEFAULT):
    """Return list of dict rows for symbols meeting all four hard constraints."""
    rows = conn.execute("""
        SELECT s.symbol, s.market, s.sector, s.market_cap_tier, s.realized_vol_30d,
               (SELECT COUNT(*) FROM candles c
                  WHERE c.symbol = s.symbol AND c.market = s.market
                    AND c.timeframe = '5m') AS n_candles,
               (SELECT COUNT(*) FROM forward_returns f
                  WHERE f.symbol = s.symbol AND f.market = s.market
                    AND f.timeframe = '5m' AND f.return_5m IS NOT NULL) AS n_returns,
               (SELECT COUNT(*) FROM realized_vol_history h
                  WHERE h.symbol = s.symbol AND h.market = s.market) AS n_vol_days
        FROM securities s
        WHERE s.removed_at IS NULL
          AND s.market = ?
          AND s.realized_vol_30d IS NOT NULL
    """, (market,)).fetchall()
    return [dict(r) for r in rows
            if r["n_candles"]  >= ELIGIBLE_MIN_CANDLES
            and r["n_returns"] >= ELIGIBLE_MIN_RETURNS
            and r["n_vol_days"] >= ELIGIBLE_MIN_VOL_DAYS]


# ── Strategy A: sector-pure ──────────────────────────────────────────────

def strategy_A(conn, instance_id, market=MARKET_DEFAULT):
    sector = SECTOR_INSTANCES[instance_id]
    pool = [r for r in _eligible_universe(conn, market) if r["sector"] == sector]
    pool.sort(key=lambda r: r["realized_vol_30d"], reverse=True)
    return [(r["symbol"], r["market"]) for r in pool[:COHORT_SIZE]]


# ── Strategy B: volatility-tiered ────────────────────────────────────────

def strategy_B(conn, instance_id, market=MARKET_DEFAULT):
    decile_target = VOL_DECILE_INSTANCES[instance_id]
    pool = _eligible_universe(conn, market)
    if not pool:
        return []
    vols = np.array([r["realized_vol_30d"] for r in pool])
    # 9 decile boundaries -> 10 buckets indexed 0..9
    deciles = np.searchsorted(np.quantile(vols, np.arange(1, 10) / 10), vols)
    pool_decile = [pool[i] for i in range(len(pool)) if deciles[i] == decile_target]
    rng = random.Random(SEEDS[instance_id])
    rng.shuffle(pool_decile)
    return [(r["symbol"], r["market"]) for r in pool_decile[:COHORT_SIZE]]


# ── Strategy C: stratified mix ───────────────────────────────────────────

def strategy_C(conn, instance_id, market=MARKET_DEFAULT):
    pool = _eligible_universe(conn, market)
    rng = random.Random(SEEDS[instance_id])
    by_sector = {}
    for r in pool:
        by_sector.setdefault(r["sector"] or "_UNKNOWN", []).append(r)
    chosen, chosen_keys = [], set()
    # Ensure ≥10 per sector when sector has at least 10 eligible
    for sector, group in by_sector.items():
        rng.shuffle(group)
        take = min(10, len(group))
        for r in group[:take]:
            key = (r["symbol"], r["market"])
            chosen.append(r); chosen_keys.add(key)
    # Fill the rest randomly from remaining pool
    remaining = [r for r in pool
                 if (r["symbol"], r["market"]) not in chosen_keys]
    rng.shuffle(remaining)
    for r in remaining:
        if len(chosen) >= COHORT_SIZE:
            break
        chosen.append(r)
    return [(r["symbol"], r["market"]) for r in chosen[:COHORT_SIZE]]


# ── Strategy D: HRP correlation clusters ─────────────────────────────────

def strategy_D(conn, instance_id, market=MARKET_DEFAULT,
              return_window=1500):
    """Hierarchical clustering on 5m return correlation, take Nth-largest cluster.

    Architecture v0.2 §5.4: d = √(½(1−ρ)), single-linkage agglomerative.
    instance_id 1/2/3 → 1st/2nd/3rd-largest cluster by member count.
    """
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform

    pool = _eligible_universe(conn, market)
    if len(pool) < COHORT_SIZE * 2:
        raise RuntimeError(
            f"HRP needs at least {COHORT_SIZE*2} eligible symbols; got {len(pool)}"
        )

    keys = [(r["symbol"], r["market"]) for r in pool]

    # Build per-symbol 5m log-return series of length `return_window`
    return_series = {}
    for sym, mkt in keys:
        rows = conn.execute(
            "SELECT close FROM candles "
            "WHERE symbol=? AND market=? AND timeframe='5m' "
            "AND close > 0.0001 ORDER BY timestamp DESC LIMIT ?",
            (sym, mkt, return_window + 1)
        ).fetchall()
        if len(rows) < return_window // 2:
            continue
        closes = np.array([r["close"] for r in rows][::-1], dtype=np.float64)
        returns = np.diff(np.log(closes))
        return_series[(sym, mkt)] = returns[-return_window:]

    keys = list(return_series.keys())
    if len(keys) < COHORT_SIZE * 2:
        raise RuntimeError(
            f"HRP: after filtering for sufficient bars, only {len(keys)} symbols. "
            f"Need ≥ {COHORT_SIZE*2}."
        )

    # Align all series to the common shortest length
    min_len = min(len(v) for v in return_series.values())
    R = np.vstack([return_series[k][-min_len:] for k in keys])

    corr = np.corrcoef(R)
    # numerical safety — corr should be in [-1, 1]
    corr = np.clip(corr, -1.0, 1.0)
    d = np.sqrt(0.5 * (1.0 - corr))
    np.fill_diagonal(d, 0.0)
    Z = linkage(squareform(d, checks=False), method="single")

    # Iterate cluster counts; find the smallest n_clusters such that the
    # instance_id-th largest cluster has ≥ COHORT_SIZE members.
    for n_clusters in range(3, min(60, len(keys))):
        labels = fcluster(Z, n_clusters, criterion="maxclust")
        # Sort cluster labels by descending size; the i-th largest = ranks[i]
        size_by_label = np.bincount(labels)[1:]  # labels are 1-based
        ordered_labels = np.argsort(size_by_label)[::-1] + 1  # desc by size
        if instance_id > len(ordered_labels):
            continue
        target_label = int(ordered_labels[instance_id - 1])
        target_size = int(size_by_label[target_label - 1])
        if target_size >= COHORT_SIZE:
            members = [keys[i] for i in range(len(keys)) if labels[i] == target_label]
            random.Random(SEEDS[instance_id]).shuffle(members)
            return members[:COHORT_SIZE]

    raise RuntimeError(
        f"HRP: could not produce instance {instance_id} of size {COHORT_SIZE}. "
        f"Universe may be too small or too correlated."
    )


# ── Strategy E: mover / mid-rank / null ──────────────────────────────────

def strategy_E(conn, instance_id, market=MARKET_DEFAULT):
    pool = _eligible_universe(conn, market)
    pool.sort(key=lambda r: r["realized_vol_30d"], reverse=True)
    if instance_id == 1:
        sliced = pool[:COHORT_SIZE]
    elif instance_id == 2:
        sliced = pool[COHORT_SIZE:COHORT_SIZE * 2]
    elif instance_id == 3:
        rng = random.Random(SEEDS[instance_id])
        sliced = rng.sample(pool, min(COHORT_SIZE, len(pool)))
    else:
        raise ValueError(f"strategy_E: unknown instance_id {instance_id}")
    return [(r["symbol"], r["market"]) for r in sliced]


# ── Driver ───────────────────────────────────────────────────────────────

STRATEGIES = {"A": strategy_A, "B": strategy_B, "C": strategy_C,
              "D": strategy_D, "E": strategy_E}


def assign_all_cohorts(draw_date=None, vol_snapshot_date=None,
                       market=MARKET_DEFAULT):
    """Generate all 15 cohorts and persist them to the cohort_experiments table.
    Returns list of (cohort_id, n_symbols)."""
    from datetime import datetime
    if draw_date is None:
        draw_date = datetime.utcnow().strftime("%Y-%m-%d")
    if vol_snapshot_date is None:
        vol_snapshot_date = draw_date

    conn = get_connection()
    cohorts = []
    for strategy_id in ("A", "B", "C", "D", "E"):
        fn = STRATEGIES[strategy_id]
        for instance_id in (1, 2, 3):
            cohort_id = f"{strategy_id}{instance_id}_{draw_date}_v1"
            try:
                symbols = fn(conn, instance_id, market)
            except Exception as e:
                print(f"  ERROR {cohort_id}: {e}")
                cohorts.append((cohort_id, 0))
                continue

            sector_filter = (SECTOR_INSTANCES[instance_id]
                             if strategy_id == "A" else None)
            conn.execute("""
                INSERT OR REPLACE INTO cohort_experiments
                (cohort_id, strategy_id, instance_id, draw_date,
                 vol_snapshot_date, sector_filter, symbols_json, n_symbols)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cohort_id, strategy_id, instance_id, draw_date,
                  vol_snapshot_date, sector_filter,
                  json.dumps(symbols), len(symbols)))
            cohorts.append((cohort_id, len(symbols)))
            print(f"  {cohort_id}: {len(symbols):>3} symbols")
    conn.commit()
    conn.close()
    return cohorts


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Assign all 15 cohorts for the universe experiment")
    p.add_argument("--draw-date", default=None,
                  help="YYYY-MM-DD draw date (default today UTC)")
    p.add_argument("--market", default=MARKET_DEFAULT)
    args = p.parse_args()
    print(f">>> Assigning 15 cohorts (5 strategies × 3 instances)\n")
    cohorts = assign_all_cohorts(draw_date=args.draw_date, market=args.market)
    n_full = sum(1 for _, n in cohorts if n == COHORT_SIZE)
    print(f"\nDone: {n_full}/15 cohorts at full size ({COHORT_SIZE} symbols)")
