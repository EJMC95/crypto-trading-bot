#!/bin/bash
# Double-click to install the bot as an always-on background service (launchd).
# After this, the bot starts automatically at login and restarts if it stops.
# It keeps running with no Terminal window open. NO real orders are ever placed.

set -e
cd "$(dirname "$0")"
WORKDIR="$(pwd)"
LABEL="com.eamon.tri-arb"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "=== Installing arbitrage bot as a background service ==="
echo "Working dir: $WORKDIR"
echo

# 1) Ensure the venv + ccxt exist (same env the launcher uses).
PY="$(command -v python3)"
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate
python -c "import ccxt" 2>/dev/null || { echo "Installing ccxt..."; pip install --quiet --upgrade pip; pip install --quiet ccxt; }
VENV_PY="$WORKDIR/.venv/bin/python"

# 2) Render the plist with real absolute paths.
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$VENV_PY|g" \
    -e "s|__WORKDIR__|$WORKDIR|g" \
    com.eamon.tri-arb.plist > "$PLIST_DST"
echo "Wrote $PLIST_DST"

# 3) (Re)load the service.
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo
echo "Service loaded. It is now running and will start at every login."
echo "  Status:   launchctl list | grep $LABEL"
echo "  Live log: tail -f \"$WORKDIR/arb_run.log\""
echo "  Stop:     double-click uninstall_service.command"
echo
read -r -p "Press Enter to close."
