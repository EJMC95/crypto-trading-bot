#!/usr/bin/env python3
"""
regime_oracle.py — CROSS-BOT LAYER 1: one shared read of the tape.

[2026-07-07] Built from the fleet's cross-bot intelligence design (see
CROSS_BOT_INTELLIGENCE_DESIGN_2026-07-07.md). Nine bots each computing a
private regime opinion is eight redundant opinions; this publishes ONE.

WHAT IT DOES
  * For each major, computes the same two-axis regime the fleet's best bots
    use: DIRECTION (close vs daily EMA200 + EMA50 3-day slope) and CHARACTER
    (Wilder ADX(14) with hysteresis: trending >= ADX_TREND, chop <= ADX_CHOP,
    hold previous in between — same bands RegimeSwitchV2 runs).
  * Publishes to Postgres bot_state key "regime-oracle" (via bot_pnl_store,
    guarded: no-op without DATABASE_URL) and appends a row to
    bot_state_history so the oracle's calls become BACKTESTABLE later
    (meta-labeling, Phase 4, needs this archive).
  * Data source: Hyperliquid public candleSnapshot (daily, CLOSED candles
    only — the partial today-candle is dropped, matching freqtrade behavior).

WEEK-ONE MODE: ADVISORY / PUBLISH-ONLY. No bot reads this yet. After a week
of history we compare its calls against what bots did (the enforcement
decision is data, not vibes).

FAIL-SAFE CONTRACT (consumers): payload carries `updated` + `ttl_sec`. If
now - updated > ttl_sec, IGNORE the oracle and fall back to local gates —
a stale oracle must never steer the fleet. (Spec'd 2026-07-01.)

Run-once process; run_all.sh loops it every 30 min (same pattern as
market_pulse). Crash of this process affects nothing else.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import bot_pnl_store as store

KEY = "regime-oracle"
TTL_SEC = 7200          # consumers must ignore anything older than 2h

# The fleet's shared majors: RegimeSwitchV2's 10 + DOT/NEAR for spot coverage.
UNIVERSE = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
            "LINK", "LTC", "DOT", "NEAR", "SUI"]  # SUI added — fleet holds it (day-zero review catch)

ADX_TREND = 17          # >= trending (matches RegimeSwitchV2 after Jul-6 cut)
ADX_CHOP = 11           # <= chop; between = hysteresis (hold previous)
EMA_FAST, EMA_SLOW, SLOPE_BARS = 50, 200, 3
LOOKBACK_DAYS = 300     # enough for a stable EMA200

HL_INFO = "https://api.hyperliquid.xyz/info"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_daily(coin):
    start = int((time.time() - LOOKBACK_DAYS * 86400) * 1000)
    body = json.dumps({"type": "candleSnapshot",
                       "req": {"coin": coin, "interval": "1d",
                               "startTime": start}}).encode()
    req = urllib.request.Request(HL_INFO, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read().decode())
    df = pd.DataFrame(rows)
    for k in ("o", "h", "l", "c"):
        df[k] = df[k].astype(float)
    return df.iloc[:-1]  # closed candles only


def wilder_adx(df, n=14):
    h, l, c = df["h"], df["l"], df["c"]
    up, dn = h.diff(), -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def classify(df, prev_trend):
    e_fast = df["c"].ewm(span=EMA_FAST, adjust=False).mean()
    e_slow = df["c"].ewm(span=EMA_SLOW, adjust=False).mean()
    adx = float(wilder_adx(df).iloc[-1])
    close = float(df["c"].iloc[-1])
    slope = float(e_fast.iloc[-1] - e_fast.iloc[-1 - SLOPE_BARS])
    up = close > float(e_slow.iloc[-1]) and slope > 0
    down = close < float(e_slow.iloc[-1]) and slope < 0
    direction = 1 if up else (-1 if down else 0)
    # hysteresis on character
    if adx >= ADX_TREND:
        trend = 1
    elif adx <= ADX_CHOP:
        trend = 0
    else:
        trend = prev_trend if prev_trend is not None else 0
    if trend and direction == 1:
        verdict = "LONG-window"
    elif trend and direction == -1:
        verdict = "SHORT-window"
    elif direction == 0:
        verdict = "dir-flat"
    else:
        verdict = "chop-gated"
    return {"dir": direction, "trend": trend, "adx": round(adx, 1),
            "close": close, "ema200": round(float(e_slow.iloc[-1]), 6),
            "verdict": verdict, "asof": str(df["t"].iloc[-1])}


def main():
    prev = store.load_state(KEY) or {}
    prev_pairs = prev.get("pairs", {})
    pairs, errors = {}, []
    for coin in UNIVERSE:
        try:
            df = fetch_daily(coin)
            if len(df) < EMA_SLOW + SLOPE_BARS:
                errors.append(f"{coin}:short-history({len(df)})")
                continue
            pairs[coin] = classify(df, (prev_pairs.get(coin) or {}).get("trend"))
        except Exception as e:
            errors.append(f"{coin}:{type(e).__name__}")
        time.sleep(0.4)  # gentle on the public API

    if not pairs:
        print(f"[regime-oracle] {now_iso()} FAILED for all coins ({errors}) — "
              f"NOT publishing (consumers keep last good + TTL)")
        return

    n_long = sum(1 for p in pairs.values() if p["verdict"] == "LONG-window")
    n_short = sum(1 for p in pairs.values() if p["verdict"] == "SHORT-window")
    n_idle = len(pairs) - n_long - n_short
    read = ("risk-off downtrend" if n_short > n_long and n_short >= 4 else
            "risk-on uptrend" if n_long > n_short and n_long >= 4 else
            "mixed / transitional")
    payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC,
        "params": {"adx_trend": ADX_TREND, "adx_chop": ADX_CHOP,
                   "ema": [EMA_FAST, EMA_SLOW], "source": "hyperliquid-1d"},
        "pairs": pairs,
        "fleet": {"n_long": n_long, "n_short": n_short, "n_flat_or_chop": n_idle,
                  "read": read},
        "errors": errors,
    }
    store.save_state(KEY, payload)
    store.save_history(KEY, {"fleet": payload["fleet"],
                             "pairs": {k: {"dir": v["dir"], "trend": v["trend"],
                                           "adx": v["adx"], "verdict": v["verdict"]}
                                       for k, v in pairs.items()}})
    print(f"[regime-oracle] {now_iso()} {read} | long={n_long} short={n_short} "
          f"flat/chop={n_idle}" + (f" | errors: {','.join(errors)}" if errors else ""))
    for k, v in pairs.items():
        print(f"[regime-oracle]   {k:5s} adx={v['adx']:5.1f} dir={v['dir']:+d} "
              f"trend={v['trend']} -> {v['verdict']}")


if __name__ == "__main__":
    main()
