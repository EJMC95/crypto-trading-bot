#!/usr/bin/env python3
"""
venues/lighter_client.py — Lighter.xyz venue client (zk perps, zero fees).

Built on lighter-sdk (verified 1.1.1: signer binaries load on BOTH our deploy
target linux/amd64 python:3.11-slim AND the dev Mac arm64 — docs/lighter.md).
The SDK is asyncio; the bots are synchronous, so this client runs one event
loop in a daemon thread and bridges calls with run_coroutine_threadsafe.

Design constraints it encodes (all empirically verified 2026-07-09):
  * Standard tier = 60 WEIGHTED req/min per L1 address shared REST+tx (order
    tx weight 6) -> ALL REST goes through venues.governor.TxBudgetGovernor;
    market data is websocket-first (free: 200 conns/IP, 500 subs/conn).
  * Fleet symbols are HL-style; venues/symbol_map.py translates (kBONK ↔
    1000BONK 1:1, PEPE ↔ 1000PEPE ×0.001). INJ/ATOM/ORDI/TON are unlisted —
    supports() lets bots skip them.
  * Auth model: L1 key NEVER touches this code. Trading uses an API key
    (index 4-254; 0-3 reserved for Lighter's own UI) created from Eamon's
    Ledger on the Mac; env only:
        LIGHTER_API_PRIVATE_KEY   (api key private key, env/Railway secret)
        LIGHTER_ACCOUNT_INDEX     (from accounts_by_l1_address)
        LIGHTER_API_KEY_INDEX     (default 4)
  * Candle dicts come back as {t,o,h,l,c,v} (t in ms) — same keys the HL
    path yields, so strategy code is venue-blind.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import json
import logging
import os
import threading
import time

from .base import VenueClient, VenueError
from .order_keys import fill_key
from .equity_guard import EquityGuard, EquityRejected, vet_account_read
from .governor import TxBudgetGovernor, WEIGHT_INFO, WEIGHT_ORDER_TX

# Tokens the public-tape FILL FALLBACK will not dip below, so a measurement can
# never eat the budget a pending market order (WEIGHT_ORDER_TX=6, capacity ~21)
# still needs. Paired with a NON-BLOCKING acquire, which is the real protection:
# telemetry never QUEUES behind money, it takes a free token or skips and says
# so. Measured on the taker's real 2-open cycle: 17 of 21 tokens spent, so one
# order's reserve leaves the measurement reachable — a reserve of 2 orders
# suppressed the very fill this fix exists to record.
_TELEMETRY_RESERVE = float(os.environ.get("LIGHTER_TELEMETRY_RESERVE",
                                          WEIGHT_ORDER_TX))

#: [(xt)] How long a declined fill stays worth re-reading. The account-filtered
#: tape is ordered by timestamp and paged to 100, so a fill only scrolls out
#: once ~100 further account trades land; 30 min is far inside that for every
#: book in this fleet (the fastest closes ~10/day) and far outside one loop.
_PENDING_FILL_TTL_S = float(os.environ.get("LIGHTER_PENDING_FILL_TTL_S", "1800"))
#: Bound on the queue itself — a venue outage must never grow it without limit.
_PENDING_FILL_MAX = int(os.environ.get("LIGHTER_PENDING_FILL_MAX", "64"))
#: Tries per entry before it is given up as unresolvable and dropped.
_PENDING_FILL_TRIES = int(os.environ.get("LIGHTER_PENDING_FILL_TRIES", "4"))


from .symbol_map import to_lighter

log = logging.getLogger("venues.lighter")


# ---------------------------------------------------------------------------
# MARGIN TRUTH [2026-08-16 (no)] — the venue's own margining fields.
#
# `AccountPosition` has carried `margin_mode`, `initial_margin_fraction`,
# `liquidation_price`, `position_value` and `allocated_margin` since the SDK
# was pinned, and this repo read NONE of them: `_positions_from` kept `size`,
# `entry` and `upnl` and dropped the rest on the floor. The consequence is not
# a missing feature, it is an unanswerable question — "what leverage is the
# real money at, and how far is it from liquidation?" could not be answered
# from the venue's own numbers, only estimated from clip arithmetic.
#
# EVERY parse below fails to None, never to 0. A zero liquidation price reads
# as "cannot be liquidated"; a zero margin fraction reads as "infinite
# leverage". Both are catastrophic misreadings of an ABSENT field, and this is
# the I8 rule at its sharpest — unknown degrades to unknown, never to a guess.
# ---------------------------------------------------------------------------
def _num(v):
    """float(v) or None. Absent, empty, unparseable or non-finite -> None.

    The venue sends these as STRINGS (`StrictStr` on the model), so a bare
    float() on a missing key raises and a bare `float(v or 0)` silently
    fabricates a zero — which for `liquidation_price` is the difference
    between "no liq price published" and "liquidates at zero". Non-finite is
    screened here too, so a NaN can never reach a published payload (I5)."""
    if v is None or isinstance(v, bool):
        # bool is an int in Python, so `float(True)` is 1.0 — a flag would
        # parse as a PRICE. Caught by the (no) mutation round: a boolean mark
        # produced a "4099x from liquidation" reading out of nothing. No venue
        # field here is ever legitimately a bool, so reject the type outright
        # rather than let a type confusion render as a risk number.
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


_MARGIN_MODE_NAMES = None


def _margin_mode_names():
    """{code: name} READ FROM THE SDK, never retyped here.

    A retyped constant is a constant that drifts, and this one decides how a
    real-money position is margined. If the SDK cannot be imported we return
    an EMPTY map, so `_margin_mode` degrades to the raw integer rather than
    inventing a name for a code we cannot verify."""
    global _MARGIN_MODE_NAMES
    if _MARGIN_MODE_NAMES is None:
        try:
            import lighter
            sc = lighter.SignerClient
            _MARGIN_MODE_NAMES = {int(sc.CROSS_MARGIN_MODE): "cross",
                                  int(sc.ISOLATED_MARGIN_MODE): "isolated"}
        except Exception:  # noqa: BLE001
            _MARGIN_MODE_NAMES = {}
    return _MARGIN_MODE_NAMES


def _margin_mode(v):
    """'cross' | 'isolated' | the RAW int for an unrecognised code | None.

    Returning the raw code for an unknown value is deliberate (I8): a new
    venue margin mode must show up as `3` in the payload — visibly unhandled —
    rather than be silently bucketed into one of the two names we know."""
    if v is None:
        return None
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return None
    return _margin_mode_names().get(iv, iv)


def _liq_price(v):
    """Liquidation price, or None when the venue publishes no usable one.

    A non-positive liq price is NOT a price — Lighter sends 0 for a position
    it is not currently margining toward liquidation. Reporting that as 0.0
    would make a short look infinitely safe and a long look already-liquidated,
    which is exactly the direction a risk read must never get wrong."""
    f = _num(v)
    return f if (f is not None and f > 0) else None


def _entry_notional(rec):
    """|size| x entry for one position, or None if either input is unusable.

    ENTRY-based, not mark-based: the forward verification recorded in
    `margin_state_from`'s docstring uses `(|size| x entry) / collateral`, and
    `value` (mark-based) misses by ~1.08%."""
    if not isinstance(rec, dict):
        return None
    size, entry = _num(rec.get("size")), _num(rec.get("entry"))
    if size is None or entry is None:
        return None
    if size != size or entry != entry:                 # NaN in, None out
        return None
    if entry <= 0:
        return None
    return abs(size) * entry


def _bounded_longs(recs, collateral):
    """The coins that PROVABLY cannot be liquidated, as a set.

    The condition is the repo's own algebra, not a new model:
    `scripts/lighter_margin_model.liq_price` returns 0.0 for a long whose
    `1/leverage >= 1.0` — at a price of zero the account is still solvent, so
    no adverse path reaches maintenance and the venue correctly publishes no
    liquidation price. `_liq_price` maps that 0 to None, which is why the coin
    lands in `liq_unknown` in the first place.

    ACCOUNT-LEVEL, and that is the whole subtlety. My first cut asked the
    question per position — `|size| x entry <= collateral` for each — and that
    is WRONG under cross margin, which pools losses: four longs each inside the
    collateral can sum to four times it, and the account is then perfectly
    liquidatable. The sound condition is that the account's TOTAL entry
    notional does not exceed its collateral, i.e. account leverage <= 1x, so
    that a simultaneous total loss of every leg still leaves it solvent.

    EVERY unreadable input returns the empty set, so an absent or unparseable
    field keeps every coin in the refusing set rather than earning it an
    exemption. A SHORT is never bounded — its loss grows without limit as the
    price rises — and the presence of ANY short means the account-level bound
    cannot be established at all, so nothing qualifies.
    """
    if collateral is None or collateral != collateral or collateral <= 0:
        return set()
    total = 0.0
    longs = set()
    for coin, rec in recs.items():
        n = _entry_notional(rec)
        if n is None:
            return set()                               # one unreadable leg
        size = _num((rec or {}).get("size"))
        if size is None or size != size or size == 0:
            return set()
        if size < 0:
            return set()                               # a short is unbounded
        total += n
        longs.add(coin)
    if not longs or total > collateral:
        return set()
    return longs


def _mark_for(marks, coin):
    """The live mark for a FLEET-spelled `coin`, under EITHER spelling, or None.

    [2026-09-02] ONE POSITION, TWO SPELLINGS — ON THE OTHER SIDE OF THE SEAM
    `(xa)` CLOSED. `_positions_from` keys this block by the FLEET symbol
    (`from_lighter`: 1000PEPE -> kPEPE), while `marks.stop_marks` keys its
    output by whatever spelling its CALLER handed it — and since (xa) the
    variant host hands it the VENUE's own spelling, because that is what its
    universe, `meta` and `held` map carry. So a bare `marks.get(coin)` asked
    for `kPEPE`, a mark filed under `1000PEPE` did not answer, and a position
    the venue HAD priced and whose order book read fine was filed as
    unmeasurable.

    MEASURED on 👩 mum's real-money row, 2-Sep 11:0xZ, and every field agrees:
      held        {..., "1000PEPE": "adopted"}       <- venue spelling
      positions   [..., "kPEPE"]                     <- fleet spelling
      liq_mark_blind  ["kPEPE"]                      <- the one 1000-market
      mark_blind      ABSENT                         <- the book read FINE
      headroom    {"ok": false, "reason": "mark_blind", "gap_stop_widths": 18.66}
    Two costs, both real and neither a loss: `nearest_liq` was computed over
    9 of 10 real-money legs, so the published liquidation distance excluded a
    position it could not see; and `mark_blind` is not in this book's
    `fleet_immune.HEADROOM_OK` allowlist, so a spelling paged the operator
    every loop — the (gl) failure, a detector whose output one learns to
    ignore. `too_close`, the one refusal that means the money is in danger,
    is also unreachable for a 1000-market leg, because such a leg can never
    BE `nearest_liq`. The rail still refused (`mark_blind` is itself a
    refusal), so nothing unsafe was ever admitted — the number was wrong, not
    the verdict.

    FIXED HERE, NOT AT THE CALL SITE, because `lighter_avo_live_bot` and
    `lighter_funding_bot` carry byte-identical `_margin_block` helpers and a
    third caller would inherit the same trap — an instance fix guarantees a
    return visit. `venues.symbol_map` stays the ONE owner of the alias rule
    ((hj)): `to_lighter` is the definitional map, an unknown coin maps to
    itself, so this is a no-op for every market that is not a 1000-market and
    can never resolve to a DIFFERENT market's price.
    """
    if not marks:
        return None
    m = marks.get(coin)
    if m is None:
        alt = to_lighter(coin)[0]
        if alt != coin:
            m = marks.get(alt)
    return m


def margin_state_from(acct, marks=None):
    """The account's margining view, derived from ONE venue account payload.

    PURE — takes the payload, returns a dict. Kept a module-level function so
    it can be tested against a real publisher shape without a venue, a signer
    or a key (the fleet's "test consumers against publisher-built payloads"
    rule; every live-account read is otherwise untestable off Railway).

    Shape:
      equity / collateral  — the venue's own account numbers
      gross                — sum of |position_value| (the VENUE's notional,
                             NOT venues.safety.open_notional, which sums each
                             position at its OWN ENTRY clip because that is
                             what the operator's cap is defined against. The
                             two answer different questions and must never be
                             substituted for one another.)
      leverage             — gross / equity: the answer to "what leverage is
                             the real money actually at". None when either
                             input is unknown — never 0.0.
      mode                 — 'cross' | 'isolated' | 'mixed' | raw code | None
      nearest_liq          — the closest position to liquidation, when marks
                             were supplied and the venue published a liq price
      liq_unknown          — coins holding a position for which the venue
                             published NO liquidation price. Published even
                             when empty, because an omitted key is
                             byte-identical between "everything is safe" and
                             "nothing was measured" — the (lv) census rule.

    TWO THINGS THIS BLOCK DOES NOT GIVE YOU, stated because a half-closed gap
    advertised as closed is worse than an open one:

      * `mmf` IS NOT HERE, and is NOT derivable from what is. To run a
        liquidation model you also need the MARKET-level
        `maintenance_margin_fraction` from /api/v1/orderBookDetails. The trap
        is `imf_pct`: that is the position's INITIAL margin fraction (XAU
        6.66), a different tier, and the plausible-looking `0.6 x imf_pct`
        gives 0.0400 against a true 0.0240 — wrong by 66%, feeding through to
        a -1.54% liquidation-price error. Read mmf per book; never derive it.
        (Same class as the venue's own OP/ARB 399-vs-400 and QQQ-199 /
        US100-200 wrinkles: these are published per book and only look
        derivable.)
      * `margin` (allocated_margin) reads 0.0 on every CROSS-mode position,
        because cross draws on the whole collateral pool rather than
        allocating per position. It is a real measured zero, not a missing
        field — do not read it as "no margin posted".

    Verified forward against the venue 16-Aug on the Farmer's XAU short:
    liq_price(entry, is_long, (|size| x entry) / collateral, mmf) reproduces
    the venue's published `liq` to -0.001%. Note the leverage basis is an
    ENTRY-based notional over COLLATERAL — `value` is MARK-based and using it
    misses by -1.078%.
    """
    positions = LighterClient._positions_from(acct)
    equity = _num(acct.get("total_asset_value"))
    if equity is None:
        equity = _num(acct.get("collateral"))
    gross = 0.0
    have_value = False
    modes, out, unknown = set(), {}, []
    # [2026-08-19 (rb)] `bounded` = the subset of `unknown` the block can PROVE
    # is unliquidatable. `blind` = positions the venue DID price whose mark is
    # unreadable — they matched neither arm of the branch below and so dropped
    # silently out of `nearest_liq`, which is a FAIL-OPEN hole in any consumer
    # that reads only the nearest: a position 3% from its liquidation with a
    # dark order book made the whole account look safe. Reproduced against this
    # publisher and the real gate before the key was added.
    blind = []
    for coin, rec in positions.items():
        val = rec.get("value")
        if val is not None:
            gross += abs(val)
            have_value = True
        if rec.get("mode") is not None:
            modes.add(rec["mode"])
        # `entry` is projected DELIBERATELY, and it is the only field here a
        # consumer cannot derive: without the venue's own avg_entry_price the
        # published block cannot be checked against a margin model at all.
        # [2026-08-16] I claimed a 0.000000% calibration of
        # scripts/lighter_margin_model against this payload and it was
        # CIRCULAR — I inverted liq_price to get an entry, then fed that entry
        # back through liq_price. It returns 0.000000% for leverage 9.9, mmf
        # 0.9 and a $1 liq price; it could not fail, so it verified nothing.
        # A real check needs an INDEPENDENT entry, which is this field.
        #
        # `size` is projected for TWO reasons, and the second is the bigger one.
        # (1) The forward test's leverage basis is (|size| x entry) / collateral
        #     — an ENTRY-based notional. `value` is the venue's MARK-based
        #     notional, so it is the wrong input, and deriving size as
        #     value/mark fails exactly when the mark is blind.
        # (2) SIGN IS DIRECTION, and without it this block could not say
        #     whether a position was long or short at all. `liq_price` takes
        #     `is_long` and its two branches differ, so a consumer had to go
        #     outside the margin block — to a per-bot field like the Farmer's
        #     `held: {"XAU": "S"}` — to run the model against it. Signed here,
        #     so consumers take abs() for notional and the sign for direction.
        row = {k: rec[k] for k in ("size", "value", "liq", "entry", "imf_pct",
                                   "max_lev", "margin", "mode") if k in rec}
        liq, mark = rec.get("liq"), _mark_for(marks, coin)
        if liq is None:
            unknown.append(coin)
            # [2026-08-19 (rb)] WHY the venue published nothing, when the block
            # can prove it. `scripts/lighter_margin_model.liq_price` states the
            # algebra: `if is_long and inv >= 1.0: return 0.0` — a long at or
            # below 1x of collateral CANNOT be liquidated, because its whole
            # loss is bounded by its notional and the account still stands at a
            # price of zero. `_liq_price` then maps that 0 to None, so the coin
            # lands in `liq_unknown` — the SAFEST position class in the fleet,
            # filed under the same key as a genuine read failure.
            #
            # `liq_none` is ADDITIVE and `liq_unknown` stays the superset, so no
            # existing consumer contract moves; a consumer that wants the honest
            # split takes `set(liq_unknown) - set(liq_none)`. Fail-CLOSED: a
            # SHORT never qualifies (its loss is unbounded above), and any coin
            # whose size, entry or the account collateral is missing, unparseable
            # or non-positive stays OUT of `liq_none`, i.e. keeps refusing.
        elif mark:
            m = _num(mark)
            if m and m > 0:
                row["mark"] = m
                # [2026-08-16] `dist_frac`, NOT `dist_pct`. This is a FRACTION
                # — XAU reads 6.35, i.e. 635% — and it shipped one commit under
                # a `_pct` name, in the same payload where I had just renamed
                # `imf` to `imf_pct` to stop exactly this. Caught by a peer
                # against the live feed. Each name states its own unit, so
                # `imf_pct` (percent) and `dist_frac` (fraction) sit together
                # unambiguously; renaming the FIELD rather than rescaling the
                # VALUE keeps every number already published still true.
                row["dist_frac"] = abs(m - liq) / m
            else:
                blind.append(coin)          # liq known, mark unusable
        else:
            blind.append(coin)              # liq known, no mark supplied
        out[coin] = row

    # [(rb)] Account-level, so it must run AFTER every position is seen.
    bounded = sorted(_bounded_longs(positions, _num(acct.get("collateral")))
                     & set(unknown))

    nearest = None
    priced = [(r["dist_frac"], c) for c, r in out.items() if "dist_frac" in r]
    if priced:
        d, c = min(priced)
        nearest = {"coin": c, "dist_frac": d, "liq": out[c].get("liq"),
                   "mark": out[c].get("mark")}

    return {
        "equity": equity,
        "collateral": _num(acct.get("collateral")),
        "gross": round(gross, 6) if have_value else None,
        "leverage": (round(gross / equity, 4)
                     if (have_value and equity and equity > 0) else None),
        "mode": (modes.pop() if len(modes) == 1
                 else ("mixed" if len(modes) > 1 else None)),
        "n": len(out),
        "positions": out,
        "nearest_liq": nearest,
        "liq_unknown": sorted(unknown),
        # Published even when empty — the (lv) census rule: an omitted key is
        # byte-identical between "nothing qualified" and "nothing was measured".
        "liq_none": sorted(bounded),
        "liq_mark_blind": sorted(blind),
    }


def _settle_ms_of(resp):
    """The venue's OWN estimate of how long this tx needs, in ms, or None.

    [2026-07-22] `RespSendTx.predicted_execution_time_ms` is returned on every
    order and had ZERO references in this repo. That is the blocker underneath
    every fill-identity tier: 0 of 81 live orders ever produced a measured fill,
    with BOTH the tx and id tiers reporting `no-match:both` — the tapes were read
    and our trade was not on them YET, because the read fires with no wait at all.
    No naming scheme fixes a tape that does not contain the trade.

    Probed across shapes like `_tx_hash_of`, for the same reason: a None here
    only costs the settle wait (i.e. today's behaviour), never an error.
    """
    for attr in ("predicted_execution_time_ms", "predictedExecutionTimeMs"):
        v = getattr(resp, attr, None)
        if v is None and isinstance(resp, dict):
            v = resp.get(attr)
        if v is not None:
            try:
                f = float(v)
                return f if f > 0 else None
            except (TypeError, ValueError):
                return None
    return None


def _tx_hash_of(tx, resp):
    """Best-effort tx hash from the signer's (tx, resp) pair, or None.

    [2026-07-21] The SDK has returned the send response in several shapes
    across versions (a bare hash string, an object with .tx_hash, a dict) —
    probe them all rather than pin one, because a None here only means the
    fill read falls back to the (measured-broken) client-id tier, never an
    error. A hex-looking string of plausible length is accepted as a hash;
    anything else is not (a str(resp) like '<TxResp ...>' must never match
    a trade's tx_hash by accident — and cannot, since the comparison is
    exact equality against the venue's hex)."""
    for cand in (resp, tx):
        if cand is None:
            continue
        for attr in ("tx_hash", "hash"):
            v = getattr(cand, attr, None)
            if v is None and isinstance(cand, dict):
                v = cand.get(attr)
            if v:
                return str(v)
        if isinstance(cand, str):
            s = cand.strip()
            if len(s) >= 40 and all(c in "0123456789abcdefABCDEF" for c in s):
                return s
    return None

MAINNET_URL = "https://mainnet.zklighter.elliot.ai"
TESTNET_URL = "https://testnet.zklighter.elliot.ai"   # verified live 2026-07-09
BOOK_STALE_SEC = 30.0    # ws book older than this -> REST fallback
# REST book snapshots are cached this long. The ws path already serves books up
# to BOOK_STALE_SEC old, so a <=20s snapshot is no staler than the accepted
# norm — and it stops the equity guard and the strategy's fresh_mid calls from
# double-paying the governor for the same book within one loop.
REST_BOOK_TTL = float(os.environ.get("LIGHTER_REST_BOOK_TTL", "20"))


# [2026-07-17 WITHDRAWN — min_size_error]
# I shipped a guard here that refused an order whose size was below its book's
# `min_base_amount` or whose notional was below `min_quote_amount`, and told the
# operator "$10 is a HARD FLOOR on every Lighter book; there is no $5 clip".
#
# BOTH HALVES ARE REFUTED BY THE FLEET'S OWN ORDER LEDGER, which had the
# evidence sitting in it the whole time:
#   * min_base_amount is NOT enforced for market orders. 16 of 56 real orders
#     were BELOW their book's min_base and the venue ACCEPTED every one —
#     including the LIVE Funding Farmer's ZEC (0.037358 vs a min_base of 0.1,
#     sent 17-Jul 10:36) and HYPE (0.33 vs 0.5), and Tide Rider's TRX (38.8 vs
#     40). The guard would have BLOCKED LIVE REAL-MONEY ENTRIES.
#   * min_quote_amount is NOT a $10 floor. The smallest real order ever sent is
#     $5.00 — four of them (perps-donchian-breakout-lighter, HYPE + kBONK,
#     10/11-Jul) — and they FILLED (67.0896, 66.3824, 0.003998, 0.004142).
#
# WHAT THESE FIELDS ACTUALLY GATE IS UNKNOWN (limit orders? resting orders? UI
# display?). Unknown is the honest answer; the venue is the authority and it
# already rejects what it dislikes, with an error the caller surfaces.
#
# THE LESSON, and it is the same one this whole day was about: I found a field
# named `min_base_amount`, ASSUMED it was enforced, derived a "floor" from it,
# and gave the operator a confident number that the outcome ledger refuted in
# one query. An unmeasured constant makes a false verdict — see
# [[unmeasured-assumptions-make-false-verdicts]]. Ask what MEASURED the number.
# Do not rebuild this without a fixture proving the venue actually rejects a
# sub-minimum MARKET order.


class _BookCache(threading.Thread):
    """One ws connection streaming order_book/{id} for every subscribed market,
    with automatic reconnect + resubscribe. Book state mirrors the SDK's merge
    semantics (price-keyed upsert, size-0 removal)."""

    def __init__(self, host: str):
        super().__init__(daemon=True, name="lighter-book-ws")
        self.url = "wss://" + host.replace("https://", "") + "/stream"
        self.market_ids: set[int] = set()
        self.books: dict[int, dict] = {}
        self.updated: dict[int, float] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self.started_ok = threading.Event()

    def subscribe(self, market_id: int):
        with self._lock:
            if market_id in self.market_ids:
                return
            self.market_ids.add(market_id)
        self._wake.set()  # force a reconnect that picks up the new subscription

    def get(self, market_id: int):
        with self._lock:
            book = self.books.get(market_id)
            ts = self.updated.get(market_id, 0.0)
        if book is None or (time.time() - ts) > BOOK_STALE_SEC:
            return None
        bids = sorted(((float(o["price"]), float(o["size"])) for o in book["bids"]),
                      key=lambda x: -x[0])
        asks = sorted(((float(o["price"]), float(o["size"])) for o in book["asks"]),
                      key=lambda x: x[0])
        return {"bids": bids, "asks": asks}

    def _merge(self, side_new, side_state):
        for new in side_new:
            for old in side_state[:]:
                if new["price"] == old["price"]:
                    old["size"] = new["size"]
                    break
            else:
                side_state.append(new)
        side_state[:] = [o for o in side_state if float(o["size"]) > 0]

    # Browser-like handshake — Lighter's CDN 400s a bare ws upgrade from cloud
    # (datacenter) IPs even though its REST works from the same host, so present
    # as a browser. Best-effort: if the CDN blocks by IP anyway, the client falls
    # back to REST orderbook snapshots (which work) — see the graceful backoff.
    _WS_ORIGIN = "https://app.lighter.xyz"
    _WS_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

    def run(self):
        from websockets.sync.client import connect
        backoff = 1.0
        fails = 0
        degraded_logged = False
        while True:
            try:
                with self._lock:
                    wanted = set(self.market_ids)
                if not wanted:
                    time.sleep(1.0)
                    continue
                self._wake.clear()
                with connect(self.url, open_timeout=15,
                             origin=self._WS_ORIGIN,
                             user_agent_header=self._WS_UA,
                             additional_headers={"Origin": self._WS_ORIGIN}) as ws:
                    for mid in wanted:
                        ws.send(json.dumps({"type": "subscribe",
                                            "channel": f"order_book/{mid}"}))
                    self.started_ok.set()
                    if fails:
                        log.info("book ws reconnected after %d failure(s)", fails)
                    fails, backoff, degraded_logged = 0, 1.0, False
                    while not self._wake.is_set():
                        msg = json.loads(ws.recv(timeout=30))
                        mt = msg.get("type")
                        if mt == "ping":
                            ws.send(json.dumps({"type": "pong"}))
                        elif mt in ("subscribed/order_book", "update/order_book"):
                            mid = int(msg["channel"].split(":")[1].split("/")[-1])
                            with self._lock:
                                if mt == "subscribed/order_book":
                                    self.books[mid] = msg["order_book"]
                                elif mid in self.books:
                                    self._merge(msg["order_book"]["asks"],
                                                self.books[mid]["asks"])
                                    self._merge(msg["order_book"]["bids"],
                                                self.books[mid]["bids"])
                                self.updated[mid] = time.time()
            except Exception as e:  # noqa: BLE001 — reconnect forever
                fails += 1
                # A few quick retries; then assume the venue ws is blocked from
                # this host (cloud-IP CDN 400) and go QUIET — orderbook() falls
                # back to governed REST snapshots, which work. Retry every 10 min
                # in case the block lifts, without spamming the log every cycle.
                if fails <= 3:
                    log.warning("book ws dropped (%s); retry in %.0fs", e, backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                else:
                    if not degraded_logged:
                        log.warning("book ws unavailable after %d tries (%s) — using "
                                    "REST orderbook snapshots; retrying every 10 min", fails, e)
                        degraded_logged = True
                    time.sleep(600.0)


class LighterClient(VenueClient):
    name = "lighter"

    def __init__(self, net: str = "mainnet", with_signer: bool = False,
                 governor: TxBudgetGovernor | None = None,
                 guard_state_key: str | None = None,
                 guard_persist_reject_streak: bool = False):
        try:
            import lighter  # lazy: only lighter modes need the SDK installed
        except ImportError as e:
            raise VenueError(f"lighter-sdk missing (pip install lighter-sdk): {e}")
        self._lighter = lighter
        self.net = net
        self.host = MAINNET_URL if net == "mainnet" else TESTNET_URL
        self.gov = governor or TxBudgetGovernor()

        # one asyncio loop thread for the whole client. aiohttp requires its
        # session objects to be created INSIDE a running loop, so the ApiClient
        # is built by a coroutine on that loop, not here.
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True,
                         name="lighter-async").start()

        async def _build():
            cfg = lighter.Configuration(host=self.host)
            api = lighter.ApiClient(configuration=cfg)
            return (api, lighter.OrderApi(api), lighter.CandlestickApi(api),
                    lighter.FundingApi(api), lighter.AccountApi(api),
                    lighter.AnnouncementApi(api))

        (self._api, self._order_api, self._candle_api, self._funding_api,
         self._account_api, self._announcement_api) = asyncio.run_coroutine_threadsafe(
            _build(), self._loop).result(timeout=30)

        # market metadata (symbol -> id, decimals, mins) — one governed call
        self.markets = self._load_markets()
        self._books = _BookCache(self.host)
        self._books.start()
        self._rest_books: dict[int, tuple[float, dict]] = {}   # market_id -> (ts, book)
        # [(xt)] fills the governor declined, kept for a LATER read against a
        # refilled bucket. Bounded and self-expiring — see drain_pending_fills.
        self._pending_fills: "OrderedDict[str, dict]" = OrderedDict()
        self._drain_last_error = None

        self.signer = None
        self.account_index = None
        self._guard = None
        # RUN-ONCE bots (Ticket Taker) set this so the guard persists its reject
        # streak across relaunches; long-lived bots (Funding Farmer) leave it
        # False so their memory-only streak resets on every redeploy. See
        # EquityGuard(persist_reject_streak=...).
        self._guard_persist_reject_streak = bool(guard_persist_reject_streak)
        if with_signer:
            self._init_signer()
            self.sends_orders = True
            self._guard = self._make_guard(guard_state_key)

        # tidy shutdown for short-lived uses (scripts) — the long-running bots
        # never exit, so this just silences aiohttp "Unclosed session" on exit.
        import atexit
        atexit.register(self.close)

    def close(self):
        try:
            asyncio.run_coroutine_threadsafe(self._api.close(), self._loop).result(timeout=5)
        except Exception:  # noqa: BLE001
            pass

    # ---- plumbing -----------------------------------------------------------
    def _run(self, coro, timeout=30.0, weight=WEIGHT_INFO, gov_timeout=None):
        # gov_timeout=0 -> NON-BLOCKING acquire: take a free token or give up
        # instantly. Telemetry passes 0 so a measurement can never queue ahead
        # of (and delay) a real order. Default None keeps acquire's own 120s.
        _kw = {} if gov_timeout is None else {"timeout": gov_timeout}
        if not self.gov.acquire(weight=weight, **_kw):
            raise VenueError("lighter tx budget exhausted; skipping")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            out = fut.result(timeout=timeout)
            self.gov.reward()
            return out
        except Exception as e:
            msg = repr(e)
            if "429" in msg or "405" in msg:
                self.gov.punish()
                log.warning("lighter rate-limited (%s); backing off", msg[:120])
            raise

    def _load_markets(self):
        r = self._run(self._order_api.order_book_details())
        out = {}
        for d in r.order_book_details:
            dd = d.to_dict()
            out[dd["symbol"]] = {
                "id": int(dd["market_id"]),
                "status": dd.get("status"),
                "price_decimals": int(dd.get("supported_price_decimals",
                                             dd.get("price_decimals", 2))),
                "size_decimals": int(dd.get("supported_size_decimals",
                                            dd.get("size_decimals", 4))),
                "min_base": float(dd.get("min_base_amount") or 0.0),
                "min_quote": float(dd.get("min_quote_amount") or 0.0),
                "last": float(dd.get("last_trade_price") or 0.0),
                "day_vol": float(dd.get("daily_quote_token_volume") or 0.0),
            }
        log.info("lighter %s: %d markets loaded", self.net, len(out))
        return out

    def refresh_markets(self):
        """Re-fetch the market list (governed) and update self.markets. Returns
        the current {symbol: meta} dict — the new-perp sniper diffs this to spot
        freshly-listed markets."""
        self.markets = self._load_markets()
        return self.markets

    def announcements(self):
        """Recent Lighter announcements (list of {title, content, created_at,...}).
        Freeform text — used only as CONTEXT for a new listing, never as the
        detection source of truth. Returns [] on any error."""
        try:
            r = self._run(self._announcement_api.announcement())
            return r.to_dict().get("announcements") or []
        except Exception:  # noqa: BLE001
            return []

    def _resolve(self, coin: str):
        sym, mult = to_lighter(coin)
        m = self.markets.get(sym)
        if m is None or m.get("status") != "active":
            raise VenueError(f"{coin} ({sym}) not listed/active on lighter {self.net}")
        return sym, mult, m

    def supports(self, coin: str) -> bool:
        try:
            self._resolve(coin)
            return True
        except VenueError:
            return False

    # ---- market data ---------------------------------------------------------
    def candles(self, coin, interval, start_ms, end_ms):
        _, _, m = self._resolve(coin)
        n = max(2, min(1500, int((end_ms - start_ms) / self._interval_ms(interval)) + 2))
        r = self._run(self._candle_api.candles(
            market_id=m["id"], resolution=interval,
            start_timestamp=int(start_ms / 1000), end_timestamp=int(end_ms / 1000),
            count_back=n))
        d = r.to_dict()
        if d.get("code") != 200:
            raise VenueError(f"candles {coin} code={d.get('code')}")
        return d.get("c") or []

    @staticmethod
    def _interval_ms(interval):
        unit = interval[-1]
        n = int(interval[:-1])
        return n * {"m": 60, "h": 3600, "d": 86400}[unit] * 1000

    def funding_map(self):
        """Lighter's own funding per market, in fleet symbols. The same endpoint
        also carries binance/bybit/hyperliquid benchmark rows — surfaced under
        '_bench' so the carry bot can do cross-venue math without extra calls."""
        from .symbol_map import from_lighter
        r = self._run(self._funding_api.funding_rates())
        rows = r.to_dict().get("funding_rates") or []
        out = {}
        for row in rows:
            sym = row.get("symbol")
            fleet, _ = from_lighter(sym)
            rec = out.setdefault(fleet, {"rate": 0.0, "mark": 0.0, "vol": 0.0,
                                         "_bench": {}})
            if row.get("exchange") == "lighter":
                rec["rate"] = float(row.get("rate") or 0.0)
            else:
                rec["_bench"][row.get("exchange")] = float(row.get("rate") or 0.0)
        for fleet, rec in out.items():
            sym, _ = to_lighter(fleet)
            m = self.markets.get(sym)
            if m:
                rec["mark"] = m["last"]
                rec["vol"] = m["day_vol"]
        return out

    def orderbook(self, coin):
        _, _, m = self._resolve(coin)
        self._books.subscribe(m["id"])
        book = self._books.get(m["id"])
        if book is not None:
            return book
        # ws not warm (the Railway norm — CDN blocks cloud-IP ws) -> governed
        # REST snapshot, TTL-cached so guard + strategy don't double-pay
        return self._rest_book(m["id"])

    def _rest_book(self, market_id, force=False):
        now = time.time()
        if not force:
            hit = self._rest_books.get(market_id)
            if hit and (now - hit[0]) <= REST_BOOK_TTL:
                return hit[1]
        r = self._run(self._order_api.order_book_orders(market_id=market_id, limit=25))
        d = r.to_dict()
        # REST snapshots come back UNSORTED (the ws cache sorts in _BookCache
        # .get) and every consumer takes [0] as top-of-book — sort here once.
        bids = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                       for o in (d.get("bids") or [])), key=lambda x: -x[0])
        asks = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                       for o in (d.get("asks") or [])), key=lambda x: x[0])
        book = {"bids": bids, "asks": asks}
        self._rest_books[market_id] = (now, book)
        return book

    # ---- account / orders (testnet + live only) ------------------------------
    def _init_signer(self):
        key = os.environ.get("LIGHTER_API_PRIVATE_KEY", "").strip()
        acct = os.environ.get("LIGHTER_ACCOUNT_INDEX", "").strip()
        if not key or not acct:
            raise VenueError("LIGHTER_API_PRIVATE_KEY / LIGHTER_ACCOUNT_INDEX not set "
                             "(env only — never in the repo)")
        self.account_index = int(acct)
        # Indices 0-3 are reserved for Lighter's own desktop/mobile UI; bots use
        # 4-254 (docs.lighter.xyz). Default 4 so a bot key never collides with UI.
        self.api_key_index = int(os.environ.get("LIGHTER_API_KEY_INDEX", "4"))
        # SignerClient.__init__ builds an aiohttp ApiClient internally, which calls
        # asyncio.get_running_loop() — so it MUST be constructed ON the loop thread
        # (like ApiClient in _build), not in this synchronous __init__ context, or
        # it raises RuntimeError('no running event loop'). [live-path fix 2026-07-10]
        async def _mk_signer():
            return self._lighter.SignerClient(
                url=self.host, account_index=self.account_index,
                api_private_keys={self.api_key_index: key})
        self.signer = asyncio.run_coroutine_threadsafe(
            _mk_signer(), self._loop).result(timeout=30)
        err = self.signer.check_client()   # local Go-binary validation (no loop)
        if err:
            raise VenueError(f"lighter signer check failed: {err}")
        # [2026-07-17] STATE THE WHEEL THAT SIGNS REAL ORDERS. requirements.txt
        # pins `lighter-sdk>=1.1.1` — UNPINNED — and 1.1.2 shipped 10-Jul, so
        # every image built since resolves to whatever PyPI's latest is on build
        # day. That wheel IS the signer (SignerClient, create_market_order, the
        # Go binary, the nonce manager): a `pip install` at build time can
        # silently swap the code that moves real money, and the born-dark guard
        # models repo-local imports and CANNOT see a pip dep (its own docstring
        # says so).
        #
        # It is NOT pinned here on purpose: either pin moves the signer under a
        # bot holding real positions, and NOBODY HAS MEASURED which version is
        # actually deployed — the build logs are cached, and `lighter.__version__`
        # is stale upstream ("1.0.0", a release PyPI does not even have; use
        # importlib.metadata). Choosing a pin from an INFERENCE is exactly the
        # mistake this file's own min_size_error withdrawal records.
        #
        # So: measure first. Every boot now names its own signer version, which
        # turns "which SDK signs our orders?" from an argument into a grep.
        try:
            import importlib.metadata as _md
            _sdk = _md.version("lighter-sdk")
        except Exception:  # noqa: BLE001 — never let telemetry block a signer
            _sdk = "unknown"
        # State the FACT (the version), not a claim about the repo. The first
        # cut appended "requirements pins >=1.1.1 — UNPINNED", which was true
        # when written and became a LIE the moment the pin landed hours later —
        # a log line asserting something it cannot know. Same class as the
        # comment-honesty fixes: say what you measured, nothing else.
        log.info("lighter signer ready (account %d, key index %d) | "
                 "lighter-sdk %s (this wheel signs real orders)",
                 self.account_index, self.api_key_index, _sdk)

    def _run_signer(self, coro, timeout=30.0):
        return self._run(coro, timeout=timeout, weight=WEIGHT_ORDER_TX)

    def _make_guard(self, state_key):
        """EquityGuard wiring: cached mids ride the ws/TTL-REST book path (what
        the bots already pay for); fresh mids force new REST snapshots and are
        only fetched on a SUSPECTED dislocation. The last accepted read is
        persisted (bot_pnl_store bot_state, like the durable daily-loss halt)
        so a redeploy can't re-anchor the guard on a dislocated print."""
        from .marks import mid_map
        load = save = None
        if state_key:
            try:
                import bot_pnl_store as _store
                load = lambda: _store.load_state(state_key)          # noqa: E731
                save = lambda st: _store.save_state(state_key, st)   # noqa: E731
            except Exception as e:  # noqa: BLE001 — guard works memory-only too
                log.warning("equity guard: no state persistence (%s)", e)
        return EquityGuard(
            mids_cached=lambda coins: mid_map(self, coins),
            mids_fresh=lambda coins: {c: m for c in coins
                                      if (m := self._mid_fresh(c))},
            load_state=load, save_state=save,
            persist_reject_streak=self._guard_persist_reject_streak)

    def _mid_fresh(self, coin):
        """Force-fresh REST book mid (bypasses ws + TTL caches) — dislocation
        re-check evidence only. Governed weight-1 per coin."""
        try:
            _, _, m = self._resolve(coin)
            book = self._rest_book(m["id"], force=True)
        except Exception:  # noqa: BLE001
            return None
        bids = [px for px, _ in book["bids"] if px > 0]
        asks = [px for px, _ in book["asks"] if px > 0]
        if bids and asks:
            return (max(bids) + min(asks)) / 2.0
        return None

    def _account_payload(self):
        r = self._run(self._account_api.account(by="index",
                                                value=str(self.account_index)))
        d = r.to_dict()
        accts = d.get("accounts") or []
        if not accts:
            raise VenueError("account not found")
        return accts[0]

    @staticmethod
    def _positions_from(acct):
        from .symbol_map import from_lighter
        out = {}
        for p in (acct.get("positions") or []):
            sym = p.get("symbol") or ""
            fleet, _ = from_lighter(sym)
            sign = -1.0 if int(p.get("sign", 1)) < 0 else 1.0
            size = float(p.get("position") or 0.0) * sign
            if size:
                rec = {"size": size,
                       "entry": float(p.get("avg_entry_price") or 0.0)}
                # venue's own mark-to-market — the equity guard cross-checks it
                # against live book mids (extra key is harmless to strategy code)
                try:
                    if p.get("unrealized_pnl") is not None:
                        rec["upnl"] = float(p["unrealized_pnl"])
                except (TypeError, ValueError):
                    pass
                # [2026-08-16 (no)] the venue's MARGIN truth. Additive keys on
                # a dict every strategy already iterates — same contract the
                # `upnl` key above has carried since it was added. A key is
                # OMITTED when the venue did not publish a usable value, so a
                # consumer's `.get()` returns None and cannot mistake a
                # fabricated zero for a measurement.
                for key, src, parse in (
                        ("liq", "liquidation_price", _liq_price),
                        # [2026-08-16] THE UNIT IS IN THE NAME, and it is not a
                        # fraction. CONFIRMED against the venue's own margin
                        # tiers rather than inferred: `orderBookDetails`
                        # publishes `default_initial_margin_fraction` in BASIS
                        # POINTS (XAU 666, BTC 500, ADA/LTC/TRX 1000) and the
                        # position field is exactly that ÷ 100 — matched on
                        # 5 of 5 live positions across both real-money books,
                        # 0 of 5 matching the min tier. Read as a 0-1 fraction
                        # it is wrong by 100×, which is the (unit-purity) class
                        # that already cost this fleet an 8×-overstated funding
                        # APR. `imf` was the name for one deploy and had no
                        # consumers; renamed while that is still free.
                        ("imf_pct", "initial_margin_fraction", _num),
                        ("value", "position_value", _num),
                        ("margin", "allocated_margin", _num),
                        ("funding_paid", "total_funding_paid_out", _num)):
                    val = parse(p.get(src))
                    if val is not None:
                        rec[key] = val
                # the number a human actually wants: what this position's own
                # margin tier permits. Derived, not fetched — 100/imf_pct is
                # exact given the unit above (XAU 6.66% -> 15.02x). Guarded so
                # a zero or absent tier yields no ratio rather than a division
                # blow-up or an infinite "leverage".
                _imf = rec.get("imf_pct")
                if _imf and _imf > 0:
                    rec["max_lev"] = round(100.0 / _imf, 2)
                mode = _margin_mode(p.get("margin_mode"))
                if mode is not None:
                    rec["mode"] = mode
                out[fleet] = rec
        return out

    def _equity_fields(self, acct):
        total = None
        for k in ("total_asset_value", "collateral"):
            if acct.get(k) is not None:
                total = float(acct[k])
                break
        if total is None:
            raise VenueError("no account value field in response")
        coll = float(acct["collateral"]) if acct.get("collateral") is not None else None
        return total, coll, self._positions_from(acct)

    def account_value(self):
        """Venue equity, vetted by the EquityGuard: the print is cross-checked
        against live book mids and the previous ACCEPTED read, and rejected
        (VenueError) on positive evidence of dislocation. [2026-07-11: one
        dislocated total_asset_value print tripped the daily-loss rail and the
        flatten sold into it — see venues/equity_guard.py.] Callers already
        treat a raise as 'equity unreadable this loop'; the day-start baseline
        is captured through this same path, so a dislocated-HIGH baseline is
        vetoed too (cold boots take two agreeing reads)."""
        try:
            return vet_account_read(
                self._guard, lambda: self._equity_fields(self._account_payload()))
        except EquityRejected as e:
            raise VenueError(str(e))

    def pop_capital_moves(self):
        """[2026-07-21 D1] Guard-detected deposits/withdrawals accepted since
        the last pop (see EquityGuard.pop_capital_moves). [] when the guard is
        off — callers fold these into their persisted capital ledger so a
        deposit never prints as trading P&L."""
        return self._guard.pop_capital_moves() if self._guard is not None else []

    def margin_state(self, marks=None):
        """The VENUE's own margining view of this account, or None if unread.

        [2026-08-16 (no)] ONE info call, derived entirely from the account
        payload the venue already returns — no per-symbol fetch, so this costs
        the same as `positions()`.

        `marks` is an optional {coin: price} the caller already has; supplied,
        it adds each position's distance to its liquidation price and the
        nearest one across the book. Omitted, the liq prices are still
        reported raw — the read never fabricates a mark to compute a distance.

        NO ACCOUNT, NO CALL. A shadow arm builds this client with
        `with_signer=False`, which leaves `account_index` None (:457 — it is
        only assigned inside `_init_signer`). Without this guard the read
        would fire a real request with `value="None"` on EVERY loop of every
        shadow book, burn governor budget against the venue, and log a
        warning each time — a telemetry read manufacturing venue traffic for
        an account that does not exist. Caught before shipping by asking what
        this does under total failure rather than on the happy path.
        """
        if self.account_index is None:
            return None
        try:
            return margin_state_from(self._account_payload(), marks)
        except VenueError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("margin_state unavailable: %r", e)
            return None

    def positions(self):
        return self._positions_from(self._account_payload())

    def _scaled(self, m, size, price):
        base = int(round(size * (10 ** m["size_decimals"])))
        px = int(round(price * (10 ** m["price_decimals"])))
        return base, px

    def market_open(self, coin, is_long, size):
        sym, mult, m = self._resolve(coin)
        book = self.orderbook(coin)
        side = book["asks"] if is_long else book["bids"]
        if not side:
            raise VenueError(f"{coin}: empty book")
        # worst acceptable = top of book +/- 2% (market-with-slippage-guard)
        worst = side[0][0] * (1.02 if is_long else 0.98)
        base, px = self._scaled(m, size * mult, worst)
        if base <= 0:
            raise VenueError(f"{coin}: size {size} scales to 0")

        # [2026-07-17] KEEP the client id — it is the fill's exact name. It was
        # computed and thrown away, so the fill read had to guess with
        # (side, since_ts) and VWAP everything that matched. Returned ADDITIVELY:
        # every caller in the fleet discards this dict (the taker only tests it
        # for None), so nothing downstream moves.
        _cid = int(time.time() * 1000) % (2 ** 48)
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=_cid,
            base_amount=base, avg_execution_price=px, is_ask=not is_long,
            api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"order failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))(),
                "client_order_index": _cid,
                # [2026-07-22] the venue's own settle estimate — read_fill waits
                # this long before looking for the fill (bounded by
                # fills.SETTLE_CAP_MS). Was returned and never read.
                "settle_ms": _settle_ms_of(resp),
                # [2026-07-21] the fill's OTHER exact name: every venue trade
                # row stamps the taker's tx_hash, so OUR submission's hash
                # matches OUR fills without depending on the venue echoing
                # client ids (measured live: 0 of 61 real orders ever
                # id-matched — fill_src 'id-miss' on every read).
                "tx_hash": _tx_hash_of(tx, resp)}

    def _our_fills(self, trades, is_ask, since_ts, client_id=None,
                   tx_hash=None):
        """Size-weighted VWAP of OUR fills in a trade list, or None. Shared by
        both read paths so the authoritative and fallback tapes can never
        disagree about what counts as ours.

        [2026-07-17] `client_id` NAMES THE ORDER, and it is what makes this a
        measurement rather than an estimate. VWAP across the partial fills of
        ONE market order is exactly right — that IS the fill price. VWAP across
        DIFFERENT orders is a fabrication: two same-side sells inside the
        `since_ts` window (an open on one lens plus a stop on another) blended
        into a single fake "fill". The old (is_ask, since_ts) match could not
        tell them apart, and the public tape widens the blend from 10 rows of
        OUR trades to 100 rows of the WHOLE market. With the id, neither window
        nor tape choice can corrupt the read.

        Without an id it still falls back to the heuristic, so callers that
        cannot supply one (an exit whose order id was not threaded) are no worse
        off than before — but they get `approx` in the reason so a blended read
        is never mistaken for an exact one.

        OWNERSHIP IS CHECKED ON BOTH PATHS, never replaced by the id. The client
        id is `int(time.time()*1000) % 2**48` — TIMESTAMP-derived and only unique
        PER ACCOUNT, so two accounts ordering in the same millisecond collide.
        My first cut matched on the id ALONE and would have read a stranger's
        fill as ours; the selftest caught it."""
        # [2026-07-21 TX-HASH TIER] the STRONGEST exact name, tried first:
        # every venue trade row stamps the taker transaction's tx_hash, and
        # OUR submission gets that hash back from SendTx — so matching on it
        # cannot depend on the venue propagating client_order_index into the
        # tape (MEASURED live: it does not — 0 of 61 real orders across both
        # live bots ever id-matched; fill_src said 'id-miss' on every read).
        # Partial fills of one IOC market order share the taker's hash, so
        # the VWAP across matches IS the fill price. Ownership is STILL
        # checked (the doctrine below: an id narrows, it never authorises).
        fills = []
        for t in (trades or []):
            # OURS, always — the id narrows, it never authorises.
            ours_ask = getattr(t, "ask_account_id", None) == self.account_index
            ours_bid = getattr(t, "bid_account_id", None) == self.account_index
            if is_ask and not ours_ask:
                continue
            if not is_ask and not ours_bid:
                continue
            if tx_hash:
                th = getattr(t, "tx_hash", None)
                if not th or str(th) != str(tx_hash):
                    continue
            elif client_id is not None:
                # our side's client id must match EXACTLY — no window, no blend
                cid = (getattr(t, "ask_client_id", None) if is_ask
                       else getattr(t, "bid_client_id", None))
                if cid is None or int(cid) != int(client_id):
                    continue
            else:
                ts = float(getattr(t, "timestamp", 0) or 0)
                if ts > 1e12:                # ms -> s (venue stamps ms)
                    ts /= 1000.0
                if ts < float(since_ts) - 5:
                    continue
            px = float(getattr(t, "price", 0) or 0)
            sz = abs(float(getattr(t, "size", 0) or 0))
            if px > 0 and sz > 0:
                fills.append((px, sz))
        if not fills:
            return None
        tot = sum(sz for _, sz in fills)
        return sum(px * sz for px, sz in fills) / tot

    def last_fill_detail(self, coin, is_ask, since_ts, lookback=10,
                         client_id=None, tx_hash=None):
        """[2026-07-17 OBSERVABLE] REAL average fill price for THIS account,
        as (price_or_None, reason). `reason` names WHY a read produced no price
        — the whole point of this method.

        WHY IT EXISTS. `last_fill` returned None for every distinct failure
        through one bare `except`, so a broken read and a genuinely empty tape
        were indistinguishable. MEASURED 17-Jul: the taker's first two REAL
        orders (STRC, 1000BONK) both fell back to the decision price with no
        log line, and the fleet had NO way to tell why — 0 of 57 real-money
        orders in its history carry a measured fill. That is the same defect
        the 17-Jul (g) fix named one level up: "measured 0" and "never
        recorded" must never be conflated. Here: "no fill found" and "the read
        exploded" must never be conflated either.

        TWO TAPES, deliberately. The account-filtered `trades` endpoint is
        AUTHORITATIVE but needs an auth token; the public `recentTrades` needs
        none and carries the same ask_account_id/bid_account_id fields.
        VERIFIED 17-Jul against the venue: our account_index appears in the
        public tape and reproduces both live fills exactly, size to the unit
        (STRC 0.175 @ 85.511 vs a decision 85.629 = 13.78bps; 1000BONK 4580 @
        0.003275 = at mark). So the fallback is a MEASUREMENT, not a guess.
        It is second, not first, because it is a market-wide window: a busy
        book can push our fill out of its 100-row cap, which the
        account-filtered tape cannot do.

        Measurement-only: EVERY path is caught and reported; a broken read can
        never block or unwind an order."""
        if self.signer is None or self.account_index is None:
            return None, "no-signer"
        try:
            _sym, _mult, m = self._resolve(coin)
        except Exception as e:  # noqa: BLE001
            return None, f"resolve-failed:{type(e).__name__}"

        # --- 1) authoritative: account-filtered, auth'd -----------------------
        reason = None
        try:
            auth = self.signer.create_auth_token_with_expiry(
                api_key_index=self.api_key_index)
            if isinstance(auth, tuple):          # sdk returns (token, err)
                auth, _err = auth
                if _err or not auth:
                    reason = f"auth-failed:{str(_err)[:60] or 'empty-token'}"
                    auth = None
            if auth:
                # [2026-07-23 AUDIT] gov_timeout=0 -> NON-BLOCKING, same as the
                # tape-2 fallback below and this module's own invariant
                # ("TELEMETRY MUST NEVER STARVE AN ORDER"). Previously this
                # authoritative read used the default 120s blocking acquire, so
                # in a 429/405 cooldown a post-close FILL MEASUREMENT could stall
                # the single-threaded live loop up to ~120s x3 — no stops
                # evaluated on other held coins, kill/daily-loss checks delayed —
                # in exactly the storm where risk management matters most. On an
                # empty bucket this now raises VenueError (caught just below) and
                # falls through to the spare-budget tape-2 peek. Fill precision
                # under contention is the documented, intended trade-off.
                r = self._run(self._order_api.trades(
                    sort_by="timestamp", sort_dir="desc",
                    limit=max(1, min(int(lookback), 100)),
                    authorization=auth, market_id=m["id"],
                    account_index=self.account_index), gov_timeout=0)
                trades = getattr(r, "trades", None) or []
                px = self._our_fills(trades, is_ask, since_ts, client_id,
                                     tx_hash=tx_hash)
                if px:
                    return px, ("trades(tx)" if tx_hash
                                else "trades" if client_id is not None
                                else "trades(approx)")
                reason = "no-match:trades" if trades else "empty:trades"
        except Exception as e:  # noqa: BLE001 — never raise from telemetry
            reason = f"api-error:trades:{type(e).__name__}:{str(e)[:60]}"

        # --- 2) fallback: PUBLIC market tape, no auth ------------------------
        # TELEMETRY MUST NEVER STARVE AN ORDER. `_run` blocks up to 120s to
        # acquire, and WEIGHT_ORDER_TX is 6 against a capacity of ~21 — so a
        # measurement burst here could make the NEXT market_open wait, or trip
        # the 429 ladder. Take this tape only from genuinely spare budget:
        # skip (naming the skip) rather than queue behind money.
        with self.gov._lock:                       # noqa: SLF001 — read-only peek
            self.gov._refill()                     # noqa: SLF001
            spare = self.gov.tokens - _TELEMETRY_RESERVE
        if spare < WEIGHT_INFO:
            _why = (f"skipped:budget({self.gov.tokens:.1f} tok, reserve "
                    f"{_TELEMETRY_RESERVE}) after {reason or 'trades-empty'}")
            # [(xt)] the tape was NEVER READ — queue it for a refilled bucket
            self._defer_fill(_why, coin, is_ask, since_ts, client_id, tx_hash)
            return None, _why
        try:
            r = self._run(self._order_api.recent_trades(
                market_id=m["id"], limit=100), gov_timeout=0)
            trades = getattr(r, "trades", None) or []
            px = self._our_fills(trades, is_ask, since_ts, client_id,
                                 tx_hash=tx_hash)
            if px:
                _exact = ("-tx" if tx_hash
                          else "" if client_id is not None else "-approx")
                return px, f"recentTrades{_exact}(after {reason or 'trades-empty'})"
            return None, (f"no-match:both({reason or 'trades-empty'})"
                          if trades else f"empty:both({reason or 'trades-empty'})")
        except Exception as e:  # noqa: BLE001
            _why = (f"api-error:recentTrades:{type(e).__name__}"
                    f":{str(e)[:50]} (after {reason or 'trades-empty'})")
            self._defer_fill(_why, coin, is_ask, since_ts, client_id, tx_hash)
            return None, _why

    def _defer_fill(self, reason, coin, is_ask, since_ts, client_id, tx_hash):
        """Queue a fill the governor DECLINED to read, for a later pass.

        Only for reasons that mean THE TAPE WAS NEVER READ — `skipped:budget`
        and `api-error`. `venues/fills.py` is explicit that retrying those in
        the SAME breath "spends the governor's telemetry reserve to fail
        identically", and it is right; this is the other case, minutes later
        against a refilled bucket. A `no-match` is NOT queued: that tape was
        read and our fill was not on it, which a re-read does not change.

        Never raises — a telemetry bookkeeping error must not reach an order."""
        try:
            if not reason or not (str(reason).startswith("skipped:budget")
                                  or str(reason).startswith("api-error")):
                return
            key = fill_key(client_id, tx_hash)
            if key is None or key in self._pending_fills:
                return
            while len(self._pending_fills) >= _PENDING_FILL_MAX:
                self._pending_fills.popitem(last=False)   # oldest goes first
            self._pending_fills[key] = {
                "coin": coin, "is_ask": bool(is_ask),
                "since_ts": float(since_ts), "client_id": client_id,
                "tx_hash": tx_hash, "queued_at": time.time(), "tries": 0,
                "first_reason": str(reason)[:120]}
        except Exception:  # noqa: BLE001
            pass

    def drain_pending_fills(self, limit=3):
        """Re-read fills the governor declined earlier. Returns a list of
        {key, px, reason, coin, is_ask} for the ones that RESOLVED.

        Spends SPARE BUDGET ONLY, exactly like the tape-2 peek it mirrors, and
        stops at the first cycle where there is none — so this can never make
        the next `market_open` queue behind a measurement. That invariant is
        the reason the fill was skipped in the first place and it is not being
        traded away here; what changes is only WHEN the read is attempted.

        Reads the AUTHORITATIVE account-filtered tape only, at full lookback.
        The public tape is a market-wide 100-row window that a busy book pushes
        our fill out of within minutes, so it is sound live and worthless late
        — using it here would manufacture `no-match` and burn the entry's
        tries. Entries expire by TTL and by try count; nothing accumulates.

        Never raises."""
        out = []
        try:
            self._drain_last_error = None
            if not self._pending_fills or self.signer is None \
                    or self.account_index is None:
                return out
            now = time.time()
            for key in list(self._pending_fills)[:max(0, int(limit))]:
                ent = self._pending_fills.get(key)
                if ent is None:
                    continue
                if now - float(ent["queued_at"]) > _PENDING_FILL_TTL_S:
                    self._pending_fills.pop(key, None)
                    continue
                with self.gov._lock:                   # noqa: SLF001
                    self.gov._refill()                 # noqa: SLF001
                    spare = self.gov.tokens - _TELEMETRY_RESERVE
                if spare < WEIGHT_INFO:
                    break          # still no room — try again next cycle
                px, reason = None, "drain-failed"
                try:
                    _sym, _mult, m = self._resolve(ent["coin"])
                    auth = self.signer.create_auth_token_with_expiry(
                        api_key_index=self.api_key_index)
                    if isinstance(auth, tuple):
                        auth, _err = auth
                    if auth:
                        r = self._run(self._order_api.trades(
                            sort_by="timestamp", sort_dir="desc", limit=100,
                            authorization=auth, market_id=m["id"],
                            account_index=self.account_index), gov_timeout=0)
                        trades = getattr(r, "trades", None) or []
                        px = self._our_fills(trades, ent["is_ask"],
                                             ent["since_ts"], ent["client_id"],
                                             tx_hash=ent["tx_hash"])
                        reason = ("trades(tx,deferred)" if ent["tx_hash"]
                                  else "trades(deferred)")
                    else:
                        reason = "auth-failed:deferred"
                except Exception as e:  # noqa: BLE001
                    reason = f"api-error:deferred:{type(e).__name__}"
                if px:
                    self._pending_fills.pop(key, None)
                    out.append({"key": key, "px": px, "reason": reason,
                                "coin": ent["coin"], "is_ask": ent["is_ask"]})
                    continue
                ent["tries"] = int(ent.get("tries") or 0) + 1
                if ent["tries"] >= _PENDING_FILL_TRIES:
                    self._pending_fills.pop(key, None)
        except Exception as e:  # noqa: BLE001
            # [(xt)] A FAIL-OPEN EXCEPT IS A SILENT KILL SWITCH. Telemetry must
            # never raise into a trading loop, so this swallows — but a
            # swallowed programming error here would leave the drain returning
            # `[]` forever, byte-identical to "nothing was pending". Record it
            # so the silence is READABLE; the caller surfaces it.
            self._drain_last_error = f"{type(e).__name__}: {str(e)[:120]}"
        return out

    def last_fill(self, coin, is_ask, since_ts, lookback=10, client_id=None):
        """[2026-07-16 FILL RECON] REAL average fill price, or None. Thin
        back-compat wrapper over `last_fill_detail` — same contract, reason
        dropped. Prefer `last_fill_detail`: a caller that cannot say WHY it
        got no price is how the fleet went 57 real orders without one."""
        return self.last_fill_detail(coin, is_ask, since_ts, lookback,
                                    client_id)[0]

    def position_of(self, coin):
        """This account's position in `coin`, under EITHER spelling.

        [2026-09-02 (xo)] `positions()` is keyed by the FLEET symbol
        (`out[fleet] = rec`, via `from_lighter`), so `1000PEPE` lives under
        `kPEPE`. A caller holding the VENUE spelling looked up a key that is
        never there and got None — and None is the "no position" answer, which
        is how a live book with $440 on the venue read as flat.

        MEASURED ON REAL MONEY, 2-Sep: 👩 mum hit her daily-loss halt at
        17:19Z, `_flatten_all` iterated her position map — which `(xa)`
        normalises to the VENUE spelling to fix a DIFFERENT arm of this same
        confusion — and called `market_close("1000PEPE")`. This lookup missed,
        returned None, and the caller logged its safe-looking
        "venue reports NO position — leaving meta; retry next cycle (not
        booking a phantom close)" and did it again 90 seconds later, forever.
        Her row published `flatten_incomplete: true` with `kPEPE` worth
        $440.02 against $521.77 of equity — 84% of a real-money book that the
        halt could not flatten and the halted loop does not manage (it
        `continue`s past the trading pass, so no roi, no stop, no max_hold).

        Fixed HERE rather than at the call site because this class already
        arrived twice ((xa) the bracket, (xe) the mark) and patching a third
        instance leaves the fourth. `positions()` is the one owner of the map;
        it now answers to the name its own callers hold.
        """
        p = self.positions() or {}
        got = p.get(coin)
        if got is None:
            from .symbol_map import from_lighter
            got = p.get(from_lighter(coin)[0])
        return got

    def market_close(self, coin):
        pos = self.position_of(coin)
        if not pos or not pos["size"]:
            return None
        sym, mult, m = self._resolve(coin)
        is_long = pos["size"] > 0
        book = self.orderbook(coin)
        side = book["bids"] if is_long else book["asks"]
        if not side:
            raise VenueError(f"{coin}: empty book")
        worst = side[0][0] * (0.98 if is_long else 1.02)
        base, px = self._scaled(m, abs(pos["size"]) * mult, worst)
        _cid = int(time.time() * 1000) % (2 ** 48)   # see market_open: the fill's name
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=_cid,
            base_amount=base, avg_execution_price=px, is_ask=is_long,
            reduce_only=True, api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"close failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))(),
                "client_order_index": _cid,
                "settle_ms": _settle_ms_of(resp),   # see market_open
                "tx_hash": _tx_hash_of(tx, resp)}   # see market_open


def _selftest():
    """[2026-07-17] The first selftest this file has ever had.

    It began life proving a guard (`min_size_error`) that turned out to be
    WRONG — see the withdrawal note at the top of this file. What survives is
    the part that was real: the REGRESSION FIXTURES built from actual orders
    the venue actually accepted. They now pin the REFUTATION, so nobody
    rebuilds the floor I invented.

    Scope is honest: pure surfaces only (`_our_fills`' matching rules and the
    order-minimum facts). The loop/signer need a venue and are not covered.
    """
    class _Trade:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Fake:
        account_index = 7
        _our_fills = LighterClient._our_fills

    f = _Fake()          # bound method: f._our_fills(trades, ...) passes self

    # --- THE REFUTATION, pinned as executable fact -------------------------
    # These are REAL orders the venue ACCEPTED. Any future "minimum order"
    # guard must let every one of them through, or it is wrong the same way.
    ACCEPTED_REAL_ORDERS = [
        # (coin,   size,        px,        book min_base, note)
        ("ZEC",    0.037358,    535.4,     0.1,   "LIVE Funding Farmer, 17-Jul 10:36"),
        ("HYPE",   0.33,        59.06,     0.5,   "LIVE Funding Farmer, 17-Jul 05:29"),
        ("TRX",    38.8102,     0.32208,   40.0,  "Tide Rider, 17-Jul 07:42"),
        ("HYPE",   0.0745,      67.0896,   0.5,   "$5.00 order — and it FILLED"),
        ("kBONK",  1250.6,      0.003998,  500.0, "$5.00 order — and it FILLED"),
    ]
    for coin, size, px, min_base, note in ACCEPTED_REAL_ORDERS:
        ntl = size * px
        assert size < min_base or ntl < 10.0, (
            f"{coin}: fixture must actually violate a claimed minimum, else it "
            f"proves nothing")
    # the two facts those orders establish:
    assert any(s < mb for _, s, _, mb, _ in ACCEPTED_REAL_ORDERS), \
        "min_base_amount is NOT enforced — 16 of 56 real orders were under it"
    assert any(s * p < 10.0 for _, s, p, _, _ in ACCEPTED_REAL_ORDERS), \
        "min_quote_amount is NOT a $10 floor — $5 orders filled"

    # --- _our_fills: the client-id match is EXACT, no blending -------------
    t_ours_a = _Trade(timestamp=1_700_000_000_000, price=100.0, size=1.0,
                      ask_account_id=7, bid_account_id=9, ask_client_id=111)
    t_ours_b = _Trade(timestamp=1_700_000_000_000, price=200.0, size=1.0,
                      ask_account_id=7, bid_account_id=9, ask_client_id=222)
    t_theirs = _Trade(timestamp=1_700_000_000_000, price=999.0, size=5.0,
                      ask_account_id=8, bid_account_id=9, ask_client_id=333)
    since = 1_699_999_999_000 / 1000.0
    trades = [t_ours_a, t_ours_b, t_theirs]

    # with an id: EXACTLY that order, never blended with our other same-side fill
    assert f._our_fills(trades, True, since, client_id=111) == 100.0
    assert f._our_fills(trades, True, since, client_id=222) == 200.0
    # without an id: the OLD heuristic blends our two orders into a fiction —
    # this is the defect the client id removes, pinned so it cannot come back
    # unnoticed. 150.0 is the average of two DIFFERENT orders: not a fill price.
    assert f._our_fills(trades, True, since) == 150.0, \
        "id-less path blends — that is why callers must pass client_id"
    # NEVER counts someone else's trade — even when the client id MATCHES.
    # The id is time.time()*1000 % 2**48: unique per ACCOUNT, not globally, so
    # two accounts ordering in the same millisecond collide. My first cut
    # matched on the id alone and this fixture caught it.
    t_collide = _Trade(timestamp=1_700_000_000_000, price=999.0, size=5.0,
                       ask_account_id=8, bid_account_id=9, ask_client_id=111)
    assert f._our_fills([t_collide], True, since, client_id=111) is None, \
        "a client-id COLLISION with another account must never read as our fill"
    assert f._our_fills(trades, True, since, client_id=333) is None
    # partial fills of ONE order DO vwap — that is correct, it IS the fill
    p1 = _Trade(timestamp=1_700_000_000_000, price=100.0, size=1.0,
                ask_account_id=7, bid_account_id=9, ask_client_id=111)
    p2 = _Trade(timestamp=1_700_000_000_000, price=102.0, size=3.0,
                ask_account_id=7, bid_account_id=9, ask_client_id=111)
    assert f._our_fills([p1, p2], True, since, client_id=111) == 101.5

    # --- [2026-07-21] the TX-HASH tier: senior to the id, ownership still --
    # required. Measured live: the venue never echoes client_order_index
    # into the tape (0/61 orders id-matched), but every trade row stamps the
    # taker's tx_hash — which our own submission returns.
    tx1 = _Trade(timestamp=1_700_000_000_000, price=100.0, size=1.0,
                 ask_account_id=7, bid_account_id=9, ask_client_id=999,
                 tx_hash="aa11")
    tx2 = _Trade(timestamp=1_700_000_000_000, price=102.0, size=3.0,
                 ask_account_id=7, bid_account_id=9, ask_client_id=998,
                 tx_hash="aa11")
    tx_other = _Trade(timestamp=1_700_000_000_000, price=999.0, size=5.0,
                      ask_account_id=7, bid_account_id=9, ask_client_id=997,
                      tx_hash="bb22")
    # tx match wins even though NO client id matches (the live defect's shape)
    assert f._our_fills([tx1, tx2, tx_other], True, since,
                        client_id=111, tx_hash="aa11") == 101.5, \
        "partials sharing one tx hash VWAP into the fill"
    # ownership stays senior to the hash — a matching hash on a trade whose
    # ask side is not us must never read as our fill
    tx_stranger = _Trade(timestamp=1_700_000_000_000, price=50.0, size=1.0,
                         ask_account_id=8, bid_account_id=9, ask_client_id=1,
                         tx_hash="aa11")
    assert f._our_fills([tx_stranger], True, since, tx_hash="aa11") is None
    # a supplied-but-unmatched hash is a MISS, never a silent id/heuristic blend
    assert f._our_fills(trades, True, since, client_id=111,
                        tx_hash="nope") is None
    # _tx_hash_of: every response shape the SDK has shipped, junk rejected
    assert _tx_hash_of(None, "f6cac47de876de02a37347e134cc22f7b9e9e186") \
        == "f6cac47de876de02a37347e134cc22f7b9e9e186"
    assert _tx_hash_of(None, {"tx_hash": "abc123"}) == "abc123"

    class _Resp:
        tx_hash = "def456"
    assert _tx_hash_of(None, _Resp()) == "def456"
    assert _tx_hash_of(None, "<TxResp code=200>") is None, \
        "a repr string must never pass as a hash"
    assert _tx_hash_of(None, None) is None

    print("venues.lighter_client _selftest OK (min-order floor REFUTED and "
          "pinned; client-id match exact, id-less path blends; tx-hash tier "
          "senior + ownership-guarded)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    print("venues/lighter_client.py — library; run: python3 -m venues.lighter_client --selftest")
