"""[26-Aug] 🧮 HULL'S VOLUME FLOOR AND POSITION CAP MOVE AS A PAIR.

THE DIAGNOSIS THIS PINS, because the pairing only makes sense with it: the
book had ZERO closes in 13 days and was NOT stuck at the entry — 6 of 6 slots
filled, $480 deployed. Its EXITS are structurally unreachable. `EXIT_APR` is
0.035 and Lighter's crypto RESTING DEFAULT is 0.10512 TRUE, so a coin pinned
at the venue default can never decay under 3.5% and can never flip sign:
`decay_paid` and `liability_flip` are both dead by construction and
`max_hold` (504h) is the only exit that can fire. Its sibling 🌾 carry closes
104 times over the same tape because carry's `EXIT_APR` is 0.15, ABOVE the
pin. That is `test_the_exit_is_unreachable_under_the_venue_pin` below, and it
is the reason the cap is a throughput knob at all: with `max_hold` as the only
live exit, closes/30d is bounded by `min(supply, cap) / hold`.

So each half ALONE is measurably worse than doing nothing, which is why they
ship together and why this file reddens on a half-revert:
  * the FLOOR alone at cap 6 is a STEP BACK, +$1.90 -> +$1.66 per 30d — more
    supply competing for the same six slots displaces better-paying coins;
  * the CAP alone is provably INERT — only 5-6 crypto books sit in the
    shipped [$2M,$10M) tier, so supply and cap are at parity and cap
    6/8/9/10/12/14/16 replay BYTE-IDENTICAL.
  * the PAIR: 6.5 -> 12.0 closes/30d (+85%), mean +0.1507 -> +0.1393 (-8%),
    t +2.18 -> +2.58, I16 lower bound +0.062 -> +0.070, $ALL/30d +$1.90 ->
    +$2.86 (+51%), both halves positive (+1.80/+1.55). I19: it costs 8% of
    per-trade expectancy and buys 51% more total dollars — TOTAL DOLLARS
    RISE, so it is not the (hl) denominator-shrinkage shape, and no exit was
    shortened.

Pinned here:
  1. the two shipped defaults, and that they are DERIVED from one declaration
     so a half-revert cannot arrive by editing one `os.environ.get` default;
  2. the pair moves together — a test that fails naming whichever half went
     back, with that half's own refusal number;
  3. `carry_exit` takes NO volume argument, so the widening is ENTRY-ONLY and
     the six open positions are untouched (no forced close, no era reset);
  4. the admitted candidate set at MIN_VOL 1e6 is a strict SUPERSET of the
     2e6 set on the same fixture — driven through the real `candidates`, not
     asserted about the constant;
  5. the census partition still sums to `scanned` at the new floor, and the
     coins that moved changed bucket in the ONE direction the floor allows
     (thin -> eligible, never the reverse);
  6. **the shipped pair REACHES the gate, and the cap actually BINDS** — see
     the mutation note below, which is the reason (6) exists at all.

[26-Aug, MUTATION ROUND] FOUR SURVIVORS, all one class, all on the CAP half.
The first round of this file killed every mutation of the two constants and of
their derivation, and then survived four mutations of the wiring that carries
them into the gate:

    candidates:  `return out[:max_n]`                 -> `return out`
    candidates:  `min_vol = MIN_VOL if min_vol is None`-> `... 2e6 if ...`
    candidates:  `max_n = MAX_POSITIONS if max_n is None` -> `... 6 if ...`
    scan_census: `min_vol = MIN_VOL if min_vol is None`-> `... 2e6 if ...`

Cause, and it is worth naming because it is I7 at the level of a TEST: every
call in this file passed `min_vol=` / `max_n=` explicitly, so **not one test
drove the call shape production actually runs** — `candidates(fund, held,
stable_since, t0, prem_map=..., max_n=free)` with the band UNPASSED, and
`scan_census(...)` with it unpassed too. The module constant could therefore
be pinned at 1e6 by tests 1 and 2 while the gate resolved 2e6 internally, and
this file would stay green: the exact half-revert its headline claims is
unreachable, reached one level lower. And `test_the_cap_binds_on_the_admitted_set`
was named for a cap that its own fixture (5 admissible coins against a cap of
10) could never make bind, so deleting the truncation outright changed nothing.
Both are closed below by driving the default path and by a fixture with MORE
supply than the cap.
"""
import ast
import inspect
import pathlib

import pytest

import lighter_book_hull_bot as hull

pytestmark = pytest.mark.autonomy

T0 = 1_785_600_000.0
H = hull.H

#: The shipped pair. Written out here ON PURPOSE rather than read from the
#: module: a test that reads the value it is pinning passes against any value.
SHIPPED_MIN_VOL = 1e6
SHIPPED_MAX_POSITIONS = 10

#: Why each half may not travel alone, in the message the failure prints.
_HALF_REFUSALS = {
    "MIN_VOL": ("the floor alone, at the old cap of 6, was MEASURED a step "
                "back: +$1.90 -> +$1.66 per 30d, because more supply "
                "competing for the same six slots displaces better-paying "
                "coins with worse ones"),
    "MAX_POSITIONS": ("the cap alone is provably INERT at the old "
                      "[$2M,$10M) tier: only 5-6 crypto books sit in it, so "
                      "supply and cap are at parity and cap 6/8/9/10/12/14/16 "
                      "replay byte-identical"),
}


def _f(apr, vol):
    """A funding row at a TRUE apr and a 24h volume."""
    return {"rate": apr / H, "vol": vol}


def _src():
    return pathlib.Path(inspect.getfile(hull)).read_text(encoding="utf-8")


def _env_default(name):
    """The literal-or-expression source of `os.environ.get("<name>", X)`.

    AST, not a substring scan: a page-wide `"1e6" in src` is green against a
    comment, and this file's whole job is to notice a half-revert.
    """
    for node in ast.walk(ast.parse(_src())):
        if not isinstance(node, ast.Call):
            continue
        # `os.environ.get` is Attribute(get) -> Attribute(environ) -> Name(os),
        # so a one-level `.value.id == "os"` check silently matches NOTHING —
        # it did on the first run of this file, and the only reason that was a
        # finding rather than a vacuous green is the raise below.
        if ast.unparse(node.func) != "os.environ.get":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if node.args[0].value != name:
            continue
        return ast.unparse(node.args[1]) if len(node.args) > 1 else None
    raise AssertionError(f"no os.environ.get({name!r}, ...) call in the module")


# ---------------------------------------------------------------------------
# 1 + 2. THE PAIR
# ---------------------------------------------------------------------------
def test_the_shipped_floor_and_cap_are_the_measured_pair():
    assert hull.HULL_BAND_PAIR == (SHIPPED_MIN_VOL, SHIPPED_MAX_POSITIONS)
    assert hull.MIN_VOL == SHIPPED_MIN_VOL
    assert hull.MAX_POSITIONS == SHIPPED_MAX_POSITIONS
    assert hull.MAX_VOL == 10e6, \
        "the CEILING did not move — [.., $10M) is 💸 the Farmer's edge (I20)"


@pytest.mark.parametrize("attr,shipped", [("MIN_VOL", SHIPPED_MIN_VOL),
                                          ("MAX_POSITIONS",
                                           SHIPPED_MAX_POSITIONS)])
def test_neither_half_may_travel_alone(attr, shipped):
    """Fails naming the half that went back, and its own refusal number."""
    live = getattr(hull, attr)
    assert live == shipped, (
        f"{attr} is {live!r}, not the shipped {shipped!r}. The floor (1e6) "
        f"and the cap (10) are ONE decision and neither may move without the "
        f"other: {_HALF_REFUSALS[attr]}. The pair together reads +85% closes, "
        "-8% mean, +51% total dollars, both halves positive. If this is a "
        "deliberate re-measurement, move HULL_BAND_PAIR (which moves both) "
        "and bring its numbers here.")


def test_both_defaults_are_derived_from_one_declaration():
    """A half-revert must not be reachable by editing one env default.

    The two `os.environ.get` defaults read from `HULL_BAND_PAIR`, so the only
    way to move one is to move the tuple — which moves both, and reddens the
    test above with its numbers. This is the (sa) rule: a value that must
    agree with another is DERIVED, never typed twice.
    """
    assert _env_default("HULL_MIN_VOL") == "str(HULL_BAND_PAIR[0])", \
        _env_default("HULL_MIN_VOL")
    assert _env_default("HULL_MAX_POSITIONS") == "str(HULL_BAND_PAIR[1])", \
        _env_default("HULL_MAX_POSITIONS")


# ---------------------------------------------------------------------------
# 3. ENTRY-ONLY — the open positions are untouched
# ---------------------------------------------------------------------------
def test_the_exit_rule_cannot_see_volume_so_open_positions_are_untouched():
    """`carry_exit(pos, apr, t0)` — no volume in, structurally.

    A signature check, not a prose promise: if a future edit gave the exit a
    volume term, a floor move would start CLOSING held positions and the
    widening would stop being entry-only. The same shape as `position_pnl`'s
    no-mark pin two functions down in the module.
    """
    params = list(inspect.signature(hull.carry_exit).parameters)
    assert params == ["pos", "apr", "t0"], params
    for p in params:
        assert "vol" not in p.lower()

    # and DRIVEN: a position whose coin is now below the floor still exits on
    # its own rule alone, with the floor moved under it.
    pos = {"coin": "A", "side": "short", "notional": 80.0,
           "opened_ts": T0 - 3600, "accrued": 0.0, "fees": 0.0}
    assert hull.carry_exit(pos, 0.105, T0) is None
    assert hull.carry_exit(dict(pos, accrued=1.0,
                                opened_ts=T0 - hull.MAX_HOLD_H * 3600 - 1),
                           0.105, T0) == "max_hold"


def test_the_widening_never_forces_a_held_coin_out():
    """A held coin is skipped by `candidates` at BOTH floors — the entry gate
    is the only consumer of volume, so a coin already in the book cannot be
    evicted by the band moving."""
    fund = {"HELD": _f(0.105, 1.5e6), "FREE": _f(0.11, 5e6)}
    aged = {c: T0 - (hull.STABLE_H + 1) * 3600 for c in fund}
    for floor in (2e6, 1e6):
        got = [c for c, _f_, _a in hull.candidates(
            fund, {"HELD"}, aged, T0, min_vol=floor, class_ok=lambda c: True)]
        assert "HELD" not in got, (floor, got)


# ---------------------------------------------------------------------------
# 4. THE ADMITTED SET IS A STRICT SUPERSET — driven, not asserted
# ---------------------------------------------------------------------------
def _band_fixture():
    """Coins spread across the OLD floor, so the two cells differ.

    Aprs are all in-band and DISTINCT so the ranking (hottest first) is
    deterministic and the `max_n` cap does not silently drop a coin the test
    is asking about.
    """
    lo, hi = hull.APR_LO_EFF, hull.APR_HI
    span = hi - lo
    fund = {
        "DEEP":   _f(lo + 0.90 * span, 8_000_000),   # both cells
        "MID":    _f(lo + 0.80 * span, 3_000_000),   # both cells
        "EDGE":   _f(lo + 0.70 * span, 2_000_000),   # both — floor is closed
        "SLIVER": _f(lo + 0.60 * span, 1_500_000),   # NEW cell only
        "ATNEW":  _f(lo + 0.50 * span, 1_000_000),   # NEW cell only, at floor
        "THIN":   _f(lo + 0.40 * span, 900_000),     # neither
        "ABOVE":  _f(hi * 1.5, 3_000_000),           # neither (carry's supply)
        "OVER":   _f(lo + 0.30 * span, 20_000_000),  # neither (Farmer's tier)
    }
    aged = {c: T0 - (hull.STABLE_H + 1) * 3600 for c in fund}
    return fund, aged


def _admitted(fund, aged, floor):
    return {c for c, _f_, _a in hull.candidates(
        fund, set(), aged, T0, min_vol=floor, max_n=len(fund),
        class_ok=lambda c: True)}


def test_the_new_floor_admits_a_strict_superset_of_the_old():
    fund, aged = _band_fixture()
    old = _admitted(fund, aged, 2e6)
    new = _admitted(fund, aged, hull.MIN_VOL)
    assert old < new, (old, new)          # strict subset: superset AND bigger
    assert new - old == {"SLIVER", "ATNEW"}, new - old
    assert old == {"DEEP", "MID", "EDGE"}, old
    # the ceiling and the apr band are untouched by the floor move
    assert "OVER" not in new and "ABOVE" not in new and "THIN" not in new


def test_the_floor_is_closed_and_the_ceiling_stays_half_open():
    """`vol >= MIN_VOL` admits and `vol >= MAX_VOL` refuses — the half-open
    tiling I20 requires, re-checked at the NEW floor because that is the edge
    that moved."""
    fund, aged = _band_fixture()
    new = _admitted(fund, aged, hull.MIN_VOL)
    assert "ATNEW" in new, "a coin exactly AT the floor is admitted"
    at_ceiling = {"CEIL": _f(hull.APR_LO_EFF * 1.5, hull.MAX_VOL)}
    aged2 = {"CEIL": T0 - (hull.STABLE_H + 1) * 3600}
    assert _admitted(at_ceiling, aged2, hull.MIN_VOL) == set(), \
        "a coin exactly AT the ceiling is the Farmer's — half-open (I20)"


def _oversupply_fixture(n=12):
    """MORE admissible coins than the cap, so the truncation actually BITES.

    `_band_fixture` admits FIVE coins against a cap of TEN, so every assertion
    about the cap there is satisfied by the FIXTURE rather than by the code —
    which is how `return out[:max_n]` -> `return out` survived the first
    mutation round of this file. A cap that cannot bind on the fixture is a cap
    the test never checked.

    Aprs descend in equal steps and are DISTINCT, so the rank order is
    deterministic and the truncation can be asserted by identity (which kills a
    sort inversion) and not merely by count. Volumes alternate across the NEW
    sliver [$1M,$2M) and the old [$2M,$10M) tier, so this supply is not
    reachable at the 2e6 floor either — the two halves of the pair are both
    load-bearing for the set that comes back.
    """
    lo, hi = hull.APR_LO_EFF, hull.APR_HI
    span = hi - lo
    fund, aged = {}, {}
    for i in range(n):
        frac = 0.95 - 0.05 * i                     # 0.95 .. 0.40, all in-band
        fund[f"C{i:02d}"] = _f(lo + frac * span,
                               1_500_000 if i % 2 else 3_000_000)
        aged[f"C{i:02d}"] = T0 - (hull.STABLE_H + 1) * 3600
    return fund, aged


def test_the_cap_binds_on_the_admitted_set():
    """The cap is the OTHER half, and it is what turns the extra supply into
    extra closes: where the admitted set exceeds the OLD cap, cap 6 throws the
    widening away at the door. Driven on a fixture that actually oversupplies —
    the previous one did not, and said so in this docstring anyway."""
    fund, aged = _oversupply_fixture()
    # The expected order is the FIXTURE'S, not the code's. Comparing `capped`
    # to an uncapped `candidates(...)` call reads like an identity check and is
    # not one: both sides come from the same sort, so they flip together and a
    # rank inversion survives — it did, in the second round of this file, in an
    # assertion written to catch exactly that.
    hottest_first = [f"C{i:02d}" for i in range(len(fund))]
    full = [c for c, _f_, _a in hull.candidates(
        fund, set(), aged, T0, min_vol=hull.MIN_VOL, max_n=len(fund),
        class_ok=lambda c: True)]
    assert full == hottest_first, full
    assert len(full) > hull.MAX_POSITIONS > 6, (
        "the fixture must OVERSUPPLY the cap or nothing here is a cap test")

    capped = [c for c, _f_, _a in hull.candidates(
        fund, set(), aged, T0, min_vol=hull.MIN_VOL,
        max_n=hull.MAX_POSITIONS, class_ok=lambda c: True)]
    # the cap truncates the TAIL of a hottest-first ranking: identity against
    # the fixture, so a lost truncation, an off-by-one and an inverted rank are
    # each a failure rather than a count that happens to match.
    assert capped == hottest_first[:hull.MAX_POSITIONS], capped

    at_old_cap = [c for c, _f_, _a in hull.candidates(
        fund, set(), aged, T0, min_vol=hull.MIN_VOL, max_n=6,
        class_ok=lambda c: True)]
    assert at_old_cap == hottest_first[:6], at_old_cap
    assert len(capped) - len(at_old_cap) == hull.MAX_POSITIONS - 6 > 0, (
        "at the OLD cap the supply the NEW floor admits is discarded at the "
        "door — that is why neither half of the pair travels alone")


# ---------------------------------------------------------------------------
# 6. THE PAIR REACHES THE GATE — production's own call shape, no overrides
# ---------------------------------------------------------------------------
def test_the_shipped_band_reaches_the_gate_with_no_override():
    """`main()` calls `candidates(fund, held, stable_since, t0, prem_map=...,
    max_n=free)` and `scan_census(fund, held, ..., prem_out=...)` — neither
    passes the band, so the DEFAULT resolution inside each function is the only
    path the shipped floor ever travels. Pinning the module constant does not
    pin that, and the mutation round proved it: `min_vol = MIN_VOL if min_vol
    is None else min_vol` -> `... 2e6 ...` was green in both functions.

    Only `class_ok` is passed, because the crypto screen is not what moved and
    the real one reaches the bus.
    """
    lo = hull.APR_LO_EFF
    fund = {
        "SLIVER": _f(lo * 1.10, 1_500_000),    # [$1M,$2M) — the cell the move added
        "TIER":   _f(lo * 1.20, 3_000_000),    # [$2M,$10M) — admitted at either floor
        "THIN":   _f(lo * 1.30,   900_000),    # below BOTH floors
        "DEEP":   _f(lo * 1.40, 12_000_000),   # at/above the ceiling: the Farmer's
    }
    aged = {c: T0 - (hull.STABLE_H + 1) * 3600 for c in fund}

    got = {c for c, _f_, _a in hull.candidates(
        fund, set(), aged, T0, class_ok=lambda c: True)}
    assert got == {"SLIVER", "TIER"}, got

    cen = hull.scan_census(fund, set(), aged, T0, class_ok=lambda c: True)
    assert (cen["eligible"], cen["thin"], cen["deep"]) == (2, 1, 1), cen


def test_the_shipped_cap_reaches_the_gate_with_no_override():
    """The cap half of the same wiring: with no `max_n`, `candidates` must
    resolve `MAX_POSITIONS` and TRUNCATE to it. Kills both `max_n = 6 if max_n
    is None` and the outright loss of `return out[:max_n]`."""
    fund, aged = _oversupply_fixture()
    got = hull.candidates(fund, set(), aged, T0, class_ok=lambda c: True)
    assert len(got) == hull.MAX_POSITIONS, [c for c, _f_, _a in got]


# ---------------------------------------------------------------------------
# 5. THE CENSUS STILL PARTITIONS, AND ONLY IN THE ALLOWED DIRECTION
# ---------------------------------------------------------------------------
def test_census_partitions_at_the_new_floor_and_moves_only_thin_to_eligible():
    fund, aged = _band_fixture()
    old = hull.scan_census(fund, set(), aged, T0, min_vol=2e6,
                           class_ok=lambda c: True)
    new = hull.scan_census(fund, set(), aged, T0, min_vol=hull.MIN_VOL,
                           class_ok=lambda c: True)
    for cen in (old, new):
        assert sum(v for k, v in cen.items() if k != "scanned") \
            == cen["scanned"] == len(fund)
    assert new["eligible"] == old["eligible"] + 2
    assert new["thin"] == old["thin"] - 2
    # a lower floor may ONLY move coins out of `thin`; every other bucket is
    # decided by an axis the floor does not touch.
    for bucket in ("below_band", "above_band", "deep", "waiting", "noncrypto",
                   "adverse_basis", "held"):
        assert new[bucket] == old[bucket], bucket


# ---------------------------------------------------------------------------
# THE DIAGNOSIS ITSELF — why the cap is a throughput knob here at all
# ---------------------------------------------------------------------------
VENUE_RESTING_TRUE_APR = 0.10512      # Lighter's crypto resting default


def test_the_exit_is_unreachable_under_the_venue_pin():
    """A position pinned at the venue's resting default can never satisfy the
    decay exit, and can never flip sign — so `max_hold` is the only exit that
    can fire. This is the whole reason the book had 0 closes in 13 days with
    6 of 6 slots full, and the reason slots are throughput.

    Driven through the REAL `carry_exit`, at the REAL constants.
    """
    assert hull.EXIT_APR < VENUE_RESTING_TRUE_APR, (
        f"EXIT_APR {hull.EXIT_APR} vs the venue pin {VENUE_RESTING_TRUE_APR}: "
        "if the exit bar ever rises ABOVE the resting default, `decay_paid` "
        "becomes reachable on a pinned coin and this book's throughput "
        "diagnosis changes — re-measure before moving the cap again.")

    pos = {"coin": "PIN", "side": "short", "notional": hull.CLIP_USD,
           "opened_ts": T0, "accrued": 0.0,
           "fees": (hull.SLIP_COST + hull.HEDGE_COST) * hull.CLIP_USD}
    # walk the whole max-hold window at the pin, accruing generously: no
    # decay_paid, no liability_flip, ever — only max_hold at the end.
    fired = []
    for hours in range(1, int(hull.MAX_HOLD_H) + 2):
        p = dict(pos, accrued=0.02 * hours)
        r = hull.carry_exit(p, VENUE_RESTING_TRUE_APR, T0 + hours * 3600.0)
        if r:
            fired.append((hours, r))
    assert fired, "something must eventually close the position"
    assert {r for _h, r in fired} == {"max_hold"}, fired
    assert fired[0][0] >= hull.MAX_HOLD_H, (
        "nothing may fire before the max hold on a pinned coin: "
        f"{fired[0]}")


def test_a_coin_off_the_pin_still_decays_out_normally():
    """The control arm for the test above — the exit is unreachable AT the
    pin, not broken. A rate that actually falls below `EXIT_APR` closes on
    `decay_paid` exactly as designed, so the diagnosis is about the venue's
    resting default and not about a dead code path."""
    fees = (hull.SLIP_COST + hull.HEDGE_COST) * hull.CLIP_USD
    pos = {"coin": "OFFPIN", "side": "short", "notional": hull.CLIP_USD,
           "opened_ts": T0, "accrued": 4 * fees + hull.PAYBACK_MARGIN,
           "fees": fees}
    assert hull.carry_exit(pos, hull.EXIT_APR / 2.0, T0 + 3600.0) \
        == "decay_paid"
    flip = {"coin": "FLIP", "side": "short", "notional": hull.CLIP_USD,
            "opened_ts": T0, "accrued": 0.0, "fees": fees}
    hull.carry_exit(flip, -0.105, T0)
    assert hull.carry_exit(flip, -0.105,
                           T0 + hull.FLIP_GRACE_H * 3600 + 1) \
        == "liability_flip"


def test_the_gross_stays_inside_the_book():
    """10 x $80 = $800 of a $1,000 book. Cap 12 measured BETTER (+$3.36 vs
    +$2.86) and was refused for exactly this: $960 leaves the book unable to
    fund its own worst case with any margin at all."""
    assert hull.CLIP_USD * hull.MAX_POSITIONS <= 0.80 * hull.START_EQUITY
    # and the delta-neutral worst case is the modelled round trip on every
    # slot — the drawdown number the widening is priced against.
    worst = hull.RT_COST_FRAC * hull.CLIP_USD * hull.MAX_POSITIONS
    assert worst / hull.START_EQUITY < 0.005, worst
