#!/usr/bin/env python3
"""
venues/base.py — VenueClient: the venue abstraction for the custom perps bots.

Gate 0 of the Lighter migration (see docs/lighter.md). Strategy code talks to
this interface only; the venue behind it is picked by the VENUE env var:

    hl_paper        (default) Hyperliquid data exactly as before — zero
                    behaviour change; dry-run fills stay in PaperBroker.
    lighter_shadow  LIVE Lighter mainnet market data; orders are modelled
                    against the real book and written to the Postgres ledger
                    (venue='lighter', shadow=true) — NEVER sent.
    lighter_testnet Real order lifecycle on the Lighter testnet (env keys).
    lighter_live    REFUSES to start unless REAL_MONEY_KILL is explicitly
                    disarmed (see venues/safety.py). Default is ARMED.

The interface is deliberately shaped around what the bots already call today
(hyperliquid.info.Info + Exchange), so the hl_paper path is a passthrough:
candles are the venue-native list-of-dicts with keys t/o/h/l/c (both HL and
Lighter use this shape; floats or numeric strings — bots float() them).
"""
from __future__ import annotations


class VenueError(Exception):
    """Raised for venue-level failures the bot should treat as 'skip this loop'."""


class VenueClient:
    """Interface. Concrete venues: HyperliquidClient, LighterClient."""

    name = "abstract"
    #: True when orders are actually transmitted to an exchange.
    sends_orders = False
    #: True when fills are modelled locally against live market data.
    is_shadow = False

    # ---- market data (read-only, required by every mode) -------------------
    def candles(self, coin: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
        """Closed candles, venue-native dicts with at least t/o/h/l/c keys.
        `coin` is always the fleet's HL-style symbol (e.g. kBONK); venues that
        name it differently translate internally (venues/symbol_map.py)."""
        raise NotImplementedError

    def funding_map(self) -> dict[str, dict]:
        """{coin: {'rate': hourly_funding, 'mark': mark_px, 'vol': day_ntl_vol}}
        for every perp on the venue, in fleet (HL-style) symbols."""
        raise NotImplementedError

    def orderbook(self, coin: str) -> dict:
        """{'bids': [(px, sz), ...], 'asks': [(px, sz), ...]} best-first.
        Used by shadow fills; may come from a ws cache."""
        raise NotImplementedError

    def supports(self, coin: str) -> bool:
        """Whether the venue lists this fleet symbol (after remapping)."""
        return True

    # ---- account (live/testnet modes) --------------------------------------
    def account_value(self) -> float:
        raise NotImplementedError

    def positions(self) -> dict[str, dict]:
        """{coin: {'size': signed_size, 'entry': entry_px}}

        Venues MAY add keys (Lighter carries 'upnl' and, since (no), the
        margin fields 'liq'/'imf'/'value'/'margin'/'mode'). Consumers read
        what they need with .get() and must treat a missing key as UNKNOWN —
        an absent margin field never means zero."""
        raise NotImplementedError

    def margin_state(self, marks=None) -> dict | None:
        """[2026-08-16 (no)] The venue's own margining view, or None.

        OPTIONAL by design, and it returns None rather than raising, because
        most venues in this fleet cannot answer it: a shadow/paper arm holds
        no venue account, so "what leverage am I at" has no venue-side answer
        there and must read as UNKNOWN rather than as a fabricated 1.0. A
        caller that gets None publishes nothing instead of publishing a
        guess."""
        return None

    # ---- order entry (live/testnet modes; shadow uses ShadowBroker) --------
    def market_open(self, coin: str, is_long: bool, size: float):
        raise NotImplementedError

    def market_close(self, coin: str):
        raise NotImplementedError
