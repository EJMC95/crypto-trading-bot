"""Configuration, HARD CEILINGS, and the single place live trading is gated.

Two rules give this module its value:

1. **A ceiling is not a default.** `HARD_CEILINGS` is the maximum a config may
   ASK for. A YAML that asks for more is REJECTED, never silently clamped -- a
   clamp turns a typo into a working system with a different risk profile than
   the operator believes it has.

2. **The live gate is one function.** Every path to submitting an order goes
   through `LiveGate.evaluate`. It fails CLOSED on anything it cannot verify
   and returns the full blocker list, so an operator is told which condition
   stopped them rather than fixing one at a time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml

from .models import Mode

#: Absolute maxima. A config may be more conservative; never less.
#: These are deliberately close to the defaults -- this is a conservative
#: system and the ceiling is not meant to be a target.
HARD_CEILINGS: dict[str, float] = {
    "risk_per_trade": 0.005,
    "max_portfolio_risk": 0.015,
    "max_daily_loss": 0.030,
    "max_weekly_loss": 0.080,
    "max_leverage": 3.0,
    "max_concurrent_positions": 5,
    "max_notional_per_symbol_pct": 0.35,
    "max_aggregate_short_notional_pct": 0.75,
    "max_margin_utilisation": 0.50,
}

#: Minimum paper soak before software will permit live mode (spec 13).
PAPER_SOAK_DAYS = 30
PAPER_SOAK_MIN_TRADES = 20

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_THE_RISK"
FLATTEN_CONFIRMATION_PHRASE = "CLOSE_ALL_POSITIONS"

#: The ONLY environment variables `LiveGate` copies. Least privilege on secret
#: material: `dict(os.environ)` would put every secret in the process onto a
#: long-lived object that is passed around and partially rendered in reports.
_GATE_ENV_KEYS = ("ENABLE_LIVE_TRADING", "LIVE_CONFIRMATION",
                  "PAPER_SOAK_OVERRIDE")


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.0025
    max_portfolio_risk: float = 0.0075
    max_daily_loss: float = 0.015
    max_weekly_loss: float = 0.04
    max_leverage: float = 1.5
    max_concurrent_positions: int = 3
    max_correlated_positions: int = 2
    max_notional_per_symbol_pct: float = 0.25
    max_aggregate_short_notional_pct: float = 0.50
    max_margin_utilisation: float = 0.35
    max_consecutive_losses: int = 4
    #: Correlation penalty applied to the Nth position in one correlated group.
    correlation_penalty: float = 0.5


@dataclass
class StrategyConfig:
    minimum_score: float = 70.0
    #: MEASURED INERT on the shipped tapes, and for a STRUCTURAL reason:
    #: `targets` are fixed R-multiples of the stop, so a signal's reward/risk
    #: is `tp2_r` BY CONSTRUCTION and this bar can never bind below it. The
    #: 40-cell sweep confirms it (spread 0.000pp across 1.4/1.8/2.2). Declared
    #: rather than deleted -- it DOES bind above tp2_r, and the regime engine's
    #: `neutral_minimum_reward_risk` raises it -- and declared rather than
    #: quietly left inert, because a knob that reaches no decision is exactly
    #: what someone tunes for a day before finding out.
    minimum_reward_risk: float = 1.8
    adx_threshold: float = 20.0
    max_entry_distance_atr: float = 0.75
    max_holding_days: float = 5.0
    atr_stop_buffer: float = 0.25
    max_stop_distance_atr: float = 3.0
    structure_window: int = 20
    tp1_r: float = 1.5
    tp1_fraction: float = 0.35
    tp2_r: float = 2.5
    tp2_fraction: float = 0.35
    #: RSI band for a CONTINUATION short. Outside it, momentum scores zero --
    #: a deeply oversold reading is not a reason to short (spec 6C).
    rsi_short_lo: float = 35.0
    rsi_short_hi: float = 60.0
    rsi_long_lo: float = 40.0
    rsi_long_hi: float = 68.0
    #: Volume must clear this multiple of its rolling average to score.
    volume_ratio_floor: float = 1.0
    #: INDICATOR PERIODS. Configurable because spec 12 requires the sensitivity
    #: sweep to vary EMA lengths, and a sweep dimension that reaches no code is
    #: an inert knob -- a result that "EMA length does not matter" would then be
    #: a property of the harness, not of the strategy. `ema_fast < ema_mid <
    #: ema_slow` is validated rather than assumed.
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    atr_period: int = 14
    rsi_period: int = 14
    adx_period: int = 14


@dataclass
class RegimeConfig:
    enabled: bool = True
    bullish_risk_multiplier: float = 1.0
    neutral_risk_multiplier: float = 0.5
    bearish_risk_multiplier: float = 0.0
    high_volatility_risk_multiplier: float = 0.35
    panic_risk_multiplier: float = 0.0
    minimum_regime_confirmation_candles: int = 2
    market_breadth_threshold: float = 0.55
    high_volatility_atr_percentile: float = 90.0
    #: BTC needs stronger confirmation before it may be shorted (spec 5).
    btc_extra_confirmation_candles: int = 2
    #: NEUTRAL raises the bars for a long (spec 21).
    neutral_minimum_reward_risk: float = 2.0
    neutral_score_bump: float = 5.0


@dataclass
class StrategyHealthConfig:
    enabled: bool = True
    warning_trade_count: int = 20
    hard_pause_trade_count: int = 30
    throttle_profit_factor: float = 0.85
    pause_profit_factor: float = 0.65
    throttle_expectancy: float = 0.0
    max_consecutive_losses: int = 4
    warning_drawdown: float = 0.05
    hard_drawdown: float = 0.08
    recovery_risk_multiplier: float = 0.25
    throttle_risk_multiplier: float = 0.50
    throttle_score_bump: float = 5.0
    throttle_rr_bump: float = 0.2
    #: RECOVERY -> ACTIVE needs this many clean trades AND a positive
    #: expectancy. Time alone never promotes (spec 24).
    recovery_min_trades: int = 10
    recovery_min_paper_signals: int = 20


@dataclass
class OvertradingConfig:
    max_entries_per_symbol_per_day: int = 2
    max_entries_per_strategy_per_day: int = 6
    max_portfolio_entries_per_hour: int = 3
    max_entries_during_regime_transition: int = 1
    cooldown_after_loss_hours: float = 6.0
    cooldown_after_profit_hours: float = 2.0
    minimum_signal_score_separation: float = 5.0
    maximum_same_setup_entries: int = 1
    require_fresh_setup_for_reentry: bool = True
    #: Churn guard: a re-entry needs time OR price displacement (spec 26C).
    reentry_min_hours: float = 4.0
    reentry_min_atr_displacement: float = 1.0


@dataclass
class ExecutionConfig:
    max_spread_bps: float = 8.0
    max_slippage_bps: float = 12.0
    order_timeout_seconds: int = 30
    use_reduce_only_exits: bool = True
    prefer_limit_orders: bool = True
    #: A marketable limit is permitted ONLY with a slippage cap. An
    #: unrestricted market order is never emitted by this package.
    allow_marketable_limit: bool = True
    maker_fee: float = 0.0002
    taker_fee: float = 0.00055
    latency_ms: int = 250


@dataclass
class UniverseConfig:
    min_quote_volume_24h: float = 50_000_000.0
    max_spread_bps: float = 8.0
    min_depth_usd: float = 100_000.0
    max_candle_staleness_bars: float = 2.0
    #: Refuse anything not on this list of quote currencies.
    allowed_quotes: list[str] = field(default_factory=lambda: ["USDT", "USDC"])


@dataclass
class ChangePointConfig:
    enabled: bool = True
    window: int = 20
    baseline_window: int = 60
    z_threshold: float = 2.5
    cusum_threshold: float = 5.0
    #: Hysteresis: a detection must persist before it acts, and must stay
    #: clear before it clears. Without this the detector flips on noise.
    min_duration_bars: int = 3
    clear_duration_bars: int = 5


@dataclass
class Timeframes:
    regime: str = "4h"
    signal: str = "1h"
    execution: str = "15m"


@dataclass
class BacktestConfig:
    start_equity: float = 10_000.0
    spread_bps: float = 3.0
    slippage_bps: float = 4.0
    funding_per_hour: float = 0.0000125     # +ve costs LONGS, pays SHORTS
    partial_fill_rate: float = 0.10
    partial_fill_fraction: float = 0.6
    limit_miss_rate: float = 0.20
    reject_rate: float = 0.0
    monte_carlo_runs: int = 500


@dataclass
class AppConfig:
    mode: Mode = Mode.BACKTEST
    exchange: str = "mock"
    symbols: list[str] = field(default_factory=lambda: [
        "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    benchmark_symbol: str = "BTC/USDT:USDT"
    timeframes: Timeframes = field(default_factory=Timeframes)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    strategy_health: StrategyHealthConfig = field(
        default_factory=StrategyHealthConfig)
    overtrading: OvertradingConfig = field(default_factory=OvertradingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    changepoint: ChangePointConfig = field(default_factory=ChangePointConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    allow_longs: bool = True
    data_dir: str = "data"
    runtime_dir: str = "runtime"
    reports_dir: str = "reports"
    state_db: str = "runtime/state.sqlite"
    log_level: str = "INFO"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


_SECTIONS = {
    "timeframes": Timeframes, "risk": RiskConfig, "strategy": StrategyConfig,
    "regime": RegimeConfig, "strategy_health": StrategyHealthConfig,
    "overtrading": OvertradingConfig, "execution": ExecutionConfig,
    "universe": UniverseConfig, "changepoint": ChangePointConfig,
    "backtest": BacktestConfig,
}


def _build(cls, raw: dict[str, Any] | None):
    raw = raw or {}
    known = set(cls.__dataclass_fields__)
    unknown = set(raw) - known
    if unknown:
        raise ValueError(
            f"{cls.__name__}: unknown key(s) {sorted(unknown)}. A silently "
            "ignored key is a setting the operator believes is applied.")
    return cls(**{k: v for k, v in raw.items() if k in known})


def load(path: str) -> AppConfig:
    with open(path) as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    cfg = AppConfig(
        mode=Mode(str(raw.get("mode", "backtest")).lower()),
        exchange=str(raw.get("exchange", "mock")),
        symbols=list(raw.get("symbols") or ["BTC/USDT:USDT", "ETH/USDT:USDT",
                                            "SOL/USDT:USDT"]),
        benchmark_symbol=str(raw.get("benchmark_symbol", "BTC/USDT:USDT")),
        allow_longs=bool(raw.get("allow_longs", True)),
        data_dir=str(raw.get("data_dir", "data")),
        runtime_dir=str(raw.get("runtime_dir", "runtime")),
        reports_dir=str(raw.get("reports_dir", "reports")),
        state_db=str(raw.get("state_db", "runtime/state.sqlite")),
        log_level=str(raw.get("log_level", "INFO")),
        **{name: _build(cls, raw.get(name)) for name, cls in _SECTIONS.items()},
    )
    problems = validate(cfg)
    if problems:
        raise ValueError("config rejected:\n  - " + "\n  - ".join(problems))
    return cfg


def validate(cfg: AppConfig) -> list[str]:
    """-> [problem, ...]. Empty means admissible. Ceilings REJECT."""
    out: list[str] = []
    r = cfg.risk
    for key, ceiling in HARD_CEILINGS.items():
        got = getattr(r, key, None)
        if got is None:
            continue
        if got > ceiling:
            out.append(f"risk.{key}={got} exceeds the hard ceiling {ceiling}")
        if got <= 0:
            out.append(f"risk.{key}={got} must be positive")
    if r.risk_per_trade > r.max_portfolio_risk:
        out.append(f"risk.risk_per_trade ({r.risk_per_trade}) exceeds "
                   f"max_portfolio_risk ({r.max_portfolio_risk}): the first "
                   "trade would already breach the portfolio budget")
    if r.max_daily_loss > r.max_weekly_loss:
        out.append("risk.max_daily_loss exceeds max_weekly_loss")
    if r.max_correlated_positions > r.max_concurrent_positions:
        out.append("risk.max_correlated_positions exceeds "
                   "max_concurrent_positions")
    s = cfg.strategy
    if not 0 < s.minimum_score <= 100:
        out.append(f"strategy.minimum_score={s.minimum_score} must be in (0,100]")
    if s.minimum_reward_risk < 1.0:
        out.append("strategy.minimum_reward_risk < 1.0 loses money at a 50% "
                   "hit rate before fees")
    if s.tp1_fraction + s.tp2_fraction >= 1.0:
        out.append("strategy.tp1_fraction + tp2_fraction >= 1.0 leaves no "
                   "runner to trail")
    if s.rsi_short_lo >= s.rsi_short_hi:
        out.append("strategy.rsi_short_lo must be below rsi_short_hi")
    if s.max_entry_distance_atr <= 0:
        out.append("strategy.max_entry_distance_atr must be positive")
    if not (s.ema_fast < s.ema_mid < s.ema_slow):
        out.append(f"strategy EMA lengths must be strictly increasing, got "
                   f"fast={s.ema_fast} mid={s.ema_mid} slow={s.ema_slow}")
    for name in ("ema_fast", "ema_mid", "ema_slow", "atr_period",
                 "rsi_period", "adx_period"):
        if getattr(s, name) < 2:
            out.append(f"strategy.{name} must be >= 2 bars")
    g = cfg.regime
    if g.bearish_risk_multiplier != 0.0:
        out.append("regime.bearish_risk_multiplier must be 0.0: BEARISH "
                   "disables new trend-following LONGS by default (spec 21)")
    if g.panic_risk_multiplier != 0.0:
        out.append("regime.panic_risk_multiplier must be 0.0: PANIC means no "
                   "new entries")
    if g.minimum_regime_confirmation_candles < 1:
        out.append("regime.minimum_regime_confirmation_candles must be >= 1")
    if not 0.0 < g.market_breadth_threshold < 1.0:
        out.append("regime.market_breadth_threshold must be a fraction in (0,1)")
    e = cfg.execution
    if e.max_slippage_bps <= 0 or e.max_spread_bps <= 0:
        out.append("execution spread/slippage limits must be positive")
    if cfg.mode is Mode.LIVE and not e.use_reduce_only_exits:
        out.append("execution.use_reduce_only_exits must be true in live mode: "
                   "a non-reduce-only exit can OPEN an opposite position on a "
                   "race with a partial fill")
    c = cfg.changepoint
    if c.min_duration_bars < 1 or c.clear_duration_bars < 1:
        out.append("changepoint hysteresis windows must be >= 1 bar, or the "
                   "detector flips state on noise")
    for sym in cfg.symbols:
        if "/" not in sym:
            out.append(f"symbol {sym!r} is not in BASE/QUOTE[:SETTLE] form")
    if cfg.benchmark_symbol not in cfg.symbols:
        out.append(f"benchmark_symbol {cfg.benchmark_symbol!r} must be in "
                   "symbols: the market regime is computed from it")
    return out


# --------------------------------------------------------------- live gate --
@dataclass
class GateResult:
    allowed: bool
    blockers: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


class LiveGate:
    """The ONE decision point for submitting orders. Fails closed."""

    def __init__(self, cfg: AppConfig, env: dict[str, str] | None = None):
        self.cfg = cfg
        src = os.environ if env is None else env
        self.env = {k: src.get(k, "") for k in _GATE_ENV_KEYS}

    def kill_switch_present(self) -> bool:
        return os.path.exists(os.path.join(self.cfg.runtime_dir, "KILL_SWITCH"))

    def evaluate(self, *, paper_days: float = 0.0, paper_trades: int = 0,
                 paper_report_exists: bool = False,
                 paper_checks_passed: bool = False,
                 account_reconciled: bool = False,
                 protective_capability: bool = False,
                 data_healthy: bool = False,
                 interactive_confirmed: bool = False) -> GateResult:
        e = self.env
        checks = {
            "enable_live_trading":
                str(e.get("ENABLE_LIVE_TRADING", "")).strip().lower() == "true",
            "live_confirmation":
                str(e.get("LIVE_CONFIRMATION", "")).strip()
                == LIVE_CONFIRMATION_PHRASE,
            "interactive_confirmation": bool(interactive_confirmed),
            "no_kill_switch": not self.kill_switch_present(),
            "paper_report_exists": bool(paper_report_exists),
            "paper_checks_passed": bool(paper_checks_passed),
            "account_reconciled": bool(account_reconciled),
            "protective_exit_capability": bool(protective_capability),
            "data_healthy": bool(data_healthy),
            "risk_within_ceilings": not validate(self.cfg),
        }
        override = str(e.get("PAPER_SOAK_OVERRIDE", "")).strip().lower() \
            in ("true", "1", "yes")
        checks["paper_soak_complete"] = bool(
            override or (paper_days >= PAPER_SOAK_DAYS
                         and paper_trades >= PAPER_SOAK_MIN_TRADES))
        if override:
            checks["paper_soak_overridden_documented"] = True
        return GateResult(allowed=all(checks.values()),
                          blockers=[k for k, v in checks.items() if not v],
                          checks=checks)


def flatten_confirmed(env: dict[str, str] | None = None) -> bool:
    src = os.environ if env is None else env
    return str(src.get("FLATTEN_CONFIRMATION", "")).strip() \
        == FLATTEN_CONFIRMATION_PHRASE
