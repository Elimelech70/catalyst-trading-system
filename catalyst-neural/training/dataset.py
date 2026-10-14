"""
Catalyst Neural — Training Dataset

Loads aligned multi-modal samples from SQLite.
Each sample: (candle_window, macro_context, news_embedding, labels)
Handles missing data gracefully — zero vectors where data is absent.

"Don't tell the network what to see. Show it what happened."
"""

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from datetime import datetime, timedelta
from bisect import bisect_right

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import get_connection
from config.settings import MACRO_INSTRUMENTS, TRAINING

# Macro instruments in fixed order for consistent input vectors
MACRO_INSTRUMENT_ORDER = list(MACRO_INSTRUMENTS.keys())
NUM_MACRO_FEATURES = len(MACRO_INSTRUMENT_ORDER) * 2  # value + change_pct

# News encoder constants
NEWS_HASH_VOCAB = 5000
NEWS_NGRAM_SIZE = 3
NEWS_LOOKBACK_HOURS = 4
SOURCE_TIERS = 4
NEWS_FEATURE_DIM = NEWS_HASH_VOCAB + SOURCE_TIERS + 1  # hash + tier one-hot + relative_time

# Label clipping range (percent)
LABEL_CLIP = 10.0


class CatalystDataset(Dataset):
    """
    Multi-modal training dataset.

    Each sample:
    - candles: (lookback, 5) — normalized OHLCV window
    - macro:   (NUM_MACRO_FEATURES,) — 15 values + 15 change_pct
    - news:    (NEWS_FEATURE_DIM,) — averaged bag-of-ngrams + tier + time
    - labels:  (5,) — forward returns [5m, 15m, 1h, 4h, 1d]
    - label_mask: (5,) — 1.0 where label exists, 0.0 where NULL
    """

    def __init__(self, timeframe="5m", lookback=None, split="train",
                 validation_split=None, symbol=None, market=None):
        if lookback is None:
            lookback = TRAINING["lookback_candles"]
        if validation_split is None:
            validation_split = TRAINING["validation_split"]

        self.timeframe = timeframe
        self.lookback = lookback
        self.split = split

        conn = get_connection()

        # Load all data into memory
        self.candle_data = self._load_candles(conn, timeframe, symbol, market)
        self.macro_data = self._load_macro(conn)
        self.news_data = self._load_news(conn)
        self.label_data = self._load_labels(conn, timeframe, symbol, market)

        conn.close()

        # Build sample index and apply temporal split
        self.samples = self._build_sample_index(validation_split)

    def _load_candles(self, conn, timeframe, symbol, market):
        """Load candles grouped by (symbol, market) -> sorted list of dicts."""
        query = """
            SELECT symbol, market, timestamp, open, high, low, close, volume
            FROM candles WHERE timeframe = ?
        """
        params = [timeframe]
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if market:
            query += " AND market = ?"
            params.append(market)
        query += " ORDER BY symbol, market, timestamp ASC"

        rows = conn.execute(query, params).fetchall()
        data = {}
        for r in rows:
            key = (r["symbol"], r["market"])
            if key not in data:
                data[key] = []
            data[key].append({
                "timestamp": r["timestamp"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
            })
        return data

    def _load_macro(self, conn):
        """Load macro data: instrument -> sorted list of (timestamp, value, change_pct)."""
        rows = conn.execute(
            "SELECT instrument, timestamp, value, change_pct FROM macro ORDER BY timestamp ASC"
        ).fetchall()
        data = {}
        for r in rows:
            inst = r["instrument"]
            if inst not in data:
                data[inst] = {"timestamps": [], "values": [], "changes": []}
            data[inst]["timestamps"].append(r["timestamp"])
            data[inst]["values"].append(r["value"] or 0.0)
            data[inst]["changes"].append(r["change_pct"] or 0.0)
        return data

    def _load_news(self, conn):
        """Load news sorted by published_at."""
        rows = conn.execute(
            "SELECT headline, source_tier, published_at, symbols FROM news ORDER BY published_at ASC"
        ).fetchall()
        return [{
            "headline": r["headline"],
            "source_tier": r["source_tier"] or 3,
            "published_at": r["published_at"],
            "symbols": r["symbols"] or "",
        } for r in rows]

    def _load_labels(self, conn, timeframe, symbol, market):
        """Load forward returns keyed by (symbol, market, timestamp)."""
        query = "SELECT * FROM forward_returns WHERE timeframe = ?"
        params = [timeframe]
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if market:
            query += " AND market = ?"
            params.append(market)

        rows = conn.execute(query, params).fetchall()
        data = {}
        for r in rows:
            key = (r["symbol"], r["market"], r["timestamp"])
            data[key] = [
                r["return_5m"], r["return_15m"], r["return_1h"],
                r["return_4h"], r["return_1d"]
            ]
        return data

    def _build_sample_index(self, validation_split):
        """Build valid sample tuples and apply temporal train/val split."""
        all_samples = []

        for (sym, mkt), candles in self.candle_data.items():
            for i in range(self.lookback, len(candles)):
                ts = candles[i]["timestamp"]
                label_key = (sym, mkt, ts)
                if label_key in self.label_data:
                    vals = self.label_data[label_key]
                    if any(v is not None for v in vals):
                        all_samples.append((sym, mkt, i, ts))

        # Sort by timestamp for temporal split
        all_samples.sort(key=lambda x: x[3])

        split_idx = int(len(all_samples) * (1.0 - validation_split))
        if self.split == "train":
            return all_samples[:split_idx]
        else:
            return all_samples[split_idx:]

    def _normalize_candle_window(self, candles):
        """
        Normalize OHLCV window relative to first candle's close.
        OHLC: percent change from reference. Volume: log-normalized.
        Returns (lookback, 5) numpy array.
        """
        ref_close = candles[0]["close"]
        if ref_close == 0:
            ref_close = 1.0

        arr = np.zeros((len(candles), 5), dtype=np.float32)
        for i, c in enumerate(candles):
            arr[i, 0] = (c["open"] - ref_close) / ref_close * 100
            arr[i, 1] = (c["high"] - ref_close) / ref_close * 100
            arr[i, 2] = (c["low"] - ref_close) / ref_close * 100
            arr[i, 3] = (c["close"] - ref_close) / ref_close * 100
            arr[i, 4] = np.log1p(c["volume"])

        # Z-score volume within window
        vol = arr[:, 4]
        vol_std = vol.std()
        if vol_std > 0:
            arr[:, 4] = (vol - vol.mean()) / vol_std

        return arr

    def _get_macro_snapshot(self, timestamp_str):
        """
        Get most recent macro reading for each instrument at or before timestamp.
        Returns (NUM_MACRO_FEATURES,) array — zero-filled for missing.
        """
        vec = np.zeros(NUM_MACRO_FEATURES, dtype=np.float32)

        for idx, inst in enumerate(MACRO_INSTRUMENT_ORDER):
            if inst not in self.macro_data:
                continue
            md = self.macro_data[inst]
            # Binary search for most recent reading <= timestamp
            pos = bisect_right(md["timestamps"], timestamp_str) - 1
            if pos >= 0:
                vec[idx * 2] = md["values"][pos]
                vec[idx * 2 + 1] = md["changes"][pos]

        return vec

    def _get_news_bag(self, timestamp_str, symbol=None):
        """
        Average bag-of-ngrams for headlines within NEWS_LOOKBACK_HOURS before timestamp.
        Returns (NEWS_FEATURE_DIM,) array — zero if no news.
        """
        if not self.news_data:
            return np.zeros(NEWS_FEATURE_DIM, dtype=np.float32)

        try:
            ts = datetime.fromisoformat(timestamp_str.replace("+00:00", ""))
        except ValueError:
            return np.zeros(NEWS_FEATURE_DIM, dtype=np.float32)

        cutoff = (ts - timedelta(hours=NEWS_LOOKBACK_HOURS)).isoformat()
        bags = []

        for article in self.news_data:
            pub = article["published_at"]
            if pub < cutoff:
                continue
            if pub > timestamp_str:
                break

            # Skip if symbol filter and article doesn't mention it
            if symbol and symbol not in article["symbols"].upper():
                continue

            # Build feature vector for this headline
            feat = np.zeros(NEWS_FEATURE_DIM, dtype=np.float32)

            # Character n-gram hash
            headline_hash = self._hash_headline(article["headline"])
            feat[:NEWS_HASH_VOCAB] = headline_hash

            # Source tier one-hot
            tier = min(max(article["source_tier"], 1), SOURCE_TIERS)
            feat[NEWS_HASH_VOCAB + tier - 1] = 1.0

            # Relative time (hours before, normalized)
            try:
                pub_dt = datetime.fromisoformat(pub.replace("+00:00", "").replace("Z", ""))
                delta_hours = (ts - pub_dt).total_seconds() / 3600.0
                feat[NEWS_HASH_VOCAB + SOURCE_TIERS] = min(delta_hours / NEWS_LOOKBACK_HOURS, 1.0)
            except ValueError:
                pass

            bags.append(feat)

        if not bags:
            return np.zeros(NEWS_FEATURE_DIM, dtype=np.float32)

        return np.mean(bags[:10], axis=0).astype(np.float32)  # cap at 10 headlines

    @staticmethod
    def _hash_headline(headline, vocab_size=NEWS_HASH_VOCAB, n=NEWS_NGRAM_SIZE):
        """Convert headline to bag-of-character-trigrams via hashing trick."""
        text = headline.lower().strip()
        vec = np.zeros(vocab_size, dtype=np.float32)
        for i in range(len(text) - n + 1):
            ngram = text[i:i + n]
            bucket = hash(ngram) % vocab_size
            vec[bucket] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sym, mkt, candle_idx, ts = self.samples[idx]

        # Candle window
        candles = self.candle_data[(sym, mkt)]
        window = candles[candle_idx - self.lookback:candle_idx]
        candle_tensor = self._normalize_candle_window(window)

        # Macro snapshot
        macro_tensor = self._get_macro_snapshot(ts)

        # News bag
        news_tensor = self._get_news_bag(ts, symbol=sym)

        # Labels + mask
        raw_labels = self.label_data[(sym, mkt, ts)]
        labels = np.zeros(5, dtype=np.float32)
        mask = np.zeros(5, dtype=np.float32)
        for i, v in enumerate(raw_labels):
            if v is not None:
                labels[i] = np.clip(v, -LABEL_CLIP, LABEL_CLIP)
                mask[i] = 1.0

        return {
            "candles": torch.from_numpy(candle_tensor),
            "macro": torch.from_numpy(macro_tensor),
            "news": torch.from_numpy(news_tensor),
            "labels": torch.from_numpy(labels),
            "label_mask": torch.from_numpy(mask),
        }


def get_dataloaders(timeframe="5m", batch_size=None, lookback=None,
                    validation_split=None, num_workers=2):
    """Create train and validation DataLoaders."""
    if batch_size is None:
        batch_size = TRAINING["batch_size"]

    train_ds = CatalystDataset(
        timeframe=timeframe, lookback=lookback, split="train",
        validation_split=validation_split
    )
    val_ds = CatalystDataset(
        timeframe=timeframe, lookback=lookback, split="val",
        validation_split=validation_split
    )

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    info = {
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "timeframe": timeframe,
        "lookback": train_ds.lookback,
        "securities": len(train_ds.candle_data),
        "macro_instruments": len(train_ds.macro_data),
        "news_articles": len(train_ds.news_data),
    }

    return train_loader, val_loader, info


# =============================================================================
# v0.3 — CandleDataset (multi-timeframe: 5m + 15m)
# v0.4 — adds news_context (16,) and security_context (18,) per
#        Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md
# =============================================================================

# Direction thresholds
DIRECTION_THRESHOLD_PCT = 0.05  # ±0.05% → balanced classes (36/36/28)
DIRECTION_BULLISH = 0
DIRECTION_BEARISH = 1
DIRECTION_NEUTRAL = 2

# Return horizons for candle model
CANDLE_RETURN_HORIZONS = ["return_5m", "return_15m", "return_1h"]
NUM_CANDLE_HORIZONS = len(CANDLE_RETURN_HORIZONS)

# ── v0.4 Context Conditioning ──
# News category order. MUST stay stable across train+inference; do not reorder
# without regenerating model. 'other' is the catch-all 16th slot.
NEWS_CATEGORY_ORDER = [
    "earnings", "corporate_action", "executive", "capital",
    "regulatory_approval", "regulatory_action", "bankruptcy",
    "product", "operational",
    "analyst", "credit_rating",
    "monetary_policy", "macro_economic", "policy_regulation", "sector_wide",
    "other",
]
NEWS_CATEGORY_INDEX = {c: i for i, c in enumerate(NEWS_CATEGORY_ORDER)}
NUM_NEWS_CATEGORIES = len(NEWS_CATEGORY_ORDER)  # 16

# Security context: market(2) + sector(11) + cap_tier(5) = 18 one-hot dims.
MARKET_ORDER = ["US", "HKEX"]
SECTOR_ORDER = [
    "TECH", "BIO", "FIN", "CONS_D", "CONS_S",
    "ENERGY", "INDUSTRIAL", "MATERIALS", "UTIL", "COMMS", "REAL_ESTATE",
]
CAP_TIER_ORDER = ["MICRO", "SMALL", "MID", "LARGE", "MEGA"]
NUM_SECURITY_FEATURES = len(MARKET_ORDER) + len(SECTOR_ORDER) + len(CAP_TIER_ORDER)  # 18

# News-context construction (architecture Section 8.2)
NEWS_CONTEXT_LOOKBACK_HOURS = 4
SOURCE_TIER_WEIGHTS = {1: 1.5, 2: 1.3, 3: 1.0, 4: 0.8, 5: 0.8}


class CandleDataset(Dataset):
    """
    v0.3 multi-timeframe candle dataset.

    Pairs 5m and 15m candle windows aligned by timestamp.
    Labels: direction (3-class) + forward returns (5m, 15m, 1h).

    Each sample:
    - candles_5m:  (lookback, 5) — normalized OHLCV
    - candles_15m: (lookback, 5) — normalized OHLCV
    - direction:   int — 0=bullish, 1=bearish, 2=neutral
    - returns:     (3,) — 5m, 15m, 1h forward returns
    - return_mask: (3,) — 1.0 where label exists
    """

    def __init__(self, lookback=None, split="train", validation_split=None,
                 include_context=True, symbol_filter=None,
                 min_date=None, max_bars_per_symbol=None):
        """
        include_context: v0.4 default True — populate news_context and
        security_context fields. Set False to mimic v0.3 (zero-vectors returned
        so the same dataset object can feed either a v0.3 or v0.4 model
        without breaking the keys).

        symbol_filter: optional list of (symbol, market) tuples. If given, only
        samples whose key matches are retained. Used by the cohort experiment
        (training/cpcv_trainer.py) to train on a specific 150-symbol slice.

        split: "train" / "val" / "all". "all" returns the full sample list
        without a train/val cut — required for external cross-validation
        (CPCV) which makes its own splits.

        min_date: YYYY-MM-DD string. Candles before this date are not loaded.
        Used by cohort runs to bound the data window — 150 symbols × 5y of
        intraday bars OOM-kills the laptop. Default None = no limit.

        max_bars_per_symbol: alternative cap — keep only the last N bars per
        symbol. Computed at the symbol level rather than absolute date.
        """
        if lookback is None:
            lookback = TRAINING["lookback_candles"]
        if validation_split is None:
            validation_split = TRAINING["validation_split"]

        self.lookback = lookback
        self.split = split
        self.include_context = include_context
        self.min_date = min_date
        self.max_bars_per_symbol = max_bars_per_symbol
        # Normalize symbol_filter to a set of (symbol_str, market_str) for fast lookup
        if symbol_filter is not None:
            self.symbol_filter = {(str(s), str(m)) for (s, m) in symbol_filter}
        else:
            self.symbol_filter = None

        conn = get_connection()

        # Load both timeframes — filtered at SQL time when symbol_filter is set
        # so we don't load the whole 30M-row candles table into RAM.
        self.candles_5m = self._load_candles_filtered(conn, "5m")
        self.candles_15m = self._load_candles_filtered(conn, "15m")
        # The Polygon backfill (2026-06-01) only collected 5m candles. For symbols
        # missing 15m data, derive it by aggregating 3 consecutive 5m bars.
        # Same underlying data, just resampled — keeps the dual-resolution
        # CNN architecture working without a separate Polygon 15m backfill.
        for key, bars_5m in self.candles_5m.items():
            if key not in self.candles_15m or len(self.candles_15m[key]) < 100:
                self.candles_15m[key] = self._aggregate_5m_to_15m(bars_5m)
        self.label_data = self._load_labels(conn)

        # v0.4: load classified news and security context.
        if self.include_context:
            self.news_by_symbol, self.news_all = self._load_news_categorized(conn)
            self.security_context_cache = self._load_security_context(conn)
        else:
            self.news_by_symbol = {}
            self.news_all = []
            self.security_context_cache = {}

        conn.close()

        # Build 15m timestamp index for fast lookup
        self._15m_ts_index = {}
        for key, candles in self.candles_15m.items():
            self._15m_ts_index[key] = [c["timestamp"] for c in candles]

        self.samples = self._build_sample_index(validation_split)

    def _load_candles(self, conn, timeframe):
        """Load candles grouped by (symbol, market) -> sorted list."""
        rows = conn.execute(
            "SELECT symbol, market, timestamp, open, high, low, close, volume "
            "FROM candles WHERE timeframe = ? ORDER BY symbol, market, timestamp ASC",
            [timeframe]
        ).fetchall()

        data = {}
        for r in rows:
            key = (r["symbol"], r["market"])
            if key not in data:
                data[key] = []
            data[key].append({
                "timestamp": r["timestamp"],
                "open": r["open"], "high": r["high"],
                "low": r["low"], "close": r["close"],
                "volume": r["volume"],
            })
        return data

    @staticmethod
    def _aggregate_5m_to_15m(bars_5m):
        """Aggregate 5m OHLCV bars to 15m by groups of 3, aligned to 15-min
        boundaries. Used when 15m data isn't independently collected (e.g.,
        Polygon backfill, which only fetches 5m)."""
        from datetime import datetime
        bars_15m = []
        i = 0
        while i < len(bars_5m):
            # Parse timestamp to determine the 15m bucket boundary
            ts_str = bars_5m[i]["timestamp"]
            try:
                ts = datetime.fromisoformat(ts_str.replace("+00:00", "").replace("Z", ""))
            except ValueError:
                i += 1
                continue
            # Align to 15-minute boundary (minutes 0/15/30/45)
            bucket_start_min = (ts.minute // 15) * 15
            bucket_ts = ts.replace(minute=bucket_start_min, second=0, microsecond=0)
            # Collect all 5m bars in this 15m bucket
            group = []
            while i < len(bars_5m):
                ts_i_str = bars_5m[i]["timestamp"]
                try:
                    ts_i = datetime.fromisoformat(ts_i_str.replace("+00:00", "").replace("Z", ""))
                except ValueError:
                    i += 1; continue
                bucket_min_i = (ts_i.minute // 15) * 15
                bucket_ts_i = ts_i.replace(minute=bucket_min_i, second=0, microsecond=0)
                if bucket_ts_i != bucket_ts:
                    break
                group.append(bars_5m[i])
                i += 1
            if not group:
                continue
            bars_15m.append({
                "timestamp": bucket_ts.isoformat(),
                "open":      group[0]["open"],
                "high":      max(g["high"] for g in group),
                "low":       min(g["low"] for g in group),
                "close":     group[-1]["close"],
                "volume":    sum(g["volume"] for g in group),
            })
        return bars_15m

    def _load_labels(self, conn):
        """Load 5m forward returns (anchor timeframe), filtered by symbol_filter
        and min_date when set. With the Polygon backfill the unfiltered
        forward_returns table has ~38M rows — fetching them all OOM-kills the
        laptop. Filter at SQL time."""
        where_parts = ["timeframe = '5m'"]
        params = []
        if self.symbol_filter is not None:
            if not self.symbol_filter:
                return {}
            syms = [s for s, m in self.symbol_filter]
            placeholders = ",".join("?" for _ in syms)
            where_parts.append(f"symbol IN ({placeholders})")
            params.extend(syms)
        if self.min_date is not None:
            where_parts.append("timestamp >= ?")
            params.append(self.min_date)
        where_sql = " AND ".join(where_parts)
        rows = conn.execute(
            f"SELECT symbol, market, timestamp, return_5m, return_15m, return_1h "
            f"FROM forward_returns WHERE {where_sql}",
            params
        ).fetchall()
        data = {}
        for r in rows:
            key = (r["symbol"], r["market"], r["timestamp"])
            data[key] = [r["return_5m"], r["return_15m"], r["return_1h"]]
        return data

    # ── v0.4 Context Loading ──

    def _load_news_categorized(self, conn):
        """
        Load classified news organized for fast per-symbol lookup.

        Returns:
          news_by_symbol: {symbol: [list of news dicts sorted by published_at]}
          news_all:       [news dicts with empty 'symbols' field — market-wide]

        Only news with news_category_primary != NULL is loaded (the rest can't
        contribute a category signal). Headlines may reference multiple symbols
        via the comma-separated `symbols` field; we index against each.
        """
        rows = conn.execute(
            "SELECT headline, source_tier, published_at, symbols, "
            "       news_category_primary, news_category_secondary, "
            "       news_category_tertiary, category_confidence "
            "FROM news WHERE news_category_primary IS NOT NULL "
            "ORDER BY published_at ASC"
        ).fetchall()

        by_symbol: dict = {}
        all_market: list = []
        for r in rows:
            item = {
                "published_at": r["published_at"],
                "source_tier": r["source_tier"] or 3,
                "primary": r["news_category_primary"],
                "secondary": r["news_category_secondary"],
                "tertiary": r["news_category_tertiary"],
                "confidence": r["category_confidence"] or 0.0,
            }
            symbols_field = (r["symbols"] or "").strip()
            if not symbols_field:
                all_market.append(item)
                continue
            for sym in symbols_field.split(","):
                sym = sym.strip().upper()
                if not sym:
                    continue
                by_symbol.setdefault(sym, []).append(item)
        # Ensure each per-symbol list is sorted (input is already, but be defensive)
        for lst in by_symbol.values():
            lst.sort(key=lambda x: x["published_at"])
        return by_symbol, all_market

    def _load_security_context(self, conn):
        """
        Build {(symbol, market): security_context_vector (18,)} cache.

        Reads sector / market_cap_tier from securities. Multiple rows may exist
        for the same (symbol, market) due to re-additions — the latest non-NULL
        sector/cap_tier wins. ETFs and unclassified securities get an all-zero
        vector (architecture Section 8.4: "use 'other' fallback bit"; since we
        don't have explicit 'other' bits in market/sector/cap_tier axes, an
        all-zero vector is the well-defined neutral input).
        """
        rows = conn.execute(
            "SELECT symbol, market, sector, market_cap_tier, context_updated_at "
            "FROM securities "
            "WHERE removed_at IS NULL "
            "ORDER BY context_updated_at DESC NULLS LAST, id DESC"
        ).fetchall()

        cache: dict = {}
        for r in rows:
            key = (r["symbol"], r["market"])
            if key in cache:
                continue  # latest update wins (DESC ordering)
            vec = np.zeros(NUM_SECURITY_FEATURES, dtype=np.float32)
            # Market one-hot (always set if market is known)
            mkt = r["market"]
            if mkt in MARKET_ORDER:
                vec[MARKET_ORDER.index(mkt)] = 1.0
            # Sector one-hot
            sec = r["sector"]
            if sec and sec in SECTOR_ORDER:
                vec[len(MARKET_ORDER) + SECTOR_ORDER.index(sec)] = 1.0
            # Cap-tier one-hot
            tier = r["market_cap_tier"]
            if tier and tier in CAP_TIER_ORDER:
                vec[len(MARKET_ORDER) + len(SECTOR_ORDER) + CAP_TIER_ORDER.index(tier)] = 1.0
            cache[key] = vec
        return cache

    def _build_news_context(self, timestamp_str, symbol):
        """
        Build the 16-dim news_context vector for (timestamp, symbol).

        Pulls news in [t - 4h, t] for this symbol (no fallback to market-wide
        when symbol is known — symbol-specific signal is cleaner). Each
        headline contributes to its primary category (full weight) plus
        secondary/tertiary at half weight, scaled by source-tier weight and
        recency decay. L1-normalized; all-zero when no news matches.
        """
        if not self.news_by_symbol:
            return np.zeros(NUM_NEWS_CATEGORIES, dtype=np.float32)

        symbol_upper = symbol.upper()
        symbol_news = self.news_by_symbol.get(symbol_upper)
        if not symbol_news:
            return np.zeros(NUM_NEWS_CATEGORIES, dtype=np.float32)

        try:
            ts = datetime.fromisoformat(
                timestamp_str.replace("+00:00", "").replace("Z", "")
            )
        except ValueError:
            return np.zeros(NUM_NEWS_CATEGORIES, dtype=np.float32)
        cutoff_ts = ts - timedelta(hours=NEWS_CONTEXT_LOOKBACK_HOURS)
        cutoff_str = cutoff_ts.isoformat()

        vec = np.zeros(NUM_NEWS_CATEGORIES, dtype=np.float32)
        for article in symbol_news:
            pub = article["published_at"]
            if pub < cutoff_str:
                continue
            if pub > timestamp_str:
                break  # sorted — stop scanning
            try:
                pub_dt = datetime.fromisoformat(
                    pub.replace("+00:00", "").replace("Z", "")
                )
            except ValueError:
                continue
            hours_before = (ts - pub_dt).total_seconds() / 3600.0
            recency = max(0.0, 1.0 - hours_before / NEWS_CONTEXT_LOOKBACK_HOURS)
            tier_w = SOURCE_TIER_WEIGHTS.get(article["source_tier"], 1.0)
            weight = tier_w * recency

            primary = article.get("primary")
            if primary in NEWS_CATEGORY_INDEX:
                vec[NEWS_CATEGORY_INDEX[primary]] += weight
            secondary = article.get("secondary")
            if secondary and secondary in NEWS_CATEGORY_INDEX:
                vec[NEWS_CATEGORY_INDEX[secondary]] += 0.5 * weight
            tertiary = article.get("tertiary")
            if tertiary and tertiary in NEWS_CATEGORY_INDEX:
                vec[NEWS_CATEGORY_INDEX[tertiary]] += 0.5 * weight

        # L1-normalize so the vector sums to 1 when news is present,
        # all-zero when absent (per architecture Section 8.2).
        total = vec.sum()
        if total > 0:
            vec /= total
        return vec

    def _get_security_context(self, symbol, market):
        """O(1) lookup from cache. Returns all-zero vector for unknowns."""
        vec = self.security_context_cache.get((symbol, market))
        if vec is None:
            return np.zeros(NUM_SECURITY_FEATURES, dtype=np.float32)
        return vec

    def _find_15m_index(self, key, timestamp):
        """Find index of nearest 15m candle <= timestamp via binary search."""
        if key not in self._15m_ts_index:
            return -1
        ts_list = self._15m_ts_index[key]
        pos = bisect_right(ts_list, timestamp) - 1
        return pos

    def _load_candles_filtered(self, conn, timeframe):
        """Same as _load_candles but applies symbol_filter + date-window filters
        at SQL time. Necessary for the Polygon-scale universe (150 symbols × 5y
        = ~15M rows per timeframe = ~30M rows total which OOM-kills the laptop).
        When symbol_filter is None falls back to the original behaviour."""
        if self.symbol_filter is None and self.min_date is None:
            return self._load_candles(conn, timeframe)
        if self.symbol_filter is not None and not self.symbol_filter:
            return {}

        # Build the WHERE conditions
        where_parts = ["timeframe = ?"]
        params = [timeframe]
        if self.symbol_filter is not None:
            placeholders = ",".join("?" for _ in self.symbol_filter)
            syms = [s for s, m in self.symbol_filter]
            where_parts.append(f"symbol IN ({placeholders})")
            params.extend(syms)
        if self.min_date is not None:
            where_parts.append("timestamp >= ?")
            params.append(self.min_date)

        where_sql = " AND ".join(where_parts)
        rows = conn.execute(
            f"SELECT symbol, market, timestamp, open, high, low, close, volume "
            f"FROM candles WHERE {where_sql} "
            f"ORDER BY symbol, market, timestamp ASC",
            params
        ).fetchall()

        data = {}
        for r in rows:
            key = (r["symbol"], r["market"])
            if self.symbol_filter is not None and key not in self.symbol_filter:
                continue
            if key not in data:
                data[key] = []
            data[key].append({
                "timestamp": r["timestamp"],
                "open": r["open"], "high": r["high"],
                "low": r["low"], "close": r["close"],
                "volume": r["volume"],
            })

        # Apply max_bars_per_symbol cap if set (keeps the last N bars per symbol)
        if self.max_bars_per_symbol is not None:
            for k in data:
                if len(data[k]) > self.max_bars_per_symbol:
                    data[k] = data[k][-self.max_bars_per_symbol:]
        return data

    def _build_sample_index(self, validation_split):
        """Build aligned samples where both 5m and 15m have enough lookback."""
        all_samples = []

        for (sym, mkt), candles_5m in self.candles_5m.items():
            key = (sym, mkt)
            if key not in self.candles_15m:
                continue
            # v0.4.1 cohort experiment: filter to the cohort's symbol list
            if self.symbol_filter is not None and key not in self.symbol_filter:
                continue

            for i in range(self.lookback, len(candles_5m)):
                ts = candles_5m[i]["timestamp"]
                label_key = (sym, mkt, ts)

                if label_key not in self.label_data:
                    continue
                vals = self.label_data[label_key]
                if vals[0] is None:  # need at least 5m return for direction
                    continue

                # Check 15m has enough lookback
                idx_15m = self._find_15m_index(key, ts)
                if idx_15m < self.lookback:
                    continue

                all_samples.append((sym, mkt, i, idx_15m, ts))

        all_samples.sort(key=lambda x: x[4])

        # split="all" → return the whole list (used by external CPCV splitter)
        if self.split == "all":
            return all_samples

        split_idx = int(len(all_samples) * (1.0 - validation_split))
        if self.split == "train":
            return all_samples[:split_idx]
        else:
            return all_samples[split_idx:]

    @staticmethod
    def _normalize_candle_window(candles):
        """Normalize OHLCV window. Reuses same logic as CatalystDataset."""
        ref_close = candles[0]["close"]
        if ref_close == 0:
            ref_close = 1.0

        arr = np.zeros((len(candles), 5), dtype=np.float32)
        for i, c in enumerate(candles):
            arr[i, 0] = (c["open"] - ref_close) / ref_close * 100
            arr[i, 1] = (c["high"] - ref_close) / ref_close * 100
            arr[i, 2] = (c["low"] - ref_close) / ref_close * 100
            arr[i, 3] = (c["close"] - ref_close) / ref_close * 100
            arr[i, 4] = np.log1p(c["volume"])

        vol = arr[:, 4]
        vol_std = vol.std()
        if vol_std > 0:
            arr[:, 4] = (vol - vol.mean()) / vol_std

        return arr

    @staticmethod
    def return_to_direction(return_5m):
        """Convert 5m return to direction class."""
        if return_5m > DIRECTION_THRESHOLD_PCT:
            return DIRECTION_BULLISH
        elif return_5m < -DIRECTION_THRESHOLD_PCT:
            return DIRECTION_BEARISH
        else:
            return DIRECTION_NEUTRAL

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sym, mkt, idx_5m, idx_15m, ts = self.samples[idx]

        # 5m window
        candles_5m = self.candles_5m[(sym, mkt)]
        window_5m = candles_5m[idx_5m - self.lookback:idx_5m]
        arr_5m = self._normalize_candle_window(window_5m)

        # 15m window
        candles_15m = self.candles_15m[(sym, mkt)]
        window_15m = candles_15m[idx_15m - self.lookback:idx_15m]
        arr_15m = self._normalize_candle_window(window_15m)

        # Labels
        raw = self.label_data[(sym, mkt, ts)]
        direction = self.return_to_direction(raw[0])

        returns = np.zeros(NUM_CANDLE_HORIZONS, dtype=np.float32)
        mask = np.zeros(NUM_CANDLE_HORIZONS, dtype=np.float32)
        for i, v in enumerate(raw):
            if v is not None:
                returns[i] = np.clip(v, -LABEL_CLIP, LABEL_CLIP)
                mask[i] = 1.0

        # v0.4 context vectors (zeros when include_context=False)
        if self.include_context:
            news_ctx = self._build_news_context(ts, sym)
            sec_ctx = self._get_security_context(sym, mkt)
        else:
            news_ctx = np.zeros(NUM_NEWS_CATEGORIES, dtype=np.float32)
            sec_ctx = np.zeros(NUM_SECURITY_FEATURES, dtype=np.float32)

        return {
            "candles_5m": torch.from_numpy(arr_5m),
            "candles_15m": torch.from_numpy(arr_15m),
            "news_context": torch.from_numpy(news_ctx),
            "security_context": torch.from_numpy(sec_ctx),
            "direction": torch.tensor(direction, dtype=torch.long),
            "returns": torch.from_numpy(returns),
            "return_mask": torch.from_numpy(mask),
        }


def get_candle_dataloaders(batch_size=None, lookback=None,
                           validation_split=None, num_workers=2):
    """Create train and validation DataLoaders for CandleDataset."""
    if batch_size is None:
        batch_size = TRAINING["batch_size"]

    train_ds = CandleDataset(lookback=lookback, split="train",
                             validation_split=validation_split)
    val_ds = CandleDataset(lookback=lookback, split="val",
                           validation_split=validation_split)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    # Count direction class distribution
    direction_counts = [0, 0, 0]
    for s in train_ds.samples + val_ds.samples:
        sym, mkt, _, _, ts = s
        ret_5m = train_ds.label_data[(sym, mkt, ts)][0]
        d = CandleDataset.return_to_direction(ret_5m)
        direction_counts[d] += 1

    total = sum(direction_counts) or 1
    info = {
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "lookback": train_ds.lookback,
        "securities_5m": len(train_ds.candles_5m),
        "securities_15m": len(train_ds.candles_15m),
        "direction_balance": {
            "bullish": f"{direction_counts[0]} ({direction_counts[0]/total*100:.1f}%)",
            "bearish": f"{direction_counts[1]} ({direction_counts[1]/total*100:.1f}%)",
            "neutral": f"{direction_counts[2]} ({direction_counts[2]/total*100:.1f}%)",
        },
        "direction_threshold": f"±{DIRECTION_THRESHOLD_PCT}%",
    }

    return train_loader, val_loader, info
