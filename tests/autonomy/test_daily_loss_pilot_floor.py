#!/usr/bin/env python3
"""[2026-09-02 (wh)] THE ABS DAILY-LOSS CAP IS A PILOT FLOOR, NOT A CEILING —
👩 mum funded $300 -> $570 was halting at 5.26%, not her intended 10%.

`SafetyRails.max_daily_loss` (`LIGHTER_MAX_DAILY_LOSS`, default $30) was a PILOT
cap from when the live books were seed-sized: $30 == 10% of a $300 book, so the
abs cap and the strategy's `DAILY_LOSS_LIMIT` (10%) COINCIDED. Eamon then moved
georgia's freed ~$220 into mum; at $570 the fixed $30 cap binds at **5.26%**
while her 10% leash intends **$57**, so the book would halt for the day on a
normal drawdown and miss the recovery — the same fixed-dollar-vs-funded-equity
class as 🙏 avo's maxdd denominator (wf).

The fix floors the pilot cap under the pct leash: the effective daily threshold
is `max(pilot_cap, pct_limit * day_start_equity)`, so the cap still protects a
tiny book and the pct leash governs a funded one. `pct_limit=0.0` (every caller
that does not pass it — the other live bots) is byte-identical to the old cap.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import venues.safety as safety  # noqa: E402


def _rails(max_daily_loss=30.0, live=True):
    r = safety.SafetyRails.__new__(safety.SafetyRails)
    r.live = live
    r.max_daily_loss = max_daily_loss
    return r


# ---- the default is unchanged for every caller that does not opt in ----------

def test_default_pct_zero_is_the_old_absolute_cap():
    r = _rails(30.0)
    # $40 loss on any book trips the old $30 cap regardless of size
    assert r.daily_loss_hit(570.0, 530.0) is True          # $40 >= $30
    assert r.daily_loss_hit(300.0, 270.0) is True          # $30 >= $30
    assert r.daily_loss_hit(570.0, 545.0) is False         # $25 < $30


# ---- the funded book: the pct leash governs, not the pilot cap ---------------

def test_mum_funded_halts_at_ten_percent_not_the_pilot_cap():
    r = _rails(30.0)
    # $570 book, 10% leash -> threshold max($30, $57) = $57
    assert r.daily_loss_hit(570.0, 530.0, 0.10) is False   # $40 = 7.0% < 10%
    assert r.daily_loss_hit(570.0, 513.0, 0.10) is True    # $57 = 10.0% >= 10%
    # and the OLD behaviour would have halted her at $40 — this is the fix
    assert r.daily_loss_hit(570.0, 530.0) is True           # (pct=0) old cap


def test_the_pilot_cap_still_floors_a_tiny_book():
    r = _rails(30.0)
    # $50 book, 10% = $5 -> threshold max($30, $5) = $30 (the floor protects it)
    assert r.daily_loss_hit(50.0, 20.0, 0.10) is True      # $30 >= $30
    assert r.daily_loss_hit(50.0, 25.0, 0.10) is False     # $25 < $30


def test_the_floor_never_tightens_the_pct_leash():
    """The effective threshold is the LOOSER of the two, so opting in can only
     RAISE the dollar threshold, never lower it — a book never halts sooner for
    passing its pct leash in."""
    r = _rails(30.0)
    for eq_start in (100.0, 300.0, 570.0, 1000.0, 5000.0):
        floored = max(30.0, 0.10 * eq_start)
        # just under the floored threshold never trips; at it, it trips
        assert r.daily_loss_hit(eq_start, eq_start - (floored - 0.01), 0.10) is False
        assert r.daily_loss_hit(eq_start, eq_start - floored, 0.10) is True
        # and the floored threshold is always >= the bare pilot cap
        assert floored >= 30.0


def test_dark_or_paper_never_halts():
    assert _rails(30.0, live=False).daily_loss_hit(570.0, 100.0, 0.10) is False
    assert _rails(30.0).daily_loss_hit(None, 100.0, 0.10) is False
    assert _rails(30.0).daily_loss_hit(570.0, None, 0.10) is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
