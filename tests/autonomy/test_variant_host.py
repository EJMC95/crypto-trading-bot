#!/usr/bin/env python3
"""[2026-08-22 (sx)] THE LIVE RUNNER IS A VARIANT HOST, AND 🙏 AVO MUST NOT MOVE.

**Eamon, 22-Aug: "get georgia ready to go live on a new sub account ill deposit
into later today prepared for 5x leverage".**

🔮 georgia gets a live arm as a VARIANT of the proven module rather than a
1,800-line copy — the 🛢️ Garrett rule ((lp)): one machine, every success
instrument inherited free (claim_writer + standby, the latched daily halt, the
capital-adjust equity guard, the venue-truth reconciler, the notional cap and
`cap_slots` census, `diversified_order`, the (st) scan census, the MTM equity
series, real-fill telemetry, the per-asset regime gate, the brain's
restrict-only sizing). A copy would have to re-earn all of it and would drift.

**THE SAFETY PROPERTY OF THIS CHANGE IS THAT AVO DOES NOT MOVE**, and it is a
real-money book, so most of this file is about that rather than about georgia.
Tests 1-3 pin the default path name by name.

The dangerous failure this forbids (test 4): an unknown or typo'd
`FAMILY_LIVE_BOOK` degrading to Avo. georgia's service would then publish to
Avo's row, restore Avo's state key, and manage Avo's REAL POSITIONS. Refusing
at import is the only acceptable behaviour — I8's "unknown never degrades to a
guess", where the guess would be another book's money.

Test 6 is the number Eamon asked about: 5x means something DIFFERENT on
georgia, because her stop is half as wide.
"""
import contextlib
import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@contextlib.contextmanager
def loaded(book=None, **env):
    """Import the live runner as `book` with `env` applied, and put the module
    back on the way out.

    A CONTEXT MANAGER rather than a function returning the module, which is how
    the first draft of this file was written and why every one of its
    assertions passed against the WRONG module: restoring the environment
    requires a second `reload`, and doing that in a `finally` before returning
    handed the caller a module that had already been reset to the defaults. The
    tests still went green on Avo — the only book whose values happen to be the
    defaults — which is exactly the shape that would have let a georgia
    regression through."""
    saved = dict(os.environ)
    os.environ.pop("FAMILY_LIVE_BOOK", None)
    if book:
        os.environ["FAMILY_LIVE_BOOK"] = book
    for k, v in env.items():
        os.environ[k] = v
    import lighter_avo_live_bot as m
    try:
        yield importlib.reload(m)
    finally:
        os.environ.clear()
        os.environ.update(saved)
        importlib.reload(m)


# ---- 1-3  🙏 Avo does not move -------------------------------------------

def test_the_default_is_avo_unchanged():
    with loaded() as m:
        assert m.BOT == "freqtrade-avo-maria"
        assert m.BOT_ROW == "freqtrade-avo-maria-lighter"
        assert m.SHADOW_ROW == "freqtrade-avo-maria-lshadow"
        assert m.STATE_KEY == "freqtrade-avo-maria-lighter:live"
        assert m._PFX == "AVO"
        assert m.LIVE_CLIP_LEVER == "live.avo.clip_scale"
        assert m.S.bot == "freqtrade-avo-maria" and m.S.max_open == 5
        assert abs(float(m.S.stoploss) + 0.10) < 1e-9


@pytest.mark.parametrize("name,value,attr,expect", [
    ("AVO_LOOP_SECONDS", "111", "LOOP_SECONDS", 111),
    ("AVO_DAILY_LOSS", "0.07", "DAILY_LOSS_LIMIT", 0.07),
    ("AVO_DELIST_GIVEUP_H", "9", "DELIST_GIVEUP_H", 9.0),
    ("AVO_MIN_CLIP_USD", "12", "MIN_CLIP_USD", 12.0),
    ("AVO_QUALITY_VETO_TTL_S", "60", "QUALITY_VETO_TTL_S", 60.0),
    ("AVO_GROSS_X", "3", "GROSS_X", 3.0),
    ("AVO_GROSS_X_MAX", "4", "GROSS_X_MAX", 4.0),
])
def test_every_avo_env_still_resolves(name, value, attr, expect):
    """Name by name. A prefix refactor that silently stopped reading one of
    these would change a REAL-MONEY book's sizing or its halt threshold with
    nothing to show for it."""
    with loaded(**{name: value}) as m:
        assert getattr(m, attr) == expect, f"{name} no longer reaches {attr}"


def test_a_georgia_env_does_not_leak_into_avo():
    """Two live services run this same image. If the namespaces bled, setting
    georgia's leverage would move Avo's."""
    with loaded(GEORGIA_GROSS_X="5", GEORGIA_LOOP_SECONDS="7") as m:
        assert m.GROSS_X == 1.0 and m.LOOP_SECONDS == 300


# ---- 4  the dangerous degrade -------------------------------------------

def test_an_unknown_book_REFUSES_rather_than_becoming_avo():
    """A typo must not point georgia's service at Avo's row, state key and
    live positions. This is the one failure that trades another book's money."""
    for bad in ("freqtrade-georgi", "georgia", "freqtrade-mum", "  "):
        with pytest.raises(SystemExit):
            with loaded(bad):
                pass


# ---- 5-6  🔮 georgia ------------------------------------------------------

def test_georgia_resolves_to_her_own_identity():
    with loaded("freqtrade-georgia") as m:
        assert m.BOT_ROW == "freqtrade-georgia-lighter"
        assert m.SHADOW_ROW == "freqtrade-georgia-lshadow"
        assert m.STATE_KEY == "freqtrade-georgia-lighter:live"
        assert m._PFX == "GEORGIA"
        assert m.LIVE_CLIP_LEVER == "live.georgia.clip_scale"
        # the strategy comes from the family REGISTRY BY IDENTITY, so the live
        # and shadow arms of the same book cannot drift apart
        import lighter_family_bot as fam
        assert m.S is next(s for s in fam.STRATEGIES
                           if s.bot == "freqtrade-georgia")
        assert m.S.tf == "15m" and m.S.max_open == 5
        assert abs(float(m.S.stoploss) + 0.05) < 1e-9


def test_5x_means_something_different_on_georgia_and_the_code_knows_it():
    """Her stop is HALF Avo's, so the same multiplier is half the drawdown.
    Measured 22-Aug and this is the number the ask turns on:
        all-slots-stop at 5x : georgia 25%  |  avo 50%
        gross the 15% bar allows at N_eff 1: georgia 3.0x | avo 1.5x
    Nothing here was hand-typed for georgia — the leverage layer already reads
    `S.stoploss`, which is why a variant was the right shape."""
    with loaded("freqtrade-georgia", GEORGIA_GROSS_X="5",
                GEORGIA_GROSS_X_MAX="5") as g:
        assert g.gross_x() == 5.0
        assert abs(g.gross_x() * abs(float(g.S.stoploss)) - 0.25) < 1e-9
        assert abs(g.vol_target_gross_x(1.0) - 3.0) < 1e-6
        # the clip is the balance split across HER slots, not Avo's
        assert abs(g.clip_usd(500.0) - 500.0 * 5.0 / g.S.max_open) < 1e-9
    with loaded(AVO_GROSS_X="5", AVO_GROSS_X_MAX="5") as a:
        assert abs(a.gross_x() * abs(float(a.S.stoploss)) - 0.50) < 1e-9
        assert abs(a.vol_target_gross_x(1.0) - 1.5) < 1e-6


def test_georgia_cannot_boot_without_her_own_venue_env():
    """`GEORGIA_VENUE`, not `AVO_VENUE` — and the refusal must SAY so, or the
    operator is sent to fix the wrong variable (I8)."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert 'f"{_PFX}_VENUE must be EXACTLY' in src, \
        "the identity guard names a hardcoded env, not this book's"
    with loaded("freqtrade-georgia") as m:
        with pytest.raises(SystemExit) as e:
            m.main()
        assert "GEORGIA_VENUE" in str(e.value), str(e.value)


# ---- 7  the arm she consumes must exist ----------------------------------

def test_her_clip_lever_is_registered():
    """`fleet_tuning.get_lever` returns the env default for an UNREGISTERED
    name, so a live book whose arm does not exist has a dial nothing can turn
    — silent, and the reverse of registered-but-inert."""
    import fleet_tuning as ft
    for book in ("freqtrade-avo-maria", "freqtrade-georgia"):
        with loaded(book) as m:
            assert m.LIVE_CLIP_LEVER in ft.LEVERS, m.LIVE_CLIP_LEVER
            cage = ft.LEVERS[m.LIVE_CLIP_LEVER]
            assert cage["hi"] == 1.0, \
                "the consumer is restrict-only; hi>1 is inert authority"
            assert cage["lane"] == "lighter-live"


# ---- 8-11  [(sy)] the liquidation arithmetic ------------------------------

def test_the_maintenance_margin_is_READ_not_hardcoded():
    """`(sr)` published `liq_gap_pct` off a literal 0.03. The venue's real
    worst across these books' own universes is 0.06 — IWM/MSTR on Avo's
    non-crypto set, ADA/DOT/AVAX/LINK once georgia's crypto set is in — so the
    row advertised a liquidation gap TWICE as far away as it was. The data was
    already on the bus ((se)) and nothing read it."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "0.03 - 1.0 / max(1e-9, gross_x())" not in src, \
        "the hardcoded 300bps is back"
    assert "fleet_bus.market_margins()" in src, "the venue's surface is unread"


def test_an_unreadable_margin_publishes_NOTHING_rather_than_a_guess():
    """`market_margins` is fail-CLOSED because the cost of a wrong default is a
    liquidation. A fabricated distance on a levered real-money row is the one
    number that must never be invented (I8)."""
    with loaded() as m:
        assert m.worst_mmf([]) is None
        assert m.liq_gap_pct(None) is None
        assert m.stop_reachable(None) == (None, None)


@pytest.mark.parametrize("book,stop,ceiling", [
    ("freqtrade-avo-maria", 0.10, 6.25),
    ("freqtrade-georgia", 0.05, 9.09),
])
def test_the_stop_has_a_gross_ceiling_of_its_own(book, stop, ceiling):
    """THE NUMBER THAT DECIDES WHAT 10x MEANS. Liquidation arrives at
    `1/G - mmf`, the stop fires at `|stoploss|` — so above
    `G = 1/(|stoploss| + mmf)` the venue liquidates FIRST and the protective
    stop is dead code. Not a risk-appetite question: a stop that cannot fire is
    a broken rail, and it was invisible until now."""
    with loaded(book) as m:
        assert abs(abs(float(m.S.stoploss)) - stop) < 1e-9
        ok, ceil = m.stop_reachable(0.06, gross=10.0)
        assert ok is False, "at 10x this stop cannot fire before liquidation"
        assert abs(ceil - ceiling) < 0.01, (ceil, ceiling)
        below, _ = m.stop_reachable(0.06, gross=ceiling - 0.5)
        assert below is True, "just under the ceiling the stop must still fire"


def test_liq_gap_matches_the_closed_form_and_keeps_its_sign():
    """`x = 1/G - mmf`, published NEGATIVE (the direction that hurts a long
    book), matching (sr)'s convention so the field's meaning did not silently
    flip when its source did."""
    with loaded() as m:
        assert m.liq_gap_pct(0.06, gross=5.0) == -0.14
        assert m.liq_gap_pct(0.06, gross=10.0) == -0.04
        assert m.liq_gap_pct(0.06, gross=0) is None


def test_the_ceiling_is_ten_and_is_a_ceiling_not_a_setting():
    """Eamon, 22-Aug: "let avo go up to 10x, and georgia also". GROSS_X_MAX is
    the bound; GROSS_X is what a service runs, and it still defaults to 1.0 —
    raising the ceiling must not lever an unconfigured book."""
    for book in ("freqtrade-avo-maria", "freqtrade-georgia"):
        with loaded(book) as m:
            assert m.GROSS_X_MAX == 10.0
            assert m.GROSS_X == 1.0 and m.gross_x() == 1.0
