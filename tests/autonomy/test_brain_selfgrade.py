"""[2026-09-07 (ze)] Pins for `brain_stats.selfgrade_mult` — the brain's
retrospective grade of its OWN stake multiplier.

The value of this organ is entirely in what it REFUSES to conclude, so every
pin here is a way the grade could be fake:

  * graded in DOLLARS, where a 2x multiplier doubles the metric by
    construction and every multiplier "works" (I7 at the actuator);
  * graded against the window that MOTIVATED the multiplier rather than a
    control arm (I25);
  * graded on trades instead of open-days, where one burst reads as evidence
    ((uf): a pooled t measures sampling density, not edge);
  * and — the one that would matter most — quietly acquiring an actuator.

The behavioural cases live in `brain_stats._selftest` (9 of 9 mutations
verified red); these are the STRUCTURAL claims a behavioural test cannot make.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import brain_stats as bs                  # noqa: E402
import bot_learn as bl                    # noqa: E402

SRC = os.path.join(ROOT, "brain_stats.py")
_TREE = ast.parse(open(SRC).read())


def _fn(name):
    for n in ast.walk(_TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{name} not found in brain_stats.py")


# --------------------------------------------------------------------------
# 1. IT MOVES NOTHING. An AST walk of CALL SITES, never a substring scan —
#    (po)/(yk): a page-wide substring check fails on its own comment and
#    passes a hand-rolled copy.
# --------------------------------------------------------------------------
FORBIDDEN = {"write_levers", "get_lever", "save_state", "publish",
             "market_open", "set_lever", "save_history"}


def test_selfgrade_calls_no_actuator():
    called = set()
    for fname in ("selfgrade_mult", "_sg_welch", "_sg_cluster_means",
                  "_sg_regime", "_sg_day"):
        for n in ast.walk(_fn(fname)):
            if isinstance(n, ast.Call):
                f = n.func
                called.add(f.attr if isinstance(f, ast.Attribute)
                           else getattr(f, "id", ""))
    assert not (called & FORBIDDEN), sorted(called & FORBIDDEN)


def test_selfgrade_returns_a_dict_and_takes_no_writer():
    """A grader that can only RETURN cannot steer. Pinned on the signature so
    a future caller cannot pass it a store/lever handle."""
    args = [a.arg for a in _fn("selfgrade_mult").args.args]
    assert args[0] == "era_trades"
    assert not ({"store", "levers", "publish", "state"} & set(args)), args


# --------------------------------------------------------------------------
# 2. THE BASIS. profit_ratio, never profit_abs — the whole design.
# --------------------------------------------------------------------------
def test_the_grade_reads_the_clip_invariant_basis_and_never_dollars():
    body = ast.dump(_fn("_sg_cluster_means"))
    assert "profit_ratio" in body
    assert "profit_abs" not in body, \
        "a size actuator graded in dollars is a tautology: 2x doubles the metric"


def test_selfgrade_never_reads_dollars_anywhere_in_its_own_call_tree():
    for fname in ("selfgrade_mult", "_sg_cluster_means", "_sg_welch"):
        assert "profit_abs" not in ast.dump(_fn(fname)), fname


# --------------------------------------------------------------------------
# 3. THE BASELINE IS A CONTROL ARM, NOT THE MOTIVATING WINDOW (I25).
# --------------------------------------------------------------------------
def test_a_bucket_with_no_flat_arm_is_never_graded():
    """No 1.0x closes means no control, and the bucket's own pre-multiplier
    window is exactly the biased baseline I25 forbids."""
    t = [{"enter_tag": "long-x", "profit_ratio": 0.05 + 0.001 * d,
          "open_ts": "2026-09-%02dT00:00:00+00:00" % d,
          "extra": {"brain_mult": 1.5}} for d in range(1, 21)]
    out = bs.selfgrade_mult({"b": t})
    assert out["pooled"]["graded"] == 0
    assert all(x["verdict"] == "undecidable" for x in out["buckets"])


def test_own_mean_is_reported_but_is_not_the_comparison():
    """`own_mean_pct` rides along as a corroborator; the t/delta must come
    from the flat arm. A bucket with a control arm grades; the same bucket
    without one does not — even though own_mean_pct exists in both."""
    sized = [{"enter_tag": "long-x", "profit_ratio": 0.03,
              "open_ts": "2026-09-%02dT00:00:00+00:00" % d,
              "extra": {"brain_mult": 1.5}} for d in range(1, 15)]
    flat = [{"enter_tag": "long-x", "profit_ratio": 0.001 * d,
             "open_ts": "2026-09-%02dT00:00:00+00:00" % d,
             "extra": {"brain_mult": 1.0}} for d in range(15, 29)]
    with_ctl = bs.selfgrade_mult({"b": sized + flat})["buckets"][0]
    without = bs.selfgrade_mult({"b": sized})["buckets"][0]
    assert without["own_mean_pct"] is not None
    assert without["t"] is None and with_ctl["t"] is not None


# --------------------------------------------------------------------------
# 4. FAIL-SAFE DIRECTION: absence never becomes a verdict.
# --------------------------------------------------------------------------
def test_dark_and_empty_inputs_assert_nothing():
    for arg in (None, {}, {"b": []}, {"b": [{}]}):
        out = bs.selfgrade_mult(arg)
        assert out["buckets"] == []
        assert out["pooled"]["graded"] == 0
        assert out["pooled"]["helping"] == 0 and out["pooled"]["hurting"] == 0


def test_the_floors_are_the_fleets_own_numbers():
    """MIN_N restates fleet_allocation's computability floor and the t bar is
    the fleet's standard evidence bar. Pinned so a future edit that loosens
    either has to say so here."""
    assert bs.SG_MIN_N == 10
    assert bs.SG_T == 2.0
    assert bs.SG_MIN_DAYS >= 5


# --------------------------------------------------------------------------
# 5. IT IS ACTUALLY WIRED, and wired REPORTED-ONLY. A grade nothing publishes
#    is the (gk) "rule nobody runs" shape.
# --------------------------------------------------------------------------
def test_the_brain_publishes_its_own_grade():
    src = open(os.path.join(ROOT, "bot_learn.py")).read()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "selfgrade_mult"]
    assert calls, "bot_learn never calls selfgrade_mult — the grade is dead code"
    assert '"selfgrade"' in src, "the grade is computed and never published"


def test_the_grade_is_not_read_by_any_sizing_path():
    """`compute_stake_mults` must not consult the self-grade: a grader that
    feeds back into the thing it grades stops being a control."""
    src = ast.dump(_fn_bl("compute_stake_mults"))
    assert "selfgrade" not in src


def _fn_bl(name):
    tree = ast.parse(open(os.path.join(ROOT, "bot_learn.py")).read())
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{name} not found in bot_learn.py")


# --------------------------------------------------------------------------
# 6. THE UNREFEREED RULES CARRY THEIR OWN NULL (ze). `pair_earner` measures
#    WORSE than chance (P(null>=real)=0.935 on the living fleet), reaches no
#    actuator, and used to advise "protect it in any universe change" — the
#    one act a starved book least needs (I26). The measurement must ride in
#    the sentence a human actually reads.
# --------------------------------------------------------------------------
def _hyps(kind, n=10, pnl=1.0):
    trades = [{"pair": "X", "profit_abs": pnl, "enter_tag": "t",
               "exit_reason": "roi", "duration_min": 60,
               "open_ts": "2026-09-01T00:00:00+00:00"} for _ in range(n)]
    _card, hyps = bl.analyse_bot("b", trades, None)
    return [h for h in hyps if h["kind"] == kind]


def test_pair_earner_advice_carries_its_measured_null():
    h = _hyps("pair_earner")
    assert h, "the rule must still fire — this is a labelling fix, not a cut"
    prop = h[0]["proposal"]
    assert "null" in prop.lower() and "0.935" in prop, prop
    assert "protect it in any universe change" not in prop, \
        "the old advice told a session to narrow on a chance finding"


def test_pair_bleeder_advice_does_not_order_a_drop():
    h = _hyps("pair_bleeder", n=10, pnl=-1.0)
    assert h
    prop = h[0]["proposal"]
    assert "measured harm" in prop, prop
    assert not prop.startswith("consider dropping"), prop


def test_neither_pair_rule_can_reach_an_actuator():
    """The labelling fix is the SECOND line of defence; the first is that
    derive_actions/derive_proposals structurally ignore these kinds. Pinned
    so a future session cannot wire a measured-chance rule to a lever."""
    ledger = {"b|tag:x": {"kind": k, "status": "ACTIONABLE",
                          "first_run": 1, "seen": 9}
              for k in ("pair_earner", "pair_bleeder",
                        "session_hot_zone", "session_dead_zone")}
    assert bl.derive_actions(ledger) == {}
    assert bl.derive_proposals(ledger) == []
