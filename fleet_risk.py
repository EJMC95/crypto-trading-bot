#!/usr/bin/env python3
"""
fleet_risk.py — CROSS-BOT LAYERS 2+3 (ADVISORY): the fleet-level view no
single bot has.

[2026-07-07] Built from CROSS_BOT_INTELLIGENCE_DESIGN_2026-07-07.md.

LAYER 2 — FLEET RISK TRAFFIC LIGHT (advisory week one)
  The scar this exists for: one July dip saw 26 same-direction crypto
  positions across three bots — every bot inside its own rules, the FLEET
  massively concentrated. This service reads every bot's live row in
  bot_pnl, counts directional crypto exposure fleet-wide, and publishes a
  traffic light + per-pair concentration to bot_state "fleet-risk".
  ADVISORY: nothing reads it yet. After a week of history we decide the
  enforcement wiring (confirm_trade_entry veto on RED) from evidence.

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
from datetime import datetime, timezone

import bot_pnl_store as store

RISK_KEY = "fleet-risk"
BUS_KEY = "signal-bus"
TTL_SEC = 900

# Directional crypto books only. Funding-carry is delta-neutral (excluded),
# sniper is event-class (tracked as gross info only), stocks are a separate
# mandate, scanners hold nothing.
FREQTRADE_BOTS = ["crypto-trend-daily", "crypto-intraday-15m", "crypto-swing-daily",
                  "crypto-breakout-4h", "crypto-trendmomo-4h", "freqtrade-mum",
                  "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia",
                  "perps-regime-switch"]
PERPS_LS_BOTS = ["perps-rsi-meanrev", "perps-donchian-breakout"]

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
    """(row, venue) for a directional bot — the LIVE Lighter row supersedes the
    paper twin so real Lighter exposure is counted and never double-counted."""
    live = by_bot.get(base + "-lighter")
    if _fresh(live):
        return live, "lighter_live"
    return by_bot.get(base), "hl_paper"

# Fleet budgets (positions, count-based v1 — inverse-vol weighting is a later
# refinement once this has advisory history to calibrate against).
LONG_BUDGET = 20
SHORT_BUDGET = 12
YELLOW_FRAC = 0.7


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def light_for(n, budget):
    if n >= budget:
        return "red"
    if n >= YELLOW_FRAC * budget:
        return "yellow"
    return "green"


def main():
    rows = store.fetch_bot_pnl()
    if rows is None:
        print(f"[fleet-risk] {now_iso()} no DB — skipped")
        return
    by_bot = {r["bot"]: r for r in rows}

    fleet_long, fleet_short = 0, 0
    per_bot, pair_count = {}, {}
    for name in FREQTRADE_BOTS:
        r = by_bot.get(name)
        if not r:
            continue
        n = int(r.get("open_trades") or 0)
        if n == 0:
            continue
        extra = r.get("extra") or {}
        pos = extra.get("open_pos") or []
        # freqtrade spot + regime-switch: entries are long unless the enter
        # tag says otherwise (regime-switch shorts carry 'short' in the tag).
        longs = sum(1 for p in pos if "short" not in str(p.get("tag", "")).lower()) if pos else n
        shorts = (len(pos) - longs) if pos else 0
        fleet_long += longs
        fleet_short += shorts
        per_bot[name] = {"long": longs, "short": shorts}
        for p in pos:
            base = str(p.get("pair", "")).split("/")[0]
            if base:
                pair_count[base] = pair_count.get(base, 0) + 1
    venues_seen = {}
    for name in PERPS_LS_BOTS:
        r, venue = authoritative_row(name, by_bot)   # live Lighter > paper twin
        if not r:
            continue
        extra = r.get("extra") or {}
        longs = int(extra.get("longs") or 0)
        shorts = int(extra.get("shorts") or 0)
        if longs or shorts:
            fleet_long += longs
            fleet_short += shorts
            per_bot[name] = {"long": longs, "short": shorts, "venue": venue}
            venues_seen[name] = venue

    # Shadow/testnet cohort — modelled, NOT real capital, so it never moves the
    # risk light; surfaced as info so the Lighter-cohort activity is still visible.
    shadow_long, shadow_short = 0, 0
    for base in PERPS_LS_BOTS:
        for suf in ("-lshadow", "-ltest"):
            e = (by_bot.get(base + suf) or {}).get("extra") or {}
            shadow_long += int(e.get("longs") or 0)
            shadow_short += int(e.get("shorts") or 0)

    gross = fleet_long + fleet_short
    light = max(light_for(fleet_long, LONG_BUDGET),
                light_for(fleet_short, SHORT_BUDGET),
                key=["green", "yellow", "red"].index)
    hot_pairs = {k: v for k, v in sorted(pair_count.items(),
                                         key=lambda kv: -kv[1]) if v >= 2}

    sniper = by_bot.get("event-listing-sniper") or {}
    risk_payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC, "mode": "advisory",
        "light": light,
        "long_positions": fleet_long, "long_budget": LONG_BUDGET,
        "short_positions": fleet_short, "short_budget": SHORT_BUDGET,
        "gross": gross,
        "pair_concentration": hot_pairs,   # same base held by >=2 bots
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
                                  "hot_pairs": hot_pairs})

    # ---- Layer 3: signal bus -------------------------------------------
    bus = {"updated": now_iso(), "ttl_sec": TTL_SEC}
    # [no-miss-sync] Funding rates GENUINELY differ across venues (Lighter vs HL
    # diverge — verified day-1). A Lighter-cohort entry filter must read LIGHTER
    # funding: prefer the Lighter-facing funding-carry row (live > shadow) over
    # the HL paper one, and tag the source so consumers know which venue it is.
    fc_row = (by_bot.get("perps-funding-carry-lighter")
              or by_bot.get("perps-funding-carry-lshadow")
              or by_bot.get("perps-funding-carry") or {})
    fc = fc_row.get("extra") or {}
    if fc.get("hottest_funding_apr"):
        bus["funding_hottest_apr"] = fc["hottest_funding_apr"]
        bus["funding_source"] = fc.get("venue") or "hyperliquid"
    xa = (by_bot.get("scanner-cross-exchange-arb") or {}).get("extra") or {}
    if xa.get("best_top_pct") is not None:
        bus["xexchange_dislocation_pct"] = xa.get("best_top_pct")
    ta = (by_bot.get("scanner-triangular-arb") or {}).get("extra") or {}
    if ta.get("best_depth_pct") is not None:
        bus["tri_arb_best_depth_pct"] = ta.get("best_depth_pct")
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
    _lv = ",".join(f"{k}:{v.split('_')[0]}" for k, v in venues_seen.items()) or "none-live"
    print(f"[fleet-risk] {now_iso()} light={light.upper()} "
          f"long={fleet_long}/{LONG_BUDGET} short={fleet_short}/{SHORT_BUDGET} "
          f"gross={gross} | live-venue: {_lv} | shadow(info) {shadow_long}L/{shadow_short}S "
          f"| funding_src={bus.get('funding_source')} | pair-pileups: {hp} "
          f"| mood={bus.get('pulse_mood')} dislocation={bus.get('xexchange_dislocation_pct')}")


if __name__ == "__main__":
    main()
