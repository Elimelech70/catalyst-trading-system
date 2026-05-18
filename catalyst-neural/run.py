#!/usr/bin/env python3
"""
Catalyst Neural — Main Runner

Single entry point for all data collection and training operations.

Usage:
    python run.py init              # Initialize database
    python run.py add AAPL US       # Add security to watch list
    python run.py add 9988 HKEX     # Add HKEX security
    python run.py pick              # Pick securities from droplet + big movers
    python run.py pick --droplet    # Poll droplet scanners only
    python run.py pick --universe   # Add full training universe
    python run.py movers            # Show big movers (no add)
    python run.py collect           # Run all collectors once
    python run.py collect candles   # Candle data only
    python run.py collect news      # News only
    python run.py collect macro     # Macro + sectors only
    python run.py backfill          # Backfill historical data
    python run.py backfill --days 60 # Backfill with custom range
    python run.py labels            # Compute forward return labels
    python run.py labels --stats    # Show label statistics
    python run.py status            # Show database status
    python run.py watch             # Continuous collection (runs every 5 min)
    python run.py train candle       # Train CandleModel v0.3
    python run.py train fused        # Train fused CatalystNet (original)
    python run.py export candle <checkpoint.pt>  # Export to ONNX
    python run.py pipeline           # Full: labels → train → export → deploy both droplets
    python run.py pipeline --skip-deploy  # Train + export only (no deploy)
"""

import sys
import time
import signal
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent))

from storage.database import init_db, get_connection, get_active_securities, add_security
from collectors.candle_collector import collect_all as collect_candles, backfill as candle_backfill
from collectors.macro_collector import (
    collect_macro_snapshot, collect_sectors,
    collect_macro_history, collect_sector_history
)
from collectors.news_collector import collect_all_news
from collectors.security_picker import update_watch_list, show_movers
from training.label_generator import compute_all as compute_labels, show_stats
from training.trainer import train_model, train_candle_model
from config.settings import active_markets, next_market_open, MARKET_HOURS


# Graceful shutdown
running = True
def signal_handler(sig, frame):
    global running
    print("\n\nShutting down gracefully...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def cmd_init():
    """Initialize the database."""
    init_db()


def cmd_add(symbol, market, name=None):
    """Add a security to the watch list."""
    init_db()
    add_security(symbol.upper(), market.upper(), name=name, source="manual")


def cmd_status():
    """Show database status."""
    init_db()
    conn = get_connection()
    
    print(f"\n{'='*60}")
    print(f"Catalyst Neural — Database Status")
    print(f"{'='*60}\n")
    
    # Table counts
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    
    for t in tables:
        name = t["name"]
        count = conn.execute(f"SELECT COUNT(*) as c FROM {name}").fetchone()["c"]
        print(f"  {name:<25} {count:>8} rows")
    
    # Active securities
    print(f"\n--- Active Securities ---")
    securities = get_active_securities()
    if securities:
        for s in securities:
            print(f"  {s['symbol']:<10} {s['market']:<6} {(s.get('name') or ''):<20} added {s['added_at'][:10]}")
    else:
        print("  (none — use 'python run.py add SYMBOL MARKET' to add)")
    
    # Recent collection log
    print(f"\n--- Recent Collections ---")
    recent = conn.execute("""
        SELECT collector, symbol, market, status, records_collected, completed_at
        FROM collection_log ORDER BY completed_at DESC LIMIT 10
    """).fetchall()
    
    for r in recent:
        r = dict(r)
        sym = f"{r['symbol'] or ''} {r['market'] or ''}".strip()
        print(f"  {r['completed_at'][:19]}  {r['collector']:<8} {sym:<15} "
              f"{r['status']:<8} {r['records_collected']} records")
    
    if not recent:
        print("  (no collections yet)")
    
    conn.close()


def cmd_collect(target="all"):
    """Run collectors."""
    init_db()
    
    if target in ("all", "candles"):
        collect_candles()
    
    if target in ("all", "macro"):
        collect_macro_snapshot()
        collect_sectors()
    
    if target in ("all", "news"):
        collect_all_news()


def cmd_backfill(days=30):
    """Backfill historical data."""
    init_db()
    print(f"\nBackfilling {days} days of historical data...\n")
    
    candle_backfill(days)
    collect_macro_history(days)
    collect_sector_history(days)
    
    print("\nBackfill complete. Run 'python run.py labels' to compute forward returns.")


def cmd_labels(stats_only=False, timeframe="5m"):
    """Compute or show forward return labels."""
    init_db()
    if stats_only:
        show_stats()
    else:
        compute_labels(timeframe)


def cmd_pick(droplet_only=False, universe=False, threshold=3.0):
    """Pick securities from droplet and/or big movers."""
    init_db()
    if universe:
        update_watch_list(include_droplet=False, include_movers=False, add_full_universe=True)
    elif droplet_only:
        update_watch_list(include_droplet=True, include_movers=False)
    else:
        update_watch_list(include_droplet=True, include_movers=True, mover_threshold=threshold)


def cmd_movers():
    """Show current big movers without adding to watch list."""
    show_movers()


def cmd_train(model_type="candle", timeframe="5m", config_overrides=None, dry_run=False):
    """Train a neural network."""
    init_db()

    if model_type == "candle":
        if dry_run:
            from training.dataset import CandleDataset, get_candle_dataloaders
            from training.models import CandleModel
            _, _, info = get_candle_dataloaders()
            model = CandleModel()
            print(f"\nDry run — CandleModel v0.3:")
            print(f"  Training samples:   {info['train_samples']:,}")
            print(f"  Validation samples: {info['val_samples']:,}")
            print(f"  Model parameters:   {model.count_parameters():,}")
            for name, count in model.encoder_parameter_counts().items():
                print(f"    {name}: {count:,}")
            for k, v in info["direction_balance"].items():
                print(f"    {k}: {v}")
            return
        train_candle_model(config_overrides)

    elif model_type in ("fused", "legacy"):
        if dry_run:
            from training.dataset import CatalystDataset
            from training.models import CatalystNet
            train_ds = CatalystDataset(timeframe=timeframe, split="train")
            val_ds = CatalystDataset(timeframe=timeframe, split="val")
            model = CatalystNet()
            print(f"\nDry run — CatalystNet (fused):")
            print(f"  Training samples:   {len(train_ds):,}")
            print(f"  Validation samples: {len(val_ds):,}")
            print(f"  Model parameters:   {model.count_parameters():,}")
            for name, count in model.encoder_parameter_counts().items():
                print(f"    {name}: {count:,}")
            return
        train_model(timeframe, config_overrides)

    else:
        print(f"ERROR: Unknown model type '{model_type}'. Use 'candle' or 'fused'.")


def cmd_export(model_type, checkpoint_path, output_path=None):
    """Export a trained model to ONNX."""
    from training.export_onnx import export_candle_model, export_fused_model

    if model_type == "candle":
        export_candle_model(checkpoint_path, output_path)
    elif model_type == "fused":
        export_fused_model(checkpoint_path, output_path)
    else:
        print(f"ERROR: Unknown model type '{model_type}'. Use 'candle' or 'fused'.")


def cmd_pipeline(skip_deploy=False, epochs=None, force=False):
    """Full pipeline: labels → train → export → deploy to both droplets."""
    init_db()
    deploy_dir = Path(__file__).parent / "deploy"

    print(f"\n{'='*60}")
    print(f"Catalyst Neural — Automated Pipeline")
    print(f"{'='*60}\n")

    # Step 1: Compute forward return labels
    print(">>> Step 1/6: Computing forward return labels...")
    compute_labels("5m")

    # Step 2: Train CandleModel
    print("\n>>> Step 2/6: Training CandleModel...")
    overrides = {}
    if epochs:
        overrides["epochs"] = epochs
    result = train_candle_model(overrides if overrides else None)

    # Step 3: Find the checkpoint from this training run
    print("\n>>> Step 3/6: Locating best checkpoint...")
    models_dir = Path(__file__).parent / "models"
    checkpoints = sorted(models_dir.glob("candle_model_*.pt"), key=lambda p: p.stat().st_mtime)
    if not checkpoints:
        print("ERROR: No checkpoint found after training. Aborting.")
        return
    latest_checkpoint = checkpoints[-1]
    print(f"    Using: {latest_checkpoint.name}")

    # Step 4: Export to ONNX
    print("\n>>> Step 4/6: Exporting to ONNX...")
    from training.export_onnx import export_candle_model
    export_candle_model(str(latest_checkpoint))

    if skip_deploy:
        print("\n>>> Skipping deployment (--skip-deploy)")
        print(f"\n{'='*60}")
        print(f"Pipeline complete (local only)")
        print(f"{'='*60}")
        return

    # Step 5: Deploy to US droplet
    print("\n>>> Step 5/6: Deploying to US droplet (68.183.177.11)...")
    us_script = deploy_dir / "deploy-neural.sh"
    us_result = subprocess.run(
        ["bash", str(us_script)],
        cwd=str(deploy_dir),
        timeout=300
    )
    if us_result.returncode != 0:
        print("WARNING: US deployment failed — continuing to international...")

    # Step 6: Deploy to International droplet
    print("\n>>> Step 6/6: Deploying to International droplet (209.38.87.27)...")
    intl_script = deploy_dir / "deploy-intl.sh"
    intl_result = subprocess.run(
        ["bash", str(intl_script)],
        cwd=str(deploy_dir),
        timeout=300
    )
    if intl_result.returncode != 0:
        print("WARNING: International deployment failed.")

    print(f"\n{'='*60}")
    print(f"Pipeline complete!")
    print(f"  Checkpoint: {latest_checkpoint.name}")
    print(f"  ONNX:       models/candle_model.onnx")
    print(f"  US deploy:  {'OK' if us_result.returncode == 0 else 'FAILED'}")
    print(f"  Intl deploy: {'OK' if intl_result.returncode == 0 else 'FAILED'}")
    print(f"{'='*60}")


def _sleep_interruptible(seconds):
    """Sleep for N seconds, checking graceful shutdown every second."""
    global running
    for _ in range(int(seconds)):
        if not running:
            return False
        time.sleep(1)
    return running


def cmd_watch(interval_minutes=5):
    """
    Market-hours-aware continuous collection.
    Collects US data during NYSE hours and HKEX data during HK hours.
    Sleeps between sessions instead of polling 24/7.
    Press Ctrl+C to stop gracefully.
    """
    init_db()
    global running

    print(f"\n{'='*60}")
    print(f"Catalyst Neural — Market-Aware Collection")
    print(f"Interval: every {interval_minutes} minutes during market hours")
    print(f"Markets: {', '.join(MARKET_HOURS.keys())}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    cycle = 0
    while running:
        markets = active_markets()

        # ── No market open — suspend or sleep until next session ──
        if not markets:
            nxt = next_market_open()
            if nxt:
                market, open_dt, secs = nxt
                local_str = open_dt.strftime("%a %H:%M %Z")
                hrs = int(secs // 3600)
                mins = int((secs % 3600) // 60)
                print(f"\nAll markets closed. Next: {market} opens {local_str} "
                      f"(in {hrs}h {mins}m)")

                # If >30 min to next session, try hardware suspend
                if secs > 1800:
                    power_script = str(Path(__file__).parent / "catalyst-power")
                    can = subprocess.run(
                        [power_script, "can-suspend"],
                        capture_output=True, text=True
                    )
                    if can.returncode == 0:
                        print("Suspending until next session...")
                        subprocess.run(["sudo", power_script, "suspend"])
                        print(f"Resumed — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
                        continue
                    else:
                        print("User active — staying awake (software sleep)")

                # Software sleep in 60s chunks
                if not _sleep_interruptible(min(secs, 60)):
                    break
            else:
                if not _sleep_interruptible(60):
                    break
            continue

        # ── At least one market is open — collect ──
        cycle += 1
        markets_str = " + ".join(markets)
        print(f"\n>>> Cycle {cycle} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} "
              f"— Markets open: {markets_str}")

        try:
            # Candles: only for open markets
            for mkt in markets:
                collect_candles(timeframes=["5m"], days=1, market=mkt)

            # Macro every cycle (relevant whenever any market trades)
            collect_macro_snapshot()

            # Sectors every 6th cycle (30 min)
            if cycle % 6 == 0:
                collect_sectors()

            # News every 3rd cycle (15 min)
            if cycle % 3 == 0:
                collect_all_news()

            # Security picker every 12th cycle (60 min)
            if cycle % 12 == 0:
                update_watch_list(include_droplet=True, include_movers=True)

        except Exception as e:
            print(f"ERROR in collection cycle: {e}")

        # Wait for next cycle
        if running:
            print(f"\nSleeping {interval_minutes} minutes...")
            if not _sleep_interruptible(interval_minutes * 60):
                break

    print("Collection stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Catalyst Neural — Data Collection & Training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py init                  # Set up database
  python run.py add AAPL US           # Watch Apple
  python run.py add 9988 HKEX         # Watch Alibaba (HKEX)
  python run.py collect               # Collect all data once
  python run.py backfill --days 30    # Get 30 days history
  python run.py labels                # Compute training labels
  python run.py watch                 # Continuous collection
  python run.py status                # Check what we have
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    subparsers.add_parser("init", help="Initialize database")
    
    # add
    add_parser = subparsers.add_parser("add", help="Add security to watch list")
    add_parser.add_argument("symbol", help="Security symbol (e.g. AAPL, 9988)")
    add_parser.add_argument("market", help="Market (US or HKEX)")
    add_parser.add_argument("--name", help="Security name", default=None)
    
    # collect
    collect_parser = subparsers.add_parser("collect", help="Run collectors")
    collect_parser.add_argument("target", nargs="?", default="all",
                                choices=["all", "candles", "news", "macro"])
    
    # pick
    pick_parser = subparsers.add_parser("pick", help="Pick securities from droplet + movers")
    pick_parser.add_argument("--droplet", action="store_true", help="Droplet picks only")
    pick_parser.add_argument("--universe", action="store_true", help="Add full training universe")
    pick_parser.add_argument("--threshold", type=float, default=3.0,
                             help="Big mover threshold (default 3%%)")
    
    # movers
    subparsers.add_parser("movers", help="Show big movers (no add)")
    
    # backfill
    backfill_parser = subparsers.add_parser("backfill", help="Backfill historical data")
    backfill_parser.add_argument("--days", type=int, default=30)
    
    # labels
    labels_parser = subparsers.add_parser("labels", help="Compute forward return labels")
    labels_parser.add_argument("--stats", action="store_true")
    labels_parser.add_argument("--timeframe", default="5m")
    
    # status
    subparsers.add_parser("status", help="Show database status")
    
    # watch
    watch_parser = subparsers.add_parser("watch", help="Continuous collection")
    watch_parser.add_argument("--interval", type=int, default=5, help="Minutes between cycles")

    # train
    train_parser = subparsers.add_parser("train", help="Train neural network")
    train_parser.add_argument("model_type", nargs="?", default="candle",
                              choices=["candle", "fused", "legacy"],
                              help="Model type (default: candle)")
    train_parser.add_argument("--timeframe", default="5m", help="Candle timeframe for fused model")
    train_parser.add_argument("--epochs", type=int, default=None, help="Override max epochs")
    train_parser.add_argument("--batch-size", type=int, default=None, help="Override batch size")
    train_parser.add_argument("--lr", type=float, default=None, help="Override learning rate")
    train_parser.add_argument("--device", default=None, help="Override device (cuda/cpu)")
    train_parser.add_argument("--dry-run", action="store_true", help="Check data + model, skip training")

    # export
    export_parser = subparsers.add_parser("export", help="Export model to ONNX")
    export_parser.add_argument("model_type", choices=["candle", "fused"],
                               help="Model type to export")
    export_parser.add_argument("checkpoint", help="Path to .pt checkpoint")
    export_parser.add_argument("--output", default=None, help="Output ONNX path")

    # pipeline
    pipeline_parser = subparsers.add_parser("pipeline",
                                             help="Full: labels → train → export → deploy")
    pipeline_parser.add_argument("--skip-deploy", action="store_true",
                                  help="Train + export only, skip deployment")
    pipeline_parser.add_argument("--epochs", type=int, default=None,
                                  help="Override max epochs")
    pipeline_parser.add_argument("--force", action="store_true",
                                  help="Run even if insufficient new data")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "init":
        cmd_init()
    elif args.command == "add":
        cmd_add(args.symbol, args.market, args.name)
    elif args.command == "pick":
        cmd_pick(args.droplet, args.universe, args.threshold)
    elif args.command == "movers":
        cmd_movers()
    elif args.command == "collect":
        cmd_collect(args.target)
    elif args.command == "backfill":
        cmd_backfill(args.days)
    elif args.command == "labels":
        cmd_labels(args.stats, args.timeframe)
    elif args.command == "status":
        cmd_status()
    elif args.command == "watch":
        cmd_watch(args.interval)
    elif args.command == "train":
        overrides = {}
        if args.epochs:
            overrides["epochs"] = args.epochs
        if args.batch_size:
            overrides["batch_size"] = args.batch_size
        if args.lr:
            overrides["learning_rate"] = args.lr
        if args.device:
            overrides["device"] = args.device
        cmd_train(args.model_type, args.timeframe,
                  overrides if overrides else None, args.dry_run)
    elif args.command == "export":
        cmd_export(args.model_type, args.checkpoint, args.output)
    elif args.command == "pipeline":
        cmd_pipeline(args.skip_deploy, args.epochs, args.force)


if __name__ == "__main__":
    main()
