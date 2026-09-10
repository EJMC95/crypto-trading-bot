"""PAPER and SHADOW runners — live Lighter data, no signed transactions.

The two modes differ in ONE line of behaviour and nothing else:

  PAPER  simulates the fill and updates a simulated book.
  SHADOW builds the EXACT live order set -- type, price, quantity, stop,
         target, leverage, expected fees -- records it, and simulates the
         same fill so state still evolves.

Everything above that line is the code live mode runs: the same regime engine,
the same scorer, the same sizer, the same liquidation check, the same budgets,
the same execution plan builder. That is deliberate and it is the whole value
of the soak: a shadow run that used a different code path would validate
nothing.

`SoakRecord` counts the days and the valid signals that `config.LiveGate` reads
before it will permit live mode.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from . import execution as ex
from . import regime as regime_mod
from . import risk as risk_mod
from . import signals as sig_mod
from .config import AppConfig
from .data import to_columns
from .health import check as health_check, kill_switch_active
from .lighter_adapter import BaseAdapter
from .logging_setup import event, get
from .market_metadata import MarketRegistry
from .models import Mode, Position, Regime, Trade
from .portfolio import Book
from .risk import AccountState
from .strategy_health import HealthRegistry, TradeBudget, strategy_key

log = get("paper")


@dataclass
class SoakRecord:
    """The evidence `LiveGate` asks for. Kept as a file so it survives
    restarts -- a soak that resets on restart is not a soak."""
    started: float = 0.0
    signals: int = 0
    orders_planned: int = 0
    trades_closed: int = 0
    days: float = 0.0
    modes: dict[str, int] = field(default_factory=dict)

    def touch(self, mode: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if not self.started:
            self.started = now
        self.days = max(0.0, (now - self.started) / 86400.0)
        self.modes[mode] = self.modes.get(mode, 0) + 1

    @classmethod
    def load(cls, state_dir: str) -> "SoakRecord":
        p = os.path.join(state_dir, "soak.json")
        if not os.path.exists(p):
            return cls()
        try:
            return cls(**json.load(open(p)))
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, state_dir: str) -> None:
        os.makedirs(state_dir, exist_ok=True)
        tmp = os.path.join(state_dir, "soak.json.tmp")
        json.dump(asdict(self), open(tmp, "w"), indent=1)
        os.replace(tmp, os.path.join(state_dir, "soak.json"))


@dataclass
class RunnerState:
    book: Book = field(default_factory=Book)
    equity: float = 10_000.0
    shadow_orders: list[dict[str, Any]] = field(default_factory=list)
    last_error: str = ""


class Runner:
    """One scan cycle, shared by paper, shadow and (via subclass) live."""

    def __init__(self, cfg: AppConfig, adapter: BaseAdapter,
                 registry: MarketRegistry, *, mode: Mode = Mode.PAPER,
                 start_equity: float = 10_000.0):
        self.cfg = cfg
        self.adapter = adapter
        self.registry = registry
        self.mode = mode
        self.engine = regime_mod.MarketRegimeEngine(cfg.regime)
        self.health = HealthRegistry(cfg.strategy_health, cfg.state_dir)
        self.budget = TradeBudget(cfg.overtrading, cfg.state_dir)
        self.state = RunnerState(equity=start_equity)
        self.start_equity = start_equity
        self.soak = SoakRecord.load(cfg.state_dir)
        self.metadata_version = registry.version
        self.metadata_fetched_at = time.time()
        self.rejections: dict[str, int] = {}

    # ------------------------------------------------------------ helpers --
    def _reject(self, reason: str) -> None:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1

    def _tapes(self, symbols: list[str]) -> dict[str, dict[str, list]]:
        tf = self.cfg.timeframes
        out: dict[str, dict[str, list]] = {}
        for s in symbols:
            try:
                out[s] = {tf.signal: self.adapter.candles(s, tf.signal, pages=1),
                          tf.regime: self.adapter.candles(s, tf.regime, pages=1)}
            except Exception as exc:                    # noqa: BLE001
                log.warning("candles unavailable for %s: %s", s, exc)
        return out

    def _account(self) -> AccountState:
        """PAPER/SHADOW use the SIMULATED book but the REAL leverage ceiling,
        so sizing is identical to live for the same equity."""
        marks = self._marks()
        return AccountState(
            equity=self.state.equity + self.state.book.unrealized(marks),
            available_collateral=self.state.equity,
            margin_used=sum(p.quantity * p.entry_price
                            / max(p.meta.get("leverage", 1.0), 1e-9)
                            for p in self.state.book.positions.values()),
            account_max_leverage=self.cfg.risk.max_leverage,
            margin_mode=self.cfg.lighter.margin_mode)

    def _marks(self) -> dict[str, float]:
        out = {}
        for s in list(self.state.book.positions):
            try:
                out[s] = self.adapter.mark_price(s)
            except Exception:                            # noqa: BLE001
                pass
        return out

    def _spread(self, symbol: str) -> float | None:
        getter = getattr(self.adapter, "best_bid_ask", None)
        if getter is None:
            return None
        bid, ask = getter(symbol)
        return ex.spread_bps(bid, ask)

    # -------------------------------------------------------------- cycle --
    def cycle(self, symbols: list[str], now: float | None = None
              ) -> dict[str, Any]:
        now = time.time() if now is None else now
        cfg = self.cfg
        tapes = self._tapes(symbols)
        tf = cfg.timeframes

        sig_series = {s: t.get(tf.signal, []) for s, t in tapes.items()}
        hc = health_check(
            runtime_dir=cfg.runtime_dir,
            metadata_version=self.metadata_version,
            metadata_age_s=now - self.metadata_fetched_at,
            candles=sig_series, timeframe=tf.signal, ws_health=None,
            nonce_ok=None, account_reconciled=True, regime=None)

        btc = tapes.get("BTC", {})
        closes = {s: [c.close for c in t.get(tf.signal, [])]
                  for s, t in tapes.items()}
        inputs = regime_mod.RegimeInputs(
            btc_4h=btc.get(tf.regime, []), btc_1h=btc.get(tf.signal, []),
            breadth_up_frac=regime_mod.breadth(closes),
            atr_percentile=regime_mod.atr_percentile_now(btc.get(tf.regime, [])),
            spread_bps=self._spread("BTC"),
            data_ok=hc.ok, data_problems=hc.failures())
        verdict = self.engine.update(inputs, now)

        killed = kill_switch_active(cfg.runtime_dir)
        opened: list[dict[str, Any]] = []
        if killed:
            self._reject("kill switch present")
        elif not verdict.tradable:
            self._reject(f"regime {verdict.regime.value}")
        else:
            opened = self._scan(symbols, tapes, verdict.regime, now)

        self._manage(now)
        self.soak.touch(self.mode.value, now)
        self.soak.save(cfg.state_dir)

        marks = self._marks()
        return {"ts": now, "regime": verdict.regime.value,
                "regime_reasons": verdict.reasons,
                "kill_switch": killed, "health": hc.as_dict(),
                "opened": opened, "book": self.state.book.summary(marks),
                "equity": round(self.state.equity
                                + self.state.book.unrealized(marks), 4),
                "rejections": dict(sorted(self.rejections.items(),
                                          key=lambda kv: -kv[1])[:10]),
                "soak": {"days": round(self.soak.days, 2),
                         "signals": self.soak.signals}}

    def _scan(self, symbols: list[str], tapes, regime: Regime,
              now: float) -> list[dict[str, Any]]:
        cfg = self.cfg
        account = self._account()
        marks = self._marks()
        exposure = self.state.book.exposure(marks)
        opened: list[dict[str, Any]] = []
        for s in symbols:
            if s in self.state.book.positions:
                continue
            series = (tapes.get(s) or {}).get(cfg.timeframes.signal) or []
            if len(series) < 210:
                self._reject("insufficient history")
                continue
            ok, why = self.registry.tradable(s, cfg.lighter.target_max_leverage)
            if not ok:
                self._reject(why[0][:60] if why else "not tradable")
                continue
            spread = self._spread(s)
            for side in ("long", "short"):
                mult = regime_mod.risk_multiplier(cfg.regime, regime, side)
                if mult <= 0:
                    continue
                sig, _rej = sig_mod.evaluate(
                    s, series, side, regime, cfg.strategy,
                    timeframe=cfg.timeframes.signal,
                    funding=self._safe(lambda: self.adapter.funding_rate(s)),
                    oi_change=None, spread_bps=spread,
                    max_spread_bps=cfg.execution.max_spread_bps)
                if sig is None:
                    continue
                self.soak.signals += 1
                key = strategy_key(sig.strategy, s, side, regime.value)
                h = self.health.get(key)
                if not h.may_enter:
                    self._reject(f"strategy {h.state.value}")
                    continue
                ok, why = sig_mod.admissible(
                    sig, cfg.strategy, regime,
                    h.score_bump(cfg.strategy_health),
                    h.rr_bump(cfg.strategy_health))
                if not ok:
                    self._reject(why.split("(")[0].strip())
                    continue
                ok, why = self.budget.may_enter(symbol=s, strategy=sig.strategy,
                                                signal_id=sig.signal_id, now=now)
                if not ok:
                    self._reject(why.split(" for ")[0])
                    continue
                dec = risk_mod.size_position(
                    signal=sig, account=account, exposure=exposure,
                    registry=self.registry, risk_cfg=cfg.risk,
                    exec_cfg=cfg.execution, regime_multiplier=mult,
                    health_multiplier=h.risk_multiplier(cfg.strategy_health)
                    * self.budget.consecutive_loss_multiplier(now),
                    liquidity_multiplier=risk_mod.liquidity_multiplier(
                        spread, cfg.execution.max_spread_bps),
                    volatility_multiplier=risk_mod.volatility_multiplier(
                        sig.atr / max(sig.entry, 1e-9)))
                if not dec.ok:
                    self._reject(dec.reason.split(":")[0][:60])
                    continue
                plan = ex.build_plan(
                    signal=sig, decision=dec, registry=self.registry,
                    cfg=cfg.execution, spread=spread,
                    supports_grouping=getattr(
                        self.adapter, "report", None) is not None
                    and self.adapter.report.supports("grouped_orders_oto_oco"),
                    now_s=now)
                self.soak.orders_planned += 1
                rec = {"signal_id": sig.signal_id, "symbol": s, "side": side,
                       "score": sig.score.total,
                       "score_breakdown": sig.score.as_dict(),
                       "reward_risk": round(sig.reward_risk, 3),
                       "regime": regime.value, "plan": plan.as_dict(),
                       "risk": {"quantity": dec.quantity,
                                "notional": round(dec.notional, 4),
                                "risk_pct_equity": round(dec.risk_pct_equity, 4),
                                "leverage": dec.leverage,
                                "liquidation_price": dec.liquidation_price,
                                "stop_to_liq_atr": dec.stop_to_liq_atr,
                                "est_fees": round(dec.est_fees, 6),
                                "worst_case_gap_loss": round(
                                    dec.worst_case_gap_loss, 4)},
                       "mode": self.mode.value}
                event(log, "order_intent", **{k: rec[k] for k in
                                              ("signal_id", "symbol", "side",
                                               "score", "mode")})
                self._place(rec, sig, dec, now)
                opened.append(rec)
                break
        return opened

    @staticmethod
    def _safe(fn):
        try:
            return fn()
        except Exception:                                # noqa: BLE001
            return None

    def _place(self, rec: dict[str, Any], sig, dec, now: float) -> None:
        """PAPER and SHADOW both simulate the fill; SHADOW also records the
        exact intended order set and submits nothing."""
        if self.mode is Mode.SHADOW:
            self.state.shadow_orders.append(rec)
        entry = sig.entry
        self.state.book.positions[sig.symbol] = Position(
            symbol=sig.symbol, side=sig.side, quantity=dec.quantity,
            entry_price=entry, opened_ts=now, stop_price=sig.stop,
            targets=list(sig.targets), strategy=sig.strategy,
            signal_id=sig.signal_id, protective_ok=True,
            meta={"regime": rec["regime"], "atr": sig.atr,
                  "r": abs(entry - sig.stop), "leverage": dec.leverage,
                  "liquidation": dec.liquidation_price,
                  "entry_fee": dec.est_fees / 2.0})
        self.budget.record_entry(symbol=sig.symbol, strategy=sig.strategy,
                                 signal_id=sig.signal_id,
                                 score=sig.score.total, now=now)

    def _manage(self, now: float) -> None:
        cfg = self.cfg
        for s in list(self.state.book.positions):
            pos = self.state.book.positions[s]
            try:
                mark = self.adapter.mark_price(s)
            except Exception:                            # noqa: BLE001
                continue
            long = pos.side == "long"
            hit_stop = (mark <= pos.stop_price) if long else (mark >= pos.stop_price)
            hit_tp = bool(pos.targets) and (
                (mark >= pos.targets[-1]) if long else (mark <= pos.targets[-1]))
            held_h = (now - pos.opened_ts) / 3600.0
            expired = held_h >= cfg.strategy.max_holding_days * 24.0
            if not (hit_stop or hit_tp or expired):
                continue
            reason = "stop" if hit_stop else ("target" if hit_tp else "max_hold")
            sgn = 1.0 if long else -1.0
            gross = sgn * (mark - pos.entry_price) * pos.quantity
            fees = pos.meta.get("entry_fee", 0.0) * 2.0
            pnl = gross - fees
            r_unit = pos.meta.get("r") or 1e-9
            tr = Trade(symbol=s, side=pos.side, strategy=pos.strategy,
                       regime=str(pos.meta.get("regime", "")),
                       opened_ts=pos.opened_ts, closed_ts=now,
                       entry=pos.entry_price, exit=mark, quantity=pos.quantity,
                       pnl=pnl, fees=fees, funding=0.0,
                       r_multiple=gross / (r_unit * pos.quantity)
                       if pos.quantity else 0.0,
                       reason=reason, signal_id=pos.signal_id)
            self.state.book.closed.append(tr)
            self.state.book.realized += pnl
            self.state.book.day_pnl += pnl
            self.state.book.week_pnl += pnl
            self.state.equity += pnl
            self.soak.trades_closed += 1
            del self.state.book.positions[s]
            self.health.record(strategy_key(pos.strategy, s, pos.side,
                                            str(pos.meta.get("regime", ""))),
                               tr, reference_equity=self.start_equity)
            self.budget.record_exit(symbol=s, signal_id=pos.signal_id,
                                    pnl=pnl, now=now)
