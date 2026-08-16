#!/usr/bin/env python3
"""
study_books_cohort_2026-08-13.py — the measurements behind the BOOKS cohort's
second wave (🧘 book-douglas, 📐 book-grimes, 🧙 book-schwager, 🧮 book-hull).

Operator, 13-Aug: "Build me 4 bots for each of these books (please read them
and build for lighter exchange as usual)."

MEASURE BEFORE BUILDING. Every rule the four bots ship — and every rule they
REFUSED — was measured here first, on Lighter's own tape (venue-purity rule:
the venue we trade is the venue we measure). Headline results at authoring:

  DOUGLAS (1h, 18 coins, 208d, 5bps/side, cap 4):
    - pre-registered impulse CONTINUATION (1.5xATR): −$210.59, t=−2.81 REFUTED
    - shipped: FADE of >2.5xATR impulses, sl 1.0x/tp 1.5xATR, 12h:
      n=575 +$27.01 t=+0.84 halves +8.80/+18.21, random-entry benchmark
      P(rand>=strat)=0.005 on both total and mean (200 draws)
    - the naive revenge-guard overlay (4h coin cooldown + 3-loss pause):
      +$27.01 -> −$11.32 REFUTED — outcomes must not alter execution
  GRIMES (4h, 18 coins, 500d): TWELVE variants of the structural setups
    (pullback x6, failtest x4, daily-dislocation fade, keltner fade) — NONE
    beat random entries (best P=0.24). The bot therefore ships the TESTING
    DISCIPLINE (the roster + rolling replay gate), not a refuted setup.
    Trailing-120d scorecard at birth, LAG-1 trend ((mh)): keltner n=109
    +$31.69 t=0.49 — knife-edge BELOW the 0.5 bar, closed; pullback
    −$36.25 closed; failtest −$12.05 closed. All gates closed at birth;
    the unlagged first cut read keltner t=0.75 OPEN — the look-ahead was
    part of the apparent edge, and the full-window refutations stand a
    fortiori (they were refuted even WITH the look-ahead flattering them).
  SCHWAGER (4h, 18 coins, 500d, cap 4):
    - shipped: Donchian-20 close breakout + EMA20>50, sl 2xATR, chandelier
      trail 3.5xATR, NO pyramid: n=277 +$457.21 mean +1.65% t=+1.88 halves
      +357.90/+99.31, P(rand>=strat)=0.015/0.020
    - pyramid-to-3-units cells: −$292.83 .. −$1,103.57 REFUTED
    - trail 2.5x cells: negative REFUTED; 1d Donchian: 2.9 closes/30d
      undecidable (I17) REFUSED
  HULL (settled fundings, 18 coins, 219d, 30bps RT on $80 clips, cap 4):
    - grace 1h (the kiyosaki-shaped flip exit) in the mid band: −$16.84,
      t=−6.65, 136/158 exits liability_flip REFUTED — churn pays the RT on
      every sign wobble
    - shipped: band [7.82%,20%) TRUE, persist 24h, grace 24h: n=45 +$4.92
      t=+3.27 halves +0.75/+4.17, random-timing control P=0.000
    - tier-restricted to [2M,10M) members: n=30 +$4.17 t=+2.76
    - the persist{6,24,48} x grace{1,6,24} x floor{7.8%,10%,12%} grid is a
      PLATEAU: all persist>=24h+grace>=6h cells positive, all grace=1h
      cells negative; floor 12% starves (0-14 closes)

Method notes (doctrine): random-entry benchmark per (hm) — same coins,
window, bracket and cap, matched signal counts, N=200 draws; throughput
modelled per (gt) — sequential portfolio with the book's position cap;
halves split + t-stat; win rate reported, never a bar (I15). Survivorship
caveat: the 18-coin universe is today's liquid set (>= $1M by the live
scout); historical membership is not reconstructable.

Usage (network: Lighter public REST only):
    python3 scripts/study_books_cohort_2026-08-13.py --fetch   # pull tape
    python3 scripts/study_books_cohort_2026-08-13.py           # run study
Tape is cached in scripts/.books_cohort_cache/ so the study is re-runnable
offline once fetched.
"""
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request

API = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".books_cohort_cache")
FEE_SIDE = 0.0005
UNIVERSE = ("BTC,ETH,SOL,HYPE,LIT,ZEC,PUMP,XRP,UNI,ETHFI,BNB,ENA,"
            "DOGE,NEAR,XMR,AVAX,LINK,TAO").split(",")
# [2026-08-13 (mf)] the >=20%-cell coin population (the carry cohort's
# supply: KAITO/XMR/PAXG/XRP per (ly), plus the cell's occasional visitors)
# for the CARRY-CELL GRACE study — Hull's basis-noise finding replayed on
# the carry books' own gate. Measured: grace 1h = +$26.88 t=1.91 (h2
# NEGATIVE, 192/231 exits churning the RT); 6h = +$42.09 t=3.00 both
# halves; 24h = +$50.87 t=3.56. Robust ex-AVNT (+$2.81 -> +$21.40).
# Consumed: 🏦 Kiyosaki FLIP_GRACE_H 1.0 -> 6.0 the same day; 🌾 carry and
# 🎸 Barnesy queued (protected clocks — OPERATOR_QUEUE).
CARRY_CELL_COINS = "KAITO,XMR,PAXG,XRP,ZEC,LIT,EDEN,AVNT,TRUMP,ENA".split(",")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def fetch_tape():
    os.makedirs(CACHE, exist_ok=True)
    d = _get(API + "/api/v1/orderBookDetails")
    ids = {b["symbol"]: int(b["market_id"])
           for b in (d.get("order_book_details") or [])}
    for res, res_sec, pages in (("1h", 3600, 10), ("4h", 14400, 6),
                                ("1d", 86400, 2)):
        out = {}
        for sym in UNIVERSE:
            if sym not in ids:
                continue
            rows = {}
            end = int(time.time())
            for _ in range(pages):
                url = (f"{API}/api/v1/candles?market_id={ids[sym]}"
                       f"&resolution={res}&start_timestamp={end - 500 * res_sec}"
                       f"&end_timestamp={end}&count_back=500")
                dd = _get(url)
                page = (dd or {}).get("c") or []
                if not page:
                    break
                for c in page:
                    t = int(c["t"]) // 1000
                    rows[t] = [t, float(c["o"]), float(c["h"]),
                               float(c["l"]), float(c["c"])]
                oldest = min(int(c["t"]) // 1000 for c in page)
                if len(page) < 400:
                    break
                end = oldest - 1
                time.sleep(0.25)
            out[sym] = [rows[t] for t in sorted(rows)]
            print(f"{res} {sym}: {len(out[sym])} bars")
        json.dump(out, open(os.path.join(CACHE, f"candles_{res}.json"), "w"))
    # settled fundings, paged backward (sign: direction long = +)
    out = {}
    for sym in sorted(set(UNIVERSE) | set(CARRY_CELL_COINS)):
        if sym not in ids:
            continue
        rows = {}
        oldest = int(time.time())
        for _ in range(8):
            q = urllib.parse.urlencode(
                {"market_id": ids[sym], "resolution": "1h",
                 "start_timestamp": 0, "end_timestamp": oldest - 3600,
                 "count_back": 0})
            dd = _get(API + "/api/v1/fundings?" + q)
            page = (dd or {}).get("fundings") or []
            if not page:
                break
            for f in page:
                t = (int(f["timestamp"]) // 3600) * 3600
                sign = 1.0 if f.get("direction") == "long" else -1.0
                rows[t] = sign * float(f["rate"]) / 100.0   # frac/hr
            new_oldest = min((int(f["timestamp"]) // 3600) * 3600
                             for f in page)
            if new_oldest >= oldest:
                break
            oldest = new_oldest
            time.sleep(0.25)
        out[sym] = sorted(rows.items())
        print(f"fundings {sym}: {len(out[sym])} rows")
    json.dump(out, open(os.path.join(CACHE, "fundings.json"), "w"))
    print("tape cached in", CACHE)


# ------------------------------------------------------------- indicators
def atr_series(rows, n):
    out = [None] * len(rows)
    a, trs, prev_c = None, [], None
    for i, r in enumerate(rows):
        _, o, h, l, c = r[:5]
        tr = (h - l) if prev_c is None else max(h - l, abs(h - prev_c),
                                                abs(l - prev_c))
        prev_c = c
        if a is None:
            trs.append(tr)
            if len(trs) == n:
                a = sum(trs) / n
        else:
            a = (a * (n - 1) + tr) / n
        out[i] = (a / c) if (a and c) else None
    return out


def ema_series(vals, n):
    out = [None] * len(vals)
    k = 2.0 / (n + 1)
    e = None
    for i, v in enumerate(vals):
        e = v if e is None else (v * k + e * (1 - k))
        out[i] = e if i >= n else None
    return out


def t_stat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(var / n) if var > 0 else 0.0


# ------------------------------------------------------- portfolio replay
def run_portfolio(signals, rows_by_sym, cap, res_sec, atrs_by_sym,
                  entry_bar_bracket=True):
    """signals: {sym: [(bar_i, side, sl, tp, hold_bars, trail_mult)]}.
    Entry next-bar open; intra-bar stop first (conservative); trail is a
    close-basis chandelier when trail_mult is set. Sequential, cap-bound.

    [2026-08-16] ADDITIVE EXTENSION for the ⚡ High Voltage sizing study — this
    stays the ONE owner of the bracket walk (a second copy is a second rule),
    so the levered study imports it rather than forking it. Nothing about the
    default path changed: with `entry_bar_bracket=True` every previously
    published number reproduces byte-identically, and the pre-existing keys
    (`sym`/`ret`/`t`/`hold`) are untouched. What is new:

      * each closed record also carries `entry`, `entry_t`, `side`, `sl`, `tp`,
        `atr0`, `reason` and `mae_frac` — the MAXIMUM ADVERSE EXCURSION as a
        fraction of entry, over every bar the position was open INCLUDING the
        entry bar. A liquidation is a pure function of that excursion and the
        position's leverage, so a levered study can price liquidation exactly
        without a second walk (and without this harness knowing what leverage
        is).
      * `gap_frac` — how far the bar that stopped the trade OPENED beyond the
        stop. The walk fills stops AT the stop price, which is optimistic on a
        gap; recording the gap lets a study charge it rather than assume it
        away. Zero when the stop was reachable inside the bar.
      * `entry_bar_bracket=False` reverts to the PRE-(ml) convention, in which
        the entry bar's own post-open range was not bracket-tested. It exists
        so the size of that look-ahead stays MEASURABLE rather than becoming
        folklore — the (ml) entry warned the recorded numbers "carry that small
        optimism", and on the Douglas cell it is not small (see the (ml)
        decomposition in the High Voltage study)."""
    ev = []
    for sym, sigs in signals.items():
        rows = rows_by_sym[sym]
        for s in sigs:
            if s[0] + 1 < len(rows):
                ev.append((rows[s[0] + 1][0], sym) + tuple(s))
    ev.sort()
    idx_of = {sym: {r[0]: i for i, r in enumerate(rows)}
              for sym, rows in rows_by_sym.items()}
    all_t = sorted({r[0] for rows in rows_by_sym.values() for r in rows})
    open_pos, closed, ei = {}, [], 0
    for now_t in all_t:
        for sym in list(open_pos):
            p = open_pos[sym]
            i = idx_of[sym].get(now_t)
            if i is None:
                continue
            _, o, h, l, c = rows_by_sym[sym][i][:5]
            e, sign = p["entry"], p["sign"]
            # MAE over EVERY bar held, entry bar included (set at open time).
            p["mae"] = max(p["mae"], (e - l) / e if sign > 0 else (h - e) / e)
            px, reason = None, None
            if sign > 0:
                stop_px = e * (1 - p["sl"]) if p["trail_px"] is None \
                    else p["trail_px"]
                if l <= stop_px:
                    px = stop_px
                    # A CHANDELIER TRAIL IS NOT A STOP. Labelling both "sl"
                    # made Schwager's cell report 328 stop-outs on a rule whose
                    # parent study reports 251 of 277 exits as the TRAIL.
                    reason = "trail" if p["trail_px"] is not None else "sl"
                    p["gap"] = max(0.0, (stop_px - o) / e)
                elif p["tp"] and h >= e * (1 + p["tp"]):
                    px, reason = e * (1 + p["tp"]), "tp"
            else:
                stop_px = e * (1 + p["sl"]) if p["trail_px"] is None \
                    else p["trail_px"]
                if h >= stop_px:
                    px = stop_px
                    reason = "trail" if p["trail_px"] is not None else "sl"
                    p["gap"] = max(0.0, (o - stop_px) / e)
                elif p["tp"] and l <= e * (1 - p["tp"]):
                    px, reason = e * (1 - p["tp"]), "tp"
            p["bars"] += 1
            if px is None and p["bars"] >= p["hold"]:
                px, reason = c, "hold"
            if px is None and p["trail"]:
                if sign > 0:
                    p["hwm"] = max(p["hwm"], c)
                    t_ = p["hwm"] * (1 - p["trail"] * p["atr0"])
                    p["trail_px"] = max(p["trail_px"] or 0, t_)
                else:
                    p["hwm"] = min(p["hwm"], c)
                    t_ = p["hwm"] * (1 + p["trail"] * p["atr0"])
                    p["trail_px"] = min(p["trail_px"] or 1e18, t_)
            if px is not None:
                ret = (px - e) / e * sign - 2 * FEE_SIDE
                closed.append(dict(sym=sym, ret=ret, t=now_t,
                                   hold=p["bars"] * res_sec / 3600.0,
                                   entry=e, entry_t=p["t0"], side=p["side"],
                                   sl=p["sl"], tp=p["tp"], atr0=p["atr0"],
                                   reason=reason, mae_frac=p["mae"],
                                   gap_frac=p["gap"]))
                del open_pos[sym]
        while ei < len(ev) and ev[ei][0] == now_t:
            _, sym, bar_i, side, sl, tp, hold, trail = ev[ei]
            ei += 1
            if sym in open_pos or len(open_pos) >= cap:
                continue
            ebar = rows_by_sym[sym][bar_i + 1]
            entry = ebar[1]
            if not entry or entry <= 0:
                continue
            a0 = atrs_by_sym[sym][bar_i] or sl
            sign = 1.0 if side == "long" else -1.0
            # [(ml)] the ENTRY BAR's own post-open range is bracket-tested
            # too (stop first, same convention as the manage pass) and the
            # bar counts toward the hold — a live loop realises entry-bar
            # stops, so skipping them graded an optimistic rule. Numbers
            # recorded before this correction carry that small optimism.
            _, _eo, eh, el, ec = ebar[:5]
            emae = (entry - el) / entry if sign > 0 else (eh - entry) / entry
            px, reason = None, None
            if entry_bar_bracket:
                if sign > 0:
                    if el <= entry * (1 - sl):
                        px, reason = entry * (1 - sl), "sl"
                    elif tp and eh >= entry * (1 + tp):
                        px, reason = entry * (1 + tp), "tp"
                else:
                    if eh >= entry * (1 + sl):
                        px, reason = entry * (1 + sl), "sl"
                    elif tp and el <= entry * (1 - tp):
                        px, reason = entry * (1 - tp), "tp"
            if px is not None:
                ret = (px - entry) / entry * sign - 2 * FEE_SIDE
                closed.append(dict(sym=sym, ret=ret, t=now_t,
                                   hold=res_sec / 3600.0,
                                   entry=entry, entry_t=now_t,
                                   side=side, sl=sl, tp=tp, atr0=a0,
                                   reason=reason, mae_frac=emae, gap_frac=0.0))
                continue
            p0 = dict(entry=entry, sign=sign,
                      sl=sl, tp=tp, hold=hold, bars=1,
                      trail=trail, trail_px=None, hwm=entry,
                      atr0=a0, t0=now_t, side=side, mae=emae, gap=0.0)
            if trail:
                if sign > 0:
                    p0["hwm"] = max(p0["hwm"], ec)
                    p0["trail_px"] = p0["hwm"] * (1 - trail * a0)
                else:
                    p0["hwm"] = min(p0["hwm"], ec)
                    p0["trail_px"] = p0["hwm"] * (1 + trail * a0)
            open_pos[sym] = p0
    return closed


def summarize(name, closed, days, clip=100.0):
    if not closed:
        print(f"{name}: ZERO closes")
        return None
    rets = [c["ret"] for c in closed]
    n = len(rets)
    tot = sum(r * clip for r in rets)
    cs = sorted(closed, key=lambda c: c["t"])
    half = n // 2
    h1 = sum(c["ret"] for c in cs[:half]) * clip
    h2 = sum(c["ret"] for c in cs[half:]) * clip
    print(f"{name}: n={n} tot=${tot:.2f} mean={sum(rets)/n*100:.3f}% "
          f"t={t_stat(rets):.2f} h1=${h1:.2f} h2=${h2:.2f} "
          f"win={sum(1 for r in rets if r > 0)/n:.2f} (reported) "
          f"c/30d={n/days*30:.1f}")
    return dict(n=n, tot=tot, mean=sum(rets) / n * 100)


def random_bench(signals, rows_by_sym, cap, res_sec, atrs, days, real,
                 n_draws=200, seed=42):
    beats_t = beats_m = 0
    for d in range(n_draws):
        rng = random.Random(seed + d)
        rsig = {}
        for sym, sigs in signals.items():
            hi = len(rows_by_sym[sym]) - 2
            rsig[sym] = sorted(
                (rng.randint(60, hi), rng.choice(["long", "short"]))
                + tuple(s[2:]) for s in sigs if hi > 60)
        closed = run_portfolio(rsig, rows_by_sym, cap, res_sec, atrs)
        if closed:
            rets = [c["ret"] for c in closed]
            if sum(r * 100 for r in rets) >= real["tot"]:
                beats_t += 1
            if sum(rets) / len(rets) * 100 >= real["mean"]:
                beats_m += 1
    print(f"  random-entry benchmark: P(tot>=)={beats_t/n_draws:.3f} "
          f"P(mean>=)={beats_m/n_draws:.3f}")


# ------------------------------------------------------------ the studies
def main():
    if "--fetch" in sys.argv:
        fetch_tape()
        return
    c1 = {s: r for s, r in json.load(
        open(os.path.join(CACHE, "candles_1h.json"))).items() if len(r) > 200}
    c4 = {s: r for s, r in json.load(
        open(os.path.join(CACHE, "candles_4h.json"))).items() if len(r) > 200}
    cd = {s: r for s, r in json.load(
        open(os.path.join(CACHE, "candles_1d.json"))).items() if len(r) > 100}
    fund = json.load(open(os.path.join(CACHE, "fundings.json")))

    def days_of(rb):
        return max((r[-1][0] - r[0][0]) for r in rb.values()) / 86400

    # ---------------- DOUGLAS
    d1 = days_of(c1)
    atrs1 = {s: atr_series(r, 24) for s, r in c1.items()}
    for k, direction, tag in ((1.5, +1, "continuation (REFUTED)"),
                              (2.5, -1, "fade (SHIPPED)")):
        sigs = {}
        for s, rows in c1.items():
            out = []
            for i in range(26, len(rows) - 1):
                a = atrs1[s][i]
                if not a:
                    continue
                chg = (rows[i][4] - rows[i - 1][4]) / rows[i - 1][4]
                if abs(chg) > k * a:
                    imp = 1 if chg > 0 else -1
                    side = "long" if imp * direction > 0 else "short"
                    out.append((i, side, 1.0 * a, 1.5 * a, 12, None))
            sigs[s] = out
        closed = run_portfolio(sigs, c1, 4, 3600, atrs1)
        r = summarize(f"DOUGLAS {k}xATR {tag}", closed, d1)
        if r and direction < 0:
            random_bench(sigs, c1, 4, 3600, atrs1, d1, r)

    # ---------------- SCHWAGER
    d4 = days_of(c4)
    atrs4 = {s: atr_series(r, 14) for s, r in c4.items()}
    e20 = {s: ema_series([r[4] for r in c4[s]], 20) for s in c4}
    e50 = {s: ema_series([r[4] for r in c4[s]], 50) for s in c4}
    for trail, tag in ((3.5, "trail 3.5x (SHIPPED)"),
                       (2.5, "trail 2.5x (REFUTED)")):
        sigs = {}
        for s, rows in c4.items():
            out = []
            for i in range(56, len(rows) - 1):
                a, xf, xs = atrs4[s][i], e20[s][i], e50[s][i]
                if not (a and xf and xs):
                    continue
                closes = [r[4] for r in rows[i - 20:i]]
                c = rows[i][4]
                if c > max(closes) and xf > xs:
                    out.append((i, "long", 2.0 * a, None, 180, trail))
                elif c < min(closes) and xf < xs:
                    out.append((i, "short", 2.0 * a, None, 180, trail))
            sigs[s] = out
        closed = run_portfolio(sigs, c4, 4, 14400, atrs4)
        r = summarize(f"SCHWAGER don20 no-pyr {tag}", closed, d4)
        if r and trail == 3.5:
            random_bench(sigs, c4, 4, 14400, atrs4, d4, r, seed=9001)

    # ---------------- GRIMES (trailing-window scorecard, the bot's gate)
    cut = time.time() - 126 * 86400
    c4t = {s: [r for r in rows if r[0] >= cut] for s, rows in c4.items()}
    c4t = {s: r for s, r in c4t.items() if len(r) > 100}
    cdt = {s: [r for r in rows if r[0] >= cut - 60 * 86400]
           for s, rows in cd.items()}
    at = {s: atr_series(r, 14) for s, r in c4t.items()}
    et20 = {s: ema_series([r[4] for r in c4t[s]], 20) for s in c4t}
    et50 = {s: ema_series([r[4] for r in c4t[s]], 50) for s in c4t}
    dtr = {}
    for s in c4t:
        if s not in cdt:
            continue
        dcl = [r[4] for r in cdt[s]]
        de20, de50 = ema_series(dcl, 20), ema_series(dcl, 50)
        # [(mh)] LAG-1: day D is gated on D-1's close — the unlagged map
        # gave the replay a look-ahead and the live scan a missing key.
        dtr[s] = {cdt[s][j][0] // 86400 + 1:
                  (0 if (de20[j] is None or de50[j] is None)
                   else (1 if de20[j] > de50[j] else -1))
                  for j in range(len(cdt[s]))}
    dt4 = days_of(c4t)

    def g_pullback(s, i):
        a, xf, xs = at[s][i], et20[s][i], et50[s][i]
        if not (a and xf and xs):
            return None
        # [(ml)] no claim (missing coin/day or EMA warmup) FAILS CLOSED —
        # dt=0 passed keltner's <=0/>=0, unfiltering the fade on gaps.
        dt = dtr.get(s, {}).get(c4t[s][i][0] // 86400)
        if dt not in (-1, 1):
            return None
        _, o, h, l, c = c4t[s][i][:5]
        if dt > 0 and xf > xs and l <= xf and c > xf:
            return ("long", 1.5 * a, 4.5 * a, 20, None)
        if dt < 0 and xf < xs and h >= xf and c < xf:
            return ("short", 1.5 * a, 4.5 * a, 20, None)
        return None

    def g_failtest(s, i):
        a = at[s][i]
        if not a or i < 22:
            return None
        hh = max(r[2] for r in c4t[s][i - 20:i])
        ll = min(r[3] for r in c4t[s][i - 20:i])
        _, o, h, l, c = c4t[s][i][:5]
        if l < ll and c > ll:
            return ("long", 1.0 * a, 2.0 * a, 12, None)
        if h > hh and c < hh:
            return ("short", 1.0 * a, 2.0 * a, 12, None)
        return None

    def g_keltner(s, i):
        a, xf = at[s][i], et20[s][i]
        if not (a and xf):
            return None
        dt = dtr.get(s, {}).get(c4t[s][i][0] // 86400)
        if dt not in (-1, 1):        # [(ml)] no claim -> no fade, fail-closed
            return None
        c = c4t[s][i][4]
        if c > xf * (1 + 2.25 * a) and dt <= 0:
            return ("short", 1.5 * a, 2.25 * a, 20, None)
        if c < xf * (1 - 2.25 * a) and dt >= 0:
            return ("long", 1.5 * a, 2.25 * a, 20, None)
        return None

    for fn, name in ((g_pullback, "pullback"), (g_failtest, "failtest"),
                     (g_keltner, "keltner")):
        sigs = {}
        for s in c4t:
            out = []
            for i in range(56, len(c4t[s]) - 1):
                r = fn(s, i)
                if r:
                    out.append((i,) + r)
            sigs[s] = out
        closed = run_portfolio(sigs, c4t, 2, 14400, at)
        summarize(f"GRIMES trailing-120d {name}", closed, dt4)

    # ---------------- HULL
    # LIQUID set only — the fundings cache also carries the (mf) carry-cell
    # coins, and the bot's [2M,10M) volume band excludes them. Leaking them
    # in was measured once by accident: the rule collapses to +$0.05 on the
    # thin names — i.e. the volume floor is LOAD-BEARING, kept as a finding.
    series = {s: {t: v * 8760.0 for t, v in fund[s]}
              for s in UNIVERSE if s in fund}
    all_t = sorted({t for s in series.values() for t in s})
    fdays = (all_t[-1] - all_t[0]) / 86400
    CLIP, RT, HI, EXIT, HOLD, MARGIN, CAP = 80.0, 0.003, 0.20, 0.035, 504, 1.3, 4
    LO = RT * 8760.0 / 336.0

    def hull_run(persist_h, grace_h):
        open_pos, closed = {}, []
        for t in all_t:
            for sym in list(open_pos):
                p = open_pos[sym]
                apr = series[sym].get(t)
                if apr is None:
                    continue
                recv = apr * p["side"] < 0
                hourly = abs(apr) / 8760.0 * CLIP
                p["acc"] += hourly if recv else -hourly
                p["pay"] = 0 if recv else p["pay"] + 1
                p["held"] += 1
                why = None
                if p["pay"] > grace_h:
                    why = "flip"
                elif p["acc"] >= RT * CLIP * MARGIN and abs(apr) < EXIT:
                    why = "decay_paid"
                elif p["held"] >= HOLD:
                    why = "max_hold"
                elif p["acc"] < -0.02 * CLIP:
                    why = "bleed"
                if why:
                    closed.append(dict(pnl=p["acc"] - RT * CLIP, t=t, why=why))
                    del open_pos[sym]
            if len(open_pos) < CAP:
                for sym in series:
                    if sym in open_pos or len(open_pos) >= CAP:
                        continue
                    w = [series[sym].get(t - 3600 * k)
                         for k in range(persist_h)]
                    if any(x is None for x in w):
                        continue
                    if len({1 if x > 0 else -1 for x in w}) != 1:
                        continue
                    if not all(LO <= abs(x) < HI for x in w):
                        continue
                    open_pos[sym] = dict(side=-1 if w[0] > 0 else 1,
                                         acc=0.0, held=0, pay=0)
        return closed

    for persist, grace, tag in ((6, 1, "grace 1h (REFUTED — churn)"),
                                (24, 24, "persist24/grace24 (SHIPPED)")):
        hc = hull_run(persist, grace)
        if not hc:
            print(f"HULL {tag}: ZERO closes")
            continue
        pnls = [c["pnl"] for c in hc]
        n = len(pnls)
        cs = sorted(hc, key=lambda c: c["t"])
        half = n // 2
        print(f"HULL {tag}: n={n} tot=${sum(pnls):.2f} "
              f"mean=${sum(pnls)/n:.3f} t={t_stat(pnls):.2f} "
              f"h1=${sum(c['pnl'] for c in cs[:half]):.2f} "
              f"h2=${sum(c['pnl'] for c in cs[half:]):.2f} "
              f"c/30d={n/fdays*30:.1f}")

    # ---------------- CARRY-CELL GRACE ((mf)): Hull's finding on the
    # carry cohort's own gate (>=20% TRUE, persist 6h, kiyosaki-form exits,
    # 6 slots), over the cell's coin population. No historical volume floor
    # is modelable — declared; the ex-AVNT split covers the thin-name risk.
    cell = {s: {t: v * 8760.0 for t, v in fund[s]}
            for s in CARRY_CELL_COINS if s in fund}
    cell_t = sorted({t for s in cell.values() for t in s})
    cdays = (cell_t[-1] - cell_t[0]) / 86400 if cell_t else 0

    def carry_run(grace_h):
        open_pos, closed = {}, []
        for t in cell_t:
            for sym in list(open_pos):
                p = open_pos[sym]
                apr = cell[sym].get(t)
                if apr is None:
                    continue
                recv = apr * p["side"] < 0
                hourly = abs(apr) / 8760.0 * CLIP
                p["acc"] += hourly if recv else -hourly
                p["pay"] = 0 if recv else p["pay"] + 1
                p["held"] += 1
                net = p["acc"] - RT * CLIP
                why = None
                if p["pay"] > grace_h:
                    why = "flip"
                elif abs(apr) < 0.01875 and net >= 0.03:
                    why = "decay_paid"
                elif p["held"] >= 336:
                    why = "max_hold"
                elif net <= -0.02 * CLIP:
                    why = "bleed"
                if why:
                    closed.append(dict(sym=sym, pnl=net, t=t))
                    del open_pos[sym]
            if len(open_pos) < 6:
                for sym in cell:
                    if sym in open_pos or len(open_pos) >= 6:
                        continue
                    w = [cell[sym].get(t - 3600 * k) for k in range(6)]
                    if any(x is None for x in w):
                        continue
                    if len({1 if x > 0 else -1 for x in w}) != 1:
                        continue
                    if not all(abs(x) >= 0.20 for x in w):
                        continue
                    open_pos[sym] = dict(side=-1 if w[0] > 0 else 1,
                                         acc=0.0, held=0, pay=0)
        return closed

    for g in (1, 6, 24):
        cc = carry_run(g)
        if not cc:
            print(f"CARRY-CELL grace={g}h: ZERO closes")
            continue
        pnls = [c["pnl"] for c in cc]
        n = len(pnls)
        cs = sorted(cc, key=lambda c: c["t"])
        half = n // 2
        ex_avnt = sum(c["pnl"] for c in cc if c["sym"] != "AVNT")
        print(f"CARRY-CELL grace={g}h: n={n} tot=${sum(pnls):.2f} "
              f"t={t_stat(pnls):.2f} "
              f"h1=${sum(c['pnl'] for c in cs[:half]):.2f} "
              f"h2=${sum(c['pnl'] for c in cs[half:]):.2f} "
              f"ex-AVNT=${ex_avnt:.2f} c/30d={n/cdays*30:.1f}")


if __name__ == "__main__":
    main()
