"""[(xz)] The leverage band — would it have caught avo?

Three constants in three files (gross on a service env, the stop in a registry,
the daily-loss fraction in a host) jointly decide whether a book's own strategy
or the daily rail ends its trades. The test that matters is the retrospective
one: plant each book's REAL pre-fix configuration and require the guard to flag
it. A guard that cannot see the incident it was built for is decoration.
"""
import os
import sys

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import audit_leverage_band as A  # noqa: E402

D = 0.15


def test_it_would_have_caught_avo_the_day_she_was_levered():
    """🙏 avo ran 5.3x on a −10% stop with a 0.10 daily fraction. Measured on
    her ledger the same day: 14 of 22 live closes (64%) were `daily_loss`
    flattens — her strategy exited 8."""
    b = A.band(5.3, -0.10, 0.10, D)
    assert b["r1"] is False, b
    assert b["stop_widths"] < 0.20, b     # 0.19 — a fifth of one stop
    assert b["r2"] is False, b            # 53% all-slots vs a 15% bar
    assert b["ceiling"] == pytest.approx(1.5), b


def test_it_would_have_caught_mum_before_tonight():
    b = A.band(3.75, -0.04, 0.10, D)
    assert b["r1"] is False, b
    assert b["stop_widths"] == pytest.approx(0.10 / 3.75 / 0.04), b


def test_it_reproduces_sr_s_own_ceiling_derivation():
    """`(sr)` derived `GROSS_X_MAX = 0.15/|stoploss|` and mum's 3.75x was
    exactly it. The band's ceiling must BE that number, not a near miss."""
    assert A.band(1.0, -0.04, 0.10, D)["ceiling"] == pytest.approx(3.75)
    assert A.band(1.0, -0.10, 0.10, D)["ceiling"] == pytest.approx(1.5)


def test_both_books_pass_r1_after_tonights_fix():
    for g, s in ((5.0, -0.04), (2.0, -0.10)):
        b = A.band(g, s, 0.20, D)
        assert b["r1"] is True, (g, s, b)
        assert b["stop_widths"] == pytest.approx(1.0), b


def test_the_relationship_is_dormant_at_1x_which_is_why_it_was_missed():
    """At gross 1.0 a book caps its own day at `s` regardless of `f`. The trap
    opens only when leverage arrives — on a service env, far from either
    constant. That is the whole mechanism."""
    assert A.band(1.0, -0.04, 0.10, D)["r1"] is True
    assert A.band(1.0, -0.10, 0.10, D)["r1"] is True     # exactly 1.00
    assert A.band(2.0, -0.10, 0.10, D)["r1"] is False    # levered -> trapped


def test_a_book_with_no_daily_halt_is_n_a_not_a_silent_pass():
    """Six living books have a stop and no daily halt. R1 must read `None`,
    never True — 'not applicable' and 'checked and fine' are different answers
    and a reader has to be able to tell them apart (I18)."""
    b = A.band(1.0, -0.05, None, D)
    assert b["r1"] is None and b["stop_widths"] is None


@pytest.mark.parametrize("args", [(0, -0.04, 0.1), (1.0, 0, 0.1),
                                  ("x", -0.04, 0.1), (1.0, None, 0.1),
                                  (float("nan"), -0.04, 0.1)])
def test_junk_degrades_to_none_and_never_raises(args):
    assert A.band(*args, D) is None or A.band(*args, D)["gs"] == A.band(*args, D)["gs"]


def test_the_gate_bar_is_imported_from_the_grader_not_retyped():
    """(hj): a second copy of a rule is a second rule. If the gate ever moves
    its bar, this audit must move with it."""
    D_, src = A.gate_bar()
    assert src != "fallback-literal", (
        "the audit could not import the gate's own bar and fell back to a "
        "literal — that is a second copy of the rule")
    import golive_readiness as gr
    assert D_ == getattr(gr, src)


def test_declared_exemptions_carry_a_reason_and_a_value():
    """DECLARED is not a place to park a book nobody thought about."""
    assert A.DECLARED, "the declared set is empty — both live books sit outside R2"
    for book, why in A.DECLARED.items():
        assert len(why) > 80, (book, why)
        assert "Eamon" in why, (book, "a declared exemption names who decided")
        assert any(t in why for t in ("R1", "R2")), (book, why)


def test_an_undeclared_violation_fails_the_scan():
    """The ratchet: declared states are recorded, a NEW one reddens."""
    rows = [("some-new-book", 4.0, -0.10, 0.10, "planted")]
    assert A.report(rows, D, "test") == 1


def test_a_declared_book_does_not_fail_the_scan():
    rows = [("freqtrade-mum-lighter", 5.0, -0.04, 0.20, "planted")]
    assert A.report(rows, D, "test") == 0


def test_an_unreadable_feed_refuses_rather_than_reporting_clean():
    """Fail-CLOSED: a dark feed must never read as a clean sheet."""
    rows, err = A.rows_from_feed("/nonexistent/path/to/nothing.json")
    assert rows is None and err
    assert A.main(["--pnl-json", "/nonexistent/path/to/nothing.json"]) == 2
