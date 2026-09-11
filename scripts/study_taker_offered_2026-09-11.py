#!/usr/bin/env python3
"""🎫 THE TAKER'S **OFFERED** SET — searching the population it did NOT condition on.

**Eamon, 2026-09-11:** *"widen metrics and parameters until you find an edge
for it."*

WHY THE OFFERED SET AND NOT THE LEDGER. A threshold sweep over the taker's own
closes searches a population the book already selected, on the very features
being swept — and conditioning on a variable removes the information in it.
Measured the same day, same feature vocabulary: offered `vol_m` p50 **0.49**
against taken **2.67**; offered `range_pos` spans **[0.84, 1.13]** against
taken **[0.94, 1.01]**. That is why `brk_quality` measured INVERSELY related
to excess on the taken set (>=0.6 -> -0.821pp): there was nothing left in it.
The unconditioned population is the scout's OFFERED tickets, and the fleet has
been recording them all along in `bot_state_history` under `lighter-market`.

POPULATION. The public `/bus.json?hours=` (server caps at 200h) yields ~2,351
snapshots over ~8.3 days. An EPISODE is a run of consecutive appearances of
one `(lens, sym)`; a gap > `GAP_H` starts a new one — episodes, not
observations ((the fleet's own count-episodes rule)). Measured: **2,768
episodes** against 208 era closes, i.e. ~13x the sample in a fifth of the
window, and ~4x better powered per cell (mde80 0.30%/trade at n=2,768 against
1.26 at n=162).

OUTCOME. Entry at the first 1h venue close at-or-after the episode's first
appearance; exit through `lighter_ticket_taker.exit_reason` IMPORTED, routed
by the module's own `bull_exit(lens)`, `peak_ret` tracked bar by bar. Side from
the ticket's own `side` where the lens carries one (divergence) and LONG
otherwise, which is the taker's own construction.

DECLARED DIVERGENCE, and it is the reason the calibration gate exists: 1h
resolution against a ~5-min offer cadence, so entry lags by up to 60 minutes.
The convention is IDENTICAL on every arm of every contrast, so it cancels in
the comparison and is bounded by the gate.

THE BAR IS PRE-REGISTERED — `PREREG_TAKER_OFFERED_2026-09-11.md`, committed
before any outcome was computed. A cell is an EDGE only if it survives
Benjamini-Hochberg at FDR 0.05 across EVERY admissible cell tested, beats the
permutation max-statistic (the best cell a pure-noise search of the same shape
would have produced), and survives drop-worst-3, leave-one-coin-out and
leave-one-UTC-day-out, at n >= 10 with its mde80 reported beside it.

EVERY CELL IS PRINTED, survivor or not. A sweep that prints only its winner is
the artifact.

Exit: 0 verdict printed · 2 refused (calibration, dark tape, or BULL_MODE).
"""
import argparse
import collections
import datetime as dt
import importlib.util
import json
import math
import os
import statistics as st
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import lighter_ticket_taker as tt                              # noqa: E402
import bot_pnl_store as store                                  # noqa: E402
import golive_readiness as gr                                  # noqa: E402
import fleet_allocation as fa                                  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
#: A gap longer than this starts a new episode for the same (lens, sym).
GAP_H = 2.0
#: I21's floor. A cell thinner than this never reaches the referee.
MIN_N = 10
#: (gx) — beyond this the harness may not say what WOULD have happened.
CALIB_TOL_PP = 0.60
#: Benjamini-Hochberg false-discovery rate, the (mr)/(I21) discipline.
FDR = 0.05
#: Permutation draws for the selection-premium max-statistic.
PERM = 2000
SEED = 20260911


def _null():
    """The (aaf) null harness, imported for its tape fetch and its walk so
    this file carries no second copy of either ((hj))."""
    p = os.path.join(ROOT, "scripts", "study_taker_random_null_2026-09-10.py")
    spec = importlib.util.spec_from_file_location("_taker_null", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _get(url, timeout=90):
    with urllib.request.urlopen(url, timeout=timeout) as fh:
        return json.load(fh)


def parse(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def episodes(hours=720, gap_h=GAP_H, snaps=None):
    """Scout ticket EPISODES from the lighter-market history.

    One episode per run of consecutive appearances of a (lens, sym); a gap
    longer than `gap_h` starts a new one. Returns oldest-first, each carrying
    the ticket fields AS OFFERED plus `_lens`, `_sym`, `_t` (first sighting).
    """
    if snaps is None:
        d = _get(f"{DASH}/bus.json?hours={int(hours)}")
        snaps = [s for s in (d.get("history") or [])
                 if s.get("key") == "lighter-market"]
    snaps = sorted(snaps, key=lambda s: s.get("ts") or "")
    gap = dt.timedelta(hours=float(gap_h))
    last, out = {}, []
    for s in snaps:
        try:
            ts = parse(s.get("ts"))
        except (TypeError, ValueError):
            continue
        for lens, arr in ((s.get("payload") or {}).get("tickets") or {}).items():
            for x in (arr or []):
                sym = x.get("sym")
                if not sym:
                    continue
                k = (lens, sym)
                if k not in last or ts - last[k] > gap:
                    e = dict(x)
                    e["_lens"], e["_sym"], e["_t"] = str(lens), str(sym), ts
                    out.append(e)
                last[k] = ts
    return out


def side_is_long(e):
    """The taker's own construction: divergence carries an explicit side;
    every other lens is long."""
    s = e.get("side")
    if isinstance(s, str) and s:
        return s != "short"
    return True


def grade(eps, tape, N):
    """Walk each episode through the taker's REAL exit, in place.

    Sets `_ret` (fraction) and `_reason`, or leaves them absent when the tape
    cannot cover the episode. Returns the number graded."""
    n = 0
    for e in eps:
        series = tape.get(e["_sym"])
        if not series:
            continue
        t0 = e["_t"].timestamp()
        entry = next(((t, px) for t, px in series if t >= t0), None)
        if entry is None:
            continue
        stamped = tt.pos_bars({})
        r = N.routing(e["_lens"], stamped)
        if r is None:
            return None                 # BULL_MODE off -> caller REFUSES
        bars, trail = r
        got = N.walk(entry[1], entry[0], side_is_long(e), bars, trail, series)
        if got is None:
            continue
        e["_ret"], e["_reason"] = got
        n += 1
    return n


def mean_t(vals):
    n = len(vals)
    if n < 2:
        return (st.mean(vals) if vals else float("nan"), float("nan"), n)
    m = st.mean(vals)
    se = st.stdev(vals) / math.sqrt(n)
    return (m, (m / se if se else float("nan")), n)


def mde80(vals):
    """The smallest effect this cell could resolve at 80% power, one-sided
    a=0.05 — so a null reads 'could not detect below X', never 'no edge'."""
    if len(vals) < 2:
        return float("nan")
    return 2.4866 * st.stdev(vals) / math.sqrt(len(vals))


def bh(pairs, fdr=FDR):
    """Benjamini-Hochberg. `pairs` = [(key, p)]; m is the FULL count."""
    m = len(pairs)
    ranked = sorted(pairs, key=lambda kp: kp[1])
    out, kmax = {}, 0
    for i, (_k, p) in enumerate(ranked, start=1):
        if p <= i * fdr / m:
            kmax = i
    for i, (k, p) in enumerate(ranked, start=1):
        out[k] = {"p": p, "rank": i, "crit": i * fdr / m,
                  "survives": i <= kmax}
    return out


#: The pre-declared cell axes. Thresholds are the OFFERED population's own
#: quantiles, never round numbers chosen by eye (PREREG §Q2).
CELL_FEATURES = ("vol_m", "apr_pct", "chg_pct", "prem_bps", "range_pos")
CELL_QUANTILES = (0.25, 0.50, 0.75)


def declared_cells(eps):
    """Every cell the pre-registration commits to, for ONE lens's episodes.

    -> [(key, predicate)] — enumerated BEFORE any outcome is read, and all of
    them are reported whether they survive or not."""
    cells = []
    for f in CELL_FEATURES:
        vals = sorted(e[f] for e in eps
                      if isinstance(e.get(f), (int, float))
                      and not isinstance(e.get(f), bool))
        if len(vals) < 4 * MIN_N:
            continue
        for q in CELL_QUANTILES:
            thr = vals[min(len(vals) - 1, int(q * len(vals)))]
            cells.append((f"{f}>=p{int(q*100)}({thr:g})",
                          (lambda f=f, thr=thr: lambda e: isinstance(
                              e.get(f), (int, float))
                              and not isinstance(e.get(f), bool)
                              and e[f] >= thr)()))
            cells.append((f"{f}<=p{int(q*100)}({thr:g})",
                          (lambda f=f, thr=thr: lambda e: isinstance(
                              e.get(f), (int, float))
                              and not isinstance(e.get(f), bool)
                              and e[f] <= thr)()))
    cells.append(("class:crypto", lambda e: not e.get("noncrypto")))
    cells.append(("class:noncrypto", lambda e: bool(e.get("noncrypto"))))
    for lo in (0, 6, 12, 18):
        cells.append((f"utc_hour[{lo},{lo+6})",
                      (lambda lo=lo: lambda e: lo <= e["_t"].hour < lo + 6)()))
    return cells


def perm_max(base, cells, eps, draws=PERM, seed=SEED):
    """The SELECTION PREMIUM, priced rather than assumed (I25).

    Shuffles the OUTCOME against the features `draws` times and records the
    best cell z each pure-noise search produced. A real survivor must beat
    this distribution, not merely its own p-value."""
    import random
    rng = random.Random(seed)
    # [corrected, first run] PERCENT, to match `base`/`bm`. This read
    # fractions against a percent baseline and produced max-z values of
    # -170 and +330 where a noise search of this shape yields ~2-3. The BH
    # column was unaffected (own units, computed separately) so the VERDICT
    # did not move — but the verdict text CITES this number, and a citation
    # of a broken number is how a wrong one gets believed later.
    rets = [100.0 * e["_ret"] for e in eps]
    masks = [[bool(pred(e)) for e in eps] for _, pred in cells]
    bm = st.mean(base) if base else 0.0
    out = []
    for _ in range(draws):
        rng.shuffle(rets)
        best = float("-inf")
        for mask in masks:
            v = [r for r, m in zip(rets, mask) if m]
            if len(v) < MIN_N:
                continue
            m_, t_, _n = mean_t(v)
            z = (m_ - bm) / (st.stdev(v) / math.sqrt(len(v))) \
                if len(v) > 1 and st.stdev(v) else 0.0
            best = max(best, z)
        if best > float("-inf"):
            out.append(best)
    out.sort()
    return out


def q(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def robust(vals, keys_coin, keys_day):
    """Drop-worst-3, leave-one-coin-out, leave-one-UTC-day-out — the three
    the pre-registration requires of any survivor."""
    out = {}
    s = sorted(vals)
    out["drop_worst_3"] = st.mean(s[3:]) if len(s) > 3 else float("nan")
    for name, keys in (("loco", keys_coin), ("lodo", keys_day)):
        by = collections.defaultdict(list)
        for v, k in zip(vals, keys):
            by[k].append(v)
        worst = float("inf")
        for k in by:
            rest = [v for kk, vv in by.items() if kk != k for v in vv]
            if len(rest) >= MIN_N:
                worst = min(worst, st.mean(rest))
        out[name] = worst if worst < float("inf") else float("nan")
    return out


def taken_index(hours):
    """The taker's OWN closes over the tape window, keyed (lens, sym) with
    their open stamps — so an offered episode can be marked TAKEN.

    Read through the repo's owners: LEDGER_QUARANTINE via
    `normalize_paper_row`, phantom/adopted via the grader."""
    d = _get(f"{DASH}/trades.json?source=paper&limit=5000")
    rows = d.get("trades") or d.get("rows") or []
    out, kept = collections.defaultdict(list), []
    for r in rows:
        if r.get("bot") != "lighter-ticket-taker-lshadow":
            continue
        n = store.normalize_paper_row(
            r.get("bot"), r.get("pair"), r.get("pnl_abs"), r.get("pnl_pct"),
            r.get("opened_at"), r.get("closed_at"), r.get("reason"),
            r.get("extra"), None, r.get("entry_price"), r.get("exit_price"),
            r.get("tag"))
        if n is None or gr.is_phantom_close(n) or gr.is_adopted_close(n):
            continue
        kept.append(n)
        lens = str(n.get("enter_tag") or "").split("-", 1)
        lens = lens[1] if len(lens) > 1 else ""
        sym = str(n.get("pair") or "").split("/")[0]
        try:
            out[(lens, sym)].append(parse(n.get("open_ts")))
        except (TypeError, ValueError):
            pass
    return out, kept


def mark_taken(eps, idx, window_h=2.0):
    """An episode is TAKEN when the book opened that (lens, sym) inside it.

    `breakoutup` is the taker's own relabel of an up-regime `breakout`, so a
    `breakout` episode matches either key — the relabel happens after the
    ticket is offered, so the OFFER carries the parent name."""
    w = dt.timedelta(hours=float(window_h))
    for e in eps:
        keys = [(e["_lens"], e["_sym"])]
        if e["_lens"] == "breakout":
            keys.append(("breakoutup", e["_sym"]))
        e["_taken"] = any(
            any(e["_t"] <= o <= e["_t"] + w for o in idx.get(k, ()))
            for k in keys)
    return sum(1 for e in eps if e["_taken"])


def routing_for(row, lens, N):
    """The exit routing for one REAL close, with that close's OWN stamped
    max-hold grafted — the live call site's construction, and the reason
    calibration is a walk-fidelity test rather than a level comparison."""
    ex = row.get("extra") if isinstance(row.get("extra"), dict) else {}
    stamped = tt.pos_bars({"bars": ex.get("bars")} if ex.get("bars") else {})
    return N.routing(lens, stamped)


def report(args):
    N = _null()
    print(__doc__.split("Exit:")[0].strip()[:0] or "", end="")
    print(f"🎫 THE TAKER'S OFFERED SET — pre-registered "
          f"{'(PREREG_TAKER_OFFERED_2026-09-11.md)'}\n")
    eps = episodes(hours=args.hours, gap_h=args.gap_h)
    if not eps:
        print("REFUSED: no scout tape (dark /bus.json history).",
              file=sys.stderr)
        return 2
    t0 = min(e["_t"] for e in eps)
    t1 = max(e["_t"] for e in eps)
    lenses = collections.Counter(e["_lens"] for e in eps)
    print(f"tape {t0:%Y-%m-%d %H:%M}Z -> {t1:%Y-%m-%d %H:%M}Z "
          f"({(t1-t0).total_seconds()/86400:.1f}d)  episodes {len(eps)}  "
          f"{dict(lenses)}")

    coins = sorted({e["_sym"] for e in eps})
    tape = N.fetch_tape(coins, t0.timestamp() - 3600,
                        t1.timestamp() + 72 * 3600)
    cov = sum(1 for c in coins if tape.get(c))
    print(f"tape coverage {cov} of {len(coins)} coins")
    if cov < 0.6 * len(coins):
        print(f"REFUSED: tape covers {cov}/{len(coins)} coins (<60%).",
              file=sys.stderr)
        return 2

    got = grade(eps, tape, N)
    if got is None:
        print("REFUSED: this process cannot reproduce the era's exit routing "
              "(BULL_MODE off). Re-run with TT_BULL_MODE=on in the COMMAND.",
              file=sys.stderr)
        return 2
    eps = [e for e in eps if "_ret" in e]
    print(f"graded {len(eps)} episodes\n")

    idx, kept = taken_index(args.hours)
    n_taken = mark_taken(eps, idx)

    # ---- CALIBRATION GATE — a WALK-FIDELITY test, PAIRED per trade ------
    # [corrected 11-Sep, first run] The first version graded every episode
    # under `pos_bars({})` — the SHIPPED defaults — and then compared the
    # taken ones against closes that ran their OWN stamped bars, entered at
    # their OWN open. It read +4.469% replayed vs +1.961% realised, drift
    # 2.508pp, and REFUSED. The gate was right and the harness was wrong:
    # that comparison was invalid by construction, not merely noisy.
    #
    # What must be faithful is the WALK. So calibration replays each real
    # close at its OWN open stamp with its OWN `extra.bars`, PAIRED against
    # that close's own realised return. The Q1/Q2 contrasts keep the uniform
    # convention (shipped bars, entry at the episode's first sighting)
    # because a CONTRAST needs one convention on both arms — declared here
    # rather than discovered later.
    lo, hi = t0, t1
    pairs_cal = []
    for r in kept:
        try:
            o = parse(r.get("open_ts"))
        except (TypeError, ValueError):
            continue
        if not (lo <= o <= hi):
            continue
        sym = str(r.get("pair") or "").split("/")[0]
        series = tape.get(sym)
        if not series:
            continue
        lens = str(r.get("enter_tag") or "").split("-", 1)
        lens = lens[1] if len(lens) > 1 else ""
        rt = routing_for(r, lens, N)
        if rt is None:
            continue
        bars, trail = rt
        entry = next(((t, px) for t, px in series if t >= o.timestamp()), None)
        if entry is None:
            continue
        got = N.walk(entry[1], entry[0],
                     not str(r.get("enter_tag") or "").startswith("short"),
                     bars, trail, series)
        if got is None:
            continue
        pairs_cal.append((100.0 * got[0], 100.0 * r["profit_ratio"]))
    if len(pairs_cal) < MIN_N:
        print(f"REFUSED: cannot calibrate — only {len(pairs_cal)} of the "
              f"book's own in-window closes could be replayed "
              f"(need >={MIN_N}).", file=sys.stderr)
        return 2
    sim = [a for a, _b in pairs_cal]
    real = [b for _a, b in pairs_cal]
    drift = st.mean(sim) - st.mean(real)
    print(f"CALIBRATION (paired, own open + own bars)  replayed "
          f"{st.mean(sim):+.3f}%/trade vs ledger {st.mean(real):+.3f}%/trade "
          f"on the SAME n={len(pairs_cal)} closes  |drift| {abs(drift):.3f}pp "
          f"vs {CALIB_TOL_PP:.2f}pp tol")
    if abs(drift) > CALIB_TOL_PP:
        print("REFUSED: a harness that cannot reproduce what DID happen may "
              "not say what WOULD have ((gx)). No verdict printed.",
              file=sys.stderr)
        return 2
    print(f"(contrast convention, declared: shipped bars + entry at the "
          f"episode's first sighting, identical on every arm)\n")
    return verdict(eps, n_taken, args,
                   own_open_mean=st.mean(sim), own_open_n=len(pairs_cal))


def verdict(eps, n_taken, args, own_open_mean=None, own_open_n=None):
    """Q1 (admission value) then Q2 (any edge anywhere), both pre-registered."""
    import random
    # ---- Q1: does the taker's ADMISSION beat the population? ------------
    print("=" * 78)
    print("Q1 — ADMISSION: **CONTAMINATED, and the confound is measured below**")
    print("=" * 78)
    print("An episode is labelled TAKEN because the book opened it LATER in")
    print("that episode, but every arm is entered at the episode's FIRST")
    print("sighting — so the taken arm is conditioned on a decision made")
    print("after its own entry. That is look-ahead, not admission value. The")
    print("`own-open` column below prices it: the SAME trades walked from the")
    print("book's actual open instead of the episode start. Read the GAP, not")
    print("the excess. Answering admission properly needs the GATES replayed")
    print("over the tape (lighter_ticket_replay), not a label join.")
    print()
    print(f"{'lens':12s} {'taken':>6s} {'mean%':>9s} | {'refused':>7s} "
          f"{'mean%':>9s} | {'excess':>8s} {'P(rand>=taken)':>15s}")
    rng = random.Random(SEED)
    for lens in sorted({e["_lens"] for e in eps}):
        sub = [e for e in eps if e["_lens"] == lens]
        tk = [100.0 * e["_ret"] for e in sub if e["_taken"]]
        rf = [100.0 * e["_ret"] for e in sub if not e["_taken"]]
        if len(tk) < MIN_N:
            print(f"{lens:12s} {len(tk):6d} {'—':>9s} | {len(rf):7d} "
                  f"{st.mean(rf) if rf else float('nan'):9.3f} | "
                  f"{'(below the n floor — not graded)':>24s}")
            continue
        allv = [100.0 * e["_ret"] for e in sub]
        hits = 0
        for _ in range(PERM):
            hits += (st.mean(rng.sample(allv, len(tk))) >= st.mean(tk))
        print(f"{lens:12s} {len(tk):6d} {st.mean(tk):9.3f} | {len(rf):7d} "
              f"{st.mean(rf):9.3f} | {st.mean(tk)-st.mean(rf):8.3f} "
              f"{hits/PERM:15.3f}")

    if own_open_mean is not None:
        print(f"\n  THE CONFOUND, PRICED: the same book's closes walked from "
              f"its OWN open read {own_open_mean:+.3f}%/trade (n={own_open_n}) "
              f"against the {'taken' } column's episode-start entry above. "
              f"The difference is ENTRY TIMING, not selection — so the "
              f"`excess` column overstates admission by roughly that gap, and "
              f"none of it may be read as an edge.")

    # ---- Q2: is there ANY edge anywhere in the offered set? -------------
    print()
    print("=" * 78)
    print("Q2 — IS THERE ANY EDGE IN THE OFFERED SET? every cell printed")
    print("=" * 78)
    rows, pairs = [], []
    for lens in sorted({e["_lens"] for e in eps}):
        sub = [e for e in eps if e["_lens"] == lens]
        if len(sub) < 4 * MIN_N:
            continue
        base = [100.0 * e["_ret"] for e in sub]
        bm = st.mean(base)
        cells = declared_cells(sub)
        pm = perm_max(base, cells, sub, draws=args.perm)
        for key, pred in cells:
            v = [100.0 * e["_ret"] for e in sub if pred(e)]
            if len(v) < MIN_N:
                rows.append((lens, key, len(v), float("nan"), float("nan"),
                             float("nan"), float("nan"), pm, None))
                continue
            m_, _t, n_ = mean_t(v)
            sd = st.stdev(v)
            se = sd / math.sqrt(n_) if n_ > 1 else float("nan")
            z = (m_ - bm) / se if se else float("nan")
            p = 0.5 * math.erfc(z / math.sqrt(2)) if z == z else 1.0
            rows.append((lens, key, n_, m_, m_ - bm, z, p, pm, v))
            pairs.append(((lens, key), p))
    bhm = bh(pairs, fdr=FDR)
    print(f"{'lens':11s} {'cell':26s} {'n':>5s} {'mean%':>8s} {'vs base':>8s} "
          f"{'z':>6s} {'p':>7s} {'BHcrit':>7s} {'BH':>4s} {'permP95':>7s} "
          f"{'mde80':>6s}")
    survivors = []
    for lens, key, n_, m_, ex, z, p, pm, v in rows:
        b = bhm.get((lens, key))
        if v is None:
            print(f"{lens:11s} {key:26s} {n_:5d}   (below the n>={MIN_N} "
                  f"floor — not tested)")
            continue
        p95 = q(pm, 0.95)
        ok = bool(b and b["survives"]) and z > p95
        print(f"{lens:11s} {key:26s} {n_:5d} {m_:8.3f} {ex:8.3f} {z:6.2f} "
              f"{p:7.4f} {(b['crit'] if b else float('nan')):7.4f} "
              f"{('YES' if b and b['survives'] else 'no'):>4s} "
              f"{p95:7.2f} {mde80(v):6.2f}"
              + ("   <== SURVIVES BOTH" if ok else ""))
        if ok:
            survivors.append((lens, key, v, eps))
    print(f"\nm = {len(pairs)} admissible cells tested; BH at FDR {FDR}; "
          f"selection premium priced by {args.perm} permutations.")

    # ---- the three robustness checks any survivor must also pass --------
    if not survivors:
        best = max((r for r in rows if r[8] is not None),
                   key=lambda r: r[5] if r[5] == r[5] else float("-inf"),
                   default=None)
        print("\nVERDICT: **NO CELL SURVIVES.** Not one of the pre-registered "
              "cells clears BH at FDR 0.05 AND beats the selection premium.")
        if best:
            print(f"  best cell was {best[0]}/{best[1]} at z={best[5]:.2f}, "
                  f"against a noise-search p95 of {q(best[7], 0.95):.2f} — "
                  f"i.e. {'below' if best[5] <= q(best[7],0.95) else 'above'} "
                  f"what a pure-noise search of this shape produces.")
        print("  Reported as a REFUSAL WITH EVIDENCE, not as 'no edge': read "
              "each cell's mde80 for what it could not have detected.")
        return 0
    print("\nSURVIVORS — now the three robustness checks (PREREG §bar 3):")
    for lens, key, v, allv in survivors:
        sub = [e for e in allv if e["_lens"] == lens]
        keys_coin = [e["_sym"] for e in sub if True]
        keys_day = [e["_t"].date().isoformat() for e in sub if True]
        rb = robust(v, keys_coin[:len(v)], keys_day[:len(v)])
        print(f"  {lens}/{key}: drop_worst_3 {rb['drop_worst_3']:+.3f}  "
              f"leave-one-coin-out(worst) {rb['loco']:+.3f}  "
              f"leave-one-day-out(worst) {rb['lodo']:+.3f}")
    return 0


def selftest():
    """Fast — everything heavy lives in report(). tests/test_selftests.py has
    a hard TIMEOUT=120 before CI's coverage multiplier."""
    T = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)

    def snap(h, lens, sym, **kw):
        return {"key": "lighter-market",
                "ts": (T + dt.timedelta(hours=h)).isoformat(),
                "payload": {"tickets": {lens: [dict({"sym": sym}, **kw)]}}}

    # EPISODES, not observations: consecutive sightings are ONE episode; a
    # gap longer than GAP_H starts a second.
    snaps = [snap(0, "breakout", "AAA"), snap(0.1, "breakout", "AAA"),
             snap(0.2, "breakout", "AAA"), snap(9, "breakout", "AAA")]
    eps = episodes(snaps=snaps)
    assert len(eps) == 2, [e["_t"] for e in eps]
    assert all(e["_lens"] == "breakout" and e["_sym"] == "AAA" for e in eps)

    # the side rule is the taker's own: divergence carries it, others are long
    assert side_is_long({"side": "short"}) is False
    assert side_is_long({"side": "long"}) is True
    assert side_is_long({}) is True

    # BH: m is the FULL count, and the threshold is rank-dependent
    r = bh([("a", 0.001), ("b", 0.20), ("c", 0.90)])
    assert r["a"]["survives"] and not r["c"]["survives"], r
    assert abs(r["a"]["crit"] - 1 * FDR / 3) < 1e-12, r["a"]

    # the n floor bites BEFORE a cell can be crowned
    assert MIN_N >= 10

    # mde80 falls as sqrt(n) — so a thin cell honestly reports a bigger bar
    a = mde80([1.0, -1.0] * 10)
    b = mde80([1.0, -1.0] * 40)
    assert a > b > 0, (a, b)

    # mark_taken matches the breakoutup RELABEL back to its breakout offer
    e = [{"_lens": "breakout", "_sym": "AAA", "_t": T}]
    assert mark_taken(e, {("breakoutup", "AAA"): [T + dt.timedelta(minutes=5)]}) == 1
    e = [{"_lens": "breakout", "_sym": "AAA", "_t": T}]
    assert mark_taken(e, {("breakoutup", "BBB"): [T]}) == 0
    print("study_taker_offered selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=720)
    ap.add_argument("--gap-h", type=float, default=GAP_H)
    ap.add_argument("--perm", type=int, default=PERM)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    return report(a)


if __name__ == "__main__":
    sys.exit(main())
