"""downtrend_ensemble_bot — a short-biased, regime-aware perpetual futures
ensemble that is backtest-first and paper by default.

NOTHING here submits an exchange order unless ENABLE_LIVE_TRADING=true,
LIVE_CONFIRMATION=I_UNDERSTAND_THE_RISK, an interactive confirmation and a
passing pre-flight ALL agree. `config.LiveGate` is the single place that
decision is made, and it fails closed on anything it cannot verify.

No claim of profitability is made anywhere in this package.
"""
__version__ = "0.1.0"
__all__ = ["__version__"]
