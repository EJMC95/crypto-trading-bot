#!/bin/sh
# deploy_freqtrade.sh — create + deploy the freqtrade bots (v4–v8: incl. the
# new long/short v5, range v7, long-only v6) as ONE always-on Railway service.
# Run from the repo root:  ./deploy_freqtrade.sh
#
# "Stays live" is guaranteed two ways:
#   * run_all.sh runs each bot in its own while-true restart loop (a crash of
#     one bot doesn't take down the others).
#   * railway.freqtrade.toml sets restartPolicyType = "always" (Railway restarts
#     the container if it ever exits).

set -eu

SERVICE="freqtrade-bots"
PROJECT_ID="9b3b7d3c-28db-417b-b864-ebc065df851f"   # your "Trading Bots" project

if ! command -v railway >/dev/null 2>&1; then
  echo "Railway CLI not found. Install it:"
  echo "    brew install railway        # macOS"
  echo "    npm i -g @railway/cli       # or via npm"
  exit 1
fi

railway whoami >/dev/null 2>&1 || railway login          # YOU authenticate in the browser
railway link --project "$PROJECT_ID"
railway add --service "$SERVICE"
railway up --service "$SERVICE" --detach

cat <<'NOTE'

==================================================================
 ONE required setting (CLI can't set it — do it once in the UI):

   freqtrade-bots service -> Settings -> "Config-as-code" /
   "Railway Config File"  ->  railway.freqtrade.toml
   then Redeploy.

 That file tells Railway to build Dockerfile.freqtrade and use
 restartPolicyType = "always" (stay live). Without it, Railway will
 try the default build and the bots won't start.

 Optional:
   - Settings -> Networking -> Generate Domain  (to view the built-in
     freqtrade dashboard_server on $PORT).

 After it deploys, watch the logs:
   - "[supervisor] starting v5gated ..." lines = bots launching.
   - "ENTRY-DIAG ..." lines  = strategies evaluating entries (good).
   - If a bot crash-loops every 10s, read its error (e.g. v5 needs
     Kraken Futures; if unavailable, set config_v5_kraken.json
     trading_mode back to "spot").
==================================================================
NOTE
