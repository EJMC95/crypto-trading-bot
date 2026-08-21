#!/usr/bin/env python3
"""[2026-08-21 (sr)] A DEPOSIT MUST NOT SILENTLY BUY FEWER BETS.

🙏 Avo Maria sizes `clip = equity / max_open`, so a deposit re-sizes every
future entry — correctly and automatically. Its notional cap
(`FREQTRADE_AVO_MARIA_MAX_NOTIONAL`) is a FIXED DOLLAR figure, so the same
deposit walks the clip INTO the cap and the last slot stops being fundable.

Measured live, 21-Aug: Eamon deposited $167.76; equity $62.93 -> $230.70 and
clip $15.73 -> $57.68 against an unchanged $200 cap. Three slots fit
($173.02); the fourth needs $230.70 and is refused. The book settles at 3 of
4 and **$57.68 of the new balance is never deployed**.

The failure is SILENT three ways, which is what these tests pin:
  * `open_trades` reads 3 of a declared `max_open` 4 exactly as on a quiet day;
  * the refusal is DELAYED — `open_notional` prices held positions at their OWN
    entry clip, so the legacy small positions hide the wall until they roll;
  * nothing FIRES, so a counter alone can never report it — only standing
    arithmetic can say "the cap will bite" before it does.

`cap_slots` is REPORTED, never enforced: SafetyRails caps are operator-only,
so its job is to name the constraint (I8), not to move it.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
os.environ.setdefault("AVO_VENUE", "lighter_live")

import lighter_avo_live_bot as A  # noqa: E402


# The live numbers this test was written from — kept as constants so a future
# reader can see the incident, not just the arithmetic.
LIVE_EQUITY_AFTER = 230.695248
LIVE_EQUITY_BEFORE = 62.93
LIVE_CAP = 200.0
LIVE_SLOTS = 4


def test_the_live_deposit_costs_a_slot_at_the_shipped_cap():
    """The incident itself: at the post-deposit clip the $200 cap funds 3 of 4."""
    clip = LIVE_EQUITY_AFTER / LIVE_SLOTS
    assert round(clip, 2) == 57.67 or round(clip, 2) == 57.68
    assert A.cap_slots(clip, LIVE_CAP, LIVE_SLOTS) == 3, (
        "the post-deposit clip must show the cap funding only 3 of 4 slots — "
        "this is the whole finding")


def test_the_same_cap_was_harmless_before_the_deposit():
    """Not a pre-existing defect: at the OLD clip the same cap funded all 4.

    This is what makes it a deposit-triggered failure rather than a standing
    misconfiguration, and it is why nothing ever fired before today.
    """
    clip = LIVE_EQUITY_BEFORE / LIVE_SLOTS
    assert A.cap_slots(clip, LIVE_CAP, LIVE_SLOTS) == LIVE_SLOTS


def test_raising_the_cap_restores_the_full_book():
    """The operator's fix, verified: >= equity funds every slot."""
    clip = LIVE_EQUITY_AFTER / LIVE_SLOTS
    assert A.cap_slots(clip, 231.0, LIVE_SLOTS) == LIVE_SLOTS
    assert A.cap_slots(clip, 250.0, LIVE_SLOTS) == LIVE_SLOTS


def test_a_cap_equal_to_equity_is_the_boundary():
    """clip = equity/slots means gross tops out at EXACTLY equity, so a cap at
    equity is the smallest one that never binds. Pinned because an off-by-a-cent
    cap silently returns slots-1 — the failure this whole file is about."""
    clip = LIVE_EQUITY_AFTER / LIVE_SLOTS
    assert A.cap_slots(clip, LIVE_EQUITY_AFTER, LIVE_SLOTS) == LIVE_SLOTS
    assert A.cap_slots(clip, LIVE_EQUITY_AFTER - 0.01, LIVE_SLOTS) == LIVE_SLOTS - 1


def test_cap_slots_never_exceeds_the_books_own_capacity():
    """A generous cap does not invent slots the strategy does not have."""
    assert A.cap_slots(10.0, 10_000.0, LIVE_SLOTS) == LIVE_SLOTS


def test_a_cap_below_one_clip_reports_zero_not_none():
    """ZERO is a finding ('this book can fund nothing'); None means 'unknown'.
    Collapsing them would make a fully-blocked book read as unmeasured."""
    assert A.cap_slots(57.68, 30.0, LIVE_SLOTS) == 0


@pytest.mark.parametrize("clip,cap,slots", [
    (None, 200.0, 4),      # equity unreadable — the guard-reject window
    (57.68, None, 4),      # cap unknown
    (0.0, 200.0, 4),       # zero clip
    (-5.0, 200.0, 4),      # nonsense clip
    (57.68, 0.0, 4),       # zero cap
    ("x", 200.0, 4),       # unparseable
    (57.68, 200.0, 0),     # no slots declared
])
def test_unknown_inputs_report_none_never_a_guess(clip, cap, slots):
    """I8: unknown degrades to None, never to a number somebody would act on.

    The equity-guard reject window makes this reachable in production — for ~15
    minutes on 21-Aug the row published `equity: None`, and a cap census that
    guessed during that window would have been read as a real constraint.
    """
    assert A.cap_slots(clip, cap, slots) is None


def test_the_row_publishes_the_census_and_the_counter():
    """The fields must reach the ROW — a value computed and never published is
    the (lv) failure this exists to close."""
    src = open(A.__file__).read()
    assert '"cap_slots": cap_slots(' in src, \
        "cap_slots must be published on the row, not merely defined"
    assert '"notional_cap_skips": notional_cap_skips' in src, \
        "the refusal counter must be published beside the other entry vetoes"


def test_the_census_reads_the_same_clip_the_row_publishes():
    """One effective clip, two consumers. A second copy of the
    `clip_usd(eq) * _clip_scale_now()` expression is how the published clip and
    the published cap census drift into disagreeing about the same book."""
    src = open(A.__file__).read()
    assert src.count("_clip_scale_now()") >= 1
    assert '"clip_usd": (round(_eff_clip, 2) if _eff_clip else None)' in src, \
        "clip_usd must read the shared _eff_clip local"
    assert '"cap_slots": cap_slots(_eff_clip,' in src, \
        "cap_slots must read the SAME _eff_clip local as clip_usd"


def test_the_vol_target_is_derived_from_the_books_own_stop_and_the_gate_bar():
    """The DIVERSIFICATION-EARNED number is derived, and must MOVE if either
    input moves — a retyped constant is a constant that drifts. It is published
    as advisory beside the operator's setting; it does not clamp it."""
    assert A.vol_target_gross_x(1.0) == round(0.15 / abs(float(A.S.stoploss)), 4)
    assert A.vol_target_gross_x(1.0) == 1.5, "fully-correlated basket -> 1.5x"
    # measured 21-Aug on Lighter's own 200d tape: one-per-class N_eff = 3.09
    assert A.vol_target_gross_x(3.09) == pytest.approx(2.6368, abs=1e-3)
    # monotone in independence: more independent bets support more gross
    assert (A.vol_target_gross_x(1.0) < A.vol_target_gross_x(1.37)
            < A.vol_target_gross_x(3.09))


def test_the_vol_target_never_credits_independence_it_cannot_measure():
    """n_eff below 1 or unreadable falls back to the fully-correlated answer —
    unknown must never buy leverage (I8: degrade to the honest number)."""
    for bad in (0.0, 0.5, -3, None, "x", float("nan")):
        assert A.vol_target_gross_x(bad) == A.vol_target_gross_x(1.0)


@pytest.mark.parametrize("raw,want", [
    ("1.0", 1.0), ("1.4", 1.4), ("2.64", 2.64), ("5.0", 5.0),
    ("6.0", 5.0), ("1e9", 5.0),                   # clamped to the OPERATOR ceiling
    ("0.5", 1.0), ("-3", 1.0), ("0", 1.0),        # floored: shrinking is the
                                                  # clip scale's job, not this
    ("nan", 1.0), ("inf", 1.0), ("abc", 1.0), ("", 1.0),   # hostile -> 1.0
])
def test_no_env_value_escapes_the_operator_ceiling(raw, want, monkeypatch):
    monkeypatch.setattr(A, "GROSS_X", _as_float(raw))
    assert A.gross_x() == pytest.approx(want)


def _as_float(raw):
    """Mirror the module's own defensive import-time parse."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0


@pytest.mark.parametrize("raw", ["abc", "", "1.4x", "None"])
def test_an_unparseable_env_must_not_crash_a_real_money_import(raw, monkeypatch):
    """THE DEFECT THIS FILE CAUGHT, and it was mine: the first cut read
    `GROSS_X = float(os.environ.get(...))` at MODULE level, so a typo'd env var
    raised ValueError at IMPORT and took the live book down before main() ran —
    a failure `gross_x()`'s own NaN handling could never reach, because the
    module never finished loading. Found by feeding the ladder "abc"."""
    import importlib
    monkeypatch.setenv("AVO_GROSS_X", raw)
    monkeypatch.setenv("AVO_VENUE", "lighter_live")
    mod = importlib.reload(A)
    try:
        assert mod.gross_x() == 1.0
    finally:
        monkeypatch.delenv("AVO_GROSS_X", raising=False)
        importlib.reload(A)


def test_the_row_states_the_risk_being_taken_rather_than_hiding_it():
    """The operator sets the leverage; the CODE owes him the arithmetic on the
    row, every loop. Eamon set 5x deliberately — so `all_slots_stop_pct` and
    `liq_gap_pct` must publish, because a setting whose consequences are
    unreadable is the thing that actually goes wrong."""
    src = open(A.__file__).read()
    for field in ('"leverage": {', '"set":', '"vol_target_at_neff1":',
                  '"deployed_at_full":', '"all_slots_stop_pct":', '"liq_gap_pct":'):
        assert field in src, f"the leverage block must publish {field}"


@pytest.mark.parametrize("g,stop_pct,liq_pct", [
    (1.4, 0.14, -0.684),
    (2.64, 0.264, -0.349),
    (5.0, 0.50, -0.170),
])
def test_the_published_risk_arithmetic_is_right(g, stop_pct, liq_pct):
    """Driven, not asserted: all-slots-stop = gross_x * |stop|, and liquidation
    is `mmf - 1/gross_x` at the worst maintenance-margin fraction of the books
    this universe trades (300bps, read per book off the venue — never derived
    from imf, the (no) trap)."""
    assert g * abs(float(A.S.stoploss)) == pytest.approx(stop_pct, abs=1e-6)
    assert 0.03 - 1.0 / g == pytest.approx(liq_pct, abs=1e-3)


def test_gross_x_of_one_reproduces_the_pre_leverage_clip_exactly():
    """Inert until set: the default must not move a single real-money order."""
    eq = LIVE_EQUITY_AFTER
    assert A.gross_x() == 1.0, "shipped default must be 1.0"
    assert A.clip_usd(eq) == pytest.approx(eq / A.S.max_open)


@pytest.mark.parametrize("g", [1.25, 1.4, 1.5])
def test_the_multiplier_actually_REACHES_the_clip(g, monkeypatch):
    """THE HEADLINE FEATURE, AND MY SUITE DID NOT TEST IT.

    Mutation M4 of the (sr) round — deleting `gross_x()` from `clip_usd`, i.e.
    leverage configured and silently never applied — SURVIVED five tests. Every
    existing case pinned the gross_x=1.0 default, where the mutant and the real
    code are identical by construction, so nothing exercised the one line the
    whole feature lives on. The (sp) shape exactly: a lever that is registered,
    documented, published and INERT.
    """
    monkeypatch.setattr(A, "GROSS_X", g)
    eq = LIVE_EQUITY_AFTER
    assert A.clip_usd(eq) == pytest.approx(eq * g / A.S.max_open)
    assert A.clip_usd(eq) > eq / A.S.max_open, \
        "a gross_x above 1.0 must produce a BIGGER clip, or it does nothing"


def test_leverage_reaches_the_published_row_too(monkeypatch):
    """And the deployed gross must equal GROSS_X * equity at full occupancy —
    the claim the drawdown budget is derived from."""
    monkeypatch.setattr(A, "GROSS_X", 1.4)
    eq = LIVE_EQUITY_AFTER
    assert A.clip_usd(eq) * A.S.max_open == pytest.approx(1.4 * eq)


def test_the_row_publishes_the_leverage_it_is_running_at():
    """Dollars now carry a multiplier. Every downstream grader — maxDD, the
    allocation claim, the ceiling — reads dollars, so a book above 1x that does
    not SAY so is publishing numbers nobody can deflate."""
    src = open(A.__file__).read()
    assert '"gross_x": round(gross_x(), 4)' in src
    assert '"gross_x_max": GROSS_X_MAX' in src


def test_cap_slots_is_reported_not_enforced():
    """SafetyRails caps are operator-only. `cap_slots` must not be wired into
    any admission decision — it names the constraint, it does not move it."""
    src = open(A.__file__).read()
    for line in src.splitlines():
        s = line.strip()
        if "cap_slots(" not in s or s.startswith("#"):
            continue
        # the definition, the publish site, and the docstring reference only
        assert (s.startswith("def cap_slots(")
                or '"cap_slots": cap_slots(' in s
                or s.startswith("S.max_open),")), \
            f"cap_slots reached a decision site: {s!r}"
