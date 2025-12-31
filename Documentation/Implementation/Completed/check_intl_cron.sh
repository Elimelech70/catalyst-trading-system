#!/bin/bash
# Check cron status for intl_claude
# Run on the INTL droplet

echo "============================================"
echo "INTL_CLAUDE CRON STATUS CHECK"
echo "============================================"
echo ""

echo "1. Current crontab entries:"
echo "--------------------------------------------"
crontab -l 2>/dev/null || echo "   No crontab configured"
echo ""

echo "2. Root crontab (if running as root):"
echo "--------------------------------------------"
sudo crontab -l 2>/dev/null || echo "   No root crontab"
echo ""

echo "3. System cron files:"
echo "--------------------------------------------"
ls -la /etc/cron.d/ 2>/dev/null | grep -E "(catalyst|claude|intl)" || echo "   No catalyst cron files in /etc/cron.d/"
echo ""

echo "4. Systemd timers (alternative to cron):"
echo "--------------------------------------------"
systemctl list-timers 2>/dev/null | grep -E "(catalyst|claude|intl)" || echo "   No catalyst timers"
echo ""

echo "5. Running Python processes:"
echo "--------------------------------------------"
ps aux | grep -E "(agent|heartbeat|claude)" | grep -v grep || echo "   No agent processes running"
echo ""

echo "6. Recent cron logs:"
echo "--------------------------------------------"
grep -E "(catalyst|claude|CRON)" /var/log/syslog 2>/dev/null | tail -10 || \
journalctl -u cron --since "1 hour ago" 2>/dev/null | tail -10 || \
echo "   No recent cron logs found"
echo ""

echo "============================================"
echo "RECOMMENDATION:"
echo "============================================"
echo "If no cron is set up, add this to crontab -e:"
echo ""
echo "# intl_claude heartbeat - every 30 mins at :30"
echo "30 * * * * cd /root/catalyst-international && ./venv/bin/python3 agent.py >> /var/log/intl_claude.log 2>&1"
echo ""
echo "Or for the report specifically:"
echo "0 17 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 scripts/generate_daily_report.py >> /var/log/intl_report.log 2>&1"
echo ""
