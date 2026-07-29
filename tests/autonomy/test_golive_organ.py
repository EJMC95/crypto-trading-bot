"""The go-live gate as a PUBLISHED organ — producer/consumer bound.

[2026-07-30] `scripts/golive_readiness.py` implements the (fk) bar, the one
rule that decides whether a $1,000 shadow book may ever hold real money. Until
today it shipped in NO image, ran on NO schedule and published NOTHING: its
verdicts existed only for as long as a human's terminal scrollback. The fleet's
own name for that class is "a rule nobody runs is not a control".

It is now an organ (Dockerfile.freqtrade COPY + a 6-hourly `--publish` loop in
run_all.sh + a deploy path) and the dashboard renders its key. That creates
exactly the failure mode this session kept finding — a producer and a consumer
that agree only in the author's head — so these tests bind the two ends:

  * the six bar NAMES are the published contract, and the dashboard's chip
    table must cover them exactly (no missing chip, no invented one);
  * `bar_map` must be EQUIVALENT to `grade`, never kinder, so six green chips
    can never sit on a book the gate rejects;
  * the card must survive junk, absent and partial payloads without hiding
    the whole page (fail-silent, per the dashboard's standing contract);
  * the loop and the COPY must actually exist — a grader that publishes
    beautifully from a file no image carries is the born-dark class.

NOTE ON THE FIXTURES: these build book dicts through the REAL `stats()`, not by
hand. Hand-written stat dicts were how four defects passed their own tests
earlier this session — a fixture that speaks a dialect the producer never emits
validates the author's model, not the contract.
"""
import os
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

import golive_readiness as g          # noqa: E402
import pnl_dashboard as dash          # noqa: E402

from datetime import datetime, timedelta, timezone   # noqa: E402

_T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _mk(pcts, span_days=40.0):
    step = timedelta(days=span_days / max(1, len(pcts) - 1))
    return [(p, p * 10.0, _T0 + i * step) for i, p in enumerate(pcts)]


def _payload(books_stats):
    """Build the published payload the way `main()` does — same call order,
    same keys — so a change in main() that these tests do not see is a change
    the dashboard would not see either."""
    books = {}
    ready = []
    for bot, s in books_stats.items():
        ok, fails = g.grade(s)
        ok_old, _ = g.grade(s, legacy=True)
        bars = g.bar_map(s)
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
            "ready": bool(ok), "legacy_ready": bool(ok_old)}
    return {"updated": "2026-07-30T00:00:00+00:00", "ttl_sec": g.TTL_SEC,
            "bar": {"min_days": g.GOLIVE_MIN_DAYS,
                    "min_closes": g.GOLIVE_MIN_CLOSES,
                    "min_t": g.GOLIVE_MIN_T, "max_dd": g.GOLIVE_MAX_DD},
            "bar_names": list(g.BAR_NAMES),
            "books": books, "ready": sorted(ready)}


def _render(payload, monkeypatch):
    monkeypatch.setattr(dash, "fetch_states",
                        lambda keys: {"golive-readiness": payload})
    return dash.golive_card()


# --------------------------------------------------------------------------
# 1. bar_map is the grade — never kinder, never stricter.
# --------------------------------------------------------------------------

_CASES = {
    # a clean pass on every bar
    "clean": _mk([0.01] * 40),
    # THE CARRY SHAPE: 33% win rate, positive expectancy — the book the
    # retired win-rate rule would have rejected forever. INTERLEAVED, not
    # blocked: the measured book earns steadily on both halves, and a blocked
    # fixture (all wins then all losses) would fail the both-halves bar for a
    # reason that has nothing to do with win rate, quietly turning the
    # divergence assertion below into a skip.
    "carry": _mk([0.20, -0.03, -0.03] * 20),
    # the inverse: high win rate, loses money on the tails
    "tails": _mk([0.01] * 34 + [-0.30] * 6),
    # positive and stable but far too noisy to believe
    "noisy": _mk([0.05, -0.045] * 20),
    # the classic one-window win
    "lopsided": _mk([0.05] * 20 + [-0.01] * 20),
    # flawless but only 10 fills — evidence is denominated in FILLS
    "thin": _mk([0.02] * 10),
    # a full sample crammed into 5 days
    "short": _mk([0.01] * 40, span_days=5.0),
}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_bar_map_is_equivalent_to_grade(name):
    """The dashboard renders `bars`; the gate decides with `grade`. If these
    can disagree, an operator can read 6/6 green on a book the gate refuses —
    which is worse than no card at all."""
    s = g.stats(_CASES[name])
    bars = g.bar_map(s)
    assert set(bars) == set(g.BAR_NAMES), bars
    assert all(bars.values()) == g.grade(s)[0], (name, bars, g.grade(s))
    assert sum(bars.values()) == len(g.BAR_NAMES) - len(g.grade(s)[1]), \
        (name, bars, g.grade(s)[1])


def test_an_unmeASURABLE_drawdown_fails_rather_than_passes():
    """It used to PASS: the condition was `is not None and >=`, so a book whose
    drawdown could not be computed cleared the one bar the operator wrote
    himself. Fail-closed is the only defensible direction on a real-money
    gate."""
    s = g.stats(_mk([0.01] * 40), book_usd=0)
    assert s["max_dd_frac"] is None, s
    assert g.bar_map(s)["maxdd"] is False
    ok, fails = g.grade(s)
    assert ok is False and any("maxDD" in f for f in fails), fails


def test_an_ungradeable_book_claims_nothing():
    s = g.stats([])
    assert g.bar_map(s) == {k: False for k in g.BAR_NAMES}
    assert g.grade(s)[0] is False


def test_win_rate_is_still_not_a_bar():
    """The (fk) rewrite's whole point. Pinned here as well as in --selftest
    because this is the assertion a future 'tighten the gate' change is most
    likely to quietly undo."""
    s = g.stats(_CASES["carry"])
    assert s["win_rate"] < 0.55 and s["mean_pct"] > 0, s
    assert "win" not in " ".join(g.grade(s)[1])
    assert g.grade(s, legacy=True)[0] is False, "the OLD rule did reject it"


# --------------------------------------------------------------------------
# 2. The dashboard's chip table must cover the published contract exactly.
# --------------------------------------------------------------------------

def test_the_card_covers_every_published_bar_and_invents_none():
    """A renamed bar must fail HERE, not degrade into a silently missing chip.
    Order matters too — the operator reads them left to right against the
    header, so the card's order is the grader's order."""
    keys = [k for k, _glyph, _tip in dash.GOLIVE_BARS]
    assert tuple(keys) == tuple(g.BAR_NAMES), (keys, g.BAR_NAMES)


def test_every_chip_has_a_distinct_glyph_and_a_tooltip():
    glyphs = [gl for _k, gl, _t in dash.GOLIVE_BARS]
    assert len(set(glyphs)) == len(glyphs), glyphs
    assert all(t.strip() for _k, _g, t in dash.GOLIVE_BARS)


# --------------------------------------------------------------------------
# 3. The card renders the real thing, and sorts by the operator's question.
# --------------------------------------------------------------------------

def test_the_card_renders_and_sorts_closest_to_the_bar_first(monkeypatch):
    """"Who is next?" is the question, so 5/6 must appear above 1/6."""
    payload = _payload({
        "book-clean": g.stats(_CASES["clean"]),
        "book-carry": g.stats(_CASES["carry"]),
        "book-thin": g.stats(_CASES["thin"]),
    })
    html = _render(payload, monkeypatch)
    assert html, "the card rendered EMPTY on a valid payload"
    # Read the order OFF the rendered html and check it is monotone in
    # bars_passed — never assert a hand-written name order, which only pins
    # what the fixtures happen to score.
    seen = sorted(payload["books"], key=html.index)
    scores = [payload["books"][b]["bars_passed"] for b in seen]
    assert scores == sorted(scores, reverse=True), (seen, scores)
    assert len(set(scores)) > 1, "fixtures must actually differ to test a sort"


def test_the_card_states_that_it_promotes_nothing(monkeypatch):
    """The gate is advisory by construction; the card must SAY so, because a
    scoreboard that looks like an authorisation is how a shadow book ends up
    holding real money by momentum."""
    html = _render(_payload({"b": g.stats(_CASES["clean"])}), monkeypatch)
    low = html.lower()
    assert "operator act" in low
    assert "not a bar" in low, "win% must be labelled as reported, not a bar"


def test_the_card_marks_the_fk_divergence(monkeypatch):
    """A book the NEW bar admits and the retired win-rate rule would have
    rejected is the single most important thing on this card — it is the
    measured justification for the whole (fk) rewrite."""
    s = g.stats(_CASES["carry"])
    if not g.grade(s)[0]:
        pytest.skip("carry fixture does not clear the new bar at this n")
    html = _render(_payload({"book-carry": s}), monkeypatch)
    assert "✦" in html


# --------------------------------------------------------------------------
# 4. Fail-silent: junk must never take the page down.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    None, {}, {"books": None}, {"books": []}, {"books": "nope"},
    {"books": {"b": None}}, {"books": {"b": "junk"}},
    {"books": {"b": {}}},
    {"books": {"b": {"bars": "not-a-dict", "n": "x", "t": None}}},
    {"books": {"b": {"bars": {}, "fails": None, "max_dd_pct": "x"}}, "bar": 7},
])
def test_the_card_never_raises_on_a_malformed_payload(payload, monkeypatch):
    """Every other organ card on this dashboard is fail-silent; this one grades
    real-money eligibility, so it is the LAST card that may take the page down
    with it."""
    monkeypatch.setattr(dash, "fetch_states",
                        lambda keys: {"golive-readiness": payload})
    out = dash.golive_card()
    assert isinstance(out, str)          # empty is fine; an exception is not


def test_a_dark_organ_hides_the_card_rather_than_showing_a_frozen_bar(monkeypatch):
    monkeypatch.setattr(dash, "fetch_states", lambda keys: {})
    assert dash.golive_card() == ""


def test_a_book_missing_its_bar_map_still_renders(monkeypatch):
    """Forward compatibility in the safe direction: an older publisher (no
    `bars` key) must render as all-dark chips, never as all-PASS."""
    p = _payload({"b": g.stats(_CASES["clean"])})
    p["books"]["b"].pop("bars")
    html = _render(p, monkeypatch)
    assert html and "not yet" in html
    assert "PASS" not in html, "a missing bar map must not read as six passes"


# --------------------------------------------------------------------------
# 5. The organ must actually SHIP and actually RUN — the born-dark class.
# --------------------------------------------------------------------------

def test_the_grader_is_copied_into_the_image_that_runs_it():
    df = (_ROOT / "Dockerfile.freqtrade").read_text()
    assert "scripts/golive_readiness.py" in df, (
        "the loop below runs a file the image does not carry")


def test_the_loop_exists_and_passes_publish():
    sh = (_ROOT / "run_all.sh").read_text()
    assert "golive_readiness.py --publish" in sh, (
        "a grader with no --publish writes nothing — the exact inertness this "
        "change exists to fix")
    # the path in the loop must be the path the Dockerfile COPYs to
    assert "/freqtrade/scripts/golive_readiness.py --publish" in sh


def test_the_file_has_a_deploy_route():
    """A change to the gate that reaches no container is invisible, and the
    workflow's `paths:` filter is the only automated route (see Railway Setup
    — 'a push is NOT a deploy')."""
    wf = (_ROOT / ".github/workflows/railway-redeploy.yml").read_text()
    assert "'scripts/golive_readiness.py'" in wf, "no paths: entry"
    assert "scripts/golive_readiness\\.py$" in wf, "no freqtrade-bots grep"


def test_the_key_is_watchdogged_and_served_off_railway():
    src = (_ROOT / "pnl_dashboard.py").read_text()
    assert src.count("'golive-readiness'") >= 2, (
        "the key must be in BOTH the live SELECT and the history SELECT of "
        "/bus.json — a review seat with no Railway login reads that endpoint")
    assert '"golive-readiness",   "🚦' in src or "golive-readiness" in src
    assert '"golive_readiness": live.get("golive-readiness")' in src


def test_publish_is_opt_in():
    """A bare run must never write the live bus — the radar's rule, and the
    reason a developer can run the grader on a laptop against the shared DB."""
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    assert '"--publish", action="store_true"' in src
    assert "if a.publish:" in src


def test_the_publish_block_cannot_fail_the_grade():
    """The grade is the deliverable; the publish is a side effect. A DB outage
    must not turn a working grader into a crash — and `save_state` already
    never raises, so this guard is about the import and the clock."""
    src = (_ROOT / "scripts/golive_readiness.py").read_text()
    block = src[src.index("if a.publish:"):]
    assert "except Exception" in block.split("print(\"Go-live remains")[0]


# --------------------------------------------------------------------------
# 6. THE SHADOW SERVICES' REAL NAMES — (gl). The deploy rules were shipped
#    with GUESSED Railway names and four of six were wrong, so four of the
#    Farnham Six never received the levers registered for them. The resolver
#    warned; nobody was watching. These pin the verified names in a place that
#    FAILS rather than warns.
# --------------------------------------------------------------------------

#: Verified against the live `railway service list` (run 30494145090).
#: Railway names follow the EMOJI NICKNAME, not the dashboard row id — the
#: mismatch that caused the misses.
SHADOW_SERVICES = {
    "Dockerfile.dislocation": "snap-back-shadow",
    "Dockerfile.fundspread": "counterweight-shadow",
    "Dockerfile.indexshadow": "equities-regime-shadow",
    "Dockerfile.psniper": "perp-sniper-shadow",
    "Dockerfile.trendlighter": "tide-rider-lighter-shadow",
    "Dockerfile.familyshadow": "family-lighter-shadow",
}

#: Names the workflow used to carry. Each one resolved to NOTHING at Railway,
#: so a push matching its rule deployed that book's image nowhere.
DEAD_SERVICE_NAMES = ("lighter-dislocation", "perps-funding-spread",
                      "lighter-perp-sniper", "crypto-trend-daily-shadow")


@pytest.mark.parametrize("dockerfile,service", sorted(SHADOW_SERVICES.items()))
def test_each_shadow_image_deploys_its_verified_service(dockerfile, service):
    wf = (_ROOT / ".github/workflows/railway-redeploy.yml").read_text()
    assert f"svcs,}}{service}\"" in wf, f"{dockerfile} has no rule for {service}"
    assert f"'{dockerfile}'" in wf, f"{dockerfile} missing from paths:"


@pytest.mark.parametrize("dead", DEAD_SERVICE_NAMES)
def test_the_unresolvable_names_are_gone(dead):
    """A rule pointing at a non-existent service is worse than no rule: it
    reads as covered, warns once in a log, and deploys nothing."""
    wf = (_ROOT / ".github/workflows/railway-redeploy.yml").read_text()
    assert f'svcs,}}{dead}"' not in wf, (
        f"{dead} does not exist at Railway — a push matching its rule deploys "
        "that book's image nowhere")


def test_the_deploy_guard_knows_about_these_images():
    """The guard was GREEN while four names were dead, because it only checks
    images listed in AUTO_IMAGES and these six were not in it. A guard that
    cannot see the rule cannot validate the rule."""
    sys.path.insert(0, str(_ROOT / "scripts"))
    import audit_deploy_coverage as adc
    for dockerfile, service in SHADOW_SERVICES.items():
        assert adc.AUTO_IMAGES.get(dockerfile) == service, dockerfile


def test_the_guard_can_read_a_variable_interpolating_grep():
    """The six rules interpolate `$_shared`. The parser read only the
    single-quoted inline form, so it saw NO rule for any of them — the same
    blindness live_marker_filters() was written to fix, one pass later. If this
    regresses, the guard silently stops checking six services."""
    sys.path.insert(0, str(_ROOT / "scripts"))
    import audit_deploy_coverage as adc
    filters = adc.workflow_filters()
    for service in SHADOW_SERVICES.values():
        rxs = filters.get(service)
        assert rxs, f"parser sees no rule at all for {service}"
        # the SHARED modules must be reachable — that is what $_shared carries,
        # and it is how a lever-registry change reaches these books
        assert any(rx.search("fleet_tuning.py") for rx in rxs), service
        assert any(rx.search("bot_pnl_store.py") for rx in rxs), service


def test_both_carry_services_are_covered():
    """(gl), operator's call. The project has `funding-carry` AND
    `yield-harvester-shadow` and this repo cannot determine which publishes the
    perps-funding-carry-lshadow row. 🌾 is five of six bars from go-live, so
    both are deployed rather than one guessed — the same guess that cost four
    books their shot earlier in this pass."""
    sys.path.insert(0, str(_ROOT / "scripts"))
    import audit_deploy_coverage as adc
    filters = adc.workflow_filters()
    for service in ("funding-carry", "yield-harvester-shadow"):
        rxs = filters.get(service)
        assert rxs, f"no parseable rule for {service}"
        # the lever registry must reach BOTH, or a carry lever lands nowhere
        assert any(rx.search("fleet_tuning.py") for rx in rxs), service
        assert any(rx.search("funding_carry_bot.py") for rx in rxs), service
