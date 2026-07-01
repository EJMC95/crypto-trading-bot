#!/bin/sh
# deploy_all.sh — ship the LATEST code to every Railway service in one command.
#
# WHY THIS EXISTS (the redeploy bug it fixes):
#   * Auto-Deploy is inconsistent across services: on a `git push`, some services
#     rebuild (perps-bot, momo-bot, freqtrade-trainer, triangular-arb) but others
#     do NOT (freqtrade-bots, listing-sniper, cross-exchange-arb, pnl-dashboard),
#     so pushed code silently never shipped to those.
#   * `railway redeploy` re-runs a service's CURRENT (old) image — it does NOT
#     ship new code. Only `railway up` uploads the current source and builds a
#     fresh deployment.
#   This script runs `railway up` for EVERY service, so one command guarantees
#   the whole fleet is running the latest committed code. Idempotent + safe: all
#   bots are dry-run/paper.
#
# USAGE:
#   ./deploy_all.sh                 # deploy all crypto services (Trading Bots project)
#   ./deploy_all.sh freqtrade-bots listing-sniper   # deploy only the named services
#
# NOTE: each service's Dockerfile/config is chosen by its Railway "Config-as-code"
# setting (railway.<svc>.toml or RAILWAY_DOCKERFILE_PATH), so `railway up -s NAME`
# builds the right image automatically. Stock bots (ikbr-stock-bot, alpaca-
# momentum) live in SEPARATE Railway projects — deploy those from their own dirs.

set -u

PROJECT_ID="9b3b7d3c-28db-417b-b864-ebc065df851f"   # "Trading Bots" project
ALL_SERVICES="freqtrade-bots perps-bot momo-bot triangular-arb cross-exchange-arb listing-sniper freqtrade-trainer pnl-dashboard perps-regime-switch"

command -v railway >/dev/null 2>&1 || { echo "Railway CLI not found (npm i -g @railway/cli)"; exit 1; }
railway whoami >/dev/null 2>&1 || { echo "Not logged in — run: railway login"; exit 1; }

SERVICES="${*:-$ALL_SERVICES}"
echo "==> Deploying latest code to: $SERVICES"
railway link --project "$PROJECT_ID" >/dev/null 2>&1 || true

fail=""
for svc in $SERVICES; do
  echo "----- railway up -s $svc -----"
  if railway up -s "$svc" --detach; then
    echo "  queued: $svc"
  else
    echo "  FAILED: $svc"
    fail="$fail $svc"
  fi
done

echo
echo "==> Triggered. Current status:"
railway status 2>/dev/null | sed -n '/Services/,/Databases/p'
[ -n "$fail" ] && { echo "!! FAILED:$fail"; exit 1; }
echo "==> All deploys queued OK. Builds finish in ~1-4 min; verify with: railway status"
