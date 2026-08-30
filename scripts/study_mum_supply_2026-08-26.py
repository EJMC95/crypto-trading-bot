#!/usr/bin/env python3
"""STUDY: 👩 mum v2 supply widening — which cells she currently REFUSES have
exit-free forward excess over matched-random entries on Lighter's OWN 1h tape?
[2026-08-26, Eamon: "adjust to whatever enables more trades and less
restriction... tweak mum v2 so she doesnt miss anything too good."]

METHOD — PRE-DECLARED BEFORE ANY NUMBER WAS COMPUTED (I19; the (hl) precedent
says most "more trades" candidates are denominator shrinkage, so the bars and
the verdict logic are written here first and the data may not move them).

CELLS, each graded separately (all require v>0 on the signal bar, mum's own
entry conjunct; uptrend = e50>e200 on 1h, the bot's own ema_series):
  B  (control)   rsi14 < 25        AND NOT uptrend   -- her shipped cell
  C1 (rescue)    rsi14 < 20        AND     uptrend   -- "too good to miss"
  C2             rsi14 in [20,25)  AND     uptrend
  C3             rsi14 in [25,30)  AND NOT uptrend
  C4             rsi14 in [30,42)  AND NOT uptrend   -- the (qu) info region

DATA. Lighter's own 1h candles (/api/v1/candles, paged 500/bar-request), the
book's ACTUAL resolved universe — `lighter_family_bot`: mum has no coins
override, so `list(COINS) + NONCRYPTO_UNIVERSE` (15 crypto + 10 non-crypto =
25 symbols). Target 460 days; ACTUAL per-coin coverage is reported, never
assumed. Indicators are the bot's OWN `rsi_series` / `ema_series`, imported
verbatim (a second copy of a rule is a second rule, (hj)).

LAG-1 EVERYWHERE. A signal is read on the CLOSED bar i; entry is the OPEN of
bar i+1; the exit-free forward return at horizon h is open[i+1+h]/open[i+1]-1.
Warmup: i >= 210 (the bot's own min_bars — e200 needs >200 closed bars).

EPISODES, not ticks. Consecutive qualifying bars on one coin (for THAT cell)
collapse to ONE episode, entered at the first LAG-1 open. This is the same
dedup (qu)/(ri) used and it is what makes n honest.

STEP 1 — EXIT-FREE FIRST ((qu)'s own discipline: ~600 bracket sweeps failed
because there was no entry edge for any bracket to harvest). Forward returns
at h = 8, 12, 24 per cell.

STEP 2 — MATCHED-RANDOM NULL ((hm): a directional book is graded against
random entries, never zero). For each cell: DRAWS=1000 resamples; each draw
picks, PER COIN, the same number of random signal-bars (uniform over all
warmed-up bars with the horizon available, with replacement) and takes the
mean forward return. Reported per cell x horizon:
  excess%   = cell mean - mean of draw means
  t_cl      = cluster-robust t of per-episode excess (episode return minus
              its own coin's all-bar null mean at that horizon), clustered by
              COIN-DAY (UTC date of entry) via the cluster sandwich --
              golive_readiness.cluster_stats' estimator, reimplemented for
              arbitrary cluster keys:
              SE = sqrt(G/(G-1) * sum_g(sum_i (x_i - xbar))^2)/n
  P(rand>=cell) = fraction of draws whose mean >= the cell mean.

STEP 3 — RECENCY ((qu)'s decay finding): every cell is ALSO graded on the
trailing 120d alone. An all-history positive that is trailing-negative is
reported DECAYED, not as support.

STEP 4 — THE REAL BRACKET, only for cells whose exit-free excess is positive
with t_cl >= 1.5 at h=12 or h=24 (both windows considered; the verdict below
still requires both). mum's shipped bracket verbatim: roi ladder
{0:2.0%, 240:1.6%, 480:1.2%, 720:0.8%, 1080:0.4%, 1440:0}, stop -4%, 24h max
hold. LAG-1 bracket walk on 1h bars: entry AT the open of bar i+1, so the
entry bar's full range is genuinely post-entry (the (ml) convention -- no
pre-entry range is ever credited); rung boundaries are all multiples of 60min
so they land exactly on bar boundaries; when stop and roi are both touched in
one bar the STOP fires first (conservative); untouched by 1440min -> exit at
open[i+1+24] (max_hold at mark). Reported: mean%/trade, iid t, cluster t,
both chronological halves (split at the median entry index), episodes/day.

STEP 5 — SUPPLY. Episodes/day per cell over the full window, trailing 120d
and trailing 30d ("more trades" is quantified, not asserted). Baseline B must
reproduce (tm)'s scarcity (~1.1 episodes/day on the current tape vs the
founding 5.07/day) or the harness is not believed.

STEP 6 — I7/I20 OVERLAP. C1/C2 admit UPTREND entries, which narrows mum's
structural disjointness from 🙏 avo (SwingDip requires e50>e200 on 4h). For
every C1/C2 episode: does the last CLOSED 4h bar (aggregated from this same
1h tape, UTC 4h boundaries) satisfy avo's cell — e50>e200 AND rsi14<42 AND
close < BB_lo(20, 2sd over typical price, ddof=1) AND v>0? The count is an
UPPER bound on co-holding (avo's oracle gate additionally refuses ungraded
non-crypto, and slots/budget bind); it goes on the record per the directive.

VERDICT PER CELL, PRE-DECLARED:
  ADMIT      exit-free excess > 0 in BOTH windows (full + trailing 120d) with
             t_cl >= 1.5 at h=12 or h=24, AND the real-bracket result is
             positive in BOTH chronological halves.
  HYPOTHESIS positive but under one or more bars — state exactly which.
  REFUSE     flat or negative — state the number.
A refusal with evidence is a first-class outcome (CLAUDE.md standing rule).

Usage:  python3 scripts/study_mum_supply_2026-08-26.py
Cache:  $MUM_SUPPLY_CACHE (default: a tmp dir) — candles only, idempotent.
"""
import bisect
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lighter_family_bot as fb                     # rsi_series / ema_series / universe

B_URL = "https://mainnet.zklighter.elliot.ai"
CACHE = os.environ.get("MUM_SUPPLY_CACHE") or os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "mum_supply_cache_2026-08-26")

# ---- pre-declared constants (see header) ----------------------------------
DAYS = 460                       # target history; actual reported
WARMUP = 210                     # the bot's own min_bars
HORIZONS = (8, 12, 24)
DRAWS = 1000
SEED = 20260826
TRAIL_D = 120
T_BAR = 1.5                      # exit-free cluster-t bar for the bracket step
ROI = [(0, 0.020), (240, 0.016), (480, 0.012), (720, 0.008),
       (1080, 0.004), (1440, 0.0)]                  # mum's shipped ladder
STOP = -0.04
MAX_HOLD_BARS = 24
RSI_P = 14

CELLS = {
    "B":  ("rsi<25  & NOT-uptrend (shipped)", lambda r, up: r < 25 and not up),
    "C1": ("rsi<20  & uptrend (rescue)",      lambda r, up: r < 20 and up),
    "C2": ("rsi 20-25 & uptrend",             lambda r, up: 20 <= r < 25 and up),
    "C3": ("rsi 25-30 & NOT-uptrend",         lambda r, up: 25 <= r < 30 and not up),
    "C4": ("rsi 30-42 & NOT-uptrend",         lambda r, up: 30 <= r < 42 and not up),
}
CELL_ORDER = ["B", "C1", "C2", "C3", "C4"]

NOW = int(time.time())
TRAIL_TS = NOW - TRAIL_D * 86400


def _get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))


def _api(path, **q):
    return _get(B_URL + path + "?" + urllib.parse.urlencode(q))


def market_ids():
    p = os.path.join(CACHE, "mids.json")
    if os.path.exists(p):
        return json.load(open(p))
    m = {o["symbol"]: o["market_id"]
         for o in (_api("/api/v1/orderBookDetails").get("order_book_details") or [])
         if o.get("symbol")}
    json.dump(m, open(p, "w"))
    return m


def fetch_1h(sym, mid):
    """[(open_ts_s, o, h, l, c, v)] oldest-first; paged backward; cached."""
    p = os.path.join(CACHE, f"c1h_{sym}.json")
    if os.path.exists(p):
        return [tuple(r) for r in json.load(open(p))]
    out, end, seen, floor = {}, NOW, None, NOW - DAYS * 86400
    while True:
        d = _api("/api/v1/candles", market_id=mid, resolution="1h",
                 start_timestamp=max(floor, end - 500 * 3600),
                 end_timestamp=end, count_back=500)
        cs = (d or {}).get("c") or []
        if not cs:
            break
        for c in cs:
            out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                        float(c["l"]), float(c["c"]),
                                        float(c.get("v") or 0.0))
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= floor or (seen is not None and oldest >= seen):
            break
        seen, end = oldest, oldest - 3600
    rows = sorted((k, *v) for k, v in out.items() if k >= floor)
    json.dump(rows, open(p, "w"))
    return [tuple(r) for r in rows]


def cluster_t(xs, keys):
    """Cluster-sandwich t of mean(xs), clusters = distinct keys.

    [2026-08-26] DELEGATES to `golive_readiness.cluster_se`, which is now
    reachable with an ARBITRARY cluster key. This docstring used to say "same
    estimator as golive_readiness.cluster_stats, generalised to an arbitrary
    cluster key" — accurate about the intent, and the copy had already drifted
    in the direction that matters. MEASURED on a near-cancelling sample whose
    honest iid t is 1.94: this copy returned **t = 2.38e+16** while the owner
    returned None, because the owner carries the `(kg)` degenerate-t guard and
    the copy carried only `se > 0`. Not a contrived shape here — the guard
    fires when a cluster's demeaned values cancel, which is the DESIGN of a
    delta-neutral basket.

    The owner returns None where this returned nan; both are "not computable",
    and callers here already branch on a non-finite value.
    """
    try:
        sys.path.insert(0, HERE)
        import golive_readiness as _GR
    except Exception:                                     # noqa: BLE001
        return float("nan"), 0        # no owner -> no number, never a guess
    n = len(xs)
    if n < 2:
        return float("nan"), 0
    se, G, _mx = _GR.cluster_se(list(xs), list(keys))
    if se is None or not (se > 0):
        return float("nan"), G
    return (sum(xs) / n) / se, G


def iid_t(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) or 1e-12
    return m / (sd / math.sqrt(n))


def roi_thr(age_min):
    thr = ROI[0][1]
    for a, v in ROI:
        if age_min >= a:
            thr = v
    return thr


def bracket_walk(bars, e):
    """mum's real bracket from entry at open of bar index e. Returns
    (ret_pct, exit_reason) or None if the tape ends before resolution."""
    entry = bars[e][1]
    stop_px = entry * (1.0 + STOP)
    for k in range(e, min(e + MAX_HOLD_BARS, len(bars))):
        age = (k - e) * 60
        thr = roi_thr(age)
        tgt = entry * (1.0 + thr)
        hit_stop = bars[k][3] <= stop_px
        hit_roi = bars[k][2] >= tgt
        if hit_stop:                      # stop first when both touch (conservative)
            return STOP * 100.0, "stop"
        if hit_roi:
            return thr * 100.0, "roi"
    if e + MAX_HOLD_BARS >= len(bars):
        return None
    return (bars[e + MAX_HOLD_BARS][1] / entry - 1.0) * 100.0, "max_hold"


def agg_4h(bars):
    """UTC-aligned 4h bars from 1h: {open_ts4: (o,h,l,c,v)} + sorted keys."""
    out = {}
    for t, o, h, l, c, v in bars:
        k = t - (t % 14400)
        if k not in out:
            out[k] = [o, h, l, c, v, t]
        else:
            r = out[k]
            r[1] = max(r[1], h); r[2] = min(r[2], l)
            if t > r[5]:
                r[3], r[5] = c, t
            r[4] += v
    keys = sorted(out)
    return keys, {k: tuple(out[k][:5]) for k in keys}


def avo_cell_series(keys, b4):
    """Per-4h-bar bool: does the CLOSED bar satisfy avo's SwingDip entry cell
    (e50>e200 & rsi<42 & c<bb_lo & v>0)? Uses the bot's own indicator fns and
    SwingDip's own construction (typical price, 20-bar, 2 x stdev ddof=1)."""
    c = [b4[k][3] for k in keys]
    h = [b4[k][1] for k in keys]
    l = [b4[k][2] for k in keys]
    v = [b4[k][4] for k in keys]
    rsi = fb.rsi_series(c, RSI_P)
    e50, e200 = fb.ema_series(c, 50), fb.ema_series(c, 200)
    tp = [(h[j] + l[j] + c[j]) / 3.0 for j in range(len(c))]
    ok = [False] * len(c)
    for i in range(len(c)):
        if i < 230 or None in (rsi[i], e50[i], e200[i]):
            continue
        w = tp[i - 19:i + 1]
        bb_lo = sum(w) / 20.0 - 2.0 * fb.stdev(w)
        ok[i] = (e50[i] > e200[i] and rsi[i] < 42.0
                 and c[i] < bb_lo and v[i] > 0)
    return ok


def main():
    os.makedirs(CACHE, exist_ok=True)
    random.seed(SEED)
    universe = list(fb.COINS) + list(fb.NONCRYPTO_UNIVERSE)
    crypto = set(fb.COINS)
    mids = market_ids()
    missing = [s for s in universe if s not in mids]
    syms = [s for s in universe if s in mids]
    print(f"universe resolved from lighter_family_bot: {len(universe)} syms "
          f"({len(fb.COINS)} crypto + {len(fb.NONCRYPTO_UNIVERSE)} non-crypto); "
          f"unlisted on venue: {missing or 'none'}")

    with ThreadPoolExecutor(max_workers=6) as ex:
        tapes = dict(zip(syms, ex.map(lambda s: fetch_1h(s, mids[s]), syms)))
    spans = {s: (len(t), (t[-1][0] - t[0][0]) / 86400.0 if t else 0.0)
             for s, t in tapes.items()}
    days_by_sym = {s: d for s, (n, d) in spans.items()}
    print("tape coverage (bars, days): " +
          ", ".join(f"{s}:{n}b/{d:.0f}d" for s, (n, d) in sorted(spans.items())))
    max_days = max(d for _, d in spans.values())
    print(f"max span {max_days:.0f}d; NOW={datetime.fromtimestamp(NOW, timezone.utc).isoformat()}")

    # ---- per-coin signal prep --------------------------------------------
    sig = {}          # sym -> list of (i, ts_entry, rsi, up) for warmed bars
    fwd = {}          # sym -> {h: {i: ret}} forward returns keyed by signal bar
    elig = {}         # sym -> {h: [i...]} eligible signal bars for the null
    for s in syms:
        bars = tapes[s]              # tuple is (ts, o, h, l, c, v)
        if len(bars) < WARMUP + 30:
            continue
        closes = [b[4] for b in bars]
        vols = [b[5] for b in bars]
        rsi = fb.rsi_series(closes, RSI_P)
        e50, e200 = fb.ema_series(closes, 50), fb.ema_series(closes, 200)
        rows = []
        for i in range(WARMUP, len(bars) - 1):
            if None in (rsi[i], e50[i], e200[i]) or not vols[i] > 0:
                continue
            rows.append((i, bars[i + 1][0], rsi[i], e50[i] > e200[i]))
        sig[s] = rows
        fwd[s] = {}
        elig[s] = {}
        for h in HORIZONS:
            m, el = {}, []
            for (i, ts, r, up) in rows:
                if i + 1 + h < len(bars):
                    m[i] = (bars[i + 1 + h][1] / bars[i + 1][1] - 1.0) * 100.0
                    el.append(i)
            fwd[s][h] = m
            elig[s][h] = el

    # ---- episodes per cell ------------------------------------------------
    episodes = {cid: [] for cid in CELLS}       # (sym, i, ts_entry)
    for s in syms:
        if s not in sig:
            continue
        for cid, (_, pred) in CELLS.items():
            prev_i = None
            for (i, ts, r, up) in sig[s]:
                if pred(r, up):
                    if prev_i is None or i - prev_i > 1:
                        episodes[cid].append((s, i, ts))
                    prev_i = i
    for cid in CELL_ORDER:
        eps = episodes[cid]
        nc = sum(1 for s, i, t in eps if s in crypto)
        print(f"{cid}: {len(eps)} episodes ({nc} crypto / {len(eps)-nc} non-crypto)")

    # ---- exit-free grading ------------------------------------------------
    def grade(eps, window, only=None):
        """window: 'full' | 'trail' -> dict h -> metrics. only: coin filter —
        the CRYPTO-ONLY pass exists because the per-asset oracle gate refuses
        ungraded non-crypto in production, so shipped supply must not lean on
        entries the bot cannot actually take."""
        out = {}
        sel = [(s, i, t) for (s, i, t) in eps
               if (window == "full" or t >= TRAIL_TS)
               and (only is None or s in only)]
        for h in HORIZONS:
            rows = [(s, i, t) for (s, i, t) in sel if i in fwd.get(s, {}).get(h, {})]
            if len(rows) < 3:
                out[h] = {"n": len(rows)}
                continue
            rets = [fwd[s][h][i] for (s, i, t) in rows]
            # per-coin null means over the same window
            null_mu = {}
            per_coin_n = {}
            for (s, i, t) in rows:
                per_coin_n[s] = per_coin_n.get(s, 0) + 1
            for s in per_coin_n:
                pool = [j for j in elig[s][h]
                        if window == "full" or tapes[s][j + 1][0] >= TRAIL_TS]
                vals = [fwd[s][h][j] for j in pool]
                null_mu[s] = sum(vals) / len(vals) if vals else 0.0
            exc = [fwd[s][h][i] - null_mu[s] for (s, i, t) in rows]
            keys = [(s, t // 86400) for (s, i, t) in rows]
            tcl, G = cluster_t(exc, keys)
            # matched-random draws (pools built once per coin, not per draw)
            pools = {}
            for s in per_coin_n:
                pools[s] = [fwd[s][h][j] for j in elig[s][h]
                            if window == "full" or tapes[s][j + 1][0] >= TRAIL_TS]
            cell_mean = sum(rets) / len(rets)
            draw_means = []
            for _ in range(DRAWS):
                tot, cnt = 0.0, 0
                for s, k in per_coin_n.items():
                    pool = pools[s]
                    if not pool:
                        continue
                    for _k in range(k):
                        tot += random.choice(pool)
                        cnt += 1
                if cnt:
                    draw_means.append(tot / cnt)
            if draw_means:
                rand_mu = sum(draw_means) / len(draw_means)
                ge = sum(1 for d in draw_means if d >= cell_mean) / len(draw_means)
            else:
                rand_mu, ge = 0.0, float("nan")
            out[h] = {"n": len(rows), "mean": cell_mean, "rand": rand_mu,
                      "excess": cell_mean - rand_mu, "t_cl": tcl, "G": G,
                      "p_ge": ge}
        return out

    results = {}
    for cid in CELL_ORDER:
        results[cid] = {"full": grade(episodes[cid], "full"),
                        "trail": grade(episodes[cid], "trail"),
                        "full_crypto": grade(episodes[cid], "full", crypto),
                        "trail_crypto": grade(episodes[cid], "trail", crypto)}
        print(f"graded {cid}")

    # ---- supply rates ------------------------------------------------------
    rates = {}
    for cid in CELL_ORDER:
        eps = episodes[cid]
        full_days = max_days
        n30 = sum(1 for (_, _, t) in eps if t >= NOW - 30 * 86400)
        n120 = sum(1 for (_, _, t) in eps if t >= TRAIL_TS)
        c30 = sum(1 for (s, _, t) in eps if t >= NOW - 30 * 86400 and s in crypto)
        c120 = sum(1 for (s, _, t) in eps if t >= TRAIL_TS and s in crypto)
        rates[cid] = {"full": len(eps) / full_days if full_days else 0,
                      "d120": n120 / TRAIL_D, "d30": n30 / 30.0,
                      "c120": c120 / TRAIL_D, "c30": c30 / 30.0}

    # ---- bracket step ------------------------------------------------------
    brackets = {}
    qual = {}
    for cid in CELL_ORDER:
        ok = False
        for h in (12, 24):
            f, tr = results[cid]["full"].get(h, {}), results[cid]["trail"].get(h, {})
            if (f.get("excess", 0) > 0 and f.get("t_cl", 0) >= T_BAR):
                ok = True
        qual[cid] = ok
        if not ok:
            continue
        rows = []
        for (s, i, t) in episodes[cid]:
            r = bracket_walk(tapes[s], i + 1)
            if r is not None:
                rows.append((t, r[0], r[1], s))
        rows.sort()

        def summarise(rr):
            rets = [r[1] for r in rr]
            keys = [(r[3], r[0] // 86400) for r in rr]
            half = len(rr) // 2
            h1, h2 = rets[:half], rets[half:]
            reasons = {}
            for r in rr:
                reasons[r[2]] = reasons.get(r[2], 0) + 1
            tr_rows = [r for r in rr if r[0] >= TRAIL_TS]
            return {
                "n": len(rr), "mean": sum(rets) / len(rets) if rets else 0,
                "t": iid_t(rets), "t_cl": cluster_t(rets, keys)[0],
                "h1": sum(h1) / len(h1) if h1 else 0,
                "h2": sum(h2) / len(h2) if h2 else 0,
                "reasons": reasons,
                "trail_n": len(tr_rows),
                "trail_mean": (sum(r[1] for r in tr_rows) / len(tr_rows))
                              if tr_rows else 0}

        brackets[cid] = summarise(rows)
        brackets[cid + "_crypto"] = summarise([r for r in rows if r[3] in crypto])

    # ---- avo overlap (C1/C2) ----------------------------------------------
    overlap = {}
    avo_ok = {}
    for s in syms:
        keys4, b4 = agg_4h(tapes[s])
        ok = avo_cell_series(keys4, b4)
        avo_ok[s] = (keys4, ok)
    for cid in ("C1", "C2"):
        tot = hit = 0
        for (s, i, t) in episodes[cid]:
            keys4, ok = avo_ok[s]
            # last CLOSED 4h bar at entry time t: open_ts4 + 14400 <= t
            j = bisect.bisect_right(keys4, t - 14400) - 1
            if j < 0:
                continue
            tot += 1
            if ok[j]:
                hit += 1
        overlap[cid] = {"n": tot, "also_avo": hit,
                        "pct": 100.0 * hit / tot if tot else 0.0}

    # ---- report ------------------------------------------------------------
    print("\n===== EXIT-FREE RESULTS =====")
    for cid in CELL_ORDER:
        print(f"\n[{cid}] {CELLS[cid][0]}  episodes={len(episodes[cid])} "
              f"rate full/120d/30d = {rates[cid]['full']:.2f}/"
              f"{rates[cid]['d120']:.2f}/{rates[cid]['d30']:.2f} eps/day "
              f"(crypto-only 120d/30d = {rates[cid]['c120']:.2f}/"
              f"{rates[cid]['c30']:.2f})")
        for w in ("full", "trail", "full_crypto", "trail_crypto"):
            for h in HORIZONS:
                m = results[cid][w].get(h, {})
                if "mean" not in m:
                    print(f"  {w:12s} h={h:<3d} n={m.get('n',0)} (too few)")
                    continue
                print(f"  {w:12s} h={h:<3d} n={m['n']:<4d} mean={m['mean']:+.3f}% "
                      f"rand={m['rand']:+.3f}% excess={m['excess']:+.3f}% "
                      f"t_cl={m['t_cl']:+.2f} (G={m['G']}) P(rand>=cell)={m['p_ge']:.3f}")
    print("\n===== BRACKET (qualifying cells only) =====")
    for cid, b in brackets.items():
        print(f"[{cid}] n={b['n']} mean={b['mean']:+.3f}%/trade t={b['t']:+.2f} "
              f"t_cl={b['t_cl']:+.2f} halves {b['h1']:+.3f}/{b['h2']:+.3f} "
              f"exits={b['reasons']} trail120d n={b['trail_n']} "
              f"mean={b['trail_mean']:+.3f}%")
    for cid in CELL_ORDER:
        if not qual[cid]:
            print(f"[{cid}] did not qualify for the bracket step "
                  f"(exit-free excess/t_cl under bar)")
    print("\n===== AVO OVERLAP (C1/C2, upper bound) =====")
    for cid, o in overlap.items():
        print(f"[{cid}] {o['also_avo']}/{o['n']} episodes ({o['pct']:.1f}%) also "
              f"satisfy avo's 4h SwingDip cell at entry")
    print("\ndone.")
    return {"results": results, "rates": rates, "brackets": brackets,
            "overlap": overlap, "episodes": {k: len(v) for k, v in episodes.items()}}


if __name__ == "__main__":
    main()
