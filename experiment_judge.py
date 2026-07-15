#!/usr/bin/env python3
"""
experiment_judge.py — 🧪⚖️ the shadow→live PROMOTION JUDGE.

WHY (2026-07-15, user): "positive changes made to shadow bots and new
implementations get carried across to the real money bots … so that they
also carry the edge to a win" — with the bar that separates EDGE from LUCK
(the Trail Blazer lesson: a +$197 paper month evaporated under scrutiny).
Nothing reaches real money on a hot streak; it reaches real money by
beating the live arm, per trade, over a real window, on both halves.

THE ARMS (Funding Farmer — the only live bot that trades often enough to
judge; Tide Rider trades ~weekly and stays backtest-validated):
  live arm    perps-funding-lighter-lighter  — env-default bars (until a
              promotion is in force via live.funding.* levers)
  shadow arm  perps-funding-lighter-lshadow  — the EXPERIMENT arm: runs the
              current candidate's bars via xp.* levers (zero real money)

LIFECYCLE (bot_state 'xp-judge'; hourly; one candidate at a time so
attribution is never confounded):
  IDLE      start the next CANDIDATE: assert its xp.* levers on the shadow
            arm, stamp started_ts. (Every close row carries extra.bars, so
            the ledger records which params produced what.)
  RUNNING   re-assert the xp levers each cycle. Once MIN_DAYS have passed
            and the floors are met (shadow >= MIN_CLOSES closes in-window,
            live >= LIVE_MIN_CLOSES for a fair pair), run the PAIRED
            evaluation: promote only if the shadow arm's mean per-trade
            pnl_pct is positive AND beats the live arm's by MARGIN_PP on
            the full window AND on both halves. Abandon at MAX_DAYS
            without clearing (verdict logged, cooldown, next candidate).
  PROMOTED  assert the live.funding.* counterpart(s) — this judge is the
            ONLY writer of that prefix — and keep the xp levers, so both
            arms run the same bars again (the control arm is restored).
            FADE WATCH: if the live arm's mean pnl_pct since promotion
            goes negative at n >= FADE_N, stop asserting; every lever
            expires back to env defaults on its own. Cooldown, then the
            queue continues.

Every transition pushes to the phone (urgent for PROMOTE and FADE — real
money changed). Fail-safe: no DB / short ledger -> nothing is asserted and
whatever was live expires back to env defaults within the lever TTL.

Run-once process; run_all.sh loops it hourly. --selftest is offline.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning

KEY = "xp-judge"
TTL_SEC = int(os.environ.get("XPJ_TTL_SEC", "10800"))
LEVER_TTL = int(os.environ.get("XPJ_LEVER_TTL", "7800"))      # ~2h re-assert
SHADOW_BOT = os.environ.get("XPJ_SHADOW_BOT", "perps-funding-lighter-lshadow")
LIVE_BOT = os.environ.get("XPJ_LIVE_BOT", "perps-funding-lighter-lighter")
MIN_DAYS = float(os.environ.get("XPJ_MIN_DAYS", "7"))
MAX_DAYS = float(os.environ.get("XPJ_MAX_DAYS", "14"))
MIN_CLOSES = int(os.environ.get("XPJ_MIN_CLOSES", "30"))      # shadow arm
LIVE_MIN_CLOSES = int(os.environ.get("XPJ_LIVE_MIN_CLOSES", "10"))
MARGIN_PP = float(os.environ.get("XPJ_MARGIN_PP", "0.5"))     # per-trade pp
FADE_N = int(os.environ.get("XPJ_FADE_N", "15"))
COOLDOWN_H = float(os.environ.get("XPJ_COOLDOWN_H", "48"))

# One candidate at a time, in order. First: the gate widening the 11-Jul
# scanner review explicitly queued as "opt-in, shadow-validate first".
CANDIDATES = [
    {"name": "enter-gate-0.30", "levers": {"xp.funding.enter_apr": 0.30}},
    {"name": "tp-0.06",         "levers": {"xp.funding.take_profit": 0.06}},
    {"name": "hold-48",         "levers": {"xp.funding.max_hold_h": 48.0}},
]
XP_TO_LIVE = {"xp.funding.enter_apr": "live.funding.enter_apr",
              "xp.funding.take_profit": "live.funding.take_profit",
              "xp.funding.max_hold_h": "live.funding.max_hold_h"}


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def parse_ts(s):
    s = str(s).strip().replace("Z", "+00:00")
    if s.endswith(" UTC"):
        s = s[:-4] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


# ---------------------------------------------------------------------------
# pure evaluation (selftested offline)
# ---------------------------------------------------------------------------

def arm_trades(rows, bot, start_ts, end_ts=None):
    """[(close_ts, pnl_pct)] for one arm inside the window, oldest first."""
    out = []
    for r in rows or []:
        if str(r.get("bot")) != bot or r.get("profit_ratio") is None:
            continue
        try:
            ts = parse_ts(r.get("close_ts"))
        except Exception:
            continue
        if ts >= start_ts and (end_ts is None or ts < end_ts):
            out.append((ts, float(r["profit_ratio"])))
    out.sort()
    return out


def _mean_pct(trades):
    return 100.0 * sum(p for _, p in trades) / len(trades) if trades else None


def paired_eval(rows, start_ts, end_ts, shadow_bot=None, live_bot=None,
                min_closes=None, live_min=None, margin_pp=None):
    """The promotion bar. Returns a verdict dict; verdict['promote'] is True
    only when the shadow arm is positive AND beats the live arm per-trade by
    margin_pp on the FULL window AND on BOTH halves (the doctrine's
    both-halves rule — a candidate that won one lucky week doesn't clear)."""
    shadow_bot = shadow_bot or SHADOW_BOT
    live_bot = live_bot or LIVE_BOT
    min_closes = min_closes or MIN_CLOSES
    live_min = live_min or LIVE_MIN_CLOSES
    margin_pp = MARGIN_PP if margin_pp is None else margin_pp
    sh = arm_trades(rows, shadow_bot, start_ts, end_ts)
    lv = arm_trades(rows, live_bot, start_ts, end_ts)
    v = {"promote": False, "n_shadow": len(sh), "n_live": len(lv),
         "shadow_mean_pct": _mean_pct(sh), "live_mean_pct": _mean_pct(lv)}
    if len(sh) < min_closes or len(lv) < live_min:
        v["why"] = f"floors: shadow {len(sh)}/{min_closes}, live {len(lv)}/{live_min}"
        return v
    mid = start_ts + (end_ts - start_ts) / 2.0
    for a, b, label in ((start_ts, mid, "h1"), (mid, end_ts, "h2")):
        shm = _mean_pct(arm_trades(rows, shadow_bot, a, b))
        lvm = _mean_pct(arm_trades(rows, live_bot, a, b))
        v[label] = {"shadow": shm, "live": lvm}
        if shm is None or lvm is None or shm <= lvm:
            v["why"] = f"{label}: shadow {shm} vs live {lvm} — no edge on this half"
            return v
    full_gap = v["shadow_mean_pct"] - v["live_mean_pct"]
    v["gap_pp"] = round(full_gap, 3)
    if v["shadow_mean_pct"] <= 0:
        v["why"] = "shadow arm not positive in its own right"
        return v
    if full_gap < margin_pp:
        v["why"] = f"gap {full_gap:.2f}pp < margin {margin_pp}pp"
        return v
    v["promote"] = True
    v["why"] = (f"shadow beats live by {full_gap:.2f}pp/trade over the window "
                f"AND both halves (n={len(sh)} vs {len(lv)})")
    return v


def fade_check(rows, promoted_ts, now, live_bot=None, fade_n=None):
    """True when the LIVE arm has gone negative since promotion (n>=fade_n)
    — the promoted edge is fading; release it back to env defaults."""
    lv = arm_trades(rows, live_bot or LIVE_BOT, promoted_ts, now)
    if len(lv) < (fade_n or FADE_N):
        return False, len(lv), _mean_pct(lv)
    m = _mean_pct(lv)
    return (m is not None and m < 0), len(lv), m


# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="default"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", "test_tube")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[xp-judge] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def _assert_levers(levers, reason, evidence):
    return tuning.write_levers(
        {k: {"value": v, "reason": reason[:180], "evidence": evidence[:280]}
         for k, v in levers.items()},
        set_by="experiment-judge", ttl_sec=LEVER_TTL)


def run_once():
    now = now_ts()
    st = store.load_state(KEY) or {}
    phase = st.get("phase") or "idle"
    idx = int(st.get("cand_idx") or 0)
    verdicts = st.get("verdicts") or []
    rows = store.fetch_paper_trades(limit=4000)
    have_ledger = bool(rows)

    def save(**kw):
        payload = {"updated": iso(now), "ttl_sec": TTL_SEC, "phase": kw.get("phase", phase),
                   "cand_idx": kw.get("cand_idx", idx),
                   "candidate": (CANDIDATES[kw.get("cand_idx", idx)]["name"]
                                 if kw.get("cand_idx", idx) < len(CANDIDATES)
                                 and kw.get("phase", phase) in ("running", "promoted")
                                 else None),
                   "started_ts": kw.get("started_ts", st.get("started_ts")),
                   "promoted_ts": kw.get("promoted_ts", st.get("promoted_ts")),
                   "cooldown_until": kw.get("cooldown_until", st.get("cooldown_until")),
                   "verdicts": verdicts[-10:], "last_eval": kw.get("last_eval")}
        store.save_state(KEY, payload)
        if hasattr(store, "save_history"):
            try:
                store.save_history(KEY, {"updated": payload["updated"],
                                         "phase": payload["phase"],
                                         "candidate": payload["candidate"]})
            except Exception:
                pass
        print(f"[xp-judge] {iso(now)} phase={payload['phase']} "
              f"candidate={payload['candidate']} "
              f"{kw.get('note') or ''}", flush=True)
        return payload

    if phase == "idle":
        if float(st.get("cooldown_until") or 0) > now:
            return save(note=f"cooldown until {iso(float(st['cooldown_until']))}")
        if idx >= len(CANDIDATES):
            return save(note="queue exhausted — new candidates via CANDIDATES")
        if not have_ledger:
            return save(note="no ledger visible — asserting nothing (fail-safe)")
        cand = CANDIDATES[idx]
        _assert_levers(cand["levers"], f"experiment {cand['name']} started",
                       f"shadow arm {SHADOW_BOT}; judge bar: {MIN_DAYS}d/"
                       f"{MIN_CLOSES} closes/+{MARGIN_PP}pp both-halves")
        send_push(f"experiment started: {cand['name']}",
                  f"shadow arm now runs {json.dumps(cand['levers'])}; "
                  f"promotion bar {MIN_DAYS:g}d / {MIN_CLOSES} closes / "
                  f"+{MARGIN_PP}pp vs live on both halves")
        return save(phase="running", started_ts=now, note=f"STARTED {cand['name']}")

    if phase == "running":
        cand = CANDIDATES[idx]
        started = float(st.get("started_ts") or now)
        _assert_levers(cand["levers"], f"experiment {cand['name']} running",
                       f"started {iso(started)}")
        days = (now - started) / 86400.0
        ev = paired_eval(rows, started, now) if have_ledger else {"promote": False, "why": "no ledger"}
        if days >= MIN_DAYS and ev["promote"]:
            live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
            _assert_levers({**cand["levers"], **live_levers},
                           f"PROMOTED {cand['name']}", ev["why"])
            verdicts.append({"name": cand["name"], "verdict": "PROMOTED",
                             "ts": iso(now), "eval": ev})
            send_push(f"PROMOTED to LIVE: {cand['name']}",
                      f"{ev['why']}\nlive levers: {json.dumps(live_levers)} "
                      f"(TTL'd; fades back to env if the live arm turns)",
                      priority="urgent")
            return save(phase="promoted", promoted_ts=now, last_eval=ev,
                        note=f"PROMOTED {cand['name']}")
        if days >= MAX_DAYS:
            verdicts.append({"name": cand["name"], "verdict": "ABANDONED",
                             "ts": iso(now), "eval": ev})
            send_push(f"experiment abandoned: {cand['name']}",
                      f"{MAX_DAYS:g}d without clearing the bar — {ev.get('why')}")
            return save(phase="idle", cand_idx=idx + 1, started_ts=None,
                        cooldown_until=now + COOLDOWN_H * 3600, last_eval=ev,
                        note=f"ABANDONED {cand['name']}")
        return save(last_eval=ev, note=f"day {days:.1f}/{MIN_DAYS:g}: {ev.get('why')}")

    if phase == "promoted":
        cand = CANDIDATES[idx]
        promoted = float(st.get("promoted_ts") or now)
        fading, n, m = fade_check(rows, promoted, now) if have_ledger else (False, 0, None)
        if fading:
            verdicts.append({"name": cand["name"], "verdict": "FADED",
                             "ts": iso(now), "live_n": n, "live_mean_pct": m})
            send_push(f"promotion FADED: {cand['name']}",
                      f"live arm {m:+.2f}%/trade over n={n} since promotion — "
                      f"levers released, env defaults return within the TTL",
                      priority="urgent")
            return save(phase="idle", cand_idx=idx + 1, started_ts=None,
                        promoted_ts=None,
                        cooldown_until=now + COOLDOWN_H * 3600,
                        note=f"FADED {cand['name']}")
        live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
        _assert_levers({**cand["levers"], **live_levers},
                       f"promotion {cand['name']} in force",
                       f"promoted {iso(promoted)}; live n={n} mean "
                       f"{m if m is None else round(m, 3)}%/trade")
        return save(note=f"promotion in force (live n={n}, mean "
                         f"{m if m is None else round(m, 2)}%)")

    return save(phase="idle", note=f"unknown phase {phase!r} reset")


# ---------------------------------------------------------------------------

def _selftest():
    def row(bot, ts, pct):
        return {"bot": bot, "profit_ratio": pct, "close_ts": iso(ts)}

    t0 = 1_800_000_000.0
    day = 86400.0
    end = t0 + 8 * day
    # shadow beats live steadily on both halves: 32 shadow closes @ +1%,
    # 12 live closes @ +0.2%
    rows = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01) for i in range(32)]
            + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev = paired_eval(rows, t0, end)
    assert ev["promote"], ev
    assert abs(ev["gap_pp"] - 0.8) < 0.01, ev

    # one lucky half must NOT clear: shadow's edge only in h1
    rows2 = ([row(SHADOW_BOT, t0 + i * (4 * day / 16), 0.02) for i in range(16)]
             + [row(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 16), -0.001)
                for i in range(16)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev2 = paired_eval(rows2, t0, end)
    assert not ev2["promote"] and "h2" in ev2["why"], ev2

    # margin gate: a 0.1pp edge is noise, not promotion
    rows3 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.003) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev3 = paired_eval(rows3, t0, end)
    assert not ev3["promote"] and "margin" in ev3["why"], ev3

    # floors: not enough closes -> not ready
    ev4 = paired_eval(rows[:10], t0, end)
    assert not ev4["promote"] and "floors" in ev4["why"], ev4

    # shadow must be positive in its own right (beating a very negative live
    # arm with a less-negative one is damage control, not edge)
    rows5 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), -0.001) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), -0.02) for i in range(12)])
    ev5 = paired_eval(rows5, t0, end)
    assert not ev5["promote"] and "own right" in ev5["why"], ev5

    # fade: live negative at n>=FADE_N since promotion -> release
    rows6 = [row(LIVE_BOT, t0 + i * 3600, -0.005) for i in range(20)]
    fading, n, m = fade_check(rows6, t0, t0 + 2 * day)
    assert fading and n == 20 and m < 0
    fading2, n2, _ = fade_check(rows6[:5], t0, t0 + 2 * day)
    assert not fading2 and n2 == 5, "below FADE_N: keep the promotion"

    # every candidate's levers are registered, in-bounds, and map to a live twin
    for c in CANDIDATES:
        for k, v in c["levers"].items():
            assert tuning.clamp(k, v) == v, (k, v)
            lk = XP_TO_LIVE[k]
            assert tuning.clamp(lk, v) == v, (lk, v)

    print("experiment_judge selftest OK (promote, lucky-half reject, margin, "
          "floors, own-right, fade, registry mapping)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
