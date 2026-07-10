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

    def order_usd(self, paper_default: float) -> float:
        if self.mode == "hl_paper":
            return paper_default
        return float(os.environ.get("LIGHTER_ORDER_USD", "30"))

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
        venue = LighterClient(net=net, with_signer=True)
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
