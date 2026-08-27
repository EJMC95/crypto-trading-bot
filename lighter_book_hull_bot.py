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
       $80 × 10 slots, no leverage stacking, no top-ups.

THE SUPPLY, NAMED (I20 — measured before minting, 13-Aug; the floor CORRECTED
IN PLACE 26-Aug per I12, because the line below described a band this book no
longer trades):
  TRUE |apr| in [~7.8%, 20%) × 24h volume in [$1M, $10M), crypto only.
  This cell sits inside the fleet's volume tiling at the mid-band aprs:
    🛢️ Garrett  [0.1M, 2M)   @ >=5%  — thin tier
    🧮 Hull     [1M, 10M)    @ [7.8%, 20%)  — THIS BOOK
    💸 Farmer   [10M, inf)   @ >=5%  — deep tier (its floor excludes this)
  The tiling against 💸 the Farmer is still exact and half-open. Against 🛢️
  Garrett it is NOT any more: since 26-Aug this book's floor reaches into
  Garrett's band and the two contend for [$1M, $2M) × [7.82%, 20%) TRUE. That
  is a DECLARED overlap, not a discovered one — see `HULL_BAND_PAIR` below and
  the I20 note above `MIN_VOL`, and it is owed an entry in
  `audit_book_overlap.KNOWN_CELL_COLLISIONS` once the new gate publishes.
  The 20% CEILING hands everything above it to the carry cohort (🌾 carry and
  🏦 Rich Dad both enter at >=20% TRUE; ~~🎸 Barnesy's carry sleeve~~ RETIRED
  17-Aug (pm), and carry's own floor is $1M since (px) with a measured-depth
  fast path below that (sk) — corrected in place 26-Aug per I12, because the
  old "$2M" read as a volume separation this book must not rely on) —
  half-open on the APR axis, which is what actually keeps this book and the
  carry cohort apart: verified against `audit_book_overlap.cells_collide`
  itself, hull x carry does NOT collide at any volume.
  ~~ZERO living rivals admit this cell.~~ **[26-Aug — that is no longer true
  and the sentence is corrected rather than deleted, because it is exactly
  what the floor move cost: 🛢️ Garrett admits the [$1M, $2M) sliver of it.
  ONE rival, on a minority of each book's supply, and it is the paragraph
  four lines up.]** Live occupancy at authoring: LIT, ZEC,
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
    **[16-Aug (oo) — THE GRIMES STABILITY TEST APPLIED HERE, AND IT PASSES.]**
    After `(om)` fixed 📐 Grimes's gate (its verdict was decided by which
    coins happened to be liquid that day), the same question was put to this
    book. **It does not have Grimes's pathology, and the reason is precise:**
      - resampling the graded coin set moves `t` by a comparable amount —
        k=9 [+1.66,+4.73], k=12 [+2.00,+4.34], k=14 [+2.01,+4.55],
        k=16 [+3.07,+5.38] — so the SPREAD is not what distinguishes them;
      - what distinguishes them is WHERE THE BAR SITS. Grimes's distribution
        straddled its 0.5 bar (so the coin draw decided the verdict);
        Hull's sits ABOVE the go-live t=2.0 bar — **0 of 12 draws fall below
        it at k>=14, 1 of 12 at k=9/k=12**.
      - leave-one-out over all 18: t in **[2.67, 4.50]**, every value above
        2.0. No single coin carries the verdict (worst drop: PUMP -> 2.67).
    **THE TRANSFERABLE RULE, worth more than either book:** universe
    sensitivity is only a defect when the BAR FALLS INSIDE the verdict
    distribution. Measuring the spread alone would have called these two the
    same and been wrong.
    OUT-OF-UNIVERSE HOLDOUT, run and reported INCONCLUSIVE rather than as
    support: funding was fetched for the 8 crypto books with real history
    that the study never saw, giving n=48, +$2.02, **t=+0.57** — much weaker,
    and FARTCOIN alone is >100% of it. **But 0 of those 8 sit in the
    [$2M,$10M) band this book trades**, so that cell tests a population the
    rule structurally excludes. It REPLICATES the study's own already-recorded
    finding that the volume floor is LOAD-BEARING (their measurement on thin
    names: +$0.05). **A true out-of-band holdout does not exist** — inside
    [$2M,$10M) the venue's crypto population essentially IS the study's liquid
    names, the same thin-supply fact `(ly)` measured. Stated as a standing
    limitation, not resolved.
    MECHANICAL NOTE from the same run: with `MAX_POSITIONS=4`, adding 8 coins
    to the universe moved n by ONE (50 -> 49). A capped book's universe size
    changes WHICH trades are taken, not how many — so "grade a wider set" is
    not a free improvement here.
    **NO CODE CHANGED.** The `(om)` fix does not transfer: this book has no
    gate to fix, and the pathology that motivated it is absent.

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
    **[26-Aug — CORRECTED IN PLACE per I12: "it needs TIME" was the wrong
    diagnosis and waiting would not have fixed it.** The live book produced
    **ZERO closes in 13 days** while holding 6 of 6 slots with $480 deployed —
    not stalled at the entry, stalled at the EXIT. `EXIT_APR` (3.5%) sits
    BELOW Lighter's crypto resting default of 10.512% TRUE and every held coin
    sat exactly AT that pin, so `decay_paid` and `liability_flip` are both
    unreachable by construction and `max_hold` (504h) is the only exit that
    can fire. 6.0 closes/30d was a REPLAY number from a study whose coins
    moved off the pin; the live book's rate is bounded by `cap / max_hold`.
    That is what makes the cap and the volume floor ONE knob here, and it is
    why they moved together — see `HULL_BAND_PAIR` below.]**
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
#: [2026-08-20] 4 -> 6. This book's OWN declared binding bar is CLOSES, not
#: `t` — `(ny)` measured 6.0 closes/30d and ~5 months to the 30-close gate from
#: a standing start, and unlike 🧙 Schwager it needs TIME rather than a better
#: statistic. Measured today: it is AT its cap (held 4 of 4) with **11 books
#: in-band and liquid** (census: scanned 228, below_band 106, above_band 21,
#: thin 90), so the cap — not the gate — is what rations its evidence. Raising
#: it raises closes/30d roughly in proportion, which is I17 decidability
#: bought directly. It is NOT a risk widening in the expectancy sense (I19):
#: per-trade % is invariant to how many positions are held, the book is
#: delta-neutral MODELLED (P&L is accrued - fees, no price term), and 6 x $80
#: = $480 of a $1,000 shadow book stays inside the same gross envelope its
#: siblings run. The entry gate, band and exits are untouched.
#:
#: ==========================================================================
#: [2026-08-26] 6 -> 10, AND THE VOLUME FLOOR 2e6 -> 1e6, **AS A PAIR** —
#: NEVER EITHER ALONE. `HULL_BAND_PAIR` below is the executable form of that
#: sentence; `tests/autonomy/test_hull_band_widen.py` reddens if one reverts
#: without the other, because each half ALONE is measurably worse than doing
#: nothing (the numbers are three paragraphs down).
#:
#: THE DIAGNOSIS FIRST, because it is the real finding and it is NOT what the
#: (ny) note above assumed. This book has ZERO closes in 13 days and it is not
#: stuck: 6/6 slots filled, $480 deployed, the entry gate working exactly as
#: designed. **Its EXITS are structurally unreachable.** `EXIT_APR` = 0.035
#: sits BELOW Lighter's crypto RESTING DEFAULT of 0.10512 TRUE, and all six
#: held coins sit at exactly 10.512% — the pin. A rate PINNED at the venue
#: default cannot decay under 3.5% and cannot flip sign, so `decay_paid` and
#: `liability_flip` are both unreachable by construction and `max_hold`
#: (504h = 21 days) is the ONLY exit that can ever fire. Its sibling 🌾 carry
#: closes 104 times over the same tape because carry's `EXIT_APR` is 0.15,
#: ABOVE the pin — the same rule, on the other side of the same constant.
#: The band arithmetic says it too: this book's bar catches **4.2%** of the
#: venue's books, carry's catches **88.2%**.
#:
#: SO THE CAP AND THE FLOOR ARE ONE KNOB HERE. With `max_hold` as the only
#: live exit, a slot is occupied for up to 21 days, and CLOSES/30d is
#: therefore `min(supply, cap) / hold` — bounded by whichever of supply and
#: cap is SMALLER. At the shipped tier only 5-6 crypto books sit in
#: [$2M,$10M), so supply and cap are at PARITY and the cap alone is provably
#: INERT: replayed at cap 6/8/9/10/12/14/16 the shipped tier gives
#: BYTE-IDENTICAL ledgers. And the floor alone, at cap 6, is a STEP BACK
#: (+$1.90 -> +$1.66 per 30d) — more supply competing for the same six slots
#: displaces better-paying coins with worse ones. Only the pair moves.
#:
#: MEASURED (funding tape, both cells replayed through this book's own rules):
#:   shipped  [2M,10M) x cap 6 :  6.5 closes/30d, mean +0.1507, t=+2.18,
#:                                I16 lower bound +0.062, $ALL/30d +$1.90
#:   proposed [1M,10M) x cap 10: 12.0 closes/30d (+85%), mean +0.1393 (-8%),
#:                                t=+2.58, LB +0.070, $ALL/30d +$2.86 (+51%),
#:                                both halves positive (+1.80/+1.55)
#: I19 PRICE, STATED: it COSTS 8% of per-trade expectancy and BUYS 51% more
#: total dollars. That is not denominator shrinkage — the (hl) failure mode is
#: a trade count that rises while total dollars fall or hold; here TOTAL
#: DOLLARS RISE, and the hold is untouched (no exit was shortened).
#: PLATEAU, not a grid edge: cap 10/12/14 all read >= +$2.86 with a flat mean
#: and cap 12 peaks at +$3.36. **10 is chosen over the peak on purpose** — it
#: keeps gross at 10 x $80 = $800 of a $1,000 book rather than $960, so the
#: book still cannot deploy more than it holds.
#: DECIDABILITY (I17, the reason this is worth doing at all): 30 closes moves
#: from ~mid-Jan-2027 to ~mid-Nov-2026.
#: DRAWDOWN is not a concern and here is the arithmetic rather than the
#: assurance: delta-neutral MODELLED, so the worst case is every slot paying
#: the full modelled round trip and accruing nothing — 10 x $0.24 = $2.40 =
#: **0.24%** of the book against a 15% bar.
#: ENTRY-ONLY: `carry_exit` takes no volume argument (structurally — pinned by
#: the test), so the six OPEN positions are untouched, nothing is force-closed
#: and no (hc) era resets: this is capacity + supply, i.e. ordinary tuning.
#: ==========================================================================
#:
#: ONE DECLARATION FOR BOTH HALVES. The two defaults are DERIVED from this
#: tuple rather than written twice, so "the floor and the cap move together"
#: is a property of the code and not a sentence in a comment somebody has to
#: remember — the same reason `(sa)`'s confirm window is derived from the
#: study's own facts instead of typed as a literal. A future session that
#: wants to walk one half back has to edit this tuple, which moves both, and
#: `tests/autonomy/test_hull_band_widen.py` then names the refused half and
#: its number. `(min_vol_usd, max_positions)`.
HULL_BAND_PAIR = (1e6, 10)
MAX_POSITIONS = int(os.environ.get("HULL_MAX_POSITIONS",
                                   str(HULL_BAND_PAIR[1])))

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

# ---- the venue's RESTING FUNDING PINS — why the exits above are DEAD --------
# [2026-08-27 (vm)] `{eligible: 1}` is byte-identical between "quiet" and
# "structurally impossible", and this book has been publishing the second while
# reading as the first (I1/I18 at book scale). MEASURED 27-Aug: of its 11
# in-band coins **TEN sit at exactly the venue's resting funding default**, and
# a rate PINNED at that default is a CONSTANT — it cannot decay under
# `EXIT_APR` and it cannot change sign. So `decay_paid` and `liability_flip`
# are unreachable BY CONSTRUCTION on a pinned coin and `max_hold` (504h) is the
# only exit that can fire, which is the whole of the (26-Aug) diagnosis three
# blocks up. The row now says so every loop instead of leaving it in a comment.
#
# THE PINS ARE DERIVED, NEVER RETYPED ([[venue-resting-defaults-trap]], I12/(hj)
# — a retyped constant is a constant that drifts, and this one has two
# venue-specific values that already read 8x wrong once). What is written here
# is the venue's RAW per-period quote; the APR comes from the one basis
# authority, exactly as `H` does, so a basis change moves both together:
#   9.6e-05/8h -> 10.512% TRUE (crypto)   3.2e-05/8h -> 3.504% (non-crypto)
# The second is present because `HULL_ALLOW_NONCRYPTO` can admit that
# population; it is BELOW `EXIT_APR`, so a non-crypto pin is the one pin this
# book's decay exit CAN clear — which is exactly why the reachability report
# asks `carry_exit`'s own bar rather than assuming "pinned == dead".
RESTING_RATES = (9.6e-05, 3.2e-05)
RESTING_APRS = tuple(funding_basis.to_apr(r, "lighter") for r in RESTING_RATES)
#: absolute TRUE-apr tolerance for "sitting ON the pin". 1e-4 of apr is 0.01
#: percentage points — three orders below the 10.512% pin it separates, and
#: wide enough for the venue's own float rounding.
PIN_TOL = 1e-4

#: How many stored census rows a 24h window needs at THIS book's cadence, with
#: 50% headroom for restarts. `census_window`'s own default assumes a 30s loop
#: (~2,880 rows) and this book runs at 300s, so the default would fetch ~10x
#: what it can use every 5 minutes, forever. DERIVED from `LOOP_SECONDS` rather
#: than typed, so a cadence change carries the window with it ((sa)'s rule);
#: if it ever binds, `census_window` says so in `truncated` ((qz)) instead of
#: letting a sampled window read as an exhaustive one.
CENSUS_LIMIT = max(200, int(1.5 * 24 * 3600 / max(1.0, LOOP_SECONDS)))

# ---- the volume TIER [1M, 10M): completes Garrett|Hull|Farmer ---------------
# [2026-08-26] The floor moved 2e6 -> 1e6. It is the OTHER half of the pair
# declared at `HULL_BAND_PAIR` above — read that block for the diagnosis (the
# exits are unreachable under the venue's resting pin, so `max_hold` is the
# only live exit and slots are the throughput), the measurement (+85% closes,
# -8% mean, +51% total dollars, both halves positive) and the two REFUSED
# halves with their own numbers. The ceiling does NOT move: [.., 10M) is 💸
# the Farmer's edge and the tiling stays half-open (I20).
#
# THE I20 CONSEQUENCE, DECLARED rather than discovered by the guard: the new
# floor reaches DOWN into 🛢️ Garrett's published band [0.1M, 2M) @ >=5% TRUE,
# so Hull x Garrett now contend for [1M, 2M) x [7.82%, 20%) TRUE — a
# populated sliver of each book's supply, not the whole of either. That is a
# NEW declared cell collision for `audit_book_overlap.KNOWN_CELL_COLLISIONS`
# once this row publishes its new `caps.min_vol`; the audit reads the LIVE
# payload, so it cannot fire before the deploy and must not be silenced by
# pre-declaring against a gate that is not yet published.
MIN_VOL = float(os.environ.get("HULL_MIN_VOL", str(HULL_BAND_PAIR[0])))
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
                class_ok=None, prem_out=None):
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
        # [19-Aug (qi)] THE FALSIFIABILITY TAP. The 10bps adverse-basis veto
        # fired 0 times in its first 21d — and that zero was UNREADABLE:
        # retained premium history keeps only the scout's top-8 outliers
        # (cutoff median 17.9bps > the veto), so band-coin premiums were
        # visible in 1 of 5,580 candidate coin-snapshots. "0 fires" is
        # byte-identical between a slack bar and blind history — the (ly)
        # falsifiable-census principle applied to a gate. This records the
        # premium of every IN-BAND, class-admissible coin into the caller's
        # dict, so the row itself shows how close the band population runs
        # to the bar. Output-only: the census buckets are untouched (the
        # selftest pins their exact shape and partition).
        if prem_out is not None and apr_lo <= a < apr_hi and class_ok(c):
            _p = (prem_map or {}).get(c)
            if _p is not None:
                try:
                    prem_out[c] = round(float(_p), 2)
                except (TypeError, ValueError):
                    pass
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


def at_resting_pin(apr, tol=None):
    """Is |TRUE apr| sitting ON one of the venue's resting funding defaults?

    A pinned rate is not a quiet rate — it is a CONSTANT, and that is the
    difference between "nothing happened to close" and "nothing CAN". Absolute
    tolerance on the apr fraction; `None`/junk is NOT a pin (unknown degrades
    to the honest answer, never to a claim)."""
    t = PIN_TOL if tol is None else tol
    try:
        a = abs(float(apr))
    except (TypeError, ValueError):
        return False
    return any(abs(a - p) <= t for p in RESTING_APRS)


def pinned_count(fund, tol=None):
    """How many of the books this loop SCANNED are resting on a pin.

    The denominator for the exit-reachability report below: 10 of 11 in-band
    coins pinned is a structural fact about the supply, while 10 of 200 would
    be noise. Counts every scanned book, band or not — a coin's pin does not
    care which band it is in, and restricting the count to the band would hide
    a venue-wide freeze. Junk rows are skipped, never counted as un-pinned."""
    n = 0
    for f in (fund or {}).values():
        try:
            rate = float((f or {}).get("rate") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if at_resting_pin(rate * H, tol):
            n += 1
    return n


def exits_reachable(positions, fund, tol=None):
    """CAN THIS BOOK'S EXITS EVER FIRE ON WHAT IT HOLDS RIGHT NOW?

    [2026-08-27 (vm)] The row read `{held: 10, eligible: 1}` — supply-limited,
    plainly — and it was not: `EXIT_APR` (3.5%) sits BELOW the crypto resting
    pin (10.512%), so on a pinned coin `carry_exit`'s first two branches are
    dead letters and `max_hold` is the only exit that can fire. A count of
    positions (never coins), one per exit `carry_exit` can return, published
    every loop so the diagnosis is falsifiable from the payload: if the venue
    ever comes off its pin these numbers move on their own.

    Reachability is stated against `carry_exit`'s OWN bars — `EXIT_APR` for the
    decay leg and a sign change for the flip leg — and the claim is PINNED
    against the real rule by test (walk a pinned position past `FLIP_GRACE_H`
    with full payback accrued and `carry_exit` still returns only `max_hold`).
    That test is the guard: a future edit to `carry_exit`'s bars reddens it
    rather than silently making this report a second, stale copy ((hj)).

      decay_paid     -- |apr| can fall under EXIT_APR. A pinned coin can only
                        do that when the pin itself is under the bar (the
                        non-crypto 3.504% pin is; the crypto 10.512% one is
                        not), so this is NOT "pinned == dead" assumed.
      liability_flip -- the rate can change sign. A constant cannot.
      max_hold       -- a CLOCK, unconditional: reachable on every position
                        this book holds, which is precisely why it is the only
                        exit this book has been using.
      unpriceable    -- the coin published no readable rate this loop, so
                        nothing above is claimed for it (I1: unknown is its own
                        bucket, never folded into a zero).

    `held` is the denominator so `decay_paid: 0` is never read without it.
    Pure; decides nothing."""
    out = {"held": len(positions or {}), "decay_paid": 0,
           "liability_flip": 0, "max_hold": 0, "unpriceable": 0}
    for pos in (positions or {}).values():
        f = (fund or {}).get((pos or {}).get("coin"))
        try:
            apr = float((f or {}).get("rate") or 0.0) * H
        except (TypeError, ValueError, AttributeError):
            f = None
            apr = 0.0
        if f is None:
            out["unpriceable"] += 1
            continue
        out["max_hold"] += 1            # the clock runs on every held position
        pinned = at_resting_pin(apr, tol)
        if (not pinned) or abs(apr) < EXIT_APR:
            out["decay_paid"] += 1
        if not pinned:
            out["liability_flip"] += 1
    return out


def oldest_held_h(positions, now=None):
    """Hours the LONGEST-held position has been open, or None when flat.

    Beside `max_hold` = MAX_HOLD_H this is the whole throughput story of a book
    whose only live exit is a clock: it says how far the front of the queue has
    walked toward the only door it can leave by. None (never 0.0) when there is
    nothing held — a flat book makes no claim about its own age."""
    t = time.time() if now is None else now
    ages = []
    for pos in (positions or {}).values():
        try:
            ages.append((t - float((pos or {}).get("opened_ts"))) / 3600.0)
        except (TypeError, ValueError):
            continue
    return round(max(ages), 2) if ages else None


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


def build_state(positions, stable_since, stable_sign, last_ts, now=None,
                veto_fires=0):
    """The persistence blob — ONE builder so the selftest exercises the same
    payload main() saves. The stability clock rides the `hot_since` key so
    funding_basis.restore_hot_since (the (iu)-hardened restorer) owns the
    restore rule; the sign map rides beside it and is dropped whenever the
    clock is."""
    return {"positions": positions, "hot_since": stable_since,
            "stable_sign": stable_sign, "last_ts": last_ts,
            "veto_fires": int(veto_fires),   # (qi) survives restarts
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, open_pnl, realized,
                band_prems=None, veto_fires=0, prem_coverage=0,
                fund=None, census_24h=None, now=None):
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
                 "crypto_only": not ALLOW_NONCRYPTO,
                 # [2026-08-27 (vm)] THE EXITS, AND WHETHER THEY CAN FIRE.
                 # `max_hold_h` is published beside them because it is the
                 # clock the other two collapse onto once the venue pins:
                 # `oldest_held_h` / `max_hold_h` is then this book's entire
                 # throughput. `n_at_pin` is the supply-side denominator (of
                 # `scan.scanned`) that makes the reachability counts a
                 # measurement rather than an assertion.
                 "max_hold_h": MAX_HOLD_H,
                 "exits_reachable": exits_reachable(positions, fund),
                 "n_at_pin": pinned_count(fund),
                 "oldest_held_h": oldest_held_h(positions, now)},
        "scan": census,
        # [2026-08-27 (vm)] the census SUMMED over the trailing 24h — the
        # denominator a single loop's `{eligible: 1}` has never had. `None`
        # (never a zero-filled dict) when the history is dark or empty, which
        # is the whole contract of `census_window`: a fabricated zero reads as
        # "measured, nothing refused" when the truth is "no data" (I1).
        "census_24h": census_24h or None,
        # [19-Aug (qi)] the veto's falsifiability surface: the premiums of
        # every in-band admissible coin THIS loop (how close the population
        # runs to the 10bps bar), fetch coverage (0 = fetch failed, the
        # fail-OPEN dark case — distinguishable from "no band coins"), and
        # the cumulative loop-coin fire counter (persisted). All three keys
        # ALWAYS present — a key that appears only when it fires is the
        # ambiguity this exists to remove ((qg)).
        "basis": {"band_prems": dict(band_prems or {}),
                  "coverage": int(prem_coverage),
                  "veto_fires": int(veto_fires)},
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
                   # [(so)] I22 receipt: the brain scale this stake was sized
                   # at. Without it the notional column is the only trace and
                   # nobody can tell a brain move from a config change.
                   "brain_mult": pos.get("brain_mult"),
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
    veto_fires = 0      # (qi) cumulative adverse-basis loop-coin counts
    _saved = None
    try:
        # the CHECKED read ((jd)): a blip at boot must not seed empty
        # positions over the durable record.
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved and isinstance(_saved.get("positions"), dict):
            positions = _saved["positions"] or {}
        if _saved is not None:
            try:
                veto_fires = int(_saved.get("veto_fires") or 0)  # (qi)
            except (TypeError, ValueError):
                veto_fires = 0
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
            band_prems = {}
            census = scan_census(fund, held, stable_since, t0,
                                 prem_map=prem_map, prem_out=band_prems)
            # [19-Aug (qi)] cumulative veto counter — LOOP-COIN counts (a
            # coin sitting adverse for 10 loops counts 10), declared as
            # such; persisted so a restart cannot zero the record.
            veto_fires += int(census.get("adverse_basis") or 0)

            # ---- entries: take the receiving side of stable carry -------
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                for c, f, apr in candidates(fund, held, stable_since, t0,
                                            prem_map=prem_map, max_n=free):
                    side = "short" if apr > 0 else "long"
                    # [2026-08-20 (so)] the brain sizes this entry. The tag is
                    # composed from the SAME two parts record_close publishes
                    # (`<side>-basis_<exit>`), so the key looked up here and the
                    # key the brain buckets under cannot drift — a lookup on a
                    # tag the ledger never writes returns 1.0 forever, which is
                    # the registered-but-inert failure wearing a consumer's hat.
                    _clip, _bm = (fleet_bus.brain_clip(
                        bot_id, f"{side}-basis", CLIP_USD,
                        deployed_usd=sum(p.get("notional") or 0.0
                                         for p in positions.values()),
                        gross_cap_usd=fleet_bus.brain_gross_cap(MAX_POSITIONS,
                                                                CLIP_USD))
                        if fleet_bus is not None else (CLIP_USD, 1.0))
                    _open_position(positions, c, side, _clip, t0, apr,
                                   prem_bps=prem_map.get(c))
                    positions[c]["brain_mult"] = _bm
                    positions[c]["spread_bps_entry"] = live_spread_bps(ctx, c)
                    held.add(c)
                    print(f"[{now_iso()}] OPEN {c} {side} ${_clip:.0f}"
                          f"{'' if _bm == 1.0 else f' (brain {_bm:.2f}x)'} | "
                          f"{apr:+.1%} TRUE | payback "
                          f"{payback_hours(apr):.0f}h | prem "
                          f"{prem_map.get(c) if prem_map.get(c) is not None else '?'}bps")

            # ---- publish -------------------------------------------------
            open_pnl = sum(position_pnl(p) for p in positions.values())
            equity = START_EQUITY + realized + open_pnl
            # [2026-08-27 (vm)] accumulate FIRST, then read the window, so
            # this loop's refusals are inside the number the row publishes.
            # Both calls never raise (store contract) and neither gates
            # anything — publish-only, and it must stay that way.
            try:
                store.snapshot_census(bot_id, census)
                _cen24 = store.census_window(bot_id, hours=24,
                                             limit=CENSUS_LIMIT)
            except Exception:  # noqa: BLE001
                _cen24 = None
            extra = build_extra(census, positions, open_pnl, realized,
                                band_prems=band_prems, veto_fires=veto_fires,
                                prem_coverage=len(prem_map or {}),
                                fund=fund, census_24h=_cen24, now=t0)
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
                    positions, stable_since, stable_sign, last_ts, t0,
                    veto_fires=veto_fires))
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
    #    2e-4 -> 21.9% (above band); 5e-5 -> 5.5% (below).
    #    THE VOLUMES ARE DERIVED FROM THE SHIPPED BAND, not typed. This
    #    fixture read `"C": {"vol": 1e6}  # thin (< $2M)` until 26-Aug, when
    #    the floor moved to $1M and turned that coin ELIGIBLE while its
    #    comment still called it thin — a retyped constant is a constant that
    #    drifts, and this one drifted straight into the census PARTITION this
    #    selftest exists to pin. Deriving them makes the next band move
    #    re-classify the fixture with the book instead of against it.
    _mid = (MIN_VOL + MAX_VOL) / 2.0
    fund = {"A": {"rate": 1e-4, "vol": _mid},         # eligible
            "B": {"rate": -1.2e-4, "vol": MIN_VOL},   # eligible, hotter — and
                                                      # AT the floor, which is
                                                      # CLOSED (`vol < min`)
            "C": {"rate": 1e-4, "vol": MIN_VOL / 2.0},  # thin, below the floor
            "D": {"rate": 1e-4, "vol": MAX_VOL * 2.0},  # deep, the Farmer's
            "E": {"rate": 2e-4, "vol": _mid},         # above band (carry's)
            "G": {"rate": 5e-5, "vol": _mid},         # below band
            "N": {"rate": 1e-4, "vol": _mid}}         # noncrypto (screened)
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
    # [26-Aug] the floor and the cap are ONE decision (see HULL_BAND_PAIR):
    # each half alone was measured WORSE than shipping neither — the floor
    # alone +$1.90 -> +$1.66/30d, the cap alone byte-identical (inert).
    #
    # WHAT THIS ASSERT ACTUALLY CATCHES, corrected in place per I12 after a
    # mutation round measured it — it read "pins that the shipped defaults are
    # still DERIVED from the one tuple", which overstates in the direction that
    # matters. `MIN_VOL`/`MAX_POSITIONS` are DERIVED FROM the tuple, so
    # comparing them back to it is TRUE BY CONSTRUCTION for ANY tuple:
    # mutating `HULL_BAND_PAIR` to (2e6, 10) or (1e6, 6) — a half-revert, the
    # exact thing the sentence claimed — leaves this selftest GREEN. Measured,
    # not reasoned: 3 of 6 mutations survived this selector.
    # It catches ONE real thing, and that thing is worth keeping: a
    # de-derivation that CHANGES a value (`str(HULL_BAND_PAIR[0])` -> "2e6"),
    # i.e. the half-revert arriving through one `os.environ.get` default.
    # THE SHIPPED VALUES ARE PINNED IN `tests/autonomy/test_hull_band_widen.py`,
    # which writes 1e6 and 10 out as literals precisely so it does not read the
    # value it is pinning — that file kills the tuple edits, verified.
    if not os.environ.get("HULL_MIN_VOL") \
            and not os.environ.get("HULL_MAX_POSITIONS"):
        assert (MIN_VOL, MAX_POSITIONS) == HULL_BAND_PAIR, \
            "the volume floor and the position cap must move as a PAIR"
    # NON-TAUTOLOGICAL, and the arithmetic that chose cap 10 over the measured
    # peak of 12: whatever the tuple says, the book may not promise more gross
    # than it holds. Catches an UPWARD cap edit here, in the container, where
    # this selftest runs and pytest does not.
    assert CLIP_USD * MAX_POSITIONS <= 0.80 * START_EQUITY, \
        (f"{MAX_POSITIONS} x ${CLIP_USD:.0f} = "
         f"${CLIP_USD * MAX_POSITIONS:.0f} exceeds 80% of a "
         f"${START_EQUITY:.0f} book — cap 12 measured BETTER (+$3.36 vs "
         "+$2.86/30d) and was refused for exactly this reason")

    # 10b) [(vm)] THE PINS, AND THE EXITS THEY KILL. Runs in the CONTAINER,
    # where pytest does not — the same reason the cap arithmetic above lives
    # here. The claim is driven against `carry_exit` itself, never asserted:
    # a position on a crypto-pinned coin, walked past FLIP_GRACE_H with the
    # round trip fully repaid, still returns ONLY `max_hold`.
    _crypto_pin, _noncrypto_pin = RESTING_APRS
    assert abs(_crypto_pin - 0.10512) < 1e-9, _crypto_pin
    assert abs(_noncrypto_pin - 0.03504) < 1e-9, _noncrypto_pin
    assert EXIT_APR < _crypto_pin, \
        "the crypto pin is ABOVE the decay bar — that is the (vm) diagnosis"
    assert at_resting_pin(_crypto_pin) and at_resting_pin(-_crypto_pin)
    assert not at_resting_pin(APR_LO_EFF) and not at_resting_pin(None)
    _pinned = {"coin": "P", "side": "short", "notional": 80.0,
               "opened_ts": t0 - 3600, "accrued": 5.0,
               "fees": (SLIP_COST + HEDGE_COST) * 80.0}
    for _dt_h in (0.0, FLIP_GRACE_H + 1.0, MAX_HOLD_H - 2.0):
        assert carry_exit(dict(_pinned), _crypto_pin, t0 + _dt_h * 3600.0) \
            is None, "a pinned rate must reach NO exit before the clock"
    _pinned_old = dict(_pinned, opened_ts=t0 - (MAX_HOLD_H + 1) * 3600.0)
    assert carry_exit(_pinned_old, _crypto_pin, t0) == "max_hold", \
        "max_hold is the ONLY exit a crypto-pinned position can ever reach"
    _pin_rate = RESTING_RATES[0]
    _fund_pin = {"P": {"rate": _pin_rate, "vol": _mid},
                 "Q": {"rate": 3e-05, "vol": _mid}}     # Q well under the bar
    _rx = exits_reachable({"P": _pinned}, _fund_pin)
    assert _rx == {"held": 1, "decay_paid": 0, "liability_flip": 0,
                   "max_hold": 1, "unpriceable": 0}, _rx
    _rx2 = exits_reachable({"Q": dict(_pinned, coin="Q")}, _fund_pin)
    assert _rx2["decay_paid"] == 1 and _rx2["liability_flip"] == 1, _rx2
    _rx3 = exits_reachable({"Z": dict(_pinned, coin="Z")}, _fund_pin)
    assert _rx3 == {"held": 1, "decay_paid": 0, "liability_flip": 0,
                    "max_hold": 0, "unpriceable": 1}, \
        "a coin with no rate is UNPRICEABLE, never a reachable zero"
    assert pinned_count(_fund_pin) == 1, pinned_count(_fund_pin)
    assert oldest_held_h({}, now=t0) is None, "a flat book makes no age claim"
    assert oldest_held_h({"P": _pinned}, now=t0) == 1.0
    _ex_pin = build_extra(cen, {"P": _pinned}, 0.0, 0.0, fund=_fund_pin,
                          now=t0)
    assert _ex_pin["caps"]["n_at_pin"] == 1
    assert _ex_pin["caps"]["max_hold_h"] == MAX_HOLD_H
    assert _ex_pin["caps"]["exits_reachable"]["max_hold"] == 1
    assert _ex_pin["census_24h"] is None, "a dark window is None, never {}"

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
