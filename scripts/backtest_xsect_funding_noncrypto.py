#!/usr/bin/env python3
"""
scripts/backtest_xsect_funding_noncrypto.py — 🏹 TAMERLANE: Counterweight's
VALIDATED funding-rank factor, applied to Lighter's NON-CRYPTO books.

WHY THIS EXISTS (2026-07-22, operator ask: two new strategies worth their names)
  The operator asked to resurrect `perps-donchian-breakout` + `perps-rsi-meanrev`
  onto Lighter. Investigation killed that: both are the SAME 20-candle-range
  long-only dip buyer (the Donchian/RSI names are logging-only), the first IS
  🧭 Trail Blazer, and Trail Blazer already has a verdict — +6% over 30d but
  −11%..−31% over 60–180d, every lever tested and failed. Re-running it on a
  falling Lighter tape is a known-negative bet.

  This is the replacement. It is NOT a new strategy — it is the ONE factor that
  has actually PASSED validation on this venue (cross-sectional funding rank,
  backtest_xsect_funding_lighter.py: full +13.6%, h1 +5.6 / h2 +6.6, maxDD
  10.1%, mirror −16.4%, shipped as ⚖️ Counterweight) pointed at a universe it
  has never been tested on.

WHY THE NON-CRYPTO UNIVERSE (measured 2026-07-22, 60d settled funding, 31 books)
  Cross-sectional funding dispersion — the quantity this factor ranks on:
      NON-CRYPTO (26 books)   median top−bottom spread  117.8pp   p90 557pp
      crypto control (5)      median                     13.1pp   p90  32pp
  ≈9x the dispersion Counterweight harvests, and the rank is NEVER degenerate
  (0.0% of hours have every book on a pinned constant, vs 13.3% on crypto).
  Longs pay on 20 of 22 equity/commodity books (SOXL +76.5% apr, MU +36.0%,
  XCU +30.4%, NVDA +12.4%); shorts pay only on the oils (WTI −18.2%).

WHY MARKET-NEUTRAL IS THE POINT, NOT AN ACCIDENT
  CLAUDE.md's item-18 / D5 caveat: Lighter's whole 438d tape is ONE falling
  regime, so "positive in both halves" is satisfied BY CONSTRUCTION for anything
  directional. That bar has toothlessly passed — and then failed live — for
  every directional book tried here. A dollar-neutral cross-section has no
  regime exposure to launder, so the both-halves gate recovers its meaning.
  It is also why this design needs NO per-asset regime gate, whose oracle step
  is tape-blocked anyway (SPY/QQQ sit at 181/203 daily bars, ~22d short).

WHAT IS HELD IDENTICAL (vary exactly ONE variable — the universe)
  simulate(), gate(), align() and the 12-cell grid are IMPORTED VERBATIM from
  backtest_xsect_funding_lighter.py. Same scoring (score = −mean trailing
  funding over fl_h; ranked[:k] LONG = most negative = receives; ranked[-k:]
  SHORT = hottest positive = receives), same $20/leg clip, same 5bps/side, same
  gates (full>0 AND h1>0 AND h2>0 AND mirror(price)<0), same slip stress.
  ONLY `COINS` changes. Do not "improve" the arithmetic in this file — if it
  differs from the control, the comparison is worthless
  (see [[ab-tests-must-vary-exactly-one-variable]]).

UNIVERSE — and the one principled exclusion
  Lighter's equity / index / commodity perps, screened for paired settled
  funding + candle history. **FX is EXCLUDED on measurement, not taste**:
  GBPUSD and AUDUSD print EXACTLY 0.00% funding for all 1439 hours of the 60d
  window (sd 0.00), EURUSD/USDJPY ~0. A book whose funding is identically zero
  can never rank; including them would pad the cross-section with dead weight.

COST — the load-bearing constant, stated in the open per doctrine
  Primary run holds SLIP at the control's 5bps/side so exactly one variable
  moves. That is an ASSUMPTION and it is almost certainly WRONG per-book here:
  Lighter friction is PER-BOOK, measured from the fleet's own fills at
  216.71bps on BOT vs 17.91bps on SOXL — and SOXL is in this universe and is
  currently coin-vetoed for it. So this file ALSO runs a per-book cost model
  built from each book's live half-spread, reported separately. Read both.
  A single flat friction number is the assumption that manufactured a FALSE
  "no edge" on the Funding Farmer and a FALSE pass elsewhere; it cuts both ways.

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-22, 150d ending 22-Jul, 23 non-crypto books, 3589h)     ║
║ **DOES NOT SHIP — and friction is NOT the reason.** 3/12 configs pass,   ║
║ no plateau; the control's shipped 72/5/24 FAILS on h2 (−3.3%).           ║
╚══════════════════════════════════════════════════════════════════════════╝
                         NON-CRYPTO (measured)   CRYPTO control (measured)
    configs passing            3/12                    6/12
    72/5/24 full              +16.4%                  +13.6%
    72/5/24 h1 / h2       +15.0 / **−3.3**         +5.6 / +6.6
    maxDD                       8.1%                   10.1%
    funding leg               +5.7pp                  +4.5pp
    mirror(price)             −19.8%                  −16.4%

  WHAT IS GENUINELY GOOD HERE — do not discard the whole idea:
  * MIRROR IS STRONGLY NEGATIVE IN ALL 12 CELLS (−7.1 to −36.6). The ranking
    carries real information; the inverted book loses badly. This is not noise.
  * The carry leg is real and BIGGER than crypto's: +4.2 to +8.4pp vs +4.5pp.
  * **Friction is not the blocker — a first for this fleet.** Measured live
    half-spread across the 23 books: median 2.90bps/side, only 4/23 wider than
    the modelled 5bps. At the measured 2.90bps the book IMPROVES (+18.2%).
    Nearly every other verdict here hinges on an unmeasured slip constant;
    this one does not.

  WHY IT FAILS — decay, and it is structural, not a bad patch:
  * Quarterly, q1 is the best quarter in EVERY config, and the two configs with
    the biggest full-window numbers decay hardest into q4:
        24/5/48  +9.3 +11.0  +3.8  **−7.0**
        48/5/24  +9.4  +4.3  +4.0  **−3.4**
        72/5/48  +9.4  +0.3  +4.7   +2.6   (the only never-negative cell)
    The best-looking configs being the worst-decaying is the overfit signature.
  * h1 +$31.42 -> h2 −$1.12, and the swing is 2 books REVERSING: SNDK +5.5->−9.2,
    INTC +4.9->−8.3. With 23 books and k=5 the book holds 10 of 23, so single-name
    idiosyncratic moves (earnings, news) swamp the funding signal. Crypto alts are
    homogeneous enough for the cross-section to average; single-name equity perps
    are not, at this universe size.
  * k=5 beats k=3 in every pairing (3/6 vs 0/6) — consistent with the above:
    the factor is starved of breadth, not of signal.

  THE REVISIT CONDITION — this is a NOT-YET, not a never. Do not re-test by
  twiddling lookback/k/rebalance (that is the knob-fitting the doctrine rejects,
  and the grid above is already exhausted). Re-test when, and only when, the
  UNIVERSE BREADTH grows: 41 non-crypto books were screened and only 23 had the
  140d+ tape this window needs (18 were dropped: SOXL 28d, NBIS 42d, NOW 47d,
  DELL/IBM 50d, RKLB 53d, BABA 60d, MRVL 69d, WHEAT 74d, ORCL 77d, MU 78d,
  TSM 76d, EWY 82d, BRENTOIL/NATGAS 119d, ASML/URA 140d-marginal). At ~35+ books
  with 140d the averaging argument changes materially. Earliest meaningful
  re-run: ~Oct 2026.
  DO NOT "fix" this by lowering --min-days: a 42d book truncates the whole
  common-hours window to 42d (that bug produced a 1/12 first run here).

  [2026-07-22, SAME DAY] **THE BREADTH DIAGNOSIS ABOVE WAS TESTED AND REFUTED.**
  backtest_xsect_funding_merged.py ran crypto-only / non-crypto / MERGED (48
  books) on one shared 3589h window. Breadth did NOT rescue it: crypto-only
  passes 11/12 cells, merged only 5/12 — adding these books DEGRADES a working
  cross-section. So the revisit condition above is materially weakened: the
  honest reading is now that the non-crypto funding rank does not carry
  transferable edge, not that it is merely short of books. Read that file first
  before spending anything on an Oct-2026 re-run.

Read-only: hits public Lighter endpoints, writes only its cache. No bot, no DB.
Usage:
    .venv/bin/python3 scripts/backtest_xsect_funding_noncrypto.py
    .venv/bin/python3 scripts/backtest_xsect_funding_noncrypto.py --days 150 --refresh
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from backtest_funding_lighter import _get, fetch_candles, fetch_fundings  # noqa: E402
# THE VALIDATED ARITHMETIC — imported, never re-implemented.
from backtest_xsect_funding_lighter import (  # noqa: E402
    align, gate, HD, ORDER_USD, SLIP,
)

CACHE = os.path.join(os.path.dirname(__file__), ".xsectfund_noncrypto_cache.json")

# Lighter's non-crypto perps: equity indices, single names, commodities.
# FX deliberately absent — measured identically-zero funding (see header).
COINS = ("SPY,QQQ,IWM,NVDA,TSLA,MSTR,AAPL,MSFT,META,GOOGL,AMZN,COIN,HOOD,SOXL,"
         "TSM,MU,AMD,INTC,ORCL,PLTR,BABA,ASML,DELL,NOW,IBM,RKLB,NBIS,SNDK,MRVL,"
         "CRCL,EWY,URA,XAU,XAG,WTI,XCU,BRENTOIL,NATGAS,WHEAT,XPT,XPD").split(",")

def half_spread_bps(mid):
    """Live half-spread for one book, from the real order book. This is the
    per-book cost model's input — orderBookDetails carries NO bid/ask, so it
    must come from /api/v1/orderBookOrders."""
    try:
        r = _get("/api/v1/orderBookOrders", market_id=mid, limit=1)
        asks, bids = r.get("asks") or [], r.get("bids") or []
        if not asks or not bids:
            return None
        a, b = float(asks[0]["price"]), float(bids[0]["price"])
        if a <= b <= 0:
            return None
        return (a - b) / ((a + b) / 2) * 1e4 / 2.0
    except Exception:  # noqa: BLE001
        return None


def load(days, refresh, min_paired_h):
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= days and d.get("min_h", 0) == min_paired_h:
            return ({s: {"fund": {int(k): v for k, v in m["fund"].items()},
                         "cand": {int(k): float(v) for k, v in m["cand"].items()}}
                     for s, m in d["mk"].items()},
                    d.get("spread", {}))
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    ids = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    vol = {o["symbol"]: float(o.get("daily_quote_token_volume") or 0.0)
           for o in obs if o.get("symbol")}
    spread = {}

    missing = [c for c in COINS if c not in ids]
    print(f"universe: {len(COINS)} non-crypto candidates; NOT Lighter markets: {missing}")
    mk = {}
    for sym in COINS:
        mid = ids.get(sym)
        if mid is None:
            continue
        try:
            fund = fetch_fundings(mid, days)
            cand = fetch_candles(mid, days)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: fetch failed ({e}) — skipped")
            continue
        common = set(fund) & set(cand)
        if len(common) < min_paired_h:
            print(f"  {sym:9s} only {len(common):5d}h paired — SKIPPED "
                  f"(<{min_paired_h//24}d; a young book would TRUNCATE the "
                  f"whole common-hours window)")
            continue
        mk[sym] = {"fund": {t: fund[t] for t in common},
                   "cand": {t: cand[t][3] for t in common}}
        spread[sym] = half_spread_bps(mid)
        hs = spread[sym]
        print(f"  {sym:9s} {len(common):5d}h paired "
              f"({(max(common)-min(common))/86400:.0f}d)  "
              f"vol=${vol.get(sym,0)/1e6:7.2f}M  half-spread="
              f"{('%6.2f' % hs) if hs is not None else '   n/a'}bps")
    json.dump({"days": days, "min_h": min_paired_h, "mk": mk, "spread": spread},
              open(CACHE, "w"))
    return mk, spread


def mk_rank_factory(coins, fund):
    def mk_rank(seg, fl):
        def rank(i):
            sc = {}
            for c in coins:
                rs = [fund[c].get(seg[j]) for j in range(i - fl, i)]
                rs = [x for x in rs if x is not None]
                if len(rs) >= fl // 2:
                    sc[c] = -sum(rs) / len(rs)
            return sc
        return rank
    return mk_rank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)   # the control's window
    ap.add_argument("--refresh", action="store_true")
    # A book with less history than this is DROPPED, not tolerated: align()
    # intersects common hours across the whole universe, so one 42d book
    # silently truncates a 150d study to 42d. Learned the hard way, 22-Jul.
    ap.add_argument("--min-days", type=int, default=140)
    # [2026-07-23] tradeable-liquidity filter: drop books whose live half-spread
    # exceeds this (bps/side). Friction is NOT homogeneous — URA 102bps / ASML
    # 27bps drag a flat-5bps read, and the illiquid tail is a plausible driver of
    # the worst quarter. Default None = the full universe (unchanged behaviour).
    ap.add_argument("--max-spread-bps", type=float, default=None,
                    help="drop books with live half-spread > this (bps/side)")
    a = ap.parse_args()

    mk, spread = load(a.days, a.refresh, a.min_days * 24)
    if a.max_spread_bps is not None:
        wide = {c: spread[c] for c in list(mk)
                if spread.get(c) is not None and spread[c] > a.max_spread_bps}
        for c in wide:
            del mk[c]
        print(f"LIQUIDITY FILTER: dropped {len(wide)} book(s) > "
              f"{a.max_spread_bps}bps/side: "
              + ", ".join(f"{c} {wide[c]:.1f}"
                          for c in sorted(wide, key=lambda x: -wide[x])))
    if len(mk) < 12:
        sys.exit(f"only {len(mk)} books with paired history — not a cross-section")
    coins, ts, px, fund = align(mk)
    span = (ts[-1] - ts[0]) / 86400
    print(f"\nuniverse {len(coins)} NON-CRYPTO Lighter books, {len(ts)} hourly "
          f"bars ({span:.0f}d), clip ${ORDER_USD:.0f}, slip {SLIP*1e4:.0f}bps/side")
    print("SIGNED settled Lighter funding (direction applied). Arithmetic is "
          "backtest_xsect_funding_lighter's, imported verbatim.\n")

    hdr = (f"{'factor':>10} {'lb':>4} {'k':>2} {'reb':>4} | {'full%':>7} "
           f"{'h1%':>7} {'h2%':>7} {'dd%':>5} {'trips':>5} | {'mirror%':>8} "
           f"{'fund_pp':>7} | verdict")
    print(hdr)
    print("-" * len(hdr))

    base = mk_rank_factory(coins, fund)
    passes, chosen = [], None
    for fl_h in [24, 48, 72]:
        for k in [3, 5]:
            for reb in [24, 48]:
                warm = fl_h + HD

                def mk_rank(seg, fl=fl_h):
                    return base(seg, fl)

                r = gate(coins, ts, px, fund, mk_rank, warm, k, reb)
                both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                ok = both and r["full"]["ret"] > 0 and r["mirror"]["price"] < 0
                if ok:
                    passes.append((fl_h, k, reb))
                if (fl_h, k, reb) == (72, 5, 24):
                    chosen = (r, ok)
                print(f"{'fundcarry':>10} {fl_h:>4} {k:>2} {reb:>4} | "
                      f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                      f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                      f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                      f"{r['full']['fund']:>7.1f} | {'PASS' if ok else 'FAIL'}")

    print("\n" + "=" * 78)
    print(f"RESULT — Counterweight's factor on the NON-CRYPTO cross-section "
          f"({span:.0f}d)")
    print("=" * 78)
    print(f"configs passing all gates: {len(passes)}/12  {passes}")
    if chosen:
        r, ok = chosen
        print(f"\nCONTROL'S SHIPPED CONFIG (72h / K=5 / reb 24h) here: "
              f"{'PASS' if ok else '**FAIL**'}")
        print(f"  full {r['full']['ret']:+.1f}%  h1 {r['h1']['ret']:+.1f}%  "
              f"h2 {r['h2']['ret']:+.1f}%  maxDD {r['full']['dd']:.1f}%  "
              f"funding {r['full']['fund']:+.1f}pp  mirror(price) "
              f"{r['mirror']['price']:+.1f}%")
        print("  CRYPTO control measured: full +13.6%  h1 +5.6%  h2 +6.6%  "
              "maxDD 10.1%  funding +4.5pp  mirror -16.4%")

    print("\n" + "-" * 78)
    print("SLIPPAGE STRESS on 72/5/24 — flat friction, the doctrine bar:")
    print("-" * 78)
    print("%-12s %8s %8s %8s  %s" % ("slip/side", "full%", "h1%", "h2%", "verdict"))
    for bps in (5, 10, 15):
        r = gate(coins, ts, px, fund, lambda seg, fl=72: base(seg, fl),
                 72 + HD, 5, 24, slip=bps / 1e4)
        both = (r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0 and r["full"]["ret"] > 0)
        print("%-12s %+8.1f %+8.1f %+8.1f  %s"
              % (f"{bps}bps", r["full"]["ret"], r["h1"]["ret"], r["h2"]["ret"],
                 "green" if both else "**NEGATIVE**"))

    # ---- the per-book cost reality check (see header) ----------------------
    sp = {c: spread.get(c) for c in coins if spread.get(c) is not None}
    if sp:
        worst = sorted(sp.items(), key=lambda x: -x[1])[:6]
        med = sorted(sp.values())[len(sp) // 2]
        print("\n" + "-" * 78)
        print("PER-BOOK FRICTION (live half-spread, bps/side) — the flat 5bps above")
        print("is an assumption; these books are NOT homogeneous:")
        print("-" * 78)
        print(f"  median {med:.2f}bps   worst: "
              + ", ".join(f"{c} {v:.1f}" for c, v in worst))
        print(f"  books wider than the modelled 5bps: "
              f"{sum(1 for v in sp.values() if v > 5)}/{len(sp)}")
        r = gate(coins, ts, px, fund, lambda seg, fl=72: base(seg, fl),
                 72 + HD, 5, 24, slip=med / 1e4)
        print(f"  at the MEDIAN measured half-spread ({med:.2f}bps/side): "
              f"full {r['full']['ret']:+.1f}%  h1 {r['h1']['ret']:+.1f}%  "
              f"h2 {r['h2']['ret']:+.1f}%")


if __name__ == "__main__":
    main()
