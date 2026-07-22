#!/usr/bin/env python3
"""
lighter_ticket_taker.py — 🎫 Ticket Taker: the scanner's designated trader (SHADOW).

WHAT / WHY (2026-07-14, user ask: "when a scanner finds something incredible,
the bot designated to that particular find absorbs the scanner's findings and
makes a trade")
  Lighter Scout publishes per-strategy TICKETS (breakout / dip / momentum
  lenses over every liquid Lighter book). Until now nothing traded them —
  publish-first doctrine. This bot is the designated consumer: a $1,000
  SHADOW book that takes only the HIGH-CONVICTION subset of each lens (the
  "incredible" bars below), models fills at Lighter's own mark price via
  PaperBroker (fees included), accrues hourly funding drag from the venue's
  funding feed, and exits on TP / SL / max-hold.

  Every close is tagged long_<lens>_<exit> in the durable paper_trades
  ledger, so the LEARNING BRAIN grades each lens on real forward returns
  (bot_learn already ingests that ledger). That closes the loop the user
  asked for: scanner finds -> designated bot trades -> brain learns which
  lens actually has an edge -> only graded lenses ever graduate.

  UNVALIDATED BY DESIGN (like every new shadow book: Perp Sniper, Snap Back):
  the lens rules cannot be backtested — they need forward data, which is
  exactly what this book collects. Run-once process; run_all.sh loops it every
  5 min. Broker state + entry metadata persist in bot_state so redeploys
  continue the same equity curve.

  THE LIVE PATH EXISTS AND IS REFUSED (see main()). It is built so the switch
  is one env var WHEN the evidence lands — not a claim that it has.

Usage:
    python3 lighter_ticket_taker.py             # one management cycle
    python3 lighter_ticket_taker.py --selftest  # offline accounting checks
    python3 lighter_ticket_taker.py --selftest-live
                                     # drive the LIVE order path end-to-end
                                     # against a stub venue (no network, no
                                     # signer, no money) — see _selftest_live()
"""
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import bot_pnl_store as store
import funding_basis
from paper_broker import PaperBroker
# [2026-07-17] The fill read is SHARED with the live Funding Farmer now
# (venues/fills.py), not copied. The copy is what let the two drift: this bot
# stamped measured=True on any price the venue returned and had no fallback when
# the client id missed, where the Farmer derived measured from the venue's own
# label and fell back once. Two live bots disagreeing about what "measured"
# means is not a style problem — implementation_shortfall compares their rows.
from venues.fills import measured_from_reason, read_fill, slip_bps_of
# Module scope, same reason as venues.safety below: this bot keys everything by
# the venue-native symbol while LighterClient.positions() speaks FLEET symbols,
# and the conversion between them is a real-money rule (see _positions()). A
# lazy import inside the live branch is one the born-dark audit cannot see.
from venues.symbol_map import from_lighter, to_lighter


def _fleet(sym):
    """venue-native symbol -> FLEET symbol: the space LighterClient's API speaks.

    [2026-07-17] The client is fleet-symbol'd END TO END — positions() runs every
    symbol through from_lighter(), and market_close() looks the coin up IN THAT
    DICT (venues/lighter_client.py:558). Its _resolve() happens to tolerate a
    native symbol (to_lighter is identity for "1000BONK"), which is exactly what
    makes this dangerous: market_OPEN accepts native and works, while
    market_CLOSE accepts native, misses the lookup, and returns None WITHOUT
    RAISING. Open succeeds, close silently no-ops, and the position is stranded.
    So: convert at EVERY venue call, not just the ones that fail loudly.
    """
    return from_lighter(sym)[0]
# The notional-cap rule lives on the rail that enforces it. Imported at module
# scope on purpose (not lazily inside the live branch): the born-dark guard
# reads static imports, and a money rule that only materialises on the live
# path is a money rule the image audit cannot see. venues/safety.py is
# dependency-free — no SDK, no network — so this costs the shadow arm nothing.
from venues.safety import open_notional

# [2026-07-17 LIVE PATH] The taker was PAPER-ONLY BY CONSTRUCTION: PaperBroker
# modelling its own fills at a flat 4bps, a hardcoded -lshadow row, and no
# venue client, signer, order path or SafetyRails anywhere. Setting
# VENUE=lighter_live on the service would NOT have placed one order — it would
# have published paper P&L into a real-money row, which looks like it works.
# That is the failure this wiring removes.
#
# Modes (TT_VENUE, default lighter_shadow — the fleet's fail-safe default):
#   lighter_paper  the legacy book: PaperBroker, modelled fills, flat fee.
#                  KEPT so the existing -lshadow equity curve stays continuous
#                  and comparable; it is a MODEL, not execution.
#   lighter_shadow ShadowBroker: fills WALK THE REAL LIGHTER BOOK (crossing the
#                  spread at our clip) and every order lands in venue_orders
#                  with decision-vs-fill slippage. This is the arm that earns a
#                  go-live, because it is the only one measuring real execution.
#   lighter_live   REFUSED — see the guard in main(). Divergence is the only
#                  lens with forward evidence and it has n=7 (~2 fills of
#                  swing) against a 30-day gate. The path exists so the switch
#                  is one env var WHEN the evidence lands; it is not a promise
#                  that it has.
#
# [2026-07-17] TT_VENUE KEEPS its default, deliberately — unlike $VENUE on the
# two real-money bots, which f44e3eb just made MANDATORY ("a default is fine
# for a preference, never for an IDENTITY that decides whether real money
# moves"). The rule is the same; the exposure is not. This bot has no service
# of its own: run_all.sh loops it inside the shared freqtrade-bots container
# with no env, so a mandatory var would simply kill the shadow arm that is
# collecting the only evidence a go-live could rest on. And an unset var CANNOT
# produce a live taker — live requires the literal string "lighter_live", which
# is explicit by construction, so the lost-var case fails SAFE here rather than
# silently-live.
# GO-LIVE PRECONDITION (write it down now, while it is cheap): the live arm
# must be its OWN Railway service with TT_VENUE set explicitly.
# [2026-07-17 DONE — that service exists: Dockerfile.tickettaker +
# railway.tickettaker.toml, and the mandatory guard is now in main(). The module
# default below is what run_all.sh's shadow arm no longer relies on: it DECLARES
# TT_VENUE=lighter_shadow on the command line, because with the guard in place
# an unset var is a refusal, not a fallback. Keep the default only so the four
# modules that import this file (replay/tuner/incubator/proprioception) can read
# the bars without an env.]
TT_VENUE = os.environ.get("TT_VENUE", "lighter_shadow").strip() or "lighter_shadow"
TT_MODES = ("lighter_paper", "lighter_shadow", "lighter_live")

try:
    import fleet_tuning as tuning     # growth rail (optional import)
except Exception:  # noqa: BLE001
    tuning = None

# [2026-07-17] the row follows the MODE — a live arm must never publish into
# the shadow arm's curve (and vice versa). paper/shadow share -lshadow on
# purpose: same book, better fill model, one continuous curve.
BOT = "lighter-ticket-taker"
_ROW_SUFFIX = {"lighter_paper": "-lshadow", "lighter_shadow": "-lshadow",
               "lighter_live": "-lighter"}
BOT_ROW = BOT + _ROW_SUFFIX.get(TT_VENUE, "-lshadow")
STATE_KEY = "lighter-ticket-taker"
# [2026-07-17 LIVE PATH] The live arm keeps its OWN state key. STATE_KEY holds
# a PaperBroker/ShadowBroker snapshot (a local account); a live arm restoring
# that would inherit the shadow book's equity curve and open positions as if
# they were its own. Live persists only what a live arm can legitimately
# remember: the P&L baseline and per-position meta (the max-hold clock, entry
# clip and lens) — the ACCOUNT itself lives on the venue. Mirrors
# lighter_funding_bot's `bot_id + ":live"`.
LIVE_STATE_KEY = STATE_KEY + ":live"
SCOUT_KEY = "lighter-market"
API_BASE = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")

START_EQUITY = 1000.0
# [2026-07-21 D1] CAPITAL IS NOT P&L. The EquityGuard records the deposits/
# withdrawals it accepts (pop_capital_moves); they accumulate in the persisted
# LIVE_STATE_KEY blob, and this env knob backfills moves that predate the
# mechanism. Default = this book's 18-Jul deposit as measured in the
# fleet-equity series (+$32.22 @ 07:37Z — review 2026-07-21 N1; printed as
# profit until this fix). Override with the exact figure if known; set to 0
# if initial_equity is ever re-baselined by hand.
CAPITAL_ADJUST_USD = float(os.environ.get("CAPITAL_ADJUST_USD", "32.22"))
CLIP_USD = float(os.environ.get("TT_CLIP_USD", "50"))   # fallback when no vol data
MAX_OPEN = int(os.environ.get("TT_MAX_OPEN", "6"))
# [2026-07-14c CONSTANT-RISK SIZING] Fixed $ clips carry wildly different risk
# across books (a $50 clip in a 10%-range alt is ~5x the risk of $50 in BTC).
# Size so every position risks ~the same dollars: expected adverse move ~ half
# the daily range, clip = RISK_USD / adverse, bounded. The brain still grades
# per-lens on pnl_pct (per-clip), so sizing doesn't distort lens grading.
RISK_USD = float(os.environ.get("TT_RISK_USD", "1.5"))
CLIP_MIN = float(os.environ.get("TT_CLIP_MIN", "20"))
CLIP_MAX = float(os.environ.get("TT_CLIP_MAX", "80"))
TAKE_PROFIT = float(os.environ.get("TT_TP", "0.04"))       # +4%
STOP_LOSS = float(os.environ.get("TT_SL", "-0.03"))        # -3%
MAX_HOLD_H = float(os.environ.get("TT_MAX_HOLD_H", "48"))
# [2026-07-16 ZOMBIE GUARD] a delisted/vanished book used to mean "hold
# forever" (exit_reason needs a mark, so even max-hold was unreachable) —
# the position froze at its last mark and ate a MAX_OPEN slot for good.
# After this many hours continuously unpriceable, close at the last known
# mark (entry if none was ever seen) — the sniper's 2-Jul give-up, ported.
DELIST_GIVEUP_H = float(os.environ.get("TT_DELIST_GIVEUP_H", "6"))

# "Incredible" — the conviction bars. A ticket must clear its lens's bar to
# be taken; ordinary tickets stay advisory for the weekly lens grading.
BRK_RANGE = float(os.environ.get("TT_BRK_RANGE", "0.95"))  # at the daily high
BRK_VOL_M = float(os.environ.get("TT_BRK_VOL_M", "1.0"))   # >= $1M/day
DIP_RANGE = float(os.environ.get("TT_DIP_RANGE", "0.05"))  # pinned to the low
MOMO_CHG = float(os.environ.get("TT_MOMO_CHG", "5.0"))     # >= +5% day
# [2026-07-21] hours a symbol stays entry-blocked after ITS OWN stop-loss
# close (0 disables). Measured basis: same-minute SL->re-enter churn, every
# instance a loser (NBIS -$5.37/8, BOT -$4.60/3 on the 17-20 Jul tape).
SL_COOLDOWN_H = float(os.environ.get("TT_SL_COOLDOWN_H", "2.0"))


def _sl_active(until_iso, t_now):
    """True while a post-stop cooldown stamp is still in the future. Junk
    stamps read as inactive (fail-open — a corrupt stamp must not embargo a
    symbol forever). Pure; selftested."""
    try:
        return parse_ts(until_iso) > t_now
    except (ValueError, TypeError):
        return False
MOMO_VOL_M = float(os.environ.get("TT_MOMO_VOL_M", "2.0")) # >= $2M/day
# [2026-07-14b] Divergence lens: receive Lighter's funding when it diverges
# this hard (percentage points of APR) from the cross-venue median.
# [2026-07-17] /8 with the fleet basis fix — same decision, true units.
DIV_GAP_PP = float(os.environ.get("TT_DIV_GAP", "62.5"))
# [2026-07-22 COIN-QUALITY VETO — the third "kill switch that never reached the
# consumer"] market_context publishes bot_state 'coin-vetoes'. TWO bars, not one
# (market_context.py:396-399): measured |slip| > 15bps over >=5 orders in 14d,
# **OR** stop-rate >= 50% over >=5 closes in 30d — pooled FLEET-WIDE across every
# bot, so a coin can arrive here on another book's stop-outs with clean slippage
# of its own (ADA today: stop-rate veto, 3.65bps slip). Do not describe this set
# as "slippage" anywhere the operator reads it. It was the fleet's
# one automated restrict-only actuator, and until now its ONLY consumer was
# lighter_funding_bot.py:1033 — the taker never read it.
# WHAT THAT COST, measured 22-Jul: BOT/USDC carries **747.6 bps** mean absolute
# slippage over 93 taker orders (81.9bps spread); the next-worst book it trades
# is SOXL at 20.9. On 22-Jul the taker put 44 of its 52 closes through BOT, and
# the short-divergence lens' realised mean went to -0.695%/trade — while the
# BRAIN still grades the divergence SIGNAL positive (ehit4h 0.536 [0.516,0.557],
# n=10522) because it grades tickets counterfactually, not slipped fills.
# The lens never decayed. One un-vetoed book was eating it.
# Contract mirrors the Farmer's verbatim: RESTRICT-ONLY, fail-OPEN on a missing
# or STALE payload (a fossil veto set is not evidence), kill switch below.
QUALITY_VETO = os.environ.get("TT_QUALITY_VETO", "on").strip().lower() \
    not in ("0", "off", "false", "no")
QUALITY_VETO_TTL_S = float(os.environ.get("TT_VETO_TTL_S", "3600"))
# [2026-07-21 DIAGNOSIS; corrected same day] divergence has no liquidity
# check (breakout >= $1M, momentum >= $2M; dip has none either — the
# original "ONLY bar without one" claim was wrong) while being the only
# lens LIVE money fills — 79% of bar-clearing divergence tickets sat on
# books under $1M/day. SHIPPED DISABLED (0 = off), and the
# fill-ledger counterfactual (scripts/study_div_vol_floor.py, 37 shadow +
# 5 live closes, volumes matched at open time 42/42) REJECTS every tested
# floor {0.25, 0.5, 1.0, 2.0}: none improves both halves — the seductive
# full-window winner (1.0: +$10.32 vs +$2.21) is a pure second-half effect,
# and thin-print P&L flips sign between halves, so volume is not a stable
# loss predictor on this tape. The knob exists for the day the evidence
# supports it (re-test at ~n>=60 per the script header); until then 0.
DIV_VOL_M = float(os.environ.get("TT_DIV_VOL_M", "0"))
# [2026-07-14b] Stress veto: when the venue-wide |premium| median is at or
# above this (bps), the whole venue is dislocated — take NO new entries this
# cycle (exits keep running). Normal tape prints ~6bps median.
STRESS_VETO_BPS = float(os.environ.get("TT_STRESS_VETO_BPS", "15"))
# [2026-07-17 LIVE PATH] Per-bot daily-loss rail, as a FRACTION of the day's
# starting equity — the strategy-side rail every funded bot carries on top of
# SafetyRails' absolute fleet rail (LIGHTER_MAX_DAILY_LOSS). Either one firing
# flattens the book and halts for the rest of the UTC day. Live-only.
DAILY_LOSS_LIMIT = float(os.environ.get("TT_DAILY_LOSS_LIMIT", "0.05"))


# [2026-07-15 GROWTH RAIL] The tuner (lighter_scout_tuner.py) may move the
# conviction bars / exit ladder within fleet_tuning's hard bounds — but ONLY
# after the change beat/matched baseline on BOTH halves of the recorded tape
# through this module's own decision code. Levers expire on their own; the
# env defaults above stay authoritative whenever no live lever exists.
TUNABLE = (("taker.dip_range", "DIP_RANGE"),
           ("taker.brk_range", "BRK_RANGE"),
           ("taker.momo_chg", "MOMO_CHG"),
           ("taker.div_gap_pp", "DIV_GAP_PP"),
           ("taker.tp", "TAKE_PROFIT"),
           ("taker.sl", "STOP_LOSS"),
           ("taker.max_hold_h", "MAX_HOLD_H"),
           # [2026-07-21] the post-stop cooldown joins the growth rail: the
           # stamp at close reads the module attr, so a lever overlay moves
           # future stamps (never an already-written sl_block entry).
           ("taker.sl_cooldown_h", "SL_COOLDOWN_H"))


def apply_tuning():
    """Overlay live growth-rail levers onto the module bars. Returns what
    moved (for the log). Defaults untouched when no lever is live.

    [2026-07-17 NOT ON REAL MONEY] The `taker.*` levers live in the
    `lighter-taker` lane — fleet_tuning.py documents it as "the $1k SHADOW
    book's bars", its author is `scout-tuner` (which has NO live authority and
    is gated by a replay over SHADOW tape), and it sits in ENACT_LANES by
    default. Taking this bot live would silently promote a shadow lane into a
    real-money lane: a shadow-replay-gated author would be steering real clips,
    which is exactly what `_LIVE_PREFIX_OWNERS` exists to prevent. Fleet
    doctrine is that ONLY `live.*` levers may steer real money, and only their
    bound author may write them. So live runs the OPERATOR's env bars, full
    stop. If the live clip should ever be tunable it goes through the existing
    board-owned `live.clip_scale` (bounded, TTL'd, and already reverted at the
    consumer when proprioception grades it hurting) — not through this door.
    """
    if TT_VENUE == "lighter_live":
        return {}
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in TUNABLE:
        cur = globals()[attr]
        val = tuning.get_lever(lever, cur)
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _get(path):
    req = urllib.request.Request(API_BASE + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_marks_and_funding():
    """{sym: mark}, {sym: hourly_rate}, {sym: day_range_pct} — keyless API."""
    obd = _get("/api/v1/orderBookDetails")
    marks, ranges = {}, {}
    for b in obd.get("order_book_details") or []:
        try:
            if b.get("status") == "active" and float(b.get("mark_price") or 0) > 0:
                sym = b["symbol"]
                marks[sym] = float(b["mark_price"])
                hi = float(b.get("daily_price_high") or 0.0)
                lo = float(b.get("daily_price_low") or 0.0)
                if hi > lo > 0:
                    ranges[sym] = 100.0 * (hi - lo) / marks[sym]
        except (TypeError, ValueError):
            continue
    fr = _get("/api/v1/funding-rates")
    funding = {}
    for r in fr.get("funding_rates") or []:
        try:
            if r.get("exchange") == "lighter" and r.get("rate") is not None:
                funding[r["symbol"]] = float(r["rate"])
        except (TypeError, ValueError):
            continue
    return marks, funding, ranges


# ---------------------------------------------------------------------------
# PURE DECISION LOGIC (unit-tested offline)
# ---------------------------------------------------------------------------

def vol_clip(day_range_pct):
    """Constant-risk clip: RISK_USD / expected adverse move (~half the daily
    range, floored at 0.5%), bounded [CLIP_MIN, CLIP_MAX]. Falls back to
    CLIP_USD when the book has no range data."""
    if not day_range_pct or day_range_pct <= 0:
        return CLIP_USD
    adverse = max(day_range_pct / 2.0, 0.5) / 100.0
    return round(min(CLIP_MAX, max(CLIP_MIN, RISK_USD / adverse)), 2)


ALL_LENSES = frozenset({"breakout", "dip", "momentum", "divergence"})
# [2026-07-17 LIVE = DIVERGENCE ONLY — operator decision] The live arm may fill
# ONE lens. The brain grades the other three NEGATIVE at n=1279-2620 with
# hit-rate 95% CIs entirely below 50% (dip -0.471%/.392, breakout -0.210%/.399,
# momentum -0.365%/.394) — three independent dip-buyer rejections across the
# fleet's history. Real money does not get to re-litigate that.
LIVE_LENSES = frozenset({"divergence"})


def allowed_lenses(mode):
    """Hard per-MODE lens allow-list. Fail-CLOSED, and deliberately NOT the
    brain's veto.

    Why this exists ALONGSIDE vetoed_lenses(): that one is RESTRICT-ONLY and
    fail-safe OPEN by design — a dark brain, a stale payload, a DB read blip or
    a lens dropped from the grade set all collapse to "veto nothing". That is
    correct for a shadow book whose JOB is grading every lens. It is
    catastrophic as the ONLY thing standing between real money and a lens the
    fleet has already rejected three times. Four independent paths re-enable
    dip/breakout/momentum with no error; none of them can reach this function,
    because it reads no bus payload at all.

    `mode` is taken EXPLICITLY rather than read off module-level TT_VENUE: four
    modules import this one (lighter_ticket_replay, lighter_scout_tuner,
    strategy_incubator, fleet_proprioception) and every one must keep grading
    ALL FOUR lenses on the shadow tape. A module-level read would make their
    behaviour depend on the importing process's environment — the exact
    "env silently decides real-money semantics" trap the 17-Jul VENUE fix
    closed. The brain's veto stays SENIOR on top of this (restrict-only).
    """
    return LIVE_LENSES if mode == "lighter_live" else ALL_LENSES


def lens_evidence(o, min_n=None):
    """(n, floor_met, avg_pct, hit) for one lens grade — EPISODE basis when
    the brain's v3 fields are present, RAW fallback otherwise.

    [2026-07-21 IMB-24, review-sanctioned migration] Raw `n4h` counts
    serially-correlated emissions: MEASURED 8-11x per genuinely independent
    episode (31x for momentum), so a raw floor of 75 can be met by ~2-8
    independent opinions. When the v3 engine publishes episode fields
    (eps4h/n_syms/eavg4h_pct/ehit4h — validated at this review: eps4h
    117-850 across the four lenses), the floor is eps4h >= TT_LENS_VETO_MIN_EPS
    AND n_syms >= TT_LENS_VETO_MIN_SYMS, and the GRADE is the episode-deduped
    mean/hit. Fallback to the raw rule when episode fields are absent keeps
    the restrict capability under a v2 brain relapse (which the immune organ
    pages on independently)."""
    o = o or {}
    if o.get("eps4h") is not None:
        eps_min = int(os.environ.get("TT_LENS_VETO_MIN_EPS", "25"))
        syms_min = int(os.environ.get("TT_LENS_VETO_MIN_SYMS", "10"))
        floor = ((o.get("eps4h") or 0) >= eps_min
                 and (o.get("n_syms") or 0) >= syms_min)
        return ((o.get("eps4h") or 0), floor,
                (o.get("eavg4h_pct") or 0), (o.get("ehit4h") or 0))
    if min_n is None:
        min_n = int(os.environ.get("TT_LENS_VETO_MIN_N", "75"))
    n = o.get("n4h") or 0
    return n, n >= min_n, (o.get("avg4h_pct") or 0), (o.get("hit4h") or 0)


def vetoed_lenses(lens_fwd, min_n=None):
    """THE lens veto rule, and the single authority for it (2026-07-17): a
    lens the brain grades negative at sample size stops getting fills.

    Extracted from this module's own loop so the rule has ONE definition. It
    had two — the loop below and lighter_scout_tuner.vetoed_lenses — and a
    third was about to appear in strategy_incubator, which breeds the very
    bars this veto decides are worthless. Consumers must not drift on the
    question "is this lens allowed to trade?".

    [2026-07-21 IMB-24] Evidence basis migrated to EPISODES via
    lens_evidence() — measured consequence on the 21-Jul payload, recorded
    honestly: dip flips allowed->vetoed (raw hit4h 0.505 vs episode ehit4h
    0.495 — the dedup'd number sits on the other side of coin-flip).
    Restrict-only, shadow-book consequence only (the LIVE taker's
    allowed_lenses is divergence-only regardless).

    RESTRICT-ONLY and fail-safe open: an empty/missing grade set vetoes
    nothing (freshness is the CALLER's job — see the loop and the tuner)."""
    out = set()
    for lens, o in (lens_fwd or {}).items():
        _n, floor_met, avg, hit = lens_evidence(o, min_n=min_n)
        if floor_met and avg < 0 and hit < 0.5:
            out.add(lens)
    return out


def incredible(tickets):
    """The high-conviction subset of the scout's tickets, per lens."""
    out = []
    for t in (tickets.get("breakout") or []):
        if t.get("range_pos", 0) >= BRK_RANGE and t.get("vol_m", 0) >= BRK_VOL_M:
            out.append(("breakout", t))
    for t in (tickets.get("dip") or []):
        if t.get("range_pos", 1) <= DIP_RANGE:
            out.append(("dip", t))
    for t in (tickets.get("momentum") or []):
        if t.get("chg_pct", 0) >= MOMO_CHG and t.get("vol_m", 0) >= MOMO_VOL_M:
            out.append(("momentum", t))
    for t in (tickets.get("divergence") or []):
        if (abs(t.get("gap_pct") or 0) >= DIV_GAP_PP
                and (DIV_VOL_M <= 0 or t.get("vol_m", 0) >= DIV_VOL_M)):
            out.append(("divergence", t))
    return out


def live_boot_gate(rails, live):
    """The BOOT half of the rails for a RUN-ONCE live arm. Returns a refusal
    string, or None to proceed. Pure — unit-tested in selftest().

    THE RULE, and why it differs from every daemon in this fleet: the cap is a
    hard boot gate; the KILL SWITCH IS NOT — it must be allowed to reach
    _flatten_all() + halt in main().

    venues/safety.py promises both halves ("refuses to start — and
    flattens+halts mid-run"), and for a daemon both hold: the funding bot is
    already looping when the switch is armed, so kill_check() fires and closes
    the book. This bot is run-once — EVERY CYCLE IS A BOOT — so
    assert_can_start() would raise before kill_check() is ever reached, and the
    flatten would be unreachable dead code. Arming REAL_MONEY_KILL would stop
    the position manager and STRAND the book: no stop, no max-hold, nothing
    watching it. The switch meant to protect the money would be what abandons
    it. That is not hypothetical — it is the shape of Tide Rider's live row
    right now (kill armed, boot refused, a position left for the operator to
    close by hand).

    So the kill switch still stops ALL trading on the first cycle (main() halts
    and takes no entries) — it now closes the book on the way out.
    """
    if live and rails.max_notional is None:
        return ("lighter_live requires an explicit per-bot notional cap "
                "(LIGHTER_TICKET_TAKER_MAX_NOTIONAL) — refusing to start.")
    return None


def delist_due(no_mark_since_iso, t_now, giveup_h=None):
    """True when a mark has been continuously missing since the given stamp
    for >= giveup_h. Unparseable stamp -> False (the caller re-stamps)."""
    try:
        gone_h = (t_now - parse_ts(no_mark_since_iso)).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return False
    return gone_h >= (DELIST_GIVEUP_H if giveup_h is None else giveup_h)


def exit_reason(entry, mark, opened, t_now, is_long=True, bars=None):
    """tp / sl / hold / None for a position held from `opened`.

    `bars` is an optional (tp, sl, max_hold_h) tuple — the position's OWN
    governing bars (see pos_bars). None = the module's current bars, the
    pre-(by) behavior every existing caller keeps."""
    if not entry or entry <= 0 or not mark or mark <= 0:
        return None
    tp, sl, hold_h = bars if bars else (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    ret = (mark / entry - 1.0) * (1.0 if is_long else -1.0)
    if ret >= tp:
        return "tp"
    if ret <= sl:
        return "sl"
    if (t_now - opened).total_seconds() >= hold_h * 3600:
        return "hold"
    return None


# [2026-07-22 LEVER FLAP FIX — operator: "implement the flap to all those who
# need it"] The (bw) taker-SL study measured the defect this closes: 9/22 SL
# closes were "already past the close-time bar" because a WIDER lever (sl
# -0.04) EXPIRED mid-position and the snapped-back default (-0.03) booked the
# whole gap instantly (delays up to 58m). The rule now: THE BARS PRICED AT
# ENTRY GOVERN THE TRADE. Entries stamp the bars in force into position meta;
# exits check the stamp, so a lever expiry can only change the bars of NEW
# positions. This also makes the runtime match every instrument that already
# assumes per-trade constant bars (replay sweep, judge receipts,
# proprioception counterfactuals). Entry GATES (dip/brk/momo/div) still read
# live levers — a crouch still bites new entries immediately; and the
# post-close SL_COOLDOWN_H deliberately stays close-time (it is close-side
# policy, not a bar the position was priced at). Stamps are written even with
# the switch off (attribution is free); LEVER_GRANDFATHER=off reverts the
# BEHAVIOR to close-time bars.
LEVER_GRANDFATHER = os.environ.get("LEVER_GRANDFATHER", "on").strip().lower() \
    not in ("off", "0", "no", "false", "disabled")


def entry_bars():
    """The bars in force RIGHT NOW, stamped into a new position's meta —
    exit bars (governing) plus the entry filters that admitted it
    (attribution; the filters never re-apply mid-position)."""
    return {"tp": TAKE_PROFIT, "sl": STOP_LOSS, "max_hold_h": MAX_HOLD_H,
            "div_gap_pp": DIV_GAP_PP, "div_vol_m": DIV_VOL_M,
            "dip_range": DIP_RANGE, "brk_range": BRK_RANGE,
            "momo_chg": MOMO_CHG}


def pos_bars(m):
    """(tp, sl, max_hold_h) GOVERNING an open position: its entry stamp when
    grandfathering is on and the stamp is sane, else the module's current
    bars. Fail-safe: an unstamped/legacy/junk position behaves exactly as
    before this fix."""
    try:
        if LEVER_GRANDFATHER:
            b = (m or {}).get("bars") or {}
            tp = float(b["tp"])
            sl = float(b["sl"])
            hold_h = float(b["max_hold_h"])
            if sl < 0.0 < tp and hold_h > 0.0:
                return tp, sl, hold_h
    except (KeyError, TypeError, ValueError):
        pass
    return TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H


# ---------------------------------------------------------------------------


def _setup_logging(_ctx=None):
    """[2026-07-17] Make the venue layer AUDIBLE. This bot configured NO logging,
    and Python drops `log.info` when the root logger has no handler — so the LIVE
    taker has been running BLIND to `venues/`: no signer banner (and therefore no
    lighter-sdk version), no EQUITY GUARD REJECTs, no governor 429/punish, no
    ws-degraded. Only WARNING+ ever surfaced, via the handler of last resort,
    which is exactly why `Unclosed client session` was visible and nothing else
    was. The funding bot configures logging and printed its signer's wheel on the
    first boot after the banner shipped; this bot could not, and that asymmetry
    is what exposed the hole.

    INSIDE main(), never at import. FOUR modules import this file
    (lighter_ticket_replay, lighter_scout_tuner, strategy_incubator,
    fleet_proprioception) and NONE configure logging — an import-time
    basicConfig would silently hijack the root logger for all of them inside the
    shared freqtrade-bots container. Same reason the TT_VENUE gate lives here.

    Idempotent by construction: basicConfig is a no-op when the root already has
    handlers, so a caller that configured its own logging keeps it. `_ctx` is the
    offline test path — left alone so the selftests' captured stdout stays clean.
    """
    if _ctx is not None:
        return
    logging.basicConfig(
        level=os.environ.get("TT_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout)


def main(_ctx=None):
    """One management cycle.

    `_ctx` is a TEST-ONLY injection point ({venue, rails, broker}); production
    calls main() with no args. It bypasses the EVIDENCE refusal below so the
    live order path can be driven end-to-end offline (--selftest-live). It does
    NOT bypass SafetyRails: the kill switch and the notional cap stay senior on
    every path, so an injected REAL client still cannot send an order without a
    deliberate REAL_MONEY_KILL=DISARMED_I_UNDERSTAND and an explicit cap. The
    evidence gate and the money gate are different gates — this opens neither
    for production, and only the first for a test.
    """
    # [2026-07-17 TT_VENUE MUST BE EXPLICIT — real money] This bot's identity,
    # its dashboard row, and whether it trades REAL MONEY all come from
    # $TT_VENUE, and it has no default it can safely inherit: the shadow id is
    # the row the freqtrade-bots container already publishes, so a lost var on
    # the live service would make TWO writers of one row while the live book's
    # positions went unmanaged — no page, because the row looks healthy. Same
    # class as the 17-Jul VENUE fix on the other two live bots; both services
    # set it explicitly, so this is inert for them and only makes a lost var
    # LOUD. Gated INSIDE main() on purpose: four modules import this one
    # (lighter_ticket_replay, lighter_scout_tuner, strategy_incubator,
    # fleet_proprioception) and an import-time guard would break every one.
    # _ctx is the offline test path and never trades.
    if _ctx is None and not os.environ.get("TT_VENUE", "").strip():
        raise SystemExit(
            "TT_VENUE is unset. This bot's identity — and whether it trades "
            "REAL MONEY — comes from it, and its lighter_shadow id is a row "
            "another service already publishes. An inherited default must never "
            "decide that. Set TT_VENUE=lighter_live or TT_VENUE=lighter_shadow "
            "explicitly.")
    _setup_logging(_ctx)
    moved = apply_tuning()
    if moved:
        print(f"[ticket-taker] {iso(now())} growth-rail levers active: {moved}")
    try:
        marks, funding, ranges = fetch_marks_and_funding()
    except Exception as e:  # noqa: BLE001 — keyless API down: skip this cycle
        # [2026-07-17] liveness touch on the skip path (the funding bot's
        # 12-Jul GO-GREEN rule, ported): this `return` published NOTHING, so a
        # keyless-API blip made the row go STALE — indistinguishable from a
        # dead bot. A skip is not a death; say so.
        print(f"[ticket-taker] {iso(now())} fetch failed (skipping): {e!r}")
        try:
            store.heartbeat(BOT_ROW)
        except Exception:  # noqa: BLE001
            pass
        return

    if TT_VENUE not in TT_MODES:
        raise SystemExit(f"TT_VENUE={TT_VENUE!r} unknown (expected {TT_MODES})")
    # [2026-07-17 LIVE REFUSAL LIFTED — operator decision, on the record.]
    # The refusal that stood here said: "divergence is the only fillable lens
    # and it has n=7 closes; the fleet's gate is a 30-day record. Lift it when
    # divergence has the closes — NOT to fill a vacancy." The operator was shown
    # that reasoning with the numbers and lifted it deliberately, to take Tide
    # Rider's vacated live slot. Recording what was traded away, because nobody
    # should have to re-derive it later:
    #   * THE EVIDENCE IS THIN AND KNOWN THIN. divergence's episode-deduped
    #     forward grade is +0.004%/4h (≈zero) with an ehit4h CI of 0.494-0.572
    #     STRADDLING a coin flip, while this bot's median divergence hold is
    #     6.68h. Its realized +4.23%/trade is 5-1000x the brain's forward grade
    #     of the SAME signal at n=2934 — that gap is the luck. $10.72 over 7
    #     fills is ~3 fills of swing, at 100% WR: a streak, not a record.
    #   * The fleet gate (30d WR>55% AND maxDD<15%) is NOT met. This is a
    #     deliberate exception to it, not a pass.
    #   * long-divergence has ZERO realized fills and the live arm can take it.
    # What replaced the refusal is not permission — it is guards, all landed and
    # negative-fixture tested: a fail-CLOSED live lens allow-list that does not
    # read the brain (allowed_lenses), a hard assert at the order, the symbol
    # round-trip fix, None-is-a-failed-close, TT_VENUE mandatory, apply_tuning
    # disabled live, plus the pre-existing kill switch / notional cap / equity
    # guard / daily-loss rail. REAL_MONEY_KILL is still the last gate and it is
    # the OPERATOR's to disarm.
    live = (TT_VENUE == "lighter_live")
    dry_run = not live

    t_now = now()
    venue = rails = broker = None
    if _ctx is not None:
        venue, rails, broker = _ctx["venue"], _ctx["rails"], _ctx["broker"]
    elif TT_VENUE == "lighter_paper":
        # legacy: models its own fills at a flat fee. Kept for curve continuity.
        broker = PaperBroker(start_equity=START_EQUITY, fee_bps=4.0)
    else:
        # REAL fills: ShadowBroker walks the live Lighter book at our clip and
        # writes every order to venue_orders (decision px vs modelled fill px,
        # spread + slippage). Lighter's perp fee is ZERO — the crossed spread
        # IS the cost, and it lands in the fill price rather than a flat 4bps
        # guess. This is the arm whose record can support a go-live.
        from venues.lighter_client import LighterClient
        from venues.shadow import ShadowBroker
        from venues.safety import SafetyRails
        # [2026-07-17 LIVE PATH] the signer is what separates a modelled fill
        # from a real one. shadow -> no signer, ShadowBroker walks the book;
        # live -> signer + market_open/market_close against the venue, and
        # SafetyRails demands an explicit notional cap or refuses to start.
        #
        # guard_state_key is LIVE-ONLY and load-bearing: LighterClient only
        # builds an EquityGuard when it has a signer, and vet_account_read()
        # returns the raw print unvetted when the guard is None. Omitting it
        # would have run the live arm's daily-loss rail on UNVETTED equity —
        # the exact 11-Jul failure where one dislocated print tripped the rail
        # and the flatten sold into the dislocation for a real -5.9%. The
        # funding bot gets this via venue_context(); this bot builds its client
        # directly, so it must pass it explicitly.
        venue = LighterClient(
            net="mainnet", with_signer=live,
            guard_state_key=(BOT_ROW + ":eqguard") if live else None,
            # RUN-ONCE (this file re-invokes main() every ~300s via
            # tickettaker_loop.sh / run_all.sh), so the EquityGuard must PERSIST
            # its reject streak across relaunches or the deposit-heal rebase can
            # never reach its consecutive-reject count. The long-lived Funding
            # Farmer leaves this False (keeps its redeploy streak-reset).
            guard_persist_reject_streak=live)
        rails = SafetyRails(BOT, TT_VENUE)
        # [2026-07-17 RUN-ONCE KILL SEMANTICS — deliberately NOT
        # assert_can_start() on the live arm.]
        # safety.py promises BOTH halves: lighter_live "refuses to start — and
        # flattens+halts mid-run". For a DAEMON both work: the funding bot is
        # already looping, so kill_check() fires and _flatten_all() closes the
        # book. This bot is RUN-ONCE (run_all.sh / the live loop re-invokes it
        # every 5 min), so EVERY CYCLE IS A BOOT — assert_can_start() would
        # raise SystemExit before kill_check() is ever reached, making the
        # flatten below unreachable dead code. Arming REAL_MONEY_KILL would
        # then STOP the position manager and STRAND whatever it holds, with no
        # stop and no max-hold: the switch meant to protect the money would be
        # the thing that abandons it. (That is not theoretical — it is exactly
        # the shape of Tide Rider's live row today: kill armed, boot refused,
        # a position left behind for the operator to close by hand.)
        # So: keep the CAP half as a hard boot gate, and let the kill switch
        # reach _flatten_all() + halt below. The kill switch still stops all
        # trading on the very first cycle; it now closes the book on the way.
        _refusal = live_boot_gate(rails, live)
        if _refusal:
            store.set_status(BOT_ROW, "error")
            raise SystemExit(_refusal)
        if not live:
            rails.assert_can_start()
        broker = None if live else ShadowBroker(BOT_ROW, venue, START_EQUITY)

    # State: the paper/shadow arms own a local ACCOUNT (broker snapshot); the
    # live arm's account lives on the venue and it persists only what it may
    # legitimately remember — the P&L baseline, the day-start equity and
    # per-position meta (max-hold clock, entry clip, lens).
    if dry_run:
        saved = store.load_state(STATE_KEY) or {}
        broker.restore_state(saved.get("broker") or {})
        live_baseline = None
    else:
        # [2026-07-17 AUDIT] load_state_CHECKED on the live arm. `load_state`
        # collapses "no row" and "READ FAILED" into None (bot_pnl_store.py:409
        # — its sibling's docstring calls this "a trap for any caller that
        # SEEDS durable state on an empty read"), and `or {}` then made meta={}
        # -> EVERY live position unattributable -> the dirty-account guard
        # below fired on a bot whose account was perfectly clean. One Postgres
        # blip therefore stopped the exit ladder on REAL positions while
        # telling the operator to go hunt a foreign position that never
        # existed. A read we could not perform is NOT evidence of an empty
        # account; refuse the cycle and let the 300s loop retry, rather than
        # act on a fact we do not have.
        _ok, _saved = store.load_state_checked(LIVE_STATE_KEY)
        if not _ok:
            store.set_status(BOT_ROW, "error")
            raise SystemExit(
                "lighter-ticket-taker: live state READ FAILED — cannot tell "
                "an empty account from an unreadable one, so this cycle does "
                "nothing rather than guess. Positions (if any) keep their "
                "venue-side state; the next cycle retries in ~300s. This is a "
                "TRANSIENT database condition, NOT a dirty account — do not "
                "reconcile meta on the strength of this message. If it "
                "persists, the DB is down: REAL_MONEY_KILL=DISARMED_I_UNDERSTAND "
                "still flattens (the kill switch runs above this).")
        saved = _saved or {}
        live_baseline = saved.get("initial_equity")
    # [2026-07-21 D1] persisted capital ledger — deposits the guard accepted;
    # pnl_abs subtracts it (+ the CAPITAL_ADJUST_USD backfill) so the
    # operator's own money never prints as trading profit. {} for dry_run.
    capital_adjust = (saved.get("capital_adjust") if live else None) \
        or {"total": 0.0, "events": []}
    meta = saved.get("meta") or {}          # sym -> {lens, opened, accrued_to}
    stats = saved.get("stats") or {"closed": 0, "wins": 0, "losses": 0}
    # [2026-07-21 AUDIT FIX] post-STOP re-entry cooldown: closes run before
    # entries each cycle and the only re-entry guard was 'sym in pos', so a
    # symbol whose stop-loss just fired was IMMEDIATELY eligible while the
    # scout's ticket still stood — measured churn on the shadow tape: NBIS
    # SL'd and re-opened in the SAME minute, 8 closes -$5.37; BOT 3 closes
    # -$4.60; every same-cycle re-entry lost. A stopped symbol now waits
    # TT_SL_COOLDOWN_H (persisted, both arms; tp/hold closes unaffected —
    # winners may re-enter freely).
    sl_block = {s: t for s, t in (saved.get("sl_block") or {}).items()
                if _sl_active(t, t_now)}
    # ShadowBroker's cost is the CROSSED SPREAD, already inside the fill price
    # (fee_bps=0 — Lighter charges no perp fee). Charging a flat fee on top
    # would double-count it; the legacy paper arm still models one. LIVE pays
    # the venue's real fee (zero) and its spread is inside the real fill, so
    # its modelled fee is zero for the same reason the shadow arm's is.
    fee_rate = broker.fee if dry_run else 0.0

    def _fold_capital_moves():
        """[2026-07-21 D1] Fold guard-detected deposits/withdrawals into the
        persisted capital ledger (fail-safe: no guard / no moves -> no-op).
        Run-once process: the same run that heals a deposit folds it, and the
        loop-bottom save_state persists it."""
        if not live:
            return
        for _mv in getattr(venue, "pop_capital_moves", lambda: [])():
            capital_adjust["total"] = round(capital_adjust["total"] + _mv["delta"], 2)
            capital_adjust["events"] = (capital_adjust.get("events") or [])[-19:] + [_mv]
            print(f"[ticket-taker] capital ledger: ${_mv['delta']:+.2f} "
                  f"({_mv['how']}) -> lifetime ${capital_adjust['total']:+.2f} "
                  f"(+${CAPITAL_ADJUST_USD:.2f} env backfill) — P&L baseline "
                  f"absorbed it.", flush=True)

    def account_value():
        """Equity. dry_run: the local broker. live: the VENUE, vetted by the
        EquityGuard (raises VenueError on a dislocated print)."""
        return broker.equity() if dry_run else venue.account_value()

    def positions():
        """{sym: {size, entry}} — the funding bot's shape. In LIVE the account
        is the source of truth, never our memory (the 11-Jul ghost-position
        lesson: a redeploy wiped an in-memory halt and the bot re-bought 37s
        after boot)."""
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        # [2026-07-17 SYMBOL SPACE — live-only, and it fires on the FIRST ticket]
        # This bot keys marks/funding/ranges/meta by the VENUE-NATIVE symbol from
        # its own orderBookDetails fetch ("1000BONK"). LighterClient.positions()
        # runs every symbol through from_lighter() and returns FLEET symbols
        # ("kBONK"). Unremapped, the live arm looks up "1000BONK" in a dict keyed
        # "kBONK", sees itself FLAT, and RE-OPENS the same position every cycle;
        # meanwhile the exit pass never examines the real one, so it runs with no
        # stop and no max-hold. MEASURED: 1000BONK is a divergence ticket right
        # now (short, gap 87.5pp) — the first thing a divergence-only arm touches.
        # Remap at THIS boundary rather than normalising the bot into fleet space:
        # meta and the broker snapshot are PERSISTED in the venue-native keys, so
        # changing the bot's key space would strand every open position on the
        # shadow arm. One space, converted where the two meet.
        # (to_lighter() mirrors from_lighter() as of today, so the trip closes for
        # all six 1000-markets — verified against all 218 live markets.)
        return {to_lighter(c)[0]: v for c, v in (venue.positions() or {}).items()}

    def _real_fill(sym, is_ask, fallback, leg, client_id=None,
                   tx_hash=None, settle_ms=None):
        """REAL fill price from the venue's own trade tape as (price, measured,
        reason). is_ask=True when WE sold (opening a SHORT / closing a LONG).
        `price` is the decision price when `measured` is False, so every caller
        can keep using it as a price — but only `measured` may be read as
        evidence.

        Extends lighter_funding_bot._real_exit to the OPEN leg too: that bot
        echoes the decision price on opens, which is the same unmeasurable-fill
        shape its own 17-Jul telemetry fix called out on closes. Entries here
        are rare (<=4/cycle), so the extra governed read is cheap and it makes
        this arm's execution measurable on BOTH legs — which is the entire
        reason a live arm exists before a go-live.

        [2026-07-17] RETURNS `measured` INSTEAD OF LETTING THE CALLER INFER IT.
        The old contract said "price == decision means we got no read". MEASURED
        false the same night: 1000BONK's REAL fill was 0.003275 and the decision
        price was 0.003275 — a genuinely perfect fill, identical to the mark,
        which the inference threw away as "unmeasured". Only THIS function knows
        whether the tape answered; inferring it from the number is a guess.

        [2026-07-17b] TWO DEFECTS FIXED, both by delegating to venues.fills:

        (1) THE ID FILTER WAS A CLIFF. `_our_fills` HARD-filters on the client id
            (lighter_client.py:624-629 `continue`s on a mismatch, no fallback),
            so the moment Lighter stopped echoing `client_order_index` — or any
            call site handed us a dict without the key — this read went from
            approximate to NOTHING (`no-match:both`), silently. Threading the id
            made the read exact on the happy path and strictly WORSE than the old
            heuristic on the unhappy one. `read_fill` retries once without the id
            on a no-match, so a venue that stops echoing costs precision, never
            the measurement. The round trip is still UNPROVEN in production: the
            only two live orders (STRC + 1000BONK, 17-Jul 09:08/09:13Z) predate
            the fill-read code by an hour, so no venue_orders row has ever
            carried `measured` at all. The fallback is what makes that
            uncertainty cost precision instead of the whole reading.

        (2) `measured` WAS HARD-CODED TRUE. This function returned
            `real, True, reason` for any price that came back, ignoring the very
            reason string that says whether the venue NAMED the fill or guessed
            it. An id-less read is labelled `trades(approx)` and is a 180s
            same-side VWAP blend — it would have been recorded as an exact
            measurement. `measured_from_reason` derives the verdict from the
            venue layer's own label, so the two cannot drift.

        Measurement-only: ANY failure falls back to the decision price, so a
        broken read can never block or unwind an order."""
        if dry_run:
            return fallback, False, "dry-run"
        detail = getattr(venue, "last_fill_detail", None)
        if detail is not None:
            px, measured, reason = read_fill(
                detail, sym, is_ask=is_ask, since_ts=time.time() - 180,
                client_id=client_id, tx_hash=tx_hash, settle_ms=settle_ms)
        else:
            # LEGACY venue: no reason channel and no id round trip, so this read
            # can only ever be a (side, since_ts) blend. It is labelled `approx`
            # for that reason — the old code called it `ok` and returned
            # measured=True, claiming an exactness the accessor cannot deliver.
            # Unreachable in production (LighterClient has both methods and the
            # shadow arm returns above), kept so a venue without the detail API
            # degrades to the heuristic rather than to nothing — the same cliff
            # as (1), one layer up.
            try:
                _lf = getattr(venue, "last_fill", None)
                px = (_lf(sym, is_ask=is_ask, since_ts=time.time() - 180)
                      if _lf else None)
                reason = ("last_fill(approx:no-detail-api)" if px
                          else "no-venue-method")
            except Exception as e:  # noqa: BLE001 — telemetry never breaks money
                px, reason = None, f"caller-error:{type(e).__name__}"
            measured = measured_from_reason(px, reason)
        if px is not None:
            print(f"[ticket-taker] {sym} {leg} fill (venue): {px:.6g} "
                  f"(decision {fallback:.6g}) via {reason}"
                  f"{'' if measured else ' — NOT measured, slippage NULL'}")
            return px, measured, reason
        # NOT a crash and NOT zero slippage — an UNMEASURED leg. Say so, loudly
        # enough that 57 orders can never again go by without anyone noticing.
        print(f"[ticket-taker] {sym} {leg} fill UNMEASURED — {reason} "
              f"(recording decision {fallback:.6g}, slippage NULL)")
        return fallback, False, reason

    # [2026-07-17] SHARED with the live Funding Farmer (venues/fills.py). The
    # local copy's `measured=None -> infer d == f` back-compat is gone: both
    # call sites below pass `measured` explicitly (they get it from _real_fill,
    # which is the only thing that knows), so the inference was dead code that
    # existed only to be gotten wrong later. The shared rule is the STRICTER of
    # the two copies — an unmeasured leg is NULL even when d != f, which is this
    # bot's rule winning over the Farmer's. See venues/fills.py for why that
    # direction: the id-miss fallback is the first read that can hand us a real
    # price we did NOT measure, and implementation_shortfall AVGs this column
    # without ever reading `measured`.
    _slip_bps_of = slip_bps_of

    def _book_close(sym, m, size, entry, exit_px, pnl, reason, decision_px=None,
                    measured=None, fill_reason=None):
        """Ledger + counters + meta pop for ONE close. Shared by the exit pass
        and _flatten_all so an emergency flatten reconstructs identically to a
        normal close (the funding bot's rule: forensics must stay consistent
        with account equity).

        `measured`/`fill_reason` carry _real_fill's verdict so the order row can
        record a MEASURED zero as zero, and name the cause when it measured
        nothing. Default None = "caller doesn't know" = the old inference."""
        is_long = size > 0
        drag = float(m.get("funding_paid") or 0.0)   # signed: shorts credit
        clip_used = float(m.get("clip") or CLIP_USD)
        fees = 2 * clip_used * fee_rate
        net = pnl - drag - fees
        stats["closed"] += 1
        stats["wins" if net > 0 else "losses"] += 1
        lens = m.get("lens") or "ticket"
        side = "long" if is_long else "short"
        # tag format <side>-<lens>_<exit>: the ledger's reason parser splits
        # on the FIRST underscore, so the brain's enter_tag becomes
        # "long-breakout"/"short-divergence" — per-lens grading, not one
        # blended "long" bucket.
        store.publish_paper_trade(
            BOT_ROW, trade_id=f"{sym}-{m.get('opened')}",
            pnl_abs=round(net, 4),
            pnl_pct=round(net / clip_used, 6),
            pair=f"{sym}/USDC",
            opened_at=m.get("opened"), closed_at=iso(t_now),
            reason=f"{side}-{lens}_{reason}",
            # [2026-07-15 AUDIT FIX] provenance: venue + arm on every row —
            # venue NULL claimed the pre-Gate-0 HL-paper era.
            venue="lighter", shadow=dry_run,
            # [2026-07-21 ATTRIBUTION; 2026-07-22 FLAP FIX] bars on every
            # close row. Since the flap fix these are the ENTRY-time stamp —
            # the bars that actually GOVERNED the trade (the 21-Jul
            # close-time caveat "a mid-hold lever change stamps the exit's
            # bars" is exactly the contamination the (bw) study had to
            # reconstruct around: 11/22 SL closes ran under a different bar
            # than the one stamped/assumed). Legacy positions opened before
            # the stamp existed fall back to close-time values, labelled so.
            extra={"bars": (m.get("bars") if isinstance(m.get("bars"), dict)
                            and m.get("bars") else entry_bars()),
                   "bars_basis": ("entry" if isinstance(m.get("bars"), dict)
                                  and m.get("bars") else "close-legacy")})
        if not dry_run:
            try:
                store.publish_venue_order(
                    BOT_ROW, venue="lighter", shadow=False, coin=sym,
                    side=("sell" if is_long else "buy"), size=abs(size),
                    px_decision=decision_px, px_fill=exit_px,
                    slippage_bps=_slip_bps_of(decision_px, exit_px,
                                              is_buy=not is_long,
                                              measured=measured),
                    # `measured` + `fill_src` make the blind spot QUERYABLE off
                    # the ledger instead of grep-able off a container log that
                    # ages out. 0 of 57 real orders carried a fill; nobody could
                    # ask the database why.
                    raw={"reason": reason, "lens": lens, "leg": "close",
                         "measured": measured, "fill_src": fill_reason})
            except Exception:  # noqa: BLE001
                pass
        print(f"[ticket-taker] {iso(t_now)} CLOSE {side} {sym} ({lens}) {reason} "
              f"pnl {pnl:+.2f} funding {-drag:+.3f} net {net:+.2f}")
        meta.pop(sym, None)

    def _flatten_all(reason):
        """LIVE emergency flatten (kill switch / daily loss). Reads the VENUE,
        not meta — an untracked position still holds real risk and must still
        be closed. Mirrors normal-close bookkeeping via _book_close."""
        try:
            # fleet -> venue-native, same boundary rule as _positions()
            live_pos = {to_lighter(c)[0]: v
                        for c, v in (venue.positions() or {}).items()}
        except Exception as e:  # noqa: BLE001
            print(f"[ticket-taker] {iso(t_now)} flatten scan failed: {e!r}")
            return
        for sym in list(live_pos):
            size = (live_pos.get(sym) or {}).get("size") or 0.0
            if not size:
                continue
            m = meta.get(sym) or {}
            is_long = size > 0
            entry = float((live_pos.get(sym) or {}).get("entry")
                          or m.get("entry") or 0.0)
            px = marks.get(sym) or float(m.get("last_mark") or entry)
            try:
                # [2026-07-17] None == the venue did NOT close it (no position
                # under that key). Treating it as success books a phantom close
                # and pops meta, stranding a REAL position with no exit rule.
                _res = venue.market_close(_fleet(sym))
                if _res is None:
                    print(f"[ticket-taker] {iso(t_now)} flatten {sym}: venue "
                          f"reported NO position to close — leaving meta intact "
                          f"and retrying next cycle (NOT booking a close)")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[ticket-taker] {iso(t_now)} flatten {sym}: {e!r}")
                continue
            _dpx = px
            px, _meas, _why = _real_fill(
                sym, is_ask=is_long, fallback=px, leg="exit",
                client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
            pnl = abs(size) * ((px - entry) if is_long else (entry - px))
            _book_close(sym, m, size, entry, px, pnl, reason, decision_px=_dpx,
                        measured=_meas, fill_reason=_why)

    # ---- LIVE RAILS (loop-top order mirrors lighter_funding_bot) -----------
    # This bot is a RUN-ONCE process (run_all.sh loops it every 5 min), so
    # everything the funding bot keeps in memory across its `while True` must
    # be DURABLE here or it resets every cycle: the day-start equity baseline
    # and the halt. A memory-only halt is exactly the 11-Jul incident — the
    # redeploy wiped it and the bot re-bought 37 seconds after boot.
    cur_day = t_now.date().isoformat()
    halted_today = False
    day_start_equity = None
    if live:
        _halt = store.load_daily_halt(BOT_ROW, cur_day)
        if _halt:
            halted_today = True
            day_start_equity = _halt.get("day_start_equity")
            print(f"[ticket-taker] {iso(t_now)} daily-loss halt restored from "
                  f"state — halted for the rest of {cur_day}")
        else:
            _ds = saved.get("day_start") or {}
            if _ds.get("day") == cur_day:
                day_start_equity = _ds.get("equity")

        # kill switch FIRST — checked every cycle, not once at boot.
        if rails.kill_check():
            print(f"[ticket-taker] {iso(t_now)} REAL_MONEY_KILL armed — "
                  f"flatten + halt.")
            halted_today = True
            _flatten_all("kill_switch")

    try:
        equity = account_value()
    except Exception as e:  # noqa: BLE001 — guard rejected, or venue down
        print(f"[ticket-taker] {iso(t_now)} account value unavailable: {e!r}")
        equity = None
    _fold_capital_moves()   # D1: a deposit accepted on that read is capital

    if live:
        if day_start_equity is None and equity is not None:
            # [2026-07-11 LATE BASELINE] if the boot/day-roll capture failed
            # (venue down, or the guard vetoed a dislocated print) the rail
            # used to stay OFF all day. Adopt the first credible read instead.
            day_start_equity = equity
            print(f"[ticket-taker] {iso(t_now)} day-start equity for {cur_day}: "
                  f"{equity:.2f}")
        _fleet_loss = rails.daily_loss_hit(day_start_equity, equity)
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)
                     or _fleet_loss)):
            # [2026-07-11 RAIL DEBOUNCE] one dislocated equity print sold the
            # book into the dislocation (-5.9% real). Confirm on a second read
            # (shared SafetyRails.confirm_daily_loss — FAIL-SAFE: an unreadable
            # confirm counts as CONFIRMED). Adopt the fresher read either way
            # so a phantom print can't leak into published equity or the
            # persisted baseline.
            _confirmed, equity = rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                print(f"[ticket-taker] {iso(t_now)} DAILY LOSS LIMIT HIT "
                      f"({equity:.2f} vs day start {day_start_equity:.2f}) — "
                      f"flatten + halt.")
                halted_today = True
                store.save_daily_halt(BOT_ROW, cur_day, day_start_equity)
                _flatten_all("daily_loss")

        if halted_today:
            # [2026-07-16 AUDIT FIX] retry the flatten every halted cycle — it
            # used to run once at the halt transition, so a single failed close
            # (rate-limit storm, venue blip) left that position with NO stop
            # until the day rolled. Idempotent once flat; skip when the kill
            # switch already flattened this same cycle.
            if not rails.kill_check():
                _flatten_all("daily_loss")
            store.save_state(LIVE_STATE_KEY, {
                "initial_equity": live_baseline, "meta": meta, "stats": stats,
                "capital_adjust": capital_adjust,
                "day_start": {"day": cur_day, "equity": day_start_equity}})
            # Report what the VENUE actually holds, not 0. A flatten can fail
            # (rate-limit storm, venue blip) and publishing open_trades=0 while
            # real positions are still open would make the retry-every-cycle
            # rail above invisible — a green row over an unstopped book is the
            # convergent-metric trap the perp sniper already walked into.
            try:
                _still = len(venue.positions())
            except Exception:  # noqa: BLE001
                _still = None
            store.publish(
                BOT_ROW, status="halted", equity=equity,
                pnl_abs=((equity - live_baseline - capital_adjust["total"]
                          - CAPITAL_ADJUST_USD)   # D1: capital-adjusted
                         if (equity is not None and live_baseline is not None)
                         else None),
                open_trades=_still, closed_trades=stats["closed"],
                wins=stats["wins"], losses=stats["losses"],
                extra={"venue": TT_VENUE, "strategy": "scout tickets (live)",
                       "halted": True, "day": cur_day,
                       "flatten_incomplete": bool(_still)})
            print(f"[ticket-taker] {iso(t_now)} halted for {cur_day}; no entries"
                  f"{f'; {_still} STILL OPEN — flatten incomplete' if _still else ''}.")
            return

    try:
        pos = positions()
    except Exception as e:  # noqa: BLE001
        # [2026-07-17] LIVE: never act on a phantom-empty position set. An
        # unreadable venue would zero BOTH the MAX_OPEN slot count and the
        # notional cap's input (open_notional sums what's in `pos`), so the
        # entry pass below would happily open a full book ON TOP of positions
        # that already exist — the cap breach the rail exists to prevent,
        # reached by believing our own blindness. The funding bot skips its
        # loop for exactly this reason; this is a run-once process, so
        # skipping the cycle IS the loop-skip.
        print(f"[ticket-taker] {iso(t_now)} positions unreadable ({e!r}) — "
              f"skipping cycle (no entries, no exits)")
        store.heartbeat(BOT_ROW)
        return

    # [2026-07-17 ADOPTION GUARD — the Tide Rider handover] A live arm inherits
    # a real Lighter SUB-ACCOUNT, and the plan is to hand it the one Tide Rider
    # is vacating. If ANY position on it has no meta of ours, this bot did not
    # open it and MUST NOT manage it: it has no entry clip, no lens and no
    # opened-time, so every rule below would be applied to someone else's
    # position on the wrong strategy's bars — the exit ladder would TP/SL a
    # trend position at the taker's ±4%, the ledger would book it under a
    # "ticket" lens the brain then grades, and the divergence-only mandate
    # would be silently violated by a coin no scout ever ticketed.
    #
    # WHY THIS IS NOT PARANOIA: crypto-trend-daily-lighter's row still reads
    # held:['TRX'] at equity $34.67 — but its status is `error`, and
    # SafetyRails._publish_refusal is a STATUS-ONLY write, so those values are
    # the LAST GOOD PUBLISH, frozen. The dashboard cannot tell you whether that
    # account is flat; only a keyed read can. So the bot checks at the venue,
    # every cycle, and refuses rather than guesses.
    #
    # Fail-CLOSED on real money: a lost meta (a failed state write) also lands
    # here, and halting is still right — a position we cannot attribute is one
    # we cannot manage. The kill switch runs ABOVE this and still flattens,
    # so REAL_MONEY_KILL remains the escape hatch for a dirty account.
    # [2026-07-17 AUDIT] SCOPED to the foreign symbols, not the whole account.
    # This guard was `raise SystemExit` on ANY unattributable position — which
    # ran BEFORE sections 1-4, so it did not merely decline to adopt the
    # stranger: it abandoned OUR OWN meta'd positions in the same breath. No
    # mark, no stop-loss, no max-hold, no delist give-up, for as long as the
    # stranger sat there. On a $15 clip at the $30 cap that is real money left
    # unstopped, and a lost meta WRITE (save_state returns False silently)
    # makes it PERMANENT — operator-only to clear.
    #
    # The original reasoning is still honoured, and is the reason this is a
    # FILTER rather than a deletion: we must not run the taker's exit ladder on
    # another strategy's position (no entry clip, lens or opened-time), and we
    # must not trade while the account is dirty. So: drop the foreign symbols
    # from the working set (sections 1-2 can never touch them), refuse NEW
    # entries, and page — while our own positions keep every exit they had.
    # The file's own live_boot_gate docstring names this exact hazard: "the
    # switch meant to protect the money would be what abandons it."
    dirty_syms = []
    if live:
        dirty_syms = sorted(s for s in pos if s not in meta)
        if dirty_syms:
            store.set_status(BOT_ROW, "error")
            print(f"[ticket-taker] {iso(t_now)} DIRTY ACCOUNT: venue reports "
                  f"{dirty_syms} with no meta of ours — NOT adopting "
                  f"{'them' if len(dirty_syms) > 1 else 'it'} (no entry clip, "
                  f"lens or opened-time, so the exit ladder would manage "
                  f"another strategy's position on the taker's bars) and NO "
                  f"NEW ENTRIES this cycle. Our own {len(pos) - len(dirty_syms)} "
                  f"position(s) keep their stop/max-hold. If this is Tide "
                  f"Rider's leftover on the handed-over sub-account, flatten it "
                  f"(by hand, or REAL_MONEY_KILL=DISARMED_I_UNDERSTAND). If it "
                  f"is OURS with a lost meta write, reconcile "
                  f"bot_state['{LIVE_STATE_KEY}'].meta — those symbols have NO "
                  f"stop until you do.", flush=True)
            # (the `error` row status above IS the operator signal — this file
            # has no push helper, and inventing one here would be a second
            # untested path on a live bot.)
            # sections 1-2 iterate `pos`; the stranger must not be in it
            pos = {s: v for s, v in pos.items() if s not in set(dirty_syms)}

    # 1) mark + hourly funding drag on held positions (longs pay positive rate)
    for sym in list(pos):
        mark = marks.get(sym)
        if mark and dry_run:
            broker.mark(sym, mark)
        m = meta.get(sym) or {}
        try:
            last = parse_ts(m.get("accrued_to") or m.get("opened"))
            hours = max(0.0, (t_now - last).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            hours = 0.0
        rate = funding.get(sym)
        if hours > 0 and rate and mark:
            size = pos[sym]["size"]
            # SIGNED accrual: a long pays a positive rate (drag > 0), a short
            # RECEIVES it (drag < 0 = credit) — the divergence lens's whole
            # thesis is collecting that credit.
            #
            # [2026-07-17 BASIS FIX] This read Lighter's quote as HOURLY and
            # accrued `rate * hours` = 8x TRUE (Lighter quotes per 8h). The
            # THIRD accruing book to carry this bug — 93be95e fixed
            # Counterweight and the family bot and called the set complete;
            # this one models its carry inline rather than via funding_basis,
            # so a grep for the fixed call site could not see it.
            # It lands exactly where it hurts most: DIVERGENCE is the only
            # lens with a positive forward grade and the only one that
            # COLLECTS carry, so the inflated credit flattered the one number
            # that could earn this bot a go-live. Same shape as Counterweight,
            # whose entire reported profit was this artifact.
            # LIVE note: a live arm's real funding is charged by the VENUE and
            # is already inside account_value(), so it must NOT also hit a
            # modelled equity — but the accrual still reaches the per-trade
            # ledger and the win/loss call, which is why it is computed on
            # both arms and applied to equity on only one.
            drag = size * mark * funding_basis.to_hourly(rate, "lighter") * hours
            if dry_run:
                broker.fees += drag
            m["funding_paid"] = round(float(m.get("funding_paid") or 0.0) + drag, 6)
            m["accrued_to"] = iso(t_now)
            meta[sym] = m

    # 2) exits
    for sym in list(pos):
        mark = marks.get(sym)
        m = meta.get(sym) or {}
        try:
            opened = parse_ts(m.get("opened"))
        except (ValueError, TypeError):
            opened = t_now
        size = pos[sym]["size"]
        # The VENUE's avg_entry_price is the REAL fill and outranks our
        # decision price; meta is the fallback for a position the venue
        # reports without one. In dry_run pos[] IS the broker, so this is the
        # broker's own entry — one expression, right on both arms.
        entry = float(pos[sym].get("entry") or m.get("entry") or 0.0)
        is_long = size > 0
        if mark:
            m.pop("no_mark_since", None)     # priceable again — reset the clock
            m["last_mark"] = mark
            meta[sym] = m
            reason = exit_reason(entry, mark, opened, t_now, is_long,
                                 bars=pos_bars(m))
        else:
            # [2026-07-16 ZOMBIE GUARD] book missing from the active universe
            first = m.get("no_mark_since")
            try:
                parse_ts(first)
            except (ValueError, TypeError):
                first = None
            if not first:
                m["no_mark_since"] = iso(t_now)   # start (or restart) the clock
                meta[sym] = m
                continue
            if not delist_due(first, t_now):
                continue
            mark = float(m.get("last_mark") or entry)
            reason = "delisted"
        if not reason:
            continue
        if dry_run:
            pnl = broker.close(sym, mark)
            _dpx = None
            _meas, _why = None, None
        else:
            try:
                # [2026-07-17] This block's own comment already said "never book
                # a close that did not happen" — but it only caught EXCEPTIONS,
                # and the stranding case does NOT raise: market_close() returns
                # None when it finds no position under that key
                # (venues/lighter_client.py:558-560). That is precisely the
                # symbol-space failure, so the guard missed the case it was
                # written for. None is a FAILED close.
                _res = venue.market_close(_fleet(sym))
                if _res is None:
                    print(f"[ticket-taker] {iso(t_now)} close {sym}: venue "
                          f"reported NO position under {_fleet(sym)!r} — NOT "
                          f"booking a close; leaving position, retry next cycle")
                    continue
            except Exception as e:  # noqa: BLE001
                # Leave the position and retry next cycle. Never book a close
                # that did not happen — a phantom close drops the position from
                # meta while the venue still holds the risk.
                print(f"[ticket-taker] {iso(t_now)} close {sym} failed: {e!r} — "
                      f"leaving position, retry next cycle")
                continue
            _dpx = mark                                  # mid at the decision
            mark, _meas, _why = _real_fill(
                sym, is_ask=is_long, fallback=mark, leg="exit",
                client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
            pnl = abs(size) * ((mark - entry) if is_long else (entry - mark))
        _book_close(sym, m, size, entry, mark, pnl, reason, decision_px=_dpx,
                    measured=_meas, fill_reason=_why)
        pos.pop(sym, None)
        if reason == "sl" and SL_COOLDOWN_H > 0:
            sl_block[sym] = iso(t_now + timedelta(hours=SL_COOLDOWN_H))
            print(f"[ticket-taker] {iso(t_now)} {sym} entry-blocked "
                  f"{SL_COOLDOWN_H:g}h post-stop (same-cycle re-entry churn "
                  f"guard)")

    # 3) entries — only from a FRESH scout snapshot, only the incredible subset
    # [2026-07-17 AUDIT] ...and never onto a DIRTY account. The old guard's
    # SystemExit blocked entries as a side effect of abandoning everything;
    # scoping it to the foreign symbols means the no-new-entries half must now
    # be stated EXPLICITLY, or relaxing the strand would have quietly relaxed
    # the trading refusal too. Refusing to ADD exposure while the account holds
    # something we cannot attribute is the half of the original rule that was
    # always right — it is the abandonment half that was the bug.
    scout = {} if dirty_syms else (store.load_state(SCOUT_KEY) or {})
    fresh = False
    try:
        age = (t_now - parse_ts(scout.get("updated"))).total_seconds()
        fresh = age <= float(scout.get("ttl_sec") or 900)
    except (ValueError, TypeError):
        fresh = False
    # [2026-07-14b] Stress veto: a venue-wide |premium| blowout means marks
    # are unreliable and every book is dislocating together — no new bets.
    stress_med = ((scout.get("stress") or {}).get("med")
                  if fresh else None)
    stressed = stress_med is not None and stress_med >= STRESS_VETO_BPS
    if stressed:
        print(f"[ticket-taker] {iso(t_now)} STRESS VETO — venue |premium| "
              f"median {stress_med}bps >= {STRESS_VETO_BPS}bps; no new entries")
    # [2026-07-14c] Fleet drawdown governor: fleet_risk publishes clip_scale
    # (1.0 / 0.5 past -5% 7d dd / 0.25 past -10%). Fail-safe neutral on
    # missing/stale state — same contract as every bus consumer.
    gov = 1.0
    long_budget_full = False
    try:
        fr = store.load_state("fleet-risk") or {}
        fr_age = (t_now - parse_ts(fr.get("updated"))).total_seconds()
        if fr_age <= float(fr.get("ttl_sec") or 900):
            gov = max(0.25, min(1.0, float(fr.get("clip_scale") or 1.0)))
            # [2026-07-15 AUDIT FIX] L2 long-budget veto now has a consumer in
            # the RUNNING fleet (it was wired only into the retired Kraken
            # strategies). Fail-safe OPEN: stale/missing state never blocks.
            _lb = fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if (fr.get("mode") == "enforce"
                    and (fr.get("long_positions") or 0) >= _lb):
                long_budget_full = True
    except (ValueError, TypeError):
        gov = 1.0
    # [2026-07-21 AUDIT FIX] the LIVE arm now honors live.clip_scale — the
    # board's ONLY live restrict lever. CLAUDE.md's live-lane contract
    # ("covers ... both live bots' clip") was half-true: the Funding Farmer
    # reads it via VenueContext.order_usd, but this bot builds LighterClient
    # directly and sized off TT_CLIP_* alone, so the board's real-money
    # down-scale (and the proprioception hurting-revert riding get_lever's
    # central hook) never reached the live Ticket Taker. get_lever carries
    # the whole fail-safe stack: registry clamp [0.5,1.5], TTL expiry,
    # immune quarantine, hurting-revert, ENACT_LANES kill.
    # [2026-07-21b, same-day verify catch] the lever REPLACES the fleet-risk
    # drawdown governor on the live arm rather than compounding with it:
    # CLAUDE.md's contract is explicit — the fleet clip_scale "reaches only
    # shadow consumers (family/taker); the live bots size off the separate
    # live.clip_scale lever" — and this arm consuming BOTH would double-
    # restrict through two organs' opinions of the same drawdown. Shadow
    # arm keeps the fleet governor unchanged (its book is the lens-grading
    # instrument).
    if not dry_run:
        live_scale = 1.0
        if tuning is not None:
            try:
                live_scale = float(tuning.get_lever("live.clip_scale", 1.0))
            except Exception:  # noqa: BLE001
                live_scale = 1.0
        gov = live_scale
        if live_scale != 1.0:
            print(f"[ticket-taker] {iso(t_now)} LIVE CLIP SCALE — "
                  f"x{live_scale} (live.clip_scale; fleet governor is "
                  f"shadow-lane per contract)")
    elif gov < 1.0:
        print(f"[ticket-taker] {iso(t_now)} DRAWDOWN GOVERNOR — clips x{gov}")
    if long_budget_full:
        print(f"[ticket-taker] {iso(t_now)} FLEET LONG-BUDGET VETO — "
              f"{fr.get('long_positions')}/{fr.get('long_budget')} directional "
              f"longs; no new LONG entries this cycle (shorts unaffected)")
    # [2026-07-15 LENS-FORWARD VETO] The brain grades every scout ticket
    # counterfactually (bot_state 'brain-lens-forward'). RESTRICT-ONLY, per
    # doctrine: a lens graded negative at sample size stops getting fills;
    # missing/stale grades never block anything (fail-safe open).
    lens_vetoed = set()
    try:
        lf = store.load_state("brain-lens-forward") or {}
        lf_age = (t_now - parse_ts(lf.get("updated"))).total_seconds()
        if lf_age <= float(lf.get("ttl_sec") or 26000):
            lens_vetoed = vetoed_lenses(lf.get("lenses"))
    except (ValueError, TypeError):
        lens_vetoed = set()
    if lens_vetoed:
        print(f"[ticket-taker] {iso(t_now)} LENS VETO — brain grades "
              f"{sorted(lens_vetoed)} negative at sample size; skipping their "
              f"tickets (restrict-only; recovers when the grade does)")
    # [2026-07-22 COIN-QUALITY VETO] Same contract as the Farmer's
    # (lighter_funding_bot.py:1033), transcribed so the two cannot drift:
    # RESTRICT-ONLY, and a missing OR STALE payload yields NO vetoes (fail
    # OPEN). Staleness matters in both directions — a dead market-context
    # either vetoes forever or, if it died empty, silently disables the veto
    # forever; only an age check distinguishes them.
    coin_vetoed = {}
    if QUALITY_VETO:
        try:
            _vp = store.load_state("coin-vetoes") or {}
            _cv = _vp.get("coins") or {}
            # a veto set is a coin->reason MAP; anything else is not evidence
            if not isinstance(_cv, dict):
                _cv = {}
            _vts = _vp.get("updated") or _vp.get("ts")
            _vttl = float(_vp.get("ttl_sec") or QUALITY_VETO_TTL_S)
            _vage = ((t_now - parse_ts(_vts)).total_seconds() if _vts else None)
            if _vage is not None and 0 <= _vage <= _vttl:
                coin_vetoed = _cv
                if coin_vetoed:
                    # Print each coin's OWN reason. The set is NOT slippage-only
                    # — market_context.py:396-399 has two branches (slip > 15bps
                    # over >=5 orders/14d, OR stop-rate >=50% over >=5 closes/
                    # 30d, pooled fleet-wide) — and today's live set proves it:
                    # ADA is a STOP-RATE veto whose own slip is 3.65bps. A log
                    # line saying "measured slippage [ADA, BOT, SOXL]" is this
                    # repo's own self-describing-label failure, in the actuator's
                    # own receipt. Say what each one actually is.
                    print(f"[ticket-taker] {iso(t_now)} COIN VETO — "
                          + "; ".join(f"{c}: {coin_vetoed[c]}"
                                      for c in sorted(coin_vetoed))
                          + "  (restrict-only for NEW entries; exits, stops and "
                            "held positions untouched)")
            elif _cv:
                print(f"[ticket-taker] {iso(t_now)} coin-vetoes STALE "
                      f"(age {_vage if _vage is None else round(_vage)}s > "
                      f"ttl {_vttl:.0f}s) — discarding {len(_cv)} veto(s); "
                      f"quality veto fails OPEN until the publisher returns")
        except Exception:  # noqa: BLE001 — the Farmer's ACTUAL contract
            # Widened from (ValueError, TypeError, AttributeError): the Farmer
            # catches bare Exception, and a narrower tuple here is exactly the
            # silent drift this change exists to prevent. On the LIVE run-once
            # arm an escape here would abort the cycle before the durable write,
            # losing day_start and re-baselining the daily-loss rail.
            coin_vetoed = {}
    opened_syms, opened_lenses = set(), set()
    # [2026-07-17] Hard mode allow-list, evaluated ONCE and independently of any
    # bus payload. Live = divergence only; shadow keeps filling all four so the
    # control arm still grades them. See allowed_lenses().
    _allowed = allowed_lenses(TT_VENUE)
    if fresh and not stressed:
        for lens, t in incredible(scout.get("tickets") or {}):
            sym = t.get("sym")
            if lens not in _allowed:
                continue          # mode allow-list — FAIL-CLOSED, reads no bus
            if lens in lens_vetoed:
                continue          # brain veto stays SENIOR (restrict-only)
            # [2026-07-22] coin-quality veto. Symbol form is normalised because
            # the scout emits a bare base ("BOT") while the ledger records a
            # pair ("BOT/USDC"); matching only one form would make this veto
            # silently inert — the exact failure mode it exists to fix.
            if coin_vetoed and str(sym or "").split("/")[0] in coin_vetoed:
                continue          # measured slippage over the bar (fail-open)
            # one NEW position per lens per cycle; never add to a held symbol
            if (not sym or sym in pos or sym in opened_syms
                    or lens in opened_lenses
                    or _sl_active(sl_block.get(sym), t_now)):
                continue
            if len(pos) >= MAX_OPEN:
                break
            mark = marks.get(sym)
            if not mark:
                continue
            is_long = t.get("side", "long") != "short"
            if is_long and long_budget_full:
                continue          # L2 veto: fleet long budget is full
            clip = round(vol_clip(ranges.get(sym)) * gov, 2)
            size = clip / mark
            ev = {k: t.get(k) for k in ("range_pos", "chg_pct", "vol_m",
                                        "prem_bps", "apr_pct", "gap_pct")}
            entry_px = mark
            # [2026-07-17] BRACES to the allow-list's belt. The filter above is
            # the belt; this is the last statement before real money moves, so
            # a future second entry path cannot bypass it by construction.
            # SystemExit propagates through _supervised() untouched — a breach
            # HALTS rather than restarting into the same bug.
            if not dry_run and lens not in LIVE_LENSES:
                raise SystemExit(
                    f"live lens allow-list BREACHED: {lens!r} reached the order "
                    f"path on real money (allowed: {sorted(LIVE_LENSES)}). "
                    f"Halting rather than filling.")
            if dry_run:
                broker.open(sym, is_long, size, mark)
                # ShadowBroker fills by WALKING the book, so the decision price
                # is NOT the fill — read the entry back instead of assuming it.
                # PaperBroker.open() also silently no-ops on a bad size/price;
                # a missing key here means no position was actually taken, and
                # claiming one in `pos` would strand a phantom in the cap
                # count and the slot budget.
                if sym not in broker.pos:
                    print(f"[ticket-taker] {iso(t_now)} open {sym} rejected by "
                          f"broker (size {size} @ {mark})")
                    continue
                _sz, entry_px = broker.pos[sym]
                size = abs(_sz)
            else:
                # The operator's hard notional cap is SENIOR to every other
                # sizing input (governor, vol_clip, growth rail) and is checked
                # against REAL deployed notional at order time — never
                # count*clip, which breached the cap on 15-Jul once the growth
                # rail made the clip variable. venues.safety owns this rule.
                open_ntl = open_notional(pos, meta, len(pos), clip)
                if not rails.notional_ok(open_ntl, clip):
                    print(f"[ticket-taker] {iso(t_now)} {sym} NOTIONAL_CAP_SKIP "
                          f"(deployed ${open_ntl:.2f} + ${clip:.2f} > cap "
                          f"${rails.max_notional})")
                    continue
                size = round(size, 6)
                try:
                    # fleet symbol — the space the client's API speaks. This one
                    # would have "worked" with a native symbol (_resolve tolerates
                    # it), which is exactly how open/close drifted apart.
                    _res = venue.market_open(_fleet(sym), is_long, size)
                except Exception as e:  # noqa: BLE001
                    print(f"[ticket-taker] {iso(t_now)} open {sym} failed: {e!r}")
                    continue
                _fill_px, _meas, _why = _real_fill(
                    sym, is_ask=not is_long, fallback=mark, leg="entry",
                    client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
                try:
                    store.publish_venue_order(
                        BOT_ROW, venue="lighter", shadow=False, coin=sym,
                        side=("buy" if is_long else "sell"), size=size,
                        px_decision=mark, px_fill=_fill_px,
                        slippage_bps=_slip_bps_of(mark, _fill_px,
                                                  is_buy=is_long,
                                                  measured=_meas),
                        raw={"lens": lens, "leg": "open", "clip": clip,
                             "evidence": ev,
                             "measured": _meas, "fill_src": _why})
                except Exception:  # noqa: BLE001
                    pass
                # ---- ORDER BEHAVIOUR STOPS HERE ---------------------------
                # Everything above is telemetry. `entry_px` is NOT: it becomes
                # meta[sym]["entry"], which the stop and TP hang off, so it
                # decides when REAL money closes. This is the one place the
                # taker differs from the Farmer, whose exit read is pure
                # forensics (the position is already flat when it runs) — here
                # the read steers the next decision.
                #
                # So an UNMEASURED price never reaches it. read_fill's id-miss
                # fallback is a 180s same-side VWAP and has NEVER run in
                # production (the id round trip is unproven — the only two live
                # orders predate the fill-read code), and a fallback's first
                # ever execution must not be the thing that moves a live stop.
                # It is probably a better entry estimate than the decision mark.
                # "Probably" is not a bar this bot clears with real money on the
                # book: the ledger records the blend and names it, the operator
                # reads it there, and a later change can promote it on evidence.
                #
                # BEHAVIOUR-IDENTICAL on every path production can reach today:
                # an exact id match (_meas=True) keeps feeding meta the real
                # fill exactly as it does now, and no-read keeps feeding it the
                # mark. Only the id-miss path — today a `no-match:both` that
                # yields the mark anyway — is touched, and it yields the mark.
                entry_px = _fill_px if _meas else mark
            # visible to the rest of THIS cycle: the cap check above and the
            # MAX_OPEN slot count must both see what we just opened.
            pos[sym] = {"size": size if is_long else -size, "entry": entry_px}
            meta[sym] = {"lens": lens, "opened": iso(t_now), "clip": clip,
                         "entry": entry_px,
                         "accrued_to": iso(t_now), "funding_paid": 0.0,
                         "evidence": ev,
                         # [2026-07-22 FLAP FIX] the bars priced at entry
                         # govern this trade — see pos_bars/entry_bars.
                         "bars": entry_bars()}
            opened_syms.add(sym)
            opened_lenses.add(lens)
            print(f"[ticket-taker] {iso(t_now)} OPEN "
                  f"{'long' if is_long else 'SHORT'} {sym} ({lens}) "
                  f"${clip} @ {entry_px} (range {round(ranges.get(sym) or 0, 1)}%) "
                  f"evidence={ev}")

    # 4) persist + publish
    if dry_run:
        equity = broker.equity()
        pnl_abs = equity - START_EQUITY
        pnl_pct = equity / START_EQUITY - 1.0
        store.save_state(STATE_KEY, {"broker": broker.to_state(), "meta": meta,
                                     "stats": stats, "sl_block": sl_block})
    else:
        # re-read AFTER trading: the loop-top print fed the rails, this one is
        # what the row reports. A failed re-read keeps the loop-top value
        # rather than publishing a hole.
        try:
            equity = account_value()
        except Exception:  # noqa: BLE001
            pass
        # [2026-07-21 AUDIT FIX] fold AGAIN before persisting: the guard can
        # record a capital move on the two LATER same-cycle reads (the rails'
        # confirm_daily_loss re-read and the line above) — a run-once process
        # that only folded at loop-top exited with those moves un-persisted,
        # so the next run's fresh guard had lost them and the P&L baseline
        # silently absorbed the operator's deposit as "trading profit".
        _fold_capital_moves()
        if live_baseline is None and equity is not None:
            live_baseline = equity
        # [2026-07-21 D1] capital-adjusted: deposits are the operator's money
        # moving, not trading results. Reporting-only — no rail reads pnl_abs.
        pnl_abs = ((equity - live_baseline - capital_adjust["total"]
                    - CAPITAL_ADJUST_USD)
                   if (equity is not None and live_baseline is not None) else None)
        pnl_pct = ((pnl_abs / live_baseline)
                   if (pnl_abs is not None and live_baseline) else None)
        # [2026-07-17 AUDIT] The meta WRITE's return was discarded. save_state
        # "Never raises" — it returns False (bot_pnl_store.py:222). So a write
        # that failed after a successful market_open lost that position's meta
        # SILENTLY AND FOREVER: next cycle the venue reports a position we have
        # no record of, and it is indistinguishable from a stranger. Before the
        # guard above was scoped that meant a PERMANENT strand; it is still the
        # one path that manufactures an unstoppable position out of nothing but
        # a DB blip. We cannot retroactively remember what we failed to write —
        # but we can refuse to let it pass unnoticed, so the operator finds it
        # by page rather than by reading the P&L.
        if not store.save_state(LIVE_STATE_KEY, {
                "initial_equity": live_baseline, "meta": meta, "stats": stats,
                "capital_adjust": capital_adjust, "sl_block": sl_block,
                "day_start": {"day": cur_day, "equity": day_start_equity}}):
            store.set_status(BOT_ROW, "error")
            print(f"[ticket-taker] {iso(t_now)} CRITICAL: live state WRITE "
                  f"FAILED — {len(meta)} position(s) worth of meta (entry clip, "
                  f"lens, max-hold clock) did NOT persist. If the process dies "
                  f"before the next successful write, those positions become "
                  f"unattributable and lose their stop/max-hold until you "
                  f"reconcile bot_state['{LIVE_STATE_KEY}'].meta by hand. "
                  f"Held: {sorted(meta)}", flush=True)
    store.publish(
        BOT_ROW, status="online",
        equity=(round(equity, 2) if equity is not None else None),
        pnl_abs=(round(pnl_abs, 2) if pnl_abs is not None else None),
        pnl_pct=(round(pnl_pct, 6) if pnl_pct is not None else None),
        open_trades=len(pos),
        closed_trades=stats["closed"], wins=stats["wins"], losses=stats["losses"],
        extra={"venue": TT_VENUE,
               "strategy": f"scout tickets ({'live' if live else 'shadow'})",
               # D1: total capital excluded from pnl_abs — self-describing
               **({"capital_adjust": round(capital_adjust["total"]
                                           + CAPITAL_ADJUST_USD, 2)}
                  if live else {}),
               "open_pos": [{"pair": f"{s}/USDC",
                             "tag": (("long-" if pos[s]["size"] > 0 else "short-")
                                     + (meta.get(s) or {}).get("lens", "ticket"))}
                            for s in pos],
               "scout_fresh": fresh, "stress_veto": stressed,
               # the bars actually in force this cycle (growth-rail visible)
               "bars": {lever: globals()[attr] for lever, attr in TUNABLE},
               "tuned": sorted(moved)})
    print(f"[ticket-taker] {iso(t_now)} equity "
          f"{equity if equity is None else round(equity, 2)} "
          f"open {len(pos)}/{MAX_OPEN} closed {stats['closed']} "
          f"({stats['wins']}W/{stats['losses']}L) scout_fresh={fresh}")


# ---------------------------------------------------------------------------


def selftest():
    print("Running Ticket Taker offline self-test...\n")
    # conviction bars (incl. the divergence lens)
    tk = {"breakout": [{"sym": "A", "range_pos": 0.96, "vol_m": 2.0},
                       {"sym": "B", "range_pos": 0.91, "vol_m": 2.0}],   # below bar
          "dip": [{"sym": "C", "range_pos": 0.04},
                  {"sym": "D", "range_pos": 0.08}],                      # below bar
          "momentum": [{"sym": "E", "chg_pct": 6.0, "vol_m": 3.0},
                       {"sym": "F", "chg_pct": 6.0, "vol_m": 1.0}],      # thin
          # [2026-07-17 BASIS FIX] fixture /8 with DIV_GAP_PP (500 -> 62.5):
          # G clears the bar, H sits below it. Intent pinned, not digits.
          "divergence": [{"sym": "G", "side": "short", "gap_pct": 87.5},
                         {"sym": "H", "side": "long", "gap_pct": -43.75}]}  # below bar
    picks = incredible(tk)
    assert [(l, t["sym"]) for l, t in picks] == \
        [("breakout", "A"), ("dip", "C"), ("momentum", "E"),
         ("divergence", "G")], picks

    # exit ladder — long and short
    t0 = now()
    from datetime import timedelta
    assert exit_reason(100.0, 104.1, t0, t0) == "tp"
    assert exit_reason(100.0, 96.9, t0, t0) == "sl"
    assert exit_reason(100.0, 101.0, t0 - timedelta(hours=49), t0) == "hold"
    assert exit_reason(100.0, 101.0, t0, t0) is None
    assert exit_reason(100.0, 95.9, t0, t0, is_long=False) == "tp"   # short profits down
    assert exit_reason(100.0, 103.1, t0, t0, is_long=False) == "sl"

    # [2026-07-22 FLAP FIX] the bars priced at entry govern the trade.
    # A position stamped under a WIDER sl (-0.04) does NOT book "sl" when the
    # module bar has snapped back to -0.03 — the measured 9/22 flap class.
    _wide = {"bars": {"tp": 0.06, "sl": -0.04, "max_hold_h": 72}}
    assert pos_bars(_wide) == (0.06, -0.04, 72.0)
    assert exit_reason(100.0, 96.5, t0, t0, bars=pos_bars(_wide)) is None, \
        "-3.5% under a grandfathered -4% bar -> still holding, no gap booked"
    assert exit_reason(100.0, 95.9, t0, t0, bars=pos_bars(_wide)) == "sl", \
        "the grandfathered bar itself still fires"
    assert exit_reason(100.0, 101.0, t0 - timedelta(hours=50), t0,
                       bars=pos_bars(_wide)) is None, \
        "grandfathered 72h hold outlives the module's 48h"
    # fail-safe: unstamped/legacy/junk positions behave exactly as before
    assert pos_bars({}) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    assert pos_bars(None) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    assert pos_bars({"bars": {"tp": "x"}}) == \
        (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), "junk stamp -> current bars"
    assert pos_bars({"bars": {"tp": -0.06, "sl": 0.04, "max_hold_h": 72}}) \
        == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), "nonsense signs -> current"
    # kill switch: LEVER_GRANDFATHER=off reverts behavior to close-time bars
    global LEVER_GRANDFATHER
    _lg = LEVER_GRANDFATHER
    LEVER_GRANDFATHER = False
    assert pos_bars(_wide) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), \
        "switch off -> stamps ignored, pre-fix behavior"
    LEVER_GRANDFATHER = _lg
    # entry_bars stamps every TUNABLE the trade was admitted/priced under
    assert set(entry_bars()) == {"tp", "sl", "max_hold_h", "div_gap_pp",
                                 "div_vol_m", "dip_range", "brk_range",
                                 "momo_chg"}

    # accounting round-trip incl. funding drag (long pays, short receives)
    b = PaperBroker(start_equity=1000.0, fee_bps=4.0)
    b.open("A", True, 0.5, 100.0)           # $50 clip
    b.mark("A", 105.0)
    drag = 0.5 * 105.0 * 0.0001 * 10        # signed: long, +1bp/h, 10h -> pays
    b.fees += drag
    pnl = b.close("A", 105.0)
    assert abs(pnl - 2.5) < 1e-9
    exp = 1000.0 + 2.5 - (0.5*100*0.0004) - (0.5*105*0.0004) - drag
    assert abs(b.equity() - exp) < 1e-9, (b.equity(), exp)
    b2 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
    b2.open("S", False, 0.5, 100.0)
    credit = (-0.5) * 100.0 * 0.0001 * 10   # signed: SHORT under +rate -> credit
    b2.fees += credit
    assert credit < 0 and b2.fees < 0.5*100*0.0004, "short must be credited"

    # constant-risk sizing: calm books size up, wild books size down, bounded
    assert vol_clip(None) == CLIP_USD, "no range data -> fallback clip"
    assert vol_clip(2.0) == CLIP_MAX, "calm 2%-range book hits the cap"
    assert abs(vol_clip(6.0) - 50.0) < 1e-9, "6% range -> $50 (1.5/3%)"
    assert abs(vol_clip(10.0) - 30.0) < 1e-9, "10% range -> $30"
    assert vol_clip(30.0) == CLIP_MIN, "wild book floors at CLIP_MIN"

    # [2026-07-17 RUN-ONCE KILL SEMANTICS] the boot gate: the cap refuses, the
    # kill switch must NOT (it has to reach the flatten). The negative fixture
    # is the one that matters — if this ever starts refusing on an armed kill
    # switch, a live taker abandons its book instead of closing it.
    class _R:
        def __init__(self, cap): self.max_notional = cap
    assert live_boot_gate(_R(None), live=True), "live with NO cap must refuse"
    assert live_boot_gate(_R(150.0), live=True) is None, "live with a cap proceeds"
    # the kill switch is NOT a boot gate here — armed or not, the gate is the
    # cap alone, so main() reaches kill_check() -> _flatten_all() -> halt.
    _prev = os.environ.get("REAL_MONEY_KILL")
    os.environ["REAL_MONEY_KILL"] = "ARMED"
    try:
        from venues.safety import kill_switch_armed
        assert kill_switch_armed() is True, "fixture must actually arm the switch"
        assert live_boot_gate(_R(150.0), live=True) is None, \
            ("an ARMED kill switch must NOT refuse the boot of a run-once bot — "
             "it must reach _flatten_all() and CLOSE the book, not strand it")
    finally:
        if _prev is None:
            os.environ.pop("REAL_MONEY_KILL", None)
        else:
            os.environ["REAL_MONEY_KILL"] = _prev
    # shadow never needs a cap
    assert live_boot_gate(_R(None), live=False) is None

    # [2026-07-16 ZOMBIE GUARD] delist give-up clock
    _t = now()
    assert delist_due(iso(_t - timedelta(hours=DELIST_GIVEUP_H + 1)), _t) is True
    assert delist_due(iso(_t - timedelta(hours=1)), _t) is False
    assert delist_due("garbage", _t) is False and delist_due(None, _t) is False

    # [2026-07-17 BASIS FIX] Lighter quotes funding per 8h; the old code
    # accrued `rate * hours` = 8x.
    #
    # HONEST SCOPE — this block PINS THE ARITHMETIC, it does NOT detect the
    # bug. Verified by mutation: re-introduce `rate * hours` in main() and
    # these assertions still pass, because they exercise funding_basis (which
    # has its own selftest) rather than the CALL SITE. The accrual is inline
    # in main()'s loop, so the only real detector is --selftest-live (tests 6
    # and 9), which drives that loop and caught the mutation immediately.
    # Left here as the worked example of the true numbers; do not mistake it
    # for the guard.
    _true = 1.0 * 100.0 * funding_basis.to_hourly(8e-4, "lighter") * 8.0
    assert abs(_true - 0.08) < 1e-12, _true
    assert abs(1.0 * 100.0 * 8e-4 * 8.0 - 0.64) < 1e-12    # what the bug paid
    assert abs(_true * funding_basis.LIGHTER_LEGACY_APR_FACTOR - 0.64) < 1e-12
    # a SHORT still gets the credit, and it is the true-sized one
    _short = -1.0 * 100.0 * funding_basis.to_hourly(8e-4, "lighter") * 8.0
    assert _short < 0 and abs(_short + 0.08) < 1e-12, _short

    # ---- LIVE LENS ALLOW-LIST — fail-CLOSED, and the negative fixture ------
    # A guard that never fires is not a guard (adversarial-verify-3-lens).
    assert allowed_lenses("lighter_live") == {"divergence"}, allowed_lenses("lighter_live")
    assert allowed_lenses("lighter_shadow") == ALL_LENSES   # control arm grades all 4
    assert allowed_lenses("lighter_paper") == ALL_LENSES
    # an UNKNOWN mode must not silently widen live (it is not "lighter_live",
    # so it gets the shadow set — and TT_VENUE is validated against TT_MODES
    # before this is ever reached)
    assert allowed_lenses("") == ALL_LENSES

    # THE POINT: a DARK brain vetoes NOTHING (fail-open by design), and the
    # allow-list must hold anyway. This is the fixture that proves live cannot
    # re-acquire a rejected lens when the brain goes down.
    # [2026-07-21 IMB-24] the veto's evidence basis is EPISODES when v3
    # fields are present, raw fallback otherwise:
    # raw-only payload (v2 relapse) — old rule verbatim
    assert vetoed_lenses({"m": {"n4h": 80, "avg4h_pct": -1.0, "hit4h": 0.3}}) == {"m"}
    assert vetoed_lenses({"m": {"n4h": 50, "avg4h_pct": -1.0, "hit4h": 0.3}}) == set()
    # episode payload — the serial-correlation case IMB-24 exists for: a lens
    # clearing the raw floor 16x over on too few independent episodes/symbols
    # no longer clears the floor…
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 20, "n_syms": 15,
                                "eavg4h_pct": -0.95, "ehit4h": 0.29}}) == set()
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 34, "n_syms": 8,
                                "eavg4h_pct": -0.95, "ehit4h": 0.29}}) == set()
    # …while real episode evidence vetoes on the DEDUP'D grade
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 117, "n_syms": 29,
                                "eavg4h_pct": -0.30, "ehit4h": 0.427}}) == {"m"}
    # the measured 21-Jul dip flip: raw says allowed (hit4h 0.505), episodes
    # say vetoed (ehit4h 0.495) — the episode number wins when present
    _dip = {"n4h": 6072, "avg4h_pct": -0.048, "hit4h": 0.505,
            "eps4h": 760, "n_syms": 110, "eavg4h_pct": -0.053, "ehit4h": 0.495}
    assert vetoed_lenses({"dip": _dip}) == {"dip"}
    assert vetoed_lenses({"dip": {k: v for k, v in _dip.items()
                                  if not k.startswith(("e", "n_s"))}}) == set()

    _dark = vetoed_lenses({})
    assert _dark == set(), _dark                    # confirms the fail-open premise
    _live_fills = {l for l, _ in incredible(tk)
                   if l in allowed_lenses("lighter_live") and l not in _dark}
    assert _live_fills == {"divergence"}, _live_fills
    # ...while the shadow arm still fills every lens the fixture qualifies
    _shadow_fills = {l for l, _ in incredible(tk)
                     if l in allowed_lenses("lighter_shadow") and l not in _dark}
    assert _shadow_fills == {"breakout", "dip", "momentum", "divergence"}, _shadow_fills
    # and the brain stays SENIOR on top: it can still restrict divergence away
    _senior = {l for l, _ in incredible(tk)
               if l in allowed_lenses("lighter_live")
               and l not in {"divergence"}}
    assert _senior == set(), _senior

    # ---- SYMBOL SPACE — the live-only stranding bug, pinned -----------------
    # This bot keys everything venue-native ("1000BONK"); LighterClient speaks
    # FLEET ("kBONK") in positions() AND in market_close()'s own lookup. The
    # round trip must close for every 1000-market or a real position is stranded
    # with no exit rule. 1000BONK was a live divergence ticket when this landed.
    for _native in ("1000BONK", "1000PEPE", "1000SHIB", "1000FLOKI",
                    "1000NOT", "1000TOSHI"):
        _f = _fleet(_native)                       # what the venue calls it
        assert _f.startswith("k"), (_native, _f)
        assert to_lighter(_f)[0] == _native, (_native, _f, to_lighter(_f)[0])
    # 1000NOT/1000TOSHI are the regression: they were absent from _EXPLICIT, so
    # to_lighter("kNOT") used to return "kNOT" — a symbol the venue does not have.
    assert to_lighter("kNOT")[0] == "1000NOT"
    assert to_lighter("kTOSHI")[0] == "1000TOSHI"
    # plain symbols must be untouched in both directions
    for _plain in ("BTC", "ETH", "SOL", "XPD", "DRAM"):
        assert _fleet(_plain) == _plain and to_lighter(_plain)[0] == _plain, _plain
    # raw-unit markets keep their size multiplier (PEPE != kPEPE)
    assert to_lighter("PEPE") == ("1000PEPE", 0.001)
    assert to_lighter("kPEPE") == ("1000PEPE", 1.0)

    # [2026-07-21] post-stop cooldown stamps: active in the future, inactive
    # in the past, fail-OPEN on junk/absent (a corrupt stamp must never
    # embargo a symbol forever)
    _ct = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    assert _sl_active(iso(_ct + timedelta(hours=1)), _ct)
    assert not _sl_active(iso(_ct - timedelta(hours=1)), _ct)
    assert not _sl_active(None, _ct) and not _sl_active("junk", _ct)

    print("All Ticket Taker self-tests passed (bars incl. divergence, "
          "long/short exits, signed funding on the TRUE 8h basis, "
          "constant-risk sizing, delist give-up, LIVE lens allow-list "
          "fail-CLOSED vs a dark brain, symbol round-trip for all six "
          "1000-markets).")


# ---------------------------------------------------------------------------
# LIVE ORDER PATH — driven end-to-end against a stub venue.
#
# The live branch is REFUSED in production (evidence, not safety), so without
# this it would be code no one has ever executed — which is how the fleet got
# a "live-ready" bot that would not have placed a single order (c5924e4). The
# stub speaks LighterClient's interface and records what it was asked to do;
# no network, no signer, no money.
# ---------------------------------------------------------------------------


class _StubVenue:
    """Records orders instead of sending them. Mirrors the LighterClient
    surface the live path touches: positions / account_value / market_open /
    market_close / last_fill_detail / last_fill.

    [2026-07-17] IT MUST MIRROR `last_fill_detail`, NOT JUST `last_fill`.
    Production's LighterClient has both, and `_real_fill` prefers the detail
    API — so a stub carrying only `last_fill` sends every test down the
    LEGACY fallback branch and leaves the real production path untested. That
    is exactly how `_StubRails`, lacking `assert_can_start`, let tests 3/4 pass
    against a path production could not reach (17-Jul entry (p)). A stub that
    is missing a method does not fail — it silently tests something else."""

    def __init__(self, equity=1000.0, pos=None, fills=None, fill_reason=None,
                 echo_ids=True):
        self._equity = equity
        self._pos = dict(pos or {})
        self._fills = dict(fills or {})     # sym -> REAL fill px the tape returns
        self._fill_reason = fill_reason     # reason reported when there is no fill
        # echo_ids=False models THE failure this stub exists for: Lighter stops
        # echoing client_order_index back as ask_client_id/bid_client_id, so an
        # id-filtered read matches nothing while the tape itself is perfectly
        # readable. That round trip is UNPROVEN in production — the taker's only
        # two live orders predate the fill-read code — so the id working is an
        # assumption, and this is the fixture that stops it being a silent one.
        self._echo_ids = echo_ids
        self.opens, self.closes, self.value_reads = [], [], 0
        self.fail_close = set()
        self._cid = 0
        self.last_cid = None
        self.seen_client_ids = []      # what the fill read was ACTUALLY given

    def account_value(self):
        self.value_reads += 1
        return self._equity

    def positions(self):
        return {s: dict(v) for s, v in self._pos.items() if v.get("size")}

    def market_open(self, coin, is_long, size):
        self.opens.append((coin, is_long, size))
        self._pos[coin] = {"size": size if is_long else -size,
                           "entry": self._fills.get(coin, 100.0)}
        # mirrors the real client: the order's client id comes back so the fill
        # read can name it. A stub that omits it sends the caller down the
        # id-less heuristic and leaves the exact-match path untested.
        self._cid += 1
        self.last_cid = self._cid
        return {"tx": "stub", "client_order_index": self._cid}

    def market_close(self, coin):
        if coin in self.fail_close:
            raise RuntimeError(f"stub: close {coin} refused")
        self.closes.append(coin)
        self._pos.pop(coin, None)
        self._cid += 1
        self.last_cid = self._cid
        return {"tx": "stub", "client_order_index": self._cid}

    def last_fill_detail(self, coin, is_ask, since_ts, lookback=10,
                         client_id=None):
        self.seen_client_ids.append(client_id)
        px = self._fills.get(coin)
        if px:
            if client_id is not None and not self._echo_ids:
                # The tape IS readable — our id simply is not on it. This is the
                # venue layer's real string for that (lighter_client.py:726) and
                # the reason strings are the contract `read_fill` keys its retry
                # on, so a paraphrase here would test nothing.
                return None, "no-match:both(no-match:trades)"
            return px, ("trades" if client_id is not None else "trades(approx)")
        return None, (self._fill_reason or "empty:both(stub)")

    def last_fill(self, coin, is_ask, since_ts, lookback=10, client_id=None):
        # delegates exactly as the real client does
        return self.last_fill_detail(coin, is_ask, since_ts, lookback,
                                     client_id)[0]


class _StubRails:
    """SafetyRails' surface, with the real notional_ok/daily_loss_hit rules."""

    def __init__(self, max_notional=None, killed=False, max_daily_loss=30.0):
        from venues.safety import SafetyRails
        self.max_notional = max_notional
        self.max_daily_loss = max_daily_loss
        self.killed = killed
        self.live = True
        self._real = SafetyRails.__new__(SafetyRails)
        self._real.max_notional = max_notional
        self._real.max_daily_loss = max_daily_loss
        self._real.live = True
        self.confirmed = []

    def kill_check(self):
        return self.killed

    def notional_ok(self, open_ntl, add_usd):
        return self._real.notional_ok(open_ntl, add_usd)

    def daily_loss_hit(self, day_start_equity, equity):
        return self._real.daily_loss_hit(day_start_equity, equity)

    def confirm_daily_loss(self, day_start, first_eq, pct_limit, read_equity):
        # the REAL one sleeps 60s to debounce; the rule under test here is
        # "what does the taker do once it IS confirmed", so confirm instantly.
        self.confirmed.append((day_start, first_eq))
        return True, first_eq


def _selftest_live():
    """Drive main()'s LIVE branch against the stub. Asserts the properties the
    order path exists to guarantee — every one of them a rail that has already
    cost real money somewhere in this fleet."""
    import types
    global TT_VENUE, BOT_ROW
    print("Running Ticket Taker LIVE order-path self-test (stub venue)...\n")

    _saved_env = (TT_VENUE, BOT_ROW)
    TT_VENUE, BOT_ROW = "lighter_live", BOT + "-lighter"
    # [2026-07-17] This harness rebinds the MODULE GLOBAL; the identity guard in
    # main() reads os.environ (it must — the global carries a default and so
    # cannot tell "unset" from "set to shadow"). One fixture below drives
    # _supervised() -> bare main(), which trips that guard before the crash it
    # is actually testing. Production always sets the var, so give the harness
    # one too; the guard has its own dedicated fixture in selftest().
    _saved_ttv = os.environ.get("TT_VENUE")
    os.environ["TT_VENUE"] = "lighter_live"

    # --- capture every side effect instead of hitting Postgres -------------
    captured = {"paper": [], "orders": [], "state": {}, "halts": [],
                "published": []}
    _real = {k: getattr(store, k) for k in
             ("publish_paper_trade", "publish_venue_order", "save_state",
              "load_state", "load_state_checked", "publish", "save_daily_halt",
              "load_daily_halt", "heartbeat")}
    store.heartbeat = lambda bot: None
    store.publish_paper_trade = lambda bot, **kw: captured["paper"].append((bot, kw))
    store.publish_venue_order = lambda bot, **kw: captured["orders"].append((bot, kw))

    # [2026-07-17 AUDIT] These two stubs must mirror the REAL functions'
    # RETURN CONTRACTS, not just their names — a stub that gets the shape right
    # and the semantics wrong makes every green assertion below meaningless.
    #   save_state: really returns True/False and NEVER raises
    #     (bot_pnl_store.py:222-250). The old stub returned None (dict
    #     __setitem__), i.e. FALSY — so the moment main() started checking that
    #     return, every fixture would have reported a failed write. The stub was
    #     silently teaching the bot that all writes fail.
    #   load_state_checked: (ok, state) — ok=False means "I could not find out",
    #     which is NOT "no row". Unstubbed, it would have reached real Postgres
    #     from inside the selftest and returned (False, None), tripping main()'s
    #     new READ-FAILED refusal in every live fixture.
    # `captured["fail_writes"]` / `["fail_reads"]` let a fixture drive the
    # failure halves deliberately — see fixtures 11a-11c.
    captured["fail_writes"] = False
    captured["fail_reads"] = False

    def _stub_save(k, v):
        if captured["fail_writes"]:
            return False
        captured["state"][k] = v
        return True

    def _stub_load_checked(k):
        if captured["fail_reads"]:
            return (False, None)          # read FAILED — not "no row"
        return (True, captured["state"].get(k))

    store.save_state = _stub_save
    store.load_state_checked = _stub_load_checked
    store.load_state = lambda k: captured["state"].get(k)
    store.publish = lambda bot, **kw: captured["published"].append((bot, kw))
    store.save_daily_halt = lambda bot, day, eq=None: captured["halts"].append((bot, day, eq))
    store.load_daily_halt = lambda bot, day: None

    _real_fetch = globals()["fetch_marks_and_funding"]

    def _stub_market(marks=None, funding=None, ranges=None):
        globals()["fetch_marks_and_funding"] = lambda: (
            dict(marks or {}), dict(funding or {}), dict(ranges or {}))

    def _scout(tickets):
        captured["state"][SCOUT_KEY] = {
            "updated": iso(now()), "ttl_sec": 900, "tickets": tickets,
            "stress": {"med": 1.0}}

    def _boom(*_a, **_kw):
        # the REAL 17-Jul crash: LighterClient -> `import lighter` -> missing
        # wheel -> VenueError, every cycle, behind an "online" row.
        raise RuntimeError("lighter-sdk missing (pip install lighter-sdk): "
                           "No module named 'lighter'")

    try:
        # ================================================================
        # 1) ENTRY sends a REAL order — not a modelled fill
        # ================================================================
        captured["state"].clear()
        _stub_market(marks={"AAA": 100.0}, funding={}, ranges={"AAA": 6.0})
        _scout({"divergence": [{"sym": "AAA", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"AAA": 100.5})
        r = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [("AAA", False, 0.5)], v.opens        # $50 clip @ 100
        assert len(captured["orders"]) == 1, captured["orders"]
        _o = captured["orders"][0][1]
        assert _o["shadow"] is False and _o["side"] == "sell"
        # the REAL fill (100.5) is recorded, and selling above the decision
        # price is NEGATIVE slippage = better than decided
        assert _o["px_fill"] == 100.5 and _o["px_decision"] == 100.0
        assert _o["slippage_bps"] < 0, _o["slippage_bps"]
        # live state is its OWN key, and it never writes a broker snapshot
        assert LIVE_STATE_KEY in captured["state"]
        assert STATE_KEY not in captured["state"]
        assert "broker" not in captured["state"][LIVE_STATE_KEY]
        # entry recorded at the REAL fill, not the decision price
        assert captured["state"][LIVE_STATE_KEY]["meta"]["AAA"]["entry"] == 100.5

        # ================================================================
        # 2) NOTIONAL CAP is senior — the cap-breaching entry never sends
        # ================================================================
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"BBB": 100.0}, funding={}, ranges={"BBB": 6.0})
        _scout({"divergence": [{"sym": "BBB", "side": "short", "gap_pct": 99.0}]})
        # $120 already deployed at its own clip, cap $150, this clip is $50
        v = _StubVenue(equity=1000.0, pos={"HELD": {"size": 1.0, "entry": 120.0}})
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0, "meta": {"HELD": {"clip": 120.0,
                                                        "lens": "divergence"}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [], f"cap breach: {v.opens}"
        assert captured["orders"] == []

        # ================================================================
        # 3) KILL SWITCH flattens the venue's book and halts — no entries
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"CCC": 100.0}, funding={}, ranges={"CCC": 6.0})
        _scout({"divergence": [{"sym": "CCC", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, pos={"ZZZ": {"size": 1.0, "entry": 90.0}},
                       fills={"ZZZ": 95.0})
        r = _StubRails(max_notional=150.0, killed=True)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"ZZZ": {"clip": 90.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.closes == ["ZZZ"], v.closes
        assert v.opens == [], "halted bot must not enter"
        assert len(captured["paper"]) == 1, captured["paper"]
        # the flatten books the ledger row like a normal close: a long closed
        # at 95 from entry 90 = +5
        _p = captured["paper"][0][1]
        assert _p["reason"] == "long-divergence_kill_switch", _p["reason"]
        assert abs(_p["pnl_abs"] - 5.0) < 1e-9, _p["pnl_abs"]
        assert _p["shadow"] is False
        assert captured["published"][-1][1]["status"] == "halted"

        # ================================================================
        # 4) DAILY LOSS flattens + halts DURABLY (survives the next cycle)
        # ================================================================
        captured["state"].clear()
        captured["halts"].clear()
        _stub_market(marks={"DDD": 100.0}, funding={}, ranges={"DDD": 6.0})
        _scout({"divergence": [{"sym": "DDD", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=940.0, pos={"YYY": {"size": 1.0, "entry": 90.0}},
                       fills={"YYY": 90.0})
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"YYY": {"clip": 90.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0},
            "day_start": {"day": now().date().isoformat(), "equity": 1000.0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert r.confirmed, "a loss breach must be CONFIRMED before flattening"
        assert v.closes == ["YYY"], v.closes
        assert v.opens == []
        assert captured["halts"] and captured["halts"][0][0] == BOT_ROW
        # ... and the halt is durable: replay with load_daily_halt returning it
        store.load_daily_halt = lambda bot, day: {"halted_date": day,
                                                  "day_start_equity": 1000.0}
        v2 = _StubVenue(equity=940.0)
        r2 = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v2, "rails": r2, "broker": None})
        assert v2.opens == [], "a restored halt must still block entries"
        store.load_daily_halt = lambda bot, day: None

        # ================================================================
        # 5) A FAILED CLOSE never books a phantom exit
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"EEE": 200.0}, funding={}, ranges={})
        _scout({})
        v = _StubVenue(equity=1000.0, pos={"EEE": {"size": 1.0, "entry": 100.0}})
        v.fail_close.add("EEE")                     # +100% -> TP, but close fails
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"EEE": {"clip": 100.0, "lens": "breakout",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert captured["paper"] == [], "a failed close must not book a row"
        assert "EEE" in captured["state"][LIVE_STATE_KEY]["meta"], \
            "a failed close must KEEP the position — the venue still holds it"

        # ================================================================
        # 6) LIVE funding is the VENUE's — it must not hit modelled equity,
        #    but it must still reach the ledger and the win/loss call
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"FFF": 104.0}, funding={"FFF": 8e-4}, ranges={})
        _scout({})
        v = _StubVenue(equity=1234.56, pos={"FFF": {"size": 1.0, "entry": 100.0}},
                       fills={"FFF": 104.0})
        r = _StubRails(max_notional=150.0)
        _opened = iso(now() - timedelta(hours=8))
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"FFF": {"clip": 100.0, "lens": "breakout",
                             "opened": _opened, "accrued_to": _opened,
                             "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert len(captured["paper"]) == 1, captured["paper"]
        _p = captured["paper"][0][1]
        # price +4 on a long; funding on the TRUE 8h basis = 1*104*1e-4*8 = 0.0832
        # (the 8x bug would have charged 0.6656). net = 4 - 0.0832 - 0 (no fee).
        assert abs(_p["pnl_abs"] - (4.0 - 0.0832)) < 1e-4, _p["pnl_abs"]
        # published equity is the VENUE's, never a modelled one
        _pub = captured["published"][-1][1]
        assert _pub["equity"] == 1234.56, _pub["equity"]
        # [2026-07-21 D1] published live P&L is CAPITAL-ADJUSTED: equity −
        # baseline − guard-recorded capital (0 here) − the env backfill.
        # Computed from the module constant so the fixture tracks the
        # contract, not a frozen number (this assert still read the pre-D1
        # 234.56 after D1 shipped — it only ever runs on signer-wheel
        # machines, where it failed on GOOD news).
        assert abs(_pub["pnl_abs"] - (234.56 - CAPITAL_ADJUST_USD)) < 1e-9, \
            _pub["pnl_abs"]

        # ================================================================
        # 7) UNREADABLE positions must SKIP the cycle — never trade blind.
        #    The negative fixture that matters: a phantom-empty set zeroes
        #    both the slot count and the cap's input, so "no positions" would
        #    read as "full book available" on top of real open risk.
        # ================================================================
        captured["state"].clear()
        _stub_market(marks={"GGG": 100.0}, funding={}, ranges={"GGG": 6.0})
        _scout({"divergence": [{"sym": "GGG", "side": "short", "gap_pct": 99.0}]})

        class _BlindVenue(_StubVenue):
            def positions(self):
                raise RuntimeError("stub: venue unreadable")

        v = _BlindVenue(equity=1000.0)
        r = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [], f"traded blind: {v.opens}"

        # ================================================================
        # 8) A FAILED FLATTEN must not publish open_trades=0. The halted row
        #    has to show the book it could not close, or the retry rail above
        #    is invisible behind a green-looking row.
        # ================================================================
        captured["state"].clear()
        captured["published"].clear()
        _stub_market(marks={"HHH": 100.0}, funding={}, ranges={})
        _scout({})
        v = _StubVenue(equity=1000.0, pos={"HHH": {"size": 1.0, "entry": 100.0}})
        v.fail_close.add("HHH")
        r = _StubRails(max_notional=150.0, killed=True)   # kill -> flatten fails
        main(_ctx={"venue": v, "rails": r, "broker": None})
        _pub = captured["published"][-1][1]
        assert _pub["status"] == "halted"
        assert _pub["open_trades"] == 1, \
            f"a failed flatten must report the open book, got {_pub['open_trades']}"
        assert _pub["extra"]["flatten_incomplete"] is True

        # ================================================================
        # 9) THE SHADOW ARM MUST NOT REGRESS. It is DEPLOYED and it is
        #    collecting the only evidence a go-live could ever rest on;
        #    breaking it mid-flight costs exactly what we are waiting for.
        #    The live refactor moved every call site in this loop off
        #    broker.pos, so drive the dry_run path end-to-end too.
        # ================================================================
        TT_VENUE, BOT_ROW = "lighter_shadow", BOT + "-lshadow"
        captured["state"].clear()
        captured["paper"].clear()
        captured["published"].clear()
        _stub_market(marks={"III": 104.0}, funding={"III": 8e-4},
                     ranges={"III": 6.0})
        _scout({"divergence": [{"sym": "III", "side": "short", "gap_pct": 99.0}]})
        b = PaperBroker(start_equity=1000.0, fee_bps=4.0)
        _opened = iso(now() - timedelta(hours=8))
        b.open("III", True, 1.0, 100.0)          # held long, +4% -> TP
        captured["state"][STATE_KEY] = {
            "broker": b.to_state(),
            "meta": {"III": {"clip": 100.0, "lens": "breakout",
                             "opened": _opened, "accrued_to": _opened,
                             "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        b2 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
        main(_ctx={"venue": None, "rails": None, "broker": b2})
        # closed through the BROKER, and the shadow arm writes the shadow row
        assert len(captured["paper"]) == 1, captured["paper"]
        _p = captured["paper"][0][1]
        assert _p["shadow"] is True and _p["reason"] == "long-breakout_tp"
        # funding on the TRUE 8h basis reaches the ledger AND the equity here
        # (a shadow book has no venue charging it): 1*104*1e-4*8 = 0.0832
        # price +4, fees 2*100*0.0004 = 0.08  ->  net = 4 - 0.0832 - 0.08
        assert abs(_p["pnl_abs"] - (4.0 - 0.0832 - 0.08)) < 1e-4, _p["pnl_abs"]
        # shadow persists a BROKER snapshot under its own key, never the live one
        assert STATE_KEY in captured["state"] and LIVE_STATE_KEY not in captured["state"]
        assert "broker" in captured["state"][STATE_KEY]
        # equity is the broker's, and the drag landed in it. Leg by leg, the
        # broker charges on ACTUAL notional at each leg (not the ledger's
        # modelled 2*clip*fee above — a pre-existing, deliberate difference):
        #   0.0400  restored entry fee on the held long (1 @ 100)
        # + 0.0832  funding, TRUE 8h basis (1 * 104 * 1e-4 * 8)
        # + 0.0416  close fee at the EXIT price 104, not the entry
        # + 0.0200  entry fee on the new divergence short (50/104 @ 104)
        _pub = captured["published"][-1][1]
        assert _pub["extra"]["venue"] == "lighter_shadow"
        assert abs(b2.fees - 0.1848) < 1e-4, b2.fees
        # THE basis detector: with the 8x bug the funding leg alone was 0.6656
        # and this total would be 0.7672. This assertion is what fails if
        # anyone ever routes this accrual around funding_basis again.
        assert abs(b2.fees - 0.7672) > 1e-2, "8x funding over-accrual is BACK"
        # and it still takes new tickets (the entry pass survived the refactor)
        assert _pub["open_trades"] == 1, _pub["open_trades"]

        # ================================================================
        # 10) A CRASH MUST MARK THE ROW. The negative fixture is the REAL
        #     incident: the exact VenueError the missing lighter-sdk wheel
        #     raised, crash-looping behind a row that still read "online".
        # ================================================================
        _status = []
        _real_set = store.set_status
        _real_load = store.load_state
        store.set_status = lambda bot, st: _status.append((bot, st))
        try:
            # The incident crashed at LighterClient construction — line 335 of
            # main(), propagating straight out to <module> UNCAUGHT. Reproduce
            # the shape (an uncaught raise from main's body) rather than the
            # exact call: the fetch path is CAUGHT and returns, so raising
            # there would prove nothing about this control. Verified the hard
            # way — the first draft of this fixture did exactly that and passed
            # against a supervisor that had never run.
            globals()["fetch_marks_and_funding"] = lambda: ({}, {}, {})
            store.load_state = _boom
            try:
                _supervised()
                raise AssertionError("the crash must propagate")
            except RuntimeError:
                pass               # re-raised by design
            store.load_state = _real_load
            assert _status == [(BOT_ROW, "error")], \
                f"a crash must mark the row, got {_status}"
            # ... and a boot REFUSAL is not a crash: it must pass through
            # untouched (SafetyRails._publish_refusal already owns that row).
            # [2026-07-17] This used to assert on the EVIDENCE refusal
            # (lighter_live raises SystemExit). The operator lifted that gate,
            # so the fixture had to be re-pointed at a refusal that still
            # exists — otherwise it would assert that a removed gate is present
            # and demand the code stay as it was. The IDENTITY refusal (TT_VENUE
            # unset) is the right subject: it is a boot refusal on the same path,
            # and unlike the old one it cannot be lifted by a decision.
            _status.clear()
            globals()["fetch_marks_and_funding"] = lambda: ({}, {}, {})
            _ttv_save = os.environ.get("TT_VENUE")
            try:
                os.environ.pop("TT_VENUE", None)
                try:
                    _supervised()          # no _ctx, no TT_VENUE -> identity refusal
                    raise AssertionError("an unset TT_VENUE must refuse")
                except SystemExit:
                    pass
                assert _status == [], f"a refusal is not a crash, got {_status}"
            finally:
                if _ttv_save is None:
                    os.environ.pop("TT_VENUE", None)
                else:
                    os.environ["TT_VENUE"] = _ttv_save
        finally:
            store.set_status = _real_set
            store.load_state = _real_load

        # ================================================================
        # 11) THE TIDE RIDER HANDOVER. The live arm inherits the sub-account
        #     Tide Rider is vacating. A leftover position there must HALT the
        #     bot, not be silently adopted onto the taker's exit ladder.
        # ================================================================
        TT_VENUE, BOT_ROW = "lighter_live", BOT + "-lighter"
        captured["state"].clear()
        captured["paper"].clear()
        _status = []
        _real_set = store.set_status
        store.set_status = lambda bot, st: _status.append((bot, st))
        try:
            # TRX at Tide Rider's entry, 5% against — inside the taker's ±4% TP
            # bar, so an ADOPTING bot would close a trend position on the
            # taker's rule. It must refuse instead.
            _stub_market(marks={"TRX": 0.2625}, funding={}, ranges={})
            _scout({"divergence": [{"sym": "AAA", "side": "short", "gap_pct": 99.0}]})
            v = _StubVenue(equity=34.67, pos={"TRX": {"size": 100.0, "entry": 0.25}})
            r = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67, "meta": {},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            # [2026-07-17 AUDIT] No longer a SystemExit: the guard is SCOPED to
            # the foreign symbols. Everything this fixture ever asserted still
            # holds — the stranger is not managed, nothing is traded, the row is
            # marked — but the bot now completes its cycle instead of dying,
            # which is what lets 11a (below) keep its own stops.
            main(_ctx={"venue": v, "rails": r, "broker": None})
            assert v.closes == [], f"must not manage a foreign position: {v.closes}"
            assert v.opens == [], f"must not trade on a dirty account: {v.opens}"
            assert captured["paper"] == [], "must not book a foreign close"
            assert _status[0] == (BOT_ROW, "error"), \
                f"a dirty account must mark the row: {_status}"

            # ================================================================
            # 11a) THE BUG THIS FIXTURE NEVER CAUGHT: our OWN position, held
            #      ALONGSIDE the stranger, must keep its stop-loss. The case
            #      above is all-foreign (meta={}) — the one shape where
            #      "abandon everything" and "abandon only the stranger" are
            #      INDISTINGUISHABLE. So `assert v.closes == []` passed for the
            #      whole life of the defect while encoding it as the contract.
            #      Mixed is the shape that tells them apart, and it is the shape
            #      production actually has: a lost meta write (or one Postgres
            #      blip) puts a stranger next to real, stopped positions.
            # ================================================================
            _status.clear()
            captured["paper"].clear()
            # OURS: a divergence SHORT 10% against us — far through the -3% stop.
            # THEIRS: Tide Rider's TRX, untouched.
            _stub_market(marks={"OWN": 110.0, "TRX": 0.2625}, funding={}, ranges={})
            v3 = _StubVenue(equity=34.67,
                            pos={"OWN": {"size": -0.15, "entry": 100.0},
                                 "TRX": {"size": 100.0, "entry": 0.25}},
                            fills={"OWN": 110.0, "TRX": 0.2625})
            r3 = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67,
                "meta": {"OWN": {"lens": "divergence", "opened": iso(now()),
                                 "entry": 100.0, "clip": 15.0, "is_long": False}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v3, "rails": r3, "broker": None})
            assert "OWN" in v3.closes, (
                "REGRESSION: our own position was abandoned because a stranger "
                f"shared the account — this is the whole bug: {v3.closes}")
            assert "TRX" not in v3.closes, \
                f"the stranger must still not be managed: {v3.closes}"
            assert v3.opens == [], f"still no new entries while dirty: {v3.opens}"
            assert _status[0] == (BOT_ROW, "error"), "still marks the row"

            # ================================================================
            # 11b) A FAILED READ IS NOT A DIRTY ACCOUNT. One Postgres blip used
            #      to yield meta={} -> every position "foreign" -> the guard
            #      fired on a CLEAN account, stopping the exit ladder on real
            #      money and sending the operator hunting a phantom stranger.
            # ================================================================
            _status.clear()
            captured["fail_reads"] = True
            v4 = _StubVenue(equity=34.67, pos={"OWN": {"size": -0.15, "entry": 100.0}},
                            fills={"OWN": 110.0})
            try:
                main(_ctx={"venue": v4, "rails": _StubRails(max_notional=150.0),
                           "broker": None})
                raise AssertionError("an unreadable state must not be guessed at")
            except SystemExit as e:
                assert "READ FAILED" in str(e), str(e)
                assert "DIRTY ACCOUNT" not in str(e), \
                    f"must NOT blame a dirty account for a DB fault: {e}"
            assert v4.closes == [] and v4.opens == [], \
                "a blind cycle must not trade on either side"
            captured["fail_reads"] = False

            # ================================================================
            # 11c) A FAILED WRITE MUST PAGE. save_state returns False and never
            #      raises, so a lost meta write is how a position becomes
            #      unattributable — and therefore unstoppable — out of nothing
            #      but a DB blip. It cannot be undone; it must not be silent.
            # ================================================================
            _status.clear()
            captured["fail_writes"] = True
            v5 = _StubVenue(equity=34.67, pos={"OWN": {"size": -0.15, "entry": 100.0}},
                            fills={"OWN": 100.5})
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67,
                "meta": {"OWN": {"lens": "divergence", "opened": iso(now()),
                                 "entry": 100.0, "clip": 15.0, "is_long": False}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v5, "rails": _StubRails(max_notional=150.0),
                       "broker": None})
            assert (BOT_ROW, "error") in _status, \
                f"a failed meta write must mark the row: {_status}"
            captured["fail_writes"] = False
            _status.clear()

            # ... and the kill switch stays the escape hatch: it runs ABOVE the
            # guard, so REAL_MONEY_KILL can still flatten a dirty account.
            _status.clear()
            v2 = _StubVenue(equity=34.67, pos={"TRX": {"size": 100.0, "entry": 0.25}},
                            fills={"TRX": 0.2625})
            r2 = _StubRails(max_notional=150.0, killed=True)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67, "meta": {},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v2, "rails": r2, "broker": None})
            assert v2.closes == ["TRX"], \
                f"the kill switch must still flatten a dirty account: {v2.closes}"

            # ... and a CLEAN account (every position has meta) proceeds.
            _stub_market(marks={"KNOWN": 100.0}, funding={}, ranges={})
            _scout({})
            v3 = _StubVenue(equity=1000.0, pos={"KNOWN": {"size": 1.0, "entry": 100.0}})
            r3 = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 1000.0,
                "meta": {"KNOWN": {"clip": 100.0, "lens": "divergence",
                                   "opened": iso(now()), "funding_paid": 0.0}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v3, "rails": r3, "broker": None})   # must not raise
        finally:
            store.set_status = _real_set

        # ================================================================
        # 12) FILL TELEMETRY is a DETECTOR — a measured 0 is a 0, and an
        #     unmeasured leg is NULL *and names why*.
        #
        #     Both halves are regression fixtures for real 17-Jul defects:
        #     (a) the taker's first two REAL orders recorded px_fill ==
        #         px_decision with slippage NULL and NO reason anywhere — 0 of
        #         57 real-money orders fleet-wide had ever carried a measured
        #         fill, and nobody could ask the ledger why.
        #     (b) 1000BONK's REAL fill was 0.003275 against a decision price of
        #         0.003275 — a genuinely perfect fill. The old `d == f` rule
        #         inferred "no read" and THREW THE MEASUREMENT AWAY.
        #     Mutation-checked: reverting _slip_bps_of to the `d == f`
        #     inference must fail (a) or (b).
        # ================================================================
        captured["state"].clear()
        captured["orders"].clear()
        # (b) a REAL fill exactly ON the mark -> slippage 0.0, measured True
        _stub_market(marks={"MRK": 100.0}, funding={}, ranges={"MRK": 6.0})
        _scout({"divergence": [{"sym": "MRK", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"MRK": 100.0})   # fill == decision
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert _o["px_fill"] == 100.0 and _o["px_decision"] == 100.0
        assert _o["slippage_bps"] == 0.0, \
            ("a MEASURED at-mark fill must record 0.0, not None — an at-mark "
             f"fill is a measurement, not a failure: {_o['slippage_bps']!r}")
        assert _o["raw"]["measured"] is True, _o["raw"]
        # EXACT match, not the (side, since_ts) heuristic: the order's own
        # client id must reach the read, or the fill is a VWAP of whatever else
        # we happened to trade on that side inside the window.
        assert _o["raw"]["fill_src"] == "trades", \
            (f"fill_src {_o['raw']['fill_src']!r} — '(approx)' means the client "
             f"id did NOT reach last_fill_detail, so the read is a blend")
        assert v.seen_client_ids == [v.last_cid], \
            (f"the fill read must be given the order's client id: "
             f"got {v.seen_client_ids!r}, order was {v.last_cid!r}")

        # (a) NO read -> decision price recorded, slippage NULL, reason NAMED
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"UNM": 100.0}, funding={}, ranges={"UNM": 6.0})
        _scout({"divergence": [{"sym": "UNM", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={},
                       fill_reason="api-error:trades:VenueError:boom")
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert v.opens, "the order must still SEND — telemetry never blocks it"
        assert _o["px_fill"] == 100.0, _o          # falls back to the decision
        assert _o["slippage_bps"] is None, \
            f"an UNMEASURED leg must be NULL, never 0.0: {_o['slippage_bps']!r}"
        assert _o["raw"]["measured"] is False, _o["raw"]
        assert "api-error" in (_o["raw"]["fill_src"] or ""), \
            f"the ledger must NAME why it could not measure: {_o['raw']!r}"

        # (c) THE ID FILTER IS NOT A CLIFF. Lighter stops echoing client ids —
        #     the tape is readable, our id is just not on it. The venue layer's
        #     id match is HARD (lighter_client.py:624-629 `continue`s, no
        #     fallback), so before this fix the read went from approximate to
        #     NOTHING: threading the id made the happy path exact and the
        #     unhappy path strictly WORSE than the heuristic it replaced, in
        #     silence. That round trip has never been proven in production — the
        #     taker's only two live orders (STRC/1000BONK, 09:08 + 09:13Z 17-Jul)
        #     predate the fill-read code by an hour, so NO venue_orders row has
        #     ever carried `measured`. This fixture is the whole reason the
        #     assumption is survivable.
        #
        #     MUTATION: drop read_fill's retry (revert to the hard filter) and
        #     px_fill collapses to the decision price -> RED.
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"NOID": 100.0}, funding={}, ranges={"NOID": 6.0})
        _scout({"divergence": [{"sym": "NOID", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"NOID": 100.5}, echo_ids=False)
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert _o["px_fill"] == 100.5, \
            (f"an id-miss must FALL BACK to the (side, since_ts) read, not "
             f"collapse to the decision price: px_fill={_o['px_fill']!r}")
        assert v.seen_client_ids == [v.last_cid, None], \
            (f"the id must be tried FIRST and dropped exactly once: "
             f"{v.seen_client_ids!r}")
        # ...and the fallback is an ESTIMATE. A blended read recorded as a
        # measurement is worse than no read at all: it is a fabrication wearing
        # a `measured: true` stamp.
        #     MUTATION: restore `return real, True, reason` in _real_fill -> RED.
        assert _o["raw"]["measured"] is False, \
            f"a fallback read is a BLEND, never a measurement: {_o['raw']!r}"
        assert "id-miss" in (_o["raw"]["fill_src"] or ""), \
            f"the ledger must NAME the degraded read: {_o['raw']!r}"
        #     MUTATION: let slip_bps_of return the bps for an unmeasured leg
        #     (the Farmer's old rule) -> RED. implementation_shortfall AVGs this
        #     column with no `measured` filter, so a blend would contaminate the
        #     live-vs-shadow execution verdict rather than just sit there.
        assert _o["slippage_bps"] is None, \
            (f"an unmeasured leg must record NULL slippage even though the "
             f"blended price differs from the decision: {_o['slippage_bps']!r}")
        # ...and the blend goes NO FURTHER THAN THE LEDGER. meta[sym]["entry"]
        # is where telemetry would become ORDER BEHAVIOUR: the stop and TP hang
        # off it, so a fallback that has never run in production would be
        # deciding when real money closes on its first ever execution. The
        # ledger row above carries the blend (px_fill=100.5, named + measured
        # False); the bot still runs its stop off the decision mark, exactly as
        # it does today when the id misses.
        #     MUTATION: `entry_px = _fill_px` (drop the `if _meas else mark`)
        #     and this is RED — that one line is the whole telemetry/behaviour
        #     boundary, and nothing else in the suite constrains it.
        _live = captured["state"][LIVE_STATE_KEY]
        assert _live["meta"]["NOID"]["entry"] == 100.0, \
            (f"an UNMEASURED fill must never reach meta['entry'] — the stop "
             f"and TP hang off it: {_live['meta']['NOID']['entry']!r} "
             f"(decision mark was 100.0, the blended read was 100.5)")
        # The measured path is the control: when the venue NAMES the fill, meta
        # takes it — that is today's behaviour and this fix must not touch it.
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"YESID": 100.0}, funding={}, ranges={"YESID": 6.0})
        _scout({"divergence": [{"sym": "YESID", "side": "short",
                                "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"YESID": 100.5})   # ids echo
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _live = captured["state"][LIVE_STATE_KEY]
        assert _live["meta"]["YESID"]["entry"] == 100.5, \
            (f"a MEASURED fill must still reach meta['entry'] — guarding the "
             f"fallback must not cost us the real fill we did measure: "
             f"{_live['meta']['YESID']['entry']!r}")

        # (d) A FAILED READ MUST NOT RETRY. `skipped:budget` / `auth-failed` /
        #     `api-error` mean the tape was never read — a second call spends the
        #     governor's telemetry reserve to fail identically, against
        #     lighter_client's explicit rule that telemetry must never make the
        #     NEXT market_open queue behind it. Only `no-match` (a readable tape
        #     our id was absent from) earns the retry.
        #
        #     MUTATION: retry on any falsy read instead of `no-match` only -> RED.
        for _bad in ("skipped:budget(2.0 tok, reserve 4)", "auth-failed:expired",
                     "api-error:trades:TimeoutError:x", "empty:both(stub)"):
            captured["state"].clear()
            captured["orders"].clear()
            _stub_market(marks={"BUD": 100.0}, funding={}, ranges={"BUD": 6.0})
            _scout({"divergence": [{"sym": "BUD", "side": "short",
                                    "gap_pct": 99.0}]})
            v = _StubVenue(equity=1000.0, fills={}, fill_reason=_bad)
            main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                       "broker": None})
            assert v.seen_client_ids == [v.last_cid], \
                (f"{_bad!r} must NOT retry — the tape was never read, so a "
                 f"second call burns budget to re-fail: {v.seen_client_ids!r}")

        # ================================================================
        # 13) THE VENUE LAYER IS AUDIBLE — and importing this file must NOT
        #     hijack anyone else's logging.
        #
        #     The live taker configured no logging, so Python dropped every
        #     `log.info` from venues/: no signer banner (hence no lighter-sdk
        #     version), no EQUITY GUARD REJECTs, no governor 429s. The funding
        #     bot could report its wheel and this bot could not — that asymmetry
        #     IS the bug. Both halves are pinned because the fix has two ways to
        #     be wrong: silent (no handler) or invasive (hijacking 4 importers).
        # ================================================================
        import logging as _lg
        import inspect as _insp

        # (0) THE CALL SITE. Testing _setup_logging() directly proves the
        #     FUNCTION works and says NOTHING about main() calling it — and a
        #     helper nobody calls is precisely the original bug. This is the
        #     THIRD time tonight that a fixture exercised a helper and missed
        #     its wiring (see _bars in funding_carry_bot, and _slip_bps_of's
        #     `measured`); mutation-proven, M14 sailed through without it.
        _main_src = "\n".join(ln.split("#", 1)[0]
                              for ln in _insp.getsource(main).splitlines())
        assert "_setup_logging(_ctx)" in _main_src, (
            "main() must CALL _setup_logging(_ctx) — without it venues' "
            "log.info is dropped and the live bot runs blind to its own "
            "signer, equity guard and governor")

        # (a) IMPORT-TIME PURITY. Four modules import this file and NONE of them
        #     configure logging; a module-level basicConfig would silently take
        #     over the root logger for all four inside the shared container.
        #     Merely importing us must therefore add no handler.
        _root = _lg.getLogger()
        _saved_handlers, _saved_level = list(_root.handlers), _root.level
        try:
            for _h in list(_root.handlers):
                _root.removeHandler(_h)
            assert not _lg.getLogger().handlers, (
                "importing lighter_ticket_taker must NOT configure the root "
                "logger — four modules import it and none configure logging")
            # _ctx (the offline path) must also leave logging alone, so these
            # very selftests never inherit a handler they did not ask for.
            _setup_logging(_ctx={"stub": True})
            assert not _lg.getLogger().handlers, \
                "_setup_logging(_ctx=...) is the TEST path — it must not configure"

            # (b) THE FIX ITSELF: the real path makes venues' log.info audible.
            _setup_logging(None)
            assert _lg.getLogger().handlers, \
                "_setup_logging() must give the root a handler, or venues' " \
                "log.info is dropped and the live bot runs blind"
            assert _lg.getLogger("venues.lighter").isEnabledFor(_lg.INFO), \
                "venues log.info must be ENABLED — that is the signer banner, " \
                "the equity-guard REJECTs and the governor 429s"
            # idempotent: a caller that already configured keeps its own setup
            _n = len(_lg.getLogger().handlers)
            _setup_logging(None)
            assert len(_lg.getLogger().handlers) == _n, \
                "basicConfig must be a no-op when the root already has handlers"
        finally:
            for _h in list(_root.handlers):
                _root.removeHandler(_h)
            for _h in _saved_handlers:
                _root.addHandler(_h)
            _root.setLevel(_saved_level)

        print("\nAll LIVE order-path self-tests passed:")
        print("  1 entry SENDS a real order + records the REAL fill")
        print("  2 notional cap is senior — cap-breaching entry never sends")
        print("  3 kill switch flattens the VENUE's book + halts")
        print("  4 daily loss confirms, flattens, halts DURABLY")
        print("  5 a failed close books no phantom row and keeps the position")
        print("  6 live funding hits the ledger, not equity; equity is the venue's")
        print("  7 unreadable positions SKIP the cycle — never trade blind")
        print("  8 a failed flatten reports the open book, not a green zero")
        print("  9 the DEPLOYED shadow arm still trades, on the TRUE 8h basis")
        print(" 10 a crash marks the row ERROR instead of going quietly stale")
        print(" 11 a DIRTY account is QUARANTINED, not adopted: the stranger is\n"
              "    never managed and nothing new is opened — but our OWN positions\n"
              "    keep their stop (11a), a failed READ is not called a dirty\n"
              "    account (11b), a failed meta WRITE pages (11c), and the kill\n"
              "    switch still flattens")
        print(" 12 fill telemetry DETECTS: a measured at-mark fill records 0.0,")
        print("    an unmeasured leg records NULL and names the reason, an")
        print("    id-miss FALLS BACK (labelled, never stamped measured), and")
        print("    a read that never happened does not retry into the reserve")
        print(" 13 the venue layer is AUDIBLE (signer/equity-guard/governor),")
        print("    and importing this file hijacks nobody's logging")
    finally:
        for k, fn in _real.items():
            setattr(store, k, fn)
        globals()["fetch_marks_and_funding"] = _real_fetch
        TT_VENUE, BOT_ROW = _saved_env
        if _saved_ttv is None:
            os.environ.pop("TT_VENUE", None)
        else:
            os.environ["TT_VENUE"] = _saved_ttv


def _supervised():
    """[2026-07-17 INCIDENT] A crash used to publish NOTHING — the row simply
    went stale, which reads as a DEAD bot rather than a broken one, and the two
    look identical on the dashboard until someone greps the container.

    That is not hypothetical: the shadow arm shipped at 05:35 UTC missing its
    lighter-sdk wheel and crash-looped every 5 minutes for an hour behind a row
    still showing the OLD image's last-good `online, 1013.99, 18 closes`. Two
    commits then cited that fossil as evidence the arm was healthy.

    A run-once process has no supervisor loop to mark the row, so do it here:
    mark ERROR and re-raise. run_all.sh's `|| true` swallows the exit code, but
    the ROW now says why — the same reason SafetyRails._publish_refusal exists
    (a refused boot must not look like a dead one). Status-only: the last good
    equity/P&L stays intact.
    """
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise                      # boot refusals (incl. lighter_live) pass through
    except Exception:              # noqa: BLE001
        try:
            store.set_status(BOT_ROW, "error")
        except Exception:          # noqa: BLE001 — never mask the real failure
            pass
        raise


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--selftest-live" in sys.argv:
        _selftest_live()
    else:
        _supervised()
