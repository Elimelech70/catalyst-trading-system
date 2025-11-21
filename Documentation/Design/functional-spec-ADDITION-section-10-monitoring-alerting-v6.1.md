# Functional Specification v6.1 - Section 10: Monitoring & Alerting

**Name of Application**: Catalyst Trading System  
**Name of file**: functional-spec-section-10-monitoring-alerting-v6.1.md  
**Version**: 6.1.0  
**Last Updated**: 2025-10-27  
**Purpose**: Complete monitoring and alerting specifications with DigitalOcean Email Service integration

---

## 10. Monitoring & Alerting System

### 10.1 Overview

The Catalyst Trading System requires real-time monitoring and alerting to ensure trading health, detect issues, and respond to critical events. The alerting system uses **DigitalOcean Email Service** (SMTP) for reliable notification delivery.

**Alert Philosophy**:
- **Critical alerts**: System has ALREADY taken action - notification is informational
- **Warning alerts**: Attention needed - degraded performance, approaching limits
- **Info alerts**: Awareness only - daily summaries, milestone events

**Key Principle**: The system acts autonomously when risk criteria are met, then informs the user of actions taken.

---

### 10.2 System Architecture

#### 10.2.1 Alert Flow

```
Risk Event Detected
    ↓
System Takes Autonomous Action
    (Emergency stop, close positions, cancel orders)
    ↓
Alert Manager Triggered
    ↓
Template Rendered with Action Details
    ↓
DigitalOcean SMTP Sends Email
    ↓
Database Tracks Alert History
    ↓
User Receives Informational Notification
```

#### 10.2.2 Components

**1. Alert Manager Service** (`services/alerting/alert_manager.py`)
- Centralized alert coordination
- Template rendering
- Severity-based routing
- Database tracking
- Rate limiting and cooldown

**2. Email Client** (`services/shared/email_client.py`)
- DigitalOcean SMTP integration
- Connection pooling
- Retry logic
- Error handling

**3. Alert Templates** (Embedded in Alert Manager)
- HTML email templates
- Variable substitution
- Responsive design
- Actionable information

**4. Database Schema**
```sql
CREATE TABLE system_alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    subject TEXT NOT NULL,
    alert_data JSONB,
    recipients TEXT[],
    sent_successfully BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX idx_system_alerts_type ON system_alerts(alert_type);
CREATE INDEX idx_system_alerts_severity ON system_alerts(severity);
CREATE INDEX idx_system_alerts_created ON system_alerts(created_at DESC);
```

---

### 10.3 DigitalOcean Email Service Integration

#### 10.3.1 Configuration

**Environment Variables** (`.env`):
```bash
# =============================================================================
# EMAIL ALERTS CONFIGURATION - DigitalOcean Email Service
# =============================================================================
# DigitalOcean SMTP (Production)
SMTP_HOST=smtp.digitalocean.com
SMTP_PORT=587
SMTP_USERNAME=your-do-smtp-username
SMTP_PASSWORD=your-do-smtp-api-token
SMTP_FROM=catalyst-alerts@yourdomain.com
SMTP_TLS=true

# OR Gmail SMTP (Development/Testing)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_TLS=true

# Alert Recipients
ALERT_EMAIL_CRITICAL=trader@yourdomain.com,admin@yourdomain.com
ALERT_EMAIL_WARNING=trader@yourdomain.com
ALERT_EMAIL_INFO=trader@yourdomain.com

# Alert Configuration
ALERT_COOLDOWN_MINUTES=15  # Prevent spam - minimum time between same alerts
ALERT_BATCH_WINDOW_SECONDS=300  # Batch similar alerts within 5 minutes
ALERT_MAX_PER_HOUR=20  # Rate limiting - maximum alerts per hour
ENABLE_EMAIL_ALERTS=true
```

#### 10.3.2 DigitalOcean Email Service Setup

**Step 1: Create DigitalOcean Account & Enable Email Service**
1. Log into DigitalOcean Console
2. Navigate to Email Service section
3. Enable Email Service for your account
4. Note the SMTP endpoint: `smtp.digitalocean.com`

**Step 2: Domain Verification**
1. Add your domain (e.g., `yourdomain.com`)
2. Configure DNS records:
   - **SPF Record**: TXT record for sender verification
     ```
     v=spf1 include:_spf.digitalocean.com ~all
     ```
   - **DKIM Record**: TXT record for authentication (provided by DigitalOcean)
   - **DMARC Record**: TXT record for policy
     ```
     v=DMARC1; p=quarantine; rua=mailto:postmaster@yourdomain.com
     ```
3. Wait for DNS propagation (typically 15-60 minutes)
4. Verify domain status in DigitalOcean console

**Step 3: Generate SMTP Credentials**
1. In Email Service settings, generate API token
2. Copy SMTP username and API token
3. Configure sending limits (if needed)
4. Set up IP whitelisting (optional)

**Step 4: Test Email Connectivity**
```bash
# Test SMTP connection
python scripts/test_email.py
```

**Alternative: SendGrid Integration**
DigitalOcean also offers SendGrid integration for higher volume:
- Suitable for >10,000 emails/month
- Better deliverability for large volumes
- Additional analytics and tracking

#### 10.3.3 Docker Compose Configuration

**Critical Fix**: Ensure all services reference `.env` at project root:

```yaml
services:
  orchestration:
    build:
      context: ./services/orchestration
      dockerfile: Dockerfile
    container_name: catalyst-orchestration
    env_file: 
      - ./.env    # ✅ CORRECT - project root
    # ... rest of config

  workflow:
    build:
      context: ./services/workflow
      dockerfile: Dockerfile
    container_name: catalyst-workflow
    env_file: 
      - ./.env    # ✅ CORRECT - project root
    # ... rest of config

  # Repeat for all services: scanner, pattern, technical, risk-manager, 
  # trading, news, reporting
```

**Quick Fix Command**:
```bash
# Replace all ./config/.env with ./.env in docker-compose.yml
sed -i 's|./config/.env|./.env|g' docker-compose.yml

# Verify changes
grep -n "env_file" docker-compose.yml
```

---

### 10.4 Alert Severity Levels

| Severity | Icon | Description | System Behavior | Recipients |
|----------|------|-------------|----------------|------------|
| **CRITICAL** | 🔴 | Action ALREADY taken by system | Emergency stop executed, positions closed | All admins + trader |
| **WARNING** | 🟡 | Attention needed soon | Degraded performance, approaching limits | Primary trader |
| **INFO** | 🔵 | Informational only | Daily summaries, routine updates | Primary trader |

**Alert Response Model**:
- **CRITICAL**: "I've already stopped trading because daily loss hit -$2,000. Here's what I did..."
- **WARNING**: "Win rate declining to 48%. Consider reviewing strategy."
- **INFO**: "Daily summary: 8 trades, +$450 P&L, 62% win rate."

---

### 10.5 Critical Alert Types

#### 10.5.1 Emergency Stop Alert

**Trigger**: Emergency stop executed OR daily loss limit hit  
**Severity**: CRITICAL  
**Nature**: System has ALREADY stopped trading (informational)  
**Recipients**: All critical alert recipients

**Includes**:
- Reason for stop (daily loss limit, manual trigger, system error)
- Positions closed (symbols, quantities, P&L)
- Orders cancelled (count and list)
- Final P&L (realized, unrealized, daily total)
- Next steps (manual restart required)

**Template Variables**:
```python
{
    "timestamp": "2025-10-27T14:30:00Z",
    "reason": "Daily loss limit exceeded",
    "orders_cancelled": 3,
    "positions_closed": 5,
    "workflow_stopped": true,
    "daily_pnl": -2050.00,
    "realized_pnl": -1800.00,
    "closed_positions": [
        {"symbol": "TSLA", "quantity": 50, "pnl": -450.00},
        {"symbol": "AAPL", "quantity": 100, "pnl": -350.00}
    ]
}
```

#### 10.5.2 Daily Loss Limit Alert

**Trigger**: 75% (warning) or 100% (critical) of max daily loss  
**Severity**: WARNING (75%) / CRITICAL (100%)  
**Nature**: 
- 75%: WARNING - approaching limit
- 100%: CRITICAL - trading ALREADY stopped

**Recipients**: 
- 75%: Warning recipients
- 100%: Critical recipients

**Includes**:
- Current vs max loss
- Percentage of limit used
- Breakdown of losing trades
- Win rate analysis
- Recommended actions

**Template Variables**:
```python
{
    "current_loss": -1850.00,
    "max_loss": 2000.00,
    "loss_pct": 92.5,
    "losing_trades": [
        {"symbol": "TSLA", "pnl": -450.00},
        {"symbol": "NVDA", "pnl": -400.00}
    ],
    "win_rate": 54.2,
    "trades_today": 12,
    "recommendation": "Close losing positions or reduce position sizes"
}
```

#### 10.5.3 Position Risk Violation

**Trigger**: Position size or risk exceeds limits  
**Severity**: CRITICAL  
**Nature**: System has ALREADY rejected/closed position  
**Recipients**: Critical alert recipients

**Includes**:
- Violation type (size, risk, exposure)
- Position details (symbol, quantity, price)
- Risk metrics (exposure, R:R ratio)
- Action taken (rejected, closed, reduced)

#### 10.5.4 Service Down Alert

**Trigger**: Service health check fails for >60 seconds  
**Severity**: CRITICAL  
**Nature**: System is attempting auto-restart  
**Recipients**: Critical alert recipients

**Includes**:
- Service name and port
- Error details
- Recovery attempts (count, status)
- Impact assessment (trading affected?)
- Manual intervention steps

#### 10.5.5 Database Connection Error

**Trigger**: Database connection failures  
**Severity**: CRITICAL  
**Nature**: System is retrying with exponential backoff  
**Recipients**: Critical alert recipients

**Includes**:
- Connection details (host, port, database)
- Failure count
- Error message
- Retry status
- Recovery steps

---

### 10.6 Warning Alert Types

#### 10.6.1 Cron Job Failure

**Trigger**: Expected workflow doesn't execute within 5 minutes of schedule  
**Severity**: WARNING  
**Recipients**: Warning alert recipients

**Includes**:
- Expected vs actual time
- Delay duration
- Job details (cron expression, command)
- Manual trigger instructions

#### 10.6.2 Win Rate Declining

**Trigger**: Win rate drops below 50% (warning) or 40% (critical)  
**Severity**: WARNING (50%) / CRITICAL (40%)  
**Recipients**: Warning/Critical based on threshold

**Includes**:
- Current win rate
- Historical comparison (7-day, 30-day average)
- Performance breakdown (by symbol, pattern, time)
- Potential issues (slippage, poor entries, strategy fit)
- Recommendations (adjust strategy, reduce size, review patterns)

#### 10.6.3 API Rate Limit Warning

**Trigger**: Approaching API rate limits (>75% usage)  
**Severity**: WARNING  
**Recipients**: Warning alert recipients

**Includes**:
- Current usage vs limit (requests, data points)
- Usage breakdown (by service, endpoint)
- Reset time
- Throttling actions (automatic slowdown)
- Recommendations (reduce scan frequency, cache more data)

---

### 10.7 Informational Alert Types

#### 10.7.1 Daily Trading Summary

**Trigger**: End of trading day (4:00 PM ET / 5:00 AM Perth AWST)  
**Severity**: INFO  
**Schedule**: Cron-triggered daily  
**Recipients**: Info alert recipients

**Includes**:
- Daily P&L (total, realized, unrealized)
- Trade statistics (count, win rate, profit factor)
- Best/worst trades
- Workflow metrics (scans executed, candidates generated)
- Link to full report

**Template Variables**:
```python
{
    "date": "2025-10-27",
    "daily_pnl": 450.25,
    "trades_executed": 8,
    "win_rate": 62.5,
    "profit_factor": 1.45,
    "best_trade": {"symbol": "TSLA", "pnl": 420.00},
    "worst_trade": {"symbol": "NVDA", "pnl": -275.00},
    "scans_executed": 12,
    "candidates_generated": 45,
    "report_link": "http://catalyst-droplet:5009/api/v1/reports/daily/20251027"
}
```

#### 10.7.2 Weekly Performance Report

**Trigger**: Sunday evening (8:00 PM Perth AWST)  
**Severity**: INFO  
**Recipients**: Info alert recipients

**Includes**:
- Weekly summary (P&L, win rate, Sharpe ratio)
- Best/worst days
- Symbol performance
- Pattern effectiveness
- Risk metrics
- Recommendations for next week

---

### 10.8 Alert Service Implementation

#### 10.8.1 Email Client

```python
# services/shared/email_client.py

"""
Name of Application: Catalyst Trading System
Name of file: email_client.py
Version: 6.1.0
Purpose: DigitalOcean SMTP email client for alerts
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    smtp_host: str = os.getenv('SMTP_HOST', 'smtp.digitalocean.com')
    smtp_port: int = int(os.getenv('SMTP_PORT', '587'))
    smtp_username: str = os.getenv('SMTP_USERNAME', '')
    smtp_password: str = os.getenv('SMTP_PASSWORD', '')
    smtp_from: str = os.getenv('SMTP_FROM', 'catalyst@localhost')
    smtp_tls: bool = os.getenv('SMTP_TLS', 'true').lower() == 'true'
    
    cooldown_minutes: int = int(os.getenv('ALERT_COOLDOWN_MINUTES', '15'))
    max_per_hour: int = int(os.getenv('ALERT_MAX_PER_HOUR', '20'))


class EmailClient:
    """DigitalOcean SMTP email client with rate limiting"""
    
    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()
        self.alert_history = {}  # Track sent alerts for cooldown
        self.hourly_count = 0
        self.hour_window = datetime.now()
        
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now()
        
        # Reset hourly counter if new hour
        if now.hour != self.hour_window.hour:
            self.hourly_count = 0
            self.hour_window = now
            
        if self.hourly_count >= self.config.max_per_hour:
            logger.warning(f"Alert rate limit reached: {self.hourly_count}/{self.config.max_per_hour} per hour")
            return False
            
        return True
    
    def _check_cooldown(self, alert_key: str) -> bool:
        """Check if alert is in cooldown period"""
        if alert_key in self.alert_history:
            last_sent = self.alert_history[alert_key]
            cooldown_end = last_sent + timedelta(minutes=self.config.cooldown_minutes)
            
            if datetime.now() < cooldown_end:
                logger.info(f"Alert '{alert_key}' in cooldown until {cooldown_end}")
                return False
                
        return True
    
    def send_alert(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        alert_key: Optional[str] = None,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send alert email with rate limiting and cooldown
        
        Args:
            subject: Email subject
            body: Plain text body
            recipients: List of email addresses
            alert_key: Unique key for cooldown tracking (optional)
            html_body: HTML version of body (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning(f"Alert not sent - rate limit exceeded: {subject}")
            return False
        
        # Check cooldown if alert_key provided
        if alert_key and not self._check_cooldown(alert_key):
            logger.info(f"Alert not sent - in cooldown: {subject}")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.smtp_from
            msg['To'] = ', '.join(recipients)
            
            # Attach plain text
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            # Connect and send
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_tls:
                    server.starttls(context=context)
                
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                server.send_message(msg)
            
            # Update tracking
            self.hourly_count += 1
            if alert_key:
                self.alert_history[alert_key] = datetime.now()
            
            logger.info(f"Alert sent successfully: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
```

#### 10.8.2 Alert Manager

```python
# services/alerting/alert_manager.py

"""
Name of Application: Catalyst Trading System
Name of file: alert_manager.py
Version: 6.1.0
Purpose: Centralized alert management with templates
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import os
import json
import asyncpg
from email_client import EmailClient, EmailConfig

class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class AlertType(Enum):
    EMERGENCY_STOP = "emergency_stop"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_RISK = "position_risk"
    SERVICE_DOWN = "service_down"
    DATABASE_ERROR = "database_error"
    CRON_FAILURE = "cron_failure"
    WIN_RATE_DECLINING = "win_rate_declining"
    API_RATE_LIMIT = "api_rate_limit"
    DAILY_SUMMARY = "daily_summary"

class AlertManager:
    """Centralized alert management"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.email_client = EmailClient()
        
        # Load recipients from environment
        self.recipients = {
            AlertSeverity.CRITICAL: os.getenv('ALERT_EMAIL_CRITICAL', '').split(','),
            AlertSeverity.WARNING: os.getenv('ALERT_EMAIL_WARNING', '').split(','),
            AlertSeverity.INFO: os.getenv('ALERT_EMAIL_INFO', '').split(',')
        }
    
    async def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        data: Dict,
        alert_key: Optional[str] = None
    ) -> bool:
        """
        Send alert with templating and tracking
        
        Args:
            alert_type: Type of alert
            severity: Alert severity level
            data: Template data
            alert_key: Unique key for cooldown (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Render template
        subject, body, html_body = self._render_template(alert_type, data)
        
        # Get recipients for severity level
        recipients = self.recipients.get(severity, [])
        
        if not recipients:
            logger.warning(f"No recipients configured for severity: {severity}")
            return False
        
        # Send email
        success = self.email_client.send_alert(
            subject=subject,
            body=body,
            recipients=recipients,
            alert_key=alert_key or f"{alert_type.value}_{datetime.now().date()}",
            html_body=html_body
        )
        
        # Track in database
        await self._track_alert(
            alert_type=alert_type.value,
            severity=severity.value,
            subject=subject,
            data=data,
            recipients=recipients,
            sent_successfully=success
        )
        
        return success
    
    def _render_template(self, alert_type: AlertType, data: Dict) -> tuple[str, str, str]:
        """
        Render alert template
        
        Returns:
            (subject, plain_body, html_body)
        """
        # Import templates
        from alert_templates import ALERT_TEMPLATES
        
        template = ALERT_TEMPLATES.get(alert_type)
        
        if not template:
            # Fallback generic template
            subject = f"Alert: {alert_type.value}"
            body = json.dumps(data, indent=2)
            html_body = f"<pre>{body}</pre>"
            return (subject, body, html_body)
        
        # Render template with data
        subject = template['subject'].format(**data)
        body = template['body'].format(**data)
        html_body = template['html'].format(**data)
        
        return (subject, body, html_body)
    
    async def _track_alert(
        self,
        alert_type: str,
        severity: str,
        subject: str,
        data: Dict,
        recipients: List[str],
        sent_successfully: bool
    ):
        """Track alert in database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO system_alerts 
                    (alert_type, severity, subject, alert_data, recipients, sent_successfully, sent_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                alert_type,
                severity,
                subject,
                json.dumps(data),
                recipients,
                sent_successfully,
                datetime.now() if sent_successfully else None
                )
        except Exception as e:
            logger.error(f"Failed to track alert in database: {e}")
```

#### 10.8.3 Integration Points

**Workflow Service → Alert Manager**:
```python
# When emergency stop triggered
await alert_manager.send_alert(
    alert_type=AlertType.EMERGENCY_STOP,
    severity=AlertSeverity.CRITICAL,
    data={
        "timestamp": datetime.now().isoformat(),
        "reason": "Daily loss limit exceeded",
        "orders_cancelled": 3,
        "positions_closed": 5,
        "daily_pnl": -2050.00,
        "realized_pnl": -1800.00,
        "closed_positions": positions_list
    }
)
```

**System Monitor → Alert Manager**:
```python
# When service goes down
await alert_manager.send_alert(
    alert_type=AlertType.SERVICE_DOWN,
    severity=AlertSeverity.CRITICAL,
    data={
        "service_name": "scanner",
        "service_port": 5001,
        "error_details": error_message,
        "recovery_attempts": 3,
        "impact": "Market scanning suspended"
    }
)
```

---

### 10.9 Configuration Checklist

#### Pre-Production Setup

- [ ] DigitalOcean Email Service account created
- [ ] Sender domain verified (SPF, DKIM, DMARC configured)
- [ ] SMTP credentials generated and tested
- [ ] Environment variables configured in `.env`
- [ ] Alert recipients configured (critical, warning, info)
- [ ] Email templates tested with sample data
- [ ] Alert database table created
- [ ] Services integrated with alert manager
- [ ] Test alerts sent successfully
- [ ] Docker Compose `env_file` paths corrected to `./.env`

#### Monitoring

- [ ] Alert delivery rate monitored (>95% success)
- [ ] Cooldown periods appropriate (not too short/long)
- [ ] Rate limiting effective (prevents spam)
- [ ] False positives minimized (<5%)
- [ ] Alert fatigue prevented (users read alerts)
- [ ] Database tracking working (all alerts logged)

---

### 10.10 Summary

**Alerting Capabilities**:
✅ DigitalOcean Email Service integration (production-ready)  
✅ Gmail SMTP support (development/testing)  
✅ 3-tier severity system (Critical, Warning, Info)  
✅ 9 alert types covering all critical scenarios  
✅ HTML email templates with actionable information  
✅ Rate limiting and cooldown to prevent spam  
✅ Database tracking for alert history  
✅ Integration with all services  
✅ **AUTONOMOUS ACTION + NOTIFICATION** model  
✅ Docker Compose environment variable configuration

**Critical Alerts** (9 types):
1. Emergency Stop (ALREADY EXECUTED - informing)
2. Daily Loss Limit (ALREADY STOPPED - informing)
3. Position Risk Violation (ALREADY REJECTED - informing)
4. Service Down (ALREADY RESTARTING - informing)
5. Database Error (ALREADY RETRYING - informing)
6. Cron Job Failure (WARNING - attention needed)
7. Win Rate Declining (WARNING - review needed)
8. API Rate Limit (WARNING - throttling active)
9. Daily Summary (INFO - awareness only)

**Key Philosophy**:
- **System acts autonomously** when risk criteria met
- **Alerts are informational** - "here's what I did and why"
- **User reviews and adjusts** risk parameters as needed
- **Manual restart** required after emergency stop
- **Configuration flexibility** without code changes

**Alert Flow Example**:
```
Risk Criteria Met (Daily loss: -$2,000)
    ↓
System Takes Action Automatically
    → Close all positions
    → Cancel all orders
    → Stop workflow execution
    ↓
System Sends Informational Alert
    → Subject: "🛑 EMERGENCY STOP - Trading Halted"
    → Body: "Trading stopped. Daily loss: -$2,000. Manual restart required."
    → HTML: Professional template with position details
    ↓
User Reviews Situation
    → Checks email on phone/desktop
    → Reviews closed positions and P&L
    → Analyzes what went wrong
    ↓
User Adjusts Risk Config (Optional)
    → Update max_daily_loss_usd to $3,000
    → Adjust position sizing
    → Modify stop loss rules
    ↓
User Manually Restarts Trading
    → Via Claude Desktop: "Start trading in conservative mode"
    → Via curl: POST /api/v1/workflow/start
```

**Benefits**:
- ✅ Capital protection without human delay
- ✅ Clear communication of autonomous actions
- ✅ Flexibility to adjust risk tolerance
- ✅ No approval bottleneck in critical situations
- ✅ Configuration changes without code deployment
- ✅ Audit trail of all alerts and actions
- ✅ Professional email delivery via DigitalOcean
- ✅ Reliable SMTP with proper DNS configuration

---

**END OF SECTION 10: MONITORING & ALERTING**

🎩 **DevGenius Status**: Comprehensive alerting system with autonomous action + DigitalOcean Email Service! 📧
