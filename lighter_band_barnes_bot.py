#!/usr/bin/env python3
"""
lighter_band_barnes_bot.py — 🎸 Barnesy (band-barnes), the FUNDING SUPER-BOOK.

WHAT THIS IS (2026-08-04, operator: "yes build the super bot" — OPERATOR_QUEUE
§1 option S2, FORWARD_STEPS_2026-08-01 item 4 "more funding surface")
  One $1,000 shadow book running the fleet's three PROVEN funding utilities as
  SLEEVES under one capital roof, named for Jimmy Barnes per the
  Australian-musician cohort rule (band-<surname>-lshadow): a book that earns
  funding WAGES, not price bets — Working Class Man.

  The measured case (1-Aug, allocation organ): every measured claim in the
  fleet lives in the FUNDING class (3 books, +$72.89, n=297); DIRECTIONAL has
  zero claims in 867 closes. The growth move is more funding surface.

THE THREE SLEEVES — each a CONSERVATIVE re-expression of a parent book's
validated gates, every close tagged `<side>-<sleeve>_<exit>` so the brain
grades sleeves independently. (The task sheet wrote the tag `<sleeve>-…`;
`bot_pnl_store.split_reason` — the ONE parser — only tags reasons that START
with a direction, so sleeve-first would have silently untagged every close,
the exact 14-Jul class. Direction first, sleeve second.)

  carry   — 🌾 funding_carry_bot's harvest: enter at >=20% TRUE apr (the
            21-Jul Lighter-tape gate sweep — the ONLY gate that beat shipped
            on the full window AND both halves; (it) measured it binding),
            6h persistence (persistent funding pays carries, spikes pay fees),
            $2M vol floor, delta-neutral MODELLED (hedge cost charged, no
            price P&L), and the (gq) exit discipline: carry earns +$71.42 on
            `*_decay_paid` and loses on sided flips — so decay closes only
            AFTER fee payback, flips get 1h grace. Max 4 x $80.
  extreme — 💸 the Farmer's shape: the venue's MOST EXTREME TRUE-apr books,
            funding-RECEIVING side taken DIRECTIONALLY (price risk is real and
            is stop-guarded at 10%, the Farmer's own bar), $10M vol floor (the
            Farmer's), same 20% TRUE entry bar (the level the 150d gate sweep
            validated — the Farmer's live 5% gate has no backtest behind it),
            persistence-aware. Max 4 x $40.
  xsect   — ⚖️ Counterweight's cross-sectional L/S at the VALIDATED config:
            K=5 per side (the backtested plateau CENTRE — deliberately NOT the
            un-backtested K=8 the shadow book ran), LONG the K most-NEGATIVE
            funders / SHORT the K most-POSITIVE, dollar-neutral $33 legs,
            24h rebalance, ranked over the scout universe with a venue-direct
            fallback (a dark scout degrades to this bot's own funding map,
            never to "trade nothing"). No per-leg stop, mirroring the parent:
            the validated book has none (replay fidelity); risk is bounded by
            balance (long$ == short$), clip size and the rebalance turnover.

HONEST ABOUT THE EVIDENCE. The sleeves inherit their parents' Lighter-tape
evidence; the COMBINATION under one roof is a NEW policy with a fresh 30-day
clock ((hm)) — none of the parents' ledger evidence carries over, and this
header does not claim it does. What the shadow clock measures is whether the
combination earns its own go-live grade (>=30 closes, mean>0, t>=2, both
halves, maxDD<15%, over >=30d), gradeable ~mid-Sep at the earliest.

CONFIG IS FROZEN FROM BIRTH — 30 DAYS. (hm): a book whose bars move accrues
ZERO gradeable closes (the Ticket Taker's 137 shadow closes produced none).
So: no tuner lane until BARNES_FREEZE_UNTIL (default 2026-09-04T00:00:00Z).
`apply_tuning()` is WIRED (registry levers `barnes.enter_apr` /
`barnes.max_positions` / `barnes.k`, lane `lighter-books`, evidence-board
author, consumed every loop) and INERT while the freeze holds — reach exists
without violating the freeze, so on day 31 the growth rail needs no deploy.

MODELLED, DECLARED (the honest-but-favourable ledger, stated not buried):
  * carry legs charge SLIP_COST + HEDGE_COST per side (15bps round trip per
    leg-pair) — the parent MEASURES perp slippage against the live book; this
    book models it flat and conservative (Lighter perp fee is zero, measured).
  * extreme/xsect legs fill AT MARK and charge SLIP_COST per side (5bps —
    ~6x the 0.86bps the carry shadow evidence models).
  * funding accrues at the venue's own hourly settlement via
    funding_basis.to_hourly — the 8x class cannot recur here because every
    bar in this file is denominated in TRUE apr and converted by the one
    basis authority. No HL-legacy thresholds exist in this file.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow is the only
accepted mode (loud SystemExit otherwise — a foreign-venue arm going quiet
must be a decision you see). This bot never constructs an order path.

Usage:
    VENUE=lighter_shadow python lighter_band_barnes_bot.py          # daemon
    VENUE=lighter_shadow python lighter_band_barnes_bot.py --once   # smoke
    python lighter_band_barnes_bot.py --selftest                    # offline
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import venue_context

# Growth rail + scout bus. Guarded like every optional organ: a dark import
# leaves the operator's env defaults and the venue-direct universe in force,
# never a crash inside a trading loop. Both COPYs land in Dockerfile.bandbarnes
# in this same commit (a guarded import with a missing COPY is the born-dark
# failure this fleet has shipped three times).
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "band-barnes"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300              # funding is hourly; 5-min polling is plenty

# TRUE-apr basis, one owner. H converts a quoted Lighter rate to TRUE apr;
# every threshold below is ALREADY a TRUE-apr fraction — there is no legacy
# scale in this file and there must never be one.
H = funding_basis.periods_per_year("lighter")

# ---- the birth freeze -------------------------------------------------------
# (hm): the 30-day go-live clock restarts on every policy change, so a book
# whose bars move accrues zero gradeable closes. The config below is FROZEN
# until this stamp; apply_tuning() refuses to move anything before it. The
# operator can extend/lift by env — that is an operator act, not a rail act.
FREEZE_UNTIL_ISO = os.environ.get(
    "BARNES_FREEZE_UNTIL", "2026-09-04T00:00:00+00:00")


def _freeze_until_ts():
    try:
        return datetime.fromisoformat(
            FREEZE_UNTIL_ISO.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        # an unparseable stamp freezes FOREVER rather than unfreezing — the
        # fail-closed direction: a typo must not hand the rail a frozen book.
        return float("inf")


def freeze_active(now=None):
    return float(now if now is not None else time.time()) < _freeze_until_ts()


# ---- instrument class screen, harvest sleeves (2026-08-13 (lv)) -------------
# The `(lj,lk,ll)` sweep class-screened 🌾 the carry PARENT and 🎯 the sniper
# and did not touch this file — so the funding SUPER-BOOK, built expressly to
# consolidate those parents' validated gates, kept taking the instrument class
# they screen out. Measured over the scout's own 8,610-snapshot tape: 68.2% of
# this sleeve's OFFERED supply is non-crypto, and all 8 of its real closes were
# WTI x4 / SKHYNIXUSD x2 / SPCX x2 — 0% win, zero crypto. `(ki)` had already
# found this exact leak in this exact book and fixed only the xsect sleeve;
# fixing instances is not closing the class (I14, `(im)`).
# Mirrors the parent's contract EXACTLY: ENTRY-ONLY (a held position exits by
# its normal rules), fail-OPEN on a missing fleet_bus (an import regression
# must not shrink the universe — the dark-scout fallback inside `is_crypto` is
# the load-bearing degrade), reversible without a deploy.
ALLOW_NONCRYPTO = os.environ.get("BARNES_ALLOW_NONCRYPTO", "").strip().lower() \
    in ("1", "on", "true", "yes")


def _class_ok(coin):
    """May `coin` ENTER a harvest sleeve? Crypto perps only — see above."""
    if ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.is_crypto(coin))
    except Exception:      # noqa: BLE001 — a class lookup must never stop a scan
        return True


# ---- shared harvest gates (carry + extreme sleeves) -------------------------
# 20% TRUE apr — the 21-Jul gate sweep on Lighter's OWN 150d tape: the only
# bar that beat shipped on the full window AND both halves (+$55.93). (it)
# measured it binding on the parent. TRUE fraction, not the parent's
# HL-legacy 1.60 denomination.
ENTER_APR = float(os.environ.get("BARNES_ENTER_APR", "0.20"))
# decay bar mirrors both parents' 0.15-legacy exit == 0.01875 TRUE.
EXIT_APR = float(os.environ.get("BARNES_EXIT_APR", "0.01875"))
PERSIST_H = 6.0                 # hot >= this long before entry (parent's bar)
FLIP_GRACE_H = 1.0              # adverse funding this long before a flip-close
MAX_HOLD_H = 14 * 24            # recycle capital (parent's bar)
DELIST_GIVEUP_H = 24.0          # coin absent from the map this long -> close

# ---- carry sleeve (🌾 parent: funding_carry_bot) ----------------------------
CARRY_NOTIONAL = 80.0
CARRY_MIN_VOL = 2e6             # parent's 24h $ turnover floor
# decay-close only when net after ALL fees clears this — scaled from the
# parent's $0.10-on-$300 to this sleeve's $80 clip.
CARRY_PAYBACK_MARGIN = 0.03
CARRY_BLEED_FRAC = 0.02         # close if net <= -2% of notional (parent's)

# ---- extreme sleeve (💸 parent: lighter_funding_bot) ------------------------
EXTREME_NOTIONAL = 40.0
EXTREME_MIN_VOL = 10e6          # the Farmer's liquidity floor
# [2026-08-13 (ly)] RETIRED — the I17 keep-or-retire call, made on measurement.
# Never opened a position in its life; every reachable floor is undecidable
# (903/181/129 days to 30 closes at $3M/$2M/$1M) and the cheap ones take the
# carry sleeve's whole supply, because both harvest sleeves bid for the SAME
# 3-4 crypto names at the 20% TRUE bar. Entry-only, so a restored position
# still exits by its normal rules. See the entry block for the full table.
EXTREME_RETIRED = os.environ.get(
    "BARNES_EXTREME_RETIRED_OVERRIDE", "").strip().lower() not in ("run", "1", "on")
# the Farmer's NON-NEGOTIABLE control for a directional funding book: a hard
# price stop, 10% — the parent's own bar, well inside the 15% go-live
# drawdown gate (test_stop_vs_gate reads this literal).
HARD_STOP = float(os.environ.get("BARNES_HARD_STOP", "0.10"))

# ---- xsect sleeve (⚖️ parent: lighter_funding_spread_bot) -------------------
K = int(os.environ.get("BARNES_K", "5"))       # the VALIDATED plateau centre
XSECT_CLIP = 33.0               # $/leg -> 2*K*33 = $330 gross, ~zero net
XSECT_REBALANCE_H = 24.0        # parent's validated cadence
XSECT_MIN_VOL_M = float(os.environ.get("BARNES_XSECT_MIN_VOL_M", "1.0"))
# [2026-08-06 (kl)] 60 -> 30, AND the core below. `(ki)` NAMED this defect in
# its own comment — "unlike its parent, which starts from a VALIDATED 30-name
# crypto core and only tops up, this sleeve had NO core at all" — and fixed
# only the crypto filter. The width was the other half: 30 is what BOTH of the
# parent's validations cleared (the HL lab and the 31-Jul (ia) Lighter re-run,
# +13.7% / maxDD 9.6%), and `(jg)` reverted the parent 60 -> 30 on that
# widening's OWN pre-registered criterion EIGHT HOURS before this book was
# born — measured in-era t=-0.44 and falling from a 0.65 baseline, mean
# -0.361%/trade, -$16.01 MTM, fleet-worst. The child shipped the reverted half.
XSECT_UNIVERSE_N = int(os.environ.get("BARNES_XSECT_UNIVERSE_N", "30"))
#: The parent's VALIDATED cross-section, seeded from its `COINS` default. This
#: sleeve ranked the venue's top-N by volume with no core, so its September
#: grade would have been a grade of a cross-section no validation covers.
#: Core names are NEVER dropped (the parent's `resolve_universe` contract);
#: only the scout's top-up is screened. `tests/autonomy/test_barnes_xsect_core`
#: pins this resolution EQUAL to the parent's function on the same inputs —
#: the two implementations cannot be shared (the parent is not in this image)
#: so they are held honest by an executable equality check instead.
XSECT_CORE = os.environ.get(
    "BARNES_XSECT_CORE",
    "BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,AAVE,WIF,"
    "JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,PYTH,W").split(",")

# harvest capacity — ONE lever for both harvest sleeves.
MAX_POSITIONS = int(os.environ.get("BARNES_MAX_POSITIONS", "4"))

# ---- modelled friction, declared --------------------------------------------
SLIP_COST = 0.0005              # per side, all sleeves (Lighter fee is zero)
HEDGE_COST = 0.0010             # per side, carry sleeve's off-venue hedge leg

# [auto-revert] the operator's env defaults, snapshotted at import —
# get_lever must be handed THESE, never the current global, or the rail is a
# one-way ratchet (the (fz) defect).
_ENV_DEFAULTS = {"ENTER_APR": ENTER_APR, "MAX_POSITIONS": MAX_POSITIONS,
                 "K": K,
                 # [2026-08-06 (kl)] I18 reach. Present here as well as in
                 # `apply_tuning` deliberately: `_ENV_DEFAULTS[attr]` raises a
                 # KeyError the tuning loop's own `except` swallows, leaving a
                 # lever that LOOKS consumed and never moves — the (gu) trap.
                 "PERSIST_H": PERSIST_H,
                 "CARRY_MIN_VOL": CARRY_MIN_VOL,
                 "EXTREME_MIN_VOL": EXTREME_MIN_VOL,
                 "XSECT_UNIVERSE_N": XSECT_UNIVERSE_N}


def apply_tuning(now=None):
    """Growth-rail levers over the env defaults — WIRED AND BIRTH-FROZEN.

    While `freeze_active(now)` the rail is refused OUTRIGHT (returns {},
    reads nothing): (hm) — a book whose bars move accrues zero gradeable
    closes, and this book's whole first month exists to accrue a gradeable
    sample. After the freeze the standard lighter-books contract applies:
    bounded registry cage, TTL auto-revert to the env defaults above, a dark
    or sick rail leaves the defaults in force. Reach without rule-drift.
    """
    global ENTER_APR, MAX_POSITIONS, K
    global PERSIST_H, CARRY_MIN_VOL, EXTREME_MIN_VOL, XSECT_UNIVERSE_N
    if tuning is None or freeze_active(now):
        return {}
    moved = {}
    for lever, attr in (("barnes.enter_apr", "ENTER_APR"),
                        ("barnes.max_positions", "MAX_POSITIONS"),
                        ("barnes.k", "K"),
                        # [(kl)] the gates the census names as binding
                        ("barnes.persist_h", "PERSIST_H"),
                        ("barnes.carry_min_vol", "CARRY_MIN_VOL"),
                        ("barnes.extreme_min_vol", "EXTREME_MIN_VOL"),
                        ("barnes.xsect_universe_n", "XSECT_UNIVERSE_N")):
        cur = globals()[attr]
        try:
            val = tuning.get_lever(lever, _ENV_DEFAULTS[attr])
        except Exception:  # noqa: BLE001
            continue                      # a sick rail never stops the book
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


def _standby_key(bot_id):
    """The bot_state key a STOOD-DOWN container reports on — (ic): the loser
    must NOT touch the book's row (a second writer of the row is the disease
    the guard exists for, and `heartbeat` would keep a dead incumbent's row
    reading fresh). Suffix, never a rewrite, so a reader holding the book id
    can always find its standby record."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- pure decision layer -----------------------------
def sleeve_tag(sleeve, side):
    """'long'/'short' + sleeve -> the ledger tag prefix. Direction FIRST —
    split_reason only tags direction-prefixed reasons, and the tag part must
    stay underscore-free (hyphens only) so the first-underscore split holds."""
    return f"{side}-{sleeve}"


def harvest_candidates(fund, held, hot_since, t0, enter_apr, min_vol,
                       max_n, persist_h=PERSIST_H, class_ok=None):
    """Eligible (coin, rec, apr) for a harvest sleeve, hottest first.

    The parent's exact gate order: not already held (across BOTH harvest
    sleeves — one coin, one harvest position), |TRUE apr| >= the bar, 24h $
    volume >= the floor, the coin has been hot >= persist_h (persistent
    funding pays carries, spikes pay fees), and — since (lv) — the venue's own
    instrument class is crypto. Pure; decides nothing itself.
    """
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
        if abs(apr) < enter_apr:
            continue
        if vol < min_vol:
            continue
        if (t0 - (hot_since or {}).get(c, t0)) < persist_h * 3600.0:
            continue
        if not class_ok(c):
            continue
        out.append((c, f, apr))
    out.sort(key=lambda x: -abs(x[2]))
    return out[:max_n]


def harvest_census(fund, held, hot_since, t0, enter_apr, min_vol,
                   persist_h=PERSIST_H, class_ok=None):
    """WHY DID NOTHING OPEN? — the (is) census for a harvest bar.
    Buckets are mutually exclusive, mirror the gate order, and sum to
    `scanned`. Pure observability; it decides nothing."""
    class_ok = _class_ok if class_ok is None else class_ok
    out = {"scanned": len(fund or {}), "held": 0, "cold": 0, "thin": 0,
           "waiting": 0, "noncrypto": 0, "eligible": 0}
    for c, f in (fund or {}).items():
        if c in held:
            out["held"] += 1
            continue
        try:
            rate = float(f.get("rate") or 0.0)
            vol = float(f.get("vol") or 0.0)
        except (TypeError, ValueError, AttributeError):
            out["cold"] += 1
            continue
        if abs(rate * H) < enter_apr:
            out["cold"] += 1
        elif vol < min_vol:
            out["thin"] += 1
        elif (t0 - (hot_since or {}).get(c, t0)) < persist_h * 3600.0:
            out["waiting"] += 1
        elif not class_ok(c):
            # [(lk)/(lv)] LAST in the gate order on purpose: this bucket means
            # "hot, liquid, persistent — blocked by class ALONE", i.e. the
            # screen's live bite, which is what lets the payload verify the
            # change and the operator see its cost.
            out["noncrypto"] += 1
        else:
            out["eligible"] += 1
    return out


def resolve_xsect_universe(fund, current_time=None, _scout=None):
    """The coin list the xsect sleeve ranks: the VALIDATED CORE first (order
    preserved), then the scout's most-liquid CRYPTO books until
    `XSECT_UNIVERSE_N` is reached.

    [2026-08-06 (kl)] This sleeve had no core at all — it ranked
    `scout_universe(min_vol_m=1.0, limit=60)` by volume, full stop, so its
    30-day grade would have graded a cross-section neither parent validation
    covers. `(ki)` named that in its own comment and fixed only the crypto
    filter; this is the other half.

    It mirrors `lighter_funding_spread_bot.resolve_universe` term for term,
    and the two CANNOT share code — the parent is not in this image, and
    dragging a whole bot module in to reuse six lines is the born-dark trade
    this fleet keeps losing. "A second copy of a rule is a second rule", so
    they are instead pinned EQUAL by an executable check
    (`test_barnes_xsect_core.py`), which is what keeps the copy honest.

    Contract, inherited from the parent deliberately:
      * a dark or stale scout returns [] from the accessor, so this returns
        the CORE unchanged — widening is an enhancement, never a dependency;
      * `XSECT_UNIVERSE_N <= 0` disables the widening entirely;
      * CORE names are NEVER dropped and NEVER crypto-filtered — they are the
        backtested list, and screening them would silently change what the
        book is. Only the scout's top-up is screened.
    """
    out = list(dict.fromkeys(
        str(c).strip().upper() for c in XSECT_CORE if str(c).strip()))
    width = int(XSECT_UNIVERSE_N or 0)
    if width <= 0 or len(out) >= width:
        return out
    extra = _scout
    if extra is None:
        extra = []
        if fleet_bus is not None:
            try:
                extra = fleet_bus.scout_universe(
                    min_vol_m=XSECT_MIN_VOL_M, limit=width,
                    current_time=current_time) or []
            except Exception:      # noqa: BLE001
                extra = []
    if not extra:
        # venue-direct fallback: never "trade nothing" because an organ is down
        extra = [c for c, f in (fund or {}).items()
                 if float((f or {}).get("vol") or 0.0) >= XSECT_MIN_VOL_M * 1e6]
    if fleet_bus is not None:
        try:
            extra = fleet_bus.crypto_only(extra)
        except Exception:          # noqa: BLE001
            pass                   # fail-open: never stop trading on this
    seen = set(out)
    for c in extra:
        c = str(c or "").strip().upper()
        if not c or c in seen:
            continue
        out.append(c)
        seen.add(c)
        if len(out) >= width:
            break
    return out


def xsect_targets(aprs, k):
    """(longs, shorts) — the Counterweight rule at the validated config:
    LONG the k most-NEGATIVE TRUE-apr books (longs RECEIVE), SHORT the k
    most-POSITIVE (shorts RECEIVE). `aprs` is {sym: TRUE apr fraction}.

    REFUSES a thin cross-section: fewer than 2k rankable books returns
    ([], []) — a rank over a sliver is a weak version of itself, and the
    parent skips its rebalance below MIN_COVERAGE for the same reason.
    Zero/unparseable rates are excluded (a book with no funding signal is
    not a candidate on a funding-rank book).
    """
    rows = []
    for sym, apr in (aprs or {}).items():
        try:
            a = float(apr)
        except (TypeError, ValueError):
            continue
        if a == 0.0:
            continue
        rows.append((a, str(sym)))
    if len(rows) < 2 * k:
        return [], []
    rows.sort()
    longs = [s for _, s in rows[:k]]           # most negative -> long receives
    shorts = [s for _, s in rows[-k:]]         # most positive -> short receives
    return longs, shorts


def carry_exit(pos, apr, t0):
    """The 🌾 exit discipline, verbatim in shape: flip only after grace,
    decay only after fee payback, max-hold expiry, bleed stop. Returns the
    exit reason or None. Mutates only the flip clock (as the parent does)."""
    flipped_now = (pos["side"] == "short" and apr < 0) or \
                  (pos["side"] == "long" and apr > 0)
    if flipped_now:
        pos.setdefault("flipped_since", t0)
    else:
        pos.pop("flipped_since", None)
    close_fee = (SLIP_COST + HEDGE_COST) * pos["notional"]
    net_if_closed = pos["accrued"] - (pos["fees"] + close_fee)
    held_h = (t0 - pos["opened_ts"]) / 3600.0
    if flipped_now and (t0 - pos["flipped_since"]) / 3600.0 >= FLIP_GRACE_H:
        return "flip"
    if abs(apr) < EXIT_APR and net_if_closed >= CARRY_PAYBACK_MARGIN:
        return "decay_paid"
    if held_h >= MAX_HOLD_H:
        return "max_hold"
    if net_if_closed <= -CARRY_BLEED_FRAC * pos["notional"]:
        return "bleed_stop"
    return None


def extreme_exit(pos, apr, mark, t0):
    """The 💸 exit shape: hard price stop FIRST (the non-negotiable control
    on a directional funding book), then flip-with-grace, decay, max-hold."""
    if mark and pos.get("entry_mark"):
        sign = 1.0 if pos["side"] == "long" else -1.0
        price_pnl = sign * (mark / pos["entry_mark"] - 1.0) * pos["notional"]
        if price_pnl <= -HARD_STOP * pos["notional"]:
            return "hard_stop"
    flipped_now = (pos["side"] == "short" and apr < 0) or \
                  (pos["side"] == "long" and apr > 0)
    if flipped_now:
        pos.setdefault("flipped_since", t0)
    else:
        pos.pop("flipped_since", None)
    if flipped_now and (t0 - pos["flipped_since"]) / 3600.0 >= FLIP_GRACE_H:
        return "flip"
    if abs(apr) < EXIT_APR:
        return "decay"
    if (t0 - pos["opened_ts"]) / 3600.0 >= MAX_HOLD_H:
        return "max_hold"
    return None


def position_pnl(pos, mark=None):
    """MTM P&L of one position: accrued funding − fees, plus price P&L for
    the mark-based sleeves (carry is delta-neutral modelled — no price term)."""
    pnl = pos["accrued"] - pos["fees"]
    if pos["sleeve"] != "carry" and pos.get("entry_mark"):
        m = mark if (mark or 0) > 0 else pos.get("last_mark")
        if m and m > 0:
            sign = 1.0 if pos["side"] == "long" else -1.0
            pnl += sign * (m / pos["entry_mark"] - 1.0) * pos["notional"]
    return pnl


def build_state(positions, hot_since, last_ts, xsect_last, now=None):
    """The persistence blob — ONE builder so the selftest exercises the same
    payload main() saves. `saved_ts` is what makes the hot-streak clock
    restorable AT ALL: funding_basis.restore_hot_since fails closed without
    it, and omitting it silently reduces the book to a fresh PERSIST_H wait
    on every boot (the (iu) class)."""
    return {"positions": positions, "hot_since": hot_since,
            "last_ts": last_ts, "xsect_last_rebalance": xsect_last,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, open_pnl, realized, moved, now=None,
                census_ext=None):
    """The published `extra` — ONE builder, so the payload the dashboard,
    board and immune organ read is the payload the selftest asserted on
    (a consumer is tested against a payload its publisher built, (hj))."""
    sleeves = {}
    for s in ("carry", "extreme", "xsect"):
        rows = [p for p in positions.values() if p["sleeve"] == s]
        sleeves[s] = {
            "open": len(rows),
            "cap": (2 * K if s == "xsect" else MAX_POSITIONS),
            "pnl": round(sum(position_pnl(p, p.get("last_mark")) for p in rows), 2),
        }
        # [(lv)] a sleeve that opens nothing must say WHY. `open: 0` alone is
        # byte-identical between "quiet venue" and "structurally unreachable",
        # and this book shipped 8 days of the second while reading as the
        # first. The extreme sleeve carries its own census at its own floor.
        if s == "extreme" and census_ext is not None:
            sleeves[s]["scan"] = census_ext
            sleeves[s]["floor_usd"] = EXTREME_MIN_VOL
            # [(ly)] the retirement is PUBLISHED, not just coded: a reader of
            # this row must not have to infer from `open: 0` whether the
            # sleeve is dead, quiet, or switched off. The census keeps
            # publishing beside it so the call stays falsifiable.
            sleeves[s]["retired"] = EXTREME_RETIRED
    # [2026-08-13 (lz)] WHAT THIS BOOK IS ACTUALLY HOLDING, in 💸 the Farmer's
    # shape ({coin: "S"|"L"}) so ONE reader serves every funding book. This row
    # published 11 open positions and named NONE of them, so nothing in the
    # fleet could ask the question that matters now that three books share a
    # gate: ARE WE ALL HOLDING THE SAME COIN? Per-sleeve counts cannot answer
    # it — concentration is a property of the coin, not of the sleeve.
    # "B" = held on BOTH sides within this book (the xsect sleeve is
    # dollar-neutral, so a name can legitimately appear long and short); a
    # side-collision must not silently overwrite into a false directional read.
    held = {}
    for p in positions.values():
        c = p["coin"]
        s = "S" if p["side"] == "short" else "L"
        held[c] = s if held.get(c, s) == s else "B"
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": held,
        "funding_basis_periods_per_year": H,
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        # the caps this loop ACTUALLY gates on, so the board can see
        # saturation instead of inferring it — and so a frozen book says so.
        # [(lz)] `min_vol` rides here so `audit_book_overlap` can rule this
        # book IN or OUT of a proposed gate's supply. Unpublished, it can do
        # neither, and an undecidable detector is a detector nobody runs.
        "caps": {"enter_apr": ENTER_APR, "max_positions": MAX_POSITIONS,
                 "min_vol": CARRY_MIN_VOL, "max_vol": None,
                 "k": K, "frozen": freeze_active(now),
                 "freeze_until": FREEZE_UNTIL_ISO},
        # the book names its own binding constraint (I8 one layer in)
        "scan": census,
        "sleeves": sleeves,
        "levers_moved": moved or {},
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_rate, pnl, mark=None):
    """Ledger one close: `<side>-<sleeve>_<exit>` + the (gr) funding-form
    telemetry on EVERY row (entry_apr/exit_apr/accrued/fees/held_h), plus
    entry/exit PRICE on the mark-based sleeves — their P&L has a price term,
    so an exit rule on them must be joinable to a price path."""
    t = time.time()
    held_h = (t - pos["opened_ts"]) / 3600.0
    # prices ride the row for the MARK-BASED sleeves (their P&L has a price
    # term, so their exit rules must be joinable to a price path); the carry
    # sleeve is delta-neutral modelled and carries None — a price on it would
    # be fabricated data, not telemetry.
    _entry_px = pos.get("entry_mark") if pos["sleeve"] != "carry" else None
    _exit_px = ((mark if (mark or 0) > 0 else pos.get("last_mark"))
                if pos["sleeve"] != "carry" else None)
    try:
        # the funding-form (gr) fields are a LITERAL dict at this call site,
        # deliberately: test_exit_telemetry reads the keys by AST, and a
        # dict built elsewhere is invisible to the guard that keeps this
        # book's exits falsifiable.
        store.publish_paper_trade(
            bot_id, trade_id=f"{key}:{pos['opened_ts']:.0f}",
            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=pos["coin"],
            opened_at=datetime.fromtimestamp(
                pos["opened_ts"], timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=sleeve_tag(pos["sleeve"], pos["side"]) + "_" + reason,
            venue="lighter", shadow=True,
            entry_price=_entry_px, exit_price=_exit_px,
            extra={"sleeve": pos["sleeve"],
                   "entry_apr": pos.get("entry_apr"),
                   "exit_apr": exit_rate,
                   "accrued": round(pos.get("accrued") or 0.0, 4),
                   "fees": round(pos.get("fees") or 0.0, 4),
                   "notional": pos.get("notional"),
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, sleeve, coin, side, notional, t0, apr,
                   mark=None):
    """Open one modelled position. Carry pays both modelled legs' open half;
    mark sleeves pay slip on the perp side only (zero venue fee, measured)."""
    open_fee = ((SLIP_COST + HEDGE_COST) if sleeve == "carry" else SLIP_COST)
    pos = {"sleeve": sleeve, "coin": coin, "side": side,
           "notional": notional, "opened_ts": t0, "accrued": 0.0,
           "fees": open_fee * notional, "entry_apr": apr}
    if sleeve != "carry":
        if not mark or mark <= 0:
            return None                    # cannot price the leg -> no entry
        pos["entry_mark"] = mark
        pos["last_mark"] = mark
    positions[f"{sleeve}:{coin}"] = pos
    return pos


def main():
    p = argparse.ArgumentParser(description="🎸 Barnesy — funding super-book")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    # SHADOW ONLY, allowlist not blocklist: this book models a hedge leg it
    # does not have and takes directional legs it must never fund — every
    # order-sending mode is refused, loudly, so a flipped env is a decision
    # someone sees rather than a row that just stops moving.
    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: band-barnes (🎸 Barnesy) runs VENUE=lighter_shadow "
            "ONLY. It is a $1,000 shadow consolidation book: the carry sleeve "
            "models an off-venue hedge leg that does not exist, so any funded "
            "mode would run naked; go-live is a separate operator act behind "
            "the standard gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # band-barnes-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}      # "<sleeve>:<coin>" -> pos dict
    hot_since = {}      # coin -> ts |TRUE apr| first held >= ENTER_APR
    xsect_last = 0.0    # last rebalance ts
    _saved = None
    try:
        # the CHECKED read — load_state collapses "no row" and "READ FAILED"
        # into one None, and a blip at boot would seed empty positions over
        # the durable record ((jd)). Refuses loudly rather than poison.
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved is not None:
            hot_since, _why = funding_basis.restore_hot_since(
                _saved, time.time())
            try:
                xsect_last = float(_saved.get("xsect_last_rebalance") or 0.0)
            except (TypeError, ValueError):
                xsect_last = 0.0
            print(f"[{now_iso()}] restored {len(positions)} position(s) | "
                  f"hot-streak clock: {_why}")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🎸 Barnesy start | venue lighter | "
          f"enter>={ENTER_APR:.2%} TRUE exit<{EXIT_APR:.2%} | "
          f"carry ${CARRY_NOTIONAL:.0f}x{MAX_POSITIONS} · "
          f"extreme ${EXTREME_NOTIONAL:.0f}x{MAX_POSITIONS} · "
          f"xsect ${XSECT_CLIP:.0f}x2x{K} | frozen until {FREEZE_UNTIL_ISO} | "
          f"realized so far ${realized:+.2f} ({n_closed} closed)")

    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except (TypeError, ValueError):
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()

    while True:
        t0 = time.time()
        # SOLE-WRITER ENFORCEMENT AT THE TOP OF THE LOOP ((hp)/(ic)): a
        # detector that runs after the trading pass is a report, not a guard.
        _ok_writer, _other = store.claim_writer(bot_id)
        if not _ok_writer:
            print(f"[{now_iso()}] STANDING DOWN — {bot_id} is claimed by "
                  f"another container ({_other}). Two writers make `n` a "
                  f"mixture of two books; holding until the claim expires "
                  f"({store.WRITER_CLAIM_TTL}s) or the incumbent stops.",
                  flush=True)
            try:
                # the loser must NOT touch the book's row ((ic)) — its state
                # goes on its OWN key, with the caps that identify WHICH
                # build is standing down.
                store.save_state(_standby_key(bot_id), {
                    "standing_down": True, "book": bot_id,
                    "duplicate_writer": _other,
                    "svc": store.service_name() or None,
                    "venue": _mode,
                    "caps": {"enter_apr": ENTER_APR,
                             "max_positions": MAX_POSITIONS, "k": K},
                    "updated": now_iso(),
                    "ttl_sec": store.WRITER_CLAIM_TTL,
                })
            except Exception:  # noqa: BLE001
                pass
            time.sleep(LOOP_SECONDS)
            continue

        _moved = apply_tuning(t0)
        if _moved:
            print(f"[{now_iso()}] levers applied {_moved} | "
                  f"enter>={ENTER_APR:.4f} max={MAX_POSITIONS} k={K}")

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:  # noqa: BLE001
            print(f"[{now_iso()}] funding fetch failed ({e!r}); retrying")
            fund = None

        if fund:
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
                    # modelled close of a delisted book
                    close_fee = ((SLIP_COST + HEDGE_COST)
                                 if pos["sleeve"] == "carry" else SLIP_COST)
                    pos["fees"] += close_fee * pos["notional"]
                    pnl = position_pnl(pos, pos.get("last_mark"))
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    _close(bot_id, key, pos, "delisted", None, pnl,
                           pos.get("last_mark"))
                    print(f"[{now_iso()}] CLOSE {key} [delisted] "
                          f"pnl {pnl:+.2f} | realized {realized:+.2f}")
                    del positions[key]
                    continue
                pos.pop("missing_since", None)
                rate = float(f.get("rate") or 0.0)
                mark = float(f.get("mark") or 0.0)
                apr = rate * H
                if pos["sleeve"] != "carry" and mark > 0:
                    pos["last_mark"] = mark
                # funding accrual at the venue's own hourly settlement
                sign = 1.0 if pos["side"] == "long" else -1.0
                pos["accrued"] += ((-sign) * funding_basis.to_hourly(
                    rate, "lighter") * dt_h * pos["notional"])

                if pos["sleeve"] == "carry":
                    reason = carry_exit(pos, apr, t0)
                elif pos["sleeve"] == "extreme":
                    reason = extreme_exit(pos, apr, mark, t0)
                else:
                    reason = None            # xsect closes at rebalance only
                if reason is None:
                    continue
                close_fee = ((SLIP_COST + HEDGE_COST)
                             if pos["sleeve"] == "carry" else SLIP_COST)
                pos["fees"] += close_fee * pos["notional"]
                pnl = position_pnl(pos, mark)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                held_h = (t0 - pos["opened_ts"]) / 3600.0
                _close(bot_id, key, pos, reason, rate, pnl, mark)
                print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                      f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                      f"realized {realized:+.2f}")
                del positions[key]

            # ---- persistence bookkeeping (shared harvest clock) ---------
            for c, f in fund.items():
                try:
                    hot = abs(float(f.get("rate") or 0.0) * H) >= ENTER_APR
                except (TypeError, ValueError, AttributeError):
                    hot = False
                if hot:
                    hot_since.setdefault(c, t0)
                else:
                    hot_since.pop(c, None)

            held_harvest = {p["coin"] for p in positions.values()
                            if p["sleeve"] in ("carry", "extreme")}
            census = harvest_census(fund, held_harvest, hot_since, t0,
                                    ENTER_APR, CARRY_MIN_VOL)
            # [(lv)] The extreme sleeve gets its OWN census. Without it the
            # sleeve publishes `open: 0` and NOTHING else — byte-identical to
            # "the venue is quiet", which is exactly how it sat dead for its
            # whole first 8 days unnoticed (I1: a payload must distinguish a
            # starved organ from an empty one). Its floor is 5x the carry
            # sleeve's, so the shared census cannot speak for it.
            census_ext = harvest_census(fund, held_harvest, hot_since, t0,
                                        ENTER_APR, EXTREME_MIN_VOL)

            # ---- carry sleeve entries -----------------------------------
            n_carry = sum(1 for p in positions.values()
                          if p["sleeve"] == "carry")
            if n_carry < MAX_POSITIONS:
                for c, f, apr in harvest_candidates(
                        fund, held_harvest, hot_since, t0, ENTER_APR,
                        CARRY_MIN_VOL, MAX_POSITIONS - n_carry):
                    side = "short" if apr > 0 else "long"
                    if _open_position(positions, "carry", c, side,
                                      CARRY_NOTIONAL, t0, apr):
                        held_harvest.add(c)
                        print(f"[{now_iso()}] OPEN carry:{c} {side} "
                              f"${CARRY_NOTIONAL:.0f} | {apr:+.1%} TRUE")

            # ---- extreme sleeve entries — RETIRED 2026-08-13 (ly) --------
            # THE I17 KEEP-OR-RETIRE CALL, MADE. `(lv)` measured this sleeve
            # structurally starved (offered nothing carry had not claimed in
            # 0 of 8,611 snapshots) and escalated the floor as a policy call.
            # The follow-up measurement retires it instead, because EVERY
            # reachable setting is undecidable and the cheap ones cannibalise
            # the sleeve that works. With the (lv) class screen on, over the
            # full 30d tape, extreme entries / days-to-30-closes:
            #     $10M any order   0   never          (shipped)
            #     $5M  any order   0   never          (the cage's own floor)
            #     $3M  extreme-1st 1   903 days
            #     $2M  extreme-1st 5   181 days  — and carry goes 5 -> 0
            #     $1M  extreme-1st 7   129 days  — and carry goes 5 -> 0
            # Lowering the floor ALONE is inert at any value >= carry's,
            # because the subset relation holds and carry still runs first;
            # only floor+reorder together move anything, and then the two
            # harvest sleeves are bidding for the SAME 3-4 crypto names.
            # This venue supports ONE harvest sleeve, not two: at the 20%
            # TRUE bar the crypto population is KAITO/XMR/PAXG/XRP, and the
            # highest 24h volume ever seen on a qualifying crypto book is
            # $5.53M — below the floor this sleeve inherited from 💸 the
            # Farmer, where it exists to guarantee REAL fills.
            # So 🎸 Barnesy is a TWO-sleeve book (carry + xsect) and its own
            # description now says so. This changes NO trades today (the
            # sleeve has never opened one); what it buys is that the next
            # session cannot "fix" the ordering and silently take carry's
            # supply away. The census below KEEPS PUBLISHING so the decision
            # stays falsifiable — if the venue's liquidity ever rises to meet
            # the bar, `extreme.scan.eligible` goes positive and says so.
            # Reversible without a deploy: BARNES_EXTREME_RETIRED_OVERRIDE=run
            n_ext = sum(1 for p in positions.values()
                        if p["sleeve"] == "extreme")
            if EXTREME_RETIRED and n_ext:
                # defensive only: entries are gated off, so a live position
                # here means a restored pre-retirement state. Let it exit by
                # its normal rules (retirement is ENTRY-only, the (if)/(jh)
                # convention) — never strand a position with no exit path.
                pass
            if not EXTREME_RETIRED and n_ext < MAX_POSITIONS:
                for c, f, apr in harvest_candidates(
                        fund, held_harvest, hot_since, t0, ENTER_APR,
                        EXTREME_MIN_VOL, MAX_POSITIONS - n_ext):
                    side = "short" if apr > 0 else "long"
                    if _open_position(positions, "extreme", c, side,
                                      EXTREME_NOTIONAL, t0, apr,
                                      mark=float(f.get("mark") or 0.0)):
                        held_harvest.add(c)
                        print(f"[{now_iso()}] OPEN extreme:{c} {side} "
                              f"${EXTREME_NOTIONAL:.0f} | {apr:+.1%} TRUE")

            # ---- xsect sleeve rebalance ---------------------------------
            if (t0 - xsect_last) >= XSECT_REBALANCE_H * 3600.0:
                xsect_last = t0
                # rank over the scout universe; a dark scout degrades to the
                # venue-direct funding map (never "trade nothing").
                uni = resolve_xsect_universe(fund)
                aprs = {}
                for c in uni:
                    f = fund.get(c)
                    if not f:
                        continue
                    try:
                        aprs[c] = float(f.get("rate") or 0.0) * H
                    except (TypeError, ValueError):
                        continue
                longs, shorts = xsect_targets(aprs, K)
                want = {f"xsect:{c}": ("long" if c in longs else "short")
                        for c in longs + shorts}
                # close legs that left the target set (or flipped side)
                for key in [k for k in positions if k.startswith("xsect:")]:
                    pos = positions[key]
                    if want.get(key) == pos["side"]:
                        continue
                    f = fund.get(pos["coin"]) or {}
                    rate = float(f.get("rate") or 0.0)
                    mark = float(f.get("mark") or 0.0)
                    pos["fees"] += SLIP_COST * pos["notional"]
                    pnl = position_pnl(pos, mark)
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    _close(bot_id, key, pos, "rebalance", rate, pnl, mark)
                    print(f"[{now_iso()}] CLOSE {key} [rebalance] "
                          f"pnl {pnl:+.2f}")
                    del positions[key]
                # open missing legs
                if longs or shorts:
                    for key, side in want.items():
                        if key in positions:
                            continue
                        c = key.split(":", 1)[1]
                        f = fund.get(c) or {}
                        if _open_position(positions, "xsect", c, side,
                                          XSECT_CLIP, t0,
                                          float(f.get("rate") or 0.0) * H,
                                          mark=float(f.get("mark") or 0.0)):
                            print(f"[{now_iso()}] OPEN xsect:{c} {side} "
                                  f"${XSECT_CLIP:.0f}")

            # ---- publish -------------------------------------------------
            open_pnl = sum(position_pnl(p, (fund.get(p["coin"]) or {}).get("mark"))
                           for p in positions.values())
            equity = START_EQUITY + realized + open_pnl
            extra = build_extra(census, positions, open_pnl, realized,
                                _moved, t0, census_ext=census_ext)
            try:
                store.publish(
                    bot_id, status="online", equity=equity,
                    pnl_abs=realized + open_pnl,
                    pnl_pct=(equity / START_EQUITY - 1.0),
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins,
                    losses=n_closed - n_wins, extra=extra)
                # MTM equity series from DAY ONE — the (hq) class closed at
                # birth instead of retrofitted: the go-live drawdown bar
                # folds this series in and a book that holds is otherwise
                # invisible to it.
                store.snapshot_equity(bot_id, equity, len(positions), realized)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(bot_id, build_state(
                    positions, hot_since, last_ts, xsect_last, t0))
            except Exception:  # noqa: BLE001
                pass

            held = ", ".join(sorted(positions)) or "none"
            print(f"[{now_iso()}] scan ok | {len(fund)} books | open: {held} "
                  f"| open_pnl {open_pnl:+.2f} | realized {realized:+.2f} | "
                  f"cold {census['cold']}, thin {census['thin']}, waiting "
                  f"{census['waiting']}, noncrypto {census['noncrypto']}, "
                  f"eligible {census['eligible']} | extreme eligible "
                  f"{census_ext['eligible']} (thin {census_ext['thin']})")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Covers the sleeve gates, the exit rules, the tag round-trip
    through the REAL parser, the freeze, and the publisher-built payload.
    Mutation-verified at authoring time: the enter_apr gate (drop the vol
    floor / persistence / the *H conversion) and the decay-paid payback rule
    each redden this when broken."""
    t0 = 1_000_000.0
    hot_old = {"A": t0 - 7 * 3600, "B": t0 - 7 * 3600, "C": t0 - 7 * 3600,
               "D": t0 - 7 * 3600}
    # rate 3e-4 * 1095 = 0.3285 TRUE (hot); 9.6e-5 -> 0.10512 TRUE (cold at
    # the 20% bar — the verified ETH anchor from funding_basis).
    fund = {"A": {"rate": 3e-4, "vol": 5e6, "mark": 10.0},
            "B": {"rate": -4e-4, "vol": 3e6, "mark": 5.0},
            "C": {"rate": 3e-4, "vol": 1e5, "mark": 1.0},    # thin
            "D": {"rate": 9.6e-5, "vol": 5e6, "mark": 2.0},  # cold: 10.5% TRUE
            "E": {"rate": 5e-4, "vol": 5e6, "mark": 3.0}}    # hot, not persisted

    # every fixture coin is crypto unless a case says otherwise — the class
    # screen has its OWN section below, and letting the live `_class_ok` run
    # here would make these gate assertions depend on the scout being up.
    _all_crypto = lambda _c: True                              # noqa: E731

    # 1) the harvest gate: bar, floor, persistence, ordering, cap, held-skip
    cands = harvest_candidates(fund, set(), hot_old, t0, 0.20, 2e6, 4,
                               class_ok=_all_crypto)
    assert [c for c, _f, _a in cands] == ["B", "A"], cands
    assert harvest_candidates(fund, {"A", "B"}, hot_old, t0, 0.20, 2e6, 4,
                              class_ok=_all_crypto) == []
    # the E coin is hot and liquid but has no persisted streak -> excluded
    assert all(c != "E" for c, _f, _a in cands)
    # the D coin is the 8x trap: 9.6e-5 quoted IS 10.5% TRUE, below a 20% bar.
    # If a mutation drops the *H conversion, D's bare rate never clears any
    # sane bar either — so pin the OTHER direction: a bar in QUOTED units
    # would admit nothing at all.
    assert harvest_candidates(fund, set(), hot_old, t0, 0.20 / H, 2e6, 9,
                              class_ok=_all_crypto) != [], \
        "gate must compare TRUE apr, not the quoted per-period rate"
    # extreme's $10M floor excludes everything in this fixture
    assert harvest_candidates(fund, set(), hot_old, t0, 0.20, 10e6, 4,
                              class_ok=_all_crypto) == []

    # 1b) [(lv)] THE INSTRUMENT-CLASS SCREEN. 🎸's harvest sleeves took the
    # class 🌾 the parent screens out — all 8 real carry closes were WTI /
    # SKHYNIXUSD / SPCX at a 0% win rate. The screen is ENTRY-ONLY and the
    # gate must sit LAST, so a non-crypto name that is also cold still reads
    # `cold` rather than masking the cheaper reason.
    _no_b = lambda c: c != "B"                                 # noqa: E731
    screened = harvest_candidates(fund, set(), hot_old, t0, 0.20, 2e6, 4,
                                  class_ok=_no_b)
    assert [c for c, _f, _a in screened] == ["A"], screened
    # fail-OPEN, exercised on the REAL `_class_ok`: a class lookup that raises
    # or a fleet_bus that never imported must ADMIT, never empty the book — an
    # import regression must not silently shrink the universe (the parent's
    # contract, and the load-bearing degrade).
    global fleet_bus
    _saved_bus, _saved_allow = fleet_bus, ALLOW_NONCRYPTO
    try:
        class _Boom:
            @staticmethod
            def is_crypto(_c):
                raise RuntimeError("class service down")
        fleet_bus = _Boom()
        assert _class_ok("ANYTHING") is True, "a raising lookup must fail OPEN"
        fleet_bus = None
        assert _class_ok("ANYTHING") is True, "a missing fleet_bus must fail OPEN"
        # and the screen must actually BITE when the bus answers honestly
        class _Bus:
            @staticmethod
            def is_crypto(c):
                return c == "A"
        fleet_bus = _Bus()
        assert _class_ok("A") is True and _class_ok("WTI") is False, \
            "the screen must consume the venue's own class verdict"
        # THE WIRING, not the function: called with NO class_ok, the gate and
        # the census must still consult `_class_ok`. Injecting class_ok in
        # every other assertion would leave the DEFAULT free to regress to
        # "admit everything" with the suite still green — a substring/shape
        # test is not a wiring test.
        _dflt = harvest_candidates(fund, set(), hot_old, t0, 0.20, 2e6, 4)
        assert [c for c, _f, _a in _dflt] == ["A"], \
            f"default gate must screen by class, got {_dflt}"
        _dcen = harvest_census(fund, set(), hot_old, t0, 0.20, 2e6)
        assert _dcen["noncrypto"] == 1 and _dcen["eligible"] == 1, _dcen
    finally:
        fleet_bus = _saved_bus

    # 2) the census mirrors the gate and sums to scanned
    cen = harvest_census(fund, set(), hot_old, t0, 0.20, 2e6,
                         class_ok=_all_crypto)
    assert cen == {"scanned": 5, "held": 0, "cold": 1, "thin": 1,
                   "waiting": 1, "noncrypto": 0, "eligible": 2}, cen
    assert sum(v for k, v in cen.items() if k != "scanned") == cen["scanned"]
    # the `noncrypto` bucket is the screen's LIVE BITE — it must move when the
    # screen bites, and the buckets must still partition `scanned`.
    cen_s = harvest_census(fund, set(), hot_old, t0, 0.20, 2e6, class_ok=_no_b)
    assert cen_s["noncrypto"] == 1 and cen_s["eligible"] == 1, cen_s
    assert sum(v for k, v in cen_s.items() if k != "scanned") == cen_s["scanned"]

    # 3) xsect: signs, k, refusal of a thin cross-section, zero-excluded
    aprs = {"P": 0.5, "Q": 0.4, "R": 0.3, "S": 0.2, "T": 0.1,
            "U": -0.5, "V": -0.4, "W": -0.3, "X": -0.2, "Y": -0.1,
            "Z": 0.0, "J": "junk"}
    longs, shorts = xsect_targets(aprs, 5)
    assert set(longs) == {"U", "V", "W", "X", "Y"}, "most NEGATIVE -> long"
    assert set(shorts) == {"P", "Q", "R", "S", "T"}, "most POSITIVE -> short"
    assert xsect_targets(aprs, 6) == ([], []), \
        "a cross-section thinner than 2k must be refused, not ranked"
    assert xsect_targets({}, 5) == ([], [])

    # 4) carry exit discipline — the (gq) rules
    def _pos(side="short", accrued=0.0, fees=0.0, opened=t0 - 3600):
        return {"sleeve": "carry", "coin": "A", "side": side,
                "notional": 80.0, "opened_ts": opened,
                "accrued": accrued, "fees": fees}
    # decay WITHOUT fee payback must NOT close (the parent's whole 0W/28L fix)
    p1 = _pos(accrued=0.05)
    assert carry_exit(p1, 0.001, t0) is None, \
        "decay before fee payback closed — that realises fees funding never repaid"
    # decay WITH payback closes as decay_paid
    p2 = _pos(accrued=1.0)
    assert carry_exit(p2, 0.001, t0) == "decay_paid"
    # a flip needs its grace period
    p3 = _pos(side="short")
    assert carry_exit(p3, -0.5, t0) is None, "flip must wait FLIP_GRACE_H"
    assert carry_exit(p3, -0.5, t0 + FLIP_GRACE_H * 3600 + 1) == "flip"
    # a flip that reverts clears the clock
    p4 = _pos(side="short")
    carry_exit(p4, -0.5, t0)
    assert carry_exit(p4, +0.5, t0 + 1800) is None and "flipped_since" not in p4
    # max hold + bleed stop
    assert carry_exit(_pos(accrued=1.0, opened=t0 - MAX_HOLD_H * 3600 - 1),
                      0.5, t0) == "max_hold"
    assert carry_exit(_pos(accrued=-5.0), 0.5, t0) == "bleed_stop"

    # 5) extreme exit — the hard stop is senior and side-correct
    def _ext(side, entry=10.0):
        return {"sleeve": "extreme", "coin": "A", "side": side,
                "notional": 40.0, "opened_ts": t0 - 3600, "accrued": 0.0,
                "fees": 0.0, "entry_mark": entry, "last_mark": entry}
    assert extreme_exit(_ext("long"), 0.5, 8.9, t0) == "hard_stop", \
        "long down 11% must stop"
    assert extreme_exit(_ext("short"), 0.5, 11.2, t0) == "hard_stop", \
        "short up 12% must stop"
    assert extreme_exit(_ext("long"), -0.5, 10.1, t0) != "hard_stop", \
        "a favourable move must never stop"
    assert extreme_exit(_ext("short"), 0.5, 10.0, t0 - 1) is None
    assert extreme_exit(_ext("short"), 0.001, 10.0, t0) == "decay"

    # 6) P&L: carry has no price term; mark sleeves do
    pc = _pos(accrued=2.0, fees=0.5)
    assert abs(position_pnl(pc, 999.0) - 1.5) < 1e-9, "carry must ignore marks"
    pe = _ext("long")
    pe["accrued"], pe["fees"] = 1.0, 0.2
    assert abs(position_pnl(pe, 11.0) - (0.8 + 0.1 * 40.0)) < 1e-9

    # 7) tag round-trip through the REAL parser — sleeve-graded, side-first
    for sleeve in ("carry", "extreme", "xsect"):
        for side in ("long", "short"):
            tag, exit_r = store.split_reason(
                sleeve_tag(sleeve, side) + "_decay_paid")
            assert tag == f"{side}-{sleeve}", (tag, sleeve, side)
            assert exit_r == "decay_paid", exit_r

    # 8) the birth freeze: a rail offering values moves NOTHING while frozen
    frozen_ts = _freeze_until_ts() - 86400.0
    thawed_ts = _freeze_until_ts() + 86400.0
    assert freeze_active(frozen_ts) and not freeze_active(thawed_ts)
    global tuning
    _orig = tuning

    class _Rail:
        @staticmethod
        def get_lever(name, default, now_ts=None):
            return 8 if name == "barnes.max_positions" else default
    tuning = _Rail
    try:
        assert apply_tuning(frozen_ts) == {}, \
            "the birth freeze must refuse the rail outright ((hm))"
        moved = apply_tuning(thawed_ts)
        assert moved == {"barnes.max_positions": 8}, moved
        assert MAX_POSITIONS == 8
    finally:
        tuning = _orig
        globals()["MAX_POSITIONS"] = _ENV_DEFAULTS["MAX_POSITIONS"]
    # ...and a dark rail is a no-op in either era
    tuning = None
    try:
        assert apply_tuning(thawed_ts) == {}
    finally:
        tuning = _orig

    # 9) publisher-built payload — non-degenerate, consumer-relevant keys
    positions = {}
    _open_position(positions, "carry", "A", "short", 80.0, t0, 0.33)
    _open_position(positions, "extreme", "B", "long", 40.0, t0, -0.33,
                   mark=5.0)
    assert _open_position(positions, "xsect", "C", "long", 33.0, t0, -0.2,
                          mark=0.0) is None, "an unpriceable mark leg must refuse"
    cen_x = harvest_census(fund, set(), hot_old, t0, 0.20, EXTREME_MIN_VOL,
                           class_ok=_all_crypto)
    extra = build_extra(cen, positions, 1.23, 4.56, {}, t0, census_ext=cen_x)
    assert extra["caps"]["enter_apr"] == ENTER_APR
    assert extra["caps"]["frozen"] is True and extra["caps"]["freeze_until"]
    assert extra["scan"]["scanned"] == 5
    assert extra["sleeves"]["carry"]["open"] == 1
    # [(lz)] the book must NAME what it holds, not just count it — the
    # cross-book concentration question is asked per COIN, and this row
    # published 11 open positions and zero coin names for its first 8 days.
    assert extra["held"] == {"A": "S", "B": "L"}, extra["held"]
    assert set(extra["held"]) == {p["coin"] for p in positions.values()}, \
        "every open position must appear in `held`"
    assert extra["sleeves"]["extreme"]["open"] == 1
    assert extra["sleeves"]["xsect"]["open"] == 0
    # [(lv)] the extreme sleeve must publish WHY it is empty at ITS OWN floor.
    # Without this the payload cannot tell a quiet venue from a sleeve that is
    # structurally unreachable — the 8-day blind spot this entry closes.
    assert extra["sleeves"]["extreme"]["floor_usd"] == EXTREME_MIN_VOL
    assert extra["sleeves"]["extreme"]["scan"]["eligible"] == 0, \
        "the fixture has nothing over $10M — the sleeve must SAY so"
    assert extra["sleeves"]["extreme"]["scan"]["thin"] >= 1, \
        "the reason must be attributable to the floor, not silence"
    # [(ly)] the retirement is a PUBLISHED fact, and the census survives it —
    # a retired sleeve that stopped reporting could never be un-retired on
    # evidence, which is the whole point of keeping the call falsifiable.
    assert extra["sleeves"]["extreme"]["retired"] is True, \
        "the extreme sleeve is retired (ly) and the row must say so"
    assert extra["sleeves"]["extreme"]["scan"]["scanned"] == 5, \
        "a retired sleeve MUST keep publishing its census"
    assert "scan" not in extra["sleeves"]["carry"], \
        "only the sleeve with its own floor carries its own census"
    st = store.json_safe(extra)
    assert st["sleeves"]["carry"]["cap"] == MAX_POSITIONS
    assert st["sleeves"]["extreme"]["scan"]["scanned"] == 5

    # 10) the persistence blob restores through the ONE owner of the rule
    blob = build_state(positions, {"A": t0 - 60}, t0, t0, now=t0)
    assert "saved_ts" in blob, "no saved_ts -> the (iu) fresh-wait class"
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 60)
    assert restored == {"A": t0 - 60}, restored
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 99999)
    assert restored == {}, "an outage-sized gap must not resurrect a streak"

    # 11) basis honesty: the bars are TRUE-apr fractions
    assert abs(funding_basis.to_apr(9.6e-05, "lighter") - 0.10512) < 1e-6
    assert 0 < EXIT_APR < ENTER_APR < 1.0
    assert H == 3 * 365

    print("lighter_band_barnes_bot self-tests passed "
          "(gates, exits, tags, freeze, payload, persistence).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
