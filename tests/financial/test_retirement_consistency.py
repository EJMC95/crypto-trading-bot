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

# The rows that hold REAL MONEY today — DERIVED from the one declaration
# rather than retyped here. [2026-08-25] This file carried its own hardcoded
# pair and went red on main when the (ta)/(tb) swap pruned the Farmer's row:
# the exact twelve-places rot `fleet_books` ((mn)) exists to end, in a test
# ABOUT retirement consistency. A second copy of a rule is a second rule.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "scripts"))
from fleet_books import DECLARED_LIVE  # noqa: E402

LIVE_ROWS = set(DECLARED_LIVE)


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
    # Every PAST occupant of the shared live slot must stay filtered, or its
    # frozen row double-counts the sub-account the CURRENT occupant reports.
    # Two generations now: Tide Rider ($34.67, 17-Jul) and the Ticket Taker
    # ($62.80, 13-Aug (ma) — measured live at cutover: live_equity read
    # $323.30 across 3 "live" rows when the real money was $260.50 across 2
    # accounts). The current occupant must NOT be filtered.
    assert "crypto-trend-daily-lighter" in RETIRED
    assert "crypto-trend-daily-lighter" in LEGACY
    assert "lighter-ticket-taker-lighter" in RETIRED
    assert "lighter-ticket-taker-lighter" in LEGACY
    assert "freqtrade-avo-maria-lighter" not in RETIRED
    assert "freqtrade-avo-maria-lighter" not in LEGACY
    # [2026-08-25] third generation: 💸 the Farmer's live row retired (ta)/(tb),
    # flatten receipt read (open == 0), then hidden + pruned; 🔮 georgia is the
    # slot's current occupant and must not be filtered.
    assert "perps-funding-lighter-lighter" in RETIRED
    assert "perps-funding-lighter-lighter" in LEGACY
    # [2026-09-02 (wl)] fourth generation: 🔮 georgia's live arm retired at
    # (wg), receipt read (open 0, equity $0.01, funds verified on mum's row),
    # then hidden + pruned. Her slot has NO successor occupant — the host
    # keeps heart-beating the row with entries registry-gated, so the prune
    # is undone each publish and RETIRED_ROWS is the operative filter. 👩 mum
    # (a FRESH sub-account, not this slot) must not be filtered.
    assert "freqtrade-georgia-lighter" in RETIRED
    assert "freqtrade-georgia-lighter" in LEGACY
    assert "freqtrade-mum-lighter" not in RETIRED
    assert "freqtrade-mum-lighter" not in LEGACY
    # the SHADOW twin keeps trading as the control arm — never filtered.
    assert "freqtrade-georgia-lshadow" not in RETIRED
    assert "freqtrade-georgia-lshadow" not in LEGACY


def test_is_live_bot_matches_the_live_suffix():
    assert pnl_dashboard.is_live_bot("perps-funding-lighter-lighter") is True
    assert pnl_dashboard.is_live_bot("freqtrade-avo-maria-lighter") is True
    assert pnl_dashboard.is_live_bot("freqtrade-mum-lshadow") is False
    assert pnl_dashboard.is_live_bot("freqtrade-mum") is False
