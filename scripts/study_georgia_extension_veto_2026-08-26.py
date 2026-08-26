#!/usr/bin/env python3
"""
study_georgia_extension_veto_2026-08-26.py — ENTRY-TIME PARABOLIC-EXTENSION
VETO on 🔮 georgia (freqtrade-georgia-lshadow), measured on her own era ledger.

THE QUESTION (pre-declared): does refusing a NEW entry when the coin's own
recent run-up AT THE MOMENT OF ENTRY exceeds a threshold in its OWN volatility
units improve her book — entries and exits otherwise UNCHANGED?

Context (26-Aug (tm) pass): her only failing go-live bar is t (0.60 iid / 0.44
cluster over ~195 era closes); ONE 3-leg flash-crash batch (22-Aug 05:11Z —
XRP −16.44%, NEAR −19.51%, TRX −2.97%, all long-trend-breakout_
trailing_stop_loss) is 73.5% of the cluster variance; exits are a measured
DEAD DIAL; a venue-stress pause was REFUTED (stress 8.6bps at entry vs a
15bps bar). The crash XRP entry came 24s after a +7.5%/50min run-up — hence
this study.

=============================================================================
PRE-DECLARED VERDICT LOGIC — written into this header BEFORE any result was
computed; results are reported against it verbatim.

1. Compute extension metrics AT ENTRY for every era close (opens >=
   2026-07-17) with a recorded opened_at, from 15m Lighter candles
   (/api/v1/candles). LAG-1: only bars CLOSED before opened_at (bar open time
   + 900s <= opened_at) may inform the metric. entry_price, where recorded, is
   used only as a candle-alignment sanity check, never in the metric.
   PRIMARY metric  EXT  = (last_close − min(low over trailing 16 closed 15m
                          bars)) / ATR14      [px vs its own 4h low, in ATR]
   SECONDARY       R4   = (last_close/close_16_bars_ago − 1) / (ATR14/last_close)
                   R1   = (last_close/close_4_bars_ago  − 1) / (ATR14/last_close)
   ATR14 = simple mean of true range over the last 14 closed bars.
   Grids: EXT ∈ {2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0};
          R4  ∈ {1.5, 2.0, 2.5, 3.0, 3.5, 4.0}   (veto when metric >= thr).
   BASE sample = era rows whose metric could be built; rows without candles
   or with too-short history are EXCLUDED AND COUNTED (honest limits, §6).

2. A veto HELPS only if, at some threshold cell:
   (a) vetoed-set mean pnl NEGATIVE, AND kept-set mean AND t_iid both IMPROVE
       vs the full BASE sample, AND BOTH chronological halves agree (split
       BASE by closed_at into equal-count halves; in EACH half the kept
       subset's mean must exceed that half's full mean);
   (b) the verdict SURVIVES dropping the 22-Aug crash day entirely (drop all
       rows with closed_at date == 2026-08-22 UTC; on that reduced ledger the
       same cell must still show delta mean > 0 AND delta t_iid > 0). A
       threshold whose whole effect is excising 2–3 known rows is curve-fit
       to one event → REFUTED-AS-OVERFIT, however good its headline;
   (c) it beats a RANDOM-VETO null of equal count: >=1000 permutation draws
       (this script uses 2000) vetoing the same NUMBER of rows at random from
       BASE; P = (1 + #{draws with kept-mean >= actual kept-mean})/(draws+1);
       require P <= 0.05  ((hm) adapted to vetoes);
   (d) dose-response monotone-ish across neighbouring thresholds: at least
       one ADJACENT threshold cell must also show delta mean > 0, and the
       delta-mean profile across the grid must not be a single spike cell
       (the (oe) artifact).

3. TAG SPLIT IS MANDATORY (I7): trend_breakout enters ON STRENGTH by design.
   Report per-tag: fraction of each tag's entries refused per threshold, and
   the per-tag verdict (per-tag delta mean, vetoed-set mean). A veto
   acceptable only as an EXTREME-degree gate must be reported as exactly
   that, with the venue-wide base rate of the extreme cell: over her era, on
   her traded universe, fraction of coin-hours with EXT >= thr (hourly
   samples of the same per-bar metric series).

4. RANK INTERACTION: is high extension the MECHANISM behind rank1's poor
   mean? Report corr(rank1-indicator, EXT), mean EXT by entry rank, and the
   rank1-vs-rank2 pnl gap within low-EXT vs high-EXT subsets (split at the
   BASE median EXT). Rank = extra.entry_rank where stamped (since 22-Aug),
   else derived as order-of-open within the calendar hour (the 3/h throttle's
   own clock); mismatches between stamped and derived are counted.

5. THROUGHPUT: she is signal-limited; a vetoed entry's pnl is fully
   foregone. Bottom line per cell: delta total $, delta mean %/trade,
   delta t (iid + cluster via scripts/golive_readiness.py cluster_stats,
   CLUSTER_WINDOW_S=60), closes/30d retained.

6. HONEST LIMITS reported: closes lacking prices (pre-(gr) rows), candle
   availability per coin, any metric that could not be built. UNBUILDABLE is
   reported as such, never approximated silently.

LIVE ledger (freqtrade-georgia-lighter) is read for 22-Aug crash-day
CORROBORATION ONLY — its 51 closes ran a different exit policy pre-26-Aug and
never enter the graded sample.

READ-ONLY study. No levers, no deploys, no commits. A refusal with evidence
is a first-class outcome (I19).
=============================================================================
"""

import json
import math
import os
import random
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import golive_readiness as gr  # cluster_stats + stats: the fleet's ONE owner

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
B = "https://mainnet.zklighter.elliot.ai"
CACHE = os.path.join(HERE, ".ext_veto_cache")
BOT = "freqtrade-georgia-lshadow"
LIVE_BOT = "freqtrade-georgia-lighter"
ERA = "2026-07-17"
CRASH_DAY = "2026-08-22"
LOOKBACK = 16          # 4h of 15m bars for the low / return window
ATR_N = 14
EXT_GRID = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0]
R4_GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
DRAWS = 2000
SEED = 20260826


def _get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _api(path, **q):
    return _get(B + path + "?" + urllib.parse.urlencode(q))


def _cache(name, build):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    v = build()
    json.dump(v, open(p, "w"))
    return v


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def fetch_ledger(bot):
    return _cache("ledger_" + bot, lambda: _get(
        f"{DASH}/trades.json?source=paper&bot={bot}&limit=5000"))["trades"]


def market_ids():
    return _cache("mids", lambda: {
        o["symbol"]: o["market_id"]
        for o in (_api("/api/v1/orderBookDetails").get("order_book_details") or [])
        if o.get("symbol")})


def candles_15m(sym, mid, t_from, t_to):
    """[(open_ts_s, o, h, l, c)] oldest-first, paged backward (500-bar cap)."""
    key = f"c15_{sym}_{int(t_from)}_{int(t_to)}"

    def build():
        out, end, seen = {}, int(t_to), None
        while True:
            cs = _api("/api/v1/candles", market_id=mid, resolution="15m",
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
    return sorted((int(k), *v) for k, v in _cache(key, build).items())


def tag_of(reason):
    r = (reason or "")
    for t in ("trend-breakout", "range-on", "bounce-pullback"):
        if t in r:
            return t
    return "other"


def build_metric_series(bars):
    """Per-bar (as-of the CLOSE of bars[i]) EXT / R4 / R1, keyed by the ts at
    which the bar CLOSES (open_ts + 900). Needs LOOKBACK+ATR_N history."""
    out = {}
    n = len(bars)
    for i in range(max(LOOKBACK, ATR_N), n):
        window = bars[i - LOOKBACK + 1:i + 1]           # last 16 bars incl. i
        c_last = bars[i][4]
        trs = []
        for j in range(i - ATR_N + 1, i + 1):
            prev_c = bars[j - 1][4]
            trs.append(max(bars[j][2] - bars[j][3],
                           abs(bars[j][2] - prev_c),
                           abs(bars[j][3] - prev_c)))
        atr = sum(trs) / ATR_N
        if atr <= 0 or c_last <= 0:
            continue
        low_w = min(b[3] for b in window)
        c_16ago = bars[i - LOOKBACK][4]
        c_4ago = bars[i - 4][4]
        atr_pct = atr / c_last
        out[bars[i][0] + 900] = {
            "EXT": (c_last - low_w) / atr,
            "R4": (c_last / c_16ago - 1.0) / atr_pct,
            "R1": (c_last / c_4ago - 1.0) / atr_pct,
            "close": c_last,
        }
    return out


def metric_at(series_keys, series, entry_ts):
    """Latest metric whose bar CLOSED at/before entry (LAG-1)."""
    import bisect
    i = bisect.bisect_right(series_keys, entry_ts) - 1
    if i < 0:
        return None
    k = series_keys[i]
    if entry_ts - k > 3 * 900:          # stale tape at entry: refuse to score
        return None
    return series[k]


def tstats(rows):
    """rows: [(pnl_pct, pnl_abs, closed_dt)] oldest-first. Mirrors
    golive_readiness.stats (population sd) + its cluster_stats."""
    pct = [r[0] for r in rows]
    n = len(pct)
    if n < 2:
        return None
    mean = sum(pct) / n
    var = sum((x - mean) ** 2 for x in pct) / n
    sd = math.sqrt(var) or 1e-12
    t = mean / (sd / math.sqrt(n))
    clus = gr.cluster_stats(rows, mean, sd, n)
    return {"n": n, "mean_pct": mean * 100, "t_iid": t,
            "t_cluster": clus["t_cluster"] if clus else None,
            "usd": sum(r[1] or 0 for r in rows)}


def main():
    random.seed(SEED)
    rows = fetch_ledger(BOT)
    era = [r for r in rows if (r.get("opened_at") or "") >= ERA]
    era.sort(key=lambda r: r["closed_at"])
    print(f"ledger {len(rows)} rows, era (opens>={ERA}) {len(era)}")
    no_price = [r for r in era if r.get("entry_price") is None]
    print(f"era rows missing entry_price (pre-(gr)): {len(no_price)} "
          f"(latest {max((r['opened_at'][:10] for r in no_price), default='-')}) "
          f"— metric needs only opened_at+candles, so they STAY in BASE")

    coins = sorted(set(r["pair"] for r in era))
    mids = market_ids()
    t_from = int(parse_ts(min(r["opened_at"] for r in era)).timestamp()) - 900 * (LOOKBACK + ATR_N + 30)
    t_to = int(parse_ts(max(r["opened_at"] for r in era)).timestamp()) + 900
    series, keys, avail = {}, {}, {}
    for c in coins:
        bars = candles_15m(c, mids[c], t_from, t_to)
        s = build_metric_series(bars)
        series[c] = s
        keys[c] = sorted(s)
        avail[c] = (len(bars), min(bars)[0] if bars else None)
        print(f"  candles {c}: {len(bars)} bars, metric points {len(s)}")

    # ---- per-row metrics (LAG-1) ------------------------------------------
    base, unbuilt = [], []
    align = []
    for r in era:
        ts = int(parse_ts(r["opened_at"]).timestamp())
        m = metric_at(keys[r["pair"]], series[r["pair"]], ts)
        if m is None:
            unbuilt.append(r)
            continue
        rec = dict(r)
        rec["EXT"], rec["R4"], rec["R1"] = m["EXT"], m["R4"], m["R1"]
        rec["tag"] = tag_of(r["reason"])
        rec["closed_dt"] = parse_ts(r["closed_at"])
        if r.get("entry_price"):
            align.append(abs(r["entry_price"] / m["close"] - 1) * 1e4)
        base.append(rec)
    print(f"BASE (metric built): {len(base)} of {len(era)}; unbuilt {len(unbuilt)}"
          + (f" ({Counter(r['pair'] for r in unbuilt)})" if unbuilt else ""))
    align.sort()
    if align:
        print(f"candle-alignment |entry_px vs last closed bar close|: "
              f"median {align[len(align)//2]:.1f}bps, "
              f"p90 {align[int(len(align)*0.9)]:.1f}bps (n={len(align)}) — "
              f"gaps are the intra-bar move the LAG-1 convention forfeits by design")

    def rowset(rs):
        return [(x["pnl_pct"], x["pnl_abs"], x["closed_dt"]) for x in
                sorted(rs, key=lambda z: z["closed_dt"])]

    full = tstats(rowset(base))
    days = (base[-1]["closed_dt"] - base[0]["closed_dt"]).total_seconds() / 86400
    print(f"\nBASE full sample: n={full['n']} mean {full['mean_pct']:+.3f}%/t "
          f"t_iid {full['t_iid']:+.2f} t_clus {full['t_cluster']} "
          f"${full['usd']:+.2f} over {days:.1f}d "
          f"({full['n']/days*30:.0f} closes/30d)")

    # crash rows' own metrics
    print("\n22-Aug crash-batch entries, their own AT-ENTRY metrics:")
    for x in base:
        if x["closed_at"][:10] == CRASH_DAY and x["pnl_pct"] < -0.02:
            print(f"  {x['pair']:5s} open {x['opened_at'][11:19]}Z "
                  f"pnl {x['pnl_pct']*100:+.2f}% EXT {x['EXT']:.2f} "
                  f"R4 {x['R4']:.2f} R1 {x['R1']:.2f}")
    ext_sorted = sorted(base, key=lambda z: -z["EXT"])
    print("top-10 EXT entries in BASE:")
    for x in ext_sorted[:10]:
        print(f"  EXT {x['EXT']:5.2f} {x['pair']:5s} {x['opened_at'][:16]} "
              f"{x['tag']:15s} pnl {x['pnl_pct']*100:+.2f}%")

    # ---- the sweep --------------------------------------------------------
    mid_i = len(base) // 2
    halves = (base[:mid_i], base[mid_i:])          # closed_at-ordered already
    ex_crash = [x for x in base if x["closed_at"][:10] != CRASH_DAY]
    full_xc = tstats(rowset(ex_crash))
    tags = sorted(set(x["tag"] for x in base))
    tag_n = Counter(x["tag"] for x in base)
    print(f"\nex-crash-day baseline: n={full_xc['n']} mean {full_xc['mean_pct']:+.3f}% "
          f"t_iid {full_xc['t_iid']:+.2f}")
    print(f"tags: {dict(tag_n)}\n")

    def sweep(metric, grid):
        cells = []
        for thr in grid:
            veto = [x for x in base if x[metric] >= thr]
            keep = [x for x in base if x[metric] < thr]
            if len(veto) == 0 or len(keep) < 10:
                cells.append({"thr": thr, "k": len(veto), "empty": True})
                continue
            ks = tstats(rowset(keep))
            vs = tstats(rowset(veto)) if len(veto) >= 2 else {
                "mean_pct": veto[0]["pnl_pct"] * 100, "usd": veto[0]["pnl_abs"],
                "n": 1, "t_iid": float("nan"), "t_cluster": None}
            d_mean = ks["mean_pct"] - full["mean_pct"]
            d_t = ks["t_iid"] - full["t_iid"]
            # halves
            hv = []
            for h in halves:
                hf = tstats(rowset(h))
                hk_rows = [x for x in h if x[metric] < thr]
                hk = tstats(rowset(hk_rows)) if len(hk_rows) >= 2 else None
                hv.append(None if (hk is None or hf is None)
                          else hk["mean_pct"] - hf["mean_pct"])
            halves_ok = all(v is not None and v > 0 for v in hv)
            # crash-day-excluded
            keep_xc = [x for x in ex_crash if x[metric] < thr]
            ks_xc = tstats(rowset(keep_xc)) if len(keep_xc) >= 10 else None
            xc_d_mean = xc_d_t = None
            if ks_xc and full_xc:
                xc_d_mean = ks_xc["mean_pct"] - full_xc["mean_pct"]
                xc_d_t = ks_xc["t_iid"] - full_xc["t_iid"]
            xc_ok = xc_d_mean is not None and xc_d_mean > 0 and xc_d_t > 0
            # random-veto null
            k = len(veto)
            ge = 0
            pnl_all = [x["pnl_pct"] for x in base]
            tot = sum(pnl_all)
            nb = len(base)
            actual_keep_mean = statistics.mean(x["pnl_pct"] for x in keep)
            for _ in range(DRAWS):
                sub = random.sample(pnl_all, k)
                if (tot - sum(sub)) / (nb - k) >= actual_keep_mean:
                    ge += 1
            p_rand = (1 + ge) / (DRAWS + 1)
            # tags
            tg = {t: {"veto_frac": (sum(1 for x in veto if x["tag"] == t)
                                    / tag_n[t] if tag_n[t] else 0.0)}
                  for t in tags}
            for t in tags:
                tk = [x for x in base if x["tag"] == t and x[metric] < thr]
                tf = [x for x in base if x["tag"] == t]
                if len(tk) >= 2 and len(tf) >= 2:
                    tg[t]["d_mean"] = (tstats(rowset(tk))["mean_pct"]
                                       - tstats(rowset(tf))["mean_pct"])
            cells.append({
                "thr": thr, "k": k, "veto_mean": vs["mean_pct"],
                "veto_usd": vs["usd"], "keep_n": ks["n"],
                "keep_mean": ks["mean_pct"], "keep_t": ks["t_iid"],
                "keep_t_clus": ks["t_cluster"], "d_mean": d_mean, "d_t": d_t,
                "d_usd": ks["usd"] - full["usd"], "halves": hv,
                "halves_ok": halves_ok, "xc_d_mean": xc_d_mean,
                "xc_d_t": xc_d_t, "xc_ok": xc_ok, "p_rand": p_rand,
                "closes30": ks["n"] / days * 30, "tags": tg})
        # dose-response: adjacent-cell agreement on d_mean
        for i, c in enumerate(cells):
            if c.get("empty"):
                continue
            neigh = [cells[j] for j in (i - 1, i + 1)
                     if 0 <= j < len(cells) and not cells[j].get("empty")]
            c["dose_ok"] = (c["d_mean"] > 0
                            and any(x["d_mean"] > 0 for x in neigh))
            c["HELPS"] = (c["d_mean"] > 0 and c["d_t"] > 0
                          and c["veto_mean"] < 0 and c["halves_ok"]
                          and c["xc_ok"] and c["p_rand"] <= 0.05
                          and c["dose_ok"])
        return cells

    for metric, grid in (("EXT", EXT_GRID), ("R4", R4_GRID), ("R1", R4_GRID)):
        print(f"===== metric {metric} (veto when >= thr) =====")
        hdr = ("thr    k veto_mean%  veto$   keep_n keep_m%  t_iid t_clus  "
               "dMean%  dT    d$      halves(d1,d2)   xc_dM% xc_dT  P_rand "
               "c/30d verdict")
        print(hdr)
        for c in sweep(metric, grid):
            if c.get("empty"):
                print(f"{c['thr']:4.1f} {c['k']:4d}  (empty or keep<10)")
                continue
            h1, h2 = c["halves"]
            fh = lambda v: "None " if v is None else f"{v:+.2f}"
            tc = "None " if c["keep_t_clus"] is None else f"{c['keep_t_clus']:+.2f}"
            verdict = ("HELPS" if c["HELPS"] else
                       ("overfit" if (c["d_mean"] > 0 and c["d_t"] > 0
                                      and not c["xc_ok"]) else "no"))
            print(f"{c['thr']:4.1f} {c['k']:4d} {c['veto_mean']:+9.3f} "
                  f"{c['veto_usd']:+7.2f} {c['keep_n']:6d} "
                  f"{c['keep_mean']:+7.3f} {c['keep_t']:+6.2f} {tc:>6s} "
                  f"{c['d_mean']:+7.3f} {c['d_t']:+5.2f} {c['d_usd']:+7.2f} "
                  f"({fh(h1)},{fh(h2)}) {fh(c['xc_d_mean']):>7s} "
                  f"{fh(c['xc_d_t']):>5s} {c['p_rand']:6.3f} "
                  f"{c['closes30']:5.1f} {verdict}")
            frac = " ".join(f"{t}:{c['tags'][t]['veto_frac']*100:.0f}%"
                            f"(d{c['tags'][t].get('d_mean', float('nan')):+.2f})"
                            for t in tags)
            print(f"      tag veto-frac(dMean%): {frac}")
        print()

    # ---- base rate of the extreme cell (coin-hours) -----------------------
    print("===== venue base rate: fraction of coin-hours with EXT >= thr "
          "(hourly samples, era window, her traded universe) =====")
    samples = []
    for c in coins:
        for k in keys[c]:
            if k % 3600 == 0:
                samples.append(series[c][k]["EXT"])
    print(f"coin-hour samples: {len(samples)}")
    for thr in EXT_GRID:
        f = sum(1 for s in samples if s >= thr) / len(samples)
        print(f"  EXT>={thr:3.1f}: {f*100:5.2f}% of coin-hours")

    # ---- rank interaction -------------------------------------------------
    print("\n===== rank interaction =====")
    byh = defaultdict(list)
    for x in base:
        byh[x["opened_at"][:13]].append(x)
    mism = 0
    for h, g in byh.items():
        g.sort(key=lambda z: z["opened_at"])
        for i, x in enumerate(g):
            x["drank"] = i + 1
            st = (x.get("extra") or {}).get("entry_rank")
            x["rank"] = st if st is not None else x["drank"]
            if st is not None and st != x["drank"]:
                mism += 1
    print(f"stamped-vs-derived rank mismatches: {mism} "
          f"(same-second batch opens make within-hour order ambiguous; "
          f"stamped wins where present)")
    for k in (1, 2):
        g = [x for x in base if x["rank"] == k]
        if len(g) >= 2:
            s = tstats(rowset(g))
            me = statistics.mean(x["EXT"] for x in g)
            print(f"  rank{k}: n={s['n']} mean {s['mean_pct']:+.3f}% "
                  f"t {s['t_iid']:+.2f} | mean EXT {me:.2f}")
    r1 = [1.0 if x["rank"] == 1 else 0.0 for x in base]
    ex = [x["EXT"] for x in base]
    mr, mx = statistics.mean(r1), statistics.mean(ex)
    cov = sum((a - mr) * (b - mx) for a, b in zip(r1, ex)) / len(base)
    corr = cov / (statistics.pstdev(r1) * statistics.pstdev(ex))
    print(f"  corr(rank1 indicator, EXT) = {corr:+.3f}")
    med = statistics.median(ex)
    for lbl, sub in (("EXT<median", [x for x in base if x["EXT"] < med]),
                     ("EXT>=median", [x for x in base if x["EXT"] >= med])):
        g1 = [x for x in sub if x["rank"] == 1]
        g2 = [x for x in sub if x["rank"] == 2]
        m1 = statistics.mean(x["pnl_pct"] for x in g1) * 100 if g1 else float("nan")
        m2 = statistics.mean(x["pnl_pct"] for x in g2) * 100 if g2 else float("nan")
        print(f"  {lbl:11s}: rank1 n={len(g1)} {m1:+.3f}% | "
              f"rank2 n={len(g2)} {m2:+.3f}% | gap {m2-m1:+.3f}pp")

    # ---- live-ledger crash-day corroboration (NOT graded) -----------------
    print("\n===== LIVE ledger 22-Aug corroboration (NOT in graded sample) =====")
    try:
        live = fetch_ledger(LIVE_BOT)
        lc = [r for r in live if (r.get("closed_at") or "")[:10] == CRASH_DAY]
        for r in sorted(lc, key=lambda z: z["closed_at"]):
            print(f"  {r['pair']:5s} open {r['opened_at'][11:19]}Z close "
                  f"{r['closed_at'][11:19]}Z pnl {r['pnl_pct']*100:+.2f}% "
                  f"{r['reason']}")
        if not lc:
            print("  (no live closes on 22-Aug)")
    except Exception as e:  # noqa: BLE001
        print(f"  live ledger unavailable: {e}")


if __name__ == "__main__":
    main()
