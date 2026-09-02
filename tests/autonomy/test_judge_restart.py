"""[2026-08-27 (vm)] THE JUDGE JUDGES NOTHING, AND IT WAS BOOKKEEPING.

MEASURED before this suite: `experiment_judge.run_once` hit a whole-function
`return save(stood_down)` keyed on `_bus.live_arm_retired(LIVE_BOT)` — 💸 the
Farmer's retired live arm — and BOTH production `paired_eval` call sites sit
below it. `paired_eval` is the sole producer of `promote: True`, so the fleet's
ONLY designed path from shadow evidence to more real money ran **zero times per
cycle**, for all four pairs, because one pair's live arm is retired. The four
`pairs` entries above that return are a read-only precheck: a census of four,
judging none.

What this file pins, and what it deliberately does NOT:

  * the stand-down is PER-PAIR (`lane_stood_down`) — and the farmer STAYS
    stood down, under a live census, a dark census and a wrong lane. That is
    the mutation that matters most here: this repo's one retired real-money
    arm must not be handed back to the candidate machine by a refactor whose
    whole point is to let the machine run.
  * `power` and `eta_judgeable` ride EVERY pair state, not only `idle`;
  * `no_closes` is a distinct reason from `policy_unstamped` — 👩 mum's
    `{live: "0/0", shadow: "0/8"}` was accusing a host file that has no bug;
  * the published MDE is the PER-HALF rung (1.414x the full-window one, and
    cleared twice), off ONE owner shared with `paired_eval`;
  * no promotion bar moved, and the judge is still the SOLE WRITER of
    `live.funding.*` (AST, over the whole tree).

Every fixture is PUBLISHER-SHAPED and pinned as such: `test_the_fixtures_carry
_the_publishers_own_keys` diffs the ledger and bot_pnl row shapes against the
keys `bot_pnl_store.fetch_paper_trades` / `fetch_bot_pnl` actually construct,
read off their AST. A hand-written fixture with an invented key name is this
repo's single most repeated defect.
"""
import ast
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import experiment_judge as ej          # noqa: E402
import fleet_bus as fb                 # noqa: E402
import fleet_tuning                    # noqa: E402


@pytest.fixture(autouse=True)
def _georgia_live_for_mechanics(monkeypatch):
    """[(wg)] This file demonstrates the parking mechanism with 💸 the FARMER as
    the retired lane and the OTHER pairs as live controls. 🔮 georgia's live arm
    is now retired too (fleet_bus.RETIRED_LIVE_ARMS), which would make her a
    SECOND parked lane and move the sets these tests assert. Force her live so
    the farmer stays the single retired example under test; that georgia parks
    when retired is the same per-pair mechanism, owned by
    test_georgia_live_retired.py and the bus=None scoping tests below."""
    monkeypatch.setenv("GEORGIA_LIVE_RETIRED_OVERRIDE", "run")


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T0 = 1_800_000_000.0                   # the judge's own selftest clock


# ---------------------------------------------------------------------------
# Publisher-shaped fixtures. Keys are pinned against the real publishers below.
# ---------------------------------------------------------------------------
def _led(bot, pol=None, age=60, pct=0.01, exit_reason="trade"):
    """One `fetch_paper_trades` row, as that function CONSTRUCTS it."""
    return {"bot": bot, "pair": "BTC/USDC", "profit_abs": 1.0,
            "profit_ratio": pct, "enter_tag": "long",
            "exit_reason": exit_reason, "duration_min": 10.0,
            "open_ts": ej.iso(T0 - age - 600), "close_ts": ej.iso(T0 - age),
            "is_open": False, "venue": "lighter",
            "open_rate": 100.0, "close_rate": 101.0,
            "extra": ({"policy": pol} if pol else {})}


def _row(bot, max_open=5, age=60):
    """One `fetch_bot_pnl` row, as that function CONSTRUCTS it."""
    return {"bot": bot, "updated_at": ej.iso(T0 - age), "status": "online",
            "equity": 1000.0, "pnl_abs": 0.0, "pnl_pct": 0.0,
            "open_trades": 0, "closed_trades": 0, "wins": 0, "losses": 0,
            "extra": {"max_open": max_open}}


def _publisher_dict_keys(func_name, path="bot_pnl_store.py"):
    """The literal dict keys a publisher builds, off its own AST."""
    tree = ast.parse(open(os.path.join(ROOT, path)).read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == func_name)
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict) and len(node.keys) > 6:
            return {k.value for k in node.keys if isinstance(k, ast.Constant)}
    raise AssertionError(f"no constructed dict found in {func_name}")


def _bot_pnl_select_cols():
    """`fetch_bot_pnl` returns `dict(zip(cols, row))` off its own SELECT, so
    the column list IS the key list — read it out of the SQL literal."""
    tree = ast.parse(open(os.path.join(ROOT, "bot_pnl_store.py")).read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_bot_pnl")
    sql = "".join(n.value for n in ast.walk(fn)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and ("SELECT" in n.value or "FROM bot_pnl" in n.value))
    body = sql.split("SELECT", 1)[1].split("FROM", 1)[0]
    return {c.strip() for c in body.split(",") if c.strip()}


def test_the_fixtures_carry_the_publishers_own_keys():
    led = _publisher_dict_keys("fetch_paper_trades")
    assert set(_led("x")) == led, (
        "ledger fixture drifted from fetch_paper_trades' constructed dict: "
        f"missing={led - set(_led('x'))} extra={set(_led('x')) - led}")
    cols = _bot_pnl_select_cols()
    got = set(_row("x"))
    # fetch_bot_pnl renames nothing; it only re-serialises `updated_at`.
    assert got == cols, f"bot_pnl fixture drift: {got ^ cols}"


# ---------------------------------------------------------------------------
# 1. THE STAND-DOWN IS PER-PAIR — and the farmer stays parked.
# ---------------------------------------------------------------------------
FARMER = fb.JUDGED_PAIRS["farmer"]["live_bot"]
GEORGIA = fb.JUDGED_PAIRS["georgia"]["live_bot"]


def test_the_serial_lane_is_derived_from_the_row_it_trades():
    """Not a second hardcoded "farmer" — the pair naming LIVE_BOT as its live
    arm IS the lane, so a slot swap cannot leave the gate aimed at a row the
    machine no longer trades (the defect that produced this whole entry)."""
    assert ej.serial_lane_id() == "farmer"
    assert ej.serial_lane_id(GEORGIA) == "georgia"
    assert ej.serial_lane_id("no-such-row") is None


def test_a_retired_arm_parks_only_its_own_lane():
    """The property the whole-function `return` did not have: one pair's
    retirement must not stand down the other three."""
    pairs = {"farmer": {"phase": "stood_down", "stood_down": {"why": "retired"}},
             "georgia": {"phase": "idle"}, "mum": {"phase": "unjudgeable"},
             "avo": {"phase": "idle"}}
    parked, lane, why = ej.lane_stood_down(pairs, bus=None)
    assert parked is True and lane == "farmer" and why["why"] == "retired"
    # ...and the same census, asked about georgia's lane, admits it.
    parked_g, lane_g, why_g = ej.lane_stood_down(pairs, live_bot=GEORGIA, bus=None)
    assert parked_g is False and lane_g == "georgia" and why_g is None


def test_another_pairs_stand_down_does_not_park_this_lane():
    """The mirror, and the one a naive 'any pair retired' rewrite would fail."""
    pairs = {"farmer": {"phase": "idle"},
             "georgia": {"phase": "stood_down", "stood_down": {"why": "x"}}}
    parked, lane, _ = ej.lane_stood_down(pairs, bus=None)
    assert parked is False and lane == "farmer"


def test_a_dark_census_still_parks_the_retired_lane():
    """FAIL-CLOSED. `pair_census` degrades to {} on a dark bot_pnl fetch, and
    an empty census must never read as 'nobody is retired' and hand a RETIRED
    REAL-MONEY ARM back to the candidate machine."""
    for census in ({}, None, {"farmer": {"phase": "idle"}}):
        parked, lane, why = ej.lane_stood_down(census, bus=fb)
        assert parked is True, (census, "the farmer must stay stood down")
        assert lane == "farmer"
        assert "retired" in str(why.get("why", "")).lower(), why
    # and the bus arm is pair-scoped too: georgia is NOT retired.
    assert ej.lane_stood_down({}, live_bot=GEORGIA, bus=fb)[0] is False


def test_lane_census_counts_what_the_judge_is_actually_judging():
    pairs = {"farmer": {"phase": "stood_down"}, "georgia": {"phase": "unjudgeable"},
             "mum": {"phase": "unjudgeable"}, "avo": {"phase": "idle"},
             "ghost": {"phase": "promoted-ish"}}
    c = ej.lane_census(pairs)
    assert c["live"] == ["avo"] and c["stood_down"] == ["farmer"]
    assert c["unjudgeable"] == ["georgia", "mum"]
    assert c["unknown"] == ["ghost"], "an unmapped phase must not be absorbed"
    assert c["judging"] == "1 of 5" and c["serial_lane"] == "farmer"


# ---------------------------------------------------------------------------
# 2. run_once end-to-end: parked lane, published lanes, ZERO lever writes.
# ---------------------------------------------------------------------------
class _FakeStore:
    def __init__(self, rows, bot_rows):
        self.rows, self.bot_rows, self.saved = rows, bot_rows, {}

    def load_state_checked(self, key):
        return True, {}

    def load_state(self, key):
        return None

    def fetch_paper_trades(self, limit=4000):
        return list(self.rows)

    def fetch_bot_pnl(self):
        return list(self.bot_rows)

    def save_state(self, key, payload):
        self.saved[key] = payload
        return True


@pytest.fixture
def judged(monkeypatch):
    """run_once against publisher-shaped data, with every side effect that
    could touch a lever or a phone replaced by a recording spy."""
    rows, bot_rows = [], []
    for pid, ps in fb.JUDGED_PAIRS.items():
        bot_rows += [_row(ps["live_bot"]), _row(ps["shadow_bot"])]
        pol = {f: "same" for f in ps["policy_fields"]}
        for i in range(12):
            rows += [_led(ps["live_bot"], pol, age=60 + i * 3600),
                     _led(ps["shadow_bot"], pol, age=60 + i * 3600)]
    store = _FakeStore(rows, bot_rows)
    calls = {"paired_eval": 0, "write_levers": 0, "push": 0}

    _real_eval = ej.paired_eval

    def _spy_eval(*a, **kw):
        calls["paired_eval"] += 1
        return _real_eval(*a, **kw)

    def _spy_write(*a, **kw):
        calls["write_levers"] += 1
        return None

    monkeypatch.setattr(ej, "store", store)
    monkeypatch.setattr(ej, "paired_eval", _spy_eval)
    monkeypatch.setattr(ej.tuning, "write_levers", _spy_write)
    monkeypatch.setattr(ej, "send_push", lambda *a, **kw: calls.__setitem__(
        "push", calls["push"] + 1))
    monkeypatch.setattr(ej, "now_ts", lambda: T0)
    ej.run_once()
    return store.saved.get(ej.KEY), calls


def test_run_once_parks_the_farmer_and_writes_no_lever(judged):
    payload, calls = judged
    assert payload is not None, "the judge must still publish a state"
    assert payload["phase"] == "stood_down"
    assert payload["last_eval"]["lane"] == "farmer"
    assert calls["write_levers"] == 0, (
        "a stood-down lane must not re-assert — not asserting IS the release")
    assert calls["paired_eval"] == 0, (
        "no promotion machinery may run for a retired real-money arm")


def test_run_once_says_which_lanes_are_not_parked(judged):
    """The 'judges 0 of 4' fact, published rather than derived by every
    reader from four nested phases."""
    payload, _ = judged
    assert set(payload["pairs"]) == set(fb.JUDGED_PAIRS)
    lanes = payload["lanes"]
    assert lanes["serial_lane"] == "farmer"
    assert lanes["stood_down"] == ["farmer"]
    assert set(lanes["live"]) | set(lanes["unjudgeable"]) == \
        set(fb.JUDGED_PAIRS) - {"farmer"}
    assert lanes["judging"].endswith(f"of {len(fb.JUDGED_PAIRS)}")
    # `note` is printed and never persisted, so the fact that this parks ONE
    # lane has to be on the payload — a stand-down that reads as fleet-wide is
    # exactly what shipped.
    assert set(payload["last_eval"]["lanes_not_parked"]) == \
        set(fb.JUDGED_PAIRS) - {"farmer"}, payload["last_eval"]


# ---------------------------------------------------------------------------
# 3. `no_closes` — an empty ledger is not an unstamped one.
# ---------------------------------------------------------------------------
def _precheck(pid, rows, bot_rows, now=T0):
    return ej._pair_precheck(pid, fb.JUDGED_PAIRS[pid], rows, bot_rows, now)


def test_an_empty_ledger_reads_no_closes_and_accuses_no_host_file():
    """👩 mum, exactly as measured: `{live: "0/0", shadow: "0/8"}`. The old
    rung published `policy_unstamped` naming `lighter_avo_live_bot.py` — a
    file that stamps 30/30 for 🔮 georgia off the same code."""
    ps = fb.JUDGED_PAIRS["mum"]
    rows = [_led(ps["shadow_bot"], None, age=60 + i * 60) for i in range(8)]
    st = _precheck("mum", rows, [_row(ps["live_bot"]), _row(ps["shadow_bot"])])
    assert st["phase"] == "unjudgeable"
    assert st["unjudgeable"]["reason"] == "no_closes", st
    assert st["stamps"] == {"live": "0/0", "shadow": "0/8"}, st
    d = st["unjudgeable"]["detail"]
    assert ps["live_bot"] in d and "0 closes" in d, d
    assert ps["shadow_bot"] not in d, "the shadow arm HAS closes — do not name it"
    assert "NOT a stamping defect" in d, d
    assert "trade" in st["unjudgeable"]["wake_when"], st


def test_an_unstamped_but_trading_arm_still_reads_policy_unstamped():
    """The negative control. `no_closes` must not swallow the reason it was
    split out of — a stamping gap on an arm that DOES trade still names the
    stamper (a reason that fires on everything trains the operator to ignore
    it)."""
    ps = fb.JUDGED_PAIRS["mum"]
    rows = ([_led(ps["shadow_bot"], None, age=60 + i * 60) for i in range(8)]
            + [_led(ps["live_bot"], None, age=60 + i * 60) for i in range(5)])
    st = _precheck("mum", rows, [_row(ps["live_bot"]), _row(ps["shadow_bot"])])
    assert st["unjudgeable"]["reason"] == "policy_unstamped", st
    assert st["stamps"] == {"live": "0/5", "shadow": "0/8"}, st


def test_no_closes_is_reported_before_a_capacity_delta_can_hide_it():
    """Rung order: an arm that has never traded cannot be diagnosed as a cap
    mismatch. Both arms empty, caps deliberately divergent."""
    ps = fb.JUDGED_PAIRS["avo"]
    st = _precheck("avo", [], [_row(ps["live_bot"], max_open=5),
                               _row(ps["shadow_bot"], max_open=6)])
    assert st["unjudgeable"]["reason"] == "no_closes", st
    assert ps["live_bot"] in st["unjudgeable"]["detail"]
    assert ps["shadow_bot"] in st["unjudgeable"]["detail"]


# ---------------------------------------------------------------------------
# 4. power + eta_judgeable on EVERY state.
# ---------------------------------------------------------------------------
def _pair_rows(ps, n_live=14, n_shadow=28, pol=None, pct=0.01):
    out = []
    for i in range(n_live):
        out.append(_led(ps["live_bot"], pol, age=60 + i * 900,
                        pct=pct * (1 + 0.1 * (i % 5))))
    for i in range(n_shadow):
        out.append(_led(ps["shadow_bot"], pol, age=60 + i * 900,
                        pct=pct * (1 + 0.1 * (i % 5))))
    return out


_AVO_POL = {f: "same" for f in fb.JUDGED_PAIRS["avo"]["policy_fields"]}


def _rows_matched(ps):
    return _pair_rows(ps, pol=dict(_AVO_POL))


def _rows_diverged(ps):
    """Same shape, one field apart -> policy_mismatch."""
    return (_pair_rows(ps, n_live=14, n_shadow=0, pol=dict(_AVO_POL))
            + _pair_rows(ps, n_live=0, n_shadow=28,
                         pol=dict(_AVO_POL, stoploss=-0.99)))


@pytest.mark.parametrize("rows_fn,expect,reason", [
    (lambda ps: [], "unjudgeable", "no_closes"),
    (_rows_diverged, "unjudgeable", "policy_mismatch"),
    (_rows_matched, "idle", None),
])
def test_power_and_eta_ride_every_pair_state(rows_fn, expect, reason):
    ps = fb.JUDGED_PAIRS["avo"]
    st = _precheck("avo", rows_fn(ps),
                   [_row(ps["live_bot"]), _row(ps["shadow_bot"])])
    assert st["phase"] == expect, st
    assert (st.get("unjudgeable") or {}).get("reason") == reason, st
    assert isinstance(st["power"], dict), (
        "the power report was published on `idle` ONLY — the blocked pairs "
        "are exactly the ones whose closes/day decides whether to bother")
    assert "eta_judgeable" in st, st
    for arm in ("live", "shadow"):
        assert set(st["power"][arm]) == {"n", "sd_pct", "closes_per_day"}


def test_a_stood_down_pair_still_publishes_its_power():
    ps = fb.JUDGED_PAIRS["farmer"]
    st = _precheck("farmer", _pair_rows(ps),
                   [_row(ps["live_bot"]), _row(ps["shadow_bot"])])
    assert st["phase"] == "stood_down", st
    assert isinstance(st["power"], dict) and st["power"]["shadow"]["n"] > 0


def test_eta_judgeable_names_the_binding_term_and_is_a_floor():
    """Same idiom as `golive_readiness.gate_horizon`: one term per gate, the
    binding one is the MAX, and the answer is the date the bar can OPEN."""
    ps = fb.JUDGED_PAIRS["avo"]
    power = ej._pair_power(_pair_rows(ps, n_live=14, n_shadow=28),
                           ps["live_bot"], ps["shadow_bot"], ps, T0)
    eta = ej._eta_judgeable(power, T0)
    # 14 closes / 14d = 1.0/d live -> 10/1 = 10d; 28/14 = 2.0/d shadow ->
    # 30/2 = 15d; window floor 7d. The shadow arm binds.
    assert eta["terms"] == {"window": 7.0, "live_closes": 10.0,
                            "shadow_closes": 15.0}, eta
    assert eta["binding"] == "shadow_closes" and eta["days"] == 15.0, eta
    assert eta["kind"] == "floor" and "not pass" in eta["why"], eta
    assert eta["eta"] == ej.iso(T0 + 15.0 * 86400.0)[:10], eta


def test_eta_judgeable_refuses_to_price_a_dead_arm():
    """FAIL-SAFE: one arm with no rate makes the ANSWER None with that arm
    named — never a date computed off the arm that still moves, which would
    read as a real ETA (I1: the smaller arm decides)."""
    ps = fb.JUDGED_PAIRS["avo"]
    power = ej._pair_power(_pair_rows(ps, n_live=0, n_shadow=28),
                           ps["live_bot"], ps["shadow_bot"], ps, T0)
    eta = ej._eta_judgeable(power, T0)
    assert eta["days"] is None and eta["eta"] is None, eta
    assert eta["binding"] == "live_closes", eta
    assert eta["terms"]["live_closes"] is None, eta
    assert ej._eta_judgeable(None, T0) is None
    assert ej._eta_judgeable("junk", T0) is None


def test_eta_judgeable_uses_the_clock_it_was_handed():
    """The (va) lesson: a date off `now_ts()` inside a function given a `now`
    is undriveable and disagrees with every other field on the payload."""
    ps = fb.JUDGED_PAIRS["avo"]
    power = ej._pair_power(_pair_rows(ps), ps["live_bot"], ps["shadow_bot"],
                           ps, T0)
    a = ej._eta_judgeable(power, T0)
    b = ej._eta_judgeable(power, T0 + 10 * 86400.0)
    assert a["eta"] != b["eta"], (a, b)


# ---------------------------------------------------------------------------
# 5. The MDE describes the rung that actually binds.
# ---------------------------------------------------------------------------
def test_half_floors_is_the_bar_paired_eval_itself_uses():
    """ONE owner. A retyped floor is how the power report came to describe a
    rung `paired_eval` does not use — pinned by identity, on the AST."""
    assert ej.half_floors() == (15, 5)
    assert ej.half_floors(min_closes=8, live_min=4) == (4, 3)   # the max() arms
    src = ast.parse(open(os.path.join(ROOT, "experiment_judge.py")).read())
    fn = next(n for n in ast.walk(src)
              if isinstance(n, ast.FunctionDef) and n.name == "paired_eval")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "half_floors" in called, (
        "paired_eval must take its per-half floors from the shared owner")


def test_the_published_mde_is_the_per_half_rung():
    """[(vm)] It read `1.28*sd*sqrt(1/30+1/10)` — the FULL-WINDOW floors —
    while the binding rung is the per-half one at sqrt(1/15+1/5), which is
    sqrt(2) wider AND must be cleared twice. The old number under-stated the
    real detection threshold by 41% on the gate that rejects first."""
    ps = fb.JUDGED_PAIRS["avo"]
    power = ej._pair_power(_pair_rows(ps, n_live=14, n_shadow=28),
                           ps["live_bot"], ps["shadow_bot"], ps, T0)
    assert power["mde_pp_half"] > power["mde_pp_full_window"] > 0, power
    ratio = power["mde_pp_half"] / power["mde_pp_full_window"]
    # sqrt((1/15+1/5)/(1/30+1/10)) = sqrt(2) exactly; the tolerance is the
    # 3dp rounding both numbers are published at, nothing else.
    assert abs(ratio - math.sqrt(2.0)) < 0.02, (ratio, power)
    assert power["mde_pp_at_floors"] == power["mde_pp_half"], (
        "the headline key must carry the BINDING rung, or a consumer keeps "
        "silently reading the looser number under the old name")
    hs, hl = ej.half_floors()
    assert abs(power["mde_pp_half"]
               - ej.MDE_Z * max(power[a]["sd_pct"] for a in ("live", "shadow"))
               * math.sqrt(1 / hs + 1 / hl)) < 0.02, power
    assert power["margin_pp"] == ej.MARGIN_PP


def test_the_mde_constant_is_owned_here_not_borrowed_from_allocation():
    """Same 1.28, different owner — `fleet_allocation.Z_LOWER` is a LIVE ENV
    LEVER (`ALLOC_Z_LOWER`), so importing it would let a capital-allocation
    tightening silently move the judge's published power report."""
    assert ej.MDE_Z == 1.28
    # ON THE AST, not a page-wide substring scan: the deliberate-non-import is
    # explained in a COMMENT that names both, so a text scan fails on the very
    # sentence promising the property (this repo's own recorded trap).
    tree = ast.parse(open(os.path.join(ROOT, "experiment_judge.py")).read())
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imported.add(n.module or "")
    assert "fleet_allocation" not in imported, imported


# ---------------------------------------------------------------------------
# 6. Nothing here moved a bar, and the judge is still the sole writer.
# ---------------------------------------------------------------------------
def test_no_promotion_bar_moved():
    """Explicitly pinned because the cheap way to make this judge 'work' is to
    lower `live >= 10` — the SMALLER arm, which dominates the standard error.
    Dropping it to 5 takes false-promote from ~8-12% to ~16%: speed bought by
    being WRONG more often about real money."""
    assert ej.MIN_CLOSES == 30 and ej.LIVE_MIN_CLOSES == 10
    assert ej.MIN_DAYS == 7.0 and ej.MARGIN_PP == 0.5
    assert ej.half_floors() == (15, 5)


def test_the_judge_is_the_sole_writer_of_live_funding():
    """AST over the whole tree: no module other than this one may author a
    lever write as `experiment-judge`, and the registry must still name it the
    only owner of the `live.funding.` prefix."""
    assert fleet_tuning._LIVE_PREFIX_OWNERS["live.funding."] == "experiment-judge"
    for author in fleet_tuning.AUTHOR_LANES:
        may = fleet_tuning._author_may_write(
            "live.funding.enter_apr", "lighter-live", author)
        assert may == (author == "experiment-judge"), author
    # DECLARED, not silent — the BORN_DARK_OK idiom. fleet_tuning's own
    # selftest calls write_levers as every author, including this one, to drive
    # the authorization it owns; it authors nothing at runtime.
    sole_writer_ok = {"fleet_tuning.py", "experiment_judge.py"}
    offenders = []
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith(".py") or name in sole_writer_ok:
            continue
        try:
            tree = ast.parse(open(os.path.join(ROOT, name)).read())
        except (SyntaxError, UnicodeDecodeError):        # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            fname = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if fname != "write_levers":
                continue
            for kw in node.keywords:
                if kw.arg == "set_by" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value == "experiment-judge":
                    offenders.append(f"{name}:{node.lineno}")
    assert not offenders, (
        f"only experiment_judge.py may write as the judge; found {offenders}")


def test_the_pair_surface_is_publish_only():
    """None of the census/power/lane code may reach an actuator. Asserted on
    the AST of the functions themselves, not by a page-wide substring scan —
    this file's own prose contains every one of these words."""
    tree = ast.parse(open(os.path.join(ROOT, "experiment_judge.py")).read())
    banned = {"write_levers", "market_open", "release_lever", "send_push"}
    for fname in ("_pair_precheck", "_pair_power", "_eta_judgeable",
                  "pair_census", "lane_stood_down", "lane_census",
                  "serial_lane_id", "half_floors"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == fname)
        called = {getattr(c.func, "attr", None) or getattr(c.func, "id", None)
                  for c in ast.walk(fn) if isinstance(c, ast.Call)}
        assert not (called & banned), (fname, called & banned)
