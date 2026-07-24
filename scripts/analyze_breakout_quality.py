#!/usr/bin/env python3
"""Increment-2 analysis for the breakout SCANNER SIDEKICK (see CHANGELOG (di)).

The taker CAPTURES `brk_quality` + `up_strength` on every bull-era breakout entry
(lighter_ticket_taker.py). This tool reads those closed breakouts back and asks
the ONE question the winning-criteria gate needs answered:

    does higher captured breakout_quality actually separate WINNERS from LOSERS?

It grades the closed long-breakouts into quality terciles (win-rate + avg P&L per
bucket) and DERIVES the lowest `TT_BRK_QUALITY_MIN` above which the surviving
cohort is positive AND both-halves-positive (the fleet's standard robustness bar)
with enough episodes to mean something. Until that bar is met it prints the honest
"insufficient / no separation" verdict and proposes NOTHING — a guessed threshold
is exactly what this pipeline exists to avoid.

It ALSO reports whether breakout is even FIRING on the shadow arm: a zero count
under an enabled bull arm means the read is blocked (brain veto / sparse regime),
not that the criteria are undecidable — a different problem with a different fix.

LIGHTER-ONLY / shadow-only: reads the paper_trades ledger; never trades. Run in
the fleet (DATABASE_URL present) or point it at the public PG URL. `--selftest`
needs no DB.
"""
import os
import sys
import json
import statistics

BOT = "lighter-ticket-taker-lshadow"
MIN_N = 12            # per-side episode floor before any threshold is proposed
MIN_EDGE = 2.0       # $ the surviving cohort must clear to count as separated


def _rows_from_db(url, since_iso):
    """(quality, up_strength, pnl_abs, closed_at) for bull-era long-breakout
    closes carrying a captured quality. Empty on any read failure — a dark read
    proposes nothing, never a fabricated pass."""
    import psycopg2
    out = []
    try:
        c = psycopg2.connect(url)
        cur = c.cursor()
        cur.execute(
            "select (extra->>'brk_quality')::float, (extra->>'up_strength')::float,"
            " pnl_abs, closed_at from paper_trades"
            " where bot=%s and reason like 'long-breakout%%'"
            "   and extra ? 'brk_quality' and closed_at >= %s"
            " order by closed_at",
            (BOT, since_iso))
        for q, u, pnl, ts in cur.fetchall():
            out.append((float(q), (float(u) if u is not None else None),
                        float(pnl), ts))
        c.close()
    except Exception as e:      # noqa: BLE001 — read failure => no data, not a crash
        print(f"[analyze] DB read failed ({e}); returning empty", file=sys.stderr)
        return []
    return out


def _fired_count(url, since_iso):
    """(entries_with_quality, all_breakout_closes) so a caller can tell 'the read
    is collecting' from 'breakout is not firing at all' (brain veto / sparse)."""
    import psycopg2
    try:
        c = psycopg2.connect(url); cur = c.cursor()
        cur.execute("select count(*) from paper_trades where bot=%s"
                    " and reason like 'long-breakout%%' and closed_at >= %s",
                    (BOT, since_iso))
        allc = cur.fetchone()[0]
        cur.execute("select count(*) from paper_trades where bot=%s"
                    " and reason like 'long-breakout%%' and extra ? 'brk_quality'"
                    " and closed_at >= %s", (BOT, since_iso))
        withq = cur.fetchone()[0]
        c.close()
        return withq, allc
    except Exception:      # noqa: BLE001
        return 0, 0


def grade_by_quality(rows):
    """Split rows (quality, _u, pnl, _ts) into quality terciles and return
    [(label, lo, hi, n, win_rate, avg_pnl), ...] low->high. Pure."""
    if len(rows) < 3:
        return []
    qs = sorted(r[0] for r in rows)
    n = len(qs)
    t1 = qs[n // 3]
    t2 = qs[2 * n // 3]
    buckets = [("low", -1e9, t1), ("mid", t1, t2), ("high", t2, 1e9)]
    out = []
    for label, lo, hi in buckets:
        # clean partition: low = q<t1, mid = t1<=q<t2, high = q>=t2 (no overlap)
        sel = [r for r in rows if lo <= r[0] < hi] if label != "high" \
            else [r for r in rows if r[0] >= lo]
        if not sel:
            out.append((label, lo, hi, 0, None, None))
            continue
        wins = sum(1 for r in sel if r[2] > 0)
        out.append((label, lo, hi, len(sel), wins / len(sel),
                    statistics.mean(r[2] for r in sel)))
    return out


def _both_halves_positive(pnls):
    """True iff the chronological first AND second half each sum positive — the
    fleet's minimum robustness bar (a single lucky streak fails it)."""
    if len(pnls) < 4:
        return False
    mid = len(pnls) // 2
    return sum(pnls[:mid]) > 0 and sum(pnls[mid:]) > 0


def derive_threshold(rows):
    """The LOWEST captured quality `q*` such that keeping only breakouts with
    quality >= q* leaves a cohort that (a) has >= MIN_N episodes, (b) sums to
    >= +$MIN_EDGE, and (c) is both-halves-positive. None if no such q* exists yet
    (the honest 'undecidable / no separation' answer). rows are (q,_u,pnl,ts),
    assumed chronological. Pure — the whole gate decision in one testable place."""
    if len(rows) < MIN_N:
        return None
    for cut in sorted({r[0] for r in rows}):
        cohort = [r for r in rows if r[0] >= cut]
        if len(cohort) < MIN_N:
            break          # raising the cut only shrinks it further
        pnls = [r[2] for r in cohort]
        if sum(pnls) >= MIN_EDGE and _both_halves_positive(pnls):
            return round(cut, 4)
    return None


def _report(rows, withq, allc):
    print(f"=== breakout scanner-sidekick quality analysis ({BOT}) ===")
    print(f"bull-era long-breakout closes: {allc} total, {withq} carry a captured "
          f"quality, {len(rows)} usable")
    if allc == 0:
        print("VERDICT: the breakout arm has taken ZERO bull-era closes — the read "
              "is NOT collecting. Check the brain veto (breakout graded negative "
              "=> vetoed) / regime sparsity BEFORE reading anything into quality.")
        return
    if len(rows) < MIN_N:
        print(f"VERDICT: INSUFFICIENT ({len(rows)} < {MIN_N}). Keep the gate OFF; "
              "propose nothing. Let the shadow arm accrue.")
        return
    print("\nquality terciles (low -> high):")
    for label, lo, hi, n, wr, avg in grade_by_quality(rows):
        print(f"  {label:>4}: n={n:<3} win={ (wr*100 if wr is not None else 0):4.0f}% "
              f"avg=${(avg if avg is not None else 0):+.3f}")
    q = derive_threshold(rows)
    if q is None:
        print("\nVERDICT: NO SEPARATION yet — no quality cut leaves a positive, "
              "both-halves cohort at the episode floor. Gate stays OFF.")
    else:
        print(f"\nVERDICT: threshold candidate TT_BRK_QUALITY_MIN={q} — the cohort "
              f"at quality>={q} clears +${MIN_EDGE} and both halves. This is a "
              "PROPOSAL for shadow validation, NOT a live change.")


def selftest():
    # grade_by_quality: high-quality bucket wins, low loses
    import datetime as _dt
    base = _dt.datetime(2026, 7, 24, tzinfo=_dt.timezone.utc)
    def _ts(i): return base + _dt.timedelta(hours=i)
    # 18 rows: quality correlates with pnl (high q -> +, low q -> -)
    rows = []
    for i in range(18):
        q = 0.2 + 0.04 * i               # 0.20 .. 0.88
        pnl = -2.0 if q < 0.5 else 2.5   # clean separation at 0.5
        rows.append((round(q, 4), 0.5, pnl, _ts(i)))
    g = grade_by_quality(rows)
    assert [b[0] for b in g] == ["low", "mid", "high"]
    assert g[0][4] < g[2][4], "high tercile must out-win low"      # win-rate
    assert g[2][5] > g[0][5], "high tercile must out-earn low"     # avg pnl
    # derive_threshold: returns a cut whose cohort is robust-positive (the LOWEST
    # such cut — admit the most trades while staying positive + both-halves). Assert
    # the CONTRACT, not a hand-picked value: the returned gate must actually work.
    q = derive_threshold(rows)
    assert q is not None, "clean separation should yield a threshold"
    cohort = [r for r in rows if r[0] >= q]
    assert len(cohort) >= MIN_N and sum(r[2] for r in cohort) >= MIN_EDGE
    assert _both_halves_positive([r[2] for r in cohort])
    assert q > min(r[0] for r in rows), "must filter out at least the worst tail"
    # both-halves guard: a front-loaded winner (all wins first) must FAIL
    fl = [(0.9, 0.5, (5.0 if i < 9 else -1.0), _ts(i)) for i in range(18)]
    # cohort at q>=0.9 is all 18; first half +, second half - => not both-halves
    assert derive_threshold(fl) is None, "front-loaded streak must not pass"
    # insufficient n: below the floor -> None, never a fabricated pass
    assert derive_threshold(rows[:6]) is None
    # all-losers: no positive cut exists
    assert derive_threshold([(0.2 + 0.04 * i, 0.5, -1.0, _ts(i))
                             for i in range(18)]) is None
    # empty / tiny inputs are safe
    assert grade_by_quality([]) == [] and derive_threshold([]) is None
    print("analyze_breakout_quality selftest OK "
          "(tercile grading, threshold derivation, both-halves guard, "
          "n-floor, all-losers, empty-safe)")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        print("no DATABASE_URL/DATABASE_PUBLIC_URL — run in the fleet or export one "
              "(this tool never trades; it only reads the ledger).", file=sys.stderr)
        sys.exit(2)
    # bull enabled on the shadow taker 2026-07-24 ~08:06 UTC (CHANGELOG (dd)/(df))
    since = os.environ.get("BRK_SINCE", "2026-07-24 08:06:00+00")
    rows = _rows_from_db(url, since)
    withq, allc = _fired_count(url, since)
    _report(rows, withq, allc)


if __name__ == "__main__":
    main()
