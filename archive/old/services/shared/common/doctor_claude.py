"""
Catalyst Trading System - Doctor Claude
Name of Application: Catalyst Trading System
Name of file: doctor_claude.py
Version: 1.0.1
Last Updated: 2025-12-28
Purpose: Health monitoring and self-healing for all agents

REVISION HISTORY:
v1.0.1 (2025-12-28) - Schema fix
  - Fixed exit_time → closed_at column name in trading health check

v1.0.0 (2025-12-28) - Initial implementation
  - Agent health monitoring
  - Database health checks
  - Message queue monitoring
  - Automated alerting
  - Daily health reports

Description:
Doctor Claude watches over all trading agents and the consciousness
framework. It runs via cron every 5 minutes to check:
- Agent status (are they waking up on schedule?)
- Database connectivity and performance
- Pending messages (are they being processed?)
- Error rates
- Budget usage

When issues are detected, Doctor Claude alerts Craig and can take
corrective actions.

Usage:
    # Run health check
    python doctor_claude.py
    
    # Run daily report
    python doctor_claude.py daily_report
"""

import os
import sys
import asyncio
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

# Add shared to path if running standalone
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alerts import AlertManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    healthy: bool
    message: str
    details: Optional[Dict] = None


class DoctorClaude:
    """
    Health monitoring for all Catalyst agents.
    
    Doctor Claude performs regular health checks on:
    - Agent states (are they active when they should be?)
    - Database connectivity and performance
    - Message queues (are messages being processed?)
    - Error rates and patterns
    - Budget consumption
    
    When issues are detected, it sends alerts and can take
    corrective actions.
    
    Example:
        pool = await asyncpg.create_pool(RESEARCH_DATABASE_URL)
        doctor = DoctorClaude(pool)
        
        results = await doctor.run_health_check()
        
        if not results['overall_healthy']:
            print("Issues detected!")
            for issue in results['issues']:
                print(f"  - {issue}")
    """
    
    def __init__(self, research_pool: asyncpg.Pool, trading_pool: asyncpg.Pool = None):
        """
        Initialize Doctor Claude.
        
        Args:
            research_pool: Connection pool for research database
            trading_pool: Connection pool for trading database (optional)
        """
        self.research_pool = research_pool
        self.trading_pool = trading_pool
        self.alerts = AlertManager()
    
    # =========================================================================
    # AGENT HEALTH
    # =========================================================================
    
    async def check_agent_health(self) -> HealthCheckResult:
        """
        Check health of all agents.
        
        Checks:
        - Last wake time (stale if > 2 hours during market hours)
        - Error count (concerning if >= 5 today)
        - Budget usage (warning if > 90%)
        
        Returns:
            HealthCheckResult with agent status
        """
        issues = []
        agent_details = {}
        
        try:
            async with self.research_pool.acquire() as conn:
                agents = await conn.fetch("""
                    SELECT agent_id, current_mode, last_wake_at, last_action_at,
                           api_spend_today, daily_budget, error_count_today, 
                           status_message, last_error, last_error_at
                    FROM claude_state
                    ORDER BY agent_id
                """)
                
                now = datetime.now(timezone.utc)
                
                for agent in agents:
                    agent_id = agent['agent_id']
                    health = self._assess_agent(agent, now)
                    agent_details[agent_id] = health
                    
                    if not health['healthy']:
                        issues.extend([f"{agent_id}: {issue}" for issue in health['issues']])
            
            healthy = len(issues) == 0
            
            return HealthCheckResult(
                name="Agent Health",
                healthy=healthy,
                message=f"{len(agent_details)} agents checked, {len(issues)} issues",
                details={'agents': agent_details, 'issues': issues}
            )
            
        except Exception as e:
            logger.error(f"Agent health check failed: {e}")
            return HealthCheckResult(
                name="Agent Health",
                healthy=False,
                message=f"Check failed: {str(e)}"
            )
    
    def _assess_agent(self, agent: asyncpg.Record, now: datetime) -> Dict:
        """Assess individual agent health."""
        health = {
            'healthy': True,
            'mode': agent['current_mode'],
            'last_wake': agent['last_wake_at'].isoformat() if agent['last_wake_at'] else None,
            'budget_used': f"{float(agent['api_spend_today'] or 0):.2f}/{float(agent['daily_budget'] or 5):.2f}",
            'errors_today': agent['error_count_today'] or 0,
            'status': agent['status_message'],
            'issues': []
        }
        
        # Check for stale agent
        if agent['last_wake_at']:
            last_wake = agent['last_wake_at']
            if last_wake.tzinfo is None:
                last_wake = last_wake.replace(tzinfo=timezone.utc)
            
            time_since_wake = now - last_wake
            
            # Only flag if > 4 hours (allowing for market closed periods)
            if time_since_wake > timedelta(hours=4):
                health['issues'].append(f"No activity for {time_since_wake}")
                health['healthy'] = False
        
        # Check for high error count
        error_count = agent['error_count_today'] or 0
        if error_count >= 10:
            health['issues'].append(f"Critical error count: {error_count}")
            health['healthy'] = False
        elif error_count >= 5:
            health['issues'].append(f"High error count: {error_count}")
            health['healthy'] = False
        
        # Check budget usage
        spend = float(agent['api_spend_today'] or 0)
        budget = float(agent['daily_budget'] or 5)
        if budget > 0:
            usage_pct = spend / budget
            if usage_pct >= 1.0:
                health['issues'].append(f"Budget exhausted: ${spend:.2f}/${budget:.2f}")
                health['healthy'] = False
            elif usage_pct >= 0.9:
                health['issues'].append(f"Budget nearly exhausted: {usage_pct:.0%}")
        
        # Check for recent errors
        if agent['last_error_at']:
            last_error_at = agent['last_error_at']
            if last_error_at.tzinfo is None:
                last_error_at = last_error_at.replace(tzinfo=timezone.utc)
            
            if now - last_error_at < timedelta(minutes=30):
                health['issues'].append(f"Recent error: {agent['last_error'][:50]}")
        
        return health
    
    # =========================================================================
    # DATABASE HEALTH
    # =========================================================================
    
    async def check_database_health(self) -> HealthCheckResult:
        """
        Check database connectivity and performance.
        
        Checks:
        - Connectivity (can we query?)
        - Connection count (warning if near limit)
        - Response time (warning if slow)
        
        Returns:
            HealthCheckResult with database status
        """
        issues = []
        details = {}
        
        try:
            # Check research database
            start = datetime.now()
            async with self.research_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                
                # Get connection count
                count = await conn.fetchval("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE datname = current_database()
                """)
                details['research_connections'] = count
            
            research_time = (datetime.now() - start).total_seconds() * 1000
            details['research_response_ms'] = round(research_time, 1)
            
            if research_time > 1000:
                issues.append(f"Research DB slow: {research_time:.0f}ms")
            
            if count > 40:  # Warning at 40 of ~47
                issues.append(f"High connection count: {count}/47")
            
            # Check trading database if available
            if self.trading_pool:
                start = datetime.now()
                async with self.trading_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                    
                    count = await conn.fetchval("""
                        SELECT count(*) FROM pg_stat_activity 
                        WHERE datname = current_database()
                    """)
                    details['trading_connections'] = count
                
                trading_time = (datetime.now() - start).total_seconds() * 1000
                details['trading_response_ms'] = round(trading_time, 1)
                
                if trading_time > 1000:
                    issues.append(f"Trading DB slow: {trading_time:.0f}ms")
            
            healthy = len(issues) == 0
            
            return HealthCheckResult(
                name="Database Health",
                healthy=healthy,
                message=f"Response: {details.get('research_response_ms', '?')}ms, Connections: {details.get('research_connections', '?')}",
                details=details
            )
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return HealthCheckResult(
                name="Database Health",
                healthy=False,
                message=f"Check failed: {str(e)}"
            )
    
    # =========================================================================
    # MESSAGE QUEUE HEALTH
    # =========================================================================
    
    async def check_message_health(self) -> HealthCheckResult:
        """
        Check message queue health.
        
        Checks:
        - Pending message count
        - Old unprocessed messages (> 1 hour)
        - Message processing rate
        
        Returns:
            HealthCheckResult with message status
        """
        issues = []
        details = {}
        
        try:
            async with self.research_pool.acquire() as conn:
                # Count pending messages
                pending = await conn.fetchval("""
                    SELECT COUNT(*) FROM claude_messages WHERE status = 'pending'
                """)
                details['pending_count'] = pending
                
                # Find old pending messages
                old_messages = await conn.fetch("""
                    SELECT id, from_agent, to_agent, subject, created_at
                    FROM claude_messages
                    WHERE status = 'pending'
                      AND created_at < NOW() - INTERVAL '1 hour'
                    ORDER BY created_at
                    LIMIT 10
                """)
                
                details['old_messages'] = len(old_messages)
                
                if old_messages:
                    issues.append(f"{len(old_messages)} messages pending > 1 hour")
                    details['old_message_list'] = [
                        {
                            'id': m['id'],
                            'from': m['from_agent'],
                            'to': m['to_agent'],
                            'subject': m['subject'],
                            'age': str(datetime.now(timezone.utc) - m['created_at'].replace(tzinfo=timezone.utc))
                        }
                        for m in old_messages
                    ]
                
                # Count messages processed in last hour
                processed = await conn.fetchval("""
                    SELECT COUNT(*) FROM claude_messages 
                    WHERE status = 'processed'
                      AND processed_at > NOW() - INTERVAL '1 hour'
                """)
                details['processed_last_hour'] = processed
            
            healthy = len(issues) == 0
            
            return HealthCheckResult(
                name="Message Queue",
                healthy=healthy,
                message=f"Pending: {pending}, Processed (1h): {processed}",
                details=details
            )
            
        except Exception as e:
            logger.error(f"Message health check failed: {e}")
            return HealthCheckResult(
                name="Message Queue",
                healthy=False,
                message=f"Check failed: {str(e)}"
            )
    
    # =========================================================================
    # TRADING HEALTH (if trading pool available)
    # =========================================================================
    
    async def check_trading_health(self) -> Optional[HealthCheckResult]:
        """
        Check trading system health.
        
        Checks:
        - Open positions
        - Stuck orders
        - Today's P&L
        
        Returns:
            HealthCheckResult or None if trading pool not available
        """
        if not self.trading_pool:
            return None
        
        issues = []
        details = {}
        
        try:
            async with self.trading_pool.acquire() as conn:
                # Check for open positions
                positions = await conn.fetchval("""
                    SELECT COUNT(*) FROM positions WHERE status = 'open'
                """)
                details['open_positions'] = positions
                
                # Check for stuck orders (pending > 5 minutes)
                stuck = await conn.fetch("""
                    SELECT * FROM orders
                    WHERE status IN ('submitted', 'pending', 'accepted')
                      AND submitted_at < NOW() - INTERVAL '5 minutes'
                """)
                details['stuck_orders'] = len(stuck)
                
                if stuck:
                    issues.append(f"{len(stuck)} orders stuck > 5 minutes")
                
                # Today's P&L
                pnl = await conn.fetchrow("""
                    SELECT
                        COALESCE(SUM(realized_pnl), 0) as total_pnl,
                        COUNT(*) as closed_positions
                    FROM positions
                    WHERE status = 'closed'
                      AND closed_at >= CURRENT_DATE
                """)
                
                if pnl:
                    details['today_pnl'] = float(pnl['total_pnl'])
                    details['closed_today'] = pnl['closed_positions']
            
            healthy = len(issues) == 0
            
            return HealthCheckResult(
                name="Trading System",
                healthy=healthy,
                message=f"Positions: {positions}, Today P&L: ${details.get('today_pnl', 0):+,.2f}",
                details=details
            )
            
        except Exception as e:
            logger.error(f"Trading health check failed: {e}")
            return HealthCheckResult(
                name="Trading System",
                healthy=False,
                message=f"Check failed: {str(e)}"
            )
    
    # =========================================================================
    # MAIN HEALTH CHECK
    # =========================================================================
    
    async def run_health_check(self) -> Dict:
        """
        Run complete health check.
        
        Returns:
            Dict with overall status and individual check results
        """
        logger.info("Running health check...")
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_healthy': True,
            'checks': {},
            'issues': []
        }
        
        # Run all checks
        checks = [
            await self.check_agent_health(),
            await self.check_database_health(),
            await self.check_message_health(),
        ]
        
        # Add trading check if available
        trading_check = await self.check_trading_health()
        if trading_check:
            checks.append(trading_check)
        
        # Aggregate results
        for check in checks:
            results['checks'][check.name] = {
                'healthy': check.healthy,
                'message': check.message,
                'details': check.details
            }
            
            if not check.healthy:
                results['overall_healthy'] = False
                if check.details and 'issues' in check.details:
                    results['issues'].extend(check.details['issues'])
                else:
                    results['issues'].append(f"{check.name}: {check.message}")
        
        # Send alert if unhealthy
        if not results['overall_healthy'] and results['issues']:
            self._send_health_alert(results)
        
        return results
    
    def _send_health_alert(self, results: Dict):
        """Send alert for health issues."""
        issues_text = "\n".join([f"• {issue}" for issue in results['issues'][:10]])
        
        self.alerts.send_email(
            subject="Health Check Failed",
            body=f"""Health Check Alert

{len(results['issues'])} issue(s) detected:

{issues_text}

Check the system and resolve issues.
""",
            priority='high',
            agent_id='doctor_claude'
        )
    
    # =========================================================================
    # DAILY REPORT
    # =========================================================================
    
    async def generate_daily_report(self) -> Dict:
        """
        Generate comprehensive daily health report.
        
        Returns:
            Dict with daily statistics and summary
        """
        logger.info("Generating daily report...")
        
        report = {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'agents': {},
            'activity': {},
            'issues_detected': 0
        }
        
        try:
            async with self.research_pool.acquire() as conn:
                # Agent summary
                agents = await conn.fetch("""
                    SELECT agent_id, current_mode, api_spend_today, api_spend_month,
                           daily_budget, error_count_today
                    FROM claude_state
                    ORDER BY agent_id
                """)
                
                for agent in agents:
                    report['agents'][agent['agent_id']] = {
                        'mode': agent['current_mode'],
                        'spend_today': float(agent['api_spend_today'] or 0),
                        'spend_month': float(agent['api_spend_month'] or 0),
                        'budget': float(agent['daily_budget'] or 5),
                        'errors_today': agent['error_count_today'] or 0
                    }
                
                # Activity counts (last 24 hours)
                observations = await conn.fetchval("""
                    SELECT COUNT(*) FROM claude_observations
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
                
                learnings = await conn.fetchval("""
                    SELECT COUNT(*) FROM claude_learnings
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
                
                messages = await conn.fetchval("""
                    SELECT COUNT(*) FROM claude_messages
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
                
                report['activity'] = {
                    'observations_24h': observations,
                    'learnings_24h': learnings,
                    'messages_24h': messages
                }
            
            # Send report
            self._send_daily_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Daily report generation failed: {e}")
            return {'error': str(e)}
    
    def _send_daily_report(self, report: Dict):
        """Send daily report email."""
        agent_summary = "\n".join([
            f"  • {aid}: ${data['spend_today']:.2f}/${data['budget']:.2f}, {data['errors_today']} errors"
            for aid, data in report['agents'].items()
        ])
        
        self.alerts.send_email(
            subject=f"Daily Health Report - {report['date']}",
            body=f"""Catalyst Daily Health Report
Date: {report['date']}

Agent Status:
{agent_summary}

Activity (24h):
  • Observations: {report['activity'].get('observations_24h', 0)}
  • Learnings: {report['activity'].get('learnings_24h', 0)}
  • Messages: {report['activity'].get('messages_24h', 0)}
""",
            priority='low',
            agent_id='doctor_claude'
        )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Run Doctor Claude."""
    # Load environment
    from dotenv import load_dotenv
    load_dotenv('/root/catalyst/config/shared.env')
    
    research_url = os.environ.get('RESEARCH_DATABASE_URL')
    trading_url = os.environ.get('DATABASE_URL')
    
    if not research_url:
        logger.error("RESEARCH_DATABASE_URL not set")
        sys.exit(1)
    
    # Create pools
    research_pool = await asyncpg.create_pool(research_url, min_size=1, max_size=3)
    trading_pool = None
    
    if trading_url:
        try:
            trading_pool = await asyncpg.create_pool(trading_url, min_size=1, max_size=3)
        except Exception as e:
            logger.warning(f"Could not connect to trading database: {e}")
    
    try:
        doctor = DoctorClaude(research_pool, trading_pool)
        
        # Check for command line argument
        if len(sys.argv) > 1 and sys.argv[1] == 'daily_report':
            report = await doctor.generate_daily_report()
            print(f"\nDaily Report Generated")
            print(f"Date: {report.get('date')}")
            print(f"Agents: {len(report.get('agents', {}))}")
        else:
            results = await doctor.run_health_check()
            
            # Print summary
            status = "✅ HEALTHY" if results['overall_healthy'] else "❌ ISSUES DETECTED"
            print(f"\n{status}")
            print(f"Timestamp: {results['timestamp']}")
            
            if results['issues']:
                print(f"\nIssues ({len(results['issues'])}):")
                for issue in results['issues'][:10]:
                    print(f"  • {issue}")
            
            print(f"\nChecks:")
            for name, check in results['checks'].items():
                icon = "✅" if check['healthy'] else "❌"
                print(f"  {icon} {name}: {check['message']}")
    
    finally:
        await research_pool.close()
        if trading_pool:
            await trading_pool.close()


if __name__ == '__main__':
    asyncio.run(main())
