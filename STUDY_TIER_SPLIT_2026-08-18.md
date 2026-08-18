# The tier split, priced — both halves measured REFUSED (2026-08-18, (py))

**The ask (operator):** *"Let's see if it works, think if needs anything else"*
— on the 16-Aug tier-split proposal (🛢️ Garrett → apr [5%, 20%), 🏦 Rich Dad →
[20%, ∞) extended down to $0.1M). `(pl)` had refused it UNPRICED (*"cannot
argue the high-APR tail is load-bearing — and equally cannot argue it is
not"*), on the snapshot fact that all 6 of Garrett's top-ranked candidates
were ≥20%. This study supplies the missing price, on the (pw) band tape
(67 books, fresh 30d window 19-Jul → 18-Aug).

## Two instruments, one per half — the books keep different P&L

* **Garrett half**: the founding funding harness (price ladder), `entry_ok`
  predicates imposing/complementing the 20% ceiling; management never
  filtered (the harness's own contract). Cap 6, $30 clips, gate 0.05,
  tier friction median 5.12 / p90 14.77 bps.
* **Rich Dad half**: the cohort study's validated delta-neutral walk
  (`hull_run` shape) with Rich Dad's OWN constants — accrued − fees on the
  receiving side, persist 6h, liability_flip grace 6h, decay_paid (payback
  ×1.3 + decay bar 0.01875), max_hold 336h, bleed −2%, entry bar 0.219
  (the payback-velocity bar), crypto-only (39 of 67 band books), $80 × 6,
  RT 30bps.

Decision rules pre-registered in the driver header before results existed.

## Results

| Garrett cell | net$ | n | h2$ | p90$ |
|---|---|---|---|---|
| control [5%, ∞) — shipped | **+4.82** | 150 | −13.22 | −3.87 |
| band [5%, 20%) — the split's Garrett | **−15.71** | 163 | −15.57 | −25.15 |
| tail [20%, ∞) only — what the ceiling removes | −11.79 | 260 | −5.13 | −26.84 |

**CEILING-OK: False** — the ceiling costs Garrett **$20.53/30d**. And the
structural finding: the tail ALONE is also negative under Garrett's ladder,
so **neither sub-band carries the edge — the RANKING across the full band
does.** Narrowing a ranked selector degrades it from both ends (the founding
study's "slot interference", mirrored).

| Rich Dad walk on the thin tier's ≥21.9% crypto supply | value |
|---|---|
| net / n / t | +$20.25 / 35 / 0.91 |
| halves | −$0.38 / +$20.63 |
| exits | liability_flip 28 · decay_paid 5 · max_hold 2 |
| **top coin (KAITO)** | **+$21.65 = 107% of the total** |
| every other coin (19) summed | −$1.40 |

**EXTENSION-OK: passed as pre-registered** (net > 0, halves not-both-negative,
n ≥ 8) — **and is then killed by the house's standing concentration test**
([[undecidable-by-tail]] / the (nu)/(oj) discipline: run the top-drop test
before believing a mean): drop KAITO and the extension earns −$1.40 over 34
closes. One coin's episodes, not a cell edge. 28 of 35 exits are the churn
exit. Recorded plainly: the pre-registered rule was too weak — it lacked a
concentration arm, and the standing doctrine supplied it.

## Verdict

**SPLIT REFUSED, both halves now measured** — (pl)'s refusal upgraded from
unpriced to priced. The declaration in
`audit_book_overlap.KNOWN_CELL_COLLISIONS` carries the numbers so the split
cannot be re-proposed unpriced. What the KAITO fact means for supply: its
thin-band excursions sit BELOW carry's new $1M floor ((px)) and inside
Garrett's band, where Garrett's ranked selector already takes them — the coin
is covered; no book needs to move.

## Drivers (preserved verbatim)

```python
#!/usr/bin/env python3
"""THE TIER SPLIT, PRICED — the measurement (pl) said it could not make.

(pl) refused the 16-Aug split (🛢️ Garrett -> apr [5%,20%), 🏦 Rich Dad ->
[20%,inf) down to $0.1M) because the cost was UNPRICED: "cannot argue the
high-APR tail is load-bearing — and equally cannot argue it is not." The 30d
band tape now exists ((pw)); this prices both halves.

TWO INSTRUMENTS, one per half, because the two books keep different P&L:
  * Garrett half: the founding funding harness (price ladder, stop/tp/flip) —
    entry_ok predicates impose/complement the ceiling. Management is never
    filtered (the harness's own contract).
  * Rich Dad half: the cohort study's validated delta-neutral walk (hull_run
    shape) with Rich Dad's OWN constants — accrued - fees, receiving side,
    persist 6h, flip grace 6h, decay_paid (payback x1.3 + decay bar 0.01875),
    max_hold 336h, bleed -2%, entry bar 0.219 (payback velocity), crypto-only,
    $80 x 6.

PRE-REGISTERED RULES (before results):
  CEILING-OK  iff net(band<20%) >= net(control) - $1  AND  h2 >= control h2
              AND p90 >= control p90 - $1        (Garrett loses nothing real)
  EXTENSION-OK iff RichDad-walk on the thin tier's >=21.9% crypto supply:
              net > 0 AND halves not-both-negative AND n >= 8 over 30d
  SHIP the split iff BOTH. If EXTENSION-OK but ceiling refused: the supply is
  real but already Garrett's — I20 duplicate, refuse. If CEILING-OK but
  extension negative: the tail is toxic under both rule-sets — the ceiling
  alone becomes a Garrett-only candidate, reported separately, not shipped
  here (it changes trades and earns its own pass).
"""
import json, os, sys, math
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot")
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot/scripts")
import backtest_funding_lighter as bt
import fleet_bus

SP = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(SP, "garrett_band_tape.json")))
mk = {s: {"fund": {int(k): v for k, v in m["fund"].items()},
          "cand": {int(k): tuple(v) for k, v in m["cand"].items()}}
     for s, m in d["mk"].items()}
hours = sorted({t for m in mk.values() for t in m["fund"]})
t0, t1 = hours[0], hours[-1] + 3600
mid = t0 + (t1 - t0) // 2
MED, P90 = 5.12/1e4, 14.77/1e4
CEIL = 0.20

def gar(pred, slip):
    bt.ORDER_USD, bt.MAX_OPEN, bt.SLIP = 30.0, 6, slip
    full = bt.run(mk, 0.05, t0, t1, entry_ok=pred)
    h2 = bt.run(mk, 0.05, mid, t1, entry_ok=pred)
    return full, h2

def apr_at(sym, t):
    return mk[sym]["fund"].get(t)

below = lambda s, t: (apr_at(s, t) or 0) and abs(apr_at(s, t)) < CEIL
above = lambda s, t: (apr_at(s, t) or 0) and abs(apr_at(s, t)) >= CEIL

print("=== GARRETT HALF (founding harness, cap 6, $30, gate 0.05) ===")
rows = {}
for tag, pred in (("control (no ceiling)", None),
                  ("band <20% (split's Garrett)", below),
                  ("tail >=20% only (what the ceiling removes)", above)):
    f_med, h2_med = gar(pred, MED)
    f_p90, _ = gar(pred, P90)
    rows[tag] = dict(net=f_med["pnl"], n=f_med["n"], h2=h2_med["pnl"], p90=f_p90["pnl"],
                     why={k: round(v, 2) for k, v in f_med["why_pnl"].items()})
    print(f"  {tag:44s} net {f_med['pnl']:+8.2f}  n {f_med['n']:3d}  "
          f"h2 {h2_med['pnl']:+8.2f}  p90 {f_p90['pnl']:+8.2f}")
    print(f"    exits: {rows[tag]['why']}")

# ---- Rich Dad walk ---------------------------------------------------------
CLIP, CAP, RT, MARGIN, EXIT, HOLD, GRACE, PERSIST, BAR = 80.0, 6, 0.003, 1.3, 0.01875, 336, 6, 6, 0.219
crypto = {s for s in mk if fleet_bus.is_crypto(s)}
print(f"\n=== RICH DAD HALF (delta-neutral walk, crypto-only: {len(crypto)}/{len(mk)} band books) ===")

def rd_walk(bar):
    series = {s: mk[s]["fund"] for s in crypto}
    open_pos, closed = {}, []
    for t in hours:
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
            if p["pay"] > GRACE:
                why = "liability_flip"
            elif p["acc"] >= RT * CLIP * MARGIN and abs(apr) < EXIT:
                why = "decay_paid"
            elif p["held"] >= HOLD:
                why = "max_hold"
            elif p["acc"] < -0.02 * CLIP:
                why = "bleed"
            if why:
                closed.append(dict(pnl=p["acc"] - RT * CLIP, t=t, why=why, sym=sym))
                del open_pos[sym]
        if len(open_pos) < CAP:
            for sym in series:
                if sym in open_pos or len(open_pos) >= CAP:
                    continue
                w = [series[sym].get(t - 3600 * k) for k in range(PERSIST)]
                if any(x is None for x in w):
                    continue
                if len({1 if x > 0 else -1 for x in w}) != 1:
                    continue
                if not all(abs(x) >= bar for x in w):
                    continue
                open_pos[sym] = dict(side=-1 if w[0] > 0 else 1, acc=0.0, held=0, pay=0)
    return closed

def t_stat(x):
    n = len(x)
    if n < 2: return 0.0
    m = sum(x) / n
    v = sum((a - m) ** 2 for a in x) / (n - 1)
    return m / math.sqrt(v / n) if v > 0 else 0.0

cl = rd_walk(BAR)
if not cl:
    print("  ZERO closes — the >=21.9% thin-tier supply does not exist at 6h persistence")
else:
    pnls = [c["pnl"] for c in cl]
    cs = sorted(cl, key=lambda c: c["t"]); half = len(cs)//2
    h1, h2 = sum(c["pnl"] for c in cs[:half]), sum(c["pnl"] for c in cs[half:])
    days = (t1 - t0) / 86400
    from collections import Counter
    print(f"  n={len(cl)} net=${sum(pnls):+.2f} mean=${sum(pnls)/len(pnls):+.3f} "
          f"t={t_stat(pnls):.2f} h1=${h1:+.2f} h2=${h2:+.2f} closes/30d={len(cl)/days*30:.1f}")
    print(f"  exits: {dict(Counter(c['why'] for c in cl))}")
    print(f"  by coin: {dict(sorted(Counter({c['sym']: round(sum(x['pnl'] for x in cl if x['sym']==c['sym']),2) for c in cl}.items())))}" if False else "")
    bycoin = {}
    for c in cl: bycoin[c["sym"]] = bycoin.get(c["sym"], 0) + c["pnl"]
    print(f"  by coin: {[(s, round(v,2)) for s, v in sorted(bycoin.items(), key=lambda kv: kv[1])]}")

print("\n=== PRE-REGISTERED VERDICT ===")
a, b = rows["control (no ceiling)"], rows["band <20% (split's Garrett)"]
ceiling_ok = (b["net"] >= a["net"] - 1) and (b["h2"] >= a["h2"]) and (b["p90"] >= a["p90"] - 1)
print(f"CEILING-OK: {ceiling_ok}  (net {b['net']:+.2f} vs {a['net']:+.2f} | h2 {b['h2']:+.2f} vs {a['h2']:+.2f} | p90 {b['p90']:+.2f} vs {a['p90']:+.2f})")
if cl:
    ext_ok = sum(pnls) > 0 and not (h1 < 0 and h2 < 0) and len(cl) >= 8
    print(f"EXTENSION-OK: {ext_ok}  (net {sum(pnls):+.2f}, halves {h1:+.2f}/{h2:+.2f}, n {len(cl)})")
else:
    ext_ok = False
    print("EXTENSION-OK: False (zero closes)")
print("SHIP SPLIT:", ceiling_ok and ext_ok)
```
