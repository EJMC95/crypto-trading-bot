#!/usr/bin/env python3
"""
fleet_risk.py — CROSS-BOT LAYERS 2+3 (ADVISORY): the fleet-level view no
single bot has.

[2026-07-07] Built from CROSS_BOT_INTELLIGENCE_DESIGN_2026-07-07.md.

LAYER 2 — FLEET RISK TRAFFIC LIGHT
  The scar this exists for: one July dip saw 26 same-direction crypto
  positions across three bots — every bot inside its own rules, the FLEET
  massively concentrated. This service reads every bot's live row in
  bot_pnl, counts directional crypto exposure fleet-wide, and publishes a
  traffic light + per-pair concentration to bot_state "fleet-risk".
  [2026-07-14 ENFORCEMENT REVIEW — the one scheduled in the 07-07 design]
  After the advisory week, mode is now "enforce": the freqtrade strategies
  veto NEW long entries in confirm_trade_entry (via fleet_bus.long_entries_
  blocked) when long_positions >= long_budget. Side-specific on purpose —
  the veto keys off the LONG count, not the blended light, so a blown short
  budget can never freeze the long-only spot bots. Existing positions and
  exits are never touched. Central kill switch: set FLEET_RISK_MODE=advisory
  on this service and every consumer goes neutral within its cache TTL —
  [2026-07-17 IMB-16] made TRUE at the publish side: advisory mode now also
  publishes clip_scale=1.0 (the governor's raw value stays visible as
  clip_scale_raw), because the clip consumers (taker, family) never checked
  mode and would have kept down-scaling through a thrown kill switch.
  (This file also folds in the 07-09 gate0 venue-aware counting —
  authoritative_row live-Lighter > paper — which main had missed.)

LAYER 3 — SIGNAL BUS
  Mirrors the fleet's scanner exhaust into one consumable key,
  bot_state "signal-bus": hottest funding APRs (funding-carry already
  fetches them), cross-exchange dislocation width (stress/vol signal),
  triangular-arb spread depth, market-pulse mood/panic. Traders will read
  these as entry FILTERS in the wiring step; publishing first makes the
  filter design measurable before it goes live.

Both payloads carry `updated` + `ttl_sec`; consumers must ignore stale data
(fail-safe contract, same as the regime oracle).

Run-once process; run_all.sh loops it every 5 min. Guarded end-to-end:
no DATABASE_URL -> silent no-op; any single bot's weird extra -> skipped.
"""

import json
import os
from datetime import datetime, timezone

import bot_pnl_store as store

RISK_KEY = "fleet-risk"
BUS_KEY = "signal-bus"
TTL_SEC = 900
# [2026-07-14] "enforce" = strategies honor the long-budget veto (fleet_bus).
# Flip to "advisory" on the Railway service to stand the whole layer down.
MODE = os.environ.get("FLEET_RISK_MODE", "enforce").strip().lower()

# [2026-07-14 GHOST-EXPOSURE FIX] bot_pnl rows outlive their bots: a
# decommissioned service (Bounce Catcher, stopped 12 Jul) leaves its last row
# frozen — open positions included — and this service was counting them
# forever (the light sat RED at 32L for hours on 22 phantom longs from two
# retired rows the dashboard no longer even displays). Rows older than this
# are now ignored everywhere: exposure counting AND the signal-bus mirrors
# (a frozen scanner row must not keep republishing last week's dislocation).
# Running bots publish every 1-10 min, so 30 min is generous; consumers
# fail-safe on absence, per the standing bus contract. This filter is a
# PREREQUISITE for wiring the RED entry veto — enforcement off a
# ghost-inflated light would throttle live bots for positions nobody holds.
# [2026-07-15 AUDIT FIX] raised 1800 -> 3900: the LIVE Tide Rider book
# publishes once per LOOP_SECONDS=3600, so at 30 min it flickered out of the
# light every cycle and its real-money position went uncounted half the time.
# 65 min still catches a genuinely dead publisher within ~1 loop.
STALE_ROW_SEC = 3900
CARRY_MAX_SEC = 86400   # dd-governor equity carry-forward expires after 24h


def row_fresh(r):
    """True if this bot_pnl row was updated within STALE_ROW_SEC."""
    ts = (r or {}).get("updated_at")
    if not ts:
        return False
    try:
        upd = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return False
    if upd.tzinfo is None:
        upd = upd.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - upd).total_seconds() <= STALE_ROW_SEC


def state_fresh(payload):
    """True if a bot_state payload self-reports as CURRENT (updated + ttl_sec).

    [2026-07-17] row_fresh() above is for bot_pnl rows and applies a fixed
    STALE_ROW_SEC. bot_state payloads carry their OWN contract — "every payload
    carries updated+ttl_sec; consumers go NEUTRAL on stale data" — so honour the
    publisher's TTL rather than a heuristic. Fails CLOSED: an unparseable or
    missing clock is stale, never fresh. (A fresh-but-wrong artifact is the
    failure class fleet_immune exists for; a stale-read-as-current one is what
    drove the 15-Jul false live down-scale off a 39h-old payload.)
    """
    try:
        upd = datetime.fromisoformat(
            str((payload or {})["updated"]).replace("Z", "+00:00"))
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - upd).total_seconds()
        return 0 <= age <= float((payload or {}).get("ttl_sec") or 0)
    except Exception:  # noqa: BLE001
        return False

# Directional crypto books only. Funding-carry is delta-neutral (excluded),
# sniper is event-class (tracked as gross info only), stocks are a separate
# mandate, scanners hold nothing. Freqtrade -lshadow twins are separate $1k
# modelled books (counted only via the info_only shadow tallies, never the
# light). [2026-07-14] Retired bots removed (the dashboard RETIRED_ROWS set):
# crypto-trendmomo-4h + perps-regime-switch dropped from this list, and the
# whole perps long/short cohort (Bounce Catcher decommissioned 12 Jul, Trail
# Blazer retired) — their frozen rows were the ghost-exposure RED. Their
# bot_pnl rows are pruned by cleanup_legacy_bots.py on boot; if one is ever
# revived, re-add it here.
# [2026-07-14 KRAKEN RETIREMENT] The Kraken paper rows are retired; each base
# resolves via authoritative_row to live Lighter > -lshadow (the fleet's
# modelled books now) > legacy paper. The light therefore tracks the LIGHTER
# fleet — documented change of meaning: shadow books are modelled capital,
# but they ARE the fleet being managed, and the pileup scar applies to
# whatever cohort trades one beta. Ticket Taker (scout-driven shadow book)
# is counted too — its open_pos extra is fleet_risk-shaped.
FREQTRADE_BOTS = ["crypto-trend-daily", "crypto-intraday-15m", "crypto-swing-daily",
                  "crypto-breakout-4h", "freqtrade-mum",
                  "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia",
                  "lighter-ticket-taker"]
# [2026-07-15 AUDIT FIX] the LIVE Funding Farmer (perps-funding-lighter) is
# directional-funding — it HOLDS one-sided positions (the side that receives
# funding), so real money was counted in NO cohort after the 14-Jul sweep
# emptied this list. Its longs/shorts derive from extra.held when absent.
PERPS_LS_BOTS = ["perps-funding-lighter"]

# [2026-07-09 LIGHTER GO-LIVE — no-miss-sync] When a bot trades on Lighter it
# publishes as <bot>-lighter (real money) / -lshadow (modelled) / -ltest. The
# fleet-risk light must count the REAL Lighter positions, not the superseded
# paper twin — otherwise the live Lighter book is invisible to the fleet view
# (the exact desync going live creates). Resolve each directional bot to its
# authoritative row: prefer live Lighter > paper; shadow/testnet are tracked
# separately as info (modelled, not real capital).
def _fresh(row):
    return bool(row) and (row.get("equity") is not None or row.get("open_trades") is not None)


def authoritative_row(base, by_bot):
    """(row, venue) for a directional bot, one row so nothing double-counts:
    live Lighter (real money) > -lshadow (the fleet's modelled Lighter books,
    post-Kraken-retirement) > legacy paper (transition fallback while the old
    services wind down). Every candidate must be FRESH — a frozen row of any
    venue must never shadow a running one."""
    for suffix, venue in (("-lighter", "lighter_live"),
                          ("-lshadow", "lighter_shadow"),
                          ("", "hl_paper")):
        r = by_bot.get(base + suffix)
        if _fresh(r) and row_fresh(r):
            return r, venue
    return None, None

# Fleet budgets (positions, count-based v1 — inverse-vol weighting is a later
# refinement once this has advisory history to calibrate against).
LONG_BUDGET = 20
SHORT_BUDGET = 12
YELLOW_FRAC = 0.7

# [2026-07-15 EXPOSURE VIEW] The light counts HOW MANY positions; this says
# HOW MANY BETS they really are (EVIDENCE_AND_LEARNING_REVIEW follow-up: 23
# open longs that are all crypto beta on one venue is ~one trade, and nothing
# said so). Advisory publish-only, same doctrine as every layer before it:
# per-symbol pileup, effective independent-bet count (1/Herfindahl), and a
# crypto-vs-equity-perp cluster split. Symbol classification is a curated
# equity-base set (Lighter's stock perps), env-extensible without a deploy;
# a miss just shifts the advisory split, never the light.
# Ambiguity policy: symbols that collide with crypto tickers (e.g. LIT)
# stay CRYPTO — a miss only shifts the advisory split. US100/US500/SOXL
# spotted holding in the first live replay (15-Jul).
EQUITY_BASES = {s.strip().upper() for s in os.environ.get(
    "FLEET_EQUITY_BASES",
    "SPY,QQQ,US100,US500,SOXL,AMD,MU,HOOD,RKLB,TSLA,NVDA,AAPL,MSFT,META,"
    "GOOGL,GOOG,AMZN,COIN,MSTR,PLTR,TSM,INTC,SKHYNIX,AMAT,EWY,LITE,CRCL,"
    "BMNR").split(",") if s.strip()}


def held_items(held):
    """Normalize a publisher's extra.held to (symbol, marker) pairs. Two
    shapes exist in the wild: the funding bots publish {coin: 'L'/'S'} and
    the family books {coin: tag}, but the LIVE trend bot (and the equities
    ports) publish a plain LIST of coins — sorted(meta.keys()). [2026-07-15b
    HOTFIX] the exposure harvest assumed .items() and crashed fleet_risk on
    Tide Rider's live row, freezing the light (consumers fail open — the
    long-budget veto went dark). List entries carry no side marker -> ''
    (classified long, correct for the long-only publishers of that shape)."""
    if isinstance(held, dict):
        return list(held.items())
    return [(c, "") for c in (held or [])]


def exposure_concentration(positions, uncovered=0):
    """Advisory concentration view over the SAME directional cohort the light
    counts. `positions` is [(bot, base_symbol, side)] where side is
    'long'/'short'; `uncovered` counts light-cohort positions whose publisher
    exposes no symbol detail (honesty metric — the view only claims what it
    can see). Pure; unit-tested via --selftest."""
    longs = [(b, str(s).upper()) for b, s, side in positions if side == "long"]
    shorts = [(b, str(s).upper()) for b, s, side in positions if side == "short"]
    by_sym = {}
    for _, s in longs:
        by_sym[s] = by_sym.get(s, 0) + 1
    n = len(longs)
    hhi = sum((c / n) ** 2 for c in by_sym.values()) if n else 0.0
    top = sorted(by_sym.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    eq_n = sum(c for s, c in by_sym.items() if s in EQUITY_BASES)
    return {
        "long_n": n, "short_n": len(shorts),
        "sym_uncovered": int(uncovered),
        "long_distinct": len(by_sym),
        # 1/HHI — "the longs behave like this many independent symbol bets".
        "long_effective_n": round(1.0 / hhi, 1) if hhi > 0 else 0.0,
        "long_max_symbol": top[0][0] if top else None,
        "long_max_share": round(top[0][1] / n, 2) if n else None,
        "long_crypto": n - eq_n, "long_equity": eq_n,
        "long_by_symbol": dict(top),
    }

# [2026-07-14b DRAWDOWN GOVERNOR] The missing risk leg: individual bots have
# seatbelts, but nothing said "the whole fleet is bleeding — shrink". This
# publishes a fleet-level 7-day equity drawdown and a clip_scale every run:
# 1.0 normally, 0.5 past DD_HALF, 0.25 past DD_QUARTER. Ticket Taker consumes
# it (scales its clips); for the gate0 books it is advisory until ported.
# Equity cohort = the same authoritative rows the light counts. Samples are
# kept inside this service's own state (>=30 min apart, 7-day window) so the
# governor survives redeploys without touching bot_state_history.
DD_HALF = float(os.environ.get("FLEET_DD_HALF", "-0.05"))
DD_QUARTER = float(os.environ.get("FLEET_DD_QUARTER", "-0.10"))
DD_SAMPLE_GAP_SEC = 1800
DD_WINDOW_SEC = 7 * 24 * 3600
# [2026-07-17 IMB-02] minimum sample-window SPAN before the governor asserts
# a drawdown number at all. A freshly-reset window computed dd=0.0 off one
# sample — and 0.0 is "not None", so it sailed through the evidence board's
# deliberately fail-closed dd leg on the real-money up-ladder. Below the
# span the governor abstains: dd=None (consumers' conservative sides bite),
# clip_scale 1.0. DELIBERATE trade (verify-reviewed): for up to 6h after a
# GENUINE cohort reset the governor is tighten-blind on the shadow-clip
# lane (the old code could re-trip DD_HALF off a sub-6h window; the pool is
# ~$8k paper + <$100 real, per-bot seatbelts + the board's ledger-anchored
# DOWN reflex stay active) — the dual of closing the fake-0.0 hole that
# passed the REAL-money up-gate. On the 21-Jul review agenda.
DD_MIN_SPAN_SEC = float(os.environ.get("FLEET_DD_MIN_SPAN_SEC", str(6 * 3600)))


def dd_governor(samples, fleet_equity, now_dt):
    """(new_samples, dd_frac, clip_scale) — pure, unit-tested.

    `samples` is [[iso_ts, equity], ...] oldest-first. Appends the current
    reading if the newest sample is >= DD_SAMPLE_GAP_SEC old, trims to the
    7-day window, and computes drawdown vs the window peak (current reading
    included, so a fresh peak means dd == 0)."""
    out = []
    for ts, eq in samples or []:
        try:
            age = (now_dt - datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                   ).total_seconds()
            if 0 <= age <= DD_WINDOW_SEC:
                out.append([ts, float(eq)])
        except (ValueError, TypeError):
            continue
    if fleet_equity and fleet_equity > 0:
        if not out:
            out.append([now_dt.isoformat(timespec="seconds"), fleet_equity])
        else:
            last_age = (now_dt - datetime.fromisoformat(
                str(out[-1][0]).replace("Z", "+00:00"))).total_seconds()
            if last_age >= DD_SAMPLE_GAP_SEC:
                out.append([now_dt.isoformat(timespec="seconds"), fleet_equity])
    if not fleet_equity or fleet_equity <= 0 or not out:
        return out, None, 1.0
    # thin window -> abstain (dd None), never a fake 0.0 (IMB-02)
    try:
        span = (datetime.fromisoformat(str(out[-1][0]).replace("Z", "+00:00"))
                - datetime.fromisoformat(str(out[0][0]).replace("Z", "+00:00"))
                ).total_seconds()
    except (ValueError, TypeError):
        span = 0.0
    if span < DD_MIN_SPAN_SEC:
        return out, None, 1.0
    peak = max(max(eq for _, eq in out), fleet_equity)
    dd = fleet_equity / peak - 1.0
    scale = 0.25 if dd <= DD_QUARTER else (0.5 if dd <= DD_HALF else 1.0)
    return out, round(dd, 4), scale


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def light_for(n, budget):
    if n >= budget:
        return "red"
    if n >= YELLOW_FRAC * budget:
        return "yellow"
    return "green"


def governed_clip_scale(raw, mode):
    """(published, raw) clip_scale after the central kill switch.

    [2026-07-17 IMB-16] FLEET_RISK_MODE=advisory is SENIOR and releases the
    drawdown governor's clip actuator too — not just the long-budget veto. The
    published value goes to 1.0 in any non-enforce mode (consumers size at full
    clip), while `raw` keeps the governor's value for display/forensics. This is
    the one place all clip consumers read, so the release lives here. Extracted
    from main() so the contract is unit-tested (it drove real money before it
    had a test)."""
    return (raw if mode == "enforce" else 1.0), raw


def main():
    rows = store.fetch_bot_pnl()
    if rows is None:
        print(f"[fleet-risk] {now_iso()} no DB — skipped")
        return
    by_bot = {r["bot"]: r for r in rows}

    fleet_long, fleet_short = 0, 0
    fleet_equity = 0.0
    equity_by_bot, equity_venue = {}, {}
    per_bot, pair_count, venues_seen = {}, {}, {}
    expo, expo_uncovered = [], 0   # [2026-07-15 EXPOSURE VIEW] (bot, base, side)
    for name in FREQTRADE_BOTS:
        r, venue = authoritative_row(name, by_bot)
        if not r:
            continue
        if r.get("equity") is not None:
            fleet_equity += float(r["equity"])   # governor cohort = light cohort
            equity_by_bot[name] = float(r["equity"])
            equity_venue[name] = venue
        n = int(r.get("open_trades") or 0)
        if n == 0:
            continue
        extra = r.get("extra") or {}
        pos = extra.get("open_pos") or []
        held = extra.get("held") or {}
        # entries are long unless the enter tag says otherwise
        longs = sum(1 for p in pos if "short" not in str(p.get("tag", "")).lower()) if pos else n
        shorts = (len(pos) - longs) if pos else 0
        fleet_long += longs
        fleet_short += shorts
        per_bot[name] = {"long": longs, "short": shorts, "venue": venue}
        if venue != "hl_paper":
            venues_seen[name] = venue
        # [2026-07-15 EXPOSURE VIEW] symbol harvest: open_pos (taker-shaped)
        # first, else extra.held (the gate0 family books publish {coin: tag})
        # — the family books were invisible to pair_concentration until now.
        # Family entry tags ('breakout', 'sma_fast_above_slow', ...) are
        # long-only; only an explicit 'S'/'short' marks a short.
        covered = 0
        for p in pos:
            base = str(p.get("pair", "")).split("/")[0]
            if base:
                side = "short" if "short" in str(p.get("tag", "")).lower() else "long"
                pair_count[base] = pair_count.get(base, 0) + 1
                expo.append((name, base, side))
                covered += 1
        if not pos:
            for coin, tag in held_items(held):
                base = str(coin).split("/")[0]
                if not base:
                    continue
                t = str(tag)
                side = "short" if (t.upper() == "S" or "short" in t.lower()) else "long"
                pair_count[base] = pair_count.get(base, 0) + 1
                expo.append((name, base, side))
                covered += 1
        expo_uncovered += max(0, longs + shorts - covered)
    for name in PERPS_LS_BOTS:
        r, venue = authoritative_row(name, by_bot)   # live Lighter > paper twin
        if not r or not row_fresh(r):
            continue
        if r.get("equity") is not None:
            fleet_equity += float(r["equity"])
            equity_by_bot[name] = float(r["equity"])
            equity_venue[name] = venue
        extra = r.get("extra") or {}
        # [2026-07-15 AUDIT FIX] Funding Farmer publishes held={'ETH':'S',...}
        # rather than longs/shorts ints — derive counts so live real-money
        # positions actually reach the light.
        held = extra.get("held") or {}
        _hv = [v for _, v in held_items(held)]   # list-shape tolerant (hotfix)
        longs = int(extra.get("longs") or 0) or \
            sum(1 for v in _hv if str(v).upper().startswith("L"))
        shorts = int(extra.get("shorts") or 0) or \
            sum(1 for v in _hv if str(v).upper().startswith("S"))
        if longs or shorts:
            fleet_long += longs
            fleet_short += shorts
            per_bot[name] = {"long": longs, "short": shorts, "venue": venue}
            venues_seen[name] = venue
            # [2026-07-15 EXPOSURE VIEW] harvest the L/S held map too, so the
            # live Funding Farmer's one-sided book joins the concentration view.
            covered = 0
            for coin, v in held_items(held):
                base = str(coin).split("/")[0]
                if not base:
                    continue
                t = str(v)
                side = "short" if (t.upper().startswith("S") or "short" in t.lower()) else "long"
                pair_count[base] = pair_count.get(base, 0) + 1
                expo.append((name, base, side))
                covered += 1
            expo_uncovered += max(0, longs + shorts - covered)

    # Shadow/testnet cohort — modelled, NOT real capital, so it never moves the
    # risk light; surfaced as info so the Lighter-cohort activity is still visible.
    shadow_long, shadow_short = 0, 0
    for base in PERPS_LS_BOTS:
        for suf in ("-lshadow", "-ltest"):
            e = (by_bot.get(base + suf) or {}).get("extra") or {}
            held = e.get("held") or {}
            _shv = [v for _, v in held_items(held)]   # list-shape tolerant, like the live tally
            shadow_long += int(e.get("longs") or 0) or \
                sum(1 for v in _shv if str(v).upper().startswith("L"))
            shadow_short += int(e.get("shorts") or 0) or \
                sum(1 for v in _shv if str(v).upper().startswith("S"))

    gross = fleet_long + fleet_short
    light = max(light_for(fleet_long, LONG_BUDGET),
                light_for(fleet_short, SHORT_BUDGET),
                key=["green", "yellow", "red"].index)

    # [2026-07-21 AUDIT FIX] EXPOSURE-ONLY extras: equities-regime (the
    # fleet's only dedicated equity book — the crypto/equity split this view
    # EXISTS for structurally could not see it: long_equity read 0 while
    # QQQ+SPY were held), the dislocation fader, and the six Parliament
    # books (they CONSUME the long-budget veto but contributed nothing to
    # any count). These join the ADVISORY exposure/pileup view only — the
    # BUDGET cohort (fleet_long above, the enforced veto) is unchanged:
    # redefining who the 20-slot budget covers changes what 20 means, and
    # that is a review decision, not an audit's (evidence filed on the
    # 21-Jul agenda). Same authoritative-row + freshness rules as the light.
    EXPOSURE_EXTRA_BOTS = ["equities-regime", "lighter-dislocation",
                           "pm-albanese", "pm-morrison", "pm-turnbull",
                           "pm-abbott", "pm-rudd", "pm-gillard"]
    for base in EXPOSURE_EXTRA_BOTS:
        row, _venue = authoritative_row(base, by_bot)
        if not row:
            continue
        held = ((row.get("extra") or {}).get("held")) or {}
        for coin, v in held_items(held):
            b = str(coin).split("/")[0]
            if not b:
                continue
            t = str(v)
            side = "short" if (t.upper().startswith("S")
                               or "short" in t.lower()) else "long"
            pair_count[b] = pair_count.get(b, 0) + 1
            expo.append((base, b, side))

    hot_pairs = {k: v for k, v in sorted(pair_count.items(),
                                         key=lambda kv: -kv[1]) if v >= 2}
    exposure = exposure_concentration(expo, uncovered=expo_uncovered)

    # [2026-07-21 PER-SYMBOL PILEUP CAP — advisory-first, N3 follow-through]
    # A week of 168h history (n=2,019) showed the 20-slot long budget binding
    # 41.5% of the time while behaving as only ~7.7 independent bets (1/HHI).
    # EVIDENCE CORRECTED same day by adversarial verify: the first-draft
    # "4-stacks in 37.1% of samples" was computed on side-blind hot_pairs —
    # the Farmer's live SHORTS were being counted into "long pileups" (ETH's
    # 4th position was a short, i.e. a partial HEDGE, the opposite of pileup
    # risk). On the honest LONG-side basis a true 4-stack existed in ~8.7%
    # of samples (~17% of red ones). The cap is therefore future-proofing
    # against a tail, not a frequent binder — kept because the budget, not
    # signal, still throttles entries (red 41.5%) and de-pileup beats a
    # bigger budget when it does bind. Design mirrors the long-budget veto:
    # this file only PUBLISHES; the only consumer surface is
    # fleet_bus.long_symbol_blocked(base), enforcing solely when
    # FLEET_SYMBOL_CAP_MODE=enforce (env default: advisory — zero behavior
    # change until a review flips it; restrict-only; fail-safe open, same
    # contract as long_entries_blocked).
    # hot_pairs mixes sides, so the cap counts the LONG side alone from expo.
    SYMBOL_CAP = int(os.environ.get("FLEET_SYMBOL_CAP", "3"))
    long_by_symbol = {}
    for _name, _base, _side in expo:
        if _side == "long":
            long_by_symbol[_base] = long_by_symbol.get(_base, 0) + 1
    symbol_cap = {
        "cap": SYMBOL_CAP,
        "mode": os.environ.get("FLEET_SYMBOL_CAP_MODE", "advisory"),
        # [2026-07-21 AUDIT FIX] publish every count that could BIND at this
        # cap (was a flat `v >= 2` noise filter): with FLEET_SYMBOL_CAP=1 a
        # symbol holding exactly 1 long was absent from the payload, so
        # long_symbol_blocked read held=0 < 1 and admitted the SECOND long —
        # the cap under-enforced by exactly one position at its tightest
        # setting. `min(2, cap)` keeps the noise filter at cap>=2.
        "long_by_symbol": {k: v for k, v in sorted(long_by_symbol.items(),
                                                   key=lambda kv: -kv[1])
                           if v >= min(2, SYMBOL_CAP)},
        "at_cap": sorted(b for b, c in long_by_symbol.items()
                         if SYMBOL_CAP > 0 and c >= SYMBOL_CAP),
    } if SYMBOL_CAP > 0 else {"cap": 0, "mode": "disabled",
                              "long_by_symbol": {}, "at_cap": []}

    sniper = by_bot.get("event-listing-sniper") or {}
    if not row_fresh(sniper):
        sniper = {}
    prev_state = store.load_state(RISK_KEY) or {}
    # [2026-07-15 AUDIT FIX] Outage guard for the drawdown governor: a bot
    # whose publisher went quiet must read as "publisher lost", not "equity
    # lost" — otherwise a container restart looks like a -12% fleet drawdown
    # and the governor shrinks clips for the wrong reason. Carry each missing
    # base's last-known equity forward (it decays out only when the whole
    # state is superseded by fresh reads).
    _prev_eq = prev_state.get("equity_by_bot") or {}
    _prev_cts = prev_state.get("equity_carry_ts") or {}
    _carried, _carry_ts = [], {}
    _now_dt = datetime.now(timezone.utc)
    for _base in FREQTRADE_BOTS + PERPS_LS_BOTS:
        if _base not in equity_by_bot and _base in _prev_eq:
            # [2026-07-15b VERIFIED FIX] carry EXPIRES: first miss starts a
            # 24h clock; past it the bot is genuinely gone and its equity
            # leaves the pool (the cohort key below resets the dd window, so
            # the drop can't read as a drawdown).
            _t0 = _prev_cts.get(_base) or _now_dt.isoformat(timespec="seconds")
            try:
                _age = (_now_dt - datetime.fromisoformat(
                    str(_t0).replace("Z", "+00:00"))).total_seconds()
            except (ValueError, TypeError):
                _age = 0.0
            if _age > CARRY_MAX_SEC:
                continue
            try:
                fleet_equity += float(_prev_eq[_base])
                equity_by_bot[_base] = float(_prev_eq[_base])
                # [2026-07-17 IMB-02] a carried base keeps its REAL venue in
                # the cohort key: the carried equity IS the same book at its
                # last reading, so like-for-like still holds — flipping the
                # key to "carried" wiped the 7d dd samples on every stale-flap
                # of a slow publisher (Tide Rider publishes hourly vs the
                # 65-min bar: 5-min slack), always landing on the RELEASE
                # side (dd -> None/0, clips 0.25 -> 1.0 mid-drawdown).
                equity_venue[_base] = ((prev_state.get("equity_venue") or {})
                                       .get(_base) or "carried")
                _carried.append(_base)
                _carry_ts[_base] = _t0
            except (TypeError, ValueError):
                continue
    # [2026-07-15b VERIFIED FIX] the dd window only compares LIKE WITH LIKE:
    # the sample series resets whenever the equity cohort changes — a live
    # book substituted by its $1k shadow (venue change), a bot list edit, or
    # an expired carry would otherwise read as a fake ±12% "drawdown" and pin
    # clip_scale at 0.25 for a week. True drawdown within a stable cohort is
    # unaffected.
    _cohort = "|".join(sorted(f"{b}:{equity_venue.get(b, '?')}"
                              for b in equity_by_bot))
    _samples_in = (prev_state.get("equity_samples")
                   if prev_state.get("equity_cohort") == _cohort else [])
    samples, dd_7d, clip_scale = dd_governor(
        _samples_in, fleet_equity, _now_dt)
    # [2026-07-17 G1 amendment — decided under delegated review authority]
    # BLIND-HOLD through the governor's thin-window abstain: while dd is
    # None (window below DD_MIN_SPAN_SEC) a PRIOR clip restriction (<1.0)
    # is held rather than snapped to 1.0 — same pattern as the board's
    # blind-cohort hold: assert-nothing on missing evidence must never
    # RELEASE an in-force restriction.
    # HONEST SCOPE (verify-corrected): this reads the prior clip regardless
    # of whether the equity COHORT matched, so a cohort change (which
    # empties the sample window -> dd None) INHERITS the old cohort's
    # restriction until >=6h of new samples accrue. That is deliberate and
    # restrict-only — a book that was being throttled keeps being throttled
    # while we are blind — but it means "a fresh cohort starts at 1.0" is
    # only true when there was NO prior restriction to inherit.
    if dd_7d is None:
        _prev_clip = prev_state.get("clip_scale_raw",
                                    prev_state.get("clip_scale"))
        try:
            if _prev_clip is not None and float(_prev_clip) < 1.0:
                clip_scale = float(_prev_clip)
        except (TypeError, ValueError):
            pass
    # [2026-07-17 IMB-16] the kill switch is SENIOR and now true at the one
    # place all clip consumers read: advisory mode publishes clip_scale=1.0
    # (raw kept for display/forensics).
    clip_scale, clip_scale_raw = governed_clip_scale(clip_scale, MODE)
    risk_payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC, "mode": MODE,
        "light": light,
        "fleet_equity": round(fleet_equity, 2),
        "fleet_dd_7d": dd_7d,
        "clip_scale": clip_scale,
        "clip_scale_raw": clip_scale_raw,   # pre-kill-switch governor value
        "equity_by_bot": {k: round(v, 2) for k, v in equity_by_bot.items()},
        "equity_cohort": _cohort,
        # persisted so a CARRIED base can keep its real venue in the cohort
        # key next cycle (IMB-02 — carry must not wipe the dd window)
        "equity_venue": equity_venue,
        "equity_carry_ts": _carry_ts,
        "equity_carried": _carried,      # bases riding on last-known equity
        "equity_samples": samples,
        "long_positions": fleet_long, "long_budget": LONG_BUDGET,
        "short_positions": fleet_short, "short_budget": SHORT_BUDGET,
        "gross": gross,
        "pair_concentration": hot_pairs,   # same base held by >=2 bots
        # [2026-07-15 EXPOSURE VIEW] how many independent bets the count is.
        "exposure": exposure,
        # [2026-07-21] per-symbol long pileup cap (advisory until the env
        # flips — see the SYMBOL_CAP block above; consumers go through
        # fleet_bus.long_symbol_blocked only).
        "symbol_cap": symbol_cap,
        "by_bot": per_bot,
        # [no-miss-sync] which venue each directional bot's REAL book is on, so
        # the risk view is explicit about counting live Lighter over paper.
        "bot_venue": venues_seen,
        "info_only": {"sniper_open": sniper.get("open_trades"),
                      "shadow_long": shadow_long, "shadow_short": shadow_short},
    }
    store.save_state(RISK_KEY, risk_payload)
    store.save_history(RISK_KEY, {"light": light, "long": fleet_long,
                                  "short": fleet_short, "gross": gross,
                                  "hot_pairs": hot_pairs,
                                  "fleet_equity": round(fleet_equity, 2),
                                  "fleet_dd_7d": dd_7d,
                                  "clip_scale": clip_scale,
                                  "exposure": {
                                      "eff_n": exposure["long_effective_n"],
                                      "crypto": exposure["long_crypto"],
                                      "equity": exposure["long_equity"],
                                      "max_share": exposure["long_max_share"],
                                      "unseen": exposure["sym_uncovered"]},
                                  # [2026-07-21] pileup-at-cap in history so
                                  # saturation DURATION is measurable next
                                  # review, not just the instantaneous view
                                  "sym_at_cap": symbol_cap["at_cap"]})

    # ---- Layer 3: signal bus -------------------------------------------
    bus = {"updated": now_iso(), "ttl_sec": TTL_SEC}

    def fresh_row(bot):
        r = by_bot.get(bot)
        return r if (r and row_fresh(r)) else None

    def fresh_extra(bot):
        r = fresh_row(bot)
        return (r.get("extra") or {}) if r else {}

    # [no-miss-sync] Funding rates GENUINELY differ across venues (Lighter vs HL
    # diverge — verified day-1). A Lighter-cohort entry filter must read LIGHTER
    # funding: prefer the Lighter-facing funding-carry row (live > shadow) over
    # the HL paper one, and tag the source so consumers know which venue it is.
    # Only FRESH rows qualify (a frozen live row must not outrank a running twin).
    fc_row = (fresh_row("perps-funding-carry-lighter")
              or fresh_row("perps-funding-carry-lshadow")
              or fresh_row("perps-funding-carry") or {})
    fc = fc_row.get("extra") or {}
    if fc.get("hottest_funding_apr"):
        bus["funding_hottest_apr"] = fc["hottest_funding_apr"]
        # [2026-07-21] absence of the venue stamp must never REPORT a venue:
        # the old default ("hyperliquid") printed a foreign venue on a
        # Lighter-only bus for 3+ days whenever a pre-contract container was
        # running (N4 — 277 of 288 trailing-24h snapshots said hyperliquid
        # right up to the 21-Jul redeploy). "unstamped" is a tell, not a lie.
        bus["funding_source"] = fc.get("venue") or "unstamped"
    # [2026-07-17 LIGHTER-ONLY — operator: "i only want things running on
    # lighter"] The Lighter venue premium now comes from the MARKET SCOUT, not
    # Gap Scout. Both read mark/index off the SAME Lighter endpoint, so this is
    # not a change of measurement — it is the same gauge from the better
    # publisher:
    #   * coverage: every LIQUID book (~200) vs Gap Scout's 6-symbol
    #     LIGHTER_WATCH (BTC,ETH,SOL,SPY,QQQ,XAU). A venue-wide stress median
    #     over 6 hand-picked books was never venue-wide.
    #   * agreement: it is already the source the Ticket Taker's stress veto
    #     trusts (`lighter-market`.stress.med). The bus and the veto now cite
    #     ONE number instead of two that could disagree.
    # Gap Scout itself is retired: its trade was CEX<->CEX arb with no Lighter
    # leg at all (its own line 201: "The CEX legs above say nothing about
    # Lighter"). `xexchange_dislocation_pct` and `tri_arb_best_depth_pct` retire
    # WITH their scanners — both were CEX gauges, and nothing outside this file
    # ever read them.
    # Shapes are preserved EXACTLY (the dashboard's signal-bus card formats
    # both keys): stress -> {med,max,n}; per-symbol -> {sym: bps}.
    _scout = store.load_state("lighter-market") or {}
    if state_fresh(_scout):
        _stress = _scout.get("stress") or {}
        if _stress.get("med") is not None:
            bus["lighter_venue_stress_bps"] = {"med": _stress.get("med"),
                                               "max": _stress.get("max"),
                                               "n": _stress.get("n")}
        # The books furthest from fair value — the ones a premium gauge is FOR.
        _outliers = {o["sym"]: o["prem_bps"]
                     for o in (_scout.get("prem_outliers") or [])
                     if o.get("sym") and o.get("prem_bps") is not None}
        if _outliers:
            bus["lighter_prem_bps"] = _outliers
    try:
        pulse = store.load_state("market-pulse") or {}
        latest = pulse.get("latest") or {}
        bus["pulse_mood"] = latest.get("mood")
        bus["pulse_panic"] = latest.get("panic")
    except Exception:
        pass
    store.save_state(BUS_KEY, bus)
    # [2026-07-07 day-zero review catch] historize the bus too — without this,
    # the Jul-14 enforcement review cannot judge Layer 3 against outcomes.
    store.save_history(BUS_KEY, bus)

    hp = ",".join(f"{k}x{v}" for k, v in list(hot_pairs.items())[:4]) or "none"
    _lv = ",".join(f"{k}:{v.replace('lighter_', '')}"
                   for k, v in venues_seen.items()) or "none-live"
    lstress = (bus.get("lighter_venue_stress_bps") or {}).get("med")
    print(f"[fleet-risk] {now_iso()} mode={MODE} light={light.upper()} "
          f"long={fleet_long}/{LONG_BUDGET} short={fleet_short}/{SHORT_BUDGET} "
          f"gross={gross} | equity={fleet_equity:.0f} dd7d={dd_7d} scale={clip_scale} "
          f"| bets: eff_n={exposure['long_effective_n']} "
          f"crypto={exposure['long_crypto']}L eq={exposure['long_equity']}L "
          f"top={exposure['long_max_symbol']}@{exposure['long_max_share']} "
          f"unseen={exposure['sym_uncovered']} "
          f"| live-venue: {_lv} | shadow(info) {shadow_long}L/{shadow_short}S "
          f"| funding_src={bus.get('funding_source')} | pair-pileups: {hp} "
          f"| mood={bus.get('pulse_mood')} panic={bus.get('pulse_panic')} "
          # [2026-07-17] dropped `dislocation=` — it was Gap Scout's CEX<->CEX
          # gauge and retired with it. lighter-stress is the venue gauge, and it
          # now covers every liquid book rather than 6.
          f"| lighter-stress={lstress}bps n={(bus.get('lighter_venue_stress_bps') or {}).get('n')}")


def selftest():
    """Offline checks for the pure functions (no DB). `--selftest`."""
    # held shapes seen in the wild: dict (funding/family), LIST (live trend
    # bot, equities ports — the 15-Jul crash), absent.
    assert held_items({"ETH": "S", "BTC": "L"}) == [("ETH", "S"), ("BTC", "L")]
    assert held_items(["BTC", "SOL"]) == [("BTC", ""), ("SOL", "")]
    assert held_items(None) == [] and held_items({}) == []
    # exposure: empty
    e = exposure_concentration([])
    assert e["long_n"] == 0 and e["long_effective_n"] == 0.0 and \
        e["long_max_symbol"] is None, e
    # exposure: pileup — 4 bots long SOL + 1 long ETH reads as ~1.5 real bets
    e = exposure_concentration(
        [("a", "SOL", "long"), ("b", "SOL", "long"), ("c", "SOL", "long"),
         ("d", "SOL", "long"), ("e", "ETH", "long")])
    assert e["long_n"] == 5 and e["long_distinct"] == 2, e
    assert e["long_max_symbol"] == "SOL" and e["long_max_share"] == 0.8, e
    assert e["long_effective_n"] == 1.5, e            # 1/(0.8^2+0.2^2)=1.47
    assert e["long_crypto"] == 5 and e["long_equity"] == 0, e
    # exposure: equity cluster + shorts + coverage honesty
    e = exposure_concentration(
        [("t", "SPY", "long"), ("t", "MU", "long"), ("f", "BTC", "short")],
        uncovered=2)
    assert e["long_equity"] == 2 and e["long_crypto"] == 0, e
    assert e["short_n"] == 1 and e["sym_uncovered"] == 2, e
    # dd governor: a thin window ABSTAINS (dd None — a fresh reset must not
    # hand the board's fail-closed dd leg a passing 0.0, IMB-02); a window
    # past DD_MIN_SPAN_SEC asserts a real number
    from datetime import timedelta
    _now = datetime.now(timezone.utc)
    _, dd, scale = dd_governor([], 1000.0, _now)
    assert dd is None and scale == 1.0, (dd, scale)
    _mid = (_now - timedelta(hours=2)).isoformat(timespec="seconds")
    assert dd_governor([[_mid, 1100.0]], 1000.0, _now)[1] is None, \
        "2h span is below the 6h evidence bar"
    _old = (_now - timedelta(hours=7)).isoformat(timespec="seconds")
    _, dd2, sc2 = dd_governor([[_old, 1100.0]], 1000.0, _now)
    assert dd2 is not None and abs(dd2 - (1000.0 / 1100.0 - 1.0)) < 1e-3, dd2
    assert sc2 == 0.5, sc2                       # -9.1% is past DD_HALF
    print("[fleet-risk] selftest OK (exposure_concentration + dd_governor)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
