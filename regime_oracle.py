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
  * Data source: LIGHTER public /api/v1/candles (daily, CLOSED candles only —
    the partial today-candle is dropped, matching freqtrade behavior).

WEEK-ONE MODE: ADVISORY / PUBLISH-ONLY. No bot reads this yet. After a week
of history we compare its calls against what bots did (the enforcement
decision is data, not vibes).

FAIL-SAFE CONTRACT (consumers): payload carries `updated` + `ttl_sec`. If
now - updated > ttl_sec, IGNORE the oracle and fall back to local gates —
a stale oracle must never steer the fleet. (Spec'd 2026-07-01.)

Run-once process; run_all.sh loops it every 30 min (same pattern as
market_pulse). Crash of this process affects nothing else.

╔══════════════════════════════════════════════════════════════════════════════╗
║ [2026-07-17] VENUE SWAP: HYPERLIQUID -> LIGHTER. Measured, not assumed.       ║
║ (LIGHTER-FIRST, CLAUDE.md user decision 14-Jul: "all services must run off    ║
║ lighter". audit_venue_purity.py flagged this file at host:api.hyperliquid.xyz.)║
║                                                                              ║
║ THE SIGNAL SURVIVES THE SWAP — and the SWAP ITSELF IS A NO-OP TODAY.          ║
║  * PRIOR (scripts/study_lighter_vs_hl_equivalence.py, read its header):       ║
║    this module's REAL classify() replayed on both sources over 200 closed     ║
║    days x 16 majors gave an IDENTICAL verdict on 99.4% of coin-days           ║
║    (3,066/3,085). The 0.6% is NOT price error — it is this oracle's OWN       ║
║    knife-edge at the ADX bands (a sub-point ADX gap flips the state and the   ║
║    hysteresis then latches the two sources apart for days). Neither source    ║
║    is "wrong"; they straddle a threshold this file makes discontinuous.       ║
║  * THIS FILE'S OWN A/B (scripts/ab_regime_oracle_venue_swap.py, run           ║
║    2026-07-17 against both live APIs — it drives THIS module's real           ║
║    fetch_daily(), because the study proved "Lighter candles" and not "this    ║
║    code"): **16/16 majors, TODAY'S VERDICT IDENTICAL on every one** — and     ║
║    SEED-INVARIANT (both arms agree under hysteresis seed None/0/1, so no      ║
║    major sits on the knife-edge today).                                       ║
║    60-day rolling replay, hysteresis carried per arm from a common seed:      ║
║    **895/900 coin-days agree (99.4%)**; 12 of the 15 replayable majors        ║
║    agree 100%. The 5 that differ: NEAR 2026-07-15 + 07-16 (HL LONG-window     ║
║    adx 13.0/13.4 vs Lighter chop-gated adx 12.0/12.3), TAO 05-24 + 06-15,     ║
║    DOGE 05-22 — the ADX-band straddle the study measured, independently       ║
║    reproduced through a DIFFERENT fetch path (the study named the same NEAR   ║
║    days to the decimal).                                                      ║
║    -> NO coin's verdict changes today. This commit changes no decision.       ║
║  * AND THE REPLAY OVERSTATES THE RISK, for a reason worth knowing: it runs    ║
║    TWO INDEPENDENT hysteresis chains, so a one-day band straddle can latch    ║
║    the arms apart for days. PRODUCTION HAS ONE CHAIN — `prev_trend` is read   ║
║    from the SHARED published state (store.load_state), so the swap INHERITS   ║
║    the HL-era trend and continues it; it does not start a rival chain. The    ║
║    live divergence is therefore <= the replay's.                              ║
║                                                                              ║
║ THE TRAP THE SWAP CARRIES — COVERAGE, and it is now EXPLICIT.                 ║
║  Lighter lists some books LATER than HL, so a young book has fewer daily      ║
║  bars than the 203 (EMA_SLOW+SLOPE_BARS) this oracle needs. The study         ║
║  measured it: Lighter's ZEC book (born 2025-10-03) could not have produced    ║
║  a verdict on 115 of 200 replayed days while HL published one — and on the    ║
║  85 days both could compute they agreed 100%. A swap that silently drops a    ║
║  coin is a BUG: the fleet would read a smaller universe and never know.       ║
║  SO: every coin that cannot be graded is NAMED in the payload's additive      ║
║  `coverage.missing` map with its REASON (no-lighter-book / short-history(n)   ║
║  / stale-tape(n) / fetch-failed:<Exc>), and stays in `errors` as before. No   ║
║  verdict beats a wrong verdict — the coin is skipped, never guessed, never    ║
║  silently absent.                                                             ║
║  THE TRAP HAS A SECOND HALF the study did not reach: a FROZEN tape. 17 of     ║
║  Lighter's 218 books are `inactive` (measured today), and a delisted book     ║
║  keeps serving its last 300 bars forever — clearing the 203-bar gate while    ║
║  describing a regime that ended weeks ago. Young-book = no data; frozen-book  ║
║  = fresh-looking WRONG data, the "alive but sick" class fleet_immune exists   ║
║  for. `MAX_TAPE_AGE_DAYS` names it instead of grading it. INERT AT SHIP:      ║
║  measured 0/16 majors stale (every one closed a bar yesterday), so it moves   ║
║  no verdict today — it is a guard against the delisting, not a change.        ║
║  MEASURED TODAY: 16/16 majors clear the 203-bar gate on Lighter — NOTHING is  ║
║  dropped right now. The trap is DORMANT, not absent, and ZEC still shows it:  ║
║  287 Lighter bars (its whole book) vs HL's 521 — it clears the gate by 84,    ║
║  yet it is STILL too young to replay 60 days against HL (the A/B could not    ║
║  score it at all), and the study measured it ungradeable on 115 of 200 days.  ║
║  A coin that clears TODAY and vanished YESTERDAY is precisely the thing a     ║
║  spot check cannot see — hence a payload field, not a glance.                 ║
║                                                                              ║
║ WHAT DID *NOT* CHANGE (deliberately — doctrine: a venue swap must be          ║
║ behaviour-neutral or MEASURED):                                               ║
║  classify(), wilder_adx(), the ADX 17/11 bands, EMA 50/200, SLOPE_BARS,       ║
║  LOOKBACK_DAYS=300, the hysteresis, the 203-bar short-history gate, the       ║
║  UNIVERSE, `updated`+`ttl_sec`, and every existing payload field. `coverage`  ║
║  is ADDITIVE. `params.source` now reads "lighter-1d" because it must not      ║
║  lie about where the tape came from.                                          ║
║                                                                              ║
║ BAR TIMESTAMPS ARE MILLISECONDS, ON PURPOSE. HL's candleSnapshot and          ║
║ Lighter's /api/v1/candles both stamp `t` in ms at the bar's OPEN, both        ║
║ aligned to UTC midnight (verified in the study). Keeping ms keeps `asof`      ║
║ byte-identical in shape across the splice — bot_learn joins this key's        ║
║ HISTORY, so the archive must not develop a seam.                              ║
║                                                                              ║
║ LIMITATIONS — read before trusting this.                                      ║
║  * The 99.4%/99.5% agreement says the signal is the SAME, NOT that either     ║
║    source is RIGHT on the days they differ. Nothing here ranks HL's regime    ║
║    call above Lighter's; that needs the calls joined to outcomes, which is    ║
║    what bot_state_history exists for.                                         ║
║  * THE SPLICE IS LONGITUDINAL. No bot consumes this key for trading —         ║
║    VERIFIED by grep, not inherited: the readers are pnl_dashboard (display),  ║
║    fleet_respiration (freshness only) and bot_learn._load_regime_history(),   ║
║    which joins the bot_state_history ARCHIVE to label losing buckets          ║
║    regime_timing. So the risk of this swap is not a live trading change; it   ║
║    is that pre-swap archive rows are HL-derived and post-swap rows            ║
║    Lighter-derived in the same column. At 99.4% identical that seam is        ║
║    nearly harmless, but it is the thing to weigh — and it is why the          ║
║    docstring's "CROSS-BOT LAYER 1 / the fleet's regime signal" framing        ║
║    overstates today's reach.                                                  ║
║  * COVERAGE SHRINKS THE READ, SAFELY. `fleet.read` needs an ABSOLUTE n>=4     ║
║    long or short to call a direction, so a universe thinned by missing books  ║
║    decays toward "mixed / transitional" — neutral — never toward a confident  ║
║    wrong direction. That is fail-safe by construction, not by accident.       ║
║  * Coverage moves as Lighter lists/delists. `coverage.missing` is the live    ║
║    answer; the 16/16 above is one reading (2026-07-17).                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import bot_pnl_store as store

KEY = "regime-oracle"
TTL_SEC = 7200          # consumers must ignore anything older than 2h

# The fleet's shared majors: RegimeSwitchV2's 10 + DOT/NEAR for spot coverage.
UNIVERSE = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
            "LINK", "LTC", "DOT", "NEAR", "SUI",  # SUI: day-zero review catch
            "HYPE", "ZEC", "TAO"]  # [2026-07-07] coverage adds with the perps web

# [2026-07-21 REVIEW ITEM 18 — build order step 1: PER-ASSET COVERAGE,
# publish-only.] The venue's non-crypto books are the fleet's only on-venue
# source of a regime that is not crypto's (measured at the review: SPY +8.1%
# through BTC −32.9%, while btc_regime_up read risk-off 61.5% of bars — a
# BTC gate over SPY is incoherent). This build publishes each non-crypto
# book's OWN regime so the per-asset gate (the NEXT, review-gated step) has
# something to consume; NOTHING consumes these entries yet, and `fleet.read`
# stays CRYPTO-ONLY (bot_learn's risk_off join reads it — see summarize()).
# MEASURED before building (21-Jul, this venue's own tape): Lighter prints
# non-crypto daily bars 7d/wk and the weekend bars are NOT flat (SPY: 52
# weekend bars, 0 flat), so the crypto method applies unmodified — no
# session filter, no frozen-bar hazard. Coverage graduates with the tape:
# at ship NVDA/TSLA/XAU/XAG clear the 203-bar EMA floor; MSTR ~1wk out;
# SPY/QQQ ~3-4wk; XCU/WTI/IWM later — each NAMED short-history until then.
NONCRYPTO = {
    "SPY": "equity-index", "QQQ": "equity-index", "IWM": "equity-index",
    "NVDA": "equity-single", "TSLA": "equity-single", "MSTR": "equity-single",
    "WTI": "commodity", "XAU": "commodity", "XAG": "commodity",
    "XCU": "commodity",
}

ADX_TREND = 17          # >= trending (matches RegimeSwitchV2 after Jul-6 cut)
ADX_CHOP = 11           # <= chop; between = hysteresis (hold previous)
EMA_FAST, EMA_SLOW, SLOPE_BARS = 50, 200, 3
LOOKBACK_DAYS = 300     # enough for a stable EMA200

# [2026-07-17] Lighter's public REST — the venue we trade is the venue we read.
LT_BASE = "https://mainnet.zklighter.elliot.ai"
PAGE_CAP = 500          # /api/v1/candles HARD cap: 500 bars per call
FETCH_SLACK_DAYS = 10   # ask past the window so a gap in the tape can't short it
# [2026-07-17] A FROZEN tape is the other half of the coverage trap. 17 of
# Lighter's 218 books are `inactive` (measured): a delisted/halted book keeps
# serving its last 300 bars forever, and grading them would publish a MONTHS-OLD
# regime stamped as today's — fresh-but-wrong, the "alive but sick" class. 3
# days of slack tolerates an illiquid book that skips a print; beyond that the
# coin is NAMED, not graded. INERT at ship: measured 0/16 majors stale (every
# one closed a bar yesterday), so this changes no verdict today.
MAX_TAPE_AGE_DAYS = 3


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lget(path, **q):
    """GET Lighter's public REST (no auth), with a short retry.

    Transient failures must not silently thin the universe — a coin that fails
    every attempt is NAMED in coverage.missing, never quietly dropped.
    """
    url = LT_BASE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def market_ids():
    """{symbol: market_id} for every Lighter book — one call for the universe.

    The oracle's majors are all plain symbols (no 1000X meme markets), so a
    direct symbol match is the whole mapping; anything absent is reported as
    `no-lighter-book`, not skipped.
    """
    rows = _lget("/api/v1/orderBookDetails").get("order_book_details") or []
    return {r["symbol"]: r["market_id"] for r in rows if r.get("symbol")}


def fetch_daily(market_id, now=None):
    """Lighter 1d candles -> the oracle's frame (t ms, o/h/l/c).

    CLOSED candles only (today's partial bar is dropped by TIMESTAMP, not by
    position: an illiquid book may publish no bar at all today, and iloc[:-1]
    would then eat a real closed day). Returns at most LOOKBACK_DAYS bars, the
    exact window the equivalence study replayed.

    Pages BACKWARD because /api/v1/candles caps at 500 bars per call: each page
    asks for the 500 days ending at `end`, then `end` moves to one day before
    the oldest bar returned. 1d reaches ~499 days — more than the 300 needed.
    """
    now = int(now if now is not None else time.time())
    day_ms = (now // 86400 * 86400) * 1000       # today's UTC midnight, ms
    cutoff = now // 86400 * 86400 - (LOOKBACK_DAYS + FETCH_SLACK_DAYS) * 86400
    bars, end, oldest_seen = {}, now, None
    while True:
        rows = _lget("/api/v1/candles", market_id=market_id, resolution="1d",
                     start_timestamp=end - PAGE_CAP * 86400,
                     end_timestamp=end, count_back=PAGE_CAP).get("c") or []
        if not rows:
            break
        for c in rows:
            bars[int(c["t"])] = (float(c["o"]), float(c["h"]),
                                 float(c["l"]), float(c["c"]))
        oldest = min(int(c["t"]) for c in rows) // 1000
        # reached the window, or the venue stopped serving older bars
        if oldest <= cutoff or (oldest_seen is not None
                                and oldest >= oldest_seen):
            break
        oldest_seen, end = oldest, oldest - 86400
    ts = sorted(t for t in bars if t < day_ms)[-LOOKBACK_DAYS:]
    return pd.DataFrame({"t": ts,
                         "o": [bars[t][0] for t in ts],
                         "h": [bars[t][1] for t in ts],
                         "l": [bars[t][2] for t in ts],
                         "c": [bars[t][3] for t in ts]})


def tape_age_days(df, now=None):
    """Days between the frame's newest CLOSED bar and today's UTC midnight.

    1 == the normal healthy read (yesterday's bar is the newest closed one).
    A big number means the book stopped printing — delisted, halted, or dead.
    """
    if df.empty:
        return None
    day = int(now if now is not None else time.time()) // 86400 * 86400
    return (day - int(df["t"].iloc[-1]) // 1000 // 86400 * 86400) // 86400


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


def summarize(pairs):
    """(fleet, noncrypto) summaries from the full pairs dict — pure, selftested.

    [2026-07-21 item 18] THE CONTRACT THIS PROTECTS: `fleet.read` is consumed
    by bot_learn's risk_off history join (bot_learn.py:704 reads
    payload.fleet.read — the Georgia "100% of losses in risk-off" diagnosis
    came from it), and it has always meant the CRYPTO majors. Non-crypto
    books must never blend into it — an aggregate across asset classes is
    exactly the incoherence item 18 exists to remove. Each non-crypto book's
    regime is PER-ASSET only (read `pairs[sym]`); the `noncrypto` block is a
    display summary, not a signal."""
    crypto = {k: v for k, v in pairs.items() if k not in NONCRYPTO}
    nc = {k: v for k, v in pairs.items() if k in NONCRYPTO}
    n_long = sum(1 for p in crypto.values() if p["verdict"] == "LONG-window")
    n_short = sum(1 for p in crypto.values() if p["verdict"] == "SHORT-window")
    n_idle = len(crypto) - n_long - n_short
    read = ("risk-off downtrend" if n_short > n_long and n_short >= 4 else
            "risk-on uptrend" if n_long > n_short and n_long >= 4 else
            "mixed / transitional")
    fleet = {"n_long": n_long, "n_short": n_short, "n_flat_or_chop": n_idle,
             "read": read}
    noncrypto = {
        "n_published": len(nc),
        "n_long": sum(1 for p in nc.values() if p["verdict"] == "LONG-window"),
        "n_short": sum(1 for p in nc.values() if p["verdict"] == "SHORT-window"),
        "by_class": {cls: [s for s in sorted(nc) if NONCRYPTO[s] == cls]
                     for cls in sorted(set(NONCRYPTO.values()))},
        "note": "per-asset only — never blended into fleet.read",
    }
    return fleet, noncrypto


# ---------------------------------------------------------------------------
# [2026-07-22] SELF-GRADING — the module's own 07-07 promise, finally built:
# "after a week of history we compare its calls against what bots did (the
# enforcement decision is data, not vibes)", and the 17-Jul swap header's
# admission that nothing here ranks a regime call as RIGHT — "that needs the
# calls joined to outcomes". Fifteen days of archive later, no join existed.
# This is it, prequentially and per asset: every DIRECTIONAL call (LONG/
# SHORT-window) on a new closed daily bar becomes one pending evidence unit,
# graded against the pair's OWN later closes at +1 and +3 bars. It is also
# exactly the evidence the review-gated step 2 (per-asset gate consumes)
# needs on the table: does SPY's own regime call predict SPY's forward
# return on this venue's tape, per asset, out of sample by construction.
# PUBLISH-ONLY: no consumer reads grades; the (bc) regime gate keeps gating
# on fleet.read exactly as evidenced. Same venue-purity as everything here —
# the grade compares Lighter closes to Lighter closes.
# ---------------------------------------------------------------------------

GRADE_BARS = (1, 3)        # horizons in CLOSED DAILY BARS (this is a 1d method)
PENDING_MAX_D = 10         # a sym that left coverage ages out of pending
PENDING_CAP = 200          # global hard bound on carried state


def grade_pairs(prev_grading, pairs, now=None):
    """(grading_state, grades_display) — one prequential pass.

    One evidence unit per (sym, closed daily bar): when a pair shows a NEW
    `asof` with a DIRECTIONAL verdict, the call is recorded at that bar's
    close; it is graded at the first later observation >= h bars ahead (a
    missed cycle grades on a wider move — recorded, not idealized). hit =
    the close moved the CALLED way; avg_pp is signed INTO the call (a SHORT
    call on a book that falls 1.2% scores +1.2pp), so positive avg_pp always
    means "the oracle's directional calls made money-shaped moves". dir-flat
    / chop-gated are never graded — the oracle claims no direction there.
    Pure, bounded (PENDING_CAP / PENDING_MAX_D), tolerant of malformed prior
    state; a sym absent today keeps its pending calls until they age out.
    """
    g = prev_grading if isinstance(prev_grading, dict) else {}
    day_ms = 86400 * 1000
    now_ms = int(now if now is not None else time.time()) * 1000
    scores = {}
    for s, sc in (g.get("scores") or {}).items():
        if isinstance(sc, dict):
            keep_h = {h: dict(b) for h, b in sc.items()
                      if isinstance(b, dict) and b.get("n")}
            if keep_h:
                scores[s] = keep_h
    pending = [p for p in (g.get("pending") or [])
               if isinstance(p, dict) and p.get("sym")]

    # 1. record new calls — one per (sym, asof), directional verdicts only
    have = {(p.get("sym"), str(p.get("asof"))) for p in pending}
    for sym, v in sorted((pairs or {}).items()):
        if not isinstance(v, dict):
            continue
        if v.get("verdict") not in ("LONG-window", "SHORT-window"):
            continue
        if (sym, str(v.get("asof"))) in have:
            continue
        pending.append({"sym": sym, "asof": str(v.get("asof")),
                        "close": v.get("close"),
                        "dir": 1 if v["verdict"] == "LONG-window" else -1,
                        "done": []})

    # 2. grade matured calls against the pair's CURRENT close
    keep = []
    for p in pending:
        cur = (pairs or {}).get(p["sym"])
        try:
            asof_p = int(float(p.get("asof")))
            c0 = float(p.get("close"))
        except (TypeError, ValueError):
            continue                       # malformed call — drop, not crash
        if not isinstance(cur, dict):
            if now_ms - asof_p <= PENDING_MAX_D * day_ms:
                keep.append(p)             # out of coverage today; wait
            continue
        try:
            asof_c = int(float(cur.get("asof")))
            c1 = float(cur.get("close"))
        except (TypeError, ValueError):
            keep.append(p)
            continue
        bars_fwd = (asof_c - asof_p) // day_ms
        done = {int(h) for h in (p.get("done") or [])}
        if bars_fwd > 0 and c0 > 0:
            fwd_pp = (c1 / c0 - 1.0) * 100.0
            signed = fwd_pp * (1 if p.get("dir", 1) >= 0 else -1)
            for h in GRADE_BARS:
                if bars_fwd >= h and h not in done:
                    b = scores.setdefault(p["sym"], {}).setdefault(
                        f"d{h}", {"n": 0, "hits": 0, "sum_pp": 0.0})
                    b["n"] += 1
                    b["hits"] += 1 if signed > 0 else 0
                    b["sum_pp"] = round(b["sum_pp"] + signed, 4)
                    done.add(h)
        if len(done) < len(GRADE_BARS):
            keep.append(dict(p, done=sorted(done)))
    pending = keep[-PENDING_CAP:]

    grades = {}
    for sym, sc in scores.items():
        out = {}
        for h in sorted(sc):
            b = sc[h]
            if b.get("n"):
                out[h] = {"n": b["n"], "hit": round(b["hits"] / b["n"], 3),
                          "avg_pp": round(b["sum_pp"] / b["n"], 3)}
        if out:
            grades[sym] = out
    return {"pending": pending, "scores": scores}, grades


def main():
    # [2026-08-05 SEED GUARD] checked read — `pairs` carries the per-asset
    # grade accrual (the item-18 evidence window); a failed read that fell
    # through as {} rebuilt it from scratch and the save made the wipe
    # durable. Standard degrade: skip the cycle.
    _ok, _prev = store.load_state_checked(KEY)
    if not _ok:
        print("[regime-oracle] state read FAILED — skipping this cycle "
              "rather than seed over the accrual record", flush=True)
        return
    prev = _prev or {}
    prev_pairs = prev.get("pairs", {})
    # missing_nc keeps the crypto coverage contract untouched: coverage.missing
    # / n_missing have always meant THE MAJORS; a young non-crypto book (most
    # of them at ship) is named in coverage.noncrypto.missing instead.
    pairs, errors, missing, missing_nc = {}, [], {}, {}

    try:
        ids = market_ids()
    except Exception as e:
        print(f"[regime-oracle] {now_iso()} Lighter book list unreachable "
              f"({type(e).__name__}) — NOT publishing (consumers keep last "
              f"good + TTL)")
        return

    for coin in list(UNIVERSE) + list(NONCRYPTO):
        _miss = missing_nc if coin in NONCRYPTO else missing
        mid = ids.get(coin)
        if mid is None:
            # NAMED, not dropped: a coin Lighter does not list is a coverage
            # hole the fleet must be able to SEE.
            _miss[coin] = "no-lighter-book"
            errors.append(f"{coin}:no-lighter-book")
            continue
        try:
            df = fetch_daily(mid)
            if len(df) < EMA_SLOW + SLOPE_BARS:
                # the young-book trap (ZEC; at ship most non-crypto books —
                # they graduate as tape accrues). No verdict > a wrong verdict.
                _miss[coin] = (f"short-history({len(df)}<"
                               f"{EMA_SLOW + SLOPE_BARS})")
                errors.append(f"{coin}:short-history({len(df)})")
                continue
            age = tape_age_days(df)
            if age is not None and age > MAX_TAPE_AGE_DAYS:
                # the frozen-book trap. Grading this would assert an old
                # regime as today's — the wrong verdict this must never give.
                _miss[coin] = f"stale-tape({age}d)"
                errors.append(f"{coin}:stale-tape({age}d)")
                continue
            pairs[coin] = classify(df, (prev_pairs.get(coin) or {}).get("trend"))
            # [2026-07-21 item 18] every pair self-describes its asset class —
            # the future per-asset gate keys on this, never on a blended read.
            pairs[coin]["class"] = NONCRYPTO.get(coin, "crypto")
        except Exception as e:
            _miss[coin] = f"fetch-failed:{type(e).__name__}"
            errors.append(f"{coin}:{type(e).__name__}")
        time.sleep(0.4)  # gentle on the public API

    # [2026-07-21 AUDIT FIX] the dark-venue guard gates on CRYPTO pairs, not
    # any pair: the (az) per-asset widening put NONCRYPTO into the fetch
    # loop, so an all-crypto-failure cycle with one surviving stock book
    # would have PUBLISHED a fresh crypto-empty fleet read — consumers
    # (`fleet.read` gates real entries via the (bc) regime gate) would read
    # a fresh 'no signal' instead of going TTL-neutral on a dark venue,
    # which the module's own selftest pins as the contract.
    if not any(c in UNIVERSE for c in pairs):
        print(f"[regime-oracle] {now_iso()} crypto majors ALL failed "
              f"({errors}) — NOT publishing (consumers keep last good + TTL; "
              f"{len(pairs)} non-crypto grades held back with it)")
        return

    fleet, noncrypto = summarize(pairs)
    n_long, n_short = fleet["n_long"], fleet["n_short"]
    n_idle, read = fleet["n_flat_or_chop"], fleet["read"]
    n_crypto = len(pairs) - noncrypto["n_published"]
    # [2026-07-22] self-grading: join this cycle's calls to prior calls'
    # outcomes (publish-only — see grade_pairs). State rides the payload.
    grading, grades = grade_pairs(prev.get("grading"), pairs)
    payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC,
        "params": {"adx_trend": ADX_TREND, "adx_chop": ADX_CHOP,
                   "ema": [EMA_FAST, EMA_SLOW], "source": "lighter-1d"},
        "pairs": pairs,
        "fleet": fleet,        # CRYPTO-ONLY by contract — see summarize()
        # [2026-07-21 item 18, publish-only] per-asset regime for the venue's
        # non-crypto books lives in `pairs` keyed by symbol (each entry tagged
        # `class`); this block is the display summary. NO consumer yet — the
        # per-asset gate is the next, review-gated step.
        "noncrypto": dict(noncrypto, missing=missing_nc,
                          universe=len(NONCRYPTO)),
        # [2026-07-22 SELF-GRADE, publish-only] per-asset forward alignment
        # of the oracle's OWN directional calls (grade_pairs): grades[sym] =
        # {d1/d3: {n, hit, avg_pp signed INTO the call}}. `grading` is the
        # carried state (pending calls + running sums), not a signal. NO
        # consumer reads either; the step-2 review reads `grades`.
        "grades": grades,
        "grading": grading,
        "errors": errors,
        # [2026-07-17] ADDITIVE — the swap's real cost, made visible. A coin
        # Lighter cannot grade (young book, delisting, dead fetch) is NAMED
        # here with its reason. Silence is what made this a bug.
        # [2026-07-21] `universe`/`n_missing`/`missing`/`complete` keep their
        # original CRYPTO-majors meaning; non-crypto holes live in
        # `noncrypto.missing` (most books are young at ship — by design).
        "coverage": {
            "source": "lighter-1d",
            "universe": len(UNIVERSE),
            "n_published": n_crypto,
            "n_missing": len(missing),
            "missing": missing,
            "complete": not missing,
            "min_bars": EMA_SLOW + SLOPE_BARS,
        },
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
    if missing:
        print(f"[regime-oracle]   COVERAGE: {n_crypto}/{len(UNIVERSE)} graded; "
              f"MISSING " + ", ".join(f"{k}({v})" for k, v in missing.items()))
    else:
        print(f"[regime-oracle]   COVERAGE: {n_crypto}/{len(UNIVERSE)} majors "
              f"graded on Lighter — complete")
    print(f"[regime-oracle]   NON-CRYPTO (per-asset, publish-only): "
          f"{noncrypto['n_published']}/{len(NONCRYPTO)} graded"
          + (f"; young/missing " + ", ".join(f"{k}({v})"
                                             for k, v in missing_nc.items())
             if missing_nc else " — complete"))
    n_d1 = sum(1 for g in grades.values() if "d1" in g)
    print(f"[regime-oracle]   SELF-GRADE: {len(grading['pending'])} calls "
          f"pending; d1 outcomes on {n_d1} syms"
          + ("" if not grades else " | " + " ".join(
              f"{s}:{g['d1']['hit']:.0%}/{g['d1']['avg_pp']:+.2f}pp"
              f"(n{g['d1']['n']})"
              for s, g in sorted(grades.items()) if "d1" in g)[:220]))


def _selftest():
    """Offline: paging, the closed-bar rule, the window trim, and — the one
    that matters — that a short-history coin is NAMED, never silently dropped.
    """
    import unittest.mock as mock

    DAY = 86400
    now = 1752710400 + 3600          # a fixed UTC noon-ish instant
    today = now // DAY * DAY

    def tape(n_days, end_day=None, step=1.0):
        """n_days of synthetic 1d bars ending at yesterday (ms open stamps)."""
        end_day = end_day if end_day is not None else today - DAY
        return [{"t": (end_day - i * DAY) * 1000, "o": 100 + step * i,
                 "h": 101 + step * i, "l": 99 + step * i, "c": 100 + step * i}
                for i in range(n_days)]

    def fake_lget(bars_by_market, calls=None, page=PAGE_CAP):
        """A stub venue. `page` is how many bars it actually serves per call —
        the real one caps at PAGE_CAP, but a stingier page is exactly what the
        backward-paging loop exists to survive."""
        def _f(path, **q):
            if calls is not None:
                calls.append((path, q))
            if path == "/api/v1/orderBookDetails":
                return {"order_book_details": [
                    {"symbol": s, "market_id": m}
                    for s, m in (("BTC", 1), ("ZEC", 2))]}
            all_bars = bars_by_market[q["market_id"]]
            end = int(q["end_timestamp"]) * 1000
            got = sorted((b for b in all_bars if b["t"] <= end),
                         key=lambda b: -b["t"])[:page]
            return {"c": got}
        return _f

    # --- 1. CLOSED bars only, trimmed to the window, ms stamps preserved -----
    full = tape(400) + [{"t": today * 1000, "o": 1, "h": 1, "l": 1, "c": 1}]
    with mock.patch(__name__ + "._lget", fake_lget({1: full})):
        df = fetch_daily(1, now=now)
    assert len(df) == LOOKBACK_DAYS, f"window not trimmed to 300: {len(df)}"
    assert int(df["t"].iloc[-1]) == (today - DAY) * 1000, \
        "today's PARTIAL bar leaked into a closed-candle frame"
    assert int(df["t"].iloc[-1]) > 1e12, "t must stay in MILLISECONDS (asof)"
    assert df["t"].is_monotonic_increasing, "bars must be oldest->newest"

    # --- 2. backward paging ------------------------------------------------
    # NB (measured by this test, not assumed): at LOOKBACK_DAYS=300 ONE 500-bar
    # page already spans the whole window, so the real venue never pages. The
    # loop is a safety net for a raised lookback or a venue that under-serves a
    # page — so test it with a stub that serves 200/call and MUST be paged.
    calls = []
    with mock.patch(__name__ + "._lget",
                    fake_lget({1: tape(400)}, calls, page=200)):
        df = fetch_daily(1, now=now)
    assert len(calls) >= 2, f"under-served page not paged: {len(calls)} call(s)"
    assert len(df) == LOOKBACK_DAYS, f"paging lost bars: {len(df)}"
    assert df["t"].is_monotonic_increasing and len(set(df["t"])) == len(df), \
        "paged bars must be ordered and de-duplicated across pages"

    # one full page IS the window at 300d — no wasted call against the real API
    calls = []
    with mock.patch(__name__ + "._lget", fake_lget({1: tape(700)}, calls)):
        df = fetch_daily(1, now=now)
    assert len(calls) == 1, f"500-bar page should cover 300d in 1 call: {calls}"
    assert len(df) == LOOKBACK_DAYS, len(df)

    # a SHORT book must not loop forever when the venue stops serving older
    calls = []
    with mock.patch(__name__ + "._lget", fake_lget({1: tape(30)}, calls)):
        df = fetch_daily(1, now=now)
    assert len(df) == 30 and len(calls) <= 3, (len(df), len(calls))

    # --- 3. the FROZEN-tape guard: healthy=1d, delisted=NAMED ---------------
    assert tape_age_days(df, now) == 1, \
        "a book that closed yesterday's bar must read age 1d"
    with mock.patch(__name__ + "._lget",
                    fake_lget({1: tape(400, end_day=today - 40 * DAY)})):
        frozen = fetch_daily(1, now=now)
    assert tape_age_days(frozen, now) == 40, tape_age_days(frozen, now)
    assert len(frozen) >= EMA_SLOW + SLOPE_BARS, \
        "the frozen fixture must CLEAR the bar gate — else it proves nothing"

    # --- 4. THE COVERAGE TRAP — a young book is NAMED, never silent ----------
    # ZEC(2) gets 100 bars: under the 203-bar gate. BTC(1) gets a full tape.
    # This is the negative fixture: if `missing` ever goes quiet, this fails.
    published = {}
    with mock.patch(__name__ + "._lget",
                    fake_lget({1: tape(400), 2: tape(100)})), \
            mock.patch.object(store, "load_state", lambda k: {}), \
            mock.patch.object(store, "save_state",
                              lambda k, p: published.update(p)), \
            mock.patch.object(store, "save_history", lambda k, p: None), \
            mock.patch(__name__ + ".UNIVERSE", ["BTC", "ZEC", "GHOST"]), \
            mock.patch(__name__ + ".time", mock.Mock(time=lambda: now,
                                                     sleep=lambda s: None)):
        sys.exit(store.organ_main('regime-oracle', main))
    cov = published["coverage"]
    assert "BTC" in published["pairs"], "a healthy book must still publish"
    assert "ZEC" not in published["pairs"], "a 100-bar book must NOT be graded"
    assert cov["missing"]["ZEC"].startswith("short-history(100<203)"), \
        f"short-history not NAMED with its reason: {cov['missing']}"
    assert cov["missing"]["GHOST"] == "no-lighter-book", \
        f"an unlisted coin must be NAMED: {cov['missing']}"
    assert cov["complete"] is False and cov["n_missing"] == 2, cov
    assert cov["n_published"] == 1 and cov["universe"] == 3, cov
    assert any(e.startswith("ZEC:short-history") for e in published["errors"]), \
        "the pre-existing `errors` contract must still carry the skip"

    # --- 5. a DELISTED book is NAMED, not graded off its frozen tape --------
    # It clears the 203-bar gate (fixture asserted above), so ONLY the
    # staleness guard can stop it. Without this, the oracle would publish a
    # 40-day-old regime as today's.
    published = {}
    with mock.patch(__name__ + "._lget",
                    fake_lget({1: tape(400),
                               2: tape(400, end_day=today - 40 * DAY)})), \
            mock.patch.object(store, "load_state", lambda k: {}), \
            mock.patch.object(store, "save_state",
                              lambda k, p: published.update(p)), \
            mock.patch.object(store, "save_history", lambda k, p: None), \
            mock.patch(__name__ + ".UNIVERSE", ["BTC", "ZEC"]), \
            mock.patch(__name__ + ".time", mock.Mock(time=lambda: now,
                                                     sleep=lambda s: None)):
        main()
    assert "ZEC" not in published["pairs"], \
        "a FROZEN tape was graded — the oracle just asserted a stale regime"
    assert published["coverage"]["missing"]["ZEC"] == "stale-tape(40d)", \
        published["coverage"]["missing"]
    assert "BTC" in published["pairs"], "the healthy book must still publish"
    # the consumer-facing shape must be intact + honest about its source
    for k in ("updated", "ttl_sec", "params", "pairs", "fleet", "errors",
              "grades", "grading"):
        assert k in published, f"payload lost {k}"
    assert published["params"]["source"] == "lighter-1d", published["params"]
    assert published["ttl_sec"] == TTL_SEC and published["updated"]

    # --- 4. a dark venue publishes NOTHING (fail-safe, not a wrong value) ----
    saved = []

    def _boom(path, **q):
        raise OSError("venue dark")
    with mock.patch(__name__ + "._lget", _boom), \
            mock.patch.object(store, "load_state", lambda k: {}), \
            mock.patch.object(store, "save_state",
                              lambda k, p: saved.append(p)):
        main()
    assert not saved, "a dark venue must NOT publish — consumers keep TTL"

    # ---- [2026-07-21 item 18] per-asset coverage: the fleet.read contract --
    # NONCRYPTO and UNIVERSE must never overlap (a symbol in both would be
    # counted into fleet.read AND tagged non-crypto — an incoherent state).
    assert not set(NONCRYPTO) & set(UNIVERSE), set(NONCRYPTO) & set(UNIVERSE)
    # fleet.read is CRYPTO-ONLY: ten shorting non-crypto books must not move
    # it (bot_learn's risk_off join reads fleet.read — the Georgia diagnosis
    # came from it; blending classes is the incoherence item 18 removes).
    _long = {"verdict": "LONG-window"}
    _short = {"verdict": "SHORT-window"}
    _crypto_up = {c: dict(_long) for c in ["BTC", "ETH", "SOL", "BNB", "XRP"]}
    _nc_down = {s: dict(_short) for s in NONCRYPTO}
    _fleet_mixed, _nc_sum = summarize({**_crypto_up, **_nc_down})
    _fleet_alone, _ = summarize(dict(_crypto_up))
    assert _fleet_mixed == _fleet_alone, (_fleet_mixed, _fleet_alone)
    assert _fleet_mixed["read"] == "risk-on uptrend", _fleet_mixed
    assert _nc_sum["n_short"] == len(NONCRYPTO) and _nc_sum["n_published"] == len(NONCRYPTO)
    assert _nc_sum["by_class"]["equity-index"] == ["IWM", "QQQ", "SPY"], _nc_sum
    assert "never blended" in _nc_sum["note"]
    # empty non-crypto (all young at ship) summarizes clean
    _f2, _nc2 = summarize(dict(_crypto_up))
    assert _nc2["n_published"] == 0 and _f2["read"] == "risk-on uptrend"

    # ---- [2026-07-22] SELF-GRADING: calls joined to outcomes --------------
    DAY_MS = 86400 * 1000
    T0 = 1_752_000_000_000 - (1_752_000_000_000 % DAY_MS)
    T1, T3 = T0 + DAY_MS, T0 + 3 * DAY_MS

    def _pv(verdict, close, asof):
        return {"verdict": verdict, "close": close, "asof": str(asof)}

    c1_pairs = {"BTC": _pv("LONG-window", 100.0, T0),
                "SPY": _pv("SHORT-window", 500.0, T0),
                "ETH": _pv("dir-flat", 10.0, T0),
                "SOL": _pv("chop-gated", 20.0, T0)}
    g1, gr1 = grade_pairs(None, c1_pairs, now=T0 // 1000)
    assert {p["sym"] for p in g1["pending"]} == {"BTC", "SPY"}, \
        "directional calls only — the oracle claims no direction elsewhere"
    assert gr1 == {}, "nothing matured on cycle 1"
    # same bar re-observed (intra-day cycle): no duplicate evidence unit
    g1b, _ = grade_pairs(g1, c1_pairs, now=T0 // 1000)
    assert len(g1b["pending"]) == 2, "one call per (sym, closed bar)"
    # +1 bar: LONG on a riser = HIT +3pp; SHORT on a riser = MISS -1pp —
    # the MIRROR check (grade the direction CALLED, never long semantics;
    # the brain's drift grader was direction-blind once — never again)
    c2_pairs = {"BTC": _pv("LONG-window", 103.0, T1),
                "SPY": _pv("LONG-window", 505.0, T1)}
    g2, gr2 = grade_pairs(g1b, c2_pairs, now=T1 // 1000)
    assert gr2["BTC"]["d1"] == {"n": 1, "hit": 1.0, "avg_pp": 3.0}, gr2
    assert gr2["SPY"]["d1"]["hit"] == 0.0 and gr2["SPY"]["d1"]["avg_pp"] == -1.0
    assert len(g2["pending"]) == 4, \
        "d1-graded calls wait for d3; the new T1 bars are fresh calls"
    # the true mirror: a SHORT call on a FALLING book scores POSITIVE pp
    gm, grm = grade_pairs(
        {"pending": [{"sym": "XAU", "asof": str(T0), "close": 200.0,
                      "dir": -1, "done": []}], "scores": {}},
        {"XAU": _pv("SHORT-window", 196.0, T1)}, now=T1 // 1000)
    assert grm["XAU"]["d1"] == {"n": 1, "hit": 1.0, "avg_pp": 2.0}, grm
    # +3 bars (cycle missed a day — graded at first observation >= h):
    # d3 lands, the T0 calls drain from pending, sums accumulate
    c3_pairs = {"BTC": _pv("LONG-window", 99.0, T3),
                "SPY": _pv("SHORT-window", 490.0, T3)}
    g3, gr3 = grade_pairs(g2, c3_pairs, now=T3 // 1000)
    assert gr3["BTC"]["d3"]["n"] == 1 and gr3["BTC"]["d3"]["avg_pp"] == -1.0
    assert gr3["SPY"]["d3"]["avg_pp"] == 2.0, "short mirror on d3 too"
    assert gr3["BTC"]["d1"]["n"] == 2, "T1's call graded d1 against T3"
    assert not any(p["asof"] == str(T0) for p in g3["pending"]), \
        "fully-graded calls must drain"
    # coverage loss: young pending kept, stale pending aged out
    lost = {"pending": [{"sym": "GONE", "asof": str(T0), "close": 5.0,
                         "dir": 1, "done": []}], "scores": {}}
    gk, _ = grade_pairs(lost, {}, now=(T0 + 2 * DAY_MS) // 1000)
    assert len(gk["pending"]) == 1, "young out-of-coverage call waits"
    gd, _ = grade_pairs(lost, {}, now=(T0 + 11 * DAY_MS) // 1000)
    assert gd["pending"] == [], "out-of-coverage call ages out"
    # malformed prior state -> clean start; junk pending dropped; cap holds
    gjunk, _ = grade_pairs("garbage", c1_pairs, now=T0 // 1000)
    assert len(gjunk["pending"]) == 2
    gj2, _ = grade_pairs({"pending": [{"sym": "X", "asof": "nope",
                                       "close": "?"}, "junk"],
                          "scores": {"X": "junk"}},
                         c1_pairs, now=T0 // 1000)
    assert {p["sym"] for p in gj2["pending"]} == {"BTC", "SPY"}
    big = {"pending": [{"sym": f"S{i}", "asof": str(T0), "close": 1.0,
                        "dir": 1, "done": []} for i in range(PENDING_CAP + 40)],
           "scores": {}}
    gcap, _ = grade_pairs(big, {}, now=T0 // 1000)
    assert len(gcap["pending"]) <= PENDING_CAP

    print("regime_oracle selftest OK (closed-bars-by-timestamp, ms stamps, "
          "500-bar paging + termination, young-book NAMED not dropped, "
          "unlisted coin NAMED, FROZEN tape NAMED not graded, payload shape "
          "held, dark venue publishes nothing, per-asset non-crypto coverage "
          "additive + fleet.read stays crypto-only, self-grading: directional-"
          "only, per-bar dedupe, MIRROR-correct short scoring, d1/d3 "
          "accumulate+drain, age-out, cap)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
