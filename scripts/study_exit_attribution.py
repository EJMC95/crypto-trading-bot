#!/usr/bin/env python3
"""study_exit_attribution.py — attribute every book's P&L to its EXIT REASON.

WHY (2026-07-30, operator: "optimise and enhance exits on all bots so they are
able to open and close as efficiently as our infrastructure and ecosystem").

Entries in this fleet have levers, adaptive gates, a scout, a tuner and a brain.
Exits have constants. Before changing any of them, one question has to be
answered with data rather than intuition: **which exit reason is making the
money, and which is losing it?**

Every close in the paper ledger carries its exit reason — either in `reason` or
as the suffix of the `<side>-<lens>_<exit>` tag the taker and the Parliament
stamp. So the attribution already exists in the data; nothing in the repo was
reading it. This does.

WHAT IT ANSWERS, per (book, exit_reason): n, total $, mean %, win %, and the
MEDIAN HOLD. The hold column is the one that turns a table into a diagnosis —
two exit reasons on the same book with a 10x hold difference are not two rules,
they are one rule firing before the other can.

FIRST RUN, 2026-07-30, on 1,683 ledger rows (20 living books; 9 RETIRED rows
excluded — the ledger is history, and a Kraken-era book measured +$272.09, the
largest single line in it). Findings no amount of code reading would produce:

  1. 🌾 YIELD HARVESTER — the fleet's best book (t=2.58, +$61.12) earns through
     `*_decay_paid`: **n=25, +$71.42**, ~100% win, median hold 65-70h. It loses
     through the SIDED flips `short_flip`/`long_flip`: **n=47, -$17.32**, 14%
     and 0% win, median hold 6-10h. So more than half its trades exit via a
     rule that loses, in a tenth of the time the winning rule takes.
     (Precision matters here: a THIRD, unsided `flip` bucket of n=10 is
     +$7.02 — "flip loses" is only true of the sided ones, and stating it
     loosely would misdirect the fix.)

  2. THE STOP IS THE FLEET'S DOMINANT LOSS MECHANISM.
     Ticket Taker shadow: `*_sl` **n=28, -$37.32** against `*_tp` n=73,
     +$47.65 — which is how that book holds positive DOLLARS (+$6.92) and a
     NEGATIVE mean per trade at the same time. pm-gillard: `*_sl` **n=78,
     -$21.11 at a 0% win rate and a 15-19 MINUTE median hold**. A stop that
     never wins and fires inside 20 minutes is inside the book's own noise —
     harvesting, not protecting. `*_sl` at 0% win on n>=5 appears on SEVEN
     living books.

  3. THE HOLD RATIO SORTS THE FLEET (see hold_ratio()). Bucketing the 20
     living books by top-earner-hold / top-loser-hold:
         ratio >= 3 (winner runs) : n=4, net +$62.67, 3/4 profitable
         ratio ~ 1 (symmetric)    : n=5, net  -$2.77, 1/5 profitable
         SINGLE EXIT (no ladder)  : n=4, net -$12.90, 0/4 profitable
     STATE THE LIMIT HONESTLY: the first bucket is +$61.12 carry plus three
     tiny books, so "winners running" is suggestive, not proven — reading it
     as proven would repeat the single-book-drives-the-result error this repo
     has already made three times. The SINGLE-EXIT result is the robust one,
     because it is structural rather than statistical: a book with exactly one
     exit reason has no ladder at all, and none of the four is profitable
     (sniper, crypto-swing-daily, freqtrade-dad, crypto-breakout-4h — the last
     two close ONLY via `long-breakout_donchian_breakdown`, and no take-profit
     has ever fired on either).

READ-ONLY. Measures and prints; changes no gate, writes no lever. Its output is
the EVIDENCE an exit change needs under "never modify bot logic without
backtesting first" — it is not itself permission to make one.

Usage:
  python3 scripts/study_exit_attribution.py                  # live endpoints
  python3 scripts/study_exit_attribution.py --book carry      # substring filter
  python3 scripts/study_exit_attribution.py --json out.json   # machine-readable
  python3 scripts/study_exit_attribution.py --selftest        # offline
"""
import argparse
import json
import os
import statistics as st
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")
#: The default page is 500 rows, which TRUNCATES the tape — carry alone has 82
#: closes and the fleet has 1,680. An attribution computed on a truncated tape
#: is worse than none, because the truncation is not random: it drops the
#: OLDEST closes, which is exactly the half a both-halves reading needs.
LIMIT = int(os.environ.get("EXIT_STUDY_LIMIT", "5000"))
#: Below this, a per-reason row is reported but never called a finding.
MIN_N = int(os.environ.get("EXIT_STUDY_MIN_N", "5"))


def fetch_trades(limit=None, url=None):
    """The paper ledger, newest-first. Returns [] on any trouble — a study
    that cannot reach the endpoint must say "no data", never invent it."""
    u = f"{url or DASH}/trades.json?source=paper&limit={limit or LIMIT}"
    try:
        with urllib.request.urlopen(u, timeout=45) as r:
            d = json.loads(r.read().decode())
    except Exception as e:      # noqa: BLE001
        print(f"could not fetch {u}: {type(e).__name__}: {e}", file=sys.stderr)
        return []
    rows = d if isinstance(d, list) else (d.get("trades") or d.get("rows") or [])
    # [2026-08-05 (kf)] APPLY THE LEDGER QUARANTINE. `/trades.json` serves the
    # ledger UNFILTERED, so this study read the 44 rows `(hr)` withholds from
    # grading — the BOT/USDC and CXMT/USDC basis defect, where a mark sitting
    # ~747bps off its own book top made a short read as instantly +7.5% in
    # profit, tripped `tp`, and closed at a loss 43 times in 4.5 hours. ONE
    # episode, not 43 trades.
    #
    # It inverted this study's largest exit row on the shadow Taker: raw it
    # reads as a 42.6%-win 4.8-MINUTE take-profit (a rule firing far too early),
    # clean it is a 96.0%-win 8.97h take-profit — the book's single best
    # mechanism. An exit pass reading the raw number would have tightened the
    # one rule that works.
    #
    # Fail-OPEN, matching `is_quarantined`'s own contract: if the store cannot
    # be imported the rows pass through, because a study that silently drops
    # its input is worse than one that reports too much.
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        from bot_pnl_store import is_quarantined
    except Exception:      # noqa: BLE001
        return rows
    keep, dropped = [], 0
    for r in rows:
        try:
            if is_quarantined(r.get("bot"), r.get("pair"),
                              r.get("closed_at") or r.get("close_ts")):
                dropped += 1
                continue
        except Exception:  # noqa: BLE001
            pass
        keep.append(r)
    if dropped:
        print(f"ledger quarantine: {dropped} row(s) withheld — real trades, "
              f"not admissible evidence (see LEDGER_QUARANTINE)",
              file=sys.stderr)
    return keep


def retired_rows():
    """The RETIRED set, from the same single source that prunes them
    (`cleanup_legacy_bots.LEGACY_BOTS`) — the pattern `golive_readiness` uses.

    This matters more here than anywhere else, because the paper ledger is
    HISTORY: it still carries Kraken-era and pre-LIGHTER-ONLY books, and their
    numbers are large enough to dominate any ranking. First run measured
    `perps-donchian-breakout` at **+$272.09** and `equities-momentum-lshadow`
    at **-$91.90** — the two biggest lines in the whole attribution, both from
    books that have not traded since 12/17-Jul. Reading a live exit rule off
    them would be reading another venue's tape.

    Fails OPEN (empty set) if the import fails: better to show a retired book
    clearly labelled than to hide a living one.
    """
    try:
        from cleanup_legacy_bots import LEGACY_BOTS
        return set(LEGACY_BOTS)
    except Exception:      # noqa: BLE001
        return set()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _iso(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def hold_hours(row):
    """Hold in hours, or None. Both timestamps must parse — a half-parsed
    duration would silently become a tiny hold and drag the median toward
    'this exit fires instantly', which is the exact conclusion this column
    exists to support or refute."""
    a, b = _iso(row.get("opened_at")), _iso(row.get("closed_at"))
    if a is None or b is None:
        return None
    h = (b - a).total_seconds() / 3600.0
    return h if h >= 0 else None


def exit_reason(row):
    """The exit reason for one close.

    Two dialects in one ledger, which is why this is a named function rather
    than an inline expression:
      * `reason` — the funding/dislocation/index bots write it directly
        (`short_decay_paid`, `long_max_hold`, `short_rebalance`).
      * the `<side>-<lens>_<exit>` TAG — the taker and the Parliament encode
        the exit in the tag's suffix (`short-divergence_tp`, `long-burst_sl`).
    Prefer `reason`; fall back to the tag. An unlabelled close is returned as
    "?" and NOT silently dropped — an exit nobody tagged is itself a finding
    (it is ungradeable by the brain's lens-forward layer).
    """
    r = str(row.get("reason") or "").strip()
    if r:
        return r
    tag = str(row.get("tag") or "").strip()
    if not tag:
        return "?"
    return tag.rsplit("_", 1)[-1] if "_" in tag else tag


def attribute(rows, min_n=None, retired=None):
    """{book: {reason: stats}} plus a per-book roll-up. Pure — selftested.

    `retired` is injectable so the selftest never depends on the live retired
    list; production passes `retired_rows()`.
    """
    min_n = MIN_N if min_n is None else min_n
    retired = set() if retired is None else set(retired)
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if not isinstance(r, dict):
            continue
        per[str(r.get("bot"))][exit_reason(r)].append(r)

    out = {}
    for bot, reasons in per.items():
        book = {"reasons": {}, "n": 0, "total_usd": 0.0}
        for reason, g in reasons.items():
            pcts = [p for p in (_num(x.get("pnl_pct")) for x in g) if p is not None]
            abss = [a for a in (_num(x.get("pnl_abs")) for x in g) if a is not None]
            hs = [h for h in (hold_hours(x) for x in g) if h is not None]
            tot = sum(abss)
            book["reasons"][reason] = {
                "n": len(g),
                "total_usd": round(tot, 2),
                "mean_pct": round(100 * st.mean(pcts), 3) if pcts else None,
                "win_pct": round(100 * sum(1 for a in abss if a > 0) / len(abss), 1)
                           if abss else None,
                "median_hold_h": round(st.median(hs), 2) if hs else None,
                "gradeable": len(g) >= min_n,
            }
            book["n"] += len(g)
            book["total_usd"] = round(book["total_usd"] + tot, 2)
        # the two rankings that make this actionable
        rs = book["reasons"]
        earners = sorted((k for k in rs if rs[k]["total_usd"] > 0),
                         key=lambda k: -rs[k]["total_usd"])
        losers = sorted((k for k in rs if rs[k]["total_usd"] < 0),
                        key=lambda k: rs[k]["total_usd"])
        book["top_earner"] = earners[0] if earners else None
        book["top_loser"] = losers[0] if losers else None
        book["earned_usd"] = round(sum(rs[k]["total_usd"] for k in earners), 2)
        book["lost_usd"] = round(sum(rs[k]["total_usd"] for k in losers), 2)
        # SINGLE-EXIT BOOKS: a book with exactly one reason has no exit
        # ladder at all — whatever that reason does IS its entire result.
        book["single_exit"] = len(rs) == 1
        # HISTORY, not a live exit rule — see retired_rows().
        book["retired"] = bot in retired
        out[bot] = book
    return out


def hold_ratio(book):
    """median hold of the top EARNER / median hold of the top LOSER, or None.

    The single most diagnostic number this study produces. A ratio well above 1
    means the losing exit fires MUCH sooner than the winning one — i.e. it is
    cutting positions before the book's thesis has time to pay. 🌾 carry
    measured ~6.6x on first run (decay_paid ~65-70h vs flip ~6-10h), which is
    the finding that reframed its whole exit question.
    """
    rs = book.get("reasons") or {}
    e, l = book.get("top_earner"), book.get("top_loser")
    if not e or not l:
        return None
    he, hl = rs[e].get("median_hold_h"), rs[l].get("median_hold_h")
    if not he or not hl or hl <= 0:
        return None
    return round(he / hl, 2)


def render(attr, book_filter=None, min_n=None, show_retired=False):
    min_n = MIN_N if min_n is None else min_n
    books = sorted(attr, key=lambda b: -(attr[b]["total_usd"]))
    n_ret = sum(1 for b in books if attr[b].get("retired"))
    if not show_retired:
        books = [b for b in books if not attr[b].get("retired")]
    if book_filter:
        books = [b for b in books if book_filter.lower() in b.lower()]
    print(f"EXIT ATTRIBUTION — which exit reason makes the money, and which loses it")
    print(f"(median hold is the diagnostic column: a losing exit that fires much "
          f"sooner than\n the winning one is cutting the thesis short, not "
          f"protecting it)\n")
    for bot in books:
        b = attr[bot]
        hr = hold_ratio(b)
        flags = []
        if b["single_exit"]:
            flags.append("SINGLE EXIT — no ladder")
        if hr and hr >= 3.0:
            flags.append(f"earner holds {hr}x longer than loser")
        if "?" in b["reasons"]:
            flags.append(f"{b['reasons']['?']['n']} UNTAGGED closes")
        head = f"{bot}  net {b['total_usd']:+.2f}  (n={b['n']})"
        print(head)
        if flags:
            print("   ! " + " · ".join(flags))
        print(f"   {'exit reason':26s} {'n':>4s} {'total$':>8s} {'mean%':>8s} "
              f"{'win%':>6s} {'hold':>8s}")
        for reason in sorted(b["reasons"], key=lambda k: b["reasons"][k]["total_usd"]):
            s = b["reasons"][reason]
            mark = " " if s["gradeable"] else "·"
            mp = f"{s['mean_pct']:+.3f}" if s["mean_pct"] is not None else "—"
            wp = f"{s['win_pct']:.0f}%" if s["win_pct"] is not None else "—"
            hh = f"{s['median_hold_h']:.1f}h" if s["median_hold_h"] is not None else "—"
            print(f"  {mark}{reason:26s} {s['n']:>4d} {s['total_usd']:>+8.2f} "
                  f"{mp:>8s} {wp:>6s} {hh:>8s}")
        print()
    print(f"· = fewer than {min_n} closes: reported, not a finding.")
    if n_ret and not show_retired:
        print(f"{n_ret} RETIRED book(s) hidden (--retired to show). They are "
              f"HISTORY: the ledger still carries Kraken-era rows whose numbers "
              f"dominate any ranking.")
    print("READ-ONLY. This is the evidence an exit change needs, not permission "
          "to make one.")


def _selftest():
    # A book whose LOSING exit fires fast and whose WINNING exit holds — the
    # carry shape, which is the pattern the whole study exists to surface.
    rows = []
    for i in range(20):
        rows.append({"bot": "b1", "reason": "decay_paid", "pnl_abs": 3.0,
                     "pnl_pct": 0.01,
                     "opened_at": "2026-07-01T00:00:00+00:00",
                     "closed_at": "2026-07-03T18:00:00+00:00"})     # 66h
    for i in range(40):
        rows.append({"bot": "b1", "reason": "flip", "pnl_abs": -1.0,
                     "pnl_pct": -0.004,
                     "opened_at": "2026-07-01T00:00:00+00:00",
                     "closed_at": "2026-07-01T10:00:00+00:00"})     # 10h
    a = attribute(rows, min_n=5)["b1"]
    assert a["n"] == 60 and a["total_usd"] == 20.0, a
    assert a["top_earner"] == "decay_paid" and a["top_loser"] == "flip", a
    assert a["earned_usd"] == 60.0 and a["lost_usd"] == -40.0, a
    assert a["reasons"]["decay_paid"]["win_pct"] == 100.0
    assert a["reasons"]["flip"]["win_pct"] == 0.0
    assert a["reasons"]["decay_paid"]["median_hold_h"] == 66.0, a
    assert hold_ratio(a) == 6.6, hold_ratio(a)      # 66 / 10
    assert not a["single_exit"]

    # TAG dialect: the exit is the suffix, and `reason` wins when both exist.
    tagged = [{"bot": "b2", "tag": "short-divergence_tp", "pnl_abs": 1.0,
               "pnl_pct": 0.01},
              {"bot": "b2", "tag": "long-dip_sl", "pnl_abs": -1.0,
               "pnl_pct": -0.01},
              {"bot": "b2", "tag": "long-dip_sl", "reason": "explicit_wins",
               "pnl_abs": 0.5, "pnl_pct": 0.005}]
    b2 = attribute(tagged, min_n=1)["b2"]["reasons"]
    assert set(b2) == {"tp", "sl", "explicit_wins"}, b2

    # SINGLE-EXIT detection — crypto-breakout-4h's real shape.
    solo = attribute([{"bot": "b3", "reason": "donchian", "pnl_abs": -1.0,
                       "pnl_pct": -0.02}], min_n=1)["b3"]
    assert solo["single_exit"] is True and solo["top_earner"] is None
    assert hold_ratio(solo) is None, "no ratio without both sides"

    # An UNTAGGED close must survive as "?" rather than vanish — an exit
    # nobody labelled is ungradeable by the brain and must stay visible.
    q = attribute([{"bot": "b4", "pnl_abs": -1.0, "pnl_pct": -0.01}], min_n=1)
    assert "?" in q["b4"]["reasons"], q

    # Junk must not raise, and must not fabricate: unparseable timestamps give
    # NO hold rather than a zero hold (a zero would read as "fires instantly").
    j = attribute([{"bot": "b5", "reason": "x", "pnl_abs": "junk",
                    "pnl_pct": None, "opened_at": "nope",
                    "closed_at": "also-nope"}], min_n=1)["b5"]
    assert j["reasons"]["x"]["median_hold_h"] is None
    assert j["reasons"]["x"]["mean_pct"] is None
    assert j["reasons"]["x"]["win_pct"] is None
    # a close_ts BEFORE the open_ts is corrupt, not a negative hold
    neg = attribute([{"bot": "b6", "reason": "x", "pnl_abs": 1.0, "pnl_pct": 0.01,
                      "opened_at": "2026-07-02T00:00:00+00:00",
                      "closed_at": "2026-07-01T00:00:00+00:00"}], min_n=1)["b6"]
    assert neg["reasons"]["x"]["median_hold_h"] is None
    assert attribute([], min_n=1) == {}
    assert attribute([None, "junk", 7], min_n=1) == {}

    # RETIRED books are LABELLED, never silently dropped or recomputed — the
    # ledger is history and a Kraken-era row measured +$272.09 on first run,
    # the largest line in the fleet, from a book that has not traded since
    # 12-Jul. Labelling is the render layer's business; the numbers must be
    # identical either way, or the flag would be quietly changing the maths.
    ret = attribute(rows, min_n=5, retired={"b1"})["b1"]
    assert ret["retired"] is True
    assert ret["total_usd"] == a["total_usd"] and ret["n"] == a["n"]
    assert attribute(rows, min_n=5)["b1"]["retired"] is False

    print("study_exit_attribution selftest OK (carry shape + hold ratio, tag "
          "dialect, single-exit, untagged, junk/negative holds)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--book", help="substring filter on the row name")
    ap.add_argument("--limit", type=int, default=LIMIT)
    ap.add_argument("--min-n", type=int, default=MIN_N)
    ap.add_argument("--retired", action="store_true",
                    help="include RETIRED books (history; excluded by default)")
    ap.add_argument("--json", help="write the attribution to this path")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    rows = fetch_trades(limit=a.limit)
    if not rows:
        print("no ledger rows — nothing to attribute.")
        return
    print(f"{len(rows)} ledger rows\n")
    attr = attribute(rows, min_n=a.min_n, retired=retired_rows())
    render(attr, book_filter=a.book, min_n=a.min_n, show_retired=a.retired)
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"rows": len(rows), "books": attr}, f, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
