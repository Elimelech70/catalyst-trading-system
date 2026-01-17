# ============================================================================
# DEV_CLAUDE - US Market Trading Schedule
# Timezone: UTC (EST = UTC-5, EDT = UTC-4)
# Version: 1.1.0
# Updated: 2026-01-17 - Consolidated to services/dev_claude
# ============================================================================

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# Working directories
CATALYST_DIR=/root/catalyst-trading-system/services/dev_claude
VENV_PYTHON=/root/catalyst-trading-system/services/dev_claude/venv/bin/python3
LOG_DIR=/root/catalyst-trading-system/services/dev_claude/logs

# ============================================================================
# PRE-MARKET SCAN (08:00 EST = 13:00 UTC)
# ============================================================================
0 13 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode scan >> $LOG_DIR/scan.log 2>&1

# ============================================================================
# TRADING HOURS (09:30-16:00 EST = 14:30-21:00 UTC)
# ============================================================================
# First cycle at market open
30 14 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# Hourly cycles during market hours
0 15 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 16 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 17 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 18 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 19 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 20 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# ============================================================================
# END OF DAY (16:00 EST = 21:00 UTC)
# ============================================================================
0 21 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode close >> $LOG_DIR/close.log 2>&1

# ============================================================================
# OFF-HOURS HEARTBEAT (every 3 hours)
# ============================================================================
0 0,3,6,9,12 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# Weekend heartbeat (every 6 hours)
0 0,6,12,18 * * 0,6 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# ============================================================================
# LOG ROTATION
# ============================================================================
0 0 * * 0 root find $LOG_DIR -name "*.log" -mtime +7 -delete
