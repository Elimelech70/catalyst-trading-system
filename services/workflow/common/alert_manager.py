#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: alert_manager.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: Email alert system for autonomous trading

Description:
Centralized alert management for all services.
Supports:
- Email notifications via SMTP
- Severity-based routing
- Rate limiting
- Informational alerts ("here's what I did")
- Alert cooldowns
"""

import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert types"""
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    EMERGENCY_STOP = "emergency_stop"
    POSITION_LIMIT = "position_limit"
    SERVICE_ERROR = "service_error"
    TRADE_EXECUTED = "trade_executed"
    RISK_WARNING = "risk_warning"
    DAILY_SUMMARY = "daily_summary"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"


class AlertManager:
    """
    Manages email alerts with rate limiting and routing.

    Usage:
        alert_manager = AlertManager()
        await alert_manager.send_alert(
            alert_type=AlertType.EMERGENCY_STOP,
            severity=AlertSeverity.CRITICAL,
            subject="Emergency Stop Triggered",
            message="Trading halted due to daily loss limit",
            data={"daily_pnl": -2000, "positions_closed": 5}
        )
    """

    def __init__(self):
        # SMTP configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_username)
        self.smtp_tls = os.getenv("SMTP_TLS", "true").lower() == "true"

        # Alert recipients
        self.critical_emails = self._parse_emails(os.getenv("ALERT_EMAIL_CRITICAL", ""))
        self.warning_emails = self._parse_emails(os.getenv("ALERT_EMAIL_WARNING", ""))
        self.info_emails = self._parse_emails(os.getenv("ALERT_EMAIL_INFO", ""))

        # Rate limiting
        self.cooldown_minutes = int(os.getenv("ALERT_COOLDOWN_MINUTES", 15))
        self.max_alerts_per_hour = int(os.getenv("ALERT_MAX_PER_HOUR", 20))

        # Track sent alerts for rate limiting
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_count_per_hour: Dict[str, int] = defaultdict(int)
        self._hour_reset_time: Dict[str, datetime] = {}

        # Check if configured
        self.enabled = bool(self.smtp_username and self.smtp_password)
        if not self.enabled:
            logger.warning("Alert manager not configured (missing SMTP credentials)")
        else:
            logger.info(f"Alert manager initialized (SMTP: {self.smtp_host}:{self.smtp_port})")

    def _parse_emails(self, email_str: str) -> List[str]:
        """Parse comma-separated email list"""
        if not email_str:
            return []
        return [email.strip() for email in email_str.split(",") if email.strip()]

    def _get_recipients(self, severity: AlertSeverity) -> List[str]:
        """Get recipients based on severity"""
        if severity == AlertSeverity.CRITICAL:
            return self.critical_emails
        elif severity == AlertSeverity.WARNING:
            return self.warning_emails
        else:
            return self.info_emails

    def _check_rate_limit(self, alert_type: AlertType) -> bool:
        """Check if alert is rate-limited"""
        now = datetime.now()
        alert_key = alert_type.value

        # Check cooldown
        if alert_key in self._last_alert_time:
            time_since_last = now - self._last_alert_time[alert_key]
            if time_since_last < timedelta(minutes=self.cooldown_minutes):
                logger.warning(
                    f"Alert {alert_type.value} rate-limited (cooldown: {self.cooldown_minutes}min)"
                )
                return False

        # Check hourly limit
        if alert_key in self._hour_reset_time:
            if now - self._hour_reset_time[alert_key] > timedelta(hours=1):
                # Reset hourly counter
                self._alert_count_per_hour[alert_key] = 0
                self._hour_reset_time[alert_key] = now
        else:
            self._hour_reset_time[alert_key] = now

        if self._alert_count_per_hour[alert_key] >= self.max_alerts_per_hour:
            logger.warning(
                f"Alert {alert_type.value} rate-limited (max {self.max_alerts_per_hour}/hour)"
            )
            return False

        return True

    async def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        subject: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        bypass_rate_limit: bool = False
    ) -> bool:
        """
        Send email alert.

        Args:
            alert_type: Type of alert
            severity: Severity level
            subject: Email subject
            message: Email body message
            data: Additional data to include
            bypass_rate_limit: Skip rate limiting (for critical alerts)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Alert not sent (disabled): {subject}")
            return False

        # Check rate limit (unless bypassed)
        if not bypass_rate_limit:
            if not self._check_rate_limit(alert_type):
                return False

        # Get recipients
        recipients = self._get_recipients(severity)
        if not recipients:
            logger.warning(f"No recipients for {severity.value} alerts")
            return False

        # Build email
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[{severity.value.upper()}] Catalyst Trading - {subject}"

            # Build email body
            body = self._build_email_body(
                alert_type=alert_type,
                severity=severity,
                message=message,
                data=data
            )

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            await self._send_email(msg, recipients)

            # Update rate limiting trackers
            alert_key = alert_type.value
            self._last_alert_time[alert_key] = datetime.now()
            self._alert_count_per_hour[alert_key] += 1

            logger.info(f"Alert sent: {alert_type.value} to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}", exc_info=True)
            return False

    def _build_email_body(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        data: Optional[Dict[str, Any]]
    ) -> str:
        """Build formatted email body"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

        body = f"""
╔══════════════════════════════════════════════════════════════╗
║     CATALYST TRADING SYSTEM - AUTOMATED ALERT                ║
╚══════════════════════════════════════════════════════════════╝

Severity: {severity.value.upper()}
Alert Type: {alert_type.value}
Timestamp: {timestamp}

───────────────────────────────────────────────────────────────

{message}

───────────────────────────────────────────────────────────────
"""

        if data:
            body += "\nDATA:\n"
            body += json.dumps(data, indent=2, default=str)
            body += "\n\n───────────────────────────────────────────────────────────────\n"

        body += """
This is an automated message from the Catalyst Trading System.

🤖 Generated with Claude Code
https://claude.com/claude-code

───────────────────────────────────────────────────────────────
"""

        return body

    async def _send_email(self, msg: MIMEMultipart, recipients: List[str]):
        """Send email via SMTP (async wrapper)"""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email_sync, msg, recipients)

    def _send_email_sync(self, msg: MIMEMultipart, recipients: List[str]):
        """Send email via SMTP (synchronous)"""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_tls:
                    server.starttls()

                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)

                server.send_message(msg)

            logger.debug(f"Email sent to {len(recipients)} recipients")

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise

    # Convenience methods for common alerts

    async def alert_emergency_stop(
        self,
        reason: str,
        daily_pnl: float,
        positions_closed: int,
        orders_cancelled: int
    ):
        """Send emergency stop alert"""
        return await self.send_alert(
            alert_type=AlertType.EMERGENCY_STOP,
            severity=AlertSeverity.CRITICAL,
            subject="🛑 EMERGENCY STOP - Trading Halted",
            message=f"""
EMERGENCY STOP EXECUTED

I've stopped trading because: {reason}

Actions Taken:
  • Closed {positions_closed} positions
  • Cancelled {orders_cancelled} pending orders
  • Daily P&L: ${daily_pnl:,.2f}
  • Trading status: HALTED

Manual restart required when ready.
To restart: POST /api/v1/workflow/start
            """,
            data={
                "reason": reason,
                "daily_pnl": daily_pnl,
                "positions_closed": positions_closed,
                "orders_cancelled": orders_cancelled,
                "action_required": "Manual restart required"
            },
            bypass_rate_limit=True  # Always send critical alerts
        )

    async def alert_daily_loss_warning(
        self,
        current_loss: float,
        max_loss: float,
        percentage: float
    ):
        """Send daily loss warning"""
        return await self.send_alert(
            alert_type=AlertType.DAILY_LOSS_LIMIT,
            severity=AlertSeverity.WARNING,
            subject=f"⚠️ Daily Loss Warning ({percentage:.0f}% of limit)",
            message=f"""
APPROACHING DAILY LOSS LIMIT

Current daily P&L: ${current_loss:,.2f}
Maximum daily loss: ${max_loss:,.2f}
Percentage: {percentage:.1f}%

This is a warning. If losses reach {max_loss:,.2f}, an emergency stop will be triggered automatically.
            """,
            data={
                "current_loss": current_loss,
                "max_loss": max_loss,
                "percentage": percentage,
                "remaining": max_loss - abs(current_loss)
            }
        )

    async def alert_workflow_started(
        self,
        cycle_id: str,
        mode: str,
        scan_frequency: int
    ):
        """Send workflow started alert"""
        return await self.send_alert(
            alert_type=AlertType.WORKFLOW_STARTED,
            severity=AlertSeverity.INFO,
            subject=f"🚀 Autonomous Workflow Started",
            message=f"""
AUTONOMOUS TRADING WORKFLOW STARTED

Cycle ID: {cycle_id}
Mode: {mode}
Scan Frequency: Every {scan_frequency // 60} minutes

The system will scan the market, filter candidates, validate risk, and execute trades automatically.
You'll receive updates on trades executed and any risk events.
            """,
            data={
                "cycle_id": cycle_id,
                "mode": mode,
                "scan_frequency": scan_frequency
            }
        )

    async def alert_trades_executed(
        self,
        cycle_id: str,
        trades: List[Dict[str, Any]],
        total_risk: float
    ):
        """Send trades executed alert"""
        trade_summary = "\n".join([
            f"  • {trade['symbol']}: {trade['quantity']} shares @ ${trade.get('price', 'market')}"
            for trade in trades
        ])

        return await self.send_alert(
            alert_type=AlertType.TRADE_EXECUTED,
            severity=AlertSeverity.INFO,
            subject=f"✅ {len(trades)} Trades Executed Automatically",
            message=f"""
TRADES EXECUTED

Cycle: {cycle_id}
Trades: {len(trades)}
Total Risk: ${total_risk:,.2f}

Positions Opened:
{trade_summary}

All trades passed risk validation and were executed automatically.
            """,
            data={
                "cycle_id": cycle_id,
                "trade_count": len(trades),
                "total_risk": total_risk,
                "trades": trades
            }
        )

    async def alert_daily_summary(
        self,
        date: str,
        trades_executed: int,
        daily_pnl: float,
        win_rate: float,
        total_positions: int
    ):
        """Send daily summary alert"""
        return await self.send_alert(
            alert_type=AlertType.DAILY_SUMMARY,
            severity=AlertSeverity.INFO,
            subject=f"📊 Daily Trading Summary - {date}",
            message=f"""
DAILY TRADING SUMMARY

Date: {date}
Trades Executed: {trades_executed}
Daily P&L: ${daily_pnl:,.2f}
Win Rate: {win_rate:.1f}%
Open Positions: {total_positions}

The system traded autonomously throughout the day. All trades followed risk management rules.
            """,
            data={
                "date": date,
                "trades_executed": trades_executed,
                "daily_pnl": daily_pnl,
                "win_rate": win_rate,
                "total_positions": total_positions
            }
        )


# Global singleton instance
alert_manager = AlertManager()


# Test function
async def test_alert_manager():
    """Test the alert manager"""
    logger.info("Testing Alert Manager...")

    # Test emergency stop alert
    result = await alert_manager.alert_emergency_stop(
        reason="Daily loss limit exceeded",
        daily_pnl=-2050.00,
        positions_closed=5,
        orders_cancelled=3
    )

    if result:
        print("✅ Emergency stop alert sent")
    else:
        print("⚠️ Alert not sent (check SMTP configuration)")

    return result


if __name__ == '__main__':
    import asyncio
    logging.basicConfig(level=logging.INFO)

    print("Testing Alert Manager...")
    print("=" * 70)
    print(f"SMTP Host: {os.getenv('SMTP_HOST', 'Not configured')}")
    print(f"SMTP Port: {os.getenv('SMTP_PORT', 'Not configured')}")
    print(f"From: {os.getenv('SMTP_FROM', 'Not configured')}")
    print(f"Critical Recipients: {os.getenv('ALERT_EMAIL_CRITICAL', 'Not configured')}")
    print("=" * 70)

    asyncio.run(test_alert_manager())
