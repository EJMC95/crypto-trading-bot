#!/usr/bin/env python3
"""
study_leverage_sizing_2026-08-16.py — ⚡ HIGH VOLTAGE'S DECISION POINT.

    .venv/bin/python3 scripts/study_leverage_sizing_2026-08-16.py
    .venv/bin/python3 scripts/study_leverage_sizing_2026-08-16.py --selftest

THE QUESTION, pre-registered in BAND_YOUNG_HIGH_VOLTAGE_2026-08-16.md §6 before
any number was produced:

    Does RISK-NORMALISED sizing — constant dollar risk per trade, notional =
    R/stop_distance, leverage an OUTPUT — improve the t-statistic versus the
    fixed-$100-clip control, on IDENTICAL entries?

WHY t AND NOT TOTAL P&L. Every one of the fleet's five prior leverage studies
applied leverage as a SCALAR on an existing book's clip. Multiply every trade's
P&L by a constant and the mean scales, the SD scales, and t is UNCHANGED — the
same algebra as POSITION-DAYS ARE NOT EXTRA EVIDENCE. A scalar dial buys
volatility and ruin risk for nothing measurable, so "it made more dollars" is
the one answer that cannot distinguish this design from the refuted ones.

WHAT MAKES THIS DIFFERENT, AND WHY THE TEST IS NOT VACUOUS. Risk-normalisation
multiplies each trade by a DIFFERENT factor 1/s_i, so t genuinely can move:

    arm A (control):   pnl_i = CLIP * ret_i             -> t = t(ret_i)
    arm B (this book): pnl_i = (R/s_i) * ret_i          -> t = t(ret_i / s_i)

and ret_i/s_i is exactly the trade's R-MULTIPLE. So the study reduces to one
honest question — IS THE EDGE MORE CONSISTENT PER UNIT OF RISK THAN PER UNIT OF
DOLLAR? — and the answer is not knowable in advance, because the cost term cuts
the other way: in R terms a round trip costs c/s_i, which is LARGER on quiet
coins, so risk-normalisation concentrates cost drag exactly where it weights
most. That tension is the whole measurement.

THE HOST is 🧘 The Zone's shipped rule (fade >2.5xATR24 1h impulses, sl 1.0x /
tp 1.5xATR, 12h expiry, cap 4, 18 liquid crypto books, 208d of Lighter's own
tape). Chosen because the fleet ALREADY RUNS IT UNLEVERED, so the control is a
live book rather than a synthetic one, and exactly one variable differs.

METHOD, and the traps it is built around:
  * ONE OWNER. The bracket walk is imported from study_books_cohort_2026-08-13
    (extended additively on 2026-08-16 to emit per-trade sl/mae/gap), never
    re-implemented — a second copy of a rule is a second rule.
  * LAG-1 / (ml). The entry bar's own post-open range is bracket-tested, so
    entry-bar stops a live loop realises are not invisible here.
  * LIQUIDATION IS PRICED, not assumed away, via venues/margin.py against the
    venue's OWN published per-book maintenance fractions. A trade liquidates
    iff its measured maximum adverse excursion reached the liquidation price.
  * THE NULL IS LEVERED TOO. A levered book graded against an unlevered
    random-entry null is a book flattering itself.
  * FIXED R IS PRIMARY. R = RISK_PCT * 1000 (a constant), so arm B's t is
    scale-free exactly as arm A's is. Equity-COMPOUNDED R is reported as a
    secondary cell only: it makes each trade's weight depend on the path, which
    is a second variable and would break the paired comparison.
  * COSTS ARE NOT DOUBLE-COUNTED. `ret` already carries 2*FEE_SIDE as a
    fraction of NOTIONAL, so re-weighting by notional scales cost correctly and
    automatically. Nothing here charges a fee again.
  * GAP FILLS. The walk fills stops AT the stop price. 16 of 641 trades opened
    THROUGH their stop, the worst by 5.45x. `--gap` charges that shortfall to
    BOTH arms identically, as a sensitivity.

PRE-REGISTERED KILL CRITERIA (§6). PRIMARY: t must improve. If it does not, the
design is REFUTED and reported as refuted.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from scripts import lighter_margin_model as M  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "books_cohort", os.path.join(HERE, "study_books_cohort_2026-08-13.py"))
BC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BC)

CLIP = 100.0                 # the control's fixed clip — 🧘 The Zone's DOUGLAS_CLIP_USD
EQUITY = 1000.0              # one shadow book
CAP = 4                      # concurrent positions — the host's own
IMPULSE_K = 2.5
SL_ATR, TP_ATR, HOLD = 1.0, 1.5, 12
COST_RT = 2 * BC.FEE_SIDE    # 10 bps of notional, round trip

#: pre-declared grid (§6.7). A grid-EDGE winner is reported unbounded.
GRID_RISK_PCT = (0.005, 0.010, 0.020)
GRID_S_FLOOR = (0.0, 0.0025, 0.0041, 0.0060)
GRID_GROSS_L = (3.0, 6.0, 12.0)
GRID_SLIP_MULT = (1.0, 2.0, 4.0)
LIQ_HEADROOM_K = 4.0
NOTIONAL_CAP = 600.0


# ------------------------------------------------------------------ stats
def t_stat(xs):
    return BC.t_stat(xs)


def cluster_t(pnls, times, batch_s=60.0):
    """Cluster-robust t on batched closes — the fleet's (kw) convention, via
    the ONE owner in golive_readiness rather than a second copy of the rule.

    Added 2026-08-16 after an adversarial review pointed out the study shipped
    without it: `t = mean/(sd/sqrt(n))` assumes n INDEPENDENT observations, and
    these trades overlap in time and across coins. It does not change this
    study's verdict (both arms shrink and the sign never moves) — it is here so
    the number is reported the way this fleet reports it.

    Returns (t_cr, n_eff) or (None, None) when the shape cannot be judged."""
    if not pnls or len(pnls) < 3:
        return None, None
    try:
        import datetime as _dt
        sys.path.insert(0, HERE)
        import golive_readiness as GR
        n = len(pnls)
        mean = sum(pnls) / n
        var = sum((x - mean) ** 2 for x in pnls) / (n - 1)
        sd = math.sqrt(var) if var > 0 else 0.0
        # cluster_stats takes (value, _, closed_at_datetime) tuples, oldest
        # first — read from its own body, not assumed.
        rows = sorted(
            ((p, p, _dt.datetime.fromtimestamp(t, _dt.timezone.utc))
             for p, t in zip(pnls, times)), key=lambda r: r[2])
        cs = GR.cluster_stats(rows, mean, sd, n)
        if not cs:
            return None, None
        return cs.get("t_cluster"), cs.get("n_eff")
    except Exception:  # noqa: BLE001 — a missing convention is not a verdict
        return None, None


def max_drawdown(pnls):
    """Closed-basis max drawdown on THE FLEET'S OWN BASIS: the worst
    peak-to-trough fall in dollars, divided by the BOOK (`abs(dd)/book_usd`),
    exactly as `golive_readiness.stats` computes `max_dd_frac`.

    [CORRECTED 2026-08-16, and it is the one defect none of three adversarial
    lenses caught — two of them then reasoned from the wrong number.] The first
    version divided by the RUNNING PEAK while its docstring claimed "a fraction
    of starting equity", which is neither this nor the fleet's convention. It
    understated the arm being REFUTED by 12.6 points — arm B reads 54.1%
    peak-relative against 66.7% on the fleet basis — and the study invites
    comparison with the 15% go-live drawdown bar, which is book-relative. An
    error that flatters the thing you are arguing against is still an error,
    and this one pointed the wrong way twice over."""
    eq, peak, dd = EQUITY, EQUITY, 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd / EQUITY


def halves(vals):
    h = len(vals) // 2
    return sum(vals[:h]), sum(vals[h:])


# ------------------------------------------------------------------ sizing
def size_trade(tr, specs, risk_usd, gross_used, opts):
    """One trade -> (notional, leverage, refusal_reason|None).

    Leverage is produced, never chosen. Clamps in order: venue max leverage,
    liquidation headroom, notional cap, book gross-leverage budget."""
    spec = M.spec_for(specs, tr["sym"])
    if spec is None:
        return 0.0, 0.0, "no_margin_spec"
    s = tr["sl"]
    if s < opts["s_floor"]:
        return 0.0, 0.0, "below_s_floor"
    n, lev, why = M.size_for_risk(
        EQUITY, risk_usd / EQUITY, s, spec,
        k=LIQ_HEADROOM_K, notional_cap=opts["notional_cap"])
    if n <= 0:
        return 0.0, 0.0, why
    room = max(0.0, opts["gross_l"] * EQUITY - gross_used)
    if n > room:
        n = room
        lev = n / EQUITY
        why = "gross_budget"
        if n <= 0:
            return 0.0, 0.0, "gross_budget"
    return n, lev, (None if why == "ok" else why)


def realise(tr, notional, leverage, specs, opts):
    """Dollar P&L for one sized trade, with liquidation priced.

    A trade liquidates iff its measured maximum adverse excursion reached the
    liquidation price. mae_frac is taken over every bar held INCLUDING the
    entry bar, so a violent bar that blew through the stop by 4x+ is read as
    the liquidation it would have been rather than a tidy fill at the stop."""
    ret = tr["ret"] - opts["slip_extra"]
    if opts["charge_gap"]:
        ret -= tr.get("gap_frac", 0.0)
    spec = M.spec_for(specs, tr["sym"])
    liq_d = M.liq_distance_frac(tr["side"] == "long", leverage,
                                spec.mmf if spec else None)
    if liq_d is not None and tr["mae_frac"] >= liq_d:
        return M.liquidation_pnl(notional, leverage, spec,
                                 opts["recovery"]), True
    return notional * ret, False


def run_arm(trades, specs, opts, fixed_clip=False):
    """Walk the closed trades in ENTRY order, applying one sizing rule.

    Entry order, not exit order: the gross-leverage budget has to bind at the
    moment a position would be OPENED. (The docstring said "exit order" for one
    commit while the code sorted by entry_t — symmetric across arms, so it moved
    no verdict, but a false docstring feeding max_drawdown is how the next
    reader gets misled.)

    Gross-leverage budget is tracked over positions that are open at the same
    moment, using each trade's own entry/exit stamps — so the budget binds the
    way it would live, not on a per-trade basis that could never bind."""
    out = {"pnl": [], "lev": [], "notional": [], "liq": 0, "refused": {},
           "clamped": {}, "taken": []}
    ordered = sorted(trades, key=lambda c: (c["entry_t"], c["sym"]))
    live = []                                   # (exit_t, notional)
    risk_usd = opts["risk_pct"] * EQUITY
    for tr in ordered:
        live = [x for x in live if x[0] > tr["entry_t"]]
        gross_used = sum(x[1] for x in live)
        if fixed_clip:
            n, lev, why = CLIP, CLIP / EQUITY, None
            if M.spec_for(specs, tr["sym"]) is None:
                n, lev, why = 0.0, 0.0, "no_margin_spec"
        else:
            n, lev, why = size_trade(tr, specs, risk_usd, gross_used, opts)
        if n <= 0:
            out["refused"][why] = out["refused"].get(why, 0) + 1
            continue
        if why:
            # A clamp is not a refusal, but it IS the sizing rule being
            # overruled — counted so a cell where the cap binds on most trades
            # cannot pass itself off as a test of the sizing rule.
            out["clamped"][why] = out["clamped"].get(why, 0) + 1
        pnl, was_liq = realise(tr, n, lev, specs, opts)
        out["pnl"].append(pnl)
        out["lev"].append(lev)
        out["notional"].append(n)
        out["taken"].append(tr)
        out["liq"] += 1 if was_liq else 0
        live.append((tr["t"], n))
    return out


def grade(name, arm, days, verbose=True):
    pnl = arm["pnl"]
    if not pnl:
        if verbose:
            print(f"{name}: ZERO trades")
        return None
    n = len(pnl)
    h1, h2 = halves(pnl)
    lev = arm["lev"]
    r = dict(name=name, n=n, tot=sum(pnl), t=t_stat(pnl),
             mean=sum(pnl) / n, h1=h1, h2=h2, dd=max_drawdown(pnl),
             liq=arm["liq"], lev_med=sorted(lev)[len(lev) // 2],
             lev_max=max(lev), gross_max=max(arm["notional"]) / EQUITY,
             c30=n / days * 30 if days else 0.0)
    if verbose:
        print(f"{name:<34} n={r['n']:<4} tot=${r['tot']:>8.2f} "
              f"t={r['t']:>5.2f} h1=${r['h1']:>7.2f} h2=${r['h2']:>7.2f} "
              f"maxDD={r['dd'] * 100:>5.1f}% liq={r['liq']:<3} "
              f"Lmed={r['lev_med']:.2f}x Lmax={r['lev_max']:.2f}x")
    return r


# ------------------------------------------------------------------ signals
def douglas_signals(c1, atrs, k=IMPULSE_K, direction=-1):
    """🧘 The Zone's shipped rule, verbatim from the parent study's cell."""
    sigs = {}
    for s, rows in c1.items():
        out = []
        for i in range(26, len(rows) - 1):
            a = atrs[s][i]
            if not a:
                continue
            chg = (rows[i][4] - rows[i - 1][4]) / rows[i - 1][4]
            if abs(chg) > k * a:
                imp = 1 if chg > 0 else -1
                side = "long" if imp * direction > 0 else "short"
                out.append((i, side, SL_ATR * a, TP_ATR * a, HOLD, None))
        sigs[s] = out
    return sigs


def random_signals(sigs, c1, rng):
    """The levered null: same coins, same bracket geometry, same count —
    random entry BAR and random side. Sized by whichever rule is under test."""
    out = {}
    for sym, ss in sigs.items():
        hi = len(c1[sym]) - 2
        if hi <= 60:
            out[sym] = []
            continue
        out[sym] = sorted((rng.randint(60, hi), rng.choice(["long", "short"]))
                          + tuple(s[2:]) for s in ss)
    return out


def opts_of(risk_pct=0.01, s_floor=0.0, gross_l=6.0, slip_mult=1.0,
            charge_gap=False, recovery="closeout", notional_cap=NOTIONAL_CAP):
    return dict(risk_pct=risk_pct, s_floor=s_floor, gross_l=gross_l,
                slip_extra=(slip_mult - 1.0) * COST_RT, charge_gap=charge_gap,
                recovery=recovery, notional_cap=notional_cap)


# ------------------------------------------------------------------- main
def main():
    specs = M.fetch_specs()
    if not specs:
        print("FAIL-CLOSED: no live margin specs from the venue.",
              file=sys.stderr)
        return 2
    bad = M.assert_tier_structure(specs)
    print(f"venue margin tiers: {len(specs)} active books, "
          f"structure violations: {bad or 'none'}")

    c1 = {s: r for s, r in json.load(
        open(os.path.join(BC.CACHE, "candles_1h.json"))).items() if len(r) > 200}
    days = max((r[-1][0] - r[0][0]) for r in c1.values()) / 86400
    atrs = {s: BC.atr_series(r, 24) for s, r in c1.items()}
    sigs = douglas_signals(c1, atrs)
    trades = BC.run_portfolio(sigs, c1, CAP, 3600, atrs)
    print(f"host: 🧘 Douglas fade, {len(c1)} coins, {days:.1f}d, "
          f"{len(trades)} closes\n")

    # ---- CALIBRATION GATE, fail-CLOSED. The control arm reconstructed here
    # must reproduce the parent harness's own summarize() to the cent, or no
    # counterfactual below is allowed to speak.
    ctrl = run_arm(trades, specs, opts_of(), fixed_clip=True)
    direct = sum(CLIP * t["ret"] for t in trades)
    drift = abs(sum(ctrl["pnl"]) - direct)
    if drift > 0.01:
        print(f"CALIBRATION FAILED: control ${sum(ctrl['pnl']):.2f} vs "
              f"harness ${direct:.2f} (drift ${drift:.2f}) — refusing to "
              f"report counterfactuals.", file=sys.stderr)
        return 3
    print(f"calibration OK: control reproduces the harness to ${drift:.4f}\n")

    # ---- the s distribution: the term the whole design turns on -----------
    ss = sorted(t["sl"] for t in trades)
    p = lambda q: ss[int(q * (len(ss) - 1))]  # noqa: E731
    s_med = p(0.50)
    print("STOP DISTANCE (s = 1.0xATR24), the denominator of leverage")
    print(f"  p10={p(.10)*100:.2f}%  p25={p(.25)*100:.2f}%  "
          f"med={s_med*100:.2f}%  p75={p(.75)*100:.2f}%  p90={p(.90)*100:.2f}%"
          f"   spread p90/p10={p(.90)/p(.10):.1f}x")
    mean_ret = sum(t["ret"] for t in trades) / len(trades)
    # TWO DIFFERENT NUMBERS, and conflating them is the design's own error.
    # mean(ret)/median(s) is the SCALAR estimate BAND_YOUNG §3 reasoned with —
    # it assumes one representative stop. mean(ret/s) is the arm's ACTUAL
    # equal-risk expectancy, because arm B's dollar P&L is exactly R * (ret/s)
    # summed. They disagree in SIGN here, and the second one is the truth: the
    # first predicts arm B earns +$199 on this tape and it loses $256.
    net_R_scalar = mean_ret / s_med
    net_R_true = sum(t["ret"] / t["sl"] for t in trades) / len(trades)
    gross_R = net_R_scalar + COST_RT / s_med
    s_floor_meas = COST_RT / gross_R if gross_R > 0 else float("inf")
    print(f"  scalar reading  mean(ret)/med(s) = {net_R_scalar:+.4f}R   "
          f"(what the design reasoned with)")
    print(f"  TRUE equal-risk mean(ret/s)      = {net_R_true:+.4f}R   "
          f"<- arm B's actual expectancy")
    print(f"  gross_R={gross_R:+.3f}R => s_floor=c/gross_R="
          f"{s_floor_meas*100:.2f}%  L_ceiling@1%risk="
          f"{0.01*gross_R/COST_RT:.2f}x")
    print("  (the design PREDICTED s_floor=0.41%, L_ceiling=2.45x off the "
          "pre-(ml) +$27.01)")

    # WHERE THE EDGE LIVES — the decomposition that explains the whole verdict.
    print("\nEXPECTANCY BY STOP-DISTANCE QUINTILE (equal-risk weights 1/s, so a"
          "\nquintile's R-multiple IS its contribution per dollar of risk)")
    ordered = sorted(trades, key=lambda t: t["sl"])
    q = len(ordered) // 5
    print(f"  {'':<4}{'n':>5}{'mean s':>9}{'mean ret':>11}"
          f"{'mean R-mult':>13}{'gross R-mult':>14}{'c/s':>8}"
          f"{'ebs%':>8}{'R ex-ebs':>12}")
    for k in range(5):
        b = ordered[k * q:(k + 1) * q] if k < 4 else ordered[4 * q:]
        ms = sum(x["sl"] for x in b) / len(b)
        mr = sum(x["ret"] for x in b) / len(b)
        mm = sum(x["ret"] / x["sl"] for x in b) / len(b)
        nb = [x for x in b
              if not (x["reason"] == "sl" and x["hold"] <= 1.0)]
        ex = (sum(x["ret"] / x["sl"] for x in nb) / len(nb)) if nb else 0.0
        print(f"  Q{k+1:<3}{len(b):>5}{ms*100:>8.3f}%{mr:>+11.5f}"
              f"{mm:>+12.4f}R{mm + COST_RT/ms:>+13.4f}R{COST_RT/ms:>8.3f}"
              f"{100*(len(b)-len(nb))/len(b):>7.0f}%{ex:>+11.4f}R")
    # THE MECHANISM, CORRECTED. The quintile gradient above is real but it is
    # NOT "wide stops are better" — an adversarial review (16-Aug) showed the
    # loss lives in the ENTRY-BAR STOP population, and excluding those, EVERY
    # quintile is positive. What equal-risk sizing actually does is charge every
    # stop-out the FULL R, while the fixed clip charges a tight-stop loss only
    # s*CLIP. With 37% of this book's trades stopping on their entry bar, that
    # difference is the whole verdict.
    ebs = [t for t in trades if t["reason"] == "sl" and t["hold"] <= 1.0]
    rest = [t for t in trades if not (t["reason"] == "sl" and t["hold"] <= 1.0)]
    if ebs and rest:
        r_e = sum(t["ret"] / t["sl"] for t in ebs) / len(ebs)
        r_r = sum(t["ret"] / t["sl"] for t in rest) / len(rest)
        print(f"  ENTRY-BAR STOPS: n={len(ebs)} ({100*len(ebs)/len(trades):.0f}%)"
              f" mean {r_e:+.4f}R (equal-risk ${10*sum(t['ret']/t['sl'] for t in ebs):+,.0f})"
              f"  |  EVERYTHING ELSE: n={len(rest)} mean {r_r:+.4f}R "
              f"(${10*sum(t['ret']/t['sl'] for t in rest):+,.0f})")
        print("  -> equal-risk charges every stop-out the FULL R; the fixed "
              "clip charges a tight-stop loss only s*CLIP. That, not stop "
              "width, is the mechanism.")

    below = [t for t in trades if t["sl"] < s_floor_meas]
    if below:
        print(f"  below s_floor ({s_floor_meas*100:.2f}%): {len(below)} of "
              f"{len(trades)} trades ({100*len(below)/len(trades):.0f}%) — "
              f"equal-risk ${10*sum(t['ret']/t['sl'] for t in below):+.2f} "
              f"vs fixed-clip ${100*sum(t['ret'] for t in below):+.2f}")
    print()

    # ---- THE PRIMARY TEST: identical trade set, one variable --------------
    print("PRIMARY — same entries, same exits, ONE variable (the sizing rule)")
    # The notional cap is DELIBERATELY unbound here: with it at $600 it binds on
    # the median trade at 1% risk, which would quietly turn arm B into a
    # near-fixed-notional arm and stop the test from measuring its own subject.
    # Caps are explored in the grid, where their binding rate is reported.
    base = opts_of(risk_pct=0.01, s_floor=0.0, gross_l=99.0, notional_cap=None)
    A = grade("A fixed $100 clip (control)", ctrl, days)
    armB = run_arm(trades, specs, base)
    B = grade("B risk-normalised 1%/trade", armB, days)
    if not A or not B:
        return 4
    print(f"  arm B clamps: {armB['clamped'] or 'none'}   "
          f"refusals: {armB['refused'] or 'none'}")
    tA_cr, nA_eff = cluster_t([CLIP * t["ret"] for t in trades],
                              [t["t"] for t in trades])
    tB_cr, nB_eff = cluster_t(armB["pnl"], [t["t"] for t in armB["taken"]])
    if tA_cr is not None and tB_cr is not None:
        print(f"  cluster-robust ((kw) convention): A t={tA_cr:+.2f} "
              f"(n_eff {nA_eff}) -> B t={tB_cr:+.2f} (n_eff {nB_eff})")
    # THE DOLLAR FIGURES ARE A CAPITAL-DEPLOYMENT ARTIFACT AND MUST NOT BE
    # QUOTED AS THE REFUTATION'S STRENGTH (adversarial review, 16-Aug). Arm B
    # runs a far larger book than the control, so its totals and drawdown are
    # the free parameter R, not the finding. t is scale-invariant and IS the
    # comparable statistic; the risk-matched restatement makes that visible.
    mean_n = sum(armB["notional"]) / len(armB["notional"])
    scale = CLIP / mean_n
    scaled = [p * scale for p in armB["pnl"]]
    print(f"  arm B mean notional ${mean_n:,.0f} vs control ${CLIP:.0f} "
          f"({mean_n/CLIP:.1f}x the book). Risk-matched to the control: "
          f"tot=${sum(scaled):.2f} maxDD={max_drawdown(scaled)*100:.1f}% "
          f"t={t_stat(scaled):+.3f} (t UNCHANGED — that is the point)")
    verdict = B["t"] > A["t"]
    print(f"\n  t: {A['t']:.3f} -> {B['t']:.3f}  "
          f"({'IMPROVED' if verdict else 'NOT IMPROVED'}; "
          f"delta {B['t'] - A['t']:+.3f})")

    # ---- the rule the DESIGN actually proposes, which is capped ----------
    # The PRIMARY above deliberately unbinds the cap so it measures the sizing
    # rule. But BAND_YOUNG §5.1 ships N = min(R/s, $600), so the capped cell is
    # reported too rather than left for a reader to assume (adversarial review,
    # 16-Aug). It is a t REGRESSION as well, which is why the verdict does not
    # turn on which of the two is quoted.
    shipped = run_arm(trades, specs,
                      opts_of(risk_pct=0.01, s_floor=0.0, gross_l=6.0,
                              notional_cap=NOTIONAL_CAP))
    S = grade("B' the SHIPPED rule (cap $600)", shipped, days)
    if S:
        pinned = shipped["clamped"].get("notional_cap", 0)
        print(f"    ...but the cap PINS {pinned} of {S['n']} trades "
              f"({100*pinned/max(1,S['n']):.0f}%), so this cell is closer to a "
              f"fixed-NOTIONAL book than to the sizing rule")

    # ---- the (ml) convention, decomposed -- the flag exists to be USED -----
    # study_books_cohort's entry_bar_bracket=False reverts to the pre-(ml)
    # look-ahead. The dollar figures FLIP SIGN across it, so quoting them as
    # the refutation's strength would be quoting a convention. The
    # pre-registered t test fails under BOTH, which is what carries the verdict.
    print("\nTHE (ml) CONVENTION — the dollar figures are convention-dependent,"
          "\nthe t verdict is not:")
    for flag, tag in ((True, "(ml) ON  [honest]"), (False, "(ml) OFF [pre-fix]")):
        tr2 = BC.run_portfolio(sigs, c1, CAP, 3600, atrs, entry_bar_bracket=flag)
        a2 = [CLIP * t["ret"] for t in tr2]
        b2 = run_arm(tr2, specs, base)
        print(f"  {tag}: n={len(tr2):<4} A tot=${sum(a2):>8.2f} "
              f"t={t_stat(a2):>6.3f}  |  B tot=${sum(b2['pnl']):>9.2f} "
              f"t={t_stat(b2['pnl']):>6.3f}  |  delta_t="
              f"{t_stat(b2['pnl']) - t_stat(a2):>+.3f}")

    # ---- levered null: leverage must not flatter itself -------------------
    print("\nLEVERED RANDOM-ENTRY NULL (200 draws, same sizing rule)")
    beats_t = beats_tot = 0
    draws = 200
    for d in range(draws):
        rng = random.Random(4242 + d)
        rtr = BC.run_portfolio(random_signals(sigs, c1, rng), c1, CAP, 3600, atrs)
        rb = run_arm(rtr, specs, base)
        if rb["pnl"]:
            if t_stat(rb["pnl"]) >= B["t"]:
                beats_t += 1
            if sum(rb["pnl"]) >= B["tot"]:
                beats_tot += 1
    print(f"  P(random t >= {B['t']:.2f}) = {beats_t/draws:.3f}   "
          f"P(random tot >= ${B['tot']:.2f}) = {beats_tot/draws:.3f}")

    # ---- the pre-declared grid -------------------------------------------
    # THE NOTIONAL CAP IS UNBOUND HERE, DELIBERATELY. With it at $600 the cells
    # at 1% and 2% risk both returned Lmed=0.60x — exactly $600/$1000 — i.e.
    # the cap pinned them and the grid's whole risk dimension was dead: those
    # rows were a fixed-NOTIONAL book wearing a leverage costume, and since t is
    # scale-invariant they simply reproduced the control's t at the same floor.
    # `clamp%` is printed so a cell that stops testing its own subject says so.
    print("\nGRID (pre-declared). risk x s_floor at gross<=6, slip 1x, no "
          "notional cap")
    print(f"  {'risk':>5} {'s_floor':>8} {'n':>5} {'tot':>9} {'t':>6} "
          f"{'maxDD':>7} {'liq':>4} {'Lmed':>6} {'clamp%':>7}")
    grid = []
    for rp in GRID_RISK_PCT:
        for sf in GRID_S_FLOOR:
            o = opts_of(risk_pct=rp, s_floor=sf, gross_l=6.0,
                        notional_cap=None)
            arm = run_arm(trades, specs, o)
            g = grade("", arm, days, verbose=False)
            if not g:
                continue
            clamp = 100.0 * sum(arm["clamped"].values()) / max(1, g["n"])
            g.update(risk=rp, s_floor=sf, clamp=clamp)
            grid.append(g)
            print(f"  {rp*100:>4.1f}% {sf*100:>7.2f}% {g['n']:>5} "
                  f"${g['tot']:>8.2f} {g['t']:>6.2f} {g['dd']*100:>6.1f}% "
                  f"{g['liq']:>4} {g['lev_med']:>5.2f}x {clamp:>6.0f}%")

    # does the s_floor help the CONTROL on its own? (the cheapest outcome)
    print("\nS_FLOOR ON THE CONTROL ALONE (would 🧘 The Zone just want this?)")
    for sf in GRID_S_FLOOR:
        sub = [t for t in trades if t["sl"] >= sf]
        if not sub:
            continue
        pn = [CLIP * t["ret"] for t in sub]
        h1, h2 = halves(pn)
        print(f"  s_floor {sf*100:>4.2f}%: n={len(pn):<4} "
              f"tot=${sum(pn):>7.2f} t={t_stat(pn):>5.2f} "
              f"h1=${h1:>7.2f} h2=${h2:>7.2f}")

    # ---- robustness: slip stress + gap fills + recovery mode --------------
    print("\nROBUSTNESS (risk 1%, gross<=6, s_floor at the measured value)")
    sf = round(s_floor_meas, 4)
    for mult in GRID_SLIP_MULT:
        o = opts_of(risk_pct=0.01, s_floor=sf, gross_l=6.0, slip_mult=mult,
                    notional_cap=None)
        gA = [CLIP * (t["ret"] - (mult - 1) * COST_RT)
              for t in trades if t["sl"] >= sf]
        gB = grade("", run_arm(trades, specs, o), days, verbose=False)
        print(f"  slip {mult:.0f}x: control t={t_stat(gA):>5.2f} "
              f"tot=${sum(gA):>7.2f}  |  risk-norm t={gB['t']:>5.2f} "
              f"tot=${gB['tot']:>7.2f}")
    o = opts_of(risk_pct=0.01, s_floor=sf, gross_l=6.0, charge_gap=True,
                notional_cap=None)
    gapA = [CLIP * (t["ret"] - t.get("gap_frac", 0.0))
            for t in trades if t["sl"] >= sf]
    gB = grade("", run_arm(trades, specs, o), days, verbose=False)
    print(f"  gap fills charged: control t={t_stat(gapA):>5.2f} "
          f"tot=${sum(gapA):>7.2f}  |  risk-norm t={gB['t']:>5.2f} "
          f"tot=${gB['tot']:>7.2f}")

    # ---- the liquidation engine MUST be able to fire ----------------------
    print("\nLIQUIDATION ENGINE — stress cells (a guard that never fires is "
          "vacuous, I3)")
    for rp in (0.05, 0.20, 0.50):
        o = opts_of(risk_pct=rp, s_floor=0.0, gross_l=999.0,
                    notional_cap=1e9)
        g = grade("", run_arm(trades, specs, o), days, verbose=False)
        print(f"  risk {rp*100:>4.1f}%/trade: Lmed={g['lev_med']:>6.2f}x "
              f"Lmax={g['lev_max']:>6.2f}x liq={g['liq']:>3} "
              f"tot=${g['tot']:>9.2f} t={g['t']:>5.2f}")
    # ...and with the headroom invariant DISABLED, so the cap is not what is
    # being tested. Sizes straight off the venue's own max leverage.
    forced = 0
    for tr in trades:
        sp = M.spec_for(specs, tr["sym"])
        if sp is None:
            continue
        d = M.liq_distance_frac(tr["side"] == "long", sp.max_leverage, sp.mmf)
        if d is not None and tr["mae_frac"] >= d:
            forced += 1
    print(f"  at each coin's VENUE-MAX leverage: {forced} of {len(trades)} "
          f"trades would have liquidated")

    # ---- secondary: equity-compounded R (a SECOND variable, reported apart)
    print("\nSECONDARY — equity-compounded R (path-dependent; NOT the paired "
          "test)")
    eq, pnls = EQUITY, []
    for tr in sorted(trades, key=lambda c: (c["entry_t"], c["sym"])):
        sp = M.spec_for(specs, tr["sym"])
        if sp is None or tr["sl"] < sf:
            continue
        n, lev, why = M.size_for_risk(eq, 0.01, tr["sl"], sp,
                                      k=LIQ_HEADROOM_K, notional_cap=None)
        if n <= 0:
            continue
        pnl, _ = realise(tr, n, lev, specs,
                         opts_of(s_floor=sf, notional_cap=None))
        eq += pnl
        pnls.append(pnl)
    h1, h2 = halves(pnls)
    print(f"  n={len(pnls)} tot=${sum(pnls):.2f} t={t_stat(pnls):.2f} "
          f"h1=${h1:.2f} h2=${h2:.2f} final_equity=${eq:.2f}")

    # ---- the verdict, against criteria written before the run -------------
    best = max((g for g in grid if g["n"] >= 30), key=lambda g: g["t"],
               default=None)
    print("\n" + "=" * 72)
    print("VERDICT against the PRE-REGISTERED criteria (§6)")
    print("=" * 72)
    print(f"  PRIMARY  t improves vs control      : "
          f"{A['t']:.2f} -> {B['t']:.2f}  {'PASS' if verdict else 'FAIL'}")
    if best:
        print(f"  best grid cell (t)                  : risk {best['risk']*100:.1f}% "
              f"s_floor {best['s_floor']*100:.2f}% -> t={best['t']:.2f} "
              f"tot=${best['tot']:.2f} maxDD={best['dd']*100:.1f}%")
        print(f"  both halves positive                : "
              f"{'PASS' if best['h1'] > 0 and best['h2'] > 0 else 'FAIL'} "
              f"(h1=${best['h1']:.2f} h2=${best['h2']:.2f})")
        print(f"  maxDD < 15%                         : "
              f"{'PASS' if best['dd'] < 0.15 else 'FAIL'} "
              f"({best['dd']*100:.1f}%)")
        print(f"  zero liquidations at shipped gross  : "
              f"{'PASS' if best['liq'] == 0 else 'FAIL'} ({best['liq']})")
    print(f"  levered null P(t)                   : {beats_t/draws:.3f}")
    return 0


# ---------------------------------------------------------------- selftest
def _selftest():
    specs = M.parse_specs([
        {"symbol": "AAA", "status": "active", "min_initial_margin_fraction": 200,
         "default_initial_margin_fraction": 500,
         "maintenance_margin_fraction": 120, "closeout_margin_fraction": 80}])

    def tr(sym="AAA", ret=0.01, sl=0.01, mae=0.0, side="long", t0=0, t1=1):
        return dict(sym=sym, ret=ret, sl=sl, tp=1.5 * sl, mae_frac=mae,
                    gap_frac=0.0, side=side, entry_t=t0, t=t1, atr0=sl,
                    reason="tp", hold=1.0, entry=100.0)

    o = opts_of(risk_pct=0.01, gross_l=99.0, notional_cap=None)
    # sizing: $1000 equity, 1% risk, 1% stop -> $1000 notional, L=1x
    n, lev, why = size_trade(tr(), specs, 10.0, 0.0, o)
    assert abs(n - 1000.0) < 1e-6 and abs(lev - 1.0) < 1e-9, (n, lev)
    assert why is None, why
    # NOTIONAL_CAP binds by default AND SAYS SO (it binds on the median trade
    # at 1% risk, so a silent clamp would have hollowed out the whole study)
    n2, _, why2 = size_trade(tr(sl=0.001), specs, 10.0, 0.0, opts_of())
    assert abs(n2 - NOTIONAL_CAP) < 1e-9 and why2 == "notional_cap", (n2, why2)
    # s_floor refuses, by name
    assert size_trade(tr(sl=0.001), specs, 10.0, 0.0,
                      opts_of(s_floor=0.005))[2] == "below_s_floor"
    # unknown book refuses, never sizes on a default
    assert size_trade(tr(sym="ZZZ"), specs, 10.0, 0.0, o)[2] == "no_margin_spec"
    # gross budget binds and is NAMED
    n3, _, why3 = size_trade(tr(), specs, 10.0, 5500.0, opts_of(gross_l=6.0))
    assert abs(n3 - 500.0) < 1e-6 and why3 == "gross_budget", (n3, why3)

    # THE CORE IDENTITY: leverage is an output, risk is the constant.
    a, la, _ = size_trade(tr(sl=0.01), specs, 10.0, 0.0, o)
    b, lb, _ = size_trade(tr(sl=0.005), specs, 10.0, 0.0,
                          opts_of(risk_pct=0.01, gross_l=99.0,
                                  notional_cap=1e9))
    assert abs(lb - 2 * la) < 1e-9, (la, lb)          # half the stop, 2x the L
    assert abs(a * 0.01 - b * 0.005) < 1e-6           # identical dollar risk

    # liquidation fires ONLY when the excursion reaches the liq price
    liq_d = M.liq_distance_frac(True, 20.0, 0.012)
    p_ok, was = realise(tr(mae=liq_d * 0.5), 1000.0, 20.0, specs, opts_of())
    assert not was and abs(p_ok - 10.0) < 1e-9, (p_ok, was)
    p_liq, was = realise(tr(mae=liq_d * 1.01), 1000.0, 20.0, specs, opts_of())
    assert was and abs(p_liq - (-42.0)) < 1e-9, (p_liq, was)
    # ...and a liquidated trade IGNORES its nominal ret (it never got there)
    p_liq2, _ = realise(tr(ret=0.05, mae=liq_d * 1.01), 1000.0, 20.0, specs,
                        opts_of())
    assert abs(p_liq2 - p_liq) < 1e-9

    # slip stress and gap charges reduce P&L, both arms, same units
    p1, _ = realise(tr(), 1000.0, 1.0, specs, opts_of(slip_mult=2.0))
    assert abs(p1 - (1000.0 * (0.01 - COST_RT))) < 1e-9, p1
    g = tr(); g["gap_frac"] = 0.002
    p2, _ = realise(g, 1000.0, 1.0, specs, opts_of(charge_gap=True))
    assert abs(p2 - (1000.0 * (0.01 - 0.002))) < 1e-9, p2

    # t is SCALE-INVARIANT (so the control's t cannot be gamed by the clip)
    xs = [0.01, -0.02, 0.03, -0.005, 0.012]
    assert abs(t_stat(xs) - t_stat([100 * x for x in xs])) < 1e-9
    # ...but NOT invariant to per-trade reweighting, which is what B does
    ws = [x / s for x, s in zip(xs, [0.01, 0.02, 0.005, 0.01, 0.03])]
    assert abs(t_stat(xs) - t_stat(ws)) > 1e-6

    # drawdown walks the realised path
    assert abs(max_drawdown([-100.0, 50.0]) - 0.10) < 1e-9
    assert max_drawdown([10.0, 10.0]) == 0.0
    print("study_leverage_sizing selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
