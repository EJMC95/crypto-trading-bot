#!/usr/bin/env python3
"""
lighter_index_bot.py — 📊 Index Rider: the IBKR stock bot on LIGHTER stock perps.

WHAT / WHY (2026-07-13)
  Eamon asked to move the IBKR bot (equities-regime-ibkr: SPY+QQQ, long while
  close > 200-day SMA, else cash — ~/Claude/Projects/Stocks/IKBR) off IBKR and
  onto Lighter. Lighter now lists REAL equity perps: SPY/QQQ trade with 1-3bps
  spreads and ~$0.6M/day each (probed 13 Jul). This is a genuine port of the
  bot to its own instruments — NOT the rejected Index Pilot flavor (that used
  the SPY signal to gate CRYPTO trades; see the 12-Jul review).

  SIGNAL comes from the REAL equity market's daily closes (Yahoo chart API,
  keyless, ~2y of history) because Lighter's SPY/QQQ candles only go back
  ~173 days — not enough for a 200-day SMA. The signal math is copied verbatim
  from the IBKR bot's signals.py (pos_regime: close > SMA(200) -> long, else
  flat), so the port trades exactly what the original trades.

  EXECUTION is Lighter: ShadowBroker fills crossing the live book, hourly
  funding accrual (SPY/QQQ funding printed ~28% APR at probe time — a LONG
  PAYS it; whether the regime edge survives that drag is the exact question
  this shadow book exists to answer, like Tide Rider's +52%->+40% study).

  UNVALIDATED on this venue: VENUE=lighter_live REFUSES to start in v1. The
  IBKR paper bot keeps running as the control arm until the record earns a
  decommission (or the user cuts it early).

  Reference-blind rule (Snap Back doctrine): no stooq daily history -> no NEW
  decisions this loop; held positions keep their marks/seatbelt.

Usage:
    VENUE=lighter_shadow python lighter_index_bot.py            # daemon
    VENUE=lighter_shadow python lighter_index_bot.py --once     # smoke
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

BOT = "equities-regime"          # row: equities-regime-lshadow

START_EQUITY = 1000.0
# [2026-07-13 UTILIZATION] $50 -> $250/slot: at 3 sleeves the book deploys up
# to 75% of its $1,000 instead of 15% — the IBKR original's biggest practical
# flaw was 10% max deployment (5%/position x 2). Sizing only, not strategy.
ORDER_USD = float(os.environ.get("INDEX_ORDER_USD", "250"))
SYMBOLS = os.environ.get("INDEX_SYMBOLS", "SPY,QQQ,XAU").split(",")
REGIME_SMA = int(os.environ.get("INDEX_REGIME_SMA", "200"))

# [2026-07-13 UNIVERSE EXPANSION — evidence in the 13-Jul sweep, scratchpad
# index_universe_backtest.py, 15y Yahoo dailies, 10bps/switch cost]
# Per-symbol rule + Yahoo reference. Both rules are VERBATIM from the IBKR
# bot's signals.py with its own config defaults (regime_sma 200; fast/slow
# 20/50) — no invented parameters.
#   SPY  regime200:   +7.7% CAGR / 22.5% maxDD (B&H +12.6%/34.1%) — shipped v1
#   QQQ  regime200:  +13.9% / 22.3% (B&H +18.3%/35.6%)            — shipped v1
#   XAU  sma20/50:    +6.4% / 20.7% (B&H +6.5%/41.4%); regime200 was marginal
#        (+4.0%/33.1%). Robust: every neighbour pair 15/40..30/70 positive
#        (+4.8..+7.6%), recent-half all positive — a plateau, not a fit.
# REJECTED by the same sweep (don't re-test): XAG (+1.2% regime / 55% DD
# cross), WTI (-4.4% regime), BRENT (-0.7%), XCU (+0.4%), XPT (-5.3%);
# NATGAS (broken funding print, decay); US500/US100 (duplicate SPY/QQQ);
# single names (the IBKR bot's own docs: timing rules fit indices, not
# stocks). Breakeven funding: SPY +9.2%apr, QQQ +16.6%, XAU-cross +12.0% —
# the venue printed ~28%apr at probe; the shadow measures the REAL average.
# [2026-07-13 ENHANCEMENT LAB — scratchpad index_enhance_backtest.py]
# regime + ±1% HYSTERESIS BAND on the index sleeves: enter > SMA200*1.01,
# exit < SMA200*0.99. 15y: SPY +8.4%/20.2%DD (raw daily200 +7.7%/22.5%),
# QQQ +14.4%/22.1% (raw +13.9%/22.3%), switches HALVED (2.3-2.8/yr vs
# 4.5-5.6) — and robust: every band 0.5..2.0% beats raw on both indices in
# BOTH window halves (a whipsaw-suppression plateau, not a fit). Divergence
# from the IBKR twin (raw daily200) is deliberate and documented — the twin
# doubles as the raw-vs-banded control.
# REJECTED by the same lab (don't re-test): monthly-eval Faber timing (DD
# 26-29% vs 20-22%), long/short regime (SPY +1.6%/46%DD), dual-momentum
# SPY/QQQ rotation (+6.6% portfolio CAGR vs +9.9% shipped).
SLEEVES = {          # symbol -> (rule, param)
    "SPY": ("regime_band", (200, 0.01)),
    "QQQ": ("regime_band", (200, 0.01)),
    "XAU": ("sma_cross", (20, 50)),
}
YAHOO_REF = {"XAU": "GC=F", "XAG": "SI=F", "WTI": "CL=F",
             "BRENTOIL": "BZ=F", "XCU": "HG=F", "XPT": "PL=F"}
CATASTROPHIC_STOP = float(os.environ.get("INDEX_CATASTROPHIC_STOP", "0.15"))
# [2026-07-16 ZOMBIE GUARD] a held symbol that leaves the tradable universe
# (unsupported at boot / removed from SYMBOLS / book dark) was never marked,
# accrued, or exit-checked again. Give up after this long at the last mark.
DELIST_GIVEUP_H = float(os.environ.get("INDEX_DELIST_GIVEUP_H", "6"))
DAILY_LOSS_LIMIT = float(os.environ.get("INDEX_DAILY_LOSS", "0.10"))
LOOP_SECONDS = int(os.environ.get("INDEX_LOOP_SECONDS", "300"))
MAX_OPEN = int(os.environ.get("INDEX_MAX_OPEN", str(len(SYMBOLS))))

LOG_FILE = os.environ.get("INDEX_LOG_FILE", "lighter_index_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


# --- signal math, verbatim from the IBKR bot's src/signals.py ---------------
def sma(values, period):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out


def pos_regime(close, period=200):
    m = sma(close, period)
    return [1 if (m[i] and close[i] > m[i]) else 0 for i in range(len(close))]


def pos_sma_cross(close, fast=20, slow=50):
    f, s = sma(close, fast), sma(close, slow)
    return [1 if (f[i] and s[i] and f[i] > s[i]) else 0 for i in range(len(close))]


def pos_regime_band(close, period=200, band=0.01):
    """pos_regime with a hysteresis band: enter above SMA*(1+band), exit below
    SMA*(1-band). Inside the band the previous state holds (whipsaw filter)."""
    m = sma(close, period)
    pos, holding = [], 0
    for i in range(len(close)):
        if m[i]:
            if close[i] > m[i] * (1 + band):
                holding = 1
            elif close[i] < m[i] * (1 - band):
                holding = 0
        pos.append(holding)
    return pos


def want_position(symbol, closes):
    """Desired position for `symbol` on its sleeve's rule."""
    rule, param = SLEEVES.get(symbol, ("regime", REGIME_SMA))
    if rule == "sma_cross":
        return pos_sma_cross(closes, *param)[-1]
    if rule == "regime_band":
        return pos_regime_band(closes, *param)[-1]
    return pos_regime(closes, param)[-1]


# --- reference daily closes (Yahoo chart API; keyless; ~2y of history) ------
# (stooq was the first choice but now sits behind a JS proof-of-work wall.)
# PARITY NOTE: the IBKR bot decides on the LATEST daily bar IB returns —
# including the still-forming session during market hours — so this port
# keeps Yahoo's live bar too instead of dropping it.
_ref_cache = {}      # symbol -> {"ts": epoch, "closes": [...], "last_date": iso}
_REF_TTL_S = 6 * 3600      # refresh a few times a day, like the 2h IBKR poll


def ref_closes(symbol):
    """Daily close series for the REAL instrument, oldest->newest. None on
    failure with no cache — callers must treat that as reference-blind."""
    hit = _ref_cache.get(symbol)
    if hit and time.time() - hit["ts"] < _REF_TTL_S:
        return hit
    ref_sym = urllib.parse.quote(YAHOO_REF.get(symbol, symbol), safe="")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ref_sym}"
           f"?range=2y&interval=1d")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        raw = json.loads(urllib.request.urlopen(req, timeout=20).read())
        res = raw["chart"]["result"][0]
        ts = res.get("timestamp") or []
        cl = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        closes, dates = [], []
        for t, c in zip(ts, cl):
            if c is None:
                continue
            closes.append(float(c))
            dates.append(datetime.fromtimestamp(t, tz=timezone.utc)
                         .date().isoformat())
        if len(closes) < REGIME_SMA + 2:
            log.warning("%s: only %d ref closes (< %d) — reference-blind",
                        symbol, len(closes), REGIME_SMA + 2)
            return None
        hit = {"ts": time.time(), "closes": closes, "last_date": dates[-1]}
        _ref_cache[symbol] = hit
        return hit
    except Exception as e:  # noqa: BLE001 — blind is an answer, not a crash
        log.warning("%s: reference unavailable (%s)", symbol, e)
        return _ref_cache.get(symbol)   # a stale cache beats nothing


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
    p = argparse.ArgumentParser(description="Index Rider — stock-perp regime (shadow)")
    p.add_argument("--once", action="store_true", help="Single loop then exit.")
    args = p.parse_args()

    mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    # [v1 GATE] UNVALIDATED on this venue — shadow only; the funding-drag
    # record vs the IBKR control arm earns (or kills) any go-live.
    if mode != "lighter_shadow":
        raise SystemExit("equities-regime runs VENUE=lighter_shadow ONLY in v1 "
                         "— the stock-perp port is unvalidated; the shadow "
                         "record earns (or kills) any go-live.")

    from venues.lighter_client import LighterClient
    from venues.shadow import ShadowBroker
    venue = LighterClient(net="mainnet", with_signer=False)
    bot_id = BOT + "-lshadow"
    broker = ShadowBroker(bot_id, venue, START_EQUITY)
    rails = SafetyRails(BOT, mode)

    symbols = [s for s in SYMBOLS if venue.supports(s)]
    skipped = [s for s in SYMBOLS if s not in symbols]

    meta = {}            # symbol -> {entry, opened_ts, accrued}
    fund_realized = 0.0
    n_closed = n_wins = 0
    saved = store.load_state(bot_id)
    if saved and broker.restore_state(saved.get("broker") or {}):
        meta = {str(k): v for k, v in (saved.get("meta") or {}).items()}
        fund_realized = float(saved.get("fund_realized") or 0.0)
        log.info("restored shadow state: $%.2f, %d open", broker.equity(),
                 broker.open_count())
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    def equity():
        open_accr = sum((m or {}).get("accrued", 0.0) for m in meta.values())
        return broker.equity() + fund_realized + open_accr

    log.info("=" * 64)
    log.info("Index Rider (STOCK PERPS on Lighter, shadow) | %s (skipped: %s)",
             ", ".join(symbols), ", ".join(skipped) or "none")
    log.info("sleeves: %s — signals on the REAL market's dailies (Yahoo), "
             "rules verbatim from the IBKR bot's signals.py | $%.0f/slot x %d "
             "| seatbelt %.0f%% | loop=%ds",
             {s: SLEEVES.get(s, ("regime", REGIME_SMA)) for s in symbols},
             ORDER_USD, MAX_OPEN, CATASTROPHIC_STOP * 100, LOOP_SECONDS)
    log.info("EVIDENCE-FIRST: measures the funding drag a long pays on equity "
             "perps (~28%% APR at probe). IBKR paper twin = control arm. "
             "lighter_live REFUSED in v1.")
    log.info("=" * 64)

    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    if store.load_daily_halt(bot_id, cur_day.isoformat()):
        halted_today = True
        log.warning("daily-loss halt restored — halted for today.")
    day_start_equity = equity()
    # [2026-07-16 AUDIT FIX] restore the accrual clock: it reset to
    # boot time on every redeploy, so funding during the gap was never
    # accrued (systematic undercount of the drag/credit this book
    # measures). Gap bounded to 48h so ancient state can't over-accrue.
    try:
        _lt = float((saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()

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
                    px = marks.fresh_mid(venue, s) or meta[s]["entry"]
                    sz, ent = broker.pos.get(s, (0.0, 0.0))
                    pnl = broker.close(s, px)
                    fund_realized += meta[s].get("accrued", 0.0)
                    n_closed += 1
                    n_wins += 1 if (pnl + meta[s].get("accrued", 0.0)) > 0 else 0
                    _record_close(bot_id, s, meta[s].get("entry"),
                                  meta[s].get("opened_ts"), px, pnl,
                                  meta[s].get("accrued", 0.0), "rail_flatten",
                                  abs(sz) * ent)
                    meta.pop(s, None)

        if halted_today:
            try:
                store.publish(bot_id, status="halted", equity=equity(),
                              pnl_abs=equity() - START_EQUITY,
                              closed_trades=n_closed, wins=n_wins,
                              losses=n_closed - n_wins,
                              extra={"mode": mode, "venue": mode,
                                     "style": "stock-perp-regime"})
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

        regime = {}
        for s in symbols:
            px = marks.fresh_mid(venue, s)
            held = s in broker.pos
            m = meta.get(s) or {}

            # mark + funding accrual + catastrophic seatbelt (live px, always)
            if held and not px:
                # [2026-07-16 ZOMBIE GUARD] unpriceable held symbol
                first = m.get("no_px_since")
                if not isinstance(first, (int, float)):
                    m["no_px_since"] = t0
                    meta[s] = m
                elif (t0 - first) / 3600.0 >= DELIST_GIVEUP_H:
                    sz, ent = broker.pos.get(s, (0.0, 0.0))
                    zpx = float(m.get("last_px") or ent or 0.0)
                    if zpx:
                        pnl = broker.close(s, zpx)
                        fund_realized += m.get("accrued", 0.0)
                        n_closed += 1
                        n_wins += 1 if (pnl + m.get("accrued", 0.0)) > 0 else 0
                        _record_close(bot_id, s, m.get("entry"), m.get("opened_ts"),
                                      zpx, pnl, m.get("accrued", 0.0), "delisted",
                                      abs(sz) * ent)
                        meta.pop(s, None)
                        log.warning("%s DELIST GIVE-UP CLOSE @ %.4f", s, zpx)
            if held and px:
                m.pop("no_px_since", None)
                m["last_px"] = px
                meta[s] = m
                broker.mark(s, px)
                rate = (fund.get(s) or {}).get("rate")
                if rate is not None:
                    sz = abs(broker.pos[s][0])
                    m["accrued"] = m.get("accrued", 0.0) - rate * sz * px * dt_h
                    meta[s] = m
                entry = m.get("entry") or 0.0
                if entry and (px - entry) / entry <= -CATASTROPHIC_STOP:
                    sz, ent = broker.pos.get(s, (0.0, 0.0))
                    pnl = broker.close(s, px)
                    fund_realized += m.get("accrued", 0.0)
                    n_closed += 1
                    n_wins += 1 if (pnl + m.get("accrued", 0.0)) > 0 else 0
                    _record_close(bot_id, s, entry, m.get("opened_ts"), px, pnl,
                                  m.get("accrued", 0.0), "catastrophic_stop",
                                  abs(sz) * ent)
                    meta.pop(s, None)
                    log.warning("%s CATASTROPHIC STOP @ %.2f", s, px)
                    continue

            # reference signal (real market dailies; blind -> no new decisions)
            ref = ref_closes(s)
            if ref is None:
                regime[s] = None
                continue
            want = want_position(s, ref["closes"])
            regime[s] = want

            if held and want == 0 and px:
                m = meta.get(s) or {}
                sz, ent = broker.pos.get(s, (0.0, 0.0))
                pnl = broker.close(s, px)
                fund_realized += m.get("accrued", 0.0)
                total = pnl + m.get("accrued", 0.0)
                n_closed += 1
                n_wins += 1 if total > 0 else 0
                log.info("CLOSE %s | price %+.2f funding %+.2f [regime_exit, "
                         "ref %s]", s, pnl, m.get("accrued", 0.0), ref["last_date"])
                _record_close(bot_id, s, m.get("entry"), m.get("opened_ts"),
                              px, pnl, m.get("accrued", 0.0), "regime_exit",
                              abs(sz) * ent)
                meta.pop(s, None)
            elif (not held and want == 1 and px
                  and broker.open_count() < MAX_OPEN):
                size = ORDER_USD / px
                broker.open(s, True, size, px)
                ent = broker.pos.get(s)
                meta[s] = {"entry": (ent[1] if ent else px),
                           "opened_ts": t0, "accrued": 0.0}
                rule, param = SLEEVES.get(s, ("regime", REGIME_SMA))
                log.info("OPEN %s long $%.0f @ %.4f | %s%s (ref %s) | "
                         "funding %.1f%%apr", s, ORDER_USD, meta[s]["entry"],
                         rule, param, ref["last_date"],
                         ((fund.get(s) or {}).get("rate") or 0) * 24 * 365 * 100)

        # [2026-07-16 ZOMBIE GUARD] ORPHANS: a restored position on a symbol
        # no longer in the tradable list never enters the loop above at all.
        for s in [c for c in list(broker.pos) if c not in symbols]:
            m = meta.get(s) or {}
            try:
                opx = marks.fresh_mid(venue, s)
            except Exception:  # noqa: BLE001
                opx = None
            if opx:
                broker.mark(s, opx)
                m.pop("no_px_since", None)
                m["last_px"] = opx
                meta[s] = m
            first = m.get("no_px_since")
            if opx is None and not isinstance(first, (int, float)):
                m["no_px_since"] = t0
                meta[s] = m
                continue
            if opx is None and (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                continue
            sz, ent = broker.pos.get(s, (0.0, 0.0))
            zpx = float(opx or m.get("last_px") or ent or 0.0)
            if not zpx:
                continue
            pnl = broker.close(s, zpx)
            fund_realized += m.get("accrued", 0.0)
            n_closed += 1
            n_wins += 1 if (pnl + m.get("accrued", 0.0)) > 0 else 0
            _record_close(bot_id, s, m.get("entry"), m.get("opened_ts"), zpx,
                          pnl, m.get("accrued", 0.0), "delisted", abs(sz) * ent)
            meta.pop(s, None)
            log.warning("%s ORPHAN CLOSE @ %.4f (symbol left the universe)", s, zpx)

        # ---- publish + persist ----
        open_accr = sum((m or {}).get("accrued", 0.0) for m in meta.values())
        try:
            store.publish(
                bot_id, status="online", equity=equity(),
                pnl_abs=equity() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": mode, "venue": mode, "style": "stock-perp-regime",
                       "held": sorted(meta.keys()),
                       "sleeves": {s: SLEEVES.get(s, ("regime", REGIME_SMA))[0]
                                   for s in symbols},
                       "regime": {s: regime.get(s) for s in symbols},
                       "fund_realized": round(fund_realized, 4),
                       "fund_open": round(open_accr, 4),
                       "funding_apr": {s: round(((fund.get(s) or {}).get("rate")
                                                 or 0) * 24 * 365 * 100, 1)
                                       for s in symbols},
                       "skipped_unlisted": skipped})
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "fund_realized": fund_realized,
                                      "last_ts": last_ts})
        except Exception:  # noqa: BLE001
            pass

        log.info("loop ok | eq $%.2f | held: %s | regime: %s",
                 equity(), ", ".join(sorted(meta)) or "none",
                 {s: regime.get(s) for s in symbols})
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
