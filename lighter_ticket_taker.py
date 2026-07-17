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
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import bot_pnl_store as store
import funding_basis
from paper_broker import PaperBroker
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
# [2026-07-17 DONE — that service exists: Dockerfile.takerlive +
# railway.takerlive.toml, and the mandatory guard is now in main(). The module
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
MOMO_VOL_M = float(os.environ.get("TT_MOMO_VOL_M", "2.0")) # >= $2M/day
# [2026-07-14b] Divergence lens: receive Lighter's funding when it diverges
# this hard (percentage points of APR) from the cross-venue median.
# [2026-07-17] /8 with the fleet basis fix — same decision, true units.
DIV_GAP_PP = float(os.environ.get("TT_DIV_GAP", "62.5"))
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
           ("taker.max_hold_h", "MAX_HOLD_H"))


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


def vetoed_lenses(lens_fwd, min_n=None):
    """THE lens veto rule, and the single authority for it (2026-07-17): a
    lens the brain grades negative at sample size stops getting fills.

    Extracted from this module's own loop so the rule has ONE definition. It
    had two — the loop below and lighter_scout_tuner.vetoed_lenses — and a
    third was about to appear in strategy_incubator, which breeds the very
    bars this veto decides are worthless. Consumers must not drift on the
    question "is this lens allowed to trade?".

    RESTRICT-ONLY and fail-safe open: an empty/missing grade set vetoes
    nothing (freshness is the CALLER's job — see the loop and the tuner)."""
    if min_n is None:
        min_n = int(os.environ.get("TT_LENS_VETO_MIN_N", "75"))
    out = set()
    for lens, o in (lens_fwd or {}).items():
        if ((o.get("n4h") or 0) >= min_n
                and (o.get("avg4h_pct") or 0) < 0
                and (o.get("hit4h") or 0) < 0.5):
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
        if abs(t.get("gap_pct") or 0) >= DIV_GAP_PP:
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


def exit_reason(entry, mark, opened, t_now, is_long=True):
    """tp / sl / hold / None for a position held from `opened`."""
    if not entry or entry <= 0 or not mark or mark <= 0:
        return None
    ret = (mark / entry - 1.0) * (1.0 if is_long else -1.0)
    if ret >= TAKE_PROFIT:
        return "tp"
    if ret <= STOP_LOSS:
        return "sl"
    if (t_now - opened).total_seconds() >= MAX_HOLD_H * 3600:
        return "hold"
    return None


# ---------------------------------------------------------------------------


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
            guard_state_key=(BOT_ROW + ":eqguard") if live else None)
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
        saved = store.load_state(LIVE_STATE_KEY) or {}
        live_baseline = saved.get("initial_equity")
    meta = saved.get("meta") or {}          # sym -> {lens, opened, accrued_to}
    stats = saved.get("stats") or {"closed": 0, "wins": 0, "losses": 0}
    # ShadowBroker's cost is the CROSSED SPREAD, already inside the fill price
    # (fee_bps=0 — Lighter charges no perp fee). Charging a flat fee on top
    # would double-count it; the legacy paper arm still models one. LIVE pays
    # the venue's real fee (zero) and its spread is inside the real fill, so
    # its modelled fee is zero for the same reason the shadow arm's is.
    fee_rate = broker.fee if dry_run else 0.0

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

    def _real_fill(sym, is_ask, fallback, leg):
        """REAL fill price from the venue's own trade tape, or the decision
        price. is_ask=True when WE sold (opening a SHORT / closing a LONG).

        Extends lighter_funding_bot._real_exit to the OPEN leg too: that bot
        echoes the decision price on opens, which is the same unmeasurable-fill
        shape its own 17-Jul telemetry fix called out on closes. Entries here
        are rare (<=4/cycle), so the extra governed read is cheap and it makes
        this arm's execution measurable on BOTH legs — which is the entire
        reason a live arm exists before a go-live.

        Measurement-only: ANY failure falls back to the decision price, so a
        broken read can never block or unwind an order."""
        if dry_run:
            return fallback
        try:
            fl = getattr(venue, "last_fill", None)
            real = fl(sym, is_ask=is_ask, since_ts=time.time() - 180) if fl else None
        except Exception:  # noqa: BLE001 — never let telemetry break an order
            real = None
        if real:
            print(f"[ticket-taker] {sym} {leg} fill (venue): {real:.6g} "
                  f"(decision {fallback:.6g})")
        return real or fallback

    def _slip_bps_of(decision, fill, is_buy):
        """Signed slippage on ONE order, bps, POSITIVE = worse than the
        decision price. None when the two are identical, because a fallback to
        the decision price means we got NO fill read — recording that as 0.0
        would be indistinguishable from a genuinely perfect fill. The fleet's
        whole execution blind spot came from an echoed decision price being
        read as data; a null is honest, a fabricated zero is not."""
        try:
            d, f = float(decision), float(fill)
            if d <= 0 or f <= 0 or d == f:
                return None
            return (f / d - 1.0) * 10_000.0 * (1.0 if is_buy else -1.0)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def _book_close(sym, m, size, entry, exit_px, pnl, reason, decision_px=None):
        """Ledger + counters + meta pop for ONE close. Shared by the exit pass
        and _flatten_all so an emergency flatten reconstructs identically to a
        normal close (the funding bot's rule: forensics must stay consistent
        with account equity)."""
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
            venue="lighter", shadow=dry_run)
        if not dry_run:
            try:
                store.publish_venue_order(
                    BOT_ROW, venue="lighter", shadow=False, coin=sym,
                    side=("sell" if is_long else "buy"), size=abs(size),
                    px_decision=decision_px, px_fill=exit_px,
                    slippage_bps=_slip_bps_of(decision_px, exit_px,
                                              is_buy=not is_long),
                    raw={"reason": reason, "lens": lens, "leg": "close"})
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
                if venue.market_close(_fleet(sym)) is None:
                    print(f"[ticket-taker] {iso(t_now)} flatten {sym}: venue "
                          f"reported NO position to close — leaving meta intact "
                          f"and retrying next cycle (NOT booking a close)")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[ticket-taker] {iso(t_now)} flatten {sym}: {e!r}")
                continue
            _dpx = px
            px = _real_fill(sym, is_ask=is_long, fallback=px, leg="exit")
            pnl = abs(size) * ((px - entry) if is_long else (entry - px))
            _book_close(sym, m, size, entry, px, pnl, reason, decision_px=_dpx)

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
                pnl_abs=((equity - live_baseline)
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
    if live:
        _foreign = sorted(s for s in pos if s not in meta)
        if _foreign:
            store.set_status(BOT_ROW, "error")
            raise SystemExit(
                f"lighter-ticket-taker REFUSES to trade a DIRTY ACCOUNT: the "
                f"venue reports {_foreign} with no meta of ours. This bot did "
                f"not open {'them' if len(_foreign) > 1 else 'it'} and will not "
                f"adopt {'them' if len(_foreign) > 1 else 'it'} — it has no "
                f"entry clip, lens or opened-time, so its exit ladder would "
                f"manage another strategy's position on the taker's bars. If "
                f"this is Tide Rider's leftover on the handed-over sub-account, "
                f"flatten it FIRST (operator, by hand or via REAL_MONEY_KILL). "
                f"If it is ours with lost state, reconcile "
                f"bot_state['{LIVE_STATE_KEY}'].meta before restarting.")

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
            reason = exit_reason(entry, mark, opened, t_now, is_long)
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
        else:
            try:
                # [2026-07-17] This block's own comment already said "never book
                # a close that did not happen" — but it only caught EXCEPTIONS,
                # and the stranding case does NOT raise: market_close() returns
                # None when it finds no position under that key
                # (venues/lighter_client.py:558-560). That is precisely the
                # symbol-space failure, so the guard missed the case it was
                # written for. None is a FAILED close.
                if venue.market_close(_fleet(sym)) is None:
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
            mark = _real_fill(sym, is_ask=is_long, fallback=mark, leg="exit")
            pnl = abs(size) * ((mark - entry) if is_long else (entry - mark))
        _book_close(sym, m, size, entry, mark, pnl, reason, decision_px=_dpx)
        pos.pop(sym, None)

    # 3) entries — only from a FRESH scout snapshot, only the incredible subset
    scout = store.load_state(SCOUT_KEY) or {}
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
    if gov < 1.0:
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
            # one NEW position per lens per cycle; never add to a held symbol
            if (not sym or sym in pos or sym in opened_syms
                    or lens in opened_lenses):
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
                    venue.market_open(_fleet(sym), is_long, size)
                except Exception as e:  # noqa: BLE001
                    print(f"[ticket-taker] {iso(t_now)} open {sym} failed: {e!r}")
                    continue
                entry_px = _real_fill(sym, is_ask=not is_long, fallback=mark,
                                      leg="entry")
                try:
                    store.publish_venue_order(
                        BOT_ROW, venue="lighter", shadow=False, coin=sym,
                        side=("buy" if is_long else "sell"), size=size,
                        px_decision=mark, px_fill=entry_px,
                        slippage_bps=_slip_bps_of(mark, entry_px, is_buy=is_long),
                        raw={"lens": lens, "leg": "open", "clip": clip,
                             "evidence": ev})
                except Exception:  # noqa: BLE001
                    pass
            # visible to the rest of THIS cycle: the cap check above and the
            # MAX_OPEN slot count must both see what we just opened.
            pos[sym] = {"size": size if is_long else -size, "entry": entry_px}
            meta[sym] = {"lens": lens, "opened": iso(t_now), "clip": clip,
                         "entry": entry_px,
                         "accrued_to": iso(t_now), "funding_paid": 0.0,
                         "evidence": ev}
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
                                     "stats": stats})
    else:
        # re-read AFTER trading: the loop-top print fed the rails, this one is
        # what the row reports. A failed re-read keeps the loop-top value
        # rather than publishing a hole.
        try:
            equity = account_value()
        except Exception:  # noqa: BLE001
            pass
        if live_baseline is None and equity is not None:
            live_baseline = equity
        pnl_abs = ((equity - live_baseline)
                   if (equity is not None and live_baseline is not None) else None)
        pnl_pct = ((pnl_abs / live_baseline)
                   if (pnl_abs is not None and live_baseline) else None)
        store.save_state(LIVE_STATE_KEY, {
            "initial_equity": live_baseline, "meta": meta, "stats": stats,
            "day_start": {"day": cur_day, "equity": day_start_equity}})
    store.publish(
        BOT_ROW, status="online",
        equity=(round(equity, 2) if equity is not None else None),
        pnl_abs=(round(pnl_abs, 2) if pnl_abs is not None else None),
        pnl_pct=(round(pnl_pct, 6) if pnl_pct is not None else None),
        open_trades=len(pos),
        closed_trades=stats["closed"], wins=stats["wins"], losses=stats["losses"],
        extra={"venue": TT_VENUE,
               "strategy": f"scout tickets ({'live' if live else 'shadow'})",
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
    market_close / last_fill."""

    def __init__(self, equity=1000.0, pos=None, fills=None):
        self._equity = equity
        self._pos = dict(pos or {})
        self._fills = dict(fills or {})     # sym -> fill px returned by last_fill
        self.opens, self.closes, self.value_reads = [], [], 0
        self.fail_close = set()

    def account_value(self):
        self.value_reads += 1
        return self._equity

    def positions(self):
        return {s: dict(v) for s, v in self._pos.items() if v.get("size")}

    def market_open(self, coin, is_long, size):
        self.opens.append((coin, is_long, size))
        self._pos[coin] = {"size": size if is_long else -size,
                           "entry": self._fills.get(coin, 100.0)}
        return {"tx": "stub"}

    def market_close(self, coin):
        if coin in self.fail_close:
            raise RuntimeError(f"stub: close {coin} refused")
        self.closes.append(coin)
        self._pos.pop(coin, None)
        return {"tx": "stub"}

    def last_fill(self, coin, is_ask, since_ts, lookback=10):
        return self._fills.get(coin)


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
              "load_state", "publish", "save_daily_halt", "load_daily_halt",
              "heartbeat")}
    store.heartbeat = lambda bot: None
    store.publish_paper_trade = lambda bot, **kw: captured["paper"].append((bot, kw))
    store.publish_venue_order = lambda bot, **kw: captured["orders"].append((bot, kw))
    store.save_state = lambda k, v: captured["state"].__setitem__(k, v)
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
        assert abs(_pub["pnl_abs"] - 234.56) < 1e-9, _pub["pnl_abs"]

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
            try:
                main(_ctx={"venue": v, "rails": r, "broker": None})
                raise AssertionError("a dirty account must REFUSE")
            except SystemExit as e:
                assert "DIRTY ACCOUNT" in str(e) and "TRX" in str(e), str(e)
            assert v.closes == [], f"must not manage a foreign position: {v.closes}"
            assert v.opens == [], f"must not trade on a dirty account: {v.opens}"
            assert captured["paper"] == [], "must not book a foreign close"
            assert _status == [(BOT_ROW, "error")], \
                f"a dirty account must mark the row: {_status}"

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
        print(" 11 a DIRTY account (Tide Rider's TRX) HALTS; kill switch still flattens")
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
