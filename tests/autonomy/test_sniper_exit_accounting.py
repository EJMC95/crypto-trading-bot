"""🎯 Perp Sniper's exit accounting — one P&L basis, and a durable zombie clock.

[2026-07-30 (ha)] Both findings came out of the exit audit and both SURVIVED an
adversarial verifier told to default to refuting. Four of forty-four did.

ONE: THE ROW CARRIED TWO DIFFERENT P&L BASES.
`record_close` derived `pnl_pct` from the `exit_px` it was handed, which in the
SHADOW branch is the decision MID (`_mid(orderbook)`). But `pnl` comes back from
`ShadowBroker.close`, which re-fetches the book and CROSSES it
(`venues/shadow.py:93-96` -> `_shadow_fill`). And the entry price read out of
`broker.pos` is itself a crossed fill (`ShadowBroker.open` stores the fill, not
the mid). So one close row carried:

    pnl_abs  — net of BOTH spreads
    pnl_pct  — net of the ENTRY spread only

Not cosmetic. `scripts/golive_readiness.py` grades **mean / t / win-rate off
pnl_pct** and **halves / drawdown off pnl_abs**, so this book was judged on two
inconsistent measures simultaneously — three bars on one basis, two on the other.

The fix derives the percentage FROM pnl, which is already what two sibling books
do (`lighter_index_bot.py:300` `pnl / notional`, `lighter_ticket_taker.py:1460`
`net / clip_used`). Direction is RESTRICT-ONLY: including the exit spread makes
`pnl_pct` strictly worse, so every gate bar gets harder, never easier.

TWO: THE WRONG ONE OF TWO CLOCKS WAS PERSISTED.
`no_px_since` / `last_px` were module-locals that reset to `{}` on every boot,
so the 6h `DELIST_GIVEUP_SEC` needed six hours of CONTINUOUS process uptime.
And it is worse than merely slow: the unpriceable branch `continue`s BEFORE the
max-hold test, so while that clock is unexpired the durable `entry_ts` clock
cannot rescue the position. The non-durable clock is the ONLY exit for an
unpriceable book — and it was the one not saved. Three sibling implementations
of the same 16-Jul guard already persist it (dislocation, family, index); the
sniper was the outlier.

Materiality is LATENT, not observed: with n=1 lifetime close no stuck position is
demonstrated in today's data. This is a durability defect in an exit guard.
"""
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SRC = (_ROOT / "lighter_perp_sniper.py").read_text()


# --------------------------------------------------------------------------
# 1. One basis.
# --------------------------------------------------------------------------

def test_pnl_pct_is_derived_from_pnl_not_from_the_decision_price():
    """The whole fix. If `notional` stops being used, the row silently returns
    to two bases and the go-live gate resumes grading on both at once."""
    assert "def record_close(coin, ent_px, ent_ts, exit_px, pnl, was_long, reason,\n" \
           "                     notional=None):" in _SRC, \
        "record_close no longer takes notional"
    assert "pnl_pct = float(pnl) / float(notional)" in _SRC, \
        "pnl_pct is no longer derived from pnl — the two-basis defect is back"


def test_both_call_sites_pass_a_notional():
    """A default of None falls back to the OLD price-derived formula, which is
    correct as a fallback and wrong as the normal path. Both closers must
    supply it or the fix is inert at exactly the site that needed it."""
    calls = [i for i in range(len(_SRC)) if _SRC.startswith("record_close(", i)]
    # the def line also matches "record_close(" — drop it
    sites = [i for i in calls if "def record_close" not in _SRC[max(0, i - 4):i + 13]]
    assert len(sites) >= 2, f"expected 2 call sites, found {len(sites)}"
    for i in sites:
        block = _SRC[i:i + 400]
        assert "notional=" in block, (
            "a record_close call site omits notional and would fall back to the "
            "decision-price formula this fix exists to remove")


def test_the_shadow_site_uses_the_CROSSED_entry_for_its_notional():
    """`_ent` comes from `broker.pos`, which ShadowBroker populates with the
    crossed fill. Using it is correct: notional must be what was actually
    committed, not the mid that was quoted."""
    assert "notional=abs(float(_sz)) * float(_ent)" in _SRC


def test_the_funded_site_is_value_unchanged():
    """The funded branch already computed pnl FROM exit_px, so pnl/notional
    returns the number it always did. This test exists so a future reader does
    not 'fix' the live path believing it was also broken — it was not."""
    assert "notional=abs(float(sz)) * float(ent_px)" in _SRC
    assert "exit_px = _real_exit(coin, was_long, px)" in _SRC, (
        "the funded branch must still price at the real fill — that is the "
        "premise that makes its two bases already agree")


def test_the_direction_is_restrict_only():
    """A long crossing out at the bid realises LESS than the mid, so a
    pnl-derived percentage is <= the old mid-derived one. Arithmetic, stated as
    a test because 'restrict-only' is the claim that makes this safe to ship
    without a backtest."""
    ent, mid, bid, size = 100.0, 110.0, 109.0, 2.0
    old_pct = (mid - ent) / ent                      # mid-derived
    pnl = size * (bid - ent)                         # crossed fill
    new_pct = pnl / (size * ent)                     # pnl-derived
    assert new_pct < old_pct, (new_pct, old_pct)


# --------------------------------------------------------------------------
# 2. The durable clock.
# --------------------------------------------------------------------------

def _save_state_blocks():
    """EVERY `store.save_state(bot_id, {...})` site, not the first one found.

    The first version of this test used `_SRC.index(...)` and read only the
    earliest of TWO writers — it failed against a fix that had been correctly
    applied to the other one. A test that inspects one of N writers cannot tell
    a whole fix from a half fix, and half a persistence fix is worse than none.
    """
    out, i = [], 0
    needle = "store.save_state(bot_id, {"
    while True:
        i = _SRC.find(needle, i)
        if i < 0:
            break
        out.append(_SRC[i:i + 3200])
        i += len(needle)
    return out


def test_EVERY_save_site_persists_the_zombie_clock():
    """Both writers must write the same shape. The seed path runs only on a
    first-ever boot, but if it ever ran with positions held it would overwrite
    the state and erase the clock — the same two-writers-one-key hazard the
    carry row demonstrated expensively earlier today."""
    blocks = _save_state_blocks()
    assert len(blocks) >= 2, f"expected >=2 save sites, found {len(blocks)}"
    for n, b in enumerate(blocks):
        assert '"no_px_since"' in b, (
            f"save site #{n + 1} does not persist no_px_since — the 6h give-up "
            "would need 6h of CONTINUOUS uptime, and it is the ONLY exit an "
            "unpriceable position has")
        assert '"last_px"' in b, f"save site #{n + 1} does not persist last_px"


def test_the_zombie_clock_is_restored():
    """Saved-but-never-read is this repo's signature failure. Both halves."""
    assert "no_px_since.update({" in _SRC, "saved but never restored"
    assert "last_px.update({" in _SRC


def test_the_durable_max_hold_clock_is_still_persisted():
    """`entry_ts` was already saved and must stay saved at EVERY site. The
    finding was that the WRONG one of two clocks was durable, not that either
    should be dropped."""
    for n, b in enumerate(_save_state_blocks()):
        assert '"entry_ts"' in b, f"save site #{n + 1} dropped entry_ts"


def test_the_unpriceable_branch_still_short_circuits_before_max_hold():
    """The mechanism that makes the persistence load-bearing rather than a
    nicety. If this `continue` is ever removed, the durable entry_ts clock WOULD
    cover an unpriceable position and the urgency here drops — so a future
    reader should know the two facts are coupled."""
    i = _SRC.index("if now.timestamp() - first < DELIST_GIVEUP_SEC:")
    assert "continue" in _SRC[i:i + 120], (
        "the unpriceable branch no longer short-circuits — re-read whether the "
        "zombie clock is still the only exit for such a position")


def test_a_missing_saved_entry_is_not_an_error():
    """The restore must tolerate absence: a coin that became priceable again
    simply has no clock, and that is the correct state — not a reset."""
    assert '_saved.get("no_px_since") or {}' in _SRC
    assert '_saved.get("last_px") or {}' in _SRC


def test_zero_prices_are_not_restored_as_real():
    """`last_px` is used as the fallback valuation price. A restored 0.0 would
    value a position at zero and book a -100% close."""
    i = _SRC.index('last_px.update({')
    assert "if v" in _SRC[i:i + 220], "a falsy last_px must not be restored"
