#!/usr/bin/env python3
"""
scripts/backtest_tide_rider_scanner.py — does a SCANNER that picks the best
positions beat Tide Rider's fixed 6-major universe?  (Lighter 1x long perp.)

Tide Rider today longs a FIXED set (BTC ETH SOL BNB XRP TRX) on each coin's
50/200 golden cross, up to MAX_OPEN slots. With only 6 coins and 6 slots there is
no competition — it just holds whatever is trending. A "scanner" only changes
anything under a CAPACITY CONSTRAINT: a WIDER universe than there are slots, where
the bot must CHOOSE which golden-cross coins get the few slots.

This replays the real portfolio so selection is isolated (same idea as the Funding
Farmer's scripts/backtest_scanner.py): each day, mark + manage open positions
(death-cross exit + 35% catastrophic seatbelt, funding accrued on the long), THEN
fill free slots with the TOP-SCORED golden-cross candidates. Only the score()
function differs between portfolios — everything else (signal, exits, fees,
funding, slot count) is identical, so any gap is the value of SELECTION.

Scorers compared (all on a WIDE universe, MAX_OPEN slots):
  alpha    neutral control — admit alphabetically (selection = none)
  trend    strongest established uptrend  (ema50-ema200)/ema200
  lowfund  cheapest to hold — lowest recent funding (a long PAYS funding)
  combo    z(trend) - z(recentFunding): strong trend AND cheap carry
vs the incumbent:
  majors6  the LIVE bot — fixed 6 majors, same slots

NO LOOK-AHEAD: the signal uses CLOSED daily bars only (EMA through day i, decide at
i's close); funding features use funding up to day i. Exactly what the live bot sees.

Perp return = spot price return MINUS funding paid over the hold (real HL hourly
funding, summed per day) — the same drag model as backtest_tide_rider_perp.py.

Usage:
    python scripts/backtest_tide_rider_scanner.py           # fetch (cached) + compare
    python scripts/backtest_tide_rider_scanner.py --refresh # refetch history
"""
import json
import math
import os
import sys
import time
import urllib.request

EMA_FAST, EMA_SLOW = 50, 200
DAYS = 1000
FEE = 0.001                 # slippage proxy per fill; Lighter perp fee is ZERO
MAX_OPEN = 6
CATASTROPHIC = 0.35         # seatbelt, matches lighter_trend_bot.py
FUND_LOOKBACK = 7           # days of funding averaged for the lowfund/combo score
HL = "https://api.hyperliquid.xyz/info"
CACHE = os.path.join(os.path.dirname(__file__), ".tiderider_scanner_cache.json")

MAJORS = ["BTC", "ETH", "SOL", "BNB", "XRP", "TRX"]
# Wide universe: liquid Lighter-listed perps that also have Binance daily klines +
# HL funding. Fetch failures are skipped, so a few misses are harmless.
UNIVERSE = MAJORS + [
    "DOGE", "ADA", "AVAX", "LINK", "DOT", "LTC", "BCH", "NEAR", "APT", "ARB",
    "OP", "SUI", "INJ", "TIA", "ATOM", "FIL", "RUNE", "AAVE", "UNI", "LDO",
]
BINANCE = {c: f"{c}USDT" for c in UNIVERSE}


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
    return [((int(k[0]) // 86400000) * 86400000, float(k[4])) for k in rows]


def funding_by_day(coin):
    day, seen = {}, set()
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
        time.sleep(0.25)
    return day


def load():
    if os.path.exists(CACHE) and "--refresh" not in sys.argv:
        try:
            raw = json.load(open(CACHE))
            return {c: {"k": [(int(t), v) for t, v in d["k"]],
                        "f": {int(t): v for t, v in d["f"].items()}}
                    for c, d in raw.items()}
        except Exception:
            pass
    data = {}
    for coin, sym in BINANCE.items():
        try:
            k = klines(sym)
            f = funding_by_day(coin)
            if len(k) >= EMA_SLOW + 5:
                data[coin] = {"k": k, "f": f}
                print(f"  {coin:>4}: {len(k)} daily candles, {len(f)} funding-days")
            else:
                print(f"  {coin:>4}: only {len(k)} candles — skip")
        except Exception as e:
            print(f"  {coin:>4}: fetch failed ({e!r}) — skip")
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


def build_series(data):
    """Align every coin onto the union daily timeline. Returns:
       days (sorted list of day_ms), and per coin a dict of index->(close, ef, es,
       recent_fund) plus funding-by-day. Missing days for a coin are absent."""
    days = sorted({t for d in data.values() for t, _ in d["k"]})
    idx = {t: i for i, t in enumerate(days)}
    coins = {}
    for c, d in data.items():
        closes_by_day = {t: px for t, px in d["k"]}
        # dense close list on the coin's own candle order for EMA
        ks = sorted(d["k"])
        ts = [t for t, _ in ks]
        cl = [px for _, px in ks]
        ef, es = ema(cl, EMA_FAST), ema(cl, EMA_SLOW)
        per_day = {}
        for j, t in enumerate(ts):
            if j < EMA_SLOW:
                continue
            # recent funding avg over the trailing FUND_LOOKBACK days (<= day t)
            rf = [d["f"].get(ts[k], 0.0) for k in range(max(0, j - FUND_LOOKBACK + 1), j + 1)]
            per_day[t] = {"c": cl[j], "ef": ef[j], "es": es[j],
                          "golden": ef[j] > es[j],
                          "rfund": sum(rf) / max(1, len(rf))}
        coins[c] = {"day": per_day, "f": d["f"]}
    return days, coins


# ----------------------------- scorers --------------------------------------
def score_alpha(coin, feat, ctx):
    return -ord(coin[0]) - (ord(coin[1]) if len(coin) > 1 else 0) / 100.0  # A first
def score_trend(coin, feat, ctx):
    return (feat["ef"] - feat["es"]) / feat["es"] if feat["es"] else 0.0
def score_lowfund(coin, feat, ctx):
    return -feat["rfund"]                     # lower funding = better for a long
def score_combo(coin, feat, ctx):
    zt = (score_trend(coin, feat, ctx) - ctx["tmean"]) / ctx["tstd"]
    zf = (feat["rfund"] - ctx["fmean"]) / ctx["fstd"]
    return zt - zf                            # strong trend AND cheap carry

SCORERS = {"alpha": score_alpha, "trend": score_trend,
           "lowfund": score_lowfund, "combo": score_combo}


def simulate(days, coins, universe, scorer, max_open=MAX_OPEN):
    """Slot-constrained portfolio. Each held slot is 1 unit of capital; basket
    return is normalized by max_open so unused (cash) slots don't inflate it.
    Returns dict of metrics + daily equity curve."""
    held = {}         # coin -> {entry, accrued}
    realized = 0.0    # sum of closed position (price+funding) returns, in unit terms
    n_trades = n_wins = 0
    drag_sum = 0.0
    eq_curve = []
    peak = 1.0; max_dd = 0.0
    pos_days = 0; total_slots_days = 0

    for t in days:
        # 1) manage open positions on today's close
        for c in list(held):
            feat = coins[c]["day"].get(t)
            if feat is None:
                continue  # coin has no bar today; carry
            px = feat["c"]
            held[c]["accrued"] += coins[c]["f"].get(t, 0.0)   # a long pays funding
            draw = (px - held[c]["entry"]) / held[c]["entry"]
            death = not feat["golden"]
            stop = draw <= -CATASTROPHIC
            if death or stop:
                sret = px * (1 - FEE) / held[c]["entry"] - 1.0
                pret = sret - held[c]["accrued"]
                realized += pret
                drag_sum += held[c]["accrued"]
                n_trades += 1; n_wins += 1 if pret > 0 else 0
                del held[c]
        # 2) fill free slots with top-scored golden-cross candidates
        free = max_open - len(held)
        total_slots_days += max_open
        pos_days += len(held)
        if free > 0:
            cands = []
            for c in universe:
                if c in held:
                    continue
                feat = coins.get(c, {}).get("day", {}).get(t)
                if feat and feat["golden"]:
                    cands.append((c, feat))
            if cands:
                seps = [(f["ef"] - f["es"]) / f["es"] if f["es"] else 0.0 for _, f in cands]
                rfs = [f["rfund"] for _, f in cands]
                ctx = {"tmean": sum(seps) / len(seps),
                       "tstd": (statpstd(seps) or 1.0),
                       "fmean": sum(rfs) / len(rfs),
                       "fstd": (statpstd(rfs) or 1.0)}
                cands.sort(key=lambda cf: scorer(cf[0], cf[1], ctx), reverse=True)
                for c, feat in cands[:free]:
                    held[c] = {"entry": feat["c"] * (1 + FEE), "accrued": 0.0}
        # 3) mark equity (realized + open MTM), normalized by slots
        open_mtm = 0.0
        for c in held:
            feat = coins[c]["day"].get(t)
            if feat:
                open_mtm += feat["c"] / held[c]["entry"] - 1.0 + held[c]["accrued"]
        eq = 1.0 + (realized + open_mtm) / max_open
        eq_curve.append(eq)
        peak = max(peak, eq); max_dd = min(max_dd, eq / peak - 1.0)

    # close survivors at last close
    last = days[-1]
    for c in list(held):
        feat = coins[c]["day"].get(last)
        if not feat:
            continue
        sret = feat["c"] * (1 - FEE) / held[c]["entry"] - 1.0
        pret = sret - held[c]["accrued"]
        realized += pret; drag_sum += held[c]["accrued"]
        n_trades += 1; n_wins += 1 if pret > 0 else 0
    basket = realized / max_open
    return {"basket": basket, "trades": n_trades, "winrate": n_wins / max(1, n_trades),
            "avg_drag": drag_sum / max(1, n_trades), "max_dd": max_dd,
            "avg_positions": pos_days / max(1, len(days)) if days else 0.0}


def statpstd(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def main():
    print("Tide Rider SCANNER backtest — does picking the best positions beat the "
          f"fixed 6 majors?  (1x long perp, {EMA_FAST}/{EMA_SLOW}, {MAX_OPEN} slots)\n")
    data = load()
    have = [c for c in UNIVERSE if c in data]
    print(f"\nuniverse loaded: {len(have)} coins — {', '.join(have)}")
    days, coins = build_series(data)
    print(f"timeline: {len(days)} days\n")

    rows = []
    # incumbent: fixed majors, neutral admit order (no competition anyway)
    rows.append(("majors6 (LIVE)", simulate(days, coins,
                 [c for c in MAJORS if c in coins], score_alpha)))
    for name in ("alpha", "trend", "lowfund", "combo"):
        rows.append((f"wide-{name}", simulate(days, coins, have, SCORERS[name])))

    print(f"{'portfolio':>16} {'perp%':>8} {'maxDD%':>8} {'win%':>6} {'avgDrag%':>9} "
          f"{'trades':>7} {'avgPos':>7}")
    print("-" * 72)
    base = None
    for name, m in rows:
        if base is None:
            base = m["basket"]
        print(f"{name:>16} {m['basket']*100:>8.1f} {m['max_dd']*100:>8.1f} "
              f"{m['winrate']*100:>6.0f} {m['avg_drag']*100:>9.2f} "
              f"{m['trades']:>7} {m['avg_positions']:>7.2f}")
    print("-" * 72)
    print("\nREAD: 'wide-alpha' is the neutral control (wider universe, NO selection "
          "skill). A scorer only EARNS its place if it beats BOTH majors6 AND wide-alpha "
          "on perp% at similar/better maxDD. If trend/lowfund/combo ~= alpha, selection "
          "adds nothing beyond universe size (cf. Trail Blazer: cherry-picking had no "
          "durable edge). Only wire a winner into the live bot.")

    # ---- Test 2: SELECTION WITHIN THE PROVEN MAJORS (no universe expansion) ----
    # "Pick the best positions" done right: keep the 6 majors, but concentrate into
    # FEWER slots — does holding the best-scored 3-4 beat spreading across all golden
    # majors? This is selection value without the toxic alt pollution above.
    print("\n\nTest 2 — concentrate INTO the best majors (universe = 6 majors, fewer slots):")
    majors_have = [c for c in MAJORS if c in coins]
    print(f"{'portfolio':>18} {'perp%':>8} {'maxDD%':>8} {'win%':>6} {'avgDrag%':>9} "
          f"{'trades':>7} {'avgPos':>7}")
    print("-" * 74)
    for k in (6, 4, 3):
        for name in (("alpha", "trend", "lowfund", "combo") if k < 6 else ("alpha",)):
            m = simulate(days, coins, majors_have, SCORERS[name], max_open=k)
            label = f"majors k={k} {name}" if k < 6 else f"majors k={k} (all)"
            print(f"{label:>18} {m['basket']*100:>8.1f} {m['max_dd']*100:>8.1f} "
                  f"{m['winrate']*100:>6.0f} {m['avg_drag']*100:>9.2f} "
                  f"{m['trades']:>7} {m['avg_positions']:>7.2f}")
    print("-" * 74)
    print("READ: k=6 holds every golden major (the LIVE bot). k=3/4 must CHOOSE. If a "
          "scorer at k=3/4 beats k=6 (higher perp% AND/OR lower maxDD), concentrating in "
          "the best majors is a real edge worth shipping. If not, holding all majors wins "
          "— the strategy already trades the best positions; leave it alone.")


if __name__ == "__main__":
    main()
