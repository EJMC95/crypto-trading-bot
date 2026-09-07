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

#: A span this short makes an annual figure an extrapolation, not a measurement.
#: 30 days is the go-live window bar — below it the fleet does not consider a
#: book graded at all, so it is the natural line.
EXTRAP_WARN_DAYS = 30.0

#: Rows whose `extra.venue` says real money. Derived from the feed, never typed
#: — `scripts/fleet_books.py` makes the same point: which rows are live is a
#: property of the PAYLOAD.
LIVE_VENUES = ("lighter_live",)


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


def build(res):
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
            "span_days_max": max(spans) if spans else None,
            "span_days_min": min(spans) if spans else None,
            "books": sorted(mem),
        }
    return {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
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
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    res = edge_audit.run(ledger=a.ledger, feed=a.feed, bus=a.bus, mc_draws=200)
    # keep the feed rows so cohort membership is DERIVED, never typed
    res["_feed_rows"] = edge_audit._load_json(a.feed).get("bots") if a.feed else None
    bl = build(res)
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
