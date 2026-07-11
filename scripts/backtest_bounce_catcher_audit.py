#!/usr/bin/env python3
"""Durable-edge audit of Bounce Catcher's LIVE logic (hyperliquid_perps_bot.py)
— the same replay methodology that exposed Trail Blazer's paper record.

Live rules replayed exactly (1h candles, long-only):
  entry: flat + close <= low20 + 0.15*band (band excl. forming bar) + 4h
         per-coin cooldown since last action
  exit:  stop 3% adverse | TP +2% entry-relative | close >= sell_zone | 24h max
Portfolio: $10 clips (Lighter pilot sizing), 6 slots, 2 new/hour, $60
collateral, both-halves OOS split. No leverage (1x).

VERDICT (2026-07-12): REJECTED for live — full 150d -15.8% (maxDD 27.9%,
1031 trades), NEGATIVE IN BOTH HALVES (-22.3% / -8.1%). 57% win rate eaten
by 473 stop/time exits: the same dip-buyer-into-downtrends signature as
Trail Blazer (the RSI gate is vestigial since the 2026-07-01 rework — this
is structurally the SAME 20-candle range strategy on 1h instead of 4h).
The +$64 paper record is a favorable-window artifact. Do NOT fund; the
9 Jul 'Bounce Catcher ready for Lighter' assessment is superseded."""
import sys, time
from datetime import datetime, timezone
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import backtest_leverage as bl

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
         "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
         "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON",
         "kSHIB", "HYPE", "ZEC", "TAO"]
STOP, TP, MAX_HOLD_H, COOLDOWN_H = 0.03, 0.02, 24, 4
SLIP = 0.0005
ORDER_USD, SLOTS, MAX_NEW, COLLATERAL = 10.0, 6, 2, 60.0
DAYS = 150


def candles_1h(coin):
    import json, urllib.request
    start = int((time.time() - DAYS * 86400) * 1000)
    out, seen, cursor = [], set(), start
    end = int(time.time() * 1000)
    for _ in range(20):
        body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin,
                           "interval": "1h", "startTime": cursor, "endTime": end}}).encode()
        req = urllib.request.Request(bl.HL, data=body,
                                     headers={"Content-Type": "application/json"})
        rows = json.loads(urllib.request.urlopen(req, timeout=30).read())
        if not rows:
            break
        new = 0
        for c in rows:
            t = int(c["t"])
            if t not in seen:
                seen.add(t)
                out.append((float(c["o"]), float(c["h"]), float(c["l"]),
                            float(c["c"]), t))
                new += 1
        last = max(int(c["t"]) for c in rows)
        if new == 0 or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.2)
    out.sort(key=lambda r: r[4])
    return out


def sim(data, lo=None, hi=None):
    idx = {c: {t: i for i, t in enumerate(a[:, 4].astype(np.int64))} for c, a in data.items()}
    ts_all = sorted({int(t) for a in data.values() for t in a[:, 4]})
    if lo: ts_all = [t for t in ts_all if t >= lo]
    if hi: ts_all = [t for t in ts_all if t < hi]
    eq = COLLATERAL; peak = eq; maxdd = 0.0
    pos = {}       # coin -> (entry_px, entry_t)
    last_act = {}  # coin -> t
    n = wins = stops = 0
    for t in ts_all:
        opened = 0
        for c, a in data.items():
            i = idx[c].get(t)
            if i is None or i < 21:
                continue
            low20 = a[i - 21:i - 1, 2].min(); high20 = a[i - 21:i - 1, 1].max()
            band = max(high20 - low20, 1e-9)
            buy_zone, sell_zone = low20 + .15 * band, high20 - .15 * band
            cl = a[i, 3]
            if c in pos:
                ent, et = pos[c]
                reason = None
                if cl <= ent * (1 - STOP):        reason = "stop"
                elif cl >= ent * (1 + TP):        reason = "tp"
                elif cl >= sell_zone:             reason = "range"
                elif (t - et) >= MAX_HOLD_H * 3600 * 1000: reason = "time"
                if reason:
                    ret = (cl * (1 - SLIP)) / ent - 1
                    eq += ret * ORDER_USD
                    n += 1; wins += 1 if ret > 0 else 0
                    stops += 1 if reason in ("stop", "time") else 0
                    del pos[c]; last_act[c] = t
            elif (cl <= buy_zone and len(pos) < SLOTS and opened < MAX_NEW
                  and t - last_act.get(c, 0) >= COOLDOWN_H * 3600 * 1000):
                pos[c] = (cl * (1 + SLIP), t); last_act[c] = t; opened += 1
        peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak)
    # mark leftovers at last close
    for c, (ent, _) in pos.items():
        eq += (data[c][-1, 3] / ent - 1) * ORDER_USD
    return (eq - COLLATERAL) / COLLATERAL * 100, maxdd * 100, n, \
        (100 * wins / max(n, 1)), stops


if __name__ == "__main__":
    import json, os
    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bounce_1h_cache.json")
    if os.path.exists(CACHE):
        raw = json.load(open(CACHE))
        data = {c: np.array(v) for c, v in raw.items()}
    else:
        data = {}
        for coin in COINS:
            try:
                cs = candles_1h(coin)
                if len(cs) > 200:
                    data[coin] = np.array(cs)
                print(f"  {coin}: {len(cs)} bars")
            except Exception as e:
                print(f"  {coin}: failed ({e!r})")
        json.dump({c: a.tolist() for c, a in data.items()}, open(CACHE, "w"))
    print(f"coins: {len(data)} | {DAYS}d 1h | ${ORDER_USD} clips x {SLOTS} slots, ${COLLATERAL}")
    now_ms = max(int(a[-1, 4]) for a in data.values())
    split = now_ms - 75 * 86400 * 1000
    for name, lo, hi in (("FULL 150d", None, None),
                         ("1st half ", None, split),
                         ("2nd half ", split, None)):
        ret, dd, n, w, s = sim(data, lo, hi)
        print(f"  {name}: ret {ret:+7.1f}%  maxDD {dd:5.1f}%  trades {n:4d}  "
              f"win {w:3.0f}%  stops/time {s}")
