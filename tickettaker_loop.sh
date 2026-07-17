#!/bin/sh
# Loop wrapper for 🎫 Ticket Taker's OWN service (Dockerfile.tickettaker).
#
# WHY THIS FILE EXISTS. lighter_ticket_taker.main() is ONE management cycle — a
# run-once process, unlike lighter_trend_bot / lighter_funding_bot which own
# their own `while True` + sleep. In the freqtrade-bots container run_all.sh
# supplies the cadence:
#     while true; do python3 lighter_ticket_taker.py || true; sleep 300; done
# A dedicated service has no run_all.sh, so the cadence must live here. Pairing a
# run-once CMD with railway's restartPolicyType="always" would NOT work: it would
# restart the process the instant it exits — a hot loop hammering the venue with
# no sleep, and every cycle paying a fresh market-list fetch.
#
# `|| true` mirrors run_all.sh: one bad cycle (venue blip, refused order) must
# not kill the loop that manages open positions. It does NOT swallow a boot
# refusal in a way that hides it — the bot marks its own row ERROR before
# raising (_supervised), and an ARMED kill switch / unset TT_VENUE / missing cap
# each refuse loudly on EVERY iteration, so a misconfigured service logs the
# reason every 300s instead of dying once and going quiet.
#
# CADENCE: 300s, identical to the shadow arm's. The two arms must scan the same
# scout payload at the same rate or their records are not comparable, and the
# shadow arm is the control this book's go-live rests on.
set -eu

echo "[tickettaker-loop] starting | TT_VENUE=${TT_VENUE:-<unset>} | cadence 300s"

while true; do
    python3 /app/lighter_ticket_taker.py || true
    sleep 300
done
