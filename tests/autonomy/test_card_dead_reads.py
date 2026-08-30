"""[(vj)] THE BOT CARD READ FIVE bot_pnl COLUMNS THAT DO NOT EXIST.

`pnl_dashboard.card()` read `row["pnl_weekly"]`, `row["pnl_monthly"]`,
`row["max_drawdown"]`, `row["best_trade"]` and `row["worst_trade"]` off a row
that comes from `SELECT * FROM bot_pnl` — a table whose twelve columns are
bot, closed_trades, equity, extra, losses, open_trades, pnl_abs, pnl_daily,
pnl_pct, status, updated_at, wins. Every read returned None on every row, each
sat behind an `is not None` guard, and so FOUR card sections were unreachable
dead code for every bot, forever. It is the read-side residue of the 28-Jul
doc-truth cleanup: those exact five names were struck from `publish()`'s docs
because a bot following them raised TypeError at the call site, and the
publisher and the docs were fixed while the consumer was not.

THE ONE THAT MATTERS is Max Drawdown — one of the six GO-LIVE BARS. The card
omitted the line rather than saying "unknown", so a reader could not tell
"this book has no drawdown" from "this number was never computed": the
(hf)/I1 byte-identical shape, at the reporting layer, on the rule that governs
real money.

WHAT THESE TESTS PIN, and the mutation that reddens each:
  * the four sections RENDER on a publisher-shaped row  (revert any read to
    `row.get(...)` => red);
  * `max_dd_pct` is formatted as the PERCENT IT ALREADY IS — the live payload
    carries 13.1 meaning 13.1%, and `pct()` renders that as +1310.00%
    (`{v:.1f}%` -> `pct(v)` => red);
  * a book the grader cannot speak for renders "unknown" WITH the grader's own
    reason, never nothing  (drop the else-branch => red);
  * the drawdown is IMPORTED from the grader, never recomputed here — a second
    computation would be a second rule ((hj)).
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

# NO `os.environ.setdefault("DATABASE_URL", ...)` here: `tests/autonomy/
# test_db_unreachable_in_tests.py` requires the name to be ABSENT, not empty,
# and setting it leaks into every later test in the session. The module
# imports fine without it — every function this file drives is pure or is
# stubbed below.
import pnl_dashboard as D          # noqa: E402

#: The columns `bot_pnl` really has. Derived in the test below from the
#: publisher's own DDL rather than restated, so a real ALTER TABLE moves it.
_DEAD_READS = ("pnl_weekly", "pnl_monthly", "max_drawdown",
               "best_trade", "worst_trade")


def _row(bot="band-kelly-lshadow", age_s=60):
    """A `bot_pnl` row shaped the way `fetch_rows()` really returns it —
    `SELECT *`, so `updated_at` is a DATETIME, not the ISO string /pnl.json
    serialises. Driving the consumer with the feed's shape instead of the
    publisher's is the (tj) trap and it raises AttributeError here."""
    return {"bot": bot, "status": "online", "equity": 1013.68,
            "pnl_abs": 13.68, "pnl_pct": 0.0137, "open_trades": 2,
            "closed_trades": 236, "wins": 120, "losses": 116,
            "pnl_daily": 1.2, "extra": {},
            "updated_at": datetime.now(timezone.utc) - timedelta(seconds=age_s)}


def _enrich(dd=None, **kw):
    base = {"pnl_7d": 13.68, "n_7d": 4, "pnl_30d": -4.61, "n_30d": 22,
            "best_trade": 36.42, "worst_trade": -30.20}
    base.update(kw)
    if dd is not None:
        base["golive_dd"] = dd
    return base


def _card(bot="band-kelly-lshadow", enrich=None, row=None):
    return D.card(bot, row if row is not None else _row(bot), {}, None, None,
                  None, enrich if enrich is not None else _enrich())


# ---------------------------------------------------------------------------
# 1. THE DEAD READS ARE GONE
# ---------------------------------------------------------------------------

def test_card_no_longer_reads_columns_bot_pnl_does_not_have():
    """AST over `card()`, against the publisher's OWN DDL. A page-wide
    substring scan is not a structural claim ((gn)) — these names legitimately
    appear in this file's prose and in the enrich dict."""
    import ast
    import re
    src = (_ROOT / "pnl_dashboard.py").read_text()
    tree = ast.parse(src)
    fns = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "card"]
    assert len(fns) == 1, f"expected one card(), found {len(fns)}"

    # the publisher's real column set, scoped to bot_pnl only
    ddl = (_ROOT / "bot_pnl_store.py").read_text()
    create = re.search(r"CREATE TABLE IF NOT EXISTS bot_pnl\s*\((.*?)\)\s*[\"']",
                       ddl, re.S)
    assert create, "could not find bot_pnl's CREATE TABLE — re-scope this test"
    cols = set(re.findall(r"^\s*(\w+)\s+\w", create.group(1), re.M))
    # `ADD COLUMN IF NOT EXISTS <name>` — the optional clause must be consumed,
    # or the capture lands on "IF" and the real column (pnl_daily) is missed,
    # which would make this guard fire on a LEGITIMATE read.
    cols |= set(re.findall(
        r"ALTER TABLE bot_pnl\s+ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)", ddl))
    assert {"bot", "equity", "pnl_abs", "updated_at", "pnl_daily"} <= cols, \
        sorted(cols)

    read = {n.args[0].value for n in ast.walk(fns[0])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get" and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "row" and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)}
    assert read, "extracted no row.get() keys — the AST walk is broken"
    assert read <= cols, ("card() reads bot_pnl columns that do not exist: "
                          f"{sorted(read - cols)}")
    for name in _DEAD_READS:
        assert name not in read, f"{name} is back on the row path"


# ---------------------------------------------------------------------------
# 2. THE SECTIONS ACTUALLY RENDER
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["7d P&amp;L", "30d P&amp;L",
                                   "Max Drawdown", "Best / Worst trade"])
def test_each_repaired_section_renders(label):
    """Four sections that rendered on ZERO bots for weeks. Driven through the
    real `card()`, not asserted about the source."""
    assert label in _card(), f"{label} still missing from the card"


def test_the_labels_are_valid_html():
    """A raw `&` is invalid HTML and survived in these two lines precisely
    because they never rendered — unreachable code is unexercised code."""
    html = _card()
    assert "P&L<" not in html, "raw ampersand in a P&L label"


# ---------------------------------------------------------------------------
# 3. THE DRAWDOWN — UNITS, AND UNKNOWN-IS-NOT-MISSING
# ---------------------------------------------------------------------------

def test_max_drawdown_renders_the_percent_it_already_is():
    """THE UNIT TRAP. `golive_readiness` publishes `max_dd_pct` ALREADY as a
    percent (live payload: band-kelly 13.1 = 13.1%), while `pct()` multiplies
    by 100 and would render +1310.00% — a number that would read as a
    catastrophic breach of the 15% bar on a book that is under it."""
    assert D.pct(13.1) == "+1310.00%", D.pct(13.1)      # the trap, pinned
    html = _card(enrich=_enrich(dd={"pct": 13.1, "basis": "mtm", "why": None}))
    assert "13.1%" in html, "max_dd not rendered in its own units"
    assert "1310" not in html, "max_dd was passed through pct() — 100x wrong"


def test_the_basis_is_shown_because_the_two_can_disagree():
    """`max_dd_pct` is the WORSE of realised and MTM (I9). Which one it is
    changes what the number means, so the card says."""
    html = _card(enrich=_enrich(dd={"pct": 2.0, "basis": "realised",
                                    "why": None}))
    assert "realised" in html, html[html.find("Max Drawdown"):][:200]


def test_a_book_the_grader_cannot_grade_says_unknown_with_the_reason():
    """UNKNOWN IS NOT MISSING. `0.0%` drawdown is a real everyday reading on
    this fleet, so an omitted line is byte-identical to a healthy one — the
    exact failure this repair exists to end. The 6 `below_floor` books carry
    the grader's own `why_absent`."""
    html = _card(enrich=_enrich(dd={"pct": None, "basis": None,
                                    "why": "no closed trades in the ledger"}))
    assert "Max Drawdown" in html, "the line vanished on an ungraded book"
    assert "unknown" in html
    assert "no closed trades in the ledger" in html, "the reason was dropped"


def test_a_dark_grader_still_renders_unknown_never_a_zero():
    """Fail-safe direction: no `golive_dd` at all (grader dark, or a book it
    has never heard of) must still render the line."""
    for enrich in (_enrich(), {}, None):
        html = _card(enrich=enrich)
        assert "Max Drawdown" in html and "unknown" in html, enrich
        assert "0.0%" not in html.split("Max Drawdown")[1][:120]


def test_the_card_imports_the_drawdown_and_never_recomputes_it():
    """A second copy of a rule is a second rule ((hj)). The drawdown number is
    the grader's; this module may READ it and must not derive one.

    STRUCTURAL, NOT A WORD SCAN. My first cut banned the substrings
    "max(" / "peak" / "cumsum" over the unparsed source — and it failed on its
    OWN DOCSTRING, because "speak" contains "peak". That is precisely the
    "a page-wide substring scan is not a structural claim" defect this repo
    records ((gn): a test requiring `dry_run` failed on the sentence promising
    the property). The check is now over the AST with the docstring removed:
    a pass-through reads and assembles, so it needs no arithmetic and no
    extremum call."""
    import ast
    src = (_ROOT / "pnl_dashboard.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_golive_dd")

    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]                      # drop the docstring — it is prose
    code = "\n".join(ast.unparse(s) for s in body)
    assert "golive-readiness" in code, "not sourced from the grader's key"

    nodes = [n for stmt in body for n in ast.walk(stmt)]
    calls = {n.func.id for n in nodes
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not ({"max", "min", "sum", "abs"} & calls), (
        f"looks like a recomputation, not a read: {sorted(calls)}")
    arith = [n for n in nodes if isinstance(n, ast.BinOp)]
    assert not arith, "a pass-through needs no arithmetic on the grader's number"


def test_fetch_golive_dd_reads_both_sections_of_the_real_payload():
    """Driven against the grader's own published shape: 14 graded books carry
    `max_dd_pct`; the 6 `below_floor` books carry `why_absent` and no number.
    A reader that took only `books` would leave those six with no line at all
    — which is the defect, re-made one level up."""
    payload = {
        "books": {"a-lshadow": {"max_dd_pct": 13.1, "maxdd_basis": "mtm"}},
        "below_floor": {"b-lshadow": {"max_dd_pct": None,
                                      "why_absent": "no closed trades"}},
    }
    D.fetch_states = lambda keys: {"golive-readiness": payload}
    got = D.fetch_golive_dd()
    assert set(got) == {"a-lshadow", "b-lshadow"}, got
    assert got["a-lshadow"] == {"pct": 13.1, "basis": "mtm", "why": None}
    assert got["b-lshadow"]["pct"] is None
    assert got["b-lshadow"]["why"] == "no closed trades"


def test_a_junk_max_dd_degrades_to_unknown_not_to_a_number():
    D.fetch_states = lambda keys: {"golive-readiness": {
        "books": {"a-lshadow": {"max_dd_pct": "nope"}}}}
    assert D.fetch_golive_dd()["a-lshadow"]["pct"] is None
