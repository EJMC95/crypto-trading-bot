"""The live loop, shared by PAPER and LIVE (specs 13, 14).

ONE ENGINE, TWO MODES, AND THE DIFFERENCE IS EXACTLY ONE THING: whether an
order leaves the process. That is deliberate. If paper ran a different code
path from live, the 30-day soak would be validating a program that is not the
one that trades, which is the most expensive kind of green test.

WHAT PAPER DOES NOT SIMULATE, DECLARED RATHER THAN QUIETLY ASSUMED:
  * real queue position -- a paper limit fills on a touch, a real one may not;
  * partial fills beyond the configured rate;
  * exchange downtime, rate limits and rejected signed payloads;
  * funding paid at settlement rather than accrued per bar.
Every one of those makes paper LOOK BETTER than live. A paper report is
therefore an upper bound on the same rules run for real, and the README says
so where an operator will read it.

THE PROTECTIVE-STOP RULE, and it is the reason this file is careful rather
than short: an entry that fills WITHOUT its stop attached is an unhedged naked
position. The order is entry -> verify fill -> attach stop -> verify stop. If
the stop cannot be attached, the position is CLOSED immediately rather than
carried; a position we cannot protect is not a position we are willing to own.
`emergency_flatten` is the one path that may send a closing order without a
matching protective order, for exactly that reason.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from . import regime as regime_mod
from . import signals as sig_mod
from .changepoint import ChangePointDetector
from .config import AppConfig, Mode
from .exchange_adapter import ExchangeAdapter, ExchangeError, Ticker
from .execution import (build_plan, breakeven_stop, should_time_stop,
                        side_to_action, spread_bps, trail_stop)
from .health import (StrategyHealthMonitor, check_system, kill_switch_active,
                     strategy_key)
from .logging_setup import get
from .models import (Candle, Market, OrderIntent, OrderRequest, OrderResult,
                     Position, Regime, Signal, Trade)
from .portfolio import Book, TradeBudget, effective_bets, group_of
from .risk import Account, size_position
from .store import Store, reconcile

log = get("trader")

TF_S = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
        "2h": 7200, "4h": 14400, "1d": 86400}


@dataclass
class LoopState:
    """What one iteration observed. Rendered by `reporting.render_status`."""
    ts: float = 0.0
    mode: str = "paper"
    regime: str = "-"
    risk_multiplier: float = 0.0
    entries_disabled: bool = True
    halts: list[str] = field(default_factory=list)
    equity: float = 0.0
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    exposure_pct: float | None = None
    margin_pct: float | None = None
    effective_bets: float | None = None
    positions: list[dict[str, Any]] = field(default_factory=list)
    strategy_health: dict[str, Any] = field(default_factory=dict)
    changepoints: list[dict[str, Any]] = field(default_factory=list)
    recent_decisions: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class Trader:
    """Paper and live. `submit` is the only behavioural difference."""

    def __init__(self, cfg: AppConfig, adapter: ExchangeAdapter, *,
                 submit: bool, store: Store | None = None,
                 markets: dict[str, Market] | None = None,
                 clock: Callable[[], float] = time.time):
        if submit and cfg.mode is not Mode.LIVE:
            raise ValueError(
                "submit=True outside LIVE mode. Order submission is gated on "
                "the MODE, not on a constructor argument, so that a paper run "
                "can never be turned into a live one by a keyword.")
        self.cfg = cfg
        self.ex = adapter
        self.submit = bool(submit)
        self.clock = clock
        self.store = store or Store(cfg.state_db)
        self.markets: dict[str, Market] = markets or {}
        self.book = Book()
        self.engine = regime_mod.MarketRegimeEngine(cfg.regime)
        self.health = StrategyHealthMonitor(cfg.strategy_health,
                                            cfg.runtime_dir)
        self.budget = TradeBudget(cfg.overtrading, cfg.runtime_dir)
        self.detector = ChangePointDetector(cfg.changepoint)
        self.equity = cfg.backtest.start_equity
        self.day_pnl = 0.0
        self.week_pnl = 0.0
        self._day_key: str | None = None
        self._week_key: str | None = None
        self._tapes: dict[str, dict[str, list[Candle]]] = {}
        self._halted: list[str] = []
        self._reconciled = False
        self._start_ts = clock()

    # ------------------------------------------------------------- setup --
    def load_markets(self) -> None:
        got = {m.symbol: m for m in self.ex.fetch_markets()}
        self.markets = {s: got[s] for s in self.cfg.symbols if s in got}
        missing = [s for s in self.cfg.symbols if s not in got]
        if missing:
            log.warning("configured symbols absent at the venue: %s", missing)
        untradable = {s: m.missing() for s, m in self.markets.items()
                      if not m.tradable}
        if untradable:
            # Refused, not defaulted: a market whose tick size or margin
            # fraction we could not read cannot be sized safely.
            log.error("markets with incomplete metadata are REFUSED: %s",
                      untradable)
            for s in untradable:
                self.markets.pop(s, None)

    def reconcile_on_start(self) -> dict[str, Any]:
        """The restart contract (spec 13/14). Trading stays halted until this
        is clean -- a restart that resumes on an unverified book can double a
        position or carry an unprotected one."""
        try:
            venue = self.ex.fetch_positions()
        except (ExchangeError, NotImplementedError) as exc:
            self._reconciled = False
            out = {"clean": False, "error": repr(exc),
                   "action": "could not read venue positions; entries halted"}
            self.store.record_event("reconcile_failed", out)
            return out
        rep = reconcile(self.store, venue)
        self._reconciled = bool(rep.get("clean"))
        if self._reconciled:
            # Adopt the venue's view into the in-memory book.
            self.book.positions = {p.symbol: p for p in venue}
            for p in venue:
                self.store.upsert_position(p)
        return rep

    # -------------------------------------------------------------- data --
    def refresh(self, symbols: Sequence[str] | None = None) -> None:
        syms = list(symbols or self.markets or self.cfg.symbols)
        tfs = [self.cfg.timeframes.regime, self.cfg.timeframes.signal,
               self.cfg.timeframes.execution]
        for s in syms:
            tape = self._tapes.setdefault(s, {})
            for tf in tfs:
                try:
                    bars = self.ex.fetch_ohlcv(s, tf, limit=400)
                except (ExchangeError, NotImplementedError) as exc:
                    log.warning("ohlcv %s %s failed: %s", s, tf, exc)
                    continue
                tape[tf] = self._closed_only(bars, tf)

    def _closed_only(self, bars: Sequence[Candle], tf: str) -> list[Candle]:
        """Drop the forming bar. Spec 2: never act on an incomplete candle.
        A bar is closed only once `ts + tf` is in the PAST."""
        span = TF_S.get(tf, 0)
        now = self.clock()
        return [c for c in bars if c.ts + span <= now]

    # ------------------------------------------------------------- gating --
    def _system(self) -> tuple[bool, list[str]]:
        sig_tf = self.cfg.timeframes.signal
        candles = {s: t.get(sig_tf, []) for s, t in self._tapes.items()}
        h = check_system(runtime_dir=self.cfg.runtime_dir, candles=candles,
                         timeframe_seconds=TF_S.get(sig_tf, 3600),
                         now=self.clock(), exchange_ok=True,
                         reconciled=self._reconciled,
                         regime=self.engine.state,
                         stale_tolerance_bars=(
                             self.cfg.universe.max_candle_staleness_bars))
        return h.ok, h.failures()

    def _roll_periods(self) -> None:
        now = self.clock()
        d = time.strftime("%Y-%m-%d", time.gmtime(now))
        w = time.strftime("%Y-%W", time.gmtime(now))
        if self._day_key != d:
            self._day_key, self.day_pnl = d, 0.0
        if self._week_key != w:
            self._week_key, self.week_pnl = w, 0.0

    # -------------------------------------------------------------- loop --
    def step(self) -> LoopState:
        """One full iteration: refresh -> regime -> manage -> scan -> report.

        MANAGE RUNS BEFORE SCAN, always. Protecting what is already open
        outranks opening more, and a loop that scans first can spend its
        position budget while an existing stop is unattached."""
        self._roll_periods()
        self.refresh()
        st = LoopState(ts=self.clock(),
                       mode=("live" if self.submit else "paper"))

        marks = self._marks()
        verdict = self._regime(marks)
        st.regime = verdict.regime.value

        self._manage(marks)

        ok, fails = self._system()
        halts = list(fails)
        if kill_switch_active(self.cfg.runtime_dir):
            halts.append("KILL_SWITCH file present")
        if self.day_pnl <= -abs(self.cfg.risk.max_daily_loss) * self.equity:
            halts.append("daily loss limit reached")
        if self.week_pnl <= -abs(self.cfg.risk.max_weekly_loss) * self.equity:
            halts.append("weekly loss limit reached")
        self._halted = halts

        cp = self.detector.evaluate(self.clock())
        st.changepoints = [e.as_dict() for e in cp.evidence]
        # The SHORT side's multiplier is the headline: this is a short-biased
        # system, so "risk multiplier" without a side would be ambiguous
        # exactly where it matters.
        short_mult = regime_mod.risk_multiplier(self.cfg.regime,
                                                self.engine.state, "short")
        risk_mult = short_mult * cp.risk_multiplier

        st.risk_multiplier = round(risk_mult, 4)
        st.entries_disabled = (bool(halts) or risk_mult <= 0
                               or not verdict.tradable
                               or cp.severity == "critical")
        st.halts = halts
        if cp.severity == "critical":
            halts.append("change-point detector: critical")
        if not verdict.tradable:
            halts.append(f"regime {self.engine.state.value}")

        if not st.entries_disabled:
            self._scan(marks, verdict, cp)
        else:
            self.store.record_decision(
                symbol="*", side="-", action="halt",
                reason="; ".join(halts) or "regime forbids new entries")

        self._fill_state(st, marks)
        self.store.record_equity(self.equity, st.exposure_pct or 0.0,
                                 len(self.book.positions), st.regime)
        return st

    def _marks(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for s in self.markets or self.cfg.symbols:
            try:
                t: Ticker = self.ex.fetch_ticker(s)
            except (ExchangeError, NotImplementedError):
                continue
            if t.last:
                out[s] = t.last
        return out

    def _regime(self, marks: dict[str, float]) -> regime_mod.RegimeVerdict:
        tf_r = self.cfg.timeframes.regime
        bench = self._tapes.get(self.cfg.benchmark_symbol, {}).get(tf_r, [])
        closes = {s: [c.close for c in t.get(tf_r, [])]
                  for s, t in self._tapes.items()}
        breadth = regime_mod.breadth(closes)
        atr_pct = regime_mod.atr_percentile_now(bench) if bench else None
        inputs = regime_mod.RegimeInputs(
            btc_4h=bench, breadth_20=breadth, atr_percentile=atr_pct,
            data_ok=bool(bench),
            data_problems=[] if bench else ["no benchmark tape"])
        verdict = self.engine.update(inputs, self.clock(),
                                     symbols=list(self.markets),
                                     open_positions=list(self.book.positions))
        if verdict.transitioned and self.engine.transitions:
            d = self.engine.transitions[-1].as_dict()
            self.store.record_event("regime_transition", d)
            self.budget.on_regime_transition()
            log.info("regime transition %s", d)
        self.detector.observe("breadth", breadth)
        self.detector.observe("atr_percentile", atr_pct)
        return verdict

    # ------------------------------------------------------------ manage --
    def _manage(self, marks: dict[str, float]) -> None:
        """Trail, break even, time-stop, and enforce the protective invariant.

        A regime change NEVER widens or removes a stop (spec 5/21). It can
        tighten one and it can close a position; it cannot make an open trade
        riskier than it was when it was sized."""
        tf_s = self.cfg.timeframes.signal
        for sym, pos in list(self.book.positions.items()):
            mark = marks.get(sym)
            if mark is None:
                continue
            bars = self._tapes.get(sym, {}).get(tf_s, [])
            cache = (sig_mod.SeriesCache(bars, self.cfg.strategy)
                     if len(bars) >= sig_mod.min_bars_for(self.cfg.strategy)
                     else None)
            x = cache.at(cache.n - 1) if cache else None

            if not pos.protective_ok:
                if not self._attach_stop(pos):
                    self._close(pos, mark, "unprotected_position")
                    continue

            hit = ((mark >= pos.stop_price) if pos.side == "short"
                   else (mark <= pos.stop_price))
            if hit:
                self._close(pos, mark, "stop")
                continue

            if should_time_stop(pos, self.clock(),
                                self.cfg.strategy.max_holding_days):
                self._close(pos, mark, "time_stop")
                continue

            new_stop = pos.stop_price
            if pos.scaled_out > 0:
                new_stop = self._toward(pos, breakeven_stop(
                    pos, self.cfg.execution))
            if x is not None:
                new_stop = self._toward(
                    pos, trail_stop(pos, x["e20"][x["i"]], x["atr"]),
                    current=new_stop)
            if abs(new_stop - pos.stop_price) > 1e-12:
                if self._move_stop(pos, new_stop):
                    pos.stop_price = new_stop
                    self.store.upsert_position(pos)

    def _toward(self, pos: Position, candidate: float,
                current: float | None = None) -> float:
        """Monotone toward the position. THE stop invariant, in one place.
        A short's stop only ever falls; a long's only ever rises."""
        cur = pos.stop_price if current is None else current
        return min(cur, candidate) if pos.side == "short" else max(cur,
                                                                   candidate)

    # ------------------------------------------------------------- scan ---
    def _scan(self, marks: dict[str, float],
              verdict: regime_mod.RegimeVerdict, cp: Any) -> None:
        cfg = self.cfg
        tf_s, tf_r = cfg.timeframes.signal, cfg.timeframes.regime
        candidates: list[tuple[Signal, float]] = []
        for sym, market in (self.markets or {}).items():
            if sym in self.book.positions:
                continue
            bars = self._tapes.get(sym, {}).get(tf_s, [])
            rbars = self._tapes.get(sym, {}).get(tf_r, [])
            need = sig_mod.min_bars_for(cfg.strategy)
            if len(bars) < need or len(rbars) < need:
                self.store.record_decision(
                    symbol=sym, side="-", action="skip",
                    reason=f"insufficient closed history ({len(bars)}/"
                           f"{len(rbars)} vs {need})")
                continue
            sym_bear, _why = regime_mod.symbol_bearish(
                rbars, cfg.strategy.adx_threshold,
                cfg.strategy.structure_window, cfg.strategy)
            spread = self._spread(sym)
            for side in (["short"] + (["long"] if cfg.allow_longs else [])):
                if side == "short" and sym == cfg.benchmark_symbol \
                        and not self.engine.btc_short_confirmed():
                    self.store.record_decision(
                        symbol=sym, side=side, action="refuse",
                        reason="benchmark short needs extra confirmation")
                    continue
                if regime_mod.risk_multiplier(cfg.regime, verdict.regime,
                                              side) <= 0:
                    continue
                sig, rejects = sig_mod.evaluate(
                    sym, bars, side, regime=verdict.regime, cfg=cfg.strategy,
                    symbol_bearish_ok=sym_bear, timeframe=tf_s,
                    funding=self._funding(sym), spread_bps=spread,
                    max_spread_bps=cfg.execution.max_spread_bps)
                if sig is None:
                    for r in rejects:
                        self.store.record_decision(
                            symbol=sym, side=side, action="refuse",
                            reason=r.reason)
                    continue
                key = strategy_key(sig.strategy, sym, side,
                                   verdict.regime.value, tf_s)
                self.health.note_signal(key)
                h = self.health.get(key)
                self.store.record_signal(sig)
                if not h.may_enter:
                    self.store.record_decision(
                        symbol=sym, side=side, action="refuse",
                        reason=f"strategy health {h.state.value}",
                        signal_id=sig.signal_id)
                    continue
                bump_score = h.score_bump(cfg.strategy_health) + cp.score_bump
                bump_rr = h.rr_bump(cfg.strategy_health)
                if verdict.regime is Regime.NEUTRAL:
                    bump_score += cfg.regime.neutral_score_bump
                    bump_rr += max(0.0,
                                   cfg.regime.neutral_minimum_reward_risk
                                   - cfg.strategy.minimum_reward_risk)
                ok, why = sig_mod.admissible(
                    sig, cfg.strategy, verdict.regime,
                    score_bump=bump_score, rr_bump=bump_rr)
                if not ok:
                    self.store.record_decision(
                        symbol=sym, side=side, action="refuse", reason=why,
                        signal_id=sig.signal_id)
                    continue
                candidates.append((sig, sig.score.total))

        # Best score first: with a hard position cap, the ORDER decides which
        # ideas get the budget, and taking them in symbol order would give the
        # first-listed market permanent first refusal.
        for sig, _score in sorted(candidates, key=lambda kv: -kv[1]):
            self._try_enter(sig, verdict, cp, marks)

    def _try_enter(self, sig: Signal, verdict: Any, cp: Any,
                   marks: dict[str, float]) -> None:
        cfg = self.cfg
        may, why = self.budget.may_enter(
            symbol=sig.symbol, strategy=sig.strategy,
            signal_id=sig.signal_id, setup=sig.setup, score=sig.score.total,
            price=sig.entry, atr=sig.atr, now=self.clock(),
            in_regime_transition=verdict.transitioned)
        if not may:
            self.store.record_decision(symbol=sig.symbol, side=sig.side,
                                       action="refuse", reason=why,
                                       signal_id=sig.signal_id)
            return
        key = strategy_key(sig.strategy, sig.symbol, sig.side,
                           verdict.regime.value, cfg.timeframes.signal)
        h = self.health.get(key)
        exposure = self.book.exposure(marks)
        exposure.day_pnl = self.day_pnl
        exposure.week_pnl = self.week_pnl
        account = Account(equity=self.equity, free_collateral=self.equity,
                          margin_used=(exposure.gross_notional
                                       / max(cfg.risk.max_leverage, 1e-9)),
                          max_leverage=cfg.risk.max_leverage)
        sizing = size_position(
            signal=sig, market=self.markets[sig.symbol], account=account,
            exposure=exposure, risk_cfg=cfg.risk, exec_cfg=cfg.execution,
            regime_multiplier=regime_mod.risk_multiplier(
                cfg.regime, verdict.regime, sig.side),
            health_multiplier=(h.risk_multiplier(cfg.strategy_health)
                               * self.budget.consecutive_loss_multiplier(
                                   self.clock())
                               * cp.risk_multiplier),
            spread_bps=self._spread(sig.symbol),
            correlated_group_count=exposure.correlated_counts.get(
                group_of(sig.symbol), 0))
        if not sizing.ok:
            self.store.record_decision(symbol=sig.symbol, side=sig.side,
                                       action="refuse", reason=sizing.reason,
                                       signal_id=sig.signal_id)
            return
        plan = build_plan(signal=sig, sizing=sizing,
                          market=self.markets[sig.symbol],
                          cfg=cfg.execution, strat=cfg.strategy,
                          spread=self._spread(sig.symbol),
                          adapter_supports_stop=(
                              self.ex.capability("native_stop")
                              and self.ex.capability("reduce_only")),
                          adapter_supports_tp=(
                              self.ex.capability("native_take_profit")
                              and self.ex.capability("reduce_only")))
        self._place(sig, sizing, plan)

    # ------------------------------------------------------------ orders --
    def _place(self, sig: Signal, sizing: Any, plan: Any) -> None:
        """Entry, then stop, then targets -- and the stop is not optional.

        NEVER RETRIED BLINDLY. A signed order whose response we did not see
        may have reached the venue; resending it can double the position. On
        an ambiguous failure the loop stops and reports."""
        req: OrderRequest = plan.entry
        self.store.record_order(req, None)
        if not self.submit:
            res = self._paper_fill(req)
        else:
            try:
                res = self.ex.create_order(req)
            except ExchangeError as exc:
                self.store.record_decision(
                    symbol=req.symbol, side=req.side, action="error",
                    reason=f"entry submission failed, NOT retried: {exc}",
                    signal_id=sig.signal_id)
                self.store.record_event("order_error", {"req": req.as_dict(),
                                                        "error": repr(exc)})
                return
        self.store.record_order(req, res)
        if not res.accepted or res.filled <= 0:
            self.store.record_decision(
                symbol=req.symbol, side=req.side, action="skip",
                reason=f"entry not filled ({res.status or res.error})",
                signal_id=sig.signal_id)
            return

        pos = Position(symbol=req.symbol, side=req.side, quantity=res.filled,
                       entry_price=res.avg_price or sig.entry,
                       opened_ts=self.clock(), stop_price=plan.stop.trigger_price,
                       targets=list(sig.targets), strategy=sig.strategy,
                       signal_id=sig.signal_id,
                       r_unit=abs(sig.entry - sig.stop),
                       meta={"setup": sig.setup, "score": sig.score.total,
                             "regime": sig.regime.value,
                             "leverage": sizing.leverage})
        self.book.positions[pos.symbol] = pos
        self.store.upsert_position(pos)
        self.budget.record_entry(symbol=pos.symbol, strategy=sig.strategy,
                                 signal_id=sig.signal_id, setup=sig.setup,
                                 score=sig.score.total, price=pos.entry_price,
                                 now=self.clock())
        self.store.record_decision(symbol=pos.symbol, side=pos.side,
                                   action="enter",
                                   reason=f"score {sig.score.total:.1f} "
                                          f"{sig.setup}",
                                   signal_id=sig.signal_id,
                                   payload=plan.as_dict())
        if not self._attach_stop(pos, plan.stop):
            log.error("%s filled with NO protective stop -- closing", pos.symbol)
            self._close(pos, pos.entry_price, "unprotected_position")
            return
        for tp in plan.targets:
            self._send_protective(tp)

    def _attach_stop(self, pos: Position,
                     req: OrderRequest | None = None) -> bool:
        if req is None:
            req = OrderRequest(
                symbol=pos.symbol, side=pos.side,
                action=side_to_action(pos.side, closing=True),
                intent=OrderIntent.STOP, order_type="stop",
                quantity=pos.quantity, price=None,
                trigger_price=pos.stop_price, reduce_only=True,
                client_order_id=f"stop-{pos.symbol}-{int(self.clock())}",
                signal_id=pos.signal_id)
        res = self._send_protective(req)
        pos.protective_ok = bool(res and res.accepted)
        pos.stop_order_id = res.order_id if res else None
        self.store.upsert_position(pos)
        return pos.protective_ok

    def _send_protective(self, req: OrderRequest):
        """Protective orders are reduce-only, ALWAYS. `use_reduce_only_exits`
        is validated true in live mode, so this cannot be configured away."""
        if not req.reduce_only and self.submit:
            log.error("refusing to send a non-reduce-only exit for %s",
                      req.symbol)
            return None
        self.store.record_order(req, None)
        if not self.submit:
            res = OrderResult(accepted=True, order_id=req.client_order_id,
                              status="resting", submitted=False)
        else:
            try:
                res = self.ex.create_order(req)
            except (ExchangeError, NotImplementedError) as exc:
                self.store.record_event("protective_failed",
                                        {"req": req.as_dict(),
                                         "error": repr(exc)})
                return None
        self.store.record_order(req, res)
        return res

    def _move_stop(self, pos: Position, new_stop: float) -> bool:
        """Cancel-then-place, in that order. Placing first can leave two
        resting stops and close the position twice."""
        if self.submit and pos.stop_order_id:
            try:
                self.ex.cancel_order(pos.symbol, pos.stop_order_id)
            except (ExchangeError, NotImplementedError) as exc:
                log.warning("could not cancel the old stop on %s: %s -- "
                            "leaving the existing (wider) stop in place",
                            pos.symbol, exc)
                return False
        old, pos.stop_price = pos.stop_price, new_stop
        if self._attach_stop(pos):
            return True
        pos.stop_price = old
        return False

    def _paper_fill(self, req: OrderRequest) -> OrderResult:
        px = req.price or 0.0
        return OrderResult(accepted=True, order_id=req.client_order_id,
                           status="filled", filled=req.quantity,
                           avg_price=px, submitted=False)

    def _close(self, pos: Position, mark: float, reason: str) -> None:
        req = OrderRequest(
            symbol=pos.symbol, side=pos.side,
            action=side_to_action(pos.side, closing=True),
            intent=OrderIntent.FLATTEN, order_type="market",
            quantity=pos.quantity, price=None, reduce_only=True,
            client_order_id=f"exit-{pos.symbol}-{int(self.clock())}",
            signal_id=pos.signal_id)
        self.store.record_order(req, None)
        if self.submit:
            try:
                res = self.ex.create_order(req)
                px = res.avg_price or mark
                self.store.record_order(req, res)
            except (ExchangeError, NotImplementedError) as exc:
                self.store.record_event("close_failed",
                                        {"symbol": pos.symbol,
                                         "error": repr(exc)})
                log.error("FAILED TO CLOSE %s: %s", pos.symbol, exc)
                return
        else:
            px = mark
        sgn = 1.0 if pos.side == "long" else -1.0
        pnl = sgn * (px - pos.entry_price) * pos.quantity
        fee = abs(px * pos.quantity) * self.cfg.execution.taker_fee
        pnl -= fee
        trade = Trade(symbol=pos.symbol, side=pos.side, strategy=pos.strategy,
                      setup=str(pos.meta.get("setup", "")),
                      regime=str(pos.meta.get("regime", "")),
                      opened_ts=pos.opened_ts, closed_ts=self.clock(),
                      entry=pos.entry_price, exit=px, quantity=pos.quantity,
                      pnl=pnl, fees=fee, funding=0.0,
                      r_multiple=(pnl / (pos.r_unit * pos.quantity)
                                  if pos.r_unit > 0 and pos.quantity > 0
                                  else 0.0),
                      reason=reason, signal_id=pos.signal_id,
                      score=float(pos.meta.get("score", 0.0)))
        self.book.positions.pop(pos.symbol, None)
        self.book.record_close(trade)
        self.store.drop_position(pos.symbol)
        self.store.record_trade(trade)
        self.equity += pnl
        self.day_pnl += pnl
        self.week_pnl += pnl
        self.budget.record_exit(symbol=pos.symbol, signal_id=pos.signal_id,
                                pnl=pnl, price=px, now=self.clock())
        self.store.record_event("trade_closed",
                                {"symbol": pos.symbol, "pnl": round(pnl, 4),
                                 "reason": reason})
        self.health.record(strategy_key(pos.strategy, pos.symbol, pos.side,
                                        str(pos.meta.get("regime", "*")),
                                        self.cfg.timeframes.signal),
                           trade, reference_equity=self.equity)
        self.store.record_decision(symbol=pos.symbol, side=pos.side,
                                   action="exit", reason=reason,
                                   signal_id=pos.signal_id,
                                   payload={"pnl": pnl, "price": px})

    # -------------------------------------------------------- emergency ---
    def emergency_flatten(self) -> dict[str, Any]:
        """Close everything, cancel everything. The ONE path that may send a
        closing order without a matching protective order."""
        out: dict[str, Any] = {"closed": [], "errors": []}
        marks = self._marks()
        for sym, pos in list(self.book.positions.items()):
            try:
                self._close(pos, marks.get(sym, pos.entry_price), "flatten")
                out["closed"].append(sym)
            except Exception as exc:                        # noqa: BLE001
                out["errors"].append({"symbol": sym, "error": repr(exc)})
        if self.submit:
            try:
                self.ex.cancel_all_orders()
            except (ExchangeError, NotImplementedError) as exc:
                out["errors"].append({"cancel_all": repr(exc)})
        self.store.record_event("flatten", out)
        return out

    # ---------------------------------------------------------- reporting --
    def _fill_state(self, st: LoopState, marks: dict[str, float]) -> None:
        st.equity = self.equity
        st.day_pnl = self.day_pnl
        st.week_pnl = self.week_pnl
        exp = self.book.exposure(marks)
        st.exposure_pct = (100.0 * exp.gross_notional / self.equity
                           if self.equity > 0 else None)
        margin = exp.gross_notional / max(self.cfg.risk.max_leverage, 1e-9)
        st.margin_pct = (100.0 * margin / self.equity
                         if self.equity > 0 else None)
        closes = {s: [c.close for c in t.get(self.cfg.timeframes.signal, [])]
                  for s, t in self._tapes.items()}
        st.effective_bets = effective_bets(list(self.book.positions), closes)
        st.positions = []
        for sym, p in self.book.positions.items():
            mark = marks.get(sym)
            st.positions.append({
                "symbol": sym, "side": p.side, "quantity": p.quantity,
                "entry_price": p.entry_price, "stop_price": p.stop_price,
                "r_multiple": (p.r_multiple(mark) if mark else None),
                "unrealized": (p.unrealized(mark) if mark else None),
                "held_h": (self.clock() - p.opened_ts) / 3600.0,
                "protective_ok": p.protective_ok})
        st.strategy_health = self.health.snapshot()
        st.recent_decisions = self.store.decisions(limit=10)

    def _spread(self, symbol: str) -> float | None:
        try:
            t = self.ex.fetch_ticker(symbol)
        except (ExchangeError, NotImplementedError):
            return None
        return spread_bps(t.bid, t.ask)

    def _funding(self, symbol: str) -> float | None:
        try:
            return self.ex.fetch_funding_rate(symbol)
        except (ExchangeError, NotImplementedError):
            return None
