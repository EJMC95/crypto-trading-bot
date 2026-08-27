#!/usr/bin/env python3
"""study_band_kelly_2026-08-18.py — founding study for 🪁 band-kelly, the
MIRROR book (operator, 18-Aug: "Make a bot that does the exact opposite of
all of the major losing sequences and trends, flipping but also using every
enhancement and knowledge we have to ride an uptrend - expansion is the
premise").

THE PREMISE, MADE FALSIFIABLE. "Do the opposite of the losers" is only a
strategy if the losers are MEASURED losers (era-clean, quarantine-filtered,
statistically established) and the opposite is taken over the SAME windows
the loser would have traded — enter when the ghost enters, hold the other
side, exit when the ghost exits. At mark with zero venue fees, that mirror's
per-trade return is the EXACT negation of the ghost's, so a loser ledger at
t <= -2.0 is founding evidence at t >= +2.0 for the mirror, minus the slip
the mirror models on itself. Everything else this study does is guarding
that construction against the known traps:

  * I7  — outcome-conditioned exits: a `_sl` bucket is a loser BY
          CONSTRUCTION. The unit here is the ENTRY FAMILY pooled across all
          its exits, never a single exit bucket.
  * I16 — luck vs evidence: roster bar is |t| >= 2.0 AND n >= 30 on the
          pooled family. (mr)'s BH discipline is inherited by taking only
          families the fleet has already adjudicated as losers or vetoed.
  * (hm) — a positive mean is not an edge on a trending tape: the replayed
          mirror is graded against a duration-matched random-SHORT
          benchmark, never against zero.
  * (nu) — tail concentration: a mirror SHORT of a breakout family is short
          a fat right tail. The replay reports top-3 |trade| share, worst
          trade and portfolio maxDD, and the stop grid is pre-declared.
  * (nt) — calibration: the harness must reproduce the GHOST's own failure
          before it may speak about the mirror. The ghost-long replay is the
          positive control: if the ghost does not lose in replay, the
          mirror's generalisation claim is withheld (the ledger negation
          then stands only as a 40-close exhibit, below its own bar).
  * I20 — supply: a mirror may only take families that are UNOWNED forward
          (book retired, or lens structurally untraded). Inverting a LIVING
          book's entries would make the fleet hold A and anti-A at once.

PRE-DECLARED VERDICT LOGIC (written before the numbers existed):
  A family ships in the v1 roster iff ALL of:
    1. pooled ledger |t| >= 2.0 and n >= 30 (era-scoped, quarantined rows
       out, (nm)-void windows out);
    2. its forward signal is computable from code this repo already ships
       (the ghost's own module — never a re-implementation);
    3. its supply is unowned forward (I20);
    4. where a candle replay is possible, the MIRROR portfolio must be
       positive with t >= +1.0 AND beat the random-short benchmark at
       P <= 0.10 AND survive a protective stop (some grid cell keeps
       t >= +1.0 with maxDD < 15%); where a replay is impossible, that
       impossibility is DECLARED and the family ships on the ledger
       negation alone, record-graded forward (I14).
  Families failing any leg are REPORTED with their numbers and refused.

Usage:
    python3 scripts/study_band_kelly_2026-08-18.py --fetch   # pull ledgers+tape
    python3 scripts/study_band_kelly_2026-08-18.py           # offline analysis
"""
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bot_pnl_store as store                    # noqa: E402  (quarantine)
from lighter_family_bot import MomoBreakout      # noqa: E402  (the REAL ghost)

CACHE = os.path.join(HERE, ".band_kelly_cache")
API = "https://mainnet.zklighter.elliot.ai"
DASH = "https://pnl-dashboard-production-858c.up.railway.app"

# The cohort's measured 18-coin universe (study_books_cohort convention) —
# BTC is required (the ghost's tide gate reads BTC's own 4h EMA200).
UNIVERSE = ("BTC,ETH,SOL,HYPE,LIT,ZEC,PUMP,XRP,UNI,ETHFI,BNB,ENA,"
            "DOGE,NEAR,XMR,AVAX,LINK,TAO").split(",")

# Ledger candidates: every family the fleet has measured as a loser with a
# forward story worth checking, plus report-only rows so refusals carry
# numbers. (bot row id, short label)
LEDGER_BOTS = [
    ("lighter-dislocation-lshadow", "snapback (retired 4-Aug (jh))"),
    ("crypto-breakout-4h-lshadow", "breakout-4h (retired 14-Aug (mr))"),
    ("freqtrade-dad-lshadow", "dad (retired 15-Aug (nf), same MomoBreakout)"),
    ("lighter-ticket-taker-lshadow", "taker shadow (dip lens vetoed)"),
    ("lighter-ticket-taker-lighter", "taker live arm (if row exists)"),
    ("pm-gillard-lshadow", "pm-gillard (retired (nf); report-only)"),
    ("pm-abbott-lshadow", "pm-abbott (retired (nf); report-only)"),
    ("pm-rudd-lshadow", "pm-rudd (retired (nf); report-only)"),
    ("pm-morrison-lshadow", "pm-morrison (retired (nf); report-only)"),
    ("crypto-intraday-15m-lshadow", "intraday-15m (retired (nf); report-only)"),
]

# Policy-era floors for the graded window. Snap Back's own retirement grade
# (jh) was pooled over its whole ledger (price book — outside POLICY_ERA on
# purpose), so its primary window here is pooled too, with a post-(fz)
# (adaptive gate, 30-Jul) split reported as sensitivity, not as the claim.
ERA_FLOOR = {
    "crypto-breakout-4h-lshadow": "2026-07-17",   # docket in-era window (mr)
    "freqtrade-dad-lshadow": "2026-07-17",
}

CLIP = 80.0          # replay clip, the family-book convention
CAP = 6              # crypto-breakout-4h's own max_open
COST_SIDE = 0.0005   # 5bps/side modelled slip (venue fee 0, measured)
GHOST_STOPLOSS = 0.12          # the ghost book's own freqtrade stop (-12%)
STOP_GRID = (None, 3.0, 2.0, 1.5)   # my protective stop, xATR14 at entry
RANDOM_DRAWS = 300
SEED = 20260818


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print(f"FAIL {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def fetch_all():
    os.makedirs(CACHE, exist_ok=True)
    # 1) ledgers (public read endpoint — the (gk) review-seat path; no DB)
    for bot, _label in LEDGER_BOTS:
        d = _get(f"{DASH}/trades.json?source=paper&bot="
                 + urllib.parse.quote(bot) + "&limit=5000")
        rows = (d or {}).get("trades") or []
        json.dump(rows, open(os.path.join(CACHE, f"ledger_{bot}.json"), "w"))
        print(f"ledger {bot}: {len(rows)} rows")
    # 2) 4h candles, full history (pages until the venue runs out)
    d = _get(API + "/api/v1/orderBookDetails")
    ids = {b["symbol"]: int(b["market_id"])
           for b in (d.get("order_book_details") or [])}
    res, res_sec, pages = "4h", 14400, 10
    out = {}
    for sym in UNIVERSE:
        if sym not in ids:
            print(f"tape: {sym} not on venue, skipped")
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
        print(f"4h {sym}: {len(out[sym])} bars")
    json.dump(out, open(os.path.join(CACHE, "candles_4h.json"), "w"))
    print("cached in", CACHE)


# ---------------------------------------------------------------- statistics
def t_stat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(var / n) if var > 0 else 0.0


def halves(xs):
    h = len(xs) // 2
    return sum(xs[:h]), sum(xs[h:])


def max_drawdown(path):
    peak, dd = -1e18, 0.0
    for v in path:
        peak = max(peak, v)
        dd = max(dd, peak - v)
    return dd


# ------------------------------------------------------------ part 1: ledgers
def family_of(tag):
    """`long-dip_hold` -> ('long-dip', 'hold'); `short_converged` ->
    ('short', 'converged'). Split on the FIRST underscore: left is the entry
    family (side[-lens]), right is the exit — pooling across exits is the I7
    rule, the exit split is reported only to show the pooling mattered."""
    s = str(tag or "?")
    if "_" in s:
        fam, ex = s.split("_", 1)
    else:
        fam, ex = s, "?"
    return fam, ex


def ledger_rows(bot):
    try:
        rows = json.load(open(os.path.join(CACHE, f"ledger_{bot}.json")))
    except Exception:  # noqa: BLE001
        return []
    era = ERA_FLOOR.get(bot)
    out = []
    for r in rows:
        # [(vb)] KEYWORDS, because this call shipped with `bot` and `pair`
        # SWAPPED. The publisher is `is_quarantined(bot, pair, closed_at)` and
        # its match is `p == q_pair and q_bot in b`, so with the two positional
        # strings reversed `p` held a BOT NAME, could never equal a quarantined
        # PAIR, and the filter returned False for every row in the fleet,
        # forever. Two same-typed positional strings is the whole trap; naming
        # them makes the swap unrepresentable at this site, and
        # `tests/autonomy/test_payload_contracts.py` now catches it at every
        # other one.
        if store.is_quarantined(bot=r.get("bot"), pair=r.get("pair"),
                                closed_at=r.get("closed_at")):
            continue
        if era and str(r.get("opened_at") or "")[:10] < era:
            continue
        if r.get("pnl_pct") is None:
            continue
        out.append(r)
    out.sort(key=lambda r: str(r.get("closed_at") or ""))
    return out


def negation_table():
    print("\n== PART 1 — LEDGER NEGATION (entry families pooled across "
          "exits, quarantine+era filtered) ==")
    print(f"{'bot':34s} {'family':16s} {'n':>4s} {'ghost mean%':>11s} "
          f"{'ghost t':>8s} {'mirror mean%':>12s} {'mirror t':>9s} "
          f"{'h1$,h2$ (mirror)':>18s}")
    results = {}
    for bot, label in LEDGER_BOTS:
        rows = ledger_rows(bot)
        if not rows:
            continue
        fams = {}
        for r in rows:
            fam, _ex = family_of(r.get("tag") or r.get("reason"))
            fams.setdefault(fam, []).append(r)
        for fam in sorted(fams, key=lambda f: -len(fams[f])):
            rs = fams[fam]
            pct = [r["pnl_pct"] for r in rs]
            usd = [-(r.get("pnl_abs") or 0.0) for r in rs]   # mirror dollars
            h1, h2 = halves(usd)
            m = sum(pct) / len(pct)
            t = t_stat(pct)
            print(f"{bot:34s} {fam:16s} {len(rs):4d} {100 * m:11.3f} "
                  f"{t:8.2f} {100 * -m:12.3f} {-t:9.2f} "
                  f"{h1:+8.2f},{h2:+7.2f}")
            results[(bot, fam)] = {
                "n": len(rs), "ghost_mean_pct": 100 * m, "ghost_t": t,
                "mirror_mean_pct": -100 * m, "mirror_t": -t,
                "mirror_h1_usd": h1, "mirror_h2_usd": h2,
                "span": (str(rs[0].get("closed_at"))[:10],
                         str(rs[-1].get("closed_at"))[:10]),
            }
        print(f"    -- {label}")
    return results


def snapback_sensitivity():
    """Post-(fz) split for Snap Back (adaptive gate shipped 30-Jul): the
    pooled grade is the (jh) retirement's own basis; this split shows
    whether the mirror claim survives the gate's own policy change."""
    rows = ledger_rows("lighter-dislocation-lshadow")
    print("\n   snapback splits (mirror sign):")
    for label, sel in (
            ("pooled", rows),
            ("pre-(fz) <30-Jul", [r for r in rows
                                  if str(r["closed_at"])[:10] < "2026-07-30"]),
            ("post-(fz) >=30-Jul", [r for r in rows
                                    if str(r["closed_at"])[:10] >= "2026-07-30"]),
    ):
        for side in ("short", "long"):
            rs = [r for r in sel
                  if family_of(r.get("tag") or r.get("reason"))[0] == side]
            if len(rs) < 3:
                print(f"     {label:20s} ghost-{side}: n={len(rs)} (thin)")
                continue
            pct = [r["pnl_pct"] for r in rs]
            print(f"     {label:20s} ghost-{side}: n={len(rs):3d} "
                  f"mirror mean%={-100 * sum(pct) / len(pct):+.3f} "
                  f"mirror t={-t_stat(pct):+.2f}")


# ---------------------------------------------------- part 2: brkfade replay
def load_tape():
    return json.load(open(os.path.join(CACHE, "candles_4h.json")))


def ghost_signals(tape):
    """Drive the REAL retired class (lighter_family_bot.MomoBreakout) bar by
    bar, exactly as its live loop did: signals on the closed-bar prefix, BTC
    tide from BTC's own series at the same closed bar. Returns per coin a
    list of (i, kind) where kind is 'enter' or 'exit' evaluated at bar i's
    close. The still-forming bar votes on nothing (prefix ends at i)."""
    mb = MomoBreakout("ghost", tf="4h", stoploss=-GHOST_STOPLOSS,
                      max_open=CAP, style="momo-breakout-4h")
    btc = tape.get("BTC") or []
    btc_ema = {}
    if btc:
        closes = [r[4] for r in btc]
        # EMA200 exactly as the family bot computes it (ema_series warmup)
        from lighter_family_bot import ema_series
        es = ema_series(closes, 200)
        for r, e in zip(btc, es):
            if e is not None:
                btc_ema[r[0]] = r[4] > e
    out = {}
    for sym, rows in tape.items():
        if sym == "BTC":
            continue
        evs = []
        c = [r[4] for r in rows]
        h = [r[2] for r in rows]
        l = [r[3] for r in rows]
        v = [1.0] * len(rows)
        for i in range(230, len(rows)):
            bars = {"c": c[:i + 1], "h": h[:i + 1], "l": l[:i + 1],
                    "v": v[:i + 1]}
            tide = btc_ema.get(rows[i][0])
            extra = {"btc_tide_up": tide} if tide is not None else None
            sig = mb.signals(bars, extra)
            if not sig:
                continue
            if sig.get("enter"):
                evs.append((i, "enter"))
            if sig.get("exit"):
                evs.append((i, "exit"))
        out[sym] = evs
        print(f"   ghost {sym}: {sum(1 for _, k in evs if k == 'enter')} "
              f"enters, {sum(1 for _, k in evs if k == 'exit')} exits")
    return out


def atr14(rows, i):
    """Wilder ATR14 fraction at bar i (entry-bar risk unit for my stop)."""
    if i < 16:
        return None
    a, prev_c, trs = None, None, []
    for r in rows[:i + 1]:
        _, o, hh, ll, cc = r
        tr = (hh - ll) if prev_c is None else max(hh - ll, abs(hh - prev_c),
                                                  abs(ll - prev_c))
        prev_c = cc
        if a is None:
            trs.append(tr)
            if len(trs) == 14:
                a = sum(trs) / 14
        else:
            a = (a * 13 + tr) / 14
    return (a / prev_c) if (a and prev_c) else None


def replay(tape, events, side, my_stop_atr):
    """Portfolio replay: `side` 'long' replays the GHOST itself (the
    calibration control), 'short' replays the MIRROR. Entry next-bar open
    after the enter signal ((ne) LAG-1); exit next-bar open after the ghost's
    exit signal; the ghost's own -12% stoploss is honoured intra-bar (for
    the mirror that stop is a PROFIT-side cover — mirror fidelity); my
    protective stop (mirror only, my_stop_atr x ATR14-at-entry) is checked
    intra-bar CONSERVATIVELY including the entry bar's post-open range
    ((ml)). One position per coin, global cap, sequential — an entry at cap
    is skipped and counted, so throughput is paid for (hl)."""
    sign = 1.0 if side == "long" else -1.0
    open_pos = {}
    closed = []
    skipped_cap = 0
    # merge per-coin events into a global time-ordered stream of bar starts
    stream = []
    for sym, evs in events.items():
        rows = tape[sym]
        for i, kind in evs:
            stream.append((rows[i][0], sym, i, kind))
    stream.sort()
    index_of = {sym: {r[0]: j for j, r in enumerate(rows)}
                for sym, rows in tape.items()}

    def step_exits(now_t):
        """Advance every open position through bars closing at/before now_t."""
        for sym in list(open_pos):
            p = open_pos[sym]
            rows = tape[sym]
            j = p["bar"]
            while j < len(rows) and rows[j][0] <= now_t:
                _t, o, hh, ll, cc = rows[j]
                # entry bar: only the post-open range counts ((ml))
                stop_px = None
                reason = None
                if side == "short":
                    if my_stop_atr and hh >= p["my_stop"]:
                        stop_px, reason = p["my_stop"], "stop"
                    elif ll <= p["ghost_stop"]:
                        stop_px, reason = p["ghost_stop"], "ghost_sl"
                else:
                    if ll <= p["ghost_stop"]:
                        stop_px, reason = p["ghost_stop"], "ghost_sl"
                if stop_px is not None:
                    ret = sign * (stop_px / p["entry"] - 1.0) - 2 * COST_SIDE
                    closed.append({"sym": sym, "ret": ret,
                                   "t_in": p["t_in"], "t_out": _t,
                                   "bars": j - p["bar0"], "exit": reason})
                    del open_pos[sym]
                    break
                p["bar"] = j + 1
                j += 1

    for now_t, sym, i, kind in stream:
        step_exits(now_t)
        rows = tape[sym]
        if kind == "exit" and sym in open_pos:
            p = open_pos[sym]
            if i + 1 < len(rows):
                px = rows[i + 1][1]
                ret = sign * (px / p["entry"] - 1.0) - 2 * COST_SIDE
                closed.append({"sym": sym, "ret": ret, "t_in": p["t_in"],
                               "t_out": rows[i + 1][0],
                               "bars": i + 1 - p["bar0"],
                               "exit": "ghost_breakdown"})
                del open_pos[sym]
        elif kind == "enter" and sym not in open_pos:
            if len(open_pos) >= CAP:
                skipped_cap += 1
                continue
            if i + 1 >= len(rows):
                continue
            entry = rows[i + 1][1]
            if not entry or entry <= 0:
                continue
            a = atr14(rows, i)
            open_pos[sym] = {
                "entry": entry, "t_in": rows[i + 1][0],
                "bar0": i + 1, "bar": i + 1,
                "ghost_stop": entry * (1.0 - GHOST_STOPLOSS),
                "my_stop": (entry * (1.0 + my_stop_atr * a)
                            if (my_stop_atr and a) else float("inf")),
            }
    # close leftovers at last close (reported, not silently dropped)
    for sym, p in open_pos.items():
        rows = tape[sym]
        px = rows[-1][4]
        ret = sign * (px / p["entry"] - 1.0) - 2 * COST_SIDE
        closed.append({"sym": sym, "ret": ret, "t_in": p["t_in"],
                       "t_out": rows[-1][0], "bars": len(rows) - p["bar0"],
                       "exit": "eod"})
    closed.sort(key=lambda x: x["t_out"])
    return closed, skipped_cap


def summarize(label, closed, skipped_cap=0):
    if not closed:
        print(f"   {label}: NO TRADES")
        return None
    rets = [c["ret"] for c in closed]
    usd = [r * CLIP for r in rets]
    h1, h2 = halves(usd)
    tot = sum(usd)
    top3 = sum(sorted((abs(u) for u in usd), reverse=True)[:3])
    share = (top3 / abs(tot)) if tot else float("inf")
    path, eq = [], 0.0
    for u in usd:
        eq += u
        path.append(eq)
    dd = max_drawdown([0.0] + path)
    out = {"n": len(closed), "total": tot, "mean_pct": 100 * sum(rets) / len(rets),
           "t": t_stat(rets), "h1": h1, "h2": h2,
           "worst": min(usd), "top3_share": share,
           "maxdd_pct": 100 * dd / 1000.0, "skipped_cap": skipped_cap}
    print(f"   {label}: n={out['n']} total=${tot:+.2f} "
          f"mean={out['mean_pct']:+.3f}%/t t={out['t']:+.2f} "
          f"h1=${h1:+.2f} h2=${h2:+.2f} worst=${out['worst']:+.2f} "
          f"top3={100 * share:.0f}% maxDD={out['maxdd_pct']:.1f}% "
          f"(capped-out entries: {skipped_cap})")
    return out


def random_short_bench(tape, closed, draws=RANDOM_DRAWS):
    """(hm): duration-matched random SHORTS on the same coins. Each draw
    re-times every realized mirror trade uniformly at random (same coin,
    same hold in bars, same costs). Reports P(random total >= mirror total)
    and the same for per-trade mean and t."""
    rng = random.Random(SEED)
    real_rets = [c["ret"] for c in closed]
    real_tot, real_mean, real_t = (sum(real_rets), sum(real_rets) / len(real_rets),
                                   t_stat(real_rets))
    ge_tot = ge_mean = ge_t = 0
    for _ in range(draws):
        rets = []
        for c in closed:
            rows = tape[c["sym"]]
            nb = max(1, c["bars"])
            if len(rows) < nb + 232:
                continue
            i = rng.randint(230, len(rows) - nb - 2)
            e = rows[i + 1][1]
            x = rows[i + 1 + nb][1]
            if e and x and e > 0:
                rets.append(-(x / e - 1.0) - 2 * COST_SIDE)
        if not rets:
            continue
        ge_tot += sum(rets) >= real_tot
        ge_mean += (sum(rets) / len(rets)) >= real_mean
        ge_t += t_stat(rets) >= real_t
    print(f"   random-short bench ({draws} draws): "
          f"P(total>=mirror)={ge_tot / draws:.3f} "
          f"P(mean>=mirror)={ge_mean / draws:.3f} "
          f"P(t>=mirror)={ge_t / draws:.3f}")
    return {"p_total": ge_tot / draws, "p_mean": ge_mean / draws,
            "p_t": ge_t / draws}


def regime_split(closed, tape):
    """Item-18 declaration: mirror per-trade mean split by BTC-above-EMA200
    at entry. The ghost's own gate means entries only ever fire tide-UP, so
    a non-degenerate DOWN bucket here would mean the gate replay is broken —
    the split doubles as a harness check."""
    from lighter_family_bot import ema_series
    btc = tape.get("BTC") or []
    es = ema_series([r[4] for r in btc], 200)
    tide = {r[0]: (r[4] > e) for r, e in zip(btc, es) if e is not None}
    up = [c["ret"] for c in closed if tide.get(c["t_in"] - 14400, True)]
    dn = [c["ret"] for c in closed if not tide.get(c["t_in"] - 14400, True)]
    print(f"   regime split at entry: tide-up n={len(up)} "
          f"mean={100 * sum(up) / len(up) if up else 0:+.3f}% | "
          f"tide-down n={len(dn)} (expected ~0 by the ghost's own gate)")


def snap_deep():
    """Robustness pass on the shipped family. Cluster-robust t is IMPORTED
    from the grader ((kw) — one owner); concentration, per-coin, class and
    drift arithmetic are the (nu)/(lk)/(hm) checks in mirror form."""
    from datetime import datetime, timezone
    import golive_readiness as gr
    rows = ledger_rows("lighter-dislocation-lshadow")
    for label, sel in (("pooled", rows),
                       ("post-(fz)", [r for r in rows
                                      if str(r["closed_at"])[:10] >= "2026-07-30"])):
        pct = [-r["pnl_pct"] for r in sel]              # mirror sign
        usd = [-(r.get("pnl_abs") or 0.0) for r in sel]
        n = len(sel)
        mean = sum(pct) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in pct) / (n - 1))
        shaped = []
        for r in sel:
            dt = datetime.fromisoformat(
                str(r["closed_at"]).replace("Z", "+00:00"))
            shaped.append((-r["pnl_pct"], -(r.get("pnl_abs") or 0.0), dt))
        cl = gr.cluster_stats(shaped, mean, sd, n)
        h1, h2 = halves(usd)
        top3 = sum(sorted((abs(u) for u in usd), reverse=True)[:3])
        tot = sum(usd)
        coins = {}
        for r in sel:
            coins.setdefault(r.get("pair"), []).append(
                -(r.get("pnl_abs") or 0.0))
        by_coin = sorted(((sum(v), len(v), k) for k, v in coins.items()),
                         reverse=True)
        best_coin_share = (by_coin[0][0] / tot) if tot else float("inf")
        # class split ((lk)): non-crypto pairs in the ghost's ledger
        try:
            import fleet_bus
            crypto = [r for r in sel if fleet_bus.is_crypto(
                str(r.get("pair") or "").split("/")[0])]
        except Exception:  # noqa: BLE001
            crypto = None
        # holds -> drift arithmetic ((hm) in mirror form): tape drift is
        # ~-32.9%/438d; over the ghost's own median hold the drift term is
        # microscopic next to the measured mirror mean, so the claim is not
        # beta. Computed, not asserted.
        holds_h = []
        for r in sel:
            try:
                o = datetime.fromisoformat(
                    str(r["opened_at"]).replace("Z", "+00:00"))
                c = datetime.fromisoformat(
                    str(r["closed_at"]).replace("Z", "+00:00"))
                holds_h.append((c - o).total_seconds() / 3600.0)
            except Exception:  # noqa: BLE001
                pass
        med_hold = sorted(holds_h)[len(holds_h) // 2] if holds_h else 0.0
        drift_per_hold = -0.329 / 438.0 / 24.0 * med_hold * 100  # % per hold
        print(f"\n   snapfade deep [{label}]: n={n} mirror ${tot:+.2f} "
              f"mean={100 * mean:+.3f}%/t t={t_stat(pct):+.2f} "
              f"t_cluster={cl['t_cluster'] if cl else None} "
              f"(n_eff={cl['n_eff'] if cl else '?'}) "
              f"h1=${h1:+.2f} h2=${h2:+.2f} top3={100 * top3 / abs(tot):.0f}% "
              f"best-coin {by_coin[0][2]} {100 * best_coin_share:.0f}%")
        print(f"     median hold {med_hold:.2f}h -> short-side drift term "
              f"{drift_per_hold:+.4f}% vs mirror mean {100 * mean:+.3f}% "
              f"({abs(100 * mean / drift_per_hold) if drift_per_hold else 0:.0f}x)")
        if crypto is not None:
            cp = [-r["pnl_pct"] for r in crypto]
            print(f"     crypto-only subset: n={len(cp)} "
                  f"mean={100 * sum(cp) / len(cp) if cp else 0:+.3f}%/t "
                  f"t={t_stat(cp):+.2f} (screen deviation priced)")
        print(f"     coins: " + ", ".join(
            f"{k}:{s:+.2f}({c})" for s, c, k in by_coin[:8]))


def main():
    if "--fetch" in sys.argv:
        fetch_all()
        return
    if "--snap-deep" in sys.argv:
        snap_deep()
        return
    print("🪁 band-kelly founding study — the mirror of the measured losers")
    results = negation_table()
    snapback_sensitivity()

    print("\n== PART 2 — BRKFADE REPLAY (mirror of MomoBreakout, the REAL "
          "retired code, full 4h tape) ==")
    tape = load_tape()
    days = 0
    for sym, rows in tape.items():
        if rows:
            days = max(days, (rows[-1][0] - rows[0][0]) / 86400.0)
    print(f"   tape: {len(tape)} coins, {days:.0f} days")
    events = ghost_signals(tape)

    print("\n   -- calibration control: the GHOST ITSELF (long) must lose "
          "in replay, or the mirror claim is withheld (nt) --")
    ghost_closed, ghost_skip = replay(tape, events, "long", None)
    ghost = summarize("ghost-long (control)", ghost_closed, ghost_skip)

    print("\n   -- the MIRROR (short), stop grid pre-declared --")
    grid = {}
    for st in STOP_GRID:
        closed, skip = replay(tape, events, "short", st)
        grid[st] = (summarize(f"mirror stop={st}xATR14" if st else
                              "mirror PURE (ghost exits only)", closed, skip),
                    closed)
    pure = grid[None][0]
    bench = random_short_bench(tape, grid[None][1]) if grid[None][1] else None
    regime_split(grid[None][1], tape)

    # ------------------------------------------------------------- verdicts
    print("\n== VERDICTS (pre-declared logic from the header) ==")
    verdicts = {}

    sb = results.get(("lighter-dislocation-lshadow", "short"))
    sl = results.get(("lighter-dislocation-lshadow", "long"))
    ok_sb = (sb and sl and sb["n"] + sl["n"] >= 30
             and (sb["mirror_t"] > 0 and sl["mirror_t"] > 0))
    pooled_rows = ledger_rows("lighter-dislocation-lshadow")
    pooled_pct = [r["pnl_pct"] for r in pooled_rows]
    pooled_t = -t_stat(pooled_pct) if pooled_pct else 0.0
    ok_sb = bool(ok_sb and pooled_t >= 2.0)
    verdicts["snapfade"] = (
        "SHIP (ledger negation; replay impossible — no historical "
        "index-vs-mark tape exists; record-graded forward per I14)"
        if ok_sb else "REFUSED — pooled mirror t below bar or halves disagree")
    print(f"   snapfade: pooled mirror t={pooled_t:+.2f} n={len(pooled_pct)} "
          f"-> {verdicts['snapfade']}")

    brk_ok = False
    if ghost and pure:
        ghost_loses = ghost["t"] < 0 or ghost["total"] < 0
        stop_ok = any(v and v["t"] >= 1.0 and v["maxdd_pct"] < 15.0
                      for v, _ in (grid[s] for s in STOP_GRID if s))
        brk_ok = (ghost_loses and pure["t"] >= 1.0
                  and bench and bench["p_t"] <= 0.10 and stop_ok)
    verdicts["brkfade"] = ("SHIP" if brk_ok else
                           "REFUSED at the replay leg — ledger negation "
                           "stands as an exhibit (n=40 < its own future)")
    print(f"   brkfade: -> {verdicts['brkfade']}")

    dip_n = 0
    for bot in ("lighter-ticket-taker-lshadow", "lighter-ticket-taker-lighter"):
        for r in ledger_rows(bot):
            if family_of(r.get("tag") or r.get("reason"))[0] in (
                    "long-dip", "short-dip"):
                dip_n += 1
    verdicts["dipfade"] = ("candidate" if dip_n >= 30 else
                           f"REFUSED — n={dip_n} < 30 (I16 floor); "
                           "day-31 candidate as the sample accrues")
    print(f"   dipfade: n={dip_n} -> {verdicts['dipfade']}")

    print("\n   report-only families (fail the roster bar or forward-"
          "infeasible — parliament lens internals):")
    for (bot, fam), r in sorted(results.items()):
        if bot.startswith("pm-") or "intraday" in bot:
            print(f"     {bot} {fam}: n={r['n']} mirror_t={r['mirror_t']:+.2f}"
                  f" (forward signal lives in parliament internals)")
    json.dump({"verdicts": verdicts}, open(
        os.path.join(CACHE, "verdicts.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
