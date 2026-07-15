#!/usr/bin/env python3
"""
fleet_respiration.py — 🫁 the fleet's RESPIRATION organ (blood-oxygen monitor).

WHY (2026-07-15, operator: "what IS the oxygen — what is it made of, what
organ processes it"). The answer, made into an organ:

  OXYGEN     = fresh market data. Money is FOOD (you can starve for a while);
               data is OXYGEN (minutes without it and every organ asphyxiates
               — the brain grades stale, the bots trade dead marks, the immune
               system can't tell sick from well).
  MOLECULE   = mark_price, index_price, bid/ask, funding_rate, volume, OI —
               the keyless venue reads the whole fleet inhales.
  LUNGS      = the venue-fetch layer (venues/lighter_client, the scout/taker
               _get() fetchers, Gap Scout's ccxt). They inhale raw HTTP and
               put usable data into the bloodstream (bot_state).
  MEMBRANE   = the equity guard + plausibility/freshness filters — they reject
               CO2/toxins (dislocated prices, WAF errors) so only clean O2
               crosses into the blood.

The gap this fills: the watchdog is a per-organ death detector; the immune
organ catches fresh-but-WRONG. NEITHER measures the SUPPLY — is the fleet as
a whole still BREATHING? This organ reads the freshness of the data-bearing
keys, computes a blood-oxygen SATURATION (fraction of the fleet's oxygen
feeds that are current), and flags HYPOXIA when the supply drops — the slow
fleet-wide suffocation a per-organ check misses (e.g. a venue WAF block
starving every Lighter-fed organ at once, as the family bot's WS drop showed
tonight). ADVISORY + phone-push on a hypoxia transition. Fail-safe, TTL'd.

Publishes bot_state 'fleet-respiration' {updated, ttl_sec, spo2, state,
breaths:[{feed, age_s, fresh}], hypoxic:[...]}. Run-once; run_all.sh loops
it. --selftest is offline.
"""
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

KEY = "fleet-respiration"
TTL_SEC = int(os.environ.get("RESP_TTL_SEC", "1200"))
NOTIFY_GAP_H = float(os.environ.get("RESP_NOTIFY_GAP_H", "3"))

# The fleet's OXYGEN FEEDS — each a data-bearing bot_state key + the max age
# (s) at which its data is still "fresh air". A feed older than its limit is
# a missed breath. Weight = how many organs depend on that feed's oxygen.
OXYGEN_FEEDS = {
    "lighter-market":  {"limit": 1200, "weight": 3},   # the whole-venue map — most organs breathe this
    "signal-bus":      {"limit": 1200, "weight": 1},
    "regime-oracle":   {"limit": 7200, "weight": 1},   # slow feed (30-min)
    "market-pulse":    {"limit": 1800, "weight": 1},   # refreshes ~10-min; 30-min limit
}
# Live bots' publish freshness is their own breathing — read from bot_pnl.
LIVE_BREATHS = {
    "perps-funding-lighter-lighter": 1800,
    "crypto-trend-daily-lighter": 5400,
}
HYPOXIA_SPO2 = float(os.environ.get("RESP_HYPOXIA_SPO2", "0.7"))   # <70% sat = hypoxic


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


def _age(updated, now):
    try:
        u = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        return max(0.0, now - u.timestamp())
    except Exception:
        return None


def saturation(breaths):
    """Blood-oxygen saturation = weighted fraction of feeds breathing fresh.
    breaths: [{feed, age_s, limit, weight, fresh}]. Returns (spo2, hypoxic
    feed names). Pure — selftested."""
    tot = sum(b["weight"] for b in breaths) or 1
    fresh_w = sum(b["weight"] for b in breaths if b["fresh"])
    hypoxic = [b["feed"] for b in breaths if not b["fresh"]]
    return round(fresh_w / tot, 3), hypoxic


def read_breaths(states, bot_ages, now):
    """Build the breath list from organ states + live-bot ages. A feed that
    is entirely absent counts as a missed breath (age None -> not fresh)."""
    breaths = []
    for feed, spec in OXYGEN_FEEDS.items():
        age = _age((states.get(feed) or {}).get("updated"), now)
        breaths.append({"feed": feed, "age_s": None if age is None else round(age),
                        "limit": spec["limit"], "weight": spec["weight"],
                        "fresh": age is not None and age <= spec["limit"]})
    for bot, limit in LIVE_BREATHS.items():
        age = bot_ages.get(bot)
        breaths.append({"feed": bot, "age_s": None if age is None else round(age),
                        "limit": limit, "weight": 2,
                        "fresh": age is not None and age <= limit})
    return breaths


def send_push(title, body, priority="high"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        req = urllib.request.Request(f"{server}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", "lungs")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[fleet-respiration] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    # one batched beat for every oxygen feed
    states = (store.fetch_states(list(OXYGEN_FEEDS))
              if hasattr(store, "fetch_states") else {}) or {}
    states = {k: (states.get(k) or {}) for k in OXYGEN_FEEDS}
    bot_ages = {}
    try:
        for r in (store.fetch_bot_pnl() or []):
            b = str(r.get("bot"))
            if b in LIVE_BREATHS:
                bot_ages[b] = _age(r.get("updated_at"), now)
    except Exception:
        pass

    breaths = read_breaths(states, bot_ages, now)
    spo2, hypoxic = saturation(breaths)
    state = ("healthy" if spo2 >= 0.9 else
             "labored" if spo2 >= HYPOXIA_SPO2 else "HYPOXIC")

    payload = {"updated": _iso(now), "ttl_sec": TTL_SEC, "spo2": spo2,
               "state": state, "hypoxic": hypoxic, "breaths": breaths}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "spo2": spo2, "state": state})
        except Exception:
            pass

    # push only on a TRANSITION into hypoxia (recovery is quiet-good news)
    prior_state = prior.get("state")
    last_push = float(prior.get("last_push") or 0)
    if state == "HYPOXIC" and prior_state != "HYPOXIC" \
            and now - last_push >= NOTIFY_GAP_H * 3600:
        if send_push(f"🫁 fleet HYPOXIC — SpO2 {spo2:.0%}",
                     "starved oxygen feeds: " + ", ".join(hypoxic)
                     + "\n(fresh market data supply dropped — check the venue "
                       "fetch layer / WAF)", priority="urgent"):
            payload["last_push"] = now
            store.save_state(KEY, payload)
    else:
        payload["last_push"] = last_push

    print(f"[fleet-respiration] {_iso(now)} SpO2 {spo2:.0%} {state} "
          f"hypoxic={hypoxic or '—'}", flush=True)
    return payload


def _selftest():
    now = 1_800_000_000.0

    # all feeds fresh -> ~100% sat, healthy
    def st(age):
        return {"updated": _iso(now - age)}
    states_ok = {f: st(10) for f in OXYGEN_FEEDS}
    ages_ok = {b: 10 for b in LIVE_BREATHS}
    br = read_breaths(states_ok, ages_ok, now)
    spo2, hyp = saturation(br)
    assert spo2 == 1.0 and hyp == [], (spo2, hyp)

    # the heaviest feed (lighter-market, weight 3) going stale drops sat but
    # not below hypoxia alone
    states_lm = dict(states_ok, **{"lighter-market": {"updated": _iso(now - 99999)}})
    br2 = read_breaths(states_lm, ages_ok, now)
    spo2b, hyp2 = saturation(br2)
    assert "lighter-market" in hyp2 and spo2b < 1.0
    # total weight = 3+1+1+1 (feeds) + 2+2 (live) = 10; lighter-market=3 stale
    assert abs(spo2b - 0.7) < 1e-9, spo2b

    # a venue-wide asphyxiation: every Lighter feed + both live bots dark
    dead = {f: {"updated": _iso(now - 99999)} for f in OXYGEN_FEEDS}
    ages_dead = {b: 99999 for b in LIVE_BREATHS}
    spo2c, hypc = saturation(read_breaths(dead, ages_dead, now))
    assert spo2c == 0.0 and len(hypc) == len(OXYGEN_FEEDS) + len(LIVE_BREATHS)

    # a totally ABSENT feed (never published) is a missed breath, not fresh
    br_absent = read_breaths({}, {}, now)
    assert all(not b["fresh"] for b in br_absent)
    assert saturation(br_absent)[0] == 0.0

    # state thresholds
    assert saturation(read_breaths(states_ok, ages_ok, now))[0] >= 0.9   # healthy
    print("fleet_respiration selftest OK (saturation weighting, stale feed, "
          "asphyxiation, absent feed, thresholds)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
