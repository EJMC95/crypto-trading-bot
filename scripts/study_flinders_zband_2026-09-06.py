#!/usr/bin/env python3
"""
scripts/study_flinders_zband_2026-09-06.py — STEP 0 of the ⚓ nav-flinders design.

THE QUESTION
  🧭 nav-cook trades an ABSOLUTE dislocation band, [45,60) bps. The flinders
  design's whole premise is that an absolute band is the wrong unit: a market
  whose own residual sigma is 4bps has a 5-sigma dislocation at 20bps that no
  absolute band in this fleet can see. So: does NORMALISING the residual by the
  market's own scale sort the reversion edge BETTER than absolute bps?

  The book is NOT built unless this clears the bars pre-registered in the design
  spec. A refusal is a valid, publishable output.

THE DATA WALL, MEASURED AND DECLARED FIRST (this governs how the answer reads)
  The scout's `prem_outliers` is HARD-CAPPED at TOP_N=8 per snapshot, RANKED BY
  ABSOLUTE |prem_bps| among liquid books. That cap is not a nuisance here, it is
  adverse to the exact hypothesis under test: a small-sigma market having a large
  SIGMA-event at a small ABSOLUTE premium is precisely what a top-8-by-absolute
  list excludes. Measured on this tape: the smallest observed |prem_bps| is
  ~9.5 while the venue-wide MEDIAN residual is ~3.5bps (`stress.med`), i.e. the
  observable sample begins near the venue's own p90.

  Consequences, both ways:
    * A POSITIVE finding here is CONSERVATIVE. Any normalisation advantage that
      survives inside a sample selected on absolute size is a lower bound on the
      advantage over the full surface.
    * A NULL finding here CANNOT refute the design, because the population the
      design targets is not in the sample. It refutes only "normalisation helps
      among already-large absolute dislocations".
  Neither reading is available until the scout publishes its FULL per-market
  residual vector instead of the top 8 — see the (ye) entry, which measures what
  that would cost (~2.5KB on a 37.8KB payload) and why it is the named next step
  rather than something this pass widened on the way past. Until then this
  script's verdict is reported with the truncation scope attached, never without.

  The venue exposes NO historical index series: /api/v1/candles ignores every
  candlestick_type / price_type / source / kind value tested, INCLUDING bogus
  ones (byte-identical responses), so the residual cannot be reconstructed
  historically. Substituting another venue's spot as the index is banned
  outright (CLAUDE.md: BACKTEST ON LIGHTER ONLY). Hence the proxy below.

THE SCALE PROXY, AND ITS OWN TEST
  sigma_price(m) = stdev of 5-minute log returns over the trailing 14d, in bps.
  Fully available from Lighter's own candles for every market, historically.
  It is a PROXY for residual sigma and is not assumed: Test A measures whether
  it predicts a market's observable residual scale. If it does not, the
  normalisation premise is weak and this script says so.

CONVENTIONS, NAMED (each is a place two honest replays diverge) — the nav-cook
study's own discipline, kept:
  C1 SIGNAL SOURCE  the scout's `prem_outliers`, top-8 by |prem_bps|. See above.
  C2 CONFIRM/LAG    entry is LAGGED 600s from the observation (the (sa)
                    correction: the founding study lagged 2 SNAPSHOTS of a
                    5-min tape = 600s, NOT 2 loops of a 90s bot).
  C3 EPISODES       one open position per symbol at a time; forward return read
                    from the market's own 5m closes; no position cap (this is a
                    signal study, not a portfolio replay).
  C4 SIDE           MIRROR: short a premium, long a discount.
  C5 COST           one round trip of the book's own slippage, by volume tier
                    from the (js)/(qq) fill study, charged on every episode.
  C6 CLUSTERING     episodes overlap heavily (same symbol, adjacent snapshots),
                    so the naive iid t is inflated. Every headline carries a
                    cluster-robust t by SYMBOL and by UTC DAY. The DAY number
                    is the one that governs, per (xy)/(vr).

Read-only. No bot, no orders, no writes, no DB.
Usage:
    python3 scripts/study_flinders_zband_2026-09-06.py --fetch     # cache tape
    python3 scripts/study_flinders_zband_2026-09-06.py             # run
    python3 scripts/study_flinders_zband_2026-09-06.py --selftest
"""
import argparse
import json
import math
import os
import pickle
import random
import statistics as st
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

LIGHTER_API = "https://mainnet.zklighter.elliot.ai"
BUS = "https://pnl-dashboard-production-858c.up.railway.app/bus.json"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".flinders_zband_cache.pkl")

ENTRY_LAG_S = 600           # C2
HOLDS_S = [1800, 3600, 7200, 14400, 28800]
VOL_WINDOW_D = 14           # sigma_price warm-up
MIN_VOL_BARS = 300          # spec 2.1 rule 6: fewer is UNKNOWN, never assumed
SIGMA_FLOOR_BPS = 2.0       # spec 2.2
HARD_STOP = 0.04            # spec 2.4


def slip_bps(vol_m):
    """(js)/(qq): MEAN bps per fill by daily volume tier. A continuous strategy
    pays the average of its fills, not the median."""
    return (0.61 if vol_m >= 10 else 1.18 if vol_m >= 2 else
            5.35 if vol_m >= 1 else 2.52 if vol_m >= 0.1 else 17.49)


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------
def _get_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_all(hours=720):
    """Scout tape off the PUBLIC /bus.json (no DB, no railway CLI), plus the
    venue's own 5m closes for every symbol the tape names."""
    print(f"[fetch] bus.json?hours={hours} ...", flush=True)
    d = _get_json(f"{BUS}?hours={hours}", timeout=180)
    hist = [r for r in (d.get("history") or [])
            if r.get("key") == "lighter-market"]
    obs, vols, classes = [], {}, {}
    for r in hist:
        p = r.get("payload") or {}
        for o in (p.get("prem_outliers") or []):
            if not isinstance(o, dict):
                continue
            s, b = o.get("sym"), o.get("prem_bps")
            if s is None or b is None:
                continue
            obs.append((r["ts"], s, float(b), o.get("vol_m")))
        vols.update(p.get("vols") or {})
        classes.update(p.get("classes") or {})
    print(f"[fetch] snapshots={len(hist)} observations={len(obs)} "
          f"symbols={len({o[1] for o in obs})}", flush=True)

    books = _get_json(f"{LIGHTER_API}/api/v1/orderBookDetails", timeout=60)
    rows = books.get("order_book_details") or books.get("orderBookDetails") or []
    meta = {}
    for b in rows:
        s, mid = b.get("symbol"), b.get("market_id")
        if s is None or mid is None:
            continue
        meta[s] = {"id": int(mid),
                   "vol": float(b.get("daily_quote_token_volume") or 0.0),
                   "mmf": int(b.get("maintenance_margin_fraction") or 0),
                   "status": b.get("status")}

    need = sorted({o[1] for o in obs})
    end = int(time.time())
    start = end - 24 * 24 * 3600            # 14d warm-up + ~9d tape + buffer

    def one(sym):
        mid = meta[sym]["id"]
        out, t = {}, start
        while t < end:
            e = min(t + 500 * 300, end)
            url = (f"{LIGHTER_API}/api/v1/candles?market_id={mid}"
                   f"&resolution=5m&start_timestamp={t}&end_timestamp={e}"
                   f"&count_back=500")
            for attempt in range(4):
                try:
                    for c in (_get_json(url, timeout=30).get("c") or []):
                        out[int(c["t"]) // 1000] = float(c["c"])
                    break
                except Exception:
                    time.sleep(1.5 * (attempt + 1))
            t = e
        return sym, out

    candles = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, (s, o) in enumerate(ex.map(one, [s for s in need if s in meta])):
            candles[s] = o
            if i % 20 == 0:
                print(f"[fetch] candles {i}/{len(need)} {s} bars={len(o)}",
                      flush=True)
    blob = {"obs": obs, "vols": vols, "classes": classes,
            "meta": meta, "candles": candles}
    with open(CACHE, "wb") as fh:
        pickle.dump(blob, fh)
    print(f"[fetch] cached -> {CACHE}", flush=True)
    return blob


def load():
    if not os.path.exists(CACHE):
        return fetch_all()
    with open(CACHE, "rb") as fh:
        return pickle.load(fh)


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def tstat(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    n = len(xs)
    if n < 3:
        return (n, float("nan"), float("nan"))
    m = st.mean(xs)
    sd = st.pstdev(xs) * math.sqrt(n / (n - 1.0)) if n > 1 else 0.0
    if sd <= 0:
        return (n, m, float("nan"))
    return (n, m, m / (sd / math.sqrt(n)))


def cluster_t(pairs):
    """Cluster-robust t by group: the group MEANS are the observations.
    pairs = [(group_key, value)]. This is the (xy)/(ky) convention."""
    g = defaultdict(list)
    for k, v in pairs:
        if v is not None and math.isfinite(v):
            g[k].append(v)
    means = [st.mean(v) for v in g.values() if v]
    return tstat(means)


def pearson(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys)
           if x is not None and y is not None
           and math.isfinite(x) and math.isfinite(y)]
    if len(pts) < 3:
        return float("nan")
    xs2 = [p[0] for p in pts]
    ys2 = [p[1] for p in pts]
    mx, my = st.mean(xs2), st.mean(ys2)
    num = sum((a - mx) * (b - my) for a, b in pts)
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs2))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys2))
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    pts = [(x, y) for x, y in zip(xs, ys)
           if x is not None and y is not None
           and math.isfinite(x) and math.isfinite(y)]
    if len(pts) < 3:
        return float("nan")
    return pearson(rank([p[0] for p in pts]), rank([p[1] for p in pts]))


# --------------------------------------------------------------------------
# series helpers
# --------------------------------------------------------------------------
def build_series(candles):
    """{sym: (sorted_ts_list, price_list)} for O(log n) as-of lookups."""
    out = {}
    for s, m in candles.items():
        if not m:
            continue
        ks = sorted(m)
        out[s] = (ks, [m[k] for k in ks])
    return out


def price_at(series, sym, ts, max_gap_s=1800):
    """Most recent close at or before ts. None if the gap is too wide — a stale
    price is not a price (I1)."""
    e = series.get(sym)
    if not e:
        return None
    ks, ps = e
    import bisect
    i = bisect.bisect_right(ks, ts) - 1
    if i < 0 or ts - ks[i] > max_gap_s:
        return None
    return ps[i]


def sigma_price_bps(series, sym, end_ts, window_d=VOL_WINDOW_D):
    """stdev of 5m log returns over the trailing window, expressed in bps.
    Returns None below MIN_VOL_BARS — UNKNOWN, never assumed (spec 2.1 r6)."""
    e = series.get(sym)
    if not e:
        return None
    ks, ps = e
    lo = end_ts - window_d * 86400
    import bisect
    i0 = bisect.bisect_left(ks, lo)
    i1 = bisect.bisect_right(ks, end_ts)
    seg = ps[i0:i1]
    if len(seg) < MIN_VOL_BARS:
        return None
    rets = []
    for a, b in zip(seg, seg[1:]):
        if a > 0 and b > 0:
            rets.append(math.log(b / a))
    if len(rets) < MIN_VOL_BARS - 1:
        return None
    sd = st.pstdev(rets)
    return sd * 1e4 if sd > 0 else None


# --------------------------------------------------------------------------
# episode construction
# --------------------------------------------------------------------------
def parse_ts(s):
    return int(time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) -
               time.timezone)


def build_episodes(blob, series, direction="mirror"):
    """One episode per (symbol, observation), lagged ENTRY_LAG_S, forward
    returns at every horizon, net of the tier's own round-trip slippage.

    direction: 'mirror' (short premium / long discount) or 'ghost'
    (continuation — the control that must LOSE)."""
    obs = blob["obs"]
    vols = blob["vols"]
    classes = blob["classes"]
    eps = []
    for ts_s, sym, prem, vol_m in obs:
        ts = parse_ts(ts_s)
        ent_ts = ts + ENTRY_LAG_S
        p_ent = price_at(series, sym, ent_ts)
        if not p_ent or p_ent <= 0:
            continue
        sig = sigma_price_bps(series, sym, ts)
        if sig is None:
            continue
        v = vols.get(sym)
        v_m = float(v) if isinstance(v, (int, float)) else (vol_m or 0.0)
        cost = 2.0 * slip_bps(v_m) / 1e4       # round trip, as a fraction
        is_long = (prem < 0)
        if direction == "ghost":
            is_long = not is_long
        rec = {"ts": ts, "sym": sym, "prem": prem, "abs_prem": abs(prem),
               "sigma": max(sig, SIGMA_FLOOR_BPS), "vol_m": v_m,
               "cls": classes.get(sym), "is_long": is_long,
               "day": time.strftime("%Y-%m-%d", time.gmtime(ts)),
               "cost": cost, "entry": p_ent}
        rec["z"] = rec["abs_prem"] / rec["sigma"]
        ok = False
        for h in HOLDS_S:
            p_ex = price_at(series, sym, ent_ts + h)
            if not p_ex or p_ex <= 0:
                rec[f"r{h}"] = None
                continue
            raw = (p_ex / p_ent - 1.0)
            if not is_long:
                raw = -raw
            rec[f"r{h}"] = (raw - cost) * 100.0     # percent, net
            ok = True
        if ok:
            eps.append(rec)
    return eps


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def line(label, xs, days=None, syms=None, width=26):
    n, m, t = tstat(xs)
    out = f"  {label:<{width}} n={n:>6} mean={m:+.4f}% t={t:+.2f}"
    if days is not None:
        _, _, td = cluster_t(days)
        out += f" t_day={td:+.2f}"
    if syms is not None:
        _, _, tsy = cluster_t(syms)
        out += f" t_sym={tsy:+.2f}"
    return out


def horizon_table(eps, title):
    print(f"\n{title}")
    for h in HOLDS_S:
        xs = [e[f"r{h}"] for e in eps if e.get(f"r{h}") is not None]
        days = [(e["day"], e[f"r{h}"]) for e in eps if e.get(f"r{h}") is not None]
        syms = [(e["sym"], e[f"r{h}"]) for e in eps if e.get(f"r{h}") is not None]
        print(line(f"{h//60:>4}m", xs, days, syms, width=6))


def strata(eps, key, edges, h, label):
    print(f"\n  by {label} @ {h//60}m:")
    for lo, hi in zip(edges, edges[1:]):
        sel = [e for e in eps
               if lo <= e[key] < hi and e.get(f"r{h}") is not None]
        if len(sel) < 20:
            print(f"    [{lo:>6.1f},{hi:>6.1f})  n={len(sel):>5}  (below floor)")
            continue
        xs = [e[f"r{h}"] for e in sel]
        n, m, t = tstat(xs)
        _, _, td = cluster_t([(e["day"], e[f"r{h}"]) for e in sel])
        print(f"    [{lo:>6.1f},{hi:>6.1f})  n={n:>5}  mean={m:+.4f}%  "
              f"t={t:+.2f}  t_day={td:+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--hours", type=int, default=720)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    blob = fetch_all(a.hours) if a.fetch else load()
    series = build_series(blob["candles"])

    print("=" * 78)
    print("STEP 0 — does sigma-normalisation sort the dislocation edge better")
    print("         than absolute bps?   (scope: TOP-8 TRUNCATED SAMPLE)")
    print("=" * 78)

    eps = build_episodes(blob, series, "mirror")
    ghost = build_episodes(blob, series, "ghost")
    if not eps:
        print("NO EPISODES — cache is empty or stale; run --fetch")
        return 1
    print(f"\nepisodes={len(eps)}  symbols={len({e['sym'] for e in eps})}  "
          f"days={len({e['day'] for e in eps})}")
    sg = sorted(e["sigma"] for e in eps)
    zz = sorted(e["z"] for e in eps)
    print(f"sigma_price bps: p10={sg[len(sg)//10]:.1f} med={sg[len(sg)//2]:.1f} "
          f"p90={sg[9*len(sg)//10]:.1f}  ratio p90/p10="
          f"{sg[9*len(sg)//10]/max(sg[len(sg)//10],1e-9):.1f}x")
    print(f"z = |prem|/sigma: p10={zz[len(zz)//10]:.2f} med={zz[len(zz)//2]:.2f} "
          f"p90={zz[9*len(zz)//10]:.2f}")

    # --- TEST A: is sigma_price a valid scale proxy? ----------------------
    print("\n" + "-" * 78)
    print("TEST A — does sigma_price predict a market's OBSERVABLE residual scale?")
    per = defaultdict(list)
    for e in eps:
        per[e["sym"]].append(e)
    xs, ys, ns = [], [], []
    for s, v in per.items():
        if len(v) < 10:
            continue
        xs.append(st.median([x["sigma"] for x in v]))
        ys.append(st.median([x["abs_prem"] for x in v]))
        ns.append(s)
    print(f"  markets with >=10 observations: {len(xs)}")
    print(f"  pearson(sigma_price, median|prem|)  = {pearson(xs, ys):+.3f}")
    print(f"  spearman(sigma_price, median|prem|) = {spearman(xs, ys):+.3f}")

    # --- TEST B: the mirror edge, and the ghost control -------------------
    print("\n" + "-" * 78)
    print("TEST B — the mirror edge on this tape, and its direction control")
    horizon_table(eps, "  MIRROR (short premium / long discount):")
    horizon_table(ghost, "  GHOST direction (continuation) — must LOSE:")

    # --- TEST C: at fixed absolute bps, does sigma sort? ------------------
    print("\n" + "-" * 78)
    print("TEST C — THE DECIDING TEST. Hold |prem_bps| FIXED; does the market's")
    print("         own sigma sort the edge? (if not, normalisation adds nothing)")
    for h in (7200, 14400):
        for lo, hi in [(20, 40), (40, 60), (60, 120)]:
            band = [e for e in eps if lo <= e["abs_prem"] < hi]
            if len(band) < 60:
                continue
            sigs = sorted(e["sigma"] for e in band)
            cut = sigs[len(sigs) // 2]
            low = [e for e in band if e["sigma"] <= cut
                   and e.get(f"r{h}") is not None]
            hig = [e for e in band if e["sigma"] > cut
                   and e.get(f"r{h}") is not None]
            if len(low) < 20 or len(hig) < 20:
                continue
            nl, ml, tl = tstat([e[f"r{h}"] for e in low])
            nh, mh, th = tstat([e[f"r{h}"] for e in hig])
            _, _, tld = cluster_t([(e["day"], e[f"r{h}"]) for e in low])
            _, _, thd = cluster_t([(e["day"], e[f"r{h}"]) for e in hig])
            print(f"\n  |prem| in [{lo},{hi}) @ {h//60}m  (sigma split at "
                  f"{cut:.1f}bps)")
            print(f"    LOW  sigma  n={nl:>5} mean={ml:+.4f}% t={tl:+.2f} "
                  f"t_day={tld:+.2f}")
            print(f"    HIGH sigma  n={nh:>5} mean={mh:+.4f}% t={th:+.2f} "
                  f"t_day={thd:+.2f}")
            d = ml - mh
            verdict = ("SUPPORTS normalisation" if d > 0
                       else "CONTRADICTS normalisation")
            print(f"    DELTA (low-high) = {d:+.4f}%  -> {verdict}")

    # --- TEST D: z-strata vs bps-strata -----------------------------------
    print("\n" + "-" * 78)
    print("TEST D — which variable sorts the edge: z or absolute bps?")
    for h in (7200, 14400):
        strata(eps, "abs_prem", [10, 25, 45, 60, 100, 200, 1e9], h,
               "ABSOLUTE |prem_bps|")
        strata(eps, "z", [0, 2, 3, 5, 8, 15, 1e9], h, "Z = |prem|/sigma")

    # --- THE PRE-REGISTERED SCORECARD -------------------------------------
    # Declared in the design spec BEFORE this ran. Evaluated mechanically here
    # so the verdict is not an eyeball over a grid of cells (the (oe) hazard).
    print("\n" + "=" * 78)
    print("PRE-REGISTERED SCORECARD — the design's own bars, evaluated")
    print("=" * 78)
    H = 14400                                    # the 4h decision horizon
    band = [e for e in eps if 3.0 <= e["z"] < 8.0 and e.get(f"r{H}") is not None]
    n_b, m_b, t_b = tstat([e[f"r{H}"] for e in band])
    _, _, t_bd = cluster_t([(e["day"], e[f"r{H}"]) for e in band])
    _, _, t_bs = cluster_t([(e["sym"], e[f"r{H}"]) for e in band])
    ndays = len({e["day"] for e in eps})
    rate = n_b / max(ndays, 1)
    pos_h = 0
    for h in HOLDS_S:
        sub = [e[f"r{h}"] for e in eps
               if 3.0 <= e["z"] < 8.0 and e.get(f"r{h}") is not None]
        if sub and st.mean(sub) > 0:
            pos_h += 1
    gh_band = [e for e in ghost if 3.0 <= e["z"] < 8.0
               and e.get(f"r{H}") is not None]
    _, gm, gt = tstat([e[f"r{H}"] for e in gh_band])
    bycls = defaultdict(list)
    for e in band:
        bycls[e["cls"]].append(e[f"r{H}"])
    cls_pos = sum(1 for v in bycls.values() if len(v) >= 20 and st.mean(v) > 0)

    print(f"\n  BAND z in [3.0, 8.0) at {H//3600}h, net of tier slippage:")
    print(f"    n={n_b}  mean={m_b:+.4f}%  t_iid={t_b:+.2f}  "
          f"t_day={t_bd:+.2f}  t_sym={t_bs:+.2f}")
    print(f"    per-class means (n>=20): "
          + ", ".join(f"{k}:{st.mean(v):+.3f}%(n={len(v)})"
                      for k, v in sorted(bycls.items(), key=lambda kv: str(kv[0]))
                      if len(v) >= 20))
    rows = [
        ("supply   r >= 6.0/day", f"{rate:.1f}/day", rate >= 6.0),
        ("edge     mean > 0", f"{m_b:+.4f}%", m_b > 0),
        (f"edge     t >= +2.0 ({H//3600}h)", f"t_day={t_bd:+.2f}", t_bd >= 2.0),
        ("shape    >=4 of 5 horizons +", f"{pos_h} of 5", pos_h >= 4),
        ("control  ghost negative", f"{gm:+.4f}% (t={gt:+.2f})", gm < 0),
        ("class    positive in >=2", f"{cls_pos} classes", cls_pos >= 2),
    ]
    print()
    allpass = True
    for name, got, ok in rows:
        allpass = allpass and ok
        print(f"    [{'PASS' if ok else 'FAIL'}]  {name:<28} {got}")
    print(f"\n  VERDICT: {'BUILD' if allpass else 'REFUSED — DO NOT BUILD'}")
    print("  The binding statistic is t_day, not t_iid: episodes overlap")
    print("  heavily (same coin, adjacent 5-min snapshots), and this tape is")
    print(f"  {ndays} days long. t_iid on this sample is inflated ~"
          f"{abs(t_b / t_bd) if t_bd else float('nan'):.1f}x.")

    print("\n" + "=" * 78)
    print("SCOPE, restated so no reader drops it: every number above is drawn")
    print("from a TOP-8-BY-ABSOLUTE-BPS sample whose smallest member is ~9.5bps")
    print("against a venue median residual of ~3.5bps. The population the")
    print("flinders design targets -- large SIGMA events at small ABSOLUTE")
    print("premia -- is structurally ABSENT here. A null in TEST C therefore")
    print("refutes only 'normalisation helps among already-large dislocations'.")
    print("=" * 78)
    return 0


def _selftest():
    # tstat / cluster_t
    n, m, t = tstat([1.0, 1.0, 1.0, 1.0])
    assert n == 4 and abs(m - 1.0) < 1e-9 and math.isnan(t), "zero-sd -> nan t"
    n, m, t = tstat([1.0, 2.0, 3.0])
    assert n == 3 and abs(m - 2.0) < 1e-9 and t > 0
    # cluster_t collapses a repeated group to ONE observation. This is the
    # whole point: 100 near-duplicate rows must not out-vote two independent
    # ones, and the iid t on the same data is inflated by exactly that.
    many = [("a", 1.0)] * 100 + [("b", 3.0), ("c", 2.0)]
    n_c, m_c, t_c = cluster_t(many)
    assert n_c == 3 and abs(m_c - 2.0) < 1e-9, (n_c, m_c)
    n_i, _, t_i = tstat([v for _, v in many])
    assert n_i == 102 and t_i > 0
    assert t_i > t_c, ("iid t must exceed the clustered t here", t_i, t_c)
    # correlation
    assert abs(pearson([1, 2, 3, 4], [2, 4, 6, 8]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    # slip tiers are MONOTONE except the declared dust tier, which is worst
    assert slip_bps(50) < slip_bps(5) < slip_bps(1.5)
    assert slip_bps(0.05) == 17.49 and slip_bps(0.05) > slip_bps(0.5)
    # price_at refuses a stale print rather than returning one (I1)
    ser = {"X": ([1000, 2000], [10.0, 20.0])}
    assert price_at(ser, "X", 2000) == 20.0
    assert price_at(ser, "X", 2000 + 1801) is None, "stale price must be None"
    assert price_at(ser, "X", 999) is None
    assert price_at(ser, "MISSING", 2000) is None
    # sigma is UNKNOWN below the bar rather than computed from a short series
    short = {"Y": (list(range(0, 100 * 300, 300)),
                   [10.0 + 0.01 * i for i in range(100)])}
    assert sigma_price_bps(short, "Y", 100 * 300) is None, "short series -> None"
    # a flat series has zero sd -> None, never 0 (which would divide-by-zero z)
    flat_ts = list(range(0, 400 * 300, 300))
    flat = {"Z": (flat_ts, [10.0] * 400)}
    assert sigma_price_bps(flat, "Z", flat_ts[-1]) is None, "flat -> None"
    # a real series produces a finite positive sigma
    random.seed(7)
    px, cur = [], 100.0
    for _ in range(500):
        cur *= math.exp(random.gauss(0, 0.001))
        px.append(cur)
    ts = list(range(0, 500 * 300, 300))
    s = sigma_price_bps({"W": (ts, px)}, "W", ts[-1])
    assert s and 5.0 < s < 20.0, s
    # the mirror/ghost sides are exact opposites
    blob = {"obs": [("2026-09-01T00:00:00", "W", 50.0, 5.0)],
            "vols": {"W": 5.0}, "classes": {"W": 2}}
    ser2 = build_series({"W": dict(zip(ts, px))})
    mir = build_episodes(blob, ser2, "mirror")
    gh = build_episodes(blob, ser2, "ghost")
    if mir and gh:
        assert mir[0]["is_long"] != gh[0]["is_long"], "ghost must invert"
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
