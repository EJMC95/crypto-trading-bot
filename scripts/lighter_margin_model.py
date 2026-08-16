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

The model has a free calibration route that should be taken before anyone
trusts it with real money: on the LIVE account, `margin_state()` publishes the
venue's own `liq` per open position, so `liq_price()` can be checked against it
directly. Until that check is run, treat this as an unvalidated model.

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
    A percent or a raw-fraction reading produces no such structure.
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
    that computes L=8 on ETHFI CANNOT OPEN. Callers must clamp with
    `max_leverage()` and treat the clamp as a refusal, not a silent downsize.

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

#: the venue publishes margin fractions as integers per-10000 (see docstring).
FRACTION_SCALE = 10_000.0

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
        if not sym or min_imf <= 0 or mmf <= 0 or mmf >= 1 or cmf <= 0:
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
    if mmf is None or mmf <= 0 or mmf >= 1:
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
    L <= 1 / (1 - (1-mmf)(1 - k*s)); the short branch is the mirror. Returns
    None when no leverage satisfies it (i.e. even 1x is inside the stop)."""
    if mmf is None or mmf <= 0 or mmf >= 1 or not stop_frac or stop_frac <= 0:
        return None
    if k is None or k <= 0:
        return None
    target = k * stop_frac
    if is_long:
        denom = 1.0 - (1.0 - mmf) * (1.0 - target)
    else:
        denom = (1.0 + mmf) * (1.0 + target) - 1.0
    if denom <= 0:
        return None                      # any leverage clears it
    lev = 1.0 / denom
    return lev if lev >= 1.0 else None


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
    if lev_cap is not None:
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
            if lev is None:
                continue
            assert abs(headroom_x(is_long, lev, 0.012, s) - 4.0) < 1e-6, (
                is_long, s, lev, headroom_x(is_long, lev, 0.012, s))

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
