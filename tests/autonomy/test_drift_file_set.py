#!/usr/bin/env python3
"""[2026-09-02 (xf)] A DIFFERENT FILE SET IS NOT DRIFT — and claiming it as
drift had jammed the fleet's only path from shadow evidence to real money.

MEASURED, 2-Sep, on 👩 mum's live ledger. The 🧪 judge's lane moved to her at
(ww) that morning; from that moment every evaluation returned:

    "ARMS ON DIFFERENT CODE: live=733ee8665875 shadow=f009aec2315f —
     this window measures a code delta, not edge; no promotion can rest on it"

Her arms run from DIFFERENT IMAGES: the live arm from `Dockerfile.avolive`
(build_n 17), the shadow twin inside the freqtrade image (build_n 14-16). And
`build_compute` hashes only the `_BUILD_SHARED` names that EXIST in an image
((fd)) — so the two digests are computed over different file sets and **can
never be equal, by construction and forever**. Over her whole ledger:

    live   {4 digests}  all build_n 17
    shadow {9 digests}  build_n in {14, 15, 16}
    intersection: EMPTY

So the sensor was structurally stuck ON, and `paired_eval` holds on it. The
class was already known and already handled elsewhere — `scripts/
evidence_review.arm_drift_line` has deferred with "arms differ on FILE SET,
not necessarily code" since 2026-08-01 — the judge's two sensors simply never
got the rule. `implementation_shortfall.stamps_comparable` is now the ONE
owner of the question ((hj)).

THE FIX IS FAIL-SAFE IN THE SENSOR'S OWN DIRECTION. Its contract is "we only
ever claim drift on POSITIVE evidence"; a digest pair that cannot answer the
question is not positive evidence, so it degrades to SILENCE exactly as an
unstamped arm does. What it must NOT do is go quietly blind — so the verdict
now publishes `arm_drift_basis` ("agree" | "drift" | "file-set" | "unstamped")
and a permanent blind spot is readable on the row (I18).

THE TESTS:
  1-4  `stamps_comparable`: only a KNOWN mismatch defers; unknown/junk counts
       compare exactly as before, so the sensor is never disarmed by a legacy
       row that predates `build_n`;
  5-6  the CONTAINER half (`implementation_shortfall.arm_drift`) on mum's real
       shape and on genuine same-file-set drift;
  7-9  the ROW half (`experiment_judge._row_drift`) likewise, plus the case
       that must keep working: a shared digest is still "same deploy line";
  10   the REGRESSION, driven on mum's real ledger shape — the exact rows that
       jammed her lane no longer claim drift;
  11-13 `drift_basis` names all four states, so "file-set" is never published
       as the same byte-string as "agree";
  14   a genuine drift on a SAME-file-set pair still holds a promotion — the
       positive control, because a gate that never fires is trivially safe and
       useless (I3 applied to a gate).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import experiment_judge as J                    # noqa: E402
import implementation_shortfall as I            # noqa: E402

LIVE, SHADOW = J.LIVE_BOT, J.SHADOW_BOT


def _row(bot, build, n=None, **extra):
    e = {"build": build}
    if n is not None:
        e["build_n"] = n
    e.update(extra)
    return {"bot": bot, "extra": e}


# ---- 1-4  the owner: only a KNOWN mismatch defers --------------------------

def test_equal_counts_are_comparable():
    assert I.stamps_comparable(15, 15) is True
    assert I.stamps_comparable("15", 15) is True      # str/int mix


def test_a_known_mismatch_is_not_comparable():
    assert I.stamps_comparable(17, 16) is False
    assert I.stamps_comparable(15, 14) is False


def test_an_unknown_count_still_compares():
    """A missing `build_n` is the pre-(fd) shape. Refusing to compare there
    would silently disarm the sensor on every legacy row — the dead-sensor
    failure this repo has already paid for."""
    assert I.stamps_comparable(None, 15) is True
    assert I.stamps_comparable(15, None) is True
    assert I.stamps_comparable(None, None) is True


def test_a_junk_count_does_not_disarm_the_sensor():
    for junk in ("nonsense", [], {}, object()):
        assert I.stamps_comparable(junk, 15) is True, junk
        assert I.stamps_comparable(15, junk) is True, junk


# ---- 5-6  the CONTAINER half -----------------------------------------------

def test_the_container_sensor_no_longer_claims_drift_across_two_images():
    got = I.arm_drift([_row(LIVE, "08147b6bc9fb", 17),
                       _row(SHADOW, "f009aec2315f", 16)],
                      live=LIVE, shadow=SHADOW)
    assert got is None, got


def test_the_container_sensor_still_claims_genuine_drift():
    got = I.arm_drift([_row(LIVE, "aaaaaaaaaaaa", 15),
                       _row(SHADOW, "bbbbbbbbbbbb", 15)],
                      live=LIVE, shadow=SHADOW)
    assert got == {"live": "aaaaaaaaaaaa", "shadow": "bbbbbbbbbbbb"}, got


# ---- 7-9  the ROW half ------------------------------------------------------

def test_the_row_sensor_no_longer_claims_drift_across_two_images():
    rows = [_row(LIVE, "08147b6bc9fb", 17), _row(LIVE, "56bb4e8ff3c2", 17),
            _row(SHADOW, "f009aec2315f", 16), _row(SHADOW, "4d93497e56d5", 15)]
    assert J._row_drift(rows, LIVE, SHADOW) is None


def test_the_row_sensor_still_claims_drift_within_one_file_set():
    rows = [_row(LIVE, "aaaaaaaaaaaa", 15), _row(SHADOW, "bbbbbbbbbbbb", 15)]
    got = J._row_drift(rows, LIVE, SHADOW)
    assert got and got["source"] == "rows-disjoint", got


def test_a_shared_digest_is_still_the_same_deploy_line():
    rows = [_row(LIVE, "aaaaaaaaaaaa", 15), _row(LIVE, "cccccccccccc", 15),
            _row(SHADOW, "aaaaaaaaaaaa", 15)]
    assert J._row_drift(rows, LIVE, SHADOW) is None


# ---- 10  the regression, on the shape that actually jammed the lane --------

def test_mums_real_ledger_shape_no_longer_jams_her_lane():
    """The measured 2-Sep sets: live all n=17, shadow n in {14,15,16}, zero
    digest overlap. Before (xf) this returned a claim on every window and
    `paired_eval` held every evaluation."""
    live_ids = ["56bb4e8ff3c2", "733ee8665875", "a48641f9c8d0", "fa4c0b99acb8"]
    shadow = [("4d93497e56d5", 15), ("276cb77076aa", 15), ("f009aec2315f", 16),
              ("bb509109a039", 15), ("cdf4d75c9f19", 15), ("9e1c1a91443e", 14)]
    rows = [_row(LIVE, b, 17) for b in live_ids] + \
           [_row(SHADOW, b, n) for b, n in shadow]
    assert J._row_drift(rows, LIVE, SHADOW) is None
    assert J.drift_basis(rows, LIVE, SHADOW) == "file-set"


# ---- 11-13  the basis names every state ------------------------------------

def test_the_basis_distinguishes_a_blind_spot_from_agreement():
    blind = [_row(LIVE, "aaa", 17), _row(SHADOW, "bbb", 16)]
    agree = [_row(LIVE, "aaa", 15), _row(SHADOW, "aaa", 15)]
    assert J.drift_basis(blind, LIVE, SHADOW) == "file-set"
    assert J.drift_basis(agree, LIVE, SHADOW) == "agree"
    assert J.drift_basis(blind, LIVE, SHADOW) != J.drift_basis(agree, LIVE, SHADOW)


def test_the_basis_names_genuine_drift_and_unstamped_rows():
    drift = [_row(LIVE, "aaa", 15), _row(SHADOW, "bbb", 15)]
    assert J.drift_basis(drift, LIVE, SHADOW) == "drift"
    assert J.drift_basis([{"bot": LIVE, "extra": {}},
                          {"bot": SHADOW, "extra": {}}], LIVE, SHADOW) == "unstamped"
    assert J.drift_basis([], LIVE, SHADOW) == "unstamped"


def test_the_basis_is_reported_never_gated():
    """Nothing may branch on the receipt — it records a verdict reached
    elsewhere. Pinned by source so a future edit cannot quietly make it a
    gate."""
    import inspect
    src = inspect.getsource(J)
    for bad in ("if drift_basis(", 'if v["arm_drift_basis"]',
                "if basis ==", "arm_drift_basis ==",
                'v.get("arm_drift_basis")'):
        assert bad not in src, f"the basis became a gate: {bad}"


# ---- 14-15  a MIXED-stamp arm must not crash the judge ---------------------

def test_a_mid_rollout_arm_with_mixed_stamps_does_not_crash_the_judge():
    """An arm's rows carry `build_n` only from the deploy that added it, so a
    real window mixes stamped and unstamped rows. Keying the build sets by
    count made `sorted()` compare None with an int — TypeError raised INSIDE
    `_row_drift`, i.e. inside the judge's own evaluation, on a shape that
    occurs during any rollout. Found by driving the case; the fix sorts the
    IDS, which is also byte-identical to the pre-(xf) return."""
    rows = [_row(LIVE, "aaa"), _row(LIVE, "bbb", 15),
            _row(SHADOW, "ccc"), _row(SHADOW, "ddd", 15)]
    got = J._row_drift(rows, LIVE, SHADOW)          # must not raise
    assert got and got["source"] == "rows-disjoint", got
    assert J.drift_basis(rows, LIVE, SHADOW) == "drift"


def test_wholly_unstamped_arms_behave_exactly_as_before():
    rows = [_row(LIVE, "aaa"), _row(SHADOW, "ccc")]
    got = J._row_drift(rows, LIVE, SHADOW)
    assert got == {"live": "aaa", "shadow": "ccc", "source": "rows-disjoint"}, got


# ---- 16-18  DEFECTS AN ADVERSARIAL REVIEW FOUND IN THE FIRST CUT -----------

def test_a_shared_DIGEST_is_agreement_even_when_the_counts_differ():
    """The first cut keyed the build sets by (count, digest) and then
    intersected the PAIRS — so two arms publishing the SAME digest under
    different counts stopped reading as one deploy line, re-creating the very
    false hold this change exists to remove. Agreement is a property of the
    DIGEST alone."""
    rows = [_row(LIVE, "aaaaaaaaaaaa", 15), _row(SHADOW, "aaaaaaaaaaaa", 16)]
    assert J._row_drift(rows, LIVE, SHADOW) is None
    assert J.drift_basis(rows, LIVE, SHADOW) == "agree"


def test_comparability_goes_through_the_declared_owner():
    """`_row_drift` open-coded its own shared-count test in the first cut — a
    second copy of a rule that disagreed with the owner (it disarmed on unknown
    counts, which `stamps_comparable` declares must not happen). Driven by
    swapping the owner out: the judge's verdict must follow it."""
    import implementation_shortfall as isf
    rows = [_row(LIVE, "aaa", 17), _row(SHADOW, "bbb", 16)]
    assert J._row_drift(rows, LIVE, SHADOW) is None          # owner says no
    real = isf.stamps_comparable
    try:
        isf.stamps_comparable = lambda a, b: True            # owner says yes
        assert J._row_drift(rows, LIVE, SHADOW) is not None
    finally:
        isf.stamps_comparable = real
    assert J._row_drift(rows, LIVE, SHADOW) is None


def test_the_claim_and_the_receipt_come_from_one_read():
    """They are returned by the same pass, so they can never describe
    different samples."""
    for rows, want_claim, want_basis in (
            ([_row(LIVE, "aaa", 15), _row(SHADOW, "bbb", 15)], True, "drift"),
            ([_row(LIVE, "aaa", 17), _row(SHADOW, "bbb", 16)], False, "file-set"),
            ([_row(LIVE, "aaa", 15), _row(SHADOW, "aaa", 15)], False, "agree"),
            ([], False, "unstamped")):
        claim, basis = J._row_drift_verdict(rows, LIVE, SHADOW)
        assert bool(claim) is want_claim and basis == want_basis, (rows, basis)
        assert J._row_drift(rows, LIVE, SHADOW) == claim
        assert J.drift_basis(rows, LIVE, SHADOW) == basis


# ---- 19  the positive control: a real drift still holds a promotion --------

def test_a_same_file_set_drift_still_holds_the_promotion():
    """A gate that never fires is trivially stable and useless. This drives
    `paired_eval` itself: same build_n, different digests -> the hold stands."""
    rows = [_row(LIVE, "aaaaaaaaaaaa", 15), _row(SHADOW, "bbbbbbbbbbbb", 15)]
    drift = J._row_drift(rows, LIVE, SHADOW)
    assert drift, "fixture must produce a genuine drift claim"
    v = J.paired_eval(rows, 0, 10 ** 12, shadow_bot=SHADOW, live_bot=LIVE,
                      drift=drift)
    assert v.get("promote") is False
    assert v.get("arm_drift") == drift
    assert "ARMS ON DIFFERENT CODE" in (v.get("why") or "")
    assert v.get("arm_drift_basis") == "drift"
