#!/usr/bin/env python3
"""
scripts/backtest_leverage_operator.py — doctrine gate for a HIGH-LEVERAGE
intraday operator on Lighter ("redesign the day trader", 12 Jul 2026).

WHY THIS SHAPE: the spot DayTrader's legs all lost ~0.24-0.35%/trade against
a ~0.52% round-trip Kraken/Binance fee — fee bleed, not signal collapse. A
zero-fee venue changes that arithmetic, and the fleet has NO intraday
long/short bot and NO leveraged bot. Candidate family: closed-hourly-bar
LONG/SHORT breakout (close beyond the prior N-bar extreme) with an ATR trail,
time stop, and honest leverage mechanics. NOT a re-test: Bounce Catcher
(range mean-reversion, REJECTED) is the opposite trade; the shootout's
donchian variants were DAILY LONG-ONLY on the Tide-Rider frame.

METHOD (mirrors the to-be-built bot):
  * universe = tight-slippage Lighter majors (measured live slip <~1bp);
  * signals on CLOSED hourly bars: close > prior N-bar high -> LONG,
    close < prior N-bar low -> SHORT; one position per coin, flips allowed;
  * exits: k*ATR14 initial stop + trailing on closed bars, checked INTRABAR
    against the bar extreme (pessimistic fill at stop level +/- slip);
    T-hour time stop; no take-profit (winners ride the trail);
  * leverage: margin clip fixed, notional = clip * lev — price P&L, FUNDING
    (real hourly history, signed) and SLIP all on the notional; forced LIQ
    close (25bps penalty) if adverse move >= 0.9/lev — must be 0 at the pick;
  * friction: 5bps/side base (zero fee venue), stressed 2-3x on the pick.

GATES: >=150d real data; BOTH halves positive; mirror (FADE the same breaks)
price-negative; a parameter PLATEAU across N x k, never one sweet spot;
zero liquidations + survives slip stress at the chosen leverage.

VERDICT (12 Jul 2026, 150d ending 10 Jul): REJECTED — do NOT re-test.
  Plain long/short: 0/8 pass (h2 or both halves negative everywhere; the
  best full-window cell 12/3.0 +4.5% fails h2). Pre-declared gates tested:
  trend-gated 0/8, long-only 0/8 (best 24/2.0 +18.5% full but h1 +5.9/h2
  +12.5 ... FAILED mirror), squeeze-gated 1/8 (24/3.0: +26.8%, h1 +5.7,
  h2 +21.1, mirror -31) — but that lone survivor sits next to a CLIFF
  (48h: -22%), both immediate neighbours fail, and it DIES under the
  doctrine's 2x-slip stress (h1 negative at 10bps at every leverage).
  Same isolated-sweet-spot signature that rejected reversal and low-vol.
  DIAGNOSTIC kept for the record: fading short-lookback breaks is
  catastrophic (mirror -43..-48% at N=12) — short-term breaks carry real
  directional information, but whipsaw + slip bleed it away faster than
  any tested exit can keep it.
  The leverage table was therefore never earned. See also
  backtest_overdrive.py — leveraging the VALIDATED funding-spread book
  fails too (squeeze-tail liqs without stops; stops kill the carry).
  No high-leverage operator ships from this search.

Usage:  python3 scripts/backtest_leverage_operator.py
"""
import json
import os
import sys

CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")
UNIVERSE = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "HYPE", "LINK"]
CLIP = 20.0                 # margin per position ($)
MAX_OPEN = 4
SLIP = 0.0005               # per side, on notional
TIME_STOP_H = 48
LIQ_FRAC = 0.90             # forced close at 0.9/lev adverse (isolated margin)
LIQ_PENALTY = 0.0025
H_YR = 24 * 365

NS = [12, 24, 48, 72]
KS = [2.0, 3.0]


def load():
    if not os.path.exists(CACHE):
        sys.exit("cache missing — run scripts/backtest_directional_funding.py first")
    raw = json.load(open(CACHE))
    out = {}
    for c in UNIVERSE:
        if c not in raw:
            continue
        ks = sorted((int(t), v) for t, v in raw[c]["k"].items())
        out[c] = {
            "ts": [t for t, _ in ks],
            "o": [v[0] for _, v in ks], "h": [v[1] for _, v in ks],
            "l": [v[2] for _, v in ks], "c": [v[3] for _, v in ks],
            "f": {int(int(t) // 3600000 * 3600000): r
                  for t, r in raw[c]["f"].items()},
        }
    return out


def atr14(d):
    n = len(d["c"])
    tr = [d["h"][0] - d["l"][0]]
    for i in range(1, n):
        tr.append(max(d["h"][i] - d["l"][i],
                      abs(d["h"][i] - d["c"][i - 1]),
                      abs(d["l"][i] - d["c"][i - 1])))
    out = [tr[0]]
    for i in range(1, n):
        out.append((out[-1] * 13 + tr[i]) / 14.0)
    return out


def ema_series(closes, span):
    kf = 2.0 / (span + 1.0)
    out = [closes[0]]
    for x in closes[1:]:
        out.append(out[-1] + kf * (x - out[-1]))
    return out


def simulate(data, atrs, common, idx, n_look, k, lev, slip=SLIP, invert=False,
             gate="none", emas=None):
    """Portfolio sim on the aligned hourly timeline. Returns stats dict.
    Accounting: margin clip CLIP per position; P&L/funding/slip on notional
    CLIP*lev; capital basis = MAX_OPEN*CLIP (deployed margin)."""
    notional = CLIP * lev
    book = {}          # coin -> {side, entry, stop, opened_i}
    cash = price_pnl = fund_pnl = 0.0
    trips = wins = liqs = 0
    eq_hist = []
    cap = MAX_OPEN * CLIP

    def close(coin, px, i, why):
        nonlocal cash, price_pnl, trips, wins, liqs
        p = book.pop(coin)
        pnl = p["side"] * (px / p["entry"] - 1.0) * notional - slip * notional
        cash += pnl
        price_pnl += pnl
        trips += 1
        wins += 1 if pnl > 0 else 0
        if why == "liq":
            liqs += 1

    for j in range(n_look + 15, len(common)):
        t = common[j]
        # manage open positions on this bar
        for coin in list(book):
            d = data[coin]
            i = idx[coin][t]
            p = book[coin]
            r = d["f"].get(t)
            if r is not None:
                cf = -p["side"] * r * notional
                cash += cf
                fund_pnl += cf
            lo, hi, cl = d["l"][i], d["h"][i], d["c"][i]
            # liquidation first (worst case ordering)
            liq_px = p["entry"] * (1 - p["side"] * LIQ_FRAC / lev)
            if (p["side"] > 0 and lo <= liq_px) or (p["side"] < 0 and hi >= liq_px):
                close(coin, liq_px * (1 - p["side"] * LIQ_PENALTY), j, "liq")
                continue
            # hard/trailing stop, intrabar
            if (p["side"] > 0 and lo <= p["stop"]) or \
                    (p["side"] < 0 and hi >= p["stop"]):
                close(coin, p["stop"], j, "stop")
                continue
            # time stop on close
            if j - p["opened_i"] >= TIME_STOP_H:
                close(coin, cl, j, "time")
                continue
            # trail on closed bar
            a = atrs[coin][i]
            if p["side"] > 0:
                p["stop"] = max(p["stop"], cl - k * a)
            else:
                p["stop"] = min(p["stop"], cl + k * a)

        # entries on the closed bar
        for coin in UNIVERSE:
            if coin not in data:
                continue
            d = data[coin]
            i = idx[coin][t]
            if i < n_look + 15:
                continue
            hh = max(d["h"][i - n_look:i])
            ll = min(d["l"][i - n_look:i])
            cl = d["c"][i]
            sig = 0
            if cl > hh:
                sig = +1
            elif cl < ll:
                sig = -1
            if invert:
                sig = -sig
            if sig == 0:
                continue
            # pre-declared robustification gates (12 Jul):
            if gate == "trend":
                e = emas[coin][i]
                if (sig > 0 and cl <= e) or (sig < 0 and cl >= e):
                    continue
            elif gate == "squeeze":
                # break must come out of COMPRESSION: the just-broken N-bar
                # range is in the tightest 30% of its own trailing-240h widths
                if i < n_look + 240:
                    continue
                w_now = (hh - ll) / cl
                ws = []
                for jj in range(i - 240, i, 8):     # 8h sampling, 30 obs
                    h2 = max(d["h"][jj - n_look:jj])
                    l2 = min(d["l"][jj - n_look:jj])
                    ws.append((h2 - l2) / d["c"][jj])
                if sorted(ws)[int(len(ws) * 0.3)] < w_now:
                    continue
            elif gate == "longonly":
                if sig < 0:
                    continue
            held = book.get(coin)
            if held and held["side"] == sig:
                continue
            if held and held["side"] != sig:
                close(coin, cl, j, "flip")
            if len(book) >= MAX_OPEN:
                continue
            a = atrs[coin][i]
            entry = cl * (1 + sig * slip)      # cross the spread
            book[coin] = {"side": sig, "entry": entry,
                          "stop": entry - sig * k * a, "opened_i": j}
            cash -= slip * notional            # entry slip (exit slip on close)
        # mark equity
        u = 0.0
        for coin, p in book.items():
            i = idx[coin][t]
            u += p["side"] * (data[coin]["c"][i] / p["entry"] - 1.0) * notional
        eq_hist.append(cash + u)

    for coin in list(book):
        i = idx[coin][common[-1]]
        close(coin, data[coin]["c"][i], len(common) - 1, "eod")
    eq_hist.append(cash)

    peak = dd = 0.0
    for e in eq_hist:
        peak = max(peak, e)
        dd = max(dd, peak - e)
    return dict(ret=100 * cash / cap, price=100 * price_pnl / cap,
                fund=100 * fund_pnl / cap, dd=100 * dd / cap,
                trips=trips, winp=(100 * wins / trips if trips else 0),
                liqs=liqs)


def main():
    data = load()
    atrs = {c: atr14(d) for c, d in data.items()}
    sets = [set(d["ts"]) for d in data.values()]
    common = sorted(set.intersection(*sets))
    idx = {c: {t: i for i, t in enumerate(d["ts"]) if t in set(common)}
           for c, d in data.items()}
    # re-index onto the common timeline positions
    for c in data:
        m = dict(zip(data[c]["ts"], range(len(data[c]["ts"]))))
        idx[c] = {t: m[t] for t in common}
    days = (common[-1] - common[0]) / 3600000 / 24 if common[0] > 1e12 else \
        (common[-1] - common[0]) / 3600 / 24
    print(f"universe {len(data)} coins, {len(common)} hourly bars (~{days:.0f}d), "
          f"clip ${CLIP:.0f} x {MAX_OPEN} slots, slip {SLIP*1e4:.0f}bps/side\n")

    half = len(common) // 2
    emas = {c: ema_series(d["c"], 200) for c, d in data.items()}
    hdr = (f"{'gate':>9} {'N':>3} {'k':>4} | {'full%':>7} {'h1%':>7} {'h2%':>7} "
           f"{'dd%':>6} {'trips':>5} {'win%':>5} {'fund_pp':>7} | {'mirror%':>8} "
           f"| verdict")
    print("=== signal gate at lev 1 (both-halves + mirror + plateau) ===")
    print(hdr)
    print("-" * len(hdr))
    passing = []
    for gate in ["none", "trend", "squeeze", "longonly"]:
        for n in NS:
            for k in KS:
                kw = dict(gate=gate, emas=emas)
                r_full = simulate(data, atrs, common, idx, n, k, 1, **kw)
                r_h1 = simulate(data, atrs, common[:half], idx, n, k, 1, **kw)
                r_h2 = simulate(data, atrs, common[half:], idx, n, k, 1, **kw)
                r_mir = simulate(data, atrs, common, idx, n, k, 1, invert=True,
                                 **kw)
                both = r_h1["ret"] > 0 and r_h2["ret"] > 0
                ok = both and r_full["ret"] > 0 and r_mir["price"] < 0
                if ok:
                    passing.append((gate, n, k, r_full, r_h1, r_h2))
                print(f"{gate:>9} {n:>3} {k:>4.1f} | {r_full['ret']:>7.1f} "
                      f"{r_h1['ret']:>7.1f} {r_h2['ret']:>7.1f} "
                      f"{r_full['dd']:>6.1f} {r_full['trips']:>5} "
                      f"{r_full['winp']:>5.0f} {r_full['fund']:>7.1f} | "
                      f"{r_mir['ret']:>8.1f} | {'PASS' if ok else 'FAIL'}")

    print(f"\n{len(passing)} / {4*len(NS)*len(KS)} signal configs pass")
    if not passing:
        print("VERDICT: REJECTED — no durable intraday breakout edge at lev 1 "
              "under ANY pre-declared gate; leverage would only multiply a "
              "non-edge.")
        return
    # plateau centre: most passing lookback-neighbours (same gate), then best
    # min-half return
    keyset = {(g, n, k) for g, n, k, *_ in passing}

    def nb(g, n, k):
        i = NS.index(n)
        s = 0
        for di in (-1, 1):
            if 0 <= i + di < len(NS) and (g, NS[i + di], k) in keyset:
                s += 1
        return s

    g, n, k, rf, r1, r2 = max(passing,
                              key=lambda x: (nb(x[0], x[1], x[2]),
                                             min(x[4]["ret"], x[5]["ret"])))
    print(f"\nCHOSEN signal: gate={g}, N={n}, k={k} -> full {rf['ret']:+.1f}% "
          f"h1 {r1['ret']:+.1f}% h2 {r2['ret']:+.1f}% dd {rf['dd']:.1f}%")

    emas = {c: ema_series(d["c"], 200) for c, d in data.items()}
    print("\n=== leverage table on the chosen signal (margin-basis returns) ===")
    print(f"{'lev':>4} {'slip':>5} | {'full%':>8} {'h1%':>7} {'h2%':>7} "
          f"{'dd%':>6} {'liqs':>4}")
    for lev in [1, 2, 3, 5]:
        for s_mult in ([1] if lev == 1 else [1, 2, 3]):
            kw = dict(gate=g, emas=emas, slip=SLIP * s_mult)
            rl = simulate(data, atrs, common, idx, n, k, lev, **kw)
            r1l = simulate(data, atrs, common[:half], idx, n, k, lev, **kw)
            r2l = simulate(data, atrs, common[half:], idx, n, k, lev, **kw)
            print(f"{lev:>4} {SLIP*s_mult*1e4:>4.0f}b | {rl['ret']:>8.1f} "
                  f"{r1l['ret']:>7.1f} {r2l['ret']:>7.1f} {rl['dd']:>6.1f} "
                  f"{rl['liqs']:>4}")


if __name__ == "__main__":
    main()
