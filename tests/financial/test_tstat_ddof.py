"""[(lj)] Every t-statistic in this fleet uses the SAMPLE stdev (ddof=1).

THE DEFECT. `scripts/golive_readiness.py::stats` — the rule that governs REAL
MONEY — computed `var = sum((x-mean)**2)/n`. That is the POPULATION variance.
It understates sd by sqrt((n-1)/n) and therefore INFLATES every book's t by
sqrt(n/(n-1)): **1.71% at the n=30 closes bar, 1.24% at n=41**. A book whose
true t is 1.9664 read exactly 2.0000 and PASSED.

Small, but it is one-directional and it is on the one gate standing between a
book and unsupervised real money: it can only ever ADMIT a book that has not
earned it, never block one that has. That is the wrong direction for a gate
whose own doctrine (I10) says to fail closed because "the cost of a wrong
default is unsupervised real money".

THE FLEET HAD ALREADY RULED ON IT AND NEVER SWEPT IT — the (li) pattern.
  * `scripts/study_alpha_vs_regime.py::_t` uses ddof=1, docstring: *"Population
    stdev inflates every t at small n."*
  * A CHANGELOG entry corrects its OWN published numbers for exactly this:
    *"Every t above used POPULATION stdev. Sample stdev: live +0.73 (not
    +0.77), shadow +4.86 (not +5.13), pooled +2.79 (not +2.86)"* — and in the
    next bullet, *"I wrote '+1.96' (the ddof=0 variant) and read it as
    survival."*
  * Every other estimator in the tree was already ddof=1: `fleet_allocation`
    (the I16 lower bound), `lighter_ticket_taker` (the I14 realised-lens veto),
    `parliament/scanners`, `lighter_funding_bot`, and `lighter_family_bot`'s
    explicit `stdev(..., ddof=1)`.

`fleet_radar._t` was the only other population user, and it carried the comment
*"population sd (matches the fleet's other scorers)"* — a parity claim that was
false when written. Both are fixed; this file stops either from drifting back,
and stops a THIRD scorer arriving with the same mistake.
"""
import ast
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [pytest.mark.financial, pytest.mark.autonomy]

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import golive_readiness as G          # noqa: E402
import fleet_radar as R               # noqa: E402


def _rows(pcts):
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    return [(p, p * 10, t0 + timedelta(days=i)) for i, p in enumerate(pcts)]


def _unit_pop_sample(n, target_pop_t, seed=7):
    """A sample whose POPULATION t is exactly `target_pop_t`.

    Built rather than asserted so the boundary case is exact: this is the book
    the old estimator passed and the new one must fail.
    """
    import random
    rnd = random.Random(seed)
    xs = [rnd.gauss(0, 1) for _ in range(n)]
    m0 = sum(xs) / n
    xs = [x - m0 for x in xs]
    sd_pop = math.sqrt(sum(x * x for x in xs) / n)
    xs = [x / sd_pop for x in xs]
    return [x + target_pop_t / math.sqrt(n) for x in xs]


# ---------------------------------------------------------------------------
# the numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [30, 41, 92])
def test_the_grader_uses_the_sample_stdev(n):
    """Compare `stats` against both estimators computed independently."""
    xs = _unit_pop_sample(n, 1.5)
    s = G.stats(_rows(xs))
    mean = sum(xs) / n
    sd_pop = math.sqrt(sum((x - mean) ** 2 for x in xs) / n)
    sd_smp = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
    t_pop = mean / (sd_pop / math.sqrt(n))
    t_smp = mean / (sd_smp / math.sqrt(n))
    assert s["t"] == pytest.approx(t_smp, rel=1e-9), (
        f"grader t={s['t']} is the POPULATION statistic {t_pop}, not the "
        f"sample statistic {t_smp}")
    assert s["t"] < t_pop


@pytest.mark.parametrize("n", [30, 41])
def test_a_book_exactly_at_the_old_bar_now_fails(n):
    """THE INCIDENT, as a number. A book whose population t is exactly 2.0000
    passed the real-money gate; its sample t is below the bar."""
    s = G.stats(_rows(_unit_pop_sample(n, 2.0)))
    assert s["t"] < G.GOLIVE_MIN_T, s["t"]
    assert G.bar_map(s)["t"] is False


def test_a_genuinely_significant_book_still_passes():
    """The control group. A correction that fails everything is not a
    correction — and it would read the same on the card."""
    s = G.stats(_rows(_unit_pop_sample(60, 4.0)))
    assert s["t"] >= G.GOLIVE_MIN_T
    assert G.bar_map(s)["t"] is True


def test_the_cluster_robust_t_is_unaffected():
    """`t_cluster` divides by its own `se_cr`, so it must not move with ddof —
    if it did, the (ky) cluster estimator would have been double-counting sd."""
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = []
    for b in range(8):                       # 8 batches of 5 simultaneous legs
        ts = t0 + timedelta(days=b)
        for k in range(5):
            rows.append((0.5 + 0.1 * k - 0.05 * b, 1.0, ts))
    s = G.stats(rows)
    clus = s.get("cluster") or s.get("clus") or {}
    if not clus:                              # field name is not the claim here
        clus = G.cluster_stats(rows, sum(r[0] for r in rows) / len(rows),
                               1.0, len(rows)) or {}
    assert clus, "the cluster estimator returned nothing for a batched book"
    direct = G.cluster_stats(rows, sum(r[0] for r in rows) / len(rows),
                             1.0, len(rows))
    assert direct["t_cluster"] == pytest.approx(
        G.cluster_stats(rows, sum(r[0] for r in rows) / len(rows),
                        2.0, len(rows))["t_cluster"]), (
        "t_cluster moved when sd changed — it must depend only on se_cr")


def test_the_radar_uses_the_sample_stdev_too():
    xs = _unit_pop_sample(40, 2.0)
    mean = sum(xs) / len(xs)
    sd_smp = math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))
    assert R._t(xs) == pytest.approx(mean / (sd_smp / math.sqrt(len(xs))),
                                     rel=1e-9)


def test_the_brain_weighted_t_carries_the_kish_correction():
    """The brain's `t` gates an ACTUATOR, not a report.

    The v3 expand bars are `t >= +2.0/+2.5` and the reduce bars `t <= -2.5`, so
    an inflated |t| makes BOTH easier to reach — and the expand direction is a
    widening bought without the evidence to pay for it (I19).

    Checked at EQUAL weights, where the Kish n_eff is exactly n and the weighted
    estimator must therefore reduce to the ordinary sample statistic. That is
    the one configuration where the right answer is unambiguous.
    """
    import brain_stats as BS

    n = 40
    now = 1_800_000_000.0
    pnls = _unit_pop_sample(n, 2.0)
    # zero age for every trade -> decay weight 1.0 -> n_eff == n exactly
    trades = [{"profit_abs": p, "close_ts": now, "profit_ratio": p / 100.0}
              for p in pnls]
    b = BS.weighted_bucket(trades, now)
    assert b["n_eff"] == pytest.approx(n, rel=1e-6), b["n_eff"]

    mean = sum(pnls) / n
    sd_smp = math.sqrt(sum((x - mean) ** 2 for x in pnls) / (n - 1))
    sd_pop = math.sqrt(sum((x - mean) ** 2 for x in pnls) / n)
    assert b["sd_w"] == pytest.approx(sd_smp, rel=1e-6), (
        f"sd_w={b['sd_w']} is the population sd {sd_pop}, not the sample sd "
        f"{sd_smp} — the Kish correction is missing")
    assert b["t"] == pytest.approx(mean / (sd_smp / math.sqrt(n)), rel=1e-6)
    # and it is strictly the conservative direction
    assert abs(b["t"]) < abs(mean / (sd_pop / math.sqrt(n)))


def test_the_two_scorers_agree_with_each_other():
    """They render side by side on the same card. A book must not read
    significant on one and not the other for an estimator reason."""
    xs = _unit_pop_sample(50, 2.4)
    assert R._t(xs) == pytest.approx(G.stats(_rows(xs))["t"], rel=1e-9)


# ---------------------------------------------------------------------------
# the class: no THIRD scorer may arrive with population variance
# ---------------------------------------------------------------------------

#: Files whose `/ n` variance is deliberate and NOT a t-statistic, with the
#: reason. The BORN_DARK_OK idiom — silence is not an option.
POPULATION_OK = {
    # mirrors scripts/study_funding_vol_filter.py EXACTLY; harness parity is the
    # point (the (cf) lesson) and it is a VOL FILTER, never a significance test
    "lighter_funding_bot.py": "realized-vol filter, mirrors its study harness",
    # rolling volatility bands, not an inference
    "scripts/backtest_tide_rider_adaptive.py": "rolling vol band, not a t",
    "scripts/backtest_tide_rider_scanner.py": "rolling vol band, not a t",
    # a low-vol RANKING score (`sc[c] = -sd`), and the window length is the
    # same for every coin, so ÷n and ÷(n-1) differ by one constant factor and
    # produce an IDENTICAL ordering. Correcting it would change no selection.
    "scripts/backtest_xsect_factor_lab.py": "low-vol rank score, order-invariant",
    # a WEIGHTED variance correctly divides by Σw, not by (n-1); its ddof=1
    # equivalent is the Kish factor n_eff/(n_eff-1) applied as a MULTIPLY on the
    # same expression, which this AST matcher cannot see. Declared rather than
    # contorting the matcher, and pinned by
    # `test_the_brain_weighted_t_carries_the_kish_correction` below — a
    # behavioural check on the number, which is the stronger guard anyway.
    "brain_stats.py": "weighted variance; ddof=1 applied via the Kish factor",
}


def _population_variance_sites():
    """Every `sum((x - m) ** 2 ...) / n` — a population variance — in a module
    that also computes a t-statistic."""
    hits = []
    for p in sorted(ROOT.rglob("*.py")):
        rel = str(p.relative_to(ROOT))
        if rel.startswith(("tests/", ".git/")) or "__pycache__" in rel:
            continue
        try:
            src = p.read_text()
            tree = ast.parse(src)
        except Exception:                       # noqa: BLE001
            continue
        for node in ast.walk(tree):
            # BinOp: <sum-of-squares> / <divisor>
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            left = ast.dump(node.left)
            if "Pow" not in left or "GeneratorExp" not in left:
                continue
            # a sample variance divides by a Sub (n - 1); anything else is
            # population
            if isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Sub):
                continue
            hits.append((rel, node.lineno))
    return hits


def test_no_undeclared_population_variance_remains():
    """The class-closer. Fixing two instances does not stop a third arriving —
    which is exactly how this one survived a CHANGELOG entry that named it."""
    offenders = [(f, ln) for f, ln in _population_variance_sites()
                 if f not in POPULATION_OK]
    assert not offenders, (
        "population variance (÷n) outside the declared exceptions — if this is "
        "a t-statistic it inflates significance; if it is a volatility measure, "
        f"declare it in POPULATION_OK with a reason: {offenders}")


def test_the_detector_is_not_vacuous():
    """If the AST matcher stops matching, the test above turns green over a
    fleet full of population variances. Prove it still finds the declared
    ones."""
    found = {f for f, _ in _population_variance_sites()}
    assert found, "the population-variance matcher found NOTHING — it is blind"
    assert found & set(POPULATION_OK), (
        f"the matcher no longer sees the known declared sites: {found}")
