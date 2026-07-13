#!/usr/bin/env python3
"""
lighter_momentum_bot.py — 🏆 Stock Leaders on LIGHTER stock perps (shadow).

WHAT / WHY (2026-07-13)
  Port of the Alpaca momentum bot (~/Claude/Trading/bot) to Lighter's equity
  perps, per Eamon's ask — same treatment as Index Rider. Rule VERBATIM from
  its strategy.py: a name QUALIFIES while close > SMA200 AND SMA20 > SMA50;
  qualifiers are RANKED by 42-day return; hold the top N equal-slot. Signals
  come from the real market's dailies (Yahoo, keyless); fills/marks/funding
  are Lighter via ShadowBroker.

  UNIVERSE (probed 13 Jul, bar: >=$100k/day AND spread <=6bp): 20 names —
  MU SNDK NVDA META COIN AMD SPY QQQ INTC MSTR HOOD CRCL MSFT MRVL TSLA AMZN
  GOOGL AAPL RKLB NBIS. Lighter lists no sector ETFs, so the Alpaca original's
  defensive-rotation arm doesn't exist here — this port is a concentrated
  growth rotation (mega-tech/semis/crypto-equities) with SPY/QQQ as the
  closest defensive fallbacks. Thin/unlisted names REJECTED at probe: PLTR,
  ORCL, BABA, IBM, TSM, ASML, DELL, NOW, IWM, QCOM, AVGO, ARM, GME (+ the
  no-reference pre-IPO tokens SPACEX/OPENAI etc.).

  CONFIG (backtested 13 Jul — scratchpad momentum_universe_backtest.py, 15y,
  10bps/switch; universe is survivorship-biased so compare VARIANTS not
  levels): top-5 of 20 (top-3 = 48-66% maxDD, too hot; top-8 dilutes),
  lookback 42d (42/63/126 within 2pp — robust, keep the Alpaca default),
  WEEKLY evaluation (vs daily: same CAGR, maxDD 40.7->36.9%, switches
  176->81/yr; monthly re-widens DD to 46.7%). Positions change only at the
  weekly rebalance — plus the catastrophic seatbelt and the daily-loss rail.

  UNVALIDATED on this venue: VENUE=lighter_live REFUSES to start. Longs pay
  funding (~28%apr printed at probe) — the shadow measures the real drag.
  The Alpaca paper bot keeps running as the control arm.

Usage:
    VENUE=lighter_shadow python lighter_momentum_bot.py            # daemon
    VENUE=lighter_shadow python lighter_momentum_bot.py --once     # smoke
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import marks
from venues.safety import SafetyRails

BOT = "equities-momentum"        # row: equities-momentum-lshadow

START_EQUITY = 1000.0
ORDER_USD = float(os.environ.get("MOMO_ORDER_USD", "180"))
TOP_N = int(os.environ.get("MOMO_TOP_N", "5"))
UNIVERSE = os.environ.get(
    "MOMO_SYMBOLS",
    "MU,SNDK,NVDA,META,COIN,AMD,SPY,QQQ,INTC,MSTR,HOOD,CRCL,MSFT,MRVL,TSLA,"
    "AMZN,GOOGL,AAPL,RKLB,NBIS").split(",")
TREND_MA, SLOW_MA, FAST_MA = 200, 50, 20         # Alpaca config.py values
MOMENTUM_LOOKBACK = int(os.environ.get("MOMO_LOOKBACK", "42"))
REBALANCE_DAYS = float(os.environ.get("MOMO_REBALANCE_DAYS", "7"))
CATASTROPHIC_STOP = float(os.environ.get("MOMO_CATASTROPHIC_STOP", "0.15"))
DAILY_LOSS_LIMIT = float(os.environ.get("MOMO_DAILY_LOSS", "0.10"))
LOOP_SECONDS = int(os.environ.get("MOMO_LOOP_SECONDS", "600"))

LOG_FILE = os.environ.get("MOMO_LOG_FILE", "lighter_momentum_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


# --- signal math, verbatim from the Alpaca bot's strategy.py -----------------
def sma(closes, window):
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def momentum(closes, lookback):
    if len(closes) <= lookback:
        return None
    past = closes[-lookback - 1]
    return (closes[-1] / past - 1.0) if past else None


def evaluate(closes):
    if len(closes) < TREND_MA + 1:
        return None
    price = closes[-1]
    fast, slow, trend = sma(closes, FAST_MA), sma(closes, SLOW_MA), sma(closes, TREND_MA)
    mom = momentum(closes, MOMENTUM_LOOKBACK)
    return {"momentum": mom,
            "is_long": price > trend and fast > slow}


def rank_targets(evaluations, max_positions):
    q = [(s, ev) for s, ev in evaluations.items()
         if ev and ev["is_long"] and ev["momentum"] is not None]
    q.sort(key=lambda kv: kv[1]["momentum"], reverse=True)
    return [s for s, _ in q[:max_positions]]


# --- reference dailies (Yahoo; cached; blind -> no rebalance) ----------------
_ref_cache = {}
_REF_TTL_S = 6 * 3600


def ref_closes(symbol):
    hit = _ref_cache.get(symbol)
    if hit and time.time() - hit["ts"] < _REF_TTL_S:
        return hit["closes"]
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol, safe='')}?range=2y&interval=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = json.loads(urllib.request.urlopen(req, timeout=20).read())
        res = raw["chart"]["result"][0]
        cl = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        closes = [float(c) for c in cl if c]
        if closes:
            _ref_cache[symbol] = {"ts": time.time(), "closes": closes}
        return closes or None
    except Exception as e:  # noqa: BLE001
        log.warning("%s: reference unavailable (%s)", symbol, e)
        return (hit or {}).get("closes")


def _record_close(bot_id, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl,
                  reason, notional):
    pnl = float(price_pnl) + float(fund_pnl)
    try:
        store.publish_paper_trade(
            bot_id, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl,
            pnl_pct=(pnl / notional) if notional else None, pair=coin,
            opened_at=datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat()
            if ent_ts else None,
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason="long_" + reason, venue="lighter", shadow=True)
    except Exception:  # noqa: BLE001
        pass


def main():
    p = argparse.ArgumentParser(description="Stock Leaders — Lighter momentum rotation (shadow)")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if mode != "lighter_shadow":
        raise SystemExit("equities-momentum runs VENUE=lighter_shadow ONLY in "
                         "v1 — the stock-perp rotation is unvalidated; the "
                         "shadow record earns (or kills) any go-live.")

    from venues.lighter_client import LighterClient
    from venues.shadow import ShadowBroker
    venue = LighterClient(net="mainnet", with_signer=False)
    bot_id = BOT + "-lshadow"
    broker = ShadowBroker(bot_id, venue, START_EQUITY)
    rails = SafetyRails(BOT, mode)

    symbols = [s for s in UNIVERSE if venue.supports(s)]
    skipped = [s for s in UNIVERSE if s not in symbols]

    meta = {}
    fund_realized = 0.0
    next_reb = 0.0
    n_closed = n_wins = 0
    saved = store.load_state(bot_id)
    if saved and broker.restore_state(saved.get("broker") or {}):
        meta = {str(k): v for k, v in (saved.get("meta") or {}).items()}
        fund_realized = float(saved.get("fund_realized") or 0.0)
        next_reb = float(saved.get("next_reb") or 0.0)
        log.info("restored shadow state: $%.2f, %d open", broker.equity(),
                 broker.open_count())
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    def equity():
        accr = sum((m or {}).get("accrued", 0.0) for m in meta.values())
        return broker.equity() + fund_realized + accr

    def close_pos(s, px, reason):
        nonlocal fund_realized, n_closed, n_wins
        m = meta.get(s) or {}
        sz, ent = broker.pos.get(s, (0.0, 0.0))
        pnl = broker.close(s, px)
        fund_realized += m.get("accrued", 0.0)
        total = pnl + m.get("accrued", 0.0)
        n_closed += 1
        n_wins += 1 if total > 0 else 0
        log.info("CLOSE %s | price %+.2f funding %+.2f [%s]",
                 s, pnl, m.get("accrued", 0.0), reason)
        _record_close(bot_id, s, m.get("entry"), m.get("opened_ts"), px, pnl,
                      m.get("accrued", 0.0), reason, abs(sz) * ent)
        meta.pop(s, None)

    log.info("=" * 64)
    log.info("Stock Leaders (LIGHTER stock-perp rotation, shadow) | %d names "
             "(skipped: %s)", len(symbols), ", ".join(skipped) or "none")
    log.info("qualify close>SMA%d & SMA%d>SMA%d, rank by %dd return, hold "
             "top-%d, rebalance every %.0fd | $%.0f/slot | seatbelt %.0f%% | "
             "loop=%ds", TREND_MA, FAST_MA, SLOW_MA, MOMENTUM_LOOKBACK, TOP_N,
             REBALANCE_DAYS, ORDER_USD, CATASTROPHIC_STOP * 100, LOOP_SECONDS)
    log.info("EVIDENCE-FIRST: rule verbatim from the Alpaca bot (its paper "
             "account = control arm); funding drag measured live. "
             "lighter_live REFUSED in v1.")
    log.info("=" * 64)

    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    if store.load_daily_halt(bot_id, cur_day.isoformat()):
        halted_today = True
        log.warning("daily-loss halt restored — halted for today.")
    day_start_equity = equity()
    last_ts = time.time()

    while True:
        t0 = time.time()
        store.heartbeat(bot_id)
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            day_start_equity = equity()

        eq = equity()
        if (not halted_today and day_start_equity
                and eq <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            confirmed, eq = rails.confirm_daily_loss(
                day_start_equity, eq, DAILY_LOSS_LIMIT, equity)
            if confirmed:
                log.warning("DAILY LOSS LIMIT (%.2f <= %.2f) — flatten + halt.",
                            eq, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                for s in list(meta):
                    px = marks.fresh_mid(venue, s) or meta[s].get("entry")
                    close_pos(s, px, "rail_flatten")

        if halted_today:
            try:
                store.publish(bot_id, status="halted", equity=equity(),
                              pnl_abs=equity() - START_EQUITY,
                              closed_trades=n_closed, wins=n_wins,
                              losses=n_closed - n_wins,
                              extra={"mode": mode, "venue": mode,
                                     "style": "stock-perp-momentum"})
            except Exception:  # noqa: BLE001
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = venue.funding_map()
        except Exception:  # noqa: BLE001
            fund = {}
        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0

        # ---- mark + accrue + seatbelt (every loop, all held) ----
        for s in list(meta):
            px = marks.fresh_mid(venue, s)
            if not px:
                continue
            broker.mark(s, px)
            rate = (fund.get(s) or {}).get("rate")
            if rate is not None:
                szv = abs(broker.pos.get(s, (0.0, 0.0))[0])
                meta[s]["accrued"] = meta[s].get("accrued", 0.0) - rate * szv * px * dt_h
            entry = meta[s].get("entry") or 0.0
            if entry and (px - entry) / entry <= -CATASTROPHIC_STOP:
                close_pos(s, px, "catastrophic_stop")

        # ---- weekly rotation ----
        ranks = None
        if t0 >= next_reb:
            evals, blind = {}, []
            for s in symbols:
                closes = ref_closes(s)
                if closes is None:
                    blind.append(s)
                    continue
                evals[s] = evaluate(closes)
            if blind and len(blind) > len(symbols) // 3:
                log.warning("reference-blind on %d/%d names — rebalance "
                            "deferred one loop", len(blind), len(symbols))
            else:
                want = rank_targets(evals, TOP_N)
                ranks = {s: round((evals[s] or {}).get("momentum") or 0, 4)
                         for s in want}
                for s in list(meta):
                    if s not in want:
                        px = marks.fresh_mid(venue, s) or meta[s].get("entry")
                        close_pos(s, px, "rotated_out")
                for s in want:
                    if s in meta:
                        continue
                    px = marks.fresh_mid(venue, s)
                    if not px:
                        log.warning("%s: no live book — entry skipped", s)
                        continue
                    size = ORDER_USD / px
                    broker.open(s, True, size, px)
                    ent = broker.pos.get(s)
                    meta[s] = {"entry": (ent[1] if ent else px),
                               "opened_ts": t0, "accrued": 0.0}
                    log.info("OPEN %s long $%.0f @ %.4f | mom %+0.1f%% | "
                             "funding %.1f%%apr", s, ORDER_USD, meta[s]["entry"],
                             (ranks.get(s) or 0) * 100,
                             ((fund.get(s) or {}).get("rate") or 0) * 24 * 365 * 100)
                next_reb = t0 + REBALANCE_DAYS * 86400
                log.info("REBALANCE done | holding %s | next %s",
                         ", ".join(sorted(meta)) or "none",
                         datetime.fromtimestamp(next_reb, tz=timezone.utc)
                         .strftime("%d %b %H:%MZ"))

        # ---- publish + persist ----
        accr = sum((m or {}).get("accrued", 0.0) for m in meta.values())
        try:
            store.publish(
                bot_id, status="online", equity=equity(),
                pnl_abs=equity() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": mode, "venue": mode, "style": "stock-perp-momentum",
                       "held": sorted(meta.keys()),
                       **({"last_ranks": ranks} if ranks else {}),
                       "fund_realized": round(fund_realized, 4),
                       "fund_open": round(accr, 4),
                       "next_reb": datetime.fromtimestamp(
                           next_reb, tz=timezone.utc).isoformat() if next_reb else None,
                       "skipped_unlisted": skipped})
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "fund_realized": fund_realized,
                                      "next_reb": next_reb})
        except Exception:  # noqa: BLE001
            pass

        log.info("loop ok | eq $%.2f | held: %s", equity(),
                 ", ".join(sorted(meta)) or "none")
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _supervised():
    while True:
        try:
            main()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            log.exception("unhandled exception — marking row ERROR, restart in 60s")
            try:
                store.set_status(BOT + "-lshadow", "error")
            except Exception:  # noqa: BLE001
                pass
            time.sleep(60)


if __name__ == "__main__":
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
