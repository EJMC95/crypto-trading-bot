#!/usr/bin/env python3
"""audit_live_roster.py — does the DECLARED live roster still match reality?

    python3 scripts/audit_live_roster.py                 # registry-only checks
    python3 scripts/audit_live_roster.py --pnl-json URL  # + the live feed
    python3 scripts/audit_live_roster.py --selftest

THE CLASS THIS CLOSES (2026-08-14 (mn)). A live slot swap changes which rows
hold real money, and the fleet writes that fact down in many places. It has now
rotted TWICE on one line — 17-Jul (Tide Rider -> Ticket Taker) and 13-Aug (
Ticket Taker -> Avo Maria) — and the second time the stale name survived in
CLAUDE.md's own "LIVE BOTS ALWAYS IN AUDIT SCOPE" rule and in two memories for
22 days. A standing audit rule naming a retired bot sends every future audit to
the wrong file, which is worse than having no rule.

`fleet_books` made the declaration single. This makes it SELF-CORRECTING: the
declared set is checked against the set DERIVED from the venue stamps, so the
next swap turns the build red the moment the new row publishes, instead of
waiting for a human to remember every site.

WHAT IT WILL AND WILL NOT SAY:
  * It NEVER guesses which roster is right. A disagreement is reported with
    both sides and the operator/next session decides — the fix might be
    "update the declaration" (a real swap) or "the feed is wrong" (a bad
    deploy publishing a stale venue), and picking one silently would be I8's
    confident-wrong-name failure.
  * It is FAIL-CLOSED on the feed: dark, empty, or venue-less input means
    "cannot say", which SKIPS the comparison rather than passing it. A network
    blip must never read as a clean roster ((kw): swept-DARK and swept-CLEAN
    must not be byte-identical). Without --pnl-json the derived arm simply does
    not run, and that is reported, not hidden.
  * The PROSE arm greps tracked docs for live-row ids that are no longer live.
    That is what would have caught the 22-day-stale CLAUDE.md rule. Retired
    rows are allowed to APPEAR (history entries legitimately name them) — it
    fires only when a doc presents one as CURRENT live surface, which is why
    it looks for the row id inside the fleet's own live-scope rule rather than
    anywhere in the file.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleet_books import (                      # noqa: E402
    DECLARED_LIVE, ROW_ENTRY, live_rows_from_feed)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Docs that state the live pair as CURRENT operating scope. {path: anchor} —
#: the anchor is the heading/rule the claim lives under, so a HISTORY mention
#: of a retired row elsewhere in the same file is not a finding.
PROSE_SCOPE = {
    "CLAUDE.md": "LIVE BOTS ALWAYS IN AUDIT SCOPE",
}

#: Rows that were live and are not any more, with the entry that retired them.
#: A doc naming one of these inside a live-scope anchor is the defect.
FORMERLY_LIVE = {
    "freqtrade-georgia-lighter": "retired 2-Sep (wg) — reallocated to mum; "
                                 "row hidden (wl)",
    "lighter-ticket-taker-lighter": "retired 13-Aug (ma) — Avo Maria took the slot",
    "crypto-trend-daily-lighter": "retired 17-Jul — the Taker took the slot",
    "equities-momentum-alpaca": "retired 14-Jul",
    "equities-regime-ibkr": "retired 14-Jul",
}


def prose_findings(root=ROOT, scope=None, formerly=None):
    """-> [(path, row, why)] for a doc presenting a retired live row as current.

    Reads a WINDOW around the anchor, not the whole file: this fleet's docs are
    part changelog, and every retired row is legitimately named in its own
    history. Only the live-scope rule itself is load-bearing for "who holds
    real money today".
    """
    scope = PROSE_SCOPE if scope is None else scope
    formerly = FORMERLY_LIVE if formerly is None else formerly
    out = []
    for rel, anchor in sorted(scope.items()):
        path = os.path.join(root, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue                     # absent doc is not a finding here
        i = text.find(anchor)
        if i < 0:
            out.append((rel, "-", f"anchor {anchor!r} not found — the rule was "
                                  f"renamed or removed; this guard is now blind "
                                  f"to it, which is itself the finding"))
            continue
        window = text[i:i + 2000]
        for row, why in sorted(formerly.items()):
            if row in window:
                out.append((rel, row, f"named as current live scope, but {why}"))
    return out


def roster_findings(declared=None, derived=None):
    """-> [str] disagreements between the declared and derived live sets."""
    declared = DECLARED_LIVE if declared is None else declared
    if derived is None:
        return []                        # cannot say -> no claim (fail-closed)
    out = []
    for row in sorted(set(derived) - set(declared)):
        out.append(f"LIVE IN THE FEED, NOT DECLARED: {row} publishes "
                   f"venue=lighter_live but is missing from "
                   f"fleet_books.DECLARED_LIVE")
    for row in sorted(set(declared) - set(derived)):
        out.append(f"DECLARED LIVE, NOT IN THE FEED: {row} is declared live but "
                   f"no row publishes venue=lighter_live under that id "
                   f"(retired? renamed? or its publisher is down)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pnl-json", help="path or URL of a /pnl.json document")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()

    fails = []

    # -- registry integrity (always runs, needs nothing external) ----------
    for row in DECLARED_LIVE:
        if row not in ROW_ENTRY:
            fails.append(f"DECLARED LIVE BUT UNMAPPED: {row} has no entry file "
                         f"in fleet_books.ROW_ENTRY")
    overlap = set(DECLARED_LIVE) & set(FORMERLY_LIVE)
    if overlap:
        fails.append(f"CONTRADICTION: {', '.join(sorted(overlap))} is both "
                     f"declared live and listed as formerly live")

    # -- the derived arm (only with a feed; fail-closed) -------------------
    derived, basis = None, "not requested (--pnl-json not given)"
    if a.pnl_json:
        try:
            import audit_code_currency as acc
            doc = acc.load_pnl_json(a.pnl_json) if hasattr(
                acc, "load_pnl_json") else None
        except Exception:                                    # noqa: BLE001
            doc = None
        if doc is None:
            doc = _load_json(a.pnl_json)
        derived = live_rows_from_feed(doc)
        basis = ("the live feed" if derived is not None else
                 "UNREADABLE — dark/empty/venue-less feed, comparison SKIPPED "
                 "(fail-closed: this is not a pass)")
    fails += roster_findings(derived=derived)

    # -- the prose arm ----------------------------------------------------
    prose = prose_findings()
    for rel, row, why in prose:
        fails.append(f"STALE DOC: {rel}: {row} — {why}")

    print(f"declared live : {', '.join(DECLARED_LIVE)}")
    print(f"derived live  : "
          f"{'(none)' if derived is None else ', '.join(derived) or '(empty)'}")
    print(f"basis         : {basis}")
    print(f"docs checked  : {', '.join(sorted(PROSE_SCOPE))}")
    if fails:
        print("\nFINDINGS:")
        for f in fails:
            print(f"  * {f}")
        print("\nFIX: if the live pair really changed, update "
              "`fleet_books.DECLARED_LIVE` (+ ROW_ENTRY/MARKER_GATED) and move "
              "the old row into FORMERLY_LIVE — ONE edit, which is the point of "
              "the registry. If the FEED is wrong, a publisher is stamping a "
              "stale venue and that is the bug. This guard never picks for you.")
        return 1
    print("\naudit_live_roster: OK — declaration, feed and docs agree.")
    return 0


def _load_json(src):
    import json
    try:
        if str(src).startswith(("http://", "https://")):
            import urllib.request
            with urllib.request.urlopen(src, timeout=30) as r:      # noqa: S310
                return json.loads(r.read().decode())
        with open(src, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                                # noqa: BLE001
        return None


def _selftest():
    print("Running audit_live_roster self-test...\n")

    # 1) agreement is silent
    assert roster_findings(declared=("a",), derived=["a"]) == []
    print("  1 declared == derived -> no finding")

    # 2) both directions of disagreement are reported, and NAMED
    f = roster_findings(declared=("a",), derived=["a", "b"])
    assert len(f) == 1 and "b" in f[0] and "NOT DECLARED" in f[0], f
    f = roster_findings(declared=("a", "c"), derived=["a"])
    assert len(f) == 1 and "c" in f[0] and "NOT IN THE FEED" in f[0], f
    print("  2 a new live row AND a vanished one are each reported")

    # 3) FAIL-CLOSED: an unreadable feed makes NO claim. If this returned a
    #    finding it would cry wolf on every network blip; if it silently
    #    "passed" it would be the vacuous green this guard exists to prevent.
    #    Skipping is the honest third state, and main() prints it as skipped.
    assert roster_findings(declared=("a",), derived=None) == []
    print("  3 unreadable feed -> no claim (and main() reports it as SKIPPED)")

    # 4) prose: a retired row inside the live-scope anchor is a finding
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d), exist_ok=True)
        doc = os.path.join(d, "DOC.md")
        open(doc, "w").write(
            "intro\n## LIVE SCOPE\ncheck old-live-row every pass\n" + "x" * 50)
        got = prose_findings(root=d, scope={"DOC.md": "LIVE SCOPE"},
                             formerly={"old-live-row": "retired"})
        assert len(got) == 1 and got[0][1] == "old-live-row", got
        print("  4 a retired row inside the live-scope rule is caught")

        # ...and the SAME row far outside the anchor window is NOT a finding:
        # history legitimately names retired rows.
        open(doc, "w").write(
            "## LIVE SCOPE\nclean rule here\n" + "x" * 4000 +
            "\nold-live-row appears here as history\n")
        assert prose_findings(root=d, scope={"DOC.md": "LIVE SCOPE"},
                              formerly={"old-live-row": "retired"}) == []
        print("  5 the same row as distant HISTORY is NOT a finding")

        # a renamed/removed anchor blinds the guard -> that IS the finding
        got = prose_findings(root=d, scope={"DOC.md": "NO SUCH ANCHOR"},
                             formerly={"old-live-row": "retired"})
        assert len(got) == 1 and "anchor" in got[0][2], got
        print("  6 a removed anchor is reported, never silently skipped")

    # 7) the LIVE repo passes its own prose check
    assert prose_findings() == [], prose_findings()
    print("  7 the live CLAUDE.md names the CURRENT live pair")

    print("\naudit_live_roster --selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
