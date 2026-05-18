#!/bin/bash
# Catalyst Neural — Power Management Installer
#
# Sets up auto wake/suspend for market trading sessions.
# Run once with: sudo bash install-power.sh
#
# What it does:
#   1. Installs catalyst-power to /usr/local/bin/
#   2. Adds passwordless sudo for catalyst-power (for RTC alarm access)
#   3. Installs shutdown hook (sets next wake alarm before poweroff)
#   4. Installs catalyst-neural user service (collection daemon)
#   5. Installs catalyst-pipeline weekly timer (train + deploy)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER="craig"

echo "=== Catalyst Neural — Power Management Setup ==="
echo ""

# 1. Install catalyst-power to /usr/local/bin
echo "[1/4] Installing catalyst-power..."
cp "$SCRIPT_DIR/catalyst-power" /usr/local/bin/catalyst-power
chmod 755 /usr/local/bin/catalyst-power
echo "  Installed /usr/local/bin/catalyst-power"

# 2. Passwordless sudo for catalyst-power
echo "[2/4] Configuring sudoers..."
SUDOERS_FILE="/etc/sudoers.d/catalyst-power"
echo "$USER ALL=(root) NOPASSWD: /usr/local/bin/catalyst-power" > "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"
echo "  Created $SUDOERS_FILE"

# 3. Shutdown hook — sets RTC alarm before any shutdown/reboot
echo "[3/4] Installing shutdown hook..."
cp "$SCRIPT_DIR/catalyst-power-shutdown.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable catalyst-power-shutdown.service
echo "  Enabled catalyst-power-shutdown.service"

# 4. User services for collection daemon + pipeline timer
echo "[4/5] Installing catalyst-neural user service..."
USER_SERVICE_DIR="/home/$USER/.config/systemd/user"
mkdir -p "$USER_SERVICE_DIR"
cp "$SCRIPT_DIR/catalyst-neural.service" "$USER_SERVICE_DIR/"
chown -R "$USER:$USER" "$USER_SERVICE_DIR"
su - "$USER" -c "systemctl --user daemon-reload && systemctl --user enable catalyst-neural.service"
echo "  Enabled catalyst-neural.service (collection daemon)"

# 5. Weekly pipeline timer (train + export + deploy)
echo "[5/5] Installing catalyst-pipeline timer..."
cp "$SCRIPT_DIR/catalyst-pipeline.service" "$USER_SERVICE_DIR/"
cp "$SCRIPT_DIR/catalyst-pipeline.timer" "$USER_SERVICE_DIR/"
chown "$USER:$USER" "$USER_SERVICE_DIR/catalyst-pipeline.service" "$USER_SERVICE_DIR/catalyst-pipeline.timer"
su - "$USER" -c "systemctl --user daemon-reload && systemctl --user enable catalyst-pipeline.timer"
echo "  Enabled catalyst-pipeline.timer (weekly Sunday 20:00)"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Verify:"
echo "  catalyst-power next              # show upcoming sessions"
echo "  sudo catalyst-power set-alarm    # test RTC alarm"
echo "  systemctl --user list-timers     # check pipeline timer"
echo ""
echo "Start now:"
echo "  systemctl --user start catalyst-neural   # start collection"
echo "  systemctl --user start catalyst-pipeline # run pipeline once now"
echo ""
echo "The machine will now:"
echo "  - Wake before each market session (HKEX + NYSE)"
echo "  - Collect data during trading hours"
echo "  - Suspend between sessions to save power"
echo "  - Stay awake if you're actively using it"
echo "  - Retrain + deploy models every Sunday at 20:00"
