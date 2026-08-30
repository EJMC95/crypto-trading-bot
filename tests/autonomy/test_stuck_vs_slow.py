"""[2026-08-27] STUCK vs SLOW — the lens that stops a retirement being made for
the wrong reason.

**Eamon, 26-Aug:** *"a lot of the time we've thought it's stuck it's slow."*

`{closed: 0}` is byte-identical between a book that CANNOT trade and one that
has not finished a trade yet, so the fleet's docket has been asking for
retirements it cannot justify. This suite pins the four properties that make the
new lens trustworthy rather than another opinion:

  * OCCUPANCY, not closes, decides — a book holding at its own cap is DEPLOYED,
    and its empty ledger is a HOLD TIME (🧮 Hull, 🏦 Rich Dad, both on the
    docket as `zero_ledger` the day this shipped);
  * a snapshot may NEVER assert a defect — STUCK needs `MIN_STUCK_PUBLISHES`
    DISTINCT publishes agreeing, so neither one loop nor three re-reads of one
    loop can reach it;
  * a healthy trading book is never STUCK, however it is sampled (the negative
    control — a detector that cries wolf is one the operator learns to ignore);
  * the docket cross-reference FIRES on a book this lens reads as merely SLOW,
    because that is the error the instrument exists to prevent.

FIXTURES ARE PUBLISHER OUTPUT, NOT INVENTIONS. `LIVE_ROWS` below is a verbatim
transcript of rows captured from the live /pnl.json on 2026-08-27 (the
dashboard's own serialisation, `extra.scan` / `extra.census` / `extra.caps`
untouched, telemetry fields included). A hand-written fixture that "looks like"
a payload tests the reader against the reader's own assumptions; these rows were
built by the publisher.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_stuck_vs_slow", ROOT / "scripts" / "audit_stuck_vs_slow.py")
sv = importlib.util.module_from_spec(_spec)
# Registered BEFORE exec_module on purpose: `@dataclass` resolves a field's
# annotation through `sys.modules[cls.__module__]`, so a module loaded by path
# and never registered raises `AttributeError: 'NoneType' has no '__dict__'`
# on 3.9. Caught by this suite's first run.
sys.modules[_spec.name] = sv
_spec.loader.exec_module(sv)

pytestmark = pytest.mark.autonomy

TS = "2026-08-27T12:40:00+00:00"

# ── verbatim transcript of live publisher output, /pnl.json 2026-08-26 ──────
# DATES SHIFTED +1 DAY (26-Aug -> 27-Aug) on purpose: 2026-08-26 is a CANONICAL
# ERA DATE, and `audit_era_date_literals` (rightly) refuses a fixture that
# hardcodes one — moving an era must never move a fixture that has nothing to
# do with it. Every timestamp shifted by the same day, so all relative deltas
# (freshness, ordering, age_sec) are byte-identical to the captured payload;
# only the absolute day differs, and nothing here asserts on the day.
LIVE_ROWS = json.loads(r"""
{
 "band-kelly-lshadow": {
  "age": 67,
  "closed": 233,
  "extra": {
   "caps": {
    "clip_usd": 250.0,
    "confirm_loops": 2,
    "crypto_only": true,
    "dip": {
     "clip_usd": 40.0,
     "ghost_sl": 0.03,
     "ghost_tp": 0.04,
     "i16_override": "operator 18-Aug, n=13 probe",
     "max_hold_s": 172800.0,
     "max_positions": 2,
     "range_max": 0.05
    },
    "exit_bps": 40.0,
    "gate_bps": 60.0,
    "gate_cap_bps": 150.0,
    "gate_floor_bps": 60.0,
    "ghost_config": "lighter-dislocation retirement (jh), frozen",
    "ghost_stop": 0.05,
    "gross_max_usd": 1080.0,
    "max_entry_slip_bps": 30.0,
    "max_hold_s": 7200.0,
    "max_positions": 4,
    "min_vol_m": 0.5,
    "my_hard_stop": 0.05,
    "my_max_slip_bps": 60.0,
    "universe_n": 40
   },
   "held": {
    "ADA": "S",
    "LTC": "S"
   },
   "scan": {
    "below_gate": 38,
    "capped": 0,
    "confirming": 0,
    "dev_max_bps": 37.7,
    "dev_med_bps": 8.8,
    "dev_n": 40,
    "dev_p98_bps": 24.2,
    "dip_capped": 0,
    "dip_cooldown": 0,
    "dip_opened": 0,
    "dip_slip": 0,
    "dip_tickets": 4,
    "embargoed": 0,
    "events": 0,
    "ghost_slip": 0,
    "held": 2,
    "my_slip": 0,
    "no_book": 0,
    "noncrypto": 0,
    "opened": 0,
    "ref_blind": 0,
    "scanned": 40
   }
  },
  "open": 2,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:36:18.051704+00:00"
 },
 "book-douglas-lshadow": {
  "age": 115,
  "closed": 60,
  "extra": {
   "caps": {
    "atr_n": 24,
    "clip_usd": 100.0,
    "crypto_only": true,
    "impulse_k": 2.5,
    "max_hold_h": 12.0,
    "max_positions": 4,
    "min_vol_m": 1.0,
    "sl_atr": 1.0,
    "tp_atr": 1.5,
    "universe_n": 18
   },
   "held": {},
   "scan": {
    "capped": 0,
    "held": 0,
    "no_bars": 0,
    "opened": 0,
    "quiet": 18,
    "scanned": 18,
    "signal": 0,
    "stops_blind": 0,
    "unpriceable": 0
   }
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:35:30.438481+00:00"
 },
 "book-grimes-lshadow": {
  "age": 93,
  "closed": 0,
  "extra": {
   "caps": {
    "clip_usd": 80.0,
    "crypto_only": true,
    "gate_min_n": 20,
    "gate_min_t": 0.5,
    "max_positions": 2,
    "min_vol_m": 1.0,
    "retest_h": 6.0,
    "setups": [
     "pullback",
     "failtest",
     "keltner"
    ],
    "universe_n": 18,
    "window_d": 120.0
   },
   "held": {},
   "scan": {
    "capped": 0,
    "gated": 8,
    "held": 0,
    "no_bars": 0,
    "opened": 0,
    "quiet": 4,
    "scanned": 18,
    "signal": 8,
    "stops_blind": 0,
    "trend_dark": 0,
    "ungraded_skip": 6,
    "unpriceable": 0
   },
   "scorecard": {
    "failtest": {
     "asof": 1787737250.94963,
     "mean_pct": -0.323,
     "n": 394,
     "net": -127.29,
     "open": false,
     "t": -1.82
    },
    "keltner": {
     "asof": 1787737250.94963,
     "mean_pct": -0.527,
     "n": 154,
     "net": -81.22,
     "open": false,
     "t": -1.17
    },
    "pullback": {
     "asof": 1787737250.94963,
     "mean_pct": -0.361,
     "n": 149,
     "net": -53.85,
     "open": false,
     "t": -0.77
    }
   }
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:35:52.538460+00:00"
 },
 "book-hull-lshadow": {
  "age": 47,
  "closed": 0,
  "extra": {
   "caps": {
    "apr_hi": 0.2,
    "basis_veto_bps": 10.0,
    "clip_usd": 80.0,
    "crypto_only": true,
    "enter_apr": 0.0782,
    "exit_apr": 0.035,
    "flip_grace_h": 24.0,
    "max_positions": 6,
    "max_vol": 10000000.0,
    "min_vol": 2000000.0,
    "payback_max_h": 336.0,
    "stable_h": 24.0
   },
   "held": {
    "BNB": "S",
    "DOGE": "S",
    "LIT": "S",
    "UNI": "S",
    "XRP": "S",
    "ZEC": "S"
   },
   "scan": {
    "above_band": 19,
    "adverse_basis": 0,
    "below_band": 106,
    "deep": 4,
    "eligible": 1,
    "held": 6,
    "noncrypto": 0,
    "scanned": 228,
    "thin": 90,
    "waiting": 2
   }
  },
  "open": 6,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:36:38.442056+00:00"
 },
 "book-kiyosaki-lshadow": {
  "age": 141,
  "closed": 0,
  "extra": {
   "caps": {
    "clip_usd": 80.0,
    "crypto_only": false,
    "enter_apr": 0.2,
    "exit_apr": 0.01875,
    "flip_grace_h": 6.0,
    "max_positions": 6,
    "min_vol": 1000000.0,
    "payback_max_h": 120.0,
    "persist_h": 6.0
   },
   "held": {
    "AAVE": "S",
    "HYPE": "S",
    "NBIS": "S",
    "XMR": "S",
    "ZEC": "S",
    "ZRO": "S"
   },
   "scan": {
    "cold": 204,
    "eligible": 2,
    "held": 6,
    "noncrypto": 0,
    "scanned": 228,
    "slow_payback": 0,
    "thin": 14,
    "waiting": 2
   }
  },
  "open": 6,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:35:03.798400+00:00"
 },
 "freqtrade-mum-lighter": {
  "age": 268,
  "closed": 0,
  "extra": {
   "held": {},
   "max_open": 4,
   "scan": {
    "held": 0,
    "near_bar": 2,
    "rsi_bar": 30.0,
    "rsi_med": 43.9,
    "rsi_min": 29.2,
    "rsi_read": 23,
    "ungraded": [
     "IWM",
     "WTI",
     "XCU"
    ],
    "universe": 23,
    "verdicts": {
     "no_signal": 22,
     "uptrend_blocked": 1
    }
   }
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:32:56.929113+00:00"
 },
 "lighter-perp-sniper-lshadow": {
  "age": 5,
  "closed": 36,
  "extra": {
   "caps": {
    "class_screen": {
     "listing": false,
     "surge": true,
     "young": true
    },
    "crypto_only": false,
    "max_open": 4,
    "surge_mult": 2.5
   },
   "held": {},
   "scan": {
    "abandoned": 0,
    "capped": 0,
    "dupe": 0,
    "failed": 0,
    "held": 0,
    "listing": 0,
    "max_open": 4,
    "not_young": 69,
    "offered": 0,
    "open_before": 0,
    "opened": 0,
    "pending": 2,
    "surge": 0,
    "surge_cooldown": 3,
    "young": 0
   }
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:37:20.336680+00:00"
 },
 "lighter-ticket-taker-lshadow": {
  "age": 241,
  "closed": 261,
  "extra": {
   "max_open": 6
  },
  "open": 3,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:33:23.694069+00:00"
 },
 "nav-cook-lshadow": {
  "age": 41,
  "closed": 3,
  "extra": {
   "caps": {
    "band_bps": [
     45.0,
     60.0
    ],
    "clip_usd": 240.0,
    "confirm_loops": 7,
    "confirm_s": 630,
    "crypto_only": false,
    "excluded_classes": [
     7
    ],
    "exit_bps": 30.0,
    "gross_max_usd": 960.0,
    "hard_stop": 0.05,
    "max_entry_slip_bps": 30.0,
    "max_hold_s": 14400.0,
    "max_positions": 4,
    "min_vol_m": 0.5,
    "study_confirm_s": 600.0,
    "tiles_with": "band-kelly >= 60bps (disjoint by construction)",
    "universe_n": 40
   },
   "held": {},
   "scan": {
    "above_band": 0,
    "below_band": 40,
    "capped": 0,
    "confirming": 0,
    "held": 0,
    "in_band": 0,
    "no_book": 0,
    "opened": 0,
    "preipo": 0,
    "ref_blind": 0,
    "resize_blind": 0,
    "scanned": 40,
    "slip": 0
   }
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:36:44.101882+00:00"
 },
 "perps-funding-carry-lshadow": {
  "age": 78,
  "closed": 104,
  "extra": {
   "caps": {
    "crypto_only": true,
    "depth_admit": true,
    "enter_apr": 0.2,
    "flip_grace_h": 6.0,
    "max_positions": 20,
    "max_vol": null,
    "min_vol": 1000000.0,
    "payback_max_h": 48.0,
    "persist_h": 12.0
   },
   "scan": {
    "cold": 196,
    "depth_admitted": 0,
    "depth_probes": 0,
    "eligible": 0,
    "held": 18,
    "next": "HBAR",
    "next_eta_h": 4.33,
    "noncrypto": 0,
    "scanned": 228,
    "thin": 11,
    "waiting": 3,
    "waiting_admissible": 1
   }
  },
  "open": 18,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:36:06.778401+00:00"
 },
 "perps-funding-spread-lshadow": {
  "age": 281,
  "closed": 141,
  "extra": {
   "caps": {
    "crypto_only": true,
    "k": 5,
    "legs": 10,
    "universe": 25,
    "universe_n": 30
   },
   "held": {
    "AAVE": "S",
    "ADA": "L",
    "APT": "L",
    "DOT": "L",
    "LTC": "L",
    "NEAR": "S",
    "PYTH": "L",
    "SOL": "S",
    "SUI": "S",
    "WIF": "S"
   }
  },
  "open": 10,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:32:43.663276+00:00"
 },
 "pm-turnbull-lshadow": {
  "age": 11,
  "closed": 23,
  "extra": {
   "held": {}
  },
  "open": 0,
  "stale": false,
  "status": "online",
  "updated": "2026-08-27T12:37:14.484080+00:00"
 }
}
""")


def row(bot, **over):
    """A /pnl.json row rebuilt from the captured transcript for `bot`."""
    r = LIVE_ROWS[bot]
    out = {"bot": bot, "kind": "trading", "status": r["status"],
           "open_trades": r["open"], "closed_trades": r["closed"],
           "stale": r["stale"], "age_sec": r["age"],
           "updated_at": r["updated"], "extra": json.loads(json.dumps(
               r["extra"]))}
    out.update(over)
    return out


def verdict(bot, **over):
    return sv.classify([sv.observe(row(bot, **over), TS)])


def repeat(r, n, distinct_publishes=True):
    """n observations of one book. `distinct_publishes=False` re-reads ONE
    publish n times — which is n samples and ONE observation."""
    obs = []
    for i in range(n):
        rr = json.loads(json.dumps(r))
        if distinct_publishes:
            rr["updated_at"] = f"2026-08-27T{10 + i:02d}:00:00+00:00"
        obs.append(sv.observe(rr, f"2026-08-27T{10 + i:02d}:00:05+00:00"))
    return obs


# ── the four real cases the prototype measured ──────────────────────────────
def test_a_full_book_with_zero_closes_is_SLOW_not_undecidable():
    """🧮 Hull: 6 of 6 slots held, 0 closes, ~6 closes/30d DECLARED AT BIRTH.
    The docket calls this `zero_ledger`; occupancy calls it a hold time."""
    v = verdict("book-hull-lshadow")
    assert v.state == "SLOW", v
    assert v.evidence["open"] == 6 and v.evidence["cap"] == 6
    assert "DEPLOYED" in v.why and "HOLD TIME" in v.why


def test_the_second_full_book_reads_the_same_way():
    v = verdict("book-kiyosaki-lshadow")
    assert v.state == "SLOW", v
    assert v.evidence["open"] == 6 and v.evidence["cap"] == 6


def test_FULL_is_said_only_when_the_book_is_actually_AT_its_cap():
    """"Holding at its OWN cap" is the claim the whole instrument rests on, and
    the `>=` that decides it was untested — `>` reddened nothing (found by
    mutation), because no case checked for the word. Driven both ways."""
    v = verdict("book-hull-lshadow")
    assert v.state == "SLOW" and "6/6 slots" in v.why
    assert "FULL" in v.why, v.why

    below = verdict("book-hull-lshadow", open_trades=3)
    assert below.state == "SLOW" and "3/6 slots" in below.why
    assert "FULL" not in below.why, below.why


def test_grimes_is_REFUSED_by_its_own_gate():
    """📐 Grimes: empty, 8 setups signalled, its own replay gate closed all
    three — the census names the bucket, so nothing is stuck."""
    v = verdict("book-grimes-lshadow")
    assert v.state == "REFUSING", v
    assert v.evidence["supply"] == 8
    assert v.evidence["top_refusal"][0] == "gated"


def test_navcook_is_REFUSED_below_its_own_band():
    """🧭 nav-cook: 40 scanned, essentially all below the [45,60) bps band."""
    v = verdict("nav-cook-lshadow")
    assert v.state == "REFUSING", v
    assert v.evidence["scanned"] == 40
    assert v.evidence["top_refusal"][0] == "below_band"


def test_a_refusal_bucket_outranks_a_missing_scan_denominator():
    """🎯 the sniper publishes NO `scanned` key and `not_young: 69`. Reading a
    missing denominator as "nothing to refuse" would invert the finding."""
    v = verdict("lighter-perp-sniper-lshadow")
    assert v.state == "REFUSING", v
    assert v.evidence["scanned"] is None
    assert v.evidence["top_refusal"][0] == "not_young"


def test_supply_is_inferred_when_the_census_accounts_for_the_whole_scan():
    """👩 mum publishes no eligible count — but her `verdicts` map accounts for
    every candidate, so supply is INFERRED zero rather than left unreadable."""
    v = verdict("freqtrade-mum-lighter")
    assert v.state == "REFUSING", v
    assert v.evidence["supply"] == 0 and v.evidence["supply_inferred"] is True
    assert v.evidence["top_refusal"][0] == "verdicts.no_signal"


def test_a_book_with_no_census_is_UNKNOWN_and_says_so():
    """🏛️ Turnbull: empty, and publishes no census at all. I18 — that gap is
    the finding, and it must never resolve to a confident verdict."""
    v = verdict("pm-turnbull-lshadow")
    assert v.state == "UNKNOWN", v
    assert "NO census" in v.why


# ── the negative control ────────────────────────────────────────────────────
@pytest.mark.parametrize("bot", ["lighter-ticket-taker-lshadow",
                                 "perps-funding-carry-lshadow",
                                 "perps-funding-spread-lshadow",
                                 "band-kelly-lshadow"])
def test_a_healthy_trading_book_is_TRADING_and_never_STUCK(bot):
    """THE NEGATIVE CONTROL. However many samples, however deep the window, a
    book that is holding and closing must never assert a defect."""
    assert verdict(bot).state == "TRADING"
    for n in (1, sv.MIN_STUCK_PUBLISHES, sv.MIN_STUCK_PUBLISHES + 4):
        v = sv.classify(repeat(row(bot), n))
        assert v.state == "TRADING", (bot, n, v)
        assert not v.asserts_defect


def test_a_refusing_book_never_becomes_stuck_by_being_sampled_more():
    """🧭 nav-cook refused on every loop of a deep window is still REFUSING —
    persistence of a NAMED reason is not evidence of a defect."""
    for n in (sv.MIN_STUCK_PUBLISHES, sv.MIN_STUCK_PUBLISHES + 5):
        v = sv.classify(repeat(row("nav-cook-lshadow"), n))
        assert v.state == "REFUSING", (n, v)
        assert not v.asserts_defect


# ── SUPPLY_EMPTY ────────────────────────────────────────────────────────────
def test_SUPPLY_EMPTY_requires_no_scan_AND_no_refusal():
    """No living book is in this state today, so it is exercised on a census
    edited to say what SUPPLY_EMPTY means: nothing reached the gate."""
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 0, "in_band": 0, "opened": 0}
    assert sv.classify([sv.observe(r, TS)]).state == "SUPPLY_EMPTY"

    # one refusal bucket is proof it looked -> REFUSING, not SUPPLY_EMPTY
    r["extra"]["scan"]["below_band"] = 7
    assert sv.classify([sv.observe(r, TS)]).state == "REFUSING"


def test_a_scan_with_no_bucket_at_all_is_REFUSING_and_blames_the_census():
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 40, "in_band": 0}
    v = sv.classify([sv.observe(r, TS)])
    assert v.state == "REFUSING", v
    assert "NO bucket names the refusal" in v.why


# ── STUCK: the only state that asserts a defect ─────────────────────────────
def _stuck_row():
    """🧭 nav-cook's real row with the census saying the one thing that has no
    innocent reading: 3 candidates passed its OWN gate, slots free, opened
    nothing, and not one bucket explains it."""
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 40, "in_band": 3, "opened": 0,
                          "below_band": 0, "above_band": 0, "confirming": 0,
                          "slip": 0, "capped": 0, "preipo": 0}
    return r


def test_STUCK_is_unreachable_from_one_snapshot():
    v = sv.classify([sv.observe(_stuck_row(), TS)])
    assert v.state == "UNKNOWN", v
    assert "snapshot is not a structural verdict" in v.why
    assert str(sv.MIN_STUCK_PUBLISHES) in v.why


def test_STUCK_needs_DISTINCT_publishes_not_repeat_reads():
    """A sensor cannot outrun its own sampling rate. Re-reading ONE publish
    many times is one observation told many times."""
    many = repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES + 3,
                  distinct_publishes=False)
    v = sv.classify(many)
    assert v.samples == sv.MIN_STUCK_PUBLISHES + 3
    assert v.publishes == 1
    assert v.state == "UNKNOWN", v
    assert not v.asserts_defect


def test_STUCK_fires_once_MIN_distinct_publishes_agree():
    obs = repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES)
    v = sv.classify(obs)
    assert v.state == "STUCK", v
    assert v.asserts_defect
    assert v.publishes == sv.MIN_STUCK_PUBLISHES
    assert "NOTHING in its census explains" in v.why


def test_one_publish_short_of_the_bar_is_UNKNOWN_not_STUCK():
    obs = repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES - 1)
    assert sv.classify(obs).state == "UNKNOWN"


def test_TWO_distinct_publishes_can_never_assert_a_defect():
    """THE BAR IS THREE, AND THE VALUE IS THE ARGUMENT — not just the role.

    Every other test here reads `MIN_STUCK_PUBLISHES` symbolically, so walking
    it 3 -> 2 reddened NOTHING (found by mutation). The module argues the value
    in prose — *"Three, not two: two consecutive loops of a bot with a slow
    cadence is one story told twice"* — and a doctrine only prose defends is
    the thing this repo has paid for repeatedly. Driven, not asserted as a
    constant: two agreeing publishes must still refuse to assert a defect."""
    v = sv.classify(repeat(_stuck_row(), 2))
    assert v.publishes == 2
    assert v.state == "UNKNOWN", v
    assert not v.asserts_defect


# ── window + ORDER ──────────────────────────────────────────────────────────
def test_the_window_is_deeper_than_the_bar_and_ORDER_decides():
    """More observations than MIN_STUCK_PUBLISHES, and the LATEST one decides
    the state. A one-row-per-key fixture cannot test a window at all."""
    n = sv.MIN_STUCK_PUBLISHES + 3
    obs = repeat(_stuck_row(), n)
    assert len(obs) == n
    assert sv.classify(obs).state == "STUCK"

    healed = row("nav-cook-lshadow", open_trades=2,
                 updated_at="2026-08-27T23:00:00+00:00")
    later = obs + [sv.observe(healed, "2026-08-27T23:00:05+00:00")]
    v = sv.classify(later)
    assert v.state == "TRADING", v          # it is holding again, and closes
    assert not v.asserts_defect

    # ORDER, not membership: the same rows with the healthy one FIRST are
    # still a stuck book, because the latest observation is stuck-shaped and
    # the run is no longer unanimous.
    reordered = [sv.observe(healed, "2026-08-27T09:00:05+00:00")] + obs
    assert sv.classify(reordered).state == "UNKNOWN"


def test_the_LATEST_sample_is_the_newest_TIMESTAMP_not_the_last_in_the_list():
    """Samples arrive as a list, and a caller may hand them over in any order
    — a replay of saved snapshots, a retry, a merge. "Latest" must mean the
    newest `sampled_at`, so the same set of observations gives the same
    verdict however it is arranged."""
    stuck = repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES)
    healed = row("nav-cook-lshadow", open_trades=2,
                 updated_at="2026-08-27T23:00:00+00:00")
    newest = sv.observe(healed, "2026-08-27T23:00:05+00:00")

    # newest LAST in the list, and newest FIRST — same answer
    assert sv.classify(stuck + [newest]).state == "TRADING"
    assert sv.classify([newest] + stuck).state == "TRADING"

    # and the mirror: an OLD healthy sample handed over last must not be
    # mistaken for the current state
    old = sv.observe(row("nav-cook-lshadow", open_trades=2,
                         updated_at="2026-08-27T01:00:00+00:00"),
                     "2026-08-27T01:00:05+00:00")
    assert sv.classify(stuck + [old]).state == "UNKNOWN"


def test_one_innocent_sample_in_the_window_clears_the_defect_assertion():
    obs = repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES)
    innocent = _stuck_row()
    innocent["extra"]["scan"]["confirming"] = 1      # a named reason
    innocent["updated_at"] = "2026-08-27T22:00:00+00:00"
    v = sv.classify(obs + [sv.observe(innocent, "2026-08-27T22:00:05+00:00")])
    assert v.state == "REFUSING", v
    assert not v.asserts_defect


def _holding(r):
    r["open_trades"] = 2
    return r


def _no_open_count(r):
    r.pop("open_trades")
    return r


def _stale(r):
    r["stale"] = True
    return r


def _no_census(r):
    r["extra"].pop("scan")
    return r


def _cap_zero(r):
    r["extra"].pop("caps")
    r["extra"].pop("scan")
    r["extra"]["census"] = {"free_slots": 0, "held": 0, "scanned": 40,
                            "in_band": 3}
    return r


def _census_holds(r):
    r["extra"]["scan"]["held"] = 2
    return r


def _census_opened(r):
    r["extra"]["scan"]["opened"] = 1
    return r


def _supply_unreadable(r):
    r["extra"]["scan"] = {"held": 0, "scanned": 40}      # no eligible-equiv
    return r


def _supply_zero(r):
    r["extra"]["scan"]["in_band"] = 0
    return r


def _explained(r):
    r["extra"]["scan"]["confirming"] = 2                 # a NAMED reason
    return r


#: Every innocent reading of one observation. Each is a way the book could be
#: fine, and `_stuck_shaped` must check all of them — but they are reachable
#: ONLY through history, because `classify` routes a LATEST sample of each
#: shape somewhere else long before the stuck branch runs. The first mutation
#: round of this suite found three of them untested.
INNOCENT_CLAUSES = {
    "holding": _holding,
    "no_open_count": _no_open_count,
    "stale": _stale,
    "no_census": _no_census,
    "cap_zero": _cap_zero,
    "census_holds_what_the_row_denies": _census_holds,
    "census_opened_this_loop": _census_opened,
    "supply_unreadable": _supply_unreadable,
    "supply_zero": _supply_zero,
    "explained": _explained,
}


#: The reason each clause must give. Asserting the REASON and not just the
#: refusal is what makes a redundant clause testable: drop `no_census` and the
#: observation is still refused — by `supply is None`, under a different name.
#: A guard that only ever agrees with the next guard is one a reader will
#: delete, so the name it gives is the thing worth pinning.
CLAUSE_REASON = {
    "holding": "book is holding",
    "no_open_count": "row publishes no open count",
    "stale": "row is stale",
    "no_census": "no census",
    "cap_zero": "cap is zero",
    "census_holds_what_the_row_denies": "census says it holds positions",
    "census_opened_this_loop": "census says it opened this loop",
    "supply_unreadable": "census publishes no supply count",
    "supply_zero": "no supply passed its gate",
    "explained": "census names a reason",
}


@pytest.mark.parametrize("clause", sorted(INNOCENT_CLAUSES))
def test_each_innocent_clause_refuses_for_ITS_OWN_reason(clause):
    ok, why = sv._stuck_shaped(
        sv.observe(INNOCENT_CLAUSES[clause](_stuck_row()), TS))
    assert ok is False, clause
    assert CLAUSE_REASON[clause] in why, (clause, why)


def test_the_clause_table_is_complete():
    """A new innocent clause added to the module without a case here would
    otherwise ship untested — the shape this suite exists to prevent."""
    assert set(CLAUSE_REASON) == set(INNOCENT_CLAUSES)
    ok, why = sv._stuck_shaped(sv.observe(_stuck_row(), TS))
    assert (ok, why) == (True, ""), "the positive case must still be positive"


@pytest.mark.parametrize("clause", sorted(INNOCENT_CLAUSES))
def test_one_innocent_EARLIER_sample_blocks_the_defect_assertion(clause):
    """The window must be UNANIMOUS, and unanimity is judged per observation.

    The latest sample here is stuck-shaped in every case, so `classify`'s own
    branches cannot see the innocent one — only `_stuck_shaped` can, which is
    exactly why each clause needs its own case."""
    earlier = INNOCENT_CLAUSES[clause](_stuck_row())
    earlier["updated_at"] = "2026-08-27T08:00:00+00:00"
    window = ([sv.observe(earlier, "2026-08-27T08:00:05+00:00")]
              + repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES))
    v = sv.classify(window)
    assert not v.asserts_defect, (clause, v)
    assert v.state == "UNKNOWN", (clause, v)


def test_the_positive_control_for_that_window():
    """POSITIVE CONTROL — without an innocent sample the SAME window shape
    does assert the defect, so the cases above measure the clauses and not
    the window length. A guard that never fires is trivially safe and
    useless (I3 applied to this suite itself)."""
    earlier = sv.observe(_stuck_row(), "2026-08-27T08:00:05+00:00")
    earlier.published_at = "2026-08-27T08:00:00+00:00"
    window = [earlier] + repeat(_stuck_row(), sv.MIN_STUCK_PUBLISHES)
    v = sv.classify(window)
    assert v.state == "STUCK", v
    assert v.publishes == sv.MIN_STUCK_PUBLISHES + 1


# ── I1: liveness before semantics ───────────────────────────────────────────
def test_a_STALE_row_is_never_read_for_semantics_however_stuck_shaped():
    r = _stuck_row()
    r["stale"] = True
    assert sv.classify([sv.observe(r, TS)]).state == "UNKNOWN"
    deep = repeat(r, sv.MIN_STUCK_PUBLISHES + 2)
    v = sv.classify(deep)
    assert v.state == "UNKNOWN", v
    assert "STALE" in v.why and not v.asserts_defect


def test_staleness_falls_back_to_age_when_the_feed_omits_its_verdict():
    """Driven on a REFUSING book, so "stale" and "read normally" are two
    DIFFERENT verdicts — on a stuck-shaped row both read UNKNOWN and the test
    would pass while measuring nothing."""
    def st(r, thr=None):
        return sv.classify([sv.observe(r, TS, thr)])

    r = row("nav-cook-lshadow")
    r.pop("stale")
    r["age_sec"] = 5
    assert st(r).state == "REFUSING"

    r["age_sec"] = sv.FALLBACK_STALE_S + 1
    v = st(r)
    assert v.state == "UNKNOWN" and "STALE" in v.why, v

    # the feed's OWN per-book threshold is preferred over the fallback: the
    # same age is stale for a 180s book and fine for a 93600s stock book
    r["age_sec"] = 400
    assert st(r, 180).state == "UNKNOWN"
    assert st(r, 93600).state == "REFUSING"

    # an age the feed does not publish either is refused, never assumed fresh
    r.pop("age_sec")
    assert st(r, 180).state == "UNKNOWN"


def test_the_stale_FALLBACK_is_tight_enough_to_catch_a_dead_row():
    """`FALLBACK_STALE_S` is a FAIL-SAFE bound, and the test above reads it
    symbolically (`FALLBACK_STALE_S + 1`) — so it could be walked to ten days
    and nothing reddened (found by mutation). The bracket is driven from both
    sides: a 5-second row must still be READ (the test above), and an hour-old
    row with no verdict from the feed must read STALE."""
    r = row("nav-cook-lshadow")
    r.pop("stale")
    r["age_sec"] = 3600
    v = sv.classify([sv.observe(r, TS)])
    assert v.state == "UNKNOWN" and "STALE" in v.why, v


def test_the_feeds_OWN_stale_threshold_reaches_the_books_THROUGH_audit():
    """The per-book threshold is read in `audit()` and PASSED to `observe()`,
    and every row in the transcript carries its own `stale` boolean — so that
    whole argument could be DELETED and nothing reddened (found by mutation:
    `observe(row, ts, thr)` -> `observe(row, ts)` survived).

    Driven on rows that OMIT `stale`, where the threshold is the only thing
    that can decide, and through `audit()` rather than `observe()` so the
    wiring itself is what is under test."""
    def docs(thr):
        d = {"meta": {"generated_at": TS, "stale_threshold_sec": thr},
             "bots": []}
        for b in ("nav-cook-lshadow", "book-hull-lshadow"):
            r = row(b)
            r.pop("stale")
            r["age_sec"] = 400          # 400s: stale for a 180s book, fine
            d["bots"].append(r)         # for a 93600s one
        return [(TS, d)]

    tight, _, _, _ = sv.audit(docs(180))
    assert tight["nav-cook-lshadow"].state == "UNKNOWN"
    assert "STALE" in tight["nav-cook-lshadow"].why
    assert tight["book-hull-lshadow"].state == "UNKNOWN"

    # the SAME rows at the stock books' own threshold are read normally — two
    # DIFFERENT verdicts, so this measures the threshold and not the row
    loose, _, _, _ = sv.audit(docs(93600))
    assert loose["nav-cook-lshadow"].state == "REFUSING"
    assert loose["book-hull-lshadow"].state == "SLOW"


def test_a_halted_or_standby_row_is_a_different_question():
    for status in ("halted", "standby", "retired-ish"):
        v = sv.classify([sv.observe(row("nav-cook-lshadow", status=status),
                                    TS)])
        assert v.state == "UNKNOWN", (status, v)


def test_mid_loop_skew_between_census_and_row_is_refused():
    """Asserting the REASON, not just UNKNOWN: a stuck-shaped row already
    reads UNKNOWN from one sample, so a state-only assertion here passes
    whether or not the skew branch exists at all."""
    r = _stuck_row()
    r["extra"]["scan"]["held"] = 2            # census holds, row says empty
    v = sv.classify([sv.observe(r, TS)])
    assert v.state == "UNKNOWN" and "census says held=2" in v.why, v

    r["extra"]["scan"]["held"] = 0
    r["extra"]["scan"]["opened"] = 1
    v = sv.classify([sv.observe(r, TS)])
    assert v.state == "UNKNOWN" and "opened=1" in v.why, v

    # and the skew must not silently become a defect on a deep window either
    r["extra"]["scan"]["opened"] = 0
    r["extra"]["scan"]["held"] = 2
    assert not sv.classify(repeat(r, sv.MIN_STUCK_PUBLISHES)).asserts_defect


# ── readers ─────────────────────────────────────────────────────────────────
def test_cap_is_read_from_every_shape_the_fleet_publishes():
    assert sv.read_cap(row("book-hull-lshadow")) == (
        6, "extra.caps.max_positions")
    assert sv.read_cap(row("lighter-ticket-taker-lshadow")) == (
        6, "extra.max_open")
    assert sv.read_cap(row("lighter-perp-sniper-lshadow")) == (
        4, "extra.caps.max_open")
    assert sv.read_cap({"extra": {"census": {"free_slots": 2, "held": 4}}}) == (
        6, "extra.census.free_slots+held")
    # an unknown cap is None and is NEVER guessed (I8)
    assert sv.read_cap(row("pm-turnbull-lshadow")) == (None, None)


def test_a_published_ZERO_cap_does_not_shadow_a_real_one():
    """`max_positions: 0` is a book with no slot, not a cap — the reader must
    keep looking rather than hand the operator an occupancy of `0/0` while a
    real cap sits one field away. No live row publishes a zero cap, so dropping
    the `> 0` guard reddened nothing (found by mutation)."""
    r = row("book-hull-lshadow")
    r["extra"]["caps"]["max_positions"] = 0
    r["extra"]["caps"]["max_open"] = 3
    assert sv.read_cap(r) == (3, "extra.caps.max_open")


def test_telemetry_is_never_counted_as_a_refusal_bucket():
    """🪁 band-kelly's census carries dev_med_bps / dev_p98_bps / dev_max_bps
    beside its counts, and 👩 mum's carries `rsi_bar: 30.0` — an integral float
    that is a THRESHOLD, not a candidate. Counting either would rename the
    binding gate in the operator's report."""
    c = sv.read_census(row("band-kelly-lshadow"))
    for k in c.explanations:
        assert not k.endswith("_bps"), k
    assert "below_gate" in c.explanations

    c = sv.read_census(row("freqtrade-mum-lighter"))
    assert "rsi_bar" not in c.explanations
    assert c.top_explanation[0] == "verdicts.no_signal"

    # THE GENERIC DEFENCE, and it is what carries a census this suite has
    # never seen: a bucket is a COUNT of candidates. Every fractional field in
    # today's fleet also happens to carry a telemetry NAME, so the name test
    # alone looks sufficient and is not — a book publishing `queue_avg: 3.7`
    # would otherwise be reported as refusing 3 candidates it never had.
    r = row("nav-cook-lshadow")
    r["extra"]["scan"].update({"queue_avg": 3.7, "blocked_ratio": 0.42,
                               "hit": 0.5, "below_band": 4})
    c = sv.read_census(r)
    assert set(c.explanations) == {"below_band"}, c.explanations
    assert c.top_explanation == ("below_band", 4)

    # NOR IS A FLAG A COUNT. `True` is an int in Python, and a census may
    # legitimately carry one — the (ly) sleeve retirement publishes
    # `retired: true` beside its counts precisely so the call stays
    # falsifiable. Counted, it becomes a phantom refusal of one candidate.
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 40, "in_band": 3,
                          "opened": 0, "retired": True, "crypto_only": False}
    c = sv.read_census(r)
    assert c.explanations == {}, c.explanations
    assert c.supply == 3


def test_the_supply_field_that_WINS_is_pinned_and_NAMED():
    """A census may publish more than one eligible-equivalent count, and the
    reader takes the FIRST match in `SUPPLY_FIELDS`. No live row publishes two,
    so reordering that tuple reddened nothing (found by mutation) — and nothing
    asserted `supply_field`, which is the evidence line telling the operator
    WHICH number the verdict was read from."""
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 40, "eligible": 2,
                          "in_band": 7, "below_band": 31}
    c = sv.read_census(r)
    assert (c.supply, c.supply_field) == (2, "eligible"), c
    assert sv.classify([sv.observe(r, TS)]).evidence["supply_field"] == \
        "eligible"


def test_a_capacity_field_inside_a_census_is_not_a_refusal_bucket():
    """🎯 the sniper's census carries `max_open: 4` beside its counts: the
    book's own capacity, not four candidates it turned away. It never surfaced
    because `not_young: 69` is larger, so dropping the capacity/display names
    from the exclusion set reddened nothing (found by mutation)."""
    c = sv.read_census(row("lighter-perp-sniper-lshadow"))
    for f in ("max_open", "free_slots", "top", "next"):
        assert f not in c.explanations, (f, c.explanations)

    # ...and it must stay out even when it is the LARGEST number in the census
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 0, "scanned": 40, "in_band": 0,
                          "max_open": 99, "free_slots": 40, "below_band": 3}
    c = sv.read_census(r)
    assert c.top_explanation == ("below_band", 3), c.explanations


def test_extra_scan_OUTRANKS_extra_census_and_the_SOURCE_is_published():
    """Most books publish `extra.scan`; the funding variants publish
    `extra.census`. No live row publishes both, so flipping the precedence
    reddened nothing (found by mutation) — and nothing asserted which source a
    verdict was actually read from."""
    r = row("nav-cook-lshadow")
    r["extra"]["census"] = {"held": 0, "scanned": 1, "in_band": 1}
    c = sv.read_census(r)
    assert (c.source, c.scanned) == ("extra.scan", 40), c
    assert sv.classify([sv.observe(r, TS)]).evidence["census"] == "extra.scan"

    # a book that publishes ONLY `extra.census` is still read
    r["extra"].pop("scan")
    assert sv.read_census(r).source == "extra.census"


def test_supply_is_inferred_when_the_buckets_EXACTLY_account_for_the_scan():
    """THE INFERENCE BAR IS `>=`, AND ITS BOUNDARY IS THE WHOLE RULE.

    No live census reaches it exactly — 👩 mum's buckets OVER-account (25 of a
    23-coin universe, because `near_bar` overlaps her verdict map) — so `>=` ->
    `>` reddened nothing (found by mutation). A census that accounts for every
    candidate and not one more has said, in its own numbers, where they all
    went; that is exactly when zero supply may be inferred."""
    r = row("nav-cook-lshadow")
    r["extra"]["scan"] = {"held": 4, "scanned": 10, "below_band": 6}
    c = sv.read_census(r)
    assert c.supply == 0 and c.supply_inferred is True, c

    # ONE SHORT of accounting for the scan leaves supply UNREADABLE, never 0 —
    # the fail-safe direction, because an inferred zero routes to REFUSING
    r["extra"]["scan"]["below_band"] = 5
    assert sv.read_census(r).supply is None


def test_a_dark_feed_is_DIAGNOSED_by_which_way_it_is_dark():
    """Both dark shapes raise `ValueError`, so the fail-closed test above
    cannot tell them apart — and collapsing the first guard into the second
    makes the message a LIE ("carried rows but no living book rows" about a
    feed that carried none). I8: a detector must name the thing the operator
    has to act on. Found by mutation: the first guard could be removed."""
    with pytest.raises(ValueError, match="carried no rows"):
        sv.book_rows({})                       # no `bots` key at all
    with pytest.raises(ValueError, match="carried no rows"):
        sv.book_rows({"bots": []})             # the key, and nothing in it
    with pytest.raises(ValueError, match="no living book rows"):
        sv.book_rows({"bots": [{"bot": "market-context", "kind": "organ"}]})


def test_a_book_row_that_is_not_a_book_is_skipped_not_misgraded():
    doc = {"meta": {}, "bots": [row("book-hull-lshadow"),
                                {"bot": "market-context", "kind": "organ"},
                                {"bot": "old", "kind": "trading",
                                 "status": "retired"}]}
    rows = sv.book_rows(doc)
    assert [r["bot"] for r in rows] == ["book-hull-lshadow"]


# ── the docket cross-reference ──────────────────────────────────────────────
DOCKET = [
    {"book": "book-hull-lshadow", "reason": "zero_ledger",
     "why": "no closes ever — undecidable until the book closes trades",
     "asks": "keep-or-retire (I17) — an operator decision, not a tuning pass",
     "since": "2026-08-13T23:58:11+00:00", "days_held": 12.5},
    {"book": "book-kiyosaki-lshadow", "reason": "zero_ledger",
     "why": "no closes ever — undecidable until the book closes trades",
     "asks": "keep-or-retire (I17) — an operator decision, not a tuning pass",
     "since": "2026-08-13T05:48:24+00:00", "days_held": 13.2},
    {"book": "book-grimes-lshadow", "reason": "zero_ledger",
     "why": "no closes ever — undecidable until the book closes trades",
     "asks": "keep-or-retire (I17) — an operator decision, not a tuning pass",
     "since": "2026-08-13T23:58:11+00:00", "days_held": 12.5},
    {"book": "lighter-ticket-taker-lshadow", "reason": "unreachable",
     "why": "mean <= 0", "asks": "keep-or-retire (I17)",
     "since": "2026-08-18T05:03:19+00:00", "days_held": 7.3},
    {"book": "pm-turnbull-lshadow", "reason": "undecidable",
     "why": "needs ~2400d at the measured rate",
     "asks": "keep-or-retire (I17)",
     "since": "2026-08-07T13:16:32+00:00", "days_held": 18.9},
]

BUS = {"golive_readiness": {
    "updated": "2026-08-27T10:54:07+00:00",
    "decision_docket": DOCKET,
    "books": {"lighter-ticket-taker-lshadow": {
        "n": 117, "days": 25.3,
        "horizon": {"verdict": "on_track", "why": "t bar binds: ~60.7d"}}},
    "below_floor": {"book-hull-lshadow": {
        "horizon": {"verdict": "no_rate", "why": "no closes ever"}}}}}


def _full_doc(samples=1):
    doc = {"meta": {"generated_at": "2026-08-27T12:40:00+00:00",
                    "stale_threshold_sec": 180},
           "bots": [row(b) for b in sorted(LIVE_ROWS)]}
    return [(f"2026-08-27T12:4{i}:00+00:00", json.loads(json.dumps(doc)))
            for i in range(samples)]


def test_the_docket_cross_reference_FIRES_on_a_SLOW_book_it_would_retire():
    """THE POINT OF THE WHOLE INSTRUMENT. Two of the three `zero_ledger` books
    on the live docket are holding at their own cap."""
    _, reads, _, _ = sv.audit(_full_doc(), BUS)
    by_book = {r["book"]: r for r in reads}
    for bot in ("book-hull-lshadow", "book-kiyosaki-lshadow"):
        r = by_book[bot]
        assert r["state"] == "SLOW", r
        assert r["misread"] is True, r
        assert r["docket_reason"] == "zero_ledger"
    assert sum(1 for r in reads if r["misread"]) == 2


def test_the_docket_cross_reference_does_NOT_fire_on_the_others():
    """A flag that fires on everything trains the operator to ignore it."""
    _, reads, _, _ = sv.audit(_full_doc(), BUS)
    by_book = {r["book"]: r for r in reads}
    assert by_book["book-grimes-lshadow"]["state"] == "REFUSING"
    assert by_book["book-grimes-lshadow"]["misread"] is False
    assert by_book["lighter-ticket-taker-lshadow"]["state"] == "TRADING"
    assert by_book["lighter-ticket-taker-lshadow"]["misread"] is False
    assert by_book["pm-turnbull-lshadow"]["state"] == "UNKNOWN"
    assert by_book["pm-turnbull-lshadow"]["misread"] is False


def test_a_docket_entry_for_a_book_absent_from_the_feed_is_not_a_verdict():
    bus = json.loads(json.dumps(BUS))
    bus["golive_readiness"]["decision_docket"] = [
        {"book": "band-barnes-lshadow", "reason": "zero_ledger",
         "asks": "keep-or-retire", "since": "2026-08-01T00:00:00+00:00",
         "days_held": 25.0}]
    _, reads, _, _ = sv.audit(_full_doc(), bus)
    assert reads[0]["state"] == "UNKNOWN"
    assert reads[0]["misread"] is False
    assert "not in the /pnl.json feed" in reads[0]["why"]


def test_the_gate_is_READ_never_recomputed():
    gv, docket, updated = sv.gate_view(BUS)
    assert gv["book-hull-lshadow"]["verdict"] == "no_rate"
    assert gv["lighter-ticket-taker-lshadow"]["n"] == 117
    assert len(docket) == len(DOCKET)
    assert updated == "2026-08-27T10:54:07+00:00"
    # a dark or shapeless bus degrades to "no docket", never to a guess
    assert sv.gate_view({}) == ({}, [], None)
    assert sv.gate_view({"golive_readiness": None}) == ({}, [], None)
    assert sv.gate_view({"golive_readiness": {"decision_docket": "junk"}})[1] \
        == []


# ── end to end ──────────────────────────────────────────────────────────────
def test_audit_end_to_end_reproduces_the_measured_fleet():
    verdicts, reads, no_census, meta = sv.audit(_full_doc(), BUS)
    assert meta["samples"] == 1
    got = {b: v.state for b, v in verdicts.items()}
    assert got["book-hull-lshadow"] == "SLOW"
    assert got["book-kiyosaki-lshadow"] == "SLOW"
    assert got["book-grimes-lshadow"] == "REFUSING"
    assert got["nav-cook-lshadow"] == "REFUSING"
    assert got["lighter-perp-sniper-lshadow"] == "REFUSING"
    assert got["perps-funding-carry-lshadow"] == "TRADING"
    assert got["pm-turnbull-lshadow"] == "UNKNOWN"
    assert "STUCK" not in set(got.values())      # nothing is stuck today
    assert set(got.values()) <= set(sv.STATES)


def test_the_no_census_section_NAMES_the_books():
    """I18 — the gap is itself the finding, so it is named, not counted."""
    _, _, no_census, _ = sv.audit(_full_doc(), BUS)
    assert "pm-turnbull-lshadow" in no_census
    assert "perps-funding-spread-lshadow" in no_census
    assert "lighter-ticket-taker-lshadow" in no_census
    assert "book-hull-lshadow" not in no_census
    assert no_census == sorted(no_census)


def test_the_no_census_list_reflects_the_LATEST_sample():
    """`classify` reads the newest observation, and the observability list must
    agree with it — otherwise the report names a book blind that has since
    started publishing, or stays silent about one that has stopped. Every
    sample in the other fixtures is byte-identical, so reading the OLDEST
    instead reddened nothing (found by mutation)."""
    def strip(sample):
        for r in sample[1]["bots"]:
            if r["bot"] == "book-hull-lshadow":
                r["extra"].pop("scan")

    first, second = _full_doc(samples=2)
    strip(first)                                   # blind THEN, publishing NOW
    _, _, no_census, _ = sv.audit([first, second])
    assert "book-hull-lshadow" not in no_census

    first, second = _full_doc(samples=2)
    strip(second)                                  # publishing THEN, blind NOW
    _, _, no_census, _ = sv.audit([first, second])
    assert "book-hull-lshadow" in no_census


def test_multi_sample_audit_carries_its_own_sample_count():
    verdicts, _, _, meta = sv.audit(_full_doc(samples=3), BUS)
    assert meta["samples"] == 3
    v = verdicts["book-hull-lshadow"]
    assert v.samples == 3
    # three re-reads of ONE publish is still ONE publish
    assert v.publishes == 1


def test_the_feed_is_FAIL_CLOSED():
    """A dark feed must never read as a clean fleet — a vacuous green here
    would certify exactly the thing the tool exists to catch."""
    for bad in ({}, {"bots": []}, [], {"bots": [{"kind": "organ"}]},
                {"bots": [{"bot": "x", "kind": "trading",
                           "status": "retired"}]}):
        with pytest.raises(ValueError):
            sv.book_rows(bad)
    with pytest.raises(ValueError):
        sv.audit([])


# ── the operator surface ────────────────────────────────────────────────────
def test_times_shown_to_a_human_are_SYDNEY_local():
    out = sv.sydney("2026-08-27T12:40:00+00:00")
    assert "(Sydney)" in out and "2026-08-27 22:40" in out
    assert "AEST" in out or "AEDT" in out
    assert sv.sydney(None) == "unknown"
    assert sv.sydney("not-a-time") == "not-a-time UTC"   # degrades, never dies


def test_the_report_LEADS_with_the_snapshot_caveat_and_names_the_misread():
    verdicts, reads, no_census, meta = sv.audit(_full_doc(), BUS)
    gv, _, _ = sv.gate_view(BUS)
    text = sv.render(verdicts, reads, no_census, meta, gv)
    head = text.split("BOOK ")[0]
    assert "SNAPSHOT ONLY" in head, "the caveat must be above the table"
    assert str(sv.MIN_STUCK_PUBLISHES) in head
    assert "MISREAD" in text
    assert "book-hull-lshadow" in text and "book-kiyosaki-lshadow" in text
    assert "retirement made for the wrong reason" in text
    assert "REFUSING is NOT an alarm" in text
    assert "(Sydney)" in text


def test_the_caveat_disappears_once_the_bar_is_reachable():
    docs = _full_doc(samples=sv.MIN_STUCK_PUBLISHES)
    for i, (ts, doc) in enumerate(docs):
        for r in doc["bots"]:
            r["updated_at"] = f"2026-08-27T{10 + i:02d}:00:00+00:00"
    verdicts, reads, no_census, meta = sv.audit(docs, BUS)
    text = sv.render(verdicts, reads, no_census, meta)
    assert "SNAPSHOT ONLY" not in text


def test_the_header_publishes_the_per_book_publish_RANGE_not_one_number():
    """Books publish on their OWN cadence, so a run that gave one book three
    fresh loops may have re-read another's single loop three times. The header
    claims to say so — and with every fixture book on the same cadence `min`
    and `max` were interchangeable, so the claim was untested (found by
    mutation: collapsing the range to `max–max` reddened nothing).

    Here 🧭 nav-cook never re-publishes while the rest do, which is the honest
    shape of a real polling run."""
    docs = _full_doc(samples=sv.MIN_STUCK_PUBLISHES)
    for i, (_, doc) in enumerate(docs):
        for r in doc["bots"]:
            if r["bot"] == "nav-cook-lshadow":
                continue                          # one loop, read three times
            r["updated_at"] = f"2026-08-27T{10 + i:02d}:00:00+00:00"
    verdicts, reads, no_census, meta = sv.audit(docs, BUS)
    assert verdicts["nav-cook-lshadow"].publishes == 1
    assert verdicts["book-hull-lshadow"].publishes == sv.MIN_STUCK_PUBLISHES

    text = sv.render(verdicts, reads, no_census, meta)
    assert f"per book 1–{sv.MIN_STUCK_PUBLISHES}" in text, text
    # ...and the caveat is suppressed by the book that DID reach the bar, so
    # the range is the only thing telling the operator who did not
    assert "SNAPSHOT ONLY" not in text


def test_states_are_exactly_the_declared_set():
    assert set(sv.STATES) == {"TRADING", "SLOW", "REFUSING", "SUPPLY_EMPTY",
                              "STUCK", "UNKNOWN"}
    assert sv.STATES[0] == "STUCK", "worst news first in the report"


def test_the_rendered_TABLE_actually_leads_with_the_worst_news():
    """`STATES` is declared worst-first and only `STATES[0]` was asserted — the
    TABLE's own ordering was untested, so re-sorting it reddened nothing (found
    by mutation). Read the rendered rows back rather than trusting the loop."""
    verdicts, reads, no_census, meta = sv.audit(_full_doc(), BUS)
    text = sv.render(verdicts, reads, no_census, meta)
    _, _, rest = text.partition(f"{'BOOK':32s}")
    table = rest.split("PUBLISHES NO CENSUS")[0]

    order = []
    for line in table.splitlines():
        parts = line.split()
        if len(parts) > 1 and parts[0] in verdicts and parts[1] in sv.STATES:
            order.append(sv.STATES.index(parts[1]))
    assert len(order) == len(verdicts), (order, len(verdicts))
    assert order == sorted(order), order


# ── the CLI ─────────────────────────────────────────────────────────────────
def _cli(args):
    return subprocess.run([sys.executable,
                           str(ROOT / "scripts" / "audit_stuck_vs_slow.py"),
                           *args], capture_output=True, text=True, timeout=120)


def test_cli_selftest_is_offline_and_green():
    r = _cli(["--selftest"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_exit_codes(tmp_path):
    doc = {"meta": {"generated_at": "2026-08-27T12:40:00+00:00",
                    "stale_threshold_sec": 180},
           "bots": [row(b) for b in sorted(LIVE_ROWS)]}
    pnl = tmp_path / "pnl.json"
    pnl.write_text(json.dumps(doc))
    bus = tmp_path / "bus.json"
    bus.write_text(json.dumps(BUS))

    # a misread docket entry is a FINDING -> exit 1
    r = _cli(["--pnl-json", str(pnl), "--bus-json", str(bus)])
    assert r.returncode == 1, r.stdout + r.stderr
    assert "MISREAD" in r.stdout

    # with no docket to re-read there is nothing to report -> exit 0
    r = _cli(["--pnl-json", str(pnl), "--bus-json", ""])
    assert r.returncode == 0, r.stdout + r.stderr

    # a dark feed is FAIL-CLOSED -> exit 2, never a quiet pass
    dark = tmp_path / "dark.json"
    dark.write_text("{}")
    r = _cli(["--pnl-json", str(dark), "--bus-json", ""])
    assert r.returncode == 2, r.stdout + r.stderr
    assert "FAIL-CLOSED" in r.stdout


def test_cli_json_mode_is_machine_readable(tmp_path):
    doc = {"meta": {"generated_at": "2026-08-27T12:40:00+00:00"},
           "bots": [row(b) for b in sorted(LIVE_ROWS)]}
    pnl = tmp_path / "pnl.json"
    pnl.write_text(json.dumps(doc))
    bus = tmp_path / "bus.json"
    bus.write_text(json.dumps(BUS))
    r = _cli(["--pnl-json", str(pnl), "--bus-json", str(bus), "--json"])
    assert r.returncode == 1, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["books"]["book-hull-lshadow"]["state"] == "SLOW"
    assert any(d["misread"] for d in out["docket"])
    assert "pm-turnbull-lshadow" in out["no_census"]
