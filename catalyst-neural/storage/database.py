"""
Catalyst Neural — Storage Layer

Raw, unbiased data storage. The recorder captures what happened.
No interpretation. No labels. Just truth with timestamps.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "catalyst_neural.db"


def get_connection():
    """Get database connection with WAL mode for concurrent reads."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all tables. Safe to call repeatedly."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Security Registry ──
    # What we're watching. Populated from droplet scanners.
    # v0.4: sector / market_cap_tier / market_cap_usd populated by security_classifier.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS securities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,          -- 'US' or 'HKEX'
            name TEXT,
            sector TEXT,                   -- one of 11 GICS-aligned IDs (v0.4)
            added_at TEXT NOT NULL,
            removed_at TEXT,              -- NULL = still active
            source TEXT,                  -- which scanner picked it
            reason TEXT,                  -- why it was picked (raw, from scanner)
            market_cap_tier TEXT,          -- MICRO|SMALL|MID|LARGE|MEGA (v0.4)
            market_cap_usd REAL,           -- snapshot, refreshed weekly (v0.4)
            volatility_regime TEXT,        -- low|medium|high|extreme (v0.5+, nullable)
            context_updated_at TEXT,       -- when sector/cap_tier last refreshed
            UNIQUE(symbol, market, added_at)
        )
    """)

    # ── Candle Data (Micro) ──
    # Raw OHLCV. No indicators. No derived values.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            timeframe TEXT NOT NULL,       -- '1m', '5m', '15m', '1h', '1d'
            timestamp TEXT NOT NULL,       -- ISO 8601 UTC
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            vwap REAL,                    -- volume-weighted avg price if available
            trade_count INTEGER,          -- number of trades in period if available
            collected_at TEXT NOT NULL,    -- when WE received this data
            UNIQUE(symbol, market, timeframe, timestamp)
        )
    """)

    # ── Macro Data (Macro) ──
    # Currencies, yields, indices — the kingdom contention scoreboard.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument TEXT NOT NULL,      -- 'DXY', 'USD/CNY', 'US10Y', 'VIX', etc.
            instrument_type TEXT NOT NULL,  -- 'currency', 'yield', 'index', 'commodity'
            timestamp TEXT NOT NULL,
            value REAL NOT NULL,
            change_pct REAL,              -- percent change from previous
            collected_at TEXT NOT NULL,
            UNIQUE(instrument, timestamp)
        )
    """)

    # ── Sector Data (Meso) ──
    # Sector ETFs and indices — where is money flowing?
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,          -- 'XLK', 'XLF', 'XLE', etc.
            name TEXT NOT NULL,            -- 'Technology', 'Financials', 'Energy'
            timestamp TEXT NOT NULL,
            close REAL NOT NULL,
            volume REAL,
            change_pct REAL,
            collected_at TEXT NOT NULL,
            UNIQUE(symbol, timestamp)
        )
    """)

    # ── News Events ──
    # Headlines with source provenance. No sentiment scoring.
    # The network learns what matters from outcomes, not our labels.
    # v0.4: 15-category taxonomy via news_classifier_regex.py (and LLM in Phase 1.5)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            source TEXT NOT NULL,          -- 'reuters', 'bloomberg', 'cnbc', etc.
            source_tier INTEGER,           -- 1=wire, 2=major, 3=secondary, 4=social
            author TEXT,                   -- if available
            url TEXT,
            published_at TEXT NOT NULL,    -- when the source published it
            collected_at TEXT NOT NULL,    -- when we captured it
            symbols TEXT,                  -- comma-separated related symbols
            markets TEXT,                  -- comma-separated related markets
            content_snippet TEXT,          -- first 500 chars if available
            news_category_primary TEXT,    -- 1 of 15 taxonomy IDs or 'other' (v0.4)
            news_category_secondary TEXT,  -- nullable, supports multi-label
            news_category_tertiary TEXT,   -- nullable, supports multi-label
            category_confidence REAL,      -- 0.0-1.0 from classifier
            classified_by TEXT,            -- 'regex_v1' | 'llm_v1' | 'manual'
            classified_at TEXT,            -- ISO timestamp of last classification
            UNIQUE(headline, source, published_at)
        )
    """)

    # ── Economic Releases (Slow Macro) ──
    # GDP, interest rates, employment, CPI — the scheduled events.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS economic_releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,      -- 'US GDP', 'Fed Funds Rate', etc.
            country TEXT NOT NULL,
            release_date TEXT NOT NULL,
            actual_value REAL,
            expected_value REAL,
            previous_value REAL,
            surprise REAL,                -- actual - expected
            source TEXT,
            collected_at TEXT NOT NULL,
            UNIQUE(event_name, country, release_date)
        )
    """)

    # ── Forward Returns (Truth Labels) ──
    # Computed offline AFTER data collection. NOT during.
    # This is what the network learns to predict.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            timestamp TEXT NOT NULL,       -- the point in time
            timeframe TEXT NOT NULL,       -- candle timeframe this relates to
            return_5m REAL,               -- 5-minute forward return (%)
            return_15m REAL,
            return_1h REAL,
            return_4h REAL,
            return_1d REAL,
            computed_at TEXT NOT NULL,
            UNIQUE(symbol, market, timestamp, timeframe)
        )
    """)

    # ── Collection Status ──
    # Track what we've collected and when. Operational metadata.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector TEXT NOT NULL,       -- 'candle', 'news', 'macro', 'sector'
            symbol TEXT,
            market TEXT,
            status TEXT NOT NULL,          -- 'success', 'error', 'partial'
            records_collected INTEGER,
            error_message TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)

    # ── Context Regime Summary (v0.4) ──
    # Analytics table — populated offline by context_regime.py.
    # NOT used during training. Lets us inspect which (news × sector × cap) cells
    # have distinguishable return distributions before committing to v0.4 training.
    cursor.execute("""
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
        )
    """)

    # ── Indexes for query performance ──
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol, market, timeframe, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_time ON candles(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_macro_lookup ON macro(instrument, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_time ON news(published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_symbols ON news(symbols)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_forward_lookup ON forward_returns(symbol, market, timestamp, timeframe)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_securities_active ON securities(market, removed_at)")
    # v0.4 indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_category_primary ON news(news_category_primary)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_category_published ON news(news_category_primary, published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_securities_sector ON securities(sector)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_securities_cap_tier ON securities(market_cap_tier)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_lookup ON context_regime_summary(news_category, sector, cap_tier, market)")

    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")


def log_collection(collector, symbol, market, status, records, error=None):
    """Log a collection run."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO collection_log (collector, symbol, market, status, records_collected, error_message, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (collector, symbol, market, status, records, error, now, now))
    conn.commit()
    conn.close()


def get_active_securities(market=None):
    """Get currently watched securities."""
    conn = get_connection()
    if market:
        rows = conn.execute(
            "SELECT * FROM securities WHERE removed_at IS NULL AND market = ? ORDER BY added_at DESC",
            (market,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM securities WHERE removed_at IS NULL ORDER BY market, added_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_security(symbol, market, name=None, sector=None, source=None, reason=None):
    """Add a security to the watch list."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    try:
        conn.execute("""
            INSERT INTO securities (symbol, market, name, sector, added_at, source, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, market, name, sector, now, source, reason))
        conn.commit()
        print(f"Added {symbol} ({market}) to watch list")
    except sqlite3.IntegrityError:
        print(f"{symbol} ({market}) already in watch list")
    conn.close()


def store_candles(candles_list):
    """
    Store candle data. Input: list of dicts with keys:
    symbol, market, timeframe, timestamp, open, high, low, close, volume
    Optional: vwap, trade_count
    """
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    inserted = 0
    for c in candles_list:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO candles
                (symbol, market, timeframe, timestamp, open, high, low, close, volume, vwap, trade_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c['symbol'], c['market'], c['timeframe'], c['timestamp'],
                c['open'], c['high'], c['low'], c['close'], c['volume'],
                c.get('vwap'), c.get('trade_count'), now
            ))
            inserted += 1
        except Exception as e:
            print(f"Error storing candle for {c.get('symbol')}: {e}")
    conn.commit()
    conn.close()
    return inserted


def store_news(headline, source, source_tier, published_at, symbols=None,
               markets=None, author=None, url=None, content_snippet=None,
               classify=True):
    """
    Store a news event. v0.4: tags the 15-category taxonomy at collection time
    when classify=True (default). Pass classify=False to skip tagging (e.g.,
    when bulk-importing and tagging in a separate pass).
    """
    conn = get_connection()
    now = datetime.utcnow().isoformat()

    # Pre-compute classification fields so we INSERT with them populated.
    cat_primary = cat_secondary = cat_tertiary = None
    confidence = None
    classified_by = classified_at = None
    if classify:
        try:
            # Local import to avoid circular dep (classifier imports get_connection)
            from storage.news_classifier_regex import (
                classify_headline, CLASSIFIER_VERSION,
            )
            cats, confidence = classify_headline(headline, content_snippet)
            cat_primary, cat_secondary, cat_tertiary = cats
            classified_by = CLASSIFIER_VERSION
            classified_at = now
        except Exception as e:
            # Don't let classifier failures block ingestion.
            print(f"Warning: news classifier failed on '{headline[:60]}': {e}")

    try:
        conn.execute("""
            INSERT OR IGNORE INTO news
            (headline, source, source_tier, author, url, published_at, collected_at,
             symbols, markets, content_snippet,
             news_category_primary, news_category_secondary, news_category_tertiary,
             category_confidence, classified_by, classified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (headline, source, source_tier, author, url, published_at, now,
              symbols, markets, content_snippet,
              cat_primary, cat_secondary, cat_tertiary,
              confidence, classified_by, classified_at))
        conn.commit()
    except Exception as e:
        print(f"Error storing news: {e}")
    conn.close()


def store_macro(instrument, instrument_type, timestamp, value, change_pct=None):
    """Store a macro data point."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO macro
            (instrument, instrument_type, timestamp, value, change_pct, collected_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (instrument, instrument_type, timestamp, value, change_pct, now))
        conn.commit()
    except Exception as e:
        print(f"Error storing macro {instrument}: {e}")
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready.")
    
    # Show table info
    conn = get_connection()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        print(f"  {t['name']}: {count} rows")
    conn.close()
