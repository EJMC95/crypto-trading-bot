#!/usr/bin/env python3
"""
compile_market_data.py — dependency-light crypto market snapshot for the research
scan. Pulls from several FREE, no-auth sources and prints a compact markdown
brief (and saves it to reports/market_snapshot_latest.md). Stdlib only.

Sources (each guarded; a failure degrades gracefully and is noted):
  - Binance klines      -> per-coin trend (price vs 200d SMA), 7d/30d return, 30d vol
  - Binance 24h ticker  -> 24h % change
  - alternative.me      -> Fear & Greed index
  - CoinGecko /global   -> BTC dominance, total market cap + 24h change

Computes a "breadth" gauge: how many of the validated basket are above their
200-day SMA — the regime backdrop the trend bots (V4/V6/V7) depend on.
"""
import json, os, statistics, urllib.request, urllib.error
from datetime import datetime, timezone

BASKET = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
          "LINK", "DOT", "LTC", "BCH", "ATOM", "XLM", "TRX"]
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (market-snapshot)"}


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def coin_trend(sym):
    """Return dict of trend metrics for SYM via Binance daily klines, or None."""
    try:
        kl = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1d&limit=250")
        closes = [float(k[4]) for k in kl]
        if len(closes) < 60:
            return None
        price = closes[-1]
        s200 = sma(closes, 200)
        s50 = sma(closes, 50)
        rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        vol30 = statistics.pstdev(rets[-30:]) * (365 ** 0.5) if len(rets) >= 30 else None
        r7 = price / closes[-8] - 1 if len(closes) >= 8 else None
        r30 = price / closes[-31] - 1 if len(closes) >= 31 else None
        return {"price": price, "above_200d": (s200 is not None and price > s200),
                "golden": (s50 is not None and s200 is not None and s50 > s200),
                "r7": r7, "r30": r30, "vol30_annual": vol30}
    except Exception:
        return None


def pct(x):
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def snapshot_markdown():
    """Build and RETURN the market snapshot as a markdown string (no I/O)."""
    now = datetime.now(timezone.utc)
    lines = [f"## Market snapshot — {now:%Y-%m-%d %H:%M UTC}", ""]
    notes = []

    # --- Fear & Greed ---
    try:
        fng = _get("https://api.alternative.me/fng/?limit=1")["data"][0]
        lines.append(f"- **Fear & Greed:** {fng['value']} ({fng['value_classification']})")
    except Exception as e:
        notes.append(f"fear&greed unavailable ({type(e).__name__})")

    # --- Global (dominance, total mcap) ---
    try:
        g = _get("https://api.coingecko.com/api/v3/global")["data"]
        btc_dom = g["market_cap_percentage"]["btc"]
        mcap_chg = g["market_cap_change_percentage_24h_usd"]
        tot = g["total_market_cap"]["usd"]
        lines.append(f"- **BTC dominance:** {btc_dom:.1f}%  ·  **Total mcap:** ${tot/1e12:.2f}T "
                     f"({mcap_chg:+.1f}% 24h)")
    except Exception as e:
        notes.append(f"coingecko global unavailable ({type(e).__name__})")

    # --- Per-coin trend + breadth ---
    trends = {}
    for c in BASKET:
        t = coin_trend(c)
        if t:
            trends[c] = t
    if trends:
        above = [c for c, t in trends.items() if t["above_200d"]]
        golden = [c for c, t in trends.items() if t["golden"]]
        lines += [
            "",
            f"- **Breadth:** {len(above)}/{len(trends)} of the basket above their 200-day SMA; "
            f"{len(golden)}/{len(trends)} in a 50>200 golden cross.",
            f"- **Regime read:** "
            + ("RISK-ON / trending — favourable for the trend bots (V4/V6/V7)."
               if len(above) >= 0.6 * len(trends) else
               "MIXED / choppy — trend bots may sit out or churn; watch V7."
               if len(above) >= 0.35 * len(trends) else
               "RISK-OFF / downtrend — trend bots should mostly be in cash; V5 stays gated."),
            "",
            "| Coin | vs200d | 50>200 | 7d | 30d | annual vol |",
            "|------|--------|--------|----|-----|-----------|",
        ]
        for c in BASKET:
            t = trends.get(c)
            if not t:
                continue
            lines.append(f"| {c} | {'↑' if t['above_200d'] else '↓'} | "
                         f"{'✓' if t['golden'] else '—'} | {pct(t['r7'])} | {pct(t['r30'])} | "
                         f"{pct(t['vol30_annual'])} |")
    else:
        notes.append("per-coin trend unavailable (Binance klines blocked?) — "
                     "agent should fall back to WebSearch / Kraken public OHLC")

    if notes:
        lines += ["", "_source notes: " + "; ".join(notes) + "_"]

    return "\n".join(lines)


def main():
    out = snapshot_markdown()
    print(out)
    try:
        os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
        with open(os.path.join(HERE, "reports", "market_snapshot_latest.md"), "w") as f:
            f.write(out + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
