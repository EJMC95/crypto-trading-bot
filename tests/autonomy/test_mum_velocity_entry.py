"""[2026-09-02 (xl)] 👩 MUM'S DIP-VELOCITY BAND — the shape of the fall.

Eamon: *"She needs to be able to jump onto something at the perfect moment...
does she need the ability to look at trends previously before making a trade?"*

The measured answer to both halves: the moment is not about SPEED (a fresh RSI
cross is worth +0.043%, t 0.88 — nothing), it is about the SHAPE of the fall,
which needs a 4-bar lookback. A drop of 12-20 RSI points over 4h reads
+0.309%/trade exit-free (t_cl 2.82 trailing 180d) against −0.076% for a slow
drift and −0.091% for a violent collapse, and on her OWN LEDGER — senior to
any replay (I14) — in-band trades read +1.039%/trade (t 3.68) live and
+1.131% (t 3.82) on the twin.

WHAT THESE TESTS GUARD, in the order the damage would be worst:
  1  SHIPPED INERT. The defaults are +-999, so `enter` is byte-identical to
     the pre-(xl) rule. Registering a lever moves nothing ((it)).
  2  RESTRICT-ONLY. The band is a conjunct; it can never ADMIT an entry the
     shipped cell refused. This is what keeps it safe to arm on a live book.
  3  FAIL-CLOSED. Armed but unmeasurable (too few bars) must REFUSE, never
     fall through to the unfiltered rule.
  4  THE LIVE ARM IS NOT TOUCHED. The band is reached through `xp.mum.*` on
     the SHADOW twin; `live.mum.*` exists but is judge-promoted only, and the
     judge is its sole writer.
  5  THE CENSUS SEES IT. An armed band that refuses everything must not read
     as a quiet tape (I18).
"""
import copy
import random
import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fleet_tuning as ft            # noqa: E402
import lighter_family_bot as fb      # noqa: E402

pytestmark = pytest.mark.autonomy


def _mum():
    return next(s for s in fb.STRATEGIES if s.bot == "freqtrade-mum")


def _tape(n=500, seed=11):
    """A DOWNTREND with real dips — so her cell (rsi<bar AND NOT uptrend)
    actually fires. A fixture that never fires would make every assertion
    below vacuous, which is this repo's own 'a check that inspects nothing
    reports clean' trap; `test_the_fixture_actually_fires` pins it."""
    rnd = random.Random(seed)
    px, c, v = 100.0, [], []
    for _ in range(n):
        px *= 1 - 0.0015 + rnd.gauss(0, 0.018)
        c.append(px)
        v.append(1.0)
    return c, v


def _entries(st, c, v):
    hits = 0
    for k in range(st.min_bars, len(c)):
        sig = st.signals({"c": c[:k + 1], "h": c[:k + 1],
                          "l": c[:k + 1], "v": v[:k + 1]}, {})
        if sig and sig.get("enter"):
            hits += 1
    return hits


def _armed(lo, hi, lookback=None):
    st = copy.copy(_mum())
    st.VEL_LO, st.VEL_HI = lo, hi
    if lookback is not None:
        st.VEL_LOOKBACK = lookback
    return st


def test_the_fixture_actually_fires():
    c, v = _tape()
    assert _entries(_mum(), c, v) > 20, (
        "the tape never triggers her cell — every other test here would be "
        "vacuously green")


# ------------------------------------------------------------------ 1 · inert
def test_the_shipped_default_is_inert():
    cls = type(_mum())
    assert cls.VEL_LO <= -900.0 and cls.VEL_HI >= 900.0, (cls.VEL_LO, cls.VEL_HI)


def test_entries_are_byte_identical_under_the_default():
    c, v = _tape()
    base = _entries(_mum(), c, v)
    assert _entries(_armed(-999.0, 999.0), c, v) == base


def test_the_registry_default_is_the_inert_one_on_both_lanes():
    for lane in ("xp", "live"):
        assert ft.LEVERS[f"{lane}.mum.vel_lo"]["env_default"] <= -900.0
        assert ft.LEVERS[f"{lane}.mum.vel_hi"]["env_default"] >= 900.0


# --------------------------------------------------------- 2 · restrict-only
@pytest.mark.parametrize("lo,hi", [(12.0, 20.0), (8.0, 24.0), (0.0, 999.0),
                                   (-999.0, 8.0), (14.0, 18.0)])
def test_the_band_can_only_ever_remove_entries(lo, hi):
    """A conjunct, never a disjunct. This is what makes arming it safe."""
    c, v = _tape()
    base = _entries(_mum(), c, v)
    assert _entries(_armed(lo, hi), c, v) <= base


def test_a_wider_band_admits_at_least_as_much_as_a_narrower_one():
    c, v = _tape()
    assert _entries(_armed(8.0, 24.0), c, v) >= _entries(_armed(12.0, 20.0), c, v)


def test_the_band_actually_bites_or_it_guards_nothing():
    c, v = _tape()
    assert _entries(_armed(12.0, 20.0), c, v) < _entries(_mum(), c, v)


# ------------------------------------------------------------ 3 · fail-closed
def test_an_unmeasurable_velocity_refuses_when_armed():
    c, v = _tape()
    assert _entries(_armed(12.0, 20.0, lookback=10 ** 6), c, v) == 0


def test_an_unmeasurable_velocity_is_ignored_when_inert():
    """Fail-closed applies to the GATE, not to the unarmed rule — otherwise
    shipping the lever would silently halve a live book."""
    c, v = _tape()
    st = _armed(-999.0, 999.0, lookback=10 ** 6)
    assert _entries(st, c, v) == _entries(_mum(), c, v)


# ------------------------------------------------- 4 · the live arm is safe
def test_the_live_lever_is_judge_owned():
    src = Path(ROOT, "fleet_tuning.py").read_text()
    assert '"live.mum.": "experiment-judge"' in src, (
        "the live.mum.* prefix is no longer bound to the judge — the band "
        "could be written to a real-money book by another author")
    for k in ("live.mum.vel_lo", "live.mum.vel_hi"):
        assert ft.LEVERS[k]["lane"] == "lighter-live"
    for k in ("xp.mum.vel_lo", "xp.mum.vel_hi"):
        assert ft.LEVERS[k]["lane"] == "lighter-xp"


def test_the_cages_only_reach_toward_the_measured_band():
    """The rail may TIGHTEN toward what was measured and never past it."""
    assert ft.LEVERS["xp.mum.vel_lo"]["hi"] <= 20.0
    assert ft.LEVERS["xp.mum.vel_hi"]["lo"] >= 8.0


# ---------------------------------------------------------- 5 · the census
def test_an_armed_band_is_visible_in_the_census():
    c, v = _tape()
    st = _armed(12.0, 20.0)
    blocked = opened = 0
    for k in range(st.min_bars, len(c)):
        sig = st.signals({"c": c[:k + 1], "h": c[:k + 1],
                          "l": c[:k + 1], "v": v[:k + 1]}, {})
        if sig and sig.get("enter"):
            opened += 1
        elif fb.census_no_entry_why(st, sig) == "vel_blocked":
            blocked += 1
    assert blocked > 0 and opened > 0, (blocked, opened)
    assert blocked + opened == _entries(_mum(), c, v), (
        "the census does not account for every entry the band removed")


def test_the_inert_default_never_reports_vel_blocked():
    c, v = _tape()
    st = _mum()
    for k in range(st.min_bars, len(c)):
        sig = st.signals({"c": c[:k + 1], "h": c[:k + 1],
                          "l": c[:k + 1], "v": v[:k + 1]}, {})
        assert fb.census_no_entry_why(st, sig) != "vel_blocked"


def test_velocity_is_published_whether_or_not_the_band_is_armed():
    c, v = _tape()
    st = _mum()
    seen = [st.signals({"c": c[:k + 1], "h": c[:k + 1], "l": c[:k + 1],
                        "v": v[:k + 1]}, {}) for k in range(st.min_bars, len(c))]
    vels = [s["vel"] for s in seen if s and s.get("vel") is not None]
    assert len(vels) > 50 and min(vels) < 0 < max(vels), (
        "vel is not published on the unarmed path — the distribution she "
        "draws from would be unobservable until someone armed the band")


# ------------------------------------------------------- the lever consumer
def test_the_consumer_carries_the_band_and_keeps_max_hold_an_int():
    """(xl) generalised the setattr cast. The old form branched on the attr
    NAME (`val if attr == "RSI_MAX" else int(val)`), which would have made
    every new float lever an INT — vel_lo 12.5 -> 12."""
    st = copy.copy(_mum())
    fb.apply_book_levers(st, "xp.mum.")
    assert isinstance(st.MAX_HOLD_MIN, int)
    assert isinstance(st.VEL_LO, float) and isinstance(st.VEL_HI, float)
    names = {b for b, _a, _c in fb.MUM_LEVER_ATTRS}
    assert {"vel_lo", "vel_hi"} <= names
    for bar, _attr, _cast in fb.MUM_LEVER_ATTRS:
        assert f"xp.mum.{bar}" in ft.LEVERS, f"{bar} is consumed but unregistered"


def test_a_fractional_band_survives_the_cast():
    st = copy.copy(_mum())
    st.VEL_LO = 12.5
    assert st.VEL_LO == 12.5, "a float lever was truncated to an int"


def test_env_defaults_are_reread_from_the_class_so_expiry_reverts_clean():
    st = copy.copy(_mum())
    st.VEL_LO, st.VEL_HI = 12.0, 20.0
    d = fb.mum_env_defaults(st)
    assert d["vel_lo"] <= -900.0 and d["vel_hi"] >= 900.0, (
        "mum_env_defaults read the MUTATED instance — a lever expiry would "
        "leave the band armed forever")


def test_the_registry_default_matches_the_class_attribute_it_describes():
    """THE DRIFT ARM FOR MUM'S LEVERS, because `audit_lever_bounds` cannot
    reach them.

    That audit drift-checks a lever by reading the ENV VAR its consumer calls
    `os.environ.get` on. Every one of mum's four levers defaults from a CLASS
    ATTRIBUTE on her carrier instead, so all four sit outside the map and a
    registry default could drift from the code silently — the `(hl)` hole,
    verified present: mutating `xp.mum.vel_lo`'s `env_default` to 5.0 leaves
    `audit_lever_bounds` green. This closes it for all four, not just the two
    (xl) added, so a registry that misdescribes what mum actually runs cannot
    reach main.
    """
    cls = type(_mum())
    for bar, attr, _cast in fb.MUM_LEVER_ATTRS:
        want = float(getattr(cls, attr))
        for lane in ("xp", "live"):
            key = f"{lane}.mum.{bar}"
            assert key in ft.LEVERS, f"{key} is consumed but not registered"
            got = float(ft.LEVERS[key]["env_default"])
            assert got == want, (
                f"{key} env_default {got} but the carrier runs {attr}={want} — "
                "every organ reasoning about her headroom reasons from the "
                "wrong number")
            lo, hi = ft.LEVERS[key]["lo"], ft.LEVERS[key]["hi"]
            assert lo <= want <= hi, f"{key} default {want} outside cage [{lo},{hi}]"
