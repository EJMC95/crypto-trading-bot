#!/usr/bin/env python3
"""[2026-08-17 (pk)] 🎯 THE PARTIAL SCREEN MUST BE PUBLISHED, NOT MERELY EXEMPT.

`(pf)` closed the class-declaration hole for the three books whose gate screens
non-crypto as a WHOLE (🌾 carry, 🎸 Barnesy, and via `(pj)` the funding trio),
and DECLARED `lighter_perp_sniper.py` in `PARTIAL_SCREEN_OK` — correctly, since
`crypto_only: true` would misdescribe a gate the LISTING source leaves open.

The exemption is right about `true` and wrong about the conclusion. `false` was
available and true the whole time, and the per-source detail is derivable from
the module. So this book publishes BOTH, and this file pins both halves.

WHY IT MATTERS, measured: 🎯 has sat `unreachable` on the decision docket for 10
days on n=29 (mean −0.498%/trade). Split by the scout's own class map, 18 of the
20 closes in the live feed window are the non-crypto class surge/young stopped
admitting on 13-Aug, carrying −$5.34, while its 2 crypto closes read +$0.46. And
unlike 🌾 carry — whose removed closes will age out of an era window — this book
has `era = null` by design (its publisher does not accrue), so those closes NEVER
leave the graded sample. The verdict is permanent by construction, on a policy
the book stopped running four days ago.

This does NOT re-cut the grade, deliberately: `(pf)`'s own ruling is that a
universe narrowing is ordinary tuning that does not move an era, and the blessed
precedent `(jg)`/`(ki)` is REPORT the split beside the pooled grade. This file
guards the reporting.

Kept OUT of `test_class_screen_declared.py` on purpose — that file is the
whole-gate guard and was open in a concurrent session when this shipped.
"""
import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SNIPER = _ROOT / "lighter_perp_sniper.py"

# The three admission sources, and whether each screens non-crypto. `listing`
# is False STRUCTURALLY — (lk) left it unscreened on the record (n=1, +$0.28,
# unmeasured, the book's founding thesis).
_SCREENED_SOURCES = ("surge", "young")
_UNSCREENED_SOURCES = ("listing",)


def _tree():
    if not _SNIPER.exists():                      # pragma: no cover
        pytest.fail("lighter_perp_sniper.py is gone — retire this guard with it")
    return ast.parse(_SNIPER.read_text(encoding="utf-8"))


def _caps_dicts(tree):
    """Every `"caps": {...}` dict literal in the module, as ast.Dict nodes.

    AST, not a substring scan: `(hj)` records three tests in one session that
    passed on the prose promising the property they checked.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and k.value == "caps"
                    and isinstance(v, ast.Dict)):
                out.append(v)
    return out


def _entry(d, key):
    """The value node for `key` in an ast.Dict, or None."""
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def test_the_sniper_publishes_a_whole_gate_crypto_only_of_false():
    """Absent reads as UNKNOWN to `audit_book_overlap`, which under-informs
    exactly as a wrong `true` would overstate. The gate admits non-crypto via
    the listing source, so `false` is the honest whole-gate answer."""
    caps = _caps_dicts(_tree())
    assert caps, "no `caps` dict found — did the publish block move?"
    declared = [_entry(d, "crypto_only") for d in caps]
    declared = [n for n in declared if n is not None]
    assert declared, (
        "lighter_perp_sniper.py publishes no `crypto_only`. Its gate as a "
        "whole ADMITS non-crypto (the listing source is unscreened), so the "
        "honest value is False — not silence. audit_book_overlap reads a bool "
        "and treats absence as UNKNOWN (pk).")
    for node in declared:
        assert isinstance(node, ast.Constant) and node.value is False, (
            "`crypto_only` must be the literal False. True would misdescribe "
            "the listing source; deriving it from ALLOW_NONCRYPTO would be "
            "WRONG here — flipping that env widens surge/young only, and the "
            "whole-gate answer stays False in both states (pk).")


def test_the_per_source_screen_is_published_and_covers_every_source():
    """The bool cannot carry the half that made this book's grade unreadable:
    that TWO of three sources are screened and one is not."""
    caps = _caps_dicts(_tree())
    maps = [_entry(d, "class_screen") for d in caps]
    maps = [n for n in maps if n is not None]
    assert maps, (
        "lighter_perp_sniper.py publishes no `class_screen`. A partial screen "
        "that publishes only a whole-gate bool still hides which sources are "
        "screened — the (pf) defect, one level down (pk).")
    for m in maps:
        assert isinstance(m, ast.Dict), "`class_screen` must be a dict literal"
        keys = {k.value for k in m.keys if isinstance(k, ast.Constant)}
        missing = set(_SCREENED_SOURCES + _UNSCREENED_SOURCES) - keys
        assert not missing, (
            f"`class_screen` omits {sorted(missing)}. Every admission source "
            "must appear, or a reader cannot tell 'unscreened' from "
            "'forgotten' — I1's shape on the reporting side (pk).")


def test_the_screened_sources_track_the_switch_rather_than_a_literal():
    """`surge`/`young` hardcoded True would lie the moment SNIPER_ALLOW_NONCRYPTO
    is set — the (a kill switch must reach the consumer) failure mirrored onto
    reporting, and the property `(pf)` pins for the whole-gate books."""
    for m in [n for n in
              (_entry(d, "class_screen") for d in _caps_dicts(_tree()))
              if n is not None]:
        for k, v in zip(m.keys, m.values):
            if not (isinstance(k, ast.Constant)
                    and k.value in _SCREENED_SOURCES):
                continue
            names = {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
            assert "ALLOW_NONCRYPTO" in names, (
                f"`class_screen[{k.value!r}]` must be DERIVED from "
                "ALLOW_NONCRYPTO (e.g. `not ALLOW_NONCRYPTO`), never a "
                "literal — the screen it describes is reversible by env (pk).")


def test_the_unscreened_source_is_a_literal_false_not_a_derived_one():
    """The mirror of the test above, and it is not symmetric: `listing` is
    unscreened in BOTH env states, so deriving it would make the reversal env
    appear to close a source it never touches."""
    for m in [n for n in
              (_entry(d, "class_screen") for d in _caps_dicts(_tree()))
              if n is not None]:
        for k, v in zip(m.keys, m.values):
            if not (isinstance(k, ast.Constant)
                    and k.value in _UNSCREENED_SOURCES):
                continue
            assert isinstance(v, ast.Constant) and v.value is False, (
                f"`class_screen[{k.value!r}]` must be the literal False: the "
                "listing source is unscreened regardless of "
                "SNIPER_ALLOW_NONCRYPTO (lk), so a derived value would "
                "misreport what that env does (pk).")


def test_the_class_screen_still_has_a_real_screen_behind_it():
    """If the surge/young screen is ever deleted, this whole declaration
    becomes a claim about nothing — and the (pf) population guard keys on the
    same module-level switch, so it would go quiet at the same moment."""
    tree = _tree()
    assert any(isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "ALLOW_NONCRYPTO"
                       for t in n.targets)
               for n in tree.body), (
        "module-level ALLOW_NONCRYPTO is gone: either the screen was removed "
        "(then delete this guard and the caps declaration with it) or it moved "
        "out of module scope (then (pf)'s population scan no longer sees this "
        "file either) (pk).")
