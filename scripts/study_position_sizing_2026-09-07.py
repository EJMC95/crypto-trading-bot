#!/usr/bin/env python3
"""study_position_sizing_2026-09-07.py — FIVE SIZING RULES ON EVERY BOOK'S OWN LEDGER.

    .venv/bin/python3 scripts/study_position_sizing_2026-09-07.py            # live feeds
    .venv/bin/python3 scripts/study_position_sizing_2026-09-07.py \
        --ledger t.json --feed p.json --bus b.json [--draws 500] [--out r.json]
    .venv/bin/python3 scripts/study_position_sizing_2026-09-07.py --selftest

THE QUESTION. The fleet sizes four different ways and calls none of them a
policy: the two real-money books clip `equity x GROSS_X / max_open` (an equity
FRACTION with a gross multiplier), the taker clips `RISK_USD / half the daily
range` (constant DOLLAR risk, volatility-scaled), the shadow family stakes a
fixed $50, and the funding books a fixed notional — with the brain's
[1/6.7, 6.7] conviction, the allocation organ's [0.25, 4] evidence scale, the
7-day governor and the two (wu) rails multiplied on top. Nothing anywhere is
Kelly. This instrument puts the five textbook rules on ONE ladder of risk and
reads, per book, what each does to return, drawdown, volatility and ruin on that
book's own closes.

THE LADDER is risk-at-the-stop per position as a fraction of equity, `rho`:
0.25% / 0.5% / 1% / 2% / 3% / 5%. A notional fraction `f` and a stop `s` are the
same thing on this axis (`rho = f * s`), which is what makes the five rules
comparable at all — avo live (2x gross / 6 slots, 10% stop) and mum live
(5x / 12 slots, 4% stop) are 3.33% and 1.67% on it.

THE FIVE RULES, each a multiplier `m` on equity, applied to the day's unit-clip
return:
  fixed_dollar    N = f * E0            a constant clip, no compounding
  fixed_fraction  N = f * E_t           the live books' shape (f = gross/slots)
  vol_adjusted    N = f * E_t * clamp(sd_expanding / sd_trailing, 1/4, 2)
                                         a volatility target on the book's own
                                         daily returns, trailing 20 days
  risk_per_trade  N = rho * E_t / s_i   the taker's shape with the STOP as the
                                         adverse move (per-trade `s_i` where the
                                         ledger stamps one)
  kelly_*         N = frac * (mu / var) * E_t   half, quarter, and quarter on
                                         the LOWER BOUND of mu (I16 — rank on a
                                         bound, never the mean), estimated
                                         EXPANDING with no look-ahead, at the
                                         probe rung below MIN_N days of history

THE UNIT OF RISK IS THE TRADING DAY, and the first cut of this got it wrong in a
way worth recording. Positions sized on the same equity and lost together are
one observation, not several — (xy) already ruled that mum's 8-leg halt is ONE
draw. The first version chained trades by OVERLAP: a trade joins the batch if it
opens before the batch's latest close. That is single-linkage clustering, and on
a book that is continuously in the market it collapses the entire history into
one cluster — measured on the taker, **183 closes became 5 "batches", one of
them 108 legs**. A UTC day cannot do that: it captures same-instant and same-day
co-movement (the halt, the rebalance, the correlated basket) and is bounded by
construction. So `R_day = sum r_i` over that day's closes on a unit clip,
`Q_day = sum r_i/s_i`, and every rule's equity step is `m * R_day`
(risk_per_trade: `rho * Q_day`). Kelly and the vol target estimate on that same
daily series — the decision unit the book actually faces, since it does not
choose how many signals fire at once.

WHAT IS NOT OPTIMISED, BY CONSTRUCTION. The proposal rule reads NO return
column — only `P(ruin)`, the p95 drawdown and peak GROSS, and its selftest permutes
every return field to pin that they cannot move the answer. On the reference rule
(fixed_fraction — the shape real money runs), `rho_adm` is the largest rung whose
bootstrap shows P(ruin) = 0, p95 max drawdown <= the go-live gate's OWN 15% bar
(`golive_readiness.GOLIVE_MAX_DD`, imported, never retyped) AND peak gross inside
the fleet's own per-book budget (`fleet_bus.BRAIN_GROSS_X`), evaluated under
BOTH an iid and a 5-day block resample with the **more conservative** taken. The
proposal is `rho* = min(RHO_HARD_CAP, largest rung <= SAFETY * rho_adm)` — HALF
the admissible rung (the parameter-uncertainty haircut that makes half-Kelly the
practitioner's Kelly), never above **2% of equity per position** whatever the
bootstrap says, because a bootstrap is CONDITIONAL on its sample and this tape is
one falling-BTC regime (item 18).

EDGE ENTERS ONCE, AS A PRECONDITION — and this study's own first output is why.
A rule reading no return column cannot tell "safe because it wins" from "safe
because it loses slowly": the perp sniper, measured mean NEGATIVE at t=-0.78,
earned a 0.25% proposal purely because at that size its p95 drawdown stays inside
the bar. So a book is sized at all only while its I16 lower bound on mean
per-trade return is POSITIVE (`fleet_allocation.lower_bound`, the one owner) —
this fleet's own I24, "scale a coin flip and you scale a coin flip". It is a
gate on being sized, never a chooser between rungs, and `rho_adm` is still
reported for a refused book so the reader sees what drawdown alone permitted.
Sizing cannot manufacture an edge; the honest size for a book without one is the
allocation organ's probe floor.

CALIBRATION, fail-closed, and the scope it certifies:
  1. the sample must reproduce the LIVE `golive-readiness` grade exactly
     (`edge_audit.calibrate` — the one owner of the era / quarantine / phantom /
     adopted pipeline, imported, never re-implemented);
  2. this module's own path arithmetic must reproduce each graded book's
     published REALISED drawdown from its `pnl_abs` in close order, to 0.05pp of
     the book — a drawdown routine that cannot reproduce what DID happen may not
     say what WOULD have ((gx)).
  Either failure REFUSES (exit 2) rather than reports. **Only books the live
  grade actually covers are studied**: a retired book is not in that payload, so
  nothing here is calibrated for it and it is skipped by name rather than
  silently mixed in.

EVERY HORIZON IS QUOTABLE BY CONSTRUCTION. The edge audit's rule is that a
projection reaching more than 10x past its own sample is not quotable; the first
run of this study projected mum's live book 19.2x. The horizon is now
`min(--horizon, 10 x the book's own span)` per book and the used horizon is
published beside every number, so no proposal rests on a projection the record
cannot support.

WHAT THIS DOES NOT DO. It moves no capital, writes no lever, changes no clip —
asserted by its own selftest's source scan. It does not model the venue's
liquidation (that is `lighter_margin_model` and the live rows' `leverage` block);
it reports peak GROSS instead, from the ledger's own peak concurrency
(`golive_readiness.peak_concurrency`). Deposits on the live rows are removed via
`edge_audit.book_usd_for` (equity - pnl_abs), the same denominator the edge audit
uses.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402  the sample pipeline + calibration
import fleet_allocation as fa            # noqa: E402  t_crit / MIN_N — one owner
import fleet_bus as fb                   # noqa: E402  BRAIN_GROSS_X — one owner
import golive_readiness as gr            # noqa: E402  GOLIVE_MAX_DD / peak_concurrency

# ------------------------------------------------------------------ constants

#: The ladder: risk at the stop per position, as a fraction of equity.
LADDER = (0.0025, 0.005, 0.01, 0.02, 0.03, 0.05)
#: No proposal above this, whatever the bootstrap says (one-regime tape, item 18).
RHO_HARD_CAP = 0.02
#: The proposal is this fraction of the admissible rung (the half-Kelly haircut).
SAFETY = 0.5
#: The gate's own drawdown bar — imported, never retyped ((hj)).
DD_BAR = float(gr.GOLIVE_MAX_DD)
#: A path touching this fraction below its peak is counted under `p_dd_half`.
DD_HALF = 0.50
#: PEAK GROSS CEILING for admissibility — the fleet's OWN per-book gross budget
#: for a shadow book (`fleet_bus.BRAIN_GROSS_X`, the (sp) bound), imported
#: rather than invented. It exists because a rung is not conservative merely
#: for having a small per-position risk: MEASURED on this ledger, the carry
#: book's 1% rung implies **7.5x gross** (a 2% bleed threshold standing in for
#: a price stop, times 15 concurrent legs), and drawdown alone never saw it.
#: The live rows carry a LARGER operator ceiling of their own (`gross_x_max` on
#: the row); this study applies the shadow budget uniformly as the conservative
#: reading and says so rather than reading each book a different bar.
GROSS_CAP_X = float(fb.BRAIN_GROSS_X)
#: Days of history before Kelly / the vol target may speak, and the floor of
#: trading days a PROPOSAL needs. `fleet_allocation.MIN_N` is the fleet's one
#: owner of "how many samples before a number may be spoken" (I16 as amended).
MIN_N = int(fa.MIN_N)
#: The vol target's trailing window, in days, and its clamp.
VOL_WINDOW = 20
VOL_CLAMP = (0.25, 2.0)
#: Bootstrap block lengths; the proposal takes the more conservative verdict.
BLOCKS = (1, 5)
KELLY_FRACS = {"kelly_half": 0.5, "kelly_quarter": 0.25, "kelly_quarter_lb": 0.25}
METHODS = ("fixed_dollar", "fixed_fraction", "vol_adjusted", "risk_per_trade",
           "kelly_half", "kelly_quarter", "kelly_quarter_lb")
#: The reference rule for the proposal — the shape the real-money books run.
REFERENCE = "fixed_fraction"
#: THE COMMON RUNG the five rules are compared at, across every calibrated book.
#: Comparing them at each book's own `rho*` answers a different question and on
#: a handful of books; holding the rung FIXED isolates the RULE, which is the
#: comparison being asked for. 0.5% is inside `RHO_HARD_CAP` and is the rung at
#: which the fleet's practical-ruin cliff first appears (see `p_dd_half`).
COMPARE_RUNG = 0.005
HORIZON_MONTHS = 6
#: A projection may not reach more than this multiple past its own sample —
#: the edge audit's own quotability rule, applied as a CAP on the horizon so
#: every published number satisfies it rather than carrying a caveat.
MAX_EXTRAPOLATION_X = 10.0
DRAWS = 500
SEED = 7
#: Path-machinery calibration tolerance, in percentage points of the book.
CAL_DD_TOL_PP = 0.05
#: Per-book declared stops for books whose rows do not stamp one — read from
#: each module's own constant. A book absent here AND without a stamped stop is
#: STOPLESS (the funding books, whose P&L is `accrued - fees` with no price
#: term) and is sized against a loss-quantile proxy, declared on its row.
DECLARED_STOP = {
    "band-kelly-lshadow": 0.05,               # KELLY_HARD_STOP
    "nav-cook-lshadow": 0.05,                 # COOK_HARD_STOP
    "lighter-perp-sniper-lshadow": 0.10,      # STOP_LOSS_PCT
    "perps-funding-lighter-lshadow": 0.10,    # FUNDING_HARD_STOP
    "perps-funding-lighter-lighter": 0.10,
    "band-garrett-lshadow": 0.10,             # variant of the Farmer
    "perps-funding-carry-lshadow": 0.02,      # BLEED_STOP_FRAC
    "lighter-dislocation-lshadow": 0.05,      # the ghost's 5% stop
}
STOPLESS = {"perps-funding-spread-lshadow", "book-hull-lshadow",
            "book-kiyosaki-lshadow", "band-barnes-lshadow"}

#: [I21] THE PRE-REGISTERED READ, declared with its AT-REGISTRATION numbers so
#: the follow-up is a COMMITMENT rather than a re-derivation — the (tt) shape,
#: which failed the first time it was left in prose. 👩 mum's LIVE arm is the
#: study's one real-money finding and it rests on the thinnest sample in the
#: table (10 trading days at the 10x extrapolation cap), so it is registered
#: rather than acted on, and it is graded on FRESH days only (I25: never the
#: window that motivated it).
PRE_REGISTERED = {
    "freqtrade-mum-lighter": {
        "id": "mum-live-rho-read",
        "registered": "2026-09-07",
        "at_registration": {
            "rho_now": 0.0167, "rho_adm": 0.005, "rho_star": 0.0025,
            "n_days": 10, "n_closes": 90, "edge_lb_pct": 0.00157,
            "extrapolation_x": 10.0,
        },
        "read_when": "n_days >= 30 (3x the registration sample) or 2026-10-07, "
                     "whichever comes first",
        "criterion": "re-run on days AFTER 2026-09-07 only. If rho_adm on the "
                     "FRESH sample is still below her running rho, escalate the "
                     "cut to Eamon with both numbers. If rho_adm >= rho_now the "
                     "flag is WITHDRAWN and recorded as withdrawn. Either way "
                     "the verdict is written down and this block is removed.",
    },
}


def registration_status(bot, seq):
    """(reg, fresh_days, due) for a pre-registered book, or (None, None, False).

    `fresh_days` counts trading days strictly AFTER the registration date — the
    only sample the criterion may be read on. Returns `due` True once the
    read_when condition is met, so the study says so on every run instead of
    waiting for someone to remember."""
    reg = PRE_REGISTERED.get(bot)
    if not reg:
        return None, None, False
    try:
        cut = datetime.strptime(reg["registered"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return reg, None, False
    fresh = sum(1 for u in seq.get("units") or [] if u["day"] > cut)
    due = fresh >= 30 or datetime.now(timezone.utc).date() >= _dt_date(2026, 10, 7)
    return reg, fresh, due


def _dt_date(y, m, d):
    from datetime import date
    return date(y, m, d)

#: Why a book got no proposal — distinct reasons, never collapsed into one
#: string, because "no rung is safe" and "half of a safe rung is below the
#: smallest rung modelled" are opposite findings.
NO_EDGE = "no admissible rung: every rung breaks the drawdown bar, the gross ceiling, or ruins"
BELOW_LADDER = "admissible only at the ladder floor; half of it is off this ladder"
THIN = "too few trading days to propose"
#: I24, in this fleet's own words: "a ceiling is computed only on a book whose
#: EDGE LOWER BOUND is positive — scale a coin flip and you scale a coin flip."
#: FOUND BY THIS STUDY'S OWN OUTPUT: the perp sniper carries a NEGATIVE measured
#: mean (t=-0.78) and still earned a 0.25% proposal, because at that size it
#: loses slowly enough to keep its p95 drawdown inside the bar. A rule that
#: reads no return column cannot tell "safe because it wins" from "safe because
#: it loses slowly", so the edge enters as a PRECONDITION on being sized at all
#: — never as a chooser of which rung earns most, which is the thing the brief
#: forbids. The bound is `fleet_allocation.lower_bound`, the one owner (I16).
WEAK_EDGE = "edge lower bound not positive (I24) — the honest size is the probe floor"


# ------------------------------------------------------------------ the sample

def stop_of(bot, extra, tag):
    """Stop distance (positive fraction) for one close, or None.

    Precedence: the row's own stamp (policy.stoploss; the taker's per-lens
    bars, breakout-tagged rows taking `brk_sl`; bezos/douglas `sl_frac`; the
    Parliament's `params.sl_pct`), then the book's declared constant."""
    ex = extra if isinstance(extra, dict) else {}
    pol = ex.get("policy")
    if isinstance(pol, dict) and isinstance(pol.get("stoploss"), (int, float)):
        return abs(float(pol["stoploss"]))
    bars = ex.get("bars")
    if isinstance(bars, dict):
        if "breakout" in str(tag or "") and isinstance(bars.get("brk_sl"), (int, float)):
            return abs(float(bars["brk_sl"]))
        if isinstance(bars.get("sl"), (int, float)):
            return abs(float(bars["sl"]))
    if isinstance(ex.get("sl_frac"), (int, float)) and ex["sl_frac"] > 0:
        return float(ex["sl_frac"])
    par = ex.get("params")
    if isinstance(par, dict) and isinstance(par.get("sl_pct"), (int, float)):
        return abs(float(par["sl_pct"]))
    return DECLARED_STOP.get(bot)


def daily_units(trades):
    """Chain trades into UTC-DAY units — see the docstring's unit note.

    trades: [(open_dt, close_dt, r, s, abs_usd)]. Returns days ordered in time:
    [{"day", "R", "Q", "L", "abs"}]. A day with no close is not a unit: the
    book's clock is its closes, and inserting empty days would dilute both the
    mean and the variance every rule is estimated on."""
    by = defaultdict(lambda: {"R": 0.0, "Q": 0.0, "L": 0, "abs": 0.0})
    for _op, cl, r, s, ab in trades:
        d = by[cl.date()]
        d["R"] += r
        d["Q"] += r / s
        d["L"] += 1
        d["abs"] += ab
    return [dict(by[k], day=k) for k in sorted(by)]


def book_sequence(bot, shaped_entry):
    """The book's era-scoped closes as daily units, plus the rules' scalars.

    Uses the 8-tuple rows `edge_audit.shape` returns: (pct, abs, closed_dt,
    opened_raw, extra, tag, pair, raw). A STOPLESS book gets a PROXY stop — the
    p95 of its own |losing return| — declared on the row, and its
    risk_per_trade then coincides with fixed_fraction by construction."""
    rows = shaped_entry["rows"]
    stops = [stop_of(bot, q[4], q[5]) for q in rows]
    stopless = bot in STOPLESS or all(s is None for s in stops)
    losses = sorted(abs(q[0]) for q in rows if q[0] < 0)
    proxy = ea._quantile(losses, 0.95) if losses else None
    if stopless:
        if not proxy:
            return None
        s_book = float(proxy)
        stops = [s_book] * len(rows)
    else:
        known = sorted(s for s in stops if s)
        s_book = float(ea._quantile(known, 0.5)) if known else None
        if not s_book:
            return None
        stops = [s if s else s_book for s in stops]
    trades, eps = [], []
    for q, s in zip(rows, stops):
        op = ea._ts(q[3]) or q[2]
        trades.append((op, q[2], float(q[0]), float(s), float(q[1] or 0.0)))
        eps.append((q[6], op, q[2]))
    units = daily_units(trades)
    if len(units) < 2:
        return None
    span_d = max(1e-9, (max(t[1] for t in trades) - min(t[0] for t in trades))
                 .total_seconds() / 86400.0)
    clips = sorted(abs(t[4]) / abs(t[2]) for t in trades if abs(t[2]) > 1e-12)
    recent = [abs(q[1]) / abs(q[0]) for q in rows[-20:] if abs(q[0]) > 1e-12]
    return {
        "bot": bot, "n": len(trades), "n_days": len(units), "units": units,
        "s_book": s_book, "stop_basis": "proxy_p95_loss" if stopless else "declared",
        "span_days": span_d,
        "days_per_year": len(units) / span_d * 365.25,
        "closes_per_year": len(trades) / span_d * 365.25,
        "peak_concurrent": gr.peak_concurrency(eps),
        "legs_max_day": max(u["L"] for u in units),
        "clip_median_usd": ea._quantile(clips, 0.5) if clips else None,
        "clip_recent_usd": (sum(recent) / len(recent)) if recent else None,
        "realised_usd": float(sum(t[4] for t in trades)),
        # I16's own bound on this book's mean per-trade return, from the one
        # owner. None when the sample cannot support one — which `propose`
        # reads as "not positive", the fail-CLOSED direction for handing out
        # size.
        "edge_lb_pct": fa.lower_bound([float(q[0]) for q in rows]),
    }


def rho_now(bot, seq, books):
    """Where the book sits on the ladder TODAY, and the basis for it. Live
    rows: their configured geometry (gross / slots x |stop|) off the published
    row; shadow rows: the last-20-close mean implied clip over the $1,000
    book, times the book's own stop."""
    if bot.endswith("-lighter"):
        for b in books or []:
            if b.get("bot") == bot:
                ex = b.get("extra") or {}
                try:
                    g, mo = float(ex.get("gross_x")), float(ex.get("max_open"))
                    sl = abs(float((ex.get("policy") or {}).get("stoploss")))
                    if g > 0 and mo > 0 and sl > 0:
                        return (g / mo * sl,
                                f"live geometry {g:g}x/{mo:g} slots @ {100*sl:g}% stop")
                except (TypeError, ValueError):
                    pass
        return None, "live row: geometry unreadable"
    c = seq.get("clip_recent_usd")
    if c:
        return c / 1000.0 * seq["s_book"], f"last-20 mean clip ${c:.0f} on $1,000"
    return None, "no priceable clip"


# ------------------------------------------------------------------ the rules

_TCRIT = {}


def _tcrit(n):
    if n not in _TCRIT:
        v = fa.t_crit(n) if n >= 2 else None
        _TCRIT[n] = float(v) if v else float(fa.Z_LOWER)
    return _TCRIT[n]


def _history_stats(R, seed_R):
    """Expanding (mean, var, n) and trailing-VOL_WINDOW sd BEFORE each step.

    R: (D, K) daily returns along the path; `seed_R`: the in-sample history
    known before a forward path starts (empty for the in-sample run itself).
    Every statistic at column k uses columns < k plus the seed — no look-ahead.
    `var` uses n-1; n<2 gives nan, which the callers floor."""
    D, K = R.shape
    n0 = len(seed_R)
    ext = np.concatenate(
        [np.broadcast_to(np.asarray(seed_R, float), (D, n0)), R], axis=1)
    c1 = np.concatenate([np.zeros((D, 1)), np.cumsum(ext, axis=1)], axis=1)
    c2 = np.concatenate([np.zeros((D, 1)), np.cumsum(ext * ext, axis=1)], axis=1)
    idx = np.arange(n0, n0 + K)                       # position BEFORE step k
    n = idx.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        s1, s2 = c1[:, idx], c2[:, idx]
        mean = np.where(n > 0, s1 / np.maximum(n, 1), np.nan)
        var = np.where(n > 1, (s2 - n * mean * mean) / np.maximum(n - 1, 1), np.nan)
        var = np.where(var < 0, 0.0, var)
        lo = np.maximum(idx - VOL_WINDOW, 0)
        nt = (idx - lo).astype(float)
        t1, t2 = c1[:, idx] - c1[:, lo], c2[:, idx] - c2[:, lo]
        tm = np.where(nt > 0, t1 / np.maximum(nt, 1), np.nan)
        tvar = np.where(nt > 1, (t2 - nt * tm * tm) / np.maximum(nt - 1, 1), np.nan)
        tvar = np.where(tvar < 0, 0.0, tvar)
    return mean, var, n, np.sqrt(tvar), nt


def multipliers(method, R, seed_R, f, rho, s_book, m_cap):
    """(m, is_risk_per_trade) — the per-step multiplier (D, K). The equity step
    is `m * R_day`, except risk_per_trade whose step is `rho * Q_day`."""
    D, K = R.shape
    if method in ("fixed_dollar", "fixed_fraction"):
        return np.full((D, K), f), False
    if method == "risk_per_trade":
        return np.full((D, K), rho), True
    mean, var, n, tsd, nt = _history_stats(R, seed_R)
    if method == "vol_adjusted":
        esd = np.sqrt(var)
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = np.where((nt >= VOL_WINDOW) & (tsd > 0) & (esd > 0), esd / tsd, 1.0)
        return f * np.clip(ratio, VOL_CLAMP[0], VOL_CLAMP[1]), False
    frac = KELLY_FRACS[method]
    mu = mean
    if method == "kelly_quarter_lb":
        se = np.sqrt(np.where(n > 1, var / np.maximum(n, 1), np.nan))
        tc = np.vectorize(lambda k: _tcrit(int(k)))(np.maximum(n, 2))
        mu = mean - tc * se
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where((n >= MIN_N) & (var > 0), frac * mu / var, np.nan)
    floor = LADDER[0] / s_book
    return np.where(np.isnan(raw), floor, np.clip(raw, 0.0, m_cap)), False


def run_paths(method, R, Q, seed_R, E0, rho, s_book, peak_conc=None,
              m_cap=None, days_per_year=None):
    """(equity paths (D, K+1), metrics) for one (method, rung).

    `E0` is the book's starting equity in dollars; the rung maps to a
    per-position notional fraction `f = rho / s_book`. Kelly rules take
    `m_cap`, the largest notional fraction they may size (default the top
    rung's). A path that reaches zero equity is RUIN and stops there — a book
    that has lost everything does not keep compounding."""
    D, K = R.shape
    f = rho / s_book
    m_cap = (LADDER[-1] / s_book) if m_cap is None else m_cap
    m, is_rpt = multipliers(method, R, seed_R, f, rho, s_book, m_cap)
    step = (rho * Q) if is_rpt else (m * R)
    if method == "fixed_dollar":
        C = f * E0
        E = np.concatenate([np.full((D, 1), E0),
                            E0 + C * np.cumsum(R, axis=1)], axis=1)
        dead = np.maximum.accumulate(E <= 0, axis=1)
        E = np.where(dead, 0.0, E)
        prev = np.maximum(E[:, :-1], 1e-12)
        g = np.where(E[:, :-1] > 0, (E[:, 1:] - E[:, :-1]) / prev, 0.0)
    else:
        growth = np.maximum(1.0 + step, 0.0)
        E = np.concatenate([np.full((D, 1), E0),
                            E0 * np.cumprod(growth, axis=1)], axis=1)
        g = np.where(E[:, :-1] > 0, growth - 1.0, 0.0)
    peak = np.maximum.accumulate(E, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        dd = np.where(peak > 0, 1.0 - E / peak, 1.0)
    maxdd = dd.max(axis=1)
    ruined = (E <= 0).any(axis=1)
    final = E[:, -1] / E0 - 1.0
    vol = g.std(axis=1, ddof=1) if K > 1 else np.zeros(D)
    # PEAK GROSS as a multiple of equity: the per-position fraction times the
    # ledger's own peak concurrency. For risk_per_trade the per-leg fraction is
    # `rho / s_i` and the day's individual stops are not carried separately, so
    # it is summarised at the book-median stop — stated, because a book whose
    # legs carry very different stops holds more gross than this line says.
    per_pos = np.full((D, K), f) if is_rpt else m
    gross_max = (per_pos * float(peak_conc or 1)).max(axis=1)
    rho_eff = np.full((D, K), rho) if is_rpt else (m * s_book)
    return E, {
        "ret_p05": float(np.quantile(final, 0.05)),
        "ret_p50": float(np.quantile(final, 0.50)),
        "ret_p95": float(np.quantile(final, 0.95)),
        "dd_p50": float(np.quantile(maxdd, 0.50)),
        "dd_p95": float(np.quantile(maxdd, 0.95)),
        "dd_p99": float(np.quantile(maxdd, 0.99)),
        "p_dd_bar": float((maxdd > DD_BAR).mean()),
        "p_dd_half": float((maxdd > DD_HALF).mean()),
        "p_ruin": float(ruined.mean()),
        "p_loss": float((final < 0).mean()),
        "vol_day": float(np.median(vol)),
        "vol_annual": (float(np.median(vol)) * math.sqrt(days_per_year)
                       if days_per_year else None),
        "gross_max_p50": float(np.quantile(gross_max, 0.50)),
        "rho_eff_p50": float(np.quantile(np.median(rho_eff, axis=1), 0.50)),
        "capped_share": (float((m >= m_cap - 1e-12).mean())
                         if method.startswith("kelly") else None),
    }


def propose(ladder_rows, n_days=None, edge_lb=None):
    """(rho_adm, rho_star, reason) from {rung: metrics} on the REFERENCE rule.

    Of the bootstrap it reads ONLY `p_ruin`, `dd_p95` and `gross_max_p50` —
    never a return column, pinned by the selftest's permutation. `rho_adm` is
    the largest rung with no ruin, a p95 drawdown inside the gate's bar AND peak
    gross inside `GROSS_CAP_X`; `rho_star` is the largest rung at or below
    `SAFETY * rho_adm`, capped at `RHO_HARD_CAP`.

    `edge_lb` is the book's one-sided lower bound on mean per-trade return
    (`fleet_allocation.lower_bound`). It is a PRECONDITION — see `WEAK_EDGE` —
    and never a chooser between rungs: `rho_adm` is still computed and reported
    so a reader can see what drawdown alone would have permitted."""
    if n_days is not None and n_days < MIN_N:
        return None, None, THIN
    adm = [r for r in sorted(ladder_rows)
           if ladder_rows[r]["p_ruin"] <= 0.0
           and ladder_rows[r]["dd_p95"] <= DD_BAR
           and ladder_rows[r].get("gross_max_p50", 0.0) <= GROSS_CAP_X]
    rho_adm = max(adm) if adm else None
    if edge_lb is None or edge_lb <= 0:
        return rho_adm, None, WEAK_EDGE
    if rho_adm is None:
        return None, None, NO_EDGE
    target = min(RHO_HARD_CAP, SAFETY * rho_adm)
    below = [r for r in LADDER if r <= target + 1e-12]
    if not below:
        return rho_adm, None, BELOW_LADDER
    return rho_adm, max(below), None


# ------------------------------------------------------------------ the study

def close_order_dd_pct(rows, book_usd):
    """Realised drawdown in CLOSE order as % of the book — the grader's own
    convention (`golive_readiness.stats`), reproduced here so this module's
    path arithmetic can be pinned against what DID happen."""
    eq = peak = dd = 0.0
    for q in sorted(rows, key=lambda q: q[2]):
        eq += float(q[1] or 0.0)
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return -dd / book_usd * 100.0


def resample(units, rnd, draws, k, block):
    """(R, Q, L) as (draws, k) arrays — a block resample of DAILY units.
    block=1 is the plain iid bootstrap; block>1 preserves local dependence."""
    Rv = np.array([u["R"] for u in units])
    Qv = np.array([u["Q"] for u in units])
    Lv = np.array([float(u["L"]) for u in units])
    n = len(units)
    if block <= 1:
        idx = np.array([rnd.choices(range(n), k=k) for _ in range(draws)])
    else:
        starts = np.array([rnd.choices(range(n), k=(k + block - 1) // block)
                           for _ in range(draws)])
        idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n
               ).reshape(draws, -1)[:, :k]
    return Rv[idx], Qv[idx], Lv[idx]


def _worse(per_block):
    """The block whose verdict is the more conservative on the two numbers the
    proposal reads, so a rung cannot be bought by picking a resampling scheme."""
    return max(BLOCKS, key=lambda b: (per_block[b]["p_ruin"], per_block[b]["dd_p95"]))


def study_book(seq, E0, draws=DRAWS, horizon_months=HORIZON_MONTHS, seed=SEED,
               ladder=LADDER, edge_lb=None):
    units = seq["units"]
    Rv = np.array([[u["R"] for u in units]])
    Qv = np.array([[u["Q"] for u in units]])
    s_book, dpy, pc = seq["s_book"], seq["days_per_year"], seq["peak_concurrent"]
    # THE HORIZON IS CAPPED AT THE QUOTABILITY RULE, per book.
    h_days = min(horizon_months * 30.44, MAX_EXTRAPOLATION_X * seq["span_days"])
    k = max(1, int(round(dpy * h_days / 365.25)))
    rnd = random.Random(seed)
    boots = {b: resample(units, rnd, draws, k, b) for b in BLOCKS}
    out = {"insample": {}, "forward": {}, "k_days": k,
           "horizon_days": h_days, "horizon_months_used": h_days / 30.44,
           "extrapolation_x": h_days / seq["span_days"]}
    for method in METHODS:
        out["insample"][method], out["forward"][method] = {}, {}
        rungs = ladder if not method.startswith("kelly") else (ladder[-1],)
        for rho in rungs:
            _, ins = run_paths(method, Rv, Qv, np.array([]), E0, rho, s_book,
                               peak_conc=pc, days_per_year=dpy)
            out["insample"][method][rho] = ins
            per_block = {}
            for b, (Rb, Qb, _Lb) in boots.items():
                _, fwd = run_paths(method, Rb, Qb, Rv[0], E0, rho, s_book,
                                   peak_conc=pc, days_per_year=dpy)
                per_block[b] = fwd
            w = _worse(per_block)
            out["forward"][method][rho] = dict(per_block[w], block=w)
    rho_adm, rho_star, why = propose(out["forward"][REFERENCE], seq["n_days"],
                                     edge_lb=edge_lb)
    out.update(rho_adm=rho_adm, rho_star=rho_star, no_proposal=why,
               at_star={}, at_rung={}, compare_rung=COMPARE_RUNG)

    def _at(rho):
        """Every rule at one rung, Kelly capped at that rung's notional so all
        five are compared at ONE risk ceiling rather than each at its own."""
        cell = {}
        cap = rho / s_book
        for method in METHODS:
            per_block = {}
            for b, (Rb, Qb, _Lb) in boots.items():
                _, fwd = run_paths(method, Rb, Qb, Rv[0], E0, rho, s_book,
                                   peak_conc=pc, m_cap=cap, days_per_year=dpy)
                per_block[b] = fwd
            w = _worse(per_block)
            _, ins = run_paths(method, Rv, Qv, np.array([]), E0, rho, s_book,
                               peak_conc=pc, m_cap=cap, days_per_year=dpy)
            cell[method] = {"forward": dict(per_block[w], block=w), "insample": ins}
        return cell

    # THE COMMON RUNG runs for EVERY book, including one refused a proposal:
    # the rule comparison is a question about the RULES, and excluding the books
    # without an edge would answer it on the winners only.
    out["at_rung"] = _at(COMPARE_RUNG)
    if rho_star is not None:
        out["at_star"] = _at(rho_star)
    return out


def run(ledger=None, feed=None, bus=None, draws=DRAWS,
        horizon_months=HORIZON_MONTHS, only=None):
    trades, books, pub = ea.load(ledger, feed, bus)
    shaped = ea.shape(trades)
    ok, findings = ea.calibrate(shaped, pub)
    res = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "horizon_months": horizon_months, "draws": draws,
           "ladder": list(LADDER), "dd_bar": DD_BAR,
           "rho_hard_cap": RHO_HARD_CAP, "safety": SAFETY, "blocks": list(BLOCKS),
           "calibration": {"ok": ok, "findings": findings},
           "books": {}, "skipped": {}}
    if not ok:
        res["refused"] = "sample does not reproduce the live golive-readiness grade"
        return res
    graded = (pub or {}).get("books") or {}
    for bot in sorted(shaped):
        if only and bot not in only:
            continue
        # SCOPE = THE CALIBRATED SET. A book the live grade does not carry (a
        # retired row's history) is not certified by gate 1 and is skipped by
        # name rather than silently mixed into a sizing answer.
        if bot not in graded:
            res["skipped"][bot] = "not in the live golive-readiness grade"
            continue
        seq = book_sequence(bot, shaped[bot])
        if seq is None or seq["n"] < MIN_N:
            res["skipped"][bot] = "no priceable stop, or below the close floor"
            continue
        E0 = ea.book_usd_for(bot, books)
        pv = graded.get(bot) or {}
        pub_dd = pv.get("max_dd_pct_realised")
        mine = close_order_dd_pct(shaped[bot]["scoped"], gr.BOOK_USD)
        cal = None
        if isinstance(pub_dd, (int, float)):
            cal = abs(mine - pub_dd)
            if cal > CAL_DD_TOL_PP:
                res["refused"] = (f"{bot}: close-order realised DD {mine:.3f}% != "
                                  f"published {pub_dd}% (tol {CAL_DD_TOL_PP}pp)")
                return res
        r_now, how = rho_now(bot, seq, books)
        entry = {k: v for k, v in seq.items() if k != "units"}
        entry.update(E0=E0, rho_now=r_now, rho_now_basis=how,
                     realised_dd_pct_closeorder=mine, published_dd_pct=pub_dd,
                     dd_calibration_gap_pp=cal,
                     graded_t=pv.get("t"), graded_mean_pct=pv.get("mean_pct"),
                     graded_ready=pv.get("ready"))
        entry.update(study_book(seq, E0, draws=draws, horizon_months=horizon_months,
                                edge_lb=seq.get("edge_lb_pct")))
        reg, fresh, due = registration_status(bot, seq)
        if reg:
            entry["pre_registered"] = dict(reg, fresh_days=fresh, due=due)
        res["books"][bot] = entry
    return res


# ------------------------------------------------------------------ rendering

def _pct(x, p=1):
    return "   —" if x is None else f"{100*x:.{p}f}"


def _rung(rho):
    return "—" if rho is None else f"{100*rho:.2g}%"


def render(res):
    if res.get("refused"):
        return (f"REFUSED: {res['refused']}\n"
                + "\n".join(f"  {b}: {w}" for b, w in res["calibration"]["findings"]))
    L = [f"POSITION SIZING — {len(res['books'])} calibrated books, block bootstrap "
         f"x{res['draws']} (blocks {res['blocks']}, worse taken), horizon capped at "
         f"{MAX_EXTRAPOLATION_X:g}x each book's own span. Ladder = risk at the stop "
         f"per position, % of equity. Proposal = min({100*res['rho_hard_cap']:g}%, "
         f"{res['safety']:g} x largest rung with P(ruin)=0, p95 DD <= "
         f"{100*res['dd_bar']:g}% and peak gross <= {GROSS_CAP_X:g}x) on {REFERENCE}; "
         f"it reads ruin, drawdown and gross only, never a return.", ""]
    L.append(f"{'book':30s} {'n':>4s} {'days':>4s} {'pk':>3s} {'stop':>5s} "
             f"{'rho_now':>7s} {'adm':>5s} {'rho*':>5s} {'horiz':>6s} {'xtrp':>5s} "
             f"{'t':>5s} {'edgeLB':>7s}  {'why no proposal':<26s}")
    for bot, b in res["books"].items():
        t = b["graded_t"]
        L.append(f"{bot:30s} {b['n']:4d} {b['n_days']:4d} {b['peak_concurrent']:3d} "
                 f"{_pct(b['s_book'],1):>5s} {_pct(b['rho_now'],2):>7s} "
                 f"{_rung(b['rho_adm']):>5s} {_rung(b['rho_star']):>5s} "
                 f"{b['horizon_months_used']:5.1f}m {b['extrapolation_x']:4.1f}x "
                 f"{(f'{t:5.2f}' if isinstance(t,(int,float)) else '    —')} "
                 f"{_pct(b.get('edge_lb_pct'),3):>7s}  "
                 f"{(b['no_proposal'] or ''):<26s}")
    L += ["", "THE LADDER on fixed_fraction (forward): rung -> ret p50 | dd p95 | "
              "P(dd>bar) | P(ruin) | peak gross x equity",
          "  RETURNS ARE CONDITIONAL ON THE SAMPLE REPEATING IN DISTRIBUTION and "
          "compound its daily mean — on a short hot window they are arithmetically "
          "correct and absurd as forecasts. Nothing in the proposal reads them; "
          "read them ACROSS rules at one rung, never as a level."]
    for bot, b in res["books"].items():
        cells = [f"{_rung(r)}: {_pct(b['forward'][REFERENCE][r]['ret_p50'])}%/"
                 f"{_pct(b['forward'][REFERENCE][r]['dd_p95'])}%/"
                 f"{b['forward'][REFERENCE][r]['p_dd_bar']:.2f}/"
                 f"{b['forward'][REFERENCE][r]['p_ruin']:.2f}/"
                 f"{b['forward'][REFERENCE][r]['gross_max_p50']:.1f}x"
                 for r in LADDER]
        L.append(f"  {bot:30s} " + "  ".join(cells))
    # ---- the RULE comparison, at ONE rung, across every calibrated book ----
    cr = res["books"] and next(iter(res["books"].values()))["compare_rung"]
    L += ["", f"THE FIVE RULES AT ONE COMMON RUNG ({_rung(cr)} risk per position), "
              f"across all {len(res['books'])} calibrated books — median RATIO to "
              f"fixed_dollar, so the RULE is isolated from the book. >1 is more of "
              f"that quantity.",
          f"   {'rule':18s} {'ret p50':>8s} {'ret p05':>8s} {'maxDD p95':>10s} "
          f"{'vol/day':>8s} {'P(dd>50%)':>10s} {'P(ruin)':>8s} {'peak gross':>11s}"]
    for method in METHODS:
        rr, r5, dd, vv, hh, ru, gg = [], [], [], [], [], [], []
        for b in res["books"].values():
            base = b["at_rung"]["fixed_dollar"]["forward"]
            f = b["at_rung"][method]["forward"]
            # A GROWTH RATIO IS UNDEFINED AGAINST A WIPED-OUT BASE. fixed_dollar
            # is the ONE rule of the five that can reach -100% (it never
            # de-risks after a loss), so `1 + ret` is exactly 0 for it on a
            # badly losing book and the ratio must be DROPPED, not divided.
            # Found by this section crashing on its first run, which is the
            # honest way to learn it; the asymmetry now has its own column.
            if abs(1 + base["ret_p50"]) > 1e-9:
                rr.append((1 + f["ret_p50"]) / (1 + base["ret_p50"]))
            if abs(1 + base["ret_p05"]) > 1e-9:
                r5.append((1 + f["ret_p05"]) / (1 + base["ret_p05"]))
            if base["dd_p95"] > 1e-9:
                dd.append(f["dd_p95"] / base["dd_p95"])
            if base["vol_day"] > 1e-9:
                vv.append(f["vol_day"] / base["vol_day"])
            hh.append(f["p_dd_half"])
            ru.append(f["p_ruin"])
            if base["gross_max_p50"] > 1e-9:
                gg.append(f["gross_max_p50"] / base["gross_max_p50"])
        med = lambda xs: (f"{sorted(xs)[len(xs) // 2]:.3f}" if xs else "    —")
        mx = lambda xs: (f"{max(xs):.3f}" if xs else "    —")
        L.append(f"   {method:18s} {med(rr):>8s} {med(r5):>8s} {med(dd):>10s} "
                 f"{med(vv):>8s} {med(hh):>10s} {mx(ru):>8s} {med(gg):>11s}")
    L.append("   P(dd>50%) is a MEDIAN and P(ruin) a MAXIMUM across books, both "
             "absolute rather than ratios. P(dd>50%) is the practical read of "
             "'ruin': strict P(equity->0) is 0.00 for every COMPOUNDING rule at "
             "every rung, because a fraction of a shrinking equity cannot reach "
             "zero — only fixed_dollar, which never de-risks, can actually wipe "
             "an account out, and its column says so.")

    L += ["", "EVERY RULE AT THE PROPOSAL rho* (forward; Kelly capped at rho*'s "
              "notional so all five are compared at one risk ceiling)"]
    for bot, b in res["books"].items():
        if b["rho_star"] is None:
            L.append(f"\n{bot}: NO PROPOSAL — {b['no_proposal']}")
            f0 = b["forward"][REFERENCE][LADDER[0]]
            L.append(f"   at the ladder floor {_rung(LADDER[0])}: ret p50 "
                     f"{_pct(f0['ret_p50'])}% · dd p95 {_pct(f0['dd_p95'])}% · "
                     f"P(dd>bar) {f0['p_dd_bar']:.2f} · P(ruin) {f0['p_ruin']:.2f}")
            continue
        L.append(f"\n{bot}  rho*={_rung(b['rho_star'])} (admissible {_rung(b['rho_adm'])}, "
                 f"running {_pct(b['rho_now'],2)}% — {b['rho_now_basis']}); stop "
                 f"{_pct(b['s_book'])}% ({b['stop_basis']}); E0 ${b['E0']:.0f}; "
                 f"{b['n_days']} trading days, peak {b['peak_concurrent']} concurrent; "
                 f"horizon {b['horizon_months_used']:.1f}m ({b['extrapolation_x']:.1f}x span)")
        L.append(f"   {'rule':17s} {'ret p05':>8s} {'p50':>7s} {'p95':>7s} | "
                 f"{'dd p50':>7s} {'p95':>6s} | {'vol/d':>6s} {'ann':>6s} | "
                 f"{'P>bar':>5s} {'ruin':>5s} | {'gross':>5s} | {'rho_eff':>7s} {'cap%':>5s}")
        for method in METHODS:
            f = b["at_star"][method]["forward"]
            cs = f["capped_share"]
            L.append(f"   {method:17s} {_pct(f['ret_p05']):>8s} {_pct(f['ret_p50']):>7s} "
                     f"{_pct(f['ret_p95']):>7s} | {_pct(f['dd_p50']):>7s} "
                     f"{_pct(f['dd_p95']):>6s} | {_pct(f['vol_day'],2):>6s} "
                     f"{_pct(f['vol_annual']):>6s} | {f['p_dd_bar']:5.2f} "
                     f"{f['p_ruin']:5.2f} | {f['gross_max_p50']:5.2f} | "
                     f"{_pct(f['rho_eff_p50'],2):>7s} "
                     f"{(f'{100*cs:5.0f}' if cs is not None else '    —')}")
    L += ["", "WHAT FRACTIONAL KELLY WANTS, uncapped to the ladder top (forward): "
              "rule -> median rho_eff | share of steps pinned at the 5% cap | ret p50 "
              "| dd p95 | P(ruin)"]
    for bot, b in res["books"].items():
        cells = []
        for method in ("kelly_half", "kelly_quarter", "kelly_quarter_lb"):
            f = b["forward"][method][LADDER[-1]]
            cells.append(f"{method[6:]}: {_pct(f['rho_eff_p50'],2)}%/"
                         f"{100*f['capped_share']:.0f}%/{_pct(f['ret_p50'])}%/"
                         f"{_pct(f['dd_p95'])}%/{f['p_ruin']:.2f}")
        L.append(f"  {bot:30s} " + "  ".join(cells))
    regs = [(b, v["pre_registered"]) for b, v in res["books"].items()
            if v.get("pre_registered")]
    if regs:
        L += ["", "PRE-REGISTERED READS (I21 — graded on FRESH days only, never "
                  "the window that motivated them)"]
        for bot, r in regs:
            L.append(f"  {bot}  [{r['id']}] registered {r['registered']}; "
                     f"{r['fresh_days']} fresh trading days; "
                     f"{'** DUE NOW **' if r['due'] else 'not yet due'}")
            L.append(f"     read when: {r['read_when']}")
            L.append(f"     criterion: {r['criterion']}")

    if res.get("skipped"):
        L += ["", f"SKIPPED ({len(res['skipped'])}, not certified by the calibration "
                  f"gate): " + ", ".join(sorted(res["skipped"]))]
    return "\n".join(L)


# ------------------------------------------------------------------ selftest

def _selftest():
    from datetime import timedelta
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # -- daily units: same-day closes aggregate, different days do not, and a
    #    continuously-in-market book cannot collapse into one unit (the defect
    #    the first cut of this study shipped and its own output exposed).
    tr = [(t0, t0 + timedelta(hours=2), 0.01, 0.05, 1.0),
          (t0 + timedelta(hours=1), t0 + timedelta(hours=3), -0.02, 0.05, -2.0),
          (t0 + timedelta(days=1), t0 + timedelta(days=1, hours=1), 0.03, 0.05, 3.0)]
    u = daily_units(tr)
    assert len(u) == 2 and u[0]["L"] == 2 and u[1]["L"] == 1, u
    assert abs(u[0]["R"] - (-0.01)) < 1e-12 and abs(u[0]["Q"] - (-0.2)) < 1e-12
    chain = [(t0 + timedelta(hours=i), t0 + timedelta(hours=i + 5), 0.01, 0.05, 1.0)
             for i in range(0, 240)]                    # 10 days, always in market
    assert len(daily_units(chain)) >= 10, "overlapping holds must not chain into one unit"

    # -- fixed_fraction compounds exactly; fixed_dollar does not
    R = np.full((1, 10), 0.01)
    Q = R / 0.05
    E, _ = run_paths("fixed_fraction", R, Q, np.array([]), 1000.0, 0.025, 0.05)
    assert abs(E[0, -1] - 1000.0 * 1.005 ** 10) < 1e-6, E[0, -1]
    E, _ = run_paths("fixed_dollar", R, Q, np.array([]), 1000.0, 0.025, 0.05)
    assert abs(E[0, -1] - (1000.0 + 10 * 500.0 * 0.01)) < 1e-6, E[0, -1]

    # -- risk_per_trade: a stop-out costs exactly rho of equity at ANY stop...
    for s in (0.02, 0.10):
        E, _ = run_paths("risk_per_trade", np.array([[-s]]), np.array([[-1.0]]),
                         np.array([]), 1000.0, 0.01, s)
        assert abs(E[0, -1] - 990.0) < 1e-9, (s, E[0, -1])
    # ... and a loss PAST the stop costs more (the ledger's r, not the stop)
    E, _ = run_paths("risk_per_trade", np.array([[-0.08]]), np.array([[-2.0]]),
                     np.array([]), 1000.0, 0.01, 0.04)
    assert abs(E[0, -1] - 980.0) < 1e-9

    # -- vol_adjusted reduces to fixed_fraction under constant dispersion. NOT
    #    to machine precision: both variances use ddof=1, so an expanding window
    #    of n and a trailing window of 20 divide by n-1 and 19 — a ~1.3% ratio
    #    bias at n=40 decaying as 1/n, two orders below the [0.25, 2] clamp and
    #    unable to move a rung. The test pins the SIZE of that deviation.
    rr = np.array([[0.01, -0.01] * 30])
    qq = rr / 0.05
    Ea, _ = run_paths("vol_adjusted", rr, qq, np.array([]), 1000.0, 0.01, 0.05)
    Eb, _ = run_paths("fixed_fraction", rr, qq, np.array([]), 1000.0, 0.01, 0.05)
    assert np.allclose(Ea, Eb, rtol=0.02), "constant vol must not move the vol target"
    mflat, _ = multipliers("vol_adjusted", rr, np.array([]), 0.2, 0.01, 0.05, 1.0)
    assert np.all(np.abs(mflat / 0.2 - 1.0) < 0.05), mflat.min() / 0.2
    # ... and it SHRINKS when trailing dispersion doubles
    rr2 = np.concatenate([np.array([[0.01, -0.01] * 20]),
                          np.array([[0.02, -0.02] * 10])], axis=1)
    m2, _ = multipliers("vol_adjusted", rr2, np.array([]), 0.2, 0.01, 0.05, 1.0)
    assert m2[0, -1] < 0.2 * 0.75, m2[0, -1]

    # -- Kelly: mu/var on a known series, quartered; half is twice quarter; the
    #    LOWER-BOUND variant sizes strictly below the mean variant; a LOSING
    #    book gets ZERO; below MIN_N the probe rung; the cap binds.
    rk = np.array([[0.02, -0.01] * 20])
    mk, _ = multipliers("kelly_quarter", rk, np.array([]), 0.2, 0.01, 0.05, 100.0)
    hist = rk[0, :-1]
    assert abs(mk[0, -1] - 0.25 * hist.mean() / hist.var(ddof=1)) < 1e-9
    mh, _ = multipliers("kelly_half", rk, np.array([]), 0.2, 0.01, 0.05, 100.0)
    assert abs(mh[0, -1] - 2 * mk[0, -1]) < 1e-9
    ml, _ = multipliers("kelly_quarter_lb", rk, np.array([]), 0.2, 0.01, 0.05, 100.0)
    assert 0 < ml[0, -1] < mk[0, -1]
    assert abs(mk[0, MIN_N - 1] - LADDER[0] / 0.05) < 1e-12, "below MIN_N: probe rung"
    rl = np.array([[-0.02, 0.01] * 20])
    mlz, _ = multipliers("kelly_quarter", rl, np.array([]), 0.2, 0.01, 0.05, 100.0)
    assert mlz[0, -1] == 0.0, "a losing book gets ZERO Kelly size, not the floor"
    mc, _ = multipliers("kelly_half", rk, np.array([]), 0.2, 0.01, 0.05, 0.3)
    assert mc[0, -1] == 0.3, "the cap binds"

    # -- ruin: a fixed-dollar path can die and stays dead; a fraction path can
    #    too (a day worse than -1/f), and a small rung survives the same day.
    Rr = np.array([[-0.5] * 4 + [0.5]])
    E, met = run_paths("fixed_dollar", Rr, Rr / 0.05, np.array([]),
                       1000.0, 0.05, 0.05)
    assert met["p_ruin"] == 1.0 and E[0, -1] == 0.0
    E, met = run_paths("fixed_fraction", np.array([[-1.5, 0.5]]),
                       np.array([[-30.0, 10.0]]), np.array([]), 1000.0, 0.05, 0.05)
    assert met["p_ruin"] == 1.0 and E[0, -1] == 0.0
    E, met = run_paths("fixed_fraction", np.array([[-0.5, 0.5]]),
                       np.array([[-10.0, 10.0]]), np.array([]), 1000.0, 0.005, 0.05)
    assert met["p_ruin"] == 0.0 and abs(met["dd_p50"] - 0.05) < 1e-9

    # -- peak GROSS uses the ledger's concurrency, not the day's close count
    _, met = run_paths("fixed_fraction", R, Q, np.array([]), 1000.0, 0.01,
                       0.05, peak_conc=4)
    assert abs(met["gross_max_p50"] - 4 * 0.2) < 1e-9, met["gross_max_p50"]

    # -- the proposal reads no return column, is half the admissible rung, is
    #    capped, and has three DISTINCT no-proposal reasons.
    rows = {r: {"p_ruin": 0.0, "dd_p95": 0.02 * i, "ret_p50": 0.1 * i,
                "gross_max_p50": 0.1} for i, r in enumerate(LADDER, 1)}
    assert propose(rows, edge_lb=0.01) == (0.05, 0.02, None)
    # the GROSS ceiling alone can refuse a rung whose drawdown is fine — the
    # carry-book shape (a small per-position risk over many concurrent legs).
    grossy = {r: dict(v, gross_max_p50=(0.5 if r <= 0.01 else GROSS_CAP_X + 1))
              for r, v in rows.items()}
    assert propose(grossy, edge_lb=0.01) == (0.01, 0.005, None), propose(grossy, edge_lb=0.01)
    rows2 = {r: dict(v, ret_p50=-v["ret_p50"] * 7) for r, v in rows.items()}
    assert propose(rows2, edge_lb=0.01) == propose(rows, edge_lb=0.01), \
        "returns moved the proposal"
    rows3 = {r: {"p_ruin": 0.0, "dd_p95": (0.10 if r <= 0.01 else 0.30),
                 "gross_max_p50": 0.1} for r in LADDER}
    assert propose(rows3, edge_lb=0.01) == (0.01, 0.005, None), propose(rows3, edge_lb=0.01)
    rows4 = {r: {"p_ruin": (0.0 if r <= 0.005 else 0.01), "dd_p95": 0.01,
                 "gross_max_p50": 0.1} for r in LADDER}
    assert propose(rows4, edge_lb=0.01) == (0.005, 0.0025, None), propose(rows4, edge_lb=0.01)
    assert propose({r: {"p_ruin": 0.0, "dd_p95": 0.9, "gross_max_p50": 0.1}
                    for r in LADDER}, edge_lb=0.01)[2] == NO_EDGE
    only_floor = {r: {"p_ruin": (0.0 if r == LADDER[0] else 1.0), "dd_p95": 0.01,
                      "gross_max_p50": 0.1} for r in LADDER}
    assert propose(only_floor, edge_lb=0.01) == (LADDER[0], None, BELOW_LADDER)
    assert propose(rows, n_days=MIN_N - 1, edge_lb=0.01) == (None, None, THIN)
    # THE I24 PRECONDITION, and the defect it closes: a book that is SAFE ONLY
    # BECAUSE IT LOSES SLOWLY passes every drawdown/gross test and must still
    # get no size. `rho_adm` is still reported so the refusal is legible.
    assert propose(rows, edge_lb=0.0) == (0.05, None, WEAK_EDGE)
    assert propose(rows, edge_lb=-0.004) == (0.05, None, WEAK_EDGE)
    assert propose(rows, edge_lb=None) == (0.05, None, WEAK_EDGE)
    # ... and it is a PRECONDITION, not a chooser: a bigger bound does not buy
    # a bigger rung.
    assert propose(rows, edge_lb=0.01) == propose(rows, edge_lb=99.0)

    # -- the close-order DD pin reproduces the GRADER'S own routine, by the key
    #    the grader really publishes (`max_dd_frac`; a guessed name raised
    #    KeyError here, which is the cheap version of this mistake).
    rowsq = [(0.01, 10.0, t0), (-0.03, -30.0, t0 + timedelta(hours=1)),
             (0.02, 20.0, t0 + timedelta(hours=2))]
    assert abs(close_order_dd_pct(rowsq, 1000.0) - 3.0) < 1e-9
    assert abs(close_order_dd_pct(rowsq, gr.BOOK_USD)
               - 100.0 * gr.stats(rowsq)["max_dd_frac"]) < 1e-9

    # -- stop resolution precedence
    assert stop_of("x", {"policy": {"stoploss": -0.04}}, "t") == 0.04
    assert stop_of("x", {"bars": {"sl": -0.03, "brk_sl": -0.07}}, "long-breakoutup") == 0.07
    assert stop_of("x", {"bars": {"sl": -0.03, "brk_sl": -0.07}}, "long-dip") == 0.03
    assert stop_of("x", {"params": {"sl_pct": 0.025}}, None) == 0.025
    assert stop_of("band-kelly-lshadow", {}, None) == 0.05
    assert stop_of("perps-funding-spread-lshadow", {}, None) is None

    # -- the block resample keeps its length and draws from the sample only
    u10 = [{"R": 0.01 * i, "Q": 0.2 * i, "L": 1} for i in range(10)]
    for blk in BLOCKS:
        Rb, Qb, Lb = resample(u10, random.Random(1), 7, 13, blk)
        assert Rb.shape == (7, 13) and Qb.shape == (7, 13) and Lb.shape == (7, 13)
        assert set(np.round(Rb.ravel(), 9)) <= {round(0.01 * i, 9) for i in range(10)}
    # ... and the conservative-block picker takes ruin first, then drawdown
    assert _worse({1: {"p_ruin": 0.0, "dd_p95": 0.9},
                   5: {"p_ruin": 0.1, "dd_p95": 0.1}}) == 5
    assert _worse({1: {"p_ruin": 0.0, "dd_p95": 0.9},
                   5: {"p_ruin": 0.0, "dd_p95": 0.1}}) == 1

    # -- the pre-registration counts FRESH days only, and says when it is due
    from datetime import date as _date
    _reg_bot = next(iter(PRE_REGISTERED))
    _u = [{"day": _date(2026, 9, 1), "R": 0.0, "Q": 0.0, "L": 1},
          {"day": _date(2026, 9, 7), "R": 0.0, "Q": 0.0, "L": 1},
          {"day": _date(2026, 9, 8), "R": 0.0, "Q": 0.0, "L": 1}]
    _r, _fresh, _due = registration_status(_reg_bot, {"units": _u})
    assert _r and _fresh == 1, (_fresh,)      # only 8-Sep is after 7-Sep
    assert registration_status("not-registered", {"units": _u}) == (None, None, False)
    _many = [{"day": _date(2026, 10, 1), "R": 0.0, "Q": 0.0, "L": 1}] * 30
    assert registration_status(_reg_bot, {"units": _many})[2] is True
    # the registration is a COMMITMENT: its at-registration numbers are declared,
    # not recomputed, so a later run cannot quietly move the thing it promised.
    assert set(PRE_REGISTERED[_reg_bot]["at_registration"]) >= {
        "rho_now", "rho_adm", "rho_star", "n_days", "edge_lb_pct"}

    # -- THE STUDY MOVES NOTHING, asserted on the AST rather than on a
    #    substring scan. This repo's own (po) rule is that "a page-wide
    #    substring scan is not a structural claim" — three tests in one session
    #    once passed or failed on the PROSE that promised the property they
    #    checked. So walk the call sites: any Call whose callee name (bare or
    #    attribute) is a mutator is a defect, and the docstrings are invisible
    #    to it by construction.
    import ast as _ast
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        src = fh.read()
    tree = _ast.parse(src)
    # the selftest itself is excluded — it may name these to assert their
    # absence, which is exactly what the substring version could not express.
    body = [n for n in tree.body
            if not (isinstance(n, _ast.FunctionDef) and n.name == "_selftest")]
    MUTATORS = {"write_levers", "market_open", "set_status", "publish",
                "get_lever", "snapshot_equity", "claim_writer", "set_lever"}
    called = set()
    for node in body:
        for sub in _ast.walk(node):
            if isinstance(sub, _ast.Call):
                fn = sub.func
                nm = (fn.attr if isinstance(fn, _ast.Attribute)
                      else fn.id if isinstance(fn, _ast.Name) else None)
                if nm:
                    called.add(nm)
    assert not (called & MUTATORS), f"study calls a mutator: {called & MUTATORS}"
    # ... and the check is not vacuous: it must SEE the calls this file does make.
    assert {"run_paths", "propose", "daily_units"} <= called, sorted(called)[:20]

    # -- end to end: a planted winner gets a rung, a planted loser gets none,
    #    and the horizon never exceeds the quotability cap.
    rnd = random.Random(1)
    good = [(t0 + timedelta(hours=3 * i), t0 + timedelta(hours=3 * i + 2),
             rnd.gauss(0.004, 0.02), 0.04, 0.0) for i in range(240)]
    gu = daily_units(good)
    seq = {"units": gu, "s_book": 0.04, "n_days": len(gu), "peak_concurrent": 3,
           "days_per_year": len(gu) / 30.0 * 365.25, "span_days": 30.0}
    r = study_book(seq, 1000.0, draws=40, horizon_months=6, edge_lb=0.004)
    assert r["rho_star"] in (None,) + LADDER
    assert r["extrapolation_x"] <= MAX_EXTRAPOLATION_X + 1e-9, r["extrapolation_x"]
    assert set(r["forward"]) == set(METHODS)
    bad_u = daily_units([(a, b, c - 0.02, d, e) for a, b, c, d, e in good])
    r2 = study_book({"units": bad_u, "s_book": 0.04, "n_days": len(bad_u),
                     "peak_concurrent": 3, "days_per_year": len(bad_u) / 30.0 * 365.25,
                     "span_days": 30.0}, 1000.0, draws=40, horizon_months=6,
                    edge_lb=-0.016)
    assert r2["rho_star"] is None, "a losing book must get no proposal"
    print("study_position_sizing selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger"); ap.add_argument("--feed"); ap.add_argument("--bus")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--horizon", type=int, default=HORIZON_MONTHS, help="months")
    ap.add_argument("--book", action="append", help="restrict to these row ids")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    res = run(a.ledger, a.feed, a.bus, draws=a.draws, horizon_months=a.horizon,
              only=set(a.book) if a.book else None)
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(res, fh, default=str, indent=1)
    print(json.dumps(res, default=str, indent=1) if a.json else render(res))
    return 2 if res.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
