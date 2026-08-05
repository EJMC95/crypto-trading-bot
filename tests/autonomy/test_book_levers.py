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
import lighter_band_barnes_bot as barnes
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
    # [2026-07-30 (hk)] Tide Rider's rate levers. `trend.rank_by_funding` was
    # its ONLY lever and is inert by construction (it reorders admission, and
    # candidates never exceeded slots — max simultaneously-golden coins over
    # 192 aligned days was ONE against six). A book whose sole lever cannot
    # change what it trades has no growth rail; these three can.
    "trend.universe_n", "trend.min_vol_m", "trend.max_open",
    # [2026-08-03] 🌾 carry's LIQUIDITY FLOOR — the gate that was actually
    # binding while the two registered ones had slack. The book sat at 6 of 12
    # slots and went 98.9h without an OPEN because only 14 of 203 books clear
    # $2M of 24h turnover (median book $0.043M); its own hot list was 13-16x
    # below the floor and KAITO missed by $2,000.
    "carry.min_vol",
    # [2026-08-03] FOUND BY THE COMPLETENESS TEST BELOW ON ITS FIRST RUN, not
    # by a human: `disloc.exit_bps` — the fleet's FIRST exit lever, shipped
    # (gu) 30-Jul — was registered on this lane and listed nowhere here, so it
    # had no cage assertion, no consumer assertion and no auto-revert
    # assertion for four days. It is correctly wired (verified: consumed in
    # `apply_tuning` and present in `_ENV_DEFAULTS`), so this was a coverage
    # hole rather than a live defect — which is exactly the shape that stays
    # invisible until the lever misbehaves.
    "disloc.exit_bps",
    # [2026-08-05] 🎸 Barnesy — registered AT BIRTH, and BIRTH-FROZEN at the
    # consumer: apply_tuning refuses the rail until BARNES_FREEZE_UNTIL
    # ((hm) — a book whose bars move accrues zero gradeable closes). The
    # dedicated freeze tests below prove BOTH halves: frozen = nothing
    # moves; thawed = the lever reaches the module global.
    "barnes.enter_apr", "barnes.max_positions", "barnes.k",
    # [2026-08-06 (kl)] I18 — the gates Barnesy's OWN CENSUS names as binding,
    # which were bare literals with no lever, no cage and no reader. Its three
    # birth levers are all tighten-only or inert on a starved sleeve, so the
    # book LOOKED tunable and could not move: 218 scanned, cold 201, thin 15,
    # waiting 2, eligible 0, and the nearest candidate's ETA moved AWAY over
    # an hour as thin books dipped and their persistence clocks were deleted.
    # Defaults UNCHANGED — reach, not payoff, exactly as (it) recorded.
    "barnes.persist_h", "barnes.carry_min_vol", "barnes.extreme_min_vol",
    "barnes.xsect_universe_n",
]


def test_every_lighter_books_lever_is_listed_here():
    """THE CLASS-CLOSER, and it is here because this file failed to catch its
    own gap. `BOOK_LEVERS` is hand-written, so when `carry.min_vol` was
    registered the 104 tests in this file passed *around* it — green, and
    covering nothing. A list that must be updated by hand is a list that will
    not be, and the failure is silent and reassuring.

    So the registry is the source of truth in the completeness direction: any
    lever on the `lighter-books` lane MUST appear above and inherit every
    assertion in this file. The hand-written list keeps its own teeth in the
    other direction — a lever DISAPPEARING from the registry still fails.

    Mutation that turns this red: register a `lighter-books` lever and do not
    list it.
    """
    registered = {n for n, s in fleet_tuning.LEVERS.items()
                  if s.get("lane") == "lighter-books"}
    missing = sorted(registered - set(BOOK_LEVERS))
    assert not missing, (
        f"registered on lighter-books but untested here: {missing} — "
        "add them to BOOK_LEVERS; a registered lever with no test is the "
        "'registered but inert' class this file exists to prevent")


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
    # [2026-08-05 (ka)] lo 2e6 -> 1e5 on BOTH cages, operator-signed ("if it
    # produces better numbers then proceed") against the thin-tier replay
    # (STUDY_THIN_TIER_MIN_VOL_2026-08-05: band01 alone +$14.83/30d, both
    # halves positive, robust at p90). Both los move together by mechanism:
    # a static candidate must clamp clean in BOTH cages, so an xp-only
    # floor is unexercisable — the judge selftest mutation-pins that.
    for name in ("xp.funding.min_vol", "live.funding.min_vol"):
        spec = fleet_tuning.LEVERS[name]
        assert spec["lo"] == 1e5 and spec["hi"] == 20e6
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
    (carry, "carry.min_vol", "MIN_DAY_VOLUME", 1.5e6),
    (spread, "fundspread.k", "K", 10),
    (spread, "fundspread.universe_n", "UNIVERSE_N", 75),
    (disloc, "disloc.enter_pct", "ENTER_PCT", 0.95),
    (disloc, "disloc.universe_n", "UNIVERSE_N", 25),
    (disloc, "disloc.exit_bps", "EXIT_BPS", 20.0),
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


def test_barnes_birth_freeze_refuses_the_rail_then_admits_it(monkeypatch):
    """🎸 Barnesy's levers are wired AND birth-frozen ((hm)): while the freeze
    holds, a rail offering values must move NOTHING — otherwise the book's
    first 30 days accrue zero gradeable closes, which is the whole reason the
    book exists. After the freeze the standard consumer contract applies, so
    day 31 needs no deploy. Both halves asserted, or 'frozen' is just a word
    in a docstring."""
    frozen = barnes._freeze_until_ts() - 86400.0
    thawed = barnes._freeze_until_ts() + 86400.0
    original = barnes.MAX_POSITIONS

    class _Rail:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return 8 if name == "barnes.max_positions" else default

    monkeypatch.setattr(barnes, "tuning", _Rail)
    try:
        assert barnes.apply_tuning(frozen) == {}, \
            "the birth freeze must refuse the rail outright"
        assert barnes.MAX_POSITIONS == original, "a frozen lever moved a global"
        moved = barnes.apply_tuning(thawed)
        assert moved == {"barnes.max_positions": 8}, \
            "after the freeze the lever must reach the module global"
        assert barnes.MAX_POSITIONS == 8
    finally:
        barnes.MAX_POSITIONS = original


def test_barnes_freeze_fails_closed_on_an_unparseable_stamp(monkeypatch):
    """A typo'd BARNES_FREEZE_UNTIL must freeze FOREVER, never unfreeze — the
    fail-closed direction for a rule whose failure mode is silent tuning."""
    monkeypatch.setattr(barnes, "FREEZE_UNTIL_ISO", "not-a-date")
    assert barnes.freeze_active(9e12), \
        "an unparseable freeze stamp must read as frozen, not as thawed"


def test_barnes_dark_rail_is_a_noop_even_after_the_freeze(monkeypatch):
    monkeypatch.setattr(barnes, "tuning", None)
    assert barnes.apply_tuning(barnes._freeze_until_ts() + 1) == {}

    class _Sick:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            raise RuntimeError("rail is sick")

    monkeypatch.setattr(barnes, "tuning", _Sick)
    assert barnes.apply_tuning(barnes._freeze_until_ts() + 1) == {}, \
        "a raising rail must not propagate into a trading loop"


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
    # Counterweight: the (fz) widening (K 5->8, universe 30->60) was REVERTED
    # 4-Aug (jg) by its OWN pre-registered criterion — n rose, t FELL (0.65 ->
    # -0.44), mean -0.361%/trade, -$16.01 MTM fleet-worst — back to the config
    # both validations actually cleared (K=5 over the hand list; the (ia)
    # Lighter re-run's universe is the bot's own COINS list). Width 30 == the
    # 30-name hand list, so no scout book is added. This pin exists to make a
    # SILENT revert visible; a documented one moves the pin with its reason.
    assert spread.K == 5
    assert spread.UNIVERSE_N == 30
    # Snap Back's gate was 40x its own median residual.
    assert disloc.ENTER_PCT == 0.98 and disloc.UNIVERSE_N == 40
    # Index Rider carried the fleet's LARGEST clip on a book with zero closes.
    # [2026-07-30 (hl)] $100 -> $65. The 15% go-live drawdown bar was ALREADY
    # BREACHED at 9x$100 — measured 21.60% (lag0) / 23.88% (lag1) realised on
    # 10y, graded through golive_readiness.stats() itself. Per-trade % is
    # invariant to clip, so this costs exactly zero expectancy while scaling
    # dollar drawdown linearly; capping concurrency instead would have bought
    # the same safety with 58% of realised P&L and 2.3pp of mean per trade.
    assert index_bot.ORDER_USD == 65.0
    # MAX_OPEN is a LITERAL now, not len(SYMBOLS): a cap defined as the
    # universe size can never bind, and it was the one lever the drift guard
    # had to be blinded to (DRIFT_OK) — where it had already drifted 10 vs 9.
    assert index_bot.MAX_OPEN == 9
    import scripts.audit_lever_bounds as _alb
    assert "index.max_open" not in _alb.DRIFT_OK, \
        "re-adding this exemption re-blinds the drift arm on the lever most able to drift"
    # [2026-07-30 (hk)] 10 -> 9: XAG REMOVED. (fz) added it under `sma_cross`
    # while this same file's reject list said "don't re-test: XAG (+1.2%
    # regime / 55% DD cross)" — naming the very rule it was shipped under —
    # and an independent 2y measure corroborates 38.7% maxDD against a 15%
    # gate. WTI/XCU stay: their reject notes quote regime200 and they ship as
    # sma_cross, a rule that sweep never tested for them; both are DECLARED in
    # SLEEVE_EXEMPT with that reasoning.
    assert len(index_bot.SYMBOLS) == 9, "the venue's non-crypto set, less XAG"
    assert "XAG" not in index_bot.SYMBOLS and "XAG" not in index_bot.SLEEVES
    # every widened sleeve must have a rule, or the symbol is dead weight
    for sym in index_bot.SYMBOLS:
        assert sym in index_bot.SLEEVES, f"{sym} has no sleeve rule"
    # and no sleeve ships against its own reject list without a stated reason
    for sym in index_bot.SYMBOLS:
        if sym in index_bot.REJECTED_SLEEVES:
            assert sym in index_bot.SLEEVE_EXEMPT, (
                f"{sym} is on REJECTED_SLEEVES with no declared exemption — "
                f"re-testing a rejected sleeve needs a recorded reason")
    # Tide Rider now ranks by the signal class that actually earns here.
    assert trend.RANK_BY_FUNDING is True
    # [(hl)] 5.0 -> 3.0: measured, 3.0 admits ZEC ($3.38M) and PAXG which carry
    # 91% of the whole delta; 2.0 buys 6 more trades and LOWERS the mean
    # (+8.52% -> +7.93%). 3.0 is where candidates stop paying for themselves.
    assert trend.MIN_VOL_M == 3.0
    # trend.max_open hi is a SAFETY bound: at >=10 the -10% daily-loss halt
    # becomes reachable before the -35% catastrophic stop, and in shadow that
    # halt skips the whole scan — no death cross, no seatbelt, for the rest of
    # the UTC day. Max simultaneously-golden books measured over 500 days: 6.
    assert fleet_tuning.LEVERS["trend.max_open"]["hi"] == 9


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


# --------------------------------------------------------------------------
# 9. AUTO-REVERT — the growth rail's central safety property.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod,lever,attr,moved", [
    (carry, "carry.enter_apr", "ENTER_APR", 2.40),
    (carry, "carry.max_positions", "MAX_POSITIONS", 16),
    (carry, "carry.min_vol", "MIN_DAY_VOLUME", 1.5e6),
    (spread, "fundspread.k", "K", 10),
    (disloc, "disloc.enter_pct", "ENTER_PCT", 0.95),
    (disloc, "disloc.exit_bps", "EXIT_BPS", 20.0),
    (index_bot, "index.max_open", "MAX_OPEN", 7),
    (sniper, "sniper.surge_mult", "SURGE_MULT", 6.0),
])
def test_an_expired_lever_reverts_to_the_operator_default(monkeypatch, mod,
                                                          lever, attr, moved):
    """THE ONE-WAY RATCHET. `get_lever` returns its `default` when a lever is
    absent, expired or quarantined. The first cut of every apply_tuning()
    passed the CURRENT global as that default, so once a lever moved it could
    never come back — auto-revert-on-expiry is the growth rail's central
    safety property ("levers EXPIRE back to defaults on their own, so
    auto-revert is the resting state"), and it was broken on all six books.

    Mutation that turns this red: pass `cur` instead of `_ENV_DEFAULTS[attr]`.
    """
    env_default = getattr(mod, attr)

    class _Live:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return moved if name == lever else default

    class _Expired:
        """what fleet_tuning does once the TTL lapses: hand back the default"""
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return default

    try:
        monkeypatch.setattr(mod, "tuning", _Live)
        mod.apply_tuning()
        assert getattr(mod, attr) == moved, "the lever must reach the bot"
        monkeypatch.setattr(mod, "tuning", _Expired)
        mod.apply_tuning()
        assert getattr(mod, attr) == env_default, (
            f"{lever} did NOT revert on expiry — the rail is a one-way ratchet")
    finally:
        setattr(mod, attr, env_default)


def test_trend_bool_lever_also_reverts(monkeypatch):
    original = trend.RANK_BY_FUNDING

    class _Expired:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return default

    try:
        trend.RANK_BY_FUNDING = False          # as if a lever had moved it
        monkeypatch.setattr(trend, "tuning", _Expired)
        trend.apply_tuning()
        assert trend.RANK_BY_FUNDING is True, "bool lever must revert too"
    finally:
        trend.RANK_BY_FUNDING = original


@pytest.mark.parametrize("mod", [carry, spread, disloc, index_bot, sniper])
def test_every_lever_consumer_has_a_call_site(mod):
    """A defined-but-never-called apply_tuning is the registered-but-inert
    class. The sniper shipped exactly that: the function existed and no loop
    invoked it, so its lever could never reach the bot."""
    import inspect
    src = inspect.getsource(mod.main)
    assert "apply_tuning()" in src, f"{mod.__name__}.main never calls apply_tuning"


# --------------------------------------------------------------------------
# 10. The SIDE contract — a two-sided book must not report its shorts as longs.
# --------------------------------------------------------------------------

def test_snap_back_publishes_a_SIDED_held_map():
    """Snap Back is two-sided (`is_long = dev_bps < 0`) but published
    `sorted(meta.keys())` — a bare LIST, which fleet_risk.held_items maps to
    side "" and classifies as LONG. Its shorts were therefore counted as longs
    in the per-symbol pileup cap, which ships mode=enforce and is consumed by
    the family bot — so a Snap Back SHORT could veto a family LONG on the same
    symbol. Latent while the book held nothing; the 30-Jul gate/universe
    widening is exactly what activates it.
    """
    import fleet_risk

    def _sides(items):
        out = []
        for _c, v in items:
            t = str(v)
            out.append("short" if (t.upper().startswith("S")
                                   or "short" in t.lower()) else "long")
        return out

    # the OLD shape mis-signs: this is the bug, pinned so it cannot return
    assert _sides(fleet_risk.held_items(["BTC", "SOL"])) == ["long", "long"]
    # the NEW shape the bot now publishes carries the side
    assert _sides(fleet_risk.held_items({"BTC": "S", "SOL": "S"})) == \
        ["short", "short"]

    import inspect
    src = inspect.getsource(disloc.main)
    assert '"held": sorted(meta.keys())' not in src, \
        "Snap Back must publish a SIDED held map, not a bare list"
    assert '"L" if m.get("is_long") else "S"' in src


def test_every_two_sided_book_publishes_the_sided_shape():
    """The contract, applied across the fleet: a book that can hold BOTH
    sides must publish {coin: L|S}. A long-only book may publish a list."""
    import inspect
    for mod, two_sided in ((disloc, True), (spread, True), (sniper, False)):
        src = inspect.getsource(mod.main)
        if two_sided:
            assert '"held": {' in src, f"{mod.__name__} must publish a sided map"


# --------------------------------------------------------------------------
# 11. The sniper's ledger must FORGET, and its age source must be exact.
# --------------------------------------------------------------------------

def test_offered_ledger_forgets_after_its_cooldown():
    """`surge_done` was a monotone SET that only grew, so every book offered
    once was excluded FOREVER — over weeks both new candidate sources decay to
    silence, a slow-acting version of the exact starvation the source was
    added to fix. A surge is an EVENT; the ledger must expire."""
    now = 1_000_000.0
    hour = 3600.0
    done = {"OLD": now - 200 * hour, "RECENT": now - 2 * hour}
    live = sniper.active_done(done, now, cooldown_h=168)
    assert live == {"RECENT"}, live
    # ...and PRUNED in place, so the persisted payload cannot grow unbounded
    assert "OLD" not in done and "RECENT" in done


def test_offered_ledger_tolerates_junk_and_the_old_list_format():
    now = 1_000_000.0
    done = {"BAD": "not-a-timestamp", "GOOD": now}
    assert sniper.active_done(done, now, cooldown_h=168) == {"GOOD"}
    assert "BAD" not in done, "unparseable entries are dropped, not kept forever"


def test_young_source_prefers_the_exact_venue_age_over_the_probe():
    """The scout publishes `ages_d` from the venue's own `created_at`. That is
    exact, covers every book at once, and costs no extra REST — the candle
    probe is only a fallback for a dark scout."""
    import inspect
    src = inspect.getsource(sniper.main)
    assert '_sp2.get("ages_d")' in src, "the sniper must read the scout's ages"
    assert "or bar_counts" in src, "the probe cache must remain the fallback"
    # and the probe must SKIP anything the scout already answered, so the
    # REST cost goes to zero once ages_d is flowing
    assert "s not in _scout_ages" in src


def test_scout_publishes_ages_and_never_guesses_new():
    """A book whose timestamp will not parse must be ABSENT from `ages_d` —
    'age unknown' must never read as 'brand new', which would hand the sniper
    every unparseable book as a debut candidate."""
    import lighter_market_scout as scout
    now_ms = 1_700_000_000_000.0
    day = 86_400_000.0
    books = [
        {"status": "active", "symbol": "NEW", "mark_price": 1.0,
         "index_price": 1.0, "daily_quote_token_volume": 1e6,
         "created_at": now_ms - 5 * day},
        {"status": "active", "symbol": "OLD", "mark_price": 1.0,
         "index_price": 1.0, "daily_quote_token_volume": 1e6,
         "created_at": now_ms - 400 * day},
        {"status": "active", "symbol": "JUNK", "mark_price": 1.0,
         "index_price": 1.0, "daily_quote_token_volume": 1e6,
         "created_at": "not-a-number"},
    ]
    stats = scout.book_stats(books, 1e5)
    snap = scout.build_snapshot(stats, {}, {}, {}, now_ms=now_ms)
    ages = snap["ages_d"]
    assert ages["NEW"] == 5.0 and ages["OLD"] == 400.0
    assert "JUNK" not in ages, "unparseable age must be ABSENT, never 0 (=new)"


# --------------------------------------------------------------------------
# [2026-07-30 (go)] EVERY LEVERED BOOK MUST PUBLISH ITS EFFECTIVE CAP.
#
# The receipt I used to prove the (fz) deploy had landed was "`extra.caps`
# present on the row" — and it was WRONG for half the cohort: only carry,
# fundspread and index ever emitted `caps`. Dislocation, sniper and trend never
# did, so for those three the receipt could not appear no matter how many times
# they deployed, and the evidence board's saturation check had to fall back to
# the REGISTRY value — unable to tell "at the cap" from "at the cap it set
# itself last cycle", the exact ambiguity (gd) added the field to remove.
#
# Two things now depend on it, which is why this is a test and not a comment:
# the board reads it to decide whether to widen, and a human reads it to tell a
# landed deploy from a stale container.
# --------------------------------------------------------------------------

LEVERED_BOOK_MODULES = [
    "funding_carry_bot",
    "lighter_funding_spread_bot",
    "lighter_index_bot",
    "lighter_dislocation_bot",
    "lighter_perp_sniper",
    "lighter_trend_bot",
]


@pytest.mark.parametrize("mod", LEVERED_BOOK_MODULES)
def test_every_levered_book_publishes_its_effective_caps(mod):
    """A book with registered levers and no published cap is observable only
    through the registry, i.e. through the value the tuner may just have
    changed. That is not an observation."""
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parents[2]
    src = (root / f"{mod}.py").read_text()
    assert '"caps"' in src, (
        f"{mod} registers levers but never publishes extra.caps — the board "
        "must fall back to the registry, and a deploy cannot be verified")


@pytest.mark.parametrize("mod", LEVERED_BOOK_MODULES)
def test_the_published_caps_sit_inside_a_publish_payload(mod):
    """Not merely present in the file — present in the `extra=` dict of a real
    `store.publish(...)` call. A `caps` dict built and never published is the
    registered-but-inert failure one layer along.

    Checked by AST, not by text proximity. The first version of this test
    searched a 2,000-character window before each `"caps"` for `extra={` and
    `publish(` — and failed on `lighter_perp_sniper`, whose payload carries a
    long explanatory comment block that pushed the call out of the window. The
    code was correct; the heuristic was not. A structural claim wants a
    structural check."""
    import ast
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parents[2]
    tree = ast.parse((root / f"{mod}.py").read_text())

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name != "publish":
            continue
        for kw in node.keywords:
            if kw.arg != "extra" or not isinstance(kw.value, ast.Dict):
                continue
            keys = [k.value for k in kw.value.keys
                    if isinstance(k, ast.Constant)]
            if "caps" in keys:
                found.append(keys)

    assert found, (
        f"{mod}: no store.publish(extra={{...}}) call carries a 'caps' key — "
        "a cap that is computed but never published is invisible to the board")
    # the cap must be a dict of NAMED gates, not a bare number — the board
    # looks levers up by name
    assert all(isinstance(k, str) for keys in found for k in keys), found


# --------------------------------------------------------------------------
# [2026-07-30 (gs)] THE CAP MUST BE ON THE PATH THAT ACTUALLY RUNS.
#
# (go) asserted that every levered book carries `caps` inside a real
# store.publish(extra=...) call, and ⚖️ Counterweight PASSED — because its caps
# were in the `status="halted"` publish, the SafetyRails branch. A book that is
# running normally never takes that path, so the field appeared exactly when the
# book had STOPPED trading. Measured on the live row: caps=None at 23:50 with
# the book online and full at 10 of 10 legs.
#
# The lesson is narrow and worth pinning: "present in a publish call" is not the
# same claim as "present in the publish call the loop makes". The (go) test was
# true and insufficient.
# --------------------------------------------------------------------------

def _publish_status(call):
    """The literal `status=` of a store.publish call, or None if not literal."""
    import ast as _a
    for kw in call.keywords:
        if kw.arg == "status" and isinstance(kw.value, _a.Constant):
            return kw.value.value
    return None


@pytest.mark.parametrize("mod", LEVERED_BOOK_MODULES)
def test_caps_ride_the_HEALTHY_publish_not_only_an_error_path(mod):
    """At least one publish whose status is NOT a halted/error state must carry
    caps. Otherwise the cap is observable only once the book has stopped."""
    import ast as _a
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parents[2]
    tree = _a.parse((root / f"{mod}.py").read_text())

    UNHEALTHY = {"halted", "error", "stopped", "crashed", "down"}
    healthy_with_caps, statuses_with_caps = False, []
    for node in _a.walk(tree):
        if not isinstance(node, _a.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, _a.Attribute) else getattr(fn, "id", "")
        if name != "publish":
            continue
        for kw in node.keywords:
            if kw.arg != "extra" or not isinstance(kw.value, _a.Dict):
                continue
            keys = [k.value for k in kw.value.keys if isinstance(k, _a.Constant)]
            if "caps" not in keys:
                continue
            st = _publish_status(node)
            statuses_with_caps.append(st)
            if st is None or str(st).lower() not in UNHEALTHY:
                healthy_with_caps = True

    assert statuses_with_caps, f"{mod}: no publish carries caps at all"
    assert healthy_with_caps, (
        f"{mod}: caps appear ONLY on publish(status={statuses_with_caps}) — an "
        "unhealthy/halted path. The cap would be visible only once the book had "
        "stopped trading, which is precisely when it no longer matters.")


# --------------------------------------------------------------------------
# [2026-07-30 (gu)] THE FLEET'S FIRST EXIT LEVER.
#
# All nine pre-existing lighter-books levers were ENTRY or CAPACITY: the growth
# rail could move what every book OPENS and nothing about what it CLOSES, on a
# fleet whose exits (gq) showed decide the result. `disloc.exit_bps` is the
# first, and it was chosen for a measured reason rather than convenience — it
# throttles its own book's ENTRY.
# --------------------------------------------------------------------------

def test_the_books_lane_now_has_at_least_one_exit_lever():
    """The asymmetry this closes: 0 of 9 governed an exit. If a refactor drops
    it the lane silently returns to entry-only and nobody notices, because every
    other test would still pass."""
    exitish = [k for k, v in fleet_tuning.LEVERS.items()
               if v.get("lane") == "lighter-books"
               and any(t in k.split(".")[-1] for t in
                       ("exit", "tp", "sl", "hold", "trail", "stop"))]
    assert exitish, (
        "the lighter-books lane governs no exit at all — the growth rail can "
        "move what these books OPEN and nothing about what they CLOSE")
    assert "disloc.exit_bps" in exitish, exitish


def test_the_exit_cage_reaches_INSIDE_the_observed_residual_distribution():
    """The whole point of the lever. Snap Back's convergence target is 40bps
    while the live residual distribution measured median 7.9 / p90 21.8 / max
    50.1 bps across 90 liquid books. A cage that cannot descend below the p90
    would leave the target permanently outside what the tape delivers — so the
    floor must reach the median region, and the ceiling must not exceed today's
    operator default (this lever may LOOSEN the exit toward the measurement,
    never tighten it past where the operator already has it)."""
    spec = fleet_tuning.LEVERS["disloc.exit_bps"]
    assert spec["lo"] <= 10.0, (
        f"lo={spec['lo']} cannot reach the observed median (~8bps) — the target "
        "would stay outside the distribution the book trades")
    assert spec["hi"] == spec["env_default"] == 40.0, (
        "the ceiling must be the operator's current default, so the rail can "
        "only loosen toward the measurement")
    assert spec["step"] < 0, "the useful direction is DOWN, toward the tape"


def test_the_exit_lever_is_consumed_and_snapshotted():
    """Registered-but-inert is this repo's signature failure, and there are TWO
    ways to hit it here. The loop must read the lever, AND `_ENV_DEFAULTS` must
    carry the attribute — `apply_tuning` does `_ENV_DEFAULTS[attr]`, and a
    missing key raises a KeyError that its own `except Exception: continue`
    swallows, leaving a lever that looks consumed and never moves."""
    import pathlib as _pl
    src = (_pl.Path(__file__).resolve().parents[2]
           / "lighter_dislocation_bot.py").read_text()
    assert '"disloc.exit_bps", "EXIT_BPS"' in src, "not read by apply_tuning"
    i = src.index("_ENV_DEFAULTS = {")
    snap = src[i:src.index("}", i)]
    assert '"EXIT_BPS"' in snap, (
        "EXIT_BPS missing from _ENV_DEFAULTS — apply_tuning would KeyError and "
        "swallow it, and an expired lever could never revert (the (fz) ratchet)")


def test_the_exit_constant_still_governs_the_entry_floor():
    """The coupling that makes this lever unusual and worth a test: EXIT_BPS
    also sets the adaptive entry gate's floor via ENTER_FLOOR_MULT. If that
    coupling is ever removed, the lever's note becomes wrong and its cage
    rationale (derived from the ENTRY side's distribution) stops applying."""
    import pathlib as _pl
    src = (_pl.Path(__file__).resolve().parents[2]
           / "lighter_dislocation_bot.py").read_text()
    assert "ENTER_FLOOR_MULT" in src
    assert "EXIT_BPS" in src
    note = fleet_tuning.LEVERS["disloc.exit_bps"]["note"]
    assert "ENTER_FLOOR_MULT" in note or "entry" in note.lower(), (
        "the note must record that this constant governs BOTH sides")


# ===========================================================================
# [2026-07-30 (hk)] TIDE RIDER: the widening, its prerequisite, and its author.
#
# The book had ZERO closes in 20 days and that was CORRECT — the 50/200 signal
# never flipped. What was NOT correct: it ranked 6 of 220 markets while (fz),
# CLAUDE.md and fleet_bus' own docstring all claimed it had been widened off
# the scout. Only two of the five named consumers ever shipped.
# ===========================================================================
class TestTideRiderUniverse:
    CORE = ["BTC", "ETH", "SOL", "BNB", "XRP", "TRX"]

    def _bus(self, out):
        class _B:
            def scout_universe(self, min_vol_m=0.0, current_time=None):
                if isinstance(out, Exception):
                    raise out
                return list(out)
        return _B()

    def test_the_import_and_the_copy_shipped_together(self):
        """A guarded import + a missing COPY is a SILENT degrade to the
        hand-typed six — precisely how (fz) 'widened' this book and moved
        nothing. Both halves, asserted together."""
        import pathlib as _p
        assert trend.fleet_bus is not None, "fleet_bus import is dark"
        root = _p.Path(__file__).resolve().parents[2]
        df = (root / "Dockerfile.trendlighter").read_text()
        assert "fleet_bus.py" in df, "image does not carry fleet_bus.py"

    def test_widening_is_additive_and_ordered(self, monkeypatch):
        monkeypatch.setattr(trend, "fleet_bus", self._bus(["HYPE", "ZEC"]))
        got = trend.resolve_universe(self.CORE, 24, 5.0)
        assert got == self.CORE + ["HYPE", "ZEC"]

    @pytest.mark.parametrize("bus", [None, "empty", "raises"])
    def test_a_dark_organ_can_never_shrink_the_book(self, monkeypatch, bus):
        """THE CONTRACT: the widening is an enhancement, never a dependency.
        Empty must read as 'keep my configured list', never 'trade nothing'."""
        monkeypatch.setattr(trend, "fleet_bus",
                            None if bus is None else
                            self._bus([] if bus == "empty"
                                      else RuntimeError("down")))
        assert trend.resolve_universe(self.CORE, 24, 5.0) == self.CORE

    def test_a_held_coin_is_always_scanned(self, monkeypatch):
        """THE PREREQUISITE. Exits are evaluated only for scanned coins, and
        this book's only sweeper (_flatten_all) is `not dry_run`-gated, so the
        SHADOW arm has none. Before this, a coin leaving the universe kept its
        position with no exit, no stop and no seatbelt, permanently — and
        making the universe DYNAMIC is what turns that latent trap into a live
        one. The two must ship together."""
        monkeypatch.setattr(trend, "fleet_bus", self._bus([]))
        assert trend.scan_universe(["BTC"], ["DOGE"], 24, 5.0) == ["BTC", "DOGE"]
        # and under every degraded bus, because that is when it matters most
        monkeypatch.setattr(trend, "fleet_bus", self._bus(RuntimeError("x")))
        assert "DOGE" in trend.scan_universe(self.CORE, ["DOGE"], 24, 5.0)

    def test_held_coins_append_so_admission_order_is_unchanged(self, monkeypatch):
        monkeypatch.setattr(trend, "fleet_bus", self._bus([]))
        assert trend.scan_universe(self.CORE, ["DOGE"], 24, 5.0)[:6] == self.CORE

    def test_supports_never_skips_a_held_position(self):
        """`supports()` answers an ENTRY question. Skipping a held coin on a
        delist removed its exit, its stop and its seatbelt in one line."""
        assert trend.skip_coin(False, 0.0) is True     # flat + unsupported
        assert trend.skip_coin(False, 1.0) is False    # HELD: never skipped

    def test_exit_predicates_are_the_production_ones(self):
        """Bound to the module's functions, not re-implemented here — a local
        copy is what let a DISABLED death cross pass this suite (measured)."""
        assert trend.exit_reason(False, 0.10) == "death_cross"
        assert trend.exit_reason(False, -0.99) == "death_cross"   # checked first
        assert trend.exit_reason(True, -trend.CATASTROPHIC_STOP) == "catastrophic_stop"
        assert trend.exit_reason(True, 0.0) is None

    def test_levers_reach_the_consumer_and_revert_on_expiry(self, monkeypatch):
        """Registered-but-inert is the failure this tier exists to prevent."""
        was = (trend.UNIVERSE_N, trend.MIN_VOL_M, trend.MAX_OPEN_POSITIONS)
        vals = {"trend.universe_n": 40, "trend.min_vol_m": 2.0,
                "trend.max_open": 9}

        class _T:
            LEVERS = fleet_tuning.LEVERS
            @staticmethod
            def get_lever(name, default, **kw):
                return vals.get(name, default)
        try:
            monkeypatch.setattr(trend, "tuning", _T)
            moved = trend.apply_tuning()
            assert trend.UNIVERSE_N == 40 and trend.MIN_VOL_M == 2.0
            assert trend.MAX_OPEN_POSITIONS == 9
            assert set(vals) <= set(moved), moved
            # EXPIRY: get_lever falls back to its `default`, and apply_tuning
            # must hand it the ENV snapshot — passing the moved value is the
            # one-way ratchet (gc) had to fix on all six books.
            vals.clear()
            trend.apply_tuning()
            assert trend.UNIVERSE_N == trend._ENV_DEFAULTS["UNIVERSE_N"]
            assert trend.MIN_VOL_M == trend._ENV_DEFAULTS["MIN_VOL_M"]
            assert trend.MAX_OPEN_POSITIONS == trend._ENV_DEFAULTS["MAX_OPEN_POSITIONS"]
        finally:
            (trend.UNIVERSE_N, trend.MIN_VOL_M,
             trend.MAX_OPEN_POSITIONS) = was

    def test_the_board_can_actually_author_this_book(self):
        """(gb) again, one level subtler: Tide Rider was ABSENT from
        BOOK_AUTHOR, so even a perfectly registered+consumed lever could never
        be moved by anything."""
        import evidence_board
        assert "crypto-trend-daily-lshadow" in evidence_board.BOOK_AUTHOR
        cap, gate = evidence_board.BOOK_AUTHOR["crypto-trend-daily-lshadow"]
        assert gate == "trend.universe_n", "the universe IS this book's gate"
        for lv in (cap, gate):
            assert lv in fleet_tuning.LEVERS, lv
            assert fleet_tuning.LEVERS[lv].get("step"), f"{lv} step cannot act"

    def test_tradfi_switch_filters_scout_adds_only(self, monkeypatch):
        """The scout ranks by turnover, so 9 of the 10 books it adds here are
        tokenised equities/commodities. Keeping that is a DECISION (item 18
        wants non-BTC regimes, and the signal is per-asset by construction) —
        so it gets an explicit, reversible switch, not a silent default."""
        monkeypatch.setattr(trend, "fleet_bus",
                            self._bus(["HYPE", "XAU", "SOXL", "ZEC"]))
        monkeypatch.setattr(trend, "ALLOW_TRADFI", False)
        assert trend.resolve_universe(self.CORE, 24, 5.0) == self.CORE + ["HYPE", "ZEC"]
        # a CONFIGURED tradfi coin is the operator's choice and is never
        # dropped — the filter applies to SCOUT-ADDED books only.
        assert trend.resolve_universe(["XAU"], 24, 5.0)[0] == "XAU"
        monkeypatch.setattr(trend, "ALLOW_TRADFI", True)
        assert "XAU" in trend.resolve_universe(self.CORE, 24, 5.0)
