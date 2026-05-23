"""
Cerebellum — Trained Neural Pattern Recognition

The cerebellum handles the routine. Claude AI handles only what requires
genuine reasoning (the 6% principle).

Two models:
  - CandleModel v0.3: Multi-timeframe OHLCV (5m + 15m) -> direction + confidence + returns
  - NewsToSecurityModel: headline + source -> security + direction + confidence

Models are ONNX files deployed from the laptop (neural_claude) via SCP.
If models are not present, the coordinator falls back to LLM-only mode.

Version: 1.2.0 — version-aware inference (v0.3 dual-input; v0.4 stub)
"""

import json
import logging
import os
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("cerebellum")

# Must match training config
LOOKBACK = 60
DIRECTION_NAMES = ["bullish", "bearish", "neutral"]
DEFAULT_VERSION_TUPLE: Tuple[int, int] = (0, 3)


def _parse_version(version_str: str) -> Tuple[int, int]:
    """Parse '0.3.1' or '0.4' -> (major, minor). Returns (0, 3) on failure."""
    try:
        parts = version_str.split(".")
        return (int(parts[0]), int(parts[1]))
    except (AttributeError, ValueError, IndexError):
        return DEFAULT_VERSION_TUPLE


def _normalize_candle_window(candles_arr: np.ndarray) -> np.ndarray:
    """
    Normalize OHLCV window exactly like training.
    OHLC: percent change from first candle's close.
    Volume: log-normalized then z-scored within window.

    Args:
        candles_arr: (N, 5) array of [open, high, low, close, volume]

    Returns:
        (N, 5) normalized array
    """
    arr = candles_arr.copy().astype(np.float32)
    ref_close = arr[0, 3]  # first candle's close
    if ref_close == 0:
        ref_close = 1.0

    # OHLC: percent change from reference
    arr[:, 0] = (arr[:, 0] - ref_close) / ref_close * 100
    arr[:, 1] = (arr[:, 1] - ref_close) / ref_close * 100
    arr[:, 2] = (arr[:, 2] - ref_close) / ref_close * 100
    arr[:, 3] = (arr[:, 3] - ref_close) / ref_close * 100

    # Volume: log-normalize then z-score
    arr[:, 4] = np.log1p(arr[:, 4])
    vol = arr[:, 4]
    vol_std = vol.std()
    if vol_std > 0:
        arr[:, 4] = (vol - vol.mean()) / vol_std

    return arr


class CandleModel:
    """
    CandleModel — Multi-timeframe direction classifier.

    Version-aware inference:
      - v0.3.x: 2 inputs (candles_5m, candles_15m) -> direction, returns, confidence
      - v0.4.x: 4 inputs (+ news_context, security_context). NOT YET IMPLEMENTED —
        see Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md
        Phase 9. The v0.4 ONNX has not shipped from catalyst-neural yet (Phase 1
        schema migration only as of 2026-05-23); this stub fails loudly to make the
        transition explicit when it does land.
    """

    def __init__(self, model_path: str, version: Tuple[int, int] = DEFAULT_VERSION_TUPLE):
        self.model_path = model_path
        self.version = version
        self.loaded = False
        self.session = None
        self._load()

    def _load(self):
        if not os.path.isfile(self.model_path):
            logger.info(f"CandleModel: No model at {self.model_path}")
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"],
            )
            inputs = {i.name: i.shape for i in self.session.get_inputs()}
            self.loaded = True
            logger.info(
                f"CandleModel: Loaded from {self.model_path} "
                f"— version={self.version[0]}.{self.version[1]} — inputs: {inputs}"
            )
            # Sanity check: input count should match declared version
            input_count = len(self.session.get_inputs())
            if self.version[1] >= 4 and input_count < 4:
                logger.warning(
                    f"CandleModel: manifest says v0.{self.version[1]} but ONNX has "
                    f"{input_count} inputs (expected 4). Inference will likely fail."
                )
            elif self.version[1] < 4 and input_count >= 4:
                logger.warning(
                    f"CandleModel: manifest says v0.{self.version[1]} but ONNX has "
                    f"{input_count} inputs. Manifest may be stale."
                )
        except ImportError:
            logger.warning("CandleModel: onnxruntime not installed")
        except Exception as e:
            logger.error(f"CandleModel: Failed to load: {e}")

    def predict(self, candles_5m, candles_15m=None, **kwargs) -> dict:
        """
        Run inference on candle sequences. Branches on model version.

        Args:
            candles_5m: List of dicts with OHLCV keys, or numpy array (N, 5)
            candles_15m: Same format for 15m timeframe. If None, uses candles_5m for both.
            **kwargs: v0.4 will accept symbol=, news_window=, etc. Ignored for v0.3.

        Returns:
            dict with: direction, confidence, probabilities, predicted returns
        """
        if not self.loaded or not self.session:
            return {"available": False, "reason": "model not loaded"}

        if self.version[1] >= 4:
            return self._predict_v04(candles_5m, candles_15m, **kwargs)
        return self._predict_v03(candles_5m, candles_15m)

    def _predict_v03(self, candles_5m, candles_15m) -> dict:
        """v0.3 inference path: 2 inputs (5m + 15m candles)."""
        try:
            # Convert to numpy arrays
            arr_5m = self._to_array(candles_5m)
            arr_15m = self._to_array(candles_15m) if candles_15m is not None else arr_5m.copy()

            # Pad/trim to LOOKBACK
            arr_5m = self._pad_to_lookback(arr_5m)
            arr_15m = self._pad_to_lookback(arr_15m)

            # Normalize like training
            norm_5m = _normalize_candle_window(arr_5m)
            norm_15m = _normalize_candle_window(arr_15m)

            # Add batch dimension: (1, LOOKBACK, 5)
            batch_5m = norm_5m.reshape(1, LOOKBACK, 5)
            batch_15m = norm_15m.reshape(1, LOOKBACK, 5)

            # Run inference
            outputs = self.session.run(None, {
                "candles_5m": batch_5m,
                "candles_15m": batch_15m,
            })

            dir_logits = outputs[0][0]   # (3,)
            pred_returns = outputs[1][0]  # (3,)
            confidence = outputs[2][0][0] # scalar

            # Softmax direction logits
            exp_logits = np.exp(dir_logits - dir_logits.max())
            probs = exp_logits / exp_logits.sum()
            idx = int(np.argmax(probs))

            result = {
                "available": True,
                "direction": DIRECTION_NAMES[idx],
                "confidence": round(float(confidence), 4),
                "direction_probability": round(float(probs[idx]), 4),
                "probabilities": {
                    d: round(float(p), 4)
                    for d, p in zip(DIRECTION_NAMES, probs)
                },
                "predicted_return_5m": round(float(pred_returns[0]), 6),
                "predicted_return_15m": round(float(pred_returns[1]), 6),
                "predicted_return_1h": round(float(pred_returns[2]), 6),
            }

            return result

        except Exception as e:
            logger.error(f"CandleModel v0.3 inference error: {e}")
            return {"available": False, "reason": str(e)}

    def _predict_v04(self, candles_5m, candles_15m, **kwargs) -> dict:
        """
        v0.4 context-conditioned inference path. Adds news_context (16-dim) and
        security_context (18-dim) to the ONNX call.

        STUB — not yet implemented. The v0.4 ONNX has not shipped from catalyst-neural;
        catalyst-neural is at Phase 1 (schema migration) as of 2026-05-23. Implement
        this when v0.4 model lands. See:
          - Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md §11
          - Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md Phase 9
        """
        logger.error(
            "CandleModel v0.4 inference invoked but path is not implemented. "
            "Falling back to no-signal. Implement _predict_v04 (news_context + "
            "security_context builders + 4-input session.run) per design doc §11."
        )
        return {
            "available": False,
            "reason": "v0.4 inference path not implemented (stub)",
            "model_version": f"{self.version[0]}.{self.version[1]}",
        }

    @staticmethod
    def _to_array(candles) -> np.ndarray:
        """Convert list of dicts or array to numpy (N, 5)."""
        if isinstance(candles, np.ndarray):
            return candles.astype(np.float32)
        return np.array([
            [c.get("open", 0), c.get("high", 0), c.get("low", 0),
             c.get("close", 0), c.get("volume", 0)]
            for c in candles
        ], dtype=np.float32)

    @staticmethod
    def _pad_to_lookback(arr: np.ndarray) -> np.ndarray:
        """Pad or trim array to exactly LOOKBACK rows."""
        if arr.shape[0] >= LOOKBACK:
            return arr[-LOOKBACK:]
        # Pad front with first row repeated
        pad_count = LOOKBACK - arr.shape[0]
        padding = np.tile(arr[0:1], (pad_count, 1))
        return np.vstack([padding, arr])


class NewsToSecurityModel:
    """
    News-to-security classifier using ONNX inference.

    Input:  headline text, source tier, timestamp
    Output: security symbol, direction, confidence
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.loaded = False
        self.session = None
        self._load()

    def _load(self):
        if not os.path.isfile(self.model_path):
            logger.info(f"NewsToSecurityModel: No model at {self.model_path}")
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"],
            )
            self.loaded = True
            logger.info(f"NewsToSecurityModel: Loaded from {self.model_path}")
        except ImportError:
            logger.warning("NewsToSecurityModel: onnxruntime not installed")
        except Exception as e:
            logger.error(f"NewsToSecurityModel: Failed to load: {e}")

    def predict(self, headline: str, source_tier: int = 3, timestamp: str = "") -> dict:
        """
        Run inference on a news headline.

        Returns:
            dict with: security, direction, confidence
        """
        if not self.loaded or not self.session:
            return {"available": False, "reason": "model not loaded"}

        try:
            tokens = np.array([ord(c) for c in headline[:256]], dtype=np.float32)
            padded = np.zeros(256, dtype=np.float32)
            padded[:len(tokens)] = tokens[:256]
            input_data = np.concatenate([padded, [float(source_tier)]]).reshape(1, -1)

            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: input_data})

            result = {
                "available": True,
                "raw_output": [float(x) for x in outputs[0][0][:5]],
                "confidence": round(float(np.max(outputs[0][0])), 4),
            }

            if len(outputs) > 1:
                direction_probs = outputs[1][0]
                result["direction"] = "bullish" if direction_probs[0] > direction_probs[1] else "bearish"
                result["direction_confidence"] = round(float(max(direction_probs)), 4)

            return result

        except Exception as e:
            logger.error(f"NewsToSecurityModel inference error: {e}")
            return {"available": False, "reason": str(e)}


class Cerebellum:
    """
    The cerebellum: fast, automatic pattern recognition. No tokens. No API calls.

    Loads ONNX models from a configured directory. If models are missing,
    the coordinator falls back to LLM-only mode gracefully.
    """

    DEFAULT_MODELS_PATH = "/app/models"

    def __init__(self, models_path: Optional[str] = None):
        self.models_path = models_path or os.getenv(
            "CEREBELLUM_MODELS_PATH", self.DEFAULT_MODELS_PATH
        )
        # Load manifest first so CandleModel knows which inference path to use.
        self._version = self._load_version()
        candle_version = _parse_version(self._version.get("version", ""))
        logger.info(
            f"Cerebellum: model_version.json reports {self._version.get('version', 'unknown')} "
            f"-> using v0.{candle_version[1]} inference path"
        )
        self.candle_model = CandleModel(
            os.path.join(self.models_path, "candle_model.onnx"),
            version=candle_version,
        )
        self.news_model = NewsToSecurityModel(
            os.path.join(self.models_path, "news_model.onnx")
        )

    def _load_version(self) -> dict:
        version_path = os.path.join(self.models_path, "model_version.json")
        try:
            with open(version_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"version": "unknown", "deployed_at": "unknown"}

    def is_loaded(self) -> bool:
        """True if at least one model is loaded and ready for inference."""
        return self.candle_model.loaded or self.news_model.loaded

    def status(self) -> dict:
        return {
            "candle_model": self.candle_model.loaded,
            "news_model": self.news_model.loaded,
            "models_path": self.models_path,
            "version": self._version,
        }
