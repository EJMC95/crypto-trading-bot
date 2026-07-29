"""The shadow books' growth surface — levers, universe widening, adaptive gate.

WHY THIS FILE EXISTS (2026-07-30, operator: "every bot needs every tool at its
disposal and every bot needs the ability to grow").

Before this change SIX books had ZERO registered levers — the Yield Harvester,
Counterweight, Snap Back, Index Rider, Tide Rider and the Perp Sniper. The
growth rail could not move a single knob on any of them, including
`carry.enter_apr`, the best-performing gate in the fleet. "The ability to grow"
is registry membership plus a consumer that actually reads it, and they had
neither.

Each test names the failure it prevents. The two failure classes that matter:

  * A LEVER THAT IS REGISTERED BUT NOT CONSUMED — the growth rail shows it
    enacted on the bus and no trade changes. This is the same shape as the
    17-Jul FLEET_RISK_MODE finding (a switch only some consumers honoured) and
    the (em)-era "code was right and never running" class.
  * A WIDENING THAT BECOMES A DEPENDENCY — a book that shrinks, or stops
    trading, because an ORGAN is down. Every widening here must degrade to the
    operator's configured list, never below it.
"""
import fleet_tuning
import pytest

import funding_carry_bot as carry
import lighter_dislocation_bot as disloc
import lighter_funding_spread_bot as spread
import lighter_index_bot as index_bot
import lighter_perp_sniper as sniper
import lighter_trend_bot as trend

pytestmark = pytest.mark.autonomy


# --------------------------------------------------------------------------
# 1. The registry: the six books have a lever surface at all, and it is caged.
# --------------------------------------------------------------------------

BOOK_LEVERS = [
    "carry.enter_apr", "carry.max_positions",
    "fundspread.k", "fundspread.universe_n",
    "disloc.enter_pct", "disloc.universe_n",
    "index.max_open", "trend.rank_by_funding", "sniper.surge_mult",
]


@pytest.mark.parametrize("name", BOOK_LEVERS)
def test_book_lever_is_registered_and_bounded(name):
    spec = fleet_tuning.LEVERS.get(name)
    assert spec, f"{name} unregistered — an unregistered lever cannot be moved"
    assert spec["lane"] == "lighter-books"
    assert spec["lo"] < spec["hi"], "a lever whose bounds collapse cannot grow"
    # every one of these books is a $1k SHADOW book; none may ever be a live
    # lever name, which is what the live-prefix owner rules key off.
    assert not name.startswith("live."), "shadow books must never mint live levers"


def test_book_lane_is_enactable_and_author_bound():
    assert "lighter-books" in fleet_tuning.ENACT_LANES, \
        "lane absent from ENACT_LANES -> get_lever returns the default forever"
    assert "lighter-books" in fleet_tuning.AUTHOR_LANES["evidence-board"]
    # the growth rail gains NO new reach into real money
    for author in ("scout-tuner", "experiment-judge", "event-sentinel"):
        assert "lighter-books" not in fleet_tuning.AUTHOR_LANES[author]
    assert fleet_tuning._author_may_write(
        "carry.enter_apr", "lighter-books", "evidence-board")
    assert not fleet_tuning._author_may_write(
        "carry.enter_apr", "lighter-books", "event-sentinel"), \
        "an author bound to its own lane must not reach the books"


def test_book_levers_clamp_to_their_cage():
    # the registry is the cage; a wild value must be clamped, never honoured
    assert fleet_tuning.clamp("carry.max_positions", 9999) == 20
    assert fleet_tuning.clamp("carry.max_positions", 0) == 6
    assert fleet_tuning.clamp("fundspread.k", 99) == 12
    assert fleet_tuning.clamp("disloc.enter_pct", 2.0) == 0.999
    assert fleet_tuning.clamp("trend.rank_by_funding", 5) == 1


def test_farmer_liquidity_floor_is_now_reachable_by_the_judge():
    # Finding: MIN_VOL=$10M excluded 5 of the venue's 8 most extreme funding
    # books. The floor must be explorable on the shadow twin and promotable
    # only by the judge — never an env flip on the live arm.
    for name in ("xp.funding.min_vol", "live.funding.min_vol"):
        spec = fleet_tuning.LEVERS[name]
        assert spec["lo"] == 2e6 and spec["hi"] == 20e6
    assert fleet_tuning._author_may_write(
        "live.funding.min_vol", "lighter-live", "experiment-judge")
    assert not fleet_tuning._author_may_write(
        "live.funding.min_vol", "lighter-live", "evidence-board"), \
        "the judge is the ONLY writer of live.funding.* — unchanged by this work"


# --------------------------------------------------------------------------
# 2. The consumers: apply_tuning() actually moves the value the bot gates on.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod,lever,attr,value", [
    (carry, "carry.enter_apr", "ENTER_APR", 2.40),
    (carry, "carry.max_positions", "MAX_POSITIONS", 16),
    (spread, "fundspread.k", "K", 10),
    (spread, "fundspread.universe_n", "UNIVERSE_N", 75),
    (disloc, "disloc.enter_pct", "ENTER_PCT", 0.95),
    (disloc, "disloc.universe_n", "UNIVERSE_N", 25),
    (index_bot, "index.max_open", "MAX_OPEN", 7),
])
def test_apply_tuning_moves_the_real_module_global(monkeypatch, mod, lever,
                                                   attr, value):
    """A registered lever with no consumer is the 'enacted but inert' class."""
    original = getattr(mod, attr)

    class _Rail:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return value if name == lever else default

    monkeypatch.setattr(mod, "tuning", _Rail)
    try:
        moved = mod.apply_tuning()
        assert moved.get(lever) == value, f"{lever} did not reach {mod.__name__}"
        assert getattr(mod, attr) == value
    finally:
        setattr(mod, attr, original)


def test_trend_rank_by_funding_lever_is_a_bool_consumer(monkeypatch):
    original = trend.RANK_BY_FUNDING

    class _Rail:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return 0 if name == "trend.rank_by_funding" else default

    monkeypatch.setattr(trend, "tuning", _Rail)
    try:
        trend.RANK_BY_FUNDING = True
        assert trend.apply_tuning() == {"trend.rank_by_funding": 0}
        assert trend.RANK_BY_FUNDING is False, "int lever -> bool consumer"
    finally:
        trend.RANK_BY_FUNDING = original


@pytest.mark.parametrize("mod", [carry, spread, disloc, index_bot, trend])
def test_dark_or_sick_rail_never_stops_a_book(monkeypatch, mod):
    """A dark rail leaves the operator's defaults in force; a RAISING rail is
    caught. An exception here would land inside a live trading loop."""
    monkeypatch.setattr(mod, "tuning", None)
    assert mod.apply_tuning() == {}

    class _Sick:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            raise RuntimeError("rail is sick")

    monkeypatch.setattr(mod, "tuning", _Sick)
    assert mod.apply_tuning() == {}, "a raising rail must not propagate"


# --------------------------------------------------------------------------
# 3. The universe widening: adds to the core, never becomes a dependency.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod", [spread, disloc])
def test_universe_widening_adds_but_never_shrinks(monkeypatch, mod):
    class _Bus:
        @staticmethod
        def scout_universe(min_vol_m=0.0, current_time=None):
            return ["SOL", "BTC", "DOGE"]      # BTC duplicates the core

    monkeypatch.setattr(mod, "fleet_bus", _Bus)
    assert mod.resolve_universe(["BTC", "ETH"], 4, 1.0) == \
        ["BTC", "ETH", "SOL", "DOGE"], "core first, in order; scout dedups"
    assert mod.resolve_universe(["BTC", "ETH"], 0, 1.0) == ["BTC", "ETH"], \
        "width 0 is the revert switch"
    # a width BELOW the core size must not truncate the validated core
    assert mod.resolve_universe(["BTC", "ETH", "SOL"], 1, 1.0) == \
        ["BTC", "ETH", "SOL"], "the configured core is never dropped"


@pytest.mark.parametrize("mod", [spread, disloc])
def test_universe_widening_degrades_to_the_configured_list(monkeypatch, mod):
    """The widening must be an ENHANCEMENT, never a DEPENDENCY: no organ
    outage may shrink a book's universe or stop it trading."""
    class _Dark:
        @staticmethod
        def scout_universe(min_vol_m=0.0, current_time=None):
            return []                      # dark/stale scout

    class _Raising:
        @staticmethod
        def scout_universe(min_vol_m=0.0, current_time=None):
            raise RuntimeError("bus down")

    for bus in (_Dark, _Raising, None):
        monkeypatch.setattr(mod, "fleet_bus", bus)
        assert mod.resolve_universe(["BTC", "ETH"], 40, 1.0) == ["BTC", "ETH"]


# --------------------------------------------------------------------------
# 4. Snap Back's adaptive gate — the 40x-above-the-median finding.
# --------------------------------------------------------------------------

def test_adaptive_gate_never_enters_inside_its_own_round_trip():
    """The gate tracks the venue, but a capture smaller than the spread+slip
    that earns it is a losing trade wearing a signal's clothes."""
    calm = [1.0] * 99 + [500.0]
    assert disloc.adaptive_enter_bps(calm, 0.98, 40.0, 1.5, 150.0, 20) == 60.0


def test_adaptive_gate_is_capped_at_the_operator_constant():
    """This is a re-basing DOWN from a stale constant, not a licence to widen
    past the operator's number."""
    wild = [80.0] * 50 + [4000.0] * 50
    assert disloc.adaptive_enter_bps(wild, 0.98, 40.0, 1.5, 150.0, 20) == 150.0


def test_adaptive_gate_uses_the_percentile_between_floor_and_cap():
    assert disloc.adaptive_enter_bps([90.0] * 100, 0.98, 40.0, 1.5,
                                     150.0, 20) == 90.0


def test_adaptive_gate_refuses_a_thin_or_junk_sample():
    """A thin sample cannot describe a distribution; guessing LOW here would
    open trades on noise — so it must fall back to the configured constant."""
    assert disloc.adaptive_enter_bps([200.0] * 5, 0.98, 40.0, 1.5, 150.0, 20) == 150.0
    assert disloc.adaptive_enter_bps([], 0.98, 40.0, 1.5, 150.0, 20) == 150.0
    assert disloc.adaptive_enter_bps([None, "x"], 0.98, 40.0, 1.5, 150.0, 20) == 150.0


def test_adaptive_gate_is_side_blind():
    """A CHEAP book dislocates as tradeably as a rich one — the gate is on
    |residual|, and a sign leak here would blind the book to half its signal."""
    assert disloc.adaptive_enter_bps([-90.0] * 100, 0.98, 40.0, 1.5,
                                     150.0, 20) == 90.0


# --------------------------------------------------------------------------
# 5. The optimised defaults, pinned so a silent revert is visible.
# --------------------------------------------------------------------------

def test_optimised_defaults_are_what_shipped():
    # carry was measured AT 7 open of 8 — the fleet's biggest earner turning
    # away graded candidates.
    assert carry.MAX_POSITIONS == 12
    # Counterweight was measured AT its cap: 10 open = exactly K=5 x 2 legs.
    assert spread.K == 8
    assert spread.UNIVERSE_N == 60
    # Snap Back's gate was 40x its own median residual.
    assert disloc.ENTER_PCT == 0.98 and disloc.UNIVERSE_N == 40
    # Index Rider carried the fleet's LARGEST clip on a book with zero closes.
    assert index_bot.ORDER_USD == 100.0
    assert len(index_bot.SYMBOLS) == 10, "the venue's non-crypto set"
    # every widened sleeve must have a rule, or the symbol is dead weight
    for sym in index_bot.SYMBOLS:
        assert sym in index_bot.SLEEVES, f"{sym} has no sleeve rule"
    # Tide Rider now ranks by the signal class that actually earns here.
    assert trend.RANK_BY_FUNDING is True


# --------------------------------------------------------------------------
# 6. The Perp Sniper's second candidate source — the population problem.
# --------------------------------------------------------------------------

def test_surge_candidates_selects_by_ratio_and_orders_by_strength():
    rows = [{"sym": "AAA", "ratio": 3.5}, {"sym": "BBB", "ratio": 9.0},
            {"sym": "CCC", "ratio": 1.2}]
    assert sniper.surge_candidates(rows, 3.0, set()) == ["BBB", "AAA"], \
        "strongest surge first; below-multiple rows excluded"


def test_surge_candidates_requires_the_dedup_ledger():
    """Every surging book is already in `baseline` (seeded with all active
    markets), so baseline cannot dedup this source. Without `already`, a book
    that keeps surging re-enters `pending` every loop, forever."""
    rows = [{"sym": "AAA", "ratio": 5.0}]
    assert sniper.surge_candidates(rows, 3.0, set()) == ["AAA"]
    assert sniper.surge_candidates(rows, 3.0, {"AAA"}) == [], \
        "an already-handled surge must never be re-offered"


def test_surge_candidates_is_bounded_and_junk_tolerant():
    many = [{"sym": f"S{i}", "ratio": 10.0} for i in range(20)]
    assert len(sniper.surge_candidates(many, 3.0, set())) == 3, \
        "one venue-wide volume event must not flood the snipe pass"
    junk = [{"sym": None, "ratio": "x"}, {"ratio": 9.0}, "notadict"]
    assert sniper.surge_candidates(junk, 3.0, set()) == []
    assert sniper.surge_candidates(None, 3.0, set()) == []


def test_surge_source_is_disabled_by_a_zero_multiple():
    assert sniper.SURGE_MULT == 3.0, "starts aligned with the scout's own detector"
    # mult 0 admits everything, which is why the LOOP gates on SURGE_MULT > 0
    # rather than relying on this function to be the switch.
    assert sniper.surge_candidates([{"sym": "A", "ratio": 0.1}], 0.0, set()) == ["A"]
    import inspect
    src = inspect.getsource(sniper.main)
    assert "SURGE_MULT > 0" in src, \
        "the loop must gate the second source on the disable switch"


def test_sniper_lever_moves_the_multiple(monkeypatch):
    original = sniper.SURGE_MULT

    class _Rail:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return 6.0 if name == "sniper.surge_mult" else default

    monkeypatch.setattr(sniper, "tuning", _Rail)
    try:
        assert sniper.apply_tuning() == {"sniper.surge_mult": 6.0}
        assert sniper.SURGE_MULT == 6.0
    finally:
        sniper.SURGE_MULT = original


# --------------------------------------------------------------------------
# 7. Scope hygiene — configured universes that contain symbols the venue
#    does not list (measured 2026-07-30: family 2/15 dead, spread 5/30 dead).
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod", [spread, disloc])
def test_prune_dead_drops_unlisted_symbols(mod):
    live, dead = mod.prune_dead(["BTC", "ATOM", "ETH", "ALGO"],
                                lambda c: c in {"BTC", "ETH"})
    assert live == ["BTC", "ETH"] and dead == ["ATOM", "ALGO"]


@pytest.mark.parametrize("mod", [spread, disloc])
def test_prune_dead_never_empties_a_book_on_a_venue_error(mod):
    """An unreachable venue must not silently prune the whole universe — a
    book with no coins trades nothing, which is the failure this work exists
    to remove, not create."""
    def _boom(_c):
        raise RuntimeError("venue unreachable")

    live, dead = mod.prune_dead(["BTC", "ETH"], _boom)
    assert live == ["BTC", "ETH"] and dead == []


# --------------------------------------------------------------------------
# 8. The Perp Sniper's THIRD source — the debut-regime cohort.
# --------------------------------------------------------------------------

def test_young_candidates_prefers_the_youngest_liquid_book():
    bars = {"NEWA": 3, "NEWB": 10, "OLD": 400}
    vols = {"NEWA": 1.0, "NEWB": 2.0, "OLD": 50.0}
    assert sniper.young_candidates(bars, 21, vols, 0.25, set(), 5) == \
        ["NEWA", "NEWB"], "youngest first; a book past the bar is excluded"


def test_young_candidates_requires_real_turnover():
    """A debut with no turnover is a ghost print — this bot's own history is
    full of one-sided debut books it could not fill."""
    bars = {"GHOST": 2, "REAL": 4}
    vols = {"GHOST": 0.0, "REAL": 1.0}
    assert sniper.young_candidates(bars, 21, vols, 0.25, set(), 5) == ["REAL"]


def test_young_candidates_dedups_and_bounds():
    bars = {f"S{i}": 2 for i in range(10)}
    vols = {f"S{i}": 1.0 for i in range(10)}
    assert len(sniper.young_candidates(bars, 21, vols, 0.25, set(), 2)) == 2
    got = sniper.young_candidates(bars, 21, vols, 0.25, {"S0", "S1"}, 10)
    assert "S0" not in got and "S1" not in got, \
        "a young book is in `baseline`, so it needs the same dedup ledger"


def test_young_candidates_tolerates_junk():
    assert sniper.young_candidates(None, 21, {}, 0.0, set(), 5) == []
    assert sniper.young_candidates({"A": "x", None: 3}, 21, {"A": 9}, 0.0,
                                   set(), 5) == []


def test_sniper_probe_cache_is_monotone_by_construction():
    """A book gets older, never younger — so `not_young` may be permanent, and
    that is what keeps the candle-probe cost decaying to zero."""
    import inspect
    src = inspect.getsource(sniper.main)
    assert "not_young.add" in src and "YOUNG_PROBE_BUDGET" in src, \
        "the probe must be governed and its exclusion set permanent"
    assert sniper.YOUNG_MAX_BARS == 21 and sniper.YOUNG_PROBE_BUDGET == 4
