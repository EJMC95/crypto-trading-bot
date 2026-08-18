#!/usr/bin/env python3
"""
funding_carry_bot.py — DRY-RUN Hyperliquid funding-rate carry harvester.

WHY THIS BOT EXISTS (2026-07-03)
  The fleet's trend bots are (correctly) flat in risk-off chop, so nothing
  earns while the tide is out. Funding carry is the classic all-weather
  income strategy: perp funding is paid every hour by the crowded side of
  the book, and a DELTA-NEUTRAL position (perp on one side, hedge on the
  other) collects it without directional exposure. In extreme-fear regimes
  funding often runs hot on the short side — exactly when the trend bots
  sit out.

MODEL (paper, deliberately explicit about what is and is not simulated)
  - Reads REAL hourly funding rates from Hyperliquid mainnet public info
    (no keys, read-only, no orders ever).
  - When a liquid coin's funding annualizes above ENTER_APR, "open" a carry:
    funding > 0 (longs pay shorts)  -> short perp + long spot hedge
    funding < 0 (shorts pay longs)  -> long perp + short spot hedge
  - While open, accrue funding on the notional at the LIVE hourly rate each
    loop (rates decay — accrual follows them down, no entry-rate anchoring).
  - Costs: perp taker both sides + hedge-leg fees/spread both sides, charged
    half at open, half at close (HEDGE_COST covers that the hedge lives on
    another venue/spot book).
  - Close when annualized funding decays below EXIT_APR, flips against the
    position, or MAX_HOLD_H passes.
  NOT modelled: basis drift between perp and hedge venue, hedge borrow cost
  for the short-spot case, and liquidation risk (delta-neutral at 1x has
  none in practice). Treat results as the honest-but-favourable case.

  Realized episodes are mirrored into the shared Postgres paper_trades
  ledger (same scheme as the sniper) so cumulative P&L survives restarts.

Usage:
    python funding_carry_bot.py            # dry-run forever (the only mode)
    python funding_carry_bot.py --once     # single scan then exit (smoke test)
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)
from venues import venue_context  # [2026-07-09 LIGHTER GATE-0] venue abstraction

# [2026-07-30] growth-rail client. Guarded like every optional organ: a dark
# import leaves the operator's env defaults in force (apply_tuning() returns
# {} on `tuning is None`), never a crash inside a trading loop. The COPY is
# in Dockerfile.funding — added in the SAME commit as this import, because a
# guarded import plus a missing COPY is precisely the born-dark failure this
# fleet has shipped three times.
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
# [2026-08-05 (jr) S1] fleet_bus for the allocation organ's capital scale —
# COPY'd into Dockerfile.funding in the same commit (a guarded import with no
# COPY is the born-dark class the comment above names). A dark bus scales
# nothing: entries stay at the env-default NOTIONAL.
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "perps-funding-carry"


def _standby_key(bot_id):
    """[2026-08-01 (ic)] The bot_state key a STOOD-DOWN container reports on.

    Deliberately NOT the book's `bot_pnl` row and NOT a `bot_pnl` row at all.
    A second row would need `CURRENT_BOTS` registration and would render as a
    book that does not exist; writing the book's own row is what (ib) measured
    going wrong (the silenced container won it 10 of 12 samples, and its
    `heartbeat` would have kept a DEAD incumbent's row reading fresh).

    Suffix, never a rewrite: the key stays derivable from the row it shadows,
    so a reader that has the book id can always find its standby record.
    """
    return f"{bot_id}:standby"


# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
NOTIONAL = 300.0          # quote notional per carry position [2026-07-06 raised from $200]
# [2026-07-30 SLOT-BOUND — 8 -> 12] Measured at 7 open of 8: the fleet's
# BIGGEST EARNER (+$56.20 realised on n=80, t=2.42, both halves positive) was
# one slot from full and could not take the eighth-best carry it had already
# graded. Its 38.8% win rate is not a defect — carry's return lives in the
# tail, which is exactly why turning away graded candidates is expensive.
# Now also a registry-bounded lever (`carry.max_positions`, [6, 20]).
MAX_POSITIONS = int(os.environ.get("CARRY_MAX_POSITIONS", "12"))
# [2026-08-03 (it) THE FLOOR WAS THE BINDING GATE AND THE RAIL COULD NOT REACH
# IT] `carry.enter_apr` and `carry.max_positions` were both registered and both
# had slack — the book sat at 6 of 12 slots and went 98.9h without an OPEN —
# while the one gate that actually bound was a bare literal. A book whose only
# tunable knobs are the ones with room looks tunable and cannot move; the same
# shape as fleet_risk's LONG_BUDGET/SHORT_BUDGET.
#
# MEASURED against the scout's live `vols` (203 books): only **14** clear this
# $2M floor and the median book turns over $0.043M. The book's own hot list
# read CXMT -692.9% ($0.155M) and H100 +209.4% ($0.128M) — 13-16x BELOW the
# floor — while KAITO missed by **$2,000** ($1.998M).
#
# REGISTERING IT MOVES NOTHING: the env default is today's value, so this ships
# INERT. Cage [1e6, 2e6] — `hi` is today's setting so the rail may only loosen
# TOWARD the tape and can never tighten past it (the `disloc.exit_bps` idiom);
# `lo` stops at $1M, which doubles the eligible set (14 -> 26) while holding the
# $300 clip at <=0.03% of a book's daily turnover. DELIBERATELY NOT LOWER:
# per-book slippage here is unmeasured ([[lighter-slippage-is-per-book-not-per-venue]])
# and the real-money funding floors (`{xp,live}.funding.min_vol`) bottom at $2M.
#
# STATED AGAINST MY OWN CHANGE, because a growth claim that does not pay must
# not be banked: walking this cage to $1M today unlocks **ZERO** additional hot
# books. Only ONE liquid book clears the 20% TRUE bar (SKHYNIXUSD +137%) and
# carry already holds it; the hot coins are 6-13x below even $1M. The venue's
# funding distribution has collapsed — a market condition, not a defect. This
# removes a STRUCTURAL blind spot in the rail; it does not buy a trade today
# and must not be reported as if it did.
# [2026-08-18 (pr) CORRECTED IN PLACE per I12 — the "zero unlock" above was a
# POINT-IN-TIME census (3-Aug's loop), and over the whole tape it does not
# hold. Measured on 9,996 scout snapshots / 34.9 days through
# audit_book_overlap.supply_in (the gate rule's one owner): cell occupancy
# (>=20% TRUE, crypto, 6h persist) at $2M floor = 5.73% / 3 coins
# (KAITO/XMR/PAXG); at $1M = 13.42% / 6 coins (+ROBO/ENA/XRP), i.e. the
# $1-2M volume band holds MORE of this cell's life than the >=2M band does.
# The book had been flat 5.2 days at `eligible 0` when this shipped —
# operator direction "expand where necessary and loosen, give more
# opportunities". Default moves to the cage's own designed `lo` ($1M: clip
# <=0.03% of daily turnover, held from the paragraph above); the registry
# cage [1e6, 2e6] is unchanged, so the rail can now only TIGHTEN back toward
# the old floor. I19 price, declared: per-book slippage on $1-2M books is
# unmeasured — irrelevant to this MODELLED shadow book's fills, real for any
# future go-live, and the real-money floors ({xp,live}.funding.min_vol)
# are untouched by this change.
MIN_DAY_VOLUME = float(os.environ.get("CARRY_MIN_VOL", "1e6"))  # 24h $ turnover floor [2026-08-18 (pr): 2e6 -> 1e6]

# Funding thresholds, ANNUALIZED. These are denominated in THIS FILE'S ORIGINAL
# HYPERLIQUID basis (hourly rate * 24 * 365) and are NOT the numbers either arm
# compares against — `_basis()` below rescales them per venue. Hyperliquid's
# baseline funding is ~0.0000125/h ~= 11%/yr; we want clearly-hot funding.
# [2026-07-21 ENTRY GATE, measured on Lighter's OWN 150d tape —
# scripts/backtest_carry_gate_lighter.py] The 0.40 bar (5% TRUE on Lighter)
# was STRUCTURAL BLEED: -$93.31/150d, 20% win rate, and the week's *_flip
# closes ran 0W/23 — at 5% TRUE, the 29bps round trip needs 508h of accrual
# vs the 336h MAX_HOLD, so an entry AT the bar cannot pay for itself. The
# sweep was monotone and only 1.60 (20% TRUE) beat shipped on the full
# window AND both halves (+$55.93; h1 +17.48 / h2 +34.00). Env-tunable so
# the operator (or a future judge lane) can move it without a deploy.
ENTER_APR = float(os.environ.get("CARRY_ENTER_APR", "1.60"))  # 20% TRUE on Lighter [2026-07-06: 0.20->0.40; 2026-07-21: 0.40->1.60 per the gate sweep]
EXIT_APR = 0.15           # close when it decays below 15% [2026-07-06 raised from 8% to exit before fees eat accrual]
MAX_HOLD_H = 14 * 24      # recycle capital after 2 weeks [2026-07-06 extended from 7d to let high-rate carries compound]
# [2026-07-16 ZOMBIE GUARD] close a carry whose coin has been continuously
# absent from the funding map this long (delisted): the position could never
# expire and its fees dragged equity forever.
DELIST_GIVEUP_H = float(os.environ.get("CARRY_DELIST_GIVEUP_H", "24"))

# [2026-07-07 EXIT REBUILD] 0W/28L root cause: decay-exits realized fees before
# funding could pay them back (round-trip 29bps needs ~64h at 40% APR; spiky alt
# funding mean-reverts in hours). Decay alone NO LONGER closes a position:
#   * flip persisting >= FLIP_GRACE_H  (we are now PAYING funding — get out)
#   * decay only AFTER fee payback     (net after all fees >= FEE_PAYBACK_MARGIN)
#   * MAX_HOLD_H expiry                (capital recycling, unchanged)
#   * bleed stop                       (catastrophic guard on adverse holds)
# Entries additionally require the rate to have stayed hot >= PERSIST_H — the
# research-backed filter: persistent funding pays carries, spikes pay fees.
PERSIST_H = 6.0            # hours a coin must hold >= ENTER_APR before entry
# [2026-08-18 (pr)] FLIP GRACE 1h -> 6h, on the (mf) CARRY-CELL measurement
# (scripts/study_books_cohort_2026-08-13.py, this cell's OWN gate and coins,
# 250d of settled fundings): grace 1h = +$27.25, t=1.95, h2 NEGATIVE, with
# **192 of 231 exits churning the 30bps RT on sign wobbles**; 6h = +$41.17,
# t=2.96, BOTH halves positive; 24h = +$50.12, t=3.52 — monotone, a plateau,
# robust ex-best-coin. The book's own ledger agrees in shape ((gq): sided
# *_flip exits -$17.32 vs decay_paid +$71.42), and its 9-loss era IS nine
# flips. 6h over the 24h optimum for decidability (I17) — ~79% of the close
# cadence at double the per-trade expectancy — and it mirrors PERSIST_H: six
# hours of proof to buy, six to sell (the same choice 🏦 Rich Dad made on
# this cell at (mf)). (mf) QUEUED this change to protect carry's mid-window
# sample; that sample froze on 12-Aug ((pf): the class screen means it
# CANNOT update), and the book held ZERO positions when this shipped, so
# every future close is opened under the new rule — the cleanest policy
# boundary this book will ever get. The older study_carry_flip_grace_lighter
# "do not move from prose" pin is about ITS OWN uncalibrated replay ((he));
# this move rides the (mf) harness instead, which the fleet already consumed
# for Rich Dad. Ordinary exit tuning per (hc) — the era is unchanged.
FLIP_GRACE_H = float(os.environ.get("CARRY_FLIP_GRACE_H", "6.0"))  # hours of adverse funding before a flip-close [2026-08-18 (pr): 1.0 -> 6.0]
FEE_PAYBACK_MARGIN = 0.10  # $ net (after ALL fees incl. close) for a decay-close
BLEED_STOP_FRAC = 0.02     # close if net drops below -2% of notional

# Round-trip friction, as fractions of notional per SIDE of the round trip.
PERP_FEE = 0.00045        # HL taker per perp fill (conservative base tier)
HEDGE_COST = 0.0010       # hedge-leg fee + spread per fill (other venue/spot)
OPEN_COST = PERP_FEE + HEDGE_COST    # charged at open; same again at close

LOOP_SECONDS = 300        # funding is hourly; 5-min polling is plenty

HOURS_PER_YEAR = 24 * 365


def _basis(mode):
    """[2026-07-17 THE SIXTH 8x BOT] Per-venue funding basis for THIS file's two
    arms, as (H, scale).

      H     — periods per year in the venue's OWN quote basis. Multiply a quoted
              `rate` by H to get a TRUE apr.
      scale — what to multiply this file's HL-denominated thresholds by so the
              SAME rate still decides the SAME way. scale == H / (24*365).

    WHY THIS EXISTS. `HOURS_PER_YEAR = 24*365` is CORRECT for the `hl_paper`
    arm — Hyperliquid quotes hourly — and 8x WRONG for the `lighter_shadow`
    arm this file grew later: Lighter quotes per 8h. Every apr this bot
    computed, gated on, logged and published on that arm was 8x TRUE.

    HOW IT WAS MISSED, which is the part worth keeping: `funding_basis.py`'s
    header cleared this file BY NAME ("these sites are CORRECT and must not be
    touched: funding_carry_bot.py ... (Hyperliquid, hourly)"). That was TRUE
    when written and FALSE the day the Lighter arm landed. A named exemption is
    a blind spot with a half-life — re-derive it when a file gains a mode.

    BEHAVIOUR-NEUTRAL BY CONSTRUCTION (the 31ec660 shape): the conversion AND
    every threshold denominated in it move by the same factor, so
        rate*H >= ENTER_APR*scale   <=>   rate*(24*365) >= ENTER_APR
    holds for every rate. Same trades, honest labels. Proven in _selftest_basis.

    VENUE IS PASSED, NEVER DEFAULTED: funding_basis.DEFAULT_VENUE is "lighter"
    and this file's default arm is HYPERLIQUID — a bare call would invert the
    bug onto the honest arm.
    """
    import funding_basis
    venue = _venue_of(mode)
    H = funding_basis.periods_per_year(venue)
    return H, H / float(HOURS_PER_YEAR)


# [2026-07-30 AUTO-REVERT FIX] The operator's env defaults, snapshotted at
# IMPORT. apply_tuning() must hand THESE to get_lever, never the current
# global: get_lever returns its `default` when the lever is absent, expired
# or quarantined, so passing the already-moved value made the rail a ONE-WAY
# RATCHET — a widened lever could never revert, and auto-revert-on-expiry is
# the growth rail's central safety property ("levers EXPIRE back to defaults
# on their own, so auto-revert is the resting state"). Shipped broken in
# (fz); it was inert only because nothing authored the lane yet.
_ENV_DEFAULTS = {"ENTER_APR": ENTER_APR, "MAX_POSITIONS": MAX_POSITIONS,
                 "MIN_DAY_VOLUME": MIN_DAY_VOLUME}


def apply_tuning():
    """Growth-rail levers override the env defaults (bounded in the
    fleet_tuning registry; expired/absent/quarantined levers leave the
    defaults intact). Returns {lever: value} of whatever actually moved.

    [2026-07-30] Until now this book had NO registered levers at all —
    `carry.enter_apr` is the best-performing gate in the fleet and the
    growth rail could not touch it. Mutating the module globals (rather
    than threading values through) is deliberate: `_bars()` is the ONE
    OWNER of the enter/exit derivation, so a lever applied here reaches
    the gate through the same single path main() uses, and the basis
    selftest keeps exercising the real call site.
    """
    global ENTER_APR, MAX_POSITIONS, MIN_DAY_VOLUME
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in (("carry.enter_apr", "ENTER_APR"),
                        ("carry.max_positions", "MAX_POSITIONS"),
                        # [2026-08-03 (it)] the liquidity floor — the gate that
                        # was actually binding while the other two had room. It
                        # must be reached through THIS loop, not read from the
                        # module constant at the call site, or the lever is
                        # registered-but-inert: the exact failure the
                        # `lighter-books` lane was created to prevent.
                        ("carry.min_vol", "MIN_DAY_VOLUME")):
        cur = globals()[attr]
        try:
            val = tuning.get_lever(lever, _ENV_DEFAULTS[attr])
        except Exception:  # noqa: BLE001
            continue                      # a sick rail never stops the book
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


def _bars(mode):
    """The (H, enter_apr, exit_apr) THIS mode's arm actually compares against.

    ONE OWNER, deliberately. main() must not re-derive `ENTER_APR * scale`
    inline: a selftest that re-does that arithmetic proves the ARITHMETIC and
    not the WIRING, so dropping the `* scale` at the call site passes it. That
    is verbatim the trap 17-Jul (l) recorded — "its basis assertions exercise
    funding_basis, not the CALL SITE" — and my first cut of _selftest_basis
    reproduced it, caught by mutation. With the derivation here, the selftest
    exercises the same code main() does.
    """
    H, scale = _basis(mode)
    return H, ENTER_APR * scale, EXIT_APR * scale


# [2026-08-13 (lk)] INSTRUMENT-CLASS SCREEN — crypto perps only. The third
# funding book to need it, and the last found the hard way: (ki) screened 🎸
# Barnesy, (jg)-era work screened ⚖️ Counterweight, and this book — the
# fleet's best-evidenced — was left harvesting tokenised non-crypto funding.
# MEASURED, era ledger (opened >= 31-Jul): non-crypto −$14.96 over 9 closes
# (WTI ×4, SKHYNIXUSD ×2, SPCX ×2, all `*_flip` with FEES > ACCRUED on every
# loss) vs crypto −$0.49 over 1 — the whole era bleed of a book that is
# +$66.21 all-time. THE MECHANISM, not just the outcome: an instrument whose
# underlying market CLOSES holds its funding artifact for hours while nothing
# can arb it, so `PERSIST_H` — the research-backed spike filter, validated on
# 24/7 crypto — is satisfied STRUCTURALLY (I7) by every closed-market night,
# and the print snaps back at reopen: entry fees paid, accrual never arrives.
# WTI's four era flips each accrued $0.11–0.47 against $2.48–2.76 of fees.
# Pre-era non-crypto reads +$30.19/29, and honesty requires saying so — but
# that sample is the two-writer window plus the wrong accrual basis, the
# exact evidence the era declaration rules inadmissible.
# Screen is ENTRY-ONLY (a held position exits by its normal rules), fail-OPEN
# on a missing fleet_bus (an import regression must not shrink the universe —
# the dark-scout fallback INSIDE `is_crypto` is the load-bearing degrade),
# and reversible without a deploy: CARRY_ALLOW_NONCRYPTO=1.
ALLOW_NONCRYPTO = os.environ.get("CARRY_ALLOW_NONCRYPTO", "").strip().lower() \
    in ("1", "on", "true", "yes")


def _class_ok(coin):
    """May `coin` ENTER this book? Crypto perps only — see the block above."""
    if ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.is_crypto(coin))
    except Exception:      # noqa: BLE001 — a class lookup must never stop a scan
        return True


def scan_census(fund, positions, hot_since, t0, H, enter_apr,
                min_vol=None, persist_h=None, class_ok=None):
    """WHY DID NOTHING OPEN? -> a per-gate count of the loop's own decisions.

    [2026-08-02] THE INCIDENT. This book opened nothing for ~50h while holding
    5 of 12 slots and publishing `hottest_funding_apr` of +245% to +345%
    against a 20% bar. Everything about the row looked wrong and nothing was:
    the three coins that had cleared the 6h persistence gate (FOLKS $6k, S
    $123k, ARC $29k of 24h volume) were **1-3 ORDERS OF MAGNITUDE below the
    $2M liquidity floor**, and the one liquid hot coin (KAITO, $3.01M) was
    0.74h short of persisting. Only 12 of the venue's 203 books cleared the
    volume floor at all. A market condition, correctly handled — not a defect.

    ESTABLISHING THAT COST A 40-MINUTE INVESTIGATION across three sources —
    this bot's `hot_since` in its state key, the scout's `vols`, and the
    source for the gate order — because the book's own log said only
    `scan ok | 217 perps` and its `caps` carried the bar and the cap. **A
    reader could not tell "no candidates exist" from "a gate is blocking" from
    "the book is broken".** That is I8 one layer in: a book must be able to
    name its own binding constraint, or every quiet spell costs an
    investigation and the next one gets misdiagnosed.

    PURE, AND IT DECIDES NOTHING. The caller's eligibility expression is
    untouched; this only counts what those rules already decided. The buckets
    are mutually exclusive and sum to `scanned`, and `eligible` is pinned
    against the REAL candidate expression in the selftest — a census that can
    drift from the gate it explains is worse than no census at all.

    Bucket order mirrors the gate order deliberately, so `thin` means "hot but
    too illiquid" rather than "illiquid", which is the distinction that made
    the incident legible.
    """
    min_vol = MIN_DAY_VOLUME if min_vol is None else min_vol
    persist_h = PERSIST_H if persist_h is None else persist_h
    class_ok = _class_ok if class_ok is None else class_ok
    out = {"scanned": len(fund or {}), "held": 0, "thin": 0,
           "cold": 0, "waiting": 0, "noncrypto": 0, "eligible": 0}
    nxt = None
    for c, f in (fund or {}).items():
        if c in (positions or {}):
            out["held"] += 1
            continue
        if abs(f["rate"] * H) < enter_apr:
            out["cold"] += 1
        elif f["vol"] < min_vol:
            out["thin"] += 1
        elif (t0 - (hot_since or {}).get(c, t0)) < persist_h * 3600.0:
            out["waiting"] += 1
            # [18-Aug (qc)] `next` may only promise a coin the class screen
            # will ADMIT once its persistence completes. The screen sits
            # AFTER this branch (deliberately last, (lk)), so without this
            # check a crypto_only book advertised next=SKHYNIXUSD with a
            # live countdown — a promise the gate order guarantees to break
            # (I8: the operator misreads the coming refusal as a stall).
            # The coin still COUNTS as waiting; only the promise is scoped.
            if class_ok(c):
                eta = persist_h - (t0 - (hot_since or {}).get(c, t0)) / 3600.0
                if nxt is None or eta < nxt[1]:
                    nxt = (c, eta)
        elif not class_ok(c):
            # [(lk)] LAST in the gate order on purpose: this bucket means
            # "hot, liquid, persistent — blocked by class ALONE", i.e. the
            # screen's live bite, which is what lets the payload verify the
            # change (FORWARD MOTION rule 1) and the operator see its cost.
            out["noncrypto"] += 1
        else:
            out["eligible"] += 1
    if nxt:
        out["next"], out["next_eta_h"] = nxt[0], round(nxt[1], 2)
    return out


_MODE_VENUE = {"lighter_shadow": "lighter", "hl_paper": "hyperliquid"}


def _venue_of(mode):
    """This file's VENUE mode -> the funding_basis venue name.

    RAISES on an unknown mode — it does NOT default. Two reasons, both learned
    the hard way today:
      * funding_basis.DEFAULT_VENUE is "lighter", so a bare call there would
        invert the 8x onto the (historic) HYPERLIQUID arm.
      * an `else: "hyperliquid"` default would hand the 8x-wrong basis to any
        future Lighter mode that someone adds to main()'s allowlist without
        reading this file. That is exactly the shape of the defect this
        function exists to fix, rebuilt one layer down — and it is the rule the
        fleet shipped twice today: a default is fine for a preference, never
        for an IDENTITY that decides what a number MEANS.

    `hl_paper` is retained though `main()`'s allowlist no longer admits it
    (LIGHTER-ONLY, 17-Jul): it is what _selftest_basis uses to PROVE the
    conversion left the historic arm bit-identical.
    """
    try:
        return _MODE_VENUE[mode]
    except KeyError:
        raise ValueError(
            f"funding_carry_bot._venue_of: unknown VENUE mode {mode!r} — refusing "
            f"to guess a funding basis. Add it to _MODE_VENUE with its venue, "
            f"or the apr is silently 8x wrong. Known: {sorted(_MODE_VENUE)}"
        ) from None


def _hourly(rate, mode):
    """Quoted rate -> fraction accrued per HOUR, on THIS mode's venue basis."""
    import funding_basis
    return funding_basis.to_hourly(rate, _venue_of(mode))


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _perp_leg_fill(ctx, bot_id, coin, is_buy, notional, mark, publish=True):
    """Cost ($) of executing the Lighter perp leg of a carry (+ the fill price).

    [2026-07-10 SHADOW EXEC] The whole reason funding-carry belongs on Lighter is
    that the perp fee is ZERO — so the only perp-leg cost is the crossed-spread
    SLIPPAGE. In shadow mode we MEASURE it against the real live book instead of
    guessing, and write one venue_orders evidence row per fill (shadow=True). That
    accumulating evidence is what tells us whether real slippage on hot-funding
    coins lands near the backtest's optimistic 3bps (both-perp) or the 20bps
    (CEX-hedge) assumption — the number the go-live decision hinges on.

    The slippage reference is the LIVE-BOOK MID from the same snapshot as the
    fill — NOT the funding-map `mark`, which is a last-trade price frozen at
    LighterClient construction and never refreshed (it would inject unbounded
    drift into the evidence over a long run). `mark` is used only to seed the
    fallback when no book is available.

    Modes:
      hl_paper       : no venue/order path — model the leg with the flat PERP_FEE
                       constant exactly as before (zero behaviour change).
      lighter_shadow : walk the LIVE Lighter book via the same fill model the
                       ShadowBroker uses; ADVERSE slippage only (a fill worse than
                       the mid) is charged — price improvement is floored to 0
                       (conservative). A thin/absent book -> zero measured slippage
                       and a levels_used=0 row that flags the illiquidity for
                       later analysis rather than silently pretending we filled.
    `publish=False` measures without writing an evidence row — used by the decay
    close-gate to check the MEASURED exit cost before committing to a close.
    Funded modes never reach here (main() refuses them — no naked-perp path).
    """
    if ctx.mode == "hl_paper":
        return PERP_FEE * notional, mark
    from venues.shadow import fill_from_book  # local import: only lighter modes need it
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        book = None
    # Reference = live book mid (fresh); fall back to the funding-map mark only
    # when the book is unavailable (illiquidity — measured cost is then 0).
    ref = mark or 0.0
    spread_bps = None
    if book and book.get("bids") and book.get("asks"):
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        mid = (bid + ask) / 2.0
        if mid:
            ref, spread_bps = mid, (ask - bid) / mid * 1e4
    if not ref or ref <= 0:
        return PERP_FEE * notional, mark   # no price to size/measure -> model it
    size = notional / ref
    fill = fill_from_book(book, is_buy, size) if book else None
    fill_px = fill[0] if fill else ref
    levels = fill[1] if fill else 0
    slip = (fill_px - ref) * (1.0 if is_buy else -1.0)   # >0 == adverse
    cost = max(0.0, slip) * size
    slip_bps = (slip / ref * 1e4) if ref else None
    if publish:
        try:
            store.publish_venue_order(
                bot_id, venue="lighter", shadow=True, coin=coin,
                side="buy" if is_buy else "sell", size=size,
                px_decision=ref, px_fill=fill_px,
                spread_bps=spread_bps, slippage_bps=slip_bps,
                raw={"leg": "perp", "levels_used": levels,
                     "notional": round(notional, 2), "ts": time.time()})
        except Exception:
            pass
    return cost, fill_px


def main():
    p = argparse.ArgumentParser(description="DRY-RUN funding-carry harvester")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    # [2026-07-10 SHADOW EXEC] Funded modes are REFUSED. Funding-carry is
    # delta-neutral by construction (perp leg + hedge leg); a perp-only venue
    # like Lighter has no automated hedge, so a funded run would place a NAKED
    # perp and silently book its price P&L as if it were neutral — the opposite
    # of the strategy. Shadow is the supported live mode: it runs the full loop
    # on real Lighter data and MEASURES perp-leg slippage without sending orders.
    # A live harvest needs a hedge venue (CEX spot, or a correlated Lighter perp)
    # built + backtested first. See docs/lighter.md and memory
    # funding-carry-structural-edge-lighter.
    # Fail-safe ALLOWLIST (not a blocklist): only the two order-less modes are
    # permitted. Any other / future / unknown VENUE refuses, so a new funded mode
    # added to venues.MODES can never silently run this hedge-less bot naked.
    #
    # [2026-07-17 LIGHTER-ONLY — operator: "i only want things running on
    # lighter"] hl_paper is REMOVED from the allowlist and the default is now
    # lighter_shadow. The HL arm (row `perps-funding-carry`) was this bot's
    # data ORIGIN, and its edge was measured on HYPERLIQUID's funding — which
    # under the 17-Jul backtest rule is not evidence about Lighter, it is a
    # hypothesis about Lighter. The Lighter twin (`perps-funding-carry-lshadow`)
    # already runs the same loop on Lighter's own funding, so the shadow record
    # that matters continues uninterrupted; only the foreign-data arm stops.
    # The delta-neutral refusal below is UNCHANGED and still senior: this bot
    # has no hedge leg, so every order-sending mode stays refused regardless.
    # [22-Jul: DONE] The service now runs VENUE=lighter_shadow (verified via
    # `railway variables --service funding-carry`), so it no longer hits the
    # refusal below. Kept the loud SystemExit guard regardless: it is the
    # tripwire if the env is ever changed back — a foreign-venue arm going quiet
    # must be a decision you see, not a row that just stops moving.
    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode not in ("lighter_shadow",):
        raise SystemExit(
            f"VENUE={_mode}: funding-carry (Yield Harvester) runs "
            "VENUE=lighter_shadow ONLY. Two independent reasons: (1) LIGHTER-"
            "FIRST — hl_paper reads HYPERLIQUID funding, and the fleet is "
            "Lighter-only (operator, 17-Jul); flip the service's VENUE to "
            "lighter_shadow to keep the Lighter twin running. (2) This bot has "
            "NO automated delta-neutral hedge leg, so every order-sending mode "
            "would place a NAKED perp and book its price P&L as if neutral — "
            "the opposite of the strategy. lighter_shadow runs the full loop on "
            "real Lighter data and measures perp-leg slippage without sending.")

    # [2026-07-17] Per-venue basis + rescaled thresholds. MUST be derived from
    # _mode, not defaulted — see _basis(). Behaviour-neutral: on hl_paper the
    # scale is exactly 1.0 and every number below is byte-identical to before.
    # The derivation lives in _bars() so the selftest exercises THIS code and
    # not a re-implementation of it.
    _H, _enter_apr, _exit_apr = _bars(_mode)

    # [2026-07-09 LIGHTER GATE-0] Funding reads go through the venue layer.
    # VENUE unset -> hl_paper -> Hyperliquid MAINNET meta_and_asset_ctxs, the
    # exact pre-refactor source. VENUE=lighter_shadow reads Lighter's own
    # funding (which natively carries binance/bybit/hyperliquid benchmark rows
    # per market — the cross-venue carry evidence for wave 2). This bot never
    # constructs an order path and cannot place orders on ANY venue.
    ctx = venue_context(bot=BOT, default_hl_net="mainnet", paper_start=START_EQUITY)
    bot_id = ctx.bot_id
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Cumulative realized P&L survives restarts via the Postgres ledger.
    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    positions = {}  # coin -> dict(side, notional, opened_ts, accrued, fees, entry_apr)
    hot_since = {}  # coin -> ts when |APR| first held >= ENTER_APR [2026-07-07]

    # [2026-07-03 PERSIST] Restore open carries from Postgres so a redeploy keeps
    # accrued funding + entry levels (realized already restores from the ledger
    # above). Saved after every published loop below.
    try:
        # [2026-08-04 SEED GUARD] the CHECKED read — load_state() collapses
        # "no row" and "READ FAILED" into one None, so a Postgres blip at boot
        # seeded empty `positions` over real open carries and the loop's
        # save_state then overwrote the durable record. load_state_required
        # retries, then REFUSES (SystemExit — a BaseException, so this
        # try/except Exception deliberately does not swallow it): crash-loop
        # loudly rather than poison the fleet's best-evidenced ledger. No
        # DATABASE_URL keeps the old fresh-boot behavior.
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict) and _saved["positions"]:
            positions = _saved["positions"]
        # [2026-08-03 (iu)] THE HOT-STREAK CLOCK IS RESTORED FAIL-CLOSED.
        # It used to be restored UNCONDITIONALLY — any dict, any age, no
        # `saved_ts` and no gap bound. That is the MIRROR of the bug `(iq)`
        # fixed on the live Farmer: a LOST clock makes a book inert, a
        # WRONGLY-RESTORED one makes it PERMISSIVE, letting a coin skip
        # PERSIST_H on a streak that did not actually persist — the exact
        # spike entry this book's thesis exists to refuse. `funding_basis` is
        # the ONE OWNER of the rule so the two funding books cannot drift.
        if _saved is not None:
            import funding_basis  # function-local, matching this file's idiom
            hot_since, _why = funding_basis.restore_hot_since(
                _saved, time.time())
            print(f"[{now_iso()}] restored {len(positions)} open carry "
                  f"position(s) | hot-streak clock: {_why}")
    except Exception:
        pass

    # [2026-07-17] The banner prints the bars THIS ARM actually uses. It printed
    # the HL-denominated constants on both arms — so the lighter_shadow arm has
    # announced "enter>=40% APR" for its whole life while admitting at 5% TRUE.
    # Caught by _selftest_basis's call-site check, not by reading it.
    print(f"[{now_iso()}] funding-carry DRY-RUN start | venue {_venue_of(_mode)} "
          f"| enter>={_enter_apr:.2%} APR "
          f"exit<{_exit_apr:.2%} | ${NOTIONAL:.0f} x max {MAX_POSITIONS} | "
          f"friction {2*OPEN_COST*1e4:.0f}bps round-trip | realized so far "
          f"${realized:+.2f} ({n_closed} closed)")

    # [2026-07-16 AUDIT FIX] restore the accrual clock: it reset to
    # boot time on every redeploy, so funding during the gap was never
    # accrued (systematic undercount of the drag/credit this book
    # measures). Gap bounded to 48h so ancient state can't over-accrue.
    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()
    while True:
        t0 = time.time()
        # [2026-07-31 (hp)] SOLE-WRITER ENFORCEMENT, at the TOP of the loop.
        # (ho) added this check but only at the publish block — after the
        # trading pass had already opened and closed positions, so the second
        # container still corrupted the ledger it was meant to protect. A
        # detector that runs after the damage is a report, not a guard.
        #
        # THE OPERATOR'S INSTRUCTION (31-Jul): "delete the double bot so this
        # doesn't keep happening." `railway down` is not durable here — the
        # deploy workflow resurrects a stopped service on the next push, which
        # is why every retirement in this repo is a CODE GUARD (the 17-Jul
        # LIGHTER-ONLY cut). This is that guard: whichever container claims the
        # book first keeps it; the other IDLES.
        #
        # IDLE, never sys.exit: `restartPolicy=always` turns an exit into a
        # permanent crash-loop (the Trail Blazer pattern, 15-Jul). It keeps
        # heart-beating and publishes WHY, so a silenced container is visible
        # rather than merely absent.
        #
        # FAIL-OPEN is preserved: claim_writer returns (True, None) on a dark
        # DB or any exception, so a Postgres blip can never idle the book.
        #
        # THE NAME IS `bot_id`, NOT `BOT_ROW` (1-Aug (ib)). (hp) shipped this
        # call against `BOT_ROW`, which is bound NOWHERE in this file — `BOT`
        # (line 59) is the bare base and `bot_id = ctx.bot_id` (line 378) is
        # the suffixed row this process actually publishes. Every boot reached
        # the top of the loop and died on `NameError`, so the guard written to
        # PREVENT the Trail Blazer crash-loop (see the comment above) became
        # one: both carry containers restarted forever and the book had no
        # writer for 25.6h. The row read `status: "online"` throughout — its
        # last word before it stopped (I1).
        _ok_writer, _other = store.claim_writer(bot_id)
        if not _ok_writer:
            print(f"[{now_iso()}] STANDING DOWN — {bot_id} is already claimed "
                  f"by another container ({_other}). Two writers make `n` a "
                  f"mixture of two books and destroy the go-live evidence for "
                  f"the fleet's best-evidenced book. This process will hold "
                  f"its positions and trade NOTHING until the claim expires "
                  f"({store.WRITER_CLAIM_TTL}s) or the incumbent stops.",
                  flush=True)
            try:
                # [2026-08-01 (ic)] THE LOSER MUST NOT TOUCH THE BOOK'S ROW.
                # (hp) had this branch call `heartbeat(bot_id)` + `publish(
                # bot_id, status="standby")` so a silenced container would be
                # "visible rather than merely absent". Correct intent, and the
                # implementation inverted it — measured the hour the guard
                # first actually ran (it had never executed before (ib)):
                #
                #   * The standby loop is ~40s and the incumbent's is ~5min, so
                #     the SILENCED container won the row 10 of 12 samples. The
                #     card read `standby / n=None / open=None` while the book
                #     was trading (n 84 -> 85, 6 open). The working container
                #     was the invisible one.
                #   * `heartbeat` is worse than the clobber. It refreshes
                #     `updated_at` WITHOUT writing content, so had the
                #     incumbent died, this process would have kept the row
                #     reading FRESH over a frozen snapshot — I1, and the exact
                #     shape that hid 🌾 carry's death for 13h.
                #
                # ONE BOOK, ONE WRITER has to bind the ROW, not just the
                # ledger: a guard against two writers that is itself the second
                # writer enforces nothing. Standby state goes on its OWN key.
                # It is deliberately NOT a page — two live containers is the
                # DESIGNED steady state while both services exist, and a
                # detector that fires on the design trains the operator to
                # ignore it.
                store.save_state(_standby_key(bot_id), {
                    "standing_down": True,
                    "book": bot_id,
                    "duplicate_writer": _other,
                    "svc": store.service_name() or None,
                    "venue": ctx.mode,
                    # `caps` rides the standby payload for the same reason it
                    # rides the online one: it identifies WHICH build is
                    # standing down. A standby record without it is
                    # indistinguishable from a stale one — the ambiguity that
                    # produced this duplicate in the first place.
                    "caps": {"max_positions": MAX_POSITIONS,
                             "enter_apr": _enter_apr},
                    "updated": now_iso(),
                    "ttl_sec": store.WRITER_CLAIM_TTL,
                })
            except Exception:  # noqa: BLE001
                pass
            time.sleep(LOOP_SECONDS)
            continue
        # [2026-07-30] Re-read the growth rail EVERY loop, then RE-DERIVE the
        # bars through the same one-owner `_bars()` call. Both halves matter:
        # a lever that moved ENTER_APR without this re-derivation would be
        # silently inert, because `_enter_apr` was computed once before the
        # loop — the lever would appear enacted on the bus and change no
        # trade. TTL expiry reverts to the operator default by the same path.
        _moved = apply_tuning()
        if _moved:
            _H, _enter_apr, _exit_apr = _bars(_mode)
            print(f"[{now_iso()}] levers applied {_moved} "
                  f"| enter>={_enter_apr:.4f} max_open={MAX_POSITIONS}")
        try:
            fund = ctx.venue.funding_map()
        except Exception as e:
            print(f"[{now_iso()}] funding fetch failed ({e!r}); retrying next loop")
            fund = None

        if fund:
            dt_h = (t0 - last_ts) / 3600.0
            last_ts = t0

            # ---- manage open carries ------------------------------------
            for coin in list(positions):
                pos = positions[coin]
                f = fund.get(coin)
                if f is None:
                    # [2026-07-16 ZOMBIE GUARD] a coin that leaves the funding
                    # map used to pause EVERYTHING including max-hold — the
                    # carry could never expire and its open fees dragged
                    # equity forever. Delta-neutral, so the harm is slot +
                    # fees; give up after DELIST_GIVEUP_H continuously absent
                    # (modelled close cost — the live book is gone).
                    first = pos.setdefault("missing_since", t0)
                    if (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                        continue
                    pos["fees"] += OPEN_COST * pos["notional"] + \
                        HEDGE_COST * pos["notional"]
                    pnl = pos["accrued"] - pos["fees"]
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    held_h = (t0 - pos["opened_ts"]) / 3600.0
                    print(f"[{now_iso()}] CLOSE {coin} {pos['side']} after "
                          f"{held_h:.1f}h | accrued {pos['accrued']:+.2f} fees "
                          f"{pos['fees']:.2f} | pnl {pnl:+.2f} [delisted] "
                          f"| realized {realized:+.2f}")
                    try:
                        store.publish_paper_trade(
                            bot_id, trade_id=f"{coin}:{pos['opened_ts']:.0f}",
                            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=coin,
                            opened_at=datetime.fromtimestamp(
                                pos["opened_ts"], timezone.utc).isoformat(),
                            closed_at=datetime.now(timezone.utc).isoformat(),
                            # [2026-07-16] prefix the DIRECTION so the close
                            # carries an entry tag. A bare reason is untagged
                            # by design (split_reason, 14-Jul: treating
                            # 'flip'/'delisted' as entry modes cost the brain
                            # 92 runs) — the fix belongs HERE, not in the
                            # parser. First-underscore split keeps the exit
                            # intact: 'short_delisted' -> tag short / exit
                            # delisted.
                            reason=("short_" if pos["side"] == "short_perp"
                                    else "long_") + "delisted",
                            venue=venue_tag, shadow=shadow_tag)
                    except Exception:  # noqa: BLE001
                        pass
                    del positions[coin]
                    continue
                pos.pop("missing_since", None)   # back in the map — reset clock
                rate = f["rate"]
                apr = rate * _H
                # Accrue at the LIVE rate: we receive |funding| while it keeps
                # our sign, and PAY it if the rate flips before we exit.
                # [2026-07-17] `rate * dt_h` is only right when the quote IS
                # hourly. On the lighter_shadow arm the quote is per 8h, so this
                # over-accrued 8x — straight into `accrued`, which IS this
                # book's reported P&L and its win/loss call. This is the
                # load-bearing half of the sixth-8x-bot defect; the gates were
                # the visible half. to_hourly(rate, venue) is exactly the
                # venue's own hourly settlement (Lighter settles rate/8 per h).
                sign = -1.0 if pos["side"] == "short_perp" else 1.0
                pos["accrued"] += ((-sign) * _hourly(rate, _mode) * dt_h
                                   * pos["notional"])
                held_h = (t0 - pos["opened_ts"]) / 3600.0

                flipped_now = (pos["side"] == "short_perp" and apr < 0) or \
                              (pos["side"] == "long_perp" and apr > 0)
                # [2026-07-07 EXIT REBUILD] flip grace + fee-payback decay + bleed stop.
                if flipped_now:
                    pos.setdefault("flipped_since", t0)
                else:
                    pos.pop("flipped_since", None)
                # Cheap MODELLED estimate first (no per-loop book read): drives
                # the flip/expire/bleed backstops and the decay pre-filter.
                close_fee_est = OPEN_COST * pos["notional"]
                net_if_closed = pos["accrued"] - (pos["fees"] + close_fee_est)
                flipped = flipped_now and \
                    (t0 - pos["flipped_since"]) / 3600.0 >= FLIP_GRACE_H
                expired = held_h >= MAX_HOLD_H
                bleeding = net_if_closed <= -BLEED_STOP_FRAC * pos["notional"]
                # Decay-close only when funding has cooled AND closing still nets
                # positive after the MEASURED (not modelled) exit cost — else a
                # thin-book exit could realize a loss the fee-payback gate treated
                # as a win. Measured lazily: only once the cheap modelled gate
                # already wants to close (no book read every loop for every pos).
                closing_short = pos["side"] == "short_perp"
                decayed = False
                if abs(apr) < _exit_apr and net_if_closed >= FEE_PAYBACK_MARGIN:
                    _pc, _ = _perp_leg_fill(
                        ctx, bot_id, coin, is_buy=closing_short,
                        notional=pos["notional"], mark=(f.get("mark") or 0.0),
                        publish=False)
                    net_meas = pos["accrued"] - (
                        pos["fees"] + _pc + HEDGE_COST * pos["notional"])
                    decayed = net_meas >= FEE_PAYBACK_MARGIN
                if not (flipped or decayed or expired or bleeding):
                    continue

                # Realized closing friction: MEASURE the perp exit leg on the live
                # book (closing a short_perp is a BUY-back, a long_perp a SELL) +
                # the modelled hedge leg. Publishes the evidence row.
                perp_close_cost, _ = _perp_leg_fill(
                    ctx, bot_id, coin, is_buy=closing_short,
                    notional=pos["notional"], mark=(f.get("mark") or 0.0))
                pos["fees"] += perp_close_cost + HEDGE_COST * pos["notional"]
                pnl = pos["accrued"] - pos["fees"]
                reason = ("flip" if flipped else "decay_paid" if decayed
                          else "max_hold" if expired else "bleed_stop")
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                print(f"[{now_iso()}] CLOSE {coin} {pos['side']} after {held_h:.1f}h "
                      f"| accrued {pos['accrued']:+.2f} fees {pos['fees']:.2f} "
                      f"| pnl {pnl:+.2f} [{reason}] | realized {realized:+.2f}")
                try:
                    store.publish_paper_trade(
                        bot_id, trade_id=f"{coin}:{pos['opened_ts']:.0f}",
                        pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=coin,
                        opened_at=datetime.fromtimestamp(
                            pos["opened_ts"], timezone.utc).isoformat(),
                        closed_at=datetime.now(timezone.utc).isoformat(),
                        # [2026-07-16] direction prefix — see the delisted
                        # close above. 'short_' + 'decay_paid' splits back to
                        # tag short / exit decay_paid, so the brain can finally
                        # grade this book's two directions separately.
                        reason=("short_" if pos["side"] == "short_perp"
                                else "long_") + reason,
                        # [2026-07-30 (gr)] EXIT TELEMETRY, and note it is
                        # deliberately NOT entry_price/exit_price. This is a
                        # FUNDING book: its P&L is `accrued - fees`, so a
                        # price-path exit sweep would measure the wrong thing
                        # entirely. What decides its exit is the APR it entered
                        # at, the APR it left at, and how much it had actually
                        # been PAID by then. (gq) measured that this book earns
                        # +$71.42 on `*_decay_paid` (hold 65-70h) and loses
                        # -$17.32 on the sided flips (hold 6-10h) — and NONE of
                        # the fields needed to ask "should the flip have waited?"
                        # were on the row. Now they are. Telemetry only.
                        extra={"entry_apr": pos.get("entry_apr"),
                               "exit_apr": (fund.get(coin) or {}).get("rate"),
                               "accrued": round(pos.get("accrued") or 0.0, 4),
                               "fees": round(pos.get("fees") or 0.0, 4),
                               "notional": pos.get("notional"),
                               "held_h": round(held_h, 2)},
                        venue=venue_tag, shadow=shadow_tag)
                except Exception:
                    pass
                del positions[coin]

            # ---- persistence bookkeeping [2026-07-07] --------------------
            # Track how long each coin has held >= ENTER_APR. First-seen coins
            # start their clock now, so nothing enters before PERSIST_H.
            for c, f in fund.items():
                if abs(f["rate"] * _H) >= _enter_apr:
                    hot_since.setdefault(c, t0)
                else:
                    hot_since.pop(c, None)

            # ---- WHY DID NOTHING OPEN? [2026-08-02] ----------------------
            # THE INCIDENT: on 2-Aug this book had opened nothing for ~50h
            # while holding 5 of 12 slots and publishing `hottest_funding_apr`
            # of +245% to +345% against a 20% bar. Everything looked wrong and
            # nothing was: the coins clearing the 6h persistence gate (FOLKS,
            # S, ARC) were 1-3 ORDERS OF MAGNITUDE below the $2M liquidity
            # floor, and the one liquid hot coin (KAITO, $3.01M) was 0.74h
            # short of persisting. A market condition, not a defect.
            #
            # IT TOOK A 40-MINUTE INVESTIGATION ACROSS THREE SOURCES to
            # establish that — this bot's state key for `hot_since`, the
            # scout's `vols`, and the source for the gate order — because the
            # book's own log says only `scan ok | 217 perps` and its `caps`
            # carry only the bar and the cap. **Nobody could tell "no
            # candidates exist" from "a gate is blocking" from "the book is
            # broken".** That is I8 one layer in: a book must be able to name
            # its own binding constraint, or every quiet spell costs an
            # investigation and the next one gets misdiagnosed as a stall.
            #
            # PURE OBSERVABILITY. This changes no gate, no ordering and no
            # entry — the census is computed from `fund`, which is already in
            # hand, and the eligibility expression below is UNCHANGED. It only
            # counts what the existing rules already decided.
            # [2026-08-03 (is)] GUARDED, and the guard is the load-bearing
            # part. `scan_census` indexes `f["rate"]`/`f["vol"]` and raises on
            # a malformed funding entry (verified: KeyError on a missing key,
            # TypeError on a None rate). It also runs UNCONDITIONALLY, while
            # the candidate expression below is gated on a free slot — so a
            # FULL book evaluates those fields on coins the trading path would
            # never touch, which is exposure the book did not have before.
            #
            # An observability feature must never be able to stop the book:
            # this one sits upstream of the exit sweep, so an exception here
            # would skip position management for the whole cycle — telemetry
            # taking down trading, which is the inverse of why it was added.
            # Degrades to a zeroed census (every key present, so the log line
            # and `extra.scan` stay well-formed) and never to a partial dict.
            try:
                _cens = scan_census(fund, positions, hot_since, t0,
                                    _H, _enter_apr)
            except Exception:  # noqa: BLE001
                _cens = {"scanned": len(fund or {}), "held": 0, "thin": 0,
                         "cold": 0, "waiting": 0, "noncrypto": 0,
                         "eligible": 0, "error": "census failed"}

            # ---- scan for new carries ------------------------------------
            if len(positions) < MAX_POSITIONS:
                # [2026-08-05 (jr) S1] the allocation organ's capital scale,
                # NEW entries only — open positions keep the notional they
                # were opened at (same rule as the growth rail's clip). This
                # arm is shadow-only by construction (the HL arm exits at
                # boot; VENUE=lighter_shadow is the only mode that runs this
                # loop), so no real money can reach it. Dark bus -> 1.0.
                _alloc = (fleet_bus.allocation_scale(bot_id)
                          if fleet_bus is not None else None) or 1.0
                _notional = NOTIONAL * _alloc
                candidates = sorted(
                    ((c, f) for c, f in fund.items()
                     if c not in positions and f["vol"] >= MIN_DAY_VOLUME
                     and abs(f["rate"] * _H) >= _enter_apr
                     and (t0 - hot_since.get(c, t0)) >= PERSIST_H * 3600.0
                     and _class_ok(c)),      # [(lk)] crypto perps only
                    key=lambda cf: -abs(cf[1]["rate"]))
                for coin, f in candidates[:MAX_POSITIONS - len(positions)]:
                    apr = f["rate"] * _H
                    side = "short_perp" if f["rate"] > 0 else "long_perp"
                    # Perp leg: short_perp opens with a SELL, long_perp with a BUY.
                    # In shadow this MEASURES the real book slippage (+logs it); in
                    # hl_paper it returns the modelled PERP_FEE. The hedge leg is
                    # always the modelled HEDGE_COST (it lives off-venue).
                    perp_open_cost, _ = _perp_leg_fill(
                        ctx, bot_id, coin, is_buy=(side == "long_perp"),
                        notional=_notional, mark=(f.get("mark") or 0.0))
                    positions[coin] = {
                        "side": side, "notional": _notional, "opened_ts": t0,
                        "accrued": 0.0,
                        "fees": perp_open_cost + HEDGE_COST * _notional,
                        "entry_apr": apr,
                    }
                    print(f"[{now_iso()}] OPEN {coin} {side} ${_notional:.0f} "
                          f"| funding {apr:+.1%} APR "
                          f"| hot {(t0 - hot_since.get(coin, t0)) / 3600.0:.1f}h "
                          f"| perp-leg cost ${perp_open_cost:.3f} "
                          f"({'measured' if ctx.mode != 'hl_paper' else 'modelled'})")

            # ---- publish snapshot ----------------------------------------
            open_pnl = sum(p["accrued"] - p["fees"] for p in positions.values())
            top = sorted(fund.items(), key=lambda cf: -abs(cf[1]["rate"]))[:3]
            try:
                store.publish(
                    bot_id, status="online",
                    equity=START_EQUITY + realized + open_pnl,
                    pnl_abs=realized,
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": "dry-run", "open_pnl": round(open_pnl, 2),
                           # [2026-07-30] the EFFECTIVE cap this loop is
                           # running, so the board can SEE saturation
                           # instead of inferring it from occupancy alone —
                           # and can tell "at the cap" from "at the cap it
                           # set itself last cycle".
                           # `_enter_apr`, NOT the raw module constant: the
                           # raw one is HL-denominated and main() is guarded
                           # against touching it (the 8x-basis defect). The
                           # board must see the bar this arm ACTUALLY gates on.
                           # [(lz)] `min_vol` rides here so
                           # `audit_book_overlap` can rule this book IN or OUT
                           # of a proposed gate's supply. THREE books now enter
                           # at ~20% TRUE / $2M / crypto-only and the venue's
                           # whole crypto population at that bar is 3 coins —
                           # unpublished, the collision is undetectable.
                           # [2026-08-17 (pf)] `crypto_only` is the OTHER HALF
                           # of that same gate, and (lz) stopped one field
                           # short of it. `(lk)` gave this book `_class_ok` on
                           # 13-Aug and nothing published the narrowing, so
                           # every downstream reader had to ASSUME it: the
                           # daily review found 9 of this book's 10 era-scoped
                           # closes (−$14.96 of −$15.45, driving t=−4.48 and
                           # an `unreachable` horizon) were SKHYNIXUSD/SPCX/WTI
                           # — instruments this gate has refused for four days
                           # — and had to derive that by hand. A book that has
                           # narrowed its own universe must publish the
                           # narrowing, or a stale losing grade is
                           # byte-identical between "the screen is working" and
                           # "the book is broken" (I1's shape, one level up).
                           # The two books BORN with the screen (🧮 Hull,
                           # 🏦 Rich Dad) publish exactly this; the two that had
                           # it RETROFITTED did not. Guarded by
                           # tests/autonomy/test_class_screen_declared.py.
                           "caps": {"max_positions": MAX_POSITIONS,
                                    "enter_apr": _enter_apr,
                                    "min_vol": MIN_DAY_VOLUME, "max_vol": None,
                                    "crypto_only": not ALLOW_NONCRYPTO,
                                    # [(pr)] the exit gate publishes like the
                                    # entry gate ((lz)/(pf) doctrine)
                                    "flip_grace_h": FLIP_GRACE_H},
                           # [2026-08-02] THE BOOK NAMES ITS OWN BINDING
                           # CONSTRAINT. `scan` answers "why did nothing
                           # open?" in one glance instead of an investigation
                           # across this bot's state key, the scout's `vols`
                           # and the source. See the census block above.
                           "scan": _cens,
                           # [2026-07-30 (ho)] SOLE-WRITER CHECK. Measured on
                           # THIS book: 14 overlapping same-pair positions and
                           # TWO distinct build stamps — `(gl)` deployed both
                           # `funding-carry` and `yield-harvester-shadow`
                           # because the repo could not say which owned the
                           # row, so both now write it. The ledger is a
                           # mixture of two independent books, which makes `n`
                           # meaningless for the fleet's ONLY go-live
                           # candidate. Advisory and fail-OPEN: it reports,
                           # it never halts. Stopping the duplicate service is
                           # a Railway act and therefore the operator's.

                           # NOT "positions": the dashboard reserves that key for
                           # the stock bots' list-of-dicts holdings format.
                           "carries": {c: f"{p['side']}@{p['entry_apr']:+.0%}"
                                       for c, p in positions.items()},
                           # [2026-07-17] STAMP THE VENUE. fleet_risk.py:548 does
                           # `fc.get("venue") or "hyperliquid"` and this payload
                           # never carried the key — so the signal-bus labelled
                           # the LIGHTER arm's rates "hyperliquid", a hardcoded
                           # default asserting a venue nobody measured. Same rule
                           # the fleet shipped twice today for VENUE/TT_VENUE: a
                           # default is fine for a preference, never for an
                           # IDENTITY. With the key present the `or` never fires.
                           "venue": _venue_of(_mode),
                           "funding_basis_periods_per_year": _H,
                           "hottest_funding_apr": {
                               c: f"{f['rate']*_H:+.1%}" for c, f in top}},
                )
                # [2026-07-31 (hq)] MTM EQUITY SERIES. (hl) shipped
                # `snapshot_equity` because the go-live drawdown bar reads
                # REALISED closed P&L only, and named THIS book as the one to
                # re-grade under MTM first — carry is five of six bars from the
                # gate, so a stricter drawdown definition lands on it before
                # anyone else. It then wired the two RIDERS and not this book,
                # so the series it deferred the decision for was never
                # accruing here. Measured 31-Jul: `bot_state_history` held
                # ':equity' for exactly `crypto-trend-daily-lshadow` and
                # `equities-regime-lshadow`. Publish-only; the grader is
                # unchanged until there is history to read.
                store.snapshot_equity(bot_id, START_EQUITY + realized + open_pnl,
                                      len(positions), realized)
            except Exception:
                pass

            # [2026-07-03 PERSIST] Durable open-carry state -> Postgres.
            try:
                # [2026-08-03 (iu)] `saved_ts` is what makes the hot-streak
                # clock restorable AT ALL — `restore_hot_since` fails closed
                # without it, so omitting it here would silently reduce the
                # book to a fresh PERSIST_H wait on every boot.
                store.save_state(bot_id, {"positions": positions, "hot_since": hot_since,
                                           "last_ts": last_ts,
                                           "saved_ts": time.time()})
            except Exception:
                pass

            held = ", ".join(f"{c}({p['side'][0]})" for c, p in positions.items()) or "none"
            # [2026-08-02] The census goes in the LOG too, not only the row.
            # A quiet book is read from its logs first, and "scan ok | 217
            # perps" is indistinguishable between a healthy wait and a stall.
            _why = (f"cold {_cens['cold']}, thin {_cens['thin']}, "
                    f"waiting {_cens['waiting']}, "
                    f"noncrypto {_cens.get('noncrypto', 0)}, "
                    f"eligible {_cens['eligible']}")
            if _cens.get("next"):
                _why += f" | next {_cens['next']} in {_cens['next_eta_h']:.1f}h"
            print(f"[{now_iso()}] scan ok | {len(fund)} perps | open: {held} "
                  f"| open_pnl {open_pnl:+.2f} | realized {realized:+.2f} "
                  f"| {_why}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _selftest_basis():
    """[2026-07-17] The BEHAVIOUR-NEUTRALITY proof for the sixth-8x-bot fix, and
    a DETECTOR for the defect itself. The 31ec660 bar: the conversion AND every
    threshold denominated in it move by the same factor, so no decision changes.

    Mutation-checked — each of these must FAIL the suite:
      * `_venue_of` returning "lighter" for hl_paper  (inverts the bug)
      * dropping the `* _scale` on either threshold   (silently stops the arm)
      * `_hourly` reverting to a bare `rate`          (the 8x accrual)
    """
    import funding_basis

    # 1) the HL arm is UNTOUCHED — the bars are byte-identical to the constants
    H_hl, en_hl, ex_hl = _bars("hl_paper")
    assert H_hl == HOURS_PER_YEAR, H_hl
    assert en_hl == ENTER_APR and ex_hl == EXIT_APR, (en_hl, ex_hl)

    # 2) the LIGHTER arm is exactly 1/8 — and 8.0 is the defect's own signature.
    #    [2026-07-21] entry pin re-aimed at the NEW contract: ENTER_APR/8 with
    #    the default 1.60 -> 0.20 TRUE (the gate-sweep verdict, see the
    #    constant). The RATIO is the invariant this proof defends, so the pin
    #    tracks ENTER_APR rather than a literal — a dropped `* _scale` still
    #    fails it at any default.
    H_lt, en_lt, ex_lt = _bars("lighter_shadow")
    assert H_lt == 3 * 365, H_lt
    assert HOURS_PER_YEAR / H_lt == 8.0, "the 8x is exactly 8760/1095"
    assert abs(en_lt - ENTER_APR / 8.0) < 1e-12 and ex_lt == 0.01875, \
        (en_lt, ex_lt)
    assert abs(en_lt - 0.20) < 1e-12, \
        "shipped default: 1.60 published = 20% TRUE (backtest_carry_gate_lighter)"

    # 3) THE PROOF: every gate decides IDENTICALLY on both arms, for every rate.
    #    Uses _bars() — the SAME call main() makes — so dropping the rescale at
    #    the call site fails here. (My first cut re-derived `ENTER_APR * scale`
    #    inline and therefore could NOT fail on that mutation.)
    rates = [0.0, 1e-9, 1e-6, 1.2493e-05, 4.5e-5, 4.5662e-5, 9.6e-5, 1e-4,
             1e-3, 5e-3, -1e-6, -9.6e-5, -1e-3, 0.0456621, 1.0]
    for mode in ("hl_paper", "lighter_shadow"):
        H, enter_bar, exit_bar = _bars(mode)
        for r in rates:
            assert (abs(r * H) >= enter_bar) == (abs(r * HOURS_PER_YEAR) >= ENTER_APR), \
                f"ENTER gate flipped: mode={mode} rate={r}"
            assert (abs(r * H) < exit_bar) == (abs(r * HOURS_PER_YEAR) < EXIT_APR), \
                f"EXIT gate flipped: mode={mode} rate={r}"

    # 3b) THE CALL SITE, checked against executable code — because (3) proves the
    #     arithmetic and main() could still ignore it. Same technique as the
    #     17-Jul (c) storm-trigger check: read main()'s SOURCE, comments stripped,
    #     and assert no gate compares a raw-basis apr again.
    import inspect
    _src = [ln.split("#", 1)[0] for ln in inspect.getsource(main).splitlines()]
    _code = "\n".join(_src)
    assert "_H, _enter_apr, _exit_apr = _bars(_mode)" in _code, \
        "main() must derive its bars from _bars(_mode) — one owner"
    assert "HOURS_PER_YEAR" not in _code, (
        "main() must never touch the raw HL basis again — that constant is the "
        "defect. Every gate/accrual/publish goes through _H / _bars / _hourly.")
    for _bad in ("ENTER_APR", "EXIT_APR"):
        assert _bad not in _code, (
            f"main() must compare against _enter_apr/_exit_apr, never the "
            f"HL-denominated {_bad} — that is the 8x gate, rebuilt.")

    # 4) the ACCRUAL — the load-bearing half. HL unchanged; Lighter exactly /8.
    for r in rates:
        assert _hourly(r, "hl_paper") == r, \
            f"the HL arm's accrual MOVED: {r} -> {_hourly(r, 'hl_paper')}"
        assert _hourly(r, "lighter_shadow") == r * 0.125, r
    # ...and the venue is never defaulted onto the honest arm
    assert _venue_of("hl_paper") == "hyperliquid"
    assert _venue_of("lighter_shadow") == "lighter"
    assert funding_basis.DEFAULT_VENUE == "lighter", (
        "if this ever becomes 'hyperliquid', the bare-call trap inverts — but "
        "this file passes venue explicitly, which is why it does not care")

    # 5) an unknown/future mode must RAISE, never silently inherit a basis.
    #    A concurrent session removed hl_paper from main()'s allowlist the same
    #    night this landed (LIGHTER-ONLY) — so the allowlist is not a stable
    #    thing to lean on. If someone adds `lighter_live` tomorrow, this must
    #    stop them, not hand them Hyperliquid's basis and an 8x apr.
    for _bad_mode in ("lighter_live", "hl_live", "", None):
        try:
            _venue_of(_bad_mode)
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"_venue_of({_bad_mode!r}) must RAISE, not guess a basis — "
                f"a default here is an 8x apr wearing a venue name")

    print("funding_carry_bot _selftest_basis OK "
          "(hl arm bit-identical; lighter arm exactly /8; no gate flips)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest_basis()
        sys.exit(0)
    main()
