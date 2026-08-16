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

# --- Main container ----------------------------------------------------------
# [2026-07-14 KRAKEN RETIREMENT — user instruction: "Retire the kraken bots,
# let's just focus on lighter"] The 4 spot originals (v4core/v5gated/v6swing/
# v7momo -> crypto-trend/intraday/swing/breakout) NO LONGER LAUNCH here; their
# Lighter shadow twins (family-lighter service, gate0) are the fleet now, and
# Tide Rider's LIVE Lighter book keeps running. The freqtrade poller goes with
# them (nothing local to poll). This container keeps the fleet ORGANS: pulse,
# brain, oracle, risk light, Lighter Scout, Ticket Taker, cleanup.
# The 4 family Railway services (ONLY_BOT mode: mum/dad/avo-maria/georgia)
# must be STOPPED by the operator in the Railway UI — ONLY_BOT stays
# functional so a still-running service doesn't crash-loop meanwhile.
# [2026-07-12 RETIRED] v8momo (crypto-trendmomo-4h · TrendMomoV1) — core leg
# backtests -29%/4.5y (26.5% win) on the bear_bounce audit replay and bled
# live (-$11.33); user-approved retirement. Row moved to dashboard RETIRED_ROWS.

# [2026-07-15 AUDIT FIX] dashboard_server.py retired from main mode: it
# polled 127.0.0.1:8084-8088 for the five RETIRED local freqtrade bots
# (v4core..v8momo) — dead ports since the Kraken retirement. The real
# dashboard is the pnl-dashboard Railway service; this container needs no
# HTTP listener (no healthcheckPath configured).

# Market pulse collector (news/social/funding mood) -> Postgres bot_state
# every 10 min. All bots feed from this for sizing decisions.
while true; do
  python3 /freqtrade/market_pulse.py || true
  sleep 600
done &

# [2026-07-16 EVENT ORGAN] Event Sentinel 🗞️⚡ — typed MAJOR-EVENT detection
# (RSS + GDELT) + historical sector-ripple playbook + self-grading against
# the scout's marks -> bot_state 'event-sentinel'. [comment corrected 4-Aug
# per I12: it HAS consumers — replay-gated proposals steer the SHADOW taker's
# levers via the scout tuner (22-Jul (ci)); real money untouched.] Offset from
# pulse so the two news fetchers don't hit feeds in the same second.
( sleep 240
  while true; do
    python3 /freqtrade/event_sentinel.py || true
    sleep 600
  done ) &

# [2026-07-14 KRAKEN RETIREMENT] main-mode poller removed with the spot bots —
# there are no local freqtrade APIs left to poll here. ONLY_BOT services keep
# their scoped poller until the operator stops them.

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
# bot_state_history. [comment corrected 4-Aug per I12: CONSUMED — the family
# bot's per-asset regime gate rides oracle verdicts for non-crypto (30-Jul).]
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
# bot_state 'fleet-risk' / 'signal-bus'. [comment corrected 4-Aug per I12:
# mode=ENFORCE — strategies veto new longs at budget; kill switch
# FLEET_RISK_MODE=advisory.]
( sleep 90
  while true; do
    python3 /freqtrade/fleet_risk.py || true
    sleep 300
  done ) &

# [2026-07-14 LIGHTER SCOUT] Venue-wide Lighter market map (all 215 books:
# premium stress, liquid funding extremes, cross-venue funding divergence,
# volume/OI moves, listings, per-strategy tickets) -> bot_state
# 'lighter-market' + history. Two keyless calls per run.
( sleep 150
  while true; do
    python3 /freqtrade/lighter_market_scout.py || true
    sleep 300
  done ) &

# [2026-07-14 TICKET TAKER] 🎫 The scout's designated trader (SHADOW $1k
# book): takes the high-conviction subset of the scout's tickets, models
# fills at Lighter marks + funding drag, exits TP/SL/max-hold, tags every
# close <side>-<lens>_<exit> so the brain grades each lens on real forward
# returns. UNVALIDATED by design — that grading is what it exists to collect.
# [2026-07-17] TT_VENUE is DECLARED here, not inherited. The taker now REFUSES
# to start without it (identity must never come from a default — the same rule
# 121f830/f44e3eb applied to the two real-money bots). That guard is inert for
# them because their services set VENUE explicitly; this arm has NO service and
# NO env, so without this line the mandatory guard is not inert — it is LETHAL:
# main() raises SystemExit, _supervised() re-raises it UNTOUCHED (a refusal is
# deliberately not a crash, so the row is never marked), `|| true` swallows it,
# and the shadow arm goes silently dark behind a stale "online" row. That is
# this morning's crash-loop incident exactly, third time in one day.
# lighter_shadow is the correct value AND the safe one: this container hosts the
# SHADOW book — the control arm and the only evidence a go-live can rest on. The
# LIVE arm is a separate service (Dockerfile.tickettaker) and sets its own.
( sleep 210
  while true; do
    TT_VENUE=lighter_shadow python3 /freqtrade/lighter_ticket_taker.py || true
    sleep 300
  done ) &

# [2026-07-15 EVIDENCE BOARD v2] ⚖️ the evidence organ: scores + corroborates
# the fleet-alerts feed, SYNTHESIZES cross-feed evidence (lens ruling floors,
# veto flap, venue stress, governor proximity, budget crowding), auto-verdicts
# the mechanical items (manual evidence-review verdicts stay senior), pushes
# new warn/action items to the operator's phone (NTFY_TOPIC — the watchdog's
# channel), and publishes SHADOW-MODE restrict-only proposals -> bot_state
# 'evidence-board'. Nothing consumes the proposals until a review flips
# EVBOARD_MODE=publish — the same earn-your-wiring path the L2 light walked.
( sleep 330
  while true; do
    python3 /freqtrade/evidence_board.py --once || true
    sleep "${EVBOARD_INTERVAL_SEC:-600}"
  done ) &

# [2026-07-15 SCOUT TUNER] 🧠🔧 the Lighter loop's self-tuning organ (user
# mandate: the scanner "needs the freedom, with the brain's support, to act").
# Hourly: replays the recorded scout tape through the taker's REAL code,
# widens starving lenses' bars (not-worse on both halves), expands
# brain-graded winners (must IMPROVE both halves), sweeps the TP/SL/hold
# grid (anti-overfit floors), widens starving lenses' scout emission (the
# brain's grading diet). Everything lands as bounded TTL'd fleet_tuning
# levers that expire back to env defaults unless re-asserted — auto-revert
# is the resting state. First cycles need tape: it skips below 60 snapshots.
# [2026-08-16 (ou)] BOOT LADDER + ONE RUN PER BOOT — the (os) fix, generalised
# to the seven siblings that were silent alongside 🛡️ the immune organ.
# A boot stagger longer than the gap between container restarts is an organ
# that NEVER RUNS: freqtrade-bots redeployed 10x between 03:40Z and 04:09Z
# (gaps 0:36-7:31) and EVERY organ staggered >=420s executed zero times for
# ~50 minutes. The shape: a short distinct offset (5..35s) so the boot burst
# is still spread, then ONE guaranteed run, then the ORIGINAL stagger to
# restore the steady-state phase separation the ladder exists to give.
# Steady-state cadence and phase are unchanged; a restart now costs one
# duplicated run per organ instead of the organ.
# The offsets are short ON PURPOSE: the failure was a delay outrunning the
# restart interval, so a long one here would rebuild the bug. All seven
# import no pandas/numpy/sklearn (checked) — stdlib+psycopg2 processes, so a
# 5s-spaced boot burst is spread, not a herd.
( sleep 5
  python3 /freqtrade/lighter_scout_tuner.py || true
  sleep 420
  while true; do
    python3 /freqtrade/lighter_scout_tuner.py || true
    sleep "${TUNER_INTERVAL_SEC:-3600}"
  done ) &

# [2026-07-16 PROPRIOCEPTION] 🦾 the autonomy stack's sense of its OWN
# movements: tracks every growth-rail lever episode (open -> expire/release/
# change), grades it retrospectively OUT-OF-SAMPLE (taker levers get the
# replay counterfactual in $ on the tape recorded DURING the episode; scout
# diet levers get grading throughput; gapscout gets census activity;
# live/xp record-only — the judge stays the real-money authority), and
# publishes per-lever helping/hurting verdicts. The scout tuner consumes
# HURTING restrict-only: a movement that measured net-negative in reality
# stops being repeated. Fail-safe: a dark organ restricts nothing.
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 10
  python3 /freqtrade/fleet_proprioception.py || true
  sleep 540
  while true; do
    python3 /freqtrade/fleet_proprioception.py || true
    sleep "${PROPRIO_INTERVAL_SEC:-900}"
  done ) &

# [2026-07-15 EXPERIMENT JUDGE] 🧪⚖️ the shadow→live promotion pipeline
# (user: shadow wins must "carry across to the real money bots"). Hourly:
# runs ONE candidate at a time on the Funding Farmer's shadow arm (xp.*
# levers), and promotes to the live arm (live.funding.*) ONLY after the
# paired bar — >=7d, >=30 shadow closes, beats live per-trade by the margin
# on the window AND both halves. Fade-watch releases a promotion whose live
# performance turns. All TTL'd; phone-pushed per transition.
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 15
  python3 /freqtrade/experiment_judge.py || true
  sleep 480
  while true; do
    python3 /freqtrade/experiment_judge.py || true
    sleep "${XPJ_INTERVAL_SEC:-3600}"
  done ) &

# [2026-07-15 IMMUNE ORGAN] 🛡️ the fleet's immune + self-repair layer (from
# the operator's "what organ self-repairs / what filters" framing, and the
# same evening's live incident where a 39h-stale artifact drove a false live
# down-scale). Every ~15 min: FILTERS the alert bloodstream (prune age-stale
# + known-toxic antibody matches), DETECTS fresh-but-wrong organ payloads
# (the failure class the death-oriented watchdog misses), QUARANTINES a sick
# growth-rail lever (fleet_tuning honors it -> reverts to operator default),
# phone-pushes NEW sickness. Restrict/clean only; fail-safe (dead immune =
# no quarantine).
# [2026-08-16 (os)] ONE RUN BEFORE THE BOOT STAGGER, because a stagger longer
# than the gap between container restarts means the organ NEVER RUNS AT ALL.
# MEASURED: freqtrade-bots redeployed 10x between 03:40Z and 04:09Z (gaps
# 0:36-7:31, every one under this 540s fuse), and 🛡️ the immune organ went
# from 03:38:49Z to 41+ minutes with ZERO executions — killed mid-fuse on
# every boot. Its own restart counter was not the sensor either: the
# Parliament's `restarts` climbed 3->5 across the same window, so the
# container churn was plainly visible while the organ that exists to notice
# such things was the one thing not running.
#
# WHY NOTHING CAUGHT IT, and this is the part worth keeping: the organ
# publishes `ttl_sec` 2400 against a 900s loop, so a 40-minute silence is
# still INSIDE its own freshness contract and the watchdog sees a healthy
# key. And `audit_organ_silence` ((hw)) cannot cover this class by
# construction — it routes organs through `organ_main` so a CRASH is
# recorded on the organ's own key, but a process killed during `sleep` never
# reaches main(), so there is nothing to record and nobody to record it.
# Crash-reporting and never-starting are different failures.
#
# The fix is one guaranteed execution per boot, BEFORE the stagger; the
# stagger then does its original thundering-herd job for every subsequent
# cycle, and steady-state cadence is unchanged. A restart now costs at most
# one duplicated run instead of the whole organ.
#
# NOT FIXED HERE, and declared rather than silently left: seven sibling
# organs carry the same shape (proprioception 540, judge 480, scout-tuner
# 420, incubator 600, regen 660, radar 660, impl-shortfall 720) and every
# one of them was ALSO silent across this window. They are not patched in
# the same pass because applying this to all eight recreates at boot exactly
# the herd the staggers exist to spread, and that trade wants its own
# measurement. 🛡️ goes first because it is the pageable safety organ and the
# only one whose silence disables a live actuator (lever quarantine).
( python3 /freqtrade/fleet_immune.py || true
  sleep "${IMMUNE_BOOT_STAGGER_SEC:-540}"
  while true; do
    python3 /freqtrade/fleet_immune.py || true
    sleep "${IMMUNE_INTERVAL_SEC:-900}"
  done ) &

# [2026-07-15 CIRCADIAN] 🕐 the fleet's coordinated sense of time (session /
# thin-liquidity / heavy-ok). Advisory; published for any organ to read.
# v2 2026-07-16: NYSE calendar + open/close EVENTS for every market +
# event_window, so consumers can allocate resources around any open/close.
# 5-min cadence keeps the sampled window flags honest (ttl 15 min).
( sleep 200
  while true; do
    python3 /freqtrade/fleet_clock.py || true
    sleep "${CLOCK_INTERVAL_SEC:-300}"
  done ) &

# [2026-07-15 REGENERATION] 🩹 self-repair tier 2: restores a stateful organ
# the immune organ flagged SICK to its last-good history snapshot (or a safe
# baseline). Runs AFTER the immune organ so it acts on fresh findings.
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 20
  python3 /freqtrade/fleet_regen.py || true
  sleep 660
  while true; do
    python3 /freqtrade/fleet_regen.py || true
    sleep "${REGEN_INTERVAL_SEC:-900}"
  done ) &

# [2026-07-15 REPRODUCTION] 🧬 breeds strategy genotypes: taker offspring
# scored instantly by replay (shadow-only), funding offspring proposed to
# 'xp-queue' for the experiment judge's paired live-promotion bar (gated).
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 25
  python3 /freqtrade/strategy_incubator.py || true
  sleep 600
  while true; do
    python3 /freqtrade/strategy_incubator.py || true
    sleep "${INCUBATOR_INTERVAL_SEC:-3600}"
  done ) &

# [2026-07-15 RESPIRATION] 🫁 blood-oxygen monitor: the SUPPLY side the
# watchdog (death) and immune organ (sickness) miss — is the fleet still
# BREATHING fresh market data? SpO2 saturation + hypoxia phone alert.
( sleep 240
  while true; do
    python3 /freqtrade/fleet_respiration.py || true
    sleep "${RESP_INTERVAL_SEC:-600}"
  done ) &

# [2026-07-15 IMPL SHORTFALL] 📏 live-vs-shadow execution-quality tracker:
# the continuous per-trade gap (live real fills − shadow mark fills) on the
# SAME coins, with entry/exit-slip decomposition as fill prices accrue. The
# clean yes/no on "is the live Funding Farmer slipping?" (30-min).
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 30
  python3 /freqtrade/implementation_shortfall.py || true
  sleep 720
  while true; do
    python3 /freqtrade/implementation_shortfall.py || true
    sleep "${SHORTFALL_INTERVAL_SEC:-1800}"
  done ) &

# [2026-07-23 EDGE RADAR] 📡 grades every LIVING book on a constellation of
# independent sensors — significance (t-stat), both-halves stability,
# median/jackknife robustness (the median catches the funding-carry false
# positive a lone t-stat waved through), concentration, trade rate — plus an
# ETA to a |t|>=2 verdict at the current effect size -> bot_state 'fleet-radar'.
# The standing version of the 22/23-Jul edge analysis, so feed/park/cull is a
# read rather than a re-derivation. PUBLISH-ONLY: no consumer, no actuator;
# --publish is explicit so a bare run never writes the live bus.
# [(ou)] boot ladder — see the note above the scout tuner.
( sleep 35
  python3 /freqtrade/fleet_radar.py --publish || true
  # [2026-08-01 (hv)] 💰 allocation view: where SHOULD the capital be?
  # Publish-only and advisory — it moves no capital and writes no lever.
  python3 /freqtrade/fleet_allocation.py --publish || true
  sleep 660
  while true; do
    python3 /freqtrade/fleet_radar.py --publish || true
    # [2026-08-01 (hv)] 💰 allocation view: where SHOULD the capital be?
    # Publish-only and advisory — it moves no capital and writes no lever.
    python3 /freqtrade/fleet_allocation.py --publish || true
    sleep "${RADAR_INTERVAL_SEC:-1800}"
  done ) &

# [2026-07-30 GO-LIVE GRADER] 🚦 grades every living book against the (fk)
# go-live bar (>=30d, >=30 closes, mean>0, t>=2.0, both halves +, maxDD<15%)
# -> bot_state 'golive-readiness', which the dashboard renders. The rule that
# governs REAL MONEY had no schedule and no publisher: it ran when a human
# remembered, so between reviews nobody could see how close a book was. Same
# "a rule nobody runs is not a control" class as the 38 unrun selftests.
# 6-hourly is plenty — the bar's shortest term is a 30-DAY window. PUBLISH-
# ONLY: promotes nothing, writes no lever; go-live is an operator act.
( sleep 900
  while true; do
    python3 /freqtrade/scripts/golive_readiness.py --publish || true
    sleep "${GOLIVE_INTERVAL_SEC:-21600}"
  done ) &

# [2026-07-21 PARLIAMENT] 🏛️ the six-layer PM shadow fleet (operator ask:
# comprehensive self-evolving system, bots named for the last 8 Australian
# PMs). ONE asyncio process carrying all six layers: Lighter-only data,
# Keating's 10 scanners + 5-model ML ensemble, the six $1k SHADOW books
# (pm-albanese/morrison/turnbull/abbott/rudd/gillard, rows *-lshadow),
# their six bounded TTL'd tuners, and Howard the ecosystem brain ->
# bot_state 'parliament' + 'parliament-tuning'. No keys, no signing, no
# orders — shadow-first like every book before it. PARLIAMENT_ENABLED=0
# idles the chamber (the process idles rather than exits — the Trail
# Blazer restart-loop lesson).
( sleep 360
  while true; do
    python3 /freqtrade/parliament_main.py || true
    echo "[supervisor] parliament exited — restarting in 30s"
    sleep 30
  done ) &

# Keep the container alive as long as any supervisor loop is running.
wait
