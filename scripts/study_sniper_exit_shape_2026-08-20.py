#!/usr/bin/env python3
"""study_sniper_exit_shape_2026-08-20.py — WHAT WOULD A DIFFERENT EXIT HAVE
EARNED ON 🎯 THE PERP SNIPER'S OWN ENTRIES, ON LIGHTER'S OWN TAPE?

THE QUESTION, and why it needed a new instrument
------------------------------------------------
The operator's ask ("restore what made the Launch Sniper earn") reduces to one
counterfactual: the predecessor's money came from a SCALE-OUT LADDER + a wide
TRAIL on a coin that ran 5x (ANSEM: +$325 of a +$206 lifetime book). The living
Lighter book has ONE scalar exit (tp +15% / sl -10% / 6h), 32 of 33 closes are
`max_hold`, and its exit constants are BARE MODULE LITERALS no lever can reach
(`scripts/study_exit_sweep.HARDCODED_EXITS` already declares it for that
reason). So: hold the ENTRIES constant and vary only the EXIT.

`scripts/study_exit_sweep.py` is the fleet's exit counterfactual and is REUSED
where it fits — its `market_ids`, its LAG-1 doctrine, its calibration-gate
shape and its grid-edge rule all live on here. It does NOT fit as-is for three
measured reasons, which is the whole justification for a second file:

  1. RESOLUTION. It walks HOURLY bars. This book's entire life is a 6h hold
     with a +15%/-10% bracket — six bars. An hourly walk cannot resolve the
     order of a tp and an sl inside one bar of a 6-bar trade. This harness
     walks 1-MINUTE bars for the realised arm, and MEASURES what the hourly
     bar would have cost (`--resolution-calib`).
  2. EXIT SEMANTICS. `walk_exit` fires on an intrabar HIGH/LOW touch, i.e.
     resting-order semantics. This bot has no resting orders: it polls the
     ORDERBOOK MID once per `LOOP_SECONDS=60` and then MARKET-closes
     (`lighter_perp_sniper.py`, the manage-open-snipes block). A wick that
     spikes through +15% between two polls does NOT pay this book. The default
     basis here is therefore POLL (evaluate on 1m closes); `touch` is
     available as the optimistic envelope and is never the default.
  3. EXIT SHAPE. It expresses tp/sl/hold/trail. It cannot express a PARTIAL
     SCALE-OUT, which is the entire hypothesis under test — and the shadow
     broker cannot either (`ShadowBroker.close(coin, price)` takes no size and
     pops the whole position), so the ladder is not merely unlevered, it is
     structurally inexpressible in the live bot today. This harness models it
     so the question can be ANSWERED before anyone changes a broker interface.

WHAT THIS FILE IS NOT
---------------------
It is not a recommender. It emits per-cell numbers and refusals. Every doctrine
bar below is a REFUSAL mechanism, not a caveat:

  * CALIBRATION GATE (gx) — `calibrate()` replays the SHIPPED rule against the
    book's own 33 closes and compares to the ledger's own mean %/trade. Outside
    `CALIB_TOL_PP` the sweep returns `{"refused": ...}` and NO cell results are
    scored as recommendations. A harness that cannot reproduce what DID happen
    may not say what WOULD have. It REFUSES; it does not caveat.
  * LAG-1 (ne)/(ml) — the entry bar's range is never credited. Ledger entries
    are mid-bar, so their entry bar is skipped ENTIRELY (conservative: OHLC
    cannot order a bar's extremes around an intra-bar timestamp). Synthetic
    entries fill at the OPEN of the bar AFTER the signal bar, so their own bar
    is legitimately available from that open forward.
  * I19 — every widening is priced in expectancy. The CONTROL families (d)
    time-only and (e) hold-to-horizon are MANDATORY and always scored, because
    (hl) killed 25 of 30 throughput candidates when a content-free time stop
    reproduced 78% of the claimed gain. A candidate that does not beat the
    content-free timer has bought turnover, not edge.
  * (po)/I17 — CONCENTRATION (top-1 / top-3 share of total) is reported on
    every cell and flagged. The hypothesis under test IS a tail hypothesis, so
    a cell that wins only through one trade must be visible, never averaged.
  * (hm) — a directional book is graded against a RANDOM-ENTRY benchmark, not
    against zero. `--null N` runs matched-random entries (same coins, same
    span, same rule) through the identical walker.
  * GRID EDGE — a winner pinned at a searched boundary is reported UNBOUNDED.
  * I15 — win rate is REPORTED, never a bar.
  * FRICTION IS CHARGED. Lighter is zero-FEE (verified below) but not
    zero-COST: `(qq)` re-derived execution cost from the fleet's OWN 3,015
    `venue_orders` at a MEAN 17.49 bps below $0.1M turnover (p90 398) versus
    2.52 bps in the $0.1M-$1M band. Young/surge books are exactly the thin
    ones. Slippage is charged per LEG, tiered on the coin's own quote volume
    ON THE ENTRY DAY (point-in-time, from daily candles' `V` field).

TWO ENTRY SETS, REPORTED SEPARATELY, NEVER BLENDED (I14)
--------------------------------------------------------
  REALISED  — the book's own 33 closes. THE RECORD. Calibratable. n=33.
  SYNTHETIC — surge/young events reconstructed from the venue's own history to
              escape n=33. NON-ARMING BY CONSTRUCTION: no realised record
              exists for an entry that was never taken, so the (gx) gate has
              nothing to calibrate against. What it CAN carry is a RESOLUTION
              calibration (the same shipped rule replayed at 1h vs 1m on the
              realised entries), which bounds what the coarser bar costs. The
              script prints that bound beside every synthetic number and marks
              the whole arm NON-ARMING.

VERDICT OF THE FIRST RUN — 2026-08-20. RE-RUN IT; DO NOT RE-ARGUE IT FROM
PROSE. **THE HARNESS CANNOT CALIBRATE AGAINST THIS BOOK, AND THE REASON IS
IRREDUCIBLE FROM THE VENUE'S PUBLIC CANDLES.**

  * Replayed SHIPPED rule **+0.230%/trade** vs the ledger's own matched mean
    **-0.104%/trade** -> gap **+0.334pp**, against a 0.15pp tolerance. FAIL.
    (The price arm PASSES: 30 of 32 rows recover the recorded exit price
    within 100bps. A mean can be wrong while every price is right, which is
    exactly why there are two arms.)
  * The error is NOT a friction constant. Per-row gap: **median +0.004pp**,
    **mean +0.334pp**, min **-0.126**, max **+1.645**, 6 of 32 rows off by
    >1pp, and **94% of the total error MASS is optimistic** while only 50% of
    rows are optimistic BY COUNT — the count reads perfectly balanced and the
    mass does not, which is why the one-sidedness metric here is by mass. 18
    of 32 rows reproduce to within a tenth of a point; 6 do not reproduce at
    all.
  * A BASIS SCAN of every convention this tape can express — {poll, touch} x
    {mean, p90, zero} slippage — calibrates in **0 of 6** cells (best gap
    +0.181pp). So the refusal is exhaustive, not assumed.
  * WHY, diagnosed rather than guessed, on the two worst rows. NZDUSD: the
    ledger's exit MID sits 65bps below the 1m trade print (the print is stale;
    the book moved and nothing traded) and the crossed fill a further 97bps
    below that. MRNA: fully liquid, prints every minute, and the bot's mid at
    its poll instant was 1.3% below that same minute's close — sub-minute poll
    PHASE. Both are one statement: **the bot decides on the 60s-polled
    ORDERBOOK MID, and the candle API does not carry that quantity at any
    resolution it offers.** A live-orderbook spread model was tested as a fix
    and REFUTED: corr(today's half-spread, per-row gap) = **0.26** (WHEAT
    152bps spread / +1.17pp gap vs BOTZ 101bps / -0.13pp).
  * CONSEQUENCE, stated so no downstream agent misreads it: **every cell this
    file can produce is NON-ARMING.** The sweep REFUSES by default;
    `--diagnostic-sweep` prints cells only as EXCESS OVER THE SHIPPED RULE
    against a published BIAS ENVELOPE of 0.334pp/trade — which is **3.2x the
    entire magnitude of the book's own mean**. Nothing here may arm a change.
  * THE ONE THING THAT SURVIVES ANYWAY, because it needs no calibration: the
    (hm) null. The shipped rule's replayed mean has **P(random >= observed) =
    0.475** over 300 matched-random draws through the identical walker. A
    coin flip reproduces this book's exit performance, and that verdict is
    invariant to the bias because the null is drawn through the same biased
    harness.
  * DO NOT "FIX" THIS BY WIDENING `SNIPER_CALIB_TOL_PP`. The gap is 2.2x the
    tolerance and one-sided; a tolerance that admits it admits an instrument
    that inflates every candidate it ranks. A gate that cannot be passed at
    the available resolution is a RESULT.

Usage:
    python3 scripts/study_sniper_exit_shape_2026-08-20.py --selftest
    python3 scripts/study_sniper_exit_shape_2026-08-20.py --calibrate-only
    python3 scripts/study_sniper_exit_shape_2026-08-20.py --families all
    python3 scripts/study_sniper_exit_shape_2026-08-20.py --families ladder \
        --null 300 --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
BOOK = "lighter-perp-sniper-lshadow"
DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")
PAPER_START = 1000.0
CLIP_USD = 20.0          # ctx.order_usd(20.0) — the book's own clip

CACHE_DIR = os.environ.get("STUDY_CACHE_DIR", tempfile.gettempdir())
CACHE = os.path.join(CACHE_DIR, "sniper_exit_shape_2026-08-20.json")

# ---------------------------------------------------------------------------
# FRICTION. Lighter's fee is ZERO and that is MEASURED, not assumed — every
# active book on /api/v1/orderBookDetails reports taker_fee 0.0000 / maker_fee
# 0.0000, and `--verify-fees` re-checks it against the live venue rather than
# trusting this comment (I12: a doctrine that no longer describes the system is
# a defect). Zero fee is NOT zero cost: the shadow book's real cost is the
# crossed spread, which lands inside the fill price.
#
# TIERS — declared, and sourced rather than invented. `(qq)` re-derived
# execution cost from the fleet's OWN 3,015 venue_orders and corrected an
# inherited flat constant in BOTH directions: the tradeable $0.1M-$1M band
# measures a true MEAN 2.52 bps, while the sub-$0.1M dust measures MEAN 17.49
# bps / p90 398 bps ("the dust is not a surface, it is a trap").
#   * (qq) published no separate >=$1M number, so the >=$1M band INHERITS 2.52
#     rather than getting an invented smaller one. That OVER-charges the liquid
#     band, which is the safe direction for a study hunting an edge.
#   * `--slip p90` charges 398 bps in the dust band — the stress reading, not
#     the headline. `--slip zero` exists only to SIZE the friction term and is
#     refused as a basis for any conclusion (it prints a banner saying so).
SLIP_TIERS_MEAN = ((0.1e6, 17.49), (float("inf"), 2.52))
SLIP_TIERS_P90 = ((0.1e6, 398.0), (float("inf"), 2.52))
SLIP_TIERS_ZERO = ((float("inf"), 0.0),)

#: How far the replayed SHIPPED rule may sit from the book's ACTUAL ledger mean
#: before this study refuses to emit ANY candidate. Percentage points per
#: trade. Set against the thing being measured: the whole per-trade dispersion
#: of this book is ~0.74pp SE on a -0.092%/trade mean, so a tolerance wider
#: than ~0.15pp would admit a harness that disagrees with reality by more than
#: the effect any candidate could plausibly show. DO NOT WIDEN THIS TO PASS.
CALIB_TOL_PP = float(os.environ.get("SNIPER_CALIB_TOL_PP", "0.15"))

#: Independent second calibration arm: can the harness recover the ledger's own
#: recorded exit PRICE from the same tape, per row? Bps.
CALIB_PX_TOL_BPS = float(os.environ.get("SNIPER_CALIB_PX_TOL_BPS", "100"))
#: Fraction of rows that must clear the price arm for the arm to pass.
CALIB_PX_MIN_FRAC = float(os.environ.get("SNIPER_CALIB_PX_MIN_FRAC", "0.80"))


# ============================================================ venue plumbing
def _get(path, tries=4, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                  # noqa: BLE001
            if a == tries - 1:
                print(f"  fetch failed {path}: {type(e).__name__}: {e}",
                      file=sys.stderr)
                return None
            time.sleep(1.2 * (a + 1))
    return None


def order_book_details():
    return (_get("/api/v1/orderBookDetails") or {}).get("order_book_details") or []


def market_ids(rows=None):
    """{symbol: market_id}. Same read `study_exit_sweep.market_ids` uses."""
    rows = order_book_details() if rows is None else rows
    return {str(r.get("symbol")): r.get("market_id") for r in rows
            if r.get("symbol") is not None and r.get("market_id") is not None}


def verify_zero_fee(rows=None):
    """MEASURE the venue fee rather than asserting it (the (gg) lesson: a
    hardcoded fee constant corrupted every brain diagnosis for weeks).
    Returns (all_zero, max_taker, max_maker, n_active)."""
    rows = order_book_details() if rows is None else rows
    tk = mk = 0.0
    n = 0
    for r in rows:
        if str(r.get("status") or "").lower() not in ("active", ""):
            continue
        n += 1
        try:
            tk = max(tk, float(r.get("taker_fee") or 0.0))
            mk = max(mk, float(r.get("maker_fee") or 0.0))
        except (TypeError, ValueError):
            continue
    return (tk == 0.0 and mk == 0.0), tk, mk, n


def fetch_candles(market_id, start_ts, end_ts, resolution="1m"):
    """OHLCV over [start, end] -> {bar_ts: (o, h, l, c, quote_vol)}.

    Paged backward at the venue's 500-bar cap, the shape proven in
    `study_exit_sweep.fetch_candles` / `backtest_funding_lighter`.
    """
    step = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}[resolution]
    out, end = {}, int(end_ts)
    seen_oldest = None
    while end > start_ts:
        d = _get("/api/v1/candles", market_id=market_id, resolution=resolution,
                 start_timestamp=max(int(start_ts), end - 500 * step),
                 end_timestamp=end, count_back=500)
        cs = (d or {}).get("c") or []
        if not cs:
            break
        for c in cs:
            try:
                out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                            float(c["l"]), float(c["c"]),
                                            float(c.get("V") or 0.0))
            except (KeyError, TypeError, ValueError):
                continue
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= start_ts or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - step
        time.sleep(0.12)
    return {t: v for t, v in out.items() if start_ts <= t <= end_ts}


# ================================================================ the ledger
def fetch_ledger(book=BOOK, limit=5000, path=None):
    """The book's own closes. A LOCAL path wins when given (offline runs)."""
    if path:
        with open(path) as fh:
            d = json.load(fh)
        return d.get("trades", d) if isinstance(d, dict) else d
    url = f"{DASH}/trades.json?source=paper&limit={limit}&bot={book}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    return d.get("trades", d) if isinstance(d, dict) else d


def _iso_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def ledger_entries(rows):
    """The REALISED entry set — held constant, never fitted.

    Carries the ledger's own crossed `entry_price`, so this arm charges EXIT
    slippage only: the entry cost is already inside the recorded fill and
    charging it twice would manufacture a loss the book never paid.
    """
    out, dropped = [], []
    for r in rows:
        ts = _iso_ts(r.get("opened_at"))
        px = r.get("entry_price")
        if ts is None or not px:
            dropped.append({"pair": r.get("pair"), "why": "no entry ts/px"})
            continue
        side = r.get("side")
        out.append({
            "sym": r.get("pair"), "entry_ts": float(ts), "entry_px": float(px),
            # This book is long-only by configuration (`SNIPER_DIRECTION`
            # defaults to long) and every stamped row reads 'long'. A row with
            # no side is treated as long and COUNTED, never silently assumed —
            # (kf) is the incident where a side-less row replayed as a long and
            # inverted every short in a book that had them.
            "is_long": (side != "short"),
            "side_missing": side is None,
            "reason": r.get("reason"),
            "actual_ret": (float(r["pnl_pct"]) if r.get("pnl_pct") is not None
                           else None),
            "actual_exit_px": (float(r["exit_price"])
                               if r.get("exit_price") else None),
            "actual_exit_ts": _iso_ts(r.get("closed_at")),
            "notional": (abs(float(r["pnl_abs"]) / float(r["pnl_pct"]))
                         if r.get("pnl_pct") else CLIP_USD),
            "entry_priced": True,
        })
    return out, dropped


def ledger_mean_pct(rows):
    """The book's ACTUAL mean %/trade — the number calibration must reproduce.
    Percent, not fraction."""
    v = [float(r["pnl_pct"]) for r in rows if r.get("pnl_pct") is not None]
    return (100.0 * sum(v) / len(v)) if v else None


# ============================================================ the exit walker
#: Every exit family this harness can express. A rule is a dict; absent keys
#: are off. `walk_exit` is the ONE owner — every family, control and null runs
#: through it, so no family can accidentally be graded by a different walker.
#:
#:   tp_pct           full exit at >= entry*(1+tp)          family (a)
#:   sl_pct           full exit at <= entry*(1-sl)          family (a)
#:   max_hold_h       full exit on the clock                families (a) (d)
#:   trail_pct        gap below the high-water mark         family (b)
#:   trail_arm_pct    trail only armed once gain >= arm     family (b)
#:   trail_on_ladder  trail arms when any ladder leg fires  family (c)
#:   ladder           [(gain, frac_of_original), ...]       family (c)
#:   (nothing set)    ride to the horizon                   family (e)
#:
#: PRECEDENCE is read out of `lighter_perp_sniper.py`'s manage-open-snipes
#: block, not assumed: delisted > tp > sl > max_hold, ONE full-exit branch per
#: poll, evaluated against the 60s-polled orderbook mid. `delisted` is not
#: modelled here (it is an unpriceable-book branch, not an exit rule); the
#: three that are price/clock rules keep their shipped order, and the ladder
#: and trail are inserted where the Launch Sniper put them (hard stop first,
#: then partial, then trail, then far tp) so the two machines stay comparable.
FULL = 1.0


def walk_exit(bars, entry_ts, entry_px, is_long, rule, horizon_h,
              basis="poll", skip_entry_bar=True, bar_sec=60):
    """Replay ONE position under `rule`. -> [(ts, px, frac, why), ...].

    `bars`: {bar_ts: (o, h, l, c, qv)} sorted-able. Fractions sum to <= 1.0;
    any remainder is closed at the horizon with why='horizon'.

    LAG-1 (ne)/(ml): with `skip_entry_bar` the walk starts at the first bar
    opening STRICTLY AFTER the bar containing `entry_ts`, so a mid-bar entry
    forfeits its own bar entirely — OHLC cannot order a bar's extremes around
    an intra-bar timestamp, and crediting them is exactly how (ne) and (ml)
    each INVERTED a verdict. Synthetic entries fill at a bar OPEN and pass
    skip_entry_bar=False, which credits only prices at/after that open.

    BASIS:
      'poll'  — decide on each bar's CLOSE and exit AT that close. This is the
                bot: one orderbook-mid poll per LOOP_SECONDS=60, then a MARKET
                close. It cannot catch a wick, and it cannot fill better than
                the close it saw.
      'touch' — decide on the bar's intrabar HIGH/LOW and fill AT the level.
                Resting-order semantics this bot does not have; kept as the
                optimistic envelope. Adverse-before-favourable within a bar,
                because OHLC cannot resolve the true order.
    """
    if not bars or not entry_px or entry_px <= 0:
        return []
    sign = 1.0 if is_long else -1.0
    tp = rule.get("tp_pct")
    sl = rule.get("sl_pct")
    hold_h = rule.get("max_hold_h")
    trail = rule.get("trail_pct")
    trail_arm = rule.get("trail_arm_pct")
    trail_on_ladder = bool(rule.get("trail_on_ladder"))
    ladder = list(rule.get("ladder") or [])

    entry_bar = (int(entry_ts) // bar_sec) * bar_sec
    first = entry_bar + bar_sec if skip_entry_bar else entry_bar
    last = entry_ts + horizon_h * 3600.0

    ts_list = sorted(t for t in bars if first <= t <= last)
    if not ts_list:
        return []

    legs = []
    remaining = FULL
    peak = entry_px
    fired = [False] * len(ladder)
    armed = False
    last_px = entry_px
    for t in ts_list:
        o, h, l, c, _qv = bars[t]
        last_px = c
        held_h = max(0.0, (t - entry_ts) / 3600.0)

        # high-water mark: RATCHET ONLY, and it rides the favourable extreme
        # even on the poll basis (the peak is an observation, not a fill).
        peak = max(peak, h) if is_long else min(peak, l)
        peak_gain = sign * (peak - entry_px) / entry_px
        if trail and not armed:
            if trail_arm is None and not trail_on_ladder:
                armed = True
            elif trail_arm is not None and peak_gain >= trail_arm:
                armed = True

        if basis == "touch":
            fav, adv = h if is_long else l, l if is_long else h
        else:
            fav = adv = c
        fav_gain = sign * (fav - entry_px) / entry_px
        adv_gain = sign * (adv - entry_px) / entry_px

        # ---- 1. hard stop (adverse first, always) -------------------------
        if sl is not None and adv_gain <= -sl:
            px = entry_px * (1 - sign * sl) if basis == "touch" else c
            legs.append((t, px, remaining, "sl"))
            return legs
        # ---- 2. trailing stop on the high-water mark ----------------------
        if trail and armed:
            tpx = peak * (1 - sign * trail)
            hit = (adv <= tpx) if is_long else (adv >= tpx)
            if hit:
                px = tpx if basis == "touch" else c
                legs.append((t, px, remaining, "trail"))
                return legs
        # ---- 3. partial scale-out ladder ----------------------------------
        for i, (g, frac) in enumerate(ladder):
            if fired[i] or fav_gain < g:
                continue
            take = min(frac, remaining)
            if take <= 0:
                fired[i] = True
                continue
            px = entry_px * (1 + sign * g) if basis == "touch" else c
            legs.append((t, px, take, f"ladder{i + 1}"))
            remaining -= take
            fired[i] = True
            if trail_on_ladder:
                armed = True
            if remaining <= 1e-12:
                return legs
        # ---- 4. far take-profit ------------------------------------------
        if tp is not None and fav_gain >= tp:
            px = entry_px * (1 + sign * tp) if basis == "touch" else c
            legs.append((t, px, remaining, "tp"))
            return legs
        # ---- 5. the clock -------------------------------------------------
        if hold_h is not None and held_h >= hold_h:
            legs.append((t, c, remaining, "max_hold"))
            return legs

    if remaining > 1e-12:
        # The tape ran out. Label WHICH rule ended it: when a max_hold is set
        # and the window reached it, the CLOCK ended the trade — calling that
        # 'horizon' would report the harness's own window as the exit rule and
        # make a 24h max_hold indistinguishable from a 24h no-exit control,
        # which is exactly the (hl) control this study leans on.
        span_h = (ts_list[-1] - entry_ts) / 3600.0
        why = ("max_hold" if (hold_h is not None
                              and span_h >= hold_h - (bar_sec / 3600.0))
               else "horizon")
        legs.append((ts_list[-1], last_px, remaining, why))
    return legs


# ================================================================== friction
def slip_bps(quote_vol_usd, tiers=SLIP_TIERS_MEAN):
    """Per-side execution cost in bps, tiered on the coin's own turnover.
    An UNKNOWN volume takes the WORST tier — absence never buys a discount."""
    if quote_vol_usd is None:
        return max(b for _, b in tiers)
    for hi, bps in tiers:
        if quote_vol_usd < hi:
            return bps
    return tiers[-1][1]


# ================================================================== scoring
def _t_stat(v):
    n = len(v)
    if n < 2:
        return None
    sd = st.stdev(v)
    if sd == 0:
        return None
    return (sum(v) / n) / (sd / math.sqrt(n))


def cluster_t(v, groups):
    """CLUSTER-ROBUST t on the mean. These entries OVERLAP IN TIME (up to
    MAX_OPEN=4 concurrent), so the independence the plain t assumes is not
    available; the default cluster is the entry CALENDAR DAY. Reduces exactly
    to the plain t when every observation is its own cluster (selftest-pinned).
    """
    n = len(v)
    if n < 2 or len(set(groups)) < 2:
        return None, len(set(groups))
    mean = sum(v) / n
    sums = {}
    for x, g in zip(v, groups):
        sums[g] = sums.get(g, 0.0) + (x - mean)
    G = len(sums)
    var = sum(s * s for s in sums.values()) / (n * n) * (G / (G - 1.0))
    if var <= 0:
        return None, G
    return mean / math.sqrt(var), G


def max_drawdown_pct(pnls, start=PAPER_START):
    """Peak-to-trough of the REALISED equity curve, as % of the book. The
    go-live bar's own basis (`golive_readiness.stats`). This is realised-only
    and therefore BLIND to open drawdown (I9) — stated, not hidden."""
    eq, peak, dd = start, start, 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak if peak else 0.0)
    return 100.0 * dd


def score(closed, label=""):
    """Everything a downstream sweep is required to read before believing a
    cell: n, $, mean, t, CLUSTER t, halves, win rate (reported, never a bar —
    I15), median hold, maxDD, and CONCENTRATION."""
    n = len(closed)
    if not n:
        return {"label": label, "n": 0}
    seq = sorted(closed, key=lambda c: c["exit_ts"])
    rets = [100.0 * c["ret"] for c in seq]          # percent
    usd = [c["usd"] for c in seq]
    tot = sum(usd)
    half = n // 2
    h1 = sum(rets[:half]) / half if half else None
    h2 = sum(rets[half:]) / (n - half) if (n - half) else None
    srt = sorted(usd, reverse=True)
    top1, top3 = srt[0], sum(srt[:3])
    ct, G = cluster_t(rets, [c["cluster"] for c in seq])
    why = {}
    for c in closed:
        for w in c["why"]:
            why[w] = why.get(w, 0) + 1
    return {
        "label": label, "n": n,
        "total_usd": tot,
        "mean_pct": sum(rets) / n,
        "t": _t_stat(rets),
        "cluster_t": ct, "n_clusters": G,
        "h1_pct": h1, "h2_pct": h2,
        "both_halves_pos": (h1 is not None and h2 is not None
                            and h1 > 0 and h2 > 0),
        "win_rate": sum(1 for r in rets if r > 0) / n,     # REPORTED (I15)
        "median_hold_h": st.median([c["held_h"] for c in closed]),
        "maxdd_pct": max_drawdown_pct(usd),
        "top1_usd": top1, "top3_usd": top3,
        # (po)/I17: a share is only meaningful against a positive total. When
        # the book loses, the share is undefined and says so rather than
        # printing a sign-flipped number that reads like a small tail.
        "top1_share": (top1 / tot if tot > 0 else None),
        "top3_share": (top3 / tot if tot > 0 else None),
        "tail_flag": (tot > 0 and top1 / tot >= 0.5),
        "ex_top1_mean_pct": (sum(r for r in rets if r != max(rets)) /
                             max(1, n - 1)) if n > 1 else None,
        "skipped": 0,
        "why": why,
    }


# ================================================================== simulate
def simulate(entries, tape, rule, horizon_h, basis="poll", cap=None,
             tiers=SLIP_TIERS_MEAN, bar_sec=60, charge_entry_slip=None):
    """SEQUENTIAL portfolio replay. An entry arriving while the book is at
    `cap` is SKIPPED — which is what makes a longer hold pay for the entries it
    blocks, the denominator half of (hl). `cap` defaults to the bot's own
    MAX_OPEN so a candidate cannot buy throughput it could not have had.
    """
    order = sorted(entries, key=lambda e: e["entry_ts"])
    open_until, closed, skipped = [], [], 0
    for e in order:
        open_until = [x for x in open_until if x > e["entry_ts"]]
        if cap is not None and len(open_until) >= cap:
            skipped += 1
            continue
        bars = tape.get(e["sym"]) or {}
        legs = walk_exit(bars, e["entry_ts"], e["entry_px"], e["is_long"], rule,
                         horizon_h, basis=basis,
                         skip_entry_bar=e.get("entry_priced", True),
                         bar_sec=bar_sec)
        if not legs:
            continue
        sign = 1.0 if e["is_long"] else -1.0
        bps = slip_bps(e.get("qvol"), tiers)
        # An entry carrying the ledger's OWN crossed fill has already paid the
        # entry crossing; charging it again invents a cost the book never bore.
        ent_slip = (bps / 1e4) if (charge_entry_slip
                                   if charge_entry_slip is not None
                                   else not e.get("entry_priced")) else 0.0
        ret = 0.0
        for _t, px, frac, _why in legs:
            gross = sign * (px - e["entry_px"]) / e["entry_px"]
            ret += frac * (gross - bps / 1e4)
        ret -= ent_slip
        xt = legs[-1][0]
        notional = e.get("notional") or CLIP_USD
        closed.append({
            "sym": e["sym"], "entry_ts": e["entry_ts"], "exit_ts": xt,
            "ret": ret, "usd": ret * notional,
            "why": [w for *_x, w in legs],
            "legs": legs,
            "held_h": (xt - e["entry_ts"]) / 3600.0,
            "cluster": int(e["entry_ts"] // 86400),      # entry calendar day
            "slip_bps": bps,
        })
        open_until.append(xt)
    s = score(closed)
    s["skipped"] = skipped
    s["closed"] = closed
    return s


# ============================================================== SHIPPED RULE
def shipped_rule():
    """The book's REAL exit, READ FROM ITS OWN MODULE — never retyped.

    A retyped constant is a constant that drifts (the `backtest_carry_gate`
    lesson: it pinned MAX_POSITIONS=8 while the bot shipped 12, so a re-run
    measured a book the fleet does not run). Returns (rule, provenance).
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import lighter_perp_sniper as snp
    except Exception as e:                                      # noqa: BLE001
        return None, f"UNREADABLE: {type(e).__name__}: {e}"
    rule = {"tp_pct": float(snp.TAKE_PROFIT_PCT),
            "sl_pct": abs(float(snp.STOP_LOSS_PCT)),
            "max_hold_h": float(snp.MAX_HOLD_SEC) / 3600.0}
    prov = (f"lighter_perp_sniper: TAKE_PROFIT_PCT={snp.TAKE_PROFIT_PCT} "
            f"STOP_LOSS_PCT={snp.STOP_LOSS_PCT} "
            f"MAX_HOLD_SEC={snp.MAX_HOLD_SEC} MAX_OPEN={snp.MAX_OPEN} "
            f"LOOP_SECONDS={snp.LOOP_SECONDS} "
            "(BARE MODULE LITERALS — no env read, no registered lever)")
    return rule, prov


def shipped_cap():
    try:
        sys.path.insert(0, os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        import lighter_perp_sniper as snp
        return int(snp.MAX_OPEN)
    except Exception:                                           # noqa: BLE001
        return 4


# ========================================================= CALIBRATION GATE
def calibrate(replayed, actual_mean_pct, px_arm=None, tol_pp=None):
    """DOES THE HARNESS REPRODUCE THE BOOK IT IS COUNTERFACTUALISING? (gx)

    Two independent arms, both of which must pass:
      MEAN — the replayed SHIPPED rule's mean %/trade vs the ledger's own.
      PRICE — per row, can the ledger's recorded exit price be recovered from
              the same tape within CALIB_PX_TOL_BPS? (a mean can agree by
              cancellation while every individual row is wrong.)

    Returns (ok, detail). A False here is a REFUSAL, not a warning: the caller
    must emit no candidate. Widening the tolerance to pass is the failure this
    gate exists to make impossible — a gate you cannot pass at the available
    resolution is a REAL RESULT ("cannot calibrate at 1m"), not a bug to tune
    away.
    """
    tol = CALIB_TOL_PP if tol_pp is None else tol_pp
    if actual_mean_pct is None or replayed.get("mean_pct") is None:
        return False, "no baseline to calibrate against"
    gap = replayed["mean_pct"] - actual_mean_pct
    mean_ok = abs(gap) <= tol
    detail = (f"MEAN arm: replayed {replayed['mean_pct']:+.3f}%/trade vs actual "
              f"{actual_mean_pct:+.3f}%/trade (gap {gap:+.3f}pp, tol {tol}pp) "
              f"-> {'PASS' if mean_ok else 'FAIL'}")
    px_ok = True
    if px_arm is not None:
        frac = px_arm.get("frac_ok")
        px_ok = frac is not None and frac >= CALIB_PX_MIN_FRAC
        detail += (f"; PRICE arm: {px_arm.get('n_ok')}/{px_arm.get('n')} rows "
                   f"reproduce exit px within {CALIB_PX_TOL_BPS:.0f}bps "
                   f"(floor {CALIB_PX_MIN_FRAC:.0%}) "
                   f"-> {'PASS' if px_ok else 'FAIL'}")
    ok = mean_ok and px_ok
    if not ok:
        detail += "  ** RECOMMENDATIONS WITHHELD **"
    return ok, detail


def row_bias(entries, sim):
    """PER-ROW replayed-minus-actual, on the SHIPPED rule. This is the number
    that decides whether the instrument may speak, and its DISTRIBUTION is the
    finding: a mean gap and a median gap that disagree by an order of magnitude
    means the error is not a uniform friction constant but a handful of rows
    the tape cannot describe. One-sidedness is worse than size — a replay that
    is never materially pessimistic inflates every candidate it ranks."""
    byk = {(c["sym"], int(c["entry_ts"])): c for c in sim.get("closed") or []}
    rowsd = []
    for e in entries:
        c = byk.get((e["sym"], int(e["entry_ts"])))
        if not c or e.get("actual_ret") is None:
            continue
        rowsd.append({"sym": e["sym"], "entry_ts": e["entry_ts"],
                      "actual_pct": 100.0 * e["actual_ret"],
                      "replay_pct": 100.0 * c["ret"],
                      "gap_pp": 100.0 * (c["ret"] - e["actual_ret"]),
                      "actual_reason": e.get("reason"),
                      "replay_why": c["why"], "slip_bps": c["slip_bps"]})
    g = sorted(r["gap_pp"] for r in rowsd)
    if not g:
        return {"n": 0, "rows": []}
    return {
        "n": len(g), "rows": sorted(rowsd, key=lambda r: -abs(r["gap_pp"])),
        "mean": sum(g) / len(g), "median": st.median(g),
        "min": g[0], "max": g[-1],
        "p90": g[int(0.9 * (len(g) - 1))],
        "n_over_1pp": sum(1 for x in g if abs(x) > 1.0),
        # One-sidedness by MAGNITUDE, not by count: a 16/32 sign split with
        # a +1.65pp max and a -0.13pp min is a one-sided error, and a count
        # would report it as perfectly balanced.
        "pos_share_of_mass": (sum(x for x in g if x > 0)
                              / sum(abs(x) for x in g)) if any(g) else None,
        "pos_count_share": sum(1 for x in g if x > 0) / len(g),
        # The paired-mean of the actual on EXACTLY the replayed rows: the only
        # like-for-like baseline. Comparing a 32-row replay to a 33-row ledger
        # mean is a different-population comparison wearing a calibration hat.
        "actual_mean_matched": sum(r["actual_pct"] for r in rowsd) / len(rowsd),
    }


def price_calibration(entries, tape, tol_bps=None):
    """Per-row: is the ledger's own recorded exit price present in the tape at
    the recorded exit minute (within tolerance)? A POSITIVE CONTROL for the
    whole harness — a check that inspects nothing reports clean, so this must
    be seen to produce both verdicts before its silence means anything."""
    tol = CALIB_PX_TOL_BPS if tol_bps is None else tol_bps
    n = n_ok = 0
    worst = []
    for e in entries:
        xp, xt = e.get("actual_exit_px"), e.get("actual_exit_ts")
        if not xp or not xt:
            continue
        bars = tape.get(e["sym"]) or {}
        bar = (int(xt) // 60) * 60
        near = [bars[b] for b in (bar - 120, bar - 60, bar, bar + 60)
                if b in bars]
        if not near:
            continue
        n += 1
        lo = min(b[2] for b in near)
        hi = max(b[1] for b in near)
        if lo <= xp <= hi:
            gap = 0.0
        else:
            ref = hi if xp > hi else lo
            gap = abs(xp - ref) / ref * 1e4
        if gap <= tol:
            n_ok += 1
        else:
            worst.append((e["sym"], round(gap, 1)))
    worst.sort(key=lambda x: -x[1])
    return {"n": n, "n_ok": n_ok, "frac_ok": (n_ok / n if n else None),
            "worst": worst[:6]}


# ================================================================= families
def family_grid(name, horizon_h):
    """The five families. (d) and (e) are CONTROLS and are NOT OPTIONAL —
    (hl) killed 25 of 30 throughput candidates because a content-free time
    stop reproduced 78% of the claimed gain, so any candidate that fails to
    beat the timer has bought turnover, not expectancy (I19)."""
    if name == "fixed":                                        # (a) incumbent
        return [{"tp_pct": tp, "sl_pct": sl, "max_hold_h": h}
                for tp in (0.05, 0.08, 0.10, 0.15, 0.25, 0.40)
                for sl in (0.03, 0.05, 0.10, 0.20)
                for h in (1, 3, 6, 12, 24)
                if h <= horizon_h]
    if name == "trail":                                        # (b) HWM trail
        return [{"sl_pct": sl, "trail_pct": tr, "trail_arm_pct": arm,
                 "max_hold_h": h}
                for sl in (0.10, 0.20, None)
                for tr in (0.05, 0.10, 0.20, 0.30)
                for arm in (None, 0.05, 0.15, 0.50)
                for h in (6, 12, 24)
                if h <= horizon_h]
    if name == "ladder":                                       # (c) THE ANSEM
        out = []
        for l1, frac in ((0.05, 0.5), (0.10, 0.5), (0.15, 0.5), (1.00, 0.5)):
            for tr in (0.10, 0.20, 0.30):
                for far in (0.40, 1.00, 4.00, None):
                    for h in (6, 24):
                        if h > horizon_h:
                            continue
                        out.append({"ladder": [(l1, frac)], "trail_pct": tr,
                                    "trail_on_ladder": True,
                                    "trail_arm_pct": 0.50,
                                    "tp_pct": far, "sl_pct": 0.10,
                                    "max_hold_h": h})
        return out
    if name == "time":                                # (d) CONTROL: bare timer
        return [{"max_hold_h": h} for h in (1, 2, 3, 6, 12, 24, 48, 72)
                if h <= horizon_h]
    if name == "hold":                        # (e) CONTROL: what entries are worth
        return [{}]
    raise ValueError(f"unknown family {name}")


FAMILIES = ("fixed", "trail", "ladder", "time", "hold")
CONTROLS = ("time", "hold")


def on_grid_edge(rule, cells):
    """A winner pinned at a searched boundary is UNBOUNDED in that direction —
    'widen the grid', never 'the best exit is X'."""
    edges = []
    for k in ("tp_pct", "sl_pct", "max_hold_h", "trail_pct", "trail_arm_pct"):
        vals = sorted({c.get(k) for c in cells if c.get(k) is not None})
        v = rule.get(k)
        if v is None or not vals:
            continue
        if v == vals[0] or v == vals[-1]:
            edges.append(k)
    return edges


# ================================================================ (hm) null
def random_null(entries, tape, rule, horizon_h, draws, basis, cap, tiers,
                seed=20260820, bar_sec=60):
    """MATCHED-RANDOM entries: same coins, same calendar span, same rule, same
    walker. (hm) — on this venue a random long earns a non-zero drift for free,
    so a positive mean is not an edge until it beats this."""
    import random
    rng = random.Random(seed)
    syms = [e["sym"] for e in entries if tape.get(e["sym"])]
    if not syms:
        return None
    lo = min(e["entry_ts"] for e in entries)
    hi = max(e["entry_ts"] for e in entries)
    per = max(1, len(entries))
    means = []
    for _ in range(draws):
        fake = []
        for _i in range(per):
            s = rng.choice(syms)
            bars = tape.get(s) or {}
            cand = [t for t in bars if lo <= t <= hi]
            if not cand:
                continue
            t0 = rng.choice(cand)
            o = bars[t0][0]
            if not o:
                continue
            fake.append({"sym": s, "entry_ts": float(t0), "entry_px": o,
                         "is_long": True, "entry_priced": False,
                         "notional": CLIP_USD,
                         "qvol": next((e.get("qvol") for e in entries
                                       if e["sym"] == s), None)})
        if not fake:
            continue
        s = simulate(fake, tape, rule, horizon_h, basis=basis, cap=cap,
                     tiers=tiers, bar_sec=bar_sec)
        if s["n"]:
            means.append(s["mean_pct"])
    if not means:
        return None
    means.sort()
    return {"draws": len(means), "means": means,
            "mean": sum(means) / len(means),
            "p50": means[len(means) // 2],
            "p90": means[int(0.9 * (len(means) - 1))],
            "max": means[-1]}


def p_random_ge(null_means, observed):
    if not null_means:
        return None
    return sum(1 for m in null_means if m >= observed) / len(null_means)


# =============================================================== tape loader
def build_tape(entries, horizon_h, resolution="1m", ids=None, cache=CACHE,
               refresh=False):
    """Fetch each entry's window once, cached on disk. Also stamps each entry
    with the coin's QUOTE VOLUME ON ITS OWN ENTRY DAY (point-in-time — the
    orderBookDetails snapshot is TODAY's number and would mis-tier a book whose
    turnover has since moved)."""
    ids = ids or market_ids()
    store = {}
    if os.path.exists(cache) and not refresh:
        try:
            with open(cache) as fh:
                store = json.load(fh)
        except (OSError, ValueError):
            store = {}
    bar_sec = {"1m": 60, "1h": 3600}[resolution]
    tape, dayvol = {}, store.get("_dayvol", {})
    misses = []
    for e in entries:
        sym = e["sym"]
        mid = ids.get(sym)
        lo = int(e["entry_ts"]) - bar_sec
        hi = int(e["entry_ts"] + horizon_h * 3600) + bar_sec
        key = f"{resolution}:{sym}:{lo}:{hi}"
        rows = store.get(key)
        if rows is None:
            if mid is None:
                misses.append(sym)
                continue
            rows = {str(k): v for k, v in
                    fetch_candles(mid, lo, hi, resolution).items()}
            store[key] = rows
        cur = tape.setdefault(sym, {})
        for k, v in rows.items():
            cur[int(k)] = tuple(v)
        # point-in-time day volume for the slippage tier
        dk = f"dv:{sym}:{int(e['entry_ts']) // 86400}"
        qv = dayvol.get(dk)
        if qv is None and mid is not None:
            d0 = (int(e["entry_ts"]) // 86400) * 86400
            dc = fetch_candles(mid, d0 - 86400, d0 + 86400, "1d")
            qv = max([v[4] for v in dc.values()] or [0.0]) or None
            dayvol[dk] = qv
        e["qvol"] = qv
    store["_dayvol"] = dayvol
    try:
        with open(cache, "w") as fh:
            json.dump(store, fh)
    except OSError:
        pass
    return tape, misses


# ============================================================ SYNTHETIC ARM
def synthetic_surge_entries(days=90, mult=None, min_vol_m=None, ids=None,
                            cache=CACHE, refresh=False, verbose=True):
    """RECONSTRUCTED surge entries — an escape from n=33 that is NON-ARMING.

    Reconstructs the scout's surge trigger at HOURLY resolution (rolling 24h
    quote volume >= SURGE_MULT x the value one bar earlier) over crypto books.
    Three declared limits, none of them fixable from this endpoint:
      * the live detector compares against a ~5-MINUTE-old snapshot; an hourly
        reconstruction gives the jump 60 minutes to happen, so this is a STRICT
        UPPER BOUND on supply (the supply census measured 49.0/30d this way vs
        10.8-12.9/30d directly observed).
      * there is NO realised record for an entry that was never taken, so the
        (gx) calibration gate has nothing to bite on. This arm is marked
        NON-ARMING and must never be blended with the realised arm (I14).
      * entries fill LAG-1 at the OPEN of the bar after the trigger bar.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import lighter_perp_sniper as snp
        mult = float(snp.SURGE_MULT) if mult is None else mult
    except Exception:                                           # noqa: BLE001
        mult = 3.0 if mult is None else mult
    rows = order_book_details()
    ids = ids or market_ids(rows)
    crypto = [str(r.get("symbol")) for r in rows
              if str(r.get("status") or "active").lower() == "active"
              and int(r.get("strategy_index") or 0) == 2]
    now = int(time.time())
    lo = now - days * 86400
    store = {}
    if os.path.exists(cache) and not refresh:
        try:
            with open(cache) as fh:
                store = json.load(fh)
        except (OSError, ValueError):
            store = {}
    out, tape = [], {}
    for i, sym in enumerate(crypto):
        mid = ids.get(sym)
        if mid is None:
            continue
        key = f"syn1h:{sym}:{lo}:{now}"
        rowsc = store.get(key)
        if rowsc is None:
            rowsc = {str(k): v for k, v in
                     fetch_candles(mid, lo, now, "1h").items()}
            store[key] = rowsc
            if verbose and i % 10 == 0:
                print(f"  synthetic tape {i}/{len(crypto)} {sym}",
                      file=sys.stderr)
        bars = {int(k): tuple(v) for k, v in rowsc.items()}
        tape[sym] = bars
        ts = sorted(bars)
        roll = []
        for j, t in enumerate(ts):
            roll.append(bars[t][4])
            if len(roll) > 24:
                roll.pop(0)
            if j < 25 or j + 1 >= len(ts):
                continue
            cur = sum(roll)
            prev = sum(roll[:-1]) + bars[ts[j - 24]][4] if j >= 24 else None
            if not prev or prev <= 0:
                continue
            if cur >= mult * prev:
                nt = ts[j + 1]                       # LAG-1: the NEXT bar
                o = bars[nt][0]
                if not o:
                    continue
                out.append({"sym": sym, "entry_ts": float(nt), "entry_px": o,
                            "is_long": True, "entry_priced": False,
                            "notional": CLIP_USD, "qvol": cur,
                            "source": "surge_reconstructed"})
    try:
        with open(cache, "w") as fh:
            json.dump(store, fh)
    except OSError:
        pass
    return out, tape


# ================================================================== printing
def fmt(s):
    """One line per cell. EVERY doctrine field is on it — including the two
    that are easiest to leave off and most load-bearing here: the CLUSTER-
    robust t (these entries overlap in time) and the top-1 CONCENTRATION."""
    if not s.get("n"):
        return f"{str(s.get('label', '')):26} n=0"
    t = "  n/a" if s["t"] is None else f"{s['t']:+5.2f}"
    ct = "  n/a" if s["cluster_t"] is None else f"{s['cluster_t']:+5.2f}"
    halves = ("halves n/a  " if s["h1_pct"] is None
              else f"h1 {s['h1_pct']:+6.2f} h2 {s['h2_pct']:+6.2f}")
    top1 = "   -" if s["top1_share"] is None else f"{s['top1_share']:4.0%}"
    tail = " TAIL" if s["tail_flag"] else ""
    skip = f" skip {s['skipped']}" if s.get("skipped") else ""
    return (f"{str(s.get('label', '')):26} n={s['n']:<4} "
            f"${s['total_usd']:+8.2f} mean {s['mean_pct']:+7.3f}% "
            f"t={t} ct={ct}/{s['n_clusters']:<3} {halves} "
            f"win {s['win_rate']:3.0%} hold {s['median_hold_h']:5.2f}h "
            f"dd {s['maxdd_pct']:4.2f}% top1 {top1}{tail}{skip}")


# ================================================================= selftest
def _bars(seq, t0=1_800_000, step=60):
    """[(o,h,l,c)] -> {ts: (o,h,l,c,qv)} on a fixed grid."""
    return {t0 + i * step: (o, h, l, c, 1e9)
            for i, (o, h, l, c) in enumerate(seq)}


def _selftest():
    T0 = 1_800_000            # 60-aligned, so the bar grid matches the walker
    # --- 1. POLL basis: a rising tape trips tp at the bar whose CLOSE clears.
    b = _bars([(100, 100, 100, 100), (100, 108, 100, 105),
               (105, 120, 105, 118), (118, 130, 118, 125)])
    legs = walk_exit(b, T0, 100.0, True, {"tp_pct": 0.15, "max_hold_h": 10},
                     10, basis="poll", skip_entry_bar=True)
    assert len(legs) == 1 and legs[0][3] == "tp", legs
    assert legs[0][0] == T0 + 120 and abs(legs[0][1] - 118) < 1e-9, legs

    # --- 2. TOUCH basis fires a bar EARLIER on the same tape, at the level.
    legs_t = walk_exit(b, T0, 100.0, True, {"tp_pct": 0.15, "max_hold_h": 10},
                       10, basis="touch", skip_entry_bar=True)
    assert legs_t[0][0] == T0 + 120 and abs(legs_t[0][1] - 115.0) < 1e-9, legs_t
    b2 = _bars([(100, 100, 100, 100), (100, 118, 100, 101),
                (101, 101, 101, 101)])
    assert walk_exit(b2, T0, 100.0, True, {"tp_pct": 0.15}, 10,
                     basis="touch")[0][3] == "tp"
    assert walk_exit(b2, T0, 100.0, True, {"tp_pct": 0.15}, 10,
                     basis="poll")[0][3] == "horizon", "poll must not catch a wick"

    # --- 3. LAG-1: a +50% spike INSIDE the entry bar is never credited.
    b3 = _bars([(100, 150, 100, 100), (100, 100, 100, 100)])
    assert walk_exit(b3, T0 + 30, 100.0, True, {"tp_pct": 0.15}, 10,
                     basis="touch", skip_entry_bar=True)[0][3] == "horizon"
    assert walk_exit(b3, T0, 100.0, True, {"tp_pct": 0.15}, 10,
                     basis="touch", skip_entry_bar=False)[0][3] == "tp"

    # --- 4. ADVERSE FIRST when one bar touches both.
    b4 = _bars([(100, 100, 100, 100), (100, 120, 88, 100)])
    assert walk_exit(b4, T0, 100.0, True,
                     {"tp_pct": 0.15, "sl_pct": 0.10}, 10,
                     basis="touch")[0][3] == "sl"

    # --- 5. TRAIL is RATCHET-ONLY and arms only above its threshold.
    b5 = _bars([(100, 100, 100, 100), (100, 130, 100, 130),
                (130, 130, 100, 100), (100, 100, 100, 100)])
    l5 = walk_exit(b5, T0, 100.0, True,
                   {"trail_pct": 0.20, "trail_arm_pct": 0.15}, 10,
                   basis="touch")
    assert l5[0][3] == "trail" and abs(l5[0][1] - 104.0) < 1e-9, l5
    l5b = walk_exit(b5, T0, 100.0, True,
                    {"trail_pct": 0.20, "trail_arm_pct": 0.50}, 10,
                    basis="touch")
    assert l5b[0][3] == "horizon", l5b     # never armed -> rides to horizon
    # RATCHET, pinned by a case only a ratchet can pass: the high-water mark
    # is set two bars back, and a trail that follows the price DOWN (peak =
    # this bar's high) never fires. A trail whose peak can fall is not a trail
    # — it is a moving target that guarantees the give-back it exists to stop.
    b5c = _bars([(100, 100, 100, 100), (130, 130, 130, 130),
                 (104, 105, 100, 100), (100, 100, 100, 100)])
    l5c = walk_exit(b5c, T0, 100.0, True, {"trail_pct": 0.20}, 10,
                    basis="touch")
    assert l5c[0][3] == "trail" and abs(l5c[0][1] - 104.0) < 1e-9, l5c

    # --- 6. LADDER: half out at +10%, remainder to a far tp. KNOWN ANSWER.
    b6 = _bars([(100, 100, 100, 100), (100, 112, 100, 112),
                (112, 500, 112, 500)])
    l6 = walk_exit(b6, T0, 100.0, True,
                   {"ladder": [(0.10, 0.5)], "tp_pct": 4.00}, 10, basis="touch")
    assert [x[3] for x in l6] == ["ladder1", "tp"], l6
    assert abs(l6[0][2] - 0.5) < 1e-12 and abs(l6[1][2] - 0.5) < 1e-12
    e6 = [{"sym": "X", "entry_ts": float(T0), "entry_px": 100.0,
           "is_long": True, "entry_priced": False, "notional": 100.0,
           "qvol": 5e6}]
    s6 = simulate(e6, {"X": b6}, {"ladder": [(0.10, 0.5)], "tp_pct": 4.00},
                  10, basis="touch", cap=None, tiers=SLIP_TIERS_ZERO)
    assert abs(s6["mean_pct"] - (0.5 * 10 + 0.5 * 400)) < 1e-6, s6["mean_pct"]

    # --- 7. FRICTION is charged per LEG and on the entry when unpriced.
    s7 = simulate(e6, {"X": b6}, {"ladder": [(0.10, 0.5)], "tp_pct": 4.00},
                  10, basis="touch", cap=None,
                  tiers=((float("inf"), 100.0),))     # 100bps = 1%
    # two legs x 1% each, weighted -> 1%, plus 1% entry = 2% total drag
    assert abs(s7["mean_pct"] - (205.0 - 2.0)) < 1e-6, s7["mean_pct"]
    e7 = dict(e6[0]); e7["entry_priced"] = True
    s7b = simulate([e7], {"X": b6}, {"ladder": [(0.10, 0.5)], "tp_pct": 4.00},
                   10, basis="touch", cap=None, tiers=((float("inf"), 100.0),))
    assert abs(s7b["mean_pct"] - (205.0 - 1.0)) < 1e-6, s7b["mean_pct"]

    # --- 8. UNKNOWN VOLUME takes the WORST tier — absence buys no discount.
    assert slip_bps(None, SLIP_TIERS_MEAN) == 17.49
    assert slip_bps(50_000, SLIP_TIERS_MEAN) == 17.49
    assert slip_bps(5_000_000, SLIP_TIERS_MEAN) == 2.52

    # --- 9. TIME-ONLY control exits exactly on the clock, every time.
    b9 = _bars([(100, 101, 99, 100)] * 20)
    l9 = walk_exit(b9, T0, 100.0, True, {"max_hold_h": 0.1}, 10, basis="poll")
    assert l9[0][3] == "max_hold" and l9[0][0] == T0 + 360, l9
    # --- and HOLD-TO-HORIZON has no exit rule at all.
    l9b = walk_exit(b9, T0, 100.0, True, {}, 0.2, basis="poll")
    assert l9b[0][3] == "horizon", l9b
    # --- a max_hold that lands ON the tape's edge is the CLOCK, not the
    #     harness window: mislabelling it makes a 24h stop indistinguishable
    #     from the 24h no-exit CONTROL, which is the comparison (hl) rests on.
    l9c = walk_exit(b9, T0, 100.0, True, {"max_hold_h": 0.31}, 0.31,
                    basis="poll")
    assert l9c[0][3] == "max_hold", l9c

    # --- 10. CLUSTER t reduces to the plain t when clusters are singletons.
    v = [1.0, -2.0, 3.0, 0.5, -1.5, 2.5]
    ct, G = cluster_t(v, list(range(len(v))))
    assert G == len(v) and abs(ct - _t_stat(v)) < 1e-9, (ct, _t_stat(v))
    # and it SHRINKS hard when the correlation is INSIDE the clusters — which
    # is the situation these overlapping entries are actually in.
    v2 = [1.0] * 5 + [-0.2] * 5
    ct2, G2 = cluster_t(v2, [0] * 5 + [1] * 5)
    assert G2 == 2 and abs(ct2 - 2.0 / 3.0) < 1e-9, ct2
    assert abs(ct2) < abs(_t_stat(v2)), (ct2, _t_stat(v2))
    # a degenerate cluster structure returns None rather than a fake number.
    assert cluster_t([1.0, 2.0], [0, 0]) == (None, 1)

    # --- 11. CONCENTRATION: one trade carrying the book must be FLAGGED.
    cl = [{"ret": 0.01, "usd": 1.0, "exit_ts": i, "why": ["x"], "held_h": 1.0,
           "cluster": i} for i in range(4)]
    cl.append({"ret": 1.0, "usd": 100.0, "exit_ts": 9, "why": ["x"],
               "held_h": 1.0, "cluster": 9})
    s = score(cl)
    assert s["tail_flag"] and abs(s["top1_share"] - 100 / 104) < 1e-9
    # a NEGATIVE total has no meaningful share and must say so, not sign-flip.
    s_neg = score([{"ret": -0.1, "usd": -10.0, "exit_ts": 1, "why": ["x"],
                    "held_h": 1, "cluster": 1},
                   {"ret": 0.01, "usd": 1.0, "exit_ts": 2, "why": ["x"],
                    "held_h": 1, "cluster": 2}])
    assert s_neg["top1_share"] is None and not s_neg["tail_flag"]

    # --- 12. THE CALIBRATION GATE REFUSES, and is seen to do BOTH verdicts.
    ok, d = calibrate({"mean_pct": -0.09}, -0.09)
    assert ok and "PASS" in d, d
    ok, d = calibrate({"mean_pct": +0.50}, -0.09)
    assert (not ok) and "WITHHELD" in d, d
    ok, d = calibrate({"mean_pct": -0.09}, -0.09,
                      px_arm={"n": 10, "n_ok": 3, "frac_ok": 0.3})
    assert (not ok) and "WITHHELD" in d, d
    ok, d = calibrate({"mean_pct": -0.09}, -0.09,
                      px_arm={"n": 10, "n_ok": 9, "frac_ok": 0.9})
    assert ok, d
    # and the SWEEP honours it: an uncalibrated run emits NO cell results.
    out = run_sweep([], {}, ["fixed"], 6, calibration=(False, "forced"),
                    shipped={"tp_pct": .15})
    assert out["refused"] and not out.get("cells"), out

    # --- 13. CAP is enforced: overlapping entries beyond the cap are SKIPPED.
    bb = _bars([(100, 100, 100, 100)] * 200)
    ents = [{"sym": "X", "entry_ts": float(T0 + i * 60), "entry_px": 100.0,
             "is_long": True, "entry_priced": False, "notional": 20.0,
             "qvol": 5e6} for i in range(6)]
    s13 = simulate(ents, {"X": bb}, {"max_hold_h": 2.0}, 3, cap=2,
                   tiers=SLIP_TIERS_ZERO)
    assert s13["n"] == 2 and s13["skipped"] == 4, (s13["n"], s13["skipped"])

    # --- 14. GRID EDGE is detected on every axis it searches.
    cells = family_grid("fixed", 24)
    assert "tp_pct" in on_grid_edge({"tp_pct": 0.40, "sl_pct": 0.05,
                                     "max_hold_h": 6}, cells)
    assert on_grid_edge({"tp_pct": 0.10, "sl_pct": 0.05,
                         "max_hold_h": 6}, cells) == []

    # --- 15. Both CONTROL families exist and are never droppable. (hl) is
    #     the whole reason: a content-free time stop reproduced 78% of a
    #     claimed gain, so a sweep with no timer control cannot tell a widening
    #     from denominator shrinkage. A run must not be able to omit them.
    assert set(CONTROLS) == {"time", "hold"}, CONTROLS
    assert set(CONTROLS) <= set(FAMILIES)
    for c in CONTROLS:
        assert family_grid(c, 24), c
    assert len(family_grid("time", 24)) >= 5

    print("selftest OK (15 groups)")
    return 0


# ==================================================================== driver
def run_sweep(entries, tape, families, horizon_h, shipped, calibration,
              basis="poll", cap=None, tiers=SLIP_TIERS_MEAN, bar_sec=60,
              null_means=None):
    """Score every cell of every requested family. REFUSES WHOLESALE when the
    calibration gate failed — it returns a refusal object with no cells, so a
    caller cannot accidentally read a number out of an uncalibrated run."""
    ok, detail = calibration
    if not ok:
        return {"refused": True, "calibration": detail, "cells": []}
    cells = []
    for fam in families:
        grid = family_grid(fam, horizon_h)
        for rule in grid:
            s = simulate(entries, tape, rule, horizon_h, basis=basis, cap=cap,
                         tiers=tiers, bar_sec=bar_sec)
            if not s["n"]:
                continue
            s.pop("closed", None)
            s["family"] = fam
            s["rule"] = {k: v for k, v in rule.items() if v is not None}
            s["grid_edge"] = on_grid_edge(rule, grid)
            if null_means is not None:
                s["p_random_ge"] = p_random_ge(null_means, s["mean_pct"])
            cells.append(s)
    base = simulate(entries, tape, shipped, horizon_h, basis=basis, cap=cap,
                    tiers=tiers, bar_sec=bar_sec)
    base.pop("closed", None)
    base["label"] = "SHIPPED"
    cells.sort(key=lambda c: -(c["total_usd"] or 0))
    return {"refused": False, "calibration": detail, "cells": cells,
            "shipped": base}


def _synthetic_arm(a, rule, cap, tiers, fams, result):
    """The reconstructed arm. Runs on BOTH paths — a failed calibration of the
    REALISED arm neither validates nor invalidates it, because it was never
    calibratable in the first place (there is no realised record for an entry
    that was never taken). It carries its own status, permanently."""
    if not a.synthetic:
        return
    print("\n" + "=" * 78)
    print("SYNTHETIC ARM — RECONSTRUCTED surge entries. NON-ARMING, ALWAYS.")
    print("No realised record exists for an entry that was never taken, so the")
    print("(gx) gate has nothing to bite on — this arm can never be calibrated,")
    print("on any run. Hourly reconstruction is also a STRICT UPPER BOUND on")
    print("the 5-minute detector's real supply, and --resolution-calib measures")
    print("what the hourly bar alone costs. Never blend with the realised arm")
    print("(I14: the ledger is the record).")
    print("=" * 78)
    se, stape = synthetic_surge_entries(days=a.syn_days, refresh=a.refresh)
    print(f"  reconstructed {len(se)} surge entries over {a.syn_days}d")
    if not se:
        print("  no reconstructed entries — nothing to report")
        return
    ssw = run_sweep(se, stape, fams, a.horizon_h, rule,
                    (True, "NOT APPLICABLE — this arm is non-arming"),
                    basis=a.basis, cap=cap, tiers=tiers, bar_sec=3600)
    print("  " + fmt(dict(ssw["shipped"], label="SHIPPED@1h")))
    b0 = ssw["shipped"]["mean_pct"]
    for c in ssw["cells"][:a.top] + [c for c in ssw["cells"]
                                     if c["family"] in CONTROLS]:
        ex = (c["mean_pct"] - b0) if b0 is not None else None
        tag = f" excess {ex:+6.3f}pp" if ex is not None else ""
        edge = (f" GRID-EDGE:{','.join(c['grid_edge'])}"
                if c["grid_edge"] else "")
        print("  " + fmt(dict(c, label=f"{c['family']}:{c['rule']}"))[:210]
              + tag + edge)
    result["synthetic"] = {
        "n_entries": len(se), "NON_ARMING": True,
        "cells": [{k: v for k, v in c.items() if k != "closed"}
                  for c in ssw["cells"]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ledger", help="local ledger json (offline)")
    ap.add_argument("--families", default="all",
                    help="comma list of " + ",".join(FAMILIES) + ", or 'all'")
    ap.add_argument("--horizon-h", type=float, default=24.0,
                    help="max tape window per entry (also family (e)'s hold)")
    ap.add_argument("--basis", default="poll", choices=("poll", "touch"))
    ap.add_argument("--slip", default="mean", choices=("mean", "p90", "zero"))
    ap.add_argument("--cap", type=int, default=None,
                    help="max concurrent (default: the bot's own MAX_OPEN)")
    ap.add_argument("--null", type=int, default=0,
                    help="(hm) matched-random draws")
    ap.add_argument("--synthetic", action="store_true",
                    help="ALSO run the reconstructed surge arm (NON-ARMING)")
    ap.add_argument("--syn-days", type=int, default=90)
    ap.add_argument("--resolution-calib", action="store_true",
                    help="what does an HOURLY bar cost vs 1m on the same rule?")
    ap.add_argument("--rows", action="store_true",
                    help="per-row replayed-vs-actual calibration table")
    ap.add_argument("--basis-scan", action="store_true",
                    help="try every basis/slippage convention available and "
                         "report whether ANY of them calibrates")
    ap.add_argument("--diagnostic-sweep", action="store_true",
                    help="on a FAILED calibration, still print cells — as "
                         "excess over the shipped rule, against the measured "
                         "bias envelope. NON-ARMING by construction.")
    ap.add_argument("--calibrate-only", action="store_true")
    ap.add_argument("--verify-fees", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json", help="write the full result object here")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    tiers = {"mean": SLIP_TIERS_MEAN, "p90": SLIP_TIERS_P90,
             "zero": SLIP_TIERS_ZERO}[a.slip]
    print("=" * 78)
    print("🎯 SNIPER EXIT-SHAPE COUNTERFACTUAL — Lighter tape only, LAG-1")
    print("=" * 78)
    if a.slip == "zero":
        print("!! --slip zero: FRICTION IS OFF. This mode exists only to SIZE")
        print("!! the friction term. NO conclusion may be drawn from it.")

    rule, prov = shipped_rule()
    if rule is None:
        print(f"REFUSED: cannot read the shipped rule ({prov})")
        return 2
    print(f"\nSHIPPED RULE (read from the module, never retyped):\n  {prov}")
    print(f"  -> {rule}")
    cap = shipped_cap() if a.cap is None else a.cap
    print(f"  cap (concurrent positions) = {cap}")
    print(f"  basis = {a.basis}   slippage tiers ({a.slip}) = "
          + ", ".join(f"<${hi:,.0f}: {b}bps" if hi != float("inf")
                      else f"rest: {b}bps" for hi, b in tiers))

    if a.verify_fees:
        z, tk, mk, n = verify_zero_fee()
        print(f"\nFEE CHECK (measured, not asserted): {n} active books, "
              f"max taker {tk}, max maker {mk} -> "
              f"{'ZERO-FEE CONFIRMED' if z else '** NON-ZERO FEE **'}")

    rows = fetch_ledger(path=a.ledger)
    actual = ledger_mean_pct(rows)
    entries, dropped = ledger_entries(rows)
    print(f"\nREALISED ARM (THE RECORD, I14): {len(rows)} closes, "
          f"{len(entries)} replayable, {len(dropped)} dropped {dropped}")
    n_missing_side = sum(1 for e in entries if e["side_missing"])
    if n_missing_side:
        print(f"  {n_missing_side} row(s) carry NO side and are treated as "
              "long (this book is long-only by config) — counted, not assumed")
    print(f"  ledger ACTUAL mean = {actual:+.4f}%/trade over {len(rows)} closes")

    print(f"\nfetching 1m tape (+{a.horizon_h}h per entry) ...")
    tape, misses = build_tape(entries, a.horizon_h, "1m", refresh=a.refresh)
    if misses:
        print(f"  !! no market_id for {sorted(set(misses))} — excluded")
    px_arm = price_calibration(entries, tape)
    base = simulate(entries, tape, rule, a.horizon_h, basis=a.basis, cap=cap,
                    tiers=tiers)
    bias = row_bias(entries, base)
    # LIKE-FOR-LIKE: grade the replay against the ledger mean of EXACTLY the
    # rows that replayed. A 32-row replay judged against a 33-row ledger mean
    # is a different-population comparison wearing a calibration hat.
    matched = bias.get("actual_mean_matched", actual)
    ok, detail = calibrate(base, matched, px_arm=px_arm)
    print("\n" + "-" * 78)
    print("CALIBRATION GATE (gx) — a harness that cannot reproduce what DID")
    print("happen may not say what WOULD have. It REFUSES; it does not caveat.")
    print("-" * 78)
    print("  " + detail.replace("; ", "\n  "))
    print(f"  (baseline is the ledger mean of the {bias['n']} MATCHED rows, "
          f"{matched:+.4f}%; the all-33 ledger mean is {actual:+.4f}%)")
    if px_arm["worst"]:
        print(f"  worst price-arm rows (bps): {px_arm['worst']}")
    if bias["n"]:
        print(f"\n  BIAS DISTRIBUTION (replay - actual, per row, pp):")
        print(f"    mean {bias['mean']:+.3f}  median {bias['median']:+.3f}  "
              f"p90 {bias['p90']:+.3f}  min {bias['min']:+.3f}  "
              f"max {bias['max']:+.3f}")
        print(f"    {bias['n_over_1pp']} of {bias['n']} rows off by >1pp; "
              f"{bias['pos_count_share']:.0%} of rows are replay-optimistic "
              f"by COUNT but {bias['pos_share_of_mass']:.0%} of the total "
              f"error MASS is optimistic")
        print("    A mean and a median an order of magnitude apart says the")
        print("    error is NOT a uniform friction constant — it is a handful")
        print("    of rows the candle tape cannot describe. One-sidedness is")
        print("    the worse half: a replay that is never materially")
        print("    pessimistic inflates every candidate it ranks.")
    if a.rows and bias["n"]:
        print(f"\n  {'sym':11}{'actual%':>9}{'replay%':>9}{'gap pp':>8}  "
              f"{'ledger reason':24}replay")
        for r in bias["rows"]:
            print(f"  {r['sym']:11}{r['actual_pct']:+9.3f}"
                  f"{r['replay_pct']:+9.3f}{r['gap_pp']:+8.3f}  "
                  f"{str(r['actual_reason']):24}{r['replay_why']}")
    print(f"\n  replayed SHIPPED: {fmt(dict(base, label='SHIPPED'))}")
    print(f"  exit mix replayed: {base['why']}")
    led_mix = {}
    for r in rows:
        k = str(r.get("reason") or "?").split("_")[-1]
        led_mix[k] = led_mix.get(k, 0) + 1
    print(f"  exit mix in the LEDGER: {led_mix}")
    print("\n  FIDELITY LIMIT, DECLARED: the bot evaluates ONE orderbook-MID")
    print("  poll per 60s and then MARKET-closes. 1m candle closes are TRADE")
    print("  prints on a 60s grid whose phase is unknown, so the replay can")
    print("  disagree with the bot by up to one poll and by the mid-vs-print")
    print("  gap. `--basis touch` bounds that from the optimistic side.")

    result = {"shipped_rule": rule, "provenance": prov, "cap": cap,
              "basis": a.basis, "slip": a.slip,
              "actual_mean_pct": actual, "actual_mean_matched": matched,
              "replayed": {k: v for k, v in base.items() if k != "closed"},
              "bias": {k: v for k, v in bias.items() if k != "rows"},
              "bias_rows": bias.get("rows", []),
              "calibration": {"ok": ok, "detail": detail, "price": px_arm}}

    if a.basis_scan:
        # EXHAUSTIVENESS. "Empty output is not a negative result until the
        # check has been seen to produce a positive one" — so a REFUSAL is not
        # a finding until the obvious alternatives have been tried and named.
        print("\nBASIS SCAN — does ANY available convention calibrate?")
        print(f"  {'basis':7}{'slip':7}{'replayed%':>11}{'gap pp':>9}  verdict")
        scan = []
        for bs in ("poll", "touch"):
            for sl_name, sl_t in (("mean", SLIP_TIERS_MEAN),
                                  ("p90", SLIP_TIERS_P90),
                                  ("zero", SLIP_TIERS_ZERO)):
                s = simulate(entries, tape, rule, a.horizon_h, basis=bs,
                             cap=cap, tiers=sl_t)
                bb = row_bias(entries, s)
                if not bb["n"]:
                    continue
                gp = s["mean_pct"] - bb["actual_mean_matched"]
                v = "PASS" if abs(gp) <= CALIB_TOL_PP else "FAIL"
                print(f"  {bs:7}{sl_name:7}{s['mean_pct']:+11.3f}"
                      f"{gp:+9.3f}  {v}")
                scan.append({"basis": bs, "slip": sl_name,
                             "mean_pct": s["mean_pct"], "gap_pp": gp,
                             "pass": v == "PASS"})
        result["basis_scan"] = scan
        if not any(x["pass"] for x in scan):
            print("  -> NO convention available from this tape calibrates.")

    if a.resolution_calib:
        t1h, _ = build_tape(entries, a.horizon_h, "1h", refresh=a.refresh)
        b1h = simulate(entries, t1h, rule, a.horizon_h, basis=a.basis, cap=cap,
                       tiers=tiers, bar_sec=3600)
        print("\nRESOLUTION CALIBRATION (what a coarser bar costs; this is the")
        print("only calibration the SYNTHETIC arm can carry):")
        print(f"  1m  {fmt(dict(base, label='shipped@1m'))}")
        print(f"  1h  {fmt(dict(b1h, label='shipped@1h'))}")
        if b1h.get("mean_pct") is not None:
            print(f"  -> hourly bars move the shipped rule by "
                  f"{b1h['mean_pct'] - base['mean_pct']:+.3f}pp/trade")
        result["resolution_calib"] = {"m1": base["mean_pct"],
                                      "h1": b1h.get("mean_pct")}

    null_means = None
    if a.null:
        # ONE owner of the null: main calls `random_null`, it does not carry a
        # second copy of it. A re-implemented rule is a second rule, and this
        # repo has already paid for that twice (the go-live gate's duplicate in
        # evidence_review, the brain's FEE_RT key).
        print(f"\n(hm) MATCHED-RANDOM NULL, {a.null} draws — a directional")
        print("book is graded against random entries, never against zero: on")
        print("this venue a random long earns a non-zero drift for free.")
        nl = random_null(entries, tape, rule, a.horizon_h, a.null, a.basis,
                         cap, tiers)
        if nl:
            null_means = nl["means"]
            p = p_random_ge(null_means, base["mean_pct"])
            print(f"  null shipped-rule mean: p50 {nl['p50']:+.3f}%  "
                  f"p90 {nl['p90']:+.3f}%  max {nl['max']:+.3f}%")
            print(f"  P(random >= observed shipped) = {p:.3f}")
            result["null"] = {"draws": nl["draws"], "p50": nl["p50"],
                              "p90": nl["p90"],
                              "p_random_ge_shipped": p}

    if a.calibrate_only:
        if a.json:
            with open(a.json, "w") as fh:
                json.dump(result, fh, indent=1, default=str)
        return 0 if ok else 1

    fams = FAMILIES if a.families == "all" else tuple(a.families.split(","))
    for c in CONTROLS:
        if c not in fams:
            fams = tuple(fams) + (c,)     # controls are NOT optional (hl)
    sw = run_sweep(entries, tape, fams, a.horizon_h, rule, (ok, detail),
                   basis=a.basis, cap=cap, tiers=tiers, null_means=null_means)
    result["sweep"] = {"refused": sw["refused"],
                       "cells": [{k: v for k, v in c.items() if k != "closed"}
                                 for c in sw["cells"]]}
    print("\n" + "=" * 78)
    if sw["refused"]:
        print("SWEEP REFUSED — the harness does not reproduce the book.")
        print("NO CELL RESULTS WERE COMPUTED. Every downstream number is")
        print("NON-ARMING. This is a RESULT, not a bug to tune away: do not")
        print("widen SNIPER_CALIB_TOL_PP to make it pass.")
        print("=" * 78)
        if a.diagnostic_sweep:
            env = abs(bias["mean"]) if bias["n"] else None
            print("\n--diagnostic-sweep: cells below are DIAGNOSTIC ONLY.")
            print("They are printed as EXCESS OVER THE SHIPPED RULE through")
            print("the SAME biased harness, because a paired difference")
            print("cancels the common-mode part of a bias the harness has")
            print("already been shown to carry. The cancellation is PARTIAL")
            print("and unquantified — the bias is exit-TIMING dependent and")
            print("candidates exit at different times.")
            if env is not None:
                print(f"BIAS ENVELOPE = {env:.3f}pp/trade (the shipped rule's")
                print("own measured calibration error). An excess smaller than")
                print("the envelope is indistinguishable from harness error.")
                print(f"For scale: the book's whole mean is {matched:+.3f}%.")
            dsw = run_sweep(entries, tape, fams, a.horizon_h, rule,
                            (True, "FORCED — DIAGNOSTIC ONLY"), basis=a.basis,
                            cap=cap, tiers=tiers, null_means=null_means)
            b0 = dsw["shipped"]["mean_pct"]
            print("\n" + fmt(dsw["shipped"]) + "   <- baseline")
            for c in dsw["cells"][:a.top] + [c for c in dsw["cells"]
                                             if c["family"] in CONTROLS]:
                ex = c["mean_pct"] - b0
                mark = "  WITHIN-BIAS" if (env is not None and abs(ex) < env) \
                    else "  >envelope"
                edge = (f" GRID-EDGE:{','.join(c['grid_edge'])}"
                        if c["grid_edge"] else "")
                print(fmt(dict(c, label=f"{c['family']}:{c['rule']}"))[:210]
                      + f" excess {ex:+6.3f}pp{mark}{edge}")
            result["diagnostic_sweep"] = {
                "NON_ARMING": True, "bias_envelope_pp": env,
                "cells": [{k: v for k, v in c.items() if k != "closed"}
                          for c in dsw["cells"]]}
        _synthetic_arm(a, rule, cap, tiers, fams, result)
        if a.json:
            with open(a.json, "w") as fh:
                json.dump(result, fh, indent=1, default=str)
        return 1

    print(f"REALISED ARM — {len(sw['cells'])} cells, ranked by total $")
    print("=" * 78)
    print(fmt(sw["shipped"]))
    print("-" * 78)
    for c in sw["cells"][:a.top]:
        edge = f" GRID-EDGE:{','.join(c['grid_edge'])}" if c["grid_edge"] else ""
        pr = (f" P(rnd>=)={c['p_random_ge']:.3f}"
              if c.get("p_random_ge") is not None else "")
        print(fmt(dict(c, label=f"{c['family']}:{c['rule']}"))[:210] + edge + pr)
    print("-" * 78)
    print("CONTROLS (a candidate that does not beat these bought turnover,")
    print("not expectancy — (hl) killed 25 of 30 throughput candidates here):")
    for c in sw["cells"]:
        if c["family"] in CONTROLS:
            print("  " + fmt(dict(c, label=f"{c['family']}:{c['rule']}"))[:210])

    _synthetic_arm(a, rule, cap, tiers, fams, result)

    if a.json:
        with open(a.json, "w") as fh:
            json.dump(result, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
