#!/usr/bin/env python3
"""
scripts/study_taker_spread_gate.py — evidence table for TT_SPREAD_GATE_BPS, a
proposed QUOTED-SPREAD-at-decision floor on the Ticket Taker's entries. It is
the 23-Jul answer to "the volume floor DIV_VOL_M is the wrong instrument — what
is the right one?" (23 Jul 2026.)

CONTEXT (the whole 23-Jul taker root-cause):
  * The divergence SIGNAL did not decay — the brain grades it forward-positive
    at n>11k. Realised P&L is negative because EXECUTION eats it on wide-quote /
    thin books (the code comment lighter_ticket_taker.py's SPREAD_GATE block).
  * The VOLUME floor (DIV_VOL_M) was RE-REJECTED at grown n (n=99 divergence
    closes): its seductive "+$13.57 t=1.83 both-halves" is a BOT mark-pathology
    artifact (BOT = 47/99 closes, moderate vol_m 0.12-0.59 but 747bps slip, a
    data pathology already vetoed). Remove BOT and EVERY volume floor FAILS
    both-halves; volume does not predict slippage ex-BOT. Volume != toxicity:
    1000BONK (0.12M, 4.8bps, +$5.84 WINNER) is wrongly excluded while SOXL
    (3.07M avg, but 20.9bps slip, loser) is kept. See study_div_vol_floor.py for
    the volume-floor rejection at the ORIGINAL n=37 and this script for its
    re-rejection at n=99.

METHOD (fill-ledger counterfactual — Lighter's own tape, venue-pure):
  * venue_orders.spread_bps is recorded at DECISION time by the ShadowBroker's
    book walk (venues/shadow.py) — 179/179 SHADOW taker rows carry it (the LIVE
    arm records none today; leg is untagged=None, so an open leg is matched to a
    close by nearest `at` to opened_at). It is a genuine AT-OPEN observable,
    historically present — so a spread gate is BACKTESTABLE on the existing
    ledger (unlike the scout-tape replay, whose 'lighter-market' snapshots carry
    only marks, NO spread — the honest limitation that motivates recording live
    spread; see the record-only mode of TT_SPREAD_GATE_BPS).
  * Each divergence close (paper_trades, reason ILIKE '%divergence%', both taker
    bots) is joined to its OPEN-leg spread. Gate sweep: keep spread <= thr,
    recompute per-trade pnl_pct mean + t-stat + both-halves (halves fixed on the
    unfiltered ledger, chronological by closed_at). Unresolved-spread closes are
    KEPT at every threshold (a gate never excludes what it cannot price).
  * Run FULL and EX-BOT (BOT is a mark pathology, already vetoed — its inclusion
    inflates every gate, so the ex-BOT column is the honest test of whether the
    signal generalises).

VERDICT (23 Jul 2026; n=99 divergence closes, 179 taker fills w/ spread):
  * QUOTED SPREAD PREDICTS REALISED SLIPPAGE, and it HOLDS EX-BOT (pearson
    r=+0.44 all / +0.42 ex-BOT). Per-fill, wide quote -> real slip on many
    books: STRC 98->46, IWM 45->27, NBIS 37->45, SOXL 24->78, BABA 30->12.
  * The gate `spread <= ~20bps` is the ONLY gate (spread OR volume) that passes
    both-halves EX-BOT while excluding ONLY losers (ex-BOT keep 46, cum +$14.15
    vs +$8.96 baseline, mean +0.659%/trade, t=+1.30, dH1 +2.18 / dH2 +3.01,
    excluded $0 winners / -$5.19 losers). Tighter (<=10) starts cutting the clean
    thin WINNERS (1000BONK/DATA) and fails both-halves — the same trap volume
    fell into; ~20 is the sweet spot.
  * SHIP DISABLED anyway (default 0). Honest bounds: (1) t=1.30 < 2 — the edge
    the gate protects is real but NOT yet significant; (2) ex-BOT the DOLLAR
    swing is only +$5 (BOT's 790bps catastrophe was the big number, and it is a
    data pathology already vetoed) — the gate's DURABLE value is catching a
    wide-quote FRESH listing on its FIRST fill (ZHIPU-class), the exact class the
    reactive coin-quality veto (>=5 orders) cannot see; (3) not every ex-BOT loss
    is execution — NBIS (-$6.36, ~10bps slip) is a DIRECTIONAL loss (long-
    divergence wrong in a downtrend) that no liquidity gate fixes.
  Re-run once the divergence ledger grows and — critically — once the LIVE arm
  has recorded spread (enable TT_SPREAD_GATE_BPS in record-only mode first), so
  the gate can be validated on real-money fills, not only the shadow book walk.

USAGE:
  DATABASE_PUBLIC_URL=... python3 scripts/study_taker_spread_gate.py
  (or pass the URL as argv[1]; get it from `railway variables --service Postgres
  --kv | grep DATABASE_PUBLIC_URL`).
"""
import os
import sys
import math
import json
import bisect
from datetime import datetime, timezone

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required (use the repo .venv: .venv/bin/python3)")


def _pdt(x):
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    for f in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z",
              "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
              "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(str(x), f)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _t(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    return m / (sd / math.sqrt(n)) if sd else float("nan")


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) \
        if sx and sy else float("nan")


def _stats(sub):
    n = len(sub)
    if n == 0:
        return (0, 0.0, 0.0, float("nan"), 0.0)
    cum = sum(t["pa"] for t in sub)
    pps = [t["pp"] for t in sub]
    mean = sum(pps) / n
    wr = sum(1 for t in sub if t["pa"] > 0) / n
    return (n, cum, mean, _t(pps), wr)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else (
        os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL"))
    if not url:
        sys.exit("need a Postgres URL (argv[1] or DATABASE_PUBLIC_URL)")
    c = psycopg2.connect(url)
    cur = c.cursor()

    # -- taker venue_orders with spread + slippage --------------------------
    cur.execute("select bot, coin, at, spread_bps, slippage_bps "
                "from venue_orders where bot ilike '%ticket-taker%'")
    vo = []
    for bot, coin, at, sp, sl in cur.fetchall():
        vo.append(dict(bot=bot, coin=coin, at=_pdt(at),
                       spread=(float(sp) if sp is not None else None),
                       slip=(abs(float(sl)) if sl is not None else None)))

    both = [(v["spread"], v["slip"]) for v in vo
            if v["spread"] is not None and v["slip"] is not None]
    exbot = [(v["spread"], v["slip"]) for v in vo
             if v["coin"] != "BOT" and v["spread"] is not None
             and v["slip"] is not None]
    print("=" * 78)
    print("(1) QUOTED SPREAD -> REALISED SLIPPAGE  (does it predict, ex-BOT?)")
    print("=" * 78)
    for label, rows in (("ALL fills", both), ("EX-BOT", exbot)):
        print(f"\n{label}: n={len(rows)}  pearson r="
              f"{_pearson([r[0] for r in rows], [r[1] for r in rows]):+.2f}")
        print(f"  {'spread(bps)':14} {'n':>3} {'mean|slip|':>10} {'med|slip|':>9}")
        for lo, hi in [(0, 5), (5, 10), (10, 20), (20, 50), (50, 1e9)]:
            s = sorted(r[1] for r in rows if lo <= r[0] < hi)
            if s:
                print(f"  {f'[{lo},{hi})':14} {len(s):>3} "
                      f"{sum(s)/len(s):>10.1f} {s[len(s)//2]:>9.1f}")

    # -- open-leg spread per (bot,coin): match by nearest at to opened_at ----
    sp_by = {}
    for v in vo:
        if v["spread"] is not None and v["at"] is not None:
            sp_by.setdefault((v["bot"], v["coin"]), []).append((v["at"], v["spread"]))
    for k in sp_by:
        sp_by[k].sort()

    def open_spread(bot, coin, oa, ca):
        arr = sp_by.get((bot, coin))
        if not arr:
            return None
        best, bd = None, None
        for at, sp in arr:
            d = abs((at - oa).total_seconds())
            if d <= 900 and (ca is None or d < abs((at - ca).total_seconds())) \
                    and (bd is None or d < bd):
                best, bd = sp, d
        return best

    cur.execute(
        "select bot, pair, reason, pnl_abs, pnl_pct, opened_at, closed_at "
        "from paper_trades where reason ilike '%divergence%' "
        "and closed_at is not null and bot ilike '%ticket-taker%' "
        "order by closed_at")
    rows = []
    for bot, pair, reason, pa, pp, oa, ca in cur.fetchall():
        coin = str(pair).split("/")[0]
        rows.append(dict(coin=coin, pa=float(pa or 0), pp=float(pp or 0) * 100,
                         ca=_pdt(ca), bot=bot,
                         spread=open_spread(bot, coin, _pdt(oa), _pdt(ca))))
    res = sum(1 for r in rows if r["spread"] is not None)
    print("\n" + "=" * 78)
    print(f"(2) SPREAD GATE SWEEP  ({len(rows)} divergence closes, "
          f"open-spread resolved {res}/{len(rows)}; keep spread <= thr)")
    print("=" * 78)

    def sweep(pool, label):
        ss = sorted(pool, key=lambda t: t["ca"])
        h = len(ss) // 2
        H1 = set(id(t) for t in ss[:h])
        bH1 = sum(t["pa"] for t in ss[:h])
        bH2 = sum(t["pa"] for t in ss[h:])
        _, cum, _, tt, _ = _stats(pool)
        print(f"\n-- {label} (n={len(pool)}) baseline cum ${cum:+.2f} t={tt:+.2f}"
              f" | H1 ${bH1:+.2f}/H2 ${bH2:+.2f} --")
        print(f"  {'thr':>5} {'keep':>4} {'cum$':>8} {'mean%':>7} {'t':>6} "
              f"{'wr':>4} {'exclW/L$':>13} {'dH1':>6} {'dH2':>6} {'both?':>5}")
        for thr in [9999, 20, 15, 10, 8, 6, 5]:
            kept = [t for t in pool if t["spread"] is None or t["spread"] <= thr]
            excl = [t for t in pool if not (t["spread"] is None or t["spread"] <= thr)]
            n, cum, mean, tt, wr = _stats(kept)
            exW = sum(t["pa"] for t in excl if t["pa"] > 0)
            exL = sum(t["pa"] for t in excl if t["pa"] <= 0)
            kH1 = sum(t["pa"] for t in kept if id(t) in H1)
            kH2 = sum(t["pa"] for t in kept if id(t) not in H1)
            both = "YES" if (kH1 - bH1 > 0 and kH2 - bH2 > 0) else "no"
            print(f"  {thr:>5.0f} {n:>4} {cum:>+8.2f} {mean:>+7.3f} {tt:>+6.2f} "
                  f"{wr*100:>3.0f}% {exW:>+5.2f}/{exL:>+6.2f} "
                  f"{kH1-bH1:>+6.2f} {kH2-bH2:>+6.2f} {both:>5}")

    sweep(rows, "FULL")
    sweep([t for t in rows if t["coin"] != "BOT"], "EX-BOT  (the honest test)")
    print("\nVERDICT: spread<=20 EX-BOT is the only gate that lifts both halves "
          "excluding only losers (t=+1.30, still <2). Ship DISABLED; record live "
          "spread first. See the module header of lighter_ticket_taker.py.")
    cur.close()
    c.close()


if __name__ == "__main__":
    main()
