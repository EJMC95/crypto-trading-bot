#!/usr/bin/env python3
"""
[2026-08-16 (nn)] 🎯 THE SNIPER'S (ne) SURGE TELEMETRY — the rules that shipped
with no test, and the coverage floor that noticed.

`(ne)` added the surge admission telemetry (`surge_ratio` + the `surge_mult`
in force at entry — the two numbers the X4 expectancy split needed and the
ledger never had) INLINE in `main()`, where nothing can reach it. Measured:
13 statements straight to uncovered, `lighter_perp_sniper.py` 83.5% -> 80.8%,
under its 81% floor — and the **Tests workflow was red on every push from
71b7f4f (ne) for four days**, which is worse than the coverage: a permanently
red CI is a guard nobody reads, so a genuine failure would have been invisible.

`(nn)` moves the three rules to module level (the convention every sibling in
that file already follows) and tests them here.

THE CONTRACT ALL THREE SHARE — and the reason each swallows instead of
raising: a junk row must degrade the close to **no extra, never a guessed
number**. A fabricated `surge_ratio` of 0.0 would be indistinguishable from a
measured one in the very analysis these fields exist to feed, which is the
same "unknown degrades to honest-absent, never to a guess" rule as I8.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lighter_perp_sniper import (          # noqa: E402
    restore_entry_meta, surge_admission, surge_ratio_map,
)


# ------------------------------------------------------------ surge_ratio_map
def test_ratio_map_parses_and_normalises_keys():
    rows = [{"sym": "kaito", "ratio": 3.5}, {"sym": " XMR ", "ratio": "2.0"}]
    assert surge_ratio_map(rows) == {"KAITO": 3.5, "XMR": 2.0}


def test_ratio_map_drops_junk_rows_individually():
    """One bad row must not cost the whole map — the surrounding loop in
    main() had exactly this per-row try/except and it is preserved."""
    rows = [{"sym": "GOOD", "ratio": 4.0},
            {"sym": "BAD", "ratio": "not-a-number"},
            {"sym": "NORATIO"},
            {"ratio": 9.9},                 # no sym -> "" key, still parseable
            None,                           # not a mapping at all
            {"sym": "ALSOGOOD", "ratio": 2.5}]
    out = surge_ratio_map(rows)
    assert out["GOOD"] == 4.0 and out["ALSOGOOD"] == 2.5
    assert "BAD" not in out and "NORATIO" not in out


def test_ratio_map_is_empty_on_a_dark_scout():
    for empty in (None, [], {}):
        assert surge_ratio_map(empty) == {}


# ----------------------------------------------------------- surge_admission
def test_admission_records_ratio_and_the_mult_in_force():
    got = surge_admission("KAITO", {"KAITO": 3.5}, 3.0)
    assert got == {"surge_ratio": 3.5, "surge_mult": 3.0}
    assert isinstance(got["surge_ratio"], float)
    assert isinstance(got["surge_mult"], float)


def test_an_unknown_ratio_records_NOTHING_not_a_zero():
    """THE LOAD-BEARING ONE. A surge admitted while the scout's row is missing
    must record no extra at all: a 0.0 would read downstream as a MEASURED
    ratio of zero and quietly corrupt the split these fields exist to feed."""
    assert surge_admission("MISSING", {"KAITO": 3.5}, 3.0) is None
    assert surge_admission("ANY", {}, 3.0) is None
    assert surge_admission("ANY", None, 3.0) is None


def test_admission_refuses_an_unparseable_mult():
    assert surge_admission("KAITO", {"KAITO": 3.5}, None) is None
    assert surge_admission("KAITO", {"KAITO": 3.5}, "off") is None


# --------------------------------------------------------- restore_entry_meta
def test_restore_round_trips_a_live_admission():
    """What the admission path writes must survive the restart that reads it —
    the two halves are tested against each other, not against a fixture
    somebody hand-wrote to match the consumer."""
    written = {"KAITO": surge_admission("KAITO", {"KAITO": 3.5}, 3.0)}
    assert restore_entry_meta(written) == written


def test_restore_drops_junk_and_keeps_the_rest():
    saved = {"OK": {"surge_ratio": 3.5, "surge_mult": 3.0},
             "NOMULT": {"surge_ratio": 3.5},           # KeyError
             "BADVAL": {"surge_ratio": "x", "surge_mult": 3.0},   # ValueError
             "NOTADICT": "hand-edited",                # TypeError
             "NULL": None}
    out = restore_entry_meta(saved)
    assert out == {"OK": {"surge_ratio": 3.5, "surge_mult": 3.0}}


def test_restore_coerces_keys_to_str_and_values_to_float():
    out = restore_entry_meta({7: {"surge_ratio": "3.5", "surge_mult": "3"}})
    assert out == {"7": {"surge_ratio": 3.5, "surge_mult": 3.0}}


def test_restore_is_empty_on_a_missing_or_unreadable_state():
    for empty in (None, {}, []):
        assert restore_entry_meta(empty) == {}


# ------------------------------------------------------------- still WIRED IN
def test_main_actually_calls_all_three():
    """Extracting a rule and leaving main() with its own copy — or with
    nothing — is the registered-but-inert failure this repo keeps paying for.
    AST, not a substring scan: a comment mentioning the name would pass that.
    """
    tree = ast.parse((ROOT / "lighter_perp_sniper.py").read_text())
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {n.func.id for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for fn in ("surge_ratio_map", "surge_admission", "restore_entry_meta"):
        assert fn in called, f"main() no longer calls {fn}() — rule is inert"


def test_main_kept_no_second_copy_of_the_parsing():
    """The inline loops are GONE, not merely shadowed by the new calls — a
    second copy of a rule is a second rule ((hj))."""
    src = (ROOT / "lighter_perp_sniper.py").read_text()
    assert 'entry_meta[str(_k)]' not in src, "inline restore loop still present"
    assert '"surge_ratio": float(_surge_ratios' not in src, \
        "inline admission record still present"


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_sniper_surge_telemetry: all passed")
