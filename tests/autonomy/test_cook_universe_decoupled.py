"""🧭 nav-cook — the universe WIDTH is this book's own knob (2026-08-26).

THE HAZARD THIS CLOSES, and it is a correctness one rather than a tidiness
one. `lighter_nav_cook_bot.resolve_universe` used to pass
`ghost.UNIVERSE_N` — the RETIRED dislocation module's constant — and
`lighter_band_kelly_bot` reads **the same constant**. So one edit intended to
widen Cook would have silently widened 🪁 band-kelly too: a book days into a
30-day (hm) window whose measured verdict is NO CHANGE, where a policy move
forfeits the whole sample. Two books, one knob, and nothing in either file
said so.

WHAT IS PINNED HERE
  1. **NO BEHAVIOUR CHANGE TODAY.** At the shipped default Cook's resolved
     universe is byte-identical to the old ghost-constant path — both driven
     through the ghost's REAL resolver over one deterministic bus, and
     compared. This is the claim the change rests on, so it is measured, not
     asserted.
  2. **THE ENV VAR REACHES THE RESOLVE SITE.** Proved twice over: by AST (the
     width argument is Cook's own `UNIVERSE_N`, not `ghost.UNIVERSE_N`) and
     end-to-end by RELOADING the module under a set `COOK_UNIVERSE_N` and
     observing the width the resolver is actually handed.
  3. **band-kelly IS UNAFFECTED.** Its resolve site still reads
     `ghost.UNIVERSE_N` (deliberate — its mirror contract imports the ghost's
     config wholesale), the ghost's constant does not move, and driving
     band-kelly's own resolver across a change in Cook's width returns an
     identical list.
  4. **BOTH WIDTHS ARE PUBLISHED**, so a future divergence is readable off the
     row instead of inferred from two source files.

NON-VACUITY IS THE WHOLE POINT of arm 3: a decoupling test that never moves
the knob would pass against the coupled code it was written to forbid. Every
arm here either drives a real function or reads a real AST node.

Mutation round (2026-08-26), all RED:
  * width argument reverted to `ghost.UNIVERSE_N`
  * the default changed from the ghost's value (40 -> 12)
  * `caps["universe_n"]` re-pointed at `ghost.UNIVERSE_N`
  * `ghost_universe_n` dropped from `caps`
"""
from __future__ import annotations

import ast
import importlib
import os
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_nav_cook_bot as cook                # noqa: E402
import lighter_band_kelly_bot as kelly             # noqa: E402
import lighter_dislocation_bot as ghost            # noqa: E402

COOK_SRC = ROOT / "lighter_nav_cook_bot.py"
KELLY_SRC = ROOT / "lighter_band_kelly_bot.py"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
class _FakeBus:
    """A deterministic stand-in for the scout, so the ghost's REAL resolver
    runs offline and its output depends on exactly one thing: the width."""

    def __init__(self, n=200):
        self._syms = ["FAKE%03d" % i for i in range(n)]

    def scout_universe(self, min_vol_m=0.0, current_time=None):
        return list(self._syms)


class _VolFakeBus:
    """A bus that RESPECTS the floor, so the floor argument has CONSEQUENCE.

    `_FakeBus` accepts `min_vol_m` and ignores it, which makes that argument
    unobservable — a stub encoding the assumption under test. Measured: with
    only that stub, replacing `MIN_VOL_M` with `0.0` at the resolve site (the
    very line the decoupling rewrote) survives the whole suite.

    Thin books sort FIRST here, so a lowered floor lets them take the width
    and the resolved list visibly changes.
    """

    THIN = ["THIN%03d" % i for i in range(60)]
    FAT = ["FAT%03d" % i for i in range(200)]

    def __init__(self, floor=0.5):
        self._floor = floor
        self.floors = []

    def scout_universe(self, min_vol_m=0.0, current_time=None):
        self.floors.append(min_vol_m)
        thin = list(self.THIN) if min_vol_m < self._floor else []
        return thin + list(self.FAT)


def _resolve_fn(tree, name="resolve_universe"):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError("no %s()" % name)


def _ghost_resolve_call(fn):
    """The `ghost.resolve_universe(...)` call node inside `fn`."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr == "resolve_universe"
                and isinstance(f.value, ast.Name) and f.value.id == "ghost"):
            return node
    raise AssertionError("no ghost.resolve_universe(...) call in %s" % fn.name)


@pytest.fixture
def fake_bus(monkeypatch):
    bus = _FakeBus()
    monkeypatch.setattr(ghost, "fleet_bus", bus)
    return bus


# --------------------------------------------------------------------------
# 1 · no behaviour change at the default
# --------------------------------------------------------------------------
def test_at_the_default_cook_resolves_exactly_what_the_ghost_constant_did(fake_bus):
    """Drive BOTH paths and compare. This is the change's whole claim."""
    old_path = ghost.resolve_universe(list(ghost.COINS), ghost.UNIVERSE_N,
                                      cook.MIN_VOL_M)
    new_path = cook.resolve_universe([])

    assert new_path == old_path, (
        "the decoupling moved the book: ghost-constant path %r vs cook %r"
        % (old_path[:5], new_path[:5]))

    # ...and non-degenerately: the width must actually BIND, or two paths that
    # both returned the bare configured list would compare equal for free.
    assert len(new_path) == cook.UNIVERSE_N > len(ghost.COINS), (
        "the fake bus must supply more names than the width, so the width is "
        "what truncates: n=%d width=%d configured=%d"
        % (len(new_path), cook.UNIVERSE_N, len(ghost.COINS)))


def test_the_shipped_default_is_the_ghosts_own_value(fake_bus):
    """A default that drifts from the ghost's IS a behaviour change, silently.

    The decoupling is only "no change today" while the two agree; the day
    someone moves Cook's width deliberately, this is the line they edit and
    the changelog entry they owe.
    """
    assert cook.UNIVERSE_N == ghost.UNIVERSE_N == 40


def test_held_coins_still_ride_along(fake_bus):
    """The (hk) orphan rule survives the change: a held coin outside the
    resolved list keeps its exit, its stop and its clock."""
    out = cook.resolve_universe(["ZZZHELD"])
    assert out[-1] == "ZZZHELD" and len(out) == cook.UNIVERSE_N + 1


# --------------------------------------------------------------------------
# 2 · the knob reaches the resolve site
# --------------------------------------------------------------------------
def test_the_resolve_site_passes_cooks_own_width_by_ast():
    """AST, not a substring scan — a page-wide `in` check passes on a comment,
    and this file's comments talk about `ghost.UNIVERSE_N` at length."""
    call = _ghost_resolve_call(_resolve_fn(ast.parse(COOK_SRC.read_text())))
    width = call.args[1]

    assert isinstance(width, ast.Name) and width.id == "UNIVERSE_N", (
        "the width must be this module's own UNIVERSE_N, got %s"
        % ast.dump(width))
    assert not (isinstance(width, ast.Attribute)
                and getattr(width.value, "id", None) == "ghost"), \
        "cook must not resolve against the ghost's shared constant"


def test_the_resolve_site_still_passes_the_books_own_volume_floor(monkeypatch):
    """The width is not the only argument on the line the decoupling rewrote.

    `MIN_VOL_M` is load-bearing rather than cosmetic: `(qq)` measured the
    fleet's own fills at a MEAN 17.49bps and a p90 of 398bps below $0.1M,
    against a band whose founding edge is +0.367%/trade (~37bps). So a
    fat-finger that zeroed this argument would admit books whose slippage
    exceeds the whole edge — silently, because the book would still trade.

    Driven against a bus that HONOURS the floor, so this is a claim about
    consequence and not merely about which name appears at a call site.
    """
    bus = _VolFakeBus()
    monkeypatch.setattr(ghost, "fleet_bus", bus)

    at_floor = cook.resolve_universe([])
    assert bus.floors == [cook.MIN_VOL_M], (
        "the resolve site must hand over THIS book's floor, saw %r"
        % (bus.floors,))
    assert cook.MIN_VOL_M == 0.5 > 0.0, (
        "the shipped $0.5M floor is the (qq)-measured one; a drift to zero is "
        "the hazard this test exists for, not a tuning detail")
    assert not any(s.startswith("THIN") for s in at_floor)

    # ...and NON-DEGENERATELY: lower the floor and the resolved list moves.
    monkeypatch.setattr(cook, "MIN_VOL_M", 0.0)
    lowered = cook.resolve_universe([])
    assert any(s.startswith("THIN") for s in lowered) and lowered != at_floor, (
        "the fake bus must let the floor bind, or any value passes for free")


def test_the_env_var_reaches_the_resolve_site_end_to_end(monkeypatch):
    """Reload the module with COOK_UNIVERSE_N set and observe the width the
    resolver is actually handed. This is what proves the env NAME is right —
    an AST check cannot see a typo'd `os.environ.get` key."""
    seen = []

    def _rec(configured, width, min_vol_m, current_time=None):
        seen.append(width)
        return ["AAA"]

    monkeypatch.setenv("COOK_UNIVERSE_N", "57")
    try:
        reloaded = importlib.reload(cook)
        assert reloaded.UNIVERSE_N == 57
        monkeypatch.setattr(ghost, "resolve_universe", _rec)
        reloaded.resolve_universe([])
        assert seen == [57], (
            "COOK_UNIVERSE_N must reach the resolve site, saw %r" % (seen,))
    finally:
        monkeypatch.delenv("COOK_UNIVERSE_N", raising=False)
        importlib.reload(cook)

    assert cook.UNIVERSE_N == 40, "the reload must restore the shipped default"


# --------------------------------------------------------------------------
# 3 · the decoupling itself — and band-kelly is untouched
# --------------------------------------------------------------------------
def test_moving_cooks_width_moves_cook_and_not_the_ghost(fake_bus, monkeypatch):
    """THE DECOUPLING, driven. Without this arm the suite would pass against
    the coupled code it exists to forbid."""
    before = cook.resolve_universe([])
    ghost_before = ghost.UNIVERSE_N

    monkeypatch.setattr(cook, "UNIVERSE_N", ghost_before + 25)
    after = cook.resolve_universe([])

    assert len(after) == ghost_before + 25 != len(before), (
        "Cook's own knob must move Cook's width: %d -> %d"
        % (len(before), len(after)))
    assert ghost.UNIVERSE_N == ghost_before, (
        "moving Cook's width must NOT move the ghost's constant — "
        "band-kelly resolves against it")


def test_band_kelly_is_unaffected_by_cooks_width(fake_bus, monkeypatch):
    """Drive band-kelly's OWN resolver either side of a change in Cook's
    width. Its scan is the thing a shared constant would have moved."""
    monkeypatch.setattr(kelly, "fleet_bus", None)   # skip its class screen

    before, _ = kelly.resolve_universe(())
    monkeypatch.setattr(cook, "UNIVERSE_N", ghost.UNIVERSE_N + 25)
    after, _ = kelly.resolve_universe(())

    assert after == before, (
        "band-kelly's scan moved with Cook's knob — the two are still coupled")
    assert len(before) == ghost.UNIVERSE_N


def test_band_kelly_still_reads_the_ghosts_constant_deliberately():
    """Its mirror contract imports the ghost's config wholesale, so this is
    the DESIGN, recorded so a later 'consistency' edit does not quietly change
    a book mid-window. If band-kelly ever gets its own width, that is a policy
    decision with its own entry — and this test is where it is declared."""
    call = _ghost_resolve_call(_resolve_fn(ast.parse(KELLY_SRC.read_text())))
    width = call.args[1]

    assert isinstance(width, ast.Attribute) and width.attr == "UNIVERSE_N" \
        and getattr(width.value, "id", None) == "ghost", ast.dump(width)


def test_the_registered_lever_reaches_neither_book():
    """I18, stated executably: `disloc.universe_n` is registered and caged and
    is applied ONLY by the retired ghost's own `apply_tuning`, which never runs
    because that bot is idled. So the cage is not a control on either book's
    width, and nobody should reason as though it were."""
    import fleet_tuning

    assert "disloc.universe_n" in fleet_tuning.LEVERS

    for src in (COOK_SRC, KELLY_SRC):
        tree = ast.parse(src.read_text())
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "apply_tuning" not in names, (
            "%s consumes a tuning lane — this book's env-only (hm) clock "
            "claim, and this test's premise, would both be false" % src.name)


# --------------------------------------------------------------------------
# 4 · both widths reach the row
# --------------------------------------------------------------------------
def test_caps_publishes_both_widths_as_separate_numbers():
    """`{universe_n: 40}` alone is byte-identical between 'Cook's own width'
    and 'the constant it shares with another book'. The row is where that
    stops being ambiguous."""
    caps = cook.build_extra({"scanned": 0}, {}, [], 0.0, 0.0)["caps"]

    assert caps["universe_n"] == cook.UNIVERSE_N
    assert caps["ghost_universe_n"] == ghost.UNIVERSE_N


def test_caps_universe_n_follows_cooks_knob(monkeypatch):
    """Published-but-inert is the failure this pins: a caps field wired to the
    ghost's constant would look right today and lie the moment Cook moves."""
    monkeypatch.setattr(cook, "UNIVERSE_N", 61)
    caps = cook.build_extra({"scanned": 0}, {}, [], 0.0, 0.0)["caps"]

    assert caps["universe_n"] == 61
    assert caps["ghost_universe_n"] == ghost.UNIVERSE_N != 61
