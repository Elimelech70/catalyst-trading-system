-- 002_cohort_experiments.sql
-- Adds realized-volatility tracking to securities and the cohort registry.
-- Implements catalyst-cohort-experiments-implementation-v0.1.md Phase 1.
-- Idempotent: ALTER TABLE wrapped in IF-NOT-EXISTS via PRAGMA inspection
-- in apply script; the CREATE statements use IF NOT EXISTS.

-- Vol columns on securities
ALTER TABLE securities ADD COLUMN realized_vol_30d REAL;
ALTER TABLE securities ADD COLUMN realized_vol_snapshot_date DATE;

CREATE INDEX IF NOT EXISTS idx_securities_vol
  ON securities(realized_vol_30d DESC);

-- Historical snapshots — so we can backtest cohort definitions on past vol
CREATE TABLE IF NOT EXISTS realized_vol_history (
  symbol             TEXT NOT NULL,
  market             TEXT NOT NULL,
  snapshot_date      DATE NOT NULL,
  realized_vol_30d   REAL NOT NULL,
  n_bars_used        INTEGER NOT NULL,
  PRIMARY KEY (symbol, market, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_vol_history_date
  ON realized_vol_history(snapshot_date DESC);

-- Cohort registry — one row per (strategy, instance, draw_date)
CREATE TABLE IF NOT EXISTS cohort_experiments (
  cohort_id           TEXT PRIMARY KEY,           -- e.g. 'A1_2026-06-02_v1'
  strategy_id         TEXT NOT NULL,              -- 'A'..'E'
  instance_id         INTEGER NOT NULL,           -- 1, 2, 3
  draw_date           DATE NOT NULL,
  vol_snapshot_date   DATE NOT NULL,
  sector_filter       TEXT,                       -- non-NULL for Strategy A
  symbols_json        TEXT NOT NULL,              -- JSON list of [sym, mkt] pairs
  n_symbols           INTEGER NOT NULL,
  -- Populated post-training
  median_val_loss     REAL,
  median_dir_acc      REAL,
  median_val_mae      REAL,
  deflated_sharpe     REAL,
  pbo_contribution    REAL,
  effective_sample_n  INTEGER,
  cohort_metrics_json TEXT,                       -- JSON: per-fold metrics, descriptors
  notes               TEXT,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cohort_strategy
  ON cohort_experiments(strategy_id, instance_id);

CREATE INDEX IF NOT EXISTS idx_cohort_draw
  ON cohort_experiments(draw_date DESC);
