#!/bin/sh
# taker_live_entry.sh — the LIVE Ticket Taker's loop.
#
# WHY A LOOP SCRIPT AND NOT A BARE CMD: lighter_ticket_taker.py is a RUN-ONCE
# process (one management cycle, then exit). In the shared freqtrade-bots
# container run_all.sh provides the loop; a dedicated live service needs its
# own. Leaving Railway's restartPolicy to do it would rebuild the container per
# cycle, throw away the ws book cache and re-pay the market load every time,
# and hit restart backoff exactly when the book most needs managing.
#
# `|| true` IS DELIBERATE, and it is the whole point of a live loop: a single
# bad cycle (venue blip, rate-limit storm, a REFUSED boot) must not end the
# process, because THE LOOP IS THE POSITION MANAGER. If it exits, whatever is
# on the book has no stop, no max-hold and nothing watching it. Every rail —
# kill switch, daily-loss, notional cap, equity guard — runs per cycle inside
# main(), so the loop staying alive IS the safety property. A refusal simply
# repeats every cycle and the row shows it (the taker marks its own row ERROR
# on a crash, and the boot refusals publish through SafetyRails).
#
# TT_VENUE is NOT defaulted here. The taker refuses to start without it: this
# bot's identity — and whether it moves REAL MONEY — must be a declared choice
# on the service, never inherited from an image (17-Jul, the rule f44e3eb
# applied to the other two real-money bots). A freshly created service
# therefore does NOTHING until an operator sets it, which is the correct
# posture for a live image.
set -u

: "${TT_LOOP_SECONDS:=300}"   # match the shadow arm's cadence so the two arms
                              # stay comparable (implementation_shortfall pairs
                              # live vs shadow closes on the same coins)

echo "[taker-live-entry] starting loop: TT_VENUE=${TT_VENUE:-<UNSET — the bot will refuse>} every ${TT_LOOP_SECONDS}s"

while true; do
    python3 lighter_ticket_taker.py || true
    sleep "$TT_LOOP_SECONDS"
done
