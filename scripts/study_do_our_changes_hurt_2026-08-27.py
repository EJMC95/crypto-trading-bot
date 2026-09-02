#!/usr/bin/env python3
"""WE WIN, WE CHANGE IT, IT STARTS LOSING. IS THAT US — OR IS IT THE MEAN?

**Eamon, 27-Aug: *"think broadly on how we can in some cases win, we then make
changes and it starts losing…"*** It is the most testable thing anyone has said
about this fleet, and it has FOUR candidate mechanisms that demand OPPOSITE
responses:

  1. **We damage books.** Our changes are net harmful -> change less, and gate
     every change behind a replay.
  2. **We overfit.** The change is fitted to the window that motivated it ->
     hold out before shipping.
  3. **REGRESSION TO THE MEAN.** We do not change books at random — we change
     them when we NOTICE something, and what we notice is an extreme. A book
     reverts toward its own mean afterwards whether we touched it or not, and
     the change gets the blame -> change nothing about changing; change what we
     BELIEVE about a hot streak.
  4. **Edge decay.** The edge was real and the market arbitraged it -> expect
     it, and re-measure on a rolling basis.

Telling them apart is the whole job, because (1) says do less and (3) says the
feeling is an artifact of when we look.

THREE ARMS, each designed so ONE mechanism can be separated from the others:

  `--age`      BOOK-AGE vs CALENDAR TIME. If every book decays together in
               CALENDAR time, it is the regime and not us. If a book decays in
               its OWN trade sequence regardless of when it started, that is us
               or edge decay. The same data cannot be both, so this splits (1)
               and (4) from the market.

  `--peak`     THE NO-CHANGE CONTROL, and the arm that matters most. For every
               book, find each HOT WINDOW (a run of K closes well above the
               book's own mean) and measure the NEXT K closes — **with no
               regard for whether anything was changed.** If performance after
               a hot window collapses toward the mean ANYWAY, then the
               "we changed it and it broke" pattern is mechanism (3), and
               changing less would not fix it.

  `--select`   THE SELECTION PREMIUM, measured on this fleet's own habit: pick
               the best of N candidate cells, then ask what the un-selected
               distribution looked like. Quantifies (2) in `t` units.

REPORTED, NEVER RANKED: per-trade returns here are the ledger's own `pnl_pct`,
pooled across books only where stated. A book's closes are not independent
draws — the whole fleet trades one venue — so pooled `t` is shown beside
by-book `t` and the by-book number is the honest one ((uf)).

READ-ONLY. Answers a question; changes nothing.
"""
import argparse
import collections
import datetime as dt
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

#: A book needs this many closes before its trend is worth reading at all.
MIN_N = 40
#: Hot-window length for the no-change control.
K = 15
#: [2026-09-02] a window size with fewer hot windows than this cannot grade the
#: grader's margin -- the collapse's standard error is what the grade is made of
MIN_WINDOWS = 20


def _conn():
    import bot_pnl_store as store
    return store._get_conn()


def ledger():
    """[(bot, closed_ts, pnl_pct)] for every close the fleet has, ordered.

    Timestamps go through `golive_readiness.parse_stamp`, the ONE owner —
    `closed_at` is TEXT in four different formats in this table and a
    hand-rolled parser silently drops whole books
    ([[ledger-schema-traps-kill-adhoc-sql]]).
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gl", os.path.join(HERE, "golive_readiness.py"))
    gl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gl)

    conn = _conn()
    if conn is None:
        print("no DATABASE_URL — this study needs the live ledger")
        return []
    with conn.cursor() as cur:
        cur.execute("""select bot, closed_at, pnl_pct from paper_trades
                       where pnl_pct is not null and closed_at is not null""")
        rows = cur.fetchall()
    out = []
    dropped = 0
    for bot, closed, pct in rows:
        ts = gl.parse_stamp(closed)
        if ts is None:
            dropped += 1
            continue
        # `parse_stamp` returns a datetime; normalise to epoch seconds here so
        # every downstream arm sorts and buckets on ONE representation.
        if isinstance(ts, dt.datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt.timezone.utc)
            ts = ts.timestamp()
        out.append((bot, float(ts), float(pct)))
    out.sort(key=lambda r: r[1])
    print(f"ledger: {len(out):,} closes across "
          f"{len(set(r[0] for r in out))} books"
          f"{f'  ({dropped} unparseable timestamps dropped)' if dropped else ''}")
    return out


def _grader():
    """The grader module, loaded by path (the ONE owner of `parse_stamp`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gl", os.path.join(HERE, "golive_readiness.py"))
    gl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gl)
    return gl


def load_ledger_file(path):
    """[(bot, closed_ts, pnl_pct)] from a `/trades.json?source=paper` dump.

    [2026-09-02 -- Eamon: "Calibrate accordingly"] The sandbox that re-measures
    this has no DATABASE_URL; the public feed carries the same rows the SQL in
    `ledger()` reads (`bot`, `closed_at`, `pnl_pct`), parsed through the same
    `parse_stamp`. NEITHER path applies `LEDGER_QUARANTINE` -- the study
    measures the tide on the raw ledger, as it did on 27-Aug, and says so. A
    `?limit=` count equal to the cap is a truncation ((qz)): read the printed
    count before believing it.
    """
    import json
    gl = _grader()
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    rows = raw.get("trades") if isinstance(raw, dict) else raw
    out, dropped = [], 0
    for r in rows or []:
        if not isinstance(r, dict) or r.get("pnl_pct") is None or not r.get("closed_at"):
            continue
        try:
            ts = gl.parse_stamp(r["closed_at"])
        except (ValueError, TypeError):      # a junk stamp is DROPPED and counted, never a crash
            ts = None
        if ts is None:
            dropped += 1
            continue
        if isinstance(ts, dt.datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt.timezone.utc)
            ts = ts.timestamp()
        out.append((r["bot"], float(ts), float(r["pnl_pct"])))
    out.sort(key=lambda r: r[1])
    print(f"ledger file: {len(out):,} closes across "
          f"{len(set(r[0] for r in out))} books"
          f"{f'  ({dropped} unparseable timestamps dropped)' if dropped else ''}")
    return out


def hot_collapse(books, k):
    """(mean_pp, se_pp, n_windows): window mean MINUS next-window mean over
    every non-overlapping k-close window whose mean beats the book's own --
    the reversion `peak_arm` prints, as ONE number with its standard error.
    The same windows as `peak_arm`, by construction: one owner of "hot"."""
    col = []
    for _bot, v in books.items():
        ys = [p for _t, p in v]
        bm = st.mean(ys)
        for i in range(0, len(ys) - 2 * k, k):
            w = ys[i:i + k]
            nxt = ys[i + k:i + 2 * k]
            if len(nxt) < k:
                break
            if st.mean(w) > bm:
                col.append((st.mean(w) - st.mean(nxt)) * 100.0)
    if len(col) < 2:
        return None, None, len(col)
    return st.mean(col), st.stdev(col) / math.sqrt(len(col)), len(col)


def margin_arm(books, margin=None, ks=None):
    """[2026-09-02 -- Eamon: "Calibrate accordingly"] GRADE THE GRADER'S CONSTANT.

    `fleet_proprioception.LIVE_PRE_MARGIN_PP` is the margin the live lane
    applies to a change judged against its own PRE-WINDOW (I25: the window
    that motivated a change is selected on an extreme, so the next window
    reverts by this much with or without the change). The constant must be the
    MEASURED reversion, so this arm measures it at the grader's own baseline
    floor (`LIVE_BASE_MIN_N`), at this study's K, and at two wider windows,
    and says whether the constant sits INSIDE every 95% band or has DRIFTED
    out of one. Returns {"k": {K: {"collapse_pp", "se_pp", "n", "inside"}},
    "margin_pp", "verdict"}; `verdict` is INSIDE, DRIFT, or THIN (no window
    size had `MIN_WINDOWS` hot windows, so nothing was graded).

    Measured 2-Sep on 3,801 closes / 26 books: K=10 +1.74 (SE 0.50), K=15
    +1.52 (0.47), K=20 +1.60 (0.46), K=30 +1.67 (0.58) -- 1.7 inside every
    band, so the constant stood.
    """
    sys.path.insert(0, os.path.dirname(HERE))
    import fleet_proprioception as fp                 # noqa: PLC0415
    if margin is None:
        margin = fp.LIVE_PRE_MARGIN_PP
    if ks is None:
        ks = sorted({fp.LIVE_BASE_MIN_N, K, 20, 30})
    print(f"\n=== ARM 4 — IS THE GRADER'S PRE-WINDOW MARGIN THE MEASURED "
          f"REVERSION? ===\n  LIVE_PRE_MARGIN_PP = {margin:.2f} pp; the collapse "
          f"is window mean minus next-window mean, hot windows only")
    out, graded, drift = {}, 0, False
    for k in ks:
        m, se, n = hot_collapse(books, k)
        if m is None or n < MIN_WINDOWS:
            out[k] = {"collapse_pp": m, "se_pp": se, "n": n, "inside": None}
            print(f"  K={k:>2}: {n} hot windows -- too few to grade "
                  f"(need {MIN_WINDOWS})")
            continue
        lo, hi = m - 2 * se, m + 2 * se
        inside = lo <= margin <= hi
        graded += 1
        drift = drift or not inside
        out[k] = {"collapse_pp": m, "se_pp": se, "n": n, "inside": inside}
        print(f"  K={k:>2}{' (grader floor)' if k == fp.LIVE_BASE_MIN_N else '':15s}"
              f" collapse {m:+.3f} pp  SE {se:.3f}  n={n:>4}  "
              f"95% band [{lo:+.2f}, {hi:+.2f}]  -> margin "
              f"{'inside' if inside else 'DRIFT'}")
    verdict = "DRIFT" if drift else ("INSIDE" if graded else "THIN")
    print(f"  VERDICT: {verdict}"
          + {"DRIFT": " -- re-derive the constant from the band above and record "
                      "it in place (I12); never move it to a point estimate with "
                      "a 0.5pp SE",
             "THIN": " -- not enough hot windows to grade",
             "INSIDE": " -- the constant is the measurement"}[verdict])
    return {"k": out, "margin_pp": margin, "verdict": verdict}


def by_book(rows):
    d = collections.defaultdict(list)
    for bot, ts, pct in rows:
        d[bot].append((ts, pct))
    return {b: sorted(v) for b, v in d.items() if len(v) >= MIN_N}


def _slope(xs, ys):
    """OLS slope, and its t. None when degenerate."""
    n = len(xs)
    if n < 5:
        return None, None
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
    if n <= 2:
        return b, None
    se2 = sum(r * r for r in resid) / (n - 2) / sxx
    return b, (b / math.sqrt(se2) if se2 > 0 else None)


def age_arm(books):
    """Does a book decay in its OWN sequence, or does the whole fleet decay
    together in CALENDAR time? Only one of those is about our changes."""
    print("\n=== ARM 1 — BOOK AGE vs CALENDAR TIME ===")
    print("  Per book: slope of pnl_pct against its own trade INDEX (0..1).")
    print(f"\n{'book':<34}{'n':>5}{'mean%':>9}{'age slope':>11}{'t':>7}")
    age_slopes = []
    for bot, v in sorted(books.items(), key=lambda kv: -len(kv[1])):
        n = len(v)
        ys = [p for _t, p in v]
        xs = [i / (n - 1) for i in range(n)]
        b, t = _slope(xs, ys)
        if b is None:
            continue
        age_slopes.append(b)
        print(f"{bot:<34}{n:>5}{st.mean(ys)*100:>9.3f}"
              f"{b*100:>11.3f}{(t if t is not None else float('nan')):>7.2f}")
    if age_slopes:
        neg = sum(1 for s in age_slopes if s < 0)
        _n, m, t = len(age_slopes), st.mean(age_slopes), None
        sd = st.pstdev(age_slopes) * math.sqrt(_n / (_n - 1)) if _n > 1 else 0
        if sd > 0:
            t = m / (sd / math.sqrt(_n))
        print(f"\n  ACROSS {_n} books: mean age-slope {m*100:+.3f} pp "
              f"(t={t:+.2f})   NEGATIVE in {neg}/{_n}" if t is not None else "")
        print("  A book-age slope near zero means books do NOT decay as we "
              "work on them.")

    # Calendar arm: pool every close by month, ignoring which book it came from.
    print("\n  CALENDAR: fleet-wide mean per-trade return by month")
    per_m = collections.defaultdict(list)
    for bot, v in books.items():
        for ts, p in v:
            per_m[dt.datetime.fromtimestamp(ts, dt.timezone.utc)
                  .strftime("%Y-%m")].append(p)
    for mth in sorted(per_m):
        r = per_m[mth]
        print(f"    {mth}  n={len(r):>5}  mean {st.mean(r)*100:+.3f}%")
    print("  If the months move together while age-slopes are ~0, the pattern "
          "is the\n  MARKET, not our changes.")


def peak_arm(books, k=K):
    """THE NO-CHANGE CONTROL. What happens after a hot window, by default?"""
    print(f"\n=== ARM 2 — WHAT FOLLOWS A HOT WINDOW (no change required) ===")
    print(f"  For each book: every non-overlapping window of {k} closes whose "
          f"mean beats\n  the book's own mean, then the NEXT {k} closes. "
          f"Nothing was necessarily\n  changed between them — this is what "
          f"reversion looks like on its own.")
    hot_after, cold_after, base = [], [], []
    for bot, v in books.items():
        ys = [p for _t, p in v]
        bm = st.mean(ys)
        base.append(bm)
        for i in range(0, len(ys) - 2 * k, k):
            w = ys[i:i + k]
            nxt = ys[i + k:i + 2 * k]
            if len(nxt) < k:
                break
            if st.mean(w) > bm:
                hot_after.append((st.mean(w), st.mean(nxt), bm))
            else:
                cold_after.append((st.mean(w), st.mean(nxt), bm))

    def _show(label, rows):
        if not rows:
            print(f"  {label}: none")
            return
        w = st.mean([r[0] for r in rows])
        n_ = st.mean([r[1] for r in rows])
        b = st.mean([r[2] for r in rows])
        worse = sum(1 for r in rows if r[1] < r[0])
        print(f"  {label:<26} n={len(rows):>4}  window {w*100:+7.3f}%  "
              f"-> next {n_*100:+7.3f}%  (book mean {b*100:+7.3f}%)  "
              f"next<window in {worse}/{len(rows)}")
    _show("AFTER A HOT WINDOW", hot_after)
    _show("AFTER A COLD WINDOW", cold_after)
    if hot_after and cold_after:
        h = st.mean([r[1] - r[2] for r in hot_after])
        c = st.mean([r[1] - r[2] for r in cold_after])
        print(f"\n  Excess over the book's OWN mean in the FOLLOWING window:")
        print(f"    after a hot window : {h*100:+.3f} pp")
        print(f"    after a cold window: {c*100:+.3f} pp")
        print("\n  IF BOTH ARE NEAR ZERO, the next window is the book's mean "
              "regardless of\n  what came before — i.e. a hot streak is "
              "followed by a fall to the mean\n  WITH OR WITHOUT any change we "
              "make. That is regression to the mean, and\n  it would produce "
              "the exact feeling of 'we changed it and it broke' even\n  if "
              "every change we ever shipped were perfectly neutral.")


def select_arm():
    """The selection premium, in `t` units, from this session's own resample."""
    print("\n=== ARM 3 — THE SELECTION PREMIUM (measured today) ===")
    print("""  👩 mum's universe widening, 27-Aug. Four volume-ranked cells were
  measured and the BEST was taken:

      k=13  t=1.36     k=25  t=1.25     k=40  t=2.30  <- chosen     k=60  t=0.32

  Holding the rule fixed and resampling WHICH coins are graded, 24 draws:

      k=40  t ranges -0.78 .. +1.41,  median 0.45,  0 of 24 reach 2.0

  So the selected cell claimed t=2.30 against a resampled median of 0.45 —
  a SELECTION PREMIUM of ~1.85 t-units, and it did not reproduce even once
  in 24 draws. Had it shipped, the live book would have "started losing"
  immediately after a change that looked, in-sample, like its best evidence.

  THIS IS MECHANISM (2), caught before it shipped, and it is the same shape
  as (oe)'s universe churn on 📐 Grimes — which DID ship.""")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--age", action="store_true")
    ap.add_argument("--peak", action="store_true")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--margin", action="store_true",
                    help="grade fleet_proprioception.LIVE_PRE_MARGIN_PP against "
                         "the measured hot-window collapse (exit 2 on DRIFT)")
    ap.add_argument("--ledger", metavar="FILE",
                    help="a /trades.json?source=paper dump to read instead of "
                         "the DB (the sandbox has no DATABASE_URL)")
    ap.add_argument("-k", type=int, default=K)
    a = ap.parse_args()
    if not (a.age or a.peak or a.select or a.margin):
        a.age = a.peak = a.select = a.margin = True

    rows = load_ledger_file(a.ledger) if a.ledger else ledger()
    if not rows and not a.select:
        return 1
    books = by_book(rows) if rows else {}
    print(f"books with >= {MIN_N} closes: {len(books)}")
    if a.age:
        age_arm(books)
    if a.peak:
        peak_arm(books, a.k)
    if a.select:
        select_arm()
    rc = 0
    if a.margin and books:
        rc = 2 if margin_arm(books)["verdict"] == "DRIFT" else 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
