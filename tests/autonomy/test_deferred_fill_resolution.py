"""[2026-09-03 (xt)] LIVE EXECUTION WAS MEASURED ON A NON-RANDOM 42%.

MEASURED on the live feed, 2-Sep (`impl-shortfall.order_slip`):

    live   orders 151   with_slip  63   echoed_decision 88
    shadow orders 134   with_slip 134   echoed_decision  0

and the skip reason on 82 of them was, verbatim:

    skipped:budget(0.9 tok, reserve 6.0) after
    api-error:trades:VenueError:lighter tx budget exhausted; skipping

The fill read fires immediately after submission, when the governor's bucket is
at its emptiest (an order costs WEIGHT_ORDER_TX=6 of ~21), so BOTH tapes are
declined and the order is recorded honestly as UNMEASURED with
`px_fill = px_decision`. Nothing lies — but live slippage (-3.24bps) is then an
average over the 42% of orders that happened to fall in a calm moment, while
the 58% that were skipped are the busiest ones, where slippage actually lives.
The shadow twin measures 134 of 134, so the two arms were never comparable —
and 👩 mum's live arm trails her own twin by 0.358pp/trade.

WHAT IS *NOT* CHANGED, and it is the whole safety of this: the order path.
`venues/fills.py` rules that an IMMEDIATE retry on `skipped:budget` is wrong —
it "spends the governor's telemetry reserve to fail identically" — and that is
exactly right for the same breath. This is the other case: minutes later,
against a REFILLED bucket, where the premise "to fail identically" is false.
Spare budget only, bounded, and the execution LEDGER alone is corrected —
never a position entry, never a booked P&L.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from venues.order_keys import fill_key            # noqa: E402
import venues.lighter_client as lc                # noqa: E402


# ------------------------------------------------------- the identity is ONE
def test_the_key_has_exactly_one_owner():
    """A second copy of this rule would key the queue one way and the ledger
    another: every resolution misses its row, silently, while both sides look
    correct. Identity, not equality ((hj))."""
    import lighter_avo_live_bot as host
    assert lc.fill_key is fill_key
    assert host.fill_key is fill_key
    src = (ROOT / "venues" / "lighter_client.py").read_text()
    assert "\ndef fill_key(" not in src, "client re-defined the key rule"


def test_tx_hash_is_senior_and_an_unnamed_order_is_None():
    assert fill_key(7, "0xabc") == "tx:0xabc"     # settled tx beats intent
    assert fill_key(7, None) == "cid:7"
    assert fill_key(0, None) == "cid:0"           # 0 is an id, not absence
    assert fill_key(None, None) is None           # never invent a key


# ------------------------------------------------------------- the queueing
class _Gov:
    def __init__(self, tokens): self.tokens = tokens
    class _L:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    _lock = _L()
    def _refill(self): pass


def _client(tokens=0.9):
    c = lc.LighterClient.__new__(lc.LighterClient)
    c._pending_fills = lc.OrderedDict()
    c.gov = _Gov(tokens)
    c.signer, c.account_index = object(), 1
    c.api_key_index = 0
    c._drain_last_error = None
    # the real client builds this in __init__; __new__ skips it, and leaving it
    # off made the drain raise AttributeError into its own swallow — a stub gap
    # that read exactly like a code bug (stubs encode the assumption under test)
    c._order_api = type("A", (), {"trades": staticmethod(lambda **k: None)})()
    return c


@pytest.mark.parametrize("reason", [
    "skipped:budget(0.9 tok, reserve 6.0) after api-error:trades:VenueError:"
    "lighter tx budget exhausted; skipping",
    "api-error:recentTrades:VenueError:boom (after trades-empty)",
])
def test_an_unread_tape_is_queued(reason):
    c = _client()
    c._defer_fill(reason, "BTC", False, 1000.0, 7, "0xabc")
    assert list(c._pending_fills) == ["tx:0xabc"]


@pytest.mark.parametrize("reason", [
    "no-match:both(no-match:trades)", "empty:both(trades-empty)",
    "trades(tx)", "auth-failed:empty-token", None, "",
])
def test_a_tape_that_WAS_read_is_never_queued(reason):
    """`venues/fills.py`'s rule, preserved: a no-match means the tape was read
    and our fill was not on it. Re-reading does not change that, and queueing
    it would burn the telemetry reserve to fail identically."""
    c = _client()
    c._defer_fill(reason, "BTC", False, 1000.0, 7, "0xabc")
    assert c._pending_fills == {}


def test_an_unnamed_order_is_not_queued():
    c = _client()
    c._defer_fill("skipped:budget(0.1 tok, reserve 6.0)", "BTC", False,
                  1000.0, None, None)
    assert c._pending_fills == {}


def test_the_queue_is_bounded_and_evicts_oldest_first():
    c = _client()
    for i in range(lc._PENDING_FILL_MAX + 12):
        c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, i, None)
    assert len(c._pending_fills) == lc._PENDING_FILL_MAX
    assert "cid:0" not in c._pending_fills          # oldest evicted
    assert f"cid:{lc._PENDING_FILL_MAX + 11}" in c._pending_fills


def test_defer_never_raises_on_junk():
    c = _client()
    for args in [("skipped:budget", None, None, None, 1, None),
                 ("skipped:budget", "BTC", False, "not-a-float", 1, None)]:
        c._defer_fill(*args)      # must not raise


# --------------------------------------------------------------- the draining
def test_the_drain_spends_SPARE_BUDGET_ONLY():
    """THE load-bearing property: the invariant that caused the skip in the
    first place ("telemetry must never starve an order") is not traded away.
    With an empty bucket the drain must touch the venue ZERO times and keep the
    entry for a later cycle.

    COUNT the calls — never `pytest.fail` inside the stub. The code under test
    swallows exceptions by design, so a raising stub is swallowed and the
    assertion passes vacuously. Caught by mutation: deleting the budget guard
    entirely left this test GREEN until it was rewritten this way."""
    c = _client(tokens=0.9)                        # spare = 0.9 - 6.0 < 0
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    calls = []
    c._resolve = lambda coin: (calls.append("resolve"), ("BTC", 1.0, {"id": 1}))[1]
    c._run = lambda *a, **k: calls.append("venue")
    assert c.drain_pending_fills() == []
    assert calls == [], f"drain spent budget it did not have: {calls}"
    assert "tx:0xabc" in c._pending_fills, "entry must survive for a retry"
    assert c._pending_fills["tx:0xabc"]["tries"] == 0, \
        "a cycle with no budget must not burn a try"


def test_a_resolved_fill_leaves_the_queue_and_is_returned():
    c = _client(tokens=50.0)
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    c._resolve = lambda coin: ("BTC", 1.0, {"id": 1})
    c.api_key_index = 0
    c.signer = type("S", (), {
        "create_auth_token_with_expiry": lambda *a, **k: ("tok", None)})()
    c._run = lambda *a, **k: type("R", (), {"trades": [{"x": 1}]})()
    c._our_fills = lambda *a, **k: 123.5
    out = c.drain_pending_fills()
    assert len(out) == 1 and out[0]["px"] == 123.5
    assert out[0]["key"] == "tx:0xabc" and "deferred" in out[0]["reason"]
    assert c._pending_fills == {}


def test_an_entry_is_given_up_after_its_tries_and_never_loops_forever():
    c = _client(tokens=50.0)
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    c._resolve = lambda coin: ("BTC", 1.0, {"id": 1})
    c.api_key_index = 0
    c.signer = type("S", (), {
        "create_auth_token_with_expiry": lambda *a, **k: ("tok", None)})()
    c._run = lambda *a, **k: type("R", (), {"trades": []})()
    c._our_fills = lambda *a, **k: None
    for _ in range(lc._PENDING_FILL_TRIES):
        assert c.drain_pending_fills() == []
    assert c._pending_fills == {}, "unresolvable entry must be dropped"


def test_an_expired_entry_is_dropped_without_spending_budget():
    c = _client(tokens=50.0)
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    c._pending_fills["tx:0xabc"]["queued_at"] -= lc._PENDING_FILL_TTL_S + 10
    calls = []
    c._run = lambda *a, **k: calls.append("venue")     # count, never raise
    assert c.drain_pending_fills() == []
    assert calls == [], "spent budget re-reading a tape the fill has left"
    assert c._pending_fills == {}


def test_the_drain_never_raises_and_is_inert_without_a_signer():
    c = _client(tokens=50.0)
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    c.signer = None
    assert c.drain_pending_fills() == []           # inert, no exception
    c.signer, c.account_index = object(), 1
    c._resolve = lambda coin: (_ for _ in ()).throw(RuntimeError("boom"))
    assert c.drain_pending_fills() == []           # swallowed


# ------------------------------------------- the ledger correction is bounded
def test_the_update_is_idempotent_and_scoped_to_the_execution_ledger():
    """A repeated drain must not double-apply, and a fill learned late must
    NEVER restate a position entry or a booked close — the book was already
    graded on those."""
    import inspect
    import bot_pnl_store as store
    src = inspect.getsource(store.resolve_venue_order_fill)
    # the EXACT guard clause — "IS NULL" alone also matches the unrelated
    # px_decision check below it, which mutation showed made this vacuous
    assert "raw::jsonb->>'fill_resolved') IS NULL" in src, \
        "a repeated drain can overwrite or double-apply a resolution"
    assert "UPDATE venue_orders" in src
    for forbidden in ("paper_trades", "bot_pnl", "INSERT"):
        assert forbidden not in src, f"touches {forbidden} — out of scope"
    assert "slippage_bps = CASE" in src, "slip must be derived in SQL"


def test_slippage_is_derived_from_the_rows_own_decision_price():
    """Both live legs reduce to (fill-dec)/dec*1e4; a caller-passed value would
    be a second copy of one formula with two chances to invert a sign."""
    import inspect
    import bot_pnl_store as store
    assert "slippage_bps" not in inspect.signature(
        store.resolve_venue_order_fill).parameters


def test_the_host_stamps_order_key_on_BOTH_legs():
    """Without the key on the row there is nothing to resolve against — and
    the open leg and the close leg are two separate call sites, so a fix that
    lands on one is half a fix."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert src.count('"order_key": fill_key(') == 2, \
        "order_key must be stamped on both the open and the close leg"


def test_the_host_actually_CALLS_the_drain_and_writes_it_back():
    """The (iz) class: an enforcement that exists and never runs.

    Asserted on the AST, not a substring. Mutation proved the substring form
    vacuous: neutering the call to `[]` left the NAME in the source (inside the
    `getattr` guard beside it) and the grep stayed green while the drain was
    dead ([[a-substring-test-is-not-a-wiring-test]])."""
    import ast
    tree = ast.parse((ROOT / "lighter_avo_live_bot.py").read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "drain_pending_fills" in called, \
        "the drain is named but never invoked — fills queue and rot"
    assert "resolve_venue_order_fill" in called, \
        "the drain runs and its result is never written back"


def test_a_swallowed_drain_error_is_RECORDED_not_silent():
    """A fail-open except is a silent kill switch. Telemetry must not raise
    into a trading loop — but a swallowed bug here returns `[]` forever, which
    is byte-identical to 'nothing was pending'. Caught during this change's own
    development, when an incomplete stub made the drain raise into its own
    swallow and read exactly like a code defect."""
    c = _client(tokens=50.0)
    c._defer_fill("skipped:budget(x)", "BTC", False, 1000.0, 7, "0xabc")
    c._resolve = lambda coin: (_ for _ in ()).throw(RuntimeError("boom"))
    c.drain_pending_fills()
    # a per-entry failure is counted against its tries, not swallowed globally
    assert c._pending_fills["tx:0xabc"]["tries"] == 1

    del c.gov                       # force the OUTER swallow
    assert c.drain_pending_fills() == []
    assert c._drain_last_error and "AttributeError" in c._drain_last_error, \
        "the outer swallow must leave a readable reason"


def test_the_host_surfaces_that_recorded_silence():
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "_drain_last_error" in src, \
        "the client records why it went quiet and nothing reads it"
