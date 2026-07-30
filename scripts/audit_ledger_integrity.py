#!/usr/bin/env python3
"""audit_ledger_integrity.py — is a book's ledger ONE book's record?

[2026-07-30 (hf)] WHY THIS EXISTS, and it is a correction of my own earlier
conclusion. `(gn)` found that two Railway services — `funding-carry` and
`yield-harvester-shadow` — both publish `perps-funding-carry-lshadow`, and
checked the paper ledger for duplicate `trade_id`s. It found none and concluded:
*"The paper LEDGER is CLEAN (82 closes, zero duplicate trade_ids) so the go-live
grade and the baseline are intact."*

**That check cannot detect the thing it was used to rule out.** Two independent
processes open positions at different moments, so their `trade_id`s
(`{coin}:{opened_ts}`) never collide. A duplicate-id scan is blind to duplicate
WRITERS by construction.

WHAT DOES DETECT THEM. A carry process keys `positions` by coin and enters only
`if c not in positions`, so **one process cannot hold two positions in the same
coin at once**. A same-coin overlap in the ledger is therefore structural proof
of a second writer. Measured across all 28 books and 1,706 episodes in the
ledger, same-pair overlapping holds appear in exactly TWO:

    perps-funding-carry-lshadow    7 overlaps, deepest  9.14h   <- two writers
    event-listing-sniper           9 overlaps, deepest 48.01h   <- see below

Every other book reads zero. The signal is specific, not an artifact of how
ledgers are written. A second, independent line points the same way: that book's
ledger reaches **10 concurrent open positions on 27 occasions** while its own
`MAX_POSITIONS` was **8** until 30-Jul.

AND THE STATE KEY IS SHARED TOO, which is the mechanism. `funding_carry_bot`
persists `positions` to `bot_state[bot_id]` and restores them at boot. Two
processes on one `bot_id` are two writers of ONE state key: each saves its own
position dict every loop and clobbers the other's, and a restart can restore the
other process's positions — so a single logical position can be tracked, and
closed, by both. That is the same two-writers-one-key hazard `(gn)` identified
for the summary row, on the key where it corrupts position tracking instead.

WHAT THIS MEANS FOR THE GRADE. `scripts/golive_readiness.py` reads this ledger.
For the book at the front of the go-live queue, `n` is not a count of one book's
independent trades — so `t`, which scales with sqrt(n), was overstated for a
reason entirely separate from `(hc)`'s era problem. **This is an operator action,
not a code fix**: one of the two services has to be stopped in Railway. A guard
cannot un-pool a ledger that two processes already wrote.

Usage:
  python3 scripts/audit_ledger_integrity.py            # against the live ledger
  python3 scripts/audit_ledger_integrity.py --selftest # offline, pure functions
"""
import argparse
import collections
import json
import os
import sys
import urllib.request
from datetime import datetime

DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")
LIMIT = int(os.environ.get("LEDGER_AUDIT_LIMIT", "5000"))

# ONE OWNER, and it is the CONSUMER. The three primitives live in
# `golive_readiness` — the module that ships inside the freqtrade image and does
# the grading these overlaps corrupt — and this audit imports them. The
# dependency points this way on purpose: the reverse would drag a non-shipped
# script into the image's import graph, which is the born-dark class, and a
# second copy here would let the audit and the gate disagree about the same
# ledger.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golive_readiness import (       # noqa: E402
    LEDGER_MIN_OVERLAP_S as MIN_OVERLAP_S, parse_stamp as _dt,
    peak_concurrency, same_pair_overlaps)

#: Books whose same-pair overlaps are EXPLAINED, with the explanation. The
#: BORN_DARK_OK idiom: an exemption is on the record or it is not taken.
LEDGER_INTEGRITY_OK = {
    "event-listing-sniper": (
        "🎯 Launch Sniper, RETIRED 17-Jul. It traded spot on ~100 CCXT "
        "exchanges and its ledger `pair` does not encode the exchange, so the "
        "SAME symbol held concurrently on two venues is one legitimate "
        "position each and reads here as an overlap. Not a second writer — a "
        "pair-naming collision in a book that no longer trades."),
}


def episodes(rows):
    """{bot: [(pair, open_dt, close_dt)]} — rows missing either stamp are
    skipped, which is correct: an episode with no open cannot be placed in
    time, and guessing one would manufacture or hide an overlap."""
    out = collections.defaultdict(list)
    for r in rows:
        if not r.get("opened_at") or not r.get("closed_at"):
            continue
        try:
            out[str(r.get("bot"))].append(
                (str(r.get("pair")), _dt(r["opened_at"]), _dt(r["closed_at"])))
        except (TypeError, ValueError):
            continue
    return out






def verdict(bot, eps, min_gap_s=MIN_OVERLAP_S):
    """(status, detail). 'two-writers' is asserted only from the OVERLAP
    detector — the one that needs no knowledge of a moving cap."""
    ov = same_pair_overlaps(eps, min_gap_s)
    peak = peak_concurrency(eps)
    if not ov:
        return "ok", f"peak {peak} concurrent, no same-pair overlap"
    if bot in LEDGER_INTEGRITY_OK:
        return "declared", f"{len(ov)} overlap(s), deepest {ov[0][1]:.2f}h"
    return "TWO-WRITERS", (
        f"{len(ov)} same-pair overlap(s), deepest {ov[0][1]:.2f}h on "
        f"{ov[0][0]} — one process cannot hold two positions in one symbol")


def fetch_rows():
    url = f"{DASH}/trades.json?source=paper&limit={LIMIT}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    return d if isinstance(d, list) else (d.get("trades") or [])


def _selftest():
    from datetime import timedelta, timezone
    t0 = datetime(2026, 7, 20, tzinfo=timezone.utc)

    def ep(pair, oh, ch):
        return (pair, t0 + timedelta(hours=oh), t0 + timedelta(hours=ch))

    # ONE process: sequential holds on one symbol, and a close-and-reopen in the
    # same loop (identical timestamps) must NOT read as an overlap.
    clean = [ep("BTC", 0, 5), ep("BTC", 5, 9), ep("ETH", 1, 4)]
    assert same_pair_overlaps(clean) == [], same_pair_overlaps(clean)
    assert peak_concurrency(clean) == 2, peak_concurrency(clean)
    assert verdict("any", clean)[0] == "ok"

    # sub-threshold jitter: a reopen 30s before the close is still one loop
    jitter = [("BTC", t0, t0 + timedelta(hours=5)),
              ("BTC", t0 + timedelta(hours=5, seconds=-30), t0 + timedelta(hours=9))]
    assert same_pair_overlaps(jitter) == [], "loop jitter must not fire"

    # TWO writers: a second BTC opens 2h inside the first hold.
    dup = [ep("BTC", 0, 5), ep("BTC", 3, 8)]
    hits = same_pair_overlaps(dup)
    assert len(hits) == 1 and abs(hits[0][1] - 2.0) < 1e-9, hits
    st, why = verdict("perps-funding-carry-lshadow", dup)
    assert st == "TWO-WRITERS" and "one process cannot" in why, (st, why)
    assert peak_concurrency(dup) == 2

    # a DECLARED book reports the same overlaps without the accusation
    st2, _ = verdict("event-listing-sniper", dup)
    assert st2 == "declared", st2
    for bot, why in LEDGER_INTEGRITY_OK.items():
        assert len(why) > 80, f"{bot}: an exemption needs a stated reason"

    # rows missing a stamp are skipped, never guessed
    got = episodes([{"bot": "b", "pair": "X", "opened_at": None,
                     "closed_at": "2026-07-20T00:00:00+00:00"},
                    {"bot": "b", "pair": "X",
                     "opened_at": "2026-07-20T00:00:00+00:00",
                     "closed_at": "2026-07-20T01:00:00+00:00"}])
    assert len(got["b"]) == 1, got
    # the sniper's ' UTC' dialect parses (its 337 rows used to be unreadable)
    got2 = episodes([{"bot": "s", "pair": "X",
                      "opened_at": "2026-07-13 15:05:04 UTC",
                      "closed_at": "2026-07-13 16:05:04 UTC"}])
    assert len(got2["s"]) == 1, got2
    assert episodes([]) == {} and peak_concurrency([]) == 0
    print("audit_ledger_integrity selftest OK (one-process clean, loop jitter "
          "below threshold, two-writer overlap, declared exemption, tolerant "
          "stamps)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--min-overlap-s", type=float, default=MIN_OVERLAP_S)
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    try:
        from cleanup_legacy_bots import LEGACY_BOTS
        retired = set(LEGACY_BOTS)
    except Exception:      # noqa: BLE001
        retired = set()
    eps = episodes(fetch_rows())
    print(f"{'book':34s} {'n':>4s} {'peak':>5s} {'ovl':>4s} {'deepest':>9s}  "
          f"verdict")
    print("-" * 96)
    bad = []
    for bot in sorted(eps):
        e = eps[bot]
        st, why = verdict(bot, e, a.min_overlap_s)
        ov = same_pair_overlaps(e, a.min_overlap_s)
        tag = " (retired)" if bot in retired else ""
        print(f"{bot:34s} {len(e):>4d} {peak_concurrency(e):>5d} "
              f"{len(ov):>4d} {(ov[0][1] if ov else 0):>8.2f}h  {st}{tag}")
        if st == "TWO-WRITERS":
            bad.append((bot, why, bot in retired))
    print()
    for bot, why, is_retired in bad:
        print(f"*** {bot}{' (RETIRED)' if is_retired else ''}: {why}")
    if bad:
        print("\nA guard cannot un-pool a ledger two processes already wrote. "
              "Stop the duplicate SERVICE in Railway; every close already "
              "written stays pooled, and any grade over that window inherits "
              "it.")
    return 1 if any(not r for _b, _w, r in bad) else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
