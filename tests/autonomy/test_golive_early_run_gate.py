"""The 🚦 go-live grader's staleness-aware early run.

[2026-08-16] WHY. `run_all.sh` started this organ behind a bare `( sleep 900`
with NO early run — the last survivor of the pattern the `(os)`/`(ou)` sweep
replaced everywhere else. Measured that morning: the freqtrade-bots container
was redeploying every ~11 minutes under three concurrent sessions, so an organ
needing an uninterrupted 15-minute window to reach its FIRST publish can miss
it indefinitely, while every liveness contract still reads fine (I1). This
organ publishes the gate that governs REAL MONEY.

The sweep's own fix — `( sleep 20; <run once>; ...)` — is wrong here on COST,
which is why this needed its own shape rather than a paste: the eight organs it
was applied to loop every 900-3600s, whereas this one loops every 21600s and
each run grades every book off a 20k-row ledger fetch. Unconditionally running
it at each boot is ~30x its designed frequency during a push burst.

WHAT THESE TESTS PIN, in order of how badly it hurts to lose it:
  1. the gate SKIPS ONLY ON POSITIVE PROOF — every uncertainty runs, so the
     change can never be the reason the real-money gate goes unpublished;
  2. the gate is consulted BEFORE the ledger fetch (asserted on the AST, since
     a check that runs after `fetch_paper_trades` has already paid the entire
     cost it exists to avoid — and nothing textual would notice);
  3. the boundary `age == threshold` RUNS, or the organ's period silently
     doubles;
  4. the run_all.sh wiring: a SHORT boot stagger, a gated early run, and an
     UNGATED steady loop.
"""
import ast
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import golive_readiness as gl  # noqa: E402

NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)


def _state(age_s):
    return {"updated": (NOW - timedelta(seconds=age_s)).isoformat()}


# ---------------------------------------------------------------- semantics

def test_a_recent_publish_is_proof_and_skips():
    assert gl.publish_is_fresh(_state(60), 21600, now=NOW) is True
    assert gl.publish_is_fresh(_state(21599), 21600, now=NOW) is True


def test_the_boundary_runs_so_the_period_cannot_double():
    """age == threshold must RUN.

    If the loop were gated too and this returned True, a wake-up landing a
    hair early would skip and the next attempt would be a full interval later
    — a 6-hourly organ silently becoming 12-hourly, which no liveness check
    would flag (TTL is 12h)."""
    assert gl.publish_is_fresh(_state(21600), 21600, now=NOW) is False
    assert gl.publish_is_fresh(_state(21601), 21600, now=NOW) is False


@pytest.mark.parametrize("state", [
    None, {}, [], "nope", 0,
    {"updated": None},
    {"updated": ""},
    {"updated": "not-a-date"},
    {"updated": "2026-13-45T99:99:99"},
    {"nothing": "here"},
])
def test_every_unreadable_state_runs(state):
    """Fail-OPEN: no proof of freshness means run, which is exactly the
    behaviour before this gate existed."""
    assert gl.publish_is_fresh(state, 21600, now=NOW) is False


@pytest.mark.parametrize("limit", [None, 0, -1, -21600, float("nan"), "junk", object()])
def test_every_junk_threshold_runs(limit):
    assert gl.publish_is_fresh(_state(60), limit, now=NOW) is False


def test_a_future_stamp_is_not_proof_of_freshness():
    """Clock skew between containers must not silence the organ: a stamp in
    the future is unexplained, and unexplained is not proof."""
    assert gl.publish_is_fresh(_state(-3600), 21600, now=NOW) is False


def test_naive_and_utc_suffixed_stamps_are_read_not_crashed():
    naive = (NOW - timedelta(seconds=60)).replace(tzinfo=None).isoformat()
    assert gl.publish_is_fresh({"updated": naive}, 21600, now=NOW) is True
    spaced = (NOW - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S UTC")
    assert gl.publish_is_fresh({"updated": spaced}, 21600, now=NOW) is True


def test_it_reuses_parse_stamp_rather_than_rolling_a_second_parser():
    """A second copy of a rule is a second rule. `parse_stamp` is this file's
    own tolerant parser and the gate must go through it, so a future widening
    (another timestamp dialect) reaches both."""
    src = open(os.path.join(ROOT, "scripts", "golive_readiness.py")).read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "publish_is_fresh")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "parse_stamp" in called, (
        "publish_is_fresh must parse via parse_stamp, not its own parser")


# ------------------------------------------------------------------ wiring

def _main_fn():
    src = open(os.path.join(ROOT, "scripts", "golive_readiness.py")).read()
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_gate_is_consulted_before_the_ledger_fetch():
    """THE ORDERING IS THE WHOLE POINT.

    A freshness check placed after `fetch_paper_trades` would be correct,
    green, and worthless — it would already have paid the 20k-row fetch it
    exists to avoid. Asserted on line numbers of the real call nodes because
    no substring test can see ordering."""
    fn = _main_fn()
    gate = [n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "publish_is_fresh"]
    fetch = [n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "fetch_paper_trades"]
    assert gate, "main() must consult publish_is_fresh"
    assert fetch, "main() must still fetch the ledger"
    assert min(gate) < min(fetch), (
        "the early-run gate must be checked BEFORE fetch_paper_trades, or it "
        "saves nothing it was built to save")


def _gate_node():
    """The `if a.publish and a.publish_if_stale is not None:` block itself.

    Scoped deliberately. The first version of the test below asserted over all
    of `main()` and was VACUOUS — the docket's own `load_state_checked` call
    (a different feature, ~100 lines later) satisfied it, so swapping the
    gate's read to `load_state` stayed green. Caught by mutation, which is the
    only thing that ever catches this."""
    for node in ast.walk(_main_fn()):
        if not isinstance(node, ast.If):
            continue
        if any(isinstance(x, ast.Attribute) and x.attr == "publish_if_stale"
               for x in ast.walk(node.test)):
            return node
    raise AssertionError("no early-run gate found in main()")


def test_a_failed_read_is_not_treated_as_no_row():
    """`load_state` collapses 'no row' and 'read failed'; the gate must use
    `load_state_checked` and honour its ok flag, or a Postgres blip reads as
    'never published' — [[load-state-seeds-durable-state-on-a-failed-read]].

    Here the trap points the SAFE way (a false 'no row' would run, not skip),
    which is exactly why it needs pinning: nothing would go wrong today, so
    nothing would notice the day the direction changed."""
    gate = _gate_node()
    called = {n.func.attr for n in ast.walk(gate)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "load_state_checked" in called, (
        "the early-run gate must read through load_state_checked so a failed "
        "read is distinguishable from an absent row")


def test_the_skip_requires_both_a_good_read_and_positive_freshness():
    """The `return 0` must be guarded by BOTH the ok flag and
    `publish_is_fresh` — dropping the ok half is the mutation that makes a
    dead database look like a fresh publish."""
    gate = _gate_node()
    skips = [n for n in ast.walk(gate)
             if isinstance(n, ast.If)
             and any(isinstance(b, ast.Return) for b in n.body)]
    assert skips, "the gate must be able to skip"
    test = skips[0].test
    assert isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And), (
        "the skip condition must be a conjunction, not a single term")
    parts = test.values
    assert any(isinstance(p, ast.Name) for p in parts), \
        "the read-ok flag must be one conjunct of the skip condition"
    assert any(isinstance(p, ast.Call) and isinstance(p.func, ast.Name)
               and p.func.id == "publish_is_fresh" for p in parts), \
        "publish_is_fresh must be one conjunct of the skip condition"


# --------------------------------------------------------- run_all.sh block

def _golive_block():
    """The `( ... ) &` subshell that runs the grader, as a list of lines.

    Located structurally rather than by page-wide grep: walk back from the
    first golive invocation to its opening `(`, forward to the closing
    `) &`."""
    lines = open(os.path.join(ROOT, "run_all.sh")).read().splitlines()
    hits = [i for i, ln in enumerate(lines) if "golive_readiness.py" in ln]
    assert hits, "run_all.sh must still schedule the go-live grader"
    start = max(i for i in range(hits[0] + 1) if lines[i].lstrip().startswith("("))
    end = next(i for i in range(hits[-1], len(lines)) if ") &" in lines[i])
    return lines[start:end + 1]


def test_no_long_sleep_precedes_the_first_publish_attempt():
    """THE DEFECT WAS A LONG SLEEP IN FRONT OF THE FIRST RUN.

    Stated as the invariant rather than as a shape: whatever the block looks
    like, nothing longer than a token stagger may sit between container start
    and the first publish attempt. Measured 16-Aug, 22 of 22 inter-deploy gaps
    were shorter than the 900s that used to sit here, so the organ publishing
    the real-money gate could not reach its first run at all.

    Written this way deliberately — an earlier version asserted the block
    OPENED with `( sleep N` and would have failed on the shipped fix, which
    opens with the invocation itself (boot+0). A test that pins a shape
    instead of a property rejects a better implementation of the same idea."""
    block = _golive_block()
    first = next(i for i, ln in enumerate(block)
                 if "golive_readiness.py" in ln)
    for ln in block[:first]:
        for m in re.finditer(r"\bsleep\s+(\d+)", ln):
            assert int(m.group(1)) <= 60, (
                f"a {m.group(1)}s sleep precedes the first publish attempt; "
                "under this fleet's deploy cadence the organ never reaches it")


def test_the_early_run_is_gated_and_the_steady_loop_is_not():
    block = _golive_block()
    # [(vm)] COUNT INVOCATIONS, NOT MENTIONS. This read "golive_readiness.py"
    # in ln and so counted COMMENTS: the day a neighbouring loop's comment
    # named the grader (explaining which files Dockerfile.freqtrade COPYs) the
    # count went 2 -> 3 and this failed on prose. The property is about how
    # many times the organ is RUN, so only executable lines may be counted —
    # and it stays strict, because a genuine third invocation still fails.
    idx = [i for i, ln in enumerate(block)
           if "golive_readiness.py" in ln and not ln.lstrip().startswith("#")]
    assert len(idx) == 2, f"expected exactly 2 invocations, got {len(idx)}"
    early = " ".join(block[idx[0]:idx[0] + 2])
    steady = " ".join(block[idx[1]:idx[1] + 2])
    assert "--publish-if-stale" in early, (
        "the boot-time run must be staleness-gated, or every restart re-grades "
        "every book")
    assert "--publish-if-stale" not in steady, (
        "the steady loop must stay UNCONDITIONAL: gating it lets jitter at the "
        "boundary skip a cycle and double the organ's period")
    loop = next(i for i, ln in enumerate(block) if "while true" in ln)
    assert idx[0] < loop < idx[1], (
        "order must be: early gated run, then the loop containing the "
        "unconditional run")


def test_the_gate_threshold_tracks_the_loop_interval():
    """Both must read the same env var, or the gate can be tuned out of step
    with the schedule it is protecting."""
    block = _golive_block()
    var = "GOLIVE_INTERVAL_SEC"
    early = [ln for ln in block if "--publish-if-stale" in ln]
    assert early and var in " ".join(early + [block[i] for i, ln
                                              in enumerate(block)
                                              if "--publish-if-stale" in ln]), \
        f"the early run's threshold must come from ${var}"
    assert any(var in ln and "sleep" in ln for ln in block), \
        f"the loop period must come from ${var}"
