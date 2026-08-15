"""Policy — the daily review must grade against the CURRENT standard, always.

WHY THIS EXISTS, and it is a two-incident class inside one day (30-Jul):

  1. The go-live gate was re-specified the evening of 29-Jul ((fk)): win rate
     demoted from a bar, `t>=2.0` and both-halves added. `scripts/evidence_review.py`
     carried its OWN copy of the old rule, so the next morning's review
     published ⚖️ Counterweight as CLEARING the gate on WR 56.1% (t=0.65,
     no measured edge) and REJECTED 🌾 carry (t=2.60, the fleet's
     best-evidenced book) on WR 40.2%. Both errors were exactly what the
     re-spec existed to remove.
  2. The FIX for (1) then drifted the same day. It classified a near-miss by
     parsing `grade()`'s prose (`why.startswith("window ")`). Hours later (hl)
     landed `bar_map()` — whose docstring says "published rather than
     re-derived ... prose is exactly what drifts" — and the prose-parser was
     obsolete on arrival.

The operator's framing: *"otherwise we are just reverting every day and wasting
time and money."* A one-off patch is not a fix; the review has to DERIVE its
bars from the canonical grader so that a bar added, renamed or redefined
upstream arrives automatically. These tests fail when it stops doing that.

Each test names the incident it prevents (house convention).
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "scripts" / "evidence_review.py"
GRADER = ROOT / "scripts" / "golive_readiness.py"


@pytest.fixture(scope="module")
def review_src():
    return REVIEW.read_text()


@pytest.fixture(scope="module")
def review_code():
    """The review's EXECUTABLE source — comments and docstrings removed.

    Load-bearing distinction: this file DOCUMENTS both incidents, so it quotes
    the very patterns these tests forbid (`why.startswith("window ")`, the old
    bar sentence). Matching raw text would fail on the documentation and force
    the next reader to delete the explanation to get green — a test that
    punishes writing down why. Strings used in EXPRESSIONS are kept, because a
    hardcoded bar description in the published line is exactly what we must
    still be able to see.
    """
    return _code_without_docs(REVIEW.read_text())


def _code_without_docs(src):
    import ast
    import io
    import tokenize
    # 1. drop comments (tokenize, so a '#' inside a literal is safe)
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            out.append(tok)
    stripped = tokenize.untokenize(out)
    # 2. blank docstrings / bare string statements
    lines = stripped.splitlines()
    tree = ast.parse(stripped)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            for i in range(node.lineno - 1, min(node.end_lineno, len(lines))):
                lines[i] = ""
    return "\n".join(lines)


def _import_both():
    """Import the two modules the way the review itself does."""
    import sys
    for p in (str(ROOT / "scripts"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import evidence_review as er
    import golive_readiness as g
    return er, g


# ---------------------------------------------------------------------------
# 1. The gate is IMPORTED, never restated.
# ---------------------------------------------------------------------------
def test_review_defines_no_gate_constants_of_its_own(review_code):
    """The (fk) incident: a private copy of the rule IS a second rule."""
    offenders = re.findall(r"^\s*(GATE_MIN\w*|GATE_MAX\w*)\s*=", review_code,
                           re.MULTILINE)
    assert not offenders, (
        f"evidence_review re-defines gate constants {offenders} — import them "
        "from golive_readiness instead; two copies drift within a day")


def test_review_imports_the_canonical_grader(review_src):
    """If the import disappears, the review is grading on something else."""
    assert "golive_readiness import" in review_src
    for name in ("stats", "grade", "bar_map", "BAR_NAMES"):
        assert name in review_src, f"the review must consume {name}"


def test_no_stray_win_rate_bar_survives_anywhere_in_the_review(review_code):
    """Win rate is REPORTED, never a bar. 0.55 must not gate anything here."""
    # allow the string in comments/prose describing the OLD rule (the file
    # documents the incident); forbid it in an executable comparison.
    assert not re.search(r"win_rate\s*[<>=]", review_code), \
        "win rate must not appear in a comparison — (fk) demoted it to reported"


# ---------------------------------------------------------------------------
# 2. The bar SET is derived, so upstream changes propagate.
# ---------------------------------------------------------------------------
def test_review_reports_every_canonical_bar_without_being_edited():
    """THE ANTI-DRIFT CONTRACT.

    A bar added or renamed in golive_readiness.BAR_NAMES must reach the
    review's own vocabulary with no edit here. `blocking_bars` is derived from
    `bar_map`, so this holds by construction — this test is what keeps it that
    way if someone re-hardcodes the list.
    """
    er, g = _import_both()
    ungradeable = g.stats([])
    assert er.blocking_bars(ungradeable) == tuple(sorted(g.BAR_NAMES)), (
        "blocking_bars must span exactly the canonical bar set — a hardcoded "
        "list here would silently ignore a new bar")


def test_blocking_bars_follows_a_bar_INJECTED_at_runtime(monkeypatch):
    """The test that actually kills a hardcoded bar list.

    Written after a mutation exposed the gap: replacing `blocking_bars`' derived
    comprehension with a literal 6-name tuple left every other test in this file
    GREEN, because a hardcoded list is indistinguishable from a derived one
    until the canonical set MOVES. So move it here — inject a bar the review has
    never heard of and require the review to report it.

    A derived implementation passes. Any literal list fails, on the day it is
    written rather than on the day upstream changes.
    """
    er, _ = _import_both()
    real = er.bar_map

    def fake(s):
        out = dict(real(s))
        out["a_bar_invented_by_this_test"] = False
        return out

    monkeypatch.setattr(er, "bar_map", fake)
    got = er.blocking_bars(_mk_stats_passing())
    assert "a_bar_invented_by_this_test" in got, (
        "blocking_bars ignored a bar present in bar_map — it is not deriving "
        "the set, so a new upstream bar would be silently dropped")


def _mk_stats_passing():
    _, g = _import_both()
    return g.stats(_mk([0.20, -0.03, -0.03] * 13 + [0.20]), book_usd=1000.0)


def test_review_does_not_hardcode_the_bar_description(review_code):
    """The published gate line must render BAR_NAMES, not a frozen sentence.

    The pre-fix line read ">=30d, >=30 closes, mean>0, t>=2, both halves +,
    maxDD<15%" as a literal — which is a copy of the rule in prose, and would
    keep claiming the old bars after the real ones moved.
    """
    assert ">=30 closes" not in review_code, \
        "the bar list is hardcoded in the published string — join BAR_NAMES"
    assert "BAR_NAMES" in review_code


def test_near_miss_never_parses_prose(review_code):
    """Incident 2: the prose-parser (`why.startswith`) obsolete within hours."""
    assert "startswith(\"window" not in review_code, \
        "near-miss must derive from bar_map, not from grade()'s reason string"


# ---------------------------------------------------------------------------
# 3. Behavioural: the derived predicates agree with the canonical grader.
# ---------------------------------------------------------------------------
def _mk(pcts, span_days=40.0):
    import datetime as dt
    t0 = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)
    step = dt.timedelta(days=span_days / max(1, len(pcts) - 1))
    return [(p, p * 10.0, t0 + i * step) for i, p in enumerate(pcts)]


def test_blocking_bars_agrees_with_grade_on_every_shape():
    """`grade` passing and `blocking_bars` being empty are the same claim."""
    er, g = _import_both()
    shapes = {
        "carry (low WR, real edge)": _mk([0.20, -0.03, -0.03] * 13 + [0.20]),
        "high-WR loser": _mk([0.01] * 34 + [-0.30] * 6),
        "noisy":         _mk([0.05, -0.045] * 20),
        "thin":          _mk([0.02] * 10),
        "lopsided":      _mk([0.05] * 20 + [-0.01] * 20),
        "short window":  _mk([0.01] * 40, span_days=5.0),
    }
    for name, rows in shapes.items():
        s = g.stats(rows, book_usd=1000.0)
        passes = g.grade(s)[0]
        assert bool(passes) is (not er.blocking_bars(s)), (
            f"{name}: grade says {passes} but blocking_bars says "
            f"{er.blocking_bars(s)}")


def test_the_carry_shape_is_admitted_and_the_high_wr_loser_is_not():
    """The (fk) pair, asserted end-to-end through the review's own helper."""
    er, _ = _import_both()
    carry = er.gate_status(_mk([0.20, -0.03, -0.03] * 13 + [0.20]))
    assert carry[0] == "pass", f"carry must clear the current gate: {carry[1]}"
    assert "not a bar" in carry[1], "win rate must be reported as a non-bar"
    tails = er.gate_status(_mk([0.01] * 34 + [-0.30] * 6))
    assert tails[0] == "fail" and "mean" in tails[1], tails[1]


def test_near_miss_requires_the_window_to_be_the_only_outstanding_bar():
    """A book that is ALSO thin is not "N days from ready"."""
    er, _ = _import_both()
    _, _, only_window = er.gate_status(_mk([0.01] * 40, span_days=5.0))
    assert er.near_miss_eta(only_window) is not None
    _, _, thin_and_short = er.gate_status(_mk([0.02] * 10, span_days=5.0))
    assert er.near_miss_eta(thin_and_short) is None


# ---------------------------------------------------------------------------
# 4. The known-limitation disclosure must not silently disappear.
# ---------------------------------------------------------------------------
def test_realised_only_drawdown_caveat_is_stated(review_src):
    """(hl) measured realised DD 9.9-10.7% vs true MTM 15.6-17.4% on 📊 — the
    two definitions disagree about the VERDICT, not just the number. Until the
    MTM series has ~30d the review must say so on every run that names a
    candidate, or a maxdd pass reads as an MTM pass."""
    assert "maxdd caveat" in review_src and "REALISED-only" in review_src, \
        "the realised-vs-MTM drawdown caveat was removed — (hl)"


#: A GOLIVE_* module-level constant OUTSIDE the grader, declared with its
#: reason — the `BORN_DARK_OK` idiom. A silent second threshold is how two code
#: paths come to disagree about who may hold real money; a DECLARED one is a
#: consumer-local bound that does not restate a bar. Declaring is not a
#: loophole: a declared name may still never shadow a name the grader owns.
GOLIVE_CONST_OK = {
    ("lighter_funding_spread_bot.py", "GOLIVE_MAX_AGE_S"):
        "(ia) freshness bound on the CONSUMED golive-readiness payload — how "
        "stale a published verdict may be before the live arm refuses. Not a "
        "bar: the bot reads book['ready'] and re-derives no threshold.",
}


def _golive_consts(py):
    """-> {name} of module-level GOLIVE_<MIN|MAX>* assignments in one file."""
    return set(re.findall(r"^(GOLIVE_(?:MIN|MAX)\w*)\s*=", py.read_text(),
                          re.MULTILINE))


def test_only_the_grader_owns_the_thresholds():
    """One owner for the numbers. If another module grows its own GOLIVE_*
    threshold, promotion decisions can disagree between two code paths.

    INCIDENT (01-Aug). (ia) landed `GOLIVE_MAX_AGE_S` in
    `lighter_funding_spread_bot.py` — a payload-FRESHNESS bound in a consumer,
    not a second copy of a bar — and this guard, which matched on name prefix
    alone, went red on the merge. Green on each branch, red in combination:
    the (hp) signature. A guard that cannot tell a restated bar from a
    consumer-local bound gets weakened or deleted the first time it cries
    wolf, so it now DECLARES the exception (with a reason) instead, and keeps
    failing on anything undeclared.
    """
    owned = _golive_consts(GRADER)
    assert owned, "the grader declares no GOLIVE_<MIN|MAX>* threshold at all"

    undeclared, shadowed = [], []
    for py in sorted(ROOT.glob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
        if py == GRADER:
            continue
        rel = py.name if py.parent == ROOT else f"scripts/{py.name}"
        for name in sorted(_golive_consts(py)):
            # A name the GRADER owns may never be redefined — declared or not.
            if name in owned:
                shadowed.append(f"{rel}:{name}")
            elif (rel, name) not in GOLIVE_CONST_OK:
                undeclared.append(f"{rel}:{name}")

    assert not shadowed, (
        f"these restate a threshold the grader owns {sorted(owned)}: {shadowed}"
        " — import it from scripts.golive_readiness, never re-declare it")
    assert not undeclared, (
        f"undeclared GOLIVE_* constants outside the grader: {undeclared} — "
        "either import the grader's value or add a (file, name) entry to "
        "GOLIVE_CONST_OK saying why it is not a bar")


def test_golive_const_exemptions_are_reasoned_and_live():
    """A declaration buys nothing if the reason is empty or the file is gone —
    the same arm `audit_doctrine_enforcement` (hy) puts on ENFORCED BY."""
    for (rel, name), why in GOLIVE_CONST_OK.items():
        assert len(why) >= 40, f"{rel}:{name} exemption reason is too thin"
        py = ROOT / rel
        assert py.exists(), f"{rel} no longer exists — drop the exemption"
        assert name in _golive_consts(py), (
            f"{rel} no longer defines {name} — drop the stale exemption")


# ---------------------------------------------------------------------------
# 3. The SAMPLE is imported too — not just the rule.
#
# INCIDENT (31-Jul, (hq)). (hn) stopped the review carrying its own copy of the
# go-live RULE. It kept selecting its own ROWS, with no policy-era filter — and
# (hc) had made the era a PRECONDITION sitting in FRONT of the six bars. The
# next morning the review published the fleet's ONLY go-live candidate,
# perps-funding-carry-lshadow, as "5/6 bars, only 'window' outstanding, ~10.5d
# away" on t=2.77 / n=84 / 19.5d, while the canonical grader read the same book
# at n=59 / t=0.33 / 13.3d — three bars short, not one, and wrong in the
# PROMOTIONAL direction on the book nearest real money.
#
# Importing the scoring while re-deriving the sample is (hj)'s "a second copy of
# a rule is a second rule" one layer down: the bars were canonical and the thing
# they were computed over was not.
# ---------------------------------------------------------------------------

def _grader():
    import sys
    for p in (str(ROOT / "scripts"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import golive_readiness
    return golive_readiness


def test_review_imports_the_era_filter_too(review_src):
    """The sample selector is the grader's, exactly as the bars are."""
    assert "era_rows" in review_src, (
        "the review must import golive_readiness.era_rows — grading a book's "
        "WHOLE retained ledger is what published a false ~10.5d go-live ETA "
        "on the fleet's only candidate (hq)")


def test_the_graded_rows_come_from_era_rows_AST(review_src):
    """The CALL SITE, not a substring. `era_rows` could be imported, called,
    and its result thrown away while `gate_status` still received the raw
    fetch — which is precisely the shape of (hq): the era machinery already
    existed and this consumer simply did not route through it.

    AST because a page-wide substring scan is not a structural claim
    (CLAUDE.md doctrine, learned three times in one session).

    Scoped to the PRODUCTION path: `_selftest` legitimately calls `gate_status`
    on synthetic in-memory rows that never came from a ledger and have no bot
    id, so an era filter is meaningless there. Including them would force a
    fake era call in the selftest — a test bending the code to satisfy it.
    """
    import ast
    tree = ast.parse(review_src)

    selftest_nodes = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and "selftest" in fn.name:
            selftest_nodes.update(id(n) for n in ast.walk(fn))

    era_targets, graded_args = set(), []
    for node in ast.walk(tree):
        if id(node) in selftest_nodes:
            continue
        # `rows, rows_all, era_iso = era_rows(...)` -> collect `rows`
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name) and fn.id == "era_rows":
                for tgt in node.targets:
                    elts = tgt.elts if isinstance(tgt, ast.Tuple) else [tgt]
                    if elts and isinstance(elts[0], ast.Name):
                        era_targets.add(elts[0].id)
        # `... = gate_status(rows)` -> collect the argument name
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "gate_status" and node.args
                and isinstance(node.args[0], ast.Name)):
            graded_args.append(node.args[0].id)

    assert era_targets, "no `era_rows(...)` assignment found in the review"
    assert graded_args, "no production `gate_status(<name>)` call site found"
    assert all(a in era_targets for a in graded_args), (
        f"gate_status is graded on {graded_args}, which is not the era-scoped "
        f"list from era_rows ({sorted(era_targets)}) — the review would grade "
        "the book's WHOLE retained ledger, the (hq) defect")


def test_era_scoping_is_LOAD_BEARING_on_the_incident_shape():
    """Functional, not structural: prove the filter changes the VERDICT.

    Reproduces (hq)'s shape — a book whose pre-era record is strong and whose
    in-era record is flat. Pooled it clears the evidence bars; era-scoped it
    does not. A filter that never changed an answer would satisfy every
    structural test above while protecting nothing."""
    from datetime import datetime, timedelta, timezone
    g = _grader()

    bot = "perps-funding-carry-lshadow"          # has a declared POLICY_ERA
    era_ep, era_iso, _ = g.era_epoch_for(bot)
    assert era_ep, "this test needs a book with a declared era"
    boundary = datetime.fromisoformat(era_iso).replace(tzinfo=timezone.utc)

    def quad(pct, opened):
        return (pct, pct * 1000.0, opened + timedelta(hours=1),
                opened.isoformat())

    # 40 strong closes BEFORE the era, 40 flat ones inside it.
    pre = [quad(0.03, boundary - timedelta(days=40 - i)) for i in range(40)]
    post = [quad(0.0001 * (1 if i % 2 else -1), boundary + timedelta(days=i))
            for i in range(40)]

    scoped, all_time, got_iso = g.era_rows(bot, pre + post)
    assert got_iso == era_iso
    assert len(all_time) == 80 and len(scoped) == 40, (
        f"era filter kept {len(scoped)} of 80; it must drop the pre-era half")

    pooled_bars = g.bar_map(g.stats(all_time, book_usd=1000.0))
    scoped_bars = g.bar_map(g.stats(scoped, book_usd=1000.0))
    assert pooled_bars["t"] and pooled_bars["mean"], \
        "fixture is wrong: the POOLED sample must look good"
    assert not scoped_bars["t"], (
        "fixture is wrong: the IN-ERA sample must fail the t bar — that "
        "difference IS the (hq) incident")


def test_era_rows_is_the_only_place_the_grading_loop_filters():
    """`era_rows` must be the function that applies `in_era`. A second inline
    filter in the grading loop is a second policy — which is how the review
    came to hold a different sample from the grader in the first place."""
    src = GRADER.read_text()
    head, _, rest = src.partition("def era_rows(")
    assert rest, "era_rows must exist in golive_readiness"
    body = rest.split("\ndef ", 1)[0]
    assert "in_era(" in body, "era_rows must be the function applying in_era"
    assert "era_rows(bot, quads" in src, (
        "the grading loop must route through era_rows, not filter inline")


def test_the_era_is_reported_beside_the_all_time_count(review_src):
    """An era that hides the sample it discarded is unauditable. The grader
    prints `[era <iso>: N of M closes count]` on every scoped line; the review
    must publish the same, so a reader can see WHICH sample produced an ETA."""
    assert "[era " in review_src and "closes count]" in review_src, (
        "the review must state the era and the all-time count beside it")


# ---------------------------------------------------------------------------
# 5. The REACH ceiling must be rendered against the bound the veto enforces.
#
# INCIDENT (01-Aug). `scan_new_evidence` rendered "<gross> gross vs long budget
# <N>". `gross` is longs+shorts; the enforced veto compares `long_positions`
# to LONG_BUDGET. On the live payload that morning: gross 25, long_positions
# 19, long_budget 20 — the review reported the fleet five longs OVER a cap it
# was one UNDER. Wrong in the ALARMING direction, on the exact ceiling the
# review's own growth section is supposed to watch. The 31-Jul report carried
# the same shape ("21 gross vs long budget 20"), so it had shipped twice
# before anyone compared the two numbers.
#
# Per (hj): built from a payload the PUBLISHER shapes, and asserted on VALUES —
# a hand-written fixture would just re-encode whichever field I happened to
# believe in, and a substring scan is not a structural claim.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def risk_payload():
    """A fleet-risk payload whose counts come from fleet_risk's own code."""
    _import_both()                      # puts ROOT on sys.path
    import fleet_risk as fr

    # 19 longs across 19 distinct symbols + 6 shorts: the live 01-Aug shape,
    # where gross (25) sits ABOVE the long budget (20) and the enforced long
    # count does not. That divergence is the whole point of the test.
    positions = ([(f"bot{i}", f"SYM{i}", "long") for i in range(19)]
                 + [(f"bot{i}", f"SYM{i}", "short") for i in range(6)])
    expo = fr.exposure_concentration(positions)
    long_n, short_n = expo["long_n"], expo["short_n"]
    return fr, {
        "light": max(fr.light_for(long_n, fr.LONG_BUDGET),
                     fr.light_for(short_n, fr.SHORT_BUDGET)),
        "gross": long_n + short_n,
        "long_positions": long_n, "long_budget": fr.LONG_BUDGET,
        "short_positions": short_n, "short_budget": fr.SHORT_BUDGET,
        "fleet_dd_7d": -0.0028, "clip_scale": 1.0,
        "exposure": expo,
    }


def test_risk_line_compares_each_side_to_its_own_budget(risk_payload):
    fr, st = risk_payload
    er, _ = _import_both()
    assert st["gross"] > st["long_budget"] > st["long_positions"], (
        "fixture must reproduce the incident: gross above the long budget "
        "while the enforced long count is below it")
    line = er.risk_line(st)
    assert f"{st['long_positions']}/{st['long_budget']}" in line, (
        f"the enforced long count must be shown against the long budget: {line}")
    assert f"{st['short_positions']}/{st['short_budget']}" in line, (
        f"shorts must be shown against the SHORT budget: {line}")
    assert f"{st['gross']}/{st['long_budget']}" not in line, (
        f"gross must never be rendered against the long budget: {line}")


def test_headroom_is_measured_from_the_enforced_count(risk_payload):
    fr, st = risk_payload
    er, _ = _import_both()
    assert er.long_budget_headroom(st) == st["long_budget"] - st["long_positions"]
    # gross-based arithmetic would have gone negative here; headroom never does
    assert er.long_budget_headroom(st) > 0


def test_headroom_fails_closed_on_an_unreadable_count():
    """A missing count must read as 'cannot say', never as free headroom —
    absence of evidence must not authorise reach ((hs))."""
    er, _ = _import_both()
    for bad in ({}, {"long_positions": None, "long_budget": 20},
                {"long_positions": "x", "long_budget": 20},
                {"long_positions": 3}):
        assert er.long_budget_headroom(bad) is None, bad
    assert er.long_budget_headroom({"long_positions": 25, "long_budget": 20}) == 0


# ---------------------------------------------------------------------------
# 6. Arm drift must distinguish DIFFERENT CODE from a DIFFERENT FILE SET.
#
# (fd), 29-Jul: `build_compute` hashes only the `_BUILD_SHARED` names that
# EXIST in an image, so one source tree stamps different ids in images with
# different COPY sets — `family-lighter-shadow` published a 14-file id against
# the repo's 15-file id and was read as "the deploy never landed". The live
# arms run from their OWN images, so the live-vs-shadow comparison is exactly
# where that hazard lives, and it compared the digest alone until 01-Aug.
# ---------------------------------------------------------------------------
def test_arm_drift_reports_code_drift_when_the_file_counts_match():
    er, _ = _import_both()
    line = er.arm_drift_line("Taker", ("0b30b0a79211", "15"), ("d012822f3ea0", "15"))
    assert "DRIFT" in line, line
    assert "file set" in line.lower(), (
        "a real drift line must say the file counts matched, so the reader "
        "knows the (fd) explanation was ruled out: " + line)


# [2026-08-06] ...but it must NOT assert what the drift MEANS.
#
# This test previously required the string "not a clean control", pinning an
# over-claim: whether differing code changes what a bot DOES is not derivable
# from two build stamps. MEASURED the morning this changed — the two Taker
# arms drifted by (kh) and (ki), neither of which touches
# `lighter_ticket_taker.py`; the diff was `bot_pnl_store.py` and an additive
# `fleet_bus` helper, so the arms' trading logic was byte-identical and the
# control was sound. Same category error (ke) fixed in `head_drift_line` and
# explicitly left open here.
def test_arm_drift_states_the_fact_and_names_the_authority_not_a_verdict():
    er, _ = _import_both()
    line = er.arm_drift_line("Taker", ("0b30b0a79211", "15"), ("d012822f3ea0", "15"))
    assert "not a clean control" not in line, (
        "the consequence is not derivable from stamps — state the fact, name "
        "the authority: " + line)
    assert "audit_code_currency" in line, (
        "a line that refuses the verdict must name who can give it: " + line)
    # (ke)'s own trap: prose ABOUT the class must not trip the ACTION matcher,
    # which keys on the verdict LABEL `BEHIND-OWN:` (with the colon).
    assert "BEHIND-OWN:" not in line, (
        "naming the classifier's verdict with its colon makes the disclaimer "
        "page as the finding — the exact (ke) collision: " + line)
    # it must still SURFACE: removing the false verdict is not the same as
    # hiding a real-money-adjacent fact.
    assert line in er.action_items([line]), (
        "arm drift must still reach the operator: " + line)


def test_arm_drift_does_not_cry_drift_on_a_different_file_set():
    er, _ = _import_both()
    line = er.arm_drift_line("Family", ("74d3b3178fa8", "14"), ("6de64508c304", "15"))
    assert "DRIFT" not in line, f"(fd) file-set difference misreported as drift: {line}"
    assert "FILE SET" in line and "(fd)" in line, line


def test_arm_drift_agrees_and_stays_quiet_when_unstamped():
    er, _ = _import_both()
    agree = er.arm_drift_line("Farmer", ("705425a83422", "15"), ("705425a83422", "15"))
    assert "AGREE" in agree and "DRIFT" not in agree, agree
    # an unstamped arm proves nothing either way — say nothing, never "AGREE"
    assert er.arm_drift_line("X", (None, None), ("abc", "15")) is None
    assert er.arm_drift_line("X", ("abc", "15"), None) is None


# ---------------------------------------------------------------------------
# 7. A ceiling with no attribution cannot be acted on.
#
# The review reported `longs 18/20` while `fleet-risk.by_bot` had carried the
# per-book breakdown all along. Measured 01-Aug once it was surfaced: 100% of
# the long budget was held by books with NO measured claim, a third of it by
# 🌊 crypto-trend-daily, which has never closed a trade — while both LIVE
# real-money books held only shorts and never competed for it at all.
# ---------------------------------------------------------------------------
def _risk_and_alloc():
    """The live 01-Aug shapes, keyed the way each PUBLISHER keys them:
    fleet_risk by BARE base, fleet_allocation by ROW (`-lshadow`)."""
    risk = {"long_positions": 18, "long_budget": 20, "by_bot": {
        "crypto-trend-daily": {"long": 6, "short": 0},
        "freqtrade-mum": {"long": 4, "short": 0},
        "freqtrade-avo-maria": {"long": 4, "short": 0},
        "freqtrade-dad": {"long": 2, "short": 0},
        "crypto-swing-daily": {"long": 2, "short": 0},
        "lighter-ticket-taker": {"long": 0, "short": 3},
        "perps-funding-lighter": {"long": 0, "short": 3},
    }}
    alloc = {"books": {
        "freqtrade-avo-maria-lshadow": {"claim": 0.0, "n": 5},
        "freqtrade-dad-lshadow": {"claim": 0.0, "n": 10},
        "crypto-swing-daily-lshadow": {"claim": 0.0, "n": 1},
    }}
    return risk, alloc


def test_occupancy_ranks_holders_and_excludes_pure_shorts():
    er, _ = _import_both()
    ranked = er.long_budget_occupancy(*_risk_and_alloc(), top=4)
    assert ranked[0][0] == "crypto-trend-daily", ranked
    assert ranked[0][1] == 6 and abs(ranked[0][2] - 6 / 18) < 1e-9, ranked

    # `top` MUST be wide enough that an unfiltered short-only book would show
    # up. A mutation deleting the `if not n_long` guard survived a top=4 check,
    # because five long-holders crowded the shorts out of the window anyway —
    # the assertion was passing for the wrong reason.
    everything = er.long_budget_occupancy(*_risk_and_alloc(), top=99)
    names = [r[0] for r in everything]
    assert len(names) == 5, f"only the five LONG holders may appear: {names}"
    assert "lighter-ticket-taker" not in names and "perps-funding-lighter" not in names, (
        "a book holding only SHORTS does not consume the long budget: " + str(names))
    assert all(r[1] > 0 for r in everything), everything


def test_occupancy_joins_the_claim_across_the_two_key_conventions():
    """fleet_risk keys by bare base, fleet_allocation by row. A join that
    missed this would report every book as unscored — which happens to look
    like the true 01-Aug answer, so it must be pinned on a book that IS
    present in the allocation payload."""
    er, _ = _import_both()
    occ = dict((r[0], r[3]) for r in er.long_budget_occupancy(*_risk_and_alloc(), top=9))
    assert occ["freqtrade-avo-maria"] == 0.0, (
        "the `-lshadow` row key was not joined to the bare base: " + str(occ))
    assert occ["crypto-trend-daily"] is None, (
        "a book ABSENT from the allocation payload must read None, never 0.0 — "
        "'not scored' and 'scored at zero' are different facts")


def test_occupancy_is_quiet_and_safe_on_a_dark_organ():
    er, _ = _import_both()
    risk, _ = _risk_and_alloc()
    assert er.long_budget_occupancy(risk, None)          # dark allocation: still ranks
    assert er.long_budget_occupancy({}, {}) == []
    assert er.long_budget_occupancy(None, None) == []
    # no long_positions -> shares are None, never a ZeroDivisionError
    only = er.long_budget_occupancy({"by_bot": {"a": {"long": 3}}}, {})
    assert only and only[0][2] is None, only


# ---------------------------------------------------------------------------
# 7. THE STAMP MUST SEE THE MODULE THAT STEERS WHAT EVERY BOOK READS.
#
# (mp), 14-Aug: `(lx)` changed `fleet_bus.allocation_scale` — a real change to
# what three funding books stake — and `build_compute` returned the IDENTICAL
# id before and after (`f80d5c78d168`, n=15), because `fleet_bus.py` was not in
# `_BUILD_SHARED`. Stamp readback is the fleet's only accepted proof a deploy
# landed, so a file outside that set is a file whose deploys cannot be proved.
#
# Asserted as BEHAVIOUR, not membership: a membership check stays green if
# somebody keeps the name and breaks the hashing, and it teaches the next
# reader nothing about why the name is there.
# ---------------------------------------------------------------------------
def test_a_fleet_bus_change_moves_the_build_stamp(tmp_path, monkeypatch):
    import bot_pnl_store as b

    root = tmp_path / "img"
    root.mkdir()
    (root / "fleet_bus.py").write_text("MULT_CEIL = 1.5\n")
    (root / "arm.py").write_text("import fleet_bus\n")
    monkeypatch.setattr(b, "_BUILD_ROOT", str(root))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)

    before = b.build_compute(str(root / "arm.py"))
    # the read client changes; the entry module does not
    (root / "fleet_bus.py").write_text("MULT_CEIL = 9.9\n")
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    after = b.build_compute(str(root / "arm.py"))

    assert before[1] == after[1] == 2, (before, after)   # entry + fleet_bus
    assert before[0] != after[0], (
        "a fleet_bus.py change must move the build id — it is the read client "
        "for brain mults, the long-budget veto, allocation_scale and the "
        "per-asset oracle, and drift there changes BOTH arms of a live/shadow "
        "pair with nothing to show for it ((mp))")


def test_an_image_without_fleet_bus_keeps_its_own_stamp(tmp_path, monkeypatch):
    """The other half, and the (fd) trap: a declared-but-ABSENT shared name is
    skipped, so the 11 images that do not COPY fleet_bus.py must not move at
    all. Predicting an image's id from the REPO tree is the mistake (fd)
    documented, and adding a name to the set is exactly when it recurs."""
    import bot_pnl_store as b

    root = tmp_path / "img"
    root.mkdir()
    (root / "arm.py").write_text("SAME = 'bytes'\n")          # no fleet_bus.py
    monkeypatch.setattr(b, "_BUILD_ROOT", str(root))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    lean = b.build_compute(str(root / "arm.py"))

    (root / "fleet_bus.py").write_text("MULT_CEIL = 1.5\n")   # same tree + bus
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    rich = b.build_compute(str(root / "arm.py"))

    assert lean[1] == 1 and rich[1] == 2, (lean, rich)
    assert lean[0] != rich[0], (
        "identical entry bytes in two different FILE SETS must stamp "
        "differently, and the COUNT is what tells a reader which they hold")


# ---------------------------------------------------------------------------
# 8. THE STAMP MUST SEE THE STRATEGY A REAL-MONEY IMAGE TRADES.
#
# (mu), 15-Aug: `Dockerfile.avolive` COPYs `lighter_family_bot.py` — the
# configured SwingDip instance 🙏 Avo Maria LIVE actually trades — and
# `_build_files('lighter_avo_live_bot.py')` did not include it, so a strategy
# edit could deploy to the live book with a byte-identical stamp. Same class
# as (mp), one file closer to the money. Behaviour-pinned like (mp)'s pair:
# a family-bot change must move the id for an image that carries it, and an
# image without it must keep its own id and count ((fd)).
# ---------------------------------------------------------------------------
def test_a_family_strategy_change_moves_the_build_stamp(tmp_path, monkeypatch):
    import bot_pnl_store as b

    root = tmp_path / "img"
    root.mkdir()
    (root / "lighter_family_bot.py").write_text("SWING_DIP = 1\n")
    (root / "arm.py").write_text("import lighter_family_bot\n")
    monkeypatch.setattr(b, "_BUILD_ROOT", str(root))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)

    before = b.build_compute(str(root / "arm.py"))
    (root / "lighter_family_bot.py").write_text("SWING_DIP = 2\n")
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    after = b.build_compute(str(root / "arm.py"))

    assert before[1] == after[1] == 2, (before, after)   # entry + strategy
    assert before[0] != after[0], (
        "a lighter_family_bot.py change must move the build id — it is the "
        "strategy module the LIVE Avo book trades, and a stamp blind to it "
        "cannot prove a live strategy deploy landed ((mu))")


def test_an_image_without_the_family_module_keeps_its_own_stamp(
        tmp_path, monkeypatch):
    """The (fd) half: 24 of 26 images do not COPY lighter_family_bot.py and
    must not move at all when the name joins the set — absent names are
    skipped, and the COUNT tells a reader which file set they hold."""
    import bot_pnl_store as b

    root = tmp_path / "img"
    root.mkdir()
    (root / "arm.py").write_text("SAME = 'bytes'\n")
    monkeypatch.setattr(b, "_BUILD_ROOT", str(root))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    lean = b.build_compute(str(root / "arm.py"))

    (root / "lighter_family_bot.py").write_text("SWING_DIP = 1\n")
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    rich = b.build_compute(str(root / "arm.py"))

    assert lean[1] == 1 and rich[1] == 2, (lean, rich)
    assert lean[0] != rich[0], (
        "identical entry bytes in two different FILE SETS must stamp "
        "differently ((fd))")


# ---------------------------------------------------------------------------
# 9. A FILE THAT IS BOTH THE ENTRY AND A SHARED NAME IS HASHED ONCE — AND THE
#    STAMP DOES NOT DEPEND ON WHO IS ASKING.
#
# (nh), 15-Aug: (mu) put `lighter_family_bot.py` into _BUILD_SHARED while it
# is ALSO the family image's entry module. `_build_files` appended it twice,
# via two different path forms (`abspath(entry)` vs `join(_BUILD_ROOT, name)`)
# — so whether the duplicate materialised depended on the CALLER'S CWD: the
# container counted 15 files, `audit_code_currency`'s per-commit probe counted
# 16, and the audit could never resolve the family rows. It printed UNRESOLVED
# and still exited OK, i.e. the fleet's answer to "which commit is this bot
# running?" was silently missing for the image that carries the live Avo
# strategy module's shadow twin.
# ---------------------------------------------------------------------------
def test_an_entry_that_is_also_shared_is_hashed_once(tmp_path, monkeypatch):
    """THE REAL MECHANISM: the two appends use different path FORMS, so the
    duplicate only materialises when those forms differ — e.g. by a symlink
    (macOS /tmp -> /private/tmp, or a git worktree under a symlinked temp
    dir, which is exactly where audit_code_currency's probe runs)."""
    import os
    import bot_pnl_store as b

    real = tmp_path / "real"
    real.mkdir()
    (real / "entry_shared.py").write_text("S = 1\n")
    link = tmp_path / "link"
    os.symlink(str(real), str(link))          # same files, different path form

    monkeypatch.setattr(b, "_BUILD_ROOT", str(real))
    monkeypatch.setattr(b, "_BUILD_SHARED", ("entry_shared.py",))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)

    # the entry arrives by the SYMLINKED form (what a differently-rooted
    # caller passes); the shared scan finds it by the REAL form
    files = b._build_files(str(link / "entry_shared.py"))
    reals = [os.path.realpath(f) for f in files]
    assert len(reals) == len(set(reals)) == 1, (
        f"entry-as-shared hashed twice via a symlinked path form: {files}")


def test_the_stamp_is_independent_of_the_path_form(tmp_path, monkeypatch):
    """The property the audit relies on: the container (image root) and the
    per-commit probe (temp worktree, often symlinked) must compute the SAME
    stamp, or resolution is impossible and the guard goes silently blind."""
    import os
    import bot_pnl_store as b

    real = tmp_path / "real"
    real.mkdir()
    (real / "entry_shared.py").write_text("S = 1\n")
    (real / "other.py").write_text("O = 1\n")
    link = tmp_path / "link"
    os.symlink(str(real), str(link))

    monkeypatch.setattr(b, "_BUILD_ROOT", str(real))
    monkeypatch.setattr(b, "_BUILD_SHARED", ("other.py", "entry_shared.py"))

    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    direct = b.build_compute(str(real / "entry_shared.py"))
    monkeypatch.setattr(b, "_BUILD_CACHE", None)
    via_link = b.build_compute(str(link / "entry_shared.py"))

    assert direct == via_link, (
        f"the stamp moved with the caller's path form: {direct} vs {via_link}"
        " — audit_code_currency can never resolve such a row (nh)")
