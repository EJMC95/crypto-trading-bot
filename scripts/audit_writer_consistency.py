#!/usr/bin/env python3
"""SPLIT-BRAIN DETECTOR — does one book's summary row and its own ledger agree
about WHICH CODE wrote them?

[2026-09-02] WHY THIS EXISTS, and it is a five-day, seven-deploy incident.

`family-lighter-shadow` spent 30-Aug -> 2-Sep with TWO code states live at once.
The container Railway shows ran HEAD and traded four books; something else,
running pre-28-Aug code, owned the three `bot_pnl` summary rows. Measured 2-Sep:

    paper_trades.extra.build  = 4d93497e56d5  (b638893..HEAD, 18 commits)
    bot_pnl.extra.build       = edc3032d1c46  (29135cd..d2c0cb9, pre-28-Aug)

Those windows are DISJOINT — a 60-commit scan finds no commit producing both —
so the two rows cannot have come from one process (`_BUILD_CACHE` is per-process
and BOTH write paths read it). The damage was silent and total:

  * 👩 mum's shadow row reported **9 closes** against **56** in her ledger;
  * 🔭 georgia-v3 traded 41 closes and **never had a row at all**;
  * all three books are the CONTROL ARMS for the three real-money books, so
    every `bot_pnl` consumer — dashboard, `fleet_allocation` claims,
    `fleet_immune` liveness, the watchdog's NOT-ONLINE page — was reading a
    container that had stopped trading, stamped `status: "online"` and fresh.

WHY NOTHING CAUGHT IT — the gap this closes. Three guards were green throughout:

  * `audit_ledger_integrity` tests same-pair POSITION OVERLAP. Two processes
    whose books never hold the same coin at once produce zero overlaps, so it
    is blind to a split brain by construction.
  * `audit_code_currency` compares a CONTAINER to the REPO. It did fire
    BEHIND-OWN here — but a reader who checks the row against the running
    container's own log sees a healthy container and dismisses it.
  * `evidence_review`'s build-drift arm defers with "FILE SET, not necessarily
    code" whenever `build_n` differs — and for this image it ALWAYS differs
    (15 vs the repo tree's 16, because `Dockerfile.familyshadow` omits
    `fleet_tuning.py`), so that arm can never fire on these books. A bounded
    check reporting clean outside its bound.

NONE of them asks the one question that settles it: **does a book's own summary
row carry the same build stamp as the trades that book just wrote?** Those two
are written by the same process through the same `_stamp_build` hook, so they
agree ALWAYS — unless two processes are writing one book. That makes this a
structural test, not a heuristic, and it is the (hf) lesson applied one level
up: pick a test that COULD detect the damage.

It also catches the second, quieter half — a book whose ledger is accruing while
it has no summary row at all (🔭 georgia-v3's shape), which is invisible to every
organ that enumerates books from `bot_pnl`.

CONTRACT
  * READ-ONLY. Never writes, never publishes, never touches a lever.
  * Two regimes ((a-guard-has-two-regimes)): with `DATABASE_URL` it audits the
    live fleet; without one it SKIPS cleanly (exit 0) rather than failing CI
    for want of a database it was never given.
  * Fail-SOFT per book: one unreadable row can never cost the whole sweep.
  * Exit 1 ONLY on a finding. A stamp that cannot be read is REPORTED and is
    not a finding — an unstampable row is a sensor that cannot see, and (I8/I6)
    an absence is not evidence without a control group. This sweep publishes
    the control group: how many books DID compare cleanly.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

#: How far back to look for a book's own recent trades. A book that has not
#: closed anything in this window has no ledger side to compare and is reported
#: QUIET, never a finding — silence is not a split brain.
LOOKBACK_H = float(os.environ.get("WRITER_CONSISTENCY_LOOKBACK_H", "48"))

#: How many of a book's most recent closes to read the stamp from. A handful,
#: because a deploy legitimately changes the stamp mid-window: we compare the
#: row against the MOST RECENT trade stamp and treat any older ones as history.
RECENT_TRADES = int(os.environ.get("WRITER_CONSISTENCY_RECENT_N", "5"))

#: A book whose ledger has closes newer than this while it has NO summary row
#: is ORPHANED — trading into a row nothing publishes.
ORPHAN_H = float(os.environ.get("WRITER_CONSISTENCY_ORPHAN_H", "12"))


def _extra(raw):
    """bot_pnl.extra / paper_trades.extra as a dict, whatever the driver gives."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except (TypeError, ValueError):
        return {}


def classify(row_build, row_n, trade_build, trade_n, ledger_n, row_closes):
    """(verdict, detail) for ONE book. Pure — this is what the selftest drives.

    Verdicts:
      SPLIT-BRAIN  the row and the book's own newest trade carry DIFFERENT
                   build stamps. Two code states wrote one book.
      QUIET        no trades in the window; nothing to compare.
      UNSTAMPED    one side carries no stamp; reported, never a finding.
      OK           both stamps present and equal.
    """
    if trade_build is None:
        return "QUIET", "no closes in the window — nothing to compare"
    if not row_build or not trade_build:
        return "UNSTAMPED", (f"row={row_build or 'none'} trade={trade_build or 'none'}"
                             " — a sensor that cannot see does not vote")
    if row_build == trade_build:
        d = f"both {row_build}"
        # The closes gap is corroboration, not the test: a row legitimately
        # lags its ledger by the publish cadence. Only flagged when the stamps
        # already agree, so it can never manufacture a SPLIT-BRAIN.
        if row_closes is not None and ledger_n is not None and ledger_n - row_closes > 20:
            d += (f" (note: row reports {row_closes} closes vs {ledger_n} in the"
                  " ledger — large gap, check the publish cadence)")
        return "OK", d
    return "SPLIT-BRAIN", (
        f"summary row was written by {row_build}/{row_n} while this book's own "
        f"newest close was written by {trade_build}/{trade_n} — two code states "
        f"are writing one book (row reports {row_closes} closes, ledger has "
        f"{ledger_n})")


def audit(conn):
    """Returns (findings, clean, reported) — findings are SPLIT-BRAIN/ORPHAN."""
    findings, clean, reported = [], [], []
    cur = conn.cursor()

    cur.execute("select bot, closed_trades, extra from bot_pnl")
    rows = {b: (cl, _extra(e)) for b, cl, e in cur.fetchall()}

    # Every book with recent ledger activity — the population, so a book with
    # no row at all is still in scope (that is the orphan half).
    cur.execute(
        """select bot, count(*) from paper_trades
           where closed_at::timestamptz > now() - interval '%s hours'
           group by 1""" % int(LOOKBACK_H))
    active = dict(cur.fetchall())

    for bot in sorted(set(rows) | set(active)):
        try:
            cur.execute(
                """select extra from paper_trades where bot=%s
                   and closed_at::timestamptz > now() - interval '%s hours'
                   order by closed_at::timestamptz desc limit %s"""
                % ("%s", int(LOOKBACK_H), RECENT_TRADES), (bot,))
            stamps = [(_extra(r[0]).get("build"), _extra(r[0]).get("build_n"))
                      for r in cur.fetchall()]
            trade_build, trade_n = (stamps[0] if stamps else (None, None))

            cur.execute("""select count(*), extract(epoch from
                             (now()-max(closed_at::timestamptz)))/3600
                           from paper_trades where bot=%s""", (bot,))
            ledger_n, last_h = cur.fetchone()

            if bot not in rows:
                if last_h is not None and last_h <= ORPHAN_H:
                    findings.append((bot, "ORPHAN-BOOK",
                                     f"{ledger_n} closes in its ledger, newest "
                                     f"{last_h:.1f}h ago, and NO bot_pnl row — "
                                     "invisible to every organ that enumerates "
                                     "books from bot_pnl"))
                continue

            row_closes, extra = rows[bot]
            verdict, detail = classify(extra.get("build"), extra.get("build_n"),
                                       trade_build, trade_n, ledger_n, row_closes)
            svc = extra.get("svc") or "?"
            if verdict == "SPLIT-BRAIN":
                findings.append((bot, verdict, f"svc={svc}: {detail}"))
            elif verdict == "OK":
                clean.append((bot, detail))
            else:
                reported.append((bot, verdict, detail))
        except Exception as e:                       # noqa: BLE001 — fail SOFT
            reported.append((bot, "ERROR", str(e)[:160]))
            try:
                conn.rollback()
            except Exception:                        # noqa: BLE001
                pass
    return findings, clean, reported


def _selftest():
    """Drive `classify` over the shapes that matter. I3: each assertion is a
    mutation someone could make to this file and would have to redden."""
    # the real 2026-09-02 incident
    v, d = classify("edc3032d1c46", 15, "4d93497e56d5", 15, 56, 9)
    assert v == "SPLIT-BRAIN", v
    assert "two code states" in d
    # the agreeing case must NOT fire, including across a legitimate redeploy
    assert classify("abc", 15, "abc", 15, 56, 55)[0] == "OK"
    # a differing build_n with the SAME id is still one process (the (fd) trap
    # is about repo-vs-container, not row-vs-ledger) — must stay OK
    assert classify("abc", 15, "abc", 16, 10, 10)[0] == "OK"
    # no trades in the window is silence, never a finding
    assert classify("abc", 15, None, None, 0, 0)[0] == "QUIET"
    # an unstamped side must not vote either way
    assert classify(None, None, "abc", 15, 5, 5)[0] == "UNSTAMPED"
    assert classify("abc", 15, "", None, 5, 5)[0] == "UNSTAMPED"
    # the closes-gap note is corroboration only: it may never CREATE a finding
    v, d = classify("abc", 15, "abc", 15, 56, 9)
    assert v == "OK" and "large gap" in d, (v, d)
    # ...and must be silent when the gap is ordinary publish lag
    assert "large gap" not in classify("abc", 15, "abc", 15, 56, 55)[1]
    print("audit_writer_consistency selftest: OK")


def main():
    if "--selftest" in sys.argv:
        _selftest()
        return 0

    url = (os.environ.get("DATABASE_URL")
           or os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if not url:
        print("audit_writer_consistency: SKIP — no DATABASE_URL "
              "(this guard needs the live fleet; CI has no database)")
        return 0
    try:
        import psycopg2
    except ImportError:
        print("audit_writer_consistency: SKIP — psycopg2 not installed")
        return 0
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
    except Exception as e:                           # noqa: BLE001
        print(f"audit_writer_consistency: SKIP — cannot connect ({e})")
        return 0

    findings, clean, reported = audit(conn)

    print("WRITER CONSISTENCY — does each book's summary row carry the same "
          "build stamp as its own newest close?")
    print(f"  window {LOOKBACK_H:.0f}h · {len(clean)} book(s) agree · "
          f"{len(reported)} reported · {len(findings)} finding(s)")
    for bot, detail in clean:
        print(f"  ok        {bot:34} {detail}")
    for bot, verdict, detail in reported:
        print(f"  {verdict.lower():9} {bot:34} {detail}")
    if not findings:
        print("\nNo split brain: every comparable book's row and ledger were "
              "written by the same code.")
        return 0
    print()
    for bot, verdict, detail in findings:
        print(f"*** {bot}: {verdict}\n    {detail}")
    print("\nA split brain means the summary row is NOT a receipt for the "
          "process that trades the book. Every bot_pnl consumer — dashboard, "
          "allocation claims, immune liveness, the NOT-ONLINE pager — is "
          "reading the wrong process. Find the second deployment and stop it; "
          "the ledger side stays sound either way.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
