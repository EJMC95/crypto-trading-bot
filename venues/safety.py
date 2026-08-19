#!/usr/bin/env python3
"""
venues/safety.py — safety rails that live in the ADAPTER, not strategy code.

Rules (Gate-0 kickoff v2, non-negotiable):
  * REAL_MONEY_KILL is ARMED by default. The lighter_live path refuses to
    start — and flattens+halts mid-run — unless the env var is EXACTLY
    'DISARMED_I_UNDERSTAND'. Checked EVERY loop, not once.
  * Per-bot notional caps come from env, never code defaults that could grow:
        TRAIL_BLAZER_MAX_NOTIONAL   (pilot $200)
        BOUNCE_CATCHER_MAX_NOTIONAL (pilot $150)
    generic form: <BOT_ENV_PREFIX>_MAX_NOTIONAL.
  * Fleet-wide max daily loss (pilot $30/day, env LIGHTER_MAX_DAILY_LOSS)
    -> flatten-and-halt for the UTC day.

These rails apply to venues that SEND orders (testnet/live). Shadow mode
uses the same sizing numbers so shadow evidence prices the live config.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

log = logging.getLogger("venues.safety")

KILL_ENV = "REAL_MONEY_KILL"
DISARM_TOKEN = "DISARMED_I_UNDERSTAND"


def kill_switch_armed() -> bool:
    """True (armed = no live trading) unless explicitly disarmed."""
    return os.environ.get(KILL_ENV, "ARMED").strip() != DISARM_TOKEN


def env_prefix(bot: str) -> str:
    """'perps-donchian-breakout' -> 'PERPS_DONCHIAN_BREAKOUT'. Pilot bots also
    accept their fleet names (TRAIL_BLAZER / BOUNCE_CATCHER)."""
    return bot.upper().replace("-", "_")


_PILOT_ALIASES = {
    "perps-donchian-breakout": "TRAIL_BLAZER",
    "perps-rsi-meanrev": "BOUNCE_CATCHER",
}


#: [2026-08-19 (qq)] HOW MANY STOP-WIDTHS OF ROOM THE MONEY MUST HAVE BEFORE
#: ITS OWN LIQUIDATION. 4 is the bar `scripts/lighter_margin_model.headroom_x`
#: was designed around; it shipped there with NO consumer because the book it
#: was written for (⚡ High Voltage) was refuted and never built, so the number
#: existed and guarded nothing. Env-tunable, and RAISING it is the safe
#: direction.
LIQ_HEADROOM_K = float(os.environ.get("LIGHTER_LIQ_HEADROOM_K", "4"))


class SafetyRails:
    def __init__(self, bot: str, venue_mode: str):
        self.bot = bot
        self.venue_mode = venue_mode
        self.live = venue_mode == "lighter_live"
        alias = _PILOT_ALIASES.get(bot)
        raw = (os.environ.get(f"{alias}_MAX_NOTIONAL") if alias else None) or \
            os.environ.get(f"{env_prefix(bot)}_MAX_NOTIONAL")
        self.max_notional = float(raw) if raw else None
        self.max_daily_loss = float(os.environ.get("LIGHTER_MAX_DAILY_LOSS", "30"))
        self.halted_day = None

    # -- start-up gate --------------------------------------------------------
    def _publish_refusal(self, why):
        """[2026-07-12 GO-GREEN] a refused boot used to look identical to a
        dead bot (row just went stale). Mark the row ERROR (status-only update
        — the last good equity/P&L stays intact) so the dashboard says WHY."""
        try:
            import bot_pnl_store as store
            store.set_status(f"{self.bot}-lighter", "error")
        except Exception:  # noqa: BLE001 — never let telemetry block the gate
            pass

    def assert_can_start(self):
        if self.live:
            if kill_switch_armed():
                self._publish_refusal("kill switch armed")
                raise SystemExit(
                    f"{KILL_ENV} is ARMED — lighter_live refuses to start. "
                    f"(Gate-4 sign-off + explicit {KILL_ENV}={DISARM_TOKEN} required.)")
            if self.max_notional is None:
                self._publish_refusal("missing notional cap")
                raise SystemExit(
                    "lighter_live requires an explicit per-bot notional cap env "
                    f"({env_prefix(self.bot)}_MAX_NOTIONAL) — refusing to start.")

    # -- per-loop gates -------------------------------------------------------
    def kill_check(self) -> bool:
        """True -> caller must flatten and stop sending orders NOW."""
        return self.live and kill_switch_armed()

    def notional_ok(self, open_notional: float, add_usd: float) -> bool:
        if self.max_notional is None:
            return True
        return (open_notional + add_usd) <= self.max_notional + 1e-9

    def headroom_check(self, margin_state, stop_frac):
        """May the book ADD notional without sitting inside its own liquidation?

        [2026-08-19 (qq)] THE GAP THIS CLOSES. `(no)` wired the venue's own
        margining truth into the live path — `margin_state` carries the
        VENUE-PUBLISHED liquidation price per position, the distance to the
        nearest one, and a census of positions whose death price the venue
        will not state. Both live bots publish it. **Nothing refused on it.**
        This module is the one gate real money passes through and it knew only
        two numbers: a notional cap and a daily-loss cap. Neither can see
        liquidation, so the fleet could watch itself approach ruin and had no
        instrument that would decline.

        WHY IT IS EXPRESSED IN STOP-WIDTHS rather than a bare percentage. A
        stop is the loss the book has ALREADY decided to accept; liquidation
        is the loss it cannot survive. The only question that travels across
        books is how many of the first fit inside the second — measured on the
        validated model:

            stop 10% (💸 the Farmer's HARD_STOP, and it runs at 2x)
                L=2  -> 4.94x  OK        L=3  -> 3.25x  refused
                L=5  -> 1.90x  refused   L=10 -> 0.89x  LIQUIDATES FIRST
            stop 3%   -> 5x is fine (6.34x);  stop 1% -> 10x is fine (8.91x)

        So the live book already sits one notch under its own ceiling, reached
        by luck rather than by design, and the catastrophic regime — where the
        liquidation fires BEFORE the stop and the stop is decorative — is five
        notches away with nothing in between. Leverage capacity is a property
        of STOP DISTANCE, not of appetite, and this gate is what makes that
        arithmetic binding instead of merely true.

        FAIL-CLOSED, AGAINST THIS FLEET'S USUAL HABIT, and deliberately: every
        other degrade here fails OPEN so an organ outage can never idle a book.
        The cost of a wrong default is different in kind on this one — an open
        failure is a liquidation of real money, so an unreadable margin state,
        an unpriced position, or an unknown stop all REFUSE. Same reasoning
        I10 gives for the go-live blocker.

        Returns True for a non-live arm: a shadow book holds no venue account,
        so there is nothing to liquidate and nothing to read. The rail is
        about real money, exactly like `daily_loss_hit`.
        """
        if not self.live:
            return True, "not_live"
        if not isinstance(margin_state, dict) or not margin_state:
            return False, "state_unreadable"
        try:
            stop = float(stop_frac)
        except (TypeError, ValueError):
            return False, "stop_unreadable"
        if not (stop > 0) or stop != stop or stop in (float("inf"),):
            return False, "stop_unreadable"
        # ---- gather, THEN report. Several refusals can hold at once, and the
        # reason the operator sees decides what they do next, so the most
        # ACTIONABLE one is reported rather than whichever branch is written
        # first. `too_close` means de-lever now; `liq_unpriced` means go look
        # at the venue read. A urgent reason masked by a bookkeeping one is the
        # (gl) failure — a detector whose output the operator learns to ignore.
        unpriced = (set(margin_state.get("liq_unknown") or ())
                    - set(margin_state.get("liq_none") or ()))
        blind = margin_state.get("liq_mark_blind") or ()
        near = margin_state.get("nearest_liq")
        d, d_ok = None, False
        if isinstance(near, dict):
            try:
                d = float(near.get("dist_frac"))
                d_ok = (d == d) and d > 0
            except (TypeError, ValueError):
                d_ok = False

        # 1. MEASURED and inside the bar — the one refusal that means the money
        #    is actually in danger. Always reported ahead of the others.
        if d_ok and d < LIQ_HEADROOM_K * stop:
            return False, "too_close"
        # 2. A position the venue PRICED whose mark we cannot read. This is the
        #    fail-OPEN case: it reaches neither `liq_unknown` nor `nearest_liq`,
        #    so without this branch the gate reports the safest REMAINING
        #    position while a blind one sits inside its own liquidation.
        if blind:
            return False, "mark_blind"
        # 3. A position the venue would not price refuses — UNLESS the block can
        #    PROVE it unliquidatable (`liq_none`). Absence of evidence stays a
        #    refusal; a positive, checkable derivation does not.
        if unpriced:
            return False, "liq_unpriced"
        if isinstance(near, dict) and not d_ok:
            return False, "dist_unreadable"
        if not margin_state.get("n"):
            return True, "flat"               # flat: nothing can be liquidated
        if d_ok:
            return True, "ok"
        # Every held position is a PROVEN-bounded long, so nothing can
        # liquidate the account and there is nothing to measure against.
        # Refusing here would be the I7 failure: a condition the book satisfies
        # STRUCTURALLY, read as danger.
        if margin_state.get("liq_none"):
            return True, "unliquidatable"
        return False, "no_nearest"            # positions held, none priced

    def daily_loss_hit(self, day_start_equity, equity) -> bool:
        """Absolute-dollar fleet rail for funded modes (the strategies keep
        their own 5% rail on top)."""
        if not self.live or not day_start_equity or equity is None:
            return False
        return (day_start_equity - equity) >= self.max_daily_loss

    def confirm_daily_loss(self, day_start_equity, first_equity, pct_limit,
                           read_equity, delay_s=60):
        """One-print glitch guard for the daily-loss rails: re-read equity
        delay_s later and only stand down when the second read POSITIVELY
        shows the breach was transient.

        [2026-07-11] a single dislocated account_value print (-25% on deployed
        notional while every held coin moved <1%) tripped Trail Blazer's 5%
        rail and the flatten sold into the dislocation — a phantom drawdown
        became a real -5.9%. ONE shared implementation so the four bots'
        semantics cannot drift.

        FAIL-SAFE: if the confirm read raises or returns None the breach
        counts as CONFIRMED — a real crash is exactly when the venue API
        degrades, and the old immediate-flatten guarantee must survive that.

        Returns (confirmed, equity). `equity` is the freshest credible read;
        callers must adopt it on BOTH paths so a dislocated first print never
        leaks into published equity or a persisted P&L baseline.
        """
        log.warning("daily-loss breach read (%.2f vs day start %.2f) — "
                    "confirming in %ds.", first_equity, day_start_equity, delay_s)
        time.sleep(delay_s)
        try:
            eq2 = read_equity()
        except Exception as e:
            log.warning("confirm read failed (%s) — breach CONFIRMED (fail-safe).", e)
            return True, first_equity
        if eq2 is None:
            log.warning("confirm read returned None — breach CONFIRMED (fail-safe).")
            return True, first_equity
        if (eq2 <= day_start_equity * (1 - pct_limit)
                or self.daily_loss_hit(day_start_equity, eq2)):
            return True, eq2
        log.warning("breach NOT confirmed (second read %.2f) — transient print; "
                    "continuing.", eq2)
        return False, eq2


def open_notional(pos, meta, open_now, order_usd):
    """REAL deployed notional of open positions — the INPUT to notional_ok().

    Each HELD position at its OWN entry clip (meta['clip'], or size*entry as a
    fallback), plus this loop's new opens at the current clip. The naive
    `open_now * order_usd` estimate under-counts whenever the growth rail moved
    the clip mid-session — a live.clip_scale DOWN-scale shrinks order_usd, which
    RAISES max_open=floor(cap/clip) and, with held positions still sized at the
    larger clip, lets a new entry breach the operator's hard notional cap. That
    is not hypothetical: it breached on 15-Jul (see [[notional-cap-vs-variable-clip]]).

    [2026-07-17] LIFTED HERE from lighter_funding_bot / lighter_trend_bot, which
    each carried their own copy. They were code-identical the day this moved —
    and that is the argument, not the counter-argument: a money rule with two
    definitions and two DIFFERENT selftests (the trend bot's lacked the
    short-at-own-entry case) is one edit away from drifting, and the drift is a
    cap breach on real money. The Ticket Taker's live path would have made it
    three. The rail that enforces the cap now also computes its input, so
    `notional_ok(open_notional(...), clip)` is one rule with one test.
    Pure — unit-checked in _selftest() below and by each bot's own selftest.
    """
    held, n = 0.0, 0
    for c, v in (pos or {}).items():
        sz = v.get("size") if isinstance(v, dict) else v
        if not sz:
            continue
        n += 1
        mc = (meta or {}).get(c) or {}
        if mc.get("clip"):
            held += float(mc["clip"])
        elif mc.get("entry"):
            held += abs(float(sz)) * float(mc["entry"])
        else:
            # [2026-07-16 AUDIT] untracked position (meta lost): price it at
            # the VENUE's own entry notional, not the current (possibly
            # down-scaled) clip — order_usd here understates a position opened
            # at a larger clip and re-opens the cap-breach window this
            # function exists to close.
            _ven = (v.get("entry") if isinstance(v, dict) else 0) or 0
            held += (abs(float(sz)) * float(_ven)) or float(order_usd)
    return held + max(0, int(open_now) - n) * float(order_usd)


def capital_adjusted_day_start(day_start, cap_delta):
    """Net-of-capital daily-loss baseline — the ONE rule EVERY live bot shares.

    [2026-08-14 (mi)] Said "both live bots" while the live pair was Farmer +
    Ticket Taker. 🙏 Avo Maria replaced the Taker on the live slot on 13-Aug
    ((ma)) and shipped with this arithmetic INLINE instead of importing it —
    already drifted, in that the copy skipped the 2dp rounding below. The
    wording is the reason it was easy to miss: a helper described by a COUNT of
    its callers stops describing the system the moment the roster changes, so
    it now names the RULE. Any new live bot imports this; a live bot that
    reimplements it is the defect this function exists to prevent.

    A deposit/withdrawal the EquityGuard just healed lands in the RAW equity
    read, and the daily-loss rail compares that raw equity to `day_start`. So
    unless day_start moves by the SAME amount, a same-day DEPOSIT masks a real
    drawdown (raw equity rises, day_start doesn't -> the rail can't fire) and a
    WITHDRAWAL fabricates a phantom flatten+halt (raw equity falls, day_start
    doesn't -> the rail flattens on the operator's own cash-out). The leash is
    NET of deposits/withdrawals (operator, 2026-07-23) — measured latent on
    BOTH real-money bots' $2/day leash vs a deposit-driven ~$67 book.

    Returns (day_start, shifted). Shift by `cap_delta` ONLY when a baseline
    already exists AND a move actually folded, so the move cancels in the rail's
    (day_start - equity). When day_start is None the caller adopts the
    capital-INCLUSIVE `equity` as the baseline and must NOT shift it again (that
    would double-count the move). Pure — this is the extracted single source of
    the shift arithmetic the Ticket Taker (two fold sites) and Funding Farmer
    each used to carry inline; the Farmer's `while True` main() has no test
    harness, so extracting it here is what gives that rail a real test.
    Unit-tested in _selftest() below and exercised end-to-end through
    production code by the taker's --selftest-live 4b/4c."""
    if day_start is not None and cap_delta:
        return round(float(day_start) + float(cap_delta), 2), True
    return day_start, False


def _selftest():
    """The 15-Jul breach scenario + the cases the two copies tested between
    them (neither tested all of them alone — see open_notional's docstring)."""
    # capital_adjusted_day_start — the net-of-capital rail baseline (23-Jul).
    # deposit: a +100 move shifts the baseline UP so the rail still sees the loss
    assert capital_adjusted_day_start(1000.0, 100.0) == (1100.0, True)
    # withdrawal: a -30 move shifts the baseline DOWN so a cash-out is not a loss
    assert capital_adjusted_day_start(1000.0, -30.0) == (970.0, True)
    # no move -> untouched, not flagged as shifted
    assert capital_adjusted_day_start(1000.0, 0.0) == (1000.0, False)
    assert capital_adjusted_day_start(1000.0, None) == (1000.0, False)
    # no baseline yet -> caller adopts capital-inclusive equity; NEVER shift here
    assert capital_adjusted_day_start(None, 100.0) == (None, False)
    assert capital_adjusted_day_start(None, 0.0) == (None, False)
    # rounds to 2dp like the ledger (66.87 + 32.22 = 99.09, the book's own numbers)
    assert capital_adjusted_day_start(66.87, 32.22) == (99.09, True)
    pos = {c: {"size": 1.0, "entry": 30.0} for c in "ABCDE"}
    meta = {c: {"clip": 30.0, "entry": 30.0} for c in "ABCDE"}
    # cap $150, five $30 positions, growth-rail down-scale to clip 22.50: the
    # old open_now*order_usd estimate said $112.50 and passed a 6th entry.
    assert open_notional(pos, meta, 5, 22.50) == 150.0
    assert open_notional(pos, {}, 5, 22.50) == 150.0        # venue-entry fallback
    # venue entry also missing -> last-resort current clip (conservative floor)
    assert open_notional({c: {"size": 1.0} for c in "ABCDE"}, {}, 5, 22.50) == 112.5
    # opens-this-loop not yet visible in pos, priced at the current clip
    assert open_notional(pos, meta, 7, 22.50) == 195.0
    # short at its own entry (size*entry, sign-independent) — the case ONLY the
    # funding bot's copy covered
    assert open_notional({"Z": {"size": -2.0, "entry": 20.0}}, {}, 1, 30.0) == 40.0
    # zero-size rows are not positions and must not consume cap
    assert open_notional({"Z": {"size": 0.0, "entry": 20.0}}, {}, 0, 30.0) == 0.0
    # empty / None inputs
    assert open_notional({}, {}, 0, 30.0) == 0.0
    assert open_notional(None, None, 0, 30.0) == 0.0
    # the rail itself: cap is inclusive, and no cap == no limit
    r = SafetyRails.__new__(SafetyRails)
    r.max_notional = 150.0
    assert r.notional_ok(120.0, 30.0) is True      # exactly at cap
    assert r.notional_ok(120.0, 30.01) is False    # one cent over
    r.max_notional = None
    assert r.notional_ok(1e9, 1e9) is True
    print("venues.safety self-tests passed (open_notional + notional_ok + "
          "capital_adjusted_day_start).")


if __name__ == "__main__":
    _selftest()
