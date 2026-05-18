#!/bin/bash
# Test email configuration

ALERT_EMAIL="craigjcolley@gmail.com"

echo "Sending test email to $ALERT_EMAIL..."

RESULT=$(echo "This is a test email from Catalyst Trading System.

If you receive this, email alerts are working correctly.

Server: $(hostname)
Time: $(date)
IP: $(curl -s ifconfig.me 2>/dev/null || echo 'unknown')

-- 
Catalyst International System" | mail -s "✅ Catalyst Email Test" "$ALERT_EMAIL" 2>&1)

if [ $? -eq 0 ]; then
    echo "✓ Email sent successfully!"
    echo "  Check craigjcolley@gmail.com inbox (and spam folder)"
else
    echo "✗ Email failed:"
    echo "$RESULT"
    echo ""
    echo "Check /var/log/catalyst/msmtp.log for details"
fi
