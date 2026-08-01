#!/usr/bin/env python3
"""
evidence_board.py — the fleet's EVIDENCE BOARD organ (v2, shipped 2026-07-15
on user instruction: "make the evidence board more advanced … an even more
integrated system the scanners and brain have to work with"; freeze lifted by
the user the same evening).

WHAT IT IS
The evidence board used to be a passive banner: market_context appended
alerts, a daily session hand-wrote verdicts, the dashboard subtracted the two.
This organ makes the board a live participant:

  1. LIFECYCLE + SCORING — every alert key gets first_seen / fires / trend
     (escalating | steady | decaying) and a composite score:
     severity x recency-decay x persistence x corroboration. Corroboration is
     mechanical: a dislocation alert scores higher while the scout's own
     stress/premium feed independently agrees.
  2. SYNTHESIS — the board CREATES evidence the alert feed can't see because
     it joins feeds nobody else joins: venue stress vs the taker's veto bar,
     lens-forward crossing its n4h ruling floor (and lenses NEGATIVE at the
     floor), the drawdown governor approaching its clip line, budget
     crowding, and coin-veto FLAP (a coin oscillating across the veto
     threshold). AND — since 15-Jul late (user: "it's so restrict heavy …
     completely one sided") — the EXPAND side with the same machinery:
     lenses POSITIVE at the ruling floor (🏆), shadow books passing the
     provisional promotion screen (🚀), the scout tuner's live enactments
     (🌱), and restrictions that never bind (🔓). Expand items push to the
     phone like warnings do — missing the cream is also a miss.
  3. AUTO-VERDICTS — mechanical verdicts (milestones auto-stale after 24h,
     dislocations fold into the census after 24h unless escalating, veto
     records age out at 48h). MANUAL verdicts in bot_state['evidence-review']
     always win — the daily review and the operator stay senior to the organ.
  4. RESPONSE — three tiers, honest about authority:
       NOTIFY (live): new warn/action items or escalations push to the
         operator's phone (same NTFY_TOPIC channel as the watchdog),
         min EVBOARD_NOTIFY_GAP_H per key.
       PROPOSE (shadow): every RESTRICT response rule names an EXISTING
         restrict-only lever (lens veto, clip scale, stress veto, budget)
         and what it WOULD do. Published in the payload, consumed by
         NOTHING until a review flips EVBOARD_MODE=publish — the same
         earn-your-wiring path the L2 risk light walked.
       ENACT (live, GROWTH RAIL — 15-Jul user instruction: "the scanner
         needs to be able to implement opening or altering … or widening
         something too so growth can happen fleet wide"): EXPAND-direction
         responses go through fleet_tuning's whitelisted, hard-bounded,
         TTL'd lever registry. Today's ladder: when the Gap Scout census
         runs quiet, the board autonomously widens the scanner's detection
         net (prefilter, book budget, second-tier venues) — and because
         every lever EXPIRES unless re-asserted each cycle, reverting is
         the resting state. Only lanes in FLEET_TUNING_ENACT_LANES are
         enactable (the shipped default includes the scanner/scout/taker/xp
         lanes AND lighter-live — the 15-Jul user-mandated live lane), and
         fleet_tuning's AUTHOR_LANES binds each author to its own lanes:
         this board may write live.clip_scale and nothing else live.

WHAT IT NEVER DOES
  Open positions, place orders, or move a lever past its registry bounds.
  On real money its whole reach is live.clip_scale [0.5-1.5] on the two
  live Lighter bots (16-Jul: up-scale gates fail CLOSED on missing/stale
  telemetry) — go-live, keys, and the operator's SafetyRails notional caps
  stay operator-only. The growth rail can only move levers that are
  registered in fleet_tuning with hard bounds, on explicitly enactable
  lanes. Opportunity flow stays where it already lives: scout tickets ->
  Ticket Taker's shadow book -> brain grading -> review promotion.

Publishes bot_state['evidence-board'] (+ lean history when available):
  {updated, ttl_sec, mode, items:[{key, msg, sev, score, fires_24h, trend,
   verdict, source, proposal}], proposals:[...], notified:{key: ts}}
Consumers: pnl_dashboard (board card + banner suppression), the daily
evidence review, and the operator's phone. Fail-silent; backtests inert
(no DATABASE_URL -> every store call no-ops).
"""
import json
import math
import os
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

try:
    import fleet_tuning as tuning     # the growth rail (optional import)
except Exception:  # noqa: BLE001
    tuning = None

BOARD_KEY = "evidence-board"
INTERVAL = int(os.environ.get("EVBOARD_INTERVAL_SEC", "600"))
MODE = os.environ.get("EVBOARD_MODE", "shadow").strip().lower()   # shadow|publish
NOTIFY_GAP_H = float(os.environ.get("EVBOARD_NOTIFY_GAP_H", "6"))
# [2026-07-17] Reminder cadence for a warn/action board item that is STILL true
# long after its onset page. Deliberately much slacker than NOTIFY_GAP_H (which
# is the floor between ANY two pushes for one key): this is "that thing is
# still broken", not a nag. 12h means an overnight problem is on the phone by
# morning instead of having been announced once and forgotten.
RENOTIFY_H = float(os.environ.get("EVBOARD_RENOTIFY_H", "12"))
WINDOW_H = 48          # board horizon — matches the dashboard banner
TTL_SEC = 3 * INTERVAL

SEV_W = {"info": 1.0, "warn": 3.0, "action": 4.0}
DECAY_HALF_LIFE_H = 12.0

# lens-forward ruling floor (agenda item 2) and the "negative at the floor" bar
LENS_FLOOR_N4H = int(os.environ.get("EVBOARD_LENS_FLOOR", "75"))
LENS_NEG_AVG4H = float(os.environ.get("EVBOARD_LENS_NEG_AVG4H", "-0.5"))
STRESS_VETO_BPS = float(os.environ.get("TT_STRESS_VETO_BPS", "15"))
DD_NEAR_TRIP = float(os.environ.get("EVBOARD_DD_NEAR_TRIP", "-0.035"))
# the lens feed's usability window (~7.2h — the brain publishes hourly; a
# payload older than this is a fossil, not evidence). [2026-07-16 BALANCE
# FIX] BOTH sides now gate on it: the expand side always did, but the
# restrict side read the raw payload — a dead brain's last lens table kept
# firing lens-negative warns (and lens-veto proposals) indefinitely.
LENS_FRESH_S = float(os.environ.get("EVBOARD_LENS_FRESH_S", "26000"))


def _now():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or _now(), tz=timezone.utc).isoformat(timespec="seconds")


def _fresh(state, max_age_s=2700):
    """A feed is usable if its own `updated` stamp is younger than max_age_s
    (fail-safe: unusable feeds contribute NOTHING — no synthesis, no boost).
    [2026-07-16 AUDIT FIX] a payload's OWN ttl_sec now tightens the window —
    the fixed 2700s let a 40-min-stale fleet-risk (ttl 900s) keep gating the
    real-money up-scale, violating the fleet's updated+ttl_sec doctrine."""
    try:
        u = datetime.fromisoformat(str(state.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        limit = float(max_age_s)
        try:
            ttl = float(state.get("ttl_sec") or 0)
            if ttl > 0:
                limit = min(limit, ttl)
        except Exception:
            pass
        return (_now() - u.timestamp()) <= limit
    except Exception:
        return False


# ---------------------------------------------------------------------------
# pure functions (selftested)
# ---------------------------------------------------------------------------

def score_item(sev, age_h, fires_24h, corroborated):
    """severity x recency-decay x persistence x corroboration -> one number
    the dashboard can sort by. Monotone in every input by construction."""
    w = SEV_W.get(sev, 1.0)
    decay = 0.5 ** (max(0.0, age_h) / DECAY_HALF_LIFE_H)
    persistence = 1.0 + math.log(max(1, fires_24h))
    boost = 1.5 if corroborated else 1.0
    return round(w * decay * persistence * boost, 3)


def trend_of(fires_recent_12h, fires_prior_12h):
    if fires_recent_12h > fires_prior_12h:
        return "escalating"
    if fires_recent_12h < fires_prior_12h:
        return "decaying"
    return "steady"


def auto_verdict(key, sev, age_h, trend):
    """Mechanical verdicts only — anything judgement-shaped returns 'active'
    and waits for the daily review / operator. Manual verdicts always win
    upstream (merge_verdicts)."""
    if key.startswith(("census:", "factor-sample:")):
        # milestone notices: their decision gates live in the standing weekly
        # reviews; once seen for a day they are recorded, not actionable.
        return "stale" if age_h >= 24 else "active"
    if key.startswith("disloc:"):
        # census evidence: folds into the census after a day UNLESS the coin
        # is escalating right now (then it deserves eyes, not archiving).
        return "active" if trend == "escalating" else ("stale" if age_h >= 24 else "active")
    if key.startswith("veto:"):
        # change records: the standing list lives with the scanner; the event
        # itself ages out. Flap detection is a separate synthesized item.
        return "stale" if age_h >= 48 else "active"
    return "active"       # live-shadow-gap, stale-live:*, everything unknown


def merge_verdicts(manual_verdicts, auto_map):
    """{key: verdict} with MANUAL (evidence-review) verdicts senior to auto."""
    out = dict(auto_map)
    for v in manual_verdicts or []:
        k, s = v.get("key"), v.get("status")
        if k and s:
            out[k] = s
    return out


def corroborate(key, lighter_market):
    """Mechanical cross-feed agreement. Only rules that are cheap to check and
    hard to argue with; everything else is un-corroborated (boost 1.0)."""
    if not lighter_market:
        return False
    if key.startswith("disloc:"):
        coin = key.split(":", 1)[1]
        stress = (lighter_market.get("stress") or {})
        if (stress.get("med") or 0) >= 10:
            return True
        outliers = lighter_market.get("prem_outliers") or []
        for o in outliers:
            # [2026-07-28 AUDIT FIX] the scout publishes {"sym": ...}
            # (lighter_market_scout prem_outliers; fleet_risk reads o["sym"]
            # too) — this read said o["symbol"], so for every real entry sym
            # was None and the per-coin branch could NEVER return True: a
            # disloc:<coin> alert only ever got corroborated via the
            # venue-wide stress branch above. Accept both spellings.
            sym = (o.get("sym") or o.get("symbol")) if isinstance(o, dict) \
                else (o[0] if isinstance(o, (list, tuple)) and o else o)
            if str(sym).upper() == coin.upper():
                return True
    return False


# [2026-07-17] fleet-alerts is written on market_context's coin-quality tick
# (QUALITY_EVERY_H, default 6h) and stamped ttl_sec=8h by save_alerts. The bar
# here is generous on purpose: `_fresh` takes min(max_age_s, payload ttl_sec),
# so the PRODUCER's own 8h stamp is what actually rules and this constant only
# has to stay out of its way. The board's default 2700s would have gated a feed
# that is 6h old in perfect health — a "freshness" check that fires on cadence
# teaches you to ignore it.
ALERTS_FRESH_S = float(os.environ.get("EVBOARD_ALERTS_FRESH_S", str(12 * 3600)))


def synthesize_alerts_feed(alerts_raw, now_ts):
    """Is the alert BLOODSTREAM itself still flowing?

    WHY THIS EXISTS, and why it is not a freshness gate on `fa`. Every consumer
    of the alerts list already windows on each alert's OWN `ts`/`last_seen` —
    the live down-reflex at 6h (LIVE_GAP_FRESH_H), veto-flap at 7d, item score
    by 12h decay. A dead producer writes no new timestamps, so all of those go
    quiet by themselves; blanking the list on a feed-level stamp would discard
    individually-valid, individually-windowed alerts and buy nothing.

    What NOTHING defends is the silence itself. An empty alerts list reads
    EXACTLY the same whether the fleet is healthy or market_context has been
    dead for a day — the board's quietest, most reassuring output is also its
    total-failure output. Same shape as the sniper's `watching:201`: ask what a
    metric reads under TOTAL failure, and if the answer is "fine", it is not a
    health check. So: don't drop the data — say the producer stopped.

    Restrict-direction and cheap: one warn item, no lever, no actuator."""
    if _fresh(alerts_raw or {}, ALERTS_FRESH_S):
        return []

    # ABSENT STAMP IS NOT A DEAD PRODUCER — and conflating them would make this
    # organ's FIRST act a false page. market_context runs in its own Railway
    # service, on its own deploy clock, so between this board shipping and
    # market-context shipping save_alerts the feed is legitimately unstamped
    # while perfectly healthy. `_fresh` cannot tell the two apart: no `updated`
    # and a 3-day-old `updated` both land on its except branch as False. So
    # split them at the only place that knows — presence of the key. INFO
    # (board-visible, no phone) for "the producer predates the stamp"; WARN
    # (phone) only for a stamp we can read and that is genuinely old. Cost of
    # the split: during the transition the dark-feed check is inert — which is
    # the status quo, not a regression. If the info item is still there
    # tomorrow, the stamp never arrived and THAT is the finding.
    u = (alerts_raw or {}).get("updated")
    if not u:
        return [{"key": "board:alerts-unstamped", "severity": "info",
                 "msg": "🩸 fleet-alerts carries no `updated` stamp — its age is "
                        "unknowable, so a dark producer would look identical to a "
                        "quiet fleet",
                 "proposal": "redeploy the market-context service: save_alerts "
                             "(17-Jul) stamps updated+ttl_sec per the bus "
                             "contract. Expected to clear on its next deploy — "
                             "if this persists, the stamp is not shipping.",
                 "lever": None, "ts": now_ts, "source": "board",
                 "direction": "restrict"}]
    try:
        t = datetime.fromisoformat(str(u).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        age = f"{(now_ts - t.timestamp()) / 3600:.1f}h old"
    except Exception:
        age = "unparseable `updated`"
    return [{"key": "board:alerts-feed-dark", "severity": "warn",
             "msg": f"🩸 the fleet-alerts feed is not being written ({age}) — "
                    f"an empty board is NOT evidence of a healthy fleet",
             "proposal": "check the market-context service: evaluate_evidence "
                         "runs on the coin-quality tick (MCTX_QUALITY_EVERY_H, "
                         "6h) and save_alerts stamps ttl_sec=8h. Alerts already "
                         "on the board stay valid on their own ts — this says "
                         "only that NEW ones would not appear.",
             "lever": None, "ts": now_ts, "source": "board",
             "direction": "restrict"}]


def synthesize(lighter_market, fleet_risk, lens_forward, now_ts):
    """Board-authored evidence from feed JOINS. Emission is level-triggered —
    an item re-emits every cycle its condition holds; run_once's seen-map
    dedups notifications. EVERY input is freshness-gated here (a stale feed
    contributes NOTHING) — including the lens feed, which outlives a dead
    brain in bot_state, so presence is not currency.
    Returns [{key, severity, msg, proposal, lever}]."""
    out = []

    def emit(key, severity, msg, proposal=None, lever=None):
        out.append({"key": key, "severity": severity, "msg": msg,
                    "proposal": proposal, "lever": lever, "ts": now_ts,
                    "source": "board"})

    lm_ok = _fresh(lighter_market or {})
    fr_ok = _fresh(fleet_risk or {})
    lf = ((lens_forward or {}).get("lenses") or {}) \
        if _fresh(lens_forward or {}, LENS_FRESH_S) else {}

    # the immune organ's findings, surfaced on the triage board (it already
    # phone-pushes; this puts sickness where the operator reviews everything)
    imm = store.load_state("fleet-immune") or {}
    if _fresh(imm) and (imm.get("sick") or imm.get("quarantined_levers")):
        q = imm.get("quarantined_levers") or {}
        n = len(imm.get("sick") or [])
        emit("board:immune", "warn",
             f"🛡️ immune organ flags {n} sick finding(s)"
             + (f"; quarantined {sorted(q)}" if q else ""),
             proposal="sickness = fresh-but-wrong data (bot_state 'fleet-immune'); "
                      "quarantined levers already revert to operator defaults",
             lever="immune")

    if lm_ok:
        med = ((lighter_market.get("stress") or {}).get("med")) or 0
        if med >= STRESS_VETO_BPS:
            emit("board:venue-stress", "warn",
                 f"🌡️ venue-wide |premium| med {med}bps ≥ taker veto bar {STRESS_VETO_BPS:g} — "
                 f"marks unreliable venue-wide",
                 proposal="Taker already pauses entries (built-in); WOULD extend the same "
                          "pause to family/live new entries",
                 lever="stress-veto")

    if fr_ok:
        dd = fleet_risk.get("fleet_dd_7d")
        if dd is not None and dd <= DD_NEAR_TRIP:
            emit("board:governor-near-trip", "warn",
                 f"📉 fleet 7d drawdown {dd*100:+.1f}% approaching the -5% half-clip line",
                 proposal=f"governor WOULD halve clips at -5% (clip_scale). No pre-emption — awareness",
                 lever="clip-scale")
        gross, budget = fleet_risk.get("gross"), fleet_risk.get("long_budget")
        if gross is not None and budget and gross >= budget:
            eff = ((fleet_risk.get("exposure") or {}).get("long_effective_n"))
            emit("board:budget-crowding", "info",
                 f"📦 directional book {gross}/{budget} — budget saturated"
                 + (f" (effective bets ≈ {eff:g})" if eff is not None else ""),
                 proposal="long-entry veto is already enforcing; evidence feeds agenda item 1",
                 lever="long-budget")

    for lens, g in sorted(lf.items()):
        n4h = int(g.get("n4h") or 0)
        avg4 = g.get("avg4h_pct")
        if n4h >= LENS_FLOOR_N4H:
            emit(f"board:lens-floor:{lens}", "info",
                 f"🎓 lens '{lens}' crossed the n4h≥{LENS_FLOOR_N4H} ruling floor "
                 f"(n={n4h}, hit4h {100*(g.get('hit4h') or 0):.0f}%, avg4h {avg4:+.2f}%)")
            if avg4 is not None and avg4 <= LENS_NEG_AVG4H:
                emit(f"board:lens-negative:{lens}", "warn",
                     f"🩸 lens '{lens}' NEGATIVE at the ruling floor "
                     f"(n4h={n4h}, avg4h {avg4:+.2f}%)",
                     proposal=f"restrict-only lens veto for '{lens}' via the brain's "
                              f"existing machinery (floors met — review rules)",
                     lever="lens-veto")
    return out


# ---------------------------------------------------------------------------
# GROWTH RAIL (expand direction) — the widen-when-quiet ladder for Gap Scout.
# Quiet = the census's own quiet_hours (0 while any episode is open, else
# hours since the last episode closed / the epoch started). Booking honesty
# is the scanner's own (episode dedup + floors); the board only widens the
# DETECTION net, one evidence-gated step at a time. Every lever expires in
# fleet_tuning's TTL unless re-asserted here — auto-revert is the default.
# ---------------------------------------------------------------------------

WIDEN_LADDER = [
    (24.0, {"gapscout.prefilter_gap": 0.0015, "gapscout.max_book_fetches": 45}),
    (48.0, {"gapscout.prefilter_gap": 0.0010, "gapscout.max_book_fetches": 60,
            "gapscout.extra_exchanges": "kucoin,gateio"}),
    (96.0, {"gapscout.extra_exchanges": "kucoin,gateio,mexc"}),
]
# [2026-07-16 expand side] when proprioception has graded the widened net
# HELPING (a past widening measurably coincided with census activity), the
# quiet-hour bars are discounted so the net re-widens SOONER — the ladder's
# VALUES never change, only how long the board waits to climb it. Bounded:
# fixed scale, hard floor on the effective bar.
GAPSCOUT_HELP_SCALE = float(os.environ.get("EVBOARD_GAPSCOUT_HELP_SCALE", "0.75"))
WIDEN_BAR_MIN_H = float(os.environ.get("EVBOARD_WIDEN_BAR_MIN_H", "12"))


def gapscout_bar_scale(prop_state):
    """GAPSCOUT_HELP_SCALE when any fresh proprioception verdict grades a
    gapscout.* lever HELPING, else 1.0. Fail-safe 1.0 — a dark organ earns
    nothing. Pure — selftested offline."""
    try:
        if not prop_state or not _fresh(prop_state, max_age_s=float(
                prop_state.get("ttl_sec") or 2700)):
            return 1.0
        for lever, v in (prop_state.get("verdicts") or {}).items():
            if (str(lever).startswith("gapscout.") and isinstance(v, dict)
                    and v.get("verdict") == "helping"):
                return GAPSCOUT_HELP_SCALE
    except Exception:  # noqa: BLE001
        return 1.0
    return 1.0


def widen_step(quiet_hours, bar_scale=1.0):
    """(step, merged_levers) for a census this many hours quiet. Monotone;
    later steps inherit (and may override) earlier steps' levers. bar_scale
    < 1 (proprioception HELPING) lowers the quiet-hour bars, never below
    WIDEN_BAR_MIN_H."""
    step, levers = 0, {}
    for i, (bar, lv) in enumerate(WIDEN_LADDER, 1):
        if quiet_hours >= max(WIDEN_BAR_MIN_H, bar * bar_scale):
            step = i
            levers.update(lv)
    return step, levers


# ---------------------------------------------------------------------------
# EXPAND-DIRECTION SYNTHESIS (2026-07-15 late, user: "the evidence board also
# needs to suggest things to widen and expand and not just restrict… it's so
# restrict heavy … completely one sided"). The board now authors POSITIVE
# evidence with the same machinery it uses for warnings: winner lenses at the
# ruling floor, shadow books passing the provisional promotion screen, the
# tuner's live enactments, and restrictions that never bind. Expand items
# push to the phone like warnings do (default priority, seedling tag) —
# missing the cream is as real a failure as missing a risk.
# ---------------------------------------------------------------------------

# provisional promotion screen (agenda item 5 shape: expectancy, not WR —
# the sniper's 9.8%-WR/+$192 book is the canonical WR-rule false negative)
PROMO_MIN_CLOSED = int(os.environ.get("EVBOARD_PROMO_MIN_CLOSED", "30"))
PROMO_MIN_PNL = float(os.environ.get("EVBOARD_PROMO_MIN_PNL", "10"))

# ---------------------------------------------------------------------------
# LIVE lane 💰 (15-Jul user mandate: "i want evidence and scanning for live
# bot changes also and for it to implement also — otherwise it's just a
# shadow bot tuning… rather than the live one which actually has money").
# One lever, `live.clip_scale`: a bounded multiplier on the operator's env
# clip for the lighter_live bots. It reshapes clip size; it CANNOT add
# exposure (SafetyRails' notional cap is operator-only and checked at order
# time). Sizing UP must be EARNED on the measured 7d ledger window — the
# whole cohort fresh + non-harming, at least one row proving the edge
# (lifetime volume + window sample + positive week), fleet light green,
# drawdown shallow, venue calm — one ladder step per cooldown, explicit
# release + TTL auto-revert to 1.0 the moment the board stops asserting.
# Sizing DOWN fires immediately on a hurt window (lifetime backstop at 2x,
# old lifetime rule when the ledger is dark) or a live-vs-shadow divergence
# alert. Every change that LANDS pushes URGENT to the phone.
# ---------------------------------------------------------------------------
# [2026-07-17 AUDIT] The cohort is "REAL-MONEY BOOKS THIS LEVER STEERS", and
# it must be BOTH halves of that sentence — the shipped default had it wrong on
# each half at once:
#
#   * crypto-trend-daily-lighter (Tide Rider) was RETIRED from the live slot
#     today and its bot_pnl row is now DELETED at boot (cleanup_legacy_bots.py
#     :53 — "this id can never be published again"). It can never appear in
#     bot_rows, so `cohort_ok = len(rows) >= len(LIVE_ROWS)` was 1 >= 2 =>
#     FALSE ON EVERY CYCLE, FOREVER. Measured consequence: no up-scale is ever
#     proposed, AND — worse — the DOWN reflex still fires on the visible
#     funding row, after which the blind-hold re-asserts that restriction every
#     cycle, because RELEASE requires the cohort to be readable. Real clips
#     could pin at 0.75 with no path back except the operator. A retired row
#     left in a live cohort is not inert; it is a one-way ratchet.
#   * The taker took that slot, but it is deliberately NOT added here: it
#     builds its client directly and never calls venue_context()
#     (lighter_ticket_taker.py:523), so it does NOT consume live.clip_scale —
#     it sizes off the SHADOW fleet-risk governor (:1059). Adding it would
#     grade this lever on a book the lever cannot move, which is the exact
#     defect proprioception has on live-clip today. When the taker is wired to
#     venue_context/live.clip_scale, add it HERE in the same commit.
#
# So the cohort is the ONE book that is both live and steered by this lever.
LIVE_ROWS = {s.strip() for s in os.environ.get(
    "EVBOARD_LIVE_ROWS",
    "perps-funding-lighter-lighter").split(",") if s.strip()}
LIVE_MIN_CLOSED = int(os.environ.get("EVBOARD_LIVE_MIN_CLOSED", "30"))
LIVE_DOWN_PNL = float(os.environ.get("EVBOARD_LIVE_DOWN_PNL", "10"))     # -$10/7d hurts
LIVE_DOWN_SCALE = float(os.environ.get("EVBOARD_LIVE_DOWN_SCALE", "0.75"))
LIVE_DD_MIN = float(os.environ.get("EVBOARD_LIVE_DD_MIN", "-0.02"))      # 7d fleet dd
LIVE_STEP_COOLDOWN_H = float(os.environ.get("EVBOARD_LIVE_COOLDOWN_H", "24"))
LIVE_LADDER = [1.0, 1.25, 1.5]
# [2026-07-16 BALANCE PASS — user: "ensure the expand vs tighten is balanced
# for real money"] The original gates were LIFETIME-anchored on both sides,
# which in practice made the lane one-sided: lifetime pnl never heals (the
# down reflex was a ratchet) and the earned bar required EVERY live row
# >=30 lifetime closes — unreachable, because Tide Rider is a position
# HOLDER (0 closes ever, by design; the judge excludes it for the same
# reason). Both sides now anchor on the same 7d realized-P&L ledger window:
#   TIGHTEN: 7d realized <= -LIVE_DOWN_PNL, with a 2x lifetime BACKSTOP
#            (and the old lifetime rule as the fallback when the ledger
#            window is dark — tighten never gets weaker on missing data).
#   EXPAND:  every row fresh + non-harming (lifetime bleed within
#            LIVE_SLOW_TOL) AND >=1 row PROVES it: >=LIVE_MIN_CLOSED
#            lifetime closes, >=LIVE_MIN_CLOSED_7D closes in the window,
#            positive 7d realized. Dark window = no up-scale (fail-closed).
LIVE_DOWN_HARD = float(os.environ.get("EVBOARD_LIVE_DOWN_HARD",
                                      str(2 * LIVE_DOWN_PNL)))
LIVE_SLOW_TOL = float(os.environ.get("EVBOARD_LIVE_SLOW_TOL", "1"))
LIVE_MIN_CLOSED_7D = int(os.environ.get("EVBOARD_LIVE_MIN_CLOSED_7D", "5"))
# anti-flap: after ANY release the up-ladder waits this long before
# re-asserting — a gate oscillating at its threshold must not strobe
# URGENT pushes at the operator every 10-min cycle. Down stays instant.
LIVE_REASSERT_GAP_H = float(os.environ.get("EVBOARD_LIVE_REASSERT_GAP_H", "1"))
# the live lever's own leash: 3 board cycles, not the rail's 2h default —
# a dead board reverts real-money clips in ~30min (write_levers per-entry
# ttl_sec can only shorten, never extend).
LIVE_LEVER_TTL_S = int(os.environ.get("EVBOARD_LIVE_LEVER_TTL_S",
                                      str(3 * INTERVAL)))
# A divergence alert only cuts LIVE size if it is CURRENT. The window was
# 48h, which let a 39h-old fossil from the RETIRED whole-book ratio check
# (the diagnosed "+5.4%" artifact) cut real money on 15-Jul. A genuine
# execution divergence re-fires within market_context's cadence, so the
# reflex trusts only a fresh alert — stale/retired signals age out.
LIVE_GAP_FRESH_H = float(os.environ.get("EVBOARD_LIVE_GAP_FRESH_H", "6"))
# [2026-07-16 AUDIT FIX] the up-scale gates read bot_pnl rows but never checked
# their age — a FROZEN live row with lifetime-positive pnl kept satisfying the
# "earned" gate while the bot's real state was unknown. 2h10m covers Tide
# Rider's hourly loop with the same headroom the dashboard uses.
LIVE_ROW_FRESH_S = float(os.environ.get("EVBOARD_LIVE_ROW_FRESH_S", "7800"))


def _row_fresh(r, now_ts, max_age_s=None):
    """bot_pnl row freshness by its updated_at (fail-closed on missing/bad)."""
    try:
        u = datetime.fromisoformat(str((r or {}).get("updated_at")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        return (now_ts - u.timestamp()) <= (max_age_s or LIVE_ROW_FRESH_S)
    except Exception:
        return False


def live_clip_grade(prop_state):
    """'hurting' | 'helping' | None for live.clip_scale from a FRESH
    proprioception payload. None on dark/stale/neutral — and the up-ladder
    treats None as fail-CLOSED for the TOP step (real-money default: no
    measured evidence, no top step). Pure — selftested offline."""
    try:
        if not prop_state or not _fresh(prop_state, max_age_s=float(
                prop_state.get("ttl_sec") or 2700)):
            return None
        v = (prop_state.get("verdicts") or {}).get("live.clip_scale")
        vd = v.get("verdict") if isinstance(v, dict) else None
        return vd if vd in ("hurting", "helping") else None
    except Exception:  # noqa: BLE001
        return None


def synthesize_live(bot_rows, fleet_risk, lighter_market, alerts,
                    prior_scale, now_ts, clip_grade=None, window=None,
                    released_ts=0.0):
    """The live lane's decision. Returns (desired_scale | None, item | None).
    None = assert nothing (the lever expires back to 1.0 on its own).
    prior_scale: {"value", "ts"} from the previous board payload — the
    up-ladder's cooldown memory.
    clip_grade (16-Jul evening, operator: "the live lane needs to learn"):
    proprioception's live.clip_scale verdict. HURTING (scaled episodes
    measured worse than the pre-window AND the shadow twin) releases the
    lever and blocks every up-step; the ladder's TOP step additionally
    REQUIRES a measured HELPING grade at the mid step — fail-CLOSED, so a
    dark sense caps the ladder at the mid step. Sizing down never needs
    the grade.
    window (16-Jul balance pass): {bot: {"pnl", "closes"}} — 7d realized
    P&L per live row from the paper_trades ledger. Time-local evidence for
    BOTH directions; None (ledger dark) fails the up-scale closed and
    drops the down reflex back to the conservative lifetime rule.
    released_ts: when the board last RELEASED the lever — the up-ladder
    waits LIVE_REASSERT_GAP_H after any release (anti-flap; down ignores
    it).
    Cohort visibility is ASYMMETRIC by design: the DOWN reflex fires on
    whatever rows are visible (plus the rows-free divergence alert), while
    a partially-visible cohort returns no decision for everything else —
    run_once then HOLDS an in-force restriction rather than releasing it.
    Pure — selftested offline."""
    rows = {str(r.get("bot")): r for r in (bot_rows or [])
            if str(r.get("bot")) in LIVE_ROWS}
    cohort_ok = bool(LIVE_ROWS) and len(rows) >= len(LIVE_ROWS)

    def emit(scale, sev, direction, why):
        return {"key": "board:live-clip-scale", "severity": sev,
                "msg": f"💰 LIVE clips x{scale:g} — {why}",
                "proposal": "live.clip_scale via fleet_tuning (bounds 0.5–1.5, "
                            "TTL auto-revert; SafetyRails notional cap stays "
                            "senior — reshapes clips, cannot add exposure)",
                "lever": "live.clip_scale", "ts": now_ts, "source": "board",
                "direction": direction}

    # DOWN first — restriction needs no cooldown and no permission, but the
    # divergence signal must be FRESH (a stale/retired alert is not evidence
    # of current execution divergence — that was the 15-Jul false down-scale).
    # last_seen (refreshed by market_context on every re-confirmation) keeps a
    # PERSISTING divergence current between 24h-dedup re-fires — without it
    # the reflex was blind ~18h of every 24 mid-divergence.
    gap = any(str(a.get("key", "")).startswith("live-shadow-gap")
              and max(a.get("ts") or 0, a.get("last_seen") or 0)
              >= now_ts - LIVE_GAP_FRESH_H * 3600
              for a in alerts or [])

    # hurt is TIME-LOCAL (16-Jul balance pass): a 7d realized hole in the
    # ledger window, with a 2x lifetime BACKSTOP for slow bleeds the window
    # can't see. Lifetime alone was a ratchet — a book that healed stayed
    # "hurt" forever. Two conservative carve-outs: a row with ZERO window
    # closes (a position HOLDER — the window is structurally blind to it)
    # keeps the FULL lifetime bar on its mark-anchored pnl, and a dark
    # window drops every row back to the old lifetime rule. The DOWN reflex
    # runs on whatever rows ARE visible — a vanished bot_pnl row must never
    # disarm the tighten side (it only blocks the expand side, below).
    def _hurt_why(b, r):
        life = float(r.get("pnl_abs") or 0)
        w = (window or {}).get(b) if window else None
        if w is not None:
            wp = float(w.get("pnl") or 0)
            if wp <= -LIVE_DOWN_PNL:
                return f"{b} 7d ${wp:+.2f}"
            if int(w.get("closes") or 0) == 0:
                return (f"{b} ${life:+.2f} (mark)"
                        if life <= -LIVE_DOWN_PNL else None)
            if life <= -LIVE_DOWN_HARD:
                return f"{b} lifetime ${life:+.2f} (backstop)"
            return None
        return f"{b} ${life:+.2f}" if life <= -LIVE_DOWN_PNL else None

    hurt = [w for b, r in sorted(rows.items()) for w in [_hurt_why(b, r)] if w]
    if gap or hurt:
        why = " ; ".join((["live-vs-shadow divergence alert"] if gap else [])
                         + hurt
                         + ([] if cohort_ok else ["cohort partially visible"]))
        return LIVE_DOWN_SCALE, emit(LIVE_DOWN_SCALE, "action", "restrict", why)

    if not cohort_ok:
        return None, None      # blind: no decision (run_once HOLDS a restriction)

    # 🦾 the live lane's own learning: a HURTING clip grade (scaled episodes
    # measured worse than the pre-window AND the shadow twin) stops the
    # board asserting ANY scale — the lever expires back to the operator's
    # env sizing. Not a punishment down-scale: the measured-bad movement
    # simply stops being repeated until the grade recovers.
    if clip_grade == "hurting":
        if (prior_scale or {}).get("value"):
            return None, {
                "key": "board:live-clip-scale", "severity": "action",
                "msg": "💰 LIVE clip lever RELEASED — 🦾 proprioception graded "
                       "scaled episodes HURTING (worse than pre-window AND "
                       "shadow twin); reverting to operator env sizing",
                "proposal": "no re-assert while the verdict holds; the judge "
                            "and the operator remain the only expand paths "
                            "for live",
                "lever": "live.clip_scale", "ts": now_ts, "source": "board",
                "direction": "restrict"}
        return None, None

    # a fresh RELEASE parks the up-ladder briefly (anti-flap): a gate
    # oscillating at its threshold must not strobe URGENT pushes.
    if released_ts and now_ts - float(released_ts) < LIVE_REASSERT_GAP_H * 3600:
        return None, None

    # UP must be earned on every gate at once.
    fr_ok = (_fresh(fleet_risk or {})
             and str(fleet_risk.get("light")) == "green"
             # [2026-07-15 AUDIT FIX] fail CLOSED for a real-money UP-scale: a
             # MISSING drawdown field must NOT bypass the shallow-DD guard
             # (was `is None or > MIN`, which up-scaled on absent dd).
             and fleet_risk.get("fleet_dd_7d") is not None
             and float(fleet_risk.get("fleet_dd_7d")) > LIVE_DD_MIN)
    med = ((lighter_market or {}).get("stress") or {}).get("med")
    lm_ok = (_fresh(lighter_market or {}) and med is not None
             and med * 2 <= STRESS_VETO_BPS)
    # EARNED, time-local + cohort-aware (16-Jul balance pass). The old bar
    # (EVERY row >=30 LIFETIME closes AND lifetime-positive) was unreachable:
    # Tide Rider holds positions (0 closes ever, by design) and a lifetime
    # anchor never heals — expand existed only on paper. The clip lever is
    # SHARED across the live cohort, so the bar splits by role: every row
    # must be FRESH and NON-HARMING (lifetime bleed inside LIVE_SLOW_TOL —
    # a frozen row's history is not evidence of current health), and at
    # least one row must PROVE the edge on the measured week: >=
    # LIVE_MIN_CLOSED lifetime closes AND >= LIVE_MIN_CLOSED_7D window
    # closes AND positive 7d realized. No ledger window -> no up (CLOSED).
    if window is None:
        return None, None
    nonharm = all(_row_fresh(r, now_ts)
                  and float(r.get("pnl_abs") or 0) >= -LIVE_SLOW_TOL
                  for r in rows.values())

    def _proves(b, r):
        w = window.get(b) or {}
        return (int(r.get("closed_trades") or 0) >= LIVE_MIN_CLOSED
                and int(w.get("closes") or 0) >= LIVE_MIN_CLOSED_7D
                and float(w.get("pnl") or 0) > 0)

    provers = [b for b, r in sorted(rows.items()) if _proves(b, r)]
    if not (fr_ok and lm_ok and nonharm and provers):
        return None, None                    # lever expires -> 1.0

    cur = float((prior_scale or {}).get("value") or 1.0)
    since = float((prior_scale or {}).get("ts") or 0)
    nxt = next((v for v in LIVE_LADDER if v > cur + 1e-9), cur)
    if cur > 1.0 and now_ts - since < LIVE_STEP_COOLDOWN_H * 3600:
        nxt = cur                            # hold this step through cooldown
    # the TOP step must be MEASURED, not just gated: it requires a fresh
    # HELPING grade at the current step (fail-CLOSED — no grade, no top)
    if nxt == LIVE_LADDER[-1] and nxt > cur and clip_grade != "helping":
        nxt = cur
    if nxt <= 1.0:
        return None, None
    why = (f"EARNED: {'+'.join(provers)} ≥{LIVE_MIN_CLOSED} closes & 7d-positive"
           f" (≥{LIVE_MIN_CLOSED_7D} window closes), cohort fresh & non-harming"
           f" (≥-${LIVE_SLOW_TOL:g}), fleet green, dd>{LIVE_DD_MIN:.0%}, "
           f"venue calm ({med}bps)"
           + (" · 🦾 measured HELPING at the prior step"
              if nxt == LIVE_LADDER[-1] and clip_grade == "helping" else ""))
    return nxt, emit(nxt, "action", "expand", why)


def synthesize_expand(lens_fwd, tuner_state, bot_rows, lighter_market, now_ts,
                      xp_state=None, radar_state=None):
    """Board-authored EXPAND evidence. Same emit shape as synthesize(), every
    item carrying direction='expand'. Pure — selftested offline.

    [2026-07-28] radar_state: the fleet-radar payload. The promotion watch
    below is a NAIVE expectancy screen (lifetime n + $ total) — exactly the
    read the radar's median/jackknife/concentration sensors were built to
    correct, and the 28-Jul review measured the collision live (Yield
    Harvester +$58.62 headline, radar `artifact`: three single closes are
    $32.69 of it; "the radar is senior here by construction"). A fresh radar
    class now rides every promotion-watch item: artifact/noise/losing/weak
    DOWNGRADES the item (headline kept honest, promotion proposal replaced
    by the radar's caveat), real_edge/plausible corroborates. Fail-open: a
    dark/stale radar leaves the naive screen exactly as it was."""
    out = []
    radar_by_bot = {}
    # [2026-07-29 AUDIT] plain numeric ceiling — _fresh already min()s in the
    # payload's own guarded ttl_sec. The old inline float(ttl_sec) was the one
    # UNGUARDED parse on this path: a sick radar payload carrying a
    # non-numeric ttl_sec raised before _fresh ran, and because run_once
    # calls synthesize_expand unwrapped, ONE bad organ payload aborted the
    # whole board cycle (including the live.clip_scale re-assert loop),
    # silently, every cycle until the radar healed.
    if radar_state and _fresh(radar_state, max_age_s=10800):
        for b in radar_state.get("books") or []:
            if isinstance(b, dict) and b.get("bot"):
                radar_by_bot[str(b["bot"])] = b

    def emit(key, msg, proposal=None, lever=None):
        out.append({"key": key, "severity": "info", "msg": msg,
                    "proposal": proposal, "lever": lever, "ts": now_ts,
                    "source": "board", "direction": "expand"})

    # 1) WINNER lenses: brain-graded positive at its own ruling floor — the
    #    exact inverse of the lens-veto rule the board already watches.
    for lens, g in sorted((lens_fwd or {}).items()):
        if ((g.get("n4h") or 0) >= LENS_FLOOR_N4H
                and (g.get("avg4h_pct") or 0) > 0
                and (g.get("hit4h") or 0) >= 0.5):
            emit(f"board:lens-positive:{lens}",
                 f"🏆 lens '{lens}' POSITIVE at the ruling floor "
                 f"(n4h={g.get('n4h')}, hit {100*(g.get('hit4h') or 0):.0f}%, "
                 f"avg4h {g.get('avg4h_pct'):+.2f}%)",
                 proposal="scout tuner auto-expands its bar (replay-gated, "
                          "both-halves); review: consider promotion / wider diet",
                 lever="growth-rail")

    # 2) The tuner's live enactments, surfaced where the operator triages.
    if tuner_state and _fresh(tuner_state, max_age_s=float(
            tuner_state.get("ttl_sec") or 10800)):
        enacted = tuner_state.get("enacted") or {}
        if enacted:
            emit("board:tuner-enacted",
                 "🌱 scout tuner self-tuned the Lighter loop: "
                 + ", ".join(f"{k}={v}" for k, v in sorted(enacted.items())),
                 proposal="replay-gated levers, TTL'd (auto-revert unless "
                          "re-asserted hourly); history under 'fleet-tuning'",
                 lever="growth-rail")

    # 3) Promotion watch: shadow books passing the provisional expectancy
    #    screen — the pipeline's whole purpose is finding these.
    for r in sorted(bot_rows or [], key=lambda r: str(r.get("bot"))):
        bot = str(r.get("bot") or "")
        extra = r.get("extra") or {}
        is_shadow = bot.endswith("-lshadow") or extra.get("venue") == "lighter_shadow"
        if not is_shadow:
            continue
        closed = int(r.get("closed_trades") or 0)
        pnl = float(r.get("pnl_abs") or 0.0)
        if closed >= PROMO_MIN_CLOSED and pnl >= PROMO_MIN_PNL:
            rb = radar_by_bot.get(bot)
            rcls = (rb or {}).get("class")
            rcav = ", ".join((rb or {}).get("caveats") or [])
            if rcls in ("artifact", "noise", "losing", "weak"):
                # the radar is SENIOR to this naive screen — keep the item
                # (the headline exists and the operator will see it anyway)
                # but let it tell the truth about itself.
                emit(f"board:promotion-watch:{bot}",
                     f"🔬 {bot}: n={closed} closed, ${pnl:+.2f} passes the "
                     f"naive expectancy screen BUT radar classes it "
                     f"'{rcls}'" + (f" ({rcav})" if rcav else ""),
                     proposal="do NOT promote on the headline — the radar's "
                              "median/jackknife read is senior (28-Jul "
                              "review); revisit if its class improves",
                     lever="promotion")
            else:
                emit(f"board:promotion-watch:{bot}",
                     f"🚀 {bot}: n={closed} closed, ${pnl:+.2f} — passes the "
                     f"provisional expectancy screen (n≥{PROMO_MIN_CLOSED}, "
                     f"≥${PROMO_MIN_PNL:g})"
                     + (f" · radar: {rcls}" + (f" ({rcav})" if rcav else "")
                        if rcls else ""),
                     proposal="promotion-review candidate — run the agenda item-5 "
                              "gate (expectancy + max-DD + profit factor) at the "
                              "review; go-live stays operator-only",
                     lever="promotion")

    # 3b) The experiment judge's phase — the shadow→live promotion pipeline
    #     visible where the operator triages.
    if xp_state and _fresh(xp_state, max_age_s=float(xp_state.get("ttl_sec") or 10800)):
        ph, cand = xp_state.get("phase"), xp_state.get("candidate")
        if ph in ("running", "promoted") and cand:
            emit(f"board:xp-{ph}:{cand}",
                 (f"🧪 experiment '{cand}' RUNNING on the Funding Farmer "
                  f"shadow arm" if ph == "running" else
                  f"🧪 promotion '{cand}' IN FORCE on the LIVE Funding Farmer"),
                 proposal="paired bar: ≥7d, ≥30 shadow closes, beats live "
                          "per-trade on window AND both halves; fade-watch "
                          "releases a turning promotion (state: 'xp-judge')",
                 lever="xp-judge")

    # 4) Restrictions that never bind: the balance check on the board's own
    #    restrict side. A veto with permanent headroom is a calibration item.
    if _fresh(lighter_market or {}):
        med = ((lighter_market.get("stress") or {}).get("med"))
        if med is not None and med * 2 <= STRESS_VETO_BPS:
            emit("board:stress-headroom",
                 f"🔓 venue stress med {med}bps vs taker veto bar "
                 f"{STRESS_VETO_BPS:g}bps — this restriction has never bound",
                 proposal="calibration item for the review: a veto that can't "
                          "fire protects nothing (agenda item 2 already tracks it)",
                 lever="stress-veto")
    return out


# [2026-07-30 THE BOOKS GET AN AUTHOR — operator: "grow into what works"]
# The `lighter-books` lane was bound to this board as AUTHOR and NOTHING in
# this file wrote it: `board_levers` was populated only from the (inert since
# 17-Jul) gapscout ladder and live.clip_scale. A lane authored by nobody is
# the exact mirror of the registered-but-not-consumed class — the levers were
# registered, consumed by their bots, graded by proprioception, and could
# never MOVE. This is the missing author.
#
# The rule is deliberately narrow, because a widening author that fires on
# noise is worse than none:
#   SATURATED  — the book is holding at its cap, so it is turning away
#                candidates it already graded, AND it is in profit on a
#                mark-to-market basis. Widen ONE step.
#   STARVED    — the book holds nothing and has closed nothing in the window,
#                so its gate is admitting nothing. Loosen ONE step.
#   otherwise  — propose nothing. A book that is working is left alone.
#
# [2026-07-31 (hs)] THE PROFIT TERM ON THE SATURATED BRANCH IS NEW, and the
# comment above ("a book that is working is left alone") described an
# intention the code did not implement: the SATURATED branch asked only
# `open_n >= cap` and never once asked whether the book was making money.
#
# MEASURED, on ⚖️ Counterweight, the day this was found:
#   * `fundspread.k` had been ratcheted 5 -> 8 -> 12 and was sitting AT its
#     registry ceiling (`hi: 12`), every step authored by this branch with
#     reason "SATURATED at 24/11".
#   * Gross exposure went $200 (the backtested plateau centre, K=5) -> $480.
#   * The book was at -$27.75: +$7.29 realised over 48 closes against a
#     -$35.04 OPEN loss carried on 24 legs. Its funding income — the entire
#     thesis — was $2.11.
# So the rail scaled a losing book by 2.4x, and cited the book's own fullness
# as the evidence for doing it.
#
# WHY IT COULD NEVER SELF-CORRECT: Counterweight is ALWAYS-IN by construction
# (its own header: "ALWAYS-IN, balanced long/short"), holding exactly 2K legs
# at all times. So `open_n >= cap` is true on EVERY cycle, unconditionally,
# and the ratchet fires until the cage stops it. For a book of that shape
# saturation carries no information at all — it is a restatement of the
# book's design, not an observation about its performance. Contrast 🌾 carry,
# measured the same hour at 8 of 12: its cap is not structurally pinned, so
# its ratchet stopped on its own and the defect stayed invisible there.
#
# THE TERM IS DELIBERATELY ASYMMETRIC — capacity only, never the gate:
#   * CAPACITY widening scales the exposure of positions the book ALREADY
#     holds. Requiring those positions to be working before adding more is
#     the whole point.
#   * The STARVED branch loosens a GATE on a book holding NOTHING, whose
#     P&L is ~0 by definition. Applying a `pnl > 0` term there would freeze
#     every starved book permanently and defeat the branch that exists to
#     unstick a gate admitting nothing.
#
# It reads `pnl_abs` — the published MARK-TO-MARKET total, not realised P&L.
# That is the load-bearing choice: on this book realised reads +$7.29 and
# would have authorised the widening, which is exactly the (hl) realised-only
# blind spot reaching a live actuator instead of only the go-live grader.
# RESTRICT-ONLY by construction: this branch can now only decline to widen,
# never widen something it would previously have left alone.
BOOK_AUTHOR = {
    # bot row -> (capacity lever, gate lever, cap source)
    "perps-funding-carry-lshadow":  ("carry.max_positions", "carry.enter_apr"),
    "perps-funding-spread-lshadow": ("fundspread.k", "fundspread.universe_n"),
    "lighter-dislocation-lshadow":  (None, "disloc.enter_pct"),
    "equities-regime-lshadow":      ("index.max_open", None),
    "lighter-perp-sniper-lshadow":  (None, "sniper.surge_mult"),
    # [2026-07-30 (hk)] Tide Rider was ABSENT from this map entirely, so its
    # one lever could never be authored — registered, consumed, and
    # unreachable, which is the (gb) class one level subtler. Its GATE is the
    # universe: this book has no entry threshold to loosen, so "starved" means
    # "it cannot see enough books to find a golden one". Measured: max
    # simultaneously-golden coins over 192 aligned days = 1, against 6 slots,
    # so the cap is not what binds — the candidate set is.
    "crypto-trend-daily-lshadow":   ("trend.max_open", "trend.universe_n"),
}
BOOK_STARVED_H = float(os.environ.get("EVBOARD_BOOK_STARVED_H", "24"))
# [2026-08-01 (hw)] ...and the same 24h meant OPPOSITE THINGS on different
# books. ⚖️ Counterweight closes ~2.8x/day, so a silent day is genuinely
# unusual; 🎯 the Perp Sniper has produced 6 closes in WEEKS, so a silent day
# is its normal Tuesday. One constant cannot serve both: on the fast book it is
# too slow to notice, and on the slow book it declares STARVED on essentially
# every cycle — which is a ratchet, not a signal.
# The clock is now derived from the BOOK'S OWN measured pace: STARVED_MULT x
# its mean gap between closes, floored and capped so the answer stays bounded
# and a book with no history still has a defined one.
STARVED_MULT = float(os.environ.get("EVBOARD_STARVED_MULT", "3.0"))
STARVED_MIN_H = float(os.environ.get("EVBOARD_STARVED_MIN_H", "12"))
STARVED_MAX_H = float(os.environ.get("EVBOARD_STARVED_MAX_H", "336"))   # 14d


def book_starved_h(closed_n, age_days, default_h=None):
    """How long THIS book must be quiet before "starved" means anything.

    `closed_n` closes over `age_days` of life -> mean gap between closes; the
    bar is STARVED_MULT x that gap, clamped to [STARVED_MIN_H, STARVED_MAX_H].

    THE TWO FALLBACKS DIFFER, and the difference is the point:
      * NEVER CLOSED (n<2): the CAP. Under the old flat 24h such a book was
        permanently STARVED, so the author widened it every single cycle until
        it hit its cage bound — growth by impatience rather than by evidence.
        A book that has not yet shown it can trade gets two weeks of patience.
      * HAS CLOSED but pace not yet measurable (no span in the board's memory):
        the FLAT default, i.e. exactly today's behaviour. A new metric that is
        not available yet must degrade to the known-acceptable one, never to
        "never fire" — my first cut returned the cap here and would have
        silently switched the starvation branch off fleet-wide, trading one
        broken direction for the other.
    """
    base = default_h if default_h is not None else BOOK_STARVED_H
    try:
        n = int(closed_n or 0)
        d = float(age_days or 0.0)
        if n < 2:
            return STARVED_MAX_H          # never traded -> be patient
        if d <= 0:
            return base                   # pace unknown -> today's behaviour
        gap_h = (d * 24.0) / n
        return max(STARVED_MIN_H, min(STARVED_MAX_H, STARVED_MULT * gap_h))
    except Exception:  # noqa: BLE001 — a bad row must not break the board
        return base


def book_mtm_pnl(row):
    """[2026-07-31 (hs)] The book's MARK-TO-MARKET P&L, or None if unreadable.

    `pnl_abs` is the published total (equity - start), so it carries OPEN
    positions. Verified on the two books this rule authors, the hour it was
    written: ⚖️ Counterweight published pnl_abs -27.75 against +7.29 realised
    (24 open legs), 🌾 carry published +65.62 against +65.91 realised (8 open).
    Realised-only would have read the first book as +$7 and widened it.

    Returns None rather than 0.0 on a missing/unparseable field, and the
    caller treats None as "do not widen" — FAIL-CLOSED IN THE WIDENING
    DIRECTION. Absence of evidence must never authorise more exposure; a book
    that genuinely sits at exactly 0.0 is also not evidence of a working book.
    """
    if not isinstance(row, dict):
        return None
    val = row.get("pnl_abs")
    if val is None or isinstance(val, bool):
        return None
    try:
        val = float(val)
    except (TypeError, ValueError):
        return None
    return None if val != val else val        # NaN is not evidence either


def synthesize_books(bot_rows, prior_books, prop_state, now_ts, tuning_mod=None):
    """Board-authored BOOK levers. Returns (levers, items).

    Pure apart from the injected `tuning_mod` (the registry + current values),
    so it selftests offline. Guards, each of which exists for a reason:

      * NEVER re-assert a lever proprioception currently grades HURTING —
        the growth rail's own restrict-first contract. A book that got worse
        under a widening does not get widened again on the next quiet cycle.
      * ONE step per book per cycle, clamped by the registry. The rail moves
        at the speed evidence accumulates, not at the speed of a loop.
      * SATURATION needs the book to be AT its cap, not near it.
      * STARVATION needs BOTH no open positions AND no closes in the window —
        a book that is holding is not starved, it is patient.
      * A book missing from `bot_rows` (dead row, stale publish) proposes
        NOTHING. Absence of evidence must never read as "widen".
    """
    levers, items = {}, []
    if tuning_mod is None:
        return levers, items
    # THE PAYLOAD SHAPE IS `verdicts: {lever: {"verdict": ...}}` — the same
    # read synthesize_proprioception above already does. An earlier cut of
    # this line read a `hurting_levers` key that DOES NOT EXIST, so the set
    # was always empty and the single most important guard here — never
    # re-widen a lever that measured worse — was silently dead. Its selftest
    # passed because the fixture invented the same wrong key. Assert against
    # the real shape, never against a shape you made up.
    hurting = {str(k) for k, v in ((prop_state or {}).get("verdicts") or {}).items()
               if isinstance(v, dict) and v.get("verdict") == "hurting"}
    rows = {str(r.get("bot")): r for r in (bot_rows or []) if r.get("bot")}

    for bot, (cap_lever, gate_lever) in sorted(BOOK_AUTHOR.items()):
        r = rows.get(bot)
        if not r:
            continue                       # no row -> no opinion, ever
        try:
            open_n = int(r.get("open_trades") or 0)
            closed_n = int(r.get("closed_trades") or 0)
        except (TypeError, ValueError):
            continue
        prev = (prior_books or {}).get(bot) or {}
        prev_closed = int(prev.get("closed") or 0)
        prev_ts = float(prev.get("ts") or 0.0)

        def _step(lever, why):
            spec = (tuning_mod.LEVERS or {}).get(lever) or {}
            if not spec or lever in hurting:
                return False
            cur = tuning_mod.get_lever(lever, spec.get("env_default"),
                                       now_ts=now_ts)
            step = spec.get("step") or 0
            if cur is None or not step:
                return False
            want = tuning_mod.clamp(lever, cur + step)
            # round the float ladder: 1.6 - 0.2 is 1.4000000000000001, and an
            # unrounded value both reads badly in the payload and drifts as
            # steps accumulate — the `want == cur` no-op check below depends
            # on a step landing exactly where the previous one left off.
            if isinstance(want, float):
                want = round(want, 6)
            if want is None or want == cur:
                return False               # already at the bound: nothing to say
            levers[lever] = {"value": want, "reason": why,
                             "evidence": f"{bot}: open={open_n} closed={closed_n}"}
            items.append({
                "key": f"board:book-{lever}", "severity": "info",
                "msg": f"🌱 {bot} {why} — {lever} {cur} → {want}",
                "proposal": f"widen (ENACTED via fleet_tuning): {lever}={want}",
                "lever": lever, "direction": "expand",
                "ts": now_ts, "source": "board"})
            return True

        # [2026-07-30] Prefer the cap the BOOK PUBLISHED (`extra.caps`) over
        # the cap the registry thinks it enacted. They can legitimately differ
        # — a bot that has not redeployed, a quarantined lever, a TTL that
        # lapsed between the write and this read — and the book's own number
        # is the one that actually gated its trades. Reading the registry
        # alone risks the author judging saturation against a cap it set
        # itself and the bot never adopted.
        cap = None
        if cap_lever:
            _caps = (r.get("extra") or {}).get("caps") or {}
            _key = cap_lever.split(".", 1)[1]
            try:
                cap = float(_caps[_key]) if _key in _caps else None
            except (TypeError, ValueError):
                cap = None
            if cap is None:
                _spec = (tuning_mod.LEVERS or {}).get(cap_lever) or {}
                cap = tuning_mod.get_lever(cap_lever, _spec.get("env_default"),
                                           now_ts=now_ts)
        if cap_lever and cap and open_n >= int(cap):
            # [2026-07-31 (hs)] SATURATION IS NOT EVIDENCE THE BOOK IS WORKING.
            # See the BOOK_AUTHOR header for the measurement that forced this.
            # Fail-CLOSED: an unreadable pnl_abs declines the widening.
            book_pnl = book_mtm_pnl(r)
            if book_pnl is None or book_pnl <= 0:
                _shown = "unreadable" if book_pnl is None else f"${book_pnl:.2f}"
                items.append({
                    "key": f"board:book-{cap_lever}-held",
                    "severity": "info",     # NOT warn: the board phone-pushes
                                            # warn/action, and an always-in
                                            # book trips this EVERY cycle.
                    "msg": (f"⚖️ {bot} saturated at {open_n}/{int(cap)} but "
                            f"MTM P&L is {_shown} — {cap_lever} held at {cap:g}"),
                    "proposal": (f"no widening: capacity growth requires the "
                                 f"book to be in profit mark-to-market"),
                    "lever": cap_lever, "direction": "hold",
                    "ts": now_ts, "source": "board"})
            else:
                _step(cap_lever,
                      f"SATURATED at {open_n}/{int(cap)}, MTM +${book_pnl:.2f}")
        else:
            # [(hw)] the clock is THIS book's, derived from its own pace —
            # see book_starved_h. `age_days` comes off the row when the
            # publisher offers it; absent, the book reads as pace-unknown and
            # gets the patient end of the range rather than the impatient one.
            # Pace comes from the board's OWN memory span (first_ts/first_closed,
            # persisted below) — no book publishes an age, and inventing a row
            # field the publishers do not emit is how a consumer goes dark.
            # Falls back to the row's own hint, then to the flat default.
            _age_d = None
            _f_ts, _f_cl = prev.get("first_ts"), prev.get("first_closed")
            if _f_ts and _f_cl is not None and closed_n > _f_cl:
                _span_d = (now_ts - float(_f_ts)) / 86400.0
                if _span_d > 0:
                    _age_d = _span_d * closed_n / max(1, closed_n - int(_f_cl))
            if _age_d is None:
                for _k in ("age_days", "days", "age_d"):
                    if (r.get("extra") or {}).get(_k) is not None:
                        _age_d = (r.get("extra") or {}).get(_k)
                        break
            _bar_h = book_starved_h(closed_n, _age_d)
            if (gate_lever and open_n == 0 and closed_n == prev_closed
                    and prev_ts and (now_ts - prev_ts) >= _bar_h * 3600):
                _step(gate_lever,
                      f"STARVED {_bar_h:.0f}h — this book's own bar "
                      f"({closed_n} closes; the fleet-flat 24h would have "
                      f"fired at 24h)")
    return levers, items


def synthesize_proprioception(prop_state, now_ts):
    """[2026-07-16] 🦾 proprioception verdicts on the triage board. HURTING
    (a lever whose graded real-world episodes measured net-negative — the
    tuner already auto-skips it) surfaces as a warn/restrict item; HELPING
    surfaces as expand evidence for the review. Stale/absent organ emits
    nothing (fail-safe). Pure — selftested offline."""
    out = []
    if not prop_state or not _fresh(prop_state, max_age_s=float(
            prop_state.get("ttl_sec") or 2700)):
        return out
    for lever, v in sorted((prop_state.get("verdicts") or {}).items()):
        if not isinstance(v, dict):
            continue
        n = v.get("n")
        measure = (f"Σ${v['sum_delta_usd']:+.2f}" if v.get("sum_delta_usd")
                   is not None else
                   f"Σ{v.get('sum_delta_grades', 0):+d} grades"
                   if v.get("sum_delta_grades") is not None else "activity")
        if v.get("verdict") == "hurting":
            out.append({"key": f"board:prop-hurting:{lever}", "severity": "warn",
                        "msg": f"🦾 lever {lever} graded HURTING in reality: "
                               f"{measure} over n={n} episodes (out-of-sample "
                               f"replay counterfactual)",
                        "proposal": "scout tuner auto-skips re-assertion while "
                                    "the verdict holds (restrict-only); review "
                                    "whether the ladder/bounds need tightening",
                        "lever": "proprioception", "ts": now_ts, "source": "board"})
        elif v.get("verdict") == "helping":
            out.append({"key": f"board:prop-helping:{lever}", "severity": "info",
                        "msg": f"🦾 lever {lever} graded HELPING in reality: "
                               f"{measure} over n={n} episodes",
                        "proposal": "outcome evidence for the review — the "
                                    "widening is paying on the tape recorded "
                                    "while it was in force",
                        "lever": "proprioception", "ts": now_ts,
                        "source": "board", "direction": "expand"})
    return out


def synthesize_parliament(parl_state, tuning_state, now_ts):
    """[2026-07-21] 🏛️ the Parliament on the triage board (operator-sanctioned
    consumer — "proceed with your invention"). Restrict-first, three item
    classes, all level-triggered off Howard's published vitals:
      * STALLED chamber organs -> warn (the board's corroboration + phone
        machinery on top of the watchdog's staleness eye)
      * a book's drawdown approaching/beyond the GO-LIVE GATE bar (maxDD<15%
        is the promotion gate; a shadow book bleeding toward it is the
        earliest restrict evidence this fleet recognises) -> warn at -10%,
        action at -15%
      * the ML bench earning a MEASURED out-of-sample edge -> info, expand
        direction (review evidence only; the gate stays reduce-only)
    Stale/absent organ emits NOTHING (fail-safe — a dark chamber is the
    watchdog's finding, not this one's). Pure — selftested offline."""
    out = []
    if not parl_state or not _fresh(parl_state, max_age_s=float(
            parl_state.get("ttl_sec") or 900)):
        return out
    stalled = (parl_state.get("health") or {}).get("stalled") or []
    if stalled:
        out.append({"key": "board:parliament-stalled", "severity": "warn",
                    "msg": f"🏛️ Parliament organ(s) STALLED: {', '.join(stalled)} "
                           f"— alive-but-quiet inside a fresh chamber payload",
                    "proposal": "check the freqtrade-bots container logs; "
                                "PARLIAMENT_ENABLED=0 idles the chamber if it "
                                "is sick (restrict-only kill switch)",
                    "lever": "parliament", "ts": now_ts, "source": "board"})
    # [2026-07-21 AUDIT FIX — label honesty] this measures P&L-FROM-START,
    # not max drawdown (Howard's book_summary carries no peak). Since peak
    # >= start, P&L-from-start is a LOWER BOUND on maxDD: a book −15% from
    # start has maxDD >= 15%, so the ACTION band fires conservatively-
    # correctly — but the item must SAY what it measured, or the operator
    # reads a maxDD number that isn't one (a book that rallied +30% then
    # gave it back sits at 0% here with a 23% true maxDD).
    for bot, b in sorted((parl_state.get("books") or {}).items()):
        try:
            pnl_pct = float(b.get("pnl", 0.0)) / 1000.0
        except (TypeError, ValueError):
            continue
        if pnl_pct <= -0.15:
            sev, band = "action", ("P&L-from-start beyond −15% — a LOWER "
                                   "BOUND on maxDD, so the 15% go-live gate "
                                   "bar is breached")
        elif pnl_pct <= -0.10:
            sev, band = "warn", ("P&L-from-start past −10% — maxDD is at "
                                 "least this; the 15% go-live gate bar nears")
        else:
            continue
        out.append({"key": f"board:parliament-drawdown:{bot}",
                    "severity": sev,
                    "msg": f"🏛️ {bot} down {pnl_pct:.1%} from its $1k start — "
                           f"{band} (closed {b.get('closed')}, "
                           f"open {b.get('open')})",
                    "proposal": "restrict-only options: let the daily-loss "
                                "halt + tuner grading work, or idle the "
                                "chamber; a book at the gate bar cannot "
                                "promote and argues for lens review",
                    "lever": "parliament", "ts": now_ts, "source": "board"})
    ml = parl_state.get("ml") or {}
    accs = ml.get("oos_acc") or {}
    if ml.get("ready") and accs and max(accs.values()) >= 0.55:
        best = max(accs, key=accs.get)
        out.append({"key": "board:parliament-ml-edge", "severity": "info",
                    "msg": f"🏛️ Keating's ML bench has a MEASURED edge: "
                           f"{best} at {accs[best]:.1%} prequential OOS "
                           f"accuracy (n={ml.get('n_seen')}) — ensemble gate "
                           f"active, reduce-only",
                    "proposal": "review evidence — the gate can only "
                                "skip/shrink; any authority expansion is a "
                                "review decision",
                    "lever": "parliament", "ts": now_ts, "source": "board",
                    "direction": "expand"})
    n_levers = 0
    if tuning_state and _fresh(tuning_state, max_age_s=float(
            tuning_state.get("ttl_sec") or 900)):
        n_levers = sum(len(v) for v in (tuning_state.get("active") or
                                        {}).values() if isinstance(v, list))
    if n_levers >= 4:
        out.append({"key": "board:parliament-tuner-breadth", "severity": "info",
                    "msg": f"🏛️ {n_levers} Parliament tuner levers active at "
                           f"once (one-per-book cap is 6) — unusually broad "
                           f"self-tuning; all TTL'd, all inside PARAM_BOUNDS",
                    "proposal": "watch item only — expiry auto-reverts every "
                                "lever; episode grading will verdict them",
                    "lever": "parliament", "ts": now_ts, "source": "board"})
    return out


def detect_veto_flap(alerts_48h_plus, now_ts, window_d=7, min_events=3):
    """A coin appearing in >= min_events veto-change alerts inside window_d
    days is oscillating across its threshold. Restrict-only so harmless, but
    it argues for remove-side hysteresis — surfaced as board evidence."""
    from collections import defaultdict
    per_coin = defaultdict(int)
    cut = now_ts - window_d * 86400
    for a in alerts_48h_plus:
        if not str(a.get("key", "")).startswith("veto:"):
            continue
        if (a.get("ts") or 0) < cut:
            continue
        for c in str(a["key"])[len("veto:"):].split(","):
            if c.strip():
                per_coin[c.strip()] += 1
    out = []
    for coin, n in sorted(per_coin.items()):
        if n >= min_events:
            out.append({"key": f"board:veto-flap:{coin}", "severity": "warn",
                        "msg": f"🔁 coin veto FLAP: {coin} changed state {n}x in {window_d}d "
                               f"— hovers at the veto threshold",
                        "proposal": "remove-side hysteresis on the coin veto "
                                    "(pure tightening; needs the backtest-first pass)",
                        "lever": "coin-veto", "ts": now_ts, "source": "board"})
    return out


# ---------------------------------------------------------------------------
# notify (same channel as the fleet watchdog)
# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="urgent", tags="scales"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", tags)
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[evidence_board] push failed: {type(e).__name__}: {e}", flush=True)
        return False


# ---------------------------------------------------------------------------
# one cycle
# ---------------------------------------------------------------------------

def run_once():
    now = _now()
    prior = store.load_state(BOARD_KEY) or {}
    prior_items = {i["key"]: i for i in prior.get("items", [])}
    notified = dict(prior.get("notified") or {})
    # [2026-07-16] full first-seen memory. prior_items only holds the top-20
    # DISPLAYED items, so anything ranked 21+ lost its first_seen and could
    # re-notify as "new" after the gap. Migrate from prior items on first run.
    seen_prior = dict(prior.get("seen") or {}) or \
        {k: (v.get("first_seen") or "") for k, v in prior_items.items()}

    # [2026-07-15 BLOODSTREAM] one batched beat for the board's whole working
    # set (was ~8 individual round-trips per cycle). Fall back to per-key reads
    # only if the batch came back empty (DB down).
    # [2026-07-30] fleet-radar / parliament / parliament-tuning were READ via
    # _g() but never FETCHED here. `_g` returns `_b.get(k) or {}` whenever the
    # batch read succeeded, so on every HEALTHY cycle those three came back
    # empty — the radar's per-book edge classification (the senior corrective
    # on the naive promotion screen) and the whole Parliament section were
    # silently inert, and only worked when fetch_states FAILED and _g fell
    # through to per-key load_state. Exactly the shape of a dark consumer.
    _keys = ["fleet-alerts", "evidence-review", "lighter-market", "fleet-risk",
             "brain-lens-forward", "scout-tuner", "xp-judge", "gapscout-census",
             "impl-shortfall", "fleet-proprioception",
             "fleet-radar", "parliament", "parliament-tuning"]
    _b = store.fetch_states(_keys) if hasattr(store, "fetch_states") else {}
    _ok = bool(_b)
    def _g(k):
        return (_b.get(k) or {}) if _ok else (store.load_state(k) or {})
    fa_raw = _g("fleet-alerts")
    fa = fa_raw.get("alerts") or []
    review = _g("evidence-review")
    lm = _g("lighter-market")
    fr = _g("fleet-risk")
    lf = _g("brain-lens-forward")

    # ---- feed alerts: latest per key inside the window --------------------
    latest, fires24, fires_12, fires_prior12 = {}, {}, {}, {}
    for a in fa:
        k = a.get("key") or a.get("msg")
        ts = a.get("ts") or 0
        if ts >= now - WINDOW_H * 3600 and (k not in latest or ts > latest[k]["ts"]):
            latest[k] = a
        if ts >= now - 24 * 3600:
            fires24[k] = fires24.get(k, 0) + 1
        if ts >= now - 12 * 3600:
            fires_12[k] = fires_12.get(k, 0) + 1
        elif ts >= now - 24 * 3600:
            fires_prior12[k] = fires_prior12.get(k, 0) + 1

    # ---- synthesized evidence (level-triggered; seen-map dedups notify) ----
    synth = (synthesize(lm, fr, lf, now) + detect_veto_flap(fa, now)
             + synthesize_alerts_feed(fa_raw, now))

    # ---- EXPAND-direction synthesis: winners, promotions, tuner activity,
    # and restrictions that never bind (the board's other eye) --------------
    tuner_state = _g("scout-tuner")
    xp_state = _g("xp-judge")
    bot_rows = []
    try:
        bot_rows = store.fetch_bot_pnl() or []
    except Exception:
        bot_rows = []
    synth += synthesize_expand((lf.get("lenses") or {}) if _fresh(lf, LENS_FRESH_S) else {},
                               tuner_state, bot_rows, lm, now, xp_state,
                               radar_state=_g("fleet-radar"))

    # 🦾 proprioception: what the autonomy stack's own movements measured
    prop_b = _g("fleet-proprioception")
    synth += synthesize_proprioception(prop_b, now)

    # [2026-07-30] the shadow books' author. Reads their published rows, the
    # registry's current lever values and proprioception's hurting set; emits
    # at most ONE step per book per cycle. `prior_books` is this board's own
    # memory of each book's close count, which is what makes "STARVED for
    # BOOK_STARVED_H" measurable at all — a single snapshot cannot tell a
    # quiet book from a dead one.
    prior_books = (prior.get("books") or {})
    book_levers, book_items = synthesize_books(
        bot_rows, prior_books, prop_b, now, tuning_mod=tuning)
    synth += book_items
    books_out = {}
    for _bot in BOOK_AUTHOR:
        _r = next((r for r in (bot_rows or []) if str(r.get("bot")) == _bot), None)
        if _r is None:
            # keep the PRIOR memory rather than resetting the clock: a missing
            # row is a publish gap, and resetting would restart the starvation
            # window every time the DB blinked.
            if _bot in prior_books:
                books_out[_bot] = prior_books[_bot]
            continue
        _closed = int(_r.get("closed_trades") or 0)
        _prev = prior_books.get(_bot) or {}
        # the clock only RESTARTS when the close count actually moves
        books_out[_bot] = ({"closed": _closed, "ts": now}
                           if _closed != int(_prev.get("closed") or -1)
                           else {"closed": _closed,
                                 "ts": float(_prev.get("ts") or now)})

    # 🏛️ the Parliament: chamber health, book drawdown vs the go-live gate,
    # ML-edge evidence (operator-sanctioned consumer, 21-Jul)
    synth += synthesize_parliament(_g("parliament"), _g("parliament-tuning"),
                                   now)

    # implementation shortfall (live execution quality) — its own tracker
    # pushes the phone alert; the board only SURFACES the verdict (dedicated-
    # push key, so no double-send). live-ahead = info, live-slipping = warn.
    isf = _g("impl-shortfall")
    if _fresh(isf) and isf.get("verdict") in ("live-ahead", "live-slipping"):
        _ahead = isf["verdict"] == "live-ahead"
        _xs = isf.get("exit_slip_bps")
        synth.append({
            "key": "board:impl-shortfall",
            "severity": "info" if _ahead else "warn",
            "direction": "expand" if _ahead else "restrict",
            "msg": (f"📏 LIVE {'BEATS' if _ahead else 'trails'} shadow "
                    f"{isf.get('gap_pp')}pp/trade over {isf.get('n_overlap')} coins"
                    + (f" (exit-slip {_xs}bps)" if _xs is not None else "")),
            "proposal": ("execution AHEAD of the model — no action" if _ahead else
                         "sustained slip → live clip-scale reflex + judge respond; "
                         "watch the entry-vs-exit split as fill prices accrue"),
            "lever": "impl-shortfall", "ts": now, "source": "board"})

    # ---- LIVE lane 💰: evidence-gated clip scaling on the real-money bots,
    # grade-aware (🦾 hurting releases/blocks; top step needs helping) and
    # time-local (7d realized ledger window on BOTH directions, 16-Jul) ----
    live_window = None
    try:
        if hasattr(store, "fetch_realized_window"):
            live_window = store.fetch_realized_window(sorted(LIVE_ROWS), days=7)
    except Exception:  # noqa: BLE001
        live_window = None
    prior_live = prior.get("live_scale") or {}
    prior_release_ts = float(prior.get("live_released_ts") or 0)
    desired_live, live_item = synthesize_live(bot_rows, fr, lm, fa, prior_live,
                                              now, live_clip_grade(prop_b),
                                              window=live_window,
                                              released_ts=prior_release_ts)
    # [2026-07-16 blind-hold] an in-force RESTRICTION (< 1.0) is never
    # withdrawn on missing data: assert-nothing WITHOUT a reasoned item
    # (blind cohort / dark window) re-asserts the prior restriction until
    # the evidence is back and healing is MEASURED. A reasoned release
    # (hurting grade) and any expansion release stay fail-closed as-is.
    _plv = prior_live.get("value")
    _vis = {str(r.get("bot")) for r in (bot_rows or [])
            if str(r.get("bot")) in LIVE_ROWS}
    live_cohort_ok = bool(LIVE_ROWS) and len(_vis) >= len(LIVE_ROWS)
    if (desired_live is None and live_item is None
            and _plv is not None and float(_plv) < 1.0
            and not (live_cohort_ok and live_window is not None)):
        desired_live = float(_plv)
        live_item = {"key": "board:live-clip-scale", "severity": "action",
                     "msg": f"💰 LIVE clips x{desired_live:g} HELD — cohort/"
                            f"window not fully visible; a restriction is only "
                            f"released on measured healing",
                     "proposal": "conservative hold, re-asserted each cycle "
                                 "until the cohort + ledger window are back",
                     "lever": "live.clip_scale", "ts": now, "source": "board",
                     "direction": "restrict"}
    if live_item:
        synth.append(live_item)

    # ---- growth rail: widen Gap Scout's net when its census runs quiet -----
    census = _g("gapscout-census")
    growth_step, growth_levers, quiet_h = 0, {}, 0.0
    if _fresh(census, max_age_s=3600):
        quiet_h = float(census.get("quiet_hours") or 0.0)
        bar_scale = gapscout_bar_scale(prop_b)
        growth_step, growth_levers = widen_step(quiet_h, bar_scale)
        if growth_step:
            synth.append({
                "key": "board:gapscout-quiet", "severity": "info",
                "msg": f"🌱 Gap Scout census quiet {quiet_h:.0f}h — detection "
                       f"net widened to step {growth_step}/{len(WIDEN_LADDER)}"
                       + (f" (bars ×{bar_scale:g} — 🦾 the wider net has "
                          f"helped before)" if bar_scale < 1.0 else ""),
                "proposal": "widen (ENACTED via fleet_tuning): " + ", ".join(
                    f"{k}={v}" for k, v in sorted(growth_levers.items())),
                "lever": "growth-rail", "direction": "expand",
                "ts": now, "source": "board"})
    synth_new = [s for s in synth if s["key"] not in seen_prior]

    # ---- assemble the board -------------------------------------------------
    auto_map, items = {}, []
    for k, a in latest.items():
        age_h = (now - (a.get("ts") or now)) / 3600
        tr = trend_of(fires_12.get(k, 0), fires_prior12.get(k, 0))
        v = auto_verdict(k, a.get("severity"), age_h, tr)
        auto_map[k] = v
        items.append({
            "key": k, "msg": a.get("msg"), "sev": a.get("severity"),
            "score": score_item(a.get("severity"), age_h, fires24.get(k, 1),
                                corroborate(k, lm if _fresh(lm) else None)),
            "fires_24h": fires24.get(k, 0), "trend": tr, "source": "alerts",
            "first_seen": seen_prior.get(k) or _iso(a.get("ts")),
            "verdict": v,
        })
    # [2026-07-17] The three literals below are DELIBERATE, not unfinished —
    # recorded because they read like hardcodes and invite a "fix" that would
    # be wrong. A board item is LEVEL-TRIGGERED (docstring, synthesize): it is
    # re-derived from scratch each cycle and emitted ONLY while its condition
    # is true RIGHT NOW. So:
    #   age_h=0.0     — it is a live reading, not a past event. Decaying it
    #                   would bury a currently-true condition as it ages, which
    #                   is precisely backwards. Alerts decay because they are
    #                   edge-triggered facts about the past; these are not.
    #   fires_24h=1   — there is no fire history to count; level-triggered
    #                   items have no edges. persistence stays 1.0 rather than
    #                   inventing a number.
    #   corroborated  — every synthesizer is a JOIN over >=2 freshness-gated
    #                   feeds, so these are corroborated by construction, which
    #                   is the boost's whole meaning. `corroborate()` only knows
    #                   how to cross-check `disloc:` alert keys against
    #                   lighter-market; asking it about a board key would answer
    #                   False for the wrong reason.
    # CONSEQUENCE, ACCEPTED: an info board item scores 1.5 flat, so severity is
    # the only discriminator among them. That is the intended ordering — what
    # is true now, ranked by how bad it is.
    # The real defect these literals DID cause was in notify, not score: see
    # `escalated` below, which read `trend` and therefore read a constant.
    for s in synth:
        k = s["key"]
        auto_map[k] = "active"
        items.append({
            "key": k, "msg": s["msg"], "sev": s["severity"],
            "score": score_item(s["severity"], 0.0, 1, True),
            "fires_24h": 1, "trend": "steady", "source": "board",
            "first_seen": seen_prior.get(k) or _iso(now),
            "verdict": "active", "proposal": s.get("proposal"), "lever": s.get("lever"),
            "direction": s.get("direction", "restrict"),
        })

    merged = merge_verdicts(review.get("verdicts"), auto_map)
    for i in items:
        i["verdict"] = merged.get(i["key"], i["verdict"])
    items.sort(key=lambda i: -i["score"])

    # [2026-07-28 AUDIT FIX] mode told the Autonomy surface every expand item
    # was 'enact' — but the board's only actuators are the gapscout widen
    # ladder and live.clip_scale; lens-positive / promotion-watch / xp-phase
    # / stress-headroom / prop-helping are review SUGGESTIONS. A telemetry
    # view that overclaims autonomy is the mirror image of the fleet_tuning
    # doctrine hazard ("a telemetry view that disagrees with the actuator").
    # 'enact' now only for items whose levers the board itself writes.
    def _mode_of(s):
        if s.get("direction") != "expand":
            return MODE
        return ("enact" if (s.get("key") == "board:gapscout-quiet"
                            or s.get("lever") == "live.clip_scale")
                else "suggest")
    proposals = [{"key": s["key"], "lever": s["lever"], "proposal": s["proposal"],
                  "direction": s.get("direction", "restrict"),
                  "mode": _mode_of(s)}
                 for s in synth if s.get("proposal")]

    # ---- enact: ONE combined write per cycle (merge semantics keep other
    # authors' levers; the board's own set must arrive together) -------------
    board_levers = {}
    if book_levers:
        board_levers.update(book_levers)
    if growth_levers:
        board_levers.update(
            {k: {"value": v,
                 "reason": f"census quiet {quiet_h:.0f}h -> widen step {growth_step}",
                 "evidence": f"gapscout-census {census.get('updated')}: "
                             f"episodes_open={census.get('episodes_open')}, "
                             f"day={json.dumps(census.get('day'))}"}
             for k, v in growth_levers.items()})
    prior_live_val = prior_live.get("value")
    # [2026-07-16] a lapse/hurting release is now an EXPLICIT WITHDRAWAL
    # (tuning.release_levers), not a wait-for-TTL: the phone said "back to
    # x1.0" while the old lever could stay in force up to 2h. A true
    # removal (not a 1.0 overwrite) so consumers revert instantly AND
    # proprioception sees a clean 'released' episode end instead of a
    # phantom no-op stance it would have to grade.
    release_live = desired_live is None and prior_live_val is not None
    if desired_live is not None:
        board_levers["live.clip_scale"] = {
            "value": desired_live, "ttl_sec": LIVE_LEVER_TTL_S,
            "reason": (live_item or {}).get("msg", "")[:180],
            "evidence": f"live rows {sorted(LIVE_ROWS)}; gates in synthesize_live"}
    enacted = None
    if board_levers and tuning is not None:
        enacted = tuning.write_levers(board_levers, set_by="evidence-board",
                                      now_ts=now)
    released = None
    if release_live and tuning is not None:
        released = tuning.release_levers(["live.clip_scale"],
                                         set_by="evidence-board", now_ts=now)
    # did the LIVE change actually land? The URGENT push and the ladder's
    # memory must not claim a change the rail never recorded.
    live_write_needed = desired_live is not None or release_live
    live_write_ok = ((desired_live is not None
                      and bool(enacted
                               and "live.clip_scale" in (enacted.get("levers") or {})))
                     or (release_live and released is not None))
    prior_step = int(prior.get("growth_step") or 0)
    # the step push lists ONLY the board's own gapscout levers — the merged
    # payload also carries other authors' lanes (and the live lever), which
    # made the push read as if the census had enacted them.
    _gs_enacted = {k: v["value"]
                   for k, v in ((enacted or {}).get("levers") or {}).items()
                   if v.get("set_by") == "evidence-board"
                   and k.startswith("gapscout.")}
    if growth_step > prior_step and _gs_enacted:
        send_push(f"growth rail: Gap Scout net -> step {growth_step}",
                  f"census quiet {quiet_h:.0f}h; enacted: " + ", ".join(
                      f"{k}={v}" for k, v in sorted(_gs_enacted.items())),
                  priority="default", tags="seedling")
        print(f"[evidence_board] growth rail ENACTED step {growth_step}: "
              f"{sorted(_gs_enacted)}", flush=True)
    # live changes always reach the phone URGENT — it's real money — but
    # only once the write LANDED; a failed write logs and retries next cycle.
    if desired_live != prior_live_val and (desired_live is not None
                                           or prior_live_val is not None):
        if live_write_ok:
            send_push("LIVE clips " + (f"x{desired_live:g}" if desired_live
                                       else "back to x1.0 (lever released)"),
                      (live_item or {}).get("msg")
                      or "conditions no longer hold — released to operator sizing",
                      priority="urgent", tags="moneybag")
            print(f"[evidence_board] LIVE clip_scale: {prior_live_val} -> "
                  f"{desired_live}", flush=True)
        else:
            print(f"[evidence_board] LIVE clip_scale write FAILED — lever "
                  f"unchanged (wanted {prior_live_val} -> {desired_live}); "
                  f"retrying next cycle", flush=True)

    # ---- notify: NEW warn/action items AND new EXPAND items — good news
    # reaches the phone with the same machinery as warnings (default
    # priority, seedling tag; missing the cream is also a miss) -------------
    # Items with a DEDICATED push above (live clip scale, growth-rail step)
    # are skipped here so they aren't double-sent — and, critically, so an
    # ENACTED live action is never mislabeled "Proposed (shadow)" by the
    # generic template (the 15-Jul confusing push).
    DEDICATED_PUSH = {"board:live-clip-scale", "board:gapscout-quiet",
                      "board:impl-shortfall"}   # its tracker owns the push
    for i in items:
        if i["key"] in DEDICATED_PUSH:
            continue
        is_expand = i.get("direction") == "expand"
        if i["verdict"] != "active":
            continue
        if i["sev"] not in ("warn", "action") and not is_expand:
            continue
        is_new = i["key"] not in seen_prior
        prior_i = prior_items.get(i["key"], {})
        escalated = i["trend"] == "escalating" and prior_i.get("trend") != "escalating"
        # [2026-07-17] TWO ways a board item reaches the phone AFTER onset.
        # Neither existed: `escalated` reads `trend`, and every board item's
        # trend is the literal "steady" (see the assemble block above), so
        # `escalated` was False BY CONSTRUCTION for the entire board-authored
        # half. The gate collapsed to `is_new`, and `seen_prior` is written
        # every cycle the condition holds — so a level-triggered warn or action
        # notified EXACTLY ONCE, at onset, and then never again no matter how
        # long it ran or how bad it got. NOTIFY_GAP_H was unreachable for them.
        # That is the failure mode where a real problem is announced once, at
        # 3am, and is silent for the next three days.
        #
        # 1) WORSENED: severity climbed (info->warn->action) while the item was
        #    already on the board. For a level-triggered item this IS the
        #    escalation signal — the fires-based `trend` cannot see it, because
        #    a re-derived item has no edges to count.
        # 2) SUSTAINED: a warn/action that simply will not go away. Rate-limited
        #    by RENOTIFY_H (a reminder, not a nag) and still subject to the
        #    NOTIFY_GAP_H floor below.
        # Restrict-side only: expand items announce once and stay quiet —
        # re-paging good news is noise, and it is not what blindness costs.
        last_n = notified.get(i["key"], 0)
        worsened = (not is_new
                    and SEV_W.get(i["sev"], 1.0) > SEV_W.get(prior_i.get("sev"), 1.0))
        sustained = (not is_new and not is_expand
                     and i["sev"] in ("warn", "action")
                     and last_n > 0 and now - last_n >= RENOTIFY_H * 3600)
        if ((is_new or escalated or worsened or sustained)
                and now - last_n >= NOTIFY_GAP_H * 3600):
            # expand items SUGGEST (review candidates); restrict items in
            # shadow mode are PROPOSED — never tag an expand item "(shadow)".
            if i.get("proposal"):
                tag = "Suggests" if is_expand else f"Proposed ({MODE})"
                body = (i["msg"] or "") + f"\n\n{tag}: {i['proposal']}"
            else:
                body = i["msg"] or ""
            title = ("evidence board (expand): " if is_expand else "evidence board: ") \
                + (i["msg"] or i["key"])[:60]
            if send_push(title, body,
                         priority="default" if is_expand else "urgent",
                         tags="seedling" if is_expand else "scales"):
                notified[i["key"]] = now
                print(f"[evidence_board] notified: {i['key']}", flush=True)

    # ladder memory: a live write that never landed must not advance the
    # cooldown clock or the release stamp — carry the prior state so the
    # transition retries next cycle.
    if live_write_needed and not live_write_ok:
        live_scale_out = prior.get("live_scale")
        released_out = prior_release_ts or None
    else:
        live_scale_out = ({"value": desired_live,
                           "ts": (prior_live.get("ts")
                                  if desired_live == prior_live_val else now)}
                          if desired_live is not None else None)
        released_out = (now if release_live else prior_release_ts) or None
    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC, "mode": MODE,
        "items": items[:20],
        "seen": {i["key"]: i["first_seen"] for i in items},
        "proposals": proposals,
        # step memory only advances when the gapscout write LANDED — else a
        # failed write at a step transition swallows the mandated push forever
        "growth_step": (growth_step if (_gs_enacted or not growth_levers)
                        else prior_step),
        "books": books_out,
        "live_scale": live_scale_out,
        "live_released_ts": released_out,
        "enacted": ({k: v["value"] for k, v in enacted["levers"].items()
                     if v.get("set_by") == "evidence-board"}
                    if enacted else None),
        "notified": {k: v for k, v in notified.items() if now - v < 7 * 86400},
        "inputs_fresh": {"lighter_market": _fresh(lm), "fleet_risk": _fresh(fr),
                         "lens_forward": _fresh(lf, LENS_FRESH_S),
                         "live_window": live_window is not None,
                         "fleet_alerts": _fresh(fa_raw, ALERTS_FRESH_S),
                         "gapscout_census": _fresh(census, max_age_s=3600)},
    }
    store.save_state(BOARD_KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(BOARD_KEY, {"updated": payload["updated"],
                                           "n_items": len(items),
                                           "top": [i["key"] for i in items[:5]],
                                           "proposals": len(proposals)})
        except Exception:
            pass
    print(f"[evidence_board] {_iso(now)} items={len(items)} "
          f"(synth {len(synth)}, new {len(synth_new)}) proposals={len(proposals)} mode={MODE}",
          flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    # scoring is monotone in every input
    assert score_item("warn", 0, 1, False) > score_item("info", 0, 1, False)
    assert score_item("warn", 0, 1, False) > score_item("warn", 24, 1, False)
    assert score_item("warn", 0, 5, False) > score_item("warn", 0, 1, False)
    assert score_item("warn", 0, 1, True) > score_item("warn", 0, 1, False)
    # trend
    assert trend_of(3, 1) == "escalating" and trend_of(0, 2) == "decaying" and trend_of(1, 1) == "steady"
    # auto-verdicts
    assert auto_verdict("census:50", "info", 30, "steady") == "stale"
    assert auto_verdict("factor-sample:1", "info", 2, "steady") == "active"
    assert auto_verdict("disloc:KAITO", "info", 30, "escalating") == "active"   # escalation blocks archiving
    assert auto_verdict("disloc:KAITO", "info", 30, "steady") == "stale"
    assert auto_verdict("veto:ADA", "action", 50, "steady") == "stale"
    assert auto_verdict("live-shadow-gap", "warn", 100, "decaying") == "active"  # never auto-cleared
    # manual verdicts win in BOTH directions
    m = merge_verdicts([{"key": "a", "status": "resolved"}, {"key": "b", "status": "active"}],
                       {"a": "active", "b": "stale", "c": "stale"})
    assert m == {"a": "resolved", "b": "active", "c": "stale"}
    # synthesis: stress + lens rules fire; stale feeds fire NOTHING
    fresh = _iso()
    lm = {"updated": fresh, "stress": {"med": 20}}
    fr = {"updated": fresh, "fleet_dd_7d": -0.04, "gross": 25, "long_budget": 20,
          "exposure": {"long_effective_n": 10.1}}
    lf = {"updated": fresh,
          "lenses": {"momentum": {"n4h": 90, "hit4h": 0.37, "avg4h_pct": -1.05},
                     "dip": {"n4h": 2, "hit4h": 0.0, "avg4h_pct": -0.6}}}
    keys = {s["key"] for s in synthesize(lm, fr, lf, _now())}
    assert keys == {"board:venue-stress", "board:governor-near-trip", "board:budget-crowding",
                    "board:lens-floor:momentum", "board:lens-negative:momentum"}, keys
    assert synthesize({"updated": "2020-01-01T00:00:00+00:00", "stress": {"med": 99}},
                      {}, {}, _now()) == []
    # a FOSSIL lens payload (dead brain) fires NO lens items on the restrict
    # side either — the same freshness bar the expand side always used
    k_st = {s["key"] for s in synthesize(
        lm, fr, dict(lf, updated="2020-01-01T00:00:00+00:00"), _now())}
    assert not any(k.startswith("board:lens-") for k in k_st), k_st
    # flap detection
    now = _now()
    fa = [{"key": "veto:ADA,kBONK", "ts": now - 3 * 86400},
          {"key": "veto:ADA", "ts": now - 2 * 86400},
          {"key": "veto:ADA", "ts": now - 1000}]
    flaps = detect_veto_flap(fa, now)
    assert [f["key"] for f in flaps] == ["board:veto-flap:ADA"], flaps
    # EXPAND synthesis: winners at the floor, tuner activity, promotion
    # watch, dead vetoes — all direction='expand', all with the same shape
    lfw = {"dip": {"n4h": 100, "avg4h_pct": 1.1, "hit4h": 0.92},      # winner
           "momentum": {"n4h": 90, "avg4h_pct": -1.0, "hit4h": 0.33},  # loser
           "breakout": {"n4h": 10, "avg4h_pct": 5.0, "hit4h": 1.0}}    # tiny n
    tstate = {"updated": fresh, "ttl_sec": 10800,
              "enacted": {"scout.dip_range_max": 0.15}}
    rows = [{"bot": "lighter-dislocation-lshadow", "closed_trades": 45,
             "pnl_abs": 22.0, "extra": {}},                            # passes
            {"bot": "lighter-perp-sniper-lshadow", "closed_trades": 45,
             "pnl_abs": -5.0, "extra": {}},                            # negative
            {"bot": "crypto-trend-daily-lighter", "closed_trades": 99,
             "pnl_abs": 99.0, "extra": {}},                            # live row
            {"bot": "perps-funding-carry-lshadow", "closed_trades": 10,
             "pnl_abs": 50.0, "extra": {}}]                            # n small
    ex = synthesize_expand(lfw, tstate, rows,
                           {"updated": fresh, "stress": {"med": 5}}, _now(),
                           xp_state={"updated": fresh, "ttl_sec": 10800,
                                     "phase": "running",
                                     "candidate": "enter-gate-0.30"})
    xkeys = {e["key"] for e in ex}
    assert xkeys == {"board:lens-positive:dip", "board:tuner-enacted",
                     "board:promotion-watch:lighter-dislocation-lshadow",
                     "board:xp-running:enter-gate-0.30",
                     "board:stress-headroom"}, xkeys
    assert all(e["direction"] == "expand" and e["severity"] == "info" for e in ex)
    # stale tuner + hot venue -> those items vanish; nothing else appears
    ex2 = synthesize_expand(lfw, {"updated": "2020-01-01T00:00:00+00:00",
                                  "ttl_sec": 10800, "enacted": {"x": 1}},
                            [], {"updated": fresh, "stress": {"med": 20}}, _now())
    k2 = {e["key"] for e in ex2}
    assert "board:tuner-enacted" not in k2 and "board:stress-headroom" not in k2
    assert "board:lens-positive:dip" in k2

    # [2026-07-28] RADAR IS SENIOR to the naive promotion screen: an
    # artifact-classed book keeps its item but the item tells the truth
    # (🔬 + do-NOT-promote proposal); a real_edge class corroborates; a
    # stale radar changes nothing (fail-open). Mutation check: dropping the
    # radar read turns the artifact assert red; dropping the freshness gate
    # turns the stale assert red.
    _radar = {"updated": fresh, "ttl_sec": 3600, "books": [
        {"bot": "lighter-dislocation-lshadow", "class": "artifact",
         "caveats": ["3 closes are 80% of net"]}]}
    ex3 = synthesize_expand({}, None, rows,
                            {"updated": fresh, "stress": {"med": 20}}, _now(),
                            radar_state=_radar)
    _pw = next(e for e in ex3
               if e["key"] == "board:promotion-watch:lighter-dislocation-lshadow")
    assert "artifact" in _pw["msg"] and "🔬" in _pw["msg"], _pw
    assert "NOT promote" in _pw["proposal"], _pw
    _radar_good = {"updated": fresh, "ttl_sec": 3600, "books": [
        {"bot": "lighter-dislocation-lshadow", "class": "real_edge",
         "caveats": ["fading"]}]}
    ex4 = synthesize_expand({}, None, rows,
                            {"updated": fresh, "stress": {"med": 20}}, _now(),
                            radar_state=_radar_good)
    _pw4 = next(e for e in ex4
                if e["key"] == "board:promotion-watch:lighter-dislocation-lshadow")
    assert "real_edge" in _pw4["msg"] and "🚀" in _pw4["msg"], _pw4
    _stale_radar = dict(_radar, updated="2020-01-01T00:00:00+00:00")
    ex5 = synthesize_expand({}, None, rows,
                            {"updated": fresh, "stress": {"med": 20}}, _now(),
                            radar_state=_stale_radar)
    _pw5 = next(e for e in ex5
                if e["key"] == "board:promotion-watch:lighter-dislocation-lshadow")
    assert "artifact" not in _pw5["msg"] and "🚀" in _pw5["msg"], \
        "a stale radar must change nothing (fail-open)"

    # 🦾 proprioception synthesis: hurting=warn/restrict, helping=expand,
    # neutral silent, stale organ emits nothing
    prop = {"updated": fresh, "ttl_sec": 2700, "verdicts": {
        "taker.dip_range": {"verdict": "hurting", "n": 3, "sum_delta_usd": -5.1},
        "scout.dip_range_max": {"verdict": "helping", "n": 2,
                                "sum_delta_grades": 35},
        "taker.tp": {"verdict": "neutral", "n": 1, "sum_delta_usd": 0.4}}}
    pit = synthesize_proprioception(prop, _now())
    pk = {p["key"]: p for p in pit}
    assert set(pk) == {"board:prop-hurting:taker.dip_range",
                       "board:prop-helping:scout.dip_range_max"}, pk
    assert pk["board:prop-hurting:taker.dip_range"]["severity"] == "warn"
    assert "Σ$-5.10" in pk["board:prop-hurting:taker.dip_range"]["msg"]
    assert pk["board:prop-helping:scout.dip_range_max"]["direction"] == "expand"
    assert "Σ+35 grades" in pk["board:prop-helping:scout.dip_range_max"]["msg"]
    assert synthesize_proprioception(
        dict(prop, updated="2020-01-01T00:00:00+00:00"), _now()) == []
    assert synthesize_proprioception({}, _now()) == []
    assert synthesize_proprioception(None, _now()) == []

    # 🏛️ Parliament synthesis: stalled=warn, drawdown warn@-10%/action@-15%,
    # ML edge=expand info, healthy chamber emits nothing, stale emits nothing
    parl = {"updated": fresh, "ttl_sec": 900,
            "health": {"stalled": ["data.market"]},
            "books": {"pm-abbott": {"pnl": -101.0, "closed": 12, "open": 1},
                      "pm-rudd": {"pnl": -151.0, "closed": 8, "open": 0},
                      "pm-gillard": {"pnl": 4.0, "closed": 3, "open": 1}},
            "ml": {"ready": True, "n_seen": 400,
                   "oos_acc": {"logit": 0.57, "knn": 0.51}}}
    parl_t = {"updated": fresh, "ttl_sec": 900,
              "active": {"pm-a": [1, 2], "pm-b": [3], "pm-c": [4]}}
    git = synthesize_parliament(parl, parl_t, _now())
    gk = {g["key"]: g for g in git}
    assert set(gk) == {"board:parliament-stalled",
                       "board:parliament-drawdown:pm-abbott",
                       "board:parliament-drawdown:pm-rudd",
                       "board:parliament-ml-edge",
                       "board:parliament-tuner-breadth"}, gk
    assert gk["board:parliament-stalled"]["severity"] == "warn"
    assert gk["board:parliament-drawdown:pm-abbott"]["severity"] == "warn"
    assert gk["board:parliament-drawdown:pm-rudd"]["severity"] == "action"
    assert gk["board:parliament-ml-edge"]["direction"] == "expand"
    assert "logit" in gk["board:parliament-ml-edge"]["msg"]
    healthy = {"updated": fresh, "ttl_sec": 900, "health": {"stalled": []},
               "books": {"pm-gillard": {"pnl": 4.0, "closed": 3, "open": 1}},
               "ml": {"ready": False, "n_seen": 0, "oos_acc": {}}}
    assert synthesize_parliament(healthy, None, _now()) == [], \
        "a healthy chamber must add NOTHING to the board"
    assert synthesize_parliament(
        dict(parl, updated="2020-01-01T00:00:00+00:00"), parl_t, _now()) == []
    assert synthesize_parliament(None, parl_t, _now()) == []
    # a stale tuning payload cannot mint the breadth item on its own
    few = synthesize_parliament(
        healthy, dict(parl_t, updated="2020-01-01T00:00:00+00:00"), _now())
    assert few == [], few

    # LIVE lane: earn-up ladder + cooldown, instant down, fail-safe absent.
    # The rows mirror the REAL cohort shape (16-Jul balance pass): Tide Rider
    # HOLDS positions (0 closes ever, tiny mark bleed), the Funding Farmer
    # trades (lifetime slightly negative, 7d window positive). This exact
    # shape must earn the first step — that reachability IS the fix.
    nowts = _now()
    fresh_fr = {"updated": fresh, "ttl_sec": 900, "light": "green",
                "fleet_dd_7d": -0.005}
    calm_lm = {"updated": fresh, "stress": {"med": 5}}
    # [2026-07-17 AUDIT] The cohort under test is DECLARED, not inherited from
    # the production roster. These cases exercise synthesize_live's ROW SHAPES
    # — a HOLDER (0 window closes, judged on its mark-anchored lifetime) vs a
    # TRADER, plus partial-cohort semantics — logic that must stay covered no
    # matter who occupies the live slot. Pinning the fixture to the real
    # LIVE_ROWS meant this suite FAILED ON THE ROSTER FIX rather than on a bug,
    # which is the tell: a test that reads a production constant is testing
    # today's deployment, not the function. Two synthetic books, so the holder
    # branch survives Tide Rider's retirement. The production roster gets its
    # OWN guard below (`no retired row in LIVE_ROWS`) — that is the assertion
    # that would have caught the real defect.
    _saved_live_rows = LIVE_ROWS
    globals()["LIVE_ROWS"] = {"holder-book", "trader-book"}
    live_ok = [{"bot": "holder-book", "closed_trades": 0,
                "pnl_abs": -0.23, "updated_at": fresh},
               {"bot": "trader-book", "closed_trades": 33,
                "pnl_abs": -0.30, "updated_at": fresh}]
    win_ok = {"holder-book": {"pnl": 0.0, "closes": 0},
              "trader-book": {"pnl": 2.4, "closes": 14}}
    s, it = synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                            window=win_ok)
    assert s == 1.25 and it["direction"] == "expand" and it["severity"] == "action"
    # DARK ledger window -> the up-scale fails CLOSED (no measured week, no up)
    assert synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts) == (None, None)
    s2, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.25, "ts": nowts - 3600}, nowts,
                            window=win_ok)
    assert s2 == 1.25, "cooldown must hold the step"
    # 🦾 the top step must be MEASURED: no grade (dark sense) -> fail-closed
    # hold at the mid step; a fresh HELPING grade unlocks it
    s3, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.25, "ts": nowts - 25 * 3600}, nowts,
                            window=win_ok)
    assert s3 == 1.25, "no measured HELPING -> top step stays out of reach"
    s3b, it3b = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                                {"value": 1.25, "ts": nowts - 25 * 3600},
                                nowts, clip_grade="helping", window=win_ok)
    assert s3b == 1.5 and "HELPING" in it3b["msg"], (s3b, it3b)
    s4, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.5, "ts": nowts - 25 * 3600}, nowts,
                            clip_grade="helping", window=win_ok)
    assert s4 == 1.5, "ladder top is the ceiling"
    # 🦾 HURTING releases an asserted lever (item, no scale) and silently
    # blocks a fresh up-start; the DOWN reflex stays senior to the grade
    sh, ith = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                              {"value": 1.25, "ts": nowts - 25 * 3600},
                              nowts, clip_grade="hurting", window=win_ok)
    assert sh is None and ith["direction"] == "restrict" \
        and "RELEASED" in ith["msg"], (sh, ith)
    assert synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                           clip_grade="hurting", window=win_ok) == (None, None)
    win_hole = dict(win_ok, **{"trader-book":
                               {"pnl": -12.0, "closes": 9}})
    sh2, ith2 = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                                {"value": 1.25, "ts": 0}, nowts,
                                clip_grade="hurting", window=win_hole)
    assert sh2 == LIVE_DOWN_SCALE, "7d-hole down-scale beats the release"
    # grade sourcing: fresh hurting/helping surface; neutral/stale/absent None
    fp = _iso()
    assert live_clip_grade({"updated": fp, "ttl_sec": 2700, "verdicts": {
        "live.clip_scale": {"verdict": "hurting"}}}) == "hurting"
    assert live_clip_grade({"updated": fp, "ttl_sec": 2700, "verdicts": {
        "live.clip_scale": {"verdict": "neutral"}}}) is None
    assert live_clip_grade({"updated": "2020-01-01T00:00:00+00:00",
                            "ttl_sec": 60, "verdicts": {
                                "live.clip_scale": {"verdict": "helping"}}}) is None
    assert live_clip_grade({}) is None and live_clip_grade(None) is None
    # DOWN is TIME-LOCAL (16-Jul balance pass): a 7d realized hole cuts even
    # while lifetime looks harmless...
    s5, it5 = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                              {"value": 1.5, "ts": 0}, nowts, window=win_hole)
    assert s5 == 0.75 and it5["direction"] == "restrict" \
        and it5["severity"] == "action" and "7d" in it5["msg"]
    # ...a healed book is NOT hurt by an old lifetime scar (ratchet removed;
    # the scar still blocks the up-scale via the non-harm tolerance)...
    healed = [live_ok[0], dict(live_ok[1], pnl_abs=-15.0)]
    assert synthesize_live(healed, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None), \
        "positive 7d window forgives a -$15 lifetime scar (no down, no up)"
    # ...a HOLDER row (0 window closes) keeps the FULL -$10 bar on its
    # mark-anchored lifetime — the window is structurally blind to it, so
    # it must not inherit the weaker backstop...
    bleed = [dict(live_ok[0], pnl_abs=-12.0), live_ok[1]]
    s5c, it5c = synthesize_live(bleed, fresh_fr, calm_lm, [], {}, nowts,
                                window=win_ok)
    assert s5c == 0.75 and "(mark)" in it5c["msg"], (s5c, it5c)
    # ...while a TRADER row (window visible + positive) only cuts at the
    # 2x lifetime backstop...
    deep = [live_ok[0], dict(live_ok[1], pnl_abs=-22.0)]
    s5e, it5e = synthesize_live(deep, fresh_fr, calm_lm, [], {}, nowts,
                                window=win_ok)
    assert s5e == 0.75 and "backstop" in it5e["msg"], (s5e, it5e)
    # ...and a DARK window falls back to the OLD lifetime rule (tighten
    # never weakens on missing data)
    s5d, _ = synthesize_live(healed, fresh_fr, calm_lm, [], {}, nowts)
    assert s5d == 0.75, "dark window -> lifetime <= -$10 still cuts"
    s6, _ = synthesize_live(live_ok, fresh_fr, calm_lm,
                            [{"key": "live-shadow-gap:ff", "ts": nowts - 100}],
                            {}, nowts)
    assert s6 == 0.75, "FRESH divergence alert -> immediate down-scale"
    # a STALE divergence alert must NOT cut live size (the 15-Jul artifact:
    # a 39h-old fossil from the retired whole-book check triggered a false
    # down-scale). Use not-yet-earned rows so ignoring the stale alert lands
    # cleanly on "assert nothing" — the correct outcome.
    live_neutral = [dict(live_ok[0], closed_trades=5), dict(live_ok[1], closed_trades=5)]
    s6b, it6b = synthesize_live(
        live_neutral, fresh_fr, calm_lm,
        [{"key": "live-shadow-gap", "ts": nowts - (LIVE_GAP_FRESH_H + 1) * 3600,
          "msg": "gap +5.4%"}],
        {}, nowts)
    assert s6b is None and it6b is None, "stale divergence alert must be ignored"
    # ...and the SAME alert, fresh, still cuts (the reflex still works)
    s6c, _ = synthesize_live(
        live_neutral, fresh_fr, calm_lm,
        [{"key": "live-shadow-gap", "ts": nowts - 100, "msg": "gap +5.4%"}],
        {}, nowts)
    assert s6c == 0.75, "a FRESH divergence alert still down-scales"
    # [2026-07-16 AUDIT] a PERSISTING divergence: old ts (dedup) but fresh
    # last_seen (re-confirmed) must keep cutting — no ~18h blind window
    s6d, _ = synthesize_live(
        live_neutral, fresh_fr, calm_lm,
        [{"key": "live-shadow-gap", "ts": nowts - 20 * 3600,
          "last_seen": nowts - 100, "msg": "gap +5.4%"}],
        {}, nowts)
    assert s6d == 0.75, "fresh last_seen on a persisting divergence still cuts"
    # the EARNED gate's three prover bars + the cohort non-harm tolerance
    tol = [dict(live_ok[0], pnl_abs=-5.0), live_ok[1]]
    assert synthesize_live(tol, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None), \
        "slow-row bleed beyond LIVE_SLOW_TOL blocks the up-scale"
    small = [live_ok[0], dict(live_ok[1], closed_trades=14)]
    assert synthesize_live(small, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None), \
        "no row with >=30 lifetime closes -> nothing proves the edge"
    thin = dict(win_ok, **{"trader-book":
                           {"pnl": 2.4, "closes": 3}})
    assert synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                           window=thin) == (None, None), \
        "a thin window sample proves nothing"
    flat = dict(win_ok, **{"trader-book":
                           {"pnl": 0.0, "closes": 14}})
    assert synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                           window=flat) == (None, None), \
        "a flat week proves nothing"
    # anti-flap: a fresh release parks the up-ladder; an old one does not;
    # the DOWN reflex ignores the gap entirely
    assert synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok,
                           released_ts=nowts - 600) == (None, None)
    sr, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                            window=win_ok, released_ts=nowts - 2 * 3600)
    assert sr == 1.25, "an old release must not park the ladder forever"
    srd, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts,
                             window=win_hole, released_ts=nowts - 600)
    assert srd == 0.75, "down ignores the re-assert gap"
    # [2026-07-16 AUDIT] a FROZEN row (updated_at 4h old) must block the
    # up-scale even with a healthy window; so must a missing updated_at
    live_frozen = [dict(live_ok[0], updated_at=_iso(nowts - 4 * 3600)), live_ok[1]]
    assert synthesize_live(live_frozen, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None)
    live_noage = [{k: v for k, v in live_ok[0].items() if k != "updated_at"}, live_ok[1]]
    assert synthesize_live(live_noage, fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None)
    # ...but a frozen row does NOT block the down reflex (lifetime backstop)
    s_fdown, _ = synthesize_live([dict(live_frozen[0], pnl_abs=-25.0), live_ok[1]],
                                 fresh_fr, calm_lm, [], {}, nowts,
                                 window=win_ok)
    assert s_fdown == 0.75, "down-scale must not require row freshness"
    # [2026-07-16 AUDIT] a payload's own ttl_sec tightens _fresh: fleet-risk
    # (ttl 900) that is 40 min stale must no longer pass the 2700s window
    stale_fr = dict(fresh_fr, updated=_iso(nowts - 2400))
    assert synthesize_live(live_ok, stale_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None), \
        "40-min-stale fleet-risk (ttl 900s) must fail _fresh"
    assert synthesize_live(live_ok, dict(fresh_fr, light="red"), calm_lm,
                           [], {}, nowts, window=win_ok) == (None, None)
    assert synthesize_live(live_ok, fresh_fr,
                           {"updated": fresh, "stress": {"med": 20}},
                           [], {}, nowts, window=win_ok) == (None, None), \
        "hot venue blocks up"
    assert synthesize_live(live_ok[:1], fresh_fr, calm_lm, [], {}, nowts,
                           window=win_ok) == (None, None)
    # PARTIAL COHORT never disarms the tighten side: the rows-free divergence
    # alert and a visible row's hurt both still cut; only expand goes blind
    sp1, ip1 = synthesize_live(live_ok[:1], fresh_fr, calm_lm,
                               [{"key": "live-shadow-gap", "ts": nowts - 100}],
                               {}, nowts, window=win_ok)
    assert sp1 == 0.75 and "cohort partially visible" in ip1["msg"], (sp1, ip1)
    sp2, _ = synthesize_live([dict(live_ok[0], pnl_abs=-12.0)], fresh_fr,
                             calm_lm, [], {}, nowts, window=win_ok)
    assert sp2 == 0.75, "a visible hurt row cuts even with the cohort partial"
    if tuning is not None:
        for v in LIVE_LADDER + [LIVE_DOWN_SCALE]:
            assert tuning.clamp("live.clip_scale", v) == v
    globals()["LIVE_ROWS"] = _saved_live_rows

    # [2026-07-17 AUDIT] THE PRODUCTION-ROSTER GUARD — the assertion that would
    # have caught the real defect, which no row-shape fixture could. A retired
    # row in LIVE_ROWS is unfalsifiable from inside synthesize_live: its bot_pnl
    # row is deleted at boot, so `cohort_ok = len(rows) >= len(LIVE_ROWS)` is
    # permanently False — no up-scale ever, and any down-scale is re-asserted
    # by the blind-hold forever (a one-way ratchet on REAL clips). Assert the
    # roster against the retirement list itself, so retiring a bot without
    # sweeping this cohort fails loudly HERE instead of silently pinning clips.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as _retired
        _rot = LIVE_ROWS & set(_retired)
        assert not _rot, (
            f"LIVE_ROWS names RETIRED row(s) {sorted(_rot)} — their bot_pnl "
            f"rows are pruned at boot, so the live cohort can never be fully "
            f"visible: no up-scale is possible and any down-scale becomes "
            f"permanent. Remove them (and add the slot's new occupant ONLY if "
            f"it actually consumes live.clip_scale via venue_context).")
    except ImportError:      # not in this image — the guard is best-effort
        pass

    # growth-rail ladder: quiet->0, monotone, later steps inherit earlier
    assert widen_step(1) == (0, {})
    s1, lv1 = widen_step(25)
    assert s1 == 1 and lv1["gapscout.prefilter_gap"] == 0.0015
    assert "gapscout.extra_exchanges" not in lv1, "venues need 48h quiet"
    s2, lv2 = widen_step(50)
    assert s2 == 2 and lv2["gapscout.prefilter_gap"] == 0.0010
    assert lv2["gapscout.extra_exchanges"] == "kucoin,gateio"
    s3, lv3 = widen_step(200)
    assert s3 == 3 and lv3["gapscout.extra_exchanges"] == "kucoin,gateio,mexc"
    assert lv3["gapscout.max_book_fetches"] == 60, "step 3 inherits step 2"
    # 🦾 expand side: a HELPING gapscout verdict discounts the quiet bars
    # (values unchanged, only the wait) — with a hard floor on the bar
    assert widen_step(19) == (0, {}), "19h quiet: no step at full bars"
    s1h, lv1h = widen_step(19, 0.75)
    assert s1h == 1 and lv1h["gapscout.prefilter_gap"] == 0.0015, (s1h, lv1h)
    assert widen_step(37, 0.75)[0] == 2, "48h bar -> 36h under the discount"
    assert widen_step(11, 0.4)[0] == 0, "WIDEN_BAR_MIN_H floors the bar (12h)"
    assert widen_step(13, 0.4)[0] == 1
    # scale sourcing: fresh helping gapscout verdict -> discount; a helping
    # TAKER verdict, a stale organ, or nothing -> full bars
    prop_gs = {"updated": fresh, "ttl_sec": 2700, "verdicts": {
        "gapscout.prefilter_gap": {"verdict": "helping", "n": 2}}}
    assert gapscout_bar_scale(prop_gs) == GAPSCOUT_HELP_SCALE
    assert gapscout_bar_scale({"updated": fresh, "ttl_sec": 2700, "verdicts": {
        "taker.tp": {"verdict": "helping"},
        "gapscout.prefilter_gap": {"verdict": "neutral"}}}) == 1.0
    assert gapscout_bar_scale(dict(prop_gs,
                                   updated="2020-01-01T00:00:00+00:00")) == 1.0
    assert gapscout_bar_scale({}) == 1.0 and gapscout_bar_scale(None) == 1.0
    # every ladder value must be registered AND in-bounds in fleet_tuning —
    # a ladder entry that would be clamped/dropped is a config bug HERE.
    if tuning is not None:
        for _, lv in WIDEN_LADDER:
            for k, v in lv.items():
                assert tuning.clamp(k, v) == v, f"ladder lever out of registry bounds: {k}={v}"
    # --- the alerts BLOODSTREAM check (17-Jul) -----------------------------
    # Synthetic ages throughout: asserts the detector, never today's feed.
    _n = _now()

    def _stamped(age_h, ttl=8 * 3600):
        return {"alerts": [], "ttl_sec": ttl,
                "updated": datetime.fromtimestamp(
                    _n - age_h * 3600, tz=timezone.utc).isoformat()}

    assert synthesize_alerts_feed(_stamped(0.2), _n) == []
    # THE CADENCE TRAP, and the whole reason ALERTS_FRESH_S is 12h: market_context
    # writes this key on the 6-hourly coin-quality tick, so ~6h old IS perfect
    # health. The board's DEFAULT _fresh window is 2700s — had this check used
    # it, the organ would have screamed "feed dark" through every healthy cycle
    # and been muted within a day. A freshness check that fires on cadence is
    # not a health check.
    assert synthesize_alerts_feed(_stamped(5.9), _n) == [], \
        "6h is NORMAL cadence (QUALITY_EVERY_H) — must stay silent"
    _dark = synthesize_alerts_feed(_stamped(9.0), _n)
    assert len(_dark) == 1 and _dark[0]["key"] == "board:alerts-feed-dark" \
        and _dark[0]["severity"] == "warn", _dark
    # the producer's OWN ttl_sec rules, not this module's constant: a feed that
    # declares a tighter cadence is judged by it (min(max_age_s, ttl_sec)).
    assert synthesize_alerts_feed(_stamped(2.0, ttl=3600), _n), \
        "a payload's own 1h ttl must tighten the window"
    # DEPLOY TRANSITION: market-context is a separate service on its own deploy
    # clock. An unstamped payload is the OLD WRITER, not a dead one — info, so
    # the board shows it without paging. This is the exact shape in production
    # right now, and shipping a phone-waking false alarm on deploy is how an
    # alerting organ gets ignored.
    _uns = synthesize_alerts_feed({"alerts": []}, _n)
    assert len(_uns) == 1 and _uns[0]["key"] == "board:alerts-unstamped" \
        and _uns[0]["severity"] == "info", _uns
    assert synthesize_alerts_feed({}, _n)[0]["severity"] == "info"

    # --- notify: a SUSTAINED warn re-pages; a level-triggered item's `trend`
    # is a constant, so `escalated` alone could never fire for board items ----
    assert SEV_W["action"] > SEV_W["warn"] > SEV_W["info"], SEV_W
    assert RENOTIFY_H >= NOTIFY_GAP_H, \
        "the reminder cadence must not undercut the per-key push floor"

    # push: unconfigured -> False, no crash
    os.environ.pop("NTFY_TOPIC", None)
    assert send_push("t", "b") is False
    # ---- [2026-07-30] THE BOOKS' AUTHOR ----------------------------------
    import fleet_tuning as _tn

    class _T:
        LEVERS = _tn.LEVERS
        vals = {}

        @staticmethod
        def get_lever(name, default, now_ts=None):
            return _T.vals.get(name, default)

        @staticmethod
        def clamp(name, value):
            return _tn.clamp(name, value)

    _bnow = 2_000_000.0
    _CB = "perps-funding-carry-lshadow"
    # [2026-07-31 (hs)] `pnl_abs` is REQUIRED on a saturation fixture now: the
    # capacity branch is fail-closed without it. +65.62 is 🌾 carry's real
    # published figure the hour the rule was written, not a round number.
    _sat = [{"bot": _CB, "open_trades": 12, "closed_trades": 80,
             "pnl_abs": 65.62}]

    # SATURATED at the cap -> widen the CAPACITY lever exactly one step
    _T.vals = {}
    lv, it = synthesize_books(_sat, {}, {}, _bnow, tuning_mod=_T)
    assert lv.get("carry.max_positions", {}).get("value") == 14, lv
    assert it and it[0]["direction"] == "expand"

    # BELOW the cap -> say nothing. "Near" is not "at".
    lv, _ = synthesize_books(
        [{"bot": _CB, "open_trades": 11, "closed_trades": 80}], {}, {}, _bnow,
        tuning_mod=_T)
    assert lv == {}, "a book with a free slot is not saturated"

    # HURTING -> never re-assert, even while saturated (restrict-first)
    # NOTE the payload shape: `verdicts`, exactly as fleet_proprioception
    # publishes it and as synthesize_proprioception reads it. A fixture that
    # invents a key would make this assertion prove nothing.
    lv, _ = synthesize_books(_sat, {}, {"verdicts": {
        "carry.max_positions": {"verdict": "hurting"}}}, _bnow, tuning_mod=_T)
    assert lv == {}, "a lever graded hurting must not be widened again"
    # a HELPING verdict must NOT block the widening (symmetry check — an
    # over-broad filter here would freeze the rail permanently)
    lv, _ = synthesize_books(_sat, {}, {"verdicts": {
        "carry.max_positions": {"verdict": "helping"}}}, _bnow, tuning_mod=_T)
    assert lv.get("carry.max_positions", {}).get("value") == 14, \
        "only HURTING blocks; helping must still widen"

    # AT the registry bound -> nothing to say (clamp makes the step a no-op)
    _T.vals = {"carry.max_positions": 20}
    lv, _ = synthesize_books(
        [{"bot": _CB, "open_trades": 20, "closed_trades": 80}], {}, {}, _bnow,
        tuning_mod=_T)
    assert lv == {}, "at the cage bound the author proposes nothing"
    _T.vals = {}

    # STARVED: 0 open AND no new closes for the window -> loosen the GATE
    _prior = {_CB: {"closed": 80, "ts": _bnow - 30 * 3600}}
    lv, _ = synthesize_books([{"bot": _CB, "open_trades": 0,
                               "closed_trades": 80}], _prior, {}, _bnow,
                             tuning_mod=_T)
    assert lv.get("carry.enter_apr", {}).get("value") == 1.4, lv

    # ...but a book that CLOSED something in the window is not starved
    lv, _ = synthesize_books([{"bot": _CB, "open_trades": 0,
                               "closed_trades": 81}], _prior, {}, _bnow,
                             tuning_mod=_T)
    assert lv == {}, "new closes mean the gate is admitting — leave it alone"

    # ...and neither is a book that is merely HOLDING
    lv, _ = synthesize_books([{"bot": _CB, "open_trades": 3,
                               "closed_trades": 80}], _prior, {}, _bnow,
                             tuning_mod=_T)
    assert lv == {}, "a book holding positions is patient, not starved"

    # ...nor one whose window has not elapsed yet
    lv, _ = synthesize_books([{"bot": _CB, "open_trades": 0,
                               "closed_trades": 80}],
                             {_CB: {"closed": 80, "ts": _bnow - 3600}}, {},
                             _bnow, tuning_mod=_T)
    assert lv == {}, "the starvation window must actually elapse"

    # THE PUBLISHED CAP is preferred over the registry's. A book that has not
    # adopted a lever (not redeployed, lever quarantined, TTL lapsed) still
    # gates on ITS number, and judging saturation against a cap the bot never
    # took is how an author talks itself into widening forever.
    _T.vals = {"carry.max_positions": 18}       # registry thinks 18...
    lv, _ = synthesize_books(
        [{"bot": _CB, "open_trades": 12, "closed_trades": 80, "pnl_abs": 65.62,
          "extra": {"caps": {"max_positions": 12}}}],   # ...the BOOK runs 12
        {}, {}, _bnow, tuning_mod=_T)
    assert lv.get("carry.max_positions", {}).get("value") == 20, \
        "saturation must be judged against the cap the BOOK published"
    lv, _ = synthesize_books(
        [{"bot": _CB, "open_trades": 12, "closed_trades": 80, "pnl_abs": 65.62,
          "extra": {"caps": {"max_positions": 18}}}],
        {}, {}, _bnow, tuning_mod=_T)
    assert lv == {}, "published cap 18 with 12 open is NOT saturated"
    _T.vals = {}

    # ---- [2026-07-31 (hs)] SATURATION IS NOT EVIDENCE ---------------------
    # The incident: ⚖️ Counterweight, always-in, saturated on EVERY cycle by
    # construction, ratcheted fundspread.k 5 -> 8 -> 12 (the cage ceiling)
    # while carrying -$27.75. Gross exposure $200 -> $480 on a losing book.
    _SB = "perps-funding-spread-lshadow"

    def _spread(pnl, open_n=24, cap=12):
        row = {"bot": _SB, "open_trades": open_n, "closed_trades": 48,
               "extra": {"caps": {"k": cap}}}
        if pnl is not None:
            row["pnl_abs"] = pnl
        return [row]

    # the measured case: saturated AND losing -> HOLD, and say so
    lv, it = synthesize_books(_spread(-27.75), {}, {}, _bnow, tuning_mod=_T)
    assert lv == {}, "a saturated LOSING book must not be widened"
    _held = [i for i in it if i.get("direction") == "hold"]
    assert _held and _held[0]["lever"] == "fundspread.k", it
    assert _held[0]["severity"] == "info", \
        "the board phone-pushes warn/action; an always-in book trips this " \
        "every cycle, so it must not page"

    # the rule still WORKS — this is a profit term, not a disabled branch
    # NOTE the step comes off the REGISTRY's current value (env_default 8),
    # while SATURATION is judged against the cap the book published (12) —
    # two different sources on purpose, per the block above.
    lv, _ = synthesize_books(_spread(+40.0), {}, {}, _bnow, tuning_mod=_T)
    assert lv.get("fundspread.k", {}).get("value") == 9, lv

    # REALISED-ONLY WOULD HAVE WIDENED IT. Counterweight's realised P&L was
    # +$7.29 against a -$27.75 mark-to-market total. If this rule ever reads a
    # realised field instead of pnl_abs, this assertion is what fails.
    lv, _ = synthesize_books(_spread(-27.75), {}, {}, _bnow, tuning_mod=_T)
    assert "fundspread.k" not in lv, \
        "the term must read MTM pnl_abs, never realised P&L (the (hl) blind spot)"

    # FAIL-CLOSED in the widening direction: no/­unreadable/NaN pnl -> hold
    for _bad in (None, "n/a", float("nan"), True):
        _rows = _spread(0.0)
        if _bad is None:
            _rows[0].pop("pnl_abs")
        else:
            _rows[0]["pnl_abs"] = _bad
        lv, _ = synthesize_books(_rows, {}, {}, _bnow, tuning_mod=_T)
        assert lv == {}, f"unreadable pnl_abs ({_bad!r}) must not widen"
    # exactly break-even is not evidence of a working book either
    lv, _ = synthesize_books(_spread(0.0), {}, {}, _bnow, tuning_mod=_T)
    assert lv == {}, "0.0 is not a profitable book"

    # THE ASYMMETRY IS DELIBERATE: the profit term guards CAPACITY only. A
    # STARVED book holds nothing, so its pnl is ~0 by definition — applying
    # the term there would freeze the branch that exists to unstick a gate
    # admitting nothing.
    lv, _ = synthesize_books(
        [{"bot": _CB, "open_trades": 0, "closed_trades": 80, "pnl_abs": -9.0}],
        {_CB: {"closed": 80, "ts": _bnow - 30 * 3600}}, {}, _bnow, tuning_mod=_T)
    assert lv.get("carry.enter_apr", {}).get("value") == 1.4, \
        "a losing STARVED book must still get its gate loosened"

    # the field is one the PUBLISHER actually emits — not a name invented by
    # whoever wrote this consumer (the (hj) hand-fixture class).
    import inspect as _insp

    import bot_pnl_store as _bps
    assert "pnl_abs" in _insp.signature(_bps.publish).parameters, \
        "pnl_abs must be a real publish() field, or this rule reads nothing"

    # A MISSING ROW proposes nothing. Absence of evidence is not "widen" —
    # this is the guard that stops a publish outage from ratcheting every
    # book wider on every cycle.
    lv, _ = synthesize_books([], _prior, {}, _bnow, tuning_mod=_T)
    assert lv == {}, "no row -> no opinion"
    # a dark rail proposes nothing either
    assert synthesize_books(_sat, {}, {}, _bnow, tuning_mod=None) == ({}, [])

    # every authored lever must be on the books lane and writable by US —
    # a lane/author drift here would be dropped silently by write_levers.
    for _lever in set(list(_tn.LEVERS)) & {
            l for pair in BOOK_AUTHOR.values() for l in pair if l}:
        assert _tn.LEVERS[_lever]["lane"] == "lighter-books", _lever
        assert _tn._author_may_write(_lever, "lighter-books", "evidence-board")

    print("evidence_board selftest OK (+ alerts-feed bloodstream: cadence-safe, "
          "dark=warn, unstamped=info, producer ttl rules; BOOK author: saturate/starve/hurting-refusal/bound/missing-row)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    elif "--once" in sys.argv:
        run_once()
    else:
        while True:
            try:
                run_once()
            except Exception as e:  # noqa: BLE001
                # [2026-08-01 (hw)] printing is NOT reporting — the print goes
                # to a container log nobody tails, which is exactly the silence
                # that hid the learning brain's crash for weeks. Record it on
                # this organ's own key so fleet_immune can see it.
                print(f"[evidence_board] cycle error: {type(e).__name__}: {e}", flush=True)
                try:
                    # (ib) 1-Aug: this read `KEY`, bound nowhere in this file —
                    # the key is `BOARD_KEY` (line 87). The NameError was
                    # swallowed by the `except` below, so (hw)'s whole point
                    # ("printing is NOT reporting") never reached the bus: the
                    # board reported no error it ever hit. Caught by
                    # scripts/audit_undefined_names.py.
                    store.record_organ_error(BOARD_KEY, e)
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(INTERVAL)
