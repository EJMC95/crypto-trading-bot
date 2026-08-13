"""🎸 Barnesy's `extreme` sleeve is RETIRED (2026-08-13 (ly)) — pin it.

WHY THIS FILE EXISTS. The sleeve never opened a position in its life, and
`(lv)` proved that was structural rather than unlucky: its candidate set is a
strict SUBSET of the carry sleeve's, drawn after carry from a shared held-set,
behind a consumer whose cap exceeds the whole qualified supply — offered
nothing carry had not already claimed in 0 of 8,611 scout snapshots.

The follow-up measurement RETIRED it rather than tuning it, and the reason is
the thing this test protects: **every reachable floor is undecidable, and the
cheap ones cannibalise the sleeve that works.** With the (lv) class screen on,
over the full 30-day tape:

    floor      order          entries   days to 30 closes   effect on carry
    $10M       any              0       never               —      (shipped)
    $5M        any              0       never               —      (cage lo)
    $3M        extreme-first    1       903                 5 -> 4
    $2M        extreme-first    5       181                 5 -> 0
    $1M        extreme-first    7       129                 5 -> 0

Lowering the floor ALONE is inert at any value >= carry's floor (the subset
relation holds and carry still runs first), so the only changes that move
anything also hand carry's supply to a sleeve that stays undecidable. This
venue supports ONE harvest sleeve at the 20% TRUE bar, where the whole crypto
population is KAITO / XMR / PAXG / XRP.

THE TRAP THIS GUARDS. The obvious "fix" — move the extreme block above the
carry block — is measurably harmful, and it is a one-line change that looks
like an improvement. If someone deletes the retirement gate, or reorders the
sleeves, this file goes red and points them at the table above.

Assertions are AST-shaped, not substring-shaped: a comment saying "retired"
must not be able to keep this green (the (hj) lesson — three mutations
survived a substring test in one day).
"""
import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "lighter_band_barnes_bot.py"
TREE = ast.parse(SRC.read_text())


def _names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


MAIN = next(n for n in ast.walk(TREE)
            if isinstance(n, ast.FunctionDef) and n.name == "main")


def _open_position_calls(sleeve, scope=MAIN):
    """Every `_open_position(..., "<sleeve>", ...)` call in the TRADING LOOP.

    Scoped to `main` deliberately: `_selftest` opens positions of every sleeve
    directly to exercise the exit rules, and those call sites are neither
    gated nor should they be. An unscoped search reports the selftest's own
    fixture as an ungated entry — which is a test bug, not a finding.
    """
    out = []
    for node in ast.walk(scope):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_open_position"):
            continue
        for a in node.args:
            if isinstance(a, ast.Constant) and a.value == sleeve:
                out.append(node)
    return out


def _guards_of(target, scope=MAIN):
    """The test expressions of every `if` that encloses `target`."""
    guards = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.If):
            continue
        if any(n is target for n in ast.walk(node)):
            guards.append(node.test)
    return guards


def test_the_extreme_sleeve_has_an_entry_site_at_all():
    """If this fails the sleeve was DELETED, not retired — and the census
    contract below is what makes the retirement falsifiable, so a deletion
    silently removes the fleet's ability to un-retire it on evidence."""
    assert _open_position_calls("extreme"), \
        "extreme's entry site vanished; retirement is a GATE, not a deletion"


def test_extreme_entries_are_gated_on_the_retirement_switch():
    """THE LOAD-BEARING ONE. Every extreme entry must sit behind a condition
    that reads EXTREME_RETIRED. Deleting the gate reopens a sleeve measured
    undecidable at every setting it can reach."""
    for call in _open_position_calls("extreme"):
        guards = _guards_of(call)
        assert any("EXTREME_RETIRED" in _names(g) for g in guards), (
            "an extreme-sleeve entry is not gated on EXTREME_RETIRED — see "
            "this file's header table: every reachable floor is undecidable "
            "and the cheap ones take carry's supply to 0")


def test_the_carry_sleeve_is_NOT_gated_on_it():
    """A mutation that gates the wrong sleeve would leave the book silently
    not trading at all, which `open: 0` cannot distinguish from a quiet
    venue (the I1 shape this whole entry is about)."""
    for call in _open_position_calls("carry"):
        for g in _guards_of(call):
            assert "EXTREME_RETIRED" not in _names(g), \
                "the carry sleeve must not be gated on extreme's retirement"


def test_the_switch_is_reversible_without_a_deploy():
    """Fleet convention ((if)/(jh)/(lo)): a retirement carries an env
    override, so resurrecting it is a variable change, not a code change."""
    src = SRC.read_text()
    assign = [n for n in ast.walk(TREE)
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "EXTREME_RETIRED"
                      for t in n.targets)]
    assert assign, "EXTREME_RETIRED must be a module-level assignment"
    assert "BARNES_EXTREME_RETIRED_OVERRIDE" in src, \
        "the retirement needs a named env override to be reversible"
    # the override must be read from the ENVIRONMENT, not a literal
    assert any(isinstance(n, ast.Attribute) and n.attr == "environ"
               for n in ast.walk(assign[0])), \
        "EXTREME_RETIRED must be derived from os.environ, not hardcoded"


def test_a_retired_sleeve_keeps_publishing_its_census():
    """The retirement is a MEASURED call, so it must stay falsifiable: if the
    venue's liquidity ever rises to meet the bar, `extreme.scan.eligible`
    goes positive and says so. A retired sleeve that stopped reporting could
    never be un-retired on evidence."""
    import lighter_band_barnes_bot as bot

    t0 = 1_000_000.0
    fund = {"A": {"rate": 3e-4, "vol": 5e6, "mark": 10.0}}
    hot = {"A": t0 - 7 * 3600}
    cen = bot.harvest_census(fund, set(), hot, t0, 0.20, bot.CARRY_MIN_VOL,
                             class_ok=lambda _c: True)
    cen_x = bot.harvest_census(fund, set(), hot, t0, 0.20, bot.EXTREME_MIN_VOL,
                               class_ok=lambda _c: True)
    extra = bot.build_extra(cen, {}, 0.0, 0.0, {}, t0, census_ext=cen_x)
    ext = extra["sleeves"]["extreme"]
    assert ext["retired"] is True, "the row must publish the retirement"
    assert ext["scan"]["scanned"] == 1, "the census must survive retirement"
    assert ext["floor_usd"] == bot.EXTREME_MIN_VOL


def test_the_reorder_trap_is_documented_where_someone_would_make_it():
    """`(lv)`/(ly)`: moving the extreme block above carry is a one-line change
    that looks like a fix and measurably is not. The refusal has to live at
    the code, not only in the changelog — a reader who greps for the entry
    site must meet the reason there."""
    src = SRC.read_text()
    lines = src.splitlines()
    # anchor on the ENTRY SITE itself (found by AST), not on the first textual
    # occurrence of "extreme" — that one is the sleeve tuple in build_extra,
    # which would let this pass while the entry block carried no reason at all.
    call = _open_position_calls("extreme")[0]
    window = "\n".join(lines[max(0, call.lineno - 40):call.lineno])
    assert any(k in window for k in
               ("cannibalise", "carry goes 5 -> 0", "undecidable", "903 days")), (
        "the measured reason for retirement must sit at the entry block, "
        "where someone about to reorder the sleeves would actually read it")
