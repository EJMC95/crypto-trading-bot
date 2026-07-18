"""Tier 2 — freqtrade_pnl_poller.poll_one: the unit conversion feeding 5+ bots.

poll_one translates freqtrade's REST payloads into the shared bot_pnl schema:
`pnl_pct = profit_closed_percent / 100`, per-trade `profit_ratio * 100`, and
hours-held from ms timestamps. A scale bug here writes a wrong pnl_pct for every
freqtrade book. The `[:12]` open-position cap is also asserted — the code's own
comment warns a shorter cap "silently under-reports fleet exposure" to
fleet_risk. We mock the HTTP layer and capture what gets published.
"""
import freqtrade_pnl_poller as poller


def _install(monkeypatch, *, profit, status, balance):
    """Route poll_one's endpoint calls to canned payloads and capture publish()."""
    def fake_req(url, headers=None):
        if "/profit" in url:
            return profit
        if "/status" in url:
            return status
        if "/balance" in url:
            return balance
        if "/trades" in url:
            return []
        raise AssertionError(f"unexpected url {url}")

    captured = {}
    monkeypatch.setattr(poller, "_req", fake_req)
    monkeypatch.setattr(poller, "_token", lambda port: "tok")
    monkeypatch.setattr(poller.store, "publish", lambda name, **kw: captured.update(kw) or True)
    monkeypatch.setattr(poller.store, "publish_trades", lambda name, trades: True)
    return captured


def test_pct_is_scaled_to_a_fraction(monkeypatch):
    cap = _install(
        monkeypatch,
        profit={"profit_closed_percent": 2.35, "profit_closed_coin": 23.5,
                "closed_trade_count": 12, "winning_trades": 8, "losing_trades": 4},
        status=[],
        balance={"total": 1023.5},
    )
    assert poller.poll_one("freqtrade-mum", 8080) is True
    assert cap["pnl_pct"] == 0.0235      # 2.35% -> 0.0235 fraction
    assert cap["pnl_abs"] == 23.5
    assert cap["equity"] == 1023.5
    assert cap["closed_trades"] == 12 and cap["wins"] == 8 and cap["losses"] == 4


def test_missing_pct_publishes_none_not_zero(monkeypatch):
    cap = _install(monkeypatch, profit={"profit_closed_coin": 0.0},
                   status=[], balance={"total": 1000.0})
    poller.poll_one("freqtrade-dad", 8081)
    assert cap["pnl_pct"] is None        # absent % must not read as 0% profit


def test_open_positions_capped_at_12(monkeypatch):
    status = [{"pair": f"C{i}/USD", "profit_ratio": 0.01, "open_timestamp": None}
              for i in range(15)]
    cap = _install(monkeypatch, profit={"profit_closed_percent": 1.0},
                   status=status, balance={"total": 1000.0})
    poller.poll_one("freqtrade-avo-maria", 8082)
    assert cap["open_trades"] == 15               # count is the FULL set…
    assert len(cap["extra"]["open_pos"]) == 12    # …but the detail list is capped


def test_per_trade_pnl_and_hours_held(monkeypatch, frozen_time):
    # ots two hours ago (ms) -> h == 2.0; profit_ratio 0.05 -> pnl 5.0
    ots_ms = int((frozen_time.now - 7200) * 1000)
    status = [{"pair": "BTC/USD", "profit_ratio": 0.05,
               "enter_tag": "momo", "open_timestamp": ots_ms}]
    cap = _install(monkeypatch, profit={"profit_closed_percent": 1.0},
                   status=status, balance={"total": 1000.0})
    poller.poll_one("freqtrade-georgia", 8083)
    pos = cap["extra"]["open_pos"][0]
    assert pos["pnl"] == 5.0
    assert pos["h"] == 2.0
    assert pos["tag"] == "momo"


def test_bot_down_records_starting(monkeypatch):
    def boom(url, headers=None):
        raise ConnectionError("api not up")
    captured = {}
    monkeypatch.setattr(poller, "_req", boom)
    monkeypatch.setattr(poller, "_token", lambda port: "tok")
    monkeypatch.setattr(poller.store, "publish", lambda name, **kw: captured.update(kw) or True)
    assert poller.poll_one("freqtrade-mum", 8080) is False
    assert captured["status"] == "starting"
