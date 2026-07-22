#!/usr/bin/env python3
"""
scripts/backtest_xsect_funding_lighter.py — ⚖️ Counterweight's funding-rank
factor, backtested ON LIGHTER at last.

WHY THIS EXISTS (2026-07-17)
  backtest_xsect_factor_lab.py PASSED factor B (cross-sectional funding rank)
  and shipped it as Counterweight — but it ran on `.dirfund_cache.json`, which
  is **HYPERLIQUID** data: it ranks on HL funding and accrues HL funding, start
  to finish. The live book ranks on LIGHTER funding and earns LIGHTER funding.
  No backtest has ever tested the live signal. This is the same hole the 17-Jul
  Funding Farmer work found ("every funding backtest ran on Hyperliquid"), and
  the same fix: Lighter serves its OWN settled history and always did.

  Found while investigating a reported unit-mixing bug in the bot's ranking
  window (scripts/study_fundspread_basis_mixing.py — that bug is real but
  INERT; this validation gap is the bigger finding, and the operator asked for
  the re-run rather than an agenda note).

WHAT IS HELD IDENTICAL TO THE HL LAB (vary ONE variable — the venue)
  The scoring, the book construction, the gates and the arithmetic are the HL
  lab's, transcribed unchanged:
    * score  = -mean(trailing funding over fl_h)   [negated, as the HL lab]
    * ranked descending => ranked[:k] = most NEGATIVE funding => LONG (receives)
                           ranked[-k:] = hottest POSITIVE     => SHORT (receives)
    * funding cf = -side * hourly_rate * ORDER_USD, accrued every hour held
    * $20/leg, 5bps/side slip, rebalance on schedule, no per-position stop
    * GATES: full>0 AND h1>0 AND h2>0 AND mirror(price)<0; plateau, not a cell
  ONLY the data source changes: Lighter `/api/v1/fundings` (SETTLED hourly,
  the `direction` field applied so the series is SIGNED) + `/api/v1/candles`,
  via backtest_funding_lighter.py's fetchers. That file never touches
  /funding-rates, so the 8x cannot leak in here.

UNITS — the thing this whole exercise is about
  fetch_fundings returns a signed TRUE APR fraction per hour-stamp. The HL lab's
  `fund[c][t]` is a per-HOUR fraction. So: hourly = apr / (24*365). Converted
  once, at load, and asserted (a sanity bound rejects an apr that is secretly
  an hourly rate or vice versa). Do not "simplify" this away.

UNIVERSE
  The BOT's own COINS list (FUNDSPREAD_COINS default) intersected with tradeable
  Lighter markets — the faithful test of the live book, not a fresh universe.
  5 of the 30 (INJ/RUNE/STX/GALA/W) are not Lighter markets and the live bot
  already skips them via ctx.supports(); they are excluded here too.

VERDICT (17 Jul 2026, 150d ending 17 Jul, 25 coins, 3585 hourly bars)
  **THE EDGE IS REAL ON LIGHTER — it REPLICATES, and the agreement with the HL
  lab is close enough to be uncanny.** The shipped live config (72h/K=5/reb 24h)
  PASSES every doctrine gate on the venue the book actually trades:
                        LIGHTER (measured)     HL lab (claimed)
      full                   +13.6%                +13.7%
      h1 / h2             +5.6 / +6.6           +5.7 / +8.9
      maxDD                   10.1%                 11.9%
      funding                 +4.5pp                +6.8pp
      mirror(price)          -16.4%                -14.4%
  * PLATEAU REPLICATES: the ENTIRE 72h-lookback row is green (4/4), exactly the
    HL lab's defining feature, and quality still improves monotonically with
    lookback (24h 1/4, 48h 1/4, 72h 4/4). 6/12 configs pass overall vs HL's
    8/12 — the 48h row is thinner here (1/4 vs 3/4), so the plateau is REAL but
    NARROWER: it is the 72h row, not the 48-72 block. Do not run this book at
    48h on Lighter.
  * MIRROR negative everywhere (-12% to -40%): the ranking carries genuine
    information; the inverted book loses. Not a coin-flip.
  * 3x FRICTION: 10bps/side +10.4% (+3.9/+5.2), 15bps/side +7.3% (+2.2/+3.7) —
    green in BOTH halves at triple the modelled slippage.
  * FUNDING is +4.5pp of the +13.6%, vs +6.8pp on HL — Lighter's funding
    cross-section is less extreme (its floor band is 3.5% apr, not 28%), so the
    carry leg contributes about a third less. The edge is correspondingly more
    dependent on the price/mean-reversion leg than the HL lab implied.
  **THIS VERDICT IS A FLOOR, NOT AN ESTIMATE — read this before citing it.**
  SLIP is held at the HL lab's 5bps/side so that exactly ONE variable (the
  venue) changes. But 5bps is an ASSUMPTION, and Lighter friction has since been
  MEASURED at **0.86bps/fill** (see the 17-Jul stop finding in
  backtest_funding_lighter.py's orbit) — the same unmeasured assumption that
  manufactured a FALSE "no edge" verdict on the Funding Farmer. So the real
  numbers are BETTER than these, and the "3x stress" at 15bps is really ~17x
  measured. The PASS is conservative in the direction that matters. A re-run at
  0.86bps is the obvious next measurement — and the lesson cuts BOTH ways: an
  assumed friction can fake an edge as easily as it can hide one.

  DO NOT say this "killed the Funding Farmer and vindicates Counterweight". The
  Funding Farmer's verdict was itself REVISED the same day (its HARD_STOP, not
  its gate, was said to be the defect: STOP 0.03 -> +$21.32, both halves
  positive, n=1911). ⛔ [2026-07-22] THAT REVISION IS ITSELF WITHDRAWN — the
  +$21.32 was a harness artifact (un-cleared `hot` on close => instant
  re-entries production refuses); corrected it is -$11.57, BOTH halves
  NEGATIVE. So the Farmer's stop was never shown to be the defect either. The
  point below is unaffected ([[harness-must-mirror-productions-close-path]]).
  What the re-test does is replace a HYPOTHESIS with a MEASUREMENT; the answer
  here happened to be favourable. maxDD 10.1% also clears the 15% go-live gate —
  but a backtest is not a shadow record, and go-live remains a separate decision
  on the LIVE record (which, until 93be95e, was 8x-inflated on its funding leg).

  DOCTRINE CONVERGENCE (17-Jul, operator: "backtest on Lighter ONLY — the venue
  we trade is the venue we measure"): this file IS that rule applied to
  Counterweight. Note the same rule condemns the bot's `hl_backfill()` —
  audit_venue_purity.py flags lighter_funding_spread_bot.py line 85
  (api.hyperliquid.xyz) as a SHIPPED violation. Removing it is no longer just
  this study's recommendation; it is required. The replacement (Lighter's own
  settled series) is the very tape this file validates.

Read-only: hits public endpoints, writes only its cache. Touches no bot, no DB.
Usage:
    python3 scripts/backtest_xsect_funding_lighter.py
    python3 scripts/backtest_xsect_funding_lighter.py --days 150 --refresh
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from backtest_funding_lighter import _get, fetch_candles, fetch_fundings  # noqa: E402

CACHE = os.path.join(os.path.dirname(__file__), ".xsectfund_lighter_cache.json")

# the live bot's config (lighter_funding_spread_bot.py) mirrored
COINS = ("BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,AAVE,WIF,"
         "JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,PYTH,W").split(",")
ORDER_USD = 20.0        # the backtested clip
SLIP = 0.0005           # 5bps/side — the HL lab's number, held
HD = 24
HOURS_PER_YEAR = 24 * 365


def load(days, refresh):
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= days:
            return {s: {"fund": {int(k): v for k, v in m["fund"].items()},
                        "cand": {int(k): float(v) for k, v in m["cand"].items()}}
                    for s, m in d["mk"].items()}
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    ids = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    missing = [c for c in COINS if c not in ids]
    print(f"universe: {len(COINS)} bot coins; NOT Lighter markets (bot skips "
          f"these too): {missing}")
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
        if len(common) < 24 * 20:
            print(f"  {sym}: only {len(common)}h paired — skipped")
            continue
        mk[sym] = {"fund": {t: fund[t] for t in common},
                   "cand": {t: cand[t][3] for t in common}}   # close
        print(f"  {sym:6s} {len(common):5d}h paired "
              f"({(max(common)-min(common))/86400:.0f}d)")
    json.dump({"days": days, "mk": mk}, open(CACHE, "w"))
    return mk


def align(mk):
    common = sorted(set.intersection(*[set(m["cand"]) for m in mk.values()]))
    coins = sorted(mk)
    px = {c: {t: mk[c]["cand"][t] for t in common} for c in coins}
    # APR -> per-hour fraction. Asserted, because this file exists because a
    # unit was wrong somewhere else.
    fund = {c: {t: mk[c]["fund"][t] / HOURS_PER_YEAR for t in common}
            for c in coins}
    sample = [abs(v) for c in coins for v in mk[c]["fund"].values()]
    med = sorted(sample)[len(sample) // 2]
    assert 1e-4 < med < 5.0, (
        f"funding tape median |apr| {med:.2e} is not an APR fraction — the "
        f"units moved; fix the loader, do not scale here")
    return coins, common, px, fund


def simulate(coins, ts, px, fund, rank_fn, warm_h, k, reb_h, invert=False,
             slip=SLIP):
    """The HL lab's simulate(), transcribed. Only `fund` differs in origin."""
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
        c, pp, fp, dd, tr, w, g = simulate(coins, seg, px, fund, mk_rank(seg),
                                           warm_h, k, reb_h, slip=slip)
        out[name] = dict(ret=100 * c / g, fund=100 * fp / g, dd=dd, trips=tr)
    c, pp, fp, dd, tr, w, g = simulate(coins, ts, px, fund, mk_rank(ts), warm_h,
                                       k, reb_h, invert=True, slip=slip)
    out["mirror"] = dict(ret=100 * c / g, price=100 * pp / g)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)   # the HL lab's window
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    mk = load(a.days, a.refresh)
    if len(mk) < 12:
        sys.exit(f"only {len(mk)} coins with paired history — not a cross-section")
    coins, ts, px, fund = align(mk)
    span = (ts[-1] - ts[0]) / 86400
    print(f"\nuniverse {len(coins)} Lighter coins, {len(ts)} hourly bars "
          f"({span:.0f}d), clip ${ORDER_USD:.0f}, slip {SLIP*1e4:.0f}bps/side")
    print("SIGNED settled Lighter funding (direction applied). "
          "The live book's own venue, at last.\n")

    hdr = (f"{'factor':>10} {'lb':>4} {'k':>2} {'reb':>4} | {'full%':>7} "
           f"{'h1%':>7} {'h2%':>7} {'dd%':>5} {'trips':>5} | {'mirror%':>8} "
           f"{'fund_pp':>7} | verdict")
    print(hdr)
    print("-" * len(hdr))

    passes, chosen = [], None
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
    print(f"RESULT — Counterweight's factor on LIGHTER's own tape ({span:.0f}d)")
    print("=" * 78)
    print(f"configs passing all gates: {len(passes)}/12  {passes}")
    if chosen:
        r, ok = chosen
        print(f"\nTHE SHIPPED LIVE CONFIG (72h / K=5 / reb 24h): "
              f"{'PASS' if ok else '**FAIL**'}")
        print(f"  full {r['full']['ret']:+.1f}%  h1 {r['h1']['ret']:+.1f}%  "
              f"h2 {r['h2']['ret']:+.1f}%  maxDD {r['full']['dd']:.1f}%  "
              f"funding {r['full']['fund']:+.1f}pp  mirror(price) "
              f"{r['mirror']['price']:+.1f}%")
        print("  HL lab claimed: full +13.7%  h1 +5.7%  h2 +8.9%  maxDD 11.9%  "
              "funding +6.8pp")
    # ---- the doctrine's last gate: does the pick survive 3x friction? -------
    print("\n" + "-" * 78)
    print("SLIPPAGE STRESS on the shipped config (72/5/24) — the doctrine bar:")
    print("still green in BOTH halves at 3x modelled friction?")
    print("-" * 78)

    def mk_rank72(seg, fl=72):
        def rank(i):
            sc = {}
            for c in coins:
                rs = [fund[c].get(seg[j]) for j in range(i - fl, i)]
                rs = [x for x in rs if x is not None]
                if len(rs) >= fl // 2:
                    sc[c] = -sum(rs) / len(rs)
            return sc
        return rank

    print("%-12s %8s %8s %8s  %s" % ("slip/side", "full%", "h1%", "h2%", "verdict"))
    stress_ok = True
    for bps in (5, 10, 15):
        r = gate(coins, ts, px, fund, mk_rank72, 72 + HD, 5, 24, slip=bps / 1e4)
        both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0 and r["full"]["ret"] > 0
        if bps == 15 and not both:
            stress_ok = False
        print("%-12s %+8.1f %+8.1f %+8.1f  %s"
              % (f"{bps}bps", r["full"]["ret"], r["h1"]["ret"], r["h2"]["ret"],
                 "green" if both else "**NEGATIVE**"))
    print(f"\n3x-friction (15bps/side) survival: "
          f"{'PASS' if stress_ok else 'FAIL'}")
    print("  HL lab claimed: 10bps +10.3% (+4.1/+7.1), 15bps +6.9% (+2.5/+5.3)")

    print("\nThe HL lab passed 8/12 with the WHOLE 72h row green. If that "
          "plateau\nis absent here, the edge was Hyperliquid's, not Lighter's — "
          "and the\nbook has been trading a signal no backtest ever validated.")


if __name__ == "__main__":
    main()
