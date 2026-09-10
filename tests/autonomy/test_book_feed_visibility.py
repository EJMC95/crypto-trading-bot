"""[(aak)] Which book is real money pricing off — the websocket, or REST?

`venues/lighter_client` falls back from the order-book websocket to governed
REST snapshots when the venue CDN blocks this host. That is CORRECT and
designed. It was also INVISIBLE: the watcher logs it once per process behind
`degraded_logged` — I4's named anti-pattern, "never report a persistent
condition with a one-shot warning" — and `orderbook()` falls back silently. Both
live books price against this client, so "are 👩 mum and 🙏 avo on the websocket
or on REST?" was not answerable from any feed.

The connection state alone is not the useful number; what a reader cares about
is what the book actually PRICED off, so the counts come from `orderbook()`
itself and cannot drift from what was served.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]
import venues.lighter_client as LC  # noqa: E402


def _client(src=None, health=None):
    c = LC.LighterClient.__new__(LC.LighterClient)
    c._books = LC._BookCache("https://example.invalid")
    if health is not None:
        c._books._ws_health = health
    c._book_src = dict(src or {"ws": 0, "rest": 0})
    return c


def test_a_cold_client_reports_unknown_not_healthy():
    h = _client().ws_health()
    assert h["ok"] is False and h["reads"]["rest_pct"] is None, h


def test_the_read_split_is_what_a_reader_actually_needs():
    h = _client({"ws": 3, "rest": 97}).ws_health()
    assert h["reads"] == {"ws": 3, "rest": 97, "rest_pct": 97.0}


def test_a_healthy_socket_says_so():
    """The positive control: this must be able to report GOOD news, or a test
    that only ever sees the degraded state proves nothing about the accessor."""
    c = _client({"ws": 50, "rest": 0},
                {"ok": True, "fails": 0, "last_ok": 1.0, "why": None, "books": 6})
    h = c.ws_health()
    assert h["ok"] is True and h["why"] is None and h["books"] == 6, h
    assert h["reads"]["rest_pct"] == 0.0


def test_the_accessor_never_raises():
    """It runs inside a real-money publish. An accessor that can break the row
    is worse than the blindness it fixes."""
    c = _client()
    c._books = object()                      # no _ws_health at all
    assert c.ws_health()["ok"] is False
    c._book_src = None                       # and no counters either
    assert c.ws_health()["ok"] is False


def test_the_failure_reason_is_a_class_never_the_raw_exception():
    """bot_pnl rows reach the public /pnl.json. An exception string can carry a
    URL or a header."""
    src = (ROOT / "venues" / "lighter_client.py").read_text()
    assert "type(e).__name__" in src
    assert '"why": str(e)' not in src and '"why": repr(e)' not in src


def test_orderbook_counts_both_paths_at_the_site_that_serves_them():
    """Counting anywhere else lets the ratio drift from what was served."""
    src = (ROOT / "venues" / "lighter_client.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "orderbook")
    body = ast.dump(fn)
    assert '_book_src' in body, "orderbook() must record which path it served"
    assert body.count("'ws'") >= 1 and body.count("'rest'") >= 1


def test_the_live_row_consumes_it():
    """An accessor with no consumer is the registered-but-inert failure (I18) —
    the exact shape this session kept finding elsewhere."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "venue.ws_health()" in src
    assert 'payload["book_feed"]' in src
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "ws_health"]
    assert calls, "the live host must actually call it"
    # ...and it must be guarded: a venue that cannot answer must not break the row
    guarded = [t for t in ast.walk(tree) if isinstance(t, ast.Try)
               and any(getattr(c.func, "attr", None) == "ws_health"
                       for c in ast.walk(t) if isinstance(c, ast.Call))]
    assert guarded, "the ws_health read must sit inside a try"
