"""[2026-09-02] THE JUDGE'S SERIAL LANE COULD NOT PROMOTE, BY CONSTRUCTION.

`implementation_shortfall.arm_drift` claims "ARMS ON DIFFERENT CODE" whenever
the two arms' `extra.build` differ, and `experiment_judge.paired_eval` returns
on that claim BEFORE any floor or gap logic — so a drift claim is a hard block
on promotion.

That guard was SOUND for the lane it was built on: 💸 the Farmer's two arms both
ran `lighter_funding_bot.py`, one entry file in two services, so converged arms
stamped IDENTICALLY and a difference really did mean one arm was behind.

(ww) moved the lane to 👩 mum, whose arms run DIFFERENT ENTRY FILES in different
images. Measured on the live feed and reproduced here from the Dockerfiles: the
family shadow image hashes 16 files, the live host 17, and the shadow's set is a
strict SUBSET — the only difference is the live entry `lighter_avo_live_bot.py`.
`build` hashes name+bytes of every file in the set, so the two ids can NEVER be
equal at any commit. The judge therefore refused every mum evaluation with
"ARMS ON DIFFERENT CODE" and would have done so forever.

THE FIX, two halves, both pinned here:
  * `bot_pnl_store.build_shared_compute` hashes `_BUILD_SHARED` ALONE (entry
    excluded). That tuple is one fleet-wide constant, so the id is comparable
    ACROSS images by construction: same shared files at the same commit -> equal.
  * `arm_drift` prefers `build_shared`; falls back to `build` only when
    `build_n` MATCHES, because a different count is a different FILE SET and two
    ids over different sets are not comparable ((fd)) — the same fail-safe
    direction the sensor already takes on an unstamped arm.

DECLARED BLIND SPOT (asserted below so it cannot be forgotten): drift confined
to a live-only entry module is invisible to the shared stamp. `build`/`build_n`
stay published and `audit_code_currency` resolves per row.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bot_pnl_store as store            # noqa: E402
import implementation_shortfall as isf   # noqa: E402

pytestmark = pytest.mark.autonomy

LIVE, SHADOW = "freqtrade-mum-lighter", "freqtrade-mum-lshadow"


def _row(bot, **extra):
    return {"bot": bot, "extra": dict(extra)}


def _copy_set(dockerfile):
    """The .py names an image COPYs — read from the Dockerfile, never retyped."""
    txt = (ROOT / dockerfile).read_text().replace("\\\n", " ")
    names = []
    for m in re.finditer(r"^COPY\s+(.*)$", txt, re.M):
        names += [p for p in m.group(1).split() if p.endswith(".py")]
    return names


# ── the premise: the two images really do carry different file sets ──────────

def test_the_two_arms_images_carry_different_file_sets():
    """The measurement the whole fix rests on, taken from the Dockerfiles."""
    live = set(_copy_set("Dockerfile.avolive"))
    shadow = set(_copy_set("Dockerfile.familyshadow"))
    assert "lighter_avo_live_bot.py" in live
    assert "lighter_avo_live_bot.py" not in shadow
    # the shadow's modules are all carried by the live image too — the live
    # image is the SUPERSET, so its `build` can never equal the shadow's
    assert shadow <= live, sorted(shadow - live)


def test_the_shared_tuple_is_one_fleet_wide_constant():
    """`build_shared` is comparable across images only because this tuple is
    the same everywhere. A per-image shared set would silently reintroduce the
    bug this file exists to close."""
    assert isinstance(store._BUILD_SHARED, tuple)
    assert "lighter_family_bot.py" in store._BUILD_SHARED
    # the LIVE entry must NOT be in it, or the stamp stops being cross-image
    # comparable (it would be absent from every other image's set)
    assert "lighter_avo_live_bot.py" not in store._BUILD_SHARED


# ── the stamp ────────────────────────────────────────────────────────────────

def test_the_shared_stamp_excludes_the_entry_module(tmp_path, monkeypatch):
    """Drive the real hasher over two synthetic images: one with an extra entry
    file, one without. `build` must differ and `build_shared` must AGREE — that
    single asymmetry is the entire fix."""
    shared = {"lighter_family_bot.py": b"family\n", "bot_pnl_store.py": b"store\n",
              "fleet_bus.py": b"bus\n", "fleet_tuning.py": b"tuning\n",
              "funding_basis.py": b"basis\n"}
    ids = {}
    for name, extra in (("shadow", {}), ("live", {"lighter_avo_live_bot.py": b"live\n"})):
        d = tmp_path / name
        (d / "venues").mkdir(parents=True)
        (d / "venues" / "__init__.py").write_bytes(b"v\n")
        for f, body in {**shared, **extra}.items():
            (d / f).write_bytes(body)
        monkeypatch.setattr(store, "_BUILD_ROOT", str(d))
        entry = str(d / ("lighter_avo_live_bot.py" if extra else "lighter_family_bot.py"))
        ids[name] = (store.build_compute(entry), store.build_shared_compute())

    (lb, ln), (ls_, lsn) = ids["live"]
    (sb, sn), (ss, ssn) = ids["shadow"]
    assert ln == sn + 1, "premise: the live image carries exactly one more file"
    assert lb != sb, "build MUST differ — that is the defect, not the fix"
    assert ls_ == ss and ls_ is not None, "build_shared must agree across images"
    assert lsn == ssn == sn


def test_every_publish_carries_the_shared_stamp():
    """The sensor can only prefer a stamp the publisher writes."""
    out = store._stamp_build({})
    assert out.get("build_shared"), out
    assert out.get("build_shared_n"), out
    # and it never overwrites a caller's own key
    assert store._stamp_build({"build_shared": "mine"})["build_shared"] == "mine"


# ── the sensor ───────────────────────────────────────────────────────────────

def test_a_converged_cross_image_pair_is_not_drift():
    """THE INCIDENT: mum's arms, same commit, different images. Before the fix
    this returned a claim on every sample and blocked every promotion."""
    rows = [_row(LIVE, build="02ef7b39f9ac", build_n=17,
                 build_shared="aa629492ce4e", build_shared_n=16),
            _row(SHADOW, build="aa629492ce4e", build_n=16,
                 build_shared="aa629492ce4e", build_shared_n=16)]
    assert isf.arm_drift(rows, live=LIVE, shadow=SHADOW) is None


def test_a_genuinely_stale_cross_image_arm_is_still_caught():
    """The guard must keep its teeth: an arm behind on SHARED code still claims."""
    rows = [_row(LIVE, build="02ef", build_n=17, build_shared="aa62", build_shared_n=16),
            _row(SHADOW, build="old0", build_n=16, build_shared="bbbb", build_shared_n=16)]
    d = isf.arm_drift(rows, live=LIVE, shadow=SHADOW)
    assert d and d["live"] == "aa62" and d["shadow"] == "bbbb"
    assert d.get("basis") == "shared"


def test_a_same_image_pair_keeps_the_original_behaviour():
    """No regression on the Farmer shape — one entry file, two services."""
    same = [_row(LIVE, build="aaaa", build_n=16), _row(SHADOW, build="aaaa", build_n=16)]
    drift = [_row(LIVE, build="aaaa", build_n=16), _row(SHADOW, build="bbbb", build_n=16)]
    assert isf.arm_drift(same, live=LIVE, shadow=SHADOW) is None
    d = isf.arm_drift(drift, live=LIVE, shadow=SHADOW)
    assert d and d["live"] == "aaaa" and d["shadow"] == "bbbb"


def test_mismatched_counts_are_not_comparable_during_rollout():
    """Before both arms publish the shared stamp, differing ids over differing
    SETS are not evidence of anything ((fd)). Fail-safe toward silence — the
    same direction the sensor already takes on an unstamped arm."""
    rows = [_row(LIVE, build="02ef", build_n=17), _row(SHADOW, build="aa62", build_n=16)]
    assert isf.arm_drift(rows, live=LIVE, shadow=SHADOW) is None


def test_absence_still_never_claims():
    """Unchanged contract: unknown is not drift."""
    assert isf.arm_drift([_row(LIVE, build="a"), _row(SHADOW)],
                         live=LIVE, shadow=SHADOW) is None
    assert isf.arm_drift([_row(LIVE)], live=LIVE, shadow=SHADOW) is None


def test_the_blind_spot_is_declared_not_hidden():
    """A live-only entry module is outside the shared set, so drift confined to
    it is invisible here. That is a real limit and must stay written down."""
    src = (ROOT / "bot_pnl_store.py").read_text()
    fn = src[src.index("def build_shared_compute"):]
    fn = fn[:fn.index('"""', fn.index('"""') + 3)]
    assert "BLIND SPOT" in fn, "the limit must be declared at the owner"


def test_the_hashing_rule_has_exactly_one_owner():
    """`build_compute` and `build_shared_compute` are compared against each
    other; two copies of the hash loop would let them drift apart ((hj))."""
    src = (ROOT / "bot_pnl_store.py").read_text()
    assert src.count("hashlib.sha256()") == 1, "the digest loop must have one owner"
    for fn in ("def build_compute", "def build_shared_compute"):
        body = src[src.index(fn):]
        body = body[:body.index("\ndef ", 1)]
        assert "_digest(" in body, f"{fn} must go through the one owner"


# ── the ROW half: the path that actually held 👩 mum ─────────────────────────
#
# The live payload named it: last_eval.arm_drift.source == "rows-disjoint".
# `_row_drift` asks whether the arms' in-window BUILD SETS intersect, on the
# (lf) reasoning that intersecting sets mean "the same deploy sequence". That
# premise holds only while both arms draw ids from ONE id space — a cross-image
# pair draws from two, so the sets are disjoint at every commit and the rule
# read "different code" forever.

import experiment_judge as J   # noqa: E402


def _crow(bot, build, n=None, shared=None):
    x = {"build": build}
    if n:
        x["build_n"] = n
    if shared:
        x["build_shared"] = shared
    return {"bot": bot, "close_ts": J.iso(1.7e9), "extra": x}


def test_row_drift_does_not_fire_on_a_converged_cross_image_pair():
    """THE INCIDENT, at the path that produced it."""
    lb, sb = J.LIVE_BOT, J.SHADOW_BOT
    # before the shared stamp deploys: differing counts -> not comparable
    assert J._row_drift([_crow(lb, "02ef", 17), _crow(sb, "aa62", 16)]) is None
    # after it deploys: the shared ids agree -> positively converged
    assert J._row_drift([_crow(lb, "02ef", 17, "ss1"),
                         _crow(sb, "aa62", 16, "ss1")]) is None


def test_row_drift_still_catches_a_genuinely_stale_arm():
    """Teeth kept: an arm behind on SHARED code still claims, and says so."""
    d = J._row_drift([_crow(J.LIVE_BOT, "02ef", 17, "ss1"),
                      _crow(J.SHADOW_BOT, "aa62", 16, "ss0")])
    assert d and d["basis"] == "shared" and d["source"] == "rows-disjoint"


def test_row_drift_keeps_both_of_the_lf_cases():
    """No regression on the rule (lf) shipped, for the pair it was shipped on:
    disjoint sets in ONE image are drift; a rolling deploy is not."""
    lb, sb = J.LIVE_BOT, J.SHADOW_BOT
    assert J._row_drift([_crow(lb, "A", 16), _crow(sb, "B", 16)]), "disjoint = drift"
    assert J._row_drift([_crow(lb, "A", 16), _crow(lb, "B", 16),
                         _crow(sb, "A", 16), _crow(sb, "B", 16)]) is None
