"""[2026-08-13 (lt)] 🏛️ THE PARLIAMENT'S RESTARTS: counting them exactly, and
the in-process state each one destroys.

THE CARRIED FINDING. `(lg)` closed the sampling half of the churn detector —
count from the publisher's own ~5-minute series, not from this organ's 900s
wake-ups — and named the remaining half in its own docstring: *"or have the
Parliament publish a monotone `boots` counter"*. `(li)` carried it forward
still-open, together with two siblings found in the same sweep: `last_skip` is
a never-reset latch whose ml-gate variant embeds a formatted probability
(inflating that class's transition count **2.98x** and misleading two of six
investigations), and `self.signals` is in-process TTL'd state that no restart
restores — *"the last open instance of a class closed three times already"*.

WHY A COUNTER RATHER THAN A BETTER INFERENCE. Every reading built on
`data.cycles` infers a restart from a REGRESSION, and that is a lower bound no
sampling rate can lift: two boots inside one publishing gap look like one, and
a boot that dies before it publishes anything leaves no regression at all. A
monotone counter kept OUTSIDE the process has neither hole. The discriminating
test for that claim is `test_two_boots_in_one_gap_*` below — the inference and
the counter are handed the SAME tape and must disagree, or the new code has
bought nothing.

METHOD (the `(lh)` lesson, which is why there is not one AST assertion here).
Source-shaped tests detect DELETION and not DISABLEMENT: five mutations that
restored the exact bugs those tests were written for all stayed green. So every
test below drives the REAL code and asserts on what it WROTE — a real SQLite
file across simulated restarts, the real publisher into the real consumer, the
real entry path for the latch.
"""
import time

import pytest

import fleet_immune as FI
from parliament.bus import EcosystemBus
from parliament.ecosystem_db import EcosystemDB
from parliament.strategies import SIGNAL_TTL_SEC, PMBot


pytestmark = pytest.mark.autonomy


# ---------------------------------------------------------------------------
# 1 · the counter itself — a real file, across real reconnections
# ---------------------------------------------------------------------------

class TestTheBootCounterSurvivesRestart:
    def test_it_counts_up_across_restarts(self, tmp_path):
        """A 'restart' is a NEW EcosystemDB on the same file — the only thing
        the container actually does."""
        path = str(tmp_path / "p.db")
        got = [EcosystemDB(path=path).bump_boots() for _ in range(4)]
        assert [n for n, _ in got] == [1, 2, 3, 4]
        assert all(durable for _, durable in got)

    def test_a_memory_only_db_reports_itself_undurable(self):
        """The in-memory fallback is right for a shadow book and fatal for this
        reading: every boot counts itself #1 forever, so the deltas are
        identically zero and a crash-looping organ certifies as healthy. It has
        to say so — `(le)`/`(lg)`'s convergent-metric trap."""
        db = EcosystemDB(path=":memory:")
        assert db.durable is False
        assert db.bump_boots() == (1, False)
        assert EcosystemDB(path=":memory:").bump_boots() == (1, False)

    def test_a_junk_memory_row_still_boots(self, tmp_path):
        """Never raise on the startup path: a corrupt counter restarts the
        count, it does not stop the chamber."""
        path = str(tmp_path / "p.db")
        db = EcosystemDB(path=path)
        for junk in ({"n": "many"}, {"n": None}, {"n": True}, {}):
            db.remember(db.BOOTS_KEY, junk)
            assert EcosystemDB(path=path).bump_boots()[0] == 1

    def test_a_negative_counter_cannot_drag_it_below_one(self, tmp_path):
        path = str(tmp_path / "p.db")
        db = EcosystemDB(path=path)
        db.remember(db.BOOTS_KEY, {"n": -5})
        assert EcosystemDB(path=path).bump_boots()[0] == 1

    def test_the_30_day_prune_does_not_reset_the_count(self, tmp_path):
        """`prune` clears signals/trades/candles. If it took the boot counter
        with them, the fleet's restart history would silently zero every month
        — and the detector would read the reset as health."""
        path = str(tmp_path / "p.db")
        db = EcosystemDB(path=path)
        for _ in range(7):
            EcosystemDB(path=path).bump_boots()
        db.prune(keep_days=0.0)
        assert EcosystemDB(path=path).bump_boots()[0] == 8


# ---------------------------------------------------------------------------
# 2 · the consumer counts EXACTLY — and refuses when it cannot
# ---------------------------------------------------------------------------

def _hist(rows, now):
    """History rows in `fetch_state_history`'s real shape."""
    return lambda key, limit=0: [
        {"ts": FI._iso(now - age), "payload": {"data": p}} for age, p in rows]


def _boots(n, durable=True):
    return {"boots": n, "boots_durable": durable, "cycles": 5}


class TestTheCountIsExact:
    def test_it_counts_the_advance_over_the_window(self):
        now = FI.now_ts()
        f = _hist([(3000, _boots(10)), (2000, _boots(11)),
                   (1000, _boots(13))], now)
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            fetch=f) == (3, 3)

    def test_two_boots_in_one_gap_are_BOTH_counted(self):
        """THE POINT OF THE WHOLE CHANGE, stated as a disagreement.

        One publishing gap contains two boots. The counter advances by 2. The
        cycles inference sees a single regression (5 -> 4) and reports 1. If
        these two ever agree, the exact path has bought nothing and should be
        deleted."""
        now = FI.now_ts()
        rows = [(3000, {"boots": 10, "boots_durable": True, "cycles": 5}),
                # ...two boots happen here, only the second one publishes...
                (2000, {"boots": 12, "boots_durable": True, "cycles": 4})]
        f = _hist(rows, now)
        exact, _ = FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now, fetch=f)
        inferred = FI.churn_from_history("parliament", "data.cycles", now,
                                         fetch=f)
        assert exact == 2
        assert inferred == (1, 0, 2)          # the regression-counter's ceiling
        assert exact > inferred[0] + inferred[1]

    def test_a_boot_that_never_published_is_still_counted(self):
        """The failure most worth paging on leaves the least evidence: a boot
        that dies before its first publish writes no row at all. The durable
        counter still carries it into the NEXT boot's payload."""
        now = FI.now_ts()
        f = _hist([(3000, _boots(40)), (600, _boots(43))], now)   # 3 boots, 1 row
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            fetch=f)[0] == 3

    def test_a_lost_volume_never_reads_as_negative(self):
        """The persist volume is lost and the counter restarts at 1. Endpoint
        differencing would return -39, which reads as health. Positive deltas
        degrade it to an undercount instead."""
        now = FI.now_ts()
        f = _hist([(3000, _boots(40)), (2000, _boots(1)),
                   (1000, _boots(2))], now)
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            fetch=f) == (1, 3)

    def test_an_undurable_counter_is_REFUSED_not_believed(self):
        """A memory-only publisher stamps 1 forever. Believing it would report
        zero boots for an organ restarting every five minutes."""
        now = FI.now_ts()
        f = _hist([(3000, _boots(1, durable=False)),
                   (2000, _boots(1, durable=False)),
                   (1000, _boots(1, durable=False))], now)
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            fetch=f) is None

    def test_a_publisher_without_the_field_yields_nothing(self):
        """Deploy order must not matter: until the Parliament ships this, the
        inference has to keep working."""
        now = FI.now_ts()
        f = _hist([(3000, {"cycles": 5}), (1000, {"cycles": 0})], now)
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            fetch=f) is None

    @pytest.mark.parametrize("bad", [
        lambda k, limit=0: [],
        lambda k, limit=0: None,
        lambda k, limit=0: (_ for _ in ()).throw(RuntimeError("db")),
    ])
    def test_a_dark_history_claims_nothing(self, bad):
        assert FI.boots_from_history("parliament", "data.boots",
                                     "data.boots_durable", FI.now_ts(),
                                     fetch=bad) is None

    def test_the_window_bounds_it(self):
        now = FI.now_ts()
        f = _hist([(200000, _boots(1)), (3000, _boots(30)),
                   (1000, _boots(31))], now)
        assert FI.boots_from_history(
            "parliament", "data.boots", "data.boots_durable", now,
            window_s=86400, fetch=f)[0] == 1


class TestTheScannerPrefersTheExactCount:
    """Behavioural: what does `restart_churn` actually REPORT?"""

    def _states(self, now, boots, durable=True, cycles=5):
        return {"parliament": {
            "updated": FI._iso(now), "ttl_sec": 900,
            "data": {"cycles": cycles, "boots": boots,
                     "boots_durable": durable},
            "health": {"stalled": []}}}

    def test_the_detail_reports_the_exact_basis_and_count(self, monkeypatch):
        now = FI.now_ts()
        monkeypatch.setattr(FI.store, "fetch_state_history",
                            _hist([(3000, _boots(10)), (2000, _boots(14)),
                                   (1000, _boots(16))], now))
        out = FI.restart_churn(self._states(now, 16), {}, now)
        assert len(out) == 1
        detail = out[0]["detail"]
        assert "6 RESTART(s)" in detail
        assert "durable boot counter" in detail
        # An exact count must not be hedged as a floor — that is what makes it
        # worth having over the inference.
        assert "LOWER BOUND" not in detail

    def test_it_beats_the_inference_on_the_same_payload(self, monkeypatch):
        """Same tape, both readings available: the exact one must win. Six
        boots occurred; the cycles column regresses only twice."""
        now = FI.now_ts()
        rows = [(3000, {"boots": 10, "boots_durable": True, "cycles": 9}),
                (2000, {"boots": 14, "boots_durable": True, "cycles": 4}),
                (1000, {"boots": 16, "boots_durable": True, "cycles": 2})]
        monkeypatch.setattr(FI.store, "fetch_state_history", _hist(rows, now))
        out = FI.restart_churn(self._states(now, 16), {}, now)
        assert "6 RESTART(s)" in out[0]["detail"]
        assert "2 RESTART(s)" not in out[0]["detail"]

    def test_an_undurable_counter_falls_back_and_says_so(self, monkeypatch):
        now = FI.now_ts()
        rows = [(3000, {"boots": 1, "boots_durable": False, "cycles": 9}),
                (2000, {"boots": 1, "boots_durable": False, "cycles": 0}),
                (1500, {"boots": 1, "boots_durable": False, "cycles": 9}),
                (1000, {"boots": 1, "boots_durable": False, "cycles": 0}),
                (900, {"boots": 1, "boots_durable": False, "cycles": 9}),
                (800, {"boots": 1, "boots_durable": False, "cycles": 0}),
                (700, {"boots": 1, "boots_durable": False, "cycles": 9}),
                (600, {"boots": 1, "boots_durable": False, "cycles": 0})]
        monkeypatch.setattr(FI.store, "fetch_state_history", _hist(rows, now))
        out = FI.restart_churn(self._states(now, 1, durable=False), {}, now)
        # The inference still fires (4 regressions) and must declare its bound.
        assert len(out) == 1
        assert "publisher series" in out[0]["detail"]
        assert "LOWER BOUND" in out[0]["detail"]

    def test_the_inference_always_declares_itself_a_floor(self, monkeypatch):
        """`(lg)`'s own carried note: *'the number is a LOWER BOUND and the
        detail line does not say so'*."""
        now = FI.now_ts()
        rows = [(3000, {"cycles": 9}), (2500, {"cycles": 0}),
                (2000, {"cycles": 9}), (1500, {"cycles": 0}),
                (1000, {"cycles": 9}), (500, {"cycles": 0}),
                (400, {"cycles": 9}), (300, {"cycles": 0})]
        monkeypatch.setattr(FI.store, "fetch_state_history", _hist(rows, now))
        out = FI.restart_churn(self._states(now, None), {}, now)
        assert out and "LOWER BOUND" in out[0]["detail"]


def test_the_exact_counter_key_is_actually_fetched():
    """The (hh) class: a path the organ never reads is dead code that passes
    every test written about it in isolation."""
    src = open("fleet_immune.py").read()
    for key in FI.BOOT_COUNTERS:
        assert key in FI.RESTART_COUNTERS, (
            f"{key} must also be watched by the inference, so a publisher "
            f"without the durable counter is not silently unwatched")
    assert "boots_from_history" in src.split("def restart_churn")[1], (
        "the exact path must be reached from restart_churn")


# ---------------------------------------------------------------------------
# 3 · the skip latch — a stable class, and a clock
# ---------------------------------------------------------------------------

def _bot(strategy="meanrev", db=None):
    return PMBot("pm-turnbull", strategy, data=None, bus=EcosystemBus(),
                 db=db, ml=None, howard=None)


class TestTheSkipLatch:
    def test_the_class_is_stable_while_the_detail_varies(self):
        """THE MEASURED DEFECT: two ml-gate skips at different probabilities
        are ONE state, and counting transitions of `last_skip` counted them as
        two. The class must not move; the human string may."""
        bot = _bot()
        bot._skip("H100", "ml-gate", "0.26")
        first_class, first_str = bot.last_skip_class, bot.last_skip
        bot._skip("KAITO", "ml-gate", "0.30")
        assert bot.last_skip_class == first_class == "ml-gate"
        assert bot.last_skip != first_str          # human field still detailed
        assert "0.30" in bot.last_skip

    def test_distinct_gates_are_distinct_classes(self):
        bot = _bot()
        seen = set()
        for klass in ("ml-gate", "brain-regime-gate", "notional-cap",
                      "max-open", "cooldown"):
            bot._skip("BTC", klass)
            seen.add(bot.last_skip_class)
        assert len(seen) == 5

    def test_the_human_field_keeps_its_historical_shape(self):
        """Nothing that already reads `last_skip` may break."""
        bot = _bot()
        bot._skip("H100", "ml-gate", "0.26")
        assert bot.last_skip == "H100:ml-gate(0.26)"
        bot._skip("BTC", "brain-regime-gate")
        assert bot.last_skip == "BTC:brain-regime-gate"

    def test_a_never_skipped_book_has_no_age(self):
        """`0` would be a lie (it means 'just now'); absent means absent."""
        assert _bot().last_skip_ts == 0.0

    def test_the_latch_is_dated(self):
        bot = _bot()
        before = time.time()
        bot._skip("BTC", "ml-gate", "0.10")
        assert before <= bot.last_skip_ts <= time.time()

    def test_a_successful_entry_drops_the_latch(self):
        """The defect: a book that has been entering happily for hours still
        displayed the last thing that ever blocked it."""
        bot = _bot()
        bot._skip("BTC", "ml-gate", "0.26")
        bot._skip_clear()
        assert bot.last_skip == bot.last_skip_class == bot.last_skip_detail == ""
        assert bot.last_skip_ts == 0.0


def test_the_entry_path_clears_the_latch_on_a_real_open():
    """Behavioural, not source: run the REAL `_try_enter` to a filled order and
    read the field afterwards. An `_skip_clear()` deleted from the success path
    reddens this; one that is merely commented out does too."""
    import parliament.strategies as S

    bot = _bot(strategy="scalp")
    if bot.broker is None:
        pytest.skip("paper_broker unavailable")
    bot._skip("OLD", "ml-gate", "0.11")
    bot.ml = None                                    # -> p_win 0.5, not ready
    bot._entry_blocked = lambda sym, direction: None
    bot._fill_px = lambda sym, is_buy: 100.0
    bot._open_notional = lambda: 0.0
    assert bot._try_enter("BTC", 1, {"strength": 1.0, "meta": {}}) is True
    assert bot.last_skip == "", "a filled entry must drop the latch"
    assert bot.last_skip_class == ""


# ---------------------------------------------------------------------------
# 4 · the signal window — the (hj) publisher/consumer seam
# ---------------------------------------------------------------------------

class TestTheSignalWindowIsRestored:
    def _seed(self, db, scanner, sym, direction=1, strength=0.9,
              meta=None, age=0.0):
        """Publish EXACTLY as ScannerEngine.run_once does — `sig['meta']` into
        the `payload` column. Writing this by hand from the consumer's side is
        the mistake the (hj) rule exists to prevent."""
        db.add_signal(scanner, sym, direction, strength,
                      meta if meta is not None else {"regime": "calm"},
                      ts=time.time() - age)

    def test_a_restored_signal_reaches_the_consumer_as_meta(self, tmp_path):
        """THE SEAM. `add_signal` stores meta into a column named `payload`, so
        `recent_signals` returns it as `payload` — while every consumer here
        reads `s['meta']`. Restoring the row verbatim puts a KeyError in the
        entry path. This drives publisher -> restore -> the REAL consumer read
        and asserts the value is non-degenerate."""
        db = EcosystemDB(path=str(tmp_path / "p.db"))
        self._seed(db, "volatility_regime", "BTC", meta={"regime": "expanding"})
        bot = _bot(strategy="meanrev", db=db)       # confirm = volatility_regime
        assert bot.restore_signals() == 1
        sig = bot._fresh_signal("signals.volatility_regime", "BTC")
        assert sig is not None
        assert sig["meta"].get("regime") == "expanding"   # the consumer's read
        assert sig["direction"] == 1 and sig["strength"] == pytest.approx(0.9)

    def test_it_restores_the_primary_topic_too(self, tmp_path):
        db = EcosystemDB(path=str(tmp_path / "p.db"))
        self._seed(db, "mean_reversion", "ETH", direction=-1)
        bot = _bot(strategy="meanrev", db=db)
        assert bot.restore_signals() == 1
        assert bot._fresh_signal("signals.mean_reversion", "ETH") is not None

    def test_an_expired_signal_is_not_resurrected(self, tmp_path):
        """Durability must not smuggle a stale signal past the TTL — that would
        be worse than forgetting it (I1)."""
        db = EcosystemDB(path=str(tmp_path / "p.db"))
        self._seed(db, "mean_reversion", "ETH", age=SIGNAL_TTL_SEC + 60)
        bot = _bot(strategy="meanrev", db=db)
        assert bot.restore_signals() == 0
        assert bot._fresh_signal("signals.mean_reversion", "ETH") is None

    def test_the_ttl_is_enforced_HERE_not_only_by_the_query(self):
        """The previous test passes even with the in-code cutoff deleted,
        because `recent_signals(hours=...)` already filters — so it does not
        verify the check it looks like it verifies. Mutation M9 proved that.

        The cutoff is still load-bearing: it is the only thing standing between
        a DB whose window filter does not bite and a stale signal being handed
        to the entry path as fresh. A restart resurrecting an expired signal is
        strictly worse than forgetting it (I1). This fake ignores `hours`
        exactly as such a DB would."""
        class IgnoresTheWindow:
            def recent_signals(self, hours=4.0, scanner=None):
                return [{"scanner": "mean_reversion", "sym": "ETH",
                         "ts": time.time() - (SIGNAL_TTL_SEC + 600),
                         "direction": -1, "strength": 0.9, "payload": {}}]

        bot = _bot(strategy="meanrev", db=IgnoresTheWindow())
        assert bot.restore_signals() == 0
        assert bot._fresh_signal("signals.mean_reversion", "ETH") is None

    def test_another_books_topics_are_not_restored_into_this_one(self, tmp_path):
        db = EcosystemDB(path=str(tmp_path / "p.db"))
        self._seed(db, "funding_extreme", "SOL")     # pm-rudd's topic
        bot = _bot(strategy="meanrev", db=db)
        assert bot.restore_signals() == 0
        assert bot.signals == {}

    def test_the_flip_exit_works_again_after_a_restart(self, tmp_path):
        """The trading consequence, end to end: `_exit_reason`'s flip rule reads
        an OPPOSING primary signal, so an empty window silently removes an exit
        from a held position. Same DB, fresh bot = a restart."""
        db = EcosystemDB(path=str(tmp_path / "p.db"))
        self._seed(db, "mean_reversion", "ETH", direction=-1, strength=0.8)
        cold = _bot(strategy="meanrev", db=db)
        assert cold._fresh_signal("signals.mean_reversion", "ETH") is None
        cold.restore_signals()
        opp = cold._fresh_signal("signals.mean_reversion", "ETH")
        assert opp is not None and opp["direction"] == -1 and opp["strength"] >= 0.6

    def test_a_dark_db_leaves_the_book_exactly_where_a_restart_does(self):
        """Fail-safe is TODAY'S behaviour, not an exception."""
        assert _bot(strategy="meanrev", db=None).restore_signals() == 0

        class Broken:
            def recent_signals(self, hours=4.0, scanner=None):
                raise RuntimeError("db gone")

        bot = _bot(strategy="meanrev", db=Broken())
        assert bot.restore_signals() == 0
        assert bot.signals == {}

    def test_junk_rows_are_skipped_not_guessed(self, tmp_path):
        class Junk:
            def recent_signals(self, hours=4.0, scanner=None):
                return [{"scanner": "mean_reversion", "sym": "ETH", "ts": None},
                        {"scanner": "mean_reversion", "sym": "X", "ts": "soon"},
                        {"scanner": None, "sym": "Y", "ts": time.time()},
                        {"scanner": "mean_reversion", "sym": "OK",
                         "ts": time.time(), "direction": 1, "strength": 0.7,
                         "payload": {"a": 1}}]

        bot = _bot(strategy="meanrev", db=Junk())
        assert bot.restore_signals() == 1
        assert bot._fresh_signal("signals.mean_reversion", "OK") is not None
