"""Open-book accounting, correlation groups, and the OVERTRADING controls.

The overtrading half (spec 26) lives here rather than in `risk.py` because it
shares the trade log with exposure and the two must never disagree about it.

TWO DESIGN CHOICES WORTH NAMING:

* **Cooldowns are keyed on the SYMBOL, not the strategy.** After a stop-out
  the MARKET is what just proved hostile; letting a second strategy re-enter
  it immediately is the loophole this closes.
* **Pruning is keyed on the LATEST TIMESTAMP SEEN, not the wall clock.** A
  backtest replays historical timestamps; pruning at `time.time() - 14d` would
  delete every entry the moment it was written and silently disable every
  budget in the one place they most need to bind.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Sequence

from .config import OvertradingConfig
from .logging_setup import get
from .models import Position, Trade, contained_path
from .risk import Exposure

log = get("portfolio")

#: Coarse correlation groups used when a measured matrix is unavailable.
#: Crude on purpose, and used ONLY to size down.
DEFAULT_GROUPS = {
    "BTC": "majors", "ETH": "majors", "SOL": "majors", "BNB": "majors",
    "XRP": "majors", "DOGE": "alt", "ADA": "alt", "AVAX": "alt",
}


def base_of(symbol: str) -> str:
    return symbol.split("/")[0].strip().upper()


def group_of(symbol: str) -> str:
    return DEFAULT_GROUPS.get(base_of(symbol), "alt")


def returns(closes: Sequence[float]) -> list[float]:
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            out.append(closes[i] / closes[i - 1] - 1.0)
    return out


def correlation(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = list(a[-n:]), list(b[-n:])
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def effective_bets(symbols: Sequence[str],
                   closes_by_symbol: dict[str, Sequence[float]]) -> float:
    """N / (1 + (N-1)*mean rho), floored at 1.0.

    An UNMEASURABLE pair contributes rho = 1.0, so a dark price feed can only
    ever REDUCE the claimed diversification. Reporting a symbol count as
    diversification is the specific error this refuses to make."""
    syms = list(dict.fromkeys(symbols))
    n = len(syms)
    if n <= 1:
        return float(n)
    rets = {s: returns(closes_by_symbol.get(s) or []) for s in syms}
    rhos = []
    for i in range(n):
        for j in range(i + 1, n):
            r = correlation(rets.get(syms[i]) or [], rets.get(syms[j]) or [])
            rhos.append(1.0 if r is None else max(-0.99, min(1.0, r)))
    mean_rho = sum(rhos) / len(rhos)
    denom = 1.0 + (n - 1) * mean_rho
    return float(n) if denom <= 0 else max(1.0, n / denom)


@dataclass
class Book:
    positions: dict[str, Position] = field(default_factory=dict)
    closed: list[Trade] = field(default_factory=list)
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    realized: float = 0.0
    consecutive_losses: int = 0

    def open_risk(self) -> float:
        return sum(abs(p.entry_price - p.stop_price) * p.quantity
                   for p in self.positions.values())

    def exposure(self, marks: dict[str, float] | None = None) -> Exposure:
        marks = marks or {}
        gross = short_n = long_n = 0.0
        per_symbol: dict[str, float] = {}
        groups: dict[str, int] = {}
        for sym, p in self.positions.items():
            px = marks.get(sym, p.entry_price)
            notional = abs(p.quantity) * px
            gross += notional
            per_symbol[sym] = per_symbol.get(sym, 0.0) + notional
            if p.side == "short":
                short_n += notional
            else:
                long_n += notional
            g = group_of(sym)
            groups[g] = groups.get(g, 0) + 1
        return Exposure(
            open_positions=len(self.positions), open_risk=self.open_risk(),
            gross_notional=gross, short_notional=short_n,
            long_notional=long_n, per_symbol_notional=per_symbol,
            correlated_counts=groups, day_pnl=self.day_pnl,
            week_pnl=self.week_pnl,
            consecutive_losses=self.consecutive_losses)

    def unrealized(self, marks: dict[str, float]) -> float:
        return sum(p.unrealized(marks.get(s, p.entry_price))
                   for s, p in self.positions.items())

    def record_close(self, trade: Trade) -> None:
        self.closed.append(trade)
        self.realized += trade.pnl
        self.day_pnl += trade.pnl
        self.week_pnl += trade.pnl
        self.consecutive_losses = (self.consecutive_losses + 1
                                   if trade.pnl <= 0 else 0)

    def summary(self, marks: dict[str, float] | None = None) -> dict[str, Any]:
        marks = marks or {}
        e = self.exposure(marks)
        return {"open": len(self.positions), "closed": len(self.closed),
                "realized": round(self.realized, 4),
                "unrealized": round(self.unrealized(marks), 4),
                "gross_notional": round(e.gross_notional, 2),
                "short_notional": round(e.short_notional, 2),
                "long_notional": round(e.long_notional, 2),
                "open_risk": round(e.open_risk, 4),
                "day_pnl": round(self.day_pnl, 4),
                "week_pnl": round(self.week_pnl, 4),
                "consecutive_losses": self.consecutive_losses,
                "held": {s: ("S" if p.side == "short" else "L")
                         for s, p in self.positions.items()}}


# ------------------------------------------------------------ overtrading ---
@dataclass
class EntryRecord:
    ts: float
    symbol: str
    strategy: str
    signal_id: str
    setup: str = ""
    score: float = 0.0
    price: float = 0.0
    outcome: str = "open"          # open | win | loss | breakeven


class TradeBudget:
    """Signal dedup, cooldowns, churn prevention and trade budgets.

    `persist=False` makes this in-memory: a BACKTEST must never mutate the
    operational state a paper or live run depends on."""

    def __init__(self, cfg: OvertradingConfig, runtime_dir: str = "runtime",
                 persist: bool = True):
        self.cfg = cfg
        self.persist = bool(persist)
        self.path = (contained_path(runtime_dir, "trade_budget.json")
                     if persist else "")
        self.entries: list[EntryRecord] = []
        self.seen_signal_ids: set[str] = set()
        self.cooldown_until: dict[str, float] = {}
        self.last_exit: dict[str, dict[str, float]] = {}
        self.global_lockout_until: float = 0.0
        self.regime_transition_entries: int = 0
        if persist:
            os.makedirs(runtime_dir, exist_ok=True)
            self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return
        self.entries = [EntryRecord(**e) for e in raw.get("entries", [])]
        self.seen_signal_ids = set(raw.get("seen_signal_ids") or [])
        self.cooldown_until = dict(raw.get("cooldown_until") or {})
        self.last_exit = dict(raw.get("last_exit") or {})
        self.global_lockout_until = float(raw.get("global_lockout_until") or 0.0)

    def save(self, now: float | None = None) -> None:
        ref = now if now is not None else max(
            (e.ts for e in self.entries), default=time.time())
        cut = ref - 30 * 86400
        self.entries = [e for e in self.entries if e.ts >= cut]
        if len(self.seen_signal_ids) > 50_000:
            self.seen_signal_ids = set(list(self.seen_signal_ids)[-25_000:])
        if not self.persist:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"entries": [asdict(e) for e in self.entries],
                       "seen_signal_ids": sorted(self.seen_signal_ids),
                       "cooldown_until": self.cooldown_until,
                       "last_exit": self.last_exit,
                       "global_lockout_until": self.global_lockout_until},
                      fh, indent=1)
        os.replace(tmp, self.path)

    def _since(self, seconds: float, now: float,
               pred=lambda e: True) -> Iterable[EntryRecord]:
        return [e for e in self.entries if e.ts >= now - seconds and pred(e)]

    def may_enter(self, *, symbol: str, strategy: str, signal_id: str,
                  setup: str = "", score: float = 0.0, price: float = 0.0,
                  atr: float = 0.0, now: float | None = None,
                  in_regime_transition: bool = False) -> tuple[bool, str]:
        now = time.time() if now is None else now
        c = self.cfg

        if now < self.global_lockout_until:
            return False, "global loss lockout is active"
        if signal_id in self.seen_signal_ids:
            return False, f"duplicate signal id {signal_id}"

        until = self.cooldown_until.get(symbol, 0.0)
        if now < until:
            return False, (f"{symbol} in cooldown for "
                           f"{(until - now) / 3600.0:.1f}h")

        # ---- churn guard (spec 26C): time OR price displacement -----------
        last = self.last_exit.get(symbol)
        if last and c.require_fresh_setup_for_reentry:
            hours = (now - last.get("ts", 0.0)) / 3600.0
            moved = (abs(price - last.get("price", price)) / atr) if atr > 0 \
                else float("inf")
            if hours < c.reentry_min_hours and moved < c.reentry_min_atr_displacement:
                return False, (f"{symbol} re-entry too soon: {hours:.1f}h and "
                               f"{moved:.2f} ATR since the last exit")

        # ---- minimum signal separation (spec 26G) -------------------------
        if setup and c.minimum_signal_score_separation > 0:
            same = [e for e in self._since(86400, now,
                                           lambda e: e.symbol == symbol
                                           and e.setup == setup)]
            if len(same) >= c.maximum_same_setup_entries:
                best = max((e.score for e in same), default=0.0)
                if score < best + c.minimum_signal_score_separation:
                    return False, (f"{symbol}/{setup} already taken today at "
                                   f"score {best:.1f}; {score:.1f} does not "
                                   f"clear it by "
                                   f"{c.minimum_signal_score_separation:.0f}")

        if len(list(self._since(86400, now, lambda e: e.symbol == symbol))) \
                >= c.max_entries_per_symbol_per_day:
            return False, (f"{symbol} at "
                           f"{c.max_entries_per_symbol_per_day} entries today")
        if len(list(self._since(86400, now, lambda e: e.strategy == strategy))) \
                >= c.max_entries_per_strategy_per_day:
            return False, (f"{strategy} at "
                           f"{c.max_entries_per_strategy_per_day} entries today")
        if len(list(self._since(3600, now))) >= c.max_portfolio_entries_per_hour:
            return False, (f"portfolio at {c.max_portfolio_entries_per_hour} "
                           "entries this hour")
        if in_regime_transition and self.regime_transition_entries \
                >= c.max_entries_during_regime_transition:
            return False, ("regime transition entry budget spent "
                           f"({c.max_entries_during_regime_transition})")
        return True, "within budget"

    def record_entry(self, *, symbol: str, strategy: str, signal_id: str,
                     setup: str = "", score: float = 0.0, price: float = 0.0,
                     now: float | None = None,
                     in_regime_transition: bool = False) -> None:
        now = time.time() if now is None else now
        self.entries.append(EntryRecord(now, symbol, strategy, signal_id,
                                        setup=setup, score=score, price=price))
        self.seen_signal_ids.add(signal_id)
        if in_regime_transition:
            self.regime_transition_entries += 1
        self.save(now)

    def record_exit(self, *, symbol: str, signal_id: str, pnl: float,
                    price: float = 0.0, now: float | None = None) -> None:
        now = time.time() if now is None else now
        c = self.cfg
        if pnl > 0:
            hours, outcome = c.cooldown_after_profit_hours, "win"
        elif pnl < 0:
            hours, outcome = c.cooldown_after_loss_hours, "loss"
        else:
            hours, outcome = c.cooldown_after_loss_hours / 2.0, "breakeven"
        self.cooldown_until[symbol] = now + hours * 3600.0
        self.last_exit[symbol] = {"ts": now, "price": price, "pnl": pnl}
        matched = False
        for e in self.entries:
            if e.signal_id == signal_id:
                e.outcome = outcome
                matched = True
        if not matched:
            # An exit whose ENTRY we have no record of still happened, and a
            # loss the budget cannot see is a loss the portfolio lockout cannot
            # count. This is the restart case: the process came back after the
            # position opened, so the entry list starts empty and the very
            # trades most likely to be going wrong would be invisible.
            self.entries.append(EntryRecord(
                now, symbol, "unknown", signal_id, price=price,
                outcome=outcome))
        losses = [e for e in self.entries
                  if e.ts >= now - 86400 and e.outcome == "loss"]
        if len(losses) >= 4:
            # Four losses in a day is the PORTFOLIO talking, not one strategy.
            self.global_lockout_until = now + c.cooldown_after_loss_hours * 3600.0
            log.warning("global loss lockout armed: %d losses in 24h",
                        len(losses))
        self.save(now)

    def on_regime_transition(self) -> None:
        self.regime_transition_entries = 0

    def consecutive_loss_multiplier(self, now: float | None = None) -> float:
        """Spec 26E: after 2 consecutive losses, cut risk 25%."""
        now = time.time() if now is None else now
        closed = [e for e in sorted(self.entries, key=lambda e: e.ts)
                  if e.outcome in ("win", "loss", "breakeven")]
        streak = 0
        for e in reversed(closed):
            if e.outcome == "loss":
                streak += 1
            else:
                break
        return 0.75 if streak >= 2 else 1.0

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        return {"entries_1h": len(list(self._since(3600, now))),
                "entries_24h": len(list(self._since(86400, now))),
                "cooldowns": sum(1 for t in self.cooldown_until.values()
                                 if t > now),
                "global_lockout": now < self.global_lockout_until,
                "signal_ids_seen": len(self.seen_signal_ids)}
