#!/usr/bin/env python3
"""fleet_bus.py — READ-side client for the fleet's shared bot_state keys.

[2026-07-14 CONSUMPTION WIRING] The intelligence organs (bot_learn brain,
fleet_risk light, regime oracle, market pulse) have been publishing since
7 Jul with ZERO consumers — the Jul-14 enforcement review found every layer
built and nobody reading it. This module is the one place strategies import
to consume the bus, so the fail-safe contract lives in exactly one file:

  FAIL-SAFE CONTRACT (same as the publishers'):
    - no DATABASE_URL / import error / DB down  -> neutral (1.0x, no veto)
    - payload missing or STALE (updated+ttl_sec) -> neutral
    - anything unparseable                       -> neutral
  In `freqtrade backtesting` DATABASE_URL is unset, so every helper here
  returns neutral and backtests exercise pure strategy logic — live-only
  inputs can never contaminate a backtest.

Reads are cached per-process for CACHE_SEC so 4 bots x N pairs don't hammer
Postgres. Shipped in Dockerfile.freqtrade next to bot_pnl_store.py (CWD
/freqtrade), so strategies use the same `import` mechanics that already
work for the market-pulse reads.
"""
import os

from datetime import datetime, timedelta, timezone

CACHE_SEC = 300
_cache = {}   # key -> {"ts": datetime, "payload": dict|None}

# TWO-WAY guardrails for the brain's L4 stake multipliers (reduce-only
# until 21-Jul): whatever the brain publishes, a strategy sizes inside
# [0.5, 1.5] — reductions as before, boosts only on the v3 mirror bars
# (Wilson LOWER bound + t, full n floor, 3-run streak — bot_learn/
# brain_stats EXP_*). Neutral 1.0 on any doubt.
MULT_FLOOR = 0.5
# [2026-07-21 TWO-WAY MULTS — operator: "brain needs to be able to widen
# too"] Ceiling raised 1.0 -> 1.5: the brain may now publish EXPAND mults
# (1.25/1.5) for tags proving out on the v3 mirror bars (Wilson LOWER
# bound, t >= +2, full n floor, streak-gated, no urgent path — brain_stats
# EXP_*). The clamp still bounds whatever arrives; only SHADOW books read
# mults. Deliberate scope expansion of the documented reduce-only
# contract, recorded in CLAUDE.md the same day.
MULT_CEIL = 1.5


def _now_utc(current_time):
    if current_time is None:
        return datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=timezone.utc)
    return current_time


def _load(key, current_time):
    """Cached bot_state read; None on any failure."""
    now = _now_utc(current_time)
    c = _cache.get(key)
    if c is not None and abs((now - c["ts"]).total_seconds()) < CACHE_SEC:
        return c["payload"]
    payload = None
    try:
        import bot_pnl_store as store
        payload = store.load_state(key) or None
    except Exception:
        payload = None
    _cache[key] = {"ts": now, "payload": payload}
    return payload


def is_fresh(payload, current_time):
    """True only when the payload self-reports as current (updated + ttl_sec)."""
    try:
        updated = datetime.fromisoformat(str(payload["updated"]).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        ttl = float(payload.get("ttl_sec") or 0)
        return timedelta(0) <= (_now_utc(current_time) - updated) <= timedelta(seconds=ttl)
    except Exception:
        return False


def stake_multiplier(bot, entry_tag, current_time=None):
    """The brain's L4 per-(bot, enter_tag) stake multiplier — TWO-WAY since
    21-Jul (operator: "brain needs to be able to widen too"), clamped to
    [MULT_FLOOR, MULT_CEIL] = [0.5, 1.5].

    Published by bot_learn.py to bot_state 'brain-stake-mults'. Reduce side
    (0.5/0.75): a tag's negative expectancy clears the trade-count floor AND
    persists across >= PROMOTE_RUNS consecutive brain runs. Expand side
    (1.25/1.5): the v3 MIRROR bars only (brain_stats.EXP_* — Wilson lower
    bound, t >= +2.0/+2.5, full n floor, no family-praise inheritance, no
    urgent fast-path; kill switches BRAIN_MULT_ENGINE=v2 /
    BRAIN_MULT_EXPAND=off zero it). SHADOW books only — no live bot reads
    mults. Neutral 1.0 on any doubt.
    """
    try:
        p = _load("brain-stake-mults", current_time)
        if not p or not is_fresh(p, current_time):
            return 1.0
        m = ((p.get("mults") or {}).get(str(bot)) or {}).get(str(entry_tag))
        if m is None:
            return 1.0
        return max(MULT_FLOOR, min(MULT_CEIL, float(m.get("mult", 1.0))))
    except Exception:
        return 1.0


def allocation_scale(bot, current_time=None):
    """💰 fleet_allocation's evidence-weighted capital scale for one SHADOW
    book: `books[bot].target_usd / book_usd`, clamped to [0.25, 4.0], or
    None on any doubt.

    [2026-08-05 (jr) S1 — operator decision "proceed"] The allocation organ
    ranked capital by claim (`max(0, mean − 1.28·SE)`) for four days with
    zero consumers; S1 flips it from advisory to ACTING on the shadow
    notionals of the three funding books — the trio holding every measured
    claim in the fleet. The ORGAN is unchanged (still publish-only,
    `moves_capital: False` — it moves nothing; consumers choosing to read it
    is the same bus pattern as brain stake-mults). Floor 0.25 mirrors the
    organ's own PROBE_FLOOR (I17: a book cannot earn evidence with no
    capital); cap 4.0 keeps a $1k paper book's clip inside sane slippage
    modelling. Scale applies to NEW entries only, at each consumer.

    REAL MONEY NEVER READS THIS — every consumer gates on its shadow arm,
    and `tests/autonomy/test_allocation_consumer.py` pins that. Kill switch:
    `FLEET_ALLOCATION_MODE=advisory` on a service returns None here, i.e.
    every consumer reverts to its env-default clip on the next loop — the
    central-accessor pattern, so the switch reaches the consumer without a
    redeploy ([[a-kill-switch-must-reach-the-consumer]]).

    Fail-safe: dark/stale organ, unknown book, junk numbers -> None, and a
    None consumer MUST keep its env default (scale nothing).
    """
    try:
        if os.environ.get("FLEET_ALLOCATION_MODE", "act").strip().lower() \
                != "act":
            return None
        p = _load("fleet-allocation", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        row = (p.get("books") or {}).get(str(bot))
        base = float(p.get("book_usd") or 0.0)
        if not isinstance(row, dict) or base <= 0:
            return None
        t = float(row.get("target_usd"))
        if t != t or t < 0:           # NaN / negative
            return None
        return max(0.25, min(4.0, t / base))
    except Exception:
        return None


def lever_outcome(lever, current_time=None):
    """🦾 fleet_proprioception's per-lever OUTCOME verdict: 'helping' |
    'hurting' | 'neutral' | 'insufficient' | None.

    [2026-07-16 CONSUMER SUPPORT] The proprioception organ grades every
    growth-rail lever episode retrospectively (taker = replay counterfactual
    $, scout = grading throughput, gapscout = census activity, live =
    per-trade vs pre-window + shadow twin). This accessor is the ONE
    supported way for any strategy/bot to consume those grades — same
    fail-safe contract as every helper here: dark/stale/absent organ or
    unknown lever -> None, and a None consumer MUST treat it as 'no
    evidence' (restrict nothing, earn nothing). First-party consumers
    (scout tuner, evidence board, experiment judge, incubator) read the
    payload directly on their own cadences; this is the client for
    everyone else.
    """
    try:
        p = _load("fleet-proprioception", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        v = (p.get("verdicts") or {}).get(str(lever))
        vd = v.get("verdict") if isinstance(v, dict) else None
        return vd if vd in ("helping", "hurting", "neutral", "insufficient") \
            else None
    except Exception:
        return None


def long_entries_blocked(current_time=None):
    """L2 fleet-risk veto: True when the fleet's LONG book is at/over budget.

    Uses the side-specific count (long_positions vs long_budget), NOT the
    blended light, so a blown SHORT budget can't freeze long-only spot bots.
    Only enforces when fleet_risk publishes mode='enforce' — flipping the
    service's FLEET_RISK_MODE env to 'advisory' is the central kill switch,
    no strategy redeploy needed. Stale/missing payload -> False (never
    dead-man-switch the whole fleet on a publisher outage).
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("mode")) != "enforce":
            return False
        return int(p.get("long_positions", 0)) >= int(p.get("long_budget", 10**9))
    except Exception:
        return False


def entry_regime_gated(bot, entry_tag, current_time=None):
    """[2026-07-21 BRAIN ACTS] True when the brain has an ACTIONABLE
    regime_timing finding for (bot, entry_tag) AND the regime oracle
    currently reads risk-off — i.e. the exact condition under which this
    tag's losses were measured to cluster (counter_share >= 0.7, streak-
    hardened across PROMOTE_RUNS brain runs before it ever acts).

    Restrict-only (can only SKIP a new entry, never take one), and the gate
    lifts by itself two ways: the oracle turns risk-on (condition ends), or
    the finding retires from the hypothesis ledger (evidence faded). Uses
    the SAME oracle signal the diagnosis measured (`fleet.read` risk-off) —
    never a different regime proxy (the SPY-vs-btc_regime_up lesson).

    Fail-safe OPEN everywhere: stale/missing brain payload, actions_mode !=
    'enforce' (BRAIN_ACTIONS_MODE=advisory is the central kill switch), no
    action for the pair, stale/missing oracle, or any parse error -> False.
    """
    try:
        p = _load("brain-diagnosis", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("actions_mode")) != "enforce":
            return False
        act = ((p.get("actions") or {}).get(str(bot)) or {}).get(str(entry_tag))
        if not act or act.get("action") != "regime_gate":
            return False
        o = _load("regime-oracle", current_time)
        if not o or not is_fresh(o, current_time):
            return False
        return str((o.get("fleet") or {}).get("read") or "").startswith("risk-off")
    except Exception:
        return False


def oracle_asset_regimes(current_time=None):
    """{sym: verdict} for every pair the regime oracle currently grades, or
    {} when the oracle is dark/stale/absent/malformed.

    [2026-07-30 PER-ASSET GATE — item-18 step 2, operator call] The ONE
    supported read for a per-asset regime consumer (first: the family bot's
    non-crypto gate). Verdicts are the oracle's own strings (LONG-window /
    SHORT-window / dir-flat / chop-gated), passed through untouched.
    Standard accessor fail-safe: any doubt -> {}. NOTE the consumer-side
    rule for NON-CRYPTO entries is fail-CLOSED (a missing sym in this map
    means NO entry — never a BTC fallback); that rule lives at the
    consumer, because this accessor cannot know which symbols a caller
    needs. Crypto consumers keep their own validated gates and should not
    read this.
    """
    try:
        p = _load("regime-oracle", current_time)
        if not p or not is_fresh(p, current_time):
            return {}
        out = {}
        for sym, v in (p.get("pairs") or {}).items():
            vd = v.get("verdict") if isinstance(v, dict) else None
            if isinstance(vd, str) and vd:
                out[str(sym)] = vd
        return out
    except Exception:
        return {}


def long_symbol_blocked(base, current_time=None):
    """[2026-07-21 PER-SYMBOL PILEUP CAP] True when opening ANOTHER long on
    `base` would stack past the fleet's per-symbol cap.

    Companion to long_entries_blocked with the identical contract: enforces
    ONLY when fleet_risk publishes symbol_cap.mode='enforce', restrict-only,
    and fail-safe OPEN — stale/missing payload, absent block, cap<=0, or any
    parse error all return False. [2026-07-22] The published default is now
    ENFORCE — the operator made the review call ("can we fix the budget
    saturation") after (bw) re-measured saturation worse (red 55.9%/48h,
    16/20 slots on 5 symbols); FLEET_SYMBOL_CAP_MODE=advisory on the
    fleet-risk service is the kill switch, and FLEET_RISK_MODE=advisory
    stays SENIOR (a stood-down risk layer publishes the cap as advisory).
    Rationale measured over 168h: 20 long slots behaving as ~7.7 independent
    bets; true LONG-side 4-stacks in ~8.7% of samples (the first-draft 37.1%
    was side-blind — corrected same day; see fleet_risk.py) — de-pileup
    frees budget without raising gross. Wired consumer: the family bot
    (lighter_family_bot.symcap_state/symcap_blocked — same payload plus
    in-cycle stacking awareness across its seven books). Review caution, on
    record from the verify pass and STILL HONOURED: do NOT wire the shadow
    TAKER to this cap — its book is the lens-grading instrument, and
    crowding-capped entries would starve the episode floors and skew the
    live-vs-shadow baselines that steer real money. Family/strategy lanes
    only.
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        sc = p.get("symbol_cap") or {}
        if str(sc.get("mode")) != "enforce":
            return False
        cap = int(sc.get("cap") or 0)
        if cap <= 0:
            return False
        held = (sc.get("long_by_symbol") or {}).get(str(base).split("/")[0], 0)
        return int(held) >= cap
    except Exception:
        return False


def scout_universe(min_vol_m=0.0, limit=None, current_time=None):
    """[2026-07-30 FLEET UNIVERSE — operator: "full universe ... every bot
    needs every tool"] The venue's LIVE tradable universe, as the market
    scout sees it: `[sym, ...]` ordered by 24h $volume descending, filtered
    to `min_vol_m` ($M) and truncated to `limit`.

    WHY THIS EXISTS. Books carried hand-typed watchlists written when
    Lighter was much smaller — Counterweight ranked 30 of 202 books (15%),
    Snap Back 16 (8%), Tide Rider 6, Index Rider 3.

    [2026-07-30 (hk) WHO ACTUALLY CONSUMES THIS — the earlier text implied all
    four did.] Shipped consumers: lighter_dislocation_bot (Snap Back),
    lighter_funding_spread_bot (Counterweight) and, since (hk),
    lighter_trend_bot (Tide Rider, 6 -> 16 measured on the live bus).
    lighter_index_bot (Index Rider) STILL DOES NOT: its signal comes from
    Yahoo equity dailies, not Lighter candles, so a scout-added book without a
    verified YAHOO_REF mapping would publish nulls behind a log warning. Its
    universe is 10 of the venue's 94 non-crypto books and widening it is a
    separate job with its own prerequisite.

    A ranked selector cannot pick a winner it never sees, and unlike loosening a gate,
    enlarging the candidate set does not weaken the selection rule at all:
    Counterweight still takes its top-K/bottom-K, just from a real
    cross-section. The scout already scans every book each cycle, so this
    is a read of work already done — no extra venue load.

    Standard accessor fail-safe: dark/stale/malformed scout -> `[]`, and
    EVERY caller must treat `[]` as "keep my configured list", never as
    "trade nothing". Delisted symbols are excluded (the scout publishes
    them); that is the one filter applied here rather than at the consumer,
    because trading a delisted book is never what any caller wants.
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return []
        # `vols` is the public $M map (2026-07-30). `_marks` is the scout's
        # private diff base, {sym: [qvol, oi]} in raw $ — read as a FALLBACK
        # only, so a consumer shipped ahead of the scout's next deploy still
        # sees the universe instead of going quietly dark.
        vols = p.get("vols")
        if not isinstance(vols, dict) or not vols:
            vols = {}
            for sym, row in (p.get("_marks") or {}).items():
                try:
                    vols[sym] = float(row[0]) / 1e6
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
        if not vols:
            return []
        dead = {str(s) for s in (p.get("delisted") or [])}
        floor = float(min_vol_m or 0.0)
        rows = []
        for sym, vol in vols.items():
            if str(sym) in dead:
                continue
            try:
                vol = float(vol)
            except (TypeError, ValueError):
                continue
            if vol >= floor:
                rows.append((vol, str(sym)))
        rows.sort(reverse=True)
        out = [s for _, s in rows]
        if limit is not None and int(limit) > 0:
            out = out[:int(limit)]
        return out
    except Exception:
        return []


def scout_funding(current_time=None):
    """{sym: apr_pct} — the scout's venue-wide funding map (annualised %,
    signed: positive = longs pay shorts). `{}` on any doubt.

    The single supported read for "what is funding doing across the whole
    venue", so a book no longer has to fetch what the scout already has.
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return {}
        f = p.get("funding")
        if not isinstance(f, dict):
            return {}
        out = {}
        for sym, apr in f.items():
            try:
                out[str(sym)] = float(apr)
            except (TypeError, ValueError):
                continue
        return out
    except Exception:
        return {}


def venue_stress_bps(current_time=None):
    """The scout's venue premium stress in bps, or None when unreadable.

    Same number the Ticket Taker's stress veto reads, so any book can crouch
    on the SAME evidence instead of inventing its own. None = no opinion;
    consumers must fail OPEN on it (a dark scout must never halt a book).
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        st = p.get("stress")
        if isinstance(st, dict):
            # the scout's own key is `med` (see lighter_market_scout.stress);
            # the *_bps aliases are accepted so a future rename cannot
            # silently turn this into a permanent None.
            for k in ("med", "med_bps", "median_bps", "bps"):
                if st.get(k) is not None:
                    return float(st[k])
            return None
        return float(st) if st is not None else None
    except Exception:
        return None


if __name__ == "__main__":
    # offline selftest: prime the cache directly, exercise the fail-safe
    # contract (no DB touched)
    _now = datetime.now(timezone.utc)
    _fresh_p = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 2700,
                "verdicts": {"taker.dip_range": {"verdict": "hurting"},
                             "scout.dip_range_max": {"verdict": "helping"},
                             "weird": {"verdict": "banana"}}}
    _cache["fleet-proprioception"] = {"ts": _now, "payload": _fresh_p}
    assert lever_outcome("taker.dip_range", _now) == "hurting"
    assert lever_outcome("scout.dip_range_max", _now) == "helping"
    assert lever_outcome("taker.tp", _now) is None, "unknown lever -> None"
    assert lever_outcome("weird", _now) is None, "unknown verdict value -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": dict(
        _fresh_p, updated="2020-01-01T00:00:00+00:00")}
    assert lever_outcome("taker.dip_range", _now) is None, "stale -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": None}
    assert lever_outcome("taker.dip_range", _now) is None, "absent -> None"

    # [2026-07-21] per-symbol pileup cap accessor: fail-safe open everywhere
    _risk = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 900,
             "symbol_cap": {"cap": 3, "mode": "enforce",
                            "long_by_symbol": {"ETH": 3, "LTC": 2}}}
    _cache["fleet-risk"] = {"ts": _now, "payload": _risk}
    assert long_symbol_blocked("ETH", _now) is True, "at cap + enforce -> True"
    assert long_symbol_blocked("ETH/USDT", _now) is True, "base-normalizes"
    assert long_symbol_blocked("LTC", _now) is False, "under cap -> False"
    assert long_symbol_blocked("BTC", _now) is False, "unheld -> False"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], mode="advisory"))}
    assert long_symbol_blocked("ETH", _now) is False, "advisory -> inert"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], cap=0))}
    assert long_symbol_blocked("ETH", _now) is False, "cap 0 -> disabled"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, updated="2020-01-01T00:00:00+00:00")}
    assert long_symbol_blocked("ETH", _now) is False, "stale -> open"
    _cache["fleet-risk"] = {"ts": _now, "payload": None}
    assert long_symbol_blocked("ETH", _now) is False, "absent -> open"

    # [2026-07-21 BRAIN ACTS] entry_regime_gated: gates ONLY when the brain's
    # streak-hardened action exists AND the oracle reads risk-off right now
    _diag = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
             "actions_mode": "enforce",
             "actions": {"freqtrade-georgia-lshadow":
                         {"long-trend-breakout": {"action": "regime_gate"}}}}
    _orc_off = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 14400,
                "fleet": {"read": "risk-off downtrend"}}
    _orc_on = dict(_orc_off, fleet={"read": "risk-on uptrend"})
    _cache["brain-diagnosis"] = {"ts": _now, "payload": _diag}
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is True, "action + risk-off -> gated"
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-range-on",
                              _now) is False, "no action for tag -> open"
    assert entry_regime_gated("freqtrade-mum-lshadow", "long-trend-breakout",
                              _now) is False, "no action for bot -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_on}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "risk-on -> gate lifts"
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(
        _orc_off, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale oracle -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, actions_mode="advisory")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "advisory kill switch -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale brain -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": None}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "absent brain -> open"

    # [2026-07-30 PER-ASSET GATE] oracle_asset_regimes: verdict map passes
    # through fresh; junk rows skipped; stale/absent -> {} (the consumer
    # fails CLOSED on a missing sym — pinned at the family bot's selftest)
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(_orc_off, pairs={
        "SPY": {"verdict": "LONG-window", "class": "equity-index"},
        "XAU": {"verdict": "SHORT-window", "class": "commodity"},
        "BTC": {"verdict": "chop-gated", "class": "crypto"},
        "JUNK": "not-a-dict", "EMPTY": {}, "NONE": {"verdict": None}})}
    assert oracle_asset_regimes(_now) == {
        "SPY": "LONG-window", "XAU": "SHORT-window", "BTC": "chop-gated"}, \
        "fresh pairs pass through; junk/verdictless rows are skipped"
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(
        _orc_off, pairs={"SPY": {"verdict": "LONG-window"}},
        updated="2020-01-01T00:00:00+00:00")}
    assert oracle_asset_regimes(_now) == {}, "stale oracle -> {}"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    assert oracle_asset_regimes(_now) == {}, "no pairs block -> {}"
    _cache["regime-oracle"] = {"ts": _now, "payload": None}
    assert oracle_asset_regimes(_now) == {}, "absent oracle -> {}"

    # [2026-07-21 TWO-WAY MULTS] the clamp passes expand values and still
    # bounds both directions
    _mults = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
              "mults": {"freqtrade-avo-maria-lshadow":
                        {"long-swing-dip": {"mult": 1.25},
                         "long-big": {"mult": 2.0},
                         "long-bad": {"mult": 0.25}}}}
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-swing-dip",
                            _now) == 1.25, "expand mult passes the clamp"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-big",
                            _now) == 1.5, "over-ceiling clamps to 1.5"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-bad",
                            _now) == 0.5, "under-floor clamps to 0.5"
    # [2026-07-30 FLEET UNIVERSE] scout accessors: shape, ordering, the
    # volume floor, delist exclusion, and the fail-safe EMPTY that every
    # caller must read as "keep my configured list".
    _scout = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 900,
              "vols": {"BTC": 120.0, "SOL": 30.0, "TINY": 0.2, "DEAD": 99.0,
                       "JUNK": "x"},
              "delisted": ["DEAD"],
              "funding": {"BTC": 10.5, "SOL": -3.0, "BAD": "x"},
              "stress": {"n": 98, "max": 50.3, "med": 3.8, "p90": 19.3}}
    _cache["lighter-market"] = {"ts": _now, "payload": _scout}
    assert scout_universe(current_time=_now) == ["BTC", "SOL", "TINY"], \
        "vol-descending, delisted dropped, junk rows skipped"
    assert scout_universe(min_vol_m=1.0, current_time=_now) == ["BTC", "SOL"], \
        "volume floor applied"
    assert scout_universe(limit=1, current_time=_now) == ["BTC"], "limit applied"
    assert scout_funding(_now) == {"BTC": 10.5, "SOL": -3.0}, \
        "funding map coerced, unparseable dropped"
    # the scout's real key is `med` — this assertion is what would have
    # caught the first cut of this accessor, which read a `med_bps` that
    # does not exist and returned None against every real payload.
    assert venue_stress_bps(_now) == 3.8, "stress read from the scout's own `med`"
    # `_marks` FALLBACK: a scout that has not yet redeployed publishes no
    # `vols`, and the consumer must still see the universe (raw $ -> $M).
    _old = {k: v for k, v in _scout.items() if k != "vols"}
    _old["_marks"] = {"BTC": [120e6, 1.0], "SOL": [30e6, 2.0], "BAD": ["x", 0]}
    _cache["lighter-market"] = {"ts": _now, "payload": _old}
    assert scout_universe(current_time=_now) == ["BTC", "SOL"], \
        "pre-deploy scout: _marks fallback keeps the consumer alive"
    _cache["lighter-market"] = {"ts": _now, "payload": _scout}
    # fail-safe: a STALE scout must return neutral-empty, never a partial
    # universe — a book widened onto this accessor falls back to its own
    # configured list, it does not stop trading.
    _stale = dict(_scout)
    _stale["updated"] = (_now - timedelta(hours=3)).isoformat(timespec="seconds")
    _cache["lighter-market"] = {"ts": _now, "payload": _stale}
    assert scout_universe(current_time=_now) == [] and scout_funding(_now) == {}
    assert venue_stress_bps(_now) is None, "stale scout has NO opinion on stress"
    _cache["lighter-market"] = {"ts": _now, "payload": None}
    assert scout_universe(current_time=_now) == [] and scout_funding(_now) == {}
    assert venue_stress_bps(_now) is None

    print("fleet_bus selftest OK (lever_outcome fresh/unknown/stale/absent; "
          "long_symbol_blocked enforce/advisory/cap0/stale/absent; "
          "entry_regime_gated act+off/no-tag/no-bot/risk-on/stale-oracle/"
          "advisory/stale-brain/absent; "
          "oracle_asset_regimes fresh/junk-skip/stale/no-pairs/absent)")
