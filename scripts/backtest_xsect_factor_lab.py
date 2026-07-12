#!/usr/bin/env python3
"""
scripts/backtest_xsect_factor_lab.py — the two remaining orthogonal CROSS-SECTIONAL
factors, same harness + doctrine gates as backtest_xsect_momentum.py (which
REJECTED cross-sectional momentum — see its header; don't re-test).

FACTOR A — short-term cross-sectional REVERSAL ("long the dip-ranked, short the
rip-ranked", market-neutral): the momentum sweep's mirror column was strongly
POSITIVE at short lookbacks (5d skip-1 mirror +22..+28% full-window), i.e. the
losers-minus-winners book made money. That is a known crypto factor (short-term
reversal). NOTE the fleet's REJECTED dip-buyers (Trail Blazer, Bounce Catcher)
were TIME-SERIES long-only; this is relative, hedged, and short the winners —
different mechanics, so it earns one doctrine-gated test, not a re-test.

FACTOR B — cross-sectional FUNDING carry ("Yield Spread", market-neutral):
rank coins by trailing mean funding; SHORT the hottest-positive-funding coins
(shorts RECEIVE) and LONG the most-negative-funding coins (longs RECEIVE) —
funding income on BOTH legs, price exposure ~neutral. Distinct from the live
Funding Farmer (directional, single-leg, slope-gated) and from the REJECTED
both-perp same-asset hedge (that was long+short the SAME coin = zero funding
edge after friction; this is ACROSS coins, keeping the funding spread).

GATES (identical to the momentum script): >=150d real data; positive in BOTH
halves; mirror (inverted ranking) price-P&L negative; plateau across
neighbouring params, never a single sweet spot; 2x-slip stress on the pick.

VERDICT (12 Jul 2026, 150d ending 10 Jul):
  FACTOR A (reversal) — REJECTED. 1/16 configs passes (5d/K3/48h) and it is
    isolated: 5d/K3/24h loses -16.8%, 5d/K5/48h +2.9% fails h1, and 2-3d
    lookbacks are catastrophically negative (-16..-52%, the book eats spread).
    Same one-regime signature as the dip-buyer family. Do not re-test.
  FACTOR B (funding-rank carry) — **PASS, with a real plateau**: 8/12 configs
    green in BOTH halves; the ENTIRE 72h-lookback row passes and results
    improve monotonically with longer funding lookback (24h: 1/4, 48h: 3/4,
    72h: 4/4). Mirrors negative everywhere on the plateau. Funding income is
    +6..9pp and consistent across halves. CHOSEN (plateau centre, fully
    surrounded by passing neighbours, lowest maxDD): 72h / K=5 / reb 24h ->
    full +13.7%, h1 +5.7%, h2 +8.9%, maxDD 11.9%, mirror(price) -14.4%.
    Slippage stress: 10bps/side +10.3% (+4.1/+7.1), 15bps/side +6.9%
    (+2.5/+5.3) — still green in both halves at 3x modelled friction.
    Shipped shadow-only as ⚖️ Counterweight (lighter_funding_spread_bot.py,
    row perps-funding-spread-lshadow).
  FACTOR C (low-vol) — REJECTED. 1/12 passes (14d/K5/24h, h2 barely +0.7%),
    neighbours fail; H2 negative nearly everywhere (high-vol coins rip in
    trends and the short-vol leg pays). Do not re-test.
Cross-sectional scorecard on this venue/universe: momentum REJECTED (see
backtest_xsect_momentum.py), reversal REJECTED, low-vol REJECTED,
funding-rank PASSED. The factor that survives is the one aligned with the
venue's structural edge: zero-fee funding capture.

Usage:  python3 scripts/backtest_xsect_factor_lab.py
"""
import json
import os
import sys

CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")
ORDER_USD = 20.0
SLIP = 0.0005
HD = 24


def load():
    if not os.path.exists(CACHE):
        sys.exit("cache missing — run scripts/backtest_directional_funding.py first")
    raw = json.load(open(CACHE))
    out = {}
    for coin, d in raw.items():
        ks = sorted((int(t), v) for t, v in d["k"].items())
        fund = {int(int(t) // 3600000 * 3600000): r for t, r in d["f"].items()}
        out[coin] = {"ts": [t for t, _ in ks], "close": [v[3] for _, v in ks],
                     "fund": fund}
    return out


def align(data):
    common = sorted(set.intersection(*[set(d["ts"]) for d in data.values()]))
    coins = sorted(data.keys())
    px = {}
    for c in coins:
        m = dict(zip(data[c]["ts"], data[c]["close"]))
        px[c] = {t: m[t] for t in common}
    return coins, common, px


def simulate(coins, ts, px, fund, rank_fn, warm_h, k, reb_h, invert=False,
             slip=SLIP):
    book, cash, price_pnl, fund_pnl = {}, 0.0, 0.0, 0.0
    trips = wins = 0
    eq = []
    gross = 2.0 * k * ORDER_USD
    for i in range(warm_h, len(ts)):
        t = ts[i]
        for c, p in book.items():
            r = fund[c].get(t)
            if r is not None:
                cf = -p["side"] * r * ORDER_USD
                cash += cf
                fund_pnl += cf
        if (i - warm_h) % reb_h == 0:
            scores = rank_fn(i)
            if scores:
                ranked = sorted(scores, key=scores.get, reverse=not invert)
                want = {c: +1 for c in ranked[:k]}
                want.update({c: -1 for c in ranked[-k:]})
                for c in list(book):
                    if want.get(c) != book[c]["side"]:
                        p = book.pop(c)
                        pnl = p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD \
                            - slip * ORDER_USD
                        cash += pnl
                        price_pnl += pnl
                        trips += 1
                        wins += 1 if pnl > 0 else 0
                for c, side in want.items():
                    if c not in book:
                        cash -= slip * ORDER_USD
                        price_pnl -= slip * ORDER_USD
                        book[c] = {"side": side, "entry": px[c][t]}
        u = sum(p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD
                for c, p in book.items())
        eq.append(cash + u)
    t = ts[-1]
    for c, p in book.items():
        pnl = p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD - slip * ORDER_USD
        cash += pnl
        price_pnl += pnl
        trips += 1
        wins += 1 if pnl > 0 else 0
    eq.append(cash)
    peak = dd = 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, peak - e)
    return cash, price_pnl, fund_pnl, 100 * dd / gross, trips, wins, gross


def gate(coins, ts, px, fund, mk_rank, warm_h, k, reb_h, slip=SLIP):
    half = len(ts) // 2
    out = {}
    for name, seg in (("full", ts), ("h1", ts[:half]), ("h2", ts[half:])):
        rank_fn = mk_rank(seg)
        c, pp, fp, dd, tr, w, g = simulate(coins, seg, px, fund, rank_fn, warm_h,
                                           k, reb_h, slip=slip)
        out[name] = dict(ret=100 * c / g, fund=100 * fp / g, dd=dd, trips=tr)
    rank_fn = mk_rank(ts)
    c, pp, fp, dd, tr, w, g = simulate(coins, ts, px, fund, rank_fn, warm_h, k,
                                       reb_h, invert=True, slip=slip)
    out["mirror"] = dict(ret=100 * c / g, price=100 * pp / g)
    return out


def main():
    data = load()
    fund = {c: d["fund"] for c, d in data.items()}
    coins, ts, px = align(data)
    print(f"universe {len(coins)} coins, {len(ts)} hourly bars, clip ${ORDER_USD:.0f}, "
          f"slip {SLIP*1e4:.0f}bps/side\n")

    hdr = (f"{'factor':>10} {'p1':>4} {'k':>2} {'reb':>4} | {'full%':>7} {'h1%':>7} "
           f"{'h2%':>7} {'dd%':>5} {'trips':>5} | {'mirror%':>8} {'fund_pp':>7} | verdict")
    print(hdr)
    print("-" * len(hdr))

    results = []

    # FACTOR A — reversal: rank by trailing return ASC == invert of momentum.
    # rank score = -trailing return  (top of book = biggest loser)
    for lb_d in [2, 3, 5, 7]:
        for k in [3, 5]:
            for reb in [24, 48]:
                warm = lb_d * HD + HD

                def mk_rank(seg, lb_h=lb_d * HD):
                    def rank(i):
                        if i - lb_h < 0:
                            return {}
                        return {c: -(px[c][seg[i]] / px[c][seg[i - lb_h]] - 1.0)
                                for c in coins if px[c][seg[i - lb_h]] > 0}
                    return rank

                r = gate(coins, ts, px, fund, mk_rank, warm, k, reb)
                both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                ok = both and r["full"]["ret"] > 0 and r["mirror"]["price"] < 0
                results.append(("reversal", lb_d, k, reb, r, ok))
                print(f"{'reversal':>10} {lb_d:>4} {k:>2} {reb:>4} | "
                      f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                      f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                      f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                      f"{r['full']['fund']:>7.1f} | {'PASS' if ok else 'FAIL'}")

    # FACTOR B — funding carry: rank by trailing mean funding ASC
    # (top of book = most NEGATIVE funding -> LONG receives; bottom = hottest
    #  positive funding -> SHORT receives)
    for fl_h in [24, 48, 72]:
        for k in [3, 5]:
            for reb in [24, 48]:
                warm = fl_h + HD

                def mk_rank(seg, fl=fl_h):
                    def rank(i):
                        sc = {}
                        for c in coins:
                            rs = [fund[c].get(seg[j]) for j in range(i - fl, i)]
                            rs = [x for x in rs if x is not None]
                            if len(rs) >= fl // 2:
                                sc[c] = -sum(rs) / len(rs)
                        return sc
                    return rank

                r = gate(coins, ts, px, fund, mk_rank, warm, k, reb)
                both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                ok = both and r["full"]["ret"] > 0 and r["mirror"]["price"] < 0
                results.append(("fundcarry", fl_h, k, reb, r, ok))
                print(f"{'fundcarry':>10} {fl_h:>4} {k:>2} {reb:>4} | "
                      f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                      f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                      f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                      f"{r['full']['fund']:>7.1f} | {'PASS' if ok else 'FAIL'}")

    # FACTOR C — low-vol (betting-against-vol): rank by trailing realised vol
    # of hourly closes, ASC (top of book = QUIETEST coin -> LONG low-vol,
    # SHORT high-vol). Orthogonal driver to trend/dip/funding.
    for vl_d in [3, 7, 14]:
        for k in [3, 5]:
            for reb in [24, 48]:
                warm = vl_d * HD + HD

                def mk_rank(seg, vl=vl_d * HD):
                    def rank(i):
                        if i - vl < 0:
                            return {}
                        sc = {}
                        for c in coins:
                            rets = []
                            for j in range(i - vl + 1, i + 1):
                                a, b = px[c][seg[j - 1]], px[c][seg[j]]
                                if a > 0:
                                    rets.append(b / a - 1.0)
                            if len(rets) >= vl // 2:
                                m = sum(rets) / len(rets)
                                sc[c] = -(sum((x - m) ** 2 for x in rets)
                                          / len(rets)) ** 0.5
                        return sc
                    return rank

                r = gate(coins, ts, px, fund, mk_rank, warm, k, reb)
                both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                ok = both and r["full"]["ret"] > 0 and r["mirror"]["price"] < 0
                results.append(("lowvol", vl_d, k, reb, r, ok))
                print(f"{'lowvol':>10} {vl_d:>4} {k:>2} {reb:>4} | "
                      f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                      f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                      f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                      f"{r['full']['fund']:>7.1f} | {'PASS' if ok else 'FAIL'}")

    passing = [x for x in results if x[5]]
    print(f"\n{len(passing)} / {len(results)} configs pass all gates")
    for fac, p1, k, reb, r, _ in passing:
        print(f"  PASS: {fac} p1={p1} k={k} reb={reb} -> "
              f"full {r['full']['ret']:+.1f}% h1 {r['h1']['ret']:+.1f}% "
              f"h2 {r['h2']['ret']:+.1f}%")


if __name__ == "__main__":
    main()
