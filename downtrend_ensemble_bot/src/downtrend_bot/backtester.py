"""Event-driven backtester. No look-ahead by CONSTRUCTION, not by care.

THE STRUCTURAL GUARANTEE. The clock advances over EXECUTION-timeframe bars.
At the close of execution bar `i`:
  * higher-timeframe series are sliced with `ts + tf_seconds <= clock`, so a
    4h bar is invisible until it has actually closed;
  * a decision made at bar `i` fills at bar `i+1`'s OPEN (LAG-1);
  * the bracket is then walked FORWARD from that bar, including its own
    post-open range.
`test_backtester` plants a spike in the FUTURE and requires the result to be
byte-identical.

WHAT IS MODELLED, because omitting any of these flatters the result: maker and
taker fees, funding per holding hour, spread, slippage, latency, partial
fills, order expiry, **STOP GAPS** (a stop that gapped fills at the bar's
OPEN, not at the stop price), leverage and margin, liquidation, rejected
orders, regime transitions, strategy throttling and pausing, cooldowns and
trade budgets.

WHAT IS NOT MODELLED, stated rather than hidden: queue position for passive
limits (approximated by requiring the price to be TOUCHED plus a configurable
miss rate), cross-margin contagion between symbols, and exchange downtime
beyond a configurable reject rate.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from . import execution as ex
from . import regime as regime_mod
from . import risk as risk_mod
from . import signals as sig_mod
from .changepoint import ChangePointDetector
from .config import AppConfig
from .health import StrategyHealthMonitor, StrategyState, strategy_key
from .logging_setup import get
from .models import Candle, Market, Position, Regime, Trade
from .portfolio import Book, TradeBudget, group_of
from .risk import Account

log = get("backtest")

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
              "4h": 14400, "1d": 86400}


#: Below this span, an annualised figure is an extrapolation of noise -- and
#: at very small spans the exponentiation overflows outright.
MIN_ANNUALISE_DAYS = 7.0


def tf_seconds(tf: str) -> int:
    if tf not in TF_SECONDS:
        raise ValueError(f"unsupported timeframe {tf!r}")
    return TF_SECONDS[tf]


@dataclass
class Frictions:
    maker_fee: float = 0.0002
    taker_fee: float = 0.00055
    spread_bps: float = 3.0
    slippage_bps: float = 4.0
    funding_per_hour: float = 0.0000125   # +ve costs LONGS, PAYS shorts
    limit_miss_rate: float = 0.20
    partial_fill_rate: float = 0.10
    partial_fill_fraction: float = 0.6
    reject_rate: float = 0.0
    latency_bars: int = 0


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[float, float]] = field(default_factory=list)
    regime_transitions: list[dict[str, Any]] = field(default_factory=list)
    rejections: dict[str, int] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    changepoints: list[dict[str, Any]] = field(default_factory=list)
    start_equity: float = 0.0
    end_equity: float = 0.0
    bars: int = 0
    liquidations: int = 0
    throttled_bars: int = 0
    paused_bars: int = 0
    exposure_curve: list[tuple[float, float]] = field(default_factory=list)

    # -------------------------------------------------------------- report --
    def metrics(self) -> dict[str, Any]:
        t = self.trades
        n = len(t)
        if not n:
            return {"trades": 0,
                    "note": "no trades were taken -- read the rejection table "
                            "before changing a threshold",
                    "rejections": dict(sorted(self.rejections.items(),
                                              key=lambda kv: -kv[1])[:15])}
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
        # ANNUALISING A SHORT SPAN IS BOTH MEANINGLESS AND DANGEROUS.
        # `(1 + r) ** (365 / span)` on a span of seconds raises the exponent
        # into the millions and OverflowErrors -- so the metric that REPORTS
        # the run is what kills the run. Below a floor the honest answer is
        # None ("not annualisable"), never a fabricated number and never a
        # crash; `fmt` renders None as `-`, distinct from a measured 0.0.
        cagr = None
        if span_d >= MIN_ANNUALISE_DAYS and eq[0] > 0 and eq[-1] > 0:
            try:
                cagr = (eq[-1] / eq[0]) ** (365.0 / span_d) - 1.0
            except (OverflowError, ValueError):
                cagr = None
        streak = worst = 0
        for p in pnls:
            streak = streak + 1 if p <= 0 else 0
            worst = max(worst, streak)
        gw, gl = sum(wins), abs(sum(losses))
        srt = sorted(pnls)
        tail = srt[:max(1, n // 20)]                 # worst 5%

        def group(fn):
            out: dict[str, dict[str, Any]] = {}
            for x in t:
                d = out.setdefault(fn(x), {"n": 0, "pnl": 0.0, "r": 0.0})
                d["n"] += 1
                d["pnl"] = round(d["pnl"] + x.pnl, 4)
                d["r"] = round(d["r"] + x.r_multiple, 4)
            for d in out.values():
                d["avg_r"] = round(d["r"] / d["n"], 4)
            return out

        monthly: dict[str, float] = {}
        for x in t:
            import time as _t
            key = _t.strftime("%Y-%m", _t.gmtime(x.closed_ts))
            monthly[key] = round(monthly.get(key, 0.0) + x.pnl, 4)

        top3 = sum(sorted(pnls, reverse=True)[:3])
        exposure = [v for _ts, v in self.exposure_curve]
        return {
            "trades": n,
            "total_return_pct": round(100.0 * total / self.start_equity, 4)
            if self.start_equity else 0.0,
            "cagr_pct": (None if cagr is None else round(100.0 * cagr, 4)),
            "sharpe": round(sharpe, 4), "sortino": round(sortino, 4),
            "calmar": (round(cagr / dd, 4)
                       if (dd > 0 and cagr is not None) else None),
            "max_drawdown_pct": round(100.0 * dd, 4),
            "average_trade": round(total / n, 6),
            "win_rate_pct": round(100.0 * len(wins) / n, 2),
            "profit_factor": round(gw / gl, 4) if gl > 0 else None,
            "expectancy": round(total / n, 6),
            "avg_r": round(statistics.fmean(rs), 4),
            "longest_losing_streak": worst,
            "monthly_returns": dict(sorted(monthly.items())),
            "by_symbol": group(lambda x: x.symbol),
            "by_setup": group(lambda x: x.setup),
            "by_regime": group(lambda x: x.regime),
            "by_side": group(lambda x: x.side),
            "fees": round(sum(x.fees for x in t), 4),
            "funding": round(sum(x.funding for x in t), 4),
            "avg_slippage_bps": round(statistics.fmean(
                x.slippage_bps for x in t), 3),
            "downside_deviation": round(dsd, 6),
            "tail_loss_mean": round(statistics.fmean(tail), 6),
            "tail_loss_worst": round(min(pnls), 6),
            "top3_share_of_profit": (round(top3 / total, 4) if total > 0
                                     else None),
            "avg_exposure_pct": (round(100.0 * statistics.fmean(exposure), 3)
                                 if exposure else None),
            "max_exposure_pct": (round(100.0 * max(exposure), 3)
                                 if exposure else None),
            "trades_per_30d": round(30.0 * n / span_d, 2) if span_d > 0 else None,
            "span_days": round(span_d, 1),
            "liquidations": self.liquidations,
            "rejections": dict(sorted(self.rejections.items(),
                                      key=lambda kv: -kv[1])[:15]),
            "start_equity": round(self.start_equity, 2),
            "end_equity": round(self.end_equity, 2),
        }

    # --------------------------------------------------------- monte carlo --
    def monte_carlo(self, runs: int = 500, seed: int = 11) -> dict[str, Any]:
        """Reshuffle TRADE ORDER to estimate the drawdown range.

        What it does and does not say: the trades themselves are held fixed,
        so this measures how much of the observed drawdown was the ORDER they
        happened to arrive in. It cannot tell you the trades will repeat."""
        pnls = [t.pnl for t in self.trades]
        if len(pnls) < 5:
            return {"runs": 0, "note": "too few trades to reshuffle"}
        rng = random.Random(seed)
        dds, finals = [], []
        for _ in range(runs):
            order = pnls[:]
            rng.shuffle(order)
            eq = self.start_equity
            peak, dd = eq, 0.0
            for p in order:
                eq += p
                peak = max(peak, eq)
                dd = max(dd, (peak - eq) / peak if peak > 0 else 0.0)
            dds.append(100.0 * dd)
            finals.append(100.0 * (eq - self.start_equity) / self.start_equity)
        dds.sort()

        def pct(xs, q):
            k = min(len(xs) - 1, max(0, int(round(q / 100.0 * (len(xs) - 1)))))
            return round(xs[k], 4)

        return {"runs": runs,
                "max_drawdown_pct_p50": pct(dds, 50),
                "max_drawdown_pct_p90": pct(dds, 90),
                "max_drawdown_pct_p99": pct(dds, 99),
                "max_drawdown_pct_worst": round(dds[-1], 4),
                "final_return_pct_p05": pct(sorted(finals), 5),
                "final_return_pct_p50": pct(sorted(finals), 50),
                "note": "trade ORDER reshuffled; the trades themselves are "
                        "held fixed, so this bounds path risk, not edge"}


def robustness(result: Result, *, min_trades: int = 30,
               max_dd_pct: float = 25.0, max_symbol_share: float = 0.60,
               max_top3_share: float = 0.80) -> tuple[bool, list[str]]:
    """Spec 11's rejection list, as a gate. A configuration that fails any of
    these is REFUSED however good the headline return looks."""
    m = result.metrics()
    fails: list[str] = []
    n = m.get("trades", 0)
    if n < min_trades:
        fails.append(f"only {n} trades (< {min_trades}): underpowered")
    if (m.get("max_drawdown_pct") or 0.0) > max_dd_pct:
        fails.append(f"max drawdown {m['max_drawdown_pct']:.1f}% exceeds "
                     f"{max_dd_pct:.0f}%")
    total = sum(t.pnl for t in result.trades)
    if total > 0:
        for sym, d in (m.get("by_symbol") or {}).items():
            share = d["pnl"] / total
            if share > max_symbol_share:
                fails.append(f"{sym} carries {share:.0%} of P&L "
                             f"(> {max_symbol_share:.0%}): one-market result")
        t3 = m.get("top3_share_of_profit")
        if t3 is not None and t3 > max_top3_share:
            fails.append(f"top 3 trades are {t3:.0%} of profit "
                         f"(> {max_top3_share:.0%}): tail-dependent")
    half = len(result.trades) // 2
    if half:
        h1 = sum(t.pnl for t in result.trades[:half])
        h2 = sum(t.pnl for t in result.trades[half:])
        if h1 <= 0 or h2 <= 0:
            fails.append(f"halves disagree (h1 {h1:+.2f} / h2 {h2:+.2f}): "
                         "unstable across time")
    gross = sum(t.pnl + t.fees - t.funding for t in result.trades)
    net = total
    if gross > 0 and net <= 0:
        fails.append("profitable before costs and unprofitable after them")
    return (not fails), fails


class Backtester:
    def __init__(self, cfg: AppConfig, markets: dict[str, Market],
                 frictions: Frictions | None = None,
                 start_equity: float | None = None, seed: int = 3):
        self.cfg = cfg
        self.markets = markets
        b = cfg.backtest
        self.fr = frictions or Frictions(
            maker_fee=cfg.execution.maker_fee, taker_fee=cfg.execution.taker_fee,
            spread_bps=b.spread_bps, slippage_bps=b.slippage_bps,
            funding_per_hour=b.funding_per_hour,
            limit_miss_rate=b.limit_miss_rate,
            partial_fill_rate=b.partial_fill_rate,
            partial_fill_fraction=b.partial_fill_fraction,
            reject_rate=b.reject_rate)
        self.start_equity = start_equity or b.start_equity
        self.rng = random.Random(seed)

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _closed_upto(series: Sequence[Candle], tf: str, clock: float,
                     hint: int = 0) -> int:
        """Index of the LAST bar closed at or before `clock`. The monotonic
        hint keeps this O(1) amortised over a full run."""
        sec = tf_seconds(tf)
        i = max(0, hint)
        while i + 1 < len(series) and series[i + 1].ts + sec <= clock:
            i += 1
        if i < len(series) and series[i].ts + sec > clock:
            return -1
        return i

    def _funding(self, side: str, notional: float, hours: float) -> float:
        """Positive `funding_per_hour` means LONGS PAY. A short RECEIVES it --
        which is a real tailwind for this system and is modelled, not assumed
        away."""
        sgn = -1.0 if side == "long" else 1.0
        return sgn * self.fr.funding_per_hour * notional * hours

    def _entry_fill(self, bar: Candle, want: float, side: str,
                    passive: bool) -> tuple[float | None, float]:
        fr = self.fr
        half = want * (fr.spread_bps / 2.0) / 10_000.0
        slip = want * fr.slippage_bps / 10_000.0
        if passive:
            touched = (bar.high >= want) if side == "short" else (bar.low <= want)
            if not touched:
                return None, 0.0
            return want, 0.0        # a maker fill pays no spread or slippage
        px = (want - half - slip) if side == "short" else (want + half + slip)
        return px, (10_000.0 * abs(px - want) / want if want else 0.0)

    def _exit_price(self, bar: Candle, level: float, side: str,
                    kind: str) -> float:
        """STOP GAPS ARE MODELLED. If the bar OPENED beyond the stop, the fill
        is the OPEN -- flattering a gap to the stop price is the single most
        common way a backtest understates tail loss."""
        if kind == "stop":
            gapped = (bar.open >= level) if side == "short" else (bar.open <= level)
            base = bar.open if gapped else level
            slip = base * self.fr.slippage_bps / 10_000.0
            return base + slip if side == "short" else base - slip
        gapped = (bar.open <= level) if side == "short" else (bar.open >= level)
        return bar.open if gapped else level

    # --------------------------------------------------------------- run ---
    def run(self, tapes: dict[str, dict[str, list[Candle]]],
            on_bar: Callable[[float, Book], None] | None = None) -> Result:
        cfg = self.cfg
        tf_x, tf_s, tf_r = (cfg.timeframes.execution, cfg.timeframes.signal,
                            cfg.timeframes.regime)
        bench = cfg.benchmark_symbol
        res = Result(start_equity=self.start_equity)
        book = Book()
        engine = regime_mod.MarketRegimeEngine(cfg.regime)
        # persist=False: a BACKTEST is a simulation and must never mutate the
        # operational state a paper or live run depends on.
        health = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                                       persist=False)
        budget = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
        detector = ChangePointDetector(cfg.changepoint)

        symbols = sorted(tapes)
        clocks = sorted({c.ts + tf_seconds(tf_x)
                         for s in symbols for c in tapes[s].get(tf_x, [])})
        if not clocks:
            return res
        caches = {s: sig_mod.SeriesCache(tapes[s].get(tf_s) or [],
                                         cfg.strategy)
                  for s in symbols}
        hints: dict[tuple[str, str], int] = {}
        equity = self.start_equity
        day_key = week_key = None
        pending: list[dict[str, Any]] = []
        atr_pct_cache: list[float | None] = [None]

        def reject(reason: str) -> None:
            res.rejections[reason] = res.rejections.get(reason, 0) + 1

        for clock in clocks:
            res.bars += 1
            d_key, w_key = int(clock // 86400), int(clock // (7 * 86400))
            if day_key != d_key:
                book.day_pnl, day_key = 0.0, d_key
            if week_key != w_key:
                book.week_pnl, week_key = 0.0, w_key

            idx: dict[tuple[str, str], int] = {}
            for s in symbols:
                for tf in {tf_x, tf_s, tf_r}:
                    k = (s, tf)
                    i = self._closed_upto(tapes[s].get(tf) or [], tf, clock,
                                          hints.get(k, 0))
                    hints[k] = max(0, i)
                    idx[k] = i
            marks = {s: tapes[s][tf_x][idx[(s, tf_x)]].close for s in symbols
                     if idx.get((s, tf_x), -1) >= 0}

            # ---- regime -----------------------------------------------------
            bi_r, bi_s = idx.get((bench, tf_r), -1), idx.get((bench, tf_s), -1)
            btc4 = tapes[bench][tf_r][:bi_r + 1] if bi_r >= 0 and bench in tapes else []
            btc1 = tapes[bench][tf_s][:bi_s + 1] if bi_s >= 0 and bench in tapes else []
            up = tot = 0
            for s in symbols:
                j, ca = idx.get((s, tf_s), -1), caches.get(s)
                if ca is None or j < 25 or j >= ca.n or ca.e20[j] is None:
                    continue
                tot += 1
                up += 1 if ca.c[j] > ca.e20[j] else 0
            breadth20 = (up / tot) if tot >= 2 else None
            if res.bars % 16 == 1 or atr_pct_cache[0] is None:
                atr_pct_cache[0] = regime_mod.atr_percentile_now(btc4)
            inputs = regime_mod.RegimeInputs(
                btc_4h=btc4, btc_1h=btc1, breadth_20=breadth20,
                atr_percentile=atr_pct_cache[0], spread_bps=self.fr.spread_bps,
                data_ok=bool(btc4),
                data_problems=[] if btc4 else ["no benchmark 4h tape"])
            verdict = engine.update(inputs, clock, symbols=symbols,
                                    open_positions=list(book.positions))
            if verdict.transitioned:
                res.regime_transitions.append(engine.transitions[-1].as_dict())
                budget.on_regime_transition()

            detector.observe("volatility", atr_pct_cache[0])
            cp = detector.evaluate(clock)
            if cp.changed and (not res.changepoints
                               or res.changepoints[-1]["severity"] != cp.severity):
                res.changepoints.append({"ts": clock, **cp.as_dict()})

            # ---- fills for orders placed on the PREVIOUS bar ----------------
            still: list[dict[str, Any]] = []
            for order in pending:
                s = order["symbol"]
                i = idx.get((s, tf_x), -1)
                if i < 0 or tapes[s][tf_x][i].ts < order["bar_ts"]:
                    still.append(order)
                    continue
                bar = tapes[s][tf_x][i]
                if self.fr.reject_rate and self.rng.random() < self.fr.reject_rate:
                    reject("exchange rejected the entry order")
                    continue
                px, bps = self._entry_fill(bar, order["price"], order["side"],
                                           order["passive"])
                if px is None:
                    age_s = clock - order["placed_at"]
                    if age_s >= cfg.execution.order_timeout_seconds * 60:
                        reject("entry order expired unfilled")
                        continue
                    still.append(order)
                    continue
                qty = order["qty"]
                if self.fr.partial_fill_rate and \
                        self.rng.random() < self.fr.partial_fill_rate:
                    qty = risk_mod.round_step(
                        qty * self.fr.partial_fill_fraction,
                        self.markets[s].qty_step)
                    if qty <= 0:
                        reject("partial fill rounded to zero")
                        continue
                fee_rate = (self.fr.maker_fee if order["passive"]
                            else self.fr.taker_fee)
                book.positions[s] = Position(
                    symbol=s, side=order["side"], quantity=qty, entry_price=px,
                    opened_ts=clock, stop_price=order["stop"],
                    targets=list(order["targets"]), strategy=order["strategy"],
                    signal_id=order["signal_id"], protective_ok=True,
                    r_unit=abs(px - order["stop"]),
                    meta={"regime": order["regime"], "atr": order["atr"],
                          "setup": order["setup"], "score": order["score"],
                          "entry_fee": qty * px * fee_rate,
                          "slippage_bps": bps, "tp_done": []})
                budget.record_entry(symbol=s, strategy=order["strategy"],
                                    signal_id=order["signal_id"],
                                    setup=order["setup"], score=order["score"],
                                    price=px, now=clock)
            pending = still

            # ---- manage open positions -------------------------------------
            for s in list(book.positions):
                i = idx.get((s, tf_x), -1)
                if i < 0:
                    continue
                bar = tapes[s][tf_x][i]
                pos = book.positions[s]
                if bar.ts + tf_seconds(tf_x) <= pos.opened_ts:
                    continue
                short = pos.side == "short"
                held_h = max(0.0, (clock - pos.opened_ts) / 3600.0)

                exit_px = exit_reason = None
                stop_hit = (bar.high >= pos.stop_price) if short \
                    else (bar.low <= pos.stop_price)
                if stop_hit:
                    exit_px = self._exit_price(bar, pos.stop_price, pos.side,
                                               "stop")
                    exit_reason = "stop"
                else:
                    for k, tp in enumerate(pos.targets):
                        hit = (bar.low <= tp) if short else (bar.high >= tp)
                        if hit and k not in pos.meta.get("tp_done", []):
                            pos.meta.setdefault("tp_done", []).append(k)
                            if k == 0:
                                pos.stop_price = ex.breakeven_stop(
                                    pos, cfg.execution)
                    if pos.targets and \
                            len(pos.meta.get("tp_done", [])) >= len(pos.targets):
                        exit_px = self._exit_price(bar, pos.targets[-1],
                                                   pos.side, "tp")
                        exit_reason = "target"
                    elif ex.should_time_stop(pos, clock,
                                             cfg.strategy.max_holding_days):
                        exit_px, exit_reason = bar.close, "max_hold"
                    elif engine.state in (Regime.PANIC, Regime.DATA_UNRELIABLE):
                        # Protective exits are KEPT; nothing is force-closed
                        # here. This branch only refuses to add.
                        pass
                    else:
                        ca = caches.get(s)
                        j = idx.get((s, tf_s), -1)
                        if ca is not None and 0 <= j < ca.n \
                                and len(pos.meta.get("tp_done", [])) >= 1:
                            pos.stop_price = ex.trail_stop(
                                pos, ca.e20[j], pos.meta.get("atr", 0.0),
                                cfg.strategy.atr_stop_buffer)
                if exit_px is None:
                    continue

                notional = pos.quantity * pos.entry_price
                sgn = -1.0 if short else 1.0
                gross = sgn * (exit_px - pos.entry_price) * pos.quantity
                fees = pos.meta.get("entry_fee", 0.0) \
                    + pos.quantity * exit_px * self.fr.taker_fee
                fund = self._funding(pos.side, notional, held_h)
                pnl = gross - fees + fund
                trade = Trade(
                    symbol=s, side=pos.side, strategy=pos.strategy,
                    setup=str(pos.meta.get("setup", "")),
                    regime=str(pos.meta.get("regime", "")),
                    opened_ts=pos.opened_ts, closed_ts=clock,
                    entry=pos.entry_price, exit=exit_px, quantity=pos.quantity,
                    pnl=pnl, fees=fees, funding=fund,
                    r_multiple=(gross / (pos.r_unit * pos.quantity))
                    if pos.r_unit and pos.quantity else 0.0,
                    reason=exit_reason, signal_id=pos.signal_id,
                    slippage_bps=pos.meta.get("slippage_bps", 0.0),
                    score=float(pos.meta.get("score", 0.0)))
                book.record_close(trade)
                res.trades.append(trade)
                equity += pnl
                del book.positions[s]
                h = health.record(strategy_key(pos.strategy, s, pos.side,
                                               str(pos.meta.get("regime", "")),
                                               tf_s),
                                  trade, reference_equity=self.start_equity)
                if h.state is StrategyState.PAUSED:
                    res.paused_bars += 1
                elif h.state is StrategyState.THROTTLED:
                    res.throttled_bars += 1
                budget.record_exit(symbol=s, signal_id=pos.signal_id, pnl=pnl,
                                   price=exit_px, now=clock)
                detector.observe("expectancy", pnl)
                detector.observe("trade_duration", held_h)

            unreal = book.unrealized(marks)
            res.equity_curve.append((clock, equity + unreal))
            gross_now = book.exposure(marks).gross_notional
            res.exposure_curve.append(
                (clock, gross_now / max(equity + unreal, 1e-9)))
            if on_bar is not None:
                on_bar(clock, book)

            # ---- new entries ------------------------------------------------
            if not verdict.tradable:
                reject(f"regime {engine.state.value}")
                continue
            if cp.severity == "critical":
                reject("change-point detector: critical")
                continue

            account = Account(equity=equity, free_collateral=equity,
                              margin_used=gross_now / max(
                                  cfg.risk.max_leverage, 1e-9),
                              max_leverage=cfg.risk.max_leverage)
            exposure = book.exposure(marks)
            for s in symbols:
                if s in book.positions or any(o["symbol"] == s for o in pending):
                    continue
                i = idx.get((s, tf_s), -1)
                if i < sig_mod.min_bars_for(cfg.strategy):
                    continue
                ri = idx.get((s, tf_r), -1)
                if ri < sig_mod.min_bars_for(cfg.strategy):
                    reject("insufficient 4h regime history")
                    continue
                sym_bear, why = regime_mod.symbol_bearish(
                    tapes[s][tf_r][:ri + 1], cfg.strategy.adx_threshold,
                    cfg.strategy.structure_window, cfg.strategy)
                sides = ["short"] + (["long"] if cfg.allow_longs else [])
                for side in sides:
                    if side == "short" and s == bench \
                            and not engine.btc_short_confirmed():
                        reject("BTC short needs extra regime confirmation")
                        continue
                    mult = regime_mod.risk_multiplier(cfg.regime, engine.state,
                                                      side)
                    if mult <= 0:
                        continue
                    sig, _rej = sig_mod.evaluate(
                        s, tapes[s][tf_s], side, regime=engine.state,
                        cfg=cfg.strategy, symbol_bearish_ok=sym_bear,
                        cache=caches[s], bar=i, timeframe=tf_s,
                        spread_bps=self.fr.spread_bps,
                        atr_percentile=atr_pct_cache[0],
                        max_spread_bps=cfg.execution.max_spread_bps)
                    if sig is None:
                        continue
                    key = strategy_key(sig.strategy, s, side,
                                       engine.state.value, tf_s)
                    health.note_signal(key)
                    hh = health.get(key)
                    if not hh.may_enter:
                        reject(f"strategy {hh.state.value}")
                        continue
                    bump_score = hh.score_bump(cfg.strategy_health) \
                        + cp.score_bump
                    bump_rr = hh.rr_bump(cfg.strategy_health)
                    if engine.state is Regime.NEUTRAL:
                        bump_score += cfg.regime.neutral_score_bump
                        bump_rr += max(0.0,
                                       cfg.regime.neutral_minimum_reward_risk
                                       - cfg.strategy.minimum_reward_risk)
                    ok, why2 = sig_mod.admissible(sig, cfg.strategy,
                                                  engine.state,
                                                  score_bump=bump_score,
                                                  rr_bump=bump_rr)
                    if not ok:
                        reject(why2.split("(")[0].strip())
                        continue
                    ok, why2 = budget.may_enter(
                        symbol=s, strategy=sig.strategy,
                        signal_id=sig.signal_id, setup=sig.setup,
                        score=sig.score.total, price=sig.entry, atr=sig.atr,
                        now=clock, in_regime_transition=verdict.transitioned)
                    if not ok:
                        reject(why2.split(":")[0][:60])
                        continue
                    dec = risk_mod.size_position(
                        signal=sig, market=self.markets[s], account=account,
                        exposure=exposure, risk_cfg=cfg.risk,
                        exec_cfg=cfg.execution, regime_multiplier=mult,
                        health_multiplier=hh.risk_multiplier(
                            cfg.strategy_health)
                        * budget.consecutive_loss_multiplier(clock)
                        * cp.risk_multiplier,
                        spread_bps=self.fr.spread_bps,
                        correlated_group_count=exposure.correlated_counts.get(
                            group_of(s), 0))
                    if not dec.ok:
                        reject(dec.reason.split(":")[0][:60])
                        continue
                    passive = cfg.execution.prefer_limit_orders
                    if passive and self.rng.random() < self.fr.limit_miss_rate:
                        reject("passive limit missed (queue position)")
                        continue
                    pending.append({
                        "symbol": s, "side": side, "price": sig.entry,
                        "stop": sig.stop, "targets": sig.targets,
                        "qty": dec.quantity, "strategy": sig.strategy,
                        "signal_id": sig.signal_id, "atr": sig.atr,
                        "setup": sig.setup, "score": sig.score.total,
                        "regime": engine.state.value, "placed_at": clock,
                        "passive": passive,
                        "bar_ts": tapes[s][tf_x][idx[(s, tf_x)]].ts
                        + tf_seconds(tf_x)})
                    break        # one side per symbol per bar

        res.end_equity = equity + book.unrealized(marks)
        res.health = health.snapshot()
        return res
