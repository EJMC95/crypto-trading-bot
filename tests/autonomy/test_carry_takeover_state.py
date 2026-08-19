"""[2026-08-19 (qj)] A FAILOVER TAKEOVER MUST ADOPT THE INCUMBENT'S WORLD, NOT
RESUME ITS OWN BOOT SNAPSHOT.

THE DEFECT, found closing out the `(qi)` referee wave's declared F5. `(hp)`
made the two carry containers a deliberate failover pair — first claimant
keeps the book, the other IDLES and re-checks every loop. But the durable
restore (`load_state_required` + `funding_basis.restore_hot_since`) runs ONCE,
at boot, and the standby branch `continue`s before every bookkeeping step. So
a container that stands by for hours and then wins the claim resumes from its
own boot snapshot of a world the incumbent has been moving the whole time:

  * `positions` — carries the incumbent CLOSED are still open in the stale map
    and get closed a SECOND time (a duplicate ledger row: the `(hp)` two-writer
    damage through a different door); carries it OPENED are absent, and the
    takeover's first `save_state` overwrites the durable record with the older
    map, so they vanish.
  * `hot_since` — a coin hot at boot and hot now reads as persisted across the
    entire standby, unobserved. That is the PERMISSIVE direction `(iu)`/`(iq)`
    exist to refuse, on the book whose thesis is "persistent funding pays
    carries, spikes pay fees". `(qi)`'s 6h -> 12h move doubled the exposure,
    which is what surfaced this.
  * `last_ts` — stale positions and a stale clock are self-consistent, which is
    precisely why the three must be adopted ATOMICALLY: fresh `accrued` under
    an old clock re-credits the whole standby gap — the `(nc)` phantom-accrual
    class that already inflated this book's pooled ledger by ~$13.

WHAT IS PINNED, and why each arm exists:
  1. The adopter takes the DURABLE world, not the caller's (all three fields).
  2. It is fail-CLOSED on a failed read — `ok=False`, and the caller must not
     trade or save. Refusing costs a loop; guessing costs the ledger.
  3. A genuinely empty state is a real answer (flat book), NOT a refusal —
     otherwise a first-ever takeover would deadlock.
  4. The hot-streak rule stays `funding_basis`'s ONE owner, so this path
     cannot drift from the boot path it mirrors — including the long-gap
     refusal, which is what makes the permissive failure unreachable.
  5. The LOOP actually wires it (AST): the standby branch sets the flag, the
     claim-success path calls the adopter, and the refusal path `continue`s.
     Without arm 5 the whole fix is a function nobody calls.
"""
import ast
import pathlib

import pytest

import funding_carry_bot as carry
import funding_basis

pytestmark = pytest.mark.autonomy

_SRC = pathlib.Path(carry.__file__)
NOW = 1_785_600_000.0


def _durable(hot_age_s=60.0, saved_age_s=60.0, positions=None, last_ts=None):
    """A state blob as the INCUMBENT's `save_state` writes it."""
    return {
        "positions": {"XMR": {"side": "short_perp", "accrued": 1.23}}
        if positions is None else positions,
        "hot_since": {"XMR": NOW - hot_age_s},
        "last_ts": NOW - 300.0 if last_ts is None else last_ts,
        "saved_ts": NOW - saved_age_s,
    }


# ---------------------------------------------------------------------------
# 1-4 · the adopter itself
# ---------------------------------------------------------------------------

def test_it_adopts_the_durable_world_not_the_callers():
    ok, pos, hot, lts, why = carry.reclaim_after_standby(_durable(), True, NOW)
    assert ok, why
    assert pos == {"XMR": {"side": "short_perp", "accrued": 1.23}}, pos
    assert hot == {"XMR": NOW - 60.0}, hot
    assert lts == NOW - 300.0, lts


def test_a_failed_read_refuses_and_hands_back_nothing_to_trade_on():
    """The state that matters: `load_state_checked` ok=False means 'I could not
    find out'. Adopting anything there is the seed-on-failed-read class."""
    ok, pos, hot, lts, why = carry.reclaim_after_standby(_durable(), False, NOW)
    assert ok is False
    assert (pos, hot, lts) == (None, None, None)
    assert "FAILED" in why


def test_a_genuinely_empty_state_is_a_real_answer_not_a_refusal():
    """ok=True/state=None is 'definitely nothing stored' — a flat book. If this
    refused, a first-ever takeover could never proceed."""
    ok, pos, hot, lts, why = carry.reclaim_after_standby(None, True, NOW)
    assert ok is True and pos == {} and hot == {}
    assert lts == NOW, lts


def test_the_long_standby_gap_cannot_resurrect_a_streak():
    """THE PERMISSIVE FAILURE, closed. A 10h standby means nobody observed the
    hours between, so the clock must NOT carry across it — the (iu) long-gap
    refusal, reached through this path because the rule has one owner."""
    stale = _durable(hot_age_s=10 * 3600.0, saved_age_s=10 * 3600.0)
    ok, pos, hot, lts, why = carry.reclaim_after_standby(stale, True, NOW)
    assert ok and hot == {}, (hot, why)          # fresh clocks, not a 10h streak
    assert pos, "positions must still be adopted — only the CLOCK fails closed"
    # and a short handoff (a rolling deploy) DOES keep the clock
    ok2, _, hot2, _, _ = carry.reclaim_after_standby(
        _durable(hot_age_s=9 * 3600.0, saved_age_s=120.0), True, NOW)
    assert ok2 and hot2 == {"XMR": NOW - 9 * 3600.0}, hot2


def test_the_clock_rule_has_one_owner():
    """AST: the adopter must CALL funding_basis.restore_hot_since rather than
    re-derive the gap bound — a second copy of a rule is a second rule ((hj))."""
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == "reclaim_after_standby")
    calls = {c.func.attr for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
    assert "restore_hot_since" in calls, (
        "the takeover path must restore the clock through funding_basis, the "
        "ONE owner of the rule ((iu)) — not its own copy of the gap bound")
    assert funding_basis.HOT_RESTORE_MAX_GAP_S > 0


def test_the_accrual_clock_is_adopted_with_the_positions_never_apart():
    """Fresh `accrued` under a stale clock re-credits the standby gap — the
    (nc) phantom-accrual class. The pair must move together."""
    ok, pos, _, lts, _ = carry.reclaim_after_standby(
        _durable(last_ts=NOW - 7200.0), True, NOW)
    assert ok and pos and lts == NOW - 7200.0, lts
    # ...and ancient state is still bounded, exactly like the boot path
    ok2, _, _, lts2, _ = carry.reclaim_after_standby(
        _durable(last_ts=NOW - 99 * 3600.0), True, NOW, gap_cap_s=48 * 3600.0)
    assert ok2 and lts2 == NOW - 48 * 3600.0, lts2


def test_it_never_aliases_the_saved_dict():
    """The adopted map must not be the blob's own object — a later mutation of
    `positions` would otherwise edit the thing we just read from storage."""
    blob = _durable()
    ok, pos, _, _, _ = carry.reclaim_after_standby(blob, True, NOW)
    assert ok
    pos["NEW"] = {"side": "long_perp"}
    assert "NEW" not in blob["positions"], "adopted map aliases the saved blob"


# ---------------------------------------------------------------------------
# 5 · the loop actually wires it (AST — a fix nobody calls is not a fix)
# ---------------------------------------------------------------------------

def _main_fn():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_standby_branch_records_that_it_stood_down():
    """Mutation that reddens this: drop `_stood_down = True` from the standby
    branch — the takeover then silently resumes the stale world again."""
    fn = _main_fn()
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        # the standby branch: `if not _ok_writer:`
        if not (isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Name)
                and node.test.operand.id == "_ok_writer"):
            continue
        assigns = {t.id for a in ast.walk(node)
                   if isinstance(a, ast.Assign) for t in a.targets
                   if isinstance(t, ast.Name)}
        assert "_stood_down" in assigns, (
            "the standby branch no longer records standing down, so winning "
            "the claim later cannot know to re-adopt the durable world")
        return
    raise AssertionError("standby branch (`if not _ok_writer:`) not found")


def test_the_claim_success_path_adopts_before_trading():
    """The adopter must be CALLED inside main(), guarded by the flag, and the
    refusal path must `continue` — trading or saving on a refused read is the
    damage this whole file is about."""
    fn = _main_fn()
    guarded = None
    for node in ast.walk(fn):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                and node.test.id == "_stood_down"):
            guarded = node
            break
    assert guarded is not None, (
        "no `if _stood_down:` takeover branch in main() — the adopter is "
        "defined and never called, which is the registered-but-inert failure")
    calls = {c.func.id for c in ast.walk(guarded)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "reclaim_after_standby" in calls, calls
    assert any(isinstance(n, ast.Continue) for n in ast.walk(guarded)), (
        "the takeover branch has no `continue` — a refused read must not fall "
        "through into the trading pass and the save that follows it")
    rebound = {t.id for a in ast.walk(guarded) if isinstance(a, ast.Assign)
               for t in (a.targets[0].elts
                         if isinstance(a.targets[0], ast.Tuple) else a.targets)
               if isinstance(t, ast.Name)}
    for name in ("positions", "hot_since", "last_ts"):
        assert name in rebound, (
            f"the takeover branch never rebinds `{name}` — the three are one "
            f"snapshot and adopting them apart re-creates the (nc) class")
