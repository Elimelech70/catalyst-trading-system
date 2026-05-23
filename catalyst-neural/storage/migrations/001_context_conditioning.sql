-- Migration: 001_context_conditioning
-- Date: 2026-05-23
-- Purpose: Schema changes for CandleModel v0.4 context-conditioned architecture.
-- Reference: Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md
--
-- IMPORTANT: securities.sector already exists in init_db() and is NULL on all
-- existing rows. We do NOT re-add it here. Phase 3 of the implementation guide
-- populates the existing sector column plus the new cap-tier columns below.

-- ── News table: 15-category classification fields ──
ALTER TABLE news ADD COLUMN news_category_primary TEXT;
ALTER TABLE news ADD COLUMN news_category_secondary TEXT;
ALTER TABLE news ADD COLUMN news_category_tertiary TEXT;
ALTER TABLE news ADD COLUMN category_confidence REAL;
ALTER TABLE news ADD COLUMN classified_by TEXT;
ALTER TABLE news ADD COLUMN classified_at TEXT;

CREATE INDEX IF NOT EXISTS idx_news_category_primary
    ON news(news_category_primary);
CREATE INDEX IF NOT EXISTS idx_news_category_published
    ON news(news_category_primary, published_at);

-- ── Securities table: cap-tier classification + volatility regime ──
-- securities.sector pre-exists; not re-added here.
ALTER TABLE securities ADD COLUMN market_cap_tier TEXT;
ALTER TABLE securities ADD COLUMN market_cap_usd REAL;
ALTER TABLE securities ADD COLUMN volatility_regime TEXT;     -- Phase 2 use, nullable
ALTER TABLE securities ADD COLUMN context_updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_securities_sector
    ON securities(sector);
CREATE INDEX IF NOT EXISTS idx_securities_cap_tier
    ON securities(market_cap_tier);

-- ── New table: context regime summary (analytics, not training) ──
CREATE TABLE IF NOT EXISTS context_regime_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_category TEXT NOT NULL,
    sector TEXT NOT NULL,
    cap_tier TEXT NOT NULL,
    market TEXT NOT NULL,
    sample_count INTEGER,
    mean_return_5m REAL,
    std_return_5m REAL,
    mean_return_15m REAL,
    std_return_15m REAL,
    mean_return_1h REAL,
    std_return_1h REAL,
    direction_bullish_pct REAL,
    direction_bearish_pct REAL,
    direction_neutral_pct REAL,
    last_computed TEXT,
    UNIQUE(news_category, sector, cap_tier, market)
);

CREATE INDEX IF NOT EXISTS idx_regime_lookup
    ON context_regime_summary(news_category, sector, cap_tier, market);
