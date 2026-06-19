"""
Combinatorial Purged Cross-Validation wrapper around CandleTrainer.

Architecture v0.2 §6.2: 5-fold purged CV, 1-hour purge, 1-day embargo.

Implementation note: we initially planned to use finance_ml.PurgedKFold but
discovered (a) it does not ship deflated_sharpe_ratio or pbo (we roll our own
in cohort_analysis.py), and (b) PurgedKFold itself has a bug when t1 is
datetime-indexed (uses label `.loc` where positional `.iloc` is needed at
kfold.py:71). Rather than depend on a forked/patched venv copy, we implement
purged k-fold from scratch — the algorithm is ~30 lines from López de Prado
(2018) Ch. 7 and trivially testable.

Cohort descriptors (median_realized_vol, sector_entropy, etc.) are computed
once per cohort before training begins and stored alongside the fold metrics
so the Phase 6 analysis module can correlate them with dir_acc.
"""

import sys
import json
import math
import time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Subset

from training.dataset import CandleDataset
from training.models import CandleModelV04
from training.trainer import CandleTrainer
from storage.database import get_connection

PURGE_BARS = 12       # 1h of 5m bars
EMBARGO_BARS = 78     # 1 trading day of 5m bars
N_FOLDS = 5


# ── CPCV splits ──────────────────────────────────────────────────────────

def _build_cpcv_splits(sample_timestamps, n_folds=N_FOLDS,
                       horizon=pd.Timedelta(hours=1),
                       embargo_bars=EMBARGO_BARS):
    """Purged k-fold cross-validation per López de Prado (2018) Ch. 7.

    sample_timestamps: array-like of bar timestamps, ASCENDING SORTED. One per sample.
    horizon:    forward-label duration. Training samples whose label window
                [t, t + horizon] overlaps any test-set bar are PURGED.
    embargo_bars: positional buffer after the test fold's last index; training
                samples within this buffer are also dropped.

    Returns list of (train_idx, test_idx) numpy arrays of POSITIONAL indices.
    """
    ts = pd.DatetimeIndex(sample_timestamps)
    if not ts.is_monotonic_increasing:
        raise ValueError("sample_timestamps must be sorted ascending")
    n = len(ts)
    indices = np.arange(n)
    label_end = ts + horizon

    # Equal-sized contiguous test folds
    fold_bounds = np.array_split(indices, n_folds)
    out = []
    for fold in fold_bounds:
        test_idx = fold
        test_start_ts = ts[test_idx[0]]
        test_end_ts   = ts[test_idx[-1]]

        # Candidate training: everything not in test
        train_mask = np.ones(n, dtype=bool)
        train_mask[test_idx] = False

        # Purge: drop training samples whose label window overlaps the test window
        # Sample s overlaps test if [ts[s], label_end[s]] ∩ [test_start, test_end] non-empty
        # i.e. ts[s] <= test_end AND label_end[s] >= test_start
        overlap = (ts <= test_end_ts) & (label_end >= test_start_ts)
        train_mask[overlap] = False

        # Embargo: drop training samples in the embargo_bars positions just
        # after the test fold (keep `train_mask[i] = False` for i in (last_test_pos, last_test_pos + embargo_bars])
        emb_end = min(n, test_idx[-1] + 1 + embargo_bars)
        train_mask[test_idx[-1] + 1 : emb_end] = False

        train_idx = indices[train_mask]
        out.append((train_idx, test_idx))
    return out


# ── Cohort descriptors ───────────────────────────────────────────────────

def compute_cohort_descriptors(conn, symbol_list, dataset):
    """Compute six descriptors per arch v0.2 §7.5 (the pattern-analysis inputs).
    Returns dict suitable for JSON serialization."""
    syms = [t[0] for t in symbol_list]
    markets = [t[1] for t in symbol_list]

    # 1. median_realized_vol
    placeholders = ",".join("?" for _ in syms)
    vols = [r["realized_vol_30d"] for r in conn.execute(
        f"SELECT realized_vol_30d FROM securities "
        f"WHERE symbol IN ({placeholders}) AND realized_vol_30d IS NOT NULL",
        syms
    )]
    median_vol = float(np.median(vols)) if vols else None

    # 2. sector_entropy + 3. cap_entropy
    sectors = [r["sector"] for r in conn.execute(
        f"SELECT sector FROM securities WHERE symbol IN ({placeholders})", syms
    ) if r["sector"]]
    caps = [r["market_cap_tier"] for r in conn.execute(
        f"SELECT market_cap_tier FROM securities WHERE symbol IN ({placeholders})", syms
    ) if r["market_cap_tier"]]

    def _entropy(items):
        if not items: return None
        c = Counter(items); total = sum(c.values())
        return -sum((n/total) * math.log(n/total) for n in c.values())

    # 4. news_density: fraction of samples in this dataset with non-zero news_context
    news_nonzero_count = 0
    if hasattr(dataset, "samples"):
        # Sample a subset for speed (full pass is expensive)
        check_n = min(2000, len(dataset))
        idxs = np.linspace(0, len(dataset) - 1, check_n).astype(int)
        for i in idxs:
            sample = dataset[i]
            if sample["news_context"].abs().sum() > 0:
                news_nonzero_count += 1
        news_density = news_nonzero_count / check_n
    else:
        news_density = None

    return {
        "median_realized_vol": median_vol,
        "sector_entropy":      _entropy(sectors),
        "cap_entropy":         _entropy(caps),
        "news_density":        news_density,
        "n_symbols_input":     len(symbol_list),
        "n_symbols_with_vol":  len(vols),
    }


# ── Main CPCV runner ─────────────────────────────────────────────────────

def run_cpcv_for_cohort(symbol_list, cohort_id, base_config=None,
                        data_window_days=180):
    """Train CandleModelV04 across 5 CPCV folds for one cohort.

    data_window_days: how far back to load candles per symbol. Default 180
    (last 6 months) — keeps the in-memory candle dict to ~1.5 GB for 150
    symbols. Previously tried 365 (1 year) and 5y, both OOM-killed the 8 GB
    laptop.

    The cohort experiment is testing universe-shape effects, not data-window
    effects; 6 months of intraday data is plenty (Krauss et al. 2017 used
    240-day rolling windows of DAILY data — we have 78x more bars per day).
    For production v0.4.1 we'd train on a longer window with a smaller
    universe or out-of-core data loading.

    Returns dict with per-fold metrics + median aggregate + descriptors.
    """
    from datetime import datetime, timedelta
    conn = get_connection()
    print(f"\n>>> Cohort {cohort_id}: {len(symbol_list)} symbols")
    t_cohort = time.time()

    min_date = (datetime.utcnow() - timedelta(days=data_window_days)).strftime("%Y-%m-%d")
    print(f"    data window: {min_date} → now ({data_window_days} days)")

    # Build the dataset filtered to this cohort's symbols
    full_dataset = CandleDataset(
        lookback=60, split="all",
        symbol_filter=symbol_list,
        include_context=True,
        min_date=min_date,
    )
    n_samples = len(full_dataset)
    print(f"    dataset built: {n_samples:,} samples")

    if n_samples < N_FOLDS * 100:
        return {
            "cohort_id": cohort_id,
            "error": f"insufficient samples ({n_samples} < {N_FOLDS*100})",
        }

    # Build sample timestamp series for PurgedKFold.
    # CandleDataset.samples is a list of (symbol, market, idx_5m, idx_15m, ts).
    # We need s[4] (the timestamp), NOT s[2] (the candle index — using that
    # gave nonsense Unix-epoch nanosecond "timestamps" which made the fold-5
    # purge drop ALL training samples. Bug fix 2026-06-09.)
    timestamps = pd.to_datetime([s[4] for s in full_dataset.samples])
    order = np.argsort(timestamps.values)
    timestamps_sorted = timestamps[order]

    descriptors = compute_cohort_descriptors(conn, symbol_list, full_dataset)
    conn.close()
    print(f"    descriptors: vol={descriptors['median_realized_vol']:.4f}  "
          f"news_density={descriptors['news_density']:.3f}")

    # _build_cpcv_splits returns positional indices INTO THE SORTED SERIES;
    # map back to dataset indices via `order`
    splits_sorted = _build_cpcv_splits(timestamps_sorted)
    splits = [(order[tr], order[te]) for tr, te in splits_sorted]
    fold_results = []
    for fold_k, (train_idx, test_idx) in enumerate(splits):
        # Skip degenerate folds (e.g. purge eating all training samples on the
        # last fold). Record the failure but don't abort the whole cohort.
        if len(train_idx) < 64 or len(test_idx) < 64:
            print(f"    fold {fold_k+1}/{N_FOLDS}: SKIPPED (train={len(train_idx)}, test={len(test_idx)}) — too small after purge")
            fold_results.append({
                "fold": fold_k, "skipped": True,
                "train_n": int(len(train_idx)), "val_n": int(len(test_idx)),
            })
            continue
        print(f"    fold {fold_k+1}/{N_FOLDS}: train={len(train_idx):,}  test={len(test_idx):,}")
        train_ds = Subset(full_dataset, train_idx.tolist())
        val_ds   = Subset(full_dataset, test_idx.tolist())
        train_loader = DataLoader(train_ds, batch_size=64, shuffle=True,
                                  drop_last=True, num_workers=0)
        val_loader   = DataLoader(val_ds, batch_size=64, shuffle=False,
                                  num_workers=0)

        model = CandleModelV04()
        trainer = CandleTrainer(model, train_loader, val_loader, config=base_config)
        trainer.run_id = f"{cohort_id}_fold{fold_k}"
        trainer.train(epochs=100)

        fold_results.append({
            "fold":            fold_k,
            "best_val_loss":   float(trainer.best_val_loss),
            "final_dir_acc":   float(trainer.history["val_dir_acc"][-1]),
            "final_val_mae":   float(trainer.history["val_mae"][-1]),
            "epochs":          len(trainer.history["train_loss"]),
            "train_n":         int(len(train_idx)),
            "val_n":           int(len(test_idx)),
        })

    elapsed = time.time() - t_cohort
    valid_folds = [f for f in fold_results if not f.get("skipped")]
    if not valid_folds:
        return {"cohort_id": cohort_id, "error": "no valid folds",
                "folds": fold_results}
    median = {
        "median_val_loss":     float(np.median([f["best_val_loss"] for f in valid_folds])),
        "median_dir_acc":      float(np.median([f["final_dir_acc"] for f in valid_folds])),
        "median_val_mae":      float(np.median([f["final_val_mae"] for f in valid_folds])),
        "effective_sample_n":  int(np.median([f["train_n"] for f in valid_folds])),
        "cohort_wall_time_s":  elapsed,
    }
    print(f"    cohort done in {elapsed/60:.1f} min  "
          f"med_val_loss={median['median_val_loss']:.4f}  "
          f"med_dir_acc={median['median_dir_acc']:.2f}%")
    return {
        "cohort_id":  cohort_id,
        "folds":      fold_results,
        **median,
        **descriptors,
    }


if __name__ == "__main__":
    # Smoke-test the CPCV split logic with synthetic data — no training.
    n = 10_000
    ts = pd.date_range("2026-01-01", periods=n, freq="5min")
    splits = _build_cpcv_splits(ts)
    for k, (tr, te) in enumerate(splits):
        overlap = set(tr) & set(te)
        print(f"  fold {k}: train={len(tr):,}  test={len(te):,}  overlap={len(overlap)}")
        assert len(overlap) == 0, "purge failed"
    print("CPCV splits OK")
