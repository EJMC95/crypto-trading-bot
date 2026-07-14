#!/usr/bin/env python3
"""
trade_analyzer.py — in-depth win/loss post-mortem for the live (paper) Freqtrade bots.

Reads the durable per-trade history from Postgres (bot_trades, populated by the
pnl poller) and, per strategy, computes a proper breakdown of what is winning and
what is losing: win rate, expectancy, profit factor, and slices by exit reason,
pair, hour-of-day, weekday, holding-duration bucket and entry tag. It then emits
plain-English recommendations.

Philosophy (this matters): the goal is NOT "do more of whatever recently won" —
that is recency/overfitting and is how trading systems blow up. The analysis is
oriented toward ROBUST edge: cut the patterns that lose, and only trust a winning
pattern if it has enough trades behind it. Structural recommendations are surfaced
for human review; the only thing applied automatically is the trainer's
out-of-sample-validated parameter tuning (and only when it's actually profitable).

Importable (run_analysis) and runnable standalone. Stdlib + bot_pnl_store only.
"""
from collections import defaultdict
from datetime import datetime, timezone

import bot_pnl_store as store

# live bot publish-name -> strategy class
# [2026-07-15 FAMILY COVERAGE] The July family bots were never in this map, so
# the dashboard Learning tab silently excluded them (georgia had the fleet's
# most closed trades with no card). Grouping is BY STRATEGY, so dad's trades
# merge into the MomoBreakoutV1 card and georgia's into DayTraderV5Gated —
# same semantic the map already used for crypto-trendmomo-4h/breakout-4h.
BOT_TO_STRATEGY = {
    "crypto-swing-daily":       "SwingDipV1",
    "crypto-breakout-4h":      "MomoBreakoutV1",
    "crypto-trendmomo-4h":     "MomoBreakoutV1",
    "crypto-intraday-15m": "DayTraderV5Gated",
    "crypto-trend-daily":    "ImprovedStrategyV4",
    "freqtrade-mum":            "TrendMomoV1",
    "freqtrade-dad":           "MomoBreakoutV1",
    "freqtrade-avo-maria":      "SwingDipV1",
    "freqtrade-georgia":   "DayTraderV5Gated",
}
MIN_GROUP = 5  # don't draw conclusions from a slice with fewer trades than this


def _bucket_duration(mins):
    if mins is None:
        return "unknown"
    if mins < 60:
        return "<1h"
    if mins < 240:
        return "1-4h"
    if mins < 1440:
        return "4-24h"
    if mins < 4320:
        return "1-3d"
    return ">3d"


def _slice_stats(trades, keyfn):
    out = defaultdict(lambda: {"n": 0, "wins": 0, "sum": 0.0})
    for t in trades:
        k = keyfn(t)
        if k is None:
            continue
        r = t.get("profit_ratio") or 0.0
        g = out[k]
        g["n"] += 1
        g["wins"] += 1 if r > 0 else 0
        g["sum"] += r
    # finalize
    res = {}
    for k, g in out.items():
        res[str(k)] = {
            "n": g["n"],
            "win_rate": round(g["wins"] / g["n"], 3) if g["n"] else 0.0,
            "avg_ratio": round(g["sum"] / g["n"], 5) if g["n"] else 0.0,
            "total_ratio": round(g["sum"], 5),
        }
    return dict(sorted(res.items(), key=lambda kv: kv[1]["total_ratio"]))


def analyze(trades):
    """Compute the full stat block for one strategy's closed trades."""
    n = len(trades)
    if n == 0:
        return {"n": 0}
    ratios = [(t.get("profit_ratio") or 0.0) for t in trades]
    wins = [r for r in ratios if r > 0]
    losses = [r for r in ratios if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    stats = {
        "n": n,
        "win_rate": round(len(wins) / n, 3),
        "avg_win": round(gross_win / len(wins), 5) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 5) if losses else 0.0,
        "expectancy": round(sum(ratios) / n, 5),               # avg profit per trade
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else float("inf"),
        "total_return_ratio": round(sum(ratios), 5),
        "best": round(max(ratios), 5),
        "worst": round(min(ratios), 5),
        "by_exit_reason": _slice_stats(trades, lambda t: t.get("exit_reason") or "none"),
        "by_pair": _slice_stats(trades, lambda t: t.get("pair")),
        "by_enter_tag": _slice_stats(trades, lambda t: t.get("enter_tag") or "none"),
        "by_duration": _slice_stats(trades, lambda t: _bucket_duration(t.get("duration_min"))),
        "by_hour": _slice_stats(trades, lambda t: _hour(t)),
        "by_weekday": _slice_stats(trades, lambda t: _weekday(t)),
    }
    return stats


def _close_dt(t):
    c = t.get("close_ts")
    if c is None:
        return None
    if isinstance(c, datetime):
        return c
    try:
        return datetime.fromisoformat(str(c).replace("Z", "+00:00"))
    except Exception:
        return None


def _hour(t):
    dt = _close_dt(t)
    return f"{dt.astimezone(timezone.utc).hour:02d}h" if dt else None


def _weekday(t):
    dt = _close_dt(t)
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()] if dt else None


def recommendations(s):
    """Turn the stats into a short list of robust, human-review recommendations."""
    recs = []
    if s.get("n", 0) < MIN_GROUP:
        return [f"Only {s.get('n', 0)} closed trades so far — not enough to draw "
                f"conclusions yet. Let it keep paper-trading."]
    pf = s["profit_factor"]
    if pf < 1.0:
        recs.append(f"Profit factor {pf} (<1): the strategy is net-losing on closed "
                    f"trades. Do NOT scale it; the retrainer will only adopt params "
                    f"that are profitable out-of-sample.")
    else:
        recs.append(f"Profit factor {pf} (>1) with win rate {s['win_rate']:.0%} and "
                    f"expectancy {s['expectancy']:+.4f}/trade — a real edge if it holds up.")

    # worst loss cluster by exit reason
    er = s["by_exit_reason"]
    worst = [(k, v) for k, v in er.items() if v["n"] >= MIN_GROUP]
    if worst:
        k, v = worst[0]  # most negative total
        if v["total_ratio"] < 0:
            recs.append(f"Losses concentrate in exit_reason='{k}' "
                        f"({v['n']} trades, win rate {v['win_rate']:.0%}, "
                        f"total {v['total_ratio']:+.4f}). If it's 'stop_loss', the stop "
                        f"may be too tight or entries too early; if 'exit_signal', the "
                        f"exit rule may be cutting winners. Review before changing.")
    # best win cluster
    best = sorted(er.items(), key=lambda kv: kv[1]["total_ratio"], reverse=True)
    best = [(k, v) for k, v in best if v["n"] >= MIN_GROUP and v["total_ratio"] > 0]
    if best:
        k, v = best[0]
        recs.append(f"Most profit comes from exit_reason='{k}' "
                    f"({v['n']} trades, win rate {v['win_rate']:.0%}). Keep this path "
                    f"intact when tuning.")
    # consistently losing pair
    losing_pairs = [(k, v) for k, v in s["by_pair"].items()
                    if v["n"] >= MIN_GROUP and v["total_ratio"] < 0]
    if losing_pairs:
        k, v = losing_pairs[0]
        recs.append(f"Pair {k} is net-negative ({v['n']} trades, {v['total_ratio']:+.4f}). "
                    f"Consider blacklisting it for this strategy (human decision).")
    if s["avg_loss"] and s["avg_win"]:
        rr = abs(s["avg_win"] / s["avg_loss"])
        if rr < 1 and s["win_rate"] < 0.5:
            recs.append(f"Reward:risk {rr:.2f} with sub-50% win rate is a losing combo — "
                        f"winners are smaller than losers AND you win less than half. "
                        f"Needs a wider target or a tighter/earlier exit, not more size.")
    return recs


def run_analysis(log=print):
    """Fetch trades, analyze per strategy, log a report, persist to Postgres.
    Returns {strategy: stats}. Safe if DB is empty/unavailable."""
    by_strategy_names = defaultdict(list)
    for bot, strat in BOT_TO_STRATEGY.items():
        by_strategy_names[strat].append(bot)

    results = {}
    for strat, bots in by_strategy_names.items():
        trades = store.fetch_trades(bots)
        s = analyze(trades)
        results[strat] = s
        log(f"----- TRADE ANALYSIS: {strat} ({', '.join(bots)}) -----")
        if s.get("n", 0) == 0:
            log("  no closed trades recorded yet (history accrues as bots trade).")
            continue
        log(f"  trades={s['n']} win_rate={s['win_rate']:.0%} expectancy={s['expectancy']:+.4f} "
            f"profit_factor={s['profit_factor']} total={s['total_return_ratio']:+.4f} "
            f"best={s['best']:+.4f} worst={s['worst']:+.4f}")
        log(f"  by exit_reason: {s['by_exit_reason']}")
        log(f"  by pair: {s['by_pair']}")
        recs = recommendations(s)
        for r in recs:
            log(f"  • {r}")
        # Persist stats + recommendations + the bots covered, so the dashboard
        # 'Learning' page can render them without recomputing.
        payload = dict(s)
        payload["recommendations"] = recs
        payload["bots"] = bots
        store.store_analysis(strat, payload)
    return results


if __name__ == "__main__":
    run_analysis()
