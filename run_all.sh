#!/bin/sh
# Supervisor for the freqtrade fleet.
# Two modes:
#   default   — the freqtrade-bots container: the 5 ORIGINAL spot bots +
#               dashboard + market pulse + poller + learning brain.
#   ONLY_BOT  — a dedicated single-bot Railway service (family bots): runs
#               exactly one bot + a poller scoped to it via FT_POLLER_BOTS.
#               No dashboard/pulse/brain here (those live in the main container).
# [2026-07-07 OPTION-B] Family bots (mum/dad/avo-maria/georgia) were REMOVED
# from this container: their dedicated services had been building from this
# same Dockerfile and therefore each ran ALL NINE bots with fresh $1000 wallets
# plus a 9-name poller — five pollers race-writing bot_pnl (the "counter reset"
# flapping of Jul 5-7). One bot, one home, one writer.
# Each runs in its own restart loop so a crash of one doesn't take down the rest.
# Logs go to stdout (captured by Railway). No --logfile on purpose.
set -u

# VOLUME OWNERSHIP SHIM (2026-07-03). Railway mounts the /freqtrade/persist
# volume owned by root, but freqtrade is installed for (and must run as)
# ftuser. The service sets RAILWAY_RUN_UID=0 so we start as root, fix the
# mount's ownership, then re-exec this script as ftuser. su resets PATH, so
# re-add ftuser's pip-install bin dir where the freqtrade CLI lives.
if [ "$(id -u)" = "0" ]; then
  chown -R ftuser:ftuser /freqtrade/persist
  exec su ftuser -s /bin/sh -c \
    'export PATH="/home/ftuser/.local/bin:$PATH"; exec sh /freqtrade/run_all.sh'
fi

run_bot() {
  cfg="$1"
  name="$2"
  while true; do
    echo "[supervisor] starting $name ($cfg)"
    freqtrade trade --config "$cfg"
    code=$?
    echo "[supervisor] $name exited (code $code) — restarting in 10s"
    sleep 10
  done
}

run_poller() {
  while true; do
    echo "[supervisor] starting freqtrade pnl poller"
    python3 /freqtrade/freqtrade_pnl_poller.py
    echo "[supervisor] pnl poller exited — restarting in 15s"
    sleep 15
  done
}

# --- Dedicated single-bot service mode (family bots) -------------------------
if [ -n "${ONLY_BOT:-}" ]; then
  cfg="user_data/config_${ONLY_BOT}.json"
  if [ ! -f "$cfg" ]; then
    echo "[supervisor] FATAL: ONLY_BOT=${ONLY_BOT} but $cfg not found"; exit 1
  fi
  port=$(python3 -c "import json;print(json.load(open('$cfg'))['api_server']['listen_port'])")
  pub_name="freqtrade-$(echo "$ONLY_BOT" | tr '_' '-')"
  export FT_POLLER_BOTS="[[\"${pub_name}\", ${port}]]"
  echo "[supervisor] ONLY_BOT mode: ${pub_name} on :${port} (poller scoped)"
  run_poller &
  run_bot "$cfg" "$ONLY_BOT" &
  wait
  exit 0
fi

# --- Main container: the 5 original spot bots --------------------------------
run_bot user_data/config_v4_core.json   v4core   &   # crypto-trend-daily   · ImprovedStrategyV4 · daily trend
run_bot user_data/config_v5_kraken.json  v5gated  &   # crypto-intraday-15m  · DayTraderV5Gated  · 15m
run_bot user_data/config_v6_swing.json   v6swing  &   # crypto-swing-daily   · SwingDipV1        · dip buyer
run_bot user_data/config_v7_momo.json    v7momo   &   # crypto-breakout-4h   · MomoBreakoutV1    · 4h breakout
# [2026-07-12 RETIRED] v8momo (crypto-trendmomo-4h · TrendMomoV1) — core leg
# backtests -29%/4.5y (26.5% win) on the bear_bounce audit replay and bled
# live (-$11.33); user-approved retirement. Row moved to dashboard RETIRED_ROWS.

# Family bots (mum/dad/avo-maria/georgia) run in their OWN Railway services
# via ONLY_BOT mode above — do NOT re-add them here (see CHANGELOG 2026-07-07).

# Combined P&L + trades dashboard, served on $PORT (Railway exposes it).
python3 /freqtrade/dashboard_server.py &

# Market pulse collector (news/social/funding mood) -> Postgres bot_state
# every 10 min. All bots feed from this for sizing decisions.
while true; do
  python3 /freqtrade/market_pulse.py || true
  sleep 600
done &

# Publish each freqtrade bot's P&L to the shared Postgres table so they show on
# the unified pnl_dashboard alongside perps/momo/arb/sniper. Guarded: no-op if
# DATABASE_URL is unset. Restart-looped so a transient error can't kill it.
run_poller &

# [2026-07-05] Run the learning brain every 2h. Reads the trade ledger across
# ALL bots (original + new fleet), correlates with market_pulse signals, and
# writes lessons to bot_state 'learning-brain'. Read-only / advisory.
( sleep 300
  while true; do
    echo "[supervisor] running learning brain (bot_learn.py)"
    python3 /freqtrade/bot_learn.py || true
    sleep 7200
  done ) &

# [2026-07-07 CROSS-BOT L1] Regime oracle — ONE shared read of the tape
# (per-major direction + ADX character) -> bot_state 'regime-oracle' +
# bot_state_history. ADVISORY week one: nothing consumes it yet.
( sleep 120
  while true; do
    python3 /freqtrade/regime_oracle.py || true
    sleep 1800
  done ) &

# [2026-07-14 GHOST-EXPOSURE CLEANUP] One-shot on boot: prune retired bots'
# frozen bot_pnl rows (explicit allow-list in the script; deleting an absent
# row is a no-op, so re-running every deploy is safe). Bounce Catcher's and
# Trail Blazer's dead rows were pinning the fleet light RED on 22 phantom
# longs. Runs before fleet_risk's first cycle so the light starts clean.
( sleep 60
  python3 /freqtrade/cleanup_legacy_bots.py --apply || true ) &

# [2026-07-07 CROSS-BOT L2/L3] Fleet risk traffic light + signal bus —
# fleet-wide directional exposure vs budgets + scanner exhaust ->
# bot_state 'fleet-risk' / 'signal-bus'. ADVISORY: enforcement wiring is
# decided from ~7 days of this history, not vibes.
( sleep 90
  while true; do
    python3 /freqtrade/fleet_risk.py || true
    sleep 300
  done ) &

# [2026-07-14 LIGHTER SCOUT] Venue-wide Lighter market map (all 215 books:
# premium stress, liquid funding extremes, cross-venue funding divergence,
# volume/OI moves, listings) -> bot_state 'lighter-market' + history.
# ADVISORY/publish-only, same doctrine as the bus. Two keyless calls per run.
( sleep 150
  while true; do
    python3 /freqtrade/lighter_market_scout.py || true
    sleep 300
  done ) &

# Keep the container alive as long as any supervisor loop is running.
wait
