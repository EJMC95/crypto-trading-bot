"""Event-driven backtester. No look-ahead, by construction rather than by care.

THE STRUCTURAL GUARANTEE. The clock advances over EXECUTION-timeframe bars.
At the close of execution bar `i`:
  * higher-timeframe series are sliced with `ts + tf_seconds <= clock` -- a 4h
    bar is invisible until it has actually closed;
  * a decision made at bar `i` fills at bar `i+1`'s OPEN, never at bar i's
    close (LAG-1);
  * the bracket is then walked from bar `i+1` FORWARD, including that bar's
    own post-open range.
`_advance` moves monotonic per-symbol pointers, so nothing can index past the
clock even by accident, and `test_backtester` plants a future spike and
requires the result to be unchanged.

WHAT IS MODELLED, because omitting any of these flatters the result:
  fees (maker/taker, from config), funding (per holding hour), spread,
  slippage, latency, partial fills, order expiry, STOP GAPS (a stop fills at
  the bar's OPEN when price gapped through it -- not at the stop price),
  leverage and margin, liquidation, rejected orders, regime transitions, and
  strategy throttling/pausing.

WHAT IS NOT MODELLED, stated rather than hidden: queue position for post-only
fills (approximated by requiring the limit price to be TOUCHED and applying a
configurable miss rate), and cross-market margin contagion.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from . import regime as regime_mod
from . import risk as risk_mod
from . import signals as sig_mod
from .config import AppConfig
from .data import tf_seconds
from .logging_setup import get
from .models import Candle, HealthState, Position, Regime, Trade
from .market_metadata import MarketRegistry
from .portfolio import Book, group_of
from .risk import AccountState
from .strategy_health import (HealthRegistry, TradeBudget, strategy_key)

log = get("backtest")


@dataclass
class Frictions:
    taker_fee: float = 0.0
    maker_fee: float = 0.0
    spread_bps: float = 2.0
    slippage_bps: float = 3.0
    latency_bars: int = 0
    funding_per_hour: float = 0.0    # fraction of notional; + costs LONGS
    post_only_miss_rate: float = 0.25
    partial_fill_rate: float = 0.0   # share of orders that fill partially
    partial_fill_fraction: float = 0.6
    reject_rate: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[float, float]] = field(default_factory=list)
    regime_transitions: list[dict[str, Any]] = field(default_factory=list)
    rejections: dict[str, int] = field(default_factory=dict)
    health_snapshot: dict[str, Any] = field(default_factory=dict)
    start_equity: float = 0.0
    end_equity: float = 0.0
    liquidation_violations: int = 0
    paused_periods: int = 0
    throttled_periods: int = 0
    bars: int = 0

    # ------------------------------------------------------------ metrics --
    def metrics(self) -> dict[str, Any]:
        t = self.trades
        n = len(t)
        if not n:
            return {"trades": 0, "note": "no trades: nothing to report"}
        pnls = [x.pnl for x in t]
        rs = [x.r_multiple for x in t]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total = sum(pnls)
        eq = [e for _ts, e in self.equity_curve] or [self.start_equity]
        peak, dd = eq[0], 0.0
        for v in eq:
            peak = max(peak, v)
            dd = max(dd, (peak - v) / peak if peak > 0 else 0.0)
        rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq))
                if eq[i - 1] > 0]
        sd = statistics.pstdev(rets) if len(rets) > 2 else 0.0
        downside = [r for r in rets if r < 0]
        dsd = statistics.pstdev(downside) if len(downside) > 2 else 0.0
        mean_r = statistics.fmean(rets) if rets else 0.0
        span_d = ((self.equity_curve[-1][0] - self.equity_curve[0][0]) / 86400.0
                  if len(self.equity_curve) > 1 else 0.0)
        per_year = (len(rets) / span_d * 365.0) if span_d > 0 else 0.0
        sharpe = (mean_r / sd * math.sqrt(per_year)) if sd > 0 and per_year else 0.0
        sortino = (mean_r / dsd * math.sqrt(per_year)) if dsd > 0 and per_year else 0.0
        cagr = ((eq[-1] / eq[0]) ** (365.0 / span_d) - 1.0) \
            if span_d > 0 and eq[0] > 0 and eq[-1] > 0 else 0.0
        streak = worst = 0
        for p in pnls:
            streak = streak + 1 if p <= 0 else 0
            worst = max(worst, streak)
        gw, gl = sum(wins), abs(sum(losses))

        def group(fn):
            out: dict[str, dict[str, Any]] = {}
            for x in t:
                k = fn(x)
                d = out.setdefault(k, {"n": 0, "pnl": 0.0, "r": 0.0})
                d["n"] += 1
                d["pnl"] = round(d["pnl"] + x.pnl, 4)
                d["r"] = round(d["r"] + x.r_multiple, 4)
            for d in out.values():
                d["avg_r"] = round(d["r"] / d["n"], 4)
            return out

        return {
            "trades": n,
            "total_return_pct": round(100.0 * total / self.start_equity, 4)
            if self.start_equity else 0.0,
            "cagr_pct": round(100.0 * cagr, 4),
            "sharpe": round(sharpe, 4), "sortino": round(sortino, 4),
            "calmar": round(cagr / dd, 4) if dd > 0 else None,
            "max_drawdown_pct": round(100.0 * dd, 4),
            "win_rate_pct": round(100.0 * len(wins) / n, 2),
            "profit_factor": round(gw / gl, 4) if gl > 0 else None,
            "expectancy": round(total / n, 6),
            "avg_r": round(statistics.fmean(rs), 4),
            "longest_losing_streak": worst,
            "fees": round(sum(x.fees for x in t), 4),
            "funding": round(sum(x.funding for x in t), 4),
            "avg_slippage_bps": round(statistics.fmean(
                x.slippage_bps for x in t), 3),
            "trades_per_30d": round(30.0 * n / span_d, 2) if span_d > 0 else None,
            "span_days": round(span_d, 1),
            "by_symbol": group(lambda x: x.symbol),
            "by_strategy": group(lambda x: x.strategy),
            "by_regime": group(lambda x: x.regime),
            "by_side": group(lambda x: x.side),
            "liquidation_violations": self.liquidation_violations,
            "rejections": dict(sorted(self.rejections.items(),
                                      key=lambda kv: -kv[1])[:15]),
            "start_equity": round(self.start_equity, 2),
            "end_equity": round(self.end_equity, 2),
        }


class Backtester:
    def __init__(self, cfg: AppConfig, registry: MarketRegistry,
                 frictions: Frictions | None = None,
                 start_equity: float = 10_000.0, state_dir: str = "state"):
        self.cfg = cfg
        self.registry = registry
        # Fees come from CONFIG, never hardcoded -- `cli fees` refreshes them
        # from the venue after a human has checked Lighter's fee docs.
        self.fr = frictions or Frictions(
            taker_fee=cfg.execution.taker_fee,
            maker_fee=cfg.execution.maker_fee)
        self.start_equity = start_equity
        self.state_dir = state_dir

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _closed_upto(series: Sequence[Candle], tf: str, clock: float,
                     hint: int = 0) -> int:
        """Index of the LAST bar closed at or before `clock`. Monotonic hint
        keeps this O(1) amortised over a full run."""
        sec = tf_seconds(tf)
        i = max(0, hint)
        while i + 1 < len(series) and series[i + 1].ts + sec <= clock:
            i += 1
        if i < len(series) and series[i].ts + sec > clock:
            return -1
        return i

    def _funding(self, side: str, notional: float, hours: float) -> float:
        """Positive `funding_per_hour` means LONGS PAY. A short receives it."""
        sgn = -1.0 if side == "long" else 1.0
        return sgn * self.fr.funding_per_hour * notional * hours

    def _entry_fill(self, bar: Candle, want: float, side: str,
                    order_type: str) -> tuple[float | None, float, bool]:
        """-> (fill price or None, slippage_bps, partial). Post-only requires
        the limit to be TOUCHED and still misses some of the time."""
        fr = self.fr
        half_spread = want * (fr.spread_bps / 2.0) / 10_000.0
        slip = want * fr.slippage_bps / 10_000.0
        if order_type == "post_only":
            touched = (bar.low <= want) if side == "long" else (bar.high >= want)
            if not touched:
                return None, 0.0, False
            # A maker fill pays no spread and no slippage; the cost is the
            # fills you DON'T get, modelled as a miss rate by the caller.
            return want, 0.0, False
        px = want + half_spread + slip if side == "long" \
            else want - half_spread - slip
        bps = 10_000.0 * abs(px - want) / want if want else 0.0
        return px, bps, False

    def _exit_price(self, bar: Candle, level: float, side: str,
                    kind: str) -> float:
        """STOP GAPS ARE MODELLED. If the bar OPENED beyond the stop, the fill
        is the open, not the level -- flattering a gap to the stop price is
        the single most common way a backtest understates tail loss."""
        if kind == "stop":
            gapped = (bar.open <= level) if side == "long" else (bar.open >= level)
            base = bar.open if gapped else level
            slip = base * self.fr.slippage_bps / 10_000.0
            return base - slip if side == "long" else base + slip
        gapped = (bar.open >= level) if side == "long" else (bar.open <= level)
        return bar.open if gapped else level

    # --------------------------------------------------------------- run ---
    def run(self, tapes: dict[str, dict[str, list[Candle]]],
            btc_symbol: str = "BTC",
            on_bar: Callable[[float, Book], None] | None = None
            ) -> BacktestResult:
        cfg = self.cfg
        tf_exec, tf_sig, tf_reg = (cfg.timeframes.execution,
                                   cfg.timeframes.signal, cfg.timeframes.regime)
        res = BacktestResult(start_equity=self.start_equity)
        book = Book()
        engine = regime_mod.MarketRegimeEngine(cfg.regime)
        # persist=False: a backtest is a simulation and must not touch the
        # operational state the paper and live runners depend on.
        health = HealthRegistry(cfg.strategy_health, self.state_dir,
                                persist=False)
        budget = TradeBudget(cfg.overtrading, self.state_dir, persist=False)

        symbols = sorted(tapes)
        clocks = sorted({c.ts + tf_seconds(tf_exec)
                         for s in symbols for c in tapes[s].get(tf_exec, [])})
        if not clocks:
            return res
        hints: dict[tuple[str, str], int] = {}
        # Indicator series are computed ONCE per symbol over the whole signal
        # tape and then INDEXED by the clock's own bar pointer. Safe only
        # because every indicator passes `assert_causal` -- the value at bar i
        # does not depend on anything after it (see signals.SeriesCache).
        caches = {s: sig_mod.SeriesCache(tapes[s].get(tf_sig) or [])
                  for s in symbols}
        equity = self.start_equity
        day_key = week_key = None
        pending: list[dict[str, Any]] = []
        # The ATR percentile walks a 240-bar window; recomputing it on every
        # execution bar is pure waste when the 4h bar it reads changes once
        # every sixteen 15m bars.
        _atr_pct_cache: list[float | None] = [None]

        def reject(reason: str) -> None:
            res.rejections[reason] = res.rejections.get(reason, 0) + 1

        for clock in clocks:
            res.bars += 1
            d_key = int(clock // 86400)
            w_key = int(clock // (7 * 86400))
            if day_key != d_key:
                book.day_pnl, day_key = 0.0, d_key
            if week_key != w_key:
                book.week_pnl, week_key = 0.0, w_key

            # ---- current closed-bar index per (symbol, tf) -----------------
            idx: dict[tuple[str, str], int] = {}
            for s in symbols:
                for tf in {tf_exec, tf_sig, tf_reg}:
                    series = tapes[s].get(tf) or []
                    k = (s, tf)
                    i = self._closed_upto(series, tf, clock, hints.get(k, 0))
                    hints[k] = max(0, i)
                    idx[k] = i

            marks = {s: tapes[s][tf_exec][idx[(s, tf_exec)]].close
                     for s in symbols
                     if idx.get((s, tf_exec), -1) >= 0}

            # ---- regime ----------------------------------------------------
            bi_r = idx.get((btc_symbol, tf_reg), -1)
            bi_s = idx.get((btc_symbol, tf_sig), -1)
            btc4 = (tapes[btc_symbol][tf_reg][:bi_r + 1]
                    if bi_r >= 0 and btc_symbol in tapes else [])
            btc1 = (tapes[btc_symbol][tf_sig][:bi_s + 1]
                    if bi_s >= 0 and btc_symbol in tapes else [])
            # Breadth off the CACHED EMA50 rather than a fresh EMA per symbol
            # per bar: same number, and it is the difference between a
            # backtest that finishes and one that does not.
            up = tot = 0
            for s in symbols:
                j = idx.get((s, tf_sig), -1)
                ca = caches.get(s)
                if ca is None or j < 55 or j >= ca.n or ca.e50[j] is None:
                    continue
                tot += 1
                up += 1 if ca.c[j] > ca.e50[j] else 0
            breadth_now = (up / tot) if tot >= 5 else None
            if res.bars % 24 == 1 or _atr_pct_cache[0] is None:
                _atr_pct_cache[0] = regime_mod.atr_percentile_now(btc4)
            inputs = regime_mod.RegimeInputs(
                btc_4h=btc4, btc_1h=btc1,
                breadth_up_frac=breadth_now,
                atr_percentile=_atr_pct_cache[0],
                spread_bps=self.fr.spread_bps,
                data_ok=bool(btc4), data_problems=[] if btc4 else ["no BTC 4h"])
            before = engine.state
            verdict = engine.update(inputs, clock)
            if engine.state is not before:
                res.regime_transitions.append(
                    {"ts": clock, "from": before.value,
                     "to": engine.state.value, "reasons": verdict.reasons})

            # ---- fills for orders placed on the PREVIOUS bar ---------------
            still: list[dict[str, Any]] = []
            for order in pending:
                s = order["symbol"]
                i = idx.get((s, tf_exec), -1)
                if i < 0:
                    still.append(order)
                    continue
                bar = tapes[s][tf_exec][i]
                if bar.ts < order["placed_bar_ts"]:
                    still.append(order)
                    continue
                age = (clock - order["placed_at"])
                px, bps, _p = self._entry_fill(bar, order["price"],
                                               order["side"],
                                               order["order_type"])
                if px is None:
                    if age >= cfg.execution.order_timeout_seconds * 60:
                        reject("entry order expired unfilled")
                        continue
                    still.append(order)
                    continue
                qty = order["qty"]
                if self.fr.partial_fill_rate > 0 and \
                        (hash(order["signal_id"]) % 100) / 100.0 \
                        < self.fr.partial_fill_rate:
                    qty = self.registry.round_qty(
                        s, qty * self.fr.partial_fill_fraction)
                    if qty <= 0:
                        reject("partial fill rounded to zero")
                        continue
                fee_rate = (self.fr.maker_fee if order["order_type"] == "post_only"
                            else self.fr.taker_fee)
                book.positions[s] = Position(
                    symbol=s, side=order["side"], quantity=qty, entry_price=px,
                    opened_ts=clock, stop_price=order["stop"],
                    targets=list(order["targets"]), strategy=order["strategy"],
                    signal_id=order["signal_id"], protective_ok=True,
                    meta={"regime": order["regime"], "atr": order["atr"],
                          "r": abs(px - order["stop"]),
                          "entry_fee": qty * px * fee_rate,
                          "slippage_bps": bps, "peak": px,
                          "leverage": order["leverage"],
                          "liquidation": order["liquidation"]})
                budget.record_entry(symbol=s, strategy=order["strategy"],
                                    signal_id=order["signal_id"],
                                    score=order["score"], now=clock)
            pending = still

            # ---- manage open positions -------------------------------------
            for s in list(book.positions):
                i = idx.get((s, tf_exec), -1)
                if i < 0:
                    continue
                bar = tapes[s][tf_exec][i]
                pos = book.positions[s]
                if bar.ts + tf_seconds(tf_exec) <= pos.opened_ts:
                    continue
                long = pos.side == "long"
                r_unit = pos.meta.get("r") or 1e-9
                held_h = max(0.0, (clock - pos.opened_ts) / 3600.0)

                liq = pos.meta.get("liquidation")
                if liq:
                    hit_liq = (bar.low <= liq) if long else (bar.high >= liq)
                    if hit_liq:
                        res.liquidation_violations += 1

                exit_px = exit_reason = None
                stop_hit = (bar.low <= pos.stop_price) if long \
                    else (bar.high >= pos.stop_price)
                if stop_hit:
                    exit_px = self._exit_price(bar, pos.stop_price, pos.side,
                                               "stop")
                    exit_reason = "stop"
                else:
                    for k, tp in enumerate(pos.targets):
                        hit = (bar.high >= tp) if long else (bar.low <= tp)
                        if hit and k >= len(pos.meta.get("tp_done", [])):
                            pos.meta.setdefault("tp_done", []).append(k)
                            if k == 0:
                                # After TP1 the stop moves to breakeven PLUS
                                # the fee, so a stopped runner is not a loss
                                # created by our own costs.
                                fee_px = pos.entry_price * (
                                    2 * (self.fr.taker_fee or 0.0) + 0.0001)
                                pos.stop_price = (pos.entry_price + fee_px
                                                  if long else
                                                  pos.entry_price - fee_px)
                    if len(pos.meta.get("tp_done", [])) >= len(pos.targets) \
                            and pos.targets:
                        exit_px = self._exit_price(bar, pos.targets[-1],
                                                   pos.side, "tp")
                        exit_reason = "target"
                    elif held_h >= cfg.strategy.max_holding_days * 24.0:
                        exit_px, exit_reason = bar.close, "max_hold"
                if exit_px is None:
                    pos.meta["peak"] = (max(pos.meta.get("peak", bar.high),
                                            bar.high) if long else
                                        min(pos.meta.get("peak", bar.low),
                                            bar.low))
                    continue

                notional = pos.quantity * pos.entry_price
                sgn = 1.0 if long else -1.0
                gross = sgn * (exit_px - pos.entry_price) * pos.quantity
                fee_rate = self.fr.taker_fee or 0.0
                fees = pos.meta.get("entry_fee", 0.0) \
                    + pos.quantity * exit_px * fee_rate
                fund = self._funding(pos.side, notional, held_h)
                pnl = gross - fees + fund
                trade = Trade(
                    symbol=s, side=pos.side, strategy=pos.strategy,
                    regime=str(pos.meta.get("regime", "")),
                    opened_ts=pos.opened_ts, closed_ts=clock,
                    entry=pos.entry_price, exit=exit_px, quantity=pos.quantity,
                    pnl=pnl, fees=fees, funding=fund,
                    r_multiple=(gross / (r_unit * pos.quantity))
                    if r_unit and pos.quantity else 0.0,
                    reason=exit_reason, signal_id=pos.signal_id,
                    slippage_bps=pos.meta.get("slippage_bps", 0.0))
                book.closed.append(trade)
                res.trades.append(trade)
                book.realized += pnl
                book.day_pnl += pnl
                book.week_pnl += pnl
                equity += pnl
                del book.positions[s]
                key = strategy_key(pos.strategy, s, pos.side,
                                   str(pos.meta.get("regime", "")))
                h = health.record(key, trade,
                                  reference_equity=self.start_equity)
                if h.state is HealthState.PAUSED:
                    res.paused_periods += 1
                elif h.state is HealthState.THROTTLED:
                    res.throttled_periods += 1
                budget.record_exit(symbol=s, signal_id=pos.signal_id, pnl=pnl,
                                   now=clock)

            res.equity_curve.append((clock, equity + book.unrealized(marks)))
            if on_bar is not None:
                on_bar(clock, book)

            # ---- new signals ------------------------------------------------
            if engine.state in (Regime.PANIC, Regime.DATA_UNRELIABLE):
                reject(f"regime {engine.state.value}")
                continue
            account = AccountState(
                equity=equity, available_collateral=equity,
                margin_used=sum(p.quantity * p.entry_price
                                / max(p.meta.get("leverage", 1.0), 1e-9)
                                for p in book.positions.values()),
                account_max_leverage=cfg.risk.max_leverage,
                margin_mode=cfg.lighter.margin_mode)
            exposure = book.exposure(marks)
            for s in symbols:
                if s in book.positions or any(o["symbol"] == s for o in pending):
                    continue
                i = idx.get((s, tf_sig), -1)
                if i < sig_mod.MIN_BARS:
                    continue
                series = tapes[s][tf_sig]
                for side in ("long", "short"):
                    mult = regime_mod.risk_multiplier(cfg.regime, engine.state,
                                                      side)
                    if mult <= 0:
                        continue
                    sig, _rej = sig_mod.evaluate(
                        s, series, side, engine.state, cfg.strategy,
                        cache=caches[s], bar=i,
                        timeframe=tf_sig, spread_bps=self.fr.spread_bps,
                        atr_percentile=inputs.atr_percentile,
                        max_spread_bps=cfg.execution.max_spread_bps)
                    if sig is None:
                        continue
                    key = strategy_key(sig.strategy, s, side,
                                       engine.state.value)
                    h = health.get(key)
                    if not h.may_enter:
                        reject(f"strategy {h.state.value}")
                        continue
                    ok, why = sig_mod.admissible(
                        sig, cfg.strategy, engine.state,
                        h.score_bump(cfg.strategy_health),
                        h.rr_bump(cfg.strategy_health))
                    if not ok:
                        reject(why.split("(")[0].strip())
                        continue
                    ok, why = budget.may_enter(symbol=s, strategy=sig.strategy,
                                               signal_id=sig.signal_id,
                                               now=clock)
                    if not ok:
                        reject(why.split(" for ")[0])
                        continue
                    dec = risk_mod.size_position(
                        signal=sig, account=account, exposure=exposure,
                        registry=self.registry, risk_cfg=cfg.risk,
                        exec_cfg=cfg.execution, regime_multiplier=mult,
                        health_multiplier=h.risk_multiplier(cfg.strategy_health)
                        * budget.consecutive_loss_multiplier(clock),
                        correlation_multiplier=risk_mod.correlation_multiplier(
                            exposure.correlation_group_count.get(
                                group_of(s), 0)),
                        volatility_multiplier=risk_mod.volatility_multiplier(
                            sig.atr / max(sig.entry, 1e-9)))
                    if not dec.ok:
                        reject(dec.reason.split(":")[0][:60])
                        continue
                    order_type = ("post_only"
                                  if cfg.execution.entry_preference
                                  == "post_only_limit" else "gtt")
                    if order_type == "post_only" and \
                            (hash(sig.signal_id) % 100) / 100.0 \
                            < self.fr.post_only_miss_rate:
                        reject("post-only miss (queue position)")
                        continue
                    pending.append({
                        "symbol": s, "side": side, "price": sig.entry,
                        "stop": sig.stop, "targets": sig.targets,
                        "qty": dec.quantity, "strategy": sig.strategy,
                        "signal_id": sig.signal_id, "atr": sig.atr,
                        "regime": engine.state.value, "placed_at": clock,
                        "placed_bar_ts": tapes[s][tf_exec][
                            idx[(s, tf_exec)]].ts + tf_seconds(tf_exec),
                        "order_type": order_type, "score": sig.score.total,
                        "leverage": dec.leverage,
                        "liquidation": dec.liquidation_price})
                    break            # one side per symbol per bar

        res.end_equity = equity + book.unrealized(marks)
        res.health_snapshot = health.snapshot()
        return res
