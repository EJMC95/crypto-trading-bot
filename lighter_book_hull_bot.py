#!/usr/bin/env python3
"""
lighter_book_hull_bot.py — 🧮 The Professor (book-hull), the COST-OF-CARRY
BOOK.

WHAT THIS IS (2026-08-13, operator: "Build me 4 bots for each of these books
... Options, Futures, and Other Derivatives — John Hull")
  One $1,000 shadow book that trades Hull's futures-pricing machinery as
  mechanical rules on Lighter's funding tape. Fourth of the BOOKS cohort
  (`book-<surname>-lshadow`, named for the AUTHOR).

THE TEXTBOOK, AS RULES:

  1. Cost of carry (ch. 5): a perp's funding rate IS its financing rate —
       the term that ties the contract to its index. A perp paying funding
       above fair carry is mispriced relative to cash-and-carry; the
       arbitrageur takes the RECEIVING side, delta-neutral, and collects
       the carry. This book does exactly that, MODELLED delta-neutral: P&L
       = accrued funding − modelled costs, NO price term anywhere in this
       file (the 🏦 Rich Dad structural rule, inherited).
  2. The no-arbitrage BAND (ch. 5): transaction costs put a band around
       fair value inside which no arbitrage exists. Encoded as PAYBACK
       VELOCITY: at the entry rate, funding must repay the declared 30bps
       round trip within PAYBACK_MAX_H (336h) ⇒ effective floor ~7.8% TRUE
       apr. Below that, the "mispricing" is inside the cost band and is not
       a trade.
  3. Basis risk (ch. 3): short-horizon basis oscillation is noise around
       carry, not a signal to unwind a hedge. Encoded as the 24h flip
       grace: a position PAYING funding is closed only after the adverse
       side persists FLIP_GRACE_H — MEASURED as the difference between this
       book existing and not existing (grace 1h: −$16.84, t=−6.65, 136 of
       158 exits paying the round trip on a sign wobble; grace 24h: +$4.92,
       t=+3.27, both halves positive — scripts/study_books_cohort_2026-08-13.py;
       re-measured 16-Aug (ny) at +$6.69, t=+3.92, both halves positive, and
       the grace-1h refutation reproduces — see HONEST ABOUT THE EVIDENCE).
  4. Convergence (ch. 5): entering AGAINST the basis gives away convergence
       P&L. The adverse-basis veto refuses an entry whose premium (mark vs
       index) opposes the position by more than BASIS_VETO_BPS. Restrict-only
       and UNMEASURED (no historical premium series exists to sim it);
       fail-OPEN on a dark feed, so the measured baseline rule above is the
       floor, never hostage to this refinement. Stated, not buried (I19).
  5. Margin prudence (ch. 2): position notional is bounded and fixed —
       $80 × 4 slots, no leverage stacking, no top-ups.

THE SUPPLY, NAMED (I20 — measured before minting, 13-Aug):
  TRUE |apr| in [~7.8%, 20%) × 24h volume in [$2M, $10M), crypto only.
  This cell COMPLETES THE FLEET'S VOLUME TILING at the mid-band aprs:
    🛢️ Garrett  [0.1M, 2M)   @ >=5%  — thin tier (its band excludes this)
    🧮 Hull     [2M, 10M)    @ [7.8%, 20%)  — THIS BOOK
    💸 Farmer   [10M, inf)   @ >=5%  — deep tier (its floor excludes this)
  The 20% CEILING hands everything above it to the carry cohort (🌾 carry,
  🎸 Barnesy's carry sleeve, 🏦 Rich Dad all enter at >=20% TRUE / $2M) —
  half-open, so no coin is ever two books' supply at the boundary. ZERO
  living rivals admit this cell. Live occupancy at authoring: LIT, ZEC,
  PUMP (the venue's ~10.5% base-rate coins in the mid tier — supply present
  in ~100% of measured hours, vs the carry cell's 6.6%).

HONEST ABOUT THE EVIDENCE (scripts/study_books_cohort_2026-08-13.py, 219d of
Lighter's own settled funding series, 18-coin liquid set):
  * the shipped rule (persist 24h, grace 24h, band floor payback-derived):
    n=45, +$4.92, t=+3.27, halves +$0.75/+$4.17.
    **[16-Aug (ny) — RE-MEASURED, AND IT HOLDS. This is the cohort book whose
    founding number SURVIVES.]** On a tape now 250d (the funding series grew
    31 days), the same cell reads **n=50, +$6.69, t=+3.92, halves
    +$3.17/+$3.53** — better than recorded, both halves positive, and the
    REFUTED grace-1h cell reproduces too (−$18.62, t=−5.95 vs −$16.84,
    t=−6.65). **(ml) does not touch this book**: `hull_run` is its own funding
    walk, not the `run_portfolio` bracket walk whose entry-bar look-ahead
    corrected 🧘 Douglas and could not reproduce 🧙 Schwager.
    STRESSED, because t=3.92 on n=50 and $6.69 total is a thin sample:
      - CONCENTRATION IS LOW, the opposite of Schwager: the best trade is 16%
        of the total and dropping it RAISES t to 4.01; top 3 = 34% (t=3.65);
        top 5 = 46% (t=3.22). 14 coins contributed, 11 positive; dropping the
        best coin (XMR) leaves n=47, +$4.73, t=3.67.
      - BLOCK BOOTSTRAP on the per-trade mean: 95% CI **[+$0.065, +$0.204]**
        with **P(mean<=0) = 0.000** at L=1, 5 and 10 — the autocorrelation a
        funding book must answer for does not move it.
      - CLUSTER-ROBUST t ((kw)) = 3.92 unchanged, n_eff 50: these closes do
        not batch, so there is no clustering penalty to take.
    ONE NUMBER ABOVE IS NOT REPRODUCIBLE AND IS WITHDRAWN: the
    "random-timing control P(rand >= real) = 0.000 across 200 draws".
    **There is no Hull random control in the study** — `random_bench` is
    invoked for Douglas and Schwager only — so that figure cannot be
    reproduced from the cited file. An independent random-timing control
    (random entry hours, random coins, same count, same exit rules, 300
    draws) gives **P ≈ 0.043–0.047**: still clears 0.05, but it is a marginal
    result, not an overwhelming one. Quote 0.045, not 0.000, and note the
    construction is mine rather than the original's.
  * ~~tier-restricted to today's [2M,10M) members: n=30, +$4.17, t=+2.76,
    halves +$0.55/+$3.62~~ **[does NOT reproduce, and the reason is benign:
    volume-tier membership MOVED.** Of the study's 18 coins only LINK and LIT
    sit in [$2M,$10M) today, giving n=19, +$3.64, t=3.63 — still positive,
    smaller n. Point-in-time volume is not reconstructable (the survivorship
    caveat below already says so), so this number will drift with every
    re-run and should be read as a sensitivity, never as a second headline.
    Note the direction of the mismatch: the STUDY sees 18 coins while the BOT
    scans the whole venue (live census: 225 scanned, 121 below band, 28 above,
    1 held) — so the study is a SUBSET of the book's real supply, not a
    superset.]** ~4-6 closes/30d — the I17 clock is SLOW (30 closes
    ~5-7 months) and that is declared here, not discovered later.
    **Measured 16-Aug: 6.0 closes/30d, so ~5 months to 30 closes from a
    standing start. Unlike 🧙 Schwager the binding bar here is CLOSES, not
    `t` — this book needs TIME, not a better statistic.**
  * the grid is a PLATEAU, not a lucky cell: every persist>=24h × grace>=6h
    × floor {7.8%, 10%} cell is positive; every grace=1h cell is negative.
  * survivorship caveat: the universe is today's liquid set; historical
    tier membership is not reconstructable from the venue's API.
  The COMBINATION is a NEW policy — fresh 30-day clock ((hm)), nothing
  inherited from any parent's ledger.

CONFIG IS ENV-ONLY — NO TUNING LANE (the Garrett choice, (lp)): single-policy
(hm) clock by construction. Levers are a day-31 decision.

MODELLED, DECLARED (flat and conservative, the cohort numbers): each leg pair
charges SLIP_COST + HEDGE_COST per side (15bps per side, 30bps round trip —
Lighter's perp fee is zero, measured; the hedge leg is modelled). Funding
accrues at the venue's own hourly settlement via funding_basis.to_hourly;
every bar in this file is a TRUE-apr fraction on the one basis authority.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow is the only
accepted mode (loud SystemExit otherwise). No order path exists in this file.

Usage:
    VENUE=lighter_shadow python lighter_book_hull_bot.py          # daemon
    VENUE=lighter_shadow python lighter_book_hull_bot.py --once   # smoke
    python lighter_book_hull_bot.py --selftest                    # offline
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import venue_context

# The class screen's one owner. Guarded like every optional organ: a dark
# import fails OPEN (admit), never a crash inside a trading loop. The COPY
# lands in Dockerfile.hull in this same commit (born-dark rule).
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "book-hull"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300              # funding is hourly; 5-min polling is plenty

H = funding_basis.periods_per_year("lighter")
HOURS_PER_YEAR = 24.0 * 365.0

# ---- rule 5: margin prudence ------------------------------------------------
CLIP_USD = float(os.environ.get("HULL_CLIP_USD", "80"))
MAX_POSITIONS = int(os.environ.get("HULL_MAX_POSITIONS", "4"))

# ---- rule 2: the no-arbitrage band ------------------------------------------
# modelled friction, declared: 15bps per side on both legs of the modelled
# pair -> 30bps round trip of notional (the cohort's flat-conservative model).
SLIP_COST = 0.0005              # per side (Lighter fee is zero, measured)
HEDGE_COST = 0.0010             # per side, the modelled off-venue hedge leg
RT_COST_FRAC = 2.0 * (SLIP_COST + HEDGE_COST)
# funding must repay the round trip within this many hours at the ENTRY rate.
# 336h (2/3 of the max hold) ⇒ effective floor RT*8760/336 ≈ 7.82% TRUE apr —
# the cost band's edge, derived from the declared friction, not hand-picked.
PAYBACK_MAX_H = float(os.environ.get("HULL_PAYBACK_MAX_H", "336"))
APR_LO_EFF = RT_COST_FRAC * HOURS_PER_YEAR / PAYBACK_MAX_H
# the band CEILING: everything at/above it is the carry cohort's supply
# (🌾/🎸/🏦 all enter >= 20% TRUE / $2M). Half-open — I20's tiling rule.
APR_HI = float(os.environ.get("HULL_APR_HI", "0.20"))
EXIT_APR = float(os.environ.get("HULL_EXIT_APR", "0.035"))

# ---- the volume TIER [2M, 10M): completes Garrett|Hull|Farmer ---------------
MIN_VOL = float(os.environ.get("HULL_MIN_VOL", "2e6"))
MAX_VOL = float(os.environ.get("HULL_MAX_VOL", "10e6"))   # half-open [lo, hi)

# ---- rule 3: basis noise tolerances (the measured cells) --------------------
STABLE_H = 24.0                 # same receiving side, in-band, this long
FLIP_GRACE_H = 24.0             # paying side must persist this long to close
MAX_HOLD_H = 21 * 24            # 504h — recycle capital
DELIST_GIVEUP_H = 24.0
PAYBACK_MARGIN = 0.07           # decay-close only when net after ALL fees
                                # clears this (accrued >= ~1.3x the round trip
                                # on the $80 clip — the simmed cell exactly)
BLEED_FRAC = 0.02

# ---- rule 4: the adverse-basis veto (restrict-only, unmeasured, declared) ---
BASIS_VETO_BPS = float(os.environ.get("HULL_BASIS_VETO_BPS", "10"))
LIGHTER_API = os.environ.get(
    "LIGHTER_API", "https://mainnet.zklighter.elliot.ai")

# ---- (lk): crypto perps only, reversible without a deploy -------------------
ALLOW_NONCRYPTO = os.environ.get(
    "HULL_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")


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
def _class_ok(coin):
    """May `coin` ENTER this book? Crypto perps only — (lk). Fail-OPEN, the
    canonical owner's own direction."""
    if ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.is_crypto(coin))
    except Exception:      # noqa: BLE001
        return True


def in_band(apr, apr_lo=None, apr_hi=None):
    """Rule 2: is |TRUE apr| inside the tradeable band [lo, hi)? Half-open at
    the ceiling so no coin is ever both this book's supply and the carry
    cohort's (I20)."""
    lo = APR_LO_EFF if apr_lo is None else apr_lo
    hi = APR_HI if apr_hi is None else apr_hi
    a = abs(apr or 0.0)
    return lo <= a < hi


def payback_hours(apr, rt_cost_frac=None):
    """Hours for funding at TRUE apr `apr` to repay the full modelled round
    trip. inf when there is no income. Monotone-decreasing in |apr|."""
    rt = RT_COST_FRAC if rt_cost_frac is None else rt_cost_frac
    a = abs(apr or 0.0)
    if a <= 0.0:
        return float("inf")
    return rt / (a / HOURS_PER_YEAR)


def basis_veto(side, prem_bps, veto_bps=None):
    """Rule 4: refuse an entry whose basis OPPOSES it by more than the veto.
    A short below fair value (prem < -veto) or a long above it (prem > +veto)
    pays convergence away at entry. `prem_bps is None` (dark feed) ALLOWS —
    the veto is an unmeasured refinement; the measured baseline must not
    hang on it. Returns True when the entry is REFUSED."""
    v = BASIS_VETO_BPS if veto_bps is None else veto_bps
    if prem_bps is None:
        return False
    if side == "short":
        return prem_bps < -v
    return prem_bps > v


def candidates(fund, held, stable_since, t0, prem_map=None, apr_lo=None,
               apr_hi=None, min_vol=None, max_vol=None, max_n=None,
               stable_h=STABLE_H, class_ok=None):
    """Eligible (coin, f, apr) rows, hottest first, capped at max_n.

    Gate order (census mirrors it exactly): not held, parseable, below-band,
    above-band (the carry cohort's supply — handed off, never taken), thin,
    deep (the Farmer's tier), stability persistence, crypto class, adverse
    basis. Pure; decides nothing."""
    apr_lo = APR_LO_EFF if apr_lo is None else apr_lo
    apr_hi = APR_HI if apr_hi is None else apr_hi
    min_vol = MIN_VOL if min_vol is None else min_vol
    max_vol = MAX_VOL if max_vol is None else max_vol
    max_n = MAX_POSITIONS if max_n is None else max_n
    class_ok = _class_ok if class_ok is None else class_ok
    out = []
    for c, f in (fund or {}).items():
        if c in held:
            continue
        try:
            rate = float(f.get("rate") or 0.0)
            vol = float(f.get("vol") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        apr = rate * H
        a = abs(apr)
        if a < apr_lo or a >= apr_hi:
            continue
        if vol < min_vol or vol >= max_vol:
            continue
        if (t0 - (stable_since or {}).get(c, t0)) < stable_h * 3600.0:
            continue
        if not class_ok(c):
            continue
        side = "short" if apr > 0 else "long"
        if basis_veto(side, (prem_map or {}).get(c)):
            continue
        out.append((c, f, apr))
    out.sort(key=lambda x: -abs(x[2]))
    return out[:max_n]


def scan_census(fund, held, stable_since, t0, prem_map=None, apr_lo=None,
                apr_hi=None, min_vol=None, max_vol=None, stable_h=STABLE_H,
                class_ok=None):
    """WHY DID NOTHING OPEN? Buckets are mutually exclusive, mirror the gate
    order exactly, and sum to `scanned`. `above_band` is the carry cohort's
    supply, counted so the tiling is visible from the row itself; `deep` is
    the Farmer's tier. Pure observability."""
    apr_lo = APR_LO_EFF if apr_lo is None else apr_lo
    apr_hi = APR_HI if apr_hi is None else apr_hi
    min_vol = MIN_VOL if min_vol is None else min_vol
    max_vol = MAX_VOL if max_vol is None else max_vol
    class_ok = _class_ok if class_ok is None else class_ok
    out = {"scanned": len(fund or {}), "held": 0, "below_band": 0,
           "above_band": 0, "thin": 0, "deep": 0, "waiting": 0,
           "noncrypto": 0, "adverse_basis": 0, "eligible": 0}
    for c, f in (fund or {}).items():
        if c in held:
            out["held"] += 1
            continue
        try:
            rate = float(f.get("rate") or 0.0)
            vol = float(f.get("vol") or 0.0)
        except (TypeError, ValueError, AttributeError):
            out["below_band"] += 1
            continue
        apr = rate * H
        a = abs(apr)
        if a < apr_lo:
            out["below_band"] += 1
        elif a >= apr_hi:
            out["above_band"] += 1
        elif vol < min_vol:
            out["thin"] += 1
        elif vol >= max_vol:
            out["deep"] += 1
        elif (t0 - (stable_since or {}).get(c, t0)) < stable_h * 3600.0:
            out["waiting"] += 1
        elif not class_ok(c):
            out["noncrypto"] += 1
        elif basis_veto("short" if apr > 0 else "long",
                        (prem_map or {}).get(c)):
            out["adverse_basis"] += 1
        else:
            out["eligible"] += 1
    return out


def carry_exit(pos, apr, t0):
    """Rules 1/2/3 as the exit rule: a paying position closes only after
    FLIP_GRACE_H of persistence (basis noise is not a signal — the MEASURED
    difference between this book working and not), a decayed position closes
    only after payback with margin, max-hold recycles capital, the bleed stop
    bounds a position whose costs outrun income. Returns the exit reason or
    None. Mutates only the flip clock."""
    paying_now = (pos["side"] == "short" and apr < 0) or \
                 (pos["side"] == "long" and apr > 0)
    if paying_now:
        pos.setdefault("paying_since", t0)
    else:
        pos.pop("paying_since", None)
    close_fee = (SLIP_COST + HEDGE_COST) * pos["notional"]
    net_if_closed = pos["accrued"] - (pos["fees"] + close_fee)
    held_h = (t0 - pos["opened_ts"]) / 3600.0
    if paying_now and (t0 - pos["paying_since"]) / 3600.0 >= FLIP_GRACE_H:
        return "liability_flip"
    if abs(apr) < EXIT_APR and net_if_closed >= PAYBACK_MARGIN:
        return "decay_paid"
    if held_h >= MAX_HOLD_H:
        return "max_hold"
    if net_if_closed <= -BLEED_FRAC * pos["notional"]:
        return "bleed_stop"
    return None


def position_pnl(pos):
    """MTM P&L of one position: accrued funding − fees. NO price term —
    rule 1 is structural: this function cannot see a mark, so no future edit
    can quietly turn the book directional without changing its signature."""
    return pos["accrued"] - pos["fees"]


def carry_ledger(positions):
    """The cost-of-carry decomposition, published every loop: per-position
    accrued income, booked costs, the basis at entry and payback progress —
    Hull's own accounting identity, visible from the row."""
    out = {}
    for c, p in positions.items():
        rt = RT_COST_FRAC * p["notional"]
        out[c] = {"side": p["side"],
                  "accrued": round(p.get("accrued") or 0.0, 4),
                  "fees": round(p.get("fees") or 0.0, 4),
                  "entry_prem_bps": p.get("entry_prem_bps"),
                  "payback_pct": round(
                      100.0 * (p.get("accrued") or 0.0) / rt, 1)}
    return out


def build_state(positions, stable_since, stable_sign, last_ts, now=None):
    """The persistence blob — ONE builder so the selftest exercises the same
    payload main() saves. The stability clock rides the `hot_since` key so
    funding_basis.restore_hot_since (the (iu)-hardened restorer) owns the
    restore rule; the sign map rides beside it and is dropped whenever the
    clock is."""
    return {"positions": positions, "hot_since": stable_since,
            "stable_sign": stable_sign, "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, open_pnl, realized):
    """The published `extra` — ONE builder ((hj)). `caps` publishes the FULL
    band, floor AND ceiling, apr AND volume — (gl)/I20: an unpublished
    ceiling is how a band book gets counted as a rival for supply its own
    band excludes; `audit_book_overlap.living_gates` reads exactly these
    keys."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "funding_basis_periods_per_year": H,
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {"enter_apr": round(APR_LO_EFF, 4), "apr_hi": APR_HI,
                 "exit_apr": EXIT_APR, "min_vol": MIN_VOL, "max_vol": MAX_VOL,
                 "stable_h": STABLE_H, "flip_grace_h": FLIP_GRACE_H,
                 "payback_max_h": PAYBACK_MAX_H,
                 "basis_veto_bps": BASIS_VETO_BPS,
                 "max_positions": MAX_POSITIONS, "clip_usd": CLIP_USD,
                 "crypto_only": not ALLOW_NONCRYPTO},
        "scan": census,
        "carry_ledger": carry_ledger(positions),
    }


# --------------------------- venue reads -------------------------------------
def fetch_premiums():
    """{coin: prem_bps} from the venue's own orderBookDetails — mark vs
    index, the basis rule 4 gates on. The scout publishes only the top-8
    outliers, so a basis book fetches the cross-section itself (one keyless
    call; raw urllib + browser UA because the SDK omits index_price and its
    default UA trips the venue's WAF). {} on ANY failure — the veto then
    admits (fail-OPEN, declared in basis_veto)."""
    try:
        req = urllib.request.Request(
            LIGHTER_API + "/api/v1/orderBookDetails",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
        out = {}
        for b in d.get("order_book_details") or []:
            try:
                mark = float(b.get("mark_price") or 0.0)
                idx = float(b.get("index_price") or 0.0)
                if mark > 0 and idx > 0:
                    sym = str(b.get("symbol"))
                    # [(mh)] key by FLEET symbol: funding_map folds per fleet
                    # symbol (1000BONK -> kBONK), and a raw-symbol key left
                    # the basis veto silently dark on every 1000-market.
                    try:
                        from venues.symbol_map import from_lighter
                        sym = from_lighter(sym)[0]
                    except Exception:  # noqa: BLE001
                        pass
                    out[sym] = (mark / idx - 1.0) * 1e4
            except (TypeError, ValueError):
                continue
        return out
    except Exception:  # noqa: BLE001
        return {}


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_rate, pnl, spread_exit=None):
    """Ledger one close: `<side>-basis_<exit>` + the (gr) funding-form
    telemetry. No prices: delta-neutral modelled — a price on its rows would
    be fabricated data (the cohort rule). The (mg) Harris spread fields ARE
    recorded: the quoted spread is what the 30bps RT friction model asserts
    about, so every close carries the number that can falsify it."""
    t = time.time()
    held_h = (t - pos["opened_ts"]) / 3600.0
    try:
        # the funding-form (gr) fields are a LITERAL dict at this call site,
        # deliberately: test_exit_telemetry reads the keys by AST.
        store.publish_paper_trade(
            bot_id, trade_id=f"{key}:{pos['opened_ts']:.0f}",
            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=pos["coin"],
            opened_at=datetime.fromtimestamp(
                pos["opened_ts"], timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=f"{pos['side']}-basis_" + reason,
            venue="lighter", shadow=True,
            extra={"entry_apr": pos.get("entry_apr"),
                   "exit_apr": exit_rate,
                   "accrued": round(pos.get("accrued") or 0.0, 4),
                   "fees": round(pos.get("fees") or 0.0, 4),
                   "notional": pos.get("notional"),
                   "entry_prem_bps": pos.get("entry_prem_bps"),
                   "spread_bps_entry": pos.get("spread_bps_entry"),
                   "spread_bps_exit": spread_exit,
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, coin, side, notional, t0, apr, prem_bps=None):
    """Open one modelled delta-neutral position; both modelled legs' open
    half booked up front."""
    positions[coin] = {"coin": coin, "side": side, "notional": notional,
                      "opened_ts": t0, "accrued": 0.0,
                      "fees": (SLIP_COST + HEDGE_COST) * notional,
                      "entry_apr": apr,
                      "entry_prem_bps": (round(prem_bps, 1)
                                         if prem_bps is not None else None)}
    return positions[coin]


def main():
    p = argparse.ArgumentParser(
        description="🧮 The Professor — the cost-of-carry book")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: book-hull (🧮 The Professor) runs "
            "VENUE=lighter_shadow ONLY. It is a $1,000 shadow book whose "
            "delta-neutral accounting models an off-venue hedge leg that "
            "does not exist; go-live is a separate operator act behind the "
            "standard gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # book-hull-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}      # coin -> pos dict
    stable_since = {}   # coin -> ts (sign, in-band) became continuously true
    stable_sign = {}    # coin -> +1/-1, the sign the clock above certifies
    _saved = None
    try:
        # the CHECKED read ((jd)): a blip at boot must not seed empty
        # positions over the durable record.
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved is not None:
            stable_since, _why = funding_basis.restore_hot_since(
                _saved, time.time())
            raw_sign = _saved.get("stable_sign")
            if isinstance(raw_sign, dict):
                for c in list(stable_since):
                    s = raw_sign.get(c)
                    if s in (1, -1, 1.0, -1.0):
                        stable_sign[c] = int(s)
                    else:
                        # a clock without its certified sign is not a clock
                        stable_since.pop(c, None)
            else:
                stable_since = {}
            print(f"[{now_iso()}] restored {len(positions)} position(s) | "
                  f"stability clock: {_why}")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🧮 The Professor start | venue lighter | "
          f"band [{APR_LO_EFF:.1%}, {APR_HI:.0%}) TRUE x "
          f"[${MIN_VOL/1e6:.0f}M, ${MAX_VOL/1e6:.0f}M) | "
          f"stable>={STABLE_H:.0f}h grace {FLIP_GRACE_H:.0f}h | "
          f"${CLIP_USD:.0f}x{MAX_POSITIONS} | "
          f"realized so far ${realized:+.2f} ({n_closed} closed)")

    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except (TypeError, ValueError):
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()

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
                    "caps": {"apr_lo": round(APR_LO_EFF, 4),
                             "apr_hi": APR_HI, "min_vol": MIN_VOL,
                             "max_vol": MAX_VOL,
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
            print(f"[{now_iso()}] funding fetch failed ({e!r}); retrying")
            fund = None

        if fund:
            prem_map = fetch_premiums()
            dt_h = (t0 - last_ts) / 3600.0
            last_ts = t0

            # ---- manage every open position -----------------------------
            for key in list(positions):
                pos = positions[key]
                f = fund.get(pos["coin"])
                if f is None:
                    first = pos.setdefault("missing_since", t0)
                    if (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                        continue
                    pos["fees"] += (SLIP_COST + HEDGE_COST) * pos["notional"]
                    pnl = position_pnl(pos)
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    _close(bot_id, key, pos, "delisted", None, pnl)
                    print(f"[{now_iso()}] CLOSE {key} [delisted] "
                          f"pnl {pnl:+.2f} | banked {realized:+.2f}")
                    del positions[key]
                    continue
                pos.pop("missing_since", None)
                rate = float(f.get("rate") or 0.0)
                apr = rate * H
                sign = 1.0 if pos["side"] == "long" else -1.0
                pos["accrued"] += ((-sign) * funding_basis.to_hourly(
                    rate, "lighter") * dt_h * pos["notional"])

                reason = carry_exit(pos, apr, t0)
                if reason is None:
                    continue
                pos["fees"] += (SLIP_COST + HEDGE_COST) * pos["notional"]
                pnl = position_pnl(pos)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                held_h = (t0 - pos["opened_ts"]) / 3600.0
                _close(bot_id, key, pos, reason, rate, pnl,
                       spread_exit=live_spread_bps(ctx, pos["coin"]))
                print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                      f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                      f"banked {realized:+.2f}")
                del positions[key]

            # ---- the stability clock (rule 2/3's persistence) -----------
            for c, f in fund.items():
                try:
                    apr = float(f.get("rate") or 0.0) * H
                except (TypeError, ValueError, AttributeError):
                    apr = 0.0
                s = 1 if apr > 0 else -1
                if in_band(apr) and stable_sign.get(c) == s:
                    pass                       # streak continues
                elif in_band(apr):
                    stable_since[c] = t0       # new streak, this sign
                    stable_sign[c] = s
                else:
                    stable_since.pop(c, None)
                    stable_sign.pop(c, None)

            held = set(positions)
            census = scan_census(fund, held, stable_since, t0,
                                 prem_map=prem_map)

            # ---- entries: take the receiving side of stable carry -------
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                for c, f, apr in candidates(fund, held, stable_since, t0,
                                            prem_map=prem_map, max_n=free):
                    side = "short" if apr > 0 else "long"
                    _open_position(positions, c, side, CLIP_USD, t0, apr,
                                   prem_bps=prem_map.get(c))
                    positions[c]["spread_bps_entry"] = live_spread_bps(ctx, c)
                    held.add(c)
                    print(f"[{now_iso()}] OPEN {c} {side} ${CLIP_USD:.0f} | "
                          f"{apr:+.1%} TRUE | payback "
                          f"{payback_hours(apr):.0f}h | prem "
                          f"{prem_map.get(c) if prem_map.get(c) is not None else '?'}bps")

            # ---- publish -------------------------------------------------
            open_pnl = sum(position_pnl(p) for p in positions.values())
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
                # MTM equity series from DAY ONE ((hq)/I9).
                store.snapshot_equity(bot_id, equity, len(positions), realized)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(bot_id, build_state(
                    positions, stable_since, stable_sign, last_ts, t0))
            except Exception:  # noqa: BLE001
                pass

            held_s = ", ".join(sorted(positions)) or "none"
            print(f"[{now_iso()}] scan ok | {len(fund)} books | open: {held_s}"
                  f" | open_pnl {open_pnl:+.2f} | banked {realized:+.2f} | "
                  f"below {census['below_band']}, above {census['above_band']}"
                  f", thin {census['thin']}, deep {census['deep']}, waiting "
                  f"{census['waiting']}, adverse {census['adverse_basis']}, "
                  f"eligible {census['eligible']}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Covers the band arithmetic (both edges half-open where the
    tiling demands it), the payback floor, the basis veto's direction and
    fail-open, the entry gates + census mirror, the measured exit tolerances,
    the no-price-term invariant, the tag round-trip, the payload builders and
    the persistence blob. Mutation-verified at authoring time: dropping the
    *H conversion, the band ceiling, the sign-reset on the stability clock,
    or the grace on liability_flip each redden this."""
    t0 = 1_000_000.0
    old = {c: t0 - 25 * 3600 for c in ("A", "B", "C", "D", "E", "G", "N")}

    # 1) the band: floor is payback-derived, ceiling hands off to carry
    assert abs(APR_LO_EFF - RT_COST_FRAC * HOURS_PER_YEAR / PAYBACK_MAX_H) \
        < 1e-12
    assert 0.075 < APR_LO_EFF < 0.081, APR_LO_EFF
    assert in_band(0.105) and in_band(-0.105)
    assert not in_band(0.05), "below the cost band must not trade"
    assert not in_band(0.20), \
        "the ceiling is HALF-OPEN: 20% TRUE is the carry cohort's supply (I20)"
    assert not in_band(0.208), "above-band is the carry cohort's, both signs"
    assert in_band(APR_LO_EFF), "the floor is closed (payback exactly met)"
    assert payback_hours(APR_LO_EFF) <= PAYBACK_MAX_H + 1e-6
    assert payback_hours(0.05) > PAYBACK_MAX_H

    # 2) the basis veto: direction, magnitude, fail-open
    assert basis_veto("short", -15.0) is True, \
        "shorting 15bps BELOW fair value pays convergence away"
    assert basis_veto("short", +15.0) is False
    assert basis_veto("long", +15.0) is True
    assert basis_veto("long", -15.0) is False
    assert basis_veto("short", -5.0) is False, "inside the veto band"
    assert basis_veto("short", None) is False, \
        "a dark basis feed must ADMIT — the measured baseline is the floor"

    # 3) entry gates + ordering. rate 1e-4 -> 10.95% TRUE (in band);
    #    2e-4 -> 21.9% (above band); 5e-5 -> 5.5% (below); vols tile.
    fund = {"A": {"rate": 1e-4, "vol": 5e6},        # eligible
            "B": {"rate": -1.2e-4, "vol": 3e6},     # eligible, hotter
            "C": {"rate": 1e-4, "vol": 1e6},        # thin (< $2M)
            "D": {"rate": 1e-4, "vol": 20e6},       # deep (the Farmer's tier)
            "E": {"rate": 2e-4, "vol": 5e6},        # above band (carry's)
            "G": {"rate": 5e-5, "vol": 5e6},        # below band
            "N": {"rate": 1e-4, "vol": 5e6}}        # noncrypto (screened)
    cands = candidates(fund, set(), old, t0, class_ok=lambda c: c != "N")
    assert [c for c, _f, _a in cands] == ["B", "A"], cands
    assert candidates(fund, {"A", "B"}, old, t0,
                      class_ok=lambda c: True) == [x for x in candidates(
                          fund, set(), old, t0, class_ok=lambda c: True)
                          if x[0] not in ("A", "B")]
    # the 8x trap: a band in QUOTED units admits everything
    assert candidates(fund, set(), old, t0, apr_lo=APR_LO_EFF / H,
                      apr_hi=APR_HI, class_ok=lambda c: True), \
        "gate must compare TRUE apr, not the quoted per-period rate"
    # no persisted streak -> excluded
    assert candidates(fund, set(), {}, t0, class_ok=lambda c: True) == []
    # the adverse-basis veto refuses at entry (A would be SHORT; prem -15)
    cands_v = candidates(fund, set(), old, t0, prem_map={"A": -15.0},
                         class_ok=lambda c: c != "N")
    assert [c for c, _f, _a in cands_v] == ["B"], cands_v

    # 4) census mirrors the gate order and sums to scanned
    cen = scan_census(fund, set(), old, t0, prem_map={"A": -15.0},
                      class_ok=lambda c: c != "N")
    assert cen == {"scanned": 7, "held": 0, "below_band": 1, "above_band": 1,
                   "thin": 1, "deep": 1, "waiting": 0, "noncrypto": 1,
                   "adverse_basis": 1, "eligible": 1}, cen
    assert sum(v for k, v in cen.items() if k != "scanned") == cen["scanned"]

    # 5) exit tolerances — the MEASURED cells (grace 24h, not 1h)
    def _pos(side="short", accrued=0.0, fees=0.0, opened=t0 - 3600):
        return {"coin": "A", "side": side, "notional": 80.0,
                "opened_ts": opened, "accrued": accrued, "fees": fees}
    p1 = _pos(side="short")
    assert carry_exit(p1, -0.10, t0) is None, \
        "one adverse hour closed the position — that churn measured −$16.84"
    assert carry_exit(p1, -0.10, t0 + 6 * 3600) is None, \
        "six adverse hours are still basis noise at the measured tolerance"
    assert carry_exit(p1, -0.10, t0 + FLIP_GRACE_H * 3600 + 1) == \
        "liability_flip"
    p2 = _pos(side="short")
    carry_exit(p2, -0.10, t0)
    assert carry_exit(p2, +0.10, t0 + 1800) is None \
        and "paying_since" not in p2, "resumed receiving must clear the clock"
    # decay closes only after payback with margin
    p3 = _pos(accrued=0.05)
    assert carry_exit(p3, 0.001, t0) is None
    p4 = _pos(accrued=0.32)     # >= fees(0.12) + close(0.12) + margin(0.07)
    assert carry_exit(p4, 0.001, t0) == "decay_paid"
    assert carry_exit(_pos(accrued=1.0, opened=t0 - MAX_HOLD_H * 3600 - 1),
                      0.10, t0) == "max_hold"
    assert carry_exit(_pos(accrued=-5.0), 0.10, t0) == "bleed_stop"

    # 6) rule 1 is structural: P&L has no price input at all
    pc = _pos(accrued=2.0, fees=0.5)
    assert abs(position_pnl(pc) - 1.5) < 1e-9
    import inspect
    assert "mark" not in inspect.signature(position_pnl).parameters, \
        "a mark parameter on position_pnl would let price P&L in"

    # 7) tag round-trip through the REAL parser
    for side in ("long", "short"):
        for exit_r in ("decay_paid", "liability_flip", "max_hold",
                       "bleed_stop", "delisted"):
            tag, ex = store.split_reason(f"{side}-basis_{exit_r}")
            assert tag == f"{side}-basis", (tag, side, exit_r)
            assert ex == exit_r, (ex, exit_r)

    # 8) publisher-built payload — the band is published WHOLE (I20/(gl))
    positions = {}
    _open_position(positions, "A", "short", 80.0, t0, 0.105, prem_bps=3.2)
    assert positions["A"]["fees"] == (SLIP_COST + HEDGE_COST) * 80.0
    assert positions["A"]["entry_prem_bps"] == 3.2
    extra = build_extra(cen, positions, 1.23, 4.56)
    assert extra["caps"]["min_vol"] == MIN_VOL
    assert extra["caps"]["max_vol"] == MAX_VOL, \
        "an unpublished ceiling made Garrett read as a rival once — never again"
    assert extra["caps"]["apr_hi"] == APR_HI
    assert extra["caps"]["enter_apr"] == round(APR_LO_EFF, 4)
    assert extra["held"] == {"A": "S"}, extra["held"]
    assert extra["carry_ledger"]["A"]["payback_pct"] == 0.0
    st = store.json_safe(extra)
    assert st["caps"]["max_positions"] == MAX_POSITIONS

    # 9) the persistence blob: clock + sign restore, sign-loss drops the clock
    blob = build_state(positions, {"A": t0 - 60}, {"A": 1}, t0, now=t0)
    assert "saved_ts" in blob
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 60)
    assert restored == {"A": t0 - 60}, restored
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 99999)
    assert restored == {}, "an outage-sized gap must not resurrect a streak"

    # 10) basis honesty
    assert abs(funding_basis.to_apr(9.6e-05, "lighter") - 0.10512) < 1e-6
    assert 0 < EXIT_APR < APR_LO_EFF < APR_HI < 1.0
    assert H == 3 * 365
    assert abs(RT_COST_FRAC - 0.003) < 1e-12
    assert MIN_VOL < MAX_VOL, "the volume band must be a real band"

    # 11) a dark class screen fails OPEN
    global fleet_bus
    _orig = fleet_bus
    fleet_bus = None
    try:
        assert _class_ok("ANYTHING") is True
    finally:
        fleet_bus = _orig


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

    print("lighter_book_hull_bot self-tests passed "
          "(band, payback floor, basis veto, gates, census, measured exit "
          "tolerances, tags, payload, persistence).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
