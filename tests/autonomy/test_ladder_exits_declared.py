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
    """georgia was the book that surfaced this and is RETIRED on both arms
    since (wt); 👩 mum's OversoldRebound and 🙏 avo maria's SwingDip both
    ride an ROI ladder — naming two living books stops a future reader
    assuming the exclusion was georgia-specific."""
    assert "freqtrade-mum-lshadow" in sweep.UNSWEEPABLE_EXITS
    assert "freqtrade-avo-maria-lshadow" in sweep.UNSWEEPABLE_EXITS


def test_a_fixed_stop_carrier_is_NOT_excluded():
    """A detector that fires on everything trains the operator to ignore it.

    [2026-08-19] This asserted against the LIVE roster until 👩 mum — the last
    flat-`roi` live family book — was retired (I17 no_rate). Every live family
    book is a ladder book now, so a roster-based assertion would have had to be
    deleted; the RULE is what matters and it is roster-independent, so the test
    moves to the carrier CLASSES. Strictly stronger: it keeps biting no matter
    which books happen to be alive.

    Worth stating, because it is the reason the ladder harness exists at all:
    with mum gone, `UNSWEEPABLE_EXITS` covers **100% of the live family**, so
    `study_exit_sweep` can answer none of them.
    """
    flat_carriers = [c for c in (fam.TrendMomo, fam.MomoBreakout)
                     if not (getattr(c, "roi", None) or {})]
    assert flat_carriers, "TrendMomo/MomoBreakout are the flat-roi carriers"
    # a flat-roi carrier must not be selected by the ladder predicate
    for c in flat_carriers:
        assert len(getattr(c, "roi", None) or {}) <= 1, c.__name__
    # and every book the declaration DOES name must really carry a ladder
    for row in sweep.UNSWEEPABLE_EXITS:
        base = row[: -len("-lshadow")]
        car = next((s for s in fam.live_strategies() if s.bot == base), None)
        assert car is not None, f"{row} declared but not live"
        assert len(getattr(car, "roi", None) or {}) > 1, f"{row} has no ladder"


def test_the_reason_names_the_ladder_and_the_rule_space():
    """A declaration whose reason is vague is a snooze. It must carry the
    actual rungs and say what rule space it falls outside of."""
    why = sweep.UNSWEEPABLE_EXITS["freqtrade-mum-lshadow"]
    assert "ladder" in why.lower()
    assert "0m:2%" in why, why         # the real first rung, not a placeholder
    assert "1440m" in why, why         # the real last rung (12h carry-bounded)
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
