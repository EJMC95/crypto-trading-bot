#!/usr/bin/env python3
"""study_georgia_entry_rank_2026-08-22.py — is 🔮 georgia's entries-per-hour cap
throwing away her best trades?

WHY (2026-08-22). Eamon, on the real-money P&L: *"all the work we did on p n L
only for it to be worse"*. He was right — live realised peaked at +$9.50 on
1-Aug and sits at +$1.47, and the go-live gate calls 💸 the Farmer's horizon
`unreachable`. His call was to leave that book and work the winner instead.

🔮 georgia IS the winner in waiting: **5 of 6 go-live bars, failing only `t`
(1.48 against 2.0)**, n=163, +0.163%/trade. The only bar she fails is the one
that CLOSES fix, so anything that costs her closes for no quality reason is
costing real money's arrival date.

WHAT WAS MEASURED FIRST, and it refused two explanations before finding one:

  * NOT slot-starved by signal. Driving the SHIPPED `DayTraderGated.signals`
    over the venue's own 15m tape (23 coins x 1400 bars) gives **597 entry
    signals in 14.6 days = 40.9/day** against her 4.53 opens/day.
  * NOT the fleet budget (long_n 12 of 20, light green, nothing at the symbol
    cap), NOT the brain (no mult, no gate, no action on her), NOT the candle
    cache (`parse_candles` drops the forming bar and `next_due` is one interval
    after the next close — correct), and NOT a code regression: her signal rate
    went 1-29/day through 7-18 Aug and 107/164/154 on 19/20/21 Aug as the tape
    started trending, and her opens tracked it 1-6/day -> 10-17/day. **The
    surge is the market.**
  * The StoplossGuard locks her for 8.2% of her life (37 fires in 39.9 days) —
    real, but not the constraint.

THE FINDING. Ranking her real entries by position within their own clock hour:

    entry #1 of the hour   n=127   +0.023%/trade   t=+0.21   $ +3.95
    entry #2 of the hour   n= 36   +0.656%/trade   t=+2.20   $+11.90

**75% of her realised P&L is on 22% of her trades, and they are the ones
`MAX_ENTRIES_PER_HOUR = 2` is closest to refusing.** She hit the cap in 34
hours; rank 3 has n=1 in her whole life *because the cap is 2*.

SIX SPLITS, ALL THE SAME SIGN (this file recomputes every one):
    surge days (>=08-19)  +0.608pp    before them        +0.390pp
    first half of life    +0.480pp    second half        +0.756pp
    within trend_breakout +0.614pp    within range_on    +0.738pp

Both chronological halves positive is the (I19) bar for an expand-direction
change, met on her OWN ledger — the record, which outranks any proxy (I14).

THE MECHANISM IS A REGIME MARKER, NOT AN ORDERING EFFECT, and that is why it
should generalise: a second entry inside one hour means several coins fired at
once, which is what a real trending burst looks like, and `trend_breakout` is
built to catch exactly that. She does not RANK candidates — she walks `b.coins`
in list order — so #1 vs #2 carries no quality ordering of its own.

DECLARED LIMIT: everything above rank 2 is extrapolation, because the cap
censored its own evidence. That is why (sv) ships 2 -> 3 rather than removing
the cap, and why `entry_rank` is recorded from the same commit (I23) so the
next step is graded from a query instead of another reconstruction.

Read-only: reads the public /trades.json. Touches no bot, no lever, no ledger.

Usage:
  python3 scripts/study_georgia_entry_rank_2026-08-22.py
  python3 scripts/study_georgia_entry_rank_2026-08-22.py --bot freqtrade-georgia-lshadow
  python3 scripts/study_georgia_entry_rank_2026-08-22.py --selftest
"""
import argparse
import collections
import datetime as dt
import json
import math
import statistics as st
import urllib.request

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
SURGE_FROM = "2026-08-19"


def tstat(v):
    if len(v) < 2:
        return float("nan")
    m, s = st.mean(v), st.stdev(v)
    return m / (s / math.sqrt(len(v))) if s else float("nan")


def fetch(bot, limit=5000):
    url = f"{DASH}/trades.json?source=paper&bot={bot}&limit={limit}"
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.loads(r.read()).get("trades") or []


def rank_rows(trades):
    """Each close, tagged with the rank of its OPEN within its clock hour.

    The rank is reconstructed from `opened_at` because nothing recorded it
    until (sv). Once the live books have republished, read `extra.entry_rank`
    instead and this reconstruction becomes a cross-check rather than the
    source — which is the whole point of recording it."""
    def P(s):
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    rows, bucket = [], collections.Counter()
    for x in sorted(trades, key=lambda z: P(z["opened_at"])):
        h = int(P(x["opened_at"]) // 3600)
        bucket[h] += 1
        stamped = ((x.get("extra") or {}).get("entry_rank"))
        rows.append({"rank": bucket[h], "stamped": stamped,
                     "pct": (x.get("pnl_pct") or 0) * 100,
                     "usd": x.get("pnl_abs") or 0.0,
                     "day": str(x["opened_at"])[:10],
                     "tag": str(x.get("reason") or "").split("_")[0]})
    return rows, bucket


def split(rows, label, out=print):
    a = [r["pct"] for r in rows if r["rank"] == 1]
    b = [r["pct"] for r in rows if r["rank"] >= 2]
    if not a or not b:
        out(f"  {label:28s} (too thin: n1={len(a)} n2={len(b)})")
        return None
    d = st.mean(b) - st.mean(a)
    out(f"  {label:28s} #1 n={len(a):3d} {st.mean(a):+7.3f} t={tstat(a):+6.2f}"
        f"  |  #2+ n={len(b):3d} {st.mean(b):+7.3f} t={tstat(b):+6.2f}"
        f"  |  delta {d:+7.3f}pp")
    return d


def _selftest():
    """Drive the reconstruction, never a hand-written expectation of it."""
    def mk(op, pct):
        return {"opened_at": op, "pnl_pct": pct / 100.0, "pnl_abs": pct,
                "reason": "long-x_roi"}
    # pct chosen so #2+ beats #1 by a KNOWN amount — a fixture whose delta is
    # zero would pass an `is not None` check while proving nothing about the
    # statistic (the first draft of this selftest did exactly that).
    tr = [mk("2026-08-01T10:00:00+00:00", 1.0),    # rank 1
          mk("2026-08-01T10:30:00+00:00", 5.0),    # rank 2
          mk("2026-08-01T10:59:00+00:00", 6.0),    # rank 3
          mk("2026-08-01T11:01:00+00:00", 2.0)]    # rank 1 (new hour)
    rows, bucket = rank_rows(tr)
    assert [r["rank"] for r in rows] == [1, 2, 3, 1], [r["rank"] for r in rows]
    assert max(bucket.values()) == 3
    # the clock hour is the bucket, not a rolling window: 10:59 and 11:01 are
    # 2 minutes apart and belong to DIFFERENT hours, exactly as throttle_ok
    # (`int(now // 3600)`) treats them.
    assert rows[3]["rank"] == 1, "the bucket must be the clock hour"
    d = split(rows, "selftest", out=lambda *_: None)
    #  #1 = [1.0, 2.0] -> 1.5 ;  #2+ = [5.0, 6.0] -> 5.5 ;  delta = +4.0
    assert d is not None and abs(d - 4.0) < 1e-9, d
    # a stamped rank rides through untouched, so the cross-check is possible
    tr[0]["extra"] = {"entry_rank": 9}
    assert rank_rows(tr)[0][0]["stamped"] == 9
    assert rank_rows([])[0] == []
    print("study_georgia_entry_rank self-test: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default="freqtrade-georgia-lshadow")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    tr = fetch(a.bot)
    if not tr:
        print(f"no trades for {a.bot} — nothing to say (fail-closed)")
        return
    rows, bucket = rank_rows(tr)
    print(f"\n{a.bot}: n={len(rows)}  "
          f"{rows[0]['day']} -> {rows[-1]['day']}")
    stamped = sum(1 for r in rows if r["stamped"] is not None)
    print(f"  entry_rank STAMPED on {stamped} of {len(rows)} rows "
          f"({'(sv) has republished — prefer the stamp' if stamped else 'pre-(sv): reconstructed from open timestamps'})")

    print("\nBY RANK WITHIN ITS CLOCK HOUR")
    agg, usd = collections.defaultdict(list), collections.defaultdict(float)
    for r in rows:
        agg[r["rank"]].append(r["pct"])
        usd[r["rank"]] += r["usd"]
    for k in sorted(agg):
        v = agg[k]
        print(f"  entry #{k}: n={len(v):4d}  mean={st.mean(v):+7.3f}%  "
              f"t={tstat(v):+6.2f}  $={usd[k]:+8.2f}  "
              f"win={100*sum(1 for p in v if p > 0)/len(v):5.1f}%")
    hrs = collections.Counter(bucket.values())
    print(f"  hours by entry count: {dict(sorted(hrs.items()))}")

    print("\nCONTROLS — a single split proves nothing; these are the ones that "
          "could have killed it")
    split([r for r in rows if r["day"] >= SURGE_FROM], f"surge days >={SURGE_FROM}")
    split([r for r in rows if r["day"] < SURGE_FROM], "before the surge")
    half = len(rows) // 2
    split(rows[:half], "first half of her life")
    split(rows[half:], "second half")
    for t in sorted({r["tag"] for r in rows}):
        sel = [r for r in rows if r["tag"] == t]
        if len(sel) >= 12:
            split(sel, f"within {t}")

    u1 = sum(r["usd"] for r in rows if r["rank"] == 1)
    u2 = sum(r["usd"] for r in rows if r["rank"] >= 2)
    n1 = sum(1 for r in rows if r["rank"] == 1)
    print(f"\nDOLLARS  rank #1 {u1:+.2f} over {n1} trades  |  "
          f"rank #2+ {u2:+.2f} over {len(rows)-n1} trades  |  "
          f"book {u1+u2:+.2f}")
    if u1 + u2:
        print(f"  rank #2+ is {100*u2/(u1+u2):.0f}% of the book's P&L on "
              f"{100*(len(rows)-n1)/len(rows):.0f}% of its trades")


if __name__ == "__main__":
    main()
