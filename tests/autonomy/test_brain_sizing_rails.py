"""[(wo)] The two sizing rails in `fleet_bus.brain_clip_multi`, driven.

Eamon, 2-Sep: "Proceed with advisements." EDGE_AUDIT_2026-09-02.md §6 proposed
two rails and both live in the one accessor every book sizes through:

  * a DRAWDOWN SCALE — 1.0 all the way to the gate's bar, then linear to 0.25
    at TWICE the bar, read from the gate's OWN per-book `max_dd_pct` (fail-OPEN
    on a dark gate: an unmeasured drawdown is not a drawdown; inside the tested
    range nothing moves);
  * NEVER LEVER A WEAK EDGE — a multiplier above 1.0 is refused only when
    `fleet_allocation` has MEASURED the sized book's era bound at or below zero
    on >= LB_CAP_MIN_N era closes. Dark, thin, None or junk change nothing: the
    brain's own t>=2 bars govern, as they always did.

Eamon, 2-Sep, on the first cut: "make sure we don't constrict too much like we
have in the past, our focus always on growth." That cut scaled from HALF the
bar and refused expansion on a dark organ — both bit on an absence, not a
measurement — and was reshaped before it shipped.

Every payload here is built by the PUBLISHER's own functions where one exists
((hj): a consumer is tested against a payload its publisher built) —
`fleet_allocation.build` + `set_era_twin` for the claim, `golive_readiness.
book_payload` for the drawdown — so these pins cannot drift from the field
names the organs actually emit. Mutations verified red before this file was
committed: (1) drop the `want > base` guard (reductions get capped too),
(2) drop the cap entirely, (3) start the scale at half the bar instead of at
it, (4) read `max_dd_pct_realised` instead of the worse-of-both field,
(5) apply the rails before the gross trim (as a real block move), (6) remove
the probe floor, (7) ignore the kill switch, (8) drop the thin-era guard.
"""
import datetime as dt
import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import fleet_allocation as FA            # noqa: E402
import golive_readiness as GR            # noqa: E402

fb = importlib.import_module("fleet_bus")

BOT = "freqtrade-avo-maria-lshadow"
TAG = "long-swing-dip"


@pytest.fixture
def bus(monkeypatch):
    """Install brain + allocation + gate payloads through the accessor's own
    `_load`, and clear the resolved-mults memo so the brain payload is re-read."""
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    state = {"brain": None, "alloc": None, "gate": None}

    def _load(key, ct=None):
        return {"fleet-allocation": state["alloc"],
                "golive-readiness": state["gate"]}.get(key)

    monkeypatch.setattr(fb, "_load", _load)
    fb._cache.clear()
    fb._resolved_mults.update({"ent": None, "map": {}, "from": None, "until": None})
    monkeypatch.delenv("BRAIN_RAILS_MODE", raising=False)

    def brain(mult):
        # `_resolve_mults` reads the brain payload from `_cache` AFTER calling
        # `_load` — the real `_load` populates the cache, the fake one here does
        # not — so the brain is installed the way the live-sizing safety test
        # installs it: straight into `_cache`, memo cleared.
        payload = {"updated": stamp, "ttl_sec": 26000,
                   "mults": {BOT: {TAG: {"mult": mult}}}}
        state["brain"] = payload
        fb._cache["brain-stake-mults"] = {"ts": now, "payload": payload}
        fb._resolved_mults.update({"ent": None, "map": {}, "from": None, "until": None})

    def alloc(claim_era, n_era=None):
        """Publisher-built: `build` on a real series, then `set_era_twin` —
        the single writer of `claim_era` / `n_era` — so these pins cannot drift
        from the field names `run_once` actually publishes."""
        n = max(20, FA.MIN_N)
        series = [0.01 + 0.002 * ((i % 5) - 2) for i in range(n)]
        p = FA.build({BOT: series})
        n_era = FA.MIN_N if n_era is None else n_era
        if isinstance(claim_era, str):
            FA.set_era_twin(p["books"][BOT], n_era, 0.0)
            p["books"][BOT]["claim_era"] = claim_era      # junk the publisher would never write
        else:
            FA.set_era_twin(p["books"][BOT], n_era, claim_era)
        p["updated"] = stamp
        p["ttl_sec"] = 5400
        state["alloc"] = p

    def gate(dd_frac, bar=0.15):
        """Publisher-built: the gate's own `book_payload` over a `stats`-shaped
        dict carrying the worse-of-both drawdown fraction."""
        s = {"n": 40, "days": 30.0, "mean_pct": 0.004, "t": 2.5, "h1": 1.0,
             "h2": 1.0, "win_rate": 0.6, "max_dd_frac": dd_frac,
             "realised_usd": 10.0, "usd_per_day": 0.3, "mde80_pct": 0.5,
             "power_at_half_pct": 0.5, "maxdd_basis": "mtm"}
        row = GR.book_payload(s)
        state["gate"] = {"updated": stamp, "ttl_sec": 43200,
                         "bar": {"max_dd": bar}, "books": {BOT: row}}

    ns = type("Bus", (), {})()
    ns.now, ns.brain, ns.alloc, ns.gate, ns.state = now, brain, alloc, gate, state
    yield ns
    fb._cache.clear()
    fb._resolved_mults.update({"ent": None, "map": {}, "from": None, "until": None})
    fb.last_sizing.clear()


# ------------------------------------------------------------ lower-bound cap

def test_a_dark_allocation_organ_leaves_the_brains_measured_expansion_alone(bus):
    """The brain's expansion is already earned (n>=30 era closes, t>=2). A
    SECOND organ being dark must not undo it — a gap is not a measurement."""
    bus.brain(1.5)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5)
    assert fb.last_sizing[BOT]["lb_capped"] is False


def test_a_measured_zero_era_claim_refuses_expansion_and_passes_reduction(bus):
    bus.brain(1.5)
    bus.alloc(0.0, n_era=40)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (80.0, 1.0)
    assert fb.last_sizing[BOT]["lb_capped"] is True
    bus.brain(0.5)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (40.0, 0.5)
    assert fb.last_sizing[BOT]["lb_capped"] is False


def test_a_positive_era_claim_admits_the_expansion(bus):
    bus.brain(1.5)
    bus.alloc(0.001, n_era=40)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5)


def test_a_thin_era_decides_nothing(bus):
    """`claim_era` 0.0 on n_era below the computability floor is not a
    measured non-positive bound — it is a book that has not been measured
    yet, and the brain's own n>=30 floor already covers thinness."""
    bus.brain(1.5)
    bus.alloc(0.0, n_era=fb.LB_CAP_MIN_N - 1)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5)
    bus.alloc(0.0, n_era=fb.LB_CAP_MIN_N)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (80.0, 1.0)


@pytest.mark.parametrize("claim", [None, float("nan"), "junk"])
def test_a_none_nan_or_junk_claim_is_no_opinion_not_a_no(bus, claim):
    bus.brain(1.5)
    bus.alloc(claim, n_era=40)
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5), claim


def test_the_claim_field_is_the_publishers_era_twin_not_the_all_time_claim(bus):
    """The all-time `claim` can be positive while the era bound is measured at
    zero — the (lx) incident. The rail must read `claim_era`."""
    bus.brain(1.5)
    bus.alloc(0.0, n_era=40)
    bus.state["alloc"]["books"][BOT]["claim"] = 0.005      # all-time looks fine
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (80.0, 1.0)


def test_a_stale_allocation_payload_changes_nothing(bus):
    bus.brain(1.5)
    bus.alloc(0.0, n_era=40)
    bus.state["alloc"]["updated"] = (bus.now - dt.timedelta(hours=9)).isoformat()
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5)


def test_the_min_n_is_the_allocation_organs_floor_not_a_retyped_constant():
    assert fb.LB_CAP_MIN_N == FA.MIN_N, (fb.LB_CAP_MIN_N, FA.MIN_N)


# ------------------------------------------------------------ drawdown scale

def test_a_dark_gate_scales_nothing(bus):
    bus.brain(1.0)
    assert fb.dd_scale(BOT, bus.now) == 1.0
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (80.0, 1.0)


@pytest.mark.parametrize("dd,expected", [
    (0.038, 1.0),          # mum-live the day this shipped
    (0.056, 1.0),          # avo-live
    (0.10, 1.0),           # an ordinary drawdown INSIDE the bar: untouched
    (0.15, 1.0),           # AT the bar: scaling begins here, not before
    (0.225, 0.625),        # halfway from the bar to twice the bar
    (0.285, 0.325),        # kelly's reading
    (0.30, 0.25),          # twice the bar: the floor
    (0.583, 0.25),         # georgia's retired live row: still the floor
])
def test_the_scale_is_one_to_the_bar_then_linear_to_the_floor_at_twice_it(bus, dd, expected):
    bus.gate(dd)
    assert fb.dd_scale(BOT, bus.now) == pytest.approx(expected)


def test_the_scale_reads_the_gates_worse_of_both_field_not_the_realised_one(bus):
    """`max_dd_pct` is the fold of realised and MTM (I9); `max_dd_pct_realised`
    is the number that read 5.3% on a book at 58% MTM. A rail reading the
    realised field would have left georgia's live row at full clip."""
    bus.gate(0.05)
    bus.state["gate"]["books"][BOT]["max_dd_pct"] = 58.3
    bus.state["gate"]["books"][BOT]["max_dd_pct_realised"] = 5.3
    assert fb.dd_scale(BOT, bus.now) == 0.25


def test_the_bar_comes_from_the_payload_with_a_pinned_fallback(bus):
    bus.gate(0.25, bar=0.20)                 # a re-specced gate publishes 20%
    # 25% is a quarter of the way from 20% to 40%
    assert fb.dd_scale(BOT, bus.now) == pytest.approx(1.0 - 0.25 * 0.75)
    bus.state["gate"]["bar"] = {}
    # fallback 15%: 25% is two-thirds of the way from 15% to 30%
    assert fb.dd_scale(BOT, bus.now) == pytest.approx(1.0 - (25.0 - 15.0) / 15.0 * 0.75)
    assert fb.DD_BAR_PCT_FALLBACK == pytest.approx(100 * GR.GOLIVE_MAX_DD), (
        "the fallback bar drifted from the gate's own GOLIVE_MAX_DD")


def test_the_scale_multiplies_the_brain_and_the_receipt_decomposes_it(bus):
    bus.brain(1.5)
    bus.alloc(0.001, n_era=40)
    bus.gate(0.30)
    usd, mult = fb.brain_clip(BOT, TAG, 80.0, bus.now)
    assert usd == pytest.approx(80.0 * 1.5 * 0.25) and mult == pytest.approx(0.375)
    assert fb.last_sizing[BOT] == {"brain": 1.5, "lb_capped": False,
                                   "dd_pct": 30.0, "dd_scale": 0.25}


def test_the_rails_act_after_the_gross_trim_not_before(bus):
    """Trim first (never below base), then scale: a book at the floor with a
    budget-trimmed brain expansion ends at trimmed x scale, not base x scale
    with the trim silently discarded."""
    bus.brain(1.5)
    bus.alloc(0.001, n_era=40)
    bus.gate(0.30)
    usd, _ = fb.brain_clip(BOT, TAG, 80.0, bus.now, deployed_usd=0.0,
                           gross_cap_usd=90.0)
    assert usd == pytest.approx(90.0 * 0.25)


def test_the_rails_read_the_first_bucket_which_is_the_sized_book(bus):
    """avo's live arm passes (BOT_ROW, SHADOW_ROW): the live row is sized, the
    shadow row is evidence. The gate reading for the LIVE row must decide."""
    bus.brain(1.0)
    bus.gate(0.30)                           # BOT at the floor
    other = "freqtrade-avo-maria-lighter"
    usd, _ = fb.brain_clip_multi([(other, TAG), (BOT, TAG)], 80.0, bus.now)
    assert usd == 80.0, "the second bucket's drawdown must not scale the first"
    usd, _ = fb.brain_clip_multi([(BOT, TAG), (other, TAG)], 80.0, bus.now)
    assert usd == pytest.approx(20.0)


# ------------------------------------------------------------ kill switch

def test_the_kill_switch_returns_both_rails_to_neutral(bus, monkeypatch):
    bus.brain(1.5)
    bus.alloc(0.0, n_era=40)                 # measured zero: cap
    bus.gate(0.30)                           # at the floor
    monkeypatch.setenv("BRAIN_RAILS_MODE", "advisory")
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (120.0, 1.5)
    monkeypatch.delenv("BRAIN_RAILS_MODE")
    assert fb.brain_clip(BOT, TAG, 80.0, bus.now) == (20.0, 0.25)


# ------------------------------------------------------------ live picture

def test_the_live_pair_is_untouched_on_the_day_this_shipped(bus):
    """mum-live: claim_era +0.003659 on n_era 52, dd 3.8%; avo-live: claim_era
    0.0 on n_era 11, dd 5.6%. Neither is scaled; mum may expand, avo may not —
    the audit's own reading (mum LB +0.366%, avo-live LB −0.316%)."""
    for dd in (0.038, 0.056):
        bus.gate(dd)
        assert fb.dd_scale(BOT, bus.now) == 1.0
    bus.alloc(0.003659, n_era=52)
    assert fb.lb_permits_expansion(BOT, bus.now) is True
    bus.alloc(0.0, n_era=11)
    assert fb.lb_permits_expansion(BOT, bus.now) is False


def test_the_rails_move_nothing_but_a_size():
    """No lever write, no order, no publish anywhere in the rails' source."""
    src = Path(fb.__file__).read_text()
    i = src.index("DD_SCALE_START_FRAC = ")
    j = src.index("def brain_clip(")
    block = src[i:j]
    for forbidden in ("write_levers(", "market_open(", "publish(", "set_lever("):
        assert forbidden not in block, forbidden
