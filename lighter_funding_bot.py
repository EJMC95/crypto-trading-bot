#!/usr/bin/env python3
"""
lighter_funding_bot.py — Yield Harvester (Lighter, DIRECTIONAL funding capture).

WHAT THIS IS — AND HONESTLY IS NOT (2026-07-10)
  Lighter is a perp-only venue, so there is NO same-coin hedge on it: a single
  venue cannot run a delta-neutral funding carry. This bot therefore captures
  funding DIRECTIONALLY — it takes the funding-RECEIVING side of a hot perp
  (SHORT when funding is positive / longs are crowded, LONG when negative) and
  collects Lighter's (zero-fee) funding while it stays hot. That means it carries
  PRICE RISK the hedge would have removed. The thesis that makes it more than a
  coin-flip: extreme funding marks crowded positioning that tends to mean-revert,
  so the funding-receiving side is also the contrarian side. The thesis that
  could break it: a strong trend runs the position over before funding pays.

  Because it is directional, the NON-NEGOTIABLE risk control is a HARD PRICE STOP
  on every position (HARD_STOP), evaluated against a FRESH live-book mid (never a
  stale mark). Supporting controls: a book-spread liquidity gate at entry (thin
  Lighter perps — WEN cost 870bps round-trip in the shadow evidence — are kept
  out), a post-stop cooldown (no instant re-entry in a trend), small clips, a
  funding-decay exit, and the fleet's notional / daily-loss / kill-switch rails.

EXECUTION / SAFETY — reuses the venue layer (venues/), same path Trail Blazer and
Bounce Catcher go live on:
  VENUE=hl_paper        (default) paper sim on HL data — offline-safe smoke.
  VENUE=lighter_shadow  models fills on the LIVE Lighter book, logs venue_orders,
                        NEVER sends an order — the validation mode.
  VENUE=lighter_live    REAL orders on Lighter. venues/safety.py REFUSES to start
                        unless REAL_MONEY_KILL=DISARMED_I_UNDERSTAND and a per-bot
                        notional cap env are BOTH set; the kill switch is re-checked
                        every loop and flattens on arm. Keys/disarm/deposit are the
                        operator's — this file never sets them.

Usage:
    python lighter_funding_bot.py           # dry-run forever
    python lighter_funding_bot.py --once     # single scan then exit (smoke test)
"""
import argparse
import logging
import math
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import marks, venue_context

BOT = "perps-funding-lighter"
H = 24 * 365

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
ORDER_USD = float(os.environ.get("FUNDING_ORDER_USD", "25"))   # small: directional
MAX_OPEN_POSITIONS = int(os.environ.get("FUNDING_MAX_OPEN", "6"))
MAX_NEW_PER_LOOP = int(os.environ.get("FUNDING_MAX_NEW_PER_LOOP", "2"))

ENTER_APR = float(os.environ.get("FUNDING_ENTER_APR", "0.40"))  # enter when |apr|>=40%
EXIT_APR = float(os.environ.get("FUNDING_EXIT_APR", "0.15"))    # leave when it cools
PERSIST_H = float(os.environ.get("FUNDING_PERSIST_H", "4"))     # hot this long first
MAX_HOLD_H = float(os.environ.get("FUNDING_MAX_HOLD_H", "72"))  # recycle after 3d
MIN_VOL = float(os.environ.get("FUNDING_MIN_VOL", "10e6"))      # 24h turnover floor
MAX_SPREAD_BPS = float(os.environ.get("FUNDING_MAX_SPREAD_BPS", "20"))  # book-spread gate

# Directional risk controls, TUNED on scripts/backtest_directional_funding.py
# (real HL funding+price, 150d, 30 coins). Key finding: funding capture is real
# (+) but directional price risk eats it (-), so the strategy is only ~break-even.
# A WIDE stop + TIGHT take-profit was the least-bad / most robust config — a tight
# stop whipsaws out on noise before funding + mean-reversion pay, LOSING more.
HARD_STOP = float(os.environ.get("FUNDING_HARD_STOP", "0.10"))     # 10% — wide (anti-whipsaw)
TAKE_PROFIT = float(os.environ.get("FUNDING_TAKE_PROFIT", "0.04"))  # 4% — lock the reversion pop
DAILY_LOSS_LIMIT = float(os.environ.get("FUNDING_DAILY_LOSS", "0.05"))
STOP_COOLDOWN_H = float(os.environ.get("FUNDING_STOP_COOLDOWN_H", "12"))  # quarantine after a stop
BLIND_STOP_MISSES = int(os.environ.get("FUNDING_BLIND_STOP_MISSES", "3"))  # live fail-safe

# ---- position SCANNER (2026-07-11) — choose the best RISK-ADJUSTED positions, not
# just the hottest funder. Backtested (scripts/backtest_scanner.py, real HL funding+
# price, 150d, 6-slot portfolio): a realized-vol VETO + fresh-adverse-trend VETO + a
# widened entry gate lift net +155% and ret/DD 2.0->7.4, robust across both halves +
# OOS. HONEST CAVEAT: much of that gain is directional MEAN-REVERSION (regime-
# dependent), not extra funding — the vol veto (skip coins whose price is convulsing
# too hard to hold past the stop) is the DURABLE piece. All existing SAFETY gates stay
# as a floor; the scanner only refines WHICH survivors get the scarce slots. The
# cross-venue (_bench) + book-VWAP-slippage layer can't be backtested from HL history
# -> shipped as LIVE-ONLY, logged to venue_orders for the shadow ledger to validate.
# Toggle SCAN=off restores the exact legacy raw-|APR| selection (old-vs-new + rollback).
SCAN_ENABLED = os.environ.get("SCAN", "on").strip().lower() not in ("off", "0", "false", "no")
SCAN_VETO_VOL = float(os.environ.get("SCAN_VETO_VOL", "0.015"))  # skip 1h realized vol > 1.5%/hr
SCAN_VETO_ADVERSE = float(os.environ.get("SCAN_VETO_ADVERSE", "0.05"))  # skip fresh >5% adverse move
SCAN_MAX_SLIP_BPS = float(os.environ.get("SCAN_MAX_SLIP_BPS", "25"))    # clip VWAP-slip gate (deeper than 20 TOB)
# CANDLE-scan only the top-N by |apr|*bench. This is a deliberate governor bound: on a
# cold cache (restart) the deep-scan bursts up to SCAN_DEEP_MAX candle fetches against the
# ~21 weight/min bucket, so 15 leaves headroom for order/close txs. TRADE-OFF (reviewed,
# low-sev): in a large live pool (~215 markets) this prefilter can miss a lower-|apr| but
# higher-quality (low-vol) coin the score would have preferred — validate on the expanded-
# universe backtest + shadow ledger before raising it. The 30-coin backtest rarely has >15
# eligible, so shipped ~= backtested there.
SCAN_DEEP_MAX = int(os.environ.get("SCAN_DEEP_MAX", "15"))
SCAN_BOOK_PROBE = int(os.environ.get("SCAN_BOOK_PROBE", "5"))   # BOOK-fetch only the top-N finalists (governor)
SCAN_VOL_LOOKBACK_H = int(os.environ.get("SCAN_VOL_LOOKBACK_H", "24"))
SCAN_MOM_LOOKBACK_H = int(os.environ.get("SCAN_MOM_LOOKBACK_H", "6"))
# (candle features are cached per CLOSED hourly bar — see _candle_features — so they
# refresh the moment a new bar closes and are reused free within the hour; no TTL knob.)

# Entry gate. The DEFAULT KEEPS THE TUNED 0.40 SAFETY GATE — the scanner's mandate is to
# pick better AMONG the survivors (veto stop-out traps + risk-adjusted rank), NOT to
# loosen the floor. Widening to ~0.25 lifts the in-cache net far more (+155% vs +53%) but
# partly as a flat-slippage backtest artifact, ~doubles churn, and changes a SAFETY gate —
# so it is OPT-IN (set SCAN_ENTER=0.25) and should be shadow-validated first. Defaults to
# ENTER_APR = no widening. (Backtest: scripts/backtest_scanner.py.)
SCAN_ENTER = float(os.environ.get("SCAN_ENTER", str(ENTER_APR)))
ENTER_GATE = SCAN_ENTER if SCAN_ENABLED else ENTER_APR

# ---- funding-SLOPE entry gate (2026-07-11) — only enter while the rate is
# still BUILDING (|apr| >= |apr LOOKBACK_H ago|). Backtested on the 150d
# portfolio sim (scripts/backtest_funding_leverage.py): at the live 2x config
# baseline +1.3% -> +8.4% with LOWER maxDD (16.5% -> 12.5%), positive in BOTH
# halves; the mirror rule (enter only on rollover) is symmetrically negative
# (-13.3%) — the effect is causal, not noise. 1h lookback chosen for
# ROBUSTNESS: 3h scores higher in-cache (+24.6%) but sits next to a sign FLIP
# at 4h — a sweet-spot overfit trap. FAIL-OPEN when history is missing
# (restart gap ~1h) — matches the backtest's handling exactly.
SLOPE_GATE = os.environ.get("FUNDING_SLOPE_GATE", "on").strip().lower() \
    not in ("off", "0", "false", "no")
SLOPE_LOOKBACK_H = float(os.environ.get("FUNDING_SLOPE_LOOKBACK_H", "1"))

# ---- coin-quality VETO (2026-07-11 SELF-CORRECT, RESTRICT-ONLY) — skip entry
# on coins the fleet's OWN measured evidence flags as toxic (slip > 15bps or
# stop-rate >= 50%, computed by market_context.py from venue_orders /
# paper_trades). HARD PRINCIPLE: automated evidence only ever REMOVES
# candidates — it can never widen a gate, raise size, or add leverage. Fails
# open (no veto state -> no vetoes). Toggle: FUNDING_QUALITY_VETO=off.
QUALITY_VETO = os.environ.get("FUNDING_QUALITY_VETO", "on").strip().lower() \
    not in ("off", "0", "false", "no")

LOOP_SECONDS = int(os.environ.get("FUNDING_LOOP_SECONDS", "300"))

LOG_FILE = os.environ.get("FUNDING_LOG_FILE", "funding_lighter_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _slope_ref(hist, now_ts, lookback_s):
    """Newest funding-apr sample at least lookback_s old (staleness-bounded to
    3x lookback). None = not enough history -> the gate FAILS OPEN."""
    if not hist:
        return None
    ref = None
    for ts, apr in hist:                      # oldest -> newest
        age = now_ts - ts
        if lookback_s <= age <= 3 * lookback_s:
            ref = apr                          # keep the newest qualifying
        elif age < lookback_s:
            break
    return ref


def _mctx_slice(mctx, coin):
    """[2026-07-11 INSTRUMENT-FIRST] Compact market-context snapshot attached to
    every ledgered ENTRY (see market_context.py). Validation dataset only —
    nothing here gates a trade until a factor passes the both-halves bar."""
    c = (mctx.get("coins") or {}).get(coin) or {}
    return {"heat": mctx.get("heat_mean_apr"), "btc_vol": mctx.get("btc_vol_1h"),
            "oi_chg_1h": c.get("oi_chg_1h"), "oi_chg_24h": c.get("oi_chg_24h"),
            "premium_bps": c.get("premium_bps"), "liq_1h": c.get("liq_1h")}


def fresh_mid(ctx, coin):
    """Current mid from the LIVE book, or None if unavailable. NEVER falls back to
    the funding-map mark — that is a last-trade price frozen at client construction
    and using it on the stop path would silently freeze the stop while the real
    price runs away. Callers MUST treat None as 'cannot evaluate risk here'.
    Shared impl: venues/marks.py (also sorts the unsorted REST-snapshot
    fallback, which this local copy did not)."""
    return marks.fresh_mid(ctx.venue, coin)


def book_spread_bps(ctx, coin):
    """Top-of-book spread in bps from the live book, or None if unavailable."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        return None
    if book and book.get("bids") and book.get("asks"):
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        mid = (bid + ask) / 2.0 if (bid and ask) else 0.0
        if mid:
            return (ask - bid) / mid * 1e4
    return None


# ============================ POSITION SCANNER ==============================
# Chooses the best RISK-ADJUSTED candidates for the scarce slots (see the SCAN_*
# config block for the thesis + backtest). Cheap funding-only prefilter runs in the
# main loop; these helpers do the deep-scan (candles + one book fetch) on the top-N.
_feat_cache = {}   # coin -> (ts, {vol, ret_mom}); candle features are slow-moving


def _candle_features(ctx, coin):
    """Realized vol + short-horizon momentum from ~1d of CLOSED 1h candles. Returns
    {'vol','ret_mom'} or None if unavailable — None means 'cannot assess price risk',
    and the caller MUST skip the candidate (never enter blind on the vol veto).
    Definitions match scripts/backtest_scanner.py EXACTLY: vol = sample stdev of the
    last SCAN_VOL_LOOKBACK_H hourly returns; ret_mom = the SCAN_MOM_LOOKBACK_H-hour
    close-to-close return.

    [review 2026-07-11] Two fixes so live == backtested + no look-ahead:
      * DROP the forming (current-hour) bar — candles() returns it as the last row;
        including it would compute vol/momentum off a partial bar (the backtest uses
        closed bars only) and read the current price into the entry feature.
      * Cache is keyed on the most-recent CLOSED hour, not a wall-clock TTL, so it
        refreshes the instant a new bar closes (a fresh vol spike is picked up next
        loop, not up to ~50min later) and is otherwise reused free within the hour.
    Rows are sorted chronologically (don't trust API order) before differencing."""
    now = time.time()
    last_closed = int(now // 3600) * 3600 - 3600     # open-ts of the newest CLOSED hour (sec)
    hit = _feat_cache.get(coin)
    if hit and hit[0] == last_closed:
        return hit[1]
    need_h = max(SCAN_VOL_LOOKBACK_H, SCAN_MOM_LOOKBACK_H) + 4
    try:
        end_ms = int(now * 1000)
        rows = ctx.venue.candles(coin, "1h", end_ms - need_h * 3600 * 1000, end_ms)
    except Exception:
        return None
    bars = []
    for c in rows or []:
        try:
            t_s = int(c["t"]) // 1000
            cl = float(c["c"])
        except (KeyError, TypeError, ValueError):
            continue
        if t_s > last_closed:            # drop the forming (current-hour) bar
            continue
        bars.append((t_s, cl))
    bars.sort()                          # chronological; API order not trusted
    closes = [cl for _, cl in bars]
    if len(closes) < SCAN_VOL_LOOKBACK_H + 1:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0
            for i in range(1, len(closes)) if closes[i - 1]]
    w = rets[-SCAN_VOL_LOOKBACK_H:]
    mean = sum(w) / len(w)
    vol = math.sqrt(sum((r - mean) ** 2 for r in w) / (len(w) - 1)) if len(w) > 1 else 0.0
    ret_mom = (closes[-1] / closes[-1 - SCAN_MOM_LOOKBACK_H] - 1.0) \
        if len(closes) > SCAN_MOM_LOOKBACK_H and closes[-1 - SCAN_MOM_LOOKBACK_H] else 0.0
    feats = {"vol": vol, "ret_mom": ret_mom}
    _feat_cache[coin] = (last_closed, feats)
    return feats


def book_metrics(ctx, coin, order_usd):
    """ONE orderbook fetch -> {mid, spread_bps, buy_slip, sell_slip}. buy/sell_slip is
    the VWAP slippage (bps, >=0) to fill an `order_usd` clip walking the asks/bids;
    None for a side without enough depth for the clip. Replaces the old
    book_spread_bps + fresh_mid DOUBLE fetch on the entry path (governor efficiency)."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        return None
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return None
    # sort defensively best-first — the ws cache is pre-sorted but the REST-snapshot
    # fallback (the Railway norm, ws is CDN-blocked) is NOT, and the VWAP walk below
    # would be wrong on an unordered book. [review 2026-07-11]
    bids = sorted(bids, key=lambda x: -x[0])     # highest bid first
    asks = sorted(asks, key=lambda x: x[0])      # lowest ask first
    if not bids[0][0] or not asks[0][0]:
        return None
    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2.0

    def vwap_slip(levels, adverse_up):
        need, cost, base = order_usd, 0.0, 0.0
        for px, sz in levels:
            if px <= 0 or sz <= 0:
                continue
            take = min(need, px * sz)
            cost += take
            base += take / px
            need -= take
            if need <= 1e-9:
                break
        if need > 1e-9 or base <= 0:
            return None                      # book too thin for the clip
        vwap = cost / base
        return (vwap - mid) / mid * 1e4 if adverse_up else (mid - vwap) / mid * 1e4

    # near-touch notional depth within +/-0.5% of mid (for the imbalance tiebreak)
    band = mid * 0.005
    bid_depth = sum(px * sz for px, sz in bids if px >= mid - band)
    ask_depth = sum(px * sz for px, sz in asks if px <= mid + band)
    return {"mid": mid, "spread_bps": (ask - bid) / mid * 1e4,
            "buy_slip": vwap_slip(asks, True), "sell_slip": vwap_slip(bids, False),
            "bid_depth": bid_depth, "ask_depth": ask_depth}


def cross_venue_mult(f):
    """Bounded [0.5, 1.2] score multiplier from cross-venue funding agreement
    (f['_bench']: binance/bybit/hyperliquid). Benches confirming Lighter's sign =
    structural crowding (reward); a Lighter-only extreme = local dislocation (demote).
    LIVE-ONLY (no _bench history to backtest); never a hard gate, never re-admits a
    vetoed coin — it only re-orders survivors. Returns 1.0 when there is no bench data
    (e.g. hl_paper)."""
    rate = f.get("rate") or 0.0
    bench = f.get("_bench") or {}
    if not rate or not bench:
        return 1.0
    total = sum(1 for v in bench.values() if v)
    if not total:
        return 1.0
    agree = sum(1 for v in bench.values() if v and (v > 0) == (rate > 0))
    return 0.5 + 0.7 * (agree / total)       # 0 agree -> 0.5, all agree -> 1.2


def scan_candidates(ctx, prelim, order_usd, log):
    """Three governor-aware stages; returns finalists ranked best-first as
    (coin, f, apr, is_short, book_metrics, evidence). Fetch-cost is bounded so the
    scan can't drain the ~21 weight/min Lighter budget shared with order txs + sibling
    bots (on Railway the ws is CDN-blocked, so EVERY orderbook() costs 1 token):

      A. FREE prefilter — rank the whole eligible pool by |apr| x cross-venue mult
         (both already in the funding_map row; 0 extra tokens). Steer the scarce
         candle/book budget toward structurally-crowded names.
      B. CANDLE deep-scan the top SCAN_DEEP_MAX (cached ~50min): VETO stop-out traps
         (vol / adverse-trend) and score survivors by |APR| x bounded risk discounts
         x cross-venue. This is the BACKTESTED core (scripts/backtest_scanner.py).
      C. BOOK-probe only the top SCAN_BOOK_PROBE survivors (ONE fetch each): spread +
         clip-slippage gate + a small book-imbalance tiebreak. Live-only overlay."""
    # STAGE A — free cross-venue-weighted prefilter over the whole eligible pool
    ranked_pre = sorted(prelim, key=lambda cfa: -abs(cfa[2]) * cross_venue_mult(cfa[1]))

    # STAGE B — candle veto + core score on the top SCAN_DEEP_MAX (cached)
    survivors = []
    for coin, f, apr in ranked_pre[:SCAN_DEEP_MAX]:
        feats = _candle_features(ctx, coin)
        if feats is None:
            log.info("%s SCAN_SKIP no-candles (risk unverifiable)", coin)
            continue
        is_short = apr > 0                       # funding>0 -> longs pay -> we SHORT
        adverse = feats["ret_mom"] if is_short else -feats["ret_mom"]
        if feats["vol"] > SCAN_VETO_VOL:
            log.info("%s VETO vol %.2f%%/h > %.2f%%", coin, feats["vol"] * 100,
                     SCAN_VETO_VOL * 100)
            continue
        if adverse > SCAN_VETO_ADVERSE:
            log.info("%s VETO adverse-trend %+.1f%% (fresh move into our stop)",
                     coin, adverse * 100)
            continue
        vol_disc = 1.0 / (1.0 + (feats["vol"] / SCAN_VETO_VOL) ** 2)  # (0,1], .5 at veto
        adv_disc = math.exp(-6.0 * max(0.0, adverse))                 # (0,1]
        xv = cross_venue_mult(f)                                      # [0.5,1.2]
        core = abs(apr) * vol_disc * adv_disc * xv
        survivors.append((core, coin, f, apr, is_short, feats, xv, adverse))
    survivors.sort(key=lambda x: -x[0])

    # STAGE C — book-probe only the top finalists (bounded token spend)
    finalists = []
    for core, coin, f, apr, is_short, feats, xv, adverse in survivors[:SCAN_BOOK_PROBE]:
        bm = book_metrics(ctx, coin, order_usd)
        if bm is None or bm["spread_bps"] > MAX_SPREAD_BPS:
            log.info("%s SPREAD/BOOK_SKIP (%s)", coin,
                     f"{bm['spread_bps']:.0f}bps" if bm else "no book")
            continue
        slip = bm["sell_slip"] if is_short else bm["buy_slip"]
        if slip is None or slip > SCAN_MAX_SLIP_BPS:
            log.info("%s VETO clip-slip %s bps > %.0f", coin,
                     f"{slip:.0f}" if slip is not None else "thin", SCAN_MAX_SLIP_BPS)
            continue
        # adverse near-touch imbalance: book leaning INTO our stop (short hurt by bids,
        # long by asks). Small tiebreak only — noisy/spoofable, never a gate.
        tot = bm["bid_depth"] + bm["ask_depth"]
        imb = (((bm["bid_depth"] - bm["ask_depth"]) if is_short
                else (bm["ask_depth"] - bm["bid_depth"])) / tot) if tot > 0 else 0.0
        final = core * (1.0 - 0.30 * max(0.0, imb))
        ev = {"score": round(final, 4), "vol": round(feats["vol"], 5),
              "adverse": round(adverse, 4), "slip_bps": round(slip, 1),
              "xv": round(xv, 2), "imb": round(imb, 2)}
        finalists.append((final, coin, f, apr, is_short, bm, ev))
    finalists.sort(key=lambda x: -x[0])
    return [(c, f, apr, is_short, bm, ev)
            for _, c, f, apr, is_short, bm, ev in finalists]


def _record_close(bot, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl, was_long,
                  reason, order_usd=ORDER_USD, venue=None, shadow=None):
    """Mirror a realized directional funding trade to the paper_trades ledger.
    pnl_abs = price P&L + funding accrued; pnl_pct is on the deployed clip."""
    pnl = float(price_pnl) + float(fund_pnl)
    pnl_pct = (pnl / (order_usd or 1.0)) if ent_px else None
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl, pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue=venue, shadow=shadow)
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="Yield Harvester — Lighter directional funding")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=("--live" in sys.argv))
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(ORDER_USD)
    max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Cumulative realized P&L survives restarts via the ledger.
    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    # Per-open bookkeeping the venue doesn't hold: is_short, entry, opened_ts,
    # accrued funding. Persisted so a redeploy doesn't reset the max-hold clock.
    meta = {}          # coin -> {is_short, entry, opened_ts, accrued}
    rate_hist = {}     # coin -> deque[(ts, apr)] — slope-gate memory (in-process)
    hot_since = {}     # coin -> ts |apr| first >= ENTER_APR
    cooldown = {}      # coin -> ts until which re-entry is blocked (post-stop)
    miss = {}          # coin -> consecutive fresh-price misses (live fail-safe)
    fund_realized = 0.0  # dry_run only: cumulative realized funding (price P&L is in broker)

    if dry_run:
        _saved = store.load_state(bot_id)
        if _saved and broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            fund_realized = float(_saved.get("fund_realized") or 0.0)
            log.info("restored paper state: equity $%.2f, %d open", broker.equity(),
                     broker.open_count())
    else:
        # Live: restore open-position meta so opened_ts (max-hold clock) survives
        # a redeploy instead of resetting to now.
        _live = store.load_state(bot_id + ":live") or {}
        meta = {str(k): v for k, v in (_live.get("meta") or {}).items()}
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None

    log.info("=" * 64)
    log.info("Yield Harvester (Lighter DIRECTIONAL funding) | venue=%s (%s)",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS")
    log.info("enter |apr|>=%.0f%% persist %.0fh, exit<%.0f%% | HARD STOP %.0f%% / TP %.0f%% "
             "| $%.0f x max %d | vol>=$%.0fM spread<=%.0fbps | loop=%ds", ENTER_GATE * 100,
             PERSIST_H, EXIT_APR * 100, HARD_STOP * 100, TAKE_PROFIT * 100, order_usd,
             max_open, MIN_VOL / 1e6, MAX_SPREAD_BPS, LOOP_SECONDS)
    if SCAN_ENABLED:
        log.info("SCANNER on: candle-scan top %d, book-probe top %d | VETO vol>%.1f%%/h | "
                 "adverse>%.0f%% | clip-slip>%.0fbps; rank |apr| x risk-discounts x "
                 "cross-venue. gate=%.0f%%%s", SCAN_DEEP_MAX, SCAN_BOOK_PROBE,
                 SCAN_VETO_VOL * 100, SCAN_VETO_ADVERSE * 100, SCAN_MAX_SLIP_BPS,
                 ENTER_GATE * 100,
                 " (WIDENED — opt-in; shadow-validate)" if SCAN_ENTER < ENTER_APR else "")
        log.info("Scanner edge is largely directional MEAN-REVERSION (regime-dependent); "
                 "the vol veto is the durable piece. Backtest: scripts/backtest_scanner.py.")
    else:
        log.info("SCANNER off (SCAN=off): legacy raw-|apr| selection.")
    log.info("DIRECTIONAL — not delta-neutral; price risk bounded by the hard stop.")
    log.info("SLOPE GATE %s: enter only while |apr| still >= its level %gh ago "
             "(building, not rolling over) — validated both-halves on the 150d "
             "portfolio sim; fails open for ~1h after restart.",
             "on" if SLOPE_GATE else "OFF", SLOPE_LOOKBACK_H)
    log.info("=" * 64)

    def account_value():
        return broker.equity() if dry_run else ctx.venue.account_value()

    def positions():
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        return ctx.venue.positions()

    def _flatten_all(reason):
        """Emergency flatten that MIRRORS normal-close bookkeeping (ledger + counters
        + meta pop) so forensic reconstruction stays consistent with account equity."""
        nonlocal n_closed, n_wins
        try:
            live_pos = ctx.venue.positions()
        except Exception as e:
            log.error("flatten scan failed: %s", e)
            return
        for c in list(live_pos):
            held = (live_pos.get(c, {}) or {}).get("size", 0.0) or 0.0
            if not held:
                continue
            m = meta.get(c) or {}
            is_short = m.get("is_short", held < 0)
            entry = m.get("entry") or (live_pos.get(c, {}) or {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or time.time()
            px = fresh_mid(ctx, c) or entry
            try:
                ctx.venue.market_close(c)
            except Exception as e:
                log.error("flatten %s: %s", c, e)
                continue
            price_pnl = abs(held) * ((px - entry) if not is_short else (entry - px))
            n_closed += 1
            n_wins += 1 if price_pnl > 0 else 0
            _record_close(bot_id, c, entry, opened_ts, px, price_pnl, m.get("accrued", 0.0),
                          was_long=not is_short, reason=reason, order_usd=order_usd,
                          venue=venue_tag, shadow=shadow_tag)
            try:
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"), shadow=shadow_tag,
                    coin=c, side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=px, px_fill=px, raw={"reason": reason, "leg": "close"})
            except Exception:
                pass
            meta.pop(c, None)
            hot_since.pop(c, None)

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("account value unreadable (%s); loss-limit waits.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    # [2026-07-11 DURABLE HALT] a tripped daily-loss halt survives restarts —
    # the memory-only flag meant a same-day redeploy silently resumed trading.
    _halt = store.load_daily_halt(bot_id, cur_day.isoformat())
    if _halt:
        halted_today = True
        day_start_equity = _halt.get("day_start_equity") or day_start_equity
        log.warning("daily-loss halt restored from state — halted for the rest of today.")
    last_ts = time.time()

    while True:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            try:
                day_start_equity = account_value()
            except Exception:
                pass

        # kill switch (live) — flatten every held coin and halt on arm.
        if not dry_run and ctx.rails.kill_check():
            log.error("REAL_MONEY_KILL armed mid-run — flatten + halt.")
            halted_today = True
            _flatten_all("kill_switch")

        try:
            equity = account_value()
        except Exception as e:
            log.warning("account value unavailable: %s", e)
            equity = None
        # [2026-07-11 LATE BASELINE] if the boot/day-roll capture failed (venue
        # down, or the equity guard vetoed a dislocated print) the rail used to
        # stay OFF all day. Adopt the first credible read instead.
        if day_start_equity is None and equity is not None:
            day_start_equity = equity
            log.warning("day-start equity adopted late: %.2f", equity)

        _fleet_loss = (not dry_run and ctx.rails.daily_loss_hit(day_start_equity, equity))
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT) or _fleet_loss)):
            # [2026-07-11 RAIL DEBOUNCE] one dislocated equity print sold the
            # book into the dislocation (-5.9% real). Confirm on a second read
            # (SafetyRails.confirm_daily_loss — shared, FAIL-SAFE: unreadable
            # confirm counts as confirmed). Adopt the fresher read either way
            # so a phantom print can't leak into published equity or the
            # persisted live P&L baseline.
            _confirmed, equity = ctx.rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt.",
                            equity, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                if not dry_run:
                    _flatten_all("daily_loss")

        if halted_today:
            log.info("halted for today; sleeping.")
            # [2026-07-11 HALT HEARTBEAT] keep the dashboard row fresh while
            # halted — the early `continue` skipped the publish below, so a
            # halted bot looked DEAD (stale row) instead of HALTED.
            try:
                if dry_run:
                    _open_fund = sum((meta.get(c) or {}).get("accrued", 0.0)
                                     for c in meta)
                    _hb_eq = broker.equity() + fund_realized + _open_fund
                    _hb_pnl = _hb_eq - START_EQUITY
                else:
                    _hb_eq = equity
                    _hb_pnl = (equity - live_baseline) if (equity is not None
                                                           and live_baseline is not None) else None
                store.publish(
                    bot_id, status="paper" if ctx.mode == "hl_paper" and dry_run
                    else "halted",
                    equity=_hb_eq, pnl_abs=_hb_pnl,
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": ctx.mode, "venue": ctx.mode,
                           "style": "directional-funding",
                           "held": {c: ("S" if (meta.get(c) or {}).get("is_short") else "L")
                                    for c in meta}})
            except Exception:
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:
            log.warning("funding fetch failed (%s); retry next loop.", e)
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            pos = positions()
        except Exception as e:
            log.warning("positions unreadable: %s", e)
            if not dry_run:
                # Acting on a phantom-empty set would zero open_now AND the cap
                # input, defeating max_open and the notional cap — skip the loop.
                if args.once:
                    break
                time.sleep(LOOP_SECONDS)
                continue
            pos = {}

        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0

        # [2026-07-11 INSTRUMENT-FIRST] one cheap state read per loop; the
        # snapshot rides along on every entry's ledger row via _mctx_slice.
        try:
            _mctx = store.load_state("market-context") or {}
        except Exception:  # noqa: BLE001
            _mctx = {}
        try:
            _vetoes = ((store.load_state("coin-vetoes") or {}).get("coins") or {}) \
                if QUALITY_VETO else {}
        except Exception:  # noqa: BLE001
            _vetoes = {}

        # [2026-07-11 SLOPE GATE] rolling in-process funding history (apr units)
        # feeding the building-vs-rolling-over entry gate. Restart loses ~1h of
        # history -> gate fails open, exactly as backtested.
        for _c, _f in fund.items():
            _r = _f.get("rate")
            if _r is not None:
                rate_hist.setdefault(_c, deque(maxlen=64)).append((t0, _r * H))

        # ---- manage open positions (held coins may no longer be hot) ----
        held_coins = set(pos) | set(meta)
        opened_this_loop = 0
        for coin in list(held_coins):
            held = pos.get(coin, {}).get("size", 0.0)
            if not held:
                meta.pop(coin, None)
                continue
            f = fund.get(coin) or {}
            rate = f.get("rate")
            apr = (rate * H) if rate is not None else None
            m = meta.get(coin) or {}
            is_short = m.get("is_short", held < 0)
            entry = m.get("entry") or pos.get(coin, {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or t0

            px = fresh_mid(ctx, coin)
            if px is None:
                # No live book -> the hard stop cannot be evaluated. Never pretend
                # with a stale mark. Log; in live, fail-safe flatten after N misses.
                miss[coin] = miss.get(coin, 0) + 1
                log.warning("%s: no live book (%d) — hard stop unverifiable", coin, miss[coin])
                if not dry_run and miss[coin] >= BLIND_STOP_MISSES:
                    log.error("%s: stop unverifiable %dx — fail-safe flatten", coin, miss[coin])
                    try:
                        ctx.venue.market_close(coin)
                        _record_close(bot_id, coin, entry, opened_ts, entry, 0.0,
                                      m.get("accrued", 0.0), was_long=not is_short,
                                      reason="stop_blind", order_usd=order_usd,
                                      venue=venue_tag, shadow=shadow_tag)
                        n_closed += 1
                        meta.pop(coin, None)
                        hot_since.pop(coin, None)
                        miss.pop(coin, None)
                    except Exception as e:
                        log.error("fail-safe close %s: %s", coin, e)
                continue
            miss.pop(coin, None)
            if dry_run:
                broker.mark(coin, px)   # feed the live mid so paper equity tracks open P&L
            notional = abs(held) * px

            if rate is not None:
                # Accrue modeled funding in BOTH modes: dry_run adds it to equity;
                # live uses it only for the per-trade ledger + win count (the real
                # funding is already in account_value, so open_fund/realized stay
                # dry_run-guarded to avoid double-counting).
                accr = (1.0 if is_short else -1.0) * rate * notional * dt_h
                m["accrued"] = m.get("accrued", 0.0) + accr
            meta[coin] = {**m, "is_short": is_short, "entry": entry, "opened_ts": opened_ts}

            held_h = (t0 - opened_ts) / 3600.0
            raw = (px - entry) / entry if entry else 0.0        # +ve = price rose
            # A SHORT loses when price rises (+raw is against us); a LONG loses
            # when price falls (so its adverse is -raw). +ve adverse == against us.
            adverse = raw if is_short else -raw
            favour = -adverse
            flipped = (apr is not None) and ((is_short and apr < 0) or (not is_short and apr > 0))

            decision = None
            if adverse >= HARD_STOP:
                decision = "stop"
            elif favour >= TAKE_PROFIT:
                decision = "take_profit"
            elif flipped:
                decision = "flip"
            elif apr is not None and abs(apr) < EXIT_APR:
                decision = "decay"
            elif held_h >= MAX_HOLD_H:
                decision = "max_hold"
            if decision is None:
                continue

            fund_pnl = m.get("accrued", 0.0)
            if dry_run:
                price_pnl = broker.close(coin, px)   # realizes price P&L in broker
                fund_realized += fund_pnl
            else:
                try:
                    ctx.venue.market_close(coin)
                except Exception as e:
                    log.error("close %s failed: %s — leaving position, retry next loop", coin, e)
                    continue
                price_pnl = (abs(held) * (px - entry)) if not is_short \
                    else (abs(held) * (entry - px))
            realized += (price_pnl + fund_pnl) if dry_run else 0.0
            n_closed += 1
            n_wins += 1 if (price_pnl + fund_pnl) > 0 else 0
            log.info("CLOSE %s %s after %.1fh | price %+.2f funding %+.2f [%s]",
                     coin, "short" if is_short else "long", held_h, price_pnl,
                     fund_pnl, decision)
            _record_close(bot_id, coin, entry, opened_ts, px, price_pnl, fund_pnl,
                          was_long=not is_short, reason=decision, order_usd=order_usd,
                          venue=venue_tag, shadow=shadow_tag)
            try:
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"),
                    shadow=shadow_tag, coin=coin,
                    side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=px, px_fill=px, raw={"reason": decision, "leg": "close"})
            except Exception:
                pass
            meta.pop(coin, None)
            hot_since.pop(coin, None)      # force a fresh persistence wait — no instant re-entry
            if decision == "stop":
                cooldown[coin] = t0 + STOP_COOLDOWN_H * 3600.0   # quarantine after a stop

        # ---- persistence clock over the whole funding map (uses the SAME gate the
        # scanner enters on, else persistence would never arm at the wider gate) ----
        for c, f in fund.items():
            r = f.get("rate")
            if r is not None and abs(r * H) >= ENTER_GATE:
                hot_since.setdefault(c, t0)
            else:
                hot_since.pop(c, None)

        # ---- scan for new entries — cheap funding prefilter, then deep-scan ----
        open_now = sum(1 for v in pos.values() if (v.get("size") if isinstance(v, dict) else v))
        if open_now < max_open:
            # cheap prefilter: hard SAFETY gates on the funding map only (no network)
            prelim = []
            for c, f in fund.items():
                if c in meta or c in pos:
                    continue
                if c in cooldown and t0 < cooldown[c]:
                    continue
                r = f.get("rate")
                if r is None:
                    continue
                apr = r * H
                if abs(apr) < ENTER_GATE or (f.get("vol") or 0.0) < MIN_VOL:
                    continue
                if (t0 - hot_since.get(c, t0)) / 3600.0 < PERSIST_H:
                    continue
                if not ctx.supports(c):
                    continue
                prelim.append((c, f, apr))
            prelim.sort(key=lambda x: -abs(x[2]))

            if SCAN_ENABLED:
                # deep-scan the hottest SCAN_DEEP_MAX: veto traps + rank risk-adjusted.
                # Each tuple carries its already-fetched book_metrics + scan evidence.
                # Wrapped: a scanner bug must NEVER crash the loop that manages stops —
                # degrade to no new entries this loop. [review 2026-07-11]
                try:
                    ranked = scan_candidates(ctx, prelim, order_usd, log)
                except Exception as e:  # noqa: BLE001
                    log.error("scanner error (%s) — no new entries this loop", e)
                    ranked = []
            else:
                # legacy: raw |apr|, book fetched per-candidate below (bm/ev = None)
                ranked = [(c, f, apr, apr > 0, None, None) for c, f, apr in prelim]

            for coin, f, apr, is_short, bm, ev in ranked:
                if open_now >= max_open or opened_this_loop >= MAX_NEW_PER_LOOP:
                    break
                # [2026-07-11 QUALITY VETO] fleet-measured toxicity, restrict-only
                if coin in _vetoes:
                    log.info("%s VETO_SKIP (%s)", coin, _vetoes[coin])
                    continue
                # [2026-07-11 SLOPE GATE] only enter while crowding still builds
                # (validated: see config block). Fails open with no history.
                _slope_prev = (_slope_ref(rate_hist.get(coin), t0,
                                          SLOPE_LOOKBACK_H * 3600)
                               if SLOPE_GATE else None)
                if _slope_prev is not None and abs(apr) < abs(_slope_prev):
                    log.info("%s SLOPE_SKIP (apr %+.1f%% < %+.1f%% %gh ago — rolling over)",
                             coin, apr * 100, _slope_prev * 100, SLOPE_LOOKBACK_H)
                    continue
                if bm is None:
                    # legacy / scanner-off: spread gate + fresh mid (own book fetch)
                    sp = book_spread_bps(ctx, coin)
                    if sp is None or sp > MAX_SPREAD_BPS:
                        log.info("%s SPREAD_SKIP (%.0fbps)", coin, sp if sp is not None else -1)
                        continue
                    px, spread_bps = fresh_mid(ctx, coin), sp
                else:
                    px, spread_bps = bm["mid"], bm["spread_bps"]   # from the deep-scan fetch
                if px is None:
                    continue
                size = round(order_usd / px, 6)
                if not dry_run:
                    open_ntl = sum(1 for v in pos.values()
                                   if (v.get("size") if isinstance(v, dict) else v)) * order_usd
                    if not ctx.rails.notional_ok(open_ntl, order_usd):
                        log.info("%s NOTIONAL_CAP_SKIP", coin)
                        continue
                try:
                    if dry_run:
                        broker.open(coin, not is_short, size, px)
                    else:
                        ctx.venue.market_open(coin, not is_short, size)
                except Exception as e:
                    log.error("open %s failed: %s", coin, e)
                    continue
                meta[coin] = {"is_short": is_short, "entry": px, "opened_ts": t0,
                              "accrued": 0.0}
                open_now += 1
                opened_this_loop += 1
                log.info("OPEN %s %s $%.0f | funding %+.1f%% APR | px %.6g | spread %.0fbps%s",
                         coin, "short" if is_short else "long", order_usd, apr, px, spread_bps,
                         (" | " + " ".join(f"{k}={v}" for k, v in ev.items())) if ev else "")
                try:
                    raw = {"apr": round(apr, 3), "spread_bps": round(spread_bps, 1),
                           "leg": "open", "mctx": _mctx_slice(_mctx, coin),
                           "slope": {"apr_prev": (round(_slope_prev, 4)
                                                  if _slope_prev is not None else None),
                                     "lookback_h": SLOPE_LOOKBACK_H,
                                     "gate": SLOPE_GATE}}
                    if ev:
                        raw["scan"] = ev      # vol/adverse/slip/xv/score -> shadow ledger
                    store.publish_venue_order(
                        bot_id, venue=("lighter" if venue_tag else "hl"),
                        shadow=shadow_tag, coin=coin,
                        side=("sell" if is_short else "buy"), size=size,
                        px_decision=px, px_fill=px, raw=raw)
                except Exception:
                    pass

        # ---- publish snapshot ----
        if dry_run:
            open_fund = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
            pub_equity = broker.equity() + fund_realized + open_fund
            pub_open = broker.open_count()
            pub_pnl = pub_equity - START_EQUITY
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values()
                           if (v.get("size") if isinstance(v, dict) else v))
            if live_baseline is None and equity is not None:
                live_baseline = equity
            pub_pnl = (equity - live_baseline) if (equity is not None
                                                   and live_baseline is not None) else None
        top = sorted(((c, f.get("rate") or 0.0) for c, f in fund.items()),
                     key=lambda cr: -abs(cr[1]))[:3]
        try:
            store.publish(
                bot_id, status="paper" if ctx.mode == "hl_paper" and dry_run
                else ("halted" if halted_today else "online"),
                equity=pub_equity, pnl_abs=pub_pnl, open_trades=pub_open,
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode, "style": "directional-funding",
                       "held": {c: ("S" if (meta.get(c) or {}).get("is_short") else "L")
                                for c in meta},
                       "hottest_apr": {c: f"{r*H:+.0%}" for c, r in top}})
        except Exception:
            pass
        # persist state (dry_run: full paper account; live: baseline + open meta)
        try:
            if dry_run:
                store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                          "fund_realized": fund_realized})
            elif live_baseline is not None:
                store.save_state(bot_id + ":live", {"initial_equity": live_baseline,
                                                    "meta": meta})
        except Exception:
            pass

        held = ", ".join(f"{c}({'S' if (meta.get(c) or {}).get('is_short') else 'L'})"
                         for c in meta) or "none"
        log.info("scan ok | %d perps | held: %s | realized $%+.2f", len(fund), held, realized)

        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


if __name__ == "__main__":
    main()
