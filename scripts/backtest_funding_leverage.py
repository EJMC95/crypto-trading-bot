#!/usr/bin/env python3
"""Leverage x rails sweep for the LIVE Funding Farmer config, portfolio-level.

Mirrors lighter_funding_bot.py semantics via the same data/rules as
scripts/backtest_directional_funding.py (150d real HL hourly funding+price,
30 coins): enter funding-receiving side after 4 consecutive hot hours
(|apr|>=40%), intrabar 10% hard stop / 4% TP, flip/decay(<15%)/72h exits.

Portfolio: $61.13 collateral, $10 margin/clip, 4 slots, <=2 new/hour,
entries ranked by |apr| (scanner vetoes NOT modeled — live selection should
be slightly better). Leverage L: notional = 10*L per clip; funding AND price
P&L both scale with L. Daily rail (live): marked equity <= day_start*0.95 or
-$10 -> flatten at close+slip, halt to next UTC day. Liquidation when
intrabar adverse >= 1/L (only reachable for L>10, since the 10% stop fires
first below that) -> lose the full $10 margin.

Caveats: HL funding as Lighter proxy; hourly bars vs live 5-min loop; stop
fills assume no gap-through; isolated-margin liq approximation.

VERDICT (2026-07-11, live config $61.13 / $10 x 4 / gate 0.40):
  * LEVERAGE: REJECTED. Unrailed it scales (1x +3.0% -> 8x +23.7%/150d) but at
    54% maxDD and liq risk >10x; WITH the live 5%/$10 daily rail every L>=2 is
    self-defeating (3x -> -16.5%, 11-43 halts: the rail force-sells the lows).
    Scale with COLLATERAL, not leverage; leverage belongs on a hedged carry.
  * DEPLOYMENT: 5-6 slots at gate 0.40 is WORSE (+1.7/1.8% vs +3.0%) — the
    5th/6th hottest funder is adverse selection.
  * GATE 0.25 x 5 slots: +6.5% in-cache but FAILS the OOS half-split
    (-1.0% first 60d / +7.3% last 90d, and the win is price luck not funding)
    — regime-dependent mean reversion, NOT a robust optimisation. Live config
    (4 x 0.40) is the only setting positive in BOTH halves. Keep it.
  * REGIME GATES (same-day follow-up runs): market-heat>75pct and btc-vol>75pct
    entry blocks both FAIL both-halves. REJECTED.
  * FUNDING-SLOPE GATE: VALIDATED and SHIPPED (FUNDING_SLOPE_GATE, default on).
    Enter only while |apr| >= its level 1h ago: at the live 2x config baseline
    +1.3% -> +8.4% with lower maxDD (16.5%->12.5%), positive in BOTH halves
    (+6.9%/+2.6%); mirror rule (enter on rollover) symmetrically negative
    (-13.3%) = causal. 1h lookback chosen over the higher-scoring 3h (+24.6%)
    because the effect FLIPS SIGN at 4h — sweet-spot overfit risk; 1h is the
    robust setting. Stable under slot-count perturbation.
  * PREMIUM FACTORS (binance premiumIndexKlines, 150d): REJECTED — redundant.
    Sign-confirm on top of the slope gate is WORSE (+5.9% vs +8.4%) and both
    mirrors score positive (no causal separation). Mechanically expected:
    funding is computed FROM premium, so the funding-slope gate already
    encodes it. Do not re-test.
  * OI (binance openInterestHist, ~20d max free history): INCONCLUSIVE —
    16 baseline trades in-window; gate and mirror within noise. Verdict waits
    on the market-context collector's accumulating history (weeks).
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import backtest_directional_funding as bdf

COLLATERAL = 61.13
MARGIN = 10.0
SLOTS = 4
MAX_NEW = 2
ENTER, EXIT_, STOP, TP, MAXH = 0.40, 0.15, 0.10, 0.04, 72
PCT_RAIL, USD_RAIL = 0.05, 10.0
H = bdf.H
SLIP = bdf.SLIP


def sim(data, L, rails=True):
    hours_all = sorted({t for d in data.values() for t in d["k"] if t in d["f"]})
    hot = {c: 0 for c in data}
    pos = {}      # coin -> dict(is_short, ent, ent_i, accr)
    idx_of = {c: {t: i for i, t in enumerate(sorted(set(d["f"]) & set(d["k"])))}
              for c, d in data.items()}
    notional = MARGIN * L
    eq = COLLATERAL
    peak, maxdd = eq, 0.0
    n = wins = stops = liqs = halts = 0
    fund_sum = price_sum = 0.0
    day, day_start, halted = None, eq, False

    def mark():
        u = 0.0
        for c, p in pos.items():
            k = data[c]["k"].get(t)
            px = k[3] if k else p["ent"]
            pr = ((p["ent"] - px) / p["ent"]) if p["is_short"] else ((px - p["ent"]) / p["ent"])
            u += (pr + p["accr"]) * notional
        return eq + u

    def close(c, exit_px, reason, t):
        nonlocal eq, n, wins, stops, liqs, fund_sum, price_sum
        p = pos.pop(c)
        if reason == "liq":
            eq -= MARGIN
            liqs += 1; n += 1
            return
        fill = exit_px * (1 - SLIP * (-1 if p["is_short"] else 1))
        pr = ((p["ent"] - fill) / p["ent"]) if p["is_short"] else ((fill - p["ent"]) / p["ent"])
        pnl = (pr + p["accr"]) * notional
        eq += pnl
        n += 1
        wins += 1 if pnl > 0 else 0
        stops += 1 if reason == "stop" else 0
        price_sum += pr * notional
        fund_sum += p["accr"] * notional

    for t in hours_all:
        d_ = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
        if d_ != day:
            day, day_start, halted = d_, mark(), False

        # manage open positions (exit checks mirror replay())
        for c in list(pos):
            k = data[c]["k"].get(t); r = data[c]["f"].get(t)
            if k is None or r is None:
                continue
            o, hi, lo, cl = k
            p = pos[c]
            p["accr"] += (1.0 if p["is_short"] else -1.0) * r
            p["held_h"] += 1
            apr = r * H
            adverse = ((hi - p["ent"]) / p["ent"]) if p["is_short"] else ((p["ent"] - lo) / p["ent"])
            if adverse >= 1.0 / L and (1.0 / L) < STOP:
                close(c, None, "liq", t); continue
            reason = exit_px = None
            if p["is_short"]:
                if hi >= p["ent"] * (1 + STOP):   reason, exit_px = "stop", p["ent"] * (1 + STOP)
                elif lo <= p["ent"] * (1 - TP):   reason, exit_px = "tp", p["ent"] * (1 - TP)
            else:
                if lo <= p["ent"] * (1 - STOP):   reason, exit_px = "stop", p["ent"] * (1 - STOP)
                elif hi >= p["ent"] * (1 + TP):   reason, exit_px = "tp", p["ent"] * (1 + TP)
            if reason is None:
                if (p["is_short"] and apr < 0) or (not p["is_short"] and apr > 0):
                    reason, exit_px = "flip", cl
                elif abs(apr) < EXIT_:
                    reason, exit_px = "decay", cl
                elif p["held_h"] >= MAXH:
                    reason, exit_px = "max_hold", cl
            if reason:
                close(c, exit_px, reason, t)
                hot[c] = 0

        # entries: rank eligible by |apr| (scanner proxy), respect slots/halt
        cands = []
        for c, d in data.items():
            r = d["f"].get(t); k = d["k"].get(t)
            if r is None or k is None:
                continue
            apr = r * H
            if c in pos:
                continue
            hot[c] = hot[c] + 1 if abs(apr) >= ENTER else 0
            if abs(apr) >= ENTER and hot[c] >= bdf.PERSIST_H:
                cands.append((abs(apr), c, apr, k[3]))
        if not halted:
            cands.sort(reverse=True)
            new = 0
            for _a, c, apr, cl in cands:
                if len(pos) >= SLOTS or new >= MAX_NEW:
                    break
                is_short = apr > 0
                pos[c] = {"is_short": is_short,
                          "ent": cl * (1 + SLIP * (-1 if is_short else 1)),
                          "accr": 0.0, "held_h": 0}
                hot[c] = 0
                new += 1

        # rails on marked equity
        m = mark()
        if rails and not halted and day_start and (
                m <= day_start * (1 - PCT_RAIL) or day_start - m >= USD_RAIL):
            for c in list(pos):
                k = data[c]["k"].get(t)
                close(c, (k[3] if k else pos[c]["ent"]), "rail_flatten", t)
            halted = True
            halts += 1
            m = eq
        peak = max(peak, m)
        maxdd = max(maxdd, (peak - m) / peak if peak > 0 else 0)

    # mark remaining at end
    final = mark()
    ret = (final - COLLATERAL) / COLLATERAL * 100
    return (ret, maxdd * 100, (100 * wins / max(n, 1)), n, stops, liqs, halts,
            fund_sum, price_sum)


if __name__ == "__main__":
    data = bdf.load_data()
    print(f"coins: {len(data)} | collateral ${COLLATERAL}, ${MARGIN} margin x {SLOTS} slots, 150d")
    for rails in (True, False):
        print(f"\n{'lev':>4} {'ret%':>8} {'maxDD%':>8} {'win%':>6} {'trades':>7} "
              f"{'stops':>6} {'liq':>4} {'halts':>6} {'fund$':>8} {'price$':>8}  "
              f"({'RAILS ON (live)' if rails else 'no rails'})")
        for L in (1, 2, 3, 5, 8, 12):
            r = sim(data, L, rails)
            print(f"{L:>4} {r[0]:>8.1f} {r[1]:>8.1f} {r[2]:>6.0f} {r[3]:>7} "
                  f"{r[4]:>6} {r[5]:>4} {r[6]:>6} {r[7]:>8.2f} {r[8]:>8.2f}")
