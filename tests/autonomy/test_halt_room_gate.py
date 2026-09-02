#!/usr/bin/env python3
"""[2026-09-02 (xg)] THE HALT-AWARE ENTRY GATE: a leg whose own stop would end
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

    WHAT THE MEASUREMENT DOES **NOT** SHOW, corrected after adversarial review:
    over that 120d window HALTS ARE UNCHANGED (18 with the gate, 18 without).
    The rail prevented no flattens at all. The gain comes from the 27 refused
    entries being net losers — it declines to open into a day already deep in
    drawdown, and those are bad entries. Flatten-avoidance is the design
    rationale and is UNTESTED; entry quality in a drawdown is what was
    measured. The study also replays the PCT leash only, while production takes
    the tighter of the leash and the absolute cap (on mum today they coincide
    at ~$57 on a $570 book, which is why the numbers stand).

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


def test_an_infinite_equity_or_day_start_is_unmeasurable_too():
    """The `x != x` idiom caught NaN and let INFINITY through; `math.isfinite`
    catches both. (CodeQL reads a self-comparison as a defect, and it was
    right that the check was doing less than it looked.)"""
    with loaded("freqtrade-mum") as m:
        r = _Rails()
        assert m.halt_room(float("inf"), 200.0, r) is None
        assert m.halt_room(200.0, float("inf"), r) is None
        assert m.halt_level(float("inf"), r) == (None, None)


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


# ---- 11-14  THE TWO REAL-MONEY DEFECTS AN ADVERSARIAL REVIEW FOUND ---------
#
# Both were in the first cut of this rail and both are pinned here.

def test_the_gate_refuses_to_arm_on_a_book_whose_one_stop_is_its_whole_leash():
    """🙏 avo runs 5 slots at 5x with a -10% stop, so her clip IS her equity and
    ONE slot-stop is 100% of her daily allowance. This module is the VARIANT
    HOST for both live books, so a rail sized on 👩 mum's geometry and shipped
    unscoped would have refused EVERY avo entry on any day she was fractionally
    down — silently stopping the fleet's other real-money book. Derived from
    the book's own geometry, never a hardcoded roster."""
    import os

    class _R:
        max_daily_loss = None

    for book, var, gx, want_armed in (
            ("freqtrade-avo-maria", "AVO_GROSS_X", "5.0", False),
            ("freqtrade-mum", "MUM_GROSS_X", "3.75", True)):
        with loaded(book, **{var: gx}) as m:
            eq = 1000.0
            share, armed = m.halt_gate_share(m.clip_usd(eq), m.S.stoploss, eq, _R())
            assert armed is want_armed, (book, share, armed)
            assert share is not None
        os.environ.pop(var, None)


def test_the_arming_share_is_unmeasurable_rather_than_guessed():
    with loaded("freqtrade-mum") as m:
        class _R:
            max_daily_loss = None
        for bad in ((None, -0.04, 100.0), (100.0, None, 100.0),
                    (100.0, -0.04, None), (100.0, -0.04, 0.0),
                    (0.0, -0.04, 100.0), (100.0, 0.0, 100.0)):
            share, armed = m.halt_gate_share(bad[0], bad[1], bad[2], _R())
            assert share is None and armed is False, bad


def test_a_second_entry_in_one_cycle_cannot_spend_the_same_room_twice():
    """`equity` is read ONCE per loop, so without a within-cycle accumulator
    every candidate saw the same room and k legs each individually "safe"
    jointly breached it. day-start 220 vs equity 200 leaves $2.00 of room
    against a $1.33 stop per leg: the first leg fits, the second must not."""
    out = _cycle(day_start=220.0)
    assert len(out["venue"].opens) == 1, \
        f"exactly one leg fits in $2.00 of room at $1.33 a stop: {out['venue'].opens}"
    assert out["vetoes"].get("halt_room_skips", 0) >= 1, out["vetoes"]


def test_the_row_publishes_whether_the_gate_is_armed_and_the_geometry():
    out = _cycle(day_start=200.0)
    g = out["vetoes"].get("halt_gate")
    assert isinstance(g, dict), out["vetoes"]
    assert g["armed"] is True and 0 < g["stop_share"] < 0.5, g
    assert g["max_share"] == 0.5


# ---- 15  the halt itself still fires ---------------------------------------

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


# ---- 16-17  the row's `binding` comes from the SAME owner ------------------

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


# ---- 19-23  (xi) the arming is never byte-identical to "the gate never ran" --

def test_a_quiet_cycle_still_publishes_the_arming_from_the_books_own_clip():
    """[(xi), I18] (xg) published `halt_gate: null` whenever no entry candidate
    reached sizing — the normal resting state for a book whose bar is
    `RSI<25 AND NOT uptrend` — so a quiet loop and a gate that never ran were
    the same bytes on a REAL-MONEY row. Observed live on mum minutes after the
    (xg) deploy, which is what motivated this.

    Driven on the RISING tape, where her entry cell cannot fire, with the book
    HEALTHY (room to spare) so a null arming could only ever be "no signal"."""
    with loaded("freqtrade-mum", MUM_GROSS_X="2") as m:
        with _driven(m, tape="breakout") as box:      # rising: her cell can't fire
            box["rails"].max_daily_loss = 57.0
            box["state"][m.STATE_KEY] = _state({}, 200.0)
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]}, once=True)
            pubs = [kw for b, kw in box["published"] if b == ROW]
            assert pubs, "the row must publish"
            vet = pubs[-1]["extra"]["entry_vetoes"]
    assert not box["venue"].opens, "fixture check: this cycle must be QUIET"
    assert vet.get("halt_room_skips", 0) == 0, \
        "fixture check: the book must be HEALTHY, so silence is the signal " \
        "and not a halt shutting entries"
    hg = vet.get("halt_gate")
    assert hg is not None, "a quiet cycle must not publish a null arming"
    assert hg["basis"] == "book_clip", hg
    assert hg["armed"] is True, "mum's geometry arms the gate"
    assert 0.0 < hg["stop_share"] <= hg["max_share"], hg


def test_a_candidate_that_prices_the_gate_wins_over_the_book_clip_fallback():
    """The fallback must never overwrite a real measurement — when an entry
    candidate reached sizing this cycle, the row reports THAT pricing."""
    out = _cycle(day_start=200.0)
    assert out["venue"].opens, "fixture check: this cycle must price a candidate"
    hg = out["vetoes"].get("halt_gate")
    assert hg is not None and hg["basis"] == "candidate", hg


def test_the_fallback_is_the_same_owner_the_entry_site_uses():
    """(hj): a second copy of a rule is a second rule. Both sites must route
    through `halt_gate_stat_for`, so the row can never claim armed while the
    actuator refuses nothing (or the reverse)."""
    import ast
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "halt_gate_stat_for"]
    assert len(calls) == 2, f"expected the entry site + the publish fallback, got {len(calls)}"
    bases = sorted(c.args[-1].value for c in calls)
    assert bases == ["book_clip", "candidate"], bases
    # and nobody hand-rolls the dict beside it
    assert src.count('"max_share": HALT_GATE_MAX_STOP_SHARE') == 1, \
        "the arming dict must be built in exactly one place"


def test_an_unreadable_clip_publishes_a_refusal_not_a_fabricated_arming():
    """`stop_share: null` with `armed: false` says the gate priced itself and
    could not — which must NOT read as armed, and must not be absent either."""
    with loaded("freqtrade-mum") as m:
        for clip in (None, 0.0, -5.0, "junk", float("inf"), float("nan")):
            hg = m.halt_gate_stat_for(clip, -0.04, 600.0, _Rails(57.0), "book_clip")
            assert hg["armed"] is False, clip
            assert hg["stop_share"] is None, clip
            assert hg["basis"] == "book_clip", clip


def test_the_arming_still_fails_open_and_gates_nothing_when_unarmed():
    """Restrict-only: an unarmed or unpriceable gate refuses no entry. avo is
    the live proof — one slot-stop is her whole allowance, so she is NOT armed
    and the rail must be inert on her book."""
    with loaded("freqtrade-avo-maria") as m:
        hg = m.halt_gate_stat_for(230.0, -0.10, 230.0,
                                  _Rails(23.0), "book_clip")
        assert hg["armed"] is False, hg
        assert hg["stop_share"] is not None and hg["stop_share"] > hg["max_share"], hg
