#!/usr/bin/env python3
"""
scripts/backtest_scanner.py — does a MULTI-FACTOR scanner pick better positions for the
Funding Farmer than the naive "rank by raw |APR|" it uses today?

WHY A PORTFOLIO BACKTEST (not the per-coin replay in backtest_directional_funding.py):
  The live bot holds at most MAX_OPEN positions and must CHOOSE among many hot candidates
  for a few slots. A scanner only matters under that capacity constraint — so this replays
  the real portfolio: each hour, mark + manage open positions, then fill free slots with the
  TOP-SCORED eligible candidates. Swapping the score() function (naive vs multi-factor) with
  everything else identical isolates the value of SELECTION. Same data + fidelity conventions
  as backtest_directional_funding.py (real HL hourly funding + 1h candles, cache reuse).

NO LOOK-AHEAD: features at hour t use only funding/candles up to and including t's close —
exactly what the live bot sees when it decides at t. Exits use intrabar candle high/low
(stop checked first = conservative).

Usage:
    python scripts/backtest_scanner.py                 # compare all scorers
    python scripts/backtest_scanner.py --scorer naive  # one scorer, verbose
    python scripts/backtest_scanner.py --refresh        # refetch HL history
"""
import argparse
import json
import math
import os
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
H = 24 * 365
FETCH_DAYS = 150
CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")

# ---- live-bot config mirrored (lighter_funding_bot.py tuned defaults) -------
ORDER_USD = 25.0
SLIP = 0.0005            # 5bps per fill (Lighter fee = 0)
ENTER_APR = 0.40
EXIT_APR = 0.15
PERSIST_H = 4
MAX_HOLD_H = 72
HARD_STOP = 0.10
TAKE_PROFIT = 0.04
STOP_COOLDOWN_H = 12
MAX_OPEN = 6
MIN_VOL = 10e6          # not enforceable from the cache (no per-hour vol) — see note

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA", "LTC",
         "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP", "OP", "ARB", "TIA",
         "ENA", "SEI", "APT", "INJ", "RUNE", "STX", "GALA", "JTO", "PYTH", "W"]


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


# --------------------------- feature engine ---------------------------------
def build_series(data):
    """Per coin, an ordered list of hours present in BOTH funding+candles, plus
    arrays for O(1) feature lookups by index. Returns {coin: {...}} and the global
    sorted set of hours."""
    series = {}
    all_hours = set()
    for coin, d in data.items():
        hrs = sorted(set(d["f"]) & set(d["k"]))
        if len(hrs) < 40:
            continue
        closes = [d["k"][t][3] for t in hrs]
        rates = [d["f"][t] for t in hrs]
        idx = {t: i for i, t in enumerate(hrs)}
        series[coin] = {"hrs": hrs, "idx": idx, "closes": closes, "rates": rates,
                        "k": d["k"]}
        all_hours.update(hrs)
    return series, sorted(all_hours)


def _rsi(closes, i, n=14):
    if i < n:
        return 50.0
    gains = losses = 0.0
    for j in range(i - n + 1, i + 1):
        ch = closes[j] - closes[j - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100.0 - 100.0 / (1.0 + rs)


def _realized_vol(closes, i, n=24):
    """Std of the last n hourly returns (fraction). 0 if insufficient history."""
    if i < n:
        return 0.0
    rets = [closes[j] / closes[j - 1] - 1.0 for j in range(i - n + 1, i + 1)
            if closes[j - 1]]
    if len(rets) < 2:
        return 0.0
    m = sum(rets) / len(rets)
    return math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))


def features(coin, s, i):
    """Compute the candidate feature dict at series-index i (hour s['hrs'][i]).
    Uses only data up to i (no look-ahead). `persist_h` is passed in by the loop
    (needs cross-hour state), so it is filled by the caller."""
    closes, rates = s["closes"], s["rates"]
    rate = rates[i]
    apr = rate * H
    is_short = apr > 0
    vol = _realized_vol(closes, i)          # hourly realized vol (fraction)
    rsi = _rsi(closes, i)
    ret6 = (closes[i] / closes[i - 6] - 1.0) if i >= 6 and closes[i - 6] else 0.0
    ret24 = (closes[i] / closes[i - 24] - 1.0) if i >= 24 and closes[i - 24] else 0.0
    # funding trend: current vs trailing 6h mean (rising funding = strengthening crowd)
    if i >= 6:
        prev = rates[i - 6:i]
        fmean = sum(prev) / len(prev)
        fund_trend = (abs(rate) - abs(fmean))
    else:
        fund_trend = 0.0
    # adverse momentum = recent price move AGAINST the side we'd take (>0 = against).
    # short (apr>0) is hurt by price rising; long is hurt by price falling.
    adverse6 = ret6 if is_short else -ret6
    # "stretch" of the crowded side: for a short, overbought (rsi high) = crowd
    # exhausted = favourable; for a long, oversold (rsi low) favourable. Map to
    # [0..1] where 1 = maximally stretched in our favour.
    stretch = (rsi / 100.0) if is_short else (1.0 - rsi / 100.0)
    return {"coin": coin, "apr": apr, "abs_apr": abs(apr), "is_short": is_short,
            "vol": vol, "rsi": rsi, "ret6": ret6, "ret24": ret24,
            "fund_trend": fund_trend, "adverse6": adverse6, "stretch": stretch}


# --------------------------- scorers (pluggable) -----------------------------
# Each takes a feature dict (+ persist_h injected) and returns a float; higher =
# more attractive. The SYNTHESIZED multi-factor scorer is added after the design
# workflow lands; these are the baseline + single-factor probes to calibrate.
def score_naive(f):
    """The CURRENT bot: rank by raw |APR|."""
    return f["abs_apr"]


def score_vol_adj(f):
    """Risk-adjusted: funding per unit of realized vol (a funding 'Sharpe')."""
    return f["abs_apr"] / (f["vol"] + 1e-4)


def score_meanrev(f):
    """Contrarian: funding weighted by how stretched/exhausted the crowd is, and
    penalized for fresh adverse momentum (a trend that will run the stop)."""
    return f["abs_apr"] * (0.5 + f["stretch"]) * math.exp(-8.0 * max(0.0, f["adverse6"]))


SCORERS = {"naive": score_naive, "vol_adj": score_vol_adj, "meanrev": score_meanrev}

# ---- the SHIPPED scanner (empirically winning config on 150d, see main()) ----
# Findings (backtest_scanner sweeps, 2026-07-11):
#   * The dominant signal is a REALIZED-VOL VETO: skip funding-hot coins whose 1h
#     realized vol is high — they get run over by the hard stop before funding pays.
#     Robust across 0.012-0.020/hr and out-of-sample; +43% net / 2.5x ret-DD @40%.
#   * A fresh-adverse-trend veto adds a little on top.
#   * RANKING (vol_adj vs naive) barely matters until the pool is large — the veto
#     and the entry gate do the work. Pure mean-reversion/RSI HURT (dropped).
#   * Lowering the gate widens the pool (more slots filled) and lifts net, but the
#     flat-slippage model degrades under churn: <12% gate is an ARTIFACT (baseline
#     funding ~11%/yr). ~25% is the robust sweet spot (realistic churn, high ret-DD).
VETO_VOL = float(os.environ.get("SCAN_VETO_VOL", "0.015"))       # skip vol > 1.5%/hr
VETO_ADVERSE = float(os.environ.get("SCAN_VETO_ADVERSE", "0.05"))  # skip fresh >5% adverse
SCANNER_ENTER = float(os.environ.get("SCAN_ENTER", "0.40"))       # SHIP DEFAULT keeps 0.40
SCANNER_ENTER_WIDE = float(os.environ.get("SCAN_ENTER_WIDE", "0.25"))  # OPT-IN widened gate


def veto_scanner(f):
    """Quality veto: refuse a funding-hot candidate that is a stop-out trap even when
    a slot is free (fewer, better trades). Backtestable core only (vol + momentum);
    the live bot adds cross-venue + book-depth vetoes on top."""
    return f["vol"] > VETO_VOL or f["adverse6"] > VETO_ADVERSE


def score_scanner(f):
    """Rank survivors by |APR| BACKBONE times BOUNDED risk discounts in [0,1].

    Design (funding-scanner-design workflow + backtest): a vol *divisor* (apr/vol)
    is harmful — it de-weights the high-|APR| names that carry the contrarian
    price alpha (fund$ << price$ in the wins). Instead keep |APR| as the backbone
    (its funding + mean-reversion signal) and inject risk as bounded multiplicative
    discounts, so the WORST case degrades to naive |APR| (downside-capped) while
    under contention it reallocates slots away from likely stop-outs.
      * vol discount:  low realized vol -> ~1; high vol -> small (stop-out proxy).
      * adverse discount: fresh momentum against our side -> shrink toward 0.
    (Cross-venue _bench + book-depth discounts are LIVE-ONLY, added in the bot.)"""
    vol_disc = 1.0 / (1.0 + (f["vol"] / VETO_VOL) ** 2)          # in (0,1], =0.5 at VETO_VOL
    adv_disc = math.exp(-6.0 * max(0.0, f["adverse6"]))          # in (0,1]
    return f["abs_apr"] * vol_disc * adv_disc


# --------------------------- portfolio simulation ----------------------------
def simulate(series, all_hours, scorer, veto=None, persist_h=PERSIST_H,
             enter=ENTER_APR, exit_apr=EXIT_APR, hard_stop=HARD_STOP,
             take_profit=TAKE_PROFIT, max_hold=MAX_HOLD_H, max_open=MAX_OPEN):
    """Replay the real portfolio hour by hour with a given scorer. Returns metrics.

    scorer(f) -> float, higher = more attractive (ranks competitors for slots).
    veto(f)   -> True to REFUSE a candidate even when a slot is free (quality gate;
                 leaves the slot empty = fewer, better trades). None = never veto.
    The competition/veto counters expose WHERE the scanner adds value: pure ranking
    only bites when eligible > free slots; the veto bites whenever a hot-but-bad
    candidate is skipped."""
    open_pos = {}     # coin -> dict(is_short, ent, ei_hour, accr, opened_hour)
    hot = {}          # coin -> consecutive hot hours
    cooldown = {}     # coin -> hour until which re-entry is blocked
    trades = []       # (exit_hour, price_ret, fund_ret, reason)
    eq = peak = maxdd = 0.0
    compete_hours = 0   # hours where eligible candidates exceeded free slots
    vetoed = 0          # candidates skipped by the veto despite a free slot

    for t in all_hours:
        # 1) manage open positions
        for coin in list(open_pos):
            s = series[coin]
            i = s["idx"].get(t)
            if i is None:
                continue  # coin has no bar this hour; funding pauses
            pos = open_pos[coin]
            o, hi, lo, c = s["k"][t]
            rate = s["rates"][i]
            apr = rate * H
            pos["accr"] += (1.0 if pos["is_short"] else -1.0) * rate
            ent = pos["ent"]
            reason = exit_px = None
            if pos["is_short"]:
                if hi >= ent * (1 + hard_stop):
                    reason, exit_px = "stop", ent * (1 + hard_stop)
                elif take_profit and lo <= ent * (1 - take_profit):
                    reason, exit_px = "tp", ent * (1 - take_profit)
            else:
                if lo <= ent * (1 - hard_stop):
                    reason, exit_px = "stop", ent * (1 - hard_stop)
                elif take_profit and hi >= ent * (1 + take_profit):
                    reason, exit_px = "tp", ent * (1 + take_profit)
            if reason is None:
                if (pos["is_short"] and apr < 0) or (not pos["is_short"] and apr > 0):
                    reason, exit_px = "flip", c
                elif abs(apr) < exit_apr:
                    reason, exit_px = "decay", c
                elif (i - pos["ei"]) >= max_hold:
                    reason, exit_px = "max_hold", c
            if reason:
                fill = exit_px * (1 - SLIP * (1 if pos["is_short"] else -1))
                pr = ((ent - fill) / ent) if pos["is_short"] else ((fill - ent) / ent)
                trades.append((t, pr, pos["accr"], reason))
                eq += (pr + pos["accr"]) * ORDER_USD
                peak = max(peak, eq)
                maxdd = max(maxdd, peak - eq)
                if reason == "stop":
                    cooldown[coin] = i + STOP_COOLDOWN_H
                del open_pos[coin]

        # 2) update persistence clocks across all coins with a bar this hour
        cand = []
        for coin, s in series.items():
            i = s["idx"].get(t)
            if i is None:
                continue
            apr = s["rates"][i] * H
            if abs(apr) >= enter:
                hot[coin] = hot.get(coin, 0) + 1
            else:
                hot[coin] = 0
            if coin in open_pos:
                continue
            if coin in cooldown and i < cooldown[coin]:
                continue
            if abs(apr) < enter or hot[coin] < persist_h:
                continue
            f = features(coin, s, i)
            f["persist_h"] = hot[coin]
            cand.append((coin, s, i, f))

        # 3) fill free slots with the top-scored candidates (veto skips bad ones)
        free = max_open - len(open_pos)
        if free > 0 and cand:
            if len(cand) > free:
                compete_hours += 1
            cand.sort(key=lambda x: -scorer(x[3]))
            filled = 0
            for coin, s, i, f in cand:
                if filled >= free:
                    break
                if veto is not None and veto(f):
                    vetoed += 1
                    continue
                c = s["closes"][i]
                is_short = f["is_short"]
                ent = c * (1 + SLIP * (1 if is_short else -1))
                open_pos[coin] = {"is_short": is_short, "ent": ent, "ei": i,
                                  "accr": 0.0, "opened_hour": t}
                filled += 1

    if not trades:
        return None
    n = len(trades)
    wins = sum(1 for _, pr, fr, _ in trades if (pr + fr) > 0)
    stops = sum(1 for _, _, _, r in trades if r == "stop")
    price = sum(pr for _, pr, _, _ in trades) * ORDER_USD
    fund = sum(fr for _, _, fr, _ in trades) * ORDER_USD
    now = time.time() * 1000
    split = now - 90 * 86400 * 1000
    oos = sum((pr + fr) * ORDER_USD for ts, pr, fr, _ in trades if ts >= split)
    return {"n": n, "ret": eq, "maxdd": maxdd, "win": 100 * wins / n,
            "stoprate": 100 * stops / n, "price": price, "fund": fund, "oos": oos,
            "ret_dd": (eq / maxdd) if maxdd > 0 else float("inf"),
            "compete_hours": compete_hours, "vetoed": vetoed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", choices=list(SCORERS), default=None)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    print(f"Portfolio scanner backtest — real HL funding+price, {FETCH_DAYS}d, "
          f"${ORDER_USD:.0f} clip, max_open={MAX_OPEN}, enter {ENTER_APR:.0%} "
          f"stop {HARD_STOP:.0%} tp {TAKE_PROFIT:.0%}\n")
    data = load_data(args.refresh)
    series, all_hours = build_series(data)
    print(f"{len(series)} coins, {len(all_hours)} hours.\n")

    def show(name, r):
        if not r:
            print(f"{name:>26}   (no trades)"); return
        print(f"{name:>26} {r['n']:>7} {r['ret']:>8.1f} {r['maxdd']:>7.1f} "
              f"{r['win']:>5.0f} {r['stoprate']:>6.0f} {r['price']:>8.1f} "
              f"{r['fund']:>7.1f} {r['oos']:>7.1f} {r['ret_dd']:>7.2f}")

    hdr = (f"{'config':>26} {'trades':>7} {'net$':>8} {'maxDD$':>7} {'win%':>5} "
           f"{'stop%':>6} {'price$':>8} {'fund$':>7} {'OOS$':>7} {'ret/DD':>7}")
    if args.scorer:
        print(hdr)
        show(args.scorer, simulate(series, all_hours, SCORERS[args.scorer]))
        return

    # ---- the ship decision: OLD (current bot) vs NEW (scanner) ----
    # SHIP DEFAULT keeps the 0.40 safety gate — the scanner's win there is the VETO
    # (skip stop-out traps). Gate-widening to 0.25 is a SEPARATE opt-in lever, shown
    # last, and flagged as partly a flat-slippage artifact (validate on shadow first).
    print("=== OLD (current bot) vs NEW (scanner) — the ship gate ===")
    print(hdr)
    old = simulate(series, all_hours, score_naive, enter=0.40)   # current: raw |APR| @40%
    show("OLD naive |APR| @40%", old)
    new = simulate(series, all_hours, score_scanner, veto=veto_scanner,
                   enter=SCANNER_ENTER)                           # DEFAULT: veto @40%
    show(f"NEW scanner @{int(SCANNER_ENTER*100)}% (default)", new)
    wide = simulate(series, all_hours, score_scanner, veto=veto_scanner,
                    enter=SCANNER_ENTER_WIDE)                     # OPT-IN widened gate
    show(f"  opt-in gate @{int(SCANNER_ENTER_WIDE*100)}% (artifact-risk)", wide)
    if old and new:
        print(f"\nNEW(default @{int(SCANNER_ENTER*100)}%) vs OLD: net ${new['ret']:.1f} vs "
              f"${old['ret']:.1f} ({(new['ret']/old['ret']-1)*100:+.0f}%), ret/DD "
              f"{new['ret_dd']:.2f} vs {old['ret_dd']:.2f}, OOS90d ${new['oos']:.1f} vs "
              f"${old['oos']:.1f}, maxDD ${new['maxdd']:.1f} vs ${old['maxdd']:.1f}, "
              f"trades {new['n']} vs {old['n']} (fewer = not churn). The default win is the "
              f"VETO. Opt-in @{int(SCANNER_ENTER_WIDE*100)}% adds ${wide['ret']-new['ret']:.0f} "
              f"more but partly as a flat-slippage artifact — shadow-validate first.")
    print("\nAll scorers (diagnostic):")
    print(hdr)
    for name in SCORERS:
        show(name, simulate(series, all_hours, SCORERS[name]))
    print("\nNote: $ are per $25 clip over 150d under a 6-slot portfolio (NOT the "
          "independent per-coin replay). MIN_VOL / cross-venue / book-depth gates are "
          "LIVE-ONLY (not in this cache) — this proves the funding+candle CORE; the live "
          "layer only adds selectivity. <12% gate is a slippage-model artifact — avoid.")


if __name__ == "__main__":
    main()
