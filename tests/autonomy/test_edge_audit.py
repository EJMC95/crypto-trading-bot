"""Structural pins for scripts/edge_audit.py — the fleet-wide edge instrument.

Every pin here was written against a mutation that would have let the audit
publish a wrong number while its selftest stayed green:

  * the sample is the GRADER'S — identity imports of era_rows / is_phantom_close
    / drop_retired_sleeves / stats, never a local copy (the (hj)/(hq) rule);
  * the calibration gate FAILS CLOSED — an absent, undated, stale or one-row-off
    published grade refuses, and refusal is the module's exit 2;
  * the public feed's missing quarantine is applied through the owner
    (`bot_pnl_store.is_quarantined`), found by the gate on its first run;
  * the bootstrap is scaled to the BOOK through the clip (the first cut summed
    clip returns as book returns and read -2082%);
  * N_eff is correlation-aware and unmeasured pairs are treated as independent
    (an UPPER bound, stated), never as zero-correlated-by-default in a way that
    could read as a floor;
  * the module moves nothing.
"""
import ast
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import edge_audit as ea            # noqa: E402
import golive_readiness as gr      # noqa: E402
import fleet_allocation as fa      # noqa: E402
import winners_docket as wd        # noqa: E402
import bot_pnl_store as store      # noqa: E402

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _row(i, pct, usd, pair="X", side=None, reason="long_x", extra=None):
    return (pct, usd, T0 + timedelta(hours=i),
            (T0 + timedelta(hours=i - 1)).isoformat(), extra or {}, None, pair,
            {"pnl_pct": pct, "pnl_abs": usd, "pair": pair, "side": side,
             "reason": reason, "entry_price": 1.0})


# ------------------------------------------------------------ identity imports

def test_the_sample_owners_are_imported_by_identity_not_copied():
    """The AST of edge_audit must not DEFINE any of the grader's owner names —
    a local `def era_rows`/`def stats` would be a second rule."""
    with open(ea.__file__) as fh:
        src = fh.read()
    tree = ast.parse(src)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for owner in ("era_rows", "stats", "is_phantom_close",
                  "drop_retired_sleeves", "cluster_se", "t_crit",
                  "lower_bound", "bh_survivors", "t_sf", "is_quarantined"):
        assert owner not in defined, f"edge_audit re-defines {owner}"
    # and the modules it uses ARE the fleet's
    assert ea.gr is gr and ea.fa is fa and ea.wd is wd and ea.store is store


def test_min_n_is_the_allocation_organs_floor_not_a_retyped_constant():
    assert ea.MIN_N is fa.MIN_N or ea.MIN_N == fa.MIN_N
    # mutation: a local literal 10 would still pass ==; pin the SOURCE form
    with open(ea.__file__) as fh:
        src = fh.read()
    assert "MIN_N = fa.MIN_N" in src


# ------------------------------------------------------------ calibration gate

def _fake_shaped(n=5):
    scoped = [(0.01, 1.0, T0 + timedelta(hours=i)) for i in range(n)]
    return {"x": {"scoped": scoped, "rows": [], "all_time": [],
                  "era_iso": None, "era_src": None}}


def test_calibration_refuses_on_absent_undated_and_stale_grades():
    sh = _fake_shaped()
    now = datetime.now(timezone.utc)
    assert ea.calibrate(sh, {})[0] is False
    assert ea.calibrate(sh, {"books": {}})[0] is False
    assert ea.calibrate(sh, {"books": {"x": {"n": 5}}})[0] is False
    stale = {"books": {"x": {"n": 5}}, "ttl_sec": 3600,
             "updated": (now - timedelta(hours=2)).isoformat()}
    assert ea.calibrate(sh, stale)[0] is False


def test_calibration_requires_n_to_match_exactly():
    sh = _fake_shaped(5)
    now = datetime.now(timezone.utc)
    s = gr.stats(sh["x"]["scoped"])
    pub = {"books": {"x": {"n": 5, "mean_pct": round(100 * s["mean_pct"], 3),
                           "t": round(s["t"], 2)}},
           "updated": now.isoformat(), "ttl_sec": 43200}
    assert ea.calibrate(sh, pub)[0] is True
    pub["books"]["x"]["n"] = 4
    ok, bad = ea.calibrate(sh, pub)
    assert ok is False and "n 5 != published 4" in bad[0][1]


def test_calibration_compares_on_the_same_clock():
    """A close that landed AFTER the grade published is in the ledger and not
    in the grade — the gate trims to the publish instant rather than failing
    every fast book on every run."""
    now = datetime.now(timezone.utc)
    scoped = [(0.01, 1.0, now - timedelta(hours=3)),
              (0.01, 1.0, now - timedelta(hours=2)),
              (0.01, 1.0, now + timedelta(hours=1))]          # after publish
    sh = {"x": {"scoped": scoped, "rows": [], "all_time": [],
                "era_iso": None, "era_src": None}}
    s = gr.stats(scoped[:2])
    pub = {"books": {"x": {"n": 2, "mean_pct": round(100 * s["mean_pct"], 3),
                           "t": round(s["t"], 2)}},
           "updated": now.isoformat(), "ttl_sec": 43200}
    assert ea.calibrate(sh, pub)[0] is True


def test_a_refused_run_exits_2_and_publishes_nothing(tmp_path, monkeypatch):
    """The CLI must not print a table when the gate refuses."""
    ledger = tmp_path / "t.json"
    ledger.write_text('{"trades": []}')
    feed = tmp_path / "p.json"
    feed.write_text('{"bots": []}')
    bus = tmp_path / "b.json"
    bus.write_text('{"golive_readiness": {}}')
    rc = ea.main(["--ledger", str(ledger), "--feed", str(feed),
                  "--bus", str(bus)])
    assert rc == 2


# ------------------------------------------------------------ the sample

def test_shape_applies_phantom_filter_and_ledger_quarantine():
    q_pair, q_bot, lo, _hi, _why = store.LEDGER_QUARANTINE[0]
    trades = [
        {"bot": f"{q_bot}-x", "pair": q_pair, "pnl_pct": 0.01, "pnl_abs": 1.0,
         "opened_at": f"{lo}T01:00:00+00:00", "closed_at": f"{lo}T02:00:00+00:00",
         "reason": "long_x", "entry_price": 1.0},                     # quarantined
        {"bot": f"{q_bot}-x", "pair": "ETH", "pnl_pct": 0.0, "pnl_abs": 0.0,
         "opened_at": "2026-08-21T01:00:00+00:00",
         "closed_at": "2026-08-21T02:00:00+00:00", "reason": "x"},   # phantom
        {"bot": f"{q_bot}-x", "pair": "ETH", "pnl_pct": 0.02, "pnl_abs": 2.0,
         "opened_at": "2026-08-22T01:00:00+00:00",
         "closed_at": "2026-08-22T02:00:00+00:00", "reason": "long_x",
         "entry_price": 1.0},
    ]
    sh = ea.shape(trades)
    assert len(sh[f"{q_bot}-x"]["rows"]) == 1


def test_shape_refuses_a_ledger_that_returned_exactly_its_own_cap(tmp_path):
    ledger = tmp_path / "t.json"
    ledger.write_text('{"trades": [' + ",".join(["{}"] * 7) + "]}")
    with pytest.raises(SystemExit):
        ea.load(ledger=str(ledger), feed=str(ledger), bus=str(ledger), limit=7)


def test_side_falls_back_to_the_reason_prefix_and_never_guesses():
    assert ea.side_of({"side": "short", "reason": "long-x_y"}) == "short"
    assert ea.side_of({"reason": "short-divergence_sl"}) == "short"
    assert ea.side_of({"reason": "long_stop"}) == "long"
    assert ea.side_of({"reason": "delisted"}) is None
    assert ea.side_of({"reason": "longing_x"}) is None


# ------------------------------------------------------------ metrics

def test_concentration_flags_three_trades_carrying_a_losing_rest():
    rows = [_row(i, -0.01, -1.0) for i in range(10)] + \
           [_row(20 + i, 0.10, 10.0) for i in range(3)]
    c = ea.concentration(rows)
    assert c["top3_share_of_net"] > 1.0
    assert c["ex_top3_mean_pct"] < 0
    assert c["best3_of_gross_wins"] == pytest.approx(1.0)


def test_a_losing_book_gets_no_share_of_net():
    c = ea.concentration([_row(i, -0.01, -1.0) for i in range(5)])
    assert "top1_share_of_net" not in c and "top_coin" not in c
    assert c["worst_coin"] == "X"


def test_breakeven_cost_is_never_negative():
    assert ea.breakeven_cost_bps(-0.01) == (0.0, 0.0)
    bps, mult = ea.breakeven_cost_bps(0.0035, 17.5)
    assert bps == pytest.approx(35.0) and mult == pytest.approx(2.0)


def test_recovery_is_none_when_never_regained_and_streak_ignores_zeros():
    abss = [1.0, 1.0, -3.0, 0.0, -1.0, -1.0, 5.0]
    closes = [T0 + timedelta(hours=i) for i in range(len(abss))]
    r = ea.risk_metrics([a / 100 for a in abss], abss, closes)
    assert r["max_consec_loss"] == 2
    assert r["recovered"] is True and r["recovery_days"] > 0
    r2 = ea.risk_metrics([0.01, -0.02], [1.0, -2.0], closes[:2])
    assert r2["recovered"] is False and r2["recovery_days"] is None


def test_profit_factor_is_none_not_inf_with_no_losses():
    m = ea.shape_metrics([0.01, 0.02], [1.0, 2.0])
    assert m["profit_factor"] is None


# ------------------------------------------------------------ monte carlo

def test_bootstrap_paths_are_scaled_to_the_book_through_the_clip():
    """+1% per trade on a $100 clip in a $1,000 book is +0.1% of book per
    trade — a 120-trade path is +12%, never +120%."""
    mc = ea.monte_carlo([0.01] * 20, [1.0] * 20, closes_per_year=120.0,
                        draws=20, cost_mults=(0.0,), horizons_months=(12,))
    h = mc["horizons"]["12m@0x"]
    assert h["trades"] == 120
    assert h["ret_p50"] == pytest.approx(0.12)
    assert mc["clip_usd"] == pytest.approx(100.0)


def test_added_cost_lowers_every_path():
    mc = ea.monte_carlo([0.001] * 30, [0.1] * 30, closes_per_year=365.0,
                        draws=30, cost_mults=(0.0, 1.0), horizons_months=(3,),
                        rt_bps=20.0)
    h0, h1 = mc["horizons"]["3m@0x"], mc["horizons"]["3m@1x"]
    assert h1["ret_p50"] < h0["ret_p50"]
    # 10bps/trade on a 20bps cost -> every trade nets -10bps -> P(loss) = 1
    assert h1["p_loss"] == 1.0 and h0["p_loss"] == 0.0


def test_block_bootstrap_preserves_blocks():
    import random
    seq = [1, 2, 3, 4, 5, 6]
    out = ea.block_bootstrap(seq, random.Random(1), block=3, k=6)
    assert len(out) == 6
    # every 3-run is a wrapped consecutive triple of the source
    for i in range(0, 6, 3):
        a, b, c = out[i:i + 3]
        assert (b - a) % 6 == 1 and (c - b) % 6 == 1


def test_n_for_significance_is_none_for_a_losing_mean():
    assert ea.n_for_significance(-0.01, 0.02) is None
    assert ea.n_for_significance(0.01, 0.02) == 16     # (2*0.02/0.01)^2


# ------------------------------------------------------------ portfolio

def test_effective_bets_is_correlation_aware():
    w = {"a": 1.0, "b": 1.0, "c": 1.0}
    full = {("a", "b"): (1.0, 9), ("a", "c"): (1.0, 9), ("b", "c"): (1.0, 9)}
    assert ea.effective_bets(w, full) == pytest.approx(1.0)
    assert ea.effective_bets(w, {}) == pytest.approx(3.0)
    half = {("a", "b"): (1.0, 9)}
    n = ea.effective_bets(w, half)
    assert 1.0 < n < 3.0


def test_correlation_uses_overlapping_days_only():
    a = {i: (1.0 if i % 2 else -1.0) for i in range(1, 12)}
    b = dict(a)
    del b[11]
    b[99] = 50.0                     # a day `a` did not trade
    cm = ea.correlation_matrix({"a": a, "b": b}, min_overlap=10)
    rho, n = cm[("a", "b")]
    assert rho == pytest.approx(1.0) and n == 10


# ------------------------------------------------------------ verdicts

def test_verdict_classes():
    base = {"n": 40, "mean_pct": -0.01, "se_pct": 0.001,
            "concentration": {"ex_top3_mean_pct": -0.02}, "lower_bound_pct": 0.0}
    assert ea.verdict(base, {}, False) == "refuted"
    base["se_pct"] = 0.02
    assert ea.verdict(base, {}, False) == "losing-underpowered"
    base.update(mean_pct=0.01, se_pct=0.001)
    assert ea.verdict(base, {}, False) == "concentrated"
    base["concentration"]["ex_top3_mean_pct"] = 0.005
    base["lower_bound_pct"] = 0.005
    assert ea.verdict(base, {}, True) == "established"
    assert ea.verdict(base, {}, False) == "positive-unproven"
    assert ea.verdict({"n": 3, "mean_pct": 0.1, "se_pct": 0.1}, {}, True) == "too-thin"


def test_oos_rejects_a_founding_claim_the_live_interval_excludes():
    a = {"n": 100, "mean_pct": -0.002, "se_pct": 0.001}
    assert ea.oos_check("band-kelly-lshadow", a)["verdict"] == "rejects-claim"
    a["mean_pct"] = 0.005
    assert ea.oos_check("band-kelly-lshadow", a)["verdict"] == "reproduces"
    assert ea.oos_check("pm-turnbull-lshadow", a)["verdict"] == "no-founding-number"


def test_multiplicity_counts_every_tested_book_in_m():
    audits = {"w": {"t": 4.0, "n": 50, "mean_pct": 0.01},
              "l": {"t": -3.0, "n": 50, "mean_pct": -0.01},
              "z": {"t": 0.5, "n": 50, "mean_pct": 0.001}}
    bh = ea.fleet_multiplicity(audits)
    assert bh["m"] == 3 and bh["survivors"] == ["w"]
    assert bh["positive_untested_by_bh"] == ["z"]


# ------------------------------------------------------------ moves nothing

def test_the_audit_moves_nothing():
    with open(ea.__file__) as fh:
        src = fh.read()
    src = src[:src.index("def _selftest")]
    tree = ast.parse(src)
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    calls |= {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for forbidden in ("write_levers", "get_lever", "market_open",
                      "market_close", "publish", "set_lever"):
        assert forbidden not in calls, forbidden


def test_selftest_runs_green():
    ea._selftest()
