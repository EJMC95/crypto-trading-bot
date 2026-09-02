#!/usr/bin/env python3
"""[2026-08-27 (uk)] A RETIRED ARM HAS NO EXECUTION TO DIVERGE FROM.

**Eamon, 27-Aug: "Fix the funding farmer issue".**

WHAT IT COST, measured on the live payload before the fix. 💸 the Funding
Farmer's live arm was retired 22-Aug `(ta)` and flattened — its last four
closes are the retirement itself (`short_retired` on ETH/BTC/SOL/XAU at
04:01–04:02Z), four forced market exits booked at whatever the book was down.
`market_context`'s divergence check pairs a HARDCODED live row against its
shadow twin over a rolling 7d window, could not tell a retirement from
slippage, and read those four exits as **−2.223pp of "execution divergence"**.

That alert is not advisory. `evidence_board.synthesize_live` consumes any
fresh `live-shadow-gap` as `gap`, and `gap` is **rows-free by design** — so
`if gap or hurt:` restricted EVERY live row:

    live.avo.clip_scale     = 0.75    $352.49 -> $264.37   (-$88.12)
    live.georgia.clip_scale = 0.75    $364.92 -> $273.69   (-$91.23)
    live.mum.clip_scale     = 0.75    $712.51 -> $534.38   (-$178.13)

**$357.48 of real-money clip withheld for five days by a book that had been
flat since 22-Aug** — and 👩 mum, restricted on it, has never taken a trade in
her life. The organ's own execution numbers said the opposite the whole time:
live fills at **0.63bps** slip against shadow's **1.08bps**.

THE SECOND HALF, and the reason this is not merely a stale alert: the window
DRAINS. Seven days after the flatten the alert stops on its own — for a reason
unrelated to any of the three books — and `impl_shortfall` falls to
`insufficient`, which "stays quiet". The fleet's only live-vs-shadow execution
instrument would have gone dark while three live/shadow pairs sat unwatched,
and `insufficient` is byte-identical between "thin week" and "this pair no
longer exists" (the `(lv)` `{open: 0}` ambiguity).

THE FIX IS NOT A NEW RULE. `fleet_bus.RETIRED_LIVE_ARMS` has been the fleet's
one declaration since `(ta)` and `experiment_judge` reads it twice — which is
exactly why 🧪 the judge next door correctly published
`farmer: {phase: "stood_down"}` throughout, while its two neighbours kept
grading a corpse. These two just never asked.

FAIL-SAFE DIRECTION, stated because it is the half that could hurt: an unknown
row is NOT retired, so a typo can never silence a living book's divergence
alert. The loud direction is the safe one here.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_bus as fb                                    # noqa: E402
import implementation_shortfall as isf                    # noqa: E402

LIVE = "perps-funding-lighter-lighter"
SHADOW = "perps-funding-lighter-lshadow"

MC = ROOT / "market_context.py"
DOCKERFILE = ROOT / "Dockerfile.marketcontext"

# The live shape: every ingredient of `live-slipping` — a gap far past
# CLEAN_PP, enough coins, enough closes — on a pair that no longer trades.
SLIPPING = {"ETH": {"live": {"avg_pct": -0.048, "n": 2},
                    "shadow": {"avg_pct": -0.028, "n": 2}},
            "SOL": {"live": {"avg_pct": -0.078, "n": 2},
                    "shadow": {"avg_pct": -0.037, "n": 2}},
            "BTC": {"live": {"avg_pct": -0.023, "n": 2},
                    "shadow": {"avg_pct": -0.008, "n": 2}}}


# ---- 1  impl_shortfall: refuse the verdict, keep the number ---------------

def test_a_retired_arm_is_stood_down_not_slipping():
    live = isf.compute_shortfall(SLIPPING)
    assert live["verdict"] == "live-slipping", "fixture must reproduce the bug"
    ret = isf.compute_shortfall(SLIPPING, retired=True)
    assert ret["verdict"] == "stood_down"


def test_the_number_survives_the_refusal():
    """The arm-drift contract, reused: report the NUMBER, refuse the VERDICT.
    A verdict that also deleted the measurement would make the retirement
    unfalsifiable."""
    live = isf.compute_shortfall(SLIPPING)
    ret = isf.compute_shortfall(SLIPPING, retired=True)
    assert ret["gap_pp"] == live["gap_pp"]
    assert ret["coins"] == live["coins"]
    assert ret["paired_closes"] == live["paired_closes"]


def test_stood_down_outranks_every_other_refusal_including_insufficient():
    """Ranked FIRST on purpose. `insufficient` and `stood_down` are both
    silence; only one of them means STOP WAITING. Since the window drains to
    empty on a retired pair, a lower rank would let the honest verdict be
    masked by the very draining it is meant to explain."""
    thin = {"x": {"live": {"avg_pct": -0.05, "n": 9},
                  "shadow": {"avg_pct": 0.0, "n": 9}}}
    assert isf.compute_shortfall(thin)["verdict"] == "insufficient"
    assert isf.compute_shortfall(thin, retired=True)["verdict"] == "stood_down"
    assert isf.compute_shortfall({}, retired=True)["verdict"] == "stood_down"
    drift = {"live": "a", "shadow": "b"}
    assert isf.compute_shortfall(SLIPPING, drift=drift)["verdict"] == "arm-drift"
    assert isf.compute_shortfall(SLIPPING, retired=True,
                                 drift=drift)["verdict"] == "stood_down"
    assert isf.compute_shortfall(SLIPPING, retired=True,
                                 xp_running=True)["verdict"] == "stood_down"


def test_it_names_the_object_and_the_way_back():
    """I8: a detector whose output is an instruction must name something the
    reader can act on."""
    sd = isf.compute_shortfall(SLIPPING, retired=True)["stood_down"]
    # [(wo)] the organ's CONFIGURED pair, whatever it is — this pinned the
    # Farmer literals, i.e. the exact list-keyed rot (wo) removed: the default
    # pair is now derived from the registry, so the receipt names THAT.
    assert sd["live_bot"] == isf.LIVE and sd["shadow_bot"] == isf.SHADOW
    assert sd["why"] and sd["wake_when"]


def test_neither_the_push_nor_the_proposal_can_fire_while_stood_down():
    """Both actuator paths in run_once ride `streak >= SUSTAIN`, and the
    streak only counts 'live-slipping'. Pinned as a PROPERTY of the verdict so
    a later refactor of run_once cannot re-arm them silently."""
    ret = isf.compute_shortfall(SLIPPING, retired=True)
    assert ret["verdict"] != "live-slipping"
    src = ast.parse((ROOT / "implementation_shortfall.py").read_text())
    fn = next(n for n in ast.walk(src)
              if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    # the streak's only increment condition is the live-slipping comparison
    cmps = [n for n in ast.walk(fn) if isinstance(n, ast.Compare)
            and any(isinstance(c, ast.Constant) and c.value == "live-slipping"
                    for c in n.comparators)]
    assert cmps, "run_once must still gate the streak on 'live-slipping'"


# ---- 2  it is INERT while the arm lives -----------------------------------

def test_a_living_arm_is_untouched():
    """The whole change must be byte-invisible to a live pair — otherwise it
    is not a fix, it is a second behaviour."""
    for fixture, want in ((SLIPPING, "live-slipping"),
                          ({"a": {"live": {"avg_pct": 0.019, "n": 3},
                                  "shadow": {"avg_pct": 0.020, "n": 5}},
                            "b": {"live": {"avg_pct": 0.010, "n": 4},
                                  "shadow": {"avg_pct": 0.011, "n": 4}}},
                           "clean")):
        r = isf.compute_shortfall(fixture)
        assert r["verdict"] == want
        assert "stood_down" not in r


def test_an_unknown_row_is_never_retired():
    """The fail-safe direction. A typo in the table must not silence a living
    book — the dangerous mistake needs the row spelled exactly right, which is
    the direction an error is loud in."""
    assert fb.live_arm_retired("a-row-that-does-not-exist") is False
    assert fb.live_arm_retired(SHADOW) is False, "the control arm still trades"
    assert isf._live_retired("a-row-that-does-not-exist") is False


def test_a_dark_fleet_bus_degrades_to_not_retired(monkeypatch):
    monkeypatch.setattr(isf, "_fb", None)
    assert isf._live_retired(LIVE) is False


# ---- 3  market_context: the wiring, by AST rather than substring ----------

def _mc_tree():
    return ast.parse(MC.read_text())


def test_market_context_imports_the_single_owner():
    """Not a substring check: the import must be a real top-level `import
    fleet_bus`, unguarded like `funding_basis` beside it, so a missing file is
    a LOUD boot failure rather than a silent degrade back to the bug."""
    tree = _mc_tree()
    names = {a.name for n in tree.body if isinstance(n, ast.Import)
             for a in n.names}
    assert "fleet_bus" in names, "top-level `import fleet_bus` is required"


def test_the_divergence_check_asks_before_it_fires():
    """The call must exist, and it must be `fleet_bus.live_arm_retired` — not
    a local re-implementation. A second copy of the retirement table is a
    second rule (the 8x funding bug's shape)."""
    tree = _mc_tree()
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "live_arm_retired"
             and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "fleet_bus"]
    assert calls, "market_context must consult fleet_bus.live_arm_retired"
    src = MC.read_text()
    assert "RETIRED_LIVE_ARMS = {" not in src, \
        "the retirement table must have exactly one owner"


def test_the_skip_is_not_logged_as_a_failure():
    """A deliberate skip surfacing as 'divergence check failed' is the same
    class as a check that inspects nothing and reports clean — the reason it
    did not run IS the finding. The sentinel must be caught above the broad
    handler."""
    tree = _mc_tree()
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
             and any(isinstance(h.type, ast.Name) and h.type.id == "_RetiredArm"
                     for h in n.handlers)]
    assert tries, "the retired-arm sentinel needs its own handler"
    for t in tries:
        kinds = [(h.type.id if isinstance(h.type, ast.Name) else None)
                 for h in t.handlers]
        assert kinds.index("_RetiredArm") < len(kinds) - 1 or \
            "Exception" not in kinds, \
            "_RetiredArm must be caught BEFORE the broad Exception handler"
        if "Exception" in kinds:
            assert kinds.index("_RetiredArm") < kinds.index("Exception")


# ---- 4  born-dark: the import must actually be in the image ---------------

def test_the_marketcontext_image_carries_fleet_bus():
    """market_context now imports fleet_bus UNGUARDED, so a missing COPY is a
    crash-loop on a real service rather than a degraded organ. This is the
    born-dark class the fleet has already paid for three times.

    Reads the COPY DIRECTIVES, not the file text. The first version of this
    test was `"fleet_bus.py" in DOCKERFILE.read_text()` and a mutation round
    proved it VACUOUS: the rationale comment directly above the COPY names
    the file, so deleting it from the COPY left the substring in place and
    the guard green. That is this repo's own "a substring test is NOT a
    wiring test" rule, walked into by the guard written to enforce it."""
    copied = set()
    for line in DOCKERFILE.read_text().splitlines():
        line = line.strip()
        if not line.upper().startswith("COPY "):
            continue
        # `COPY a.py b.py ./` — every token but the directive and the dest
        copied.update(line.split()[1:-1])
    assert "fleet_bus.py" in copied, (
        "Dockerfile.marketcontext must COPY fleet_bus.py — market_context "
        f"imports it unguarded. COPY'd today: {sorted(copied)}")


def test_fleet_bus_brings_no_import_cascade_into_that_image():
    """The COPY is only safe because fleet_bus is stdlib-only at import time.
    If that ever changes, this image needs more than one file and the guard
    should say so here rather than at 3am on a dead service."""
    tree = ast.parse((ROOT / "fleet_bus.py").read_text())
    top = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            top |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            top.add(n.module.split(".")[0])
    assert top <= {"math", "os", "datetime", "json", "time", "sys"}, \
        f"fleet_bus grew a top-level dependency the marketcontext image lacks: {top}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
