"""Tier 1 — EquityGuard: the dislocation guard on venue equity reads.

The 2026-07-11 incident: Lighter printed a ~-25% dislocated equity while every
held coin's book moved <1%; that print tripped the daily-loss rail and the
flatten sold into the dislocation. This guard exists to reject such a print
BEFORE it reaches the rail. It has an injectable, pure design (mid providers /
clock / persistence) — and had zero coverage. This file exercises every verdict
path: mark-cross-check, forced-fresh re-read, continuity, cash-move escape,
rebase self-heal, the boot double-read, and state restore.
"""
import pytest

from venues import equity_guard as eg
from venues.equity_guard import EquityGuard, EquityRejected, vet_account_read

T = 1_700_000_000.0  # fixed clock


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    # Pin the guard's tolerances to their documented pilot defaults so a stray
    # CI env var can't loosen/tighten the bands under the tests.
    for k, v in {
        "LIGHTER_EQUITY_GUARD": "1",
        "LIGHTER_EQUITY_TOL_ABS": "1.0",
        "LIGHTER_EQUITY_TOL_NTL_PCT": "0.01",
        "LIGHTER_EQUITY_TOL_EQ_PCT": "0.002",
        "LIGHTER_EQUITY_REBASE_AFTER": "3",
        "LIGHTER_EQUITY_BOOT_CONFIRM_S": "5",
    }.items():
        monkeypatch.setenv(k, v)


def _guard(cached, fresh=None, **kw):
    """Build a guard with static mid providers and a frozen clock."""
    fresh = cached if fresh is None else fresh
    return EquityGuard(
        mids_cached=lambda coins: {c: cached.get(c) for c in coins},
        mids_fresh=lambda coins: {c: fresh.get(c) for c in coins},
        now=lambda: T,
        **kw,
    )


def _pos(size, entry, upnl=None):
    d = {"size": size, "entry": entry}
    if upnl is not None:
        d["upnl"] = upnl
    return d


# ── disabled / flat ──────────────────────────────────────────────────────────
def test_disabled_passthrough(monkeypatch):
    monkeypatch.setenv("LIGHTER_EQUITY_GUARD", "0")
    g = _guard({"BTC": 100.0})
    v = g.evaluate(999.0, 999.0, {"BTC": _pos(1, 100, upnl=0)})
    assert v.accepted and v.equity == 999.0 and v.reason == "disabled"


def test_flat_account_accepts_and_baselines():
    g = _guard({})
    v = g.evaluate(1000.0, 1000.0, {"BTC": _pos(0.0, 100)})  # zero size = flat
    assert v.accepted and v.reason == "flat"
    assert g.has_state


# ── mark cross-check ─────────────────────────────────────────────────────────
def test_mark_gap_rejects_phantom_print():
    # Book flat at 100, but venue claims -25 unrealized -> marks disagree w/ book.
    g = _guard({"BTC": 100.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert not v.accepted and v.reason == "mark_gap" and v.equity is None


def test_corroborated_crash_is_accepted():
    # A REAL crash: book actually fell to 75, venue upnl -25 agrees -> accept.
    g = _guard({"BTC": 75.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert v.accepted and v.reason == "ok"


def test_forced_fresh_read_rescues_a_fast_crash():
    # Cached ws mid is stale (still 100) so the first judge flags a gap, but the
    # forced-fresh REST read shows the true 75 and the print is corroborated.
    g = _guard(cached={"BTC": 100.0}, fresh={"BTC": 75.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert v.accepted and v.reason == "ok"


# ── continuity ───────────────────────────────────────────────────────────────
def _baseline(g):
    # Establish an accepted read: 1 BTC @100, book 100, equity 100.
    v = g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})
    assert v.accepted
    return g


def test_continuity_rejects_corrupt_total():
    # Same book (mid 100, unchanged size), but the venue total jumps to 75 with
    # no mid move to explain it. upnl omitted so only continuity can fire.
    g = _baseline(_guard({"BTC": 100.0}))
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert not v.accepted and v.reason == "continuity"


def test_cash_move_escape_accepts_a_deposit():
    # Baseline: 1 BTC, book 95, upnl -5, collateral 105, total 100.
    g = _guard({"BTC": 95.0})
    assert g.evaluate(100.0, 105.0, {"BTC": _pos(1, 100, upnl=-5.0)}).accepted
    # Deposit $30: collateral 135, total 130, positions & book unchanged. The
    # jump is fully explained by collateral (ledger-grade) -> ACCEPT not reject.
    v = g.evaluate(130.0, 135.0, {"BTC": _pos(1, 100, upnl=-5.0)})
    assert v.accepted and v.reason == "ok"


def test_cash_escape_disabled_without_discriminating_upnl():
    # Same $30 jump, but |sum(upnl)| is within tolerance, so collateral==total
    # semantics are indistinguishable and the escape must stay OFF -> reject.
    g = _guard({"BTC": 100.0})
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    v = g.evaluate(130.0, 130.0, {"BTC": _pos(1, 100, upnl=0.0)})
    assert not v.accepted and v.reason == "continuity"


# ── rebase self-heal ─────────────────────────────────────────────────────────
def test_continuity_rebases_after_consistent_rejects():
    g = _baseline(_guard({"BTC": 100.0}))
    # rebase_after=3: two rejects, then the third consistent print rebases.
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)}).reason == "continuity"
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)}).reason == "continuity"
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert v.accepted and v.reason == "rebase" and v.equity == 75.0


def test_mark_gap_needs_4x_more_rejects_to_rebase():
    # mark_gap carries live counter-evidence, so its rebase bar is 4x higher:
    # three consistent mark-gap rejects must NOT rebase (still rejected).
    g = _guard({"BTC": 100.0})
    for _ in range(3):
        v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
        assert not v.accepted and v.reason == "mark_gap"


# ── tolerance ────────────────────────────────────────────────────────────────
def test_tolerance_is_max_of_the_three_bands():
    g = _guard({})
    # abs floor dominates for tiny books
    assert g.tolerance(10.0, 10.0) == 1.0
    # notional band: 1% of gross
    assert g.tolerance(1000.0, 100.0) == pytest.approx(10.0)
    # equity band: 0.2% of |equity|
    assert g.tolerance(100.0, 10000.0) == pytest.approx(20.0)


# ── vet_account_read: boot double-read + wiring ──────────────────────────────
def test_vet_disabled_returns_raw(monkeypatch):
    monkeypatch.setenv("LIGHTER_EQUITY_GUARD", "0")
    g = _guard({"BTC": 100.0})
    got = vet_account_read(g, lambda: (123.0, 123.0, {}), sleep=lambda s: None)
    assert got == 123.0


def test_vet_cold_boot_double_reads():
    g = _guard({"BTC": 100.0})
    calls = {"fetch": 0, "slept": []}

    def fetch():
        calls["fetch"] += 1
        return (100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})

    got = vet_account_read(g, fetch, sleep=lambda s: calls["slept"].append(s))
    assert got == 100.0
    assert calls["fetch"] == 2          # boot demands two agreeing reads
    assert calls["slept"] == [5.0]      # spaced by boot_confirm_s


def test_vet_cold_boot_rejects_before_sleeping():
    g = _guard({"BTC": 100.0})
    slept = []

    def fetch():
        return (75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})  # dislocated

    with pytest.raises(EquityRejected):
        vet_account_read(g, fetch, sleep=lambda s: slept.append(s))
    assert slept == []                  # never slept — rejected on first read


def test_vet_warm_state_single_read():
    g = _baseline(_guard({"BTC": 100.0}))  # already has state
    calls = {"fetch": 0}

    def fetch():
        calls["fetch"] += 1
        return (100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})

    got = vet_account_read(g, fetch, sleep=lambda s: pytest.fail("should not sleep"))
    assert got == 100.0 and calls["fetch"] == 1


# ── persisted-state restore ──────────────────────────────────────────────────
def test_state_restore_within_age():
    st = {"ts": T - 3600.0, "equity": 100.0, "collateral": 100.0,
          "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}}
    g = _guard({"BTC": 100.0}, load_state=lambda: st)
    assert g.has_state and g._last["equity"] == 100.0


def test_state_restore_ignores_stale_snapshot():
    st = {"ts": T - 8 * 86400.0, "equity": 100.0, "collateral": 100.0,
          "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}}
    g = _guard({"BTC": 100.0}, load_state=lambda: st)
    assert not g.has_state           # >7d old snapshot proves nothing about today
