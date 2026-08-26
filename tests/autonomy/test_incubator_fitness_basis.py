"""[2026-08-26] THE INCUBATOR SCORED A BOOK THE TAKER DOES NOT RUN.

TWO MECHANISMS, and they are **MUTUALLY EXCLUSIVE, NOT INDEPENDENT** — the
distinction was refuted into place by an adversarial referee driving the real
code, and it is recorded here because getting it backwards makes half the fix
look optional and the other half look harmful:

  1. `evaluate()` called `rp.replay(tape)` at three sites with NO `up_resolver`,
     while `lighter_scout_tuner` passes one. Without a resolver the replay
     forces `up=False` on the breakout lens, so the taker's relabel to
     `breakoutup` never fires — `rp.UNREACHABLE_WITHOUT_RESOLVER` says exactly
     that, in the harness's own words.
  2. `_marked`/`_pnl_usd`/`_marked_series` filter `if l in lenses`, where
     `lenses` came from `live_lenses()` = `set(LENS_GENE) - vetoed`.
     `LENS_GENE` has FOUR keys and none is `breakoutup`.

**Only one can be in force for a given trade.** With no resolver an up-regime
crypto breakout is scored under the label `breakout`, which IS a `LENS_GENE`
key — so where `breakout` is unvetoed the P&L was *included*, and shipping the
resolver ALONE would move it into a bucket nothing scores, making the score
strictly WORSE. That is why both halves ship together, and it is pinned below
(`test_the_resolver_alone_would_make_the_score_worse`).

WHERE THE ORGAN WAS ACTUALLY BLIND is the regime it runs in: the brain grades
breakout/dip/momentum negative at sample size, so `allowed` collapses to
`{divergence}` — and then the up-regime book is scored under NEITHER name.
Production, same window: the scout tuner's replay reads baseline **+$22.21**
with `breakoutup` contributing **+$34.39 over 22 closes**, while this organ's
default genome reads **-$62.02**, with `h1 > 0` in **0 of 1519** genotypes and
`elite = 0`. That gap is NOT a like-for-like attribution (the tuner's number is
closed-only across five lenses; this one is mark-inclusive across four), and no
bar was moved to chase it — see `PREREG_INCUBATOR_FITNESS_2026-08-26.md`.

WHAT THIS FILE PINS, and why each arm is shaped the way it is:

  * The wiring is asserted on the **AST**, not on a substring — a `grep` for
    "up_resolver" stays green against a resolver that is built and dropped, and
    against `up_resolver=None` hard-coded at the call site.
  * The FITNESS arm drives the REAL `rp.replay` over a tape in the scout's own
    payload shape, in the PRODUCTION lens regime, and asserts the score MOVES.
    It fails if either half is reverted, and the `{breakout, divergence}`
    control fails if only the resolver ships.
  * `breakoutup` is admitted on the TAKER'S asymmetry — it is vetoed by its own
    `long-breakoutup` closes through `tt.breakoutup_self_vetoed`, never by the
    scout's `breakout` grade, because the taker relabels BEFORE it vetoes.
  * `LENS_GENE` must keep exactly its four ENTRY genes: `breakoutup` has no
    gene of its own (it rides `BRK_RANGE`), and adding it there would make
    `evolvable_genes` drop `BRK_RANGE` whenever either name is vetoed.

NOT CLAIMED, deliberately: that any genotype becomes a gamete or that any book
earns more. This makes the organ measure the same book its sibling measures;
the consequence is unknown and the pre-registration grades it on production.
"""
import ast
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import lighter_ticket_replay as rp
import lighter_ticket_taker as tt
import strategy_incubator as si

pytestmark = pytest.mark.autonomy

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "strategy_incubator.py"


# ---------------------------------------------------------------------------
# a tape in the SCOUT'S OWN payload shape (marks + per-lens tickets), long
# enough that halves are real windows rather than one row each
# ---------------------------------------------------------------------------

T0 = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)

#: BTC = an up-regime CRYPTO long breakout (relabelled `breakoutup` when a
#: resolver is present). ETH = a divergence SHORT that loses — the shape of the
#: live book, where the only unvetoed lens is the losing one.
#: DIV2 is a THIRD ticket, on the off-phase, at a gap the DEFAULT genome
#: refuses (55 < DIV_GAP_PP 62.5) and a LOOSER allele takes — and it loses
#: badly. It exists so the population is not uniform at the both-halves gate:
#: without it every genotype that clears the closes floor also clears halves,
#: and a funnel that computes that gate over the WHOLE population is
#: indistinguishable from a cumulative one (a mutation survived on exactly
#: that).
BRK_SYM, DIV_SYM, DIV2_SYM = "BTC", "ETH", "SOL"


def _snap(h, marks, tickets=None):
    p = {"marks": dict(marks), "tickets": tickets or {}}
    return (T0 + timedelta(hours=h), p)


#: The two lenses run on DIFFERENT periods on purpose (6h vs 4h). Equal
#: periods make every genotype produce the same close count, and a funnel
#: whose gates all admit the same set cannot distinguish a CUMULATIVE chain
#: from an independent one — two mutations survived on exactly that.
BRK_PERIOD, DIV_PERIOD = 6, 4


def build_tape(n_snaps=60):
    """Open on the hour, resolve one hour later, quiet in between.

    Deliberately MORE ROWS THAN THE WINDOW (60 snapshots, halves of 30) and in
    time ORDER, so a half is a real sample and `_marked`'s halves mean
    something. A one-row-per-key fixture cannot test a window.

    Sizing is chosen so the hidden lens is what carries the genome:
      * BRK (crypto long, up-regime) resolves +12% -> take profit, 10 closes.
      * DIV (short) resolves +3.2% against it -> stop loss, 15 closes.
    So `divergence`-only (the pre-fix score) is NEGATIVE in both halves and the
    resolved book is positive in both — the both-halves gate literally flips,
    which is the gate "0 of 1519 genotypes" was measuring. And a genotype whose
    `DIV_GAP_PP` allele refuses this ticket keeps only the 10 breakout closes,
    landing BELOW `MIN_GT_CLOSES` while still passing both halves — the case
    that separates the funnel's cumulative chain from an independent one."""
    tape = []
    for i in range(n_snaps):
        marks = {BRK_SYM: 112.0 if i % BRK_PERIOD == 1 else 100.0,
                 DIV_SYM: 103.2 if i % DIV_PERIOD == 1 else 100.0,
                 DIV2_SYM: 108.0 if i % DIV_PERIOD == 3 else 100.0}
        tickets = {}
        if i % BRK_PERIOD == 0:
            tickets["breakout"] = [{"sym": BRK_SYM, "range_pos": 0.99,
                                    "vol_m": 5.0}]
        if i % DIV_PERIOD == 0:
            tickets["divergence"] = [{"sym": DIV_SYM, "gap_pct": 70.0,
                                      "side": "short", "vol_m": 5.0}]
        elif i % DIV_PERIOD == 2:
            # the off-phase, because the replay opens at most ONE position per
            # lens per snapshot — two divergence tickets in one snapshot would
            # silently drop the second
            tickets["divergence"] = [{"sym": DIV2_SYM, "gap_pct": 55.0,
                                      "side": "short", "vol_m": 5.0}]
        tape.append(_snap(i, marks, tickets))
    return tape


DEFAULT_GT = {"DIV_GAP_PP": tt.DIV_GAP_PP}


def _always_up(_sym, _ts):
    return True


@pytest.fixture(scope="module")
def tape():
    return build_tape()


# ---------------------------------------------------------------------------
# 0. THE FIXTURE IS NON-VACUOUS — the positive control for every arm below.
#    "Empty output is not a negative result until the check has been seen to
#    produce a positive one."
# ---------------------------------------------------------------------------

def test_fixture_actually_produces_a_breakoutup_book(tape):
    with_res = rp.replay(tape, up_resolver=_always_up)
    without = rp.replay(tape)
    assert with_res["lenses"].get("breakoutup", {}).get("closed", 0) >= 10, \
        "fixture must produce a real breakoutup sample, not one lucky close"
    assert with_res["lenses"]["breakoutup"]["net"] > 0, \
        "the hidden lens must be a WINNER here, or hiding it costs nothing"
    assert with_res["lenses"].get("divergence", {}).get("net", 0.0) < 0, \
        "the surviving lens must LOSE, mirroring the live book"
    # and the harness itself says the lens is unreachable without a resolver
    assert "breakoutup" not in without["lenses"]
    assert "breakoutup" in without["coverage"]["unreachable"]
    assert without["coverage"]["up_resolver"] is False


# ---------------------------------------------------------------------------
# 1. WIRING — asserted on the AST. A substring test is not a wiring test.
# ---------------------------------------------------------------------------

def _func(name):
    tree = ast.parse(SRC.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {SRC}")


def _replay_calls(fn):
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "replay" \
                and isinstance(f.value, ast.Name) and f.value.id == "rp":
            out.append(node)
    return out


def test_evaluate_passes_the_resolver_to_every_replay():
    fn = _func("evaluate")
    calls = _replay_calls(fn)
    assert len(calls) == 3, (
        "evaluate() should replay the full tape and both halves; found "
        f"{len(calls)} rp.replay call(s)")
    assert "up_resolver" in [a.arg for a in fn.args.args], \
        "evaluate() must ACCEPT a resolver, not build one per genotype"
    for call in calls:
        kw = {k.arg: k.value for k in call.keywords}
        assert "up_resolver" in kw, (
            f"rp.replay at line {call.lineno} is missing up_resolver= — that "
            "call scores a book without the breakoutup lens")
        val = kw["up_resolver"]
        assert isinstance(val, ast.Name) and val.id == "up_resolver", (
            f"rp.replay at line {call.lineno} must forward evaluate()'s own "
            "parameter; a literal (e.g. None) is the defect wearing the fix")


def test_rank_accepts_and_forwards_the_resolver():
    fn = _func("rank")
    assert "up_resolver" in [a.arg for a in fn.args.args]
    ev = [n for n in ast.walk(fn)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == "evaluate"]
    assert ev, "rank() must call evaluate()"
    for call in ev:
        kw = {k.arg: k.value for k in call.keywords}
        assert "up_resolver" in kw and isinstance(kw["up_resolver"], ast.Name) \
            and kw["up_resolver"].id == "up_resolver", \
            "rank() must forward its resolver to evaluate(), not swallow it"


def test_run_once_hands_rank_the_resolver_it_built():
    """AST: `rank()` in run_once must receive the NAME run_once bound from
    `build_up_resolver`, never a literal.

    Found by a surviving mutation. `up_resolver=None` at that one call site
    scores every genotype of the cycle blind while `funnel["up_resolver"]`
    still publishes `true` off the built object — coverage the payload CLAIMS
    and the scoring did not have, which is strictly worse than being blind
    honestly. The behavioural twin is
    `test_the_vetoed_regime_cycle_scores_the_hidden_lens`; this arm is the
    cheap structural one that names the defect."""
    run = _func("run_once")
    built = [n for n in ast.walk(run)
             if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Name)
             and n.value.func.id == "build_up_resolver"]
    assert len(built) == 1 and isinstance(built[0].targets[0], ast.Name), \
        "run_once must bind the cycle's resolver to a name exactly once"
    name = built[0].targets[0].id
    calls = [n for n in ast.walk(run)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "rank"]
    assert calls, "run_once must rank the population"
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert "up_resolver" in kw, (
            f"rank() at line {c.lineno} is missing up_resolver= — the whole "
            "cycle would be scored without the breakoutup lens")
        val = kw["up_resolver"]
        assert isinstance(val, ast.Name) and val.id == name, (
            f"rank() at line {c.lineno} must be handed `{name}`, the resolver "
            "run_once built; a literal is the defect wearing the fix, and the "
            "funnel would still report up_resolver: true")


def test_the_resolver_is_built_once_per_cycle_not_per_genotype():
    """A cycle scores ~1519 genotypes x 3 replays. The builder is a per-symbol
    candle fetch, so building it inside evaluate()/rank() would be ~4500
    constructions of the same object."""
    for name in ("evaluate", "rank"):
        fn = _func(name)
        built = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "build_up_resolver"]
        assert not built, f"{name}() must not build a resolver (per-genotype cost)"
    run = _func("run_once")
    built = [n for n in ast.walk(run)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "build_up_resolver"]
    assert len(built) == 1, (
        f"run_once() must build the cycle's resolver exactly once; found "
        f"{len(built)}")


def test_rank_builds_no_resolver_across_many_genotypes(tape, monkeypatch):
    """The behavioural twin of the AST arm above, with a counted denominator:
    the factory must be called ONCE for the whole cycle while the replay runs
    many times."""
    calls = {"factory": 0, "replay": 0}
    real_replay = rp.replay

    def counting_factory(syms, lo, hi):
        calls["factory"] += 1
        return _always_up

    def counting_replay(*a, **kw):
        calls["replay"] += 1
        return real_replay(*a, **kw)

    monkeypatch.setattr(si.rp, "daily_up_resolver", counting_factory)
    monkeypatch.setattr(si.rp, "replay", counting_replay)

    res = si.build_up_resolver(tape)                     # the once-per-cycle build
    pop = [{"DIV_GAP_PP": v} for v in si.TAKER_GENES["DIV_GAP_PP"][1]]
    assert len(pop) >= 5
    si.rank(pop, tape, {"divergence", "breakoutup"}, up_resolver=res)

    assert calls["replay"] == 3 * len(pop), calls
    assert calls["factory"] == 1, (
        f"the resolver was constructed {calls['factory']} times across "
        f"{calls['replay']} replays — it must be built once per CYCLE")


# ---------------------------------------------------------------------------
# 2. THE FITNESS ARM — the non-vacuous core. It must FAIL if either exclusion
#    returns, so both are exercised against the same tape and genome.
# ---------------------------------------------------------------------------

def test_up_regime_breakout_pnl_reaches_the_fitness(tape):
    scored = si.scored_lens_set({"divergence"}, {}, tt.BOT_ROW)
    assert scored == {"divergence", "breakoutup"}, scored

    blind = si.evaluate(DEFAULT_GT, tape, scored)                    # half 1 back
    seen = si.evaluate(DEFAULT_GT, tape, scored, up_resolver=_always_up)

    rep = rp.replay(tape, up_resolver=_always_up)
    brk_net = rep["lenses"]["breakoutup"]["net"]
    brk_n = rep["lenses"]["breakoutup"]["closed"]

    assert seen["net"] > blind["net"], (
        "the up-regime breakout book must REACH the fitness; got "
        f"blind={blind['net']} seen={seen['net']}")
    assert seen["net"] == pytest.approx(blind["net"] + brk_net, abs=0.05), (
        "the whole of the relabelled lens's P&L must land in the score, not a "
        f"slice of it: {blind} -> {seen}, lens net {brk_net}")
    assert seen["closes"] == blind["closes"] + brk_n
    # the HALVES must move too — a full-tape resolver with blind halves would
    # grade a genotype's halves on different coverage from its own total
    assert seen["h1"] > blind["h1"] and seen["h2"] > blind["h2"], (blind, seen)
    # and the gap is DECISION-SIZED: it crosses the both-halves gate, which is
    # what "0 of 1519 genotypes" was measuring
    assert blind["both_halves_pos"] is False
    assert seen["both_halves_pos"] is True, (
        "on this fixture the hidden lens is what makes the genome viable — if "
        "it does not flip the gate the arm proves nothing")


def test_the_old_lens_set_still_hides_it_even_with_a_resolver(tape):
    """The CONTROL for the lens-set half. With a resolver but the pre-fix lens
    set (`set(LENS_GENE) - vetoed`, which can never contain `breakoutup`), the
    score must collapse back to the blind number — so this test fails the day
    someone reverts `scored_lens_set` and keeps only the resolver."""
    blind = si.evaluate(DEFAULT_GT, tape, {"divergence"})
    old_set = si.evaluate(DEFAULT_GT, tape, {"divergence"},
                          up_resolver=_always_up)
    assert old_set["net"] == pytest.approx(blind["net"], abs=1e-9)
    assert old_set["closes"] == blind["closes"]
    assert "breakoutup" not in set(si.LENS_GENE), \
        "if breakoutup ever enters LENS_GENE this control stops controlling"


def test_the_resolver_alone_would_make_the_score_worse(tape):
    """THE REFEREE'S CORRECTION, pinned so it cannot be re-forgotten.

    The two mechanisms are MUTUALLY EXCLUSIVE. Where `breakout` is unvetoed,
    the pre-fix organ DID score the up-regime book — under the label
    `breakout`, which is a `LENS_GENE` key. Shipping the resolver on its own
    RELABELS that P&L into `breakoutup`, a bucket the pre-fix lens set cannot
    contain, so the score gets strictly WORSE.

    This is the arm that makes "both halves ship together" a measurement
    rather than a preference — and it is the reason a future session must not
    "simplify" `scored_lens_set` away while keeping the resolver."""
    old_lenses = {"breakout", "divergence"}          # a pre-fix `allowed` set
    before = si.evaluate(DEFAULT_GT, tape, old_lenses)
    resolver_only = si.evaluate(DEFAULT_GT, tape, old_lenses,
                                up_resolver=_always_up)
    assert before["closes"] > resolver_only["closes"], (
        "the fixture must have breakout P&L for the relabel to move, or this "
        f"arm proves nothing: {before} vs {resolver_only}")
    assert resolver_only["net"] < before["net"], (
        "the resolver ALONE must be a regression — that is why the lens set "
        f"moves with it: {before} -> {resolver_only}")
    # ...and the FULL fix (resolver + widened lens set) recovers it and more
    full = si.evaluate(DEFAULT_GT, tape,
                       si.scored_lens_set(old_lenses, {}, tt.BOT_ROW),
                       up_resolver=_always_up)
    assert full["net"] >= before["net"], (before, resolver_only, full)


def test_a_dark_resolver_degrades_to_reduced_coverage_never_an_error(tape,
                                                                     monkeypatch):
    """Fail-safe direction: an unbuildable resolver must return None (reduced
    coverage), never raise and never fabricate coverage."""
    def boom(*_a, **_k):
        raise RuntimeError("candles down")

    monkeypatch.setattr(si.rp, "daily_up_resolver", boom)
    assert si.build_up_resolver(tape) is None
    # and the scoring path still works, just narrower
    out = si.evaluate(DEFAULT_GT, tape, {"divergence", "breakoutup"},
                      up_resolver=None)
    assert out["closes"] > 0


def test_kill_switch_reaches_the_builder(monkeypatch, tape):
    built = []

    def factory(syms, lo, hi):
        built.append(syms)
        return _always_up

    monkeypatch.setattr(si.rp, "daily_up_resolver", factory)
    assert si.build_up_resolver(tape) is not None and built

    built.clear()
    monkeypatch.setattr(si, "UP_RESOLVER_ON", False)
    assert si.build_up_resolver(tape) is None
    assert built == [], "a disabled resolver must not even be constructed"


def test_kill_switch_env_name_is_the_incubators_own():
    """The tuner's builder is gated by SCOUT_TUNER_UP_RESOLVER. Reusing it
    would let one organ's kill switch silently revert ANOTHER organ's fitness
    to the defect this file exists to close.

    Asserted on the ENV READS, not on the file text — the module names the
    tuner's switch in prose to explain why it is not reused, and a substring
    scan would fail on that sentence (the "a page-wide substring scan is not a
    structural claim" trap)."""
    tree = ast.parse(SRC.read_text())
    reads = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str) \
                and "UP_RESOLVER" in node.args[0].value:
            reads.add(node.args[0].value)
    assert reads == {"INCUBATOR_UP_RESOLVER"}, (
        f"this organ must own its resolver kill switch; env reads: {reads}")


# ---------------------------------------------------------------------------
# 3. THE SCORED LENS SET — the taker's veto asymmetry, imported not re-derived
# ---------------------------------------------------------------------------

def _mults(tag, row=None):
    return {"mults": {row or tt.BOT_ROW: {"long-breakoutup": tag}}}


def test_breakoutup_is_scored_whenever_breakout_is_allowed():
    out = si.scored_lens_set({"breakout", "dip", "momentum", "divergence"}, {},
                             tt.BOT_ROW)
    assert "breakoutup" in out
    assert {"breakout", "dip", "momentum", "divergence"} <= out, \
        "the allowed set must be preserved, not replaced"


def test_a_vetoed_breakout_does_not_veto_breakoutup():
    """The taker relabels BEFORE it applies `lens_vetoed` (the entry loop's
    "(dk) breakout_up RELABEL — BEFORE the veto"), which is precisely how the
    up-regime subset escapes the broad breakout veto and keeps filling. In
    production the brain vetoes breakout/dip/momentum and only `divergence`
    survives — so gating this on `breakout in allowed` would leave the fix
    inert exactly where it is needed."""
    out = si.scored_lens_set({"divergence"}, {}, tt.BOT_ROW)
    assert out == {"divergence", "breakoutup"}, out


def test_a_breakoutup_self_veto_excludes_it_and_leaves_breakout_scored():
    decisive = _mults({"mult": 0.5, "n": 99})
    out = si.scored_lens_set({"breakout", "divergence"}, decisive, tt.BOT_ROW)
    assert "breakoutup" not in out, "a decisive floor-reduce must veto the lens"
    assert {"breakout", "divergence"} <= out, \
        "the self-veto is breakoutup's alone — it must not touch `breakout`"


@pytest.mark.parametrize("tag,expected", [
    ({"mult": 0.5, "n": 99}, False),      # decisive floor-reduce => vetoed
    ({"mult": 0.5, "n": 30}, False),      # exactly at the brain's floor
    ({"mult": 0.5, "n": 29}, True),       # below the floor => keep collecting
    ({"mult": 0.75, "n": 99}, True),      # mild reduce => keep collecting
    ({"mult": 1.5, "n": 99}, True),       # expand (a winner)
    ({"mult": 0.5}, True),                # no n field => fail-OPEN
])
def test_the_veto_is_the_takers_own_thresholds(tag, expected):
    """Driven through the taker's real function — the rule is imported, never
    re-implemented, so these cases move only when the taker moves."""
    out = si.scored_lens_set({"breakout"}, _mults(tag), tt.BOT_ROW)
    assert ("breakoutup" in out) is expected, (tag, out)


@pytest.mark.parametrize("payload", [None, {}, {"mults": {}},
                                     {"mults": {"other-lighter": {}}},
                                     {"junk": 1}])
def test_a_dark_or_foreign_grade_vetoes_nothing(payload):
    assert "breakoutup" in si.scored_lens_set({"breakout"}, payload, tt.BOT_ROW)


@pytest.mark.parametrize("junk", [[1, 2, 3], "not-a-payload", 7,
                                  {"mults": "not-a-map"}])
def test_a_malformed_grade_fails_OPEN_rather_than_raising(junk):
    """A restrict-only rule must never crash the organ, and must never veto on
    garbage: the fail-safe direction for a lens is KEEP SCORING it, because
    silently dropping 39% of the book is the defect this file closes."""
    out = si.scored_lens_set({"breakout"}, junk, tt.BOT_ROW)
    assert "breakoutup" in out, junk


def test_the_default_row_is_this_bots_own():
    """`scored_lens_set` may be called without a row (its signature defaults),
    and that default must resolve to the taker's own `BOT_ROW` — a wrong
    default reads every grade under a bucket that is always empty, i.e. a veto
    that can never fire."""
    decisive = _mults({"mult": 0.5, "n": 99})           # keyed by tt.BOT_ROW
    assert "breakoutup" not in si.scored_lens_set({"breakout"}, decisive)
    assert "breakoutup" in si.scored_lens_set({"breakout"}, {})


def test_the_grade_is_read_under_this_bots_own_row():
    """A grade published for a DIFFERENT row must not veto this book."""
    foreign = _mults({"mult": 0.5, "n": 99}, row="some-other-bot-lighter")
    assert "breakoutup" in si.scored_lens_set({"breakout"}, foreign, tt.BOT_ROW)


def test_freshness_is_checked_by_the_caller():
    now = si.now_ts()
    fresh = {"updated": si._iso(now - 60), "ttl_sec": 600,
             "mults": {tt.BOT_ROW: {"long-breakoutup": {"mult": 0.5, "n": 99}}}}
    stale = dict(fresh, updated=si._iso(now - 99999))
    assert si.fresh_stake_mults(fresh, now) == fresh
    assert si.fresh_stake_mults(stale, now) == {}
    # ...and the veto therefore evaporates on a stale payload (fail-OPEN)
    assert "breakoutup" not in si.scored_lens_set(
        {"breakout"}, si.fresh_stake_mults(fresh, now), tt.BOT_ROW)
    assert "breakoutup" in si.scored_lens_set(
        {"breakout"}, si.fresh_stake_mults(stale, now), tt.BOT_ROW)


def test_run_once_checks_freshness_before_passing_the_grade():
    """AST: the payload handed to `scored_lens_set` in run_once must come from
    `fresh_stake_mults`, not straight off a state read — the taker's contract
    is that the CALLER owns freshness, and this is the caller."""
    run = _func("run_once")
    calls = [n for n in ast.walk(run)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "scored_lens_set"]
    # one call is the fail-safe-open default before the tape check (no grade to
    # read yet); the graded call is the one that passes a payload.
    graded = [c for c in calls if len(c.args) >= 2]
    assert len(graded) == 1, (
        f"expected exactly one graded scored_lens_set call, got {len(graded)} "
        f"of {len(calls)}")
    inner = graded[0].args[1]
    assert isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
        and inner.func.id == "fresh_stake_mults", \
        "the brain grade must be freshness-checked at the caller"


def test_the_withheld_raw_read_is_declared_not_silent():
    """THE ONE HALF THIS PASS COULD NOT WIRE, pinned so it cannot rot.

    `tt.breakoutup_self_vetoed` needs the RAW brain stake-mults payload (it
    reads `n`, which `fleet_bus.brain_mults` drops through the clamp), and the
    fleet's raw-read guard requires such a reader to be DECLARED in its own
    `RAW_READ_OK` map — a file this pass did not own. So the read is withheld
    and the consequence is PUBLISHED rather than taken quietly. This test
    fails the moment either half changes, which is the point: closing the gap
    must be a deliberate edit in both places."""
    assert si.BRKUP_VETO_WIRED is False, (
        "if the raw read has been wired, this organ must be listed in the "
        "fleet raw-read guard's RAW_READ_OK — update both together")
    assert si.stake_mults_payload() == {}, "withheld means empty, not junk"
    # the guard that forces the declaration: this module must not name the key
    guard = REPO / "tests/autonomy/test_brain_sizing_reaches_every_book.py"
    assert guard.exists(), "the raw-read guard moved; re-derive this rule"
    raw = si.stake_mults_payload.__doc__ or ""
    assert "withheld" in raw
    # ...and the seam must still run the freshness path, so closing the gap is
    # a one-line body change rather than a rewire
    assert si.fresh_stake_mults(si.stake_mults_payload(), si.now_ts()) == {}


# ---------------------------------------------------------------------------
# 4. LENS_GENE stays a map of lens -> ENTRY GENE
# ---------------------------------------------------------------------------

def test_lens_gene_keeps_exactly_its_four_entry_genes():
    assert set(si.LENS_GENE) == {"breakout", "dip", "momentum", "divergence"}
    assert set(si.LENS_GENE.values()) == {"BRK_RANGE", "DIP_RANGE",
                                          "MOMO_CHG", "DIV_GAP_PP"}
    assert "breakoutup" not in si.LENS_GENE, (
        "breakoutup has no entry gene of its own — it is a relabelled subset "
        "of breakout gated by the same BRK_RANGE bar. Adding it here would "
        "make evolvable_genes drop BRK_RANGE whenever EITHER name is vetoed.")


def test_adding_breakoutup_to_lens_gene_would_over_drop_the_shared_gene():
    """The counterfactual that makes the arm above a claim rather than a
    preference: with breakoutup in the map, a breakoutup-only veto costs the
    breakout lens its gene."""
    genes = dict(si.TAKER_GENES)
    hypothetical = dict(si.LENS_GENE, breakoutup="BRK_RANGE")
    kept, dropped = si.evolvable_genes(genes, {"breakout", "divergence"})
    assert "BRK_RANGE" in kept and "BRK_RANGE" not in dropped

    out, drop = dict(genes), []
    for lens, gene in hypothetical.items():          # evolvable_genes' own loop
        if lens not in {"breakout", "divergence"} and gene in out:
            del out[gene]
            drop.append(gene)
    assert "BRK_RANGE" in drop, (
        "the hypothetical must actually reproduce the over-drop, or it is not "
        "evidence for keeping breakoutup out of LENS_GENE")


# ---------------------------------------------------------------------------
# 5. THE PUBLISHED FUNNEL — driven through a REAL run_once cycle
# ---------------------------------------------------------------------------

class _FakeStore:
    """Minimal bot_pnl_store stand-in. Every read is the DARK/EMPTY case, which
    is the fail-safe-open path the organ documents."""

    def __init__(self, states=None):
        self.saved = {}
        self.states = states or {}

    def load_state_checked(self, key):
        return True, self.states.get(key, {})

    def load_state(self, key):
        return self.states.get(key, {})

    def fetch_paper_trades(self, limit=None):
        return []

    def save_state(self, key, payload):
        self.saved[key] = payload
        return True

    def save_history(self, key, row):
        return True


def run_cycle(monkeypatch, tape, min_gt_closes=None, states=None):
    store = _FakeStore(states)
    monkeypatch.setattr(si, "store", store)
    monkeypatch.setattr(si.rp, "load_tape", lambda source="auto": (tape, "test"))
    monkeypatch.setattr(si.rp, "daily_up_resolver",
                        lambda syms, lo, hi: _always_up)
    monkeypatch.setattr(si, "EXPLORE_N", 6)     # keep the cycle quick
    monkeypatch.setattr(si, "proprio", None)
    if min_gt_closes is not None:
        monkeypatch.setattr(si, "MIN_GT_CLOSES", min_gt_closes)
    payload = si.run_once()
    assert payload is not None
    return store, payload


@pytest.fixture()
def cycle(monkeypatch, tape):
    return run_cycle(monkeypatch, tape)


def test_the_payload_publishes_a_funnel(cycle):
    _store, payload = cycle
    assert "funnel" in payload, (
        "`elite: []` is byte-identical between 'died at a gate' and 'the "
        "surface is negative' — the per-gate counts must be published")
    f = payload["funnel"]
    for k in ("generated", "scored", "closes_ok", "both_halves_pos",
              "enactable", "elite", "champion_why", "bars", "up_resolver",
              "lenses_scored"):
        assert k in f, f"funnel is missing {k}"


def test_the_funnel_counts_are_internally_consistent(cycle):
    _store, payload = cycle
    f = payload["funnel"]
    chain = [f["generated"], f["scored"], f["closes_ok"],
             f["both_halves_pos"], f["enactable"], f["elite"]]
    assert all(isinstance(v, int) and v >= 0 for v in chain), chain
    assert chain == sorted(chain, reverse=True), (
        f"the funnel must be monotone non-increasing down the gates: {chain}")
    assert f["elite"] == len(payload["elite"])
    assert f["elite"] <= f["bars"]["elite_n"]
    assert f["scored"] == f["generated"], "rank() scores the whole population"
    assert f["generated"] > 0
    # EVERY published bar must be the constant the organ actually applies.
    # `elite_n` was found by a surviving mutation: `<= bars["elite_n"]` above
    # stays true when the bar is INFLATED, so a payload that misdescribes the
    # running cap read as healthy — the "a registry that misdescribes the
    # running value is worse than none" shape, in a diagnostic.
    assert f["bars"] == {"min_gt_closes": si.MIN_GT_CLOSES,
                         "half_margin": pytest.approx(si.HALF_MARGIN),
                         "edge_margin": pytest.approx(si.EDGE_MARGIN),
                         "min_closes": si.MIN_CLOSES,
                         "min_tape_hours": pytest.approx(si.MIN_TAPE_HOURS),
                         "elite_n": si.ELITE_N}, f["bars"]
    # the closes gate must actually BITE on this fixture, or the monotone
    # assertion above is satisfied by a chain of equal numbers and proves
    # nothing about the gates
    # EVERY gate must actually BITE on this fixture, or the monotone assertion
    # above is satisfied by a chain of equal numbers and proves nothing.
    assert f["closes_ok"] < f["scored"], (
        f"the closes gate is untested — no genotype falls below it: {f}")
    assert f["both_halves_pos"] < f["closes_ok"], (
        f"the both-halves gate is untested — it drops nobody: {f}")
    assert f["enactable_all"] > f["enactable"], (
        "the enactable count must be taken DOWNSTREAM of the earlier gates; "
        f"it matches the whole-population count, so the chain is not "
        f"cumulative there: {f}")
    assert f["enactable_all"] <= f["scored"] and f["any_closes"] <= f["scored"]


def test_the_funnel_is_cumulative_not_a_row_of_independent_counts(monkeypatch,
                                                                  tape):
    """A funnel whose gates are each computed over the WHOLE population reads
    almost identically to a cumulative one, and is a different claim: it cannot
    say where the population died.

    The discriminator: move ONLY the closes floor. This fixture carries
    genotypes that pass both halves on ~10 closes (a `DIV_GAP_PP` allele that
    refuses the divergence ticket keeps just the breakout book), so a
    CUMULATIVE `both_halves_pos` must move with the floor and an independent
    one cannot."""
    _s, loose = run_cycle(monkeypatch, tape, min_gt_closes=1)
    _s2, tight = run_cycle(monkeypatch, tape, min_gt_closes=12)
    lo, hi = loose["funnel"], tight["funnel"]
    assert lo["scored"] == hi["scored"], "same population, different floor only"
    assert lo["closes_ok"] > hi["closes_ok"], (lo, hi)
    assert lo["both_halves_pos"] > hi["both_halves_pos"], (
        "`both_halves_pos` must be counted DOWNSTREAM of the closes gate; it "
        f"did not move with the floor: {lo} vs {hi}")
    assert lo["enactable"] >= hi["enactable"]


def test_the_funnel_closes_gate_is_the_same_bar_select_elite_applies(monkeypatch,
                                                                     tape):
    """FOUND BY A SURVIVING MUTATION: `>= MIN_GT_CLOSES` -> `> MIN_GT_CLOSES`.

    The funnel's whole job is to say WHERE the population died, and
    `select_elite` admits at `>=`. An off-by-one at the bar misreports exactly
    the boundary genotypes — and it can make `elite` exceed `closes_ok`, which
    breaks the funnel's own monotone claim. The monotone arm above cannot see
    it, because nothing in this fixture sits ON the default floor of 12.

    So the floor is put ON a value the population actually reaches. The organ
    is deterministic (it says so: "Deterministic — no RNG"), which is what
    makes a probe run followed by a measured run a sound comparison, and the
    probe asserts that determinism rather than assuming it."""
    runs = []
    real_rank = si.rank

    def capture(pop, tp, lenses=None, up_resolver=None):
        out = real_rank(pop, tp, lenses, up_resolver=up_resolver)
        runs.append([s["closes"] for s in out])
        return out

    monkeypatch.setattr(si, "rank", capture)
    _s, probe = run_cycle(monkeypatch, tape)
    closes = runs[0]
    assert probe["funnel"]["closes_ok"] == sum(
        1 for c in closes if c >= si.MIN_GT_CLOSES), (
        "the funnel's closes count must be the SAME predicate select_elite "
        f"applies: {probe['funnel']} vs {sorted(closes)}")

    top = max(closes)
    at_top = closes.count(top)
    assert at_top >= 1 and top > si.MIN_GT_CLOSES, sorted(closes)

    _s2, measured = run_cycle(monkeypatch, tape, min_gt_closes=top)
    assert runs[1] == closes, (
        "the population must be deterministic for this comparison to mean "
        "anything")
    assert measured["funnel"]["closes_ok"] == at_top, (
        f"with the floor set exactly ON the population's own maximum close "
        f"count ({top}), the funnel must ADMIT those {at_top} genotypes — the "
        f"bar is `>=`, not `>`; got {measured['funnel']['closes_ok']}")


def test_the_funnel_carries_the_champions_failing_bar(cycle):
    _store, payload = cycle
    f = payload["funnel"]
    assert isinstance(f["champion_why"], str) and f["champion_why"], \
        "assess_champion's reason was printed to stdout and never published"
    assert f["champion_confidence"] in ("none", "tentative", "candidate",
                                        "stable")
    assert isinstance(f["champion_is"], bool)


def test_the_funnel_reports_the_coverage_it_was_scored_under(cycle):
    _store, payload = cycle
    f = payload["funnel"]
    assert f["up_resolver"] is True
    assert f["unreachable_lenses"] == []
    assert "breakoutup" in f["lenses_scored"]
    assert "breakoutup" in payload["lenses_scored"]


def test_a_self_veto_reaches_the_payload(monkeypatch, tape):
    """END-TO-END on the veto side, and the arm that pins `lenses_vetoed` over
    the TAKER's full lens set: `breakoutup` is not in `LENS_GENE`, so the old
    `set(LENS_GENE) - scored` could never report it and a self-veto was
    invisible on the payload.

    The grade is injected through the withheld seam (`stake_mults_payload`)
    rather than the bot_state key, because this organ deliberately does not
    read that key yet — see `test_the_withheld_raw_read_is_declared_not_silent`.
    Injecting here proves the whole path downstream of the read is correct, so
    closing the gap is the one-line change that entry describes."""
    decisive = {"updated": si._iso(si.now_ts() - 60), "ttl_sec": 3600,
                "mults": {tt.BOT_ROW: {"long-breakoutup": {"mult": 0.5,
                                                           "n": 99}}}}
    monkeypatch.setattr(si, "stake_mults_payload", lambda: decisive)
    _s, payload = run_cycle(monkeypatch, tape)
    assert "breakoutup" not in payload["lenses_scored"]
    assert "breakoutup" in payload["lenses_vetoed"], (
        "a decisive self-veto must be REPORTED, not merely applied: "
        f"{payload['lenses_vetoed']}")
    assert "breakoutup" not in payload["funnel"]["lenses_scored"]
    # ...and the veto really did change the fitness basis, not just the label
    assert payload["funnel"]["up_resolver"] is True

    # FAIL-SAFE DIRECTION: the same decisive grade, STALE, must veto nothing —
    # a restrict-only rule read off a dead payload would silence the lens
    # forever with nobody told.
    stale = dict(decisive, updated=si._iso(si.now_ts() - 999999))
    monkeypatch.setattr(si, "stake_mults_payload", lambda: stale)
    _s2, open_payload = run_cycle(monkeypatch, tape)
    assert "breakoutup" in open_payload["lenses_scored"]
    assert "breakoutup" not in open_payload["lenses_vetoed"]


def test_the_funnel_publishes_the_veto_wiring_state(cycle):
    _s, payload = cycle
    state = payload["funnel"]["breakoutup_veto"]
    assert isinstance(state, str) and state
    assert ("unwired" in state) is (si.BRKUP_VETO_WIRED is False), (
        "the published wiring state must track the flag, not a stale string")


def test_a_short_tape_still_publishes_a_funnel(monkeypatch, tape):
    """A payload with no funnel at all is the ambiguity this block closes; a
    cycle that scored nothing must SAY that rather than omit the key."""
    store = _FakeStore()
    monkeypatch.setattr(si, "store", store)
    monkeypatch.setattr(si.rp, "load_tape",
                        lambda source="auto": (tape[:3], "test"))
    monkeypatch.setattr(si, "proprio", None)
    payload = si.run_once()
    assert payload["funnel"]["scored_this_cycle"] is False
    assert payload["funnel"]["why"]
    # ...and the pre-breeding default must be FAIL-SAFE OPEN, `breakoutup`
    # included. Found by a surviving mutation: dropping `scored_lens_set` from
    # that default publishes `breakoutup` under `lenses_vetoed` on every
    # short-tape cycle — a veto nobody applied, reported as if someone had.
    assert "breakoutup" in payload["lenses_scored"], payload["lenses_scored"]
    assert payload["lenses_vetoed"] == [], (
        "a cycle that scored nothing has vetoed nothing: "
        f"{payload['lenses_vetoed']}")


def test_the_funnel_is_json_safe(cycle):
    """I5: a bare NaN/Infinity makes the whole jsonb write fail, so the funnel
    must survive `json_safe(...)` + `allow_nan=False` — the exact call
    `bot_pnl_store.save_state` makes."""
    import json

    import bot_pnl_store as store_mod
    _s, payload = cycle
    json.dumps(store_mod.json_safe(payload["funnel"]), allow_nan=False)


def test_the_cycle_scores_the_breakoutup_book(cycle):
    """End-to-end: the organ's own published leaderboard/champion must be
    computed over a report that CONTAINS the relabelled lens. Without the fix
    this cycle's `lenses_scored` cannot mention it at all."""
    _store, payload = cycle
    assert "breakoutup" in payload["lenses_scored"]
    assert "breakoutup" not in payload["lenses_vetoed"]
    # the fixture's breakoutup book is a winner, so the cycle must find gametes
    assert payload["funnel"]["elite"] > 0, (
        "on a tape whose hidden lens is profitable the population must survive "
        "— elite 0 here is the stillbirth this file exists to catch")


# ---------------------------------------------------------------------------
# 6. THE VETOED REGIME — the only regime where the fix does anything, and the
#    one every cycle test above was missing.
#
# FOUND BY A SURVIVING MUTATION (`rank(..., up_resolver=None)` in run_once,
# which the whole section-5 suite passed). The `cycle` fixture reads a DARK
# brain, so `allowed` is all four lenses and `breakout` is unvetoed — and
# there the two mechanisms are MUTUALLY EXCLUSIVE (this file's own header):
# an up-regime breakout is scored under `breakout` when blind and under
# `breakoutup` when resolved, and BOTH are in the scored set, so the score is
# BYTE-IDENTICAL either way. Measured on this fixture: net 35.0 / closes 25 /
# both_halves True, with the resolver and without it.
#
# In production the brain grades breakout/dip/momentum negative at sample
# size, `allowed` collapses to `{divergence}`, and the SAME tape reads
# resolved +35.0 (25 closes, both halves positive) vs blind -24.6 (15 closes,
# both halves NEGATIVE). That is the whole finding, and no cycle test ran in
# it.
# ---------------------------------------------------------------------------

def _lens_fwd_vetoing_all_but_divergence(now):
    """A `brain-lens-forward` payload in the shape the TAKER reads (v3 episode
    fields), grading breakout/dip/momentum negative at sample size.

    The floors are NOT restated here — `test_the_vetoed_fixture_really_vetoes`
    drives `tt.vetoed_lenses` and asserts the outcome, so this fixture follows
    the taker if its bars ever move instead of silently going vacuous."""
    def bad():
        return {"eps4h": 500, "n_syms": 50, "eavg4h_pct": -0.50,
                "ehit4h": 0.40}

    def good():
        return {"eps4h": 500, "n_syms": 50, "eavg4h_pct": +0.50,
                "ehit4h": 0.55}
    return {"updated": si._iso(now - 60), "ttl_sec": 3600,
            "lenses": {"breakout": bad(), "dip": bad(), "momentum": bad(),
                       "divergence": good()}}


def _vetoed_states():
    return {"brain-lens-forward":
            _lens_fwd_vetoing_all_but_divergence(si.now_ts())}


def test_the_vetoed_fixture_really_vetoes(tape):
    """The positive control. An empty output is not a negative result: if this
    grade stopped vetoing, every arm below would pass vacuously by falling
    back into the dark-brain regime where the resolver cannot matter."""
    lf = si.fresh_lens_fwd(_lens_fwd_vetoing_all_but_divergence(si.now_ts()),
                           si.now_ts())
    assert lf, "the grade must be FRESH or the veto never runs"
    assert tt.vetoed_lenses(lf, realised={}) == {"breakout", "dip", "momentum"}
    assert si.live_lenses(lf, realised={}) == {"divergence"}
    # ...and in that regime the resolver is DECISION-SIZED on this tape
    scored = si.scored_lens_set({"divergence"}, {}, tt.BOT_ROW)
    blind = si.evaluate(DEFAULT_GT, tape, scored)
    seen = si.evaluate(DEFAULT_GT, tape, scored, up_resolver=_always_up)
    assert blind["both_halves_pos"] is False and seen["both_halves_pos"] is True


def test_the_vetoed_regime_cycle_scores_the_hidden_lens(monkeypatch, tape):
    """THE MUTATION KILLER, behavioural half. A cycle in the production lens
    regime must find gametes, because its hidden lens is the profitable one.

    Any reversion that scores the cycle blind — dropping the resolver at the
    `rank()` call, passing `allowed` instead of `scored_lenses`, or unwiring
    `build_up_resolver` — collapses the fitness to the losing `divergence`
    book (net -24.6, both halves negative) and the population dies at the
    both-halves gate. That is the `elite: 0` stillbirth this file exists to
    catch, and section 5's dark-brain cycle cannot see it."""
    _s, payload = run_cycle(monkeypatch, tape, states=_vetoed_states())
    f = payload["funnel"]
    assert sorted(payload["lenses_scored"]) == ["breakoutup", "divergence"], (
        "the vetoed regime must reach the organ: this is the production "
        f"lens set, not the dark-brain one — got {payload['lenses_scored']}")
    assert f["both_halves_pos"] > 0, (
        "no genotype cleared both halves in the vetoed regime — the cycle was "
        f"scored without the breakoutup book: {f}")
    assert f["elite"] > 0, (
        f"elite 0 in the vetoed regime is the stillbirth, not a bar: {f}")
    assert payload["champion"] is not None or f["elite"] > 0


def test_a_blind_cycle_in_the_vetoed_regime_really_does_die(monkeypatch, tape):
    """The CONTROL for the arm above: with the resolver genuinely unavailable
    (the venue's candles are down) the same cycle must die at the gates.

    Without this, `elite > 0` above could be true for reasons having nothing
    to do with coverage, and the killer would not be measuring what it
    claims."""
    def boom(*_a, **_k):
        raise RuntimeError("candles down")

    store = _FakeStore(_vetoed_states())
    monkeypatch.setattr(si, "store", store)
    monkeypatch.setattr(si.rp, "load_tape", lambda source="auto": (tape, "test"))
    monkeypatch.setattr(si.rp, "daily_up_resolver", boom)
    monkeypatch.setattr(si, "EXPLORE_N", 6)
    monkeypatch.setattr(si, "proprio", None)
    payload = si.run_once()
    f = payload["funnel"]
    assert f["up_resolver"] is False, (
        "a dark resolver must be REPORTED as reduced coverage, not assumed")
    assert "breakoutup" in f["unreachable_lenses"]
    assert f["elite"] == 0 and f["both_halves_pos"] == 0, (
        "the blind cycle must die in this regime, or the killer above proves "
        f"nothing about coverage: {f}")
