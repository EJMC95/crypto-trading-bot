"""[2026-08-06 (kk)] `(jf)`'s MECHANICAL POLICY CLOCK WAS UN-ADOPTABLE.

`stamped_policy_boundary` derives a book's era from its own `extra.policy`
stamps: the era is the maximal same-signature SUFFIX of the ledger. Rows whose
stamp cannot be read break the run, fail-closed — correct, and the reason the
gate can trust a stamp at all.

THE DEFECT: `policy_signature` returned None for BOTH "this stamp is broken"
and "this book does not stamp yet". So the first stamped close on any ADOPTING
book read as a policy CHANGE, and the boundary landed on it.

MEASURED on the live payload the morning this was found: 💸 the Funding Farmer
is the fleet's ONLY 4/6 book and the only one with a realistic path to the gate
(~178 in-era closes needed for t>=2.0, ~5-Sep at its current rate). Giving it a
policy stamp would have set its era to that morning and discarded **62 of its
62 in-era closes** — 4/6 bars to ~1/6, gate date to nowhere. The change that
was supposed to PROTECT the gate would have destroyed its only candidate.

🎫 the Ticket Taker survived adoption on 30-Jul only because its DECLARED era
happened to coincide with the stamp's arrival, so `max(declared, stamped)`
masked the spurious boundary. One book adopting cleanly was luck, not design.

THE RULE: **an absence is not a change** (I6). A malformed stamp still is.
"""
import pathlib
import sys

from datetime import datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g  # noqa: E402


_POL_A = {"venue": "lighter_live", "bull": True,
          "lenses": ["funding"], "sides": ["short"]}
_POL_B = {"venue": "lighter_live", "bull": True,
          "lenses": ["funding"], "sides": ["long", "short"]}

STAMPED_A = {"policy": _POL_A}
STAMPED_B = {"policy": _POL_B}
UNSTAMPED = None                       # pre-adoption: no `policy` key at all
BROKEN = {"policy": {"venue": "x"}}    # present but nameless -> unreadable


def _rows(spec):
    """era_rows' shape, oldest first, with the row's `extra` at [4].

    Dates are real datetime arithmetic, NOT f"2026-07-{10+i}" — that emits
    "2026-07-34" past 25 rows, which `_era_parse` cannot read, so the walk
    breaks fail-closed and any `ep is None` assertion passes for entirely
    the wrong reason. Caught when a 25-row case went red.
    """
    base = datetime(2026, 7, 10, tzinfo=timezone.utc)
    return [(0.01, 100.0, (base + timedelta(days=i)).isoformat(), None, s)
            for i, s in enumerate(spec)]


class TestTheThreeStates:
    def test_absent_is_its_own_state(self):
        assert g.stamp_state(None) is g.ABSENT
        assert g.stamp_state({}) is g.ABSENT
        assert g.stamp_state({"svc": "x"}) is g.ABSENT

    def test_broken_is_unreadable_not_absent(self):
        assert g.stamp_state(BROKEN) is None
        assert g.stamp_state({"policy": "nonsense"}) is None
        assert g.stamp_state({"policy": {"lenses": []}}) is None

    def test_a_good_stamp_returns_a_signature(self):
        assert isinstance(g.stamp_state(STAMPED_A), str)
        assert g.stamp_state(STAMPED_A) != g.stamp_state(STAMPED_B)

    def test_policy_signature_keeps_its_two_state_contract(self):
        """Existing callers must not see the sentinel leak out."""
        assert g.policy_signature(None) is None
        assert g.policy_signature(BROKEN) is None
        assert g.policy_signature(STAMPED_A) == g.stamp_state(STAMPED_A)


class TestAdoptionDoesNotResetAnEra:
    def test_the_farmer_case_the_incident_named(self):
        """10 unstamped closes, then 3 stamped ones, policy never changed."""
        ep, iso, pol, n = g.stamped_policy_boundary(
            _rows([UNSTAMPED] * 10 + [STAMPED_A] * 3))
        assert ep is None and iso is None, (
            "adoption invented a boundary: every pre-stamp close would be "
            "discarded and the book's era would restart at the first stamp")
        assert pol is not None, "the policy is still KNOWN, just unchanged"

    def test_a_single_stamped_close_does_not_reset_anything(self):
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([UNSTAMPED] * 40 + [STAMPED_A]))
        assert ep is None


class TestARealChangeStillBites:
    """The half that must NOT be weakened — this is a real-money gate."""

    def test_a_signature_change_is_a_boundary(self):
        ep, iso, _, n = g.stamped_policy_boundary(
            _rows([STAMPED_A] * 5 + [STAMPED_B] * 4))
        assert ep is not None and n == 4, (ep, n)

    def test_a_broken_stamp_is_still_fail_closed(self):
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([STAMPED_A] * 4 + [BROKEN] + [STAMPED_A] * 3))
        assert ep is not None, "an unreadable stamp must still break the run"

    def test_a_stamp_that_vanishes_and_returns_is_not_adoption(self):
        """Adoption is an unstamped PREFIX. A gap in the middle means some
        older row IS stamped, so this is not a book taking the stamp up — it
        is a book whose telemetry dropped out, and that stays fail-closed."""
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([STAMPED_A] * 3 + [UNSTAMPED] * 2 + [STAMPED_A] * 3))
        assert ep is not None

    def test_a_change_after_adoption_is_found(self):
        """The point of adopting at all: once stamped, the NEXT real change
        must produce a boundary."""
        ep, _, _, n = g.stamped_policy_boundary(
            _rows([UNSTAMPED] * 6 + [STAMPED_A] * 3 + [STAMPED_B] * 2))
        assert ep is not None and n == 2, (ep, n)


class TestTheUnchangedControls:
    @pytest.mark.parametrize("spec,label", [
        ([STAMPED_A] * 9, "stamped throughout: no change, no boundary"),
        ([UNSTAMPED] * 9, "never stamped: stamps derive nothing"),
        ([], "empty ledger"),
    ])
    def test_prior_behaviour_is_byte_identical(self, spec, label):
        ep, iso, _, _ = g.stamped_policy_boundary(_rows(spec))
        assert ep is None and iso is None, label

    def test_the_graders_own_selftest_still_passes(self):
        """`grade` is the authority over real money; this change touches the
        sample it grades, so its own suite is part of this test's claim."""
        g._selftest()
