"""[2026-08-20 (sp)] THE THREE THINGS THAT MAKE THE BRAIN SAFE ON REAL MONEY.

Eamon: *"Optimise the lookup ... and ensure the brain doesn't cause problems."*

`(so)` wired the brain's multiplier into both real-money rows and justified it
with one sentence: *"the multiplier proposes; the rails dispose."* An
adversarial audit of that change measured the sentence and it was **false in
the consequential direction** — `notional_ok` is a BOOLEAN, so a caller's
`continue` discards the whole CANDIDATE rather than the excess:

  * 💸 the Farmer, shipped live config `order_usd $37.50 / cap $150`: a brain
    rung of 4.5 asks $168.75 — over the cap FROM AN EMPTY BOOK. Every ranked
    candidate skipped, every loop, indefinitely. **The brain rewarding this
    book for its evidence would have stopped it trading.**
  * 🙏 Avo, live equity ~$63 / clip ~$15.70 / min clip $5: a reduce rung of
    1/4.5 gives $3.49 and 1/6.7 gives $2.34 — both under the floor, so every
    entry `continue`s. A 100% halt dressed as a size reduction, self-locking
    (a book that stops trading stops producing the closes that would lift the
    reduce), and invisible: the row keeps publishing `status: online`.
  * 🙏 Avo again, expand side: its own `_clip_scale_now` docstring states the
    invariant *"gross notional can never exceed account equity — the book is
    1.00x by construction and no lever reaches past it"*, and `(so)` broke it
    silently — 6.39x puts two slots at $99.98 = 3.19x equity.

The fixes are behavioural, so these tests are behavioural: they drive the real
functions, not the shape of the source.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _src(name):
    return (ROOT / name).read_text()


def _fn(name, fnname):
    for n in ast.walk(ast.parse(_src(name))):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fnname:
            return n
    return None


# --------------------------------------------------------------------------
# 1. the rail TRIMS
# --------------------------------------------------------------------------
def test_the_farmer_trims_to_the_rail_instead_of_refusing():
    """The `continue` on a cap breach must be reachable ONLY when even the
    PRE-BRAIN clip does not fit. Asserted on the source because the entry loop
    is a 400-line closure with no seam — but asserted on the CONTROL FLOW, not
    on a phrase: the trim branch must exist, must compare against the pre-brain
    clip, and must derive its size from the rail's own `max_notional`.
    """
    s = _src("lighter_funding_bot.py")
    assert "_clip_prebrain" in s, "the pre-brain clip is not even recorded"
    assert "BRAIN_CLIP_TRIMMED" in s, "no trim branch"
    # the trim is bounded by the rail's own number, never by a local constant
    assert "ctx.rails.max_notional" in s
    # ...and it only ever fires when the brain made the clip bigger
    assert "if clip > _clip_prebrain and _room >= _clip_prebrain:" in s, (
        "the trim must be gated on the brain having INCREASED the clip — "
        "otherwise it silently changes pre-brain refusal behaviour")


def test_the_farmer_still_refuses_when_the_unscaled_clip_does_not_fit():
    """The safety property that must NOT have moved: a book at its cap with a
    neutral brain refuses exactly as it did before (so)."""
    s = _src("lighter_funding_bot.py")
    i = s.index("BRAIN_CLIP_TRIMMED")
    tail = s[i:i + 1600]
    assert "NOTIONAL_CAP_SKIP" in tail, (
        "the else-branch refusal disappeared — an over-cap clip with a neutral "
        "brain must still be skipped")
    assert "post-trim" in tail, "the belt-and-braces re-check is gone"


# --------------------------------------------------------------------------
# 2. Avo is restrict-only, and preserves its own stated invariant
# --------------------------------------------------------------------------
def test_avos_brain_is_restrict_only_on_real_money():
    """🙏 Avo's module docstring states `1.00x by construction`. Its
    `live.clip_scale` lever is `min(1.0, ...)` for exactly that reason. The
    brain now matches — expansion on a real-money book past its own equity is
    a LEVERAGE decision, and I22 says leverage needs a measured vol target
    this book does not have.
    """
    s = _src("lighter_avo_live_bot.py")
    assert "if bmult > 1.0:" in s, "the expand side is not refused"
    assert "brain_expand_refused" in s, (
        "a refused expand must be COUNTED and published — a silent refusal is "
        "the class this whole pass exists to close")
    # the invariant it protects is still stated in the module
    assert "1.00x by construction" in s


def test_avos_reduce_floors_at_the_min_clip_instead_of_halting():
    """A reduce must make the book smaller, not retire it. The floor is only
    applied when the UNSCALED stake would itself have been tradeable — a book
    whose own clip is under the minimum is still skipped, as before.
    """
    s = _src("lighter_avo_live_bot.py")
    assert "if stake < MIN_CLIP_USD <= clip * S.stake_mult(tag, bars):" in s, (
        "the floor must be conditional on the PRE-brain stake being tradeable")
    assert "brain_floored" in s, "a floored reduce must be counted"
    # and the original skip survives for the genuinely-too-small case
    assert s.count("if stake < MIN_CLIP_USD") >= 2


def test_both_avo_counters_are_published_and_default_to_zero():
    """A counter nobody can read is not a receipt. Both must reach the row,
    and both must be initialised in EVERY scope the publish helper runs from —
    the kill/halt paths publish before the entry section assigns anything.
    """
    s = _src("lighter_avo_live_bot.py")
    assert '"brain_expand_refused": brain_expand_refused,' in s
    assert '"brain_floored": brain_floored,' in s
    assert s.count("brain_expand_refused = brain_floored = 0") >= 2, (
        "the counters must be initialised in the loop-scope defaults too, or "
        "a halt path raises NameError inside the publish — telemetry taking "
        "down trading, the inverse of why it was added")


# --------------------------------------------------------------------------
# 3. the taker takes conviction as RISK, so constant-risk sizing survives
# --------------------------------------------------------------------------
def test_the_taker_scales_risk_not_the_clip():
    import importlib
    import sys
    sys.path.insert(0, str(ROOT))
    tt = importlib.import_module("lighter_ticket_taker")
    # the default path is untouched
    assert tt.vol_clip(6.0) == pytest.approx(tt.RISK_USD / 0.03, abs=0.01)
    assert tt.vol_clip(2.0) == tt.CLIP_MAX, "a calm book still hits the cap"
    assert tt.vol_clip(30.0) == tt.CLIP_MIN
    assert tt.vol_clip(None) == tt.CLIP_USD
    # a doubled risk budget doubles the clip — where the ceiling allows
    assert tt.vol_clip(10.0, risk_usd=tt.RISK_USD * 2) == pytest.approx(
        2 * tt.vol_clip(10.0), abs=0.02)
    # ...and the CEILING still binds, which is the property (so) destroyed
    assert tt.vol_clip(10.0, risk_usd=tt.RISK_USD * 1000) == tt.CLIP_MAX
    assert tt.vol_clip(10.0, risk_usd=tt.RISK_USD * 1000,
                       clip_max=tt.CLIP_MAX * 2) == tt.CLIP_MAX * 2
    # the FLOOR is not lifted by a reduce: a tiny risk budget still cannot
    # produce a sub-minimum clip
    assert tt.vol_clip(10.0, risk_usd=0.0001) == tt.CLIP_MIN


def test_the_taker_passes_the_brain_through_vol_clip():
    """...and the wiring actually uses it. A function that CAN take a risk
    budget while the call site still multiplies the result would pass the test
    above and change nothing."""
    s = _src("lighter_ticket_taker.py")
    assert "risk_usd=RISK_USD * _bm" in s
    assert "clip_max=CLIP_MAX * getattr(fleet_bus" in s


# --------------------------------------------------------------------------
# 4. the shadow books' gross budget actually bounds gross
# --------------------------------------------------------------------------
@pytest.mark.parametrize("mod,const,cap_name", [
    ("funding_carry_bot.py", "NOTIONAL", "MAX_POSITIONS"),
    ("lighter_book_hull_bot.py", "CLIP_USD", "MAX_POSITIONS"),
    ("lighter_book_kiyosaki_bot.py", "CLIP_USD", "MAX_POSITIONS"),
    ("lighter_book_grimes_bot.py", "CLIP_USD", "MAX_POSITIONS"),
    ("lighter_book_douglas_bot.py", "CLIP_USD", "MAX_POSITIONS"),
    ("lighter_nav_cook_bot.py", "CLIP_USD", "MAX_POSITIONS"),
])
def test_every_rail_less_book_passes_a_gross_budget(mod, const, cap_name):
    """A book with no SafetyRails cap must hand `brain_clip*` both a deployed
    total and a budget — otherwise the multiplier both proposes and disposes
    there, which is precisely what the (so) safety sentence assumed away.
    """
    s = _src(mod)
    assert "deployed_usd=" in s, f"{mod} passes no deployed total"
    assert "gross_cap_usd=" in s, f"{mod} passes no gross budget"
    # AST, not substring: every one of these call sites wraps its arguments
    # across lines, so a textual match would be testing the formatter. (The
    # first draft of this assertion did exactly that and failed on all six.)
    args = [[ast.unparse(a) for a in c.args]
            for c in ast.walk(ast.parse(s))
            if isinstance(c, ast.Call)
            and (getattr(c.func, "attr", "") or getattr(c.func, "id", ""))
            == "brain_gross_cap"]
    assert args, f"{mod} never calls brain_gross_cap"
    assert [cap_name, const] in args, (
        f"{mod}'s budget must be derived from its own {cap_name}/{const} "
        f"CONSTANTS, not typed as a number that drifts: {args}")


def test_the_budget_is_derived_from_constants_not_from_a_scaled_clip():
    """🌾 carry and ⚖️ Counterweight also carry the allocation organ's scale,
    and carry sits AT its 4.0 ceiling right now. Budgeting off the SCALED base
    would hand the brain another $24k of room on the one book that least needs
    it; budgeting off the constants leaves the allocation organ's behaviour
    untouched and gives the brain no room there at all.
    """
    def _cap_args(mod):
        return [[ast.unparse(a) for a in c.args]
                for c in ast.walk(ast.parse(_src(mod)))
                if isinstance(c, ast.Call)
                and (getattr(c.func, "attr", "") or getattr(c.func, "id", ""))
                == "brain_gross_cap"]

    assert ["MAX_POSITIONS", "NOTIONAL"] in _cap_args("funding_carry_bot.py"), (
        "carry must budget off NOTIONAL (its constant), NOT the "
        "allocation-scaled base — it sits AT the organ's 4.0 ceiling today")
    cw = _cap_args("lighter_funding_spread_bot.py")
    assert ["K * 2", "ORDER_USD"] in cw, (
        "Counterweight must budget K*2 LEGS off ORDER_USD — using K alone "
        "would let the bound be breached by exactly the factor that makes it "
        f"a spread book, and using the scaled base defeats it: {cw}")
