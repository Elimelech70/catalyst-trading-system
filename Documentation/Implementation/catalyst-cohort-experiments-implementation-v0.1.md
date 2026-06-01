# Catalyst Neural — Cohort Experiments Implementation

| Field | Value |
|---|---|
| Document | catalyst-cohort-experiments-implementation |
| Version | 0.1 (DRAFT) |
| Created | 2026-06-01 |
| Last updated | 2026-06-01 |
| Updated by | Craig + Claude |
| Status | Implementation guide — not yet executed |
| Implements | `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 |
| Related | `catalyst-context-conditioned-implementation-v0.1.md`, `catalyst-neural-architecture-v0.3.md` |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-06-01 | Craig + Claude | Initial draft — implementation of 5-strategy × 3-instance cohort experiment per architecture v0.2 |

---

## How to use this document

The architecture document (`catalyst-cohort-experiments-architecture-v0.1.md` v0.2) is the source of truth for *what* and *why*. This document is the source of truth for *how* and *in what order*. Phases are numbered, sequential where dependencies require it, and parallel where they do not.

Each phase declares: **Owner**, **Pre-flight**, **Steps**, **Verify**, **Stop conditions**, **Rollback**. Do not skip the verify step. The rollback path exists because something will go wrong; assume the rollback is the path you will need.

> ⚠️ **Status alert (2026-06-01):** This experiment requires a broader US candle + news universe than the laptop currently has (59 symbols, 1,160 classified news rows). **Phase 3 of the implementation is gated on Phase 0 (universe expansion + data accumulation), which is a 4-week calendar dependency, not a code task.** Do not attempt to run the 15-cohort experiment until Phase 0 completes.

> ⚠️ **Deployed-schema reality (2026-06-01):** The candles schema is a single `candles` table with a `timeframe` column. The `securities` table already has `sector` (populated by v0.4 Phase 3) and `market_cap_tier` (populated by v0.4 Phase 3). The `news` table has 1,160 rows as of 2026-06-01 03:00 UTC. There are no `realized_vol_*` columns yet — Phase 1 below adds them.

---

## Overall pre-flight

Before starting any phase, confirm:

- [ ] Git working tree is clean (or uncommitted v0.4 work is intentionally being preserved — see 2026-05-28 sync of runtime tree to git tree)
- [ ] `catalyst-neural.service` is running and the loop-fix patch is live (`systemctl --user status catalyst-neural` shows recent activity, no sudo-suspend hot-spin)
- [ ] NewsAPI and Finnhub API keys are populated in `/home/craig/catalyst/catalyst-neural/.env`
- [ ] NVIDIA driver is loaded (`nvidia-smi` returns a clean device listing)
- [ ] Disk has ≥ 5 GB free for cohort-experiment artifacts (`models/cohort_*` will grow to ~3 GB)
- [ ] No other GPU consumer is running (other PyTorch processes, browser ML extensions)

---

## Phase 0 — Universe expansion (calendar dependency)

**Owner:** `craig_laptop`

This is the *only* phase that is not a code task. It is the data-collection precondition for everything below. Skipping it means running the experiment on a 59-symbol universe that cannot meaningfully populate sector-pure or HRP-cluster cohorts.

### Pre-flight

- Phase-1-onwards code is built (Phases 1, 2, 3, 4 below can be implemented in parallel during this 4-week window).

### Steps

**0.1** Edit `collectors/news_collector.py:198` to lift the per-cycle symbol cap from 10 to the full active US universe, batched across cycles so each individual cycle stays under Finnhub free-tier rate limits.

```python
# Before: for sym in us_symbols[:10]:
# After: rotate through full US active universe in batches
batch_size = 10
batch_start = (cycle_count * batch_size) % len(us_symbols)
batch = us_symbols[batch_start:batch_start + batch_size]
for sym in batch:
    total += collect_finnhub_news(symbol=sym, market="US")
    time.sleep(1.5)
```

**0.2** Edit `collectors/candle_collector.py` to fetch candles for a wider US active list. Currently the collector picks up whichever securities are in `get_active_securities()`; verify this list is the intended ~300 US training universe and not the 59-symbol historical default. If not, add securities via the picker:

```bash
cd /home/craig/catalyst/catalyst-neural
venv/bin/python run.py pick --universe   # adds the full training universe
```

**0.3** Let the watch service run uninterrupted for **4 weeks of trading days** (≈ 28 calendar days, ≈ 20 trading days for US). Monitor weekly:

```bash
# Weekly check
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
print('US securities with ≥1000 5m candles:',
      conn.execute(\"SELECT COUNT(DISTINCT symbol) AS n FROM candles WHERE market='US' AND timeframe='5m' GROUP BY symbol HAVING COUNT(*) >= 1000\").fetchone())
print('Classified news rows:',
      conn.execute('SELECT COUNT(*) AS n FROM news WHERE news_category_primary IS NOT NULL').fetchone()['n'])
print('US symbols with ≥30 news rows:',
      conn.execute(\"SELECT COUNT(*) AS n FROM (SELECT symbol FROM news WHERE symbols IS NOT NULL GROUP BY symbols HAVING COUNT(*) >= 30)\").fetchone()['n'])
conn.close()
"
```

### Verify

The experiment can begin when ALL of these are true:

- [ ] ≥ 300 US symbols with ≥ 1000 5m candles each
- [ ] ≥ 50 US symbols with ≥ 30 classified news rows each
- [ ] ≥ 5,000 total classified news rows
- [ ] At least 60 trading days of `realized_vol_30d` snapshots (so the metric is stable)

### Stop conditions

- Coverage stalls (no new symbols crossing the 1000-candle threshold for 3 consecutive weeks) → investigate yfinance rate limits or symbol-list bug; do not advance with degenerate data.
- NewsAPI free-tier 100 req/day exceeded with no rows landing → check the per-day budget logic, throttle.

### Rollback

Phase 0 has no rollback — it accumulates data. The accumulated data is useful regardless of what happens with the cohort experiment.

---

## Phase 1 — Schema migration

**Owner:** `claude_assist`

### Pre-flight

- A backup of `data/catalyst_neural.db` exists (the v0.4 Phase 1 migration backup pattern is `data/catalyst_neural.db.pre-v04-backup`; mirror that pattern for `pre-cohort-backup`).

### Steps

**1.1** Create `storage/migrations/002_cohort_experiments.sql`:

```sql
-- 002_cohort_experiments.sql
-- Adds realized-volatility tracking to securities and a cohort registry.
-- Idempotent: safe to re-run.

ALTER TABLE securities ADD COLUMN realized_vol_30d REAL;
ALTER TABLE securities ADD COLUMN realized_vol_snapshot_date DATE;

CREATE INDEX IF NOT EXISTS idx_securities_vol ON securities(realized_vol_30d DESC);

CREATE TABLE IF NOT EXISTS realized_vol_history (
  symbol             TEXT NOT NULL,
  market             TEXT NOT NULL,
  snapshot_date      DATE NOT NULL,
  realized_vol_30d   REAL NOT NULL,
  n_bars_used        INTEGER NOT NULL,
  PRIMARY KEY (symbol, market, snapshot_date)
);

CREATE TABLE IF NOT EXISTS cohort_experiments (
  cohort_id           TEXT PRIMARY KEY,
  strategy_id         TEXT NOT NULL,           -- 'A'..'E'
  instance_id         INTEGER NOT NULL,        -- 1, 2, 3
  draw_date           DATE NOT NULL,
  vol_snapshot_date   DATE NOT NULL,
  sector_filter       TEXT,
  symbols_json        TEXT NOT NULL,
  n_symbols           INTEGER NOT NULL,
  median_val_loss     REAL,
  median_dir_acc      REAL,
  deflated_sharpe     REAL,
  pbo_contribution    REAL,
  effective_sample_n  INTEGER,
  cohort_metrics_json TEXT,
  notes               TEXT,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cohort_strategy ON cohort_experiments(strategy_id, instance_id);
```

**1.2** Apply via:

```bash
cd /home/craig/catalyst/catalyst-neural
cp data/catalyst_neural.db data/catalyst_neural.db.pre-cohort-backup
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
with open('storage/migrations/002_cohort_experiments.sql') as f:
    conn.executescript(f.read())
conn.commit()
print('Migration 002 applied.')
"
```

### Verify

```bash
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
cols = [r['name'] for r in conn.execute('PRAGMA table_info(securities)')]
assert 'realized_vol_30d' in cols, 'realized_vol_30d missing'
assert 'realized_vol_snapshot_date' in cols
tables = [t['name'] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]
assert 'realized_vol_history' in tables
assert 'cohort_experiments' in tables
print('Schema OK.')
"
```

### Stop conditions

- Migration fails partway through → restore from `pre-cohort-backup` and inspect the SQL diff.

### Rollback

```bash
cp data/catalyst_neural.db.pre-cohort-backup data/catalyst_neural.db
```

---

## Phase 2 — Realized-volatility ranking job

**Owner:** `claude_assist`

### Pre-flight

- Phase 1 verify passed

### Steps

**2.1** Create `storage/realized_vol.py`:

```python
"""
Compute 30-day realized volatility from 5m candles.

Definition (matches architecture v0.2 Section 5.1):
    σ(symbol, t) = stdev{ ln(close_t / close_{t-1}) :
                          5m bars in [t - 30 trading days, t] }

Stored on a daily snapshot basis. Annualized for human readability is
σ × √(78 × 252) (78 = 5m bars in a 6.5h trading day, 252 = trading days/year).
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
import math

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from storage.database import get_connection

WINDOW_TRADING_DAYS = 30
BARS_PER_DAY = 78               # 5m bars in a 6.5h US session
MIN_BARS_REQUIRED = 500          # at least ~6 trading days


def compute_realized_vol_for_symbol(conn, symbol, market, as_of_date=None):
    """Return realized_vol_30d (raw 5m stdev) for one (symbol, market)."""
    if as_of_date is None:
        as_of_date = datetime.utcnow().strftime("%Y-%m-%d")
    cutoff_str = (datetime.fromisoformat(as_of_date) -
                  timedelta(days=int(WINDOW_TRADING_DAYS * 1.5))).isoformat()

    rows = conn.execute(
        "SELECT close FROM candles "
        "WHERE symbol=? AND market=? AND timeframe='5m' "
        "AND timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp ASC",
        (symbol, market, cutoff_str, as_of_date)
    ).fetchall()

    if len(rows) < MIN_BARS_REQUIRED:
        return None, len(rows)

    closes = np.array([r["close"] for r in rows], dtype=np.float64)
    returns = np.diff(np.log(closes))
    if len(returns) < MIN_BARS_REQUIRED - 1:
        return None, len(returns)
    sigma = float(np.std(returns, ddof=1))
    return sigma, len(returns)


def run_vol_snapshot(as_of_date=None):
    """Compute and persist realized_vol_30d for all active securities."""
    if as_of_date is None:
        as_of_date = datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_connection()
    secs = conn.execute(
        "SELECT symbol, market FROM securities WHERE removed_at IS NULL"
    ).fetchall()
    n_ok = n_skip = 0
    for s in secs:
        sigma, n_bars = compute_realized_vol_for_symbol(
            conn, s["symbol"], s["market"], as_of_date
        )
        if sigma is None:
            n_skip += 1
            continue
        conn.execute(
            "UPDATE securities SET realized_vol_30d=?, realized_vol_snapshot_date=? "
            "WHERE symbol=? AND market=?",
            (sigma, as_of_date, s["symbol"], s["market"])
        )
        conn.execute(
            "INSERT OR REPLACE INTO realized_vol_history "
            "(symbol, market, snapshot_date, realized_vol_30d, n_bars_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (s["symbol"], s["market"], as_of_date, sigma, n_bars)
        )
        n_ok += 1
    conn.commit()
    conn.close()
    print(f"Vol snapshot {as_of_date}: {n_ok} updated, {n_skip} skipped (insufficient bars)")
    return n_ok, n_skip


if __name__ == "__main__":
    run_vol_snapshot()
```

**2.2** Add a nightly cron entry on the laptop (user crontab; runs at 22:00 local):

```cron
# Realized vol snapshot (catalyst-neural cohort experiments)
0 22 * * * cd /home/craig/catalyst/catalyst-neural && venv/bin/python storage/realized_vol.py >> logs/vol_snapshot.log 2>&1
```

**2.3** Run it once manually now to backfill the current day:

```bash
cd /home/craig/catalyst/catalyst-neural
venv/bin/python storage/realized_vol.py
```

### Verify

```bash
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
n = conn.execute('SELECT COUNT(*) AS n FROM securities WHERE realized_vol_30d IS NOT NULL').fetchone()['n']
print(f'Securities with vol metric: {n}')
top = conn.execute(\"SELECT symbol, market, realized_vol_30d FROM securities WHERE realized_vol_30d IS NOT NULL ORDER BY realized_vol_30d DESC LIMIT 5\").fetchall()
print('Top 5 by vol:')
for r in top: print(f'  {r[\"symbol\"]:>10} {r[\"market\"]} {r[\"realized_vol_30d\"]:.6f}')
"
```

### Stop conditions

- `n_ok` < 30 in the first run → candle data is too sparse; revisit Phase 0 coverage before continuing.
- Top-vol symbols look like data-quality outliers (e.g., a delisted symbol with stale prices) → add a sanity filter for `close > 0.01`.

### Rollback

The vol snapshot is idempotent. Re-running with the same `as_of_date` will overwrite. To unwind entirely:

```sql
UPDATE securities SET realized_vol_30d = NULL, realized_vol_snapshot_date = NULL;
DELETE FROM realized_vol_history;
```

---

## Phase 3 — Cohort assignment module

**Owner:** `claude_assist`

### Pre-flight

- Phase 0 verify passed (≥300 US symbols with candles, ≥50 with news)
- Phase 2 verify passed (vol metric populated)

### Steps

**3.1** Create `storage/cohort_assignment.py` with five strategy implementations. Each takes the eligible universe and returns 150 (symbol, market) tuples. Skeleton:

```python
"""
Cohort assignment for the 15-cohort universe experiment.

Per architecture v0.2 Section 5:
  - A: sector-pure (Tech / Financials / Healthcare for instances 1/2/3)
  - B: vol-tiered (top decile / 5th decile / bottom decile)
  - C: stratified mix (3 random seeds)
  - D: HRP correlation clusters (1st / 2nd / 3rd largest)
  - E: mover / null (top-150 vol / rank 150–300 / uniform random)
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
ELIGIBLE_MIN_VOL_DAYS = 60


def _eligible_universe(conn, market="US"):
    """Symbols meeting all four hard constraints from arch v0.2 Section 5.4."""
    rows = conn.execute("""
        SELECT s.symbol, s.market, s.sector, s.market_cap_tier, s.realized_vol_30d,
               (SELECT COUNT(*) FROM candles c
                  WHERE c.symbol=s.symbol AND c.market=s.market AND c.timeframe='5m') AS n_candles,
               (SELECT COUNT(*) FROM forward_returns f
                  WHERE f.symbol=s.symbol AND f.market=s.market
                    AND f.timeframe='5m' AND f.return_5m IS NOT NULL) AS n_returns,
               (SELECT COUNT(*) FROM realized_vol_history h
                  WHERE h.symbol=s.symbol AND h.market=s.market) AS n_vol_days
        FROM securities s
        WHERE s.removed_at IS NULL
          AND s.market = ?
          AND s.realized_vol_30d IS NOT NULL
    """, (market,)).fetchall()
    return [r for r in rows if r["n_candles"] >= ELIGIBLE_MIN_CANDLES
            and r["n_returns"] >= ELIGIBLE_MIN_RETURNS
            and r["n_vol_days"] >= ELIGIBLE_MIN_VOL_DAYS]


# ── Strategy A: sector-pure ──────────────────────────────────────────────

SECTOR_INSTANCES = {1: "TECH", 2: "FINANCIAL", 3: "HEALTH"}

def strategy_A(conn, instance_id, market="US"):
    sector = SECTOR_INSTANCES[instance_id]
    pool = [r for r in _eligible_universe(conn, market) if r["sector"] == sector]
    pool.sort(key=lambda r: r["realized_vol_30d"], reverse=True)
    return [(r["symbol"], r["market"]) for r in pool[:COHORT_SIZE]]


# ── Strategy B: volatility-tiered ────────────────────────────────────────

VOL_DECILE_INSTANCES = {1: 9, 2: 4, 3: 0}   # 9 = top decile, 0 = bottom

def strategy_B(conn, instance_id, market="US", seed=42):
    decile_target = VOL_DECILE_INSTANCES[instance_id]
    pool = _eligible_universe(conn, market)
    vols = np.array([r["realized_vol_30d"] for r in pool])
    deciles = np.searchsorted(np.quantile(vols, np.arange(1, 10) / 10), vols)
    pool_decile = [pool[i] for i in range(len(pool)) if deciles[i] == decile_target]
    rng = random.Random(seed + instance_id)
    rng.shuffle(pool_decile)
    return [(r["symbol"], r["market"]) for r in pool_decile[:COHORT_SIZE]]


# ── Strategy C: stratified mix ───────────────────────────────────────────

def strategy_C(conn, instance_id, market="US", seed=42):
    pool = _eligible_universe(conn, market)
    rng = random.Random(seed + instance_id)
    # Group by sector
    by_sector = {}
    for r in pool: by_sector.setdefault(r["sector"], []).append(r)
    chosen = []
    # Ensure ≥10 per sector when possible
    for sector, group in by_sector.items():
        rng.shuffle(group)
        chosen.extend(group[:min(10, len(group))])
    # Fill the rest randomly from remaining, respecting cap constraints
    remaining = [r for r in pool if (r["symbol"], r["market"]) not in
                 {(c["symbol"], c["market"]) for c in chosen}]
    rng.shuffle(remaining)
    chosen.extend(remaining[:COHORT_SIZE - len(chosen)])
    return [(r["symbol"], r["market"]) for r in chosen[:COHORT_SIZE]]


# ── Strategy D: HRP correlation clusters ─────────────────────────────────

def strategy_D(conn, instance_id, market="US"):
    """Cluster eligible symbols by 5m return correlation. Take 1st/2nd/3rd largest."""
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    pool = _eligible_universe(conn, market)
    syms = [(r["symbol"], r["market"]) for r in pool]
    # Build return matrix: symbols × time
    return_series = {}
    for sym, mkt in syms:
        rows = conn.execute(
            "SELECT close FROM candles WHERE symbol=? AND market=? AND timeframe='5m' "
            "ORDER BY timestamp DESC LIMIT 2000", (sym, mkt)).fetchall()
        if len(rows) < 1000:
            continue
        closes = np.array([r["close"] for r in rows][::-1], dtype=np.float64)
        return_series[(sym, mkt)] = np.diff(np.log(closes))[-1500:]  # last 1500 returns
    keys = list(return_series.keys())
    if len(keys) < COHORT_SIZE * 2:
        raise RuntimeError(f"HRP needs at least {COHORT_SIZE*2} symbols; got {len(keys)}")
    # Align to common length
    min_len = min(len(v) for v in return_series.values())
    R = np.vstack([return_series[k][-min_len:] for k in keys])
    corr = np.corrcoef(R)
    d = np.sqrt(0.5 * (1 - corr))
    np.fill_diagonal(d, 0)
    Z = linkage(squareform(d), method="single")
    # Cut at the cluster count that yields a "1st-largest" of ≥ COHORT_SIZE
    for n_clusters in range(3, 50):
        labels = fcluster(Z, n_clusters, criterion="maxclust")
        sizes = sorted(np.bincount(labels)[1:], reverse=True)
        if instance_id <= len(sizes) and sizes[instance_id - 1] >= COHORT_SIZE:
            target_cluster_size = sizes[instance_id - 1]
            target_cluster_label = np.argsort(np.bincount(labels)[1:])[-instance_id] + 1
            chosen = [keys[i] for i in range(len(keys)) if labels[i] == target_cluster_label]
            random.Random(42 + instance_id).shuffle(chosen)
            return chosen[:COHORT_SIZE]
    raise RuntimeError(f"HRP could not produce instance {instance_id} of size {COHORT_SIZE}")


# ── Strategy E: mover / null ─────────────────────────────────────────────

def strategy_E(conn, instance_id, market="US", seed=42):
    pool = _eligible_universe(conn, market)
    pool.sort(key=lambda r: r["realized_vol_30d"], reverse=True)
    if instance_id == 1:
        return [(r["symbol"], r["market"]) for r in pool[:COHORT_SIZE]]
    elif instance_id == 2:
        return [(r["symbol"], r["market"]) for r in pool[COHORT_SIZE:COHORT_SIZE * 2]]
    elif instance_id == 3:
        rng = random.Random(seed)
        sampled = rng.sample(pool, COHORT_SIZE)
        return [(r["symbol"], r["market"]) for r in sampled]


# ── Driver ───────────────────────────────────────────────────────────────

STRATEGIES = {"A": strategy_A, "B": strategy_B, "C": strategy_C,
              "D": strategy_D, "E": strategy_E}

def assign_all_cohorts(conn, draw_date, vol_snapshot_date):
    """Generate all 15 cohorts and persist to cohort_experiments table."""
    cohorts = []
    for strategy_id, fn in STRATEGIES.items():
        for instance_id in (1, 2, 3):
            cohort_id = f"{strategy_id}{instance_id}_{draw_date}_v1"
            symbols = fn(conn, instance_id)
            sector_filter = (SECTOR_INSTANCES[instance_id]
                             if strategy_id == "A" else None)
            conn.execute("""
                INSERT OR REPLACE INTO cohort_experiments
                (cohort_id, strategy_id, instance_id, draw_date, vol_snapshot_date,
                 sector_filter, symbols_json, n_symbols)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cohort_id, strategy_id, instance_id, draw_date, vol_snapshot_date,
                  sector_filter, json.dumps(symbols), len(symbols)))
            cohorts.append((cohort_id, len(symbols)))
            print(f"  {cohort_id}: {len(symbols)} symbols")
    conn.commit()
    return cohorts


if __name__ == "__main__":
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_connection()
    print(f"Assigning 15 cohorts for draw_date={today}:")
    assign_all_cohorts(conn, today, today)
    conn.close()
```

**3.2** Run it:

```bash
venv/bin/python storage/cohort_assignment.py
```

### Verify

```bash
venv/bin/python -c "
import sys, json; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
rows = conn.execute('SELECT cohort_id, strategy_id, instance_id, n_symbols FROM cohort_experiments ORDER BY cohort_id').fetchall()
assert len(rows) == 15, f'Expected 15 cohorts, got {len(rows)}'
for r in rows:
    assert r['n_symbols'] == 150, f\"{r['cohort_id']} has only {r['n_symbols']} symbols\"
    print(f'  {r[\"cohort_id\"]}: {r[\"n_symbols\"]} OK')
# Check overlap between cohorts (sanity)
overlap = conn.execute(\"\"\"
  SELECT a.cohort_id, b.cohort_id, COUNT(*) AS overlap
  FROM (SELECT cohort_id, json_each.value AS sym FROM cohort_experiments, json_each(symbols_json)) a,
       (SELECT cohort_id, json_each.value AS sym FROM cohort_experiments, json_each(symbols_json)) b
  WHERE a.cohort_id < b.cohort_id AND a.sym = b.sym
  GROUP BY a.cohort_id, b.cohort_id
  HAVING overlap > 100 ORDER BY overlap DESC LIMIT 5
\"\"\").fetchall()
print('Top overlaps (informational):')
for r in overlap: print(' ', r)
"
```

### Stop conditions

- Any strategy fails to fill 150 symbols → eligible universe is too small; revisit Phase 0.
- HRP raises `cluster too small` → correlation matrix doesn't decompose into 3 large clusters; reduce instance count for D or expand universe.

### Rollback

```sql
DELETE FROM cohort_experiments WHERE draw_date = '<today>';
```

---

## Phase 4 — CPCV trainer wrapper

**Owner:** `claude_assist`

### Pre-flight

- Phase 3 verify passed
- `CandleTrainer` v0.4 (already shipped, runtime tree + git tree synced 2026-05-28) is functional
- **Install `finance_ml`** — López de Prado's CPCV / PBO / sample-uniqueness implementations, packaged from *Advances in Financial Machine Learning* Ch. 7. Authoritative, battle-tested, peer-reviewed. Do not re-implement these from the book yourself:
  ```bash
  cd /home/craig/catalyst/catalyst-neural
  venv/bin/pip install git+https://github.com/jjakimoto/finance_ml.git
  ```

### Steps

**4.1** Create `training/cpcv_trainer.py`:

```python
"""
Combinatorial Purged Cross-Validation wrapper around CandleTrainer.

Per architecture v0.2 Section 6.2:
  - 5-fold CPCV
  - Purge: training labels whose forward windows overlap test windows are dropped
  - Embargo: 1-day buffer after each test fold

Per López de Prado (2018) Ch. 7. Returns per-fold metrics; the cohort runner
aggregates to median across folds.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.dataset import CandleDataset
from training.models import CandleModelV04
from training.trainer import CandleTrainer

PURGE_BARS = 12      # 1h of 5m bars
EMBARGO_BARS = 78    # 1 trading day of 5m bars
N_FOLDS = 5


def _build_cpcv_splits(n_samples, sample_timestamps, label_horizons, n_folds=N_FOLDS):
    """Return list of (train_idx, test_idx) tuples with purge + embargo.

    Uses finance_ml.model_selection.PurgedKFold from López de Prado (2018) Ch. 7.
    sample_timestamps: pd.Series indexed by sample-idx, values = bar timestamp
    label_horizons:    pd.Series indexed by sample-idx, values = end-of-label timestamp
                       (i.e. timestamp + max(horizon)). Required for the purge step
                       to drop training labels whose forward windows overlap test bars.
    """
    import pandas as pd
    from finance_ml.model_selection import PurgedKFold

    embargo_pct = EMBARGO_BARS / n_samples
    pkf = PurgedKFold(
        n_splits=n_folds,
        t1=label_horizons,                  # end-of-label per sample
        pct_embargo=embargo_pct,
    )
    fake_X = pd.DataFrame(index=sample_timestamps.index)
    return list(pkf.split(fake_X))


def run_cpcv_for_cohort(symbol_list, cohort_id, base_config=None):
    """Train and validate v0.4 model across 5 CPCV folds for one cohort.
    Returns dict with per-fold metrics + median aggregate."""
    from torch.utils.data import DataLoader, Subset
    full_dataset = CandleDataset(
        lookback=60, split="all",
        symbol_filter=symbol_list,   # NEW kwarg; see step 4.2
        include_context=True,
    )
    n = len(full_dataset)
    splits = _build_cpcv_splits(n)
    fold_results = []
    for fold_k, (train_idx, test_idx) in enumerate(splits):
        train_ds = Subset(full_dataset, train_idx)
        val_ds = Subset(full_dataset, test_idx)
        train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, drop_last=True)
        val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
        model = CandleModelV04()
        trainer = CandleTrainer(model, train_loader, val_loader, config=base_config)
        trainer.run_id = f"{cohort_id}_fold{fold_k}"
        trainer.train(epochs=100)
        fold_results.append({
            "fold": fold_k,
            "best_val_loss": trainer.best_val_loss,
            "final_dir_acc": trainer.history["val_dir_acc"][-1],
            "final_val_mae": trainer.history["val_mae"][-1],
            "epochs": len(trainer.history["train_loss"]),
            "train_n": len(train_idx),
            "val_n": len(test_idx),
        })
    median = {
        "median_val_loss": float(np.median([f["best_val_loss"] for f in fold_results])),
        "median_dir_acc":  float(np.median([f["final_dir_acc"] for f in fold_results])),
        "median_val_mae":  float(np.median([f["final_val_mae"] for f in fold_results])),
        "effective_sample_n": int(np.median([f["train_n"] for f in fold_results])),
    }
    return {"folds": fold_results, **median}
```

**4.2** Extend `training/dataset.py` `CandleDataset.__init__` to accept a `symbol_filter` kwarg (list of `(symbol, market)` tuples). Filter rows during dataset construction; if `symbol_filter is None`, behaviour is unchanged.

### Verify

```bash
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
import pandas as pd
from training.cpcv_trainer import _build_cpcv_splits

n = 10000
ts = pd.Series(pd.date_range('2026-01-01', periods=n, freq='5min'))
horizons = ts + pd.Timedelta('1h')
splits = _build_cpcv_splits(n, ts, horizons)
for k, (tr, te) in enumerate(splits):
    overlap = set(tr) & set(te)
    print(f'  fold {k}: train={len(tr)} test={len(te)} overlap={len(overlap)}')
    assert len(overlap) == 0, 'purge failed'
print('CPCV splits OK')
"
```

### Stop conditions

- Per-fold training time > 15 min → reduce dataset size or batch size; if persistent, revisit cohort size.
- Validation loss diverges (val_loss > 5.0) on any fold → architecture bug; do not advance.

### Rollback

Delete the file. No DB or model state has changed yet.

---

## Phase 5 — Cohort experiment runner

**Owner:** `claude_assist` + GPU time

### Pre-flight

- Phases 1–4 verify passed
- Phase 0 data accumulation is complete
- DB snapshot frozen (see step 5.1)

### Steps

**5.1** Freeze the database snapshot so all 15 cohorts train against identical data:

```bash
cd /home/craig/catalyst/catalyst-neural
mkdir -p snapshots
SNAP=snapshots/cohort_run_$(date +%Y%m%d).db
cp data/catalyst_neural.db "$SNAP"
echo "Snapshot: $SNAP"
```

**5.2** Create `training/run_cohort_experiment.py`:

```python
"""
Sequence all 15 cohorts through CPCV, persist per-cohort artifacts and the
aggregated metrics back to cohort_experiments table.
"""

import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.database import get_connection
from training.cpcv_trainer import run_cpcv_for_cohort


def run_all_cohorts(draw_date):
    conn = get_connection()
    cohorts = conn.execute(
        "SELECT cohort_id, symbols_json FROM cohort_experiments WHERE draw_date=? ORDER BY cohort_id",
        (draw_date,)
    ).fetchall()
    t0 = time.time()
    for i, c in enumerate(cohorts, 1):
        print(f"\n[{i}/{len(cohorts)}] {c['cohort_id']} starting at +{int(time.time()-t0)}s")
        symbols = [tuple(p) for p in json.loads(c["symbols_json"])]
        results = run_cpcv_for_cohort(symbols, c["cohort_id"])
        conn.execute("""
            UPDATE cohort_experiments
            SET median_val_loss=?, median_dir_acc=?, effective_sample_n=?,
                cohort_metrics_json=?
            WHERE cohort_id=?
        """, (results["median_val_loss"], results["median_dir_acc"],
              results["effective_sample_n"], json.dumps(results), c["cohort_id"]))
        conn.commit()
        print(f"  done: val_loss={results['median_val_loss']:.4f} "
              f"dir_acc={results['median_dir_acc']:.2f}%")
    conn.close()
    print(f"\nAll 15 cohorts complete in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    import sys
    draw_date = sys.argv[1] if len(sys.argv) > 1 else None
    if draw_date is None:
        from datetime import datetime
        draw_date = datetime.utcnow().strftime("%Y-%m-%d")
    run_all_cohorts(draw_date)
```

**5.3** Run, in the background, with a log file:

```bash
cd /home/craig/catalyst/catalyst-neural
LOG=logs/cohort_experiment_$(date +%Y%m%d_%H%M%S).log
nohup venv/bin/python -u training/run_cohort_experiment.py > "$LOG" 2>&1 &
echo "PID: $!  Log: $LOG"
```

Expected wall time: ~7.5 hours. Run overnight.

### Verify

```bash
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from storage.database import get_connection
conn = get_connection()
rows = conn.execute(
    \"SELECT cohort_id, median_val_loss, median_dir_acc, effective_sample_n \"
    \"FROM cohort_experiments WHERE median_val_loss IS NOT NULL ORDER BY median_dir_acc DESC\"
).fetchall()
print(f'{len(rows)}/15 cohorts complete')
for r in rows:
    print(f'  {r[\"cohort_id\"]:>20}  val_loss={r[\"median_val_loss\"]:.4f}  dir_acc={r[\"median_dir_acc\"]:.2f}%  N={r[\"effective_sample_n\"]:,}')
"
```

### Stop conditions

- Total wall time exceeds 12 hours → kill the job; investigate. Likely cause: a single cohort hitting the 100-epoch ceiling without early-stopping. Reduce patience or epoch cap.
- ≥ 4 cohorts have `news_density < 5%` (computed from cohort_metrics_json) → cancel; news coverage too thin; return to Phase 0.
- Identical results across cohorts 1–4 (dir_acc within 0.1 pp) → architecture insensitive to universe; kill the experiment and revisit v0.4.

### Rollback

```sql
UPDATE cohort_experiments
   SET median_val_loss = NULL, median_dir_acc = NULL,
       effective_sample_n = NULL, cohort_metrics_json = NULL
   WHERE draw_date = '<today>';
```

Model checkpoints in `models/cohort_*_fold_*.pt` can be left in place or deleted — they don't affect re-runs.

---

## Phase 6 — Pattern analysis module

**Owner:** `claude_assist`

### Pre-flight

- Phase 5 verify passed (all 15 cohorts have results)

### Steps

**6.1** Create `training/cohort_analysis.py`. We use `finance_ml` where it has the functionality (`PurgedKFold` in Phase 4) and roll our own where it doesn't (DSR + PBO are not in `finance_ml.stats` or `finance_ml.experiments` — both are explicitly cited as Bailey et al. 2014 algorithms, the math is fully specified in the papers, and we implement them as ~100 lines straight from the source):

```python
"""
Pattern analysis across all 15 cohorts.

Produces:
  1. Strategy-level ANOVA (F-test or Kruskal-Wallis)
  2. Cohort-metric correlations (Spearman ρ)
  3. Sweet-spot scatter (dir_acc vs median_realized_vol)
  4. Common-failure-mode aggregation
  5. Common-success-mode aggregation
  6. Symbol-level transfer analysis
  7. Deflated Sharpe per cohort (via finance_ml)
  8. Probability of Backtest Overfitting (PBO) (via finance_ml)

Heavy statistical machinery is delegated to finance_ml so we are not
re-deriving López de Prado's algorithms from the book — they are imported
from the canonical implementation at
https://github.com/jjakimoto/finance_ml
"""

import sys, json
from pathlib import Path
import numpy as np
from scipy import stats

# NOTE on dependencies: finance_ml ships PurgedKFold (used in Phase 4 CPCV
# trainer) but does NOT ship deflated_sharpe_ratio or pbo — those modules
# either don't exist (DSR) or are misnamed (the `experiments` module is for
# simulating synthetic correlation matrices, not the Bailey/Borwein PBO test).
# We implement DSR and PBO directly from Bailey & López de Prado (2014, JPM)
# and Bailey/Borwein/LdP/Zhu (2014, SSRN 2326253). Math is ~100 lines total
# and is fully specified in the source papers — see _deflated_sharpe and
# _pbo below.

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.database import get_connection


def load_results(draw_date):
    conn = get_connection()
    rows = conn.execute(
        "SELECT cohort_id, strategy_id, instance_id, median_val_loss, "
        "median_dir_acc, effective_sample_n, cohort_metrics_json, symbols_json "
        "FROM cohort_experiments WHERE draw_date=? AND median_val_loss IS NOT NULL "
        "ORDER BY cohort_id",
        (draw_date,)
    ).fetchall()
    conn.close()
    return rows


def strategy_anova(rows):
    """One-way K-W on dir_acc across 5 strategies."""
    by_strategy = {}
    for r in rows:
        by_strategy.setdefault(r["strategy_id"], []).append(r["median_dir_acc"])
    groups = [by_strategy[s] for s in sorted(by_strategy.keys())]
    h, p = stats.kruskal(*groups)
    # Within/between variance
    grand_mean = np.mean([x for g in groups for x in g])
    between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
    within = sum(sum((x - np.mean(g)) ** 2 for x in g) for g in groups)
    eta_sq = between / (between + within)
    return {"H": h, "p_value": p, "eta_squared": eta_sq, "by_strategy": by_strategy}


def cohort_metric_correlations(rows):
    """Spearman ρ between cohort descriptors and dir_acc."""
    descriptors = {"median_realized_vol": [], "sector_entropy": [],
                   "news_density": [], "mean_correlation": [],
                   "effective_sample_n": []}
    dir_accs = []
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        # cohort_metrics_json is expected to include these — emit them in cpcv_trainer
        for k in descriptors:
            descriptors[k].append(m.get(k, np.nan))
        dir_accs.append(r["median_dir_acc"])
    out = {}
    for k, vals in descriptors.items():
        rho, p = stats.spearmanr(vals, dir_accs, nan_policy="omit")
        out[k] = {"rho": rho, "p_value": p}
    return out


def _deflated_sharpe(returns_series, n_trials):
    """Bailey & López de Prado (2014, JPM) deflated Sharpe ratio.
    returns_series: array of per-fold lifts (e.g., dir_acc - chance_baseline)
    n_trials: number of independent cohorts being compared (N=15 here)
    Returns DSR (a probability — interpretable as p(true SR > 0) after deflation)."""
    from scipy.stats import norm
    r = np.asarray(returns_series, dtype=np.float64)
    n = len(r)
    if n < 2:
        return float("nan")
    sr = r.mean() / (r.std(ddof=1) + 1e-12)
    # Skew + kurt of returns matter for the SR distribution
    skew = ((r - r.mean()) ** 3).mean() / (r.std() ** 3 + 1e-12)
    kurt = ((r - r.mean()) ** 4).mean() / (r.std() ** 4 + 1e-12)
    # Expected max SR under the null over N trials (LdP 2014 eq. 10)
    em = (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_trials) + \
         np.euler_gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    # Variance of SR estimate (LdP 2014 eq. 9)
    sigma_sr = np.sqrt((1 - skew * sr + ((kurt - 1) / 4) * sr ** 2) / (n - 1))
    z = (sr - em) / (sigma_sr + 1e-12)
    return float(norm.cdf(z))


def deflated_sharpe(rows):
    """Deflated Sharpe per cohort. Treats each fold's dir_acc lift over the
    33.3% chance baseline as the 'return' series."""
    out = {}
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        lifts = [f["final_dir_acc"] - 33.3 for f in m["folds"]]
        dsr = _deflated_sharpe(lifts, n_trials=len(rows))
        out[r["cohort_id"]] = {"dsr": float(dsr)}
    return out


def _pbo(M, S=16):
    """Probability of Backtest Overfitting (Bailey/Borwein/LdP/Zhu 2014).
    M: ndarray cohorts × folds of performance metrics.
    S: number of submatrix splits (S=16 -> C(16,8)=12,870 combos, standard).
    Returns scalar in [0,1]; <0.5 -> winner generalises, >0.5 -> overfit."""
    from itertools import combinations
    M = np.asarray(M, dtype=np.float64)
    n_cohorts, n_folds = M.shape
    # If we have fewer folds than S, use n_folds as S
    S = min(S, n_folds)
    if S % 2 == 1:
        S -= 1
    if S < 4:
        return float("nan")
    # Partition folds into S equal-size submatrices, take all S/2-subsets
    # as in-sample, rest as out-of-sample
    sub = np.array_split(np.arange(n_folds), S)
    inversions = 0
    total = 0
    for is_idx in combinations(range(S), S // 2):
        in_folds = np.concatenate([sub[i] for i in is_idx])
        out_folds = np.concatenate([sub[i] for i in range(S) if i not in is_idx])
        in_score = M[:, in_folds].mean(axis=1)
        out_score = M[:, out_folds].mean(axis=1)
        best_in = int(np.argmax(in_score))
        # Where does the best-in-sample cohort rank out-of-sample? (LdP rank logit)
        oo_rank = (out_score < out_score[best_in]).sum() / max(1, n_cohorts - 1)
        if oo_rank < 0.5:
            inversions += 1
        total += 1
    return inversions / total if total > 0 else float("nan")


def pbo(rows):
    """PBO across the 15-cohort × 5-fold matrix."""
    accs_per_cohort = []
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        accs_per_cohort.append([f["final_dir_acc"] for f in m["folds"]])
    M = np.array(accs_per_cohort)
    return float(_pbo(M, S=4))   # S=4 because we only have 5 folds


def common_failure_modes(draw_date, threshold=0.8):
    """For each validation sample, count cohorts that misclassified it.
    Return samples misclassified by ≥ threshold fraction of cohorts."""
    # Implementation requires per-sample predictions persisted from each
    # CPCV fold. The cpcv_trainer needs to dump these to JSONL files.
    # (Stub — full implementation in Phase 6 follow-up.)
    raise NotImplementedError("Requires per-sample prediction logging; see TODO")


if __name__ == "__main__":
    import sys
    draw_date = sys.argv[1]
    rows = load_results(draw_date)
    print(f"Loaded {len(rows)} cohorts for {draw_date}\n")
    print("=== Strategy-level ANOVA ===")
    a = strategy_anova(rows)
    print(f"  Kruskal-Wallis H={a['H']:.3f}  p={a['p_value']:.4f}  η²={a['eta_squared']:.3f}")
    print("\n=== Cohort-metric correlations ===")
    for k, v in cohort_metric_correlations(rows).items():
        print(f"  {k:>22} ρ={v['rho']:+.3f}  p={v['p_value']:.4f}")
    print("\n=== Deflated Sharpe per cohort ===")
    for cid, v in deflated_sharpe(rows).items():
        print(f"  {cid:>20}  SR={v['sr']:+.2f}  DSR={v['dsr']:+.2f}")
    print(f"\n=== PBO: {pbo(rows):.3f} ===")
```

**6.2** Extend `training/cpcv_trainer.py` to emit `cohort_metrics_json` containing:

- `median_realized_vol`
- `sector_entropy`
- `cap_entropy`
- `news_density`
- `mean_correlation`
- `effective_sample_n`
- `folds` (the per-fold list)

These are needed by the analysis module. Compute them at the start of `run_cpcv_for_cohort()` before training begins.

### Verify

```bash
venv/bin/python training/cohort_analysis.py 2026-MM-DD
# Expect: ANOVA H + p, 5 Spearman correlations, 15 DSR rows, 1 PBO
```

### Stop conditions

- ANOVA p < 0.001 but with η² < 0.05 → numerically significant but effect-size trivial. Treat as null result.
- PBO > 0.5 → results are likely overfit; do not lock in any strategy.

### Rollback

Analysis is read-only; no rollback needed. Delete the file if abandoning.

---

## Phase 7 — Comparison report HTML

**Owner:** `claude_assist`

### Pre-flight

- Phase 6 verify passed

### Steps

**7.1** Create `training/cohort_report.py` that emits a single self-contained HTML with:

- Header: experiment metadata (draw_date, snapshot, total wall time, count)
- Section A: 15-cohort leaderboard (cohort_id, strategy, dir_acc, val_loss, DSR sorted desc)
- Section B: Strategy-level boxplot (matplotlib → base64-embedded SVG)
- Section C: ANOVA + post-hoc table (omnibus H/p/η², pairwise Tukey or Dunn)
- Section D: Spearman correlation table with 5 descriptors
- Section E: Sweet-spot scatter (`median_realized_vol` × `dir_acc`)
- Section F: Per-cohort sector + cap composition stacked-bar
- Section G: Common-failure-mode table (top 20 sample types misclassified by ≥80% of cohorts)
- Section H: PBO value and interpretation
- Section I: Verdict — Outcome 1/2/3/4 per architecture Section 11

**7.2** Save report to `Documentation/Reports/cohort_experiment_<date>.html`.

### Verify

```bash
xdg-open Documentation/Reports/cohort_experiment_<date>.html
# Inspect each section. Check that the verdict block matches the
# ANOVA + DSR + PBO numbers shown above it.
```

### Stop conditions

- Verdict block displays "Outcome 4" → architecture is the bottleneck; do not advance to Phase 8.

### Rollback

Delete the HTML file. No state change.

---

## Phase 8 — Gate evaluation

**Owner:** Craig + Claude

### Pre-flight

- Phase 7 HTML report exists and has been reviewed

### Steps

**8.1** Read the verdict block in the report. Match against architecture Section 11:

- **Outcome 1 (single strategy wins clearly):** Write a one-paragraph decision note in `Documentation/Analysis/cohort_decision_<date>.md`. Specify the winning strategy and the rule for v0.4.1 cohort assignment going forward.
- **Outcome 2 (two strategies tie):** Pick the operationally simpler. Write the decision note with the operational-simplicity justification.
- **Outcome 3 (vol confirmed, no structured winner):** Adopt vol-rank-filtered universes. Write the decision note.
- **Outcome 4 (no strategy beats null):** Decision note explains the null result. Return to v0.4 architecture work — do not deploy v0.4.1.

**8.2** If Outcomes 1, 2, or 3: tag the winning cohort definition in code (`storage/cohort_assignment.py` adds a `PRODUCTION_COHORT_SPEC` constant referencing the winning strategy + instance + version).

### Verify

The decision note exists, has a date, and is referenced from `CLAUDE.md` root (add a row to the document-family table under "Analysis").

### Stop conditions

- Decision note cannot be written because the report is ambiguous → re-run the experiment with a fresh snapshot rather than guess.

### Rollback

Delete the decision note. The verdict can be re-evaluated later.

---

## Phase 9 — v0.4.1 production deployment

**Owner:** `craig_laptop` + `claude_assist`

This phase is **deferred to a separate document**. Once Phase 8 produces a winning cohort spec, deployment follows the existing v0.4 implementation document Phases 7–9 (ONNX export, droplet sync, smoke test). The only change is the cohort filter applied to the training run.

Pointer: `catalyst-context-conditioned-implementation-v0.1.md` Phase 7+ with the cohort filter added.

---

## Reading the patterns — what to look for

The analyses run automatically; interpreting them is judgment. Five lenses to apply when reading the HTML report:

### A. Did strategy matter at all?

- **ANOVA p < 0.05** AND **η² > 0.20**: strategy is a real driver. Pick the winner.
- **ANOVA p < 0.05** AND **η² < 0.10**: numerically significant but explanatorily trivial. Treat as null.
- **ANOVA p > 0.05**: no evidence strategy matters. Outcome 4.

### B. Did volatility matter?

- B1 (top-vol) > B3 (bottom-vol) by ≥ 1 pp **AND** E1 (pure mover) > E3 (random) by ≥ 0.5 pp: vol is real signal.
- B1 ≈ B3 and E1 ≈ E3: vol is not the bottleneck.
- B3 > B1 (bottom-vol *wins*): genuinely surprising; investigate before concluding. Quiet names may have cleaner mean-reversion patterns that the model can exploit.

### C. Did news coverage matter?

- Spearman ρ(`news_density`, `dir_acc`) > 0.5: coverage is the bottleneck, not strategy. Expand collection.
- ρ ≈ 0: model isn't using the news signal effectively — architecture issue, not data issue.
- ρ < 0 (unexpected): news_context may be adding noise rather than signal. Investigate the classifier accuracy.

### D. Did the model find any real patterns?

- Mean fold dir_acc across all 15 cohorts > 42%: real (vs the ~33% chance baseline + the ~40% the v0.3 model achieves).
- Mean fold dir_acc < 41%: the architecture is barely moving above the v0.4 single-run baseline; cohort choice can't fix that.

### E. Are the same samples failing everywhere?

Common-failure-mode table at the bottom of the report. If the top failure modes are:

- A specific news category (e.g., `bankruptcy`, `regulatory_approval`): rare-category signal is weak. Add category-weighted loss in v0.4.2.
- A specific sector (e.g., `BIOTECH`): sector-specific behaviour the model can't capture. Specialist model worth revisiting.
- A specific cap tier (e.g., `MICRO`): small-cap candle patterns are noise-dominated. Filter them out of training.
- Nothing systematic (failures spread across categories/sectors/cap): residual irreducible noise. We've reached a floor.

---

## What this document does not specify

- **Hyperparameter sensitivity.** Every cohort uses default training settings. A v0.4.2 doc may explore tuning per-cohort.
- **Architecture sensitivity.** Every cohort uses `CandleModelV04`. We are not testing model architecture in this experiment.
- **Time-window sensitivity.** Every cohort uses the same training window. A walk-forward across time is a separate experimental design.
- **Cross-market cohorts.** All cohorts are US-only. HKEX is excluded because free news APIs do not cover it.

These are deliberate. The cohort experiment answers *the universe question*, holding everything else fixed. Mixing in other variables makes the result un-interpretable.

---

*Craig + Claude — The Catalyst Family*
*2026-06-01*
