#!/bin/sh
# Supervisor: run all 4 freqtrade dry-run bots in one container.
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

run_bot user_data/config_v4_core.json   v4core   &
run_bot user_data/config_v5_kraken.json  v5gated  &
run_bot user_data/config_v6_swing.json   v6swing  &
run_bot user_data/config_v7_momo.json    v7momo   &
run_bot user_data/config_v8_momo.json    v8momo   &

# Combined P&L + trades dashboard, served on $PORT (Railway exposes it).
python3 /freqtrade/dashboard_server.py &

# Market pulse collector (news/social/funding mood) -> Postgres bot_state
# every 10 min. Strategies read it for informed SIZING (never entries), the
# brain correlates trades with the mood they were opened in, and the
# pnl-dashboard serves it at /pulse.json. Guarded: a failed cycle just retries.
while true; do
  python3 /freqtrade/market_pulse.py || true
  sleep 600
done &

# Publish each freqtrade bot's P&L to the shared Postgres table so they show on
# the unified pnl_dashboard alongside perps/momo/arb/sniper. Guarded: no-op if
# DATABASE_URL is unset. Restart-looped so a transient error can't kill it.
while true; do
  echo "[supervisor] starting freqtrade pnl poller"
  python3 /freqtrade/freqtrade_pnl_poller.py
  echo "[supervisor] pnl poller exited — restarting in 15s"
  sleep 15
done &

# Keep the container alive as long as any supervisor loop is running.
wait
