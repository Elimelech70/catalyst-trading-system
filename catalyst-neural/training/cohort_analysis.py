"""
Pattern analysis across all 15 cohorts.

Implements:
  1. Strategy-level Kruskal-Wallis ANOVA + variance decomposition (η²)
  2. Cohort-metric Spearman correlations (vs dir_acc)
  3. Deflated Sharpe Ratio per cohort (Bailey & López de Prado 2014, JPM)
  4. Probability of Backtest Overfitting across the set (Bailey/Borwein/LdP/Zhu 2014)
  5. Pairwise Dunn post-hoc with Benjamini-Hochberg FDR correction
  6. Sweet-spot detection (vol × dir_acc)
  7. Common failure modes (stubbed — requires per-sample prediction logging)

Note: DSR and PBO are implemented from the source papers because finance_ml
does not ship them. Math is ~100 lines total and trivially testable.
"""

import sys
import json
import math
from pathlib import Path
from itertools import combinations
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
from scipy import stats

from storage.database import get_connection

DIR_ACC_CHANCE = 33.3  # 3-class baseline


# ── Data loading ─────────────────────────────────────────────────────────

def load_results(draw_date=None):
    """Load all cohort results. If draw_date is None, take the most recent."""
    conn = get_connection()
    if draw_date is None:
        row = conn.execute(
            "SELECT MAX(draw_date) AS d FROM cohort_experiments "
            "WHERE median_val_loss IS NOT NULL"
        ).fetchone()
        draw_date = row["d"] if row else None
    if draw_date is None:
        conn.close()
        return [], None
    rows = conn.execute(
        "SELECT cohort_id, strategy_id, instance_id, n_symbols, "
        "       median_val_loss, median_dir_acc, median_val_mae, "
        "       effective_sample_n, cohort_metrics_json, symbols_json "
        "FROM cohort_experiments "
        "WHERE draw_date = ? AND median_val_loss IS NOT NULL "
        "ORDER BY strategy_id, instance_id",
        (draw_date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows], draw_date


# ── 1. Strategy-level ANOVA + η² ─────────────────────────────────────────

def strategy_anova(rows, metric="median_dir_acc"):
    """Kruskal-Wallis omnibus on per-cohort `metric` grouped by strategy.
    Returns dict with H, p-value, η² (variance decomposition), by-strategy means."""
    by_strategy = defaultdict(list)
    for r in rows:
        by_strategy[r["strategy_id"]].append(r[metric])
    groups = [by_strategy[s] for s in sorted(by_strategy.keys())]
    if len(groups) < 2 or min(len(g) for g in groups) < 2:
        return {"H": float("nan"), "p_value": float("nan"),
                "eta_squared": float("nan"), "by_strategy": dict(by_strategy)}
    H, p = stats.kruskal(*groups)
    grand = np.mean([x for g in groups for x in g])
    between = sum(len(g) * (np.mean(g) - grand) ** 2 for g in groups)
    within  = sum(sum((x - np.mean(g)) ** 2 for x in g) for g in groups)
    eta_sq  = between / (between + within) if (between + within) > 0 else 0.0
    return {
        "H":           float(H),
        "p_value":     float(p),
        "eta_squared": float(eta_sq),
        "by_strategy": {k: {"mean": float(np.mean(v)),
                            "std":  float(np.std(v, ddof=1) if len(v) > 1 else 0.0),
                            "n":    len(v)}
                        for k, v in by_strategy.items()},
    }


def pairwise_dunn(rows, metric="median_dir_acc", alpha=0.05):
    """Dunn's post-hoc test (non-parametric pairwise after K-W omnibus).
    BH-FDR corrected at α. Returns list of {pair, z, p_raw, p_adj, significant}."""
    by_strategy = defaultdict(list)
    for r in rows:
        by_strategy[r["strategy_id"]].append(r[metric])
    strategies = sorted(by_strategy.keys())
    if len(strategies) < 2:
        return []

    # Rank all values together
    all_vals = []
    all_groups = []
    for s in strategies:
        for v in by_strategy[s]:
            all_vals.append(v); all_groups.append(s)
    ranks = stats.rankdata(all_vals)
    rank_sum = {s: 0.0 for s in strategies}
    rank_n   = {s: 0   for s in strategies}
    for g, r in zip(all_groups, ranks):
        rank_sum[g] += r; rank_n[g] += 1
    N = len(all_vals)

    results = []
    pairs = list(combinations(strategies, 2))
    p_raw = []
    for a, b in pairs:
        mean_a = rank_sum[a] / rank_n[a]
        mean_b = rank_sum[b] / rank_n[b]
        se = math.sqrt((N * (N + 1) / 12.0) * (1.0 / rank_n[a] + 1.0 / rank_n[b]))
        z = (mean_a - mean_b) / se if se > 0 else 0.0
        p = 2 * (1 - stats.norm.cdf(abs(z)))
        results.append({"pair": (a, b), "z": float(z), "p_raw": float(p)})
        p_raw.append(p)

    # Benjamini-Hochberg FDR
    n = len(p_raw)
    order = np.argsort(p_raw)
    p_adj = [0.0] * n
    for i, idx in enumerate(order):
        adj = p_raw[idx] * n / (i + 1)
        p_adj[idx] = min(adj, 1.0)
    # Ensure monotonic (running min from largest p)
    for i in range(n - 2, -1, -1):
        idx_now  = order[i]; idx_next = order[i + 1]
        if p_adj[idx_now] > p_adj[idx_next]:
            p_adj[idx_now] = p_adj[idx_next]
    for r, p in zip(results, p_adj):
        r["p_adj"] = float(p); r["significant"] = bool(p < alpha)
    return results


# ── 2. Cohort-metric correlations ────────────────────────────────────────

_DESCRIPTOR_KEYS = ("median_realized_vol", "sector_entropy", "cap_entropy",
                    "news_density", "effective_sample_n")


def cohort_metric_correlations(rows, target_metric="median_dir_acc"):
    """Spearman ρ between cohort descriptors and the target metric.
    Returns dict {descriptor_key: {rho, p_value}}."""
    targets = np.array([r[target_metric] for r in rows], dtype=float)
    out = {}
    for k in _DESCRIPTOR_KEYS:
        vals = []
        for r in rows:
            m = json.loads(r["cohort_metrics_json"])
            v = m.get(k)
            vals.append(v if v is not None else np.nan)
        vals = np.array(vals, dtype=float)
        mask = ~np.isnan(vals)
        if mask.sum() < 3:
            out[k] = {"rho": float("nan"), "p_value": float("nan"), "n": int(mask.sum())}
            continue
        rho, p = stats.spearmanr(vals[mask], targets[mask])
        out[k] = {"rho": float(rho), "p_value": float(p), "n": int(mask.sum())}
    return out


# ── 3. Deflated Sharpe Ratio ─────────────────────────────────────────────

def _deflated_sharpe(returns_series, n_trials):
    """Bailey & López de Prado (2014, JPM) deflated Sharpe ratio.

    Returns DSR as the cumulative probability that the true SR > 0 under the
    null of N trials. DSR > 0.95 is the standard "winner" threshold.

    Args:
        returns_series: array of per-fold returns (e.g., dir_acc - chance)
        n_trials: number of cohorts being compared (N for the deflation)
    """
    r = np.asarray(returns_series, dtype=np.float64)
    n = len(r)
    if n < 2:
        return float("nan")
    mean_r = r.mean()
    sd_r   = r.std(ddof=1)
    if sd_r < 1e-12:
        return float("nan")
    sr = mean_r / sd_r
    # Higher moments
    skew = ((r - mean_r) ** 3).mean() / (sd_r ** 3 + 1e-12)
    kurt = ((r - mean_r) ** 4).mean() / (sd_r ** 4 + 1e-12)
    # Expected max SR under null over N_trials (LdP 2014 eq. 10, Euler-Mascheroni)
    em = ((1 - np.euler_gamma) * stats.norm.ppf(1 - 1.0 / n_trials)
          + np.euler_gamma * stats.norm.ppf(1 - 1.0 / (n_trials * np.e)))
    # Variance of SR estimate (LdP 2014 eq. 9)
    sigma_sr = math.sqrt(max(1e-12,
        (1 - skew * sr + ((kurt - 1) / 4.0) * sr ** 2) / (n - 1)))
    z = (sr - em) / sigma_sr
    return float(stats.norm.cdf(z))


def deflated_sharpe(rows):
    """DSR per cohort. Treats per-fold dir_acc lift above 33.3% as the return series.
    Returns dict {cohort_id: {sr, dsr}}."""
    n_trials = len(rows)
    out = {}
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        lifts = [f["final_dir_acc"] - DIR_ACC_CHANCE for f in m["folds"]]
        sr = float(np.mean(lifts) / (np.std(lifts, ddof=1) + 1e-12))
        out[r["cohort_id"]] = {"sr": sr,
                               "dsr": _deflated_sharpe(lifts, n_trials)}
    return out


# ── 4. Probability of Backtest Overfitting ───────────────────────────────

def _pbo(M, S=None):
    """Bailey/Borwein/López de Prado/Zhu (2014) PBO.

    Partitions fold dimension into S equal subsets; iterates all C(S, S/2)
    in-sample / out-of-sample splits; counts how often the best in-sample
    cohort ranks BELOW the median out-of-sample (relative-rank inversion).

    Returns scalar in [0, 1]. PBO < 0.2 = winner generalises; > 0.5 = overfit.
    """
    M = np.asarray(M, dtype=np.float64)
    n_cohorts, n_folds = M.shape
    if S is None:
        S = n_folds
    if S % 2 == 1:
        S -= 1
    if S < 4 or n_cohorts < 2:
        return float("nan")

    sub = np.array_split(np.arange(n_folds), S)
    inversions = 0
    total = 0
    for in_idx in combinations(range(S), S // 2):
        in_folds  = np.concatenate([sub[i] for i in in_idx])
        out_folds = np.concatenate([sub[i] for i in range(S) if i not in in_idx])
        in_score  = M[:, in_folds].mean(axis=1)
        out_score = M[:, out_folds].mean(axis=1)
        best_in = int(np.argmax(in_score))
        # Where does the in-sample winner rank out-of-sample?
        # LdP's "logit" approach: count where out_score[best_in] is below median
        median_out = float(np.median(out_score))
        if out_score[best_in] < median_out:
            inversions += 1
        total += 1
    return inversions / total if total > 0 else float("nan")


def pbo(rows):
    """PBO across the 15-cohort × 5-fold matrix using per-fold dir_acc."""
    accs = []
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        accs.append([f["final_dir_acc"] for f in m["folds"]])
    M = np.array(accs)
    return _pbo(M)


# ── 5. Sweet-spot detection ──────────────────────────────────────────────

def sweet_spot(rows, descriptor="median_realized_vol", target="median_dir_acc"):
    """Return arrays (xs, ys) suitable for scatter + a one-line interpretation."""
    xs, ys, ids = [], [], []
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        v = m.get(descriptor)
        if v is None: continue
        xs.append(v); ys.append(r[target]); ids.append(r["cohort_id"])
    xs = np.array(xs); ys = np.array(ys)
    if len(xs) < 3:
        return {"xs": xs.tolist(), "ys": ys.tolist(), "cohort_ids": ids,
                "shape": "insufficient_data"}
    rho, p = stats.spearmanr(xs, ys)
    if abs(rho) < 0.2:
        shape = "flat"
    elif rho > 0:
        shape = "monotonic_positive"
    else:
        shape = "monotonic_negative"
    return {"xs": xs.tolist(), "ys": ys.tolist(), "cohort_ids": ids,
            "rho": float(rho), "p_value": float(p), "shape": shape}


# ── 6. Common failure modes (placeholder) ────────────────────────────────

def common_failure_modes(draw_date, threshold=0.8):
    """Identify samples misclassified by ≥threshold fraction of cohorts.

    Requires per-sample predictions persisted from each CPCV fold. As of
    2026-06-01 the CPCV trainer does NOT log per-sample predictions; doing so
    is a Phase 6 follow-up that needs to be added to training/cpcv_trainer.py.

    For now this returns a stub message.
    """
    return {
        "implemented": False,
        "note": ("Per-sample prediction logging not yet added to cpcv_trainer.py. "
                 "When added, this function will aggregate per-(news_category, "
                 "sector, cap_tier) misclassification counts to identify the "
                 "architecture's blind spots."),
    }


# ── Driver ───────────────────────────────────────────────────────────────

def run_all_analyses(draw_date=None):
    """Run every analysis and return a single dict suitable for Phase 7 report."""
    rows, draw_date = load_results(draw_date)
    if not rows:
        return {"error": "no completed cohorts found"}

    return {
        "draw_date":      draw_date,
        "n_cohorts":      len(rows),
        "leaderboard":    sorted(rows, key=lambda r: -r["median_dir_acc"]),
        "anova_dir_acc":  strategy_anova(rows, "median_dir_acc"),
        "anova_val_loss": strategy_anova(rows, "median_val_loss"),
        "pairwise_dunn":  pairwise_dunn(rows, "median_dir_acc"),
        "correlations":   cohort_metric_correlations(rows, "median_dir_acc"),
        "deflated_sharpe": deflated_sharpe(rows),
        "pbo":            pbo(rows),
        "sweet_spot_vol": sweet_spot(rows, "median_realized_vol", "median_dir_acc"),
        "sweet_spot_news": sweet_spot(rows, "news_density",       "median_dir_acc"),
        "common_failures": common_failure_modes(draw_date),
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Pattern analysis across all cohorts")
    p.add_argument("--draw-date", default=None)
    args = p.parse_args()
    out = run_all_analyses(args.draw_date)
    if "error" in out:
        print(out["error"]); sys.exit(1)
    print(f"\n=== Cohort experiment results — {out['draw_date']} ===")
    print(f"Cohorts complete: {out['n_cohorts']}")
    print(f"\nLeaderboard (top 5 by dir_acc):")
    for r in out["leaderboard"][:5]:
        print(f"  {r['cohort_id']:>20}  dir_acc={r['median_dir_acc']:.2f}%  "
              f"val_loss={r['median_val_loss']:.4f}")
    print(f"\nStrategy ANOVA (dir_acc): H={out['anova_dir_acc']['H']:.2f}  "
          f"p={out['anova_dir_acc']['p_value']:.4f}  "
          f"η²={out['anova_dir_acc']['eta_squared']:.3f}")
    print(f"PBO: {out['pbo']:.3f}")
    print(f"\nDeflated Sharpe (top 5 cohorts):")
    dsr_sorted = sorted(out["deflated_sharpe"].items(),
                       key=lambda kv: -kv[1]["dsr"])
    for cid, v in dsr_sorted[:5]:
        print(f"  {cid:>20}  SR={v['sr']:+.2f}  DSR={v['dsr']:.3f}")
    print(f"\nCohort-metric correlations with dir_acc:")
    for k, v in out["correlations"].items():
        print(f"  {k:>22}  ρ={v['rho']:+.3f}  p={v['p_value']:.4f}  n={v['n']}")
