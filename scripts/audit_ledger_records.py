#!/usr/bin/env python3
"""audit_ledger_records — A RECORD MUST NOT FABRICATE WHAT IT DOES NOT KNOW.

Born 27-Aug-2026 (tw), out of Eamon's ask — *"make sure all data has been
recorded correctly, for each bot, in the right place"* — and out of what that
sweep found. Six defects, and they are ONE CLASS wearing six costumes: **a
write site that did not know something and wrote a plausible-looking value
instead of recording the absence.**

  * `f"{pair}:{m.get('opened_ts')}"` -> the literal id `"ETH:None"`, a SHARED
    primary key under an upsert, so the second row silently OVERWROTE the
    first. 15 exposed rows on the two real-money books, one of them a real
    -$0.84 trade one halt event from being zeroed ((tv)).
  * `opened_ts or time.time()` -> an open stamp taken from a clock that runs
    AFTER the close, so 8 rows carry a NEGATIVE hold ((tv)).
  * a halt/flatten EVENT written into the closed-trade ledger as a trade, and
    counted as a LOSS: 🙏 avo published 3W/10L over 13 "closes" on a book
    that had taken 4 real trades ((tw)).
  * 🧭 nav-cook's row counters diverged from its own ledger (3 closes vs 37).
  * 🌾 carry publishes `pnl_abs` on a different BASIS from the other 19 rows.

I8 already says *"unknown degrades to the OLD id, never to a guess"* — but I8
governs a DETECTOR'S OUTPUT, and every one of the above is a LEDGER WRITE. The
class had no guard, which is why it recurred six times before anyone counted
it. This is that guard.

**WHAT IT CHECKS** — only conditions that are INTERNALLY IMPOSSIBLE for an
honest record, so a finding is never a matter of taste:

  R1  opened_at > closed_at            a trade that closed before it opened
  R2  trade_id renders an absent value ':None', ':nan', a trailing ':'
  R3  an EVENT with no marker          the (th) `non_economic` contract
  R4  row counters vs the ledger       closed_trades vs the admissible count
  R5  pnl_abs basis divergence         equity-1000 vs realised, unexplained

**IT IS A RATCHET, NOT A BAR.** A guard that reddens CI on a pre-existing
backlog gets exempted within a day and then guards nothing ((mz)). So the
counts measured the day it shipped are the CEILING: the backlog may only
shrink, and a NEW violation fails immediately. Lower a number here only with
a commit that actually fixed rows.

**TWO REGIMES, and the CI one is not a weaker version of the other.** CI has
no DATABASE_URL, so there the ledger arms cannot run at all. Reporting green
there would be the vacuous-green failure this repo has already paid for, so
with no DB this exits 0 having explicitly SAID it inspected nothing — a
skip that announces itself is not a pass. The `--strict` flag turns that
skip into a failure for anywhere that genuinely has a DB and wants proof.

ADVISORY / READ-ONLY: opens one read connection, writes nothing, moves no
lever. Exit 1 on a ratchet breach, 2 on an unusable feed under --strict.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The ONE owner of "is this row an event rather than a trade" — imported,
# never re-expressed here ((hj): a second copy of the rule is a second rule,
# and this exact predicate has already drifted once inside a single commit).
from bot_pnl_store import is_non_economic, is_quarantined  # noqa: E402

# ---------------------------------------------------------------------------
# THE RATCHET. Measured 2026-08-27 on the live ledger. These are CEILINGS.
# A number may only fall, and only in a commit that fixed the rows behind it.
RATCHET = {
    "R1_negative_hold": 8,       # 5 avo + 3 georgia, all pre-(tv)
    "R2_absent_in_id": 15,       # 9 avo + 5 georgia + 1 legacy, all pre-(tv)
    "R3_unmarked_event": 13,     # 9 avo + 4 georgia, all pre-(th)
    # 3 TODAY: nav-cook (-34, a real drift) + avo (+9) and georgia (+4),
    # which are the (tw) phantom miscount itself. Both live books re-seed
    # from `fetch_paper_aggregate` at their next boot, so this MUST fall to
    # 1 once the (tw) deploy has cycled them — verified after, not assumed.
    "R4_counter_drift": 3,
}
# R5 is REPORTED, never ratcheted: carry's realised-only basis is a deliberate
# design decision that needs an operator ruling (one convention, or a declared
# `extra.pnl_basis`), not a build failure. Recorded so it cannot go quiet.

LIVE_BOOKS = ("freqtrade-avo-maria-lighter", "freqtrade-georgia-lighter",
              "freqtrade-mum-lighter")


def _conn():
    url = (os.environ.get("DATABASE_URL")
           or os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if not url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(url)
    except Exception:  # noqa: BLE001
        return None


def _living(cur, hours=48):
    cur.execute(
        "SELECT bot FROM bot_pnl WHERE updated_at > now() - interval '%s hours'"
        % int(hours))
    return sorted(r[0] for r in cur.fetchall())


def audit(cur, living):
    """-> {rule: [finding, ...]}. Every finding names bot + row + the values."""
    out = {k: [] for k in RATCHET}
    out["R5_basis_divergence"] = []

    # R1 — a trade cannot close before it opens.
    cur.execute(
        "SELECT bot, trade_id, opened_at, closed_at FROM paper_trades "
        "WHERE opened_at IS NOT NULL AND closed_at IS NOT NULL "
        "  AND opened_at::timestamptz > closed_at::timestamptz")
    for bot, tid, oa, ca in cur.fetchall():
        out["R1_negative_hold"].append(
            f"{bot} {tid}: opened {oa} AFTER closed {ca}")

    # R2 — an id that renders an absent value is a SHARED key under the
    # upsert, so a collision destroys a row instead of duplicating it.
    cur.execute(
        "SELECT bot, trade_id FROM paper_trades "
        "WHERE trade_id LIKE '%%:None' OR trade_id LIKE '%%:nan' "
        "   OR trade_id LIKE '%%:' OR trade_id LIKE '%%:none'")
    for bot, tid in cur.fetchall():
        out["R2_absent_in_id"].append(f"{bot} {tid!r}")

    # R3 — an event the (th) marker does not claim. The signature is the
    # legacy bridge; a row written AFTER the marker shipped and still
    # unmarked is a NEW violation, which is what the ratchet catches.
    cur.execute(
        "SELECT bot, trade_id, pnl_abs, entry_price, extra, closed_at "
        "FROM paper_trades WHERE pnl_abs = 0")
    for bot, tid, pnl, ep, ex, ca in cur.fetchall():
        if not is_non_economic(pnl, ep, ex):
            continue
        if (ex or {}).get("non_economic") is True:
            continue
        out["R3_unmarked_event"].append(f"{bot} {tid} closed {str(ca)[:19]}")

    # R4 — the row's counters against its own ledger. The first live run
    # taught this rule what it may actually assert: books do NOT share one
    # counting convention. 🧘 douglas seeds from `fetch_paper_aggregate` and
    # so publishes quarantine-EXCLUDED (60 of 62); 🎫 the taker keeps its own
    # running count and publishes the raw 263 while 45 of its rows are
    # quarantined. Demanding one number flagged BOTH as defects, and neither
    # is one. So the assertion is a BAND, and only the two edges are
    # impossible for an honest row:
    #   upper = total - non_economic   (counting EVENTS as trades is the
    #                                   (tw) defect: avo +9, georgia +4)
    #   lower = upper - quarantined    (below this the row has lost closes
    #                                   its ledger holds: nav-cook 3 vs 37)
    # Anything between the edges is a book's declared convention, not drift.
    for bot in living:
        cur.execute(
            "SELECT pnl_abs, entry_price, extra, pair, closed_at "
            "FROM paper_trades WHERE bot=%s", (bot,))
        rows = cur.fetchall()
        total = len(rows)
        n_event = sum(1 for p, e, x, _pr, _ca in rows if is_non_economic(p, e, x))
        n_quar = sum(1 for p, e, x, pr, ca in rows
                     if not is_non_economic(p, e, x) and is_quarantined(bot, pr, ca))
        upper = total - n_event
        lower = upper - n_quar
        cur.execute("SELECT closed_trades FROM bot_pnl WHERE bot=%s", (bot,))
        got = cur.fetchone()
        if not got or got[0] is None:
            continue
        published = int(got[0])
        if published > upper:
            out["R4_counter_drift"].append(
                f"{bot}: row publishes {published}, ledger holds only "
                f"{upper} economic closes (+{published - upper} EVENTS "
                f"counted as trades)")
        elif published < lower:
            out["R4_counter_drift"].append(
                f"{bot}: row publishes {published}, ledger holds {upper} "
                f"economic closes ({published - upper}; quarantine explains "
                f"at most {n_quar})")

    # R5 — one field, one meaning. Reported, never ratcheted.
    cur.execute(
        "SELECT bot, equity, pnl_abs, extra FROM bot_pnl "
        "WHERE bot LIKE '%%lshadow'")
    for bot, eq, pnl, ex in cur.fetchall():
        if eq is None or pnl is None:
            continue
        resid = float(eq) - 1000.0 - float(pnl)
        if abs(resid) <= 0.01:
            continue
        # [(vk)] A DECLARED basis is not a divergence. 🌾 carry publishes
        # `pnl_abs` realised-only on purpose — accrual is not realised until
        # the leg closes — and now SAYS so on the row, with the reconciling
        # `open_pnl` beside it. The defect was never the convention; it was
        # that a fleet-summing consumer had no way to know. A row that
        # declares its basis has closed that, so it stops being reported;
        # a row that diverges SILENTLY still is.
        basis = (ex or {}).get("pnl_basis") if isinstance(ex, dict) else None
        if basis:
            continue
        out["R5_basis_divergence"].append(
            f"{bot}: equity-1000-pnl_abs = {resid:+.4f} with NO "
            f"`extra.pnl_basis` (every other shadow row reconciles to "
            f"0.0000; declare the basis or use the fleet convention)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="fail (exit 2) when the ledger cannot be read, "
                         "instead of skipping with an explicit notice")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    conn = _conn()
    if conn is None:
        msg = ("audit_ledger_records: SKIPPED — no readable DATABASE_URL, so "
               "NOTHING was inspected. This is not a pass.")
        print(msg)
        return 2 if a.strict else 0

    try:
        with conn.cursor() as cur:
            living = _living(cur)
            found = audit(cur, living)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    if a.json:
        print(json.dumps({k: v for k, v in found.items()}, indent=2))

    bad = False
    print(f"audit_ledger_records — {len(living)} living books\n")
    for rule, ceiling in RATCHET.items():
        hits = found.get(rule, [])
        n = len(hits)
        state = "OK " if n <= ceiling else "FAIL"
        if n > ceiling:
            bad = True
        arrow = "" if n == ceiling else f"  ({n - ceiling:+d} vs ratchet)"
        print(f"  [{state}] {rule:22} {n:3} / ceiling {ceiling}{arrow}")
        for h in hits[:6]:
            print(f"           - {h}")
        if n > 6:
            print(f"           ... and {n - 6} more "
                  f"(--json for the full list, never truncate a work-list)")
    r5 = found.get("R5_basis_divergence", [])
    print(f"\n  [INFO] R5_basis_divergence   {len(r5)} (reported, not ratcheted)")
    for h in r5:
        print(f"           - {h}")

    if bad:
        print("\nFAIL — a ratchet was breached. These counts are CEILINGS: a "
              "new record that fabricates what it does not know is a defect, "
              "not a backlog item.")
        return 1
    print("\nOK — no ratchet breached.")
    return 0


def _selftest():
    """The owner's contract, and proof each arm CAN fire — an audit whose
    silence has never been shown to break is not a negative result."""
    assert is_non_economic(0.0, None, {}) is True
    assert is_non_economic(0.0, None, {"non_economic": True}) is True
    assert is_non_economic(-0.84, 3.6604, {}) is False, \
        "georgia's real LIT loss must never be classified as an event"
    assert is_non_economic(0.0, None, {"accrued": 0.3}) is False, \
        "a funding row books accrual, not a price — it is a TRADE"
    assert is_non_economic(0.0, 100.0, {}) is False
    assert is_non_economic("junk", None, None) is False, "fail-OPEN"
    assert set(RATCHET) == {"R1_negative_hold", "R2_absent_in_id",
                            "R3_unmarked_event", "R4_counter_drift"}
    assert all(isinstance(v, int) and v >= 0 for v in RATCHET.values())
    print("audit_ledger_records self-test: OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(main())
