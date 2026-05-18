-- ============================================================================
-- Feedback Loop Foundation — Phase 1
-- Version: 1.0.0
-- Date: 2026-04-08
-- Purpose: Add exit_type tracking, candle snapshots, pattern confidence/outcomes
-- ============================================================================

-- Exit type tracking on positions
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_type VARCHAR(30);
-- Values: AI_PATTERN | STOP_LOSS | TAKE_PROFIT | MANUAL | MARKET_CLOSE | TIME_LIMIT

-- Candle snapshots at entry and exit (20-candle OHLCV windows for training data)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS candles_at_entry JSONB;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS candles_at_exit JSONB;

-- Pattern confidence — synaptic weights (LTP/LTD updated by learning.py)
CREATE TABLE IF NOT EXISTS pattern_confidence (
    pattern_name    VARCHAR(100) PRIMARY KEY,
    confidence      FLOAT DEFAULT 0.5,  -- 0.0 to 1.0
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    stop_loss_exits INTEGER DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial pattern types with neutral confidence
INSERT INTO pattern_confidence (pattern_name, confidence) VALUES
    ('breakout', 0.5),
    ('near_breakout', 0.5),
    ('momentum_continuation', 0.5),
    ('bull_flag', 0.5),
    ('bear_flag', 0.5),
    ('ascending_triangle', 0.5),
    ('descending_triangle', 0.5),
    ('cup_and_handle', 0.5),
    ('abcd_pattern', 0.5),
    ('breakdown', 0.5)
ON CONFLICT (pattern_name) DO NOTHING;

-- Pattern outcomes — links closed trades to the pattern that triggered them
CREATE TABLE IF NOT EXISTS pattern_outcomes (
    id              SERIAL PRIMARY KEY,
    position_id     INTEGER,
    pattern_name    VARCHAR(100),
    entry_confidence FLOAT,
    exit_type       VARCHAR(30),
    pnl             FLOAT,
    pnl_pct         FLOAT,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pattern_outcomes_pattern ON pattern_outcomes(pattern_name);
CREATE INDEX IF NOT EXISTS idx_pattern_outcomes_exit_type ON pattern_outcomes(exit_type);
