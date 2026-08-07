"""The brain's regime_timing diagnosis must MEASURE, not restate the tape.

THE INCIDENT (2026-08-07, measured in the live DB before a line was changed):
`bot_state_history` key='regime-oracle' held **1,569 samples over 30.8 days**
and `COUNT(DISTINCT payload->'fleet'->>'read')` was **1** — the value was
"risk-off downtrend" on every single one, zero transitions. `diagnose` rule 4
fired on `counter_share >= 0.7`, the share of a bucket's LOSERS that opened
while that flag read risk-off. Against a constant, that share is identically
**1.0** by arithmetic — and all 10 live `regime_timing` findings read exactly
"100% of matched losses", not one below.

Two invariants were broken at once:
  * I7 — a trigger a book satisfies STRUCTURALLY is not a measurement.
  * I6 — an absence is evidence only against a CONTROL GROUP. Every one of
    those buckets' WINNERS opened in risk-off too; the population where the
    property is absent did not exist.

WHAT IT COST. The minted action gates BOTH sides of a book
(`fleet_bus.entry_regime_gated` -> `parliament/strategies.py:364`). A gated
book takes no trades, so its era bucket freezes (`era_trades` filters on a
FIXED start with no rolling window), the hypothesis re-fires identically every
run, `last_run` tracks `run_no` forever and retirement via PROMOTE_RUNS is
unreachable. The ONLY release is `alive` — the book going silent past
LIVENESS_DAYS. **The gate lifts by declaring the book dead**, then re-fires
once it trades again. Observed: 🏛️ pm-gillard continuously gated 10.6 days and
silent 137.9h; pm-abbott released 5-Aug 10:29Z, opened one position 21:39Z,
re-gated 23:14Z — 12.75h of trading inside a 7.6-day drought.

THE FIX, and it is a SWEEP not an invention: `(jv)` had made the identical
correction two days earlier in `event_sentinel` for the identical shape (a
market-bias constant that gated nothing) — score against a control group
instead of a raw rate. The class was engraved there and never swept; this is
the sweep. Rule 4 now requires the losers' risk-off share to EXCEED the same
share over the bucket's own non-losers by `REGIME_LIFT_MIN`, plus a separate
assertion that the oracle actually varied in the window the rule read.

Fixtures here are deliberately hand-built: `diagnose` is a pure function over
(trades, regime_hist), so these ARE its publisher's shapes — the (hj) rule
bites when a consumer invents a payload shape, which is not the case for a
pure function whose inputs the test constructs from the documented contract.
"""
import datetime as dt

import bot_learn as bl


def _iso(ts):
    """Ledger shape: `open_ts` is an ISO string (`bot_learn._epoch` parses that,
    NOT a bare epoch — a fixture using ints matches nothing and every test over
    it passes vacuously)."""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def _t(pnl, ts, ratio=None):
    """One ledger-shaped closed trade opening at epoch `ts`."""
    return {"profit_abs": pnl, "open_ts": _iso(ts),
            "profit_ratio": ratio if ratio is not None else (0.01 if pnl > 0 else -0.01),
            "exit_reason": "tp" if pnl > 0 else "sl", "pair": "BTC/USDC"}


def _hist(flags, t0=1_785_000_000):
    """Oracle history: one snapshot per hour, `flags` are the risk_off bools."""
    return [{"ts": t0 + i * 3600, "risk_off": f} for i, f in enumerate(flags)]


def _bucket(loser_flags, winner_flags, t0=1_785_000_000):
    """Trades whose opens land on the hours whose risk_off values are given.

    The bucket must be NET NEGATIVE and >= DIAG_MIN_N or `diagnose` returns
    early — that floor is not what this file is testing.
    """
    hist = _hist(loser_flags + winner_flags, t0)
    trades = []
    for i in range(len(loser_flags)):
        trades.append(_t(-1.0, t0 + i * 3600))
    for j in range(len(winner_flags)):
        trades.append(_t(+0.10, t0 + (len(loser_flags) + j) * 3600))
    return trades, hist


def _diagnose(trades, hist):
    return bl.diagnose("pm-gillard-lshadow", "short-disloc", trades, hist,
                       venue_ab={}, drift_budget={"left": 0}, venue_fees=None)


# ---------------------------------------------------------------------------
# THE INCIDENT ITSELF
# ---------------------------------------------------------------------------
def test_a_constant_oracle_mints_no_regime_action():
    """1,569/1,569 samples risk-off => lift 0.0 => rule 4 must NOT fire.

    This is the live 6-Aug condition reproduced exactly: every trade, winner
    and loser alike, opened while the flag read risk-off.
    """
    trades, hist = _bucket([True] * 12, [True] * 10)
    d = _diagnose(trades, hist)
    assert (d or {}).get("primary") != "regime_timing", (
        "a conditioning variable that never varies is not evidence (I7/I6) — "
        f"got {d}")


def test_the_old_bar_alone_would_still_have_fired():
    """Pins that the fixture really does satisfy the PRE-FIX condition.

    Without this, the test above could pass because the bucket never reached
    rule 4 at all — a green test proving nothing, which is the failure mode
    this repo keeps paying for.
    """
    trades, hist = _bucket([True] * 12, [True] * 10)
    losers = [t for t in trades if t["profit_abs"] < 0]
    matched = sum(1 for t in losers if bl._regime_at(hist, t["open_ts"]))
    counter = sum(1 for t in losers
                  if (bl._regime_at(hist, t["open_ts"]) or {}).get("risk_off"))
    assert matched >= 8, matched
    assert counter / matched >= 0.7, (
        "fixture must satisfy the OLD bar, or the fix is untested")


# ---------------------------------------------------------------------------
# ...AND THE RULE MUST STAY REACHABLE THE DAY THE ORACLE TURNS
# ---------------------------------------------------------------------------
def test_a_real_regime_effect_still_fires():
    """Losers concentrated in risk-off, winners in risk-on => big lift => FIRES.

    The whole danger of a fix like this is over-correction: a rule that can
    never fire again is not stricter, it is deleted. 12 losers all in risk-off
    against 10 winners all in risk-on is lift +1.00.
    """
    trades, hist = _bucket([True] * 12, [False] * 10)
    d = _diagnose(trades, hist)
    assert (d or {}).get("primary") == "regime_timing", (
        f"a genuine regime effect must still be diagnosable — got {d}")
    assert "lift" in (d.get("proposal") or ""), (
        "the operator-facing prose must publish the lift, not just the raw "
        f"share — got {d.get('proposal')!r}")
    # ...and STRUCTURALLY, so a consumer never has to parse prose (the
    # `bar_map` lesson: prose is what drifts).
    ev = d.get("evidence") or {}
    assert ev.get("base_regime") == 0.0 and ev.get("counter_regime") == 1.0, ev
    assert ev.get("regime_lift") == 1.0 and ev.get("regime_varies") is True, ev


def test_a_weak_lift_does_not_fire():
    """Losers 10/12 risk-off vs non-losers 9/10 — lift ~0.03, below the bar."""
    trades, hist = _bucket([True] * 10 + [False] * 2, [True] * 9 + [False])
    d = _diagnose(trades, hist)
    assert (d or {}).get("primary") != "regime_timing", (
        f"a 3pp lift is noise, not a regime finding — got {d}")


# ---------------------------------------------------------------------------
# I6 — no control group means no action
# ---------------------------------------------------------------------------
def test_no_control_group_means_no_action():
    """A bucket with too few matched non-losers cannot support the claim.

    Failing to mint keeps the book TRADING, which is the safe direction for a
    gate whose failure mode is a book silenced indefinitely.

    THE HISTORY MUST VARY HERE, deliberately. An all-risk-off fixture would be
    caught by `_regime_hist_varies` instead, and this test would pass while
    saying nothing about the control group — a mutation defaulting `base_share`
    to 0.0 (the permissive direction) survived exactly that way before this
    fixture was fixed. Losers all risk-off, the two non-losers risk-ON: the
    oracle varies, the lift would be a full +1.00 if a missing base were
    treated as zero, and ONLY the `base_matched >= REGIME_BASE_MIN_N` floor
    can refuse it.
    """
    trades, hist = _bucket([True] * 12, [False] * 2)   # 2 < REGIME_BASE_MIN_N
    assert bl._regime_hist_varies(hist) is True, (
        "the fixture must clear the variance lock, or it tests the wrong lock")
    d = _diagnose(trades, hist)
    assert (d or {}).get("primary") != "regime_timing", (
        f"no control group => uninterpretable => no action (I6) — got {d}")


# ---------------------------------------------------------------------------
# the variance assertion, which must not depend on the tunable
# ---------------------------------------------------------------------------
def test_regime_hist_varies_is_the_second_lock():
    assert bl._regime_hist_varies(_hist([True, False, True])) is True
    assert bl._regime_hist_varies(_hist([True] * 50)) is False, \
        "50 identical samples is a constant, not a history"
    assert bl._regime_hist_varies(_hist([False] * 50)) is False
    # fail-closed on absence: no history => no action => the book keeps trading
    assert bl._regime_hist_varies([]) is False
    assert bl._regime_hist_varies(None) is False
    # malformed entries are skipped, not crashed on
    assert bl._regime_hist_varies([{"ts": 1}, {"risk_off": True},
                                   {"risk_off": False}]) is True


def test_the_variance_lock_holds_even_if_the_lift_bar_is_tuned_to_zero():
    """The two locks are independent by construction.

    If a future pass re-tunes REGIME_LIFT_MIN toward 0.0, a constant oracle
    gives lift exactly 0.0 and `>= 0.0` would be TRUE — the latch would return
    silently. `_regime_hist_varies` is what stops that, so it is pinned
    separately rather than trusted to be redundant.
    """
    trades, hist = _bucket([True] * 12, [True] * 10)
    orig = bl.REGIME_LIFT_MIN
    try:
        bl.REGIME_LIFT_MIN = 0.0
        d = _diagnose(trades, hist)
        assert (d or {}).get("primary") != "regime_timing", (
            "with the lift bar at zero the variance lock must still refuse a "
            f"constant oracle — got {d}")
    finally:
        bl.REGIME_LIFT_MIN = orig


def test_the_bars_are_declared_and_sane():
    assert 0.0 < bl.REGIME_LIFT_MIN < 1.0, bl.REGIME_LIFT_MIN
    assert bl.REGIME_BASE_MIN_N >= 8, (
        "the control group's floor must not be looser than the losers' own")
