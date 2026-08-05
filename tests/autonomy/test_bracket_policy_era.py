"""[2026-08-06 (km)] THE GATE NOW READS THE BRACKET 💸 THE FARMER ALREADY STAMPS.

`(kg)` measured the most expensive way this fleet could be wrong about real
money: **truncation collapses variance faster than it collapses the mean, so a
tight take-profit does not lower `t` — it INFLATES it.** At TP=0.28% the live
Farmer reads **85.9% win and t=+2.55, PASSING the t>=2.0 bar**, on a book
earning **$2.36 instead of $6.46**. `(kg)` published the money beside the bars
so the damage is visible, and escalated the question of whether to make it
BLOCKING, because a gate re-spec is an operator act.

THE ANSWER SHIPPED HERE IS NOT A SEVENTH BAR. A `net_usd > 0` bar is already
implied by the existing `mean > 0` bar and would change no verdict on any book;
the truncated Farmer still earns +$1.95. What has teeth is the ERA: a bracket
change must earn its OWN 30 days instead of inheriting 62 closes.

AND THE TELEMETRY WAS ALREADY THERE. The Farmer has stamped `extra.bars` with
`bars_basis: "entry"` on every close for weeks — the exact keyed-on-the-OPEN
basis the era doctrine requires. The gate simply never read it. No change to a
real-money bot, no marker deploy: this is grader-side only.

MEASURED BEFORE SHIPPING, on the public ledger: the bracket is CONSTANT across
all 63 Farmer closes in the 7-day window (`take_profit 0.04, max_hold_h 72.0`),
so reading it produces **no boundary** and the live arm's era, sample and 4/6
standing are untouched. This arms a guard; it does not move a verdict.

LIMIT, stated rather than discovered later: that window covers 26 of the live
arm's 62 in-era closes. If the bracket DID change in the older 36, a boundary
will fire and correctly shrink the era — the current 4/6 would then have been
pooling two policies, and shrinking it is the honest outcome.
"""
import pathlib
import sys

from datetime import datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g  # noqa: E402


def farmer(tp=0.04, max_hold=72.0, **tuning):
    """A Farmer close row's `extra`, in the shape the bot really emits."""
    bars = {"enter_apr": 0.05, "take_profit": tp, "max_hold_h": max_hold,
            "min_vol": 1e7, "slope_gate": 1, "explore_k": 0}
    bars.update(tuning)
    return {"bars_basis": "entry", "bars": bars, "svc": "trail-blazer-live"}


LEGACY = {"bars_basis": "close-legacy", "bars": {"take_profit": 0.04}}

TAKER = {"policy": {"venue": "lighter_live", "bull": True,
                    "lenses": ["divergence"], "sides": ["short"]},
         "bars_basis": "entry", "bars": {"take_profit": 0.04}}


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


class TestTheKgAttackNowRestartsTheClock:
    def test_a_take_profit_cut_is_a_new_era(self):
        """The exact (kg) move: TP 4% -> 0.28%, which reads 85.9% win and
        t=+2.55 while destroying 63-88% of the book's money."""
        ep, iso, _, n = g.stamped_policy_boundary(
            _rows([farmer(0.04)] * 15 + [farmer(0.0028)] * 5))
        assert ep is not None, (
            "a bracket change inherited the old sample — the truncated book "
            "would pass the t bar on 62 closes it did not earn")
        assert n == 5, n

    def test_a_max_hold_change_is_also_a_bracket_change(self):
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([farmer(max_hold=72.0)] * 8 + [farmer(max_hold=6.0)] * 3))
        assert ep is not None

    def test_the_degenerate_limit_is_caught_too(self):
        """(kg)'s limit case: TP=0.05% gives win 100%, maxDD ~0, t=6.1e15."""
        ep, _, _, n = g.stamped_policy_boundary(
            _rows([farmer(0.04)] * 30 + [farmer(0.0005)] * 2))
        assert ep is not None and n == 2


class TestOrdinaryTuningMustNotResetIt:
    """(hc): the growth rail moves levers daily BY DESIGN. Resetting the clock
    on each one makes the 30-day bar unreachable forever — which would be a
    worse failure than the one this guards, because it is silent."""

    @pytest.mark.parametrize("field,value", [
        ("enter_apr", 0.30),      # the judge's promoted lever
        ("min_vol", 1e5),         # (ka)/(jy) thin-tier floor
        ("slope_gate", 0),
        ("explore_k", 3),
        ("conviction_hi", 2.2),
    ])
    def test_a_tuning_field_is_not_a_policy_change(self, field, value):
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([farmer()] * 10 + [farmer(**{field: value})] * 6))
        assert ep is None, (
            f"{field} reset the era — it is ordinary tuning ((hc)) and the "
            "gate would become unreachable")

    def test_the_signature_names_only_the_bracket(self):
        assert set(g.BRACKET_SIG_FIELDS) == {"take_profit", "max_hold_h"}


class TestAdoptionAndPrecedence:
    def test_legacy_rows_are_pre_adoption_not_a_change(self):
        """`close-legacy` carries the bars ACTIVE AT CLOSE, which cannot say
        what policy the trade was TAKEN under. Treating it as unreadable would
        manufacture a boundary on every legacy row — the (kk) bug."""
        assert g.stamp_state(LEGACY) is g.ABSENT
        ep, _, _, _ = g.stamped_policy_boundary(
            _rows([LEGACY] * 8 + [farmer()] * 4))
        assert ep is None

    def test_an_explicit_policy_block_still_wins(self):
        """🎫 the Taker stamps BOTH. Its explicit policy is the deliberate
        statement and must outrank a bracket inferred from telemetry."""
        st = g.stamp_state(TAKER)
        assert "lenses" in st and "bracket" not in st

    def test_a_book_that_stamps_neither_is_absent(self):
        assert g.stamp_state({"svc": "x"}) is g.ABSENT
        assert g.stamp_state(None) is g.ABSENT

    def test_a_malformed_bars_stamp_is_still_fail_closed(self):
        assert g.stamp_state({"bars_basis": "entry", "bars": "junk"}) is None
        assert g.stamp_state({"bars_basis": "entry", "bars": {}}) is None
        assert g.stamp_state(
            {"bars_basis": "entry", "bars": {"enter_apr": 0.05}}) is None


class TestItDoesNotMoveTodaysVerdict:
    def test_a_constant_bracket_yields_no_boundary(self):
        """The measured live shape: 63 closes, one bracket. The Farmer's era,
        sample and 4/6 standing are untouched by this change."""
        ep, iso, pol, n = g.stamped_policy_boundary(_rows([farmer()] * 25))
        assert ep is None and iso is None
        assert pol is not None, "the policy is KNOWN, just unchanged"

    def test_the_graders_own_selftest_still_passes(self):
        g._selftest()
