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
  exactly what this book collects. There is NO live path at all: pure paper
  on public keyless data. Run-once process; run_all.sh loops it every 5 min.
  Broker state + entry metadata persist in bot_state so redeploys continue
  the same equity curve.

Usage:
    python3 lighter_ticket_taker.py            # one management cycle
    python3 lighter_ticket_taker.py --selftest # offline accounting checks
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import bot_pnl_store as store
from paper_broker import PaperBroker

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
#                  lens with forward evidence and it has n=6 (~2 fills of
#                  swing) against a 30-day gate. The path exists so the switch
#                  is one env var WHEN the evidence lands; it is not a promise
#                  that it has.
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
    moved (for the log). Defaults untouched when no lever is live."""
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


def main():
    moved = apply_tuning()
    if moved:
        print(f"[ticket-taker] {iso(now())} growth-rail levers active: {moved}")
    try:
        marks, funding, ranges = fetch_marks_and_funding()
    except Exception as e:  # noqa: BLE001 — keyless API down: skip this cycle
        print(f"[ticket-taker] {iso(now())} fetch failed (skipping): {e!r}")
        return

    if TT_VENUE not in TT_MODES:
        raise SystemExit(f"TT_VENUE={TT_VENUE!r} unknown (expected {TT_MODES})")
    # [2026-07-17 LIVE REFUSED — the path is built, the evidence is not.]
    # Of the four lenses the brain grades, THREE are vetoed negative at
    # n=1263-2470 (dip -0.424%/hit .41, breakout -0.211%/.40, momentum
    # -0.377%/.39). Only divergence is positive (n=2820, +0.164%, hit .571) —
    # and it has SIX closes, ~2 fills of swing, against a fleet gate of 30-day
    # WR>55% AND maxDD<15%. Going live on that is the Trail Blazer mistake
    # exactly (live on ~2d of shadow; retired as "a lucky ~30d window").
    # This refusal is what makes the live path safe to BUILD before it is
    # earned. Lift it when divergence has the closes — not to fill a vacancy.
    if TT_VENUE == "lighter_live":
        raise SystemExit(
            "lighter-ticket-taker REFUSES lighter_live: divergence is the only "
            "fillable lens (the brain vetoes the other three) and it has n=6 "
            "closes — the fleet's gate is a 30-day record. The live path is "
            "wired and shadow-verified; it needs EVIDENCE, not permission. "
            "See the block above.")

    saved = store.load_state(STATE_KEY) or {}
    venue = None
    rails = None
    live = (TT_VENUE == "lighter_live")
    if TT_VENUE == "lighter_paper":
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
        # [2026-07-17] Signer wiring is READY for live (with_signer=live) and
        # SafetyRails is constructed from the real mode, so a live boot demands
        # an explicit LIGHTER_TICKET_TAKER_MAX_NOTIONAL or refuses. But the
        # ORDER PATH ITSELF IS NOT BUILT: every call site below assumes a local
        # broker (broker.pos / .open / .close / .equity / .fees), and live needs
        # positions read from the VENUE, market_open/market_close, last_fill
        # reconciliation, an equity guard and a daily-loss rail. Until that
        # exists, live must construct NOTHING — a None broker would AttributeError
        # its way through the loop, which is a trap dressed as a fail-safe.
        # The refusal above is what makes this honest; do not lift it to "see
        # what happens".
        venue = LighterClient(net="mainnet", with_signer=live)
        rails = SafetyRails(BOT, TT_VENUE)
        rails.assert_can_start()
        broker = ShadowBroker(BOT_ROW, venue, START_EQUITY)
    broker.restore_state(saved.get("broker") or {})
    meta = saved.get("meta") or {}          # sym -> {lens, opened, accrued_to}
    stats = saved.get("stats") or {"closed": 0, "wins": 0, "losses": 0}
    t_now = now()

    # 1) mark + hourly funding drag on held positions (longs pay positive rate)
    for sym in list(broker.pos):
        mark = marks.get(sym)
        if mark:
            broker.mark(sym, mark)
        m = meta.get(sym) or {}
        try:
            last = parse_ts(m.get("accrued_to") or m.get("opened"))
            hours = max(0.0, (t_now - last).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            hours = 0.0
        rate = funding.get(sym)
        if hours > 0 and rate and mark:
            size, _entry = broker.pos[sym]
            # SIGNED accrual: a long pays a positive rate (drag > 0), a short
            # RECEIVES it (drag < 0 = credit) — the divergence lens's whole
            # thesis is collecting that credit.
            drag = size * mark * rate * hours
            broker.fees += drag
            m["funding_paid"] = round(float(m.get("funding_paid") or 0.0) + drag, 6)
            m["accrued_to"] = iso(t_now)
            meta[sym] = m

    # 2) exits
    for sym in list(broker.pos):
        mark = marks.get(sym)
        m = meta.get(sym) or {}
        try:
            opened = parse_ts(m.get("opened"))
        except (ValueError, TypeError):
            opened = t_now
        size, entry = broker.pos[sym]
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
        pnl = broker.close(sym, mark)
        drag = float(m.get("funding_paid") or 0.0)   # signed: shorts credit
        clip_used = float(m.get("clip") or CLIP_USD)
        # ShadowBroker's cost is the CROSSED SPREAD, already inside the fill
        # price (fee_bps=0 — Lighter charges no perp fee). Charging a flat fee
        # on top would double-count it; the legacy paper arm still models one.
        fees = 2 * clip_used * broker.fee
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
            # [2026-07-15 AUDIT FIX] provenance: shadow-only book on Lighter
            # marks — venue NULL claimed the pre-Gate-0 HL-paper era.
            venue="lighter", shadow=(TT_VENUE != "lighter_live"))
        print(f"[ticket-taker] {iso(t_now)} CLOSE {side} {sym} ({lens}) {reason} "
              f"pnl {pnl:+.2f} funding {-drag:+.3f} net {net:+.2f}")
        meta.pop(sym, None)

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
    if fresh and not stressed:
        for lens, t in incredible(scout.get("tickets") or {}):
            sym = t.get("sym")
            if lens in lens_vetoed:
                continue          # brain graded this lens negative at n>=min_n
            # one NEW position per lens per cycle; never add to a held symbol
            if (not sym or sym in broker.pos or sym in opened_syms
                    or lens in opened_lenses):
                continue
            if broker.open_count() >= MAX_OPEN:
                break
            mark = marks.get(sym)
            if not mark:
                continue
            is_long = t.get("side", "long") != "short"
            if is_long and long_budget_full:
                continue          # L2 veto: fleet long budget is full
            clip = round(vol_clip(ranges.get(sym)) * gov, 2)
            broker.open(sym, is_long, clip / mark, mark)
            meta[sym] = {"lens": lens, "opened": iso(t_now), "clip": clip,
                         "accrued_to": iso(t_now), "funding_paid": 0.0,
                         "evidence": {k: t.get(k) for k in
                                      ("range_pos", "chg_pct", "vol_m",
                                       "prem_bps", "apr_pct", "gap_pct")}}
            opened_syms.add(sym)
            opened_lenses.add(lens)
            print(f"[ticket-taker] {iso(t_now)} OPEN "
                  f"{'long' if is_long else 'SHORT'} {sym} ({lens}) "
                  f"${clip} @ {mark} (range {round(ranges.get(sym) or 0, 1)}%) "
                  f"evidence={meta[sym]['evidence']}")

    # 4) persist + publish
    equity = broker.equity()
    store.save_state(STATE_KEY, {"broker": broker.to_state(), "meta": meta,
                                 "stats": stats})
    store.publish(
        BOT_ROW, status="online",
        equity=round(equity, 2),
        pnl_abs=round(equity - START_EQUITY, 2),
        pnl_pct=round(equity / START_EQUITY - 1.0, 6),
        open_trades=broker.open_count(),
        closed_trades=stats["closed"], wins=stats["wins"], losses=stats["losses"],
        extra={"venue": "lighter_shadow", "strategy": "scout tickets (shadow)",
               "open_pos": [{"pair": f"{s}/USDC",
                             "tag": (("long-" if broker.pos[s][0] > 0 else "short-")
                                     + (meta.get(s) or {}).get("lens", "ticket"))}
                            for s in broker.pos],
               "scout_fresh": fresh, "stress_veto": stressed,
               # the bars actually in force this cycle (growth-rail visible)
               "bars": {lever: globals()[attr] for lever, attr in TUNABLE},
               "tuned": sorted(moved)})
    print(f"[ticket-taker] {iso(t_now)} equity {equity:+.2f} "
          f"open {broker.open_count()}/{MAX_OPEN} closed {stats['closed']} "
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

    # [2026-07-16 ZOMBIE GUARD] delist give-up clock
    _t = now()
    assert delist_due(iso(_t - timedelta(hours=DELIST_GIVEUP_H + 1)), _t) is True
    assert delist_due(iso(_t - timedelta(hours=1)), _t) is False
    assert delist_due("garbage", _t) is False and delist_due(None, _t) is False
    print("All Ticket Taker self-tests passed (bars incl. divergence, "
          "long/short exits, signed funding, constant-risk sizing, "
          "delist give-up).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
