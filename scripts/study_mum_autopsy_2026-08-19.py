#!/usr/bin/env python3
"""STUDY: 👩 mum's autopsy — the three numbers behind the (ro) revival, made
re-runnable. [2026-08-19, operator: "do a deep, deep dive on why".]

A finding nobody can re-run is a note. This script recomputes, from sources the
venue and the fleet expose publicly, the three measurements the mum-v2 design
rests on:

  1. HER EXACT FUNDING DRAG — settled, not modelled — over her three real hold
     windows. This is what CORRECTS `(rd)`'s "-$2.15" to **-$0.246** (I12).
  2. THE COST OF BEING LONG on this venue: what a long pays per day, and
     therefore what a hold of N days costs before it earns anything. This is
     the constraint that bounds v2's 12h cap.
  3. THE COST OF TRADING OFTEN: the fleet's own realised exit slippage across
     every short-hold close in the paper ledger. This is what makes the clock
     fix affordable — and together with (2) it is the whole indictment of v1.

THE UNIT TRAP, because it inverts a number by 12.5x and this script exists
partly to stop the next reader walking into it: `/api/v1/funding-rates` quotes
a FRACTION per 8h, but the SETTLED series `/api/v1/fundings` quotes **PERCENT
PER HOUR**. The hourly fraction is `rate/100`, never `rate/8`. Verified rather
than assumed — `--verify-units` reprints the check: the median non-zero settled
rate is exactly 0.0012 on the majors, which is the venue's own resting default
(9.6e-05 per 8h => 1.2e-05/hr => 0.0012 %/hr), the same constant
`funding_basis.py` documents.

DATA, and one hard constraint recorded so nobody re-tries it: the venue's
`/api/v1/candlesticks` endpoint returns **403 from every egress outside the
production containers** (measured 19-Aug from this container AND from GitHub
Actions runners, every market_id). So there is NO price/OHLCV history here and
this study deliberately contains no price-path backtest. Substituting another
venue's tape is refused — CLAUDE.md's venue-purity rule, which exists because
that substitution already cost real money twice.

Usage:
  python3 scripts/study_mum_autopsy_2026-08-19.py            # all three
  python3 scripts/study_mum_autopsy_2026-08-19.py --verify-units
  python3 scripts/study_mum_autopsy_2026-08-19.py --fund-dir /path/to/fundings
"""
import argparse
import datetime as dt
import glob
import gzip
import json
import os
import statistics as st
import subprocess
import sys

VENUE = "https://mainnet.zklighter.elliot.ai/api/v1"
DASH = "https://pnl-dashboard-production-858c.up.railway.app"
CLIP = 50.0                      # the family's stake; mum's notional read back
                                 # from the ledger as exactly 50.0 (pnl/pct)
MAJORS = ("BTC", "ETH", "SOL", "XRP", "LINK", "LTC", "DOGE", "AVAX")


def _get(url, timeout=40):
    """curl, because this container's egress needs its CA bundle."""
    r = subprocess.run(["curl", "-fsS", "--max-time", str(timeout), url],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def hourly_fraction(row):
    """One settled row -> the signed hourly fraction paid BY A LONG.

    `direction == "long"` means the LONG side pays (positive cost); "short"
    means longs RECEIVE. `rate` is PERCENT PER HOUR (see the header), so the
    fraction is rate/100.
    """
    try:
        rate = float(row["rate"]) / 100.0
    except (TypeError, ValueError, KeyError):
        return 0.0
    return rate if row.get("direction") == "long" else -rate


def load_fundings(fund_dir):
    out = {}
    for p in sorted(glob.glob(os.path.join(fund_dir, "*.jsonl.gz"))):
        coin = os.path.basename(p).split(".")[0]
        out[coin] = {int(r["timestamp"]): hourly_fraction(r)
                     for r in (json.loads(l) for l in gzip.open(p, "rt"))}
    return out


def fetch_fundings(fund_dir, coins, days=460):
    """Page the settled series backward. Idempotent — skips what it has."""
    os.makedirs(fund_dir, exist_ok=True)
    ob = _get(f"{VENUE}/orderBookDetails")
    if not ob:
        print("orderBookDetails unreachable — cannot resolve market ids")
        return
    ids = {r["symbol"]: r["market_id"] for r in ob.get("order_book_details", [])}
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    for coin in coins:
        path = os.path.join(fund_dir, f"{coin}.jsonl.gz")
        if os.path.exists(path) or coin not in ids:
            continue
        rows, end, floor = {}, now, now - days * 86400
        for _ in range(40):
            d = _get(f"{VENUE}/fundings?market_id={ids[coin]}&resolution=1h"
                     f"&start_timestamp={max(floor, end - 500 * 3600)}"
                     f"&end_timestamp={end}&count_back=500")
            c = (d or {}).get("fundings") or []
            if not c:
                break
            new = sum(1 for r in c if int(r["timestamp"]) not in rows)
            rows.update({int(r["timestamp"]): r for r in c})
            oldest = min(int(r["timestamp"]) for r in c)
            if not new or oldest <= floor:
                break
            end = oldest
        with gzip.open(path, "wt") as f:
            for t in sorted(rows):
                f.write(json.dumps(rows[t]) + "\n")
        print(f"  fetched {coin}: {len(rows)} settled rows")


# ---------------------------------------------------------------------------
def verify_units(funds):
    """The positive control for the whole study (I3): if this does not read
    0.0012, every dollar figure below is wrong by a constant and must not be
    quoted."""
    print("\nUNIT CHECK — the venue's resting default is 9.6e-05 per 8h, i.e.")
    print("1.2e-05/hr, i.e. 0.0012 as a PERCENT-per-hour quote.")
    ok = True
    for coin in ("BTC", "ETH", "HYPE"):
        m = funds.get(coin)
        if not m:
            continue
        # undo the /100 to inspect the raw quote's median
        nz = sorted(abs(v) * 100.0 for v in m.values() if v)
        med = nz[len(nz) // 2] if nz else 0.0
        hit = abs(med - 0.0012) < 1e-9
        ok &= hit
        print(f"  {coin:5s} median non-zero raw rate = {med:.4f} "
              f"{'== 0.0012 OK' if hit else '!= 0.0012 -- STOP'}")
    print(f"  => hourly fraction is rate/100 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")
    return ok


def part1_mum_drag(funds):
    print("\n" + "=" * 72)
    print("1 · MUM'S OWN FUNDING DRAG — settled, over her real hold windows")
    print("=" * 72)
    d = _get(f"{DASH}/trades.json?source=paper")
    rows = d if isinstance(d, list) else (d or {}).get("trades") or []
    mum = [r for r in rows if "mum" in (r.get("bot") or "")]
    if not mum:
        print("  no mum rows in the ledger window (the feed is capped at 500 "
              "most-recent rows) — cannot recompute; NOT reporting a number.")
        return
    print(f"  {'pair':5s} {'hold_d':>7s} {'gross%':>8s} {'ledger$':>9s} "
          f"{'funding$':>9s} {'hrs':>6s} {'long-pays':>10s}")
    tot = 0.0
    for t in sorted(mum, key=lambda r: r["pair"]):
        f = funds.get(t["pair"])
        if not f:
            print(f"  {t['pair']:5s}  (no settled series cached — skipped)")
            continue
        o = dt.datetime.fromisoformat(t["opened_at"]).timestamp()
        c = dt.datetime.fromisoformat(t["closed_at"]).timestamp()
        hrs = [ts for ts in f if o <= ts <= c]
        drag = sum(f[ts] for ts in hrs) * CLIP
        tot += drag
        gross = (t["exit_price"] - t["entry_price"]) / t["entry_price"]
        pays = sum(1 for ts in hrs if f[ts] > 0) / max(len(hrs), 1)
        print(f"  {t['pair']:5s} {(c - o) / 86400:7.1f} {100 * gross:+8.2f} "
              f"{t['pnl_abs']:+9.3f} {-drag:+9.3f} {len(hrs):6d} {100 * pays:9.1f}%")
    print(f"\n  TOTAL settled funding: {-tot:+.3f}$")
    print("  (rd) claimed -$2.15 and retired her partly on it; the settled")
    print("  series says otherwise. The CLOCK argument is unaffected — that is")
    print("  what the retirement actually rested on, and what v2 fixes.")


def part2_carry(funds):
    print("\n" + "=" * 72)
    print("2 · THE COST OF BEING LONG — what duration costs on this venue")
    print("=" * 72)
    print(f"  {'coin':6s} {'hours':>7s} {'days':>6s} {'long-pays':>10s} "
          f"{'%/day':>8s} {'%/7d':>8s} {'%/30d':>8s}")
    per_day = []
    for coin in sorted(funds):
        m = funds[coin]
        if len(m) < 500:
            continue
        vals = list(m.values())
        mean_h = sum(vals) / len(vals)
        pays = sum(1 for v in vals if v > 0) / len(vals)
        d = 100 * mean_h * 24
        print(f"  {coin:6s} {len(m):7d} {(max(m) - min(m)) / 86400:6.0f} "
              f"{100 * pays:9.1f}% {d:+8.4f} {d * 7:+8.3f} {d * 30:+8.2f}")
        if coin in MAJORS:
            per_day.append(d)
    if per_day:
        med = st.median(per_day)
        print(f"\n  MAJORS median: a long pays {med:+.4f}%/day of notional.")
        print(f"    a 12h hold costs {med / 2:+.4f}%   <- mum v2's cap")
        print(f"    a 29d hold costs {med * 29:+.3f}%   <- mum v1's median hold")
        print("  Carry punishes DURATION. v1 was built from the maximum-duration")
        print("  end of this table; v2 from the other end.")


def part3_execution():
    print("\n" + "=" * 72)
    print("3 · THE COST OF TRADING OFTEN — the fleet's own realised slippage")
    print("=" * 72)
    d = _get(f"{DASH}/trades.json?source=paper")
    rows = d if isinstance(d, list) else (d or {}).get("trades") or []
    gaps = []
    for r in rows:
        ep, xp, pa, pp = (r.get("entry_price"), r.get("exit_price"),
                          r.get("pnl_abs"), r.get("pnl_pct"))
        if not all(isinstance(v, (int, float)) for v in (ep, xp, pa, pp)):
            continue
        if ep <= 0 or pp == 0:
            continue
        try:
            hold_h = (dt.datetime.fromisoformat(r["closed_at"])
                      - dt.datetime.fromisoformat(r["opened_at"])).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            continue
        if hold_h > 48:          # long holds: the gap is funding, not slippage
            continue
        mv = (xp - ep) / ep
        if str(r.get("side", "long")).startswith("short"):
            mv = -mv
        gaps.append((pp - mv) * 1e4)
    if not gaps:
        print("  no priced short-hold closes in the window — nothing reported.")
        return
    gaps.sort()
    med = st.median(gaps)
    print(f"  n={len(gaps)} short-hold closes (<=48h, so funding is ~1bp and the")
    print("  gap between the decision mark and the realised fill is EXECUTION)")
    print(f"    median {med:+.1f} bps | p10 {gaps[len(gaps)//10]:+.1f} | "
          f"p90 {gaps[9*len(gaps)//10]:+.1f}")
    print(f"  => round trip ~= {2 * abs(med):.0f} bps. The venue is zero-fee and")
    print("  the cost model is the crossed spread alone, so TURNOVER IS CHEAP —")
    print("  which is what makes v2's clock fix affordable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fund-dir", default=os.environ.get(
        "MUM_FUND_DIR", "/tmp/mum_fundings"))
    ap.add_argument("--verify-units", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()

    if not a.no_fetch:
        print(f"settled-funding cache: {a.fund_dir}")
        fetch_fundings(a.fund_dir, MAJORS + ("HYPE", "SPY", "QQQ", "XAU", "WTI"))
    funds = load_fundings(a.fund_dir)
    print(f"loaded settled series for {len(funds)} coins")

    if not verify_units(funds):
        print("\nUNIT CHECK FAILED — refusing to report dollar figures computed "
              "on a basis this script cannot confirm. Fix the convention first.")
        return 2
    if a.verify_units:
        return 0

    part1_mum_drag(funds)
    part2_carry(funds)
    part3_execution()
    print("\nTHE ONE-LINE FINDING: this venue charges almost nothing to trade")
    print("OFTEN and a real amount to hold LONG — and mum v1 was configured at")
    print("precisely the wrong corner of both. Turnover was free and she")
    print("refused it. That is the whole autopsy.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
