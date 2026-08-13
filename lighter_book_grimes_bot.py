#!/usr/bin/env python3
"""
lighter_book_grimes_bot.py — 📐 The Technician (book-grimes), the
QUANTIFIED-EDGE BOOK.

WHAT THIS IS (2026-08-13, operator: "Build me 4 bots for each of these books
... The Art and Science of Technical Analysis — Adam Grimes")
  One $1,000 shadow book that trades Grimes's framework as he actually
  states it: "most price patterns don't work; the only way to know is to
  test; trade only with a quantified edge." Third of the BOOKS cohort's
  second wave (`book-<surname>-lshadow`, named for the AUTHOR).

THE BOOK, AS RULES — the honest translation is NOT any one setup. Twelve
pre-declared variants of Grimes's structural setups were measured on 500d of
Lighter 4h tape before this file was written, and NONE beat random entries
on the full window (best: mtf-pullback +$84.07 at P(random>=strategy)=0.24;
failure test −$284, Keltner fade −$94 full-window). Shipping a refuted setup
is banned; shipping his TESTING DISCIPLINE is the book:

  1. THE ROSTER: his structural setups live in this file as code —
       `pullback` (with-trend, daily-trend aligned), `failtest` (spring/
       upthrust fade), `keltner` (band fade in a non-trending regime).
       `breakout` is structurally ABSENT: that supply is 🧙 book-schwager's
       (I20 — the same signal family on the same coins is the same bet at a
       new row id; selftest-pinned).
  2. THE GATE: every RETEST_H, each setup is replayed through ITS OWN live
       signal code over the trailing WINDOW_D of the venue's own 4h tape
       (cap-2 sequential portfolio, 5bps/side — the study's exact method).
       A setup may ENTER only while its trailing record clears the bar:
       n >= 20 closes, net > $0, t >= +0.5. Fail-CLOSED: a missing or
       stale scorecard admits nothing.
  3. THE SCORECARD IS PUBLIC: every loop publishes each setup's trailing
       {n, net, mean_pct, t, open} — so `open: 0` is never byte-identical
       between "quiet" and "nothing currently tests" (I18/(lv)).
  4. THE REGIME SWITCH IS MECHANICAL: when the tape changes, a setup's
       trailing record opens or closes its gate — Grimes's "match the trade
       to the market regime" without a human in the loop. At authoring the
       trailing-120d scorecard read: keltner n=106, +$48.79, t=0.75 ->
       OPEN; pullback n=130, −$13.32 -> closed; failtest n=294, −$7.24 ->
       closed. The book is born trading exactly one setup, by its own rule.

THE SUPPLY, NAMED (I20): the venue's liquid crypto set (24h vol >= $1M, top
18). A DIRECTIONAL price book: it can hold the same coin as the family
books, the Taker, 🧘 Douglas or 🧙 Schwager at the same moment.
Differentiation is by SIGNAL FAMILY and HORIZON — 4h structure (pullback/
failtest/band-fade, holds ~1-3 days), vs Douglas's 1h impulse fades and
Schwager's multi-day channel breakouts (excluded here). No funding gate.

HONEST ABOUT THE EVIDENCE (scripts/study_books_cohort_2026-08-13.py):
  * the ROSTER mechanism itself is unmeasured as a combination — no
    historical scorecard series exists to backtest gate-switching. What is
    measured: each setup's full-window and trailing-window record (above),
    and the bar the gate applies. The (hm) clock runs from first publish;
    the brain grades each `<side>-<setup>` sleeve separately.
  * the gate's bar (n>=20, net>0, t>=0.5) is DELIBERATELY below the
    go-live bar — it decides which setup may spend shadow clips, not what
    goes live; the go-live gate is unchanged and senior.
  * decidability (I17): if no setup clears the gate for long stretches the
    book is undecidable and that is a keep-or-retire call, not a reason to
    lower this bar. The scorecard makes the starvation visible either way.

CONFIG IS ENV-ONLY — NO TUNING LANE (the Garrett choice): single-policy
(hm) clock by construction.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow only.

Usage:
    VENUE=lighter_shadow python lighter_book_grimes_bot.py          # daemon
    VENUE=lighter_shadow python lighter_book_grimes_bot.py --once   # smoke
    python lighter_book_grimes_bot.py --selftest                    # offline
"""
import argparse
import math
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

# Universe + class screen come from the bus. Guarded: a dark import keeps the
# configured list. COPY lands in Dockerfile.grimes in this same commit.
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "book-grimes"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300

BAR_INTERVAL = "4h"
BAR_SEC = 4 * 3600
ATR_N = 14
EMA_FAST, EMA_SLOW = 20, 50
KELT_MULT = 2.25                # Keltner band width, x ATR

# ---- rule 2: the gate -------------------------------------------------------
RETEST_H = float(os.environ.get("GRIMES_RETEST_H", "6"))
WINDOW_D = float(os.environ.get("GRIMES_WINDOW_D", "120"))
GATE_MIN_N = int(os.environ.get("GRIMES_GATE_MIN_N", "20"))
GATE_MIN_T = float(os.environ.get("GRIMES_GATE_MIN_T", "0.5"))
SCORECARD_TTL_H = 24.0          # older than this -> gate fail-CLOSED
REF_CLIP = 100.0                # the study's reference clip for the replay

CLIP_USD = float(os.environ.get("GRIMES_CLIP_USD", "80"))
MAX_POSITIONS = int(os.environ.get("GRIMES_MAX_POSITIONS", "2"))

MIN_VOL_M = float(os.environ.get("GRIMES_MIN_VOL_M", "1.0"))
UNIVERSE_N = int(os.environ.get("GRIMES_UNIVERSE_N", "18"))
DEFAULT_COINS = ("BTC,ETH,SOL,HYPE,LIT,ZEC,PUMP,XRP,UNI,ETHFI,BNB,ENA,"
                 "DOGE,NEAR,XMR,AVAX,LINK,TAO").split(",")

SLIP_COST = 0.0005
DELIST_GIVEUP_H = 6.0

ALLOW_NONCRYPTO = os.environ.get(
    "GRIMES_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")

#: The roster. `breakout` is DELIBERATELY absent — 🧙 book-schwager owns
#: channel breakouts on this universe (I20); adding it here mints the same
#: bet at a second row id. Selftest-pinned.
SETUPS = ("pullback", "failtest", "keltner")


def _standby_key(bot_id):
    """(ic): the claim loser reports on its OWN key. Suffix, never a rewrite."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- indicators (the study's exact math) -------------
def atr_series(bars, n=ATR_N):
    """Wilder ATR per bar as a fraction of close; None before warmup."""
    out = [None] * len(bars)
    a = None
    trs = []
    prev_c = None
    for i, (_t, _o, h, l, c) in enumerate(bars):
        tr = (h - l) if prev_c is None else max(
            h - l, abs(h - prev_c), abs(l - prev_c))
        prev_c = c
        if a is None:
            trs.append(tr)
            if len(trs) == n:
                a = sum(trs) / n
        else:
            a = (a * (n - 1) + tr) / n
        out[i] = (a / c) if (a and c) else None
    return out


def ema_series(vals, n):
    """EMA per index, seeded at the first value; None before index n."""
    out = [None] * len(vals)
    k = 2.0 / (n + 1)
    e = None
    for i, v in enumerate(vals):
        e = v if e is None else (v * k + e * (1 - k))
        out[i] = e if i >= n else None
    return out


def daily_trend_map(daily_bars):
    """{utc_day_number: +1/-1/0} from daily EMA20 vs EMA50 closes."""
    closes = [b[4] for b in daily_bars or []]
    e20 = ema_series(closes, EMA_FAST)
    e50 = ema_series(closes, EMA_SLOW)
    out = {}
    for j, b in enumerate(daily_bars or []):
        a, s = e20[j], e50[j]
        out[b[0] // 86400] = 0 if (a is None or s is None) else \
            (1 if a > s else -1)
    return out


# --------------------------- the setups (ONE owner: live + replay) -----------
def sig_pullback(bars, i, atrs, e20, e50, dtrend):
    """With-trend pullback, daily trend aligned: EMA20>EMA50, price pierces
    EMA20 and closes back on the trend side. sl 1.5xATR, tp 3R, 20 bars."""
    a, x20, x50 = atrs[i], e20[i], e50[i]
    if not (a and x20 and x50):
        return None
    dt = dtrend.get(bars[i][0] // 86400, 0)
    _t, _o, h, l, c = bars[i]
    if dt > 0 and x20 > x50 and l <= x20 and c > x20:
        return "long", 1.5 * a, 4.5 * a, 20
    if dt < 0 and x20 < x50 and h >= x20 and c < x20:
        return "short", 1.5 * a, 4.5 * a, 20
    return None


def sig_failtest(bars, i, atrs, e20, e50, dtrend):
    """Failure test: the bar pierces the prior 20-bar extreme and closes
    back inside — fade it. sl 1.0xATR, tp 2R, 12 bars."""
    a = atrs[i]
    if not a or i < 22:
        return None
    hh = max(b[2] for b in bars[i - 20:i])
    ll = min(b[3] for b in bars[i - 20:i])
    _t, _o, h, l, c = bars[i]
    if l < ll and c > ll:
        return "long", 1.0 * a, 2.0 * a, 12
    if h > hh and c < hh:
        return "short", 1.0 * a, 2.0 * a, 12
    return None


def sig_keltner(bars, i, atrs, e20, e50, dtrend):
    """Keltner band fade in a NON-trending regime: close beyond EMA20 +/-
    2.25xATR with the daily trend not aligned with the excursion — fade
    toward the mean. sl 1.5xATR, tp 2.25xATR, 20 bars."""
    a, x20 = atrs[i], e20[i]
    if not (a and x20):
        return None
    dt = dtrend.get(bars[i][0] // 86400, 0)
    c = bars[i][4]
    if c > x20 * (1 + KELT_MULT * a) and dt <= 0:
        return "short", 1.5 * a, KELT_MULT * a, 20
    if c < x20 * (1 - KELT_MULT * a) and dt >= 0:
        return "long", 1.5 * a, KELT_MULT * a, 20
    return None


SETUP_FNS = {"pullback": sig_pullback, "failtest": sig_failtest,
             "keltner": sig_keltner}


# --------------------------- the replay gate (rule 2) ------------------------
def replay_setup(setup, bars_by_coin, dtrend_by_coin, cap=None,
                 clip=REF_CLIP):
    """Replay ONE setup over the supplied tape through its own signal code:
    cap-bound sequential portfolio, entry at next bar open, intra-bar
    bracket with the stop checked FIRST (conservative), 5bps/side. Returns
    the closed-trade $ list, oldest-exit first. The study's exact method —
    grading each setup as if it were the whole book."""
    cap = MAX_POSITIONS if cap is None else cap
    fn = SETUP_FNS[setup]
    sigs = []
    for coin, bars in (bars_by_coin or {}).items():
        if len(bars) < EMA_SLOW + 8:
            continue
        atrs = atr_series(bars)
        closes = [b[4] for b in bars]
        e20 = ema_series(closes, EMA_FAST)
        e50 = ema_series(closes, EMA_SLOW)
        dtrend = dtrend_by_coin.get(coin, {})
        for i in range(EMA_SLOW + 6, len(bars) - 1):
            s = fn(bars, i, atrs, e20, e50, dtrend)
            if s is not None:
                side, sl, tp, hold = s
                sigs.append((bars[i + 1][0], coin, i, side, sl, tp, hold))
    sigs.sort()
    idx_of = {c: {b[0]: j for j, b in enumerate(bars)}
              for c, bars in (bars_by_coin or {}).items()}
    all_t = sorted({b[0] for bars in (bars_by_coin or {}).values()
                    for b in bars})
    open_pos = {}
    closed = []
    si = 0
    for t in all_t:
        for coin in list(open_pos):
            p = open_pos[coin]
            j = idx_of[coin].get(t)
            if j is None:
                continue
            _t, o, h, l, c = bars_by_coin[coin][j]
            e = p["entry"]
            sign = p["sign"]
            reason_px = None
            if sign > 0:
                if l <= e * (1 - p["sl"]):
                    reason_px = e * (1 - p["sl"])
                elif h >= e * (1 + p["tp"]):
                    reason_px = e * (1 + p["tp"])
            else:
                if h >= e * (1 + p["sl"]):
                    reason_px = e * (1 + p["sl"])
                elif l <= e * (1 - p["tp"]):
                    reason_px = e * (1 - p["tp"])
            p["bars"] += 1
            if reason_px is None and p["bars"] >= p["hold"]:
                reason_px = c
            if reason_px is not None:
                ret = (reason_px - e) / e * sign - 2 * SLIP_COST
                closed.append(ret * clip)
                del open_pos[coin]
        while si < len(sigs) and sigs[si][0] == t:
            _et, coin, i, side, sl, tp, hold = sigs[si]
            si += 1
            if coin in open_pos or len(open_pos) >= cap:
                continue
            entry = bars_by_coin[coin][i + 1][1]
            if not entry or entry <= 0:
                continue
            open_pos[coin] = {"entry": entry,
                              "sign": 1.0 if side == "long" else -1.0,
                              "sl": sl, "tp": tp, "hold": hold, "bars": 0}
    return closed


def grade(closed, min_n=None, min_t=None):
    """The gate's bar on one setup's trailing record: n, net, mean, t and
    the OPEN verdict (n >= min_n AND net > 0 AND t >= min_t)."""
    min_n = GATE_MIN_N if min_n is None else min_n
    min_t = GATE_MIN_T if min_t is None else min_t
    n = len(closed or [])
    net = sum(closed or [])
    mean = (net / n) if n else 0.0
    t = 0.0
    if n >= 3:
        var = sum((x - mean) ** 2 for x in closed) / (n - 1)
        t = mean / math.sqrt(var / n) if var > 0 else 0.0
    return {"n": n, "net": round(net, 2),
            "mean_pct": round(mean / REF_CLIP * 100, 3) if n else None,
            "t": round(t, 2),
            "open": bool(n >= min_n and net > 0 and t >= min_t)}


def setup_open(scorecard, setup, t0, ttl_h=SCORECARD_TTL_H):
    """May `setup` enter? FAIL-CLOSED: a missing, malformed or stale
    scorecard row admits nothing — no evidence is not evidence."""
    try:
        row = (scorecard or {}).get(setup)
        if not isinstance(row, dict) or not row.get("open"):
            return False
        asof = float(row.get("asof") or 0.0)
        return 0 <= (t0 - asof) <= ttl_h * 3600.0
    except (TypeError, ValueError):
        return False


def resolve_universe(held, current_time=None):
    """Scout's liquid crypto set, falling back to the MEASURED default list
    on any doubt, PLUS every held coin ((hk))."""
    out = list(DEFAULT_COINS)
    try:
        if fleet_bus is not None:
            scout = fleet_bus.scout_universe(
                min_vol_m=MIN_VOL_M, limit=UNIVERSE_N,
                current_time=current_time)
            if not ALLOW_NONCRYPTO:
                scout = fleet_bus.crypto_only(scout)
            if scout:
                out = list(scout[:UNIVERSE_N])
    except Exception:  # noqa: BLE001
        pass
    have = set(out)
    for c in held or ():
        s = str(c).strip().upper()
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


def build_state(positions, acted, scorecard, last_retest, last_ts, now=None):
    """The persistence blob — ONE builder. The scorecard persists so a
    restart keeps gating on the last real evidence (within its TTL) instead
    of trading gate-blind or refetching mid-boot."""
    return {"positions": positions, "acted": acted, "scorecard": scorecard,
            "last_retest": last_retest, "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, scorecard, open_pnl, realized):
    """The published `extra` — ONE builder ((hj)). The scorecard is the
    book's signature payload: rule 3 says the test table is public."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {"setups": list(SETUPS), "retest_h": RETEST_H,
                 "window_d": WINDOW_D, "gate_min_n": GATE_MIN_N,
                 "gate_min_t": GATE_MIN_T,
                 "max_positions": MAX_POSITIONS, "clip_usd": CLIP_USD,
                 "min_vol_m": MIN_VOL_M, "universe_n": UNIVERSE_N,
                 "crypto_only": not ALLOW_NONCRYPTO},
        "scan": census,
        "scorecard": scorecard or {},
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_px, pnl):
    """Ledger one close: `<side>-<setup>_<exit>` + (gr) price telemetry."""
    t = time.time()
    held_h = (t - pos["opened_ts"]) / 3600.0
    entry_px = pos.get("entry_mark")
    try:
        store.publish_paper_trade(
            bot_id, trade_id=f"{key}:{pos['opened_ts']:.0f}",
            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=pos["coin"],
            opened_at=datetime.fromtimestamp(
                pos["opened_ts"], timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=f"{pos['side']}-{pos['setup']}_" + reason,
            venue="lighter", shadow=True, side=pos["side"],
            entry_price=entry_px, exit_price=exit_px,
            extra={"setup": pos.get("setup"),
                   "sl_frac": pos.get("sl_frac"),
                   "tp_frac": pos.get("tp_frac"),
                   "notional": pos.get("notional"),
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, setup, coin, side, mark, sl, tp, hold_bars,
                   t0, signal_t):
    """Open one modelled position at mark with the setup's own bracket.
    One bet per coin across setups. Unpriceable mark refuses."""
    if any(p["coin"] == coin for p in positions.values()):
        return None
    if not mark or mark <= 0 or not sl or sl <= 0:
        return None
    key = f"{setup}:{coin}"
    positions[key] = {"coin": coin, "setup": setup, "side": side,
                      "notional": CLIP_USD, "opened_ts": t0,
                      "entry_mark": mark, "last_mark": mark,
                      "sl_frac": sl, "tp_frac": tp,
                      "max_hold_h": hold_bars * BAR_SEC / 3600.0,
                      "signal_t": signal_t,
                      "fees": SLIP_COST * CLIP_USD}
    return positions[key]


def bracket_exit(pos, mark, t0):
    """The setup's own predefined bracket. 'tp'/'sl'/'max_hold'/None."""
    e = pos["entry_mark"]
    if not e or e <= 0 or not mark or mark <= 0:
        return None
    sign = 1.0 if pos["side"] == "long" else -1.0
    ret = (mark / e - 1.0) * sign
    if ret >= pos["tp_frac"]:
        return "tp"
    if ret <= -pos["sl_frac"]:
        return "sl"
    if (t0 - pos["opened_ts"]) / 3600.0 >= pos["max_hold_h"]:
        return "max_hold"
    return None


def _price_pnl(pos, mark):
    sign = 1.0 if pos["side"] == "long" else -1.0
    m = mark if (mark or 0) > 0 else pos.get("last_mark")
    if not m or not pos.get("entry_mark"):
        return -pos["fees"]
    return sign * (m / pos["entry_mark"] - 1.0) * pos["notional"] - pos["fees"]


def _closed_bars(rows, bar_sec, now_s):
    out = []
    for c in rows or []:
        try:
            t = int(c["t"]) // 1000
            if t + bar_sec <= now_s:
                out.append((t, float(c["o"]), float(c["h"]),
                            float(c["l"]), float(c["c"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    return out


def main():
    p = argparse.ArgumentParser(
        description="📐 The Technician — trade only what tests")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: book-grimes (📐 The Technician) runs "
            "VENUE=lighter_shadow ONLY. $1,000 shadow, fills modelled at "
            "mark; go-live is a separate operator act behind the standard "
            "gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # book-grimes-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}
    acted = {}          # "<setup>:<coin>" -> signal-bar ts already traded
    scorecard = {}
    last_retest = 0.0
    _saved = None
    try:
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved and isinstance(_saved.get("acted"), dict):
            acted = {str(k): v for k, v in _saved["acted"].items()
                     if isinstance(v, (int, float))}
        if _saved and isinstance(_saved.get("scorecard"), dict):
            scorecard = _saved["scorecard"]
        try:
            last_retest = float((_saved or {}).get("last_retest") or 0.0)
        except (TypeError, ValueError):
            last_retest = 0.0
        if _saved is not None:
            print(f"[{now_iso()}] restored {len(positions)} position(s), "
                  f"scorecard for {sorted(scorecard)}")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 📐 The Technician start | venue lighter | roster "
          f"{'/'.join(SETUPS)} | gate n>={GATE_MIN_N}, net>0, "
          f"t>={GATE_MIN_T} over {WINDOW_D:.0f}d, retest {RETEST_H:.0f}h | "
          f"${CLIP_USD:.0f}x{MAX_POSITIONS} | "
          f"realized so far ${realized:+.2f} ({n_closed} closed)")

    last_ts = time.time()
    dtrend_cache = {}
    dtrend_asof = 0.0

    while True:
        t0 = time.time()
        # SOLE-WRITER ENFORCEMENT AT THE TOP OF THE LOOP ((hp)/(ic)).
        _ok_writer, _other = store.claim_writer(bot_id)
        if not _ok_writer:
            print(f"[{now_iso()}] STANDING DOWN — {bot_id} is claimed by "
                  f"another container ({_other}); holding until the claim "
                  f"expires ({store.WRITER_CLAIM_TTL}s).", flush=True)
            try:
                store.save_state(_standby_key(bot_id), {
                    "standing_down": True, "book": bot_id,
                    "duplicate_writer": _other,
                    "svc": store.service_name() or None,
                    "venue": _mode,
                    "caps": {"setups": list(SETUPS),
                             "max_positions": MAX_POSITIONS},
                    "updated": now_iso(),
                    "ttl_sec": store.WRITER_CLAIM_TTL,
                })
            except Exception:  # noqa: BLE001
                pass
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:  # noqa: BLE001
            print(f"[{now_iso()}] mark fetch failed ({e!r}); retrying")
            fund = None

        if fund:
            last_ts = t0
            universe = resolve_universe(
                {p["coin"] for p in positions.values()})
            now_s = int(t0)

            # ---- manage every open position -----------------------------
            for key in list(positions):
                pos = positions[key]
                f = fund.get(pos["coin"])
                mark = float((f or {}).get("mark") or 0.0)
                if f is None or mark <= 0:
                    first = pos.setdefault("missing_since", t0)
                    if (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                        continue
                    px = pos.get("last_mark")
                    pos["fees"] += SLIP_COST * pos["notional"]
                    pnl = _price_pnl(pos, px)
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    _close(bot_id, key, pos, "delisted", px, pnl)
                    print(f"[{now_iso()}] CLOSE {key} [delisted] "
                          f"pnl {pnl:+.2f} | banked {realized:+.2f}")
                    del positions[key]
                    continue
                pos.pop("missing_since", None)
                pos["last_mark"] = mark
                reason = bracket_exit(pos, mark, t0)
                if reason is None:
                    continue
                pos["fees"] += SLIP_COST * pos["notional"]
                pnl = _price_pnl(pos, mark)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                held_h = (t0 - pos["opened_ts"]) / 3600.0
                _close(bot_id, key, pos, reason, mark, pnl)
                print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                      f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                      f"banked {realized:+.2f}")
                del positions[key]

            # ---- the retest (rule 2): replay the roster on fresh tape ---
            if (t0 - last_retest) >= RETEST_H * 3600.0:
                try:
                    deep_bars, deep_trend = {}, {}
                    span_ms = int((WINDOW_D * 86400 +
                                   (EMA_SLOW + 10) * BAR_SEC) * 1000)
                    for coin in universe:
                        try:
                            rows = ctx.venue.candles(
                                coin, BAR_INTERVAL,
                                now_s * 1000 - span_ms, now_s * 1000)
                            bars = _closed_bars(rows, BAR_SEC, now_s)
                            if len(bars) >= EMA_SLOW + 8:
                                deep_bars[coin] = bars
                            drows = ctx.venue.candles(
                                coin, "1d",
                                now_s * 1000 - int(
                                    (WINDOW_D + 80) * 86400 * 1000),
                                now_s * 1000)
                            deep_trend[coin] = daily_trend_map(
                                _closed_bars(drows, 86400, now_s))
                        except Exception:  # noqa: BLE001
                            continue
                    if deep_bars:
                        for s in SETUPS:
                            closed = replay_setup(s, deep_bars, deep_trend)
                            row = grade(closed)
                            row["asof"] = t0
                            scorecard[s] = row
                        last_retest = t0
                        dtrend_cache = deep_trend
                        dtrend_asof = t0
                        print(f"[{now_iso()}] RETEST "
                              + " | ".join(
                                  f"{s}: n={scorecard[s]['n']} "
                                  f"net={scorecard[s]['net']:+.2f} "
                                  f"t={scorecard[s]['t']:.2f} "
                                  f"{'OPEN' if scorecard[s]['open'] else 'closed'}"
                                  for s in SETUPS))
                except Exception as e:  # noqa: BLE001
                    print(f"[{now_iso()}] retest failed ({e!r}); the gate "
                          f"stays on the last scorecard until its TTL")

            # ---- scan for signals from OPEN setups ----------------------
            census = {"scanned": len(universe), "held": 0, "no_bars": 0,
                      "quiet": 0, "signal": 0}
            opened = capped = unpriceable = gated = 0
            held_coins = {p["coin"] for p in positions.values()}
            if (t0 - dtrend_asof) > 6 * 3600.0:
                dtrend_cache = {}       # stale daily trend: setups needing
                                        # it will simply not fire long
            for coin in universe:
                if coin in held_coins:
                    census["held"] += 1
                    continue
                try:
                    end_ms = now_s * 1000
                    start_ms = end_ms - (EMA_SLOW * 4) * BAR_SEC * 1000
                    rows = ctx.venue.candles(coin, BAR_INTERVAL,
                                             start_ms, end_ms)
                except Exception:  # noqa: BLE001
                    census["no_bars"] += 1
                    continue
                bars = _closed_bars(rows, BAR_SEC, now_s)
                if len(bars) < EMA_SLOW + 8:
                    census["no_bars"] += 1
                    continue
                atrs = atr_series(bars)
                closes = [b[4] for b in bars]
                e20 = ema_series(closes, EMA_FAST)
                e50 = ema_series(closes, EMA_SLOW)
                dtrend = dtrend_cache.get(coin, {})
                i = len(bars) - 1
                fired = False
                for s in SETUPS:
                    sig = SETUP_FNS[s](bars, i, atrs, e20, e50, dtrend)
                    if sig is None:
                        continue
                    fired = True
                    if not setup_open(scorecard, s, t0):
                        gated += 1
                        continue
                    akey = f"{s}:{coin}"
                    if acted.get(akey) == bars[i][0]:
                        continue
                    if len(positions) >= MAX_POSITIONS:
                        capped += 1
                        continue
                    side, sl, tp, hold = sig
                    mark = float((fund.get(coin) or {}).get("mark") or 0.0)
                    pos = _open_position(positions, s, coin, side, mark,
                                         sl, tp, hold, t0, bars[i][0])
                    if pos is None:
                        unpriceable += 1
                        continue
                    acted[akey] = bars[i][0]
                    held_coins.add(coin)
                    opened += 1
                    print(f"[{now_iso()}] OPEN {s}:{coin} {side} "
                          f"${CLIP_USD:.0f} @ {mark} | sl {sl:.2%} tp "
                          f"{tp:.2%} hold {hold} bars")
                if fired:
                    census["signal"] += 1
                else:
                    census["quiet"] += 1
            census["opened"] = opened
            census["capped"] = capped
            census["unpriceable"] = unpriceable
            census["gated"] = gated
            acted = {k: v for k, v in acted.items()
                     if isinstance(v, (int, float))
                     and now_s - v < 3 * 86400}

            # ---- publish -------------------------------------------------
            open_pnl = sum(
                _price_pnl(p, float((fund.get(p["coin"]) or {}).get("mark")
                                    or 0.0))
                for p in positions.values())
            equity = START_EQUITY + realized + open_pnl
            extra = build_extra(census, positions, scorecard, open_pnl,
                                realized)
            try:
                store.publish(
                    bot_id, status="online", equity=equity,
                    pnl_abs=realized + open_pnl,
                    pnl_pct=(equity / START_EQUITY - 1.0),
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins,
                    losses=n_closed - n_wins, extra=extra)
                # MTM equity series from DAY ONE ((hq)/I9).
                store.snapshot_equity(bot_id, equity, len(positions), realized)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(bot_id, build_state(
                    positions, acted, scorecard, last_retest, last_ts, t0))
            except Exception:  # noqa: BLE001
                pass

            held_s = ", ".join(sorted(positions)) or "none"
            open_setups = [s for s in SETUPS if setup_open(scorecard, s, t0)]
            print(f"[{now_iso()}] scan ok | {census['scanned']} coins | "
                  f"open: {held_s} | gates open: "
                  f"{','.join(open_setups) or 'NONE'} | open_pnl "
                  f"{open_pnl:+.2f} | banked {realized:+.2f} | quiet "
                  f"{census['quiet']}, signal {census['signal']}, gated "
                  f"{gated}, opened {opened}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Covers the roster's I20 exclusion, each setup's signal
    arithmetic (both sides), the replay engine end-to-end on a fixture, the
    gate's bar in both directions, the fail-closed scorecard TTL, one-bet-
    per-coin, tags and payload builders. Mutation-verified at authoring
    time: adding 'breakout' to SETUPS, opening the gate on net<=0, letting
    a stale scorecard admit, or double-holding a coin each redden this."""
    t = 1_000_000

    # 1) THE I20 PIN: breakout is Schwager's supply, structurally absent.
    assert "breakout" not in SETUPS, \
        "channel breakouts on this universe are 🧙 book-schwager's supply " \
        "(I20) — adding the setup here mints the same bet at a second row"
    assert set(SETUPS) == set(SETUP_FNS), "every setup needs its one owner"

    # 2) setup arithmetic on engineered fixtures
    # keltner: flat tape then a violent poke above the band, daily trend flat
    bars = [(t + i * BAR_SEC, 100.0, 100.6, 99.4, 100.0) for i in range(70)]
    bars.append((t + 70 * BAR_SEC, 100.0, 112.0, 100.0, 111.0))
    atrs = atr_series(bars)
    closes = [b[4] for b in bars]
    e20 = ema_series(closes, EMA_FAST)
    e50 = ema_series(closes, EMA_SLOW)
    i = len(bars) - 1
    sk = sig_keltner(bars, i, atrs, e20, e50, {})
    assert sk is not None and sk[0] == "short", sk
    # the SAME poke with the daily trend UP is refused (regime filter)
    up_day = {bars[i][0] // 86400: 1}
    assert sig_keltner(bars, i, atrs, e20, e50, up_day) is None
    # failtest: pierce the prior 20-bar low, close back above it
    ll = min(b[3] for b in bars[i - 20:i])
    bars_ft = bars[:-1] + [(t + 70 * BAR_SEC, 100.0, 100.2,
                            ll * 0.98, ll * 1.01)]
    sf = sig_failtest(bars_ft, i, atr_series(bars_ft), e20, e50, {})
    assert sf is not None and sf[0] == "long", sf
    # pullback: rising tape, dip through EMA20, close back above, daily up
    rise = []
    px = 100.0
    for j in range(70):
        px *= 1.004
        rise.append((t + j * BAR_SEC, px / 1.004, px * 1.004,
                     px * 0.997, px))
    r_atr = atr_series(rise)
    r_cl = [b[4] for b in rise]
    r20 = ema_series(r_cl, EMA_FAST)
    r50 = ema_series(r_cl, EMA_SLOW)
    ri = len(rise) - 1
    x20 = r20[ri]
    rise[ri] = (rise[ri][0], rise[ri][1], rise[ri][2],
                x20 * 0.998, x20 * 1.004)     # pierce and reclaim EMA20
    day_up = {rise[ri][0] // 86400: 1}
    sp = sig_pullback(rise, ri, r_atr, r20, r50, day_up)
    assert sp is not None and sp[0] == "long", sp
    assert sig_pullback(rise, ri, r_atr, r20, r50, {}) is None, \
        "no daily-trend alignment -> no pullback trade"

    # 3) the replay engine, end-to-end: the keltner fixture must produce a
    # closed SHORT that mean-reverts to profit.
    fix = list(bars)
    fix.append((t + 71 * BAR_SEC, 111.0, 111.5, 100.0, 100.5))   # reversion
    for j in range(3):
        fix.append((t + (72 + j) * BAR_SEC, 100.5, 101.0, 99.9, 100.2))
    closed = replay_setup("keltner", {"AAA": fix}, {"AAA": {}}, cap=2)
    assert len(closed) >= 1, "the fixture's fade must close"
    assert closed[0] > 0, "the reversion trade must be profitable net of fees"

    # 4) the gate, both directions + fail-closed staleness
    g = grade([5.0] * 25)
    assert g["open"] is False, "zero variance -> t=0 -> gate closed"
    g2 = grade([1.0, -0.5] * 15)
    assert g2["n"] == 30 and g2["net"] > 0
    assert grade([1.0] * 10)["open"] is False, "n<20 must not open"
    assert grade([-1.0] * 30)["open"] is False, "net<=0 must not open"
    sc = {"keltner": {"open": True, "asof": float(t)}}
    assert setup_open(sc, "keltner", t + 3600) is True
    assert setup_open(sc, "keltner", t + SCORECARD_TTL_H * 3600 + 1) is False, \
        "a stale scorecard must FAIL CLOSED"
    assert setup_open(sc, "pullback", t + 3600) is False
    assert setup_open({}, "keltner", t) is False
    assert setup_open({"keltner": {"open": True, "asof": "junk"}},
                      "keltner", t) is False

    # 5) one bet per coin across setups
    positions = {}
    p1 = _open_position(positions, "keltner", "AAA", "short", 100.0,
                        0.015, 0.0225, 20, t, t)
    assert p1 is not None
    p2 = _open_position(positions, "failtest", "AAA", "long", 100.0,
                        0.01, 0.02, 12, t, t)
    assert p2 is None, "two setups on one coin is the fleet holding " \
                       "one bet twice (I20's shape, in-book)"

    # 6) bracket exits (setup-owned brackets)
    assert bracket_exit(p1, 100.0 * (1 - 0.0225) * 0.999, t + 60) == "tp"
    assert bracket_exit(p1, 100.0 * (1 + 0.015) * 1.001, t + 60) == "sl"
    assert bracket_exit(p1, 100.0,
                        t + p1["max_hold_h"] * 3600 + 1) == "max_hold"

    # 7) universe contract
    global fleet_bus
    _orig = fleet_bus
    fleet_bus = None
    try:
        assert resolve_universe(set()) == list(DEFAULT_COINS)
        assert "ZZZ" in resolve_universe({"ZZZ"})
    finally:
        fleet_bus = _orig

    # 8) tags round-trip through the REAL parser, per setup sleeve
    for side_ in ("long", "short"):
        for s in SETUPS:
            for exit_r in ("tp", "sl", "max_hold", "delisted"):
                tag, ex = store.split_reason(f"{side_}-{s}_{exit_r}")
                assert tag == f"{side_}-{s}", (tag, side_, s)
                assert ex == exit_r
            assert "_" not in s, "setup names must stay underscore-free " \
                                 "or the first-underscore split breaks"

    # 9) payload builders — the scorecard is public (rule 3)
    cen = {"scanned": 18, "held": 1, "no_bars": 0, "quiet": 16, "signal": 1,
           "opened": 1, "capped": 0, "unpriceable": 0, "gated": 0}
    sc2 = {s: dict(grade([]), asof=float(t)) for s in SETUPS}
    extra = build_extra(cen, positions, sc2, 1.23, 4.56)
    assert set(extra["scorecard"]) == set(SETUPS)
    assert extra["caps"]["setups"] == list(SETUPS)
    assert extra["held"] == {"AAA": "S"}
    st = store.json_safe(extra)
    assert st["caps"]["gate_min_n"] == GATE_MIN_N

    # 10) the persistence blob
    blob = build_state(positions, {"keltner:AAA": float(t)}, sc2, t, t, now=t)
    assert "saved_ts" in blob and "scorecard" in blob

    print("lighter_book_grimes_bot self-tests passed "
          "(I20 roster pin, setup signals, replay engine, gate + fail-closed "
          "TTL, one-bet-per-coin, tags, payload).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
