"""[2026-08-27 (vn)] 🎫 THE TAKER'S SLOT CAP 6 -> 8, AND THE CLIP PAIRING THAT
MAKES IT LEGAL.

Eamon: *"take it to 8"*. `(uo)`'s `slot_census` had shown `{offered: 4,
slots_full: 4, lens_once: 0}` — four tickets a loop refused purely on the
position cap, the per-lens throttle NOT binding — but one loop is n=1. Driven
through `lighter_ticket_replay` over the same 2,388-snapshot bus tape, the
taker's REAL code, both arms identical but for the cap:

    6 slots -> 75 closes, net +$1.85, $0.025/trade
    8 slots -> 99 closes, net +$6.76, $0.068/trade

More closes AND a better mean, so it is not `(hl)`'s denominator shrinkage.

WHAT THIS FILE PINS, and the second one is the load-bearing half: the cap is
where the measurement put it, and **the clip ceiling can never let the cap
breach the funding bar** — at 8 slots the old $95 gives $1,520 against a
$1,200 bar, so shipping the cap alone would have reddened
`test_brain_live_sizing_safety` and, worse, sized the book beyond what it
could fund with fill terms calibrated at the designed clip.
"""
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _mods():
    return (importlib.import_module("lighter_ticket_taker"),
            importlib.import_module("fleet_bus"))


def test_the_cap_is_where_the_replay_put_it():
    m, _ = _mods()
    assert m.MAX_OPEN == 8, (
        f"TT_MAX_OPEN is {m.MAX_OPEN}, not 8 — Eamon's call 27-Aug, and the "
        "replay measured +32% closes with a better mean at 8")


def test_the_worst_case_gross_stays_inside_the_funding_bar():
    """THE PAIRING. Not a style preference — the bar exists because fill and
    slippage terms calibrated at the designed clip become fiction above what
    the book could fund. Imported from the same owner the sizing-safety guard
    uses, never retyped."""
    m, fb = _mods()
    eq = float(getattr(m, "START_EQUITY", 1000.0))
    gross = m.CLIP_MAX * fb.BRAIN_GROSS_X * m.MAX_OPEN
    assert gross < 1.2 * eq, (
        f"worst-case gross ${gross:,.0f} breaches the ${1.2 * eq:,.0f} bar at "
        f"CLIP_MAX={m.CLIP_MAX} x BRAIN_GROSS_X={fb.BRAIN_GROSS_X} x "
        f"MAX_OPEN={m.MAX_OPEN}")


def test_the_pairing_holds_across_the_whole_reachable_cap_range():
    """The property, not today's two numbers: for ANY cap an operator can set
    via TT_MAX_OPEN within the sane range, the shipped ceiling must keep the
    book inside the bar. This is what fails the day someone raises the cap
    again and forgets the clip — the exact mistake this entry nearly made."""
    m, fb = _mods()
    eq = float(getattr(m, "START_EQUITY", 1000.0))
    worst = m.CLIP_MAX * fb.BRAIN_GROSS_X * m.MAX_OPEN
    assert worst < 1.2 * eq
    # and the ceiling must be the largest that is STRICTLY inside, within $5 —
    # a needlessly small clip throws away size the book is allowed to use.
    head = (1.2 * eq) / (fb.BRAIN_GROSS_X * m.MAX_OPEN) - m.CLIP_MAX
    assert 0 < head <= 10.0, (
        f"CLIP_MAX={m.CLIP_MAX} leaves ${head:.1f} of unused ceiling at "
        f"{m.MAX_OPEN} slots — either it breaches the bar or it is leaving "
        "size on the table for no reason")


def test_the_clip_ceiling_almost_never_binds_at_the_books_real_size():
    """WHY CUTTING THE CEILING IS CHEAP, stated as a test so a future session
    does not read 95 -> 70 as a restriction being smuggled in. The book's
    sizing is constant-RISK: clip = RISK_USD / adverse, bounded [CLIP_MIN,
    CLIP_MAX]. Its measured median deployed clip is ~$21 ((td)), so the
    ceiling binds only on the calmest books, and per-trade % is invariant to
    clip anyway ((hl))."""
    m, _ = _mods()
    assert m.CLIP_MIN < 21.0 < m.CLIP_MAX, (
        "the book's measured median deployed clip (~$21) must sit strictly "
        f"inside [{m.CLIP_MIN}, {m.CLIP_MAX}] — if the ceiling has fallen to "
        "or below it, this stopped being a free change")


def test_the_slot_census_still_reports_what_the_cap_refuses():
    """The instrument that justified the raise must survive it — otherwise the
    NEXT cap question is unanswerable for the same reason this one was."""
    src = (ROOT / "lighter_ticket_taker.py").read_text()
    for field in ("slot_census", "slots_full", "offered", "lens_once"):
        assert field in src, (
            f"{field!r} is gone from the taker — `open 8/8` is byte-identical "
            "between a full book and a starved one, which is the whole reason "
            "(uo) built the census")
