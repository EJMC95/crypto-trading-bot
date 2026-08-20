"""[(sf)] The judge's paired bar was comparing two arms on different policies.

🧪 the experiment judge is the fleet's ONLY designed path to more real money:
a candidate is promoted when the shadow twin beats the live control per-trade
by MARGIN_PP (0.50pp) over the window and both halves. `arm_trades` gated the
shadow arm on the lever RECEIPT — proof it ran the candidate's BARS — and said
nothing about which ENTRY POLICY produced each close.

The arms do not run the same one. The shadow twin runs `explore_k=2` (plus
scaled conviction); the live control runs `explore_k=0`. So a THIRD of the
experiment arm's closes came from a policy the control never runs, and they are
the losing third.

MEASURED post-28-Jul (the src-stamped era, both arms on one build so no
`arm_drift` fires), reproduced independently from the paper ledger:

    shadow ALL       n=113   mean -0.1711%/trade
      src=exploit    n= 74   mean -0.0104%
      src=explore    n= 38   mean -0.4961%
    live  ALL        n= 73   mean -0.0368%   (72 of 73 stamped `exploit`)

    paired gap AS THE JUDGE COMPUTED IT   -0.1343pp
    paired gap on SRC-MATCHED subsets     +0.0264pp
    => a 0.161pp handicap against a +0.50pp bar — 32% of it, charged to the
       experiment before it began.

NOT hypothetical: the judge's ONE completed verdict in five weeks reads
`RELEASED-OPERATOR ... 3-variable A/B (shadow ran explore+conviction
mid-window)`, and the growth promoter sits parked on "shadow arm not positive
in its own right" — circular, because explore is what makes it not positive.
Zero promotions in five weeks.
"""
import pytest

pytestmark = pytest.mark.autonomy

import experiment_judge as J          # noqa: E402


import json
from datetime import datetime, timezone

T0 = 1_800_000_000.0
T1 = T0 + 2000 * 3600.0     # wide enough that no fixture row falls outside it


def _ts(i):
    """The judge parses ISO strings off `bot_trades.close_ts`, so the fixture
    must speak the publisher's own shape — a float here would silently miss
    every window filter and make the whole file vacuous (the (hj) rule: a
    consumer is tested against a payload its publisher built)."""
    return datetime.fromtimestamp(T0 + i * 3600.0,
                                  timezone.utc).isoformat()


def _spread():
    """40 winning on-policy shadow closes, 20 losing OFF-policy ones, and a
    live control — all spread across the window so the BOTH-HALVES gate is
    exercised rather than accidentally deciding the verdict."""
    return ([_row("sh", _ts(i * 7), 0.8, "exploit") for i in range(40)]
            + [_row("sh", _ts(i * 13 + 2), -3.0, "explore") for i in range(20)]
            + [_row("live", _ts(i * 7 + 3), 0.1, "exploit") for i in range(40)])


def _row(bot, ts, pct, src=None, extra_str=False):
    x = {"src": src} if src else {}
    return {"bot": bot, "close_ts": ts, "profit_ratio": pct / 100.0,
            "extra": (json.dumps(x) if extra_str else x)}


# ------------------------------------------------------------- the src reader

def test_the_src_is_read_from_a_dict_or_a_json_string():
    """bot_trades hands `extra` back as either, depending on the driver."""
    assert J._src_of(_row("b", _ts(0), 1.0, "explore")) == "explore"
    assert J._src_of(_row("b", _ts(0), 1.0, "explore", extra_str=True)) \
        == "explore"
    assert J._src_of(_row("b", _ts(0), 1.0)) is None
    assert J._src_of({"extra": "not json"}) is None
    assert J._src_of({}) is None


def test_an_arm_that_stamps_nothing_is_UNKNOWN_not_empty():
    """"I cannot tell" and "the arm ran no policies" are different states, and
    only the first may disable the match. Collapsing them would filter every
    experiment close away the moment the control stopped stamping."""
    rows = [_row("live", _ts(i), 0.1) for i in range(5)]
    assert J.policy_srcs(rows, "live", T0, T1) is None
    assert J.policy_srcs([], "live", T0, T1) == set()


def test_the_control_defines_the_policy_set():
    rows = [_row("live", _ts(i), 0.1, "exploit") for i in range(5)]
    assert J.policy_srcs(rows, "live", T0, T1) == {"exploit"}


# --------------------------------------------------------------- the filter

def test_the_losing_off_policy_third_leaves_the_comparison():
    """The finding, as a behaviour. The experiment arm's explore closes are a
    policy the control never runs; with them in, the gap reads negative."""
    rows = ([_row("sh", _ts(i), -0.01, "exploit") for i in range(74)]
            + [_row("sh", _ts(200 + i), -0.50, "explore") for i in range(38)]
            + [_row("live", _ts(400 + i), -0.04, "exploit") for i in range(73)])
    sh = J.arm_trades(rows, "sh", T0, T1)
    lv = J.arm_trades(rows, "live", T0, T1)
    keep = J.policy_srcs(rows, "live", T0, T1)
    assert keep == {"exploit"}
    before = J._mean_pct(sh) - J._mean_pct(lv)
    sh2, dropped = J.match_policy(rows, "sh", T0, T1, keep)
    after = J._mean_pct(sh2) - J._mean_pct(lv)
    assert dropped == 38, dropped
    assert before < 0 < after, (before, after)
    assert after - before == pytest.approx(0.16, abs=0.01), (before, after)


def test_the_restriction_is_symmetric():
    """Both arms are cut to the SAME set, so an unstamped row is dropped from
    each rather than assumed to be exploit on one side only."""
    rows = ([_row("sh", _ts(i), 1.0, "exploit") for i in range(3)]
            + [_row("sh", _ts(10), 9.0)]
            + [_row("live", _ts(20 + i), 1.0, "exploit") for i in range(3)]
            + [_row("live", _ts(30), 9.0)])
    keep = J.policy_srcs(rows, "live", T0, T1)
    _, ds = J.match_policy(rows, "sh", T0, T1, keep)
    _, dl = J.match_policy(rows, "live", T0, T1, keep)
    assert ds == 1 and dl == 1, (ds, dl)


# ------------------------------------------------------------- fail-safe

def test_an_unstamped_control_filters_nothing():
    """Fail-safe toward today's behaviour: a bias fix that can silence the
    judge entirely is a worse defect than the bias."""
    rows = ([_row("sh", _ts(i), 1.0, "explore") for i in range(5)]
            + [_row("live", _ts(20 + i), 1.0) for i in range(5)])
    keep = J.policy_srcs(rows, "live", T0, T1)
    assert keep is None
    sh = J.arm_trades(rows, "sh", T0, T1)
    assert J.match_policy(rows, "sh", T0, T1, keep) == (sh, 0)


def test_filtering_everything_away_falls_back_instead_of_starving():
    rows = ([_row("sh", _ts(i), 1.0, "explore") for i in range(5)]
            + [_row("live", _ts(20 + i), 1.0, "exploit") for i in range(5)])
    sh = J.arm_trades(rows, "sh", T0, T1)
    keep = J.policy_srcs(rows, "live", T0, T1)
    kept, dropped = J.match_policy(rows, "sh", T0, T1, keep)
    assert kept == sh and dropped == 0, (
        "an all-off-policy arm must fall back, not report an empty sample "
        "that the floors would then read as 'not enough data yet' forever")


# ------------------------------------------------------ wired, and published

def test_paired_eval_applies_it_and_says_what_it_did():
    """A sample that shrank by a third without saying so is the same class of
    defect this fixes."""
    rows = _spread()
    v = J.paired_eval(rows, T0, T0 + 300 * 3600.0, shadow_bot="sh",
                      live_bot="live", min_closes=10, live_min=10)
    assert v["policy_match"]["keep"] == ["exploit"]
    assert v["policy_match"]["dropped_shadow"] == 20, v["policy_match"]
    assert v["n_shadow"] == 40, v
    assert v["shadow_mean_pct"] == pytest.approx(0.8, abs=1e-6), v
    assert v["promote"] is True, v


def test_the_same_data_does_NOT_promote_without_the_match(monkeypatch):
    """The control for the test above: with the off-policy closes left in, the
    identical candidate fails the bar. That is the promotion the bias was
    eating."""
    monkeypatch.setattr(J, "policy_srcs", lambda *a, **k: None)
    rows = _spread()
    v = J.paired_eval(rows, T0, T0 + 300 * 3600.0, shadow_bot="sh",
                      live_bot="live", min_closes=10, live_min=10)
    assert v["promote"] is False, v
    assert v["shadow_mean_pct"] < 0, v


def test_the_judge_is_still_the_only_writer_of_the_live_lane():
    """The fix touches the COMPARISON, never the authority. If this change had
    quietly widened who may write live.funding.*, that would outrank every
    promotion it unblocks."""
    import ast
    import inspect
    src = inspect.getsource(J)
    tree = ast.parse(src)
    writers = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "write_levers"]
    assert writers, "the judge no longer writes any lever — wiring is gone"
    for fn in ("match_policy", "policy_srcs", "_src_of"):
        body = inspect.getsource(getattr(J, fn))
        assert "write_levers" not in body and "live." not in body, fn


def test_the_halves_take_the_same_match_as_the_full_window():
    """Caught by this file's own fixture during the fix: matching only the full
    window left the BOTH-HALVES gate — the doctrine's central noise filter —
    reading the biased sample. A candidate could then clear the window bar and
    be failed by a half that still counted off-policy closes, which is worse
    than no fix at all because it looks corrected."""
    rows = _spread()
    v = J.paired_eval(rows, T0, T0 + 300 * 3600.0, shadow_bot="sh",
                      live_bot="live", min_closes=10, live_min=10)
    assert v["promote"] is True, v
    for half in ("h1", "h2"):
        if half in v:
            assert v[half]["shadow"] > 0, (half, v[half])


def test_a_half_the_match_would_empty_falls_back_rather_than_failing_it():
    """Same fail-safe as the full window, one level down. A half with no
    on-policy closes must not be reported as a LOSING half — that is a verdict
    about missing data wearing the clothes of a verdict about edge."""
    rows = ([_row("sh", _ts(i * 7), 0.8, "exploit") for i in range(30)]
            + [_row("sh", _ts(200 + i), 5.0, "explore") for i in range(12)]
            + [_row("live", _ts(i * 7 + 3), 0.1, "exploit") for i in range(30)]
            + [_row("live", _ts(205 + i), 0.1, "exploit") for i in range(12)])
    v = J.paired_eval(rows, T0, T0 + 300 * 3600.0, shadow_bot="sh",
                      live_bot="live", min_closes=10, live_min=10)
    # the second half's shadow arm is ENTIRELY off-policy; the fallback keeps
    # it measurable instead of scoring it as an absent-and-therefore-failing
    # half
    assert "why" not in v or "half" not in str(v.get("why", "")), v


def test_the_row_filter_survives_a_shared_close_timestamp():
    """The defect the first draft shipped and the fixture caught: it joined
    trades back onto rows by close_ts. ⚖️ Counterweight closes TEN legs in one
    instant, and even in this fixture 3 of 40 on-policy closes were dropped
    because an off-policy row overwrote their key. A join on a non-unique key
    is not a filter."""
    same = _ts(5)
    rows = ([_row("sh", same, 1.0, "exploit") for _ in range(4)]
            + [_row("sh", same, -9.0, "explore") for _ in range(4)]
            + [_row("live", _ts(6), 0.1, "exploit")])
    keep = J.policy_srcs(rows, "live", T0, T1)
    kept, dropped = J.match_policy(rows, "sh", T0, T1, keep)
    assert len(kept) == 4 and dropped == 4, (kept, dropped)
    assert J._mean_pct(kept) == pytest.approx(1.0), J._mean_pct(kept)


def test_paired_eval_filters_the_CONTROL_arm_too_not_just_the_experiment():
    """Caught by a SURVIVING mutation: `test_the_restriction_is_symmetric`
    above exercises `match_policy` directly, so leaving the control arm
    unfiltered inside `paired_eval` went undetected.

    It matters. The control defines the policy set, so its only off-set rows
    are UNSTAMPED ones — and an unstamped close is exactly the row we refuse to
    guess about. Counting it on the control side while excluding its twin on
    the experiment side reintroduces the asymmetry the fix exists to remove,
    with the baseline now carrying a row the experiment may not.
    """
    rows = ([_row("sh", _ts(i * 7), 0.8, "exploit") for i in range(30)]
            + [_row("live", _ts(i * 7 + 3), 0.1, "exploit") for i in range(30)]
            # one unstamped control close, and a big one so it moves the mean
            + [_row("live", _ts(101), 40.0)])
    v = J.paired_eval(rows, T0, T0 + 300 * 3600.0, shadow_bot="sh",
                      live_bot="live", min_closes=10, live_min=10)
    assert v["policy_match"]["dropped_live"] == 1, v["policy_match"]
    assert v["n_live"] == 30, v
    assert v["live_mean_pct"] == pytest.approx(0.1, abs=1e-6), (
        "the unstamped control close is still in the baseline — the control "
        "arm is not being matched")
