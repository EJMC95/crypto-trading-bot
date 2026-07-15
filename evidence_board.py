#!/usr/bin/env python3
"""
evidence_board.py — the fleet's EVIDENCE BOARD organ (v2, shipped 2026-07-15
on user instruction: "make the evidence board more advanced … an even more
integrated system the scanners and brain have to work with"; freeze lifted by
the user the same evening).

WHAT IT IS
The evidence board used to be a passive banner: market_context appended
alerts, a daily session hand-wrote verdicts, the dashboard subtracted the two.
This organ makes the board a live participant:

  1. LIFECYCLE + SCORING — every alert key gets first_seen / fires / trend
     (escalating | steady | decaying) and a composite score:
     severity x recency-decay x persistence x corroboration. Corroboration is
     mechanical: a dislocation alert scores higher while the scout's own
     stress/premium feed independently agrees.
  2. SYNTHESIS — the board CREATES evidence the alert feed can't see because
     it joins feeds nobody else joins: venue stress vs the taker's veto bar,
     lens-forward crossing its n4h ruling floor (and lenses NEGATIVE at the
     floor), the drawdown governor approaching its clip line, budget
     crowding, and coin-veto FLAP (a coin oscillating across the veto
     threshold).
  3. AUTO-VERDICTS — mechanical verdicts (milestones auto-stale after 24h,
     dislocations fold into the census after 24h unless escalating, veto
     records age out at 48h). MANUAL verdicts in bot_state['evidence-review']
     always win — the daily review and the operator stay senior to the organ.
  4. RESPONSE — two tiers, honest about authority:
       NOTIFY (live): new warn/action items or escalations push to the
         operator's phone (same NTFY_TOPIC channel as the watchdog),
         min EVBOARD_NOTIFY_GAP_H per key.
       PROPOSE (shadow): every response rule names an EXISTING restrict-only
         lever (lens veto, clip scale, stress veto, budget) and what it WOULD
         do. Published in the payload, consumed by NOTHING until a review
         flips EVBOARD_MODE=publish — the same earn-your-wiring path the L2
         risk light walked (advisory 07-Jul -> enforced 15-Jul on evidence).

WHAT IT NEVER DOES
  Open positions, loosen a veto, raise a stake, or touch bot logic. The
  fleet's standing doctrine (restrict-only actuators, backtest-first,
  NO_REAL_MONEY) binds this organ regardless of freeze state. Opportunity
  flow stays where it already lives: scout tickets -> Ticket Taker's shadow
  book -> brain grading -> review promotion.

Publishes bot_state['evidence-board'] (+ lean history when available):
  {updated, ttl_sec, mode, items:[{key, msg, sev, score, fires_24h, trend,
   verdict, source, proposal}], proposals:[...], notified:{key: ts}}
Consumers: pnl_dashboard (board card + banner suppression), the daily
evidence review, and the operator's phone. Fail-silent; backtests inert
(no DATABASE_URL -> every store call no-ops).
"""
import json
import math
import os
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

BOARD_KEY = "evidence-board"
INTERVAL = int(os.environ.get("EVBOARD_INTERVAL_SEC", "600"))
MODE = os.environ.get("EVBOARD_MODE", "shadow").strip().lower()   # shadow|publish
NOTIFY_GAP_H = float(os.environ.get("EVBOARD_NOTIFY_GAP_H", "6"))
WINDOW_H = 48          # board horizon — matches the dashboard banner
TTL_SEC = 3 * INTERVAL

SEV_W = {"info": 1.0, "warn": 3.0, "action": 4.0}
DECAY_HALF_LIFE_H = 12.0

# lens-forward ruling floor (agenda item 2) and the "negative at the floor" bar
LENS_FLOOR_N4H = int(os.environ.get("EVBOARD_LENS_FLOOR", "75"))
LENS_NEG_AVG4H = float(os.environ.get("EVBOARD_LENS_NEG_AVG4H", "-0.5"))
STRESS_VETO_BPS = float(os.environ.get("TT_STRESS_VETO_BPS", "15"))
DD_NEAR_TRIP = float(os.environ.get("EVBOARD_DD_NEAR_TRIP", "-0.035"))


def _now():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or _now(), tz=timezone.utc).isoformat(timespec="seconds")


def _fresh(state, max_age_s=2700):
    """A feed is usable if its own `updated` stamp is younger than max_age_s
    (fail-safe: unusable feeds contribute NOTHING — no synthesis, no boost)."""
    try:
        u = datetime.fromisoformat(str(state.get("updated")).replace("Z", "+00:00"))
        return (_now() - u.timestamp()) <= max_age_s
    except Exception:
        return False


# ---------------------------------------------------------------------------
# pure functions (selftested)
# ---------------------------------------------------------------------------

def score_item(sev, age_h, fires_24h, corroborated):
    """severity x recency-decay x persistence x corroboration -> one number
    the dashboard can sort by. Monotone in every input by construction."""
    w = SEV_W.get(sev, 1.0)
    decay = 0.5 ** (max(0.0, age_h) / DECAY_HALF_LIFE_H)
    persistence = 1.0 + math.log(max(1, fires_24h))
    boost = 1.5 if corroborated else 1.0
    return round(w * decay * persistence * boost, 3)


def trend_of(fires_recent_12h, fires_prior_12h):
    if fires_recent_12h > fires_prior_12h:
        return "escalating"
    if fires_recent_12h < fires_prior_12h:
        return "decaying"
    return "steady"


def auto_verdict(key, sev, age_h, trend):
    """Mechanical verdicts only — anything judgement-shaped returns 'active'
    and waits for the daily review / operator. Manual verdicts always win
    upstream (merge_verdicts)."""
    if key.startswith(("census:", "factor-sample:")):
        # milestone notices: their decision gates live in the standing weekly
        # reviews; once seen for a day they are recorded, not actionable.
        return "stale" if age_h >= 24 else "active"
    if key.startswith("disloc:"):
        # census evidence: folds into the census after a day UNLESS the coin
        # is escalating right now (then it deserves eyes, not archiving).
        return "active" if trend == "escalating" else ("stale" if age_h >= 24 else "active")
    if key.startswith("veto:"):
        # change records: the standing list lives with the scanner; the event
        # itself ages out. Flap detection is a separate synthesized item.
        return "stale" if age_h >= 48 else "active"
    return "active"       # live-shadow-gap, stale-live:*, everything unknown


def merge_verdicts(manual_verdicts, auto_map):
    """{key: verdict} with MANUAL (evidence-review) verdicts senior to auto."""
    out = dict(auto_map)
    for v in manual_verdicts or []:
        k, s = v.get("key"), v.get("status")
        if k and s:
            out[k] = s
    return out


def corroborate(key, lighter_market):
    """Mechanical cross-feed agreement. Only rules that are cheap to check and
    hard to argue with; everything else is un-corroborated (boost 1.0)."""
    if not lighter_market:
        return False
    if key.startswith("disloc:"):
        coin = key.split(":", 1)[1]
        stress = (lighter_market.get("stress") or {})
        if (stress.get("med") or 0) >= 10:
            return True
        outliers = lighter_market.get("prem_outliers") or []
        for o in outliers:
            sym = o.get("symbol") if isinstance(o, dict) else (o[0] if isinstance(o, (list, tuple)) and o else o)
            if str(sym).upper() == coin.upper():
                return True
    return False


def synthesize(lighter_market, fleet_risk, lens_forward, prior_keys, now_ts):
    """Board-authored evidence from feed JOINS. Each item fires on condition
    ENTER (not every cycle) — prior_keys is the set of synthesized keys that
    were active last cycle. Returns [{key, severity, msg, proposal, lever}]."""
    out = []

    def emit(key, severity, msg, proposal=None, lever=None):
        out.append({"key": key, "severity": severity, "msg": msg,
                    "proposal": proposal, "lever": lever, "ts": now_ts,
                    "source": "board"})

    lm_ok = _fresh(lighter_market or {})
    fr_ok = _fresh(fleet_risk or {})
    lf = (lens_forward or {}).get("lenses") or {}

    if lm_ok:
        med = ((lighter_market.get("stress") or {}).get("med")) or 0
        if med >= STRESS_VETO_BPS:
            emit("board:venue-stress", "warn",
                 f"🌡️ venue-wide |premium| med {med}bps ≥ taker veto bar {STRESS_VETO_BPS:g} — "
                 f"marks unreliable venue-wide",
                 proposal="Taker already pauses entries (built-in); WOULD extend the same "
                          "pause to family/live new entries",
                 lever="stress-veto")

    if fr_ok:
        dd = fleet_risk.get("fleet_dd_7d")
        if dd is not None and dd <= DD_NEAR_TRIP:
            emit("board:governor-near-trip", "warn",
                 f"📉 fleet 7d drawdown {dd*100:+.1f}% approaching the -5% half-clip line",
                 proposal=f"governor WOULD halve clips at -5% (clip_scale). No pre-emption — awareness",
                 lever="clip-scale")
        gross, budget = fleet_risk.get("gross"), fleet_risk.get("long_budget")
        if gross is not None and budget and gross >= budget:
            eff = ((fleet_risk.get("exposure") or {}).get("long_effective_n"))
            emit("board:budget-crowding", "info",
                 f"📦 directional book {gross}/{budget} — budget saturated"
                 + (f" (effective bets ≈ {eff:g})" if eff is not None else ""),
                 proposal="long-entry veto is already enforcing; evidence feeds agenda item 1",
                 lever="long-budget")

    for lens, g in sorted(lf.items()):
        n4h = int(g.get("n4h") or 0)
        avg4 = g.get("avg4h_pct")
        if n4h >= LENS_FLOOR_N4H:
            emit(f"board:lens-floor:{lens}", "info",
                 f"🎓 lens '{lens}' crossed the n4h≥{LENS_FLOOR_N4H} ruling floor "
                 f"(n={n4h}, hit4h {100*(g.get('hit4h') or 0):.0f}%, avg4h {avg4:+.2f}%)")
            if avg4 is not None and avg4 <= LENS_NEG_AVG4H:
                emit(f"board:lens-negative:{lens}", "warn",
                     f"🩸 lens '{lens}' NEGATIVE at the ruling floor "
                     f"(n4h={n4h}, avg4h {avg4:+.2f}%)",
                     proposal=f"restrict-only lens veto for '{lens}' via the brain's "
                              f"existing machinery (floors met — review rules)",
                     lever="lens-veto")
    return out


def detect_veto_flap(alerts_48h_plus, now_ts, window_d=7, min_events=3):
    """A coin appearing in >= min_events veto-change alerts inside window_d
    days is oscillating across its threshold. Restrict-only so harmless, but
    it argues for remove-side hysteresis — surfaced as board evidence."""
    from collections import defaultdict
    per_coin = defaultdict(int)
    cut = now_ts - window_d * 86400
    for a in alerts_48h_plus:
        if not str(a.get("key", "")).startswith("veto:"):
            continue
        if (a.get("ts") or 0) < cut:
            continue
        for c in str(a["key"])[len("veto:"):].split(","):
            if c.strip():
                per_coin[c.strip()] += 1
    out = []
    for coin, n in sorted(per_coin.items()):
        if n >= min_events:
            out.append({"key": f"board:veto-flap:{coin}", "severity": "warn",
                        "msg": f"🔁 coin veto FLAP: {coin} changed state {n}x in {window_d}d "
                               f"— hovers at the veto threshold",
                        "proposal": "remove-side hysteresis on the coin veto "
                                    "(pure tightening; needs the backtest-first pass)",
                        "lever": "coin-veto", "ts": now_ts, "source": "board"})
    return out


# ---------------------------------------------------------------------------
# notify (same channel as the fleet watchdog)
# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="urgent", tags="scales"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", tags)
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[evidence_board] push failed: {type(e).__name__}: {e}", flush=True)
        return False


# ---------------------------------------------------------------------------
# one cycle
# ---------------------------------------------------------------------------

def run_once():
    now = _now()
    prior = store.load_state(BOARD_KEY) or {}
    prior_items = {i["key"]: i for i in prior.get("items", [])}
    notified = dict(prior.get("notified") or {})

    fa = (store.load_state("fleet-alerts") or {}).get("alerts") or []
    review = store.load_state("evidence-review") or {}
    lm = store.load_state("lighter-market") or {}
    fr = store.load_state("fleet-risk") or {}
    lf = store.load_state("brain-lens-forward") or {}

    # ---- feed alerts: latest per key inside the window --------------------
    latest, fires24, fires_12, fires_prior12 = {}, {}, {}, {}
    for a in fa:
        k = a.get("key") or a.get("msg")
        ts = a.get("ts") or 0
        if ts >= now - WINDOW_H * 3600 and (k not in latest or ts > latest[k]["ts"]):
            latest[k] = a
        if ts >= now - 24 * 3600:
            fires24[k] = fires24.get(k, 0) + 1
        if ts >= now - 12 * 3600:
            fires_12[k] = fires_12.get(k, 0) + 1
        elif ts >= now - 24 * 3600:
            fires_prior12[k] = fires_prior12.get(k, 0) + 1

    # ---- synthesized evidence (condition-ENTER only) -----------------------
    prior_synth = {k for k in prior_items if k.startswith("board:")}
    synth = synthesize(lm, fr, lf, prior_synth, now) + detect_veto_flap(fa, now)
    synth_new = [s for s in synth if s["key"] not in prior_synth]

    # ---- assemble the board -------------------------------------------------
    auto_map, items = {}, []
    for k, a in latest.items():
        age_h = (now - (a.get("ts") or now)) / 3600
        tr = trend_of(fires_12.get(k, 0), fires_prior12.get(k, 0))
        v = auto_verdict(k, a.get("severity"), age_h, tr)
        auto_map[k] = v
        items.append({
            "key": k, "msg": a.get("msg"), "sev": a.get("severity"),
            "score": score_item(a.get("severity"), age_h, fires24.get(k, 1),
                                corroborate(k, lm if _fresh(lm) else None)),
            "fires_24h": fires24.get(k, 0), "trend": tr, "source": "alerts",
            "first_seen": prior_items.get(k, {}).get("first_seen") or _iso(a.get("ts")),
            "verdict": v,
        })
    for s in synth:
        k = s["key"]
        auto_map[k] = "active"
        items.append({
            "key": k, "msg": s["msg"], "sev": s["severity"],
            "score": score_item(s["severity"], 0.0, 1, True),
            "fires_24h": 1, "trend": "steady", "source": "board",
            "first_seen": prior_items.get(k, {}).get("first_seen") or _iso(now),
            "verdict": "active", "proposal": s.get("proposal"), "lever": s.get("lever"),
        })

    merged = merge_verdicts(review.get("verdicts"), auto_map)
    for i in items:
        i["verdict"] = merged.get(i["key"], i["verdict"])
    items.sort(key=lambda i: -i["score"])

    proposals = [{"key": s["key"], "lever": s["lever"], "proposal": s["proposal"],
                  "mode": MODE} for s in synth if s.get("proposal")]

    # ---- notify: NEW warn/action (or escalating) active items --------------
    for i in items:
        if i["verdict"] != "active" or i["sev"] not in ("warn", "action"):
            continue
        is_new = i["key"] not in prior_items or (i["key"] in {s["key"] for s in synth_new})
        escalated = i["trend"] == "escalating" and prior_items.get(i["key"], {}).get("trend") != "escalating"
        last_n = notified.get(i["key"], 0)
        if (is_new or escalated) and now - last_n >= NOTIFY_GAP_H * 3600:
            body = (i["msg"] or "") + (f"\n\nProposed ({MODE}): {i['proposal']}" if i.get("proposal") else "")
            if send_push(f"evidence board: {(i['msg'] or i['key'])[:60]}", body):
                notified[i["key"]] = now
                print(f"[evidence_board] notified: {i['key']}", flush=True)

    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC, "mode": MODE,
        "items": items[:20],
        "proposals": proposals,
        "notified": {k: v for k, v in notified.items() if now - v < 7 * 86400},
        "inputs_fresh": {"lighter_market": _fresh(lm), "fleet_risk": _fresh(fr),
                         "lens_forward": bool(lf)},
    }
    store.save_state(BOARD_KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(BOARD_KEY, {"updated": payload["updated"],
                                           "n_items": len(items),
                                           "top": [i["key"] for i in items[:5]],
                                           "proposals": len(proposals)})
        except Exception:
            pass
    print(f"[evidence_board] {_iso(now)} items={len(items)} "
          f"(synth {len(synth)}, new {len(synth_new)}) proposals={len(proposals)} mode={MODE}",
          flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    # scoring is monotone in every input
    assert score_item("warn", 0, 1, False) > score_item("info", 0, 1, False)
    assert score_item("warn", 0, 1, False) > score_item("warn", 24, 1, False)
    assert score_item("warn", 0, 5, False) > score_item("warn", 0, 1, False)
    assert score_item("warn", 0, 1, True) > score_item("warn", 0, 1, False)
    # trend
    assert trend_of(3, 1) == "escalating" and trend_of(0, 2) == "decaying" and trend_of(1, 1) == "steady"
    # auto-verdicts
    assert auto_verdict("census:50", "info", 30, "steady") == "stale"
    assert auto_verdict("factor-sample:1", "info", 2, "steady") == "active"
    assert auto_verdict("disloc:KAITO", "info", 30, "escalating") == "active"   # escalation blocks archiving
    assert auto_verdict("disloc:KAITO", "info", 30, "steady") == "stale"
    assert auto_verdict("veto:ADA", "action", 50, "steady") == "stale"
    assert auto_verdict("live-shadow-gap", "warn", 100, "decaying") == "active"  # never auto-cleared
    # manual verdicts win in BOTH directions
    m = merge_verdicts([{"key": "a", "status": "resolved"}, {"key": "b", "status": "active"}],
                       {"a": "active", "b": "stale", "c": "stale"})
    assert m == {"a": "resolved", "b": "active", "c": "stale"}
    # synthesis: stress + lens rules fire; stale feeds fire NOTHING
    fresh = _iso()
    lm = {"updated": fresh, "stress": {"med": 20}}
    fr = {"updated": fresh, "fleet_dd_7d": -0.04, "gross": 25, "long_budget": 20,
          "exposure": {"long_effective_n": 10.1}}
    lf = {"lenses": {"momentum": {"n4h": 90, "hit4h": 0.37, "avg4h_pct": -1.05},
                     "dip": {"n4h": 2, "hit4h": 0.0, "avg4h_pct": -0.6}}}
    keys = {s["key"] for s in synthesize(lm, fr, lf, set(), _now())}
    assert keys == {"board:venue-stress", "board:governor-near-trip", "board:budget-crowding",
                    "board:lens-floor:momentum", "board:lens-negative:momentum"}, keys
    assert synthesize({"updated": "2020-01-01T00:00:00+00:00", "stress": {"med": 99}},
                      {}, {}, set(), _now()) == []
    # flap detection
    now = _now()
    fa = [{"key": "veto:ADA,kBONK", "ts": now - 3 * 86400},
          {"key": "veto:ADA", "ts": now - 2 * 86400},
          {"key": "veto:ADA", "ts": now - 1000}]
    flaps = detect_veto_flap(fa, now)
    assert [f["key"] for f in flaps] == ["board:veto-flap:ADA"], flaps
    # push: unconfigured -> False, no crash
    os.environ.pop("NTFY_TOPIC", None)
    assert send_push("t", "b") is False
    print("evidence_board selftest OK")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    elif "--once" in sys.argv:
        run_once()
    else:
        while True:
            try:
                run_once()
            except Exception as e:  # noqa: BLE001
                print(f"[evidence_board] cycle error: {type(e).__name__}: {e}", flush=True)
            time.sleep(INTERVAL)
