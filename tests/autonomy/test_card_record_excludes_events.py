"""THE DASHBOARD SHOWED EAMON PHANTOM LOSSES ON HIS REAL-MONEY BOOKS — (vm).

`(tw)` established the defect and fixed the OWNER (`bot_pnl_store.is_non_economic`)
and the book's own boot seed (`fetch_paper_aggregate`): a daily-loss halt
flattens positions with no entry basis and no P&L, `publish_paper_trade` wrote
those EVENTS into the closed-trade ledger as TRADES, and `losses = closed - wins`
counted every one as a LOSS.

It did not fix the DASHBOARD, which is the thing Eamon actually looks at.
Measured 27-Aug: `grep -c is_non_economic pnl_dashboard.py` = **0** against 4
hits in the owner, and the cards read

    🙏 avo      15 closes / 5W / **10L**   honest record: 6 / 5 / 1
    🔮 georgia  60 closes / 27W / **33L**  honest record: 56 / 27 / 29

Nine and four phantom losses, on real money, on the fleet's whole reporting
surface.

WHAT THESE TESTS PIN, in the order the risk actually runs:
  1. the EVENTS come out (the defect), and
  2. nothing else does — a real forced-flatten loss, a funding book's
     price-free accrual row, a genuinely flat close and every `bot_trades`
     row all stay in, because a filter that shrinks a real-money sample it
     cannot justify shrinking is the disease and not the cure; and
  3. the fix is a LOOKUP of the one owner, not a second copy of its rule.
"""
import pnl_dashboard as D
import bot_pnl_store as store


# --------------------------------------------------------------- the fixtures

def _event(bot="freqtrade-avo-maria-lighter", **kw):
    """A daily-loss FLATTEN row: no entry basis, no P&L, no funding form.
    This is the legacy-bridge shape — the 13 rows (tw) measured fleet-wide,
    which predate the (th) marker and carry nothing but their own emptiness."""
    r = {"bot": bot, "pnl": 0.0, "entry_price": None, "extra": {},
         "in_today": False, "in_7d": True, "in_30d": True}
    r.update(kw)
    return r


def _marked(bot="freqtrade-mum-lighter", **kw):
    """The forward CONTRACT: the (th) write-site marker, which needs no
    signature match at all."""
    return _event(bot, extra={"non_economic": True}, **kw)


def _flat_trade(bot="freqtrade-georgia-lighter", **kw):
    """A REAL close that happened to land on exactly $0.00. It trips the cheap
    SQL candidate test and it is a trade, so the owner must hand it back."""
    return _event(bot, entry_price=2500.05, **kw)


def _agg_record(n, w, total, **kw):
    """What the aggregate leaves behind for a bot, pre-fold — `events` already
    present at 0 because absent and zero are different states."""
    rec = {"n": n, "w": w, "l": n - w, "total": total, "events": 0}
    rec.update(kw)
    return rec


# ============================================================ THE DECISION SEAM
# `fold_ledger_candidates` is where the SQL results become `record`, and every
# one of these drives the REAL `bot_pnl_store.is_non_economic`.

def test_avos_nine_phantom_losses_come_off_the_card():
    """The measured defect, at the seam that renders it. 15 / 5W / 10L was the
    card; 6 / 5 / 1 is the book."""
    out = {"freqtrade-avo-maria-lighter": {"record": _agg_record(6, 5, 16.97)}}
    D.fold_ledger_candidates(out, [_event() for _ in range(9)])
    rec = out["freqtrade-avo-maria-lighter"]["record"]
    assert (rec["n"], rec["w"], rec["l"]) == (6, 5, 1)
    assert rec["events"] == 9
    # an event's P&L is 0.00 BY DEFINITION, so only the COUNTS move — the same
    # stance `fetch_paper_aggregate` takes, and for the same reason.
    assert rec["total"] == 16.97


def test_georgias_four_phantom_losses_come_off_the_card():
    out = {"freqtrade-georgia-lighter": {"record": _agg_record(56, 27, -41.2)}}
    D.fold_ledger_candidates(
        out, [_event(bot="freqtrade-georgia-lighter") for _ in range(4)])
    rec = out["freqtrade-georgia-lighter"]["record"]
    assert (rec["n"], rec["w"], rec["l"]) == (56, 27, 29)
    assert rec["events"] == 4


def test_the_th_marker_is_honoured_on_the_card_too():
    """No DB row carries the marker yet; the day one does, the card must read
    it without the legacy bridge having to fire."""
    out = {"freqtrade-mum-lighter": {"record": _agg_record(4, 3, 5.0)}}
    D.fold_ledger_candidates(out, [_marked()])
    assert out["freqtrade-mum-lighter"]["record"]["events"] == 1
    assert out["freqtrade-mum-lighter"]["record"]["n"] == 4


# ------------------------------- what must NEVER be taken off a real-money card

def test_a_real_forced_flatten_loss_stays_on_the_card():
    """🔮 georgia's 25-Aug rail closed five REAL positions for -$30.96 and her
    22-Aug TRX -$3.87 is a real forced flatten. The reason string is
    `daily_loss` on BOTH; the BASIS is what separates them, and these are
    losses the book genuinely took."""
    real = [_event(bot="freqtrade-georgia-lighter", pnl=p, entry_price=e)
            for p, e in ((-3.04, 2500.05), (-8.42, 1.518757),
                         (-6.64, 11.78749), (-3.20, 7.6169),
                         (-9.66, 1.97479), (-3.87, 0.3509))]
    out = {"freqtrade-georgia-lighter": {"record": _agg_record(50, 27, 0.0)}}
    D.fold_ledger_candidates(out, real)
    rec = out["freqtrade-georgia-lighter"]["record"]
    assert rec["events"] == 0, "a real forced-flatten loss was erased"
    # they carry a P&L, so they are not even candidates in production; folded
    # here they must land as LOSSES, not vanish.
    assert (rec["n"], rec["w"], rec["l"]) == (56, 27, 29)


def test_a_funding_books_price_free_row_is_a_trade():
    """Funding books legitimately record NO price — they book accrual. They are
    the population a naive signature would eat, and `_FUNDING_FORM` is what
    makes their safety structural rather than lucky."""
    for key in store._FUNDING_FORM:
        out = {"perps-funding-carry-lshadow": {"record": _agg_record(10, 4, 3.0)}}
        D.fold_ledger_candidates(
            out, [_event(bot="perps-funding-carry-lshadow", extra={key: 0.3})])
        rec = out["perps-funding-carry-lshadow"]["record"]
        assert rec["events"] == 0, f"a funding row carrying {key} was erased"
        assert rec["n"] == 11


def test_a_close_that_landed_exactly_flat_is_still_a_trade():
    """pnl == 0 is the cheap CANDIDATE test, never the verdict. With an entry
    price the row has a basis and the owner hands it back."""
    out = {"freqtrade-georgia-lighter": {"record": _agg_record(55, 27, -41.2)}}
    D.fold_ledger_candidates(out, [_flat_trade()])
    rec = out["freqtrade-georgia-lighter"]["record"]
    assert rec["events"] == 0
    assert (rec["n"], rec["w"], rec["l"]) == (56, 27, 29)


# --------------------------------------------------- the figures that ride along

def test_best_and_worst_exclude_events():
    """Extrema cannot be repaired by subtraction the way a count can. On an
    all-WINNING book a $0.00 halt event becomes the "worst trade" — a phantom
    with a dollar sign on it."""
    out = {"freqtrade-mum-lighter": {"record": _agg_record(3, 3, 12.0),
                                     "best_trade": 7.0, "worst_trade": 2.0}}
    D.fold_ledger_candidates(out, [_event(bot="freqtrade-mum-lighter")])
    b = out["freqtrade-mum-lighter"]
    assert b["worst_trade"] == 2.0, "a $0.00 halt event became the worst trade"
    assert b["best_trade"] == 7.0


def test_the_7d_and_30d_counters_are_repaired_too():
    """`n_7d`/`n_30d` exist so a window with NO closes stays distinguishable
    from one that closed exactly flat — which is the very confusion a halt
    event manufactures."""
    out = {"freqtrade-avo-maria-lighter": {
        "record": _agg_record(6, 5, 16.97),
        "n_7d": 2, "pnl_7d": 4.0, "n_30d": 6, "pnl_30d": 16.97,
        "today_n": 0, "today_closed": 0.0}}
    D.fold_ledger_candidates(out, [_event(in_today=True) for _ in range(9)])
    b = out["freqtrade-avo-maria-lighter"]
    assert (b["n_7d"], b["n_30d"], b["today_n"]) == (2, 6, 0), \
        "halt events were counted as closes in a P&L window"
    assert b["pnl_7d"] == 4.0


def test_an_admitted_candidate_is_folded_back_into_every_window():
    """The other half: a real trade the cheap test could not settle was
    EXCLUDED from the aggregate, so it has to be put back — into the counts,
    the sums and the extrema alike, or the fix trades one wrong number for
    another."""
    out = {"freqtrade-georgia-lighter": {
        "record": _agg_record(55, 27, -41.2),
        "n_7d": 3, "pnl_7d": -5.0, "n_30d": 20, "pnl_30d": -30.0,
        "today_n": 1, "today_closed": -2.0,
        "best_trade": 9.0, "worst_trade": -8.0}}
    D.fold_ledger_candidates(out, [_flat_trade(in_today=True)])
    b = out["freqtrade-georgia-lighter"]
    assert b["record"]["n"] == 56
    assert (b["n_7d"], b["n_30d"], b["today_n"]) == (4, 21, 2)
    assert (b["pnl_7d"], b["pnl_30d"], b["today_closed"]) == (-5.0, -30.0, -2.0)
    assert (b["best_trade"], b["worst_trade"]) == (9.0, -8.0)


def test_a_book_whose_every_row_was_a_candidate_still_gets_a_record():
    """`WHERE NOT cand` means such a book is absent from the aggregate
    entirely. It must read `0 closed · N halt events`, never disappear — the
    card losing a real-money book is a worse failure than the one being
    fixed."""
    out = {}
    D.fold_ledger_candidates(out, [_event() for _ in range(9)])
    rec = out["freqtrade-avo-maria-lighter"]["record"]
    assert (rec["n"], rec["w"], rec["l"], rec["events"]) == (0, 0, 0, 9)


def test_events_is_always_published_never_absent():
    """0 and absent are different states and only one of them means "nothing
    was withheld" — the I1 shape at the reporting layer."""
    out = {"freqtrade-mum-lighter": {"record": _agg_record(4, 3, 5.0)}}
    D.fold_ledger_candidates(out, [])
    assert out["freqtrade-mum-lighter"]["record"]["events"] == 0


# ==================================================================== FAIL-OPEN
# The defect being repaired is a count that was too BIG. The defect this must
# never introduce is one that is too SMALL.

def test_no_owner_degrades_the_card_to_its_pre_vm_numbers(monkeypatch):
    """If `bot_pnl_store` ever leaves the dashboard image, every candidate is
    ADMITTED and avo reads 15 / 5 / 10 again — wrong, and exactly as wrong as
    it was yesterday. A reporting fix may not cost a book its rows."""
    monkeypatch.setattr(D, "_non_economic_owner", lambda: None)
    out = {"freqtrade-avo-maria-lighter": {"record": _agg_record(6, 5, 16.97)}}
    D.fold_ledger_candidates(out, [_event() for _ in range(9)])
    rec = out["freqtrade-avo-maria-lighter"]["record"]
    assert (rec["n"], rec["w"], rec["l"]) == (15, 5, 10)
    assert rec["events"] == 0


def test_a_predicate_that_raises_admits_the_row(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("unreadable row")
    monkeypatch.setattr(D, "_non_economic_owner", lambda: _boom)
    out = {"freqtrade-mum-lighter": {"record": _agg_record(4, 3, 5.0)}}
    D.fold_ledger_candidates(out, [_event(bot="freqtrade-mum-lighter")])
    rec = out["freqtrade-mum-lighter"]["record"]
    assert rec["events"] == 0 and rec["n"] == 5


def test_an_unkeyable_row_cannot_corrupt_the_map():
    out = {}
    D.fold_ledger_candidates(out, [_event(bot=None)])
    assert out == {}


# ======================================================== ONE OWNER, ONE RULE
# (hj): pin re-use by IDENTITY. A name check stays green against a hand-rolled
# copy, and a second copy of a rule is a second rule.

def test_the_dashboard_uses_the_owner_itself_not_a_copy():
    assert D._non_economic_owner() is store.is_non_economic


def test_the_dashboard_re_expresses_no_part_of_the_predicate():
    """The owner's verdict rests on `non_economic`, `_FUNDING_FORM` and the
    entry-price/P&L conjunction. None of those may be RE-DECIDED here — the
    dashboard's only mention of the funding form or the marker is inside a
    SQL CANDIDATE narrowing or a comment, never a branch."""
    import ast
    fold = next(n for n in ast.walk(ast.parse(open(D.__file__).read()))
                if isinstance(n, ast.FunctionDef)
                and n.name == "fold_ledger_candidates")
    # STRING CONSTANTS only, and the docstring dropped — the rule's substance
    # is its key names, and a name check over the whole dump matches the
    # resolver `_non_economic_owner` and passes for the wrong reason.
    literals = {n.value for n in ast.walk(ast.Module(body=fold.body[1:],
                                                     type_ignores=[]))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for token in store._FUNDING_FORM + ("non_economic",):
        assert token not in literals, \
            f"the fold re-expresses the owner's rule ({token!r}) instead of asking it"


# ============================================================== THE SQL WIRING
# `fold_ledger_candidates` is only right if the aggregate actually WITHHELD the
# rows it folds. These drive the real `fetch_ledger_enrich` against a fake
# connection so the two queries are checked for complementarity and for reading
# the SAME declarations.

class _Cur:
    """Just enough cursor to record the SQL and hand back canned rows."""

    def __init__(self, plan):
        self._plan, self._rows, self.sql = plan, [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append(sql)
        for key, rows in self._plan:
            if key in sql:
                self._rows = rows
                return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self, **kw):
        return self._cur

    def close(self):
        pass


def _drive(monkeypatch, agg_rows, cand_rows):
    """Run the REAL `fetch_ledger_enrich` against a fake DB. Returns (out, cur)."""
    import psycopg2
    cur = _Cur([
        ("to_regclass", [{"t1": "bot_trades", "t2": "paper_trades",
                          "t3": None, "t4": None}]),
        ("WHERE NOT cand GROUP BY bot", agg_rows),
        ("FROM t WHERE cand", cand_rows),
        ("DISTINCT ON (bot)", []),
    ])
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _Conn(cur))
    D._ENRICH_CACHE["ts"] = 0.0          # the 20s cache would serve a stale map
    return D.fetch_ledger_enrich(), cur


def _agg_row(bot, n, w, total):
    return {"bot": bot, "n": n, "w": w, "total": total,
            "today_closed": 0, "today_n": 0, "pnl_7d": total, "n_7d": n,
            "pnl_30d": total, "n_30d": n, "best": 9.0, "worst": -8.0}


def test_end_to_end_the_feed_publishes_the_honest_record(monkeypatch):
    """`enrich.record` is what /pnl.json serves and what the card renders. The
    live payload read {'n': 15, 'w': 5, 'l': 10, 'total': 16.97}."""
    out, _ = _drive(
        monkeypatch,
        [_agg_row("freqtrade-avo-maria-lighter", 6, 5, 16.97)],
        [_event() for _ in range(9)])
    rec = out["freqtrade-avo-maria-lighter"]["record"]
    assert (rec["n"], rec["w"], rec["l"], rec["events"]) == (6, 5, 1, 9)
    assert rec["total"] == 16.97


def test_the_aggregate_withholds_exactly_what_the_candidate_query_takes(monkeypatch):
    """Complementarity. `WHERE NOT cand` and `WHERE cand` partition the union,
    so no row is counted twice and — the direction that would be silent — none
    falls out of both."""
    _, cur = _drive(monkeypatch, [], [])
    agg = next(s for s in cur.sql if "GROUP BY bot" in s)
    cand = next(s for s in cur.sql if "in_today" in s)
    assert "FROM t WHERE NOT cand GROUP BY bot" in agg
    assert "FROM t WHERE cand" in cand
    assert "WHERE NOT cand" not in cand


def test_both_queries_read_the_one_candidate_declaration(monkeypatch):
    """The drift guard: inline the expression in either query and the sentinel
    stops appearing. Two copies of the narrowing would let the aggregate and
    the fold disagree about which rows are in play."""
    monkeypatch.setattr(D, "_LEDGER_CAND_SQL", "SENTINEL_CAND_EXPR")
    _, cur = _drive(monkeypatch, [], [])
    for label, needle in (("aggregate", "GROUP BY bot"), ("candidate", "in_today")):
        sql = next(s for s in cur.sql if needle in s)
        assert "SENTINEL_CAND_EXPR" in sql, \
            f"the {label} query does not read _LEDGER_CAND_SQL"


def test_both_queries_read_the_one_window_declaration(monkeypatch):
    """Written twice, the two would drift a day apart at a daylight boundary
    and a row would be inside the aggregate's 7d and outside the fold's."""
    monkeypatch.setattr(D, "_W_7D", "SENTINEL_7D")
    _, cur = _drive(monkeypatch, [], [])
    for needle in ("GROUP BY bot", "in_today"):
        sql = next(s for s in cur.sql if needle in s)
        assert "SENTINEL_7D" in sql


def test_bot_trades_can_never_become_a_candidate(monkeypatch):
    """`bot_trades` has no `extra` column — checked: not one ALTER TABLE on it
    in the tree — so it cannot carry the (th) marker. Supplying NULLs alone
    would make each of its FLAT closes look exactly like a halt event and
    delete real freqtrade trades; `FALSE AS cand` is what withholds them from
    the question entirely."""
    _, cur = _drive(monkeypatch, [], [])
    union = next(s for s in cur.sql if "UNION ALL" in s)
    branch = union.split("UNION ALL")[0]
    assert "FROM bot_trades" in branch
    assert "FALSE AS cand" in branch, \
        "bot_trades is being offered to a predicate it cannot answer"


def test_a_null_cand_can_never_swallow_a_row(monkeypatch):
    """With `pnl_abs` NULL and no marker the bare OR is NULL, and a NULL `cand`
    satisfies neither `WHERE cand` nor `WHERE NOT cand` — the row would fall
    out of BOTH queries and vanish from the card. Unknown means "keep it"."""
    _, cur = _drive(monkeypatch, [], [])
    union = next(s for s in cur.sql if "UNION ALL" in s)
    branch = union.split("UNION ALL")[-1]
    assert f"COALESCE({D._LEDGER_CAND_SQL}, FALSE)" in branch


def test_last_close_is_deliberately_unfiltered(monkeypatch):
    """It answers "what did this book last DO?", a LIVENESS question (I1).
    Hiding a halt there would leave a book that flattened this morning showing
    a days-old close and looking like it merely went quiet."""
    _, cur = _drive(monkeypatch, [], [])
    last = next(s for s in cur.sql if "DISTINCT ON (bot)" in s)
    assert "WHERE NOT cand" not in last and "WHERE cand" not in last
