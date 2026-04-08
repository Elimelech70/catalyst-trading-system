#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: cortex.py
Version: 1.0.0
Last Updated: 2026-04-06
Purpose: Neural cortex — forward-return prediction engine

REVISION HISTORY:
v1.0.0 (2026-04-06) - Initial creation
- ONNX Runtime inference for CatalystNet
- Polls communication table for predict tasks
- Fetches live OHLCV + macro data via Alpaca/Yahoo
- Publishes predictions to the signals table
- Periodic background prediction cycle during market hours

v1.1.0 (2026-04-08) - Dual-model architecture (v0.3)
- Added CandleModel support (multi-timeframe 5m + 15m direction prediction)
- Candle model: direction (bullish/bearish/neutral) + returns (5m, 15m, 1h) + confidence
- Fused model remains optional for backward compatibility
- New env vars: CANDLE_MODEL_PATH, FUSED_MODEL_PATH

Description:
The neural cortex is the prediction engine of the agent body.
Trained on the laptop (RTX 4050), deployed here as ONNX for CPU inference.
CandleModel v0.3: multi-timeframe direction classification + return prediction.
Fused CatalystNet: 5-horizon return prediction (legacy, optional).
Publishes directional signals with confidence scores.

"Don't tell the network what to see. Show it what happened.
 Let it find what matters."
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import numpy as np
import onnxruntime as ort
import yfinance as yf

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import (
    Component, MessageType, Direction,
    Severity, SignalDomain, SignalScope,
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neural")

# ── Constants matching training configuration ──
LOOKBACK = 60
HORIZON_NAMES = ["5m", "15m", "1h", "4h", "1d"]
CANDLE_HORIZON_NAMES = ["5m", "15m", "1h"]
DIRECTION_NAMES = ["bullish", "bearish", "neutral"]
LABEL_CLIP = 10.0

# Macro instruments in the same order as training
MACRO_INSTRUMENT_ORDER = [
    "DXY", "USD/CNY", "USD/JPY", "USD/HKD", "EUR/USD", "GBP/USD",
    "AUD/USD", "USD/RUB", "US10Y", "US02Y", "US30Y", "VIX",
    "GOLD", "OIL", "BTC/USD",
]
MACRO_YAHOO = {
    "DXY": "DX-Y.NYB", "USD/CNY": "CNY=X", "USD/JPY": "JPY=X",
    "USD/HKD": "HKD=X", "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X", "USD/RUB": "RUB=X",
    "US10Y": "^TNX", "US02Y": "^IRX", "US30Y": "^TYX",
    "VIX": "^VIX", "GOLD": "GC=F", "OIL": "CL=F", "BTC/USD": "BTC-USD",
}
NUM_MACRO_FEATURES = len(MACRO_INSTRUMENT_ORDER) * 2  # value + change_pct

# News feature dim (must match training)
NEWS_HASH_VOCAB = 5000
SOURCE_TIERS = 4
NEWS_FEATURE_DIM = NEWS_HASH_VOCAB + SOURCE_TIERS + 1

# HKEX suffix mapping
HKEX_SUFFIX = ".HK"

# Confidence thresholds for signal severity
CONFIDENCE_HIGH = 0.7
CONFIDENCE_MED = 0.4

# Prediction cycle interval (seconds)
PREDICT_INTERVAL = 300  # 5 minutes

# Component name
NEURAL = "neural"


class NeuralCortex:
    """
    Neural prediction engine — the brain's forward model.

    Uses ONNX Runtime to run trained models on CPU.
    Supports dual-model architecture:
    - CandleModel v0.3: multi-timeframe direction classification
    - CatalystNet (fused): 5-horizon return prediction (optional)
    """

    def __init__(self, config: AgentConfig,
                 candle_model_path: Optional[str] = None,
                 fused_model_path: Optional[str] = None):
        self.config = config
        self.candle_model_path = candle_model_path
        self.fused_model_path = fused_model_path
        self.db: Optional[AgentDB] = None
        self.candle_session: Optional[ort.InferenceSession] = None
        self.fused_session: Optional[ort.InferenceSession] = None
        self._running = False
        self._macro_cache: Dict[str, Dict] = {}
        self._macro_cache_time: Optional[datetime] = None

    async def initialize(self):
        """Load ONNX models and connect to agent.db."""
        models_loaded = []

        # Load candle model (v0.3 — primary)
        if self.candle_model_path and os.path.exists(self.candle_model_path):
            self.candle_session = ort.InferenceSession(
                self.candle_model_path,
                providers=["CPUExecutionProvider"],
            )
            inputs = {i.name: i.shape for i in self.candle_session.get_inputs()}
            logger.info("CandleModel loaded: %s — inputs: %s",
                        self.candle_model_path, inputs)
            models_loaded.append("candle")
        elif self.candle_model_path:
            logger.warning("CandleModel not found: %s", self.candle_model_path)

        # Load fused model (legacy — optional)
        if self.fused_model_path and os.path.exists(self.fused_model_path):
            self.fused_session = ort.InferenceSession(
                self.fused_model_path,
                providers=["CPUExecutionProvider"],
            )
            inputs = {i.name: i.shape for i in self.fused_session.get_inputs()}
            logger.info("FusedModel loaded: %s — inputs: %s",
                        self.fused_model_path, inputs)
            models_loaded.append("fused")
        elif self.fused_model_path:
            logger.warning("FusedModel not found: %s", self.fused_model_path)

        if not models_loaded:
            raise FileNotFoundError("No models found. Set CANDLE_MODEL_PATH or FUSED_MODEL_PATH.")

        # Connect to agent database
        self.db = AgentDB(self.config.agent_db_path)
        await self.db.connect()

        # Announce presence
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=NEURAL,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="neural_online",
            payload={
                "status": "online",
                "models": models_loaded,
                "candle_model": os.path.basename(self.candle_model_path or ""),
                "fused_model": os.path.basename(self.fused_model_path or ""),
            },
        )
        logger.info("Neural cortex online — models: %s", models_loaded)

    async def run(self):
        """Main loop — handle tasks + periodic prediction cycles."""
        self._running = True
        logger.info("Neural cortex entering main loop")

        last_predict = 0

        while self._running:
            try:
                # 1. Check for explicit predict tasks
                messages = await self.db.receive_messages(
                    target=NEURAL,
                    msg_types=[MessageType.TASK],
                    limit=5,
                )
                for msg in messages:
                    await self._process_task(msg)

                # 2. Periodic prediction cycle during market hours
                now = datetime.now(timezone.utc).timestamp()
                if now - last_predict > PREDICT_INTERVAL:
                    if self._any_market_open():
                        await self._prediction_cycle()
                        last_predict = now

            except Exception as e:
                logger.error("Neural loop error: %s", e, exc_info=True)
                await self._publish_health_signal(
                    f"Neural loop error: {str(e)[:200]}",
                    data={"error_type": type(e).__name__},
                )

            await asyncio.sleep(self.config.poll_interval)

    async def _process_task(self, msg: Dict[str, Any]):
        """Process a prediction task from the communication table."""
        msg_id = msg["id"]
        identifier = msg.get("identifier", "")
        logger.info("Processing task msg_id=%d identifier=%s", msg_id, identifier)

        await self.db.update_message_status(
            msg_id, "processing", processed_by=NEURAL
        )

        try:
            payload = json.loads(msg["payload"]) if msg.get("payload") else {}

            if identifier in ("predict", "neural_predict"):
                symbols = payload.get("symbols", [])
                market = payload.get("market", "US")
                result = await self._predict_symbols(symbols, market)
            else:
                result = {"error": f"Unknown task: {identifier}"}

            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=NEURAL,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "result": result},
            )
            await self.db.update_message_status(
                msg_id, "completed", processed_by=NEURAL
            )

        except Exception as e:
            logger.error("Task msg_id=%d failed: %s", msg_id, e, exc_info=True)
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=NEURAL,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "error": str(e)},
            )
            await self.db.update_message_status(
                msg_id, "failed", processed_by=NEURAL
            )
            await self._publish_health_signal(
                f"Neural prediction failed: {str(e)[:200]}",
                data={"task_identifier": identifier},
            )

    async def _prediction_cycle(self):
        """Run predictions for all watched symbols."""
        logger.info("Starting prediction cycle")

        # Get active US symbols from recent scan tasks or PFC state
        us_symbols = await self._get_active_symbols("US")
        hkex_symbols = await self._get_active_symbols("HKEX")

        predictions = {}

        if us_symbols:
            us_result = await self._predict_symbols(us_symbols, "US")
            predictions.update(us_result)

        if hkex_symbols:
            hkex_result = await self._predict_symbols(hkex_symbols, "HKEX")
            predictions.update(hkex_result)

        if predictions:
            await self._publish_predictions(predictions)
            logger.info("Prediction cycle complete: %d symbols", len(predictions))
        else:
            logger.info("Prediction cycle: no active symbols")

    async def _get_active_symbols(self, market: str) -> List[str]:
        """Get symbols to predict from recent communication or PFC state."""
        # Check for recent scan tasks that mention symbols
        results = await self.db.get_recent_results(
            source="occipital", limit=5, minutes=30
        )
        symbols = set()

        for r in results:
            try:
                payload = json.loads(r["payload"]) if r.get("payload") else {}
                result_data = payload.get("result", {})
                # Extract symbols from occipital scan results
                for match in result_data.get("buy_matches", []):
                    symbols.add(match.get("symbol", ""))
                for match in result_data.get("sell_matches", []):
                    symbols.add(match.get("symbol", ""))
            except (json.JSONDecodeError, KeyError):
                pass

        # Also check PFC state for watchlist
        pfc_state = await self.db.get_pfc_state()
        if pfc_state:
            try:
                state_data = json.loads(pfc_state.get("state_data", "{}"))
                watchlist = state_data.get("watchlist", [])
                symbols.update(watchlist)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        symbols.discard("")
        return list(symbols)

    async def _predict_symbols(
        self, symbols: List[str], market: str
    ) -> Dict[str, Any]:
        """Run inference for a list of symbols."""
        if not symbols:
            return {}

        results = {}

        for symbol in symbols:
            try:
                result = {}

                # Candle model (v0.3 — primary)
                if self.candle_session:
                    candle_result = self._predict_candle(symbol, market)
                    if candle_result:
                        result.update(candle_result)

                # Fused model (legacy — additional horizons)
                if self.fused_session:
                    fused_result = self._predict_fused(symbol, market)
                    if fused_result:
                        # Merge: fused adds 4h, 1d horizons
                        if "returns" in result and "returns" in fused_result:
                            for h in ("4h", "1d"):
                                if h in fused_result["returns"]:
                                    result["returns"][h] = fused_result["returns"][h]
                            result["fused_confidence"] = fused_result.get("confidence", 0)
                        else:
                            result.update(fused_result)

                if result:
                    result["market"] = market
                    result["timestamp"] = datetime.now(timezone.utc).isoformat()
                    results[symbol] = result

            except Exception as e:
                logger.error("Prediction failed for %s: %s", symbol, e)
                results[symbol] = {"error": str(e)}

        return results

    def _predict_candle(self, symbol: str, market: str) -> Optional[Dict]:
        """Run CandleModel inference for a symbol."""
        candle_5m = self._fetch_candles(symbol, market, interval="5m")
        if candle_5m is None:
            return None

        candle_15m = self._fetch_candles(symbol, market, interval="15m")
        if candle_15m is None:
            return None

        dir_logits, pred_returns, confidence = self._infer_candle(candle_5m, candle_15m)

        # Softmax direction logits
        exp_logits = np.exp(dir_logits - dir_logits.max())
        probs = exp_logits / exp_logits.sum()
        direction_idx = int(np.argmax(probs))
        direction = DIRECTION_NAMES[direction_idx]
        direction_prob = float(probs[direction_idx])

        return {
            "direction": direction,
            "direction_probability": round(direction_prob, 4),
            "direction_probs": {
                name: round(float(probs[i]), 4)
                for i, name in enumerate(DIRECTION_NAMES)
            },
            "returns": {
                name: round(float(pred_returns[i]), 4)
                for i, name in enumerate(CANDLE_HORIZON_NAMES)
            },
            "confidence": round(float(confidence), 4),
            "model": "candle_v0.3",
        }

    def _predict_fused(self, symbol: str, market: str) -> Optional[Dict]:
        """Run fused CatalystNet inference for a symbol."""
        candle_arr = self._fetch_candles(symbol, market, interval="5m")
        if candle_arr is None:
            return None

        macro_vec = self._get_macro_vector()
        news_vec = np.zeros(NEWS_FEATURE_DIM, dtype=np.float32)

        pred_returns, confidence = self._infer_fused(candle_arr, macro_vec, news_vec)

        return {
            "returns": {
                name: round(float(pred_returns[i]), 4)
                for i, name in enumerate(HORIZON_NAMES)
            },
            "confidence": round(float(confidence), 4),
            "model": "fused_v0.1",
        }

    def _fetch_candles(self, symbol: str, market: str,
                       interval: str = "5m") -> Optional[np.ndarray]:
        """Fetch recent candles and normalise like training."""
        yahoo_symbol = symbol
        if market == "HKEX":
            yahoo_symbol = f"{symbol.zfill(4)}{HKEX_SUFFIX}"

        # Period depends on interval
        period = "5d" if interval == "5m" else "30d"

        try:
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(period=period, interval=interval)

            if df is None or len(df) < LOOKBACK:
                logger.warning(
                    "%s: insufficient data (%d candles)",
                    symbol, len(df) if df is not None else 0,
                )
                return None

            # Take the most recent LOOKBACK candles
            df = df.tail(LOOKBACK)

            # Normalise like training: % change from first close
            ref_close = df["Close"].iloc[0]
            if ref_close == 0:
                ref_close = 1.0

            arr = np.zeros((LOOKBACK, 5), dtype=np.float32)
            for i, (_, row) in enumerate(df.iterrows()):
                arr[i, 0] = (row["Open"] - ref_close) / ref_close * 100
                arr[i, 1] = (row["High"] - ref_close) / ref_close * 100
                arr[i, 2] = (row["Low"] - ref_close) / ref_close * 100
                arr[i, 3] = (row["Close"] - ref_close) / ref_close * 100
                arr[i, 4] = np.log1p(row["Volume"])

            # Z-score volume
            vol = arr[:, 4]
            vol_std = vol.std()
            if vol_std > 0:
                arr[:, 4] = (vol - vol.mean()) / vol_std

            return arr

        except Exception as e:
            logger.error("Failed to fetch candles for %s: %s", yahoo_symbol, e)
            return None

    def _get_macro_vector(self) -> np.ndarray:
        """Fetch or return cached macro data."""
        now = datetime.now(timezone.utc)

        # Refresh cache every 5 minutes
        if (
            self._macro_cache_time
            and (now - self._macro_cache_time).total_seconds() < 300
            and self._macro_cache
        ):
            return self._build_macro_vec()

        logger.info("Refreshing macro data...")
        self._macro_cache = {}

        for inst in MACRO_INSTRUMENT_ORDER:
            yahoo = MACRO_YAHOO.get(inst)
            if not yahoo:
                continue
            try:
                ticker = yf.Ticker(yahoo)
                hist = ticker.history(period="2d", interval="1d")
                if hist is not None and len(hist) >= 1:
                    current = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                    change_pct = ((current - prev) / prev * 100) if prev != 0 else 0.0
                    self._macro_cache[inst] = {
                        "value": float(current),
                        "change_pct": float(change_pct),
                    }
            except Exception as e:
                logger.debug("Macro fetch failed for %s: %s", inst, e)

        self._macro_cache_time = now
        logger.info("Macro data refreshed: %d/%d instruments",
                     len(self._macro_cache), len(MACRO_INSTRUMENT_ORDER))
        return self._build_macro_vec()

    def _build_macro_vec(self) -> np.ndarray:
        """Build the macro feature vector from cache."""
        vec = np.zeros(NUM_MACRO_FEATURES, dtype=np.float32)
        for idx, inst in enumerate(MACRO_INSTRUMENT_ORDER):
            if inst in self._macro_cache:
                vec[idx * 2] = self._macro_cache[inst]["value"]
                vec[idx * 2 + 1] = self._macro_cache[inst]["change_pct"]
        return vec

    def _infer_candle(
        self, candles_5m: np.ndarray, candles_15m: np.ndarray
    ) -> tuple:
        """Run CandleModel ONNX inference.
        Returns (direction_logits[3], returns[3], confidence)."""
        c5m_batch = candles_5m[np.newaxis, ...]   # (1, 60, 5)
        c15m_batch = candles_15m[np.newaxis, ...]  # (1, 60, 5)

        outputs = self.candle_session.run(
            None,
            {
                "candles_5m": c5m_batch,
                "candles_15m": c15m_batch,
            },
        )

        dir_logits = outputs[0][0]     # (3,)
        pred_returns = outputs[1][0]   # (3,)
        confidence = outputs[2][0][0]  # scalar

        pred_returns = np.clip(pred_returns, -LABEL_CLIP, LABEL_CLIP)
        return dir_logits, pred_returns, confidence

    def _infer_fused(
        self, candles: np.ndarray, macro: np.ndarray, news: np.ndarray
    ) -> tuple:
        """Run fused CatalystNet ONNX inference. Returns (returns[5], confidence)."""
        candles_batch = candles[np.newaxis, ...]  # (1, 60, 5)
        macro_batch = macro[np.newaxis, ...]      # (1, 30)
        news_batch = news[np.newaxis, ...]        # (1, 5005)

        outputs = self.fused_session.run(
            None,
            {
                "candles": candles_batch,
                "macro": macro_batch,
                "news": news_batch,
            },
        )

        pred_returns = outputs[0][0]  # (5,)
        confidence = outputs[1][0][0]  # scalar

        pred_returns = np.clip(pred_returns, -LABEL_CLIP, LABEL_CLIP)
        return pred_returns, confidence

    async def _publish_predictions(self, predictions: Dict[str, Any]):
        """Publish predictions to the signal bus."""
        for symbol, pred in predictions.items():
            if "error" in pred:
                continue

            returns = pred.get("returns", {})
            confidence = pred.get("confidence", 0)
            market = pred.get("market", "US")

            # Use candle model direction if available, else infer from returns
            direction = pred.get("direction", None)
            direction_prob = pred.get("direction_probability", 0)

            if direction is None:
                # Fallback: infer from return predictions
                return_1h = returns.get("1h", 0)
                return_1d = returns.get("1d", 0)
                if abs(return_1h) < 0.05 and abs(return_1d) < 0.05:
                    direction = "neutral"
                elif return_1h > 0:
                    direction = "bullish"
                else:
                    direction = "bearish"

            # Severity based on confidence
            if confidence >= CONFIDENCE_HIGH:
                severity = Severity.INFO
            elif confidence >= CONFIDENCE_MED:
                severity = Severity.OBSERVE
            else:
                severity = Severity.OBSERVE

            # Build readable content
            return_parts = " | ".join(
                f"{k}: {v:+.2f}%" for k, v in returns.items()
            )
            dir_str = f"{direction}"
            if direction_prob > 0:
                dir_str += f" ({direction_prob:.0%})"

            content = (
                f"Neural: {symbol} ({market}) → {dir_str} | "
                f"{return_parts} | conf: {confidence:.1%}"
            )

            await self.db.publish_signal(
                severity=severity,
                domain=SignalDomain.TRADING,
                scope=SignalScope.BROADCAST,
                source=NEURAL,
                content=content,
                data={
                    "symbol": symbol,
                    "market": market,
                    "direction": direction,
                    "direction_probability": direction_prob,
                    "direction_probs": pred.get("direction_probs", {}),
                    "returns": returns,
                    "confidence": confidence,
                    "model": pred.get("model", "unknown"),
                },
                expires_at=(
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).strftime("%Y-%m-%d %H:%M:%S"),
            )

    async def _publish_health_signal(
        self, content: str, data: dict = None
    ):
        """Publish CRITICAL:HEALTH signal when something breaks."""
        try:
            await self.db.publish_signal(
                severity=Severity.CRITICAL,
                domain=SignalDomain.HEALTH,
                scope=SignalScope.BROADCAST,
                source=NEURAL,
                content=content,
                data=data,
            )
        except Exception as e:
            logger.error("Failed to publish health signal: %s", e)

    @staticmethod
    def _any_market_open() -> bool:
        """Check if US or HKEX market is open (with 15 min buffer)."""
        from datetime import time

        markets = {
            "US": {"open": time(9, 30), "close": time(16, 0),
                    "tz": ZoneInfo("America/New_York")},
            "HKEX": {"open": time(9, 30), "close": time(16, 0),
                      "tz": ZoneInfo("Asia/Hong_Kong")},
        }
        for cfg in markets.values():
            now = datetime.now(cfg["tz"])
            if now.weekday() >= 5:
                continue
            buffered_open = datetime.combine(
                now.date(), cfg["open"], tzinfo=cfg["tz"]
            ) - timedelta(minutes=15)
            close = datetime.combine(
                now.date(), cfg["close"], tzinfo=cfg["tz"]
            )
            if buffered_open <= now <= close:
                return True
        return False

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.db:
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=NEURAL,
                target=None,
                msg_type=MessageType.STATUS,
                identifier="neural_offline",
                payload={"status": "offline"},
            )
            await self.db.close()
        logger.info("Neural cortex shutdown complete")


async def main():
    config = AgentConfig.from_env()

    # Model paths from env
    candle_model = os.getenv("CANDLE_MODEL_PATH", "/app/neural/model/candle_model.onnx")
    fused_model = os.getenv("FUSED_MODEL_PATH", "/app/neural/model/catalyst_net.onnx")

    # Legacy env var support
    legacy_path = os.getenv("NEURAL_MODEL_PATH")
    if legacy_path and not os.path.exists(fused_model):
        fused_model = legacy_path

    cortex = NeuralCortex(
        config,
        candle_model_path=candle_model,
        fused_model_path=fused_model,
    )

    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(cortex.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await cortex.initialize()
        await cortex.run()
    except asyncio.CancelledError:
        pass
    finally:
        await cortex.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
