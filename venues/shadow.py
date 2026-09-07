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

WHERE THE MODEL IS OPTIMISTIC, stated because it is not visible from the
fill price: when the book cannot fill the clip (empty side, or depth
exhausted inside the 25 REST levels) or cannot be read at all, the order is
booked at the DECISION price — a free fill. That is the honest thing to do
with the P&L (there is no better price to use) and a lie to publish as a
measurement, so since 2026-09-07 such a row carries `slippage_bps = NULL`,
`measured: false` and a `fill_src` naming which of the three conditions
fired. Count `measured` rows, never all rows, when grading execution.
"""
from __future__ import annotations

import logging
import time

from paper_broker import PaperBroker
import bot_pnl_store as store

log = logging.getLogger("venues.shadow")


def fill_from_book(book: dict, is_buy: bool, size: float):
    """Walk the book for `size` units. Returns (avg_px, levels_used, top_px)
    or None when this book cannot fill us.

    None has TWO causes and the caller must be able to tell them apart: the
    quoted side is EMPTY, or the visible depth (25 REST levels — see
    `LighterClient._rest_book`) is exhausted before `size` is filled.

    [2026-09-07] The old docstring said "thin book -> skip" and NOTHING
    skips: `_shadow_fill` falls back to the decision price and books the
    trade. A comment that describes a refusal the code does not perform is
    how the fallback stayed invisible — see `_shadow_fill`."""
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
        """Fill `size` by crossing the live book; record what actually happened.

        [2026-09-07] AN UNFILLABLE ORDER IS NOT A ZERO-COST FILL. Three
        different conditions land on the same fallback — the quoted side is
        empty, the visible depth cannot cover the clip, or `orderbook()`
        raised — and all three used to publish `slippage_bps = 0.0` with a
        `book_top` copied from the decision price. That is a FABRICATED
        MEASUREMENT, and it was consumed as one:

          * `market_context._fold_coin_quality` counts NON-NULL slippage as
            `measured_14d`, the n-floor of the coin-quality veto, and averages
            the same column. Its own 22-Jul note already states the rule this
            path was breaking — "a live-arm row with NULL slippage is not
            evidence" — after the identical defect on the LIVE side inflated
            the floor with rows carrying no measurement.
          * so the orders that could NOT be filled satisfied the floor and
            pulled the average toward zero, in the one fleet mechanism whose
            job is to veto coins that are expensive to trade. The books most
            likely to hit this fallback are the thin ones the veto exists for.

        The rule applied here is the fleet's own, already pinned for live
        fills in `venues/fills.slip_bps_of` and in the Ticket Taker's
        selftest: UNMEASURED IS NULL, never 0.0; a MEASURED at-mark fill is a
        real 0.0; and the ledger NAMES why it could not measure. P&L is
        untouched — the fallback still books at the decision price, exactly as
        before, so every equity curve is byte-identical. Only the telemetry
        stops lying.
        """
        src = None
        try:
            book = self.venue.orderbook(coin)
        except Exception as e:  # noqa: BLE001 — no book, no fill
            log.warning("%s shadow book unavailable (%s); using decision px", coin, e)
            book, src = None, f"venue-dark:{type(e).__name__}"
        if not book and src is None:
            # orderbook() answered, with nothing in it. Distinct from a raise:
            # one is a dead venue, the other a market quoting no book at all.
            src = "no-book"
        fill = fill_from_book(book, is_buy, size) if book else None
        if fill is None:
            # NOT a fill. Keep the decision price so the book's accounting and
            # its equity curve are unchanged, and record everything else as the
            # absence it is: no levels walked, no book top read, no slippage.
            fill_px, levels, top, measured = decision_px, 0, None, False
            if src is None:
                side = (book or {}).get("asks" if is_buy else "bids") or []
                src = "empty-side" if not side else "thin-book"
        else:
            fill_px, levels, top = fill
            measured, src = True, "walked"
        spread_bps = None
        if book and book.get("bids") and book.get("asks"):
            bid, ask = book["bids"][0][0], book["asks"][0][0]
            mid = (bid + ask) / 2
            spread_bps = (ask - bid) / mid * 1e4 if mid else None
        # `measured` gates the arithmetic, never `fill_px != decision_px` — a
        # real fill that lands exactly on the decision price is a measured 0.0
        # and must survive as one (the taker's own rule (b)).
        slip_bps = None
        if measured and decision_px:
            slip_bps = ((fill_px - decision_px) / decision_px * 1e4
                        * (1 if is_buy else -1))
        store.publish_venue_order(
            self.bot, venue="lighter", shadow=True, coin=coin,
            side="buy" if is_buy else "sell", size=size,
            px_decision=decision_px, px_fill=fill_px,
            spread_bps=spread_bps, slippage_bps=slip_bps,
            raw={"levels_used": levels, "book_top": top,
                 "measured": measured, "fill_src": src, "ts": time.time()})
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
