#!/usr/bin/env python3
"""
scripts/backtest_tide_rider_perp.py — GO-LIVE GATE for Tide Rider on LIGHTER.

Tide Rider is validated as a KRAKEN SPOT strategy (daily 50/200 golden cross,
long-only). On Lighter it can only run as a 1x LONG PERP — same price exposure,
zero fee, BUT a long perp PAYS funding, and this strategy holds long for weeks/
months during uptrends (exactly when funding runs hot). This quantifies that
funding drag against real history so we don't point real money at an unvalidated
perp version.

Method: daily 50/200 golden cross on Binance daily closes (spot price), then for
each long hold subtract the ACTUAL funding paid = sum of Hyperliquid hourly
funding over the hold (a long pays when funding>0). Reports, per coin and basket:
  spot_return  (the Kraken-validated figure) vs
  perp_return  (spot minus funding drag = what Lighter would actually deliver).
"""
import json
import os
import time
import urllib.request

FEE = 0.001               # slippage proxy; Lighter perp fee is ZERO
EMA_FAST, EMA_SLOW = 50, 200
DAYS = 1000
H = 24 * 365
CACHE = os.path.join(os.path.dirname(__file__), ".tiderider_perp_cache.json")
PAIRS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
         "BNB": "BNBUSDT", "XRP": "XRPUSDT", "TRX": "TRXUSDT"}
HL = "https://api.hyperliquid.xyz/info"


def _post(payload, tries=5):
    body = json.dumps(payload).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(HL, data=body,
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(0.6 * (i + 1))
    return None


def klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={DAYS}"
    req = urllib.request.Request(url, headers={"User-Agent": "bt"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    # (day_bucket_ms, close)
    return [((int(k[0]) // 86400000) * 86400000, float(k[4])) for k in rows]


def funding_by_day(coin):
    """{day_ms: summed_hourly_funding_that_day} from HL, paginated back DAYS."""
    day = {}
    seen = set()
    cursor = int((time.time() - DAYS * 86400) * 1000)
    end = int(time.time() * 1000)
    for _ in range(80):
        rows = _post({"type": "fundingHistory", "coin": coin,
                      "startTime": cursor, "endTime": end})
        if not rows:
            break
        new = 0
        for r in rows:
            t = int(r["time"])
            if t in seen:
                continue
            seen.add(t)
            d = (t // 86400000) * 86400000
            day[d] = day.get(d, 0.0) + float(r["fundingRate"])
            new += 1
        last = max(int(r["time"]) for r in rows)
        if new == 0 or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.28)
    return day


def load():
    if os.path.exists(CACHE) and "--refresh" not in os.sys.argv:
        try:
            raw = json.load(open(CACHE))
            return {c: {"k": [(int(t), v) for t, v in d["k"]],
                        "f": {int(t): v for t, v in d["f"].items()}}
                    for c, d in raw.items()}
        except Exception:
            pass
    data = {}
    for coin, sym in PAIRS.items():
        try:
            k = klines(sym)
            f = funding_by_day(coin)
            data[coin] = {"k": k, "f": f}
            print(f"  {coin:>4}: {len(k)} daily candles, {len(f)} funding-days")
        except Exception as e:
            print(f"  {coin:>4}: fetch failed {e!r}")
    try:
        json.dump({c: {"k": [[t, v] for t, v in d["k"]],
                       "f": {str(t): v for t, v in d["f"].items()}}
                   for c, d in data.items()}, open(CACHE, "w"))
    except Exception:
        pass
    return data


def ema(a, span):
    k = 2.0 / (span + 1.0)
    out = [a[0]]
    for i in range(1, len(a)):
        out.append(a[i] * k + out[-1] * (1 - k))
    return out


def replay(k, fday):
    """Golden-cross long/flat. Returns (spot_ret, perp_ret, n_trades, wins_perp,
    fund_drag_frac, frac_time_long)."""
    if len(k) < EMA_SLOW + 5:
        return None
    ts = [t for t, _ in k]
    closes = [c for _, c in k]
    ef, es = ema(closes, EMA_FAST), ema(closes, EMA_SLOW)
    eq_s = eq_p = 1.0
    in_pos = False; entry = 0.0; hold_fund = 0.0
    n = 0; wins_p = 0; drag_total = 0.0; days_long = 0; days_total = 0
    for i in range(EMA_SLOW, len(closes)):
        px = closes[i]
        days_total += 1
        long_ok = ef[i] > es[i]
        if in_pos:
            hold_fund += fday.get(ts[i], 0.0)     # a long pays this day's funding
            days_long += 1
        if not in_pos and long_ok:
            in_pos, entry, hold_fund = True, px * (1 + FEE), 0.0; n += 1
        elif in_pos and not long_ok:
            sret = px * (1 - FEE) / entry - 1.0
            pret = sret - hold_fund               # perp = spot minus funding paid
            eq_s *= (1 + sret); eq_p *= (1 + pret)
            wins_p += 1 if pret > 0 else 0
            drag_total += hold_fund
            in_pos = False
    if in_pos:  # close at last px
        px = closes[-1]
        sret = px * (1 - FEE) / entry - 1.0
        pret = sret - hold_fund
        eq_s *= (1 + sret); eq_p *= (1 + pret)
        wins_p += 1 if pret > 0 else 0
        drag_total += hold_fund
    return (eq_s - 1.0, eq_p - 1.0, n, wins_p, drag_total, days_long / max(1, days_total))


def main():
    print(f"Tide Rider on LIGHTER (1x long PERP) — {EMA_FAST}/{EMA_SLOW} golden cross, "
          f"funding drag from real HL history, ~{DAYS}d\n")
    data = load()
    print(f"\n{'coin':>4} {'spot%':>8} {'perp%':>8} {'fundDrag%':>9} {'%timeLong':>9} "
          f"{'trades':>7} {'perpWin%':>8}  verdict")
    s_sum = p_sum = 0.0; n_coins = 0
    for coin, d in data.items():
        r = replay(d["k"], d["f"])
        if not r:
            continue
        sret, pret, n, wp, drag, tlong = r
        n_coins += 1; s_sum += sret; p_sum += pret
        vp = "POSITIVE" if pret > 0.10 else ("marginal" if pret > 0 else "NEGATIVE on perp")
        print(f"{coin:>4} {sret*100:>8.1f} {pret*100:>8.1f} {drag*100:>9.1f} "
              f"{tlong*100:>8.0f}% {n:>7} {100*wp/max(1,n):>8.0f}  {vp}")
    if n_coins:
        print(f"\nBasket (equal-weight avg of {n_coins}): "
              f"spot {s_sum/n_coins*100:+.1f}%  ->  perp {p_sum/n_coins*100:+.1f}%  "
              f"(funding drag = {(s_sum-p_sum)/n_coins*100:.1f}pp)")
        print("\nGO-LIVE GATE: does the PERP column still clear a worthwhile return after "
              "the funding drag? If perp ~<= 0 or << spot, the Lighter (perp) version is "
              "not the Kraken-validated edge — say so before any real money.")


if __name__ == "__main__":
    import sys as _sys
    os.sys = _sys
    main()
