#!/usr/bin/env python3
"""study_regime_veto_identifiability_2026-09-09.py — is the regime short-veto a
REGIME finding, or a SIDE cut wearing a regime label?

WHY. `scripts/study_regime_short_veto_2026-09-02.py` is the pre-registered
instrument for the edge audit's hypothesis #3 (veto shorts opened in the
oracle's `LONG-window`, longs in `SHORT-window`). Its `decide()` compares the
VETOED set against the PASSED set. On 9-Sep the fresh read returned `confirmed`
on 🚀 bezos and `undecided` on 🪁 kelly by 0.007pp — and on every book that
reached the n floor the vetoed set was ~ENTIRELY one side:

    kelly  fresh: veto = 73 shorts + 0 longs ; pass = 2 shorts + 182 longs
    bezos  fresh: veto = 31 shorts + 0 longs ; pass = 0 shorts +   6 longs

BTC read `LONG-window` on essentially every snapshot of the fresh window, so
"short in LONG-window" and "short" are the same predicate there. A comparison
of vetoed-vs-passed is then a comparison of shorts-vs-longs, and this fleet has
ALREADY measured that (EDGE_AUDIT §1b: every mixed book's loss is its short
side) and already refused acting on it (the 2-Sep expansion log: kelly's short
side is undecidable by tail — t=-4.32 -> -1.35 -> -0.52 as the outcome-
conditioned exits and the three worst closes are put back).

So the registered rule can `confirm` on a book while the oracle contributes no
information at all. That is not a defect in the registration — it declared this
exposure itself ("the `pass` set for crypto shorts is empty") — it is a
CONFOUND that has to be measured before either verdict is read.

WHAT THIS MEASURES. Two things the parent instrument does not:

  1. COLLINEARITY. Cramer's V between the label (veto/pass) and the side
     (long/short) per book. V = 1.0 means the label IS the side and the read
     carries zero regime information, whatever its verdict says.

  2. THE IDENTIFIED COMPARISON — within ONE side, does the label separate?
     `veto` minus `pass` inside shorts, and inside longs, per book, n-weighted
     across every cell where BOTH labels reach MIN_CELL. Under the hypothesis
     this is NEGATIVE (trades against the regime do worse). Under "the label is
     just the side" it is ~0.

  3. THE ROTATED-LABEL NULL. A scatter null that relabels at random is too
     easy: a regime verdict is autocorrelated in time, so a real label removes
     a CONTIGUOUS block. The honest null circularly ROTATES the oracle's whole
     verdict series against its own timestamps — identical marginal
     frequencies, identical autocorrelation, no relationship to returns — and
     re-runs the entire within-side procedure. (The null is not invented here:
     it is the one `scripts/study_regime_split_2026-09-07.py` used to refuse
     the long-side regime filter on the two real-money books.)

CALIBRATION (I3 — an instrument that cannot recover a planted effect may not
report its absence). `--selftest` plants a within-shorts regime effect and
requires it to be recovered at P <= 0.05, runs a placebo with the effect
removed and requires it NOT to be, and pins that rotation preserves the
verdict histogram exactly.

WHAT THIS DOES NOT DO. It vetoes nothing, moves no lever, changes no book,
resets no era, and it does NOT re-decide the pre-registered read — that rule
belongs to the parent instrument and its verdict on the fresh sample stands as
that instrument reports it. This measures whether that verdict is identified.

    python3 scripts/study_regime_veto_identifiability_2026-09-09.py --selftest
    python3 scripts/study_regime_veto_identifiability_2026-09-09.py            # fresh window
    python3 scripts/study_regime_veto_identifiability_2026-09-09.py --pooled   # full history
"""
from __future__ import annotations

import argparse
import bisect
import importlib.util
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402  (load_trades/shape/side_of)


def _load_parent():
    """The parent instrument, by PATH — its filename is not an identifier.
    Imported so `verdict_at`/`label`/`_bounds`/`load_oracle` have exactly ONE
    owner: a second copy of a rule is a second rule."""
    p = os.path.join(HERE, "study_regime_short_veto_2026-09-02.py")
    spec = importlib.util.spec_from_file_location("_regime_short_veto", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SV = _load_parent()

MIN_CELL = 10          # fleet_allocation.MIN_N — a mean from fewer is not a mean
DRAWS = 2000           # rotation draws
SIDES = ("short", "long")


# ------------------------------------------------------------ labelling

def anchor(shaped, oracle, since=None, bots=None):
    """Precompute, ONCE, everything a rotation cannot change.

    A circular rotation moves the verdict PAYLOADS and leaves the timestamps
    where they are, so each close's oracle index — the `bisect` result the
    parent's `verdict_at` computes — is INVARIANT across every draw. Anchoring
    it here turns each null draw from a 3,000-element bisect per close into an
    O(1) lookup, and is the only reason 2,000 draws is affordable.

    Returns {bot: [(idx, opened, coin, side, quad)]}.
    """
    times = [o[0] for o in oracle]
    out = {}
    for bot, d in sorted(shaped.items()):
        if bots and bot not in bots:
            continue
        rows = []
        for q in d["rows"]:
            opened = SV._ts(q[3])
            if opened is None or (since is not None and opened <= since):
                continue
            side = ea.side_of(q[7] if len(q) > 7 else {})
            if side not in SV.VETO_MAP:
                continue
            i = bisect.bisect_right(times, opened) - 1
            rows.append((i, opened, str(q[6] or "").split("/")[0], side, q))
        if rows:
            out[bot] = rows
    return out


def labelled(anchored, oracle, k=0):
    """{bot: [(side, label, quad)]} for the oracle rotated by `k`.

    The verdict is read through the PARENT's own `verdict_at` on the single
    snapshot that close resolved to — same staleness rule, same own/btc-proxy
    precedence, same KNOWN set. One owner for the rule (I3/(hj))."""
    n = len(oracle)
    out = {}
    for bot, rows in anchored.items():
        got = []
        for i, opened, coin, side, q in rows:
            if i < 0:
                continue
            snap = (oracle[i][0], oracle[(i + k) % n][1], None)
            v, _why = SV.verdict_at([snap], coin, opened)
            lab = SV.label(side, v)
            if lab is not None:
                got.append((side, lab, q))
        if got:
            out[bot] = got
    return out


# ------------------------------------------------------------ statistics

def cramers_v(rows):
    """Cramer's V between label and side on one book. 1.0 = the label IS the
    side (a 2x2 table, so V is |phi|). None when a margin is degenerate."""
    tab = defaultdict(int)
    for side, lab, _q in rows:
        tab[(side, lab)] += 1
    n = sum(tab.values())
    sides = sorted({s for s, _ in tab})
    labs = sorted({l for _, l in tab})
    if n == 0 or len(sides) < 2 or len(labs) < 2:
        return None, dict(tab), n
    chi2 = 0.0
    for s in sides:
        rs = sum(tab[(s, l)] for l in labs)
        for l in labs:
            cs = sum(tab[(x, l)] for x in sides)
            exp = rs * cs / n
            if exp > 0:
                chi2 += (tab[(s, l)] - exp) ** 2 / exp
    k = min(len(sides), len(labs)) - 1
    return math.sqrt(chi2 / (n * k)), dict(tab), n


def _mean_pct(quads):
    """Mean per-trade return in PERCENT, through the parent's own bounds
    helper (which goes through `golive_readiness.stats`)."""
    b = SV._bounds(quads)
    return b.get("mean_pct"), b.get("n", 0), b.get("se_pct")


def within_side_cells(rows, min_cell=MIN_CELL):
    """[(side, n_veto, mean_veto, se_veto, n_pass, mean_pass, se_pass)] for
    sides where BOTH labels reach min_cell — the identified comparison."""
    by = defaultdict(lambda: defaultdict(list))
    for side, lab, q in rows:
        by[side][lab].append(q)
    cells = []
    for side in SIDES:
        v, p = by[side].get("veto", []), by[side].get("pass", [])
        if len(v) < min_cell or len(p) < min_cell:
            continue
        mv, nv, sv = _mean_pct(v)
        mp, np_, sp = _mean_pct(p)
        if mv is None or mp is None:
            continue
        cells.append((side, nv, mv, sv, np_, mp, sp))
    return cells


def weighted_diff(cells):
    """Precision-weighted mean of (veto - pass) across cells, in pp/trade.
    Weight = 1/(se_v^2 + se_p^2) — inverse variance of each difference, so a
    cell measured badly cannot dominate. Falls back to 1/(1/nv+1/np) when a
    cell has no SE. NEGATIVE supports the hypothesis."""
    num = den = 0.0
    for _side, nv, mv, sv, np_, mp, sp in cells:
        if sv and sp:
            w = 1.0 / (sv * sv + sp * sp)
        elif nv and np_:
            w = 1.0 / (1.0 / nv + 1.0 / np_)
        else:
            continue
        num += w * (mv - mp)
        den += w
    return (num / den) if den else None


def rotate(oracle, k):
    """Circularly shift the verdict payloads against their own timestamps.
    Marginal frequencies and autocorrelation are preserved EXACTLY; the
    relationship to returns is destroyed."""
    n = len(oracle)
    if n == 0:
        return oracle
    k %= n
    return [(oracle[i][0], oracle[(i + k) % n][1], oracle[i][2]) for i in range(n)]


def run(shaped, oracle, since=None, bots=None, draws=DRAWS, seed=11,
        min_cell=MIN_CELL):
    """Observed within-side statistic + the rotated-label null."""
    anchored = anchor(shaped, oracle, since=since, bots=bots)
    obs_rows = labelled(anchored, oracle, 0)
    per_book, all_cells = {}, []
    for bot, rows in obs_rows.items():
        v, tab, n = cramers_v(rows)
        cells = within_side_cells(rows, min_cell)
        all_cells.extend(cells)
        per_book[bot] = {
            "n_labelled": n, "cramers_v": (round(v, 3) if v is not None else None),
            "table": {f"{s}/{l}": c for (s, l), c in sorted(tab.items())},
            "cells": [{"side": s, "n_veto": nv, "mean_veto_pct": mv,
                       "n_pass": np_, "mean_pass_pct": mp,
                       "diff_pp": round(mv - mp, 4)}
                      for s, nv, mv, _sv, np_, mp, _sp in cells],
        }
    observed = weighted_diff(all_cells)

    rnd = random.Random(seed)
    n_or = len(oracle)
    null, valid = [], 0
    for _ in range(draws):
        k = rnd.randrange(1, n_or) if n_or > 1 else 0
        cells = []
        for bot, rows in labelled(anchored, oracle, k).items():
            cells.extend(within_side_cells(rows, min_cell))
        d = weighted_diff(cells)
        if d is not None:
            null.append(d)
            valid += 1
    p = None
    if observed is not None and valid >= 50:
        # one-sided: how often does a label with no information look at least
        # this favourable to the hypothesis (i.e. at least this negative)?
        p = round(sum(1 for d in null if d <= observed) / valid, 4)
    null_sorted = sorted(null)

    def q(f):
        return round(null_sorted[int(f * (len(null_sorted) - 1))], 4) if null_sorted else None

    return {
        "since": since.isoformat() if since else None,
        "min_cell": min_cell,
        "observed_diff_pp": (round(observed, 4) if observed is not None else None),
        "n_cells": len(all_cells),
        "cells": [{"side": s, "n_veto": nv, "mean_veto_pct": mv, "n_pass": np_,
                   "mean_pass_pct": mp, "diff_pp": round(mv - mp, 4)}
                  for s, nv, mv, _sv, np_, mp, _sp in all_cells],
        "null": {"draws": draws, "valid": valid, "p_one_sided": p,
                 "p05": q(0.05), "p50": q(0.50), "p95": q(0.95)},
        "books": per_book,
    }


def render(res):
    L = [f"# regime-veto IDENTIFIABILITY — window since {res['since'] or 'ALL'}",
         "",
         "## 1. Is the label the side? (Cramer's V; 1.0 = the label IS the side)",
         "", "| book | labelled | V | table |", "|---|---:|---:|---|"]
    for bot, b in sorted(res["books"].items(), key=lambda kv: -(kv[1]["n_labelled"])):
        if b["n_labelled"] < MIN_CELL:
            continue
        L.append(f"| {bot} | {b['n_labelled']} | {b['cramers_v']} | "
                 + ", ".join(f"{k} {v}" for k, v in b["table"].items()) + " |")
    L += ["", "## 2. The identified comparison — within ONE side",
          f"(cells with both labels at n>={res['min_cell']})", "",
          "| book | side | veto n | veto mean% | pass n | pass mean% | diff pp |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for bot, b in sorted(res["books"].items()):
        for c in b["cells"]:
            L.append(f"| {bot} | {c['side']} | {c['n_veto']} | {c['mean_veto_pct']:+.3f} | "
                     f"{c['n_pass']} | {c['mean_pass_pct']:+.3f} | {c['diff_pp']:+.3f} |")
    n = res["null"]
    L += ["", "## 3. The rotated-label null",
          f"observed within-side diff (veto - pass): **{res['observed_diff_pp']:+.4f} pp/trade** "
          f"over {res['n_cells']} cells" if res["observed_diff_pp"] is not None
          else "observed: — (no identified cell)",
          f"rotated null: {n['valid']}/{n['draws']} valid draws · "
          f"p05 {n['p05']} · median {n['p50']} · p95 {n['p95']}",
          f"**P(a no-information label looks at least this good) = {n['p_one_sided']}**"]
    return "\n".join(L)


# ------------------------------------------------------------ selftest

def _synth(planted=True, seed=5, n=400):
    """An oracle whose BTC verdict alternates in BLOCKS (so rotation is a real
    null) and a ledger of SHORTS ONLY, so nothing can be explained by side."""
    rnd = random.Random(seed)
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    oracle = []
    for h in range(0, 900):
        v = "LONG-window" if (h // 50) % 2 == 0 else "SHORT-window"
        oracle.append((t0 + timedelta(hours=h), {"BTC": {"verdict": v}}, "x"))
    rows = []
    for i in range(n):
        opened = t0 + timedelta(hours=rnd.uniform(0.5, 890))
        h = int((opened - t0).total_seconds() // 3600)
        against = (h // 50) % 2 == 0          # short in LONG-window
        mu = (-0.020 if against else 0.004) if planted else 0.0
        pct = rnd.gauss(mu, 0.020)
        closed = opened + timedelta(hours=rnd.uniform(1, 6))
        r = {"side": "short", "reason": "short-x_hold", "pair": "ETH/USDC"}
        rows.append((pct, pct * 100, closed, opened.isoformat(), None,
                     r["reason"], "ETH/USDC", r))
    rows.sort(key=lambda q: q[2])
    return oracle, {"synth": {"rows": rows}}


def _selftest():
    # rotation preserves the verdict histogram EXACTLY
    oracle, shaped = _synth()
    def hist(o):
        c = defaultdict(int)
        for _, p, _ in o:
            c[p["BTC"]["verdict"]] += 1
        return dict(c)
    assert hist(rotate(oracle, 137)) == hist(oracle), "rotation changed the marginals"
    assert [o[0] for o in rotate(oracle, 3)] == [o[0] for o in oracle], "timestamps moved"

    # Cramer's V: a label that IS the side reads 1.0; an orthogonal one ~0
    same = [("short", "veto", None)] * 40 + [("long", "pass", None)] * 40
    v, _t, _n = cramers_v(same)
    assert v is not None and v > 0.99, v
    orth = ([("short", "veto", None)] * 25 + [("short", "pass", None)] * 25
            + [("long", "veto", None)] * 25 + [("long", "pass", None)] * 25)
    v2, _t, _n = cramers_v(orth)
    assert v2 is not None and v2 < 0.01, v2

    # THE OPTIMISATION IS EQUIVALENT TO THE NAIVE PATH, at every rotation
    # tested. `anchor` freezes each close's oracle index because rotation moves
    # payloads and not timestamps; if that ever stops being true this fails.
    anchored = anchor(shaped, oracle)
    for k in (0, 1, 137, 449, len(oracle) - 1):
        fast = labelled(anchored, oracle, k)
        rot = rotate(oracle, k)
        slow = {}
        for bot, rows in anchored.items():
            got = []
            for _i, opened, coin, side, q in rows:
                v, _w = SV.verdict_at(rot, coin, opened)
                lab = SV.label(side, v)
                if lab is not None:
                    got.append((side, lab, q))
            if got:
                slow[bot] = got
        assert ({b: [(s, l) for s, l, _ in r] for b, r in fast.items()}
                == {b: [(s, l) for s, l, _ in r] for b, r in slow.items()}), \
            f"anchored labelling disagrees with the naive rotation at k={k}"

    # POSITIVE CONTROL: a planted within-shorts regime effect is recovered
    got = run(shaped, oracle, draws=300, seed=3)
    assert got["n_cells"] == 1, got["n_cells"]
    assert got["observed_diff_pp"] < -1.0, got["observed_diff_pp"]
    assert got["null"]["p_one_sided"] is not None and got["null"]["p_one_sided"] <= 0.05, got["null"]
    # and the book is NOT collinear — one side only, so V is undefined, and the
    # finding therefore cannot be a side cut
    assert got["books"]["synth"]["cramers_v"] is None

    # PLACEBO: no planted effect -> not significant, and the null brackets it
    oracle_p, shaped_p = _synth(planted=False, seed=9)
    gp = run(shaped_p, oracle_p, draws=300, seed=3)
    assert gp["null"]["p_one_sided"] is None or gp["null"]["p_one_sided"] > 0.05, gp["null"]
    assert abs(gp["observed_diff_pp"]) < 1.0, gp["observed_diff_pp"]

    # the weighting cannot be dominated by a badly measured cell
    cells = [("short", 100, -1.0, 0.05, 100, 0.0, 0.05),
             ("long", 12, +9.0, 5.00, 12, 0.0, 5.00)]
    d = weighted_diff(cells)
    assert d is not None and d < -0.9, d

    # a cell below the floor is not an identified comparison — BOTH halves of
    # the floor are pinned, because an adversarial review found the pass-side
    # half unexercised: the veto arm alone stayed green against a mutation
    # that deleted the pass-side check.
    thin = [("short", "veto", q) for q in shaped["synth"]["rows"][:5]]
    thin += [("short", "pass", q) for q in shaped["synth"]["rows"][5:200]]
    assert within_side_cells(thin, MIN_CELL) == [], "veto-side floor"
    thin_pass = [("short", "veto", q) for q in shaped["synth"]["rows"][:195]]
    thin_pass += [("short", "pass", q) for q in shaped["synth"]["rows"][195:200]]
    assert within_side_cells(thin_pass, MIN_CELL) == [], "pass-side floor"
    # exactly AT the floor on both sides IS a cell (the boundary, both ways)
    at_floor = [("short", "veto", q) for q in shaped["synth"]["rows"][:MIN_CELL]]
    at_floor += [("short", "pass", q) for q in shaped["synth"]["rows"][MIN_CELL:2 * MIN_CELL]]
    assert [c[0] for c in within_side_cells(at_floor, MIN_CELL)] == ["short"]

    # `since` EXCLUDES closes opened at or before it — the fresh-window filter
    # the registered read depends on, and unpinned until an adversarial review
    # named it. Anchoring is where it lives, so drive it there.
    all_rows = anchor(shaped, oracle)["synth"]
    cut = sorted(r[1] for r in all_rows)[len(all_rows) // 2]
    fresh = anchor(shaped, oracle, since=cut).get("synth", [])
    assert len(fresh) < len(all_rows), "since did not filter anything"
    assert all(r[1] > cut for r in fresh), "since admitted a close at or before it"
    assert len(fresh) == sum(1 for r in all_rows if r[1] > cut)

    print("study_regime_veto_identifiability selftest OK — rotation preserves "
          "marginals and timestamps, Cramer's V pins the collinear and the "
          "orthogonal case, planted within-side effect recovered at P<=0.05, "
          "placebo not recovered, inverse-variance weighting, floor enforced")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--oracle-json")
    ap.add_argument("--bus-json")
    ap.add_argument("--hours", type=float, default=SV.MAX_HOURS)
    ap.add_argument("--pooled", action="store_true",
                    help="the whole history, not just the registration window")
    ap.add_argument("--bots")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--min-cell", type=int, default=MIN_CELL)
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    trades = ea.load_trades(a.ledger, a.limit)
    shaped = ea.shape(trades)
    oracle, used = SV.load_oracle(a.oracle_json, a.bus_json, a.hours)
    if not oracle:
        print("REFUSING: no oracle history — nothing to label against (I1)")
        return 2
    since = None if a.pooled else SV._ts(SV.PRE_REGISTERED["since"])
    res = run(shaped, oracle, since=since,
              bots=set(a.bots.split(",")) if a.bots else None,
              draws=a.draws, min_cell=a.min_cell)
    res["oracle"] = {"source": used, "n_snapshots": len(oracle)}
    print(render(res))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
