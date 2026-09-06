#!/usr/bin/env python3
"""
scripts/fleet_pooled_grader.py — DOES A STRUCTURAL FEATURE PAY, POOLED ACROSS
EVERY BOOK THAT HAS IT?

THE GAP THIS FILLS, measured by grepping the tree before writing a line.
  Every grading instrument in this fleet is PER BOOK. `golive_readiness` grades
  a book. `winners_docket` buckets `for bot, rows in by_bot.items()`.
  `fleet_allocation` ranks books. `edge_audit` has a `side_split` and computes
  it INSIDE `audit_book`. Not one of them pools a feature ACROSS books.

  That is not a cosmetic gap. A defect that is small in every book and large in
  the fleet is invisible to every per-book instrument at once, because each book
  sees an underpowered slice and none sees the sum. Measured on the day this
  shipped: the fleet's SHORT side reads n=34 on the taker, n=44 on Counterweight,
  n=26 on bezos — nothing survives multiplicity anywhere — while POOLED it is
  **n=1441 across 22 books and 53 days, -0.618%/trade, cluster-by-book t=-2.61,
  cluster-by-day t=-3.83.** It had run for 59 days and no instrument in the
  fleet could see it, because no instrument was allowed to add the books up.

  This is I22's arithmetic pointed at MEASUREMENT rather than at trading: one
  book is one term in the sum, and the fleet had no way to take the sum.

WHAT IT IS NOT
  * NOT a second copy of any rule. The sample is `edge_audit.shape` (which is
    itself `golive_readiness.era_rows` + `is_phantom_close` + `is_adopted_close`
    + `store.is_quarantined` + `drop_retired_sleeves`); the clustered SE is
    `golive_readiness.cluster_se`; the multiplicity rule is
    `winners_docket.bh_survivors`; the critical value is
    `fleet_allocation.t_crit`. All identity imports. A local re-implementation
    of any of them is the (hj) defect and is pinned against in the tests.
  * NOT a gate and NOT an actuator. It moves no capital, writes no lever,
    promotes and retires nothing — asserted against this module's own source,
    the `fleet_allocation` pattern. A pooled cell is EVIDENCE ABOUT A CLASS; the
    per-book instruments stay the authority over any individual book.
  * NOT a licence to act on a cell. A pooled feature mixes books with different
    signals, so a negative cell says "this shape is not paying across the
    fleet", never "book X should stop". Acting on one is a separate, measured,
    per-book decision.

THE BINDING STATISTIC IS THE WORSE OF t_book AND t_day.
  A pooled cell has two ways to be a fake: one prolific book can carry it (the
  concentration failure the (wo) audit found four times), or one day can (the
  (vr) day-concentration class, where 17 simultaneous exits across 7 correlated
  majors were 77% of a book's P&L). Clustering by book alone is blind to the
  second; by day alone is blind to the first. This reports both and rules on
  whichever is weaker, then applies BH across every cell tested.

Read-only. No DB, no orders, no writes.
Usage:
    python3 scripts/fleet_pooled_grader.py            # live feed
    python3 scripts/fleet_pooled_grader.py --json     # machine-readable
    python3 scripts/fleet_pooled_grader.py --selftest # offline
"""
import argparse
import json
import math
import os
import statistics as st
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edge_audit as ea                       # noqa: E402
import golive_readiness as gr                 # noqa: E402
import winners_docket as wd                   # noqa: E402
import fleet_allocation as fa                 # noqa: E402
import bot_pnl_store as store                 # noqa: E402

LIGHTER_API = "https://mainnet.zklighter.elliot.ai"
BTC_MARKET_ID = 1
EMA_N = 200
MIN_CELL_N = 30          # the go-live gate's own closes bar, applied to a cell
MIN_BOOKS = 3            # a "fleet-wide" claim needs more than a pair of books
FDR = 0.05

# Hold bands, in hours. Chosen to match the bands the fleet already reasons in
# ((wo): the taker's "1-3d" and "1-4h" cells), not invented here.
HOLD_BANDS = [(0.0, 1.0, "<1h"), (1.0, 4.0, "1-4h"), (4.0, 24.0, "4-24h"),
              (24.0, 72.0, "1-3d"), (72.0, float("inf"), ">3d")]


# ---------------------------------------------------------------------------
# regime — reconstructed from the venue's OWN BTC candles, LAG-1
# ---------------------------------------------------------------------------
def btc_regime_map(fetch=True):
    """{YYYY-MM-DD: +1 up | -1 down} from Lighter's own BTC daily closes vs an
    EMA200, LAG-1 (the regime KNOWN at the start of day d is d-1's close vs
    d-1's ema) — no look-ahead, the fleet's standing convention.

    Fail-CLOSED: any trouble returns {} and every trade reads `unknown`, which
    is reported as its own cell rather than folded into either regime (I8:
    unknown degrades to unknown, never to a guess)."""
    if not fetch:
        return {}
    try:
        import urllib.request
        end = int(time.time())
        start = end - 500 * 86400
        url = (f"{LIGHTER_API}/api/v1/candles?market_id={BTC_MARKET_ID}"
               f"&resolution=1d&start_timestamp={start}"
               f"&end_timestamp={end}&count_back=500")
        with urllib.request.urlopen(url, timeout=60) as r:
            c = json.loads(r.read()).get("c") or []
        rows = sorted((int(x["t"]) // 1000, float(x["c"])) for x in c)
        if len(rows) < EMA_N:
            return {}
        k = 2.0 / (EMA_N + 1.0)
        ema, out = None, {}
        prev = None
        for ts, px in rows:
            ema = px if ema is None else px * k + ema * (1 - k)
            day = time.strftime("%Y-%m-%d", time.gmtime(ts))
            if prev is not None:
                out[day] = 1 if prev[0] > prev[1] else -1
            prev = (px, ema)
        return out
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# feature extraction
# ---------------------------------------------------------------------------
def hold_band(extra):
    h = (extra or {}).get("held_h") if isinstance(extra, dict) else None
    if not isinstance(h, (int, float)) or not math.isfinite(float(h)):
        return None
    for lo, hi, name in HOLD_BANDS:
        if lo <= float(h) < hi:
            return name
    return None


def exit_family(reason):
    """The exit family, or None if it must not be graded.

    TWO OWNERS, BOTH IMPORTED — and this function is the worked example of why
    that matters, because its first draft owned both itself and got both wrong.

    1. THE SPLIT is `bot_pnl_store.split_reason`, "the ONE parser those
       composers round-trip against". The first draft took `rsplit("_", 1)[-1]`
       and produced garbage the moment a real ledger hit it:
       `long_exit_long` -> "long" (a cell that read +4.803%/trade and reached
       the BH survivor list as a *finding*), `long_range_high` -> "high",
       `long-trend-breakout_trailing_stop_loss` -> "loss".
    2. THE I7 SCREEN is `winners_docket.OUTCOME_EXITS`. An exit family
       CONDITIONED ON THE PRICE OUTCOME is a winner or a loser BY CONSTRUCTION:
       a `tp` bucket wins because it is the bucket that won. The first draft
       had no screen and duly "discovered" tp +2.700% and sl -2.225% at
       binding t of +3.69 and -5.74 -- five of its eight BH survivors were
       tautologies. `winners_docket` had closed exactly this class at I21 and
       the defect was reproduced one directory away, which is (hj) ("a second
       copy of a rule is a second rule") and I15 ("when a bad idea is removed
       from a report, grep for it in the things that ACT") in one line.

    The substring test is deliberately the docket's own conservative one: it
    matches on BOTH the full family and its last token, so `trailing_stop_loss`
    is screened by "stop" rather than surviving on "loss"."""
    _tag, fam = store.split_reason(str(reason or ""))
    if not fam or fam == "trade":
        return None
    base = fam.split("-")[-1].split("_")[-1]
    if any(o in fam.lower() for o in wd.OUTCOME_EXITS) or \
       any(o in base.lower() for o in wd.OUTCOME_EXITS):
        return None               # I7: selected on the outcome — not a bucket
    return fam


def features(bot, q, regime):
    """Every (feature, value) this closed trade belongs to.

    q is edge_audit.shape's row tuple: (pct, abs, closed_dt, opened_raw,
    extra, tag, pair, raw)."""
    raw = q[7]
    side = ea.side_of(raw)
    day = str(q[3])[:10] if q[3] else None
    g = regime.get(day)
    rg = "risk-ON" if g == 1 else ("risk-OFF" if g == -1 else "unknown")
    out = []
    if side:
        out.append(("side", side))
        out.append(("side x regime", f"{side} | {rg}"))
    hb = hold_band(q[4])
    if hb:
        out.append(("hold band", hb))
        if side:
            out.append(("side x hold", f"{side} | {hb}"))
    ex = exit_family(q[5] or raw.get("reason"))
    if ex:
        out.append(("exit", ex))
    return out


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------
def _t_from_se(mean, se):
    if se is None or not math.isfinite(se) or se <= 0:
        return float("nan")
    return mean / se


def _p_two_sided(t, dof):
    """Two-sided p from a t statistic. Pooled cells are tested in BOTH
    directions on purpose: this instrument exists to find losers as readily as
    winners, so a one-sided winners' test would be blind to exactly the class
    it found first."""
    if not math.isfinite(t) or dof < 1:
        return 1.0
    x = dof / (dof + t * t)
    return max(0.0, min(1.0, _betainc_half(0.5 * dof, 0.5, x)))


def _betainc_half(a, b, x):
    """Regularised incomplete beta I_x(a,b) by continued fraction — enough
    precision for a p-value. Standard Lentz; no scipy in these images."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    return front * (f - 1.0)


def grade_cell(vals, bots, days):
    """One pooled cell. Returns None below the floors — an underpowered cell is
    NOT a finding, and reporting it as one is how a fleet learns to ignore its
    own instruments."""
    n = len(vals)
    nb = len(set(bots))
    if n < MIN_CELL_N or nb < MIN_BOOKS:
        return None
    mean = st.mean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    t_iid = mean / (sd / math.sqrt(n)) if sd > 0 else float("nan")
    se_b, g_b, mx_b = gr.cluster_se(vals, bots)
    se_d, g_d, mx_d = gr.cluster_se(vals, days)
    t_b, t_d = _t_from_se(mean, se_b), _t_from_se(mean, se_d)
    # THE BINDING STATISTIC: the weaker of the two clusterings. A cell that one
    # book carries and a cell that one day carries are both fakes, and only the
    # minimum |t| refuses both.
    cand = [(x, g) for x, g in ((t_b, g_b), (t_d, g_d)) if math.isfinite(x)]
    if cand:
        t_bind, g_bind = min(cand, key=lambda xg: abs(xg[0]))
    else:
        t_bind, g_bind = float("nan"), min(g_b, g_d)
    # The dof belongs to WHICHEVER CLUSTERING BINDS, not to the smaller of the
    # two. The first draft used `min(g_b, g_d) - 1` and so priced a t that came
    # from 13 day-clusters against 2 degrees of freedom, inflating its p ~2x.
    # Over-conservative is still WRONG: it hides findings, and a grader that
    # silently under-reports is the failure this instrument exists to end.
    dof = max(1, g_bind - 1)
    return {"n": n, "books": nb, "days": len(set(days)),
            "mean_pct": mean * 100.0, "t_iid": t_iid,
            "t_book": t_b, "n_book": g_b, "max_book": mx_b,
            "t_day": t_d, "n_day": g_d, "max_day": mx_d,
            "t_binding": t_bind, "dof": dof,
            "p": _p_two_sided(t_bind, dof),
            "t_crit": fa.t_crit(min(g_b, g_d))}


def living_bases(books):
    """The era_base of every book publishing a row TODAY.

    WHY THE DEFAULT IS LIVING-ONLY. `edge_audit.shape` grades all 41 books the
    ledger has ever held, which is right for an audit and wrong for a claim
    about how the fleet trades NOW: the retained ledger contains Kraken-era
    rows, and `study_exit_attribution` already set this precedent in the fleet's
    own words -- "RETIRED rows are excluded by default: the ledger is history
    and a Kraken-era book measures +$272.09, the largest line in it". Measured
    here: the first run's ONLY BH survivor was `exit_long` +6.387%/trade, all
    but 4 of its 99 rows from the RETIRED `perps-donchian-breakout`."""
    out = set()
    for r in (books or []):
        b = r.get("bot") if isinstance(r, dict) else None
        if b:
            out.add(gr.era_base(str(b)))
    return out


def audit(shaped, regime, living=None):
    """living: the set of era_bases to grade, or None for every book.

    CLUSTERING IS BY STRATEGY, NOT BY ROW ID -- `golive_readiness.era_base`, the
    owner. `X`, `X-lighter` and `X-lshadow` are ONE strategy on three arms, and
    counting them as three independent clusters understates the SE of every
    cell they appear in. Measured on the first run: `exit_long` reported
    "across 3 books" and was `perps-donchian-breakout` plus its own two arms,
    95 of 99 rows on one of them. That is the same suffix hazard `era_base`
    exists for, reached from the clustering side rather than the era side."""
    cells = defaultdict(lambda: ([], [], []))
    for bot, v in shaped.items():
        base = gr.era_base(str(bot))
        if living is not None and base not in living:
            continue
        for q in v["rows"]:
            day = str(q[3])[:10] if q[3] else str(q[2])[:10]
            for feat, val in features(bot, q, regime):
                c = cells[(feat, val)]
                c[0].append(float(q[0]))
                c[1].append(base)
                c[2].append(day)
    graded = {}
    for key, (vals, bots, days) in cells.items():
        g = grade_cell(vals, bots, days)
        if g:
            graded[key] = g
    surv = wd.bh_survivors([(k, v["p"]) for k, v in graded.items()], fdr=FDR)
    for k, v in graded.items():
        v["bh"] = k in surv
    return graded


def report(graded, out=sys.stdout):
    print("=" * 96, file=out)
    print("FLEET POOLED GRADER — does a structural feature pay, pooled across "
          "every book that has it?", file=out)
    print(f"cells graded: {len(graded)}   floors: n>={MIN_CELL_N}, "
          f"books>={MIN_BOOKS}   multiplicity: BH at FDR {FDR}", file=out)
    print("=" * 96, file=out)
    hdr = (f"{'feature':<14} {'value':<22} {'n':>5} {'bk':>3} {'d':>3} "
           f"{'mean':>9} {'t_iid':>7} {'t_book':>7} {'t_day':>7} "
           f"{'BINDING':>8} {'BH':>3}")
    last = None
    for key in sorted(graded, key=lambda k: (k[0], -abs(graded[k]["t_binding"]))):
        v = graded[key]
        if key[0] != last:
            print(f"\n{hdr}", file=out)
            last = key[0]
        print(f"{key[0]:<14} {key[1]:<22} {v['n']:>5} {v['books']:>3} "
              f"{v['days']:>3} {v['mean_pct']:>+8.3f}% {v['t_iid']:>+7.2f} "
              f"{v['t_book']:>+7.2f} {v['t_day']:>+7.2f} "
              f"{v['t_binding']:>+8.2f} {'YES' if v['bh'] else '-':>3}", file=out)
    surv = [(k, v) for k, v in graded.items() if v["bh"]]
    print("\n" + "-" * 96, file=out)
    if not surv:
        print("NO CELL SURVIVES BH — nothing here is a fleet-wide claim.",
              file=out)
    else:
        print(f"SURVIVES BH at FDR {FDR} ({len(surv)}):", file=out)
        for k, v in sorted(surv, key=lambda kv: kv[1]["t_binding"]):
            d = "LOSES" if v["mean_pct"] < 0 else "PAYS "
            print(f"  {d}  {k[0]}={k[1]:<22} n={v['n']:>5} "
                  f"{v['mean_pct']:+.3f}%/trade  binding t={v['t_binding']:+.2f}"
                  f"  across {v['books']} books / {v['days']} days", file=out)
    print("-" * 96, file=out)
    print("ADVISORY. A pooled cell is evidence about a CLASS, never an "
          "instruction about a book:", file=out)
    print("pooling mixes books with different signals, so acting on a cell is "
          "a separate,", file=out)
    print("per-book, measured decision. This module moves no capital and "
          "writes no lever.", file=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ledger")
    ap.add_argument("--feed")
    ap.add_argument("--bus")
    ap.add_argument("--no-regime", action="store_true")
    ap.add_argument("--all-books", action="store_true",
                    help="include RETIRED books (default: living rows only)")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    trades, _books, _pub = ea.load(a.ledger, a.feed, a.bus)
    shaped = ea.shape(trades)
    regime = btc_regime_map(fetch=not a.no_regime)
    if not regime:
        print("[regime] UNAVAILABLE — every trade reads `unknown`; the regime "
              "cells below are not a split.", file=sys.stderr)
    living = None if a.all_books else living_bases(_books)
    if living is not None and not living:
        print("[books] pnl.json named NO living book — refusing to grade a "
              "sample I cannot scope (fail-closed).", file=sys.stderr)
        return 2
    graded = audit(shaped, regime, living)
    if a.json:
        print(json.dumps({f"{k[0]}|{k[1]}": v for k, v in graded.items()},
                         indent=2, sort_keys=True, default=float))
    else:
        report(graded)
    return 0


# ---------------------------------------------------------------------------
def _selftest():
    import ast
    src = open(os.path.abspath(__file__)).read()
    tree = ast.parse(src)

    # ADVISORY, asserted on the source (the fleet_allocation pattern): this
    # module may not write a lever, move capital, or open a market.
    banned = {"write_levers", "get_lever", "market_open", "publish",
              "apply_tuning", "set_allocation"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            nm = getattr(f, "attr", None) or getattr(f, "id", None)
            assert nm not in banned, f"advisory module calls {nm}"

    # (hj): the rules must be IMPORTED, never re-implemented here. A local def
    # of any owner's name is the second-copy defect.
    local = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for owned in ("cluster_se", "bh_survivors", "t_crit", "era_rows",
                  "shape", "side_of", "is_phantom_close", "era_base",
                  "split_reason"):
        assert owned not in local, f"{owned} must be imported, not redefined"
    assert gr.cluster_se is not None and wd.bh_survivors is not None
    assert fa.t_crit is not None and ea.side_of is not None

    # cluster_se is the owner and it is doing the work: 100 rows from ONE book
    # must not out-vote three books.
    vals = [0.01] * 100 + [-0.02, -0.03, -0.01]
    bots = ["a"] * 100 + ["b", "c", "d"]
    days = [f"d{i%7}" for i in range(103)]
    se_b, g_b, _ = gr.cluster_se(vals, bots)
    assert g_b == 4, g_b
    n_iid = len(vals)
    sd = st.stdev(vals)
    t_iid = st.mean(vals) / (sd / math.sqrt(n_iid))
    t_b = _t_from_se(st.mean(vals), se_b)
    assert abs(t_b) < abs(t_iid), (t_b, t_iid)

    # the binding statistic is the WEAKER clustering, not the average and not
    # the first one computed
    g = grade_cell(vals, bots, days)
    assert g is not None
    cands = [g["t_book"], g["t_day"]]
    assert abs(g["t_binding"] - min(cands, key=abs)) < 1e-12, g
    assert abs(g["t_binding"]) <= abs(g["t_iid"]) + 1e-9
    # the dof must belong to the clustering that BINDS, not to the smaller of
    # the two group counts (the first draft's defect: it priced a day-clustered
    # t against the book count's dof and inflated p)
    g_bind = g["n_book"] if g["t_binding"] == g["t_book"] else g["n_day"]
    assert g["dof"] == max(1, g_bind - 1), (g["dof"], g_bind, g)
    lop = grade_cell([0.01, -0.005] * 30,
                     ["a", "b", "c"] * 20,
                     [f"d{i}" for i in range(60)])
    assert lop is not None
    gb2 = lop["n_book"] if lop["t_binding"] == lop["t_book"] else lop["n_day"]
    assert lop["dof"] == max(1, gb2 - 1), lop

    # FLOORS refuse, rather than report, an underpowered cell
    assert grade_cell([0.01] * 10, ["a"] * 10, ["d"] * 10) is None, "n floor"
    assert grade_cell([0.01] * 50, ["a"] * 50, ["d"] * 50) is None, "book floor"
    ok = grade_cell([0.01, -0.02] * 20, ["a", "b", "c"] * 13 + ["a"],
                    [f"d{i}" for i in range(40)])
    assert ok is not None and ok["books"] == 3

    # p-value sanity: a big |t| is small p, t=0 is p=1, and it is TWO-SIDED so
    # a strong LOSER is as findable as a strong winner
    assert _p_two_sided(0.0, 30) > 0.99
    assert _p_two_sided(6.0, 30) < 0.01
    assert abs(_p_two_sided(-6.0, 30) - _p_two_sided(6.0, 30)) < 1e-12
    assert _p_two_sided(2.045, 29) < 0.06 and _p_two_sided(2.045, 29) > 0.04

    # features: side comes from the OWNER, and unknown regime is its own cell
    row = {"side": "short", "reason": "short-snap_conv", "pnl_pct": -0.01}
    q = (-0.01, -1.0, None, "2026-09-01T00:00:00", {"held_h": 2.0},
         "short-snap_conv", "X", row)
    f = dict(features("b", q, {"2026-09-01": 1}))
    assert f["side"] == "short" and f["side x regime"] == "short | risk-ON"
    assert f["hold band"] == "1-4h" and f["exit"] == "conv"
    f2 = dict(features("b", q, {}))
    assert f2["side x regime"] == "short | unknown", f2
    # a trade with no readable side contributes NO side cell rather than a guess
    q2 = (0.01, 1.0, None, "2026-09-01T00:00:00", {}, "weird", "X",
          {"reason": "weird", "pnl_pct": 0.01})
    assert not [k for k, _ in features("b", q2, {}) if k.startswith("side")]

    # hold_band / exit_family are None-safe and refuse junk
    assert hold_band(None) is None and hold_band({"held_h": "x"}) is None
    assert hold_band({"held_h": float("nan")}) is None
    assert hold_band({"held_h": 0.5}) == "<1h"
    assert hold_band({"held_h": 1000.0}) == ">3d"
    # exit_family uses the OWNERS: split_reason for the split, OUTCOME_EXITS
    # for the I7 screen. Each of these is a real string from the live ledger
    # that the hand-rolled first draft got wrong.
    assert exit_family(None) is None
    assert exit_family("short-funding") is None      # no exit part -> "trade"
    assert exit_family("long_exit_long") == "exit_long"   # was "long"
    assert exit_family("long_range_high") == "range_high"  # was "high"
    assert exit_family("long-snap_conv") == "conv"
    # I7: outcome-conditioned families are REFUSED, including the one whose
    # last token ("loss") hides that it is a stop
    for tautology in ("long-dip_tp", "short-disloc_sl", "long-x_roi",
                      "long-trend-breakout_trailing_stop_loss",
                      "long-range-on_range_top", "long_stop",
                      "long-dip-in-uptrend_sell_into_strength"):
        assert exit_family(tautology) is None, tautology

    # regime map is FAIL-CLOSED: no fetch -> {} -> every trade reads unknown
    assert btc_regime_map(fetch=False) == {}

    # end-to-end on a synthetic fleet: a feature carried by ONE book must not
    # survive, while the same effect spread over many books does
    shaped = {}
    for b in range(6):
        rows = []
        for i in range(12):
            r = {"side": "short", "reason": "short-x_conv", "pnl_pct": -0.02}
            rows.append((-0.02, -1.0, None, f"2026-08-{(i % 27) + 1:02d}"
                         "T00:00:00", {"held_h": 2.0}, "short-x_conv", "P", r))
        shaped[f"book{b}"] = {"rows": rows}
    g = audit(shaped, {})
    assert ("side", "short") in g, list(g)
    assert g[("side", "short")]["books"] == 6
    assert g[("side", "short")]["mean_pct"] < 0
    one = {"solo": {"rows": [(-0.02, -1.0, None, "2026-08-01T00:00:00",
                              {"held_h": 2.0}, "short-x_conv", "P",
                              {"side": "short", "reason": "short-x_conv"})
                             ] * 200}}
    g1 = audit(one, {})
    assert ("side", "short") not in g1, "a one-book cell must not be graded"

    # ARMS OF ONE STRATEGY ARE ONE CLUSTER. This is the defect the first live
    # run shipped: `X`, `X-lighter`, `X-lshadow` counted as three books and
    # cleared the MIN_BOOKS floor on what is one strategy.
    arms = {}
    for suf in ("", "-lighter", "-lshadow"):
        arms["perps-donchian-breakout" + suf] = {"rows": [
            (0.05, 1.0, None, f"2026-08-{(i % 27) + 1:02d}T00:00:00",
             {"held_h": 2.0}, "long-x_conv", "P",
             {"side": "long", "reason": "long-x_conv"}) for i in range(40)]}
    g_arms = audit(arms, {})
    assert ("side", "long") not in g_arms, \
        "three arms of one strategy must not clear the MIN_BOOKS floor"
    assert gr.era_base("perps-donchian-breakout-lshadow") == \
        gr.era_base("perps-donchian-breakout"), "arms must share a base"

    # living_bases scopes by era_base and is fail-closed on an empty feed
    lb = living_bases([{"bot": "freqtrade-mum-lshadow"}, {"bot": "book-x"}])
    assert gr.era_base("freqtrade-mum-lshadow") in lb and "book-x" in lb
    assert living_bases([]) == set() and living_bases(None) == set()
    kept = audit(arms, {}, living=set())
    assert kept == {}, "an empty living set must grade nothing"
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
