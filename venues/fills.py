#!/usr/bin/env python3
"""
venues/fills.py — the fleet's ONE answer to "what did we actually pay?"

Same consolidation as `venues/safety.py::open_notional`, and for the same
reason: this logic was written twice, drifted, and the drift was invisible
because each copy had its own tests.

WHAT LIVES HERE. The three helpers that turn `LighterClient.last_fill_detail`
into a ledger row: the escalation policy (`read_fill`), the measured/estimated
verdict (`measured_from_reason`), and the slippage rule (`slip_bps_of`).
Imported by lighter_funding_bot (Funding Farmer, LIVE) and
lighter_ticket_taker (Ticket Taker, LIVE).

WHAT DOES NOT. `lighter_trend_bot._real_exit` and `lighter_perp_sniper._real_exit`
are NOT copies of this despite looking like it — they call the legacy `last_fill`,
thread no client id, and publish no `slippage_bps` at all (neither file writes a
venue_orders row). Their read is an exit PRICE for P&L, not execution telemetry.
Folding them in here would change what two more bots' ledgers record, for no
measurement gain in either. Left alone deliberately; see the 17-Jul note in
CHANGELOG.md.

MEASUREMENT ONLY. Nothing here may block, delay or unwind an order. Every path
is caught and every failure is NAMED — "no fill found" and "the read exploded"
must never collapse into the same None, which is how the fleet went 58 real
orders without a single measured fill.
"""
from __future__ import annotations


def measured_from_reason(px, reason):
    """Did the venue NAME this fill, or guess it?

    Single source of truth, and deliberately parasitic on the venue layer's own
    labelling: lighter_client tags every id-less read `approx`
    (`trades(approx)` / `recentTrades-approx(...)`) and every id-matched read
    without it. Deriving `measured` from that string rather than re-deciding it
    here means the two layers cannot drift into disagreeing about what counts
    as a measurement.

    THIS IS WHY IT IS A FUNCTION AND NOT A LITERAL. The taker's `_real_fill`
    hard-coded `return real, True, reason` — measured=True whenever ANY price
    came back, reason string ignored. An id-less read (a venue that stops
    echoing ids, a market_close whose dict lacks the key) would have been
    recorded as an exact measurement while being a 180s same-side VWAP blend.
    A fabrication with a `measured: true` stamp on it is worse than a null.
    """
    return px is not None and "approx" not in (reason or "")


def read_fill(detail_fn, coin, is_ask, since_ts, client_id, tx_hash=None):
    """(px_or_None, measured, reason) — the id first, the heuristic as a net.

    THE ESCALATION, and why it cannot live one layer down in
    `LighterClient._our_fills`:

      1. `last_fill_detail` labels a read from whether an id was SUPPLIED, not
         whether it MATCHED (`"trades" if client_id is not None else
         "trades(approx)"`, lighter_client.py:700). A fallback inside
         `_our_fills` would hand back a blended price still labelled `trades`
         — exact — and `measured_from_reason` would stamp it True. The lie
         would be one layer below every test that could catch it.
      2. `last_fill_detail` reads TWO tapes: the auth'd account-filtered
         `trades` (10 rows) then the public `recentTrades` (100 rows). An
         id-miss on tape 1 currently escalates to tape 2 WITH the id. A
         fallback inside `_our_fills` would blend on tape 1 and return, never
         reaching tape 2 — where the exact match is more likely to be, because
         it is the wider window. The correct order is id-on-both-tapes, THEN
         heuristic-on-both-tapes, and only a caller ABOVE `last_fill_detail`
         can express that. This function is that caller.

    RETRY ONLY ON no-match. `skipped:budget` / `api-error` / `auth-failed` mean
    the tape was never read; retrying spends the governor's telemetry reserve to
    fail identically, and lighter_client's own rule is explicit that a
    measurement burst must never make the NEXT market_open queue behind it.
    A no-match means the tape WAS read and our id simply was not on it — that,
    and only that, is worth a second look.

    The fallback's worst case is exactly the id-less behaviour, LABELLED. That
    is the whole point: a venue that stops echoing `client_order_index` must
    cost us precision, never the measurement itself.
    """
    if detail_fn is None:
        return None, False, "no-detail-fn"
    # [2026-07-21 TX TIER] the transaction hash is the STRONGEST exact name
    # (measured live: the venue does not echo client_order_index into the
    # tape — 0 of 61 real orders ever id-matched — but every trade row
    # stamps the taker's tx_hash, which OUR submission returns). Same
    # escalation doctrine as below: tx-on-both-tapes, then id-on-both-tapes,
    # then the labelled heuristic; retry only on no-match (the tape was read
    # and we simply were not on it). Older venue layers without the tx_hash
    # kwarg degrade to the id tier via TypeError — additive by construction.
    if tx_hash:
        try:
            px, reason = detail_fn(coin, is_ask=is_ask, since_ts=since_ts,
                                   client_id=client_id, tx_hash=tx_hash)
        except TypeError:
            px, reason = None, "tx-unsupported"
        except Exception as e:  # noqa: BLE001
            return None, False, f"read-raised:{type(e).__name__}"
        if px is not None:
            return px, measured_from_reason(px, reason), reason
        if "no-match" not in (reason or "") and reason != "tx-unsupported":
            # skipped:budget / api-error / auth-failed: the tape was never
            # read — retrying spends the reserve to fail identically.
            return None, False, reason
        _tx_note = f" (tx-miss: {reason})"
    else:
        _tx_note = ""
    try:
        px, reason = detail_fn(coin, is_ask=is_ask, since_ts=since_ts,
                               client_id=client_id)
    except Exception as e:  # noqa: BLE001 — telemetry NEVER raises at a caller
        return None, False, f"read-raised:{type(e).__name__}"
    reason = f"{reason}{_tx_note}" if reason else reason
    if px is None and client_id is not None and "no-match" in (reason or ""):
        try:
            px2, reason2 = detail_fn(coin, is_ask=is_ask, since_ts=since_ts,
                                     client_id=None)
        except Exception as e:  # noqa: BLE001
            return None, False, f"retry-raised:{type(e).__name__} (after {reason})"
        # px2 is a BLEND whatever happens — the id is what made it exact, and we
        # just dropped it. `measured` is False on both branches by construction.
        return px2, False, f"{reason2} (id-miss: {reason})"
    return px, measured_from_reason(px, reason), reason


def slip_bps_of(decision, fill, is_buy, measured=False):
    """Signed slippage on ONE order, bps. POSITIVE = worse than the decision
    price (paid up buying / sold lower). None = we did not measure this leg.

    `measured` is PASSED, never inferred from d == f. The old rule returned None
    whenever the two were equal, because an unread fill fell back to the decision
    mid and a fabricated 0.000 is worse than a null. But it also threw away every
    GENUINELY perfect fill — 1000BONK filled exactly at mark on the taker's first
    live order, real data the fleet discarded. With the flag the two separate:
    measured d == f is a true 0.0; unmeasured d == f stays NULL.

    UNMEASURED IS ALWAYS NULL, even when d != f. This is the rule the two copies
    disagreed on: the taker's returned None, the Farmer's returned the bps. The
    disagreement was unreachable while every read was exact-or-nothing — and
    `read_fill`'s fallback is precisely what makes it reachable, because an
    approx read is the first thing in the fleet's history to carry BOTH a real
    price and measured=False. The Farmer's rule would have fed a 180s VWAP blend
    into `implementation_shortfall._fetch_order_slip`, which does an unfiltered
    `AVG(slippage_bps)` — it reads no `measured` flag, so a contaminated row is
    indistinguishable from a clean one. Strict direction wins: record the blend
    as px_fill (it is a real price), record NO slippage from it.
    """
    try:
        d, f = float(decision), float(fill)
        if d <= 0 or f <= 0:
            return None
        if not measured:
            return None
        if d == f:
            return 0.0          # explicit: (f/d - 1) * -1 would give -0.0
        return (f / d - 1.0) * 10_000.0 * (1.0 if is_buy else -1.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
