"""
Name of Application: Catalyst Trading System
Name of file: context_regime.py
Version: 0.1.0
Last Updated: 2026-05-23
Purpose: Populate context_regime_summary; run Test 1 KS distribution gate.

REVISION HISTORY:
v0.1.0 (2026-05-23) - Initial implementation. Phase 5 of v0.4 context-conditioned plan.
  - Aggregates per-(news_category, sector, cap_tier, market) cell returns
  - Populates context_regime_summary table
  - Runs pairwise Kolmogorov-Smirnov tests on return distributions
  - Reports cells with sample_count > N_MIN as statistically meaningful
  - Pass criterion (architecture Sec 12.1): at least 5 pairs with p < 0.01

Reference: Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md Section 12.1
           Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md Phase 5
"""

import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from storage.database import get_connection

# Architecture Section 12.1 / 12.2 thresholds
SAMPLE_COUNT_MIN = 100        # cells with fewer samples excluded from KS
KS_PVALUE_GATE = 0.01         # KS test threshold for "statistically distinguishable"
KS_PAIRS_REQUIRED = 5         # Pass criterion: at least N pairs below p-value gate

DIRECTION_THRESHOLD_PCT = 0.05  # matches CandleDataset.return_to_direction


def _ks_2samp(a: np.ndarray, b: np.ndarray) -> Tuple[float, float]:
    """
    Two-sample Kolmogorov-Smirnov test.

    Returns (D, p_value). Falls back to a simple bootstrap p-value if scipy
    isn't available (we shouldn't require scipy just for this — but use it if
    present).
    """
    try:
        from scipy.stats import ks_2samp
        res = ks_2samp(a, b)
        return float(res.statistic), float(res.pvalue)
    except ImportError:
        pass

    # Manual KS-D and asymptotic p-value (Smirnov)
    a_sorted = np.sort(a)
    b_sorted = np.sort(b)
    n_a, n_b = len(a_sorted), len(b_sorted)
    all_vals = np.concatenate([a_sorted, b_sorted])
    cdf_a = np.searchsorted(a_sorted, all_vals, side="right") / n_a
    cdf_b = np.searchsorted(b_sorted, all_vals, side="right") / n_b
    d = float(np.max(np.abs(cdf_a - cdf_b)))
    # Smirnov approximate p-value
    en = np.sqrt(n_a * n_b / (n_a + n_b))
    # Kolmogorov distribution: P(D > d) = 2 * sum_{k=1..inf} (-1)^(k-1) exp(-2 k^2 (en+0.12+0.11/en)^2 d^2)
    lam = (en + 0.12 + 0.11 / en) * d
    p = 2.0 * sum((-1) ** (k - 1) * np.exp(-2.0 * (k * lam) ** 2) for k in range(1, 50))
    p = max(0.0, min(1.0, p))
    return d, float(p)


def _direction_of(ret_pct: float) -> int:
    if ret_pct > DIRECTION_THRESHOLD_PCT:
        return 0  # bullish
    if ret_pct < -DIRECTION_THRESHOLD_PCT:
        return 1  # bearish
    return 2     # neutral


def collect_returns_by_cell(
    timeframe: str = "5m",
    include_news_dim: bool = True,
) -> Dict[Tuple[str, str, str, str], Dict]:
    """
    Group forward returns into (news_category, sector, cap_tier, market) cells.

    When include_news_dim=False, news_category is fixed to '_no_news_dim' so the
    cells reduce to (sector × cap_tier × market). Use this when the news table
    is empty / sparse and you still want a Test 1 signal on the security axis.

    Returns: {cell_key: {
        "ret_5m": [floats], "ret_15m": [floats], "ret_1h": [floats],
        "dir_counts": [bull, bear, neutral],
    }}
    """
    conn = get_connection()

    # Build sector / cap_tier lookup once
    sec_rows = conn.execute(
        "SELECT symbol, market, sector, market_cap_tier "
        "FROM securities WHERE removed_at IS NULL"
    ).fetchall()
    sec_lookup: Dict[Tuple[str, str], Tuple[Optional[str], Optional[str]]] = {}
    for r in sec_rows:
        key = (r["symbol"], r["market"])
        # Latest non-NULL wins (we don't reorder here — duplicates may exist).
        if key in sec_lookup and sec_lookup[key][0] is not None:
            continue
        sec_lookup[key] = (r["sector"], r["market_cap_tier"])

    # News lookup. When include_news_dim=True, build a per-symbol sorted list
    # of (published_at, category) so we can attach the most-recent news category
    # in [t-4h, t] for each forward-return sample.
    news_by_sym: Dict[str, List[Tuple[str, str]]] = {}
    if include_news_dim:
        for n in conn.execute(
            "SELECT symbols, published_at, news_category_primary "
            "FROM news WHERE news_category_primary IS NOT NULL "
            "ORDER BY published_at ASC"
        ):
            for s in (n["symbols"] or "").split(","):
                s = s.strip().upper()
                if not s:
                    continue
                news_by_sym.setdefault(s, []).append(
                    (n["published_at"], n["news_category_primary"])
                )

    # Iterate forward_returns
    rows = conn.execute(
        "SELECT symbol, market, timestamp, return_5m, return_15m, return_1h "
        "FROM forward_returns WHERE timeframe = ? AND return_5m IS NOT NULL",
        (timeframe,),
    )

    cells: Dict[Tuple[str, str, str, str], Dict] = {}

    def _empty_cell():
        return {"ret_5m": [], "ret_15m": [], "ret_1h": [], "dir_counts": [0, 0, 0]}

    for r in rows:
        sym, mkt, ts = r["symbol"], r["market"], r["timestamp"]
        sector, cap_tier = sec_lookup.get((sym, mkt), (None, None))
        if sector is None:
            sector = "OTHER"
        if cap_tier is None:
            cap_tier = "OTHER"

        if include_news_dim:
            # Look up most-recent news category in [t-4h, t] for this symbol.
            news_cat = "_no_news_"
            sym_news = news_by_sym.get(sym.upper())
            if sym_news:
                # Linear scan (good enough for current 0-row case; bisect later)
                for pub, cat in reversed(sym_news):
                    if pub <= ts:
                        # Within 4 hours?
                        try:
                            ts_dt = datetime.fromisoformat(
                                ts.replace("+00:00", "").replace("Z", "")
                            )
                            pub_dt = datetime.fromisoformat(
                                pub.replace("+00:00", "").replace("Z", "")
                            )
                            if (ts_dt - pub_dt).total_seconds() <= 4 * 3600:
                                news_cat = cat
                        except ValueError:
                            pass
                        break
        else:
            news_cat = "_no_news_dim"

        key = (news_cat, sector, cap_tier, mkt)
        cell = cells.setdefault(key, _empty_cell())
        ret_5m = r["return_5m"]
        cell["ret_5m"].append(ret_5m)
        if r["return_15m"] is not None:
            cell["ret_15m"].append(r["return_15m"])
        if r["return_1h"] is not None:
            cell["ret_1h"].append(r["return_1h"])
        cell["dir_counts"][_direction_of(ret_5m)] += 1

    conn.close()
    return cells


def populate_summary_table(cells: Dict[Tuple[str, str, str, str], Dict]) -> int:
    """Write the cells into context_regime_summary. Replaces existing rows."""
    conn = get_connection()
    conn.execute("DELETE FROM context_regime_summary")
    now = datetime.utcnow().isoformat()
    n = 0
    for (news_cat, sector, cap_tier, market), c in cells.items():
        n_total = sum(c["dir_counts"]) or 1
        r5 = np.asarray(c["ret_5m"], dtype=np.float32)
        r15 = np.asarray(c["ret_15m"], dtype=np.float32) if c["ret_15m"] else r5[:0]
        r1h = np.asarray(c["ret_1h"], dtype=np.float32) if c["ret_1h"] else r5[:0]
        conn.execute(
            """
            INSERT INTO context_regime_summary (
                news_category, sector, cap_tier, market, sample_count,
                mean_return_5m, std_return_5m,
                mean_return_15m, std_return_15m,
                mean_return_1h, std_return_1h,
                direction_bullish_pct, direction_bearish_pct, direction_neutral_pct,
                last_computed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (news_cat, sector, cap_tier, market, sum(c["dir_counts"]),
             float(r5.mean()) if len(r5) else 0.0, float(r5.std()) if len(r5) else 0.0,
             float(r15.mean()) if len(r15) else 0.0, float(r15.std()) if len(r15) else 0.0,
             float(r1h.mean()) if len(r1h) else 0.0, float(r1h.std()) if len(r1h) else 0.0,
             100.0 * c["dir_counts"][0] / n_total,
             100.0 * c["dir_counts"][1] / n_total,
             100.0 * c["dir_counts"][2] / n_total,
             now),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def run_ks_gate(
    cells: Dict[Tuple[str, str, str, str], Dict],
    n_min: int = SAMPLE_COUNT_MIN,
    p_gate: float = KS_PVALUE_GATE,
    horizon: str = "ret_5m",
) -> Dict:
    """
    Run pairwise Kolmogorov-Smirnov tests on well-populated cells.

    Returns: {
        "populated_cells": int,
        "pairs_tested": int,
        "pairs_below_p": int,
        "passes_gate": bool,
        "top_pairs": [(cell_a, cell_b, D, p)],   # most distinguishable
    }
    """
    populated = [
        (key, np.asarray(c[horizon], dtype=np.float32))
        for key, c in cells.items()
        if len(c[horizon]) >= n_min
    ]

    results = []
    for (k1, v1), (k2, v2) in combinations(populated, 2):
        D, p = _ks_2samp(v1, v2)
        results.append((k1, k2, D, p))
    results.sort(key=lambda x: x[3])  # most significant first

    below = sum(1 for r in results if r[3] < p_gate)
    return {
        "populated_cells": len(populated),
        "pairs_tested": len(results),
        "pairs_below_p": below,
        "passes_gate": below >= KS_PAIRS_REQUIRED,
        "top_pairs": results[:20],
    }


def report(verbose: bool = True) -> Dict:
    """
    Full Phase 5 pipeline:
      1. collect cell returns (with news dim and without)
      2. populate context_regime_summary
      3. run KS gate
      4. print summary
    Returns the gate result dict.
    """
    # First with news dim (will collapse to _no_news_ everywhere if news empty)
    cells_full = collect_returns_by_cell(timeframe="5m", include_news_dim=True)
    written = populate_summary_table(cells_full)
    if verbose:
        print(f"Populated context_regime_summary with {written:,} cells.")

    # If news table is empty, also run the 2D (sector × cap_tier) gate so we
    # still get a Test 1 signal on what we have.
    conn = get_connection()
    news_count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    conn.close()

    if news_count == 0 and verbose:
        print()
        print("⚠ news table is empty — full Test 1 cannot run.")
        print("  Falling back to 2D (sector × cap_tier × market) KS gate.")
        cells_no_news = collect_returns_by_cell(timeframe="5m", include_news_dim=False)
        gate = run_ks_gate(cells_no_news)
    else:
        gate = run_ks_gate(cells_full)

    if verbose:
        print()
        print("=== Test 1 — KS distribution gate ===")
        print(f"  Horizon:           5m forward return")
        print(f"  Sample-count min:  {SAMPLE_COUNT_MIN}")
        print(f"  P-value gate:      < {KS_PVALUE_GATE}")
        print(f"  Pairs required:    {KS_PAIRS_REQUIRED}")
        print()
        print(f"  Populated cells:   {gate['populated_cells']}")
        print(f"  Pairs tested:      {gate['pairs_tested']}")
        print(f"  Pairs below p:     {gate['pairs_below_p']}")
        print(f"  Result:            {'PASS — proceed to v0.4 training' if gate['passes_gate'] else 'GATE NOT YET MET'}")
        print()
        if gate["top_pairs"]:
            print("  Most distinguishable pairs (top 10):")
            for k1, k2, D, p in gate["top_pairs"][:10]:
                a = "/".join(str(x) for x in k1)
                b = "/".join(str(x) for x in k2)
                print(f"    D={D:.3f}  p={p:.2e}   {a}  vs  {b}")

    return gate


if __name__ == "__main__":
    report()
