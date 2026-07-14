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
STALE_ROW_SEC = 1800


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

# Directional crypto books only. Funding-carry is delta-neutral (excluded),
# sniper is event-class (tracked as gross info only), stocks are a separate
# mandate, scanners hold nothing.
# [2026-07-14] Retired bots removed (the dashboard RETIRED_ROWS set):
# crypto-trendmomo-4h + perps-regime-switch dropped from this list, and the
# whole perps long/short cohort (Bounce Catcher decommissioned 12 Jul, Trail
# Blazer retired) — their frozen rows were the ghost-exposure RED. Their
# bot_pnl rows are pruned by cleanup_legacy_bots.py on boot; if one is ever
# revived, re-add it here.
FREQTRADE_BOTS = ["crypto-trend-daily", "crypto-intraday-15m", "crypto-swing-daily",
                  "crypto-breakout-4h", "freqtrade-mum",
                  "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia"]
PERPS_LS_BOTS = []

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
        if not r or not row_fresh(r):
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
    for name in PERPS_LS_BOTS:
        r = by_bot.get(name)
        if not r or not row_fresh(r):
            continue
        extra = r.get("extra") or {}
        longs = int(extra.get("longs") or 0)
        shorts = int(extra.get("shorts") or 0)
        if longs or shorts:
            fleet_long += longs
            fleet_short += shorts
            per_bot[name] = {"long": longs, "short": shorts}

    gross = fleet_long + fleet_short
    light = max(light_for(fleet_long, LONG_BUDGET),
                light_for(fleet_short, SHORT_BUDGET),
                key=["green", "yellow", "red"].index)
    hot_pairs = {k: v for k, v in sorted(pair_count.items(),
                                         key=lambda kv: -kv[1]) if v >= 2}

    sniper = by_bot.get("event-listing-sniper") or {}
    if not row_fresh(sniper):
        sniper = {}
    risk_payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC, "mode": "advisory",
        "light": light,
        "long_positions": fleet_long, "long_budget": LONG_BUDGET,
        "short_positions": fleet_short, "short_budget": SHORT_BUDGET,
        "gross": gross,
        "pair_concentration": hot_pairs,   # same base held by >=2 bots
        "by_bot": per_bot,
        "info_only": {"sniper_open": sniper.get("open_trades")},
    }
    store.save_state(RISK_KEY, risk_payload)
    store.save_history(RISK_KEY, {"light": light, "long": fleet_long,
                                  "short": fleet_short, "gross": gross,
                                  "hot_pairs": hot_pairs})

    # ---- Layer 3: signal bus -------------------------------------------
    bus = {"updated": now_iso(), "ttl_sec": TTL_SEC}

    def fresh_extra(bot):
        r = by_bot.get(bot)
        return (r.get("extra") or {}) if (r and row_fresh(r)) else {}

    fc = fresh_extra("perps-funding-carry")
    if fc.get("hottest_funding_apr"):
        bus["funding_hottest_apr"] = fc["hottest_funding_apr"]
    xa = fresh_extra("scanner-cross-exchange-arb")
    if xa.get("best_top_pct") is not None:
        bus["xexchange_dislocation_pct"] = xa.get("best_top_pct")
    # [2026-07-14 review] Lighter venue premium (mark vs index, bps) — the
    # dislocation signal measured on the venue the fleet actually trades.
    # Advisory, like everything on the bus. Gap Scout publishes it.
    if xa.get("lighter_prem_bps"):
        bus["lighter_prem_bps"] = xa["lighter_prem_bps"]
    if xa.get("lighter_prem_med_bps") is not None:
        bus["lighter_venue_stress_bps"] = {
            "med": xa.get("lighter_prem_med_bps"),
            "max": xa.get("lighter_prem_max_bps"),
            "n": xa.get("lighter_prem_n")}
    ta = fresh_extra("scanner-triangular-arb")
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
    lstress = (bus.get("lighter_venue_stress_bps") or {}).get("med")
    print(f"[fleet-risk] {now_iso()} light={light.upper()} "
          f"long={fleet_long}/{LONG_BUDGET} short={fleet_short}/{SHORT_BUDGET} "
          f"gross={gross} | pair-pileups: {hp} | mood={bus.get('pulse_mood')} "
          f"panic={bus.get('pulse_panic')} | dislocation={bus.get('xexchange_dislocation_pct')} "
          f"| lighter-stress={lstress}bps")


if __name__ == "__main__":
    main()
