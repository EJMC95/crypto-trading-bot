#!/usr/bin/env python3
"""
lighter_book_schwager_bot.py — 🧙 The Wizard (book-schwager), the
CUT-LOSSES-RIDE-WINNERS BOOK.

WHAT THIS IS (2026-08-13, operator: "Build me 4 bots for each of these books
... Market Wizards — Jack Schwager")
  One $1,000 shadow book that trades the wizards' consensus doctrine as
  mechanical rules on Lighter's own tape. Second of the BOOKS cohort's
  second wave (`book-<surname>-lshadow`, named for the AUTHOR).

THE INTERVIEWS, AS RULES — Schwager's wizards disagree on everything except
execution; the rules below are the consensus, and every one was measured on
this venue's tape before it shipped:

  1. "Ride winners" (Seykota) — NO PROFIT TARGET. The only profit exit is a
       WIDE trailing stop: a chandelier 3.5x ATR14 below the close-basis
       high-water mark (above, for shorts), ratcheting only. MEASURED as
       the whole edge: trail 3.5x = +$457.21 vs trail 2.5x = −$29.88 on the
       same entries — the tight trail gives the winners back.
  2. "Cut losses" (everyone) — the initial stop is 2x ATR14, fixed at
       entry, live until the first trail update supersedes it.
  3. "Trade with the trend" (Marcus, Kovner) — entries are 4h Donchian-20
       closing-channel breakouts, confirmed by EMA20 > EMA50 (long side;
       mirrored short), the classic wizard entry on the horizon that is
       DECIDABLE here: the daily variant measured 2.9 closes/30d — the 🌊
       Tide Rider shape I17 retired — and was refused for it.
  4. "Never add to a loser" — and on this tape, never add AT ALL. The
       famous pyramid rule was MEASURED AND REFUTED: adding units into
       winners turned +$457.21 into −$292.83 (trail 3.5) and −$1,103.57
       (trail 2.5), t=−5.8 — pyramiding buys chop exposure at the top of
       every leg. STRUCTURAL here: one position per coin, and no code path
       adds to an open position (selftest-pinned).
  5. "Undertrade" (Kovner) — $80 x 4 slots, fixed, no leverage stacking.

THE SUPPLY, NAMED (I20): the venue's liquid crypto set (24h vol >= $1M, top
18 — the measured universe). A DIRECTIONAL price book: it can hold the same
coin as the family books, the Taker's lenses, 🧘 Douglas or 📐 Grimes at the
same moment. Differentiation is by SIGNAL FAMILY and HORIZON — 4h channel
BREAKOUTS with a multi-day trail (median hold ~112h), the opposite trade of
Douglas's 1h fades. Grimes's roster EXCLUDES breakout structurally so this
supply has one owner. No funding gate; the funding books are untouched.

HONEST ABOUT THE EVIDENCE (scripts/study_books_cohort_2026-08-13.py, 500d of
Lighter 4h tape, 18 coins, 5bps/side):
  * shipped cell: n=277, +$457.21, mean +1.65%/trade, t=1.88, halves
    +$357.90/+$99.31, beats 197 of 200 random-entry draws (P=0.015);
    251 of 277 exits are the trail — the rule doing the earning.
  * longs +$443.40 / shorts +$13.80: the long side carried the window.
    Shorts stay ON — they paid for themselves and are the only regime
    insurance a one-tape validation has (item 18); the brain grades
    `long-trend` and `short-trend` separately.
  * t=1.88 is below the go-live bar; ~17 closes/30d puts 30 closes at
    ~54 days — gradeable ~mid-Oct by the standard gate. This book exists
    to earn that sample in shadow.
  * grid discipline: 10 pre-declared cells; every pyramid cell negative,
    every 2.5-trail cell negative, don=55 weaker than don=20, 1d
    undecidable. The shipped cell's neighbour (don=55, trail 3.5, no
    pyramid) agrees in sign (+$155.69).

CONFIG IS ENV-ONLY — NO TUNING LANE (the Garrett choice): single-policy
(hm) clock by construction. Levers are a day-31 decision.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow only.

Usage:
    VENUE=lighter_shadow python lighter_book_schwager_bot.py          # daemon
    VENUE=lighter_shadow python lighter_book_schwager_bot.py --once   # smoke
    python lighter_book_schwager_bot.py --selftest                    # offline
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

# Universe + class screen come from the bus. Guarded: a dark import keeps the
# configured list. COPY lands in Dockerfile.schwager in this same commit.
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "book-schwager"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300

# ---- rule 3: the trend entry ------------------------------------------------
BAR_INTERVAL = "4h"
BAR_SEC = 4 * 3600
DON_N = int(os.environ.get("SCHWAGER_DON_N", "20"))
EMA_FAST, EMA_SLOW = 20, 50
ATR_N = 14

# ---- rules 1/2: exits -------------------------------------------------------
SL_ATR = float(os.environ.get("SCHWAGER_SL_ATR", "2.0"))
TRAIL_ATR = float(os.environ.get("SCHWAGER_TRAIL_ATR", "3.5"))
MAX_HOLD_H = float(os.environ.get("SCHWAGER_MAX_HOLD_H", "720"))   # 30d

# ---- rule 5: undertrade -----------------------------------------------------
CLIP_USD = float(os.environ.get("SCHWAGER_CLIP_USD", "80"))
MAX_POSITIONS = int(os.environ.get("SCHWAGER_MAX_POSITIONS", "4"))

MIN_VOL_M = float(os.environ.get("SCHWAGER_MIN_VOL_M", "1.0"))
UNIVERSE_N = int(os.environ.get("SCHWAGER_UNIVERSE_N", "18"))
DEFAULT_COINS = ("BTC,ETH,SOL,HYPE,LIT,ZEC,PUMP,XRP,UNI,ETHFI,BNB,ENA,"
                 "DOGE,NEAR,XMR,AVAX,LINK,TAO").split(",")

SLIP_COST = 0.0005
DELIST_GIVEUP_H = 6.0

ALLOW_NONCRYPTO = os.environ.get(
    "SCHWAGER_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")


def _standby_key(bot_id):
    """(ic): the claim loser reports on its OWN key. Suffix, never a rewrite."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- microstructure telemetry ((mg)) -----------------
def spread_bps(book):
    """Quoted spread of a live order book in bps of mid, or None when the
    book cannot support a claim. Harris (Trading and Exchanges): the spread
    is the price of immediacy — this book MODELS its fills at mark plus a
    flat slip constant, and recording what the venue actually quotes at
    entry/exit is what keeps that constant falsifiable instead of asserted.
    Levels with non-positive price/size are filtered (the Farmer's measured
    lesson: a negative level sorts first and fabricates a garbage mid), and
    a crossed book returns None — a book that is not a price makes no claim."""
    try:
        bids = [p for p, s in (book or {}).get("bids") or [] if p > 0 and s > 0]
        asks = [p for p, s in (book or {}).get("asks") or [] if p > 0 and s > 0]
        if not bids or not asks:
            return None
        bid, ask = max(bids), min(asks)
        mid = (bid + ask) / 2.0
        if mid <= 0 or ask < bid:
            return None
        return round((ask - bid) / mid * 1e4, 2)
    except Exception:      # noqa: BLE001
        return None


def live_spread_bps(ctx, coin):
    """One orderbook fetch -> quoted spread bps. TELEMETRY ONLY, never a
    gate — None on any failure, and a dark book must not slow the pass."""
    try:
        return spread_bps(ctx.venue.orderbook(coin))
    except Exception:      # noqa: BLE001
        return None


# --------------------------- pure decision layer -----------------------------
def atr_frac(bars, n=ATR_N):
    """Wilder ATR of the LAST bar as a fraction of its close. None when the
    history is short or unpriceable."""
    if not bars or len(bars) < n + 2:
        return None
    a = None
    trs = []
    prev_c = None
    for _t, _o, h, l, c in bars:
        tr = (h - l) if prev_c is None else max(
            h - l, abs(h - prev_c), abs(l - prev_c))
        prev_c = c
        if a is None:
            trs.append(tr)
            if len(trs) == n:
                a = sum(trs) / n
        else:
            a = (a * (n - 1) + tr) / n
    if not a or not prev_c or prev_c <= 0:
        return None
    return a / prev_c


def ema_last(vals, span):
    """EMA of the series' last value, seeded at the first (converged over
    the fetched window). None on empty."""
    if not vals:
        return None
    k = 2.0 / (span + 1.0)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def trend_signal(bars, don_n=None):
    """Rule 3: the last CLOSED bar closes beyond the prior don_n-bar closing
    channel, with the EMAs aligned. Returns (side, atr, signal_t) or None.
    Pure — same code the study ran."""
    don_n = DON_N if don_n is None else don_n
    if not bars or len(bars) < max(don_n + 2, EMA_SLOW + 5):
        return None
    a = atr_frac(bars)
    if a is None:
        return None
    closes = [b[4] for b in bars]
    ef = ema_last(closes, EMA_FAST)
    es = ema_last(closes, EMA_SLOW)
    if ef is None or es is None:
        return None
    prior = closes[-(don_n + 1):-1]
    c = closes[-1]
    if c > max(prior) and ef > es:
        return "long", a, bars[-1][0]
    if c < min(prior) and ef < es:
        return "short", a, bars[-1][0]
    return None


def update_trail(pos, mark):
    """Rule 1: ratchet the chandelier from the close-basis high-water mark.
    The trail only ever TIGHTENS (monotone toward the price) — a trail that
    can loosen is a stop that widens. Mutates hwm/trail_px."""
    if not mark or mark <= 0:
        return
    a = pos["atr_frac"]
    if pos["side"] == "long":
        pos["hwm"] = max(pos.get("hwm") or mark, mark)
        t = pos["hwm"] * (1.0 - TRAIL_ATR * a)
        pos["trail_px"] = max(pos.get("trail_px") or 0.0, t)
    else:
        pos["hwm"] = min(pos.get("hwm") or mark, mark)
        t = pos["hwm"] * (1.0 + TRAIL_ATR * a)
        prev = pos.get("trail_px")
        pos["trail_px"] = t if prev is None else min(prev, t)


def trend_exit(pos, mark, t0):
    """Rules 1/2: the trail once it exists, else the fixed initial stop;
    max-hold recycles a trade the trend never paid. Checked BEFORE the trail
    update each loop (the study's ordering). Returns
    'trail'/'sl'/'max_hold'/None."""
    e = pos["entry_mark"]
    if not e or e <= 0 or not mark or mark <= 0:
        return None
    sign = 1.0 if pos["side"] == "long" else -1.0
    trail = pos.get("trail_px")
    if trail is not None:
        hit = mark <= trail if pos["side"] == "long" else mark >= trail
        if hit:
            return "trail"
    else:
        ret = (mark / e - 1.0) * sign
        if ret <= -pos["sl_frac"]:
            return "sl"
    if (t0 - pos["opened_ts"]) / 3600.0 >= MAX_HOLD_H:
        return "max_hold"
    return None


def resolve_universe(held, current_time=None):
    """Scout's liquid crypto set, falling back to the MEASURED default list
    on any doubt, PLUS every held coin ((hk))."""
    out = list(DEFAULT_COINS)
    try:
        if fleet_bus is not None:
            # [(mh)] NO limit on the scout read: `limit` truncates to the
            # venue's top-N across ALL instrument classes BEFORE the crypto
            # screen, so every non-crypto book in the volume top-18 silently
            # shrank this book's universe below the measured 18. Screen
            # first, then truncate.
            scout = fleet_bus.scout_universe(
                min_vol_m=MIN_VOL_M, current_time=current_time)
            if not ALLOW_NONCRYPTO:
                scout = fleet_bus.crypto_only(scout)
            if scout:
                out = list(scout[:UNIVERSE_N])
    except Exception:  # noqa: BLE001
        pass
    have = set(out)
    for c in held or ():
        s = str(c).strip()      # ((mh)) venue symbols verbatim — no .upper()
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


def build_state(positions, acted, last_ts, now=None):
    """The persistence blob — ONE builder. Trail/hwm ride inside each
    position dict so a restart resumes the ratchet where it left it."""
    return {"positions": positions, "acted": acted, "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, open_pnl, realized):
    """The published `extra` — ONE builder ((hj))."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {"don_n": DON_N, "sl_atr": SL_ATR, "trail_atr": TRAIL_ATR,
                 "max_hold_h": MAX_HOLD_H, "ema": [EMA_FAST, EMA_SLOW],
                 "max_positions": MAX_POSITIONS, "clip_usd": CLIP_USD,
                 "min_vol_m": MIN_VOL_M, "universe_n": UNIVERSE_N,
                 "pyramid": False,        # refuted, structural — see header
                 "crypto_only": not ALLOW_NONCRYPTO},
        "scan": census,
        "trails": {p["coin"]: {"hwm": p.get("hwm"),
                               "trail_px": p.get("trail_px")}
                   for p in positions.values()},
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_px, pnl, spread_exit=None):
    """Ledger one close: `<side>-trend_<exit>` + (gr) price telemetry + the
    (mg) Harris quoted-spread fields (falsifiable slip model)."""
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
            reason=f"{pos['side']}-trend_" + reason,
            venue="lighter", shadow=True, side=pos["side"],
            entry_price=entry_px, exit_price=exit_px,
            extra={"atr_frac": pos.get("atr_frac"),
                   "sl_frac": pos.get("sl_frac"),
                   "trail_px": pos.get("trail_px"),
                   "hwm": pos.get("hwm"),
                   "notional": pos.get("notional"),
                   "spread_bps_entry": pos.get("spread_bps_entry"),
                   "spread_bps_exit": spread_exit,
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, coin, side, mark, atr, t0, signal_t):
    """Open ONE position at mark. Rule 4 is this function's shape: it keys
    by coin and refuses a coin already held, and no other code path mutates
    a position's notional — there is no add-to-winner and no add-to-loser,
    measured and refuted (−$292.83 to −$1,103.57). An unpriceable mark
    refuses the entry."""
    if coin in positions:
        return None
    if not mark or mark <= 0 or not atr or atr <= 0:
        return None
    if TRAIL_ATR * atr >= 0.9 or SL_ATR * atr >= 0.9:
        return None      # ((mh)) a stop wider than the price is not a stop:
                         # hwm*(1-3.5*atr) <= 0 clamps the long trail to 0
                         # and silently disables BOTH stops
    positions[coin] = {"coin": coin, "side": side, "notional": CLIP_USD,
                       "opened_ts": t0, "entry_mark": mark,
                       "last_mark": mark, "atr_frac": atr,
                       "sl_frac": SL_ATR * atr,
                       "hwm": mark, "trail_px": None,
                       "signal_t": signal_t,
                       "fees": SLIP_COST * CLIP_USD}
    return positions[coin]


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
        description="🧙 The Wizard — cut losses, ride winners")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: book-schwager (🧙 The Wizard) runs "
            "VENUE=lighter_shadow ONLY. $1,000 shadow, fills modelled at "
            "mark; go-live is a separate operator act behind the standard "
            "gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # book-schwager-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}
    acted = {}          # coin -> signal-bar ts already traded
    _saved = None
    try:
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved and isinstance(_saved.get("acted"), dict):
            acted = {str(k): v for k, v in _saved["acted"].items()
                     if isinstance(v, (int, float))}
        if _saved is not None:
            print(f"[{now_iso()}] restored {len(positions)} position(s)")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🧙 The Wizard start | venue lighter | 4h "
          f"Donchian-{DON_N} + EMA{EMA_FAST}/{EMA_SLOW} | sl {SL_ATR:.1f}x, "
          f"trail {TRAIL_ATR:.1f}xATR, hold<={MAX_HOLD_H:.0f}h, NO pyramid | "
          f"${CLIP_USD:.0f}x{MAX_POSITIONS} | "
          f"realized so far ${realized:+.2f} ({n_closed} closed)")

    last_ts = time.time()

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
                    "caps": {"don_n": DON_N,
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
            universe = resolve_universe(set(positions))

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
                # exit check first, then the ratchet — the study's ordering
                reason = trend_exit(pos, mark, t0)
                if reason is None:
                    # ((mh)) THE RATCHET FEEDS ON CLOSED 4h BARS, NEVER the
                    # 5-min mark: the study's +$457 ratcheted the chandelier
                    # on bar CLOSES, and feeding intrabar highs tightens the
                    # trail toward the REFUTED 2.5x-shaped behavior. One
                    # candles call per held coin per loop; a dark fetch
                    # skips the ratchet (the trail keeps its last level and
                    # exits keep running on the live mark).
                    try:
                        rows = ctx.venue.candles(
                            pos["coin"], BAR_INTERVAL,
                            (int(t0) - 3 * BAR_SEC) * 1000, int(t0) * 1000)
                        cb = _closed_bars(rows, BAR_SEC, int(t0))
                        if cb:
                            bt, _o, _h, _l, bc = cb[-1]
                            if (bt + BAR_SEC > pos["opened_ts"]
                                    and bt != pos.get("trail_bar_t")):
                                update_trail(pos, bc)
                                pos["trail_bar_t"] = bt
                    except Exception:  # noqa: BLE001
                        pass
                    continue
                pos["fees"] += SLIP_COST * pos["notional"]
                px = pos["trail_px"] if reason == "trail" else mark
                if reason == "trail" and pos["side"] == "long":
                    px = min(mark, pos["trail_px"])   # gap through the trail
                elif reason == "trail":
                    px = max(mark, pos["trail_px"])
                pnl = _price_pnl(pos, px)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                held_h = (t0 - pos["opened_ts"]) / 3600.0
                _close(bot_id, key, pos, reason, px, pnl,
                       spread_exit=live_spread_bps(ctx, pos["coin"]))
                print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                      f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                      f"banked {realized:+.2f}")
                del positions[key]

            # ---- scan for breakouts -------------------------------------
            census = {"scanned": len(universe), "held": 0, "no_bars": 0,
                      "quiet": 0, "signal": 0}
            opened = capped = unpriceable = 0
            now_s = int(t0)
            # ((mh)) 3x the slow span: an EMA50 seeded over a 61-bar
            # window is half-converged and flips the confirm near crosses
            # where the study's full-history EMAs did not.
            need = max(DON_N + 2, EMA_SLOW * 3, ATR_N + 2) + 10
            for coin in universe:
                if coin in positions:
                    census["held"] += 1
                    continue
                try:
                    end_ms = now_s * 1000
                    start_ms = end_ms - need * BAR_SEC * 1000
                    rows = ctx.venue.candles(coin, BAR_INTERVAL,
                                             start_ms, end_ms)
                except Exception:  # noqa: BLE001
                    census["no_bars"] += 1
                    continue
                bars = _closed_bars(rows, BAR_SEC, now_s)
                sig = trend_signal(bars)
                if sig is None:
                    if len(bars) < max(DON_N + 2, EMA_SLOW + 5):
                        census["no_bars"] += 1
                    else:
                        census["quiet"] += 1
                    continue
                census["signal"] += 1
                side, a, sig_t = sig
                if acted.get(coin) == sig_t:
                    census["repeat"] = census.get("repeat", 0) + 1
                    continue
                if len(positions) >= MAX_POSITIONS:
                    acted[coin] = sig_t     # ((mh)) sim semantics: a
                    capped += 1             # cap-bound signal is DROPPED,
                    continue                # never retried at drifted marks
                mark = float((fund.get(coin) or {}).get("mark") or 0.0)
                pos = _open_position(positions, coin, side, mark, a, t0, sig_t)
                if pos is None:
                    acted[coin] = sig_t
                    unpriceable += 1
                    continue
                pos["spread_bps_entry"] = live_spread_bps(ctx, coin)
                acted[coin] = sig_t
                opened += 1
                print(f"[{now_iso()}] OPEN {coin} {side} ${CLIP_USD:.0f} @ "
                      f"{mark} | Donchian-{DON_N} breakout | sl "
                      f"{pos['sl_frac']:.2%}, trail {TRAIL_ATR:.1f}xATR")
            census["opened"] = opened
            census["capped"] = capped
            census["unpriceable"] = unpriceable
            acted = {c: t for c, t in acted.items()
                     if isinstance(t, (int, float))
                     and now_s - t < 5 * 86400}

            # ---- publish -------------------------------------------------
            open_pnl = sum(
                _price_pnl(p, float((fund.get(p["coin"]) or {}).get("mark")
                                    or 0.0))
                for p in positions.values())
            equity = START_EQUITY + realized + open_pnl
            extra = build_extra(census, positions, open_pnl, realized)
            try:
                store.publish(
                    bot_id, status="online", equity=equity,
                    pnl_abs=realized + open_pnl,
                    pnl_pct=(equity / START_EQUITY - 1.0),
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins,
                    losses=n_closed - n_wins, extra=extra)
                # MTM equity series from DAY ONE ((hq)/I9) — a book whose
                # median hold is ~112h is exactly I9's blind spot otherwise.
                store.snapshot_equity(bot_id, equity, len(positions), realized)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(bot_id, build_state(
                    positions, acted, last_ts, t0))
            except Exception:  # noqa: BLE001
                pass

            held_s = ", ".join(sorted(positions)) or "none"
            print(f"[{now_iso()}] scan ok | {census['scanned']} coins | "
                  f"open: {held_s} | open_pnl {open_pnl:+.2f} | banked "
                  f"{realized:+.2f} | quiet {census['quiet']}, signal "
                  f"{census['signal']}, no_bars {census['no_bars']}, "
                  f"opened {opened}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Covers the Donchian+EMA entry (both sides, trend confirm
    binding), the trail's monotone ratchet, the initial-stop-then-trail
    handoff, the NO-PYRAMID structural pin, the universe fallback, tags and
    payload builders. Mutation-verified at authoring time: loosening the
    ratchet, letting a held coin re-open, or dropping the EMA confirm each
    redden this."""
    import inspect
    t = 1_000_000

    # fixture: a rising tape that breaks its 20-bar closing high
    bars = []
    px = 100.0
    for i in range(80):
        px *= 1.002
        bars.append((t + i * 4 * 3600, px / 1.002, px * 1.004,
                     px * 0.996, px))
    hi = max(b[4] for b in bars[-(DON_N + 1):-1])
    bars.append((t + 80 * 4 * 3600, px, hi * 1.02, px * 0.999, hi * 1.01))

    # 1) the entry: breakout + trend confirm, both binding
    sig = trend_signal(bars)
    assert sig is not None and sig[0] == "long", sig
    # the same breakout with the EMAs AGAINST it is refused: a falling tape
    fall = []
    px2 = 100.0
    for i in range(80):
        px2 *= 0.998
        fall.append((t + i * 4 * 3600, px2 / 0.998, px2 * 1.004,
                     px2 * 0.996, px2))
    lo = min(b[4] for b in fall[-(DON_N + 1):-1])
    fall.append((t + 80 * 4 * 3600, px2, px2 * 1.001, lo * 0.98, lo * 0.99))
    sd = trend_signal(fall)
    assert sd is not None and sd[0] == "short", sd
    # a down-break on the RISING tape is refused (EMA confirm binds)
    mixed = bars[:-1] + [(t + 80 * 4 * 3600, px, px,
                          min(b[4] for b in bars[-(DON_N + 1):-1]) * 0.98,
                          min(b[4] for b in bars[-(DON_N + 1):-1]) * 0.99)]
    assert trend_signal(mixed) is None, \
        "a short against EMA20>EMA50 must be refused"
    assert trend_signal(bars[:30]) is None, "short history refuses"

    # 2) the trail: ratchets toward price, NEVER loosens
    positions = {}
    pos = _open_position(positions, "A", "long", 100.0, 0.01, t, bars[-1][0])
    assert pos is not None and pos["trail_px"] is None
    update_trail(pos, 100.0)
    t1 = pos["trail_px"]
    assert abs(t1 - 100.0 * (1 - TRAIL_ATR * 0.01)) < 1e-9
    update_trail(pos, 110.0)
    t2 = pos["trail_px"]
    assert t2 > t1, "a new high must ratchet the trail up"
    update_trail(pos, 105.0)
    assert pos["trail_px"] == t2, \
        "a pullback must NOT loosen the trail — the ratchet is the rule"
    assert pos["hwm"] == 110.0
    # short side mirrors (trail ratchets DOWN)
    ps = _open_position({}, "B", "short", 100.0, 0.01, t, bars[-1][0])
    update_trail(ps, 100.0)
    s1 = ps["trail_px"]
    update_trail(ps, 90.0)
    s2 = ps["trail_px"]
    assert s2 < s1
    update_trail(ps, 95.0)
    assert ps["trail_px"] == s2, \
        "a bounce must NOT loosen the short trail — the ratchet is the rule"

    # 3) exits: initial stop before the first ratchet, trail after
    pf = _open_position({}, "C", "long", 100.0, 0.01, t, bars[-1][0])
    assert trend_exit(pf, 100.0 * (1 - SL_ATR * 0.01) * 0.999, t + 60) == "sl"
    update_trail(pf, 100.0)
    assert trend_exit(pf, pf["trail_px"] * 0.999, t + 60) == "trail"
    assert trend_exit(pf, pf["trail_px"] * 1.05, t + 60) is None
    assert trend_exit(pf, 100.0,
                      t + MAX_HOLD_H * 3600 + 1) == "max_hold"

    # 4) NO PYRAMID, STRUCTURAL (rule 4): a held coin cannot be re-opened,
    # and no parameter exists to add units — the refuted rule cannot return
    # without changing this file's shape.
    again = _open_position(positions, "A", "long", 111.0, 0.01, t + 60,
                           bars[-1][0])
    assert again is None, \
        "re-opening a held coin is pyramiding — measured −$292.83 to " \
        "−$1,103.57, refused structurally"
    assert _open_position({}, "W", "long", 100.0, 0.30, t, bars[-1][0]) \
        is None, "((mh)) a 105%-wide trail is no stop — entry must refuse"
    params = set(inspect.signature(_open_position).parameters)
    for banned in ("units", "add", "pyramid", "scale_in"):
        assert banned not in params, f"a '{banned}' input is the pyramid door"

    # 5) universe contract
    global fleet_bus
    _orig = fleet_bus
    fleet_bus = None
    try:
        uni = resolve_universe(set())
        assert uni == list(DEFAULT_COINS)
        assert "ZZZ" in resolve_universe({"ZZZ"}), "(hk): held coins stay"
    finally:
        fleet_bus = _orig

    # 6) tags round-trip through the REAL parser
    for side_ in ("long", "short"):
        for exit_r in ("trail", "sl", "max_hold", "delisted"):
            tag, ex = store.split_reason(f"{side_}-trend_{exit_r}")
            assert tag == f"{side_}-trend", (tag, side_, exit_r)
            assert ex == exit_r, (ex, exit_r)

    # 7) payload builders
    cen = {"scanned": 18, "held": 1, "no_bars": 0, "quiet": 16, "signal": 1,
           "opened": 1, "capped": 0, "unpriceable": 0}
    extra = build_extra(cen, positions, 1.23, 4.56)
    assert extra["caps"]["pyramid"] is False
    assert extra["caps"]["trail_atr"] == TRAIL_ATR
    assert extra["held"] == {"A": "L"}, extra["held"]
    assert "A" in extra["trails"]
    st = store.json_safe(extra)
    assert st["caps"]["don_n"] == DON_N

    # 8) P&L at mark, fees both halves
    p8 = _open_position({}, "D", "long", 100.0, 0.01, t, bars[-1][0])
    p8["fees"] += SLIP_COST * p8["notional"]
    pnl = _price_pnl(p8, 101.0)
    assert abs(pnl - (0.01 * CLIP_USD - 2 * SLIP_COST * CLIP_USD)) < 1e-9

    # 9) the persistence blob
    blob = build_state(positions, {"A": float(bars[-1][0])}, t, now=t)
    assert "saved_ts" in blob and "positions" in blob


    # (mg) Harris spread telemetry: pure arithmetic + the refusal shapes
    good = {"bids": [(99.0, 5.0), (98.0, 1.0)], "asks": [(101.0, 4.0)]}
    assert abs(spread_bps(good) - 200.0) < 0.5, spread_bps(good)
    assert spread_bps({"bids": [], "asks": [(1, 1)]}) is None
    assert spread_bps({"bids": [(-1.0, 50), (99.0, 1)],
                       "asks": [(101.0, 1)]}) == \
        spread_bps({"bids": [(99.0, 1)], "asks": [(101.0, 1)]}), \
        "a negative level must be FILTERED, never a mid (the Farmer's lesson)"
    assert spread_bps({"bids": [(102.0, 1)], "asks": [(101.0, 1)]}) is None, \
        "a crossed book is not a price and makes no claim"
    assert spread_bps(None) is None

    print("lighter_book_schwager_bot self-tests passed "
          "(entry+confirm, monotone trail, stop handoff, no-pyramid pin, "
          "universe contract, tags, payload).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
