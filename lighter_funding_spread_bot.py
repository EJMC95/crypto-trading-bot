#!/usr/bin/env python3
"""
lighter_funding_spread_bot.py — ⚖️ Counterweight (cross-sectional funding-spread
factor book, market-neutral, Lighter).

WHAT / WHY (2026-07-12)
  Born from the 12-Jul fleet strategy audit: the fleet is saturated with
  time-series signals on individual coins (two bots literally converged on the
  identical 20-candle-range entry), while NOTHING ranks coins against each
  other. Four cross-sectional factors were pushed through the validation
  doctrine (scripts/backtest_xsect_momentum.py + backtest_xsect_factor_lab.py):
  price momentum, short-term reversal and low-vol all REJECTED (isolated
  sweet spots, one regime carrying the return). FUNDING RANK passed with a
  real plateau: 8/12 configs green in BOTH halves, the whole 72h-lookback row
  green, mirrors negative everywhere, and it survives 3x modelled slippage.

  The book: every REBALANCE_H hours rank the universe by TRAILING MEAN hourly
  funding (LOOKBACK_H window). LONG the K most-NEGATIVE-funding coins (longs
  RECEIVE), SHORT the K most-POSITIVE (shorts RECEIVE) — funding income on
  both legs, ~zero net market exposure. Chosen config = the plateau centre,
  not the flashiest cell: 72h / K=5 / 24h rebalance ($20 clips -> $200 gross):
  full +13.7%, h1 +5.7%, h2 +8.9%, maxDD 11.9%, funding +6.8pp of it.

  Distinct from the live Funding Farmer (threshold-gated |APR|>=40% entries,
  directional, stops/TP, slope gate): Counterweight is ALWAYS-IN, balanced
  long/short by construction, and trades the rank, not the level. Kinship is
  the funding driver — book overlap vs the Farmer is published every loop
  (extra.ff_overlap) so the census can quantify how different it really is.

  UNVALIDATED LIVE. Shadow fills on the real book via ShadowBroker; funding
  accrued hourly from the venue's own funding map, exactly as the backtest.
  VENUE=lighter_live REFUSES to start in v1 — go-live is a separate decision
  on the shadow record (see GO_LIVE_LIGHTER.md).

RISK MODEL (why each gate exists)
  * No per-position stop — the BACKTESTED book has none (positions turn over
    at rebalance; adding unbacktested stops would violate replay fidelity).
    Risk is bounded by balance (long$ == short$), clip size, and the fleet
    daily-loss rail (restrict-only: rails may CUT, never widen).
  * Thin books: fills are the clip's real book VWAP (ShadowBroker crosses the
    spread); the 15bps/side stress case stays positive in both halves.
  * Warm boot: ranking needs LOOKBACK_H of funding history — backfilled from
    HL fundingHistory (the backtest's own data source; rates ~arbitraged) and
    replaced by sampled Lighter rates as they accumulate.
  * Fleet furniture: durable daily-loss halt (debounced), loop heartbeat,
    every fill ledgered to venue_orders, round-trips to paper_trades.

Usage:
    VENUE=lighter_shadow python lighter_funding_spread_bot.py          # daemon
    VENUE=lighter_shadow python lighter_funding_spread_bot.py --once   # smoke
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import venue_context

BOT = "perps-funding-spread"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
COINS = os.environ.get(
    "FUNDSPREAD_COINS",
    "BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,AAVE,WIF,"
    "JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,PYTH,W").split(",")
K = int(os.environ.get("FUNDSPREAD_K", "5"))
LOOKBACK_H = int(os.environ.get("FUNDSPREAD_LOOKBACK_H", "72"))
REBALANCE_H = float(os.environ.get("FUNDSPREAD_REBALANCE_H", "24"))
ORDER_USD = float(os.environ.get("FUNDSPREAD_ORDER_USD", "20"))
DAILY_LOSS_LIMIT = float(os.environ.get("FUNDSPREAD_DAILY_LOSS", "0.05"))
LOOP_SECONDS = int(os.environ.get("FUNDSPREAD_LOOP_SECONDS", "300"))
SAMPLE_SECONDS = 3300           # ~hourly funding samples (one per venue period)
MIN_COVERAGE = LOOKBACK_H // 2  # doctrine: rank only with >=half-window history
# [2026-07-17 BASIS FIX] Lighter quotes an 8h rate — was annualised as hourly
# (8x). Logging-only here, but a log that lies is how the fleet believed the
# venue's floor was 28% apr for four days. See funding_basis.py.
H = funding_basis.periods_per_year('lighter')   # rate -> TRUE APR (logging)
HL_INFO = "https://api.hyperliquid.xyz/info"

LOG_FILE = os.environ.get("FUNDSPREAD_LOG_FILE", "lighter_funding_spread_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def hl_backfill(coin, hours):
    """Bootstrap funding history from HL (the backtest's data source — rates
    are ~arbitraged cross-venue). Returns [(epoch_s, hourly_rate)] or []."""
    try:
        start = int((time.time() - hours * 3600) * 1000)
        body = json.dumps({"type": "fundingHistory", "coin": coin,
                           "startTime": start}).encode()
        req = urllib.request.Request(
            HL_INFO, data=body, headers={"Content-Type": "application/json"})
        rows = json.loads(urllib.request.urlopen(req, timeout=20).read())
        out = {}
        for r in rows or []:
            t = (int(r["time"]) // 3600000) * 3600
            out[t] = float(r["fundingRate"])
        return sorted(out.items())
    except Exception as e:  # noqa: BLE001
        log.warning("HL backfill %s failed: %s", coin, e)
        return []


def fresh_mid(ctx, coin):
    """Live book mid; None = unreadable (skip — never mark on a stale print)."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:  # noqa: BLE001
        return None
    bids = [p for p, s in (book or {}).get("bids") or [] if p > 0 and s > 0]
    asks = [p for p, s in (book or {}).get("asks") or [] if p > 0 and s > 0]
    if not bids or not asks:
        return None
    return (max(bids) + min(asks)) / 2.0


def _record_close(bot, coin, ent_px, ent_ts, exit_px, total_pnl, was_long,
                  reason, shadow):
    pnl_pct = None
    if ent_px:
        pnl_pct = ((exit_px - ent_px) / ent_px) if was_long \
            else ((ent_px - exit_px) / ent_px)
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(total_pnl),
            pnl_pct=pnl_pct, pair=coin, opened_at=oa,
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue="lighter", shadow=shadow)
    except Exception:  # noqa: BLE001
        pass


def main():
    p = argparse.ArgumentParser(
        description="Counterweight — cross-sectional funding-spread factor book")
    p.add_argument("--once", action="store_true", help="Single loop then exit.")
    args = p.parse_args()

    # [2026-07-16 AUDIT] a lost Railway VENUE var silently booted hl_paper
    # (unsuffixed row, HL data under a Lighter-named book). Lighter-shadow
    # is this bot's identity — default to it like the sniper does.
    os.environ.setdefault("VENUE", "lighter_shadow")
    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=False)
    # [v1 GATE] UNVALIDATED LIVE — the shadow record must earn a separate,
    # explicit go-live (own sub-account), like every bot before it.
    if ctx.mode == "lighter_live":
        raise SystemExit("perps-funding-spread is UNVALIDATED live — v1 refuses "
                         "lighter_live. Run VENUE=lighter_shadow to build the "
                         "record; go-live is a separate decision.")
    bot_id = ctx.bot_id
    broker = ctx.broker
    order_usd = ctx.order_usd(ORDER_USD, own=True)   # backtested $20/leg clip
    shadow_tag = ctx.mode == "lighter_shadow"

    meta = {}            # coin -> {is_short, entry, opened_ts, accrued}
    fund_hist = {}       # coin -> [[epoch_s, hourly_rate], ...] (rolling window)
    fund_realized = 0.0
    next_reb = None
    _saved = store.load_state(bot_id)
    if _saved:
        if broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            log.info("restored shadow state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        fund_hist = {str(k): [list(x) for x in v]
                     for k, v in (_saved.get("fund_hist") or {}).items()}
        fund_realized = float(_saved.get("fund_realized") or 0.0)
        next_reb = _saved.get("next_reb")

    n_closed, n_wins = 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    log.info("=" * 64)
    log.info("Counterweight (x-sect FUNDING-SPREAD book) | venue=%s | %d coins",
             ctx.mode, len(COINS))
    log.info("rank=%dh mean funding | LONG bottom-%d / SHORT top-%d | reb every "
             "%.0fh | $%.0f/leg (gross $%.0f) | no per-pos stop (as backtested) "
             "| daily rail %.0f%% | loop=%ds",
             LOOKBACK_H, K, K, REBALANCE_H, order_usd, 2 * K * order_usd,
             DAILY_LOSS_LIMIT * 100, LOOP_SECONDS)
    log.info("doctrine: scripts/backtest_xsect_factor_lab.py (72/5/24 plateau "
             "centre). lighter_live REFUSED in v1.")
    log.info("=" * 64)

    # ---- warm boot: make the ranking possible from loop one ----------------
    now_s = time.time()
    for coin in COINS:
        have = fund_hist.get(coin) or []
        cov = sum(1 for t, _ in have if t >= now_s - LOOKBACK_H * 3600)
        if cov < MIN_COVERAGE:
            bf = hl_backfill(coin, LOOKBACK_H + 6)
            seen = {int(t) for t, _ in have}
            merged = have + [[t, r] for t, r in bf if t not in seen]
            merged.sort()
            fund_hist[coin] = merged[-(LOOKBACK_H + 24):]
    log.info("funding history ready: %d/%d coins with >=%dh coverage",
             sum(1 for c in COINS
                 if sum(1 for t, _ in fund_hist.get(c, [])
                        if t >= now_s - LOOKBACK_H * 3600) >= MIN_COVERAGE),
             len(COINS), MIN_COVERAGE)

    def account_value():
        open_accr = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
        return broker.equity() + fund_realized + open_accr

    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    if store.load_daily_halt(bot_id, cur_day.isoformat()):
        halted_today = True
        log.warning("daily-loss halt restored from state — halted for today.")
    day_start_equity = account_value()
    # [2026-07-16 AUDIT FIX] restore the accrual clock: it reset to
    # boot time on every redeploy, so funding during the gap was never
    # accrued (systematic undercount of the drag/credit this book
    # measures). Gap bounded to 48h so ancient state can't over-accrue.
    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()
    last_sample = 0.0

    def close_position(coin, reason, px=None):
        nonlocal fund_realized, n_closed, n_wins
        m = meta.get(coin) or {}
        px = px or fresh_mid(ctx, coin) or m.get("entry") or 0.0
        price_pnl = broker.close(coin, px)
        accr = m.get("accrued", 0.0)
        fund_realized += accr
        total = price_pnl + accr
        n_closed += 1
        n_wins += 1 if total > 0 else 0
        log.info("CLOSE %s %s $%+.3f (price %+.3f, funding %+.3f) [%s]",
                 coin, "short" if m.get("is_short") else "long", total,
                 price_pnl, accr, reason)
        _record_close(bot_id, coin, m.get("entry"), m.get("opened_ts"), px,
                      total, was_long=not m.get("is_short"), reason=reason,
                      shadow=shadow_tag)
        meta.pop(coin, None)

    while True:
        now = datetime.now(timezone.utc)
        t0 = time.time()
        store.heartbeat(bot_id)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            day_start_equity = account_value()

        equity = account_value()
        if (not halted_today and day_start_equity
                and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            _confirmed, equity = ctx.rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt.",
                            equity, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                for c in list(meta):
                    close_position(c, "rail_flatten")

        if halted_today:
            log.info("halted for today; sleeping.")
            try:
                store.publish(bot_id, status="halted", equity=account_value(),
                              pnl_abs=account_value() - START_EQUITY,
                              closed_trades=n_closed, wins=n_wins,
                              losses=n_closed - n_wins,
                              extra={"mode": ctx.mode, "venue": ctx.mode,
                                     "style": "xsect-funding-spread"})
            except Exception:  # noqa: BLE001
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:  # noqa: BLE001
            log.warning("funding fetch failed (%s); retry next loop.", e)
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        # ---- ~hourly funding sample into the rolling window ----------------
        if t0 - last_sample >= SAMPLE_SECONDS:
            last_sample = t0
            for coin in COINS:
                r = (fund.get(coin) or {}).get("rate")
                if r is not None:
                    hist = fund_hist.setdefault(coin, [])
                    hist.append([int(t0), float(r)])
                    cut = t0 - (LOOKBACK_H + 24) * 3600
                    fund_hist[coin] = [x for x in hist if x[0] >= cut]

        # ---- accrue funding + mark open positions --------------------------
        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0
        for coin, m in list(meta.items()):
            px = fresh_mid(ctx, coin)
            if px is None:
                log.warning("%s: no live book — mark/accrual skipped this loop", coin)
                continue
            broker.mark(coin, px)
            rate = (fund.get(coin) or {}).get("rate")
            if rate is not None:
                notional = abs(broker.szi().get(coin, 0.0)) * px
                m["accrued"] = m.get("accrued", 0.0) + \
                    (1.0 if m.get("is_short") else -1.0) * rate * notional * dt_h

        # ---- rebalance on schedule -----------------------------------------
        if next_reb is None:
            next_reb = t0            # first loop rebalances immediately
        if t0 >= next_reb:
            while next_reb <= t0:
                next_reb += REBALANCE_H * 3600
            floor = t0 - LOOKBACK_H * 3600
            scores = {}
            for coin in COINS:
                if not ctx.supports(coin):
                    continue
                rs = [r for t, r in fund_hist.get(coin, []) if t >= floor]
                if len(rs) >= MIN_COVERAGE:
                    scores[coin] = sum(rs) / len(rs)
            if len(scores) < 2 * K:
                log.warning("rebalance skipped: only %d/%d coins rankable",
                            len(scores), 2 * K)
            else:
                ranked = sorted(scores, key=scores.get)      # most negative first
                want = {c: False for c in ranked[:K]}        # LONG  (receive <0)
                want.update({c: True for c in ranked[-K:]})  # SHORT (receive >0)
                for c in list(meta):
                    if want.get(c) != meta[c].get("is_short"):
                        close_position(c, "rebalance")
                for c, is_short in want.items():
                    if c in meta:
                        continue
                    px = fresh_mid(ctx, c)
                    if px is None:
                        log.warning("%s: no live book — entry skipped", c)
                        continue
                    size = order_usd / px
                    broker.open(c, not is_short, size, px)
                    ent = broker.pos.get(c)
                    meta[c] = {"is_short": is_short,
                               "entry": (ent[1] if ent else px),
                               "opened_ts": t0, "accrued": 0.0}
                    log.info("OPEN %s %s $%.0f @ %.6g (%dh mean %+.1f%% apr)",
                             c, "SHORT" if is_short else "LONG", order_usd,
                             meta[c]["entry"], LOOKBACK_H, scores[c] * H * 100)
                lo = {c: f"{scores[c]*H*100:+.0f}%" for c in ranked[:K]}
                hi = {c: f"{scores[c]*H*100:+.0f}%" for c in ranked[-K:]}
                log.info("REBALANCE done | LONG %s | SHORT %s | next %s",
                         lo, hi, datetime.fromtimestamp(
                             next_reb, tz=timezone.utc).isoformat())

        # ---- census: overlap vs the live Funding Farmer's candidate rule ---
        # (|apr| >= 40% receiving side == what the Farmer would consider). This
        # quantifies how different this book REALLY is — cited at go-live.
        ff_overlap = 0
        for coin, m in meta.items():
            rate = (fund.get(coin) or {}).get("rate")
            if rate is not None and abs(rate) * H >= 0.40 and \
                    (rate > 0) == bool(m.get("is_short")):
                ff_overlap += 1

        # ---- publish + persist ----------------------------------------------
        open_accr = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
        try:
            store.publish(
                bot_id, status="online",
                equity=account_value(),
                pnl_abs=account_value() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode,
                       "style": "xsect-funding-spread",
                       "held": {c: ("S" if m.get("is_short") else "L")
                                for c, m in meta.items()},
                       "fund_realized": round(fund_realized, 4),
                       "fund_open": round(open_accr, 4),
                       "ff_overlap": f"{ff_overlap}/{len(meta)}" if meta else "0/0",
                       "next_reb": datetime.fromtimestamp(
                           next_reb, tz=timezone.utc).isoformat() if next_reb else None})
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "fund_hist": fund_hist,
                                      "fund_realized": fund_realized,
                                      "next_reb": next_reb,
                                      "last_ts": last_ts})
        except Exception:  # noqa: BLE001
            pass

        log.info("loop ok | book %d/%d (%s) | eq $%.2f (funding %+.2f real "
                 "%+.2f open) | next reb %s",
                 broker.open_count(), 2 * K,
                 ", ".join(f"{c}:{'S' if m.get('is_short') else 'L'}"
                           for c, m in sorted(meta.items())) or "empty",
                 account_value(), fund_realized, open_accr,
                 datetime.fromtimestamp(next_reb, tz=timezone.utc).strftime("%d %H:%MZ")
                 if next_reb else "-")
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _supervised():
    """Unhandled exception -> log, mark row ERROR, restart in 60s (state
    re-hydrates). SystemExit/Ctrl-C pass through. (GO-GREEN furniture.)"""
    while True:
        try:
            main()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            log.exception("unhandled exception — marking row ERROR, restarting in 60s")
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
