"""Per-strategy health state machine and the overtrading budget.

TWO SEPARATE JOBS, deliberately in one module because they share the trade
log and must never disagree about it:

  1. HEALTH -- is this (strategy, symbol, direction, regime) still working?
     ACTIVE -> THROTTLED -> PAUSED, with RECOVERY as the only way back.
  2. OVERTRADING -- even a healthy strategy may not fire without limit.
     Budgets, cooldowns, and a deterministic signal ID that makes the same
     setup on the same closed candle the SAME signal across restarts.

DEGRADATION IS FAST, PROMOTION IS SLOW, and the asymmetry is the design: a
strategy that has stopped working costs money every trade, while one that is
throttled too long costs only opportunity. PAUSED never returns to ACTIVE
directly -- it goes through RECOVERY at 25% risk with the highest bar.

An unknown key starts ACTIVE. That is deliberate: this machine's job is to
detect DECAY in something that was validated, not to be a second gate in
front of an unvalidated strategy. The soak requirement in `config.LiveGate`
is what stops an ungraded strategy reaching live in the first place.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

from .config import HealthConfig, OvertradingConfig
from .logging_setup import get
from .models import HealthState, Trade

log = get("health")


def strategy_key(strategy: str, symbol: str, side: str, regime: str = "*",
                 version: str = "v1") -> str:
    return f"{strategy}|{symbol}|{side}|{regime}|{version}"


@dataclass
class StrategyStats:
    n: int = 0
    wins: int = 0
    gross_win: float = 0.0
    gross_loss: float = 0.0        # positive magnitude
    net: float = 0.0
    fees: float = 0.0
    funding: float = 0.0
    r_sum: float = 0.0
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0
    peak_equity: float = 0.0
    equity: float = 0.0
    max_drawdown: float = 0.0
    slippage_bps_sum: float = 0.0
    durations_h: list[float] = field(default_factory=list)
    #: Account equity when this strategy's FIRST trade was recorded. The
    #: drawdown bars in HealthConfig are fractions OF EQUITY, so without a
    #: reference there is no denominator -- see `_drawdown_frac`.
    reference_equity: float = 0.0

    @property
    def win_rate(self) -> float:
        return 0.0 if not self.n else self.wins / self.n

    @property
    def profit_factor(self) -> float | None:
        """None when there is no loss yet -- an infinite PF from a 3-trade
        sample is not a measurement, and reporting it as a number invites a
        gate to act on it."""
        if self.gross_loss <= 0:
            return None
        return self.gross_win / self.gross_loss

    @property
    def expectancy(self) -> float:
        return 0.0 if not self.n else self.net / self.n

    @property
    def avg_r(self) -> float:
        return 0.0 if not self.n else self.r_sum / self.n

    @property
    def avg_slippage_bps(self) -> float:
        return 0.0 if not self.n else self.slippage_bps_sum / self.n


@dataclass
class StrategyHealth:
    key: str
    state: HealthState = HealthState.ACTIVE
    stats: StrategyStats = field(default_factory=StrategyStats)
    since: float = 0.0
    reason: str = ""
    recovery_trades: int = 0
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def risk_multiplier(self, cfg: HealthConfig) -> float:
        return {HealthState.ACTIVE: 1.0,
                HealthState.THROTTLED: cfg.throttle_risk_multiplier,
                HealthState.RECOVERY: cfg.recovery_risk_multiplier,
                HealthState.PAUSED: 0.0,
                HealthState.DISABLED: 0.0}[self.state]

    def score_bump(self, cfg: HealthConfig) -> float:
        if self.state is HealthState.THROTTLED:
            return cfg.throttle_score_bump
        if self.state is HealthState.RECOVERY:
            return cfg.throttle_score_bump * 2.0
        return 0.0

    def rr_bump(self, cfg: HealthConfig) -> float:
        if self.state is HealthState.THROTTLED:
            return cfg.throttle_rr_bump
        if self.state is HealthState.RECOVERY:
            return cfg.throttle_rr_bump * 2.0
        return 0.0

    @property
    def may_enter(self) -> bool:
        return self.state in (HealthState.ACTIVE, HealthState.THROTTLED,
                              HealthState.RECOVERY)


class HealthRegistry:
    """`persist=False` makes this in-memory.

    THE BUG THAT REQUIRES IT: a backtest constructs a registry against the
    same `state/` directory the paper and live runners use, and every
    `record()` writes. So running a backtest CLOBBERED the live book's
    strategy health -- silently, and in the direction that matters, because a
    replayed losing streak would arrive as a PAUSED live strategy. A backtest
    must never mutate operational state."""

    def __init__(self, cfg: HealthConfig, state_dir: str = "state",
                 persist: bool = True):
        self.cfg = cfg
        self.dir = state_dir
        self.persist = bool(persist)
        self.path = os.path.join(state_dir, "strategy_health.json")
        self.books: dict[str, StrategyHealth] = {}
        if self.persist:
            os.makedirs(state_dir, exist_ok=True)
            self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            raw = json.load(open(self.path))
        except (OSError, ValueError):
            return
        for k, v in (raw or {}).items():
            st = StrategyStats(**(v.get("stats") or {}))
            self.books[k] = StrategyHealth(
                key=k, state=HealthState(v.get("state", "ACTIVE")), stats=st,
                since=float(v.get("since") or 0.0), reason=v.get("reason", ""),
                recovery_trades=int(v.get("recovery_trades") or 0),
                transitions=list(v.get("transitions") or []))

    def save(self) -> None:
        if not self.persist:
            return
        out = {}
        for k, h in self.books.items():
            d = asdict(h)
            d["state"] = h.state.value
            out[k] = d
        tmp = self.path + ".tmp"
        json.dump(out, open(tmp, "w"), indent=1, default=str)
        os.replace(tmp, self.path)

    def get(self, key: str) -> StrategyHealth:
        if key not in self.books:
            self.books[key] = StrategyHealth(key=key, since=time.time())
        return self.books[key]

    # ------------------------------------------------------------ updates --
    def record(self, key: str, trade: Trade,
               reference_equity: float | None = None) -> StrategyHealth:
        """Record one closed trade. `reference_equity` is the account equity
        this strategy is measured against; it is captured ONCE, on the first
        trade, so a growing account cannot quietly loosen the drawdown bar."""
        h = self.get(key)
        s = h.stats
        if s.reference_equity <= 0 and reference_equity and reference_equity > 0:
            s.reference_equity = float(reference_equity)
        s.n += 1
        s.net += trade.pnl
        s.fees += trade.fees
        s.funding += trade.funding
        s.r_sum += trade.r_multiple
        s.slippage_bps_sum += trade.slippage_bps
        s.durations_h.append(trade.held_h)
        if len(s.durations_h) > 500:
            s.durations_h = s.durations_h[-500:]
        if trade.pnl > 0:
            s.wins += 1
            s.gross_win += trade.pnl
            s.consecutive_losses = 0
        else:
            s.gross_loss += abs(trade.pnl)
            s.consecutive_losses += 1
            s.max_consecutive_losses = max(s.max_consecutive_losses,
                                           s.consecutive_losses)
        s.equity += trade.pnl
        s.peak_equity = max(s.peak_equity, s.equity)
        s.max_drawdown = max(s.max_drawdown, s.peak_equity - s.equity)
        if h.state is HealthState.RECOVERY:
            h.recovery_trades += 1
        self._transition(h)
        self.save()
        return h

    def _set(self, h: StrategyHealth, state: HealthState, reason: str) -> None:
        if h.state is state:
            return
        log.info("strategy %s %s -> %s (%s)", h.key, h.state.value,
                 state.value, reason)
        h.transitions.append({"ts": time.time(), "from": h.state.value,
                              "to": state.value, "reason": reason})
        h.state, h.reason, h.since = state, reason, time.time()
        if state is HealthState.RECOVERY:
            h.recovery_trades = 0

    def _drawdown_frac(self, s: StrategyStats) -> float | None:
        """Drawdown as a fraction OF ACCOUNT EQUITY, or None when unknown.

        THE BUG THIS REPLACES, because it would have made the whole machine
        useless: the first version divided by `max(peak_equity, abs(net), 1)`.
        A strategy's `equity` here is CUMULATIVE P&L starting at zero, so
        after a single -$1 trade peak=0, max_drawdown=1 and base=1 -- a
        drawdown of 100%. Every strategy PAUSED on its first losing trade,
        and `test_three_consecutive_losses_throttle` is what caught it.

        None means "not measurable", and the caller SKIPS the drawdown
        condition rather than firing it. Skipping one condition on missing
        data is a real weakening and is declared; firing it on every loss is
        worse, because a machine that pauses everything gets switched off."""
        if s.reference_equity <= 0:
            return None
        return s.max_drawdown / s.reference_equity

    def _transition(self, h: StrategyHealth) -> None:
        cfg, s = self.cfg, h.stats
        if not cfg.enabled or h.state is HealthState.DISABLED:
            return
        pf = s.profit_factor
        dd = self._drawdown_frac(s)

        pause_hits = []
        if s.n >= cfg.hard_pause_trade_count and s.expectancy < cfg.throttle_expectancy:
            pause_hits.append(f"expectancy {s.expectancy:.4f} over {s.n} trades")
        if pf is not None and s.n >= cfg.hard_pause_trade_count \
                and pf < cfg.pause_profit_factor:
            pause_hits.append(f"profit factor {pf:.2f} < {cfg.pause_profit_factor}")
        if s.consecutive_losses >= cfg.max_consecutive_losses + 1:
            pause_hits.append(f"{s.consecutive_losses} consecutive losses")
        if dd is not None and dd >= cfg.hard_drawdown:
            pause_hits.append(f"drawdown {dd:.1%} >= {cfg.hard_drawdown:.1%}")
        if pause_hits:
            self._set(h, HealthState.PAUSED, "; ".join(pause_hits))
            return

        throttle_hits = []
        if s.n >= cfg.warning_trade_count and s.expectancy < cfg.throttle_expectancy:
            throttle_hits.append(f"expectancy {s.expectancy:.4f}")
        if pf is not None and s.n >= cfg.warning_trade_count \
                and pf < cfg.throttle_profit_factor:
            throttle_hits.append(f"profit factor {pf:.2f}")
        if s.consecutive_losses >= 3:
            throttle_hits.append(f"{s.consecutive_losses} consecutive losses")
        if dd is not None and dd >= cfg.warning_drawdown:
            throttle_hits.append(f"drawdown {dd:.1%}")

        if h.state is HealthState.RECOVERY:
            if throttle_hits:
                self._set(h, HealthState.PAUSED,
                          "recovery failed: " + "; ".join(throttle_hits))
            elif h.recovery_trades >= 10 and s.expectancy > 0:
                self._set(h, HealthState.ACTIVE,
                          f"recovery complete: {h.recovery_trades} trades, "
                          f"expectancy {s.expectancy:+.4f}")
            return
        if throttle_hits:
            self._set(h, HealthState.THROTTLED, "; ".join(throttle_hits))
        elif h.state is HealthState.THROTTLED and s.consecutive_losses == 0 \
                and s.expectancy > 0 and (pf is None or pf >= 1.0):
            self._set(h, HealthState.ACTIVE, "recovered within throttle")

    def promote_to_recovery(self, key: str, validation_note: str) -> StrategyHealth:
        """PAUSED -> RECOVERY. Explicit, and it records WHAT validated it --
        an automatic promotion on elapsed time is how a broken strategy comes
        back untested."""
        h = self.get(key)
        if h.state is not HealthState.PAUSED:
            return h
        self._set(h, HealthState.RECOVERY, f"validated: {validation_note}")
        self.save()
        return h

    def snapshot(self) -> dict[str, Any]:
        return {k: {"state": h.state.value, "n": h.stats.n,
                    "expectancy": round(h.stats.expectancy, 6),
                    "profit_factor": (None if h.stats.profit_factor is None
                                      else round(h.stats.profit_factor, 3)),
                    "consecutive_losses": h.stats.consecutive_losses,
                    "reason": h.reason}
                for k, h in sorted(self.books.items())}


# --------------------------------------------------------- overtrading ------
@dataclass
class EntryRecord:
    ts: float
    symbol: str
    strategy: str
    signal_id: str
    outcome: str = "open"       # open | win | loss | breakeven
    score: float = 0.0


class TradeBudget:
    """Entry budgets, cooldowns and duplicate-signal refusal.

    The cooldown is keyed on the SYMBOL, not the strategy: after a loss on a
    market, the market is the thing that just proved hostile, and letting a
    second strategy re-enter it immediately is the loophole this closes."""

    def __init__(self, cfg: OvertradingConfig, state_dir: str = "state",
                 persist: bool = True):
        self.cfg = cfg
        self.persist = bool(persist)
        self.path = os.path.join(state_dir, "trade_budget.json")
        self.entries: list[EntryRecord] = []
        self.seen_signal_ids: set[str] = set()
        self.cooldown_until: dict[str, float] = {}
        self.global_lockout_until: float = 0.0
        if self.persist:
            os.makedirs(state_dir, exist_ok=True)
            self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            raw = json.load(open(self.path))
        except (OSError, ValueError):
            return
        self.entries = [EntryRecord(**e) for e in raw.get("entries", [])]
        self.seen_signal_ids = set(raw.get("seen_signal_ids") or [])
        self.cooldown_until = dict(raw.get("cooldown_until") or {})
        self.global_lockout_until = float(raw.get("global_lockout_until") or 0.0)

    def save(self, now: float | None = None) -> None:
        """Prune against the LATEST timestamp seen, not the wall clock.

        THE BUG THIS REPLACES: pruning at `time.time() - 14d` silently deleted
        every entry in a BACKTEST, because historical timestamps are years
        below the wall clock. The budgets therefore did nothing at all in the
        one place they most need to bind -- a backtest would report a trade
        rate the live system could never take, and nothing would have said so.
        `test_per_market_daily_budget` caught it."""
        ref = now if now is not None else max(
            (e.ts for e in self.entries), default=time.time())
        cut = ref - 14 * 86400
        self.entries = [e for e in self.entries if e.ts >= cut]
        if not self.persist:
            return
        if len(self.seen_signal_ids) > 20000:
            self.seen_signal_ids = set(list(self.seen_signal_ids)[-10000:])
        tmp = self.path + ".tmp"
        json.dump({"entries": [asdict(e) for e in self.entries],
                   "seen_signal_ids": sorted(self.seen_signal_ids),
                   "cooldown_until": self.cooldown_until,
                   "global_lockout_until": self.global_lockout_until},
                  open(tmp, "w"), indent=1)
        os.replace(tmp, self.path)

    def _since(self, seconds: float, now: float,
               pred=lambda e: True) -> Iterable[EntryRecord]:
        return [e for e in self.entries if e.ts >= now - seconds and pred(e)]

    def may_enter(self, *, symbol: str, strategy: str, signal_id: str,
                  now: float | None = None) -> tuple[bool, str]:
        now = time.time() if now is None else now
        if now < self.global_lockout_until:
            return False, (f"global loss lockout until "
                           f"{self.global_lockout_until:.0f}")
        if signal_id in self.seen_signal_ids:
            return False, f"duplicate signal id {signal_id}"
        until = self.cooldown_until.get(symbol, 0.0)
        if now < until:
            return False, f"{symbol} in cooldown for {(until - now) / 3600:.1f}h"
        c = self.cfg
        if len(self._since(86400, now, lambda e: e.symbol == symbol)) \
                >= c.max_entries_per_market_per_day:
            return False, (f"{symbol} at {c.max_entries_per_market_per_day} "
                           "entries today")
        if len(self._since(86400, now, lambda e: e.strategy == strategy)) \
                >= c.max_entries_per_strategy_per_day:
            return False, (f"{strategy} at {c.max_entries_per_strategy_per_day}"
                           " entries today")
        if len(self._since(3600, now)) >= c.max_portfolio_entries_per_hour:
            return False, (f"portfolio at {c.max_portfolio_entries_per_hour} "
                           "entries this hour")
        return True, "within budget"

    def record_entry(self, *, symbol: str, strategy: str, signal_id: str,
                     score: float = 0.0, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.entries.append(EntryRecord(now, symbol, strategy, signal_id,
                                        score=score))
        self.seen_signal_ids.add(signal_id)
        self.save(now)

    def record_exit(self, *, symbol: str, signal_id: str, pnl: float,
                    now: float | None = None) -> None:
        now = time.time() if now is None else now
        c = self.cfg
        if pnl > 0:
            hours, outcome = c.cooldown_after_profit_hours, "win"
        elif pnl < 0:
            hours, outcome = c.cooldown_after_loss_hours, "loss"
        else:
            hours, outcome = c.cooldown_after_breakeven_hours, "breakeven"
        self.cooldown_until[symbol] = now + hours * 3600.0
        for e in self.entries:
            if e.signal_id == signal_id:
                e.outcome = outcome
        recent = [e for e in self.entries if e.ts >= now - 86400
                  and e.outcome == "loss"]
        if len(recent) >= 4:
            # Four losses in a day is the portfolio talking, not one strategy.
            self.global_lockout_until = now + c.cooldown_after_loss_hours * 3600.0
            log.warning("global loss lockout armed: %d losses in 24h",
                        len(recent))
        self.save(now)

    def consecutive_loss_multiplier(self, now: float | None = None) -> float:
        """After 2 consecutive portfolio losses, cut risk 25%."""
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
