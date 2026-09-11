"""Two kinds of health, deliberately in one module because they share a log.

* **StrategyHealthMonitor** (spec 23-25): is this strategy still working?
  ACTIVE -> THROTTLED -> PAUSED, with RECOVERY the only way back.
* **System health** (spec 16): is the plumbing trustworthy RIGHT NOW?

DEGRADATION IS FAST, PROMOTION IS SLOW, and the asymmetry is the design: a
strategy that has stopped working costs money every trade, while one that is
throttled too long costs only opportunity.

TWO THINGS THAT ARE NOT ALLOWED, and both are enforced rather than advised:
  * PAUSED never returns straight to ACTIVE. It goes through RECOVERY at 25%
    risk with the highest bar and an explicit, recorded validation. **Time
    alone never promotes** -- `promote_to_recovery` REFUSES without a paper
    validation record.
  * Drawdown is measured against a REFERENCE EQUITY captured once. Measuring
    it against the strategy's own cumulative P&L (which starts at zero) makes
    a single losing trade read as a 100% drawdown and pauses everything.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Sequence

from .config import StrategyHealthConfig
from .logging_setup import get
from .models import Candle, Regime, StrategyState, Trade, contained_path

log = get("health")

#: Rolling windows the monitor reports on (spec 23).
WINDOWS = (10, 20, 50)


def strategy_key(strategy: str, symbol: str, side: str, regime: str = "*",
                 timeframe: str = "*", version: str = "v1") -> str:
    return f"{strategy}|{symbol}|{side}|{regime}|{timeframe}|{version}"


@dataclass
class Stats:
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
    duration_h_sum: float = 0.0
    signals_seen: int = 0
    #: Account equity when the FIRST trade landed. The drawdown bars are
    #: fractions OF EQUITY, so without this there is no denominator.
    reference_equity: float = 0.0
    recent_r: list[float] = field(default_factory=list)
    recent_pnl: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return 0.0 if not self.n else self.wins / self.n

    @property
    def profit_factor(self) -> float | None:
        """None when there is no loss yet. An infinite PF from a 3-trade
        sample is not a measurement, and reporting it as a number invites a
        gate to act on it."""
        return None if self.gross_loss <= 0 else self.gross_win / self.gross_loss

    @property
    def expectancy(self) -> float:
        return 0.0 if not self.n else self.net / self.n

    @property
    def avg_r(self) -> float:
        return 0.0 if not self.n else self.r_sum / self.n

    @property
    def avg_slippage_bps(self) -> float:
        return 0.0 if not self.n else self.slippage_bps_sum / self.n

    @property
    def avg_duration_h(self) -> float:
        return 0.0 if not self.n else self.duration_h_sum / self.n

    @property
    def signal_conversion(self) -> float | None:
        return None if not self.signals_seen else self.n / self.signals_seen

    def rolling(self, k: int) -> dict[str, Any]:
        xs = self.recent_pnl[-k:]
        if not xs:
            return {"n": 0}
        wins = [x for x in xs if x > 0]
        losses = [abs(x) for x in xs if x <= 0]
        pf = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else None
        return {"n": len(xs), "expectancy": round(statistics.fmean(xs), 6),
                "profit_factor": None if pf is None else round(pf, 4),
                "win_rate": round(len(wins) / len(xs), 4)}

    def top_trade_share(self, k: int = 3) -> float | None:
        """What fraction of profit came from the k best trades. A number near
        1.0 means the record is a tail, not an edge."""
        if self.net <= 0 or len(self.recent_pnl) < k + 2:
            return None
        top = sum(sorted(self.recent_pnl, reverse=True)[:k])
        return top / self.net


@dataclass
class StrategyHealth:
    key: str
    state: StrategyState = StrategyState.ACTIVE
    stats: Stats = field(default_factory=Stats)
    since: float = 0.0
    reason: str = ""
    recovery_trades: int = 0
    paper_validated: bool = False
    paper_validation_note: str = ""
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def risk_multiplier(self, cfg: StrategyHealthConfig) -> float:
        return {StrategyState.ACTIVE: 1.0,
                StrategyState.THROTTLED: cfg.throttle_risk_multiplier,
                StrategyState.RECOVERY: cfg.recovery_risk_multiplier,
                StrategyState.PAUSED: 0.0,
                StrategyState.DISABLED: 0.0}[self.state]

    def score_bump(self, cfg: StrategyHealthConfig) -> float:
        if self.state is StrategyState.THROTTLED:
            return cfg.throttle_score_bump
        if self.state is StrategyState.RECOVERY:
            return cfg.throttle_score_bump * 2.0
        return 0.0

    def rr_bump(self, cfg: StrategyHealthConfig) -> float:
        if self.state is StrategyState.THROTTLED:
            return cfg.throttle_rr_bump
        if self.state is StrategyState.RECOVERY:
            return cfg.throttle_rr_bump * 2.0
        return 0.0

    def max_positions(self, base: int) -> int:
        if self.state is StrategyState.RECOVERY:
            return 1
        if self.state is StrategyState.THROTTLED:
            return max(1, base // 2)
        return base

    @property
    def may_enter(self) -> bool:
        return self.state in (StrategyState.ACTIVE, StrategyState.THROTTLED,
                              StrategyState.RECOVERY)


class StrategyHealthMonitor:
    def __init__(self, cfg: StrategyHealthConfig, runtime_dir: str = "runtime",
                 persist: bool = True):
        self.cfg = cfg
        self.persist = bool(persist)
        self.path = (contained_path(runtime_dir, "strategy_health.json")
                     if persist else "")
        self.books: dict[str, StrategyHealth] = {}
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
        for k, v in (raw or {}).items():
            try:
                st = Stats(**(v.get("stats") or {}))
                self.books[k] = StrategyHealth(
                    key=k, state=StrategyState(v.get("state", "ACTIVE")),
                    stats=st, since=float(v.get("since") or 0.0),
                    reason=v.get("reason", ""),
                    recovery_trades=int(v.get("recovery_trades") or 0),
                    paper_validated=bool(v.get("paper_validated")),
                    paper_validation_note=v.get("paper_validation_note", ""),
                    transitions=list(v.get("transitions") or []))
            except (TypeError, ValueError):
                continue

    def save(self) -> None:
        if not self.persist:
            return
        out = {}
        for k, h in self.books.items():
            d = asdict(h)
            d["state"] = h.state.value
            out[k] = d
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        os.replace(tmp, self.path)

    def get(self, key: str) -> StrategyHealth:
        if key not in self.books:
            self.books[key] = StrategyHealth(key=key, since=time.time())
        return self.books[key]

    def note_signal(self, key: str) -> None:
        self.get(key).stats.signals_seen += 1

    def record(self, key: str, trade: Trade,
               reference_equity: float | None = None) -> StrategyHealth:
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
        s.duration_h_sum += trade.held_h
        s.recent_pnl.append(trade.pnl)
        s.recent_r.append(trade.r_multiple)
        if len(s.recent_pnl) > 500:
            s.recent_pnl = s.recent_pnl[-500:]
            s.recent_r = s.recent_r[-500:]
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
        if h.state is StrategyState.RECOVERY:
            h.recovery_trades += 1
        self._transition(h)
        self.save()
        return h

    def drawdown_frac(self, s: Stats) -> float | None:
        """Fraction OF ACCOUNT EQUITY, or None when unknown.

        None means NOT MEASURABLE and the caller SKIPS the drawdown condition
        rather than firing it. Skipping one condition on missing data is a
        real weakening and is declared; firing it on every loss is worse,
        because a monitor that pauses everything gets switched off."""
        if s.reference_equity <= 0:
            return None
        return s.max_drawdown / s.reference_equity

    def _set(self, h: StrategyHealth, state: StrategyState,
             reason: str) -> None:
        if h.state is state:
            return
        log.info("strategy %s %s -> %s (%s)", h.key, h.state.value,
                 state.value, reason)
        h.transitions.append({"ts": time.time(), "from": h.state.value,
                              "to": state.value, "reason": reason})
        h.state, h.reason, h.since = state, reason, time.time()
        if state is StrategyState.RECOVERY:
            h.recovery_trades = 0
        if state is StrategyState.PAUSED:
            h.paper_validated = False        # must be re-earned

    def _transition(self, h: StrategyHealth) -> None:
        cfg, s = self.cfg, h.stats
        if not cfg.enabled or h.state is StrategyState.DISABLED:
            return
        r20 = s.rolling(20)
        r30 = s.rolling(50)
        dd = self.drawdown_frac(s)

        pause = []
        if s.n >= cfg.hard_pause_trade_count and r30.get("n", 0) >= 20 \
                and r30.get("expectancy", 0.0) < 0:
            pause.append(f"rolling expectancy {r30['expectancy']:.5f} over "
                         f"{r30['n']} trades")
        pf20 = r20.get("profit_factor")
        if pf20 is not None and r20.get("n", 0) >= cfg.warning_trade_count \
                and pf20 < cfg.pause_profit_factor:
            pause.append(f"rolling-20 profit factor {pf20:.2f} < "
                         f"{cfg.pause_profit_factor}")
        if s.consecutive_losses >= cfg.max_consecutive_losses + 1:
            pause.append(f"{s.consecutive_losses} consecutive losses")
        if dd is not None and dd >= cfg.hard_drawdown:
            pause.append(f"drawdown {dd:.1%} >= {cfg.hard_drawdown:.1%}")
        if pause:
            self._set(h, StrategyState.PAUSED, "; ".join(pause))
            return

        throttle = []
        if r20.get("n", 0) >= cfg.warning_trade_count \
                and r20.get("expectancy", 0.0) < cfg.throttle_expectancy:
            throttle.append(f"rolling-20 expectancy {r20['expectancy']:.5f}")
        if pf20 is not None and r20.get("n", 0) >= cfg.warning_trade_count \
                and pf20 < cfg.throttle_profit_factor:
            throttle.append(f"rolling-20 profit factor {pf20:.2f}")
        if s.consecutive_losses >= 3:
            throttle.append(f"{s.consecutive_losses} consecutive losses")
        if dd is not None and dd >= cfg.warning_drawdown:
            throttle.append(f"drawdown {dd:.1%}")

        if h.state is StrategyState.RECOVERY:
            if throttle:
                self._set(h, StrategyState.PAUSED,
                          "recovery failed: " + "; ".join(throttle))
            elif h.recovery_trades >= cfg.recovery_min_trades \
                    and s.expectancy > 0:
                self._set(h, StrategyState.ACTIVE,
                          f"recovery complete: {h.recovery_trades} trades, "
                          f"expectancy {s.expectancy:+.5f}")
            return
        if throttle:
            self._set(h, StrategyState.THROTTLED, "; ".join(throttle))
        elif h.state is StrategyState.THROTTLED and s.consecutive_losses == 0 \
                and r20.get("expectancy", 0.0) > 0 \
                and (pf20 is None or pf20 >= 1.0):
            self._set(h, StrategyState.ACTIVE, "recovered within throttle")

    def record_paper_validation(self, key: str, *, signals: int,
                                expectancy: float, max_drawdown: float,
                                note: str) -> tuple[bool, str]:
        """Spec 25's preconditions, checked rather than trusted."""
        cfg = self.cfg
        h = self.get(key)
        fails = []
        if signals < cfg.recovery_min_paper_signals:
            fails.append(f"only {signals} paper signals, need "
                         f"{cfg.recovery_min_paper_signals}")
        if expectancy < 0:
            fails.append(f"paper expectancy {expectancy:+.5f} is negative")
        if max_drawdown > cfg.hard_drawdown:
            fails.append(f"paper drawdown {max_drawdown:.1%} exceeds "
                         f"{cfg.hard_drawdown:.1%}")
        if fails:
            return False, "; ".join(fails)
        h.paper_validated = True
        h.paper_validation_note = note
        self.save()
        return True, "paper validation recorded"

    def promote_to_recovery(self, key: str) -> tuple[bool, str]:
        """PAUSED -> RECOVERY. REFUSES without a recorded paper validation --
        'time has passed' is never a reason (spec 25)."""
        h = self.get(key)
        if h.state is not StrategyState.PAUSED:
            return False, f"{key} is {h.state.value}, not PAUSED"
        if not h.paper_validated:
            return False, ("no paper validation on record: run the strategy in "
                           "paper/shadow and call record_paper_validation first")
        self._set(h, StrategyState.RECOVERY,
                  f"validated: {h.paper_validation_note}")
        self.save()
        return True, "promoted to RECOVERY at reduced risk"

    def snapshot(self) -> dict[str, Any]:
        out = {}
        for k, h in sorted(self.books.items()):
            s = h.stats
            out[k] = {"state": h.state.value, "n": s.n,
                      "expectancy": round(s.expectancy, 6),
                      "profit_factor": (None if s.profit_factor is None
                                        else round(s.profit_factor, 3)),
                      "avg_r": round(s.avg_r, 4),
                      "win_rate": round(s.win_rate, 4),
                      "consecutive_losses": s.consecutive_losses,
                      "drawdown": (None if self.drawdown_frac(s) is None
                                   else round(self.drawdown_frac(s), 4)),
                      "avg_slippage_bps": round(s.avg_slippage_bps, 2),
                      "signal_conversion": (None if s.signal_conversion is None
                                            else round(s.signal_conversion, 3)),
                      "top3_share": s.top_trade_share(3),
                      "rolling": {str(w): s.rolling(w) for w in WINDOWS},
                      "reason": h.reason}
        return out


# ------------------------------------------------------------ system health -
@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SystemHealth:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, bool(ok), detail))

    def failures(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.ok]

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok,
                "checks": {c.name: {"ok": c.ok, "detail": c.detail}
                           for c in self.checks},
                "failures": self.failures()}

    def render(self) -> str:
        w = max((len(c.name) for c in self.checks), default=10)
        lines = [f"  [{'ok ' if c.ok else 'FAIL'}] {c.name:<{w}}  {c.detail}"
                 for c in self.checks]
        return "\n".join([f"SYSTEM HEALTH: {'OK' if self.ok else 'NOT HEALTHY'}"]
                         + lines)


def kill_switch_path(runtime_dir: str) -> str:
    return os.path.join(runtime_dir, "KILL_SWITCH")


def kill_switch_active(runtime_dir: str) -> bool:
    return os.path.exists(kill_switch_path(runtime_dir))


def check_system(*, runtime_dir: str, candles: dict[str, Sequence[Candle]],
                 timeframe_seconds: int, now: float,
                 exchange_ok: bool = True, reconciled: bool = True,
                 regime: Regime | None = None,
                 stale_tolerance_bars: float = 2.0) -> SystemHealth:
    h = SystemHealth()
    killed = kill_switch_active(runtime_dir)
    h.add("kill_switch_absent", not killed,
          "KILL_SWITCH present -- entries halted" if killed
          else "no kill switch")
    stale = {}
    for sym, cs in candles.items():
        if not cs:
            stale[sym] = "no bars"
            continue
        age = now - (cs[-1].ts + timeframe_seconds)
        if age > stale_tolerance_bars * timeframe_seconds:
            stale[sym] = f"{age / 60.0:.0f}m"
    h.add("candles_fresh", not stale,
          "all series current" if not stale else f"stale: {stale}")
    h.add("candles_present", bool(candles),
          f"{len(candles)} series" if candles else "no candle series at all")
    h.add("exchange_ok", bool(exchange_ok),
          "exchange responding" if exchange_ok else "exchange unhealthy")
    h.add("account_reconciled", bool(reconciled),
          "reconciled" if reconciled else "NOT reconciled: refuse new entries")
    if regime is not None:
        h.add("regime_tradable",
              regime not in (Regime.PANIC, Regime.DATA_UNRELIABLE),
              regime.value)
    return h
