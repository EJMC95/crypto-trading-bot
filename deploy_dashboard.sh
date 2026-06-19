#!/bin/sh
# deploy_dashboard.sh — create + deploy the live P&L dashboard as a Railway
# service in your existing "Trading Bots" project, using the Railway CLI.
# Run from the repo root:  ./deploy_dashboard.sh
#
# It does NOT touch your other services. It creates ONE new service called
# "pnl-dashboard" that runs pnl_dashboard.py and reads your Postgres.

set -eu

SERVICE="pnl-dashboard"
PROJECT_ID="9b3b7d3c-28db-417b-b864-ebc065df851f"   # your "Trading Bots" project

# 1. Install the CLI if missing (https://docs.railway.com/guides/cli)
if ! command -v railway >/dev/null 2>&1; then
  echo "Railway CLI not found. Install it with:"
  echo "    brew install railway      # macOS"
  echo "    npm i -g @railway/cli      # or via npm"
  exit 1
fi

# 2. Log in (opens your browser — YOU authenticate, not this script)
railway whoami >/dev/null 2>&1 || railway login

# 3. Link this folder to the Trading Bots project
railway link --project "$PROJECT_ID"

# 4. Create the new service and deploy the current folder to it
railway add --service "$SERVICE"
railway up --service "$SERVICE" --detach

echo ""
echo "=================================================================="
echo " Service '$SERVICE' created and deploying."
echo " STILL TO DO (once, in the Railway UI — 2 clicks each):"
echo "   1. $SERVICE -> Variables -> Add Reference -> Postgres DATABASE_URL"
echo "   2. $SERVICE -> Settings -> set Start Command: python pnl_dashboard.py"
echo "   3. $SERVICE -> Settings -> Networking -> Generate Domain"
echo "   4. Also add the DATABASE_URL reference to each bot service"
echo "      (perps-bot, momo-bot, triangular-arb, listing-sniper) so they publish."
echo " Then open the generated domain and log in (DASH_USER/DASH_PASS)."
echo "=================================================================="
