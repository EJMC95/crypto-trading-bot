"""[2026-08-17 (pf)] A BOOK THAT SCREENS AN INSTRUMENT CLASS MUST PUBLISH THAT
IT DOES — otherwise its own losing grade is unreadable.

THE INCIDENT, found by the daily review on 17-Aug. `(lk)` and `(lv)` gave
🌾 carry, 🎸 Barnes and 🎯 the sniper a crypto-only entry screen on 13-Aug.
Four days later the go-live grader and the gate horizon were publishing this,
and no consumer could tell what it was measuring:

    🌾 perps-funding-carry-lshadow   era n=10  t=−4.48  horizon: unreachable
        └─ 9 of 10 closes are SKHYNIXUSD / SPCX / WTI, carrying −$14.96
           of the −$15.45. The book's own gate has refused all three since
           13-Aug, and it has opened NOTHING since.
    🎸 band-barnes-lshadow (carry)   era n=9   t=−4.47  horizon: unreachable
        └─ 9 of 9. The living sleeve has no trade under its current policy
           at all.

So the verdict an operator would retire either book on describes a policy
neither book still runs — and the payload said nothing, because `caps` carried
`enter_apr` and `min_vol` but not the class screen. `(lz)` had already added
`min_vol` to both books for exactly this reason ("unpublished, the collision is
undetectable") and stopped one field short of the other half of the same gate.

THE SPLIT THAT MAKES THIS A CLASS, NOT TWO BUGS: the books BORN with the screen
(🧮 Hull `(me)`, 🏦 Rich Dad `(ls)`, 🧘 Douglas, 📐 Grimes) all publish
`caps.crypto_only`; every book that had it RETROFITTED does not. A retrofit
that changes what a book may enter and does not change what it publishes is the
shape this guard exists to catch, and it will recur the next time a screen is
added to a book that already ships.

I1's shape one level up: `{open: 0}` plus a stale losing grade is byte-identical
between "the screen is working exactly as designed" and "the book is broken".
Only the declaration separates them.
"""
import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Modules whose screen is DELIBERATELY PARTIAL, so a flat `crypto_only: true`
#: would be a false declaration — worse than none. Declared rather than
#: defaulted, the `BORN_DARK_OK` idiom.
PARTIAL_SCREEN_OK = {
    "lighter_perp_sniper.py":
        "[(lk)] the surge and young admission sources are crypto-only; the "
        "LISTING source is deliberately UNSCREENED (n=1, unmeasured, founding "
        "thesis). The book's gate as a whole therefore does NOT refuse "
        "non-crypto, and publishing crypto_only:true would misdescribe it. "
        "Revisit if the listing source is ever screened or retired.",
}


def _module_paths():
    """Every top-level bot module that runs an instrument-class screen.

    Keyed on a module-level `ALLOW_NONCRYPTO` assignment — the reversal switch
    every one of these screens ships with — rather than on a filename list, so
    a NEW book that adds a screen is covered the day it lands.
    """
    out = []
    for p in sorted(_ROOT.glob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        for node in tree.body:                      # module level ONLY
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "ALLOW_NONCRYPTO"
                    for t in node.targets):
                out.append((p, tree))
                break
    return out


def _caps_keys(tree):
    """Every string key of every dict literal assigned to a `"caps"` entry.

    AST, not a substring scan: `(hj)` records three tests in one session that
    passed on the prose promising the property they were checking. A comment
    mentioning `crypto_only` must not satisfy this guard.
    """
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and k.value == "caps"
                    and isinstance(v, ast.Dict)):
                for ck in v.keys:
                    if isinstance(ck, ast.Constant) and isinstance(ck.value, str):
                        keys.add(ck.value)
    return keys


def test_the_scan_finds_the_books_this_is_about():
    """A guard that matched nothing would pass forever. Name the population."""
    names = {p.name for p, _ in _module_paths()}
    assert len(names) >= 6, names
    for expected in ("funding_carry_bot.py", "lighter_band_barnes_bot.py",
                     "lighter_book_hull_bot.py", "lighter_book_kiyosaki_bot.py",
                     "lighter_perp_sniper.py"):
        assert expected in names, f"{expected} missing from {sorted(names)}"


@pytest.mark.parametrize("path,tree", _module_paths(),
                         ids=lambda x: getattr(x, "name", ""))
def test_a_screened_book_declares_its_screen(path, tree):
    if path.name in PARTIAL_SCREEN_OK:
        pytest.skip(PARTIAL_SCREEN_OK[path.name])
    keys = _caps_keys(tree)
    assert keys, (
        f"{path.name} runs a class screen but publishes no `caps` dict at all "
        "— nothing downstream can read its gate")
    assert "crypto_only" in keys, (
        f"{path.name} runs a crypto-only entry screen (module-level "
        "ALLOW_NONCRYPTO) and does NOT publish `caps.crypto_only`. Its grade "
        "then cannot be read: 9 of 🌾 carry's 10 era closes were instruments "
        "its own gate had refused for four days, and the payload said nothing "
        "(pf). Add `\"crypto_only\": not ALLOW_NONCRYPTO` to the caps dict, or "
        "declare the book in PARTIAL_SCREEN_OK with the reason its screen is "
        f"deliberately incomplete. caps keys found: {sorted(keys)}")


def test_the_declaration_tracks_the_switch_not_a_literal():
    """`crypto_only: True` hardcoded would lie the moment the reversal env is
    set — the (a kill switch must reach the consumer) failure, mirrored on the
    reporting side. The published value must be derived from ALLOW_NONCRYPTO.
    """
    offenders = []
    for path, tree in _module_paths():
        if path.name in PARTIAL_SCREEN_OK:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for k, v in zip(node.keys, node.values):
                if not (isinstance(k, ast.Constant) and k.value == "caps"
                        and isinstance(v, ast.Dict)):
                    continue
                for ck, cv in zip(v.keys, v.values):
                    if not (isinstance(ck, ast.Constant)
                            and ck.value == "crypto_only"):
                        continue
                    names = {n.id for n in ast.walk(cv)
                             if isinstance(n, ast.Name)}
                    if "ALLOW_NONCRYPTO" not in names:
                        offenders.append(f"{path.name}: {ast.unparse(cv)}")
    assert not offenders, (
        "caps.crypto_only must be derived from ALLOW_NONCRYPTO so the "
        "declaration follows the reversal switch: " + "; ".join(offenders))


def test_partial_screen_exemptions_carry_a_reason_and_still_exist():
    """A declared exemption is a decision, not a snooze — and a stale one that
    names a deleted file silently stops guarding anything."""
    for name, why in PARTIAL_SCREEN_OK.items():
        assert (_ROOT / name).exists(), f"{name} no longer exists — drop it"
        assert len(why) > 60, f"{name}: exemption needs a real reason"
