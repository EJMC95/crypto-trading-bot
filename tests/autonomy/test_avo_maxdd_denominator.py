#!/usr/bin/env python3
"""[2026-09-02] THE MAXDD PROTECTION WAS MEASURING 4% OF THE BOOK AND CALLING
IT 20% — a frozen-seed denominator idled a funded real-money book ~103h.

🙏 Avo Maria's live arm locks entries when the book-level MaxDrawdown rail
trips: a peak-to-trough drawdown of her recent closes >= `maxdd.dd` (0.20) of
a denominator. (vm) set that denominator to `state.initial_equity` — correct
when she WAS a $63 book, and the reason it read "the LIVE baseline instead of
the shadow's $1,000". But `initial_equity` is her BIRTH seed and never tracked
deposits: Eamon funded her $62.93 -> $305, so 20% of the frozen $62.80 is
**$12.56**, LESS than a single -4% stop on her leveraged $323 clip. Measured on
her own live ledger her worst drawdown was $22.12 (7% of her real equity) —
under the intended 20% bar, over the accidental one — so maxdd fired on 4 of
her last 5 days and idled the live arm ~103h while her shadow twin (same
strategy, $1,000 denominator that simply never binds) traded on_track.

`maxdd_ref` moves the RISK denominator to the funded book (day-start equity,
the capital-adjusted (mi) daily-loss anchor) while the P&L anchor stays the
seed. These tests pin: the helper's preference order and dark fallback; that
avo's real drawdown LOCKS at the frozen seed and does NOT at the funded book;
and that the loop actually passes `maxdd_ref(...)` and not the raw baseline
(the revert this whole fix guards against).
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
os.environ.setdefault("AVO_VENUE", "lighter_live")

import lighter_avo_live_bot as A  # noqa: E402

# The live numbers this test was written from (row payload, 2026-09-01).
SEED = 62.795571          # state.initial_equity — her pre-funding seed
FUNDED = 305.082036       # equity today, after Eamon's deposits
DD = 0.20                 # SwingDip maxdd.dd
REAL_DRAWDOWN = 22.12     # her worst peak-to-trough over the whole live ledger


# ---- the helper: funded equity wins, seed is the last resort ---------------

def test_maxdd_ref_prefers_day_start_over_the_frozen_seed():
    """The whole fix in one line: day-start (funded) beats initial_equity."""
    assert A.maxdd_ref(FUNDED, 300.0, SEED) == FUNDED
    # a revert to `baseline`-first would return SEED here and fail
    assert A.maxdd_ref(FUNDED, 300.0, SEED) != SEED


def test_maxdd_ref_falls_back_through_equity_then_seed():
    assert A.maxdd_ref(None, FUNDED, SEED) == FUNDED      # day-start dark
    assert A.maxdd_ref(None, None, SEED) == SEED          # only the seed left
    assert A.maxdd_ref(0.0, 0.0, SEED) == SEED            # zeros are not equity


def test_maxdd_ref_is_none_when_everything_is_dark():
    # entries_lock then fails OPEN to $1,000 — a looser protection on dark
    # data is the safe direction, and matches its own `else 1000.0`.
    assert A.maxdd_ref(None, None, None) is None
    assert A.maxdd_ref(0, 0, 0) is None


# ---- the incident and the fix, through the real protection -----------------

def _avo_drawdown_closes(t_now):
    """Four NON-STOP closes inside the 160h maxdd window summing to a ~$22
    peak-to-trough drawdown — her real live figure. Non-stop on purpose so
    StoplossGuard (2 stops) cannot fire and confound the maxdd reading."""
    h = 3600.0
    return [
        {"ts": t_now - 10 * h, "pnl": -9.0, "stop": False},
        {"ts": t_now - 8 * h, "pnl": -14.0, "stop": False},
        {"ts": t_now - 6 * h, "pnl": +2.0, "stop": False},
        {"ts": t_now - 4 * h, "pnl": +2.0, "stop": False},
    ]  # cumulative 0 -> -9 -> -23 -> -21 -> -19; drawdown = 23 (~ $22.12)


def test_avo_drawdown_locks_at_the_frozen_seed():
    """The bug: $23 of drawdown is 37% of the $62.80 seed -> maxdd LOCKS."""
    t_now = 1_000_000.0
    until, cause = A.entries_lock(_avo_drawdown_closes(t_now), t_now, SEED)
    assert cause == "maxdd"
    assert until > t_now
    assert REAL_DRAWDOWN / SEED > DD          # 0.35 > 0.20 — the accidental bar


def test_avo_drawdown_does_not_lock_at_the_funded_book():
    """The fix: the same drawdown is 7% of her real $305 -> NO lock."""
    t_now = 1_000_000.0
    until, cause = A.entries_lock(_avo_drawdown_closes(t_now), t_now, FUNDED)
    assert cause is None
    assert until == 0.0
    assert REAL_DRAWDOWN / FUNDED < DD        # 0.07 < 0.20 — the intended bar


def test_a_genuine_twenty_percent_drawdown_still_locks_the_funded_book():
    """The fix restores the 20% bar, it does not remove it: a real -20% of the
    funded book still trips maxdd, so the protection is intact at her scale."""
    t_now = 1_000_000.0
    h = 3600.0
    big = 0.25 * FUNDED  # a genuine 25% peak-to-trough drawdown
    closes = [
        {"ts": t_now - 9 * h, "pnl": -big / 2, "stop": False},
        {"ts": t_now - 7 * h, "pnl": -big / 2, "stop": False},
        {"ts": t_now - 5 * h, "pnl": 0.0, "stop": False},
        {"ts": t_now - 3 * h, "pnl": 0.0, "stop": False},
    ]
    until, cause = A.entries_lock(closes, t_now, FUNDED)
    assert cause == "maxdd"
    assert until > t_now


# ---- the wiring: the loop passes maxdd_ref(...), not the raw baseline -------

def test_the_loop_passes_maxdd_ref_to_entries_lock_not_the_raw_baseline():
    """AST pin on the call site. A revert to `entries_lock(..., baseline, ...)`
    — the exact regression this fix undoes — reddens here."""
    src = open(A.__file__).read()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id == "entries_lock"]
    assert calls, "no entries_lock call site found — has the loop moved?"
    for call in calls:
        # the maxdd denominator is the 3rd positional arg
        assert len(call.args) >= 3, "entries_lock call is missing its denominator arg"
        denom = call.args[2]
        assert isinstance(denom, ast.Call) and isinstance(denom.func, ast.Name) \
            and denom.func.id == "maxdd_ref", \
            "entries_lock must be called with maxdd_ref(...) as its denominator"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
