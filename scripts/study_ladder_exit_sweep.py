#!/usr/bin/env python3
"""
study_ladder_exit_sweep.py — the LADDER-AWARE exit replay (2026-08-19).

WHY THIS EXISTS
  `study_exit_sweep` expresses exactly {tp_pct, sl_pct, max_hold_h, trail_pct}:
  ONE fixed target, ONE fixed stop, ONE fixed trail. The family carriers do not
  exit that way, so `(ql)` DECLARED them unsweepable (`UNSWEEPABLE_EXITS`)
  rather than hand that harness a rule the book does not run — the `(ps)`
  false-pass. This is the build that declaration named as the only honest way
  to answer the question.

  THE QUESTION IT EXISTS TO ANSWER: the brain has published `exit_too_tight` on
  🔮 georgia in 129 of 129 runs for 8+ days — **reclaim 1.0** (every losing exit
  reclaimed its entry within 24h), forward **+1.63%**, trailing-stop path
  **-$17.14 over 71 era closes** against an roi path earning **+$17.70**. A
  measured direction with no instrument able to test it is the I18 shape.

WHAT IT MODELS — georgia's REAL exit set, read from the carrier, never retyped:
  1. ATR RATCHET   `stop_px = max(stop_px, px*(1-dist))`,
                   `dist = min(mult*atr/px, -stoploss)`, mult 3.5 for the
                   counter-trend tags else 2.5 (`atr_stop_dist`)
  2. ROI LADDER    continuous freqtrade form: newest rung <= age wins
  3. CUSTOM EXIT   bounce_take 1.2% / bounce_timeout 12h / max_hold 24h
  4. EXIT SIGNAL   **NOT MODELLED** — it needs the ENTRY strategy re-run, and
                   the sweep doctrine holds entries CONSTANT. Measured cost on
                   the replayable set: 2 of 33 rows (6%). Declared, not hidden;
                   those rows are REPORTED separately and never scored.

FIDELITY, declared because the bias runs INTO the path under test:
  * The live loop is 90s (`LOOP_SECONDS`) while the timeframe is 15m, so the
    real ratchet updates ~10x per bar off the current mark. Replay ratchets ONCE
    per bar off the bar HIGH, which is where ~10 samples would have taken it.
  * INTRABAR ORDER IS UNKNOWABLE, so the ADVERSE leg is taken first: the stop is
    tested against the PREVIOUS bar's level using this bar's LOW, and only then
    does the high ratchet it up. Assuming the favourable order is the classic
    way a backtest flatters itself.
  * LAG-1 entry ((ne)): the walk starts at the first bar OPENING at/after entry;
    a mid-bar entry forfeits its partial bar. Conservative.
  * P&L is compared as PRICE RETURN on both sides — replayed vs the row's own
    recorded entry/exit prices — so fees and funding never enter the comparison
    and cannot be mismodelled into the verdict.

PRE-REGISTERED RULES — written before any result existed:
  C1 CALIBRATION IS FAIL-CLOSED. Replay the SHIPPED rule over the replayable
     rows and compare the replayed mean price return to the ACTUAL mean price
     return of those same rows. |replayed - actual| must be <= CAL_TOL_PP
     (0.25pp) AND the replayed exit-reason mix must put `trailing_stop_loss`
     within +/-20pp of its actual share. Outside either, EVERY recommendation
     is WITHHELD. A harness that cannot reproduce what DID happen may not say
     what WOULD have.
  C2 n floor: >= 20 scored rows, else UNDECIDED (no verdict either way).
  C3 The sweep varies ONE family at a time: the ATR multiplier (the stop's
     width) and the stop cap. The ROI ladder is HELD at shipped — widening the
     stop and loosening the target at once cannot be attributed.
  C4 PLATEAU: a winning cell must have BOTH neighbours (by atr_mult) also beat
     shipped, else it is a lone spike and is refused ((pw) E4).
  C5 A recommendation must improve the mean price return AND not worsen the
     worst single trade by more than 1.0pp (a wider stop that merely defers
     ruin is not an improvement).
  C6 Report the reason MIX per cell. A cell that "wins" by converting stops
     into max_hold timeouts is holding losers longer; that must be visible.

READ-ONLY. Recommends nothing on its own authority; a candidate here is a
candidate for review, exactly as `study_exit_sweep`'s banner says.
"""

import argparse
import json
import math
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lighter_family_bot import (atr_series, live_strategies)  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
B = "https://mainnet.zklighter.elliot.ai"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ladder_cache")
CAL_TOL_PP = 0.25          # C1
MIX_TOL_PP = 20.0          # C1
MIN_N = 20                 # C2
RATCHET_FIRST = os.environ.get("LADDER_INTRABAR", "adverse") == "ratchet_first"
WARMUP_BARS = 40           # ATR-14 needs a warm start before the entry bar
HORIZON_BARS = 24 * 4 * 3  # 3 days of 15m bars is > any georgia max_hold


def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _cache(name, build):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    v = build()
    json.dump(v, open(p, "w"))
    return v


def market_ids():
    return _cache("mids", lambda: {
        o["symbol"]: o["market_id"]
        for o in (_get("/api/v1/orderBookDetails").get("order_book_details") or [])
        if o.get("symbol")})


def candles_15m(sym, mid, t_from, t_to):
    """{ts: (o,h,l,c)} at 15m, paged backward from t_to."""
    key = f"c15_{sym}_{int(t_from)}_{int(t_to)}"

    def build():
        out, end = {}, int(t_to)
        seen = None
        while True:
            cs = _get("/api/v1/candles", market_id=mid, resolution="15m",
                      start_timestamp=end - 500 * 900, end_timestamp=end,
                      count_back=500).get("c") or []
            if not cs:
                break
            for c in cs:
                out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                            float(c["l"]), float(c["c"]))
            oldest = min(int(c["t"]) // 1000 for c in cs)
            if oldest <= t_from or (seen is not None and oldest >= seen):
                break
            seen, end = oldest, oldest - 900
        return {str(k): v for k, v in out.items() if t_from <= k <= t_to}
    return {int(k): tuple(v) for k, v in _cache(key, build).items()}


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def split_tag_exit(reason):
    """('long-trend-breakout', 'trailing_stop_loss') from the ledger reason."""
    r = reason or ""
    if r.startswith(("long-", "short-", "long_", "short_")):
        tag, _sep, ex = r.partition("_")
        return tag, (ex or "trade")
    return None, r


def carrier_for(bot_row, include_retired=False):
    """The LIVE strategy object whose constants govern this row. Imported, never
    retyped — a retyped constant is a constant that drifts.

    [2026-09-02 (ws)] 🔮 georgia — the book this harness was built for — is
    RETIRED on both arms, so by default her row has NO carrier here: a retired
    book's replay is HISTORY and may not stand as a live baseline. Pass
    `include_retired=True` to read the constants off the retired carrier for a
    historical re-read; that path still reads the class, never a retyped copy.
    """
    base = bot_row.replace("-lshadow", "")
    for s in live_strategies():
        if s.bot == base:
            return s
    if include_retired:
        from lighter_family_bot import STRATEGIES
        for s in STRATEGIES:
            if s.bot == base:
                return s
    return None


def shipped_rule(carrier):
    return {
        "atr_mult_trend": 2.5,      # atr_stop_dist
        "atr_mult_counter": 3.5,
        "stop_cap": -carrier.stoploss,
        "roi": dict(carrier.roi),
        "bounce_take": 0.012,
        "bounce_timeout_min": 720,
        "max_hold_min": 1440,
    }


COUNTER_TAGS = ("bounce_pullback", "range_meanrev")


def walk(bars_ts, bars, entry_ts, entry_px, tag, rule):
    """Replay ONE position. -> (exit_ts, exit_px, why) or (None,None,'no-data').

    Adverse-first within a bar (see the fidelity note): test the stop on the
    LOW against the level standing from the previous bar, THEN ratchet on the
    HIGH, THEN test roi/timeouts on the CLOSE.
    """
    idx = [i for i, t in enumerate(bars_ts) if t >= entry_ts]
    if not idx or not entry_px:
        return None, None, "no-data"
    start = idx[0]
    atr = atr_series([bars[t][1] for t in bars_ts],
                     [bars[t][2] for t in bars_ts],
                     [bars[t][3] for t in bars_ts], 14)
    base = tag.split("-", 1)[-1] if tag else ""
    mult = (rule["atr_mult_counter"] if base in COUNTER_TAGS
            else rule["atr_mult_trend"])
    stop_px = 0.0
    for i in range(start, min(len(bars_ts), start + HORIZON_BARS)):
        t = bars_ts[i]
        o, h, l, c = bars[t]
        age_min = (t - entry_ts) / 60.0
        # THE INTRABAR CONVENTION IS AMBIGUOUS AND BOTH ARMS ARE RUN.
        # `adverse` (default) tests the standing stop on the LOW before the
        # HIGH ratchets it up — the classic conservative choice, and it
        # reproduces the exit MIX exactly (81% tsl vs 81% actual) while its
        # mean is 0.241pp off. `ratchet_first` mirrors the 90s loop actually
        # sampling ~10x per 15m bar, and reproduces the MEAN to 0.045pp while
        # overstating stop-outs (90% vs 81%). Neither dominates, so per the
        # (ne)/gillard precedent a verdict counts only if BOTH agree.
        if RATCHET_FIRST:
            a = atr[i]
            if a and h:
                dist = min(mult * a / h, rule["stop_cap"])
                stop_px = max(stop_px, h * (1 - dist))
            if stop_px and l <= stop_px:
                return t, stop_px, "trailing_stop_loss"
        else:
            if stop_px and l <= stop_px:
                return t, stop_px, "trailing_stop_loss"
            a = atr[i]
            if a and h:
                dist = min(mult * a / h, rule["stop_cap"])
                stop_px = max(stop_px, h * (1 - dist))
        # 3. targets on the close
        profit = (c - entry_px) / entry_px
        rungs = [k for k in rule["roi"] if k <= age_min]
        if rungs and profit >= rule["roi"][max(rungs)]:
            return t, c, "roi"
        if base == "bounce_pullback":
            if profit >= rule["bounce_take"]:
                return t, c, "bounce_take"
            if age_min >= rule["bounce_timeout_min"]:
                return t, c, "bounce_timeout"
        if age_min >= rule["max_hold_min"]:
            return t, c, "max_hold_timeout"
    return None, None, "horizon"


def load_rows(bot):
    d = _cache(f"led_{bot}", lambda: json.loads(urllib.request.urlopen(
        f"{DASH}/trades.json?source=paper&bot={bot}&limit=500", timeout=60).read()))
    rows = d if isinstance(d, list) else d.get("trades") or []
    out = []
    for r in rows:
        tag, ex = split_tag_exit(r.get("reason"))
        t0, t1 = parse_ts(r.get("opened_at")), parse_ts(r.get("closed_at"))
        ep, xp = r.get("entry_price"), r.get("exit_price")
        if not (ep and xp and r.get("side") and t0 and t1 and tag):
            continue
        out.append({"coin": (r.get("pair") or "").split("/")[0].split(":")[0],
                    "tag": tag, "exit": ex, "t0": t0, "t1": t1,
                    "entry": float(ep), "exit_px": float(xp),
                    "side": r.get("side"),
                    "actual_ret": (float(xp) / float(ep) - 1.0)})
    return out


def score(rows, bars_by_coin, rule):
    scored, mix, unmodelled = [], {}, 0
    for r in rows:
        if r["exit"] in ("range_top", "exit_signal"):
            unmodelled += 1
            continue
        bt = bars_by_coin.get(r["coin"])
        if not bt:
            continue
        ts, bars = bt
        xt, xp, why = walk(ts, bars, r["t0"], r["entry"], r["tag"], rule)
        if xp is None:
            continue
        mix[why] = mix.get(why, 0) + 1
        scored.append({"row": r, "ret": (xp / r["entry"] - 1.0), "why": why})
    return scored, mix, unmodelled


def summarize(scored):
    rets = [s["ret"] for s in scored]
    if not rets:
        return None
    return {"n": len(rets), "mean_pp": statistics.mean(rets) * 100,
            "total_pp": sum(rets) * 100, "worst_pp": min(rets) * 100}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="freqtrade-georgia-lshadow")
    a = ap.parse_args()

    carrier = carrier_for(a.book)
    if carrier is None:
        print(f"{a.book}: no LIVE carrier — retired or not a family book")
        return 2
    if not (getattr(carrier, "roi", None) or {}):
        print(f"{a.book}: carrier has no ROI ladder — use study_exit_sweep")
        return 2

    rows = load_rows(a.book)
    print(f"{a.book}: {len(rows)} replayable closes "
          f"(price+side+tag), carrier {type(carrier).__name__}")
    if not rows:
        return 2

    mids = market_ids()
    bars_by_coin = {}
    for coin in sorted({r["coin"] for r in rows}):
        if coin not in mids:
            print(f"  ! {coin}: not on the venue today — skipped")
            continue
        lo = min(r["t0"] for r in rows if r["coin"] == coin) - WARMUP_BARS * 900
        hi = max(r["t1"] for r in rows if r["coin"] == coin) + HORIZON_BARS * 900
        try:
            b = candles_15m(coin, mids[coin], lo, hi)
            if b:
                bars_by_coin[coin] = (sorted(b), b)
        except Exception as e:
            print(f"  ! {coin}: candles failed ({str(e)[:60]})")

    ship = shipped_rule(carrier)
    print(f"shipped rule: atr {ship['atr_mult_trend']}x/"
          f"{ship['atr_mult_counter']}x cap {ship['stop_cap']:.3f} "
          f"roi {ship['roi']} max_hold {ship['max_hold_min']}m")

    scored, mix, unmodelled = score(rows, bars_by_coin, ship)
    s = summarize(scored)
    if not s:
        print("nothing scored — no verdict")
        return 2
    actual = [x["row"]["actual_ret"] for x in scored]
    act_mean = statistics.mean(actual) * 100
    act_mix = {}
    for x in scored:
        act_mix[x["row"]["exit"]] = act_mix.get(x["row"]["exit"], 0) + 1

    print(f"\n=== C1 CALIBRATION (fail-closed) ===")
    print(f"  scored {s['n']} rows; {unmodelled} exit_signal rows EXCLUDED "
          f"(declared unmodelled)")
    print(f"  replayed mean {s['mean_pp']:+.3f}pp  vs  actual mean {act_mean:+.3f}pp"
          f"   delta {abs(s['mean_pp']-act_mean):.3f}pp (tol {CAL_TOL_PP})")
    rep_tsl = mix.get("trailing_stop_loss", 0) / max(1, s["n"]) * 100
    act_tsl = act_mix.get("trailing_stop_loss", 0) / max(1, s["n"]) * 100
    print(f"  replayed tsl share {rep_tsl:.0f}%  vs actual {act_tsl:.0f}%"
          f"   delta {abs(rep_tsl-act_tsl):.0f}pp (tol {MIX_TOL_PP})")
    print(f"  replayed mix {mix}")
    print(f"  actual   mix {act_mix}")

    ok_mean = abs(s["mean_pp"] - act_mean) <= CAL_TOL_PP
    ok_mix = abs(rep_tsl - act_tsl) <= MIX_TOL_PP
    ok_n = s["n"] >= MIN_N
    if not ok_n:
        print(f"\n  VERDICT: UNDECIDED — {s['n']} scored rows < {MIN_N} (C2). "
              f"No recommendation either way.")
        return 1
    if not (ok_mean and ok_mix):
        print(f"\n  VERDICT: CALIBRATION FAILED "
              f"(mean_ok={ok_mean} mix_ok={ok_mix}) — EVERY recommendation is "
              f"WITHHELD. A harness that cannot reproduce what DID happen may "
              f"not say what WOULD have.")
        return 1

    print("\n  CALIBRATION PASSED — the sweep may speak.")
    print(f"\n=== C3 SWEEP: the stop's WIDTH only (roi HELD at shipped) ===")
    base_mean = s["mean_pp"]
    results = []
    for m in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        r = dict(ship)
        r["atr_mult_trend"] = m
        r["atr_mult_counter"] = m + 1.0
        for cap in (ship["stop_cap"], ship["stop_cap"] * 1.5, ship["stop_cap"] * 2.0):
            r2 = dict(r); r2["stop_cap"] = cap
            sc, mx, _ = score(rows, bars_by_coin, r2)
            ss = summarize(sc)
            if not ss:
                continue
            results.append((m, cap, ss, mx))
            print(f"  atr {m:>4.1f}x cap {cap*100:>5.1f}%: n={ss['n']:3d} "
                  f"mean={ss['mean_pp']:+.3f}pp (shipped {base_mean:+.3f}) "
                  f"worst={ss['worst_pp']:+.2f}pp  mix={mx}")
    # ---- C4 plateau + C5 worst-trade, COMPUTED (a finding no gate consumes
    # is a note). Cells are grouped by atr_mult; the cap is reported inert
    # separately. A survivor must beat shipped AND have both atr neighbours
    # also beat shipped AND not worsen the worst trade by > 1.0pp.
    by_m = {}
    for m, cap, ss, mx in results:
        by_m.setdefault(m, []).append((cap, ss, mx))
    ms = sorted(by_m)
    base_worst = s["worst_pp"]
    beats = {m: (statistics.mean([x[1]["mean_pp"] for x in by_m[m]]) > base_mean)
             for m in ms}
    survivors = []
    for i, m in enumerate(ms):
        if m <= ship["atr_mult_trend"]:
            continue                      # widening only — the brain's direction
        if not beats[m]:
            continue
        nbrs = [ms[j] for j in (i - 1, i + 1) if 0 <= j < len(ms)]
        if not all(beats.get(n) for n in nbrs):
            continue                      # C4: lone spike
        worst = min(x[1]["worst_pp"] for x in by_m[m])
        if worst < base_worst - 1.0:
            continue                      # C5
        survivors.append(m)

    caps = {m: len({round(x[1]["mean_pp"], 6) for x in by_m[m]}) for m in ms}
    inert = all(v == 1 for v in caps.values())

    print("\n=== C4/C5 VERDICT ===")
    print(f"  widening cells beating shipped: "
          f"{[m for m in ms if m > ship['atr_mult_trend'] and beats[m]] or 'none'}")
    print(f"  surviving C4 plateau + C5 worst-trade: {survivors or 'NONE'}")
    print(f"  worst trade by atr_mult: "
          + ", ".join(f"{m}x {min(x[1]['worst_pp'] for x in by_m[m]):+.2f}pp"
                      for m in ms))
    if inert:
        print(f"  NOTE: the carrier stop cap ({ship['stop_cap']*100:.1f}%) is "
              f"INERT on this book — every cap value gives an identical result, "
              f"so `mult*atr/px` never reaches it. A constant that cannot bind "
              f"is not a lever (I18).")
    if not survivors:
        print("\n  VERDICT: NO WIDENING IS SUPPORTED. The brain's "
              "`exit_too_tight` direction is REFUTED on this book's own "
              "replayable ledger.")
    else:
        print(f"\n  VERDICT: CANDIDATE(S) {survivors} — for REVIEW, not "
              f"permission. Re-run under BOTH intrabar conventions "
              f"(LADDER_INTRABAR=adverse|ratchet_first) and ship only if both "
              f"agree ((ne) precedent).")
    print("\nREAD-ONLY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
