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
  👓 BIFOCAL    — two focal lengths: the far lens is the full-history class,
                  the near lens re-runs the SAME ladder on only the last
                  NEAR_D days. focus = fading (far good, near dead) /
                  emerging (far dead, near good) / blurry (near starved) /
                  consistent. The far average blurs regime change; the near
                  lens is where it shows first.

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
NEAR_D = float(os.environ.get("RADAR_NEAR_D", "45"))  # 👓 near-lens window (days)


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
    # sd > 1e-9, not > 0: identical values give a FLOAT-NOISE sd ~1e-17 (0.05
    # is not exactly representable), which would explode m/(sd/√n) to ~1e16. A
    # real pnl_pct sd is >1e-4, so the guard cleanly separates noise from signal.
    return (m / (sd / math.sqrt(n))) if sd > 1e-9 else 0.0


def _slope_t(xs):
    """t-stat of the OLS slope of xs against its own index (0..n-1) — is the
    per-trade return TRENDING up or down over the book's life? 0.0 undefined."""
    n = len(xs)
    if n < 3:
        return 0.0
    xbar = (n - 1) / 2.0
    ybar = _mean(xs)
    sxx = sum((i - xbar) ** 2 for i in range(n))
    sxy = sum((i - xbar) * (xs[i] - ybar) for i in range(n))
    if sxx <= 0:
        return 0.0
    b = sxy / sxx
    a = ybar - b * xbar
    sse = sum((xs[i] - (a + b * i)) ** 2 for i in range(n))
    if sse <= 0 or n <= 2:
        return 0.0
    se = math.sqrt((sse / (n - 2)) / sxx)
    return (b / se) if se > 1e-9 else 0.0     # float-noise se guard (see _t)


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


def _classify(n, t, med, both_pos, both_neg, jt, conc):
    """The ONE class ladder, shared by the far (full-history) and 👓 near
    (recent-window) lenses — two focal lengths must never grade on two rulers."""
    if n < MIN_N:
        return "starved"
    if t <= -T_VERDICT or (t < -1 and both_neg):
        return "losing"
    if t >= T_VERDICT and (med <= 0 or jt < JACK_FLOOR or conc >= CONC_CAP):
        # significant MEAN, but the typical trade doesn't share it (a few
        # winners carrying losers) — the funding-carry false positive
        return "artifact"
    if t >= T_VERDICT and both_pos and med > 0 and jt >= JACK_FLOOR and conc < CONC_CAP:
        return "real_edge"
    if t >= 1.0 and both_pos and jt >= 1.0:
        return "plausible"
    if abs(t) < 1.0:
        return "noise"
    return "weak"


def diagnose_book(bot, trades, now_ts=None):
    """PURE. trades: list of {profit_ratio, profit_abs, pair/coin, close_ts}.
    Returns the full multi-sensor reading + class + ETA for one book."""
    # OLDEST-FIRST — the ledger fetch is closed_at DESC (newest first), which
    # would invert every time-ordered read: the trajectory's "recent half" would
    # be the OLD half and a decaying edge would read as stable. Sort ascending so
    # rets[mid:] really is the recent half. (Missing close_ts -> 0, sorts first.)
    trades = sorted(trades, key=lambda tr: _parse_ts(tr.get("close_ts")) or 0.0)
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

    # 🧭 TRAJECTORY — velocity, not just position. The ETA below assumes a
    # CONSTANT effect size; a real radar tracks whether the target is CLOSING on
    # its destination or DRIFTING away. Measured 23-Jul: the Farmer's t=1.73 is
    # a fading average — thirds t 3.28/1.10/-0.54, recent-half median NEGATIVE —
    # so a constant-effect ETA projects convergence on an edge that already died.
    # Needs enough per-half depth to compare (>=12 each).
    traj, traj_delta, t_recent, med_recent, decay_ratio, slope_t = \
        "insufficient", None, None, None, None, None
    if n >= 24:
        rh = rets[mid:]                       # recent half, close-ordered
        t_recent, med_recent = _t(rh), _median(rh)
        traj_delta = round(t_recent - t, 2)
        m_full = _mean(rets)
        m_recent = _mean(rets[-min(15, mid):])
        decay_ratio = round(m_recent / m_full, 2) if m_full > 0 else None
        slope_t = round(_slope_t(rets), 2)
        _faded = (m_full > 0 and m_recent < 0.5 * m_full)   # recent < half the full mean
        # TREND GATE = slope_t, NOT traj_delta. traj_delta (t_recent - t_full)
        # compares a HALF-sample t-stat to a FULL-sample one, so it is biased
        # NEGATIVE by ~(1/sqrt2 - 1)*t from sample size ALONE — a same-level book
        # whose recent half is merely NOISIER (lower t, not lower mean) trips it
        # with zero real decay. Measured 23-Jul (Monte-Carlo): ~15% of
        # CONSTANT-effect books read "decaying" on traj_delta; slope_t (a
        # calibrated OLS-slope t-stat, ~N(0,1) under a constant effect, -14 on the
        # real Farmer shape) cuts that to ~2%. traj_delta stays a reported
        # diagnostic; it no longer gates the label. (Validate on the live Lighter
        # tape before trusting the label on a marginal book — synthetic-only here.)
        if slope_t is not None and slope_t <= -2.0 and (med_recent < 0 or _faded):
            traj = "decaying"
        elif slope_t is not None and slope_t >= 2.0 and med_recent > 0:
            traj = "emerging"
        else:
            traj = "stable"

    # 🌐 SATELLITE (deep) — pnl-weighted LEAVE-ONE/TWO-COIN-OUT. A count-based
    # HHI HIDES concentration; only removing the top coins' PnL exposes it. The
    # live Farmer's whole edge is ZEC+HYPE (drop them and t: 1.10 -> -0.32).
    # By COIN only — NEVER an exit-inclusive reason (a *_tp cell is
    # tautologically positive).
    coin_pnl = defaultdict(float)
    for tr in trades:
        c = (tr.get("coin") or str(tr.get("pair") or "").split("/")[0])
        if tr.get("profit_ratio") is not None:
            coin_pnl[c] += float(tr["profit_ratio"])
    ranked = sorted(coin_pnl, key=lambda c: coin_pnl[c], reverse=True)
    tot_pp = sum(coin_pnl.values())
    top_coin_share = round(max(coin_pnl.values()) / tot_pp, 2) if tot_pp > 0 else None

    def _t_drop(drop):
        keep = [float(tr["profit_ratio"]) for tr in trades
                if tr.get("profit_ratio") is not None
                and (tr.get("coin") or str(tr.get("pair") or "").split("/")[0]) not in drop]
        return _t(keep) if len(keep) >= 2 else 0.0
    loco_t1 = round(_t_drop(set(ranked[:1])), 2) if len(ranked) >= 2 else round(t, 2)
    loco_t2 = round(_t_drop(set(ranked[:2])), 2) if len(ranked) >= 3 else loco_t1

    # --- classify from the CONSTELLATION, not one sensor ---
    cls = _classify(n, t, med, both_pos, both_neg, jt, conc)

    # 👓 BIFOCAL — the NEAR lens: re-run the SAME ruler on only the last NEAR_D
    # days of closes. The far (full-history) class is an average that BLURS
    # regime change: a book that was good and is now dead, or was noise and is
    # now working, both read as their lifetime blend. The near lens is an
    # independent re-classification of the recent subpopulation — not a trend
    # statistic (that is the trajectory sensor) but a full class at short focal
    # length, with the same starved floor so a thin window can never overclaim.
    now = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    near_cut = now - NEAR_D * 86400
    near_trades = [tr for tr in trades
                   if (_parse_ts(tr.get("close_ts")) or 0.0) >= near_cut]
    nrets = [float(tr["profit_ratio"]) for tr in near_trades
             if tr.get("profit_ratio") is not None]
    nn = len(nrets)
    nt, nmed = _t(nrets), _median(nrets)
    nmid = nn // 2
    nta, ntb = _t(nrets[:nmid]), _t(nrets[nmid:])
    if nn >= 3:
        ndrop = max(range(nn), key=lambda i: abs(nrets[i]))
        njt = _t([r for i, r in enumerate(nrets) if i != ndrop])
    else:
        njt = nt
    ncoin = defaultdict(float)
    for tr in near_trades:
        c = (tr.get("coin") or str(tr.get("pair") or "").split("/")[0])
        ncoin[c] += abs(float(tr.get("profit_abs") or 0.0))
    ndenom = sum(ncoin.values())
    nconc = round(100 * sum(sorted(ncoin.values(), reverse=True)[:2]) / ndenom, 0) if ndenom else 0.0
    near_cls = _classify(nn, nt, nmed, nta > 0 and ntb > 0, nta < 0 and ntb < 0, njt, nconc)
    # FOCUS: how the two lenses disagree. 'blurry' when the near lens is
    # starved (thin recent window says nothing — never 'emerging' on tiny n).
    _GOOD, _BAD = ("plausible", "real_edge"), ("noise", "losing", "weak", "artifact")
    if near_cls == "starved" and cls != "starved":
        focus = "blurry"
    elif cls in _GOOD and near_cls in _BAD:
        focus = "fading"
    elif cls in _BAD and near_cls in _GOOD:
        focus = "emerging"
    else:
        focus = "consistent"

    # CAVEATS sharpen a plausible/real_edge verdict WITHOUT demoting the class
    # (per-book slopes are weak, |t|<1.1 — flag, don't overclaim). A "plausible"
    # book that is fading and/or carried by two coins is the live-Farmer trap.
    caveats = []
    if cls in ("plausible", "real_edge"):
        if traj == "decaying":
            caveats.append("fading")
        if (loco_t1 is not None and loco_t1 < 1.0) or \
           (loco_t2 is not None and loco_t2 < 1.0):
            caveats.append("2-coin")
    # 👓 a bifocal disagreement is a caveat on ANY class — the whole point is
    # that the far average hides it. 'blurry' is deliberately NOT flagged
    # (a thin recent window is normal for slow books, not a finding).
    if focus in ("fading", "emerging"):
        caveats.append(f"👓{focus}:near-{near_cls}")

    more, days, eta_note = _eta(n, t, rate)
    # the ETA must respect the CLASS and the TRAJECTORY — a starved book has NOT
    # "arrived" however high its tiny-n t; a noise book has no destination; and a
    # DECAYING edge must NEVER be shown a climbing ETA (the constant-effect lie).
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
    elif traj == "decaying":
        more, days, eta_note = None, None, "DIVERGING — effect shrinking; no verdict on this trajectory"
    return {
        "bot": bot, "class": cls, "n": n, "net": net,
        "win_pct": round(100 * wins / n) if n else 0,
        "radar_t": round(t, 2), "median_pct": round(med, 3),
        "lidar_t": [round(ta, 2), round(tb, 2)], "stable": bool(both_pos or both_neg),
        "jackknife_t": round(jt, 2), "conc_pct": conc,
        "rate_per_day": round(rate, 2),
        # 🧭 trajectory / velocity
        "trajectory": traj, "traj_delta": traj_delta,
        "t_recent": (round(t_recent, 2) if t_recent is not None else None),
        "median_recent_pct": (round(med_recent, 3) if med_recent is not None else None),
        "decay_ratio": decay_ratio, "slope_t": slope_t,
        # 🌐 concentration fragility
        "top_coin_share": top_coin_share, "loco_t1": loco_t1, "loco_t2": loco_t2,
        # 👓 bifocal — the near lens (last NEAR_D days) + the focus verdict
        "near_class": near_cls, "near_n": nn, "near_t": round(nt, 2),
        "near_median_pct": round(nmed, 3), "near_days": NEAR_D, "focus": focus,
        "caveats": caveats,
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
    # TWIN DEDUP — a live book and its own '-lshadow' control arm are ONE edge
    # (measured 23-Jul: +0.795 correlated, same coins same days). Never present
    # them as two independent plausible rows, and never let a consumer POOL
    # them (n=110, t=1.98 LOOKS like it clears |t|>=2 — a double-counted
    # mirage). Name-based, no correlation math: same base once the venue suffix
    # is stripped. The LIVE arm is authoritative; the shadow is tagged control.
    def _base(b):
        for suf in ("-lighter", "-lshadow"):
            if b.endswith(suf):
                return b[: -len(suf)]
        return b
    live_bases = {_base(d["bot"]) for d in books if str(d["bot"]).endswith("-lighter")}
    for d in books:
        b = d["bot"]
        if str(b).endswith("-lshadow") and _base(b) in live_bases:
            d["twin_of"] = _base(b) + "-lighter"     # its live authority
            d["twin_role"] = "control"
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
    print(f"{'':2s} {'class':10s} {'book':30s} {'n':>4} {'t':>6} {'tr':>2} "
          f"{'flags':>12} {'ETA':<44}")
    print("-" * 118)
    _ARR = {"decaying": "↓", "emerging": "↑", "stable": "→", "insufficient": "·"}
    last = None
    for d in payload["books"]:
        if d["class"] != last:
            print(); last = d["class"]
        flags = ",".join(d.get("caveats") or [])
        if d.get("twin_role") == "control":
            flags = (flags + " twin").strip(" ,") if flags else "twin"
        print(f"{_ICON.get(d['class'],'?'):2s} {d['class']:10s} {d['bot'][:30]:30s} "
              f"{d['n']:>4} {d['radar_t']:>+6.2f} {_ARR.get(d.get('trajectory'),'·'):>2} "
              f"{str(d.get('near_class', ''))[:8]:>8} "
              f"{('⚠'+flags if flags else ''):>22} {str(d['eta'])[:40]:<40}")


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

    # time-ordered fixture: close_ts increases with index so oldest sorts first
    def mkt(rets, coins=None):
        now = 1_000_000.0
        coins = coins or ["A"] * len(rets)
        nn = len(rets)
        out = [{"profit_ratio": r, "profit_abs": r * 100,
                "coin": coins[i % len(coins)], "pair": coins[i % len(coins)] + "/USDC",
                "close_ts": now - (nn - i) * 3600.0}   # oldest first, within nn hours
               for i, r in enumerate(rets)]
        return out, now

    # 8. TRAJECTORY DECAYING: strong-early, dead-late (the Farmer shape). The ETA
    # must NOT show a climbing verdict on a shrinking effect.
    tr, now = mkt([0.8] * 15 + [-0.3] * 15, [f"C{i%9}" for i in range(30)])
    d = diagnose_book("decay-bot", tr, now)
    _ck(d["trajectory"] == "decaying",
        f"strong-early/dead-late must be DECAYING, got {d['trajectory']} Δ={d['traj_delta']}")
    _ck("DIVERG" in d["eta"] or d["class"] in ("noise", "losing"),
        f"a decaying book must not show a climbing ETA, got {d['eta']}")

    # 9. INVERSION GUARD: reverse the SAME series (newest-first, as the ledger
    # fetch delivers) — the sort must recover the same decaying verdict, never
    # flip it to emerging.
    tr_rev = list(reversed(tr))
    d9 = diagnose_book("decay-bot-rev", tr_rev, now)
    _ck(d9["trajectory"] == "decaying",
        f"decay must survive a reversed fetch order (the closed_at DESC trap), got {d9['trajectory']}")

    # 9b. SLOPE-GATE (not the biased traj_delta): a SAME-LEVEL book whose recent
    # half is merely NOISIER — lower t, NOT lower mean — trips traj_delta<=-1 via
    # the half-vs-full sample-size bias, yet has ZERO real decay (slope_t~0). The
    # trend label must gate on slope_t and read STABLE. Reverting the gate to
    # traj_delta flips this to "decaying" — the ~15%->~2% false-positive fix.
    tr, now = mkt([0.5] * 12 + [-0.5, 2.5, -0.5, -0.5, 2.5, -0.5, -0.5, 2.5, -0.5, -0.5, 2.5, -0.5],
                  [f"C{i%9}" for i in range(24)])
    d9b = diagnose_book("noisy-recent-bot", tr, now)
    _ck(d9b["traj_delta"] <= -1.0 and d9b["median_recent_pct"] < 0,
        f"fixture must sit in traj_delta's false-positive zone, got Δ={d9b['traj_delta']} med={d9b['median_recent_pct']}")
    _ck(d9b["trajectory"] == "stable",
        f"same-level noisier-recent book must be STABLE (slope_t gate), not decaying; "
        f"got {d9b['trajectory']} slope_t={d9b['slope_t']} Δ={d9b['traj_delta']}")

    # 10. CONCENTRATION: one coin carries the edge -> dropping it collapses t.
    tr, now = mkt([0.05] * 20 + [3.0, 3.0, 3.0], ["A"] * 20 + ["MOON"] * 3)
    d = diagnose_book("conc-bot", tr, now)
    _ck(d["loco_t1"] < d["radar_t"],
        f"dropping the top-pnl coin must lower t, got loco1={d['loco_t1']} t={d['radar_t']}")

    # ---- 👓 BIFOCAL fixtures: explicit ages, so the near window really cuts --
    def mka(specs):
        """specs: list of (ret, coin, age_days). Oldest ages sort first."""
        now = 1_000_000.0
        out = [{"profit_ratio": r, "profit_abs": r * 100, "coin": c,
                "pair": c + "/USDC", "close_ts": now - age * 86400.0}
               for r, c, age in specs]
        return out, now

    # 12. FADING: a long good history (50-100d ago) + a clearly bad recent 20d.
    # Far lens: good (the average blurs the death). Near lens: losing. The
    # focus must say FADING — and near_n must be the WINDOWED count (18), which
    # is the mutation guard: break the window filter and near==far==consistent.
    old_good = [(0.6 + (0.05 if i % 2 else -0.05), f"C{i%9}", 50 + i) for i in range(60)]
    rec_bad = [(-0.2 + (0.1 if i % 2 else -0.1) / 2, f"C{i%9}", 1 + i) for i in range(18)]
    tr, now = mka(old_good + rec_bad)
    d12 = diagnose_book("fading-bot", tr, now)
    _ck(d12["class"] in ("real_edge", "plausible", "artifact") and d12["class"] != "starved",
        f"fading fixture's FAR lens must read good-ish on the lifetime blend, got {d12['class']}")
    _ck(d12["near_n"] == 18,
        f"near lens must see ONLY the {NEAR_D:.0f}d window (18 closes), got {d12['near_n']}")
    _ck(d12["near_class"] in ("losing", "noise", "weak") and d12["focus"] == "fading",
        f"good-far/dead-near must be FADING, got near={d12['near_class']} focus={d12['focus']}")
    _ck(any(c.startswith("👓fading") for c in d12["caveats"]),
        f"a fading book must carry the 👓 caveat, got {d12['caveats']}")

    # 13. EMERGING: a dead history + a strong recent 20d. Far: bad. Near: good.
    old_dead = [(-0.02 + (0.1 if i % 2 else -0.1), f"C{i%9}", 50 + i) for i in range(60)]
    rec_good = [(0.5 + (0.06 if i % 2 else -0.06), f"C{i%9}", 1 + i) for i in range(20)]
    tr, now = mka(old_dead + rec_good)
    d13 = diagnose_book("emerging-bot", tr, now)
    _ck(d13["near_class"] in ("real_edge", "plausible") and d13["focus"] == "emerging",
        f"dead-far/strong-near must be EMERGING, got far={d13['class']} "
        f"near={d13['near_class']} focus={d13['focus']}")

    # 14. BLURRY, the anti-overclaim: 3 huge recent closes must NOT read
    # emerging — a near window under MIN_N is starved, so the focus is blurry.
    old_ok = [(0.35 + (0.04 if i % 2 else -0.04), f"C{i%9}", 60 + i) for i in range(40)]
    rec_tiny = [(2.0, "M", 2), (2.2, "N", 4), (1.8, "O", 6)]
    tr, now = mka(old_ok + rec_tiny)
    d14 = diagnose_book("blurry-bot", tr, now)
    _ck(d14["near_class"] == "starved" and d14["focus"] == "blurry",
        f"a 3-close near window must be STARVED/blurry, never emerging; "
        f"got near={d14['near_class']} focus={d14['focus']}")
    _ck(not any("emerging" in c for c in d14["caveats"]),
        f"blurry must not carry an emerging caveat, got {d14['caveats']}")

    # 11. TWIN DEDUP: a -lshadow with a live -lighter base is tagged control.
    live_tr, now = mkt([0.5] * 20, [f"C{i}" for i in range(20)])
    shad_tr, _ = mkt([0.4] * 20, [f"C{i}" for i in range(20)])
    pay = scan([dict(t, bot="foo-lighter") for t in live_tr]
               + [dict(t, bot="foo-lshadow") for t in shad_tr])
    twin = [b for b in pay["books"] if b["bot"] == "foo-lshadow"][0]
    _ck(twin.get("twin_role") == "control" and twin.get("twin_of") == "foo-lighter",
        f"a -lshadow twin of a live book must be tagged control, got {twin.get('twin_role')}")

    if all(ok):
        print(f"fleet_radar selftest OK — {len(ok)} checks (noise/real/artifact/plausible/"
              "losing/starved classes, jackknife robustness, ETA math + idle, trajectory "
              "decay + inversion + slope-gate, coin-concentration, twin-dedup, "
              "👓bifocal fading/emerging/blurry)")
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
