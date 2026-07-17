#!/usr/bin/env python3
"""
clock_consumer_premise_check.py — does the fleet clock's `event_window` mark
moments a SCANNER should care about?

VERDICT (2026-07-17, first run, 69h tape): **NO SUPPORT FOUND.** Every
dislocation quantity the premise names is FLAT at the bell. Don't wire a
scanner cadence boost on this evidence; re-run before the review and after
more sessions accumulate.

WHY THIS EXISTS. Agenda item 11 offered three "first consumers" for the
circadian organ. All three were written by one 16-Jul session, in one breath,
with zero verification. The equities option was checked on 17-Jul and turned
out FABRICATED (it described a bot design this repo does not contain). The
other two were then carried forward as "the honest candidates" — which is
survivorship, not validation: they were never scrutinised either. This script
scrutinises the scanner one, against the tape the fleet already writes, so the
21-Jul review decides on a measurement instead of on prose.

THE PREMISE, VERBATIM: "opens/closes are when dislocations and vol moves
happen." That is a DENSITY claim about the market, and it is directly
measurable: `lighter_market_scout` publishes a premium-stress cross-section
(`stress.med/p90/max` over every book with premium data) plus vol/OI move
counts on every ~5-min sample, and `bot_state_history` keeps it for 60 days.
Test = those quantities INSIDE the clock's real ±15min `event_window` vs
outside it. Welch t on the two samples; |t|>2 to call a difference.

RESULT, first run — 827 samples, 07-14 05:07Z → 07-17 02:03Z (69h, 3 NYSE
sessions), NYSE ±15min n=36 in-window / 791 out:
    stress.med   5.62 in  vs 5.62 out   (t=+0.06)  — dead flat
    stress.p90  15.59 in  vs 16.28 out  (t=-1.91)  — if anything LOWER
    stress.max  67.65 in  vs 74.71 out  (t=-1.41)  — if anything LOWER
    oi_moves     0.11 in  vs 0.06 out   (t=+0.98)  — no difference
Widening to ANY clock event (NYSE + crypto session seams, n=144/683) does not
change it. NOT ONE metric is higher in-window. The premise had the burden and
produced nothing: dislocation intensity at the bell is indistinguishable from
any other moment on this venue.

TWO METRICS ARE INERT — do not cite them either way:
  * `prem_outliers` is a fixed TOP-8 list, so its length is 8.00 on both sides
    by construction. It carries zero density signal.
  * `vol_surges` flags "LOWER" at t=-2.24 on means of 0.00 vs 0.01 — an
    artifact of near-zero counts (~8 surges in 791 samples), not evidence the
    window is worse. A near-zero base cannot support a verdict in EITHER
    direction.

LIMITATIONS — state these at the review; they are the reason this is "no
support found", not "refuted":
  * 3 NYSE sessions, n=36 in-window samples. The point estimates are FLAT
    (stress.med differs by +0.01 bps on a 5.62 bps base), not merely noisy —
    but a real effect smaller than ~1 bps would not be visible yet.
  * Measures EMISSION/INTENSITY, not the VALUE of acting in the window. A
    cadence boost could in principle catch *better* dislocations rather than
    more of them. That is a different (untested) hypothesis, and it is not the
    one the agenda offered.
  * NOT TESTED — the equity-perp subset. `stress` is an aggregate over ~94
    books, and the scout's universe is NOT crypto-only: its premium outliers
    are dominated by EQUITY perps (SAMSUNGUSD, SKHYNIXUSD, ZHIPU, DRAM, ORCL).
    A real NYSE-bell effect confined to those names could be washed out by the
    crypto majority here. If the review wants the scanner option alive, THIS is
    the scoped next test — and note it would need the right bell per name
    (KRX/HKEX for the Korean/Chinese listings, not NYSE).

THE GAP SCOUT HALF IS NOT ANSWERABLE AND WAS NOT TESTED. The 17-Jul agenda
text claimed this was "cheaply checkable" via `gapscout-census` history. That
claim was itself unverified and WRONG: epoch 2 has written FOUR history rows
total, spanning 12 minutes on 07-16 — two episodes, both CRO/USD on the same
kraken→coinbaseexchange route (`scanner-cross-exchange-arb` has 2 paper_trades
rows fleet-wide). There is no density to measure. Separately worth the
review's attention: a "cadence boost" for a scanner booking 2 episodes in 2
days is aimed at the wrong bottleneck — the census is quiet enough that the
evidence board's growth rail is already widening its prefilter.

Read-only. Needs DATABASE_PUBLIC_URL (or DATABASE_URL) in env; touches no bot.
    python3 clock_consumer_premise_check.py
"""
import os
import statistics as st
import sys
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 not installed")

WINDOW_MIN = float(os.environ.get("CLOCK_EVENT_PRE_MIN", "15"))
# NYSE regular hours in UTC during EDT (July). The clock organ owns the real
# calendar; this check only spans days where that mapping holds — assert it if
# you extend the tape across a DST boundary or a holiday.
NYSE_UTC_MIN = (13 * 60 + 30, 20 * 60)
CRYPTO_SEAM_H = (0, 7, 8, 13, 16, 21)

METRICS = {
    "stress.med (bps)": lambda p: (p.get("stress") or {}).get("med"),
    "stress.p90 (bps)": lambda p: (p.get("stress") or {}).get("p90"),
    "stress.max (bps)": lambda p: (p.get("stress") or {}).get("max"),
    "oi_moves (n)": lambda p: len(p.get("oi_moves") or []),
    "tickets (n)": lambda p: (sum(len(v) for v in (p.get("tickets") or {}).values())
                              if isinstance(p.get("tickets"), dict) else None),
}


def _events(days):
    ny, cr = [], []
    for d in days:
        base = datetime.combine(d, datetime.min.time(), timezone.utc)
        if d.weekday() < 5:
            ny += [base + timedelta(minutes=m) for m in NYSE_UTC_MIN]
        cr += [base + timedelta(hours=h) for h in CRYPTO_SEAM_H]
    return ny, cr


def _welch(a, b):
    try:
        se = (st.variance(a) / len(a) + st.variance(b) / len(b)) ** 0.5
        return (st.mean(a) - st.mean(b)) / se if se else 0.0
    except Exception:  # noqa: BLE001
        return float("nan")


def main():
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("set DATABASE_PUBLIC_URL (railway variables --service Postgres)")
    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        cur.execute("SELECT ts, payload FROM bot_state_history "
                    "WHERE key='lighter-market' ORDER BY ts")
        rows = cur.fetchall()
    if len(rows) < 50:
        sys.exit(f"tape too short to say anything: {len(rows)} samples")

    days = sorted({r[0].date() for r in rows})
    span = [days[0] + timedelta(days=k - 1) for k in range(len(days) + 3)]
    ny, cr = _events(span)
    near = lambda ts, evs: min(abs((ts - e).total_seconds()) / 60.0 for e in evs)  # noqa: E731

    for label, evs in (("NYSE open/close", ny), ("ANY clock event (NYSE + crypto seams)", ny + cr)):
        print(f"\n=== {label} — ±{WINDOW_MIN:.0f}min event_window ===")
        print(f"{'metric':22s} {'in-win':>9s} {'out':>9s} {'delta':>8s} {'t':>7s}  verdict")
        for name, fn in METRICS.items():
            inw = [fn(p) for ts, p in rows if near(ts, evs) <= WINDOW_MIN and fn(p) is not None]
            out = [fn(p) for ts, p in rows if near(ts, evs) > WINDOW_MIN and fn(p) is not None]
            if len(inw) < 5 or len(out) < 5:
                print(f"{name:22s}  insufficient samples ({len(inw)}/{len(out)})")
                continue
            mi, mo, t = st.mean(inw), st.mean(out), _welch(inw, out)
            verdict = "HIGHER" if t > 2 else "LOWER" if t < -2 else "no diff"
            print(f"{name:22s} {mi:9.2f} {mo:9.2f} {mi - mo:+8.2f} {t:+7.2f}  "
                  f"{verdict}   (n={len(inw)}/{len(out)})")

    hrs = (rows[-1][0] - rows[0][0]).total_seconds() / 3600
    print(f"\ntape: {len(rows)} samples  {rows[0][0]:%m-%d %H:%M}Z -> "
          f"{rows[-1][0]:%m-%d %H:%M}Z ({hrs:.0f}h)")
    print("A scanner cadence boost needs at least ONE metric materially HIGHER "
          "in-window. Read the LIMITATIONS in this file's header before calling "
          "a flat result a refutation.")
    conn.close()


if __name__ == "__main__":
    main()
