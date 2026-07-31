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


def test_only_the_grader_owns_the_thresholds():
    """One owner for the numbers. If another module grows its own GOLIVE_*
    threshold, promotion decisions can disagree between two code paths."""
    owners = []
    for py in ROOT.glob("*.py"):
        if re.search(r"^GOLIVE_(MIN|MAX)\w*\s*=", py.read_text(), re.MULTILINE):
            owners.append(py.name)
    for py in (ROOT / "scripts").glob("*.py"):
        if re.search(r"^GOLIVE_(MIN|MAX)\w*\s*=", py.read_text(), re.MULTILINE):
            owners.append(f"scripts/{py.name}")
    assert owners == ["scripts/golive_readiness.py"], (
        f"gate thresholds must have exactly ONE owner, found {owners}")


# ---------------------------------------------------------------------------
# 3. The SAMPLE is imported too — not just the rule.
#
# INCIDENT (31-Jul, (hp)). (hn) stopped the review carrying its own copy of the
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
        "on the fleet's only candidate (hp)")


def test_the_graded_rows_come_from_era_rows_AST(review_src):
    """The CALL SITE, not a substring. `era_rows` could be imported, called,
    and its result thrown away while `gate_status` still received the raw
    fetch — which is precisely the shape of (hp): the era machinery already
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
        "the book's WHOLE retained ledger, the (hp) defect")


def test_era_scoping_is_LOAD_BEARING_on_the_incident_shape():
    """Functional, not structural: prove the filter changes the VERDICT.

    Reproduces (hp)'s shape — a book whose pre-era record is strong and whose
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
        "difference IS the (hp) incident")


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
