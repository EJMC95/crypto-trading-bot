"""A DAILY-LOSS HALT MUST BE RECONCILABLE WITH THE STOP IT CAN PRE-EMPT.

[2026-09-11 (abg)] `(gv)` established the rule for the 15% drawdown bar and
built `test_stop_vs_gate.py`. The same books carry a SECOND rail that can end a
position and nothing read it against the stop: the daily-loss halt. They are the
same quantity in different units — the halt a DOLLAR allowance on the book, the
stop a PERCENT move on a position — and the gross converts between them.

MEASURED ON 👩 mum, 11-Sep, and it was the whole of her divergence from a twin
that was WINNING the same strategy:

    exit family        LIVE n   LIVE %/t  | TWIN n  TWIN %/t
    roi                    79    +1.416%  |     72   +1.422%
    max_hold               17    -1.369%  |     17   -1.155%
    stop_loss              15    -4.640%  |     12   -4.806%
    daily_loss             20    -1.597%  |      0        --   <-- live only

On the exits the arms SHARE: +0.171%/trade (n=111) against +0.243% (n=106) —
indistinguishable. The halt family alone is -1.451%/trade, t=-5.41, and carries
-0.506pp of the -0.578pp/trade gap between a book at -15% and one at +2.5%.
Neither rail was wrong alone: the $105 cap was 20% of a $525 day-start and the
gross came from a liquidation ceiling. Nobody multiplied them.

WHAT IS PINNED HERE is the ARITHMETIC and the DEGRADATION, never a setting:
mum's 9.5x is Eamon's on-record decision (11-Sep) and is declared in
`audit_halt_vs_stop.HALT_FIRST_OK` with his words, not exempted silently.
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT = ROOT / "lighter_avo_live_bot.py"


class _Rails:
    """Minimal stand-in for SafetyRails: the only field `halt_level` reads."""

    def __init__(self, cap):
        self.max_daily_loss = cap


def _mod(leash=0.20):
    """The module with a STATED daily leash.

    `DAILY_LOSS_LIMIT` defaults to 0.10 and 👩 mum's service sets
    `MUM_DAILY_LOSS=0.20`, so a test that does not say which leash it means
    silently measures a book nobody runs — and the first version of this file
    did exactly that, reading 0.10/9.5 and failing its own calibration pin. The
    leash is part of the geometry under test, so it is an argument."""
    import lighter_avo_live_bot as m
    importlib.reload(m)
    m.DAILY_LOSS_LIMIT = leash
    return m


# --------------------------------------------------------------------------
# THE CALIBRATION PIN. (aat) measured mum's halt firing at a "1.40% basket
# move" at her 11-Sep geometry by an INDEPENDENT route (its own table of
# liquidation points). If `halt_vs_stop` cannot reproduce that number it may
# not be used to reason about her — the (gx) rule: a harness that cannot
# reproduce what DID happen may not say what WOULD have.
# --------------------------------------------------------------------------
def test_the_arithmetic_reproduces_the_independently_measured_number():
    m = _mod()
    out = m.halt_vs_stop(780.57, _Rails(105.0), -0.04, 9.5)
    assert out is not None
    assert out["halt_at_basket_pct"] == pytest.approx(0.0142, abs=5e-4), out
    # (aat) measured 1.40%; anything outside 5bps of it means the two
    # derivations disagree and one of them is wrong.
    assert abs(100 * out["halt_at_basket_pct"] - 1.40) < 0.05, out
    assert out["stop_fires_first"] is False, out


def test_the_binding_rail_is_used_not_the_leash():
    """The defect this closed: the row published `DAILY_LOSS_LIMIT/gross` — the
    PCT leash — while `binding` beside it said "abs". mum's $105 cap has bound
    since 4-Sep, so the published number described a rail that does not fire."""
    m = _mod()
    ds = 780.57
    # abs binds (105 < 20% of 780.57 = 156.11)
    tight = m.halt_vs_stop(ds, _Rails(105.0), -0.04, 9.5)
    assert tight["binding"] == "abs"
    assert tight["allowance_usd"] == pytest.approx(105.0, abs=0.01)
    # a cap LOOSER than the leash must leave the leash binding
    loose = m.halt_vs_stop(ds, _Rails(10_000.0), -0.04, 9.5)
    assert loose["binding"] == "pct"
    assert loose["allowance_usd"] == pytest.approx(ds * m.DAILY_LOSS_LIMIT,
                                                   abs=0.01)
    # and the two must DIFFER — if they did not, this test could not tell a
    # binding-rail read from a leash read, which is the bug it exists for.
    assert tight["halt_at_basket_pct"] < loose["halt_at_basket_pct"]


def test_gross_at_parity_is_the_gross_where_the_rails_agree():
    """Round-trip: feeding `gross_at_parity` back in must put the halt exactly
    at the stop. A parity number that does not round-trip is a number the next
    reader sets a lever from and gets a different answer."""
    m = _mod()
    for ds, cap, stop in ((780.57, 105.0, -0.04), (666.56, 105.0, -0.04),
                          (1000.0, 500.0, -0.10), (230.70, 80.0, -0.10)):
        p = m.halt_vs_stop(ds, _Rails(cap), stop, 9.5)["gross_at_parity"]
        back = m.halt_vs_stop(ds, _Rails(cap), stop, p)
        assert back["halt_at_basket_pct"] == pytest.approx(abs(stop), rel=1e-3)
        assert back["stop_fires_first"] is True


def test_stop_fires_first_flips_at_the_parity_gross():
    m = _mod()
    ds, cap, stop = 666.56, 105.0, -0.04
    p = m.halt_vs_stop(ds, _Rails(cap), stop, 9.5)["gross_at_parity"]
    assert m.halt_vs_stop(ds, _Rails(cap), stop, p * 0.99)["stop_fires_first"]
    assert not m.halt_vs_stop(ds, _Rails(cap), stop,
                              p * 1.01)["stop_fires_first"]


def test_the_measured_fill_basis_is_separate_and_degrades_to_none():
    """The stop's real cost is where it FILLS. An UNMEASURED fill must not read
    as a measured one — `(lv)`/I18's byte-identical trap."""
    m = _mod()
    a = m.halt_vs_stop(666.56, _Rails(105.0), -0.04, 3.75)
    assert a["stop_fill_at_basket_pct"] is None
    assert a["stop_fill_fires_first"] is None
    assert a["stop_fires_first"] is True          # nominal basis still answers
    b = m.halt_vs_stop(666.56, _Rails(105.0), -0.04, 3.75, overshoot_bps=62.4)
    assert b["stop_fill_at_basket_pct"] == pytest.approx(0.04624, abs=1e-5)
    # at 3.75x the halt (4.20%) clears the nominal stop but NOT the measured
    # fill (4.624%) — the two bases genuinely disagree, so both are published.
    assert b["stop_fires_first"] is True
    assert b["stop_fill_fires_first"] is False


@pytest.mark.parametrize("ds,cap,stop,gross", [
    (None, 105.0, -0.04, 9.5),          # dark day-start
    ("x", 105.0, -0.04, 9.5),
    (0.0, 105.0, -0.04, 9.5),
    (-5.0, 105.0, -0.04, 9.5),
    (float("nan"), 105.0, -0.04, 9.5),
    (float("inf"), 105.0, -0.04, 9.5),
    (780.57, 105.0, 0.0, 9.5),          # no stop -> no ordering to state
    (780.57, 105.0, -0.04, 0.0),        # no gross
    (780.57, 105.0, -0.04, None),
    (780.57, 105.0, -0.04, float("nan")),
])
def test_an_unmeasurable_ordering_is_none_never_a_verdict(ds, cap, stop, gross):
    """I1: asserting an ordering from an unknown is the flattering direction.
    The whole dict degrades, so no consumer can read half of one."""
    m = _mod()
    assert m.halt_vs_stop(ds, _Rails(cap), stop, gross) is None


def test_a_non_numeric_cap_cannot_raise_inside_the_publish_path():
    """The `halt_level` hazard: a telemetry field able to take down the loop
    that publishes it. A junk cap degrades to the pct leash, never to a throw
    and never to "no rail"."""
    m = _mod()
    for bad in (None, "abc", object(), float("nan")):
        out = m.halt_vs_stop(780.57, _Rails(bad), -0.04, 9.5)
        assert out is not None and out["binding"] == "pct", bad
        assert out["allowance_usd"] == pytest.approx(
            780.57 * m.DAILY_LOSS_LIMIT, abs=0.01)


# --------------------------------------------------------------------------
# THE ONE OWNER of the overshoot p90. Two inline copies had DIFFERENT n floors.
# --------------------------------------------------------------------------
def test_the_overshoot_p90_has_one_owner_and_the_consumer_read_is_floored():
    m = _mod()
    thin = {"n": 2, "vals": [10.0, 90.0]}
    fat = {"n": 15, "vals": [float(i) for i in range(15)]}
    # the CONSUMER read refuses a thin sample; the published series does not,
    # so that field's history stays byte-identical.
    assert m.overshoot_p90_bps(thin) is None
    assert m.overshoot_p90_bps(thin, floored=False) == 90.0
    assert m.overshoot_p90_bps(fat) == m.overshoot_p90_bps(fat, floored=False)
    # and the cost function must DEFER to it rather than carry a second copy
    assert m._honest_stop_cost(thin) is None
    assert m._honest_stop_cost(fat, gx=1.0, stop=-0.04) is not None
    for junk in (None, {}, {"n": 99, "vals": []}, {"n": 99, "vals": None}):
        assert m.overshoot_p90_bps(junk) is None


def test_no_second_copy_of_the_p90_expression_survives():
    """WHOLE-FILE, not scoped. The first version of this test walked the AST
    per-function and asked "does this function contain 0.9 AND a sorted() call"
    — which is not co-location, so it both false-positived on `main` and
    MISSED a real third copy in `stop_bases`. A whole-file scan for the literal
    index expression found three where the scoped check found two. (po): "prefer
    a whole-file grep to a scoped one, because scoping is where the silence
    hides" — and the miss was inside the guard built to close the class."""
    text = BOT.read_text(encoding="utf-8")
    tree = ast.parse(text)
    # Lines occupied by STRING LITERALS are prose: a docstring may describe the
    # expression (this one's own does). Excluding them by AST rather than by a
    # `"sorted(" in line` filter, which this test tried first and which flagged
    # its own explanatory docstring — a check that cannot tell code from the
    # comment about the code is the (po) shape again, one level up.
    prose = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            prose.update(range(n.lineno, getattr(n, "end_lineno", n.lineno) + 1))
    code = [(i + 1, ln) for i, ln in enumerate(text.splitlines())
            if re.search(r"0\.9\s*\*\s*len", ln) and (i + 1) not in prose]
    assert len(code) == 1, f"{len(code)} live copies of the p90 index: {code}"
    owner_line = code[0][0]
    owner = next(fn.name for fn in ast.walk(tree)
                 if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and fn.lineno <= owner_line <= fn.end_lineno)
    assert owner == "overshoot_p90_bps", owner


def test_every_p90_consumer_defers_to_the_owner():
    """The three former copies, driven: all must move together when the owner
    does. A mutation in the owner has to reach every one of them."""
    m = _mod()
    fat = {"n": 15, "vals": [float(i) for i in range(1, 16)]}
    p90 = m.overshoot_p90_bps(fat)
    assert p90 == 14.0, p90          # sorted[round(.9*15)-1] = [13]
    bases = m.stop_bases(fat, stop=-0.04)
    assert bases["measured_p90"] == pytest.approx(0.04 + 14.0 / 1e4)
    assert m._honest_stop_cost(fat, gx=1.0, stop=-0.04) == pytest.approx(
        0.04 + 14.0 / 1e4, rel=1e-4)
    # and a THIN sample is refused by both consumers, identically
    thin = {"n": 2, "vals": [1.0, 14.0]}
    assert "measured_p90" not in m.stop_bases(thin, stop=-0.04)
    assert m._honest_stop_cost(thin) is None


# --------------------------------------------------------------------------
# `scan.verdicts_basis` — the I1 gap that cost a live diagnosis real time.
# --------------------------------------------------------------------------
def test_the_census_says_whether_the_scan_actually_ran():
    m = _mod()
    kw = dict(rsi_readings={}, rsi_bar=36.0, universe=["A", "B"], held=[],
              ungraded=None, entries_shut=None, last_open_ts=None,
              last_close_ts=None, t_now=0.0)
    assert m.scan_census({}, scanned=True, **kw)["verdicts_basis"] == "this_loop"
    assert m.scan_census({}, scanned=False, **kw)["verdicts_basis"] == "carried"
    # a caller that does not know says NOTHING, rather than either verdict
    assert "verdicts_basis" not in m.scan_census({}, scanned=None, **kw)
    assert "verdicts_basis" not in m.scan_census({}, **kw)


def test_the_publish_closure_reads_no_name_main_binds_after_it_runs():
    """THE BUG THIS TEST WAS WRITTEN FOR WAS MINE, and it was live-real-money
    shaped. The first version of `verdicts_basis` read `entries_ok` out of the
    publish closure. `entries_ok` is assigned ~1,570 lines below the three
    `_publish_row` calls that run before it — two of them the HALT paths, i.e.
    exactly the state a shut book publishes from — so it would have raised
    NameError on a free variable inside the real-money publish path on the
    first loop. Caught by a symtable check, not by reading the code.

    This pins the CLASS: no name `_publish_row` reads out of `main` may be
    first bound later than the earliest `_publish_row` call."""
    tree = ast.parse(BOT.read_text(encoding="utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    pub = next(n for n in ast.walk(main)
               if isinstance(n, ast.FunctionDef) and n.name == "_publish_row")

    reads = {n.id for n in ast.walk(pub)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    local = {n.id for n in ast.walk(pub)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    local |= {a.arg for a in pub.args.args}
    local |= {a.arg for a in pub.args.kwonlyargs}
    free = reads - local

    first = {}
    for n in ast.walk(main):
        if (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                and not (pub.lineno <= n.lineno <= pub.end_lineno)):
            first[n.id] = min(first.get(n.id, n.lineno), n.lineno)
    calls = [n.lineno for n in ast.walk(main)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_publish_row"]
    earliest = min(calls)

    late = sorted(k for k in free if first.get(k, 0) > earliest)
    assert not late, (
        f"_publish_row reads {late} which main binds after line {earliest} — "
        f"NameError on the early/halt publish paths")


# --------------------------------------------------------------------------
# THE GUARD.
# --------------------------------------------------------------------------
def test_the_guard_is_a_ratchet_not_a_bar():
    """(mz)/I23: a guard that reddens on a pre-existing backlog gets exempted
    within a day and then guards nothing. Measured on the live feed the day this
    shipped, BOTH real-money books sit below 1.0 at Eamon's own on-record
    settings (avo 0.83, mum 0.41), so a plain bar would have failed 2 of 2 and
    been switched off. The floors are DECLARED with their numbers; the ratchet
    may only tighten."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_halt_vs_stop as g
    importlib.reload(g)

    def row(bot, ratio, live=True, age=10):
        return {"bot": bot, "live": live, "age_sec": age,
                "extra": {"leverage": {"halt": {"vs_stop": {
                    "halt_at_basket_pct": 0.04 * ratio,
                    "stop_at_basket_pct": 0.04,
                    "stop_fires_first": ratio >= 1.0,
                    "gross_at_parity": 3.36}}}}}

    # an UNDECLARED book is held to 1.0 — a NEW instance fails at once
    assert [f[0] for f in g.findings([row("new", 0.99)], ratchet={})] == ["new"]
    assert g.findings([row("new", 1.00)], ratchet={}) == []
    # a DECLARED floor holds only down to itself
    rat = {"x": (0.40, "Eamon, 11-Sep-2026: a dated reason long enough to pass")}
    assert g.findings([row("x", 0.40)], ratchet=rat) == []
    out = g.findings([row("x", 0.39)], ratchet=rat)
    assert [f[0] for f in out] == ["x"] and out[0][4] == 0.39 and out[0][5] == 0.40
    # a floor never silences another book
    assert [f[0] for f in g.findings([row("y", 0.50)], ratchet=rat)] == ["y"]
    # paper is out of scope; a stale row says nothing (I1)
    assert g.findings([row("x", 0.01, live=False)], ratchet={}) == []
    assert g.findings([row("x", 0.01, age=99999)], ratchet={}) == []


def test_both_live_books_have_a_declared_floor_with_a_dated_reason():
    """The baseline is recorded, not hidden. mum's is Eamon's on-record 9.5x;
    avo's is pre-existing and DECLARED rather than fixed in this pass (SHIP
    NARROW). An undeclared live book fails at 1.0, which is the point."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_halt_vs_stop as g
    importlib.reload(g)
    for bot in ("freqtrade-mum-lighter", "freqtrade-avo-maria-lighter"):
        assert bot in g.RATCHET, bot
        floor, why = g.RATCHET[bot]
        assert 0.0 < floor <= 1.0, (bot, floor)
        assert "2026" in why and len(why) > 20, (bot, why)
    # a floor of 0 would silence any regression, so mum's must stay off the deck
    assert g.RATCHET["freqtrade-mum-lighter"][0] >= 0.30


def test_a_blanket_exemption_is_still_available_but_unused():
    """A declared FLOOR is strictly more informative than a blanket exemption,
    so `HALT_FIRST_OK` stays empty — kept only for a book that must be silent
    entirely."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_halt_vs_stop as g
    importlib.reload(g)
    assert g.HALT_FIRST_OK == {}


def test_the_guard_refuses_a_dark_feed_rather_than_passing_it():
    """(jc): a dark feed exits non-zero, never a vacuous green."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_halt_vs_stop as g
    importlib.reload(g)
    assert g.main(["--pnl-json", "file:///nonexistent/none.json"]) == 2


def test_the_guard_selftest_passes():
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_halt_vs_stop as g
    importlib.reload(g)
    assert g.main(["--selftest"]) == 0


# --------------------------------------------------------------------------
# THE POLICY-DRIFT FIELDS. `DAILY_LOSS_LIMIT` states the leash as a fraction and
# the abs cap states it as a fixed dollar, so they diverge the moment equity
# moves — and `halt_level` takes the tighter, which is the stale one on a book
# that has grown. mum's $105 was 20% of a $525 day-start and is 15.8% today.
# --------------------------------------------------------------------------
def test_the_two_daily_rails_report_whether_they_still_agree():
    m = _mod(leash=0.20)
    # at the equity the cap was DERIVED from, they agree
    at_origin = m.halt_vs_stop(525.0, _Rails(105.0), -0.04, 9.5)
    assert at_origin["abs_pct_of_day_start"] == pytest.approx(0.20, abs=1e-4)
    assert at_origin["rails_agree"] is True
    # at today's book they do NOT — 15.8% against a stated 20%
    today = m.halt_vs_stop(666.56, _Rails(105.0), -0.04, 9.5)
    assert today["abs_pct_of_day_start"] == pytest.approx(0.1575, abs=1e-3)
    assert today["rails_agree"] is False
    # and the drift is what makes the abs rail the binding one
    assert today["binding"] == "abs"


def test_an_unreadable_cap_never_reads_as_agreement():
    """I1's flattering direction: an unknown must not publish as a green."""
    m = _mod(leash=0.20)
    for bad in (None, "abc", float("nan"), float("inf")):
        out = m.halt_vs_stop(666.56, _Rails(bad), -0.04, 9.5)
        assert out["rails_agree"] is None, bad
        assert out["abs_pct_of_day_start"] is None, bad
        # ...and the leash still governs, so the book is never left unrailed
        assert out["binding"] == "pct", bad
    # A BOOL IS A DECLARED DIVERGENCE, not an oversight. `_rails_agree` rejects
    # it (a bool is not a cap) while `halt_level` — the OWNER of which rail
    # binds, and senior here — reads `float(True)` as a $1 cap and lets it bind.
    # Unreachable from `LIGHTER_MAX_DAILY_LOSS`, which is `float(os.environ...)`,
    # so the owner is NOT changed for a case production cannot produce: a live
    # real-money rail is not edited to satisfy a test's imagination. Pinned so
    # the divergence is deliberate rather than discovered.
    out = m.halt_vs_stop(666.56, _Rails(True), -0.04, 9.5)
    assert out["rails_agree"] is None
    assert out["binding"] == "abs"          # the owner's reading, unchanged


def test_the_drift_fields_are_reported_and_nothing_reads_them():
    """AST: `rails_agree` / `abs_pct_of_day_start` are telemetry. If a gate ever
    consumes one, a value decision that is Eamon's has become automatic."""
    tree = ast.parse(BOT.read_text(encoding="utf-8"))
    owner = next(fn for fn in ast.walk(tree)
                 if isinstance(fn, ast.FunctionDef) and fn.name == "halt_vs_stop")
    lits = {"rails_agree", "abs_pct_of_day_start"}
    readers = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and n.slice.value in lits:
            readers.add(n.lineno)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and n.args[0].value in lits:
            readers.add(n.lineno)
    outside = {ln for ln in readers
               if not (owner.lineno <= ln <= owner.end_lineno)}
    assert not outside, f"a consumer reads the drift fields at {sorted(outside)}"
