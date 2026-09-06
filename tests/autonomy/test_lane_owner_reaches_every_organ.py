"""[(yi)] ONE lane owner, read by every organ that acts on the judge's lane.

`(ww)` moved the judge's serial lane from 💸 the Farmer to 👩 mum and `(ye)`
made the lever PREFIX a declaration (`fleet_bus.JUDGED_PAIRS[*]["xp_prefix"]`,
read through `xp_prefix_for`) after four days in which mum's arm could not hear
its own candidate. That closed the prefix at the bot; it did not close the same
class in the ORGANS that watch the lane, each of which still carried a Farmer
literal written when the Farmer's lane was the only one:

  * `fleet_immune.APP_RECEIPT_BOTS` — two hardcoded entries, so the
    enacted-is-not-applied detector watched a RETIRED pair and was structurally
    blind to the lane the judge actually runs;
  * `experiment_judge` wrote its just-built state onto `pairs["farmer"]`, so
    the census entry for the live lane kept a stale precheck view while a
    retired pair claimed a running machine;
  * the growth-lever promoter asked mum's shadow to prove it ran
    `xp.funding.*` — a receipt no book on this lane can produce, published
    hourly as "floors" and an UNREACHABLE warning;
  * `fleet_proprioception.grade_live` pooled EVERY live row, so
    `live.mum.rsi_max` was graded over 🙏 avo's trades — and a `hurting`
    verdict on the generic `live` group is reverted at the consumer by
    `fleet_tuning.get_lever`, i.e. one book's record could release another
    book's promoted lever.

Every assertion below is written to redden when the corresponding literal is
restored. Mutations verified: see the (yi) changelog entry.
"""
import ast
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_bus                     # noqa: E402
import fleet_immune                  # noqa: E402
import fleet_proprioception as prop  # noqa: E402
import experiment_judge as judge     # noqa: E402


def _pairs():
    return {k: v for k, v in (getattr(fleet_bus, "JUDGED_PAIRS", {}) or {}).items()
            if isinstance(v, dict)}


# --------------------------------------------------------------------------
# 1. the immune organ's receipt map is DERIVED from the declaration
# --------------------------------------------------------------------------
def test_every_declared_pair_has_both_receipt_lanes():
    """Mutation: restore the two `xp.funding.`/`live.funding.` literals =>
    mum's lanes vanish and this reddens."""
    m = fleet_immune.APP_RECEIPT_BOTS
    assert m, "receipt map is empty — the derivation is dark"
    for pid, ps in _pairs().items():
        xp = ps.get("xp_prefix")
        if not (isinstance(xp, str) and xp.startswith("xp.")):
            continue
        if ps.get("shadow_bot"):
            assert m.get(xp) == ps["shadow_bot"], (pid, xp, m.get(xp))
        if ps.get("live_bot"):
            lv = "live." + xp[len("xp."):]
            assert m.get(lv) == ps["live_bot"], (pid, lv, m.get(lv))


def test_the_judges_own_serial_lane_is_watched_by_the_immune_organ():
    """The lane the judge RUNS today must be in the map — the specific hole
    (ww) opened. Mutation: any hardcoded map that names one book => red."""
    lane = judge.serial_lane_id()
    assert lane, "no declared pair claims the judge's live arm"
    ps = _pairs()[lane]
    assert fleet_immune.APP_RECEIPT_BOTS.get(ps["xp_prefix"]) == ps["shadow_bot"]


def test_no_book_name_is_hardcoded_in_the_receipt_map():
    """AST: the module-level assignment must be a CALL (the derivation), never
    a dict display of literals."""
    tree = ast.parse(io.open(fleet_immune.__file__, encoding="utf-8").read())
    found = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "APP_RECEIPT_BOTS"
                     for t in n.targets)]
    assert len(found) == 1, "APP_RECEIPT_BOTS assigned more than once"
    assert isinstance(found[0].value, ast.Call), \
        "APP_RECEIPT_BOTS is a literal again — it must be derived"


def test_a_dark_declaration_publishes_sickness_rather_than_a_silent_pass():
    """I1/I4: an unreadable declaration must not read as 'nothing is sick'.
    Mutation: delete the `if not APP_RECEIPT_BOTS` guard => red."""
    real = fleet_immune.APP_RECEIPT_BOTS
    try:
        fleet_immune.APP_RECEIPT_BOTS = {}
        out = fleet_immune.application_sickness(
            {"xp.mum.rsi_max": {"value": 36,
                                "expires": "2099-01-01T00:00:00+00:00"}},
            [], 0.0, {})
        assert "app-receipt-map" in out, out
        assert "DARK" in str(out["app-receipt-map"])
    finally:
        fleet_immune.APP_RECEIPT_BOTS = real


# --------------------------------------------------------------------------
# 2. the judge mirrors its state onto the lane it actually runs
# --------------------------------------------------------------------------
def _run_once_payload():
    store = judge.store
    saved = {}
    keys = ("load_state_checked", "load_state", "save_state",
            "fetch_paper_trades", "fetch_bot_pnl", "save_history")
    orig = {k: getattr(store, k, None) for k in keys}
    store.load_state_checked = lambda k: (True, {})
    store.load_state = lambda k: None
    store.save_state = lambda k, v: saved.__setitem__(k, v) or True
    store.fetch_paper_trades = lambda limit=4000: []
    store.fetch_bot_pnl = lambda: []
    store.save_history = lambda k, v: True
    try:
        judge.run_once()
    finally:
        for k, fn in orig.items():
            if fn is not None:
                setattr(store, k, fn)
    return saved.get(judge.KEY) or {}


def test_the_machines_state_lands_on_the_lane_it_runs_and_nowhere_else():
    """Mutation: restore `_pairs["farmer"] = ...` => the machine's provenance
    lands on the retired pair and both assertions redden."""
    lane = judge.serial_lane_id()
    pl = _run_once_payload()
    assert set(pl.get("pairs") or {}) == set(_pairs()), sorted(pl.get("pairs") or {})
    assert pl["pairs"][lane].get("src") == "machine", pl["pairs"]
    machine = [p for p, e in pl["pairs"].items()
               if isinstance(e, dict) and e.get("src") == "machine"]
    assert machine == [lane], machine
    assert pl["pairs"][lane]["phase"] == pl["phase"], pl["pairs"][lane]


def test_the_lane_id_is_derived_from_the_declaration_not_written_twice():
    """`serial_lane_id` reads LIVE_BOT against the declared pairs; swap the
    live arm and the lane follows without a code change."""
    for pid, ps in _pairs().items():
        assert judge.serial_lane_id(ps["live_bot"]) == pid, pid
    assert judge.serial_lane_id("no-such-row") is None


# --------------------------------------------------------------------------
# 3. the growth pair runs only on the lane whose prefix it names
# --------------------------------------------------------------------------
def test_the_growth_pair_belongs_to_one_lane_and_says_so():
    assert judge.growth_cand_for("xp.funding.") == judge.GROWTH_CAND
    for pid, ps in _pairs().items():
        if ps.get("xp_prefix") != "xp.funding.":
            assert judge.growth_cand_for(ps["xp_prefix"]) == {}, pid


@pytest.mark.skipif(judge.lane_prefix() == "xp.funding.",
                    reason="the serial lane IS the growth pair's lane today")
def test_a_lane_without_the_growth_pair_publishes_skipped_not_a_verdict():
    """Mutation: drop the `if not _gc:` gate in run_once => the promoter runs
    against a receipt gate mum can never satisfy and publishes `eval`."""
    pl = _run_once_payload()
    assert (pl.get("last_growth") or {}).get("kind") == "skipped", pl.get("last_growth")
    reach = pl.get("growth_reach") or {}
    assert reach.get("skipped") is True and reach.get("reachable") is None, reach
    assert judge.lane_prefix() in str((pl.get("growth") or {}).get("why") or "")


# --------------------------------------------------------------------------
# 4. a per-book live lever is graded over its own book
# --------------------------------------------------------------------------
def test_a_per_book_live_lever_is_graded_over_that_book_alone():
    """Mutation: restore `bots = set(LIVE_ROWS)` => mum's lever is graded over
    avo's trades too and this reddens."""
    for pid, ps in _pairs().items():
        lb, xp = ps.get("live_bot"), ps.get("xp_prefix") or ""
        if not (lb and xp.startswith("xp.")):
            continue
        lev = "live." + xp[len("xp."):] + "rsi_max"
        assert prop.live_books_for({"stance": {lev: 36}}, "live") == {lb}, pid


def test_a_joint_stance_is_graded_over_exactly_the_books_it_steers():
    ps = list(_pairs().values())
    a, b = ps[0], ps[1]
    stance = {"live." + a["xp_prefix"][3:] + "rsi_max": 1,
              "live." + b["xp_prefix"][3:] + "rsi_max": 2}
    assert prop.live_books_for({"stance": stance}, "live") == {
        a["live_bot"], b["live_bot"]}


def test_an_unattributable_live_lever_fails_open_to_the_whole_cohort():
    """A lever we cannot attribute is graded CONSERVATIVELY (the pre-(yi)
    population), never dropped — the shadow-lane fail-safe contract."""
    assert prop.live_books_for({"stance": {"live.clip_scale": 1.25}},
                               "live-clip") == set(prop.LIVE_ROWS)
    assert prop.live_books_for({"stance": {}}, "live") == set(prop.LIVE_ROWS)


def test_the_funding_lane_keeps_its_own_name_filter():
    rows = {"perps-funding-lighter-lighter", "freqtrade-mum-lighter"}
    assert prop.live_books_for({"stance": {"live.funding.enter_apr": 0.03}},
                               "live-funding", rows=rows) == {
        "perps-funding-lighter-lighter"}


def test_grade_live_reads_the_population_from_the_one_owner():
    """AST: `grade_live` must call `live_books_for` and must not rebuild the
    population inline. Mutation: inline `set(LIVE_ROWS)` again => red."""
    tree = ast.parse(io.open(prop.__file__, encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "grade_live")
    calls = {getattr(c.func, "id", None) for c in ast.walk(fn)
             if isinstance(c, ast.Call)}
    assert "live_books_for" in calls, "grade_live no longer asks the owner"
    src = ast.get_source_segment(
        io.open(prop.__file__, encoding="utf-8").read(), fn) or ""
    assert "LIVE_ROWS" not in src, \
        "grade_live reads LIVE_ROWS directly again — the population has two owners"
