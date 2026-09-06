"""[2026-09-06] Pins for `scripts/fleet_pooled_grader.py`.

The module's whole value is that a pooled cell is HARDER to claim than a
per-book one, so every pin here is about a way a pooled claim can be fake:
one book carrying it, one day carrying it, an outcome-conditioned bucket, or
three arms of one strategy wearing three names. Each of those four produced a
wrong headline on a real run before it was pinned.
"""
import ast
import math
import os
import statistics as st
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fleet_pooled_grader as pg          # noqa: E402
import golive_readiness as gr             # noqa: E402
import winners_docket as wd               # noqa: E402
import fleet_allocation as fa             # noqa: E402
import bot_pnl_store as store             # noqa: E402

SRC = os.path.join(ROOT, "scripts", "fleet_pooled_grader.py")


def _rows(bot_days, pct, held_h=2.0, reason="long-x_conv", side="long"):
    return {"rows": [
        (pct, 1.0, None, f"{d}T00:00:00", {"held_h": held_h}, reason, "P",
         {"side": side, "reason": reason}) for d in bot_days]}


def _days(n, start=1):
    return [f"2026-08-{((start + i) % 27) + 1:02d}" for i in range(n)]


def test_selftest_passes():
    assert pg._selftest() == 0


# ---------------------------------------------------------------------------
# IDENTITY IMPORTS — (hj): a second copy of a rule is a second rule
# ---------------------------------------------------------------------------
def test_rules_are_imported_not_reimplemented():
    tree = ast.parse(open(SRC).read())
    local = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for owned in ("cluster_se", "bh_survivors", "t_crit", "era_rows",
                  "era_base", "shape", "side_of", "split_reason",
                  "is_phantom_close", "OUTCOME_EXITS"):
        assert owned not in local, f"{owned} must be imported, not redefined"


def test_owners_are_the_real_objects():
    # identity, not name-presence: a hand-rolled copy passes a name check
    assert pg.gr.cluster_se is gr.cluster_se
    assert pg.wd.bh_survivors is wd.bh_survivors
    assert pg.fa.t_crit is fa.t_crit
    assert pg.store.split_reason is store.split_reason
    assert pg.gr.era_base is gr.era_base
    assert pg.wd.OUTCOME_EXITS is wd.OUTCOME_EXITS


def test_module_is_advisory_on_its_own_source():
    """It may not write a lever, move capital or open a market — the
    fleet_allocation pattern, asserted against the source rather than promised
    in the docstring."""
    tree = ast.parse(open(SRC).read())
    banned = {"write_levers", "get_lever", "market_open", "publish",
              "apply_tuning", "set_allocation", "claim_writer"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            nm = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            assert nm not in banned, f"advisory module calls {nm}"


# ---------------------------------------------------------------------------
# I7 — outcome-conditioned exits never reach the referee
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("reason", [
    "long-dip_tp", "short-disloc_sl", "long-x_roi", "long_stop",
    "long-trend-breakout_trailing_stop_loss",   # 'loss' hides a stop
    "long-range-on_range_top",
    "long-dip-in-uptrend_sell_into_strength",
])
def test_outcome_conditioned_exits_are_refused(reason):
    assert pg.exit_family(reason) is None, reason


@pytest.mark.parametrize("reason,fam", [
    ("long-snap_conv", "conv"),
    ("long_exit_long", "exit_long"),     # naive rsplit gave "long"
    ("long_range_high", "range_high"),   # naive rsplit gave "high"
    ("long-impulse-fade_max_hold", "max_hold"),
])
def test_non_outcome_exits_keep_their_full_family(reason, fam):
    assert pg.exit_family(reason) == fam


def test_reason_without_an_exit_part_is_not_a_family():
    # `short-funding` has no underscore: split_reason returns "trade"
    assert pg.exit_family("short-funding") is None
    assert pg.exit_family(None) is None
    assert pg.exit_family("") is None


def test_a_tautological_cell_cannot_reach_the_report():
    """End-to-end: a book whose every close is a take-profit must contribute
    NO exit cell, however large and consistent it is."""
    shaped = {f"b{i}": _rows(_days(40, i * 3), 0.05, reason="long-x_tp")
              for i in range(5)}
    graded = pg.audit(shaped, {})
    assert not [k for k in graded if k[0] == "exit"], graded


# ---------------------------------------------------------------------------
# CLUSTERING — the two ways a pooled cell is a fake
# ---------------------------------------------------------------------------
def test_one_book_cannot_carry_a_cell():
    one = {"solo": _rows(_days(200), -0.02, side="short",
                         reason="short-x_conv")}
    assert ("side", "short") not in pg.audit(one, {})


def test_arms_of_one_strategy_are_one_cluster():
    """`X`, `X-lighter`, `X-lshadow` are one strategy. Counting them as three
    books cleared the MIN_BOOKS floor on a single book in the first live run
    and produced the report's only BH survivor."""
    arms = {"perps-donchian-breakout" + s: _rows(_days(40), 0.05)
            for s in ("", "-lighter", "-lshadow")}
    assert ("side", "long") not in pg.audit(arms, {})
    assert (gr.era_base("perps-donchian-breakout-lshadow")
            == gr.era_base("perps-donchian-breakout"))


def test_binding_statistic_is_the_weaker_clustering():
    vals = [0.01] * 100 + [-0.02, -0.03, -0.01]
    bots = ["a"] * 100 + ["b", "c", "d"]
    days = [f"d{i % 7}" for i in range(103)]
    g = pg.grade_cell(vals, bots, days)
    assert g is not None
    assert abs(g["t_binding"] - min([g["t_book"], g["t_day"]], key=abs)) < 1e-12
    assert abs(g["t_binding"]) <= abs(g["t_iid"]) + 1e-9


def test_dof_belongs_to_the_clustering_that_binds():
    """The first draft used `min(n_book, n_day) - 1`, so a t from 13 day
    clusters was priced against 2 dof and its p inflated ~2x. Over-conservative
    is still wrong: it hides findings."""
    for vals, bots, days in [
        ([0.01, -0.005] * 30, ["a", "b", "c"] * 20, [f"d{i}" for i in range(60)]),
        ([0.02, -0.01] * 25, [f"b{i % 9}" for i in range(50)], ["d1", "d2", "d3"] * 17),
    ]:
        g = pg.grade_cell(vals, bots, days[:len(vals)])
        if g is None:
            continue
        gb = g["n_book"] if g["t_binding"] == g["t_book"] else g["n_day"]
        assert g["dof"] == max(1, gb - 1), g


def test_book_floor_refuses_a_one_book_cell():
    assert pg.grade_cell([0.01] * 50, ["a"] * 50, ["d"] * 50) is None
    assert pg.grade_cell([0.01] * 50, ["a"] * 25 + ["b"] * 25,
                         [f"d{i}" for i in range(50)]) is None


def test_trade_floor_refuses_a_thin_cell_that_has_enough_books():
    """The two floors are independent and each needs its own case: this cell
    clears MIN_BOOKS and must still be refused on n. Pinned after a mutation
    dropping MIN_CELL_N 30 -> 2 SURVIVED the first suite, because every
    "underpowered" fixture there happened to fail the BOOK floor first."""
    n = pg.MIN_CELL_N - 1
    vals = [0.01 if i % 2 else -0.02 for i in range(n)]
    bots = [f"b{i % 5}" for i in range(n)]
    days = [f"d{i}" for i in range(n)]
    assert len(set(bots)) >= pg.MIN_BOOKS
    assert pg.grade_cell(vals, bots, days) is None, "n floor must bind"
    # one more trade, same shape, and it grades — so the refusal above is the
    # floor doing its job rather than the fixture being unusable
    vals.append(0.01)
    bots.append("b5")
    days.append("dX")
    assert pg.grade_cell(vals, bots, days) is not None


def test_a_cell_at_both_floors_grades():
    ok = pg.grade_cell([0.01, -0.02] * 20, ["a", "b", "c"] * 13 + ["a"],
                       [f"d{i}" for i in range(40)])
    assert ok is not None and ok["books"] == 3


# ---------------------------------------------------------------------------
# SCOPE — living books, and fail-closed unknowns
# ---------------------------------------------------------------------------
def test_living_scope_excludes_retired_books():
    shaped = {f"b{i}": _rows(_days(40, i * 3), 0.05) for i in range(5)}
    assert ("side", "long") in pg.audit(shaped, {})
    assert pg.audit(shaped, {}, living=set()) == {}
    assert ("side", "long") in pg.audit(shaped, {},
                                        living={f"b{i}" for i in range(5)})


def test_living_bases_uses_era_base_and_is_none_safe():
    lb = pg.living_bases([{"bot": "freqtrade-mum-lshadow"}, {"bot": "book-x"}])
    assert gr.era_base("freqtrade-mum-lshadow") in lb and "book-x" in lb
    assert pg.living_bases([]) == set()
    assert pg.living_bases(None) == set()


def test_unknown_regime_is_its_own_cell_never_a_guess():
    q = (-0.01, -1.0, None, "2026-09-01T00:00:00", {"held_h": 2.0},
         "short-snap_conv", "X",
         {"side": "short", "reason": "short-snap_conv"})
    assert dict(pg.features("b", q, {}))["side x regime"] == "short | unknown"
    assert dict(pg.features("b", q, {"2026-09-01": 1}))["side x regime"] \
        == "short | risk-ON"
    assert dict(pg.features("b", q, {"2026-09-01": -1}))["side x regime"] \
        == "short | risk-OFF"


def test_regime_map_is_fail_closed_without_a_fetch():
    assert pg.btc_regime_map(fetch=False) == {}


def test_unreadable_side_contributes_no_side_cell():
    q = (0.01, 1.0, None, "2026-09-01T00:00:00", {}, "weird", "X",
         {"reason": "weird", "pnl_pct": 0.01})
    assert not [k for k, _ in pg.features("b", q, {}) if k.startswith("side")]


def test_hold_band_refuses_junk():
    assert pg.hold_band(None) is None
    assert pg.hold_band({"held_h": "x"}) is None
    assert pg.hold_band({"held_h": float("nan")}) is None
    assert pg.hold_band({}) is None
    assert pg.hold_band({"held_h": 0.5}) == "<1h"
    assert pg.hold_band({"held_h": 1000.0}) == ">3d"


# ---------------------------------------------------------------------------
# p-values — two-sided on purpose, so a LOSER is as findable as a winner
# ---------------------------------------------------------------------------
def test_p_is_two_sided_and_calibrated():
    assert pg._p_two_sided(0.0, 30) > 0.99
    assert pg._p_two_sided(6.0, 30) < 0.01
    assert abs(pg._p_two_sided(-6.0, 30) - pg._p_two_sided(6.0, 30)) < 1e-12
    # t=2.045 at 29 dof is the textbook two-sided 0.05 point
    assert 0.045 < pg._p_two_sided(2.045, 29) < 0.055
    # t=2.756 at 29 dof is the two-sided 0.01 point
    assert 0.008 < pg._p_two_sided(2.756, 29) < 0.012


def test_bh_is_applied_across_every_graded_cell():
    shaped = {f"b{i}": _rows(_days(40, i * 3), 0.05) for i in range(6)}
    graded = pg.audit(shaped, {})
    assert graded
    assert all("bh" in v for v in graded.values())
    surv = wd.bh_survivors([(k, v["p"]) for k, v in graded.items()],
                           fdr=pg.FDR)
    assert {k for k, v in graded.items() if v["bh"]} == set(surv)


def test_a_real_spread_effect_is_found_across_many_books():
    """The positive control (I3 applied to a grader): an instrument that never
    finds anything is trivially safe and useless."""
    shaped = {f"b{i}": _rows(_days(40, i * 3), -0.02, side="short",
                             reason="short-x_conv") for i in range(8)}
    graded = pg.audit(shaped, {})
    cell = graded.get(("side", "short"))
    assert cell is not None
    assert cell["books"] == 8 and cell["mean_pct"] < 0
    assert cell["bh"] is True, cell
