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
    def assert_can_start(self):
        if self.live:
            if kill_switch_armed():
                raise SystemExit(
                    f"{KILL_ENV} is ARMED — lighter_live refuses to start. "
                    f"(Gate-4 sign-off + explicit {KILL_ENV}={DISARM_TOKEN} required.)")
            if self.max_notional is None:
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

    def daily_loss_hit(self, day_start_equity, equity) -> bool:
        """Absolute-dollar fleet rail for funded modes (the strategies keep
        their own 5% rail on top)."""
        if not self.live or not day_start_equity or equity is None:
            return False
        return (day_start_equity - equity) >= self.max_daily_loss
