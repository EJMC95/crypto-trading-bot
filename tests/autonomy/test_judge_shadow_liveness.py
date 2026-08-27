"""[(va)] THE CONTROL ARM WAS NEVER CHECKED FOR LIFE.

`_pair_precheck`'s `live_row_dark` rung was the ONLY liveness check in the whole
precheck. `fetch_bot_pnl` upserts on a bot primary key, so a dead publisher's
final row persists forever rather than ageing out — and every rung below read
the SHADOW row's last known values as current.

MEASURED by driving the real function: a shadow row TEN DAYS stale returned
verdicts BYTE-IDENTICAL to a fresh one. caps 5v6 -> `capacity_mismatch`, which
the dashboard files under PIPE_WIRE ("a session can clear this week"), sending
someone to align caps against a corpse; caps 5v5 -> `idle`, i.e. JUDGEABLE.
The second is the dangerous one — `idle` is the state a real comparison starts
from. The rungs in front of capacity do not help either: `_latest_policy_stamp`
has no recency window, so a dead arm still yields a policy stamp and parity
passes on it.

I1: establish that something still WRITES a payload before interpreting what it
says. This is a false certification, not a wrong bar, so it fails CLOSED.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import experiment_judge as J        # noqa: E402
import fleet_bus as fb              # noqa: E402

SPEC = dict(fb.JUDGED_PAIRS["georgia"])
LB, SB = SPEC["live_bot"], SPEC["shadow_bot"]

_LIVE_POL = {"strategy": "daytrader-15m", "venue": "lighter_live",
             "stoploss": -0.05, "roi": {"0": 0.02}, "sides": ["long"],
             "scan_order": "diversified", "max_entries_per_hour": None}
_SHADOW_POL = dict(_LIVE_POL, venue="lighter_shadow", scan_order="list",
                   max_entries_per_hour=None)


def _row(bot, now, max_open=5, age=60):
    """The PUBLISHER's shape: `fetch_bot_pnl` carries `updated_at` (ISO)."""
    return {"bot": bot, "updated_at": J.iso(now - age),
            "extra": {"max_open": max_open}}


def _led(bot, pol, now, age=60):
    """The PUBLISHER's shape: `fetch_paper_trades` emits `close_ts`."""
    return {"bot": bot, "close_ts": J.iso(now - age), "extra": {"policy": pol}}


def _verdict(now, shadow_age, live_cap=5, shadow_cap=5, shadow_row=True):
    """Rows are stamped relative to the SAME instant `now` names, whichever
    shape it is handed in — the point under test is that the gate resolves
    that instant, so the fixture must not quietly re-anchor on wall clock.

    The instant is derived HERE, independently, and deliberately NOT via
    `J._epoch`: building the fixture with the function under test made the
    `_epoch` mutation survive, because a corrupted `_epoch` moved the rows and
    the bar together and they stayed consistent. A test must not source its
    expectation from the code it is testing."""
    base = (now.timestamp() if hasattr(now, "timestamp") else float(now))
    rows = [_led(LB, _LIVE_POL, base), _led(SB, _SHADOW_POL, base)]
    bot_rows = [_row(LB, base, live_cap, 60)]
    if shadow_row:
        bot_rows.append(_row(SB, base, shadow_cap, shadow_age))
    v = J._pair_precheck("georgia", SPEC, rows, bot_rows, now)
    return v, (v.get("unjudgeable") or {}).get("reason")


def test_a_dead_control_arm_is_never_certified_judgeable():
    # THE DANGEROUS CASE: caps agree, policy agrees, shadow publisher dead.
    # Before this rung the pair read `idle` — judgeable — off a corpse.
    now = J.now_ts()
    v, reason = _verdict(now, shadow_age=10 * 86400, live_cap=5, shadow_cap=5)
    assert v["phase"] == "unjudgeable", v
    assert reason == "shadow_row_dark", reason
    assert SB in v["unjudgeable"]["detail"], "the reason must NAME the arm (I8)"


def test_a_dead_control_arm_outranks_a_capacity_verdict():
    # caps 5v6 used to publish `capacity_mismatch`, which the dashboard files
    # as a config job — sending a human to align caps while the arm is dead.
    now = J.now_ts()
    _, reason = _verdict(now, shadow_age=10 * 86400, live_cap=5, shadow_cap=6)
    assert reason == "shadow_row_dark", reason


def test_an_absent_shadow_row_is_dark_too():
    now = J.now_ts()
    _, reason = _verdict(now, shadow_age=0, shadow_row=False)
    assert reason == "shadow_row_dark", reason


def test_a_live_control_arm_is_untouched_the_negative_control():
    # A gate that fires on everything is as useless as one that never fires.
    now = J.now_ts()
    v, reason = _verdict(now, shadow_age=60, live_cap=5, shadow_cap=5)
    assert v["phase"] == "idle" and reason is None, v
    _, mismatch = _verdict(now, shadow_age=60, live_cap=5, shadow_cap=6)
    assert mismatch == "capacity_mismatch", mismatch


def test_the_gate_reads_the_clock_it_was_handed_not_the_wall_clock():
    # The in-module selftest drives t0 = 1_800_000_000.0, ~12.2M seconds in the
    # FUTURE of wall clock. Against `now_ts()` every age came out NEGATIVE, so
    # the bar passed for ANY horizon and that selftest could not exercise this
    # gate in either direction — and it would have flipped on 2027-01-15 when
    # t0 becomes the past. Determinism is what makes the rung testable at all.
    t0 = 1_800_000_000.0
    _, fresh = _verdict(t0, shadow_age=60)
    _, stale = _verdict(t0, shadow_age=10 * 86400)
    assert fresh is None, f"a fresh row went dark at a fixed clock: {fresh}"
    assert stale == "shadow_row_dark", \
        f"staleness is invisible at a fixed clock: {stale}"


def test_the_reason_is_in_the_shared_vocabulary_and_its_consumer_map():
    # (tb) inversion: a reason that skips fleet_bus reddens THIS build rather
    # than being erased downstream. And an unmapped reason renders as nothing
    # on the pipeline card, which is a silent blocker.
    assert "shadow_row_dark" in fb.XP_JUDGE_UNJUDGEABLE
    src = (ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    i = src.find("PIPE_PAIR_REASON")
    assert i > 0 and "shadow_row_dark" in src[i:i + 900], \
        "the dashboard does not classify shadow_row_dark — it would render " \
        "as an unexplained blocker on the pipeline card"


def test_a_datetime_now_means_ITS_instant_not_the_wall_clock():
    """`pair_census` has two live callers passing two shapes: `run_once` a
    float, the pipeline-card fixture a `datetime`. `_epoch` normalises them —
    and it must resolve the datetime to ITS OWN instant, not quietly fall back
    to the wall clock, or a fixture driving a fixed moment silently grades
    against "now" and every age it constructs is meaningless.

    Driven at an instant ~12.2M seconds from wall clock so the two answers
    cannot coincide (the mutation `hasattr -> now_ts()` survived a float-only
    suite because at wall clock they agree).
    """
    from datetime import datetime, timezone
    t0 = 1_800_000_000.0
    dt = datetime.fromtimestamp(t0, tz=timezone.utc)

    # rows built RELATIVE TO t0: fresh at t0, ancient against the wall clock
    _, fresh = _verdict(dt, shadow_age=60)
    assert fresh is None, \
        f"a row fresh at the handed instant read dark: {fresh} — `now` " \
        f"resolved to the wall clock instead of the datetime it was given"

    _, stale = _verdict(dt, shadow_age=10 * 86400)
    assert stale == "shadow_row_dark", \
        f"staleness at the handed instant was invisible: {stale}"

    # and the float and datetime spellings of the SAME instant agree exactly
    assert _verdict(t0, shadow_age=60)[1] == _verdict(dt, shadow_age=60)[1]
    assert (_verdict(t0, shadow_age=10 * 86400)[1]
            == _verdict(dt, shadow_age=10 * 86400)[1])
