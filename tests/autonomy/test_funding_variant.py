"""[2026-08-13 (lp)] VARIANT INSTANCES of the Farmer file — 🛢️ Garrett's birth.

`lighter_funding_bot.py` carries BOTH real-money Farmer arms, so the variant
mechanism's load-bearing property is NO-OP-BY-DEFAULT: with FUNDING_VARIANT
unset, every behaviour below must be byte-identical legacy. The second
property is LEVER ISOLATION: a variant must never consume the judge's
`xp.funding.*` / `live.funding.*` levers — the judge's experiment arm is
`perps-funding-lighter-lshadow`, and a second consumer of its lever value
would grade the paired bar against a book the experiment never specified
(the (kp) version-skew class, one seat over).

What is guarded, in priority order:
  1. default = legacy: BOT id unchanged, MAX_VOL=inf admits everything a
     floor admits, apply_levers still reads the tuning lane;
  2. variant = isolated: own row id, tuning lane NOT read even when a lever
     is set (the mutation that reddens this restores the judge collision);
  3. the band is half-open [lo, hi): a book AT the ceiling is excluded, so
     two band instances can tile without double-admission.
"""
import importlib
import os

import pytest

pytestmark = pytest.mark.autonomy


def _fresh(monkeypatch, **env):
    for k in ("FUNDING_VARIANT", "FUNDING_MIN_VOL", "FUNDING_MAX_VOL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import lighter_funding_bot
    return importlib.reload(lighter_funding_bot)


@pytest.fixture(autouse=True)
def _restore_module():
    yield
    # leave the module in default shape for every other test in the session
    for k in ("FUNDING_VARIANT", "FUNDING_MIN_VOL", "FUNDING_MAX_VOL"):
        os.environ.pop(k, None)
    import lighter_funding_bot
    importlib.reload(lighter_funding_bot)


def test_default_is_byte_identical_legacy(monkeypatch):
    fb = _fresh(monkeypatch)
    assert fb.BOT == "perps-funding-lighter"
    assert fb.VARIANT == ""
    assert fb.MAX_VOL == float("inf")
    # the ceiling admits everything the old floor admitted
    assert fb.MIN_VOL <= 1e12 < fb.MAX_VOL


def test_variant_gets_its_own_row_id(monkeypatch):
    fb = _fresh(monkeypatch, FUNDING_VARIANT="band-garrett")
    assert fb.BOT == "band-garrett"
    # venue_context appends the venue suffix, so the published row becomes
    # band-garrett-lshadow — the musician-cohort convention — with ledgers,
    # claims and state keys separated automatically by the id.


def test_variant_reads_no_tuning_lane(monkeypatch):
    """THE JUDGE-COLLISION GUARD. With a lever set on the shadow lane, the
    default arm must consume it and a variant must NOT."""
    fb = _fresh(monkeypatch, FUNDING_VARIANT="band-garrett",
                FUNDING_MIN_VOL="1e5", FUNDING_MAX_VOL="2e6")

    class _Tuning:
        def __init__(self):
            self.calls = []

        def get_lever(self, name, default):
            self.calls.append(name)
            if name.endswith("min_vol"):
                return 5e6          # a judge experiment value
            return default

    spy = _Tuning()
    monkeypatch.setattr(fb, "tuning", spy)
    fb.apply_levers("lighter_shadow")
    assert spy.calls == [], (
        "a VARIANT consumed the tuning lane — this is the judge collision "
        f"the mechanism exists to prevent: {spy.calls}")
    assert fb.MIN_VOL == 1e5, "variant bars must come from env only"

    fb2 = _fresh(monkeypatch)          # default arm, same spy
    spy2 = _Tuning()
    monkeypatch.setattr(fb2, "tuning", spy2)
    fb2.apply_levers("lighter_shadow")
    assert any(c.startswith("xp.funding.") for c in spy2.calls), (
        "the DEFAULT shadow arm must still read its lane — legacy behaviour")
    assert fb2.MIN_VOL == 5e6, "the default arm must consume the lever"


def test_the_band_is_half_open(monkeypatch):
    fb = _fresh(monkeypatch, FUNDING_VARIANT="band-garrett",
                FUNDING_MIN_VOL="1e5", FUNDING_MAX_VOL="2e6")
    assert fb.MIN_VOL <= 1e5 < fb.MAX_VOL          # floor admitted
    assert fb.MIN_VOL <= 1.99e6 < fb.MAX_VOL       # inside
    assert not (fb.MIN_VOL <= 2e6 < fb.MAX_VOL)    # ceiling excluded
    assert not (fb.MIN_VOL <= 9.9e4 < fb.MAX_VOL)  # below floor excluded


def test_variant_takes_no_allocation_scale(monkeypatch):
    """[(nb), 15-Aug] THE OTHER EXTERNAL KNOB. apply_levers short-circuits
    the tuning lane for a variant, but the (jr) allocation consumer arrived
    later and was not variant-gated: the organ's no-claim probe floor (0.25)
    quarter-sized 🛢️ Garrett to $7.50 clips while its whole birth thesis is
    validating a study cell measured AT $25 clips. Asserted on the SOURCE
    GUARD (the `shadow_tag and not VARIANT` gate), driven through the same
    module-reload fixture as the lane test above."""
    import ast
    import inspect

    fb = _fresh(monkeypatch, FUNDING_VARIANT="band-garrett",
                FUNDING_MIN_VOL="1e5", FUNDING_MAX_VOL="2e6")
    src = inspect.getsource(fb)
    tree = ast.parse(src)
    guarded = False
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(src, node.test) or ""
            if "shadow_tag" in seg and "allocation_scale" in ast.dump(node):
                guarded = "not VARIANT" in seg.replace("(", " ").replace(")", " ")
                break
    assert guarded, (
        "the allocation_scale consumer must be gated `shadow_tag and not "
        "VARIANT ...` — a variant scaled by an external organ is no longer "
        "single-policy by construction ((lp)/(nb))")


def test_variant_clip_is_its_own_measured_size_not_the_global(monkeypatch):
    """[19-Aug (qi)] 🛢️ Garrett ran $30 clips for its whole life against a
    founding study whose ONLY measured cell is $25 — `ctx.order_usd(ORDER_USD)`
    without `own` falls through to the global LIGHTER_ORDER_USD for every
    shadow book. The variant contract is env-only single-policy config, and
    the clip is config. Behavioural pin on the venues seam itself: own=True in
    a shadow mode returns the caller's own default; own=False returns the
    global — BOTH directions, so the fix and the Farmer twins' deliberate
    mirroring are each load-bearing here."""
    import venues
    monkeypatch.setenv("LIGHTER_ORDER_USD", "30")
    ctx = venues.venue_context(bot="test-variant-clip", default_hl_net="testnet",
                               paper_start=1000.0)
    monkeypatch.setattr(ctx, "mode", "lighter_shadow", raising=False)
    assert ctx.order_usd(25.0, own=True) == 25.0, \
        "a variant's own clip must survive the global env"
    assert ctx.order_usd(25.0, own=False) == 30.0, \
        "the Farmer twins mirror live sizing — own=False keeps the global"


def test_farmer_call_sites_key_own_on_variant(monkeypatch):
    """AST pin (a substring test is not a wiring test): EVERY `.order_usd(`
    call in lighter_funding_bot.py must pass own=bool(VARIANT) — so the Farmer
    (VARIANT='') stays byte-identical control-arm mirroring while any variant
    keeps its measured size. A third call site added without the keyword
    reintroduces the Garrett defect silently; this makes it loud."""
    import ast
    import pathlib
    import lighter_funding_bot as fb
    tree = ast.parse(pathlib.Path(fb.__file__.replace(".pyc", ".py"))
                     .read_text(encoding="utf-8"))
    sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "order_usd"):
            kw = {k.arg: k.value for k in node.keywords}
            ok = ("own" in kw and isinstance(kw["own"], ast.Call)
                  and isinstance(kw["own"].func, ast.Name)
                  and kw["own"].func.id == "bool"
                  and len(kw["own"].args) == 1
                  and isinstance(kw["own"].args[0], ast.Name)
                  and kw["own"].args[0].id == "VARIANT")
            sites.append((node.lineno, ok))
    assert sites, "no order_usd call sites found — the scan is broken, not clean"
    bad = [ln for ln, ok in sites if not ok]
    assert not bad, f"order_usd call site(s) missing own=bool(VARIANT): lines {bad}"
