#!/usr/bin/env python3
"""PER-ASSET vs BTC regime gating on the venue's NON-CRYPTO books — the
item-18/D5 evidence study, full tape depth.

WHY (the decision this feeds, 4-Aug review): the 28-Jul review held step 2
("DO NOT wire the gate yet — the accrual is working, the n is not there";
self-grade bar n>=20/sym d1, ~mid-August). Those self-grades accrue at ~1
call/day. This study is the DEEP-HISTORY complement: it replays the oracle's
OWN method (regime_oracle.classify — same EMA50/200, ADX hysteresis, same
203-bar floor, prefix-exact because every component is causal) over each
non-crypto book's WHOLE Lighter 1d tape, so the per-asset question gets
hundreds of graded bars per book instead of five.

WHAT IT MEASURES (gate alignment, not a strategy backtest): for every graded
bar of every non-crypto book, two long-permission reads —
  own  = the asset's OWN oracle verdict == LONG-window  (what step 2 would consume)
  btc  = BTC 4h EMA50>EMA200                            (lighter_family_bot.btc_regime_up,
                                                         the gate D5 forbids for non-crypto)
— then forward returns of the ASSET at +1/+3 CLOSED bars, split by the 2x2
(btc, own) cells. The two decision cells:
  btc=1,own=0  — entries BTC's gate would ADMIT that the asset's own gate
                 refuses (the D5 damage cell: "risk-off 61.5% through SPY's
                 bull run" was the mirror of this);
  btc=0,own=1  — entries BTC's gate would BLOCK that the asset's own gate
                 would take.
If the asset's own gate is the better sensor, cell (1,0) forward returns are
poor and cell (0,1) forward returns are good.

LIMITS (stated): one venue tape (the only admissible one, per doctrine);
gate ALIGNMENT only — no entries/exits/slip/sizing (same object the oracle's
self-grades measure, at depth); books younger than 203 bars are NAMED, not
graded (SPY/QQQ/IWM/WTI/XCU/MSTR at 28-Jul — they graduate as the tape
accrues); long-permission framing because every family book is long-only.
The WIRING decision stays with the review — this prints evidence, changes
nothing, and consumes nothing at runtime.

    python3 scripts/study_per_asset_gate.py            # full available depth
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import regime_oracle as RO   # noqa: E402  (classify parity: constants + adx)

DEPTH_DAYS = 460             # past the venue's genesis — the pager stops itself
MIN_BARS = RO.EMA_SLOW + RO.SLOPE_BARS      # 203 — the oracle's own floor
HORIZONS = (1, 3)            # closed daily bars, = the oracle's self-grade

BTC_TF_S = 4 * 3600          # the family gate's timeframe
BTC_WARMUP = 210             # lighter_family_bot.btc_regime_up's floor


def fetch_bars(mid, resolution, step_s, depth_days):
    """Deep-paged closed candles -> DataFrame(t ms, o/h/l/c), oldest first.

    fetch_daily caps at LOOKBACK_DAYS=300 by design (the oracle needs a
    stable EMA200, not the whole tape); this study wants everything, so it
    pages with the same endpoint/stop conditions at arbitrary depth. The
    current PARTIAL bar is dropped by timestamp, like fetch_daily.
    """
    import time as _t
    now = int(_t.time())
    cur_open_ms = (now // step_s * step_s) * 1000
    cutoff = now - depth_days * 86400
    bars, end, oldest_seen = {}, now, None
    while True:
        rows = RO._lget("/api/v1/candles", market_id=mid,
                        resolution=resolution,
                        start_timestamp=end - 500 * step_s,
                        end_timestamp=end, count_back=500).get("c") or []
        if not rows:
            break
        for c in rows:
            bars[int(c["t"])] = (float(c["o"]), float(c["h"]),
                                 float(c["l"]), float(c["c"]))
        oldest = min(int(c["t"]) for c in rows) // 1000
        if oldest <= cutoff or (oldest_seen is not None
                                and oldest >= oldest_seen):
            break
        oldest_seen, end = oldest, oldest - step_s
    ts = sorted(t for t in bars if t < cur_open_ms)
    return pd.DataFrame({"t": ts,
                         "o": [bars[t][0] for t in ts],
                         "h": [bars[t][1] for t in ts],
                         "l": [bars[t][2] for t in ts],
                         "c": [bars[t][3] for t in ts]})


def verdict_series(df):
    """Point-in-time oracle verdicts for every bar index >= MIN_BARS-1.

    Exactly classify() on each prefix: EMA/ADX ewm recursions are causal, so
    the full-series value at index i equals the prefix value; the ADX
    hysteresis threads prev_trend forward exactly as the oracle's cycle loop
    does (prev_pairs[coin].trend).
    """
    e_fast = df["c"].ewm(span=RO.EMA_FAST, adjust=False).mean()
    e_slow = df["c"].ewm(span=RO.EMA_SLOW, adjust=False).mean()
    adx = RO.wilder_adx(df)
    out, prev_trend = {}, None
    for i in range(MIN_BARS - 1, len(df)):
        a = float(adx.iloc[i])
        close = float(df["c"].iloc[i])
        slope = float(e_fast.iloc[i] - e_fast.iloc[i - RO.SLOPE_BARS])
        up = close > float(e_slow.iloc[i]) and slope > 0
        down = close < float(e_slow.iloc[i]) and slope < 0
        direction = 1 if up else (-1 if down else 0)
        if a >= RO.ADX_TREND:
            trend = 1
        elif a <= RO.ADX_CHOP:
            trend = 0
        else:
            trend = prev_trend if prev_trend is not None else 0
        prev_trend = trend
        if trend and direction == 1:
            v = "LONG-window"
        elif trend and direction == -1:
            v = "SHORT-window"
        elif direction == 0:
            v = "dir-flat"
        else:
            v = "chop-gated"
        out[i] = v
    return out


def btc_up_series(df4):
    """Causal family-gate series on BTC 4h: e50>e200 per closed bar."""
    e50 = df4["c"].ewm(span=50, adjust=False).mean()
    e200 = df4["c"].ewm(span=200, adjust=False).mean()
    up = (e50 > e200)
    ts = df4["t"].to_numpy() // 1000                    # bar OPEN, s
    return ts, up.to_numpy()


def btc_up_at(ts_arr, up_arr, when_s):
    """The family read at time `when_s`: last CLOSED 4h bar's e50>e200.
    Fail-safe False before warmup — btc_regime_up's own missing-series
    default."""
    idx = np.searchsorted(ts_arr + BTC_TF_S, when_s, side="right") - 1
    if idx < BTC_WARMUP - 1:
        return False
    return bool(up_arr[idx])


def main():
    ids = RO.market_ids()
    print(f"PER-ASSET vs BTC gate — {len(RO.NONCRYPTO)} non-crypto books, "
          f"oracle method at full depth (floor {MIN_BARS} bars)")
    df4 = fetch_bars(ids["BTC"], "4h", BTC_TF_S, DEPTH_DAYS)
    bts, bup = btc_up_series(df4)
    print(f"BTC 4h: {len(df4)} bars "
          f"({(df4['t'].iloc[-1] - df4['t'].iloc[0]) / 86400000:.0f}d)")

    cells_all = {}                     # class -> cell -> [d1 list, d3 list]
    rows = []
    for sym in sorted(RO.NONCRYPTO):
        cls = RO.NONCRYPTO[sym]
        mid = ids.get(sym)
        if mid is None:
            rows.append((sym, cls, 0, "no-lighter-book"))
            continue
        df = fetch_bars(mid, "1d", 86400, DEPTH_DAYS)
        if len(df) < MIN_BARS + max(HORIZONS):
            rows.append((sym, cls, len(df), f"short-history({len(df)}<"
                                            f"{MIN_BARS + max(HORIZONS)})"))
            continue
        v = verdict_series(df)
        c = df["c"].to_numpy()
        t_ms = df["t"].to_numpy()
        cells = {}                     # (btc, own) -> {h: [pp,...]}
        n_own = n_btc = n_dis = 0
        graded = [i for i in sorted(v) if i + max(HORIZONS) < len(df)]
        for i in graded:
            own = v[i] == "LONG-window"
            btc = btc_up_at(bts, bup, t_ms[i] // 1000 + 86400)
            n_own += own
            n_btc += btc
            n_dis += (own != btc)
            cell = cells.setdefault((int(btc), int(own)),
                                    {h: [] for h in HORIZONS})
            for h in HORIZONS:
                cell[h].append(100.0 * (c[i + h] - c[i]) / c[i])
        n = len(graded)
        rows.append((sym, cls, n, None))
        print(f"\n{sym:5s} [{cls}] graded n={n} "
              f"({(t_ms[graded[-1]] - t_ms[graded[0]]) / 86400000:.0f}d) | "
              f"own-long {100 * n_own / n:.0f}% | btc-up {100 * n_btc / n:.0f}% | "
              f"DISAGREE {100 * n_dis / n:.0f}%")
        for (b, o) in sorted(cells):
            lab = {(1, 0): "btc=1 own=0  <- D5 damage cell",
                   (0, 1): "btc=0 own=1  <- blocked-by-btc cell",
                   (1, 1): "btc=1 own=1", (0, 0): "btc=0 own=0"}[(b, o)]
            d = cells[(b, o)]
            agg = cells_all.setdefault(cls, {}).setdefault(
                (b, o), {h: [] for h in HORIZONS})
            for h in HORIZONS:
                agg[h].extend(d[h])
            print(f"        {lab:36s} n={len(d[1]):4d} | "
                  f"fwd d1 {np.mean(d[1]):+6.2f}pp  d3 {np.mean(d[3]):+6.2f}pp")

    print("\n" + "=" * 78)
    print("POOLED BY CLASS (per-asset stays the signal — pooling is display):")
    for cls in sorted(cells_all):
        print(f"  {cls}:")
        for (b, o) in sorted(cells_all[cls]):
            d = cells_all[cls][(b, o)]
            if not d[1]:
                continue
            print(f"    btc={b} own={o}  n={len(d[1]):4d} | "
                  f"fwd d1 {np.mean(d[1]):+6.2f}pp  d3 {np.mean(d[3]):+6.2f}pp")
    ungraded = [(s, c, n, r) for s, c, n, r in rows if r]
    if ungraded:
        print("\nNOT GRADED (named, never silent): " +
              ", ".join(f"{s}({r})" for s, _, _, r in ungraded))
    print("\nREADOUT: if the (1,0) cell's forward pp is poor while (0,1) is "
          "good,\nBTC's gate is measurably the wrong sensor for these books "
          "— the per-asset\nwiring case strengthens. The wiring DECISION "
          "stays with the review (28-Jul:\nself-grade bar n>=20/sym; this is "
          "the deep-history complement, not a bypass).")


if __name__ == "__main__":
    main()
