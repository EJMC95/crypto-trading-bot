#!/usr/bin/env python3
"""
fleet_agronomy.py — 🌱 the PER-BOOK conditions scanner.

WHY (2026-07-22, operator: "we've been focusing so much on real estate, not
enough on good sunlight, water and putting the right plants where they belong.
attach an appropriate scanner to each bot, like in parliament").

The fleet keeps ADDING books instead of measuring whether each existing book
has the conditions it needs to express an edge. Parliament already runs a
per-book scanner bench (parliament/scanners.py); nothing else does — and
Parliament's bench scans the MARKET ("what is the venue doing"), not the BOOK
("does this plant have light and water"). This organ scans the BOOKS.

SCOPE — what this does NOT duplicate (say it out loud or a reviewer will
rightly call it a second copy of an existing organ):
  • fleet_proprioception grades levers that MOVED. This grades levers that
    CANNOT move — an inert lever generates zero episodes, so proprioception's
    silence there is indistinguishable from health (the sniper's watching:201
    failure). It also covers knobs with NO lever at all, which are outside
    proprioception's universe by construction.
  • fleet_risk measures OPEN-position concentration (1/HHI, per-symbol pileup).
    This measures REALISED loss/gain concentration on CLOSED trades, counted in
    EPISODES. Different axis, different question.
  • lighter_scout_tuner / parliament.tuners treat starvation as a WIDENING
    TRIGGER per lens / per PM book. This measures whether a BOOK can ever reach
    the gate it must clear. A measurement, not a widening.
  • evidence_board emits ONE hardcoded "restriction that can't bind" item
    (stress-headroom). This generalises that shape over the whole lever
    registry.

PUBLISH-ONLY. It enacts nothing, proposes nothing, and never raises into a
trading loop. It is a thermometer, not a treatment — wiring a consumer is a
review decision, not this organ's.

THE EIGHT CLASSES it covers (7 measured on 2026-07-22 + the unmeasured-fill
fraction the build brief asked for explicitly):
  inert_lever · unlevered_knob · unwired_consumer · concentration ·
  realised_vs_graded · memory_only_guard · evidence_starvation · unmeasured_fill

METRIC DOCTRINE (hard-won, applied here, not softened):
  • rank on the LOWER bound, never the point estimate
  • count EPISODES, not trades — re-entries into one stuck position are ONE
  • report the t-stat at ZERO cost so edge-blocked vs cost-blocked is legible
  • both-halves is TOOTHLESS on this single-regime tape; not used as a bar
  • a metric that reads healthy under TOTAL failure of its own mechanism is not
    a health check. Every check here has a named dark-guard, and `dark` is a
    TOP-LEVEL payload list — never folded into findings, never rendered as a
    verdict.
  • insufficient-n is reported as insufficient, with the n, not as a number.

Read-only on Postgres. CAN publish bot_state 'fleet-agronomy' (+ history), but
ONLY with an explicit --publish flag.

NOT WIRED (2026-07-22): this organ is not in run_all.sh, has no COPY in any
Dockerfile, and has no consumer. It is a thermometer sitting on the bench —
run it by hand. (An earlier draft of this docstring claimed "run_all.sh loops
it", which was never true; wiring it in is a review decision, and doing so
means adding the loop, the COPY, and a --publish flag together.)

--selftest is OFFLINE (no net, no DB) and is mutation-tested: break a guard,
the suite must go red.
"""
import fnmatch
import json
import math
import os
import re
import statistics
import sys
from datetime import datetime, timezone

try:
    import bot_pnl_store as store          # guarded publisher (no-op w/o DB)
except Exception:                          # noqa: BLE001
    store = None

try:
    import fleet_tuning as tuning          # the lever REGISTRY (bounds)
except Exception:                          # noqa: BLE001
    tuning = None

KEY = "fleet-agronomy"
INTERVAL_SEC = int(os.environ.get("AGRONOMY_INTERVAL_SEC", "1800"))
TTL_SEC = int(os.environ.get("AGRONOMY_TTL_SEC", str(3 * 1800)))
WINDOW_D = float(os.environ.get("AGRONOMY_WINDOW_D", "7"))
ORDER_WINDOW_D = float(os.environ.get("AGRONOMY_ORDER_WINDOW_D", "30"))
MAX_FINDINGS = int(os.environ.get("AGRONOMY_MAX_FINDINGS", "60"))

# The go-live screen every book must eventually clear (pnl_dashboard.py:3524-27).
GATE_MIN_TRADES_30D = 20
GATE_MIN_AGE_DAYS = 30

# ---------------------------------------------------------------------------
# floors — each one is the n below which the statistic is a story, not a number
# ---------------------------------------------------------------------------
F_LEVER_Q_MIN = 200          # observations before a distribution is describable
F_LEVER_SNAPS = 24           # distinct snapshots (one scan is not a tape)
F_KNOB_ATTR_N = 5            # closes before a knob gets a P&L share headline
F_KNOB_CLOSES = 10           # closes before gross_loss is a usable denominator
F_CONC_EPISODES = 8          # episodes before HHI means anything
F_CONC_SYMBOLS = 3           # symbols — a 1-symbol book has HHI 1.0 by identity
F_CONC_SUPPORT = 2           # episodes behind the top symbol to name a mechanism
F_CONC_USD = 3.0             # matches PROP_HURT_USD; one fill swings ~$3.50
F_REALISED_N = 20            # closes for a realised per-lens mean
F_GRADED_N = 75              # TT_LENS_VETO_MIN_N — the brain's own ruling floor
F_SLIP_N = 20                # orders before a slippage median exists
F_GUARD_EVENTS = 3           # guard firings before a violation RATE
F_EVID_SD_N = 10             # closes before sd (and therefore t) is estimable
F_CADENCE_SPAN_D = 3.0       # days of history before a cadence may be projected

# thresholds — measured, not invented (see the per-check docstrings)
T_STEP_SHARE = 0.50          # one cliff carrying half the swing = degenerate
T_SWING_INERT = 0.05         # <5pp of the gated population moves = inert
T_SATURATED = 0.90           # admits >=90% at BOTH ends = cannot restrict
T_COARSE_R = 10              # <=10 reachable admitted-sets across the bound
T_KNOB_SHARE = 0.25          # uniform share over 4 exit reasons IS 0.25
T_CONC_SHARE = 0.40          # >2x uniform at 3+ symbols
T_ECHO_FRAC = 0.90           # px_fill == px_decision on 90%+ = sensor unplugged
T_STARVE_DAYS = 180.0        # days-to-power beyond which the book is starved
T_SLOW_DAYS = 90.0

TAKER_FEE_FRAC = float(os.environ.get("AGRONOMY_TAKER_FEE", "0.00045"))

SEV_RANK = {"info": 0, "warn": 1, "action": 2}

# The eight classes. A check may emit several; every class must have an owner —
# `--selftest` asserts CLASS_OWNER is total over KLASSES, so a class cannot be
# silently dropped by deleting the code that finds it.
KLASSES = (
    "inert_lever", "unlevered_knob", "unwired_consumer", "concentration",
    "realised_vs_graded", "memory_only_guard", "evidence_starvation",
    "unmeasured_fill",
)
CLASS_OWNER = {
    "inert_lever": "lever_authority",
    "unlevered_knob": "lever_authority",
    "unwired_consumer": "signals",
    "concentration": "concentration",
    "realised_vs_graded": "execution",
    "unmeasured_fill": "execution",
    "memory_only_guard": "guards",
    "evidence_starvation": "evidence",
}

# ---------------------------------------------------------------------------
# SIGNALS — the fleet-wide RESTRICT-ONLY safety keys. "Should consume" is not a
# taste judgement: these are published fleet-wide, are restrict-only (reading
# one can only ever make a book trade LESS), and their stated scope is every
# book that takes a position. A book that never names the key cannot be reading
# it — that direction of the inference is sound. The other direction is not:
# a reference can exist and never be reached (FLEET_RISK_MODE, ENACT_LANES,
# coin-vetoes — three instances), so a present reference is reported as
# REFERENCED, never as "wired", and carries verified=False.
# ---------------------------------------------------------------------------
SIGNALS = {
    "fleet-risk": "L2 traffic light + long-budget veto + DD governor",
    "coin-vetoes": "measured per-coin stop-rate / slippage veto",
    "brain-lens-forward": "counterfactual lens grades (restrict-only veto)",
}


class QSpec:
    """How a lever's UNITS map onto the tape's units, and which way it gates.

    This is the seam the 8x funding-basis bug lived in: `live.funding.enter_apr`
    is a FRACTION (0.03125-0.075) and the scout tape's `funding` map is apr_pct
    (3.125-7.5). Comparing them raw reports admit=100% forever — a green light
    from a unit error. `to_q` is mandatory and the selftest asserts it applied.
    """

    def __init__(self, source, field, unit, to_q, direction, use_abs=False,
                 lens=None, precision=None):
        self.source = source        # 'funding' | 'ticket' | 'ledger_hold'
        self.field = field
        self.unit = unit
        self.to_q = to_q            # lever units -> quantity units
        self.direction = direction  # 'ge' (admit q >= x) | 'le'
        self.use_abs = use_abs
        self.lens = lens
        self.precision = precision  # tape rounding, in quantity units


_X100 = (lambda v: v * 100.0)
_ID = (lambda v: v)

LEVER_Q = {
    "live.funding.enter_apr": QSpec("funding", None, "apr_pct", _X100, "ge",
                                    use_abs=True, precision=0.1),
    "xp.funding.enter_apr": QSpec("funding", None, "apr_pct", _X100, "ge",
                                  use_abs=True, precision=0.1),
    "taker.div_gap_pp": QSpec("ticket", "gap_pct", "pp", _ID, "ge",
                              use_abs=True, lens="divergence"),
    "taker.brk_range": QSpec("ticket", "range_pos", "frac", _ID, "ge",
                             lens="breakout"),
    "taker.dip_range": QSpec("ticket", "range_pos", "frac", _ID, "le",
                             lens="dip"),
    "taker.momo_chg": QSpec("ticket", "chg_pct", "pct", _ID, "ge",
                            use_abs=True, lens="momentum"),
    "taker.max_hold_h": QSpec("ledger_hold", None, "hours", _ID, "ge"),
    "xp.funding.max_hold_h": QSpec("ledger_hold", None, "hours", _ID, "ge"),
    "live.funding.max_hold_h": QSpec("ledger_hold", None, "hours", _ID, "ge"),
}
# Levers whose gating quantity is NOT observable from anything the fleet
# records (a TP bar gates on the maximum favourable excursion; nothing logs
# MFE). Declared, so they read `unmeasurable` — never `healthy`.
UNMEASURABLE_LEVERS = {
    "taker.tp", "taker.sl", "taker.sl_cooldown_h",
    "live.funding.take_profit", "xp.funding.take_profit",
    "scout.ticket_top_n", "scout.brk_range_min", "scout.dip_range_max",
    "scout.div_gap_pp", "scout.momo_chg_min",
    "evsent.min_sources", "evsent.severity_bar",
    "gapscout.prefilter_gap", "gapscout.max_book_fetches",
    "gapscout.extra_exchanges",
}


class Guard:
    """A book's own re-entry rule, and the durable key that must survive a boot.

    `state_key` is what must appear in the book's PUBLISHED state payload. The
    probe is deliberately RUNTIME, not a source read: a code review already
    missed this class once, and source is not what runs.

    `duration_h=None` means the guard is NOT a time window — Snap Back's
    non-convergence quarantine releases when |dev| falls below EXIT_BPS, a
    condition, not a clock. The behavioural probe is then SKIPPED rather than
    run against an invented duration: a violation count measured against a
    number nobody measured is the exact failure mode this organ exists to find.
    Every duration below is read out of the book's own source, and the source
    line is named.

    `basis` is which two timestamps the window spans, and it is NOT cosmetic:
    the Farmer/taker/family cooldowns are armed at CLOSE (close -> next open),
    while Parliament's is armed at ENTRY (`self.last_entry[sym] = now` at
    strategies.py:381, tested at :289), so it spans open -> next open.
    Measuring an entry-to-entry rule from the close over-reports every leak by
    the hold time — a violation count that is really a hold-duration
    measurement in disguise.
    """

    def __init__(self, name, event_glob, duration_h, state_key, state_of=None,
                 source="", basis="close_to_open"):
        self.name = name
        self.event_glob = event_glob
        self.duration_h = None if duration_h is None else float(duration_h)
        self.state_key = state_key
        self.state_of = state_of    # bot_state key holding it (default: row's)
        self.source = source        # where the duration was READ from
        self.basis = basis          # 'close_to_open' | 'open_to_open'


class BookSpec:
    def __init__(self, row, module, live=False, state_key=None, knob_floor=0,
                 levers=(), knob_reasons=None, guards=(), expects=(),
                 cooldown_min=0.0, order_usd=None, notional_cap=None,
                 gate_trades_30d=GATE_MIN_TRADES_30D, note="",
                 private_levers=False):
        self.row = row
        self.module = module
        self.live = bool(live)
        self.state_key = state_key or row
        self.knob_floor = int(knob_floor)
        self.levers = tuple(levers)
        self.knob_reasons = dict(knob_reasons or {})
        self.guards = tuple(guards)
        self.expects = tuple(expects or SIGNALS.keys())
        self.cooldown_min = float(cooldown_min)
        self.order_usd = order_usd
        self.notional_cap = notional_cap
        self.gate_trades_30d = int(gate_trades_30d)
        self.note = note
        self.private_levers = bool(private_levers)


_FAMILY_REASONS = {
    "STOPLOSS": ["*_trailing_stop_loss", "*_stop_loss"],
    "ROI": ["*_roi", "*_range_top", "*_sell_into_strength"],
}
# cooldown_candles * timeframe, per carrier — READ from lighter_family_bot.py
# (protections at :435 TrendMomo cd1, :461 MomoBreakout cd1, :509 SwingDip cd1,
# :545 DayTraderGated cd4; carriers wired at :635-647), applied on EVERY close
# (:778 `self.cooldown[coin] = now + cooldown_candles * tf_s`), not just stops.
_FAMILY_COOLDOWN_H = {
    "freqtrade-mum-lshadow": 24.0,           # TrendMomo   1d  x1
    "freqtrade-dad-lshadow": 4.0,            # MomoBreakout 4h x1
    "freqtrade-avo-maria-lshadow": 4.0,      # SwingDip    4h  x1
    "freqtrade-georgia-lshadow": 1.0,        # DayTrader  15m  x4
    "crypto-intraday-15m-lshadow": 4.0,      # DayTrader   1h  x4
    "crypto-swing-daily-lshadow": 24.0,      # SwingDip    1d  x1
    "crypto-breakout-4h-lshadow": 4.0,       # MomoBreakout 4h x1
}
_PM_GUARD = (Guard("coin_cooldown", "*", 1.0, "last_entry",
                   source="parliament/strategies.py:64 "
                          "PARL_COIN_COOLDOWN_SEC=3600, armed at :381 on ENTRY,"
                          " tested at :289",
                   basis="open_to_open"),)


def _family(row):
    return BookSpec(
        row, "lighter_family_bot.py", knob_floor=3,
        knob_reasons=_FAMILY_REASONS,
        guards=(Guard("cooldown", "*", _FAMILY_COOLDOWN_H[row], "cooldown",
                      source="lighter_family_bot.py:778 cooldown_candles x tf"),),
        expects=("fleet-risk", "coin-vetoes"),
        cooldown_min=_FAMILY_COOLDOWN_H[row] * 60.0,
        note="7 books in ONE process; sizing modulated by brain mults + "
             "pulse panic, but ZERO fleet_tuning levers")


def _pm(row, lens):
    return BookSpec(
        row, "parliament/strategies.py", knob_floor=5,
        knob_reasons={"SL_PCT": ["*_sl"], "TP_PCT": ["*_tp"],
                      "MAX_HOLD_HR": ["*_hold", "*_fade", "*_conv"]},
        guards=_PM_GUARD, expects=("fleet-risk", "coin-vetoes"),
        cooldown_min=60.0, order_usd=25.0, notional_cap=150.0,
        private_levers=True,
        note=f"{lens} lens; tuned by parliament/tuners.py — a PRIVATE registry "
             f"fleet_tuning cannot clamp, fleet_immune cannot quarantine and "
             f"fleet_proprioception cannot grade")


BOOKS = {b.row: b for b in [
    # ---- REAL MONEY --------------------------------------------------------
    BookSpec(
        "perps-funding-lighter-lighter", "lighter_funding_bot.py", live=True,
        state_key="perps-funding-lighter-lighter:live", knob_floor=20,
        levers=("live.funding.enter_apr", "live.funding.take_profit",
                "live.funding.max_hold_h", "live.clip_scale"),
        knob_reasons={"HARD_STOP": ["*_stop"],
                      "EXIT_APR": ["*_decay", "*_flip"],
                      "TAKE_PROFIT": ["*_take_profit"],
                      "MAX_HOLD_H": ["*_max_hold"]},
        guards=(Guard("stop_cooldown", "*_stop", 12.0, "cooldown",
                      source="FUNDING_STOP_COOLDOWN_H default 12"),
                Guard("repeat_stop", "*_stop", 72.0, "stop_hist",
                      source="FUNDING_REPEAT_STOP_COOLDOWN_H default 72")),
        expects=("fleet-risk", "coin-vetoes"),
        cooldown_min=720.0, order_usd=25.0, notional_cap=30.0,
        note="💸 Funding Farmer LIVE"),
    BookSpec(
        "lighter-ticket-taker-lighter", "lighter_ticket_taker.py", live=True,
        state_key="lighter-ticket-taker:live", knob_floor=16,
        levers=("live.clip_scale",),
        knob_reasons={"STOP_LOSS": ["*_sl"], "TAKE_PROFIT": ["*_tp"],
                      "MAX_HOLD_H": ["*_hold"]},
        guards=(Guard("sl_cooldown", "*_sl", 2.0, "sl_block",
                      source="TT_SL_COOLDOWN_H default 2.0"),),
        expects=("fleet-risk", "coin-vetoes", "brain-lens-forward"),
        cooldown_min=120.0, order_usd=15.0, notional_cap=30.0,
        note="🎫 Ticket Taker LIVE, divergence-only. apply_tuning() returns {} "
             "on lighter_live by design — every entry bar, TP, SL, hold and "
             "cooldown on a real-money book is operator-env-only"),
    # ---- SHADOW ------------------------------------------------------------
    BookSpec(
        "perps-funding-lighter-lshadow", "lighter_funding_bot.py",
        knob_floor=20,
        levers=("xp.funding.enter_apr", "xp.funding.take_profit",
                "xp.funding.max_hold_h"),
        knob_reasons={"HARD_STOP": ["*_stop"],
                      "EXIT_APR": ["*_decay", "*_flip"],
                      "TAKE_PROFIT": ["*_take_profit"],
                      "MAX_HOLD_H": ["*_max_hold"]},
        guards=(Guard("stop_cooldown", "*_stop", 12.0, "cooldown",
                      source="FUNDING_STOP_COOLDOWN_H default 12"),
                Guard("repeat_stop", "*_stop", 72.0, "stop_hist",
                      source="FUNDING_REPEAT_STOP_COOLDOWN_H default 72")),
        expects=("fleet-risk", "coin-vetoes"), cooldown_min=720.0,
        note="the judge's EXPERIMENT arm while a candidate runs"),
    BookSpec(
        "lighter-ticket-taker-lshadow", "lighter_ticket_taker.py",
        state_key="lighter-ticket-taker", knob_floor=16,
        levers=("taker.dip_range", "taker.brk_range", "taker.momo_chg",
                "taker.div_gap_pp", "taker.tp", "taker.sl",
                "taker.max_hold_h", "taker.sl_cooldown_h"),
        knob_reasons={"STOP_LOSS": ["*_sl"], "TAKE_PROFIT": ["*_tp"],
                      "MAX_HOLD_H": ["*_hold"]},
        guards=(Guard("sl_cooldown", "*_sl", 2.0, "sl_block",
                      source="TT_SL_COOLDOWN_H default 2.0"),),
        expects=("fleet-risk", "coin-vetoes", "brain-lens-forward"),
        cooldown_min=120.0),
    BookSpec(
        "crypto-trend-daily-lshadow", "lighter_trend_bot.py", knob_floor=5,
        knob_reasons={"CATASTROPHIC_STOP": ["*_catastrophic_stop"]},
        expects=("fleet-risk", "coin-vetoes"),
        note="🌊 Tide Rider shadow. Exit is the death cross only — no TP, no "
             "time stop. CLAUDE.md already exempts it from judging"),
    BookSpec(
        "lighter-dislocation-lshadow", "lighter_dislocation_bot.py",
        knob_floor=9,
        knob_reasons={"HARD_STOP": ["*_stop"], "MAX_HOLD_S": ["*_max_hold"],
                      "EXIT_BPS": ["*_converged"]},
        guards=(Guard("nonconvergence", "*_max_hold", None, "noconv",
                      source="lighter_dislocation_bot.py:430/454 — released by "
                             "|dev| <= EXIT_BPS, NOT by a clock; no duration "
                             "exists to measure a re-entry against"),),
        expects=("fleet-risk", "coin-vetoes"),
        note="🧲 Snap Back. Dockerfile.dislocation COPIES neither "
             "fleet_tuning.py nor fleet_bus.py — the growth rail and the brain "
             "cannot reach this book at all"),
    BookSpec(
        "lighter-perp-sniper-lshadow", "lighter_perp_sniper.py", knob_floor=4,
        knob_reasons={"STOP_LOSS_PCT": ["*_stop*"],
                      "MAX_HOLD_SEC": ["*_max_hold"]},
        expects=("fleet-risk", "coin-vetoes"),
        note="🎯 Perp Sniper. TP/SL/hold are HARDCODED module constants — not "
             "even env-readable. Cadence bounded by Lighter's listing rate"),
    BookSpec(
        "perps-funding-spread-lshadow", "lighter_funding_spread_bot.py",
        knob_floor=5, knob_reasons={"REBALANCE_H": ["*_rebalance"]},
        expects=("fleet-risk", "coin-vetoes"),
        note="⚖️ Counterweight. No stop, no TP, no max-hold by backtest "
             "fidelity — REBALANCE_H alone sets the trade count"),
    BookSpec(
        "perps-funding-carry-lshadow", "funding_carry_bot.py", knob_floor=2,
        knob_reasons={"EXIT_APR": ["*decay*"], "FLIP_GRACE_H": ["*flip*"]},
        expects=("fleet-risk", "coin-vetoes"),
        note="🌾 Yield Harvester — the fleet's most profitable book, and 11 of "
             "its 13 P&L knobs are module constants (not even env-readable)"),
    BookSpec(
        "equities-regime-lshadow", "lighter_index_bot.py", knob_floor=5,
        knob_reasons={"CATASTROPHIC_STOP": ["*_catastrophic_stop"]},
        expects=("fleet-risk", "coin-vetoes"),
        note="📊 Index Rider. Its own header computes 2.3-2.8 switches/YEAR"),
    _family("freqtrade-mum-lshadow"),
    _family("freqtrade-dad-lshadow"),
    _family("freqtrade-avo-maria-lshadow"),
    _family("freqtrade-georgia-lshadow"),
    _family("crypto-intraday-15m-lshadow"),
    _family("crypto-swing-daily-lshadow"),
    _family("crypto-breakout-4h-lshadow"),
    _pm("pm-albanese-lshadow", "trend"),
    _pm("pm-morrison-lshadow", "breakout"),
    _pm("pm-turnbull-lshadow", "meanrev"),
    _pm("pm-abbott-lshadow", "scalp"),
    _pm("pm-rudd-lshadow", "funding"),
    _pm("pm-gillard-lshadow", "disloc"),
]}

# The default may be a literal OR an expression (`str(6 * 3600)`), so it is
# NOT part of the match — requiring a quoted default silently dropped 2 of the
# sniper's 4 knobs, which is a census under-count wearing a clean face.
KNOB_RE = re.compile(
    r'^([A-Z][A-Z0-9_]*)\s*=\s*(?:float|int)\(os\.environ\.get\(\s*'
    r'["\']([A-Z0-9_]+)["\']', re.M)


# =========================================================================== #
# pure helpers — no I/O below this line until build_ctx()
# =========================================================================== #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _sd(xs):
    xs = [x for x in xs if x is not None]
    return statistics.stdev(xs) if len(xs) >= 2 else None


def _t_stat(xs):
    """t of the mean against zero. Reported at ZERO COST elsewhere so
    'edge-blocked' and 'cost-blocked' are distinguishable on the face of it."""
    m, s, n = _mean(xs), _sd(xs), len([x for x in xs if x is not None])
    if m is None or not s or n < 2:
        return None
    return m / (s / math.sqrt(n))


def _ci_hi(xs):
    m, s, n = _mean(xs), _sd(xs), len([x for x in xs if x is not None])
    if m is None or s is None or n < 2:
        return None
    return m + 1.96 * s / math.sqrt(n)


def _ci_lo(xs):
    m, s, n = _mean(xs), _sd(xs), len([x for x in xs if x is not None])
    if m is None or s is None or n < 2:
        return None
    return m - 1.96 * s / math.sqrt(n)


def _r4(x):
    return None if x is None else round(float(x), 4)


def _parse_ts(v):
    """ISO -> epoch seconds, or None. Never raises."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:                       # noqa: BLE001
        return None


def _fresh(payload, now_ts):
    """A payload's OWN updated+ttl_sec contract. Fails CLOSED."""
    if not isinstance(payload, dict):
        return False
    u = _parse_ts(payload.get("updated"))
    ttl = payload.get("ttl_sec")
    if u is None or not ttl:
        return False
    age = now_ts - u
    return 0 <= age <= float(ttl)


def _glob_any(text, globs):
    return any(fnmatch.fnmatch(text or "", g) for g in (globs or ()))


def _finding(check, klass, book, severity, summary, **evidence):
    return {"check": check, "klass": klass, "book": book,
            "severity": severity, "summary": summary,
            "live": bool(BOOKS[book].live) if book in BOOKS else False,
            "evidence": evidence}


def episodes(closes, gap_min):
    """Collapse a book's closes into EPISODES.

    An episode is a maximal run of closes on the SAME symbol where the next
    position opened less than `gap_min` minutes after the previous one closed.
    Eight re-entries into one stuck gap are ONE episode — the mechanism claim
    is denominated in episodes, the exposure claim in trades, and both are
    reported because neither alone is honest.
    """
    by_sym = {}
    for c in closes:
        by_sym.setdefault(c["pair"], []).append(c)
    out = []
    gap_s = float(gap_min) * 60.0
    for sym, rows in by_sym.items():
        rows = sorted(rows, key=lambda r: (r["open_ts"] or 0.0))
        cur = None
        for r in rows:
            if cur is None:
                cur = {"sym": sym, "n": 0, "pnl": 0.0,
                       "first": r["open_ts"], "last": r["close_ts"]}
            elif (r["open_ts"] is None or cur["last"] is None
                  or (r["open_ts"] - cur["last"]) >= gap_s):
                out.append(cur)
                cur = {"sym": sym, "n": 0, "pnl": 0.0,
                       "first": r["open_ts"], "last": r["close_ts"]}
            cur["n"] += 1
            cur["pnl"] += float(r["pnl_abs"] or 0.0)
            cur["last"] = max(cur["last"] or 0.0, r["close_ts"] or 0.0)
        if cur is not None:
            out.append(cur)
    return sorted(out, key=lambda e: e["first"] or 0.0)


def hhi(shares):
    """Herfindahl over a dict {key: magnitude}; returns (hhi, eff_n, top, share)."""
    tot = sum(shares.values())
    if tot <= 0:
        return None, None, None, None
    top = max(shares, key=lambda k: shares[k])
    h = sum((v / tot) ** 2 for v in shares.values())
    return h, (1.0 / h if h else None), top, shares[top] / tot


def cdf_admit(qs, x, direction):
    """Empirical admitted fraction at bar x. Undefined (None) on an empty tape —
    NEVER 0.0. A 0.0 default here makes a dark sensor read as a dead lever."""
    if not qs:
        return None
    if direction == "le":
        return sum(1 for q in qs if q <= x) / len(qs)
    return sum(1 for q in qs if q >= x) / len(qs)


def lever_authority(name, spec, qs, n_snaps, precision=None):
    """Can this lever's REGISTERED BOUND change what the book selects?

    Statistics over the empirical CDF of the gated quantity, evaluated at the
    bound's ends and at every distinct value inside it:
      swing  — pp of the gated population between lo and hi
      R      — count of DISTINCT admitted sets reachable inside the bound
      S      — largest single step / swing   (one cliff carrying the whole range)
      mode   — the modal quantity value, and whether the bound can separate it

    The 0.50 step-share cut is a MEASURED separation, not a guess. On the 2026-
    07-22 tape: taker.div_gap_pp S=0.01, taker.momo_chg S=0.01,
    taker.brk_range S=0.19, taker.dip_range S=0.26 — and
    live.funding.enter_apr S=0.93. 0.50 sits inside an empty gap.
    """
    lo, hi = spec.get("lo"), spec.get("hi")
    q = LEVER_Q.get(name)
    if lo is None or hi is None or q is None:
        return {"verdict": "unmeasurable", "reason": "no quantity mapping"}
    if not qs or n_snaps < F_LEVER_SNAPS or len(qs) < F_LEVER_Q_MIN:
        # DARK, not inert: an empty tape must never be reported as a dead lever.
        return {"verdict": "dark", "n_q": len(qs or []), "n_snaps": n_snaps,
                "reason": f"tape below floor (n_q>={F_LEVER_Q_MIN}, "
                          f"snaps>={F_LEVER_SNAPS})"}
    lo_q, hi_q = q.to_q(lo), q.to_q(hi)
    a_lo, a_hi = cdf_admit(qs, lo_q, q.direction), cdf_admit(qs, hi_q, q.direction)
    inside = sorted({v for v in qs if lo_q <= v <= hi_q})
    fs = [a_lo] + [cdf_admit(qs, v, q.direction) for v in inside] + [a_hi]
    fs = [f for f in fs if f is not None]
    swing = abs(a_lo - a_hi)
    steps = [abs(fs[i + 1] - fs[i]) for i in range(len(fs) - 1)]
    step_share = (max(steps) / swing) if (steps and swing > 0) else 0.0
    reach = len({round(f, 10) for f in fs})
    # modal value and whether the bound can put a bar between it and the rest
    prec = precision or q.precision
    keyed = [round(v / prec) * prec if prec else v for v in qs]
    counts = {}
    for v in keyed:
        counts[v] = counts.get(v, 0) + 1
    mode = max(counts, key=lambda k: counts[k])
    mode_mass = counts[mode] / len(keyed)
    separable = bool(lo_q <= mode <= hi_q)
    # THE DECISIVE VALUE over the FULL support. Moving the bar past a value
    # changes the admitted set by exactly that value's probability mass, so the
    # decisive bar IS the modal value — and `decisive_vs_bound` says how far
    # outside the lever's reach it sits (>1 = above hi for a `ge` lever).
    decisive = mode if mode_mass >= 0.10 else None
    ref = hi_q if q.direction == "ge" else lo_q
    decisive_vs_bound = (decisive / ref) if (decisive is not None and ref) else None
    out = {"bound": [lo, hi], "bound_q": [_r4(lo_q), _r4(hi_q)],
           "unit": q.unit, "n_q": len(qs), "n_snaps": n_snaps,
           "admit_lo": _r4(a_lo), "admit_hi": _r4(a_hi),
           "swing_pp": round(swing * 100.0, 2), "reach": reach,
           "step_share": _r4(step_share), "mode": _r4(mode),
           "mode_mass": _r4(mode_mass), "separable": separable,
           "decisive": _r4(decisive),
           "decisive_vs_bound": _r4(decisive_vs_bound)}
    if swing < T_SWING_INERT:
        out["verdict"] = "inert"
    elif step_share >= T_STEP_SHARE and not separable:
        out["verdict"] = "degenerate"
    elif min(a_lo, a_hi) >= T_SATURATED:
        out["verdict"] = "saturated"
    elif reach <= T_COARSE_R:
        out["verdict"] = "coarse"
    else:
        out["verdict"] = "healthy"
    return out


def clip_authority(spec, order_usd, cap_usd):
    """A multiplier lever gates no distribution; its authority is the set of
    reachable DOWNSTREAM DISCRETE outcomes (how many clips fit under the cap,
    and whether a clip still clears the venue's minimum)."""
    lo, hi = spec.get("lo"), spec.get("hi")
    if lo is None or hi is None or not order_usd or not cap_usd:
        return {"verdict": "dark", "reason": "clip/cap unknown"}
    outs = set()
    steps = 21
    for i in range(steps):
        x = lo + (hi - lo) * i / (steps - 1)
        outs.add((int(cap_usd // max(order_usd * x, 1e-9)), order_usd * x >= 5.0))
    return {"bound": [lo, hi], "order_usd": order_usd, "cap_usd": cap_usd,
            "reach": len(outs), "slots": sorted({o[0] for o in outs}),
            "verdict": "inert" if len(outs) <= 1 else "healthy"}


# --------------------------------------------------------------------------- #
# THE BENCH — six pure checks. Each takes (ctx, spec) and returns findings.
# One failing check never stops the bench (run_bench wraps each).
# --------------------------------------------------------------------------- #
def check_lever_authority(ctx, spec):
    """INERT LEVER + UNLEVERED KNOB."""
    out, card = [], {"levers": {}, "knobs": {}}
    registry = ctx.get("registry") or {}
    if not registry:
        card["dark"] = "lever registry unavailable (fleet_tuning import failed)"
        return out, card

    # --- inert / degenerate levers ----------------------------------------
    for name in spec.levers:
        rspec = registry.get(name)
        if not rspec:
            card["levers"][name] = {"verdict": "unregistered"}
            continue
        if name == "live.clip_scale":
            res = clip_authority(rspec, spec.order_usd, spec.notional_cap)
        elif name in UNMEASURABLE_LEVERS:
            res = {"verdict": "unmeasurable", "bound": [rspec.get("lo"), rspec.get("hi")],
                   "reason": "gating quantity is not recorded anywhere "
                             "(e.g. a TP bar gates on MFE; nothing logs MFE)"}
        else:
            qs, n_snaps = _lever_quantity(ctx, spec, name)
            res = lever_authority(name, rspec, qs, n_snaps)
        card["levers"][name] = res
        if res.get("verdict") in ("inert", "degenerate", "saturated"):
            sev = "action" if spec.live else "warn"
            out.append(_finding(
                "lever_authority", "inert_lever", spec.row, sev,
                f"{name} is {res['verdict']}: its registered bound "
                f"{res.get('bound')} cannot select against the population it "
                f"gates", lever=name, **{k: v for k, v in res.items()
                                          if k != "bound"}))

    # --- unlevered knobs carrying P&L -------------------------------------
    src = (ctx.get("src") or {}).get(spec.module)
    if src is None:
        card["knobs"]["dark"] = f"source not readable: {spec.module}"
        ctx["dark"].append(f"{spec.row}.knobs: source unreadable ({spec.module})")
        return out, card
    knobs = dict((m.group(1), m.group(2)) for m in KNOB_RE.finditer(src))
    if len(knobs) < spec.knob_floor:
        # A parse failure yields ZERO knobs and therefore "0 unlevered knobs" —
        # a perfect score from a total failure. The floor is the dark-guard.
        card["knobs"]["dark"] = (f"parsed {len(knobs)} knobs, floor "
                                 f"{spec.knob_floor} — parse is not trustworthy")
        ctx["dark"].append(f"{spec.row}.knobs: parsed {len(knobs)} < floor "
                           f"{spec.knob_floor}")
        return out, card
    levered = _levered_attrs(src)
    card["knobs"]["n"] = len(knobs)
    card["knobs"]["n_levered"] = sum(1 for k in knobs if k in levered)
    card["knobs"]["unlevered"] = sorted(k for k in knobs if k not in levered)

    closes = ctx["closes"].get(spec.row) or []
    losses = [c for c in closes if (c["pnl_abs"] or 0.0) < 0]
    gross_loss = -sum(c["pnl_abs"] for c in losses) if losses else 0.0
    attributed = 0.0
    hot = []
    for knob, globs in spec.knob_reasons.items():
        if knob not in knobs:
            continue
        rows = [c for c in closes if _glob_any(c["reason"], globs)]
        klosses = [c for c in rows if (c["pnl_abs"] or 0.0) < 0]
        kloss = -sum(c["pnl_abs"] for c in klosses) if klosses else 0.0
        # attribution is computed for EVERY mapped knob, levered or not, so
        # `unattributed_share` means what it says (the reason map has rotted)
        # rather than "this loss belongs to a knob that happens to have a
        # lever" — only the UNLEVERED ones go on to be findings.
        attributed += kloss
        if knob in levered:
            continue
        entry = {"knob": knob, "reasons": list(globs), "n": len(rows),
                 "close_share": _r4(len(rows) / len(closes)) if closes else None,
                 "loss_usd": round(kloss, 3),
                 "loss_share": _r4(kloss / gross_loss) if gross_loss > 0 else None,
                 "gross_loss_usd": round(gross_loss, 3)}
        if len(rows) < F_KNOB_ATTR_N or len(closes) < F_KNOB_CLOSES:
            # structural fact stays reportable; the STATISTIC does not.
            entry["attribution"] = f"insufficient(n={len(rows)})"
            hot.append(entry)
            continue
        share = max(entry["loss_share"] or 0.0, entry["close_share"] or 0.0)
        if share >= T_KNOB_SHARE:
            entry["attribution"] = "hot"
            hot.append(entry)
            sev = "action" if spec.live else "warn"
            out.append(_finding(
                "lever_authority", "unlevered_knob", spec.row, sev,
                f"{knob} has NO lever and carries "
                f"{entry['loss_share'] if entry['loss_share'] is not None else '?'} "
                f"of gross loss (${entry['loss_usd']} of ${gross_loss:.2f}) / "
                f"{entry['close_share']} of closes over n={len(closes)}",
                **entry))
        else:
            entry["attribution"] = "cold"
            hot.append(entry)
    card["knobs"]["attributed"] = hot
    card["knobs"]["gross_loss_usd"] = round(gross_loss, 3)
    card["knobs"]["unattributed_share"] = (
        _r4(1.0 - attributed / gross_loss) if gross_loss > 0 else None)
    return out, card


def _levered_attrs(src):
    """Attribute names reachable by a lever: anything named on a get_lever line
    or inside the module's TUNABLE tuple."""
    hay = "\n".join(ln for ln in src.splitlines() if "get_lever(" in ln)
    m = re.search(r"TUNABLE\s*=\s*\((.*?)\)\s*\n(?=\S|$)", src, re.S)
    if m:
        hay += "\n" + m.group(1)
    return {a for a in set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", hay))}


def _lever_quantity(ctx, spec, name):
    """The distribution the lever gates, in the TAPE's units."""
    q = LEVER_Q.get(name)
    if q is None:
        return [], 0
    if q.source == "funding":
        vals, snaps = [], 0
        for rec in ctx.get("tape") or []:
            f = rec.get("funding")
            if not isinstance(f, dict) or not f:
                continue
            snaps += 1
            for v in f.values():
                try:
                    x = float(v)
                except (TypeError, ValueError):
                    continue
                vals.append(abs(x) if q.use_abs else x)
        return vals, snaps
    if q.source == "ticket":
        vals, snaps = [], 0
        for rec in ctx.get("tape") or []:
            t = (rec.get("tickets") or {}).get(q.lens)
            if not isinstance(t, list):
                continue
            snaps += 1
            for row in t:
                try:
                    x = float(row.get(q.field))
                except (TypeError, ValueError, AttributeError):
                    continue
                vals.append(abs(x) if q.use_abs else x)
        return vals, snaps
    if q.source == "ledger_hold":
        closes = ctx["closes"].get(spec.row) or []
        vals = [(c["close_ts"] - c["open_ts"]) / 3600.0 for c in closes
                if c["close_ts"] and c["open_ts"]]
        # each close is its own observation; snapshots are not the unit here
        return vals, (len(vals) if len(vals) >= F_LEVER_SNAPS else 0)
    return [], 0


def check_concentration(ctx, spec):
    """CONCENTRATION — episode-aware, gains and losses kept APART.

    Losses concentrate and gains spread; pooling the signs hides exactly the
    asymmetry that is the finding. HHI is UNDETERMINED below 3 symbols — a
    one-symbol book scores 1.0 by identity, which is maximum concentration and
    zero information.
    """
    out = {}
    closes = ctx["closes"].get(spec.row) or []
    if not closes:
        return [], {"verdict": "no_closes", "n_trades": 0}
    if any(c["pnl_abs"] is None for c in closes):
        ctx["dark"].append(f"{spec.row}.concentration: pnl_abs NULL on "
                           f"{sum(1 for c in closes if c['pnl_abs'] is None)} rows")
        return [], {"verdict": "dark", "reason": "pnl_abs NULL on some closes"}
    holds = [(c["close_ts"] - c["open_ts"]) / 60.0 for c in closes
             if c["close_ts"] and c["open_ts"]]
    med_hold = statistics.median(holds) if holds else 0.0
    gap = max(spec.cooldown_min, med_hold)
    eps = episodes(closes, gap)
    syms = {}
    for e in eps:
        syms.setdefault(e["sym"], []).append(e["pnl"])
    loss_mag = {s: -sum(p for p in v if p < 0) for s, v in syms.items()}
    gain_mag = {s: sum(p for p in v if p > 0) for s, v in syms.items()}
    loss_mag = {k: v for k, v in loss_mag.items() if v > 0}
    gain_mag = {k: v for k, v in gain_mag.items() if v > 0}
    out = {"episode_gap_min": round(gap, 1), "median_hold_min": round(med_hold, 1),
           "n_trades": len(closes), "n_episodes": len(eps),
           "n_symbols": len(syms)}
    findings = []
    for side, mags in (("loss", loss_mag), ("gain", gain_mag)):
        if len(syms) < F_CONC_SYMBOLS or len(eps) < F_CONC_EPISODES:
            out[side] = {"verdict": "insufficient",
                         "reason": f"episodes={len(eps)} (floor {F_CONC_EPISODES}), "
                                   f"symbols={len(syms)} (floor {F_CONC_SYMBOLS})"}
            continue
        h, eff, top, share = hhi(mags)
        if h is None:
            out[side] = {"verdict": "none", "total_usd": 0.0}
            continue
        support = sum(1 for p in syms[top] if (p < 0 if side == "loss" else p > 0))
        blk = {"hhi": _r4(h), "eff_books": _r4(eff), "top": top,
               "top_share": _r4(share), "top_support_episodes": support,
               "total_usd": round(sum(mags.values()), 3)}
        if share >= T_CONC_SHARE and sum(mags.values()) >= F_CONC_USD:
            if support >= F_CONC_SUPPORT:
                blk["verdict"] = "concentrated"
                if side == "loss":
                    findings.append(_finding(
                        "concentration", "concentration", spec.row,
                        "action" if spec.live else "warn",
                        f"{share:.0%} of realised LOSS sits in {top} "
                        f"(${blk['total_usd']:.2f} total, {support} loss "
                        f"episodes, {len(closes)} trades / {len(eps)} episodes)",
                        side=side, **blk))
            else:
                # the "8 trades were 2 episodes" lesson, made mechanical
                blk["verdict"] = "concentrated_unproven"
                blk["note"] = (f"share clears but only {support} episode(s) "
                               f"support it — exposure, not a mechanism")
        else:
            blk["verdict"] = "diffuse"
        out[side] = blk
    return findings, out


def check_execution(ctx, spec):
    """EXECUTION — measured slippage, the unmeasured-fill fraction, and the
    realised-vs-graded gap.

    THE CONVERGENT-METRIC TRAP THIS EXISTS TO AVOID: both real-money books
    record px_fill == px_decision on nearly every row and 0 non-null
    slippage_bps. A `COALESCE(slippage_bps, px_fill/px_decision-1)` fallback —
    the obvious implementation — scores real money at a PERFECT 0.0 bps. So the
    echo fraction is measured and published as its OWN finding, and mde stays
    null rather than borrowing a fleet-wide constant (slippage is per-BOOK:
    BOT 747.6bps vs SOXL 20.9 on the same book, same day).
    """
    findings = []
    o = (ctx.get("orders") or {}).get(spec.row) or {}
    n = int(o.get("n") or 0)
    n_slip = int(o.get("n_slip") or 0)
    n_echo = int(o.get("n_echo") or 0)
    card = {"orders": n, "orders_with_slippage": n_slip,
            "echo_fills": n_echo,
            "unmeasured_fill_frac": _r4(o.get("echo_frac")),
            "slip_bps_med": _r4(o.get("slip_med")),
            "by_coin": o.get("by_coin") or {}}
    if n == 0:
        card["verdict"] = "no_orders"
    elif n_slip < F_SLIP_N:
        card["verdict"] = "dark"
        card["mde"] = None
        ctx["dark"].append(
            f"{spec.row}.mde: {n_slip} non-null slippage_bps over {n} orders "
            f"(floor {F_SLIP_N}) — no per-book friction, so no honest MDE")
    else:
        card["verdict"] = "measured"
        card["mde"] = _r4(2.0 * float(o["slip_med"]) / 1e4 + 2.0 * TAKER_FEE_FRAC)
    if n >= F_SLIP_N and (o.get("echo_frac") or 0.0) >= T_ECHO_FRAC:
        findings.append(_finding(
            "execution", "unmeasured_fill", spec.row,
            "action" if spec.live else "warn",
            f"fill sensor reads DISCONNECTED: px_fill == px_decision on "
            f"{n_echo}/{n} orders ({(o.get('echo_frac') or 0):.0%}) and "
            f"{n_slip} of {n} carry slippage_bps — a friction metric here "
            f"scores a perfect 0.0bps under total sensor failure",
            orders=n, echo=n_echo, with_slippage=n_slip))

    # --- realised vs graded, per lens -------------------------------------
    grades = ctx["states"].get("brain-lens-forward")
    lens_ok = _fresh(grades, ctx["now"]) if grades else False
    card["lenses"] = {}
    closes = ctx["closes"].get(spec.row) or []
    by_lens = {}
    for c in closes:
        tag = (c["reason"] or "").split("_")[0]
        if "-" not in tag:
            continue
        by_lens.setdefault(tag.split("-", 1)[1], []).append(c)
    for lens, rows in sorted(by_lens.items()):
        rets = [c["pnl_pct"] for c in rows if c["pnl_pct"] is not None]
        blk = {"n": len(rets), "realised_pct": _r4(_mean(rets)),
               "realised_hi_pct": _r4(_ci_hi(rets))}
        g = ((grades or {}).get("lenses") or {}).get(lens) if lens_ok else None
        if not lens_ok or not g:
            # missing/stale grade must be UNDETERMINED. `(lo or 0) > 0.5` would
            # evaluate False here and read as "no gap" — a clean bill from a
            # dead sensor.
            blk["verdict"] = "undetermined"
            blk["reason"] = ("grade missing" if grades is None else
                             ("grade stale" if not lens_ok else "lens not graded"))
            card["lenses"][lens] = blk
            continue
        blk["graded_lo"] = g.get("ehit4h_lo")
        blk["graded_n_episodes"] = g.get("eps4h")
        if len(rets) < F_REALISED_N or (g.get("eps4h") or 0) < F_GRADED_N:
            blk["verdict"] = "insufficient"
            blk["reason"] = (f"realised n={len(rets)} (floor {F_REALISED_N}), "
                             f"graded eps4h={g.get('eps4h')} (floor {F_GRADED_N})")
        else:
            sig_pos = (blk["graded_lo"] or 0.0) > 0.50
            real_neg = (blk["realised_hi_pct"] is not None
                        and blk["realised_hi_pct"] < 0.0)
            if sig_pos and real_neg:
                blk["verdict"] = "gap"
                worst = _localise_gap(rows, o.get("by_coin") or {})
                blk["localised_to"] = worst
                findings.append(_finding(
                    "execution", "realised_vs_graded", spec.row,
                    "action" if spec.live else "warn",
                    f"lens '{lens}': the SIGNAL grades positive "
                    f"(ehit4h lo {blk['graded_lo']} at {g.get('eps4h')} "
                    f"episodes) while the FILLS lose (upper bound "
                    f"{blk['realised_hi_pct']} at n={len(rets)}) — this is "
                    f"EXECUTION, not decay",
                    lens=lens, localised_to=worst, **{
                        k: blk[k] for k in
                        ("n", "realised_pct", "realised_hi_pct", "graded_lo")}))
            else:
                blk["verdict"] = "no_gap"
        card["lenses"][lens] = blk
    return findings, card


def _localise_gap(rows, by_coin):
    """A gap verdict without a named cause is not actionable: recompute the
    realised upper bound with each symbol removed and report the symbol whose
    removal flips it above zero, joined to that symbol's measured slippage."""
    syms = sorted({r["pair"] for r in rows})
    best = None
    for s in syms:
        rest = [r["pnl_pct"] for r in rows
                if r["pair"] != s and r["pnl_pct"] is not None]
        if len(rest) < 5:
            continue
        hi = _ci_hi(rest)
        if hi is not None and hi > 0:
            slip = (by_coin.get(s.split("/")[0]) or {}).get("slip_bps")
            cand = {"symbol": s, "hi_without": _r4(hi), "slip_bps": _r4(slip),
                    "n_removed": sum(1 for r in rows if r["pair"] == s)}
            if best is None or (cand["slip_bps"] or 0) > (best["slip_bps"] or 0):
                best = cand
    return best


def check_guards(ctx, spec):
    """MEMORY-ONLY GUARD — durable-looking state a restart wipes.

    TWO probes, neither of which reads source (a code review already missed
    this class once, and source is not what runs):
      A. DURABILITY — is the guard's key actually IN the book's published state?
         `persisted == False` is a finding on its own, at zero violations.
      B. VIOLATION  — did the book re-enter the same symbol inside its own
         declared window after firing the guard?
    A guard that never fired is UNTESTED, never PASS: zero violations out of
    zero events is a perfect score from a mechanism that never ran.

    WHAT IS DELIBERATELY *NOT* CLAIMED. Probe A is a reading of the state
    payload NOW; probe B's violations are HISTORICAL. bot_state keeps no
    per-bot history, so a key that is present today may have been added after
    the leaks it is supposed to explain (the Farmer's cooldown/stop_hist were
    persisted only on 2026-07-22). Fusing the two into "the guard is broken" or
    "a restart wiped it" would be a causal verdict resting on an unmeasured
    timeline — the exact shape of error this organ exists to catch. So the
    verdicts stay descriptive, the leak timestamps are published, and the
    causality caveat rides along in the payload.
    """
    findings, card = [], []
    closes = ctx["closes"].get(spec.row) or []
    for g in spec.guards:
        state = ctx["states"].get(g.state_of or spec.state_key)
        if state is None:
            persisted = None            # read failed / no row -> undetermined
        else:
            persisted = g.state_key in state
        events = [c for c in closes if _glob_any(c["reason"], [g.event_glob])]
        violations = []
        if g.duration_h is not None:
            for e in events:
                anchor = (e["open_ts"] if g.basis == "open_to_open"
                          else e["close_ts"])
                if not anchor:
                    continue
                later = [c["open_ts"] for c in closes
                         if c["pair"] == e["pair"] and c["open_ts"]
                         and c["open_ts"] > anchor]
                if not later:
                    continue
                delta_h = (min(later) - anchor) / 3600.0
                if delta_h < g.duration_h:
                    violations.append({"sym": e["pair"],
                                       "delta_h": round(delta_h, 2),
                                       "basis": g.basis,
                                       "after_close_at": e["close_iso"]})
        blk = {"guard": g.name, "state_key": g.state_key, "basis": g.basis,
               "durable_now": persisted, "window_h": g.duration_h,
               "duration_source": g.source, "events": len(events),
               "violations": (None if g.duration_h is None else len(violations)),
               "examples": violations[:3]}
        if persisted is None:
            blk["verdict"] = "undetermined"
            blk["reason"] = "state row unreadable"
            ctx["dark"].append(f"{spec.row}.guard.{g.name}: state unreadable")
        elif g.duration_h is None:
            # no clock -> the behavioural probe is not run at all
            blk["verdict"] = "not_durable" if not persisted else "durable"
            blk["probe_b"] = "skipped — condition-released guard, no duration"
        elif violations and not persisted:
            blk["verdict"] = "memory_only_suspected"
            blk["causality"] = ("key absent from durable state AND leaks "
                                "observed — a boot wipe explains them, but no "
                                "boot record exists to prove it")
        elif violations and persisted:
            blk["verdict"] = "leaks_with_durable_state"
            blk["causality"] = ("key present NOW; bot_state has no history, so "
                                "whether it was present at the leak times is "
                                "not measurable — date the leaks below against "
                                "the persistence change")
        elif not persisted and events:
            blk["verdict"] = "at_risk"
        elif not persisted:
            blk["verdict"] = "at_risk_untested"
        elif not events:
            blk["verdict"] = "untested"
        else:
            blk["verdict"] = "durable"
        if len(events) < F_GUARD_EVENTS and violations:
            blk["note"] = (f"n={len(events)} events — an existence proof, "
                           f"not a violation RATE")
        card.append(blk)
        if blk["verdict"] in ("memory_only_suspected", "leaks_with_durable_state",
                              "not_durable", "at_risk", "at_risk_untested"):
            hard = blk["verdict"] in ("memory_only_suspected",
                                      "leaks_with_durable_state")
            sev = "action" if (spec.live or hard) else "warn"
            vtxt = ("probe B skipped (no clock)" if g.duration_h is None
                    else f"{len(violations)} leak(s) over {len(events)} event(s)")
            findings.append(_finding(
                "guards", "memory_only_guard", spec.row, sev,
                f"guard '{g.name}' "
                f"({'condition-released' if g.duration_h is None else str(g.duration_h) + 'h'}"
                f" on {g.event_glob}): durable key '{g.state_key}' "
                f"{'ABSENT from' if not persisted else 'present in'} published "
                f"state; {vtxt}", **blk))
    return findings, card


def check_signals(ctx, spec):
    """UNWIRED CONSUMER — a published safety signal the book never reads.

    The publisher's OWN freshness is evaluated FIRST. If the publisher is dark,
    every consumer verdict is UNDETERMINED — never 'wired' and never 'unwired'.
    Otherwise a naive "did anyone read it" scores 100% (nobody needed to) or 0%
    (nobody did), from the publisher's death rather than the consumer's.
    """
    findings, card = [], {}
    src = (ctx.get("src") or {}).get(spec.module)
    if src is None:
        ctx["dark"].append(f"{spec.row}.signals: source unreadable")
        return [], {"dark": f"source unreadable: {spec.module}"}
    closes = ctx["closes"].get(spec.row) or []
    for key in spec.expects:
        pub = ctx["states"].get(key)
        blk = {"publisher_fresh": _fresh(pub, ctx["now"]) if pub else False}
        if not blk["publisher_fresh"]:
            blk["verdict"] = "undetermined"
            blk["reason"] = "publisher missing or stale — consumers unjudgeable"
            card[key] = blk
            continue
        referenced = (key in src)
        blk["referenced"] = referenced
        blk["verified"] = False     # static: presence never proves it is REACHED
        if referenced:
            blk["verdict"] = "referenced"
        else:
            blk["verdict"] = "unwired"
            sev = ("action" if (spec.live and closes)
                   else ("warn" if closes else "info"))
            findings.append(_finding(
                "signals", "unwired_consumer", spec.row, sev,
                f"never reads '{key}' ({SIGNALS.get(key, '')}) — publisher is "
                f"fresh, the module never names the key, and the book has "
                f"{len(closes)} closes of exposure",
                key=key, n_closes=len(closes)))
        card[key] = blk
    return findings, card


def check_evidence(ctx, spec):
    """EVIDENCE STARVATION — can this book ever reach statistical power?

    Both n* values are mandatory and reported together. n_obs* (the n needed
    for the OBSERVED mean to clear zero) is the OVERFIT trap: it shrinks
    whenever a lucky window inflates |m|, so a book looks closest to
    significance exactly when it is most overfit. n_mde* is the honest one,
    because the minimum detectable effect is fixed by MEASURED friction rather
    than by the result — an edge smaller than the cost of trading is not worth
    detecting. n_mde* is null (not substituted) when friction is unmeasured.

    `closed_trades == 0` on a book reporting status=online with ~$1000 equity is
    the loudest verdict here, precisely because every dashboard panel reads
    green in that state.
    """
    closes = ctx["closes"].get(spec.row) or []
    pnl_row = (ctx.get("pnl") or {}).get(spec.row) or {}
    first_seen = (ctx.get("first_seen") or {}).get(spec.row)
    now = ctx["now"]
    span_d = None
    if closes:
        t0 = min(c["open_ts"] or c["close_ts"] for c in closes)
        t1 = max(c["close_ts"] or 0.0 for c in closes)
        if t0 and t1 and t1 > t0:
            span_d = (t1 - t0) / 86400.0
    age_d = ((now - first_seen) / 86400.0) if first_seen else None
    card = {"n_closes": len(closes), "span_d": _r4(span_d), "age_d": _r4(age_d),
            "status": pnl_row.get("status"), "equity": pnl_row.get("equity")}
    findings = []
    if not closes and not ctx.get("ledger_ok"):
        # The ledger never loaded. "No closes" is UNKNOWN, not zero — emitting
        # a starvation finding here fabricates evidence from a dead DB, and on
        # a live book it does so at ACTION severity. Report the darkness; rule
        # on nothing.
        card["verdict"] = "undetermined"
        card["cadence_d"] = None
        card["why"] = "ledger dark — cannot distinguish no-closes from no-read"
        return findings, card
    if not closes:
        card["verdict"] = "no_closes_ever"
        card["cadence_d"] = 0.0
        findings.append(_finding(
            "evidence", "evidence_starvation", spec.row,
            "action" if spec.live else "warn",
            f"ZERO closes ever in {age_d:.1f} days alive while reporting "
            f"status={pnl_row.get('status')} equity="
            f"{pnl_row.get('equity')} — every panel reads green and the book "
            f"has produced no evidence at all"
            if age_d else "ZERO closes ever; age unknown",
            age_d=_r4(age_d), status=pnl_row.get("status")))
        return findings, card
    denom = span_d if (span_d and span_d > 0) else (age_d or None)
    cadence = (len(closes) / denom) if denom else None
    recent = [c for c in closes if c["close_ts"] and now - c["close_ts"] <= 7 * 86400]
    cadence7 = len(recent) / 7.0
    rets = [c["pnl_pct"] for c in closes if c["pnl_pct"] is not None]
    m, s = _mean(rets), _sd(rets)
    t = _t_stat(rets) if len(rets) >= F_EVID_SD_N else None
    card.update({"cadence_d": _r4(cadence), "cadence_7d": _r4(cadence7),
                 "mean_pct": _r4((m or 0) * 100 if m is not None else None),
                 "sd_pct": _r4((s or 0) * 100 if s is not None else None),
                 "t_zero_cost": _r4(t)})
    n_obs = None
    if m and s and abs(m) > 0:
        n_obs = int(math.ceil((1.96 * s / abs(m)) ** 2))
    mde = ((ctx.get("orders") or {}).get(spec.row) or {}).get("mde")
    n_mde = None
    if s and mde:
        n_mde = int(math.ceil(((1.96 + 0.84) * s / mde) ** 2))
    card["n_obs_star"] = n_obs
    card["n_mde_star"] = n_mde
    card["mde"] = _r4(mde)
    if n_mde is None:
        card["mde_note"] = ("dark: friction unmeasured for this book — no "
                            "fleet-wide constant substituted (slippage is "
                            "per-book, not per-venue)")
    # WHICH TARGET. n_mde* is the honest one — its effect size is fixed by
    # MEASURED friction, not by the result. n_obs* shrinks whenever a lucky
    # window inflates |m|, so a book looks CLOSEST to significance exactly when
    # it is most overfit. Falling back to it silently would be the same error as
    # substituting a friction constant, in a different dress — so the fallback
    # happens, and it is STAMPED.
    target = n_mde or n_obs
    card["power_basis"] = ("mde (measured friction)" if n_mde else
                           ("observed_mean — OVERFIT-PRONE: friction is "
                            "unmeasured for this book, so the target shrinks "
                            "with a lucky window" if n_obs else None))
    days_to = None
    if target and cadence7 and cadence7 > 0 and target > len(closes):
        days_to = (target - len(closes)) / cadence7
    elif target and target <= len(closes):
        days_to = 0.0
    card["days_to_power"] = _r4(days_to)
    proj30 = (cadence or 0.0) * 30.0
    card["proj_trades_30d"] = _r4(proj30)
    card["gate_trades_30d"] = spec.gate_trades_30d
    card["gate_age_days"] = GATE_MIN_AGE_DAYS
    card["gate_age_reachable"] = None if age_d is None else bool(age_d >= 0)
    card["age_gate_met"] = None if age_d is None else bool(age_d >= GATE_MIN_AGE_DAYS)
    # A cadence measured over one or two days is noise, not construction. The
    # six Parliament books are ~1 day old; extrapolating them to 30 would be
    # arithmetic wearing the clothes of evidence.
    young = (denom is None) or (denom < F_CADENCE_SPAN_D)
    card["cadence_basis_days"] = _r4(denom)
    if young:
        card["verdict"] = "too_young_to_judge"
        card["note"] = (f"cadence measured over {denom:.1f}d (<{F_CADENCE_SPAN_D}) "
                        f"— extrapolating it to 30d would be noise")
    elif proj30 < spec.gate_trades_30d:
        card["verdict"] = "gate_unreachable"
        findings.append(_finding(
            "evidence", "evidence_starvation", spec.row,
            "action" if spec.live else "warn",
            f"cannot reach the go-live trade gate: {cadence:.2f} closes/day "
            f"over {denom:.1f}d projects {proj30:.1f} per 30d against a floor "
            f"of {spec.gate_trades_30d} — this is construction, not a slow week",
            cadence_d=_r4(cadence), proj_30d=_r4(proj30), span_d=_r4(denom),
            gate=spec.gate_trades_30d, n=len(closes)))
    elif cadence7 == 0:
        card["verdict"] = "stalled"
        findings.append(_finding(
            "evidence", "evidence_starvation", spec.row,
            "action" if spec.live else "warn",
            f"STALLED: {len(closes)} lifetime closes but ZERO in the last 7 "
            f"days — cadence measured from first close would hide this",
            n=len(closes)))
    elif days_to is not None and days_to > T_STARVE_DAYS:
        card["verdict"] = "starved"
        findings.append(_finding(
            "evidence", "evidence_starvation", spec.row,
            "warn", f"{days_to:.0f} days to power at the current "
                    f"{cadence7:.2f} closes/day (target n={target} on "
                    f"{card['power_basis']}, have {len(closes)}; sd "
                    f"{card['sd_pct']}%, t {card['t_zero_cost']})",
            days_to_power=_r4(days_to), target_n=target, n=len(closes),
            power_basis=card["power_basis"], mde=card["mde"]))
    elif days_to is not None and days_to > T_SLOW_DAYS:
        card["verdict"] = "slow"
    elif mde and s and mde > 2.0 * s:
        # A minimum detectable effect larger than TWO per-trade standard
        # deviations means no realistic edge could ever clear the cost. The
        # book is COST-blocked, not evidence-blocked — and n_mde* collapses to
        # ~1, which would otherwise print as "powered". That is the degenerate
        # reading this branch exists to stop.
        card["verdict"] = "cost_blocked"
        findings.append(_finding(
            "evidence", "evidence_starvation", spec.row,
            "action" if spec.live else "warn",
            f"COST-BLOCKED, not evidence-blocked: measured friction implies a "
            f"minimum detectable effect of {mde*100:.1f}%/trade against a "
            f"per-trade sd of {s*100:.2f}% — no plausible edge clears it. "
            f"t at ZERO cost is {_r4(t)} over n={len(closes)}",
            mde=_r4(mde), sd=_r4(s), t_zero_cost=_r4(t), n=len(closes)))
    elif target and len(closes) >= target:
        card["verdict"] = "powered"
    else:
        card["verdict"] = "building"
    if len(rets) < F_EVID_SD_N:
        card["t_note"] = (f"n={len(rets)} < {F_EVID_SD_N}: sd is not estimable, "
                          f"so no t is reported")
    return findings, card


CHECKS = {
    "lever_authority": check_lever_authority,
    "concentration": check_concentration,
    "execution": check_execution,
    "guards": check_guards,
    "signals": check_signals,
    "evidence": check_evidence,
}


# --------------------------------------------------------------------------- #
# verdict — ONE status and THE ONE binding constraint per book
# --------------------------------------------------------------------------- #
# priority order: what most limits this book from producing trustworthy P&L.
_BIND_ORDER = ("evidence_starvation", "unmeasured_fill", "memory_only_guard",
               "unwired_consumer", "realised_vs_graded", "inert_lever",
               "unlevered_knob", "concentration")


def book_verdict(spec, findings, card):
    sev = max([SEV_RANK[f["severity"]] for f in findings], default=-1)
    status = {2: "action", 1: "watch", 0: "note", -1: "clear"}[sev]
    binding = None
    for klass in _BIND_ORDER:
        cands = [f for f in findings if f["klass"] == klass]
        if cands:
            cands.sort(key=lambda f: -SEV_RANK[f["severity"]])
            binding = {"klass": klass, "summary": cands[0]["summary"]}
            break
    dark_here = [d for d in (card.get("_dark") or [])]
    if status == "clear" and dark_here:
        status = "dark"
    return {"status": status, "binding_constraint": binding,
            "n_findings": len(findings),
            "real_money": spec.live}


def run_bench(ctx):
    """Run every check for every book. One failing check never stops the bench,
    and the bench telemetry is PRE-SEEDED for all six names — a check that never
    fires must look QUIET, not absent. Absent is how gaps hide."""
    bench = {name: {"runs": 0, "findings": 0, "errors": 0, "last_book": None}
             for name in CHECKS}
    cards, findings = {}, []
    for row, spec in BOOKS.items():
        card = {}
        dark_before = len(ctx["dark"])
        book_findings = []
        for name, fn in CHECKS.items():
            bench[name]["runs"] += 1
            try:
                fs, blk = fn(ctx, spec)
            except Exception as e:              # noqa: BLE001
                bench[name]["errors"] += 1
                card[name] = {"error": f"{type(e).__name__}: {e}"}
                ctx["dark"].append(f"{row}.{name}: check raised {type(e).__name__}")
                continue
            card[name] = blk
            for f in fs:
                bench[name]["findings"] += 1
                bench[name]["last_book"] = row
            book_findings.extend(fs)
        card["_dark"] = ctx["dark"][dark_before:]
        card["verdict"] = book_verdict(spec, book_findings, card)
        card["note"] = spec.note
        card["live"] = spec.live
        card["module"] = spec.module
        cards[row] = card
        findings.extend(book_findings)
    return cards, findings, bench


def rank_findings(findings):
    """REAL-MONEY FIRST. Within that, severity, then the class priority order,
    then dollars implicated."""
    def usd(f):
        ev = f.get("evidence") or {}
        for k in ("loss_usd", "total_usd", "gross_loss_usd"):
            if isinstance(ev.get(k), (int, float)):
                return abs(float(ev[k]))
        return 0.0
    order = {k: i for i, k in enumerate(_BIND_ORDER)}
    return sorted(findings, key=lambda f: (
        0 if f["live"] else 1,
        -SEV_RANK[f["severity"]],
        order.get(f["klass"], 99),
        -usd(f),
    ))


# =========================================================================== #
# I/O — the only DB-touching code in the module
# =========================================================================== #
def db_now(cur, fallback):
    """The clock for freshness arithmetic, taken from the DB.

    Every `updated` stamp on the bus was written against the DB's clock, and
    _fresh() requires 0 <= age — a future-dated payload is NOT fresh (the
    fleet-wide contract; fleet_tuning._is_fresh does the same). Measured
    2026-07-22: a few seconds of skew between this process and the publisher
    flipped 18 consumer verdicts to `undetermined` and dropped 19 findings.
    Fail-safe, but wrong, and only visible because two runs a minute apart
    disagreed. Falls back to the caller's clock rather than raising.

    NOTE: the CALL SITE in build_ctx() is not reachable from the offline
    selftest — an I/O line cannot be covered without a DB. This function is
    unit-tested; the wiring is covered by the live-run stability check.
    """
    try:
        cur.execute("SELECT extract(epoch from now())")
        return float(cur.fetchone()[0])
    except Exception:                           # noqa: BLE001
        return fallback


def _repo_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _read_sources():
    out = {}
    base = _repo_dir()
    for spec in BOOKS.values():
        if spec.module in out:
            continue
        p = os.path.join(base, spec.module)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                out[spec.module] = fh.read()
        except Exception:                       # noqa: BLE001
            out[spec.module] = None
    return out


def build_ctx():
    """ONE shared read per cycle. Every failure degrades to a dark marker; the
    checks then report `dark`, which renders distinctly from every verdict."""
    now = datetime.now(timezone.utc).timestamp()
    # [2026-07-22] ledger_ok distinguishes "this book genuinely has no closes"
    # from "we never got to look". EVERY build_ctx failure path leaves
    # ctx["closes"] == {}, and check_evidence read that as "ZERO closes ever" —
    # an ACTION-severity finding on the LIVE books, manufactured from a dark
    # ledger. Absence of evidence rendered as evidence of absence; the same
    # shape as the sniper's `watching: 201`
    # ([[a-convergent-metric-is-not-a-health-check]]). Only the successful
    # paper_trades query sets this True.
    ctx = {"now": now, "window_d": WINDOW_D, "dark": [], "ledger_ok": False,
           "closes": {}, "orders": {}, "pnl": {}, "states": {},
           "first_seen": {}, "tape": [], "src": _read_sources(),
           "registry": dict(getattr(tuning, "LEVERS", {}) or {}) if tuning else {}}
    if not ctx["registry"]:
        ctx["dark"].append("lever registry unavailable (fleet_tuning not importable)")
    for mod, txt in ctx["src"].items():
        if txt is None:
            ctx["dark"].append(f"source unreadable: {mod}")

    keys = sorted(set(list(SIGNALS) + [s.state_key for s in BOOKS.values()]
                      + [g.state_of for s in BOOKS.values() for g in s.guards
                         if g.state_of] + ["fleet-tuning"]))
    if store is None:
        ctx["dark"].append("bot_pnl_store unavailable — ledger, orders and "
                           "state are ALL dark")
        return ctx
    try:
        ctx["states"] = store.fetch_states(keys) or {}
    except Exception as e:                      # noqa: BLE001
        ctx["dark"].append(f"state read failed: {type(e).__name__}")
    missing = [k for k in SIGNALS if k not in ctx["states"]]
    for k in missing:
        ctx["dark"].append(f"signal '{k}' absent from bot_state")

    conn = None
    try:
        conn = store._get_conn()
    except Exception:                           # noqa: BLE001
        conn = None
    if conn is None:
        ctx["dark"].append("no DB connection — ledger/orders/tape dark")
        return ctx
    rows = list(BOOKS)
    try:
        with conn.cursor() as cur:
            # THE CLOCK COMES FROM THE DB, not from this process. Every
            # `updated` stamp on the bus was written against the DB's clock,
            # and _fresh() requires 0 <= age (a future-dated payload is not
            # fresh — the fleet-wide contract, fleet_tuning._is_fresh:same).
            # Measured 2026-07-22: a few seconds of skew between a laptop and
            # the publisher flipped 18 consumer verdicts to `undetermined` and
            # silently dropped 19 findings. Fail-safe, but wrong — and only
            # visible because the counts moved between two runs a minute apart.
            ctx["now"] = db_now(cur, ctx["now"])
            cur.execute(
                """SELECT bot, pair, opened_at, closed_at, reason, pnl_abs,
                          pnl_pct, side
                     FROM paper_trades
                    WHERE bot = ANY(%s) AND closed_at IS NOT NULL
                      AND COALESCE(side,'') <> 'skip'""", (rows,))
            for (bot, pair, o, c, reason, pa, pp, side) in cur.fetchall():
                ctx["closes"].setdefault(bot, []).append({
                    "pair": pair, "open_ts": _parse_ts(o), "close_ts": _parse_ts(c),
                    "close_iso": c, "reason": reason,
                    "pnl_abs": float(pa) if pa is not None else None,
                    "pnl_pct": float(pp) if pp is not None else None,
                    "side": side})
            for bot in ctx["closes"]:
                ctx["closes"][bot].sort(key=lambda r: r["open_ts"] or 0.0)
            # The ledger query SUCCEEDED — an empty closes[] for a book now
            # genuinely means that book has no closes.
            ctx["ledger_ok"] = True

            # Book-level first, and the MEDIAN is computed in SQL over the raw
            # rows — a median of per-coin means is not a median, and on a book
            # where one coin is 56% of the orders the difference is the whole
            # number. NOTE the deliberate absence of a COALESCE fallback to
            # px_fill/px_decision-1: on both live books that expression is
            # exactly 0 and would score real money at perfect execution.
            cur.execute(
                """SELECT bot, count(*), count(slippage_bps),
                          count(*) FILTER (WHERE px_fill IS NULL
                                            OR px_fill = px_decision),
                          percentile_cont(0.5) WITHIN GROUP
                              (ORDER BY abs(slippage_bps))
                     FROM venue_orders
                    WHERE bot = ANY(%s) AND at > now() - %s * interval '1 day'
                    GROUP BY 1""", (rows, ORDER_WINDOW_D))
            agg = {}
            for bot, n, ns, echo, med in cur.fetchall():
                agg[bot] = {"n": int(n), "n_slip": int(ns), "n_echo": int(echo),
                            "slip_med": float(med) if med is not None else None,
                            "by_coin": {}}
            cur.execute(
                """SELECT bot, coin, count(*), count(slippage_bps),
                          percentile_cont(0.5) WITHIN GROUP
                              (ORDER BY abs(slippage_bps))
                     FROM venue_orders
                    WHERE bot = ANY(%s) AND at > now() - %s * interval '1 day'
                    GROUP BY 1,2""", (rows, ORDER_WINDOW_D))
            for bot, coin, n, ns, med in cur.fetchall():
                if bot in agg and med is not None:
                    agg[bot]["by_coin"][coin] = {"n": int(n), "n_slip": int(ns),
                                                 "slip_bps": float(med)}
            for bot, a in agg.items():
                a["echo_frac"] = (a["n_echo"] / a["n"]) if a["n"] else None
                a["mde"] = ((2.0 * a["slip_med"] / 1e4 + 2.0 * TAKER_FEE_FRAC)
                            if (a["slip_med"] is not None
                                and a["n_slip"] >= F_SLIP_N) else None)
            ctx["orders"] = agg

            cur.execute("SELECT bot, status, equity, closed_trades FROM bot_pnl "
                        "WHERE bot = ANY(%s)", (rows,))
            for bot, status, eq, ct in cur.fetchall():
                ctx["pnl"][bot] = {"status": status,
                                   "equity": float(eq) if eq is not None else None,
                                   "closed_trades": ct}
            cur.execute("SELECT bot, min(ts) FROM bot_equity_history "
                        "WHERE bot = ANY(%s) GROUP BY 1", (rows,))
            for bot, t0 in cur.fetchall():
                ctx["first_seen"][bot] = t0.timestamp() if t0 else None

            cur.execute(
                """SELECT payload->'funding', payload->'tickets'
                     FROM bot_state_history
                    WHERE key = 'lighter-market'
                      AND ts > now() - %s * interval '1 day'""", (WINDOW_D,))
            ctx["tape"] = [{"funding": f, "tickets": t} for f, t in cur.fetchall()]
    except Exception as e:                      # noqa: BLE001
        ctx["dark"].append(f"ledger read failed: {type(e).__name__}: {e}")
    if not ctx["tape"]:
        ctx["dark"].append("scout tape empty for the window — lever authority "
                           "is DARK, not healthy")
    return ctx


def build_payload(ctx, cards, findings, bench):
    ranked = rank_findings(findings)
    counts = {}
    for f in findings:
        counts[f["klass"]] = counts.get(f["klass"], 0) + 1
    for k in KLASSES:
        counts.setdefault(k, 0)
    stat = {}
    for row, card in cards.items():
        stat[card["verdict"]["status"]] = stat.get(card["verdict"]["status"], 0) + 1
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "ttl_sec": TTL_SEC,
        "window_d": WINDOW_D,
        "books": cards,
        "findings": ranked[:MAX_FINDINGS],
        "n_findings": len(findings),
        "bench": bench,
        "class_owner": CLASS_OWNER,
        "counts": {"books": len(cards), "by_class": counts, "by_status": stat,
                   "dark": len(ctx["dark"])},
        # dark is TOP-LEVEL and never folded into findings: a dark sensor must
        # be visible AS a dark sensor, which is the whole point of the class.
        "dark": ctx["dark"][:200],
        "mode": "publish-only",
    }


def run_once(publish=True):
    ctx = build_ctx()
    cards, findings, bench = run_bench(ctx)
    payload = build_payload(ctx, cards, findings, bench)
    if publish and store is not None:
        try:
            store.save_state(KEY, payload)
            store.save_history(KEY, payload)
        except Exception as e:                  # noqa: BLE001
            print(f"[agronomy] publish failed: {e}", file=sys.stderr)
    return payload


# =========================================================================== #
# SELFTEST — offline. Every case asserts the metric reads NOT-healthy under
# total failure of its own mechanism. Mutation-tested: break a guard, go red.
# =========================================================================== #
_FAILS = []


def _ck(cond, msg):
    if not cond:
        _FAILS.append(msg)


def _close(pair, o_h, c_h, reason, pnl, pct=None, base=0.0):
    return {"pair": pair, "open_ts": base + o_h * 3600.0,
            "close_ts": base + c_h * 3600.0,
            "close_iso": datetime.fromtimestamp(base + c_h * 3600.0,
                                                timezone.utc).isoformat(),
            "reason": reason, "pnl_abs": pnl,
            "pnl_pct": pct if pct is not None else pnl / 100.0, "side": "long"}


def _ctx(**kw):
    # ledger_ok defaults TRUE here: every fixture below describes a book whose
    # ledger loaded fine, which is what makes "zero closes" meaningful. Pass
    # ledger_ok=False explicitly to exercise the dark-ledger path.
    base = {"now": 1_000_000.0, "window_d": 7, "dark": [], "ledger_ok": True,
            "closes": {}, "orders": {}, "pnl": {}, "states": {}, "first_seen": {},
            "tape": [], "src": {}, "registry": dict(getattr(tuning, "LEVERS", {}) or {})}
    base.update(kw)
    return base


def _spec(**kw):
    kw.setdefault("row", "TEST")
    kw.setdefault("module", "test_module.py")
    s = BookSpec(**kw)
    BOOKS[s.row] = s          # so _finding() can resolve live-ness
    return s


def _selftest():
    global _FAILS
    _FAILS = []

    # -- 1. bench + class coverage -----------------------------------------
    _ck(len(CHECKS) == 6, f"bench size changed: {len(CHECKS)}")
    _ck(set(CLASS_OWNER) == set(KLASSES),
        "CLASS_OWNER is not total over KLASSES — a class lost its owner")
    _ck(all(v in CHECKS for v in CLASS_OWNER.values()),
        "a class points at a check that does not exist")

    # -- 2. lever authority: the degenerate two-pin distribution ------------
    qs = [10.512] * 78 + [3.504] * 76 + [4.0 + i * 0.05 for i in range(48)]
    res = lever_authority("live.funding.enter_apr",
                          {"lo": 0.03125, "hi": 0.075}, qs, 100)
    _ck(res["verdict"] == "degenerate",
        f"two-pin distribution should be degenerate, got {res['verdict']}")
    _ck(res["step_share"] >= 0.50,
        f"step_share must be normalised by swing: {res['step_share']}")
    _ck(res["separable"] is False, "the modal pin must be unseparable")
    _ck(res["decisive_vs_bound"] and res["decisive_vs_bound"] > 1.0,
        f"the decisive value sits ABOVE the bound; decisive_vs_bound must "
        f"exceed 1, got {res.get('decisive_vs_bound')}")

    # -- 3. lever authority: a healthy continuous lever ---------------------
    qs2 = [i * 0.2 for i in range(1000)]         # 0..200 uniform
    res2 = lever_authority("taker.div_gap_pp", {"lo": 37.5, "hi": 87.5}, qs2, 100)
    _ck(res2["verdict"] == "healthy",
        f"a uniform quantity should be healthy, got {res2['verdict']}")
    _ck(res2["reach"] > T_COARSE_R, "a continuous lever must be finely reachable")

    # -- 4. DARK on an empty tape (must NOT read 'inert') -------------------
    res3 = lever_authority("live.funding.enter_apr", {"lo": 0.03125, "hi": 0.075},
                           [], 0)
    _ck(res3["verdict"] == "dark",
        f"empty tape must be dark, got {res3['verdict']}")
    _ck(res3["verdict"] not in ("healthy", "inert", "degenerate"),
        "a dark sensor must not render as any verdict")

    # -- 5. UNIT ADAPTER: the 8x-shaped error -------------------------------
    q = LEVER_Q["live.funding.enter_apr"]
    _ck(abs(q.to_q(0.075) - 7.5) < 1e-9,
        "to_q must map the lever's FRACTION onto the tape's apr_pct")
    raw = cdf_admit(qs, 0.075, "ge")
    adapted = cdf_admit(qs, q.to_q(0.075), "ge")
    _ck(raw == 1.0 and adapted < 1.0,
        "without to_q the lever admits everything — the unit bug must be visible")

    # -- 6. episodes: back-to-back re-entries are ONE episode ---------------
    rows = [_close("BOT", i * 0.1, i * 0.1 + 0.08, "short-divergence_sl", -0.5)
            for i in range(8)]
    eps = episodes(rows, 120.0)
    _ck(len(eps) == 1, f"8 back-to-back re-entries must be 1 episode, got {len(eps)}")
    # -- 7. ...and widely spaced ones are eight ----------------------------
    rows2 = [_close("BOT", i * 10.0, i * 10.0 + 0.08, "x_sl", -0.5) for i in range(8)]
    _ck(len(episodes(rows2, 120.0)) == 8,
        "10h-spaced trades must be separate episodes — the gap must be USED")

    # -- 8. concentration: 1-symbol book is UNDETERMINED, not HHI 1.0 -------
    sp = _spec(row="T_CONC1", cooldown_min=120.0)
    f, c = check_concentration(_ctx(closes={"T_CONC1": rows}), sp)
    _ck(c["loss"]["verdict"] == "insufficient",
        f"a 1-symbol book must be insufficient, got {c['loss']}")
    _ck(not f, "a 1-symbol book must not raise a concentration finding")

    # -- 9. concentration: gains and losses must NOT be pooled -------------
    many = []
    for i in range(6):
        many.append(_close("AAA", i * 20.0, i * 20.0 + 1.0, "x_sl", -3.0))
    for i in range(6):
        many.append(_close(f"S{i}", 200 + i * 20.0, 201 + i * 20.0, "x_tp", 2.0))
    sp9 = _spec(row="T_CONC2", cooldown_min=60.0)
    f9, c9 = check_concentration(_ctx(closes={"T_CONC2": many}), sp9)
    _ck(c9["loss"]["top_share"] == 1.0 and c9["gain"]["top_share"] < 0.5,
        f"signs must be kept apart: loss={c9['loss']}, gain={c9['gain']}")
    _ck(any(x["klass"] == "concentration" for x in f9),
        "a 100%-in-one-symbol loss with 6 episodes must be flagged")

    # -- 10. concentration: pnl_abs NULL must be DARK, not clean ------------
    bad = [dict(r, pnl_abs=None) for r in many]
    f10, c10 = check_concentration(_ctx(closes={"T_CONC2": bad}), sp9)
    _ck(c10["verdict"] == "dark",
        f"NULL pnl_abs must be dark, got {c10.get('verdict')}")

    # -- 11. guards: zero events is UNTESTED, never PASS --------------------
    spg = _spec(row="T_G1", state_key="T_G1",
                guards=(Guard("cool", "*_stop", 12.0, "cooldown"),))
    f11, c11 = check_guards(
        _ctx(closes={"T_G1": [_close("X", 0, 1, "long_tp", 1.0)]},
             states={"T_G1": {"cooldown": {}}}), spg)
    _ck(c11[0]["verdict"] == "untested",
        f"no guard events must be untested, got {c11[0]['verdict']}")

    # -- 12. guards: an ABSENT durable key is a finding at ZERO violations --
    f12, c12 = check_guards(
        _ctx(closes={"T_G1": [_close("X", 0, 1, "long_stop", -1.0)]},
             states={"T_G1": {"meta": {}}}), spg)
    _ck(c12[0]["durable_now"] is False and c12[0]["verdict"] == "at_risk",
        f"absent durable key must flag on its own: {c12[0]}")
    _ck(any(x["klass"] == "memory_only_guard" for x in f12),
        "probe A must stand alone — no violation required")

    # -- 13. guards: the two probes must NOT be fused into causality --------
    seq = [_close("X", 0, 1, "long_stop", -1.0), _close("X", 2, 3, "long_tp", 1.0)]
    f13, c13 = check_guards(
        _ctx(closes={"T_G1": seq}, states={"T_G1": {"cooldown": {}}}), spg)
    _ck(c13[0]["verdict"] == "leaks_with_durable_state" and c13[0]["violations"] == 1,
        f"present key + leak must NOT be called a logic bug: {c13[0]}")
    _ck("not measurable" in (c13[0].get("causality") or ""),
        "a NOW reading against HISTORICAL leaks must carry the timeline caveat")
    _ck(c13[0]["examples"] and c13[0]["examples"][0].get("after_close_at"),
        "leaks must carry a REAL timestamp — a null date cannot be placed "
        "against the persistence change, which is the whole caveat")
    f13b, c13b = check_guards(
        _ctx(closes={"T_G1": seq}, states={"T_G1": {"meta": {}}}), spg)
    _ck(c13b[0]["verdict"] == "memory_only_suspected",
        f"absent key + leak = memory_only_SUSPECTED, got {c13b[0]['verdict']}")
    _ck("no boot record" in (c13b[0].get("causality") or ""),
        "the wipe explanation must be labelled unproven — no boot record exists")

    # -- 14. guards: an unreadable state row is UNDETERMINED ----------------
    f14, c14 = check_guards(_ctx(closes={"T_G1": seq}, states={}), spg)
    _ck(c14[0]["verdict"] == "undetermined",
        f"missing state must be undetermined, got {c14[0]['verdict']}")

    # -- 14b. a CONDITION-released guard has no clock: probe B must not run -
    spq = _spec(row="T_G2", state_key="T_G2",
                guards=(Guard("noconv", "*_max_hold", None, "noconv"),))
    seq2 = [_close("X", 0, 1, "long_max_hold", -1.0),
            _close("X", 1.1, 2, "long_converged", 0.1)]
    f14b, c14b = check_guards(
        _ctx(closes={"T_G2": seq2}, states={"T_G2": {"meta": {}}}), spq)
    _ck(c14b[0]["violations"] is None and "skipped" in c14b[0].get("probe_b", ""),
        f"no duration => no violation count may be invented: {c14b[0]}")
    _ck(c14b[0]["verdict"] == "not_durable" and f14b,
        "probe A still convicts an absent durable key without probe B")

    # -- 14c. the window BASIS must be the one the book actually arms --------
    # open 0h -> close 5h -> re-open 5.5h. Under an ENTRY-armed 1h cooldown
    # that is legal (5.5h between entries); measuring it from the CLOSE calls
    # it a leak. Same rows, opposite verdicts — so the basis is load-bearing.
    held = [_close("X", 0.0, 5.0, "long-x_tp", 1.0),
            _close("X", 5.5, 6.0, "long-x_tp", 1.0)]
    sp_c = _spec(row="T_G3", state_key="T_G3",
                 guards=(Guard("cd", "*", 1.0, "k", basis="close_to_open"),))
    sp_o = _spec(row="T_G4", state_key="T_G4",
                 guards=(Guard("cd", "*", 1.0, "k", basis="open_to_open"),))
    _, cc = check_guards(_ctx(closes={"T_G3": held},
                              states={"T_G3": {"k": {}}}), sp_c)
    _, co = check_guards(_ctx(closes={"T_G4": held},
                              states={"T_G4": {"k": {}}}), sp_o)
    _ck(cc[0]["violations"] == 1 and co[0]["violations"] == 0,
        f"an ENTRY-armed cooldown measured from the close invents leaks: "
        f"close_to_open={cc[0]['violations']}, open_to_open={co[0]['violations']}")

    # -- 15. signals: a STALE publisher makes every consumer undetermined ---
    sps = _spec(row="T_S1", expects=("fleet-risk",))
    stale = {"updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 300}
    f15, c15 = check_signals(
        _ctx(src={"test_module.py": "no key here"}, states={"fleet-risk": stale},
             closes={"T_S1": [_close("X", 0, 1, "x_tp", 1.0)]}), sps)
    _ck(c15["fleet-risk"]["verdict"] == "undetermined" and not f15,
        f"stale publisher must not convict a consumer: {c15}")
    fresh = {"updated": datetime.fromtimestamp(1_000_000 - 10, timezone.utc)
             .isoformat(), "ttl_sec": 3600}
    f15b, c15b = check_signals(
        _ctx(src={"test_module.py": "no key here"}, states={"fleet-risk": fresh},
             closes={"T_S1": [_close("X", 0, 1, "x_tp", 1.0)]}), sps)
    _ck(c15b["fleet-risk"]["verdict"] == "unwired" and len(f15b) == 1,
        f"fresh publisher + no reference = unwired: {c15b}")
    f15c, c15c = check_signals(
        _ctx(src={"test_module.py": 'load_state("fleet-risk")'},
             states={"fleet-risk": fresh}, closes={"T_S1": []}), sps)
    _ck(c15c["fleet-risk"]["verdict"] == "referenced"
        and c15c["fleet-risk"]["verified"] is False,
        "a static reference is REFERENCED, never verified-wired")

    # -- 16. execution: the echo-fill trap ---------------------------------
    spe = _spec(row="T_X1", live=True)
    ctxe = _ctx(orders={"T_X1": {"n": 81, "n_slip": 0, "n_echo": 78,
                                 "echo_frac": 78 / 81, "slip_med": None,
                                 "by_coin": {}}},
                closes={"T_X1": []})
    f16, c16 = check_execution(ctxe, spe)
    _ck(c16["verdict"] == "dark" and c16["mde"] is None,
        f"no slippage rows must leave mde null: {c16.get('verdict')}")
    _ck(any(x["klass"] == "unmeasured_fill" for x in f16),
        "px_fill == px_decision on 96% of a live book must be a finding")
    _ck(any("T_X1.mde" in d for d in ctxe["dark"]),
        "the dark marker must name the book and the metric")

    # -- 17. execution: realised-vs-graded is THREE-state -------------------
    lens_rows = [_close("BOT/USDC", i * 5.0, i * 5.0 + 1.0,
                        "short-divergence_sl", -0.5, pct=-0.01) for i in range(25)]
    spl = _spec(row="T_X2")
    g_fresh = {"updated": datetime.fromtimestamp(1_000_000 - 10, timezone.utc)
               .isoformat(), "ttl_sec": 3600,
               "lenses": {"divergence": {"ehit4h_lo": 0.512, "eps4h": 977}}}
    f17, c17 = check_execution(
        _ctx(closes={"T_X2": lens_rows}, states={"brain-lens-forward": g_fresh},
             orders={}), spl)
    _ck(c17["lenses"]["divergence"]["verdict"] == "gap",
        f"positive grade + negative fills = gap: {c17['lenses']}")
    f17b, c17b = check_execution(
        _ctx(closes={"T_X2": lens_rows}, states={}, orders={}), spl)
    _ck(c17b["lenses"]["divergence"]["verdict"] == "undetermined" and not f17b,
        "a missing grade must be undetermined, never 'no gap'")

    # -- 18. evidence: closed_trades == 0 while status=online is LOUD -------
    spv = _spec(row="T_E1")
    f18, c18 = check_evidence(
        _ctx(closes={}, pnl={"T_E1": {"status": "online", "equity": 1000.0}},
             first_seen={"T_E1": 1_000_000.0 - 9 * 86400}), spv)
    _ck(c18["verdict"] == "no_closes_ever" and f18,
        f"a green-but-empty book must be the loudest verdict: {c18['verdict']}")

    # -- 18b. THE SAME INPUT ON A DARK LEDGER MUST RULE ON NOTHING ---------
    # [2026-07-22] Every build_ctx failure path leaves closes == {}, which is
    # byte-identical to "this book has no closes". Before ledger_ok, case 18's
    # ACTION finding fired on a dead DB — fabricated evidence, on the LIVE
    # books, at the loudest severity. The two inputs differ ONLY by ledger_ok,
    # so this case pins the distinction rather than the wording.
    f18b, c18b = check_evidence(
        _ctx(closes={}, ledger_ok=False,
             pnl={"T_E1": {"status": "online", "equity": 1000.0}},
             first_seen={"T_E1": 1_000_000.0 - 9 * 86400}), spv)
    _ck(c18b["verdict"] == "undetermined" and not f18b,
        f"a DARK ledger must rule on nothing, got {c18b['verdict']} "
        f"with {len(f18b)} finding(s)")
    _ck(c18["verdict"] != c18b["verdict"],
        "no-closes and cannot-read must not collapse to the same verdict")

    # -- 19. evidence: an unreachable gate is construction, not a slow week -
    # returns must VARY, or sd == 0 and the n_mde* assertion below passes for
    # the wrong reason (a constant-substitution bug would survive it).
    slow = [_close("X", i * 24 * 30.0, i * 24 * 30.0 + 1, "x_tp", 1.0,
                   pct=0.01 * (i + 1))
            for i in range(3)]
    f19, c19 = check_evidence(
        _ctx(closes={"T_E1": slow}, pnl={}, first_seen={}), spv)
    _ck(c19["verdict"] == "gate_unreachable",
        f"2.5 trades/quarter must be gate_unreachable, got {c19['verdict']}")
    _ck(c19["n_mde_star"] is None and c19.get("mde_note"),
        "no friction measured => n_mde* null AND the omission stated")
    _ck("OVERFIT" in (c19.get("power_basis") or ""),
        f"falling back to n_obs* must be STAMPED as overfit-prone, got "
        f"{c19.get('power_basis')}")

    # -- 19b. a book too young to project must say so, not claim a gate -----
    young = [_close("X", i * 6.0, i * 6.0 + 1, "x_tp", 1.0, pct=0.01 * (i + 1))
             for i in range(3)]          # ~13h of history
    f19b, c19b = check_evidence(_ctx(closes={"T_E1": young}, pnl={},
                                     first_seen={}), spv)
    _ck(c19b["verdict"] == "too_young_to_judge" and not f19b,
        f"13h of history must not be extrapolated to 30d: {c19b['verdict']}")

    # -- 20. evidence: no fleet-wide friction constant may be substituted ---
    _ck("mde_note" in c19 and "per-book" in c19["mde_note"],
        "the mde omission must say WHY no constant was substituted")

    # -- 20b. a huge MDE must read COST-BLOCKED, never "powered" ------------
    # measured today: the taker shadow's slip median is 747.6bps (BOT is 56% of
    # its orders), so mde = 15%/trade against a per-trade sd of 2.6%. n_mde*
    # collapses to 1 and the book would otherwise print as fully powered.
    fat = [_close("X", i * 3.0, i * 3.0 + 1, "x_tp", 1.0, pct=0.02 * ((i % 5) - 2))
           for i in range(40)]
    f20, c20 = check_evidence(
        _ctx(closes={"T_E1": fat},
             orders={"T_E1": {"n": 165, "n_slip": 165, "n_echo": 1,
                              "echo_frac": 0.006, "slip_med": 747.6,
                              "mde": 0.1504, "by_coin": {}}},
             pnl={}, first_seen={}), spv)
    _ck(c20["verdict"] == "cost_blocked",
        f"a 15%/trade MDE must be cost_blocked, not powered: {c20['verdict']}")
    _ck(c20["t_zero_cost"] is not None,
        "the t at ZERO cost must be reported so cost-blocked is legible")
    _ck(any("COST-BLOCKED" in x["summary"] for x in f20),
        "cost-blocked must surface as a finding, not just a card field")

    # -- 21. knob census: a parse failure must be DARK, not '0 unlevered' ---
    spk = _spec(row="T_K1", module="tiny.py", knob_floor=20,
                knob_reasons={"HARD_STOP": ["*_stop"]})
    ctxk = _ctx(src={"tiny.py": 'A = float(os.environ.get("A", "1"))\n'},
                closes={"T_K1": [_close("X", 0, 1, "long_stop", -5.0)]})
    f21, c21 = check_lever_authority(ctxk, spk)
    _ck("dark" in c21["knobs"] and not f21,
        f"a 1-knob parse under a floor of 20 must be dark: {c21['knobs']}")
    _ck(any("T_K1.knobs" in d for d in ctxk["dark"]),
        "the parse-failure dark marker must be recorded")

    # -- 22. knob census: attribution below the n floor is NOT a headline ---
    src22 = "".join(f'K{i} = float(os.environ.get("K{i}", "1"))\n' for i in range(25))
    src22 += 'HARD_STOP = float(os.environ.get("HARD_STOP", "0.1"))\n'
    # a knob whose default is an EXPRESSION, not a quoted literal — the sniper
    # writes `str(6 * 3600)`. Requiring a quoted default silently drops it, and
    # a census that under-counts knobs under-reports the unlevered surface.
    src22 += 'EXPR_KNOB = float(os.environ.get("EXPR_KNOB", str(6 * 3600)))\n'
    spk2 = _spec(row="T_K2", module="tiny2.py", knob_floor=20,
                 knob_reasons={"HARD_STOP": ["*_stop"]})
    closes22 = ([_close("X", i, i + 1, "long_stop", -2.0) for i in range(2)]
                + [_close("Y", 10 + i, 11 + i, "long_tp", 1.0) for i in range(10)])
    f22, c22 = check_lever_authority(
        _ctx(src={"tiny2.py": src22}, closes={"T_K2": closes22}), spk2)
    hot = [h for h in c22["knobs"]["attributed"] if h["knob"] == "HARD_STOP"]
    _ck(hot and hot[0]["attribution"].startswith("insufficient"),
        f"n=2 must report insufficient, not a 51% headline: {hot}")
    _ck(not any(x["klass"] == "unlevered_knob" for x in f22),
        "an n=2 knob must not raise a finding")
    _ck(hot and hot[0]["gross_loss_usd"] == 4.0,
        "the DENOMINATOR must be published beside the share")
    _ck("EXPR_KNOB" in c22["knobs"]["unlevered"],
        "a knob with a computed default must still be censused")

    # -- 23b. loss owned by a LEVERED knob is attributed, not "unattributed" -
    # otherwise unattributed_share reads 1.0 on a perfectly-mapped book and the
    # map-rot signal cries wolf.
    spk3 = _spec(row="T_K3", module="tiny3.py", knob_floor=1,
                 knob_reasons={"TP": ["*_tp"]})
    src3 = ('TP = float(os.environ.get("TP", "0.04"))\n'
            'x = tuning.get_lever("a.tp", TP)\n')
    cl3 = [_close("X", i, i + 1, "long_tp", -1.0) for i in range(6)]
    _, c23b = check_lever_authority(
        _ctx(src={"tiny3.py": src3}, closes={"T_K3": cl3}), spk3)
    _ck(c23b["knobs"]["unattributed_share"] == 0.0,
        f"a levered knob's loss must still count as attributed: "
        f"{c23b['knobs']['unattributed_share']}")
    _ck(not any(h["knob"] == "TP" for h in c23b["knobs"]["attributed"]),
        "a LEVERED knob must not be reported in the unlevered-hot list")

    # -- 23. knob census: a LEVERED knob is not reported unlevered ----------
    src23 = src22 + '\nea = tuning.get_lever("x.enter", HARD_STOP)\n'
    f23, c23 = check_lever_authority(
        _ctx(src={"tiny2.py": src23}, closes={"T_K2": closes22}), spk2)
    _ck("HARD_STOP" not in c23["knobs"]["unlevered"],
        "a knob named on a get_lever line must count as levered")

    # -- 24. ranking: real money first --------------------------------------
    # the SHADOW finding is deliberately the more severe one, so only the
    # real-money key can put the live finding first — otherwise severity alone
    # would pass the test and a dropped live-first rule would survive.
    a = _finding("evidence", "evidence_starvation", "T_X1", "action", "shadow")
    b = _finding("evidence", "evidence_starvation", "T_E1", "warn", "live")
    a["live"], b["live"] = False, True
    _ck(rank_findings([a, b])[0] is b,
        "real-money findings must rank first, ABOVE a more severe shadow one")

    # -- 25. clip authority is a DISCRETE-outcome count, not a distribution --
    ca = clip_authority({"lo": 0.5, "hi": 1.5}, 25.0, 30.0)
    _ck(ca["verdict"] in ("healthy", "inert") and ca["reach"] >= 1,
        f"clip authority must be computable: {ca}")
    ca2 = clip_authority({"lo": 0.5, "hi": 1.5}, None, None)
    _ck(ca2["verdict"] == "dark", "unknown clip/cap must be dark")

    # -- 25b. the clock must come from the DB, not this process ------------
    class _FakeCur:
        def execute(self, q):
            self.q = q

        def fetchone(self):
            return (1_700_000_000.0,)

    class _DeadCur:
        def execute(self, q):
            raise RuntimeError("no db")

    _ck(db_now(_FakeCur(), 1.0) == 1_700_000_000.0,
        "db_now must PREFER the database clock over the local one")
    _ck(db_now(_DeadCur(), 42.0) == 42.0,
        "db_now must fall back, never raise, when the DB is unreachable")

    # -- 26. freshness fails CLOSED ----------------------------------------
    _ck(_fresh(None, 1.0) is False and _fresh({"updated": "x"}, 1.0) is False,
        "freshness must fail closed on junk")

    for row in ("TEST", "T_CONC1", "T_CONC2", "T_G1", "T_G2", "T_G3",
                "T_G4", "T_S1", "T_X1", "T_X2", "T_E1", "T_K1", "T_K2",
                "T_K3"):
        BOOKS.pop(row, None)

    if _FAILS:
        print("fleet_agronomy SELFTEST FAILED:")
        for m in _FAILS:
            print("  ✗", m)
        sys.exit(1)
    print(f"fleet_agronomy selftest OK — {len(CHECKS)} checks, "
          f"{len(KLASSES)} classes, 32 cases "
          "(lever authority incl. unit adapter + dark tape, episode collapse, "
          "sign-split concentration, guard probes A+B, publisher-first signal "
          "verdicts, echo-fill trap, three-state lens gap, green-but-empty "
          "book, knob-parse floor, real-money ranking)")


def _syd(iso):
    """Operator-facing times are Sydney-local, labelled. Fleet INTERNALS stay
    UTC (the payload's updated/ttl_sec contract) — this is a display rule."""
    t = _parse_ts(iso)
    if t is None:
        return str(iso)
    # AEST = UTC+10 in July (no DST in the southern winter).
    d = datetime.fromtimestamp(t + 10 * 3600, timezone.utc)
    return d.strftime("%Y-%m-%d %H:%M") + " Sydney (AEST)"


def _report(payload):
    print(f"🌱 fleet-agronomy  {_syd(payload['updated'])}  "
          f"window {payload['window_d']}d  mode={payload['mode']}")
    c = payload["counts"]
    print(f"   books={c['books']}  findings={payload['n_findings']}  "
          f"dark={c['dark']}  status={c['by_status']}")
    print(f"   by class: {c['by_class']}")
    print("\n-- RANKED FINDINGS (real money first) " + "-" * 40)
    for i, f in enumerate(payload["findings"], 1):
        flag = "💰LIVE" if f["live"] else "shadow"
        print(f"{i:2d}. [{f['severity'].upper():6s}][{flag}] {f['book']} "
              f"({f['klass']})\n     {f['summary']}")
    print("\n-- PER-BOOK VERDICTS " + "-" * 55)
    for row, card in sorted(payload["books"].items(),
                            key=lambda kv: (not kv[1]["live"], kv[0])):
        v = card["verdict"]
        b = v["binding_constraint"]
        print(f"{'💰' if card['live'] else '  '} {row:34s} {v['status']:7s} "
              f"n={v['n_findings']}")
        if b:
            print(f"     binding: [{b['klass']}] {b['summary']}")
    if payload["dark"]:
        print("\n-- DARK SENSORS " + "-" * 60)
        for d in payload["dark"]:
            print("   •", d)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        # [2026-07-22] PUBLISH IS OPT-IN. This was `publish unless --print/
        # --no-publish`, so a bare `python3 fleet_agronomy.py` — the obvious
        # thing to type while developing it — wrote a 102KB row to PRODUCTION
        # bot_state, and it had to be deleted by hand. An organ with no
        # consumer, no run_all.sh loop and no image COPY has no business
        # writing to the live bus by default. Wiring it in is a review
        # decision; when that happens the loop passes --publish explicitly.
        pub = "--publish" in sys.argv
        p = run_once(publish=pub)
        if "--json" in sys.argv:
            print(json.dumps(p, indent=1, default=str))
        else:
            _report(p)
