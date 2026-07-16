#!/usr/bin/env python3
"""
venues/__init__.py — venue selection for the custom perps bots (Gate 0).

    ctx = venue_context(bot="perps-donchian-breakout", default_hl_net="testnet",
                        paper_start=1000.0, live_flag=False)

VENUE env picks the mode (default hl_paper = pre-migration behaviour, byte
identical). The context bundles everything the bots used to build inline:

    ctx.mode         hl_paper | lighter_shadow | lighter_testnet | lighter_live
    ctx.venue        VenueClient (market data + live order entry)
    ctx.broker       PaperBroker (hl_paper) / ShadowBroker (lighter_shadow) /
                     None (funded modes: account state lives on the venue)
    ctx.bot_id       ledger/dashboard identity. SUFFIXED outside hl_paper
                     (-lshadow / -ltest / -lighter) so shadow & testnet curves
                     NEVER contaminate the paper era rows.
    ctx.rails        SafetyRails (kill switch, notional caps, daily-loss halt)
    ctx.dry_run      True when fills are modelled locally (hl_paper, shadow)

Sizing in lighter modes comes from env (LIGHTER_ORDER_USD, default $30 —
pilot clips $25-35) and the per-bot notional caps scale the open-position
cap: floor(cap / clip). hl_paper keeps each bot's own constants untouched.
"""
from __future__ import annotations

import logging
import math
import os

from .base import VenueClient, VenueError          # noqa: F401 (re-export)
from .governor import TxBudgetGovernor             # noqa: F401
from .safety import SafetyRails

try:
    import fleet_tuning as _tuning     # growth rail (optional import)
except Exception:  # noqa: BLE001 — images without the module: lever inert
    _tuning = None

log = logging.getLogger("venues")

MODES = ("hl_paper", "lighter_shadow", "lighter_testnet", "lighter_live")

_SUFFIX = {"hl_paper": "", "lighter_shadow": "-lshadow",
           "lighter_testnet": "-ltest", "lighter_live": "-lighter"}


class VenueContext:
    def __init__(self, mode, venue, broker, bot, rails):
        self.mode = mode
        self.venue = venue
        self.broker = broker
        self.bot_id = bot + _SUFFIX[mode]
        self.rails = rails
        # fills modelled locally whenever a broker exists (hl_paper dry-run,
        # lighter_shadow); funded modes (broker None) trade on the venue.
        self.dry_run = broker is not None
        self._unsupported_logged = set()

    def supports(self, coin) -> bool:
        ok = self.venue.supports(coin)
        if not ok and coin not in self._unsupported_logged:
            self._unsupported_logged.add(coin)
            log.info("%s: %s not listed on %s — skipping (see docs/lighter.md)",
                     self.bot_id, coin, self.venue.name)
        return ok

    def order_usd(self, paper_default: float, own: bool = False) -> float:
        if self.mode == "hl_paper":
            return paper_default
        # [2026-07-16 AUDIT FIX] own=True: bots whose clip is part of their
        # BACKTESTED definition (Snap Back $10, Counterweight $20/leg) keep
        # their per-bot env — the global LIGHTER_ORDER_USD silently overrode
        # it on every Lighter mode, so Snap Back ran 3x its documented size.
        # The funding/trend twins deliberately DON'T pass own: they mirror
        # live sizing (control arm). Live mode keeps the global anchor +
        # growth-rail lever regardless.
        if own and self.mode != "lighter_live":
            return paper_default
        base = float(os.environ.get("LIGHTER_ORDER_USD", "30"))
        # [2026-07-15 GROWTH RAIL — live lane] lighter_live clips carry the
        # evidence board's bounded clip_scale (fleet_tuning clamps to
        # [0.5, 1.5]; lever expires to 1.0 on its own). The operator's env
        # stays the anchor and SafetyRails' notional cap stays senior at
        # order time — this reshapes clips, it cannot add exposure.
        if self.mode == "lighter_live" and _tuning is not None:
            base = round(base * _tuning.get_lever("live.clip_scale", 1.0), 2)
        return base

    def max_open_positions(self, paper_default: int) -> int:
        if self.mode == "hl_paper" or self.rails.max_notional is None:
            return paper_default
        return max(1, math.floor(self.rails.max_notional /
                                 self.order_usd(paper_default)))


def venue_context(bot: str, default_hl_net: str = "testnet",
                  paper_start: float = 1000.0, live_flag: bool = False):
    mode = os.environ.get("VENUE", "hl_paper").strip() or "hl_paper"
    if mode not in MODES:
        raise SystemExit(f"VENUE={mode!r} unknown (expected one of {MODES})")

    rails = SafetyRails(bot, mode)
    rails.assert_can_start()

    if mode == "hl_paper":
        from .hyperliquid_client import HyperliquidClient
        venue = HyperliquidClient(net=default_hl_net, with_exchange=live_flag)
        broker = None
        if not live_flag:
            from paper_broker import PaperBroker
            broker = PaperBroker(paper_start)
        return VenueContext(mode, venue, broker, bot, rails)

    from .lighter_client import LighterClient
    if mode == "lighter_shadow":
        venue = LighterClient(net="mainnet", with_signer=False)
        from .shadow import ShadowBroker
        broker = ShadowBroker(bot + _SUFFIX[mode], venue, paper_start)
        return VenueContext(mode, venue, broker, bot, rails)

    net = "testnet" if mode == "lighter_testnet" else "mainnet"
    try:
        # guard_state_key: the equity guard's last-accepted read persists under
        # the suffixed bot id (like the durable daily-loss halt) so a redeploy
        # cannot re-anchor equity validation on a dislocated print.
        venue = LighterClient(net=net, with_signer=True,
                              guard_state_key=bot + _SUFFIX[mode] + ":eqguard")
    except Exception as e:
        # [2026-07-10] A live bot that can't authenticate used to die SILENTLY —
        # the dashboard row just went stale with no explanation. Publish an
        # explicit error row (guarded) so the card shows WHY it is down
        # (e.g. "private key does not match the one on Lighter").
        try:
            import bot_pnl_store as store
            store.publish(bot + _SUFFIX[mode], status="error",
                          extra={"mode": mode, "venue": mode,
                                 "error": str(e)[:220]})
        except Exception:  # noqa: BLE001 — never mask the real failure
            pass
        raise
    return VenueContext(mode, venue, None, bot, rails)
