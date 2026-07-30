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
  funding accrual.

  [2026-07-22 THE FOUNDING QUESTION IS ANSWERED — AND THE ANSWER IS "NO"]
  This file used to say SPY/QQQ funding "printed ~28% APR at probe — whether
  the regime edge survives that drag is the exact question this shadow book
  exists to answer". **That 28% was the 8x pre-basis-fix artifact** (the
  /funding-rates endpoint quotes an 8-HOUR fraction that was annualised as if
  hourly; corrected 17-Jul, funding_basis.py). Funding does NOT threaten this
  sleeve, and three independent measurements agree:
      source                                    SPY     QQQ     XAU
      60d SETTLED /api/v1/fundings (22-Jul)    +2.4%   +7.8%   +7.6%
      funding_basis.py:18 anchor          published 28.0% -> settled 3.50%
      this bot's OWN accrual (-$0.405 on ~$500 over ~9d)   ~3.3% apr
      its stated BREAKEVEN (below)             +9.2%  +16.6%  +12.0%
  Every measured number is well under its breakeven. Do NOT rebuild a
  funding-drag study to re-answer this; it is answered three ways.

  WHAT IS STILL UNKNOWN is the regime edge itself — and this book cannot tell
  you, because it barely trades: **0 closed trades in its first ~9 days**,
  holding SPY+QQQ with XAU flat. That is BY DESIGN (a 200d filter with a ±1%
  band switches ~2.3-2.8x/YEAR), and it means the fleet's ">=20 trades/30d"
  go-live gate is UNREACHABLE BY CONSTRUCTION for this bot. It needs Tide
  Rider's exemption (CLAUDE.md: "trades too rarely to judge; stays
  backtest-validated"), not the trade-count gate.

  UNVALIDATED on this venue: VENUE=lighter_live REFUSES to start in v1.
  [2026-07-22] The IBKR paper twin named here as the control arm was RETIRED
  14-Jul in the Lighter-first cut, so the go-live rule as originally written
  has NO COMPARATOR — and the twin also doubled as the raw-vs-banded control,
  which is likewise gone. Any go-live decision must therefore rest on the 15y
  backtest + the now-measured funding drag, reviewed explicitly. Do not read
  the absence of a control arm as the record having "earned" anything.

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

# [2026-07-30] growth rail; guarded, COPY added to Dockerfile.indexshadow in
# the same commit (born-dark doctrine).
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
import funding_basis
from venues import marks
from venues.safety import SafetyRails

BOT = "equities-regime"          # row: equities-regime-lshadow

START_EQUITY = 1000.0
# [2026-07-13 UTILIZATION] $50 -> $250/slot: at 3 sleeves the book deploys up
# to 75% of its $1,000 instead of 15% — the IBKR original's biggest practical
# flaw was 10% max deployment (5%/position x 2). Sizing only, not strategy.
# [2026-07-30 SIZE vs EVIDENCE] $250 -> $100. This book carried the LARGEST
# CLIP IN THE FLEET — 5x the family's $50, 10x the Farmer's $25 — on a book
# with ZERO closed trades. That is maximum size on minimum evidence, the exact
# inversion of how every other book here is sized. $100 across a widened
# sleeve set deploys MORE of the book than $250 across three, while making
# each individual bet survivable enough to be informative.
ORDER_USD = float(os.environ.get("INDEX_ORDER_USD", "100"))
# [2026-07-30 UNIVERSE] SPY,QQQ,XAU -> the venue's full non-crypto set (the
# same ten books the family bot's per-asset gate grades). These are the
# fleet's ONLY source of a regime that is not falling-BTC: over the same
# window SPY +8.1%, QQQ +12.2%, WTI +23.0%. Item 18 says a directional book
# validated on this tape has been validated in ONE regime; widening here is
# the on-venue way to get a second one.
SYMBOLS = [s.strip().upper() for s in os.environ.get(
    "INDEX_SYMBOLS", "SPY,QQQ,IWM,NVDA,TSLA,MSTR,WTI,XAU,XAG,XCU").split(",")
    if s.strip()]
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
# [2026-07-22 MEASURED, supersedes the "~28%apr at probe" that stood here]
# realized 60d SETTLED funding is SPY +2.4% / QQQ +7.8% / XAU +7.6% apr, i.e.
# 26% / 47% / 63% of breakeven. The 28% was the 8x basis artifact. The drag is
# real but it does NOT eat the edge. (These breakevens were also computed
# against RAW regime200, not the shipped ±1% band, which has higher CAGR and
# marginally higher time-in-market — so they are mildly conservative.)
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
    # [2026-07-30] the widened set. Index-like books reuse the validated
    # 200-day regime band; the single-name and commodity books use the
    # faster SMA cross, matching how XAU was already treated. Deliberately
    # NOT new rules — this widens the UNIVERSE the existing, validated
    # rules are applied to, so the change is one variable, not two.
    "IWM": ("regime_band", (200, 0.01)),
    "NVDA": ("sma_cross", (20, 50)),
    "TSLA": ("sma_cross", (20, 50)),
    "MSTR": ("sma_cross", (20, 50)),
    "WTI": ("sma_cross", (20, 50)),
    "XAG": ("sma_cross", (20, 50)),
    "XCU": ("sma_cross", (20, 50)),
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


# [2026-07-30 AUTO-REVERT FIX] The operator's env defaults, snapshotted at
# IMPORT. apply_tuning() must hand THESE to get_lever, never the current
# global: get_lever returns its `default` when the lever is absent, expired
# or quarantined, so passing the already-moved value made the rail a ONE-WAY
# RATCHET — a widened lever could never revert, and auto-revert-on-expiry is
# the growth rail's central safety property ("levers EXPIRE back to defaults
# on their own, so auto-revert is the resting state"). Shipped broken in
# (fz); it was inert only because nothing authored the lane yet.
_ENV_DEFAULTS = {"MAX_OPEN": MAX_OPEN}


def apply_tuning():
    """Growth-rail levers over the env defaults; {} when the rail is dark."""
    global MAX_OPEN
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in (("index.max_open", "MAX_OPEN"),):
        cur = globals()[attr]
        try:
            val = tuning.get_lever(lever, _ENV_DEFAULTS[attr])
        except Exception:  # noqa: BLE001
            continue
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


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
            # [2026-07-30 (gr)] EXIT TELEMETRY — computed above for pnl_pct,
            # then discarded. publish_paper_trade has accepted these since
            # 17-Jul, the DB column exists, the reader SELECTs them and
            # /trades.json exposes them: 8 of 9 bots never filled the pipe.
            # Without the prices no exit rule can be counterfactually
            # tested — the price PATH cannot be joined to the trade.
            # Telemetry only; no gate moves.
            entry_price=ent_px, exit_price=exit_px,
            reason="long_" + reason, venue="lighter", shadow=True)
    except Exception:  # noqa: BLE001
        pass


def main():
    p = argparse.ArgumentParser(description="Index Rider — stock-perp regime (shadow)")
    p.add_argument("--once", action="store_true", help="Single loop then exit.")
    args = p.parse_args()

    mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    # [v1 GATE] UNVALIDATED on this venue — shadow only.
    # [2026-07-22] The original rule read "the funding-drag record vs the IBKR
    # control arm earns (or kills) any go-live". BOTH halves of that are now
    # void: the funding-drag question is ANSWERED (measured well under
    # breakeven, see the module docstring) and the IBKR control arm was
    # RETIRED 14-Jul, so there is no comparator. This guard stays regardless —
    # a bot with 0 closed trades in 9 days has produced no record at all, and
    # "no evidence against" is not evidence for.
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
        # [2026-07-30] growth rail, every loop; a TTL expiry reverts to the
        # operator default by the same path that applied the lever.
        _lv = apply_tuning()
        if _lv:
            log.info("levers applied %s", _lv)
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
                    # [2026-07-17 BASIS FIX] 8h quote accrued per hour = 8x
                    m["accrued"] = (m.get("accrued", 0.0)
                                    - funding_basis.to_hourly(rate, "lighter")
                                    * sz * px * dt_h)
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
                         funding_basis.to_apr_pct((fund.get(s) or {}).get('rate') or 0, 'lighter'))

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
                       # [2026-07-30] effective cap — see funding_carry_bot
                       "caps": {"max_open": MAX_OPEN,
                                "universe": len(SYMBOLS)},
                       "held": sorted(meta.keys()),
                       "sleeves": {s: SLEEVES.get(s, ("regime", REGIME_SMA))[0]
                                   for s in symbols},
                       "regime": {s: regime.get(s) for s in symbols},
                       "fund_realized": round(fund_realized, 4),
                       "fund_open": round(open_accr, 4),
                       "funding_apr": {s: round(funding_basis.to_apr_pct(
                                           (fund.get(s) or {}).get("rate") or 0,
                                           "lighter"), 1)
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


def _selftest():
    """Offline checks of the signal math + the ledger row shape. No network,
    no DB, no venue — the bot ran with ZERO tests until 2026-07-29 (coverage
    Finding 7); this is the fleet's minimum selftest parity."""
    # sma: warmup Nones, then the rolling mean
    assert sma([1.0, 2.0, 3.0, 4.0], 2) == [None, 1.5, 2.5, 3.5]

    # plain regime: above SMA = 1, at-or-below = 0
    closes = [100.0, 100.0, 105.0, 90.0]
    assert pos_regime(closes, period=2) == [0, 0, 1, 0]

    # band hysteresis: INSIDE the band the previous state HOLDS — the whipsaw
    # filter. Series crafted so bar 3 sits inside the ±1% band around its
    # SMA2: plain regime flips to 0 there, the band variant must hold 1.
    hyst = [100.0, 100.0, 105.0, 103.0, 90.0]
    assert pos_regime(hyst, period=2)[3] == 0
    band = pos_regime_band(hyst, period=2, band=0.01)
    assert band == [0, 0, 1, 1, 0], band     # bar 3 held long; bar 4 exits

    # sleeve dispatch: each rule reachable, unknown symbol -> plain regime
    saved = dict(SLEEVES)
    try:
        SLEEVES.clear()
        SLEEVES.update({"T_BAND": ("regime_band", (2, 0.01)),
                        "T_X": ("sma_cross", (1, 2))})
        assert want_position("T_BAND", hyst[:4]) == 1     # held by the band
        assert want_position("T_X", [1.0, 2.0, 3.0]) == 1  # fast>slow rising
        assert want_position("UNKNOWN", [1.0] * (REGIME_SMA + 1)) == 0
    finally:
        SLEEVES.clear()
        SLEEVES.update(saved)

    # ledger row: tag/venue/shadow shape + the price+funding sum, and the
    # publish guard never raises into the trading loop
    cap = {}
    _orig = store.publish_paper_trade
    store.publish_paper_trade = lambda bot_id, **kw: cap.update(bot=bot_id, **kw)
    try:
        _record_close("equities-regime-lshadow", "SPY", 500.0, 1_700_000_000,
                      510.0, price_pnl=2.0, fund_pnl=-0.5, reason="tp",
                      notional=100.0)
        assert cap["reason"] == "long_tp"            # sleeve is long-only
        assert cap["pnl_abs"] == 1.5                 # price + funding, signed
        assert cap["pnl_pct"] == 0.015
        assert cap["venue"] == "lighter" and cap["shadow"] is True
        _record_close("b", "SPY", 500.0, None, 510.0, 1.0, 0.0, "stop", 0.0)
        assert cap["pnl_pct"] is None                # zero notional -> no pct
        assert cap["opened_at"] is None              # no entry ts -> honest None

        def _boom(bot_id, **kw):
            raise RuntimeError("db down")
        store.publish_paper_trade = _boom
        _record_close("b", "SPY", 500.0, 1, 510.0, 1.0, 0.0, "tp", 100.0)
    finally:
        store.publish_paper_trade = _orig
    print("[index-rider] selftest OK (sma/regime/band-hysteresis/dispatch/ledger-row)")


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
    if "--selftest" in sys.argv:
        _selftest()
        raise SystemExit(0)
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
