#!/usr/bin/env python3
"""
fleet_radar.py — 📡 the fleet's edge RADAR: does each book have a real
destination, and how long until it gets there?

WHY (2026-07-23, operator). We proved the taker's price lenses are noise and the
Funding Farmer is the fleet's one plausible edge — using significance +
both-halves + concentration. This organ makes that ONE ruler STANDING, over
every book, refreshed continuously, so "feed / park / cull" writes itself.

NO SINGLE SENSOR IS TRUSTED — a lone t-stat lies (it flagged funding-carry as a
"REAL EDGE" when its whole t=2.23 was two lucky non-crypto trades; drop them and
it is 1.74, median NEGATIVE). So the map triangulates from a constellation:

  📡 RADAR      — significance: the per-trade t-stat (is the mean edge real?)
  🛰️ LIDAR      — temporal stability: the t-stat on each time-half (does the
                  edge hold across time, or is it one lucky half?)
  🌐 SATELLITE  — robustness: top-2-coin concentration + the JACKKNIFE t (drop
                  the single biggest trade and recompute — an edge that dies
                  when you remove one trade was never an edge)
  📶 STARLINK   — traffic: closes/day (the odometer — a book with no fuel can't
                  be diagnosed at all, only fed)
  🧭 ETA        — destination time: at the current effect size and trade rate,
                  how many MORE closes (and days) until the t-stat crosses the
                  |t|>=2 verdict line — or "no destination" when it isn't
                  converging. Honest by construction: a noise book's ETA is
                  never, because its mean is ~0 and no amount of n moves it.

PUBLISH-ONLY. It grades and publishes bot_state 'fleet-radar'; it enacts
nothing, proposes nothing, vetoes nothing. A thermometer, not a treatment.
Publishing is OPT-IN (--publish) so a bare run never writes the live bus.

THE VERDICT CLASSES (the map legend):
  real_edge · plausible · artifact · weak · noise · losing · starved
Only `plausible` and `real_edge` carry a real ETA — the rest have no
destination the current signal is driving toward.

  python3 fleet_radar.py            # print the map, no publish
  python3 fleet_radar.py --publish  # + write bot_state 'fleet-radar'
  python3 fleet_radar.py --selftest # offline, no net/DB
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

try:
    import bot_pnl_store as store
except Exception:      # noqa: BLE001 — offline (selftest) has no store
    store = None

KEY = "fleet-radar"
TTL_SEC = int(os.environ.get("RADAR_TTL_SEC", "5400"))
MIN_N = int(os.environ.get("RADAR_MIN_N", "15"))        # below this: STARVED, undiagnosable
T_VERDICT = float(os.environ.get("RADAR_T_VERDICT", "2.0"))  # |t| that settles it
CONC_CAP = float(os.environ.get("RADAR_CONC_CAP", "65"))     # top-2-coin % that flags concentration
JACK_FLOOR = float(os.environ.get("RADAR_JACK_FLOOR", "1.5"))  # jackknife t an edge must keep
ETA_MAX_TRADES = int(os.environ.get("RADAR_ETA_MAX", "1500"))  # beyond this = no realistic destination


# --------------------------------------------------------------------------
# PURE core (unit-tested via --selftest — no net, no DB)
# --------------------------------------------------------------------------
def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs):
    if not xs:
        return 0.0
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def _t(xs):
    """One-sample t-stat of the mean vs zero. 0.0 when undefined."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / n     # population sd (matches the fleet's other scorers)
    sd = math.sqrt(var)
    return (m / (sd / math.sqrt(n))) if sd > 0 else 0.0


def _eta(n, t, rate_per_day):
    """(more_trades, days, note) to cross |t|>=T_VERDICT at the CURRENT effect
    size and trade rate. Honest: the t-stat grows ~sqrt(n) only if the effect
    holds — a book that regresses (like the taker) never arrives, and its ETA
    says so rather than promising a false date."""
    at = abs(t)
    if at >= T_VERDICT:
        return 0, 0.0, "arrived — verdict reached (confirm robustness)"
    if at < 0.3:
        # mean indistinguishable from zero: no n moves it to significance
        return None, None, "no destination — not converging (noise)"
    # n scales as (T/t)^2 to reach the target t at a fixed effect size
    n_target = n * (T_VERDICT / at) ** 2
    more = max(0, int(math.ceil(n_target - n)))
    if more > ETA_MAX_TRADES:
        return None, None, "no realistic destination (too far at this effect size)"
    if not rate_per_day or rate_per_day <= 0:
        return more, None, f"{more} more closes — but IDLE (0/day): no ETA until it trades"
    days = more / rate_per_day
    return more, round(days, 1), f"~{more} more closes ≈ {days:.1f}d at {rate_per_day:.1f}/day"


def diagnose_book(bot, trades, now_ts=None):
    """PURE. trades: list of {profit_ratio, profit_abs, pair/coin, close_ts}.
    Returns the full multi-sensor reading + class + ETA for one book."""
    rets = [float(t["profit_ratio"]) for t in trades if t.get("profit_ratio") is not None]
    n = len(rets)
    abss = [float(t.get("profit_abs") or 0.0) for t in trades]
    net = round(sum(abss), 2)
    wins = sum(1 for a in abss if a > 0)

    # 📡 RADAR — significance
    t = _t(rets)
    med = _median(rets)     # the TYPICAL trade — the robust check the mean/t hides
    # 🛰️ LIDAR — temporal stability (both halves)
    mid = n // 2
    ta, tb = _t(rets[:mid]), _t(rets[mid:])
    both_pos = ta > 0 and tb > 0
    both_neg = ta < 0 and tb < 0
    # 🌐 SATELLITE — concentration + jackknife robustness
    bycoin = defaultdict(float)
    for tr in trades:
        c = (tr.get("coin") or str(tr.get("pair") or "").split("/")[0])
        bycoin[c] += float(tr.get("profit_abs") or 0.0)
    denom = sum(abs(v) for v in bycoin.values())
    top2 = sum(sorted((abs(v) for v in bycoin.values()), reverse=True)[:2])
    conc = round(100 * top2 / denom, 0) if denom else 0.0
    # jackknife: drop the single most extreme-|return| trade, recompute t
    if n >= 3:
        drop_i = max(range(n), key=lambda i: abs(rets[i]))
        jt = _t([r for i, r in enumerate(rets) if i != drop_i])
    else:
        jt = t
    # 📶 STARLINK — traffic (closes/day over the last 7d)
    rate = _rate_per_day(trades, now_ts)

    # --- classify from the CONSTELLATION, not one sensor ---
    if n < MIN_N:
        cls = "starved"
    elif t <= -T_VERDICT or (t < -1 and both_neg):
        cls = "losing"
    elif t >= T_VERDICT and (med <= 0 or jt < JACK_FLOOR or conc >= CONC_CAP):
        # significant MEAN, but the typical trade doesn't share it (a few
        # winners carrying losers) — the funding-carry false positive
        cls = "artifact"
    elif t >= T_VERDICT and both_pos and med > 0 and jt >= JACK_FLOOR and conc < CONC_CAP:
        cls = "real_edge"
    elif t >= 1.0 and both_pos and jt >= 1.0:
        cls = "plausible"
    elif abs(t) < 1.0:
        cls = "noise"
    else:
        cls = "weak"

    more, days, eta_note = _eta(n, t, rate)
    # the ETA must respect the CLASS — a starved book has NOT "arrived" however
    # high its tiny-n t (avo-maria n=3 t=4.5 is starved, not proven); a noise
    # book has no destination to time.
    if cls == "starved":
        need = MIN_N - n
        d2 = (need / rate) if rate and rate > 0 else None
        more, days = need, (round(d2, 1) if d2 is not None else None)
        eta_note = (f"feed +{need} closes to begin a read"
                    + (f" ≈ {d2:.0f}d at {rate:.1f}/day" if d2 is not None else " — IDLE (0/day)"))
    elif cls == "noise":
        more, days, eta_note = None, None, "no destination — not converging (noise)"
    elif cls == "losing" and t <= -T_VERDICT:
        more, days, eta_note = 0, 0.0, "verdict: significantly NEGATIVE — no edge here"
    return {
        "bot": bot, "class": cls, "n": n, "net": net,
        "win_pct": round(100 * wins / n) if n else 0,
        "radar_t": round(t, 2), "median_pct": round(med, 3),
        "lidar_t": [round(ta, 2), round(tb, 2)], "stable": bool(both_pos or both_neg),
        "jackknife_t": round(jt, 2), "conc_pct": conc,
        "rate_per_day": round(rate, 2),
        "eta_trades": more, "eta_days": days, "eta": eta_note,
    }


def _rate_per_day(trades, now_ts=None):
    now = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    recent = 0
    for tr in trades:
        ts = _parse_ts(tr.get("close_ts"))
        if ts is not None and 0 <= (now - ts) <= 7 * 86400:
            recent += 1
    return recent / 7.0


def _parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        z = str(s).strip().replace("Z", "+00:00")
        if z.endswith(" UTC"):
            z = z[:-4] + "+00:00"
        dt = datetime.fromisoformat(z)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


_ORDER = ["real_edge", "plausible", "artifact", "weak", "noise", "losing", "starved"]


def scan(all_trades, now_ts=None):
    """Group the fleet's closes by book and diagnose each. Returns the payload."""
    by_bot = defaultdict(list)
    for tr in all_trades:
        by_bot[tr.get("bot")].append(tr)
    books = [diagnose_book(b, trs, now_ts) for b, trs in by_bot.items() if b]
    books.sort(key=lambda d: (_ORDER.index(d["class"]) if d["class"] in _ORDER else 9,
                              -d["radar_t"]))
    summary = {c: [d["bot"] for d in books if d["class"] == c] for c in _ORDER}
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "ttl_sec": TTL_SEC,
        "params": {"min_n": MIN_N, "t_verdict": T_VERDICT, "conc_cap": CONC_CAP,
                   "jack_floor": JACK_FLOOR},
        "n_books": len(books),
        "summary": summary,
        "books": books,
    }


# --------------------------------------------------------------------------
# I/O shell
# --------------------------------------------------------------------------
def run_once(publish=False):
    if store is None:
        return None
    trades = store.fetch_paper_trades(limit=8000)
    # LIVING FLEET ONLY — retired bots' ledgers are archival (HL-era / pre-cut
    # data), not an actionable read. Exact-match the fleet's own retirement
    # authority so a living '-lshadow' port is never dropped by a base-name
    # collision. Fail-open: no list -> grade everything (the map just carries a
    # few archival rows, never silently blank).
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as _retired
        _retired = set(_retired)
    except Exception:      # noqa: BLE001
        _retired = set()
    trades = [t for t in trades if t.get("bot") not in _retired]
    # normalize a coin field once
    for tr in trades:
        tr["coin"] = str(tr.get("pair") or "").split("/")[0]
    payload = scan(trades)
    payload["excluded_retired"] = len(_retired)
    if publish:
        try:
            store.save_state(KEY, payload)
            store.save_history(KEY, {"summary": payload["summary"],
                                     "n_books": payload["n_books"],
                                     "updated": payload["updated"]})
        except Exception as e:      # noqa: BLE001
            print(f"[fleet-radar] publish failed: {e}", file=sys.stderr)
    return payload


_ICON = {"real_edge": "🟢", "plausible": "🟡", "artifact": "🟠", "weak": "⚪",
         "noise": "⚫", "losing": "🔴", "starved": "🌫️"}


def _report(payload):
    if not payload:
        print("[fleet-radar] no DB — nothing to scan"); return
    print(f"📡 FLEET RADAR — {payload['n_books']} books  ({payload['updated'][:16]})\n")
    print(f"{'':2s} {'class':10s} {'book':32s} {'n':>4} {'net$':>8} {'t':>6} "
          f"{'halves':>13} {'jk_t':>6} {'conc':>5} {'ETA':<34}")
    print("-" * 128)
    last = None
    for d in payload["books"]:
        if d["class"] != last:
            print(); last = d["class"]
        hv = f"[{d['lidar_t'][0]:+.1f},{d['lidar_t'][1]:+.1f}]"
        print(f"{_ICON.get(d['class'],'?'):2s} {d['class']:10s} {d['bot'][:32]:32s} "
              f"{d['n']:>4} {d['net']:>+8.2f} {d['radar_t']:>+6.2f} {hv:>13} "
              f"{d['jackknife_t']:>+6.2f} {d['conc_pct']:>4.0f}% {str(d['eta'])[:34]:<34}")


def _selftest():
    ok = []

    def _ck(cond, msg):
        ok.append(cond)
        if not cond:
            print(f"  ✗ {msg}")

    def mk(rets, coins=None, rate_days=0):
        # build trade dicts; spread closes over `rate_days*7` recent days so the
        # 7d rate is ~rate_days/... — we set close_ts directly for determinism
        now = 1_000_000.0
        coins = coins or ["A"] * len(rets)
        out = []
        for i, r in enumerate(rets):
            out.append({"profit_ratio": r, "profit_abs": r * 100,
                        "coin": coins[i % len(coins)], "pair": coins[i % len(coins)] + "/USDC",
                        "close_ts": now - 86400})    # all within 7d
        return out, now

    # 1. NOISE: mean ~0, |t|<1 -> class noise, ETA "no destination"
    tr, now = mk([0.01, -0.01, 0.012, -0.011, 0.009, -0.008] * 4)
    d = diagnose_book("noise-bot", tr, now)
    _ck(d["class"] == "noise", f"symmetric returns must be NOISE, got {d['class']} t={d['radar_t']}")
    _ck(d["eta_trades"] is None, f"noise must have NO ETA, got {d['eta']}")

    # 2. REAL EDGE: consistent positive, many coins, survives jackknife
    import random
    rets = [0.6, 0.5, 0.7, 0.55, 0.65, 0.5, 0.6, 0.7, 0.45, 0.6,
            0.55, 0.5, 0.62, 0.58, 0.66, 0.52, 0.6, 0.64, 0.5, 0.6]
    coins = [f"C{i}" for i in range(len(rets))]
    tr, now = mk(rets, coins)
    d = diagnose_book("edge-bot", tr, now)
    _ck(d["class"] == "real_edge", f"consistent broad positive must be REAL_EDGE, got {d['class']} t={d['radar_t']} jk={d['jackknife_t']} conc={d['conc_pct']}")
    _ck(d["eta_trades"] == 0, f"a t>=2 book has arrived (0 more), got {d['eta_trades']}")

    # 3. ARTIFACT: the funding-carry signature — mean POSITIVE and t>=2, but the
    # TYPICAL (median) trade is NEGATIVE: a few winners carrying many small
    # losers. Significant by the mean, hollow by the median.
    rets = [-0.1] * 30 + [2.0] * 10          # median -0.1, mean +0.425, t~3
    coins = [f"C{i}" for i in range(40)]     # spread across coins so conc doesn't trip it
    tr, now = mk(rets, coins)
    d = diagnose_book("artifact-bot", tr, now)
    _ck(d["radar_t"] >= 2.0 and d["median_pct"] < 0,
        f"fixture must be t>=2 with median<0, got t={d['radar_t']} med={d['median_pct']}")
    _ck(d["class"] == "artifact",
        f"significant-mean-but-negative-median must be ARTIFACT, got {d['class']}")

    # 4. PLAUSIBLE: positive both halves, t in [1,2) -> has a real ETA
    rets = [0.3, -0.1, 0.4, 0.2, -0.2, 0.5, 0.1, 0.35, -0.15, 0.3,
            0.25, -0.1, 0.4, 0.15, -0.2, 0.45, 0.1, 0.3, -0.1, 0.35]
    coins = [f"C{i%7}" for i in range(len(rets))]
    tr, now = mk(rets, coins)
    d = diagnose_book("plausible-bot", tr, now)
    _ck(d["class"] in ("plausible", "real_edge"), f"positive-both-halves must be plausible+, got {d['class']} t={d['radar_t']}")
    if d["class"] == "plausible":
        _ck(d["eta_trades"] and d["eta_trades"] > 0, f"a plausible book must have a forward ETA, got {d['eta']}")

    # 5. LOSING: consistently negative
    tr, now = mk([-0.3, -0.4, -0.2, -0.5, -0.3, -0.35, -0.25, -0.4, -0.3, -0.45,
                  -0.3, -0.4, -0.2, -0.5, -0.3, -0.35, -0.25, -0.4] )
    d = diagnose_book("losing-bot", tr, now)
    _ck(d["class"] == "losing", f"consistent negative must be LOSING, got {d['class']} t={d['radar_t']}")

    # 6. STARVED: n<MIN_N regardless of how good it looks
    tr, now = mk([2.0, 3.0, 2.5])   # huge but n=3
    d = diagnose_book("starved-bot", tr, now)
    _ck(d["class"] == "starved", f"n<{MIN_N} must be STARVED, got {d['class']}")

    # 7. ETA math: to double from t=1 to t=2 needs ~4x the n (n*(2/1)^2)
    more, days, note = _eta(50, 1.0, 5.0)
    _ck(more == 150, f"ETA from t=1,n=50 to t=2 must be 150 more (200-50), got {more}")
    _ck(abs(days - 30.0) < 0.1, f"150 more at 5/day must be 30d, got {days}")
    # idle book: has trades-to-verdict but no day estimate
    more2, days2, _ = _eta(50, 1.0, 0.0)
    _ck(more2 == 150 and days2 is None, "an idle book gets a trade count but no ETA days")

    if all(ok):
        print(f"fleet_radar selftest OK — {len(ok)} checks (noise/real/artifact/plausible/"
              "losing/starved classes, jackknife robustness, ETA math + idle)")
        return True
    print("fleet_radar SELFTEST FAILED")
    return False


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    pub = "--publish" in sys.argv
    p = run_once(publish=pub)
    if "--json" in sys.argv:
        print(json.dumps(p, indent=1, default=str))
    else:
        _report(p)
