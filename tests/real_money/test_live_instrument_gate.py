"""[(lj)] The live Ticket Taker's instrument-class gate must not depend on an env var.

THE DEFECT. `(kt)`/`(ku)` shipped the tokenised-equity screen inside
`bull_entry_ok()`, and the entry loop calls that function only under
`if BULL_MODE:`. `BULL_MODE` is `os.environ.get("TT_BULL_MODE", "off")` — it
defaults to OFF. So the only thing standing between the real-money book and a
short on a tokenised equity was one environment variable being set on one
container.

THIS IS `(hj)` REPEATED ONE SCREEN OVER, and the lesson was already engraved in
the same file. `allowed_sides()`, ~80 lines above `live_instrument_ok()`, exists
because the SIDE restriction had exactly this shape, and its docstring says so:

    "Deliberately independent of BULL_MODE and of bull_entry_ok(): that gate is
     RESTRICT-ONLY and evaluated only when an env var is on, which is exactly
     why it cannot be the thing protecting real money."

`(kt)`'s own comment then states the dependency out loud as if it were a
safeguard — *"the live arm ... runs `bull: True` ... so every live real-money
entry passes through `bull_entry_ok` -> `_is_crypto`"*. A restriction that holds
because a variable happens to be set is not a gate.

MEASURED (OPERATOR_QUEUE item 0a, corrected 6-Aug): the live real-money book had
already opened **19 non-crypto positions**, five of them in-era short-divergence
(DRAM, MINIMAX, SKHY) — **5 of 14 in-era trades**, i.e. over a third of the
sample the go-live gate is grading on the book nearest real money.

WHAT THIS FILE PINS: the gate is BELT (entry loop) and BRACES (order path),
evaluated on the live arm regardless of BULL_MODE, restrict-only, and a strict
no-op on the shadow arm — which must keep taking non-crypto tickets, because
that grade is what justifies the live rule.
"""
import ast
import os
import pathlib

import pytest

pytestmark = [pytest.mark.real_money, pytest.mark.autonomy]

TAKER = pathlib.Path(__file__).resolve().parents[2] / "lighter_ticket_taker.py"


@pytest.fixture(scope="module")
def TT():
    os.environ.setdefault("TT_VENUE", "lighter_shadow")
    import lighter_ticket_taker as m
    return m


# ---------------------------------------------------------------------------
# the gate itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sym", ["CAP", "DRAM", "CXMT", "MINIMAX", "SKHY",
                                 "XAU", "WTI", "EURUSD", "GME", "OPENAI"])
def test_the_live_arm_refuses_every_tradfi_class(TT, sym):
    assert TT.live_instrument_ok("lighter_live", {"sym": sym}) is False


@pytest.mark.parametrize("sym", ["BTC", "ETH", "SOL", "HYPE", "1000BONK"])
def test_the_live_arm_still_admits_crypto(TT, sym):
    """The control group. A gate that refuses everything is not a gate — it is
    an outage, and it would read as 'no non-crypto trades' just the same."""
    assert TT.live_instrument_ok("lighter_live", {"sym": sym}) is True


@pytest.mark.parametrize("mode", ["lighter_shadow", "lighter_paper", "", None])
def test_the_shadow_arm_is_untouched(TT, mode):
    """Narrowing the shadow arm would blind the grade that justifies the live
    rule — the same reasoning allowed_sides() gives for both sides."""
    assert TT.live_instrument_ok(mode, {"sym": "CAP"}) is True
    assert TT.live_instrument_ok(mode, {"sym": "X", "noncrypto": True}) is True


def test_the_venue_stamp_screens_a_book_the_hand_list_has_never_seen(TT):
    """(ku)'s point: a newly listed equity is screened the moment the scout
    sees it, with no code change and no marked real-money deploy."""
    assert TT.live_instrument_ok(
        "lighter_live", {"sym": "NEVERSEENBEFORE", "noncrypto": True}) is False


def test_an_absent_stamp_means_no_opinion_never_crypto(TT):
    """ABSENT must fall through to the hand list, not admit."""
    assert TT.live_instrument_ok("lighter_live",
                                 {"sym": "CAP", "noncrypto": None}) is False
    assert TT.live_instrument_ok("lighter_live",
                                 {"sym": "CAP"}) is False


def test_junk_input_does_not_crash_the_entry_loop(TT):
    for junk in (None, {}, {"sym": None}, {"sym": ""}):
        assert TT.live_instrument_ok("lighter_live", junk) is True


def test_the_verdict_does_not_move_when_bull_mode_does(TT):
    """THE WHOLE DEFECT, asserted rather than described.

    A fixture that only ran at the current BULL_MODE would prove nothing about
    the configuration that caused the incident — which is BULL_MODE=off, the
    default.
    """
    saved = TT.BULL_MODE
    try:
        for bm in (True, False):
            TT.BULL_MODE = bm
            assert TT.live_instrument_ok("lighter_live", {"sym": "CAP"}) is False, bm
            assert TT.live_instrument_ok("lighter_live", {"sym": "BTC"}) is True, bm
    finally:
        TT.BULL_MODE = saved


def test_bull_mode_still_defaults_off(TT):
    """If this ever flips to on-by-default the incident's premise changes, and
    the entry above should be re-read rather than silently invalidated."""
    assert os.environ.get("TT_BULL_MODE", "off").strip().lower() \
        not in ("1", "true", "on", "yes")


# ---------------------------------------------------------------------------
# the WIRING — belt and braces, by AST over the real call sites
# ---------------------------------------------------------------------------

def _falsy_const(test):
    """True when an `if` test is a compile-time constant false.

    `if False:` leaves every line of the body in the source, so a check that
    the raise message "appears" is satisfied by dead code — the (lh) class:
    detecting DELETION and not DISABLEMENT. My own first cut of this file did
    exactly that and two mutations walked through it.
    """
    return isinstance(test, ast.Constant) and not test.value


@pytest.fixture(scope="module")
def calls():
    """Every PRODUCTION `live_instrument_ok(...)` guard, with its context.

    Scoped away from `_selftest`, which calls the gate a dozen times: counting
    those made a "the gate is called at least twice" assertion survive the
    deletion of BOTH real call sites. Asserting the gate exists is not enough —
    the defect being fixed is a correct gate placed inside an env-var branch.
    """
    tree = ast.parse(TAKER.read_text())

    # every line belonging to a selftest/helper definition we must ignore
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (
                node.name.startswith("_selftest") or node.name == "live_instrument_ok"):
            skip.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or node.lineno in skip:
            continue
        called = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                     and c.func.id == "live_instrument_ok"
                     for c in ast.walk(node.test))
        if not called:
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        out.append({
            "line": node.lineno,
            "under_bull": "BULL_MODE" in names,
            "dead": _falsy_const(node.test),
            "skips": any(isinstance(s, ast.Continue) for s in node.body),
            "halts": any(isinstance(s, ast.Raise) for s in node.body),
        })

    # a guard is also dead if any ENCLOSING if is a constant-false
    dead_spans = [range(n.lineno, (n.end_lineno or n.lineno) + 1)
                  for n in ast.walk(tree)
                  if isinstance(n, ast.If) and _falsy_const(n.test)]
    bull_spans = [range(n.lineno, (n.end_lineno or n.lineno) + 1)
                  for n in ast.walk(tree)
                  if isinstance(n, ast.If)
                  and "BULL_MODE" in {x.id for x in ast.walk(n.test)
                                      if isinstance(x, ast.Name)}]
    for c in out:
        c["dead"] = c["dead"] or any(c["line"] in s for s in dead_spans)
        c["under_bull"] = c["under_bull"] or any(c["line"] in s for s in bull_spans)
    return out


def test_the_gate_has_both_a_belt_and_braces(calls):
    """The empty-collection trap: every assertion below is vacuous on [].

    Both call sites must exist AND be live code — see `_falsy_const`.
    """
    live = [c for c in calls if not c["dead"]]
    assert len(live) >= 2, (
        "expected a live belt and a live braces guard on live_instrument_ok; "
        f"found {live} (all sites: {calls})")
    assert any(c["skips"] for c in live), "no belt: nothing skips the ticket"
    assert any(c["halts"] for c in live), (
        "no braces: nothing HALTS on the order path. Silently skipping a "
        "breached entry would leave the fleet's loudest real-money invariant "
        "looking like a quiet day")


def test_no_guard_sits_inside_a_bull_mode_branch(calls):
    """The regression that would restore the bug: move either guard back under
    `if BULL_MODE:` and the gate is env-var-conditional again."""
    inside = [c["line"] for c in calls if c["under_bull"]]
    assert not inside, (
        "live_instrument_ok() is guarded inside an `if BULL_MODE:` branch at "
        f"line(s) {inside} — that is the exact defect (lj) fixed: the gate "
        "becomes conditional on TT_BULL_MODE, which defaults to off")


def test_the_breach_message_is_reachable_code():
    """`if False:` leaves the raise in the source. Assert it is live."""
    dead = [c for c in _dead_raises() if "INSTRUMENT-CLASS" in c]
    assert not dead, f"the instrument-class breach raise is dead code: {dead}"


def _dead_raises():
    tree = ast.parse(TAKER.read_text())
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.If) and _falsy_const(node.test)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise):
                out.append(ast.dump(sub)[:400])
    return out
