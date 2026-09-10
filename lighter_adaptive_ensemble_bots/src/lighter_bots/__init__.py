"""lighter_adaptive_ensemble_bots — a backtest-first long/short perpetual
ensemble for the Lighter exchange.

DEFAULT MODE IS BACKTEST. Nothing in this package signs a transaction unless
`ENABLE_LIVE_TRADING=true`, `LIVE_CONFIRMATION=I_UNDERSTAND_THE_RISK`, an
interactive confirmation and a passing pre-flight all agree. See
`config.LiveGate` for the single place that decision is made.

No claim of profitability is made anywhere in this package. The measured
evidence that motivated its design is in `reports/` and is deliberately
mixed: two of the three cells it started from were REFUTED.
"""
__version__ = "0.1.0"
__all__ = ["__version__"]
