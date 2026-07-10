#!/usr/bin/env python3
"""
scripts/backtest_directional_funding.py — tune the Funding Farmer's RISK defaults.

The Funding Farmer (lighter_funding_bot.py) is DIRECTIONAL: it takes the
funding-receiving side of a hot perp (SHORT when funding>0, LONG when <0) and
collects funding while price risk is bounded by a HARD STOP. Its P&L =
price P&L (directional) + funding accrued. This replays that exact logic on real
Hyperliquid history (a good proxy for Lighter — same assets, ~arbitraged funding)
and sweeps the risk knobs so the defaults are chosen on evidence, not vibes.

Fidelity notes (learned the hard way, see memory):
  * The live bot polls every 5 min and stops on a FRESH mid, so an intrabar spike
    that breaches the stop DOES take us out — modelled here by checking the candle
    HIGH/LOW against the stop/TP (slightly pessimistic = safe for risk tuning).
  * Funding accrues hourly at the live rate (real funding history), with the
    position's sign; a rate that flips against us costs us, exactly as live.
  * Costs: Lighter perp fee is ZERO; the modelled friction is entry+exit slippage
    (SLIP), the honest cost on a zero-fee venue.

Reports per config: trades, total return on deployed capital, max drawdown,
win%, stop-out rate, and how much of the P&L is FUNDING vs PRICE — plus an
out-of-sample (recent-90d) column so we don't overfit the full window.
"""
import json
import os
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
H = 24 * 365
FETCH_DAYS = 150
ORDER_USD = 25.0
SLIP = 0.0005                 # 5bps entry+exit slippage (Lighter fee is 0)
PERSIST_H = 4
CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA", "LTC",
         "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP", "OP", "ARB", "TIA",
         "ENA", "SEI", "APT", "INJ", "RUNE", "STX", "GALA", "JTO", "PYTH", "W"]


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


def funding_history(coin):
    out, seen = [], set()
    cursor = int((time.time() - FETCH_DAYS * 86400) * 1000)
    end = int(time.time() * 1000)
    for _ in range(80):
        rows = _post({"type": "fundingHistory", "coin": coin,
                      "startTime": cursor, "endTime": end})
        if not rows:
            break
        new = 0
        for r in rows:
            t = (int(r["time"]) // 3600000) * 3600000   # floor to the hour (align w/ candles)
            if t in seen:
                continue
            seen.add(t)
            out.append((t, float(r["fundingRate"])))
            new += 1
        last = max(int(r["time"]) for r in rows)
        if new == 0 or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.3)
    return dict(out)


def candles_1h(coin):
    out, seen = {}, set()
    cursor = int((time.time() - FETCH_DAYS * 86400) * 1000)
    end = int(time.time() * 1000)
    for _ in range(80):
        rows = _post({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1h",
                      "startTime": cursor, "endTime": end}})
        if not rows:
            break
        new = 0
        for c in rows:
            t = int(c["t"])
            if t in seen:
                continue
            seen.add(t)
            out[t] = (float(c["o"]), float(c["h"]), float(c["l"]), float(c["c"]))
            new += 1
        last = max(int(c["t"]) for c in rows)
        if new == 0 or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.25)
    return out


def _floor_h(t):
    """Floor a ms timestamp to the top of its hour — HL funding stamps carry a
    few-ms offset while candle stamps are exact, so align both to the hour."""
    return (int(t) // 3600000) * 3600000


def load_data():
    if os.path.exists(CACHE) and "--refresh" not in os.sys.argv:
        try:
            raw = json.load(open(CACHE))
            return {c: {"f": {_floor_h(k): v for k, v in d["f"].items()},
                        "k": {int(k): tuple(v) for k, v in d["k"].items()}}
                    for c, d in raw.items()}
        except Exception:
            pass
    data = {}
    for coin in COINS:
        f = funding_history(coin)
        k = candles_1h(coin)
        if f and k:
            data[coin] = {"f": f, "k": k}
            print(f"  {coin:>6}: {len(f)} funding hrs, {len(k)} candles")
    try:
        json.dump({c: {"f": {str(t): v for t, v in d["f"].items()},
                       "k": {str(t): list(v) for t, v in d["k"].items()}}
                   for c, d in data.items()}, open(CACHE, "w"))
    except Exception:
        pass
    return data


def replay(coin, d, enter_apr, exit_apr, hard_stop, take_profit, max_hold_h):
    """Directional funding replay on one coin. Returns list of trades:
    (exit_ts, price_ret_frac, fund_ret_frac, reason)."""
    fmap, kmap = d["f"], d["k"]
    hours = sorted(set(fmap) & set(kmap))
    if len(hours) < PERSIST_H + 5:
        return []
    out = []
    pos = None          # (is_short, entry_px, entry_i, accrued_frac)
    hot = 0             # consecutive hot hours
    for idx in range(len(hours)):
        t = hours[idx]
        rate = fmap[t]
        apr = rate * H
        o, hi, lo, c = kmap[t]
        if pos is None:
            if abs(apr) >= enter_apr:
                hot += 1
            else:
                hot = 0
            if abs(apr) >= enter_apr and hot >= PERSIST_H:
                is_short = apr > 0
                pos = (is_short, c * (1 + SLIP * (-1 if is_short else 1)), idx, 0.0)
        else:
            is_short, ent, ei, accr = pos
            # accrue funding this hour (sign of the position)
            accr += (1.0 if is_short else -1.0) * rate
            # intrabar stop / take-profit (stop checked first = conservative)
            reason = None
            exit_px = None
            if is_short:
                if hi >= ent * (1 + hard_stop):
                    reason, exit_px = "stop", ent * (1 + hard_stop)
                elif take_profit and lo <= ent * (1 - take_profit):
                    reason, exit_px = "tp", ent * (1 - take_profit)
            else:
                if lo <= ent * (1 - hard_stop):
                    reason, exit_px = "stop", ent * (1 - hard_stop)
                elif take_profit and hi >= ent * (1 + take_profit):
                    reason, exit_px = "tp", ent * (1 + take_profit)
            if reason is None:  # close-based exits
                if (is_short and apr < 0) or (not is_short and apr > 0):
                    reason, exit_px = "flip", c
                elif abs(apr) < exit_apr:
                    reason, exit_px = "decay", c
                elif (idx - ei) >= max_hold_h:
                    reason, exit_px = "max_hold", c
            if reason:
                fill = exit_px * (1 - SLIP * (-1 if is_short else 1))
                price_ret = ((ent - fill) / ent) if is_short else ((fill - ent) / ent)
                out.append((t, price_ret, accr, reason))
                pos = None
                hot = 0
            else:
                pos = (is_short, ent, ei, accr)
    return out


def evaluate(data, enter_apr, exit_apr, hard_stop, take_profit, max_hold_h):
    trades = []
    for coin, d in data.items():
        trades += replay(coin, d, enter_apr, exit_apr, hard_stop, take_profit, max_hold_h)
    if not trades:
        return None
    trades.sort()
    now = time.time() * 1000
    split = now - 90 * 86400 * 1000
    eq = 0.0; peak = 0.0; maxdd = 0.0
    wins = stops = 0; price_sum = fund_sum = 0.0; oos = 0.0
    for ts, pr, fr, reason in trades:
        pnl = (pr + fr) * ORDER_USD
        eq += pnl
        peak = max(peak, eq); maxdd = max(maxdd, peak - eq)
        wins += 1 if pnl > 0 else 0
        stops += 1 if reason == "stop" else 0
        price_sum += pr * ORDER_USD; fund_sum += fr * ORDER_USD
        if ts >= split:
            oos += pnl
    n = len(trades)
    cap = ORDER_USD  # per-clip; report return per $ deployed per trade-slot
    return {"n": n, "ret": eq, "retpct": eq / cap * 100 / max(1, n) * n,  # $ on a $25 slot
            "maxdd": maxdd, "win": 100 * wins / n, "stoprate": 100 * stops / n,
            "price": price_sum, "fund": fund_sum, "oos": oos,
            "ret_dd": (eq / maxdd) if maxdd > 0 else float("inf")}


def main():
    print(f"Directional funding backtest — real HL funding+price, {FETCH_DAYS}d, "
          f"{len(COINS)} coins, ${ORDER_USD:.0f}/clip, {SLIP*2*1e4:.0f}bps round-trip slip\n")
    data = load_data()
    print(f"\n{len(data)} coins loaded.\n")

    # 1) STOP / TAKE-PROFIT sweep at the current entry config (40% enter, 15% exit, 72h)
    print("=== hard-stop x take-profit (enter 40%, exit 15%, max-hold 72h) ===")
    print(f"{'stop%':>5} {'tp%':>5} {'trades':>7} {'net$':>8} {'maxDD$':>7} {'win%':>5} "
          f"{'stop%':>6} {'price$':>8} {'fund$':>7} {'OOS$':>7} {'ret/DD':>7}")
    for stop in (0.03, 0.05, 0.08, 0.12):
        for tp in (0.0, 0.03, 0.04, 0.06):
            r = evaluate(data, 0.40, 0.15, stop, tp, 72)
            if not r:
                continue
            print(f"{stop*100:>5.0f} {tp*100:>5.0f} {r['n']:>7} {r['ret']:>8.1f} "
                  f"{r['maxdd']:>7.1f} {r['win']:>5.0f} {r['stoprate']:>6.0f} "
                  f"{r['price']:>8.1f} {r['fund']:>7.1f} {r['oos']:>7.1f} {r['ret_dd']:>7.2f}")

    # 2) ENTER threshold x max-hold (at a chosen stop/tp — filled from sweep 1 read)
    print("\n=== enter-APR x max-hold (stop 5%, tp 4%, exit 15%) ===")
    print(f"{'enter%':>6} {'hold_h':>6} {'trades':>7} {'net$':>8} {'maxDD$':>7} {'win%':>5} "
          f"{'fund$':>7} {'OOS$':>7} {'ret/DD':>7}")
    for ea in (0.30, 0.40, 0.60, 1.00):
        for mh in (24, 72, 168):
            r = evaluate(data, ea, ea * 0.375, 0.05, 0.04, mh)
            if not r:
                continue
            print(f"{ea*100:>6.0f} {mh:>6} {r['n']:>7} {r['ret']:>8.1f} {r['maxdd']:>7.1f} "
                  f"{r['win']:>5.0f} {r['fund']:>7.1f} {r['oos']:>7.1f} {r['ret_dd']:>7.2f}")


if __name__ == "__main__":
    import sys as _sys
    os.sys = _sys
    main()
