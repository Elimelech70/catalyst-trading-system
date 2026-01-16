"""
Catalyst Trading System - Alerts Module
Name of Application: Catalyst Trading System
Name of file: alerts.py
Version: 1.0.0
Last Updated: 2025-12-28
Purpose: Email and notification system for all agents

REVISION HISTORY:
v1.0.0 (2025-12-28) - Initial implementation
  - Email alerts via SMTP
  - Trade alerts
  - Error alerts
  - Daily summaries
  - Priority-based formatting

Description:
This module provides email notification capabilities for all Catalyst agents.
It sends alerts to Craig for important events like trades, errors, and
daily summaries.

Usage:
    from alerts import AlertManager
    
    alerts = AlertManager()
    
    # Send trade alert
    alerts.send_trade_alert(
        agent_id='public_claude',
        action='buy',
        symbol='AAPL',
        quantity=100,
        price=150.00,
        reason='Bull flag pattern detected'
    )
    
    # Send error alert
    alerts.send_error_alert(
        agent_id='public_claude',
        error_type='broker_api',
        error_message='Order rejected',
        context='Attempted to buy AAPL'
    )
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, List

# Configure logging
logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages email alerts and notifications.
    
    Sends formatted emails to Craig for important system events.
    Supports priority levels that affect subject line formatting.
    
    Environment Variables:
        SMTP_HOST: SMTP server hostname (default: smtp.gmail.com)
        SMTP_PORT: SMTP server port (default: 587)
        SMTP_USER: SMTP username/email
        SMTP_PASSWORD: SMTP password or app password
        ALERT_EMAIL: Recipient email address
    
    Example:
        alerts = AlertManager()
        
        # Check if configured
        if alerts.is_configured:
            alerts.send_email("Test", "This is a test email")
    """
    
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        alert_email: str = None
    ):
        """
        Initialize AlertManager.
        
        Args:
            smtp_host: SMTP server (default: from env)
            smtp_port: SMTP port (default: from env)
            smtp_user: SMTP username (default: from env)
            smtp_password: SMTP password (default: from env)
            alert_email: Recipient email (default: from env)
        """
        self.smtp_host = smtp_host or os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.environ.get('SMTP_PORT', 587))
        self.smtp_user = smtp_user or os.environ.get('SMTP_USER')
        self.smtp_password = smtp_password or os.environ.get('SMTP_PASSWORD')
        self.alert_email = alert_email or os.environ.get('ALERT_EMAIL')
    
    @property
    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return all([self.smtp_user, self.smtp_password, self.alert_email])
    
    def send_email(
        self,
        subject: str,
        body: str,
        priority: str = 'normal',
        agent_id: str = 'system',
        html: bool = False
    ) -> bool:
        """
        Send an email alert.
        
        Args:
            subject: Email subject
            body: Email body
            priority: Priority level (low, normal, high, urgent)
            agent_id: Source agent ID
            html: If True, send as HTML email
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("Email not configured - skipping alert")
            return False
        
        try:
            msg = MIMEMultipart('alternative' if html else 'mixed')
            msg['From'] = self.smtp_user
            msg['To'] = self.alert_email
            
            # Add priority prefix to subject
            prefix = self._get_priority_prefix(priority)
            msg['Subject'] = f"{prefix}[Catalyst/{agent_id}] {subject}"
            
            # Format body with footer
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            full_body = f"""{body}

---
Agent: {agent_id}
Time: {timestamp}
Priority: {priority}
"""
            
            # Attach body
            if html:
                msg.attach(MIMEText(full_body, 'plain'))
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(full_body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _get_priority_prefix(self, priority: str) -> str:
        """Get emoji prefix for priority level."""
        prefixes = {
            'urgent': '🚨 URGENT: ',
            'high': '⚠️ ',
            'normal': '',
            'low': '📝 '
        }
        return prefixes.get(priority, '')
    
    def send_trade_alert(
        self,
        agent_id: str,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        reason: str,
        stop_loss: float = None,
        take_profit: float = None,
        position_value: float = None
    ) -> bool:
        """
        Send a trade execution alert.
        
        Args:
            agent_id: Source agent ID
            action: Trade action (buy, sell)
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            reason: Reason for trade
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            position_value: Total position value (optional)
            
        Returns:
            True if sent successfully
        """
        value = position_value or (quantity * price)
        
        subject = f"Trade: {action.upper()} {quantity} {symbol} @ ${price:.2f}"
        
        body = f"""Trade Executed

Action: {action.upper()}
Symbol: {symbol}
Quantity: {quantity}
Price: ${price:.2f}
Value: ${value:,.2f}

Reason: {reason}
"""
        
        if stop_loss:
            body += f"\nStop Loss: ${stop_loss:.2f}"
        if take_profit:
            body += f"\nTake Profit: ${take_profit:.2f}"
        
        return self.send_email(subject, body, 'normal', agent_id)
    
    def send_position_closed_alert(
        self,
        agent_id: str,
        symbol: str,
        quantity: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        hold_time: str,
        exit_reason: str
    ) -> bool:
        """
        Send position closed alert.
        
        Args:
            agent_id: Source agent ID
            symbol: Stock symbol
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price
            pnl: Profit/loss in dollars
            pnl_pct: Profit/loss percentage
            hold_time: How long position was held
            exit_reason: Why it was closed
            
        Returns:
            True if sent successfully
        """
        outcome = "WIN 🎉" if pnl > 0 else "LOSS 📉" if pnl < 0 else "BREAK-EVEN"
        priority = 'normal' if pnl >= 0 else 'high'
        
        subject = f"Position Closed: {symbol} {outcome} ${pnl:+,.2f} ({pnl_pct:+.1f}%)"
        
        body = f"""Position Closed

Symbol: {symbol}
Quantity: {quantity}
Entry: ${entry_price:.2f}
Exit: ${exit_price:.2f}

P&L: ${pnl:+,.2f} ({pnl_pct:+.1f}%)
Hold Time: {hold_time}
Exit Reason: {exit_reason}
"""
        
        return self.send_email(subject, body, priority, agent_id)
    
    def send_error_alert(
        self,
        agent_id: str,
        error_type: str,
        error_message: str,
        context: str = None,
        stack_trace: str = None
    ) -> bool:
        """
        Send an error alert.
        
        Args:
            agent_id: Source agent ID
            error_type: Type of error
            error_message: Error message
            context: Additional context (optional)
            stack_trace: Stack trace (optional)
            
        Returns:
            True if sent successfully
        """
        subject = f"Error: {error_type}"
        
        body = f"""Error Occurred

Type: {error_type}
Message: {error_message}
"""
        
        if context:
            body += f"\nContext: {context}"
        
        if stack_trace:
            body += f"\n\nStack Trace:\n{stack_trace}"
        
        return self.send_email(subject, body, 'high', agent_id)
    
    def send_risk_alert(
        self,
        agent_id: str,
        alert_type: str,
        current_value: float,
        limit_value: float,
        action_taken: str
    ) -> bool:
        """
        Send a risk management alert.
        
        Args:
            agent_id: Source agent ID
            alert_type: Type of risk alert
            current_value: Current value triggering alert
            limit_value: Limit that was hit
            action_taken: What action was taken
            
        Returns:
            True if sent successfully
        """
        pct = (current_value / limit_value * 100) if limit_value else 0
        
        subject = f"Risk Alert: {alert_type}"
        
        body = f"""Risk Alert

Alert Type: {alert_type}
Current Value: ${current_value:,.2f}
Limit: ${limit_value:,.2f}
Percentage: {pct:.1f}%

Action Taken: {action_taken}
"""
        
        return self.send_email(subject, body, 'urgent', agent_id)
    
    def send_daily_summary(
        self,
        agent_id: str,
        date: str,
        trades: int,
        winning_trades: int,
        losing_trades: int,
        gross_pnl: float,
        commissions: float,
        net_pnl: float,
        win_rate: float,
        observations: List[str] = None,
        learnings: List[str] = None
    ) -> bool:
        """
        Send daily trading summary.
        
        Args:
            agent_id: Source agent ID
            date: Trading date
            trades: Total trades
            winning_trades: Number of winning trades
            losing_trades: Number of losing trades
            gross_pnl: Gross P&L
            commissions: Total commissions
            net_pnl: Net P&L
            win_rate: Win rate percentage
            observations: Key observations (optional)
            learnings: Learnings from the day (optional)
            
        Returns:
            True if sent successfully
        """
        outcome_emoji = "📈" if net_pnl > 0 else "📉" if net_pnl < 0 else "➡️"
        
        subject = f"Daily Summary {date}: {outcome_emoji} ${net_pnl:+,.2f}"
        
        body = f"""Daily Trading Summary - {date}

Performance
-----------
Total Trades: {trades}
Winning: {winning_trades}
Losing: {losing_trades}
Win Rate: {win_rate:.1f}%

P&L
---
Gross P&L: ${gross_pnl:+,.2f}
Commissions: ${commissions:,.2f}
Net P&L: ${net_pnl:+,.2f}
"""
        
        if observations:
            body += "\n\nKey Observations\n----------------\n"
            for obs in observations[:5]:
                body += f"• {obs}\n"
        
        if learnings:
            body += "\n\nLearnings\n---------\n"
            for learning in learnings[:3]:
                body += f"• {learning}\n"
        
        return self.send_email(subject, body, 'normal', agent_id)
    
    def send_startup_notification(
        self,
        agent_id: str,
        mode: str,
        version: str,
        components: dict
    ) -> bool:
        """
        Send agent startup notification.
        
        Args:
            agent_id: Agent ID
            mode: Operating mode (paper, live)
            version: System version
            components: Component status dict
            
        Returns:
            True if sent successfully
        """
        subject = f"Agent Started: {agent_id}"
        
        component_status = "\n".join([
            f"  • {name}: {'✅' if status else '❌'}"
            for name, status in components.items()
        ])
        
        body = f"""Agent Started

Agent: {agent_id}
Mode: {mode}
Version: {version}

Component Status:
{component_status}
"""
        
        return self.send_email(subject, body, 'low', agent_id)
    
    def send_shutdown_notification(
        self,
        agent_id: str,
        reason: str,
        runtime: str,
        trades_today: int,
        pnl_today: float
    ) -> bool:
        """
        Send agent shutdown notification.
        
        Args:
            agent_id: Agent ID
            reason: Shutdown reason
            runtime: How long agent ran
            trades_today: Trades executed today
            pnl_today: P&L today
            
        Returns:
            True if sent successfully
        """
        subject = f"Agent Shutdown: {agent_id}"
        
        body = f"""Agent Shutdown

Agent: {agent_id}
Reason: {reason}
Runtime: {runtime}

Today's Activity:
  Trades: {trades_today}
  P&L: ${pnl_today:+,.2f}
"""
        
        return self.send_email(subject, body, 'low', agent_id)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get default AlertManager singleton.
    
    Returns:
        AlertManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = AlertManager()
    return _default_manager


def send_alert(
    subject: str,
    body: str,
    priority: str = 'normal',
    agent_id: str = 'system'
) -> bool:
    """
    Convenience function to send an alert.
    
    Args:
        subject: Email subject
        body: Email body
        priority: Priority level
        agent_id: Source agent
        
    Returns:
        True if sent successfully
    """
    return get_alert_manager().send_email(subject, body, priority, agent_id)


# =============================================================================
# TESTING
# =============================================================================

def test_alerts():
    """Test alert functionality."""
    print("Testing Alerts Module")
    print("=" * 50)
    
    alerts = AlertManager()
    
    print(f"\n1. Configuration Check")
    print(f"   SMTP Host: {alerts.smtp_host}")
    print(f"   SMTP Port: {alerts.smtp_port}")
    print(f"   SMTP User: {alerts.smtp_user[:20] + '...' if alerts.smtp_user else 'Not set'}")
    print(f"   Alert Email: {alerts.alert_email or 'Not set'}")
    print(f"   Is Configured: {alerts.is_configured}")
    
    if not alerts.is_configured:
        print("\n   ⚠️  Email not configured - skipping send tests")
        print("   Set SMTP_USER, SMTP_PASSWORD, and ALERT_EMAIL")
        return
    
    print("\n2. Send Test Email")
    response = input("   Send test email? (y/n): ")
    
    if response.lower() == 'y':
        success = alerts.send_email(
            subject="Test Alert",
            body="This is a test alert from the Catalyst Trading System.",
            priority='low',
            agent_id='test_module'
        )
        print(f"   Email sent: {success}")
    
    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == '__main__':
    test_alerts()
