#!/usr/bin/env python3
"""
VERDICT (2026-07-12): REJECTED — do not rebuild, do not re-test.
Even on this 2022-inclusive window (the thesis's BEST case) the gate fails
the doctrine bars: the 2022 crash-dodge is half-only and is paid back by a
~185pp 2023 re-entry miss; not robust across index/lookback; Tide Rider
dodges 2022 natively and better. See backtest_index_pilot_macro.py header
and memory/index-pilot-lighter-rejected.md.

scripts/backtest_index_pilot_macro_long.py — the EXOGENOUS equity-macro-gate test
(see backtest_index_pilot_macro.py) re-run on a LONGER window that INCLUDES the
2022 risk-off period — the equity-bear/crypto-bear overlap that the ~2.7y HL window
never saw. This is the thesis's best case: if a SPY/QQQ risk-on gate ever earns its
keep, it is by going flat through the 2022 crypto collapse while SPY was sub-SMA200.

DATA (longer history than HL provides):
  * Crypto: Binance daily klines + real Binance perp funding (summed to daily) for the
    SAME 6 majors Tide Rider is validated on. All coins aligned to a common date grid
    (intersection) so index windows == calendar windows across coins. ~2020-09 -> 2026-07;
    scored from +200d warmup (~2021-04), so 2022 is fully in-sample.
  * Equity: SPY/QQQ daily closes from Yahoo back to 2020-01 (SMA200 warm before 2021).
  * Cached to .index_pilot_long_cache.json for offline reruns.

ENGINE + GATE + DOCTRINE BARS: identical to backtest_index_pilot_macro.py — the gate is
the ONLY change on the shootout basket engine; scored full + both halves; MIRROR test
(long-in-risk-OFF must be symmetrically worse); robustness sweep over lookback/def.
PLUS a per-calendar-year table so the 2022 behaviour is visible on its own.

Usage:  python scripts/backtest_index_pilot_macro_long.py
"""
import bisect
import datetime
import importlib.util
import json
import os
import time
import urllib.request

_here = os.path.dirname(__file__)
def _load(mod, fname):
    sp = importlib.util.spec_from_file_location(mod, os.path.join(_here, fname))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
S = _load("shoot", "backtest_strategy_shootout.py")          # engine: ema/sma/SIGNALS/basket
M = _load("macro", "backtest_index_pilot_macro.py")          # gate helpers: equity_regime/align_to_coin/rr

MAJORS = S.MAJORS                                            # BTC ETH SOL BNB XRP TRX
CACHE = os.path.join(_here, ".index_pilot_long_cache.json")
WARM = 200
BINANCE = "https://api.binance.com/api/v3/klines"
FAPI = "https://fapi.binance.com/fapi/v1/fundingRate"
START = int(datetime.datetime(2020, 7, 1).timestamp() * 1000)
END = int(datetime.datetime(2026, 7, 11).timestamp() * 1000)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _klines(sym):
    out = {}; cur = START
    while cur < END:
        rows = _get(f"{BINANCE}?symbol={sym}&interval=1d&startTime={cur}&endTime={END}&limit=1000")
        if not rows:
            break
        for r in rows:
            out[int(r[0])] = float(r[4])          # openTime(ms 00:00 UTC) -> close
        if len(rows) < 1000:
            break
        cur = int(rows[-1][0]) + 86_400_000
        time.sleep(0.15)
    return out


def _funding_daily(sym):
    """Sum the 3x/day funding events into a per-day long-cost, keyed by day-ordinal."""
    ev = []; cur = START
    while cur < END:
        rows = _get(f"{FAPI}?symbol={sym}&startTime={cur}&endTime={END}&limit=1000")
        if not rows:
            break
        ev += rows
        if len(rows) < 1000:
            break
        cur = int(rows[-1]["fundingTime"]) + 1
        time.sleep(0.15)
    daily = {}
    for r in ev:
        d = datetime.datetime.utcfromtimestamp(int(r["fundingTime"]) / 1000).date().toordinal()
        daily[d] = daily.get(d, 0.0) + float(r["fundingRate"])
    return daily


def build_crypto():
    if os.path.exists(CACHE):
        raw = json.load(open(CACHE))
        return {c: {"t": v["t"], "c": v["c"], "f": {int(k): x for k, x in v["f"].items()}}
                for c, v in raw["data"].items()}, raw["dates"]
    per = {}
    for c in MAJORS:
        sym = c + "USDT"
        print(f"  fetching {sym} …", flush=True)
        kl = _klines(sym); fd = _funding_daily(sym)
        per[c] = (kl, fd)
    # common date grid = ordinals present for ALL coins
    ords = None
    for c in MAJORS:
        s = {datetime.datetime.utcfromtimestamp(t / 1000).date().toordinal() for t in per[c][0]}
        ords = s if ords is None else (ords & s)
    dates = sorted(ords)
    data = {}
    for c in MAJORS:
        kl, fd = per[c]
        by_ord = {datetime.datetime.utcfromtimestamp(t / 1000).date().toordinal(): (t, cl)
                  for t, cl in kl.items()}
        t_arr, c_arr, f_map = [], [], {}
        for d in dates:
            tms, cl = by_ord[d]
            t_arr.append(tms); c_arr.append(cl); f_map[tms] = fd.get(d, 0.0)
        data[c] = {"t": t_arr, "c": c_arr, "f": f_map}
    json.dump({"dates": dates,
               "data": {c: {"t": v["t"], "c": v["c"], "f": {str(k): x for k, x in v["f"].items()}}
                        for c, v in data.items()}}, open(CACHE, "w"))
    return data, dates


def build_equity():
    ec = os.path.join(_here, ".index_pilot_long_equity.json")
    if os.path.exists(ec):
        return {k: [tuple(x) for x in v] for k, v in json.load(open(ec)).items()}
    p1 = int(datetime.datetime(2020, 1, 1).timestamp()); p2 = int(datetime.datetime(2026, 7, 11).timestamp())
    out = {}
    for sym in ("SPY", "QQQ"):
        u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
             f"?period1={p1}&period2={p2}&interval=1d")
        r = _get(u)["chart"]["result"][0]
        ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
        out[sym] = [[datetime.datetime.utcfromtimestamp(t).date().toordinal(), float(c)]
                    for t, c in zip(ts, cl) if c is not None]
        out[sym].sort()
    json.dump(out, open(ec, "w"))
    return {k: [tuple(x) for x in v] for k, v in out.items()}


def score(data, base_seqs, gate_seqs, lo, hi):
    seqs = {}
    for c in data:
        b = base_seqs[c]
        seqs[c] = b if gate_seqs is None else [b[i] and gate_seqs[c][i] for i in range(len(b))]
    return S.basket(data, seqs, WARM, lo, hi)


def frow(tag, full, h1, h2, note=""):
    dur = "YES" if (h1["ret"] > 0.05 and h2["ret"] > 0.05) else (
          "half" if (h1["ret"] > 0.05 or h2["ret"] > 0.05) else "no")
    print(f"{tag:>24} | {full['ret']*100:>7.1f} {full['mdd']*100:>7.1f} {M.rr(full):>6.2f} "
          f"{full['pct_long']*100:>4.0f}% | {h1['ret']*100:>7.1f} {h2['ret']*100:>7.1f} "
          f"{dur:>4} | {note}")


def main():
    print("Building longer crypto dataset (Binance klines + real funding) …", flush=True)
    data, dates = build_crypto()
    eq = build_equity()
    N = len(dates); mid = N // 2
    y0 = datetime.date.fromordinal(dates[0]).isoformat()
    y1 = datetime.date.fromordinal(dates[-1]).isoformat()
    print(f"crypto grid: {N}d  {y0} → {y1}  (scored from +{WARM}d warmup ≈ "
          f"{datetime.date.fromordinal(dates[WARM]).isoformat()})\n")

    bases = {}
    for name in ("buy_hold", "tide_50_200"):
        bases[name] = {c: S.SIGNALS[name](data[c]["c"])[0] for c in data}

    def gate(sym, kind, invert=False):
        dts, reg = M.equity_regime(eq[sym], kind)
        return {c: M.align_to_coin(data[c]["t"], dts, reg, invert) for c in data}

    hdr = (f"{'variant':>24} | {'FULL%':>7} {'maxDD%':>7} {'ret/DD':>6} {'%lng':>4} "
           f"| {'H1%':>7} {'H2%':>7} {'dur':>4} | note")
    print(f"Index Pilot exogenous macro gate — LONG window incl. 2022 bear. 6 majors, 1x perp, "
          f"real Binance funding.\nH1≈{datetime.date.fromordinal(dates[WARM]).isoformat()}→"
          f"{datetime.date.fromordinal(dates[mid]).isoformat()} (has the 2022 risk-off), "
          f"H2≈{datetime.date.fromordinal(dates[mid]).isoformat()}→{y1}.\n")
    print(hdr); print("-" * len(hdr))
    for b in ("buy_hold", "tide_50_200"):
        frow(f"{b} (UNGATED)", score(data, bases[b], None, 0, N),
             score(data, bases[b], None, 0, mid), score(data, bases[b], None, mid, N), "reference")
    print("-" * len(hdr))
    for b in ("buy_hold", "tide_50_200"):
        for sym in ("SPY", "QQQ"):
            g = gate(sym, "sma200")
            frow(f"{b} x {sym}>SMA200", score(data, bases[b], g, 0, N),
                 score(data, bases[b], g, 0, mid), score(data, bases[b], g, mid, N), "risk-on gate")
    print("-" * len(hdr))
    for b in ("buy_hold", "tide_50_200"):
        g = gate("SPY", "sma200", invert=True)
        frow(f"{b} x SPY<SMA200", score(data, bases[b], g, 0, N),
             score(data, bases[b], g, 0, mid), score(data, bases[b], g, mid, N),
             "MIRROR (risk-OFF) — should be worse")
    print("-" * len(hdr))

    # per-calendar-year: does the risk-on gate actually dodge the 2022 crash?
    print("\nPer-year (buy_hold): UNGATED vs risk-ON gate vs MIRROR risk-OFF — the 2022 test:")
    print(f"{'year':>6} | {'ungated%':>9} {'gatedON%':>9} {'mirrorOFF%':>10} | {'gate %long':>10} | note")
    print("-" * 70)
    gon = gate("SPY", "sma200"); goff = gate("SPY", "sma200", invert=True)
    for yr in range(2021, 2027):
        idx = [i for i, d in enumerate(dates) if datetime.date.fromordinal(d).year == yr]
        if len(idx) < 20:
            continue
        lo, hi = idx[0], idx[-1] + 1
        if lo < WARM + 1:
            lo = WARM + 1
        if hi - lo < 20:
            continue
        u = score(data, bases["buy_hold"], None, lo, hi)
        gn = score(data, bases["buy_hold"], gon, lo, hi)
        gf = score(data, bases["buy_hold"], goff, lo, hi)
        note = "← 2022 bear (gate's best case)" if yr == 2022 else ""
        print(f"{yr:>6} | {u['ret']*100:>9.1f} {gn['ret']*100:>9.1f} {gf['ret']*100:>10.1f} "
              f"| {gn['pct_long']*100:>9.0f}% | {note}")
    print("-" * 70)

    print("\nRobustness (buy_hold × SPY gate) over lookback/def on the long window:")
    print(hdr); print("-" * len(hdr))
    for kind in ("sma100", "sma150", "sma200", "golden"):
        g = gate("SPY", kind)
        frow(f"buy_hold x SPY {kind}", score(data, bases["buy_hold"], g, 0, N),
             score(data, bases["buy_hold"], g, 0, mid), score(data, bases["buy_hold"], g, mid, N))
    print("-" * len(hdr))
    print("\nVERDICT criteria unchanged: gate earns a build only if it beats its UNGATED base in "
          "BOTH halves (ret or ret/DD), the MIRROR is clearly worse, AND it is robust. The 2022 "
          "year-row is the decisive look — a real risk-on gate should crush ungated there.")


if __name__ == "__main__":
    main()
