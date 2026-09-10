"""Configuration, HARD CEILINGS, and the single place live trading is gated.

Two rules give this module its whole value:

1. **A ceiling is not a default.** `HARD_CEILINGS` is the maximum a config
   file may ask for. A YAML that asks for more is REJECTED — never silently
   clamped — because a clamp turns a typo into a working system with a
   different risk profile than the operator believes it has.

2. **The live gate is one function.** Every path to signing goes through
   `LiveGate.evaluate`. It fails CLOSED on anything it cannot verify, and it
   returns the list of reasons so an operator is told which condition blocked
   them rather than being left to guess.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml

from .models import Mode

#: Absolute maxima. A config may be more conservative; it may never exceed
#: these, and exceeding one is a validation ERROR.
HARD_CEILINGS: dict[str, float] = {
    "risk_per_trade": 0.010,
    "max_portfolio_risk": 0.030,
    "max_daily_loss": 0.050,
    "max_weekly_loss": 0.120,
    "max_leverage": 10.0,
    "max_margin_utilisation": 0.50,
    "max_concurrent_positions": 10,
    "max_notional_per_market_percent": 40.0,
    "max_gross_notional_percent": 300.0,
    "max_net_long_notional_percent": 200.0,
    "max_net_short_notional_percent": 200.0,
}

#: Minimum soak before software will permit live mode.
LIVE_SOAK_DAYS = 30
LIVE_SOAK_SIGNALS = 100

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_THE_RISK"
FLATTEN_CONFIRMATION_PHRASE = "CLOSE_ALL_POSITIONS"


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.004
    max_portfolio_risk: float = 0.012
    max_daily_loss: float = 0.025
    max_weekly_loss: float = 0.07
    max_leverage: float = 10.0
    max_margin_utilisation: float = 0.35
    max_concurrent_positions: int = 6
    max_notional_per_market_percent: float = 25.0
    max_gross_notional_percent: float = 250.0
    max_net_long_notional_percent: float = 150.0
    max_net_short_notional_percent: float = 150.0
    #: The liquidation buffer, in ATR. A stop closer to liquidation than this
    #: is refused: the exchange would close the position before our own risk
    #: rule ever fired, which makes the measured stop distance a fiction.
    min_stop_to_liquidation_atr: float = 2.0
    #: Collateral floor below which sizing is cut rather than refused.
    collateral_buffer_pct: float = 0.15


@dataclass
class StrategyConfig:
    long_minimum_score: float = 62.0
    short_minimum_score: float = 62.0
    neutral_minimum_score: float = 68.0
    bearish_tactical_long_minimum_score: float = 75.0
    minimum_reward_risk: float = 1.4
    neutral_minimum_reward_risk: float = 1.6
    adx_threshold: float = 20.0
    max_entry_distance_atr: float = 1.0
    max_holding_days: float = 7.0
    atr_stop_buffer: float = 0.25
    max_stop_distance_atr: float = 3.0
    tp1_r: float = 1.20
    tp1_fraction: float = 0.30
    tp2_r: float = 2.00
    tp2_fraction: float = 0.35


@dataclass
class RegimeConfig:
    enabled: bool = True
    bullish_long_risk_multiplier: float = 1.0
    bullish_short_risk_multiplier: float = 0.25
    neutral_risk_multiplier: float = 0.75
    bearish_long_risk_multiplier: float = 0.25
    bearish_short_risk_multiplier: float = 1.0
    high_volatility_risk_multiplier: float = 0.50
    panic_risk_multiplier: float = 0.0
    minimum_confirmation_candles: int = 2
    high_volatility_atr_percentile: float = 90.0


@dataclass
class HealthConfig:
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


@dataclass
class OvertradingConfig:
    max_entries_per_market_per_day: int = 3
    max_entries_per_strategy_per_day: int = 10
    max_portfolio_entries_per_hour: int = 5
    cooldown_after_loss_hours: float = 6.0
    cooldown_after_profit_hours: float = 2.0
    cooldown_after_breakeven_hours: float = 3.0
    minimum_signal_score_separation: float = 5.0
    require_fresh_setup_for_reentry: bool = True


@dataclass
class ExecutionConfig:
    max_spread_bps: float = 10.0
    max_slippage_bps: float = 15.0
    order_timeout_seconds: int = 30
    entry_preference: str = "post_only_limit"
    use_ioc_when_necessary: bool = True
    use_reduce_only_exits: bool = True
    require_native_stop_or_fail: bool = True
    taker_fee: float = 0.0
    maker_fee: float = 0.0
    latency_ms: int = 250


@dataclass
class LighterConfig:
    base_url: str = "https://mainnet.zklighter.elliot.ai"
    chain_id: int = 304
    target_max_leverage: float = 10.0
    use_websocket: bool = True
    use_native_sdk: bool = True
    require_market_metadata_validation: bool = True
    require_reduce_only_exits: bool = True
    require_protective_exit_confirmation: bool = True
    margin_mode: str = "isolated"        # "isolated" | "cross" | "detect"


@dataclass
class Timeframes:
    regime: str = "4h"
    signal: str = "1h"
    execution: str = "15m"


@dataclass
class AppConfig:
    mode: Mode = Mode.BACKTEST
    exchange: str = "lighter"
    symbols: list[str] = field(default_factory=list)
    lighter: LighterConfig = field(default_factory=LighterConfig)
    timeframes: Timeframes = field(default_factory=Timeframes)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    strategy_health: HealthConfig = field(default_factory=HealthConfig)
    overtrading: OvertradingConfig = field(default_factory=OvertradingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    state_dir: str = "state"
    runtime_dir: str = "runtime"
    reports_dir: str = "reports"
    data_dir: str = "data"
    log_level: str = "INFO"
    backtest: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


_SECTIONS = {
    "lighter": LighterConfig, "timeframes": Timeframes, "risk": RiskConfig,
    "strategy": StrategyConfig, "regime": RegimeConfig,
    "strategy_health": HealthConfig, "overtrading": OvertradingConfig,
    "execution": ExecutionConfig,
}


def _build(cls, raw: dict[str, Any] | None):
    raw = raw or {}
    known = {f for f in cls.__dataclass_fields__}
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
        exchange=str(raw.get("exchange", "lighter")),
        symbols=list(raw.get("symbols") or []),
        state_dir=str(raw.get("state_dir", "state")),
        runtime_dir=str(raw.get("runtime_dir", "runtime")),
        reports_dir=str(raw.get("reports_dir", "reports")),
        data_dir=str(raw.get("data_dir", "data")),
        log_level=str(raw.get("log_level", "INFO")),
        backtest=dict(raw.get("backtest") or {}),
        **{name: _build(cls, raw.get(name)) for name, cls in _SECTIONS.items()},
    )
    problems = validate(cfg)
    if problems:
        raise ValueError("config rejected:\n  - " + "\n  - ".join(problems))
    return cfg


def validate(cfg: AppConfig) -> list[str]:
    """-> [problem, ...]. Empty means the config is admissible.

    Ceilings are REJECTIONS, not clamps -- see the module docstring."""
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
    if r.min_stop_to_liquidation_atr < 1.0:
        out.append("risk.min_stop_to_liquidation_atr < 1.0 ATR is not a buffer")
    if cfg.lighter.target_max_leverage > HARD_CEILINGS["max_leverage"]:
        out.append(f"lighter.target_max_leverage="
                   f"{cfg.lighter.target_max_leverage} exceeds "
                   f"{HARD_CEILINGS['max_leverage']}")
    if cfg.lighter.target_max_leverage > r.max_leverage:
        out.append("lighter.target_max_leverage exceeds risk.max_leverage")
    s = cfg.strategy
    for k in ("long_minimum_score", "short_minimum_score",
              "neutral_minimum_score", "bearish_tactical_long_minimum_score"):
        v = getattr(s, k)
        if not 0 < v <= 100:
            out.append(f"strategy.{k}={v} must be in (0, 100]")
    if s.minimum_reward_risk < 1.0:
        out.append("strategy.minimum_reward_risk < 1.0 loses money at a 50% "
                   "hit rate before fees")
    if s.tp1_fraction + s.tp2_fraction >= 1.0:
        out.append("strategy.tp1_fraction + tp2_fraction >= 1.0 leaves no "
                   "runner to trail")
    if cfg.regime.panic_risk_multiplier != 0.0:
        out.append("regime.panic_risk_multiplier must be 0.0: PANIC means no "
                   "new entries")
    if cfg.mode is Mode.LIVE and not cfg.execution.require_native_stop_or_fail:
        out.append("execution.require_native_stop_or_fail must be true in "
                   "live mode: a client-only stop dies with the process")
    if cfg.exchange != "lighter":
        out.append(f"exchange={cfg.exchange!r}: this package is Lighter-native")
    return out


# --------------------------------------------------------------- live gate --
@dataclass
class GateResult:
    allowed: bool
    blockers: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


class LiveGate:
    """The ONE decision point for signing. Fails closed on everything."""

    def __init__(self, cfg: AppConfig, env: dict[str, str] | None = None):
        self.cfg = cfg
        self.env = dict(os.environ if env is None else env)

    def kill_switch_present(self) -> bool:
        return os.path.exists(os.path.join(self.cfg.runtime_dir, "KILL_SWITCH"))

    def evaluate(self, *, soak_days: float = 0.0, soak_signals: int = 0,
                 metadata_valid: bool = False, account_reconciled: bool = False,
                 protective_capability: bool = False,
                 nonce_ok: bool = False,
                 interactive_confirmed: bool = False) -> GateResult:
        e, blockers = self.env, []
        checks = {
            "enable_live_trading":
                str(e.get("ENABLE_LIVE_TRADING", "")).strip().lower() == "true",
            "live_confirmation":
                str(e.get("LIVE_CONFIRMATION", "")).strip()
                == LIVE_CONFIRMATION_PHRASE,
            "interactive_confirmation": bool(interactive_confirmed),
            "account_index": bool(str(e.get("LIGHTER_ACCOUNT_INDEX", "")).strip()),
            "api_key_index": bool(str(e.get("LIGHTER_API_KEY_INDEX", "")).strip()),
            "api_private_key":
                bool(str(e.get("LIGHTER_API_PRIVATE_KEY", "")).strip()),
            "no_kill_switch": not self.kill_switch_present(),
            "market_metadata_valid": bool(metadata_valid),
            "account_reconciled": bool(account_reconciled),
            "protective_order_capability": bool(protective_capability),
            "nonce_manager_ok": bool(nonce_ok),
            "risk_within_ceilings": not validate(self.cfg),
        }
        soak_override = str(e.get("LIVE_SOAK_OVERRIDE", "")).strip().lower() \
            in ("true", "1", "yes")
        checks["soak_complete"] = bool(
            soak_override
            or (soak_days >= LIVE_SOAK_DAYS and soak_signals >= LIVE_SOAK_SIGNALS))
        if soak_override:
            checks["soak_overridden_documented"] = True
        for name, ok in checks.items():
            if not ok:
                blockers.append(name)
        return GateResult(allowed=not blockers, blockers=blockers, checks=checks)


def flatten_confirmed(env: dict[str, str] | None = None) -> bool:
    e = dict(os.environ if env is None else env)
    return str(e.get("FLATTEN_CONFIRMATION", "")).strip() \
        == FLATTEN_CONFIRMATION_PHRASE
