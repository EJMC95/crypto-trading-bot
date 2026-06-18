#!/bin/sh
# Supervisor: run all 4 freqtrade dry-run bots in one container.
# Each runs in its own restart loop so a crash of one doesn't take down the rest.
# Logs go to stdout (captured by Railway). No --logfile on purpose.
set -u

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

# Keep the container alive as long as any supervisor loop is running.
wait
