"""GATE HORIZON — the fleet's first sense of its own FUTURE, producer/consumer bound.

[2026-08-06 (ks)] `gate_horizon` projects WHEN each currently-failing go-live
bar flips at a book's measured in-era trajectory, published as an additive
per-book `horizon` sub-dict beside `era`/`alltime`/`integrity`. The operator's
calendar was hand-typed prose (OPERATOR_QUEUE item 5) and had already rotted —
the Farmer's "~16-Aug" matches its pre-(jf) era while the stamped era arms
~22-Aug — and the (kp) entry hand-computed "needs ~178 closes against 62" in
prose. Both are the closed form n_req = n * (T/t)^2 over fields the grader
already publishes.

These tests bind the three ends the selftest cannot: the RATE DENOMINATOR
decision (era age, never close span — a span cannot see a stall, I1), the
payload WIRING in main() (an unpublished projection is a note), and the
DASHBOARD consumer (chip renders from a publisher-built payload, never crashes
on junk, and renders NOTHING on a pre-horizon payload).

Fixtures build stats through the REAL `stats()`, per the standing (hj) rule.
"""
import ast
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
_NOW = _T0 + timedelta(days=40)


def _mk(pcts, span_days=40.0, t0=_T0):
    step = timedelta(days=span_days / max(1, len(pcts) - 1))
    return [(p, p * 10.0, t0 + i * step) for i, p in enumerate(pcts)]


# an on-track shape: mean>0, 0<t<2, every other bar green (t is sole binder)
_ONTRACK = g.stats(_mk([0.052, -0.032] * 20))


# --------------------------------------------------------------------------
# 1. The closed form, pinned exactly — n_req = n * (GOLIVE_MIN_T / t)^2.
# --------------------------------------------------------------------------

def test_n_req_formula_exact():
    # t=1.0 at n=40 -> 40 * (2.0/1.0)^2 = 160, no rounding ambiguity. A
    # mutated factor (2.0 -> 1.0) or a dropped square breaks this first.
    s = dict(_ONTRACK)
    s.update(t=1.0)
    hz = g.gate_horizon(s, first_close=_T0, now=_NOW)
    assert hz["n_req_t"] == 160, hz


def test_eta_date_arithmetic_through_the_rate():
    # 40 closes, first close 40d ago -> rate exactly 1.0/day; eta_days must be
    # (n_req - n) / rate and the date must be now + eta_days.
    hz = g.gate_horizon(_ONTRACK, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "on_track" and hz["binding"] == "t", hz
    assert abs(hz["eta_days"] - (hz["n_req_t"] - 40)) < 0.2, hz
    want = (_NOW + timedelta(days=hz["eta_days"])).date().isoformat()
    assert hz["eta"] == want, hz


# --------------------------------------------------------------------------
# 2. THE RATE DENOMINATOR IS ERA AGE, NEVER CLOSE SPAN (I1: a span cannot see
#    a stall — the last-close->now gap is the quantity that grows with the
#    fault). Measured on the live fleet: dad's span-rate read 2.2x its
#    age-rate because the book had stalled 7-11d.
# --------------------------------------------------------------------------

def test_rate_uses_era_age_not_close_span():
    # 40 closes crammed into a 10d burst, then a 30d stall. Span-rate would be
    # 40/10 = 4.0/day; the honest go-forward rate is 40/40 = 1.0/day.
    stalled = g.stats(_mk([0.052, -0.032] * 20, span_days=10.0))
    hz = g.gate_horizon(stalled, first_close=_T0, now=_NOW)
    assert hz["verdict"] in ("on_track", "undecidable"), hz
    assert hz["rate_cpd"] == pytest.approx(1.0, abs=0.05), \
        ("span denominator regression — a stalled book's ETA must stretch, "
         "not freeze", hz)


# --------------------------------------------------------------------------
# 3. Honest refusals: unreachable / undecidable / no_rate / unprojectable /
#    fail-closed junk. (The selftest walks these too; here they guard the
#    module against a refactor that keeps the selftest and loses the branch.)
# --------------------------------------------------------------------------

def test_negative_mean_is_unreachable_never_a_date():
    tails = g.stats(_mk([0.01] * 34 + [-0.30] * 6))
    hz = g.gate_horizon(tails, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "unreachable" and hz["eta"] is None, hz
    assert "trajectory" in hz["why"], hz     # a trajectory statement, not retire-now


def test_blown_maxdd_is_unreachable_not_projectable():
    blown = g.stats(_mk([2.0] * 10 + [-1.6] * 10 + [2.0] * 20))
    assert blown["mean_pct"] > 0 and blown["max_dd_frac"] >= g.GOLIVE_MAX_DD
    hz = g.gate_horizon(blown, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "unreachable" and "maxDD" in hz["why"], hz


def test_cap_converts_year_2051_to_undecidable_with_raw_days():
    noisy = g.stats(_mk([0.05, -0.045] * 20))    # t ~ 0.33 -> ~1,400d needed
    hz = g.gate_horizon(noisy, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "undecidable" and hz["eta"] is None, hz
    assert hz["raw_days"] > g.HORIZON_CAP_DAYS, hz   # magnitude stays auditable


def test_tiny_n_gets_floor_only():
    hz = g.gate_horizon(g.stats(_mk([0.01])), era_epoch=_T0.timestamp(),
                        now=_NOW)
    assert hz["verdict"] == "no_rate" and hz["eta_kind"] == "floor", hz
    assert hz["eta"] == (_T0 + timedelta(days=g.GOLIVE_MIN_DAYS)).date().isoformat()


def test_birth_burst_gets_a_floor_not_a_rate():
    # [(kz)] MEASURED on the live payload: 🎸 Barnesy published
    # `rate_cpd: 45.66` — 8 closes over the 4.2 HOURS since its first one.
    # A count floor is not a time floor; a rate needs a denominator too.
    burst = g.stats(_mk([0.02, 0.001] * 4, span_days=0.15))   # 8 closes, 3.6h
    hz = g.gate_horizon(burst, first_close=_NOW - timedelta(hours=4),
                        era_epoch=(_NOW - timedelta(days=1)).timestamp(),
                        now=_NOW)
    assert hz["verdict"] == "no_rate", hz
    assert hz["rate_cpd"] is None, "a birth burst must not publish a rate"
    assert hz["eta_kind"] == "floor" and hz["eta"], \
        "the honest window floor must survive — only the false rate goes"
    assert "burst" in hz["why"], hz


def test_the_time_floor_lets_a_real_rate_through():
    # ...and it must not swallow a genuine measurement: the same shape over a
    # week publishes its rate normally (a floor that blocks everything is the
    # I7 failure — a bar satisfied structurally measures nothing).
    real = g.stats(_mk([0.02, 0.001] * 4, span_days=7.0))
    hz = g.gate_horizon(real, first_close=_NOW - timedelta(days=7), now=_NOW)
    assert hz["verdict"] == "on_track" and hz["rate_cpd"], hz
    assert hz["rate_cpd"] == pytest.approx(8 / 7.0, abs=0.05), hz


def test_stalled_book_never_projects_the_window_to_today():
    # [(la)] THE DEFECT: the window bar reads the CLOSE SPAN, which only
    # advances when a NEW close lands — but the projection was pure calendar
    # (30 - age_d), so a STALLED 5/6 book published "on_track, eta = TODAY".
    # 40 closes, first 40d ago, last 12d ago -> span 28d (window fails), age
    # 40d (calendar term is negative). The honest answer is "at least one
    # more close away", never today.
    t0 = _NOW - timedelta(days=40)
    step = timedelta(days=28.0 / 39)
    rows = [(0.01, 0.1, t0 + i * step) for i in range(40)]
    s = g.stats(rows)
    assert s["days"] < g.GOLIVE_MIN_DAYS, "fixture must fail the window bar"
    hz = g.gate_horizon(s, first_close=t0, now=_NOW)
    assert hz["binding"] == "window", hz
    assert hz["eta_days"] >= 1.0 / hz["rate_cpd"] - 0.01, \
        ("a stalled book must be projected at least one close out, not today",
         hz)
    assert hz["eta"] != _NOW.date().isoformat(), \
        "a 12-day-silent book must never read as ready today"


def test_rate_denominator_spans_the_whole_era_not_the_close_tail():
    # [(la)] `era_rows` keys an era on the OPEN, so a HOLDING book's first
    # in-era close lags the era boundary by one holding period. Measuring the
    # rate from that close prices the wait out of existence — measured risk
    # on 🌾 carry (65-70h holds), the fleet's only go-live candidate.
    era_start = _NOW - timedelta(days=10)
    fc = _NOW - timedelta(days=2)
    rows = [(0.01, 0.1, fc + timedelta(hours=4 * i)) for i in range(10)]
    s = g.stats(rows)
    hz = g.gate_horizon(s, first_close=fc, era_epoch=era_start.timestamp(),
                        now=_NOW)
    assert hz["rate_cpd"] == pytest.approx(1.0, abs=0.1), \
        ("rate must be n/era-age (10/10d), not n/close-tail (10/2d)", hz)
    # ...and with NO era declared it still uses the first close (unchanged).
    hz2 = g.gate_horizon(s, first_close=fc, now=_NOW)
    assert hz2["rate_cpd"] == pytest.approx(5.0, abs=0.3), hz2


def test_future_first_close_refuses_a_rate():
    hz = g.gate_horizon(_ONTRACK, first_close=_NOW + timedelta(days=1),
                        now=_NOW)
    assert hz["verdict"] == "no_rate" and hz["eta"] is None, hz


def test_halves_only_is_unprojectable():
    halved = g.stats(_mk([0.05] * 20 + [-0.001] * 20))
    hz = g.gate_horizon(halved, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "unprojectable" and hz["eta"] is None, hz


def test_every_emitted_number_is_finite_or_none():
    # I5 at the boundary: save_history does not run json_safe, so one NaN here
    # kills the whole history write.
    for s in (_ONTRACK, g.stats(_mk([0.05, -0.045] * 20)), {}, {"n": 3}):
        hz = g.gate_horizon(s, first_close=_T0, now=_NOW)
        for k, v in hz.items():
            if isinstance(v, float):
                import math
                assert math.isfinite(v), (k, v)


# --------------------------------------------------------------------------
# 4. THE WIRING: main() must actually publish the block. A projection nothing
#    consumes is a note; a helper nothing calls is the (iz) inert-enforcement
#    shape. AST, not substring — this file's own doctrine forbids page-wide
#    substring claims.
# --------------------------------------------------------------------------

def test_main_publishes_horizon_key():
    tree = ast.parse((_ROOT / "scripts" / "golive_readiness.py").read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    keys = [k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant)]
    assert "horizon" in keys, "main() no longer publishes the horizon block"
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "gate_horizon"]
    assert calls, "main() no longer calls gate_horizon"
    # [(kv)] ...and the below-floor map must ride the same payload — a book
    # too thin for `books` was invisible to the very calendar built to flag
    # its undecidability (equities-regime at 0 closes, newborn Barnesy).
    assert "below_floor" in keys, "main() no longer publishes below_floor"
    ra = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name) and n.func.id == "roster_admits"]
    assert ra, "main()'s roster sweep no longer runs the liveness filter"


def test_roster_admits_is_fail_closed():
    # [(kv)] I1 at the roster: a frozen bot_pnl row must not resurrect a dead
    # book onto the go-live card. Fail-CLOSED on junk/absent stamps.
    now = _NOW
    assert g.roster_admits(now - timedelta(hours=1), now) is True
    assert g.roster_admits(now - timedelta(hours=49), now) is False
    assert g.roster_admits(None, now) is False
    assert g.roster_admits("not a stamp", now) is False
    # naive stamps are treated as UTC, not rejected (the DB writes UTC)
    naive_fresh = (now - timedelta(hours=2)).replace(tzinfo=None)
    assert g.roster_admits(naive_fresh, now) is True


def test_roster_admits_accepts_the_publishers_real_shape():
    # [(kw)] `fetch_bot_pnl` returns `updated_at` as an ISO STRING
    # (`.isoformat()` inside bot_pnl_store) — the datetime-only first cut
    # silently rejected the ENTIRE living roster and the sweep published
    # nothing. The (hj) class, inside the change whose PR cited (hj): this
    # fixture is the string the publisher actually emits, not the datetime
    # the consumer's author imagined.
    now = _NOW
    fresh_iso = (now - timedelta(hours=1)).isoformat()
    stale_iso = (now - timedelta(hours=72)).isoformat()
    naive_iso = (now - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    assert g.roster_admits(fresh_iso, now) is True, \
        "the publisher's ISO string form MUST be admitted when fresh"
    assert g.roster_admits(stale_iso, now) is False
    assert g.roster_admits(naive_iso, now) is True
    # a date-only string parses; it is stale by construction here
    assert g.roster_admits("2026-01-01", now) is False
    # ...and the pin that keeps the two ends honest: the publisher REALLY
    # does convert to a string (if this ever changes, the fixture above is
    # stale and this failure names it).
    import inspect
    import bot_pnl_store as store
    src = inspect.getsource(store.fetch_bot_pnl)
    assert 'd["updated_at"].isoformat()' in src, \
        "fetch_bot_pnl no longer stringifies updated_at — update roster_admits fixtures"


def test_non_book_publishers_are_declared_and_excluded():
    # [(kx)] The receipt's first live read admitted `market-context` — a
    # heartbeat publisher, not a book — onto the go-live card (I7: the sweep's
    # question is satisfied structurally by any non-trading publisher). The
    # declared set is the guard; every entry must carry a reason, and the
    # sweep must consult it (AST pin below in the wiring test).
    assert "market-context" in g.ROSTER_NON_BOOKS
    for name, why in g.ROSTER_NON_BOOKS.items():
        assert isinstance(why, str) and len(why) > 10, \
            (name, "a declared exclusion needs a reason, not a bare name")
    tree = ast.parse((_ROOT / "scripts" / "golive_readiness.py").read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    names = [n.id for n in ast.walk(fn) if isinstance(n, ast.Name)]
    assert "ROSTER_NON_BOOKS" in names, \
        "main()'s roster sweep no longer consults the non-book set"


def test_both_horizon_call_sites_use_the_same_maxdd_basis():
    # [(la)] The below-floor branch called gate_horizon on RAW stats while the
    # graded path folds MTM in first, so `bars["maxdd"]` meant two different
    # things either side of --min-closes — the below-floor side using the
    # realised-only definition I9 exists to replace. Pinned by STRUCTURE
    # because both call sites live in main()'s DB path, which no offline test
    # reaches: a mutation removing the wrap survived the whole suite until
    # this test existed (the (kz)/roster_admits lesson, applied without
    # waiting to be bitten twice).
    tree = ast.parse((_ROOT / "scripts" / "golive_readiness.py").read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "gate_horizon"]
    assert len(calls) >= 2, "expected a graded and a below-floor call site"
    # COUNT the folds, do not match argument names: both call sites can pass a
    # bare `s` and are then indistinguishable by name — the first cut of this
    # test allowed exactly that and the mutation walked straight through it.
    # One fold per horizon call site is the invariant that actually bites.
    folds = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "apply_mtm"]
    assert len(folds) >= len(calls), (
        f"{len(calls)} gate_horizon call sites but only {len(folds)} "
        "apply_mtm folds — one of them projects on a realised-only maxDD")


def test_main_publishes_roster_receipt():
    # [(kw)] scanned=0 / non-null error must be readable from the PAYLOAD —
    # the sweep's first failure was visible only in container stdout (I4).
    tree = ast.parse((_ROOT / "scripts" / "golive_readiness.py").read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    keys = [k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant)]
    assert "roster" in keys, "main() no longer publishes the roster receipt"


# --------------------------------------------------------------------------
# 4b. BELOW THE FLOOR [(kv)]: the card's footer line for books too thin for
#     `books` — present when published, absent on old payloads, junk-proof.
# --------------------------------------------------------------------------

def _bf(n_alltime, horizon):
    return {"n_alltime": n_alltime,
            "why_absent": "below --min-closes (10)", "horizon": horizon}


def test_card_renders_below_floor_footer(monkeypatch):
    thin_hz = g.gate_horizon(g.stats(_mk([0.01] * 8, span_days=8.0)),
                             first_close=_T0, now=_NOW)
    p = _payload({"bk": _book(_ONTRACK, None)})
    p["below_floor"] = {
        "band-barnes-lshadow": _bf(8, thin_hz),
        "equities-regime-lshadow": _bf(0, {"verdict": "no_rate", "eta": None,
                                           "why": "no closes ever"}),
    }
    html = _render(p, monkeypatch)
    assert "below floor:" in html, "footer line missing"
    assert "band-barnes-lshadow n8" in html, html
    assert "equities-regime-lshadow n0" in html, html
    assert "I17" in html, "the footer tooltip must carry the I17 framing"


def test_old_payload_has_no_below_floor_footer(monkeypatch):
    html = _render(_payload({"bk": _book(_ONTRACK, None)}), monkeypatch)
    assert "below floor:" not in html


@pytest.mark.parametrize("junk", [
    "not-a-dict", 123, {}, {"x": "not-a-dict"}, {"x": {"horizon": 5}},
    {"x": {"n_alltime": None, "horizon": {}}},
])
def test_card_survives_junk_below_floor(monkeypatch, junk):
    p = _payload({"bk": _book(_ONTRACK, None)})
    p["below_floor"] = junk
    html = _render(p, monkeypatch)
    assert html and "bk" in html, f"card blanked on junk below_floor {junk!r}"


# --------------------------------------------------------------------------
# 5. THE CONSUMER: the dashboard chip, rendered from a publisher-built payload
#    ((hj): never a hand-written fixture dialect).
# --------------------------------------------------------------------------

def _book(s, horizon):
    ok, fails = g.grade(s)
    b = {**g.book_payload(s), "fails": fails, "ready": bool(ok),
         "legacy_ready": False, "era": None, "alltime": g.book_payload(s)}
    if horizon is not None:
        b["horizon"] = horizon
    return b


def _payload(books):
    return {"updated": "2026-08-06T00:00:00+00:00", "ttl_sec": g.TTL_SEC,
            "bar": {"min_days": g.GOLIVE_MIN_DAYS,
                    "min_closes": g.GOLIVE_MIN_CLOSES,
                    "min_t": g.GOLIVE_MIN_T, "max_dd": g.GOLIVE_MAX_DD},
            "bar_names": list(g.BAR_NAMES), "books": books, "ready": []}


def _render(payload, monkeypatch):
    monkeypatch.setattr(dash, "fetch_states",
                        lambda keys: {"golive-readiness": payload})
    return dash.golive_card()


def test_card_renders_on_track_chip(monkeypatch):
    hz = g.gate_horizon(_ONTRACK, first_close=_T0, now=_NOW)
    html = _render(_payload({"bk": _book(_ONTRACK, hz)}), monkeypatch)
    assert f'→ {hz["eta"][5:]}' in html, "on_track chip missing"
    assert "never a promise" in html, "the honesty tooltip is load-bearing"


def test_card_renders_unreachable_and_floor_and_undecidable(monkeypatch):
    tails = g.stats(_mk([0.01] * 34 + [-0.30] * 6))
    noisy = g.stats(_mk([0.05, -0.045] * 20))
    thin = g.stats(_mk([0.01]))
    books = {
        "unreach": _book(tails, g.gate_horizon(tails, first_close=_T0,
                                               now=_NOW)),
        "undecid": _book(noisy, g.gate_horizon(noisy, first_close=_T0,
                                               now=_NOW)),
        "floor": _book(thin, g.gate_horizon(thin, era_epoch=_T0.timestamp(),
                                            now=_NOW)),
    }
    html = _render(_payload(books), monkeypatch)
    assert "∞ @trend" in html, "unreachable chip missing"
    assert "undecidable" in html, "undecidable chip missing"
    assert "≥ " in html, "window-floor chip missing"


def test_low_confidence_eta_carries_tilde(monkeypatch):
    # n=12, strong t, waiting on the CLOSES bar: on_track, but below
    # HORIZON_LOWCONF_N the rate itself has ~29% Poisson CV, so the date must
    # read "~" — near_miss_eta's own warning ("a thin book must never read as
    # N days from ready") applied to the chip.
    s = g.stats(_mk([0.02, 0.001] * 6, span_days=30.0))
    hz = g.gate_horizon(s, first_close=_T0, now=_T0 + timedelta(days=30))
    assert hz["verdict"] == "on_track" and hz["binding"] == "closes", hz
    assert hz["eta_conf"] == "low"
    html = _render(_payload({"bk": _book(s, hz)}), monkeypatch)
    assert "→ ~" in html, "low-confidence ETA must be visibly approximate"


def test_pre_horizon_payload_renders_unchanged(monkeypatch):
    # An OLD payload (no horizon key anywhere) must render with zero horizon
    # artefacts — additive means additive.
    html = _render(_payload({"bk": _book(_ONTRACK, None)}), monkeypatch)
    assert html and "bk" in html, "card must still render"
    for marker in ("→ ", "∞ @trend", "undecidable", "≥ "):
        assert marker not in html, f"horizon artefact {marker!r} on old payload"


@pytest.mark.parametrize("junk", [
    "not-a-dict", 123, {"verdict": 123}, {"verdict": "on_track"},
    {"verdict": "on_track", "eta": None}, {"verdict": None, "why": "x"},
    {"verdict": "no_rate"}, {},
])
def test_card_survives_junk_horizon(monkeypatch, junk):
    b = _book(_ONTRACK, None)
    b["horizon"] = junk
    html = _render(_payload({"bk": b}), monkeypatch)
    # the card's blanket except would BLANK everything on a crash — so the
    # assertion is that the book still renders, not merely that nothing raised.
    assert html and "bk" in html, f"card blanked on junk horizon {junk!r}"


def test_the_five_of_six_book_gets_a_chip_too(monkeypatch):
    # [(la)] `unprojectable` (only the halves bar failing) had no branch in
    # either consumer, so a 2/6 book showed a chip and the 5/6 book CLOSEST
    # to the gate showed none — read as "no data" rather than "one path bar".
    halved = g.stats(_mk([0.05] * 20 + [-0.001] * 20))
    hz = g.gate_horizon(halved, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "unprojectable"
    html = _render(_payload({"bk": _book(halved, hz)}), monkeypatch)
    assert "halves only" in html, "the 5/6 book must not be the silent one"


def test_below_floor_footer_labels_projections_and_keeps_verdicts(monkeypatch):
    # [(la)] The footer stamped `≥` (the card's own FLOOR glyph) on ANY eta,
    # so a PROJECTED date read as a floor; and unreachable/undecidable books
    # (eta=None) rendered as a bare `bot nN`, byte-identical to a book with
    # no horizon — the two verdicts that carry the I17 call, invisible on the
    # line built to surface I17.
    proj = {"verdict": "on_track", "eta": "2026-09-05",
            "eta_kind": "projected", "why": "window bar binds"}
    unre = {"verdict": "unreachable", "eta": None, "why": "mean <= 0"}
    floor = {"verdict": "no_rate", "eta": "2026-08-28", "eta_kind": "floor",
             "why": "window floor"}
    p = _payload({"bk": _book(_ONTRACK, None)})
    p["below_floor"] = {"proj-bk": _bf(8, proj), "unre-bk": _bf(6, unre),
                        "floor-bk": _bf(1, floor)}
    html = _render(p, monkeypatch)
    assert "&rarr;09-05" in html, "a projection must not wear the floor glyph"
    assert "&ge;08-28" in html, "a real floor keeps the floor glyph"
    assert "@trend" in html, "an unreachable below-floor book must say so"
    assert "window bar binds" in html, "per-book why must reach the tooltip"


def test_footer_says_so_when_the_roster_sweep_is_dark(monkeypatch):
    # [(la)] (kw) made the sweep self-reporting and left every CONSUMER blind:
    # on a dark fetch the roster books just vanish and the footer gets
    # shorter — silently dropping 📊 equities-regime, the standing I17 case.
    p = _payload({"bk": _book(_ONTRACK, None)})
    p["below_floor"] = {}
    p["roster"] = {"scanned": 0, "admitted": 0, "rejected": 0,
                   "non_book": 0, "error": None}
    html = _render(p, monkeypatch)
    assert "roster sweep DARK" in html, "a dark sweep must not read as clean"
    # ...and a healthy sweep says nothing.
    p["roster"] = {"scanned": 23, "admitted": 2, "rejected": 0,
                   "non_book": 1, "error": None}
    p["below_floor"] = {"x": _bf(3, {"verdict": "no_rate", "eta": None,
                                     "why": "thin"})}
    assert "roster sweep DARK" not in _render(p, monkeypatch)


def test_ready_book_gets_no_horizon_chip(monkeypatch):
    good = g.stats(_mk([0.01] * 40))
    hz = g.gate_horizon(good, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "ready"
    html = _render(_payload({"bk": _book(good, hz)}), monkeypatch)
    for marker in ("→ ", "∞ @trend", "undecidable"):
        assert marker not in html, "a ready book needs no projection chip"
