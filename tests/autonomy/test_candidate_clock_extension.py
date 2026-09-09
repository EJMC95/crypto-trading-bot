"""[(zn)] A CANDIDATE THAT NARROWS ITS OWN ARM NOW GETS THE CLOCK ITS OWN RATE
SAYS IT NEEDS — BOUNDED, RE-DERIVED EVERY CYCLE, AND NEVER ON A HUNCH.

Eamon, 9-Sep: *"extend max_days for gate-narrowing candidates."* The (zl)
measurement behind the decision, taken on the running candidate
`mum-vel-12-20` with the LIVE arm as the control that feels the same tide:

    SHADOW (velocity band ON)   7.52 opens/day before -> 1.84   (0.245)
    LIVE   (control, no band)   7.76 opens/day before -> 3.68   (0.474)

At its own rate the shadow arm needed **16.3d for its 30-close floor against a
14-day clock**, so the candidate would have run out of clock before it could be
judged either way. Three of mum's four queued candidates change their own
arm's close rate; on a fixed clock, "be more selective" was a class this judge
structurally could not grade.

THE SHAPE, and why this one: the clock is extended **to exactly the day the
candidate's own projection names**, never to the ceiling, and it is
**re-derived every cycle** from the growing sample — so it self-corrects in
both directions and needs no margin. No "gate-narrowing" label is detected:
the actuator does not need the cause, a hand-typed label is the retyped
constant that drifts, and incubator-proposed candidates would arrive without
one. The ceiling `MAX_DAYS_EXTENDED` is 2x the base clock — one extra clock —
and it is env-tunable.

FAIL-CLOSED TOWARD THE BASE CLOCK. An extension is a COST to a serial, scarce
lane, so absence of evidence never buys one: no horizon, an unreadable one, a
thin arm, a dead arm, floors already met, or a need past the ceiling all leave
the clock at MAX_DAYS. A candidate that cannot make it even with the extra
clock expires UNDERPOWERED (not a refutation) and comes back after
DONE_RETRY_D.

NOT TOUCHED: the paired bar, the floors, the margin, the live arm, and the
sole-writer rule on `live.*`. More clock changes how long a candidate may TRY
to reach the evidence; it never changes what counts as evidence.
"""
import ast
import os
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import experiment_judge as ej          # noqa: E402


def _ev(n_shadow, n_live, days):
    ev = {"promote": False, "n_shadow": n_shadow, "n_live": n_live,
          "why": f"floors: shadow {n_shadow}/30, live {n_live}/10"}
    ev["horizon"] = ej.sample_horizon(ev, days)
    return ev


# ------------------------------------------------------- THE MEASURED CASE

def test_the_live_candidate_is_extended_to_its_own_projection():
    """The entry's own numbers: 3 shadow / 8 live closes in 1.63d projects the
    30-close floor at 16.3d. The clock becomes 16.3d — not 28."""
    eff, ext = ej.effective_max_days(_ev(3, 8, 1.631))
    assert eff == 16.3
    assert ext["from"] == 14.0 and ext["to"] == 16.3 and ext["ceiling"] == 28.0
    assert ext["binding"] == "shadow"


def test_the_extension_is_re_derived_every_cycle_and_self_corrects():
    """Day 14 with 26 closes -> 16.2d. Day 15 with 29 closes -> 15.5d (the rate
    improved, the extension shrank). Then the rate collapses: day 15 with only
    16 closes projects 28.1d, past the ceiling, and the extension is
    WITHDRAWN — the candidate expires on the base clock rather than holding
    the lane for a sample that will not arrive."""
    assert ej.effective_max_days(_ev(26, 68, 14.0))[0] == 16.2
    assert ej.effective_max_days(_ev(29, 73, 15.0))[0] == 15.5
    eff, ext = ej.effective_max_days(_ev(16, 60, 15.0))
    assert eff == 14.0 and ext is None


def test_extends_to_the_need_never_to_the_ceiling():
    """A clock extended to the ceiling would hand every slow candidate the
    same 28 days regardless of what it needs. The extension is the
    projection, to the tenth of a day."""
    for n, days, want in ((3, 1.631, 16.3), (10, 6.0, 18.0), (20, 15.0, 22.5)):
        eff, ext = ej.effective_max_days(_ev(n, 40, days))
        assert eff == want, (n, days, eff)
        assert ext["to"] == want and eff < ej.MAX_DAYS_EXTENDED


def test_a_need_past_the_ceiling_is_not_fed_more_lane():
    """5 closes in 6 days projects 36d. That candidate will not be judged on
    any clock this lane can afford; it expires at 14 as UNDERPOWERED and
    returns after DONE_RETRY_D."""
    ev = _ev(5, 40, 6.0)
    assert ev["horizon"]["days_req_total"] == 36.0
    assert ev["horizon"]["reachable_extended"] is False
    assert ej.effective_max_days(ev) == (14.0, None)


def test_exactly_at_the_base_clock_is_not_an_extension():
    """need == MAX_DAYS means the base clock already suffices."""
    ev = _ev(30, 40, 14.0)            # 30 closes in 14d: met, and need = 0
    assert ej.effective_max_days(ev) == (14.0, None)
    ev = _ev(15, 40, 7.0)             # 15 in 7d -> need exactly 14.0
    assert ev["horizon"]["days_req_total"] == 14.0
    assert ej.effective_max_days(ev) == (14.0, None)


def test_floors_met_returns_the_base_clock_so_the_bar_decides():
    """Once the sample exists the clock's job is over; whether the candidate
    clears is the paired bar's question, and an expiry past the base clock
    with floors met is a RESULT (ABANDONED), exactly as before."""
    ev = _ev(30, 78, 16.2)
    assert ev["horizon"]["met"] is True
    assert ej.effective_max_days(ev) == (14.0, None)
    assert ej.expiry_verdict(ev)[0] == "ABANDONED"


# ------------------------------------------------------------ FAIL-CLOSED

@pytest.mark.parametrize("ev,why", [
    ({}, "no horizon"),
    ({"horizon": None}, "horizon None"),
    ({"horizon": "nope"}, "horizon not a dict"),
    ({"horizon": {}}, "horizon with nothing in it"),
    ({"horizon": {"days_req_total": None}}, "unprojectable (thin arm)"),
    ({"horizon": {"days_req_total": True}}, "bool need"),
    ({"horizon": {"days_req_total": "16"}}, "string need"),
    ({"horizon": {"days_req_total": float("nan")}}, "NaN need"),
    ({"horizon": {"days_req_total": float("inf")}}, "infinite need"),
    ({"horizon": {"days_req_total": 16.3, "met": True}}, "met beats need"),
    (None, "ev None"),
    ("nope", "ev not a dict"),
])
def test_any_doubt_leaves_the_base_clock_never_an_extension(ev, why):
    """An extension is lane time spent; nothing unmeasured may spend it."""
    assert ej.effective_max_days(ev) == (14.0, None), why


def test_a_bool_need_is_refused_where_it_would_otherwise_extend():
    """`True` is an int in Python and would read as a 1.0-day need. At the
    default clocks that collapses harmlessly into "inside the base clock", so
    the guard is unobservable there — the mutation round proved it (M8, an
    equivalent mutant at 14/28). Driven at explicit clocks where 1.0 WOULD
    fall in the extension band, so the guard is reachable and pinned."""
    ev = {"horizon": {"days_req_total": True, "binding": "shadow"}}
    assert ej.effective_max_days(ev, max_days=0.5, max_days_extended=2.0) == (0.5, None)
    # and a REAL 1.0 at the same clocks does extend — the control for the guard
    ev = {"horizon": {"days_req_total": 1.0, "binding": "shadow"}}
    assert ej.effective_max_days(ev, max_days=0.5, max_days_extended=2.0)[0] == 1.0


def test_a_dead_arm_is_not_extended():
    """Zero shadow closes in 6 days: the horizon says reachable False with no
    number, and no number means no extension."""
    ev = _ev(0, 40, 6.0)
    assert ev["horizon"]["reachable"] is False
    assert ev["horizon"]["days_req_total"] is None
    assert ej.effective_max_days(ev) == (14.0, None)


def test_it_actually_extends():
    """The mirror of every fail-closed case: an owner that always returned the
    base clock passes all of them and extends nothing, forever (I3)."""
    eff, ext = ej.effective_max_days(_ev(10, 40, 6.0))
    assert eff == 18.0 and ext is not None and ext["to"] == 18.0


# ----------------------------------------------------- THE PUBLISHED READ

def test_the_horizon_publishes_both_clocks_so_the_payload_is_one_story():
    """`reachable` keeps its (zl) meaning (inside the base clock);
    `reachable_extended` is the reading against the clock a starving
    candidate can actually be given. 16.3d reads False / True."""
    h = ej.sample_horizon({"n_shadow": 3, "n_live": 8}, 1.631)
    assert h["reachable"] is False and h["reachable_extended"] is True
    assert h["max_days"] == 14.0 and h["max_days_extended"] == 28.0
    assert "extendable to 28d" in h["why"]


def test_the_ceiling_is_one_extra_clock_and_the_base_clock_did_not_move():
    assert ej.MAX_DAYS == 14.0
    assert ej.MAX_DAYS_EXTENDED == 28.0 == 2 * ej.MAX_DAYS


# ------------------------------------------------------------- THE WIRING

def _run_once():
    mod = ast.parse(pathlib.Path(ej.__file__).read_text())
    return next(n for n in ast.walk(mod)
                if isinstance(n, ast.FunctionDef) and n.name == "run_once")


def _expiry_if(fn):
    """The `if` whose body appends the expiry verdict via `expiry_verdict`."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        calls = {c.func.id for c in ast.walk(node)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        if "expiry_verdict" in calls and not any(
                isinstance(inner, ast.If) and inner is not node
                and "expiry_verdict" in {
                    c.func.id for c in ast.walk(inner)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
                for inner in ast.walk(node)):
            return node
    return None


def test_the_expiry_compares_against_the_owner_never_against_max_days():
    """THE CLASS-CLOSER. The defect was `if days >= MAX_DAYS:` — a fixed clock.
    The compare must read the value `effective_max_days` returned. Asserted on
    the AST of the branch, so prose cannot satisfy it."""
    node = _expiry_if(_run_once())
    assert node is not None, "no expiry branch calls expiry_verdict"
    t = node.test
    assert isinstance(t, ast.Compare) and isinstance(t.ops[0], ast.GtE)
    assert isinstance(t.left, ast.Name) and t.left.id == "days"
    rhs = t.comparators[0]
    assert isinstance(rhs, ast.Name) and rhs.id == "_eff_max", (
        "the expiry compares against something other than the owner's value — "
        "a fixed MAX_DAYS here is the (zl) starvation reinstated")


def test_the_clock_is_derived_and_published_in_the_same_block_before_the_compare():
    """The owner is called, and `ev["clock"]` assigned, as sibling statements
    IMMEDIATELY before the expiry `if` — not somewhere else, and not behind a
    guard. That is what makes the extension re-derived every cycle and the
    reason a candidate is still running past 14d readable on the payload."""
    fn = _run_once()
    target = _expiry_if(fn)
    parent_body = None
    for node in ast.walk(fn):
        for field in ("body", "orelse"):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list) and any(s is target for s in stmts):
                parent_body = stmts
    assert parent_body is not None
    idx = next(i for i, s in enumerate(parent_body) if s is target)
    before = parent_body[max(0, idx - 2):idx]
    assert len(before) == 2, "the two statements before the compare are missing"
    owner_call, clock_pub = before
    assert (isinstance(owner_call, ast.Assign)
            and isinstance(owner_call.value, ast.Call)
            and isinstance(owner_call.value.func, ast.Name)
            and owner_call.value.func.id == "effective_max_days"), ast.dump(owner_call)
    assert isinstance(clock_pub, ast.Assign)
    tgt = clock_pub.targets[0]
    assert (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name)
            and tgt.value.id == "ev" and isinstance(tgt.slice, ast.Constant)
            and tgt.slice.value == "clock"), ast.dump(clock_pub)


def test_no_bar_no_floor_no_live_lever_moved():
    """More clock, not more permission. The owner writes nothing and names no
    live prefix; the paired bar's floors and margin are byte-unchanged."""
    assert (ej.MIN_DAYS, ej.MIN_CLOSES, ej.LIVE_MIN_CLOSES, ej.MARGIN_PP) == (7.0, 30, 10, 0.5)
    mod = ast.parse(pathlib.Path(ej.__file__).read_text())
    fn = next(n for n in ast.walk(mod)
              if isinstance(n, ast.FunctionDef) and n.name == "effective_max_days")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert not calls & {"_assert_levers", "write_levers", "save", "send_push"}
    strings = {c.value for c in ast.walk(fn)
               if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert not any(s.startswith("live.") for s in strings)
