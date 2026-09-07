"""[(yj)] THE MEASURABILITY GUARD PARSED 68 RETIRED ROWS WHERE 46 ARE DECLARED.

`audit_lever_measurability.retired_rows` read `pnl_dashboard.RETIRED_ROWS` with
`re.search(r"RETIRED_ROWS\\s*=\\s*\\{(.*?)\\n\\}")`. The set is INDENTED, so that
end pattern cannot match its own closing brace: the match ran on ~200 lines to
the next line-start `}` in the file, swallowing 22 extra names out of
`OVERTRADE_MAX` — LIVING books among them (band-kelly, book-hull,
book-kiyosaki, lighter-perp-sniper, lighter-ticket-taker, perps-funding-spread,
pm-albanese, pm-turnbull).

It changed no verdict only by luck: the swallowed names are BASE ids and every
`LEVER_BOOK` target carries a `-lshadow` suffix, so none collided. The failure
direction is the dangerous one — an over-read retired set marks a LIVING book's
lever `DEAD`, and `DEAD` is EXEMPT from I23's measurability ratchet, so the
guard would quietly excuse the levers it exists to chase. The guard's own
empty-parse check catches under-reading and is structurally blind to this,
which is `(po)`'s rule again: a check that inspects the wrong span reports
clean.
"""
import ast
import importlib.util
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "alm", ROOT / "scripts" / "audit_lever_measurability.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ast_truth():
    tree = ast.parse((ROOT / "pnl_dashboard.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", None) == "RETIRED_ROWS" for t in n.targets):
            return {e.value for e in n.value.elts
                    if isinstance(e, ast.Constant)}
    raise AssertionError("RETIRED_ROWS not found")


def test_the_parse_is_exactly_the_declared_set():
    """Mutation: restore the regex parse => 68 vs 46 and this reddens."""
    got, real = _mod().retired_rows(), _ast_truth()
    assert got == real, {"extra": sorted(got - real),
                         "missing": sorted(real - got)}


def test_a_living_book_is_never_read_as_retired():
    """The consequence, stated as its own assertion: no row the fleet still
    publishes may appear in the parsed retired set."""
    import json
    living = set(json.loads(
        (ROOT / "tests" / "fixtures" / "living_rows.json").read_text())["rows"])
    assert not (_mod().retired_rows() & living), \
        sorted(_mod().retired_rows() & living)


def test_an_absent_declaration_reads_empty_rather_than_guessing():
    """Fail-safe unchanged: `check` fails on an empty parse, so a vanished
    assignment must come back empty, never partially matched from elsewhere."""
    assert _mod().retired_rows(src="X = 1\n") == set()
    assert _mod().retired_rows(src="RETIRED_ROWS = some_call()\n") == set()
