#!/usr/bin/env python3
"""
scripts/study_funding_settlement.py — do crowded sides de-risk around the
HOURLY funding settlement, leaving a repeatable intra-hour flow? (12 Jul 2026,
the "what would a successful perp day trader actually harvest" programme.)

HYPOTHESIS: funding settles hourly and the upcoming rate is visible in
advance, so the PAYING side has an incentive to flatten just before the
stamp and re-enter after. If real, hot-funding coins should show a
systematic price drift into the settlement (direction = paying side
closing) and a reversal after — a time-boxed, named-payer flow. Cold-funding
hours are the control and must show ~nothing.

METHOD: Hyperliquid 5m candles (same hourly settlement mechanics as
Lighter, rates ~arbitraged — the house proxy), max depth ~17.5d (HL caps
candleSnapshot at ~5000 bars). 16 Lighter-listed coins: 11 recent
hot-funding leaders + BTC/ETH/SOL/HYPE/LINK as liquid controls. Every
settlement stamp T is labeled by the rate PAID AT T (fundingHistory), and
the 12 five-minute returns in [T-30m, T+30m] are averaged per relative
bucket within groups:
    hot-pos  apr >= +40%   (LONGS pay  -> expect down-drift into T)
    hot-neg  apr <= -40%   (SHORTS pay -> expect up-drift into T)
    warm     10% <= |apr| < 40%
    cold     |apr| < 10%   (control — must be flat)
Consistency checks: first vs second half of the window, and per-coin sign
agreement. A tradeable effect must clear ~10bps round-trip friction inside
a <=30min window; anything smaller is real-but-unharvestable.

VERDICT (12 Jul 2026, first 17.5d window, 480 stamps/coin, 16 coins):
  NOT CONFIRMED at harvestable size — do not trade this on current evidence.
  hot-neg (shorts paying, n=134): pre-stamp -2.6bps / post-stamp +5.8bps —
  the hypothesized direction, but inside 2se (8.8/9.8) and BELOW the ~10bps
  round-trip friction even at face value. hot-pos: n=34, pure noise (2se 27).
  Controls flat (validates the method). Halves flip sign (-5.2 vs +8.9) —
  fails any consistency bar. SECONDARY finding worth keeping: a universal
  +2-3bps drift in the FIRST 5min after every hour across ALL groups incl.
  cold controls — too small to trade, but any hourly-bar backtest inherits
  it (bar-alignment seasonality caution).
  The cache is CUMULATIVE (merge-on-rerun) — re-run weekly; at ~8 weeks the
  hot samples reach n~500-1000 and a 3-5bps effect becomes resolvable. If
  the hot-neg pre/post pattern then clears 2se AND friction, revisit; else
  close the thesis permanently.

Usage:  python3 scripts/study_funding_settlement.py
"""
import json
import os
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(__file__), ".settle_cache.json")
HL = "https://api.hyperliquid.xyz/info"
H_YR = 24 * 365

HOT = ["JTO", "SEI", "OP", "APT", "DOT", "WIF", "JUP", "ADA", "PYTH", "NEAR",
       "ENA"]
CTRL = ["BTC", "ETH", "SOL", "HYPE", "LINK"]
COINS = HOT + CTRL

GROUPS = (("hot-pos", lambda a: a >= 0.40),
          ("hot-neg", lambda a: a <= -0.40),
          ("warm", lambda a: 0.10 <= abs(a) < 0.40),
          ("cold", lambda a: abs(a) < 0.10))


def post(payload, tries=4):
    body = json.dumps(payload).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(
                HL, data=body, headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:  # noqa: BLE001
            time.sleep(1 + i)
    return None


def load(refresh=True):
    """CUMULATIVE cache: HL only serves ~17.5d of 5m candles, so each re-run
    fetches the current window and MERGES it into the cache — re-run weekly
    (or whenever) and the sample grows past the venue's depth cap."""
    out = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if not refresh and out:
        return out
    now = int(time.time() * 1000)
    for c in COINS:
        rows = post({"type": "candleSnapshot",
                     "req": {"coin": c, "interval": "5m",
                             "startTime": now - 20 * 86400000,
                             "endTime": now}}) or []
        f = post({"type": "fundingHistory", "coin": c,
                  "startTime": now - 20 * 86400000}) or []
        rec = out.setdefault(c, {"px": {}, "fund": {}})
        rec["px"].update({str(int(r["t"])): float(r["c"]) for r in rows})
        rec["fund"].update(
            {str((int(r["time"]) // 3600000) * 3600000): float(r["fundingRate"])
             for r in f})
        print(f"  {c}: {len(rec['px'])} 5m bars, {len(rec['fund'])} funding "
              f"stamps (cumulative)")
        time.sleep(0.2)
    json.dump(out, open(CACHE, "w"))
    return out


def main():
    data = load()
    B5 = 300000                       # 5 min in ms
    # rel buckets: -6..-1 = the 30min INTO the stamp, +1..+6 = 30min after
    rels = list(range(-6, 0)) + list(range(1, 7))

    # collect per (group, rel) return lists; sign-FLIP hot-neg so both hot
    # groups read as "paying-side pressure" in one direction
    def collect(coins, t_lo=None, t_hi=None):
        agg = {g: {r: [] for r in rels} for g, _ in GROUPS}
        n_ev = {g: 0 for g, _ in GROUPS}
        for c in coins:
            px = {int(k): v for k, v in data[c]["px"].items()}
            fund = {int(k): v for k, v in data[c]["fund"].items()}
            for T, rate in fund.items():
                if t_lo and T < t_lo or t_hi and T >= t_hi:
                    continue
                apr = rate * H_YR
                grp = next((g for g, fn in GROUPS if fn(apr)), None)
                if grp is None:
                    continue
                ok = True
                rets = {}
                for r in rels:
                    t1 = T + r * B5
                    t0 = t1 - B5
                    if t0 not in px or t1 not in px or px[t0] <= 0:
                        ok = False
                        break
                    rets[r] = (px[t1] / px[t0] - 1.0) * 1e4      # bps
                if not ok:
                    continue
                flip = -1.0 if grp == "hot-neg" else 1.0
                for r in rels:
                    agg[grp][r].append(flip * rets[r])
                n_ev[grp] += 1
        return agg, n_ev

    def mean_se(xs):
        n = len(xs)
        if n < 2:
            return 0.0, 0.0
        m = sum(xs) / n
        var = sum((x - m) ** 2 for x in xs) / (n - 1)
        return m, (var / n) ** 0.5

    agg, n_ev = collect(COINS)
    print("\nmean 5m return (bps) by bucket relative to settlement T")
    print("(hot-neg SIGN-FLIPPED so both hot rows read as paying-side "
          "pressure: negative pre-T = paying side selling into the stamp)")
    hdr = "group      n_ev |" + "".join(f" {r:+3d}" .rjust(7) for r in rels)
    print(hdr)
    print("-" * len(hdr))
    for g, _ in GROUPS:
        row = f"{g:10s} {n_ev[g]:5d} |"
        for r in rels:
            m, se = mean_se(agg[g][r])
            mark = "*" if abs(m) > 2 * se and se > 0 else " "
            row += f" {m:+5.1f}{mark}"
        print(row)

    # headline windows: last 15min into T and first 15min after T
    print("\nheadline (paying-side direction): mean cumulative bps, 2se")
    for g, _ in GROUPS:
        pre = [sum(x) for x in zip(*(agg[g][r] for r in (-3, -2, -1)))] \
            if agg[g][-1] else []
        post_ = [sum(x) for x in zip(*(agg[g][r] for r in (1, 2, 3)))] \
            if agg[g][1] else []
        mp, sp = mean_se(pre)
        ma, sa = mean_se(post_)
        print(f"  {g:10s} pre[-15m,T]: {mp:+6.2f} (2se {2*sp:.2f})   "
              f"post[T,+15m]: {ma:+6.2f} (2se {2*sa:.2f})")

    # halves consistency on the pooled hot groups
    ts = [int(t) for c in COINS for t in data[c]["fund"].keys()]
    mid = sorted(ts)[len(ts) // 2]
    for label, lo, hi in (("first half", None, mid), ("second half", mid, None)):
        a2, n2 = collect(COINS, lo, hi)
        hot_pre = [sum(x) for g in ("hot-pos", "hot-neg")
                   for x in zip(*(a2[g][r] for r in (-3, -2, -1)))
                   if a2[g][-1]]
        m, se = mean_se(hot_pre)
        print(f"  {label}: pooled-hot pre-stamp 15m {m:+6.2f} bps "
              f"(2se {2*se:.2f}, n {len(hot_pre)})")


if __name__ == "__main__":
    main()
