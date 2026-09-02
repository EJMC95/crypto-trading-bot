#!/usr/bin/env python3
"""STUDY (read-only, moves nothing): 👩 mum's GROSS and her DAILY-LOSS HALT,
priced on her own cell replayed as a 12-slot BOOK.

[2-Sep, Eamon: "Proceed with optimal metrics and parameters" — after the (xa)
deep dive showed a −2% BTC day taking the 9.5×-set book within a 0.68% basket
move of the $57 daily halt, which FLATTENS every leg at the low.]

WHAT IS MEASURED. Two rails act on her real money and both are gross-BLIND
(a fraction of equity and a fixed $): the daily-loss halt (10% of day-start
equity, `DAILY_LOSS_LIMIT`; abs cap $57 ≈ the same today) and the go-live
gate's 15% drawdown bar (I9: MTM folded in). Her strategy buys deep-oversold
coins and waits up to 24h for the rebound — so a halt that flattens at the
day's low is the exact opposite of the thesis, and its frequency and cost
scale with the gross. Neither number has ever been measured on her cell;
(th) derived "a ~1% basket move ends the day at 9.5×" from geometry alone.

METHOD, PRE-DECLARED. One owner for the tape, the roi ladder and the stop:
`study_mum_supply_2026-08-26` (S) by import. The signal is the SHIPPED cell
read off the strategy object (`rsi < RSI_MAX AND NOT (e50 > e200) AND v > 0`,
RSI(14) and EMAs from `lighter_family_bot`), LAG-1 entry at the next open,
one position per coin, 12 slots (`max_open` read from the registry, never
retyped), cooldown 1 bar after a close (`cooldown_candles`). Slots are filled
deepest-RSI-first — a deterministic stand-in for `diversified_order`, DECLARED
(the live host orders by basket correlation; this replay cannot, so its
baskets are if anything MORE correlated and its halts an upper bound on that
axis). Clip = `gross × equity_at_entry / 12`. Exits: the bracket walk per bar
(stop first, roi ladder, max_hold at the 24th open) — S.roi_thr / S.STOP.

THE HALT is simulated as the bot runs it: day-start equity at each UTC roll;
if intraday equity ≤ (1 − frac) × day-start, every leg is flattened at that
bar's CLOSE and entries are shut until the roll. Equity is marked two ways:
  * `close` — each leg at the bar close (what the 5-min loop mostly sees);
  * `low`   — each leg at the bar LOW (every leg at its worst instant at
              once, which they never are) — an UPPER bound on halts.
The truth lies between; both are printed and the decision uses `close`.
THE COST of a halt = Σ over flattened legs of (what the bracket would have
returned, walked forward on the same tape − the flatten return), in % of
equity at the gross — the P&L the halt threw away, signed.

GRID. gross ∈ {1, 2, 3, 3.75, 5, 6, 7.5, 9.5, 10} × halt frac ∈ {0.10, 0.15}.
3.75 is `0.15 / |stop|` (the all-slots-stop bound the allocation organ
publishes as `dd_bound.max_scale`); 5.2 ≈ `vol_target_here` on her held
basket's n_eff 1.94; 9.5 is her setting; 10 is `GROSS_X_MAX`.

WINDOWS. Trailing 120d (the (qu) decay window — the DECISION window) and
trailing 30d (the live regime) — both printed; a number that holds in one
and not the other is reported as such, not averaged.

CALIBRATION GATE (the (gx) rule): at gross 1 over the shadow twin's own
window (24-Aug → now) the replay must reproduce the twin's ledger — closes
per day within ×/÷ 1.6 and mean %/trade within 0.30pp of her 53 closes at
+0.494%/trade, 6.0 closes/day (the twin runs the same 12 slots and the
same cell, minus the brain gate and the correlation ordering). Miss ⇒ the
study REFUSES (exit 2) and prints nothing forward-looking.

DECISION RULE, PRE-DECLARED (so the data cannot move it):
  gross* = the LARGEST grid gross such that, on the trailing 120d at
           frac 0.10, (a) the close-marked MTM max drawdown ≤ 15% (the gate's
           own bar) AND (b) halts ≤ 1 per 30 days (a flatten is a tail event,
           not a routine one).
  The halt frac stays 0.10 unless 0.15 cuts halts by ≥ half at gross* while
  (a) still holds — a 15% day-halt is the whole gate bar spent in one day,
  so it needs that much to earn its place.
A refusal to raise, or a cut, is a first-class outcome with its number.

    MUM_SUPPLY_CACHE=/path python3 scripts/study_mum_gross_halt_2026-09-02.py \
        [--ledger trades.json]
"""
import argparse
import importlib.util
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "study_mum_supply", os.path.join(HERE, "study_mum_supply_2026-08-26.py"))
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)                       # ONE owner for tape + bracket

import lighter_family_bot as fb                    # noqa: E402

GROSS_GRID = [1.0, 2.0, 3.0, 3.75, 5.0, 6.0, 7.5, 9.5, 10.0]
FRACS = [0.10, 0.15]
WINDOWS = {"trail120d": 120, "trail30d": 30}
DD_BAR = 0.15
HALT_BAR_PER_30D = 1.0
CAL_MEAN_PCT, CAL_TOL_PP = 0.494, 0.30
CAL_RATE, CAL_RATE_X = 6.02, 1.6
CAL_START = datetime(2026, 8, 24, 13, 59, tzinfo=timezone.utc).timestamp()


def _mum():
    return next(x for x in fb.STRATEGIES if x.bot == "freqtrade-mum")


def prep(tapes, strat):
    """Per coin: aligned bars + the shipped cell's signal on every warmed bar."""
    out = {}
    for s, bars in tapes.items():
        if len(bars) < S.WARMUP + 30:
            continue
        closes = [b[4] for b in bars]
        vols = [b[5] for b in bars]
        rsi = fb.rsi_series(closes, S.RSI_P)
        e50, e200 = fb.ema_series(closes, 50), fb.ema_series(closes, 200)
        sig = {}
        for i in range(S.WARMUP, len(bars) - 1):
            if None in (rsi[i], e50[i], e200[i]) or not vols[i] > 0:
                continue
            if rsi[i] < strat.RSI_MAX and not (e50[i] > e200[i]):
                sig[i] = rsi[i]
        out[s] = (bars, sig)
    return out


def bracket_from(bars, e):
    """Forward bracket outcome from an entry at open of bar e — the exit the
    halt pre-empted. S.bracket_walk, by identity."""
    r = S.bracket_walk(bars, e)
    return r


def replay(prepd, strat, gross, frac, t_start, t_end, mark="close"):
    """One book, one gross, one halt fraction. Returns a dict of measurements."""
    slots = strat.max_open
    cool_bars = int(strat.protections.get("cooldown_candles", 1)) if \
        isinstance(getattr(strat, "protections", None), dict) else 1
    # hour grid across all coins
    hours = sorted({b[0] for bars, _ in prepd.values() for b in bars
                    if t_start <= b[0] <= t_end})
    idx = {s: {b[0]: k for k, b in enumerate(bars)} for s, (bars, _) in prepd.items()}
    equity = 1.0
    open_pos = {}          # sym -> dict(e, entry, notional, k_entry)
    cooldown = {}
    day, day_start, halted = None, equity, False
    closes, rets = 0, []
    halts, halt_cost, locked_h = 0, 0.0, 0
    peak, maxdd = equity, 0.0
    daily = []             # (day, ret)
    for h in hours:
        d = h // 86400
        if d != day:
            if day is not None:
                daily.append(day_start and (equity / day_start - 1.0))
            day, day_start, halted = d, equity, False
        # ---- manage held legs on this bar ------------------------------
        for s in list(open_pos):
            p = open_pos[s]
            bars = prepd[s][0]
            k = idx[s].get(h)
            if k is None:
                continue
            age = k - p["k_entry"]
            if age >= S.MAX_HOLD_BARS:
                r = bars[k][1] / p["entry"] - 1.0        # max_hold at the open
                equity += p["notional"] * r
                rets.append(r * 100.0); closes += 1
                open_pos.pop(s); cooldown[s] = k + cool_bars
                continue
            thr = S.roi_thr(age * 60)
            if bars[k][3] <= p["entry"] * (1.0 + S.STOP):
                r = S.STOP
            elif bars[k][2] >= p["entry"] * (1.0 + thr):
                r = thr
            else:
                continue
            equity += p["notional"] * r
            rets.append(r * 100.0); closes += 1
            open_pos.pop(s); cooldown[s] = k + cool_bars
        # ---- mark and the halt check -------------------------------------
        def _mtm(col):
            m = 0.0
            for s, p in open_pos.items():
                k = idx[s].get(h)
                if k is not None:
                    m += p["notional"] * (prepd[s][0][k][col] / p["entry"] - 1.0)
            return m
        eq_close = equity + _mtm(4)
        eq_low = equity + _mtm(3)
        eq_mark = eq_close if mark == "close" else eq_low
        if not halted and eq_mark <= day_start * (1.0 - frac):
            halted = True; halts += 1
            for s, p in list(open_pos.items()):
                k = idx[s][h]
                bars = prepd[s][0]
                r_flat = bars[k][4] / p["entry"] - 1.0
                fwd = bracket_from(bars, p["k_entry"])
                if fwd is not None:
                    halt_cost += p["notional"] * (fwd[0] / 100.0 - r_flat)
                equity += p["notional"] * r_flat
                rets.append(r_flat * 100.0); closes += 1
                open_pos.pop(s); cooldown[s] = k + cool_bars
            eq_close = equity
        if halted:
            locked_h += 1
        peak = max(peak, eq_close)
        maxdd = max(maxdd, 1.0 - eq_close / peak)
        # ---- entries: signal on bar h's PREVIOUS bar, entry at this open --
        if halted or len(open_pos) >= slots:
            continue
        cands = []
        for s, (bars, sig) in prepd.items():
            if s in open_pos:
                continue
            k = idx[s].get(h)
            if k is None or k - 1 not in sig or k < cooldown.get(s, -1):
                continue
            cands.append((sig[k - 1], s, k))
        cands.sort()
        for _, s, k in cands[: slots - len(open_pos)]:
            notional = gross * equity / slots
            open_pos[s] = {"entry": prepd[s][0][k][1], "notional": notional,
                           "k_entry": k}
    days = max(1e-9, (hours[-1] - hours[0]) / 86400.0) if hours else 1e-9
    mean = sum(rets) / len(rets) if rets else float("nan")
    sd_day = (math.sqrt(sum((x - sum(daily) / len(daily)) ** 2 for x in daily)
                        / max(1, len(daily) - 1)) if len(daily) > 2 else float("nan"))
    return {"gross": gross, "frac": frac, "days": days, "closes": closes,
            "closes_per_day": closes / days, "mean_pct": mean,
            "total_ret_pct": (equity - 1.0) * 100.0, "maxdd_pct": maxdd * 100.0,
            "halts": halts, "halts_per_30d": halts / days * 30.0,
            "halt_cost_pct": halt_cost * 100.0,
            "locked_frac": locked_h / max(1, len(hours)),
            "sd_day_pct": sd_day * 100.0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=None, help="trades.json (calibration readout)")
    ap.add_argument("--universe-file", default=None,
                    help="JSON list of venue symbols to replay INSTEAD of the offline "
                         "carrier_universe (which is the 15-major configured list when "
                         "the scout is dark) — e.g. the scout's crypto books at mum's "
                         "$0.1M floor, the universe her LIVE arm actually scans (94)")
    a = ap.parse_args(argv)
    os.makedirs(S.CACHE, exist_ok=True)
    strat = _mum()
    print(f"mum registry: rsi_max={strat.RSI_MAX} stop={strat.stoploss} slots={strat.max_open} "
          f"max_hold_bars={S.MAX_HOLD_BARS} roi={S.ROI}")
    universe = list(fb.carrier_universe(strat))
    if a.universe_file:
        with open(a.universe_file) as fh:
            universe = list(json.load(fh))
        print(f"universe OVERRIDDEN from {a.universe_file}: {len(universe)} symbols")
    mids = S.market_ids()
    syms = [s for s in universe if s in mids]
    print(f"universe {len(universe)} (carrier_universe), on venue {len(syms)}; "
          f"tape cache {S.CACHE}")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        tapes = dict(zip(syms, ex.map(lambda s: S.fetch_1h(s, mids[s]), syms)))
    print(f"tape fetched in {time.time()-t0:.0f}s; spans: "
          + ", ".join(f"{s}:{len(t)}b" for s, t in sorted(tapes.items())[:8]) + " ...")
    prepd = prep(tapes, strat)
    print(f"prepared {len(prepd)} coins with warmed signal series")

    # ---- calibration -------------------------------------------------------
    cal = replay(prepd, strat, 1.0, 0.10, CAL_START, S.NOW)
    ok = (abs(cal["mean_pct"] - CAL_MEAN_PCT) <= CAL_TOL_PP and
          CAL_RATE / CAL_RATE_X <= cal["closes_per_day"] <= CAL_RATE * CAL_RATE_X)
    print(f"\nCALIBRATION (gross 1, shadow window {datetime.fromtimestamp(CAL_START, timezone.utc):%d-%b %H:%M}Z→now): "
          f"replay n={cal['closes']} {cal['closes_per_day']:.2f}/day mean {cal['mean_pct']:+.3f}%/trade "
          f"vs ledger {CAL_RATE:.2f}/day {CAL_MEAN_PCT:+.3f}% (tol ±{CAL_TOL_PP}pp, ×/÷{CAL_RATE_X}) -> "
          f"{'OK' if ok else 'MISS'}")
    if not ok:
        print("REFUSED: the harness does not reproduce the twin's record; nothing "
              "forward-looking is printed (gx).")
        return 2

    # ---- the grid ------------------------------------------------------------
    results = {}
    for wname, wdays in WINDOWS.items():
        t_start = S.NOW - wdays * 86400
        print(f"\n== window {wname} ({wdays}d) ==")
        print(f"{'gross':>6} {'frac':>5} {'n':>4} {'n/day':>6} {'mean%':>7} {'total%':>8} "
              f"{'maxDD%':>7} {'halts':>5} {'/30d':>6} {'lowB/30d':>8} {'cost%':>7} {'lock%':>6} {'sdday%':>7}")
        for g in GROSS_GRID:
            for f in FRACS:
                r = replay(prepd, strat, g, f, t_start, S.NOW, mark="close")
                rl = replay(prepd, strat, g, f, t_start, S.NOW, mark="low")
                results[(wname, g, f)] = (r, rl)
                print(f"{g:>6.2f} {f:>5.2f} {r['closes']:>4d} {r['closes_per_day']:>6.2f} "
                      f"{r['mean_pct']:>+7.3f} {r['total_ret_pct']:>+8.2f} {r['maxdd_pct']:>7.2f} "
                      f"{r['halts']:>5d} {r['halts_per_30d']:>6.2f} {rl['halts_per_30d']:>8.2f} "
                      f"{r['halt_cost_pct']:>+7.2f} {100*r['locked_frac']:>6.1f} {r['sd_day_pct']:>7.2f}")

    # ---- the decision, by the pre-declared rule -------------------------------
    def passes(g, f):
        r, _ = results[("trail120d", g, f)]
        return r["maxdd_pct"] <= DD_BAR * 100 and r["halts_per_30d"] <= HALT_BAR_PER_30D
    ok_g = [g for g in GROSS_GRID if passes(g, 0.10)]
    g_star = max(ok_g) if ok_g else None
    print("\n== DECISION (trail120d, frac 0.10) ==")
    for g in GROSS_GRID:
        r, _ = results[("trail120d", g, 0.10)]
        why = []
        if r["maxdd_pct"] > DD_BAR * 100: why.append(f"maxDD {r['maxdd_pct']:.1f}% > 15%")
        if r["halts_per_30d"] > HALT_BAR_PER_30D: why.append(f"halts {r['halts_per_30d']:.2f}/30d > 1")
        print(f"  gross {g:>5.2f}: {'PASS' if not why else 'FAIL — ' + '; '.join(why)}")
    if g_star is None:
        print("  gross*: NONE passes both bars — report, do not set.")
    else:
        r10, _ = results[("trail120d", g_star, 0.10)]
        r15, _ = results[("trail120d", g_star, 0.15)]
        frac_star = 0.15 if (r15["halts_per_30d"] <= 0.5 * r10["halts_per_30d"]
                             and r15["maxdd_pct"] <= DD_BAR * 100) else 0.10
        print(f"  gross* = {g_star} ; halt frac* = {frac_star} "
              f"(0.10: {r10['halts_per_30d']:.2f} halts/30d maxDD {r10['maxdd_pct']:.1f}% ; "
              f"0.15: {r15['halts_per_30d']:.2f}/30d maxDD {r15['maxdd_pct']:.1f}%)")
    with open(os.path.join(S.CACHE, "gross_halt_results.json"), "w") as fh:
        json.dump({f"{w}|{g}|{f}": {"close": r, "low": rl}
                   for (w, g, f), (r, rl) in results.items()}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
