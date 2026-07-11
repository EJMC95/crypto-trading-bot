#!/usr/bin/env python3
"""FAITHFUL leverage x rails sweep for the live Trail Blazer strategy.

Bar-by-bar global simulation (all coins on one 4h timeline):
  - marked-to-market equity every bar (like live account_value)
  - 5% daily rail + $10 fleet rail on marked equity -> FLATTEN (realize the
    drawdown at current closes, with slippage) + no new entries until next
    UTC day  == exactly what the live halt does
  - entries blocked while halted; 8-open / 2-new-per-bar caps as live
  - liquidation when intrabar adverse >= 1/L (margin gone before 8% stop)

This corrects the exit-time-bucketing artifact (which deleted losing trades
with hindsight and inflated rails-on returns).

VERDICT (2026-07-11, 180d to date): REJECTED — leverage does not work at any
setting, rails or no rails. 1x/-15.7%, 3x/-47%, 12x/-189% without rails;
WITH rails: 1x/-18%, 3x/-25% (18 halts), 5x+/-78..-99% (43-82 halts, win rate
56%->25%). Rails cap the tails but force-realize drawdowns at local lows — on
a dip-buying strategy the rail systematically sells the bottom, so rails +
leverage interact NEGATIVELY. Rails are venue-pathology insurance, not a
performance enabler; there is no edge here to lever (see
trail-blazer-no-durable-edge memory / 10 Jul sweep).
"""
import sys, time
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import backtest_leverage as bl
import numpy as np

PCT_RAIL, USD_RAIL = 0.05, 10.0
LEVERAGES = [1, 2, 3, 5, 8, 12]
MAX_OPEN, MAX_NEW = 8, 2


def load():
    data = {}
    for coin in bl.COINS:
        try:
            cs = bl.candles(coin)
            if len(cs) >= 25:
                data[coin] = cs
        except Exception as e:
            print(f"  {coin}: fetch failed ({e!r})")
        time.sleep(0.25)
    return data


def sim(data, L, rails):
    notional = bl.ORDER_USD * L
    # index candles by timestamp per coin
    seq = {c: {t: (o, h, l, cl) for (o, h, l, cl, t) in rows} for c, rows in data.items()}
    hist = {c: {"l": {}, "h": {}} for c in data}   # rolling windows via arrays
    arr = {c: np.array([[r[0], r[1], r[2], r[3], r[4]] for r in rows]) for c, rows in data.items()}
    idx = {c: {int(t): i for i, t in enumerate(arr[c][:, 4])} for c in data}
    ts_all = sorted({int(t) for rows in data.values() for (*_, t) in rows})

    eq_real = bl.COLLATERAL   # realized cash equity
    pos = {}                  # coin -> (entry_px, entry_ts_index_bar)
    peak, maxdd, wins, n, liq, halts = eq_real, 0.0, 0, 0, 0, 0
    day, day_start, halted = None, eq_real, False

    def bars_held(coin, i_now, ent_i):
        return i_now - ent_i

    for t in ts_all:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
        # mark equity at this bar's closes
        unreal = 0.0
        for c, (ent, _ei) in pos.items():
            i = idx[c].get(t)
            px = arr[c][i, 3] if i is not None else ent
            unreal += (px / ent - 1) * notional
        eq_mark = eq_real + unreal
        if d != day:
            day, day_start, halted = d, eq_mark, False

        opened = 0
        for c in list(data):
            i = idx[c].get(t)
            if i is None or i < 21:
                continue
            o, h, l_, cl = arr[c][i, 0], arr[c][i, 1], arr[c][i, 2], arr[c][i, 3]
            low20 = arr[c][i - 21:i - 1, 2].min()
            high20 = arr[c][i - 21:i - 1, 1].max()
            band = max(high20 - low20, 1e-9)
            buy_zone, sell_zone = low20 + .15 * band, high20 - .15 * band
            if c in pos:
                ent, ei = pos[c]
                adverse = (l_ - ent) / ent
                if adverse <= -1.0 / L and (1.0 / L) < bl.HARD_STOP:
                    eq_real -= bl.ORDER_USD; liq += 1; n += 1
                    del pos[c]; continue
                reason = None
                if cl <= ent * (1 - bl.HARD_STOP): reason = "stop"
                elif cl >= ent * (1 + bl.TAKE_PROFIT_PCT): reason = "tp"
                elif cl >= sell_zone: reason = "range_high"
                elif bars_held(c, i, ei) >= bl.MAX_HOLD_BARS: reason = "time"
                if reason:
                    ret = (cl - ent) / ent - bl.SLIP
                    eq_real += ret * notional
                    wins += 1 if ret > 0 else 0
                    n += 1
                    del pos[c]
            elif (not halted and cl <= buy_zone and len(pos) < MAX_OPEN
                  and opened < MAX_NEW):
                pos[c] = (cl * (1 + bl.SLIP), i)
                opened += 1

        # re-mark after closes/entries, then rail check (live checks each loop)
        unreal = 0.0
        for c, (ent, _ei) in pos.items():
            i = idx[c].get(t)
            px = arr[c][i, 3] if i is not None else ent
            unreal += (px / ent - 1) * notional
        eq_mark = eq_real + unreal
        if rails and not halted and day_start and (
                eq_mark <= day_start * (1 - PCT_RAIL)
                or day_start - eq_mark >= USD_RAIL):
            # flatten: realize at current closes with slippage
            for c in list(pos):
                ent, _ei = pos.pop(c)
                i = idx[c].get(t)
                px = arr[c][i, 3] if i is not None else ent
                ret = (px - ent) / ent - bl.SLIP
                eq_real += ret * notional
                wins += 1 if ret > 0 else 0
                n += 1
            halted = True
            halts += 1
            eq_mark = eq_real
        peak = max(peak, eq_mark)
        if peak > 0:
            maxdd = max(maxdd, (peak - eq_mark) / peak)

    retpct = (eq_real + sum((arr[c][-1, 3] / ent - 1) * notional
                            for c, (ent, _e) in pos.items()) - bl.COLLATERAL) \
        / bl.COLLATERAL * 100
    return retpct, maxdd * 100, (100 * wins / max(n, 1)), liq, halts, n


if __name__ == "__main__":
    print(f"FAITHFUL sweep | {bl.DAYS}d, ${bl.ORDER_USD} clip, ${bl.COLLATERAL} "
          f"collateral, caps {MAX_OPEN} open/{MAX_NEW} new-per-bar")
    data = load()
    print(f"coins loaded: {len(data)}")
    for rails in (False, True):
        print(f"\n{'lev':>4} {'ret%':>8} {'maxDD%':>8} {'win%':>6} {'liq':>4} "
              f"{'halts':>6} {'trades':>7}  ({'RAILS ON' if rails else 'no rails'})")
        for L in LEVERAGES:
            r, dd, w, lq, ha, n = sim(data, L, rails)
            print(f"{L:>4} {r:>8.1f} {dd:>8.1f} {w:>6.0f} {lq:>4} {ha:>6} {n:>7}")
