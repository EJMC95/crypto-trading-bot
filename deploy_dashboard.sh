#!/bin/sh
# deploy_dashboard.sh — create + deploy the unified live P&L dashboard as a
# Railway service, fully from the CLI (no UI field-hunting).
# Run from the repo root:  ./deploy_dashboard.sh
#
# Builds Dockerfile.dashboard (selected via RAILWAY_DOCKERFILE_PATH), points it
# at the Postgres service for data, and generates a public domain.

set -eu

SERVICE="pnl-dashboard"
PROJECT_ID="9b3b7d3c-28db-417b-b864-ebc065df851f"   # your "Trading Bots" project

if ! command -v railway >/dev/null 2>&1; then
  echo "Railway CLI not found. Install: brew install railway  (or  npm i -g @railway/cli)"
  exit 1
fi

railway whoami >/dev/null 2>&1 || railway login
railway link --project "$PROJECT_ID"
railway add --service "$SERVICE"

# Build the dashboard Dockerfile + give it Postgres access (no UI needed).
railway variables \
  --set "RAILWAY_DOCKERFILE_PATH=Dockerfile.dashboard" \
  --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}' \
  --service "$SERVICE"

railway up --service "$SERVICE" --detach
railway domain --service "$SERVICE"   # generates a public URL

echo ""
echo "=================================================================="
echo " pnl-dashboard deployed. Open the domain printed above and log in"
echo " (user: eamon  pass: freqbot2026, unless you set DASH_USER/PASS)."
echo " Tiles populate as each bot reports in (freqtrade poller every 30s)."
echo "=================================================================="
