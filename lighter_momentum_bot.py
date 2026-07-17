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
import funding_basis
from venues import marks
from venues.safety import SafetyRails

BOT = "equities-momentum"        # row: equities-momentum-lshadow

START_EQUITY = 1000.0
ORDER_USD = float(os.environ.get("MOMO_ORDER_USD", "180"))
TOP_N = int(os.environ.get("MOMO_TOP_N", "5"))
# [2026-07-13 REACH WIDENING — evidence in the 13-Jul universe sweep]
# MULTI-ASSET rotation: gold/silver/oil + BTC/ETH now COMPETE for the same
# five slots as the 20 stocks. Backtest (same harness, 15y, both halves):
# beats the stock-only universe on CAGR AND maxDD in ALL SIX configs tested
# (top3/5/8 x lb42/63; e.g. top5/42: +43.7%/44.3%DD vs +35.6%/50.1%DD) —
# both-halves better in every cell. NOTE this is DISTINCT from the rejected
# crypto x-sect momentum factor (Counterweight lab: 72h ranks, crypto-only);
# here BTC/ETH are 2 of 25 candidates on 42d ranks behind SMA200 qualifiers.
# REJECTED in the same sweep (don't re-test): EWY (adds nothing — never
# out-ranks the growth names), SOXL (no benefit even before the objection
# that a 3x levered ETF has no place in a 1x fleet), Asia singles + thematic
# ETFs (MAGS/SOXX/BOTZ/ROBO/URA/TENCENT/BYD/XIAOMI/SAMSUNG etc.: dead books).
UNIVERSE = os.environ.get(
    "MOMO_SYMBOLS",
    "MU,SNDK,NVDA,META,COIN,AMD,SPY,QQQ,INTC,MSTR,HOOD,CRCL,MSFT,MRVL,TSLA,"
    "AMZN,GOOGL,AAPL,RKLB,NBIS,XAU,XAG,WTI,BTC,ETH").split(",")
# Yahoo reference tickers for the non-equity legs (equities map 1:1).
REF_MAP = {"XAU": "GC=F", "XAG": "SI=F", "WTI": "CL=F",
           "BTC": "BTC-USD", "ETH": "ETH-USD"}
TREND_MA, SLOW_MA, FAST_MA = 200, 50, 20         # Alpaca config.py values
MOMENTUM_LOOKBACK = int(os.environ.get("MOMO_LOOKBACK", "42"))
REBALANCE_DAYS = float(os.environ.get("MOMO_REBALANCE_DAYS", "7"))
CATASTROPHIC_STOP = float(os.environ.get("MOMO_CATASTROPHIC_STOP", "0.15"))
DAILY_LOSS_LIMIT = float(os.environ.get("MOMO_DAILY_LOSS", "0.10"))
LOOP_SECONDS = int(os.environ.get("MOMO_LOOP_SECONDS", "600"))

# [2026-07-13 YIELD LAB — scratchpad momentum_yield_lab.py] price-based
# ranking variants all FAILED the both-halves bar vs the shipped rule
# (SHARPE -6pp; IVOL sizing DD 36.9->54.9%; SKIP/DUAL mixed across halves) —
# don't re-test. The remaining yield lever is VENUE-NATIVE and has no history
# to backtest: funding-aware selection (HOOD printed 301%apr = ~5.8%/WEEK
# carry on day one — far larger than any adjacent-rank momentum spread). So
# it runs as a LIVE A/B: the real book stays verbatim-Alpaca; this VIRTUAL
# ledger applies a funding veto (skip/exit qualifiers paying more than
# MOMO_AB_VETO_APR, backfill next rank) and is marked/accrued in parallel
# (mid fills — slightly optimistic vs the real book's VWAP; the comparison
# horizon is weeks, where funding dwarfs that bias). Published in
# extra.ab_funding_veto; the winner after ~2-4 weeks gets shipped.
#
# [2026-07-17 EPOCH 2 — the instrument was measuring nothing] v1's A/B
# differed from the real book in THREE variables at once, so no divergence
# was attributable: (a) it was bootstrapped mid-cycle at its own entry
# prices, i.e. a different window; (b) it carried NO seatbelt while the real
# book did; (c) the veto was checked ONLY at rebalance. On 17-Jul it read
# eq $829.30 vs the real book's $872.21 — which invites "the funding veto
# loses $43" when in fact last_vetoed was EMPTY (the veto had never once
# fired) and the whole $43 was the seatbelt. Epoch 2 makes the veto the ONLY
# variable: the ledger is SEEDED from the real book (identical positions,
# entries, accrual, marks -> both start at the same equity, so all later
# divergence is the veto), it MIRRORS the seatbelt and the rail flatten, and
# the veto runs CONTINUOUSLY. Continuity matters because the spike is the
# whole cost: SNDK/NBIS entered affordable and only later printed ~967%/687%
# apr — an entry-only veto cannot see the carry that actually gets paid.
# Epoch stamped in extra.ab_funding_veto.epoch; pre-epoch numbers are void.
AB_VETO_APR = float(os.environ.get("MOMO_AB_VETO_APR", "0.1875"))  # /8 basis fix = 18.75% TRUE

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
    ref = REF_MAP.get(symbol, symbol)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ref, safe='')}?range=2y&interval=1d")
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

    # [2026-07-17 RETIRED] The shadow record KILLED the go-live — exactly what
    # the guard below promised it could. Recording why, because the obvious
    # reading is wrong:
    #   The RULE is not what failed. 86% of the 4-day loss that prompted the
    #   review was a real market-wide crash (SNDK/MRVL/NBIS/MU printed
    #   -18.3/-18.7/-20.7/-10.1% on Yahoo over the same window) on n=3 fills,
    #   well inside this strategy's own backtested envelope. Nothing was tuned.
    #   What failed is that it cannot promote AT ANY SIZE WORTH THE SLOT:
    #   * maxDD 37-44% with ZERO funding modelled (four independent harnesses;
    #     this file's own header says 36.9-44.3%) against the fleet's go-live
    #     gate of maxDD < 15% (CLAUDE.md Rules) — 2.5-3x over before a cent of
    #     carry. A one-path maxDD is downward-biased, so the truth is worse.
    #   * SIZING is the only lever that touches DD, and DD scales SUBLINEARLY:
    #     the only deployment clearing 15% is 15% ($30/slot) -> 6.7% CAGR /
    #     13.9% maxDD = ~$67/yr on the $1000 book. Strip the ~38% hindsight
    #     premium (names unselectable at window start) -> ~$42/yr: at or BELOW
    #     risk-free cash, for a 14% drawdown. Cutting size 6x only halves DD
    #     while cutting return 5x.
    #   * Every other design fails too (~10 tested): best-of-field 28%-band
    #     universe +7.2% CAGR / -39.5% DD, failing both halves; top-3 -67.6%.
    #     Carry is TIME-based (drag 29.5/28.4/29.1pp at 7/14/28d rebalance) so
    #     trading less cannot outrun it.
    #   * FUNDING WAS NEVER THE PROBLEM: ~8% TRUE apr against a ~52% breakeven.
    #     The "98-967% apr" read was 8x inflated — the venue's rate is an 8-HOUR
    #     fraction annualised as hourly fleet-wide (see the BASIS STAMP in
    #     lighter_market_scout.py + 21-Jul agenda item 16). The companion
    #     "momentum ranks crowding" claim was REFUTED (Spearman -0.174, p=0.40).
    #   * The header's +43.7%/44.3% is itself a GRID ARTIFACT (union-of-25 grid
    #     annualising 15.3y as 19.9 and freezing stock legs on ~26% of rows).
    # Ledger + row history KEPT (paper_trades, bot_state). Row hidden via
    # RETIRED_ROWS in pnl_dashboard.py. A code guard rather than `railway down`
    # because Railway auto-deploy RESURRECTS stopped services on git push.
    # TO UN-RETIRE: set MOMO_RETIRED=off (or revert this block) and drop
    # "equities-momentum-lshadow" from RETIRED_ROWS.
    if os.environ.get("MOMO_RETIRED", "on").strip().lower() \
            not in ("off", "0", "false", "no"):
        raise SystemExit(
            "equities-momentum is RETIRED (2026-07-17). maxDD 37-44% vs the "
            "fleet's 15% go-live gate, and the only deployment that clears the "
            "gate earns ~$42-67/yr — at or below risk-free. The momentum rule "
            "is NOT what failed (n=3 fills, a real market crash); the venue fit "
            "at a size worth the slot is. See the block above. "
            "MOMO_RETIRED=off to run it anyway.")

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
    ab_meta = {}          # A/B virtual book: sym -> {entry, size, accrued, mark}
    ab_realized = 0.0
    ab_fund_realized = 0.0   # funding component only — lets the review say
                             # how much of any edge is CARRY vs price luck
    ab_vetoed = []        # entry-vetoes at the last rebalance
    ab_veto_exits = []    # CONTINUOUS veto exits since the epoch. Without
                          # this the payload shows the variant holding fewer
                          # names than the real book with `last_vetoed: []`
                          # beside it — unreadable, and exactly the kind of
                          # silent mismatch that made the v1 A/B misleading.
    ab_base = None        # [EPOCH 2] closed-book equity at the seed instant;
    ab_epoch = None       # None -> seed from the real book on this loop
    saved = store.load_state(bot_id)
    if saved and broker.restore_state(saved.get("broker") or {}):
        meta = {str(k): v for k, v in (saved.get("meta") or {}).items()}
        fund_realized = float(saved.get("fund_realized") or 0.0)
        next_reb = float(saved.get("next_reb") or 0.0)
        ab_meta = {str(k): v for k, v in (saved.get("ab_meta") or {}).items()}
        ab_realized = float(saved.get("ab_realized") or 0.0)
        ab_fund_realized = float(saved.get("ab_fund_realized") or 0.0)
        ab_veto_exits[:] = list(saved.get("ab_veto_exits") or [])
        ab_epoch = saved.get("ab_epoch")
        _ab = saved.get("ab_base")
        ab_base = float(_ab) if _ab is not None else None
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

    def ab_equity():
        # [EPOCH 2] ab_base is the real book's CLOSED-book equity at the seed
        # instant, so ab_equity() == equity() to the cent at the epoch and
        # every later dollar of divergence is the veto's doing. START_EQUITY
        # only applies before the first seed.
        out = (START_EQUITY if ab_base is None else ab_base) + ab_realized
        for m in ab_meta.values():
            mark = m.get("mark") or m["entry"]
            out += m["size"] * (mark - m["entry"]) + m.get("accrued", 0.0)
        return out

    def ab_close(s, px, reason):
        """Realise a virtual leg. The A/B mirrors EVERY exit the real book
        takes (seatbelt, rail flatten, rotation) so the funding veto stays the
        only variable — plus the veto's own exit, which is what's under test."""
        nonlocal ab_realized, ab_fund_realized
        m = ab_meta.pop(s, None)
        if not m:
            return
        px = px or m["entry"]
        pnl = m["size"] * (px - m["entry"])
        fnd = m.get("accrued", 0.0)
        ab_realized += pnl + fnd
        ab_fund_realized += fnd
        if reason == "funding_veto":
            ab_veto_exits.append({"sym": s, "at": datetime.now(timezone.utc)
                                  .isoformat(), "fund": round(fnd, 3)})
            del ab_veto_exits[:-20]        # keep the payload bounded
        log.info("AB CLOSE %s | price %+.2f funding %+.2f [%s]",
                 s, pnl, fnd, reason)

    def ab_seed():
        """[EPOCH 2] Start the variant FROM the real book: identical legs,
        entries, accrual and marks, plus a base equity that makes the two
        ledgers agree right now. v1 bootstrapped at its own prices in its own
        window — which is why its $43 gap measured the seatbelt, not the veto."""
        nonlocal ab_meta, ab_realized, ab_fund_realized, ab_base, ab_epoch
        ab_meta = {s: {"entry": ent, "size": abs(sz),
                       "accrued": (meta.get(s) or {}).get("accrued", 0.0),
                       "mark": broker.marks.get(s) or ent}
                   for s, (sz, ent) in broker.pos.items()}
        ab_realized = ab_fund_realized = 0.0
        del ab_veto_exits[:]           # a new epoch starts with a clean slate
        # Closed-book equity: total less what the open legs contribute, since
        # ab_equity() re-adds exactly those legs back out of ab_meta.
        ab_base = broker.equity() - broker.unrealized() + fund_realized
        ab_epoch = datetime.now(timezone.utc).isoformat()
        log.info("A/B EPOCH 2 seeded from the real book | base $%.2f | eq "
                 "$%.2f == real $%.2f | mirroring %s | veto >%.0f%%apr "
                 "CONTINUOUS", ab_base, ab_equity(), equity(),
                 ", ".join(sorted(ab_meta)) or "flat", AB_VETO_APR * 100)

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
    day_start_equity = equity()
    # [2026-07-17 AUDIT FIX] the daily-loss rail lost its BASELINE on every
    # restart: day_start_equity re-based to boot equity, so a redeploy part
    # way down a losing day re-anchored the 10% rail to the already-depressed
    # number and it could no longer fire on that day's drawdown. The baseline
    # now rides the persisted state (same UTC day only) or the saved halt
    # record. Same class as the 16-Jul last_ts fix below.
    # NOTE the two LIVE bots (lighter_funding_bot / lighter_trend_bot) carry
    # only the narrower halt-record half of this, so they still re-base on a
    # PRE-halt restart — real money, logged for the 21-Jul review, not
    # touched here.
    _halt = store.load_daily_halt(bot_id, cur_day.isoformat())
    if _halt:
        halted_today = True
        day_start_equity = _halt.get("day_start_equity") or day_start_equity
        log.warning("daily-loss halt restored — halted for today.")
    elif (saved or {}).get("day") == cur_day.isoformat():
        try:
            day_start_equity = float(saved["day_start_equity"])
            log.info("daily-rail baseline restored from state: $%.2f",
                     day_start_equity)
        except (KeyError, TypeError, ValueError):
            pass
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
                    px = marks.fresh_mid(venue, s) or meta[s].get("entry")
                    close_pos(s, px, "rail_flatten")
                # [EPOCH 2] the variant mirrors the rail too — it exists to
                # isolate the funding veto, not to also test "no daily rail".
                for s in list(ab_meta):
                    ab_close(s, marks.fresh_mid(venue, s), "rail_flatten")

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

        # [EPOCH 2] Seed BEFORE this loop's mark/accrue, never after: seeding
        # afterwards copied an `accrued` the real book had ALREADY advanced by
        # dt_h and then advanced it again in the A/B pass — one loop of double
        # funding, which showed up as a $0.01 epoch drift that must be exactly
        # $0.00. Seeding here, both books enter the loop identical and each
        # applies the same dt_h once. (ab_base is mark-independent: the
        # unrealized term cancels, leaving start+realized-fees+fund_realized.)
        if ab_epoch is None:
            ab_seed()

        # ---- mark + accrue + seatbelt (every loop, all held) ----
        for s in list(meta):
            px = marks.fresh_mid(venue, s)
            if not px:
                continue
            broker.mark(s, px)
            rate = (fund.get(s) or {}).get("rate")
            if rate is not None:
                szv = abs(broker.pos.get(s, (0.0, 0.0))[0])
                meta[s]["accrued"] = (meta[s].get("accrued", 0.0)   # [BASIS FIX] /8
                                      - funding_basis.to_hourly(rate, "lighter")
                                      * szv * px * dt_h)
            entry = meta[s].get("entry") or 0.0
            if entry and (px - entry) / entry <= -CATASTROPHIC_STOP:
                close_pos(s, px, "catastrophic_stop")

        # ---- A/B virtual book: mark + accrue + MIRRORED seatbelt + the
        # continuous funding veto (the one variable). Seeded at the loop top. --
        for s in list(ab_meta):
            m = ab_meta[s]
            px = marks.fresh_mid(venue, s)
            if not px:
                continue
            m["mark"] = px
            rate = (fund.get(s) or {}).get("rate")
            if rate is not None:
                m["accrued"] = (m.get("accrued", 0.0)               # [BASIS FIX] /8
                                - funding_basis.to_hourly(rate, "lighter")
                                * m["size"] * px * dt_h)
            entry = m.get("entry") or 0.0
            if entry and (px - entry) / entry <= -CATASTROPHIC_STOP:
                ab_close(s, px, "catastrophic_stop")   # mirrors the real book
                continue
            # THE VARIABLE UNDER TEST: bail out of a leg whose carry has spiked
            # past the bar. v1 checked only at entry and so never saw the cost
            # that actually gets paid — SNDK/NBIS entered affordable and only
            # later printed ~967%/687% apr. The freed slot stays CASH until the
            # next weekly rebalance: back-filling mid-week would smuggle a
            # second variable (rotation cadence) into the comparison.
            if rate is not None and funding_basis.to_apr(rate, 'lighter') > AB_VETO_APR:
                ab_close(s, px, "funding_veto")

        # ---- weekly rotation ----
        # [2026-07-17 STORM FIX] the trigger used to be
        # `t0 >= next_reb or (meta and not ab_meta)` — a mid-cycle bootstrap
        # for the A/B ledger. But that disjunct re-fires EVERY loop for as
        # long as the variant is flat while the real book holds, which is
        # precisely what a fully-vetoed top-5 produces (SNDK 967% / NBIS 687%
        # apr are one bad week away from it). It would silently demote the
        # WEEKLY rotation the backtest validated to a ~6-hourly one (bounded
        # only by the Yahoo cache TTL) — and the same sweep already found
        # daily WORSE than weekly (maxDD 40.7 vs 36.9%, 176 vs 81 switches/yr).
        # The variant now seeds itself once from the real book (ab_seed), so
        # the rebalance is the clock and nothing else.
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
                             funding_basis.to_apr_pct((fund.get(s) or {}).get('rate') or 0, 'lighter'))
                # ---- A/B: funding-veto variant rebalance (virtual fills) ----
                apr = {s: funding_basis.to_apr((fund.get(s) or {}).get('rate') or 0, 'lighter')
                       for s in symbols}
                q = [(s, ev) for s, ev in evals.items()
                     if ev and ev["is_long"] and ev["momentum"] is not None
                     and apr.get(s, 0) <= AB_VETO_APR]
                q.sort(key=lambda kv: kv[1]["momentum"], reverse=True)
                ab_want = [s for s, _ in q[:TOP_N]]
                ab_vetoed = [s for s in want
                             if s not in ab_want and apr.get(s, 0) > AB_VETO_APR]
                for s in list(ab_meta):
                    if s not in ab_want:
                        ab_close(s, marks.fresh_mid(venue, s), "rotated_out")
                for s in ab_want:
                    if s in ab_meta:
                        continue
                    px = marks.fresh_mid(venue, s)
                    if px:
                        # [EPOCH 2] when the real book entered this same name
                        # at THIS rebalance, take its ACTUAL crossed fill: a
                        # mid fill would hand the variant a free half-spread
                        # on every shared leg, and that is not the veto's
                        # doing. A leg the real book holds from an earlier
                        # rebalance is genuine veto-driven divergence — the
                        # variant is entering it fresh, so mid is correct.
                        # Mirror the real book EXACTLY on a shared leg: it
                        # sizes off the mid, fills crossed, and marks at its
                        # own fill (so it shows no crossing cost until the
                        # next loop). Sizing off `ent` or marking at mid here
                        # would re-introduce a spread-shaped difference that
                        # the veto would then get blamed or credited for.
                        _m = meta.get(s) or {}
                        ent = _m["entry"] if _m.get("opened_ts") == t0 else px
                        ab_meta[s] = {"entry": ent, "size": ORDER_USD / px,
                                      "accrued": 0.0, "mark": ent}
                if ab_vetoed:
                    log.info("A/B veto: %s (funding > %.0f%%apr) -> variant "
                             "holds %s", ", ".join(ab_vetoed),
                             AB_VETO_APR * 100, ", ".join(sorted(ab_meta)))
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
                       # [EPOCH 2] `epoch` is when the two ledgers were made
                       # identical — the comparison means NOTHING before it.
                       # vs_real is the headline (ab minus real, same instant,
                       # same start); fund_paid vs the real book's
                       # fund_realized+fund_open attributes any edge to CARRY
                       # rather than price luck.
                       "ab_funding_veto": {"eq": round(ab_equity(), 2),
                                           "vs_real": round(ab_equity() - equity(), 2),
                                           "epoch": ab_epoch,
                                           "base": round(ab_base, 2)
                                           if ab_base is not None else None,
                                           "fund_paid": round(
                                               ab_fund_realized
                                               + sum((m or {}).get("accrued", 0.0)
                                                     for m in ab_meta.values()), 4),
                                           "held": sorted(ab_meta),
                                           "veto_apr": AB_VETO_APR,
                                           "last_vetoed": ab_vetoed,
                                           "veto_exits": ab_veto_exits},
                       "next_reb": datetime.fromtimestamp(
                           next_reb, tz=timezone.utc).isoformat() if next_reb else None,
                       "skipped_unlisted": skipped})
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "fund_realized": fund_realized,
                                      "ab_meta": ab_meta,
                                      "ab_realized": ab_realized,
                                      "ab_fund_realized": ab_fund_realized,
                                      "ab_veto_exits": ab_veto_exits,
                                      "ab_base": ab_base,
                                      "ab_epoch": ab_epoch,
                                      "next_reb": next_reb,
                                      "last_ts": last_ts,
                                      # daily-rail baseline rides the state so
                                      # a restart can't re-base it (see boot)
                                      "day": cur_day.isoformat(),
                                      "day_start_equity": day_start_equity})
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
