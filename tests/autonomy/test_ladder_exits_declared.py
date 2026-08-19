"""[2026-08-19 fleet audit] A book whose exit is outside the sweep's rule space
must SAY SO — "impossible", never "unknown".

Found running the carried georgia item: `study_exit_sweep` reported
`calibration: SKIPPED — shipped exit rule could not be read from its module`,
which reads as a missing registry entry and sends the next session to add one.
It is not missing. 🔮 georgia exits on a TIME-DECAYING ROI ladder
({0: 1.8%, 180: 1.2%, 360: 0.8%, 720: 0.5%}) under an ATR ratchet capped by the
carrier stoploss; the harness expresses one fixed tp, one fixed sl, one fixed
trail. Mapping the ladder's first rung to `tp_pct` would hand `calibrate()` a
rule the book does not run — the (ps) false-pass, where a calibration gate
graded the harness against trades it could not replay and then guarded the
fleet's largest stop pot.

So the exclusion is DECLARED and DERIVED from the live registry, which is what
keeps it honest as books come and go.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import study_exit_sweep as sweep  # noqa: E402
import lighter_family_bot as fam  # noqa: E402


def test_every_live_ladder_book_is_declared_unsweepable():
    """The population is whoever has a ladder TODAY — not a hand list."""
    expected = {f"{s.bot}-lshadow" for s in fam.live_strategies()
                if len(getattr(s, "roi", None) or {}) > 1}
    assert expected, "expected at least one live ROI-ladder book"
    assert set(sweep.UNSWEEPABLE_EXITS) == expected, (
        f"declared {sorted(sweep.UNSWEEPABLE_EXITS)} vs live {sorted(expected)}")


def test_the_two_known_ladder_books_are_covered():
    """georgia is the book that surfaced this; avo maria is the fleet's
    best-evidenced book and rides the same SwingDip ladder — naming both
    stops a future reader assuming the exclusion is georgia-specific."""
    assert "freqtrade-georgia-lshadow" in sweep.UNSWEEPABLE_EXITS
    assert "freqtrade-avo-maria-lshadow" in sweep.UNSWEEPABLE_EXITS


def test_a_fixed_stop_book_is_NOT_excluded():
    """A detector that fires on everything trains the operator to ignore it.
    Carriers with `roi = {}` (TrendMomo, MomoBreakout) exit on a fixed stop and
    are expressible — they must stay sweepable."""
    flat = {f"{s.bot}-lshadow" for s in fam.live_strategies()
            if not (getattr(s, "roi", None) or {})}
    assert flat, "expected at least one non-ladder live family book"
    assert not (flat & set(sweep.UNSWEEPABLE_EXITS)), sorted(flat & set(sweep.UNSWEEPABLE_EXITS))


def test_the_reason_names_the_ladder_and_the_rule_space():
    """A declaration whose reason is vague is a snooze. It must carry the
    actual rungs and say what rule space it falls outside of."""
    why = sweep.UNSWEEPABLE_EXITS["freqtrade-georgia-lshadow"]
    assert "ladder" in why.lower()
    assert "1.8%" in why, why          # the real first rung, not a placeholder
    assert "720m" in why, why          # the real last rung
    assert "ratchet" in why.lower()


def test_no_ladder_book_ever_gets_a_BOOK_EXITS_entry():
    """The tempting 'fix' is a BOOK_EXITS row, which is exactly the fiction
    this declaration exists to prevent. If both ever name the same book, the
    sweep would calibrate against a rule the book does not run."""
    assert not (set(sweep.BOOK_EXITS) & set(sweep.UNSWEEPABLE_EXITS)), \
        sorted(set(sweep.BOOK_EXITS) & set(sweep.UNSWEEPABLE_EXITS))


def test_the_cli_reports_impossible_before_falling_back_to_unknown():
    """Order matters: the generic 'could not be read' branch must not shadow
    the specific one, or the message reverts to the misleading original."""
    src = (ROOT / "scripts" / "study_exit_sweep.py").read_text()
    tree = ast.parse(src)
    impossible = unknown = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In):
            if getattr(node.comparators[0], "id", "") == "UNSWEEPABLE_EXITS":
                impossible = node.lineno
        if (isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.Is)
                and isinstance(node.left, ast.Call)
                and getattr(node.left.func, "id", "") == "shipped_rule"):
            unknown = node.lineno
    assert impossible is not None, "no UNSWEEPABLE_EXITS branch in the CLI"
    assert unknown is not None, "no shipped_rule-is-None branch in the CLI"
    assert impossible < unknown, (
        f"the specific branch ({impossible}) must precede the generic one ({unknown})")


def test_it_fails_safe_to_empty_rather_than_raising():
    """A study helper that raises on an unimportable registry would take the
    whole sweep down for every book. Fail-safe: no declaration, sweep runs."""
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "lighter_family_bot":
            raise ImportError("simulated")
        return real(name, *a, **k)

    builtins.__import__ = boom
    try:
        assert sweep._ladder_exit_books() == {}
    finally:
        builtins.__import__ = real
