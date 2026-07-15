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
         the resting state. Only lanes in FLEET_TUNING_ENACT_LANES
         (default: paper-scanner — zero trading surface) are enactable;
         trading-book lanes stay proposal-only until a review adds them.

WHAT IT NEVER DOES
  Open positions, raise a stake on a trading book, loosen a live veto, or
  touch real money — go-live and real-money sizing stay operator-only
  (NO_REAL_MONEY unchanged). The growth rail can only move levers that are
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
WINDOW_H = 48          # board horizon — matches the dashboard banner
TTL_SEC = 3 * INTERVAL

SEV_W = {"info": 1.0, "warn": 3.0, "action": 4.0}
DECAY_HALF_LIFE_H = 12.0

# lens-forward ruling floor (agenda item 2) and the "negative at the floor" bar
LENS_FLOOR_N4H = int(os.environ.get("EVBOARD_LENS_FLOOR", "75"))
LENS_NEG_AVG4H = float(os.environ.get("EVBOARD_LENS_NEG_AVG4H", "-0.5"))
STRESS_VETO_BPS = float(os.environ.get("TT_STRESS_VETO_BPS", "15"))
DD_NEAR_TRIP = float(os.environ.get("EVBOARD_DD_NEAR_TRIP", "-0.035"))


def _now():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or _now(), tz=timezone.utc).isoformat(timespec="seconds")


def _fresh(state, max_age_s=2700):
    """A feed is usable if its own `updated` stamp is younger than max_age_s
    (fail-safe: unusable feeds contribute NOTHING — no synthesis, no boost)."""
    try:
        u = datetime.fromisoformat(str(state.get("updated")).replace("Z", "+00:00"))
        return (_now() - u.timestamp()) <= max_age_s
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
            sym = o.get("symbol") if isinstance(o, dict) else (o[0] if isinstance(o, (list, tuple)) and o else o)
            if str(sym).upper() == coin.upper():
                return True
    return False


def synthesize(lighter_market, fleet_risk, lens_forward, prior_keys, now_ts):
    """Board-authored evidence from feed JOINS. Each item fires on condition
    ENTER (not every cycle) — prior_keys is the set of synthesized keys that
    were active last cycle. Returns [{key, severity, msg, proposal, lever}]."""
    out = []

    def emit(key, severity, msg, proposal=None, lever=None):
        out.append({"key": key, "severity": severity, "msg": msg,
                    "proposal": proposal, "lever": lever, "ts": now_ts,
                    "source": "board"})

    lm_ok = _fresh(lighter_market or {})
    fr_ok = _fresh(fleet_risk or {})
    lf = (lens_forward or {}).get("lenses") or {}

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


def widen_step(quiet_hours):
    """(step, merged_levers) for a census this many hours quiet. Monotone;
    later steps inherit (and may override) earlier steps' levers."""
    step, levers = 0, {}
    for i, (bar, lv) in enumerate(WIDEN_LADDER, 1):
        if quiet_hours >= bar:
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
# time). Sizing UP must be EARNED — every live row over the closed-trade
# floor AND net positive, fleet light green, drawdown shallow, venue calm —
# one ladder step per cooldown, TTL auto-revert to 1.0 the moment the board
# stops re-asserting. Sizing DOWN fires immediately on a hurt live row or a
# live-vs-shadow divergence alert. Every change pushes URGENT to the phone.
# ---------------------------------------------------------------------------
LIVE_ROWS = {s.strip() for s in os.environ.get(
    "EVBOARD_LIVE_ROWS",
    "crypto-trend-daily-lighter,perps-funding-lighter-lighter").split(",") if s.strip()}
LIVE_MIN_CLOSED = int(os.environ.get("EVBOARD_LIVE_MIN_CLOSED", "30"))
LIVE_DOWN_PNL = float(os.environ.get("EVBOARD_LIVE_DOWN_PNL", "10"))     # -$10 hurts
LIVE_DOWN_SCALE = float(os.environ.get("EVBOARD_LIVE_DOWN_SCALE", "0.75"))
LIVE_DD_MIN = float(os.environ.get("EVBOARD_LIVE_DD_MIN", "-0.02"))      # 7d fleet dd
LIVE_STEP_COOLDOWN_H = float(os.environ.get("EVBOARD_LIVE_COOLDOWN_H", "24"))
LIVE_LADDER = [1.0, 1.25, 1.5]
# A divergence alert only cuts LIVE size if it is CURRENT. The window was
# 48h, which let a 39h-old fossil from the RETIRED whole-book ratio check
# (the diagnosed "+5.4%" artifact) cut real money on 15-Jul. A genuine
# execution divergence re-fires within market_context's cadence, so the
# reflex trusts only a fresh alert — stale/retired signals age out.
LIVE_GAP_FRESH_H = float(os.environ.get("EVBOARD_LIVE_GAP_FRESH_H", "6"))


def synthesize_live(bot_rows, fleet_risk, lighter_market, alerts,
                    prior_scale, now_ts):
    """The live lane's decision. Returns (desired_scale | None, item | None).
    None = assert nothing (the lever expires back to 1.0 on its own).
    prior_scale: {"value", "ts"} from the previous board payload — the
    up-ladder's cooldown memory. Pure — selftested offline."""
    rows = {str(r.get("bot")): r for r in (bot_rows or [])
            if str(r.get("bot")) in LIVE_ROWS}
    if not LIVE_ROWS or len(rows) < len(LIVE_ROWS):
        return None, None                    # can't see the whole live cohort

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
    gap = any(str(a.get("key", "")).startswith("live-shadow-gap")
              and (a.get("ts") or 0) >= now_ts - LIVE_GAP_FRESH_H * 3600
              for a in alerts or [])
    hurt = [b for b, r in sorted(rows.items())
            if float(r.get("pnl_abs") or 0) <= -LIVE_DOWN_PNL]
    if gap or hurt:
        why = " ; ".join((["live-vs-shadow divergence alert"] if gap else [])
                         + [f"{b} ${float(rows[b].get('pnl_abs') or 0):+.2f}"
                            for b in hurt])
        return LIVE_DOWN_SCALE, emit(LIVE_DOWN_SCALE, "action", "restrict", why)

    # UP must be earned on every gate at once.
    fr_ok = (_fresh(fleet_risk or {})
             and str(fleet_risk.get("light")) == "green"
             and (fleet_risk.get("fleet_dd_7d") is None
                  or float(fleet_risk.get("fleet_dd_7d")) > LIVE_DD_MIN))
    med = ((lighter_market or {}).get("stress") or {}).get("med")
    lm_ok = (_fresh(lighter_market or {}) and med is not None
             and med * 2 <= STRESS_VETO_BPS)
    earned = all(int(r.get("closed_trades") or 0) >= LIVE_MIN_CLOSED
                 and float(r.get("pnl_abs") or 0) > 0 for r in rows.values())
    if not (fr_ok and lm_ok and earned):
        return None, None                    # lever expires -> 1.0

    cur = float((prior_scale or {}).get("value") or 1.0)
    since = float((prior_scale or {}).get("ts") or 0)
    nxt = next((v for v in LIVE_LADDER if v > cur + 1e-9), cur)
    if cur > 1.0 and now_ts - since < LIVE_STEP_COOLDOWN_H * 3600:
        nxt = cur                            # hold this step through cooldown
    if nxt <= 1.0:
        return None, None
    why = (f"EARNED: every live row ≥{LIVE_MIN_CLOSED} closes & net positive, "
           f"fleet green, dd>{LIVE_DD_MIN:.0%}, venue calm ({med}bps)")
    return nxt, emit(nxt, "action", "expand", why)


def synthesize_expand(lens_fwd, tuner_state, bot_rows, lighter_market, now_ts,
                      xp_state=None):
    """Board-authored EXPAND evidence. Same emit shape as synthesize(), every
    item carrying direction='expand'. Pure — selftested offline."""
    out = []

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
            emit(f"board:promotion-watch:{bot}",
                 f"🚀 {bot}: n={closed} closed, ${pnl:+.2f} — passes the "
                 f"provisional expectancy screen (n≥{PROMO_MIN_CLOSED}, "
                 f"≥${PROMO_MIN_PNL:g})",
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

    fa = (store.load_state("fleet-alerts") or {}).get("alerts") or []
    review = store.load_state("evidence-review") or {}
    lm = store.load_state("lighter-market") or {}
    fr = store.load_state("fleet-risk") or {}
    lf = store.load_state("brain-lens-forward") or {}

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

    # ---- synthesized evidence (condition-ENTER only) -----------------------
    prior_synth = {k for k in prior_items if k.startswith("board:")}
    synth = synthesize(lm, fr, lf, prior_synth, now) + detect_veto_flap(fa, now)

    # ---- EXPAND-direction synthesis: winners, promotions, tuner activity,
    # and restrictions that never bind (the board's other eye) --------------
    tuner_state = store.load_state("scout-tuner") or {}
    xp_state = store.load_state("xp-judge") or {}
    bot_rows = []
    try:
        bot_rows = store.fetch_bot_pnl() or []
    except Exception:
        bot_rows = []
    synth += synthesize_expand((lf.get("lenses") or {}) if _fresh(lf, 26000) else {},
                               tuner_state, bot_rows, lm, now, xp_state)

    # ---- LIVE lane 💰: evidence-gated clip scaling on the real-money bots --
    prior_live = prior.get("live_scale") or {}
    desired_live, live_item = synthesize_live(bot_rows, fr, lm, fa, prior_live, now)
    if live_item:
        synth.append(live_item)

    # ---- growth rail: widen Gap Scout's net when its census runs quiet -----
    census = store.load_state("gapscout-census") or {}
    growth_step, growth_levers, quiet_h = 0, {}, 0.0
    if _fresh(census, max_age_s=3600):
        quiet_h = float(census.get("quiet_hours") or 0.0)
        growth_step, growth_levers = widen_step(quiet_h)
        if growth_step:
            synth.append({
                "key": "board:gapscout-quiet", "severity": "info",
                "msg": f"🌱 Gap Scout census quiet {quiet_h:.0f}h — detection "
                       f"net widened to step {growth_step}/{len(WIDEN_LADDER)}",
                "proposal": "widen (ENACTED via fleet_tuning): " + ", ".join(
                    f"{k}={v}" for k, v in sorted(growth_levers.items())),
                "lever": "growth-rail", "direction": "expand",
                "ts": now, "source": "board"})
    synth_new = [s for s in synth if s["key"] not in prior_synth]

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
            "first_seen": prior_items.get(k, {}).get("first_seen") or _iso(a.get("ts")),
            "verdict": v,
        })
    for s in synth:
        k = s["key"]
        auto_map[k] = "active"
        items.append({
            "key": k, "msg": s["msg"], "sev": s["severity"],
            "score": score_item(s["severity"], 0.0, 1, True),
            "fires_24h": 1, "trend": "steady", "source": "board",
            "first_seen": prior_items.get(k, {}).get("first_seen") or _iso(now),
            "verdict": "active", "proposal": s.get("proposal"), "lever": s.get("lever"),
            "direction": s.get("direction", "restrict"),
        })

    merged = merge_verdicts(review.get("verdicts"), auto_map)
    for i in items:
        i["verdict"] = merged.get(i["key"], i["verdict"])
    items.sort(key=lambda i: -i["score"])

    proposals = [{"key": s["key"], "lever": s["lever"], "proposal": s["proposal"],
                  "direction": s.get("direction", "restrict"),
                  "mode": "enact" if s.get("direction") == "expand" else MODE}
                 for s in synth if s.get("proposal")]

    # ---- enact: ONE combined write per cycle (merge semantics keep other
    # authors' levers; the board's own set must arrive together) -------------
    board_levers = {}
    if growth_levers:
        board_levers.update(
            {k: {"value": v,
                 "reason": f"census quiet {quiet_h:.0f}h -> widen step {growth_step}",
                 "evidence": f"gapscout-census {census.get('updated')}: "
                             f"episodes_open={census.get('episodes_open')}, "
                             f"day={json.dumps(census.get('day'))}"}
             for k, v in growth_levers.items()})
    if desired_live is not None:
        board_levers["live.clip_scale"] = {
            "value": desired_live,
            "reason": (live_item or {}).get("msg", "")[:180],
            "evidence": f"live rows {sorted(LIVE_ROWS)}; gates in synthesize_live"}
    enacted = None
    if board_levers and tuning is not None:
        enacted = tuning.write_levers(board_levers, set_by="evidence-board",
                                      now_ts=now)
    prior_step = int(prior.get("growth_step") or 0)
    if growth_step > prior_step and enacted:
        send_push(f"growth rail: Gap Scout net -> step {growth_step}",
                  f"census quiet {quiet_h:.0f}h; enacted: " + ", ".join(
                      f"{k}={v['value']}" for k, v in enacted["levers"].items()),
                  priority="default", tags="seedling")
        print(f"[evidence_board] growth rail ENACTED step {growth_step}: "
              f"{sorted(enacted['levers'])}", flush=True)
    # live changes always reach the phone URGENT — it's real money
    prior_live_val = prior_live.get("value")
    if desired_live != prior_live_val and (desired_live is not None
                                           or prior_live_val is not None):
        send_push("LIVE clips " + (f"x{desired_live:g}" if desired_live
                                   else "back to x1.0 (lever released)"),
                  (live_item or {}).get("msg")
                  or "conditions no longer hold — expires to operator sizing",
                  priority="urgent", tags="moneybag")
        print(f"[evidence_board] LIVE clip_scale: {prior_live_val} -> "
              f"{desired_live}", flush=True)

    # ---- notify: NEW warn/action items AND new EXPAND items — good news
    # reaches the phone with the same machinery as warnings (default
    # priority, seedling tag; missing the cream is also a miss) -------------
    # Items with a DEDICATED push above (live clip scale, growth-rail step)
    # are skipped here so they aren't double-sent — and, critically, so an
    # ENACTED live action is never mislabeled "Proposed (shadow)" by the
    # generic template (the 15-Jul confusing push).
    DEDICATED_PUSH = {"board:live-clip-scale", "board:gapscout-quiet"}
    for i in items:
        if i["key"] in DEDICATED_PUSH:
            continue
        is_expand = i.get("direction") == "expand"
        if i["verdict"] != "active":
            continue
        if i["sev"] not in ("warn", "action") and not is_expand:
            continue
        is_new = i["key"] not in prior_items or (i["key"] in {s["key"] for s in synth_new})
        escalated = i["trend"] == "escalating" and prior_items.get(i["key"], {}).get("trend") != "escalating"
        last_n = notified.get(i["key"], 0)
        if (is_new or escalated) and now - last_n >= NOTIFY_GAP_H * 3600:
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

    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC, "mode": MODE,
        "items": items[:20],
        "proposals": proposals,
        "growth_step": growth_step,
        "live_scale": ({"value": desired_live,
                        "ts": (prior_live.get("ts") if desired_live == prior_live_val
                               else now)}
                       if desired_live is not None else None),
        "enacted": ({k: v["value"] for k, v in enacted["levers"].items()
                     if v.get("set_by") == "evidence-board"}
                    if enacted else None),
        "notified": {k: v for k, v in notified.items() if now - v < 7 * 86400},
        "inputs_fresh": {"lighter_market": _fresh(lm), "fleet_risk": _fresh(fr),
                         "lens_forward": bool(lf),
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
    lf = {"lenses": {"momentum": {"n4h": 90, "hit4h": 0.37, "avg4h_pct": -1.05},
                     "dip": {"n4h": 2, "hit4h": 0.0, "avg4h_pct": -0.6}}}
    keys = {s["key"] for s in synthesize(lm, fr, lf, set(), _now())}
    assert keys == {"board:venue-stress", "board:governor-near-trip", "board:budget-crowding",
                    "board:lens-floor:momentum", "board:lens-negative:momentum"}, keys
    assert synthesize({"updated": "2020-01-01T00:00:00+00:00", "stress": {"med": 99}},
                      {}, {}, set(), _now()) == []
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

    # LIVE lane: earn-up ladder + cooldown, instant down, fail-safe absent
    nowts = _now()
    fresh_fr = {"updated": fresh, "ttl_sec": 900, "light": "green",
                "fleet_dd_7d": -0.005}
    calm_lm = {"updated": fresh, "stress": {"med": 5}}
    live_ok = [{"bot": "crypto-trend-daily-lighter", "closed_trades": 40,
                "pnl_abs": 12.0},
               {"bot": "perps-funding-lighter-lighter", "closed_trades": 33,
                "pnl_abs": 4.0}]
    s, it = synthesize_live(live_ok, fresh_fr, calm_lm, [], {}, nowts)
    assert s == 1.25 and it["direction"] == "expand" and it["severity"] == "action"
    s2, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.25, "ts": nowts - 3600}, nowts)
    assert s2 == 1.25, "cooldown must hold the step"
    s3, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.25, "ts": nowts - 25 * 3600}, nowts)
    assert s3 == 1.5, "past cooldown -> next step"
    s4, _ = synthesize_live(live_ok, fresh_fr, calm_lm, [],
                            {"value": 1.5, "ts": nowts - 25 * 3600}, nowts)
    assert s4 == 1.5, "ladder top is the ceiling"
    live_hurt = [dict(live_ok[0], pnl_abs=-15.0), live_ok[1]]
    s5, it5 = synthesize_live(live_hurt, fresh_fr, calm_lm, [],
                              {"value": 1.5, "ts": 0}, nowts)
    assert s5 == 0.75 and it5["direction"] == "restrict" and it5["severity"] == "action"
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
    live_small = [dict(live_ok[0], closed_trades=5), live_ok[1]]
    assert synthesize_live(live_small, fresh_fr, calm_lm, [], {}, nowts) == (None, None)
    assert synthesize_live(live_ok, dict(fresh_fr, light="red"), calm_lm,
                           [], {}, nowts) == (None, None)
    assert synthesize_live(live_ok, fresh_fr,
                           {"updated": fresh, "stress": {"med": 20}},
                           [], {}, nowts) == (None, None), "hot venue blocks up"
    assert synthesize_live(live_ok[:1], fresh_fr, calm_lm, [], {}, nowts) == (None, None)
    if tuning is not None:
        for v in LIVE_LADDER + [LIVE_DOWN_SCALE]:
            assert tuning.clamp("live.clip_scale", v) == v

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
    # every ladder value must be registered AND in-bounds in fleet_tuning —
    # a ladder entry that would be clamped/dropped is a config bug HERE.
    if tuning is not None:
        for _, lv in WIDEN_LADDER:
            for k, v in lv.items():
                assert tuning.clamp(k, v) == v, f"ladder lever out of registry bounds: {k}={v}"
    # push: unconfigured -> False, no crash
    os.environ.pop("NTFY_TOPIC", None)
    assert send_push("t", "b") is False
    print("evidence_board selftest OK")


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
                print(f"[evidence_board] cycle error: {type(e).__name__}: {e}", flush=True)
            time.sleep(INTERVAL)
