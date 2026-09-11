#!/usr/bin/env python3
"""🔭 THE ENTRY-CELL OBSERVER — how often does a book's entry cell OPEN,
for how long does it STAY open, and how many openings did its own universe
never show it?

**Eamon, 11-Sep-2026:** *"Let's use this knowledge we now have about the
uptrend and entertain the idea of having something dedicated to providing bots
the reaction time"* -> *"Yes fantastic work let's do it"*.

WHY THIS EXISTS. 👩 mum went live and did not trade. Every explanation offered
was about her plumbing — a daily-loss halt that pre-empted her own stop, a
`maxdd` lock, an RSI bar — and after all of them were fixed she still held
nothing, because on the day she was fixed the MARKET was not in her cell: her
87 scanned names had a median RSI(14) of 64.2 against a bar of 42, exactly one
name below it, and that one sat inside an uptrend her rule refuses. Her unrailed
paper twin held nothing either, on the identical reading.

That is a supply question, and the fleet had no instrument for it. The books
publish a census of their OWN scan (`scan_census`), which answers *"did anything
qualify in the 87 names I look at?"* — it structurally cannot answer the two
questions that decide what to build next:

  1. **Did the cell open somewhere she cannot see?** Her crypto half is the
     top-N by volume off the scout; the venue lists ~215 books. An opening on
     name 95 is invisible to her census and invisible to this file's reader.
     That count is I26's number: the cost of a narrow LIST, measured, not
     argued. It is what decides whether widening `FAMILY_CRYPTO_N` is worth
     anything at all.
  2. **How long does an opening LAST?** This is Eamon's reaction-time question
     and it is the more important half. If a missed opening dwells four hours,
     the fix is the universe and a 90s loop is already fast enough. If it
     dwells five minutes, the universe is beside the point and what matters is
     how quickly a book can act — two different builds, and nothing in the
     fleet could tell them apart.

WHAT IT IS NOT. **PUBLISH-ONLY.** It places no order, writes no lever, moves no
capital and promotes nothing — asserted by AST in
`tests/autonomy/test_entry_cell_observer.py`, the `fleet_allocation` contract.
It is an instrument, and per I22 an instrument does not get a row, a clock or
capital.

THE CELL IS THE BOOK'S OWN CODE, CALLED. `observe_carrier` invokes
`carrier.signals(bars, extra)` — the REAL method the live arm calls at its own
entry site — and resolves the scanned universe through
`lighter_family_bot.carrier_universe`, the declared ONE OWNER of that rule.
There is no second copy of the entry rule here, because a second copy of a rule
is a second rule ((hj)): a re-implementation would drift from the books within
a week and then the measurement would be about this file instead of about them.

DECLARED LIMITS, because an overstating detector is one the operator learns to
ignore ((gl)):

  * **AN OPENING IS NOT A TRADE.** The observer models the ENTRY CELL only. The
    universe-independent gates the live loop applies after it — slots full, a
    coin already held, per-coin cooldown, the fleet long-budget veto, the
    notional cap, market hours — are NOT modelled, so `missed` is an UPPER
    BOUND on trades a wider universe would have produced, never a forecast of
    them.
  * **AN OPENING IS NOT EDGE.** It is supply. Which names are worth admitting
    is a separate, priced question (I19/I26: liquidity, measured slippage,
    whether the cell's edge holds off the majors). A count here authorises a
    MEASUREMENT, never a widening.
  * **COVERAGE IS GOVERNED AND PUBLISHED.** One candle fetch per (coin, tf) per
    closed candle, under a per-cycle budget, so a cold boot sweeps in over
    several cycles instead of bursting. `covered`/`pending` publish every loop:
    `open: 0` must never be byte-identical between "nothing qualified" and
    "not looked at yet" (I1, and the (lv) `{open: 0}` ambiguity).
  * **DWELL IS QUANTISED BY THE SAMPLE CADENCE.** An opening shorter than one
    cycle is invisible, and every dwell is a multiple of the loop. The
    resolution publishes as `dwell_resolution_s` so no reader mistakes a floor
    for a measurement, and a dwell is only ever CLOSED on a cycle that actually
    graded that coin — an uncovered coin carries, rather than being recorded as
    a short opening that never happened.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import statistics
import sys
import time

log = logging.getLogger("entry-cell-observer")

#: bot_state key. Advisory + publish-only: declared in `UNPAGEABLE_OK`.
STATE_KEY = "entry-cell-observer"

#: Seconds between samples. Also the dwell resolution, so it is deliberately
#: well under the shortest family timeframe (15m) — a cell that opens and
#: closes inside one candle is still seen twice.
LOOP_SECONDS = int(os.environ.get("OBSERVER_LOOP_SECONDS", "300"))

#: TTL published on the key. 3x the loop, the watchdog's DARK convention.
TTL_SEC = int(os.environ.get("OBSERVER_TTL_SEC", str(3 * LOOP_SECONDS)))

#: New candle fetches allowed per cycle. A cached-and-fresh read is FREE and
#: never counted. At the default a ~215-book venue warms in ~4 cycles (~20
#: min) and then costs only what the candle clock demands.
FETCH_BUDGET = int(os.environ.get("OBSERVER_FETCH_BUDGET", "60"))

#: Venue names to consider, by 24h volume descending. None = the whole list.
VENUE_LIMIT = int(os.environ.get("OBSERVER_VENUE_LIMIT", "0")) or None

#: Dwell samples retained per (book, bucket). Bounded so the state blob cannot
#: grow without limit — a persisted list that only ever appends is a slow leak.
DWELL_MAX_SAMPLES = 200

#: Names reported in the "most often open and unseen" ranking. Bounded for the
#: same reason `refused_coins` caps its list: a payload is read by a human.
TOP_MISSED = 12


#: THE CEILINGS, PUBLISHED WITH THE NUMBERS. Named one per constant rather
#: than written inline, because a multi-line string inside a LIST literal is
#: byte-indistinguishable from a dropped comma — four of these were flagged by
#: CodeQL on this module's first review, and it was right: the hazard is not
#: the wrapping but that a later edit deleting a line would silently shorten
#: the list instead of failing. In an assignment there is no comma to miss.
LIMIT_NOT_A_TRADE = (
    "an opening is not a trade: slots/held/cooldown/budget/cap gates are NOT "
    "modelled, so missed_n is an upper bound")
LIMIT_NOT_EDGE = (
    "an opening is not edge: admitting a name is a separate priced "
    "measurement (I19/I26)")
LIMIT_DWELL_QUANTISED = (
    "dwell is quantised by dwell_resolution_s and is a floor, never an exact "
    "duration")
LIMIT_GATE_BLOCKED_IS_NEITHER = (
    "gate_blocked_n is in NEITHER actionable_n nor missed_n: the cell is open "
    "and the entry site refuses the name, so no universe change reaches it")

#: The published order. A tuple so a consumer cannot mutate the contract.
LIMITS = (LIMIT_NOT_A_TRADE, LIMIT_NOT_EDGE, LIMIT_DWELL_QUANTISED,
          LIMIT_GATE_BLOCKED_IS_NEITHER)


# ---------------------------------------------------------------------------
# Pure arithmetic. No venue, no database — every function below is testable
# against a hand-built reading, and the tests do exactly that.

def cell_open(sig):
    """Did the book's own `signals()` open its entry cell on this candle?

    ONE definition, matching the live entry site: a truthy `enter` tag. A
    carrier that returns None (too few bars, an unmeasurable indicator) has not
    opened, and is NOT the same thing as a carrier that refused — which is why
    `observe_carrier` counts `ungraded` separately.
    """
    return bool(sig and sig.get("enter"))


def _finite(x):
    """A float that storage will accept, or None (I5: a bad field becomes null
    and the row still writes; losing one field beats losing the whole state)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def refusal_reason(sig, rsi_bar=None):
    """WHICH TERM of the cell refused this coin, from the book's own published
    signal dict. Reported, never acted on.

    Deliberately derived from the `signals()` RETURN VALUE rather than from a
    re-evaluation of the rule: the return value is what the book itself says
    about the candle, so this cannot disagree with the book ((hj)). A carrier
    that publishes neither `rsi` nor `uptrend` reports `opaque` — honest, and
    visibly different from "it passed".
    """
    if sig is None:
        return "ungraded"
    if sig.get("enter"):
        return "open"
    terms = []
    rsi, up, vol = sig.get("rsi"), sig.get("uptrend"), sig.get("vol")
    if rsi_bar is not None and isinstance(rsi, (int, float)):
        if not (float(rsi) < float(rsi_bar)):
            terms.append("rsi_above_bar")
    if up is True:
        terms.append("uptrend")
    if sig.get("vel_ok") is False:
        terms.append("vel_band")
    # The volume term, from the book's OWN published `vol` — never re-derived
    # from bars here. A carrier that does not publish it reports `opaque`
    # rather than a guess: absent is absent, and an inferred term would be a
    # second copy of the rule ((hj)). Measured 11-Sep: this single term was
    # the whole of `opaque` on 👩 mum's live sweep — SMIC at RSI 30.1 and
    # outside an uptrend, refused because its underlying market was shut.
    if isinstance(vol, (int, float)) and not (float(vol) > 0):
        terms.append("no_volume")
    if not terms:
        return "opaque"
    return "+".join(terms)


def observe_carrier(carrier, syms, universe, bars_for, extra_for,
                    covered=None, rsi_bar=None, admits=None):
    """Evaluate `carrier`'s entry cell over `syms`, splitting by whether the
    carrier's own `universe` contains the name AND whether its entry site would
    admit it.

    `bars_for(sym)` returns bars or None; `covered` (a set) names the symbols
    this cycle actually graded — a symbol outside it was not looked at, which
    is a THIRD state beside open and shut and must not read as either.

    `admits(sym) -> bool` is THE ENTRY-SITE GATE, injected so this function
    cannot hold a copy of it: `run_once` passes
    `not lighter_family_bot.noncrypto_entry_blocked(...)`, the declared one
    owner of that rule. It is the distinction the whole instrument turns on.
    Measured on 👩 mum 11-Sep: of the six names under her RSI bar, THREE were
    non-crypto books her per-asset oracle cannot grade (SMIC, MU, BRENTOIL —
    all three in her row's own `ungraded` list), so the cell being open on them
    authorises nothing. An observer that counted those as openings would have
    argued for a universe widening when the binding constraint is a gate that
    opens on daily bars and nothing else. `(uw)` reached the same verdict on
    🙏 avo by hand — *"held-starved and gate-refused, not signal-starved"* —
    and this is that reading, published every loop.

    Default `admits=None` means "admit everything", which is correct for a
    crypto-only carrier and is what the pure tests exercise.
    """
    uni = {str(c).upper() for c in (universe or ())}
    seen, reasons = {}, {}
    out = {"bot": getattr(carrier, "bot", None),
           "tf": getattr(carrier, "tf", None),
           "universe_n": len(uni), "scanned_n": 0,
           "open_in_universe": [], "open_missed": [],
           "open_gate_blocked": [], "ungraded": 0, "not_covered": 0}
    for sym in syms:
        key = str(sym).upper()
        if covered is not None and key not in covered:
            out["not_covered"] += 1
            continue
        bars = bars_for(sym)
        if not bars or not bars.get("t"):
            out["not_covered"] += 1
            continue
        try:
            sig = carrier.signals(bars, extra_for(sym))
        except Exception as e:                              # noqa: BLE001
            # A carrier that raises on one coin must not silence the sweep for
            # the other 214 — and the failure is COUNTED, never swallowed into
            # a clean-looking zero.
            log.warning("%s signals(%s) raised: %s",
                        out["bot"], sym, e)
            out["ungraded"] += 1
            continue
        out["scanned_n"] += 1
        if sig is None:
            out["ungraded"] += 1
            continue
        opened = cell_open(sig)
        seen[key] = opened
        why = refusal_reason(sig, rsi_bar=rsi_bar)
        reasons[why] = reasons.get(why, 0) + 1
        if opened:
            # FAIL-CLOSED on an unreadable gate: a predicate that raises is
            # read as "would not admit", the same direction the live entry site
            # fails in. An instrument must not report an opening as actionable
            # because its own gate check broke.
            try:
                ok = True if admits is None else bool(admits(sym))
            except Exception as e:                          # noqa: BLE001
                log.warning("%s admits(%s) raised: %s", out["bot"], sym, e)
                ok = False
            if not ok:
                out["open_gate_blocked"].append(key)
            elif key in uni:
                out["open_in_universe"].append(key)
            else:
                out["open_missed"].append(key)
    for k in ("open_in_universe", "open_missed", "open_gate_blocked"):
        out[k].sort()
    out["open_n"] = (len(out["open_in_universe"]) + len(out["open_missed"])
                     + len(out["open_gate_blocked"]))
    # THE HEADLINE PAIR. `actionable_n` is what the book could act on in its
    # own list right now; `missed_n` is what a wider list would have shown it.
    # `gate_blocked_n` is neither and must never be added to either — it is the
    # count that says a widening is the wrong build.
    out["actionable_n"] = len(out["open_in_universe"])
    out["missed_n"] = len(out["open_missed"])
    out["gate_blocked_n"] = len(out["open_gate_blocked"])
    out["reasons"] = reasons
    return out, seen


def dwell_step(prev, seen, universe, now_ts, max_samples=DWELL_MAX_SAMPLES,
               blocked=None):
    """Advance the dwell bookkeeping by one sample.

    `seen` maps symbol -> is-open for the symbols GRADED THIS CYCLE ONLY. A
    symbol absent from `seen` carries its open stance untouched: closing an
    opening because the observer did not look at it would manufacture short
    dwells out of its own fetch budget, which is the measurement reporting on
    itself rather than on the market (the (ml) stale-reader shape).

    The bucket (`in_universe` / `missed`) is stamped AT THE OPEN, so a universe
    widened mid-dwell cannot retroactively re-file an opening it did not show
    the book.

    -> (state, closed) with closed = [{"sym","secs","bucket"}, ...]
    """
    prev = prev if isinstance(prev, dict) else {}
    uni = {str(c).upper() for c in (universe or ())}
    blk = {str(c).upper() for c in (blocked or ())}
    since, closed = {}, []
    raw = prev.get("open_since")
    raw = raw if isinstance(raw, dict) else {}
    samples = {"in_universe": [], "missed": []}
    for b in samples:
        got = (prev.get("dwell") or {}).get(b)
        if isinstance(got, list):
            samples[b] = [s for s in (_finite(v) for v in got)
                          if s is not None][-max_samples:]

    for sym, rec in raw.items():
        key = str(sym).upper()
        # Defensive parse: bot_state is read back from storage, so a record
        # may be a bare timestamp from an older shape or junk from neither.
        if isinstance(rec, dict):
            ts, bucket = _finite(rec.get("ts")), rec.get("bucket")
        else:
            ts, bucket = _finite(rec), None
        if ts is None:
            continue
        bucket = bucket if bucket in samples else (
            "in_universe" if key in uni else "missed")
        if key in seen and not seen[key]:
            secs = max(0.0, float(now_ts) - ts)
            closed.append({"sym": key, "secs": secs, "bucket": bucket})
            samples[bucket] = (samples[bucket] + [secs])[-max_samples:]
        else:
            since[key] = {"ts": ts, "bucket": bucket}

    for key, opened in seen.items():
        if opened and key not in since:
            since[key] = {"ts": float(now_ts),
                          "bucket": "in_universe" if key in uni else "missed"}
    # A gate-blocked opening is dropped from the dwell memory entirely: its
    # duration is not a reaction-time question, because no reaction was
    # available. Carrying it would inflate the `missed` dwell with names a
    # wider universe still could not have traded.
    for key in list(since):
        if key in blk:
            since.pop(key, None)

    cyc = prev.get("cycles") if isinstance(prev.get("cycles"), dict) else {}
    n = int(cyc.get("n") or 0) + 1
    any_open = any(v for k, v in seen.items() if k not in blk)
    any_uni = any(v and k in uni and k not in blk for k, v in seen.items())
    state = {"open_since": since, "dwell": samples,
             "cycles": {"n": n,
                        "with_open_venue": int(cyc.get("with_open_venue") or 0)
                                           + (1 if any_open else 0),
                        "with_open_universe":
                            int(cyc.get("with_open_universe") or 0)
                            + (1 if any_uni else 0)},
             "missed_counts": _bump_missed(
                 prev.get("missed_counts"),
                 [k for k, v in seen.items()
                  if v and k not in uni and k not in (blocked or ())])}
    return state, closed


def _bump_missed(prev, syms):
    """Per-coin tally of openings the book's universe did not show it.

    This is the actionable half: a count of 1 is noise, a name that opens
    outside her list on 40 of 100 cycles is a candidate with a number attached.
    """
    out = {}
    if isinstance(prev, dict):
        for k, v in prev.items():
            iv = _finite(v)
            if iv is not None and iv > 0:
                out[str(k).upper()] = int(iv)
    for s in syms:
        k = str(s).upper()
        out[k] = out.get(k, 0) + 1
    return out


def summarize_dwell(samples, resolution_s=None):
    """Median / p90 / max over retained dwell samples, or an explicit dark
    reading. NEVER a zero for "no samples": 0 seconds and "never measured" are
    different facts and a consumer must be able to tell them apart (I1)."""
    vals = sorted(s for s in (_finite(v) for v in (samples or ()))
                  if s is not None)
    if not vals:
        return {"n": 0, "median_s": None, "p90_s": None, "max_s": None,
                "resolution_s": resolution_s}
    return {"n": len(vals),
            "median_s": round(statistics.median(vals), 1),
            # The same one-sided p90 convention the fleet uses elsewhere
            # (`overshoot_p90_bps`): index ceil(0.9n)-1 on the sorted sample.
            "p90_s": round(vals[max(0, int(math.ceil(0.9 * len(vals))) - 1)], 1),
            "max_s": round(vals[-1], 1),
            "resolution_s": resolution_s}


def build_payload(books, venue_n, covered_n, pending_n, now_ts,
                  loop_s=LOOP_SECONDS, no_bars_n=0, fetches=None,
                  venue_basis="scout"):
    """Assemble the published reading. Pure: `books` is already observed."""
    out = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
           "ttl_sec": TTL_SEC,
           "venue_n": venue_n,
           #: "scout" = the venue's own list was read; "dark" = it was not, so
           #: every `missed_n` below is null rather than zero.
           "venue_basis": venue_basis,
           # `basis` keys on PENDING alone: a book with no candle series is
           # covered as far as this sweep can ever be, while a pending one is
           # the sweep still warming — only the second makes `open: 0` partial.
           "coverage": {"covered": covered_n, "pending": pending_n,
                        "no_bars": no_bars_n, "fetches": fetches,
                        "basis": ("complete" if not pending_n
                                  and venue_basis == "scout" else "partial")},
           "dwell_resolution_s": loop_s,
           "books": {},
           # Stated in the payload itself, not only in this file: a reader who
           # finds `missed_n` on a dashboard must meet its ceiling there too.
           "limits": list(LIMITS)}
    for b in books:
        bot = b.get("bot")
        if not bot:
            continue
        cyc = b.get("cycles") or {}
        n = int(cyc.get("n") or 0)
        out["books"][bot] = {
            "tf": b.get("tf"),
            "universe_n": b.get("universe_n"),
            "scanned_n": b.get("scanned_n"),
            "open_n": b.get("open_n"),
            "open_in_universe": b.get("open_in_universe"),
            "open_missed": b.get("open_missed"),
            "open_gate_blocked": b.get("open_gate_blocked"),
            "actionable_n": b.get("actionable_n"),
            "missed_n": b.get("missed_n"),
            "gate_blocked_n": b.get("gate_blocked_n"),
            "ungraded": b.get("ungraded"),
            "not_covered": b.get("not_covered"),
            "reasons": b.get("reasons"),
            "rsi_bar": b.get("rsi_bar"),
            "cycles": cyc,
            "open_frac_universe": (round(int(cyc.get("with_open_universe") or 0)
                                         / n, 4) if n else None),
            "open_frac_venue": (round(int(cyc.get("with_open_venue") or 0)
                                      / n, 4) if n else None),
            "dwell": b.get("dwell"),
            "top_missed": b.get("top_missed"),
        }
    return out


def top_missed(counts, cycles_n, limit=TOP_MISSED):
    """Rank the unseen openings. Publishes the CYCLE COUNT beside each name, so
    a name is read as a rate rather than a score — `cycles` is the denominator
    and a ranking without one is how a thin sample gets promoted (I16)."""
    items = sorted(((str(k), int(v)) for k, v in (counts or {}).items()
                    if _finite(v) and int(v) > 0),
                   key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"sym": k, "cycles_open": v,
             "frac": round(v / cycles_n, 4) if cycles_n else None}
            for k, v in items]


# ---------------------------------------------------------------------------
# The live sweep. Everything venue-facing lives below this line.

class BudgetedBars:
    """`CandleCache` under a per-cycle NEW-FETCH budget.

    A cached-and-still-fresh read costs nothing and is always served. A read
    that would hit the venue spends budget; once spent, the symbol is reported
    UNCOVERED rather than given stale or absent bars — an exhausted budget must
    degrade to "I did not look", never to "nothing there".
    """

    def __init__(self, cache, budget=FETCH_BUDGET):
        self.cache, self.budget, self.spent = cache, budget, 0
        #: `pending` is "the budget ran out" and `no_bars` is "the venue has no
        #: usable series". Kept APART on purpose: the first clears itself next
        #: cycle and the second never will, and a single count would hide a
        #: permanently unreadable book inside a warming sweep.
        self.covered, self.pending, self.no_bars = set(), set(), set()

    def _fresh(self, coin, tf):
        hit = self.cache.data.get((coin, tf))
        return bool(hit and int(time.time() * 1000) < hit["next_due"])

    def get(self, coin, tf):
        key = str(coin).upper()
        if self._fresh(coin, tf):
            self.covered.add(key)
            return self.cache.data[(coin, tf)]["bars"]
        if self.spent >= self.budget:
            self.pending.add(key)
            return None
        self.spent += 1
        bars = self.cache.get(coin, tf)
        if bars and bars.get("t"):
            self.covered.add(key)
        else:
            self.no_bars.add(key)
        return bars


def _carriers(fam):
    """The LIVING family carriers that expose an entry cell, via the module's
    own `live_strategies()` — derived, never a second roster ((mo))."""
    return [s for s in fam.live_strategies() if hasattr(s, "signals")]


def run_once(fam, bus, venue, cache, store, prev_state, budget=FETCH_BUDGET,
             venue_limit=VENUE_LIMIT, now_ts=None):
    """One sample across every living family carrier. Returns (payload, state)."""
    now_ts = time.time() if now_ts is None else now_ts
    # THE VENUE LIST, AND ITS DARKNESS IS PUBLISHED. A dark scout returns [],
    # the observer then sees only each book's own list, and `missed_n` would
    # read 0 — byte-identical to "a wider universe would have shown her
    # nothing", which is the exact claim this instrument exists to make. So the
    # basis is published and a dark read is never a clean zero (I1/I6: an
    # absence is evidence only against a control group). Caught in this
    # module's own first live run, where an unset DATABASE_URL made the sweep
    # silently self-confirming.
    try:
        venue_syms = [c for c in (bus.scout_universe(
            min_vol_m=0.0, limit=venue_limit) or []) if venue.supports(c)]
    except Exception as e:                                  # noqa: BLE001
        log.warning("venue universe unavailable: %s", e)
        venue_syms = []
    venue_basis = "scout" if venue_syms else "dark"
    if venue_basis == "dark":
        log.error("VENUE UNIVERSE DARK — missed_n is not measurable this "
                  "cycle and publishes as null, not 0")
    books, new_state = [], {}
    bars = BudgetedBars(cache, budget=budget)
    # The oracle's per-asset verdicts, fetched ONCE per cycle through the
    # family module's own wrapper — the same map the live entry site reads.
    # Passing {} here (the draft did) makes every non-crypto name fail-closed
    # and the observer then disagrees with the bot it is measuring.
    oracle = fam.noncrypto_regimes()
    for s in _carriers(fam):
        try:
            uni = [c for c in fam.carrier_universe(s) if venue.supports(c)]
        except Exception as e:                              # noqa: BLE001
            log.warning("%s universe unavailable: %s", getattr(s, "bot", "?"), e)
            continue
        # The venue sweep UNION the book's own list: a configured name the
        # scout happens not to rank must still be graded, or the in-universe
        # half of the split under-reports.
        syms = list(dict.fromkeys([str(c).upper() for c in venue_syms]
                                  + [str(c).upper() for c in uni]))
        regime, tide = _regime(fam, cache)

        def extra_for(sym, _f=fam, _r=regime, _t=tide, _o=oracle):
            r_up, t_up = _f.regime_inputs_for(sym, _r, _t, _o)
            out = {"btc_regime_up": r_up}
            if getattr(_f, "MOMO_TIDE_GATE", False):
                out["btc_tide_up"] = t_up
            return out

        def admits(sym, _f=fam, _r=regime, _t=tide, _o=oracle):
            r_up, _ = _f.regime_inputs_for(sym, _r, _t, _o)
            return not _f.noncrypto_entry_blocked(sym, r_up)

        rsi_bar = getattr(s, "RSI_MAX", None)
        obs, seen = observe_carrier(
            s, syms, uni, lambda c, _s=s, _b=bars: _b.get(c, _s.tf),
            extra_for, covered=None, rsi_bar=rsi_bar, admits=admits)
        st, _closed = dwell_step((prev_state or {}).get(s.bot), seen, uni,
                                 now_ts, blocked=obs["open_gate_blocked"])
        if venue_basis == "dark":
            obs["missed_n"] = None      # unmeasurable, and says so
        obs["rsi_bar"] = _finite(rsi_bar)
        obs["cycles"] = st["cycles"]
        obs["dwell"] = {b: summarize_dwell(st["dwell"].get(b), LOOP_SECONDS)
                        for b in ("in_universe", "missed")}
        obs["top_missed"] = top_missed(st["missed_counts"],
                                      int(st["cycles"].get("n") or 0))
        books.append(obs)
        new_state[s.bot] = st
    payload = build_payload(books, len(venue_syms), len(bars.covered),
                            len(bars.pending), now_ts,
                            no_bars_n=len(bars.no_bars),
                            fetches=bars.spent, venue_basis=venue_basis)
    return payload, new_state


def _regime(fam, cache):
    """BTC's regime inputs, through the family module's own owners — which take
    the CACHE, not bars, and pick their own timeframes (4h for the regime).
    Passing bars here would have type-errored every cycle into the fail-safe
    below and published a silently ungated reading.

    Fail-safe: any doubt returns (False, False), the strategies' own documented
    conservative default, and `regime_inputs_for` then decides per name — which
    for a non-crypto book is fail-CLOSED, the shipped behaviour.
    """
    try:
        return fam.btc_regime_up(cache), fam.btc_tide_up(cache)
    except Exception as e:                                  # noqa: BLE001
        log.warning("btc regime unavailable: %s", e)
        return False, False


def publish_reading(store, payload, state):
    """Write the reading and the dwell memory. **The persistence result is
    load-bearing** (I4): a silent write failure makes this organ amnesiac while
    it keeps publishing a fresh-looking payload, and the dwell numbers would
    then be computed from a frozen `open_since` forever."""
    body = dict(payload)
    body["_dwell_state"] = state
    # [(hw)/I13] A RECOVERED ORGAN MUST STOP READING AS SICK. `organ_main`
    # stamps the death; the happy path has to clear it, or one crash makes the
    # key permanently sick and the detector means nothing afterwards.
    store.clear_organ_error(body)
    ok = store.save_state(STATE_KEY, body)
    if not ok:
        log.error("OBSERVER STATE NOT PERSISTED — dwell memory will not "
                  "advance; payload not published this cycle")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--publish", action="store_true",
                    help="write bot_state (a bare run prints and writes nothing)")
    ap.add_argument("--loop", action="store_true",
                    help="sample every OBSERVER_LOOP_SECONDS (the organ form)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if a.selftest:
        return _selftest()

    import bot_pnl_store as store
    import fleet_bus as bus
    import lighter_family_bot as fam
    from venues.lighter_client import LighterClient

    # `with_signer=False` is the structural half of publish-only: a client with
    # no signer cannot place an order even if a future edit asked it to. The
    # same construction the shadow host uses for its read path.
    venue = LighterClient(net="mainnet", with_signer=False)
    cache = fam.CandleCache(venue)
    prev = {}
    got = store.load_state(STATE_KEY) or {}
    if isinstance(got.get("_dwell_state"), dict):
        prev = got["_dwell_state"]
    while True:
        payload, prev = run_once(fam, bus, venue, cache, store, prev)
        if a.publish:
            publish_reading(store, payload, prev)
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        if not a.loop:
            return 0
        time.sleep(LOOP_SECONDS)


# ---------------------------------------------------------------------------

def _selftest():
    """Drives every pure function against hand-built readings. The dwell cases
    are the ones that matter: a carried (uncovered) opening, a bucket stamped
    at open, and a bounded sample list."""
    assert cell_open({"enter": "oversold-rebound"}) is True
    assert cell_open({"enter": None}) is False
    assert cell_open(None) is False

    assert refusal_reason(None) == "ungraded"
    assert refusal_reason({"enter": "x"}) == "open"
    assert refusal_reason({"enter": None, "rsi": 64.0, "uptrend": False},
                          rsi_bar=42.0) == "rsi_above_bar"
    assert refusal_reason({"enter": None, "rsi": 30.0, "uptrend": True},
                          rsi_bar=42.0) == "uptrend"
    assert refusal_reason({"enter": None, "rsi": 64.0, "uptrend": True},
                          rsi_bar=42.0) == "rsi_above_bar+uptrend"
    assert refusal_reason({"enter": None}) == "opaque"
    # THE VOLUME TERM — the live refusal this instrument could not name until
    # `OversoldRebound.signals` published `vol`. A zero-volume candle that
    # passes every other term must read as `no_volume`, never `opaque`.
    assert refusal_reason({"enter": None, "rsi": 30.0, "uptrend": False,
                           "vol": 0.0}, rsi_bar=42.0) == "no_volume"
    assert refusal_reason({"enter": None, "rsi": 64.0, "uptrend": False,
                           "vol": 0.0}, rsi_bar=42.0) == "rsi_above_bar+no_volume"
    # A carrier that publishes no `vol` is still `opaque` — absent is absent,
    # and a guessed term would be a second copy of the rule.
    assert refusal_reason({"enter": None, "rsi": 30.0,
                           "uptrend": False}, rsi_bar=42.0) == "opaque"
    assert refusal_reason({"enter": None, "rsi": 30.0, "uptrend": False,
                           "vol": 5.0}, rsi_bar=42.0) == "opaque"

    class _C:
        bot, tf, RSI_MAX = "book", "1h", 42.0

        def signals(self, bars, extra):
            r = bars["rsi"]
            return {"enter": "go" if r < self.RSI_MAX else None,
                    "rsi": r, "uptrend": False}

    reading = {"AAA": 30.0, "BBB": 70.0, "ZZZ": 20.0}

    def _bars(sym):
        return {"t": [1], "rsi": reading[sym]} if sym in reading else None

    obs, seen = observe_carrier(_C(), ["AAA", "BBB", "ZZZ", "QQQ"],
                                ["AAA", "BBB"], _bars, lambda s: {},
                                rsi_bar=42.0)
    assert obs["open_in_universe"] == ["AAA"], obs
    assert obs["open_missed"] == ["ZZZ"], obs          # outside the universe
    assert obs["missed_n"] == 1 and obs["open_n"] == 2
    assert obs["not_covered"] == 1                    # QQQ had no bars
    assert obs["reasons"] == {"open": 2, "rsi_above_bar": 1}, obs["reasons"]
    assert seen == {"AAA": True, "BBB": False, "ZZZ": True}

    # A carrier that raises is counted, not swallowed, and does not stop the rest.
    class _Boom(_C):
        def signals(self, bars, extra):
            if bars["rsi"] == 70.0:
                raise RuntimeError("boom")
            return super().signals(bars, extra)

    ob2, _ = observe_carrier(_Boom(), ["AAA", "BBB"], ["AAA", "BBB"],
                             _bars, lambda s: {}, rsi_bar=42.0)
    assert ob2["ungraded"] == 1 and ob2["open_in_universe"] == ["AAA"], ob2

    # THE ENTRY-SITE GATE SPLIT — the measurement the whole instrument turns
    # on. AAA is in her list, ZZZ is not, and QQ2 is open but the gate refuses
    # it: QQ2 belongs to NEITHER headline count.
    reading["QQ2"] = 25.0
    ob3, seen3 = observe_carrier(
        _C(), ["AAA", "BBB", "ZZZ", "QQ2"], ["AAA", "BBB", "QQ2"], _bars,
        lambda s: {}, rsi_bar=42.0, admits=lambda sym: sym != "QQ2")
    assert ob3["open_in_universe"] == ["AAA"], ob3
    assert ob3["open_missed"] == ["ZZZ"], ob3
    assert ob3["open_gate_blocked"] == ["QQ2"], ob3
    assert (ob3["actionable_n"], ob3["missed_n"], ob3["gate_blocked_n"]) == (
        1, 1, 1), ob3
    assert ob3["open_n"] == 3, ob3          # every opening is counted ONCE
    # FAIL-CLOSED: a gate predicate that raises reads as "would not admit".
    def _boom_admits(sym):
        raise RuntimeError("oracle down")
    ob4, _ = observe_carrier(_C(), ["AAA"], ["AAA"], _bars, lambda s: {},
                             rsi_bar=42.0, admits=_boom_admits)
    assert ob4["open_gate_blocked"] == ["AAA"] and ob4["actionable_n"] == 0, ob4

    # A GATE-BLOCKED OPENING NEVER ENTERS THE DWELL MEMORY, the cycle
    # counters, or the missed ranking: its duration is not a reaction-time
    # question because no reaction was available.
    stg, _ = dwell_step({}, {"QQ2": True}, [], 0.0, blocked=["QQ2"])
    assert stg["open_since"] == {}, stg
    assert stg["cycles"]["with_open_venue"] == 0, stg
    assert stg["missed_counts"] == {}, stg
    # ... and the same reading WITHOUT the block does record it, so the
    # assertions above are about the block and not about an empty fixture.
    stg2, _ = dwell_step({}, {"QQ2": True}, [], 0.0)
    assert "QQ2" in stg2["open_since"] and stg2["missed_counts"] == {"QQ2": 1}
    assert stg2["cycles"]["with_open_venue"] == 1
    del reading["QQ2"]

    # DWELL. Open at t=0, still open at t=300, closed at t=600 => 600s.
    st, closed = dwell_step({}, {"AAA": True}, ["AAA"], 0.0)
    assert closed == [] and st["open_since"]["AAA"]["ts"] == 0.0
    assert st["open_since"]["AAA"]["bucket"] == "in_universe"
    st, closed = dwell_step(st, {"AAA": True}, ["AAA"], 300.0)
    assert closed == [] and st["cycles"]["n"] == 2
    st, closed = dwell_step(st, {"AAA": False}, ["AAA"], 600.0)
    assert closed == [{"sym": "AAA", "secs": 600.0, "bucket": "in_universe"}]
    assert st["dwell"]["in_universe"] == [600.0] and not st["open_since"]

    # AN UNCOVERED COIN CARRIES. Absent from `seen` => neither closed nor
    # re-stamped, so the dwell clock keeps running from the original open.
    st, _ = dwell_step({}, {"AAA": True}, ["AAA"], 0.0)
    st, closed = dwell_step(st, {}, ["AAA"], 300.0)
    assert closed == [] and st["open_since"]["AAA"]["ts"] == 0.0, st
    st, closed = dwell_step(st, {"AAA": False}, ["AAA"], 900.0)
    assert closed[0]["secs"] == 900.0, closed

    # The bucket is stamped AT THE OPEN: widening the universe mid-dwell does
    # not re-file an opening the book was never shown.
    st, _ = dwell_step({}, {"ZZZ": True}, [], 0.0)
    assert st["open_since"]["ZZZ"]["bucket"] == "missed"
    st, closed = dwell_step(st, {"ZZZ": False}, ["ZZZ"], 60.0)
    assert closed[0]["bucket"] == "missed", closed

    # Counters and the ranking.
    assert st["cycles"]["with_open_venue"] == 1
    assert st["cycles"]["with_open_universe"] == 0
    assert top_missed({"ZZZ": 4, "YYY": 9}, 10)[0] == {
        "sym": "YYY", "cycles_open": 9, "frac": 0.9}

    # Bounded retention, BOTH PATHS. The load path trims a list read back from
    # storage; the CLOSE path must also trim, or a cycle that closes many
    # openings at once overshoots until the next load tidies up. The close-path
    # cap was untested until a mutation survived and said so.
    big = {"dwell": {"in_universe": [1.0] * 500}}
    st2, _ = dwell_step(big, {}, [], 0.0)
    assert len(st2["dwell"]["in_universe"]) == DWELL_MAX_SAMPLES
    full = {"dwell": {"in_universe": [1.0] * DWELL_MAX_SAMPLES},
            "open_since": {"AAA": {"ts": 0.0, "bucket": "in_universe"}}}
    st2b, cl2b = dwell_step(full, {"AAA": False}, ["AAA"], 42.0)
    assert len(cl2b) == 1 and cl2b[0]["secs"] == 42.0
    assert len(st2b["dwell"]["in_universe"]) == DWELL_MAX_SAMPLES, (
        "the close path must trim too")
    assert st2b["dwell"]["in_universe"][-1] == 42.0   # newest kept, oldest lost

    # Junk from storage degrades, never raises.
    st3, cl3 = dwell_step({"open_since": {"AAA": "nope", "BBB": 5.0},
                           "dwell": {"in_universe": ["x", None]},
                           "cycles": "junk", "missed_counts": {"QQQ": "x"}},
                          {"BBB": False}, ["BBB"], 65.0)
    assert cl3 == [{"sym": "BBB", "secs": 60.0, "bucket": "in_universe"}]
    assert "AAA" not in st3["open_since"] and st3["cycles"]["n"] == 1

    # No-sample dwell is DARK, never 0.0 — a floor must not read as a fact.
    assert summarize_dwell([], 300) == {"n": 0, "median_s": None,
                                        "p90_s": None, "max_s": None,
                                        "resolution_s": 300}
    d = summarize_dwell([60, 120, 180, 6000], 300)
    assert (d["n"], d["median_s"], d["p90_s"], d["max_s"]) == (
        4, 150.0, 6000.0, 6000.0), d

    # Non-finite never reaches storage (I5).
    assert _finite(float("nan")) is None and _finite(float("inf")) is None
    assert summarize_dwell([float("nan"), 10.0], 300)["n"] == 1

    # The ceilings are a published CONTRACT: four of them, in order, each a
    # single string. A line deleted from the old inline list would have
    # shortened this silently — which is exactly what CodeQL flagged.
    assert len(LIMITS) == 4 and len(set(LIMITS)) == 4
    assert all(isinstance(x, str) and len(x) > 40 for x in LIMITS), LIMITS
    assert build_payload([], 1, 1, 0, 0.0)["limits"] == list(LIMITS)

    p = build_payload([dict(obs, bot="book", cycles={"n": 4,
                                                     "with_open_venue": 3,
                                                     "with_open_universe": 1})],
                      200, 180, 20, 0.0)
    assert p["coverage"] == {"covered": 180, "pending": 20, "no_bars": 0,
                             "fetches": None, "basis": "partial"}
    assert p["venue_basis"] == "scout"
    # A DARK VENUE LIST IS PARTIAL EVEN WITH NOTHING PENDING — the failure that
    # made this module's own first live run self-confirming.
    pd = build_payload([], 0, 5, 0, 0.0, venue_basis="dark")
    assert pd["coverage"]["basis"] == "partial" and pd["venue_basis"] == "dark"
    pb = build_payload([dict(ob3, bot="b2")], 9, 9, 0, 0.0)
    assert pb["books"]["b2"]["gate_blocked_n"] == 1
    assert pb["books"]["b2"]["open_gate_blocked"] == ["QQ2"]
    assert pb["books"]["b2"]["actionable_n"] == 1
    assert p["books"]["book"]["open_frac_universe"] == 0.25
    assert p["books"]["book"]["open_frac_venue"] == 0.75
    assert p["ttl_sec"] == TTL_SEC and p["dwell_resolution_s"] == LOOP_SECONDS
    assert build_payload([], 1, 5, 0, 0.0)["coverage"]["basis"] == "complete"
    json.dumps(p, allow_nan=False)          # storage would accept this row

    print("entry_cell_observer selftest OK")
    return 0


if __name__ == "__main__":
    # [(hw)/I13] Routed through the shared wrapper so a crash RECORDS on this
    # organ's own key. `run_all.sh` runs it behind `|| true`, so without this a
    # fault is invisible — and the complement still matters: a subshell that has
    # DIED runs no handler at all, which is what the TTL + vitals row are for.
    # Imported lazily for the same reason the venue is: `--selftest` must stay
    # runnable with no database and no venue present.
    if "--selftest" in sys.argv:
        sys.exit(main())
    import bot_pnl_store as _store
    sys.exit(_store.organ_main(STATE_KEY, main))
