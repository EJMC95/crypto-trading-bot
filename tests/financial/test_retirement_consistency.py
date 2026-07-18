"""Tier 2 — the retirement de-dup invariants that keep the fleet total honest.

CLAUDE.md: "a retirement needs BOTH halves — RETIRED_ROWS in pnl_dashboard.py
(hides the card) AND LEGACY_BOTS in cleanup_legacy_bots.py (prunes the frozen
row). Doing one hides your own omission." Two real incidents proved it:

  * 🏆 Stock Leaders was added to RETIRED_ROWS but NOT LEGACY_BOTS — hidden on
    the grid, still sitting in bot_pnl, still summed by anything reading the
    table directly (fleet_risk). Half a retirement.
  * 🌊 Tide Rider's live row and the Ticket Taker's row reported the SAME
    sub-account's $34.67; the fleet total double-counted real money until the
    Tide Rider id was retired.

These are pure set invariants over two hand-maintained lists — exactly the kind
of drift a test should pin.
"""
import cleanup_legacy_bots
import pnl_dashboard

RETIRED = pnl_dashboard.RETIRED_ROWS
LEGACY = set(cleanup_legacy_bots.LEGACY_BOTS)

# The two rows that hold REAL MONEY today (base id + the -lighter live suffix).
LIVE_ROWS = {"perps-funding-lighter-lighter", "lighter-ticket-taker-lighter"}


def test_every_hidden_row_is_also_pruned():
    # RETIRED_ROWS ⊆ LEGACY_BOTS: a row hidden from the grid but left in the
    # table lingers stale and is still counted by direct readers. This is the
    # Stock Leaders half-retirement, caught as a set-subset check.
    missing = RETIRED - LEGACY
    assert not missing, (
        "these ids are in RETIRED_ROWS (hidden) but not LEGACY_BOTS (pruned) — "
        f"a half-done retirement leaves them counted by direct readers: {sorted(missing)}"
    )


def test_no_live_suffixed_row_is_pruned_unless_retired():
    # cleanup DELETEs every LEGACY_BOTS id each boot. A live (-lighter) id in
    # that list would delete a real row on every run — permitted ONLY if the row
    # is officially retired (then re-upsert can't happen because the service was
    # repurposed). So: {live-suffixed ∈ LEGACY} ⊆ RETIRED.
    pruned_live_suffixed = {b for b in LEGACY if b.endswith("-lighter")}
    unretired = pruned_live_suffixed - RETIRED
    assert not unretired, (
        f"live-suffixed ids pruned without being retired (would delete a real "
        f"row every boot): {sorted(unretired)}"
    )


def test_current_live_rows_are_never_hidden_or_pruned():
    for row in LIVE_ROWS:
        assert row not in RETIRED, f"{row} holds real money — must not be hidden"
        assert row not in LEGACY, f"{row} holds real money — must not be pruned"


def test_the_34_67_double_count_fix_is_locked():
    # The retired Tide Rider live row must stay filtered (else it double-counts
    # the Ticket Taker's shared sub-account); the taker's live row must NOT be
    # filtered (it is the surviving owner of that money).
    assert "crypto-trend-daily-lighter" in RETIRED
    assert "crypto-trend-daily-lighter" in LEGACY
    assert "lighter-ticket-taker-lighter" not in RETIRED


def test_is_live_bot_matches_the_live_suffix():
    assert pnl_dashboard.is_live_bot("perps-funding-lighter-lighter") is True
    assert pnl_dashboard.is_live_bot("lighter-ticket-taker-lighter") is True
    assert pnl_dashboard.is_live_bot("freqtrade-mum-lshadow") is False
    assert pnl_dashboard.is_live_bot("freqtrade-mum") is False
