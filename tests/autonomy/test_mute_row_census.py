"""[2026-08-27 (vm)] THE ROWS THAT PUBLISHED NOTHING, AND A BOOK WHOSE EXITS
ARE DEAD — the census wiring for ⚖️ Counterweight, the 🏛️ PM books, and 🧮 the
Professor's exit-reachability report.

WHY THIS FILE EXISTS, measured 27-Aug on the live payload:

  * `perps-funding-spread-lshadow` (⚖️ Counterweight) published `caps`, a
    `held` map and `ff_overlap` — what it HOLDS — and NOTHING about what its
    rank turned away, while sitting on the decision docket at ~2,500 days to
    the 30-close bar. The two candidate explanations demand OPPOSITE actions:
    a rebalance being SKIPPED for want of rankable coins (supply — fixable) vs
    a rebalance that runs and re-selects the SAME 2K legs (no churn, therefore
    no closes — not fixable by more coins). Nothing in the row could tell them
    apart.
  * `pm-albanese-lshadow` / `pm-turnbull-lshadow` published `last_skip`: ONE
    string, the LAST refusal of the LAST symbol of the cycle. Four different
    diagnoses (no signal / confirm leg / ML gate / every slot full) collapsed
    into one, and the one that won was whichever symbol happened to be last.
  * `book-hull-lshadow` read `{held: 10, eligible: 1}` — supply-limited,
    plainly — and it is not. Its `EXIT_APR` (3.5%) sits BELOW the venue's
    crypto resting funding pin (10.512%) and TEN of its eleven in-band coins
    sit exactly ON that pin, so `decay_paid` and `liability_flip` are dead by
    construction and `max_hold` (504h) is the only exit that can fire.
    `{eligible: 1}` is byte-identical between "quiet" and "structurally
    impossible" — I1/I18 at book scale.

WHAT IS PINNED HERE, and the shape of it: the censuses are PUBLISHER-BUILT —
every payload in this file comes out of the bots' own gate functions
(`rank_scores`/`rank_targets`, `PMBot._candidates`/`_try_enter`,
`hull.exits_reachable`), never a dict written to look like one. The
reachability report is cross-checked against `carry_exit` ITSELF over a swept
rate grid, so a future edit to the exit bars reddens this file instead of
quietly leaving a stale second copy of the rule behind ((hj)).

THE ONE STRUCTURAL REFUSAL. `test_exit_apr_never_reaches_into_the_entry_band`
forbids the "obvious fix" for 🧮 Hull that reached us and is WRONG twice over:
raising `HULL_EXIT_APR` to 0.036 does nothing (this book is crypto-only and the
CRYPTO pin is 0.10512, not the non-crypto 0.03504), and raising it ABOVE the
pin would put the exit INSIDE the entry band `[7.82%, 20%)` — closing coins on
the loop after they open. Both constants are IMPORTED, never retyped.

THE SEAM is the same one `test_census_accumulation.py` uses: `save_history` /
`fetch_state_history`, the two module globals `snapshot_census` and
`census_window` call by name. There is no DATABASE_URL under pytest.
"""
import ast
import datetime as _dt
import inspect
import time

import pytest

import bot_pnl_store as store
import lighter_book_hull_bot as hull
import lighter_funding_spread_bot as cw
from parliament import strategies as pm


# --------------------------------------------------------------- the seam ----
class FakeHistory:
    """bot_state_history at the save/fetch seam, replaying
    `fetch_state_history`'s own documented contract: NEWEST FIRST,
    [{"ts": iso, "payload": dict}]."""

    def __init__(self):
        self.rows = []

    def save(self, key, payload):
        self.rows.append((key, time.time(), payload))
        return True

    def fetch(self, key, limit=800):
        got = sorted([r for r in self.rows if r[0] == key],
                     key=lambda r: r[1], reverse=True)
        return [{"ts": _dt.datetime.fromtimestamp(
                    ts, _dt.timezone.utc).isoformat(), "payload": p}
                for _k, ts, p in got[:int(limit)]]


@pytest.fixture
def hist(monkeypatch):
    fh = FakeHistory()
    monkeypatch.setattr(store, "save_history",
                        lambda key, payload: fh.save(key, payload))
    monkeypatch.setattr(store, "fetch_state_history",
                        lambda key, limit=800: fh.fetch(key, limit))
    return fh


# ======================================================= ⚖️ Counterweight ====
def _cw_hist(coins, now, n=None):
    """A rolling funding window the book's own `rank_scores` will accept:
    `n` samples inside the lookback, one distinct mean per coin."""
    n = cw.MIN_COVERAGE if n is None else n
    floor = now - cw.LOOKBACK_H * 3600
    return {c: [[int(floor + 60 * j), (i - len(coins) / 2.0) * 1e-5]
                for j in range(n)]
            for i, c in enumerate(coins)}


def _cw_rank(coins, now, supports=None, hist_over=None):
    """Run the book's REAL ranking path and return (funnel, scores, want)."""
    funnel = {}
    floor = now - cw.LOOKBACK_H * 3600
    fh = _cw_hist(coins, now) if hist_over is None else hist_over
    scores = cw.rank_scores(coins, supports or (lambda c: True), fh, floor,
                            census=funnel)
    want = cw.rank_targets(scores, census=funnel)
    return funnel, scores, want


def test_the_rank_census_partitions_the_universe_it_scanned():
    """Buckets are mutually exclusive and sum to `scanned` — the property that
    makes "the first non-zero refusal named the gate" mean anything."""
    now = 1_000_000.0
    coins = [f"C{i}" for i in range(3 * cw.K)] + ["GONE", "THIN"]
    fh = _cw_hist(coins, now)
    fh["THIN"] = [[int(now), 1e-5]]                  # under MIN_COVERAGE
    funnel, scores, want = _cw_rank(coins, now, supports=lambda c: c != "GONE",
                                    hist_over=fh)
    assert funnel["scanned"] == len(coins)
    assert funnel["unsupported"] == 1
    assert funnel["short_history"] == 1
    assert funnel["eligible"] == 2 * cw.K == len(want)
    assert (funnel["unsupported"] + funnel["short_history"]
            + funnel["waiting"] + funnel["cold"] + funnel["eligible"]
            == funnel["scanned"])


def test_a_skipped_rebalance_reads_as_waiting_not_as_mid_pack():
    """The two zero-turnover explanations must not share a bucket. Below the
    2K quorum the book skips the WHOLE rebalance, so its rankable coins are
    waiting for a quorum — calling them `cold` (mid-pack) would name a gate
    that did not fire and send a session to widen the wrong thing."""
    now = 1_000_000.0
    coins = [f"C{i}" for i in range(2 * cw.K - 1)]
    funnel, scores, want = _cw_rank(coins, now)
    assert want == {}, "fewer than 2K rankable must select NOTHING"
    assert funnel["waiting"] == len(scores) == len(coins)
    assert funnel["cold"] == 0
    assert funnel["eligible"] == 0


def test_the_census_reports_the_selection_the_book_actually_acts_on():
    """`rank_targets` IS the rebalance's selection — LONG the K most-negative,
    SHORT the K most-positive — so `eligible` cannot drift from what opens."""
    now = 1_000_000.0
    coins = [f"C{i}" for i in range(3 * cw.K)]
    _funnel, scores, want = _cw_rank(coins, now)
    ranked = sorted(scores, key=scores.get)
    assert set(c for c, is_s in want.items() if not is_s) == set(ranked[:cw.K])
    assert set(c for c, is_s in want.items() if is_s) == set(ranked[-cw.K:])


def test_an_always_in_book_that_retains_every_leg_reports_zero_churn():
    """THE DIAGNOSIS THE ROW COULD NOT MAKE: same 2K legs re-selected =>
    `rotating: 0` => nothing closes => ~2,500 days to a 30-close bar, with
    every gate working exactly as designed."""
    now = 1_000_000.0
    coins = [f"C{i}" for i in range(3 * cw.K)]
    funnel, _scores, want = _cw_rank(coins, now)
    same = cw.rank_census(funnel, "fresh", want, set(want))
    assert same["retained"] == 2 * cw.K
    assert same["rotating"] == 0 and same["entering"] == 0
    churned = cw.rank_census(funnel, "fresh", want, {"OTHER"})
    assert churned["retained"] == 0, "retained is the OVERLAP, not a union"
    assert churned["rotating"] == 1 and churned["entering"] == 2 * cw.K


def test_the_liveness_verdict_comes_first_and_is_never_summed(hist):
    """I1: the verdict leads the census, and it is a STRING so the accumulator
    cannot turn it into a fake measurement — it lands in `_dropped` instead."""
    now = 1_000_000.0
    funnel, _s, want = _cw_rank([f"C{i}" for i in range(3 * cw.K)], now)
    cen = cw.rank_census(funnel, "fresh", want, set())
    assert list(cen)[0] == "scan" and cen["scan"] == "fresh"
    store.snapshot_census("counterweight", cen)
    w = store.census_window("counterweight", hours=24)
    assert "scan" not in w, "a verdict must never be summed"
    assert w["dropped"] >= 1


def test_the_counterweight_census_accumulates_and_names_its_binding_gate(hist):
    """Publisher-built, end to end: the book's own funnel through the real
    accumulator, three loops, and the largest DECLARED refusal wins."""
    now = 1_000_000.0
    coins = [f"C{i}" for i in range(3 * cw.K)]
    funnel, _s, want = _cw_rank(coins, now)
    cen = cw.rank_census(funnel, "fresh", want, set(want))
    for _ in range(3):
        assert store.snapshot_census("counterweight", cen) is True
    w = store.census_window("counterweight", hours=24)
    assert w["loops"] == 3
    assert w["scanned"] == 3 * len(coins)
    assert w["cold"] == 3 * funnel["cold"] > 0
    assert w["binding_gate"] == "cold", w
    # the churn counts are NOT refusals and must never win the gate
    assert set(w["unclassified"]) == {"retained", "rotating", "entering"}, w


# ============================================================== 🧮 Hull ======
_PIN = hull.RESTING_APRS[0]                 # 10.512% TRUE — the crypto pin


def _hull_pos(coin="P", side="short", accrued=5.0, opened=0.0):
    return {"coin": coin, "side": side, "notional": hull.CLIP_USD,
            "opened_ts": opened, "accrued": accrued,
            "fees": (hull.SLIP_COST + hull.HEDGE_COST) * hull.CLIP_USD}


def test_exit_apr_never_reaches_into_the_entry_band():
    """THE STRUCTURAL REFUSAL. A proposal to lift `HULL_EXIT_APR` over the
    resting pin so the decay exit can fire is WRONG TWICE: 0.036 changes
    nothing (this book is crypto-only and the crypto pin is 10.512%, not the
    non-crypto 3.504%), and anything above the pin lands INSIDE the entry band
    `[APR_LO_EFF, APR_HI)` — the book would close a coin on the loop after it
    opened it. Both constants imported, never retyped (I23/(hj))."""
    assert hull.EXIT_APR < hull.APR_LO_EFF, (
        f"EXIT_APR {hull.EXIT_APR} has reached into the entry band "
        f"[{hull.APR_LO_EFF}, {hull.APR_HI}) — a coin would be closed on the "
        "loop after it opens. The exits are dead because of the venue's "
        "resting PIN; raise the entry floor or accept max_hold, never this.")
    assert 0 < hull.EXIT_APR
    assert not hull.in_band(hull.EXIT_APR), \
        "the exit bar must sit OUTSIDE the band the entry gate admits"


def test_the_pins_are_derived_through_the_basis_authority_not_retyped():
    """A retyped literal is BYTE-IDENTICAL to the derived value today — the
    equality below cannot tell them apart, and a test that cannot see the
    defect it names is the vacuous kind this repo keeps paying for. So assert
    the WIRING on the module's own AST ([[a-substring-test-is-not-a-wiring-
    test]]): `RESTING_APRS` must be built by calling the basis owner over
    `RESTING_RATES`, so a venue basis change moves the pin with it instead of
    leaving 0.10512 frozen in this file the way 8x once was."""
    tree = ast.parse(inspect.getsource(hull))
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "RESTING_APRS"
                       for t in n.targets)]
    assert len(assigns) == 1, "RESTING_APRS must have exactly one owner"
    body = assigns[0].value
    calls = [n for n in ast.walk(body) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "to_apr"]
    assert calls, "RESTING_APRS must be DERIVED via funding_basis.to_apr"
    assert any(isinstance(n, ast.Name) and n.id == "RESTING_RATES"
               for n in ast.walk(body)), "derived from the venue's raw quotes"
    assert hull.RESTING_APRS == tuple(
        hull.funding_basis.to_apr(r, "lighter") for r in hull.RESTING_RATES)


def test_the_crypto_pin_sits_above_the_decay_bar():
    """The measured cause of the dead exits."""
    assert abs(_PIN - 0.10512) < 1e-9
    assert hull.EXIT_APR < _PIN, "this inequality IS the (vm) diagnosis"
    assert hull.at_resting_pin(_PIN) and hull.at_resting_pin(-_PIN)
    assert not hull.at_resting_pin(hull.APR_LO_EFF)
    assert not hull.at_resting_pin(None) and not hull.at_resting_pin("junk")


def test_a_pinned_position_can_only_ever_reach_max_hold():
    """Driven against `carry_exit` ITSELF, not against a restatement of it:
    hold the pin, walk the clock past FLIP_GRACE_H with the round trip fully
    repaid, and no exit but the clock ever returns."""
    t0 = 1_000_000.0
    for dt_h in (0.0, 1.0, hull.FLIP_GRACE_H + 1.0, hull.MAX_HOLD_H - 2.0):
        pos = _hull_pos(opened=t0)
        assert hull.carry_exit(pos, _PIN, t0 + dt_h * 3600.0) is None
    late = _hull_pos(opened=t0 - (hull.MAX_HOLD_H + 1) * 3600.0)
    assert hull.carry_exit(late, _PIN, t0) == "max_hold"


def test_exits_reachable_agrees_with_carry_exit_over_a_swept_rate():
    """The report is a claim ABOUT `carry_exit`, so sweep the rule and check
    the claim. Off the pin the decay exit becomes reachable exactly where
    `carry_exit` starts returning `decay_paid`."""
    t0 = 1_000_000.0
    for apr in (_PIN, hull.APR_LO_EFF, hull.EXIT_APR / 2.0, 0.0):
        fund = {"P": {"rate": apr / hull.H, "vol": 5e6}}
        rx = hull.exits_reachable({"P": _hull_pos(opened=t0)}, fund)
        fires = hull.carry_exit(_hull_pos(opened=t0), apr, t0) == "decay_paid"
        if fires:
            assert rx["decay_paid"] == 1, (apr, rx)
        assert rx["max_hold"] == 1 and rx["held"] == 1
    # and the sign-flip leg: a pinned rate is a constant, so it cannot flip
    pinned = hull.exits_reachable(
        {"P": _hull_pos(opened=t0)},
        {"P": {"rate": _PIN / hull.H, "vol": 5e6}})
    assert pinned["liability_flip"] == 0 and pinned["decay_paid"] == 0
    free = hull.exits_reachable(
        {"P": _hull_pos(opened=t0)},
        {"P": {"rate": hull.APR_LO_EFF / hull.H, "vol": 5e6}})
    assert free["liability_flip"] == 1 and free["decay_paid"] == 1


def test_a_position_with_no_readable_rate_is_unpriceable_never_a_zero():
    """I1/rule 5: unknown gets its own bucket. Folding it into the reachable
    counts would make a dark funding fetch look like a structural freeze."""
    rx = hull.exits_reachable({"Z": _hull_pos(coin="Z")}, {"OTHER": {}})
    assert rx == {"held": 1, "decay_paid": 0, "liability_flip": 0,
                  "max_hold": 0, "unpriceable": 1}
    assert hull.exits_reachable({}, None) == {
        "held": 0, "decay_paid": 0, "liability_flip": 0, "max_hold": 0,
        "unpriceable": 0}


def test_the_pin_count_is_the_supply_side_denominator():
    """10 of 11 pinned is structural; 10 of 200 is noise. Junk rows are
    skipped, never counted as un-pinned."""
    fund = {"A": {"rate": hull.RESTING_RATES[0], "vol": 5e6},
            "B": {"rate": -hull.RESTING_RATES[0], "vol": 5e6},
            "C": {"rate": hull.RESTING_RATES[1], "vol": 5e6},
            "D": {"rate": hull.APR_LO_EFF / hull.H, "vol": 5e6},
            "E": {"rate": "junk", "vol": 5e6}}
    assert hull.pinned_count(fund) == 3
    assert hull.pinned_count({}) == 0 and hull.pinned_count(None) == 0


def test_oldest_held_h_is_none_when_flat_never_zero():
    t0 = 1_000_000.0
    assert hull.oldest_held_h({}, now=t0) is None
    pos = {"A": _hull_pos(opened=t0 - 3600.0),
           "B": _hull_pos(coin="B", opened=t0 - 7200.0)}
    assert hull.oldest_held_h(pos, now=t0) == 2.0
    assert hull.oldest_held_h({"X": {"opened_ts": None}}, now=t0) is None


def test_build_extra_publishes_the_reachability_report(hist):
    """The consumer of all of the above is the row itself — asserted on the
    payload the real builder produces, JSON-safe, non-degenerate."""
    t0 = 1_000_000.0
    fund = {"P": {"rate": hull.RESTING_RATES[0], "vol": 5e6},
            "Q": {"rate": hull.APR_LO_EFF / hull.H, "vol": 5e6}}
    cen = hull.scan_census(fund, {"P"}, {}, t0)
    extra = hull.build_extra(cen, {"P": _hull_pos(opened=t0 - 3600.0)},
                             0.0, 0.0, fund=fund, now=t0)
    caps = extra["caps"]
    assert caps["exits_reachable"] == {"held": 1, "decay_paid": 0,
                                       "liability_flip": 0, "max_hold": 1,
                                       "unpriceable": 0}
    assert caps["n_at_pin"] == 1
    assert caps["oldest_held_h"] == 1.0
    assert caps["max_hold_h"] == hull.MAX_HOLD_H
    assert extra["census_24h"] is None, "a dark window is None, never {}"
    assert store.json_safe(extra)["caps"]["n_at_pin"] == 1


def test_the_hull_census_accumulates_off_its_own_gate(hist):
    """Publisher-built: hull's real `scan_census`, summed."""
    t0 = 1_000_000.0
    fund = {"T1": {"rate": hull.APR_LO_EFF / hull.H, "vol": 1e5},
            "T2": {"rate": hull.APR_LO_EFF / hull.H, "vol": 1e5},
            "E1": {"rate": hull.APR_LO_EFF / hull.H, "vol": 5e6}}
    cen = hull.scan_census(fund, set(), {"E1": 0.0}, t0,
                           class_ok=lambda c: True)
    assert cen["thin"] == 2 and cen["eligible"] == 1, cen
    for _ in range(4):
        store.snapshot_census("book-hull", cen)
    w = store.census_window("book-hull", hours=24)
    assert w["loops"] == 4 and w["thin"] == 8
    assert w["binding_gate"] == "thin", w
    assert w["unclassified"] == [], w


# ============================================================ 🏛️ the PMs =====
class _FakeData:
    """The candle/stat layer's read surface, only what the entry path calls."""

    def __init__(self, fresh=True, px=100.0, chg=0.0):
        self._fresh, self._px, self._chg = fresh, px, chg
        self.ws_books = {}

    def fresh(self):
        return self._fresh

    def stats(self, sym):
        return {"last": self._px, "mark": self._px, "chg": self._chg}


def _pm(strategy="meanrev", base="pm-turnbull", data=None):
    bot = pm.PMBot(base, strategy, data or _FakeData(), None, None, None)
    bot._restored = True
    return bot


def _sig(strength=1.0, direction=1):
    return {"strength": strength, "direction": direction, "ts": time.time(),
            "meta": {}}


def test_every_entry_blocked_reason_has_its_own_census_stage():
    """THE DRIFT GUARD. `_entry_blocked` returns its own reason strings; the
    census maps each to a stage. A NEW reason added without a stage would
    otherwise land in `blocked_other` forever and nobody would know which gate
    it was. Read off the AST of the real function, so it cannot be satisfied
    by a comment."""
    tree = ast.parse(inspect.getsource(pm.PMBot._entry_blocked).lstrip())
    reasons = {n.value.value for n in ast.walk(tree)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
               and isinstance(n.value.value, str)}
    assert reasons, "the AST walk found no reasons — the check inspected nothing"
    missing = reasons - set(pm.CENSUS_BLOCK)
    assert not missing, f"entry gates with no census stage: {sorted(missing)}"
    assert set(pm.CENSUS_BLOCK.values()) <= set(pm.CENSUS_STAGES)


def test_the_pm_census_partitions_the_signals_it_scanned():
    """Every primary-topic signal lands in exactly one bucket, and a signal on
    ANOTHER lens's topic is not this book's scan at all."""
    bot = _pm()
    primary = bot.primary_topic
    bot.signals = {(primary, "AAA"): _sig(strength=1.0),
                   (primary, "BBB"): _sig(strength=0.0),      # under the bar
                   (primary, "CCC"): _sig(direction=0),       # no direction
                   ("signals.some_other_lens", "DDD"): _sig()}
    out = bot._candidates()
    cen = bot.census
    assert cen["scanned"] == 3, cen
    assert cen["no_signal"] == 2, cen
    assert len(out) == 1 and out[0][0] == "AAA"


def test_the_confirm_leg_gets_its_own_bucket_not_no_signal():
    """A candidate killed by the strategy's confirm leg is a DIFFERENT
    diagnosis from one that never signalled — `last_skip` could not say
    which, and it is the difference between tuning a bar and adding a feed."""
    bot = _pm(strategy="meanrev")
    bot.signals = {
        (bot.primary_topic, "AAA"): _sig(),
        (bot.confirm_topic, "AAA"): dict(_sig(), meta={"regime": "expanding"}),
    }
    assert bot._candidates() == []
    assert bot.census["confirming"] == 1 and bot.census["no_signal"] == 0


def test_a_blocked_entry_lands_in_its_own_stage(monkeypatch):
    """Publisher-built again: the REAL `_entry_blocked` decides, and the stage
    it lands in is the one its own reason maps to — never a near-miss."""
    monkeypatch.setattr(pm, "fleet_bus", None)          # the dark-organ path
    bot = _pm(data=_FakeData(fresh=False))              # -> "stale-data"
    assert bot._try_enter("AAA", 1, _sig()) is False
    assert bot.census[pm.CENSUS_BLOCK["stale-data"]] == 1
    assert sum(bot.census.values()) == 1, bot.census

    bot2 = _pm()
    bot2.last_entry["AAA"] = time.time()                # -> "cooldown"
    assert bot2._try_enter("AAA", 1, _sig()) is False
    assert bot2.census[pm.CENSUS_BLOCK["cooldown"]] == 1


def test_an_unpriceable_candidate_is_counted_at_all(monkeypatch):
    """It was the one refusal that wrote NEITHER a ledger row nor a
    `last_skip`: a candidate cleared every gate, had no price, and vanished."""
    monkeypatch.setattr(pm, "fleet_bus", None)
    monkeypatch.setattr(pm, "featurize", lambda *a, **k: {})
    bot = _pm(data=_FakeData(px=0.0))
    assert bot._try_enter("AAA", 1, _sig()) is False
    assert bot.census["unpriceable"] == 1


@pytest.mark.skipif(pm.PaperBroker is None, reason="paper_broker not importable")
def test_an_opened_entry_is_counted_and_the_partition_still_holds(monkeypatch):
    monkeypatch.setattr(pm, "fleet_bus", None)
    monkeypatch.setattr(pm, "featurize", lambda *a, **k: {})
    bot = _pm()
    bot.signals = {(bot.primary_topic, "AAA"): _sig()}
    cands = bot._candidates()
    assert len(cands) == 1
    assert bot._try_enter(*cands[0]) is True
    cen = bot.census
    assert cen["opened"] == 1
    assert cen["scanned"] == cen["no_signal"] + cen["confirming"] + cen[
        "opened"] + sum(cen[k] for k in pm.CENSUS_BLOCK.values()) \
        + cen["gated"] + cen["ml_gate"] + cen["unpriceable"] \
        + cen["blocked_other"]
    # and the SECOND attempt on the same coin is a refusal with a real name
    assert bot._try_enter("AAA", 1, _sig()) is False
    assert bot.census["held_sym"] == 1


def test_the_pm_census_accumulates_and_names_its_binding_gate(hist):
    """Publisher-built: `new_census()` + the real gates, summed. `last_skip`
    would have reported ONE of these three cycles."""
    bot = _pm(data=_FakeData(fresh=False))
    for _ in range(3):
        bot.census = pm.new_census()
        bot._try_enter("AAA", 1, _sig())
        store.snapshot_census("pm-turnbull", bot.census)
    w = store.census_window("pm-turnbull", hours=24)
    assert w["loops"] == 3
    assert w["no_bars"] == 3, w
    assert w["binding_gate"] == "no_bars", w
    assert w["hours"] >= 0.0


def test_the_dominant_quiet_cycle_refusal_can_win_the_binding_gate(hist):
    """THE PROPERTY THE STAGE NAMES EXIST FOR, and it is not free. Only a
    DECLARED refusal (`bot_pnl_store.CENSUS_REFUSALS`) may win `binding_gate`,
    so a stage with an undeclared name silently loses to a SMALLER declared
    one — the binding gate would then name the wrong fix. Measured here: 9
    stale-data refusals against 3 slot refusals must report the stale feed."""
    cen = pm.new_census()
    cen.update({"scanned": 5, pm.CENSUS_BLOCK["stale-data"]: 3,
                "slots_full": 1, "opened": 1})
    for _ in range(3):
        store.snapshot_census("pm-binding", cen)
    w = store.census_window("pm-binding", hours=24)
    assert w[pm.CENSUS_BLOCK["stale-data"]] == 9 and w["slots_full"] == 3
    assert w["binding_gate"] == pm.CENSUS_BLOCK["stale-data"], w


def test_every_pm_stage_is_declared_so_none_abstains_from_the_binding_gate(
        hist):
    """[(vm)] THE LIMITATION IS GONE, and this test is how we found out.

    It previously pinned the COST: four PM stages — `venue_stress`,
    `daily_halt`, `ml_gate`, `blocked_other` — had no word in the fleet's
    declared refusal vocabulary, so they published their counts and ABSTAINED
    from `binding_gate`, and it failed by design the day someone declared
    them. That happened in the same wave: they are in
    `bot_pnl_store.CENSUS_REFUSALS` now.

    Why it matters rather than being bookkeeping: only a DECLARED refusal may
    win `binding_gate`, so an undeclared stage silently loses to a SMALLER
    declared one and the gate names the WRONG fix. A 🏛️ book stopped by venue
    stress would have reported `slots_full`, sending the operator at capacity
    when the answer was the venue. So the property is now the strong one —
    EVERY stage is classified and nothing abstains."""
    cen = pm.new_census()
    cen.update({k: 1 for k in pm.CENSUS_STAGES})
    store.snapshot_census("pm-undeclared", cen)
    w = store.census_window("pm-undeclared", hours=24)
    assert set(w["unclassified"]) == set(), (
        "a PM stage abstains from binding_gate again — declare it in "
        "bot_pnl_store.CENSUS_REFUSALS or it will lose to a smaller refusal")
    assert set(pm.CENSUS_STAGES) <= (
        store.CENSUS_REFUSALS | store.CENSUS_DENOMINATORS)
    # and the four now genuinely COMPETE: a dominant venue-stress refusal must
    # be able to win outright, which is the whole point of declaring them.
    cen2 = pm.new_census()
    cen2.update({"scanned": 12, "venue_stress": 9, "slots_full": 3})
    store.snapshot_census("pm-stress", cen2)
    w2 = store.census_window("pm-stress", hours=24)
    assert w2["binding_gate"] == "venue_stress", w2


def test_the_census_is_reset_every_cycle_never_accumulated_in_memory(
        hist, monkeypatch):
    """THE ROLLUP'S OWN PRECONDITION. `snapshot_census` appends ONE loop's
    refusals and `census_window` sums them, so a per-cycle dict that is never
    zeroed would publish a LIFETIME total and the trailing-day number would be
    a triangular sum of itself — a counter that reads bigger the longer the
    book runs, which is exactly the fake measurement this wave exists to
    remove. Driven through the REAL `cycle()`, twice."""
    import asyncio

    monkeypatch.setattr(pm, "fleet_bus", None)
    bot = _pm(data=_FakeData(fresh=False))
    bot.signals = {(bot.primary_topic, "AAA"): _sig(),
                   (bot.primary_topic, "BBB"): _sig()}
    asyncio.run(bot.cycle())
    first = dict(bot.census)
    assert first["scanned"] == 2, first
    asyncio.run(bot.cycle())
    assert bot.census == first, "the census must describe ONE cycle"

    w = store.census_window(bot.bot_id, hours=24)
    assert w["loops"] == 2 and w["scanned"] == 4, w


def test_a_pm_book_that_never_reaches_its_entry_phase_still_has_a_census():
    """Bound at construction, so `publish()` can never KeyError on a book that
    returned early — the fail-safe half of a telemetry addition."""
    bot = _pm()
    assert bot.census == {k: 0 for k in pm.CENSUS_STAGES}


# ============================================================ publish-only ====
def test_each_row_asks_for_a_window_it_can_actually_fill():
    """`census_window`'s default row limit assumes a 30s loop. These books run
    at 300s (⚖️/🧮) and 60s (🏛️), so the default over-fetches by up to 10x on
    every loop forever — and a limit set too LOW is worse than that: the window
    silently becomes a SAMPLE. Each caller passes a limit derived from its own
    cadence, and it must cover a full day at that cadence with headroom."""
    for mod in (hull, cw):
        assert mod.CENSUS_LIMIT * mod.LOOP_SECONDS >= 24 * 3600, mod.__name__
        assert mod.CENSUS_LIMIT < 2880, \
            f"{mod.__name__} gains nothing over census_window's own default"
    assert pm.CENSUS_LIMIT * 60.0 >= 24 * 3600      # run_forever's 60s default
    # ...and the call sites actually pass it (a constant nothing reads is the
    # registered-but-inert failure wearing a telemetry hat).
    for src in (inspect.getsource(hull.main), inspect.getsource(cw.main),
                inspect.getsource(pm.PMBot.publish)):
        assert "census_window(" in src and "limit=CENSUS_LIMIT" in src


def test_none_of_the_new_surfaces_can_move_a_lever_or_an_order():
    """Rule 6, asserted of the diff rather than believed: the census surfaces
    added by (vm) contain no lever write, no order path and no gate read."""
    banned = ("write_levers", "get_lever", "market_open", "broker.open",
              "close_position", "publish_paper_trade")
    for fn in (cw.rank_scores, cw.rank_targets, cw.rank_census,
               hull.exits_reachable, hull.pinned_count, hull.oldest_held_h,
               hull.at_resting_pin, pm.new_census):
        src = inspect.getsource(fn)
        for b in banned:
            assert b not in src, f"{fn.__name__} touches {b}"


def test_the_census_builders_are_pure():
    """Called twice on the same inputs they return the same thing and mutate
    nothing the trading loop reads — a telemetry call in a trading loop that
    has side effects is the whole class this rule exists for."""
    t0 = 1_000_000.0
    pos = {"P": _hull_pos(opened=t0)}
    before = dict(pos["P"])
    fund = {"P": {"rate": _PIN / hull.H, "vol": 5e6}}
    assert hull.exits_reachable(pos, fund) == hull.exits_reachable(pos, fund)
    assert pos["P"] == before, "the reachability report must not touch a position"
    coins = [f"C{i}" for i in range(3 * cw.K)]
    f1, s1, w1 = _cw_rank(coins, t0)
    f2, s2, w2 = _cw_rank(coins, t0)
    assert (f1, s1, w1) == (f2, s2, w2)
