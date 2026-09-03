"""[2026-09-03 (xv)] THE HALT-COST REGISTRATION, PINNED.

Eamon asked whether 👩 mum's daily-loss halt costs or saves her. It cannot be
answered today and the reason is the point: her ledger holds **one** daily-loss
halt (2-Sep 17:19:45Z, 8 legs), and all eight legs closed in one flatten on one
falling minute. That is ONE observation. Counting the legs instead gives a
7-of-7 sign test at p≈0.008 — a number that looks decisive and is an artifact
of treating a single market moment as seven independent draws ((kw)/(ky)).

So the criterion is fixed NOW, before the data arrives (I21), and these tests
exist to stop it being quietly moved once a bad week makes loosening attractive.

THE ASYMMETRY THAT MAKES THAT NECESSARY: a rail's cost is visible every time it
fires; its benefit shows only on the day it prevents a ruinous loss, which has
not happened yet. A cost-only study reads "loosen" on every ordinary halt day
right up until the day it doesn't. Hence: the default verdict is KEEP and the
burden sits on loosening.
"""
import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts" / "study_mum_halt_cost_2026-09-03.py"


def _mod():
    spec = importlib.util.spec_from_file_location("halt_cost", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _mod()


def _leg(coin, closed, pct, opened="2026-09-02T10:00:00", bot=None):
    return {"bot": bot or M.LIVE, "pair": f"{coin}/USDC",
            "reason": "long-oversold-rebound_daily_loss",
            "closed_at": closed, "opened_at": opened, "pnl_pct": pct / 100.0}


# ------------------------------------------------ one halt is ONE observation
def test_a_flatten_spanning_seconds_is_still_ONE_event():
    """The defect the calibration gate caught during development: keying on the
    exact timestamp split one flatten into many 'events' and inflated the count
    toward a decision. `halted_today` latches once per UTC day, so a day is a
    halt."""
    rows = [_leg("A", "2026-09-02T17:19:45.876379", -3.0),
            _leg("B", "2026-09-02T17:19:47.101010", -2.0),
            _leg("C", "2026-09-02T17:24:51.900000", -1.0)]   # a later retry
    ev = M.halt_events(rows)
    assert len(ev) == 1, f"one flatten must be one event, got {list(ev)}"
    assert len(next(iter(ev.values()))) == 3
    assert next(iter(ev)).startswith("2026-09-02T17:19:45"), "key = first leg"


def test_two_different_days_are_two_events():
    rows = [_leg("A", "2026-09-02T17:19:45", -3.0),
            _leg("B", "2026-09-04T11:00:00", -2.0)]
    assert len(M.halt_events(rows)) == 2


def test_only_the_live_arm_and_only_daily_loss_rows_count():
    rows = [_leg("A", "2026-09-02T17:19:45", -3.0, bot=M.SHADOW),
            {"bot": M.LIVE, "pair": "B/USDC", "pnl_pct": -0.03,
             "reason": "long-oversold-rebound_stop_loss",
             "closed_at": "2026-09-02T17:19:45", "opened_at": "x"}]
    assert M.halt_events(rows) == {}, \
        "a stop-loss is not a halt, and the twin never halts"


# ------------------------------------------------------- the criterion is FIXED
def test_the_bar_is_five_EVENTS_not_legs_and_the_default_is_KEEP():
    assert M.MIN_EVENTS >= 5, "loosening a real-money rail needs >=5 events"
    assert M.LOOSEN_COST_PP >= 1.0, "the cost bar may not be lowered silently"
    crit = M.PRE_REGISTERED["criterion"]
    assert "EVENTS (instants, not legs)" in crit
    assert "otherwise KEEP" in crit, "the default verdict must be KEEP"


def test_the_registration_records_its_own_at_registration_numbers():
    """A commitment, not a re-derivation (I21) — so a later run cannot quietly
    restate what was registered."""
    r = M.PRE_REGISTERED["at_registration"]
    assert r["halt_events"] == 1 and r["legs"] == 8 and r["paired_legs"] == 7
    assert r["cost_pp_per_leg"] == pytest.approx(1.76, abs=0.01)
    # the I25 control, on the PAIRED window
    assert r["baseline_live_mean_pct"] == pytest.approx(0.720, abs=0.001)
    assert r["baseline_twin_mean_pct"] == pytest.approx(0.625, abs=0.001)
    assert r["baseline_live_mean_pct"] > r["baseline_twin_mean_pct"], \
        "the registration records that live BEATS the twin off halt days"


def test_the_registered_event_is_never_re_mined_as_fresh():
    """I21: the window that generated the hypothesis cannot also decide it."""
    src = SCRIPT.read_text()
    assert "is_fresh = _ts(inst).date() > reg_day" in src
    assert "not_yet_decidable" in src


# ------------------------------------------------------- the baseline is paired
def test_the_baseline_is_restricted_to_the_paired_window():
    """A control arm on a different window is not a control. Unrestricted, the
    twin scores over 21 extra days and the verdict FLIPS (+1.105 vs +0.625)."""
    rows = [
        # live: one close, inside the window
        {"bot": M.LIVE, "pair": "A/USDC", "reason": "long_roi",
         "closed_at": "2026-09-01T00:00:00", "opened_at": "2026-09-01",
         "pnl_pct": 0.01},
        # twin: one inside, one 3 weeks BEFORE live existed
        {"bot": M.SHADOW, "pair": "A/USDC", "reason": "long_roi",
         "closed_at": "2026-09-01T00:00:00", "opened_at": "2026-09-01",
         "pnl_pct": 0.02},
        {"bot": M.SHADOW, "pair": "A/USDC", "reason": "long_roi",
         "closed_at": "2026-08-07T00:00:00", "opened_at": "2026-08-07",
         "pnl_pct": 0.99},
    ]
    b = M.baseline(rows, set())
    assert b["twin"][0] == 1, "the pre-window twin close must be excluded"
    assert b["twin"][1] == pytest.approx(2.0, abs=1e-9)
    assert b["since"] == "2026-09-01"


# ----------------------------------------------------------- the pairing rule
def test_an_unpairable_leg_is_reported_never_imputed():
    legs = [_leg("GHOST", "2026-09-02T17:19:45", -3.0)]
    cost, n, detail = M.pair_event(legs, [])
    assert cost is None and n == 0
    assert detail and detail[0][2] is None, "unpaired must surface as None"


def test_the_twin_leg_must_close_at_or_after_the_halted_legs_open():
    """A twin close from BEFORE the halted leg was even opened is not a
    counterfactual for it."""
    legs = [_leg("A", "2026-09-02T17:19:45", -3.0, opened="2026-09-02T10:00:00")]
    stale = [{"bot": M.SHADOW, "pair": "A/USDC", "reason": "long_roi",
              "closed_at": "2026-09-02T09:00:00", "pnl_pct": 0.05}]
    cost, n, _ = M.pair_event(legs, stale)
    assert n == 0, "a pre-open twin close must not be paired"


# ------------------------------------------------- the carried row cannot drop
def test_the_read_is_carried_so_it_cannot_be_forgotten():
    sys.path.insert(0, str(ROOT / "scripts"))
    import session_state as ss                       # noqa: PLC0415
    row = next((c for c in ss.CARRIED
                if c["id"] == "mum-halt-cost-preregistered-read"), None)
    assert row is not None, "the pre-registered read is not carried"
    assert row["closes_when"]() is False, \
        "it must stay OPEN until the read is taken and the block removed"
