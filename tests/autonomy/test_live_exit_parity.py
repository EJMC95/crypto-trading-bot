#!/usr/bin/env python3
"""[2026-08-26] THE LIVE HOST RUNS THE STRATEGY'S OWN EXIT POLICY — ALL OF IT.

The (te) audit found the variant host never called `custom_exit`. This file
pins the two family semantics that audit missed, found by pairing 🔮
georgia's live ledger against her shadow twin's:

  * the trend_breakout VETO on the exit signal — the live row booked 24 of 51
    closes as `long-trend-breakout_range_top` at 15m median hold, a
    combination the shadow's ledger cannot book at all (0 of 207: the family
    loop vetoes `range_top` for breakout entries, because a breakout is by
    construction at the top of the range it just left);

  * DayTraderGated's trailing ATR ratchet — the shadow's primary loss control
    (106 of her 207 closes) simply did not exist on the live arm, which
    checked only the fixed `profit <= stoploss` (0 trailing closes in 51; the
    one fixed-stop fill gapped to -7.17%).

Everything drives `manage_exit_reason`, the extracted seam, with the REAL
strategy instances from lighter_family_bot.STRATEGIES — never hand-rolled
fixtures ((hj): a consumer is tested against a payload its publisher built).

Plus the census split's contract (`census_no_entry_why`, one owner both
arms): 👩 mum's uptrend-blocked refusals stop being byte-identical to "no low
rsi anywhere" (I18), and 🙏 avo's SwingDip — whose sig also carries
rsi/uptrend, with uptrend REQUIRED rather than blocking — must NOT inherit
mum's semantics by shape.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("AVO_VENUE", "lighter_live")

import lighter_avo_live_bot as A          # noqa: E402
import lighter_family_bot as fam          # noqa: E402


def _book(bot):
    for s in fam.STRATEGIES:
        if s.bot == bot:
            return s
    raise AssertionError(f"{bot} not in STRATEGIES")


GEORGIA = _book("freqtrade-georgia")
AVO = _book("freqtrade-avo-maria")
MUM = _book("freqtrade-mum")

#: bars short of min_bars on purpose: DayTraderGated.signals returns None, so
#: atr_stop_dist falls back to its own declared -stoploss cap (0.05) — a
#: deterministic ratchet distance without a 200-bar fixture.
SHORT_BARS = {"t": [1, 2, 3], "c": [100.0] * 3, "h": [101.0] * 3,
              "l": [99.0] * 3, "v": [1.0] * 3}


def _reason(strategy, tag, px, entry, age_min=10.0, sig=None, bars=None,
            m=None):
    m = m if m is not None else {"tag": tag}
    profit = (px - entry) / entry
    return A.manage_exit_reason(strategy, m, px, profit, age_min, sig, bars), m


# ---------------------------------------------------------------- the veto
def test_breakout_never_exits_on_the_range_top_signal():
    """The impossible-in-shadow combination stays impossible live."""
    sig = {"exit": True, "exit_reason": "range_top"}
    r, _ = _reason(GEORGIA, "trend_breakout", px=101.0, entry=100.0,
                   sig=sig, bars=SHORT_BARS)
    assert r is None, (
        f"live host booked {r!r} — the family vetoes range_top for "
        f"trend_breakout, and 24 of georgia's first 51 live closes were "
        f"exactly this defect")


def test_range_on_still_takes_the_exit_signal():
    """The veto is tag-scoped: range books keep their own exit."""
    sig = {"exit": True, "exit_reason": "range_top"}
    r, _ = _reason(GEORGIA, "range_on", px=101.0, entry=100.0,
                   sig=sig, bars=SHORT_BARS)
    assert r == "range_top"


def test_roi_outranks_the_exit_signal():
    """Family order: stop -> roi -> custom_exit -> signal."""
    sig = {"exit": True, "exit_reason": "range_top"}
    r, _ = _reason(GEORGIA, "range_on", px=101.9, entry=100.0,
                   sig=sig, bars=SHORT_BARS)
    assert r == "roi"          # 1.9% >= the 0-rung's 1.8% bar


# ------------------------------------------------------------- the ratchet
def test_ratchet_arms_below_the_current_price_not_at_the_fixed_stop():
    """First manage call at -5.5%: the fixed stop would fire; the family's
    ratchet arms BELOW the current price instead. This is the exact
    behavioural difference between the two policies."""
    r, m = _reason(GEORGIA, "trend_breakout", px=94.5, entry=100.0,
                   bars=SHORT_BARS)
    assert r is None, f"fixed-stop semantics leaked through: {r!r}"
    assert m["stop_px"] == pytest.approx(94.5 * 0.95)


def test_ratchet_is_monotone_and_fires_on_the_way_back_down():
    m = {"tag": "trend_breakout"}
    r, _ = _reason(GEORGIA, "trend_breakout", px=100.0, entry=100.0, m=m,
                   bars=SHORT_BARS)
    assert r is None and m["stop_px"] == pytest.approx(95.0)
    # a dip that stays above the stop must not LOWER it
    r, _ = _reason(GEORGIA, "trend_breakout", px=98.0, entry=100.0, m=m,
                   bars=SHORT_BARS)
    assert r is None and m["stop_px"] == pytest.approx(95.0), (
        "the ratchet moved DOWN — it is a high-water mark, not a tracker")
    # a run-up (below the 1.8% roi bar) ratchets it
    r, _ = _reason(GEORGIA, "trend_breakout", px=101.5, entry=100.0, m=m,
                   bars=SHORT_BARS)
    assert r is None and m["stop_px"] == pytest.approx(101.5 * 0.95)
    # and the give-back is caught at -4% from entry — INSIDE the fixed -5%
    # stop, i.e. an exit the live arm's old policy could never take
    r, _ = _reason(GEORGIA, "trend_breakout", px=96.0, entry=100.0, m=m,
                   bars=SHORT_BARS)
    assert r == "trailing_stop_loss"


def test_bars_dark_keeps_the_fixed_stop_as_backstop():
    """Declared divergence from the family (where bars always exist): a
    DayTrader position with no bars must never be stopless."""
    r, _ = _reason(GEORGIA, "trend_breakout", px=94.0, entry=100.0, bars=None)
    assert r == "stop_loss"
    r, _ = _reason(GEORGIA, "trend_breakout", px=99.0, entry=100.0, bars=None)
    assert r is None


def test_non_daytrader_books_keep_the_fixed_stop():
    """🙏 avo's SwingDip bracket is fixed-stop BY DESIGN — unchanged."""
    r, _ = _reason(AVO, "dip_in_uptrend", px=89.0, entry=100.0,
                   bars=SHORT_BARS)
    assert r == "stop_loss"                     # -11% through the -10% stop


def test_the_seam_reads_the_handed_strategys_ladder_not_the_module_global():
    """S is avo (module default): avo's 0-rung is 20%, georgia's is 1.8%. A
    seam that read S would refuse georgia's roi here."""
    r, _ = _reason(GEORGIA, "range_on", px=101.9, entry=100.0,
                   bars=SHORT_BARS)
    assert r == "roi"


# ------------------------------------------------------------- the census
def test_mum_sub_bar_rsi_blocked_by_uptrend_reads_uptrend_blocked():
    sig = {"enter": None, "exit": False, "rsi": 16.8, "uptrend": True}
    assert fam.census_no_entry_why(MUM, sig) == "uptrend_blocked"


def test_mum_high_rsi_is_plain_no_signal():
    sig = {"enter": None, "exit": False, "rsi": 40.0, "uptrend": True}
    assert fam.census_no_entry_why(MUM, sig) == "no_signal"


def test_mum_sub_bar_rsi_without_uptrend_is_no_signal():
    """rsi<bar and NOT uptrend and still no enter (e.g. zero volume) — the
    uptrend did not block it, so the census must not say it did."""
    sig = {"enter": None, "exit": False, "rsi": 16.8, "uptrend": False}
    assert fam.census_no_entry_why(MUM, sig) == "no_signal"


def test_a_none_sig_is_no_read_never_no_signal():
    assert fam.census_no_entry_why(MUM, None) == "no_read"


def test_avo_swingdip_never_inherits_mums_semantics_by_shape():
    """SwingDip reports rsi<42 beside uptrend=True with uptrend REQUIRED —
    the exact shape that would fake an uptrend_blocked without the
    class-scoped gate."""
    assert not getattr(AVO, "UPTREND_BLOCKS", False)
    sig = {"enter": None, "exit": False, "rsi": 30.0, "uptrend": True}
    assert fam.census_no_entry_why(AVO, sig) == "no_signal"


def test_the_census_owner_is_shared_by_identity():
    """(hj): a second copy of a rule is a second rule."""
    assert A.census_no_entry_why is fam.census_no_entry_why


def test_the_family_loop_consumes_the_owner_and_seeds_the_buckets():
    src = open(os.path.join(ROOT, "lighter_family_bot.py")).read()
    assert "b.scan[census_no_entry_why(b.s, sig)] += 1" in src, (
        "the family census no longer routes through the one owner")
    assert '"uptrend_blocked": 0' in src and '"no_read": 0' in src, (
        "the scan seed dict lost the new buckets — a plain-dict += on an "
        "unseeded key raises KeyError in the live loop")


# ----------------------------------------------------------- the era move
def test_georgias_live_row_era_starts_at_the_parity_fix():
    """Dates derived from the table, never hardcoded (audit_era_date_literals):
    the pinned properties are the exact-key scoping and the ordering."""
    import golive_readiness as g
    assert g.era_base("freqtrade-georgia-lighter") == \
        "freqtrade-georgia-lighter", "exact-match lookup lost — the strip " \
        "would scope the shadow twin too ((hd))"
    live_iso = g.POLICY_ERA["freqtrade-georgia-lighter"][0]   # KeyError = red
    ep, iso, why = g.era_epoch_for("freqtrade-georgia-lighter")
    assert ep is not None and iso == live_iso, (iso, why)
    assert "exit" in why, "the reason must name the policy change"
    # the shadow twin keeps its own, EARLIER era — its 195-close sample IS
    # the go-live case and always ran the declared policy
    ep2, iso2, _ = g.era_epoch_for("freqtrade-georgia-lshadow")
    assert iso2 == g.POLICY_ERA["freqtrade-georgia"][0] and iso2 < iso
