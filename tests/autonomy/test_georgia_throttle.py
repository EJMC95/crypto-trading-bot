#!/usr/bin/env python3
"""[2026-08-22 (sv)] THE RATE LIMITER WAS CUTTING 🔮 georgia's BEST ENTRIES.

She is the fleet's closest book to real money — 5 of 6 go-live bars, failing
only `t` (1.48 against 2.0) — so the single thing between her and a live row is
CLOSES. Measured on her own 163-trade ledger, ranking each entry by its
position within its own clock hour:

    entry #1 of the hour   n=127   +0.023%/trade   t=+0.21   $ +3.95
    entry #2 of the hour   n= 36   +0.656%/trade   t=+2.20   $+11.90

75% of her realised P&L sits on 22% of her trades, and those are the ones
`MAX_ENTRIES_PER_HOUR = 2` was closest to refusing. She hit the cap in 34 hours.

SIX SPLITS, ALL THE SAME SIGN — not the 19-21 Aug trending burst, not a
tag-mix artifact: surge days +0.608pp / before +0.390pp; first half of her life
+0.480pp / second half +0.756pp; within trend_breakout +0.614pp, within
range_on +0.738pp.

WHY 3 AND NOT UNLIMITED: the cap censored its own evidence. Rank 3 has n=1 in
her entire life *because the cap is 2*, so anything above rank 2 is
extrapolation. One step generates the sample that grades the next, and
`entry_rank` is now recorded so that grade is a query rather than another
reconstruction from timestamps (I23).

These tests pin the mechanism, never the verdict:
  1-3  the cap is a real bound, steps to 3, and stays operator-overridable;
  4-6  the rank is recorded, is the granted rank, and is ABSENT (never a
       fabricated 1) on a book that has no throttle;
  7    the blast radius: DayTraderGated is georgia plus one RETIRED book, so
       this moves exactly one living row;
  8    it is NOT an era reset — capacity is ordinary tuning ((hc)), and
       resetting would discard the 163 closes the change exists to add to.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam            # noqa: E402


def _georgia():
    return [s for s in fam.STRATEGIES if s.bot == "freqtrade-georgia"][0]


class _B:
    """The throttle's real host, with only what throttle_ok touches."""
    def __init__(self, strat):
        self.s = strat
        self.throttle = {"bucket": None, "n": 0, "last_rank": None}
    throttle_ok = fam.Book.throttle_ok


def test_the_cap_is_three_and_it_actually_binds():
    b = _B(_georgia())
    t = 1_000_000 * 3600.0                       # a clean hour boundary
    granted = [b.throttle_ok(t + i) for i in range(6)]
    assert granted[:3] == [True, True, True], granted
    assert granted[3:] == [False, False, False], "the cap must still be a bound"


def test_the_next_hour_resets_it():
    b = _B(_georgia())
    t = 1_000_000 * 3600.0
    for _ in range(4):
        b.throttle_ok(t)
    assert b.throttle_ok(t + 3600) is True, "a new clock hour must re-arm"


def test_the_cap_stays_operator_overridable():
    """A rate limiter on the book nearest real money must be reversible without
    a deploy — the same contract every other bar on these books carries."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert 'os.environ.get(\n        "GEORGIA_MAX_ENTRIES_PER_HOUR", "3")' in src \
        or 'GEORGIA_MAX_ENTRIES_PER_HOUR' in src, "no env override on the cap"
    assert _georgia().MAX_ENTRIES_PER_HOUR == 3, "the shipped step is 2 -> 3"


def test_the_rank_is_recorded_and_is_the_granted_rank():
    """I23: the knob must record the quantity it cuts. (sv) was decided by
    reconstructing this from open timestamps; that must not be needed twice."""
    b = _B(_georgia())
    t = 1_000_000 * 3600.0
    seen = []
    for _ in range(3):
        b.throttle_ok(t)
        seen.append(b.throttle["last_rank"])
    assert seen == [1, 2, 3], seen


def test_a_refused_entry_does_not_advance_the_rank():
    """A refusal is not an entry — if it bumped the counter the recorded rank
    would drift away from the trade it describes."""
    b = _B(_georgia())
    t = 1_000_000 * 3600.0
    for _ in range(3):
        b.throttle_ok(t)
    assert b.throttle_ok(t) is False
    assert b.throttle["last_rank"] == 3, "a refusal moved the recorded rank"


def test_a_book_without_a_throttle_publishes_NO_rank():
    """SwingDip and the rest have no throttle, so `1` would be a fabricated
    reading of a gate they do not run (I8: unknown never degrades to a guess)."""
    swing = [s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria"][0]
    b = _B(swing)
    b.throttle["last_rank"] = 7                  # stale value from nowhere
    assert b.throttle_ok(1_000_000 * 3600.0) is True
    assert b.throttle["last_rank"] is None, "a throttle-less book invented a rank"
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert 'if m.get("entry_rank") is not None else None' in src, \
        "the close row must omit the rank rather than publish a fake one"


def test_the_blast_radius_is_one_living_book():
    """DayTraderGated is 🔮 georgia and the RETIRED crypto-intraday-15m, so
    this change reaches exactly one row that still trades."""
    users = [s.bot for s in fam.STRATEGIES
             if isinstance(s, fam.DayTraderGated)]
    living = [b for b in users if b not in fam.RETIRED_BOOKS]
    assert living == ["freqtrade-georgia"], (users, living)


def test_capacity_is_not_an_era_reset():
    """(hc): ordinary tuning — a lever step, a widened universe, a clip change
    — does NOT reset the policy era. Resetting georgia's would discard the 163
    closes this change exists to add to, on the book whose only failing bar is
    the one that needs them."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import golive_readiness as gl
    era = getattr(gl, "POLICY_ERA", {})
    for key in ("freqtrade-georgia", "freqtrade-georgia-lshadow"):
        assert "2026-08-22" not in str(era.get(key, "")), (
            f"{key} had its era moved to today — a throttle step is capacity, "
            f"not a change of kind")
