"""The horizon must not call a THIN sample a dead one.  [2026-08-20 (tz)]

THE DEFECT. `gate_horizon` declared `unreachable` — *"more of the same closes
cannot flip mean/t/halves"* — on `mean <= 0` **alone, at any n**. That claim is
false on a thin sample: with n=10 and a wide SE a mean of −0.155% is entirely
consistent with a true mean of +2%, and more closes can absolutely flip it.

IT MATTERED because `unreachable` is in `DOCKET_VERDICTS`, so it starts I17's
keep-or-retire clock. The pipeline ran

    mean <= 0 (any n)  ->  unreachable  ->  decision docket  ->  retire

and a book could be routed toward retirement by noise on ten trades. Measured
the day this shipped, 🌾 carry — the fleet's best-evidenced book — carried
`unreachable` on **n=10**, and four books (🧘 Douglas, 🎯 the sniper, 🎫 the
Taker, 💸 the Farmer's shadow) sat on that conveyor with upper bounds still
comfortably ABOVE zero.

THE FIX is a power gate, not a softening: `unreachable` now requires the
one-sided UPPER bound `mean + 1.28*se` to sit at or below zero — the sample must
actually have EXCLUDED a positive mean. Same z the fleet already uses for I16's
lower bound, deliberately: one standard of evidence whether the fleet is
deciding to feed a book or to doubt one.

The discrimination is the point, and these tests pin BOTH directions:
a genuinely measured loser must STILL read `unreachable`.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import golive_readiness as g            # noqa: E402

NOW = dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc)


def _rows(pcts, start_days_ago=60, usd=20.0):
    """Closed-trade rows, oldest first, evenly spread over the window."""
    out, n = [], len(pcts)
    for i, p in enumerate(pcts):
        ts = NOW - dt.timedelta(days=start_days_ago * (1 - i / max(1, n - 1)))
        out.append((p, p * usd, ts))
    return out


def _horizon(pcts, **kw):
    """(horizon, stats). `gate_horizon(s, first_close, era_epoch, now)` — the
    second arg is the FIRST CLOSE, not the bar map; passing bars there silently
    yields `no_rate` for every fixture, which is how the first draft of this
    file "passed" nothing."""
    rows = _rows(pcts, **kw)
    st = g.stats(rows)
    return g.gate_horizon(st, first_close=rows[0][2], now=NOW), st


# ------------------------------------------------------------------ the fix
def test_a_thin_negative_sample_is_underpowered_not_unreachable():
    """n=10, mean slightly negative, wide dispersion — the carry shape."""
    pcts = [-0.05, 0.06, -0.04, 0.05, -0.06, 0.04, -0.05, 0.05, -0.04, -0.01]
    hz, s = _horizon(pcts)
    assert s["mean_pct"] < 0, s["mean_pct"]
    upper = s["mean_pct"] + g.HORIZON_Z * s["se_pct"]
    assert upper > 0, "fixture must not have excluded a positive mean"
    assert hz["verdict"] == "underpowered", hz
    assert "has not excluded a positive mean" in hz["why"], hz["why"]


def test_underpowered_is_not_on_the_retirement_docket():
    """The whole reason the verdict exists — it must not start I17's clock."""
    assert "underpowered" not in g.DOCKET_VERDICTS, (
        "an underpowered book is being routed to the keep-or-retire docket; "
        "that is the pipeline this fix exists to break")
    assert "unreachable" in g.DOCKET_VERDICTS, \
        "a genuinely measured loser must still reach the docket"


def test_it_says_how_many_closes_would_decide_the_sign():
    """A verdict that only says 'not yet' is not actionable; feed it a number."""
    pcts = [-0.05, 0.06, -0.04, 0.05, -0.06, 0.04, -0.05, 0.05, -0.04, -0.01]
    hz, s = _horizon(pcts)
    assert isinstance(hz.get("n_req_decide"), int) and hz["n_req_decide"] > len(pcts), hz
    # se scales as 1/sqrt(n), so n_req is where the upper bound reaches zero.
    # [2026-08-20] the critical value comes from `horizon_crit` — the ONE owner
    # — not from a retyped constant. Typing `g.HORIZON_Z` here made the test
    # agree with the code only while the code used a constant too.
    import math
    crit = g.horizon_crit(len(pcts))
    want = math.ceil(len(pcts) * (crit * s["se_pct"] / abs(s["mean_pct"])) ** 2)
    assert hz["n_req_decide"] == want, (hz["n_req_decide"], want, crit)


# --------------------------------------------------- the OTHER direction
def test_a_measured_loser_is_still_unreachable():
    """The gate must DISCRIMINATE. A tight, genuinely negative sample keeps its
    verdict — otherwise this is a blanket softening rather than a fix, and the
    fleet loses the signal it needs to act on a book that really is losing."""
    pcts = [-0.02] * 40 + [-0.018] * 40      # tight, unambiguously negative
    hz, s = _horizon(pcts)
    upper = s["mean_pct"] + g.HORIZON_Z * s["se_pct"]
    assert upper < 0, "fixture must exclude a positive mean"
    assert hz["verdict"] == "unreachable", hz
    assert "EXCLUDED a positive mean" in hz["why"], hz["why"]


def test_a_blown_drawdown_is_still_unreachable_however_thin():
    """A drawdown that has already blown the bar cannot un-blow at any n, so
    power is irrelevant there — only the MEAN branch is power-gated."""
    # big early loss then small gains: mean can even be positive-ish, DD blown
    pcts = [-0.60] + [0.01] * 9
    rows = _rows(pcts, usd=1000.0)
    st = g.stats(rows, book_usd=1000.0)
    if g.bar_map(st)["maxdd"]:
        pytest.skip("fixture did not blow the drawdown bar")
    hz = g.gate_horizon(st, first_close=rows[0][2], now=NOW)
    assert hz["verdict"] == "unreachable", hz
    assert "un-blow" in hz["why"], hz["why"]


def test_an_unmeasurable_se_never_counts_as_an_exclusion():
    """I6: absence of evidence must not promote a book toward the docket.

    A sample with no computable SE (zero dispersion) has excluded nothing, and
    the fail-safe direction here is AWAY from the retirement conveyor.
    """
    # Take a REAL negative sample and blank its SE — identical closes will not
    # do it (they give a perfectly measured SE of ~5e-19, and `unreachable` is
    # then arithmetically CORRECT), so the guard is exercised directly.
    rows = _rows([-0.05, 0.06, -0.04, 0.05, -0.06, 0.04, -0.05, 0.05,
                  -0.04, -0.01])
    st = g.stats(rows)
    st["se_pct"] = None
    hz = g.gate_horizon(st, first_close=rows[0][2], now=NOW)
    assert hz["verdict"] != "unreachable", (
        "an unmeasurable SE was read as 'the sample excluded a positive "
        "mean' — absence of evidence must never route a book to the docket")


def test_the_gate_uses_the_same_z_as_the_allocation_lower_bound():
    """One standard of evidence for feeding and for doubting.

    [2026-08-20] pinned by IDENTITY, not by two constants that happen to match.
    Comparing `HORIZON_Z == Z_LOWER` stayed green against two independent
    implementations of the bound, which is the second-rule shape ((hj) — "pin
    re-use by identity, not by asserting constant names are absent").
    """
    import fleet_allocation as fa
    assert g.HORIZON_Z == fa.Z_LOWER, (
        f"the horizon doubts a book at z={g.HORIZON_Z} but the allocation "
        f"organ feeds one at z={fa.Z_LOWER}; a fleet that applies a different "
        f"standard in each direction will drift toward whichever is stricter")
    # ... and the same INSTRUMENT, at every sample size, not just the same
    # large-sample floor.
    for n in (3, 5, 12, 40, 300):
        assert g.horizon_crit(n) == fa.t_crit(n, floor=g.HORIZON_Z), n
    assert g.horizon_crit(5) > g.horizon_crit(300), \
        "a thin sample must be doubted with a WIDER interval, in both organs"


def test_the_horizon_fails_toward_keeping_a_book_when_the_owner_is_missing():
    """No instrument is not evidence for a retirement verdict (I6).

    `horizon_crit` imports the rule's single owner. If that import ever breaks
    — a COPY set that drops `fleet_allocation.py`, a rename — the honest result
    is that no sample has been shown to exclude a positive mean, so nothing may
    reach the retirement docket on that path.
    """
    import builtins
    real = builtins.__import__

    def _no_alloc(name, *a, **k):
        if name == "fleet_allocation":
            raise ImportError("simulated: module absent from this image")
        return real(name, *a, **k)

    # The fixture must DISCRIMINATE: it is a sample that WOULD be excluded if
    # the code quietly fell back to the constant, so a fallback is visible as a
    # verdict flip rather than hidden behind a book that was underpowered
    # anyway. The first draft used the thin fixture and passed under the
    # mutation — a vacuous test, caught by I3 and not by reading it.
    pcts = [-0.02] * 40 + [-0.018] * 40
    hz_ok, s_ok = _horizon(pcts)
    assert hz_ok["verdict"] == "unreachable", (
        "control: with the owner present this sample IS a measured loser")
    assert s_ok["mean_pct"] + g.HORIZON_Z * s_ok["se_pct"] < 0, (
        "control: the constant fallback would also exclude it, so a flip to "
        "'unreachable' below can only come from the fallback")

    builtins.__import__ = _no_alloc
    try:
        assert g.horizon_crit(50) is None
        hz, _ = _horizon(pcts)
        assert hz["verdict"] != "unreachable", (
            "a missing critical-value owner must NOT route a book to the "
            "retirement docket — that is absence of evidence acting as proof")
    finally:
        builtins.__import__ = real


# ------------------------------------------------------------------ (xg)
# THE VERDICT MAY NOT ASSERT AN EXCLUSION THE SAMPLE NEVER MADE.
# The `underpowered` branch is gated on `bars["maxdd"]`, so a book failing the
# mean bar AND the drawdown bar falls straight through to `unreachable` — and
# that block used to print "the sample has EXCLUDED a positive mean" beside
# the very number refuting it. Measured in the live payload the day this was
# written: 🪁 band-kelly-lshadow published "upper bound +0.027% <= 0 — the
# sample has EXCLUDED a positive mean". That sentence is the I17 precondition
# a RETIREMENT is written on.

def _blown_dd_open_mean():
    """A book with a blown drawdown whose mean is negative but NOT excluded.

    DETERMINISTIC on purpose. A seeded random fixture reproduced this state on
    9 of 14 seeds and a POSITIVE mean on the rest, so the first draft `skip`ped
    — and a skipped test reads exactly like a passing one in the summary line,
    which is the repo's own "a check that inspects nothing reports clean" trap.
    One 60% loss blows the drawdown bar permanently; a symmetric +-8% ladder
    around it supplies dispersion, so the mean is dragged below zero while the
    upper bound stays clearly ABOVE it. Every precondition below is ASSERTED,
    never skipped: if this stops reproducing the state, the test must go red,
    because it is then no longer testing what it claims.
    """
    pcts = [-0.60] + [0.08, -0.08] * 60
    rows = _rows(pcts, usd=1000.0)
    st = g.stats(rows, book_usd=1000.0)
    bars = g.bar_map(st)
    assert bars["mean"] is False, ("fixture no longer fails the mean bar", st["mean_pct"])
    assert bars["maxdd"] is False, ("fixture no longer blows the drawdown bar",
                                    st.get("max_dd_frac"))
    upper = st["mean_pct"] + g.horizon_crit(st["n"]) * st["se_pct"]
    assert upper > 0, ("fixture's upper bound is genuinely excluded — it can no "
                       "longer stand in for the un-excluded case", upper)
    return st, rows


def test_a_blown_drawdown_never_manufactures_an_exclusion_of_the_mean():
    st, rows = _blown_dd_open_mean()
    hz = g.gate_horizon(st, first_close=rows[0][2], now=NOW)
    assert hz["verdict"] == "unreachable", hz          # the drawdown is permanent
    assert hz.get("mean_excluded") is False, hz        # ...but the mean is NOT
    assert "has NOT excluded a positive mean" in hz["why"], hz["why"]
    assert "has EXCLUDED a positive mean" not in hz["why"], (
        "the verdict claims an exclusion its own upper bound refutes — this is "
        "the sentence an I17 retirement is written on")
    assert "un-blow" in hz["why"], "the real binding cause must still be named"


def test_a_genuine_exclusion_still_says_so_and_publishes_the_flag():
    """The fix must DISCRIMINATE, or it is a blanket softening (I3)."""
    pcts = [-0.02] * 40 + [-0.018] * 40
    hz, st = _horizon(pcts)
    assert hz["verdict"] == "unreachable", hz
    assert hz.get("mean_excluded") is True, hz
    assert "has EXCLUDED a positive mean" in hz["why"], hz["why"]


def test_the_exclusion_flag_is_published_not_left_to_prose():
    """A docket that string-matches the reason is a second copy of the rule."""
    st, rows = _blown_dd_open_mean()
    hz = g.gate_horizon(st, first_close=rows[0][2], now=NOW)
    assert "mean_excluded" in hz, (
        "an `unreachable` verdict must publish whether the MEAN was excluded — "
        "otherwise the only way to know is to parse the sentence")
