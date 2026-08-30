#!/usr/bin/env python3
"""🇵🇹 THE SESSION AXIS — REFUTED. Kept as the instrument that refuted it.

**VERDICT, 27-Aug: REFUSE. No row, no clock, no capital, no budget slot.**
Recorded at the top per I12, because this file's original headline was wrong in
three separate ways and a reader who stops at the hypothesis below would act on
a number that does not exist.

WHAT THIS FILE ORIGINALLY REPORTED, and why every part of it was wrong:

  1. **THE SIGN WAS INVERTED.** It printed "8h fade +0.352%/trade, t=+2.78".
     That is the CONTINUATION number wearing the fade's name — see
     `trade_return` for the double negation. Run as literally specified, the
     fade is a significant LOSER: by-coin **-0.528%/trade, t=-4.11** on the
     US+KR slice. The perps CONTINUE their closed-window move; they do not
     revert. That is the opposite of the hypothesis this file was built on.

  2. **THE HALVES WERE A NAME SPLIT.** "+0.553/+0.044, both halves positive"
     split the trade list by COIN ORDER, not time, so it never tested the
     go-live both-halves bar at all. On a calendar split the same cell reads
     +0.235/+0.320.

  3. **THE US SESSION HOURS WERE EDT-ONLY.** ~4 months of the window are EST,
     where the true UTC open is an hour later; on that subsample the effect
     reads t=-0.17. See `session_hours`.

AND THE SURVIVING (CONTINUATION) EFFECT STILL DOES NOT EARN A BOOK:

  * **It is eaten by its own spread.** Break-even is **17.6 bps/side** and the
    t=2.0 bar is lost at **4.9 bps/side**, against a median Roll half-spread of
    **15.0 bps** measured on these same books and the fleet's own measured mean
    fill slippage of 17.49 bps ((qq)). Net of each book's own spread the cell
    reads **+0.018%/trade, t=+0.13** — a coin flip sitting on its cost line.
  * **I22 fails even GROSS**: S_d=+0.2163 ⇒ **85 days-to-gate**, over the
    60-day bar. Net of spread: never.
  * **Concentration on the axis that matters**: top-3 by NAME is 56.9%
    (SNDK alone 26.0%) — past the undecidable-by-tail bar. The 9% figure this
    file printed is on the TRADE axis, which cannot see a one-name effect.

  * **THE I20 CELL IS FALSIFIED — and this is the finding that ends it.** The
    book was to be differentiated on the TIME axis: each name's own underlying
    session. It is not that. Same tape, same names, one hour changed:
    SKHYNIXUSD at **its own KRX open reads -0.427%/t=-0.80**, and at the **US
    open +1.199%/t=+3.92**; SAMSUNGUSD -0.179%/t=-0.42 vs +0.869%/t=+2.99.
    Korean stocks prefer the American clock. The effect is a single US-clock
    ~18h return autocorrelation across a universe that is 15/19 American — not
    a per-name session phenomenon, so there is no time axis to mint a book on.

  * **ONE CONTROL IS DECLARED UNSOUND rather than quoted.** An adversarial pass
    proposed a "mid-session placebo" (close=16, open=17 UTC) and it does read
    significant (t=-3.59). It is NOT evidence either way: moving the boundary
    into mid-session also collapses the drift window from ~18h to ~1h, so it
    compares different measurements, not different hours. The Korean-vs-US
    comparison above is the sound one — both windows are ~17-18h — and it is
    what the refusal rests on.

THE TRANSFERABLE LESSON, which is the reason this file is kept: **printing both
directions is not a control unless the sign convention is itself asserted
against a hand-computed case.** This module carried an explicit symmetry
defence in its own prose and computed both sides faithfully — under swapped
labels. Pinned now by `tests/autonomy/test_lus_session_sign.py`.

DO NOT re-propose: this book at any hold (literal spec is t=-2.78 to -4.11);
the continuation version at the full universe (85 days gross, never net);
semis-only as a mintable cell (79 days net, N_eff 2.7 of 6, in-sample pick that
retains 2 of 6 names out of sample); any 4h variant (t=2.0 lost at ~0 bps/side);
leverage to raise S_d (t is invariant — the seventh measured rejection).

THE ONE THING THAT COULD REOPEN IT, and it is cheap: a REAL effective
half-spread for SNDK/INTC/MU/NBIS/DRAM/SOXL from `venue_orders` /
`implementation_shortfall` rather than the Roll estimator, which conflates
bid-ask bounce with genuine reversion and is therefore an UPPER bound. At
<=10 bps/side the semis cell reads ~50 days — inside the bar. That would then
need pre-registering in the CONTINUATION orientation with the session framing
dropped, and graded forward on day-as-unit `t`. A different finding, under a
different name.

--- the original hypothesis, kept for the record ---

Does the perp's overnight drift mean-revert at the open?

The lead candidate for the LUS cohort, and the reason it is the lead: these are
perps on underlyings that keep REAL TRADING HOURS, and the fleet has already
measured something adjacent. 🧭 cook, 19-Aug: its dislocation edge concentrates
when the underlying market is CLOSED (+0.409%/t=+2.34) and is ZERO when it is
open (+0.007%/t=+0.02). That is cook's band, not this rule — so what follows is
a HYPOTHESIS being tested, never an inheritance.

THE MECHANISM BEING TESTED. While SKHYNIX's Seoul listing is shut, the Lighter
perp still trades: price moves on thin flow with no arbitrage anchor to the
underlying. When Seoul reopens, the perp must reconcile. So the overnight DRIFT
should partly REVERSE after the open — and the trade is to fade it.

WHY THIS IS A LEGITIMATE I20 CELL. It is differentiated on the TIME axis (the
underlying's own session), which I20 admits explicitly, and on supply: all 21
names are markets no living directional book scans. 🧭 cook's universe overlaps,
but cook takes a premium EVENT on the [45,60)bps band and holds ~4h; this takes
a scheduled CALENDAR position. Different trigger, different clock.

METHODOLOGY, and every one of these is a rule this repo paid to learn:

  * ONE TRADE PER NAME PER DAY, NON-OVERLAPPING. (uf) measured that pooled `t`
    over overlapping windows reports SAMPLING DENSITY, not edge — sweeping only
    the stride took pooled t from 3.98 to 0.36 while by-coin t held near 0.6.
    Here the sampling rate is not a free parameter: the session boundary
    happens once a day, so the observations are what the calendar gives.

  * `t` IS REPORTED BY COIN. Pooled is shown only so the gap is visible.

  * A RANDOM NULL, ALWAYS. (hm): on this venue a random short earns +0.2% to
    +1.1%/trade for free, so a positive mean is not an edge. The null here
    SHUFFLES THE SIGNAL, not the dates — it permutes which day's drift sign is
    attached to which day's forward return, so the tape, the hours, the names
    and the trade count are all held EXACTLY fixed and only the information
    content of the signal is destroyed. That is the null that answers "does the
    drift predict anything", rather than "is this tape falling".

  * BOTH DIRECTIONS. Fade AND follow are reported. A rule that must be flipped
    to win was not a finding in the first place, and (ub)/(uf) is this fleet's
    worked example of shipping one unsupported side over another.

  * CONCENTRATION AND HALVES, on every cell.

READ-ONLY. Prints and exits 0. Mints nothing, moves no capital.
"""
import argparse
import collections
import datetime as dt
import importlib.util
import math
import pathlib
import random
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "sse", ROOT / "scripts" / "study_sniper_exit_shape_2026-08-20.py")
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)
fetch_candles = _sse.fetch_candles
order_book_details = _sse.order_book_details

#: The 21 unclaimed non-crypto markets, grouped by the underlying's own session.
#: DECLARED rather than fetched: the venue's `market_config.trading_hours` is
#: EMPTY on every row (measured 27-Aug), so there is no on-venue source. UTC
#: hours, no DST and no holiday calendar — approximate by construction, which
#: is why a mis-set hour shows up as a WEAKER result, never a stronger one.
SESSION = {
    #                       close_h  open_h   (UTC, whole hours)
    "US": (20, 14),   # NYSE/Nasdaq 09:30-16:00 ET
    "KR": (7, 0),     # KRX 09:00-15:30 KST
    "EU": (17, 7),    # LBMA/LME core
}
NAMES = {
    "SNDK": "US", "MU": "US", "NBIS": "US", "DRAM": "US", "CBRS": "US",
    "SOXL": "US", "US100": "US", "INTC": "US", "STRC": "US", "COIN": "US",
    "META": "US", "CRCL": "US", "MRNA": "US", "US500": "US", "AAPL": "US",
    "SKHYNIXUSD": "KR", "SAMSUNGUSD": "KR", "SMIC": "KR",
    "BRENTOIL": "EU",
}
#: SPCX and CASHCAT are class-7 (pre-IPO / memecoin) with NO underlying session,
#: so they are structurally outside this rule and are excluded rather than
#: assigned a guessed calendar. 🧭 cook already measured the pre-IPO class as
#: its band's ONLY negative cell.
EXCLUDED = {"SPCX", "CASHCAT"}

DAYS = 180
HOLDS = (1, 2, 4, 8)
NULL_DRAWS = 400
MIN_TRADES = 20


def _agg(v):
    """(n, mean, t) over a list — t is None below 2 observations."""
    n = len(v)
    if n < 2:
        return n, (v[0] if v else 0.0), None
    m = st.mean(v)
    sd = st.pstdev(v) * math.sqrt(n / (n - 1)) if n > 1 else 0.0
    return n, m, (m / (sd / math.sqrt(n)) if sd > 0 else None)


def trade_return(drift, fwd, side):
    """Return of ONE trade. `side` is 'fade' (opposite the drift) or 'follow'.

    [27-Aug] THIS FUNCTION EXISTS BECAUSE THE EXPRESSION IT REPLACES WAS
    INVERTED, AND THE INVERSION SURVIVED THE VERY DEFENCE BUILT AGAINST IT.
    The original read

        for side, sgn in (("fade", -1.0), ("follow", +1.0)):
            r = [sgn * (-1.0 if dr > 0 else 1.0) * fw for ...]

    where `(-1.0 if dr > 0 else 1.0)` is ALREADY `-sign(drift)` — the fade
    position. Multiplying it by `sgn = -1.0` for the row LABELLED "fade"
    double-negates, so that row computed `+sign(drift)*fwd`: CONTINUATION.
    Both labels were swapped, the docstring thirty lines above was right, and
    the module's own boast — *"BOTH DIRECTIONS. Fade AND follow are reported.
    A rule that must be flipped to win was not a finding in the first place"*
    — was defeated by its own arithmetic, because a symmetric defence that
    prints both sides still prints them under the wrong names.

    The general shape, and it belongs beside I3: **running both directions is
    not a control unless the sign convention is itself asserted against a
    hand-computed case.** Pinned by `tests/autonomy/test_lus_session_sign.py`,
    which reddens on the double negation.
    """
    d = 1.0 if drift > 0 else -1.0
    pos = -d if side == "fade" else d
    return pos * fwd


#: US Eastern observes DST, and the declared (close=20, open=14) UTC pair is
#: EDT-ONLY. Roughly four months of this tape (Nov-2025 -> Mar-2026) are EST,
#: where NYSE 09:30-16:00 is 14:30-21:00 UTC — an hour later. Measured on the
#: EST subsample the effect reads t=-0.17, i.e. the declared hours were
#: silently wrong for ~40% of the window.
US_DST_2026 = (
    dt.datetime(2026, 3, 8, tzinfo=dt.timezone.utc).timestamp(),
    dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc).timestamp(),
)


def session_hours(sym, when_ts):
    """(close_h, open_h) UTC for `sym` at `when_ts`, DST-aware for US names."""
    bucket = NAMES[sym]
    if bucket != "US":
        return SESSION[bucket]
    lo, hi = US_DST_2026
    return (20, 14) if lo <= when_ts < hi else (21, 15)


def episodes(sym, mid, hold_h):
    """One fade candidate per name per session boundary.

    Returns [(day, drift, fwd)] where `drift` is the perp's log return across
    the underlying's CLOSED window and `fwd` is its log return over `hold_h`
    after the reopen. The trade's return is `-sign(drift) * fwd` for the fade
    and `+sign(drift) * fwd` for the follow.
    """
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    bars = fetch_candles(mid, now - DAYS * 86400, now, resolution="1h")
    if not bars:
        return []
    close_px = {t: v[3] for t, v in bars.items() if v[3] > 0}

    out = []
    day0 = (now - DAYS * 86400) // 86400
    for d in range(day0, now // 86400):
        close_h, open_h = session_hours(sym, d * 86400)
        t_open = d * 86400 + open_h * 3600
        # The close that STARTED this closed window: the previous calendar day
        # if the session runs within one UTC day, else the same day.
        prev = t_open - 86400 if close_h > open_h else t_open
        t_close = (prev // 86400) * 86400 + close_h * 3600
        if t_close >= t_open:
            t_close -= 86400
        wd_open = dt.datetime.fromtimestamp(t_open, dt.timezone.utc).weekday()
        wd_close = dt.datetime.fromtimestamp(t_close, dt.timezone.utc).weekday()
        # WEEKDAY-TO-WEEKDAY ONLY. A Friday->Monday gap is a 65-hour window,
        # a different animal from a 17-hour one, and pooling them would let the
        # weekend set the answer. Reported separately by `--weekend`.
        if wd_open > 4 or wd_close > 4:
            continue
        t_exit = t_open + hold_h * 3600
        a, b, c = close_px.get(t_close), close_px.get(t_open), close_px.get(t_exit)
        if not (a and b and c):
            continue
        out.append((d, math.log(b / a), math.log(c / b)))
    return out


def run(args):
    rows = {r["symbol"]: r for r in order_book_details()
            if r.get("status") == "active"}
    universe = [s for s in NAMES if s in rows and s not in EXCLUDED]
    print(f"\nfetching {DAYS}d of HOURLY tape for {len(universe)} names "
          f"(~9 pages each, venue throttle ~21/min — this takes several minutes)")

    tape = {}
    for i, s in enumerate(universe, 1):
        tape[s] = {h: episodes(s, int(rows[s]["market_id"]), h) for h in HOLDS}
        got = len(tape[s][HOLDS[0]])
        print(f"  {i:>2}/{len(universe)} {s:<12} {got:>4} session boundaries")

    print(f"\n{'hold':>5} {'side':<7}{'n':>6}{'mean%':>9}{'by-coin t':>11}"
          f"{'pooled t':>10}{'null P':>8}{'top3%':>7}{'h1/h2':>16}")
    best = None
    for h in HOLDS:
        for side in ("fade", "follow"):
            per_coin, dated = {}, []
            for s in universe:
                eps = [e for e in tape[s][h] if e[1] != 0.0]
                r = [trade_return(dr, fw, side) for (_, dr, fw) in eps]
                if len(r) >= 5:
                    per_coin[s] = r
                    dated += [(d, x) for (d, _, _), x in zip(eps, r)]
            # TIME-ORDERED. The original built one flat list by CONCATENATING
            # per-coin lists and split it at the midpoint, so `h1` was the
            # first half of the COIN LIST — the published +0.553/+0.044 was a
            # name split and tested nothing about stability over time, which
            # is the whole point of the go-live both-halves bar. On a calendar
            # split the same cell reads +0.235/+0.320.
            dated.sort(key=lambda x: x[0])
            allr = [x for _, x in dated]
            if len(allr) < MIN_TRADES:
                continue
            coin_means = [st.mean(v) for v in per_coin.values()]
            _, bc_m, bc_t = _agg(coin_means)
            n, pm, pt = _agg(allr)

            # SIGNAL-SHUFFLE NULL: permute which day's drift sign attaches to
            # which day's forward return, within the coin. Tape, hours, names
            # and trade count all held fixed; only the information dies.
            rnd = random.Random(20260827)
            obs, hits = bc_m, 0
            for _ in range(NULL_DRAWS):
                nm = []
                for s, _r in per_coin.items():
                    eps = [e for e in tape[s][h] if e[1] != 0.0]
                    # Shuffle the DRIFTS, then price the trade through the ONE
                    # owner. The null previously re-implemented the position
                    # expression inline and so inherited the same inversion —
                    # a second copy of a rule is a second rule, and here it was
                    # a second copy of the same bug.
                    drifts = [e[1] for e in eps]
                    rnd.shuffle(drifts)
                    nm.append(st.mean([trade_return(dr, e[2], side)
                                       for dr, e in zip(drifts, eps)]))
                if st.mean(nm) >= obs:
                    hits += 1
            p = (hits + 1) / (NULL_DRAWS + 1)

            srt = sorted(allr, reverse=True)
            tot = sum(allr)
            top3 = (sum(srt[:3]) / tot * 100) if tot > 0 else float("nan")
            half = len(allr) // 2
            h1, h2 = st.mean(allr[:half]), st.mean(allr[half:])
            bc_t_s = f"{bc_t:+.2f}" if bc_t is not None else "—"
            pt_s = f"{pt:+.2f}" if pt is not None else "—"
            print(f"{h:>4}h {side:<7}{n:>6}{bc_m*100:>9.3f}{bc_t_s:>11}"
                  f"{pt_s:>10}{p:>8.3f}{top3:>7.0f}"
                  f"{h1*100:>+8.3f}/{h2*100:>+7.3f}")
            if bc_t is not None and (best is None or bc_t > best[0]):
                best = (bc_t, h, side, bc_m, p, allr, per_coin)

    print("\n  by-coin t is the honest unit. pooled t treats every name-day as "
          "an\n  independent draw, which they are not — the names co-move "
          "(N_eff ~2.4\n  measured 27-Aug), so pooled overstates by roughly "
          "sqrt(n/N_eff).")

    if best:
        bc_t, h, side, bc_m, p, allr, per_coin = best
        print(f"\nBEST CELL: {side} at {h}h — by-coin t={bc_t:+.2f}, "
              f"mean {bc_m*100:+.3f}%/trade, null P={p:.3f}")
        # I22 arithmetic on the BEST cell, stated whether or not it flatters.
        daily = collections.defaultdict(float)
        for s, r in per_coin.items():
            for (d, dr, fw), x in zip([e for e in tape[s][h] if e[1] != 0.0], r):
                daily[d] += x / max(1, len(per_coin))
        series = [daily[d] for d in sorted(daily)]
        if len(series) > 2:
            m = st.mean(series)
            sd = st.pstdev(series) * math.sqrt(len(series) / (len(series) - 1))
            s_d = (m / sd) if sd > 0 else 0.0
            print(f"  daily Sharpe S_d = {s_d:+.4f} over {len(series)} days")
            if s_d > 0:
                dtg = (2.0 / s_d) ** 2
                print(f"  days-to-gate = (2/S_d)^2 = {dtg:,.0f} days "
                      f"— {'INSIDE' if dtg <= 60 else 'OUTSIDE'} I22's 60-day bar")
                if dtg > 60:
                    print("  => a design that cannot be decided inside 60 days "
                          "is a STUDY, not a book.\n     I22: it may run as an "
                          "instrument; it does not get a row, a clock,\n     "
                          "capital or a slot of the enforced fleet budget.")
            else:
                print("  S_d <= 0 — no decidability at any horizon. REFUSED.")
    else:
        print("\nNo cell reached the trade floor. REFUSED for want of supply.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=DAYS)
    a = ap.parse_args()
    globals()["DAYS"] = a.days
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
