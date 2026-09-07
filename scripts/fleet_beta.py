#!/usr/bin/env python3
"""scripts/fleet_beta.py — THE FLEET'S MARKET EXPOSURE, AND WHO SUPPLIES IT.

    python3 scripts/fleet_beta.py --ledger t.json --feed p.json --bus b.json \
        --majors majors_1h.json --out beta.json --md FLEET_BETA.md
    python3 scripts/fleet_beta.py --selftest

WHY. The fleet grades every book ALONE — six bars, a lower-bound claim, a
winners' docket, a ceiling, and now a per-book cost. **Not one of those can see
a property that only exists across books**, and the largest one measured in this
audit is exactly that shape: the fleet earns from long beta and PAYS for its
hedge. No per-book instrument can say so, because for each book separately
nothing is wrong.

THE MEASUREMENT, and the weighting IS the finding:

  * **trade-weighted beta reads +0.04** — apparently market-neutral;
  * **exposure-weighted beta reads +0.324**, and the LIVE cohort **+0.658**.

The gap is not noise, it is an averaging artifact with a name: 🪁 kelly
contributes 590 of ~1,740 labelled trades at a $250 clip held ~1.2h and a beta
of −0.76, so it dominates the COUNT and almost none of the RISK. **Weighting by
trade count asks "what does the average trade look like"; weighting by
time-weighted capital asks "what is the money doing". Only the second is a risk
question**, so this module reports both and says which one to read.

AND THE COMPOSITION MATTERS MORE THAN THE LEVEL. Profitable books mean beta
+0.40; loss-making books −0.12. A fleet that nets to zero beta by holding
winners long and losers short is not hedged — it is paying for its neutrality,
and the bill is the losers' P&L.

WHAT IT DOES NOT DO. It moves nothing: no lever, no capital, no promotion. It
does NOT modify `fleet_risk.exposure` — that field feeds live consumers and the
brief's safety constraints forbid touching filters that affect existing bots.
Instead it publishes a correlation-aware effective-N **beside** the incumbent
`1/HHI` so the two can be compared before anyone decides to move one.

WHY `1/HHI` OVER DISTINCT SYMBOLS OVERSTATES INDEPENDENCE, stated because this
module's whole second half rests on it: `fleet_risk.py:366` computes
`long_effective_n = 1/sum((count/n)^2)` over SYMBOLS, so 9 longs in 9 different
tickers read as 9.0 independent bets no matter how correlated those tickers are.
The organ's own docstring already warns that *"23 open longs that are all crypto
beta is ~one trade, and nothing said so"* — the warning is right and the formula
cannot express it. A correlation-aware N_eff can: `(sum w)^2 / (w' R w)`, which
collapses toward 1 as the pairwise correlations approach 1 and equals the symbol
count only when they are all zero.

THE CALIBRATION GATE. Beta is a regression, and a regression on a window that
does not contain the trades is a number about nothing. This REFUSES unless the
regime index covers a minimum share of each graded book's closes, and reports
per-book coverage. Fail-CLOSED: no index, no coverage, no claim.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edge_audit                                    # noqa: E402
import baseline_snapshot as _bl                      # noqa: E402 — regime owner

#: Identity imports. The regime index and the holding-window market move are
#: `baseline_snapshot`'s, so the beta here and the regime split in the baseline
#: cannot disagree about what "the market did" ((hj)).
build_regimes = _bl.build_regimes
market_move = _bl.market_move

#: A book with fewer labelled closes than this gets NO beta. 20 is not a
#: significance bar — it is the point below which a slope is arithmetic rather
#: than evidence. The t-stat is published beside every beta so the reader
#: judges; this floor only stops the module printing a number from 4 points.
MIN_N = 20

#: Minimum share of a book's closes the index must cover before its beta is
#: reported. Below it the regression describes the covered subset, not the book.
MIN_COVERAGE = 0.80


def book_beta(rows, regimes):
    """(beta, t, n, coverage) of a book's per-trade return on the market's move
    over THAT TRADE'S OWN holding window.

    Contemporaneous by construction: it asks what the market did WHILE the book
    held, not what it did before the book decided. That is the exposure
    question. A predictive version would be a different (and much stronger)
    claim and this module does not make it.
    """
    xs, ys, seen = [], [], 0
    for q in rows:
        seen += 1
        m = market_move(_bl._ts_of(q[3]), q[2], regimes)
        if m is None:
            continue
        xs.append(m)
        ys.append(q[0])
    cov = (len(xs) / seen) if seen else None
    if len(xs) < MIN_N or cov is None or cov < MIN_COVERAGE:
        return None, None, len(xs), cov
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((a - mx) ** 2 for a in xs)
    if var <= 0:
        return None, None, len(xs), cov
    beta = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / var
    alpha = my - beta * mx
    resid = [b - (alpha + beta * a) for a, b in zip(xs, ys)]
    dof = len(xs) - 2
    if dof <= 0:
        return beta, None, len(xs), cov
    se = (sum(r * r for r in resid) / dof / var) ** 0.5
    return beta, (beta / se if se > 0 else None), len(xs), cov


def corr_effective_n(weights, corr):
    """(sum w)^2 / (w' R w) — independence a symbol count cannot express.

    Equals len(w) when every pairwise correlation is 0 and collapses toward 1
    as they approach 1, which is the property `1/HHI` over distinct symbols
    lacks: it reads 9 perfectly-correlated longs as 9 independent bets.
    Returns None on anything unusable — an unmeasurable pair must never
    silently read as uncorrelated, because zero is the value that BUYS
    diversification (the (sr) fail-safe).
    """
    ks = [k for k in weights if weights[k] > 0]
    if not ks:
        return None
    num = sum(weights[k] for k in ks) ** 2
    den = 0.0
    for i in ks:
        for j in ks:
            if i == j:
                r = 1.0
            else:
                r = corr.get((i, j), corr.get((j, i)))
                if r is None:
                    return None            # unmeasurable pair => no claim
            den += weights[i] * weights[j] * r
    if den <= 0:
        return None
    return num / den


def fetch_returns(symbols, ids, hours=400, api=None):
    """{symbol: {hour_epoch: hourly return}} for the CURRENTLY HELD names.

    The correlation that matters is between the coins the fleet is HOLDING, not
    between three majors. Computing N_eff on a proxy basket and comparing it to
    `1/HHI` on the real held set is an apples-to-oranges ratio — a defect this
    module shipped in its first cut and which is corrected here: the two numbers
    must describe the SAME population or the ratio means nothing.

    A symbol that cannot be fetched is ABSENT, never zero-correlation — the
    (sr) fail-safe, because zero is the value that buys diversification.
    """
    import time
    import urllib.request
    api = api or os.environ.get("LIGHTER_API",
                                "https://mainnet.zklighter.elliot.ai")
    now = int(time.time())
    out = {}
    for sym in symbols:
        mid = ids.get(sym)
        if mid is None:
            continue
        url = ("%s/api/v1/candles?market_id=%d&resolution=1h"
               "&start_timestamp=%d&end_timestamp=%d&count_back=%d"
               % (api, mid, now - hours * 3600, now, min(hours, 500)))
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.loads(r.read().decode())
        except Exception:                                   # noqa: BLE001
            continue                                        # absent, not zero
        rows = sorted(((int(c["t"]) // 1000, float(c["c"]))
                       for c in (d.get("c") or [])), key=lambda x: x[0])
        if len(rows) < 40:
            continue
        out[sym] = {rows[i][0]: (rows[i][1] / rows[i - 1][1] - 1.0)
                    for i in range(1, len(rows)) if rows[i - 1][1]}
    return out


def pairwise_corr(series):
    """{(a,b): rho} over aligned hourly return series. None where too short."""
    out, keys = {}, sorted(series)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ha = series[a]
            hb = series[b]
            common = sorted(set(ha) & set(hb))
            if len(common) < 30:
                out[(a, b)] = None
                continue
            xa = [ha[h] for h in common]
            xb = [hb[h] for h in common]
            ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
            va = sum((x - ma) ** 2 for x in xa)
            vb = sum((x - mb) ** 2 for x in xb)
            if va <= 0 or vb <= 0:
                out[(a, b)] = None
                continue
            out[(a, b)] = (sum((x - ma) * (y - mb) for x, y in zip(xa, xb))
                           / (va ** 0.5) / (vb ** 0.5))
    return out


def _f(v, spec="%.2f", dash="—"):
    return dash if v is None else (spec % v)


def render_md(res):
    if res.get("refused"):
        return ("# FLEET BETA — REFUSED\n\n%s\n" % res["refused"])
    L = []
    A = L.append
    A("# FLEET MARKET EXPOSURE — %s" % res["generated"][:16].replace("T", " "))
    A("")
    A("_Advisory. Moves no lever, no capital, no promotion. Beta is each book's "
      "per-trade return regressed on an equal-weight BTC/ETH/SOL index over "
      "**that trade's own holding window**._")
    A("")
    A("## The headline, and the weighting is the finding")
    A("")
    A("| weighting | fleet beta | what it asks |")
    A("|---|---|---|")
    A("| trade-weighted | **%s** | what does the average TRADE look like |"
      % _f(res["fleet"]["trade_weighted"], "%+.3f"))
    A("| **exposure-weighted** | **%s** | **what is the MONEY doing** |"
      % _f(res["fleet"]["exposure_weighted"], "%+.3f"))
    A("| live cohort only | **%s** | what is the REAL money doing |"
      % _f(res["fleet"]["live_exposure_weighted"], "%+.3f"))
    A("")
    if res["fleet"].get("count_dominator"):
        A("The gap is an averaging artifact with a name: **%s contributes %s of "
          "%s labelled trades at a beta of %s** and a small clip, so it "
          "dominates the COUNT and almost none of the RISK. Only the "
          "exposure-weighted row is a risk statement."
          % (res["fleet"]["count_dominator"],
             _f(res["fleet"]["count_dominator_n"], "%d"),
             _f(res["fleet"]["n_labelled"], "%d"),
             _f(res["fleet"]["count_dominator_beta"], "%+.2f")))
        A("")
    A("## Composition — who supplies the exposure, and who pays for the hedge")
    A("")
    A("| cohort | mean beta | net $ |")
    A("|---|---|---|")
    A("| books that MAKE money | **%s** | %s |"
      % (_f(res["fleet"]["profitable_mean_beta"], "%+.2f"),
         _f(res["fleet"]["profitable_net"], "$%+.2f")))
    A("| books that LOSE money | **%s** | %s |"
      % (_f(res["fleet"]["losing_mean_beta"], "%+.2f"),
         _f(res["fleet"]["losing_net"], "$%+.2f")))
    A("")
    A("**A fleet that nets to zero beta by holding winners long and losers "
      "short is not hedged — it is paying for its neutrality, and the bill is "
      "the losers' P&L.**")
    A("")
    A("## Per book")
    A("")
    A("| book | beta | t | avg $ at risk | net $ | n | coverage |")
    A("|---|---|---|---|---|---|---|")
    for bot, r in sorted(res["books"].items(),
                         key=lambda kv: -(kv[1].get("exposure_usd") or 0)):
        A("| `%s` | %s | %s | %s | %s | %d | %s |"
          % (bot, _f(r.get("beta"), "%+.2f"), _f(r.get("t"), "%+.2f"),
             _f(r.get("exposure_usd"), "$%.0f"), _f(r.get("net_usd"), "$%+.2f"),
             r.get("n") or 0, _f((r.get("coverage") or 0) * 100.0, "%.0f%%")))
    A("")
    A("`avg $ at risk` is time-weighted deployed capital — the weight that "
      "makes the exposure-weighted beta a risk number rather than a trade "
      "average. A book with no beta had fewer than %d labelled closes or "
      "under %.0f%% index coverage; it is not a claim of neutrality."
      % (MIN_N, MIN_COVERAGE * 100))
    A("")
    A("## Effective bets — what `1/HHI` over symbols cannot express")
    A("")
    en = res.get("effective_n") or {}
    A("| measure | value | what it counts |")
    A("|---|---|---|")
    A("| distinct symbols held | %s | the raw count |" % _f(en.get("n_symbols"), "%d"))
    A("| `fleet_risk.long_effective_n` (`1/HHI`) | %s | concentration ACROSS "
      "symbols, blind to whether they move together |" % _f(en.get("hhi_n"), "%.1f"))
    A("| **correlation-aware N_eff** | **%s** | independence — collapses toward "
      "1 as the held names correlate |" % _f(en.get("corr_n"), "%.1f"))
    A("")
    if en.get("corr_n") and en.get("hhi_n") and en.get("comparable"):
        A("**The incumbent overstates independence by %.1fx on the currently "
          "held set** (%d of %d held names priced). `fleet_risk`'s own "
          "docstring already warns that *\"23 open longs that are all crypto "
          "beta is ~one trade, and nothing said so\"* — the warning is correct "
          "and `1/HHI` over symbols cannot express it."
          % (en["hhi_n"] / en["corr_n"], en.get("n_priced") or 0,
             en.get("n_symbols") or 0))
        A("")
    elif en.get("corr_n") or en.get("hhi_n"):
        A("**Ratio WITHHELD** — only %s of %s held names could be priced "
          "(%s coverage), so the two measures do not describe the same "
          "population and comparing them would be the apples-to-oranges error "
          "this module shipped in its first cut."
          % (en.get("n_priced"), en.get("n_symbols"),
             _f((en.get("coverage") or 0) * 100, "%.0f%%")))
        A("")
    A("**NOTHING HERE MODIFIES `fleet_risk`.** That field feeds live consumers "
      "and the audit's safety constraints forbid touching filters that affect "
      "existing bots. This publishes the alternative BESIDE the incumbent so "
      "the two can be compared before anyone decides to move one.")
    return "\n".join(L) + "\n"


def _selftest():
    # corr_effective_n: the property 1/HHI lacks
    w = {"a": 1.0, "b": 1.0, "c": 1.0}
    indep = {("a", "b"): 0.0, ("a", "c"): 0.0, ("b", "c"): 0.0}
    assert abs(corr_effective_n(w, indep) - 3.0) < 1e-9
    same = {("a", "b"): 1.0, ("a", "c"): 1.0, ("b", "c"): 1.0}
    assert abs(corr_effective_n(w, same) - 1.0) < 1e-9      # 3 names, ONE bet
    half = {("a", "b"): 0.5, ("a", "c"): 0.5, ("b", "c"): 0.5}
    n = corr_effective_n(w, half)
    assert 1.0 < n < 3.0, n
    # an unmeasurable pair must NOT read as uncorrelated (which buys diversification)
    assert corr_effective_n(w, {("a", "b"): None, ("a", "c"): 0.0,
                                ("b", "c"): 0.0}) is None
    assert corr_effective_n({}, indep) is None

    # book_beta: a floor, a coverage gate, and a real slope
    import datetime as D
    def mk(pct, h0, h1):
        o = D.datetime(2026, 8, 1, tzinfo=D.timezone.utc) + D.timedelta(hours=h0)
        c = D.datetime(2026, 8, 1, tzinfo=D.timezone.utc) + D.timedelta(hours=h1)
        return (pct, 0.0, c, o.isoformat(), None, None, "X", {})
    reg, lvl = {}, 100.0
    base = int(D.datetime(2026, 8, 1, tzinfo=D.timezone.utc).timestamp()) // 3600 * 3600
    for i in range(200):
        lvl *= 1.001 if i % 2 else 0.999
        reg[base + i * 3600] = {"idx": lvl, "trend": "bull", "vol": "low_vol"}
    rows = [mk(0.02 * ((reg[base + (i + 1) * 3600]["idx"]
                        / reg[base + i * 3600]["idx"]) - 1.0) * 100, i, i + 1)
            for i in range(100)]
    b, t, n, cov = book_beta(rows, reg)
    assert n == 100 and cov == 1.0, (n, cov)
    assert b is not None and b > 0, b
    # below the floor => no number, and that is not a claim of neutrality
    b2, _, n2, _ = book_beta(rows[:5], reg)
    assert b2 is None and n2 == 5
    # coverage gate: rows outside the index are counted against coverage
    far = [mk(1.0, 5000 + i, 5001 + i) for i in range(90)]
    b3, _, _, cov3 = book_beta(rows + far, reg)
    assert cov3 < 1.0 and b3 is None, (b3, cov3)
    # pairwise_corr refuses a SHORT overlap rather than inventing a rho.
    # The first cut of this assertion used a ONE-point overlap, which returns
    # None through the zero-variance branch whether or not the length floor
    # exists — a test that passed for the wrong reason and let a mutation of
    # the floor survive. Use 5 points with real variance: without the floor
    # this yields a confident (and meaningless) rho of 1.0.
    short = {"a": {i: 0.01 * i for i in range(5)},
             "b": {i: 0.02 * i for i in range(5)}}
    assert pairwise_corr(short)[("a", "b")] is None, "short overlap must refuse"
    # and with a LONG enough overlap it does produce one, so the floor is not
    # merely refusing everything (the (po) positive control)
    long_ = {"a": {i: 0.01 * ((i % 7) - 3) for i in range(60)},
             "b": {i: 0.02 * ((i % 7) - 3) for i in range(60)}}
    r = pairwise_corr(long_)[("a", "b")]
    assert r is not None and r > 0.99, r
    # the ratio is only claimed when both measures cover the same population
    base = {"generated": "2026-09-07T00:00", "fleet": {}, "books": {}}
    base["fleet"] = {k: None for k in
                     ("trade_weighted", "exposure_weighted",
                      "live_exposure_weighted", "n_labelled", "count_dominator",
                      "count_dominator_n", "count_dominator_beta",
                      "profitable_mean_beta", "losing_mean_beta",
                      "profitable_net", "losing_net")}
    md = render_md(dict(base, effective_n={"hhi_n": 11.8, "corr_n": 1.2,
                                           "n_symbols": 29, "n_priced": 3,
                                           "coverage": 0.10,
                                           "comparable": False}))
    assert "WITHHELD" in md and "overstates independence" not in md, md
    md2 = render_md(dict(base, effective_n={"hhi_n": 11.8, "corr_n": 1.2,
                                            "n_symbols": 29, "n_priced": 27,
                                            "coverage": 0.93,
                                            "comparable": True}))
    assert "overstates independence by 9.8x" in md2, md2
    print("fleet_beta selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger"); ap.add_argument("--feed"); ap.add_argument("--bus")
    ap.add_argument("--majors", required=False)
    ap.add_argument("--obd", help="orderBookDetails dump (market ids for the "
                                  "held-symbol return series)")
    ap.add_argument("--out"); ap.add_argument("--md")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest(); return 0
    if not a.majors:
        sys.stderr.write("no --majors index: refusing (a beta with no market "
                         "is a number about nothing)\n")
        return 2
    res = edge_audit.run(ledger=a.ledger, feed=a.feed, bus=a.bus, mc_draws=100)
    if res.get("refused"):
        sys.stderr.write("edge_audit refused; beta cannot speak\n")
        return 2
    raw = edge_audit._load_json(a.majors) or {}
    majors = {k: {int(t): float(c) for t, c in v.items()} for k, v in raw.items()}
    regimes = build_regimes(majors)
    if not regimes:
        print(render_md({"refused": "majors index too short to build a regime"}))
        return 2
    shaped = edge_audit.shape(edge_audit.load_trades(a.ledger))
    feed = {r["bot"]: r for r in (edge_audit._load_json(a.feed) or {}).get("bots") or []}

    books, tot_x = {}, 0.0
    for bot in sorted(res["books"]):
        aud = res["books"][bot]
        rows = (shaped.get(bot) or {}).get("rows") or []
        beta, t, n, cov = book_beta(rows, regimes)
        tm = _bl.trade_metrics(rows, aud.get("book_usd") or 1000.0)
        expo = (tm.get("avg_exposure_frac") or 0.0) * (aud.get("book_usd") or 1000.0)
        live = ((feed.get(bot) or {}).get("extra") or {}).get("venue") == "lighter_live"
        books[bot] = {"beta": beta, "t": t, "n": n, "coverage": cov,
                      "exposure_usd": round(expo, 2), "live": live,
                      "net_usd": aud.get("realised_usd")}
        tot_x += expo

    def wavg(sel):
        num = den = 0.0
        for b, r in books.items():
            if r["beta"] is None or not sel(r):
                continue
            num += r["beta"] * r["exposure_usd"]; den += r["exposure_usd"]
        return (num / den) if den else None

    graded = {b: r for b, r in books.items() if r["beta"] is not None}
    tn = sum(r["n"] for r in graded.values())
    tw = (sum(r["beta"] * r["n"] for r in graded.values()) / tn) if tn else None
    dom = max(graded, key=lambda b: graded[b]["n"]) if graded else None
    pos = [r for r in graded.values() if (r["net_usd"] or 0) > 0]
    neg = [r for r in graded.values() if (r["net_usd"] or 0) <= 0]

    # effective bets on the CURRENTLY HELD set, from the risk organ's own view
    bus = edge_audit._load_json(a.bus) or {}
    fr = bus.get("fleet_risk") or {}
    held = {}
    for r in (edge_audit._load_json(a.feed) or {}).get("bots") or []:
        for sym in ((r.get("extra") or {}).get("held") or {}):
            held[edge_audit.base_symbol(sym) or sym] = held.get(
                edge_audit.base_symbol(sym) or sym, 0) + 1
    # THE HELD SET, not a proxy basket — the two numbers must describe the
    # same population or their ratio is meaningless (first-cut defect, fixed).
    ids = {}
    if a.obd:
        for r in (edge_audit._load_json(a.obd) or {}).get("order_book_details") or []:
            ids[r["symbol"]] = r["market_id"]
    series = fetch_returns(sorted(held), ids) if (held and ids) else {}
    corr = pairwise_corr(series)
    # weight each held name by how many books hold it — the concentration
    # `1/HHI` is computed on, so the comparison is like-for-like.
    w = {k: float(held.get(k, 0)) for k in series}
    corr_n = corr_effective_n(w, corr)
    covered = len(series)
    en = {"n_symbols": len(held) or None,
          "hhi_n": (fr.get("exposure") or {}).get("long_effective_n"),
          "corr_n": corr_n,
          "corr_basis": "held symbols",
          "n_priced": covered,
          "coverage": round(covered / len(held), 3) if held else None,
          "comparable": bool(held) and covered >= max(3, int(0.8 * len(held))),
          "note": ("corr_n is measured on the SAME held set as hhi_n. Where "
                   "coverage is below 80%% the two are NOT comparable and the "
                   "ratio is withheld.")}

    out = {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
           "advisory": True, "moves_capital": False,
           "fleet": {"trade_weighted": tw,
                     "exposure_weighted": wavg(lambda r: True),
                     "live_exposure_weighted": wavg(lambda r: r["live"]),
                     "n_labelled": tn,
                     "count_dominator": dom,
                     "count_dominator_n": graded[dom]["n"] if dom else None,
                     "count_dominator_beta": graded[dom]["beta"] if dom else None,
                     "profitable_mean_beta": (sum(r["beta"] for r in pos) / len(pos)
                                              if pos else None),
                     "losing_mean_beta": (sum(r["beta"] for r in neg) / len(neg)
                                          if neg else None),
                     "profitable_net": sum(r["net_usd"] or 0 for r in pos),
                     "losing_net": sum(r["net_usd"] or 0 for r in neg)},
           "effective_n": en, "books": books}
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(out, fh, default=str, indent=1)
    md = render_md(out)
    if a.md:
        with open(a.md, "w") as fh:
            fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
