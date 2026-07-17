"""Canonical fleet rename map — single source of truth for code + DB migration."""
# old_key -> (new_key, descriptive_label)
RENAME = {
    "trend-golden-cross":    ("crypto-trend-daily",        "Crypto · Trend Follower (50/200, Daily)"),
    "intraday-daytrader-5m": ("crypto-intraday-15m",       "Crypto · Intraday Breakout (15M)"),
    "swing-dip-buyer":       ("crypto-swing-daily",        "Crypto · Mean-Reversion Swing (Daily)"),
    "momo-breakout-4h":      ("crypto-breakout-4h",        "Crypto · Breakout Momentum (4H)"),
    "momo-breakout-alt":     ("crypto-trendmomo-4h",       "Crypto · Trend Momentum (SMA, 4H)"),
    "hl-perps-rsi":          ("perps-rsi-meanrev",         "Perps · RSI Mean-Reversion (Hyperliquid)"),
    "hl-momo-breakout":      ("perps-donchian-breakout",   "Perps · Donchian Breakout (Hyperliquid)"),
    "triangular-arb":        ("scanner-triangular-arb",    "Scanner · Triangular Arbitrage"),
    "cross-exchange-arb":    ("scanner-cross-exchange-arb","Scanner · Cross-Exchange Arbitrage"),
    "listing-sniper":        ("event-listing-sniper",      "Event · New-Listing Sniper"),
    "ikbr-stock-bot":        ("equities-regime-ibkr",      "Equities · SPY/QQQ Regime (IBKR)"),
    "alpaca-momentum":       ("equities-momentum-alpaca",  "Equities · Momentum Rank (Alpaca)"),
}
