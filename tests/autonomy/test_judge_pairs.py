"""[2026-08-25 (ti)] JUDGE V2.0 — the pair registry's fleet-scoped roster.

F5's class is "real money exists outside the judge's frame", and the audit's
finding was that a host-scoped roster (importing one host's _BOOKS) can only
see live books born on THAT host. The fleet-scoped source a go-live cannot
avoid is the deploy layer: every real-money service is marker-gated in
scripts/fleet_books.MARKER_GATED. So the roster rule is: every marker-gated
LIVE row resolves to a JUDGED_PAIRS live_bot, or RETIRED_LIVE_ARMS, or a
declared UNJUDGED_OK reason — a new live book cannot ship unjudged without
someone writing a sentence saying why.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fleet_bus  # noqa: E402
import fleet_books  # noqa: E402


def _live_rows():
    return [r for r in fleet_books.MARKER_GATED
            if not r.endswith("-lshadow")]


def test_every_marker_gated_live_row_is_judged_or_declared():
    judged = {p["live_bot"] for p in fleet_bus.JUDGED_PAIRS.values()}
    retired = set(fleet_bus.RETIRED_LIVE_ARMS)
    declared = set(fleet_bus.UNJUDGED_OK)
    missing = [r for r in _live_rows()
               if r not in judged | retired | declared]
    assert not missing, (
        f"live rows outside the judge's frame with no declared reason: "
        f"{missing} — add a JUDGED_PAIRS entry or an UNJUDGED_OK reason")


def test_the_declared_exemptions_carry_real_reasons():
    for row, why in fleet_bus.UNJUDGED_OK.items():
        assert isinstance(why, str) and len(why) >= 20, (row, why)


def test_the_roster_mechanism_is_not_vacuous():
    """Inject a synthetic live row the registry does not know: the roster
    check must FLAG it (the STALE_WRITER_OK lesson — an arm reading an empty
    live dict goes vacuously green the day it empties)."""
    judged = {p["live_bot"] for p in fleet_bus.JUDGED_PAIRS.values()}
    retired = set(fleet_bus.RETIRED_LIVE_ARMS)
    declared = set(fleet_bus.UNJUDGED_OK)
    ghost = "freqtrade-ghost-lighter"
    assert ghost not in judged | retired | declared
    missing = [r for r in _live_rows() + [ghost]
               if r not in judged | retired | declared]
    assert missing == [ghost], missing


def test_declared_live_trio_is_fully_judged():
    """The three DECLARED_LIVE real-money rows must each be a pair's
    live_bot — not exempted, not retired: these are the books the judge
    exists to grow."""
    judged = {p["live_bot"] for p in fleet_bus.JUDGED_PAIRS.values()}
    for row in fleet_books.DECLARED_LIVE:
        assert row in judged, (
            f"{row} is DECLARED_LIVE but no JUDGED_PAIRS entry names it")


def test_pair_shapes():
    for pid, p in fleet_bus.JUDGED_PAIRS.items():
        assert p["pnl_form"] in ("price", "funding"), (pid, p["pnl_form"])
        assert p["shadow_bot"].endswith("-lshadow"), pid
        assert p["xp_prefix"].startswith("xp.") and \
            p["xp_prefix"].endswith("."), pid
        assert p["policy_fields"], pid
        assert isinstance(p["growth"], dict), (
            pid, "growth must be a dict — EMPTY means the fast path is "
                 "structurally unreachable for this pair, never just off")


def test_vocabulary_is_complete_and_owned_by_the_bus():
    assert set(fleet_bus.XP_JUDGE_PHASES) == {
        "idle", "running", "promoted", "stood_down", "unjudgeable"}
    assert "floors" in fleet_bus.XP_JUDGE_HOLDS
    assert {"policy_unstamped", "policy_mismatch", "capacity_mismatch",
            "parity_unreadable", "live_row_dark"} <= \
        set(fleet_bus.XP_JUDGE_UNJUDGEABLE)


def test_immune_validates_pairs_against_the_imported_vocabulary():
    """The F4 closure driven end-to-end: a fresh xp-judge payload whose PAIR
    phase is outside the vocabulary is flagged sick; the same payload with
    every phase inside the vocabulary — per-pair stood_down and unjudgeable
    included — is QUIET (the (tc) negative control, extended to the map)."""
    import fleet_immune as im
    now = im.now_ts() if hasattr(im, "now_ts") else __import__("time").time()

    def _xp(pair_phase):
        return {"xp-judge": {
            "updated": im._iso(now), "ttl_sec": 10800, "phase": "stood_down",
            "pairs": {"georgia": {"phase": pair_phase},
                      "farmer": {"phase": "stood_down"}}}}

    bad = im.organ_invariants(_xp("promoted-ish"), now)
    assert any("georgia" in s["detail"] and "promoted-ish" in s["detail"]
               for s in bad), bad
    ok = im.organ_invariants(_xp("unjudgeable"), now)
    assert not any("unknown phase" in s["detail"] for s in ok), ok
