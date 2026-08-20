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


# [2026-08-13 (lk)] INSTRUMENT-CLASS SCREEN on the surge + young sources —
# crypto perps only. MEASURED on this book's own ledger: non-crypto surge
# entries −$5.01 over 13 closes and non-crypto young −$1.19/2, against crypto
# +$1.13 over 5 across all sources; every surge close exits `max_hold` (the
# tp/sl are bare literals, (gt)), so a surge-long on USDKRW/BOTZ/WHEAT is a
# timer-held drift bet on an instrument whose venue volume surge is its
# UNDERLYING's market event, already priced where the underlying trades —
# not the crypto discovery repricing this book's thesis is about. The
# LISTING source stays UNSCREENED, declared: n=1 (+$0.28) is unmeasured, and
# a listing pop is the book's founding thesis — screening it on no evidence
# would close the source entirely now that most new listings are tokenised.
# Fail-OPEN on a missing fleet_bus; reversible: SNIPER_ALLOW_NONCRYPTO=1.
ALLOW_NONCRYPTO = os.environ.get("SNIPER_ALLOW_NONCRYPTO", "").strip().lower() \
    in ("1", "on", "true", "yes")


def _class_ok(sym):
    """May `sym` enter via the SURGE source? Crypto perps only.

    [(sl)] Scope narrowed from "surge/young" to SURGE. The young source now
    asks `_young_class_ok` — a different question, for a measured reason; see
    below. Nothing about the surge screen changed: its evidence (non-crypto
    surge −$5.01/13, and (sk)'s class-7 surge at −0.840%/trade @6h, negative at
    every hold) is unaffected and it stays crypto-only.
    """
    if ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.is_crypto(sym))
    except Exception:      # noqa: BLE001 — class lookup must never stop a scan
        return True


# [2026-08-20 (sl)] THE YOUNG SOURCE ASKS A DIFFERENT QUESTION — and this is
# the change that gives this book its supply back, not another screen.
#
# THE DEFECT, measured. (lk) applied ONE screen to both sources on evidence
# that was almost entirely SURGE's: non-crypto surge −$5.01 over 13 closes
# versus non-crypto **young −$1.19 over TWO**. The young leg rested on n=2.
# `is_crypto` asks `strategy_index == 2`, and **the venue files crypto-native
# memecoin debuts under class 7** — the same grab-bag that holds tokenised
# pre-IPO equity. So the screen refused exactly the cohort a debut sniper
# exists to trade.
#
# THE COST, measured 20-Aug: the young source published `admitted: 0` for
# **66 consecutive days**. Its live supply on that day was SEVEN books, of
# which five were zero-volume ghosts (AXTI/WDC/SOXS/KORU/KIOXIA — tokenised
# equities that never traded an hour) and the only two with real turnover were
# CASHCAT ($0.45M) and UNITREE ($0.84M), both class 7, both refused. The book
# was not quiet; it was structurally unable to admit anything.
#
# AND THE SUPPLY WAS NEVER DEAD. `(qi)`/`(sk)` reported "ZERO crypto births for
# 86 days", which is true of `strategy_index == 2` and FALSE of the cohort this
# book trades: on the venue-priced axis, births run **1.67-2.00/30d and have
# not stopped in any month measured** — CAP (Jun), ANSEM (Jul), CASHCAT (Aug).
# Corrected in place per I12 rather than left standing.
#
# WHAT REPLACES IT: `fleet_bus.venue_priced` — the axis the (lk) argument was
# really making ("already priced where the underlying trades"). It admits
# crypto-native books INCLUDING class-7 memecoins, and still refuses tokenised
# equity/FX/commodity/pre-IPO. That exclusion is now BETTER evidenced than it
# was: (sl) measured shorting an externally-priced debut at −0.714%/trade,
# **t=−2.04** — the only significant cell in the study — so the half of (lk)
# this keeps is the half the tape supports.
# Reversible independently of the surge screen: SNIPER_YOUNG_ALLOW_ANY=1.
YOUNG_ALLOW_ANY = os.environ.get("SNIPER_YOUNG_ALLOW_ANY", "").strip().lower() \
    in ("1", "on", "true", "yes")


def _young_class_ok(sym):
    """May `sym` enter via the YOUNG source? Books PRICED ON THIS VENUE.

    Fail-OPEN on a missing/raising fleet_bus, exactly as `_class_ok` does — a
    classification outage must never be what stops a debut scan.
    """
    if YOUNG_ALLOW_ANY or ALLOW_NONCRYPTO or fleet_bus is None:
        return True
    try:
        return bool(fleet_bus.venue_priced(sym))
    except Exception:      # noqa: BLE001 — class lookup must never stop a scan
        return True


# [2026-08-20 (sk)] THE PER-SOURCE CENSUS — I18/(lv)'s "a sleeve that opens
# nothing must publish its OWN census at its OWN bar".
#
# MEASURED THE DAY THIS SHIPPED, and it is why the guard exists rather than a
# tidiness argument: this book's `listing` source has had ZERO crypto supply
# for 86 days (last crypto birth CTR/RAIL 25-May) and its `young` source has
# been EMPTY for 66 days (0 admissible today: the venue files memecoin debuts
# under strategy_index 7, which the (lk) crypto screen excludes, and the class-2
# birth rate is 0.00/30d). Both were dead the whole time behind an `extra`
# payload that published `watching: 212` and nothing per source — so
# `opened: 0` was byte-identical between "quiet" and "structurally impossible",
# the exact condition that hid 🎸 Barnesy's `extreme` sleeve for 8 days.
#
# The funnel is filled BY THE ADMISSION FUNCTIONS THEMSELVES, one counter per
# gate stage, so it cannot drift from the gate the way a re-implemented census
# would ((hj): a second copy of a rule is a second rule). Publish-only: no
# counter is read by any decision in this file, and admission is byte-identical
# with `census=None`.
def _new_funnel(census, stages):
    """Zero a per-source funnel dict in `census` (or a throwaway) and return it.

    `stages` are the gate stages in the order the admission function applies
    them; every stage counts the candidates that REACHED it and passed. So a
    source dies at the first stage whose count is 0, and the reader can name
    which gate killed it without reading this file.
    """
    cen = census if census is not None else {}
    for k in stages:
        cen[k] = 0
    cen["admitted"] = 0
    cen["capped"] = False
    return cen


def surge_candidates(surges, mult, already, limit=SURGE_MAX_PER_LOOP,
                     class_ok=None, census=None):
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
    class_ok = _class_ok if class_ok is None else class_ok
    cen = _new_funnel(census, ("offered", "parsed", "ratio_ok", "fresh",
                              "class_ok"))
    try:
        rows = sorted(surges or [],
                      key=lambda r: -float(r.get("ratio") or 0.0))
    except (TypeError, ValueError, AttributeError):
        return out
    cen["offered"] = len(rows)
    for r in rows:
        try:
            sym = str(r.get("sym") or "").strip().upper()
            ratio = float(r.get("ratio") or 0.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if not sym:
            continue
        cen["parsed"] += 1
        # The admission predicate below is the SAME test as the original
        # single-expression `if`, split one stage per line so the census
        # counts the real gate rather than a second copy of it ((hj)).
        if ratio < float(mult):
            continue
        cen["ratio_ok"] += 1
        if sym in already:
            continue
        cen["fresh"] += 1
        if not class_ok(sym):             # [(lk)] crypto perps only
            continue
        cen["class_ok"] += 1
        # Cap the ADMISSION, never the count: the loop runs to the end so a
        # capped pass still reports how much supply it turned away. Rows are
        # ratio-sorted, so the first `limit` survivors are exactly the ones
        # the pre-census `break` admitted.
        if len(out) >= int(limit):
            cen["capped"] = True
            continue
        out.append(sym)
    cen["admitted"] = len(out)
    return out


# ---------------------------------------------------------------------------
# [2026-08-16 (nn)] THE (ne) SURGE-ADMISSION TELEMETRY, LIFTED OUT OF main().
#
# `(ne)` added these three pieces of logic INLINE in main(), where no test can
# reach them — 13 statements that went straight to uncovered and took this
# file from a measured 83.5% to 80.8%, breaching its 81% floor and leaving the
# Tests workflow red on every push for 24 hours and nine consecutive runs
# ([(nq)] corrected in place: this comment and `(nn)`'s title both said "four
# days". Last green `15acd05` 15-Aug 01:15:29Z, first red `71b7f4f` 15-Aug
# 01:28:37Z, green again `65e1ae4` 16-Aug 01:32:19Z. The run COUNT was right;
# the duration was 4× over). Every sibling rule in this
# file is already module-level and pure for exactly this reason
# (`surge_candidates`, `young_candidates`, `active_done`, `close_reason`);
# these three are moved back to that convention, behaviour unchanged.
#
# The contract they share, and the reason they all swallow rather than raise:
# this is TELEMETRY on a shadow book. A junk row must degrade the close to NO
# extra — never to a guessed number — because a fabricated ratio would be
# indistinguishable from a measured one in the X4 expectancy split these
# fields exist to feed.
# ---------------------------------------------------------------------------
def surge_ratio_map(surges):
    """{SYM: ratio} from the scout's `vol_surges` rows.

    The ratio each surge candidate carried AT ADMISSION. Keyed like the
    source map (stripped, upper-cased); unparseable rows are dropped
    individually, so one bad row cannot cost the whole map.
    """
    out = {}
    for r in (surges or []):
        try:
            out[str(r.get("sym") or "").strip().upper()] = float(r.get("ratio"))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def surge_admission(sym, ratios, mult):
    """The `{surge_ratio, surge_mult}` a SURGE admission records, or None.

    None when the ratio is unknown — `float(None)` is the guard, not an
    accident: a surge admitted while the scout's row is missing records
    NOTHING rather than a zero that would read as a measured ratio.
    """
    try:
        return {"surge_ratio": float((ratios or {}).get(sym)),
                "surge_mult": float(mult)}
    except (TypeError, ValueError):
        return None


def restore_entry_meta(saved_meta):
    """Rehydrate the surge admission telemetry across a restart.

    Durable like `entry_src`, and junk is dropped the same way: a half-written
    or hand-edited entry degrades that coin's close to no extra. A missing
    entry is correct — it is a pre-(ne) open.
    """
    out = {}
    for k, m in (saved_meta or {}).items():
        try:
            out[str(k)] = {"surge_ratio": float(m["surge_ratio"]),
                           "surge_mult": float(m["surge_mult"])}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def young_candidates(bar_counts, max_bars, vols, min_vol_m, already, limit,
                     class_ok=None, census=None):
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
    # [(sl)] the YOUNG screen, not the surge one — `_young_class_ok` asks
    # "is this priced on this venue", which admits the class-7 memecoin debuts
    # `is_crypto` refuses. An explicit `class_ok=` still overrides, which is
    # what the tests drive.
    class_ok = _young_class_ok if class_ok is None else class_ok
    cen = _new_funnel(census, ("scanned", "age_ok", "fresh", "class_ok",
                               "vol_ok"))
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
        if not s:
            continue
        cen["scanned"] += 1
        # Same admission test as the original combined `if`, one stage per
        # line so the funnel counts the real gate ((hj)). Age first, then
        # dedup: the ORDER decides only which bucket a doubly-refused symbol
        # lands in, never whether it is admitted.
        if bars > int(max_bars):
            continue
        cen["age_ok"] += 1
        if s in (already or set()):
            continue
        cen["fresh"] += 1
        if not class_ok(s):               # [(sl)] priced on THIS venue
            continue
        cen["class_ok"] += 1
        try:
            vol = float((vols or {}).get(s, 0.0) or 0.0)
        except (TypeError, ValueError):
            vol = 0.0
        if vol < float(min_vol_m):
            continue
        cen["vol_ok"] += 1
        rows.append((bars, -vol, s))
    rows.sort()
    out = [s for _, _, s in rows[:int(limit)]]
    cen["admitted"] = len(out)
    cen["capped"] = len(rows) > len(out)
    return out


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

    [2026-08-16 (nv)] AND `is_held` CANNOT SEE THIS PASS'S OWN OPENS — it is a
    snapshot taken before the loop, so the latch above covers a position from a
    PREVIOUS pass and nothing covered a symbol appearing TWICE in `candidates`.
    That is reachable, not theoretical: `candidates` is
    `new_listings + _surge + _young`, and the listing list is the only one not
    deduped against `surge_done`, so a brand-new book that is also surging
    arrives twice. Measured through `main()` before the fix: TWO `market_open`
    calls on one coin in one pass (funded: two clips against one entry_ts;
    shadow: `PaperBroker.open` re-opens a held symbol and realises P&L with no
    `record_close` — a trade that never reaches the ledger, on a book whose
    only product is its ledger). `_src_map`'s `setdefault` shows the overlap
    was anticipated for the TAG and forgotten for the ORDER. First occurrence
    wins here too, so the two agree by construction.

    Returns (open_now, sniped, abandoned).
    """
    sniped, abandoned, seen = [], [], set()
    for sym in candidates:
        if sym in seen:
            continue          # [(nv)] one attempt per symbol per pass
        seen.add(sym)
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
    # [2026-08-15 (ne)] admission-time SURGE telemetry: {sym: {"surge_ratio",
    # "surge_mult"}}. The X4 audit found the surge bucket's expectancy
    # question UNMEASURABLE because the ledger stamps the source but not the
    # ratio or the mult-in-force at entry — so "does the board's widened
    # population (mult<3.0 admits) differ?" had no data. Durable like
    # entry_src; forward-only; a missing entry is a pre-(ne) open.
    entry_meta = {}
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
        # [(ne)] restore the surge admission telemetry; junk values dropped
        # (the close degrades to no extra, never a guessed number).
        # [(nn)] the rule itself now lives at module level, where a test can
        # reach it — see restore_entry_meta.
        entry_meta = restore_entry_meta(_saved.get("entry_meta"))
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
            # [2026-08-05 (kf)] `was_long` is used two lines above to sign
            # pnl_pct and was then dropped — the (gr) shape, one field over.
            # A side-less row used to replay as a LONG in study_exit_sweep,
            # inverting every short.
            side=("long" if was_long else "short"),
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
            # [(ne)] surge admission telemetry (ratio + mult in force at
            # entry) — the two numbers the X4 expectancy split needed; empty
            # for non-surge and pre-(ne) opens. Pop: one close consumes it.
            extra=(entry_meta.pop(coin, None) or None),
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
            # [(ne)] surge admissions record the ratio + the mult in force —
            # the two numbers X4 needed and the ledger never had. [(nn)] the
            # rule is module-level now; None means "ratio unknown", and an
            # unknown ratio records NOTHING rather than a guessed number.
            if src == "surge":
                _meta = surge_admission(sym, _surge_ratios, SURGE_MULT)
                if _meta is not None:
                    entry_meta[sym] = _meta
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
                                      "entry_meta": entry_meta,
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
        # [(sk)] the listing funnel. Deliberately SHORTER than the other two —
        # this source has no class screen and no volume floor ((lk) left it
        # open on purpose), so `offered` and `fresh` ARE its whole gate, and
        # publishing stages it does not have would overstate the filtering.
        # `scan: "fresh"` unconditionally: unlike surge/young this source reads
        # the venue market list this loop already fetched, not the scout, so it
        # cannot be dark without the loop having already restarted above.
        _listing_cen = {"scan": "fresh", "offered": len(new_listings),
                        "fresh": len(fresh), "pending": len(pending),
                        "admitted": len(fresh), "capped": False}
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
        _surge_ratios = {}      # [(ne)] always bound, even on a dark scout
        # [(sk)] the census STARTS at its liveness verdict, before any count,
        # so a dark or stale scout publishes `scan: "dark"/"stale"` instead of
        # an all-zero funnel that reads exactly like a live scan finding
        # nothing (I1 — liveness before semantics).
        _surge_cen = {"scan": "off" if SURGE_MULT <= 0 else "dark"}
        if SURGE_MULT > 0 and fleet_bus is not None:
            try:
                _sp = fleet_bus._load("lighter-market", None) or {}
                if fleet_bus.is_fresh(_sp, None):
                    _surge_cen["scan"] = "fresh"
                    _live_done = active_done(surge_done, now.timestamp())
                    _surge = surge_candidates(_sp.get("vol_surges"), SURGE_MULT,
                                              _live_done | set(pending),
                                              census=_surge_cen)
                    # [(ne)] the ratio each surge candidate carried at
                    # admission — telemetry for the close, keyed like
                    # _src_map. [(nn)] module-level: see surge_ratio_map.
                    _surge_ratios = surge_ratio_map(_sp.get("vol_surges"))
                else:
                    _surge_cen["scan"] = "stale"
            except Exception:  # noqa: BLE001
                _surge = []
                _surge_cen["scan"] = "error"
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
        _young_cen = {"scan": "off" if YOUNG_MAX_BARS <= 0 else "dark"}
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
            # [(sk)] WHICH age source answered is part of the census: the
            # scout's exact `ages_d` and the 4/loop candle-probe cache are
            # different instruments, and a funnel read off the fallback means
            # something weaker than one read off the venue's own created_at.
            _young_cen["scan"] = "fresh" if _ages else (
                "probe" if bar_counts else "dark")
            _young = young_candidates(_age_src, YOUNG_MAX_BARS, _vols,
                                      YOUNG_MIN_VOL_M,
                                      active_done(surge_done, now.timestamp())
                                      | set(pending), YOUNG_MAX_PER_LOOP,
                                      census=_young_cen)
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
                                 # [2026-08-20 (sk)] THE PER-SOURCE CENSUS —
                                 # see _new_funnel(). `watching`/`pending`
                                 # above are book-wide, so until now nothing
                                 # in this payload could say WHICH of the
                                 # three sources supplied a pass, or why one
                                 # supplied nothing. Two of them had supplied
                                 # nothing for 86 and 66 days respectively and
                                 # the row looked identical throughout. Read
                                 # `scan` FIRST (I1), then the first stage
                                 # whose count is 0 — that is the gate that
                                 # killed the source. Publish-only.
                                 "sources": {"listing": _listing_cen,
                                             "surge": _surge_cen,
                                             "young": _young_cen},
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
                                          "max_open": MAX_OPEN,
                                          # [2026-08-17 (pk)] THE CLASS AXIS
                                          # ON A BOOK WHOSE SCREEN IS PARTIAL.
                                          # `(pf)` gave the three books with a
                                          # WHOLE-gate screen a `crypto_only`
                                          # and DECLARED this one exempt,
                                          # because `true` would misdescribe a
                                          # gate the listing source leaves
                                          # open. Correct — and it concluded
                                          # "publish nothing" when `false` was
                                          # available and TRUE. This book's
                                          # gate as a whole DOES admit
                                          # non-crypto, so `false` is the
                                          # honest whole-gate answer, and an
                                          # absent field under-informs exactly
                                          # as a wrong `true` would overstate
                                          # — the argument `(pj)` makes for
                                          # the Farmer/Garrett rows.
                                          # NOT a claim about a consumer:
                                          # `audit_book_overlap` reads this
                                          # field, but its population is
                                          # `FUNDING_BOOKS` and this is a
                                          # DIRECTIONAL book, so nothing
                                          # automated consumes it today. It is
                                          # published in the fleet's standard
                                          # shape so the grade is READABLE —
                                          # which was `(pf)`'s whole defect.
                                          #
                                          # WHY THE LITERAL IS SAFE HERE, and
                                          # it is the opposite reason to the
                                          # usual one: `false` does not track
                                          # ALLOW_NONCRYPTO because it CANNOT
                                          # drift with it. Flipping the
                                          # reversal env only widens what
                                          # surge/young admit; the listing
                                          # source is unscreened either way,
                                          # so the whole-gate answer is
                                          # `false` in both states.
                                          "crypto_only": False,
                                          # ...and the detail the bool cannot
                                          # carry, which is the half that made
                                          # this book's grade unreadable: 18 of
                                          # the 20 closes behind its 10-day
                                          # `unreachable` verdict are the class
                                          # surge/young stopped admitting on
                                          # 13-Aug (−$5.34 against +$0.46 on
                                          # the 2 crypto closes). Per SOURCE,
                                          # derived from the switch so it
                                          # tracks a reversal:
                                          "class_screen": {
                                              "surge": not ALLOW_NONCRYPTO,
                                              "young": not (ALLOW_NONCRYPTO
                                                            or YOUNG_ALLOW_ANY),
                                              # structural, not a default —
                                              # see the (lk) block: n=1,
                                              # unmeasured, founding thesis.
                                              "listing": False},
                                          # [(sl)] WHICH QUESTION each screen
                                          # asks. `surge: is_crypto` and
                                          # `young: venue_priced` are DIFFERENT
                                          # gates and a payload saying only
                                          # "screened: true" for both cannot
                                          # tell them apart — which is how a
                                          # screen justified on n=2 sat on the
                                          # wrong axis for 66 days. Publishing
                                          # the axis makes the next reader able
                                          # to ask the question this book could
                                          # not be asked.
                                          "young_axis": (
                                              "any" if (ALLOW_NONCRYPTO
                                                        or YOUNG_ALLOW_ANY)
                                              else "venue_priced"),
                                          "surge_axis": (
                                              "any" if ALLOW_NONCRYPTO
                                              else "is_crypto")}})
        except Exception as e:  # noqa: BLE001
            # Never let telemetry kill the trading loop — but never let it fail
            # in silence either: a bare `except: pass` here is what hid the
            # funded-mode AttributeError above indefinitely.
            log.warning("publish failed (row will go stale): %s", e)
        # [2026-08-15 (my)] I9 MTM series. The MTM_PENDING exemption ("n=5,
        # nowhere near the closes bar") aged out: the book reads n=29 and sits
        # on the decision docket — a keep-or-retire verdict should see the
        # same drawdown definition the gate uses, not realised-only.
        try:
            store.snapshot_equity(bot_id, pub_equity, pub_open)
        except Exception:  # noqa: BLE001
            pass
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
                                  "entry_meta": entry_meta,
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

    # `None` is a LEGITIMATE fleet_bus (the import guard sets it), so the
    # "leave the global alone" default needs a sentinel, not None.
    _UNSET = object()

    def _drive(venue, cap, clip, saved, broker=None, mode="lighter_live",
               bus=_UNSET):
        """Run ONE --once loop of main() against a fake venue; return the store.

        `bus` swaps the module-global `fleet_bus` for the duration — the scout
        is how the SURGE and YOUNG sources get their population, and with the
        real module in place a selftest has no DB and reads nothing, so those
        two of the three admission sources never execute at all. Left UNSET
        the global is untouched, which is what every fixture above wants.
        """
        g, fs = globals(), _FakeStore(saved)
        keep = (g["venue_context"], g["store"], sys.argv,
                os.environ.get("DATABASE_URL"), g["fleet_bus"])
        try:
            g["venue_context"] = lambda **kw: _FakeCtx(venue, _FakeRails(cap), clip,
                                                       broker=broker, mode=mode)
            g["store"] = fs
            if bus is not _UNSET:
                g["fleet_bus"] = bus
            sys.argv = ["lighter_perp_sniper.py", "--once"]
            os.environ["DATABASE_URL"] = "postgres://selftest-not-dialled"
            main()
        finally:
            g["venue_context"], g["store"], sys.argv = keep[0], keep[1], keep[2]
            g["fleet_bus"] = keep[4]
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

    # ---- [2026-08-16 (np)] THE SURGE ADMISSION TELEMETRY, END TO END — the
    # WIRING half of the (nn) fix, which pinned the RULES.
    # `(nn)` lifted (ne)'s three inline rules to module level (surge_ratio_map,
    # surge_admission, restore_entry_meta) and unit-tested them there, which is
    # what took this file back over its floor. What no unit test can see is
    # whether main() still CALLS them, and whether the value a call returns
    # survives the trip it exists to make: admission -> saved state -> restart
    # -> ledger row. Delete every call site and (nn)'s tests stay green, its
    # coverage stays where it is, and the X4 split silently gets nothing.
    #
    # Reaching that meant fixing something older and larger than (ne): the
    # SURGE and YOUNG sources both read the scout, and `_drive` left the real
    # `fleet_bus` in place, where a selftest has no DB — `_load` returns
    # nothing, `is_fresh` is False. So **two of this book's three admission
    # sources had never executed in any fixture this file has ever had**; the
    # listing path was the only one any of them drove. That is why (ne)'s code
    # could land in a hole: the hole predates it. `bus=` opens it.
    class _FakeBus:
        """The scout's payload, as `lighter_market_scout` publishes it."""

        def __init__(self, payload):
            self._p = payload

        def _load(self, key, _default=None):
            return dict(self._p) if key == "lighter-market" else _default

        def is_fresh(self, payload, _ttl=None):
            return bool(payload)

        def is_crypto(self, sym):        # [(lk)] the surge source is crypto-only
            return str(sym).upper() != "SPXUSD"

    # QUIET carries `ratio: None`. It is not a decoration, and it is the one
    # property a unit test on `surge_ratio_map` CANNOT state: `surge_candidates`
    # reads that field as `float(r.get("ratio") or 0.0)` (-> 0.0, simply not a
    # candidate) while `surge_ratio_map` reads it as `float(r.get("ratio"))`
    # (-> TypeError). Two consumers, one field, two readings — and in main()
    # they sit inside ONE `try`, so a raise the map did not swallow lands in
    # `except Exception: _surge = []` and **one malformed row silences the
    # whole surge source for that loop**. In isolation the map just returns a
    # short dict and nothing is wrong. The assertion that pins it can therefore
    # only be made from here, and it is not about the map at all: SRG is still
    # sniped. SPXUSD pins the (lk) class screen in the same pass.
    _bus = _FakeBus({
        "vol_surges": [{"sym": "srg", "ratio": 5.0},      # lower-case: normalised
                       {"sym": "SPXUSD", "ratio": 9.0},   # non-crypto: screened
                       {"sym": "QUIET", "ratio": None}],  # unparseable ratio
        "vols": {"OLD": 50.0, "SRG": 50.0},
        # every active book has a known age, so no young candidate is admitted
        # and no candle probe is fired — this fixture is about the surge source.
        "ages_d": {"OLD": 500.0, "SRG": 500.0},
    })
    _srg_books = dict(_books, SRG={"bids": [[10.0, 10]], "asks": [[10.2, 10]]})
    _srg_markets = {s: {"status": "active"} for s in ("OLD", "SRG")}
    ven7 = _FakeVenue(_srg_markets, _srg_books, {})
    fs7 = _drive(ven7, 1000.0, CLIP,
                 {"baseline": ["OLD", "SRG"], "entry_ts": {}, "pending": {}},
                 bus=_bus)
    assert [o[0] for o in ven7.opened] == ["SRG"], (
        f"the surge source admitted nothing: {ven7.opened} — a raise inside the "
        "ratio map escapes to the source's own except and empties _surge")
    _blob7 = fs7.saves[-1][1]
    assert _blob7["entry_src"]["SRG"] == "surge", _blob7["entry_src"]
    assert _blob7["entry_meta"]["SRG"] == {"surge_ratio": 5.0,
                                           "surge_mult": SURGE_MULT}, \
        f"the admission telemetry was not recorded: {_blob7.get('entry_meta')}"
    assert "SPXUSD" not in _blob7["entry_src"], "the class screen let SPXUSD in"
    assert "QUIET" not in _blob7["entry_meta"], _blob7["entry_meta"]

    # ...and the record SURVIVES A RESTART and reaches the LEDGER ROW — the
    # whole point of a durable map, and the leg with three call sites between
    # its ends (`restore_entry_meta` at boot, both `save_state` blobs, the pop
    # in `record_close`). `entry_src` gained the same lifecycle in (ha)/(jk).
    # Junk restores to NOTHING: the close degrades to no extra, never to a
    # guessed number (ht) — asserted here on the ROW, not on the rule.
    ven8 = _FakeVenue({s: {"status": "active"} for s in ("OLD", "SRG")},
                      dict(_books, SRG={"bids": [[46.0, 5]], "asks": [[46.2, 5]]}),
                      {"SRG": {"size": 1.0, "entry": 40.0}})
    fs8 = _drive(ven8, CAP, CLIP,
                 {"baseline": ["OLD", "SRG"], "entry_ts": {}, "pending": {},
                  "entry_src": {"SRG": "surge", "BAD": "surge"},
                  "entry_meta": {"SRG": {"surge_ratio": 5.0, "surge_mult": 3.0},
                                 "BAD": {"surge_ratio": "not-a-number",
                                         "surge_mult": 3.0},
                                 "GONE": {"surge_mult": 3.0}}})
    assert ven8.closed == ["SRG"], ven8.closed
    _bot8, tr8 = fs8.trades[-1]
    assert tr8["reason"] == "long-surge_tp", tr8["reason"]
    assert tr8["extra"] == {"surge_ratio": 5.0, "surge_mult": 3.0}, (
        f"the restored admission telemetry never reached the ledger: {tr8}")
    _meta8 = fs8.saves[-1][1]["entry_meta"]
    assert "SRG" not in _meta8, "the close must CONSUME the record (pop), not keep it"
    assert "BAD" not in _meta8 and "GONE" not in _meta8, (
        f"junk restored as a number — the (ht) degrade rule: {_meta8}")

    # ---- [(np)] AND THE TWO `save_state` WRITERS MUST AGREE ON SHAPE.
    # `(ha)` asserts that they do — in a COMMENT, at both of them ("same shape
    # at BOTH writers") — and nothing tested it. The SEED writer fires only on
    # a first-ever run (`if not baseline`), which no fixture had ever driven,
    # so a key added to the steady-state blob and forgotten at the seed one is
    # invisible until a first-boot container restores a blob missing it.
    # Found by mutation, not by reading: dropping `entry_meta` from the seed
    # writer alone SURVIVED every other assertion in this block. Comparing the
    # KEY SETS closes the class rather than this instance — the next field
    # added at one writer and not the other trips here.
    ven10 = _FakeVenue(_srg_markets, _srg_books, {})
    fs10 = _drive(ven10, 1000.0, CLIP,
                  {"baseline": [], "entry_ts": {}, "pending": {}}, bus=_bus)
    _seed_blob = fs10.saves[-1][1]
    assert sorted(_seed_blob) == sorted(_blob7), (
        "the two save_state writers disagree on shape — (ha) requires the seed "
        f"blob and the steady-state blob to carry the same keys:\n"
        f"  seed only: {sorted(set(_seed_blob) - set(_blob7))}\n"
        f"  steady only: {sorted(set(_blob7) - set(_seed_blob))}")
    assert ven10.opened == [], "the seed run must never buy the venue"

    # A non-surge close carries NO extra — `entry_meta` is empty for the other
    # two sources, and `or None` must keep an empty dict out of the row.
    ven9 = _FakeVenue(_tp_markets, _tp_books, {"T1": {"size": 1.0, "entry": 40.0}})
    fs9 = _drive(ven9, CAP, CLIP, {"baseline": ["OLD", "T1"], "entry_ts": {},
                                   "pending": {}, "entry_meta": {}})
    assert fs9.trades[-1][1]["extra"] is None, fs9.trades[-1][1]["extra"]

    # ---- [2026-08-16 (nr)] THE YOUNG SOURCE — the third and last admission
    # route, and the one `(np)` left behind. Same finding, same shape: `(ga)`
    # added it in July precisely BECAUSE the listing trigger was unobservable
    # (a market-set diff qualifies a symbol for exactly one loop, and only if
    # the process is running with a warm baseline at that instant), so this is
    # the source carrying the population the book is supposed to be graded on
    # — and it had never executed in a fixture in its life. `young_candidates`
    # is unit-tested as a RULE; what follows is everything between the rule and
    # a position: the scout read, the probe fallback, the dedup ledger, the
    # source stamp on the close.
    #
    # It has a second half the surge source does not: a CANDLE PROBE, which is
    # I/O the bot pays for per loop and is governed by two properties stated in
    # the comment above it and asserted nowhere — BUDGETED (at most
    # YOUNG_PROBE_BUDGET unknown symbols per loop) and MONOTONE (a book
    # measured older than the bar goes into `not_young` FOREVER, because books
    # only age). "The probe cost decays to zero once the venue has been walked"
    # is a claim about a REST bill, and until now nothing checked that a second
    # loop re-probes nothing.
    class _ProbeVenue(_FakeVenue):
        """A venue that answers the daily-candle probe, and remembers who asked."""

        def __init__(self, markets, books, positions, bars):
            _FakeVenue.__init__(self, markets, books, positions)
            self._bars, self.probed = bars, []

        def candles(self, sym, _interval, _start_ms, _end_ms):
            self.probed.append(sym)
            return [None] * int(self._bars.get(sym, 0))

    # (1) THE SCOUT-FED PATH — `ages_d` is the preferred age source (exact,
    # whole-venue, zero extra REST), so a payload carrying it must admit the
    # young book AND fire no probe at all.
    _young_bus = _FakeBus({
        "vol_surges": [],
        "vols": {"OLD": 50.0, "NEWB": 3.0},
        "ages_d": {"OLD": 500.0, "NEWB": 5.0},   # NEWB is 5 days old: young
    })
    _young_books = dict(_books, NEWB={"bids": [[2.0, 50]], "asks": [[2.02, 50]]})
    _young_markets = {s: {"status": "active"} for s in ("OLD", "NEWB")}
    ven11 = _ProbeVenue(_young_markets, _young_books, {}, {"NEWB": 5})
    fs11 = _drive(ven11, 1000.0, CLIP,
                  {"baseline": ["OLD", "NEWB"], "entry_ts": {}, "pending": {}},
                  bus=_young_bus)
    assert [o[0] for o in ven11.opened] == ["NEWB"], (
        f"the young source admitted nothing: {ven11.opened}")
    assert ven11.probed == [], (
        f"the scout gave every age and the probe still ran on {ven11.probed} — "
        "the REST bill this fallback is supposed to avoid")
    _blob11 = fs11.saves[-1][1]
    assert _blob11["entry_src"]["NEWB"] == "young", _blob11["entry_src"]
    # the young source shares the SURGE cooldown ledger deliberately (a young
    # book is in `baseline`, so baseline cannot dedup it) — without this the
    # book re-enters `pending` every loop forever.
    assert "NEWB" in _blob11["surge_done"], _blob11["surge_done"]
    # ...and it carries NO surge telemetry. `entry_meta` is surge-ONLY; a
    # stamp that fired for every source would put a mult on a book no mult
    # admitted, and the X4 split would read it as a measured surge.
    assert "NEWB" not in (_blob11.get("entry_meta") or {}), _blob11["entry_meta"]

    # (2) THE PROBE FALLBACK — a scout with no `ages_d` (the dark/stale case
    # the probe exists for). Both branches of the bar test in one pass, and
    # the two durable maps they write.
    _probe_bus = _FakeBus({"vol_surges": [], "vols": {"PROBED": 3.0, "OLDBK": 90.0}})
    _probe_books = dict(_books,
                        PROBED={"bids": [[2.0, 50]], "asks": [[2.02, 50]]},
                        OLDBK={"bids": [[9.0, 50]], "asks": [[9.05, 50]]})
    _probe_markets = {s: {"status": "active"} for s in ("PROBED", "OLDBK")}
    ven12 = _ProbeVenue(_probe_markets, _probe_books, {},
                        {"PROBED": 5, "OLDBK": 400})
    fs12 = _drive(ven12, 1000.0, CLIP,
                  {"baseline": ["PROBED", "OLDBK"], "entry_ts": {}, "pending": {}},
                  bus=_probe_bus)
    assert sorted(ven12.probed) == ["OLDBK", "PROBED"], ven12.probed
    _blob12 = fs12.saves[-1][1]
    assert _blob12["bar_counts"].get("PROBED") == 5, _blob12["bar_counts"]
    assert "OLDBK" in _blob12["not_young"], _blob12["not_young"]
    assert "PROBED" not in _blob12["not_young"], _blob12["not_young"]
    assert [o[0] for o in ven12.opened] == ["PROBED"], (
        f"the probe cache is the fallback age source and admitted nothing: "
        f"{ven12.opened}")
    assert _blob12["entry_src"]["PROBED"] == "young", _blob12["entry_src"]

    # ...and MONOTONE: replay the same loop with the maps the first one wrote
    # and NOTHING is re-probed. This is the property that makes the probe's
    # cost decay to zero, and a `not_young` that reset (or was dropped from
    # either save writer) would re-probe the whole venue every loop forever —
    # the (ha) zombie-clock defect's exact shape, on the REST bill.
    ven13 = _ProbeVenue(_probe_markets, _probe_books, {},
                        {"PROBED": 5, "OLDBK": 400})
    _drive(ven13, 1000.0, CLIP,
           {"baseline": ["PROBED", "OLDBK"], "entry_ts": {}, "pending": {},
            "bar_counts": _blob12["bar_counts"],
            "not_young": _blob12["not_young"],
            "surge_done": _blob12["surge_done"]},
           bus=_probe_bus)
    assert ven13.probed == [], (
        f"a second loop re-probed {ven13.probed} — the probe is not monotone, "
        "so its cost never decays")

    # (3) THE SOURCE STAMP REACHES THE LEDGER, and only the young half of it.
    ven14 = _ProbeVenue(_young_markets,
                        dict(_young_books,
                             NEWB={"bids": [[2.4, 50]], "asks": [[2.42, 50]]}),
                        {"NEWB": {"size": 10.0, "entry": 2.0}}, {})
    fs14 = _drive(ven14, CAP, CLIP,
                  {"baseline": ["OLD", "NEWB"], "entry_ts": {}, "pending": {},
                   "entry_src": {"NEWB": "young"},
                   "not_young": ["OLD"]})
    assert ven14.closed == ["NEWB"], ven14.closed
    _tr14 = fs14.trades[-1][1]
    assert _tr14["reason"] == "long-young_tp", _tr14["reason"]
    assert _tr14["extra"] is None, (
        f"a YOUNG close carried surge telemetry: {_tr14['extra']}")

    # (4) A BUS THAT RAISES admits nothing and stops nothing — both scout reads
    # in this block are wrapped, and the fail-safe contract is that a dark or
    # broken organ costs the book its widened population, never its loop.
    class _BoomBus:
        def _load(self, *_a, **_k):
            raise RuntimeError("bot_state read failed")

        def is_fresh(self, *_a, **_k):
            return True

        def is_crypto(self, _sym):
            return True

    ven15 = _ProbeVenue(_young_markets, _young_books, {}, {"NEWB": 5})
    fs15 = _drive(ven15, 1000.0, CLIP,
                  {"baseline": ["OLD", "NEWB"], "entry_ts": {}, "pending": {}},
                  bus=_BoomBus())
    assert ven15.opened == [], "a dark scout must admit no young/surge book"
    assert fs15.saves and fs15.published, \
        "a raising bus stopped the loop — the fail-safe contract is degrade, not halt"

    # ---- [2026-08-16 (nv)] THE LISTING SOURCE — the third of three, and the
    # only one that was ALREADY driven end to end (every `_drive` fixture above
    # snipes `NEW` off the market-set diff). So this block is not "reach the
    # source"; it is the RULES the listing source owns and nobody asserted.
    # Measured before writing any of it, by mutating each rule and running the
    # suite: three of the four survived everything the repo had.
    #
    # The fourth is worth naming as a shape, not just a result. "Listing wins a
    # tie" WAS defended — by `'"listing"' in block and "setdefault" in block`
    # over a 400-character window of the SOURCE TEXT. That catches deleting the
    # literal and nothing else: rewriting the surge line to
    # `_src_map[_s] = "surge"` inverts the priority while leaving the word
    # `setdefault` sitting in the young line two rows down, so the test stays
    # green on a mutation that changes which bucket every dual-source close
    # lands in. The memory rule is the general form — a substring test is not a
    # wiring test — and the fix is to assert the STAMP on a close, below.

    # (1) THE CLOSE TAG, through the bot's OWN saved blob rather than a
    # hand-written one ((hj)): pass 1 snipes the listing, pass 2 is handed
    # exactly what pass 1 persisted and must produce `long-listing_tp`.
    _li_books = dict(_books, LIST1={"bids": [[4.0, 50]], "asks": [[4.04, 50]]})
    _li_markets = {s: {"status": "active"} for s in ("OLD", "LIST1")}
    ven16 = _FakeVenue(_li_markets, _li_books, {})
    fs16 = _drive(ven16, 1000.0, CLIP,
                  {"baseline": ["OLD"], "entry_ts": {}, "pending": {}})
    assert [o[0] for o in ven16.opened] == ["LIST1"], ven16.opened
    _blob16 = fs16.saves[-1][1]
    assert _blob16["entry_src"]["LIST1"] == "listing", _blob16["entry_src"]
    ven17 = _FakeVenue(_li_markets,
                       dict(_li_books, LIST1={"bids": [[4.8, 50]], "asks": [[4.84, 50]]}),
                       {"LIST1": {"size": 3.0, "entry": 4.02}})
    fs17 = _drive(ven17, CAP, CLIP, _blob16)
    assert ven17.closed == ["LIST1"], ven17.closed
    assert fs17.trades[-1][1]["reason"] == "long-listing_tp", \
        fs17.trades[-1][1]["reason"]

    # (2) THE TIE, AND THE DOUBLE-OPEN IT WAS HIDING. A brand-new book that is
    # ALSO surging is in `new_listings` AND `_surge`: the listing list is the
    # only one not deduped against `surge_done`, so the symbol arrives in
    # `candidates` twice. Measured through main() before (nv): TWO market_open
    # calls on one coin in one pass, one entry_ts, and a row reporting `1 open`
    # — the venue keys positions by symbol, so the second clip is invisible in
    # the book's own report. In shadow the second open re-enters a held symbol,
    # which realises P&L with NO record_close: a trade that never reaches the
    # ledger, on a book whose only product is its ledger.
    _dual_bus = _FakeBus({"vol_surges": [{"sym": "DUAL", "ratio": 9.0}],
                          "vols": {"OLD": 50.0, "DUAL": 50.0},
                          "ages_d": {"OLD": 900.0, "DUAL": 900.0}})
    _dual_books = dict(_books, DUAL={"bids": [[5.0, 50]], "asks": [[5.05, 50]]})
    ven18 = _FakeVenue({s: {"status": "active"} for s in ("OLD", "DUAL")},
                       _dual_books, {})
    fs18 = _drive(ven18, 1000.0, CLIP,
                  {"baseline": ["OLD"], "entry_ts": {}, "pending": {}},
                  bus=_dual_bus)
    assert [o[0] for o in ven18.opened] == ["DUAL"], (
        f"a dual-source symbol was sniped {len(ven18.opened)}x in one pass: "
        f"{ven18.opened} — is_held is a pre-pass snapshot and cannot see it")
    assert fs18.saves[-1][1]["entry_src"]["DUAL"] == "listing", (
        "listing must win the tie — it is tried first, so it is the source "
        "that actually admitted the symbol: "
        f"{fs18.saves[-1][1]['entry_src']}")
    # ...and the ORDER and the TAG must agree by construction, which is the
    # whole reason the dedup keeps the FIRST occurrence.
    _o, _s2, _a = run_snipe_pass(candidates=["D", "D", "E"], pending={},
                                 baseline=set(), now_ts=t0, open_now=0,
                                 max_open=9, try_snipe=always)
    assert _s2 == ["D", "E"] and _o == 2, (_s2, _o)

    # (3) A LISTING THAT FLAPS OUT OF `active`. A fresh perp's status flickers
    # around its debut, and the rule has two halves that pull opposite ways:
    # INSIDE the give-up window the pending record is KEPT (popping it would
    # reset first_seen/attempts on the symbol's return, so a flapping book
    # would never reach the bound and could be sniped days late), and past the
    # bound it is dropped from pending but NEVER folded into `baseline` — an
    # inactive market that re-lists later is a genuinely new listing, which is
    # the 17-Jul absorption bug the whole retry design exists to prevent.
    _now = time.time()
    _flap = _drive(_FakeVenue(_li_markets, _li_books, {}), CAP, CLIP,
                   {"baseline": ["OLD", "LIST1"], "entry_ts": {},
                    "pending": {"YOUNGFLAP": {"first_seen": _now - 60,
                                              "attempts": 7},
                                "OLDFLAP": {"first_seen": _now
                                            - PENDING_MAX_AGE_SEC - 60,
                                            "attempts": 9}}})
    _pend, _base = _flap.saves[-1][1]["pending"], _flap.saves[-1][1]["baseline"]
    assert _pend.get("YOUNGFLAP", {}).get("attempts") == 7, (
        f"a flapping listing lost its retry clock inside the window: {_pend}")
    assert "OLDFLAP" not in _pend, f"past the bound it must be dropped: {_pend}"
    assert "OLDFLAP" not in _base and "YOUNGFLAP" not in _base, (
        f"an inactive market was folded into the baseline — it can never be "
        f"sniped when it re-lists: {_base}")

    # (4) `_announcement_tag` — the label on every NEW LISTING DETECTED line.
    _anns = [{"title": "Scheduled maintenance", "content": ""},
             {"title": "Perpetual listing: $WIF now trading", "content": ""},
             {"title": "", "content": "MOODENG debuts today"}]
    assert _announcement_tag(_anns, "WIF") == "Perpetual listing: $WIF now trading"
    assert _announcement_tag(_anns, "MOODENG") == "announced", \
        "a matching announcement with no title must still name itself"
    assert _announcement_tag(_anns, "ABSENT") is None
    assert _announcement_tag(None, "WIF") is None       # no feed, no crash
    assert len(_announcement_tag([{"title": "x" * 200, "content": "ZZZ"}],
                                 "ZZZ")) == 60, "the tag must stay a LOG label"

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
          "lost-ack position and caps on REAL deployed notional; the SHADOW "
          "path still books, persists and never sends; a SURGE admission "
          "records its ratio + mult, survives a restart, reaches the ledger "
          "row and degrades junk to no extra; both save_state writers "
          "persist the same shape; and the YOUNG source admits off the scout, "
          "falls back to a BUDGETED and MONOTONE candle probe, stamps its own "
          "close tag and carries no surge telemetry; and a LISTING wins the "
          "tie, is sniped ONCE even when it also surges, keeps its retry clock "
          "while it flaps and never absorbs into the baseline).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        try:
            main()
        except KeyboardInterrupt:
            log.info("stopped by user.")
