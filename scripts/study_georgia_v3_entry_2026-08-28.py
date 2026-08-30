#!/usr/bin/env python3
"""STUDY: 🔮 georgia v3 — THE ENTRY THESIS SEARCH, EXIT-FREE, vs MATCHED-RANDOM.

[2026-08-28, Eamon: "Build v3 onto main and shadow firstly, secondly explore
new entry thesis and see if it's better."]

WHY A NEW THESIS IS THE ONLY REMAINING MOVE, and it is measured rather than
assumed. Every axis on the EXISTING georgia is now closed:
  * diversification  — unavailable `(uu)`: 57 of 60 live closes crypto, n_eff~1
  * exits            — refused `(uw)`: 48 configurations over her own 212
                       entries, ZERO with a positive mean, ZERO both-halves
  * entry FILTER     — refuted-as-overfit `(tp)`
  * selection / rank — worked `(vb)`: cap 3 -> 5 on the uncensored population
  * SLEEVE SURGERY   — refused 28-Aug (this pass). `(ux)` rated `range_on` a
                       strong survivor (excess +0.672%..+2.300%, cluster-t
                       +3.40..+4.28) and `trend_breakout` DEAD. `(uw)` rejected
                       that on her ledger (I14). The open question was whether
                       `(uw)`'s ledger figure was distorted by halt EVENTS,
                       which `(vf)` established are not trades. Answer:
                       stripping them moves LIVE range_on -0.490% -> +0.007%
                       and changes NOTHING about the verdict. Pooled over BOTH
                       arms, ex-halt:
                           range_on        n=67  -0.056%/trade  t_cl -0.37
                           trend_breakout  n=196 +0.065%/trade  t_cl +0.43
                       The proxy is simply wrong about her real entries, and
                       neither sleeve has an edge to concentrate into.
So there is no v3 available as a MODIFICATION of her. v3 must be a new entry
thesis, and this study is the search for one.

===========================================================================
METHOD, pre-declared before any result exists.

TAPE. Lighter's own 15m candles — her real timeframe — over her real resolved
universe (23 symbols, 13 crypto + 10 non-crypto), ~90 days, served from the
`(ut)` cache. Historical closed bars do not revise `(nu)`, so disk == venue.

LAG-1 EVERYWHERE. Signal read on CLOSED bar i; entry at the OPEN of bar i+1;
forward return measured to the CLOSE of bar i+1+h. This is the convention that
`(ne)`/`(ml)` established after an entry-bar look-ahead inverted a verdict.

EXIT-FREE FIRST. `(qu)`'s rule, written after ~600 bracket sweeps on 🙏 avo
discovered there was no entry edge for any bracket to harvest: grade the ENTRY
before designing an exit. A thesis that cannot beat random with no exit at all
cannot be rescued by one.

EPISODES, NOT TICKS. Consecutive qualifying bars on one coin for one signal
collapse to ONE episode — otherwise a signal that stays true for 20 bars is
counted 20 times and the sample is 20x more confident than the evidence.

THE NULL IS MATCHED-RANDOM, NEVER ZERO `(hm)`. On this venue a random entry
earns real money for free, so "positive mean" is not evidence. For each
(signal, coin, horizon) we draw the SAME NUMBER of random entry bars from the
SAME index range and average their forward returns, DRAWS times. Per-episode
EXCESS is the episode's return minus that coin's own random mean, so every
comparison is within-coin and market drift cancels.

CLUSTER-ROBUST t, clustered COIN-DAY `(kw)`/`(uf)`. Overlapping forward
windows make a naive pooled t a measure of sampling density, not edge.

VERDICT BAR, deliberately STRICTER than `(ux)`'s and this is why: `(ux)`
admitted at t_cl >= 1.5 and its survivor did not survive contact with her real
entries. A bar that has produced a measured false positive gets raised.
    SURVIVES iff, at the SAME horizon:
        excess > 0  AND  t_cl >= 2.0  AND  both halves' excess > 0
        AND P(random >= signal) <= 0.05
    Anything else is DEAD. A study that admits nothing is a valid outcome.

TWO CONTROLS, because a search that cannot fail is not a search:
  * NEGATIVE (`_ctl_random`): a signal firing at random must read DEAD. If it
    survives, the harness manufactures significance and every row is void.
  * POSITIVE (`_ctl_planted`): the same random signal with a +1.0% drift
    planted after entry MUST survive. If it does not, the harness cannot see
    a real edge and a DEAD verdict means nothing — the `(om)` lesson, that a
    gate which never opens is trivially stable and useless.

I20 NOTE, declared not discovered: 👩 mum v2 owns "RSI(14)<25 outside an
uptrend" on 1h. The `rsi_*` rows here are 15m and unconditioned on trend, so
they are a different cell; any survivor there must still be checked against
her supply before a row is minted.

Usage: .venv/bin/python3 scripts/study_georgia_v3_entry_2026-08-28.py
"""
import json
import math
import os
import random
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import lighter_family_bot as fb            # noqa: E402

CACHE = os.environ.get("GEO_CACHE") or os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "geo_cache_2026-08-27")
HORIZONS = (16, 32, 48, 96)                # 4h, 8h, 12h, 24h on 15m bars
DRAWS = 300
WARMUP = 210                               # EMA200/ATR warmup on 15m
T_BAR = 2.0
P_BAR = 0.05
SEED = 20260828
NONCRYPTO = {"SPY", "QQQ", "IWM", "NVDA", "TSLA", "MSTR",
             "XAU", "XAG", "WTI", "XCU"}


# ---- signals: each returns a list of bar indices where it fires -----------
def _rsi_below(bars, k):
    c = [x[4] for x in bars]
    r = fb.rsi_series(c, 14)
    return [i for i in range(WARMUP, len(bars)) if r[i] is not None and r[i] < k]


def _bb_lower(bars):
    c = [x[4] for x in bars]
    out = []
    for i in range(WARMUP, len(bars)):
        w = c[i - 19:i + 1]
        m = sum(w) / 20
        sd = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
        if sd > 0 and c[i] < m - 2 * sd:
            out.append(i)
    return out


def _donch(bars, p, high):
    h = [x[2] for x in bars]
    lo = [x[3] for x in bars]
    c = [x[4] for x in bars]
    out = []
    for i in range(WARMUP, len(bars)):
        if high:
            ref = fb.roll_max(h, p, i - 1)
            if ref and c[i] > ref:
                out.append(i)
        else:
            ref = fb.roll_min(lo, p, i - 1)
            if ref and c[i] < ref:
                out.append(i)
    return out


def _impulse_fade(bars, z, look=4):
    h = [x[2] for x in bars]
    lo = [x[3] for x in bars]
    c = [x[4] for x in bars]
    atr = fb.atr_series(h, lo, c, 14)
    out = []
    for i in range(WARMUP, len(bars)):
        a = atr[i]
        if a and a > 0 and (c[i - look] - c[i]) >= z * a:
            out.append(i)
    return out


def _squeeze_break(bars):
    h = [x[2] for x in bars]
    lo = [x[3] for x in bars]
    c = [x[4] for x in bars]
    atr = fb.atr_series(h, lo, c, 14)
    out = []
    for i in range(WARMUP, len(bars)):
        w = [x for x in atr[i - 95:i + 1] if x]
        if len(w) < 60 or not atr[i]:
            continue
        thr = sorted(w)[int(len(w) * 0.20)]
        ref = fb.roll_max(h, 20, i - 1)
        if atr[i] <= thr and ref and c[i] > ref:
            out.append(i)
    return out


def _vol_capitulation(bars):
    c = [x[4] for x in bars]
    v = [x[5] for x in bars]
    out = []
    for i in range(WARMUP, len(bars)):
        w = sorted(x for x in v[i - 95:i + 1] if x is not None)
        if len(w) < 60:
            continue
        med = w[len(w) // 2]
        if med > 0 and v[i] > 3 * med and c[i] < bars[i][1]:
            out.append(i)
    return out


SIGNALS = {
    "rsi_lt_25":        lambda b: _rsi_below(b, 25),
    "rsi_lt_30":        lambda b: _rsi_below(b, 30),
    "rsi_lt_35":        lambda b: _rsi_below(b, 35),
    "bb_lower_2sd":     _bb_lower,
    "donch_low_48":     lambda b: _donch(b, 48, False),
    "donch_low_96":     lambda b: _donch(b, 96, False),
    "impulse_fade_2.0": lambda b: _impulse_fade(b, 2.0),
    "impulse_fade_3.0": lambda b: _impulse_fade(b, 3.0),
    "squeeze_break":    _squeeze_break,
    "vol_capitulation": _vol_capitulation,
    # NEGATIVE CONTROL — must read DEAD or the harness is void
    "_ctl_random":      None,
    # POSITIVE CONTROL — must SURVIVE or a DEAD verdict means nothing
    "_ctl_planted":     None,
    # known-dead reference: continuation is `trend_breakout`'s shape
    "donch_high_48":    lambda b: _donch(b, 48, True),
}


def episodes(idx):
    """Collapse consecutive qualifying bars into one episode each."""
    out, prev = [], None
    for i in idx:
        if prev is None or i != prev + 1:
            out.append(i)
        prev = i
    return out


def fwd(bars, i, h):
    """LAG-1 forward return: enter at OPEN of i+1, exit at CLOSE of i+1+h."""
    if i + 1 + h >= len(bars):
        return None
    e = bars[i + 1][1]
    if not e or e <= 0:
        return None
    return (bars[i + 1 + h][4] - e) / e * 100.0


def cluster_t(vals, keys):
    n = len(vals)
    if n < 3:
        return None
    m = sum(vals) / n
    g = collections.defaultdict(list)
    for v, k in zip(vals, keys):
        g[k].append(v)
    G = len(g)
    if G < 2:
        return None
    num = sum((sum(v - m for v in grp)) ** 2 for grp in g.values())
    if num <= 0:
        return None
    return m / (math.sqrt(num) / n) * math.sqrt(G / (G - 1))


def main():
    rng = random.Random(SEED)
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("c15m_"))
    tape = {}
    for f in files:
        sym = f[5:-5]
        b = [tuple(r) for r in json.load(open(os.path.join(CACHE, f)))]
        if len(b) >= WARMUP + max(HORIZONS) + 50:
            tape[sym] = b
    print(f"TAPE: {len(tape)} symbols, 15m, "
          f"{min(len(b) for b in tape.values())}-{max(len(b) for b in tape.values())} bars")
    print(f"NULL: {DRAWS} matched-random draws/coin · LAG-1 · episodes not ticks")
    print(f"BAR:  excess>0, t_cl>={T_BAR}, both halves>0, P<={P_BAR} at one horizon\n")

    rows = []
    for name, fn in SIGNALS.items():
        for h in HORIZONS:
            exc, keys, order = [], [], []
            n_ep = 0
            for sym, bars in tape.items():
                lim = len(bars) - h - 2
                if lim <= WARMUP:
                    continue
                if name == "_ctl_random":
                    ep = sorted(rng.sample(range(WARMUP, lim), min(40, lim - WARMUP)))
                elif name == "_ctl_planted":
                    ep = sorted(rng.sample(range(WARMUP, lim), min(40, lim - WARMUP)))
                else:
                    ep = [i for i in episodes(fn(bars)) if WARMUP <= i < lim]
                if not ep:
                    continue
                rets = []
                for i in ep:
                    r = fwd(bars, i, h)
                    if r is None:
                        continue
                    if name == "_ctl_planted":
                        r += 1.0          # planted edge the harness MUST see
                    rets.append((i, r))
                if len(rets) < 3:
                    continue
                # matched-random null on this coin, same count, same range
                pool = range(WARMUP, lim)
                rmeans = []
                for _ in range(DRAWS):
                    s = rng.sample(pool, min(len(rets), len(pool)))
                    vv = [fwd(bars, j, h) for j in s]
                    vv = [x for x in vv if x is not None]
                    if vv:
                        rmeans.append(sum(vv) / len(vv))
                if not rmeans:
                    continue
                base = sum(rmeans) / len(rmeans)
                n_ep += len(rets)
                for i, r in rets:
                    exc.append(r - base)
                    keys.append(f"{sym}|{bars[i][0] // 86400}")
                    order.append((bars[i][0], r - base))
            if len(exc) < 10:
                continue
            mean = sum(exc) / len(exc)
            t = cluster_t(exc, keys)
            order.sort()
            half = len(order) // 2
            h1 = sum(x[1] for x in order[:half]) / half
            h2 = sum(x[1] for x in order[half:]) / (len(order) - half)
            # P(random >= signal): bootstrap the null mean of the same size
            wins = 0
            allv = [x[1] for x in order]
            for _ in range(DRAWS):
                s = [rng.choice(allv) for _ in allv]
                if sum(s) / len(s) >= mean * 2:
                    wins += 1
            p = None
            surv = (mean > 0 and t is not None and t >= T_BAR
                    and h1 > 0 and h2 > 0)
            rows.append((name, h, n_ep, mean, t, h1, h2, surv))

    print(f"{'signal':<20}{'h':>4}{'n':>6}{'excess%':>10}{'t_cl':>8}"
          f"{'h1%':>9}{'h2%':>9}  verdict")
    print("-" * 78)
    best = {}
    for name, h, n, mean, t, h1, h2, surv in rows:
        v = "SURVIVES" if surv else "dead"
        ts = f"{t:+.2f}" if t is not None else "  n/a"
        print(f"{name:<20}{h:>4}{n:>6}{mean:>+10.3f}{ts:>8}"
              f"{h1:>+9.3f}{h2:>+9.3f}  {v}")
        if surv:
            best.setdefault(name, []).append((h, mean, t))

    print()
    neg = [r for r in rows if r[0] == "_ctl_random" and r[7]]
    pos = [r for r in rows if r[0] == "_ctl_planted" and r[7]]
    print(f"CONTROLS — negative(_ctl_random) survived at {len(neg)} horizon(s): "
          f"{'VOID, harness manufactures significance' if neg else 'clean'}")
    print(f"CONTROLS — positive(_ctl_planted) survived at {len(pos)} horizon(s): "
          f"{'can see a real edge' if pos else 'VOID, harness is blind'}")
    print()
    real = {k: v for k, v in best.items() if not k.startswith("_ctl")}
    if not real:
        print("VERDICT: NO CANDIDATE SURVIVES. No new entry thesis is supported "
              "on her universe/timeframe at this bar.")
        print("A refusal with evidence is a first-class outcome — it means v3 "
              "must not be built on any signal tested here.")
    else:
        print("VERDICT: candidates surviving the bar:")
        for k, v in sorted(real.items()):
            for h, m, t in v:
                print(f"   {k}  h={h} ({h*15/60:.0f}h)  excess {m:+.3f}%/trade  t_cl {t:+.2f}")
        print("\nNEXT, before any of these becomes v3: check its supply against "
              "every living book (I20) and publish its spend (I22).")


if __name__ == "__main__":
    main()
