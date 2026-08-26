#!/usr/bin/env python3
"""A 24h-turnover floor is a PROXY. This measures the thing it stands in for.

THE CAGE. 🌾 carry — the fleet's best-evidenced book (n=101, +$66.21, and the
only one that has ever cleared the `t` bar) — was holding **0 of its 12 slots**
with **`eligible: 0` of 228 books scanned**. Its `CARRY_MIN_VOL` floor exists
because *"per-book slippage here is unmeasured"* ((px), quoting
[[lighter-slippage-is-per-book-not-per-venue]]): the floor is not a view about
volume, it is a stand-in for a cost nobody had measured. That is a defensible
place to start and an indefensible place to stay — an unmeasured quantity is a
reason to measure, not a reason to keep refusing.

WHAT THE FLOOR ACTUALLY DOES, measured 2026-08-20 against the venue's own tape:
20 books cleared the 20% TRUE APR bar and the $1M floor refused **16 of them** —
including UNITREE at **1202% APR** on $858k of turnover and 3,723 trades/day,
whose funding repays a 22bps round trip in **1.6 hours**. Of the four it
admitted, PUMP sits at 21.9% APR — an **88-hour** payback. The floor was
admitting the slowest-paying carries in the venue and refusing the fastest,
because turnover and payback are close to orthogonal.

WHAT THIS MEASURES INSTEAD. For each candidate: walk the LIVE book both ways for
the clip the bot actually trades, through `venues.shadow.fill_from_book` — the
fleet's own fill model, imported rather than re-implemented, so this cannot
disagree with what the book will really pay. Round-trip cost in bps, then the
PAYBACK HORIZON: how many hours of funding at the current rate repay it.

    payback_h = rt_cost_frac / (true_apr / 8760)

A carry whose payback is a small fraction of its max hold is a good carry
whatever its 24h turnover says; one whose payback exceeds its max hold cannot
pay for itself at any size. That is the quantity the gate wants, and unlike
turnover it is denominated in the same units as the decision.

HONESTY. Depth is a SNAPSHOT — one book, one moment, top 25 levels. It says what
the clip costs now, not what it costs in a squeeze, and a book that cannot fill
the clip out of visible depth is reported UNFILLABLE rather than given a number.
`--clip` is the real decision variable and the output is meaningless without it.

    python3 scripts/study_depth_vs_volume.py --clip 80 --apr 0.20
    python3 scripts/study_depth_vs_volume.py --clip 300 --floor 2e6
    python3 scripts/study_depth_vs_volume.py --selftest
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

#: THE FILL RULE HAS ONE OWNER and it is the BOT, not this script. `rt_cost_bps`
#: is imported from `funding_carry_bot` so a measurement here can never disagree
#: with the gate it is measuring — the second-copy-of-a-rule trap (hj), which on
#: a cost model would show up as a study recommending books the book refuses.
from funding_carry_bot import (payback_hours,                    # noqa: E402
                               rt_cost_bps as _rt)

LIGHTER = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
#: Lighter settles funding every 8h -> 1095 periods/yr. The one place this
#: number belongs is `funding_basis`; imported, never retyped.
try:
    import funding_basis
    PERIODS_Y = float(funding_basis.periods_per_year("lighter"))
except Exception:                                                # noqa: BLE001
    PERIODS_Y = 1095.0


def _get(path, **params):
    url = f"{LIGHTER}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def book_of(market_id, limit=25):
    d = _get("/api/v1/orderBookOrders", market_id=market_id, limit=limit)
    bids = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                   for o in (d.get("bids") or [])), key=lambda x: -x[0])
    asks = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                   for o in (d.get("asks") or [])), key=lambda x: x[0])
    return {"bids": bids, "asks": asks}


def roundtrip_bps(book, clip_usd):
    """The bot's own `rt_cost_bps`, plus the levels each leg consumed.

    Only the LEVEL COUNTS are computed here — they are reporting detail, not
    part of the decision, so the decision itself stays in the one place that
    owns it.
    """
    from venues.shadow import fill_from_book
    bps = _rt(book, clip_usd)
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if bps is None:
        if not bids or not asks:
            return None, 0, 0
        mid = (bids[0][0] + asks[0][0]) / 2.0
        size = (clip_usd / mid) if mid > 0 else 0.0
        b = fill_from_book(book, True, size) if size else None
        sl = fill_from_book(book, False, size) if size else None
        return None, (b[1] if b else 0), (sl[1] if sl else 0)
    mid = (bids[0][0] + asks[0][0]) / 2.0
    size = clip_usd / mid
    return bps, fill_from_book(book, True, size)[1], \
        fill_from_book(book, False, size)[1]


payback_h = payback_hours


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", type=float, default=80.0)
    ap.add_argument("--apr", type=float, default=0.20, help="TRUE APR bar")
    ap.add_argument("--floor", type=float, default=1e6, help="the volume gate")
    ap.add_argument("--max-hold-h", type=float, default=336.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    rates = {r["symbol"]: float(r["rate"])
             for r in (_get("/api/v1/funding-rates").get("funding_rates") or [])
             if r.get("exchange") == "lighter" and r.get("symbol")}
    det = {r["symbol"]: r for r in
           (_get("/api/v1/orderBookDetails").get("order_book_details") or [])
           if r.get("status") == "active"}

    cands = []
    for sym, rate in rates.items():
        d = det.get(sym)
        if not d:
            continue
        apr = abs(rate) * PERIODS_Y
        if apr < a.apr:
            continue
        cands.append((sym, apr, float(d.get("daily_quote_token_volume") or 0),
                      d.get("market_id"),
                      int(d.get("daily_trades_count") or 0)))
    cands.sort(key=lambda r: -r[1])
    print(f"clip ${a.clip:,.0f} · TRUE APR bar {a.apr:.0%} · turnover floor "
          f"${a.floor:,.0f} · max hold {a.max_hold_h:.0f}h · "
          f"{len(cands)} book(s) over the APR bar\n")
    print(f"  {'sym':<11}{'TRUE apr':>10}{'24h $vol':>13}{'trds':>6}"
          f"{'floor':>7}{'rt_bps':>9}{'lvls':>7}{'payback_h':>11}  verdict")
    adm_by_vol, adm_by_cost, both, neither = [], [], [], []
    for sym, apr, vol, mid_id, trades in cands:
        try:
            bps, li, lo = roundtrip_bps(book_of(mid_id), a.clip)
        except Exception as e:                                   # noqa: BLE001
            print(f"  {sym:<11}{apr * 100:>9.1f}%{vol:>13,.0f}{trades:>6}"
                  f"{'':>7}{'ERR':>9}   {type(e).__name__}")
            continue
        pb = payback_h(bps, apr)
        vol_ok = vol >= a.floor
        cost_ok = pb is not None and pb <= a.max_hold_h
        verdict = ("UNFILLABLE at this clip" if bps is None else
                   "pays back inside max hold" if cost_ok else
                   "cannot pay for itself")
        (both if (vol_ok and cost_ok) else adm_by_vol if vol_ok else
         adm_by_cost if cost_ok else neither).append(sym)
        print(f"  {sym:<11}{apr * 100:>9.1f}%{vol:>13,.0f}{trades:>6}"
              f"{('pass' if vol_ok else 'BLOCK'):>7}"
              f"{(f'{bps:.1f}' if bps is not None else '—'):>9}"
              f"{(f'{li}/{lo}' if bps is not None else '—'):>7}"
              f"{(f'{pb:.1f}' if pb is not None else '—'):>11}  {verdict}")

    print(f"\n  both gates agree (admit)      : {len(both):>3}  "
          f"{', '.join(both[:10])}")
    print(f"  turnover admits, cost refuses : {len(adm_by_vol):>3}  "
          f"{', '.join(adm_by_vol[:10])}   <- paying for depth it does not need")
    print(f"  turnover refuses, cost admits : {len(adm_by_cost):>3}  "
          f"{', '.join(adm_by_cost[:10])}   <- the cage")
    print(f"  both refuse                   : {len(neither):>3}  "
          f"{', '.join(neither[:10])}")
    print("\nrt_bps walks the LIVE book both ways for the clip through the "
          "fleet's own\n`fill_from_book`; payback_h is how long the current "
          "rate takes to repay it.\nDepth is a SNAPSHOT — it prices the clip "
          "now, not in a squeeze.")
    return 0


def selftest():
    # a 2-level book, clip fits at the top level: cost is the half-spread twice
    b = {"bids": [(99.0, 100.0), (98.0, 100.0)],
         "asks": [(101.0, 100.0), (102.0, 100.0)]}
    bps, li, lo = roundtrip_bps(b, 100.0)
    assert li == lo == 1, (li, lo)
    assert abs(bps - 200.0) < 1e-6, bps          # 1.0 in + 1.0 out on mid 100

    # walking deeper costs strictly more
    deep, _, _ = roundtrip_bps(b, 100.0 * 150)
    assert deep > bps, (deep, bps)

    # visible depth cannot fill -> UNFILLABLE, never a big number
    assert roundtrip_bps(b, 1e9)[0] is None
    assert roundtrip_bps({"bids": [], "asks": []}, 10.0)[0] is None

    # a perfectly tight book is free
    tight = {"bids": [(100.0, 1e9)], "asks": [(100.0, 1e9)]}
    assert abs(roundtrip_bps(tight, 100.0)[0]) < 1e-9

    # payback: 22bps at 100% APR = 0.0022 / (1/8760) h
    assert abs(payback_h(22.0, 1.0) - 19.272) < 1e-3, payback_h(22.0, 1.0)
    # and it is INVERSE in the rate — 10x the rate, a tenth of the wait
    assert abs(payback_h(22.0, 10.0) * 10 - payback_h(22.0, 1.0)) < 1e-9
    assert payback_h(22.0, 0.0) is None and payback_h(None, 1.0) is None
    assert PERIODS_Y == 1095.0, PERIODS_Y
    print("study_depth_vs_volume selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
