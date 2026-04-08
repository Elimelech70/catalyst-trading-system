"""
Catalyst Neural — ONNX Export

Exports trained PyTorch models to ONNX format for CPU inference on the droplet.
"""

import torch
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import MODELS_DIR, TRAINING


def export_candle_model(checkpoint_path, output_path=None):
    """
    Export CandleModel checkpoint to ONNX.

    Args:
        checkpoint_path: Path to .pt checkpoint
        output_path: Output .onnx path (default: models/candle_model.onnx)
    """
    from training.models import CandleModel

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        print(f"ERROR: Checkpoint not found: {checkpoint_path}")
        return None

    if output_path is None:
        output_path = MODELS_DIR / "candle_model.onnx"
    else:
        output_path = Path(output_path)

    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

    model = CandleModel()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print(f"Model parameters: {model.count_parameters():,}")

    lookback = TRAINING["lookback_candles"]
    dummy_5m = torch.randn(1, lookback, 5)
    dummy_15m = torch.randn(1, lookback, 5)

    print(f"Exporting to ONNX: {output_path}")
    torch.onnx.export(
        model,
        (dummy_5m, dummy_15m),
        str(output_path),
        input_names=["candles_5m", "candles_15m"],
        output_names=["direction_logits", "pred_returns", "confidence"],
        dynamic_axes={
            "candles_5m": {0: "batch"},
            "candles_15m": {0: "batch"},
            "direction_logits": {0: "batch"},
            "pred_returns": {0: "batch"},
            "confidence": {0: "batch"},
        },
        opset_version=17,
    )

    # Check for external data file
    data_file = Path(str(output_path) + ".data")
    if data_file.exists():
        print(f"External data: {data_file} ({data_file.stat().st_size / 1024:.1f} KB)")

    onnx_size = output_path.stat().st_size
    print(f"ONNX model: {output_path} ({onnx_size / 1024:.1f} KB)")

    # Verify with onnxruntime
    try:
        import onnxruntime as ort
        import numpy as np

        sess = ort.InferenceSession(str(output_path))
        result = sess.run(None, {
            "candles_5m": np.random.randn(1, lookback, 5).astype(np.float32),
            "candles_15m": np.random.randn(1, lookback, 5).astype(np.float32),
        })
        dir_logits, pred_returns, confidence = result
        print(f"\nVerification passed:")
        print(f"  direction_logits: {dir_logits.shape} — {dir_logits[0]}")
        print(f"  pred_returns:     {pred_returns.shape} — {pred_returns[0]}")
        print(f"  confidence:       {confidence.shape} — {confidence[0]}")
    except ImportError:
        print("(onnxruntime not installed — skipping verification)")

    return output_path


def export_fused_model(checkpoint_path, output_path=None):
    """
    Export fused CatalystNet checkpoint to ONNX.

    Args:
        checkpoint_path: Path to .pt checkpoint
        output_path: Output .onnx path (default: models/catalyst_net.onnx)
    """
    from training.models import CatalystNet
    from training.dataset import NUM_MACRO_FEATURES, NEWS_FEATURE_DIM

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        print(f"ERROR: Checkpoint not found: {checkpoint_path}")
        return None

    if output_path is None:
        output_path = MODELS_DIR / "catalyst_net.onnx"
    else:
        output_path = Path(output_path)

    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

    model = CatalystNet()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print(f"Model parameters: {model.count_parameters():,}")

    lookback = TRAINING["lookback_candles"]
    dummy_candles = torch.randn(1, lookback, 5)
    dummy_macro = torch.randn(1, NUM_MACRO_FEATURES)
    dummy_news = torch.randn(1, NEWS_FEATURE_DIM)

    print(f"Exporting to ONNX: {output_path}")
    torch.onnx.export(
        model,
        (dummy_candles, dummy_macro, dummy_news),
        str(output_path),
        input_names=["candles", "macro", "news"],
        output_names=["returns", "confidence"],
        dynamic_axes={
            "candles": {0: "batch"},
            "macro": {0: "batch"},
            "news": {0: "batch"},
            "returns": {0: "batch"},
            "confidence": {0: "batch"},
        },
        opset_version=17,
    )

    data_file = Path(str(output_path) + ".data")
    if data_file.exists():
        print(f"External data: {data_file} ({data_file.stat().st_size / 1024:.1f} KB)")

    onnx_size = output_path.stat().st_size
    print(f"ONNX model: {output_path} ({onnx_size / 1024:.1f} KB)")
    return output_path
