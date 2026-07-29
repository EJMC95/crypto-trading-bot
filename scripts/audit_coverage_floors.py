#!/usr/bin/env python3
"""audit_coverage_floors.py — the real-money surface's coverage RATCHET.

Finding 9 (TEST_COVERAGE_ANALYSIS_2026-07-29.md): the repo measured 48%
coverage the day it was first measured, and nothing in CI would notice the
real-money files drifting back down. This guard reads a coverage.json
(produced by the tests.yml `coverage-floors` job: the FULL suite under
subprocess-aware coverage, signer SDK installed so the live harness
contributes) and fails if any floored file drops below its floor.

DOCTRINE:
  * Floors sit ~2 points under the MEASURED value at the time they were set
    (2026-07-29, suite=274, SDK present) — ordinary line drift passes, a
    deleted test file or a big untested addition trips.
  * Floors only RATCHET UP. When a file's coverage durably rises, raise its
    floor in the same PR that raised it. Never lower a floor to ship —
    lowering is an operator decision with a CHANGELOG entry.
  * Files with no meaningful tests yet (marks, shadow, hl_client, the
    render() body) are DELIBERATELY absent: a floor is a ratchet on ground
    already held, not an aspiration. Add the file WITH its first tests.

Exit 0 = all floors held (prints the table). Exit 1 = breaches, named.
`--selftest` proves the detector can still see (fixture with a breach).
"""
import json
import sys
from pathlib import Path

# repo-relative file -> minimum line-coverage percent
FLOORS = {
    # the two live real-money bots
    "lighter_ticket_taker.py": 90,     # measured 92 (the --selftest-live harness)
    # [2026-07-30] 45 -> 50. Finding 14 of the coverage second pass: the (en)
    # exit-ladder and (eq) flatten seams raised this file ~6pp and NEITHER
    # raised the floor, leaving 7.7pp of slack on the LIVE real-money bot —
    # a change could have deleted every assertion those seams added and CI
    # would still have passed green. Doctrine is "raise the floor in the same
    # PR that raised the coverage"; this is that raise, late.
    "lighter_funding_bot.py": 50,      # measured 52.7
    # the shared real-money surface
    "venues/safety.py": 92,            # measured 94
    "venues/equity_guard.py": 93,      # measured 95
    "venues/lighter_client.py": 63,    # measured 65
    "venues/__init__.py": 86,          # measured 88
    "venues/governor.py": 77,          # measured 79
    "venues/fills.py": 62,             # measured 64
    "venues/symbol_map.py": 95,        # measured 100 (12 stmts; one lost line trips)
    # [2026-07-29 (eo)] Finding 6 completed — the promotion-evidence fill
    # model and the shared mid helpers gained their tests and enter the
    # ratchet at 95 (both measured 100; small files, 1-2 lines of slack).
    "venues/shadow.py": 95,            # measured 100 — every -lshadow curve's fills
    "venues/marks.py": 95,             # measured 100 — the equity guard's mid
    "funding_basis.py": 93,            # measured 95 (the 8x anchor)
    # the money pipeline + enforcement organs
    "bot_pnl_store.py": 40,            # measured 42
    "pnl_dashboard.py": 13,            # measured 15
    "fleet_risk.py": 37,               # measured 39
    "fleet_bus.py": 88,                # measured 90
    "fleet_tuning.py": 87,             # measured 89
    "brain_stats.py": 96,              # measured 98
    "paper_broker.py": 97,             # measured 99
    # [2026-07-30 THE SHADOW BOOKS] These six had no pytest tier at all until
    # they gained growth-rail levers, a widened universe and (Snap Back) an
    # adaptive gate. They enter the ratchet WITH their first tests, per the
    # doctrine above — a floor is ground held, never an aspiration. They are
    # $1k shadow books, so these floors protect EVIDENCE quality rather than
    # real money: every one of these curves feeds the brain, the risk light
    # and ultimately a go-live decision.
    "funding_carry_bot.py": 35,        # measured 37.5 — the fleet's best book
    "lighter_funding_spread_bot.py": 38,   # measured 40.0
    "lighter_dislocation_bot.py": 36,  # measured 38.8 (was 27 before the gate work)
    "lighter_index_bot.py": 32,        # measured 34.6
    "lighter_perp_sniper.py": 81,      # measured 83.5
    "lighter_market_scout.py": 80,     # measured 82.5 — the fleet's signal source
}


def _percent(entry):
    s = entry.get("summary") or {}
    if s.get("percent_covered") is not None:
        return float(s["percent_covered"])
    st = s.get("num_statements") or 0
    return 100.0 if not st else 100.0 * float(s.get("covered_lines") or 0) / st


def check(path="coverage.json"):
    try:
        doc = json.loads(Path(path).read_text())
    except OSError as e:
        print(f"FLOORS: cannot read {path}: {e}")
        print("(this guard only runs where the coverage job produced one)")
        return 1
    files = doc.get("files") or {}

    def find(rel):
        # coverage keys may be absolute or relative — match on the suffix
        for k, v in files.items():
            kk = k.replace("\\", "/")
            if kk == rel or kk.endswith("/" + rel):
                return v
        return None

    breaches, rows = [], []
    for rel, floor in sorted(FLOORS.items()):
        entry = find(rel)
        if entry is None:
            # a floored file MISSING from the measurement is itself a breach —
            # else deleting/renaming the file silently deletes its floor
            breaches.append(f"{rel}: NOT MEASURED (floor {floor})")
            rows.append((rel, None, floor))
            continue
        pct = _percent(entry)
        rows.append((rel, pct, floor))
        if pct < floor:
            breaches.append(f"{rel}: {pct:.1f}% < floor {floor}%")

    width = max(len(r) for r, _, _ in rows)
    for rel, pct, floor in rows:
        shown = "  MISSING" if pct is None else f"{pct:7.1f}%"
        flag = "  BREACH" if (pct is None or pct < floor) else ""
        print(f"  {rel:<{width}}  {shown}  (floor {floor}%){flag}")
    if breaches:
        print("\nFLOORS BREACHED — the real-money surface only ratchets UP:")
        for b in breaches:
            print(f"  {b}")
        print("Add tests to restore the floor; lowering one is an operator "
              "decision with a CHANGELOG entry.")
        return 1
    print(f"\nFLOORS: all {len(FLOORS)} held.")
    return 0


def _selftest():
    """The detector must still see a breach, a hold, and a missing file."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        good = {rel: 99.0 for rel in FLOORS}
        fx = Path(td) / "cov.json"

        def write(percents, drop=None):
            files = {
                f"/repo/{rel}": {"summary": {"percent_covered": p,
                                             "num_statements": 100,
                                             "covered_lines": int(p)}}
                for rel, p in percents.items() if rel != drop}
            fx.write_text(json.dumps({"files": files}))

        write(good)
        assert check(str(fx)) == 0, "all-above-floor must pass"
        bad = dict(good)
        bad["venues/safety.py"] = 10.0
        write(bad)
        assert check(str(fx)) == 1, "a floored file below floor must fail"
        write(good, drop="lighter_ticket_taker.py")
        assert check(str(fx)) == 1, "a floored file MISSING must fail"
    print("audit_coverage_floors --selftest OK (breach + hold + missing all seen)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "coverage.json"))
