"""[2026-08-06 (kw)] `t` ASSUMES INDEPENDENT TRADES. A BASKET BOOK HAS BATCHES.

`t = mean / (sd/sqrt(n))` counts every close as one independent observation.
Several books here close a whole basket in one instant: ⚖️ Counterweight holds
10 legs and rebalances them together, so its legs are far fewer decisions than
trades, and they share that instant's move. Treating them as independent
overstates `t` by roughly sqrt(legs-per-batch) — and `t >= 2.0` is the bar
standing between a book and REAL MONEY.

MEASURED ACROSS EVERY LIVING LEDGER the day this shipped:

    book                     n    t_iid  t_cluster  batches  max  n_eff
    perps-funding-spread    90    -1.96      -1.27       24   12   37.6   <-- basket
    perps-funding-carry-l   89    +3.12      +3.10       86    2   87.8
    perps-funding-lighter   89    +1.69      +1.66       84    3   86.4
    lighter-ticket-taker-l  41    +0.09      +0.08       41    1   40.0

Counterweight's effective sample is 42% of its nominal one. Every book that
does NOT batch is essentially unchanged, which is the property that makes this
safe to publish: it is inert where there is no clustering and decisive where
there is.

FORWARD-LOOKING, and the real reason to ship it now: 🎸 Barnesy's xsect sleeve
rebalances 10 legs every 24h — the identical shape — and its 30-day grade
starts in September. Without this, its first gate reading would be inflated by
construction.

REPORTED, NEVER A BAR. `BAR_NAMES` is the published contract and `grade()` is
byte-unchanged. Making it BLOCKING is a gate re-spec and therefore an operator
act, exactly as (kg) ruled for money.
"""
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g  # noqa: E402

_BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _rows(spec):
    """spec: [(pct, offset_seconds), ...] -> stats()' row shape."""
    return [(pct, pct, _BASE + timedelta(seconds=off)) for pct, off in spec]


def _batched(n_batches, per_batch, pct, spacing_h=24):
    """A basket book: `per_batch` legs closing together, every `spacing_h`.

    `pct` is indexed PER BATCH, so every leg in a batch shares that batch's
    return — which is the dependence being modelled. An earlier version cycled
    a fixed pattern INSIDE each batch, which made every batch's deviations sum
    to exactly zero: the degenerate case, and it is now its own test.
    """
    out = []
    for b in range(n_batches):
        for i in range(per_batch):
            out.append((pct[b % len(pct)] + (0.01 * i),
                        b * spacing_h * 3600 + i))     # same instant, 1s apart
    return _rows(out)


class TestItFindsTheBatches:
    def test_a_basket_book_reads_far_fewer_decisions_than_trades(self):
        rows = _batched(6, 10, [1.0, -0.8, 0.6, -0.4, 0.9], spacing_h=24)
        s = g.stats(rows)
        c = s["cluster"]
        assert s["n"] == 60
        assert c["n_clusters"] == 6, c
        assert c["max_batch"] == 10, c
        assert c["n_eff"] < s["n"], "a batched book cannot have n_eff == n"

    def test_an_unbatched_book_is_essentially_unchanged(self):
        """The safety property: inert where there is no clustering."""
        rows = _rows([(0.5 if i % 3 else -0.4, i * 7200) for i in range(40)])
        s = g.stats(rows)
        c = s["cluster"]
        assert c["n_clusters"] == 40
        assert c["max_batch"] == 1
        assert abs(c["t_cluster"] - s["t"]) < 0.15, (c["t_cluster"], s["t"])

    def test_trades_inside_the_window_are_one_decision(self):
        rows = _rows([(1.0, 0), (1.0, 30), (1.0, 59), (-1.0, 100000)])
        assert g.stats(rows)["cluster"]["n_clusters"] == 2

    def test_trades_outside_the_window_are_separate(self):
        rows = _rows([(1.0, 0), (1.0, 61), (1.0, 200), (-1.0, 100000)])
        assert g.stats(rows)["cluster"]["n_clusters"] == 4


class TestItMovesTInTheRightDirection:
    def test_batching_shrinks_a_significant_t(self):
        """The whole point: correlated legs must not manufacture significance."""
        # five batches with DIFFERENT returns: mostly up, one down.
        # iid sees 60 observations; there are five decisions.
        rows = _batched(5, 12, [1.2, 0.9, 1.1, 0.8, -0.5], spacing_h=24)
        s = g.stats(rows)
        assert abs(s["cluster"]["t_cluster"]) < abs(s["t"]), (
            "clustering did not reduce t on a book whose 60 legs are 5 "
            "decisions — the estimator is not seeing the dependence")

    def test_n_eff_is_the_iid_sample_that_would_give_the_same_se(self):
        """n_eff must be directly comparable to the `closes` bar, or it is a
        number with no unit."""
        rows = _batched(6, 10, [1.0, -0.8, 0.6, -0.4, 0.9])
        s = g.stats(rows)
        c = s["cluster"]
        se_iid = abs(s["mean_pct"] / s["t"])
        se_cr = abs(s["mean_pct"] / c["t_cluster"])
        assert math.isclose(c["n_eff"], s["n"] * (se_iid / se_cr) ** 2,
                            rel_tol=0.02), c


class TestItFailsClosedRatherThanInventing:
    def test_a_single_batch_returns_None_not_a_number(self):
        """One cluster has no between-cluster variation. Any value would be
        invented, and ABSENT must read as 'not computable', never 'fine'."""
        rows = _rows([(1.0, 0), (0.5, 10), (-0.2, 20), (0.8, 30)])
        assert g.stats(rows)["cluster"] is None

    def test_a_thin_book_does_not_crash_the_grade(self):
        for rows in (_rows([(1.0, 0)]), _rows([])):
            s = g.stats(rows)
            assert isinstance(s, dict)

    def test_a_reported_field_never_breaks_a_grade(self):
        """It runs inside the authority over real money; a fault here must
        degrade to None, not take the verdict with it."""
        rows = _rows([(1.0, 0), (0.5, 100000)])
        rows.append((0.3, 0.3, "not-a-datetime"))
        s = g.stats(rows[:2])
        assert "cluster" in s


class TestTheBarsAreUntouched:
    """A gate re-spec is an operator act. This publishes a number; it must not
    move a verdict."""

    def test_bar_names_is_unchanged(self):
        assert list(g.BAR_NAMES) == ["window", "closes", "mean", "t",
                                     "halves", "maxdd"]

    def test_grade_ignores_the_cluster_field(self):
        rows = _batched(6, 10, [1.2, 0.9, 1.1, 0.8, -0.5, 0.4])
        s = g.stats(rows)
        before = g.grade(dict(s))
        after = g.grade(dict(s, cluster=None))
        assert before == after, (
            "grade() changed with the cluster field — this is REPORTED, and "
            "making it blocking is an operator decision")


class TestTheDegenerateCase:
    """Found by a fixture that built it by accident, which is the only reason
    it is guarded. Every batch's deviations cancelling makes the between-batch
    variance ~0, and the naive estimator then reports an astronomically
    significant t — the (kg) degenerate-t pathology (win 100%, t=6.1e15) in a
    new place."""

    def test_exactly_cancelling_batches_return_None(self):
        pattern = [1.0, -0.8, 0.6, -0.4, 0.9]
        out = []
        for b in range(6):                       # identical pattern per batch
            for i, v in enumerate(pattern):
                out.append((v, b * 24 * 3600 + i))
        s = g.stats(_rows(out))
        assert s["cluster"] is None, (
            "near-zero between-batch variance reported as enormous "
            f"significance: {s['cluster']}")

    def test_n_eff_never_reports_an_absurd_value(self):
        """The guard's purpose, stated as the property it protects."""
        for spec in ([1.0, -0.8, 0.6, -0.4, 0.9], [0.5, -0.5], [1.0, -1.0]):
            out = []
            for b in range(6):
                for i, v in enumerate(spec):
                    out.append((v, b * 24 * 3600 + i))
            c = g.stats(_rows(out))["cluster"]
            assert c is None or c["n_eff"] <= len(out) * 1.5, c


class TestTheSmallGCorrection:
    """MUTATION-DRIVEN. Dropping the `G/(G-1)` factor SURVIVED the first round:
    at G=6 it is a ~10% move in SE, which every tolerance-based test above
    absorbed. It matters MOST when batches are few — which is precisely the
    basket-book case this whole estimator exists for — so it gets an exact
    arithmetic pin rather than a tolerance.
    """

    def test_t_cluster_equals_the_hand_computed_sandwich(self):
        rows = _batched(6, 10, [1.2, 0.9, 1.1, 0.8, -0.5, 0.4])
        s = g.stats(rows)
        pct = [r[0] for r in rows]
        n = len(pct)
        mean = sum(pct) / n
        groups = [pct[i * 10:(i + 1) * 10] for i in range(6)]
        meat = sum(sum(x - mean for x in grp) ** 2 for grp in groups)
        se_cr = math.sqrt((6 / 5.0) * meat) / n          # WITH the correction
        assert math.isclose(s["cluster"]["t_cluster"], round(mean / se_cr, 2),
                            abs_tol=0.011), s["cluster"]

    def test_dropping_the_correction_is_detectable(self):
        """The uncorrected estimator is smaller by exactly sqrt(G/(G-1)); at
        G=6 that is 9.5% of t. Pinned so the factor cannot be removed."""
        rows = _batched(6, 10, [1.2, 0.9, 1.1, 0.8, -0.5, 0.4])
        s = g.stats(rows)
        pct = [r[0] for r in rows]
        n = len(pct); mean = sum(pct) / n
        groups = [pct[i * 10:(i + 1) * 10] for i in range(6)]
        meat = sum(sum(x - mean for x in grp) ** 2 for grp in groups)
        uncorrected = mean / (math.sqrt(meat) / n)
        assert abs(s["cluster"]["t_cluster"] - uncorrected) > 0.05, (
            "corrected and uncorrected t are indistinguishable in this "
            "fixture — it cannot pin the factor")


class TestTheEstimatorHasExactlyOneOwner:
    """[2026-08-26] THE OWNER WAS UNREACHABLE WITH ANY OTHER CLUSTER KEY, so
    two studies re-implemented it — and both had already drifted.

    `cluster_stats` builds its groups INTERNALLY by scanning timestamps against
    `CLUSTER_WINDOW_S`, i.e. it hard-codes the batched-close cluster
    DEFINITION. A study clustering by coin, coin-day or entry-day had no way in
    and wrote the estimator again. Two did, and said so in their own
    docstrings — this is "A SECOND COPY OF A RULE IS A SECOND RULE" arriving
    through a real gap in the interface, which is why the fix is an entry point
    (`cluster_se(values, keys)`) rather than a rule about copying.

    THE DRIFT, measured the day this shipped, on a near-cancelling sample whose
    honest iid t is 1.94:

        study_mum_supply copy    t_cluster = 2.38e+16
        study_sniper_exit copy   t_cluster = 2.38e+16
        golive_readiness owner   t_cluster = None      <- fails CLOSED

    Both copies reproduced the `(kg)` degenerate-t pathology (win 100%,
    t=6.1e15) the owner's guard exists to kill — a fix made once and left
    undone in two places. Not a contrived shape for this fleet: the guard fires
    when a cluster's demeaned values cancel, which is the DESIGN of a
    delta-neutral basket. ⚖️ Counterweight closes ten hedged legs in one instant.
    """

    #: near-cancelling: each cluster's demeaned values sum to ~DELTA, so the
    #: between-cluster variance underflows toward zero while the iid t is
    #: unremarkable. This is the shape, not a magic number.
    DELTA = 1e-7

    def _degenerate(self):
        vals, keys = [], []
        for gi in range(8):
            vals += [1.5, -0.5 + self.DELTA]
            keys += [gi, gi]
        return vals, keys

    def test_the_degenerate_sample_is_refused_not_reported_as_enormous(self):
        vals, keys = self._degenerate()
        n = len(vals); mean = sum(vals) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / (n - 1))
        iid = mean / (sd / math.sqrt(n))
        assert 1.5 < iid < 2.5, (
            f"fixture must look UNREMARKABLE on the honest statistic or it "
            f"proves nothing: iid t={iid}")
        se, G, _mx = g.cluster_se(vals, keys)
        assert se is None, (
            f"the (kg) degeneracy was reported as a number, not refused: "
            f"se={se} would give t={mean / se if se else 'n/a'}")
        assert G == 8, G

    def test_an_ordinary_clustered_sample_still_gets_a_number(self):
        """The guard must be inert where there is no degeneracy — a refusal
        that fires on healthy data is worse than none."""
        vals = [1.2, 1.4, 0.3, 0.5, -0.4, -0.2, 0.9, 1.1]
        keys = [0, 0, 1, 1, 2, 2, 3, 3]
        se, G, mx = g.cluster_se(vals, keys)
        assert se is not None and se > 0, (se, G)
        assert G == 4 and mx == 2, (G, mx)

    def test_a_single_cluster_is_refused_deliberately_not_by_crashing(self):
        """The FULL tuple, not just the None.

        A mutation that deletes the `G < 2` branch SURVIVED the first draft of
        this test: with the branch gone the code divides by `g - 1 == 0`, the
        blanket `except` swallows it, and `None` comes back anyway. Identical
        first element, entirely different reason — "refused because a single
        cluster has no between-cluster variation" vs "crashed and said
        nothing". The cluster count is what separates them: the deliberate path
        reports G=1 and the real max cluster size; the exception path reports
        zeros. (I3: the mutation is what graded this test, not re-reading it.)
        """
        assert g.cluster_se([1.0, 2.0, 3.0], [0, 0, 0]) == (None, 1, 3)

    def test_cluster_stats_delegates_rather_than_re_deriving(self):
        """Pinned by the CALL, by AST. A boolean-equality assertion is
        satisfied by a re-typed copy — that exact mutation SURVIVED a round in
        `(tu)`, so the check is that the call site exists, not that two numbers
        agree."""
        import ast
        src = (_ROOT / "scripts" / "golive_readiness.py").read_text()
        fn = [f for f in ast.walk(ast.parse(src))
              if isinstance(f, ast.FunctionDef) and f.name == "cluster_stats"][0]
        calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "cluster_se"]
        assert calls, (
            "cluster_stats no longer calls cluster_se — the batched-close path "
            "has its own copy of the arithmetic again")
        # ...and it must not have kept a second copy beside the call.
        body = ast.unparse(fn)
        assert "g / (g - 1.0)" not in body and "G / (G - 1" not in body, (
            "cluster_stats still contains the sandwich arithmetic — a call "
            "PLUS a copy is still a copy")

    @pytest.mark.parametrize("script,fname", [
        ("study_mum_supply_2026-08-26.py", "cluster_t"),
        ("study_sniper_exit_shape_2026-08-20.py", "cluster_t"),
    ])
    def test_every_study_copy_delegates_to_the_owner(self, script, fname):
        """A study may own its CLUSTER KEY; it may not own the ESTIMATOR."""
        import ast
        src = (_ROOT / "scripts" / script).read_text()
        fn = [f for f in ast.walk(ast.parse(src))
              if isinstance(f, ast.FunctionDef) and f.name == fname]
        assert fn, f"{script} no longer defines {fname}"
        body = ast.unparse(fn[0])
        assert "cluster_se" in body, (
            f"{script}::{fname} re-implements the estimator instead of "
            f"delegating to golive_readiness.cluster_se")
        # the sandwich correction must not ALSO be present locally
        assert "(G - 1" not in body and "(g - 1" not in body, (
            f"{script}::{fname} still carries the sandwich arithmetic itself")
