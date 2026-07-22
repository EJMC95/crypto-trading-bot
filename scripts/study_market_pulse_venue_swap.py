#!/usr/bin/env python3
"""
study_market_pulse_venue_swap.py — did moving market_pulse off Binance change
a DECISION? (2026-07-17)

WHY THIS EXISTS
  audit_venue_purity.py caught market_pulse.py reading PRICE (Binance klines)
  and FUNDING (Binance premiumIndex) on a LIGHTER-FIRST fleet. Doctrine binds
  the fix: "NEVER change trading BEHAVIOUR in a venue-swap commit — a
  data-source swap must be behaviour-neutral or MEASURED." This is the
  measurement. It replays market_pulse's REAL rule against both venues over
  the same window, so the swap ships on evidence instead of on the plausible
  story that two BTC series must surely agree.

  It is deliberately a SCRIPT, not a paragraph: market_pulse.py's header cites
  "251/251, 100.0%", and a number in a docstring with no reproducible source is
  the exact unchecked-prose failure this repo keeps paying for. Re-run it.

-----------------------------------------------------------------------------
VERDICT — measured 2026-07-17. Reproducible: `python3 scripts/study_market_pulse_venue_swap.py`
(numbers drift as the window rolls; the CONCLUSIONS held across the runs below).

  REGIME (the decision that could actually flip)
    Replaying fetch_btc_regime's rule — 4h EMA50 > EMA200 over a 250-bar
    trailing window — at EVERY step across 500 aligned 4h bars
    (2026-04-25 -> 2026-07-17, timestamps intersected, not zipped):
      verdict AGREEMENT ........ 251/251 = 100.0%   ZERO flips
      lighter coverage ......... 500/500 of Binance's bars (no gap on BTC)
      close divergence ......... median 0.054%, max 0.094%  (perp vs spot)
    => NO BEHAVIOUR CHANGE. The swap is regime-neutral on this window.

  FUNDING (numerically different BY CONSTRUCTION — that is the point)
    At swap time, Lighter BTC/ETH/SOL ALL sat at the venue's RESTING DEFAULT
    9.6e-05 per 8h == 10.512% TRUE apr, while Binance showed real dispersion:
      BTC  binance +8.56% apr  |  lighter +10.51% apr
      ETH  binance +4.60% apr  |  lighter +10.51% apr
      SOL  binance +0.25% apr  |  lighter +10.51% apr
    fund_lean +0.0816 -> +0.1920  =>  mood +0.0166 on [-1,+1] (funding is 15%
    of mood). Mood is ADVISORY; `panic` (the one consumed field) is
    news-derived and untouched by this swap.

  THE NON-OBVIOUS FINDING — Lighter's BTC funding is ASYMMETRIC, and this is
  NOT a defect to tune around. Over the settled series (751 hourly rows,
  /api/v1/fundings, %/hr):
      at the resting magnitude .. 327/751 = 43.5% of hours (23 distinct
                                  values — it MOVES, it is not pinned)
      min -0.00450  median +0.00090  max +0.00120 %/hr
    The max IS the resting default: on BTC, Lighter's funding tops out at the
    resting rate on the long side and only disperses DOWNWARD. So fund_lean
    now has a ceiling near +0.19 but can still reach ~-0.7 — a euphoria signal
    is compressed, a fear signal is not. Re-denominating fund_lean to
    Lighter's own distribution may well be right; it is a SEPARATE,
    evidence-gated decision, and this commit deliberately does not take it.

LIMITATIONS (read before citing this)
  * ONE coin (BTC), ~83 days, ONE rule. It is evidence these two series agree
    on this rule in this window — not proof they always will. The broader
    claim it rhymes with is already on the record: regime_oracle's real
    classify() agrees on 99.4% of coin-days on Lighter vs HL candles
    (study_lighter_vs_hl_equivalence.py).
  * Live-API dependent: it measures TODAY's window, so it cannot reproduce the
    exact 2026-04-25 window forever. The agreement RATE is the durable claim.
  * A 100% agreement does not mean the series are identical — they are not
    (median 0.054% apart). It means the EMA50/EMA200 crossover, which is what
    the fleet reads, never landed inside that gap in this window. A rule with
    a tighter threshold could still flip where this one does not.
"""
import json
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])
import funding_basis  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-fleet-pulse; dry-run research)"}
LIGHTER = "https://mainnet.zklighter.elliot.ai"
BTC_MARKET_ID = 1
WINDOW = 250          # market_pulse's trailing bar count (REGIME_BARS)
PULL = 500            # Lighter's hard cap per candles call


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode()


def ema(vals, n):
    """market_pulse.fetch_btc_regime's EMA, verbatim — the point is to replay
    the REAL rule, not a reimplementation that might round differently."""
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def regime(closes):
    return ema(closes, 50) > ema(closes, 200)


def main():
    now = int(time.time())

    # --- pull both series, keyed by bar-open second -------------------------
    b = json.loads(_get("https://api.binance.com/api/v3/klines"
                        f"?symbol=BTCUSDT&interval=4h&limit={PULL}"))
    bmap = {int(c[0]) // 1000: float(c[4]) for c in b}
    l = json.loads(_get(f"{LIGHTER}/api/v1/candles?market_id={BTC_MARKET_ID}"
                        f"&resolution=4h&start_timestamp={now - PULL * 4 * 3600}"
                        f"&end_timestamp={now}&count_back={PULL}"))["c"]
    lmap = {int(c["t"]) // 1000: float(c["c"]) for c in l}

    # INTERSECT on timestamp — never zip. Two feeds of "500 bars" can cover
    # different windows, and zipping would silently compare misaligned bars
    # and then report a fabricated agreement rate.
    common = sorted(set(bmap) & set(lmap))
    print("=== BTC 4h REGIME: Binance klines vs Lighter candles ===")
    print(f"  binance bars {len(bmap)} | lighter bars {len(lmap)} | "
          f"COMMON {len(common)}")
    print(f"  lighter missing {len(set(bmap) - set(lmap))} of binance's bars "
          f"(coverage trap check)")
    if len(common) < WINDOW + 1:
        print(f"  INSUFFICIENT overlap ({len(common)} < {WINDOW + 1}) — no verdict.")
        return 1
    print(f"  window {time.strftime('%Y-%m-%d', time.gmtime(common[0]))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(common[-1]))} UTC")

    agree = flips = 0
    for i in range(WINDOW, len(common) + 1):
        ts = common[i - WINDOW:i]
        bv = regime([bmap[t] for t in ts])
        lv = regime([lmap[t] for t in ts])
        if bv == lv:
            agree += 1
        else:
            flips += 1
            print(f"    *** FLIP at "
                  f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(ts[-1]))}: "
                  f"binance={bv} lighter={lv}")
    n = agree + flips
    div = [abs(bmap[t] - lmap[t]) / bmap[t] * 100 for t in common]
    print(f"  AGREEMENT {agree}/{n} = {100 * agree / n:.1f}%  ({flips} flips)")
    print(f"  close divergence: median {statistics.median(div):.3f}%  "
          f"max {max(div):.3f}%")
    print(f"  >>> {'NO BEHAVIOUR CHANGE' if not flips else '*** REGIME FLIPS — STOP ***'}")

    # --- funding, side by side ---------------------------------------------
    print("\n=== FUNDING: Binance premiumIndex vs Lighter /funding-rates ===")
    lit = {x["symbol"]: float(x["rate"])
           for x in json.loads(_get(f"{LIGHTER}/api/v1/funding-rates"))["funding_rates"]
           if x["exchange"] == "lighter"}
    bl, ll = [], []
    for sym in ("BTC", "ETH", "SOL"):
        d = json.loads(_get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}USDT"))
        br = float(d.get("lastFundingRate") or 0.0)
        lr = lit.get(sym)
        bl.append(br)
        ll.append(lr)
        # BOTH venues quote per 8h -> funding_basis, never a bare 3*365.
        print(f"  {sym:4} binance rate_8h={br:+.8f} "
              f"apr={funding_basis.to_apr_pct(br, 'binance'):+7.2f}%  |  "
              f"lighter rate_8h={lr:+.8f} "
              f"apr={funding_basis.to_apr_pct(lr, 'lighter'):+7.2f}%")

    def lean(vals):     # market_pulse's fund_lean, verbatim
        return max(-1.0, min(1.0, (sum(vals) / len(vals)) / 0.0005))
    print(f"\n  fund_lean (15% of mood): binance={lean(bl):+.4f} "
          f"lighter={lean(ll):+.4f}")
    print(f"  mood delta from funding alone: {0.15 * (lean(ll) - lean(bl)):+.4f}")
    resting = all(abs(v - 9.6e-05) < 1e-9 for v in ll)
    print(f"  all majors at Lighter's RESTING DEFAULT (9.6e-05/8h = "
          f"{funding_basis.to_apr_pct(9.6e-05, 'lighter'):.3f}% true apr)? {resting}")

    # --- is Lighter's own funding pinned, or does it move? -----------------
    print("\n=== Lighter BTC settled funding (/api/v1/fundings, %/hr) ===")
    f = json.loads(_get(f"{LIGHTER}/api/v1/fundings?market_id={BTC_MARKET_ID}"
                        f"&resolution=1h&start_timestamp=0&end_timestamp={now}"
                        f"&count_back=0"))["fundings"]
    # NOTE: this endpoint's rate is PERCENT/HR and UNSIGNED with a separate
    # `direction` — the OPPOSITE convention to /funding-rates (signed fraction
    # per 8h). Crossing the two is an 8x-and-a-sign error. Re-sign explicitly.
    rates = [float(x["rate"]) * (1 if x.get("direction") == "long" else -1)
             for x in f]
    rest_mag = 9.6e-05 * 100 / 8.0          # per-8h fraction -> %/hr == 0.0012
    rest = sum(1 for r in rates if abs(abs(r) - rest_mag) < 1e-6)
    print(f"  rows {len(rates)} | distinct |rate| values "
          f"{len({abs(r) for r in rates})}")
    print(f"  at resting magnitude ({rest_mag:.4f} %/hr): {rest}/{len(rates)} "
          f"= {100 * rest / len(rates):.1f}%")
    print(f"  min {min(rates):+.5f}  median {statistics.median(rates):+.5f}  "
          f"max {max(rates):+.5f} %/hr")
    print(f"  >>> long side tops out at the resting default? "
          f"{abs(max(rates) - rest_mag) < 1e-6} "
          f"(=> fund_lean ceiling ~{lean([9.6e-05]):+.2f}, floor still ~"
          f"{lean([min(rates) / 100 * 8]):+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
