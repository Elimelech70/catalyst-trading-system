# Catalyst Trading System - Autonomous Trading Guide

**Version**: 6.1.0
**Last Updated**: 2025-11-18
**Status**: PRODUCTION READY

---

## 🎯 Overview

The Catalyst Trading System is configured for **fully autonomous trading** with the Risk Manager as the safety layer. The system:

- ✅ **Executes trades automatically** after risk validation
- ✅ **Enforces safety limits autonomously** (no human approval required)
- ✅ **Sends informational alerts** ("here's what I did")
- ✅ **Operates 10+ times/day** via cron automation
- ✅ **Protects capital** through multi-layer risk management

---

## 🏗️ Architecture

### Dual-Initiation Model

```
PRIMARY: Cron Automation (Production Trading)
  └─> 10+ automated workflows/day
  └─> REST API → Workflow service (port 5006)
  └─> Autonomous execution after risk validation
  └─> RUNS THE BUSINESS

SECONDARY: Claude Desktop (Monitoring - OPTIONAL)
  └─> Manual oversight and analysis
  └─> MCP protocol → Orchestration service (port 5000)
  └─> ML training data generation
  └─> IMPROVES THE BUSINESS
```

### Autonomous Workflow

```
CRON TRIGGER (e.g., 9:30 AM ET)
  ↓
POST /api/v1/workflow/start {"mode": "autonomous"}
  ↓
Workflow Service coordinates:
  ├─> Scanner: 100 → 35 → 20 → 10 → 5 candidates
  ├─> Pattern: Identify chart setups
  ├─> Technical: Validate indicators
  ├─> Risk Manager: PRE-TRADE VALIDATION ✓
  │   ✅ Pass → Execute trade
  │   ❌ Fail → Reject, log reason
  ↓
Trading Service: Execute via Alpaca
  ↓
CONTINUOUS MONITORING:
  └─> Risk Manager checks every 60 seconds
      ├─> P&L -$1,500 (75%) → WARNING email
      ├─> P&L -$2,000 (100%) → EMERGENCY STOP (auto-close all)
      └─> Position count > 5 → Reject new trades
```

---

## ⚙️ Configuration Files

### 1. Risk Parameters (`config/risk_parameters.yaml`)

**Key Settings**:

```yaml
risk_limits:
  max_daily_loss_usd: 2000          # Emergency stop at -$2,000
  warning_threshold_pct: 0.75       # Email warning at 75%
  max_positions: 5
  max_position_size_usd: 10000
  max_correlation: 0.70
  min_stop_loss_atr_multiple: 2.0
  min_risk_reward_ratio: 1.5

emergency_actions:
  close_all_positions: true         # Auto-close on limit
  cancel_all_orders: true
  halt_new_trades: true
  notify_via_email: true
  require_manual_restart: true      # Safety: manual restart after stop
```

**Hot-Reload**: Changes take effect immediately (no restart required)

### 2. Trading Configuration (`config/trading_config.yaml`)

**Critical Setting**:

```yaml
trading_session:
  mode: "autonomous"                # NOT "supervised"
  # autonomous = Execute immediately
  # supervised = Wait for human approval
```

**Other Key Settings**:

```yaml
workflow:
  scan_frequency_minutes: 30        # Scan every 30 minutes
  execute_top_n: 3                  # Trade top 3 candidates

order_execution:
  default_order_type: "limit"
  use_bracket_orders: true          # Entry + stop + target

position_management:
  update_frequency_seconds: 60      # Monitor every minute
  max_position_age_minutes: 180     # Close after 3 hours
```

### 3. Environment Variables (`.env`)

**Copy from template**:

```bash
cp .env.template .env
nano .env
```

**Required Settings**:

```bash
# Autonomous Trading
TRADING_SESSION_MODE=autonomous
WORKFLOW_AUTO_EXECUTE=true
ENABLE_AUTONOMOUS_TRADING=true

# Email Alerts (DigitalOcean SMTP)
SMTP_HOST=smtp.digitalocean.com
SMTP_PORT=587
SMTP_USERNAME=your-do-smtp-username
SMTP_PASSWORD=your-do-smtp-api-token
SMTP_FROM=catalyst-alerts@yourdomain.com

ALERT_EMAIL_CRITICAL=trader@yourdomain.com
ALERT_EMAIL_WARNING=trader@yourdomain.com
ALERT_EMAIL_INFO=trader@yourdomain.com
```

### 4. Cron Automation (`config/autonomous-cron-setup.txt`)

**Install**:

```bash
# SSH to DigitalOcean droplet
ssh root@your-droplet-ip

# Install cron configuration
crontab -e
# Paste contents from config/autonomous-cron-setup.txt

# Verify installation
crontab -l
```

**Key Cron Jobs**:

```bash
# Market open (9:30 AM ET)
30 22 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -d '{"mode": "autonomous"}'

# Periodic scans (every 30 min during market hours)
0,30 23 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -d '{"mode": "autonomous"}'
```

---

## 🛡️ Risk Manager: Autonomous Safety Layer

### Pre-Trade Validation (Automatic Rejection)

The Risk Manager **automatically validates** every trade:

```python
# NO HUMAN APPROVAL REQUIRED
def validate_trade(symbol, quantity, entry_price):
    # Check 1: Daily loss limit
    if current_daily_pnl <= -max_daily_loss:
        return REJECTED("Daily loss limit reached")

    # Check 2: Position count
    if active_positions >= max_positions:
        return REJECTED("Max positions reached")

    # Check 3: Position size
    if position_value > max_position_size:
        return REJECTED("Position too large")

    # Check 4: Correlation
    if correlation > 0.7:
        return REJECTED("High correlation")

    # ALL CHECKS PASSED → EXECUTE IMMEDIATELY
    return APPROVED
```

### Real-Time Monitoring (Automatic Emergency Stop)

The Risk Manager **continuously monitors** positions (every 60 seconds):

```python
# Runs automatically, no human intervention
def monitor_positions():
    current_pnl = get_daily_pnl()

    # WARNING threshold (75%)
    if current_pnl <= -1500:
        send_email_alert(
            severity="WARNING",
            message="Daily P&L: -$1,500 (75% of limit)"
        )

    # CRITICAL threshold (100%) - AUTO-EXECUTE
    if current_pnl <= -2000:
        # EMERGENCY STOP - NO HUMAN APPROVAL
        result = emergency_stop()

        send_email_alert(
            severity="CRITICAL",
            message=f"Trading STOPPED. Closed {result.positions} positions."
        )
```

---

## 📧 Email Alerts: Informational Only

### Alert Philosophy

```yaml
OLD (Supervised Mode):
  "⚠️ Daily loss approaching limit - What should I do?"
  → User Action: REQUIRED to proceed

NEW (Autonomous Mode):
  "🛑 EMERGENCY STOP - Trading Halted"
  "I've stopped trading because daily loss hit -$2,000.
   Here's what I did:
   - Closed 5 positions
   - Cancelled 3 orders
   - Final P&L: -$2,050

   Manual restart required when ready."
  → User Action: Review and restart when appropriate
```

### Alert Types

1. **CRITICAL** (Auto-execute, then inform)
   - Emergency stop triggered
   - Daily loss limit hit
   - Service down

2. **WARNING** (Informational)
   - Approaching loss limit (75%)
   - Win rate declining
   - High error rate

3. **INFO** (Daily summaries)
   - Daily trading summary
   - Weekly performance report

---

## 🚀 Deployment Steps

### 1. Configure Risk Parameters

```bash
# Edit risk parameters
nano config/risk_parameters.yaml

# Set your limits:
# - max_daily_loss_usd: 2000
# - max_positions: 5
# - max_position_size_usd: 10000
```

### 2. Configure Environment

```bash
# Copy template
cp .env.template .env

# Edit environment variables
nano .env

# Set:
# - TRADING_SESSION_MODE=autonomous
# - Email SMTP settings
# - Alert recipients
# - API keys
```

### 3. Install Cron Jobs

```bash
# Install cron configuration
crontab -e

# Paste contents from:
# config/autonomous-cron-setup.txt

# Verify
crontab -l
```

### 4. Deploy Services

```bash
# Start all services
docker-compose up -d

# Verify services are healthy
docker-compose ps

# Check logs
docker-compose logs -f workflow
```

### 5. Test Autonomous Workflow

```bash
# Manual test (before cron kicks in)
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "autonomous", "max_positions": 1, "execute_top_n": 1}'

# Monitor logs
tail -f /var/log/catalyst/autonomous-trading.log

# Check email for alerts
```

---

## 📊 Monitoring Autonomous Trading

### 1. Log Monitoring

```bash
# Real-time trading log
tail -f /var/log/catalyst/autonomous-trading.log

# Health checks
tail -f /var/log/catalyst/health.log

# Daily reports
ls -l /var/log/catalyst/daily_report_*.json
```

### 2. Email Alerts

You'll receive emails for:

- **Market open**: "Autonomous workflow started"
- **Trades executed**: "Executed TSLA: 50 shares @ $240"
- **Risk warnings**: "Daily P&L: -$1,500 (75% of limit)"
- **Emergency stop**: "Trading halted at -$2,000"
- **Daily summary**: "Today's results: 8 trades, +$450"

### 3. Database Queries

```sql
-- Current positions
SELECT * FROM v_positions_current;

-- Today's performance
SELECT * FROM v_performance_daily WHERE date = CURRENT_DATE;

-- Recent risk events
SELECT * FROM risk_events ORDER BY occurred_at DESC LIMIT 10;

-- Rejected trades
SELECT * FROM decision_logs WHERE action = 'rejected'
ORDER BY timestamp DESC LIMIT 20;
```

### 4. Claude Desktop (Optional)

If Claude Desktop is available (via MCP):

```
"Show me today's trading activity"
"Why was the last trade rejected?"
"What's our current P&L?"
"Analyze win rate by pattern"
```

---

## 🔄 Human Interaction Points

### Before Trading (Configuration)

- ✅ Set risk parameters (`max_daily_loss`, `max_positions`)
- ✅ Review strategy logic
- ✅ Configure email alerts
- ✅ Validate backtests (optional)

### During Trading (Monitoring - OPTIONAL)

- 📧 Receive email alerts (informational)
- 📊 Monitor via Claude Desktop (if available)
- 📈 Review dashboard (if implemented)
- ⚠️ **NOT REQUIRED for system operation**

### After Emergency Stop (Manual Restart)

```bash
# 1. Review why stop was triggered
cat /var/log/catalyst/autonomous-trading.log

# 2. Check email for details
# 3. Adjust risk parameters if needed
nano config/risk_parameters.yaml

# 4. Manually restart when ready
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "autonomous"}'
```

### End of Day (Review)

- 📧 Read daily summary email
- 📊 Review performance metrics
- ⚙️ Adjust strategy parameters (if needed)
- 🔧 Plan improvements

---

## 🛠️ Troubleshooting

### Workflow Not Starting

```bash
# Check cron is running
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Test workflow manually
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -d '{"mode": "autonomous"}'
```

### Trades Not Executing

```bash
# Check workflow logs
docker-compose logs workflow

# Check risk manager logs
docker-compose logs risk-manager

# Check if in paper trading mode
grep TRADING_MODE .env
```

### Email Alerts Not Sending

```bash
# Test email configuration
python scripts/test_email.py

# Check SMTP settings in .env
grep SMTP .env

# Check alert manager logs
docker-compose logs orchestration | grep alert
```

### Emergency Stop Not Triggering

```bash
# Check risk parameters
cat config/risk_parameters.yaml | grep max_daily_loss

# Check current P&L
curl http://localhost:5006/api/v1/performance/daily

# Check risk manager service
docker-compose logs risk-manager
```

---

## ⚡ Quick Commands

### Start/Stop Trading

```bash
# Start autonomous trading
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -d '{"mode": "autonomous"}'

# Stop trading
curl -X POST http://localhost:5006/api/v1/workflow/stop

# Emergency stop (close all positions)
curl -X POST http://localhost:5006/api/v1/emergency-stop \
  -d '{"reason": "Manual intervention"}'
```

### Check Status

```bash
# Workflow status
curl http://localhost:5006/api/v1/workflow/status

# Current positions
curl http://localhost:5006/api/v1/positions/active

# Daily P&L
curl http://localhost:5006/api/v1/performance/daily

# Risk status
curl http://localhost:5004/api/v1/risk/status
```

### Modify Risk Parameters (Hot Reload)

```bash
# Edit parameters
nano config/risk_parameters.yaml

# Changes apply immediately (no restart)

# Verify new limits
curl http://localhost:5004/api/v1/risk/limits
```

---

## 🔐 Safety Guarantees

The autonomous system provides:

✅ **Daily loss limit enforced** (auto-stop at -$2,000)
✅ **Position limits enforced** (reject if exceeds)
✅ **Correlation checks** (reject correlated positions)
✅ **Stop losses on every trade** (2x ATR minimum)
✅ **Emergency stop capability** (automatic when limits hit)
✅ **All decisions logged** (for review and ML training)
✅ **Manual restart required** (after emergency stop)
✅ **Hot-reload configuration** (adjust limits without restart)
✅ **Email notifications** (informational alerts)
✅ **Multi-layer validation** (Scanner → Pattern → Technical → Risk)

---

## 📈 Performance Expectations

### Stage 1 (Current - Rule-Based)

```yaml
Target Metrics:
  Win Rate: ≥60%
  Sharpe Ratio: ≥1.0
  Max Drawdown: <10%
  Average R:R: ≥1.5
  Daily Trades: 5-10

Data Collection:
  Trades: 500-1000 (3-6 months)
  Purpose: ML training for future stages
```

### Future Stages (Research Instance)

See `Documentation/Design/strategy-ml-roadmap-v50.md` for long-term vision.

---

## 🆘 Emergency Procedures

### If System Goes Wrong

1. **Immediate Stop**:
   ```bash
   curl -X POST http://localhost:5006/api/v1/emergency-stop
   ```

2. **Disable Cron**:
   ```bash
   crontab -r  # Remove all cron jobs
   ```

3. **Stop Services**:
   ```bash
   docker-compose stop
   ```

4. **Review Logs**:
   ```bash
   tail -n 100 /var/log/catalyst/autonomous-trading.log
   ```

5. **Check Alpaca**:
   - Log into Alpaca dashboard
   - Verify positions
   - Manually close if needed

6. **Contact Support**:
   - Review email alerts
   - Check database for events
   - Analyze what went wrong

---

## ✅ Pre-Launch Checklist

Before enabling autonomous trading:

- [ ] Risk parameters configured (`max_daily_loss`, `max_positions`)
- [ ] Environment variables set (`.env`)
- [ ] Email alerts tested (test_email.py)
- [ ] Cron jobs installed and verified
- [ ] Services running and healthy
- [ ] Paper trading tested successfully
- [ ] Alpaca API keys configured
- [ ] Database schema deployed
- [ ] Backups configured
- [ ] Emergency stop procedure documented
- [ ] Alert recipients notified
- [ ] First manual workflow test passed

---

## 📚 Additional Resources

- **Functional Spec**: `Documentation/Design/catalyst-functional-spec-v6.1.0b.md`
- **Architecture**: `Documentation/Design/architecture-mcp-v60.md`
- **Database Schema**: `Documentation/Design/database-schema-mcp-v60.md`
- **Risk Parameters**: `config/risk_parameters.yaml`
- **Trading Config**: `config/trading_config.yaml`
- **Cron Setup**: `config/autonomous-cron-setup.txt`

---

## 🎯 Summary

**The Catalyst Trading System is fully autonomous**:

1. **Cron triggers workflows** 10+ times/day
2. **Risk Manager validates** every trade
3. **System executes** immediately if approved
4. **System rejects** if validation fails
5. **Email alerts inform** you of actions taken
6. **Emergency stop automatic** at daily loss limit
7. **Manual restart required** after emergency stop

**Safety is in the Risk Manager** - multi-layer validation ensures capital protection while enabling autonomous operation.

---

**You're ready for fully autonomous trading!** 🚀

*Review the configuration, test thoroughly, and let the system trade while you monitor via email alerts.*
