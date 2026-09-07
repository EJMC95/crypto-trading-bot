#!/usr/bin/env python3
"""scripts/baseline_snapshot.py — THE BASELINE, SAVED BEFORE ANYTHING CHANGES.

    python3 scripts/baseline_snapshot.py --ledger t.json --feed p.json --bus b.json \
        --out BASELINE_<date>.json --md BASELINE_<date>.md
    python3 scripts/baseline_snapshot.py --selftest

WHY THIS EXISTS (2026-09-07). An audit that proposes changes needs a number to
be judged against later, and this fleet had every INPUT to that number and no
artefact holding it: `golive_readiness` publishes six pass/fail bars, `edge_audit`
publishes shape, `fleet_allocation` publishes a claim — but nobody had written
down "total return, annualised return, net after fees, win rate, avg win, avg
loss" per book, dated, reproducible, in one place. So a later "did it help?"
had nowhere to start. This is that starting line.

IT RE-IMPLEMENTS NOTHING, and that is the point ((hj) — a second copy of a rule
is a second rule). Every statistic here is DERIVED from `edge_audit.run()`,
which in turn imports `golive_readiness` for the era, the phantom filter, the
retired-sleeve drop, `stats`, `cluster_se`, and `fleet_allocation.t_crit`. The
only arithmetic this module owns is the four ratios the audit asked for that
nobody had named yet, and each one is a division of two numbers that already
existed.

THE CALIBRATION GATE IS INHERITED, NOT REBUILT. `edge_audit` REFUSES when its
sample cannot reproduce the live `golive-readiness` grade. This module refuses
with it — a baseline computed off a sample the fleet's own grader disowns is
worse than no baseline, because it will be quoted for months. Fail-CLOSED.

THREE HONESTY RULES BAKED IN, because each one is a way a baseline lies:

  1. **ANNUALISATION IS FLAGGED, NEVER SILENT.** A book with a 9-day span has
     no annual return; it has a 9-day return and an extrapolation. Every row
     carries `span_days` and `extrapolation_x` (365/span), and any row above
     `EXTRAP_WARN_X` is marked. The fleet has retired books on exactly this
     error in the other direction (🧙 Schwager's ~40-month decidability).

  2. **SIMPLE AND COMPOUNDED ARE BOTH SHOWN.** These books trade a FIXED clip,
     not a fraction of equity, so compounding the realised return is the wrong
     model and reads high. Simple (`usd_per_day x 365 / book_usd`) is the
     honest headline; compounded is reported beside it so nobody re-derives a
     bigger number later and thinks they found something.

  3. **LIVE AND PAPER ARE NEVER POOLED.** Cohorts are separated at every
     aggregate. Paper cannot risk real money and real money cannot risk paper;
     one number for both is a category error in both directions ((wp)).

WHAT "NET AFTER FEES" MEANS HERE, stated because the phrase is ambiguous on a
zero-fee venue. Lighter charges **zero** taker/maker fee (measured across all
active books), so the venue fee term is 0.00 and `realised_usd` is ALREADY net
of the only real cost — the crossed spread, which lands inside the shadow
broker's book-walked fill price. `net_after_fees_usd` therefore equals
`realised_usd`, and is reported as such rather than silently omitted. The
SENSITIVITY is what carries information, so every row also gets
`net_at_measured_cost_usd`: realised minus `n x MEASURED_RT_BPS x clip`, i.e.
what the book would have earned had it paid the fleet's own measured 17.49bps
round trip on top. A book that flips sign under that stress has an edge thinner
than the fleet's own execution noise.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import edge_audit  # noqa: E402  — the calibrated owner; never re-derive its stats

#: Identity imports, not copies — the same parser and the same symbol
#: normaliser the audit itself used to build the rows being sliced. A second
#: `base_symbol` here would put kBONK and 1000BONK in different buckets, which
#: is exactly the defect (yk) found in the live fleet.
_ts_of = edge_audit._ts
_base_sym = edge_audit.base_symbol

#: A span this short makes an annual figure an extrapolation, not a measurement.
#: 30 days is the go-live window bar — below it the fleet does not consider a
#: book graded at all, so it is the natural line.
EXTRAP_WARN_DAYS = 30.0

#: Rows whose `extra.venue` says real money. Derived from the feed, never typed
#: — `scripts/fleet_books.py` makes the same point: which rows are live is a
#: property of the PAYLOAD.
LIVE_VENUES = ("lighter_live",)


#: Realised-vol split point. The MEDIAN of the window's own hourly vol, so the
#: two buckets are equal-sized BY CONSTRUCTION and neither is a rare-event
#: bucket whose `n` decides nothing. Never a hardcoded bps number: this venue's
#: vol level is not stable across months and a fixed bar silently rebalances
#: the split every time the tape changes.
VOL_SPLIT_Q = 0.50

#: Trend regime on the majors index: EMA fast/slow on 1h closes. 50/200 is the
#: fleet's own convention (every family carrier reads e50/e200), so the split
#: agrees with what the books themselves call an uptrend rather than inventing
#: a second definition of the same word.
EMA_FAST, EMA_SLOW = 50, 200


def _ema(xs, n):
    k = 2.0 / (n + 1.0)
    out, e = [], None
    for x in xs:
        e = x if e is None else (x * k + e * (1 - k))
        out.append(e)
    return out


def build_regimes(majors):
    """hour_epoch -> {trend, vol, mkt_ret_1h} from an equal-weight majors index.

    `majors` is {symbol: {epoch_sec: close}}. The index is equal-weighted in
    RETURN space, not price space — a price-weighted basket of BTC and SOL is
    a BTC basket, and the regime this labels is the market's, not BTC's.

    Fail-CLOSED: too little history returns {} and every downstream split is
    reported as unavailable rather than computed on a stub. A regime label is
    the input to a decision about real money; a fabricated one is worse than
    none ((yq): unmeasured is NULL, never a convenient default).
    """
    if not majors:
        return {}
    hours = sorted(set.intersection(*(set(v) for v in majors.values())) if majors else [])
    if len(hours) < EMA_SLOW + 2:
        return {}
    rets = []
    for i, h in enumerate(hours):
        if i == 0:
            rets.append(0.0); continue
        per = []
        for sym, ser in majors.items():
            a, b = ser.get(hours[i - 1]), ser.get(h)
            if a and b:
                per.append(b / a - 1.0)
        rets.append(sum(per) / len(per) if per else 0.0)
    idx, lvl = [], 100.0
    for r in rets:
        lvl *= (1.0 + r); idx.append(lvl)
    ef, es = _ema(idx, EMA_FAST), _ema(idx, EMA_SLOW)
    # realised vol: rolling 24h stdev of the index return, split at its own median
    vols = []
    for i in range(len(rets)):
        w = rets[max(0, i - 23):i + 1]
        m = sum(w) / len(w)
        vols.append((sum((x - m) ** 2 for x in w) / len(w)) ** 0.5)
    ranked = sorted(v for v in vols[EMA_SLOW:] if v is not None)
    vsplit = ranked[int(len(ranked) * VOL_SPLIT_Q)] if ranked else None
    out = {}
    for i, h in enumerate(hours):
        if i < EMA_SLOW:
            continue                      # EMA warmup: no claim, not a guess
        out[h] = {"trend": "bull" if ef[i] > es[i] else "bear",
                  "vol": None if vsplit is None else ("high_vol" if vols[i] >= vsplit else "low_vol"),
                  "idx": idx[i], "ret_1h": rets[i]}
    return out


def regime_at(ts, regimes):
    """The regime label for the hour a trade OPENED. None when uncovered."""
    if not regimes or ts is None:
        return None
    h = int(ts.timestamp()) // 3600 * 3600
    return regimes.get(h)


def market_move(opened, closed, regimes):
    """Index return over the trade's OWN holding window — the direct answer to
    'winning vs losing market'. Contemporaneous by design: it asks what the
    market did WHILE the book held, not what it did before the book decided."""
    if not regimes or opened is None or closed is None:
        return None
    a = regimes.get(int(opened.timestamp()) // 3600 * 3600)
    b = regimes.get(int(closed.timestamp()) // 3600 * 3600)
    if not a or not b or not a.get("idx"):
        return None
    return b["idx"] / a["idx"] - 1.0



#: The LIGHTER-ONLY cut (2026-07-17, "i only want things running on lighter").
#: Before it the fleet traded Kraken/Hyperliquid/CEX spot, so pooling those
#: closes into a Lighter result mixes venues — and three legacy books
#: (perps-donchian-breakout +$272, event-listing-sniper +$206, perps-rsi-meanrev
#: +$69) would flatter it by ~$550 of P&L earned somewhere we no longer trade.
LIGHTER_ONLY_CUT = _dt.datetime(2026, 7, 17, tzinfo=_dt.timezone.utc)


def survivorship(trades, living, cut=LIGHTER_ONLY_CUT):
    """What the fleet earned INCLUDING the books it retired.

    THE BIAS THIS MEASURES, and it is the largest single distortion in the
    fleet's own reporting. Every instrument here grades LIVING books:
    `golive_readiness.roster` admits publishers, `fleet_allocation` ranks
    living rows, `edge_audit` audits the published grade, and this module's own
    cohort totals do the same. Retirement is decided per book on a measured
    exclusion (I17), which is correct — but a loser leaving the sample the day
    it is retired means the SURVIVORS' SUM IS NOT THE FLEET'S RESULT, and
    nothing in the tree had ever computed the difference.

    Scoped to the Lighter-only era on purpose: a pre-cut close is a different
    venue, and including it would replace one bias with another.

    Returns living / retired / true totals. No verdict — the retirements were
    individually justified and this does not reopen them. What it refuses to
    let happen is the survivors' number being quoted as the fleet's.
    """
    liv = {"n": 0, "usd": 0.0, "books": set()}
    ret = {"n": 0, "usd": 0.0, "books": set()}
    for r in trades:
        c = _ts_of(r.get("closed_at"))
        if c is None or c < cut:
            continue
        bot = r.get("bot")
        d = liv if bot in living else ret
        d["n"] += 1
        d["usd"] += float(r.get("pnl_abs") or 0.0)
        d["books"].add(bot)
    out = {"cut": cut.date().isoformat()}
    for name, d in (("living", liv), ("retired", ret)):
        out[name] = {"n_books": len(d["books"]), "n_closes": d["n"],
                     "net_usd": round(d["usd"], 2)}
    out["true_total_usd"] = round(liv["usd"] + ret["usd"], 2)
    out["survivor_overstatement_usd"] = round(liv["usd"] - out["true_total_usd"], 2)
    out["survivor_overstatement_x"] = (round(liv["usd"] / out["true_total_usd"], 2)
                                       if out["true_total_usd"] else None)
    return out


def _cohort(bot, feed_rows):
    v = (feed_rows.get(bot) or {}).get("venue")
    return "live" if v in LIVE_VENUES else "shadow"


def _feed_index(res_feed):
    """bot -> {venue, equity, status} from the /pnl.json dump."""
    out = {}
    for r in (res_feed or []):
        ex = r.get("extra") or {}
        out[r.get("bot")] = {"venue": ex.get("venue"),
                             "equity": r.get("equity"),
                             "status": r.get("status"),
                             # lifetime, INCLUDING open MTM and capital
                             # adjustments — carried only for reconciliation
                             # against the era-scoped realised figure, never
                             # summed into a cohort total.
                             "pnl_abs": r.get("pnl_abs")}
    return out


def derive(a, book_usd):
    """The four ratios the audit named, from numbers edge_audit already has.

    Returns None for anything the inputs cannot support — a missing span or a
    zero book is "unknown", never 0.0 ((qq)/(ye): unmeasured is NULL).
    """
    realised = a.get("realised_usd")
    span = a.get("span_days")
    n = a.get("n") or 0
    out = {
        "n": n,
        "book_usd": book_usd,
        "span_days": span,
        # --- return ---------------------------------------------------------
        "total_return_pct": None,
        "ann_return_simple_pct": None,
        "ann_return_compounded_pct": None,
        "extrapolation_x": None,
        "annualisation_is_extrapolation": None,
        # --- profit ---------------------------------------------------------
        "net_after_fees_usd": realised,       # venue fee is 0.0; see module doc
        "venue_fee_usd": 0.0,
        "net_at_measured_cost_usd": None,
        "flips_sign_under_measured_cost": None,
        # --- shape ----------------------------------------------------------
        "win_rate_pct": (a["win_rate"] * 100.0) if a.get("win_rate") is not None else None,
        "n_win": a.get("n_win"),
        "n_loss": a.get("n_loss"),
        "avg_win_usd": a.get("avg_win_usd"),
        "avg_loss_usd": a.get("avg_loss_usd"),
        "avg_win_pct": (a["avg_win_pct"] * 100.0) if a.get("avg_win_pct") is not None else None,
        "avg_loss_pct": (a["avg_loss_pct"] * 100.0) if a.get("avg_loss_pct") is not None else None,
        "win_loss_ratio": None,
        "profit_factor": a.get("profit_factor"),
        "expectancy_usd": a.get("expectancy_usd"),
    }
    if realised is not None and book_usd:
        out["total_return_pct"] = 100.0 * realised / book_usd
    if span and span > 0 and book_usd:
        per_day = (a.get("usd_per_day")
                   if a.get("usd_per_day") is not None
                   else (realised / span if realised is not None else None))
        if per_day is not None:
            out["ann_return_simple_pct"] = 100.0 * per_day * 365.0 / book_usd
        if realised is not None:
            g = 1.0 + realised / book_usd
            if g > 0:                     # a book that lost its whole stake has
                out["ann_return_compounded_pct"] = (  # no compounded rate
                    100.0 * (g ** (365.0 / span) - 1.0))
        out["extrapolation_x"] = 365.0 / span
        out["annualisation_is_extrapolation"] = span < EXTRAP_WARN_DAYS
    # cost stress: what the fleet's OWN measured round trip would have taken
    clip = (a.get("monte_carlo") or {}).get("clip_usd")
    if clip and n:
        drag = n * (edge_audit.MEASURED_RT_BPS / 1e4) * clip
        out["measured_rt_bps"] = edge_audit.MEASURED_RT_BPS
        out["cost_drag_usd"] = -drag
        if realised is not None:
            out["net_at_measured_cost_usd"] = realised - drag
            out["flips_sign_under_measured_cost"] = (
                realised > 0 and (realised - drag) <= 0)
    aw, al = a.get("avg_win_usd"), a.get("avg_loss_usd")
    if aw and al:
        out["win_loss_ratio"] = abs(aw / al)
    return out



def _notional(raw):
    """Implied position notional = |pnl_abs / pnl_pct|.

    DERIVED, not read, and that is deliberate: `size` is present on only 878 of
    4,311 ledger rows (20%) while `pnl_pct` is present on essentially all of
    them, so reading `size` would compute turnover on a fifth of the fleet and
    silently call it the fleet. The identity holds for every book here because
    `pnl_pct` IS `pnl_abs / notional` at the publish site. Returns None when
    `pnl_pct` is zero or missing — an exact-scratch trade has no recoverable
    notional, and inventing one would inflate turnover on the books that
    scratch most.
    """
    a, p = raw.get("pnl_abs"), raw.get("pnl_pct")
    if not isinstance(a, (int, float)) or not isinstance(p, (int, float)) or p == 0:
        return None
    return abs(a / p)


def trade_metrics(rows, book_usd, regimes=None):
    """Turnover, exposure, holding time, and the per-asset/month/regime slices.

    EXPOSURE is time-weighted capital: sum(notional x hours_held) / (book x
    window_hours). It answers "how much of the book was at risk on average",
    which is the number that makes a return comparable across books — a 2%
    return at 10% average exposure and a 2% return at 90% are not the same
    result, and nothing in this fleet had ever printed the denominator.

    Every slice is a plain mean with its own n. NO significance is claimed here
    and none should be read: `golive_readiness.stats` and `winners_docket` own
    that judgement, and a per-asset table with 300+ buckets is a multiplicity
    trap ((yl)/I21) if any single cell is quoted as evidence. These are
    DESCRIPTIVE and labelled as such.
    """
    out = {"n": len(rows)}
    if not rows:
        return out
    hold_h, notion, expo, missing_notional = [], [], 0.0, 0
    first, last = None, None
    for q in rows:
        closed, opened = q[2], _ts_of(q[3])
        if opened is not None:
            h = (closed - opened).total_seconds() / 3600.0
            if h >= 0:
                hold_h.append(h)
        first = closed if first is None or closed < first else first
        last = closed if last is None or closed > last else last
        nv = _notional(q[7])
        if nv is None:
            missing_notional += 1
        else:
            notion.append(nv)
            if opened is not None:
                expo += nv * max(0.0, (closed - opened).total_seconds() / 3600.0)
    span_h = ((last - first).total_seconds() / 3600.0) if (first and last) else None
    out["avg_hold_h"] = (sum(hold_h) / len(hold_h)) if hold_h else None
    out["median_hold_h"] = (sorted(hold_h)[len(hold_h) // 2]) if hold_h else None
    out["gross_notional_usd"] = sum(notion) if notion else None
    out["notional_coverage"] = (len(notion) / len(rows)) if rows else None
    out["turnover_x"] = (sum(notion) / book_usd) if (notion and book_usd) else None
    # THE DEPLOYED CLIP, not the declared one. A book's published `caps.clip_usd`
    # is the BASE; `brain_clip` x drawdown-scale x `allocation_scale` all
    # multiply afterwards, so the number on the row is not the number at risk.
    # Measured here: 🌾 carry declares $80 and deploys a median $300 (3.75x),
    # 🪁 kelly declares $80 and deploys $250. Nothing was wrong — but reading
    # the cap as the exposure understates both books by the whole sizing stack.
    out["implied_clip_median"] = (sorted(notion)[len(notion) // 2]) if notion else None
    out["avg_exposure_frac"] = ((expo / (book_usd * span_h))
                                if (span_h and span_h > 0 and book_usd) else None)
    out["trades_per_day"] = (len(rows) / (span_h / 24.0)) if (span_h and span_h > 0) else None
    out["rows_without_notional"] = missing_notional

    def _slice(keyfn):
        b = {}
        for q in rows:
            k = keyfn(q)
            if k is None:
                continue
            d = b.setdefault(k, {"n": 0, "usd": 0.0, "pct_sum": 0.0})
            d["n"] += 1; d["usd"] += q[1]; d["pct_sum"] += q[0]
        return {k: {"n": v["n"], "net_usd": round(v["usd"], 2),
                    "mean_pct": round(100.0 * v["pct_sum"] / v["n"], 4)}
                for k, v in sorted(b.items(), key=lambda kv: -kv[1]["n"])}

    out["by_asset"] = _slice(lambda q: _base_sym(q[6]))
    out["by_month"] = _slice(lambda q: q[2].strftime("%Y-%m"))
    out["by_side"] = _slice(lambda q: (q[7].get("side") or "?"))
    if regimes:
        out["by_trend"] = _slice(lambda q: (regime_at(_ts_of(q[3]), regimes) or {}).get("trend"))
        out["by_vol"] = _slice(lambda q: (regime_at(_ts_of(q[3]), regimes) or {}).get("vol"))

        def _mkt(q):
            m = market_move(_ts_of(q[3]), q[2], regimes)
            return None if m is None else ("mkt_up" if m > 0 else "mkt_down")
        out["by_market"] = _slice(_mkt)
        cov = sum(1 for q in rows if regime_at(_ts_of(q[3]), regimes))
        out["regime_coverage"] = cov / len(rows)
    else:
        out["regime_unavailable"] = "no majors index supplied — split withheld"
    return out


def build(res, shaped=None, regimes=None, all_trades=None, feed_bots=None):
    """Baseline rows + cohort aggregates from an edge_audit result."""
    if res.get("refused"):
        # I8 — a refusal must name the object the reader can act on. edge_audit's
        # `refused` is a bare bool; the per-book disagreement lives in
        # `calibration`, so carry it rather than printing "REFUSED: True".
        return {"refused": res["refused"],
                "calibration": res.get("calibration") or
                               "no published golive-readiness grade to calibrate "
                               "against (dark or empty bus) — fail-closed"}
    feed = _feed_index(res.get("_feed_rows"))
    rows, cohorts = {}, {}
    for bot, a in sorted((res.get("books") or {}).items()):
        book_usd = a.get("book_usd") or 1000.0
        d = derive(a, book_usd)
        d["cohort"] = _cohort(bot, feed)
        d["verdict"] = a.get("verdict")
        d["gate_bars_passed"] = a.get("gate_bars_passed")
        d["t"] = a.get("t")
        d["mean_pct"] = (a["mean_pct"] * 100.0) if a.get("mean_pct") is not None else None
        d["max_dd_pct"] = (a["max_dd_frac"] * 100.0) if a.get("max_dd_frac") is not None else None
        d["era"] = a.get("era")
        # RECONCILIATION (see render_md's basis note): the baseline is
        # ERA-SCOPED and REALISED, so it will NOT equal the dashboard row's
        # lifetime `pnl_abs`. Carrying both makes the gap readable instead of
        # leaving a future reader to find it and distrust the artefact.
        d["n_alltime"] = a.get("n_alltime")
        d["row_pnl_abs_lifetime_usd"] = (feed.get(bot) or {}).get("pnl_abs")
        d["row_equity"] = (feed.get(bot) or {}).get("equity")
        # CALMAR — annualised return over maxDD. Uses the SIMPLE annualisation
        # (fixed clip, see the module doc) and the REALISED drawdown on the
        # same book unit, so numerator and denominator share a basis. None
        # when either side is unknown or the book never drew down: a Calmar
        # with a zero denominator is infinity dressed as a score.
        dd = d.get("max_dd_pct")
        ar = d.get("ann_return_simple_pct")
        d["calmar"] = (ar / dd) if (ar is not None and dd) else None
        d["recovery_days"] = a.get("recovery_days")
        d["recovered"] = a.get("recovered")
        d["closes_per_year"] = a.get("closes_per_year")
        d["sharpe"] = a.get("sharpe")
        d["sortino"] = a.get("sortino")
        d["gate_mtm_dd_pct"] = a.get("gate_mtm_dd_pct")
        d["underwater_frac"] = a.get("underwater_frac")
        d["max_consec_loss"] = a.get("max_consec_loss")
        # `expected_streak` is {p50, p95} — the chance median and 95th pct of
        # the longest losing run for THIS book's own hit rate and n. Keep p50
        # as the comparison point: a streak below the median is not a signal,
        # it is the distribution.
        es = a.get("expected_streak")
        d["expected_streak"] = es.get("p50") if isinstance(es, dict) else es
        d["expected_streak_p95"] = es.get("p95") if isinstance(es, dict) else None
        if shaped and bot in shaped:
            d["trade"] = trade_metrics(shaped[bot]["rows"], book_usd, regimes)
        rows[bot] = d
    for name in ("live", "shadow"):
        mem = {b: r for b, r in rows.items() if r["cohort"] == name}
        if not mem:
            continue
        cap = sum(r["book_usd"] for r in mem.values())
        net = sum(r["net_after_fees_usd"] or 0.0 for r in mem.values())
        stressed = sum((r.get("net_at_measured_cost_usd")
                        if r.get("net_at_measured_cost_usd") is not None
                        else (r["net_after_fees_usd"] or 0.0))
                       for r in mem.values())
        nw = sum(r["n_win"] or 0 for r in mem.values())
        nl = sum(r["n_loss"] or 0 for r in mem.values())
        # gross win/loss are summed from edge_audit, never re-derived from pcts
        gw = sum((res["books"][b].get("gross_win_usd") or 0.0) for b in mem)
        gl = sum((res["books"][b].get("gross_loss_usd") or 0.0) for b in mem)
        spans = [r["span_days"] for r in mem.values() if r["span_days"]]
        cohorts[name] = {
            "n_books": len(mem),
            "capital_usd": cap,
            "net_after_fees_usd": net,
            "net_at_measured_cost_usd": stressed,
            "total_return_pct": 100.0 * net / cap if cap else None,
            "n_closes": sum(r["n"] for r in mem.values()),
            "win_rate_pct": 100.0 * nw / (nw + nl) if (nw + nl) else None,
            "avg_win_usd": gw / nw if nw else None,
            "avg_loss_usd": gl / nl if nl else None,
            "profit_factor": abs(gw / gl) if gl else None,
            "turnover_x": (sum((r.get("trade") or {}).get("gross_notional_usd") or 0.0
                                for r in mem.values()) / cap) if cap else None,
            "avg_exposure_frac": (
                sum(((r.get("trade") or {}).get("avg_exposure_frac") or 0.0) * r["book_usd"]
                    for r in mem.values()) / cap) if cap else None,
            "span_days_max": max(spans) if spans else None,
            "span_days_min": min(spans) if spans else None,
            "books": sorted(mem),
        }
    surv = (survivorship(all_trades, feed_bots) if (all_trades and feed_bots) else None)
    return {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "survivorship": surv,
            "regimes_available": bool(regimes),
            "regime_hours": len(regimes or {}),
            "published_grade_at": res.get("published_grade_at"),
            "measured_rt_bps": edge_audit.MEASURED_RT_BPS,
            "extrap_warn_days": EXTRAP_WARN_DAYS,
            "n_books": len(rows),
            "cohorts": cohorts,
            "books": rows}


def _f(v, spec="%.2f", dash="—"):
    return dash if v is None else (spec % v)


def render_md(bl):
    if bl.get("refused"):
        return ("# BASELINE — REFUSED\n\nThe sample could not reproduce the live "
                "`golive-readiness` grade, so no baseline was written.\n\n```\n%s\n```\n"
                % json.dumps(bl.get("calibration"), default=str, indent=1))
    L = []
    A = L.append
    A("# BASELINE — %s" % bl["generated"][:10])
    A("")
    A("_Generated by `scripts/baseline_snapshot.py`. Calibrated against the live "
      "`golive-readiness` grade published %s — the run REFUSES if the sample "
      "cannot reproduce it._" % bl.get("published_grade_at"))
    A("")
    A("Every statistic below is derived from `scripts/edge_audit.py`, which "
      "imports `golive_readiness` (era, phantom filter, retired-sleeve drop, "
      "`stats`, `cluster_se`) and `fleet_allocation.t_crit`. Nothing here is a "
      "second implementation of a rule the fleet already owns.")
    A("")
    A("## Basis — read this before quoting any number below")
    A("")
    A("* **ERA-SCOPED.** `n` is the book's CURRENT-POLICY sample "
      "(`golive_readiness.POLICY_ERA` / the ledger's own `extra.policy` stamps), "
      "not its lifetime. A book whose accounting or strategy changed does not "
      "get to keep the old record. Where `n` < `n_all` the difference is "
      "pre-era closes this baseline deliberately excludes — 🌾 carry is the "
      "extreme case in this run.")
    A("* **REALISED.** Closed trades only. Open positions are marks, not "
      "evidence, so **these figures will NOT equal the dashboard row\'s "
      "`pnl_abs`**, which carries open MTM and capital adjustments. Both are "
      "shown per book so the gap is readable rather than surprising. The "
      "gate\'s own mark-to-market drawdown is folded into `maxDD` separately "
      "(I9).")
    A("* **QUARANTINE + PHANTOM FILTERED.** The public "
      "`/trades.json?source=paper` feed does NOT apply `LEDGER_QUARANTINE`; "
      "`edge_audit` does, via `bot_pnl_store.is_quarantined` and "
      "`golive_readiness.is_phantom_close`. Grading straight off the public "
      "feed would use a sample the gate refuses.")
    A("* **BOOK UNIT.** Shadow rows are the fleet standard $1,000. Live rows "
      "use their REAL starting equity, so a live return is a return on money "
      "that actually existed.")
    A("")
    sv = bl.get("survivorship")
    if sv:
        A("## Survivorship — the survivors' sum is not the fleet's result")
        A("")
        A("| population | books | closes | net $ |")
        A("|---|---|---|---|")
        A("| still publishing | %d | %d | **$%+.2f** |"
          % (sv["living"]["n_books"], sv["living"]["n_closes"], sv["living"]["net_usd"]))
        A("| retired since the cut | %d | %d | **$%+.2f** |"
          % (sv["retired"]["n_books"], sv["retired"]["n_closes"], sv["retired"]["net_usd"]))
        A("| **TRUE FLEET TOTAL** | %d | %d | **$%+.2f** |"
          % (sv["living"]["n_books"] + sv["retired"]["n_books"],
             sv["living"]["n_closes"] + sv["retired"]["n_closes"], sv["true_total_usd"]))
        A("")
        A("Realised P&L on **every book traded on Lighter since the %s "
          "LIGHTER-ONLY cut**, retired ones included. The living-book figure "
          "overstates the fleet's actual result by **$%.2f (%sx)**."
          % (sv["cut"], sv["survivor_overstatement_usd"],
             sv["survivor_overstatement_x"]))
        A("")
        A("**This does not reopen a single retirement.** Each was decided on a "
          "measured exclusion (I17) and retiring proven losers is correct. What "
          "it says is narrower and harder: every instrument in this fleet grades "
          "the LIVING set, so a loser leaves the sample on the day it is retired "
          "— and the number that survives is therefore not the number that was "
          "earned. Both belong in the record. Scoped to the Lighter era on "
          "purpose: pre-cut closes are a different venue, and three legacy books "
          "(+$547 combined) would flatter this in the other direction.")
        A("")
    A("## Cohort totals — live and paper are never pooled")
    A("")
    A("| cohort | books | capital | net after fees | total return | closes | "
      "win rate | avg win | avg loss | PF |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for name in ("live", "shadow"):
        c = bl["cohorts"].get(name)
        if not c:
            continue
        A("| **%s** | %d | $%s | **$%s** | **%s%%** | %d | %s%% | $%s | $%s | %s |"
          % (name, c["n_books"], _f(c["capital_usd"], "%.0f"),
             _f(c["net_after_fees_usd"]), _f(c["total_return_pct"]),
             c["n_closes"], _f(c["win_rate_pct"], "%.1f"),
             _f(c["avg_win_usd"]), _f(c["avg_loss_usd"]),
             _f(c["profit_factor"])))
    A("")
    A("## Per book")
    A("")
    A("| book | n (era) | n all | span d | net $ (era, realised) | row $ (lifetime, +MTM) "
      "| total ret % | ann % (simple) | ann % (comp) "
      "| win % | avg win $ | avg loss $ | W/L | PF | mean %/trade | t | maxDD % | verdict |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for bot, r in sorted(bl["books"].items(),
                         key=lambda kv: -(kv[1]["net_after_fees_usd"] or 0)):
        flag = " ⚠" if r.get("annualisation_is_extrapolation") else ""
        A("| `%s` | %d | %s | %s | %s | %s | %s | %s%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
          % (bot, r["n"], _f(r.get("n_alltime"), "%d"), _f(r["span_days"], "%.1f"),
             _f(r["net_after_fees_usd"]),
             _f(r.get("row_pnl_abs_lifetime_usd")), _f(r["total_return_pct"]),
             _f(r["ann_return_simple_pct"], "%.0f"), flag,
             _f(r["ann_return_compounded_pct"], "%.0f"),
             _f(r["win_rate_pct"], "%.1f"), _f(r["avg_win_usd"]),
             _f(r["avg_loss_usd"]), _f(r["win_loss_ratio"]),
             _f(r["profit_factor"]), _f(r["mean_pct"], "%.3f"),
             _f(r["t"]), _f(r["max_dd_pct"], "%.1f"), r.get("verdict") or "—"))
    A("")
    A("⚠ = span < %.0f days, so the annualised column is an **extrapolation**, "
      "not a measurement. The simple column (`$/day x 365 / book`) is the honest "
      "one: these books trade a FIXED clip, so compounding realised P&L models a "
      "book none of them runs." % bl["extrap_warn_days"])
    A("")
    A("## Risk-adjusted and activity metrics")
    A("")
    A("| book | Sharpe | Sortino | Calmar | maxDD % (realised) | maxDD % (gate MTM) "
      "| recovery d | underwater % | worst streak (vs chance) | trades/day | "
      "avg hold h | deployed clip $ | turnover x | avg exposure % |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for bot, r in sorted(bl["books"].items(),
                         key=lambda kv: -(kv[1].get("sharpe") or -9e9)):
        t = r.get("trade") or {}
        rec = ("never" if r.get("recovered") is False and r.get("recovery_days") is None
               else _f(r.get("recovery_days"), "%.1f"))
        A("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s / %s | %s | %s | %s | %s | %s |"
          % (bot, _f(r.get("sharpe"), "%.1f"), _f(r.get("sortino"), "%.1f"),
             _f(r.get("calmar"), "%.1f"), _f(r.get("max_dd_pct"), "%.1f"),
             _f(r.get("gate_mtm_dd_pct"), "%.1f"), rec,
             _f((r.get("underwater_frac") or 0) * 100.0, "%.0f"),
             _f(r.get("max_consec_loss"), "%d"), _f(r.get("expected_streak"), "%d"),
             _f(t.get("trades_per_day"), "%.2f"), _f(t.get("avg_hold_h"), "%.1f"),
             _f(t.get("implied_clip_median"), "%.0f"), _f(t.get("turnover_x"), "%.1f"),
             _f((t.get("avg_exposure_frac") or 0) * 100.0, "%.1f")))
    A("")
    A("`deployed clip $` is the MEDIAN notional actually put at risk, derived "
      "per trade — not the book\'s published `caps.clip_usd`, which is only the "
      "BASE before `brain_clip` x drawdown-scale x `allocation_scale` multiply "
      "it. 🌾 carry declares $80 and deploys $300 (3.75x); 🪁 kelly declares $80 "
      "and deploys $250. Nothing is broken — but the cap on the row is not the "
      "exposure, and no instrument here had said so.")
    A("")
    A("`turnover x` = gross entry notional / book, derived as `|pnl_abs/pnl_pct|` "
      "(present on ~all rows; `size` is on only 20%). `avg exposure %` = "
      "time-weighted deployed capital — the denominator that makes two equal "
      "returns comparable, and the one nothing in this fleet had printed. "
      "`worst streak` is shown beside its own chance median: a streak is only "
      "evidence when it exceeds what the book's hit rate produces by luck.")
    A("")

    # ---- regime -----------------------------------------------------------
    A("## Performance by market regime")
    A("")
    if not bl.get("regimes_available"):
        A("**WITHHELD.** No majors index was supplied, so no regime split was "
          "computed. A fabricated regime label is worse than none.")
    else:
        A("Regime is labelled from an **equal-weight BTC/ETH/SOL index in RETURN "
          "space** (a price-weighted basket of BTC and SOL is a BTC basket), on "
          "%d hourly bars. `trend` = index EMA%d vs EMA%d — the fleet's own "
          "e50/e200 convention, so the split agrees with what the books "
          "themselves call an uptrend. `vol` splits at the window's OWN median "
          "realised vol, so both buckets are equal-sized by construction. "
          "`market` is the index return over each trade's OWN holding window — "
          "the direct read of \"did this book make money while the market rose "
          "or fell\"." % (bl.get("regime_hours") or 0, EMA_FAST, EMA_SLOW))
        # THE BUCKET BALANCE IS PART OF THE RESULT, not a footnote. A split
        # whose minority bucket holds 16% of the sample spread across 14 books
        # cannot support a per-book claim, and this fleet's own doctrine (item
        # 18) already says the venue's tape is close to one regime.
        bal = {}
        for _b, _r in bl["books"].items():
            _t = _r.get("trade") or {}
            for _dim in ("by_trend", "by_vol", "by_market"):
                for _k, _v in (_t.get(_dim) or {}).items():
                    bal[_k] = bal.get(_k, 0) + _v["n"]
        tot_t = bal.get("bull", 0) + bal.get("bear", 0)
        A("**BUCKET BALANCE — read before any per-book cell.** %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(bal.items())))
        A("")
        A("The trend split is **%.0f%% bull**, which is this fleet's item-18 "
          "regime caveat measured rather than asserted: the venue's tape is "
          "close to one regime, so a per-book `bear` cell of a dozen trades "
          "decides nothing and must not be read as one. **The market-direction "
          "split is the usable one** (%d up / %d down, near balanced) because "
          "it is scored over each trade's own holding window rather than over "
          "a slow index state."
          % (100.0 * bal.get("bull", 0) / tot_t if tot_t else 0,
             bal.get("mkt_up", 0), bal.get("mkt_down", 0)))
        A("")
        for dim, title in (("by_trend", "Trend"), ("by_vol", "Volatility"),
                           ("by_market", "Market direction over the hold")):
            A("### %s" % title)
            A("")
            A("| book | %s |" % " | ".join(["bucket: n / net $ / mean %"] * 1))
            A("|---|---|")
            for bot, r in sorted(bl["books"].items()):
                d = (r.get("trade") or {}).get(dim) or {}
                if not d:
                    continue
                cells = "; ".join("**%s** %d / $%.2f / %.3f%%"
                                  % (k, v["n"], v["net_usd"], v["mean_pct"])
                                  for k, v in d.items())
                A("| `%s` | %s |" % (bot, cells))
            A("")
    A("")
    A("## Performance by month")
    A("")
    months = sorted({m for r in bl["books"].values()
                     for m in ((r.get("trade") or {}).get("by_month") or {})})
    if months:
        A("| book | " + " | ".join(months) + " |")
        A("|---" * (len(months) + 1) + "|")
        for bot, r in sorted(bl["books"].items(),
                             key=lambda kv: -(kv[1]["net_after_fees_usd"] or 0)):
            bm = (r.get("trade") or {}).get("by_month") or {}
            cells = [("%d / $%.2f" % (bm[m]["n"], bm[m]["net_usd"])) if m in bm else "—"
                     for m in months]
            A("| `%s` | %s |" % (bot, " | ".join(cells)))
        A("")
    A("## Top assets by trade count (descriptive — no significance claimed)")
    A("")
    A("| book | top assets (n / net $ / mean %) | distinct assets |")
    A("|---|---|---|")
    for bot, r in sorted(bl["books"].items()):
        ba = (r.get("trade") or {}).get("by_asset") or {}
        if not ba:
            continue
        top = list(ba.items())[:5]
        A("| `%s` | %s | %d |"
          % (bot, "; ".join("**%s** %d / $%.2f / %.2f%%"
                            % (k, v["n"], v["net_usd"], v["mean_pct"]) for k, v in top),
             len(ba)))
    A("")
    A("_Per-asset cells are DESCRIPTIVE. With 300+ buckets across the fleet, "
      "quoting any single one as evidence is a multiplicity trap — "
      "`golive_readiness.stats` and `winners_docket` own that judgement._")
    A("")
    A("## Cost sensitivity — what the fleet's own measured execution would take")
    A("")
    A("Venue fee is **zero** (measured across all active Lighter books), so "
      "`net after fees` above already carries the only real cost: the crossed "
      "spread, inside the book-walked fill. The stress below charges each book "
      "`n x %.2fbps x clip` on top — the fleet's OWN measured round trip `(qq)`."
      % bl["measured_rt_bps"])
    A("")
    A("| book | net $ | at measured cost $ | drag $ | flips sign |")
    A("|---|---|---|---|---|")
    for bot, r in sorted(bl["books"].items(),
                         key=lambda kv: -(kv[1]["net_after_fees_usd"] or 0)):
        if r.get("net_at_measured_cost_usd") is None:
            continue
        A("| `%s` | %s | %s | %s | %s |"
          % (bot, _f(r["net_after_fees_usd"]),
             _f(r["net_at_measured_cost_usd"]), _f(r.get("cost_drag_usd")),
             "**YES**" if r.get("flips_sign_under_measured_cost") else "no"))
    return "\n".join(L) + "\n"


def _selftest():
    # derive() must not invent a number the inputs cannot support.
    d = derive({"realised_usd": None, "span_days": None, "n": 0}, 1000.0)
    assert d["total_return_pct"] is None, d
    assert d["ann_return_simple_pct"] is None, d
    assert d["net_at_measured_cost_usd"] is None, d
    # a real row: 10% on $1,000 over half a year annualises to ~20% simple.
    d = derive({"realised_usd": 100.0, "span_days": 182.5, "usd_per_day": 100.0 / 182.5,
                "n": 50, "n_win": 30, "n_loss": 20, "win_rate": 0.6,
                "avg_win_usd": 10.0, "avg_loss_usd": -10.0,
                "monte_carlo": {"clip_usd": 100.0}}, 1000.0)
    assert abs(d["total_return_pct"] - 10.0) < 1e-9, d
    assert abs(d["ann_return_simple_pct"] - 20.0) < 1e-6, d
    assert abs(d["ann_return_compounded_pct"] - 21.0) < 0.01, d
    assert d["annualisation_is_extrapolation"] is False, d
    assert abs(d["win_loss_ratio"] - 1.0) < 1e-9, d
    # net after fees is realised (zero venue fee), and the stress is separate.
    assert d["net_after_fees_usd"] == 100.0 and d["venue_fee_usd"] == 0.0, d
    exp = 100.0 - 50 * (edge_audit.MEASURED_RT_BPS / 1e4) * 100.0
    assert abs(d["net_at_measured_cost_usd"] - exp) < 1e-9, d
    # a short span MUST be flagged, or the annual figure reads as measured.
    d2 = derive({"realised_usd": 10.0, "span_days": 9.0, "usd_per_day": 10.0 / 9.0,
                 "n": 5, "monte_carlo": {}}, 1000.0)
    assert d2["annualisation_is_extrapolation"] is True, d2
    assert abs(d2["extrapolation_x"] - 365.0 / 9.0) < 1e-9, d2
    # a book that lost everything has no compounded rate, and must not crash.
    d3 = derive({"realised_usd": -1000.0, "span_days": 30.0, "usd_per_day": -33.3,
                 "n": 5, "monte_carlo": {}}, 1000.0)
    assert d3["ann_return_compounded_pct"] is None, d3
    # the reconciliation fields must survive build() — without them the artefact
    # silently disagrees with the dashboard and gets distrusted.
    bl = build({"books": {"b": {"n": 3, "n_alltime": 9, "realised_usd": 1.0,
                                "span_days": 40.0, "usd_per_day": 0.025,
                                "book_usd": 1000.0, "monte_carlo": {}}},
                "_feed_rows": [{"bot": "b", "pnl_abs": 7.5, "equity": 1007.5,
                                "extra": {"venue": "lighter_shadow"}}]})
    rb = bl["books"]["b"]
    assert rb["n_alltime"] == 9 and rb["n"] == 3, rb
    assert rb["row_pnl_abs_lifetime_usd"] == 7.5, rb
    assert rb["cohort"] == "shadow", rb
    md = render_md(bl)
    assert "ERA-SCOPED" in md and "REALISED" in md and "QUARANTINE" in md, md
    # and a live row must land in the live cohort, derived from the payload
    bl2 = build({"books": {"L": {"n": 1, "realised_usd": 1.0, "book_usd": 100.0,
                                "monte_carlo": {}}},
                 "_feed_rows": [{"bot": "L", "pnl_abs": 1.0,
                                 "extra": {"venue": "lighter_live"}}]})
    assert bl2["books"]["L"]["cohort"] == "live", bl2
    assert "live" in bl2["cohorts"] and "shadow" not in bl2["cohorts"], bl2

    # survivorship: a retired loser must not be able to leave the total.
    import datetime as D
    cut = D.datetime(2026, 7, 17, tzinfo=D.timezone.utc)
    tr = [{"bot": "alive", "pnl_abs": 100.0, "closed_at": "2026-08-01T00:00:00+00:00"},
          {"bot": "dead", "pnl_abs": -80.0, "closed_at": "2026-08-01T00:00:00+00:00"},
          {"bot": "dead", "pnl_abs": -900.0, "closed_at": "2026-07-01T00:00:00+00:00"}]
    sv = survivorship(tr, {"alive"}, cut=cut)
    assert sv["living"]["net_usd"] == 100.0, sv
    assert sv["retired"]["net_usd"] == -80.0, sv     # pre-cut row excluded
    assert sv["true_total_usd"] == 20.0, sv
    assert sv["survivor_overstatement_usd"] == 80.0, sv
    assert sv["survivor_overstatement_x"] == 5.0, sv
    assert "Survivorship" in render_md(build(
        {"books": {}, "_feed_rows": []}, all_trades=tr, feed_bots={"alive"})), "not rendered"

    # a refusal propagates rather than producing a baseline nobody may quote,
    # and it NAMES what disagreed (I8) instead of printing a bare bool.
    r = build({"refused": True, "calibration": {"mum": "n 91 vs 59"}})
    assert r["refused"] is True, r
    assert r["calibration"] == {"mum": "n 91 vs 59"}, r
    assert "books" not in r, r
    r2 = build({"refused": True})          # no findings supplied
    assert "fail-closed" in str(r2["calibration"]), r2
    assert "REFUSED" in render_md(r2) and "n 91 vs 59" in render_md(r), r2
    print("baseline_snapshot selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger")
    ap.add_argument("--feed")
    ap.add_argument("--bus")
    ap.add_argument("--out", help="write the baseline JSON here")
    ap.add_argument("--md", help="write the baseline markdown here")
    ap.add_argument("--majors", help="local {symbol: {epoch_sec: close}} 1h dump "
                                     "for the regime split; omitted = split withheld")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    res = edge_audit.run(ledger=a.ledger, feed=a.feed, bus=a.bus, mc_draws=200)
    # keep the feed rows so cohort membership is DERIVED, never typed
    res["_feed_rows"] = edge_audit._load_json(a.feed).get("bots") if a.feed else None
    shaped, regimes = None, None
    if not res.get("refused"):
        shaped = edge_audit.shape(edge_audit.load_trades(a.ledger))
    if a.majors:
        raw = edge_audit._load_json(a.majors) or {}
        regimes = build_regimes({k: {int(t): float(c) for t, c in v.items()}
                                 for k, v in raw.items()})
    feed_bots = ({r.get("bot") for r in (res.get("_feed_rows") or [])}
                 if res.get("_feed_rows") else None)
    bl = build(res, shaped=shaped, regimes=regimes,
               all_trades=edge_audit.load_trades(a.ledger) if a.ledger else None,
               feed_bots=feed_bots)
    if bl.get("refused"):
        sys.stderr.write("BASELINE REFUSED — sample disowned by the live grade: "
                         "%s\n" % json.dumps(bl.get("calibration"), default=str)[:600])
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(bl, fh, default=str, indent=1)
    md = render_md(bl)
    if a.md:
        with open(a.md, "w") as fh:
            fh.write(md)
    print(md)
    return 2 if bl.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
