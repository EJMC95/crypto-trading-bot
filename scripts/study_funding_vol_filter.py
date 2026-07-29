#!/usr/bin/env python3
"""Coin-QUALITY (character) filter study for the Funding Farmer, on Lighter's
own tape. Per the (ce) verdict: per-coin P&L memory is DEAD (persistence
-0.016) but CHARACTER persists (realized vol +0.830 across halves). So the
filter under test is VOLATILITY-based, point-in-time, never P&L-based.

Filter: at entry time, the coin's trailing 14d realized vol (hourly log-ret
stdev) ranked cross-sectionally against every coin with data at that hour.
  lowvol50  — enter only if vol <= median      (calm half only)
  lowvol75  — enter only if vol <= p75         (drop the wildest quartile)
  highvol50 — enter only if vol >  median      (REVERSE control: must be worse
              for the mechanism story to hold)
Gate 0.05 TRUE (the live gate). Bar: both-halves AND all-thirds positive at
BOTH 0.5 and 2.0 bps slip. Multiplicity: 3 filters tested, stated.

Depth: --days 180 (default) reproduces the 24-Jul/29-Jul snapshots; the
full-tape run is --days 455 --refresh --cache <own-path> (Lighter's settled
history reaches back to 2025-05-05, so ~450d is "everything"; the fetch stops
at genesis on its own). Use --cache for deep runs so the shared 180d fetch
cache is not clobbered for the other studies."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as bt

_ap = argparse.ArgumentParser()
_ap.add_argument("--days", type=int, default=180)
_ap.add_argument("--universe", type=int, default=25)
_ap.add_argument("--refresh", action="store_true")
_ap.add_argument("--cache", default=None,
                 help="own cache path for deep runs (default: the shared one)")
_a = _ap.parse_args()
if _a.cache:
    bt.CACHE = _a.cache

GATE = 0.05
WIN_H = 336                      # 14d trailing window
mk = bt.load(_a.days, _a.universe, refresh=_a.refresh)
hours_all = sorted({t for m in mk.values() for t in m["fund"]})
lo, hi = min(hours_all), max(hours_all)
mid = lo + (hi - lo) // 2
a3, b3 = lo + (hi - lo) // 3, lo + 2 * (hi - lo) // 3

# ---- point-in-time trailing vol per (sym, hour) -----------------------------
vol = {}                          # sym -> {hour: trailing stdev of hourly logret}
for sym, m in mk.items():
    hs = sorted(m["cand"])
    closes = [m["cand"][h][3] for h in hs]
    lr = [0.0] + [math.log(closes[i] / closes[i - 1]) if closes[i - 1] > 0 else 0.0
                  for i in range(1, len(hs))]
    s1 = [0.0]; s2 = [0.0]
    for r in lr:
        s1.append(s1[-1] + r); s2.append(s2[-1] + r * r)
    v = {}
    for i, h in enumerate(hs):
        j = max(0, i - WIN_H)
        n = i - j
        if n >= 72:               # need >=3d of returns before trusting a vol
            mu = (s1[i] - s1[j]) / n
            var = (s2[i] - s2[j]) / n - mu * mu
            v[h] = math.sqrt(max(var, 0.0))
    vol[sym] = v

# cross-sectional percentile rank at each hour (point-in-time, no lookahead)
pct = {}                          # (sym, hour) -> percentile in [0,1]
for t in hours_all:
    xs = [(s, vol[s][t]) for s in mk if t in vol.get(s, {})]
    if len(xs) < 8:
        continue
    xs.sort(key=lambda kv: kv[1])
    for rank, (s, _) in enumerate(xs):
        pct[(s, t)] = rank / (len(xs) - 1)

def make_pred(kind):
    if kind == "baseline":
        return None
    def pred(sym, t):
        p = pct.get((sym, t))
        if p is None:
            return False          # no character read -> fail-closed (skip)
        if kind == "lowvol50":
            return p <= 0.50
        if kind == "lowvol75":
            return p <= 0.75
        if kind == "highvol50":
            return p > 0.50
        return True
    return pred

def ev(pred, slip_bps):
    bt.SLIP = slip_bps / 1e4
    f = bt.run(mk, GATE, lo, hi + 1, entry_ok=pred)
    h = [bt.run(mk, GATE, lo, mid, entry_ok=pred)["pnl"],
         bt.run(mk, GATE, mid, hi + 1, entry_ok=pred)["pnl"]]
    # thirds carry (pnl, n): a 0-trade third is NO-EVIDENCE, not a flat
    # result — at full tape depth the venue's first ~5 months predate a
    # rankable >=8-book cross-section, so every filtered variant is
    # structurally out of the market there (measured 2026-07-30: first
    # rankable hour 2025-10-06; the registered bar still counts such a
    # third as a fail — the printout just makes WHY visible).
    t3 = [bt.run(mk, GATE, lo, a3, entry_ok=pred),
          bt.run(mk, GATE, a3, b3, entry_ok=pred),
          bt.run(mk, GATE, b3, hi + 1, entry_ok=pred)]
    return f, h, [(r["pnl"], r["n"]) for r in t3]

print(f"tape: {len(mk)} markets {(hi-lo)/86400:.0f}d | gate {GATE} TRUE | "
      f"trailing {WIN_H//24}d vol, cross-sectional pct | 3 filters + baseline + reverse control\n")
print(f"{'filter':>10} {'slip':>5} | {'P&L $':>8} {'n':>5} {'win%':>5} {'maxDD':>7} "
      f"{'halves':>16} {'thirds':>22} {'H+T pos?':>8}")
print("-" * 100)
verdicts = {}
for kind in ("baseline", "lowvol50", "lowvol75", "highvol50"):
    pred = make_pred(kind)
    rob = True
    for slip in (0.5, 2.0):
        f, h, t3 = ev(pred, slip)
        ok = all(x > 0 for x in h) and all(p > 0 for p, _ in t3)
        rob = rob and ok
        t3s = "[" + ", ".join(f"{p:.1f}" + ("(n0)" if n == 0 else "")
                              for p, n in t3) + "]"
        print(f"{kind:>10} {slip:>5.1f} | {f['pnl']:>8.2f} {f['n']:>5d} {f['win']:>5.1f} "
              f"{f['maxdd']:>7.1f} {str([round(x,1) for x in h]):>16} "
              f"{t3s:>22} {'YES' if ok else 'no':>8}")
    verdicts[kind] = rob
    print()

print("=== VERDICT (bar: halves+thirds positive at BOTH slips; 3 filters tested — multiplicity stated) ===")
for k, v in verdicts.items():
    print(f"  {k:>10}: {'ROBUST' if v else 'not robust'}")
mech = ("holds" if (verdicts.get('lowvol50') or verdicts.get('lowvol75'))
        and not verdicts.get('highvol50') else "NOT supported")
print(f"  mechanism story (calm coins keep the carry, wild coins eat it): {mech}")
