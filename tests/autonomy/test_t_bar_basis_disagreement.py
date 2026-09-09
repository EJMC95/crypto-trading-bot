"""[(zi)] THE GATE'S t BAR AND ITS OWN CLUSTER READ DISAGREED ON EXACTLY THE
TWO BOOKS HOLDING REAL MONEY — AND NOTHING SAID SO.

Measured 2026-09-09 on the live `golive-readiness` payload, all 14 books
carrying both statistics:

    👩 mum LIVE    n=100  t=2.01 PASS   t_cluster=1.45 FAIL   max_batch=8
    🙏 avo LIVE    n= 18  t=2.65 PASS   t_cluster=1.86 FAIL   max_batch=5
    ...and 0 of the 12 SHADOW books disagree at all.

Two of fourteen, both real money, both in the PERMISSIVE direction — the bar
admits where the cluster-robust read of the same sample refuses. It names its
own cause: the live arms carry a flatten (the daily-loss halt) that closes a
whole basket in one instant, so they batch 8 and 5 legs where their paper
twins batch 4. The iid `t` counts those legs as independent draws.

WHAT THIS DOES NOT DO, deliberately: it does not move the bar. `(ky)` left
the gate on the iid value and said why — *changing a go-live bar is a policy
act, not a fix* — and that is Eamon's call, exactly as `(yr)` left the
peak-relative drawdown reported-not-a-bar. What was missing is that the
disagreement was INVISIBLE: a reader had to hand-compare `t` against
`cluster.t_cluster` AND know which basis the bar used. That is the `(lv)`
ambiguity sitting on the gate that governs real money, and publishing it is
what turns a policy question into one Eamon can actually see.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import sys                                        # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
import golive_readiness as G                      # noqa: E402


def _s(t, tc, n=100, g=20):
    return {"t": t, "n": n, "cluster": {"t_cluster": tc, "n_clusters": g}}


# ------------------------------------------------- THE BAR DID NOT MOVE

def test_grade_never_reads_the_cluster_statistic():
    """THE LOAD-BEARING PIN. This entry publishes a number beside the gate; a
    later edit that lets `grade()` READ it silently re-specs the go-live bar
    on real money. Asserted on the AST of the function itself, not on prose."""
    mod = ast.parse(pathlib.Path(G.__file__).read_text())
    fn = next(n for n in ast.walk(mod)
              if isinstance(n, ast.FunctionDef) and n.name == "grade")
    names = {n.value for n in ast.walk(fn)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    names |= {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    names |= {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    for forbidden in ("t_bar", "t_cluster", "cluster", "permissive"):
        assert forbidden not in names, (
            f"grade() now reads {forbidden!r} — the t bar has been re-spec'd. "
            f"That is a policy act ((ky)), not a publish.")


def test_the_published_bar_contract_is_unchanged():
    assert G.BAR_NAMES == ("window", "closes", "mean", "t", "halves", "maxdd")
    assert "t_bar" not in G.BAR_NAMES


def test_a_permissive_book_still_passes_the_gate_exactly_as_before():
    """Publishing the disagreement must not quietly fail mum or avo. A book
    that passed on iid yesterday passes today — otherwise this is a tightening
    wearing a publish's clothes, and a tightening needs Eamon (I26)."""
    s = {"n": 100, "days": 40.0, "mean_pct": 0.004, "t": 2.01,
         "h1": 10.0, "h2": 1.0, "max_dd_frac": 0.07, "win_rate": 0.73,
         "cluster": {"t_cluster": 1.45, "n_clusters": 52}}
    ok, fails = G.grade(s)
    assert ok, fails
    assert not any("t " in f for f in fails), fails
    # and the disagreement IS visible on the same sample
    r = G.t_bar_bases(s)
    assert r["permissive"] is True and r["agree"] is False


# --------------------------------------------------------- FAIL-CLOSED

@pytest.mark.parametrize("state,why", [
    ({"t": 2.5, "n": 100},                              "no cluster block"),
    ({"t": 2.5, "n": 100, "cluster": None},             "cluster is None"),
    ({"t": 2.5, "n": 100, "cluster": "nope"},           "cluster not a dict"),
    ({"n": 100, "cluster": {"t_cluster": 1.2, "n_clusters": 20}}, "t missing"),
    ({"t": 2.5, "n": 100, "cluster": {"n_clusters": 20}}, "t_cluster missing"),
    (_s(2.5, float("nan")),                             "t_cluster NaN"),
    (_s(float("inf"), 1.2),                             "t infinite"),
    (_s(2.5, 1.2, g=1),                                 "single cluster"),
    (_s(2.5, 1.2, n=100, g=100),                        "no batching (g == n)"),
    (_s(2.5, 1.2, n=True),                              "n is a bool"),
    (_s(True, 1.2),                                     "t is a bool"),
    ("not-a-dict",                                      "state is not a dict"),
    (None,                                              "state is None"),
])
def test_any_doubt_publishes_nothing_never_a_false_agreement(state, why):
    """Silence, never a fabricated `agree: True`. A book whose cluster read
    does not exist must not be reported as one whose bases agree — that is a
    reassurance about real money that nothing measured."""
    assert G.t_bar_bases(state) is None, why


def test_it_actually_computes_on_a_real_sample():
    """The mirror of every fail-closed case: a function that always returned
    None would pass all of them and publish nothing, forever (I3)."""
    r = G.t_bar_bases(_s(2.01, 1.45, n=100, g=52))
    assert r is not None
    assert r["t_iid"] == 2.01 and r["t_cluster"] == 1.45
    assert r["basis"] == "iid" and r["bar"] == G.GOLIVE_MIN_T


# ------------------------------------------------------- THE ASYMMETRY

def test_permissive_is_the_direction_that_can_put_money_behind_a_weak_number():
    """A book the bar REFUSES while the cluster read would pass stays on paper
    and costs nothing. The reverse is the only direction that matters here."""
    assert G.t_bar_bases(_s(2.5, 1.2))["permissive"] is True    # bar admits
    assert G.t_bar_bases(_s(1.2, 2.5))["permissive"] is False   # bar refuses
    assert G.t_bar_bases(_s(2.5, 2.5))["permissive"] is False   # both pass
    assert G.t_bar_bases(_s(1.2, 1.2))["permissive"] is False   # both fail


def test_agree_tracks_the_bar_not_the_gap_between_the_numbers():
    """Two statistics far apart but on the SAME side of the bar agree about
    the verdict, which is the only thing the gate acts on."""
    wide = G.t_bar_bases(_s(9.0, 2.1))          # 6.9 apart, both pass
    assert wide["agree"] is True and wide["permissive"] is False
    narrow = G.t_bar_bases(_s(2.01, 1.99))      # 0.02 apart, straddles
    assert narrow["agree"] is False and narrow["permissive"] is True


def test_the_boundary_is_inclusive_exactly_as_the_bar_is():
    """`grade()` fails on `t < GOLIVE_MIN_T`, so t == the bar PASSES. A
    reimplementation that used `>` here would report a disagreement the gate
    does not have — a second copy of the rule ((hj))."""
    at = G.t_bar_bases(_s(G.GOLIVE_MIN_T, G.GOLIVE_MIN_T))
    assert at["passes_iid"] is True and at["passes_cluster"] is True
    just_under = G.t_bar_bases(_s(G.GOLIVE_MIN_T, G.GOLIVE_MIN_T - 0.01))
    assert just_under["passes_cluster"] is False


# --------------------------------------------------------- THE PUBLISH

def test_the_publish_site_attaches_it():
    src = pathlib.Path(G.__file__).read_text()
    assert 'out["t_bar"] = t_bar_bases(s)' in src, (
        "the disagreement is computed and never published — the (lv) shape "
        "this entry exists to close")
