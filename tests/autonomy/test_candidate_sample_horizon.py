"""[(zl)] `ABANDONED` MEANT BOTH "WE MEASURED IT AND IT LOST" AND "WE NEVER GOT
ENOUGH CLOSES TO ASK" — on the fleet's ONLY designed path to more real money.

Measured 2026-09-09 on the running candidate `mum-vel-12-20`, 39h in, with the
LIVE arm as the control that feels the same tide (I25):

    SHADOW (velocity band ON)   7.52 opens/day before -> 1.84 after   (0.245)
    LIVE   (control, no band)   7.76 opens/day before -> 3.68 after   (0.474)

The tape halved both arms; the band halved the shadow AGAIN (0.245/0.474 =
0.52). Two consequences, and this file pins both:

  * THE PROJECTION WAS COMPUTED ON THE WRONG RATE. `_eta_judgeable` sizes its
    terms from `_pair_power`'s trailing 14 DAYS — the rate the arm ran BEFORE
    the candidate narrowed its gate — and published `binding: window` at 7.0d
    with a `shadow_closes` term of 4.4d. On the candidate's own rate the
    shadow arm needs **16.3d**, and `MAX_DAYS` is **14**. The pair's ETA is
    not wrong for a pair; it is wrong for a CANDIDATE, because a gate-narrowing
    candidate changes the very quantity the projection is built from.
  * THE VERDICT COULD NOT TELL THE TWO APART. At `days >= MAX_DAYS` the judge
    appended `ABANDONED` whatever the reason and pushed "14d without clearing
    the bar", which reads as a refutation of the idea. It is the I17/(tz) split
    one level up: `unreachable` had to be separated from `underpowered` for
    BOOKS because a thin sample is not an exclusion — and a candidate that
    starves its own arm is exactly that shape.

NOT AN EDGE CASE — THE QUEUE'S NORMAL CASE. Three of mum's four candidates
change their own arm's close rate: `vel-12-20` and `rsi-32` narrow the entry
gate (at `rsi_max` 32.0 the shadow's live scan of 102 coins has `rsi_min` 33.3,
i.e. it admits NOTHING today), `hold-2880` halves turnover. Only `hold-720`
speeds it up.

WHAT THIS DOES NOT DO, deliberately: it moves no bar and no control flow. An
expired candidate still stands down, still cools down, still enters `done` —
the lane is SERIAL and scarce, and a candidate that loops would be worse than
one that is mislabelled. `MAX_DAYS` was untouched HERE: extending the clock
for starving candidates is a policy act on the promotion path, and Eamon made
it the same day — see (zn) / `test_candidate_clock_extension.py`.
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


def _ev(n_shadow, n_live, **kw):
    d = {"promote": False, "n_shadow": n_shadow, "n_live": n_live,
         "why": f"floors: shadow {n_shadow}/30, live {n_live}/10"}
    d.update(kw)
    return d


# ------------------------------------------------------- THE MEASURED CASE

def test_the_live_candidate_is_projected_unreachable_on_its_own_rate():
    """The entry's own numbers, driven through the shipped function: 3 shadow
    and 8 live closes in 1.63 days needs 16.3d for the 30-close floor, against
    a 14-day clock."""
    h = ej.sample_horizon(_ev(3, 8), 1.631)
    assert h["rate"]["shadow"] == 1.84
    assert h["days_req"]["shadow"] == 16.3
    assert h["binding"] == "shadow"
    assert h["reachable"] is False
    assert h["verdict_if_expired"] == "UNDERPOWERED"


def test_the_rate_is_the_candidates_own_not_the_arms_trailing_one():
    """THE CLASS. Same close counts, different elapsed time -> a different
    horizon. A projection reading a trailing window would be invariant to
    this, which is exactly how the pair ETA said 4.4d while the candidate
    needed 16.3d."""
    fast = ej.sample_horizon(_ev(10, 10), 1.0)["days_req"]["shadow"]
    slow = ej.sample_horizon(_ev(10, 10), 4.0)["days_req"]["shadow"]
    assert fast == 3.0 and slow == 12.0, (fast, slow)


# --------------------------------------------------------- THE TWO VERDICTS

def test_floors_met_is_a_result_and_keeps_the_name_abandoned():
    ev = _ev(30, 10)
    ev["horizon"] = ej.sample_horizon(ev, 14.0)
    assert ev["horizon"]["met"] is True
    name, why = ej.expiry_verdict(ev)
    assert name == "ABANDONED" and "clearing the bar" in why


def test_floors_unmet_is_not_a_result_and_says_so():
    ev = _ev(3, 8)
    ev["horizon"] = ej.sample_horizon(ev, 14.0)
    assert ev["horizon"]["met"] is False
    name, why = ej.expiry_verdict(ev)
    assert name == "UNDERPOWERED"
    assert "NOT a refutation" in why and "nothing was measured" in why


def test_one_arm_short_is_still_underpowered():
    """The live floor is 10 and the shadow floor 30; either one unmet means
    the paired bar was never askable."""
    for n_sh, n_lv in ((30, 9), (29, 10), (0, 40)):
        ev = _ev(n_sh, n_lv)
        ev["horizon"] = ej.sample_horizon(ev, 14.0)
        assert ej.expiry_verdict(ev)[0] == "UNDERPOWERED", (n_sh, n_lv)


@pytest.mark.parametrize("ev,why", [
    ({}, "no horizon attached"),
    ({"horizon": None}, "horizon is None"),
    ({"horizon": "nope"}, "horizon is not a dict"),
    ({"horizon": {}}, "horizon has no verdict"),
    ({"horizon": {"met": None}}, "met is None"),
    (None, "ev is None"),
    ("nope", "ev is not a dict"),
])
def test_an_unreadable_horizon_never_fabricates_a_refutation(ev, why):
    """FAIL-CLOSED, and the direction is the whole safety of the split.
    Under-claiming a real negative costs nothing — the candidate stands down
    and enters `done` either way. Over-claiming one retires an idea on a
    verdict about a sample nobody took."""
    assert ej.expiry_verdict(ev)[0] == "UNDERPOWERED", why


# ------------------------------------------------------------ FAIL-CLOSED

@pytest.mark.parametrize("ev,days,why", [
    ("not-a-dict", 3.0,          "ev is not a dict"),
    (None, 3.0,                  "ev is None"),
    (_ev(5, 5), 0,               "zero elapsed"),
    (_ev(5, 5), -1.0,            "negative elapsed"),
    (_ev(5, 5), float("nan"),    "elapsed is NaN"),
    (_ev(5, 5), float("inf"),    "elapsed is infinite"),
    (_ev(5, 5), "soon",          "elapsed is not a number"),
    (_ev(5, 5), None,            "elapsed is None"),
])
def test_any_doubt_publishes_nothing(ev, days, why):
    assert ej.sample_horizon(ev, days) is None, why


def test_a_thin_arm_is_unprojectable_never_optimistic_and_never_a_refusal():
    """One close in six hours extrapolates to 4/day. Below `HORIZON_MIN_N` the
    honest answer is that the horizon cannot be sized — `reachable: None`, not
    `False`, because a thin sample is not an exclusion (I17-as-amended)."""
    h = ej.sample_horizon(_ev(1, 8), 0.25)
    assert h["days_req"]["shadow"] is None
    assert h["reachable"] is None
    assert h["binding"] == "shadow"
    assert "UNPROJECTABLE" in h["why"]


def test_zero_closes_is_the_one_case_that_is_decidable_downward():
    """A rate of zero reaches no floor at any horizon — that is an answer, not
    a thin sample, and it is the state `mum-rsi-32` would sit in (its bar
    admits nothing on the current tape)."""
    h = ej.sample_horizon(_ev(0, 12), 6.0)
    assert h["reachable"] is False
    assert h["days_req"]["shadow"] is None
    assert "closed NOTHING" in h["why"]


def test_a_bool_count_is_refused_like_any_other_junk():
    """`True` is an int in Python and would size a rate of 1/day."""
    h = ej.sample_horizon(_ev(True, 8), 2.0)
    assert h["have"]["shadow"] is None
    assert h["reachable"] is None


def test_it_actually_computes_on_a_real_sample():
    """The mirror of every fail-closed case above: a function that always
    returned None would satisfy all of them and project nothing, forever (I3)."""
    h = ej.sample_horizon(_ev(15, 12), 5.0)
    assert h is not None and h["days_req_total"] == 10.0
    assert h["reachable"] is True and h["binding"] == "shadow"
    assert h["days_req"]["live"] == 0.0      # live floor already met


# ------------------------------------------------------------- THE WIRING

def test_the_running_phase_attaches_the_horizon_every_cycle():
    """Not only at expiry — the point is to see a starving candidate while it
    still has days left to run.

    ASSERTED ON REACHABILITY, not on the presence of the line. The first
    version of this test was a substring scan and the mutation round walked
    straight through it: `if False: ev["horizon"] = _hz` leaves both strings
    in the file and every character of the attach intact, while the attach
    never runs. That is this repo's own rule — a page-wide substring scan is
    not a structural claim — and it is the same vacuous-guard shape (zk)
    recorded two entries ago. So: find the assignment inside `run_once`, and
    require its guard to be a comparison of the computed value against None."""
    mod = ast.parse(pathlib.Path(ej.__file__).read_text())
    fn = next(n for n in ast.walk(mod)
              if isinstance(n, ast.FunctionDef) and n.name == "run_once")

    def _attaches(node):
        # DIRECT body only. `ast.walk` would also match every ENCLOSING `if`
        # (`if phase == "running":` and friends), and the innermost guard is
        # the one that decides whether the attach runs.
        for a in node.body:
            if not isinstance(a, ast.Assign):
                continue
            for t in a.targets:
                if (isinstance(t, ast.Subscript)
                        and isinstance(t.value, ast.Name) and t.value.id == "ev"
                        and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "horizon"):
                    return True
        return False

    guards = [n for n in ast.walk(fn) if isinstance(n, ast.If) and _attaches(n)]
    assert guards, "nothing in run_once attaches ev['horizon']"
    for g in guards:
        assert isinstance(g.test, ast.Compare), (
            "the horizon attach is guarded by something that is not a value "
            "check — an `if False:` keeps the line and kills the behaviour")
        assert isinstance(g.test.ops[0], (ast.Is, ast.IsNot)), g.test.ops
        assert isinstance(g.test.left, ast.Name) and g.test.left.id == "_hz"
        assert (isinstance(g.test.comparators[0], ast.Constant)
                and g.test.comparators[0].value is None)
    # and the value it guards is computed from the candidate's OWN elapsed days
    src = pathlib.Path(ej.__file__).read_text()
    assert "_hz = sample_horizon(ev, days)" in src


def test_the_expiry_branch_reads_the_owner_and_never_hardcodes_a_name():
    """THE CLASS-CLOSER. The defect was a literal `"ABANDONED"` in the branch;
    a later edit that reintroduces one silently restores it. Asserted on the
    AST of the enclosing function, so prose cannot satisfy it."""
    mod = ast.parse(pathlib.Path(ej.__file__).read_text())
    fn = next(n for n in ast.walk(mod)
              if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "expiry_verdict" in calls, "run_once no longer reads the one owner"
    # and the verdict appended at expiry is the OWNER's value, not a literal
    for node in ast.walk(fn):
        if (isinstance(node, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "verdict"
                        for k in node.keys)):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "verdict":
                    assert not (isinstance(v, ast.Constant)
                                and v.value == "ABANDONED"), (
                        "the expiry verdict is a hard-coded ABANDONED again — "
                        "a never-sampled candidate is recorded as refuted")


def test_no_bar_and_no_control_flow_moved():
    """A candidate that expires must still stand down, cool down and enter
    `done`: the lane is SERIAL, and a looping candidate is worse than a
    mislabelled one.

    [CORRECTED IN PLACE per I12 at (zn).] This read "MAX_DAYS itself is
    untouched — extending it is a policy act with its own price", and pinned
    the literal `if days >= MAX_DAYS:`. Eamon took that policy act the same
    day, so the expiry now compares against `effective_max_days`' value; the
    base clock is still 14 and the control flow at expiry is still the same
    three acts. `test_candidate_clock_extension.py` owns the extension."""
    assert ej.MAX_DAYS == 14.0
    assert ej.MIN_CLOSES == 30 and ej.LIVE_MIN_CLOSES == 10
    src = pathlib.Path(ej.__file__).read_text()
    branch = src.split("if days >= _eff_max:")[1].split("return save(")[1][:400]
    for keep in ('phase="idle"', "done=done + [cand", "cooldown_until=now"):
        assert keep in branch, f"the expiry branch stopped doing {keep!r}"
