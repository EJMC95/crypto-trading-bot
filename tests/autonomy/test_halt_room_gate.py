#!/usr/bin/env python3
"""[2026-09-02 (xe)] THE HALT-AWARE ENTRY GATE: a leg whose own stop would end
the day for the WHOLE book is refused.

Eamon, 2-Sep: *"Let it run, but optimise and enhance as best as possible."*

WHY THIS RAIL EXISTS, and why it is not just another cap. The daily-loss halt
does not close one position — it FLATTENS every leg at whatever the mark is
and shuts entries to the UTC roll. So an entry taken while the book's room to
that level is smaller than that entry's OWN stop carries the entire book's
downside: one −4% on the new leg ends the day for all twelve and sells every
held dip at the low, which is the exact loss 👩 mum's thesis (buy deep-oversold,
wait up to 24h for the rebound) cannot absorb. Measured on the day it shipped:
her live row sat **$14 above the halt — a 0.42% basket move — with 10 legs open
at 6.2× while a fresh entry was still admissible.**

MEASURED BEFORE IT SHIPPED, not asserted (`scripts/study_mum_gross_halt_2026-
09-02.py --sweep`, her own cell replayed as a 12-slot book on the live 64-coin
universe, calibrated against her shadow twin's ledger). Rule pre-declared in
the study: ship only if the gate never lowers 30d total AND lowers halts or
drawdown somewhere.
    trailing 30d  @3.75x: total +28.78% -> +28.78%, maxDD 13.17 -> 13.17,
                          0 entries gated   (INERT in the regime she trades)
    trailing 120d @3.75x: total −56.48% -> −50.20% (+6.28pp),
                          maxDD 70.0 -> 65.7 (−4.3pp), 27 entries gated
    trailing 120d @9.5x : total −56.48%-class books gate 27 entries; at the
                          gross she ran until today it is the difference
                          between one stop and a flatten.

THESE TESTS DRIVE THE REAL `main()` one cycle against a stub venue (the (sz)
boot-smoke harness) rather than reading the source — behaviour, not shape:
  1-4  `halt_room` fails OPEN on every unreadable input (the direction that
       matters: a dark read must never invent a refusal, nor a permission);
  5-6  the TIGHTER of the two rails wins, in BOTH directions — the pct leash
       when it binds, the absolute cap when IT binds. A gate guarding a looser
       level than the one that actually fires is worse than no gate;
  7    a cycle with room BELOW one stop sends NO order and says so on the row
       (`entry_vetoes.halt_room_skips`, I18: `opened: 0` must never be
       byte-identical between "quiet" and "a rail refused everything");
  8    a cycle with room to spare is BYTE-IDENTICAL to before — the rail is
       inert when it should be, which is what the 30d measurement predicts;
  9    a junk absolute cap does not silently OPEN the gate — the pct leash
       still governs (fail-open must not mean fail-permissive on a rail);
  10   the gate never suppresses the halt itself: at a real breach the book
       still flattens.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.autonomy.test_variant_host import loaded, _driven   # noqa: E402

ROW = "freqtrade-mum-lighter"


class _Rails:
    """Only what `halt_room` reads."""
    def __init__(self, cap=30.0):
        self.max_daily_loss = cap


def _state(meta, day_start):
    return {"initial_equity": 200.0, "meta": meta,
            "day_start": {"day": time.strftime("%Y-%m-%d", time.gmtime()),
                          "equity": day_start}}


def _cycle(day_start, cap=30.0, meta=None, pos=None):
    """One real cycle of mum's `main()` with a chosen day-start anchor."""
    with loaded("freqtrade-mum", MUM_GROSS_X="2") as m:
        with _driven(m, tape="oversold") as box:
            box["rails"].max_daily_loss = cap
            box["venue"].pos = dict(pos or {})
            box["state"][m.STATE_KEY] = _state(meta or {}, day_start)
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            out = dict(box)
            pubs = [kw for b, kw in box["published"] if b == ROW]
            out["pub"] = pubs[-1] if pubs else None
            out["vetoes"] = pubs[-1]["extra"]["entry_vetoes"] if pubs else {}
    return out


# ---- 1-4  fail OPEN on anything unreadable ---------------------------------

def test_halt_room_is_none_on_a_dark_equity_or_day_start():
    with loaded("freqtrade-mum") as m:
        r = _Rails()
        assert m.halt_room(None, 200.0, r) is None
        assert m.halt_room(200.0, None, r) is None
        assert m.halt_room("junk", 200.0, r) is None
        assert m.halt_room(200.0, "junk", r) is None


def test_halt_room_is_none_on_nan_or_a_nonpositive_day_start():
    with loaded("freqtrade-mum") as m:
        r = _Rails()
        assert m.halt_room(float("nan"), 200.0, r) is None
        assert m.halt_room(200.0, float("nan"), r) is None
        assert m.halt_room(200.0, 0.0, r) is None
        assert m.halt_room(200.0, -5.0, r) is None


def test_a_junk_absolute_cap_leaves_the_pct_leash_alone():
    """A cap that cannot be read must not remove the rail that CAN be —
    UNREADABLE only: a string, an absent value, NaN, an infinity."""
    with loaded("freqtrade-mum") as m:
        for junk in ("nonsense", None, float("nan"), float("inf")):
            got = m.halt_room(200.0, 220.0, _Rails(cap=junk))
            assert abs(got - (200.0 - 220.0 * (1 - m.DAILY_LOSS_LIMIT))) < 1e-9, \
                (junk, got)


def test_a_zero_or_negative_cap_is_a_REAL_rail_and_is_measured_as_one():
    """NOT junk, and this direction is the safety-relevant one.
    `SafetyRails.daily_loss_hit` trips at `loss >= cap`, so a cap of $0 halts
    the book on the first cent and a negative cap halts it immediately. A
    `cap > 0` guard in the level read this as "no absolute rail" and would
    have handed the gate room against a level the actuator had already
    passed. Caught by a parity grid against the expression this replaces —
    reading the code had said the guard was harmless."""
    with loaded("freqtrade-mum") as m:
        # cap 0 -> the level IS day-start: any loss at all ends the day.
        assert abs(m.halt_room(200.0, 220.0, _Rails(cap=0.0)) - (-20.0)) < 1e-9
        assert m.halt_level(220.0, _Rails(cap=0.0))[1] == "abs"
        # a negative cap is tighter still, and must never read as room.
        assert m.halt_room(220.0, 220.0, _Rails(cap=-5.0)) < 0
        assert m.halt_level(220.0, _Rails(cap=-5.0))[1] == "abs"


def test_a_rails_object_with_no_cap_attribute_at_all_still_measures():
    with loaded("freqtrade-mum") as m:
        class _Bare:
            pass
        got = m.halt_room(200.0, 220.0, _Bare())
        assert abs(got - (200.0 - 220.0 * (1 - m.DAILY_LOSS_LIMIT))) < 1e-9


# ---- 5-6  the TIGHTER rail wins, both directions ---------------------------

def test_the_absolute_cap_wins_when_it_is_the_tighter_rail():
    """$1,000 day-start: the pct leash allows a $100 loss, the $57 cap allows
    $57 — the CAP is what fires, so it is what the gate must measure."""
    with loaded("freqtrade-mum") as m:
        got = m.halt_room(1000.0, 1000.0, _Rails(cap=57.0))
        assert abs(got - 57.0) < 1e-9, got          # not 100.0


def test_the_pct_leash_wins_when_IT_is_the_tighter_rail():
    """$300 day-start: the pct leash allows $30, the $57 cap allows $57 — the
    LEASH fires first, so the gate must not read the looser cap."""
    with loaded("freqtrade-mum") as m:
        got = m.halt_room(300.0, 300.0, _Rails(cap=57.0))
        assert abs(got - 30.0) < 1e-9, got          # not 57.0


# ---- 7  room below one stop -> no order, and the row says so ---------------

def test_an_entry_whose_own_stop_would_halt_the_book_is_refused():
    # day-start 221 vs equity 200: pct level 198.90 (tighter than 221-30=191),
    # so room is $1.10 while one stop on a $33.33 clip is $1.33. Not halted
    # (200 > 198.90) — the exact state the gate exists for.
    out = _cycle(day_start=221.0)
    assert out["venue"].opens == [], f"order sent with no halt room: {out['venue'].opens}"
    assert out["vetoes"].get("halt_room_skips", 0) >= 1, out["vetoes"]
    assert any("HALT_ROOM_SKIP" in p for p in out["printed"]), out["printed"][-6:]


# ---- 8  room to spare -> inert ---------------------------------------------

def test_a_book_with_room_trades_exactly_as_before():
    out = _cycle(day_start=200.0)
    assert out["venue"].opens, "the gate must be inert when there is room"
    assert out["vetoes"].get("halt_room_skips", 0) == 0, out["vetoes"]
    assert not any("HALT_ROOM_SKIP" in p for p in out["printed"])


# ---- 9  a junk cap does not open the gate ----------------------------------

def test_a_junk_cap_does_not_silently_open_the_gate():
    out = _cycle(day_start=221.0, cap="nonsense")
    assert out["venue"].opens == [], out["venue"].opens
    assert out["vetoes"].get("halt_room_skips", 0) >= 1, out["vetoes"]


# ---- 10  the halt itself still fires ---------------------------------------

def test_the_gate_never_suppresses_the_halt_itself():
    """A real breach must still flatten — the gate sits in front of ENTRIES and
    must not have reordered the rail that closes positions. The flatten reads
    the VENUE, not meta, so the position is seeded on both."""
    held = {"BTC": {"size": 0.15, "entry": 100.0}}
    out = _cycle(day_start=250.0, pos=held,
                 meta={"BTC": {"entry": 100.0, "opened_ts": time.time() - 3600,
                               "tag": "oversold-rebound", "size": 0.15,
                               "accrued": 0.0}})
    assert out["venue"].closes == ["BTC"], "a breach must still flatten the book"
    assert out["venue"].opens == []


# ---- 11-12  the row's `binding` comes from the SAME owner ------------------

def test_the_row_reports_which_rail_binds_from_the_gates_own_owner():
    """`halt.binding` used to re-derive the tighter-rail comparison inline —
    (hj)'s second copy of a rule, on a real-money row. It reads the owner now,
    and the two must agree by construction."""
    with loaded("freqtrade-mum") as m:
        for ds, cap, want in ((1000.0, 57.0, "abs"),      # cap is tighter
                              (300.0, 57.0, "pct"),       # leash is tighter
                              (570.0, 57.0, "pct")):      # exactly equal -> leash
            assert m.halt_level(ds, _Rails(cap))[1] == want, (ds, cap)


def test_a_non_numeric_cap_can_no_longer_raise_inside_the_publish_path():
    """The old inline comparison threw `TypeError: '<' not supported between
    str and float` from INSIDE the row build — a telemetry field able to take
    down the loop that publishes it. Driven: the cycle completes and the row
    is published."""
    out = _cycle(day_start=221.0, cap="nonsense")
    assert out["pub"] is not None, "the row must still publish"
    assert out["pub"]["extra"]["leverage"]["halt"]["binding"] == "pct"
