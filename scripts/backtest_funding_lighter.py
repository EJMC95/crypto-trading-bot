#!/usr/bin/env python3
"""
scripts/backtest_funding_lighter.py — the Funding Farmer, backtested ON LIGHTER.

╔══════════════════════════════════════════════════════════════════════════╗
║ ⛔ VERDICT WITHDRAWN 2026-07-17 (later the same day). READ THIS FIRST.    ║
║                                                                          ║
║ EVERY ECONOMIC CONCLUSION BELOW IS DENOMINATED IN `SLIP = 0.0005`         ║
║ (5bps/fill) — A NUMBER I ASSUMED AND NEVER MEASURED. The LIMITATIONS      ║
║ block below says so in as many words ("FRICTION IS ASSUMED at 10bps, NOT  ║
║ measured. It is the load-bearing constant") — and then the VERDICT says   ║
║ "the strategy is DEAD" and "DO NOT re-tune the gate, the slope, the vol   ║
║ filter, or the persist bar" anyway. The caveat went in the small print;   ║
║ the unqualified claim went in the headline. Under this repo's "don't      ║
║ re-test what a script header rejects" doctrine, that header BLOCKED the   ║
║ next reader from the right answer. **If a constant is load-bearing and    ║
║ unmeasured, it belongs in the VERDICT SENTENCE or the verdict is not      ║
║ earned.**                                                                 ║
║                                                                          ║
║ EXACTLY WHAT IS REFUTED — do not over-withdraw this either. Re-run at     ║
║ both frictions (BT_SLIP_BPS=5.0 vs 0.86), same 150d, same code:           ║
║      gate   @5bps(assumed)   @0.86bps(modelled)   both halves             ║
║      0.05      -41.95            -15.85             no / no               ║
║      0.12      -10.26            +11.91             no (h1 -4.23)         ║
║      0.20       +5.01            +22.51             no (h1 -2.31)         ║
║      0.40      -10.66             -0.82             no / no               ║
║  * **"NO GATE PASSES BOTH HALVES" SURVIVES at BOTH frictions.** That row  ║
║    of the verdict stands and is friction-independent.                     ║
║  * REFUTED: the breakeven arithmetic (0.122 / ~110% TRUE APR), "14-31x     ║
║    below breakeven", "THE STRATEGY IS DEAD", "NOT a tuning problem".      ║
║  * WHY I got it wrong, and it is not the constant — it is the LEAP: I     ║
║    swept the GATE, the slope, the vol filter and the persist bar, found   ║
║    none of them worked, and concluded the STRATEGY was dead. **I never    ║
║    swept the STOP.** At 0.86bps, TP.04/**STOP.03** takes the same 150d to ║
║    **+$21.32, both halves positive, n=1911** — a 10% stop against a 4%    ║
║                                                                          ║
║ ██ [2026-07-22] THE +$21.32 ABOVE IS WITHDRAWN — THIS HARNESS PRODUCED IT ██║
║ ██ FROM A BUG, AND THE CORRECTED NUMBER IS **-$11.57, BOTH HALVES      ██║
║ ██ NEGATIVE**. The bug: this file never cleared `hot` on a close, while  ██║
║ ██ the live bot pops `hot_since` on EVERY close (lighter_funding_bot.py  ██║
║ ██ :940, :1226). So PERSIST_H bit ONCE per hot run here and every time   ██║
║ ██ in production — 32-44% of the trades behind that +$21.32 were instant ██║
║ ██ re-entries the real bot REFUSES. Fixed at the `hot.pop(sym, None)`    ██║
║ ██ below; the STOP is no longer a supported fix, and the sweep of gates  ██║
║ ██ built on this harness has h2 NEGATIVE at every level 0.03..0.40.      ██║
║ ██ THE REFUTATION ABOVE ("I never swept the STOP") STILL STANDS as a     ██║
║ ██ lesson about generalising from four knobs — but its replacement       ██║
║ ██ verdict was itself an artifact. A harness that does not mirror the    ██║
║ ██ production rule does not produce a weaker answer; it produces a       ██║
║ ██ WRONG one, with the same confident sign. Re-derive anything citing    ██║
║ ██ this file before 2026-07-22.                                          ██║
║    take-profit lets losers run 2.5x further than winners are allowed,     ║
║    backwards for a mean-reversion book. "I tested every knob I thought    ║
║    of" is NOT "no knob works", and the header even listed the four knobs  ║
║    it had tested while the headline generalised to all of them. See       ║
║    [[funding-farmer-stop-is-the-bug]] and                                 ║
║    [[refutation-doesnt-clear-the-siblings]] — same shape.                 ║
║                                                                          ║
║ BUT DO NOT SWAP ONE UNMEASURED CONSTANT FOR ANOTHER — the 0.86bps is NOT  ║
║ A MEASURED FILL EITHER, and I checked before believing it:                ║
║   * `venue_orders` for `perps-funding-lighter-lshadow` (n=160, slip       ║
║     0.882bps, spread 1.744bps) is the SHADOW arm — `shadow=True`. Those   ║
║     are ShadowBroker MODELLED fills against the real book, not fills the  ║
║     venue gave anyone. A model's output is a hypothesis about friction.   ║
║   * The LIVE book (`perps-funding-lighter-lighter`) has **49 REAL orders, ║
║     07-11 → 07-17 — and `slippage_bps` is NULL on all 49**. Both prices   ║
║     ARE stored, and `px_fill == px_decision` EXACTLY on every one:        ║
║     measured real slippage = **0.000bps**, because the bot records the    ║
║     price it WANTED, not the price it GOT.                                ║
║   * A fill-telemetry fix landed today (445e189) and is HALF DONE: the two ║
║     CLOSE legs now read the real fill (`_real_exit` -> `last_fill`), but  ║
║     the ENTRY leg still publishes `px_decision=px, px_fill=px` with no    ║
║     slippage_bps. A ROUND TRIP NEEDS BOTH LEGS. A live order at 07-17     ║
║     05:29Z — an hour AFTER that commit — still wrote fill == decision.    ║
║                                                                          ║
║ SO: **Lighter's real round-trip friction has never been measured, and     ║
║ cannot be until the entry leg records a real fill.** My 5bps and the      ║
║ 0.86bps that refuted it are BOTH unmeasured; they merely disagree. The    ║
║ ranking of gates/stops below is a function of that constant, so nothing   ║
║ here is a verdict — it is a SENSITIVITY ANALYSIS awaiting one number.     ║
║ THE ONE EXPERIMENT THAT SETTLES THIS: fix the entry leg, let the live     ║
║ book accumulate paired decision/fill prices, and read the round trip off  ║
║ real money. Everything else is arithmetic on a guess.                     ║
║                                                                          ║
║ What still stands (structural, friction-independent): the resting-default ║
║ pin (§1 of backtest_funding_persistence), the sign-flip death mechanism,  ║
║ "hold longer" REFUTED, and Lighter's tape being 438d not 150d.            ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║ ORIGINAL VERDICT (2026-07-17, first run — the first time this bot had     ║
║ EVER been measured on the venue it trades). 150d, 25 markets,             ║
║ 2026-02-17→07-17. **All economic rows below assume SLIP=5bps — VOID.**    ║
║                                                                          ║
║ 1. NO GATE PASSES BOTH HALVES. Not one row. The naive Funding Farmer has  ║
║    no validated edge on Lighter at ANY entry gate.                        ║
║ 2. THE LIVE GATE IS BELOW THE FRICTION BREAKEVEN — structurally, before   ║
║    any price risk. Carry per trade = apr * hold_h/8760, so breakeven =    ║
║    round_trip_slip * 8760/hold_h. At the 72h CAP that is 0.122 TRUE; the  ║
║    live bot sits at 0.05 TRUE and the venue's floor band is 0.035 TRUE.   ║
║    Both below, by construction.                                           ║
║ 2b. **AND 0.122 IS FAR TOO GENEROUS — THE CAP NEVER BINDS.** Measured     ║
║    exit mix at the live gate: flip 42.9% / take_profit 24.5% / cold 20.5% ║
║    / stop 7.1% / max_hold only 4.9%. **63% of trades end because the      ║
║    FUNDING SIGNAL ITSELF EVAPORATED** (flip = rate crossed zero, cold =   ║
║    decayed under the exit bar) at a **MEDIAN HOLD OF 8h** (mean 16.8h).   ║
║    The MARKET closes the trade, not the cap. So the operative breakeven   ║
║    uses 8h, not 72h:  0.001 * 8760/8 = **1.09 = ~110% TRUE APR.**         ║
║    Lighter's floor is 3.5% and ETH is ~8% TRUE. The bot is **14-31x       ║
║    below its own friction breakeven** at the holding period the market    ║
║    actually grants it. Even a 0.5bp/fill fill (perp fee is 0 — this is    ║
║    pure spread) only brings breakeven to 11% TRUE at 8h, still above ETH. ║
║ 2c. RAISING THE GATE MAKES THIS WORSE, NOT BETTER: at gate 0.20 the       ║
║    median hold falls to 3h (hotter rates are spikier and mean-revert      ║
║    faster), so carry earned is 0.7bps against the same 10bps round trip.  ║
║ 3. THE SWEEP AND THE ARITHMETIC AGREE INDEPENDENTLY: P&L flips sign       ║
║    between gate 0.12 and 0.20; the cap-based breakeven predicts 0.122.    ║
║    A mechanism, not a curve fit. (The sweep can only ever reach ~flat     ║
║    because of 2b — no gate buys a longer hold.)                           ║
║ 3b. REFUTED HYPOTHESIS, recorded so nobody re-runs it: "hold longer —     ║
║    breakeven falls linearly with hold_h." MEASURED: raising MAX_HOLD_H    ║
║    72->168->336->720 moves funding earned by $0.20 ($15.95 -> $15.75)     ║
║    and makes P&L WORSE (-41.95 -> -47.12). The cap is not binding; you    ║
║    cannot buy hold time the market will not give you.                     ║
║ 4. FUNDING IS POSITIVE AT EVERY GATE (+$12..+$22 / 150d) AND TOO SMALL    ║
║    TO MATTER. Price P&L is negative at every gate. At the live gate,      ║
║    slippage (~1261 trades x 10bps x $25 = ~$31.5) costs ~2x the entire    ║
║    funding earned (+$15.95). The bot pays more to trade than it harvests. ║
║ 5. So the 8x bug did not merely mislabel the gate — it parked the live    ║
║    bot in the WORST region of its own gate curve (0.02-0.08 all lose      ║
║    $30-76; 0.20-0.30 are ~flat).                                          ║
║                                                                          ║
║ THEREFORE: "fix the conversion, keep 0.40" is NOT the answer either — a   ║
║ TRUE-40% gate also fails both halves (-$10.66). Neither the live gate nor ║
║ the HL-validated one survives on Lighter. THIS IS NOT A THRESHOLD TWEAK   ║
║ AND NOT A TUNING PROBLEM: no gate exists that clears a ~110% breakeven on ║
║ a venue whose floor is 3.5% and whose typical name is ~8% TRUE. The carry ║
║ is real (funding > 0 at every gate) and ~20x too small to pay for the     ║
║ round trip it takes to collect it.                                        ║
║                                                                          ║
║ AND IT IS NOT A FUNDING BOT. P&L by exit at the live gate:                ║
║     take_profit  +$304.06  (309 trades, +$0.98 ea)  <- the ONLY positive  ║
║     stop         -$225.51  ( 90 trades, -$2.51 ea)                        ║
║     flip          -$64.90  (541 trades)                                   ║
║     cold          -$24.59  (259 trades)                                   ║
║     max_hold      -$31.02  ( 62 trades)                                   ║
║ Every dollar of outcome is the 4%-TP / 10%-stop directional lottery. The  ║
║ funding is an entry FLAVOUR, not a P&L source: it decides which coin to   ║
║ bet on, then the price decides everything. Whatever this book is, it is   ║
║ not harvesting carry — and calling it "the Funding Farmer" is why nobody  ║
║ checked whether the carry could pay.                                      ║
║                                                                          ║
║ LIMITS — read before acting. This replays the NAIVE selector (first-come  ║
║ above the gate). The live bot also runs a multi-factor SCANNER            ║
║ (SCAN_ENABLED, vol veto) that `funding-farmer-scanner` memory credits     ║
║ with "the durable +52%", plus the 11-Jul slope gate — neither is modelled ║
║ here, so the live bot may do better than these rows. What the scanner     ║
║ cannot change is finding #2: it picks WHICH names clear the gate, not how ║
║ much carry a 72h hold earns. Universe = top 25 by daily quote volume      ║
║ (includes equity perps + commodities). One 150d window; halves shown.     ║
║ NEXT TEST: re-run with the scanner's selection modelled before concluding ║
║ the bot is unfixable — but do NOT re-denominate the live gate to 0.40     ║
║ true expecting the HL result; on Lighter data it does not reproduce.      ║
╚══════════════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS (2026-07-17, operator: "we need everything to run off lighter
as thats what we run on"). Agenda item 16 found every Lighter funding APR is 8x
true. The blocking question was whether `FUNDING_ENTER_APR=0.40` was FITTED in
those wrong units (label-only bug) or set from a TRUE-apr reference (genuinely
mis-set). Settled: **genuinely mis-set.** EVERY funding backtest in this repo
loads HYPERLIQUID (`backtest_directional_funding.py`, `backtest_scanner.py`,
`backtest_carry_hedged.py`, `backtest_tide_rider_scanner.py` — all
`HL = api.hyperliquid.xyz`, all `H = 24*365`), and HL's native funding really IS
hourly, so 24*365 is CORRECT there and 0.40 meant a TRUE 40% APR. The live bot
applies that same 0.40 to Lighter's 8h-basis rate, so it admits at ~5% TRUE.

VERIFIED, not assumed (17-Jul, against both live APIs):
  * HL `fundingHistory` ETH = 168 rows/7d = HOURLY, mean 1.2493e-05/hr;
    x24x365 = 10.94% APR (plausible) vs x3x365 = 1.37% (not). HL = hourly. ✓
  * Lighter `/api/v1/funding-rates` carries FOUR exchanges (lighter/binance/
    bybit/hyperliquid) normalised to a common 8-HOUR basis: its `hyperliquid`
    row is 0.0001 = exactly 8x HL's native 1.2493e-05/hr. Its `lighter` ETH row
    9.6e-05 x3x365 = 10.51% = the SETTLED series to the digit. Lighter = 8h. ✓
So the two venues' conventions differ by exactly 8, and the threshold was ported
across that gap as a bare constant. THE PORT IS THE BUG.

THE DATA GAP THIS CLOSES. The fleet used HL data as a proxy — but Lighter serves
its OWN history and always did: `/api/v1/fundings` pages back to **2025-05-05
(438d+)** of SETTLED HOURLY rates, and `/api/v1/candles` pages 500 bars at a
time arbitrarily far back. The HL harnesses fetch 150d. There was never a data
reason to backtest the Lighter bot on another venue.

TRUE APR, and the only conversion this file uses:
    settled `/api/v1/fundings` row = {timestamp, rate (PERCENT PER HOUR),
                                      direction: long|short, value}
    apr_true = rate/100 * 24 * 365, signed: direction 'long' => longs pay
                                    => apr>0 => the farmer SHORTS to earn.
  (Sanity: ETH mean rate 0.000947 %/hr -> 8.3% APR. Not 66%.)
  This file NEVER touches /funding-rates, so the 8x cannot leak in here.

FIDELITY — the live bot's real rules (`lighter_funding_bot.py`), mirrored:
  ENTER_GATE on |apr|, PERSIST_H hot-streak first, then exits in the live
  order: HARD_STOP (adverse) > TAKE_PROFIT (favour) > flip (apr crossed zero)
  > EXIT_APR (|apr| decayed) > MAX_HOLD_H. MAX_OPEN slots, ORDER_USD clip,
  SLIP per fill, funding accrued hourly at the settled rate.
  NO LOOK-AHEAD, same convention as the HL harnesses: the decision at hour t
  uses the rate settled at t and the candle CLOSED at t; stops are checked on
  the NEXT bar's intrabar high/low (stop before take-profit = conservative).
  EXIT_APR scales WITH the swept gate at the live ratio (0.15/0.40 = 0.375), so
  the sweep moves ONE variable — the gate — not the gate and its exit together
  ([[ab-tests-must-vary-exactly-one-variable]]).

READ THE VERDICT IN THE OUTPUT, and read `both halves` before believing any row.
Read-only: hits public endpoints, writes only its cache. Touches no bot, no DB.
    python3 scripts/backtest_funding_lighter.py            # sweep the gate
    python3 scripts/backtest_funding_lighter.py --days 150 --refresh
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request

B = "https://mainnet.zklighter.elliot.ai"
CACHE = os.path.join(os.path.dirname(__file__), ".lighterfund_cache.json")

# ---- live-bot config mirrored (lighter_funding_bot.py tuned defaults) -------
ORDER_USD = 25.0
# ⛔ THE LOAD-BEARING CONSTANT — every verdict this file has ever printed is a
# function of it, and NOBODY HAS MEASURED IT. Lighter's perp fee is 0, so this
# is pure spread/impact. Provenance of the candidates, checked 17-Jul:
#   0.0005  (5bps)  — what I ASSUMED. Source: nothing. It produced "the strategy
#                     is dead / 110% breakeven".
#   0.000086 (0.86bps) — the SHADOW arm's ShadowBroker MODEL (venue_orders,
#                     bot=perps-funding-lighter-lshadow, shadow=TRUE, n=160).
#                     A modelled fill against the real book — a hypothesis about
#                     friction, not a fill anyone got. It produced the WITHDRAWN
#                     "+$21.32" (see the banner: that was this harness's own
#                     `hot` bug, corrected to -$11.57 both halves negative).
#   REAL    — NOW MEASURED (2026-07-23): the fill-telemetry organ reads the live
#             Farmer's round-trip slip at ~0.47-0.54 bps/fill on real settled
#             fills (impl_shortfall.order_slip.live; "live executes TIGHTER than
#             its own shadow model ~0.87bps"). That is ~10x below this default,
#             and it FLIPS THE VERDICT: at 0.5bps the live gate 0.05 is +$33.47
#             / 180d BOTH HALVES POSITIVE (win 59%), not the near-dead +$3.57 the
#             5bps default prints. See FUNDING_GATE_LIGHTER_2026-07-23.md.
#             DEFAULT LEFT AT 5.0 deliberately (pessimistic reference; the live
#             measurement's final n is owned by the fill-telemetry work) — but
#             run `BT_SLIP_BPS=0.5` for the REAL verdict. Widening the gate up
#             (>=0.12) loses in both halves at EVERY slip level, so that
#             conclusion is slip-invariant.
# Override it and re-run rather than trusting any single row: the sweep is a
# SENSITIVITY ANALYSIS, and the P&L is dominated by THIS constant — use the
# measured ~0.5bps, not the unfounded 5, for any real read.
SLIP = float(os.environ.get("BT_SLIP_BPS", "5.0")) / 1e4
EXIT_RATIO = 0.375       # live EXIT_APR/ENTER_APR = 0.15/0.40 — held across the sweep
PERSIST_H = 4
MAX_HOLD_H = 72
HARD_STOP = 0.10
TAKE_PROFIT = 0.04
MAX_OPEN = 6

# The gate, in TRUE apr. 0.05 = what the live bot does TODAY (0.40 published /8).
# 0.40 = what the HL backtest validated. The rest bracket them.
SWEEP = [0.02, 0.03, 0.05, 0.08, 0.12, 0.20, 0.30, 0.40]


def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fetch_fundings(mid, days):
    """Settled hourly funding, paged backward. -> {hour_ts: signed_apr_true}."""
    out, end, cutoff = {}, int(time.time()), int(time.time()) - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/fundings", market_id=mid, resolution="1h",
                    start_timestamp=0, end_timestamp=end, count_back=0).get("fundings") or []
        if not rows:
            break
        for f in rows:
            rate = float(f["rate"]) / 100.0 * 24 * 365          # %/hr -> apr fraction
            out[int(f["timestamp"])] = rate * (1 if f["direction"] == "long" else -1)
        oldest = min(f["timestamp"] for f in rows)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if t >= cutoff}


def fetch_candles(mid, days):
    """Hourly OHLC, paged backward (500-bar cap per call). -> {hour_ts: (o,h,l,c)}."""
    out, end, cutoff = {}, int(time.time()), int(time.time()) - days * 86400
    seen_oldest = None
    while True:
        cs = _get("/api/v1/candles", market_id=mid, resolution="1h",
                  start_timestamp=end - 500 * 3600, end_timestamp=end,
                  count_back=500).get("c") or []
        if not cs:
            break
        for c in cs:
            out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                        float(c["l"]), float(c["c"]))
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if t >= cutoff}


def load(days, universe_n, refresh):
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days") >= days and d.get("universe_n") >= universe_n:
            return {s: {"fund": {int(k): v for k, v in m["fund"].items()},
                        "cand": {int(k): tuple(v) for k, v in m["cand"].items()}}
                    for s, m in d["mk"].items()}
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    liquid = sorted((o for o in obs if o.get("symbol")),
                    key=lambda o: -float(o.get("daily_quote_token_volume") or 0))
    mk = {}
    for o in liquid[:universe_n]:
        sym, mid = o["symbol"], o["market_id"]
        try:
            fund, cand = fetch_fundings(mid, days), fetch_candles(mid, days)
        except Exception as e:
            print(f"  {sym}: fetch failed ({e}) — skipped")
            continue
        common = set(fund) & set(cand)
        if len(common) < 24 * 20:
            print(f"  {sym}: only {len(common)}h of paired history — skipped")
            continue
        mk[sym] = {"fund": fund, "cand": cand}
        print(f"  {sym:12s} {len(common):5d}h paired "
              f"({(max(common)-min(common))/86400:.0f}d)")
    json.dump({"days": days, "universe_n": universe_n,
               "mk": {s: {"fund": m["fund"], "cand": m["cand"]} for s, m in mk.items()}},
              open(CACHE, "w"))
    return mk


# [2026-07-25 SLOPE-GATE STUDY] the live bot's funding-SLOPE entry gate (enter
# only while |apr| is still BUILDING, >= its value SLOPE_LOOKBACK_H ago) has NEVER
# been measured on LIGHTER — it is validated ONLY on Hyperliquid
# (backtest_funding_leverage.py), and this file's own line ~156 says the slope
# gate is "not modelled". Mirrors lighter_funding_bot.SLOPE_LOOKBACK_H (default 1h).
SLOPE_LOOKBACK_H = float(os.environ.get("FUNDING_SLOPE_LOOKBACK_H", "1"))


def _in_restart_window(t, restarts_per_day, window_h=1.0):
    """Deterministic model of the live slope-gate FAIL-OPEN. The live bot's
    rate history is IN-PROCESS, so for ~window_h after each boot it cannot look
    back SLOPE_LOOKBACK_H and the gate fails OPEN (no skip). The live service
    restarts ~restarts_per_day times (11 on 22-Jul alone). Evenly-spaced restarts
    (an idealisation — real deploys cluster) => a fail-open fraction of about
    restarts_per_day*window_h/24. Deterministic (no RNG) so the study reproduces."""
    if restarts_per_day <= 0:
        return False
    period = 86400.0 / restarts_per_day
    return (t % period) < window_h * 3600.0


def run(mk, enter_apr, t0, t1, slope=None, restarts_per_day=11, entry_ok=None,
        decay_persist_h=0):
    """Replay the live bot's rules over [t0,t1). Returns a result dict.

    entry_ok: optional (sym, hour_ts) -> bool predicate consulted ONLY at the
    entry site (a coin-quality/character filter study hook). None (default)
    reproduces the unfiltered behaviour exactly — position management, funding
    accrual and every exit path are never filtered, so an open position is
    always managed even if its coin later fails the predicate.

    decay_persist_h: [2026-07-30 DECAY-EXIT STUDY hook] the cold exit fires
    only after the rate has read decayed (|apr| < exit_apr) for MORE than
    this many CONSECUTIVE hourly reads. 0 (default) = first decayed read
    exits — byte-identical to the shipped behaviour (the counter reaches 1 >
    0 on the same hour the old inline check fired). A missing apr skips the
    position's management hour wholesale (this harness's existing contract,
    mirroring the ladder's apr=None-disables-decay), so the streak neither
    extends nor resets there. Ladder precedence is untouched: stop > tp >
    flip > cold > max_hold.

    `slope` adds the funding-SLOPE entry gate (default OFF => the sweep verdict
    in main() is byte-identical to before this study):
      None       -> gate off (unchanged)
      "active"   -> DURABLE history: gate always applied (the proposed fix)
      "failopen" -> LIVE reality: gate applied EXCEPT in a post-restart window
                    (restarts_per_day). The gap between active and failopen is
                    exactly what making the slope history durable would recover."""
    exit_apr = enter_apr * EXIT_RATIO
    hours = sorted({t for m in mk.values() for t in m["fund"] if t0 <= t < t1})
    pos, hot, cool = {}, {}, {}
    fund_pnl = price_pnl = 0.0
    trades, wins, eq, peak, maxdd = 0, 0, 0.0, 0.0, 0.0
    why_n, why_pnl, holds = {}, {}, []   # the exit mix IS the finding — see 2b

    for t in hours:
        for sym, m in mk.items():
            apr, c = m["fund"].get(t), m["cand"].get(t)
            if apr is None or c is None:
                continue
            _o, hi, lo, close = c
            p = pos.get(sym)
            if p:
                # funding accrues hourly at the SETTLED rate
                f = (1.0 if p["short"] else -1.0) * (apr / (24 * 365)) * p["ntl"]
                fund_pnl += f
                p["fund"] += f
                held_h = (t - p["t0"]) / 3600.0
                adverse = ((hi - p["px"]) / p["px"]) if p["short"] else ((p["px"] - lo) / p["px"])
                favour = ((p["px"] - lo) / p["px"]) if p["short"] else ((hi - p["px"]) / p["px"])
                out_px, why = None, None
                # decay streak: consecutive hourly reads under the exit bar
                # (0-persist reproduces the old immediate check exactly)
                p["cold_n"] = (p.get("cold_n", 0) + 1) if abs(apr) < exit_apr \
                    else 0
                if adverse >= HARD_STOP:                       # stop first = conservative
                    out_px, why = p["px"] * (1 + HARD_STOP if p["short"] else 1 - HARD_STOP), "stop"
                elif favour >= TAKE_PROFIT:
                    out_px, why = p["px"] * (1 - TAKE_PROFIT if p["short"] else 1 + TAKE_PROFIT), "tp"
                elif (p["short"] and apr < 0) or (not p["short"] and apr > 0):
                    out_px, why = close, "flip"
                elif p["cold_n"] > decay_persist_h:
                    out_px, why = close, "cold"
                elif held_h >= MAX_HOLD_H:
                    out_px, why = close, "max_hold"
                if out_px is not None:
                    raw = (p["px"] - out_px) / p["px"] if p["short"] else (out_px - p["px"]) / p["px"]
                    pp = raw * p["ntl"] - 2 * SLIP * p["ntl"]
                    price_pnl += pp
                    tot = pp + p["fund"]
                    trades += 1
                    wins += 1 if tot > 0 else 0
                    eq += tot
                    peak = max(peak, eq)
                    maxdd = min(maxdd, eq - peak)
                    why_n[why] = why_n.get(why, 0) + 1
                    why_pnl[why] = why_pnl.get(why, 0.0) + tot
                    holds.append(held_h)
                    cool[sym] = t + 12 * 3600 if why == "stop" else 0
                    pos.pop(sym)
                    # [2026-07-22 PERSISTENCE PARITY — this harness was WRONG
                    # and it inverted a SHIPPED verdict.] The live bot pops
                    # hot_since on EVERY close (lighter_funding_bot.py:940 and
                    # :1226 — "force a fresh persistence wait, no instant
                    # re-entry"). This harness never cleared `hot`, so a book
                    # that stays hot was re-entered the very next hour and
                    # PERSIST_H only ever bit ONCE per hot run. Every gate
                    # sweep and every exit-ladder study built on this file
                    # judged candidates on rules production does not run, with
                    # 32-44% of their trades being instant re-entries the real
                    # bot refuses. WHAT IT COST: the STOP 0.03 verdict flips
                    # from +$21.32 / both halves positive to **-$11.57 / both
                    # halves NEGATIVE** once this line exists. Do not remove it
                    # without re-deriving every verdict that cites this harness.
                    hot.pop(sym, None)
                continue
            # ---- entry: hot for PERSIST_H, gate on TRUE apr, slots free ----
            if abs(apr) >= enter_apr:
                hot[sym] = hot.get(sym) or t
            else:
                hot[sym] = None
            if (len(pos) < MAX_OPEN and hot.get(sym)
                    and (t - hot[sym]) / 3600.0 >= PERSIST_H
                    and t >= cool.get(sym, 0)
                    and (entry_ok is None or entry_ok(sym, t))):
                # [2026-07-25 SLOPE GATE] enter only while |apr| is still BUILDING
                # (>= its value SLOPE_LOOKBACK_H ago). The funding TAPE is the
                # history — apr 1h ago = m["fund"][t-3600] — and a MISSING value
                # FAILS OPEN, exactly the live _slope_ref contract (a real tape gap
                # IS the restart gap). `hot[sym]` is deliberately NOT cleared on a
                # slope skip: the coin stays hot and is re-checked next hour, as
                # the live loop does. Default slope=None keeps this a no-op.
                if slope:
                    prev = m["fund"].get(t - int(SLOPE_LOOKBACK_H * 3600))
                    _fo = (slope == "failopen"
                           and _in_restart_window(t, restarts_per_day))
                    if prev is not None and not _fo and abs(apr) < abs(prev):
                        continue          # rolling over — the gate's whole job
                pos[sym] = {"px": close, "short": apr > 0, "t0": t,
                            "ntl": ORDER_USD, "fund": 0.0}
    med = sorted(holds)[len(holds) // 2] if holds else 0.0
    return {"enter": enter_apr, "pnl": eq, "fund": fund_pnl, "price": price_pnl,
            "n": trades, "win": 100.0 * wins / trades if trades else 0.0,
            "maxdd": maxdd, "why_n": why_n, "why_pnl": why_pnl,
            "hold_med": med,
            "hold_mean": (sum(holds) / len(holds)) if holds else 0.0,
            # The operative breakeven uses the hold the MARKET grants, not the
            # cap — the cap fires on <5% of trades. See verdict 2b.
            "breakeven": (2 * SLIP * 8760 / med) if med else float("inf")}


def _slope_study(mk, lo, mid, hi):
    """The funding-slope gate meets LIGHTER — off / durable(always) / live-
    failopen, at BOTH the assumed 5bps and the modelled 0.86bps slip (the
    header's own discipline: a load-bearing constant belongs in the readout).
    'durable' = the proposed fix (rate history survives restarts). 'failopen' =
    today (gate off ~1h after each of ~11 daily restarts). The gap between them
    is what making the slope history durable would recover. Both halves must
    agree in sign or it is a window, not an edge worth protecting."""
    global SLIP
    _saved_slip = SLIP
    rpd = int(os.environ.get("BT_RESTARTS_PER_DAY", "11"))
    fo_frac = min(rpd * 1.0 / 24.0, 1.0)
    print("\n" + "=" * 82)
    print("SLOPE-GATE STUDY on LIGHTER — first measurement here (validated only on HL before)")
    print(f"  rule: enter only while |apr| >= its value {SLOPE_LOOKBACK_H:.0f}h ago (still building)")
    print(f"  fail-open: {rpd} restarts/day x 1h ~= {fo_frac*100:.0f}% of hours the gate is OFF")
    print(f"  {len(mk)} markets | {(hi-lo)/86400:.0f}d | BOTH halves must agree in sign")
    print("=" * 82)
    modes = [("off", None), ("durable", "active"), ("failopen", "failopen")]
    for slip_bps in (5.0, 0.86):
        SLIP = slip_bps / 1e4
        print(f"\n--- slip {slip_bps:.2f} bps/fill "
              f"{'(assumed)' if slip_bps == 5.0 else '(modelled)'} ---")
        hdr = (f"{'gate':>6s} {'mode':>9s} {'P&L $':>9s} {'fund$':>8s} {'price$':>8s} "
               f"{'n':>5s} {'win%':>6s} {'maxDD':>8s} | {'h1':>8s} {'h2':>8s} {'both+':>6s}")
        print(hdr); print("-" * len(hdr))
        for g in (0.05, 0.20, 0.40):
            for name, sl in modes:
                full = run(mk, g, lo, hi + 1, slope=sl)
                h1 = run(mk, g, lo, mid, slope=sl)
                h2 = run(mk, g, mid, hi + 1, slope=sl)
                both = "yes" if (full["pnl"] > 0 and h1["pnl"] > 0
                                 and h2["pnl"] > 0) else "no"
                tag = "  <- LIVE TODAY" if (g == 0.05 and name == "off") else ""
                print(f"{g:>6.2f} {name:>9s} {full['pnl']:>9.2f} {full['fund']:>8.2f} "
                      f"{full['price']:>8.2f} {full['n']:>5d} {full['win']:>6.1f} "
                      f"{full['maxdd']:>8.2f} | {h1['pnl']:>8.2f} {h2['pnl']:>8.2f} "
                      f"{both:>6s}{tag}")
            print()
    SLIP = _saved_slip
    print("READOUT — two questions:")
    print("  1) does DURABLE beat OFF? (is the slope gate a LIGHTER edge at all — it")
    print("     is not, unless durable is both-halves-positive AND beats off)")
    print("  2) DURABLE minus FAILOPEN = what durable slope history would RECOVER")
    print("     (the actual Phase-2 fix). If ~0, the restart fail-open is not the")
    print("     problem and the code change is not worth the real-money risk.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--universe", type=int, default=25)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--slope-study", action="store_true",
                    help="measure the funding-slope gate on Lighter (off/durable/failopen)")
    a = ap.parse_args()

    print(f"Fetching LIGHTER history — {a.days}d, top {a.universe} by daily quote volume")
    mk = load(a.days, a.universe, a.refresh)
    if not mk:
        raise SystemExit("no markets with paired funding+candle history")
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2
    if a.slope_study:
        _slope_study(mk, lo, mid, hi)
        return
    print(f"\n{len(mk)} markets | {time.strftime('%Y-%m-%d', time.gmtime(lo))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(hi))} ({(hi-lo)/86400:.0f}d)")
    print(f"clip ${ORDER_USD:.0f} x {MAX_OPEN} slots | slip {SLIP*1e4:.0f}bps/fill | "
          f"exit = enter x {EXIT_RATIO}\n")

    hdr = (f"{'gate(TRUE apr)':>15s} {'P&L $':>9s} {'fund $':>8s} {'price $':>9s} "
           f"{'n':>5s} {'win%':>6s} {'maxDD $':>8s} | {'1st half':>9s} {'2nd half':>9s}")
    print(hdr); print("-" * len(hdr))
    for g in SWEEP:
        full = run(mk, g, lo, hi + 1)
        h1 = run(mk, g, lo, mid)
        h2 = run(mk, g, mid, hi + 1)
        tag = ""
        if abs(g - 0.05) < 1e-9:
            tag = "  <- LIVE TODAY (0.40 published / 8)"
        if abs(g - 0.40) < 1e-9:
            tag = "  <- what the HL backtest validated"
        print(f"{g:>15.2f} {full['pnl']:>9.2f} {full['fund']:>8.2f} {full['price']:>9.2f} "
              f"{full['n']:>5d} {full['win']:>6.1f} {full['maxdd']:>8.2f} | "
              f"{h1['pnl']:>9.2f} {h2['pnl']:>9.2f}{tag}")
    print("\nBOTH HALVES must agree in sign before a gate is believable — a row that "
          "wins only on one half is a window, not an edge (see trail-blazer-no-durable-edge).")

    # ---- the diagnosis that matters more than the sweep (verdict 2b) --------
    for g in (0.05, 0.20):
        r = run(mk, g, lo, hi + 1)
        n = r["n"] or 1
        print(f"\n=== gate {g:.2f} TRUE — WHY trades end (n={n}) ===")
        print(f"  median hold {r['hold_med']:.1f}h / mean {r['hold_mean']:.1f}h "
              f"vs a {MAX_HOLD_H}h cap")
        for why, k in sorted(r["why_n"].items(), key=lambda x: -x[1]):
            print(f"  {why:>12s} {k:>5d} {100*k/n:>5.1f}%  ${r['why_pnl'][why]:>8.2f}  "
                  f"(${r['why_pnl'][why]/k:>6.3f}/trade)")
        signal_gone = 100 * (r["why_n"].get("flip", 0) + r["why_n"].get("cold", 0)) / n
        print(f"  -> {signal_gone:.0f}% of trades end because the FUNDING SIGNAL "
              f"EVAPORATED (flip+cold), not on price or the cap.")
        print(f"  -> carry earned over a {r['hold_med']:.0f}h hold at gate {g:.2f} = "
              f"{g*r['hold_med']/8760*1e4:.1f}bps vs {2*SLIP*1e4:.0f}bps round-trip slip")
        print(f"  -> OPERATIVE BREAKEVEN at that hold = {r['breakeven']:.2f} TRUE apr "
              f"({r['breakeven']*100:.0f}% APR). Venue floor is 3.5%, ETH ~8%.")


if __name__ == "__main__":
    main()
