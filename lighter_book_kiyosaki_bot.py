#!/usr/bin/env python3
"""
lighter_book_kiyosaki_bot.py — 🏦 Rich Dad (book-kiyosaki), the CASH-FLOW
DOCTRINE BOOK.

WHAT THIS IS (2026-08-13, operator: "read the book rich dad poor dad by
Robert Kiyosaki and create a bot from it")
  One $1,000 shadow book that trades Robert Kiyosaki's core lessons as
  mechanical rules on Lighter's funding tape. First of the BOOKS cohort
  (`book-<surname>-lshadow`, named for the AUTHOR — the Australian-musician
  rule keeps governing incubator-earned rows; an operator-commissioned themed
  build carries its own theme's name, as Barnesy and Garrett carried theirs).

THE LESSONS, AS RULES — each mapped to a gate this fleet has already
validated wherever one exists, with exactly ONE new rule (restrict-only):

  1. "An asset puts money in my pocket; a liability takes it out."
       The book holds ONLY funding-RECEIVING positions (assets). A position
       whose funding flips against it has become a liability and is SOLD —
       after FLIP_GRACE_H of persistence, because one adverse print is noise,
       not a liability ("don't let fear make the decision"). Exit reason:
       `liability_flip`.
  2. "The rich focus on cash flow, not capital gains."
       Delta-neutral MODELLED, the 🌾 carry shape: P&L = accrued funding −
       modelled costs, NO price term anywhere in this file. The book cannot
       win or lose on price; it can only collect or pay cash flow.
  3. "Pay yourself first."
       The (gq) decay-paid discipline, the fleet's measured best exit
       (+$71.42 on carry's `*_decay_paid`): a decayed position closes only
       AFTER its accrued income has repaid every modelled cost with margin —
       income is banked, never abandoned mid-payback. The realized ledger is
       published as `banked` in the income statement.
  4. "It's not how much you make, it's how much you keep" (financial
       literacy — the ONE NEW RULE). Every entry must pass the PAYBACK
       VELOCITY test: at the entry rate, accrued funding must repay the full
       modelled round trip within PAYBACK_MAX_H (120h — a deal must return
       its cost inside ~1/3 of the 336h max hold). At this file's declared
       friction (30bps RT) that makes the EFFECTIVE entry bar ~21.9% TRUE
       apr — a TIGHTENING of the validated 20% floor, never a widening, so
       it cannot admit anything the 21-Jul gate sweep did not validate; it
       can only decline some of it. Stated, not buried (I19).
  5. "Don't let emotions drive decisions" (fear and greed).
       Hysteresis on BOTH ends: 6h funding persistence before entry (greed
       guard — "persistent funding pays carries, spikes pay fees", the
       parent's validated bar) and FLIP_GRACE_H before a liability sale
       (fear guard). No discretionary paths exist.
  6. "Mind your own business — know your income statement."
       Every publish carries the book's own income statement: income
       (accrued), expenses (modelled fees), banked (realized), and the live
       asset/liability split of its positions. Pure observability.

WHAT IS DELIBERATELY NOT ENCODED, stated so no future session "finishes" it:
  * OPM / leverage ("good debt") — $1,000, no top-ups, is fleet law; a
    leverage game on a shadow book manufactures fake evidence.
  * "The rich invent money" as discretionary deal-making — the assistant
    does not direct trades; every rule here is mechanical.
  * Real estate / business equity — the venue trades perps; funding is the
    only on-venue cash flow, and it is the honest analogue of rent.

THE VALIDATED GATES INHERITED (the Barnesy carry-sleeve cell, itself the 🌾
parent's): enter >= 20% TRUE apr (21-Jul Lighter-tape sweep — the only bar
that beat shipped on the full window AND both halves), 6h persistence, $2M
24h-volume floor, decay bar 0.01875 TRUE, flip grace 6h ((mf) — was 1h;
measured on the cell: 1h churned half the profit away), max hold 336h,
bleed stop −2%, crypto perps only ((lk): carry's non-crypto era was 9-of-10
losers; a closed underlying satisfies persistence structurally, I7).

HONEST ABOUT THE EVIDENCE. The gates inherit their parents' Lighter-tape
evidence; the COMBINATION under one roof — and the payback tightening — is a
NEW policy with a fresh 30-day clock ((hm)). Nothing carries over. Gradeable
~12-Sep at the earliest, by the standard gate only.

CONFIG IS ENV-ONLY — NO TUNING LANE (the Garrett choice, (lp)): this book
reads no lever, so its (hm) clock is single-policy BY CONSTRUCTION and needs
no freeze machinery. Registering levers is a day-31 decision, taken only
once the book is decidable.

MODELLED, DECLARED (flat and conservative, the Barnesy numbers): each leg
pair charges SLIP_COST + HEDGE_COST per side (15bps per side, 30bps round
trip — Lighter's perp fee is zero, measured; the hedge leg is modelled, it
does not exist). Funding accrues at the venue's own hourly settlement via
funding_basis.to_hourly — every bar in this file is denominated in TRUE apr
by the one basis authority; no legacy threshold exists here and never may.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow is the only
accepted mode (loud SystemExit otherwise). This bot never constructs an
order path.

Usage:
    VENUE=lighter_shadow python lighter_book_kiyosaki_bot.py          # daemon
    VENUE=lighter_shadow python lighter_book_kiyosaki_bot.py --once   # smoke
    python lighter_book_kiyosaki_bot.py --selftest                    # offline
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import venue_context

# The class screen's one owner. Guarded like every optional organ: a dark
# import fails OPEN (admit — fleet_bus.is_crypto's own documented direction),
# never a crash inside a trading loop. The COPY lands in Dockerfile.kiyosaki
# in this same commit (a guarded import with a missing COPY is the born-dark
# failure this fleet has shipped three times).
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "book-kiyosaki"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = 300              # funding is hourly; 5-min polling is plenty

# TRUE-apr basis, one owner. H converts a quoted Lighter rate to TRUE apr;
# every threshold below is ALREADY a TRUE-apr fraction.
H = funding_basis.periods_per_year("lighter")
HOURS_PER_YEAR = 24.0 * 365.0   # TRUE apr is per year; payback is per hour

# ---- lesson 1/5: the asset gate (validated cell, inherited) -----------------
ENTER_APR = float(os.environ.get("RICHDAD_ENTER_APR", "0.20"))
EXIT_APR = float(os.environ.get("RICHDAD_EXIT_APR", "0.01875"))
PERSIST_H = 6.0                 # hot >= this long before entry (parent's bar)
# [2026-08-13 (mf)] 1.0 -> 6.0, MEASURED on this cell's own coin population
# (250d of settled fundings, KAITO/XMR/PAXG/XRP + the cell's visitors, the
# book's own gate + exits replayed): grace 1h = +$26.88 t=1.91 with h2
# NEGATIVE and 192/231 exits churning the 30bps RT on sign wobbles; grace 6h
# = +$42.09 t=3.00 both halves positive; monotone to 24h (+$50.87 t=3.56).
# Hull's ch.-3 basis-noise doctrine (the 🧮 book), landing on its sibling:
# a one-hour adverse spell is noise, not a liability. 6h chosen over 24h to
# keep the close cadence (27.7 -> 21.8/30d vs 16.6) on a book whose supply
# is already the starved 6.6%-occupancy cell (I17: decidability first) —
# and it mirrors PERSIST_H: six hours of proof to buy, six to sell.
FLIP_GRACE_H = 6.0              # a liability must persist before it is sold
MAX_HOLD_H = 14 * 24            # recycle capital (parent's bar)
DELIST_GIVEUP_H = 24.0          # coin absent from the map this long -> close
MIN_VOL = float(os.environ.get("RICHDAD_MIN_VOL", "2e6"))

# ---- lesson 2: capacity (cash flow only, so clip == exposure to costs) ------
CLIP_USD = float(os.environ.get("RICHDAD_CLIP_USD", "80"))
MAX_POSITIONS = int(os.environ.get("RICHDAD_MAX_POSITIONS", "6"))

# ---- lesson 3: pay yourself first ------------------------------------------
# decay-close only when net after ALL fees clears this margin — scaled from
# the parent's $0.10-on-$300 to this book's $80 clip (the Barnesy number).
PAYBACK_MARGIN = 0.03
BLEED_FRAC = 0.02               # close if net <= -2% of notional (parent's)

# ---- lesson 4: the payback-velocity literacy gate (THE one new rule) --------
# modelled friction, declared: 15bps per side on both legs of the modelled
# pair, both directions -> 30bps round trip of notional.
SLIP_COST = 0.0005              # per side (Lighter fee is zero, measured)
HEDGE_COST = 0.0010             # per side, the modelled off-venue hedge leg
RT_COST_FRAC = 2.0 * (SLIP_COST + HEDGE_COST)
# a deal must repay its own round trip within this many hours at the ENTRY
# rate. 120h == the 20%-floor payback (131.4h) tightened to an effective
# ~21.9% TRUE bar — restrict-only relative to the validated gate, by
# construction (payback_hours is monotone-decreasing in |apr|).
PAYBACK_MAX_H = float(os.environ.get("RICHDAD_PAYBACK_MAX_H", "120"))

# ---- (lk): crypto perps only, reversible without a deploy -------------------
ALLOW_NONCRYPTO = os.environ.get(
    "RICHDAD_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")


def _standby_key(bot_id):
    """The bot_state key a STOOD-DOWN container reports on — (ic): the loser
    must NOT touch the book's row. Suffix, never a rewrite."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- pure decision layer -----------------------------
def _class_ok(coin):
    """May `coin` ENTER this book? Crypto perps only — (lk). Fail-OPEN, the
    canonical owner's own direction: a class lookup must never stop a scan,
    and the venue lists new crypto books weekly."""
    if ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.is_crypto(coin))
    except Exception:      # noqa: BLE001
        return True


def payback_hours(apr, rt_cost_frac=None):
    """Lesson 4: hours for funding at TRUE apr `apr` to repay the full
    modelled round trip. inf when there is no income to repay with.
    Monotone-decreasing in |apr|, which is what makes the gate built on it
    restrict-only relative to the plain apr bar."""
    rt = RT_COST_FRAC if rt_cost_frac is None else rt_cost_frac
    a = abs(apr or 0.0)
    if a <= 0.0:
        return float("inf")
    return rt / (a / HOURS_PER_YEAR)


def candidates(fund, held, hot_since, t0, enter_apr=None, min_vol=None,
               max_n=None, persist_h=PERSIST_H, payback_max_h=None,
               class_ok=None):
    """Eligible (coin, f, apr) rows, hottest first, capped at max_n.

    Gate order (the parent's, + the two screens this book adds): not held,
    parseable, |TRUE apr| >= bar, volume >= floor, persisted >= persist_h,
    crypto class, payback within the literacy bound. Pure; decides nothing.
    """
    enter_apr = ENTER_APR if enter_apr is None else enter_apr
    min_vol = MIN_VOL if min_vol is None else min_vol
    max_n = MAX_POSITIONS if max_n is None else max_n
    payback_max_h = PAYBACK_MAX_H if payback_max_h is None else payback_max_h
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
        if payback_hours(apr) > payback_max_h:
            continue
        out.append((c, f, apr))
    out.sort(key=lambda x: -abs(x[2]))
    return out[:max_n]


def scan_census(fund, held, hot_since, t0, enter_apr=None, min_vol=None,
                persist_h=PERSIST_H, payback_max_h=None, class_ok=None):
    """WHY DID NOTHING OPEN? — the (is) census. Buckets are mutually
    exclusive, mirror the gate order exactly, and sum to `scanned`.
    `noncrypto` is blocked-by-class-alone ((lk): behind the economic gates);
    `slow_payback` is blocked by the literacy gate alone — the book's own
    signature rule gets its own visible count. Pure observability."""
    enter_apr = ENTER_APR if enter_apr is None else enter_apr
    min_vol = MIN_VOL if min_vol is None else min_vol
    payback_max_h = PAYBACK_MAX_H if payback_max_h is None else payback_max_h
    class_ok = _class_ok if class_ok is None else class_ok
    out = {"scanned": len(fund or {}), "held": 0, "cold": 0, "thin": 0,
           "waiting": 0, "noncrypto": 0, "slow_payback": 0, "eligible": 0}
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
        apr = rate * H
        if abs(apr) < enter_apr:
            out["cold"] += 1
        elif vol < min_vol:
            out["thin"] += 1
        elif (t0 - (hot_since or {}).get(c, t0)) < persist_h * 3600.0:
            out["waiting"] += 1
        elif not class_ok(c):
            out["noncrypto"] += 1
        elif payback_hours(apr) > payback_max_h:
            out["slow_payback"] += 1
        else:
            out["eligible"] += 1
    return out


def cashflow_exit(pos, apr, t0):
    """Lessons 1/3/5 as the exit rule — the 🌾/(gq) discipline in shape:
    a liability is sold only after FLIP_GRACE_H (fear guard), a decayed
    asset closes only after payback (pay yourself first), max-hold recycles
    capital, the bleed stop bounds a position whose costs outrun income.
    Returns the exit reason or None. Mutates only the flip clock."""
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
    lesson 2 is structural, not a preference: this function cannot see a
    mark, so no future edit can quietly turn the book directional without
    changing its signature."""
    return pos["accrued"] - pos["fees"]


def income_statement(positions, realized):
    """Lesson 6: the book's own income statement, published every loop.
    `assets` are positions currently RECEIVING; `liabilities` are positions
    inside their flip grace (paying, awaiting the sale rule). The split is
    derived from the flip clock the exit rule itself maintains — one owner,
    so the telemetry cannot disagree with the rule."""
    return {
        "income": round(sum(p["accrued"] for p in positions.values()), 4),
        "expenses": round(sum(p["fees"] for p in positions.values()), 4),
        "banked": round(realized, 2),
        "assets": sum(1 for p in positions.values()
                      if "flipped_since" not in p),
        "liabilities": sum(1 for p in positions.values()
                           if "flipped_since" in p),
    }


def build_state(positions, hot_since, last_ts, now=None):
    """The persistence blob — ONE builder so the selftest exercises the same
    payload main() saves. `saved_ts` is what makes the hot-streak clock
    restorable AT ALL (funding_basis.restore_hot_since fails closed without
    it — the (iu) class)."""
    return {"positions": positions, "hot_since": hot_since,
            "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, open_pnl, realized):
    """The published `extra` — ONE builder, so the payload the dashboard,
    board and immune organ read is the payload the selftest asserted on
    (a consumer is tested against a payload its publisher built, (hj))."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        # [2026-08-13 (lz)] WHAT THIS BOOK IS ACTUALLY HOLDING, in 💸 the
        # Farmer's shape ({coin: "S"|"L"}) so ONE reader serves every funding
        # book. Load-bearing now that THREE books share this gate — 🌾 carry,
        # 🎸 Barnesy's carry sleeve and this one all enter at ~20% TRUE / $2M /
        # crypto-only, and the venue's whole crypto population at that bar is
        # KAITO/XMR/PAXG/XRP. Without this field nothing can ask whether three
        # "diversified" books are holding one coin.
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "funding_basis_periods_per_year": H,
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        # the caps this loop ACTUALLY gates on, so the board can see the
        # binding constraint instead of inferring it (I8 one layer in)
        "caps": {"enter_apr": ENTER_APR, "exit_apr": EXIT_APR,
                 "persist_h": PERSIST_H, "payback_max_h": PAYBACK_MAX_H,
                 "max_positions": MAX_POSITIONS, "clip_usd": CLIP_USD,
                 "min_vol": MIN_VOL,
                 "crypto_only": not ALLOW_NONCRYPTO},
        "scan": census,
        "income_statement": income_statement(positions, realized),
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_rate, pnl):
    """Ledger one close: `<side>-cashflow_<exit>` + the (gr) funding-form
    telemetry on EVERY row. No prices: the book is delta-neutral modelled —
    a price on its rows would be fabricated data, not telemetry (the
    Barnesy carry-sleeve rule, inherited deliberately)."""
    t = time.time()
    held_h = (t - pos["opened_ts"]) / 3600.0
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
            reason=f"{pos['side']}-cashflow_" + reason,
            venue="lighter", shadow=True,
            extra={"entry_apr": pos.get("entry_apr"),
                   "exit_apr": exit_rate,
                   "accrued": round(pos.get("accrued") or 0.0, 4),
                   "fees": round(pos.get("fees") or 0.0, 4),
                   "notional": pos.get("notional"),
                   "held_h": round(held_h, 2)})
    except Exception:  # noqa: BLE001
        pass


def _open_position(positions, coin, side, notional, t0, apr):
    """Open one modelled delta-neutral position; pays both modelled legs'
    open half up front (an expense is booked when incurred, lesson 6)."""
    positions[coin] = {"coin": coin, "side": side, "notional": notional,
                      "opened_ts": t0, "accrued": 0.0,
                      "fees": (SLIP_COST + HEDGE_COST) * notional,
                      "entry_apr": apr}
    return positions[coin]


def main():
    p = argparse.ArgumentParser(
        description="🏦 Rich Dad — the cash-flow doctrine book")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    # SHADOW ONLY, allowlist not blocklist: this book models a hedge leg it
    # does not have — every order-sending mode is refused, loudly, so a
    # flipped env is a decision someone sees, never a row that stops moving.
    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: book-kiyosaki (🏦 Rich Dad) runs "
            "VENUE=lighter_shadow ONLY. It is a $1,000 shadow book whose "
            "delta-neutral accounting models an off-venue hedge leg that "
            "does not exist, so any funded mode would run naked; go-live is "
            "a separate operator act behind the standard gate, never an env "
            "flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # book-kiyosaki-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}      # coin -> pos dict
    hot_since = {}      # coin -> ts |TRUE apr| first held >= ENTER_APR
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
            print(f"[{now_iso()}] restored {len(positions)} position(s) | "
                  f"hot-streak clock: {_why}")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🏦 Rich Dad start | venue lighter | "
          f"enter>={ENTER_APR:.2%} TRUE exit<{EXIT_APR:.2%} | "
          f"payback<={PAYBACK_MAX_H:.0f}h (effective bar "
          f"{RT_COST_FRAC * HOURS_PER_YEAR / PAYBACK_MAX_H:.1%}) | "
          f"${CLIP_USD:.0f}x{MAX_POSITIONS} | "
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
                             "max_positions": MAX_POSITIONS,
                             "payback_max_h": PAYBACK_MAX_H},
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
                # funding accrual at the venue's own hourly settlement
                sign = 1.0 if pos["side"] == "long" else -1.0
                pos["accrued"] += ((-sign) * funding_basis.to_hourly(
                    rate, "lighter") * dt_h * pos["notional"])

                reason = cashflow_exit(pos, apr, t0)
                if reason is None:
                    continue
                pos["fees"] += (SLIP_COST + HEDGE_COST) * pos["notional"]
                pnl = position_pnl(pos)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                held_h = (t0 - pos["opened_ts"]) / 3600.0
                _close(bot_id, key, pos, reason, rate, pnl)
                print(f"[{now_iso()}] CLOSE {key} {pos['side']} after "
                      f"{held_h:.1f}h [{reason}] pnl {pnl:+.2f} | "
                      f"banked {realized:+.2f}")
                del positions[key]

            # ---- persistence bookkeeping (the greed guard's clock) ------
            for c, f in fund.items():
                try:
                    hot = abs(float(f.get("rate") or 0.0) * H) >= ENTER_APR
                except (TypeError, ValueError, AttributeError):
                    hot = False
                if hot:
                    hot_since.setdefault(c, t0)
                else:
                    hot_since.pop(c, None)

            held = set(positions)
            census = scan_census(fund, held, hot_since, t0)

            # ---- entries: buy assets ------------------------------------
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                for c, f, apr in candidates(fund, held, hot_since, t0,
                                            max_n=free):
                    side = "short" if apr > 0 else "long"
                    _open_position(positions, c, side, CLIP_USD, t0, apr)
                    held.add(c)
                    print(f"[{now_iso()}] OPEN {c} {side} ${CLIP_USD:.0f} | "
                          f"{apr:+.1%} TRUE | payback "
                          f"{payback_hours(apr):.0f}h")

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
                # MTM equity series from DAY ONE — the (hq) class closed at
                # birth instead of retrofitted: the go-live drawdown bar
                # folds this series in.
                store.snapshot_equity(bot_id, equity, len(positions), realized)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.save_state(bot_id, build_state(
                    positions, hot_since, last_ts, t0))
            except Exception:  # noqa: BLE001
                pass

            held_s = ", ".join(sorted(positions)) or "none"
            print(f"[{now_iso()}] scan ok | {len(fund)} books | open: {held_s}"
                  f" | open_pnl {open_pnl:+.2f} | banked {realized:+.2f} | "
                  f"cold {census['cold']}, thin {census['thin']}, waiting "
                  f"{census['waiting']}, noncrypto {census['noncrypto']}, "
                  f"slow_payback {census['slow_payback']}, eligible "
                  f"{census['eligible']}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Covers the entry gates (including the payback tightening and
    the TRUE-apr conversion), the census mirror, the exit discipline, the
    no-price-term invariant, the tag round-trip through the REAL parser, the
    payload builders and the persistence blob. Mutation-verified at
    authoring time: dropping the *H conversion, the payback gate, the
    persistence gate or the payback requirement on decay each redden this."""
    t0 = 1_000_000.0
    hot_old = {c: t0 - 7 * 3600 for c in ("A", "B", "C", "D", "E", "S")}
    # rate 3e-4 * 1095 = 0.3285 TRUE (payback 80.0h — passes); 9.6e-5 ->
    # 0.10512 TRUE (cold at the 20% bar — the verified ETH anchor);
    # 1.9e-4 -> 0.20805 TRUE (clears the 20% bar, FAILS the payback gate:
    # 126.3h > 120 — the coin only the literacy rule refuses).
    fund = {"A": {"rate": 3e-4, "vol": 5e6},
            "B": {"rate": -4e-4, "vol": 3e6},
            "C": {"rate": 3e-4, "vol": 1e5},       # thin
            "D": {"rate": 9.6e-5, "vol": 5e6},     # cold: 10.5% TRUE
            "E": {"rate": 5e-4, "vol": 5e6},       # hot, not persisted
            "S": {"rate": 1.9e-4, "vol": 5e6}}     # slow payback: 20.8% TRUE
    hot_old.pop("E")

    # 1) payback velocity — the one new rule, pinned by arithmetic
    assert payback_hours(0.0) == float("inf")
    assert abs(payback_hours(0.20) - 131.4) < 0.1, payback_hours(0.20)
    assert payback_hours(0.20) > PAYBACK_MAX_H, \
        "a bare-20% coin must be refused by the literacy gate"
    assert payback_hours(-0.30) < PAYBACK_MAX_H, "sign must not matter"
    assert payback_hours(0.30) < payback_hours(0.25) < payback_hours(0.22), \
        "payback must be monotone-decreasing in |apr|"
    # the effective bar the gate implies, stated in the header: ~21.9%
    eff = RT_COST_FRAC * HOURS_PER_YEAR / PAYBACK_MAX_H
    assert 0.215 < eff < 0.225, eff
    assert eff > ENTER_APR, \
        "the literacy gate must TIGHTEN the validated bar, never widen it"

    # 2) the entry gate: bar, floor, persistence, class, payback, ordering
    cands = candidates(fund, set(), hot_old, t0, class_ok=lambda c: True)
    assert [c for c, _f, _a in cands] == ["B", "A"], cands
    assert candidates(fund, {"A", "B"}, hot_old, t0,
                      class_ok=lambda c: True) == []
    # S clears the validated 20% bar and is refused by payback alone
    assert all(c != "S" for c, _f, _a in cands)
    # E is hot and liquid but has no persisted streak -> excluded
    assert all(c != "E" for c, _f, _a in cands)
    # D is the 8x trap: 9.6e-5 quoted IS 10.5% TRUE, below a 20% bar. Pin
    # the direction that catches a dropped *H: a bar in QUOTED units admits.
    assert candidates(fund, set(), hot_old, t0, enter_apr=0.20 / H,
                      payback_max_h=1e9, class_ok=lambda c: True) != [], \
        "gate must compare TRUE apr, not the quoted per-period rate"
    # the class screen refuses what the venue calls non-crypto
    assert candidates(fund, set(), hot_old, t0,
                      class_ok=lambda c: c != "B") == \
        [x for x in cands if x[0] != "B"]

    # 3) the census mirrors the gate order and sums to scanned
    cen = scan_census(fund, set(), hot_old, t0, class_ok=lambda c: c != "B")
    assert cen == {"scanned": 6, "held": 0, "cold": 1, "thin": 1,
                   "waiting": 1, "noncrypto": 1, "slow_payback": 1,
                   "eligible": 1}, cen
    assert sum(v for k, v in cen.items() if k != "scanned") == cen["scanned"]
    cen2 = scan_census(fund, {"A"}, hot_old, t0, class_ok=lambda c: True)
    assert cen2["held"] == 1 and cen2["eligible"] == 1, cen2

    # 4) the exit discipline — lessons 1/3/5
    def _pos(side="short", accrued=0.0, fees=0.0, opened=t0 - 3600):
        return {"coin": "A", "side": side, "notional": 80.0,
                "opened_ts": opened, "accrued": accrued, "fees": fees}
    # decay WITHOUT payback must NOT close (pay yourself first)
    p1 = _pos(accrued=0.05)
    assert cashflow_exit(p1, 0.001, t0) is None, \
        "decay before payback closed — that realises costs income never repaid"
    # decay WITH payback banks as decay_paid
    p2 = _pos(accrued=1.0)
    assert cashflow_exit(p2, 0.001, t0) == "decay_paid"
    # a liability must persist its grace before it is sold (fear guard)
    p3 = _pos(side="short")
    assert cashflow_exit(p3, -0.5, t0) is None, \
        "one adverse print sold the position — that is fear, not the rule"
    assert cashflow_exit(p3, -0.5, t0 + FLIP_GRACE_H * 3600 + 1) == \
        "liability_flip"
    # an asset that resumes paying clears the liability clock
    p4 = _pos(side="short")
    cashflow_exit(p4, -0.5, t0)
    assert cashflow_exit(p4, +0.5, t0 + 1800) is None \
        and "flipped_since" not in p4
    # max hold + bleed stop
    assert cashflow_exit(_pos(accrued=1.0, opened=t0 - MAX_HOLD_H * 3600 - 1),
                         0.5, t0) == "max_hold"
    assert cashflow_exit(_pos(accrued=-5.0), 0.5, t0) == "bleed_stop"

    # 5) lesson 2 is structural: P&L has no price input at all
    pc = _pos(accrued=2.0, fees=0.5)
    assert abs(position_pnl(pc) - 1.5) < 1e-9
    import inspect
    assert "mark" not in inspect.signature(position_pnl).parameters, \
        "a mark parameter on position_pnl would let price P&L in"

    # 6) the income statement derives from the flip clock (one owner)
    ps = {"A": _pos(accrued=1.0, fees=0.2)}
    ps["B"] = _pos(side="long", accrued=0.5, fees=0.1)
    ps["B"]["flipped_since"] = t0
    stmt = income_statement(ps, 4.56)
    assert stmt["assets"] == 1 and stmt["liabilities"] == 1
    assert abs(stmt["income"] - 1.5) < 1e-9
    assert abs(stmt["expenses"] - 0.3) < 1e-9
    assert stmt["banked"] == 4.56

    # 7) tag round-trip through the REAL parser — side-first, brain-gradeable
    for side in ("long", "short"):
        for exit_r in ("decay_paid", "liability_flip", "max_hold",
                       "bleed_stop", "delisted"):
            tag, ex = store.split_reason(f"{side}-cashflow_{exit_r}")
            assert tag == f"{side}-cashflow", (tag, side, exit_r)
            assert ex == exit_r, (ex, exit_r)

    # 8) publisher-built payload — non-degenerate, consumer-relevant keys
    positions = {}
    _open_position(positions, "A", "short", 80.0, t0, 0.33)
    assert positions["A"]["fees"] == (SLIP_COST + HEDGE_COST) * 80.0
    extra = build_extra(cen, positions, 1.23, 4.56)
    assert extra["caps"]["enter_apr"] == ENTER_APR
    assert extra["caps"]["payback_max_h"] == PAYBACK_MAX_H
    assert extra["caps"]["crypto_only"] is True
    assert extra["scan"]["scanned"] == 6
    assert extra["income_statement"]["assets"] == 1
    # [(lz)] the book must NAME what it holds. This book shares its gate with
    # 🌾 carry and 🎸 Barnesy's carry sleeve (~20% TRUE / $2M / crypto-only),
    # and the venue's crypto population at that bar is four coins — so the
    # cross-book concentration check needs coin names, not a count.
    assert extra["held"] == {"A": "S"}, extra["held"]
    assert set(extra["held"]) == set(positions), \
        "every open position must appear in `held`"
    st = store.json_safe(extra)
    assert st["caps"]["max_positions"] == MAX_POSITIONS

    # 9) the persistence blob restores through the ONE owner of the rule
    blob = build_state(positions, {"A": t0 - 60}, t0, now=t0)
    assert "saved_ts" in blob, "no saved_ts -> the (iu) fresh-wait class"
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 60)
    assert restored == {"A": t0 - 60}, restored
    restored, _why = funding_basis.restore_hot_since(blob, t0 + 99999)
    assert restored == {}, "an outage-sized gap must not resurrect a streak"

    # 10) basis honesty: the bars are TRUE-apr fractions on the ONE authority
    assert abs(funding_basis.to_apr(9.6e-05, "lighter") - 0.10512) < 1e-6
    assert 0 < EXIT_APR < ENTER_APR < 1.0
    assert H == 3 * 365
    assert abs(RT_COST_FRAC - 0.003) < 1e-12, \
        "the declared friction model is what the payback bar prices"

    # 11) a dark class screen fails OPEN (the canonical owner's direction)
    global fleet_bus
    _orig = fleet_bus
    fleet_bus = None
    try:
        assert _class_ok("ANYTHING") is True
    finally:
        fleet_bus = _orig

    print("lighter_book_kiyosaki_bot self-tests passed "
          "(payback gate, entry gates, census, exits, income statement, "
          "tags, payload, persistence).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
