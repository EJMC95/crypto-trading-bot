#!/usr/bin/env python3
"""
lighter_perp_sniper.py — Lighter-native NEW-PERP-LISTING sniper.

The spiritual analog of the spot Launch Sniper, but for a perps DEX: instead of
brand-new spot pairs across 100 CCXT exchanges, it snipes brand-new PERP MARKETS
the moment Lighter lists them. Built 2026-07-09 at Eamon's request to replace the
spot sniper (which can't run on a fixed-market perps venue) — UNVALIDATED, so it
runs SHADOW-FIRST and only trades real money once he explicitly disarms the kill
switch (venues/safety.py). There is no historical edge to point to here; the
shadow ledger is how we find out whether one exists.

DETECTION (deterministic — the source of truth):
  Diff the current set of active Lighter perp markets against a persisted
  baseline. A symbol present now but not in the baseline = a fresh listing. The
  first run SEEDS the baseline with all current markets and buys nothing (so it
  never snipes the existing 215). AnnouncementApi text is attached as CONTEXT
  only (e.g. "New RWA Perp Listing — $WEN"), never trusted as the trigger.

  A detected symbol stays PENDING (retried every loop) until a snipe actually
  opens a position, or until a bounded, logged give-up. Only those two outcomes
  fold it into the baseline — see the 2026-07-17 RETRY FIX below.

TRADE (long-biased new-listing pop, tight risk):
  On a new market: open one LONG clip (LIGHTER_ORDER_USD, default $20), then
  manage with take-profit / stop-loss / max-hold. One position per new market,
  global cap, adapter-level notional cap + daily-loss halt from venues/safety.py.

MODES (venues layer): Lighter-only. Defaults to lighter_shadow; refuses hl_paper.
    VENUE=lighter_shadow  (default) live books, modelled fills, ledger, no send
    VENUE=lighter_testnet real order lifecycle on testnet (faucet funds)
    VENUE=lighter_live    real money — refuses to boot unless REAL_MONEY_KILL
                          is explicitly disarmed (default ARMED)

Usage:
    python lighter_perp_sniper.py            # shadow forever
    python lighter_perp_sniper.py --once     # single scan then exit (smoke)
"""
import argparse
import os
import sys
import time
import logging
from datetime import datetime, timezone

import bot_pnl_store as store

# [2026-07-30] growth rail + the shared scout read; guarded, with both COPYs
# added to Dockerfile.psniper in the same commit (born-dark doctrine).
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None
from venues import venue_context
from venues.safety import open_notional

BOT = "lighter-perp-sniper"

# --------------------------- configuration ----------------------------------
PAPER_START = 1000.0
TAKE_PROFIT_PCT = 0.15      # +15%: new listings pop hard or not at all
STOP_LOSS_PCT = 0.10       # -10% hard stop
MAX_HOLD_SEC = 6 * 3600    # 6h — snipe the debut move, don't marry it
# [2026-07-16 ZOMBIE GUARD] a pulled/delisted book used to mean "hold
# forever" (`if not px: continue` skipped even max-hold) — the most likely
# fate for a fresh listing. Give up after this long continuously
# unpriceable; close at the last seen mid (entry if none).
DELIST_GIVEUP_SEC = float(os.environ.get("SNIPER_DELIST_GIVEUP_SEC", str(6 * 3600)))
MAX_OPEN = 4               # global cap on concurrent snipes
# [2026-07-30] the SURGE trigger — see surge_candidates(). A book whose 24h
# volume jumps by this multiple is treated as a snipe candidate alongside a
# genuinely new listing. Registry-bounded lever `sniper.surge_mult` [2.0, 8.0];
# the scout's own surge detector uses 3.0, so this starts aligned with it.
# Set SNIPER_SURGE_MULT=0 to disable the second source entirely.
SURGE_MULT = float(os.environ.get("SNIPER_SURGE_MULT", "3.0"))
SURGE_MAX_PER_LOOP = int(os.environ.get("SNIPER_SURGE_MAX_PER_LOOP", "3"))
# [2026-07-30 SCOPE — THE THIRD SOURCE, and the one that actually reaches] A
# book is YOUNG until it has this many daily candles. Measured on the venue:
# the majors carry ~402 daily bars, so a book with a handful is genuinely in
# its debut regime — the same phenomenon "new listing" names, but observable
# for WEEKS instead of for the single loop in which the market-set diff fires.
# That single-loop window is why this bot has n=1 in weeks: not a bad thesis,
# an unobservable event. This source reaches back over the whole young cohort.
YOUNG_MAX_BARS = int(os.environ.get("SNIPER_YOUNG_MAX_BARS", "21"))
YOUNG_MAX_PER_LOOP = int(os.environ.get("SNIPER_YOUNG_MAX_PER_LOOP", "2"))
# A young book still has to be TRADABLE — a debut with no turnover is a
# ghost print, and the sniper's own history is full of one-sided debut books.
YOUNG_MIN_VOL_M = float(os.environ.get("SNIPER_YOUNG_MIN_VOL_M", "0.25"))
# Candle probes per loop for unknown books. Small on purpose: the venue REST
# budget is shared, and the cache is monotone so the cost decays to zero.
YOUNG_PROBE_BUDGET = int(os.environ.get("SNIPER_YOUNG_PROBE_BUDGET", "4"))
# How long a book stays on the offered-ledger before it may be offered again.
# A surge is an EVENT, not a permanent property, so the ledger must forget.
SURGE_COOLDOWN_H = float(os.environ.get("SNIPER_SURGE_COOLDOWN_H", "168"))
LOOP_SECONDS = 60          # poll the market list every minute
DIRECTION_LONG = os.environ.get("SNIPER_DIRECTION", "long").lower() != "short"
# [2026-07-17 RETRY FIX] `baseline |= set(new_listings)` used to run
# UNCONDITIONALLY after the snipe loop, outside every failure path inside it.
# A listing that skipped (one-sided book, book fetch raised, notional cap,
# order failed) was still folded into the baseline, and since detection is
# `active - baseline` it could never surface again. The "will retry next loop"
# comment and the "wait" log were both false: there was no retry, ever. It bit
# exactly when it mattered — `_mid` returns None if EITHER side is empty, and a
# one-sided book is the MOST likely state for a brand-new perp. Measured
# 17-Jul: 0 trades since 9-Jul; FOLKS and SKHY (both listed 14-Jul, after the
# seed) sit in the baseline having never been traded.
# A symbol is now folded in only when a position OPENS, or on a bounded, logged
# give-up. At LOOP_SECONDS=60 the two bounds coincide at ~2h: attempts bound a
# fast loop, age bounds a restart-churn case (first_seen persists, attempts do
# not). Past the debut window a snipe is just a stale random long, so giving up
# is deliberate — but it is LOUD, never silent absorption.
PENDING_MAX_ATTEMPTS = int(os.environ.get("SNIPER_PENDING_MAX_ATTEMPTS", "120"))
PENDING_MAX_AGE_SEC = float(os.environ.get("SNIPER_PENDING_MAX_AGE_SEC", str(2 * 3600)))
# Boot state reads to attempt before refusing to run — see the SEED GUARD below.
STATE_READ_TRIES = int(os.environ.get("SNIPER_STATE_READ_TRIES", "3"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("lighter_perp_sniper.log"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def _mid(book):
    """Mid price from a {bids,asks} book, or None if a side is empty."""
    if book and book.get("bids") and book.get("asks"):
        return (book["bids"][0][0] + book["asks"][0][0]) / 2
    return None


def _announcement_tag(anns, symbol):
    """Return a short context string if a recent announcement mentions `symbol`."""
    for a in anns or []:
        blob = f"{a.get('title', '')} {a.get('content', '')}"
        if symbol in blob or f"${symbol}" in blob:
            return (a.get("title") or "announced").strip()[:60]
    return None


def _snipe_price(orderbook_fn, sym):
    """(price, None) if the book is snipeable, else (None, why-not).

    Split out of the snipe loop so the self-test drives the REAL `_mid`
    semantics — a one-sided debut book is the case that broke this bot.
    """
    try:
        book = orderbook_fn(sym)
    except Exception as e:  # noqa: BLE001
        return None, f"book unavailable ({e})"
    px = _mid(book)
    if not px:
        return None, "no two-sided book yet"
    return px, None


# [2026-07-30 AUTO-REVERT FIX] The operator's env defaults, snapshotted at
# IMPORT. apply_tuning() must hand THESE to get_lever, never the current
# global: get_lever returns its `default` when the lever is absent, expired
# or quarantined, so passing the already-moved value made the rail a ONE-WAY
# RATCHET — a widened lever could never revert, and auto-revert-on-expiry is
# the growth rail's central safety property ("levers EXPIRE back to defaults
# on their own, so auto-revert is the resting state"). Shipped broken in
# (fz); it was inert only because nothing authored the lane yet.
_ENV_DEFAULTS = {"SURGE_MULT": SURGE_MULT}


def active_done(done, now_ts, cooldown_h=None):
    """The offered-ledger entries still inside their cooldown, as a SET.

    Everything older has been forgotten deliberately: a book that surged two
    weeks ago and surges again is a new event. Also PRUNES `done` in place so
    the persisted payload cannot grow without bound. Tolerates the (ga) list
    format and junk timestamps.
    """
    h = SURGE_COOLDOWN_H if cooldown_h is None else cooldown_h
    cutoff = float(now_ts) - float(h) * 3600.0
    live = set()
    for sym in list(done or ()):
        try:
            ts = float(done[sym])
        except (TypeError, ValueError, KeyError):
            done.pop(sym, None)
            continue
        if ts >= cutoff:
            live.add(str(sym))
        else:
            done.pop(sym, None)          # forgotten — offerable again
    return live


def apply_tuning():
    """Growth-rail levers over the env defaults; {} when the rail is dark."""
    global SURGE_MULT
    if tuning is None:
        return {}
    cur = SURGE_MULT
    try:
        val = tuning.get_lever("sniper.surge_mult", _ENV_DEFAULTS["SURGE_MULT"])
    except Exception:  # noqa: BLE001
        return {}
    if val != cur:
        SURGE_MULT = val
        return {"sniper.surge_mult": val}
    return {}


def surge_candidates(surges, mult, already, limit=SURGE_MAX_PER_LOOP):
    """Books the scout reports as volume-SURGING, as snipe candidates.

    [2026-07-30 THE SNIPER'S POPULATION PROBLEM] This bot's event — a brand-new
    perp listing — is too rare to grade: n=1 close in weeks, and the scout's
    `new_listings` is routinely empty. A strategy that cannot accumulate a
    sample cannot be validated, improved, or retired on evidence; it just sits
    on a dashboard row. "New listing" is one instance of the thing this bot is
    actually good at — a book repricing violently with no settled history — and
    a volume surge is the same phenomenon in a book that listed last week.

    Pure: the caller supplies the scout's `vol_surges` rows and the set of
    symbols already handled. `already` is REQUIRED and does real work — every
    surging book is in `baseline` (baseline is seeded with all active markets),
    so baseline cannot dedup these the way it dedups listings, and without a
    separate ledger a surging book would re-enter `pending` every loop forever.
    Bounded by `limit` so one venue-wide volume event cannot flood the pass.
    """
    out = []
    try:
        rows = sorted(surges or [],
                      key=lambda r: -float(r.get("ratio") or 0.0))
    except (TypeError, ValueError, AttributeError):
        return out
    for r in rows:
        if len(out) >= int(limit):
            break
        try:
            sym = str(r.get("sym") or "").strip().upper()
            ratio = float(r.get("ratio") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if sym and sym not in already and ratio >= float(mult):
            out.append(sym)
    return out


def young_candidates(bar_counts, max_bars, vols, min_vol_m, already, limit):
    """Books still inside their DEBUT REGIME, as snipe candidates.

    [2026-07-30 THE SCOPE FIX] `new_listings` is a market-set DIFF: a symbol
    qualifies for exactly the one loop in which it first appears, and only if
    this process is running and its baseline is warm at that moment. That is
    why the book has n=1 in weeks with `new_listings: []` on the bus — the
    thesis (violent repricing in a book with no settled history) is fine; the
    TRIGGER was unobservable. A book with `< max_bars` daily candles is in the
    same state and stays observable for weeks, so the same edge finally gets a
    population to be measured on.

    Pure — the caller supplies the bar counts and the volume map. Ordered
    YOUNGEST first (fewest bars = closest to the debut, where the move is),
    filtered to books with real turnover, deduped against `already` (the same
    ledger the surge source uses: a young book is in `baseline`, so baseline
    cannot dedup it), and bounded by `limit`.
    """
    rows = []
    for sym, n in (bar_counts or {}).items():
        # `str(sym)` alone is too permissive — a None key coerces to the
        # string "NONE" and becomes a tradable-looking candidate. Caught by
        # test_young_candidates_tolerates_junk; require a real string.
        if not isinstance(sym, str):
            continue
        try:
            bars = int(n)
        except (TypeError, ValueError):
            continue
        s = sym.strip().upper()
        if not s or s in (already or set()) or bars > int(max_bars):
            continue
        try:
            vol = float((vols or {}).get(s, 0.0) or 0.0)
        except (TypeError, ValueError):
            vol = 0.0
        if vol < float(min_vol_m):
            continue
        rows.append((bars, -vol, s))
    rows.sort()
    return [s for _, _, s in rows[:int(limit)]]


# [2026-08-04] ADMISSION SOURCES — the three routes into this book. Every
# close used to land in one undifferentiated bucket (`long_<exit>`), so the
# (ga) three-source experiment was unfalsifiable: 9/9 exits were
# `long_max_hold` and nothing could say WHICH source supplied the losers.
# The tuple is the whitelist for both the tag composer and the state restore
# — junk degrades to the un-stamped tag, never to a guessed source.
SNIPE_SOURCES = ("listing", "surge", "young")


def close_reason(was_long, exit_reason, src=None):
    """The ledger close tag, source-stamped — the taker's lens pattern.

    [2026-08-04] `<side>-<source>_<exit>` (e.g. `long-young_max_hold`) when the
    admission source is known, else the historical `<side>_<exit>` — an unknown
    source degrades to the OLD tag, never to a guess (the (ht) rule). Source
    names must stay underscore-free: `bot_pnl_store.split_reason` partitions at
    the FIRST underscore, so `long-young_max_hold` round-trips to
    enter_tag='long-young' / exit='max_hold' and the brain buckets each source
    separately. Forward-only: rows written before this stamp keep their tags.
    """
    side = "long" if was_long else "short"
    if src in SNIPE_SOURCES:
        return f"{side}-{src}_{exit_reason}"
    return f"{side}_{exit_reason}"


def run_snipe_pass(*, candidates, pending, baseline, now_ts, open_now, max_open,
                   try_snipe, is_held=lambda s: False,
                   max_attempts=PENDING_MAX_ATTEMPTS,
                   max_age_sec=PENDING_MAX_AGE_SEC):
    """One snipe pass over `candidates`. Mutates `pending` and `baseline`.

    `try_snipe(sym, open_now)` does the I/O and returns True only if a position
    actually OPENED; any retryable skip returns False. This function owns the one
    rule the old code got wrong: a symbol enters `baseline` on exactly two routes
    — a snipe that opened, or a bounded give-up — and on nothing else.

    `open_now` is passed to `try_snipe` because the notional cap needs the count
    INCLUDING this pass's earlier opens: position snapshots come over REST and
    are eventually consistent, so a clip sent two seconds ago may still be
    invisible. Without it, two snipes in one pass can both price the cap off the
    same stale snapshot and both be admitted (see venues.safety.open_notional).

    `is_held(sym)` is the DOUBLE-OPEN guard. The old unconditional fold was, by
    accident, also a "snipe each market at most once" latch; retrying without
    replacing it would let an order that landed-but-failed-to-ack be sent twice
    (live: a second clip; shadow: PaperBroker.open silently FLIPS the position,
    realising P&L with no record_close). A held symbol is by definition sniped.

    Returns (open_now, sniped, abandoned).
    """
    sniped, abandoned = [], []
    for sym in candidates:
        if is_held(sym):
            pending.pop(sym, None)
            baseline.add(sym)
            log.info("%s: already held — folding into baseline (snipe landed)", sym)
            continue
        rec = pending.setdefault(sym, {"first_seen": now_ts, "attempts": 0})
        age = now_ts - rec["first_seen"]
        # Deliberate abandonment: the ONLY non-success route into the baseline.
        # Checked first and uniformly, so a symbol blocked purely by the cap
        # still ages out instead of sitting pending forever.
        if rec["attempts"] >= max_attempts or age >= max_age_sec:
            pending.pop(sym, None)
            baseline.add(sym)
            abandoned.append(sym)
            log.warning("%s: GIVING UP after %d attempts / %.0f min unsnipeable"
                        " — folding into baseline; it will NOT be retried.",
                        sym, rec["attempts"], age / 60)
            continue
        if open_now >= max_open:
            # The cap is the fleet's state, not this listing's fault: stay
            # pending and burn no retry budget, so a freed slot still gets it.
            log.info("%s: cap %d reached — stays pending (age %.0f min)",
                     sym, max_open, age / 60)
            continue
        if try_snipe(sym, open_now):
            pending.pop(sym, None)
            baseline.add(sym)
            sniped.append(sym)
            open_now += 1
            continue
        rec["attempts"] += 1
    return open_now, sniped, abandoned


def main():
    ap = argparse.ArgumentParser(description="Lighter new-perp-listing sniper")
    ap.add_argument("--once", action="store_true", help="single scan then exit")
    args = ap.parse_args()

    # Lighter-only: default to shadow, and refuse the hl_paper default outright —
    # sniping Lighter listings on a Hyperliquid client makes no sense.
    os.environ.setdefault("VENUE", "lighter_shadow")
    ctx = venue_context(bot=BOT, paper_start=PAPER_START)
    if ctx.mode == "hl_paper":
        log.error("lighter_perp_sniper is Lighter-only. Set VENUE=lighter_shadow"
                  " | lighter_testnet | lighter_live.")
        sys.exit(2)
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(20.0)
    max_open = min(MAX_OPEN, ctx.max_open_positions(MAX_OPEN))
    venue_tag = "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Restore paper account + baseline + open snipes from Postgres.
    entry_ts = {}
    # [2026-08-04] sym -> admission source ("listing"|"surge"|"young"), set at
    # snipe time and consumed at close to stamp the ledger tag. Persisted with
    # entry_ts (same lifecycle): a restart that forgot it would close every
    # held position under the un-stamped tag and silently un-grade the very
    # sources the (ga) experiment exists to compare.
    entry_src = {}
    baseline = set()
    pending = {}          # sym -> {"first_seen": ts, "attempts": n} — detected, not yet sniped
    # [2026-07-30] the SURGE source's own dedup ledger (see surge_candidates).
    # Persisted with the rest of the state: a restart that forgot it would
    # re-offer every book that has ever surged, which is the retry-forever bug
    # baseline cannot prevent for this source.
    # [2026-07-30 COOLDOWN, not a tombstone] `surge_done` was a monotone SET
    # that only ever grew, so every book that surged or was young once was
    # excluded FOREVER — over weeks both new candidate sources decay to
    # silence, which is a slow-acting version of the exact starvation (ga)
    # set out to fix. It is now {sym: last_offered_ts} with a cooldown: a
    # book that surged a fortnight ago and surges again is a GENUINE new
    # event, not a duplicate. `not_young` stays permanent — that one is
    # correct, because books only ever age.
    surge_done = {}
    # [2026-07-30] young-book probe cache. `bar_counts` holds measured daily-bar
    # counts for books still under the young bar; `not_young` is the permanent
    # exclusion set (a book that has aged past the bar can never re-enter).
    bar_counts = {}
    not_young = set()
    no_px_since = {}      # coin -> first ts the book was unpriceable (zombie clock)
    last_px = {}          # coin -> last seen mid (zombie exit price)
    # [2026-07-17 SEED GUARD] The seed below (`if not baseline`) absorbs every
    # active market by design — correct on a true first run, catastrophic on a
    # Postgres blip, because load_state() returns None for BOTH. That path would
    # silently re-create the very absorption bug this file was fixed for, so an
    # unreadable state is a REFUSAL, not an empty one: crash-loop loudly (Railway
    # restarts us, the watchdog sees it) rather than poison the baseline.
    # No DB AT ALL is the same poison arriving by a different road, and it is not
    # hypothetical: a Railway env var went missing on 16-Jul (see f44e3eb). With
    # no persistence this bot re-seeds every boot, absorbs every listing, and
    # publishes a healthy row while sniping nothing — the exact silent-zero this
    # file was fixed for. Retrying cannot help (an unset var will not appear), so
    # say the real cause and refuse now rather than after 3 misleading tries.
    #
    # [2026-07-17 FUNDED-MODE FIX] Every line of this guard, and the restore it
    # protects, used to be gated `if dry_run` — so it existed only in shadow. In
    # lighter_live/lighter_testnet the venues layer returns broker=None, hence
    # dry_run=False, hence the baseline was never read back: each boot re-seeded
    # from the current active set, silently absorbing any listing that appeared
    # during the restart, and the pending retry clock died with the process. The
    # case for a durable baseline is about DETECTION, which is venue-independent
    # — if anything it is stronger with real money, where a missed listing and a
    # doubled clip both cost. Only the paper broker's own state is dry_run-
    # specific. State is keyed by ctx.bot_id, which the venues layer already
    # suffixes per mode (-lshadow / -ltest / -lighter), so the live row reads and
    # writes its OWN baseline and can never inherit the shadow twin's.
    _saved, _ok = None, True
    if not os.environ.get("DATABASE_URL", "").strip():
        log.error("DATABASE_URL is not set. This sniper's correctness DEPENDS on a"
                  " durable baseline: with no persistence every boot re-seeds and"
                  " absorbs every live listing, so it would look online and snipe"
                  " nothing. Refusing to run.")
        sys.exit(3)
    for _try_n in range(1, STATE_READ_TRIES + 1):
        _ok, _saved = store.load_state_checked(bot_id)
        if _ok:
            break
        log.error("state read FAILED (try %d/%d) — NOT seeding: an unreadable"
                  " state is indistinguishable from a fresh bot, and seeding"
                  " now would absorb every live listing forever.",
                  _try_n, STATE_READ_TRIES)
        if _try_n < STATE_READ_TRIES:
            time.sleep(LOOP_SECONDS)
    if not _ok:
        log.error("state unreadable after %d tries — exiting rather than "
                  "seeding a false baseline.", STATE_READ_TRIES)
        sys.exit(3)
    if _saved:
        if dry_run and broker.restore_state(_saved.get("broker") or {}):
            log.info("restored paper state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        baseline = set(_saved.get("baseline") or [])
        entry_ts = {str(k): float(v) for k, v in (_saved.get("entry_ts") or {}).items()}
        # [2026-08-04] restore the admission-source map. Whitelisted through
        # SNIPE_SOURCES: a junk value is DROPPED, so its close degrades to the
        # old un-stamped tag rather than inventing a source. A missing entry is
        # correct for positions opened before this stamp shipped (forward-only).
        entry_src = {str(k): str(v) for k, v
                     in (_saved.get("entry_src") or {}).items()
                     if str(v) in SNIPE_SOURCES}
        # [2026-07-30 (ha)] restore the zombie clock — see save_state below.
        # A missing entry is correct (the coin becomes priceable again and the
        # clock is irrelevant); a RESET entry was the defect.
        no_px_since.update({str(k): float(v) for k, v
                            in (_saved.get("no_px_since") or {}).items()})
        last_px.update({str(k): float(v) for k, v
                        in (_saved.get("last_px") or {}).items() if v})
        # [2026-07-17 RETRY FIX] persist the retry budget: first_seen must
        # survive a restart or a give-up could never be reached across a
        # deploy loop. A dropped pending entry is self-healing (the symbol
        # isn't in the baseline, so it re-detects), just with a fresh clock.
        for k, v in (_saved.get("pending") or {}).items():
            try:
                # A missing/zero first_seen must NOT default to 0.0 — that is an
                # age of ~55 years, an instant give-up, i.e. the absorption bug
                # again. An unknown clock starts NOW.
                pending[str(k)] = {"first_seen": float(v.get("first_seen") or time.time()),
                                   "attempts": int(v.get("attempts") or 0)}
            except Exception:  # noqa: BLE001
                continue
        # [2026-07-30] the surge source's dedup ledger. A DROPPED entry here
        # is not self-healing the way a dropped `pending` entry is — the symbol
        # is in `baseline`, so nothing else would stop it being re-offered.
        try:
            _sd = _saved.get("surge_done")
            if isinstance(_sd, dict):
                for _k, _v in _sd.items():
                    try:
                        surge_done[str(_k)] = float(_v)
                    except (TypeError, ValueError):
                        continue
            else:
                # the (ga) format was a bare list with no timestamps. Treat
                # those as offered NOW rather than dropping them: a restart
                # must not re-offer everything at once.
                for _x in (_sd or []):
                    surge_done[str(_x)] = time.time()
            not_young.update(str(x) for x in (_saved.get("not_young") or []))
            for _k, _v in (_saved.get("bar_counts") or {}).items():
                bar_counts[str(_k)] = int(_v)
        except Exception:  # noqa: BLE001
            pass
        if pending:
            log.info("restored %d pending listing(s) awaiting a snipeable book: %s",
                     len(pending), ", ".join(sorted(pending)))

    log.info("=" * 64)
    log.info("Lighter NEW-PERP sniper | venue=%s (%s) | dir=%s | clip $%.0f | "
             "TP +%.0f%% SL -%.0f%% hold %.0fh | cap %d",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS",
             "long" if DIRECTION_LONG else "short", order_usd,
             TAKE_PROFIT_PCT * 100, STOP_LOSS_PCT * 100, MAX_HOLD_SEC / 3600, max_open)
    log.info("=" * 64)

    def record_close(coin, ent_px, ent_ts, exit_px, pnl, was_long, reason,
                     notional=None):
        # [2026-07-30 (ha)] ONE BASIS. This derived pnl_pct from the passed
        # exit_px, which in the SHADOW branch is the decision MID — while `pnl`
        # comes back from ShadowBroker.close, which re-fetches the book and
        # crosses it (venues/shadow.py:93-96 -> _shadow_fill). And the entry
        # `_ent` read out of broker.pos is itself a CROSSED fill. So the row
        # carried pnl_abs net of BOTH spreads and pnl_pct net of the entry
        # spread only — two different bases on one close.
        # That is not cosmetic: scripts/golive_readiness.py grades mean/t/win
        # off pnl_pct and halves/drawdown off pnl_abs, so this book was being
        # judged on two inconsistent measures at once.
        # Deriving the percentage FROM pnl makes both identical, and matches
        # what two sibling books already do (lighter_index_bot.py:300
        # `pnl_pct=(pnl / notional)`, lighter_ticket_taker.py:1460
        # `net / clip_used`). Direction is RESTRICT-ONLY: adding the exit
        # spread makes pnl_pct strictly worse, so every gate bar gets harder.
        # The FUNDED branch is unaffected in value — it already computes pnl
        # from exit_px, so pnl/notional returns the same number it did before.
        pnl_pct = None
        if notional:
            pnl_pct = float(pnl) / float(notional)
        elif ent_px:
            pnl_pct = ((exit_px - ent_px) / ent_px) if was_long else ((ent_px - exit_px) / ent_px)
        oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
        store.publish_paper_trade(
            bot_id, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(pnl), pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            # [2026-08-04] source-stamped close tag (`long-young_max_hold` ...)
            # so the brain and study_exit_attribution grade each admission
            # source separately; a position with no recorded source (opened
            # pre-stamp, or a landed-but-unacked order folded in as held)
            # keeps the historical `long_<exit>` tag. Pop: one close consumes
            # the record, same lifecycle as entry_ts.
            reason=close_reason(was_long, reason, entry_src.pop(coin, None)),
            # [2026-07-30 (gr)] EXIT TELEMETRY — computed above for pnl_pct,
            # then discarded. publish_paper_trade has accepted these since
            # 17-Jul, the DB column exists, the reader SELECTs them and
            # /trades.json exposes them: 8 of 9 bots never filled the pipe.
            # Without the prices no exit rule can be counterfactually
            # tested — the price PATH cannot be joined to the trade.
            # Telemetry only; no gate moves.
            entry_price=ent_px, exit_price=exit_px,
            venue=venue_tag, shadow=shadow_tag)

    def _real_exit(coin, was_long, fallback):
        """[2026-07-17 LEDGER FIX] The REAL average exit fill from the venue, or
        the decision mid. Same pattern (and same accessor) as
        lighter_funding_bot._real_exit — closing a LONG SELLS, so is_ask=True.

        Never raises and never blocks: `last_fill` is a best-effort read that
        returns None on any failure, and a ledger row priced at the decision mid
        is a small inaccuracy, where a close that throws is a stuck position.
        """
        if dry_run:
            return fallback
        try:
            fl = getattr(ctx.venue, "last_fill", None)
            real = fl(coin, is_ask=was_long,
                      since_ts=time.time() - 180) if fl else None
        except Exception:  # noqa: BLE001
            real = None
        if real:
            log.info("%s exit fill (venue): %.6g (decision %.6g)",
                     coin, real, fallback or 0.0)
        return real or fallback

    def open_snipe(sym, now_ts, open_now, src=None):
        """Attempt ONE snipe. True only if a position actually opened.

        Every False is a retryable skip — the caller keeps the symbol pending
        rather than folding it into the baseline. `src` is the admission source
        ("listing"|"surge"|"young") recorded into entry_src on success so the
        eventual close carries it; None records nothing (old-style tag).
        """
        px, why = _snipe_price(ctx.venue.orderbook, sym)
        if not px:
            log.info("%s: %s — staying pending, will retry next loop", sym, why)
            return False
        size = round(order_usd / px, 6)
        if size <= 0:
            # PaperBroker.open() silently no-ops on size<=0 and market_open would
            # send a zero clip: returning True here would log a phantom "SNIPED"
            # and fold the symbol into the baseline with no position — the exact
            # absorption this file was fixed for. Refuse instead.
            log.error("%s: clip $%.2f at px %.6f rounds to size 0 — NOT sniping"
                      " (check LIGHTER_ORDER_USD); staying pending",
                      sym, order_usd, px)
            return False
        if dry_run:
            broker.mark(sym, px)
            broker.open(sym, DIRECTION_LONG, size, px)
            if sym not in broker.pos:
                log.error("%s: broker.open did not materialise a position — "
                          "staying pending", sym)
                return False
            entry_ts[sym] = now_ts
        else:
            # [2026-07-17 CAP FIX] was `len(positions()) * order_usd` — the
            # count*clip estimate the 15-Jul CRITICAL fix deleted from both
            # real-money bots and never reached this file (it was the last
            # holdout; the helper is now shared, so there is no third copy to
            # miss next time). Positions are keyed by symbol and were opened at
            # THEIR clip, not the current one: on the live lane a
            # live.clip_scale down-scale would have under-counted deployed
            # notional and walked a new clip straight through the operator's
            # hard cap. `meta={}` — this bot keeps no per-position clip record,
            # so the venue's own avg entry price prices each held position.
            open_ntl = open_notional(ctx.venue.positions(), {}, open_now, order_usd)
            if not ctx.rails.notional_ok(open_ntl, order_usd):
                log.info("%s NOTIONAL_CAP_SKIP ($%.2f deployed + $%.2f clip > "
                         "cap $%s) — staying pending",
                         sym, open_ntl, order_usd, ctx.rails.max_notional)
                return False
            try:
                ctx.venue.market_open(sym, DIRECTION_LONG, size)
                entry_ts[sym] = now_ts
            except Exception as e:  # noqa: BLE001
                log.error("snipe order failed %s: %s — staying pending", sym, e)
                return False
        if src in SNIPE_SOURCES:
            entry_src[sym] = src
        log.info("SNIPED %s %s @ %.6f size %.4f ($%.0f) [src=%s]",
                 sym, "LONG" if DIRECTION_LONG else "SHORT", px, size, order_usd,
                 src or "?")
        return True

    # [2026-07-16 AUDIT FIX] seed W/L from the durable ledger — this bot
    # published NULL counts every loop (the dashboard row showed no record),
    # and `realized_seeded` was assigned but never used (the seeding it
    # promised was never written).
    n_closed, n_wins = 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass
    while True:
        now = datetime.now(timezone.utc)
        try:
            markets = ctx.venue.refresh_markets()
        except Exception as e:  # noqa: BLE001
            log.warning("market refresh failed: %s; retry next loop", e)
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        active = {s for s, m in markets.items() if m.get("status") == "active"}

        # First ever run: SEED the baseline, snipe nothing (never buy the 215).
        if not baseline:
            baseline = set(active)
            store.save_state(bot_id, {"baseline": sorted(baseline),
                                      "broker": broker.to_state() if dry_run else None,
                                      "entry_ts": entry_ts, "pending": pending,
                                      # [2026-08-04] admission-source map —
                                      # same shape at BOTH writers ((ha)).
                                      "entry_src": entry_src,
                                      "surge_done": {k: round(v, 0) for k, v in surge_done.items()},
                                      "bar_counts": bar_counts,
                                      # [2026-07-30 (ha)] the SEED path is a
                                      # SECOND WRITER of this key with what was
                                      # a DIFFERENT key set. In practice it runs
                                      # only on a first-ever boot, when nothing
                                      # is held and the clock is empty anyway —
                                      # but if it ever ran with positions open
                                      # (baseline lost while broker state
                                      # restored) it would overwrite the saved
                                      # state and silently ERASE the zombie
                                      # clock, which is the only exit an
                                      # unpriceable position has. Two writers of
                                      # one key must write the same shape; the
                                      # carry row proved that the expensive way
                                      # earlier today ((gn)).
                                      "no_px_since": {k: round(v, 0) for k, v
                                                      in no_px_since.items()},
                                      "last_px": {k: v for k, v
                                                  in last_px.items() if v},
                                      "not_young": sorted(not_young)})
            log.info("seeded baseline with %d active markets — sniping only NEW "
                     "listings from here.", len(baseline))
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        # A pending symbol is NOT in the baseline, so it stays in new_listings
        # until it is sniped or given up on — that IS the retry.
        new_listings = sorted(active - baseline)
        # Pulled before we could get in. KEEP the retry clock while it's inside
        # the give-up window: popping the record would reset first_seen/attempts
        # on its return, so a symbol flapping in and out of `active` — exactly
        # what a fresh listing's status does around its debut — would never
        # reach the give-up and could be sniped days late. Drop it only once
        # it's past the bound, and never into the baseline: an inactive market
        # that re-lists later is a genuinely new listing.
        for sym in [s for s in pending if s not in active]:
            if now.timestamp() - pending[sym]["first_seen"] >= PENDING_MAX_AGE_SEC:
                pending.pop(sym, None)
                log.info("%s: inactive past the give-up window — dropped from "
                         "pending (never sniped)", sym)
        fresh = [s for s in new_listings if s not in pending]
        if fresh:
            anns = ctx.venue.announcements()
            for sym in fresh:
                tag = _announcement_tag(anns, sym) or "market-set diff"
                log.info("NEW LISTING DETECTED: %s (%s)", sym, tag)

        # ----- open snipes on genuinely new markets -----
        open_now = broker.open_count() if dry_run else len(ctx.venue.positions())
        _held_now = set(broker.pos) if dry_run else set(ctx.venue.positions())
        # [2026-07-30] SECOND CANDIDATE SOURCE — surging books. `surge_done`
        # is this source's own dedup ledger and is NOT optional: every surging
        # book is already in `baseline` (it is seeded with all active markets),
        # so baseline cannot dedup them, and a surging book would otherwise
        # re-enter `pending` on every loop for as long as it kept surging.
        # [2026-07-30] growth rail, every loop. This call site was MISSING
        # when the lever shipped: apply_tuning() was defined, registered and
        # never invoked, so `sniper.surge_mult` could never reach this bot —
        # the same registered-but-inert class the whole pass exists to remove.
        _lv = apply_tuning()
        if _lv:
            log.info("levers applied %s", _lv)
        _surge = []
        if SURGE_MULT > 0 and fleet_bus is not None:
            try:
                _sp = fleet_bus._load("lighter-market", None) or {}
                if fleet_bus.is_fresh(_sp, None):
                    _live_done = active_done(surge_done, now.timestamp())
                    _surge = surge_candidates(_sp.get("vol_surges"), SURGE_MULT,
                                              _live_done | set(pending))
            except Exception:  # noqa: BLE001
                _surge = []
            if _surge:
                log.info("SURGE CANDIDATES (>=%.1fx 24h volume): %s",
                         SURGE_MULT, ", ".join(_surge))
                for _s in _surge:
                    surge_done[_s] = now.timestamp()
        # [2026-07-30] THIRD SOURCE — books still inside their debut regime.
        # The candle probe is GOVERNED and MONOTONE: at most YOUNG_PROBE_BUDGET
        # unknown symbols per loop, and a book measured older than the young bar
        # is recorded in `not_young` FOREVER (books get older, never younger),
        # so the probe cost decays to zero once the venue has been walked.
        _young = []
        if YOUNG_MAX_BARS > 0:
            # [2026-07-30] probe ONLY what the scout could not tell us. Once
            # `ages_d` is flowing this list is empty and the candle probes stop
            # entirely — the fallback costs nothing when it is not needed.
            _scout_ages = {}
            if fleet_bus is not None:
                try:
                    _sp0 = fleet_bus._load("lighter-market", None) or {}
                    if fleet_bus.is_fresh(_sp0, None):
                        _scout_ages = _sp0.get("ages_d") or {}
                except Exception:  # noqa: BLE001
                    _scout_ages = {}
            _unknown = [s for s in sorted(active)
                        if s not in not_young and s not in bar_counts
                        and s not in _scout_ages
                        and s not in active_done(surge_done, now.timestamp())]
            for _sym in _unknown[:YOUNG_PROBE_BUDGET]:
                try:
                    _cs = ctx.venue.candles(
                        _sym, "1d", int((now.timestamp() - 400 * 86400) * 1000),
                        int(now.timestamp() * 1000))
                    _n = len(_cs or [])
                except Exception:  # noqa: BLE001 — budget/venue hiccup, retry later
                    continue
                if _n > YOUNG_MAX_BARS:
                    not_young.add(_sym)      # permanent: it can only age
                else:
                    bar_counts[_sym] = _n
            _vols, _ages = {}, {}
            if fleet_bus is not None:
                try:
                    _sp2 = fleet_bus._load("lighter-market", None) or {}
                    if fleet_bus.is_fresh(_sp2, None):
                        _vols = _sp2.get("vols") or {}
                        # [2026-07-30] EXACT listing age from the venue's own
                        # `created_at`, published by the scout. Strictly better
                        # than the candle probe below: exact rather than a
                        # bar-count proxy, all ~202 books at once rather than
                        # 4/loop, and zero extra REST (the scout already
                        # fetches that response). Measured at ship: majors read
                        # 558.6d, exactly 4 books under 21d.
                        _ages = _sp2.get("ages_d") or {}
                except Exception:  # noqa: BLE001
                    _vols, _ages = {}, {}
            # Prefer the scout's exact ages; the probe cache is the FALLBACK
            # for a dark/stale scout (age in days vs the bar bar — one daily
            # candle per day, so the two units are directly comparable).
            _age_src = ({s: a for s, a in _ages.items()
                         if s not in not_young} or bar_counts)
            _young = young_candidates(_age_src, YOUNG_MAX_BARS, _vols,
                                      YOUNG_MIN_VOL_M,
                                      active_done(surge_done, now.timestamp())
                                      | set(pending), YOUNG_MAX_PER_LOOP)
            if _young:
                log.info("YOUNG-BOOK CANDIDATES (<=%d daily bars): %s",
                         YOUNG_MAX_BARS,
                         ", ".join(f"{s}({bar_counts.get(s)}d)" for s in _young))
                for _s in _young:
                    surge_done[_s] = now.timestamp()
        # [2026-08-04] which source ADMITTED each candidate this pass, for the
        # close-tag stamp. Listing wins a tie (candidate order: it is tried
        # first, so it is the source that actually admitted the symbol);
        # setdefault keeps that priority. A pending symbol from an earlier
        # pass that is no longer in any source list simply has no entry and
        # closes under the old un-stamped tag — never a guessed source.
        _src_map = {s: "listing" for s in new_listings}
        for _s in _surge:
            _src_map.setdefault(_s, "surge")
        for _s in _young:
            _src_map.setdefault(_s, "young")
        open_now, _sniped, _abandoned = run_snipe_pass(
            candidates=new_listings + _surge + _young, pending=pending,
            baseline=baseline,
            now_ts=now.timestamp(), open_now=open_now, max_open=max_open,
            try_snipe=lambda s, n: open_snipe(s, now.timestamp(), n,
                                              src=_src_map.get(s)),
            is_held=lambda s: s in _held_now)

        # ----- manage open snipes (TP / SL / max-hold) -----
        held = (broker.szi() if dry_run
                else {c: v["size"] for c, v in ctx.venue.positions().items()})
        for coin, sz in list(held.items()):
            if not sz:
                continue
            if coin not in entry_ts:
                # [2026-07-17 CLOCK FIX] `entry_ts.get(coin, now.timestamp())`
                # recomputed the default EVERY loop, so a position with no
                # recorded entry had held_sec ~0 forever and max_hold could never
                # fire: held to eternity. That is the same "hold forever" failure
                # the 16-Jul zombie guard closed for unpriceable books, arriving
                # by another road — and unlike that one it is silent, because a
                # 0-second hold looks perfectly healthy.
                # It is reachable on the funded path specifically: entry_ts is
                # set only AFTER market_open RETURNS, so an order that lands but
                # whose ack times out leaves a REAL position with no clock. The
                # is_held guard stops the double-open, but nothing backfilled the
                # timestamp. A restart or a hand-opened position does the same.
                # The true entry time is unknowable here — the venue's position
                # payload carries no open time (lighter_client._positions_from
                # returns size/entry/upnl only) — so start the clock at first
                # sighting and say so out loud. Deliberately conservative: this
                # exits LATE, never early, and never "never".
                entry_ts[coin] = now.timestamp()
                log.warning("%s: held with no entry timestamp (lost order ack, or"
                            " opened before this process started) — starting the"
                            " max-hold clock NOW: it exits %.0fh from this"
                            " sighting, not from its real entry.",
                            coin, MAX_HOLD_SEC / 3600)
            try:
                px = _mid(ctx.venue.orderbook(coin))
            except Exception:  # noqa: BLE001
                px = None
            was_long = sz > 0
            ent_px = broker.pos.get(coin, (0.0, 0.0))[1] if dry_run else \
                ctx.venue.positions().get(coin, {}).get("entry", 0.0)
            zombie = False
            if not px:
                # [2026-07-16 ZOMBIE GUARD] unpriceable book: start the clock;
                # past the give-up, value at the last seen mid (entry if none)
                first = no_px_since.setdefault(coin, now.timestamp())
                if now.timestamp() - first < DELIST_GIVEUP_SEC:
                    continue
                px = last_px.get(coin) or ent_px
                if not px:
                    continue             # nothing to value it at — keep waiting
                zombie = True
            else:
                no_px_since.pop(coin, None)
                last_px[coin] = px
            if dry_run:
                broker.mark(coin, px)
            gain = ((px - ent_px) / ent_px) if (ent_px and was_long) else \
                   ((ent_px - px) / ent_px) if ent_px else 0.0
            held_sec = now.timestamp() - entry_ts[coin]
            reason = None
            if zombie:
                reason = "delisted"
            elif gain >= TAKE_PROFIT_PCT:
                reason = "tp"
            elif gain <= -STOP_LOSS_PCT:
                reason = "sl"
            elif held_sec >= MAX_HOLD_SEC:
                reason = "max_hold"
            if reason:
                if dry_run:
                    _sz, _ent = broker.pos.get(coin, (0.0, 0.0))
                    pnl = broker.close(coin, px)
                    record_close(coin, _ent, entry_ts.pop(coin, None), px, pnl,
                                 _sz > 0, reason,
                                 notional=abs(float(_sz)) * float(_ent))
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    no_px_since.pop(coin, None)
                    last_px.pop(coin, None)
                else:
                    try:
                        ctx.venue.market_close(coin)
                    except Exception as e:  # noqa: BLE001
                        log.error("close failed %s: %s", coin, e)
                        continue
                    # [2026-07-17 LEDGER FIX] a funded close used to record
                    # NOTHING: record_close sat in the dry_run branch only, so
                    # the live row's closed/wins/losses were seeded from an
                    # empty ledger and would have read 0 forever — the same
                    # silent-zero-behind-a-green-row this bot keeps producing
                    # (see the 16-Jul W/L seeding fix, and `watching` before
                    # it). No trade record also means no P&L, and a sniper you
                    # cannot grade cannot earn its way past a review.
                    # Price it at the REAL fill, not the decision mid: this is
                    # the fleet's live-vs-shadow premise (implementation_
                    # shortfall) and the funding bot's established pattern.
                    exit_px = _real_exit(coin, was_long, px)
                    pnl = abs(float(sz)) * ((exit_px - ent_px) if was_long
                                            else (ent_px - exit_px))
                    record_close(coin, ent_px, entry_ts.pop(coin, None),
                                 exit_px, pnl, was_long, reason,
                                 notional=abs(float(sz)) * float(ent_px))
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    no_px_since.pop(coin, None)
                    last_px.pop(coin, None)
                log.info("CLOSED %s [%s] gain %.1f%%", coin, reason, gain * 100)

        # ----- publish + persist -----
        if dry_run:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
            _held_syms = sorted(broker.pos)
        else:
            _pos = ctx.venue.positions()
            pub_equity = None
            pub_open = len(_pos)
            pub_pnl = None
            # [2026-07-17 PUBLISH FIX] the `held` map below read
            # `sorted(broker.pos)` unconditionally, but broker is None in funded
            # modes: AttributeError, raised INSIDE the try and swallowed whole by
            # the bare `except: pass`. The live row published NOTHING — no
            # equity, no counts, and none of the pending/gave_up telemetry added
            # today precisely so a silent sniper can be SEEN. A dashboard row
            # that simply stops updating is the failure this bot keeps having.
            _held_syms = sorted(_pos)
        try:
            store.publish(bot_id, status="online", equity=pub_equity, pnl_abs=pub_pnl,
                          open_trades=pub_open,
                          closed_trades=n_closed, wins=n_wins,
                          losses=n_closed - n_wins,
                          extra={"mode": ctx.mode, "venue": ctx.mode,
                                 "watching": len(baseline),
                                 # [2026-07-17 RETRY FIX] `watching` alone is
                                 # NOT a health signal — the old unconditional
                                 # fold drove it to the active count whether or
                                 # not a snipe ever landed, so a broken bot and
                                 # a healthy one looked identical. These two say
                                 # what the baseline count cannot.
                                 "pending": len(pending),
                                 "gave_up": sorted(_abandoned),
                                 "dir": "long" if DIRECTION_LONG else "short",
                                 # [2026-07-15 GAP FIX] position detail so the
                                 # fleet exposure/concentration view can see
                                 # this book (it was sym_uncovered before).
                                 "held": {c: ("L" if DIRECTION_LONG else "S")
                                          for c in _held_syms},
                                 # [2026-07-30 (go)] the EFFECTIVE gate this
                                 # loop is running. Three of the six books that
                                 # gained levers in (fz) never published one, so
                                 # the evidence board fell back to the REGISTRY
                                 # value — which cannot tell "at the cap" from
                                 # "at the cap it set itself last cycle", the
                                 # exact ambiguity (gd) added this field to
                                 # remove. It also means `extra.caps` is a
                                 # usable deploy receipt for this book, which it
                                 # was NOT: `caps` present proves the container
                                 # is running code that carries apply_tuning.
                                 # Publish-only; no gate moves.
                                 "caps": {"surge_mult": SURGE_MULT,
                                          "max_open": MAX_OPEN}})
        except Exception as e:  # noqa: BLE001
            # Never let telemetry kill the trading loop — but never let it fail
            # in silence either: a bare `except: pass` here is what hid the
            # funded-mode AttributeError above indefinitely.
            log.warning("publish failed (row will go stale): %s", e)
        # [2026-07-17 FUNDED-MODE FIX] was `if dry_run` — the mirror of the
        # restore gate above, and the reason a funded boot had nothing to read
        # back. The seed path already saved unconditionally, so live mode wrote a
        # baseline it then ignored. Only "broker" is dry_run-specific.
        store.save_state(bot_id, {"baseline": sorted(baseline),
                                  "broker": broker.to_state() if dry_run else None,
                                  "entry_ts": entry_ts,
                                  "pending": pending,
                                  # [2026-08-04] admission-source map — the
                                  # close-tag stamp survives a restart, same
                                  # lifecycle as entry_ts ((ha): both writers
                                  # of this key write the same shape).
                                  "entry_src": entry_src,
                                  "surge_done": {k: round(v, 0) for k, v in surge_done.items()},
                                  "bar_counts": bar_counts,
                                  # [2026-07-30 (ha)] PERSIST THE ZOMBIE CLOCK.
                                  # `no_px_since`/`last_px` were module-locals
                                  # that reset to {} on every boot, so
                                  # DELIST_GIVEUP_SEC (6h) required 6h of
                                  # CONTINUOUS uptime. Worse than slow: the
                                  # `continue` in the unpriceable branch
                                  # short-circuits BEFORE the max-hold test, so
                                  # while that clock is unexpired the durable
                                  # entry_ts clock cannot rescue the position —
                                  # the non-durable clock is the ONLY exit, and
                                  # the wrong one of the two was persisted.
                                  # Three sibling implementations of the same
                                  # 16-Jul guard already keep it in persisted
                                  # per-coin meta (dislocation, family, index);
                                  # the sniper was the outlier.
                                  "no_px_since": {k: round(v, 0) for k, v
                                                  in no_px_since.items()},
                                  "last_px": {k: v for k, v
                                              in last_px.items() if v},
                                  "not_young": sorted(not_young)})

        if args.once:
            log.info("--once complete: watching %d markets, %d pending, %d open.",
                     len(baseline), len(pending), pub_open)
            return
        time.sleep(LOOP_SECONDS)


def selftest():
    print("Running Lighter perp sniper offline self-test...\n")
    t0 = 1_000_000.0
    never = lambda s, n: False    # noqa: E731 — every snipe skips
    always = lambda s, n: True    # noqa: E731 — every snipe opens

    # ---- _mid: a one-sided book has NO price. This is why the bug bit a
    # brand-new listing specifically — a fresh perp's debut book is the most
    # likely book in the fleet to have an empty side.
    assert _mid({"bids": [[10.0, 1]], "asks": [[10.2, 1]]}) == 10.1
    assert _mid({"bids": [[10.0, 1]], "asks": []}) is None
    assert _mid({"bids": [], "asks": [[10.2, 1]]}) is None
    assert _mid({"bids": [], "asks": []}) is None
    assert _mid(None) is None

    # ---- _snipe_price surfaces both non-snipeable shapes as retryable
    def _boom(sym):
        raise RuntimeError("503")
    px, why = _snipe_price(_boom, "X")
    assert px is None and "unavailable" in why, (px, why)
    px, why = _snipe_price(lambda s: {"bids": [[5.0, 1]], "asks": []}, "X")
    assert px is None and "two-sided" in why, (px, why)
    px, why = _snipe_price(lambda s: {"bids": [[5.0, 1]], "asks": [[5.2, 1]]}, "X")
    assert px == 5.1 and why is None, (px, why)

    # ---- NEGATIVE FIXTURE — the 2026-07-17 defect, pinned.
    # A new listing whose FIRST orderbook read is one-sided must NOT be
    # absorbed into the baseline: it must survive as pending and still be
    # sniped on a later loop. Under the old `baseline |= set(new_listings)`
    # this fails at loop 2 — the symbol is gone from `active - baseline`
    # forever and `opened` stays empty.
    books = {1: {"bids": [[5.0, 10]], "asks": []},                # debut: bids only
             2: {"bids": [[5.0, 10]], "asks": []},                # still one-sided
             3: {"bids": [[5.0, 10]], "asks": [[5.2, 10]]}}       # two-sided at last
    loop, opened = {"n": 0}, []

    def _try(sym, _open_now):
        px, _why = _snipe_price(lambda s: books[loop["n"]], sym)
        if not px:
            return False
        opened.append((sym, px))
        return True

    baseline, pending = {"OLD"}, {}
    for n in (1, 2):
        loop["n"] = n
        assert sorted({"OLD", "NEW"} - baseline) == ["NEW"], \
            f"loop {n}: a one-sided book absorbed the listing — the 17-Jul bug"
        run_snipe_pass(candidates=sorted({"OLD", "NEW"} - baseline), pending=pending,
                       baseline=baseline, now_ts=t0 + n * LOOP_SECONDS,
                       open_now=len(opened), max_open=4, try_snipe=_try)
        assert "NEW" not in baseline, f"loop {n}: unsniped listing must stay OUT"
        assert pending["NEW"]["attempts"] == n, pending
        assert opened == [], opened
    loop["n"] = 3
    run_snipe_pass(candidates=sorted({"OLD", "NEW"} - baseline), pending=pending,
                   baseline=baseline, now_ts=t0 + 3 * LOOP_SECONDS,
                   open_now=len(opened), max_open=4, try_snipe=_try)
    assert opened == [("NEW", 5.1)], f"the retry must land the snipe: {opened}"
    assert "NEW" in baseline and "NEW" not in pending, (baseline, pending)

    # ---- a snipe that OPENS folds in immediately (the only success route)
    baseline, pending = {"OLD"}, {}
    open_now, sniped, abandoned = run_snipe_pass(
        candidates=["S1"], pending=pending, baseline=baseline, now_ts=t0,
        open_now=0, max_open=4, try_snipe=always)
    assert sniped == ["S1"] and not abandoned and open_now == 1
    assert "S1" in baseline and not pending

    # ---- the cap must NOT absorb, and must burn no retry budget
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["N1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=4, max_open=4, try_snipe=always)
    assert "N1" not in baseline and pending["N1"]["attempts"] == 0, (baseline, pending)
    # ...and a mid-list cap hit leaves the rest pending, not lost (was `break`)
    baseline, pending = {"OLD"}, {}
    _o, sniped, _a = run_snipe_pass(candidates=["B1", "B2"], pending=pending,
                                    baseline=baseline, now_ts=t0, open_now=3,
                                    max_open=4, try_snipe=always)
    assert sniped == ["B1"] and "B2" not in baseline and "B2" in pending

    # ---- a raising orderbook must NOT absorb either
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["X1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4,
                   try_snipe=lambda s, n: bool(_snipe_price(_boom, s)[0]))
    assert "X1" not in baseline and pending["X1"]["attempts"] == 1

    # ---- give-up is BOUNDED by attempts (age pinned) ...
    baseline, pending = {"OLD"}, {}
    for _ in range(PENDING_MAX_ATTEMPTS):
        run_snipe_pass(candidates=["Z1"], pending=pending, baseline=baseline,
                       now_ts=t0, open_now=0, max_open=4, try_snipe=never)
    assert "Z1" not in baseline and pending["Z1"]["attempts"] == PENDING_MAX_ATTEMPTS
    _o, _s, abandoned = run_snipe_pass(candidates=["Z1"], pending=pending,
                                       baseline=baseline, now_ts=t0, open_now=0,
                                       max_open=4, try_snipe=never)
    assert abandoned == ["Z1"] and "Z1" in baseline and "Z1" not in pending

    # ---- ... and independently by AGE (attempts pinned at 1)
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["A1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4, try_snipe=never)
    assert "A1" not in baseline
    _o, _s, abandoned = run_snipe_pass(candidates=["A1"], pending=pending,
                                       baseline=baseline,
                                       now_ts=t0 + PENDING_MAX_AGE_SEC, open_now=0,
                                       max_open=4, try_snipe=never)
    assert abandoned == ["A1"] and "A1" in baseline and "A1" not in pending

    # ---- a cap-blocked listing still ages out (never pends forever)
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["C1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=4, max_open=4, try_snipe=always)
    _o, _s, abandoned = run_snipe_pass(candidates=["C1"], pending=pending,
                                       baseline=baseline,
                                       now_ts=t0 + PENDING_MAX_AGE_SEC, open_now=4,
                                       max_open=4, try_snipe=always)
    assert abandoned == ["C1"] and "C1" in baseline

    # ---- DOUBLE-OPEN GUARD: an order that landed but failed to ack must not be
    # sent twice. The old unconditional fold was an accidental once-only latch;
    # removing it without this guard is a real-money regression (and in shadow
    # PaperBroker.open FLIPS the position, realising P&L with no record_close).
    baseline, pending = {"OLD"}, {}
    sends = []
    run_snipe_pass(candidates=["D1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4,
                   try_snipe=lambda s, n: sends.append(s) or False)  # landed, ack failed
    assert sends == ["D1"] and "D1" not in baseline and pending["D1"]["attempts"] == 1
    run_snipe_pass(candidates=["D1"], pending=pending, baseline=baseline,
                   now_ts=t0 + LOOP_SECONDS, open_now=1, max_open=4,
                   try_snipe=lambda s, n: sends.append(s) or False,
                   is_held=lambda s: s == "D1")                    # ack caught up
    assert sends == ["D1"], f"a held symbol must NEVER be re-sent: {sends}"
    assert "D1" in baseline and "D1" not in pending, (baseline, pending)

    # ---- PaperBroker.open contract (why open_snipe must verify, not assume):
    # it silently no-ops on size<=0, and FLIPS an existing position (a close
    # with no record_close). Both make a bare `return True` a phantom SNIPED.
    from venues.shadow import PaperBroker
    _b = PaperBroker(start_equity=1000.0)
    _b.open("Q", True, 0.0, 5.0)
    assert "Q" not in _b.pos, "size<=0 no-ops silently — open_snipe must check"
    _b.open("Q", True, 1.0, 5.0)
    assert "Q" in _b.pos
    _b.open("Q", True, 1.0, 6.0)          # re-open == flip: closes the old side
    assert _b.realized != 0.0, "re-opening a held symbol realises P&L silently"

    # ---- SEED GUARD: load_state_checked must distinguish "definitely no row"
    # from "I could not find out". A false seed absorbs every live market
    # durably, so an unreadable state must never look empty.
    import bot_pnl_store as _st
    assert hasattr(_st, "load_state_checked"), "the seed guard needs the checked read"
    _ok, _state = _st.load_state_checked("no-such-bot")
    assert _ok is False and _state is None, \
        "no DATABASE_URL must report ok=False (cannot confirm emptiness), not (True, None)"
    assert _st.load_state("no-such-bot") is None, "load_state must still delegate unchanged"

    # ---- NEGATIVE FIXTURE — the count*clip notional cap, pinned in ARITHMETIC.
    # The estimate this file ran until 17-Jul (`len(positions()) * order_usd`)
    # prices HELD positions at the CURRENT clip. They were opened at THEIRS. On
    # the live lane a growth-rail `live.clip_scale` down-scale moves the current
    # clip and nothing else, so the estimate under-reports deployed dollars and
    # admits a clip the operator's hard cap forbids. Three positions opened at
    # $40 = $120 real; clip now $15; cap $130:
    CAP, CLIP = 130.0, 15.0
    _held3 = {c: {"size": 1.0, "entry": 40.0} for c in ("G1", "G2", "G3")}
    assert open_notional(_held3, {}, 3, CLIP) == 120.0, open_notional(_held3, {}, 3, CLIP)
    _old_estimate = len(_held3) * CLIP                       # what this file ran
    assert _old_estimate == 45.0
    assert _old_estimate + CLIP <= CAP, "fixture must reproduce the OLD admit"
    assert open_notional(_held3, {}, 3, CLIP) + CLIP > CAP, \
        "the TRUTH must reject what count*clip admitted — else this fixture is blind"
    # meta['clip'] (what the bot sent) outranks the venue's entry price...
    assert open_notional(_held3, {"G1": {"clip": 99.0}}, 3, CLIP) == 179.0
    # ...and an open this loop that the venue's REST snapshot cannot see yet is
    # still charged to the cap, at the current clip (the open_now - n term).
    assert open_notional({}, {}, 1, CLIP) == CLIP
    assert open_notional(_held3, {}, 4, CLIP) == 120.0 + CLIP

    # ---- NEGATIVE FIXTURE — the FUNDED path, driven end-to-end through main().
    # All three 17-Jul defects live in `if dry_run` branches, so no amount of
    # shadow testing reaches them. venues/__init__ hands funded modes
    # broker=None (hence dry_run=False); this fixture supplies exactly that and
    # asserts the live path SAVES, PUBLISHES, CLOCKS and CAPS. Every assertion
    # below fails on the pre-17-Jul file.
    class _FakeVenue:
        def __init__(self, markets, books, positions):
            self._markets, self._books = markets, books
            self.pos = {k: dict(v) for k, v in positions.items()}
            self.opened, self.closed = [], []

        def refresh_markets(self):
            return self._markets

        def orderbook(self, sym):
            return self._books[sym]

        def announcements(self):
            return []

        def positions(self):
            return {k: dict(v) for k, v in self.pos.items()}

        def market_open(self, sym, is_long, size):
            self.opened.append((sym, is_long, size))
            self.pos[sym] = {"size": size if is_long else -size,
                             "entry": _mid(self._books[sym])}

        def market_close(self, sym):
            self.closed.append(sym)
            self.pos.pop(sym, None)

    class _FakeRails:
        def __init__(self, cap):
            self.max_notional = cap

        def notional_ok(self, open_ntl, add_usd):      # venues/safety.py contract
            return (open_ntl + add_usd) <= self.max_notional + 1e-9

    class _FakeCtx:
        def __init__(self, venue, rails, clip, broker=None, mode="lighter_live"):
            self.mode, self.venue, self.rails = mode, venue, rails
            self.broker = broker          # None IS the funded-mode contract...
            self.dry_run = broker is not None   # ...and venues/__init__ derives
            self._clip = clip                   # dry_run from it exactly so.
            self.bot_id = BOT + ("-lshadow" if mode == "lighter_shadow"
                                 else "-lighter")

        def order_usd(self, default, own=False):
            return self._clip

        def max_open_positions(self, default):
            return default

    class _FakeStore:
        def __init__(self, saved):
            self._saved, self.published, self.saves = saved, [], []
            self.trades = []

        def load_state_checked(self, bot):
            return True, self._saved

        def publish(self, bot, **kw):
            self.published.append((bot, kw))

        def save_state(self, bot, state):
            self.saves.append((bot, state))
            return True

        def fetch_paper_aggregate(self, bot):
            return None

        def publish_paper_trade(self, bot, **kw):
            self.trades.append((bot, kw))

    def _drive(venue, cap, clip, saved, broker=None, mode="lighter_live"):
        """Run ONE --once loop of main() against a fake venue; return the store."""
        g, fs = globals(), _FakeStore(saved)
        keep = (g["venue_context"], g["store"], sys.argv,
                os.environ.get("DATABASE_URL"))
        try:
            g["venue_context"] = lambda **kw: _FakeCtx(venue, _FakeRails(cap), clip,
                                                       broker=broker, mode=mode)
            g["store"] = fs
            sys.argv = ["lighter_perp_sniper.py", "--once"]
            os.environ["DATABASE_URL"] = "postgres://selftest-not-dialled"
            main()
        finally:
            g["venue_context"], g["store"], sys.argv = keep[0], keep[1], keep[2]
            if keep[3] is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = keep[3]
        return fs

    # G1..G3 are positions the venue HAS and the bot never recorded — the
    # lost-ack case: market_open lands, the ack times out, entry_ts is never set.
    # Their book sits at their entry so no TP/SL fires and the pass stays clean.
    _books = {"NEW": {"bids": [[5.0, 10]], "asks": [[5.2, 10]]},
              "G1": {"bids": [[40.0, 5]], "asks": [[40.2, 5]]},
              "G2": {"bids": [[40.0, 5]], "asks": [[40.2, 5]]},
              "G3": {"bids": [[40.0, 5]], "asks": [[40.2, 5]]}}
    _markets = {s: {"status": "active"} for s in ("OLD", "NEW", "G1", "G2", "G3")}
    _state = {"baseline": ["OLD", "G1", "G2", "G3"], "entry_ts": {}, "pending": {}}
    ven = _FakeVenue(_markets, _books, _held3)
    fs = _drive(ven, CAP, CLIP, _state)

    # fix 2 — funded modes PERSIST. Was `if dry_run`: the live row read back
    # nothing and re-seeded (absorbing any listing born during a restart).
    assert fs.saves, "funded mode saved NO state — the 17-Jul dry_run gate"
    _bot, blob = fs.saves[-1]
    assert _bot == BOT + "-lighter", _bot          # its OWN row, not the twin's
    assert blob["broker"] is None                  # no broker to serialise
    assert "OLD" in blob["baseline"]
    # fix 1 — the cap REJECTS $120-deployed + $15 against a $130 cap. The old
    # count*clip saw $45 and would have sent the order. (Asserted before the
    # clock check below so that breaking the cap trips THIS line, not that one.)
    assert ven.opened == [], f"count*clip admitted a cap-breaching clip: {ven.opened}"
    assert "NEW" not in blob["baseline"], "a cap skip must never absorb the listing"
    assert "NEW" in blob["pending"], blob["pending"]
    # fix 4 — a venue position with no recorded entry gets its clock STARTED and
    # REMEMBERED. Was: `entry_ts.get(coin, now)` re-defaulted every loop, so
    # held_sec was ~0 forever and max_hold could never fire.
    assert sorted(blob["entry_ts"]) == ["G1", "G2", "G3"], blob["entry_ts"]
    # fix 3 — the live row PUBLISHES. Was: `sorted(broker.pos)` with broker=None
    # -> AttributeError inside the try, eaten by a bare `except: pass`. Note the
    # failure was SILENT, so the fixture asserts the ROW, not an exception.
    assert fs.published, "funded mode published NOTHING — the 17-Jul AttributeError"
    _bot, kw = fs.published[-1]
    assert kw["extra"]["held"] == {"G1": "L", "G2": "L", "G3": "L"}, kw["extra"]
    assert kw["extra"]["mode"] == "lighter_live" and kw["open_trades"] == 3
    assert kw["equity"] is None and kw["extra"]["pending"] == 1

    # ...and the same pass with headroom SNIPES (the cap rejects, it doesn't jam).
    ven2 = _FakeVenue(_markets, _books, _held3)
    fs2 = _drive(ven2, 1000.0, CLIP, dict(_state, pending={}))
    assert [o[0] for o in ven2.opened] == ["NEW"], ven2.opened
    assert "NEW" in fs2.saves[-1][1]["baseline"]
    assert "NEW" in fs2.saves[-1][1]["entry_ts"], "a funded snipe must clock itself"

    # ---- NEGATIVE FIXTURE — a FUNDED close must write a LEDGER row, priced at
    # the REAL fill. record_close used to live in the dry_run branch alone, so a
    # live close recorded nothing: closed/wins/losses are seeded from the ledger
    # (fetch_paper_aggregate), so the live row would have read 0 closed forever
    # while really trading. T1 is +15.25% on the book -> take-profit.
    _tp_books = dict(_books, T1={"bids": [[46.0, 5]], "asks": [[46.2, 5]]})
    _tp_markets = {s: {"status": "active"} for s in ("OLD", "T1")}
    ven4 = _FakeVenue(_tp_markets, _tp_books, {"T1": {"size": 1.0, "entry": 40.0}})
    fs4 = _drive(ven4, CAP, CLIP, {"baseline": ["OLD", "T1"], "entry_ts": {},
                                   "pending": {}})
    assert ven4.closed == ["T1"], ven4.closed
    assert fs4.trades, "a FUNDED close recorded NO ledger row — the 17-Jul gap"
    _bot4, tr = fs4.trades[-1]
    assert _bot4 == BOT + "-lighter" and tr["pair"] == "T1", (_bot4, tr)
    assert tr["reason"] == "long_tp", tr["reason"]
    assert tr["shadow"] is False and tr["venue"] == "lighter", tr   # REAL money
    # no last_fill on this venue -> falls back to the decision mid (46.1)
    assert abs(tr["pnl_abs"] - 6.1) < 1e-6, tr["pnl_abs"]
    assert fs4.published[-1][1]["closed_trades"] == 1, fs4.published[-1][1]

    # ...and when the venue CAN report the real fill, the row is priced at it —
    # not at the decision mid. This is the whole point of pricing a live ledger
    # off fills (implementation_shortfall's live-vs-shadow premise): a row that
    # echoes back the decision price silently reports zero slippage.
    ven5 = _FakeVenue(_tp_markets, _tp_books, {"T1": {"size": 1.0, "entry": 40.0}})
    ven5.last_fill = lambda coin, is_ask, since_ts, lookback=10: (
        45.0 if (coin == "T1" and is_ask is True) else None)   # sold a long
    fs5 = _drive(ven5, CAP, CLIP, {"baseline": ["OLD", "T1"], "entry_ts": {},
                                   "pending": {}})
    _bot5, tr5 = fs5.trades[-1]
    assert abs(tr5["pnl_abs"] - 5.0) < 1e-6, \
        f"the ledger must use the REAL fill (45.0 -> $5.00), not the mid: {tr5}"
    assert abs(tr5["pnl_pct"] - 0.125) < 1e-9, tr5["pnl_pct"]
    # a last_fill that dies must never block the close — just cost precision
    ven6 = _FakeVenue(_tp_markets, _tp_books, {"T1": {"size": 1.0, "entry": 40.0}})
    def _boom_fill(*a, **k):
        raise RuntimeError("venue trades endpoint 503")
    ven6.last_fill = _boom_fill
    fs6 = _drive(ven6, CAP, CLIP, {"baseline": ["OLD", "T1"], "entry_ts": {},
                                   "pending": {}})
    assert ven6.closed == ["T1"], "a broken fill read must not block the close"
    assert abs(fs6.trades[-1][1]["pnl_abs"] - 6.1) < 1e-6, fs6.trades[-1][1]

    # ---- REGRESSION FIXTURE — the SHADOW path, which is what actually runs
    # today (perp-sniper-shadow / lighter-perp-sniper-lshadow). The fixes above
    # are for a mode nothing runs yet; this asserts the same pass still works
    # where a broker EXISTS, so the funded-mode work cannot quietly break the
    # live book. Same harness, dry_run derived from the broker exactly as
    # venues/__init__ does.
    _seed = PaperBroker(start_equity=1000.0)
    _seed.mark("G1", 40.0)
    _seed.open("G1", True, 1.0, 40.0)     # a restored position with NO entry_ts
    ven3 = _FakeVenue({s: {"status": "active"} for s in ("OLD", "NEW", "G1")},
                      _books, {})
    fs3 = _drive(ven3, CAP, CLIP, {"baseline": ["OLD", "G1"],
                                   "broker": _seed.to_state(),
                                   "entry_ts": {}, "pending": {}},
                 broker=PaperBroker(start_equity=1000.0), mode="lighter_shadow")
    _bot3, blob3 = fs3.saves[-1]
    assert _bot3 == BOT + "-lshadow", _bot3
    assert blob3["broker"] is not None, "shadow must still persist its paper book"
    assert "NEW" in blob3["baseline"], "shadow must still snipe a fresh listing"
    # the backfill is not funded-only: a restored paper position whose clock was
    # lost would have been held forever here too.
    assert sorted(blob3["entry_ts"]) == ["G1", "NEW"], blob3["entry_ts"]
    _bot3, kw3 = fs3.published[-1]
    assert kw3["equity"] is not None and kw3["open_trades"] == 2, kw3
    assert kw3["extra"]["held"] == {"G1": "L", "NEW": "L"}, kw3["extra"]
    assert ven3.opened == [], "shadow must NEVER send an order to the venue"

    # ---- [2026-08-04] SOURCE-STAMPED CLOSE TAGS round-trip through the ONE
    # parser every ledger row passes ((hj): test against the real consumer,
    # never a hand-written fixture). Three properties: each source yields a
    # DISTINCT enter_tag, the exit survives intact (max_hold has its own
    # underscore — the split must be at the FIRST one), and an unknown source
    # degrades to the historical tag, never to a guess.
    for _src in SNIPE_SOURCES:
        assert "_" not in _src, f"source {_src!r} breaks the split contract"
        _r = close_reason(True, "max_hold", _src)
        assert _r == f"long-{_src}_max_hold", _r
        _tag, _exit = store.split_reason(_r)
        assert _tag == f"long-{_src}" and _exit == "max_hold", (_tag, _exit)
    assert close_reason(True, "tp", None) == "long_tp"
    assert close_reason(False, "sl", "junk-source") == "short_sl", \
        "an unrecognised source must degrade to the un-stamped tag"
    _tag, _exit = store.split_reason(close_reason(True, "tp", None))
    assert (_tag, _exit) == ("long", "tp"), (_tag, _exit)

    print("All perp sniper self-tests passed (one-sided debut book RETRIES and "
          "still snipes; cap/exception/skip never absorb; give-up bounded by "
          "attempts AND age; held symbols never double-open; an unreadable "
          "state never looks empty; the FUNDED path saves, publishes, clocks a "
          "lost-ack position and caps on REAL deployed notional; and the SHADOW "
          "path still books, persists and never sends).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        try:
            main()
        except KeyboardInterrupt:
            log.info("stopped by user.")
