#!/usr/bin/env python3
"""
scripts/lighter_margin_model.py — ISOLATED-MARGIN LIQUIDATION MODEL for
Lighter perps. A MODEL for positions that do not exist, NOT a reader of ones
that do.

    python3 -m scripts.lighter_margin_model --selftest
    python3 -m scripts.lighter_margin_model --table   # live venue margin tiers

MODEL vs RECORD — READ THIS BEFORE USING EITHER (I14: a proxy is not the
record). Hours before this file was written, `(no)` wired the venue's OWN
margining truth into the live path: `venues/lighter_client.margin_state_from`
returns the real account's equity, gross, leverage, margin mode and the
VENUE-PUBLISHED liquidation price per position. Where both exist, THAT WINS —
this module must never be used to second-guess a liq price the venue itself
published for a real position.

They are complements, and `venues/base.margin_state`'s own docstring names the
gap this fills: *"a shadow/paper arm holds no venue account, so 'what leverage
am I at' has no venue-side answer there"*. A paper book and a backtest have no
account and no venue-published liq price, so the only way to price liquidation
for them is to MODEL it from the venue's published per-book margin tier. That
is this file, and its scope is exactly that: hypothetical positions.

VALIDATED FORWARD AGAINST THE VENUE, 2026-08-16 — to 0.001%, on independently
observed inputs, AND it corrected the model's caller convention in the process.
Read the confidence stratification before quoting it.

  THE TEST: the venue publishes `avg_entry_price` and `liquidation_price` for
  each live position. Feed the OBSERVED entry forward through `liq_price()` and
  compare. Nothing back-solved (see the retraction below for why that matters).
  Control: 💸 the Farmer's XAU short. entry 4339.72 · venue liq 32238.9162 ·
  mark 4386.935 · position value 30.2703 · total_asset 197.516986 ·
  collateral 197.843218 · mmf 0.0240.

      leverage basis                        L          predicted    error
      mark-notional  / total_asset_value    0.153254   31891.47     -1.078%
      entry-notional / total_asset_value    0.151605   32192.33     -0.145%
      entry-notional / COLLATERAL           0.151355   32238.50     -0.001%

  SO THE ISOLATED FORMULA IS CORRECT IN CROSS MODE — but the leverage that
  feeds it is **(size x avg_entry_price) / collateral**, an ENTRY-based
  notional over COLLATERAL. Use `cross_leverage()` below; do NOT hand this
  module `gross/equity`, which is wrong by 1.078% here.

  CONFIDENCE, STRATIFIED. Both free choices are now RESOLVED, by two different
  kinds of evidence — and the second was upgraded from "provisional" on
  2026-08-16 by a DIFFERENTIAL test, not by a better fit:
  * **entry-vs-mark notional: ESTABLISHED by MAGNITUDE.** The dominant term
    (mark/entry = 1.0109, a 1.088% effect); it moves the error from -1.078% to
    -0.145%, far outside any rounding.
  * **collateral-vs-total_asset: ESTABLISHED by MOTION.** These two
    denominators sit only 0.165% apart in LEVEL, which is why one snapshot
    could not separate them — but their MOTION differs by ~40x, and a
    differential test survives any constant offset. Three snapshots of the
    same XAU short, `entry` and `size` identical throughout:

        snap  collateral    total_asset   venue liq       coll err   total err
        T1    197.843218    197.516986    32238.916157    0.00000%   -0.14322%
        T2    197.843339    197.521799    32238.933282    0.00000%   -0.14116%
        T3    197.843339    197.522213    32238.933282    0.00000%   -0.14098%
        T4    197.843339    197.528768    32238.933282    0.00000%   -0.13810%

        T1->T2  observed +0.000053%   coll +0.000053%   total +0.002116%
        T2->T3  observed +0.000000%   coll +0.000000%   total +0.000182%   NULL
        T3->T4  observed +0.000000%   coll +0.000000%   total +0.002882%   NULL
        T2->T4  observed +0.000000%   coll +0.000000%   total +0.003064%   (composed)

    T4 is on a LATER BUILD, so this null also survives a redeploy — but the
    `total_asset` motion is PRICE-driven, not restart-driven: with `size`,
    `entry` and `collateral` byte-identical across T2/T3/T4 the identity
    `d_equity = -d_value` holds exactly (~1e-14), and `d_collateral` is
    identically zero. A container READS this state and cannot move it; T2->T3
    has the same shape and spans no restart at all. **T3->T4 is the citation to
    quote: same verdict as T2->T3 with 15.8x more room to have been wrong** —
    that factor is a ~4.1x longer window (8m27s -> 34m43s) times a bigger price
    move, the `position_value`-implied price falling 0.06 then 0.95 (a 15.83x
    ratio, which IS the 15.8x). Quote the IMPLIED price, not the `mark` field:
    the latter moves only 0.35 -> 0.86 (2.46x) and the two venue series differ
    by 0.06-0.17 here.

    TWO nulls and one positive: the liq moves exactly when collateral moves and
    holds exactly when collateral holds. T2->T4 is listed for completeness but
    is NOT a third observation — collateral is byte-identical at all three
    snapshots, so it is the arithmetic composition of the other two
    (0.000182% + 0.002882% = 0.003064%, exactly) and is forced given them.

    METHOD NOTE, learned by getting it wrong: **hold `size` and `entry` FIXED
    across snapshots.** A differential is meant to isolate the denominator, and
    T1 predates the published `size` field — letting it fall back to a derived
    `value/mark` (0.0069001022 vs the published 0.0069) pollutes the
    comparison and is the entire source of T1's -0.00129% forward residual
    under the derived convention. With size fixed at the published value all
    four snapshots are EXACT.

    **T2->T3 IS A NULL TEST AND IT REFUTES total_asset OUTRIGHT.** `value` and
    `total_asset` both moved (the mark ticked, unrealised P&L with it) while
    collateral did NOT — and the venue's liq did not move either, identical to
    ten significant figures (not literally byte-identical: the published doubles
    wobble by ~1 ULP, ~2.5e-16, immaterial here but worth saying exactly in a
    block that rests on nulls). A total_asset formula REQUIRED motion of
    +0.000182% and there was none. **Refuted by the absence, not disfavoured by
    a fit** — and corroborated in both directions: liq moved exactly when
    collateral moved (T1->T2) and held exactly when it held (T2->T3).
  * **FEED IT THE PUBLISHED `size`, NOT `value/mark`.** With the venue's own
    4-dp `size` the reproduction is EXACT (+0.0000%); deriving it as
    `value/mark` leaves -0.0013% — pure derivation error, not model error.
  * A CONSUMER TRAP VISIBLE IN A SINGLE ROW: at T3 `value` moved while `entry`,
    `size` and `liq` all held. **`value` breathes with the mark; the
    liquidation price does not**, because it is struck off ENTRY-based
    notional. Anyone reaching for `value` as the notional sees it drift under a
    stationary liq and will, reasonably, blame the model.
  * **STILL GENUINELY OPEN: one POSITION.** `gross/equity` and "this position's
    value/equity" stay numerically identical while the Farmer holds a single
    open position, so that pair is untested and needs a naturally-occurring
    second concurrent position. Not manufactured for telemetry.

  AND THIS IS WHAT THE EARLIER CIRCULAR CHECK HID: back-solving produced an
  entry of 4385.65 against an observed 4339.72. That **1.058% gap WAS the model
  error** — larger than the entire mmf term — and the inversion absorbed it
  invisibly. A forward test on an observed input surfaced it on the first try.

  HOW WE GOT HERE — kept because the failure mode recurs, not for narrative.
  This block briefly claimed "THE CALIBRATION HAS BEEN RUN, AND IT PASSES" on a
  reported 0.000000% match. **That result was CIRCULAR.** The entry it fed in
  was back-solved as `entry = liq*(1+mmf)/(1+1/L)` — the exact inverse of
  `liq_price` — so feeding it back is an algebraic identity: it returns
  0.000000% at L=9.9, at mmf=0.9, against a $1 liq. **A check that cannot fail
  is not a check**, and it arrived wearing the word "calibration" rather than
  looking like the I3 shape it was. An intermediate step then recovered the
  BASIS non-circularly (inverting the venue's liq through tier-level candidates
  demands entries of ~$31,000, impossible for gold), which correctly refuted
  tier-level leverage but could not reach the finer terms. Only the forward
  test on an OBSERVED entry, above, settled it — and it overturned the
  substitution the circular check had "confirmed".

  THREE LESSONS WORTH THE LINES:
  * a validation whose input is derived from its own target validates nothing;
  * the residual it hides is exactly the model error (1.058% here);
  * publish the observed input. `avg_entry_price` was read into the client's
    position record all along and never projected into the payload, which is
    precisely why the impossible check got substituted with a circular one.

  STILL OPEN: ONE POSITION. `gross/equity` and "this position's value/equity"
  stay numerically identical while the Farmer holds a single open position, so
  that pair is untested and needs a naturally-occurring second one.
  (This block previously read "STILL OPEN ... the collateral vs
  total_asset_value choice ... at n=1". That was superseded by the null test
  above and is corrected in place per I12 — it survived the upgrade for one
  commit and is exactly the self-contradiction this section exists to prevent.
  Settling it took a DIFFERENT KIND of evidence, not more n.)

WHY IT LIVES UNDER scripts/, DELIBERATELY. `bot_pnl_store._BUILD_SHARED` begins
with `"venues"`, so ANY file under `venues/` joins the build-stamp file set of
every image that COPYs it. Measured 2026-08-16: placing this module at
`venues/margin.py` moved 🧘 Douglas's stamp from `build_n=17` to `18` — a
fleet-wide re-stamp of ~22 images for a module none of them import, which
`audit_code_currency` would read as the whole fleet drifting (the (fd) trap).
Nothing in a container consumes this today, so it goes where `fleet_books.py`
went and for the same stated reason. If a levered book is ever built, moving it
into `venues/` is a DELIBERATE act with that stamp shift understood — never a
quiet import.

WHY THIS EXISTS (2026-08-16, the ⚡ High Voltage design, BAND_YOUNG_HIGH_VOLTAGE
_2026-08-16.md §4).

  `paper_broker.py` says so in its own docstring: *"MODEL (deliberately simple,
  cash-settled perps, LEVERAGE 1): equity = start + realized_pnl - fees +
  unrealized_pnl"*. There is no margin, no maintenance margin, no liquidation
  price and no liquidation EVENT anywhere in fleet code — the repo-wide grep for
  `update_leverage|margin_mode|initial_margin|liquidation` returned zero hits
  outside site-packages on the day this file was written.

  The absence has a CONTROL GROUP (I6), which is what makes it a finding rather
  than a gap: the installed SDK exposes `update_leverage(market_index,
  margin_mode, leverage)` (`site-packages/lighter/signer_client.py:1343`) and
  `venues/lighter_client.py` already calls a SIBLING METHOD on that same signer
  object for every real order. The fleet could always have read this; it never
  did, because at 1x nothing needed it.

  THE COST OF SHIPPING WITHOUT IT: a levered shadow book on today's broker will
  carry a position through a -$3,000 excursion on a $1,000 account and book the
  recovery. That is not a conservative shadow — it is a FICTION GENERATOR,
  publishing P&L a real account could never have earned because it was
  liquidated hours earlier. A book that cannot lose the way the real thing loses
  is not evidence at any leverage. So this module ships BEFORE any levered book.

THE VENUE PUBLISHES ITS OWN MARGIN TIERS — measured 2026-08-16 across all 210
active books on `/api/v1/orderBookDetails`, the endpoint `lighter_market_scout`
ALREADY FETCHES every loop:

    field                            min    med    max
    min_initial_margin_fraction      200   1000   3333
    default_initial_margin_fraction  500   1000   3333
    maintenance_margin_fraction      120    600   2000
    closeout_margin_fraction          80    400   1333

  * UNITS ARE PER-10000. Established by the DISTINCT-VALUE SET, not by
    assumption: min_initial_margin_fraction takes exactly
    {200, 333, 400, 500, 666, 1000, 1250, 2000, 3333}, which is
    10000/{50, 30, 25, 20, 15, 10, 8, 5, 3} — the venue's leverage tiers.
    A percent or a raw-fraction reading produces no such structure. The
    installed SDK divides the same fields by 10_000 independently
    (`site-packages/lighter/.../risk.py`).
  * TWO DIFFERENT `imf` FIELDS EXIST AND THEY ARE ON DIFFERENT SCALES — do not
    cross them. This module reads the MARKET-level tier
    (`min/default_initial_margin_fraction`, integer per-10000, so 200 = 2% =
    50x). The ACCOUNT-POSITION field that `venues/lighter_client` reads is a
    PERCENT, which is why `(no)`/`94d2cdf` derives its own `max_lev` as
    `100.0 / imf_pct` while this module uses `1.0 / min_imf`. Both give 50x on
    BTC and they are NOT interchangeable inputs.
  * THE TIERS ARE STRUCTURAL, NOT PER-BOOK TUNING: `mmf ~= 0.60 * min_imf` and
    `cmf ~= 0.40 * min_imf` hold on all 210 active books TO WITHIN THE VENUE'S
    OWN INTEGER ROUNDING (+/-1 per-10000 unit), and exactly on 207 of them.
    THE THREE EXCEPTIONS ARE REAL AND ARE THE REASON THIS RULE IS AN ALARM AND
    NEVER A SOURCE: OP and ARB publish mmf=399 where 0.6*666=399.6 rounds to
    400, and QQQ publishes mmf=199 where 0.6*333=199.8 rounds to 200 — while
    US100, WITH THE SAME min_imf OF 333, publishes 200. Two books, one tier,
    two different maintenance fractions. So a consumer that DERIVES mmf from
    min_imf is wrong on a real book today, which is why `parse_specs` reads the
    published field per book and `assert_tier_structure()` exists only to fire
    when the venue changes its scheme under a book that is sizing against it.
  * MAX LEVERAGE IS A HARD PER-COIN CAP: BTC/ETH 50x, SOL 25x, XRP/HYPE/BNB
    20x, most alts 10x, LIT/ETHFI/TAO 5x, the thinnest books 3x. A sizing rule
    that computes L=8 on ETHFI cannot open THAT SIZE. `size_for_risk` DOWNSIZES
    to the cap and NAMES it (`venue_max_leverage`) rather than refusing —
    an under-risked trade is not a dangerous one. But the clamped trade is no
    longer carrying the intended risk, so **an arm with a material clamp rate
    is no longer the constant-risk arm it claims to be**, and any consumer must
    report the rate rather than let it hide. (This paragraph previously said
    callers "must treat the clamp as a refusal, not a silent downsize", which
    the code has never done; corrected in place per I12 after an adversarial
    review caught the contradiction. The real defect it pointed at was the
    SILENCE, and that is fixed — every binding constraint is now named.)

FAIL-CLOSED, DELIBERATELY, AGAINST THIS REPO'S USUAL HABIT. Everywhere else in
the fleet a dark organ degrades to a neutral default. Here an unknown
maintenance fraction means "we cannot say where this position dies", and the
only safe answer at leverage is to REFUSE THE TRADE. `spec_for()` returns None
on any doubt and every consumer must read None as no-entry (I10's shape: the
cost of a wrong default is an unmodelled liquidation).

WHAT IS DECLARED UNKNOWN, rather than guessed (I8 — unknown degrades honestly):
  `liquidation_fee` reads '1.0000' on EVERY active book. The most plausible
  reading is ONE PERCENT OF NOTIONAL, which matters far more than it looks:
  charged on notional but paid out of margin, it costs L% OF POSTED MARGIN —
  20% of margin at 20x, 50% at 50x. It is therefore available as an explicit
  `liq_fee_pct_of_notional` charge, DEFAULT OFF, because the reading is not
  established: a percent reading leaves 0.2% against BTC's 1.2% maintenance,
  which sits below the published 0.8% closeout floor and so cannot be the whole
  mechanism. Turning it on moves the model in the CONSERVATIVE direction, which
  is why it is offered at all. Recovery otherwise comes from the venue's own
  published closeout fraction, with the residual ambiguity exposed as
  `RECOVERY_MODES` for sensitivity rather than buried in a constant.
  Interpreting `liquidation_fee` is an open question, not a solved one, and the
  live account's own `margin_state()` is where it would be settled.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")

#: this file, for the self-contradiction guard in the selftest.
_SELF_PATH = os.path.abspath(__file__)

#: the venue publishes margin fractions as integers per-10000 (see docstring).
FRACTION_SCALE = 10_000.0

def _frac_ok(x, lo=0.0, hi=1.0):
    """True only for a FINITE fraction strictly inside (lo, hi).

    NaN IS THE POINT. `nan <= 0` and `nan >= 1` are BOTH False, so the obvious
    guard `if mmf <= 0 or mmf >= 1` passes a NaN straight through — and this
    module then returns a NaN liquidation price, after which `check()` compares
    `mark <= nan`, gets False, and reports "ok". A fail-OPEN, inside the one
    module whose whole premise is failing closed. Found by its own selftest,
    2026-08-16; it is the I5 non-finite class arriving at a risk gate rather
    than at storage."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf")) and lo < f < hi


#: structural tier relationships, re-derived from live data by
#: assert_tier_structure(). Not used as constants — used as an ALARM.
TIER_MMF_OF_IMF = 0.60
TIER_CMF_OF_IMF = 0.40

#: how much of the posted margin a liquidated position gives back.
#:   "closeout" — the venue's own published closeout fraction is recovered.
#:               The DEFAULT and the honest reading of `closeout_margin_fraction`.
#:   "zero"     — nothing is recovered (harshest; the sensitivity bound).
#:   "maintenance" — the maintenance fraction is recovered (most optimistic;
#:               present only so a study can bracket the answer).
RECOVERY_MODES = ("closeout", "zero", "maintenance")


class MarginSpec:
    """One book's margin tier. Immutable-by-convention; all fractions are
    plain fractions (0.012), never the venue's per-10000 integers."""

    __slots__ = ("symbol", "market_id", "min_imf", "default_imf", "mmf",
                 "cmf", "liq_fee_raw")

    def __init__(self, symbol, market_id, min_imf, default_imf, mmf, cmf,
                 liq_fee_raw=None):
        self.symbol = symbol
        self.market_id = market_id
        self.min_imf = float(min_imf)
        self.default_imf = float(default_imf)
        self.mmf = float(mmf)
        self.cmf = float(cmf)
        self.liq_fee_raw = liq_fee_raw          # UNINTERPRETED — see docstring

    @property
    def max_leverage(self) -> float:
        """Hard venue cap. A position above this cannot be opened at all."""
        return 1.0 / self.min_imf

    def __repr__(self):
        return (f"MarginSpec({self.symbol} maxL={self.max_leverage:.0f}x "
                f"mmf={self.mmf:.4f} cmf={self.cmf:.4f})")


# --------------------------------------------------------------- venue read
def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def parse_specs(rows) -> dict:
    """orderBookDetails rows -> {symbol: MarginSpec}. Pure, so the selftest and
    any study can exercise it without a network call.

    A row missing ANY of the four fractions is DROPPED, not defaulted — an
    absent maintenance fraction is exactly the case where we must not guess."""
    out = {}
    for r in rows or []:
        if r.get("status") != "active":
            continue
        sym = r.get("symbol")
        try:
            min_imf = float(r["min_initial_margin_fraction"]) / FRACTION_SCALE
            def_imf = float(r["default_initial_margin_fraction"]) / FRACTION_SCALE
            mmf = float(r["maintenance_margin_fraction"]) / FRACTION_SCALE
            cmf = float(r["closeout_margin_fraction"]) / FRACTION_SCALE
        except (KeyError, TypeError, ValueError):
            continue
        # A degenerate tier is worse than a missing one: it would produce an
        # infinite max leverage or a liquidation price at the entry.
        if not sym or not _frac_ok(mmf) or not _frac_ok(min_imf) \
                or not _frac_ok(cmf):
            continue
        if cmf > mmf or mmf > min_imf:
            # closeout must sit below maintenance, which must sit below the
            # initial requirement. Anything else is a venue we do not understand.
            continue
        out[sym] = MarginSpec(sym, r.get("market_id"), min_imf, def_imf, mmf,
                              cmf, r.get("liquidation_fee"))
    return out


def fetch_specs(api=API) -> dict:
    """{symbol: MarginSpec} live from the venue. {} on any failure — callers
    must treat an empty map as 'cannot size at leverage', never as 'no limits'."""
    try:
        d = _get(api + "/api/v1/orderBookDetails")
    except Exception:  # noqa: BLE001 — 'no answer' is an answer here
        return {}
    return parse_specs((d or {}).get("order_book_details"))


def spec_for(specs, symbol):
    """FAIL-CLOSED accessor. None means REFUSE THE TRADE."""
    if not specs or not symbol:
        return None
    return specs.get(symbol)


def assert_tier_structure(specs, tol_units=1.0):
    """Re-derive the structural tier rule from live data and return the books
    that BREAK it. Empty list == the rule still holds.

    This is NOT a source of maintenance fractions and must never become one —
    3 of 210 live books disagree with the derived value by one unit (see the
    module docstring; QQQ and US100 share a tier and publish different
    maintenance fractions). It is the ALARM that fires when the venue changes
    its margin scheme under a book that is sizing against it.

    `tol_units` is expressed in the venue's OWN per-10000 integers, because
    that is the grid the published values live on — a tolerance in fraction
    space would be a tolerance in a unit the venue does not use, and picking
    one small enough to look strict is how the rounding noise above got
    mistaken for 39 broken books on this module's first run."""
    bad = []
    for s in specs.values():
        d_mmf = abs(s.mmf - TIER_MMF_OF_IMF * s.min_imf) * FRACTION_SCALE
        d_cmf = abs(s.cmf - TIER_CMF_OF_IMF * s.min_imf) * FRACTION_SCALE
        if d_mmf > tol_units + 1e-9 or d_cmf > tol_units + 1e-9:
            bad.append(s.symbol)
    return sorted(bad)


# ------------------------------------------------------------------- model
def liq_price(entry, is_long, leverage, mmf):
    """Isolated-margin liquidation price.

    Derivation (long; short is the mirror). Position equity at mark P is the
    posted margin plus unrealised P&L, and liquidation fires when that equity
    falls to the maintenance requirement on the CURRENT notional:

        M + q(P - P0) <= mmf * q * P,     M = N/L,  q = N/P0

      => P_liq = P0 * (1 - 1/L) / (1 - mmf)          [long]
         P_liq = P0 * (1 + 1/L) / (1 + mmf)          [short]

    Note the asymmetry is REAL and is not a rounding artifact: a short's
    maintenance requirement grows as the price runs against it, so its
    liquidation sits marginally closer than a long's at the same leverage
    (BTC 20x: long -3.85%, short +3.76%).

    Returns None if the inputs cannot define one (fail-closed)."""
    if not entry or entry <= 0 or not leverage or leverage <= 0:
        return None
    if entry != entry or leverage != leverage:      # NaN in, None out
        return None
    if not _frac_ok(mmf):
        return None
    inv = 1.0 / leverage
    if is_long:
        if inv >= 1.0:                    # <=1x long can never be liquidated
            return 0.0
        return entry * (1.0 - inv) / (1.0 - mmf)
    return entry * (1.0 + inv) / (1.0 + mmf)


def liq_distance_frac(is_long, leverage, mmf):
    """|P_liq - P0| / P0 — the adverse move a position survives. Scale-free, so
    a caller can compare it to a stop distance without knowing the price."""
    p = liq_price(1.0, is_long, leverage, mmf)
    if p is None:
        return None
    return abs(p - 1.0)


def headroom_x(is_long, leverage, mmf, stop_frac):
    """liq_distance / stop_distance — 'how many stops fit before the liq'.

    THE INVARIANT ⚡ High Voltage refuses on: headroom_x >= LIQ_HEADROOM_K (4).
    None (unknown mmf, absurd stop) is a REFUSAL, not a pass."""
    d = liq_distance_frac(is_long, leverage, mmf)
    if d is None or not stop_frac or stop_frac <= 0:
        return None
    return d / stop_frac


def max_leverage_for_headroom(is_long, mmf, stop_frac, k):
    """The largest leverage at which headroom_x >= k still holds.

    Solves d(L) >= k*s for L. For a long, d = 1 - (1-1/L)/(1-mmf), which gives
    L <= 1 / (1 - (1-mmf)(1 - k*s)); the short branch is the mirror.

    THREE OUTCOMES, DISTINGUISHED — and they must be, because they are not the
    same instruction (adversarial review, 2026-08-16). The first version
    returned a bare None for all three and `size_for_risk` read None as "no
    constraint", so the two REFUSAL cases FAILED OPEN, inside the module whose
    whole premise is failing closed:
      * float('inf') — every leverage clears the invariant. Never binds.
      * 0.0          — even 1x violates it (the stop sits at or beyond the
        liquidation). A REFUSAL: no size respects the invariant.
      * None         — the inputs cannot define it (unknown mmf, absurd stop).
        Also a REFUSAL, never a pass."""
    if not _frac_ok(mmf) or not stop_frac or stop_frac <= 0:
        return None
    if k is None or k <= 0 or k != k:
        return None
    target = k * stop_frac
    if is_long:
        denom = 1.0 - (1.0 - mmf) * (1.0 - target)
    else:
        denom = (1.0 + mmf) * (1.0 + target) - 1.0
    if denom <= 0:
        return float("inf")              # any leverage clears it
    lev = 1.0 / denom
    return lev if lev >= 1.0 else 0.0    # 0.0 == not satisfiable at any size


def cross_leverage(size, entry_price, collateral):
    """The leverage to feed `liq_price()` for a CROSS-margin account.

    `L = (size * avg_entry_price) / collateral` — an ENTRY-based notional over
    COLLATERAL. Validated forward against the venue's own published
    liquidation price to **0.001%** (see the module docstring for the table).

    WHY THIS EXISTS RATHER THAN LEAVING IT TO CALLERS: the intuitive input is
    `gross/equity`, and on the control position that is wrong by **1.078%** —
    larger than the whole maintenance term, so it cannot be tuned away. Two
    substitutions matter and they are NOT equally well established:
      * entry-based notional rather than MARK-based: strongly established,
        a 1.088% effect that moves the error from -1.078% to -0.145%.
      * collateral rather than total_asset_value: ESTABLISHED, by MOTION.
        They differ by only 0.165% in LEVEL, so a single snapshot could not
        separate them — but a NULL TEST did. Across three snapshots of one
        position, `total_asset` moved while `collateral` did not, and the
        venue's liquidation price did not move either (byte-identical to ten
        significant figures) where a total_asset formula REQUIRED +0.000182%.
        **Do not "fix" this back to total_asset_value** — that is the branch
        the venue's own behaviour refutes.

    Returns None on any doubt — the module-wide fail-closed contract."""
    try:
        s, e, c = float(size), float(entry_price), float(collateral)
    except (TypeError, ValueError):
        return None
    if not (s > 0 and e > 0 and c > 0):     # NaN fails this too
        return None
    lev = (s * e) / c
    return lev if lev > 0 else None


def check(entry, is_long, leverage, mmf, mark):
    """'ok' | 'liq' — evaluated on a LIVE mark, on the same loop as the stop.

    UNKNOWN IS 'liq'. A position whose liquidation price cannot be computed is
    a position whose risk cannot be evaluated, and at leverage the safe read of
    that is 'get out', not 'carry on' ((nm): a stop that is only checked when
    another endpoint answers is not a stop)."""
    p = liq_price(entry, is_long, leverage, mmf)
    if p is None or not mark or mark <= 0:
        return "liq"
    return "liq" if ((mark <= p) if is_long else (mark >= p)) else "ok"


def liquidation_pnl(notional, leverage, spec, mode="closeout",
                    liq_fee_pct_of_notional=0.0):
    """Realised P&L (a NEGATIVE number) when a position is liquidated.

    The trader posted margin M = notional/L and recovers `recovery` of the
    notional per the declared mode; the difference is the loss. Recovery is
    computed on the ENTRY notional rather than the notional at the liquidation
    price — a deliberate simplification in the CONSERVATIVE direction for a
    long (the liq notional is smaller, so real recovery is smaller still) and
    a ~mmf-sized optimism for a short, which is declared rather than modelled
    because the whole term is second-order beside M.

    NEVER returns a loss larger than the posted margin: isolated margin is the
    entire liability by construction, and a model that can lose more than the
    margin would overstate exactly the tail this engine exists to price."""
    if not notional or notional <= 0 or not leverage or leverage <= 0:
        return 0.0
    if mode not in RECOVERY_MODES:
        raise ValueError(f"unknown recovery mode {mode!r}")
    margin = notional / leverage
    if spec is None:
        recovery_frac = 0.0               # unknown tier -> assume total loss
    elif mode == "closeout":
        recovery_frac = spec.cmf
    elif mode == "maintenance":
        recovery_frac = spec.mmf
    else:
        recovery_frac = 0.0
    recovery = min(margin, recovery_frac * notional)
    if liq_fee_pct_of_notional:
        # Charged on NOTIONAL, paid out of MARGIN — so it costs L% of the
        # margin, not 1% of it. This is the term that makes high leverage
        # expensive to be wrong at, and it is off by default because the
        # field's units are not established (see the module docstring).
        recovery = max(0.0, recovery
                       - (liq_fee_pct_of_notional / 100.0) * notional)
    return -(margin - recovery)


def size_for_risk(equity, risk_pct, stop_frac, spec, k=4.0, notional_cap=None,
                  min_notional=None):
    """THE SIZING RULE, and the one place leverage is produced.

        R = risk_pct * equity ;  N = R / stop_frac ;  L = N / equity

    Leverage is an OUTPUT. It is then clamped by, in order:
      * the venue's own hard per-coin cap (`spec.max_leverage`),
      * the liquidation-headroom invariant (`k` stops must fit before the liq),
      * an absolute notional cap.

    Returns (notional, leverage, reason). `notional == 0.0` is a REFUSAL and
    `reason` names which gate refused — so a book that opens nothing can
    publish WHY at its own bar (I18), instead of an ambiguous {open: 0}."""
    if spec is None:
        return 0.0, 0.0, "no_margin_spec"
    if not equity or equity <= 0 or not risk_pct or risk_pct <= 0:
        return 0.0, 0.0, "no_equity"
    if not stop_frac or stop_frac <= 0:
        return 0.0, 0.0, "no_stop"

    # Every constraint is expressed as a candidate leverage and the BINDING one
    # is named. A clamp that does not say it bound is how an experiment
    # silently stops testing the thing it was built to test: at 1% risk on this
    # venue's median stop the notional cap binds, and the first cut of this
    # function applied it without a reason.
    cands = [("ok", (risk_pct * equity) / stop_frac / equity),
             ("venue_max_leverage", spec.max_leverage)]
    if notional_cap:
        cands.append(("notional_cap", notional_cap / equity))
    # Headroom is evaluated on the SHORT branch, which is the tighter of the
    # two (a short's liquidation sits marginally closer at the same leverage),
    # so a long can never be admitted at a leverage the binding branch refuses.
    lev_cap = max_leverage_for_headroom(False, spec.mmf, stop_frac, k)
    if lev_cap is None:
        # Cannot evaluate the invariant -> REFUSE. Reading this as "no
        # constraint" is the fail-open bug an adversarial review found here.
        return 0.0, 0.0, "liq_headroom_unknown"
    cands.append(("liq_headroom", lev_cap))

    reason, leverage = min(cands, key=lambda kv: kv[1])
    if leverage <= 0:
        return 0.0, 0.0, reason
    notional = leverage * equity
    if min_notional and notional < min_notional:
        return 0.0, 0.0, "below_min_notional"
    return notional, leverage, reason


# ---------------------------------------------------------------- selftest
def _selftest():
    # --- units and parsing -------------------------------------------------
    rows = [
        {"symbol": "BTC", "market_id": 1, "status": "active",
         "min_initial_margin_fraction": 200, "default_initial_margin_fraction": 500,
         "maintenance_margin_fraction": 120, "closeout_margin_fraction": 80,
         "liquidation_fee": "1.0000"},
        {"symbol": "ETHFI", "market_id": 9, "status": "active",
         "min_initial_margin_fraction": 2000, "default_initial_margin_fraction": 2000,
         "maintenance_margin_fraction": 1200, "closeout_margin_fraction": 800,
         "liquidation_fee": "1.0000"},
        # dropped: inactive
        {"symbol": "DEAD", "status": "inactive", "min_initial_margin_fraction": 200,
         "default_initial_margin_fraction": 500, "maintenance_margin_fraction": 120,
         "closeout_margin_fraction": 80},
        # dropped: missing maintenance fraction -> must NOT be defaulted
        {"symbol": "NOMMF", "status": "active", "min_initial_margin_fraction": 200,
         "default_initial_margin_fraction": 500, "closeout_margin_fraction": 80},
        # dropped: closeout above maintenance -> a venue we do not understand
        {"symbol": "WEIRD", "status": "active", "min_initial_margin_fraction": 200,
         "default_initial_margin_fraction": 500, "maintenance_margin_fraction": 80,
         "closeout_margin_fraction": 120},
    ]
    specs = parse_specs(rows)
    assert set(specs) == {"BTC", "ETHFI"}, sorted(specs)
    assert abs(specs["BTC"].mmf - 0.012) < 1e-12, specs["BTC"].mmf
    assert abs(specs["BTC"].max_leverage - 50.0) < 1e-9, specs["BTC"].max_leverage
    assert abs(specs["ETHFI"].max_leverage - 5.0) < 1e-9
    assert assert_tier_structure(specs) == []

    # THE ROUNDING BOUNDARY, pinned with the REAL books that forced it. QQQ and
    # US100 share min_imf=333 and publish DIFFERENT maintenance fractions (199
    # vs 200) — one unit of venue rounding, not a broken tier. Both must pass;
    # two units out must not. The first cut of this guard used a tolerance in
    # fraction space and called 39 healthy books broken.
    real = parse_specs([
        {"symbol": "QQQ", "status": "active", "min_initial_margin_fraction": 333,
         "default_initial_margin_fraction": 333, "maintenance_margin_fraction": 199,
         "closeout_margin_fraction": 133},
        {"symbol": "US100", "status": "active", "min_initial_margin_fraction": 333,
         "default_initial_margin_fraction": 333, "maintenance_margin_fraction": 200,
         "closeout_margin_fraction": 133},
        {"symbol": "OP", "status": "active", "min_initial_margin_fraction": 666,
         "default_initial_margin_fraction": 666, "maintenance_margin_fraction": 399,
         "closeout_margin_fraction": 266},
    ])
    assert set(real) == {"QQQ", "US100", "OP"}, sorted(real)
    assert assert_tier_structure(real) == [], assert_tier_structure(real)
    assert real["QQQ"].mmf != real["US100"].mmf     # same tier, different mmf
    # ...and the engine must use each book's OWN published value, not the tier
    assert abs(real["QQQ"].mmf - 0.0199) < 1e-12
    assert abs(real["US100"].mmf - 0.0200) < 1e-12
    # two units out IS a finding
    two_off = parse_specs([
        {"symbol": "OFF", "status": "active", "min_initial_margin_fraction": 333,
         "default_initial_margin_fraction": 333, "maintenance_margin_fraction": 202,
         "closeout_margin_fraction": 133}])
    assert assert_tier_structure(two_off) == ["OFF"]

    # a venue tier change must be REPORTED, not silently absorbed
    broken = dict(specs)
    broken["X"] = MarginSpec("X", 0, 0.02, 0.05, 0.019, 0.008)
    assert assert_tier_structure(broken) == ["X"]

    # fail-closed accessor
    assert spec_for(specs, "NOPE") is None
    assert spec_for({}, "BTC") is None

    # --- liquidation price -------------------------------------------------
    # BTC at 20x: long dies 3.85% down, short 3.76% up (asymmetry is real).
    lp = liq_price(100.0, True, 20.0, 0.012)
    assert abs(lp - 100.0 * 0.95 / 0.988) < 1e-9, lp
    assert abs(lp - 96.1538) < 1e-3, lp
    sp = liq_price(100.0, False, 20.0, 0.012)
    assert abs(sp - 100.0 * 1.05 / 1.012) < 1e-9, sp
    assert abs(sp - 103.7549) < 1e-3, sp
    assert liq_distance_frac(True, 20.0, 0.012) > liq_distance_frac(False, 20.0, 0.012)
    # unknown maintenance fraction cannot produce a price
    assert liq_price(100.0, True, 20.0, None) is None
    assert liq_price(100.0, True, 20.0, 0.0) is None
    assert liq_price(0.0, True, 20.0, 0.012) is None
    # 1x long is unliquidatable
    assert liq_price(100.0, True, 1.0, 0.012) == 0.0

    # --- check() -----------------------------------------------------------
    assert check(100.0, True, 20.0, 0.012, 97.0) == "ok"
    assert check(100.0, True, 20.0, 0.012, 96.0) == "liq"
    assert check(100.0, False, 20.0, 0.012, 103.0) == "ok"
    assert check(100.0, False, 20.0, 0.012, 104.0) == "liq"
    # UNKNOWN IS 'liq' — the whole point of fail-closed at leverage
    assert check(100.0, True, 20.0, None, 99.0) == "liq"
    assert check(100.0, True, 20.0, 0.012, None) == "liq"
    assert check(100.0, True, 20.0, 0.012, 0.0) == "liq"

    # --- the headroom invariant -------------------------------------------
    # At the design's own operating point (L~2.4, stop 0.41%) the liq is ~100
    # stops away: the COST arithmetic binds long before liquidation does, which
    # is the design's central claim and is pinned here so a future edit that
    # breaks it is loud.
    h = headroom_x(True, 2.4, 0.012, 0.0041)
    assert h > 90.0, h
    # at 50x on a 0.41% stop it is NOT satisfied
    h50 = headroom_x(True, 50.0, 0.012, 0.0041)
    assert h50 < 4.0, h50
    assert headroom_x(True, 2.4, None, 0.0041) is None      # refusal
    assert headroom_x(True, 2.4, 0.012, 0.0) is None

    # max_leverage_for_headroom must be the exact inverse of headroom_x
    for is_long in (True, False):
        for s in (0.002, 0.0041, 0.01, 0.03):
            lev = max_leverage_for_headroom(is_long, 0.012, s, 4.0)
            if lev is None or lev in (0.0, float("inf")):
                continue
            assert abs(headroom_x(is_long, lev, 0.012, s) - 4.0) < 1e-6, (
                is_long, s, lev, headroom_x(is_long, lev, 0.012, s))

    # THE THREE OUTCOMES ARE DISTINCT, and conflating them fails OPEN. The
    # first version returned a bare None for all three and size_for_risk read
    # None as "no constraint" — so a stop WIDER than the liquidation, which is
    # the one case the invariant exists to catch, sailed through unclamped.
    assert max_leverage_for_headroom(False, None, 0.01, 4.0) is None
    assert max_leverage_for_headroom(False, 0.012, 0.0, 4.0) is None
    # a stop so wide that even 1x breaches it -> 0.0, i.e. NOT SATISFIABLE
    assert max_leverage_for_headroom(False, 0.012, 0.40, 4.0) == 0.0
    # THE inf BRANCH IS UNREACHABLE WITH VALID INPUTS, and that is a fact
    # about the algebra worth pinning rather than a case to hope for: for a
    # short, denom = (1+mmf)(1+target) - 1 >= mmf > 0; for a long,
    # denom = 1 - (1-mmf)(1-target) > 0 since both factors are below 1. So the
    # headroom cap is always FINITE and bounded by ~1/mmf — a vanishing stop
    # buys ~83x on BTC, not infinity, because the maintenance fraction floors
    # it. The branch stays as a defensive guard; this pins what actually
    # happens so a future reader does not chase it.
    tight = max_leverage_for_headroom(False, 0.012, 1e-9, 4.0)
    assert tight != float("inf") and abs(tight - 1.0 / 0.012) < 0.01, tight
    # ...and size_for_risk must REFUSE on both refusal shapes, by name
    assert size_for_risk(1000.0, 0.01, 0.40, specs["BTC"],
                         k=4.0)[2] == "liq_headroom"
    # A NaN MAINTENANCE FRACTION MUST REFUSE, AND MUST SAY "UNKNOWN". Before
    # _frac_ok this returned a NaN liq price and check() read it as "ok".
    broken_spec = MarginSpec("B", 0, 0.02, 0.05, float("nan"), 0.008)
    assert size_for_risk(1000.0, 0.01, 0.006, broken_spec,
                         k=4.0)[2] == "liq_headroom_unknown"
    assert liq_price(100.0, True, 20.0, float("nan")) is None
    assert check(100.0, True, 20.0, float("nan"), 99.0) == "liq"
    assert headroom_x(True, 20.0, float("nan"), 0.01) is None
    assert liq_price(float("nan"), True, 20.0, 0.012) is None
    assert liq_price(100.0, True, float("nan"), 0.012) is None
    # ...and a venue row carrying a non-finite fraction is DROPPED, not parsed
    assert parse_specs([{"symbol": "NAN", "status": "active",
                         "min_initial_margin_fraction": float("nan"),
                         "default_initial_margin_fraction": 500,
                         "maintenance_margin_fraction": 120,
                         "closeout_margin_fraction": 80}]) == {}
    # an inf cap must not poison the min-over-candidates
    n_inf, lev_inf, why_inf = size_for_risk(1000.0, 0.01, 1e-6, specs["BTC"],
                                            k=4.0, notional_cap=1e9)
    assert why_inf == "venue_max_leverage" and \
        lev_inf == specs["BTC"].max_leverage

    # --- liquidation P&L ---------------------------------------------------
    btc = specs["BTC"]
    # 20x, $1000 notional -> $50 margin, recover cmf(0.8%)*1000 = $8 -> -$42
    l20 = liquidation_pnl(1000.0, 20.0, btc, "closeout")
    assert abs(l20 - (-42.0)) < 1e-9, l20
    assert abs(liquidation_pnl(1000.0, 20.0, btc, "zero") - (-50.0)) < 1e-9
    assert abs(liquidation_pnl(1000.0, 20.0, btc, "maintenance") - (-38.0)) < 1e-9
    # NEVER worse than the posted margin (isolated margin is the whole liability)
    for lev in (1.0, 2.0, 3.0, 50.0):
        loss = liquidation_pnl(1000.0, lev, btc, "closeout")
        assert loss >= -(1000.0 / lev) - 1e-9, (lev, loss)
        assert loss <= 0.0
    # THE LIQUIDATION FEE IS CHARGED ON NOTIONAL BUT PAID OUT OF MARGIN, so it
    # costs L% of the margin. Off by default; on, it is strictly more punitive.
    fee20 = liquidation_pnl(1000.0, 20.0, btc, "closeout",
                            liq_fee_pct_of_notional=1.0)
    assert abs(fee20 - (-50.0)) < 1e-9, fee20        # 1% of 1000 wipes the $8
    fee5 = liquidation_pnl(1000.0, 5.0, btc, "closeout",
                           liq_fee_pct_of_notional=1.0)
    assert abs(fee5 - (-200.0 + 0.0)) < 1e-9, fee5   # margin 200, recovery 8-10<0
    assert liquidation_pnl(1000.0, 3.0, btc, "closeout",
                           liq_fee_pct_of_notional=1.0) <= \
        liquidation_pnl(1000.0, 3.0, btc, "closeout")
    # ...and it can never make the loss exceed the posted margin
    for lev in (1.0, 2.0, 20.0, 50.0):
        assert liquidation_pnl(1000.0, lev, btc, "closeout",
                               liq_fee_pct_of_notional=1.0) >= \
            -(1000.0 / lev) - 1e-9

    # an unknown tier assumes TOTAL loss, never a comfortable default
    assert abs(liquidation_pnl(1000.0, 20.0, None, "closeout") - (-50.0)) < 1e-9
    try:
        liquidation_pnl(1000.0, 20.0, btc, "bogus")
        raise AssertionError("unknown recovery mode must raise")
    except ValueError:
        pass

    # --- THE FORWARD CALIBRATION, PINNED (observed inputs, nothing derived) --
    # 2026-08-16. This REPLACES a back-solved "0.000000%" triple that was
    # circular and verified nothing — the entry it used was computed as the
    # inverse of liq_price, so it could not fail. Every number below is read
    # off the venue: 💸 the Farmer's live XAU short.
    xau_entry, xau_liq, xau_mmf = 4339.72, 32238.9162, 0.0240
    xau_size, xau_coll = 30.2703 / 4386.935, 197.843218
    xau_size_pub = 0.0069          # the venue's OWN published size
    xau_tav, xau_mark = 197.516986, 4386.935
    lev = cross_leverage(xau_size, xau_entry, xau_coll)
    assert abs(lev - 0.151355) < 1e-5, lev
    pred = liq_price(xau_entry, False, lev, xau_mmf)
    assert abs(pred - xau_liq) / xau_liq < 2e-5, (pred, xau_liq)
    # THE FILE MUST NOT ARGUE WITH ITSELF. A peer review caught this module
    # claiming ESTABLISHED in its header and PROVISIONAL in `cross_leverage`'s
    # own docstring — the one a consumer actually reads, where the obvious
    # "fix" would have been to swap the denominator back to the branch the
    # null test refutes. Normally a substring assertion is not a wiring test;
    # here THE PROSE IS THE ARTEFACT, so checking the prose is the right
    # instrument. Guarded rather than merely corrected, per I12.
    # NOTE two earlier cuts of this guard were themselves defective, which is
    # the whole reason it is mutation-tested: the first read
    # `if "__file__" in dir()` (dir() returns LOCALS inside a function, so it
    # never ran), and the second scanned the raw file and tripped on its own
    # assertion message. It now walks DOCSTRINGS via ast — the claim lives in
    # prose, so prose is the right thing to check, and scoping it to
    # docstrings keeps the guard from reading its own code.
    import ast as _ast
    _doc_tree = _ast.parse(open(_SELF_PATH, encoding="utf-8").read())
    _docs = [_ast.get_docstring(_doc_tree) or ""]
    for _n in _ast.walk(_doc_tree):
        if isinstance(_n, (_ast.FunctionDef, _ast.ClassDef)):
            _docs.append(_ast.get_docstring(_n) or "")
    _live = "\n".join(
        ln for d in _docs for ln in d.splitlines()
        if "previously read" not in ln and "corrected in place" not in ln)
    assert "PROVISIONAL" not in _live, (
        "the collateral term is ESTABLISHED by the null test; a live "
        "PROVISIONAL claim in a docstring contradicts it and invites a "
        "consumer to revert the denominator")
    # ...and the POSITIVE half, added after a reviewer noted the check above
    # tests the VOCABULARY and not the CLAIM: a rewrite hedging it as "not yet
    # firmly established" would pass a word-ban. Requiring the current claim
    # to be PRESENT closes that — the two assertions together mean the file
    # must say this and must not say the old thing.
    assert "ESTABLISHED, by MOTION" in _live, (
        "cross_leverage must state the collateral term as ESTABLISHED, by "
        "MOTION — a reworded hedge passes a word-ban but not this")

    # THE NULL TEST, pinned — the strongest single artifact here. Three
    # snapshots of the same position; between T2 and T3 `total_asset` MOVED
    # (+0.000210%) while `collateral` did not, and the venue's liq did not
    # move either. A total_asset-denominated model is refuted by that absence.
    # T3->T4 is pinned rather than T2->T3: same NULL verdict, 15.8x the
    # magnitude total_asset would have had to move, and it spans a redeploy.
    T2_coll, T3_coll = 197.843339, 197.843339
    T2_tot, T3_tot = 197.521799, 197.528768        # T3_tot is T4's, the wider gap
    venue_liq_T2 = venue_liq_T3 = 32238.933282
    n_ent = xau_size_pub * xau_entry
    for coll, want in ((T2_coll, venue_liq_T2), (T3_coll, venue_liq_T3)):
        got = liq_price(xau_entry, False, n_ent / coll, xau_mmf)
        assert abs(got - want) / want < 1e-8, (got, want)
    # collateral predicts NO motion, and there was none
    a = liq_price(xau_entry, False, n_ent / T2_coll, xau_mmf)
    b = liq_price(xau_entry, False, n_ent / T3_coll, xau_mmf)
    assert a == b, "collateral was static; the model must predict no motion"
    # total_asset predicts motion that the venue did NOT show
    ta = liq_price(xau_entry, False, n_ent / T2_tot, xau_mmf)
    tb = liq_price(xau_entry, False, n_ent / T3_tot, xau_mmf)
    assert tb != ta, "the total_asset branch must predict motion here"
    assert abs(ta - venue_liq_T2) / venue_liq_T2 > 0.001, \
        "total_asset must visibly miss the venue's liq, or this pins nothing"

    # ...and the WRONG basis must visibly fail, or this pins nothing. The
    # intuitive gross/equity input is off by ~1.08%, which is larger than the
    # entire maintenance term — that is why a helper exists at all.
    bad = liq_price(xau_entry, False, 30.2703 / xau_tav, xau_mmf)
    assert abs(bad - xau_liq) / xau_liq > 0.010, bad
    # the entry-vs-mark choice is the DOMINANT term and must dominate here too
    mark_based = liq_price(xau_entry, False,
                           (xau_size * xau_mark) / xau_coll, xau_mmf)
    assert abs(mark_based - xau_liq) / xau_liq > 0.009, mark_based
    # fail-closed contract on the helper
    assert cross_leverage(0, xau_entry, xau_coll) is None
    assert cross_leverage(xau_size, xau_entry, 0) is None
    assert cross_leverage(float("nan"), xau_entry, xau_coll) is None
    # ...and the NEGATIVE control, which is the half that proves the model is
    # responsive rather than vacuous: 🙏 Avo sits at L=0.999, and a long at or
    # below 1x has NO liquidation price — only a path to worthlessness. So the
    # venue publishing nothing for those four longs is CORRECT, not a data gap.
    assert liq_price(100.0, True, 0.999, 0.012) == 0.0
    for lev, want in ((2.0, 0.494), (5.0, 0.190), (10.0, 0.089)):
        d = liq_distance_frac(True, lev, 0.012)
        assert abs(d - want) < 0.002, (lev, d, want)

    # --- the sizing rule ---------------------------------------------------
    # $1000 equity, 1% risk, 0.6% stop -> $1666 notional, L=1.67x
    n, lev, why = size_for_risk(1000.0, 0.01, 0.006, btc)
    assert abs(n - 1000.0 / 0.6) < 1e-6 and abs(lev - 1.6667) < 1e-3, (n, lev)
    assert why == "ok", why
    # leverage is an OUTPUT: halving the stop doubles it, at IDENTICAL risk
    n2, lev2, _ = size_for_risk(1000.0, 0.01, 0.003, btc)
    assert abs(lev2 - 2 * lev) < 1e-9, (lev, lev2)
    assert abs(n2 * 0.003 - n * 0.006) < 1e-9      # same dollar risk
    # A BINDING NOTIONAL CAP MUST SAY SO. Silently clamping here is how a
    # sizing experiment stops measuring its own sizing rule.
    n_c, lev_c, why_c = size_for_risk(1000.0, 0.01, 0.006, btc,
                                      notional_cap=600.0)
    assert why_c == "notional_cap", why_c
    assert abs(n_c - 600.0) < 1e-9 and abs(lev_c - 0.6) < 1e-9, (n_c, lev_c)
    # ...and a NON-binding cap must NOT claim to have bound
    assert size_for_risk(1000.0, 0.01, 0.006, btc, notional_cap=1e9)[2] == "ok"
    # the VENUE cap binds on a 5x book before anything else does
    ethfi = specs["ETHFI"]
    n3, lev3, why3 = size_for_risk(1000.0, 0.05, 0.002, ethfi)
    assert abs(lev3 - 5.0) < 1e-9 and why3 == "venue_max_leverage", (lev3, why3)
    # ...and the headroom invariant binds before the venue cap on a tight stop
    n4, lev4, why4 = size_for_risk(1000.0, 0.20, 0.0041, btc, k=4.0)
    assert why4 == "liq_headroom", why4
    assert abs(headroom_x(False, lev4, btc.mmf, 0.0041) - 4.0) < 1e-6
    assert lev4 < btc.max_leverage
    # refusals are NAMED, never a silent zero
    assert size_for_risk(1000.0, 0.01, 0.006, None) == (0.0, 0.0, "no_margin_spec")
    assert size_for_risk(1000.0, 0.01, 0.0, btc)[2] == "no_stop"
    assert size_for_risk(0.0, 0.01, 0.006, btc)[2] == "no_equity"
    assert size_for_risk(1000.0, 0.01, 0.006, btc, min_notional=1e9)[2] == \
        "below_min_notional"
    # a cap is applied BEFORE leverage is derived, so the two never disagree
    n5, lev5, _ = size_for_risk(1000.0, 0.01, 0.006, btc, notional_cap=600.0)
    assert abs(n5 - 600.0) < 1e-9 and abs(lev5 - 0.6) < 1e-9, (n5, lev5)

    # --- the engine must be able to FIRE (a guard that never fires is vacuous)
    # A planted 8% adverse intrabar at 20x MUST liquidate, not stop out at 1xATR.
    entry, stop = 100.0, 100.0 * (1 - 0.006)
    worst = 92.0
    assert check(entry, True, 20.0, btc.mmf, worst) == "liq"
    assert worst < stop                      # the stop was also breached...
    lp20 = liq_price(entry, True, 20.0, btc.mmf)
    assert worst < lp20 < stop               # ...but the LIQ came first
    print("scripts/lighter_margin_model.py selftest OK")
    return 0


def _table():
    specs = fetch_specs()
    if not specs:
        print("no live specs (venue unreachable) — fail-closed", file=sys.stderr)
        return 1
    bad = assert_tier_structure(specs)
    print(f"{len(specs)} active books; tier-structure violations: {bad or 'none'}")
    print(f"{'sym':<10}{'maxL':>7}{'mmf%':>8}{'cmf%':>8}"
          f"{'liq@2.4x':>10}{'liq@10x':>9}")
    for s in sorted(specs.values(), key=lambda x: -x.max_leverage)[:24]:
        d24 = liq_distance_frac(True, min(2.4, s.max_leverage), s.mmf)
        d10 = liq_distance_frac(True, min(10.0, s.max_leverage), s.mmf)
        print(f"{s.symbol:<10}{s.max_leverage:>6.0f}x{s.mmf * 100:>8.2f}"
              f"{s.cmf * 100:>8.2f}{d24 * 100:>9.1f}%{d10 * 100:>8.1f}%")
    return 0


if __name__ == "__main__":
    if "--table" in sys.argv:
        sys.exit(_table())
    sys.exit(_selftest())
