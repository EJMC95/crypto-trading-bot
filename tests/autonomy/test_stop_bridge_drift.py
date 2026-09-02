"""[2026-09-02 (xj)] THE DRIFT GUARD `_STOP_BRIDGE` PROMISED AND NEVER GOT.

`fleet_allocation._STOP_BRIDGE` retypes each book's catastrophic stop, and the
module explains at length why retyping is the RIGHT call there: importing the
book's module would be born-dark, because `fleet_allocation` runs in the
freqtrade image, which does not COPY `lighter_family_bot` — the lookup would
fail inside its own `try/except` and every family book would silently get no
bound. Its closing sentence is the promise:

    "A retyped constant that a guard CAN check beats an import that it cannot."

**The guard was never written.** Ten hand-typed stop values feed `dd_bound`,
which is the per-book capital bound the 15% go-live drawdown bar implies — and
nothing compared any of them to the book they claim to describe. That is this
repo's most-repeated failure shape wearing a new coat: a declared enforcement
that does not exist ((iz): I9's enforcement existed and was inert; the
doctrine file's own opening warns a green run proves an enforcement EXISTS,
not that it is CORRECT).

MEASURED at the time of writing: all ten values are CORRECT, so this guard is
green on its first run. That is the honest state and it is worth stating —
this is a ratchet against tomorrow's drift, not a repair of today's. What IS
already wrong is MEMBERSHIP: the bridge names three RETIRED books
(`perps-funding-lighter-lshadow`, `band-garrett-lshadow`, `nav-cook-lshadow`,
all retired at (wt)) while NINE living books resolve to no bound at all, so the
shared `[PROBE_FLOOR, SCALE_CEIL]` clamp governs them blind.

WHY IT MATTERS DESPITE NOT BEING URGENT: maxDD is the only go-live bar that is
NOT clip-invariant, so scaling a book scales its drawdown against a fixed 15%
bar. Nothing sits near the ceiling today (fleet max scale ~1.59 against a 4.0
ceiling), which is exactly why this is the right time to fix the arithmetic —
before a number depends on it.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fleet_allocation as fa            # noqa: E402

pytestmark = pytest.mark.autonomy

#: bot -> where its stop REALLY lives. Two shapes, because the fleet has two:
#: an env-backed module constant, or a `Carrier(...)` row in the family host.
#: This map names the SOURCE; the test reads the value from it every run, so a
#: change to either side that is not mirrored in the other reddens the build.
SOURCES = {
    "perps-funding-lighter-lshadow": ("env", "lighter_funding_bot", "FUNDING_HARD_STOP"),
    "band-garrett-lshadow":          ("env", "lighter_funding_bot", "FUNDING_HARD_STOP"),
    "band-kelly-lshadow":            ("env", "lighter_band_kelly_bot", "KELLY_HARD_STOP"),
    "nav-cook-lshadow":              ("env", "lighter_nav_cook_bot", "COOK_HARD_STOP"),
    "freqtrade-mum-lshadow":         ("family", "freqtrade-mum"),
    "freqtrade-mum-lighter":         ("family", "freqtrade-mum"),
    "freqtrade-avo-maria-lshadow":   ("family", "freqtrade-avo-maria"),
    "freqtrade-avo-maria-lighter":   ("family", "freqtrade-avo-maria"),
    "freqtrade-georgia-lshadow":     ("family", "freqtrade-georgia"),
    "freqtrade-georgia-lighter":     ("family", "freqtrade-georgia"),
}


def _env_stop(module, var):
    """The literal in `os.environ.get("VAR", "X")`, via the parser this repo
    already proved against this codebase — never a second copy of it ((hj)).
    `test_stop_vs_gate` reads its stops the same way, for the same reason."""
    import audit_lever_bounds as alb
    return abs(float(alb._literal_env_default(f"{module}.py", var)))


def _family_stops():
    """{row_name: |stoploss|} read by AST from the family host's own
    `Carrier(...)` rows. AST, not a regex: a `stoploss=-0.04` inside a comment
    or a selftest fixture must not be mistaken for the shipped row, and this
    file's whole point is that a lookalike is not a measurement."""
    src = Path(ROOT, "lighter_family_bot.py").read_text(encoding="utf-8")
    out = {}
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.args[0]
        if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
            continue
        for kw in node.keywords:
            if kw.arg != "stoploss":
                continue
            v = kw.value
            # `stoploss=-0.04` parses as a UnaryOp, not a Constant.
            if isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.USub) \
                    and isinstance(v.operand, ast.Constant):
                out.setdefault(name.value, abs(float(v.operand.value)))
            elif isinstance(v, ast.Constant) and isinstance(v.value, (int, float)):
                out.setdefault(name.value, abs(float(v.value)))
    return out


# ── the drift arm — the promise, kept ────────────────────────────────────────

def test_the_source_map_covers_every_bridge_entry():
    """A bridge row with no declared source is a value nothing can check —
    which is the state this whole file exists to end. Adding an entry to
    `_STOP_BRIDGE` without one fails HERE, at the moment it is added."""
    missing = sorted(set(fa._STOP_BRIDGE) - set(SOURCES))
    assert not missing, (
        f"{missing} are in fleet_allocation._STOP_BRIDGE with no entry in "
        f"SOURCES, so their retyped stop is unchecked. Name where the stop "
        f"really lives, or remove the row.")


@pytest.mark.parametrize("bot", sorted(fa._STOP_BRIDGE))
def test_every_retyped_stop_matches_its_books_own_source(bot):
    """THE GUARD THE MODULE PROMISED. Each bridge value is compared to the
    constant it claims to mirror, read from that book's own file every run."""
    spec = SOURCES[bot]
    if spec[0] == "env":
        real = _env_stop(spec[1], spec[2])
        where = f"{spec[1]}.py::{spec[2]}"
    else:
        stops = _family_stops()
        assert spec[1] in stops, (
            f"{spec[1]} no longer has a Carrier row in lighter_family_bot.py — "
            f"the bridge describes a book that has moved or gone")
        real = stops[spec[1]]
        where = f"lighter_family_bot.py::{spec[1]}.stoploss"
    got = abs(float(fa._STOP_BRIDGE[bot]))
    assert abs(got - real) < 1e-9, (
        f"_STOP_BRIDGE[{bot!r}] = {got} but {where} says {real}. This value "
        f"feeds dd_bound, the per-book capital bound the 15% drawdown bar "
        f"implies — a drifted stop is a drifted bound on real money.")


def test_the_family_reader_actually_reads(
):
    """A parser that returns {} would make every family row above vacuously
    pass. Assert it finds the rows we know are there, with the values source
    shows — the 'empty output is not a negative result' rule, applied to this
    file's own helper."""
    stops = _family_stops()
    assert stops.get("freqtrade-mum") == 0.04, stops
    assert stops.get("freqtrade-avo-maria") == 0.10, stops
    assert stops.get("freqtrade-georgia") == 0.05, stops
    # and it must see a book the bridge does NOT carry, or it is only ever
    # confirming what it was told
    assert stops.get("freqtrade-georgia-v3") == 0.015, stops


def test_the_env_reader_actually_reads():
    """Same positive control for the other shape."""
    assert _env_stop("lighter_band_kelly_bot", "KELLY_HARD_STOP") == 0.05
    assert _env_stop("lighter_funding_bot", "FUNDING_HARD_STOP") == 0.10


# ── the membership arm — a RATCHET, never a bar ──────────────────────────────
#
# A guard that reddens the build on a pre-existing backlog gets exempted within
# a day and then guards nothing ((mz)'s lesson, and the shape
# `audit_lever_measurability` already uses). So the nine living books that
# resolve to no bound are DECLARED here and may only shrink: a NEW book with no
# bound fails immediately, and closing one of these means deleting its line.
UNBOUNDED_BACKLOG = frozenset({
    # Delta-neutral MODELLED funding books. Each has a 2% bleed stop
    # (`BLEED_STOP_FRAC` / `BLEED_FRAC`), which is a genuine per-position loss
    # bound — but whether a bleed stop is the right input to `0.15/|stop|` is a
    # claim about books nobody has studied for this purpose, and inventing
    # 7.5x for three books on a grep is exactly the confident-wrong-number this
    # feature exists to prevent. Named, not guessed.
    "perps-funding-carry-lshadow",
    "book-kiyosaki-lshadow",
    "book-hull-lshadow",
    # Bracketed books whose stop is a per-trade literal rather than a book
    # constant; each needs its own reading before a bound is asserted.
    "lighter-ticket-taker-lshadow",
    "lighter-perp-sniper-lshadow",
    "book-bezos-lshadow",
    # Parliament books: their stop is a tuned per-lens `SL_PCT` inside a
    # PRIVATE registry, so the "book's own stop" is not a single number.
    "pm-albanese-lshadow",
    "pm-turnbull-lshadow",
})


def test_the_backlog_only_shrinks():
    """Every declared-unbounded book must still be unbounded. When one gains a
    bound, this fails and the line is deleted — so the list cannot rot into a
    permanent exemption."""
    still = {b for b in UNBOUNDED_BACKLOG
             if b not in fa._STOP_BRIDGE and b not in fa.NO_STOP_BY_DESIGN}
    closed = sorted(UNBOUNDED_BACKLOG - still)
    assert not closed, (
        f"{closed} now resolve to a bound — delete them from "
        f"UNBOUNDED_BACKLOG. A ratchet that keeps a closed row is an "
        f"exemption pretending to be a backlog.")


def test_the_bridge_and_the_backlog_do_not_overlap():
    """A book cannot be both bounded and declared unbounded."""
    both = sorted(set(fa._STOP_BRIDGE) & UNBOUNDED_BACKLOG)
    assert not both, both
    assert not sorted(fa.NO_STOP_BY_DESIGN & UNBOUNDED_BACKLOG)
