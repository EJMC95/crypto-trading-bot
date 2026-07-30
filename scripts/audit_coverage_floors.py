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
    # [2026-07-30 (gp)] 50 -> 52. The (gm) book-gate tests took this file to
    # 54.9% (measured CI's way — subprocess-aware, combined) and took
    # `book_metrics` + `vwap_slip` from "only the def line" to fully covered.
    # Raised in the same pass that raised the coverage, which is the doctrine
    # the note below records being violated once already. What this floor now
    # protects specifically: the negative-price fail-open fix, the defensive
    # sort, and the None-means-thin contract on the LIVE Farmer's entry gate.
    "lighter_funding_bot.py": 52,      # measured 54.9
    # [2026-07-30] 45 -> 50. Finding 14 of the coverage second pass: the (en)
    # exit-ladder and (eq) flatten seams raised this file ~6pp and NEITHER
    # raised the floor, leaving 7.7pp of slack on the LIVE real-money bot —
    # a change could have deleted every assertion those seams added and CI
    # would still have passed green. Doctrine is "raise the floor in the same
    # PR that raised the coverage"; this is that raise, late.
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
    # [2026-07-30] THE PROMOTION SURFACE — the code deciding which $1k shadow
    # book gets offered up for real money. Floored for the same reason as the
    # books above: it governs a real-money decision without being real-money
    # code. Incident: on 30-Jul the daily review published ⚖️ Counterweight as
    # CLEARING the go-live gate on win rate 56.1% when its t is 0.65, and
    # REJECTED 🌾 carry (t=2.60, the fleet's best-evidenced book) on win rate
    # 40.2% — because `evidence_review` carried its OWN copy of the rule the
    # (fk) re-spec had replaced the day before. It now IMPORTS the gate from
    # `golive_readiness`; these floors hold the tests that pin that.
    "scripts/golive_readiness.py": 67,  # measured 69.4 — the canonical gate
    "scripts/evidence_review.py": 49,   # measured 51.0 — its daily consumer
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
        # [2026-07-30 (hi)] DISTINGUISH "no coverage data" FROM "a real breach".
        # When EVERY floored file reads NOT MEASURED, the coverage run simply
        # never happened — the report is empty, not the tests. The old message
        # said "Add tests to restore the floor" in that case, which sends a
        # reader hunting for missing tests that exist. Still exits NON-ZERO,
        # deliberately: in CI a missing measurement IS a broken guard, and a
        # guard that passes when it measured nothing is the failure mode this
        # whole file exists to prevent. Only the DIAGNOSIS changes.
        # THE CONDITION HAS TO SEPARATE TWO THINGS, and my first two attempts
        # each got one of them wrong:
        #   * a STALE/EMPTY report (this worktree held an artifact measuring
        #     exactly ONE module at 10.6%) — not a breach, a missing run;
        #   * a DELETED or RENAMED floored file, where 24 of 25 are measured —
        #     that IS a breach, and excusing it would let removing a file
        #     silently remove its floor, which this guard's own comment calls out.
        # `all(pct is None)` missed the first (one floor read as a real breach);
        # `len(files) < len(FLOORS)` broke the second (the synthetic fixture
        # writes only the floored files, so dropping one tripped the excuse).
        # The invariant that holds for both: a report which measured FEWER THAN
        # HALF the floored files cannot be speaking to the floors at all.
        _measured = sum(1 for _r, p, _f in rows if p is not None)
        if _measured * 2 < len(FLOORS):
            print(f"\nPARTIAL OR ABSENT COVERAGE DATA — only {_measured} of "
                  f"{len(FLOORS)} floored files are in the report ({len(files)} "
                  f"file(s) total), so it cannot speak to the floors. This is an "
                  f"EMPTY/STALE REPORT, not a breach.")
            print("Generate it the way CI does (subprocess-aware, or the "
                  "--selftest blocks driven as subprocesses are invisible):")
            print("  COVERAGE_PROCESS_START=.coveragerc coverage run "
                  "--source=. -m pytest tests/ -q && coverage json")
            print("Then re-run this audit. Exiting non-zero: a coverage guard "
                  "that passes without measuring anything is not a guard.")
            return 1
        print("\nFLOORS BREACHED — the real-money surface only ratchets UP:")
        for b in breaches:
            print(f"  {b}")
        print("Add tests to restore the floor; lowering one is an operator "
              "decision with a CHANGELOG entry.")
        return 1
    print(f"\nFLOORS: all {len(FLOORS)} held.")
    return 0


def _selftest():
    """The detector must see a breach, a hold, a missing file — and, since
    2026-07-30 (hi), must DIAGNOSE a stale report differently from a breach.

    The exit-code assertions alone could not test that: both cases exit 1, so a
    misdiagnosis passes silently. That is precisely the hole the (hi) change
    exists to close, and it was open in this selftest until now — so the message
    is asserted too."""
    import contextlib
    import io
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

        def run():
            """(exit_code, stdout) — the verdict AND the diagnosis."""
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check(str(fx))
            return rc, buf.getvalue()

        write(good)
        assert run()[0] == 0, "all-above-floor must pass"
        bad = dict(good)
        bad["venues/safety.py"] = 10.0
        write(bad)
        rc, out = run()
        assert rc == 1, "a floored file below floor must fail"
        assert "FLOORS BREACHED" in out and "PARTIAL" not in out, out[-400:]

        # A DELETED/RENAMED floored file is a BREACH, not an excused report —
        # else removing a file silently removes its floor. 24 of 25 measured.
        write(good, drop="lighter_ticket_taker.py")
        rc, out = run()
        assert rc == 1, "a floored file MISSING must fail"
        assert "FLOORS BREACHED" in out, "a deleted floor must read as a BREACH"
        assert "PARTIAL" not in out, (
            "dropping ONE floored file was misdiagnosed as a stale report — the "
            "excuse would then hide every rename")

        # A STALE/PARTIAL report (one module, the shape this worktree actually
        # held) must be diagnosed as missing DATA and still exit non-zero: a
        # coverage guard that passes without measuring anything is not a guard.
        write({"lighter_funding_bot.py": 10.6})
        rc, out = run()
        assert rc == 1, "an empty report must still fail closed"
        assert "PARTIAL OR ABSENT COVERAGE DATA" in out, out[-400:]
        assert "FLOORS BREACHED" not in out, (
            "a stale report was reported as a breach — this sends the reader "
            "hunting for tests that already exist")
        assert "coverage run" in out, "say how to generate the data"
    print("audit_coverage_floors --selftest OK (breach + hold + missing "
          "+ stale-vs-breach diagnosis)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "coverage.json"))
