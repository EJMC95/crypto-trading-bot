#!/usr/bin/env python3
"""
scripts/backtest_xsect_slope.py — FACTOR D: cross-sectional FUNDING-SLOPE rank.

The Funding Farmer's slope GATE is doctrine-validated (enter only while |apr|
is still building). This asks the cross-sectional cousin: rank coins by the
CHANGE in funding (mean of recent window minus mean of prior window), SHORT
the fastest-RISING funding (shorts will receive more), LONG the fastest-
FALLING (rates heading negative pay longs). Distinct from Counterweight's
LEVEL rank (backtest_xsect_factor_lab.py FACTOR B, shipped) — this trades the
derivative. NOT a re-test of the rejected premium factors (those duplicated
the slope gate inside the Farmer's threshold entry; this is a standalone
always-in book).

Same harness + gates as the factor lab (both halves, mirror, plateau, on the
150d dirfund cache).

VERDICT (12 Jul 2026, 150d ending 10 Jul): REJECTED — 0/16 configs pass.
  Full-window negative nearly everywhere (best cell 24v48/K3/48h +6.4% is
  H2-NEGATIVE, -17.3%); the slope book churns 329-1181 trips (vs the level
  book's ~340) and the derivative signal decays inside the holding period.
  The slope is a good ENTRY-TIMING gate (where it is already shipped in the
  Funding Farmer) but carries no durable cross-sectional edge of its own.
  Do not re-test. Cross-sectional scorecard on this venue is now 1-for-5:
  momentum ✗, reversal ✗, low-vol ✗, funding-slope ✗, funding-LEVEL ✓
  (shipped as ⚖️ Counterweight).

Usage:  python3 scripts/backtest_xsect_slope.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import backtest_xsect_factor_lab as lab  # noqa: E402  (shared harness)

HD = lab.HD


def main():
    data = lab.load()
    fund = {c: d["fund"] for c, d in data.items()}
    coins, ts, px = lab.align(data)
    print(f"universe {len(coins)} coins, {len(ts)} hourly bars, "
          f"clip ${lab.ORDER_USD:.0f}, slip {lab.SLIP*1e4:.0f}bps/side\n")
    hdr = (f"{'recent':>6} {'prior':>5} {'k':>2} {'reb':>4} | {'full%':>7} "
           f"{'h1%':>7} {'h2%':>7} {'dd%':>5} {'trips':>5} | {'mirror%':>8} "
           f"{'fund_pp':>7} | verdict")
    print(hdr)
    print("-" * len(hdr))
    passing = []
    for rec_h, pri_h in [(12, 36), (24, 48), (24, 72), (48, 96)]:
        for k in [3, 5]:
            for reb in [24, 48]:
                warm = rec_h + pri_h + HD

                def mk_rank(seg, rec=rec_h, pri=pri_h):
                    def rank(i):
                        sc = {}
                        for c in coins:
                            f = fund[c]
                            r1 = [f.get(seg[j]) for j in range(i - rec, i)]
                            r0 = [f.get(seg[j]) for j in range(i - rec - pri,
                                                               i - rec)]
                            r1 = [x for x in r1 if x is not None]
                            r0 = [x for x in r0 if x is not None]
                            if len(r1) >= rec // 2 and len(r0) >= pri // 2:
                                slope = sum(r1) / len(r1) - sum(r0) / len(r0)
                                sc[c] = -slope   # top of rank = fastest-FALLING -> LONG
                        return sc
                    return rank

                r = lab.gate(coins, ts, px, fund, mk_rank, warm, k, reb)
                both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                ok = both and r["full"]["ret"] > 0 and r["mirror"]["price"] < 0
                if ok:
                    passing.append((rec_h, pri_h, k, reb, r))
                print(f"{rec_h:>6} {pri_h:>5} {k:>2} {reb:>4} | "
                      f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                      f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                      f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                      f"{r['full']['fund']:>7.1f} | {'PASS' if ok else 'FAIL'}")
    print(f"\n{len(passing)} / 16 configs pass all gates")
    for rec, pri, k, reb, r in passing:
        print(f"  PASS: slope {rec}v{pri} k={k} reb={reb} -> "
              f"full {r['full']['ret']:+.1f}% h1 {r['h1']['ret']:+.1f}% "
              f"h2 {r['h2']['ret']:+.1f}%")


if __name__ == "__main__":
    main()
