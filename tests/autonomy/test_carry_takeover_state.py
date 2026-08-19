"""[2026-08-19 (qp)] A FAILOVER TAKEOVER MUST ADOPT THE INCUMBENT'S WORLD, NOT
RESUME ITS OWN BOOT SNAPSHOT.

THE DEFECT, found closing out the `(qo)` referee wave's declared F5. `(hp)`
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
    carries, spikes pay fees". `(qo)`'s 6h -> 12h move doubled the exposure,
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
from funding_carry_bot import takeover_step

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
# 5 · THE TAKEOVER ITSELF, DRIVEN BEHAVIOURALLY (the a6ce1b2 lesson).
#
# The first cut of this section was AST-only — "does `main()` mention these
# identifiers in these shapes". An adversarial round drove SEVEN survivors
# through it, every one a realistic regression: hardcoding `ok_read=True` at
# the call site, throwing the adopter's result away and self-assigning the
# caller's own values, replacing the checked read with `True, None` (which
# adopts an EMPTY world and then overwrites the durable record), and never
# clearing the flag. AST arms cannot see values, argument bindings, dead code
# or self-assignment — which is where all of those live. `takeover_step` takes
# its store as an argument precisely so the whole step can be driven against a
# fake, and these tests are the pins that survive mutation.
# ---------------------------------------------------------------------------

class FakeStore:
    """The durable side of the world, as the INCUMBENT left it."""

    def __init__(self, saved=None, ok_read=True, agg=None):
        self._saved, self._ok, self._agg = saved, ok_read, agg
        self.reads = 0

    def load_state_checked(self, bot):
        self.reads += 1
        return self._ok, self._saved

    def fetch_paper_aggregate(self, bot):
        return self._agg


def _agg(realized=54.0, closed=101, wins=40):
    return {"realized": realized, "closed": closed, "wins": wins,
            "losses": closed - wins}


def test_the_takeover_adopts_the_incumbents_whole_world():
    """All SIX fields, from the durable record — not the caller's memory."""
    store = FakeStore(saved=_durable(), agg=_agg())
    ok, world, why = takeover_step(store, "bot", NOW)
    assert ok, why
    assert world["positions"] == {"XMR": {"side": "short_perp", "accrued": 1.23}}
    assert world["hot_since"] == {"XMR": NOW - 60.0}
    assert world["last_ts"] == NOW - 300.0
    assert (world["realized"], world["n_closed"], world["n_wins"]) == (54.0, 101, 40)


def test_the_ledger_aggregate_is_re_read_not_carried():
    """THE REGRESSION THIS EXISTS FOR. Adopting a fresh position map against a
    STALE realised total books a step-down with no trade behind it: the row's
    `closed_trades` goes BACKWARDS and the same wrong equity reaches
    `<bot>:equity`, which the go-live max-drawdown bar reads worse-of-both.
    Measured at -$4.00 on a one-close standby before this was fixed."""
    store = FakeStore(saved=_durable(positions={}), agg=_agg(realized=54.0,
                                                             closed=101))
    ok, world, _ = takeover_step(store, "bot", NOW)
    assert ok
    # the incumbent's close is present in BOTH halves, so nothing cancels and
    # nothing double-counts: flat book, ledger truth.
    assert world["positions"] == {} and world["realized"] == 54.0
    assert world["n_closed"] == 101


def test_a_failed_state_read_holds_and_hands_back_no_world():
    store = FakeStore(saved=_durable(), ok_read=False, agg=_agg())
    ok, world, why = takeover_step(store, "bot", NOW)
    assert ok is False and world is None and "FAILED" in why


def test_a_failed_aggregate_read_also_holds():
    """Both reads are load-bearing: a fresh map under unknown realised totals
    is exactly the step-down above, so an unavailable ledger must HOLD too."""
    store = FakeStore(saved=_durable(), agg=None)
    ok, world, why = takeover_step(store, "bot", NOW)
    assert ok is False and world is None
    assert "aggregate" in why.lower()


def test_a_long_standby_clears_the_clock_through_the_whole_step():
    """End-to-end, not just in the adopter: at a REAL takeover the gap always
    exceeds the trusted bound (claim TTL 1800s vs restore bound 900s), so the
    honest outcome is cold clocks — a deterministic re-prove, not a restore."""
    store = FakeStore(saved=_durable(hot_age_s=10 * 3600.0,
                                     saved_age_s=1798.0), agg=_agg())
    ok, world, why = takeover_step(store, "bot", NOW)
    assert ok and world["hot_since"] == {}, why
    assert world["positions"], "only the CLOCK fails closed, never the book"


def test_the_claim_ttl_exceeds_the_clock_restore_bound():
    """The arithmetic the docstring rests on, pinned so a future change to
    either constant surfaces here instead of silently making the takeover
    permissive again."""
    import bot_pnl_store
    assert bot_pnl_store.WRITER_CLAIM_TTL > funding_basis.HOT_RESTORE_MAX_GAP_S


# ---------------------------------------------------------------------------
# 6 · the loop wires it — the minimum AST arm, now that behaviour is covered
# ---------------------------------------------------------------------------

def _main_fn():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_standby_branch_records_that_it_stood_down():
    fn = _main_fn()
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
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


def test_the_claim_success_path_calls_the_step_and_clears_the_flag():
    """Deliberately thin: it pins only what AST CAN see — that main() routes
    the takeover through `takeover_step`, `continue`s on a hold, rebinds all
    six fields, and CLEARS the flag (an un-cleared flag re-adopts durable
    state every loop and turns one transient read failure into a permanent
    refusal to trade). Everything about VALUES is covered above."""
    fn = _main_fn()
    guarded = next((n for n in ast.walk(fn)
                    if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                    and n.test.id == "_stood_down"), None)
    assert guarded is not None, (
        "no `if _stood_down:` takeover branch in main() — the step is defined "
        "and never called, the registered-but-inert failure")
    calls = {c.func.id for c in ast.walk(guarded)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "takeover_step" in calls, calls
    assert any(isinstance(n, ast.Continue) for n in ast.walk(guarded)), (
        "the takeover branch has no `continue` — a held read must not fall "
        "through into the trading pass and the save that follows it")
    rebound = {t.id for a in ast.walk(guarded) if isinstance(a, ast.Assign)
               for t in (a.targets[0].elts
                         if isinstance(a.targets[0], ast.Tuple) else a.targets)
               if isinstance(t, ast.Name)}
    for name in ("positions", "hot_since", "last_ts",
                 "realized", "n_closed", "n_wins", "_stood_down"):
        assert name in rebound, (
            f"the takeover branch never rebinds `{name}` — the six fields are "
            f"one snapshot and adopting them apart re-creates the very "
            f"step-down and (nc) accrual classes this step exists to prevent")
