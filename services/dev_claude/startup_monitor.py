#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: startup_monitor.py
Version: 1.0.0
Last Updated: 2026-01-15
Purpose: Pre-market position reconciliation and health check

REVISION HISTORY:
v1.0.0 (2026-01-15) - Initial implementation
  - Broker position reconciliation
  - Account health check
  - Overnight gap analysis
  - Pre-market alerts

Description:
Run before market open to:
1. Reconcile broker positions with database
2. Check for overnight gaps
3. Verify account health (margin, buying power)
4. Generate pre-market alerts
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
logger = logging.getLogger('startup_monitor')


class StartupMonitor:
    """Pre-market startup checks and reconciliation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        self.config = config
        self.broker = None
        self.db_pool = None
        self.research_pool = None
        self.agent_id = config.get('agent', {}).get('id', 'dev_claude')

        # Risk thresholds
        trading_config = config.get('trading', {})
        self.max_positions = trading_config.get('max_positions', 8)
        self.daily_loss_limit = trading_config.get('daily_loss_limit', 2500)
        self.min_buying_power = trading_config.get('min_buying_power', 1000)
        self.gap_alert_threshold = 0.05  # 5% overnight gap

    async def connect(self):
        """Connect to databases and broker."""
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

    async def run_startup_checks(self) -> Dict[str, Any]:
        """Run all pre-market startup checks."""
        results = {
            'timestamp': datetime.now(ET).isoformat() if hasattr(ET, 'localize') else datetime.now(ET).isoformat(),
            'status': 'healthy',
            'alerts': [],
            'account': {},
            'positions': {},
            'gaps': [],
            'recommendations': []
        }

        try:
            # 1. Account Health Check
            account_result = await self._check_account_health()
            results['account'] = account_result
            if account_result.get('alerts'):
                results['alerts'].extend(account_result['alerts'])

            # 2. Position Reconciliation
            position_result = await self._reconcile_positions()
            results['positions'] = position_result
            if position_result.get('alerts'):
                results['alerts'].extend(position_result['alerts'])

            # 3. Overnight Gap Analysis
            gap_result = await self._analyze_overnight_gaps()
            results['gaps'] = gap_result.get('gaps', [])
            if gap_result.get('alerts'):
                results['alerts'].extend(gap_result['alerts'])

            # 4. Generate Recommendations
            results['recommendations'] = self._generate_recommendations(results)

            # Determine overall status
            if any(a.get('severity') == 'critical' for a in results['alerts']):
                results['status'] = 'critical'
            elif any(a.get('severity') == 'warning' for a in results['alerts']):
                results['status'] = 'warning'

            # Send alerts if any
            if results['alerts']:
                await self._send_startup_alert(results)

        except Exception as e:
            logger.error(f"Startup check error: {e}", exc_info=True)
            results['status'] = 'error'
            results['error'] = str(e)

        return results

    async def _check_account_health(self) -> Dict[str, Any]:
        """Check account health metrics."""
        result = {
            'alerts': []
        }

        try:
            account = self.broker.get_account()
            result['cash'] = account['cash']
            result['equity'] = account['equity']
            result['buying_power'] = account['buying_power']
            result['portfolio_value'] = account['portfolio_value']
            result['day_trade_count'] = account.get('day_trade_count', 0)

            # Check buying power
            if account['buying_power'] < self.min_buying_power:
                result['alerts'].append({
                    'type': 'low_buying_power',
                    'severity': 'warning',
                    'message': f"Low buying power: ${account['buying_power']:.2f}"
                })

            # Check for pattern day trader warning
            if account.get('day_trade_count', 0) >= 3:
                result['alerts'].append({
                    'type': 'pdt_warning',
                    'severity': 'warning',
                    'message': f"Day trade count: {account['day_trade_count']}/4 - approaching PDT limit"
                })

            logger.info(f"Account: ${account['equity']:.2f} equity, ${account['buying_power']:.2f} buying power")

        except Exception as e:
            result['error'] = str(e)
            result['alerts'].append({
                'type': 'account_error',
                'severity': 'critical',
                'message': f"Could not fetch account: {e}"
            })

        return result

    async def _reconcile_positions(self) -> Dict[str, Any]:
        """Reconcile broker positions with database."""
        result = {
            'broker_positions': 0,
            'db_positions': 0,
            'mismatches': [],
            'alerts': []
        }

        try:
            # Get broker positions
            broker_positions = self.broker.get_positions()
            result['broker_positions'] = len(broker_positions)
            broker_symbols = {p['symbol'] for p in broker_positions}

            # Check position count
            if len(broker_positions) >= self.max_positions:
                result['alerts'].append({
                    'type': 'max_positions',
                    'severity': 'warning',
                    'message': f"At max positions: {len(broker_positions)}/{self.max_positions}"
                })

            # Get database positions (if table exists)
            if self.db_pool:
                try:
                    async with self.db_pool.acquire() as conn:
                        # Check if we track positions in DB
                        db_positions = await conn.fetch("""
                            SELECT symbol, quantity, entry_price, status
                            FROM positions
                            WHERE status = 'open'
                        """)
                        result['db_positions'] = len(db_positions)
                        db_symbols = {p['symbol'] for p in db_positions}

                        # Find mismatches
                        broker_only = broker_symbols - db_symbols
                        db_only = db_symbols - broker_symbols

                        if broker_only:
                            result['mismatches'].append({
                                'type': 'broker_only',
                                'symbols': list(broker_only),
                                'message': f"Positions in broker not in DB: {broker_only}"
                            })

                        if db_only:
                            result['mismatches'].append({
                                'type': 'db_only',
                                'symbols': list(db_only),
                                'message': f"Positions in DB not in broker: {db_only}"
                            })

                        if result['mismatches']:
                            result['alerts'].append({
                                'type': 'position_mismatch',
                                'severity': 'warning',
                                'message': f"Position sync issues detected: {len(result['mismatches'])} mismatches"
                            })

                except Exception as e:
                    logger.warning(f"Could not check DB positions: {e}")

            # Log positions
            for pos in broker_positions:
                logger.info(f"Position: {pos['symbol']} qty={pos['quantity']} P&L={pos['pnl_pct']:.2f}%")

            result['positions'] = broker_positions

        except Exception as e:
            result['error'] = str(e)
            result['alerts'].append({
                'type': 'position_error',
                'severity': 'critical',
                'message': f"Could not fetch positions: {e}"
            })

        return result

    async def _analyze_overnight_gaps(self) -> Dict[str, Any]:
        """Analyze overnight price gaps for open positions."""
        result = {
            'gaps': [],
            'alerts': []
        }

        try:
            positions = self.broker.get_positions()

            for position in positions:
                symbol = position['symbol']

                try:
                    bars = self.broker.get_bars(symbol, days=2)
                    if len(bars) >= 2:
                        prev_close = bars[-2]['close']
                        today_open = bars[-1]['open']
                        gap_pct = (today_open - prev_close) / prev_close

                        if abs(gap_pct) >= self.gap_alert_threshold:
                            gap_info = {
                                'symbol': symbol,
                                'prev_close': prev_close,
                                'today_open': today_open,
                                'gap_pct': round(gap_pct * 100, 2),
                                'direction': 'up' if gap_pct > 0 else 'down'
                            }
                            result['gaps'].append(gap_info)

                            # Alert on significant gaps against position
                            side = position.get('side', 'long')
                            if (side == 'long' and gap_pct < -self.gap_alert_threshold) or \
                               (side == 'short' and gap_pct > self.gap_alert_threshold):
                                result['alerts'].append({
                                    'type': 'adverse_gap',
                                    'severity': 'warning',
                                    'message': f"{symbol}: Adverse overnight gap of {gap_pct*100:.1f}%"
                                })

                except Exception as e:
                    logger.warning(f"Could not analyze gap for {symbol}: {e}")

        except Exception as e:
            result['error'] = str(e)

        return result

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate trading recommendations based on startup checks."""
        recommendations = []

        # Account recommendations
        account = results.get('account', {})
        if account.get('buying_power', 0) < self.min_buying_power:
            recommendations.append("Consider closing positions to free up buying power")

        # Position recommendations
        positions = results.get('positions', {})
        if positions.get('broker_positions', 0) >= self.max_positions:
            recommendations.append("At max positions - focus on managing existing positions")

        if positions.get('mismatches'):
            recommendations.append("Reconcile position mismatches before trading")

        # Gap recommendations
        gaps = results.get('gaps', [])
        adverse_gaps = [g for g in gaps if any(
            a.get('type') == 'adverse_gap' and g['symbol'] in a.get('message', '')
            for a in results.get('alerts', [])
        )]
        if adverse_gaps:
            recommendations.append(f"Review positions with adverse gaps: {[g['symbol'] for g in adverse_gaps]}")

        # General recommendation
        if results.get('status') == 'healthy':
            recommendations.append("All checks passed - ready for trading")

        return recommendations

    async def _send_startup_alert(self, results: Dict[str, Any]):
        """Send startup summary alert."""
        if not self.research_pool:
            return

        alerts = results.get('alerts', [])
        status = results.get('status', 'unknown')

        subject = f"Pre-Market Check: {status.upper()}"
        body = f"""Pre-market startup check completed.

Status: {status}
Alerts: {len(alerts)}

Account:
- Equity: ${results.get('account', {}).get('equity', 0):.2f}
- Buying Power: ${results.get('account', {}).get('buying_power', 0):.2f}

Positions: {results.get('positions', {}).get('broker_positions', 0)}

Alerts:
{chr(10).join(['- ' + a.get('message', '') for a in alerts]) if alerts else 'None'}

Recommendations:
{chr(10).join(['- ' + r for r in results.get('recommendations', [])])}
"""

        priority = 'high' if status in ['critical', 'warning'] else 'normal'

        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority)
                    VALUES ($1, 'big_bro', 'report', $2, $3, $4)
                """, self.agent_id, subject, body, priority)
            logger.info("Startup alert sent")
        except Exception as e:
            logger.warning(f"Could not send startup alert: {e}")


async def main():
    """Main entry point."""
    import yaml

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'dev_claude_config.yaml')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {'agent': {'id': 'dev_claude'}, 'trading': {}}

    monitor = StartupMonitor(config)

    try:
        await monitor.connect()
        results = await monitor.run_startup_checks()
        logger.info(f"Startup Check Result: {json.dumps(results, indent=2, default=str)}")
        return results
    finally:
        await monitor.close()


def cli():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='Pre-market Startup Monitor')
    args = parser.parse_args()
    asyncio.run(main())


if __name__ == "__main__":
    cli()
