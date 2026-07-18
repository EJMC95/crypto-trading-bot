"""Tier 3 — fleet_risk freshness gates + authoritative-row precedence.

These are the fail-closed / anti-double-count guards fleet_risk's own selftest
skips (it covers only dd_governor + exposure math):

  * state_fresh — honours a bot_state payload's own updated+ttl_sec and fails
    CLOSED. This is the fix for the 15-Jul false LIVE down-scale that fired off
    a 39h-old payload read as current.
  * authoritative_row — resolves each directional bot to ONE row (live Lighter >
    lshadow > paper) and requires it FRESH, so a frozen row never shadows a
    running one (the ghost-exposure RED that pinned the risk light for hours).
"""
from datetime import datetime, timedelta, timezone

import fleet_risk


def _iso(dt):
    return dt.isoformat()


def _now():
    return datetime.now(timezone.utc)


# ── state_fresh: fail-closed TTL honouring ───────────────────────────────────
def test_state_fresh_true_within_ttl():
    p = {"updated": _iso(_now() - timedelta(minutes=5)), "ttl_sec": 3600}
    assert fleet_risk.state_fresh(p) is True


def test_state_fresh_false_when_past_ttl():
    # the 39h-stale payload class: old, but a naive reader would trust it
    p = {"updated": _iso(_now() - timedelta(hours=39)), "ttl_sec": 3600}
    assert fleet_risk.state_fresh(p) is False


def test_state_fresh_false_on_future_timestamp():
    p = {"updated": _iso(_now() + timedelta(minutes=10)), "ttl_sec": 3600}
    assert fleet_risk.state_fresh(p) is False       # negative age fails closed


def test_state_fresh_false_on_missing_or_unparseable():
    assert fleet_risk.state_fresh({}) is False
    assert fleet_risk.state_fresh(None) is False
    assert fleet_risk.state_fresh({"updated": "not-a-date", "ttl_sec": 3600}) is False
    assert fleet_risk.state_fresh({"updated": _iso(_now())}) is False   # ttl 0


# ── row_fresh: bot_pnl row staleness ─────────────────────────────────────────
def test_row_fresh_within_window():
    assert fleet_risk.row_fresh({"updated_at": _iso(_now() - timedelta(minutes=10))}) is True


def test_row_fresh_false_when_stale():
    # STALE_ROW_SEC is 3900s (65 min); 2h is well past
    assert fleet_risk.row_fresh({"updated_at": _iso(_now() - timedelta(hours=2))}) is False


def test_row_fresh_false_on_missing_or_bad():
    assert fleet_risk.row_fresh({}) is False
    assert fleet_risk.row_fresh(None) is False
    assert fleet_risk.row_fresh({"updated_at": "garbage"}) is False


def test_row_fresh_accepts_Z_suffix():
    ts = _now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    assert fleet_risk.row_fresh({"updated_at": ts}) is True


# ── authoritative_row: one row, live>lshadow>paper, must be fresh ────────────
def _row(equity=1000.0, age_min=1):
    return {"equity": equity, "updated_at": _iso(_now() - timedelta(minutes=age_min))}


def test_live_lighter_wins_over_shadow_and_paper():
    by_bot = {
        "crypto-trend-daily-lighter": _row(equity=34.67),
        "crypto-trend-daily-lshadow": _row(equity=1000.0),
        "crypto-trend-daily": _row(equity=999.0),
    }
    row, venue = fleet_risk.authoritative_row("crypto-trend-daily", by_bot)
    assert venue == "lighter_live" and row["equity"] == 34.67


def test_frozen_live_row_does_not_shadow_a_running_shadow():
    by_bot = {
        "crypto-trend-daily-lighter": _row(age_min=200),   # frozen (stale)
        "crypto-trend-daily-lshadow": _row(equity=1000.0, age_min=1),
    }
    row, venue = fleet_risk.authoritative_row("crypto-trend-daily", by_bot)
    assert venue == "lighter_shadow"      # the fresh one wins, not the stale live


def test_paper_fallback_when_only_paper_present():
    by_bot = {"crypto-trend-daily": _row(equity=1000.0)}
    row, venue = fleet_risk.authoritative_row("crypto-trend-daily", by_bot)
    assert venue == "hl_paper"


def test_none_when_all_stale_or_absent():
    by_bot = {"crypto-trend-daily-lighter": _row(age_min=999)}
    assert fleet_risk.authoritative_row("crypto-trend-daily", by_bot) == (None, None)
    assert fleet_risk.authoritative_row("nonexistent", {}) == (None, None)


# ── governed_clip_scale: the advisory kill switch releases the clip actuator ──
def test_enforce_mode_publishes_the_governor_value():
    # In enforce mode the drawdown governor's throttle is live.
    assert fleet_risk.governed_clip_scale(0.5, "enforce") == (0.5, 0.5)
    assert fleet_risk.governed_clip_scale(1.0, "enforce") == (1.0, 1.0)


def test_advisory_mode_releases_clip_to_one_but_keeps_raw():
    # IMB-16: throwing the kill switch restores FULL clip size, and the raw
    # governor value is preserved for display/forensics.
    published, raw = fleet_risk.governed_clip_scale(0.25, "advisory")
    assert published == 1.0
    assert raw == 0.25


def test_any_non_enforce_mode_releases():
    for mode in ("advisory", "off", "", "ADVISORY".lower()):
        assert fleet_risk.governed_clip_scale(0.5, mode)[0] == 1.0
