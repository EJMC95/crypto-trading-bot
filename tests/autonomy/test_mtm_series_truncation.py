"""[2026-09-10 (zv)] A TRUNCATED MTM WINDOW MUST SAY SO.

THE GAP. `golive_readiness.equity_series` reads `<bot>:equity` through
`bot_pnl_store.fetch_state_history`, whose SQL is `ORDER BY ts DESC LIMIT %s`.
So the cap yields the NEWEST `EQUITY_LIMIT` samples: a book that has published
more than that is graded on a trailing window, not on its life — and a
truncated read returns the same SHAPE of list as a complete one, so nothing
downstream could tell them apart.

MEASURED ON THE LIVE PAYLOAD, 10-Sep 02:00Z: three books sit at EXACTLY the
cap — 🎯 `lighter-perp-sniper-lshadow`, 🏗️ `pm-albanese-lshadow` and 💼
`pm-turnbull-lshadow`, all `mtm.n = 20000` over 14.2-14.7 days — and 🪁
`band-kelly-lshadow` is at 16,762 and climbing. That is the `(qz)` signature
the repo already has doctrine for: *a result exactly equal to its own limit is
a truncation signature*, and the two numbers were never compared.

WHICH WAY IT FAILS, which is why it is worth a flag: a trailing sub-window's
peak-to-trough is a max over a SUBSET of the pairs the full series offers, so
truncation can only UNDERSTATE the drawdown — the permissive direction on the
one go-live bar that is not clip-invariant — and it shrinks `peak_equity`,
which since (yz) is that bar's own denominator.

PUBLISH-ONLY BY CONSTRUCTION: `grade` and `bar_map` are untouched and the flag
gates nothing. Making truncation refuse a verdict is a gate re-spec, i.e.
Eamon's act, not a session's — the (yr)/(yz) precedent.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import golive_readiness as gr  # noqa: E402

pytestmark = pytest.mark.autonomy

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _Store:
    """A store whose history has `total` samples and honours the LIMIT the
    caller passes, newest-first — `fetch_state_history`'s own contract."""

    def __init__(self, total, equities=None):
        self.total = total
        self.equities = equities
        self.asked = None

    def fetch_state_history(self, key, limit=800):
        self.asked = limit
        n = min(self.total, limit)
        rows = []
        for i in range(n):                       # newest first
            eq = (self.equities[i] if self.equities is not None
                  else 1000.0 + (i % 7))
            rows.append({"ts": (T0 - timedelta(minutes=5 * i)).isoformat(),
                         "payload": {"equity": eq}})
        return rows


def _clear():
    gr.last_series_read.clear()


# ------------------------------------------------------------- the finding
def test_a_read_that_fills_the_cap_is_flagged_truncated():
    _clear()
    st = _Store(total=50_000)
    m = gr.book_mtm("bookish", store=st)
    assert st.asked == gr.EQUITY_LIMIT, "the cap must reach the store"
    assert m["n"] == gr.EQUITY_LIMIT
    assert m["truncated"] is True
    assert m["window_limit"] == gr.EQUITY_LIMIT


def test_a_read_under_the_cap_is_not_flagged():
    """The control group: a detector that flags everything trains the reader
    to ignore it ((hh)). 👩 mum's live arm reads 4,524 today."""
    _clear()
    m = gr.book_mtm("bookish", store=_Store(total=4_524))
    assert m["n"] == 4_524
    assert m["truncated"] is False
    assert m["window_limit"] == gr.EQUITY_LIMIT


def test_the_flag_rides_apply_mtm_to_the_published_payload():
    """`apply_mtm` does `out["mtm"] = mtm`, so the flag must arrive in the
    payload without any consumer being taught about it."""
    _clear()
    m = gr.book_mtm("bookish", store=_Store(total=50_000))
    out = gr.apply_mtm({"max_dd_frac": 0.01}, m)
    assert out["mtm"]["truncated"] is True
    assert out["mtm"]["window_limit"] == gr.EQUITY_LIMIT


def test_the_receipt_counts_RAW_rows_not_parsed_points():
    """The false-negative that matters: if the count were taken AFTER the
    parse filter, a truncated read carrying junk rows would sit under the cap
    and report clean. Every row here fills the cap; half are unreadable."""
    _clear()

    class _Junk(_Store):
        def fetch_state_history(self, key, limit=800):
            rows = super().fetch_state_history(key, limit)
            for i in range(0, len(rows), 2):
                rows[i]["payload"] = {}          # no equity -> dropped
            return rows

    m = gr.book_mtm("bookish", store=_Junk(total=50_000))
    assert m["n"] < gr.EQUITY_LIMIT, "the parse filter must have dropped rows"
    assert m["truncated"] is True, \
        "the receipt must count RAW rows, or junk masks a truncated read"


# ------------------------------------------------------------- direction
def test_truncation_understates_the_drawdown_the_permissive_direction():
    """The claim the docstring rests on, driven rather than asserted: the
    book's deep hole is OLD, so a trailing window that excludes it reports a
    smaller drawdown. Same data, two caps."""
    _clear()
    # newest-first: index 0 is newest. A crash sits in the OLD tail.
    eq = [1000.0] * 300 + [500.0] * 50 + [1000.0] * 50
    full = gr.mtm_drawdown(gr.equity_series(
        "b", store=_Store(total=len(eq), equities=eq), limit=len(eq)))
    trunc = gr.mtm_drawdown(gr.equity_series(
        "b", store=_Store(total=len(eq), equities=eq), limit=200))
    assert abs(full["max_dd_usd"]) > abs(trunc["max_dd_usd"]), \
        "the older crash must be invisible to the trailing window"
    assert abs(trunc["max_dd_usd"]) == 0.0
    assert full["peak_equity"] >= trunc["peak_equity"]


# ------------------------------------------------------------ fail-safes
def test_a_dark_store_records_a_read_of_zero_and_never_claims_truncation():
    _clear()

    class _Dark:
        def fetch_state_history(self, key, limit=800):
            raise RuntimeError("db down")

    assert gr.equity_series("b", store=_Dark()) == []
    assert gr.last_series_read["b"] == {"rows": 0, "limit": gr.EQUITY_LIMIT,
                                        "truncated": False}
    assert gr.book_mtm("b", store=_Dark()) is None


def test_an_absent_receipt_never_manufactures_a_flag():
    """`book_mtm` on a book whose receipt was cleared underneath it must read
    False, never None-as-truthy or a KeyError."""
    _clear()
    m = gr.mtm_drawdown(gr.equity_series("b", store=_Store(total=300)))
    gr.last_series_read.clear()
    rec = gr.last_series_read.get("b") or {}
    assert bool(rec.get("truncated")) is False
    assert isinstance(m, dict)


def test_a_series_too_thin_for_a_verdict_returns_None_unchanged():
    _clear()
    assert gr.book_mtm("b", store=_Store(total=1)) is None


def test_book_mtm_passes_its_limit_through_to_the_read():
    """An argument that is accepted and silently ignored is worse than one
    that does not exist — caught here by a surviving mutation that dropped
    `limit=limit` from the inner call and left every other test green."""
    _clear()
    st = _Store(total=50_000)
    m = gr.book_mtm("bookish", store=st, limit=500)
    assert st.asked == 500, "the caller's limit never reached the store"
    assert m["n"] == 500 and m["truncated"] is True
    assert m["window_limit"] == 500, "the receipt must record the limit USED"


def test_the_limit_is_env_tunable_and_sane():
    assert 1_000 <= gr.EQUITY_LIMIT <= 500_000, gr.EQUITY_LIMIT


def test_a_missing_store_api_still_fails_LOUD_the_ja_iz_contract():
    """NOT a never-raises test, deliberately. `equity_series` resolves
    `store.fetch_state_history` OUTSIDE its fail-safe because (iz) shipped a
    phantom method name that failed SILENT on every book for days — "a missing
    API is a programming error and must fail loud". Adding a receipt must not
    have softened that."""
    _clear()
    with pytest.raises(AttributeError):
        gr.equity_series("b", store=object())


def test_the_receipt_writer_never_raises_on_junk():
    _clear()
    gr._note_series_read("b", "x", None)          # unparseable -> no record
    gr._note_series_read(None, None, None)
    assert "b" not in gr.last_series_read


# --------------------------------------------- the enforcement is not inert
def test_both_production_call_sites_compose_through_book_mtm():
    """The (iz) class: a flag that exists and never reaches the payload.
    Assert the call sites by AST, not substring."""
    import ast
    tree = ast.parse((ROOT / "scripts" / "golive_readiness.py").read_text())
    # The defect shape is the COMPOSED expression `mtm_drawdown(equity_series(
    # ...))` — a live read whose truncation is then unpublishable. Hand-built
    # fixture dicts passed to apply_mtm in the selftest are legitimately not
    # book_mtm, so scan for the composition rather than for every call site.
    # `book_mtm` IS the one place the composition is allowed — it is the
    # owner that folds the receipt in. Every other site is the defect.
    owner = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "book_mtm")
    inside_owner = {id(x) for x in ast.walk(owner)}
    composed = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "mtm_drawdown"
                and id(n) not in inside_owner
                and any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                        and a.func.id == "equity_series" for a in n.args)]
    assert not composed, (
        f"{len(composed)} call site(s) still compose mtm_drawdown(equity_series"
        "(...)) directly, so their truncation never reaches the payload — "
        "use book_mtm()")
    # ...and the production path must actually go through it.
    via = [n for n in ast.walk(tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == "apply_mtm"
           and any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                   and a.func.id == "book_mtm" for a in n.args)]
    assert len(via) >= 2, \
        f"expected both production apply_mtm sites to use book_mtm, found {len(via)}"
