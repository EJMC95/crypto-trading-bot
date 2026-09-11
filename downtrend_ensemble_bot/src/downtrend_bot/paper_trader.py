"""The 30-day paper soak (spec 13), and the report that gates live trading.

WHAT THE SOAK IS FOR: not to find out whether the strategy is profitable --
30 days at this trade rate cannot answer that -- but to find out whether the
PROGRAM is correct. Does it reconnect? Does it reconcile after a restart? Does
every fill get a stop? Does the regime engine flip sensibly on real data? Do
the budgets and cooldowns fire? Those are answerable in 30 days, and every one
of them is a way to lose money that has nothing to do with edge.

THE REPORT IS THE ARTEFACT THE LIVE GATE READS. `live_trader` refuses to start
without one that is complete, recent and from the same configuration -- so the
soak is a precondition in code, not a habit.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import AppConfig, Mode
from .exchange_adapter import ExchangeAdapter
from .logging_setup import get
from .models import contained_path
from .reporting import render_status, write_json
from .store import Store
from .trader import LoopState, Trader

log = get("paper")

REPORT_NAME = "paper_soak.json"


@dataclass
class SoakReport:
    started: float = 0.0
    updated: float = 0.0
    days: float = 0.0
    loops: int = 0
    trades: int = 0
    signals: int = 0
    refusals: int = 0
    errors: int = 0
    restarts: int = 0
    reconcile_clean: bool = False
    unprotected_seen: int = 0
    start_equity: float = 0.0
    equity: float = 0.0
    config_fingerprint: str = ""
    symbols: list[str] = field(default_factory=list)
    daily: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["complete"] = self.complete()[0]
        d["complete_why"] = self.complete()[1]
        return d

    def complete(self, min_days: float = 30.0, min_trades: int = 20
                 ) -> tuple[bool, list[str]]:
        """Both bars, and BOTH must be met. Days alone lets a soak that took
        no trades certify a trading program; trades alone lets a busy week
        stand in for a month of conditions."""
        why = []
        if self.days < min_days:
            why.append(f"{self.days:.1f} of {min_days:.0f} days")
        if self.trades < min_trades:
            why.append(f"{self.trades} of {min_trades} trades")
        if not self.reconcile_clean:
            why.append("reconciliation has never been clean")
        if self.unprotected_seen:
            why.append(f"{self.unprotected_seen} position(s) were seen "
                       "without a protective stop -- a program defect, not a "
                       "strategy result")
        return (not why), why


def config_fingerprint(cfg: AppConfig) -> str:
    """What the live gate compares against. Deliberately covers the RULES
    (risk, strategy, regime, execution, symbols) and not the run-time paths --
    moving a log directory does not invalidate a soak; changing the score
    threshold does."""
    import hashlib
    payload = {
        "symbols": sorted(cfg.symbols),
        "timeframes": cfg.timeframes.__dict__,
        "risk": cfg.risk.__dict__,
        "strategy": cfg.strategy.__dict__,
        "regime": cfg.regime.__dict__,
        "execution": cfg.execution.__dict__,
        "overtrading": cfg.overtrading.__dict__,
        "allow_longs": cfg.allow_longs,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def report_path(cfg: AppConfig) -> str:
    os.makedirs(cfg.reports_dir, exist_ok=True)
    return contained_path(cfg.reports_dir, REPORT_NAME)


def load_report(cfg: AppConfig) -> SoakReport | None:
    path = report_path(cfg)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as exc:
        log.error("paper report unreadable: %s", exc)
        return None
    rep = SoakReport()
    for k, v in raw.items():
        if hasattr(rep, k) and k not in ("complete", "complete_why"):
            setattr(rep, k, v)
    return rep


def run_paper(cfg: AppConfig, adapter: ExchangeAdapter, *,
              loops: int | None = None, interval_s: float = 60.0,
              on_state: Callable[[LoopState], None] | None = None,
              sleep: Callable[[float], None] = time.sleep,
              clock: Callable[[], float] = time.time) -> SoakReport:
    """Run the soak. Resumes an existing report rather than starting over --
    a restart is part of what is being tested, not a reason to lose 3 weeks."""
    if cfg.mode is Mode.LIVE:
        raise ValueError("run_paper refuses to run with mode=LIVE")
    store = Store(cfg.state_db)
    trader = Trader(cfg, adapter, submit=False, store=store, clock=clock)
    trader.load_markets()
    rec = trader.reconcile_on_start()

    rep = load_report(cfg) or SoakReport(started=clock(),
                                         start_equity=trader.equity)
    fp = config_fingerprint(cfg)
    if rep.config_fingerprint and rep.config_fingerprint != fp:
        # A rule change restarts the clock. Carrying the old days forward
        # would certify a program that no longer exists.
        log.warning("configuration changed (%s -> %s): the soak clock RESTARTS",
                    rep.config_fingerprint, fp)
        rep = SoakReport(started=clock(), start_equity=trader.equity)
        rep.notes.append(f"clock restarted on a config change to {fp}")
    else:
        rep.restarts += 1
    rep.config_fingerprint = fp
    rep.symbols = list(cfg.symbols)
    rep.reconcile_clean = bool(rec.get("clean")) or rep.reconcile_clean

    n = 0
    day_key = None
    day_start_equity = trader.equity
    try:
        while loops is None or n < loops:
            st = trader.step()
            n += 1
            rep.loops += 1
            rep.updated = clock()
            rep.days = max(0.0, (rep.updated - rep.started) / 86400.0)
            rep.equity = trader.equity
            rep.trades = len(trader.book.closed)
            rep.unprotected_seen += sum(
                1 for p in st.positions if not p.get("protective_ok"))
            counts = store.counts()
            rep.signals = counts.get("signals", 0)
            rep.refusals = counts.get("decisions", 0)

            k = time.strftime("%Y-%m-%d", time.gmtime(rep.updated))
            if day_key is None:
                day_key, day_start_equity = k, trader.equity
            elif k != day_key:
                rep.daily.append({"date": day_key,
                                  "equity": round(trader.equity, 2),
                                  "pnl": round(trader.equity
                                               - day_start_equity, 2),
                                  "open": len(trader.book.positions),
                                  "regime": st.regime})
                day_key, day_start_equity = k, trader.equity
            write_json(cfg.reports_dir, REPORT_NAME, rep.as_dict())
            if on_state:
                on_state(st)
            if loops is None or n < loops:
                sleep(interval_s)
    except KeyboardInterrupt:
        log.info("paper soak interrupted; report saved")
    finally:
        write_json(cfg.reports_dir, REPORT_NAME, rep.as_dict())
        store.close()
    return rep


def render(cfg: AppConfig, st: LoopState) -> str:
    return render_status(st.as_dict())
