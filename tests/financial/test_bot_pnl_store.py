"""Tier 2 — the shared publisher: money sanitization + the close-reason parser.

Every bot writes money through bot_pnl_store.publish(). Its own selftest covers
only the build-id stamp — not the money. Two gaps mattered:

  * publish() passed equity/pnl_abs/pnl_pct/pnl_daily straight into the shared
    schema. Postgres float8 accepts NaN/Infinity, so a single mis-publishing bot
    would make SUM(pnl_abs) NaN and corrupt the whole fleet total. `_finite_or_none`
    (added 2026-07-18) contains that; these tests lock it and prove it is wired
    into the write path.
  * split_reason() is the ONE parser every ledger composer round-trips against;
    its docstring records four separate money-affecting regressions.
"""
import bot_pnl_store as store


# ── _finite_or_none: the money sanitizer ─────────────────────────────────────
def test_finite_values_pass_through():
    assert store._finite_or_none(1000.0) == 1000.0
    assert store._finite_or_none(-23.5) == -23.5
    assert store._finite_or_none(0.0) == 0.0
    assert store._finite_or_none(100) == 100.0          # int -> float, exact
    assert store._finite_or_none("1.5") == 1.5          # numeric string coerced


def test_non_finite_and_garbage_become_none():
    assert store._finite_or_none(None) is None
    assert store._finite_or_none(float("nan")) is None
    assert store._finite_or_none(float("inf")) is None
    assert store._finite_or_none(float("-inf")) is None
    assert store._finite_or_none("abc") is None
    assert store._finite_or_none("") is None
    assert store._finite_or_none(object()) is None
    assert store._finite_or_none([1, 2]) is None


# ── publish(): the sanitizer is wired into the write path ────────────────────
class _FakeCursor:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sink.append(params)


class _FakeConn:
    def __init__(self, sink):
        self.sink = sink

    def cursor(self):
        return _FakeCursor(self.sink)

    def close(self):
        pass


def _capture_publish(monkeypatch, **kwargs):
    sink = []
    monkeypatch.setattr(store, "_get_conn", lambda: _FakeConn(sink))
    monkeypatch.setattr(store, "_ensure_table", lambda conn: None)
    monkeypatch.setattr(store, "_stamp_build", lambda extra: extra)
    ok = store.publish("mybot", **kwargs)
    assert ok is True
    assert sink, "publish never executed a statement"
    # params tuple: (bot, status, equity, pnl_abs, pnl_pct, open, closed, wins,
    #                losses, extra_json, pnl_daily)
    p = sink[-1]
    return {"equity": p[2], "pnl_abs": p[3], "pnl_pct": p[4], "pnl_daily": p[10]}


def test_publish_nulls_nan_money(monkeypatch):
    got = _capture_publish(monkeypatch, equity=1000.0, pnl_abs=float("nan"),
                           pnl_pct=float("inf"), pnl_daily=5.0)
    assert got["equity"] == 1000.0     # good values untouched
    assert got["pnl_daily"] == 5.0
    assert got["pnl_abs"] is None      # NaN contained -> None, not persisted
    assert got["pnl_pct"] is None      # inf contained


def test_publish_passes_clean_money_through(monkeypatch):
    got = _capture_publish(monkeypatch, equity=1023.5, pnl_abs=23.5,
                           pnl_pct=0.0235, pnl_daily=5.2)
    assert got == {"equity": 1023.5, "pnl_abs": 23.5,
                   "pnl_pct": 0.0235, "pnl_daily": 5.2}


# ── split_reason: entry-tag vs exit-reason ───────────────────────────────────
def test_direction_prefixed_reasons_carry_an_enter_tag():
    assert store.split_reason("long_tp") == ("long", "tp")
    assert store.split_reason("short_sl") == ("short", "sl")
    # the Ticket Taker's hyphenated side-lens tags split at the FIRST underscore
    assert store.split_reason("long-breakout_tp") == ("long-breakout", "tp")
    # the family bot's multi-hyphen strategy tags round-trip too
    assert store.split_reason("long-bounce-pullback_stop") == ("long-bounce-pullback", "stop")


def test_exit_only_reasons_are_not_mistaken_for_entries():
    # 'flip' (funding-carry) and 'delisted' (sniper) are EXITS, not enter_tags —
    # the bug that had the brain proposing to "tighten the flip entry gate".
    assert store.split_reason("flip") == (None, "flip")
    assert store.split_reason("delisted") == (None, "delisted")
    # 'decay_paid' has no direction prefix -> kept WHOLE, not mangled to 'decay'
    assert store.split_reason("decay_paid") == (None, "decay_paid")


def test_split_reason_edge_cases():
    assert store.split_reason("") == (None, "trade")
    assert store.split_reason(None) == (None, "trade")
    assert store.split_reason("long_") == ("long", "trade")   # nothing after the sep
