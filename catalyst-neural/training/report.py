"""
Catalyst Neural — Training Report Generator

Produces a comprehensive HTML report after each training run.
Includes: loss curves, per-horizon analysis, prediction scatter plots,
baseline comparison, confidence calibration, per-security breakdown,
and error distributions.
"""

import json
import base64
import io
import numpy as np
import torch
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import MODELS_DIR


HORIZON_NAMES = ["5m", "15m", "1h", "4h", "1d"]
CANDLE_HORIZON_NAMES = ["5m", "15m", "1h"]
DIRECTION_NAMES = ["Bullish", "Bearish", "Neutral"]


def _fig_to_base64(fig):
    """Convert matplotlib figure to base64-encoded PNG for embedding in HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _generate_plots(history, val_predictions, val_labels, val_masks,
                    val_confidences, val_symbols):
    """Generate all report charts. Returns dict of name -> base64 PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots = {}

    # ── 1. Loss Curves ──
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    epochs = range(1, len(history["train_loss"]) + 1)
    ax1.plot(epochs, history["train_loss"], label="Train", linewidth=2)
    ax1.plot(epochs, history["val_loss"], label="Validation", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs, history["lr"], label="Learning Rate", color="orange", linewidth=2)
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Learning Rate")
    ax2.set_title("Learning Rate Schedule")
    ax2.set_yscale("log")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plots["loss_curves"] = _fig_to_base64(fig)
    plt.close()

    # ── 2. Per-Horizon MAE Bar Chart ──
    horizon_mae = []
    baseline_mae = []
    for h in range(5):
        mask_h = val_masks[:, h] > 0
        if mask_h.sum() > 0:
            pred_h = val_predictions[mask_h, h]
            label_h = val_labels[mask_h, h]
            horizon_mae.append(np.mean(np.abs(pred_h - label_h)))
            baseline_mae.append(np.mean(np.abs(label_h)))  # "predict zero" baseline
        else:
            horizon_mae.append(0)
            baseline_mae.append(0)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(5)
    w = 0.35
    ax.bar(x - w / 2, horizon_mae, w, label="Model MAE", color="#2196F3")
    ax.bar(x + w / 2, baseline_mae, w, label="Baseline MAE (predict 0)", color="#FF9800", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(HORIZON_NAMES)
    ax.set_ylabel("Mean Absolute Error (%)")
    ax.set_title("Per-Horizon: Model vs Naive Baseline")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    for i, (m, b) in enumerate(zip(horizon_mae, baseline_mae)):
        improvement = ((b - m) / b * 100) if b > 0 else 0
        ax.text(i, max(m, b) + 0.05, f"{improvement:+.0f}%", ha="center", fontsize=9, fontweight="bold")
    plt.tight_layout()
    plots["horizon_mae"] = _fig_to_base64(fig)
    plt.close()

    # ── 3. Prediction vs Actual Scatter (per horizon) ──
    fig, axes = plt.subplots(1, 5, figsize=(20, 4))
    for h, ax in enumerate(axes):
        mask_h = val_masks[:, h] > 0
        if mask_h.sum() == 0:
            ax.set_title(f"{HORIZON_NAMES[h]} (no data)")
            continue
        pred_h = val_predictions[mask_h, h]
        label_h = val_labels[mask_h, h]

        # Subsample for readability
        n = min(2000, len(pred_h))
        idx = np.random.choice(len(pred_h), n, replace=False)

        ax.scatter(label_h[idx], pred_h[idx], alpha=0.15, s=8, color="#2196F3")
        lims = [min(label_h[idx].min(), pred_h[idx].min()),
                max(label_h[idx].max(), pred_h[idx].max())]
        ax.plot(lims, lims, "r--", linewidth=1, alpha=0.7)
        ax.set_xlabel("Actual (%)")
        ax.set_ylabel("Predicted (%)")
        ax.set_title(f"{HORIZON_NAMES[h]}")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.2)

        # R-squared
        ss_res = np.sum((label_h - pred_h) ** 2)
        ss_tot = np.sum((label_h - label_h.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        ax.text(0.05, 0.95, f"R²={r2:.3f}", transform=ax.transAxes,
                fontsize=9, va="top", fontweight="bold")

    plt.suptitle("Predicted vs Actual Forward Returns", y=1.02)
    plt.tight_layout()
    plots["scatter"] = _fig_to_base64(fig)
    plt.close()

    # ── 4. Error Distribution Histograms ──
    fig, axes = plt.subplots(1, 5, figsize=(20, 4))
    for h, ax in enumerate(axes):
        mask_h = val_masks[:, h] > 0
        if mask_h.sum() == 0:
            continue
        errors = val_predictions[mask_h, h] - val_labels[mask_h, h]
        ax.hist(errors, bins=50, color="#4CAF50", alpha=0.7, edgecolor="white")
        ax.axvline(0, color="red", linestyle="--", linewidth=1)
        ax.set_xlabel("Prediction Error (%)")
        ax.set_title(f"{HORIZON_NAMES[h]} (μ={errors.mean():.3f}, σ={errors.std():.3f})")
        ax.grid(True, alpha=0.2)
    plt.suptitle("Error Distributions", y=1.02)
    plt.tight_layout()
    plots["error_dist"] = _fig_to_base64(fig)
    plt.close()

    # ── 5. Confidence Calibration ──
    if val_confidences is not None and len(val_confidences) > 0:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Confidence vs absolute error
        mean_abs_err = np.zeros(len(val_confidences))
        for h in range(5):
            mask_h = val_masks[:, h] > 0
            err = np.abs(val_predictions[:, h] - val_labels[:, h])
            err[~mask_h] = 0
            mean_abs_err += err
        counts = val_masks.sum(axis=1).clip(min=1)
        mean_abs_err /= counts
        conf = val_confidences.squeeze()

        # Bin by confidence deciles
        n_bins = 10
        bin_edges = np.linspace(conf.min(), conf.max(), n_bins + 1)
        bin_mae = []
        bin_centers = []
        for i in range(n_bins):
            in_bin = (conf >= bin_edges[i]) & (conf < bin_edges[i + 1])
            if in_bin.sum() > 0:
                bin_mae.append(mean_abs_err[in_bin].mean())
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

        ax1.bar(bin_centers, bin_mae, width=(bin_edges[1] - bin_edges[0]) * 0.8,
                color="#9C27B0", alpha=0.7)
        ax1.set_xlabel("Model Confidence")
        ax1.set_ylabel("Mean Absolute Error (%)")
        ax1.set_title("Confidence vs Error (lower error at higher conf = good)")
        ax1.grid(True, alpha=0.3)

        # Confidence distribution
        ax2.hist(conf, bins=50, color="#9C27B0", alpha=0.7, edgecolor="white")
        ax2.set_xlabel("Confidence Score")
        ax2.set_ylabel("Count")
        ax2.set_title("Confidence Distribution")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plots["confidence"] = _fig_to_base64(fig)
        plt.close()

    # ── 6. Per-Security Performance ──
    if val_symbols is not None:
        unique_symbols = sorted(set(val_symbols))
        if len(unique_symbols) > 1:
            sym_mae = {}
            for sym in unique_symbols:
                idx = np.array([i for i, s in enumerate(val_symbols) if s == sym])
                if len(idx) < 10:
                    continue
                # Use 1h horizon (index 2) as representative
                mask_h = val_masks[idx, 2] > 0
                if mask_h.sum() > 0:
                    errs = np.abs(val_predictions[idx[mask_h], 2] - val_labels[idx[mask_h], 2])
                    sym_mae[sym] = errs.mean()

            if sym_mae:
                sorted_syms = sorted(sym_mae.items(), key=lambda x: x[1])
                names = [s[0] for s in sorted_syms[:30]]
                vals = [s[1] for s in sorted_syms[:30]]

                fig, ax = plt.subplots(figsize=(12, max(5, len(names) * 0.3)))
                colors = ["#4CAF50" if v < np.median(vals) else "#FF5722" for v in vals]
                ax.barh(names, vals, color=colors, alpha=0.8)
                ax.set_xlabel("1h Horizon MAE (%)")
                ax.set_title("Per-Security Performance (1h horizon, sorted by MAE)")
                ax.grid(True, alpha=0.2, axis="x")
                plt.tight_layout()
                plots["per_security"] = _fig_to_base64(fig)
                plt.close()

    return plots


def generate_report(model, val_loader, history, run_id, config, dataset_info,
                    device="cpu"):
    """
    Run full validation pass, generate all analytics, and produce an HTML report.

    Args:
        model: trained CatalystNet (best checkpoint loaded)
        val_loader: validation DataLoader
        history: dict with train_loss, val_loss, val_mae, lr lists
        run_id: training run identifier
        config: training config dict
        dataset_info: dict from get_dataloaders
        device: torch device string

    Returns:
        Path to the saved HTML report
    """
    print("\nGenerating training report...")
    device = torch.device(device)
    model = model.to(device)
    model.eval()

    # ── Collect all validation predictions ──
    all_preds = []
    all_labels = []
    all_masks = []
    all_confs = []
    all_symbols = []

    with torch.no_grad():
        for batch in val_loader:
            candles = batch["candles"].to(device)
            macro = batch["macro"].to(device)
            news = batch["news"].to(device)

            pred_returns, confidence = model(candles, macro, news)

            all_preds.append(pred_returns.cpu().numpy())
            all_labels.append(batch["labels"].numpy())
            all_masks.append(batch["label_mask"].numpy())
            all_confs.append(confidence.cpu().numpy())

    val_preds = np.concatenate(all_preds, axis=0)
    val_labels = np.concatenate(all_labels, axis=0)
    val_masks = np.concatenate(all_masks, axis=0)
    val_confs = np.concatenate(all_confs, axis=0)

    # Get symbols from the dataset for per-security analysis
    val_symbols = None
    if hasattr(val_loader.dataset, "samples"):
        val_symbols = [s[0] for s in val_loader.dataset.samples[:len(val_preds)]]

    # ── Compute stats ──
    horizon_stats = []
    for h in range(5):
        mask_h = val_masks[:, h] > 0
        n_valid = int(mask_h.sum())
        if n_valid > 0:
            pred_h = val_preds[mask_h, h]
            label_h = val_labels[mask_h, h]
            errors = pred_h - label_h
            abs_errors = np.abs(errors)
            baseline_mae = np.mean(np.abs(label_h))
            model_mae = np.mean(abs_errors)

            ss_res = np.sum(errors ** 2)
            ss_tot = np.sum((label_h - label_h.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            improvement = ((baseline_mae - model_mae) / baseline_mae * 100) if baseline_mae > 0 else 0

            # Direction accuracy: does model predict correct sign?
            correct_dir = np.sum((pred_h > 0) == (label_h > 0))
            dir_acc = correct_dir / n_valid * 100

            horizon_stats.append({
                "name": HORIZON_NAMES[h],
                "samples": n_valid,
                "model_mae": model_mae,
                "baseline_mae": baseline_mae,
                "improvement": improvement,
                "r_squared": r2,
                "mean_error": errors.mean(),
                "std_error": errors.std(),
                "direction_accuracy": dir_acc,
            })
        else:
            horizon_stats.append({
                "name": HORIZON_NAMES[h], "samples": 0,
                "model_mae": 0, "baseline_mae": 0, "improvement": 0,
                "r_squared": 0, "mean_error": 0, "std_error": 0,
                "direction_accuracy": 50,
            })

    # ── Generate plots ──
    plots = _generate_plots(history, val_preds, val_labels, val_masks,
                            val_confs, val_symbols)

    # ── Build HTML ──
    report_html = _build_html(run_id, config, dataset_info, history,
                              horizon_stats, plots)

    # ── Save ──
    report_path = MODELS_DIR / f"report_{run_id}.html"
    with open(report_path, "w") as f:
        f.write(report_html)

    # Also save the raw stats as JSON
    stats_path = MODELS_DIR / f"report_stats_{run_id}.json"
    with open(stats_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "horizon_stats": horizon_stats,
            "dataset_info": dataset_info,
            "config": config,
        }, f, indent=2, default=str)

    print(f"Report saved: {report_path}")
    print(f"Stats saved:  {stats_path}")
    return report_path


def _build_html(run_id, config, dataset_info, history, horizon_stats, plots):
    """Assemble the HTML report."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Summary table rows
    best_epoch = int(np.argmin(history["val_loss"])) + 1
    best_val = min(history["val_loss"])
    final_train = history["train_loss"][-1]
    epochs_trained = len(history["train_loss"])

    # Horizon table rows
    horizon_rows = ""
    for s in horizon_stats:
        color = "#4CAF50" if s["improvement"] > 0 else "#FF5722"
        dir_color = "#4CAF50" if s["direction_accuracy"] > 55 else ("#FF9800" if s["direction_accuracy"] > 50 else "#FF5722")
        horizon_rows += f"""
        <tr>
            <td><strong>{s['name']}</strong></td>
            <td>{s['samples']:,}</td>
            <td>{s['model_mae']:.4f}%</td>
            <td>{s['baseline_mae']:.4f}%</td>
            <td style="color:{color};font-weight:bold">{s['improvement']:+.1f}%</td>
            <td>{s['r_squared']:.4f}</td>
            <td style="color:{dir_color};font-weight:bold">{s['direction_accuracy']:.1f}%</td>
            <td>{s['mean_error']:+.4f}%</td>
            <td>{s['std_error']:.4f}%</td>
        </tr>"""

    # Build image tags
    def img(key, alt=""):
        if key in plots:
            return f'<img src="data:image/png;base64,{plots[key]}" alt="{alt}" style="width:100%;max-width:1200px;">'
        return f'<p><em>{alt} — no data</em></p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Catalyst Neural — Training Report {run_id}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           max-width: 1300px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #333; }}
    h1 {{ border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
    h2 {{ color: #1565C0; margin-top: 40px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px; margin: 20px 0; }}
    .card {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .card .label {{ font-size: 0.85em; color: #666; margin-bottom: 4px; }}
    .card .value {{ font-size: 1.4em; font-weight: bold; color: #1565C0; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px;
             overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    th {{ background: #1565C0; color: white; padding: 10px 12px; text-align: left; font-size: 0.9em; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }}
    tr:hover {{ background: #f0f7ff; }}
    .chart {{ background: white; border-radius: 8px; padding: 15px; margin: 15px 0;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
    .footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd;
               color: #999; font-size: 0.85em; }}
    .verdict {{ background: white; border-left: 4px solid #2196F3; padding: 15px;
                margin: 20px 0; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
</style>
</head>
<body>

<h1>Catalyst Neural — Training Report</h1>
<p>Run <strong>{run_id}</strong> &mdash; {timestamp}</p>

<h2>Summary</h2>
<div class="summary">
    <div class="card">
        <div class="label">Training Samples</div>
        <div class="value">{dataset_info.get('train_samples', 0):,}</div>
    </div>
    <div class="card">
        <div class="label">Validation Samples</div>
        <div class="value">{dataset_info.get('val_samples', 0):,}</div>
    </div>
    <div class="card">
        <div class="label">Securities</div>
        <div class="value">{dataset_info.get('securities', 0)}</div>
    </div>
    <div class="card">
        <div class="label">Best Val Loss</div>
        <div class="value">{best_val:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Best Epoch</div>
        <div class="value">{best_epoch} / {epochs_trained}</div>
    </div>
    <div class="card">
        <div class="label">Final Train Loss</div>
        <div class="value">{final_train:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Overfit Ratio</div>
        <div class="value">{best_val / final_train:.2f}x</div>
    </div>
    <div class="card">
        <div class="label">Batch / LR / Device</div>
        <div class="value" style="font-size:1em">{config.get('batch_size',64)} / {config.get('learning_rate',1e-3)} / {config.get('device','?')}</div>
    </div>
</div>

<h2>Per-Horizon Performance</h2>
<table>
<tr>
    <th>Horizon</th><th>Samples</th><th>Model MAE</th><th>Baseline MAE</th>
    <th>vs Baseline</th><th>R&sup2;</th><th>Direction Acc</th><th>Mean Error</th><th>Std Error</th>
</tr>
{horizon_rows}
</table>

<div class="verdict">
<strong>Key metrics:</strong>
<ul>
    <li><strong>vs Baseline</strong> — positive means model beats naive "predict zero". Negative means it's worse than doing nothing.</li>
    <li><strong>Direction Accuracy</strong> — does the model predict the correct direction (up/down)? &gt;55% is meaningful signal.</li>
    <li><strong>R&sup2;</strong> — 0 = no better than mean prediction. Closer to 1 = stronger fit. Can be negative if model is bad.</li>
</ul>
</div>

<h2>Training Curves</h2>
<div class="chart">{img("loss_curves", "Loss Curves")}</div>

<h2>Model vs Baseline (per horizon)</h2>
<div class="chart">{img("horizon_mae", "Horizon MAE Comparison")}</div>

<h2>Predicted vs Actual</h2>
<div class="chart">{img("scatter", "Prediction Scatter")}</div>

<h2>Error Distributions</h2>
<div class="chart">{img("error_dist", "Error Histograms")}</div>

<h2>Confidence Calibration</h2>
<div class="chart">{img("confidence", "Confidence Analysis")}</div>

<h2>Per-Security Performance</h2>
<div class="chart">{img("per_security", "Per-Security MAE")}</div>

<div class="footer">
    Catalyst Neural v0.1.0 &mdash; Craig + Claude &mdash; {timestamp}
</div>

</body>
</html>"""


# =============================================================================
# v0.3 — Candle Model Report
# =============================================================================


def _generate_candle_plots(history, val_dir_preds, val_dir_labels,
                           val_predictions, val_labels, val_masks,
                           val_confidences, val_symbols):
    """Generate candle model report charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots = {}

    # ── 1. Loss + Direction Accuracy Curves ──
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))
    epochs = range(1, len(history["train_loss"]) + 1)

    ax1.plot(epochs, history["train_loss"], label="Train", linewidth=2)
    ax1.plot(epochs, history["val_loss"], label="Validation", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs, history["val_dir_acc"], label="Val Direction Acc", color="green", linewidth=2)
    ax2.axhline(y=33.3, color="red", linestyle="--", alpha=0.5, label="Random (33.3%)")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Accuracy (%)")
    ax2.set_title("Direction Classification Accuracy")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3.plot(epochs, history["lr"], label="Learning Rate", color="orange", linewidth=2)
    ax3.set_xlabel("Epoch")
    ax3.set_ylabel("LR")
    ax3.set_title("Learning Rate Schedule")
    ax3.set_yscale("log")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plots["loss_curves"] = _fig_to_base64(fig)
    plt.close()

    # ── 2. Direction Confusion Matrix ──
    from collections import Counter
    n_classes = 3
    confusion = np.zeros((n_classes, n_classes), dtype=int)
    for true, pred in zip(val_dir_labels, val_dir_preds):
        confusion[true, pred] += 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    im = ax1.imshow(confusion, cmap="Blues")
    ax1.set_xticks(range(n_classes))
    ax1.set_yticks(range(n_classes))
    ax1.set_xticklabels(DIRECTION_NAMES)
    ax1.set_yticklabels(DIRECTION_NAMES)
    ax1.set_xlabel("Predicted")
    ax1.set_ylabel("Actual")
    ax1.set_title("Direction Confusion Matrix")
    for i in range(n_classes):
        for j in range(n_classes):
            ax1.text(j, i, str(confusion[i, j]), ha="center", va="center",
                     color="white" if confusion[i, j] > confusion.max() / 2 else "black")
    fig.colorbar(im, ax=ax1)

    # Per-class accuracy bar chart
    class_acc = []
    for c in range(n_classes):
        total_c = confusion[c].sum()
        class_acc.append(confusion[c, c] / total_c * 100 if total_c > 0 else 0)

    colors = ["#4CAF50" if a > 33.3 else "#FF5722" for a in class_acc]
    ax2.bar(DIRECTION_NAMES, class_acc, color=colors, alpha=0.8)
    ax2.axhline(y=33.3, color="red", linestyle="--", alpha=0.5, label="Random")
    ax2.set_ylabel("Accuracy (%)")
    ax2.set_title("Per-Class Direction Accuracy")
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis="y")
    for i, v in enumerate(class_acc):
        ax2.text(i, v + 1, f"{v:.1f}%", ha="center", fontweight="bold")

    plt.tight_layout()
    plots["confusion"] = _fig_to_base64(fig)
    plt.close()

    # ── 3. Per-Horizon MAE Bar Chart ──
    horizon_mae = []
    baseline_mae = []
    for h in range(3):
        mask_h = val_masks[:, h] > 0
        if mask_h.sum() > 0:
            pred_h = val_predictions[mask_h, h]
            label_h = val_labels[mask_h, h]
            horizon_mae.append(np.mean(np.abs(pred_h - label_h)))
            baseline_mae.append(np.mean(np.abs(label_h)))
        else:
            horizon_mae.append(0)
            baseline_mae.append(0)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(3)
    w = 0.35
    ax.bar(x - w / 2, horizon_mae, w, label="Model MAE", color="#2196F3")
    ax.bar(x + w / 2, baseline_mae, w, label="Baseline (predict 0)", color="#FF9800", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(CANDLE_HORIZON_NAMES)
    ax.set_ylabel("MAE (%)")
    ax.set_title("Per-Horizon: Model vs Baseline")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    for i, (m, b) in enumerate(zip(horizon_mae, baseline_mae)):
        improvement = ((b - m) / b * 100) if b > 0 else 0
        ax.text(i, max(m, b) + 0.02, f"{improvement:+.0f}%", ha="center", fontsize=9, fontweight="bold")
    plt.tight_layout()
    plots["horizon_mae"] = _fig_to_base64(fig)
    plt.close()

    # ── 4. Prediction vs Actual Scatter ──
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for h, ax in enumerate(axes):
        mask_h = val_masks[:, h] > 0
        if mask_h.sum() == 0:
            ax.set_title(f"{CANDLE_HORIZON_NAMES[h]} (no data)")
            continue
        pred_h = val_predictions[mask_h, h]
        label_h = val_labels[mask_h, h]
        n = min(2000, len(pred_h))
        idx = np.random.choice(len(pred_h), n, replace=False)
        ax.scatter(label_h[idx], pred_h[idx], alpha=0.15, s=8, color="#2196F3")
        lims = [min(label_h[idx].min(), pred_h[idx].min()),
                max(label_h[idx].max(), pred_h[idx].max())]
        ax.plot(lims, lims, "r--", linewidth=1, alpha=0.7)
        ax.set_xlabel("Actual (%)")
        ax.set_ylabel("Predicted (%)")
        ax.set_title(CANDLE_HORIZON_NAMES[h])
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.2)
        ss_res = np.sum((label_h - pred_h) ** 2)
        ss_tot = np.sum((label_h - label_h.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        ax.text(0.05, 0.95, f"R²={r2:.3f}", transform=ax.transAxes,
                fontsize=9, va="top", fontweight="bold")
    plt.suptitle("Predicted vs Actual Forward Returns", y=1.02)
    plt.tight_layout()
    plots["scatter"] = _fig_to_base64(fig)
    plt.close()

    # ── 5. Confidence Calibration ──
    if val_confidences is not None and len(val_confidences) > 0:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        conf = val_confidences.squeeze()

        # Group by direction correctness
        correct = val_dir_preds == val_dir_labels
        conf_correct = conf[correct]
        conf_wrong = conf[~correct]

        bins = np.linspace(0, 1, 30)
        ax1.hist(conf_correct, bins=bins, alpha=0.6, label=f"Correct ({len(conf_correct)})", color="#4CAF50")
        ax1.hist(conf_wrong, bins=bins, alpha=0.6, label=f"Wrong ({len(conf_wrong)})", color="#FF5722")
        ax1.set_xlabel("Confidence")
        ax1.set_ylabel("Count")
        ax1.set_title("Confidence Distribution by Correctness")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        ax2.hist(conf, bins=50, color="#9C27B0", alpha=0.7, edgecolor="white")
        ax2.set_xlabel("Confidence Score")
        ax2.set_ylabel("Count")
        ax2.set_title("Overall Confidence Distribution")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plots["confidence"] = _fig_to_base64(fig)
        plt.close()

    # ── 6. Per-Security Direction Accuracy ──
    if val_symbols is not None:
        unique_symbols = sorted(set(val_symbols))
        if len(unique_symbols) > 1:
            sym_acc = {}
            for sym in unique_symbols:
                idx = np.array([i for i, s in enumerate(val_symbols) if s == sym])
                if len(idx) < 10:
                    continue
                correct_sym = (val_dir_preds[idx] == val_dir_labels[idx]).sum()
                sym_acc[sym] = correct_sym / len(idx) * 100

            if sym_acc:
                sorted_syms = sorted(sym_acc.items(), key=lambda x: x[1], reverse=True)
                names = [s[0] for s in sorted_syms[:30]]
                vals = [s[1] for s in sorted_syms[:30]]

                fig, ax = plt.subplots(figsize=(12, max(5, len(names) * 0.3)))
                colors = ["#4CAF50" if v > 40 else "#FF5722" for v in vals]
                ax.barh(names, vals, color=colors, alpha=0.8)
                ax.axvline(x=33.3, color="red", linestyle="--", alpha=0.5, label="Random")
                ax.set_xlabel("Direction Accuracy (%)")
                ax.set_title("Per-Security Direction Accuracy")
                ax.legend()
                ax.grid(True, alpha=0.2, axis="x")
                plt.tight_layout()
                plots["per_security"] = _fig_to_base64(fig)
                plt.close()

    return plots


def generate_candle_report(model, val_loader, history, run_id, config,
                           dataset_info, device="cpu"):
    """Generate HTML report for CandleModel v0.3 training run."""
    print("\nGenerating candle model report...")
    device = torch.device(device)
    model = model.to(device)
    model.eval()

    all_dir_preds = []
    all_dir_labels = []
    all_preds = []
    all_labels = []
    all_masks = []
    all_confs = []
    all_symbols = []

    with torch.no_grad():
        for batch in val_loader:
            c5m = batch["candles_5m"].to(device)
            c15m = batch["candles_15m"].to(device)

            dir_logits, pred_returns, confidence = model(c5m, c15m)

            all_dir_preds.append(dir_logits.argmax(dim=1).cpu().numpy())
            all_dir_labels.append(batch["direction"].numpy())
            all_preds.append(pred_returns.cpu().numpy())
            all_labels.append(batch["returns"].numpy())
            all_masks.append(batch["return_mask"].numpy())
            all_confs.append(confidence.cpu().numpy())

    val_dir_preds = np.concatenate(all_dir_preds)
    val_dir_labels = np.concatenate(all_dir_labels)
    val_preds = np.concatenate(all_preds)
    val_labels = np.concatenate(all_labels)
    val_masks = np.concatenate(all_masks)
    val_confs = np.concatenate(all_confs)

    val_symbols = None
    if hasattr(val_loader.dataset, "samples"):
        val_symbols = [s[0] for s in val_loader.dataset.samples[:len(val_preds)]]

    # Direction stats
    total_correct = (val_dir_preds == val_dir_labels).sum()
    overall_dir_acc = total_correct / len(val_dir_labels) * 100

    # Per-horizon return stats
    horizon_stats = []
    for h in range(3):
        mask_h = val_masks[:, h] > 0
        n_valid = int(mask_h.sum())
        if n_valid > 0:
            pred_h = val_preds[mask_h, h]
            label_h = val_labels[mask_h, h]
            errors = pred_h - label_h
            baseline_mae = np.mean(np.abs(label_h))
            model_mae = np.mean(np.abs(errors))
            ss_res = np.sum(errors ** 2)
            ss_tot = np.sum((label_h - label_h.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            improvement = ((baseline_mae - model_mae) / baseline_mae * 100) if baseline_mae > 0 else 0
            horizon_stats.append({
                "name": CANDLE_HORIZON_NAMES[h], "samples": n_valid,
                "model_mae": model_mae, "baseline_mae": baseline_mae,
                "improvement": improvement, "r_squared": r2,
                "mean_error": float(errors.mean()), "std_error": float(errors.std()),
            })
        else:
            horizon_stats.append({
                "name": CANDLE_HORIZON_NAMES[h], "samples": 0,
                "model_mae": 0, "baseline_mae": 0, "improvement": 0,
                "r_squared": 0, "mean_error": 0, "std_error": 0,
            })

    plots = _generate_candle_plots(
        history, val_dir_preds, val_dir_labels,
        val_preds, val_labels, val_masks, val_confs, val_symbols
    )

    report_html = _build_candle_html(
        run_id, config, dataset_info, history,
        overall_dir_acc, horizon_stats, plots
    )

    report_path = MODELS_DIR / f"candle_report_{run_id}.html"
    with open(report_path, "w") as f:
        f.write(report_html)

    stats_path = MODELS_DIR / f"candle_stats_{run_id}.json"
    with open(stats_path, "w") as f:
        json.dump({
            "run_id": run_id, "model_type": "candle",
            "overall_direction_accuracy": overall_dir_acc,
            "horizon_stats": horizon_stats,
            "dataset_info": dataset_info,
            "config": config,
        }, f, indent=2, default=str)

    print(f"Report saved: {report_path}")
    print(f"Stats saved:  {stats_path}")
    return report_path


def _build_candle_html(run_id, config, dataset_info, history,
                       overall_dir_acc, horizon_stats, plots):
    """Build HTML report for CandleModel."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    best_epoch = int(np.argmin(history["val_loss"])) + 1
    best_val = min(history["val_loss"])
    final_train = history["train_loss"][-1]
    epochs_trained = len(history["train_loss"])
    best_dir_acc = max(history["val_dir_acc"]) if history["val_dir_acc"] else 0

    horizon_rows = ""
    for s in horizon_stats:
        color = "#4CAF50" if s["improvement"] > 0 else "#FF5722"
        horizon_rows += f"""
        <tr>
            <td><strong>{s['name']}</strong></td>
            <td>{s['samples']:,}</td>
            <td>{s['model_mae']:.4f}%</td>
            <td>{s['baseline_mae']:.4f}%</td>
            <td style="color:{color};font-weight:bold">{s['improvement']:+.1f}%</td>
            <td>{s['r_squared']:.4f}</td>
            <td>{s['mean_error']:+.4f}%</td>
            <td>{s['std_error']:.4f}%</td>
        </tr>"""

    dir_color = "#4CAF50" if overall_dir_acc > 40 else ("#FF9800" if overall_dir_acc > 33.3 else "#FF5722")

    def img(key, alt=""):
        if key in plots:
            return f'<img src="data:image/png;base64,{plots[key]}" alt="{alt}" style="width:100%;max-width:1200px;">'
        return f'<p><em>{alt} — no data</em></p>'

    direction_balance = dataset_info.get("direction_balance", {})
    balance_str = " / ".join(f"{k}: {v}" for k, v in direction_balance.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CandleModel v0.3 — Training Report {run_id}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           max-width: 1300px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #333; }}
    h1 {{ border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
    h2 {{ color: #1565C0; margin-top: 40px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px; margin: 20px 0; }}
    .card {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .card .label {{ font-size: 0.85em; color: #666; margin-bottom: 4px; }}
    .card .value {{ font-size: 1.4em; font-weight: bold; color: #1565C0; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px;
             overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    th {{ background: #1565C0; color: white; padding: 10px 12px; text-align: left; font-size: 0.9em; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }}
    tr:hover {{ background: #f0f7ff; }}
    .chart {{ background: white; border-radius: 8px; padding: 15px; margin: 15px 0;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
    .footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd;
               color: #999; font-size: 0.85em; }}
    .verdict {{ background: white; border-left: 4px solid #2196F3; padding: 15px;
                margin: 20px 0; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
</style>
</head>
<body>

<h1>CandleModel v0.3 — Training Report</h1>
<p>Run <strong>{run_id}</strong> &mdash; {timestamp} &mdash; Multi-timeframe (5m + 15m)</p>

<h2>Summary</h2>
<div class="summary">
    <div class="card">
        <div class="label">Training Samples</div>
        <div class="value">{dataset_info.get('train_samples', 0):,}</div>
    </div>
    <div class="card">
        <div class="label">Validation Samples</div>
        <div class="value">{dataset_info.get('val_samples', 0):,}</div>
    </div>
    <div class="card">
        <div class="label">Direction Accuracy</div>
        <div class="value" style="color:{dir_color}">{overall_dir_acc:.1f}%</div>
    </div>
    <div class="card">
        <div class="label">Best Dir Accuracy</div>
        <div class="value" style="color:{dir_color}">{best_dir_acc:.1f}%</div>
    </div>
    <div class="card">
        <div class="label">Best Val Loss</div>
        <div class="value">{best_val:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Best Epoch</div>
        <div class="value">{best_epoch} / {epochs_trained}</div>
    </div>
    <div class="card">
        <div class="label">Direction Balance</div>
        <div class="value" style="font-size:0.8em">{balance_str}</div>
    </div>
    <div class="card">
        <div class="label">Config</div>
        <div class="value" style="font-size:0.9em">B{config.get('batch_size',64)} / LR{config.get('learning_rate',1e-3)}</div>
    </div>
</div>

<h2>Direction Classification</h2>
<div class="chart">{img("confusion", "Direction Confusion Matrix")}</div>

<div class="verdict">
<strong>Direction classification:</strong> {overall_dir_acc:.1f}% accuracy (random = 33.3%).
{"The model shows meaningful directional signal." if overall_dir_acc > 40 else "Direction accuracy is still close to random — the model needs more training or better features."}
</div>

<h2>Per-Horizon Return Prediction</h2>
<table>
<tr>
    <th>Horizon</th><th>Samples</th><th>Model MAE</th><th>Baseline MAE</th>
    <th>vs Baseline</th><th>R&sup2;</th><th>Mean Error</th><th>Std Error</th>
</tr>
{horizon_rows}
</table>

<h2>Training Curves</h2>
<div class="chart">{img("loss_curves", "Loss & Accuracy Curves")}</div>

<h2>Model vs Baseline (per horizon)</h2>
<div class="chart">{img("horizon_mae", "Horizon MAE Comparison")}</div>

<h2>Predicted vs Actual Returns</h2>
<div class="chart">{img("scatter", "Prediction Scatter")}</div>

<h2>Confidence Calibration</h2>
<div class="chart">{img("confidence", "Confidence Analysis")}</div>

<h2>Per-Security Performance</h2>
<div class="chart">{img("per_security", "Per-Security Direction Accuracy")}</div>

<div class="footer">
    CandleModel v0.3 &mdash; Craig + Claude &mdash; {timestamp}
</div>

</body>
</html>"""
