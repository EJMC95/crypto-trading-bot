"""(mr) 🚀 crypto-breakout-4h is RETIRED — and the retirement is ROW-scoped.

THE DECISION (2026-08-14, operator: "go ahead and retire it"). The I17
keep-or-retire call, made on a measurement: of the NINE books the decision
docket published, this is the ONLY one that survives Benjamini-Hochberg at
FDR 0.05 (p=0.0036 against a 0.0056 critical value). In-era n=15, mean
-1.745%/trade, t=-3.50, both halves negative; all-time n=21, t=-5.48. The
horizon verdict is `unreachable` — mean <= 0, so more of the same closes
cannot flip it.

WHAT MAKES THIS RETIREMENT DIFFERENT, and why these tests exist: it is the
fleet's first retirement of a book that SHARES ITS MODULE. 🌊 Tide Rider and
📊 Index Rider each owned their file and could idle the whole process
(`while True: sleep`). `lighter_family_bot.py` runs SEVEN books in one
service, so that pattern would silence six healthy ones. The failure this
file guards is therefore not "the retirement was forgotten" but "the
retirement was too broad".
"""
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

BOT = "crypto-breakout-4h"
ROW = "crypto-breakout-4h-lshadow"
OVERRIDE = "BREAKOUT4H_RETIRED_OVERRIDE"


def _family():
    import lighter_family_bot as fam
    return fam


def test_the_retired_book_is_absent_from_the_live_roster(monkeypatch):
    fam = _family()
    monkeypatch.delenv(OVERRIDE, raising=False)
    live = {s.bot for s in fam.live_strategies()}
    assert BOT not in live, "the retired book is still being built into a Book"
    # ...and it is STILL DECLARED, so the venue/universe assertions and the
    # history keep covering it. A retirement that deletes the declaration
    # deletes the reason with it.
    assert BOT in {s.bot for s in fam.STRATEGIES}, (
        "the strategy declaration was deleted rather than retired — "
        "RETIRED_BOOKS is the record of WHY, and STRATEGIES is what the "
        "spot-ports-stay-crypto assertion walks")


def test_the_other_six_books_keep_trading(monkeypatch):
    """THE FAILURE THIS RETIREMENT COULD HAVE CAUSED. The idle-the-process
    pattern of the two prior row retirements would have silenced every family
    book in this service."""
    fam = _family()
    monkeypatch.delenv(OVERRIDE, raising=False)
    live = {s.bot for s in fam.live_strategies()}
    for still in ("freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria",
                  "freqtrade-georgia", "crypto-intraday-15m",
                  "crypto-swing-daily"):
        assert still in live, f"{still} was retired by collateral damage"
    assert len(live) == len(fam.STRATEGIES) - 1, live


def test_the_override_resurrects_it_with_no_redeploy(monkeypatch):
    fam = _family()
    for val in ("run", "1", "true", "RUN"):
        monkeypatch.setenv(OVERRIDE, val)
        assert BOT in {s.bot for s in fam.live_strategies()}, val
    for val in ("", "no", "0", "false", "yes"):
        monkeypatch.setenv(OVERRIDE, val)
        assert BOT not in {s.bot for s in fam.live_strategies()}, (
            f"{val!r} must not resurrect a retired book — only an explicit "
            f"run/1/true does")


def test_no_consumer_iterates_the_raw_declaration_to_run_books():
    """A RETIREMENT IS ONE DECLARATION AND ONE DERIVATION ((mo)).

    `STRATEGIES` may be READ (assertions, docs, history). What it must not do
    is drive anything that PUBLISHES a row or OPENS a position — that is how a
    book ends up retired in one loop and alive in another. Checked by AST over
    the real source: a page-wide substring scan is not a structural claim.
    """
    tree = ast.parse((ROOT / "lighter_family_bot.py").read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        it = node.iter
        if not (isinstance(it, ast.Name) and it.id == "STRATEGIES"):
            continue
        body = ast.dump(node)
        # a loop that constructs a Book or writes to bot_pnl is a RUN path
        if "Book" in body or "set_status" in body or "publish" in body:
            offenders.append(node.lineno)
    assert not offenders, (
        f"lighter_family_bot.py lines {offenders} iterate STRATEGIES to run or "
        f"publish books — use live_strategies() so RETIRED_BOOKS is honoured")


def test_both_halves_of_the_row_retirement():
    """RETIRED_ROWS hides the card; LEGACY_BOTS prunes the frozen row. Doing
    one hides your own omission — and the prune is what frees the book's two
    held slots from every reader of bot_pnl, the ENFORCED long budget
    included."""
    import cleanup_legacy_bots as clean
    import pnl_dashboard as dash
    assert ROW in dash.RETIRED_ROWS, "the dashboard still shows the card"
    assert ROW in clean.LEGACY_BOTS, (
        "the frozen row is never pruned — a hidden-but-present row keeps "
        "consuming budget invisibly (the 14-Jul phantom-holdings failure)")


def test_the_reason_travels_with_the_code():
    fam = _family()
    assert fam.RETIRED_BOOKS.get(BOT) == OVERRIDE, fam.RETIRED_BOOKS
    src = (ROOT / "lighter_family_bot.py").read_text()
    where = src.index("RETIRED_BOOKS = {")
    note = src[max(0, where - 4000):where]
    for token in ("(mr)", "-3.50", "Benjamini", OVERRIDE):
        assert token in note, (
            f"the retirement note lost {token!r} — a retirement without its "
            f"measurement is a preference, and the next session cannot "
            f"re-decide it")
