#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: learning.py
Version: 1.0.0
Last Updated: 2026-04-06
Purpose: Synaptic learning module — LTP/LTD for pattern confidence

REVISION HISTORY:
v1.0.0 (2026-04-06) - Initial creation — v8 architecture alignment
- LTP (Long-Term Potentiation): winning trade strengthens pattern confidence
- LTD (Long-Term Depression): losing trade weakens pattern confidence
- Pattern outcome recording from closed trades
- Confidence weight management in pattern_confidence table
- Designed to run during Pondering cycle (CYCLE_MODE=ponder)

Description:
The synaptic learning loop is the mechanism by which the system learns
from its own trade outcomes. It implements biological LTP/LTD:

  Trade executed → position closed → outcome recorded in pattern_outcomes
      → Pondering cycle runs learning.py
          → LTP/LTD updates pattern_confidence weights
              → coordinator loads updated weights each trade cycle
                  → Decision Engine receives current confidence levels

This module runs on the host (like coordinator.py), triggered by cron
during the daily Pondering cycle.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import aiosqlite

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("learning")

# LTP/LTD parameters
LTP_INCREMENT = 0.05    # Confidence increase per win
LTD_DECREMENT = 0.08    # Confidence decrease per loss (asymmetric — losses teach more)
MIN_CONFIDENCE = 0.05   # Floor — never forget a pattern entirely
MAX_CONFIDENCE = 0.95   # Ceiling — never be 100% sure
DECAY_RATE = 0.995      # Weekly decay for patterns not recently traded


class SynapticLearning:
    """
    Implements LTP/LTD for pattern confidence based on trade outcomes.

    LTP (Long-Term Potentiation): winning trades strengthen the confidence
    of the pattern that triggered them.

    LTD (Long-Term Depression): losing trades weaken that pattern's confidence.

    The system literally learns what works.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.memory_conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Connect to hippocampus memory.db."""
        self.memory_conn = await aiosqlite.connect(self.config.hippocampus_db_path)
        self.memory_conn.row_factory = aiosqlite.Row
        await self.memory_conn.execute("PRAGMA journal_mode=WAL")
        await self.memory_conn.execute("PRAGMA busy_timeout=5000")
        await self._ensure_tables()
        logger.info("Synaptic Learning initialized. Connected to %s", self.config.hippocampus_db_path)

    async def _ensure_tables(self):
        """Create tables if they don't exist."""
        await self.memory_conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_outcomes (
                outcome_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                holding_minutes INTEGER,
                outcome TEXT NOT NULL CHECK (outcome IN ('win', 'loss', 'breakeven')),
                trade_context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.memory_conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_confidence (
                pattern_type TEXT PRIMARY KEY,
                confidence REAL DEFAULT 0.5 CHECK (confidence BETWEEN 0.0 AND 1.0),
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                avg_win_pct REAL DEFAULT 0.0,
                avg_loss_pct REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.memory_conn.commit()

    async def record_outcome(
        self,
        pattern_type: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        holding_minutes: int = 0,
        trade_context: dict = None,
    ) -> Dict[str, Any]:
        """
        Record a trade outcome and update synaptic weights.

        Called when a position is closed. Links the outcome to
        the pattern that triggered entry.
        """
        return_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0

        if return_pct > 0.001:
            outcome = "win"
        elif return_pct < -0.001:
            outcome = "loss"
        else:
            outcome = "breakeven"

        outcome_id = f"O-{uuid.uuid4().hex[:8]}"

        await self.memory_conn.execute(
            """INSERT INTO pattern_outcomes
               (outcome_id, pattern_type, symbol, entry_price, exit_price,
                return_pct, holding_minutes, outcome, trade_context)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                outcome_id, pattern_type, symbol, entry_price, exit_price,
                round(return_pct, 6), holding_minutes, outcome,
                json.dumps(trade_context) if trade_context else None,
            ),
        )
        await self.memory_conn.commit()

        # Apply LTP or LTD
        delta = await self._apply_ltp_ltd(pattern_type, outcome, return_pct)

        logger.info(
            "Outcome recorded: %s %s %s (%.2f%%) → %s confidence %+.3f",
            outcome, pattern_type, symbol, return_pct * 100,
            "LTP" if delta > 0 else "LTD", delta,
        )

        return {
            "outcome_id": outcome_id,
            "pattern_type": pattern_type,
            "outcome": outcome,
            "return_pct": round(return_pct, 6),
            "confidence_delta": round(delta, 4),
        }

    async def _apply_ltp_ltd(self, pattern_type: str, outcome: str, return_pct: float) -> float:
        """
        Apply Long-Term Potentiation (win) or Long-Term Depression (loss).
        Returns the confidence delta applied.
        """
        # Get or create confidence record
        cursor = await self.memory_conn.execute(
            "SELECT * FROM pattern_confidence WHERE pattern_type = ?",
            (pattern_type,),
        )
        row = await cursor.fetchone()

        if row:
            old_confidence = row["confidence"]
            total_trades = row["total_trades"]
            wins = row["wins"]
            losses = row["losses"]
            avg_win = row["avg_win_pct"]
            avg_loss = row["avg_loss_pct"]
        else:
            old_confidence = 0.5
            total_trades = 0
            wins = 0
            losses = 0
            avg_win = 0.0
            avg_loss = 0.0

        total_trades += 1

        if outcome == "win":
            wins += 1
            # LTP: strengthen confidence
            delta = LTP_INCREMENT * (1 + abs(return_pct))  # Bigger wins = stronger LTP
            new_confidence = min(MAX_CONFIDENCE, old_confidence + delta)
            # Update running average win
            avg_win = ((avg_win * (wins - 1)) + return_pct) / wins if wins > 0 else return_pct
        elif outcome == "loss":
            losses += 1
            # LTD: weaken confidence (asymmetric — losses teach more)
            delta = -LTD_DECREMENT * (1 + abs(return_pct))  # Bigger losses = stronger LTD
            new_confidence = max(MIN_CONFIDENCE, old_confidence + delta)
            # Update running average loss
            avg_loss = ((avg_loss * (losses - 1)) + return_pct) / losses if losses > 0 else return_pct
        else:
            # Breakeven: tiny decay
            delta = -0.005
            new_confidence = max(MIN_CONFIDENCE, old_confidence + delta)

        actual_delta = new_confidence - old_confidence

        if row:
            await self.memory_conn.execute(
                """UPDATE pattern_confidence
                   SET confidence = ?, total_trades = ?, wins = ?, losses = ?,
                       avg_win_pct = ?, avg_loss_pct = ?, last_updated = CURRENT_TIMESTAMP
                   WHERE pattern_type = ?""",
                (round(new_confidence, 4), total_trades, wins, losses,
                 round(avg_win, 6), round(avg_loss, 6), pattern_type),
            )
        else:
            await self.memory_conn.execute(
                """INSERT INTO pattern_confidence
                   (pattern_type, confidence, total_trades, wins, losses,
                    avg_win_pct, avg_loss_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pattern_type, round(new_confidence, 4), total_trades, wins, losses,
                 round(avg_win, 6), round(avg_loss, 6)),
            )

        await self.memory_conn.commit()
        return actual_delta

    async def run_pondering_cycle(self) -> Dict[str, Any]:
        """
        Run the full Pondering cycle — analyze unprocessed outcomes,
        decay stale patterns, promote validated learnings.

        This is designed to be called by cron during the daily Pondering window.
        """
        logger.info("=== PONDERING CYCLE START ===")
        results = {}

        # 1. Get current confidence landscape
        cursor = await self.memory_conn.execute(
            "SELECT * FROM pattern_confidence ORDER BY confidence DESC"
        )
        rows = await cursor.fetchall()
        confidence_landscape = [dict(r) for r in rows]
        results["confidence_landscape"] = confidence_landscape
        logger.info("Pattern confidence landscape: %d patterns tracked", len(confidence_landscape))

        for pc in confidence_landscape:
            win_rate = pc["wins"] / pc["total_trades"] if pc["total_trades"] > 0 else 0
            logger.info(
                "  %s: confidence=%.3f trades=%d wins=%d losses=%d win_rate=%.1f%%",
                pc["pattern_type"], pc["confidence"], pc["total_trades"],
                pc["wins"], pc["losses"], win_rate * 100,
            )

        # 2. Decay stale patterns (not traded recently)
        decay_result = await self._decay_stale_patterns()
        results["decay"] = decay_result

        # 3. Identify patterns ready for promotion to CLAUDE-LEARNINGS.md
        promotable = [
            pc for pc in confidence_landscape
            if pc["confidence"] >= 0.75 and pc["total_trades"] >= 5
        ]
        results["promotable_patterns"] = [p["pattern_type"] for p in promotable]
        if promotable:
            logger.info("Patterns ready for promotion: %s", [p["pattern_type"] for p in promotable])

        # 4. Identify weak patterns that need attention
        weak = [
            pc for pc in confidence_landscape
            if pc["confidence"] <= 0.25 and pc["total_trades"] >= 3
        ]
        results["weak_patterns"] = [p["pattern_type"] for p in weak]
        if weak:
            logger.info("Weak patterns (consider dropping): %s", [p["pattern_type"] for p in weak])

        # 5. Summary statistics
        total_outcomes = sum(pc["total_trades"] for pc in confidence_landscape)
        total_wins = sum(pc["wins"] for pc in confidence_landscape)
        overall_win_rate = total_wins / total_outcomes if total_outcomes > 0 else 0
        results["summary"] = {
            "total_patterns": len(confidence_landscape),
            "total_outcomes": total_outcomes,
            "overall_win_rate": round(overall_win_rate, 4),
            "promotable_count": len(promotable),
            "weak_count": len(weak),
        }

        logger.info(
            "=== PONDERING CYCLE COMPLETE: %d patterns, %d outcomes, %.1f%% win rate ===",
            len(confidence_landscape), total_outcomes, overall_win_rate * 100,
        )
        return results

    async def _decay_stale_patterns(self) -> Dict[str, Any]:
        """Decay confidence for patterns not traded in the last 7 days."""
        result = await self.memory_conn.execute(
            """UPDATE pattern_confidence
               SET confidence = MAX(?, confidence * ?),
                   last_updated = CURRENT_TIMESTAMP
               WHERE last_updated < datetime('now', '-7 days')
                 AND confidence > ?""",
            (MIN_CONFIDENCE, DECAY_RATE, MIN_CONFIDENCE),
        )
        await self.memory_conn.commit()
        decayed = result.rowcount
        if decayed:
            logger.info("Decayed %d stale patterns (rate=%.3f)", decayed, DECAY_RATE)
        return {"decayed_count": decayed}

    async def get_confidence_weights(self) -> Dict[str, float]:
        """
        Get current pattern confidence weights.
        Called by coordinator each trade cycle to feed the Decision Engine.
        """
        cursor = await self.memory_conn.execute(
            "SELECT pattern_type, confidence FROM pattern_confidence ORDER BY confidence DESC"
        )
        rows = await cursor.fetchall()
        return {row["pattern_type"]: row["confidence"] for row in rows}

    # =========================================================================
    # PATH 1 INTEGRATION: Process trade_feedback from agent.db
    # v2.4 architecture -- three learning paths
    # =========================================================================

    async def process_feedback(self, agent_db_path: str) -> Dict[str, Any]:
        """
        Path 1: Process trade feedback from agent.db into pattern outcomes.
        Reads trade_feedback table, applies LTP/LTD based on exit type.

        AI_PATTERN exits with profit -> strong LTP (model was right)
        AI_PATTERN exits with loss -> mild LTD (model exited but wrong direction)
        STOP_LOSS exits -> strong LTD (model failed to detect reversal)
        """
        import aiosqlite as aiosql
        results = {"processed": 0, "ltp_applied": 0, "ltd_applied": 0}

        async with aiosql.connect(agent_db_path) as conn:
            conn.row_factory = aiosql.Row
            cursor = await conn.execute("""
                SELECT * FROM trade_feedback
                WHERE created_at >= datetime('now', '-1 day')
                ORDER BY created_at DESC
            """)
            feedback_rows = await cursor.fetchall()

        for fb in feedback_rows:
            fb = dict(fb)
            pattern_type = fb.get("pattern_type") or f"neural_{fb.get('exit_type', 'unknown').lower()}"
            exit_type = fb.get("exit_type", "MANUAL")
            return_pct = fb.get("return_pct", 0)

            # Adjust LTP/LTD strength based on exit type
            context = {"exit_type": exit_type, "symbol": fb.get("symbol")}

            if exit_type == "STOP_LOSS":
                # Strong LTD -- the model failed. This is the most important signal.
                context["learning_note"] = "Position Monitor missed reversal"

            result = await self.record_outcome(
                pattern_type=pattern_type,
                symbol=fb.get("symbol", "UNKNOWN"),
                entry_price=fb.get("entry_price", 0),
                exit_price=fb.get("exit_price", 0),
                holding_minutes=fb.get("holding_minutes", 0),
                trade_context=context,
            )

            results["processed"] += 1
            if result["confidence_delta"] > 0:
                results["ltp_applied"] += 1
            elif result["confidence_delta"] < 0:
                results["ltd_applied"] += 1

        logger.info(
            "Feedback processed: %d trades, %d LTP, %d LTD",
            results["processed"], results["ltp_applied"], results["ltd_applied"],
        )
        return results

    async def export_training_data(self, agent_db_path: str, output_path: str) -> Dict[str, Any]:
        """
        Path 3: Export production feedback for neural retraining.
        Writes prediction/outcome pairs for neural_claude to consume.
        """
        import aiosqlite as aiosql
        records = []

        async with aiosql.connect(agent_db_path) as conn:
            conn.row_factory = aiosql.Row
            cursor = await conn.execute("""
                SELECT symbol, market, entry_price, exit_price, return_pct,
                       exit_type, neural_prediction, neural_confidence,
                       candles_at_exit, candle_model_version, entry_at, exit_at
                FROM trade_feedback
                WHERE neural_prediction IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1000
            """)
            rows = await cursor.fetchall()
            records = [dict(r) for r in rows]

        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2, default=str)

        logger.info("Exported %d training records to %s", len(records), output_path)
        return {"exported": len(records), "path": output_path}

    async def close(self):
        """Clean up."""
        if self.memory_conn:
            await self.memory_conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Synaptic Learning — LTP/LTD for pattern confidence")
    parser.add_argument(
        "--mode",
        choices=["ponder", "weights", "record"],
        default="ponder",
        help="ponder: run full Pondering cycle | weights: print current weights | record: record an outcome",
    )
    parser.add_argument("--pattern-type", help="Pattern type (for record mode)")
    parser.add_argument("--symbol", help="Symbol (for record mode)")
    parser.add_argument("--entry-price", type=float, help="Entry price (for record mode)")
    parser.add_argument("--exit-price", type=float, help="Exit price (for record mode)")
    args = parser.parse_args()

    # Load env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    config = AgentConfig.from_env()
    learner = SynapticLearning(config)

    try:
        await learner.initialize()

        if args.mode == "ponder":
            result = await learner.run_pondering_cycle()
            print(json.dumps(result, indent=2, default=str))

        elif args.mode == "weights":
            weights = await learner.get_confidence_weights()
            print(json.dumps(weights, indent=2))

        elif args.mode == "record":
            if not all([args.pattern_type, args.symbol, args.entry_price, args.exit_price]):
                print("Error: record mode requires --pattern-type, --symbol, --entry-price, --exit-price")
                sys.exit(1)
            result = await learner.record_outcome(
                pattern_type=args.pattern_type,
                symbol=args.symbol,
                entry_price=args.entry_price,
                exit_price=args.exit_price,
            )
            print(json.dumps(result, indent=2))

    finally:
        await learner.close()


if __name__ == "__main__":
    asyncio.run(main())
