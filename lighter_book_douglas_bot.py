#!/usr/bin/env python3
"""
lighter_book_douglas_bot.py — 🧘 The Zone (book-douglas), the DISCIPLINE
BOOK.

WHAT THIS IS (2026-08-13, operator: "Build me 4 bots for each of these books
... Trading in the Zone — Mark Douglas")
  One $1,000 shadow book that trades Mark Douglas's discipline doctrine as
  mechanical rules on Lighter's own tape. First of the BOOKS cohort's second
  wave (`book-<surname>-lshadow`, named for the AUTHOR).

THE BOOK, AS RULES — Douglas supplies no entries ("an edge is simply a
higher probability of one thing happening over another"); he supplies the
EXECUTION doctrine. The edge here is the one this venue's tape actually
supports, measured before a line of this file was written:

  1. "Predefine the risk of every trade."
       The bracket is fixed AT ENTRY — stop, target and expiry all derive
       from the entry bar's ATR and are never widened afterward. No code
       path in this file can move a stop away from the price.
  2. "Anything can happen" / think in probabilities, not predictions.
       The edge is a fade of EXTREME 1h impulses (|close-to-close| >
       2.5x ATR24): the disciplined trader is the casino, taking the other
       side of emotional overreaction with a fixed, asymmetric bracket
       (stop 1.0x ATR, target 1.5x ATR, expiry 12h). MEASURED on 208d of
       Lighter 1h tape: ~~+$27.01, both halves positive (+$8.80/+$18.21),
       t=0.84~~ — **CORRECTED IN PLACE 2026-08-16 (I12): those are PRE-(ml)
       numbers and they overstate.** (ml) taught the replay to bracket-test
       the ENTRY BAR's own post-open range, because a live loop realises
       entry-bar stops; its own entry warned that "numbers recorded before
       this correction carry that small optimism". On THIS book it is not
       small. Re-measured 16-Aug through the same harness, decomposed so
       the cause is not guessed (tape roll contributes ~nothing):
           13-Aug window, (ml) OFF : n=562 +$31.70 t=1.00 h1=+$14.10
           13-Aug window, (ml) ON  : n=630 +$17.90 t=0.52 h1=−$10.45
           today  (208d), (ml) ON  : n=641 +$17.38 t=0.50 h1=−$7.73
       So the honest reading is **+$17.38, t=0.50, and h1 NEGATIVE** — the
       entry-bar fix costs 44% of the total, halves t, and flips the first
       half. THE EDGE ITSELF SURVIVES: it still beats 199 of 200
       random-entry draws on BOTH total and per-trade mean, and impulse
       CONTINUATION, the crowd's trade, still loses heavily (see below).
       The mirror is still the message. What does NOT survive is
       "both halves positive" — one of the six go-live bars.
       ALSO RE-MEASURED, because a correction that leaves pre-fix numbers
       standing in its own paragraph is the I12 rot it exists to prevent:
       impulse CONTINUATION under (ml) ON is **n=2919, −$248.65, t=−3.05**
       (recorded pre-(ml) as −$210.59, t=−2.81) — still the crowd's trade,
       still the mirror, and now more negative. The random-entry benchmark
       WAS re-run under (ml) ON and the edge survives it: P≈0.005–0.007
       (200–300 draws) on total, per-trade mean and t.
       DECLARED UNEXPLAINED rather than folded in: no cell reproduces the
       recorded n=575/+$27.01 exactly — the closest pre-(ml) cells are
       n=562/+$31.70 (13-Aug window) and n=574/+$34.02 (full cache), leaving
       ~13 trades and ~$4.69 unaccounted, most likely a refetched tape. The
       (ml) attribution does not depend on it, and it is named rather than
       absorbed.
       Found by the calibration gate of `study_leverage_sizing_2026-08-16`,
       which had to reproduce this book to be allowed to speak about it.
  3. "Wins and losses are randomly distributed" — CONSISTENCY.
       Every trade is the same size. Outcomes cannot alter execution:
       `_open_position` takes no streak, no last-trade, no equity input —
       structural (selftest pins the signature), so no future edit can
       quietly add a martingale. THE REFUTATION THAT SHAPED THIS: a naive
       "revenge guard" (per-coin cooldown after a loss + streak pause) was
       measured and it FLIPPED THE BOOK NEGATIVE (+$27.01 -> −$11.32, a
       PRE-(ml) pair — the direction is what matters and it is unchanged;
       the cell has not been re-measured under (ml) ON) —
       skipping entries after losses is itself an emotional deviation from
       the edge, exactly as Douglas says ("the market doesn't know about
       your last trade"). Not shipped; reported.
  4. "Trade in sample sizes" — the 20-trade exercise.
       The book publishes its rolling 20-trade sample every loop
       (expectancy in R-multiples, win rate REPORTED never a bar, I15) so
       the edge is judged at the sample level, never the trade level.

THE SUPPLY, NAMED (I20): the venue's liquid crypto set (24h vol >= $1M, top
18 by volume — the measured universe). This is a DIRECTIONAL price book: it
can hold the same coin as the family books, the Ticket Taker's lenses or
📐 Grimes at the same moment. Differentiation is by SIGNAL FAMILY and
HORIZON — 1h impulse mean-reversion, median hold ~1h; Grimes trades 4h
structure, 🧙 Schwager 4h channel breakouts (the opposite side of the same
tape). No funding gate; the funding books' supply is untouched.

HONEST ABOUT THE EVIDENCE (scripts/study_books_cohort_2026-08-13.py):
  * winner of a PRE-DECLARED 16-cell grid (impulse {1.5,2.5} x dir
    {cont,fade} x bracket {1.0/1.5, 1.5/1.0} x hold {12,24}) — every
    continuation cell negative, every tight-target cell negative; the
    shipped cell's neighbours agree in sign (fade 2.5 h24: +$22.75).
  * ~~t=0.84~~ **t=0.50 (corrected 16-Aug, see above)** is BELOW the go-live
    t-bar, and the backtest's h1 is now NEGATIVE, so the book would fail two
    of the six bars on its own founding sample. This book exists to earn that
    evidence in shadow, ~92 closes/30d, gradeable ~12-Sep by the standard
    gate — on its OWN ledger, which is the record and outranks any replay
    (I14). Regime caveat (item 18): one tape, mean-reverting in its recent
    half; the brain grades `long-impulse` and `short-impulse` separately.
  * friction modelled flat 5bps/side (Lighter fee is zero, measured; the
    Barnesy mark-sleeve number). Fills AT MARK by declared model.

CONFIG IS ENV-ONLY — NO TUNING LANE (the Garrett choice): single-policy
(hm) clock by construction. Levers are a day-31 decision.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow only.

Usage:
    VENUE=lighter_shadow python lighter_book_douglas_bot.py          # daemon
    VENUE=lighter_shadow python lighter_book_douglas_bot.py --once   # smoke
    python lighter_book_douglas_bot.py --selftest                    # offline
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context
from venues.marks import fresh_mid, stop_marks

# Universe + class screen come from the bus. Guarded: a dark import keeps the
# configured list ((hk): the widening is an enhancement, never a dependency).
# The COPY lands in Dockerfile.douglas in this same commit (born-dark rule).
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "book-douglas"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300

# ---- rule 2: the measured edge ----------------------------------------------
BAR_INTERVAL = "1h"
BAR_SEC = 3600
ATR_N = 24                      # ATR lookback, 1h bars
IMPULSE_K = float(os.environ.get("DOUGLAS_IMPULSE_K", "2.5"))
SL_ATR = float(os.environ.get("DOUGLAS_SL_ATR", "1.0"))
TP_ATR = float(os.environ.get("DOUGLAS_TP_ATR", "1.5"))
MAX_HOLD_H = float(os.environ.get("DOUGLAS_MAX_HOLD_H", "12"))

# ---- rule 3: consistency (same size, every trade) ---------------------------
CLIP_USD = float(os.environ.get("DOUGLAS_CLIP_USD", "100"))
MAX_POSITIONS = int(os.environ.get("DOUGLAS_MAX_POSITIONS", "4"))

# ---- the universe (the measured set) ----------------------------------------
MIN_VOL_M = float(os.environ.get("DOUGLAS_MIN_VOL_M", "1.0"))   # $M, 24h
UNIVERSE_N = int(os.environ.get("DOUGLAS_UNIVERSE_N", "18"))
# the backtest's own 18 coins — the fallback when the scout is dark, so no
# organ outage can shrink this book's universe below what was measured.
DEFAULT_COINS = ("BTC,ETH,SOL,HYPE,LIT,ZEC,PUMP,XRP,UNI,ETHFI,BNB,ENA,"
                 "DOGE,NEAR,XMR,AVAX,LINK,TAO").split(",")

SLIP_COST = 0.0005              # per side, fills at mark (venue fee 0)
DELIST_GIVEUP_H = 6.0
SAMPLE_N = 20                   # rule 4: the Douglas sample size

ALLOW_NONCRYPTO = os.environ.get(
    "DOUGLAS_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")


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
    """Wilder ATR of the LAST bar as a fraction of its close, over closed
    bars [(t,o,h,l,c), ...] oldest-first. None when history is short or the
    last close is unpriceable — 'no data' must never read as 'no risk'."""
    if not bars or len(bars) < n + 2:
        return None
    a = None
    trs = []
    prev_c = None
    for _t, _o, h, l, c, in bars:
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


def impulse_signal(bars, k=None):
    """Rule 2: the last CLOSED bar's close-to-close move beyond k x ATR24 is
    an extreme impulse; the trade is the FADE (side opposes the impulse).
    Returns (side, atr, signal_t) or None. Pure — same code the study ran."""
    k = IMPULSE_K if k is None else k
    a = atr_frac(bars)
    if a is None or len(bars) < 2:
        return None
    c1, c0 = bars[-1][4], bars[-2][4]
    if not c0 or c0 <= 0:
        return None
    chg = (c1 - c0) / c0
    if abs(chg) <= k * a:
        return None
    side = "short" if chg > 0 else "long"      # fade, never chase
    return side, a, bars[-1][0]


def bracket_exit(pos, mark, t0):
    """Rule 1: the predefined bracket, checked against the live mark. The
    stop/target were fixed at entry and are read, never recomputed — a
    bracket that breathes with today's ATR is a bracket that widens.
    Returns 'tp'/'sl'/'max_hold'/None."""
    e = pos["entry_mark"]
    if not e or e <= 0 or not mark or mark <= 0:
        return None
    sign = 1.0 if pos["side"] == "long" else -1.0
    ret = (mark / e - 1.0) * sign
    if ret >= pos["tp_frac"]:
        return "tp"
    if ret <= -pos["sl_frac"]:
        return "sl"
    if (t0 - pos["opened_ts"]) / 3600.0 >= MAX_HOLD_H:
        return "max_hold"
    return None


def recent_entry(key, pos, pnl, closed_at=None):
    """One rolling-sample row, STAMPED so the ledger quarantine can reach it.

    [2026-08-19] The sample used to carry only {pnl, r}. That is unfalsifiable:
    `bot_pnl_store.is_quarantined` keys on (bot, pair, closed_at), so a row the
    fleet has RULED inadmissible could not be identified here and kept being
    counted. Measured live: after the seed-path fix landed, this book published
    `closed 7 / realized -0.12` beside `sample20 {n: 9, sum_usd: -26.60}` — the
    card and rule 4's own discipline instrument disagreeing by exactly the two
    (nm)/(pv) void rows, in the same payload.

    `pair` + `closed_at` are the ONLY additions, and they exist so the ONE
    owner of the question can answer it — never a second copy of the rule.
    """
    return {"pnl": round(pnl, 4),
            "r": (round((pnl / pos["notional"]) / pos["sl_frac"], 3)
                  if pos.get("sl_frac") else None),
            "pair": key,
            "closed_at": closed_at or datetime.now(timezone.utc).isoformat()}


def admissible_recent(bot_id, recent):
    """`recent` minus rows the ledger quarantine withholds.

    Entries stamped before this shipped carry no `pair`/`closed_at`, so they
    CANNOT be asked and are KEPT — fail-OPEN, the same contract
    `is_quarantined` itself uses. They age out of the 20-row window on their
    own; the alternative is guessing which unstamped row is which, and a
    quarantine that swallows rows it cannot classify is the disease, not the
    cure.
    """
    out = []
    for e in (recent or []):
        if not isinstance(e, dict):
            continue
        pair, closed_at = e.get("pair"), e.get("closed_at")
        if pair and closed_at:
            try:
                if store.is_quarantined(bot_id, pair, closed_at):
                    continue
            except Exception:      # noqa: BLE001 — unaskable ⇒ admitted
                pass
        out.append(e)
    return out


def sample20(recent):
    """Rule 4: the rolling 20-trade sample, published every loop. R-multiple
    = return / stop-fraction at entry, so expectancy is denominated in the
    risk that was PREDEFINED (rule 1), not in dollars that vary with ATR.
    Win rate is REPORTED, never a bar (I15)."""
    rows = list(recent or [])[-SAMPLE_N:]
    if not rows:
        return {"n": 0, "expectancy_r": None, "win": None, "sum_usd": 0.0,
                "unstamped": 0}
    rs = [r.get("r") for r in rows if isinstance(r.get("r"), (int, float))]
    wins = sum(1 for r in rows if (r.get("pnl") or 0) > 0)
    # `unstamped`: rows predating the (rk) pair/closed_at stamp — the ones the
    # quarantine CANNOT be asked about and keeps fail-OPEN. Published so the
    # window in which sample20 visibly disagrees with the card (n=9/−$26.60
    # beside closed 7/−$0.12, live 19-Aug) carries its own explanation instead
    # of costing the next reader an investigation. Always present, including 0
    # — an omitted key is byte-identical between "all stamped" and "not
    # computed" ((lv)).
    unstamped = sum(1 for r in rows
                    if not (r.get("pair") and r.get("closed_at")))
    return {"n": len(rows),
            "expectancy_r": (round(sum(rs) / len(rs), 3) if rs else None),
            "win": round(wins / len(rows), 3),
            "sum_usd": round(sum(r.get("pnl") or 0.0 for r in rows), 2),
            "unstamped": unstamped}


def resolve_universe(held, current_time=None):
    """The coins this loop looks at: the scout's liquid crypto set (>= $1M,
    top N by volume), falling back to the MEASURED default list on any doubt
    — [] never means 'trade nothing' — PLUS every held coin ((hk): a coin
    leaving the list must keep its exit, stop and expiry)."""
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


def build_state(positions, recent, acted, last_ts, now=None):
    """The persistence blob — ONE builder. `recent` is the rolling sample
    (rule 4's memory); `acted` maps coin -> the signal-bar ts already traded,
    so a restart cannot re-enter the same impulse."""
    return {"positions": positions, "recent": recent, "acted": acted,
            "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, recent, open_pnl, realized):
    """The published `extra` — ONE builder ((hj))."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {"impulse_k": IMPULSE_K, "sl_atr": SL_ATR, "tp_atr": TP_ATR,
                 "max_hold_h": MAX_HOLD_H, "atr_n": ATR_N,
                 "max_positions": MAX_POSITIONS, "clip_usd": CLIP_USD,
                 "min_vol_m": MIN_VOL_M, "universe_n": UNIVERSE_N,
                 "crypto_only": not ALLOW_NONCRYPTO},
        "scan": census,
        "sample20": sample20(recent),
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_px, pnl, spread_exit=None):
    """Ledger one close: `<side>-impulse_<exit>` + the (gr) price telemetry —
    entry/exit prices from the position's own records, never literals. The
    (mg) Harris fields record the venue's QUOTED spread at entry/exit so the
    flat modelled slip stays falsifiable against the book's own tape."""
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
            reason=f"{pos['side']}-impulse_" + reason,
            venue="lighter", shadow=True, side=pos["side"],
            entry_price=entry_px, exit_price=exit_px,
            extra={"atr_frac": pos.get("atr_frac"),
                   # [(so)] I22 receipt: the brain scale this stake was sized at.
                   "brain_mult": pos.get("brain_mult"),
                   "sl_frac": pos.get("sl_frac"),
                   "tp_frac": pos.get("tp_frac"),
                   "notional": pos.get("notional"),
                   "spread_bps_entry": pos.get("spread_bps_entry"),
                   "spread_bps_exit": spread_exit,
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, coin, side, mark, atr, t0, signal_t,
                   notional=None, brain_mult=1.0):
    """Open one modelled position at mark, bracket predefined from the entry
    bar's ATR (rule 1). SIGNATURE IS THE CONSISTENCY RULE (rule 3): no
    streak, no last-outcome, no equity parameter exists, so size cannot vary
    with results without changing this function's shape. An unpriceable mark
    refuses the entry.

    [2026-08-20 (so)] `notional` arrives as an argument and the rule 3 pin is
    UNCHANGED, because the two are about different things and it is worth
    saying which. What Douglas forbids — and what this book MEASURED at
    +$27.01 -> −$11.32 — is *your last outcome* moving *your next bet*: a
    cooldown after a loss, a pause after a streak, a bigger clip because you
    are up. What arrives here is the brain's per-(book, side) scale, a
    function of >= 30 closes held for >= 3 consecutive brain runs. Two trades
    on the same side in the same cycle get the SAME clip; a trade taken right
    after a loser gets the same clip as one taken after a winner. That is
    consistency, and the pin below still bans every input that would break it.
    """
    if not mark or mark <= 0 or not atr or atr <= 0:
        return None
    ntl = CLIP_USD if notional is None else float(notional)
    positions[coin] = {"coin": coin, "side": side, "notional": ntl,
                       "opened_ts": t0, "entry_mark": mark,
                       "last_mark": mark, "atr_frac": atr,
                       "sl_frac": SL_ATR * atr, "tp_frac": TP_ATR * atr,
                       "signal_t": signal_t,
                       "brain_mult": brain_mult,
                       "fees": SLIP_COST * ntl}
    return positions[coin]


def _price_pnl(pos, mark):
    """Realizable P&L at `mark`: signed price move minus booked fees."""
    sign = 1.0 if pos["side"] == "long" else -1.0
    m = mark if (mark or 0) > 0 else pos.get("last_mark")
    if not m or not pos.get("entry_mark"):
        return -pos["fees"]
    return sign * (m / pos["entry_mark"] - 1.0) * pos["notional"] - pos["fees"]


def _closed_bars(rows, bar_sec, now_s):
    """Candle rows -> [(t_s,o,h,l,c)] oldest-first, CLOSED bars only (the
    still-forming bar votes on nothing)."""
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
        description="🧘 The Zone — the discipline book")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: book-douglas (🧘 The Zone) runs "
            "VENUE=lighter_shadow ONLY. $1,000 shadow, fills modelled at "
            "mark; go-live is a separate operator act behind the standard "
            "gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # book-douglas-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}      # coin -> pos dict
    recent = []         # rolling closed-trade sample (rule 4's memory)
    acted = {}          # coin -> signal-bar ts already traded
    _saved = None
    try:
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved and isinstance(_saved.get("recent"), list):
            # [2026-08-19] withhold quarantined rows from rule 4's sample the
            # same way the seed path withholds them from the totals, so the
            # card and the discipline instrument cannot disagree again.
            recent = admissible_recent(bot_id, _saved["recent"])[-SAMPLE_N:]
        if _saved and isinstance(_saved.get("acted"), dict):
            acted = {str(k): v for k, v in _saved["acted"].items()
                     if isinstance(v, (int, float))}
        if _saved is not None:
            print(f"[{now_iso()}] restored {len(positions)} position(s), "
                  f"{len(recent)}-trade sample")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🧘 The Zone start | venue lighter | fade "
          f">{IMPULSE_K:.1f}xATR{ATR_N} 1h impulses | bracket "
          f"{SL_ATR:.1f}/{TP_ATR:.1f}xATR, {MAX_HOLD_H:.0f}h | "
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
                    "caps": {"impulse_k": IMPULSE_K,
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

        # ---- manage every open position -----------------------------------
        # ((nm)) EXITS DO NOT DEPEND ON THE FUNDING MAP, and the bracket is
        # evaluated on the LIVE BOOK. Both halves were defects:
        #   * this block used to sit inside `if fund:`, so a dark funding
        #     fetch suspended every stop while every position stayed open;
        #   * it read `fund[coin]["mark"]`, a last-trade price frozen at
        #     client construction, so the stop compared a boot-time price
        #     with itself (venues/marks.stop_marks carries the measurement).
        # A stop that is only checked when the funding endpoint answers, at a
        # price captured at boot, is not a stop.
        stops, stop_blind = stop_marks(ctx.venue, set(positions))
        for key in list(positions):
            pos = positions[key]
            mark = stops.get(pos["coin"]) or 0.0
            if mark <= 0:
                first = pos.setdefault("stop_blind_since", t0)
                if (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                    continue
                px = pos.get("last_mark")
                pos["fees"] += SLIP_COST * pos["notional"]
                pnl = _price_pnl(pos, px)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                recent.append(recent_entry(key, pos, pnl))
                recent = recent[-SAMPLE_N:]
                _close(bot_id, key, pos, "delisted", px, pnl)
                print(f"[{now_iso()}] CLOSE {key} [delisted] "
                      f"pnl {pnl:+.2f} | banked {realized:+.2f}")
                del positions[key]
                continue
            pos.pop("stop_blind_since", None)
            pos.pop("missing_since", None)     # pre-(nm) restored state
            pos["last_mark"] = mark
            reason = bracket_exit(pos, mark, t0)
            if reason is None:
                continue
            pos["fees"] += SLIP_COST * pos["notional"]
            pnl = _price_pnl(pos, mark)
            realized += pnl
            n_closed += 1
            n_wins += 1 if pnl > 0 else 0
            recent.append(recent_entry(key, pos, pnl))
            recent = recent[-SAMPLE_N:]
            held_h = (t0 - pos["opened_ts"]) / 3600.0
            _close(bot_id, key, pos, reason, mark, pnl,
                   spread_exit=live_spread_bps(ctx, pos["coin"]))
            print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                  f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                  f"banked {realized:+.2f}")
            del positions[key]
        if stop_blind:
            print(f"[{now_iso()}] STOPS BLIND on {', '.join(stop_blind)} — "
                  f"no live book; bracket NOT evaluated this loop")

        if fund:
            last_ts = t0
            universe = resolve_universe(set(positions))

            # ---- scan for impulses --------------------------------------
            census = {"scanned": len(universe), "held": 0, "no_bars": 0,
                      "quiet": 0, "signal": 0}
            opened = capped = unpriceable = 0
            now_s = int(t0)
            for coin in universe:
                if coin in positions:
                    census["held"] += 1
                    continue
                try:
                    end_ms = now_s * 1000
                    # ((mh)) 3x the ATR span: a Wilder ATR seeded five steps
                    # ago is not the study's converged ATR.
                    start_ms = end_ms - (ATR_N * 3 + 6) * BAR_SEC * 1000
                    rows = ctx.venue.candles(coin, BAR_INTERVAL,
                                             start_ms, end_ms)
                except Exception:  # noqa: BLE001
                    census["no_bars"] += 1
                    continue
                bars = _closed_bars(rows, BAR_SEC, now_s)
                sig = impulse_signal(bars)
                if sig is None:
                    if len(bars) < ATR_N + 2:
                        census["no_bars"] += 1
                    else:
                        census["quiet"] += 1
                    continue
                census["signal"] += 1
                side, a, sig_t = sig
                if acted.get(coin) == sig_t:
                    census["repeat"] = census.get("repeat", 0) + 1
                    continue                    # this impulse already traded
                if len(positions) >= MAX_POSITIONS:
                    acted[coin] = sig_t         # ((mh)) sim semantics: a
                    capped += 1                 # cap-bound signal is DROPPED,
                    continue                    # never retried at drifted marks
                # ((nm)) price the ENTRY on the live book too — the funding
                # map's mark is frozen at boot, so entries were being booked
                # at prices the venue never offered (ROBO 0.017707 against a
                # 12:00 bar of [0.014507, 0.014938]). An unpriceable coin
                # refuses the entry, which _open_position already enforces.
                mark = fresh_mid(ctx.venue, coin) or 0.0
                # [2026-08-20 (so)] the brain's per-(book, side) scale, keyed
                # on the SAME `<side>-impulse` record_close publishes. See
                # _open_position's note for why this is not the cooldown
                # overlay this book measured and refused.
                _clip, _bm = (fleet_bus.brain_clip(
                    bot_id, f"{side}-impulse", CLIP_USD,
                    deployed_usd=sum(p.get("notional") or 0.0
                                     for p in positions.values()),
                    gross_cap_usd=fleet_bus.brain_gross_cap(MAX_POSITIONS,
                                                            CLIP_USD))
                    if fleet_bus is not None else (CLIP_USD, 1.0))
                pos = _open_position(positions, coin, side, mark, a, t0, sig_t,
                                     notional=_clip, brain_mult=_bm)
                if pos is None:
                    acted[coin] = sig_t
                    unpriceable += 1
                    continue
                pos["spread_bps_entry"] = live_spread_bps(ctx, coin)
                acted[coin] = sig_t
                opened += 1
                print(f"[{now_iso()}] OPEN {coin} {side} ${_clip:.0f}"
                      f"{'' if _bm == 1.0 else f' (brain {_bm:.2f}x)'} @ "
                      f"{mark} | fade {IMPULSE_K:.1f}xATR impulse | "
                      f"sl {pos['sl_frac']:.2%} tp {pos['tp_frac']:.2%} "
                      f"exp {MAX_HOLD_H:.0f}h")
            census["opened"] = opened
            census["capped"] = capped
            census["unpriceable"] = unpriceable
            # ((nm)) a held coin with no live book has an UNEVALUATED stop —
            # published so `open: N` is never byte-identical between "stops
            # live" and "stops blind" (I1/I18).
            census["stops_blind"] = len(stop_blind)
            # prune acted stamps older than two days — the map must not grow
            acted = {c: t for c, t in acted.items()
                     if isinstance(t, (int, float)) and now_s - t < 2 * 86400}

            # ---- publish -------------------------------------------------
            # ((nm)) MTM on the live book, not the boot-frozen mark — this
            # number feeds snapshot_equity and therefore the go-live maxDD
            # bar (I9), so a stale price here grades the book wrong too.
            # _price_pnl falls back to the position's own last_mark at 0.
            open_pnl = sum(
                _price_pnl(p, stops.get(p["coin"]) or 0.0)
                for p in positions.values())
            equity = START_EQUITY + realized + open_pnl
            extra = build_extra(census, positions, recent, open_pnl, realized)
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
                    positions, recent, acted, last_ts, t0))
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
    """Offline. Covers the ATR/impulse arithmetic (fade direction pinned —
    the mirror IS the finding), the predefined bracket (fixed at entry, both
    sides, expiry), the consistency rule as a SIGNATURE pin, the R-multiple
    sample, the universe fallback contract, tags through the REAL parser and
    the payload builders. Mutation-verified at authoring time: flipping the
    fade to continuation, widening a stored bracket, or adding an outcome
    parameter to _open_position each redden this."""
    import inspect

    # fixture: 30 flat 1h bars then one violent up bar (close 100 -> 110)
    t = 1_000_000
    bars = [(t + i * 3600, 100.0, 100.5, 99.5, 100.0) for i in range(30)]
    bars.append((t + 30 * 3600, 100.0, 111.0, 100.0, 110.0))

    # 1) ATR + impulse: the violent bar fires, and the trade FADES it
    a = atr_frac(bars)
    assert a is not None and a > 0
    sig = impulse_signal(bars)
    assert sig is not None, "a 10% move on a 1% ATR tape must fire"
    side, a2, sig_t = sig
    assert side == "short", \
        "an UP impulse is FADED short — continuation measured t=-2.81"
    assert sig_t == bars[-1][0]
    # a quiet tape fires nothing
    assert impulse_signal(bars[:-1]) is None
    # symmetric: a violent down bar is faded long
    bars_dn = bars[:-1] + [(t + 30 * 3600, 100.0, 100.0, 89.0, 90.0)]
    sd = impulse_signal(bars_dn)
    assert sd is not None and sd[0] == "long"
    # short history refuses (no data is not no risk)
    assert atr_frac(bars[:10]) is None

    # 2) the predefined bracket: fixed at entry, never recomputed
    positions = {}
    pos = _open_position(positions, "A", "short", 110.0, 0.01, t, sig_t)
    assert pos is not None
    assert abs(pos["sl_frac"] - SL_ATR * 0.01) < 1e-12
    assert abs(pos["tp_frac"] - TP_ATR * 0.01) < 1e-12
    # short: profit when mark falls to the target
    assert bracket_exit(pos, 110.0 * (1 - TP_ATR * 0.01) * 0.999, t + 60) == "tp"
    assert bracket_exit(pos, 110.0 * (1 + SL_ATR * 0.01) * 1.001, t + 60) == "sl"
    assert bracket_exit(pos, 110.0, t + 60) is None
    assert bracket_exit(pos, 110.0, t + MAX_HOLD_H * 3600 + 1) == "max_hold"
    # long side mirrors
    pl = _open_position({}, "B", "long", 100.0, 0.02, t, sig_t)
    assert bracket_exit(pl, 100.0 * (1 + TP_ATR * 0.02) * 1.001, t + 60) == "tp"
    assert bracket_exit(pl, 100.0 * (1 - SL_ATR * 0.02) * 0.999, t + 60) == "sl"
    # unpriceable mark refuses the entry
    assert _open_position({}, "C", "long", 0.0, 0.02, t, sig_t) is None
    assert _open_position({}, "C", "long", 100.0, None, t, sig_t) is None

    # 3) CONSISTENCY IS STRUCTURAL (rule 3): sizing can see no outcomes.
    params = set(inspect.signature(_open_position).parameters)
    for banned in ("streak", "last_pnl", "equity", "wins", "losses",
                   "cooldown", "last_outcome", "consecutive", "drawdown"):
        assert banned not in params, \
            f"_open_position grew a '{banned}' input — outcomes must not " \
            "size trades (the measured cooldown overlay cost $38.33). " \
            "[(so)] `notional`/`brain_mult` are DELIBERATELY allowed and " \
            "are not this: the brain's scale is a per-(book, side) function " \
            "of >=30 closes over >=3 runs, identical for every trade in a " \
            "cycle, so it cannot express 'I just lost, bet differently'."
    # …and the default is still the flat clip, so a caller that passes no
    # notional sizes exactly as this book always has.
    assert pos["notional"] == CLIP_USD == pl["notional"]
    assert pos["brain_mult"] == 1.0, "unsized entries record a 1.0 receipt"
    _pb = _open_position({}, "BM", "long", 100.0, 0.02, t, sig_t,
                         notional=CLIP_USD * 2, brain_mult=2.0)
    assert _pb["notional"] == CLIP_USD * 2 and _pb["brain_mult"] == 2.0
    assert abs(_pb["fees"] - SLIP_COST * CLIP_USD * 2) < 1e-12, \
        "fees must be charged on the SIZED notional, not the flat clip"

    # 4) the 20-trade sample (rule 4): R denominated in predefined risk
    rec = [{"pnl": 1.5, "r": 1.5}, {"pnl": -1.0, "r": -1.0}]
    s = sample20(rec)
    assert s["n"] == 2 and abs(s["expectancy_r"] - 0.25) < 1e-9
    assert s["win"] == 0.5 and abs(s["sum_usd"] - 0.5) < 1e-9
    assert sample20([])["n"] == 0
    long_rec = [{"pnl": 1.0, "r": 0.5}] * 40
    assert sample20(long_rec)["n"] == SAMPLE_N, "the sample is capped at 20"

    # 5) universe: dark bus keeps the measured list; held coins never drop
    global fleet_bus
    _orig = fleet_bus
    fleet_bus = None
    try:
        uni = resolve_universe(set())
        assert uni == list(DEFAULT_COINS), \
            "a dark scout must keep the configured list, never shrink it"
        uni2 = resolve_universe({"ZZZ"})
        assert "ZZZ" in uni2, "(hk): a held coin keeps its exits"
    finally:
        fleet_bus = _orig

    # 6) closed-bar filter: the forming bar votes on nothing
    rows = [{"t": (t + i * 3600) * 1000, "o": 1, "h": 1, "l": 1, "c": 1}
            for i in range(3)]
    cb = _closed_bars(rows, 3600, t + 2 * 3600 + 10)
    assert len(cb) == 2, "the still-forming bar must be dropped"

    # 7) tags round-trip through the REAL parser
    for side_ in ("long", "short"):
        for exit_r in ("tp", "sl", "max_hold", "delisted"):
            tag, ex = store.split_reason(f"{side_}-impulse_{exit_r}")
            assert tag == f"{side_}-impulse", (tag, side_, exit_r)
            assert ex == exit_r, (ex, exit_r)

    # 8) publisher-built payload
    cen = {"scanned": 18, "held": 1, "no_bars": 0, "quiet": 16, "signal": 1,
           "opened": 1, "capped": 0, "unpriceable": 0}
    extra = build_extra(cen, positions, rec, 1.23, 4.56)
    assert extra["caps"]["impulse_k"] == IMPULSE_K
    assert extra["caps"]["crypto_only"] is True
    assert extra["held"] == {"A": "S"}, extra["held"]
    assert extra["sample20"]["n"] == 2
    st = store.json_safe(extra)
    assert st["caps"]["clip_usd"] == CLIP_USD

    # 9) P&L arithmetic at mark, fees booked both halves
    p9 = _open_position({}, "D", "short", 100.0, 0.01, t, sig_t)
    p9["fees"] += SLIP_COST * p9["notional"]        # close half
    pnl = _price_pnl(p9, 99.0)
    assert abs(pnl - (0.01 * CLIP_USD - 2 * SLIP_COST * CLIP_USD)) < 1e-9

    # 10) the persistence blob
    blob = build_state(positions, rec, {"A": float(sig_t)}, t, now=t)
    assert "saved_ts" in blob and blob["acted"] == {"A": float(sig_t)}


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

    print("lighter_book_douglas_bot self-tests passed "
          "(impulse fade, predefined bracket, consistency signature, "
          "20-sample, universe contract, tags, payload).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
