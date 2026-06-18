#!/bin/bash
# Double-click to stop and remove the always-on background service.
# Your scripts, logs, and CSV stay; only the auto-run service is removed.

cd "$(dirname "$0")"
LABEL="com.eamon.tri-arb"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "=== Stopping arbitrage bot background service ==="
launchctl unload "$PLIST_DST" 2>/dev/null && echo "Service stopped." || echo "Service was not loaded."
if [ -f "$PLIST_DST" ]; then
  rm "$PLIST_DST"
  echo "Removed $PLIST_DST"
fi
echo "Done. Logs and data are untouched."
read -r -p "Press Enter to close."
