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
