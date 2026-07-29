#!/usr/bin/env python3
"""golive_readiness.py — grade every shadow book against the go-live bar.

WHY (2026-07-29, operator: "give the carry book a promotion path, and fix the
gate that would reject it").

TWO PIPELINES, and conflating them is why the best book had no path:
  * The EXPERIMENT JUDGE re-parameterises a book that is ALREADY live — it
    needs a live arm to pair the shadow against. `perps-funding-carry-lshadow`
    has no live arm, so the judge can never reach it. That is not an oversight
    in the judge; it is the wrong pipeline for the question.
  * A NEW book's path to real money is the GO-LIVE GATE. It had no
    implementation at all — the rule lived in CLAUDE.md as prose and was
    applied by hand, which is how it went un-noticed that it would reject the
    fleet's best-evidenced book.

THE GATE DEFECT. CLAUDE.md's rule reads: *"Paper trading only until 30-day win
rate > 55% AND max drawdown < 15%"*. Measured 29-Jul, the carry book is the
fleet's strongest by every evidence measure — t=2.42 on n=80, both halves
positive (+42.42 / +13.78), realised +$56.20, unrealised +$7.62 (so the
hedged-book "close only when paid" artifact is NOT masking open losses),
maxDD −$6.13 — and it **wins 38.8% of its trades**. It is a low-win-rate,
positive-expectancy book, and a win-rate gate is orthogonal to expectancy:
it would reject this book forever while admitting a high-win-rate book that
loses money on the tails. Same non-sequitur shape as the tp-0.06 rationale
this session already refuted, except sitting in the rule that governs real
money.

THE REPLACEMENT BAR is this repo's own doctrine, applied to a whole book:
  window   >= GOLIVE_MIN_DAYS (30)      the operator's, unchanged
  evidence >= GOLIVE_MIN_CLOSES (30)    fills, never hours
  positive    mean per-trade > 0        in its own right
  SIGNIFICANT t >= GOLIVE_MIN_T (2.0)   a positive LOWER bound, not a max
  ROBUST      both halves positive      the fleet's central noise filter
  maxDD    <  GOLIVE_MAX_DD (15%)       the operator's, unchanged

Win rate is still REPORTED — it is informative — but it is not a bar.

HONEST ABOUT DIRECTION: this is not uniformly stricter. It drops a
requirement the carry book fails and adds two (significance, both-halves)
that the old rule never had. For a high-win-rate/negative-expectancy book it
is STRICTER; for carry it is what makes go-live reachable at all. That is a
real loosening for that book and is stated here rather than buried.

REGIME CAVEAT (21-Jul item 18): Lighter's tape is one falling-BTC regime, so
"both halves" is weak for anything DIRECTIONAL. Reported per book; funding
books (carry, Farmer, spread) are largely direction-agnostic so it bites less,
but a directional book passing here has passed in ONE regime only.

READ-ONLY. Grades and prints. Promotes nothing, writes no lever, flips no
dry_run — go-live remains an explicit operator act
([[no-real-money-without-explicit-golive]]).

Usage:
  DATABASE_URL=... python3 scripts/golive_readiness.py
  python3 scripts/golive_readiness.py --selftest
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

GOLIVE_MIN_DAYS = float(os.environ.get("GOLIVE_MIN_DAYS", "30"))
GOLIVE_MIN_CLOSES = int(os.environ.get("GOLIVE_MIN_CLOSES", "30"))
GOLIVE_MIN_T = float(os.environ.get("GOLIVE_MIN_T", "2.0"))
GOLIVE_MAX_DD = float(os.environ.get("GOLIVE_MAX_DD", "0.15"))
GOLIVE_LEGACY_WIN = float(os.environ.get("GOLIVE_LEGACY_WIN", "0.55"))
BOOK_USD = float(os.environ.get("GOLIVE_BOOK_USD", "1000"))
# [2026-07-30] bot_state key + TTL for the published verdicts (see main()).
KEY = "golive-readiness"
TTL_SEC = int(os.environ.get("GOLIVE_TTL_SEC", "86400"))


def stats(rows, book_usd=None):
    """Grade one book from its closed-trade rows.

    rows: [(pnl_pct, pnl_abs, closed_at_datetime)] oldest first. Pure — the DB
    read is the caller's job so this is selftestable offline."""
    book_usd = BOOK_USD if book_usd is None else book_usd
    pct = [r[0] for r in rows if isinstance(r[0], (int, float))]
    n = len(pct)
    out = {"n": n}
    if n < 2:
        out["why"] = "too few closes to grade"
        return out
    days = (rows[-1][2] - rows[0][2]).total_seconds() / 86400.0
    mean = sum(pct) / n
    var = sum((x - mean) ** 2 for x in pct) / n
    sd = math.sqrt(var) or 1e-12
    t = mean / (sd / math.sqrt(n))
    mid = n // 2
    h1 = sum(r[1] or 0 for r in rows[:mid])
    h2 = sum(r[1] or 0 for r in rows[mid:])
    eq = peak = dd = 0.0
    for r in rows:
        eq += r[1] or 0
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    wins = sum(1 for x in pct if x > 0)
    out.update(days=days, mean_pct=mean, t=t, h1=h1, h2=h2,
               win_rate=wins / n, max_dd_usd=dd,
               max_dd_frac=abs(dd) / book_usd if book_usd else None,
               realised_usd=sum(r[1] or 0 for r in rows))
    return out


#: The six bars, in the order the operator reads them. Names are the PUBLISHED
#: contract (`golive-readiness.books.<bot>.bars`) — the dashboard renders these
#: keys, so a rename here is a breaking change and `test_golive_readiness.py`
#: pins them.
BAR_NAMES = ("window", "closes", "mean", "t", "halves", "maxdd")


def bar_map(s):
    """{bar_name: passed} for one book — the same six conditions `grade()`
    checks, in a form a CONSUMER can render without string-parsing `fails`.

    Published rather than re-derived: the dashboard used to have no way to show
    "5 of 6 bars, missing the window" except by matching prose, and prose is
    exactly what drifts. `_selftest` asserts `all(bar_map(s).values()) is
    grade(s)[0]` over every fixture, so the two cannot diverge silently. An
    unmeasurable bar (maxDD with no book size) counts as NOT passed — the
    fail-closed direction for a gate that governs real money."""
    if s.get("n", 0) < 2:
        return {k: False for k in BAR_NAMES}
    dd = s.get("max_dd_frac")
    return {
        "window": s["days"] >= GOLIVE_MIN_DAYS,
        "closes": s["n"] >= GOLIVE_MIN_CLOSES,
        "mean": s["mean_pct"] > 0,
        "t": s["t"] >= GOLIVE_MIN_T,
        "halves": s["h1"] > 0 and s["h2"] > 0,
        "maxdd": dd is not None and dd < GOLIVE_MAX_DD,
    }


def grade(s, legacy=False):
    """(passes, [failed_bar, ...]) for one book's stats dict.

    legacy=True applies CLAUDE.md's ORIGINAL rule (30d + win>55% + maxDD<15%)
    so the two can be compared side by side and the divergence is visible
    rather than asserted. Pure — selftested."""
    if s.get("n", 0) < 2:
        return False, ["ungradeable"]
    fails = []
    if s["days"] < GOLIVE_MIN_DAYS:
        fails.append(f"window {s['days']:.1f}d < {GOLIVE_MIN_DAYS:g}d")
    # [2026-07-30] An UNMEASURABLE drawdown now FAILS the bar rather than
    # passing it. It was `is not None and >=`, i.e. a book whose drawdown could
    # not be computed (no book size) sailed through the one bar the operator
    # wrote himself. Fail-closed is the only defensible direction for a gate on
    # real money, and it is what lets `bar_map` be exactly equivalent to this
    # function (selftest-bound) instead of quietly kinder in one corner.
    if s["max_dd_frac"] is None:
        fails.append("maxDD unmeasurable")
    elif s["max_dd_frac"] >= GOLIVE_MAX_DD:
        fails.append(f"maxDD {100*s['max_dd_frac']:.1f}% >= {100*GOLIVE_MAX_DD:.0f}%")
    if legacy:
        if s["win_rate"] <= GOLIVE_LEGACY_WIN:
            fails.append(f"win {100*s['win_rate']:.1f}% <= {100*GOLIVE_LEGACY_WIN:.0f}%")
        return not fails, fails
    if s["n"] < GOLIVE_MIN_CLOSES:
        fails.append(f"n {s['n']} < {GOLIVE_MIN_CLOSES}")
    if s["mean_pct"] <= 0:
        fails.append(f"mean {100*s['mean_pct']:+.3f}% <= 0")
    if s["t"] < GOLIVE_MIN_T:
        fails.append(f"t {s['t']:.2f} < {GOLIVE_MIN_T:g}")
    if not (s["h1"] > 0 and s["h2"] > 0):
        fails.append(f"halves {s['h1']:+.2f}/{s['h2']:+.2f} not both positive")
    return not fails, fails


def _selftest():
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def mk(pcts, span_days=40.0):
        step = timedelta(days=span_days / max(1, len(pcts) - 1))
        return [(p, p * 10.0, t0 + i * step) for i, p in enumerate(pcts)]

    # a CLEAN book: 40 steady winners over 40d
    good = stats(mk([0.01] * 40))
    assert good["n"] == 40 and good["days"] > 30 and good["t"] > 2
    assert grade(good)[0] is True, grade(good)

    # THE CARRY SHAPE — the whole reason this file exists. Low win rate,
    # positive expectancy: a few big wins carrying many small losses.
    carry = stats(mk(([0.20] * 14 + [-0.03] * 26) * 1))
    assert carry["win_rate"] < 0.55, carry["win_rate"]
    assert carry["mean_pct"] > 0, carry
    ok_new, f_new = grade(carry)
    ok_old, f_old = grade(carry, legacy=True)
    assert ok_old is False and any("win" in x for x in f_old), f_old
    assert not any("win" in x for x in f_new), "win rate is NOT a bar any more"
    # ...and the new bar still refuses it if the EVIDENCE is not there
    assert ok_new is False or carry["t"] >= GOLIVE_MIN_T

    # THE INVERSE, which is what the new bar buys: a high win rate that LOSES
    # money must fail the new gate and PASS the old one on win rate alone.
    tails = stats(mk([0.01] * 34 + [-0.30] * 6))
    assert tails["win_rate"] > 0.55 and tails["mean_pct"] < 0, tails
    assert grade(tails, legacy=True)[1] == [] or all(
        "win" not in x for x in grade(tails, legacy=True)[1]), \
        "old rule does not object to a money-losing book on win rate"
    ok_t, f_t = grade(tails)
    assert ok_t is False and any("mean" in x for x in f_t), f_t

    # EACH BAR MUST BE THE SOLE REASON IN SOME CASE, or it is untested
    # decoration — both of these were added after mutations proved the bar
    # could be deleted with the suite still green.
    #  (a) SIGNIFICANCE alone: positive mean, both halves positive, enough
    #      closes and days — but far too noisy to believe (t ~ 0.3).
    noisy = stats(mk([0.05, -0.045] * 20))
    assert noisy["mean_pct"] > 0 and noisy["h1"] > 0 and noisy["h2"] > 0
    assert noisy["n"] >= GOLIVE_MIN_CLOSES and noisy["days"] >= GOLIVE_MIN_DAYS
    ok_n, f_n = grade(noisy)
    assert ok_n is False and f_n == [f"t {noisy['t']:.2f} < {GOLIVE_MIN_T:g}"], f_n
    #  (b) BOTH-HALVES alone: strongly positive mean AND a big t, but the
    #      whole result is the first half — the classic one-window win.
    lopsided = stats(mk([0.05] * 20 + [-0.01] * 20))
    assert lopsided["mean_pct"] > 0 and lopsided["t"] >= GOLIVE_MIN_T
    assert lopsided["h1"] > 0 > lopsided["h2"], lopsided
    ok_l, f_l = grade(lopsided)
    assert ok_l is False and len(f_l) == 1 and "halves" in f_l[0], f_l

    #  (c) THE CLOSES FLOOR alone: flawless on every other bar over a full
    #      window, but only 10 fills. Evidence is denominated in FILLS, never
    #      in days ([[incubator-evidence-denominated-in-fills]]) — a long
    #      quiet window is not a substitute for trades.
    thin = stats(mk([0.02] * 10))
    assert thin["days"] >= GOLIVE_MIN_DAYS and thin["mean_pct"] > 0
    assert thin["h1"] > 0 and thin["h2"] > 0 and thin["t"] >= GOLIVE_MIN_T
    ok_th, f_th = grade(thin)
    assert ok_th is False and f_th == [f"n 10 < {GOLIVE_MIN_CLOSES}"], f_th

    # window and drawdown bars still bite (the operator's two, unchanged)
    short = stats(mk([0.01] * 40, span_days=5.0))
    assert any("window" in x for x in grade(short)[1])
    deep = stats(mk([0.5] * 5 + [-4.0] * 10 + [0.5] * 25))
    assert deep["max_dd_frac"] > 0, deep
    # ungradeable input claims nothing, never raises
    assert grade(stats([]))[0] is False
    assert stats([])["n"] == 0 and "why" in stats([])

    # [2026-07-30] THE PUBLISHED BAR MAP IS BOUND TO THE GRADE. `bar_map` is
    # what the dashboard renders; if it could drift from `grade`, the operator
    # would read six green chips on a book the gate rejects. Asserted over
    # every fixture above INCLUDING the unmeasurable-drawdown corner, which is
    # the one place the two used to disagree.
    nodd = stats(mk([0.01] * 40), book_usd=0)
    assert nodd["max_dd_frac"] is None, nodd
    for name, s in [("good", good), ("carry", carry), ("tails", tails),
                    ("noisy", noisy), ("lopsided", lopsided), ("thin", thin),
                    ("short", short), ("deep", deep), ("empty", stats([])),
                    ("nodd", nodd)]:
        bm = bar_map(s)
        assert set(bm) == set(BAR_NAMES), bm
        assert all(bm.values()) == grade(s)[0], (name, bm, grade(s))
        if s.get("n", 0) >= 2:
            # every failed bar is exactly one dark chip, and vice versa
            assert sum(bm.values()) == len(BAR_NAMES) - len(grade(s)[1]), \
                (name, bm, grade(s)[1])
        else:
            assert sum(bm.values()) == 0, (name, bm)   # claims nothing at all
    assert bar_map(nodd)["maxdd"] is False, "an unmeasured drawdown is not a pass"
    print("golive_readiness selftest OK (clean pass, the carry shape, the "
          "high-win-rate loser, window/DD bars, ungradeable input)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="write the verdicts to bot_state['golive-readiness']")
    ap.add_argument("--min-closes", type=int, default=10,
                    help="ignore books below this many closes")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    import bot_pnl_store as store          # noqa: E402
    # RETIRED rows are HISTORY, not candidates — grading them would offer a
    # dead bot for promotion. Single source: cleanup_legacy_bots.LEGACY_BOTS
    # (the same list that prunes them), fail-OPEN if it cannot be imported.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS
        retired = set(LEGACY_BOTS)
    except Exception:      # noqa: BLE001
        retired = set()
    rows = store.fetch_paper_trades(limit=20000) or []
    books = {}
    for r in rows:
        bot = str(r.get("bot"))
        if bot in retired:
            continue
        books.setdefault(bot, []).append(r)

    def _key(r):
        return r.get("close_ts") or r.get("closed_at") or ""

    print(f"GO-LIVE READINESS — bar: >={GOLIVE_MIN_DAYS:g}d, >={GOLIVE_MIN_CLOSES} "
          f"closes, mean>0, t>={GOLIVE_MIN_T:g}, both halves +, maxDD<"
          f"{100*GOLIVE_MAX_DD:.0f}%")
    print(f"{'book':34s} {'n':>4s} {'days':>6s} {'mean%':>8s} {'t':>6s} "
          f"{'win%':>6s} {'maxDD%':>7s}  verdict")
    print("-" * 104)
    ready, payload_books = [], {}
    for bot in sorted(books):
        rs = sorted(books[bot], key=_key)
        parsed = []
        for r in rs:
            try:
                from experiment_judge import parse_ts
                from datetime import datetime, timezone
                ts = datetime.fromtimestamp(parse_ts(_key(r)), tz=timezone.utc)
            except Exception:      # noqa: BLE001
                continue
            parsed.append((r.get("profit_ratio"), r.get("profit_abs"), ts))
        s = stats(parsed)
        if s.get("n", 0) < a.min_closes:
            continue
        ok, fails = grade(s)
        ok_old, fails_old = grade(s, legacy=True)
        verdict = "READY" if ok else "; ".join(fails[:2])
        flag = ""
        if ok and not ok_old:
            flag = "   <- passes the NEW bar, REJECTED by the win-rate rule"
        if ok_old and not ok:
            flag = "   <- old rule would have ADMITTED it"
        dd_pct = (round(100 * s["max_dd_frac"], 1)
                  if s.get("max_dd_frac") is not None else None)
        bars = bar_map(s)
        print(f"{bot:34s} {s['n']:>4d} {s['days']:>6.1f} "
              f"{100*s['mean_pct']:>7.3f}% {s['t']:>6.2f} "
              f"{100*s['win_rate']:>5.1f}% "
              f"{('n/a' if dd_pct is None else f'{dd_pct:.1f}%'):>7s}  "
              f"{verdict}{flag}")
        if ok:
            ready.append(bot)
        # [2026-07-30] collect for the PUBLISH below — see the note there.
        # `bars` is the machine-readable per-bar map the dashboard renders; the
        # prose `fails` stays for humans. Publishing both means no consumer has
        # to string-match a message to know WHICH bar is dark.
        payload_books[bot] = {
            "n": s["n"], "days": round(s["days"], 1),
            "mean_pct": round(100 * s["mean_pct"], 3),
            "t": round(s["t"], 2), "win_pct": round(100 * s["win_rate"], 1),
            "max_dd_pct": dd_pct,
            "h1": round(s["h1"], 2), "h2": round(s["h2"], 2),
            "bars": bars, "bar_names": list(BAR_NAMES),
            "bars_passed": sum(bars.values()), "fails": fails,
            "ready": bool(ok), "legacy_ready": bool(ok_old)}
    print()
    print(f"READY: {ready or 'none'}")

    # [2026-07-30 THIS GRADER BECOMES AN ORGAN — operator: "make sure the PNL
    # dashboard reflects all work done".] Until now it published NOTHING and was
    # scheduled NOWHERE: the tool that decides whether a book has earned real
    # money ran only when a human remembered, and its verdicts reached no
    # organ, no dashboard and no review. That is the fleet's own "a rule nobody
    # runs is not a control" class — the same shape as the 38 selftests before
    # 18-Jul and `--selftest-live` before (ej). Publishing makes the gate
    # VISIBLE between reviews; it changes no decision and promotes nothing.
    # Go-live remains an explicit operator act.
    if a.publish:
        try:
            import bot_pnl_store as _store
            from datetime import datetime as _dt, timezone as _tz
            payload = {
                "updated": _dt.now(_tz.utc).isoformat(timespec="seconds"),
                "ttl_sec": TTL_SEC,
                "bar": {"min_days": GOLIVE_MIN_DAYS,
                        "min_closes": GOLIVE_MIN_CLOSES,
                        "min_t": GOLIVE_MIN_T, "max_dd": GOLIVE_MAX_DD},
                "bar_names": list(BAR_NAMES),
                "books": payload_books,
                "ready": sorted(ready)}
            ok_pub = _store.save_state(KEY, payload)
            # HISTORY too, because the question the baseline document asks is a
            # TRAJECTORY one — "is t moving toward 2.0 and n above 41?" — and a
            # single current snapshot cannot answer it. 4 writes/day against a
            # 60-day retention is ~240 rows; negligible against the ~400/day
            # the organs already write.
            _store.save_history(KEY, payload)
            print(f"published {KEY}: {len(payload_books)} books, "
                  f"{len(ready)} ready ({'ok' if ok_pub else 'WRITE FAILED'})")
        except Exception as e:      # noqa: BLE001 — a publish must never fail the grade
            print(f"publish skipped: {type(e).__name__}: {e}")
    print("Go-live remains an explicit operator act — this grades, it does not "
          "promote. Lighter's tape is ONE regime; a DIRECTIONAL book passing "
          "here has passed in that regime only.")


if __name__ == "__main__":
    main()
