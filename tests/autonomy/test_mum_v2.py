"""[2026-08-19 (ro)] 👩 mum is ALIVE AGAIN, as v2 — and the revival must not
re-run v1's failure.

This file REPLACES tests/autonomy/test_mum_retired.py. The operator reversed
(rd)'s I17 retirement ("unretire mum and bring her back to life"), and a
reversal that simply un-hid the row would have restored the exact configuration
that produced ~2.4 closes/30d — a book that is ungradeable for a year. So what
is pinned here is not "mum trades" but the four properties that make v2 a
different animal from v1:

  1. she is NOT retired, in all three declaration sites;
  2. her clock is short — 1h bars and a bounded hold — because the CLOCK, not a
     loss, is what killed v1;
  3. her exit bracket can actually FIRE (v1's custom_exit-equivalent did not
     exist, and the loop's isinstance gate would have silently ignored one);
  4. she carries her own random-entry CONTROL ARM, so (hm)'s "grade a
     directional book against a random null, never against zero" is answered
     from her own payload rather than in a study nobody runs.

Plus the two invariants a revival can silently break: the era must move (or v1's
closes pool into v2's grade), and her four frozen v1 positions must be released
(or she holds every slot and can never enter — undecidable again, by a new
mechanism).
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam  # noqa: E402


def _mum():
    for s in fam.STRATEGIES:
        if s.bot == "freqtrade-mum":
            return s
    raise AssertionError("freqtrade-mum is not in STRATEGIES at all")


# --- 1 · she is alive, in every place a retirement touches -----------------
def test_mum_is_not_retired_anywhere():
    assert "freqtrade-mum" not in fam.RETIRED_BOOKS
    assert "freqtrade-mum" in {s.bot for s in fam.live_strategies()}


def test_the_row_is_neither_hidden_nor_pruned():
    """The mirror of (rd)'s both-halves test. NOTE the bare-name trap: the
    Kraken-era `freqtrade-mum` (no suffix) stays retired in both files, and
    only the `-lshadow` row comes back — a substring check would pass while
    the live row was still hidden."""
    import cleanup_legacy_bots
    import pnl_dashboard
    assert "freqtrade-mum-lshadow" not in pnl_dashboard.RETIRED_ROWS
    assert "freqtrade-mum-lshadow" not in set(cleanup_legacy_bots.LEGACY_BOTS)
    # ...while the retired Kraken-era bare id is untouched
    assert "freqtrade-mum" in pnl_dashboard.RETIRED_ROWS


def test_the_living_books_are_undisturbed():
    live = {s.bot for s in fam.live_strategies()}
    assert {"freqtrade-avo-maria", "freqtrade-georgia"} <= live


# --- 2 · the clock, which is the whole diagnosis ---------------------------
def test_she_is_no_longer_on_daily_bars():
    """v1's disease: 1d bars gave ~15 decision points/day across the universe
    and exits only on a monthly cross => ~2.4 closes/30d => ~12 months to the
    30-close bar. 1h multiplies the decision surface by 24."""
    assert _mum().tf == "1h"


def test_the_hold_is_bounded_in_hours_not_weeks():
    """Carry measured on the venue's own settled series: ~0.0288%/day, so a
    month-long hold starts ~0.86% behind and a 12h hold 0.014%. v1 held 25-33
    days by design; v2 may not."""
    s = _mum()
    assert s.custom_exit(None, s.MAX_HOLD_MIN + 1, 0.0) == "max_hold"
    assert s.custom_exit(None, s.MAX_HOLD_MIN - 1, 0.0) is None
    assert s.MAX_HOLD_MIN <= 24 * 60, "a v2 hold beyond a day re-introduces v1's tax"


def test_the_exit_bracket_can_actually_fire():
    """The loop gated custom_exit on `isinstance(b.s, DayTraderGated)`, so a
    time stop on any NEW carrier was dead code — the registered-but-inert
    shape (I18), and precisely how v1 held for a month. Pinned behaviourally:
    the roster's carriers that DECLARE a custom_exit must be reachable."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert 'hasattr(b.s, "custom_exit")' in src, (
        "custom_exit must be duck-typed, not isinstance-gated on one class")
    assert "isinstance(b.s, DayTraderGated):\n                        reason = b.s.custom_exit" not in src


def test_she_has_a_real_stop_and_it_is_inside_the_gate_bar():
    s = _mum()
    assert -0.15 < s.stoploss < 0, "v1's -15% stop was sized for a month, not 12h"
    assert abs(s.stoploss) < 0.15, "must sit inside the go-live 15% drawdown bar"


# --- 3 · the entry: the measured cell, and I20 disjointness ----------------
def test_the_entry_refuses_the_trend_filter_that_was_measured_destructive():
    """(qu) measured avo's `e50>e200` filter as ACTIVELY DESTRUCTIVE (adding it
    lowered the mean of every base). v2 takes the deep tail OUTSIDE an uptrend
    — which also makes her cell disjoint from avo's ON THE SAME TIMEFRAME
    (I20), so the (lv) subset-starvation trap between two books in one process
    is unreachable. NOTE the declared limit, which this test does NOT claim to
    cover: the two books read trend on different timeframes (1h vs 4h), so
    cross-timeframe co-holding of one coin remains possible and is bounded by
    fleet_risk's per-symbol cap rather than by this predicate."""
    s = _mum()
    n = 260
    # a deep-oversold tape in a DOWNtrend: long decline, so e50 < e200
    closes = [100.0 - 0.28 * i for i in range(n)]
    bars = {"c": closes, "h": [c * 1.004 for c in closes],
            "l": [c * 0.996 for c in closes], "v": [10.0] * n,
            "t": list(range(n))}
    sig = s.signals(bars, {"btc_regime_up": 0})
    assert sig is not None, "warmed-up bars must produce a verdict"
    assert sig["uptrend"] is False
    assert sig["rsi"] < s.RSI_MAX, "a monotonic decline must read deeply oversold"
    assert sig["enter"] == "oversold-rebound"

    # The SAME deeply-oversold reading INSIDE an uptrend must be REFUSED —
    # that is 🙏 avo's cell, and the disjointness is the whole I20 claim.
    # NOTE the tape is constructed so `uptrend` is TRUE and rsi is deep, and
    # both are asserted UNCONDITIONALLY: an earlier version guarded this with
    # `if usig["uptrend"]:` and a mutation setting `outside_uptrend = True`
    # SURVIVED, because a conditional assertion skips instead of failing.
    m = 420
    up = [50.0 + 0.9 * i for i in range(m)]
    up = up + [up[-1] - 0.055 * up[-1] * (j + 1) / 6 for j in range(14)]
    ubars = {"c": up, "h": [c * 1.004 for c in up], "l": [c * 0.996 for c in up],
             "v": [10.0] * len(up), "t": list(range(len(up)))}
    usig = s.signals(ubars, {"btc_regime_up": 1})
    assert usig is not None
    assert usig["uptrend"] is True, "fixture must actually BE an uptrend"
    assert usig["rsi"] < s.RSI_MAX, "fixture must actually be deeply oversold"
    assert usig["enter"] is None, "an uptrend dip belongs to avo, not mum"


def test_the_oversold_threshold_is_genuinely_DEEP():
    """Pins the DEPTH, not just the direction: a mild pullback outside an
    uptrend must still be refused. Without this, widening RSI_MAX to 95 — i.e.
    'buy almost anything falling' — passes every other test in this file, and
    that mutation did in fact survive the first round."""
    s = _mum()
    n = 300
    mild = [100.0 - 0.02 * i + (1.6 if i % 2 else -1.6) for i in range(n)]
    bars = {"c": mild, "h": [c * 1.004 for c in mild],
            "l": [c * 0.996 for c in mild], "v": [10.0] * n,
            "t": list(range(n))}
    sig = s.signals(bars, {})
    assert sig is not None
    assert sig["uptrend"] is False, "fixture must be outside an uptrend"
    assert 40 < sig["rsi"] < 65, "fixture must be a MILD reading, not a deep one"
    assert sig["enter"] is None, "a mild dip is not this book's cell"
    assert s.RSI_MAX <= 30, "an entry bar above 30 is no longer 'deep oversold'"


def test_no_exit_signal_the_bracket_is_the_rule():
    """Douglas's discipline: predefined at entry, never widened. v1's only exit
    was a signal, which is why it never came."""
    s = _mum()
    n = 260
    closes = [100.0 - 0.28 * i for i in range(n)]
    bars = {"c": closes, "h": [c * 1.004 for c in closes],
            "l": [c * 0.996 for c in closes], "v": [10.0] * n,
            "t": list(range(n))}
    assert s.signals(bars, {})["exit"] is False


def test_the_clip_is_structurally_constant():
    """No streak, outcome or equity input reaches sizing — the 🧘 Douglas pin."""
    s = _mum()
    assert s.stake_mult("oversold-rebound", None) == 1.0
    import inspect
    assert list(inspect.signature(s.stake_mult).parameters) == ["tag", "bars"]


# --- 4 · the control arm ---------------------------------------------------
def test_she_declares_a_control_arm_and_publishes_it_even_at_zero():
    """(hm) requires a directional book to be graded against a random-entry
    null. An omitted key at n=0 is byte-identical between 'no closes yet' and
    'the arm is not running' ((lv)), so the block must ALWAYS be present."""
    s = _mum()
    assert getattr(s, "control_arm", False) is True

    class _B:
        pass
    b = _B()
    b.s = s
    b.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
    out = fam._control_extra(b)
    assert "control" in out
    assert out["control"]["n"] == 0
    assert out["control"]["mean_pct"] is None and out["control"]["edge_pct"] is None

    b.ctrl = {"n": 2, "sum": 0.04, "null_sum": 0.01, "null_n": 2}
    out = fam._control_extra(b)["control"]
    assert out["mean_pct"] == pytest.approx(2.0)
    assert out["null_pct"] == pytest.approx(0.5)
    assert out["edge_pct"] == pytest.approx(1.5), "edge is mean MINUS the null"


def test_other_family_books_do_not_grow_a_control_block():
    """Blast-radius discipline: only a carrier that DECLARES the arm gets it."""
    class _B:
        pass
    for s in fam.STRATEGIES:
        if s.bot == "freqtrade-mum":
            continue
        b = _B()
        b.s = s
        b.ctrl = {"n": 1, "sum": 0.0, "null_sum": 0.0, "null_n": 1}
        assert fam._control_extra(b) == {}


def test_the_census_can_name_the_binding_constraint():
    """I18/(lv): `opened: 0` must never be byte-identical between a quiet
    market and a structurally impossible one. v1 was invisible for five weeks."""
    class _B:
        pass
    b = _B()
    b.s = _mum()
    b.scan = {"scanned": 15, "no_signal": 15, "opened": 0}
    b.last_rsi = {}
    out = fam._census_extra(b)
    assert out["scan"]["scanned"] == 15 and out["scan"]["opened"] == 0


def test_the_gauge_says_how_far_the_market_is_from_the_bar():
    """(rq): the census says WHY nothing opened; the gauge says HOW FAR AWAY
    the market is from opening something. `no_signal: 23` is byte-identical
    between "quiet today" and "this threshold will never fire" — and v1 died
    of the second while every reading on her row looked like the first."""
    class _B:
        pass
    b = _B()
    b.s = _mum()
    b.scan = {"scanned": 4, "no_signal": 4, "opened": 0}
    #                bar-4  bar+2  bar+13  bar+27   (bar is RSI_MAX = 25)
    b.last_rsi = {"A": 21.0, "B": 27.0, "C": 38.0, "D": 52.0}
    scan = fam._census_extra(b)["scan"]
    assert scan["rsi_bar"] == b.s.RSI_MAX
    assert scan["rsi_min"] == 21.0, "the closest coin to the bar"
    assert scan["rsi_read"] == 4
    # within 8 points of the bar: 21.0 and 27.0 qualify, 38.0 and 52.0 do not.
    # This is the leading indicator — visible hours before an entry, where the
    # entry itself is only visible days after.
    assert scan["near_bar"] == 2


def test_the_gauge_is_absent_rather_than_zero_when_nothing_was_read():
    """A fabricated `rsi_min: 0.0` on a dark scan would read as "a coin is AT
    the bar" — the loudest possible reading, from no data at all. Absence is
    the honest degrade (I8: unknown never degrades to a guess)."""
    class _B:
        pass
    b = _B()
    b.s = _mum()
    b.scan = {"scanned": 0, "opened": 0}
    b.last_rsi = {}
    scan = fam._census_extra(b)["scan"]
    for k in ("rsi_min", "rsi_med", "near_bar", "rsi_read"):
        assert k not in scan, f"{k} was invented from an empty reading set"


def test_the_gauge_has_a_feeder_and_a_source():
    """A gauge nothing writes to is the registered-but-inert shape (I18) — it
    would publish nothing forever and read as "no readings", i.e. exactly the
    silence it exists to break. Two halves, both required: the carrier must
    EMIT an rsi on every evaluated bar, and the loop must CAPTURE it."""
    s = _mum()
    n = 300                                     # a mild tape that never enters
    mild = [100.0 - 0.02 * i + (1.6 if i % 2 else -1.6) for i in range(n)]
    bars = {"c": mild, "h": [c * 1.004 for c in mild],
            "l": [c * 0.996 for c in mild], "v": [10.0] * n,
            "t": list(range(n))}
    sig = s.signals(bars, {})
    assert sig["enter"] is None, "fixture must be the NO-ENTRY case"
    assert sig is not None and isinstance(sig.get("rsi"), (int, float)), (
        "signals() must report its rsi even when it does NOT enter — the "
        "no-entry case is the only one the gauge exists to measure")
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert "b.last_rsi[coin] = float(sig[\"rsi\"])" in src, (
        "the scan loop must feed b.last_rsi, or the gauge is inert")


def test_other_family_books_do_not_grow_a_gauge():
    """Same blast-radius rule as the control arm: a book that declares no
    census keeps its payload shape exactly as it was."""
    class _B:
        pass
    for s in fam.STRATEGIES:
        if getattr(s, "census", False):
            continue
        b = _B()
        b.s = s
        b.scan = {"scanned": 9}
        b.last_rsi = {"A": 10.0}
        assert fam._census_extra(b) == {}


# --- 5 · the two things a revival silently breaks --------------------------
def test_the_era_moved_or_v1s_closes_pool_into_v2s_grade():
    """Her three v1 closes were opened 2026-07-12 under a rule v2 does not
    contain. Both tables must move together — the gate's sample may never be
    wider than the brain's."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import bot_learn
    import golive_readiness as gl
    gate_iso = gl.POLICY_ERA["freqtrade-mum"][0]
    brain_iso = bot_learn.ERA_START["freqtrade-mum"]
    # DERIVED, never a date literal: audit_era_date_literals fails a test that
    # hardcodes a date the era tables own, so that one legitimate table move
    # cannot redden a test which is not about the date.
    v1_open_day = "2026-07-12"          # her v1 trades' open date, not an era
    assert gate_iso > v1_open_day and brain_iso > v1_open_day, \
        "an era at or before v1's opens would pool v1's closes into v2's grade"
    assert gate_iso[:10] == brain_iso[:10], "the two tables must move together"
    # and the gate may never scope WIDER than the brain
    assert gate_iso >= brain_iso


def test_the_frozen_v1_positions_are_released():
    """The subtle trap: mum's four v1 positions (opened 2026-07-12) would hold
    every one of her four slots forever, so v2 could never open a trade — she
    would be undecidable again by a NEW mechanism. They flatten once, tagged,
    and they opened before the era boundary so they cannot pollute v2's grade."""
    s = _mum()
    fb = getattr(s, "FLATTEN_BEFORE_TS", 0.0)
    assert fb > 0, "no flatten boundary declared"
    import datetime as dt
    v1_open = dt.datetime(2026, 7, 12, 21, 41, 49, tzinfo=dt.timezone.utc).timestamp()
    assert v1_open < fb, "v1's positions must fall before the boundary"
    assert dt.datetime.now(dt.timezone.utc).timestamp() + 60 > fb, \
        "the boundary must be in the past, or v2's OWN entries get flattened"
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert 'reason = "v1_legacy"' in src
    assert 'FLATTEN_BEFORE_TS' in src


def test_the_control_arm_ACCUMULATES_when_a_trade_actually_closes():
    """Drives the real `Book.record_close`, not just the publisher.

    The first mutation round disabled the accumulator inside `record_close`
    and SURVIVED, because every control-arm test until now hand-fed `b.ctrl`
    and only exercised `_control_extra`. That is the (qy) lesson exactly:
    asserting on the reporting half cannot see a broken recording half. Here
    the placebo is settled through the real code path — a +2% real trade
    against a placebo coin that moved +0.5% must leave edge = +1.5pp.
    """
    class _Stub:
        pass
    b = _Stub()
    b.s = _mum()
    b.bot_id = "freqtrade-mum-lshadow"
    b.meta = {"BTC": {"accrued": 0.0, "opened_ts": 1.0, "tag": "oversold-rebound",
                      "entry": 100.0, "null_pair": "ETH", "null_entry": 200.0}}
    b.last_mark = {"ETH": 201.0}          # the placebo moved +0.5%
    b.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
    b.fund_realized = 0.0
    b.n_closed = b.n_wins = 0
    b.closed = []
    b.cooldown = {}

    fam.Book.record_close(b, "BTC", 102.0, 1.0, "roi", notional=50.0)

    assert b.ctrl["n"] == 1, "the real trade must be recorded"
    assert b.ctrl["null_n"] == 1, "the placebo must settle on the same close"
    assert b.ctrl["sum"] == pytest.approx(0.02), "1.0/50 = +2%"
    assert b.ctrl["null_sum"] == pytest.approx(0.005), "201/200 - 1 = +0.5%"
    out = fam._control_extra(b)["control"]
    assert out["edge_pct"] == pytest.approx(1.5)


def test_a_legacy_close_with_no_placebo_is_EXCLUDED_from_the_arm():
    """[(rp)] Caught in mum v2's FIRST live payload: the arm read
    `n: 4, mean_pct: 7.81` because her four v1 legacy flattens were counted.
    Those are v1-policy marks being realised — not v2's edge — and they carry
    no placebo, so the pair cannot be formed. Requiring BOTH legs excludes
    them for free and keeps `n == null_n` true by construction."""
    class _Stub:
        pass
    b = _Stub()
    b.s = _mum()
    b.bot_id = "freqtrade-mum-lshadow"
    b.meta = {"BTC": {"accrued": 0.0, "opened_ts": 1.0, "tag": "sma-fast-above-slow",
                      "entry": 100.0}}          # a v1 position: NO null_pair
    b.last_mark = {"ETH": 201.0}
    b.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
    b.fund_realized = 0.0
    b.n_closed = b.n_wins = 0
    b.closed = []
    b.cooldown = {}
    fam.Book.record_close(b, "BTC", 108.0, 4.0, "v1_legacy", notional=50.0)
    assert b.ctrl["n"] == 0, "a legacy close must not enter v2's control sample"
    assert b.ctrl["sum"] == 0.0
    assert fam._control_extra(b)["control"]["mean_pct"] is None


def test_the_arm_survives_a_redeploy():
    """A 30-day instrument in a container that redeploys whenever any shared
    organ changes cannot live in memory: it would reset to zero forever and
    never reach its own sample. Pinned by driving the real persist/restore
    field list rather than asserting on a name."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    persist = src[src.index("def persist(self):"):src.index("def persist(self):") + 1400]
    assert '"ctrl": self.ctrl' in persist, "the control arm must be persisted"
    restore = src[src.index("def restore(self):"):src.index("def persist(self):")]
    assert 'saved.get("ctrl")' in restore, "the control arm must be restored"


def test_pair_counts_can_never_diverge():
    """n and null_n move together or not at all — the edge is a PAIRED
    difference, and an unpaired observation cannot be differenced."""
    class _Stub:
        pass
    b = _Stub()
    b.s = _mum()
    b.bot_id = "freqtrade-mum-lshadow"
    b.fund_realized = 0.0
    b.n_closed = b.n_wins = 0
    b.closed = []
    b.cooldown = {}
    b.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
    for i, (pair, mark) in enumerate((("ETH", 201.0), ("ZZZ", None), ("ETH", 201.0))):
        b.meta = {"BTC": {"accrued": 0.0, "opened_ts": 1.0, "tag": "oversold-rebound",
                          "entry": 100.0, "null_pair": pair, "null_entry": 200.0}}
        b.last_mark = {"ETH": 201.0} if mark else {}
        fam.Book.record_close(b, "BTC", 102.0, 1.0, "roi", notional=50.0)
    assert b.ctrl["n"] == b.ctrl["null_n"] == 2, "the dark-placebo close is dropped from BOTH"


def test_a_dark_placebo_never_breaks_a_close():
    """An instrument that can break a trading loop is worse than no
    instrument — two LIVING books share this process."""
    class _Stub:
        pass
    b = _Stub()
    b.s = _mum()
    b.bot_id = "freqtrade-mum-lshadow"
    # placebo coin was never marked this cycle: the lookup must degrade, not raise
    b.meta = {"BTC": {"accrued": 0.0, "opened_ts": 1.0, "tag": "oversold-rebound",
                      "entry": 100.0, "null_pair": "ZZZ", "null_entry": 200.0}}
    b.last_mark = {}
    b.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
    b.fund_realized = 0.0
    b.n_closed = b.n_wins = 0
    b.closed = []
    b.cooldown = {}
    fam.Book.record_close(b, "BTC", 102.0, 1.0, "roi", notional=50.0)
    # atomic pairing: an unsettleable placebo drops the observation from BOTH
    # legs rather than leaving the real leg counted against nothing
    assert b.ctrl["n"] == 0 and b.ctrl["null_n"] == 0
    assert fam._control_extra(b)["control"]["edge_pct"] is None
