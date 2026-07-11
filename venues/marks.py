#!/usr/bin/env python3
"""
venues/marks.py — venue-blind live-book price helpers.

fresh_mid was born in lighter_trend_bot.py / lighter_funding_bot.py (identical
copies); promoted here 2026-07-11 so the adapter's equity guard
(venues/equity_guard.py) and the bots share ONE implementation. The contract
the bots rely on is unchanged:

  * The mid comes from the LIVE order book only — NEVER a funding-map mark
    (that is a last-trade price frozen at client construction; using it on a
    stop path would silently freeze the stop while the real price runs away).
  * None means 'cannot evaluate risk here' and callers MUST treat it that way.

Levels are reduced with max/min rather than [0]-indexing: the Lighter REST
snapshot fallback (the Railway norm — the venue ws is CDN-blocked from cloud
IPs) returns UNSORTED levels, and top-of-book-by-index on an unsorted book is
just some price. The ws cache pre-sorts, so this is free there.
"""
from __future__ import annotations


def fresh_mid(venue, coin):
    """Live-book mid for `coin` (fleet symbol) on `venue`, or None."""
    try:
        book = venue.orderbook(coin)
    except Exception:  # noqa: BLE001 — 'no price' is an answer, not a crash
        return None
    if not book:
        return None
    bids = [px for px, _ in (book.get("bids") or []) if px > 0]
    asks = [px for px, _ in (book.get("asks") or []) if px > 0]
    if not bids or not asks:
        return None
    return (max(bids) + min(asks)) / 2.0


def mid_map(venue, coins):
    """{coin: mid} for every coin with a readable live book (others absent)."""
    out = {}
    for c in coins:
        m = fresh_mid(venue, c)
        if m:
            out[c] = m
    return out
