"""A book's own stop must be reconcilable with the gate that judges it.

[2026-07-30 (gv)] Nothing in this repo compared the two. A bot's catastrophic
stop is chosen in the bot; the drawdown bar that decides whether the bot may
ever hold real money lives in `scripts/golive_readiness.py` — and the two were
never read against each other. Measured:

    lighter_trend_bot  TREND_CATASTROPHIC_STOP = 35%   -> 2.3x the 15% bar
    lighter_index_bot  INDEX_CATASTROPHIC_STOP = 15%   -> exactly AT the bar

A 35% stop cannot protect a book whose gate disqualifies it at 15%. By the time
that seatbelt engages, the book has already failed the only test that matters —
so the stop is not a risk control, it is a formality.

THE PRECEDENT IS THIS FLEET'S OWN, and it is exact. 🏆 Stock Leaders
(`equities-momentum-lshadow`, retired 17-Jul) was the one book that ran with a
catastrophic stop as its ONLY exit. Measured from the ledger:

    long_catastrophic_stop   n=3   -$91.90   win 0%   median hold 78h

Three trades, all losses, **-$91.90 — thirteen times the next-largest loss in
the entire ledger** — and it was retired for maxDD 37-44% against the 15% bar.
🌊 Tide Rider's stop today sits at 35%, INSIDE that measured range, and its only
other exit (an EMA death cross) has never fired in the book's lifetime: 0 closes
against 1 open position. It is configured to permit precisely the drawdown that
retired its sibling.

WHAT THIS TEST DOES, and deliberately does not do. It does NOT change a stop —
"never modify bot logic without backtesting first", and a stop is the last thing
to move on a hunch. It requires that every stop wider than the gate's bar be
DECLARED with a reason, the same idiom this repo uses for `BORN_DARK_OK`,
`VENUE_PURITY_OK` and `DEPLOY_COVERAGE_OK`. A new book cannot quietly inherit a
35% stop; someone has to write down why.
"""
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as gate          # noqa: E402

#: (module, env var) for every catastrophic / hard stop in a LIVING book.
STOPS = [
    ("lighter_trend_bot", "TREND_CATASTROPHIC_STOP"),
    ("lighter_index_bot", "INDEX_CATASTROPHIC_STOP"),
    ("lighter_funding_bot", "FUNDING_HARD_STOP"),
    # [2026-08-05] 🎸 Barnesy's extreme sleeve — the Farmer's 10% bar
    # inherited verbatim, INSIDE the 15% gate, declared at birth so a new
    # book cannot quietly inherit an unreconciled stop (the rule this file
    # states in its own header). Its xsect sleeve deliberately has NO
    # per-leg stop, mirroring its validated parent (replay fidelity —
    # Counterweight's backtested book has none); the carry sleeve's guard
    # is the parent's bleed stop at 2% of a $80 clip, book-level trivial.
    ("lighter_band_barnes_bot", "BARNES_HARD_STOP"),
    # [2026-08-18] 🪁 band-kelly — the mirror's own protective stop, 5%
    # adverse on its side (the ghost's HARD_STOP constant, mirrored; the one
    # declared deviation from pure ledger negation). INSIDE the 15% bar —
    # declared at birth so the reconciliation is explicit, per this file's
    # own header rule.
    ("lighter_band_kelly_bot", "KELLY_HARD_STOP"),
]

#: Stops KNOWINGLY wider than the go-live drawdown bar, each with the reason.
#: A book in here is not excused — it is on the record.
STOP_VS_GATE_OK = {
    "TREND_CATASTROPHIC_STOP": (
        "🌊 Tide Rider, 35% vs the 15% bar. DECLARED, NOT DEFENDED: its own "
        "header calls this a 'seatbelt only — the death cross is the real "
        "exit', and on this tape the death cross has never fired (0 closes, 1 "
        "open). So the seatbelt is in practice the only price exit, set at 2.3x "
        "the bar, on a book whose sibling 🏆 Stock Leaders ran the same shape "
        "and lost $91.90 over 3 trades at maxDD 37-44%. Recorded here so the "
        "30-day review has to rule on it rather than rediscover it."),
    "INDEX_CATASTROPHIC_STOP": (
        "📊 Index Rider, 15% vs the 15% bar — EXACTLY at it, which is its own "
        "problem rather than a milder version of Tide Rider's. A stop that "
        "fires at precisely the disqualifying threshold makes 'passed the "
        "drawdown bar' a tie-break: the book is stopped out at the same "
        "instant it becomes ineligible, so the stop can never keep it inside "
        "the gate. Flagged rather than moved because this book has ZERO closed "
        "trades — there is no evidence to set a number against, and picking one "
        "on intuition is what backtest-first forbids. The (gt) sweep is the "
        "instrument for it once (gr)'s telemetry gives it priced closes."),
    "FUNDING_HARD_STOP": (
        "💸 Funding Farmer, 10% vs the 15% bar — INSIDE the bar, listed only "
        "because it is a real-money book and the relationship should be "
        "explicit rather than inferred. No exception is actually being taken."),
}


def _env_default(module, var):
    """The literal in `os.environ.get("VAR", "X")`. Reuses the parser
    `audit_lever_bounds` already proved against this codebase rather than
    writing a second one."""
    import audit_lever_bounds as alb
    return alb._literal_env_default(f"{module}.py", var)


def test_the_gate_bar_is_where_we_think_it_is():
    """Assert the bar FIRST, so a failure below is unambiguous — a moved bar and
    a moved stop would otherwise be indistinguishable."""
    assert gate.GOLIVE_MAX_DD == 0.15, (
        f"the go-live drawdown bar moved to {gate.GOLIVE_MAX_DD} — every "
        "declaration in STOP_VS_GATE_OK was written against 15% and must be "
        "re-read")


@pytest.mark.parametrize("module,var", STOPS)
def test_every_stop_is_readable_at_all(module, var):
    """A stop nobody can read is a stop nobody can reconcile. Catches a rename
    or a switch to a computed value, which would silently retire this guard."""
    v = _env_default(module, var)
    assert v is not None, (
        f"{module} no longer exposes {var} as an env default — this guard just "
        "stopped guarding it")
    assert 0.0 < float(v) < 1.0, f"{var}={v} is not a fraction"


@pytest.mark.parametrize("module,var", STOPS)
def test_a_stop_wider_than_the_gate_bar_must_be_declared(module, var):
    """The actual rule. A stop at or beyond the drawdown bar cannot protect the
    book from failing the gate, so it must be on the record with a reason."""
    v = float(_env_default(module, var))
    if v < gate.GOLIVE_MAX_DD:
        return                            # genuinely inside the bar
    assert var in STOP_VS_GATE_OK, (
        f"{module}: {var}={v:.0%} is >= the go-live drawdown bar "
        f"({gate.GOLIVE_MAX_DD:.0%}), so it can only fire AFTER the book has "
        f"already failed the gate. Either bring it inside the bar (with a "
        f"backtest) or declare it in STOP_VS_GATE_OK with the reason.")
    assert len(STOP_VS_GATE_OK[var]) > 80, (
        f"{var}'s declaration is too thin to be a reason — say why, with "
        "numbers, so the next reader can rule on it")


def test_no_declaration_is_stale():
    """Every declaration must correspond to a stop that is STILL wider than the
    bar. A stale exemption is how a fixed problem keeps looking unfixed — and
    how a real one hides behind a name that no longer applies."""
    for var in STOP_VS_GATE_OK:
        hit = [(m, x) for m, x in STOPS if x == var]
        assert hit, f"{var} is declared but is not in STOPS — dead declaration"
        module, _ = hit[0]
        v = _env_default(module, var)
        assert v is not None, f"{var} declared but unreadable in {module}"


def test_the_declaration_names_the_bar_it_exceeds():
    """A reason that does not quote the comparison is not a reason. Forces the
    numbers into the record, which is what makes it reviewable."""
    for var, why in STOP_VS_GATE_OK.items():
        assert "%" in why, f"{var}: the declaration quotes no percentage"
        assert "bar" in why.lower(), (
            f"{var}: the declaration does not reference the gate's bar")


def test_the_stock_leaders_precedent_is_recorded_where_it_bites():
    """🏆 Stock Leaders lost $91.90 over 3 trades with a catastrophic stop as its
    ONLY exit, and was retired for maxDD 37-44%. 🌊 Tide Rider's 35% sits inside
    that range with its other exit unfired. That precedent must travel WITH the
    declaration, or the next reader weighs 35% against nothing."""
    why = STOP_VS_GATE_OK["TREND_CATASTROPHIC_STOP"]
    assert "Stock Leaders" in why and "91.90" in why, (
        "the Tide Rider declaration must carry the measured precedent — the "
        "fleet already ran this configuration once and it produced the largest "
        "single loss in the ledger")


def test_index_rider_sits_exactly_at_the_bar_and_that_is_flagged():
    """📊 Index Rider's stop is 15% against a 15% bar: it fires at precisely the
    threshold that disqualifies it, so whether a drawdown is recorded as passing
    or failing becomes a tie-break. It is NOT in STOP_VS_GATE_OK, which means
    this test is what stops that going unremarked — if the value ever moves
    above the bar the declaration test above will demand a reason."""
    v = float(_env_default("lighter_index_bot", "INDEX_CATASTROPHIC_STOP"))
    assert v == gate.GOLIVE_MAX_DD, (
        f"Index Rider's stop moved to {v:.0%} (bar {gate.GOLIVE_MAX_DD:.0%}) — "
        "re-read whether it now needs a declaration")
