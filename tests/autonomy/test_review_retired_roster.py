"""[2026-08-16 (ni)] THE DAILY REVIEW WAS GRADING RETIRED BOOKS AS GO-LIVE
CANDIDATES.

THE INCIDENT. `scripts/evidence_review.py` filtered its go-live scan on a
hand-written `RETIRED` frozenset that was last touched at the JULY cut. Under
it the fleet retired twelve more books — 🌊 Tide Rider `(if)`, 🧲 Snap Back
`(jh)`, 📊 Index Rider `(lo)`, the Taker's live arm `(ma)`, 🚀 crypto-breakout-4h
`(mr)`, and the SEVEN-row red-stop slate `(nf)` — and not one of them reached
the list. The 16-Aug review printed the symptom in its own payload: the 🔭 gate
horizon named eight dead books as `unreachable`, the `(gl)` overstating-detector
shape that trains an operator to stop reading a line.

The exposure is the line ABOVE the horizon. That loop's entire purpose is to
announce a book as a REAL-MONEY promotion candidate, and it was scoring corpses:
`pm-gillard-lshadow` carried n=304 — the largest ledger in the scanned set — and
had been retired at t=−1.85 the previous day. Nothing but its own bad numbers
stopped the review nominating a book the operator had just killed.

THE CLASS is `(hj)`'s, and this file is its third instance: a consumer keeping a
private copy of a standard it does not own. `(mo)` moved `DECLARED_LIVE` and
`ROW_ENTRY` in this very file to the one declaration and left `RETIRED` behind —
so the fix is not "update the list", it is "stop having a list".
`cleanup_legacy_bots.LEGACY_BOTS` is canonical: it is the half of CLAUDE.md's
two-half retirement rule that PRUNES the frozen row, and it is what
`golive_readiness` already imports for this exact purpose. Review and grader now
agree about which books are dead as they already agree about the bars `(hj)` and
the era `(hq)`.

MUTATION-VERIFIED — each of these reddens this file:
  1. `RETIRED = _RETIRED_FLOOR`                     (the original bug)
  2. dropping the `|` union, keeping only LEGACY_BOTS with an empty floor
  3. `except` clause returning `frozenset()`        (fail-open = grade everything)
  4. rewriting membership to `any(d in bot for d in RETIRED)` (the bare-name trap)
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))


@pytest.fixture(scope="module")
def review():
    return pytest.importorskip("evidence_review")


@pytest.fixture(scope="module")
def legacy():
    from cleanup_legacy_bots import LEGACY_BOTS
    return frozenset(LEGACY_BOTS)


def test_every_canonically_retired_book_is_excluded(review, legacy):
    """The bug in one assertion: the review's set must cover the canonical one.

    Not "contains the names I remembered" — contains ALL of them, so the NEXT
    retirement needs no edit here and cannot drift the way this one did.
    """
    missing = legacy - review.RETIRED
    assert not missing, (
        f"{len(missing)} canonically-retired book(s) are still fed to the "
        f"go-live scan: {sorted(missing)}. `RETIRED` must derive from "
        "`cleanup_legacy_bots.LEGACY_BOTS`, not restate it.")


@pytest.mark.parametrize("dead", [
    "pm-gillard-lshadow",           # (nf) red-stop slate — n=304, t=-1.85
    "pm-abbott-lshadow",            # (nf)
    "pm-rudd-lshadow",              # (nf)
    "pm-morrison-lshadow",          # (nf)
    "freqtrade-dad-lshadow",        # (nf)
    "crypto-intraday-15m-lshadow",  # (nf)
    "crypto-swing-daily-lshadow",   # (nf)
    "crypto-breakout-4h-lshadow",   # (mr)
    "lighter-ticket-taker-lighter", # (ma) — the Taker's LIVE arm
    "equities-regime-lshadow",      # (lo)
    "lighter-dislocation-lshadow",  # (jh) — the fleet's only significant loser
    "crypto-trend-daily-lshadow",   # (if)
])
def test_named_retirements_cannot_be_nominated(review, dead):
    """Each book this review would have graded on 16-Aug, named individually.

    Parametrised on purpose: a set-difference failure says "12 missing", while
    this says WHICH book and which changelog entry retired it — I8, a detector
    must name the object the operator can act on.
    """
    assert dead in review.RETIRED


@pytest.mark.parametrize("alive", [
    "freqtrade-georgia-lshadow",
    # [2026-08-19] freqtrade-mum-lshadow was here until it was RETIRED (I17
    # no_rate: 0 in-era closes ever, ~2.4 closes/30d). Two living subjects
    # still exercise the trap; the semantics being guarded did not move.
    "freqtrade-avo-maria-lshadow",   # the LIVE pair's control arm
])
def test_the_bare_name_trap_does_not_retire_a_living_book(review, alive, legacy):
    """`LEGACY_BOTS` carries Kraken-era BARE names whose -lshadow twins live.

    `freqtrade-georgia` was retired 14-Jul; `freqtrade-georgia-lshadow` has 118
    closes and is trading now. Membership must stay EXACT-match — a rewrite to
    substring/prefix matching would silently retire three healthy books, one of
    them the control arm of a real-money row, and the go-live scan would go
    quiet about them with no error anywhere.
    """
    bare = alive[: -len("-lshadow")]
    assert bare in legacy, "premise: the bare Kraken name is canonically retired"
    assert alive not in review.RETIRED, (
        f"{alive} is a LIVING book and must never be filtered out of the "
        "go-live scan by its retired bare-name ancestor")


def test_floor_is_a_strict_subset_of_the_canonical_list(review, legacy):
    """The degraded-mode floor must never become a second authority.

    The floor exists only so an unimportable `LEGACY_BOTS` cannot make the scan
    WIDER than it is today (golive_readiness fails open to `set()`; for this
    consumer that is the bug). The moment it carries a name the canonical list
    does not, the two can disagree about a retirement — which is the whole
    failure this entry fixes.
    """
    extra = review._RETIRED_FLOOR - legacy
    assert not extra, (
        f"floor carries non-canonical name(s) {sorted(extra)} — declare them in "
        "cleanup_legacy_bots.LEGACY_BOTS (which also prunes the row) instead")


def test_retired_set_survives_an_unimportable_canonical_list(review):
    """Fail-SOFT, not fail-open: a dead import degrades to the floor.

    A `except: RETIRED = frozenset()` would restore the original bug in its
    worst form — every retired book graded — while the report still looked
    clean. Asserted by construction: the floor is non-empty and contained.
    """
    assert review._RETIRED_FLOOR, "floor must be non-empty to be a floor"
    assert review._RETIRED_FLOOR <= review.RETIRED


def test_retired_is_only_ever_used_as_exact_membership():
    """AST, not substring: pin HOW the filter matches, not just what it holds.

    Written because the first cut of this file did NOT catch it. Mutating the
    go-live guard to `any(d in bot for d in RETIRED)` left every other test in
    here green — the set contents are identical, only the matching semantics
    move — and that mutant silently drops `freqtrade-georgia-lshadow` and
    `freqtrade-avo-maria-lshadow` out of the scan, because `LEGACY_BOTS`
    carries their retired Kraken-era BARE names. Living books, one of them the
    live pair's control arm, would stop being graded with no error raised
    anywhere. A set-contents assertion cannot see
    that; only the call site can. ("A substring test is not a wiring test.")

    The contract: every read of `RETIRED` outside its own assignment must be
    the right-hand side of an `in` / `not in` comparison. Iterating it — in a
    comprehension, a loop, or a call — is the failure.
    """
    import ast

    src_path = os.path.join(ROOT, "scripts", "evidence_review.py")
    with open(src_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=src_path)

    # Every Name node that READS `RETIRED` (Store contexts are the definition).
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Name) and n.id == "RETIRED"
             and isinstance(n.ctx, ast.Load)]
    assert reads, "no read of RETIRED found — has the go-live filter moved?"

    # Collect the ones that sit where they should: `<x> in RETIRED`.
    ok = set()
    for cmp_node in ast.walk(tree):
        if not isinstance(cmp_node, ast.Compare):
            continue
        for op, comparator in zip(cmp_node.ops, cmp_node.comparators):
            if (isinstance(op, (ast.In, ast.NotIn))
                    and isinstance(comparator, ast.Name)
                    and comparator.id == "RETIRED"):
                ok.add(id(comparator))

    bad = [n for n in reads if id(n) not in ok]
    assert not bad, (
        "RETIRED is read at line(s) "
        f"{sorted(n.lineno for n in bad)} somewhere other than the right-hand "
        "side of an `in` test. Membership must stay EXACT-match: iterating the "
        "set (e.g. `any(d in bot for d in RETIRED)`) makes a retired BARE name "
        "swallow its living -lshadow twin.")


def test_script_selftest_still_passes():
    """The in-script `--selftest` carries the same contract; keep it green."""
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "evidence_review.py"),
         "--selftest"],
        capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"selftest failed:\n{r.stdout}\n{r.stderr}"
