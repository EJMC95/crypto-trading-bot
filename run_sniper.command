#!/bin/zsh
# Double-click launcher for the multi-exchange listing sniper (DRY-RUN).
# Seeds the baseline on first run, then starts the live paper monitor.

cd "$(dirname "$0")" || exit 1

echo "================================================================"
echo " Multi-Exchange Listing Sniper — launcher"
echo " Folder: $(pwd)"
echo "================================================================"

# Make sure ccxt (and the rest) are installed; quiet unless something happens.
python3 -m pip install -r requirements.txt >/dev/null 2>&1

# Seed only if there's no baseline yet (so re-launching never re-fires on
# existing pairs). Delete sniper_data/known_pairs.json if you want a fresh seed.
if [ ! -f "sniper_data/known_pairs.json" ]; then
  echo "[launcher] No baseline found — seeding the top-100-exchange snapshot…"
  python3 listing_sniper.py --seed
else
  echo "[launcher] Baseline found — skipping seed."
fi

echo "[launcher] Starting live paper monitor. Close this window or press Ctrl-C to stop."
echo
python3 listing_sniper.py

echo
echo "[launcher] Sniper stopped. You can close this window."
