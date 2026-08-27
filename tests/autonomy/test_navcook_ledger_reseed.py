"""🧭 nav-cook's counters must recover the record (sa)'s fix could not.

(sa) made `realized`/`n_closed`/`n_wins` PERSIST; it could not restore the 34
closes already lost to the restarts before it. The row kept publishing
`closed_trades: 3 / pnl_abs: -5.82 / equity: 994.18` against its own ledger's
**37 closes / -$9.62** — overstating equity by $3.80 and disagreeing with
every organ that grades the ROW (golive_readiness, fleet_allocation, the
horizon sweep).

The load-bearing property is the DIRECTION: the ledger may only ever RAISE
these counters, so a short read can never turn a recovery into data loss.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = (ROOT / "lighter_nav_cook_bot.py").read_text()


def _reseed(persisted, agg):
    """The shipped adopt-on-more rule, evaluated exactly as the module runs
    it. Kept as a local model ONLY because main() is an infinite trading
    loop that cannot be called in a test; the AST tests below pin that the
    module really contains this shape rather than trusting the model."""
    realized, n_closed, n_wins = persisted
    if agg and int(agg.get("closed") or 0) > n_closed:
        realized = float(agg.get("realized") or 0.0)
        n_wins = int(agg.get("wins") or 0)
        n_closed = int(agg["closed"])
    return realized, n_closed, n_wins


# ------------------------------------------------------ the recovery itself
def test_the_live_defect_is_repaired():
    """The measured numbers: row 3 closes / -$5.82 vs a 37-close / -$9.62
    ledger."""
    out = _reseed((-5.82, 3, 1),
                  {"realized": -9.62, "closed": 37, "wins": 12, "losses": 25})
    assert out == (-9.62, 37, 12)


# --------------------------------- the direction that makes it safe to ship
def test_a_SHORT_ledger_read_can_never_shrink_the_record():
    """A partial fetch, a filtered window or a DB blip must not turn a
    recovery into the data loss it repairs."""
    persisted = (-9.62, 37, 12)
    for agg in ({"realized": 0.0, "closed": 0, "wins": 0},
                {"realized": -1.0, "closed": 3, "wins": 1},
                {"realized": -9.0, "closed": 36, "wins": 11}):
        assert _reseed(persisted, agg) == persisted, \
            f"a ledger reading {agg['closed']} must not overwrite 37"


def test_a_dark_or_junk_aggregate_keeps_the_persisted_record():
    persisted = (-9.62, 37, 12)
    for agg in (None, {}, {"closed": None}):
        assert _reseed(persisted, agg) == persisted


def test_an_equal_ledger_is_not_adopted():
    """Strictly-greater, so a steady state does not rewrite itself every boot."""
    persisted = (-9.62, 37, 12)
    assert _reseed(persisted, {"realized": -1.0, "closed": 37, "wins": 1}) \
        == persisted


def test_a_fresh_book_adopts_its_whole_ledger():
    assert _reseed((0.0, 0, 0),
                   {"realized": -9.62, "closed": 37, "wins": 12}) \
        == (-9.62, 37, 12)


# ------------------------------------------- the module really does this
def test_the_module_calls_the_fleets_recovery_owner_not_a_local_count():
    """`fetch_paper_aggregate` is quarantine- and event-filtered ((tw)), so
    it returns the ADMISSIBLE record. A hand-rolled `SELECT count(*)` here
    would re-seed the very phantom rows (tw) removed — a second copy of the
    rule ((hj))."""
    assert "store.fetch_paper_aggregate(bot_id)" in SRC
    for banned in ("SELECT count(*) FROM paper_trades",
                   "select count(*) from paper_trades"):
        assert banned not in SRC, "must not re-derive the count locally"


def test_the_adoption_is_guarded_by_a_STRICTLY_GREATER_comparison():
    """AST-shaped: pin the comparison operator itself, because the whole
    safety of this is the direction. A substring test would pass against
    `>=`, `<`, or a bare `if _agg:`."""
    tree = ast.parse(SRC)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        seg = ast.get_source_segment(SRC, node) or ""
        if "_agg" in seg and "closed" in seg and "n_closed" in seg:
            found.append((type(node.ops[0]).__name__, seg))
    assert found, "no _agg[closed] vs n_closed comparison found at all"
    assert all(op == "Gt" for op, _ in found), \
        f"the re-seed must be strictly-greater, got {found}"


def test_the_reseed_failure_path_keeps_trading():
    """A recovery that raises must not take the book down with it — the
    counters are a RECORD, and a book that cannot read them still trades."""
    tree = ast.parse(SRC)
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        body = ast.get_source_segment(SRC, node) or ""
        if "fetch_paper_aggregate" in body and node.handlers:
            guarded = True
    assert guarded, "the ledger re-seed must sit inside a try/except"
