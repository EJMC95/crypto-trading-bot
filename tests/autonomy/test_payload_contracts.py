"""Tier 3 — PUBLISHER→CONSUMER payload contracts, built by the publisher.

WHY THIS FILE EXISTS (2026-07-30 (hj)). The single most repeated defect in this
repo is not a wrong algorithm — it is a consumer reading a key its publisher
does not emit, with a GREEN selftest, because the selftest's fixture was
hand-written by whoever wrote the consumer. It happened FOUR times on 30-Jul
alone, in one session:

  * (fz) `fleet_bus.scout_universe` read `marks[sym]["vol_m"]`; the scout emits
    `marks = {sym: PRICE}` (a float). The accessor returned an empty universe
    against every real payload.
  * (fz) the same accessor read `stress["med_bps"]`; the scout emits `"med"`.
  * (gb) the evidence board's hurting-refusal read `prop["hurting_levers"]`;
    `fleet_proprioception` publishes `verdicts: {lever: {...}}`. The single most
    important guard in the books' author was silently dead.
  * (gc) `grade_book` read `ep["lever"]`; the tracker emits `stance`, a dict.
    The grader was structurally incapable of ever grading.

Every one passed its own selftest. Every one was caught by a human diffing the
fixture against the live `/bus.json` — a control that is "remember to check",
which is the shape this repo replaces with guards on principle.

THE RULE THIS FILE ENFORCES: a consumer accessor is tested against a payload
produced by CALLING THE PUBLISHER, never by writing a dict that looks like one.
If the publisher's shape changes, these go red at the seam instead of at the
next incident.

The assertions are deliberately about NON-DEGENERACY, not values: each of the
four defects above produced an empty/None result that a value-free test would
have called "fine". `assert x` where the bug yields `[]` is the whole point.
"""
from datetime import datetime, timedelta, timezone

import pytest

import fleet_bus
import fleet_proprioception as prop
import lighter_market_scout as scout

NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# The publisher, invoked for real. `stats` rows carry the scout's own row shape
# (lighter_market_scout.py:156) — the ONE hand-built thing here, and it is the
# publisher's INPUT, not its output.
# ---------------------------------------------------------------------------
def _scout_stats():
    def row(qvol, oi, prem, liquid=True):
        return {"prem_bps": prem, "qvol": qvol, "oi": oi, "liquid": liquid,
                "mark": 100.0, "index": 100.0, "chg_pct": 1.0,
                "range_pos": 0.5, "funding_apr": 0.0}
    return {
        "BTC": row(9.0e8, 1.0e4, 2.0),
        "ETH": row(4.0e8, 8.0e3, -3.0),
        "SOL": row(2.5e7, 1.0e3, 12.0),
        "DUST": row(1.0e4, 5.0, 40.0, liquid=False),   # illiquid on purpose
    }


@pytest.fixture()
def snapshot():
    """The scout's REAL published payload, from its own builder."""
    stats = _scout_stats()
    aprs = {"BTC": 12.0, "ETH": -30.0, "SOL": 55.0, "DUST": -99.0}
    snap = scout.build_snapshot(stats, aprs, {}, {}, None,
                                now_ms=int(NOW.timestamp() * 1000))
    # build_snapshot stamps `updated` off the WALL CLOCK (now_ms only feeds
    # `ages_d`), so it must be OVERRIDDEN, not setdefault'd, or every accessor
    # below reads a payload that is hours stale relative to NOW and returns the
    # fail-safe empty — which looks exactly like the bug this file detects.
    snap["updated"] = _iso(NOW)
    snap["ttl_sec"] = 900
    return snap


@pytest.fixture(autouse=True)
def _clear_cache():
    fleet_bus._cache.clear()
    yield
    fleet_bus._cache.clear()


def _prime(key, payload):
    fleet_bus._cache[key] = {"ts": NOW, "payload": payload}


# ===========================================================================
# 1) scout `lighter-market`  ->  fleet_bus.scout_universe / _funding / stress
#    The (fz) defect: the accessor read a nested dict out of a map of floats.
# ===========================================================================
class TestScoutAccessors:
    def test_universe_is_non_empty_against_the_real_payload(self, snapshot):
        _prime("lighter-market", snapshot)
        uni = fleet_bus.scout_universe(min_vol_m=1.0, limit=10, current_time=NOW)
        # THE ASSERTION THAT WOULD HAVE CAUGHT (fz): the buggy accessor returned
        # [] here, and [] is the documented "keep your configured list" value —
        # so the widening silently did nothing and nothing was ever wrong.
        assert uni, "scout_universe returned nothing against a REAL snapshot"
        assert "BTC" in uni and "ETH" in uni, uni
        assert all(isinstance(s, str) for s in uni), uni

    def test_universe_ranks_by_real_turnover(self, snapshot):
        _prime("lighter-market", snapshot)
        uni = fleet_bus.scout_universe(min_vol_m=1.0, limit=3, current_time=NOW)
        assert uni[0] == "BTC", uni      # $900M > $400M > $25M
        assert uni.index("ETH") < uni.index("SOL"), uni

    def test_min_vol_floor_is_read_in_the_publisher_s_units(self, snapshot):
        """`vols` is $M. A consumer reading raw dollars would let everything
        through; one reading the wrong scale would let nothing."""
        _prime("lighter-market", snapshot)
        assert "SOL" in fleet_bus.scout_universe(min_vol_m=1.0, limit=10,
                                                 current_time=NOW)
        assert "SOL" not in fleet_bus.scout_universe(min_vol_m=100.0, limit=10, current_time=NOW)
        assert fleet_bus.scout_universe(min_vol_m=1e9, limit=10, current_time=NOW) == []

    def test_funding_map_reaches_the_consumer(self, snapshot):
        _prime("lighter-market", snapshot)
        f = fleet_bus.scout_funding(current_time=NOW)
        assert f, "scout_funding empty against a REAL snapshot"
        assert f.get("SOL") == pytest.approx(55.0), f

    def test_venue_stress_reads_the_key_the_scout_writes(self, snapshot):
        """The (fz) sibling defect: the accessor read `med_bps`, the scout
        writes `med`. A permanent None reads as 'no stress' — fail-open on the
        LIVE taker's stress veto."""
        _prime("lighter-market", snapshot)
        s = fleet_bus.venue_stress_bps(current_time=NOW)
        assert s is not None, "venue stress None against a REAL snapshot"
        assert s > 0, s

    def test_stress_is_computed_over_liquid_books_only(self, snapshot):
        """DUST is illiquid with a 40bps premium; including it would inflate
        the median the live taker vetoes on."""
        assert snapshot["stress"]["n"] == 3, snapshot["stress"]

    def test_dark_and_junk_buses_return_the_fail_safe_value(self):
        """CONTRACT: any doubt returns []/{}/None, and callers read that as
        'keep my configured list' — never as 'trade nothing'."""
        assert fleet_bus.scout_universe(current_time=NOW) == []
        assert fleet_bus.scout_funding(current_time=NOW) == {}
        assert fleet_bus.venue_stress_bps(current_time=NOW) is None
        for junk in ({}, {"vols": None}, {"vols": "nope"},
                     {"stress": "nope"}, {"stress": {"n": 4}}):
            _prime("lighter-market", {**junk, "updated": _iso(NOW),
                                      "ttl_sec": 900})
            assert fleet_bus.scout_universe(current_time=NOW) == []
            assert fleet_bus.venue_stress_bps(current_time=NOW) is None
            fleet_bus._cache.clear()

    def test_a_bare_numeric_stress_is_DELIBERATELY_tolerated(self):
        """Checked against the accessor, not assumed: `stress` may be a bare
        number as well as the scout's dict. Recorded here because it looks like
        a missing type check and is not one — the aliases exist so a future
        scout rename cannot turn this into a permanent None."""
        _prime("lighter-market", {"stress": 3, "updated": _iso(NOW),
                                  "ttl_sec": 900})
        assert fleet_bus.venue_stress_bps(current_time=NOW) == 3.0
        for alias in ("med", "med_bps", "median_bps", "bps"):
            fleet_bus._cache.clear()
            _prime("lighter-market", {"stress": {alias: 7.5},
                                      "updated": _iso(NOW), "ttl_sec": 900})
            assert fleet_bus.venue_stress_bps(current_time=NOW) == 7.5, alias

    def test_a_stale_payload_is_not_read(self, snapshot):
        old = dict(snapshot, updated=_iso(NOW - timedelta(hours=9)),
                   ttl_sec=900)
        fleet_bus._cache["lighter-market"] = {
            "ts": NOW - timedelta(hours=9), "payload": old}
        assert fleet_bus.scout_universe(current_time=NOW) == []


# ===========================================================================
# 2) proprioception episodes -> grade/verdicts -> the consumers' accessors
#    The (gb)/(gc) defects: `hurting_levers` was never published, and the
#    episode key was `stance`, not `lever`.
# ===========================================================================
def _real_episode(lever="carry.max_positions", value=12):
    """(in_flight, closed_record) built by the REAL publisher chain:

        fleet_tuning.active_levers()-shape  -> build_stances -> track -> run_once's record

    Nothing here is a hand-written episode. The two shapes are DIFFERENT and
    that difference is the (gc) trap: the tracker's in-flight episode carries
    `stance` (a dict) and the PUBLISHED record carries BOTH `stance` and
    `levers` (a sorted list). grade_book read neither — it read `lever`.
    """
    t0 = NOW - timedelta(days=3)
    active = {lever: {"value": value, "set_by": "evidence-board",
                      "expires": _iso(NOW + timedelta(hours=6))}}
    stances = prop.build_stances(active)
    open_eps, _ = prop.track({}, stances, t0.timestamp())
    _open2, closed = prop.track(open_eps, {}, NOW.timestamp())
    in_flight = next(iter(open_eps.values()))
    # run_once's record construction, verbatim (fleet_proprioception.py:879)
    c = closed[0]
    rec = {"group": c["group"], "levers": sorted(c["stance"]),
           "stance": c["stance"], "set_by": c.get("set_by") or [],
           "start": c["start"], "end": c["end"], "reason": c["reason"]}
    return in_flight, rec


class TestProprioceptionEpisodeShape:
    def test_the_tracker_emits_stance_and_never_lever(self):
        """(gc): grade_book read ep['lever'] and was inert forever. The fixture
        that 'passed' invented a key the tracker never produces."""
        ep, _rec = _real_episode()
        assert "stance" in ep and isinstance(ep["stance"], dict), ep
        assert "lever" not in ep, (
            "the tracker grew a 'lever' key \u2014 grade_book's fallback and this "
            "contract both need re-checking")
        assert next(iter(ep["stance"])) == "carry.max_positions", ep

    def test_the_published_record_carries_levers_AND_stance(self):
        """The two shapes DIFFER and consumers read different ones: grade_book
        reads `stance`, lever_verdicts reads `levers`. A test that only ever
        built one of them leaves the other unguarded \u2014 which is how (gc)
        happened."""
        _ep, rec = _real_episode()
        assert rec["levers"] == ["carry.max_positions"], rec
        assert rec["stance"] == {"carry.max_positions": 12}, rec
        assert "lever" not in rec, rec

    def test_grade_book_can_name_the_lever_from_a_real_episode(self):
        ep, _rec = _real_episode()
        ep = dict(ep, group="book:carry")
        lever = next(iter(ep.get("stance") or ()), "") or (ep.get("lever") or "")
        assert lever == "carry.max_positions", ep


class TestVerdictConsumers:
    """The (gb) defect: the board read a key the publisher does not write."""

    def _payload(self, signal="bad", lever="carry.max_positions"):
        """Verdicts computed by the PUBLISHER over records shaped by run_once
        \u2014 never a hand-written verdict dict."""
        _ep, rec = _real_episode(lever)
        eps = [dict(rec, status="graded", signal=signal, end=NOW.timestamp())
               for _ in range(max(2, prop.MIN_EPISODES))]
        return {"episodes": eps, "verdicts": prop.lever_verdicts(eps, now=None),
                "updated": _iso(NOW), "ttl_sec": 7200}

    def test_the_publisher_writes_verdicts_not_hurting_levers(self):
        p = self._payload()
        assert p["verdicts"], "lever_verdicts produced nothing for a book lever"
        assert "hurting_levers" not in p, (
            "if the publisher ever adds this key, the (gb) workaround and this "
            "contract must be revisited together")
        # the accessor the board's guard ACTUALLY calls, against the real shape
        assert prop.hurting_levers(p, NOW.timestamp()), p["verdicts"]

    def test_lever_outcome_reads_the_published_shape(self):
        _prime("fleet-proprioception", self._payload())
        out = fleet_bus.lever_outcome("carry.max_positions", NOW)
        # lever_outcome returns the verdict STRING, not the verdict dict —
        # checked against the accessor rather than assumed (my first cut of
        # this test called .get() on it, which is the same class of mistake
        # the whole file is about).
        assert out, "lever_outcome empty against a REAL verdicts payload"
        assert out == "hurting", out
        p = fleet_bus._cache["fleet-proprioception"]["payload"]
        assert p["verdicts"]["carry.max_positions"]["basis"] == "book-paired"

    def test_a_helping_verdict_is_not_read_as_hurting(self):
        """Symmetry: a guard that reports everything as hurting freezes the
        growth rail permanently \u2014 the failure that looks like safety."""
        p = self._payload(signal="good")
        _prime("fleet-proprioception", p)
        assert fleet_bus.lever_outcome("carry.max_positions", NOW) == "helping", p
        assert not prop.hurting_levers(p, NOW.timestamp()), p

    def test_unknown_lever_and_dark_bus_are_fail_safe(self):
        _prime("fleet-proprioception", self._payload())
        assert not fleet_bus.lever_outcome("nonesuch.knob", NOW)
        fleet_bus._cache.clear()
        assert not fleet_bus.lever_outcome("carry.max_positions", NOW)


# ===========================================================================
# 3) The taker's LIVE side gate (hj) — the policy stamp a grader era-splits on.
# ===========================================================================
class TestTakerPolicyStamp:
    def test_live_sides_are_stamped_and_short_only(self):
        import lighter_ticket_taker as tt
        assert tt.allowed_sides("lighter_live", "divergence") == {"short"}
        assert tt.allowed_sides("lighter_shadow", "divergence") == tt.ALL_SIDES
        # fail-CLOSED: a lens with no deliberate side decision fills nothing
        assert tt.allowed_sides("lighter_live", "breakout") == frozenset()
        # every live lens carries a side decision — this is what turns red if
        # LIVE_LENSES grows without a matching LIVE_SIDES entry
        assert all(tt.allowed_sides("lighter_live", l) for l in tt.LIVE_LENSES)

    def test_the_side_gate_does_not_depend_on_bull_mode(self):
        """THE INCIDENT (hj): 12 of the live book's 25 closes were
        long-divergence, and the only thing that stopped them was an env var
        defaulting to 'off'."""
        import lighter_ticket_taker as tt
        was = tt.BULL_MODE
        try:
            for bm in (True, False):
                tt.BULL_MODE = bm
                assert tt.allowed_sides("lighter_live", "divergence") == {"short"}
        finally:
            tt.BULL_MODE = was

    def test_side_of_agrees_with_the_entry_loop_is_long(self):
        import lighter_ticket_taker as tt
        for t in ({"side": "short"}, {"side": "long"}, {}, {"side": None}):
            assert (tt.side_of(t) == "long") is (t.get("side", "long") != "short")


# ===========================================================================
# [2026-07-30 (ho)] TWO CONTAINERS WRITING ONE BOOK — silent, and it destroys
# the evidence rather than the money. Measured on the fleet's ONLY go-live
# candidate: 14 overlapping same-pair positions and TWO distinct build stamps
# on perps-funding-carry-lshadow.
# ===========================================================================
class TestSoleWriterClaim:
    def _store(self, monkeypatch):
        import bot_pnl_store as store
        box = {}
        monkeypatch.setattr(store, "load_state", lambda k: box.get(k))
        monkeypatch.setattr(store, "save_state",
                            lambda k, v: box.__setitem__(k, v) or True)
        return store, box

    def test_first_claimant_wins_and_incumbent_refreshes(self, monkeypatch):
        store, _ = self._store(monkeypatch)
        assert store.claim_writer("bk", now=1000.0) == (True, None)
        assert store.claim_writer("bk", now=1100.0) == (True, None)

    def test_a_second_container_is_detected(self, monkeypatch):
        store, _ = self._store(monkeypatch)
        store.claim_writer("bk", now=1000.0)
        monkeypatch.setattr(store, "_WRITER_ID", "OTHER-CONTAINER")
        ok, other = store.claim_writer("bk", now=1100.0)
        assert ok is False and other, "a duplicate writer must be detected"

    def test_a_dead_incumbent_frees_the_book(self, monkeypatch):
        """A lock with no expiry is worse than none — a crashed container would
        silence the book forever."""
        store, _ = self._store(monkeypatch)
        store.claim_writer("bk", now=1000.0)
        monkeypatch.setattr(store, "_WRITER_ID", "OTHER-CONTAINER")
        t = 1000.0 + store.WRITER_CLAIM_TTL + 1
        assert store.claim_writer("bk", now=t) == (True, None)

    # -- [2026-08-01 (id)] A REDEPLOY IS NOT A DUPLICATE ---------------------
    # `_writer_id()` is RAILWAY_REPLICA_ID and Railway mints a new one on every
    # deploy, so a redeployed container met a claim from its own dead
    # predecessor and stood down against ITSELF. Measured from funding-carry's
    # own log: "already claimed by another container (funding-carry (838bd...))"
    # — its own service name in the other-container slot. Four consecutive
    # idle loops; it would have idled the book for the full 30-min TTL after
    # every deploy.

    def test_a_redeployed_container_takes_over_from_its_own_dead_replica(
            self, monkeypatch):
        store, _ = self._store(monkeypatch)
        monkeypatch.setattr(store, "service_name", lambda: "funding-carry")
        assert store.claim_writer("bk", now=1000.0) == (True, None)
        # same service redeployed -> brand new replica id, claim still warm
        monkeypatch.setattr(store, "_WRITER_ID", "NEW-REPLICA-AFTER-DEPLOY")
        ok, other = store.claim_writer("bk", now=1100.0)
        assert ok is True and other is None, (
            "a container must not stand down against a previous replica of "
            "its OWN service — that idles the book for the whole TTL on every "
            "deploy")

    def test_it_still_refuses_a_genuine_second_SERVICE(self, monkeypatch):
        """The steal must not weaken the protection this guard exists for:
        funding-carry and yield-harvester-shadow are the real duplicate."""
        store, _ = self._store(monkeypatch)
        monkeypatch.setattr(store, "service_name", lambda: "funding-carry")
        assert store.claim_writer("bk", now=1000.0) == (True, None)
        monkeypatch.setattr(store, "_WRITER_ID", "OTHER-CONTAINER")
        monkeypatch.setattr(store, "service_name",
                            lambda: "yield-harvester-shadow")
        ok, other = store.claim_writer("bk", now=1100.0)
        assert ok is False and "funding-carry" in str(other), (
            "a different SERVICE is a real duplicate and must still be refused")

    def test_an_unknown_service_is_never_stolen_from(self, monkeypatch):
        """(ht): unknown degrades to the OLD behaviour, never to a guess. A
        pre-(ht) claim carries no `svc`, so it must fall through to the TTL
        rather than be taken on the assumption that it is ours."""
        store, _ = self._store(monkeypatch)
        monkeypatch.setattr(store, "service_name", lambda: "")
        assert store.claim_writer("bk", now=1000.0) == (True, None)
        monkeypatch.setattr(store, "_WRITER_ID", "OTHER-CONTAINER")
        ok, other = store.claim_writer("bk", now=1100.0)
        assert ok is False, "an empty svc on both sides must not count as a match"

        # and one-sided knowledge is not a match either
        store2, box2 = self._store(monkeypatch)
        monkeypatch.setattr(store2, "_WRITER_ID", "R1")
        monkeypatch.setattr(store2, "service_name", lambda: "")
        store2.claim_writer("bk2", now=1000.0)
        monkeypatch.setattr(store2, "_WRITER_ID", "R2")
        monkeypatch.setattr(store2, "service_name", lambda: "funding-carry")
        ok2, _ = store2.claim_writer("bk2", now=1100.0)
        assert ok2 is False, "known-vs-unknown svc must not be treated as same"

    def test_it_fails_OPEN_on_any_error(self, monkeypatch):
        """THE DIRECTION MATTERS. A duplicate writer corrupts EVIDENCE, which
        is recoverable; a false positive would stop a book TRADING, which is
        lost opportunity. So a dark DB must never look like a collision."""
        import bot_pnl_store as store
        def boom(_k):
            raise RuntimeError("db down")
        monkeypatch.setattr(store, "load_state", boom)
        assert store.claim_writer("bk", now=1.0) == (True, None)

    def test_books_do_not_block_each_other(self, monkeypatch):
        store, _ = self._store(monkeypatch)
        assert store.claim_writer("book-a", now=1.0) == (True, None)
        monkeypatch.setattr(store, "_WRITER_ID", "OTHER")
        assert store.claim_writer("book-b", now=2.0) == (True, None), \
            "the claim is per-book, not global"

    def test_the_carry_bot_actually_calls_it(self):
        """Registered-but-unconsumed is this repo's most repeated defect."""
        import pathlib as _p
        src = (_p.Path(__file__).resolve().parents[2]
               / "funding_carry_bot.py").read_text()
        assert "claim_writer" in src, "carry does not check for a second writer"
        assert "duplicate_writer" in src, "the collision is not published"


# ===========================================================================
# [2026-07-31 (hp)] THE DOUBLE IS DELETED IN CODE, because `railway down` is
# not durable here — the deploy workflow resurrects a stopped service on the
# next push. Operator: "delete the double bot so this doesn't keep happening."
# ===========================================================================
class TestSoleWriterEnforced:
    def _src(self):
        import pathlib as _p
        return (_p.Path(__file__).resolve().parents[2]
                / "funding_carry_bot.py").read_text()

    def test_the_claim_runs_BEFORE_the_trading_pass(self):
        """(ho) checked at the PUBLISH block — after the loop had already
        opened and closed positions, so the duplicate still corrupted the very
        ledger the check existed to protect. A detector that runs after the
        damage is a report, not a guard.

        Bound via the AST, not string offsets: my first cut searched for
        "OPEN " and matched the words "fail-OPEN" inside my own comment —
        a test of the prose, not the code. Today's lesson, same day."""
        import ast
        tree = ast.parse(self._src())
        loop = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.While)
                    and isinstance(n.test, ast.Constant) and n.test.value is True)
        claim = min(n.lineno for n in ast.walk(loop)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", None) == "claim_writer")
        # the real trading act: writing a new entry into `positions`
        opens = [n.lineno for n in ast.walk(loop)
                 if isinstance(n, ast.Subscript)
                 and getattr(n.value, "id", None) == "positions"]
        assert opens, "could not locate the position-opening site"
        assert claim < min(opens), (
            f"claim_writer at line {claim} must precede the first positions[] "
            f"write at line {min(opens)} — otherwise the duplicate has already "
            f"traded by the time it is detected")

    def test_a_losing_claimant_stands_down_and_does_not_exit(self):
        """IDLE, never sys.exit: restartPolicy=always turns an exit into a
        permanent crash-loop (the Trail Blazer pattern, 15-Jul)."""
        src = self._src()
        blk = src[src.index("STANDING DOWN"):]
        blk = blk[:blk.index("time.sleep")]
        assert "sys.exit" not in blk and "SystemExit" not in blk, \
            "a standing-down container must idle, never exit"
        tail = src[src.index("STANDING DOWN"):]
        tail = tail[:tail.index("# ---- ") if "# ---- " in tail else 3000]
        assert "continue" in tail, "it must skip the cycle, not fall through"
        assert "time.sleep" in tail, "and wait, not spin"

    def test_it_still_records_why_it_is_silent(self):
        """A silenced container must be VISIBLE, not merely absent — the
        ambiguity that produced this duplicate was nobody being able to say
        which service owned the row. (ic) moved WHERE it says so; it must
        still say it."""
        src = self._src()
        blk = src[src.index("STANDING DOWN"):]
        blk = blk[:blk.index("time.sleep")]
        for key in ("standing_down", "duplicate_writer", '"caps"', "svc"):
            assert key in blk, f"standby record must carry {key}"

    def test_the_loser_never_writes_the_books_own_row(self):
        """[2026-08-01 (ic)] ONE BOOK, ONE WRITER has to bind the ROW, not only
        the ledger — a guard against two writers that is itself the second
        writer of that row enforces nothing.

        MEASURED the hour (ib) made this branch reachable for the first time:
        the standby loop is ~40s against the incumbent's ~5min, so the SILENCED
        container owned the row in 10 of 12 samples — the card read
        `standby / n=None / open=None` while the book was trading (n 84 -> 85,
        6 open). And `heartbeat` was worse than the clobber: it refreshes
        `updated_at` without writing content, so a DEAD incumbent would have
        read fresh indefinitely (I1).

        AST-bound to the standing-down branch, not a substring scan of the
        file: `publish` and `heartbeat` are called legitimately elsewhere in
        this same loop, so a page-wide grep would be green against the very
        defect it is meant to catch."""
        import ast
        tree = ast.parse(self._src())
        loop = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.While)
                    and isinstance(n.test, ast.Constant) and n.test.value is True)
        # the `if not _ok_writer:` branch — located by the claim, not by prose
        claim = next(n for n in ast.walk(loop)
                     if isinstance(n, ast.Call)
                     and getattr(n.func, "attr", None) == "claim_writer")
        branch = next(n for n in ast.walk(loop)
                      if isinstance(n, ast.If) and n.lineno > claim.lineno
                      and any(isinstance(c, ast.Continue) for c in ast.walk(n)))

        banned = {"publish", "heartbeat", "publish_paper_trade",
                  "snapshot_equity", "publish_trades"}
        for call in ast.walk(branch):
            if not isinstance(call, ast.Call):
                continue
            attr = getattr(call.func, "attr", None)
            if attr not in banned:
                continue
            raise AssertionError(
                f"the standing-down branch calls store.{attr}() at line "
                f"{call.lineno} — that writes the BOOK's row, which this "
                f"process does not own. Report on _standby_key() instead.")

        # and it must still record SOMEWHERE, or "visible not absent" is lost
        writes = [c for c in ast.walk(branch)
                  if isinstance(c, ast.Call)
                  and getattr(c.func, "attr", None) == "save_state"]
        assert writes, "a standing-down container must still record its state"
        # ...on a key derived from the book, never the bare book id
        keyed_off_helper = any(
            isinstance(w.args[0], ast.Call)
            and getattr(w.args[0].func, "id", None) == "_standby_key"
            for w in writes if w.args)
        assert keyed_off_helper, (
            "standby state must go to _standby_key(bot_id), not a bare row id")

    def test_standby_key_is_a_suffix_of_the_book_it_shadows(self):
        """A reader holding the book id must be able to find its standby
        record without a lookup table."""
        import funding_carry_bot as fc
        book = "perps-funding-carry-lshadow"
        key = fc._standby_key(book)
        assert key != book, "the standby key must not BE the book's row"
        assert key.startswith(book), f"not derivable from the book: {key}"

    def test_enforcement_is_still_fail_open(self, monkeypatch):
        """A Postgres blip must NEVER idle the book. Evidence corruption is
        recoverable; a halted book is lost opportunity."""
        import bot_pnl_store as store
        def boom(_k):
            raise RuntimeError("db down")
        monkeypatch.setattr(store, "load_state", boom)
        ok, other = store.claim_writer("perps-funding-carry", now=1.0)
        assert ok is True and other is None


# ===========================================================================
# [2026-07-31 (hr)] THE LEDGER QUARANTINE — real trades that are not evidence.
# ===========================================================================
class TestLedgerQuarantine:
    BOT = "lighter-ticket-taker-lshadow"

    def test_the_churn_episode_is_withheld(self):
        import bot_pnl_store as s
        assert s.is_quarantined(self.BOT, "BOT/USDC", "2026-07-22T03:46:00+00:00")
        assert s.is_quarantined(self.BOT, "CXMT/USDC", "2026-07-21T23:19:00+00:00")

    def test_the_GENUINE_20_jul_stops_are_kept(self):
        """The window is dated for a reason: the two 20-Jul BOT
        long-divergence stops had 47.9/87.2bps gaps — normal book behaviour,
        real evidence. A quarantine that swallowed them would be hiding losses."""
        import bot_pnl_store as s
        assert not s.is_quarantined(self.BOT, "BOT/USDC", "2026-07-20T11:00:00+00:00")

    def test_it_is_scoped_to_pair_AND_bot(self):
        import bot_pnl_store as s
        assert not s.is_quarantined(self.BOT, "SOL/USDC", "2026-07-22T03:46:00+00:00")
        assert not s.is_quarantined("perps-funding-carry-lshadow", "BOT/USDC",
                                    "2026-07-22T03:46:00+00:00")

    def test_it_fails_OPEN_on_anything_unparseable(self):
        """A filter that swallows what it cannot classify silently shrinks
        every sample it touches — the disease, not the cure."""
        import bot_pnl_store as s
        for args in ((None, None, None), ("x", "BOT/USDC", "garbage"),
                     ("x", "BOT/USDC", ""), (1, 2, 3)):
            assert s.is_quarantined(*args) is False, args

    def test_every_entry_carries_a_reason_and_a_closed_window(self):
        """No open-ended quarantines, and no undocumented ones — this is not a
        place to hide losses."""
        import bot_pnl_store as s
        assert s.LEDGER_QUARANTINE, "empty is fine, but then delete the machinery"
        for pair, bot, lo, hi, why in s.LEDGER_QUARANTINE:
            assert pair and bot, (pair, bot)
            assert len(lo) == 10 and len(hi) == 10 and lo <= hi, (lo, hi)
            assert len(why) > 30, f"{pair}: a quarantine needs a real reason"

    def test_the_reader_actually_applies_it(self):
        import pathlib as _p
        src = (_p.Path(__file__).resolve().parents[2] / "bot_pnl_store.py").read_text()
        body = src[src.index("def fetch_paper_trades"):]
        assert "is_quarantined(" in body, "declared but never applied"
        assert "_quarantined" in body, "a silent filter hides its own effect"
