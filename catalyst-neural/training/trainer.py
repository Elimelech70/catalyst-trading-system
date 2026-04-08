"""
Catalyst Neural — Training Loop

Trains CatalystNet with masked multi-horizon regression loss.
Early stopping, LR scheduling, loss curves, model checkpoints.
"""

import json
import time
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TRAINING, MODELS_DIR
from training.dataset import get_dataloaders, get_candle_dataloaders
from training.models import CatalystNet, CandleModel
from training.report import generate_report, generate_candle_report


class MaskedMSELoss(nn.Module):
    """MSE loss over valid (non-NULL) label entries only."""

    def forward(self, pred, target, mask):
        sq_error = (pred - target) ** 2 * mask
        count = mask.sum().clamp(min=1.0)
        return sq_error.sum() / count


class ConfidenceLoss(nn.Module):
    """Penalizes high confidence on wrong predictions."""

    def forward(self, confidence, pred, target, mask):
        abs_error = torch.abs(pred - target) * mask
        mean_error = abs_error.sum(dim=1, keepdim=True) / mask.sum(dim=1, keepdim=True).clamp(min=1.0)
        return (confidence * mean_error).mean()


class Trainer:
    """Training orchestrator for CatalystNet."""

    def __init__(self, model, train_loader, val_loader, config=None):
        self.cfg = {**TRAINING}
        if config:
            self.cfg.update(config)

        self.device = torch.device(self.cfg["device"] if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.val_loader = val_loader

        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.cfg["learning_rate"], weight_decay=1e-4
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
        )

        self.return_loss_fn = MaskedMSELoss()
        self.conf_loss_fn = ConfidenceLoss()
        self.conf_alpha = 0.1

        # Tracking
        self.history = {"train_loss": [], "val_loss": [], "val_mae": [], "lr": []}
        self.best_val_loss = float("inf")
        self.patience_counter = 0
        self.patience = 15
        self.best_checkpoint_path = None

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def train_epoch(self):
        self.model.train()
        total_loss = 0
        total_ret_loss = 0
        total_conf_loss = 0
        n_batches = 0

        for batch in self.train_loader:
            candles = batch["candles"].to(self.device)
            macro = batch["macro"].to(self.device)
            news = batch["news"].to(self.device)
            labels = batch["labels"].to(self.device)
            mask = batch["label_mask"].to(self.device)

            pred_returns, confidence = self.model(candles, macro, news)

            loss_ret = self.return_loss_fn(pred_returns, labels, mask)
            loss_conf = self.conf_loss_fn(confidence, pred_returns, labels, mask)
            loss = loss_ret + self.conf_alpha * loss_conf

            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            total_ret_loss += loss_ret.item()
            total_conf_loss += loss_conf.item()
            n_batches += 1

        n = max(n_batches, 1)
        return {
            "loss": total_loss / n,
            "return_loss": total_ret_loss / n,
            "conf_loss": total_conf_loss / n,
        }

    @torch.no_grad()
    def validate(self):
        self.model.eval()
        total_loss = 0
        total_ret_loss = 0
        all_errors = []
        n_batches = 0

        for batch in self.val_loader:
            candles = batch["candles"].to(self.device)
            macro = batch["macro"].to(self.device)
            news = batch["news"].to(self.device)
            labels = batch["labels"].to(self.device)
            mask = batch["label_mask"].to(self.device)

            pred_returns, confidence = self.model(candles, macro, news)

            loss_ret = self.return_loss_fn(pred_returns, labels, mask)
            loss_conf = self.conf_loss_fn(confidence, pred_returns, labels, mask)
            loss = loss_ret + self.conf_alpha * loss_conf

            total_loss += loss.item()
            total_ret_loss += loss_ret.item()
            n_batches += 1

            # Per-horizon absolute error
            abs_err = (torch.abs(pred_returns - labels) * mask).cpu().numpy()
            mask_np = mask.cpu().numpy()
            all_errors.append((abs_err, mask_np))

        n = max(n_batches, 1)

        # Compute per-horizon MAE
        all_err = np.concatenate([e[0] for e in all_errors], axis=0)
        all_mask = np.concatenate([e[1] for e in all_errors], axis=0)
        per_horizon_mae = []
        for h in range(5):
            valid = all_mask[:, h].sum()
            if valid > 0:
                per_horizon_mae.append(float(all_err[:, h].sum() / valid))
            else:
                per_horizon_mae.append(0.0)

        return {
            "loss": total_loss / n,
            "return_loss": total_ret_loss / n,
            "mean_abs_error": float(np.mean(per_horizon_mae)),
            "per_horizon_mae": per_horizon_mae,
        }

    def train(self, epochs=None):
        if epochs is None:
            epochs = self.cfg["epochs"]

        horizon_names = ["5m", "15m", "1h", "4h", "1d"]

        print(f"\n{'='*60}")
        print(f"Training CatalystNet — {self.run_id}")
        print(f"Device: {self.device}")
        print(f"Parameters: {self.model.count_parameters():,}")
        print(f"Epochs: {epochs}, Patience: {self.patience}")
        print(f"LR: {self.cfg['learning_rate']}, Batch: {self.cfg['batch_size']}")
        print(f"{'='*60}\n")

        start_time = time.time()

        for epoch in range(1, epochs + 1):
            epoch_start = time.time()

            train_metrics = self.train_epoch()
            val_metrics = self.validate()

            current_lr = self.optimizer.param_groups[0]["lr"]
            self.scheduler.step(val_metrics["loss"])

            # Track history
            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["val_mae"].append(val_metrics["mean_abs_error"])
            self.history["lr"].append(current_lr)

            # Early stopping / checkpointing
            if val_metrics["loss"] < self.best_val_loss:
                self.best_val_loss = val_metrics["loss"]
                self.patience_counter = 0
                self._save_checkpoint(epoch, val_metrics["loss"])
                marker = " *"
            else:
                self.patience_counter += 1
                marker = ""

            elapsed = time.time() - epoch_start
            mae_str = " | ".join(
                f"{n}:{v:.4f}" for n, v in zip(horizon_names, val_metrics["per_horizon_mae"])
            )

            print(f"Epoch {epoch:3d}/{epochs} ({elapsed:.1f}s) | "
                  f"Train: {train_metrics['loss']:.6f} | "
                  f"Val: {val_metrics['loss']:.6f} | "
                  f"MAE: {mae_str} | "
                  f"LR: {current_lr:.1e}{marker}")

            if self.patience_counter >= self.patience:
                print(f"\nEarly stopping at epoch {epoch} (patience {self.patience})")
                break

        total_time = time.time() - start_time
        print(f"\nTraining complete in {total_time:.1f}s ({total_time/60:.1f}m)")

        # Save artifacts
        self._save_loss_curves()
        self._save_training_metadata(total_time)

        # Load best checkpoint
        if self.best_checkpoint_path and self.best_checkpoint_path.exists():
            checkpoint = torch.load(self.best_checkpoint_path, weights_only=False)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            print(f"Loaded best checkpoint (val_loss: {self.best_val_loss:.6f})")

        return self.model

    def _save_checkpoint(self, epoch, val_loss):
        path = MODELS_DIR / f"catalyst_net_{self.run_id}.pt"
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_loss": val_loss,
            "config": self.cfg,
        }, path)
        self.best_checkpoint_path = path

    def _save_loss_curves(self):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

            epochs = range(1, len(self.history["train_loss"]) + 1)

            ax1.plot(epochs, self.history["train_loss"], label="Train Loss")
            ax1.plot(epochs, self.history["val_loss"], label="Val Loss")
            ax1.set_xlabel("Epoch")
            ax1.set_ylabel("Loss")
            ax1.set_title("Training & Validation Loss")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            ax2.plot(epochs, self.history["val_mae"], label="Val MAE", color="green")
            ax2.set_xlabel("Epoch")
            ax2.set_ylabel("Mean Absolute Error (%)")
            ax2.set_title("Validation MAE")
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            path = MODELS_DIR / f"loss_curves_{self.run_id}.png"
            plt.savefig(path, dpi=100)
            plt.close()
            print(f"Loss curves saved: {path}")
        except Exception as e:
            print(f"Could not save loss curves: {e}")

    def _save_training_metadata(self, total_time):
        meta = {
            "run_id": self.run_id,
            "config": self.cfg,
            "total_parameters": self.model.count_parameters(),
            "encoder_parameters": self.model.encoder_parameter_counts(),
            "best_val_loss": self.best_val_loss,
            "epochs_trained": len(self.history["train_loss"]),
            "final_train_loss": self.history["train_loss"][-1] if self.history["train_loss"] else None,
            "final_val_loss": self.history["val_loss"][-1] if self.history["val_loss"] else None,
            "final_val_mae": self.history["val_mae"][-1] if self.history["val_mae"] else None,
            "training_time_seconds": total_time,
            "device": str(self.device),
            "checkpoint": str(self.best_checkpoint_path) if self.best_checkpoint_path else None,
        }
        path = MODELS_DIR / f"training_meta_{self.run_id}.json"
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"Training metadata saved: {path}")


def train_model(timeframe="5m", config_overrides=None):
    """
    Top-level entry point for fused CatalystNet. Called from run.py.
    """
    cfg = {**TRAINING}
    if config_overrides:
        cfg.update(config_overrides)

    print("Loading dataset...")
    train_loader, val_loader, info = get_dataloaders(
        timeframe=timeframe,
        batch_size=cfg["batch_size"],
        lookback=cfg["lookback_candles"],
        validation_split=cfg["validation_split"],
    )

    print(f"\nDataset:")
    print(f"  Training samples:   {info['train_samples']:,}")
    print(f"  Validation samples: {info['val_samples']:,}")
    print(f"  Securities:         {info['securities']}")
    print(f"  Macro instruments:  {info['macro_instruments']}")
    print(f"  News articles:      {info['news_articles']}")

    if info["train_samples"] == 0:
        print("\nERROR: No training samples. Run 'python run.py labels' first.")
        return None

    model = CatalystNet(lookback=cfg["lookback_candles"])

    print(f"\nModel: CatalystNet")
    print(f"  Total parameters: {model.count_parameters():,}")
    for name, count in model.encoder_parameter_counts().items():
        print(f"  {name}: {count:,}")

    trainer = Trainer(model, train_loader, val_loader, config=cfg)
    trained_model = trainer.train(epochs=cfg["epochs"])

    # Generate HTML report
    generate_report(
        model=trained_model,
        val_loader=val_loader,
        history=trainer.history,
        run_id=trainer.run_id,
        config=cfg,
        dataset_info=info,
        device=str(trainer.device),
    )

    return trained_model


# =============================================================================
# v0.3 — CandleTrainer (direction + returns + confidence)
# =============================================================================


class CandleTrainer:
    """Training orchestrator for CandleModel (v0.3)."""

    def __init__(self, model, train_loader, val_loader, config=None):
        self.cfg = {**TRAINING}
        if config:
            self.cfg.update(config)

        self.device = torch.device(self.cfg["device"] if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.val_loader = val_loader

        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.cfg["learning_rate"], weight_decay=1e-4
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
        )

        self.direction_loss_fn = nn.CrossEntropyLoss()
        self.return_loss_fn = MaskedMSELoss()
        self.conf_loss_fn = ConfidenceLoss()

        # Loss weights
        self.direction_alpha = 1.0
        self.return_alpha = 1.0
        self.conf_alpha = 0.1

        self.history = {
            "train_loss": [], "val_loss": [],
            "val_dir_acc": [], "val_mae": [], "lr": [],
        }
        self.best_val_loss = float("inf")
        self.patience_counter = 0
        self.patience = 15
        self.best_checkpoint_path = None

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def train_epoch(self):
        self.model.train()
        total_loss = 0
        total_dir_loss = 0
        total_ret_loss = 0
        n_batches = 0
        correct = 0
        total = 0

        for batch in self.train_loader:
            c5m = batch["candles_5m"].to(self.device)
            c15m = batch["candles_15m"].to(self.device)
            direction = batch["direction"].to(self.device)
            returns = batch["returns"].to(self.device)
            mask = batch["return_mask"].to(self.device)

            dir_logits, pred_returns, confidence = self.model(c5m, c15m)

            loss_dir = self.direction_loss_fn(dir_logits, direction)
            loss_ret = self.return_loss_fn(pred_returns, returns, mask)
            loss_conf = self.conf_loss_fn(confidence, pred_returns, returns, mask)
            loss = (self.direction_alpha * loss_dir +
                    self.return_alpha * loss_ret +
                    self.conf_alpha * loss_conf)

            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            total_dir_loss += loss_dir.item()
            total_ret_loss += loss_ret.item()
            n_batches += 1

            preds = dir_logits.argmax(dim=1)
            correct += (preds == direction).sum().item()
            total += direction.size(0)

        n = max(n_batches, 1)
        return {
            "loss": total_loss / n,
            "dir_loss": total_dir_loss / n,
            "ret_loss": total_ret_loss / n,
            "dir_acc": correct / max(total, 1) * 100,
        }

    @torch.no_grad()
    def validate(self):
        self.model.eval()
        total_loss = 0
        all_errors = []
        correct = 0
        total = 0
        n_batches = 0

        for batch in self.val_loader:
            c5m = batch["candles_5m"].to(self.device)
            c15m = batch["candles_15m"].to(self.device)
            direction = batch["direction"].to(self.device)
            returns = batch["returns"].to(self.device)
            mask = batch["return_mask"].to(self.device)

            dir_logits, pred_returns, confidence = self.model(c5m, c15m)

            loss_dir = self.direction_loss_fn(dir_logits, direction)
            loss_ret = self.return_loss_fn(pred_returns, returns, mask)
            loss_conf = self.conf_loss_fn(confidence, pred_returns, returns, mask)
            loss = (self.direction_alpha * loss_dir +
                    self.return_alpha * loss_ret +
                    self.conf_alpha * loss_conf)

            total_loss += loss.item()
            n_batches += 1

            preds = dir_logits.argmax(dim=1)
            correct += (preds == direction).sum().item()
            total += direction.size(0)

            abs_err = (torch.abs(pred_returns - returns) * mask).cpu().numpy()
            mask_np = mask.cpu().numpy()
            all_errors.append((abs_err, mask_np))

        n = max(n_batches, 1)

        all_err = np.concatenate([e[0] for e in all_errors], axis=0)
        all_mask = np.concatenate([e[1] for e in all_errors], axis=0)
        per_horizon_mae = []
        for h in range(3):
            valid = all_mask[:, h].sum()
            if valid > 0:
                per_horizon_mae.append(float(all_err[:, h].sum() / valid))
            else:
                per_horizon_mae.append(0.0)

        return {
            "loss": total_loss / n,
            "dir_acc": correct / max(total, 1) * 100,
            "mean_abs_error": float(np.mean(per_horizon_mae)),
            "per_horizon_mae": per_horizon_mae,
        }

    def train(self, epochs=None):
        if epochs is None:
            epochs = self.cfg["epochs"]

        horizon_names = ["5m", "15m", "1h"]

        print(f"\n{'='*60}")
        print(f"Training CandleModel v0.3 — {self.run_id}")
        print(f"Device: {self.device}")
        print(f"Parameters: {self.model.count_parameters():,}")
        print(f"Epochs: {epochs}, Patience: {self.patience}")
        print(f"LR: {self.cfg['learning_rate']}, Batch: {self.cfg['batch_size']}")
        print(f"{'='*60}\n")

        start_time = time.time()

        for epoch in range(1, epochs + 1):
            epoch_start = time.time()

            train_metrics = self.train_epoch()
            val_metrics = self.validate()

            current_lr = self.optimizer.param_groups[0]["lr"]
            self.scheduler.step(val_metrics["loss"])

            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["val_dir_acc"].append(val_metrics["dir_acc"])
            self.history["val_mae"].append(val_metrics["mean_abs_error"])
            self.history["lr"].append(current_lr)

            if val_metrics["loss"] < self.best_val_loss:
                self.best_val_loss = val_metrics["loss"]
                self.patience_counter = 0
                self._save_checkpoint(epoch, val_metrics["loss"])
                marker = " *"
            else:
                self.patience_counter += 1
                marker = ""

            elapsed = time.time() - epoch_start
            mae_str = " | ".join(
                f"{n}:{v:.4f}" for n, v in zip(horizon_names, val_metrics["per_horizon_mae"])
            )

            print(f"Epoch {epoch:3d}/{epochs} ({elapsed:.1f}s) | "
                  f"Loss: {train_metrics['loss']:.4f}/{val_metrics['loss']:.4f} | "
                  f"Dir: {train_metrics['dir_acc']:.1f}%/{val_metrics['dir_acc']:.1f}% | "
                  f"MAE: {mae_str} | "
                  f"LR: {current_lr:.1e}{marker}")

            if self.patience_counter >= self.patience:
                print(f"\nEarly stopping at epoch {epoch} (patience {self.patience})")
                break

        total_time = time.time() - start_time
        print(f"\nTraining complete in {total_time:.1f}s ({total_time/60:.1f}m)")

        self._save_training_metadata(total_time)

        if self.best_checkpoint_path and self.best_checkpoint_path.exists():
            checkpoint = torch.load(self.best_checkpoint_path, weights_only=False)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            print(f"Loaded best checkpoint (val_loss: {self.best_val_loss:.6f})")

        return self.model

    def _save_checkpoint(self, epoch, val_loss):
        path = MODELS_DIR / f"candle_model_{self.run_id}.pt"
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_loss": val_loss,
            "config": self.cfg,
            "model_type": "candle",
        }, path)
        self.best_checkpoint_path = path

    def _save_training_metadata(self, total_time):
        meta = {
            "run_id": self.run_id,
            "model_type": "candle",
            "config": self.cfg,
            "total_parameters": self.model.count_parameters(),
            "encoder_parameters": self.model.encoder_parameter_counts(),
            "best_val_loss": self.best_val_loss,
            "epochs_trained": len(self.history["train_loss"]),
            "final_train_loss": self.history["train_loss"][-1] if self.history["train_loss"] else None,
            "final_val_loss": self.history["val_loss"][-1] if self.history["val_loss"] else None,
            "final_dir_acc": self.history["val_dir_acc"][-1] if self.history["val_dir_acc"] else None,
            "final_val_mae": self.history["val_mae"][-1] if self.history["val_mae"] else None,
            "training_time_seconds": total_time,
            "device": str(self.device),
            "checkpoint": str(self.best_checkpoint_path) if self.best_checkpoint_path else None,
        }
        path = MODELS_DIR / f"training_meta_{self.run_id}.json"
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"Training metadata saved: {path}")


def train_candle_model(config_overrides=None):
    """
    Top-level entry point for CandleModel training. Called from run.py.
    """
    cfg = {**TRAINING}
    if config_overrides:
        cfg.update(config_overrides)

    print("Loading multi-timeframe candle dataset...")
    train_loader, val_loader, info = get_candle_dataloaders(
        batch_size=cfg["batch_size"],
        lookback=cfg["lookback_candles"],
        validation_split=cfg["validation_split"],
    )

    print(f"\nDataset:")
    print(f"  Training samples:   {info['train_samples']:,}")
    print(f"  Validation samples: {info['val_samples']:,}")
    print(f"  Securities (5m):    {info['securities_5m']}")
    print(f"  Securities (15m):   {info['securities_15m']}")
    print(f"  Direction threshold: {info['direction_threshold']}")
    for cls, count in info["direction_balance"].items():
        print(f"    {cls}: {count}")

    if info["train_samples"] == 0:
        print("\nERROR: No training samples. Run 'python run.py labels' first.")
        return None

    model = CandleModel()

    print(f"\nModel: CandleModel v0.3")
    print(f"  Total parameters: {model.count_parameters():,}")
    for name, count in model.encoder_parameter_counts().items():
        print(f"  {name}: {count:,}")

    trainer = CandleTrainer(model, train_loader, val_loader, config=cfg)
    trained_model = trainer.train(epochs=cfg["epochs"])

    generate_candle_report(
        model=trained_model,
        val_loader=val_loader,
        history=trainer.history,
        run_id=trainer.run_id,
        config=cfg,
        dataset_info=info,
        device=str(trainer.device),
    )

    return trained_model
