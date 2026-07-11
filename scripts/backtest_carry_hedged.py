#!/usr/bin/env python3
"""
scripts/backtest_carry_hedged.py — does a BOTH-PERP (major-hedge) funding carry
have a real edge on Lighter?  (Yield Harvester, self-custody variant.)

THE QUESTION
  Lighter is perp-only, so there is no same-coin spot hedge. The self-custody way
  to be delta-neutral is a SECOND perp: take the funding-receiving side of a hot
  alt A (SHORT if A funding>0), and hedge the delta with a beta-weighted position
  in a liquid MAJOR B (ETH/BTC) — LONG B when short A. That strips the *market*
  component of A's move but leaves A's IDIOSYNCRATIC move unhedged (a major cannot
  cancel a memecoin's own pump). This script measures whether that trade-off leaves
  a positive, market-neutral edge — or whether the hedge leg's own funding drag +
  double the slippage + residual idiosyncratic risk eats it.

WHAT IT COMPARES — same entry signals, three structures, so the deltas are honest:
  1. DIRECTIONAL   (Funding Farmer): 1 leg. price = full alt move; funding = alt.
  2. MAJOR-HEDGE   (this proposal):  2 perp legs. price = alt + beta*B (idiosyncratic
                                     residual); funding = alt - beta*B_funding; 4 fills.
  3. SPOT-HEDGE    (ideal, needs a CEX): 0 price risk; funding = full alt; ~20bps CEX
                                     round-trip. The authoritative number lives in
                                     scripts/backtest_funding.py — reproduced here on
                                     the same signals only for side-by-side context.

FIDELITY (same conventions as backtest_directional_funding.py, learned the hard way):
  * Real Hyperliquid hourly funding + 1h candles (a good Lighter proxy: same assets,
    ~arbitraged funding). Reuses that script's .dirfund_cache.json — no refetch.
  * Funding accrues hourly at the LIVE rate with each leg's sign (a flip costs us).
  * The hard stop / take-profit is checked on the NET (combined-leg) price path each
    hour using candle marks (close-to-close; intrabar wick not modelled on the net
    because the two legs' wicks don't co-occur — slightly optimistic on the stop,
    flagged). Lighter perp fee = 0; friction is SLIP per fill (4 fills hedged, 2 not).
  * beta = full-window OLS of alt hourly returns on B's — IN-SAMPLE (a live bot would
    use a trailing beta); a beta=1.0 naive-hedge column bounds the estimation error.

Usage:
    python scripts/backtest_carry_hedged.py            # ETH hedge, OLS beta
    python scripts/backtest_carry_hedged.py --hedge BTC
    python scripts/backtest_carry_hedged.py --refresh  # refetch HL history
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
H = 24 * 365
FETCH_DAYS = 150
ORDER_USD = 25.0                 # primary clip $ (hedge leg is beta*this)
SLIP = 0.0005                    # 5bps per fill (Lighter fee is 0)
SPOT_HEDGE_RT = 0.0020           # 20bps CEX spot round-trip (scope doc / backtest_funding)
PERSIST_H = 4
# Cache is shared with the directional backtest (same coins + window) — reuse it.
CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA", "LTC",
         "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP", "OP", "ARB", "TIA",
         "ENA", "SEI", "APT", "INJ", "RUNE", "STX", "GALA", "JTO", "PYTH", "W"]
MAJORS = {"BTC", "ETH"}          # never a *primary*; only the hedge leg


# --------------------------- data (mirrors backtest_directional_funding) ------
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
            t = (int(r["time"]) // 3600000) * 3600000
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
    return (int(t) // 3600000) * 3600000


def load_data(refresh):
    if os.path.exists(CACHE) and not refresh:
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


# --------------------------- beta -------------------------------------------
def ols_beta(alt_k, maj_k):
    """Full-window OLS beta of alt hourly close-returns on the major's. IN-SAMPLE
    (a live bot uses a trailing window); the beta=1.0 column bounds this error."""
    hours = sorted(set(alt_k) & set(maj_k))
    ra, rb = [], []
    for i in range(1, len(hours)):
        pa0, pa1 = alt_k[hours[i - 1]][3], alt_k[hours[i]][3]
        pb0, pb1 = maj_k[hours[i - 1]][3], maj_k[hours[i]][3]
        if pa0 and pb0:
            ra.append(pa1 / pa0 - 1.0)
            rb.append(pb1 / pb0 - 1.0)
    if len(rb) < 50:
        return None
    mb = sum(rb) / len(rb)
    ma = sum(ra) / len(ra)
    var = sum((x - mb) ** 2 for x in rb)
    if var <= 0:
        return None
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(len(rb)))
    return cov / var


# --------------------------- replay -----------------------------------------
def replay(coin, d, maj, beta, mode, enter_apr, exit_apr, hard_stop, take_profit,
           max_hold_h):
    """One coin. mode in {'directional','hedge','spot'}.
    Returns trades: (exit_ts, price_ret_frac, fund_ret_frac, reason). All returns
    are fractions of the PRIMARY clip (ORDER_USD); the hedge leg is beta*primary."""
    fmap, kmap = d["f"], d["k"]
    mk = maj["k"] if maj else {}
    mf = maj["f"] if maj else {}
    hours = sorted(set(fmap) & set(kmap) & (set(mk) if mode == "hedge" else set(kmap)))
    if len(hours) < PERSIST_H + 5:
        return []
    hedged = mode == "hedge"
    out = []
    pos = None       # (is_short, entA, entB, ei, accr_frac)
    hot = 0
    for idx in range(len(hours)):
        t = hours[idx]
        rate = fmap[t]
        apr = rate * H
        cA = kmap[t][3]
        cB = mk[t][3] if hedged else 0.0
        if pos is None:
            hot = hot + 1 if abs(apr) >= enter_apr else 0
            if abs(apr) >= enter_apr and hot >= PERSIST_H:
                is_short = apr > 0
                entA = cA * (1 + SLIP * (1 if is_short else -1))   # short sells low / adverse
                entB = cB * (1 + SLIP * (1 if not is_short else -1)) if hedged else 0.0
                pos = (is_short, entA, entB, idx, 0.0)
        else:
            is_short, entA, entB, ei, accr = pos
            # funding accrual this hour (fraction of primary clip)
            accr += (1.0 if is_short else -1.0) * rate
            if hedged:
                # hedge is opposite sign to primary; its notional is beta*primary
                rate_b = mf.get(t, 0.0)
                accr += (-1.0 if is_short else 1.0) * (-rate_b) * beta  # long B pays +funding
            # net price path from entry (fraction of primary clip)
            pa = (entA - cA) / entA if is_short else (cA - entA) / entA
            pb = 0.0
            if hedged:
                pb = ((cB - entB) / entB if is_short else (entB - cB) / entB) * beta
            net_px = pa + pb
            reason = None
            if net_px <= -hard_stop:
                reason = "stop"
            elif take_profit and net_px >= take_profit:
                reason = "tp"
            elif (is_short and apr < 0) or (not is_short and apr > 0):
                reason = "flip"
            elif abs(apr) < exit_apr:
                reason = "decay"
            elif (idx - ei) >= max_hold_h:
                reason = "max_hold"
            if reason:
                # exit fills: primary + (hedge) each pay SLIP again
                fillA = cA * (1 - SLIP * (1 if is_short else -1))
                pa = (entA - fillA) / entA if is_short else (fillA - entA) / entA
                pb = 0.0
                if hedged:
                    fillB = cB * (1 - SLIP * (1 if not is_short else -1))
                    pb = ((fillB - entB) / entB if is_short else (entB - fillB) / entB) * beta
                price_ret = pa + pb
                if mode == "spot":
                    # ideal: no price risk, full alt funding, 20bps CEX round-trip.
                    price_ret = -SPOT_HEDGE_RT
                out.append((t, price_ret, accr, reason))
                pos = None
                hot = 0
            else:
                pos = (is_short, entA, entB, ei, accr)
    return out


def evaluate(data, maj_key, betas, mode, enter_apr, exit_apr, hard_stop,
             take_profit, max_hold_h):
    maj = data.get(maj_key) if mode == "hedge" else None
    trades = []
    for coin, d in data.items():
        if coin in MAJORS:
            continue
        beta = betas.get(coin, 1.0) if mode == "hedge" else 0.0
        trades += replay(coin, d, maj, beta, mode, enter_apr, exit_apr, hard_stop,
                         take_profit, max_hold_h)
    if not trades:
        return None
    trades.sort()
    now = time.time() * 1000
    split = now - 90 * 86400 * 1000
    eq = peak = maxdd = 0.0
    wins = stops = 0
    price_sum = fund_sum = oos = 0.0
    for ts, pr, fr, reason in trades:
        pnl = (pr + fr) * ORDER_USD
        eq += pnl
        peak = max(peak, eq)
        maxdd = max(maxdd, peak - eq)
        wins += 1 if pnl > 0 else 0
        stops += 1 if reason == "stop" else 0
        price_sum += pr * ORDER_USD
        fund_sum += fr * ORDER_USD
        if ts >= split:
            oos += pnl
    n = len(trades)
    return {"n": n, "ret": eq, "maxdd": maxdd, "win": 100 * wins / n,
            "stoprate": 100 * stops / n, "price": price_sum, "fund": fund_sum,
            "oos": oos, "ret_dd": (eq / maxdd) if maxdd > 0 else float("inf")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hedge", default="ETH", choices=["ETH", "BTC"])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    print(f"Both-perp (major-hedge) carry backtest — real HL funding+price, "
          f"{FETCH_DAYS}d, ${ORDER_USD:.0f} primary clip, hedge={args.hedge}, "
          f"{SLIP*1e4:.0f}bps/fill\n")
    data = load_data(args.refresh)
    print(f"{len(data)} coins loaded.")
    if args.hedge not in data:
        print(f"hedge asset {args.hedge} missing from data — abort.")
        return

    # per-coin OLS beta vs the hedge major (in-sample)
    betas = {}
    for c, d in data.items():
        if c in MAJORS:
            continue
        b = ols_beta(d["k"], data[args.hedge]["k"])
        if b is not None:
            betas[c] = b
    if betas:
        bs = sorted(betas.values())
        print(f"per-coin beta vs {args.hedge}: median {bs[len(bs)//2]:.2f}, "
              f"range [{bs[0]:.2f}, {bs[-1]:.2f}] over {len(betas)} coins\n")

    cfg = dict(enter_apr=0.40, exit_apr=0.15, hard_stop=0.10, take_profit=0.04,
               max_hold_h=72)
    print("=== structure comparison — SAME signals (enter 40%, exit 15%, "
          "stop 10%, tp 4%, hold 72h) ===")
    print(f"{'structure':>16} {'trades':>7} {'net$':>8} {'maxDD$':>7} {'win%':>5} "
          f"{'stop%':>6} {'price$':>8} {'fund$':>7} {'OOS$':>7} {'ret/DD':>7}")
    rows = [
        ("directional", evaluate(data, None, betas, "directional", **cfg)),
        (f"hedge β·{args.hedge}", evaluate(data, args.hedge, betas, "hedge", **cfg)),
        (f"hedge 1·{args.hedge}", evaluate(data, args.hedge,
                                           {c: 1.0 for c in betas}, "hedge", **cfg)),
        ("spot-hedge(ideal)", evaluate(data, None, betas, "spot", **cfg)),
    ]
    for name, r in rows:
        if not r:
            print(f"{name:>16}   (no trades)")
            continue
        print(f"{name:>16} {r['n']:>7} {r['ret']:>8.1f} {r['maxdd']:>7.1f} "
              f"{r['win']:>5.0f} {r['stoprate']:>6.0f} {r['price']:>8.1f} "
              f"{r['fund']:>7.1f} {r['oos']:>7.1f} {r['ret_dd']:>7.2f}")

    # sensitivity: does a wider gate (only the hottest, most persistent) help the
    # hedged structure? — funding must beat the hedge's own drag + 4-leg slip.
    print(f"\n=== major-hedge (β·{args.hedge}) enter-APR x hard-stop sensitivity ===")
    print(f"{'enter%':>6} {'stop%':>5} {'trades':>7} {'net$':>8} {'maxDD$':>7} "
          f"{'win%':>5} {'fund$':>7} {'price$':>8} {'OOS$':>7} {'ret/DD':>7}")
    for ea in (0.40, 0.60, 1.00):
        for stop in (0.06, 0.10, 0.20):
            r = evaluate(data, args.hedge, betas, "hedge", enter_apr=ea,
                         exit_apr=ea * 0.375, hard_stop=stop, take_profit=0.04,
                         max_hold_h=72)
            if not r:
                continue
            print(f"{ea*100:>6.0f} {stop*100:>5.0f} {r['n']:>7} {r['ret']:>8.1f} "
                  f"{r['maxdd']:>7.1f} {r['win']:>5.0f} {r['fund']:>7.1f} "
                  f"{r['price']:>8.1f} {r['oos']:>7.1f} {r['ret_dd']:>7.2f}")

    print("\nNotes: $ are per $25 primary clip over 150d, summed across all trade "
          "slots (not annualized). 'price$' for the hedge rows is the residual "
          "idiosyncratic move after beta-stripping; 'fund$' is alt funding NET of "
          "the hedge leg's funding drag. Spot-hedge row is the ideal (CEX) bound.")


if __name__ == "__main__":
    main()
