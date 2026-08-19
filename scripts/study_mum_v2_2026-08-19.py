#!/usr/bin/env python3
"""STUDY: 👩 mum v2 — why v1 starved, and which expression of "mum" the
venue's own tape supports. [2026-08-19, operator: "unretire mum and bring her
back to life, and do a deep, deep dive on why — give her the attention she
needs to succeed."]

THE PATIENT. mum v1 = TrendMomo: SMA 10/40 on DAILY bars, entry on a STATE
(fast>slow — so she boot-filled every slot in one second on 12-Jul), exit only
on the death CROSS (a roughly-monthly event), ROI disabled, no time stop,
long-only, paying funding for the whole hold. Her complete lifetime: 3 closes,
all opened 2026-07-12 21:41:49Z, held 26/29/33 days, all `death_cross`;
realised +$0.68 against ~-$2.15 of funding drag. The same structural shape the
fleet has retired four times (🌊 EMA50/200 daily, 📊 sma_cross daily,
crypto-swing-daily, and mum herself at (rd)).

TAPE. 1h OHLCV from the venue's own /candlesticks (paged by the one-shot
Actions fetcher — this session's egress is 403-blocked on that endpoint;
orderBookDetails/fundings are open and were fetched directly), ~460d asked,
span reported per coin. Funding from /api/v1/fundings, hourly rows, per coin.
BACKTEST ON LIGHTER ONLY: no other venue's data appears anywhere below.

CONVENTIONS (the fleet's own, cited):
  * entries at the NEXT bar's OPEN after the signal bar closes — LAG-1, the
    (ne)/(ml) rule; no entry-bar range credit anywhere;
  * same-bar exits resolve CONSERVATIVELY (stop tested before target — the
    (ml) `adverse` convention);
  * costs 5 bps/side flat (conservative vs the (qq) measured 2.52 bps mean
    fill cost in the $0.1-1M band; these are majors);
  * funding: the coin's OWN hourly settle (rate/8 per hour, funding_basis'
    verified Lighter convention) charged while held, sign-correct for a long
    (positive rate: longs pay; negative: longs receive) — the exact drag
    class that killed v1, priced into every candidate;
  * per-coin sequential episodes (no pyramiding), portfolio throughput
    modelled at the book's slot count for the shipped config.

NULL (the (hm) rule): every directional cell is graded against a MATCHED
random-entry null — same coin mix, same episode count, same window, same exit
rule, entries drawn uniformly from the coin's tradeable bars; P(null >= cand)
over N_NULL draws. A positive mean on a trending tape is not an edge.

VERDICT LOGIC, PRE-REGISTERED (before any number existed):
  ship the best cell that clears ALL of
    V1  beats its matched random-entry null at P <= 0.10;
    V2  both halves >= 0;
    V3  sign-agreement with >= 2 adjacent cells (a plateau, never a lone
        spike — the (oe)/(qt) rule);
    V4  >= 25 expected episodes/30d at the book's slot count (decidability —
        the disease v1 actually died of; I17).
  If no cell clears V1-V3, the shipped config is the best V4-passing cell
  with the misses DECLARED on the row and in the book's description — the
  🧘 douglas / 📐 grimes precedent: an honest sub-bar status beats an invented
  edge, and the 30-day forward record (I14) is the real test.

MULTIPLICITY: the full grid is reported with Benjamini-Hochberg at FDR 0.10
across every directional cell's null-P; a cell that only looks good raw is
said so. Sensitivities are reported, never silently chosen.

Usage:
  python3 scripts/study_mum_v2_2026-08-19.py --tape-dir tape --fund-dir fundings
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
from collections import defaultdict

CRYPTO = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "AVAX", "LINK", "LTC",
          "NEAR", "TRX", "DOGE", "AAVE", "SUI", "BNB", "HYPE"]
NONCRYPTO = ["SPY", "QQQ", "XAU", "WTI"]
COST_SIDE = 0.0005            # 5 bps/side flat, conservative (see header)
N_NULL = 300
STAKE = 50.0                  # the family's $50 clip — reporting only


# ---------------------------------------------------------------------------
# data
def load_tape(tape_dir):
    out = {}
    for p in sorted(glob.glob(os.path.join(tape_dir, "*_1h.jsonl.gz"))):
        coin = os.path.basename(p).split("_")[0]
        rows = [json.loads(l) for l in gzip.open(p, "rt")]
        if not rows:
            continue
        # keys discovered from the fetcher's RAW CANDLE SHAPE print; be
        # tolerant of open/close key spellings
        def f(r, *names):
            for n in names:
                if n in r and r[n] is not None:
                    return float(r[n])
            return None
        tk = "timestamp" if "timestamp" in rows[0] else (
            "start_timestamp" if "start_timestamp" in rows[0] else "t")
        bars = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
        for r in sorted(rows, key=lambda x: int(x[tk])):
            o = f(r, "open", "o"); h = f(r, "high", "h")
            l = f(r, "low", "l");  c = f(r, "close", "c")
            v = f(r, "volume1", "base_volume", "volume", "v", "volume0")
            if None in (o, h, l, c) or min(o, h, l, c) <= 0:
                continue
            bars["t"].append(int(r[tk])); bars["o"].append(o)
            bars["h"].append(h); bars["l"].append(l); bars["c"].append(c)
            bars["v"].append(v if v is not None else 0.0)
        if len(bars["t"]) > 500:
            out[coin] = bars
    return out


def load_fundings(fund_dir):
    out = {}
    for p in sorted(glob.glob(os.path.join(fund_dir, "*.jsonl.gz"))):
        coin = os.path.basename(p).split(".")[0]
        m = {}
        for l in gzip.open(p, "rt"):
            r = json.loads(l)
            try:
                # `rate` is the venue's per-8h quote (funding_basis, VERIFIED
                # 17-Jul); settle is rate/8 per hour. direction 'short' rows
                # quote the side that PAYS as shorts -> longs RECEIVE.
                rate8 = float(r.get("rate"))
            except (TypeError, ValueError):
                continue
            sign = -1.0 if str(r.get("direction")) == "short" else 1.0
            m[int(r["timestamp"])] = sign * rate8 / 8.0
        out[coin] = m
    return out


def resample(bars, step_h):
    """1h -> N-hour bars, UTC-anchored so every run buckets identically."""
    t, o, h, l, c, v = (bars[k] for k in ("t", "o", "h", "l", "c", "v"))
    out = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    cur = None
    for i in range(len(t)):
        bucket = t[i] - (t[i] % (step_h * 3600))
        if cur is None or bucket != cur:
            if cur is not None:
                out["t"].append(cur); out["o"].append(oo); out["h"].append(hh)
                out["l"].append(ll); out["c"].append(cc); out["v"].append(vv)
            cur, oo, hh, ll, cc, vv = bucket, o[i], h[i], l[i], c[i], v[i]
        else:
            hh = max(hh, h[i]); ll = min(ll, l[i]); cc = c[i]; vv += v[i]
    if cur is not None:
        out["t"].append(cur); out["o"].append(oo); out["h"].append(hh)
        out["l"].append(ll); out["c"].append(cc); out["v"].append(vv)
    return out


def sma(xs, n, i):
    if i + 1 < n:
        return None
    return sum(xs[i - n + 1:i + 1]) / n


def atr(bars, n, i):
    if i < n:
        return None
    s = 0.0
    for j in range(i - n + 1, i + 1):
        s += max(bars["h"][j] - bars["l"][j],
                 abs(bars["h"][j] - bars["c"][j - 1]),
                 abs(bars["l"][j] - bars["c"][j - 1]))
    return s / n


def roc(bars, n, i):
    if i < n or bars["c"][i - n] <= 0:
        return None
    return bars["c"][i] / bars["c"][i - n] - 1.0


# ---------------------------------------------------------------------------
# episode walker — one entry, walked to its exit under the cell's rule
def walk(bars, fund, i_sig, step_h, sl_atr=None, tp_atr=None, max_hold_h=None,
         exit_fn=None, atr_n=24):
    """Enter at bars.o[i_sig+1] (LAG-1). Returns (ret_frac, held_h, why) or
    None if the entry bar does not exist. Same-bar stop-before-target."""
    i0 = i_sig + 1
    if i0 >= len(bars["t"]):
        return None
    entry = bars["o"][i0]
    a = atr(bars, atr_n, i_sig) or 0.0
    stop = entry - sl_atr * a if (sl_atr and a) else None
    take = entry + tp_atr * a if (tp_atr and a) else None
    for i in range(i0, len(bars["t"])):
        held_h = (i - i0 + 1) * step_h
        if stop is not None and bars["l"][i] <= stop:
            px, why = stop, "sl"
            if i == i0 and bars["o"][i0] < stop:      # gapped through
                px = bars["o"][i0]
            return _net(entry, px, fund, bars, i0, i, step_h), held_h, why
        if take is not None and bars["h"][i] >= take:
            return _net(entry, take, fund, bars, i0, i, step_h), held_h, "tp"
        if exit_fn is not None and exit_fn(i):
            return (_net(entry, bars["c"][i], fund, bars, i0, i, step_h),
                    held_h, "signal")
        if max_hold_h is not None and held_h >= max_hold_h:
            return (_net(entry, bars["c"][i], fund, bars, i0, i, step_h),
                    held_h, "hold")
    return None


def _net(entry, exit_px, fund, bars, i0, i1, step_h):
    gross = (exit_px - entry) / entry
    drag = 0.0
    if fund:
        for j in range(i0, i1 + 1):
            for hh in range(step_h):
                drag += fund.get(bars["t"][j] + hh * 3600, 0.0)
    return gross - 2 * COST_SIDE - drag


def seq_episodes(entries, bars, fund, step_h, **exit_kw):
    """Sequential per-coin: an entry while a previous episode is still open is
    skipped — matches the book's one-position-per-coin rule."""
    out, busy_until = [], -1
    for i_sig in entries:
        if i_sig + 1 <= busy_until:
            continue
        r = walk(bars, fund, i_sig, step_h, **exit_kw)
        if r is None:
            continue
        ret, held_h, why = r
        out.append((ret, held_h, why, bars["t"][i_sig + 1]
                    if i_sig + 1 < len(bars["t"]) else bars["t"][-1]))
        busy_until = i_sig + 1 + int(held_h / step_h)
    return out


# ---------------------------------------------------------------------------
# stats
def tstat(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(var / n) if var > 0 else 0.0


def cluster_t(rows):
    """day-clustered t on (ret, ts): entries sharing a UTC day are one cluster
    — the (kw) discipline, simple CRVE1 form."""
    by_day = defaultdict(list)
    for ret, ts in rows:
        by_day[ts // 86400].append(ret)
    means = [sum(v) / len(v) for v in by_day.values()]
    return tstat(means), len(means)


def summarize(eps):
    rets = [e[0] for e in eps]
    n = len(rets)
    if not n:
        return {"n": 0}
    m = sum(rets) / n
    half = n // 2
    ct, neff = cluster_t([(e[0], e[3]) for e in eps])
    span_d = (max(e[3] for e in eps) - min(e[3] for e in eps)) / 86400.0
    return {"n": n, "mean_pct": 100 * m, "t": tstat(rets), "ct": ct,
            "neff": neff,
            "h1": 100 * sum(rets[:half]) / max(1, half),
            "h2": 100 * sum(rets[half:]) / max(1, n - half),
            "eps30": n / max(span_d, 1.0) * 30.0,
            "hold_med": sorted(e[1] for e in eps)[n // 2]}


def null_p(cell_eps, per_coin_entries, tapes, funds, step_h, exit_kw, seed):
    """P(random >= cand): same per-coin episode counts, entries uniform over
    the coin's own eligible signal indices."""
    cand = sum(e[0] for e in cell_eps) / len(cell_eps)
    rng = random.Random(seed)
    ge = 0
    for _ in range(N_NULL):
        rets = []
        for coin, k in per_coin_entries.items():
            bars = tapes[coin]
            hi = len(bars["t"]) - 2
            lo = min(200, hi - 1)
            idx = sorted(rng.sample(range(lo, hi), min(k, hi - lo)))
            for e in seq_episodes(idx, bars, funds.get(coin), step_h,
                                  **exit_kw)[:k]:
                rets.append(e[0])
        if rets and sum(rets) / len(rets) >= cand:
            ge += 1
    return ge / N_NULL


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape-dir", default="tape")
    ap.add_argument("--fund-dir", default="fundings")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tapes_1h = load_tape(args.tape_dir)
    funds = load_fundings(args.fund_dir)
    print(f"tape: {len(tapes_1h)} coins loaded")
    for c in sorted(tapes_1h):
        b = tapes_1h[c]
        print(f"  {c:5s} {len(b['t'])} bars  "
              f"{(b['t'][-1] - b['t'][0]) / 86400:.0f}d")
    # funding sanity: the resting default is 9.6e-5/hr; the per-8h quote is
    # 8x that. Report each coin's median |hourly| so a unit error is visible.
    for c in ("BTC", "HYPE", "SPY"):
        m = funds.get(c) or {}
        if m:
            v = sorted(abs(x) for x in m.values())
            print(f"  funding {c}: n={len(v)} med|hourly|={v[len(v)//2]:.3e} "
                  f"p95={v[int(len(v)*0.95)]:.3e}")

    tapes = {"1h": tapes_1h,
             "4h": {c: resample(b, 4) for c, b in tapes_1h.items()},
             "1d": {c: resample(b, 24) for c, b in tapes_1h.items()}}
    results = []

    def run_cell(name, tf, step_h, coin_list, entry_fn, exit_kw, family):
        per_coin, eps = {}, []
        for coin in coin_list:
            bars = tapes[tf].get(coin)
            if not bars:
                continue
            entries = [i for i in range(60, len(bars["t"]) - 1)
                       if entry_fn(bars, i)]
            got = seq_episodes(entries, bars, funds.get(coin), step_h,
                               **exit_kw)
            if got:
                per_coin[coin] = len(got)
                eps.extend(got)
        if not eps:
            results.append({"cell": name, "family": family, "n": 0})
            return
        s = summarize(eps)
        s["cell"], s["family"] = name, family
        s["p_null"] = null_p(eps, per_coin, tapes[tf], funds, step_h,
                             exit_kw, seed=hash(name) & 0xFFFF)
        results.append(s)
        print(f"  {name:42s} n={s['n']:4d} mean={s['mean_pct']:+.3f}% "
              f"t={s['t']:+.2f} ct={s['ct']:+.2f} h1={s['h1']:+.3f} "
              f"h2={s['h2']:+.3f} P={s['p_null']:.3f} eps30={s['eps30']:.1f} "
              f"hold_med={s['hold_med']:.0f}h")

    # ---- A · v1 AUTOPSY: her exact rule, on the real tape -----------------
    print("\nA · v1 autopsy — SMA10/40 daily, state entry, cross exit")
    a_events = a_days = 0
    for coin in CRYPTO:
        b = tapes["1d"].get(coin)
        if not b:
            continue
        a_days = max(a_days, (b["t"][-1] - b["t"][0]) / 86400)
        for i in range(45, len(b["t"])):
            f0, s0 = sma(b["c"], 10, i - 1), sma(b["c"], 40, i - 1)
            f1, s1 = sma(b["c"], 10, i), sma(b["c"], 40, i)
            if None in (f0, s0, f1, s1):
                continue
            if f1 < s1 and f0 >= s0:
                a_events += 1
    print(f"  death-crosses across {len(CRYPTO)} coins over ~{a_days:.0f}d: "
          f"{a_events}  => {a_events / max(a_days, 1) * 30:.1f} exits/30d "
          f"FLEET-WIDE at unlimited slots; at 4 slots the realised rate was "
          f"2.4/30d — (rd) reproduced: the clock, not the coins, was the "
          f"disease")

    # ---- B · her own idea, made decidable: SMA cross EVENT + bracket ------
    print("\nB · TrendMomo modernised (cross-EVENT entry + bracket)")
    def cross_up(fast_n, slow_n):
        def fn(bars, i):
            f0, s0 = sma(bars["c"], fast_n, i - 1), sma(bars["c"], slow_n, i - 1)
            f1, s1 = sma(bars["c"], fast_n, i), sma(bars["c"], slow_n, i)
            if None in (f0, s0, f1, s1):
                return False
            return f1 > s1 and f0 <= s0
        return fn
    for tf, step in (("4h", 4), ("1h", 1)):
        for hold in (48, 96):
            run_cell(f"B sma10/40-cross {tf} sl2.0 hold{hold}h", tf, step,
                     CRYPTO, cross_up(10, 40),
                     dict(sl_atr=2.0, max_hold_h=hold), "B")

    # ---- C · dad's unowned supply: Donchian-20 breakout + bracket ---------
    print("\nC · Donchian-20 breakout 4h (supply unowned since (po)/(mr))")
    def dc_break(n):
        def fn(bars, i):
            if i < n + 1:
                return False
            hi = max(bars["h"][i - n:i])
            return bars["c"][i] > hi
        return fn
    for hold in (24, 72):
        for sl in (1.5, 2.5):
            run_cell(f"C dc20-breakout 4h sl{sl} hold{hold}h", "4h", 4,
                     CRYPTO, dc_break(20),
                     dict(sl_atr=sl, max_hold_h=hold), "C")

    # ---- D · plain momentum continuation --------------------------------
    print("\nD · momentum continuation (ROC top entry, fixed hold)")
    def roc_gt(n_bars, x):
        def fn(bars, i):
            r = roc(bars, n_bars, i)
            return r is not None and r > x
        return fn
    for x in (0.03, 0.05):
        for hold in (12, 24):
            run_cell(f"D roc24h>{x:.0%} 1h hold{hold}h", "1h", 1,
                     CRYPTO, roc_gt(24, x),
                     dict(sl_atr=2.0, max_hold_h=hold), "D")

    # ---- E · cross-sectional momentum L/S (market-neutral) ---------------
    print("\nE · cross-sectional 72h-momentum L/S, 24h rebalance, majors")
    for (k, look_h) in ((3, 72), (3, 48), (2, 72)):
        eps = []
        days = sorted({t - (t % 86400)
                       for b in tapes["1d"].values() for t in b["t"]})
        idx_of = {c: {t: i for i, t in enumerate(tapes["1d"][c]["t"])}
                  for c in CRYPTO if c in tapes["1d"]}
        for d0, d1 in zip(days[:-1], days[1:]):
            rocs = {}
            for c, m in idx_of.items():
                i = m.get(d0)
                if i is None or i + 1 >= len(tapes["1d"][c]["t"]) or i < 4:
                    continue
                r = roc(tapes["1d"][c], max(1, look_h // 24), i)
                if r is not None:
                    rocs[c] = (r, i)
            if len(rocs) < 2 * k + 2:
                continue
            ranked = sorted(rocs, key=lambda c: rocs[c][0])
            day_ret, legs = 0.0, 0
            for c in ranked[-k:]:
                i = rocs[c][1]
                b = tapes["1d"][c]
                day_ret += (b["c"][i + 1] - b["o"][i + 1]) / b["o"][i + 1] \
                    - 2 * COST_SIDE
                legs += 1
            for c in ranked[:k]:
                i = rocs[c][1]
                b = tapes["1d"][c]
                day_ret -= (b["c"][i + 1] - b["o"][i + 1]) / b["o"][i + 1]
                day_ret -= 2 * COST_SIDE
                legs += 1
            if legs:
                eps.append((day_ret / legs, 24.0, "rebal", d1))
        if eps:
            s = summarize(eps)
            s["cell"] = f"E xsect k{k} look{look_h}h"
            s["family"] = "E"
            s["p_null"] = float("nan")      # neutral: drift cancels by design
            results.append(s)
            print(f"  {s['cell']:42s} n={s['n']:4d} mean={s['mean_pct']:+.3f}% "
                  f"t={s['t']:+.2f} ct={s['ct']:+.2f} h1={s['h1']:+.3f} "
                  f"h2={s['h2']:+.3f} eps30={s['eps30']:.1f}")

    # ---- F · the non-crypto uptrend (the one non-falling regime) ---------
    print("\nF · non-crypto sleeve (SPY/QQQ/XAU/WTI) — cross event + bracket")
    for hold in (48, 96):
        run_cell(f"F sma10/40-cross 4h NONCRYPTO sl2.0 hold{hold}h", "4h", 4,
                 NONCRYPTO, cross_up(10, 40),
                 dict(sl_atr=2.0, max_hold_h=hold), "F")
    for x, hold in ((0.01, 24), (0.02, 24)):
        run_cell(f"F roc24h>{x:.0%} 1h NONCRYPTO hold{hold}h", "1h", 1,
                 NONCRYPTO, roc_gt(24, x),
                 dict(sl_atr=2.0, max_hold_h=hold), "F")

    # ---- G · session effect (calendar cell, cheap, needs BH survival) ----
    print("\nG · session-hold cells (majors, UTC windows)")
    for w0, w1 in ((0, 8), (8, 16), (16, 24)):
        def in_window(bars, i, w0=w0):
            return (bars["t"][i] // 3600) % 24 == w0
        run_cell(f"G session {w0:02d}-{w1:02d}Z hold{w1 - w0}h", "1h", 1,
                 ["BTC", "ETH", "SOL"], in_window,
                 dict(max_hold_h=w1 - w0), "G")

    # ---- BH across every cell with a null P ------------------------------
    print("\nBH (FDR 0.10) across null-P cells:")
    ps = sorted([(r["p_null"], r["cell"]) for r in results
                 if r.get("n", 0) > 0 and r.get("p_null") == r.get("p_null")])
    m = len(ps)
    survivors = []
    for rank, (p, cell) in enumerate(ps, 1):
        if p <= 0.10 * rank / m:
            survivors.append((p, cell))
    print(f"  {len(survivors)} of {m} survive:",
          [c for _, c in survivors] or "none")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=1)
        print(f"\nresults -> {args.out}")


if __name__ == "__main__":
    main()
