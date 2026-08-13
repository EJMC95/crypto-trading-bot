"""Tier 2 — the dashboard's money surface: the read-time filter, /pnl.json,
/trades.json, and the auth gate.

pnl_dashboard.py is the fleet's money scoreboard and was 9% covered — the
single biggest gap in TEST_COVERAGE_ANALYSIS_2026-07-29.md (Finding 2). The
money risk concentrates in four places, each with incident history:

  * fetch_rows — THE read-time choke point ("grid, the totals AND /pnl.json
    all respect it"): RETIRED_ROWS + hidden + CURRENT_BOTS filtering. The
    $34.67 double-count survived exactly as long as a retired live row could
    reach a reader.
  * /pnl.json — the live-fleet subtotal the scheduled reports headline, and
    the feed the watchdog probes. Publisher NaN-containment means money
    fields can legitimately be None; the sums must survive that without
    corrupting the total (the reason _finite_or_none exists upstream).
  * /trades.json — param clamping + source routing for the ledger feed the
    organs (implementation_shortfall) and reviews read.
  * _auth_ok — FAILS CLOSED with no configured secret (the committed-default
    "freqbot2026" was found live on production; no secret => no access).

The handler is driven without a socket (H.__new__ + stubbed send_*), the
fetchers without a DB (monkeypatched, or a fake psycopg2 for fetch_rows) —
the parliament_card test's recipe, extended to the money paths.
"""
import base64
import datetime as dt
import io
import json
import sys
import types

import pytest

import pnl_dashboard as pd

pytestmark = pytest.mark.financial

NOW = dt.datetime.now(dt.timezone.utc)


# ── harness: drive H.do_GET without a socket ─────────────────────────────────
def _drive(path, auth_header=None):
    h = pd.H.__new__(pd.H)
    h.path = path
    h.headers = {"Authorization": auth_header} if auth_header else {}
    h.wfile = io.BytesIO()
    sent = {"status": None, "headers": []}
    h.send_response = lambda code, *a: sent.__setitem__("status", code)
    h.send_header = lambda k, v: sent["headers"].append((k, v))
    h.end_headers = lambda: None
    h.do_GET()
    return sent["status"], dict(sent["headers"]), h.wfile.getvalue()


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


# ── _auth_ok: fail-closed ────────────────────────────────────────────────────
def test_auth_denies_everyone_when_no_secret_configured(monkeypatch):
    # The committed-default incident: unset password must mean NO access —
    # even a caller presenting the empty password must be refused.
    monkeypatch.setattr(pd, "DASH_PASS", "")
    h = pd.H.__new__(pd.H)
    h.headers = {"Authorization": _basic("eamon", "")}
    assert h._auth_ok() is False


def test_auth_accepts_only_the_exact_credentials(monkeypatch):
    monkeypatch.setattr(pd, "DASH_USER", "eamon")
    monkeypatch.setattr(pd, "DASH_PASS", "s3cret")
    h = pd.H.__new__(pd.H)
    h.headers = {"Authorization": _basic("eamon", "s3cret")}
    assert h._auth_ok() is True
    h.headers = {"Authorization": _basic("eamon", "wrong")}
    assert h._auth_ok() is False
    h.headers = {"Authorization": _basic("intruder", "s3cret")}
    assert h._auth_ok() is False
    h.headers = {"Authorization": "Basic not-base64!!"}
    assert h._auth_ok() is False
    h.headers = {}
    assert h._auth_ok() is False


def test_html_page_is_auth_gated(monkeypatch):
    monkeypatch.setattr(pd, "DASH_PASS", "s3cret")
    status, headers, body = _drive("/")
    assert status == 401
    assert "WWW-Authenticate" in headers
    assert body.startswith(b"Auth required")


# ── /pnl.json: the money feed ────────────────────────────────────────────────
def _row(bot, equity, pnl_abs, age_sec=10, naive=False, extra=None):
    ua = NOW - dt.timedelta(seconds=age_sec)
    if naive:
        ua = ua.replace(tzinfo=None)
    return {"bot": bot, "status": "running", "equity": equity,
            "pnl_abs": pnl_abs, "pnl_pct": None, "open_trades": 0,
            "closed_trades": 3, "wins": 2, "losses": 1,
            "extra": extra or {}, "updated_at": ua}


@pytest.fixture
def pnl_fixture(monkeypatch):
    rows = {
        # the real live pair's ids — base bots are in CURRENT_BOTS
        "perps-funding-lighter-lighter": _row(
            "perps-funding-lighter-lighter", 1034.67, 34.67),
        # NaN-contained publisher output: money fields None, row still live
        "lighter-ticket-taker-lighter": _row(
            "lighter-ticket-taker-lighter", None, None),
        # a shadow twin — must NEVER enter the live subtotal
        "lighter-ticket-taker-lshadow": _row(
            "lighter-ticket-taker-lshadow", 990.0, -10.0),
        # stale + naive timestamp (assumed UTC), crypto threshold is 180s
        "crypto-intraday-15m-lshadow": _row(
            "crypto-intraday-15m-lshadow", 1001.0, 1.0,
            age_sec=7200, naive=True),
    }
    monkeypatch.setattr(pd, "fetch_rows", lambda hidden=None: rows)
    monkeypatch.setattr(pd, "fetch_ledger_enrich", lambda: {})
    return rows


def test_pnl_json_live_subtotal_counts_only_live_rows(pnl_fixture):
    status, headers, body = _drive("/pnl.json")
    assert status == 200
    assert headers.get("Content-Type") == "application/json"
    doc = json.loads(body)
    live = doc["meta"]["live_fleet"]
    assert live["n_live_bots"] == 2
    assert set(live["live_bots"]) == {"perps-funding-lighter-lighter",
                                      "lighter-ticket-taker-lighter"}
    # the shadow twin's -10 must not leak in; the None-money live row must
    # contribute zero, not corrupt the sum
    assert live["live_pnl"] == 34.67
    assert live["live_equity"] == 1034.67


def test_pnl_json_survives_none_money_rows(pnl_fixture):
    # The publisher nulls NaN/inf money (_finite_or_none). The feed must
    # serialize those rows as-is — None, not 0, not NaN — and still total.
    doc = json.loads(_drive("/pnl.json")[2])
    by_bot = {d["bot"]: d for d in doc["bots"]}
    taker = by_bot["lighter-ticket-taker-lighter"]
    assert taker["equity"] is None and taker["pnl_abs"] is None
    assert taker["live"] is True
    # json.dumps would have emitted NaN (invalid JSON) had a NaN slipped in;
    # json.loads succeeding is itself part of the contract.


def test_pnl_json_venue_provenance_and_serialization(pnl_fixture):
    doc = json.loads(_drive("/pnl.json")[2])
    by_bot = {d["bot"]: d for d in doc["bots"]}
    assert by_bot["perps-funding-lighter-lighter"]["venue_mode"] == "lighter_live"
    assert by_bot["lighter-ticket-taker-lshadow"]["venue_mode"] == "lighter_shadow"
    assert by_bot["lighter-ticket-taker-lshadow"]["live"] is False
    assert by_bot["lighter-ticket-taker-lshadow"]["base_bot"] == "lighter-ticket-taker"
    # datetimes must arrive as ISO strings (json.dumps would raise on raw dt)
    assert isinstance(by_bot["perps-funding-lighter-lighter"]["updated_at"], str)


def test_pnl_json_stale_flags_are_per_bot_and_feed_stale_needs_all(pnl_fixture):
    doc = json.loads(_drive("/pnl.json")[2])
    by_bot = {d["bot"]: d for d in doc["bots"]}
    # the 2h-old row (naive ts, assumed UTC) is past the 180s crypto threshold
    assert by_bot["crypto-intraday-15m-lshadow"]["stale"] is True
    assert by_bot["perps-funding-lighter-lighter"]["stale"] is False
    meta = doc["meta"]
    assert meta["n_stale"] == 1
    assert meta["feed_stale"] is False      # one laggard != a frozen feed


def test_pnl_json_feed_stale_when_every_bot_is_past_threshold(monkeypatch):
    rows = {
        "perps-funding-lighter-lighter": _row(
            "perps-funding-lighter-lighter", 1000.0, 0.0, age_sec=7200),
        "lighter-ticket-taker-lshadow": _row(
            "lighter-ticket-taker-lshadow", 1000.0, 0.0, age_sec=7200),
    }
    monkeypatch.setattr(pd, "fetch_rows", lambda hidden=None: rows)
    monkeypatch.setattr(pd, "fetch_ledger_enrich", lambda: {})
    doc = json.loads(_drive("/pnl.json")[2])
    assert doc["meta"]["feed_stale"] is True   # the 2026-06-22 failure class


def test_pnl_json_db_error_returns_500_not_garbage(monkeypatch):
    def _boom(hidden=None):
        raise RuntimeError("db down")
    monkeypatch.setattr(pd, "fetch_rows", _boom)
    status, _, body = _drive("/pnl.json")
    assert status == 500
    assert "db down" in json.loads(body)["error"]


# ── /trades.json: param clamping + source routing ────────────────────────────
@pytest.fixture
def trades_capture(monkeypatch):
    calls = {}

    def fake_trades(bot=None, limit=500, include_open=False):
        calls.update(src="bot", bot=bot, limit=limit, include_open=include_open)
        return [{"bot": bot or "b", "pnl_abs": 1.5,
                 "closed_at": NOW}]

    def fake_paper(bot=None, limit=500):
        calls.update(src="paper", bot=bot, limit=limit)
        return [{"bot": bot or "b", "pnl_abs": -0.5, "closed_at": NOW}]

    monkeypatch.setattr(pd, "fetch_trades", fake_trades)
    monkeypatch.setattr(pd, "fetch_paper_rows", fake_paper)
    return calls


def test_trades_json_defaults(trades_capture):
    status, _, body = _drive("/trades.json")
    assert status == 200
    doc = json.loads(body)
    assert doc["source"] == "bot"
    assert trades_capture == {"src": "bot", "bot": None, "limit": 500,
                              "include_open": False}
    assert isinstance(doc["trades"][0]["closed_at"], str)   # serialized


def test_trades_json_limit_is_clamped_both_ways(trades_capture):
    _drive("/trades.json?limit=999999")
    assert trades_capture["limit"] == 5000
    _drive("/trades.json?limit=0")
    assert trades_capture["limit"] == 1
    _drive("/trades.json?limit=abc")
    assert trades_capture["limit"] == 500      # junk -> default, not a crash


def test_trades_json_source_paper_routes_to_the_paper_ledger(trades_capture):
    doc = json.loads(_drive("/trades.json?source=paper&bot=freqtrade-mum")[2])
    assert doc["source"] == "paper"
    assert trades_capture["src"] == "paper"
    assert trades_capture["bot"] == "freqtrade-mum"


def test_trades_json_include_open_flag(trades_capture):
    _drive("/trades.json?include_open=1")
    assert trades_capture["include_open"] is True


# ── fetch_rows: the read-time retirement filter ──────────────────────────────
class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._last = sql

    def fetchone(self):
        return {"t": "bot_pnl"}         # to_regclass: table exists

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, cursor_factory=None):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def _install_fake_psycopg2(monkeypatch, rows):
    fake = types.ModuleType("psycopg2")
    fake.connect = lambda *a, **kw: _FakeConn(rows)
    fake_extras = types.ModuleType("psycopg2.extras")
    fake_extras.RealDictCursor = object
    fake.extras = fake_extras
    monkeypatch.setitem(sys.modules, "psycopg2", fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", fake_extras)


def test_fetch_rows_drops_retired_hidden_and_unknown(monkeypatch):
    # Preconditions the fixture relies on (roster drift would invalidate it):
    # [2026-08-13 (ma)] the slot's THIRD occupant — the Taker live row joined
    # Tide Rider's on the RETIRED side when Avo Maria took the sub-account.
    assert "crypto-trend-daily-lighter" in pd.RETIRED_ROWS   # the $34.67 row
    assert "lighter-ticket-taker-lighter" in pd.RETIRED_ROWS  # the $62.80 row
    assert "freqtrade-avo-maria" in pd.CURRENT_BOTS

    db_rows = [
        {"bot": "crypto-trend-daily-lighter", "equity": 1034.67},   # RETIRED
        {"bot": "lighter-ticket-taker-lighter", "equity": 62.80},   # RETIRED
        {"bot": "freqtrade-avo-maria-lighter", "equity": 62.80},    # survivor
        {"bot": "freqtrade-mum-lshadow", "equity": 1000.0},   # hidden below
        {"bot": "totally-unknown-bot", "equity": 999.0},      # not current
    ]
    _install_fake_psycopg2(monkeypatch, db_rows)
    out = pd.fetch_rows(hidden={"freqtrade-mum-lshadow"})
    # Every PAST occupant of the shared live slot reports the SAME
    # sub-account's money as the current one; only the current occupant may
    # pass, or the fleet total double-counts real dollars. Two generations
    # of the incident now, pinned at the choke point.
    assert set(out) == {"freqtrade-avo-maria-lighter"}


def test_fetch_rows_variant_passes_while_its_retired_base_row_stays_out(monkeypatch):
    # The ex-Kraken bases live a double life: the BARE id is a RETIRED paper-era
    # row (14-Jul Kraken cut) while remaining a CURRENT base so its -lshadow
    # twin displays. The filter must express both halves at once.
    assert "crypto-intraday-15m" in pd.CURRENT_BOTS
    assert "crypto-intraday-15m" in pd.RETIRED_ROWS
    db_rows = [{"bot": "crypto-intraday-15m-lshadow", "equity": 1000.0},
               {"bot": "crypto-intraday-15m", "equity": 1000.0}]
    _install_fake_psycopg2(monkeypatch, db_rows)
    out = pd.fetch_rows(hidden=set())
    assert "crypto-intraday-15m-lshadow" in out    # variant of a current base
    assert "crypto-intraday-15m" not in out        # retired paper row stays gone


# ── formatter None-safety (they render money on every card) ──────────────────
def test_money_pct_cls_are_none_safe():
    assert pd.money(None) == "—" and pd.money("abc") == "—"
    assert pd.money(1234.5) == "+1,234.50" and pd.money(-3) == "-3.00"
    assert pd.pct(None) == "—" and pd.pct(0.0235) == "+2.35%"
    assert pd.cls(None) == "" and pd.cls(-1) == "neg" and pd.cls(0) == "pos"
