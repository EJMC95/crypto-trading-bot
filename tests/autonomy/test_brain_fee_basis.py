"""The brain's fee basis — where it was DEGRADING, and why it cannot again.

[2026-07-30] Three defects compounded in `bot_learn`'s round-trip friction
estimate, and the result was not a cosmetic mis-report: the brain attributed
losses to a cost that does not exist, and in doing so SUPPRESSED its only
actionable diagnosis.

  1. WRONG KEY FORM — `FEE_RT.get(bot, ...)` was called with the SUFFIXED row
     name (`perps-funding-carry-lshadow`) while every table key is a bare base
     name. Not one entry ever matched; every bot took the default. The
     identical defect the 23-Jul audit fixed for ERA_START, five lines away in
     the same function.
  2. A RETIRED VENUE'S FEE AS THE FLEET DEFAULT — 0.0052 is Kraken SPOT taker
     round trip, and Kraken was retired 14-Jul.
  3. LIGHTER IS ZERO-FEE, MEASURED — all 203 active books report
     `taker_fee 0.0000` / `maker_fee 0.0000` (2026-07-30, via
     orderBookDetails). The phantom cost was the ENTIRE estimate.

THE DAMAGE, which is what these tests really guard: `diagnose()` rule 3 fires
when `fee_rt / med_loser >= 0.5` and `med_loser <= 0.012`, and it RETURNS.
With fee_rt = 0.0052 that holds for ANY bucket whose median loser is <= 1.04%
— an extremely common loss size — so rule 3 pre-empted rule 4
(`regime_timing`), the ONLY diagnosis kind carrying an actuator
(`regime_gate`). The brain could not recommend the one thing it can act on.

The fee is now MEASURED (the scout publishes the venue's own schedule) with a
per-venue fallback for a dark scout. Note `is_taker_fee_enabled` is TRUE on
every book with the rate at zero — the machinery is ON and the rate CAN
change, so a hardcoded 0.0 would be this same mistake mirrored.
"""
from datetime import datetime, timedelta, timezone

import bot_learn
import pytest

pytestmark = pytest.mark.autonomy


# --------------------------------------------------------------------------
# 1. The key form — defect 1.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("row,base", [
    ("perps-funding-carry-lshadow", "perps-funding-carry"),
    ("perps-funding-lighter-lighter", "perps-funding-lighter"),
    ("lighter-dislocation-lshadow", "lighter-dislocation"),
    ("freqtrade-mum", "freqtrade-mum"),          # already bare
])
def test_fee_base_strips_the_row_suffix(row, base):
    assert bot_learn.fee_base(row) == base


def test_the_fee_table_is_keyed_on_bases_that_actually_resolve():
    """A table whose keys can never match any real row is dead configuration
    that silently routes every bot to the default."""
    for key in bot_learn.FEE_RT:
        assert bot_learn.fee_base(key) == key, (
            f"FEE_RT key {key!r} is not a bare base name")


# --------------------------------------------------------------------------
# 2. No Lighter row may ever inherit another venue's fee — defects 2 and 3.
# --------------------------------------------------------------------------

LIGHTER_ROWS = [
    "perps-funding-carry-lshadow", "perps-funding-spread-lshadow",
    "lighter-dislocation-lshadow", "equities-regime-lshadow",
    "crypto-trend-daily-lshadow", "lighter-perp-sniper-lshadow",
    "lighter-ticket-taker-lshadow", "lighter-ticket-taker-lighter",
    "perps-funding-lighter-lighter", "freqtrade-mum-lshadow",
]


@pytest.mark.parametrize("row", LIGHTER_ROWS)
def test_a_lighter_row_never_inherits_the_kraken_default(row):
    assert bot_learn.is_lighter_row(row), row
    got = bot_learn.fee_rt_for(row)
    assert got != bot_learn.FEE_RT_DEFAULT, (
        f"{row} took the Kraken SPOT default {bot_learn.FEE_RT_DEFAULT} — "
        "that inheritance IS the defect")
    assert got == bot_learn.LIGHTER_FEE_RT_FALLBACK


@pytest.mark.parametrize("row", LIGHTER_ROWS)
def test_a_lighter_row_prefers_the_MEASURED_venue_fee(row):
    """The scout publishes the venue's own schedule; the brain must use it, so
    that a fee change at the venue needs no code change here."""
    assert bot_learn.fee_rt_for(row, {"taker": 0.0, "maker": 0.0}) == 0.0
    # round trip = BOTH sides; a taker-only estimate is optimistic
    assert bot_learn.fee_rt_for(row, {"taker": 0.0004}) == pytest.approx(0.0008)


def test_a_dark_scout_falls_back_but_never_to_a_foreign_venue():
    """Fail-safe direction: an unmeasured fee must not become a claim of
    certainty (0.0) NOR another venue's constant."""
    for fees in (None, {}, {"taker": None}, {"taker": "junk"}):
        got = bot_learn.fee_rt_for("perps-funding-carry-lshadow", fees)
        assert got == bot_learn.LIGHTER_FEE_RT_FALLBACK, fees
        assert got != bot_learn.FEE_RT_DEFAULT
        assert got > 0.0, "a dark scout must not assert zero-cost certainty"


def test_non_lighter_rows_still_use_their_table_entry():
    """The fix must not silently zero the fee for a genuinely fee-paying
    venue — the retired rows' history is still graded."""
    assert bot_learn.fee_rt_for("event-listing-sniper") == 0.0060
    assert bot_learn.fee_rt_for("perps-rsi-meanrev") == 0.0029
    assert bot_learn.fee_rt_for("some-unknown-spot-bot") == \
        bot_learn.FEE_RT_DEFAULT


# --------------------------------------------------------------------------
# 3. THE ACTUAL DAMAGE — rule 3 shadowing rule 4, the only rule with an
#    actuator. This is the test that matters.
# --------------------------------------------------------------------------

# `bot_learn._epoch` parses ISO-8601 STRINGS (it is `datetime.fromisoformat`),
# so a trade row carries an ISO `open_ts`. An epoch-int fixture makes
# `_regime_at` return None for every trade, `regime_matched` 0, and the bucket
# falls through to `mixed_unclear` — the test would then "pass" the
# no-fee_bleed claim while proving NOTHING about regime_timing. Measured that
# exact failure while writing this file; the fixture must speak the real
# ledger's dialect.
_T0 = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _losers(n, pct):
    """n closed losers of size `pct`, all opened in one regime window."""
    return [{"pair": "BTC/USDT", "profit_abs": -1.0, "profit_ratio": -pct,
             "enter_tag": "long-dip", "exit_reason": "roi",
             "open_ts": _iso(_T0 + timedelta(seconds=i)),
             "close_ts": _iso(_T0 + timedelta(seconds=100 + i))}
            for i in range(n)]


def _regime_hist(risk_off=True):
    # `_regime_at` matches the nearest snapshot within 1h of a trade's OPEN,
    # and compares raw epoch floats — so `ts` here is a float, while the trade
    # rows above are ISO. Two different dialects in one function, which is
    # exactly why this fixture is worth spelling out.
    base = _T0.timestamp()
    return [{"ts": base + i, "risk_off": risk_off} for i in range(20)]


def test_the_phantom_fee_would_shadow_the_only_actionable_diagnosis():
    """With the Kraken constant, a 1% median loser reads as 'fee-scale' and
    rule 3 RETURNS before regime_timing — the only diagnosis with an actuator
    — can ever be evaluated. Demonstrated directly against fee_rt_for's two
    answers for the SAME book.
    """
    row = "perps-funding-carry-lshadow"
    med_loser = 0.010                      # 1% — an ordinary losing trade

    phantom = bot_learn.FEE_RT_DEFAULT     # what the bug applied
    measured = bot_learn.fee_rt_for(row, {"taker": 0.0})   # what is true

    # rule 3's condition, verbatim from diagnose()
    def fires(fee_rt):
        return (fee_rt / med_loser) >= 0.5 and med_loser <= 0.012

    assert fires(phantom), "the Kraken constant DOES trip rule 3 at a 1% loser"
    assert not fires(measured), (
        "the measured zero-fee venue must NOT trip rule 3 — otherwise the "
        "brain keeps blaming costs and never reaches regime_timing")


def _regime_effect_bucket(n_losers=12, pct=0.010, n_win=10):
    """A bucket carrying a GENUINE regime effect: losers in risk-off, winners
    in risk-on, so `counter_share − base_share` is a real lift.

    [2026-08-06 (li)] This fixture used to be 12 losers, NO winners, and an
    all-risk-off history — and it reached `regime_timing` because rule 4 fired
    on a raw rate that is 1.0 by arithmetic whenever the oracle is constant.
    That is the exact defect (li) fixed: the test was passing BECAUSE of the
    bug. Its actual invariant — rule 3 (`fee_bleed`) must not shadow rule 4,
    the only diagnosis carrying an actuator — is unchanged and still tested;
    it now just rests on regime evidence that would genuinely justify the
    verdict. Winners are tiny (+0.001) so the bucket stays NET NEGATIVE, which
    `diagnose` requires before it will classify at all.
    """
    base = _T0.timestamp()
    trades = _losers(n_losers, pct)
    hist = [{"ts": base + i, "risk_off": True} for i in range(n_losers)]
    for j in range(n_win):
        off = 7200 + j * 60          # well clear of the losers' 1h match window
        trades.append({"pair": "BTC/USDT", "profit_abs": +0.001,
                       "profit_ratio": +0.0001, "enter_tag": "long-dip",
                       "exit_reason": "roi",
                       "open_ts": _iso(_T0 + timedelta(seconds=off)),
                       "close_ts": _iso(_T0 + timedelta(seconds=off + 100))})
        hist.append({"ts": base + off, "risk_off": False})
    return trades, hist


def test_diagnose_reaches_regime_timing_on_a_zero_fee_venue():
    """End-to-end through the real diagnose(): the same bucket that would have
    been called `fee_bleed` now reaches `regime_timing`, which is the finding
    that carries an actuator."""
    trades, hist = _regime_effect_bucket()
    d = bot_learn.diagnose("perps-funding-carry-lshadow", "long-dip", trades,
                           hist, {}, {"left": 120},
                           venue_fees={"taker": 0.0, "maker": 0.0})
    assert d is not None, "the bucket should be diagnosable at this n"
    assert d["primary"] != "fee_bleed", (
        "a zero-fee venue must never be diagnosed fee_bleed — that was the "
        "corruption")
    assert d["primary"] == "regime_timing", d


def test_diagnose_still_calls_fee_bleed_where_fees_are_REAL():
    """The fix must not blind the rule. A genuinely fee-paying venue with
    fee-scale losses must still be diagnosed fee_bleed."""
    trades = _losers(12, 0.010)
    d = bot_learn.diagnose("event-listing-sniper", "long-dip", trades,
                           _regime_hist(risk_off=True), {}, {"left": 120})
    assert d is not None and d["primary"] == "fee_bleed", d


def test_a_fee_hike_at_the_venue_reaches_the_diagnosis_with_no_code_change():
    """The self-correcting property. If Lighter switches its (already-enabled)
    fees on, the brain must start seeing fee_bleed again — that is the whole
    reason the fee is published rather than hardcoded to 0.0."""
    trades = _losers(12, 0.010)
    d = bot_learn.diagnose("perps-funding-carry-lshadow", "long-dip", trades,
                           _regime_hist(risk_off=True), {}, {"left": 120},
                           venue_fees={"taker": 0.0030, "maker": 0.0010})
    assert d is not None and d["primary"] == "fee_bleed", d


# --------------------------------------------------------------------------
# 4. The feed must actually be fed — the registered-but-unfed class.
# --------------------------------------------------------------------------

def test_main_loads_the_measured_fees_and_threads_them_through():
    """`fee_rt_for` reading a `venue_fees` nobody supplies would silently take
    the dark-scout fallback forever, making the 'measured' claim false."""
    import inspect
    src = inspect.getsource(bot_learn.main)
    assert 'load_state("lighter-market")' in src, \
        "main must LOAD the scout's fee block"
    assert "venue_fees=venue_fees" in src, \
        "main must THREAD it into diagnose — a loaded-but-unpassed feed is inert"


def test_the_scout_publishes_the_block_the_brain_reads():
    """Both ends of the contract, in one assertion — a rename on either side
    must fail here rather than degrade silently."""
    import lighter_market_scout as scout
    books = [{"status": "active", "symbol": "BTC", "mark_price": 1.0,
              "index_price": 1.0, "daily_quote_token_volume": 1e6,
              "taker_fee": 0.0, "maker_fee": 0.0},
             {"status": "active", "symbol": "PRICEY", "mark_price": 1.0,
              "index_price": 1.0, "daily_quote_token_volume": 1e6,
              "taker_fee": 0.0005, "maker_fee": 0.0002}]
    snap = scout.build_snapshot(scout.book_stats(books, 1e5), {}, {}, {},
                               now_ms=1_700_000_000_000.0)
    fees = snap["fees"]
    # MAX, not mean: one expensive book must not hide behind the free ones
    assert fees["taker"] == 0.0005 and fees["maker"] == 0.0002
    assert fees["n_books"] == 2
    # and the brain consumes exactly this shape
    assert bot_learn.fee_rt_for("x-lshadow", fees) == pytest.approx(0.0010)
