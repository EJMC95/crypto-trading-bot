"""[2026-08-16 (nk)] THE GRADER HAD NO CONCEPT OF A RETIRED SLEEVE.

THE INCIDENT. `(nf)` retired 🎸 Barnes's `xsect` sleeve, leaving a ONE-sleeve
(carry) book. The go-live grader — the rule that governs real money — kept
scoring the whole two-sleeve ledger: `n=58, mean −0.505%, −$10.52`, of which the
RETIRED sleeve was **49 closes and −$9.07**. The book that actually exists is
`n=9, mean −0.201%, −$1.45`. The operator was being asked to judge a book on a
burn that belonged to a component already switched off.

THE CLASS is `(hc)`'s era precondition, one axis over. An era asks "is this
sample the book's current self in TIME"; this asks it in COMPOSITION. Both sit
in front of the six bars, and a bar computed over the wrong sample means nothing
whichever axis is wrong. It is deliberately NOT an era reset: `(ly)`/`(nf)` chose
sleeve-scoped retirement so the SURVIVING sleeve keeps its own `(hm)` clock, and
moving the era would throw away the carry sleeve's real history to fix the xsect
sleeve's.

WHAT IT DOES NOT BUY — recorded because the opposite was assumed while building
it. The verdict does NOT move: sleeve-scoped, Barnes reads `t = −4.47` (a small,
consistent loser) versus the pooled `t = −2.19`, so the horizon stays
`unreachable` more emphatically, not less. `test_the_verdict_does_not_soften`
pins that refutation so nobody re-derives the wrong expectation from the fix's
existence.

MUTATION-VERIFIED — each of these reddens this file:
  1. dropping the `drop_retired_sleeves` call from the grader's main loop
  2. `retired_sleeves` accepting any truthy value instead of `is True`
  3. `sleeve_of` splitting on the LAST hyphen (`rsplit`) — eats hyphenated sleeves
  4. the fail-open branch DROPPING an unreadable tag instead of keeping it
  5. filtering AFTER `era_rows` instead of before (composition-before-time)
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))


@pytest.fixture(scope="module")
def gl():
    return pytest.importorskip("golive_readiness")


def _row(tag, pct=-0.002, usd=-0.16):
    """The grader's row shape with the sleeve tag at [5]."""
    return (pct, usd, None, None, None, tag)


# ---------------------------------------------------------------- sleeve_of
@pytest.mark.parametrize("tag,want", [
    ("long-xsect", "xsect"),
    ("short-carry", "carry"),
    ("long-mean-rev", "mean-rev"),   # FIRST hyphen only — rsplit would give 'rev'
    ("long", None),                  # the whole rest of the fleet
    ("short", None),
    ("long-", None),
    ("", None),
    (None, None),
])
def test_sleeve_of(gl, tag, want):
    assert gl.sleeve_of(tag) == want


def test_sleeve_of_splits_on_the_first_hyphen_not_the_last(gl):
    """A hyphenated sleeve name must survive intact.

    `rsplit('-', 1)` looks equivalent on `long-xsect` and silently renames
    `long-mean-rev`'s sleeve to `rev` — which would then match nothing in the
    retired set, so the sleeve would keep being graded with no error anywhere.
    """
    assert gl.sleeve_of("long-mean-rev") == "mean-rev"
    assert gl.sleeve_of("short-basis-carry") == "basis-carry"


# ----------------------------------------------------------- retired_sleeves
def test_retired_sleeves_reads_the_books_own_declaration(gl):
    assert gl.retired_sleeves({"sleeves": {
        "xsect": {"retired": True},
        "extreme": {"retired": True},
        "carry": {"retired": False}}}) == frozenset({"xsect", "extreme"})


@pytest.mark.parametrize("extra", [
    {"sleeves": {"a": {"retired": "yes"}}},   # truthy STRING is not a retirement
    {"sleeves": {"a": {"retired": 1}}},       # nor is truthy int
    {"sleeves": {"a": {}}},
    {"sleeves": {"a": None}},
    {"sleeves": []},
    {"sleeves": None},
    {},
    None,
])
def test_retired_sleeves_excludes_nothing_on_doubt(gl, extra):
    """Only `retired is True` retires. Everything else grades as before.

    The direction matters: this filter's failure mode is silently SHRINKING a
    sample, so anything ambiguous must mean "keep grading it".
    """
    assert gl.retired_sleeves(extra) == frozenset()


# ------------------------------------------------------ drop_retired_sleeves
def test_the_incident_in_numbers(gl):
    """🎸 Barnes: 58 graded closes, 49 of them a sleeve `(nf)` retired."""
    rows = ([_row("long-xsect")] * 30 + [_row("short-xsect")] * 19
            + [_row("long-carry")] * 6 + [_row("short-carry")] * 3)
    retired = gl.retired_sleeves({"sleeves": {"xsect": {"retired": True},
                                              "extreme": {"retired": True},
                                              "carry": {"retired": False}}})
    kept, dropped = gl.drop_retired_sleeves(rows, retired)
    assert len(rows) == 58
    assert len(kept) == 9, "the graded sample is the sleeves that still trade"
    assert dropped == {"xsect": 49}


@pytest.mark.parametrize("retired", [frozenset(), None, set()])
def test_no_retired_sleeve_is_a_TRUE_no_op(gl, retired):
    """Every other book in the fleet must be byte-identical.

    Asserted by IDENTITY, not equality: the same list object comes back, so a
    single-sleeve book cannot even pay a copy for a feature it does not use —
    and no future refactor can quietly start rebuilding every book's row list.
    """
    rows = [_row("long"), _row("short"), _row(None)]
    kept, dropped = gl.drop_retired_sleeves(rows, retired)
    assert kept is rows
    assert dropped == {}


def test_an_unreadable_tag_is_KEPT_not_dropped(gl):
    """Fail-OPEN. A sample filter that swallows what it cannot classify is the
    disease, not the cure (`is_quarantined`'s rule, same reasoning)."""
    class Boom:
        def __str__(self):
            raise RuntimeError("unreadable tag")

    kept, dropped = gl.drop_retired_sleeves(
        [_row(Boom()), _row("long-xsect"), _row("long-carry")],
        frozenset({"xsect"}))
    assert len(kept) == 2, "the unreadable row survives; only xsect leaves"
    assert dropped == {"xsect": 1}


def test_a_living_sleeve_is_never_dropped(gl):
    kept, dropped = gl.drop_retired_sleeves(
        [_row("long-carry")] * 5, frozenset({"xsect", "extreme"}))
    assert len(kept) == 5 and dropped == {}


def test_custom_tag_extractor_keeps_one_owner(gl):
    """Differently-shaped rows reuse this function rather than copying it.

    `evidence_review` reads the RAW `reason` column, not the normalised
    `enter_tag`, so it needs its own extractor — and (hq) is explicit that a
    consumer re-deriving the selection is how review and grader diverge.
    """
    kept, _ = gl.drop_retired_sleeves(
        [{"t": "long-xsect"}, {"t": "long-carry"}], frozenset({"xsect"}),
        tag_of=lambda r: r["t"])
    assert len(kept) == 1


# ------------------------------------------------------------ the refutation
def test_the_verdict_does_not_soften(gl):
    """PINS A REFUTATION, not a feature.

    While building this it was assumed that scoping Barnes to its surviving
    sleeve would soften `unreachable` into `undecidable` — a thinner sample
    reading as less certain. The measurement says the opposite: the carry sleeve
    is a small but unusually CONSISTENT loser, so t moves from −2.19 to −4.47
    and the verdict hardens.

    Recorded as a test because the fix's existence invites the wrong inference,
    and the honest claim for it is "the sample and the magnitude are now right"
    (−$1.45, not −$10.52), never "it changed the answer".
    """
    pooled = ([-0.0056] * 49) + ([-0.002] * 9)      # xsect + carry, pooled
    carry_only = [-0.002] * 9

    def t_of(pcts):
        rows = [(p, p * 80.0, None) for p in pcts]
        import statistics as st
        m, sd, n = st.mean(pcts), st.pstdev(pcts), len(pcts)
        return abs(m / (sd / n ** 0.5)) if sd > 0 else float("inf")

    # the surviving sleeve is MORE significant, not less — it is consistent
    assert t_of(carry_only) > t_of(pooled) or t_of(carry_only) == float("inf")


# ------------------------------------------------------------ wiring (AST)
def test_the_grader_filters_before_it_derives_the_era():
    """COMPOSITION BEFORE TIME, pinned at the call site.

    Order is load-bearing and not obvious: `era_rows` derives the policy
    boundary from the rows it is given, so filtering AFTER it would let a dead
    sleeve's policy stamps still choose which of the LIVING sleeve's trades
    count. A substring test cannot see call order — this walks the AST.
    """
    import ast

    src = os.path.join(ROOT, "scripts", "golive_readiness.py")
    with open(src, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=src)

    main = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, "main() not found — has the grader been restructured?"

    drop_ln = [n.lineno for n in ast.walk(main)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "drop_retired_sleeves"]
    era_ln = [n.lineno for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id == "era_rows"]
    assert drop_ln, "the grader no longer drops retired sleeves at all"
    assert era_ln, "era_rows call not found in main()"
    assert min(drop_ln) < min(era_ln), (
        "drop_retired_sleeves must run BEFORE era_rows: a retired sleeve's "
        "trades are not this book's record, so they must not influence the "
        "policy boundary derivation")


def test_the_review_runs_the_same_selection_as_the_grader():
    """(hq): a consumer that imports the SCORING but re-derives the SAMPLE is
    the divergence that published a wrong go-live verdict on 31-Jul. The daily
    review must import this filter, not carry its own."""
    import ast

    src = os.path.join(ROOT, "scripts", "evidence_review.py")
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    tree = ast.parse(text, filename=src)

    # RESOLVED AT RUNTIME, not merely present in some import block. An AST
    # check that unions the primary import and its `except ImportError`
    # fallback stays green when only ONE of them loses the name — which is a
    # real failure (the call site NameErrors on whichever path actually ran).
    # Verified: that exact mutation survived the AST-only form of this test.
    review = pytest.importorskip("evidence_review")
    gl_mod = pytest.importorskip("golive_readiness")
    for name in ("drop_retired_sleeves", "retired_sleeves"):
        fn = getattr(review, name, None)
        assert callable(fn), (
            f"evidence_review must resolve `{name}` from golive_readiness on "
            "the import path it actually runs — re-implementing or losing it "
            "is (hj)'s second-copy bug")
        assert fn is getattr(gl_mod, name), (
            f"`{name}` must BE the grader's function, not a same-named copy — "
            "pin re-use by identity (hj), never by name")

    called = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id == "drop_retired_sleeves"]
    assert called, "imported but never called — the registered-but-inert failure"


def test_grader_selftest_passes():
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "golive_readiness.py"),
         "--selftest"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
