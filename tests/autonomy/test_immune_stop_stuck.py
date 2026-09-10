"""[2026-09-09 (zv)] A LIVE LEG SITTING THROUGH ITS OWN STOP MUST PAGE.

THE GAP, measured on origin/main 2faa3a1: the variant host that runs both
real-money books catches a REFUSED close, prints one line to the container log
and `continue`s (`close {sym} failed: ... — position keeps its manager`). The
row's only reject telemetry sits in the ENTRY branch; `status` stays `online`;
`grep -nE 'close_fail|exit_fail|close_reject|stop_fail'` over the host returns
nothing. Between "the stop should have fired" and "the daily-loss halt fired"
NOTHING pages — `flatten_stuck_sickness` only sees a halted row, and the
watchdog only sees a dead one. The memory `a-venue-403-kills-a-live-book-
silently` records the class at 8.2h dark.

WHAT THE ROW DOES CARRY is venue truth: `extra.margin.positions[sym]` with the
venue's own entry / size / value (mark notional), beside `extra.policy.stoploss`
and `policy.sides`. Every fixture below is 👩 mum's and 🙏 avo's REAL published
shape from the 9-Sep 06:03Z /pnl.json capture, field for field, with one leg
moved. The detector is out-of-process by design (I13): the in-process retry is
behaving exactly as written, and its log line reads like safety.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fleet_immune as fi   # noqa: E402

pytestmark = pytest.mark.autonomy

NOW = 1_788_930_000.0


def _mum(spy_value=237.827238, status="online", age=248, policy=True,
         margin=True, sides=("long",), stop=-0.04):
    """freqtrade-mum-lighter as published 2026-09-09T06:03Z: 4 legs, cross
    margin, leverage 1.65x. `spy_value` moves SPY's mark notional — its entry
    is 765.86 at size 0.3102, so 237.83 is +0.11% and 223.0 is -6.1%."""
    pol = {"roi": {"0": 0.02, "1440": 0.0}, "sides": list(sides),
           "venue": "lighter_live", "stoploss": stop,
           "strategy": "oversold-1h", "coin_veto": True}
    mg = {"n": 4, "mode": "cross", "gross": 961.283015,
          "equity": 581.344753, "leverage": 1.6536, "liq_none": [],
          "positions": {
              "SPY": {"mode": "cross", "size": 0.3102, "entry": 765.86,
                      "value": spy_value, "margin": 0.0, "imf_pct": 6.66},
              "XAU": {"mode": "cross", "size": 0.0547, "entry": 4379.47,
                      "value": 240.891689, "margin": 0.0, "imf_pct": 6.66},
              "COIN": {"mode": "cross", "size": 1.332, "entry": 180.661,
                       "value": 240.960132, "margin": 0.0, "imf_pct": 10.0},
              "MORPHO": {"mode": "cross", "size": 102.3, "entry": 2.34917,
                         "value": 241.603956, "margin": 0.0, "imf_pct": 20.0}},
          "collateral": 578.14953, "nearest_liq": None}
    return {"bot": "freqtrade-mum-lighter", "status": status,
            "equity": 580.85, "pnl_abs": 60.43, "open_trades": 4,
            "age_sec": age,
            "extra": {"svc": "mum-live", "max_open": 12, "gross_x": 5.0,
                      "held": {"SPY": "oversold-rebound",
                               "XAU": "oversold-rebound",
                               "COIN": "oversold-rebound",
                               "MORPHO": "oversold-rebound"},
                      **({"policy": pol} if policy else {}),
                      **({"margin": mg} if margin else {})}}


def _avo(btc_value=146.704152):
    """freqtrade-avo-maria-lighter, same capture: 6 legs, -10% stop. BTC
    entry 78252.9 at size 0.00186 — 146.70 is +0.79%."""
    return {"bot": "freqtrade-avo-maria-lighter", "status": "online",
            "equity": 443.8, "open_trades": 6, "age_sec": 18,
            "extra": {"svc": "tide-rider-lighter-live", "max_open": 6,
                      "policy": {"sides": ["long"], "venue": "lighter_live",
                                 "stoploss": -0.1, "strategy": "swing-dip-4h"},
                      "margin": {"mode": "cross", "positions": {
                          "BTC": {"size": 0.00186, "entry": 78252.9,
                                  "value": btc_value},
                          "MON": {"size": 6539.3, "entry": 0.02451,
                                  "value": 169.760228},
                          "SPY": {"size": 0.0946, "entry": 767.17,
                                  "value": 72.538334},
                          "XAU": {"size": 0.0165, "entry": 4397.3,
                                  "value": 72.672105},
                          "XMR": {"size": 0.144, "entry": 510.774,
                                  "value": 72.6876},
                          "NVDA": {"size": 0.654, "entry": 226.415,
                                   "value": 148.061022}}}}}


def _shadow():
    """A paper twin — never a real-money verdict, and it publishes no
    `margin` block anyway."""
    return {"bot": "freqtrade-mum-lshadow", "status": "online",
            "open_trades": 1, "age_sec": 475,
            "extra": {"svc": "family-lighter-shadow",
                      "held": {"BNB": "oversold-rebound"}}}


# --------------------------------------------------------------- the finding
def test_a_leg_through_its_stop_pages_once_it_is_stuck_rather_than_in_flight():
    seen = {}
    rows = [_mum(spy_value=223.0), _avo(), _shadow()]     # SPY at -6.1%
    # first sighting starts the clock and says nothing — the manager gets
    # its pass
    assert fi.stop_stuck_sickness(rows, seen, NOW) == []
    assert seen == {"freqtrade-mum-lighter:SPY": NOW}
    # still inside three trading passes
    assert fi.stop_stuck_sickness(rows, seen, NOW + fi.STOP_STUCK_S - 1) == []
    # past it: the stop has had three passes and the leg is still on
    out = fi.stop_stuck_sickness(rows, seen, NOW + fi.STOP_STUCK_S + 1)
    assert [o["organ"] for o in out] == ["freqtrade-mum-lighter"], out


def test_the_healthy_rows_in_the_same_payload_stay_silent():
    """The (hh) rule, and the capture itself: at 06:03Z every one of the ten
    real legs sat between +0.1% and +0.8% — the shipped payload must read
    CLEAN, or the detector pages on day one and trains ignoring."""
    seen = {}
    rows = [_mum(), _avo(), _shadow()]
    assert fi.stop_stuck_sickness(rows, seen, NOW) == []
    assert fi.stop_stuck_sickness(rows, seen, NOW + 100_000) == []
    assert seen == {}


def test_the_detail_names_the_service_the_coin_and_the_numbers_i8():
    seen = {"freqtrade-mum-lighter:SPY": NOW}
    out = fi.stop_stuck_sickness([_mum(spy_value=223.0)], seen, NOW + 1800)
    d = out[0]["detail"]
    assert "mum-live" in d, d            # the Railway service to open
    assert "SPY" in d, d                 # the leg
    assert "-6.1" in d and "-4.0%" in d, d   # where it sits vs the stop
    assert "30 min" in d, d
    assert "NOT EXECUTING" in d, d


def test_the_overshoot_allowance_is_the_venues_slippage_not_a_missed_stop():
    """mum's measured stop overshoot: p90 51.7bps, worst 62.4bps (n=7). A leg
    at -4.5% is a stop that fired late, not one that did not fire. -5.5% is
    through the 1.0pp allowance."""
    seen = {}
    late = _mum(spy_value=765.86 * 0.3102 * (1 - 0.045))    # -4.5%
    fi.stop_stuck_sickness([late], seen, NOW)
    assert seen == {}, "inside the overshoot allowance must not start a clock"
    through = _mum(spy_value=765.86 * 0.3102 * (1 - 0.055))  # -5.5%
    fi.stop_stuck_sickness([through], seen, NOW)
    assert seen == {"freqtrade-mum-lighter:SPY": NOW}


def test_a_short_only_book_reads_the_leg_the_other_way():
    """The margin block carries no side, so the SIDE comes from policy.sides:
    a short-only book at a HIGHER mark is the one through its stop."""
    row = _mum(spy_value=765.86 * 0.3102 * 1.06, sides=("short",))  # +6%
    seen = {}
    fi.stop_stuck_sickness([row], seen, NOW)
    assert seen == {"freqtrade-mum-lighter:SPY": NOW}
    # ...and the same mark on a LONG book is a winner, not a finding
    seen2 = {}
    fi.stop_stuck_sickness([_mum(spy_value=765.86 * 0.3102 * 1.06)], seen2, NOW)
    assert seen2 == {}


# ------------------------------------------------------------- the fail-safes
def test_a_stale_row_is_not_a_live_verdict_i1():
    seen = {}
    stale = _mum(spy_value=223.0, age=fi.STALE_ROW_S + 60)
    assert fi.stop_stuck_sickness([stale], seen, NOW) == []
    assert seen == {}
    assert fi.stop_stuck_sickness([stale], seen, NOW + 100_000) == []


def test_a_halted_book_belongs_to_the_flatten_detector():
    """After the daily-loss halt the host `continue`s past position
    management by design and retries the flatten; that shape is
    flatten_stuck_sickness's, and two pages for one condition is noise."""
    seen = {}
    row = _mum(spy_value=223.0, status="halted")
    fi.stop_stuck_sickness([row], seen, NOW)
    assert fi.stop_stuck_sickness([row], seen, NOW + 100_000) == []
    assert seen == {}


@pytest.mark.parametrize("kw", [dict(policy=False), dict(margin=False),
                                dict(stop=None), dict(stop="x"),
                                dict(stop=0.04), dict(sides=("long", "short")),
                                dict(sides=())])
def test_a_row_that_cannot_be_read_is_silent_never_guessed(kw):
    """Absence is deploy latency, not sickness; a mixed-side book cannot be
    read from a side-less margin block, and a guessed side is a wrong number
    on real money."""
    seen = {}
    row = _mum(spy_value=223.0, **kw)
    fi.stop_stuck_sickness([row], seen, NOW)
    assert fi.stop_stuck_sickness([row], seen, NOW + 100_000) == []
    assert seen == {}


def test_a_paper_row_that_grew_a_margin_block_is_not_real_money():
    row = _mum(spy_value=223.0)
    row["bot"] = "freqtrade-mum-lshadow"
    row["extra"]["policy"]["venue"] = "lighter_shadow"
    seen = {}
    fi.stop_stuck_sickness([row], seen, NOW)
    assert fi.stop_stuck_sickness([row], seen, NOW + 100_000) == []
    assert seen == {}


def test_a_leg_that_closes_or_recovers_is_forgotten():
    """The clock belongs to the EPISODE: a leg the manager finally closes
    must not leave a spent clock that pages the next episode on sight."""
    seen = {}
    fi.stop_stuck_sickness([_mum(spy_value=223.0)], seen, NOW)
    assert "freqtrade-mum-lighter:SPY" in seen
    # the manager closes SPY: the leg is gone from the margin block
    closed = _mum()
    del closed["extra"]["margin"]["positions"]["SPY"]
    assert fi.stop_stuck_sickness([closed], seen, NOW + 60) == []
    assert seen == {}, "a cleared leg must be forgotten"
    # a new episode starts its own clock and does not page immediately
    assert fi.stop_stuck_sickness([_mum(spy_value=223.0)], seen, NOW + 120) == []


def test_a_declared_exemption_suppresses_and_the_dict_is_empty_today():
    assert fi.STOP_STUCK_OK == {}, \
        "an exemption here excuses a real-money book from the detector built for it"
    seen = {"freqtrade-mum-lighter:SPY": NOW}
    assert fi.stop_stuck_sickness([_mum(spy_value=223.0)], seen, NOW + 5000,
                                  ok={"freqtrade-mum-lighter": "declared"}) == []


def test_junk_input_never_raises():
    for rows in (None, [], [{}], [None], [{"bot": "x-lighter"}],
                 [{"bot": "x-lighter", "extra": None}],
                 [{"bot": "x-lighter", "extra": {"policy": [], "margin": 3}}],
                 [{"bot": "x-lighter", "extra": {
                     "policy": {"stoploss": -0.04, "sides": ["long"]},
                     "margin": {"positions": {"A": None, "B": {"entry": "?"},
                                              "C": {"entry": 1, "size": 0,
                                                    "value": 1}}}}}]):
        fi.stop_stuck_sickness(rows, {}, NOW)


def test_leg_return_arithmetic():
    assert abs(fi._leg_return({"entry": 100.0, "size": 2.0, "value": 190.0},
                              "long") - (-0.05)) < 1e-9
    assert abs(fi._leg_return({"entry": 100.0, "size": 2.0, "value": 210.0},
                              "short") - (-0.05)) < 1e-9
    assert fi._leg_return({"entry": 100.0, "size": -2.0, "value": 190.0},
                          "long") is not None, "a signed size is still a size"
    for bad in ({}, None, {"entry": 0, "size": 1, "value": 1},
                {"entry": 1, "size": 1, "value": 0}, {"entry": "x"}):
        assert fi._leg_return(bad, "long") is None


# ------------------------------------------------- the enforcement is not inert
def _src():
    return (ROOT / "fleet_immune.py").read_text()


def test_the_detector_is_actually_WIRED_into_the_scan():
    tree = ast.parse(_src())
    run_once = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    called = {n.func.id for n in ast.walk(run_once)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "stop_stuck_sickness" in called, \
        "the detector is defined and never called — inert enforcement"


def test_its_memory_is_read_from_and_written_back_to_the_payload():
    src = _src()
    assert 'prior.get("stop_seen")' in src, "memory never restored"
    assert '"stop_seen": stop_seen' in src, "memory never persisted"


def test_the_keys_we_consume_are_the_keys_the_publisher_actually_emits():
    """Test the consumer against what the PUBLISHERS build ((hj)): each key
    this detector reads must be a literal dict key in the file that actually
    emits it, or the detector goes silently blind on exactly the books it was
    built for."""
    def _keys(fname):
        tree = ast.parse((ROOT / fname).read_text())
        return {k.value for n in ast.walk(tree) if isinstance(n, ast.Dict)
                for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    # the live host publishes the row (`policy`, `margin`), the family's
    # policy_stamp builds the policy dict (`stoploss`, `sides`), and the
    # venue client's margin_state builds the margin block (`positions`)
    for fname, wanted in (("lighter_avo_live_bot.py", ("policy", "margin")),
                          ("lighter_family_bot.py", ("stoploss", "sides")),
                          ("venues/lighter_client.py", ("positions",))):
        keys = _keys(fname)
        for k in wanted:
            assert k in keys, f"{fname} no longer publishes {k!r} as a dict key"


def test_the_bar_is_three_trading_passes_and_the_allowance_clears_measured_overshoot():
    """900s = 3 x LOOP_SECONDS (300); 1.0pp is ~2x mum's worst measured stop
    overshoot (62.4bps). Both are env-tunable, neither may drift to a value
    that pages on ordinary slippage or waits out a whole halt."""
    assert 600.0 <= fi.STOP_STUCK_S <= 1800.0, fi.STOP_STUCK_S
    assert 0.7 <= fi.STOP_OVERSHOOT_PP <= 2.0, fi.STOP_OVERSHOOT_PP
