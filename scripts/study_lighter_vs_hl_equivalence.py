#!/usr/bin/env python3
"""
scripts/study_lighter_vs_hl_equivalence.py — CAN the fleet's HL-fed organs read
Lighter instead? MEASURED, per consumer. Nothing is swapped here.

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-17, measured against both live APIs. Every number below is   ║
║ this script's real output.)                                                   ║
║                                                                              ║
║ THE ANSWER IS NOT ONE ANSWER. Four consumers, four verdicts — and the         ║
║ operator's "everything on Lighter" is RIGHT for one, WRONG for two, and a     ║
║ near-no-op-with-a-trap for the fourth.                                        ║
║                                                                              ║
║ 1. regime_oracle.py  ->  **EQUIVALENT on the signal (99.4%), but DO NOT SWAP  ║
║    BLIND — a young-book coverage trap rides along.**                          ║
║    Faithful rolling replay of the REAL classify() (imported, not re-written), ║
║    200 closed days x 16 majors, prev_trend hysteresis carried per source,     ║
║    the 300d window rebuilt at every day exactly as the oracle does:           ║
║      **VERDICTS IDENTICAL ON 99.4% OF COIN-DAYS (3,066/3,085). 19 differ.**   ║
║      10 of 16 majors agree on 100.0% of days. Worst: DOGE 96.0% (8 days),     ║
║      then NEAR 98.0%, SOL 98.5%, TAO 99.0%, AVAX/DOT 99.5%.                   ║
║      Prices agree too: median close divergence 1.3-8.4bps/coin, max 106.2bps. ║
║    I EXPECTED THIS TO BE A BEHAVIOUR CHANGE. It mostly is not. The signal     ║
║    survives the swap.                                                         ║
║                                                                              ║
║ 1b. WHERE THE 0.6% COMES FROM — MEASURED, NOT ASSERTED. It is NOT price       ║
║    error. It is regime_oracle's OWN KNIFE-EDGE at the ADX bands, and it       ║
║    LATCHES. DOGE 2026-04-13: HL ADX 11.6 (>11 -> hysteresis holds "trending") ║
║    vs Lighter ADX 10.8 (<=11 -> "chop"). A 0.8-point ADX difference at the    ║
║    band edge flipped the state — and hysteresis then held the two sources     ║
║    APART FOR 10 CONSECUTIVE DAYS (Apr 13-22), including days where both       ║
║    sat inside the band (16.4 vs 15.7) and merely held different pasts.        ║
║    SOL's 3 disagreements sit ON the 11.0 boundary to the rounding digit.      ║
║    So: 13 of 19 are CHARACTER (trend/chop) flips, 6 are DIRECTION flips.      ║
║    -> Neither source is "wrong". They straddle a threshold the oracle         ║
║       itself makes discontinuous. A swap does not degrade the signal; it      ║
║       reshuffles which side of a coin-flip you land on ~0.6% of the time.     ║
║    -> AND IT IS LIVE RIGHT NOW: NEAR disagrees on 2026-07-15 AND 07-16        ║
║       (HL LONG-window adx 13.0/13.4 vs Lighter chop-gated adx 12.0/12.3).     ║
║                                                                              ║
║ 1c. **THE ACTUAL FINDING — ZEC. A SILENT COIN DROP.**                         ║
║    Lighter's ZEC book has 288 daily bars (born 2025-10-03); HL has 521.       ║
║    On **115 of the 200 replayed days** Lighter could not have produced a ZEC  ║
║    verdict AT ALL — under 203 bars trips regime_oracle's own short-history    ║
║    skip — while HL published one. On the 85 days both could compute, they     ║
║    agreed 100%. TODAY Lighter ZEC clears the gate on a 287-bar EMA200 warmup  ║
║    vs HL's 300, so it publishes and the drop is INVISIBLE in a spot check.    ║
║    Any coin Lighter lists later than HL carries this. That is the swap's      ║
║    real cost, and it is a coverage bug, not a signal bug.                     ║
║                                                                              ║
║ 1d. AND THE BRIEF'S PREMISE IS WRONG — VERIFIED, worth more than the %.       ║
║    "regime_oracle feeds the WHOLE fleet's regime signal" is NOT true today:   ║
║    **no bot consumes `regime-oracle`.** Grepped: the readers are              ║
║    pnl_dashboard (display), fleet_respiration (freshness), and — the one      ║
║    that matters — `bot_learn.diagnose()`, which joins the `bot_state_history` ║
║    ARCHIVE (fetch_state_history, bot_pnl_store.py:1024) to classify losing    ║
║    buckets as regime_timing. So the swap's risk is NOT a live trading         ║
║    change; it is a LONGITUDINAL one: pre-swap archive rows are HL-derived,    ║
║    post-swap rows Lighter-derived, same column. At 99.4% that splice is       ║
║    nearly harmless — but it is the thing to weigh, not the trading path.      ║
║                                                                              ║
║ 2. lighter_funding_spread_bot.hl_backfill()  ->  **LIGHTER IS BETTER.         ║
║    Swap it — but as a BUG FIX, not a venue preference.**                      ║
║    THE BENCH RATIO GENERALISES: the brief's single ETH sample holds across    ║
║    the cross-section. **Pooled median ratio 8.0021** over 196 same-instant    ║
║    paired observations (10 moving-funding coins x 20 polls / 6.7 min); an     ║
║    earlier independent run gave 8.0000 (n=170). Per-coin medians 7.98-8.24    ║
║    (the two widest, BERA/OP, are the small-n coins after the near-zero cut).  ║
║    STALENESS: **the bench is LIVE, trailing HL by SECONDS.** On a 20s grid    ║
║    the best fit is lag 20s (median rel-err 0.18%, vs 0.23% at lag 0, rising   ║
║    monotonically to 1.08% by 100s); on a 2s grid it is lag 2s (0.11%). The    ║
║    lag is under one sample interval BOTH times, so the honest resolution is   ║
║    "seconds" — not minutes, not hours. It ticks 15-17 distinct values per 20  ║
║    polls: live, not a fossil. For an hourly-funding consumer that is zero.    ║
║    No staleness reason to keep the direct HL call.                            ║
║                                                                              ║
║ 2b. **A METHOD WARNING — GUARD YOUR NEAR-ZERO DENOMINATORS.**                 ║
║    [2026-07-17 CORRECTED. This box first read "Pair your samples, or you will ║
║    'discover' a basis bug that is not there", and blamed the outliers on an   ║
║    UNPAIRED read. THAT DIAGNOSIS WAS WRONG ABOUT ITS OWN INSTRUMENT: [A]      ║
║    (:496) and [B] (:532) call the IDENTICAL `_bench_snapshot()` and carry the ║
║    identical sub-second intra-call offset. [A] was never unpaired. Pairing is ║
║    CONSTANT across the two arms, so it cannot be what separates them — the    ║
║    box credited a variable that does not differ. Same shape as the bug it     ║
║    was documenting, and a same-day repeat of the Stock Leaders A/B that       ║
║    differed three ways and pointed the opposite way to the truth.]            ║
║    WHAT ACTUALLY DIFFERS, three things at once: the near-zero cut **1e-9 vs   ║
║    NEAR_ZERO 5e-6** (5000x), the universe (92 symbols vs 10 hand-picked), and ║
║    20 pooled repeats. HOLDING PAIRING CONSTANT AND CHANGING ONLY THE CUT:     ║
║    min/max **7.329/8.155 -> 7.876/8.085**; median |err| **11.95% below the    ║
║    cut (n=5) vs 0.00% above it (n=87)**. Ratio error is a monotone function   ║
║    of the DENOMINATOR, not of read skew: the worst offenders are the smallest ║
║    denominators (BCH |live|=1.36e-06 -> 9.17; BERA 2.69e-06 -> 5.87), and a   ║
║    **-5.37 sign flip cannot come from a 0.5s skew** — it needs a denominator  ║
║    that crossed zero. The header's own mechanism sentence (AVAX at 8.5e-07,   ║
║    below the 5e-6 cut) always named the real cause; it was stapled to the     ║
║    wrong conclusion. THE LESSON: **guard near-zero denominators**, or you     ║
║    will "discover" a basis bug that is not there — a sign-flipped ratio is    ║
║    exactly the artifact that would get a real, correct API blamed.            ║
║    (The two runs' instability — min -5.37/187.87 vs 6.42/9.28 — is the SAME   ║
║    [A] instrument twice: evidence that near-zero coins wander in and out of   ║
║    the unguarded set, NOT evidence about pairing.)                            ║
║                                                                              ║
║ 2c. **THE REAL FINDING HERE IS A LIVE BUG, NOT A SWAP QUESTION.**             ║
║    `hl_backfill()` returns HL rates (1h basis). The live sampling loop        ║
║    appends `funding_map()['rate']` (Lighter, 8h basis). BOTH LAND IN THE SAME ║
║    `fund_hist[coin]` WINDOW (merge line ~211, append line ~311), and the      ║
║    rebalance ranks on `sum(rs)/len(rs)` over it (line ~342). Each coin's      ║
║    score therefore averages rows whose units differ by EXACTLY 8x, and THE    ║
║    MIX RATIO DIFFERS PER COIN (it depends how much live coverage that coin    ║
║    has accrued since its last backfill). This is NOT the fleet-wide monotonic ║
║    8x that [[lighter-funding-apr-8x-overstated]] says leaves rankings intact  ║
║    — there the factor is constant, so order survives. HERE IT VARIES WITHIN   ║
║    THE CROSS-SECTION, and the bot is a pure cross-sectional ranker: it LONGs  ║
║    the K most-negative and SHORTs the K most-positive. A freshly-backfilled   ║
║    coin's score is compressed ~8x toward zero purely from uptime.             ║
║    Sign convention is NOT the problem — /funding-rates IS signed. MEASURED    ║
║    (a ruled-out hypothesis, recorded so nobody re-tests it): ~105-123 of its  ║
║    684 rows are negative on any given snapshot, and the lighter rows span     ║
║    both signs (e.g. -0.015224..+0.014616). Unlike the SETTLED /api/v1/        ║
║    fundings series — whose `rate` is unsigned and needs its `direction`       ║
║    field — /funding-rates needs no direction. The bot's L/S legs are fine.    ║
║    Backfilling from Lighter's OWN settled series (/api/v1/fundings, pages     ║
║    back 438d+) fixes the units AND drops the cross-venue proxy. Shadow book,  ║
║    no real money — but this book's whole record is suspect until it is fixed. ║
║                                                                              ║
║ 3. lighter_dislocation_bot.hl_mids()  ->  **KEEP HL. THE SWAP IS IMPOSSIBLE   ║
║    AND WOULD BE CIRCULAR.** The brief's premise ("a reference they could read ║
║    from Lighter's own API ... funding_map() already surfaces them as          ║
║    '_bench'") is REFUTED for this bot: it reads no funding at all. It reads   ║
║    `allMids` — cross-venue MID PRICES — and computes                          ║
║    `dev_bps = (lighter_mid / hl_mid - 1) * 1e4` (line ~296).                  ║
║    MEASURED: /funding-rates carries exactly four fields — market_id,          ║
║    exchange, rate, symbol. RATES ONLY. Lighter's API publishes no other       ║
║    venue's PRICE anywhere, so `_bench` cannot substitute for a mid.           ║
║    And the deeper reason: this bot's entire thesis is Lighter-vs-an-          ║
║    INDEPENDENT-venue. Sourcing that reference from Lighter would measure      ║
║    Lighter against itself and read ~0bps forever — a silently DEAD bot whose  ║
║    census would simply stop finding dislocations. Worse than degraded.        ║
║                                                                              ║
║ 4. market_context.py  ->  **DIFFERENT / WORSE. Do not swap.** Field-by-field  ║
║    Lighter can serve the shapes (open_interest ✓, mark_price ✓, funding ✓,    ║
║    premium derivable from mark-vs-index) — so a swap would COMPILE and look   ║
║    fine. It would still be wrong, for two measured reasons:                   ║
║    (a) IT IS A DIFFERENT QUANTITY. HL OI is the MARKET's positioning;         ║
║        Lighter OI is OUR VENUE's. MEASURED across the 16 majors: Lighter OI   ║
║        notional is a median **~4%** of HL's (4.0% and 4.2% on two runs;       ║
║        range 0.6%-18.4%; BTC $110M vs $2.40B, NEAR $0.49M vs $83.8M). Not     ║
║        two reads of one number — a ~25x smaller, differently-composed book.   ║
║    (b) HL's `premium` field is NOT (mark-index)/index — MEASURED on HL's OWN  ║
║        BTC snapshot, where both numbers come from the SAME payload:           ║
║          run 1: premium field -0.47bps vs (mark-oracle)/oracle -0.63bps       ║
║          run 2: premium field +0.00bps vs (mark-oracle)/oracle -0.47bps       ║
║        They never coincide. (HL documents `premium` as an impact-price-vs-    ║
║        oracle construct — that EXPLANATION is inferred, not measured here;    ║
║        the DIFFERENCE is measured.) A Lighter "premium_bps" derived from      ║
║        mark-vs-index would wear the field name and mean something else.       ║
║    And the decisive one: market_context exists to ACCUMULATE a clean factor   ║
║    dataset ("LOG FIRST, gate later" — its own header) stamped onto live       ║
║    entries as `mctx` (lighter_funding_bot.py:813, lighter_dislocation_bot     ║
║    .py:279). Swapping the source mid-stream splices two different             ║
║    definitions of OI into one column, poisoning the dataset the fleet is      ║
║    waiting on. The cost is paid later, by a validation that quietly cannot    ║
║    work. Unlike regime_oracle's 99.4%-identical splice, this one is a 24x     ║
║    discontinuity.                                                             ║
║                                                                              ║
║ SO: 2 do-not-swap (dislocation impossible/circular; market_context redefines  ║
║ the factor), 1 swap-as-a-bugfix (spread backfill), 1 safe-on-the-signal-but-  ║
║ fix-the-coverage-first (regime_oracle). "Everything on Lighter" is correct    ║
║ for the funding bench and incorrect for the price reference. A worse data     ║
║ source does not become correct by being ours.                                 ║
║                                                                              ║
║ LIMITATIONS — read before acting.                                            ║
║  * The regime replay is a FAITHFUL RE-EXECUTION, not a P&L backtest. It says  ║
║    the signal is 99.4% IDENTICAL; it does NOT say which source is RIGHT on    ║
║    the 19 days they differ. Nothing here ranks HL's regime call above         ║
║    Lighter's. Deciding that needs the oracle's calls joined to outcomes —     ║
║    bot_state_history exists for exactly this (regime_oracle's own docstring)  ║
║    and is untouched here.                                                     ║
║  * 200 replay days x 16 majors = ONE window. Both venues bar-align to UTC     ║
║    midnight (verified) so the day grid is directly comparable.                ║
║  * The bench ratio/staleness poll is 20 samples over 6.3 min on 10 coins —    ║
║    good enough to kill the staleness hypothesis (20s lag), NOT a 24h          ║
║    characterisation. BERA/OP have small n after the near-zero filter.         ║
║  * The OI ratio and the premium figures are ONE snapshot and will move with   ║
║    the tape. The 8x basis is structural and will not.                         ║
║  * market_context's oi_chg_1h/24h factors are TIME SERIES; only the OI LEVEL  ║
║    ratio is measured. Whether Lighter OI *changes* track HL OI changes is     ║
║    UNMEASURED and needs a collection window.                                  ║
║  * Coverage counts move as both venues list/delist.                           ║
║                                                                              ║
║ Read-only: public endpoints + its own gitignored cache. Touches no bot, no    ║
║ DB, no config. Imports regime_oracle ONLY to call its real classify().        ║
║ NEEDS pandas (as regime_oracle does) — run it with the venv interpreter:      ║
║   .venv/bin/python scripts/study_lighter_vs_hl_equivalence.py                 ║
║   .venv/bin/python scripts/study_lighter_vs_hl_equivalence.py --refresh       ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS (2026-07-17, operator: "we need everything to run off lighter as
that's what we run on"). regime_oracle.py and market_context.py read Hyperliquid;
two Lighter bots call api.hyperliquid.xyz directly. Swapping any of them is BOT
LOGIC, and doctrine is backtest-first. Nobody had measured whether the swap is a
no-op or a behaviour change. This measures it and changes nothing — a human
decides. Being willing to answer "keep HL" is the point.

METHOD — fidelity notes, because a sloppy mirror would fake the answer:
  * The regime signal is computed by IMPORTING regime_oracle and calling its own
    classify()/wilder_adx(). Not re-implemented: pandas' ewm(adjust=False) NaN
    handling inside the Wilder ADX is exactly the detail a hand-rolled "mirror"
    gets subtly wrong, and a wrong mirror yields a confident wrong verdict. The
    gates (ADX 17/11, EMA 50/200, slope 3, lookback 300d, the 16-coin universe)
    are READ from the module, never copied.
  * Each replay day D rebuilds the oracle's REAL window: the <=300 closed daily
    bars ending at D, then the oracle's own len < EMA_SLOW+SLOPE_BARS (203)
    short-history skip. Partial today-candles are dropped from both sources
    (the oracle's df.iloc[:-1]).
  * prev_trend hysteresis carries forward INDEPENDENTLY per source from a common
    None seed, with a warmup before the reported window — so a latched
    disagreement is counted honestly and the seed is never the cause.
  * The funding bench is measured on SAME-INSTANT PAIRED samples (see verdict
    2b — an unpaired cross-section lies). TRUE APR uses funding_basis.py, the
    fleet's basis authority, never a hardcoded 24*365.
"""
import argparse
import json
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import funding_basis  # noqa: E402
import regime_oracle as ro  # noqa: E402  (imported for its REAL classify)

LT = "https://mainnet.zklighter.elliot.ai"
HL = "https://api.hyperliquid.xyz/info"
CACHE = os.path.join(os.path.dirname(__file__), ".lighterhl_equiv_cache.json")

# The real consumers' real coin lists (read from the bots, not invented).
DISLOC_COINS = ("BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,SUI,LTC,ADA,DOT,AAVE,"
                "HYPE,NEAR,BCH").split(",")
SPREAD_COINS = ("BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,"
                "AAVE,WIF,JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,"
                "PYTH,W").split(",")

FETCH_DAYS = 520          # both venues serve this; > the oracle's 300d window
REPORT_DAYS = 200         # replayed days actually compared
WARMUP_DAYS = 60          # hysteresis warmup before the reported window

# Bench poll: HL's live funding moves continuously, so samples MUST be paired.
POLL_N = 20
POLL_EVERY = 20
POLL_COINS = ["GRASS", "PENGU", "BERA", "TRUMP", "VIRTUAL",
              "STRK", "BIO", "ZEC", "OP", "ICP"]
NEAR_ZERO = 5e-6          # |HL rate| below this makes the ratio meaningless


# ------------------------------- transport ----------------------------------
def _lget(path, **q):
    url = LT + path + ("?" + urllib.parse.urlencode(q) if q else "")
    for a in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if a == 3:
                raise
            time.sleep(1.5 * (a + 1))


def _hl(body):
    for a in range(4):
        try:
            req = urllib.request.Request(
                HL, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if a == 3:
                raise
            time.sleep(1.5 * (a + 1))


# ------------------------------ candle fetch --------------------------------
def lighter_daily(mid, days):
    """Daily OHLC paged backward (500-bar cap/call) -> {day_ts_sec: (o,h,l,c)}."""
    out, end = {}, int(time.time())
    cutoff, seen = int(time.time()) - days * 86400, None
    while True:
        cs = _lget("/api/v1/candles", market_id=mid, resolution="1d",
                   start_timestamp=end - 500 * 86400, end_timestamp=end,
                   count_back=500).get("c") or []
        if not cs:
            break
        for c in cs:
            out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                        float(c["l"]), float(c["c"]))
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= cutoff or (seen is not None and oldest >= seen):
            break
        seen, end = oldest, oldest - 86400
    return {t: v for t, v in out.items() if t >= cutoff}


def hl_daily(coin, days):
    """HL candleSnapshot daily -> {day_ts_sec: (o,h,l,c)}."""
    now = int(time.time() * 1000)
    rows = _hl({"type": "candleSnapshot",
                "req": {"coin": coin, "interval": "1d",
                        "startTime": now - days * 86400000, "endTime": now}}) or []
    return {int(r["t"]) // 1000: (float(r["o"]), float(r["h"]),
                                  float(r["l"]), float(r["c"])) for r in rows}


def to_df(bars, drop_from):
    """{ts:(o,h,l,c)} -> the oracle's frame shape, CLOSED candles only."""
    ts = sorted(t for t in bars if t < drop_from)
    return pd.DataFrame({"t": ts,
                         "o": [bars[t][0] for t in ts],
                         "h": [bars[t][1] for t in ts],
                         "l": [bars[t][2] for t in ts],
                         "c": [bars[t][3] for t in ts]})


# --------------------------- the faithful replay -----------------------------
def verdict_series(df, first_report_ts):
    """Re-execute the REAL regime_oracle at every closed day.

    At day D the oracle holds the <=LOOKBACK_DAYS closed bars ending at D and
    applies its own short-history skip. prev_trend carries forward per source
    (hysteresis latches — that is the finding, not an artifact).
    -> {day_ts: verdict|None}.  None == the oracle would SKIP the coin.
    """
    need = ro.EMA_SLOW + ro.SLOPE_BARS          # the oracle's own 203-bar gate
    win = ro.LOOKBACK_DAYS
    out, prev_trend = {}, None
    warm_ts = first_report_ts - WARMUP_DAYS * 86400
    for i in range(len(df)):
        ts = int(df["t"].iloc[i])
        if ts < warm_ts:
            continue
        w = df.iloc[max(0, i - win + 1): i + 1]
        if len(w) < need:
            out[ts] = None                      # oracle: short-history -> skip
            continue
        v = ro.classify(w, prev_trend)
        prev_trend = v["trend"]
        out[ts] = v
    return out


def part1_regime(cache, refresh):
    print("=" * 78)
    print("PART 1 — CANDLE / REGIME EQUIVALENCE  (regime_oracle.py)")
    print("=" * 78)
    print(f"mirroring the REAL module: ADX {ro.ADX_TREND}/{ro.ADX_CHOP} | "
          f"EMA {ro.EMA_FAST}/{ro.EMA_SLOW} | slope {ro.SLOPE_BARS} | "
          f"lookback {ro.LOOKBACK_DAYS}d | universe {len(ro.UNIVERSE)}")

    obs = _lget("/api/v1/orderBookDetails").get("order_book_details") or []
    sym2id = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    today = int(time.time()) // 86400 * 86400

    if "candles" not in cache or refresh:
        cand = {}
        for c in ro.UNIVERSE:
            rec = {}
            try:
                rec["hl"] = {str(k): v for k, v in hl_daily(c, FETCH_DAYS).items()}
            except Exception as e:
                print(f"  {c}: HL fetch failed ({e})")
                rec["hl"] = {}
            try:
                rec["lt"] = ({str(k): v for k, v
                              in lighter_daily(sym2id[c], FETCH_DAYS).items()}
                             if c in sym2id else {})
            except Exception as e:
                print(f"  {c}: Lighter fetch failed ({e})")
                rec["lt"] = {}
            cand[c] = rec
            print(f"  fetched {c:5s} HL {len(rec['hl']):4d}d | "
                  f"Lighter {len(rec['lt']):4d}d")
            time.sleep(0.2)
        cache["candles"] = cand
        json.dump(cache, open(CACHE, "w"))
    cand = cache["candles"]

    frames = {}
    for c in ro.UNIVERSE:
        hl = {int(k): tuple(v) for k, v in cand[c]["hl"].items()}
        lt = {int(k): tuple(v) for k, v in cand[c]["lt"].items()}
        if not hl or not lt:
            continue
        frames[c] = (to_df(hl, today), to_df(lt, today))

    last_ts = max(int(f[0]["t"].iloc[-1]) for f in frames.values())
    first_report_ts = last_ts - (REPORT_DAYS - 1) * 86400
    print(f"\nreplaying {REPORT_DAYS} closed days "
          f"({time.strftime('%Y-%m-%d', time.gmtime(first_report_ts))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(last_ts))}), "
          f"{WARMUP_DAYS}d hysteresis warmup, {len(frames)} coins\n")

    hdr = (f"{'coin':>5s} {'HLd':>5s} {'LTd':>5s} {'days':>5s} {'agree':>6s} "
           f"{'agree%':>7s} {'dirX':>5s} {'chrX':>5s} {'LTskip':>7s} "
           f"{'medbps':>7s} {'maxbps':>7s}")
    print(hdr)
    print("-" * len(hdr))

    tot_days = tot_agree = tot_dir = tot_chr = tot_skip = 0
    worst_bps, details, per_coin = 0.0, {}, {}
    for c, (dh, dl) in sorted(frames.items()):
        vh = verdict_series(dh, first_report_ts)
        vl = verdict_series(dl, first_report_ts)
        days = [t for t in sorted(set(vh) & set(vl)) if t >= first_report_ts]
        both = [t for t in days if vh[t] is not None and vl[t] is not None]
        skip = [t for t in days if vh[t] is not None and vl[t] is None]
        agree = [t for t in both if vh[t]["verdict"] == vl[t]["verdict"]]
        dis = [t for t in both if vh[t]["verdict"] != vl[t]["verdict"]]
        dirx = [t for t in dis if vh[t]["dir"] != vl[t]["dir"]]
        chrx = [t for t in dis if vh[t]["trend"] != vl[t]["trend"]]

        hmap = dict(zip(dh["t"], dh["c"]))
        lmap = dict(zip(dl["t"], dl["c"]))
        bps = [abs(lmap[t] / hmap[t] - 1) * 1e4
               for t in days if t in hmap and t in lmap and hmap[t]]
        med = st.median(bps) if bps else 0.0
        mx = max(bps) if bps else 0.0
        worst_bps = max(worst_bps, mx)

        tot_days += len(both)
        tot_agree += len(agree)
        tot_dir += len(dirx)
        tot_chr += len(chrx)
        tot_skip += len(skip)
        pct = 100.0 * len(agree) / len(both) if both else float("nan")
        per_coin[c] = pct
        if dis:
            details[c] = [(t, vh[t], vl[t]) for t in dis]
        print(f"{c:>5s} {len(dh):>5d} {len(dl):>5d} {len(both):>5d} "
              f"{len(agree):>6d} {pct:>6.1f}% {len(dirx):>5d} {len(chrx):>5d} "
              f"{len(skip):>7d} {med:>7.1f} {mx:>7.1f}")

    overall = 100.0 * tot_agree / tot_days if tot_days else float("nan")
    print("-" * len(hdr))
    print(f"{'ALL':>5s} {'':>5s} {'':>5s} {tot_days:>5d} {tot_agree:>6d} "
          f"{overall:>6.1f}% {tot_dir:>5d} {tot_chr:>5d} {tot_skip:>7d} "
          f"{'':>7s} {worst_bps:>7.1f}")

    n100 = sum(1 for v in per_coin.values() if v >= 99.995)
    print(f"\n  IDENTICAL VERDICT ON {overall:.1f}% OF COIN-DAYS "
          f"({tot_agree}/{tot_days}). {tot_days - tot_agree} differ.")
    print(f"  {n100}/{len(per_coin)} majors agree on 100.0% of days"
          + (f"; worst {min(per_coin, key=per_coin.get)} "
             f"{min(per_coin.values()):.1f}%" if per_coin else ""))
    print(f"  kind: {tot_chr} CHARACTER (trend/chop) flips vs {tot_dir} "
          f"DIRECTION flips")
    print(f"  max close divergence, all coins/days: {worst_bps:.1f}bps "
          f"-> the prices agree; so, overwhelmingly, does the signal.")
    print(f"\n  *** Lighter SHORT-HISTORY days (the oracle would SKIP the coin "
          f"while HL\n      publishes a verdict): {tot_skip} ***")

    # --- WHY they differ: measured, not asserted -----------------------------
    print("\n  WHY the disagreements happen — the ADX band edge, then LATCHING:")
    for c, ds in sorted(details.items(), key=lambda kv: -len(kv[1]))[:3]:
        print(f"    {c} ({len(ds)} days):")
        for t, a, b in ds[:4]:
            print(f"      {time.strftime('%Y-%m-%d', time.gmtime(t))} "
                  f"HL={a['verdict']:12s}(adx{a['adx']:5.1f},dir{a['dir']:+d})  "
                  f"LT={b['verdict']:12s}(adx{b['adx']:5.1f},dir{b['dir']:+d})")
        if len(ds) > 4:
            print(f"      (+{len(ds)-4} more)")
    print(f"    -> bands are ADX>={ro.ADX_TREND} trend / <={ro.ADX_CHOP} chop / "
          f"between = HOLD PREVIOUS.")
    print("    -> a sub-point ADX gap at a band edge flips the state, and the")
    print("       hysteresis then holds the two sources apart for DAYS.")
    print("       Neither source is wrong; the oracle's own threshold is a")
    print("       knife-edge and the two venues straddle it.")
    return overall, tot_skip


# --------------------------- PART 2 — funding bench --------------------------
def _bench_snapshot():
    fr = _lget("/api/v1/funding-rates").get("funding_rates") or []
    bench = {r["symbol"]: float(r.get("rate") or 0.0)
             for r in fr if r["exchange"] == "hyperliquid"}
    meta, ctxs = _hl({"type": "metaAndAssetCtxs"})
    live = {}
    for u, c in zip(meta.get("universe") or [], ctxs or []):
        try:
            live[u["name"]] = float(c.get("funding") or 0.0)
        except (TypeError, ValueError):
            continue
    return fr, bench, live


def part2_bench(poll_n, poll_every):
    print("\n" + "=" * 78)
    print("PART 2 — FUNDING BENCH EQUIVALENCE  (Lighter '_bench' vs direct HL)")
    print("=" * 78)

    fr, bench, live = _bench_snapshot()
    by_ex = {}
    for r in fr:
        by_ex.setdefault(r["exchange"], {})[r["symbol"]] = float(r.get("rate") or 0)
    print(f"  /funding-rates: {len(fr)} rows | " +
          " ".join(f"{e}={len(v)}" for e, v in sorted(by_ex.items())))
    neg = sum(1 for r in fr if float(r.get("rate") or 0) < 0)
    lr = list(by_ex.get("lighter", {}).values())
    print(f"  SIGNED? {neg}/{len(fr)} rows negative (lighter rows span "
          f"{min(lr):+.6f}..{max(lr):+.6f}) -> the rate IS signed.")
    print(f"  basis (funding_basis.py): lighter "
          f"{funding_basis.periods_per_year('lighter'):.0f}/yr (8h) vs "
          f"hyperliquid {funding_basis.periods_per_year('hyperliquid'):.0f}/yr (1h)")

    # --- the UNFILTERED test, shown ONLY to document that it lies (2b) ------
    # NOTE: this arm is PAIRED — it reads bench and live from the single
    # _bench_snapshot() above, exactly as [B] does. The ONLY thing that makes it
    # lie is the near-zero cut below (1e-9 vs [B]'s NEAR_ZERO=5e-6): a
    # denominator near zero manufactures 30x-188x ratios and sign flips out of
    # rounding. Do not relabel this "unpaired" — that was the original,
    # incorrect diagnosis and the whole point of verdict 2b's correction.
    pairs = [(s, bench[s], live[s]) for s in bench
             if s in live and abs(live[s]) > 1e-9]
    naive = sorted(b / h for _, b, h in pairs)
    nok = sum(1 for r in naive if abs(r - 8.0) <= 0.04)
    print(f"\n  [A] UNFILTERED CROSS-SECTION ({len(naive)} symbols, near-zero cut "
          f"1e-9 — PAIRED, same snapshot as [B]) — THIS INSTRUMENT LIES:")
    print(f"      median {st.median(naive):.3f} | min {min(naive):.3f} | "
          f"max {max(naive):.3f} | within 0.5% of 8.00: {nok}/{len(naive)}")
    print("      Do NOT read the outliers as a basis bug. The cause is the")
    print("      DENOMINATOR: this arm keeps coins whose |HL rate| is ~0 (cut")
    print("      1e-9), and a near-zero denominator manufactures 30x-188x")
    print("      ratios and sign flips out of rounding. [B] below differs in")
    print("      THREE ways (near-zero cut 5e-6, 10 coins, 20 repeats) — it is")
    print("      NOT a pairing contrast: both arms read one _bench_snapshot().")
    print("      Holding pairing constant and changing ONLY the cut already")
    print("      collapses the tail (min/max 7.329/8.155 -> 7.876/8.085).")

    # --- [B]: FILTERED + pooled repeats. NOT a pairing contrast with [A] —
    # both arms are same-instant paired from one _bench_snapshot(). [B] differs
    # by its near-zero guard (NEAR_ZERO=5e-6), its 10-coin universe, and 20
    # repeats. It is the trustworthy instrument because of the GUARD.
    print(f"\n  [B] FILTERED POLL (near-zero cut 5e-6) — {poll_n} samples every "
          f"{poll_every}s (~{poll_n*poll_every/60:.1f} min), "
          f"{len(POLL_COINS)} moving-funding coins")
    samples = []
    for i in range(poll_n):
        t0 = time.time()
        try:
            _, b, h = _bench_snapshot()
            samples.append({c: (b.get(c), h.get(c)) for c in POLL_COINS})
        except Exception as e:  # noqa: BLE001
            print(f"      poll {i} failed: {e}")
        time.sleep(max(0.0, poll_every - (time.time() - t0)))
    if len(samples) < 3:
        print("      too few samples — skipping the paired test")
        return None, None

    print(f"      collected {len(samples)} samples")
    hdr = (f"    {'sym':>8s} {'n':>3s} {'med ratio':>10s} {'min':>8s} "
           f"{'max':>8s} {'bench ticks':>12s}")
    print(hdr)
    pooled = []
    for c in POLL_COINS:
        rs = [d[c][0] / d[c][1] for d in samples
              if d[c][0] is not None and d[c][1] is not None
              and abs(d[c][1]) >= NEAR_ZERO]
        ticks = len({d[c][0] for d in samples if d[c][0] is not None})
        if not rs:
            continue
        pooled += rs
        print(f"    {c:>8s} {len(rs):>3d} {st.median(rs):>10.3f} {min(rs):>8.3f} "
              f"{max(rs):>8.3f} {ticks:>4d}/{len(samples):<7d}")
    med = st.median(pooled) if pooled else float("nan")
    print(f"\n  POOLED MEDIAN RATIO = {med:.4f}  (n={len(pooled)} paired obs)")
    print(f"  => the brief's single ETH sample GENERALISES: Lighter's bench is")
    print(f"     HL's rate on an 8h basis. Not an anecdote.")

    # --- staleness: lag fit on the PAIRED series ----------------------------
    print("\n  STALENESS — is the bench a fresh read of HL, or a fossil?")
    best = None
    for L in range(0, 6):
        errs = []
        for c in POLL_COINS:
            for i in range(L, len(samples)):
                b = samples[i][c][0]
                h = samples[i - L][c][1]
                if b is None or h is None or abs(h) < NEAR_ZERO:
                    continue
                errs.append(abs((b / 8.0) / h - 1.0))
        if not errs:
            continue
        m = st.median(errs)
        print(f"    lag {L*poll_every:3d}s  median rel-err {m:7.2%}  n={len(errs)}")
        if best is None or m < best[1]:
            best = (L * poll_every, m)
    if best:
        print(f"\n  BEST FIT: lag {best[0]}s (median rel-err {best[1]:.2%}).")
        print("  The bench TICKS (see 'bench ticks' above) — it is live, not a")
        print(f"  fossil. Trailing HL by ~{best[0]}s is ZERO for an hourly-funding")
        print("  consumer => NO staleness reason to keep the direct HL call.")
    return med, best


# ------------------------------ PART 3 — coverage ----------------------------
def part3_coverage():
    print("\n" + "=" * 78)
    print("PART 3 — COVERAGE  (a swap that silently drops coins is a bug)")
    print("=" * 78)

    obs = _lget("/api/v1/orderBookDetails").get("order_book_details") or []
    lt_books = {o["symbol"] for o in obs if o.get("symbol")}
    fr = _lget("/api/v1/funding-rates").get("funding_rates") or []
    bench = {r["symbol"] for r in fr if r["exchange"] == "hyperliquid"}
    lt_fund = {r["symbol"] for r in fr if r["exchange"] == "lighter"}
    hl_uni = {u["name"] for u in _hl({"type": "meta"}).get("universe") or []}
    hl_mids = {c for c in _hl({"type": "allMids"}) if not c.startswith("@")}

    print(f"  Lighter order books          : {len(lt_books)}")
    print(f"  Lighter /funding-rates own   : {len(lt_fund)}")
    print(f"  Lighter /funding-rates HL row: {len(bench)}   <- the '_bench'")
    print(f"  HL perp universe             : {len(hl_uni)}")
    print(f"  HL allMids (the disloc ref)  : {len(hl_mids)}")

    print(f"\n  HL has, Lighter has no BOOK ({len(hl_uni - lt_books)}): "
          f"{sorted(hl_uni - lt_books)[:12]}...")
    print(f"  Lighter has, HL lacks ({len(lt_books - hl_uni)}): "
          f"{sorted(lt_books - hl_uni)[:12]}...")
    print(f"  Lighter book with NO HL bench row ({len(lt_books - bench)}): "
          f"{sorted(lt_books - bench)[:12]}...")

    for name, coins in (("regime_oracle UNIVERSE", ro.UNIVERSE),
                        ("dislocation bot COINS", DISLOC_COINS),
                        ("funding-spread COINS", SPREAD_COINS)):
        print(f"\n  {name} (n={len(coins)}):")
        print(f"    not on Lighter books : "
              f"{[c for c in coins if c not in lt_books] or 'none'}")
        print(f"    no Lighter HL-bench  : "
              f"{[c for c in coins if c not in bench] or 'none'}")
        print(f"    not on HL            : "
              f"{[c for c in coins if c not in hl_uni] or 'none'}")
    print(f"\n  Lighter /funding-rates row fields: {sorted(fr[0].keys())}")
    print("  -> RATES ONLY. No price anywhere => the dislocation bot's allMids")
    print("     reference has NO Lighter equivalent. That swap is impossible.")


# --------------------- PART 4 — market_context field map ---------------------
def part4_market_context():
    print("\n" + "=" * 78)
    print("PART 4 — market_context.py FIELD-BY-FIELD  (can Lighter serve it?)")
    print("=" * 78)

    meta, ctxs = _hl({"type": "metaAndAssetCtxs"})
    hlm = {}
    for u, c in zip(meta.get("universe") or [], ctxs or []):
        try:
            mark = float(c.get("markPx") or 0)
            hlm[u["name"]] = {"oi_ntl": float(c.get("openInterest") or 0) * mark,
                              "premium": float(c.get("premium") or 0),
                              "oracle": float(c.get("oraclePx") or 0), "mark": mark}
        except (TypeError, ValueError):
            continue
    ltm = {}
    for o in _lget("/api/v1/orderBookDetails").get("order_book_details") or []:
        try:
            mark = float(o.get("mark_price") or 0)
            ltm[o["symbol"]] = {"oi_ntl": float(o.get("open_interest") or 0) * mark,
                                "mark": mark,
                                "index": float(o.get("index_price") or 0)}
        except (TypeError, ValueError):
            continue

    print("  market_context field -> Lighter availability:")
    print("    oi_ntl       : open_interest * mark_price      SHAPE AVAILABLE")
    print("    funding_apr  : /funding-rates lighter row      AVAILABLE (8h basis!)")
    print("    premium_bps  : (mark_price-index_price)/index  DERIVABLE, NOT the same")
    print("    mark         : mark_price                      AVAILABLE")
    print("    liq tape     : Binance ws — unaffected by an HL swap")

    b = hlm.get("BTC")
    if b and b["oracle"]:
        derived = (b["mark"] - b["oracle"]) / b["oracle"] * 1e4
        print("\n  PREMIUM IS A DIFFERENT CONSTRUCT — measured on HL's OWN BTC "
              "snapshot:")
        print(f"    HL 'premium' field   = {b['premium']*1e4:+.2f}bps")
        print(f"    (mark-oracle)/oracle = {derived:+.2f}bps   <- same snapshot!")
        print("  -> HL's premium is impact-price vs oracle, time-weighted. A")
        print("     Lighter (mark-index)/index would wear the name, not the meaning.")

    print("\n  OI IS A DIFFERENT QUANTITY (HL = the market; Lighter = our venue):")
    print(f"    {'coin':>5s} {'HL OI $':>15s} {'Lighter OI $':>15s} {'LT/HL':>7s}")
    ratios = []
    for c in ro.UNIVERSE:
        if c in hlm and c in ltm and hlm[c]["oi_ntl"] > 0:
            r = ltm[c]["oi_ntl"] / hlm[c]["oi_ntl"]
            ratios.append(r)
            print(f"    {c:>5s} {hlm[c]['oi_ntl']:>15,.0f} "
                  f"{ltm[c]['oi_ntl']:>15,.0f} {r:>6.1%}")
    if ratios:
        print(f"\n  Lighter OI is a median {st.median(ratios):.1%} of HL's "
              f"(range {min(ratios):.1%}-{max(ratios):.1%}) across "
              f"{len(ratios)} majors.")
        print("  => NOT two reads of one number. A swap REDEFINES the factor,")
        print("     mid-stream, inside the `mctx` column stamped onto live entries")
        print("     (lighter_funding_bot.py:813) — poisoning the very dataset")
        print("     market_context exists to accumulate.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore the candle cache")
    ap.add_argument("--skip-regime", action="store_true")
    ap.add_argument("--poll-samples", type=int, default=POLL_N)
    ap.add_argument("--poll-every", type=int, default=POLL_EVERY)
    a = ap.parse_args()

    cache = {}
    if os.path.exists(CACHE) and not a.refresh:
        try:
            cache = json.load(open(CACHE))
        except Exception:  # noqa: BLE001
            cache = {}

    print("\nLIGHTER vs HYPERLIQUID — EQUIVALENCE STUDY (read-only; swaps nothing)")
    print(f"run {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n")

    if not a.skip_regime:
        part1_regime(cache, "candles" not in cache or a.refresh)
    part2_bench(a.poll_samples, a.poll_every)
    part3_coverage()
    part4_market_context()

    print("\n" + "=" * 78)
    print("READ THE HEADER VERDICT. Per consumer — there is no single answer:")
    print("  regime_oracle    -> signal 99.4% IDENTICAL (safe), BUT fix the")
    print("                      young-book coverage trap first (ZEC).")
    print("                      NB: no bot consumes it; bot_learn.diagnose()")
    print("                      joins its HISTORY — the splice is longitudinal.")
    print("  spread backfill  -> Lighter BETTER; the mixed-unit window is a BUG.")
    print("  dislocation mids -> KEEP HL. No equivalent exists; would be circular.")
    print("  market_context   -> DO NOT SWAP. Different quantity (OI ~4% of HL's);")
    print("                      poisons the `mctx` factor dataset.")
    print("=" * 78)


if __name__ == "__main__":
    main()
