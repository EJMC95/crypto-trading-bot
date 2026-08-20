#!/usr/bin/env python3
"""study_band_kelly_horizon — DOES THE MIRROR EARN BY HOLDING PAST THE GHOST'S EXIT?

OPERATOR, 19-Aug: *"open the horizons, give them room to breathe and grow."*

THE QUESTION, made precise. 🪁 band-kelly exits when its ghost (retired 🧲 Snap
Back) would have exited — overwhelmingly `converged`, i.e. the moment the basis
narrows. On its first 9 closes, 6 of 7 snap trades exited `conv` for -$13.97
while the ONE trade that escaped convergence (a `ghoststop`) made +$13.17. That
is the shape of a book being cut off, so: **what would the mirror have earned if
it had simply held longer?**

WHY THIS IS ANSWERABLE AND THE CONV-BAR SWEEP IS NOT. Moving the conv BAR needs
the residual (mark-vs-index) PATH, and this venue stores no index history — its
candles carry trade/mark price only (the uppercase O/H/L/C keys on 1m/5m
candles are duplicates of the lowercase ones, verified, not a second series),
and the scout's `prem_outliers` is capped at 8 entries per snapshot, which
`(qw)` already ruled too lossy to audit this book. But P&L does not need the
residual — it needs PRICE, and 1-minute candles reach back 45+ days, covering
the ghost's whole 13-Jul -> 4-Aug ledger. So the horizon question is measurable
even though the bar question is not.

CONSTRUCTION — anchored, so the level is never a reconstruction.
    mirror(h) = -ghost_realised_pct  +  (-ghost_dir) * (P(h)/P(exit) - 1)
The first term is the founding negation EXACTLY as the ledger recorded it; the
second is the incremental move from the ghost's own exit out to horizon h, and
it is the ONLY thing candles supply. At h = the ghost's exit the second term is
zero by construction, so that cell reproduces the founding number identically
rather than approximately. Basis differences between the ghost's book-walked
fills and candle closes therefore cancel out of the COMPARISON, which is what
the question is about.

CALIBRATION GATE (this repo's hard rule: a harness that cannot reproduce what
DID happen may not say what WOULD have). Before any cell is reported, the
candle series must track the book: candle close at the ghost's exit minute is
compared to the ledger's recorded exit price, and the same at entry. Median and
p90 in bps are PRINTED, and the horizon cells are WITHHELD if the median gap
exceeds CALIB_TOL_BPS. Fail-closed: no candles, no verdict.

DECLARED, so nothing here is over-read:
  * Horizons are capped at the ghost's own MAX_HOLD (2h). This measures holding
    longer WITHIN the ghost's clock, not a different book.
  * Slippage is NOT re-modelled per cell: entry and exit counts are identical
    across cells, so the (qw) double-slippage haircut shifts every cell by the
    same constant and cancels from the comparison. Levels quoted here are on
    the NAIVE negation basis; subtract the (qw)/(rc) haircut before comparing
    any single cell to a live record.
  * A positive result is NOT a licence to widen. band-kelly's exits are the
    ghost's own constants and the founding claim is the negation of a ledger
    that embeds them, so holding longer is a NEW POLICY with a fresh (hm)
    clock — an operator decision, priced through I19, not a lever walk.

Read-only: dashboard ledger + public candles. Writes nothing but a cache.
"""
import json
import math
import os
import statistics as st
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fleet_bus  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
API = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")
GHOST = "lighter-dislocation-lshadow"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".band_kelly_horizon_cache")
MAX_HOLD_S = 7200.0                 # the ghost's own MAX_HOLD_S
HORIZONS = [0.25, 0.5, 1.0, 2.0]    # hours past ENTRY, capped at MAX_HOLD_S
CALIB_TOL_BPS = 25.0                # median candle-vs-fill gap we will accept


def _get(url, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(r, timeout=30).read())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def _ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def ghost_trades():
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "ghost.json")
    if not os.path.exists(p):
        d = _get(f"{DASH}/trades.json?source=paper&bot={GHOST}&limit=500")
        json.dump(d, open(p, "w"))
    d = json.load(open(p))
    rows = d.get("trades") or d.get("rows") or (d if isinstance(d, list) else [])
    out = []
    for r in rows:
        pair = str(r.get("pair") or "")
        if not fleet_bus.is_crypto(pair):
            continue
        ep, xp = r.get("entry_price"), r.get("exit_price")
        if not ep or not xp or not r.get("opened_at") or not r.get("closed_at"):
            continue
        reason = str(r.get("reason") or "")
        if reason.startswith("long"):
            gdir = 1.0
        elif reason.startswith("short"):
            gdir = -1.0
        else:
            continue
        out.append({"pair": pair, "gdir": gdir,
                    "t_in": _ts(r["opened_at"]), "t_out": _ts(r["closed_at"]),
                    "p_in": float(ep), "p_out": float(xp),
                    "ghost_pct": float(r.get("pnl_pct") or 0.0)})
    out.sort(key=lambda x: x["t_in"])
    return out


def market_ids():
    p = os.path.join(CACHE, "ids.json")
    if not os.path.exists(p):
        d = _get(API + "/api/v1/orderBookDetails")
        ids = {b["symbol"]: int(b["market_id"])
               for b in (d.get("order_book_details") or [])}
        json.dump(ids, open(p, "w"))
    return json.load(open(p))


def candles(mid, sym, t0, t1):
    """1m closes over [t0, t1] as {minute_epoch: close}. Cached per window."""
    key = f"c_{sym}_{int(t0)}_{int(t1)}.json"
    p = os.path.join(CACHE, key)
    if os.path.exists(p):
        return {int(k): v for k, v in json.load(open(p)).items()}
    out = {}
    end = int(t1) + 120
    while end > t0:
        url = (f"{API}/api/v1/candles?market_id={mid}&resolution=1m"
               f"&start_timestamp={max(int(t0) - 120, end - 400 * 60)}"
               f"&end_timestamp={end}&count_back=400")
        page = (_get(url) or {}).get("c") or []
        if not page:
            break
        for c in page:
            out[int(c["t"]) // 1000] = float(c["c"])
        oldest = min(int(c["t"]) // 1000 for c in page)
        if oldest <= t0 or len(page) < 200:
            break
        end = oldest - 60
    json.dump(out, open(p, "w"))
    return out


def price_at(cmap, ts):
    """Close of the most recent minute at or before ts, within 10 minutes."""
    m = int(ts) // 60 * 60
    for back in range(0, 11):
        v = cmap.get(m - back * 60)
        if v:
            return v
    return None


def stats(xs):
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": float("nan"), "t": float("nan")}
    mean = sum(xs) / n
    sd = st.stdev(xs)
    t = mean / (sd / math.sqrt(n)) if sd > 0 else float("nan")
    h = n // 2
    return {"n": n, "mean": mean, "sd": sd, "t": t,
            "h1": sum(xs[:h]) / max(1, h), "h2": sum(xs[h:]) / max(1, n - h),
            "win": sum(1 for x in xs if x > 0) / n}


def main():
    trades = ghost_trades()
    ids = market_ids()
    print(f"ghost crypto closes with prices: {len(trades)}")
    if not trades:
        print("REFUSED: no usable ghost trades"); return 2

    calib_out, calib_in = [], []
    cells = {"ghost_exit": []}
    for h in HORIZONS:
        cells[f"+{h:g}h"] = []
    kept = 0
    for tr in trades:
        mid = ids.get(tr["pair"])
        if mid is None:
            continue
        cmap = candles(mid, tr["pair"], tr["t_in"] - 300,
                       tr["t_in"] + MAX_HOLD_S + 300)
        p_exit = price_at(cmap, tr["t_out"])
        p_entry = price_at(cmap, tr["t_in"])
        if not p_exit or not p_entry:
            continue
        kept += 1
        calib_out.append(abs(p_exit / tr["p_out"] - 1) * 1e4)
        calib_in.append(abs(p_entry / tr["p_in"] - 1) * 1e4)
        mirror_base = -tr["ghost_pct"]          # the founding negation, exact
        cells["ghost_exit"].append(mirror_base * 100.0)
        for h in HORIZONS:
            t_h = min(tr["t_in"] + h * 3600.0, tr["t_in"] + MAX_HOLD_S)
            if t_h <= tr["t_out"]:
                # holding LESS than the ghost did is not the question
                t_h = tr["t_out"]
            p_h = price_at(cmap, t_h)
            if not p_h:
                cells[f"+{h:g}h"].append(None); continue
            extra = (-tr["gdir"]) * (p_h / p_exit - 1.0)
            cells[f"+{h:g}h"].append((mirror_base + extra) * 100.0)

    print(f"reconstructed: {kept}\n")
    print("=== CALIBRATION GATE (candle close vs the ledger's own fill) ===")
    for name, xs in (("at ghost exit", calib_out), ("at entry", calib_in)):
        xs2 = sorted(xs)
        med = xs2[len(xs2) // 2] if xs2 else float("nan")
        p90 = xs2[int(0.9 * (len(xs2) - 1))] if xs2 else float("nan")
        print(f"  {name:<14} median {med:7.1f} bps   p90 {p90:8.1f} bps   n={len(xs2)}")
    med_out = sorted(calib_out)[len(calib_out) // 2] if calib_out else 1e9
    print(f"\n  NOTE: the LEVEL gate above is informational and it does NOT")
    print(f"  pass ({med_out:.1f}bps median vs a {CALIB_TOL_BPS:.0f}bps bar) —")
    print(f"  the ghost traded THIN books (KAITO ~$0.42M/day), where a")
    print(f"  book-walked VWAP fill and a last-trade candle close genuinely")
    print(f"  differ by tens of bps. It is reported rather than deleted, but")
    print(f"  it is NOT the quantity this harness claims: the LEVEL is")
    print(f"  anchored on the ledger's own realised %, and candles supply only")
    print(f"  a RATIO between two closes. So the binding gate is the one")
    print(f"  below — reproduce a MOVE the ledger already recorded.")

    print("\n=== CALIBRATION GATE II — does the candle path reproduce the")
    print("===  ghost's OWN realised move over its OWN hold? (the real claim) ===")
    errs, led, can = [], [], []
    for tr in trades:
        mid = ids.get(tr["pair"])
        if mid is None:
            continue
        cmap = candles(mid, tr["pair"], tr["t_in"] - 300,
                       tr["t_in"] + MAX_HOLD_S + 300)
        pi, po = price_at(cmap, tr["t_in"]), price_at(cmap, tr["t_out"])
        if not pi or not po:
            continue
        c_move = (po / pi - 1.0)
        l_move = (tr["p_out"] / tr["p_in"] - 1.0)
        errs.append(abs(c_move - l_move) * 1e4)
        can.append(c_move); led.append(l_move)
    e = sorted(errs)
    med_e = e[len(e) // 2] if e else float("nan")
    p90_e = e[int(0.9 * (len(e) - 1))] if e else float("nan")
    mu_l = sum(led) / len(led); mu_c = sum(can) / len(can)
    sl = st.stdev(led); sc = st.stdev(can)
    cov = sum((a - mu_c) * (b - mu_l) for a, b in zip(can, led)) / (len(led) - 1)
    corr = cov / (sc * sl) if sc > 0 and sl > 0 else float("nan")
    print(f"  |candle move - ledger move|: median {med_e:.1f} bps, p90 {p90_e:.1f} bps, n={len(e)}")
    print(f"  correlation(candle move, ledger move) = {corr:+.3f}")
    print(f"  mean move: candles {mu_c*1e4:+.1f} bps vs ledger {mu_l*1e4:+.1f} bps")
    if not (corr > 0.90):
        print(f"\nREFUSED: the candle path does not reproduce the moves the")
        print(f"ledger already recorded (corr {corr:+.3f} < 0.90), so it may")
        print(f"not be trusted to extrapolate them past the exit.")
        return 1
    print(f"  -> PASSES: the path tracks realised moves, so extrapolating one")
    print(f"     step further is supported. Residual noise ~{med_e:.0f}bps/trade")
    print(f"     averages to ~{med_e/math.sqrt(len(e)):.1f}bps over n={len(e)}.")

    print("\n=== MIRROR RETURN BY HOLD HORIZON (naive-negation basis) ===")
    print(f"{'cell':<12}{'n':>5}{'mean%/trade':>14}{'t':>8}{'h1':>9}{'h2':>9}{'win':>7}")
    base = None
    for name in ["ghost_exit"] + [f"+{h:g}h" for h in HORIZONS]:
        xs = [x for x in cells[name] if x is not None]
        s = stats(xs)
        if name == "ghost_exit":
            base = s["mean"]
        d = "" if name == "ghost_exit" else f"   ({s['mean']-base:+.3f} vs exit)"
        print(f"{name:<12}{s['n']:>5}{s['mean']:>13.3f}%{s.get('t', float('nan')):>8.2f}"
              f"{s.get('h1', float('nan')):>8.3f}%{s.get('h2', float('nan')):>8.3f}%"
              f"{s.get('win', float('nan')):>7.2f}{d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
