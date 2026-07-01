#!/bin/sh
# Supervisor for the dedicated perps-regime-switch service: run the single
# RegimeSwitchV1 dry-run bot + publish its P&L to the shared Postgres table so
# it appears on the unified pnl_dashboard alongside the rest of the fleet.
# Mirrors run_all.sh, but one bot instead of five. Logs go to stdout (Railway).
set -u

# Point the shared poller at just this bot (name must match pnl_dashboard EXPECTED,
# port must match api_server.listen_port in config_regimeswitch.json).
export FT_POLLER_BOTS='[["perps-regime-switch", 8089]]'

# freqtrade in its own restart loop so a transient crash self-heals.
(
  while true; do
    echo "[supervisor] starting perps-regime-switch (RegimeSwitchV1)"
    freqtrade trade --config user_data/config_regimeswitch.json
    echo "[supervisor] perps-regime-switch exited ($?) — restarting in 10s"
    sleep 10
  done
) &

# Publish P&L to Postgres. Guarded: no-op if DATABASE_URL is unset.
while true; do
  echo "[supervisor] starting regime pnl poller"
  python3 /freqtrade/freqtrade_pnl_poller.py
  echo "[supervisor] pnl poller exited — restarting in 15s"
  sleep 15
done &

# Keep the container alive as long as any supervisor loop is running.
wait
