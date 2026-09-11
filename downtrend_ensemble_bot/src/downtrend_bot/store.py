"""Durable record of what the system decided and what the venue did (spec 15).

WHY SQLITE AND NOT A LOG FILE: after a restart the trader has to answer "what
do I already own, and did my last order actually reach the venue?" A log can
be read; it cannot be QUERIED for the open set, and reconciliation that has to
parse its own logs will eventually parse them wrong.

THE ONE RULE THAT MATTERS HERE: the venue is the authority on positions, this
table is the authority on INTENT. Reconciliation compares the two and reports
the difference; it never assumes either side is right. A position present at
the venue and absent here is an ORPHAN (a fill we did not record, and it has
no stop attached in our book); present here and absent at the venue is a GHOST
(closed behind our back, or never opened). Both are surfaced, neither is
silently repaired -- an automatic "repair" that guesses wrong writes a real
order against real money.

Decisions are recorded whether or not they led to a trade. A refused signal is
the more informative row: a book that takes nothing is only explainable if the
refusals were written down.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import time
from typing import Any, Sequence

from .logging_setup import get
from .models import (Fill, OrderRequest, OrderResult, Position, Signal, Trade,
                     contained_path)

log = get("store")

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY, ts REAL, symbol TEXT, side TEXT,
    strategy TEXT, setup TEXT, score REAL, entry REAL, stop REAL,
    reward_risk REAL, regime TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, symbol TEXT, side TEXT,
    signal_id TEXT, action TEXT, reason TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS orders (
    client_order_id TEXT PRIMARY KEY, ts REAL, symbol TEXT, side TEXT,
    action TEXT, intent TEXT, order_type TEXT, quantity REAL, price REAL,
    trigger_price REAL, reduce_only INTEGER, status TEXT, exchange_id TEXT,
    signal_id TEXT, error TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, order_id TEXT,
    symbol TEXT, side TEXT, quantity REAL, price REAL, fee REAL,
    partial INTEGER);
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY, side TEXT, quantity REAL, entry_price REAL,
    opened_ts REAL, stop_price REAL, protective_ok INTEGER, r_unit REAL,
    signal_id TEXT, strategy TEXT, scaled_out REAL, realized REAL,
    payload TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, side TEXT,
    strategy TEXT, setup TEXT, regime TEXT, opened_ts REAL, closed_ts REAL,
    entry REAL, exit REAL, quantity REAL, pnl REAL, fees REAL, funding REAL,
    r_multiple REAL, reason TEXT, signal_id TEXT, score REAL,
    slippage_bps REAL);
CREATE TABLE IF NOT EXISTS equity (
    ts REAL PRIMARY KEY, equity REAL, exposure REAL, open_positions INTEGER,
    regime TEXT);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, payload TEXT);
CREATE INDEX IF NOT EXISTS idx_trades_closed ON trades(closed_ts);
CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
"""


def _j(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return json.dumps({"unserialisable": str(type(obj))})


class Store:
    def __init__(self, path: str):
        d = os.path.dirname(path) or "."
        os.makedirs(d, exist_ok=True)
        # The filename is ours, but route it through the same containment
        # helper every other writer uses so there is ONE owner of that rule.
        self.path = contained_path(d, os.path.basename(path))
        self.db = sqlite3.connect(self.path, timeout=30.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        try:
            self.db.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------ writes --
    def record_signal(self, sig: Signal) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO signals (signal_id,ts,symbol,side,"
            "strategy,setup,score,entry,stop,reward_risk,regime,payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (sig.signal_id, time.time(), sig.symbol, sig.side, sig.strategy,
             sig.setup, sig.score.total, sig.entry, sig.stop, sig.reward_risk,
             sig.regime.value, _j(dataclasses.asdict(sig))))
        self.db.commit()

    def record_decision(self, *, symbol: str, side: str, action: str,
                        reason: str, signal_id: str = "",
                        payload: Any = None) -> None:
        """`action` is one of enter/refuse/exit/skip/halt. A REFUSAL is a
        first-class row: it is the only way a quiet book is explainable."""
        self.db.execute(
            "INSERT INTO decisions (ts,symbol,side,signal_id,action,reason,"
            "payload) VALUES (?,?,?,?,?,?,?)",
            (time.time(), symbol, side, signal_id, action, reason,
             _j(payload or {})))
        self.db.commit()

    def record_order(self, req: OrderRequest, res: OrderResult | None = None
                     ) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO orders (client_order_id,ts,symbol,side,"
            "action,intent,order_type,quantity,price,trigger_price,"
            "reduce_only,status,exchange_id,signal_id,error,payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (req.client_order_id, time.time(), req.symbol, req.side,
             req.action, req.intent.value, req.order_type, req.quantity,
             req.price, req.trigger_price, int(bool(req.reduce_only)),
             (res.status if res else "submitted"),
             (res.order_id if res else None), req.signal_id,
             (res.error if res else None), _j(req.as_dict())))
        self.db.commit()

    def record_fill(self, fill: Fill) -> None:
        self.db.execute(
            "INSERT INTO fills (ts,order_id,symbol,side,quantity,"
            "price,fee,partial) VALUES (?,?,?,?,?,?,?,?)",
            (fill.ts, fill.order_id, fill.symbol, fill.side,
             fill.quantity, fill.price, fill.fee, int(bool(fill.partial))))
        self.db.commit()

    def upsert_position(self, pos: Position) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO positions (symbol,side,quantity,"
            "entry_price,opened_ts,stop_price,protective_ok,r_unit,signal_id,"
            "strategy,scaled_out,realized,payload,updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pos.symbol, pos.side, pos.quantity, pos.entry_price,
             pos.opened_ts, pos.stop_price, int(bool(pos.protective_ok)),
             pos.r_unit, pos.signal_id, pos.strategy, pos.scaled_out,
             pos.realized, _j(pos.meta), time.time()))
        self.db.commit()

    def drop_position(self, symbol: str) -> None:
        self.db.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        self.db.commit()

    def record_trade(self, t: Trade) -> None:
        self.db.execute(
            "INSERT INTO trades (symbol,side,strategy,setup,regime,opened_ts,"
            "closed_ts,entry,exit,quantity,pnl,fees,funding,r_multiple,reason,"
            "signal_id,score,slippage_bps) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (t.symbol, t.side, t.strategy, t.setup, t.regime, t.opened_ts,
             t.closed_ts, t.entry, t.exit, t.quantity, t.pnl, t.fees,
             t.funding, t.r_multiple, t.reason, t.signal_id, t.score,
             t.slippage_bps))
        self.db.commit()

    def record_equity(self, equity: float, exposure: float, open_n: int,
                      regime: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO equity (ts,equity,exposure,"
                        "open_positions,regime) VALUES (?,?,?,?,?)",
                        (time.time(), equity, exposure, open_n, regime))
        self.db.commit()

    def record_event(self, kind: str, payload: Any) -> None:
        self.db.execute("INSERT INTO events (ts,kind,payload) VALUES (?,?,?)",
                        (time.time(), kind, _j(payload)))
        self.db.commit()

    # ------------------------------------------------------------- reads --
    def open_positions(self) -> list[dict[str, Any]]:
        return [dict(r) for r in
                self.db.execute("SELECT * FROM positions").fetchall()]

    def trades(self, since: float = 0.0) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM trades WHERE closed_ts>=? ORDER BY closed_ts",
            (since,)).fetchall()]

    def decisions(self, since: float = 0.0, limit: int = 500
                  ) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM decisions WHERE ts>=? ORDER BY ts DESC LIMIT ?",
            (since, limit)).fetchall()]

    def equity_curve(self, since: float = 0.0) -> list[tuple[float, float]]:
        return [(r["ts"], r["equity"]) for r in self.db.execute(
            "SELECT ts,equity FROM equity WHERE ts>=? ORDER BY ts",
            (since,)).fetchall()]

    def order(self, client_order_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM orders WHERE client_order_id=?",
                            (client_order_id,)).fetchone()
        return dict(r) if r else None

    def counts(self) -> dict[str, int]:
        out = {}
        for tbl in ("signals", "decisions", "orders", "fills", "positions",
                    "trades", "equity", "events"):
            out[tbl] = self.db.execute(
                f"SELECT COUNT(*) c FROM {tbl}").fetchone()["c"]
        return out


# ------------------------------------------------------------ reconcile ----
def reconcile(store: Store, venue_positions: Sequence[Position]
              ) -> dict[str, Any]:
    """Compare INTENT (our table) against the AUTHORITY (the venue).

    Reports; does not repair. A repair that guesses wrong sends a real order.
    `unprotected` is the row that must page a human: a position the venue
    holds with no protective stop recorded against it."""
    ours = {p["symbol"]: p for p in store.open_positions()}
    theirs = {p.symbol: p for p in venue_positions}
    orphans, ghosts, mismatched, unprotected = [], [], [], []
    for sym, p in theirs.items():
        if sym not in ours:
            orphans.append({"symbol": sym, "side": p.side,
                            "quantity": p.quantity,
                            "why": "held at the venue, absent from our book"})
            continue
        o = ours[sym]
        if o["side"] != p.side or abs(o["quantity"] - p.quantity) > \
                max(1e-9, 0.01 * abs(p.quantity)):
            mismatched.append({"symbol": sym, "ours": {
                "side": o["side"], "quantity": o["quantity"]},
                "venue": {"side": p.side, "quantity": p.quantity}})
        if not o["protective_ok"]:
            unprotected.append({"symbol": sym,
                                "why": "no protective stop recorded"})
    # Distinct names on purpose: the loop above already binds `sym`/`o`, and
    # reusing them here is what CodeQL flagged as a potentially-uninitialized
    # use. Shadowing across two loops in one function is confusing whether or
    # not the analyser is strictly right.
    for our_sym, ours_row in ours.items():
        if our_sym not in theirs:
            ghosts.append({"symbol": our_sym, "side": ours_row["side"],
                           "quantity": ours_row["quantity"],
                           "why": "in our book, absent at the venue"})
    clean = not (orphans or ghosts or mismatched or unprotected)
    out = {"clean": clean, "orphans": orphans, "ghosts": ghosts,
           "mismatched": mismatched, "unprotected": unprotected,
           "ours": len(ours), "venue": len(theirs),
           "action": ("none" if clean else
                      "REVIEW REQUIRED -- reconciliation reports, it never "
                      "repairs; trading stays halted until a human decides")}
    store.record_event("reconcile", out)
    if not clean:
        log.error("reconciliation is NOT clean: %s", _j(out))
    return out
