#!/usr/bin/env python3
"""
venues/shadow.py — ShadowBroker: paper fills against the LIVE Lighter book.

Shadow mode is the evidence engine for Gate 3/4: the full decision loop runs
on live Lighter mainnet data, and every order is filled by CROSSING THE
SPREAD in the real order book (walk the ask side for buys, the bid side for
sells, at our clip size) — the honest, slightly pessimistic fill model. The
order NEVER leaves this process.

Every simulated order is also written to Postgres (bot_pnl_store.
publish_venue_order: venue='lighter', shadow=true, decision px vs modelled
fill px, spread at decision time) so realizable spread / slippage per market
accumulates per shadow-day.

Accounting reuses PaperBroker (fees forced to ZERO — Lighter standard tier
charges none; slippage IS the cost and it's realised in the fill price).
"""
from __future__ import annotations

import logging
import time

from paper_broker import PaperBroker
import bot_pnl_store as store

log = logging.getLogger("venues.shadow")


def fill_from_book(book: dict, is_buy: bool, size: float):
    """Walk the book for `size` units. Returns (avg_px, levels_used, top_px)
    or None when the visible depth can't fill us (thin book -> skip)."""
    side = book.get("asks" if is_buy else "bids") or []
    if not side:
        return None
    top_px = side[0][0]
    remaining = size
    cost = 0.0
    used = 0
    for px, sz in side:
        take = min(remaining, sz)
        cost += take * px
        remaining -= take
        used += 1
        if remaining <= 1e-12:
            return cost / size, used, top_px
    return None  # not enough visible depth


class ShadowBroker(PaperBroker):
    """PaperBroker whose fills come from the live venue book."""

    def __init__(self, bot: str, venue, start_equity: float = 1000.0):
        # fee_bps=0: Lighter standard tier is zero-fee; the cost model is the
        # crossed spread itself, which lands in the fill price.
        super().__init__(start_equity=start_equity, fee_bps=0.0)
        self.bot = bot
        self.venue = venue

    def _shadow_fill(self, coin: str, is_buy: bool, size: float, decision_px: float):
        try:
            book = self.venue.orderbook(coin)
        except Exception as e:  # noqa: BLE001 — no book, no fill
            log.warning("%s shadow book unavailable (%s); using decision px", coin, e)
            book = None
        fill = fill_from_book(book, is_buy, size) if book else None
        if fill is None:
            fill_px, levels, top = decision_px, 0, decision_px
        else:
            fill_px, levels, top = fill
        spread_bps = None
        if book and book.get("bids") and book.get("asks"):
            bid, ask = book["bids"][0][0], book["asks"][0][0]
            mid = (bid + ask) / 2
            spread_bps = (ask - bid) / mid * 1e4 if mid else None
        slip_bps = (fill_px - decision_px) / decision_px * 1e4 * (1 if is_buy else -1) \
            if decision_px else None
        store.publish_venue_order(
            self.bot, venue="lighter", shadow=True, coin=coin,
            side="buy" if is_buy else "sell", size=size,
            px_decision=decision_px, px_fill=fill_px,
            spread_bps=spread_bps, slippage_bps=slip_bps,
            raw={"levels_used": levels, "book_top": top, "ts": time.time()})
        return fill_px

    # -- PaperBroker overrides: same call sites, book-aware fills -------------
    def open(self, coin, is_long, size, price):
        fill_px = self._shadow_fill(coin, is_long, size, price)
        super().open(coin, is_long, size, fill_px)

    def close(self, coin, price):
        if coin not in self.pos:
            return 0.0
        size, _ = self.pos[coin]
        fill_px = self._shadow_fill(coin, size < 0, abs(size), price)
        return super().close(coin, fill_px)
