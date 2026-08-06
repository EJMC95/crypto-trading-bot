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


def test_ready_book_gets_no_horizon_chip(monkeypatch):
    good = g.stats(_mk([0.01] * 40))
    hz = g.gate_horizon(good, first_close=_T0, now=_NOW)
    assert hz["verdict"] == "ready"
    html = _render(_payload({"bk": _book(good, hz)}), monkeypatch)
    for marker in ("→ ", "∞ @trend", "undecidable"):
        assert marker not in html, "a ready book needs no projection chip"
