# ============================================================================
# DEV_CLAUDE - US Market Trading Schedule
# Timezone: America/New_York (all times are Eastern, DST-aware)
# Version: 2.0.0
# Updated: 2026-03-28 - Fixed timezone: use ET directly, not UTC offsets
# ============================================================================

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
TZ=America/New_York

# Working directories
CATALYST_DIR=/root/catalyst-trading-system/services/dev_claude
VENV_PYTHON=/root/catalyst-trading-system/services/dev_claude/venv/bin/python3
LOG_DIR=/root/catalyst-trading-system/services/dev_claude/logs

# ============================================================================
# PRE-MARKET SCAN (08:00 ET)
# ============================================================================
0 8 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode scan >> $LOG_DIR/scan.log 2>&1

# ============================================================================
# TRADING HOURS (09:30-16:00 ET)
# ============================================================================
# First cycle at market open
30 9 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# Hourly cycles during market hours
0 10 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 11 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 12 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 13 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 14 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 15 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# ============================================================================
# END OF DAY (16:00 ET)
# ============================================================================
0 16 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode close >> $LOG_DIR/close.log 2>&1

# ============================================================================
# OFF-HOURS HEARTBEAT (every 3 hours ET, weekdays)
# ============================================================================
0 0,3,6,9,12 * * 1-5 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# Weekend heartbeat (every 6 hours ET)
0 0,6,12,18 * * 0,6 root cd $CATALYST_DIR && source $CATALYST_DIR/.env && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# ============================================================================
# LOG ROTATION (Sunday midnight ET)
# ============================================================================
0 0 * * 0 root find $LOG_DIR -name "*.log" -mtime +7 -delete
