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
# =============================================================================

# Direction thresholds
DIRECTION_THRESHOLD_PCT = 0.05  # ±0.05% → balanced classes (36/36/28)
DIRECTION_BULLISH = 0
DIRECTION_BEARISH = 1
DIRECTION_NEUTRAL = 2

# Return horizons for candle model
CANDLE_RETURN_HORIZONS = ["return_5m", "return_15m", "return_1h"]
NUM_CANDLE_HORIZONS = len(CANDLE_RETURN_HORIZONS)


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

    def __init__(self, lookback=None, split="train", validation_split=None):
        if lookback is None:
            lookback = TRAINING["lookback_candles"]
        if validation_split is None:
            validation_split = TRAINING["validation_split"]

        self.lookback = lookback
        self.split = split

        conn = get_connection()

        # Load both timeframes
        self.candles_5m = self._load_candles(conn, "5m")
        self.candles_15m = self._load_candles(conn, "15m")
        self.label_data = self._load_labels(conn)

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

    def _load_labels(self, conn):
        """Load 5m forward returns (anchor timeframe)."""
        rows = conn.execute(
            "SELECT symbol, market, timestamp, return_5m, return_15m, return_1h "
            "FROM forward_returns WHERE timeframe = '5m'"
        ).fetchall()

        data = {}
        for r in rows:
            key = (r["symbol"], r["market"], r["timestamp"])
            data[key] = [r["return_5m"], r["return_15m"], r["return_1h"]]
        return data

    def _find_15m_index(self, key, timestamp):
        """Find index of nearest 15m candle <= timestamp via binary search."""
        if key not in self._15m_ts_index:
            return -1
        ts_list = self._15m_ts_index[key]
        pos = bisect_right(ts_list, timestamp) - 1
        return pos

    def _build_sample_index(self, validation_split):
        """Build aligned samples where both 5m and 15m have enough lookback."""
        all_samples = []

        for (sym, mkt), candles_5m in self.candles_5m.items():
            key = (sym, mkt)
            if key not in self.candles_15m:
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

        return {
            "candles_5m": torch.from_numpy(arr_5m),
            "candles_15m": torch.from_numpy(arr_15m),
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
