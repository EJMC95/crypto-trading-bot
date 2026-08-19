#!/usr/bin/env python3
"""
study_divergence_veto_2026-08-19.py — divergence-conditioned harvesting,
measured. Growth study #1 admitted at (qa): the scout computes
`funding_divergence` (Lighter APR vs cross-venue) and NO harvest book reads
it. This buys the measurement before any book does.

QUESTION
  Do harvest-book entries taken while Lighter's funding rate is IDIOSYNCRATIC
  (far from the cross-venue rate for the same coin) underperform entries taken
  while the venues agree — and does an entry veto at |divergence| >= D improve
  the books' expectancy?

MEASURED PRIOR (the class this would screen, named at (qa)): 5 of the live
Farmer's 7 stops were LIT shorts (-$9.17) with LIT the standing market-wide
extreme; live snapshot ZK -51.7% on Lighter vs +10.9% cross-venue.

DATA — every source declared:
  * OUTCOMES: the books' OWN ledgers (I14 — the record decides), fetched from
    the public /trades.json. pnl_abs exactly as recorded. Books: the three
    rows of the lighter_funding_bot machine (Farmer LIVE, Farmer SHADOW,
    Garrett) pooled — that machine is where a veto would ship; carry reported
    INFORMATIONALLY only (different machine, and its pre-31-Jul rows carry the
    (nc) phantom accrual so pooling them would corrupt the total).
  * LIGHTER side: the venue's settled /api/v1/fundings via
    backtest_funding_lighter.fetch_fundings — the 17-Jul-verified basis, one
    owner, never re-implemented here.
  * BENCH side: HYPERLIQUID hourly funding ONLY. DECLARED DEVIATION from the
    scout's 3-venue median: binance and bybit are geo-blocked from this
    runner. Genuine divergences are triple-digit pp (the scout's own header),
    so a 1-venue bench is a usable proxy — but it is NOT the scout's number,
    and every table says "HL bench".
  * VENUE PURITY: cross-venue BY CONSTRUCTION — the signal IS the other
    venue's rate; the outcomes stay Lighter's own ledger. The declared
    exception pattern (CLAUDE.md, backtest-on-Lighter rule).

PRE-REGISTERED DECISION RULES — written before any result existed:
  R1 grid: D in {0.5, 1.0, 2.0} apr fraction (50/100/200pp TRUE).
     Veto = |lighter_apr(entry hr) - hl_apr(entry hr)| >= D.
  R2 ship bar (on the POOLED lighter_funding_bot set): vetoed subset total < 0
     AND mean < 0; kept subset beats unscreened on total AND mean in BOTH
     time halves (split at the pooled median opened_at); no single book's
     kept subset worse than its unscreened self by > $1.
  R3 floor: n_vetoed >= 10 pooled, else UNDECIDED (I16) — no ship either way.
  R4 plateau: two adjacent D cells must agree in improvement direction, else
     the winning cell is a lone spike and is refused (the (pw) E4 rule).
  R5 confound control: report |lighter apr| band x veto cross-table. If the
     veto's entire effect lives in the top |apr| band, it is "don't take
     extremes" wearing a divergence costume — CONFOUNDED, not shippable as a
     divergence rule (it would contradict the harvester's own thesis).
  R6 coverage receipt: mapped-crypto coverage per book printed; < 60% of a
     book's crypto closes mapped => that book's row is PARTIAL and says so.
  MECHANISM ROW: the LIT stop cluster from (qa) must itself show high |div|
     at entry, or the prior is withdrawn regardless of the pooled table.

An entry-time split has no look-ahead (the signal exists at the moment of
entry). NOT modelled, declared: slot substitution (a vetoed entry frees a
slot for the next candidate) — conservative for capacity-bound books.
"""

import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_funding_lighter import _get, fetch_fundings  # noqa: E402
from fleet_bus import is_crypto  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
HL = "https://api.hyperliquid.xyz/info"
CACHE_DIR = os.environ.get(
    "DIV_CACHE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".divstudy_cache"),
)

POOLED_BOOKS = [  # the lighter_funding_bot machine — where a veto would ship
    "perps-funding-lighter-lighter",
    "perps-funding-lighter-lshadow",
    "band-garrett-lshadow",
]
INFO_BOOKS = ["perps-funding-carry-lshadow"]  # reported, never pooled

D_GRID = [0.5, 1.0, 2.0]          # R1, apr fractions
APR_BANDS = [0.0, 0.5, 1.0, 2.0]  # R5 |lighter apr| band edges


def _jget(url):
    req = urllib.request.Request(url, headers={"User-Agent": "fleet-study"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _hl_post(payload):
    req = urllib.request.Request(
        HL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _cache(name, builder):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, name + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    v = builder()
    json.dump(v, open(p, "w"))
    return v


def fetch_ledger(bot):
    return _cache(f"ledger_{bot}", lambda: _jget(
        f"{DASH}/trades.json?source=paper&bot={bot}&limit=500"))


def hl_universe():
    meta = _cache("hl_meta", lambda: _hl_post({"type": "meta"}))
    return {u["name"] for u in meta.get("universe", [])}


def hl_funding_series(coin, start_s, end_s):
    """HL hourly funding, paged forward. -> {hour_ts: apr_fraction}."""
    def build():
        out, t = {}, int(start_s * 1000)
        end_ms = int(end_s * 1000)
        while t < end_ms:
            rows = _hl_post({"type": "fundingHistory", "coin": coin,
                             "startTime": t}) or []
            if not rows:
                break
            for r in rows:
                ts = int(r["time"]) // 1000
                out[ts - ts % 3600] = float(r["fundingRate"]) * 24 * 365
            newest = max(int(r["time"]) for r in rows)
            if newest <= t:
                break
            t = newest + 1
            if len(rows) < 400:  # short page = end of history
                break
        return {str(k): v for k, v in out.items()}
    raw = _cache(f"hl_{coin}_{int(start_s)//86400}", build)
    return {int(k): v for k, v in raw.items()}


def lighter_series(sym, mid, days):
    raw = _cache(f"lf_{sym}_{days}", lambda: {
        str(k): v for k, v in fetch_fundings(mid, days).items()})
    return {int(k): v for k, v in raw.items()}


def at_hour(series, ts, tol_h=2):
    """Value at the hour bucket <= ts, walking back up to tol_h hours."""
    h = ts - ts % 3600
    for k in range(tol_h + 1):
        if (h - k * 3600) in series:
            return series[h - k * 3600]
    return None


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def tstat(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    if var <= 0:
        return None
    return m / math.sqrt(var / n)


def main():
    hl_names = hl_universe()

    # ---- assemble rows -----------------------------------------------------
    ledgers = {}
    for b in POOLED_BOOKS + INFO_BOOKS:
        d = fetch_ledger(b)
        rows = d if isinstance(d, list) else d.get("trades") or []
        ledgers[b] = rows
        print(f"ledger {b}: {len(rows)} closes")

    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    mid_of = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}

    all_rows = []
    for b, rows in ledgers.items():
        for r in rows:
            coin = (r.get("pair") or "").split("/")[0].split(":")[0]
            t0 = parse_ts(r.get("opened_at"))
            if not coin or t0 is None or r.get("pnl_abs") is None:
                continue
            all_rows.append({
                "book": b, "coin": coin, "t0": t0,
                "pnl": float(r["pnl_abs"]),
                "side": r.get("side"), "reason": r.get("reason"),
            })

    t_min = min(r["t0"] for r in all_rows) - 7200
    t_max = max(r["t0"] for r in all_rows) + 3600
    days = int((time.time() - t_min) / 86400) + 2
    print(f"rows total {len(all_rows)}; window {days}d")

    # ---- coverage classification ------------------------------------------
    coins_needed = sorted({r["coin"] for r in all_rows})
    mapped, unmapped = {}, []
    for c in coins_needed:
        if not is_crypto(c):
            continue  # non-crypto: the already-screened class, out of scope
        if c in hl_names and c in mid_of:
            mapped[c] = mid_of[c]
        else:
            unmapped.append(c)
    print(f"crypto coins mapped on HL: {len(mapped)}; unmapped: {unmapped}")

    lf, hf = {}, {}
    for c, mid in mapped.items():
        try:
            lf[c] = lighter_series(c, mid, days)
        except Exception as e:
            print(f"  ! lighter series {c}: {e}")
        try:
            hf[c] = hl_funding_series(c, t_min, t_max)
        except Exception as e:
            print(f"  ! hl series {c}: {e}")

    # ---- per-row divergence ------------------------------------------------
    graded, dropped = [], {"noncrypto": 0, "unmapped": 0, "no_rate": 0}
    for r in all_rows:
        c = r["coin"]
        if not is_crypto(c):
            dropped["noncrypto"] += 1
            continue
        if c not in lf or c not in hf:
            dropped["unmapped"] += 1
            continue
        la = at_hour(lf[c], int(r["t0"]))
        ha = at_hour(hf[c], int(r["t0"]))
        if la is None or ha is None:
            dropped["no_rate"] += 1
            continue
        r["l_apr"], r["h_apr"], r["div"] = la, ha, la - ha
        graded.append(r)
    print(f"graded {len(graded)}; dropped {dropped}")

    for b in POOLED_BOOKS + INFO_BOOKS:
        n_all = sum(1 for r in all_rows if r["book"] == b and is_crypto(r["coin"]))
        n_g = sum(1 for r in graded if r["book"] == b)
        cov = (n_g / n_all * 100) if n_all else 0
        flag = "" if cov >= 60 else "  << PARTIAL (R6)"
        print(f"  coverage {b}: {n_g}/{n_all} crypto closes ({cov:.0f}%){flag}")

    pooled = [r for r in graded if r["book"] in POOLED_BOOKS]
    info = [r for r in graded if r["book"] in INFO_BOOKS]

    def stats(rows):
        if not rows:
            return "n=0"
        tot = sum(r["pnl"] for r in rows)
        n = len(rows)
        t = tstat([r["pnl"] for r in rows])
        w = sum(1 for r in rows if r["pnl"] > 0) / n * 100
        return (f"n={n:3d} total={tot:+8.2f} mean={tot/n:+7.3f} "
                f"t={t if t is None else round(t,2)} win={w:.0f}%")

    # ---- the tables --------------------------------------------------------
    print("\n=== DIVERGENCE BUCKETS (pooled lighter_funding_bot books; HL bench) ===")
    edges = [0.0, 0.25, 0.5, 1.0, 2.0, 99.0]
    for lo, hi in zip(edges, edges[1:]):
        rows = [r for r in pooled if lo <= abs(r["div"]) < hi]
        print(f"  |div| [{lo:4.2f},{hi:4.2f}): {stats(rows)}")

    med_t0 = sorted(r["t0"] for r in pooled)[len(pooled) // 2] if pooled else 0

    print("\n=== R1/R2 VETO GRID (pooled; kept = |div| < D) ===")
    verdicts = {}
    for D in D_GRID:
        kept = [r for r in pooled if abs(r["div"]) < D]
        veto = [r for r in pooled if abs(r["div"]) >= D]
        h1u = [r for r in pooled if r["t0"] <= med_t0]
        h2u = [r for r in pooled if r["t0"] > med_t0]
        h1k = [r for r in kept if r["t0"] <= med_t0]
        h2k = [r for r in kept if r["t0"] > med_t0]

        def tm(rows):
            return (sum(r["pnl"] for r in rows),
                    (sum(r["pnl"] for r in rows) / len(rows)) if rows else 0.0)
        ku_t, ku_m = tm(pooled)
        k_t, k_m = tm(kept)
        v_t, v_m = tm(veto)
        h1_ok = tm(h1k)[0] >= tm(h1u)[0] and (tm(h1k)[1] >= tm(h1u)[1])
        h2_ok = tm(h2k)[0] >= tm(h2u)[0] and (tm(h2k)[1] >= tm(h2u)[1])
        book_ok = True
        for b in POOLED_BOOKS:
            bu = [r for r in pooled if r["book"] == b]
            bk = [r for r in kept if r["book"] == b]
            if tm(bk)[0] < tm(bu)[0] - 1.0:
                book_ok = False
        floor_ok = len(veto) >= 10
        veto_neg = v_t < 0 and v_m < 0
        ship = veto_neg and h1_ok and h2_ok and book_ok and floor_ok
        verdicts[D] = ship
        print(f"  D={D}: unscreened {stats(pooled)}")
        print(f"        kept       {stats(kept)}")
        print(f"        vetoed     {stats(veto)}")
        print(f"        bars: veto_neg={veto_neg} h1_improve={h1_ok} "
              f"h2_improve={h2_ok} books_ok={book_ok} n_floor={floor_ok} "
              f"=> {'SHIP-CANDIDATE' if ship else 'refused'}"
              f"{'' if floor_ok else ' (UNDECIDED per R3)'}")

    print("\n=== R4 PLATEAU ===")
    ship_cells = [D for D in D_GRID if verdicts[D]]
    plateau = any(verdicts[a] and verdicts[b]
                  for a, b in zip(D_GRID, D_GRID[1:]))
    print(f"  ship-candidate cells: {ship_cells}; adjacent pair agrees: {plateau}")

    print("\n=== R5 CONFOUND: |lighter apr| band x veto (D=1.0) ===")
    for lo, hi in zip(APR_BANDS, APR_BANDS[1:] + [99.0]):
        band = [r for r in pooled if lo <= abs(r["l_apr"]) < hi]
        agree = [r for r in band if abs(r["div"]) < 1.0]
        idio = [r for r in band if abs(r["div"]) >= 1.0]
        print(f"  |apr| [{lo},{hi}): agree {stats(agree)}")
        print(f"                 idio  {stats(idio)}")

    print("\n=== MECHANISM ROW: the (qa) LIT stop cluster ===")
    lits = [r for r in graded if r["coin"] == "LIT" and "stop" in (r["reason"] or "")]
    for r in sorted(lits, key=lambda r: r["t0"]):
        d = datetime.fromtimestamp(r["t0"], tz=timezone.utc).strftime("%m-%d %H:%M")
        print(f"  {r['book'][:28]:28s} {d} side={r['side']} pnl={r['pnl']:+.2f} "
              f"l_apr={r['l_apr']:+.2f} hl_apr={r['h_apr']:+.2f} div={r['div']:+.2f}")
    if not lits:
        print("  (no graded LIT stop rows — prior NOT confirmable from mapped data)")

    print("\n=== INFO: carry (never pooled; pre-31-Jul rows carry (nc) phantom) ===")
    for lo, hi in zip(edges, edges[1:]):
        rows = [r for r in info if lo <= abs(r["div"]) < hi]
        if rows:
            print(f"  |div| [{lo:4.2f},{hi:4.2f}): {stats(rows)}")

    print("\nVERDICT INPUTS COMPLETE — apply R1-R6 by reading the tables above.")


if __name__ == "__main__":
    main()
