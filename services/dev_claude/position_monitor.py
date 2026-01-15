#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: position_monitor.py
Version: 1.0.0
Last Updated: 2026-01-15
Purpose: Real-time position monitoring with exit signal detection

REVISION HISTORY:
v1.0.0 (2026-01-15) - Initial implementation
  - Trade-triggered monitoring
  - Exit signal integration
  - Automatic position closure on critical signals
  - Alerting to consciousness framework

Description:
Monitors open positions for exit signals. Can be run:
1. After a trade is executed (trade-triggered)
2. On a schedule (periodic monitoring)
3. Manually for ad-hoc checks
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import asyncpg
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Import local modules
from signals import SignalDetector, SignalStrength, ExitSignal

# Load environment
load_dotenv()

# Timezone
try:
    import pytz
    ET = pytz.timezone('America/New_York')
except ImportError:
    ET = timezone(timedelta(hours=-5))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('position_monitor')


class PositionMonitor:
    """Monitors positions for exit signals."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize monitor with configuration."""
        self.config = config
        self.signal_detector = SignalDetector(config)
        self.broker = None
        self.db_pool = None
        self.research_pool = None
        self.agent_id = config.get('agent', {}).get('id', 'dev_claude')

    async def connect(self):
        """Connect to databases and broker."""
        # Database connections
        trading_url = os.getenv("DATABASE_URL") or os.getenv("DEV_DATABASE_URL")
        research_url = os.getenv("RESEARCH_DATABASE_URL")

        if trading_url:
            self.db_pool = await asyncpg.create_pool(trading_url, min_size=1, max_size=3)
            logger.info("Connected to trading database")

        if research_url:
            try:
                self.research_pool = await asyncpg.create_pool(research_url, min_size=1, max_size=2)
                logger.info("Connected to research database")
            except Exception as e:
                logger.warning(f"Could not connect to research database: {e}")

        # Broker connection
        from unified_agent import AlpacaClient
        self.broker = AlpacaClient(paper_trading=True)
        logger.info("Connected to Alpaca broker")

    async def close(self):
        """Close connections."""
        if self.db_pool:
            await self.db_pool.close()
        if self.research_pool:
            await self.research_pool.close()
        logger.info("Connections closed")

    async def get_technicals(self, symbol: str) -> Dict[str, Any]:
        """Get technical indicators for a symbol."""
        try:
            bars = self.broker.get_bars(symbol, days=30)
            if not bars:
                return {}

            closes = [b['close'] for b in bars]

            # RSI calculation
            rsi = self._calculate_rsi(closes, 14)

            # Moving averages
            sma_10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
            sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None

            current = closes[-1] if closes else 0

            return {
                'symbol': symbol,
                'current_price': current,
                'rsi_14': round(rsi, 2) if rsi else None,
                'sma_10': round(sma_10, 2) if sma_10 else None,
                'sma_20': round(sma_20, 2) if sma_20 else None,
                'above_sma_10': current > sma_10 if sma_10 else None,
                'above_sma_20': current > sma_20 if sma_20 else None,
            }
        except Exception as e:
            logger.error(f"Error getting technicals for {symbol}: {e}")
            return {}

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return None

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    async def monitor_positions(self, auto_close: bool = False) -> Dict[str, Any]:
        """
        Monitor all positions for exit signals.

        Args:
            auto_close: If True, automatically close positions with critical signals

        Returns:
            Summary of monitoring results
        """
        results = {
            'timestamp': datetime.now(ET).isoformat() if hasattr(ET, 'localize') else datetime.now(ET).isoformat(),
            'positions_checked': 0,
            'signals_detected': 0,
            'positions_closed': 0,
            'position_details': []
        }

        try:
            # Get current positions from broker
            positions = self.broker.get_positions()
            results['positions_checked'] = len(positions)

            if not positions:
                logger.info("No open positions to monitor")
                return results

            for position in positions:
                symbol = position['symbol']
                logger.info(f"Monitoring {symbol}...")

                # Get technical data
                technicals = await self.get_technicals(symbol)

                # Detect signals
                signals = self.signal_detector.detect_exit_signals(
                    position=position,
                    technicals=technicals,
                    patterns=None  # Could add pattern detection
                )

                position_result = {
                    'symbol': symbol,
                    'pnl_pct': position.get('pnl_pct', 0),
                    'unrealized_pnl': position.get('unrealized_pnl', 0),
                    'signals': [
                        {
                            'type': s.signal_type,
                            'strength': s.strength.name,
                            'reason': s.reason,
                            'urgency': s.urgency
                        }
                        for s in signals
                    ],
                    'action_taken': None
                }

                if signals:
                    results['signals_detected'] += len(signals)
                    strongest = self.signal_detector.get_strongest_signal(signals)

                    # Log significant signals
                    if strongest.strength.value >= SignalStrength.MODERATE.value:
                        logger.warning(f"{symbol}: {strongest.reason}")

                    # Auto-close on critical signals
                    if auto_close and strongest.strength == SignalStrength.CRITICAL:
                        logger.warning(f"AUTO-CLOSING {symbol}: {strongest.reason}")
                        close_result = self.broker.close_position(symbol)

                        if close_result.get('success'):
                            results['positions_closed'] += 1
                            position_result['action_taken'] = 'closed'

                            # Alert via consciousness
                            await self._send_alert(
                                subject=f'Position Closed: {symbol}',
                                body=f'Auto-closed {symbol} due to: {strongest.reason}\nP&L: {position.get("pnl_pct", 0):.2f}%',
                                priority='high'
                            )
                        else:
                            position_result['action_taken'] = f'close_failed: {close_result.get("error")}'

                results['position_details'].append(position_result)

        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)
            results['error'] = str(e)

        return results

    async def monitor_single(self, symbol: str) -> Dict[str, Any]:
        """Monitor a single position."""
        positions = self.broker.get_positions()
        position = next((p for p in positions if p['symbol'] == symbol), None)

        if not position:
            return {'error': f'No position found for {symbol}'}

        technicals = await self.get_technicals(symbol)
        signals = self.signal_detector.detect_exit_signals(
            position=position,
            technicals=technicals
        )

        return {
            'symbol': symbol,
            'position': position,
            'technicals': technicals,
            'signals': [
                {
                    'type': s.signal_type,
                    'strength': s.strength.name,
                    'reason': s.reason,
                    'urgency': s.urgency,
                    'recommended_action': s.recommended_action
                }
                for s in signals
            ],
            'should_exit': self.signal_detector.should_exit(signals),
            'exit_reason': self.signal_detector.get_exit_reason(signals) if signals else None
        }

    async def _send_alert(self, subject: str, body: str, priority: str = 'normal'):
        """Send alert via consciousness framework."""
        if not self.research_pool:
            return

        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority)
                    VALUES ($1, 'big_bro', 'alert', $2, $3, $4)
                """, self.agent_id, subject, body, priority)
        except Exception as e:
            logger.warning(f"Could not send alert: {e}")

    async def log_monitoring_event(self, results: Dict[str, Any]):
        """Log monitoring event to database."""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO decisions (symbol, decision_type, reasoning, confidence, metadata)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                'MONITORING',
                'position_check',
                f"Checked {results['positions_checked']} positions, found {results['signals_detected']} signals",
                0.9,
                json.dumps({
                    'agent_id': self.agent_id,
                    'positions_checked': results['positions_checked'],
                    'signals_detected': results['signals_detected'],
                    'positions_closed': results['positions_closed']
                })
                )
        except Exception as e:
            logger.warning(f"Could not log monitoring event: {e}")


async def main(mode: str = 'check', symbol: Optional[str] = None, auto_close: bool = False):
    """Main entry point."""
    import yaml

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'dev_claude_config.yaml')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {'agent': {'id': 'dev_claude'}, 'signals': {}}

    monitor = PositionMonitor(config)

    try:
        await monitor.connect()

        if mode == 'single' and symbol:
            result = await monitor.monitor_single(symbol)
        else:
            result = await monitor.monitor_positions(auto_close=auto_close)

        await monitor.log_monitoring_event(result)

        logger.info(f"Result: {json.dumps(result, indent=2, default=str)}")
        return result

    finally:
        await monitor.close()


def cli():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='Position Monitor for dev_claude')
    parser.add_argument(
        '--mode',
        choices=['check', 'single', 'auto'],
        default='check',
        help='Mode: check (monitor all), single (one symbol), auto (with auto-close)'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default=None,
        help='Symbol to monitor (for single mode)'
    )
    parser.add_argument(
        '--auto-close',
        action='store_true',
        help='Automatically close positions with critical signals'
    )

    args = parser.parse_args()

    auto_close = args.auto_close or args.mode == 'auto'
    asyncio.run(main(args.mode, args.symbol, auto_close))


if __name__ == "__main__":
    cli()
