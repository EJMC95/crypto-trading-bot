"""🏭 THE PRODUCTION PIPE CARD — its numbers come from four publishers, and a
dark publisher must render UNKNOWN rather than a plausible zero.

WHY THIS CARD NEEDED ITS OWN TEST FILE, stated as the defect it prevents.
Eamon's standing complaint is that no new bot has appeared on the dashboard as
a promoted book, and answering it meant hand-reading /bus.json. `pipeline_card`
joins `golive-readiness`, `xp-judge`, `fleet-allocation` and
`strategy-incubator` into one answer. Every one of those keys can be dark,
stale, or a payload version that predates a field — and here that failure is
dangerous in one SPECIFIC direction, which is the trap these tests are pointed
at:

    `0 at the bar` is a REAL, TRUE, EVERYDAY measurement on this fleet.

So a dark grader coerced to `0` renders as a confident, plausible, wrong
reading that is byte-identical to the healthy one — the (hf)/I1 shape at the
reporting layer, and exactly the "convergent metric is not a health check"
class. `test_a_dark_grader_renders_unknown_not_zero` is the load-bearing test:
it renders the SAME card twice, once with a real `ready: []` and once with the
key absent, and requires the two outputs to DIFFER.

FIXTURES ARE PUBLISHER-BUILT, never hand-written to "look like" the payload —
the (hj) rule. Concretely:
  * `fleet_allocation.build()` is the organ's own pure payload builder, plus
    the two keys `run_once` bolts on (`zero_close_books`, `sample`);
  * `golive_readiness.stats/grade/bar_map/gate_horizon/decision_docket` are the
    grader's own functions, called in `main()`'s order;
  * `experiment_judge.pair_census()` is the judge's real census, driven with
    real `bot_pnl`-shaped rows and real ledger rows so the pair states
    (`policy_unstamped`, `policy_mismatch`, `live_row_dark`, `stood_down`) are
    the judge's verdicts, not mine — the farmer's `stood_down` comes from the
    live `fleet_bus.RETIRED_LIVE_ARMS` declaration;
  * `strategy_incubator.is_enactable/proposal_capacity/assess_champion` decide
    the incubator fields.

The pair fixtures deliberately carry MORE PAIRS THAN ONE CLASS and are checked
for ORDER: a one-pair fixture cannot test that WIRE-blocked pairs lead, and
leading with the clearable class is the entire editorial claim of the card.
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import experiment_judge as ej           # noqa: E402
import fleet_allocation as fa           # noqa: E402
import fleet_bus as _fb                 # noqa: E402
import golive_readiness as g            # noqa: E402
import pnl_dashboard as dash            # noqa: E402
import strategy_incubator as si         # noqa: E402


@pytest.fixture(autouse=True)
def _georgia_live_for_mechanics(monkeypatch):
    """[(we)] These card tests use 🔮 georgia as the `policy_mismatch` (WIRE)
    example and 💸 the farmer as the `stood_down` example, to check the pipeline
    card sorts blockers by who can clear them. georgia's live arm is now retired
    (fleet_bus.RETIRED_LIVE_ARMS), which would short-circuit her to `stood_down`
    before the policy check and collapse the two distinct verdicts into one — so
    force her live to keep her the policy_mismatch example. Her retirement is
    owned by test_georgia_live_retired.py."""
    assert "freqtrade-georgia-lighter" in _fb.RETIRED_LIVE_ARMS  # keep this honest
    monkeypatch.setenv("GEORGIA_LIVE_RETIRED_OVERRIDE", "run")

#: [2026-08-26] THE WALL CLOCK, not a frozen instant — and this file's own
#: `_row()` docstring is where the rule comes from: *"a fixture whose verdicts
#: depend on what time the suite happens to run is worse than no fixture"*.
#: That was honoured for the `bot_pnl` rows and NOT for the four bot_state
#: payloads below, which stamp `updated = NOW` beside a REAL `ttl_sec` while
#: the card judges freshness against the actual clock.
#:
#: MEASURED: frozen at `2026-08-26 12:00Z` this file passed when it was written
#: and then rotted organ by organ as each TTL expired — 0 failures at 13:1xZ,
#: 5 at 14:1xZ, **11 at 14:4xZ**, and 11 on every machine and every CI run
#: thereafter, permanently. Bisected to the commit that introduced it: its
#: parent is green, it is red. CI passed it only because CI ran inside the
#: window.
#:
#: Every use of NOW here is RELATIVE (-40d, -19.9d, -i hours, -TTL*10s) or means
#: "the current instant" (`gate_horizon(now=)`, `pair_census`), and no assertion
#: depends on the literal date — so tracking the clock is the whole fix. A
#: frozen anchor would also work IF the card's clock were frozen with it; it is
#: not, and pinning one half of a comparison is what broke this.
#:
#: Mutation-verified: restoring the frozen anchor reddens all 11 again, and
#: `now() - 3h` reddens 3 — so what this pins is AGE, not the literal date.
#: DECLARED, not fixed: `now() + 3h` stays GREEN, because a future-stamped
#: payload has a negative age and every `age < ttl` check reads that as fresh.
#: That is a property of the freshness contract, not of this fixture, and it is
#: bounded live by whatever clock skew exists between a container and the
#: reader — named here so it is not rediscovered as a mystery.
NOW = datetime.now(timezone.utc)
_T0 = NOW - timedelta(days=40)


# ---------------------------------------------------------------------------
# publisher-built payloads
# ---------------------------------------------------------------------------
def _pcts(pcts, span_days=40.0):
    """(pnl_pct, pnl_usd, closed_at) triples in `stats()`'s own input shape."""
    step = timedelta(days=span_days / max(1, len(pcts) - 1))
    return [(p, p * 10.0, _T0 + i * step) for i, p in enumerate(pcts)]


def alloc_payload(books, zero_close=()):
    """`fleet_allocation.build()` + the two keys `run_once` adds after it.

    Mirrors the publisher's own call order rather than restating its output
    shape, so a change to `build()` reaches this fixture the way it reaches
    the dashboard."""
    p = fa.build(books)
    p["zero_close_books"] = sorted(zero_close)
    p["sample"] = "all-time-pooled"
    p["updated"] = NOW.isoformat()
    return p


def golive_payload(books_pcts, zero_ledger=(), docket_prior=None,
                   docket_now=None, floor_pcts=None, docket_valid=True):
    """The grader's payload, assembled through its OWN functions.

    `books_pcts` is {bot: [per-trade pcts]}. Each book runs through `stats` ->
    `grade` -> `bar_map` -> `gate_horizon`, exactly as `main()` does, and the
    docket through `decision_docket` — so `ready`, the horizon verdicts and the
    docket ages are the grader's verdicts and not mine.

    `zero_ledger` books take the roster sweep's OWN branch: a `below_floor`
    entry plus a `roster_zero_ledger` docket input. That branch matters here
    because the card merges `books` and `below_floor` before counting
    on-track — a fixture with only graded books cannot see a merge defect.

    `floor_pcts` puts a THIN but graded book in `below_floor`, the (kv) shape:
    a book under the publish floor still gets a horizon from its own sample,
    so it can be `on_track` while never appearing in `books`. Dropping the
    merge would silently undercount exactly those books.

    `docket_valid` mirrors the grader's own field, which it publishes as
    `bool(_seen_ok)` — False when it could not read its prior docket-seen map,
    so every clock reads as first-seen today and the ages are FLOORS."""
    books, ready, current, floor = {}, [], {}, {}
    for bot, pcts in books_pcts.items():
        rows = _pcts(pcts)
        s = g.stats(rows)
        ok, fails = g.grade(s)
        bars = g.bar_map(s)
        hz = g.gate_horizon(s, first_close=rows[0][2], now=NOW)
        if ok:
            ready.append(bot)
        books[bot] = {
            "n": s["n"], "days": round(s["days"], 1),
            "mean_pct": round(100 * s["mean_pct"], 3),
            "t": round(s["t"], 2), "win_pct": round(100 * s["win_rate"], 1),
            "max_dd_pct": (round(100 * s["max_dd_frac"], 1)
                           if s.get("max_dd_frac") is not None else None),
            "h1": round(s["h1"], 2), "h2": round(s["h2"], 2),
            "bars": bars, "bar_names": list(g.BAR_NAMES),
            "bars_passed": sum(bars.values()), "fails": fails,
            "ready": bool(ok), "horizon": hz}
        current[bot] = {"hz": hz, "era_days": s["days"], "n": s["n"],
                        "mean_pct": s["mean_pct"], "t": s["t"]}
    for bot, pcts in (floor_pcts or {}).items():
        rows = _pcts(pcts)
        s = g.stats(rows)
        hz = g.gate_horizon(s, first_close=rows[0][2], now=NOW)
        floor[bot] = {"n_alltime": s.get("n", 0),
                      "why_absent": "below --min-closes", "horizon": hz}
        current[bot] = {"hz": hz, "era_days": s.get("days"),
                        "n": s.get("n", 0), "mean_pct": s.get("mean_pct"),
                        "t": s.get("t")}
    for bot in zero_ledger:
        hz = {"verdict": "no_rate", "eta": None, "eta_days": None,
              "eta_kind": None, "eta_conf": None, "binding": None,
              "blockers": [], "rate_cpd": None, "n_req_t": None,
              "raw_days": None,
              "why": "no closes ever — undecidable until the book closes "
                     "trades (I17: keep-or-retire, not another tuning pass)"}
        floor[bot] = {"n_alltime": 0,
                      "why_absent": "no closed trades in the ledger",
                      "horizon": hz}
        current[bot] = {"hz": hz, "era_days": None, "roster_zero_ledger": True,
                        "n": 0, "mean_pct": None, "t": None}
    dock, seen = g.decision_docket(
        current, docket_prior or {}, (docket_now or NOW).isoformat())
    return {"updated": NOW.isoformat(), "ttl_sec": g.TTL_SEC,
            "bar": {"min_days": g.GOLIVE_MIN_DAYS,
                    "min_closes": g.GOLIVE_MIN_CLOSES,
                    "min_t": g.GOLIVE_MIN_T, "max_dd": g.GOLIVE_MAX_DD},
            "bar_names": list(g.BAR_NAMES), "books": books,
            "ready": sorted(ready), "below_floor": floor,
            "decision_docket": dock, "docket_seen": seen,
            "docket_days": g.DOCKET_DAYS, "docket_valid": bool(docket_valid)}


def _row(bot, max_open=4, age_s=30):
    """A `bot_pnl`-shaped row in the form `fetch_bot_pnl` really returns —
    `updated_at` as ISO, never a precomputed `age_sec` (the (tj) trap the
    judge's own census walked into).

    Stamped off the WALL CLOCK, which is also what this module's `NOW` is
    (`datetime.now(timezone.utc)` at import), so the two agree.

    [(va)] CORRECTED IN PLACE: this used to say `_fresh()` "reads `now_ts()`
    and ignores the `now` it is handed". That is no longer true — the gate now
    reads the clock it is HANDED, so that it can be driven at a fixed instant
    (the judge's in-module selftest drives a t0 ~12.2M seconds in the future,
    where a wall-clock read made every age negative and the bar unfalsifiable).
    `pair_census` normalises `now` via `_epoch`, so this fixture may pass its
    `NOW` datetime and production may pass a float, and both mean the same
    instant. A fixture whose verdicts depend on what time the suite runs is
    still worse than no fixture — that part stands, and wall-clock stamps
    against a wall-clock `NOW` are what keep it honest.

    [(uy)] `ttl_sec: 900` removed — the same (tj) miss this docstring warns
    about, in the line below it. `fetch_bot_pnl` emits no `ttl_sec` (zero
    occurrences in bot_pnl_store.py; the table has no such column), so the
    fixture drove `3 * row.ttl_sec` while production drove the `or 900`
    fallback, leaving the live bar unmutatable. The bar is now the named
    `experiment_judge.PAIR_ROW_STALE_S`."""
    return {"bot": bot,
            "updated_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=age_s)).isoformat(),
            "extra": {"max_open": max_open}}


def _close(bot, i, policy=None):
    """A ledger close row shaped the way `bot_pnl_store.fetch_paper_trades`
    BUILDS them — the judge's only ledger source.

    [(uy)] This said "shaped the way `_latest_policy_stamp` reads them", and
    that is the defect's own fingerprint: written to match the CONSUMER, it
    built `closed_at`/`pnl_pct` — the DB COLUMN names — while the fetch
    normalises those to `close_ts`/`profit_ratio` and emits neither. A fixture
    that agrees with the consumer instead of the publisher cannot detect the
    two disagreeing, which is exactly what `_close_rank` was doing."""
    r = {"bot": bot, "close_ts": (NOW - timedelta(hours=i)).isoformat(),
         "profit_ratio": 0.01, "extra": {}}
    if policy is not None:
        r["extra"]["policy"] = dict(policy)
    return r


def judge_payload(rows, bot_rows, phase="idle"):
    """`experiment_judge.pair_census()` — the judge's own builder."""
    return {"updated": NOW.isoformat(), "ttl_sec": ej.TTL_SEC,
            "phase": phase, "pairs": ej.pair_census(rows, bot_rows, NOW)}


def _funding_names_the_organ_can_generate():
    """Ask the incubator what funding candidates it can mint, so an EXHAUSTED
    lane can be produced by feeding those very names back as already-proposed.

    Publisher-driven on purpose: `proposal_capacity` reports
    `exhausted = bool(generatable) and not untried`, and hand-writing
    `{"exhausted": True}` would test my idea of the field rather than the
    organ's."""
    return si.proposal_capacity({"verdicts": [], "done": []},
                                {"proposed": []})["names"]


def incubator_payload(genotype, closes=60, net=-29.42, proposed=(),
                      drop_enactable=False):
    """Incubator fields decided by the organ's own pure functions.

    `proposed` is the lifetime ledger of already-minted funding candidate
    NAMES — pass `_funding_names_the_organ_can_generate()` to drive
    `proposal_capacity` to its real EXHAUSTED verdict.

    `drop_enactable` removes the frontier's `enactable` field entirely: the
    older-payload shape, where the honest answer is UNKNOWN rather than a
    confident "no"."""
    top = {"genotype": dict(genotype), "closes": closes, "net": net,
           "h1": net / 2, "h2": net / 2}
    _is, streak, _stable, conf, _why = si.assess_champion(
        top, default_net=0.0, tape_hours=999.0, prior_champ=None,
        prior_streak=0)
    cap = si.proposal_capacity({"verdicts": [], "done": []},
                               {"proposed": [{"name": n} for n in proposed]})
    frontier = dict(top, enactable=si.is_enactable(genotype))
    if drop_enactable:
        frontier.pop("enactable")
    return {"updated": NOW.isoformat(), "ttl_sec": si.TTL_SEC,
            "elite": [], "champion": dict(top, confidence=conf, streak=streak),
            "frontier": frontier,
            "proposal_capacity": cap}


# ---------------------------------------------------------------------------
# the three scenarios
# ---------------------------------------------------------------------------
#: FOUR books, and each one lands on a DIFFERENT grader verdict — verified in
#: `test_the_fixture_covers_every_verdict_the_card_reads` rather than assumed,
#: because a fixture where every book resolves the same way cannot distinguish
#: a working funnel from a constant.
#:   clean   -> passes all six bars   (ready: the AT THE BAR stage)
#:   ontrack -> on_track, with an eta (the MEASUREMENT line)
#:   loser   -> unreachable           (the DECISION docket)
#:   newborn -> zero-ledger           (below_floor + the docket's roster arm)
HEALTHY_BOOKS = {
    "book-clean-lshadow": [0.010, 0.014] * 20,
    "book-ontrack-lshadow": [0.02, -0.005] * 8,
    "book-loser-lshadow": [-0.02, 0.001] * 20,
}
HEALTHY_ZERO_LEDGER = ("book-newborn-lshadow",)
HEALTHY_ALLOC = {
    "book-clean-lshadow": [0.010, 0.014] * 20,      # tight + positive -> a claim
    "book-ontrack-lshadow": [0.02, -0.005] * 8,
    "book-loser-lshadow": [-0.02, 0.001] * 20,
    "book-newborn-lshadow": [],              # zero-close
}


def healthy_states(**over):
    """All four keys, fresh. `over` replaces or deletes (None) a key."""
    # avo: both arms publish, live stamped, shadow NOT -> policy_unstamped
    #      (a MEASUREMENT block: the stamp ships, the closes have not).
    # georgia: both stamped but the arms disagree on `stoploss`
    #      -> policy_mismatch (a WIRE block). The divergence field is chosen
    #      deliberately: `scan_order` carries a MEASURED-INERT waiver on this
    #      pair, so diverging there yields `idle`, not a mismatch — and a
    #      fixture keyed to a waivable field silently changes verdict the day
    #      someone lands a waiver, which is exactly what happened mid-build.
    # mum: live row missing entirely -> live_row_dark (a WIRE block).
    # farmer: stood_down, straight off the live RETIRED_LIVE_ARMS declaration
    #      (a DECISION block).
    pol = {"strategy": "S", "venue": "lighter", "stoploss": -0.1,
           "roi": {"0": 0.02}, "sides": "long", "scan_order": "list"}
    bot_rows = [_row("freqtrade-avo-maria-lighter"),
                _row("freqtrade-avo-maria-lshadow"),
                _row("freqtrade-georgia-lighter"),
                _row("freqtrade-georgia-lshadow"),
                _row("freqtrade-mum-lshadow")]
    rows = ([_close("freqtrade-avo-maria-lighter", i, pol) for i in range(6)]
            + [_close("freqtrade-avo-maria-lshadow", i) for i in range(6)]
            + [_close("freqtrade-georgia-lighter", i, pol) for i in range(6)]
            + [_close("freqtrade-georgia-lshadow", i,
                      dict(pol, stoploss=-0.2)) for i in range(6)])
    prior = {"book-loser-lshadow":
             {"reason": "unreachable",
              "since": (NOW - timedelta(days=19.9)).isoformat()},
             "book-newborn-lshadow":
             {"reason": "zero_ledger",
              "since": (NOW - timedelta(days=13.2)).isoformat()}}
    st = {"golive-readiness": golive_payload(HEALTHY_BOOKS,
                                             HEALTHY_ZERO_LEDGER,
                                             docket_prior=prior),
          "xp-judge": judge_payload(rows, bot_rows),
          "fleet-allocation": alloc_payload(HEALTHY_ALLOC,
                                            ["book-newborn-lshadow"]),
          "strategy-incubator": incubator_payload(
              {"MOMO_CHG": 5.0, "BRK_RANGE": 0.95, "TAKE_PROFIT": 0.04})}
    for k, v in over.items():
        k = k.replace("_", "-")
        if v is None:
            st.pop(k, None)
        else:
            st[k] = v
    return st


def render(states, monkeypatch):
    monkeypatch.setattr(dash, "fetch_states", lambda keys: dict(states))
    return dash.pipeline_card()


# ---------------------------------------------------------------------------
# 1. THE HEALTHY CASE — the card says something, and it says the right thing.
# ---------------------------------------------------------------------------
def test_the_fixture_covers_every_verdict_the_card_reads():
    """Guard the guard. If every fixture book landed on the same verdict, the
    funnel tests below would pass against a card that printed a constant — the
    vacuous-test shape this repo keeps paying for. Assert the spread FIRST."""
    p = healthy_states()["golive-readiness"]
    got = {b: str((v.get("horizon") or {}).get("verdict"))
           for b, v in list(p["books"].items()) + list(p["below_floor"].items())}
    assert got == {"book-clean-lshadow": "ready",
                   "book-ontrack-lshadow": "on_track",
                   "book-loser-lshadow": "unreachable",
                   "book-newborn-lshadow": "no_rate"}, got
    assert p["ready"] == ["book-clean-lshadow"], p["ready"]


def test_healthy_card_renders_the_funnel_from_the_publishers(monkeypatch):
    """Non-degenerate: the (hj) lesson is that a dead consumer returns an
    empty/None a value-free test calls 'fine'. Every funnel number below is
    asserted against what the PUBLISHERS actually computed."""
    st = healthy_states()
    out = render(st, monkeypatch)
    assert out, "healthy payloads rendered nothing"

    alloc, gl = st["fleet-allocation"], st["golive-readiness"]
    assert f'<b>{alloc["n_books"]}</b> <span class="muted">rows' in out
    ever = alloc["n_books"] - len(alloc["zero_close_books"])
    assert f'<b>{ever}</b> <span class="muted">ever closed' in out
    claims = sum(1 for v in alloc["books"].values() if (v.get("claim") or 0) > 0)
    assert claims >= 1, "fixture produced no I16 claim — it cannot test the stage"
    assert f'<b>{claims}</b> <span class="muted">measured claim' in out
    assert f'<b>{len(gl["ready"])}</b> <span class="muted">AT THE BAR' in out
    # and there IS something at the bar in this fixture, so a card that always
    # printed 0 would fail here
    assert len(gl["ready"]) >= 1


def test_the_card_leads_with_the_promotion_pipe_not_the_gate_bars(monkeypatch):
    """The editorial claim, made executable: the judge pairs are rendered
    ABOVE the measurement/decision lines. Leading with the gate bars buries
    the one class a session can clear."""
    out = render(healthy_states(), monkeypatch)
    assert out.index("promotion pipe") < out.index("measurement:")
    assert out.index("promotion pipe") < out.index("decision (Eamon)")


def test_every_judge_pair_is_named_with_its_blocker_and_wake_when(monkeypatch):
    """Each pair surfaces its own `wake_when` — the payload already carries it,
    and it is the sentence that says what would unblock the pair."""
    st = healthy_states()
    out = render(st, monkeypatch)
    for pid, pair in st["xp-judge"]["pairs"].items():
        assert pid in out, f"pair {pid} missing from the card"
        blk = pair.get("unjudgeable") or pair.get("stood_down") or {}
        wake = blk.get("wake_when")
        assert wake, f"fixture pair {pid} carries no wake_when to surface"
        # Assert the VISIBLE `wake:` line, not merely the string's presence.
        # A mutation that deleted the line survived the looser check, because
        # the same text also rides in a `title=` tooltip — and a remedy the
        # reader has to HOVER to find is not surfaced. Compare against the
        # ESCAPED form: the card html-escapes, and these strings carry
        # apostrophes ("both arms' closes").
        import html as _h
        assert f'wake: {_h.escape(wake)[:60]}' in out, (
            f"pair {pid}'s wake_when is not on a visible line")


def test_blockers_are_sorted_by_who_can_clear_them(monkeypatch):
    """WIRE first, then DECISION, then MEASUREMENT. The fixture carries all
    three classes on purpose — a single-class fixture cannot observe order,
    which is how a sort defect ships green."""
    st = healthy_states()
    pairs = st["xp-judge"]["pairs"]
    assert (pairs["georgia"]["unjudgeable"]["reason"] == "policy_mismatch"
            and pairs["mum"]["unjudgeable"]["reason"] == "live_row_dark"
            and pairs["avo"]["unjudgeable"]["reason"] == "policy_unstamped"
            and pairs["farmer"]["phase"] == "stood_down"), pairs
    out = render(st, monkeypatch)
    assert out.index("policy_mismatch") < out.index("stood_down")
    assert out.index("stood_down") < out.index("policy_unstamped")


def test_the_measurement_line_names_the_on_track_books_and_their_eta(
        monkeypatch):
    """BLOCKED ON A MEASUREMENT — no owner, the clock does it — needs the ETA,
    or it is indistinguishable from a book that is simply stuck."""
    st = healthy_states()
    out = render(st, monkeypatch)
    hz = st["golive-readiness"]["books"]["book-ontrack-lshadow"]["horizon"]
    assert hz["eta"], "fixture produced no eta — it cannot test the line"
    assert "book-ontrack-lshadow" in out
    assert hz["eta"] in out
    # the on-track stage counts that book, and it is not the ready one
    assert '<b>1</b> <span class="muted">on track' in out


def test_the_decision_docket_names_its_count_and_how_long_it_has_waited(
        monkeypatch):
    """BLOCKED ON A DECISION — owner Eamon — needs the age, or it reads as a
    to-do list rather than an overdue call (I17)."""
    st = healthy_states()
    dock = st["golive-readiness"]["decision_docket"]
    assert dock, "fixture produced an empty docket — it cannot test the line"
    out = render(st, monkeypatch)
    assert f'<b>{len(dock)}</b> book(s) asking keep-or-retire' in out
    worst = max(d["days_held"] for d in dock)
    assert f'longest {worst:.0f}d' in out


def test_a_docket_timestamp_is_rendered_in_sydney_local(monkeypatch):
    """CLAUDE.md's timezone rule: a real TIMESTAMP handed to Eamon is
    Sydney-local and labelled. Verified against the conversion rather than a
    substring — a bare 'Syd' would pass on any wrong hour."""
    st = healthy_states()
    dock = st["golive-readiness"]["decision_docket"]
    worst = max(dock, key=lambda d: d["days_held"])
    out = render(st, monkeypatch)
    from zoneinfo import ZoneInfo
    want = (datetime.fromisoformat(worst["since"])
            .astimezone(ZoneInfo("Australia/Sydney"))
            .strftime("%d-%b %H:%M Syd"))
    assert want in out, f"expected Sydney stamp {want!r}"
    # ...and the BARE UTC clock time is not what was handed over. Sydney is
    # UTC+10/+11 year-round, so the two never coincide — this arm goes red if
    # the conversion is dropped and the raw stamp printed instead.
    utc = datetime.fromisoformat(worst["since"]).strftime("%d-%b %H:%M")
    assert utc not in out, (
        f"a bare UTC time {utc!r} reached the card — CLAUDE.md's timezone "
        f"rule is that Eamon never gets one")


def test_a_missing_tzdata_still_never_yields_a_bare_utc_time(monkeypatch):
    """`tzdata` can be absent on a slim image. The fallback mirrors
    `fleet_watchdog_svc._now_op`'s measured one — fixed +10, LABELLED with a
    star — rather than dropping the stamp or, far worse, printing UTC and
    calling it Sydney."""
    import zoneinfo
    monkeypatch.setattr(zoneinfo, "ZoneInfo",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            zoneinfo.ZoneInfoNotFoundError("no tzdata")))
    got = dash._pipe_syd("2026-08-06T22:28:34+00:00")
    assert got == "07-Aug 08:28 Syd*", got
    assert dash._pipe_syd("not-a-timestamp") is None


def test_a_horizon_eta_is_shown_as_published_and_labelled_not_shifted():
    """The grader's `eta` is a bare CALENDAR DATE with no time of day, so a
    UTC->Sydney shift would invent a day boundary it never computed. Render it
    unchanged and SAY it is the grader's date; never silently relabel."""
    txt, note = dash._pipe_eta("2026-11-10")
    assert txt == "2026-11-10", "the published date must not be shifted"
    assert "UTC calendar date" in note, "an unlabelled date is a bare UTC time"
    assert dash._pipe_eta(None) == (None, "")


# ---------------------------------------------------------------------------
# 2. THE DARK CASE — the trap. A missing key must never read as a measurement.
# ---------------------------------------------------------------------------
def test_all_four_keys_dark_hides_the_card(monkeypatch):
    """Fail-silent, the dashboard's standing contract: nothing published at
    all means no card, never a card full of question marks."""
    assert render({}, monkeypatch) == ""


def test_a_dark_grader_renders_unknown_not_zero(monkeypatch):
    """THE LOAD-BEARING TEST, and the whole reason this file exists.

    `0 at the bar` is a real and routine measurement on this fleet, so a dark
    grader coerced to 0 is indistinguishable from a healthy one. Render the
    same card twice — once with a genuine empty `ready`, once with the key
    absent — and require the two to DIFFER."""
    live = healthy_states()
    live["golive-readiness"]["ready"] = []       # a REAL zero
    with_zero = render(live, monkeypatch)
    without = render(healthy_states(golive_readiness=None), monkeypatch)

    assert '<b>0</b> <span class="muted">AT THE BAR' in with_zero
    assert '<b>0</b> <span class="muted">AT THE BAR' not in without, (
        "a DARK grader rendered 0 at the bar — byte-identical to the true "
        "measurement, which is the exact defect this card must not ship")
    assert '<b style="color:#d1242f" title="UNKNOWN' in without
    assert "dark: golive-readiness" in without
    assert with_zero != without


def test_a_dark_allocation_organ_renders_no_funnel_numbers(monkeypatch):
    """Same trap on the other publisher: `0 rows` / `0 measured claim` would
    read as 'the fleet has no evidence', a finding nobody measured."""
    out = render(healthy_states(fleet_allocation=None), monkeypatch)
    assert out, "the card must still render — a partial dark is when unknowns matter"
    for stage in ("rows", "ever closed", "measured claim"):
        assert f'<b>0</b> <span class="muted">{stage}' not in out
    assert "dark: fleet-allocation" in out


def test_a_dark_judge_says_the_pipe_is_unknown_not_clean(monkeypatch):
    """An empty promotion pipe reads as 'nothing is blocked'. A dark judge
    must say UNKNOWN instead — the absence of blockers is not good news.

    The MESSAGE is asserted, not just the word UNKNOWN: 'the judge is dark'
    and 'the judge published no pairs' are different findings with different
    fixes (chase the organ vs deploy the census), and a mutation collapsing
    the two survived a laxer version of this test."""
    out = render(healthy_states(xp_judge=None), monkeypatch)
    assert "promotion pipe UNKNOWN — xp-judge dark or stale" in out
    assert "no pairs published" not in out
    assert "dark: xp-judge" in out


def test_a_judge_payload_with_no_pairs_map_says_so_distinctly(monkeypatch):
    """The other half: a FRESH judge on an older payload version, with no
    `pairs` map at all. Also UNKNOWN, and it must name its own reason."""
    st = healthy_states()
    st["xp-judge"].pop("pairs")
    out = render(st, monkeypatch)
    assert "promotion pipe UNKNOWN — no pairs published" in out
    assert "xp-judge dark or stale" not in out


def test_a_dark_incubator_says_unknown_not_exhausted(monkeypatch):
    """'funding lane EXHAUSTED' is a real published verdict; a dark organ must
    not borrow it."""
    out = render(healthy_states(strategy_incubator=None), monkeypatch)
    assert "strategy-incubator dark or stale" in out
    assert "funding lane EXHAUSTED" not in out


def test_a_stale_payload_is_treated_as_dark_and_said_so(monkeypatch):
    """I1, liveness before semantics: a frozen payload and a live one are
    byte-identical in CONTENT — only the timestamp separates them. A grader
    past grace x ttl supplies no numbers and the header names it."""
    st = healthy_states()
    old = NOW - timedelta(seconds=g.TTL_SEC * 10)
    st["golive-readiness"]["updated"] = old.isoformat()
    out = render(st, monkeypatch)
    assert "stale: golive-readiness" in out
    assert '<b>0</b> <span class="muted">AT THE BAR' not in out
    assert '<b style="color:#d1242f" title="UNKNOWN' in out


def test_an_absent_zero_close_list_is_unknown_not_the_full_roster(monkeypatch):
    """An older allocation payload has no `zero_close_books`. 'ever closed'
    then has no honest value — and must NOT silently equal `n_books`, which
    would claim every book has traded."""
    st = healthy_states()
    n = st["fleet-allocation"]["n_books"]
    st["fleet-allocation"].pop("zero_close_books")
    out = render(st, monkeypatch)
    assert f'<b>{n}</b> <span class="muted">ever closed' not in out
    assert '<span class="muted">ever closed' in out    # the stage still shows


def test_books_without_a_claim_field_are_unknown_not_zero_claims(monkeypatch):
    """An allocation payload predating `claim` has books but no bounds. '0
    measured claim' would then assert 'not one book in the fleet has evidence'
    — a finding nobody computed, on the organ whose whole job is that number
    (I16). Absent field ⇒ unknown; a real zero still prints 0."""
    st = healthy_states()
    for v in st["fleet-allocation"]["books"].values():
        v.pop("claim", None)
    out = render(st, monkeypatch)
    assert '<b>0</b> <span class="muted">measured claim' not in out
    assert '<span class="muted">measured claim' in out    # the stage survives

    # ...and the SAME card with every claim present but zero must print 0 —
    # otherwise this test would also pass on a card that never counts.
    st2 = healthy_states()
    for v in st2["fleet-allocation"]["books"].values():
        v["claim"] = 0.0
    assert ('<b>0</b> <span class="muted">measured claim'
            in render(st2, monkeypatch))


def test_a_below_floor_book_on_track_is_counted(monkeypatch):
    """The (kv) merge: a book under the grader's publish floor still gets a
    horizon from its own sample, and lives in `below_floor`, never in `books`.
    Counting only `books` undercounts exactly the thin books the horizon
    exists to surface — silently, because the total stays plausible."""
    st = healthy_states()
    st["golive-readiness"] = golive_payload(
        HEALTHY_BOOKS, HEALTHY_ZERO_LEDGER,
        floor_pcts={"book-thin-lshadow": [0.02, -0.005] * 8})
    bf = st["golive-readiness"]["below_floor"]["book-thin-lshadow"]
    assert bf["horizon"]["verdict"] == "on_track", bf["horizon"]
    assert "book-thin-lshadow" not in st["golive-readiness"]["books"]
    out = render(st, monkeypatch)
    # two on-track books now: the graded one and the below-floor one
    assert '<b>2</b> <span class="muted">on track' in out
    assert "book-thin-lshadow" in out
    assert bf["horizon"]["eta"] in out


def test_an_absent_docket_is_unknown_not_an_empty_docket(monkeypatch):
    """'none open' is a real state. A payload that never published a docket
    must not claim it."""
    st = healthy_states()
    st["golive-readiness"].pop("decision_docket")
    out = render(st, monkeypatch)
    assert "no docket published" in out
    assert "none open" not in out


def test_an_unmapped_pair_reason_renders_unknown_not_a_class(monkeypatch):
    """A NEW `unjudgeable.reason` from the judge must not be absorbed into
    whichever class sits nearest in the table — I8: unknown degrades to
    honest, never to a guess."""
    st = healthy_states()
    st["xp-judge"]["pairs"]["mum"]["unjudgeable"] = {
        "reason": "a_reason_invented_after_this_card",
        "detail": "d", "wake_when": "w"}
    out = render(st, monkeypatch)
    assert "? unknown" in out
    assert "a_reason_invented_after_this_card" in out


def test_an_unverified_docket_clock_reads_as_a_floor_and_a_verified_one_does_not(
        monkeypatch):
    """The docket AGES are the whole point of the decision line — 'longest 20d'
    is what turns a to-do list into an overdue call (I17). The grader publishes
    `docket_valid = bool(_seen_ok)`, False when it could not read its own prior
    docket-seen map: every clock then reads as first-seen today, so every age
    is a FLOOR, not a measurement.

    BOTH ARMS ARE REQUIRED, and that is what a mutation round proved. Inverting
    the caveat's condition survived the suite: it silently DROPPED the warning
    on the payload that needs it, while shouting it on healthy payloads. A
    one-armed test cannot see that — an age you cannot trust, rendered
    identically to one you can, is the (hf)/I1 shape at the reporting layer."""
    st = healthy_states()
    assert st["golive-readiness"]["docket_valid"] is True
    healthy = render(st, monkeypatch)
    assert "clocks unverified" not in healthy, (
        "a VERIFIED docket must not be caveated — a warning that fires on the "
        "healthy case is one the reader learns to ignore")

    st2 = healthy_states(golive_readiness=golive_payload(
        HEALTHY_BOOKS, HEALTHY_ZERO_LEDGER,
        docket_prior={"book-loser-lshadow":
                      {"reason": "unreachable",
                       "since": (NOW - timedelta(days=19.9)).isoformat()}},
        docket_valid=False))
    assert st2["golive-readiness"]["decision_docket"], "fixture lost its docket"
    unverified = render(st2, monkeypatch)
    assert "clocks unverified" in unverified, (
        "the grader said it could not verify its own docket clocks and the "
        "card reported the ages as if measured")
    assert unverified != healthy


def test_an_unknown_frontier_enactable_is_never_a_confident_no(monkeypatch):
    """`frontier enactable no` is a real verdict from `si.is_enactable` — the
    organ's own fail-CLOSED answer to 'could this genotype ever ship?'. An
    OLDER payload that carries no `enactable` field at all must read UNKNOWN
    instead of borrowing that verdict, the same rule the funnel stages follow.

    Three arms, because two of them are the positive controls that stop this
    passing against a card printing a constant: a real True, a real False the
    organ decided, and the absent field."""
    yes = render(healthy_states(), monkeypatch)
    assert "frontier enactable yes" in yes

    bad_genotype = {"NOT_A_GENE_ANY_REGISTRY_KNOWS": 1.0}
    assert si.is_enactable(bad_genotype) is False, (
        "fixture no longer exercises the False arm — the organ now considers "
        "this genotype enactable")
    no = render(healthy_states(
        strategy_incubator=incubator_payload(bad_genotype)), monkeypatch)
    assert "frontier enactable no" in no

    unknown = render(healthy_states(
        strategy_incubator=incubator_payload(
            {"MOMO_CHG": 5.0}, drop_enactable=True)), monkeypatch)
    assert "frontier enactable unknown" in unknown
    assert "frontier enactable no" not in unknown, (
        "an ABSENT enactable field rendered as a measured 'no' — nobody "
        "computed that, and it reads as 'this line of work is dead'")


def test_the_funding_lane_verdict_is_the_organs_and_not_the_cards(monkeypatch):
    """`funding lane EXHAUSTED` says the reproduction organ can mint no new
    funding experiment — the (jn)-class sterility that ran silent for weeks.
    It must track `proposal_capacity`'s own `exhausted` field in BOTH
    directions, and an older payload without the field reads unknown.

    A mutation inverting that test survived the suite: it hid a REAL exhausted
    lane and cried EXHAUSTED on a healthy one. The dark-organ test could not
    see it, because a dark organ never reaches this branch at all."""
    cap = healthy_states()["strategy-incubator"]["proposal_capacity"]
    assert cap["exhausted"] is False and cap["untried"] > 0, cap
    live = render(healthy_states(), monkeypatch)
    assert "funding lane EXHAUSTED" not in live
    assert f'{cap["untried"]} untried' in live

    # ...and the organ's REAL exhausted verdict: hand its own generatable
    # names back as already-proposed, which is exactly how it goes sterile.
    spent = incubator_payload({"MOMO_CHG": 5.0},
                              proposed=_funding_names_the_organ_can_generate())
    assert spent["proposal_capacity"]["exhausted"] is True, (
        spent["proposal_capacity"])
    out = render(healthy_states(strategy_incubator=spent), monkeypatch)
    assert "funding lane EXHAUSTED" in out, (
        "the organ reported it can mint nothing new and the card did not say so")

    # an older payload with no `exhausted`/`untried` at all is UNKNOWN
    older = incubator_payload({"MOMO_CHG": 5.0})
    older["proposal_capacity"] = {"generatable": 4, "names": []}
    blind = render(healthy_states(strategy_incubator=older), monkeypatch)
    assert "funding lane unknown" in blind
    assert "funding lane EXHAUSTED" not in blind


def test_an_unmeasured_champion_or_elite_is_unknown_not_a_plausible_number(
        monkeypatch):
    """The SAME honesty rule as the funnel, on the breeding line — and two
    mutations survived here because only the funnel had been tested for it.

    `champion $0` and `elite 1` are both perfectly plausible readings. The
    first says the best genotype the organ has bred is exactly break-even (the
    live value is −$29.42, so $0 reads as a real improvement); the second says
    one elite genotype is queued, off a field that is not even a list. Neither
    number was computed by anybody."""
    healthy = render(healthy_states(), monkeypatch)
    # positive controls: a real negative net and a real EMPTY elite list both
    # print their values, so "always unknown" cannot pass this test either.
    assert "champion $-29.42" in healthy
    assert "elite 0" in healthy

    inc = incubator_payload({"MOMO_CHG": 5.0})
    inc["champion"].pop("net")          # an older payload / a failed score
    inc["elite"] = "x"                  # not a list — junk or an older shape
    out = render(healthy_states(strategy_incubator=inc), monkeypatch)
    assert "champion unknown" in out
    assert "champion $0" not in out, (
        "an unscored champion rendered as a measured break-even")
    assert "elite unknown" in out
    assert "elite 1" not in out, (
        "a non-list `elite` was counted — len('x') is not a genotype count")


def test_an_empty_measurement_line_says_no_book_is_on_track(monkeypatch):
    """When NOTHING is on track, the line must say so in words.

    Dropping the sentence leaves `⏳ measurement:` followed by nothing, and a
    blank reads as 'nothing to report here' — while the actual finding is the
    most serious one this card can carry: not a single book is projected to
    reach the bar at its measured trajectory. Same shape as a dark stage
    rendering 0."""
    st = healthy_states(golive_readiness=golive_payload(
        {b: p for b, p in HEALTHY_BOOKS.items() if b != "book-ontrack-lshadow"},
        HEALTHY_ZERO_LEDGER))
    gl = st["golive-readiness"]
    verdicts = {b: str((v.get("horizon") or {}).get("verdict"))
                for b, v in list(gl["books"].items())
                + list(gl["below_floor"].items())}
    assert "on_track" not in verdicts.values(), verdicts
    out = render(st, monkeypatch)
    assert "none — no book is on track" in out
    # ...and the healthy fixture, which DOES have one, names it instead —
    # otherwise this would pass against a card that always printed the phrase.
    healthy = render(healthy_states(), monkeypatch)
    assert "none — no book is on track" not in healthy
    assert "book-ontrack-lshadow" in healthy


# ---------------------------------------------------------------------------
# 3. THE PARTIAL CASE — some keys fresh, some absent, some missing a field.
# ---------------------------------------------------------------------------
def test_partial_payloads_render_what_is_known_and_flag_what_is_not(
        monkeypatch):
    """The realistic day: one organ deploys ahead of another. The card renders
    the fresh half and marks the dark half, rather than hiding (which loses
    the working data) or guessing (which is the trap above)."""
    st = healthy_states(fleet_allocation=None, strategy_incubator=None)
    out = render(st, monkeypatch)
    assert out
    gl = st["golive-readiness"]
    assert f'<b>{len(gl["ready"])}</b> <span class="muted">AT THE BAR' in out
    assert "policy_mismatch" in out                       # judge half intact
    assert "dark: fleet-allocation" in out and "strategy-incubator" in out


def test_only_one_key_present_still_renders(monkeypatch):
    """One live key is enough to be worth showing — and every stage it cannot
    supply reads unknown."""
    out = render({"xp-judge": healthy_states()["xp-judge"]}, monkeypatch)
    assert out
    assert '<b style="color:#d1242f" title="UNKNOWN' in out
    assert '<b>0</b>' not in out


def test_junk_payloads_do_not_take_the_page_down(monkeypatch):
    """Fail-silent under garbage, like every other card: a broken card must
    never break the dashboard around it."""
    for junk in ({"golive-readiness": {"books": "not-a-dict", "ready": 7}},
                 {"xp-judge": {"pairs": [1, 2, 3]}},
                 {"fleet-allocation": {"n_books": "many", "books": None}},
                 {"strategy-incubator": {"champion": 5, "elite": "x"}}):
        assert isinstance(render(junk, monkeypatch), str)


# ---------------------------------------------------------------------------
# 4. the card is registered, and it does not disturb its neighbours
# ---------------------------------------------------------------------------
def test_the_card_is_wired_into_the_render_chain():
    """A card nobody calls is the (gk) 'rule nobody runs' shape. Asserted by
    AST — a substring scan would pass on this docstring's own mention."""
    import ast
    src = (_ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "render")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "pipeline_card" in called, (
        "pipeline_card() is defined but never called from render()")
    # and every card it sits beside is still called from the same place
    for neighbour in ("golive_card", "radar_card", "incubator_card",
                      "brain_card_html"):
        assert neighbour in called, f"{neighbour} lost its call site"


def test_it_reads_only_keys_the_dashboard_already_fetches(monkeypatch):
    """No new data source and therefore no new deploy surface. Captured from
    the real call rather than asserted from the docstring."""
    seen = []

    def _spy(keys):
        seen.append(list(keys))
        return {}

    monkeypatch.setattr(dash, "fetch_states", _spy)
    dash.pipeline_card()
    assert seen and set(seen[0]) == {"golive-readiness", "xp-judge",
                                     "fleet-allocation", "strategy-incubator"}
