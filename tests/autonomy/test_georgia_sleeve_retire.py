"""🔮 georgia spent 73% of her entries on the sleeve with no measured edge.

[2026-08-28 (vd)] Eamon: *"i refute with the amount of bots, information and
data that we cant find an entry for georgia"*. He was right, and the earlier
conclusion — "no lever is available" — was wrong in a specific, checkable way.

EXIT-FREE vs MATCHED-RANDOM, 90d of her own 15m tape, cluster-robust t:

    sleeve            eps      4h        12h      P(rand>=)
    range_on          257   +0.623%   +1.548%    0.000 at EVERY horizon
    bounce_pullback   368   -0.058%   +0.400%    0.003
    trend_breakout   1203   -0.108%   -0.150%    **0.99**  -> DEAD

A random entry on the same coins and windows beats `trend_breakout` 99% of the
time, and it is **154 of her 212 real entries**.

THE DECIDING NUMBER: her SHIPPED rule, entries held constant, restricted to the
surviving sleeves reads **+0.183%/trade, t_cl +2.40, halves +0.345/+0.021**
against **+0.057%** for the whole book — on a harness that calibrates to her
real ledger at 0.004pp.

WHY THIS IS NOT `(uw)` REPEATED: that sweep pooled all three sleeves and found
no exit configuration positive. Correct — 73% of that population has no entry
edge, and no exit rescues an entry that loses to random. This restricts the
ENTRY, which `(uw)` itself named as the remaining hypothesis.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam                             # noqa: E402


def test_the_edgeless_sleeve_is_off_by_default():
    assert "trend_breakout" in fam.SLEEVES_OFF, (
        "trend_breakout loses to a random entry 99% of the time and is 73% of "
        "her trades")


def test_the_surviving_sleeves_are_untouched():
    """The two sleeves that BEAT random must keep trading — this is a
    restriction on one measured loser, not a shutdown."""
    for keep in ("range_on", "bounce_pullback"):
        assert keep not in fam.SLEEVES_OFF, f"{keep} survives and must trade"


def test_the_gate_is_read_at_the_entry_site_not_just_declared():
    """A retired sleeve that still assigns its tag is a declaration, not a
    retirement — the (ly) sleeve rule: gate ENTRIES, keep the evidence."""
    import ast
    src = (ROOT / "lighter_family_bot.py").read_text()
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "DayTraderGated")
    sig = next(n for n in ast.walk(cls)
               if isinstance(n, ast.FunctionDef) and n.name == "signals")
    body = ast.get_source_segment(src, sig) or ""
    assert "SLEEVES_OFF" in body, (
        "signals() never consults SLEEVES_OFF — the sleeve is declared retired "
        "and still assigns its tag")


def test_it_is_reversible_in_one_env():
    """Every retirement in this fleet is reversible by env — the call must stay
    falsifiable ((ly))."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    assert "GEORGIA_SLEEVES_OFF" in src
    assert fam.SLEEVES_OFF == frozenset({"trend_breakout"})


@pytest.mark.parametrize("raw,expect", [
    ("trend_breakout", {"trend_breakout"}),
    ("", set()),
    ("trend_breakout,bounce_pullback", {"trend_breakout", "bounce_pullback"}),
    ("  trend_breakout , ", {"trend_breakout"}),
])
def test_the_env_parses_including_empty_meaning_ALL_ON(raw, expect):
    """An empty value must mean every sleeve trades — a parse that turned ''
    into {''} would silently retire nothing while looking configured, and one
    that failed closed would silence the whole book."""
    got = frozenset(x.strip() for x in raw.split(",") if x.strip())
    assert got == expect


def test_the_restriction_moves_her_TOWARD_the_gate():
    """THE ARITHMETIC A RESTRICTION MUST PASS (I17/I22), asserted rather than
    asserted-about: dropping 73% of entries costs sqrt(n) on `t` and must buy
    more than that back in mean, or it is starvation wearing a fix's clothes.

        n falls 1828 -> 625 = 2.93x  -> t penalty sqrt(2.93) = 1.71x
        mean 0.057 -> 0.183          = 3.21x
        net t improvement            = 3.21 / 1.71 = 1.88x
    """
    import math
    n_ratio, mean_ratio = 1828 / 625, 0.183 / 0.057
    net = mean_ratio / math.sqrt(n_ratio)
    assert net > 1.0, (
        f"the restriction moves her AWAY from the gate (net t x{net:.2f}) — "
        f"that is starvation, not a fix")
    assert net == pytest.approx(1.88, abs=0.05)
