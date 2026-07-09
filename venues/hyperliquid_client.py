#!/usr/bin/env python3
"""
venues/hyperliquid_client.py — the existing HL read/trade logic, wrapped.

This is a PASSTHROUGH of what hyperliquid_momo_bot.py / hyperliquid_perps_bot.py
/ funding_carry_bot.py already did inline, so VENUE=hl_paper is byte-identical
market data: candles_snapshot dicts, user_state positions, meta_and_asset_ctxs
funding. No new behaviour lives here on purpose.
"""
from __future__ import annotations

import os

from .base import VenueClient, VenueError


class HyperliquidClient(VenueClient):
    name = "hyperliquid"

    def __init__(self, net: str = "testnet", with_exchange: bool = False):
        try:
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
        except ImportError as e:  # same hard requirement as before the refactor
            raise VenueError(f"hyperliquid-python-sdk missing: {e}")
        self.net = net
        self.base_url = (constants.MAINNET_API_URL if net == "mainnet"
                         else constants.TESTNET_API_URL)
        self.info = Info(self.base_url, skip_ws=True)
        self.exchange = None
        self.addr = None
        if with_exchange:
            import eth_account
            from hyperliquid.exchange import Exchange
            secret = os.environ.get("HL_API_PRIVATE_KEY", "").strip()
            if not secret:
                raise VenueError("HL_API_PRIVATE_KEY not set for live/testnet trading")
            account_address = os.environ.get("HL_ACCOUNT_ADDRESS", "").strip()
            wallet = eth_account.Account.from_key(secret)
            self.exchange = Exchange(wallet, self.base_url,
                                     account_address=account_address or None)
            self.addr = account_address or wallet.address
            self.sends_orders = True

    # ---- market data --------------------------------------------------------
    def candles(self, coin, interval, start_ms, end_ms):
        return self.info.candles_snapshot(coin, interval, start_ms, end_ms)

    def funding_map(self):
        meta, ctxs = self.info.meta_and_asset_ctxs()
        out = {}
        for asset, ctx in zip(meta["universe"], ctxs):
            try:
                out[asset["name"]] = {
                    "rate": float(ctx.get("funding") or 0.0),
                    "mark": float(ctx.get("markPx") or 0.0),
                    "vol": float(ctx.get("dayNtlVlm") or 0.0),
                }
            except (TypeError, ValueError):
                continue
        return out

    def orderbook(self, coin):
        book = self.info.l2_snapshot(coin)
        levels = book.get("levels") or [[], []]
        bids = [(float(l["px"]), float(l["sz"])) for l in levels[0]]
        asks = [(float(l["px"]), float(l["sz"])) for l in levels[1]]
        return {"bids": bids, "asks": asks}

    # ---- account ------------------------------------------------------------
    def account_value(self):
        st = self.info.user_state(self.addr)
        return float(st["marginSummary"]["accountValue"])

    def positions(self):
        st = self.info.user_state(self.addr)
        out = {}
        for p in st.get("assetPositions", []):
            pos = p["position"]
            out[pos["coin"]] = {"size": float(pos["szi"]),
                                "entry": float(pos.get("entryPx") or 0.0)}
        return out

    # ---- orders -------------------------------------------------------------
    def market_open(self, coin, is_long, size):
        return self.exchange.market_open(coin, is_long, size)

    def market_close(self, coin):
        return self.exchange.market_close(coin)
