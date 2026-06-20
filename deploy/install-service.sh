#!/usr/bin/env bash
# Install + start the job-autopilot systemd service. Run as root:
#   sudo bash deploy/install-service.sh
set -euo pipefail

SVC=job-autopilot
SRC=/media/server/Storage/www/job-autopilot/deploy/job-autopilot.service
DEST=/etc/systemd/system/$SVC.service

if [ "$(id -u)" -ne 0 ]; then
  echo "Must run as root: sudo bash deploy/install-service.sh" >&2
  exit 1
fi

echo "→ installing $DEST"
cp "$SRC" "$DEST"
systemctl daemon-reload
systemctl enable "$SVC"

# Free port 8080 from any manually-launched instance so the service can bind it.
PID=$(ss -ltnp 2>/dev/null | grep ':8080 ' | grep -oP 'pid=\K[0-9]+' || true)
if [ -n "${PID:-}" ]; then
  echo "→ stopping manual instance (pid $PID) holding :8080"
  kill "$PID" 2>/dev/null || true
  sleep 2
fi

echo "→ starting service"
systemctl restart "$SVC"
sleep 3
systemctl --no-pager --full status "$SVC" | head -20
