#!/usr/bin/env python3
"""🇵🇹 THE CONTINUATION CELL, NET OF THE SPREAD THE FLEET ACTUALLY RECORDED.

**Eamon, 27-Aug: *"I think we record things far too slowly and it impairs our
judgement."*** He is right, and this file is the instance that proves it. The
(ur) refusal hours earlier rested on a spread the fleet had NEVER READ — I used
Roll's estimator at 15.0 bps/side because no measured number was to hand.

**The measured number was to hand.** `venue_orders` holds **3,230 book-walk
records with `spread_bps`**, written by `venues/shadow.py` every time any book
fills, going back to 9-Jul — including **SKHYNIXUSD n=409** and **SNDK n=112**,
two of the six names the verdict turned on. Nothing in the fleet reads that
column. So a study reconstructed, badly, a quantity the fleet was already
recording well: **Roll overstated the good names by 5-12x**, and the refusal it
produced was wrong on its binding constraint.

RECORDED, 27-Aug (`spread_bps` is the FULL spread `(ask-bid)/mid`, so cost per
side is half of it):

    SNDK   4.36 -> 2.18/side (n=112)   NBIS  9.55 -> 4.77 (n=17)
    INTC   2.39 -> 1.20     (n=1)      DRAM 13.21 -> 6.61 (n=9)
    MU     2.70 -> 1.35     (n=27)     SOXL  7.58 -> 3.79 (n=16)

and on 412 REAL (non-shadow) fills the recorded SLIPPAGE runs
**median 0.35 bps, mean 1.19, p90 6.90** — against Roll's 15.0.

**Eamon, same session: *"Where things are missed by a fraction / widen or
tighten accordingly — I find we often miss out by a hair, let's give a little
wiggle room too."*** Applied here as a rule with a hard edge, because the
difference matters: **the BARS do not move — t>=2.0, 60 days-to-gate, both
halves — the DESIGN does.** Two consequences, both implemented:

  1. **A COST-BASED TIGHTENING IS NOT CURVE-FITTING, and that is why it is the
     lever this file pulls.** Selecting names by their RECORDED SPREAD is
     selection on a property measured independently of returns, so it cannot
     manufacture the edge it is applied to — unlike selecting the six names
     whose past returns were largest, which is what the (ur) workflow measured
     and found retains only 2 of 6 names out of sample. `--max-half-bps` is
     therefore swept and reported, and any winner sitting at the sweep's
     boundary is called UNBOUNDED rather than quoted.

  2. **EVERY BAR PUBLISHES ITS MARGIN.** A pass at t=2.01 and a pass at t=3.5
     are not the same evidence, and a fleet that prints only pass/fail cannot
     tell them apart — which is exactly how a hair's-breadth miss reads as a
     wall. `margin()` prints how far each bar cleared or missed, in the bar's
     own units.

FAIL-CLOSED ON AN UNPRICED NAME. A name with no recorded spread is EXCLUDED,
never given the median — an unmeasured cost that defaults to the average is the
same defect this file exists to correct, pointing the other way.

READ-ONLY. Prints and exits 0.
"""
import argparse
import collections
import json
import math
import pathlib
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCRATCH = pathlib.Path(
    "/private/tmp/claude-501/-Users-eamonjuaomartins-carrick-Claude-Projects-"
    "Crypto-Trading-Bot/052c7975-4dbe-47ea-b07e-2c313172e87c/scratchpad")
TAPE = SCRATCH / "lus_tape_1h.json"
SPREADS = SCRATCH / "recorded_spreads.json"

#: The go-live bars this design must clear. Bars, not preferences — they are
#: not swept, not relaxed, and not "given wiggle room". The design moves.
T_BAR = 2.0
DAYS_BAR = 60.0

SESSION = {"US": (20, 14), "KR": (7, 0), "EU": (17, 7)}
NAMES = {
    "SNDK": "US", "MU": "US", "NBIS": "US", "DRAM": "US", "CBRS": "US",
    "SOXL": "US", "US100": "US", "INTC": "US", "STRC": "US", "COIN": "US",
    "META": "US", "CRCL": "US", "MRNA": "US", "US500": "US", "AAPL": "US",
    "SKHYNIXUSD": "KR", "SAMSUNGUSD": "KR", "SMIC": "KR", "BRENTOIL": "EU",
}
US_DST = (1772928000, 1793491200)   # 2026-03-08 .. 2026-11-01 UTC


def session_hours(sym, ts):
    if NAMES[sym] != "US":
        return SESSION[NAMES[sym]]
    return (20, 14) if US_DST[0] <= ts < US_DST[1] else (21, 15)


def load():
    tape = {s: {int(t): v for t, v in b.items()}
            for s, b in json.loads(TAPE.read_text())["bars"].items()}
    spreads = json.loads(SPREADS.read_text())
    return tape, spreads


def episodes(sym, bars, hold_h):
    """(day, drift, fwd) per weekday session boundary — the (ur) construction."""
    import datetime as dt
    px = {t: v[3] for t, v in bars.items() if v[3] > 0}
    if not px:
        return []
    out = []
    for day in range(min(px) // 86400, max(px) // 86400 + 1):
        close_h, open_h = session_hours(sym, day * 86400)
        t_open = day * 86400 + open_h * 3600
        prev = t_open - 86400 if close_h > open_h else t_open
        t_close = (prev // 86400) * 86400 + close_h * 3600
        if t_close >= t_open:
            t_close -= 86400
        if dt.datetime.fromtimestamp(t_open, dt.timezone.utc).weekday() > 4:
            continue
        if dt.datetime.fromtimestamp(t_close, dt.timezone.utc).weekday() > 4:
            continue
        a = px.get(t_close)
        b = px.get(t_open)
        c = px.get(t_open + hold_h * 3600)
        if a and b and c:
            out.append((day, math.log(b / a), math.log(c / b)))
    return out


def margin(label, got, bar, unit, higher_is_better=True):
    """Print a bar AND how far it cleared or missed. Eamon, 27-Aug: a fleet
    that prints only pass/fail cannot tell a hair from a wall."""
    if got is None:
        return False, f"  {label:<26} —        (unmeasurable)"
    ok = (got >= bar) if higher_is_better else (got <= bar)
    d = (got - bar) if higher_is_better else (bar - got)
    pct = (abs(d) / bar * 100.0) if bar else float("nan")
    verdict = "PASS" if ok else "MISS"
    return ok, (f"  {label:<26}{got:>9.3f}{unit}  bar {bar:g}{unit}  "
                f"{verdict} by {abs(d):.3f}{unit} ({pct:.0f}%)")


def cell(tape, spreads, names, hold_h, side="follow"):
    """Per-trade returns NET of each name's own recorded round-trip cost."""
    per_coin, daily = {}, collections.defaultdict(list)
    priced, unpriced = [], []
    for s in names:
        rec = spreads.get(s)
        if not rec:
            unpriced.append(s)
            continue
        rt = rec["med"] / 1e4          # full spread = one round trip, in frac
        eps = [e for e in episodes(s, tape.get(s, {}), hold_h) if e[1] != 0.0]
        if len(eps) < 5:
            continue
        r = []
        for d, dr, fw in eps:
            sgn = (1.0 if dr > 0 else -1.0) if side == "follow" else \
                  (-1.0 if dr > 0 else 1.0)
            net = sgn * fw - rt
            r.append(net)
            daily[d].append(net)
        per_coin[s] = r
        priced.append(s)
    return per_coin, daily, priced, unpriced


def stats(per_coin, daily):
    coin_means = [st.mean(v) for v in per_coin.values()]
    n = sum(len(v) for v in per_coin.values())
    if len(coin_means) < 2:
        return None
    m = st.mean(coin_means)
    sd = st.pstdev(coin_means) * math.sqrt(len(coin_means) / (len(coin_means) - 1))
    bc_t = m / (sd / math.sqrt(len(coin_means))) if sd > 0 else None
    days = sorted(daily)
    series = [st.mean(daily[d]) for d in days]
    if len(series) < 3:
        return None
    dm = st.mean(series)
    dsd = st.pstdev(series) * math.sqrt(len(series) / (len(series) - 1))
    day_t = dm / (dsd / math.sqrt(len(series))) if dsd > 0 else None
    s_d = (dm / dsd) if dsd > 0 else 0.0
    dtg = (2.0 / s_d) ** 2 if s_d > 0 else None
    half = len(series) // 2
    return {"n": n, "k": len(coin_means), "mean": m, "bc_t": bc_t,
            "day_t": day_t, "s_d": s_d, "dtg": dtg, "ndays": len(series),
            "h1": st.mean(series[:half]), "h2": st.mean(series[half:])}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hold", type=int, default=8)
    ap.add_argument("--sweep", action="store_true",
                    help="sweep the cost bar and the hold")
    a = ap.parse_args()

    tape, spreads = load()
    universe = [s for s in NAMES if s in tape]

    print("RECORDED COST per candidate (venue_orders.spread_bps, FULL spread; "
          "cost/side = half)")
    print(f"  {'name':<12}{'n':>6}{'full bps':>10}{'per side':>10}")
    for s in sorted(universe, key=lambda x: spreads.get(x, {}).get("med", 1e9)):
        r = spreads.get(s)
        print(f"  {s:<12}{r['n']:>6}{r['med']:>10.2f}{r['med']/2:>10.2f}"
              if r else f"  {s:<12}{'—':>6}{'NO RECORD — EXCLUDED':>22}")

    if a.sweep:
        print(f"\nSWEEP — cost bar x hold. mean%/trade net, day-as-unit t, "
              f"days-to-gate.")
        print(f"  {'max bps/side':>13}{'k':>4}", end="")
        for h in (4, 6, 8, 10, 12, 16):
            print(f"{'h='+str(h):>22}", end="")
        print()
        for cap in (1.5, 2.5, 3.5, 5.0, 8.0, 99.0):
            keep = [s for s in universe
                    if spreads.get(s) and spreads[s]["med"] / 2 <= cap]
            print(f"  {cap:>13.1f}{len(keep):>4}", end="")
            for h in (4, 6, 8, 10, 12, 16):
                pc, dl, pr, _ = cell(tape, spreads, keep, h)
                s = stats(pc, dl)
                if not s or s["dtg"] is None:
                    print(f"{'—':>22}", end="")
                else:
                    print(f"{s['mean']*100:>+8.3f} t{s['day_t']:>+5.2f}"
                          f"{s['dtg']:>7.0f}d", end="")
            print()
        print("\n  A winner at the EDGE of this sweep is UNBOUNDED, not a value.")
        return 0

    for cap, label in ((99.0, "ALL PRICED NAMES"), (3.5, "COST-SCREENED <=3.5 bps/side")):
        keep = [s for s in universe
                if spreads.get(s) and spreads[s]["med"] / 2 <= cap]
        pc, dl, priced, unpriced = cell(tape, spreads, keep, a.hold)
        s = stats(pc, dl)
        print(f"\n{'='*72}\n{label} — hold {a.hold}h, continuation, "
              f"net of each name's OWN recorded spread")
        print(f"  names priced+kept: {len(priced)}  "
              f"{sorted(priced)}")
        if unpriced:
            print(f"  EXCLUDED, no recorded spread (fail-closed): {sorted(unpriced)}")
        if not s:
            print("  insufficient sample")
            continue
        print(f"  n={s['n']} trades over {s['ndays']} days, {s['k']} names\n")
        oks = []
        for args_ in (
            ("mean per trade", s["mean"] * 100, 0.0, "%", True),
            ("day-as-unit t", s["day_t"], T_BAR, "", True),
            ("by-coin t", s["bc_t"], T_BAR, "", True),
            ("days-to-gate", s["dtg"], DAYS_BAR, "d", False),
            ("first half", s["h1"] * 100, 0.0, "%", True),
            ("second half", s["h2"] * 100, 0.0, "%", True),
        ):
            ok, line = margin(*args_)
            oks.append(ok)
            print(line)
        print(f"\n  => {sum(oks)}/{len(oks)} bars cleared"
              f"{'  ** ALL BARS CLEAR **' if all(oks) else ''}")
    print("\nNOTE: the bars above are NOT swept and NOT relaxed. What this file "
          "moves is\n  the DESIGN — which names, at what recorded cost. The "
          "margin column exists so\n  a hair's-breadth pass is never mistaken "
          "for a comfortable one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
