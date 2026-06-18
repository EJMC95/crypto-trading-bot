#!/bin/bash
# Double-click this file in Finder to start the arbitrage bot (paper trading).
# It sets up an isolated Python environment, installs ccxt the first time,
# then runs the live depth-aware detection + paper-trading loop.
#
# NO real orders are ever placed. Press Ctrl-C in the window to stop.

cd "$(dirname "$0")" || exit 1

echo "=== Triangular Arbitrage Bot — paper trading launcher ==="
echo

# 1) Find a Python 3.
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "Python 3 not found. Install it from https://www.python.org/downloads/ and retry."
  read -r -p "Press Enter to close."
  exit 1
fi
echo "Using Python: $PY"

# 2) Create a local virtual environment the first time.
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv || { echo "venv creation failed"; read -r -p "Enter to close."; exit 1; }
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 3) Install / update ccxt inside the venv.
python -c "import ccxt" 2>/dev/null || {
  echo "Installing ccxt (first run only)..."
  pip install --quiet --upgrade pip
  pip install --quiet ccxt || { echo "ccxt install failed"; read -r -p "Enter to close."; exit 1; }
}

# 4) Smoke test: one live scan to confirm it can reach Kraken.
echo
echo "--- Smoke test: one live scan against Kraken ---"
python triangular_arb.py --once || {
  echo "Smoke test failed (check your internet connection)."
  read -r -p "Press Enter to close."
  exit 1
}

# 5) Go live (continuous paper trading). Logs to the window AND
#    arb_run.log, opportunities to arb_opportunities.csv.
echo
echo "--- Going live: continuous paper trading. Ctrl-C to stop. ---"
echo "    Opportunity log: arb_opportunities.csv"
echo "    Full output:     arb_run.log"
echo
exec python triangular_arb.py 2>&1 | tee -a arb_run.log
