# 🛢️ Garrett cap + exit sweep — the never-empty tier's depth is NEGATIVE beyond 6 slots (2026-08-18, (pw))

**The ask (operator, 18-Aug):** *"Find a path or a way to make it win and a
growing PnL."* The obvious candidate was the one `(pu)` refused fail-closed the
same day on I7/`(hs)`: 🛢️ Garrett sits at 6/6 slots with ~23 eligible
candidates CAPPED every loop, in the one funding tier measured 100%-occupied
(median 31 qualified coins) while three books share a cell empty ~70% of the
time. This study upgrades that fail-closed refusal to a MEASURED refutation —
or would have shipped the widening had the tape supported it.

## Method

`scripts/backtest_funding_lighter.run()` — the persistence-parity-fixed replay
of the real funding rule (PERSIST_H 4, exit ratio 0.375, ladder
stop>tp>flip>cold>max_hold) — over the band's OWN universe (every book with
`daily_quote_token_volume` ∈ [$0.1M, $2M) on 18-Aug: 70 books, 67 with ≥20d
paired funding+candle history), FRESH 30d window 19-Jul → 18-Aug, at Garrett's
real config (gate 0.05 TRUE, $30 clips), tier friction from the (js) tx-hash
fill study (median 5.12 bps/fill, p90 14.77). Caveats inherited from the
founding study, stated: the harness fills free slots in volume order while the
real bot ranks by |apr|; band membership is TODAY'S volumes (point-in-time
membership is not reconstructable — the Hull (ny) caveat).

**Decision rules were PRE-REGISTERED in the drivers' headers before any result
existed** (R1–R5 for the cap; E1–E5 plateau-only for the exits — see below).

## Result 1 — the cap sweep: REFUSED, decisively

| cap | net$ | n | win% | $/trade | maxDD$ | h1$ | h2$ | p90$ |
|---|---|---|---|---|---|---|---|---|
| **6 (shipped)** | **+4.82** | 150 | 60.0 | +0.032 | −9.90 | +10.62 | −13.22 | −3.87 |
| 9 | −7.07 | 248 | 58.1 | −0.028 | −27.60 | +11.49 | −12.75 | −21.43 |
| 12 | −9.95 | 355 | 54.9 | −0.028 | −26.87 | −0.50 | −2.24 | −30.51 |

Slots 7–12 are NEGATIVE expectancy on the tier's own tape: the stop bucket
scales from −$26.67 → −$47.84 → −$65.95 while tp gains less. **cap 9 fails
R1/R2/R4; cap 12 fails R1/R2/R3/R4.** The ~23 "turned away" candidates are
trades the book is RIGHT to refuse — saturation is not evidence (I7), now
measured rather than presumed at this book.

## Result 2 — the exit ladder: no cell clears the plateau bar

16 cells, HARD_STOP {0.06,0.08,0.10,0.14} × TAKE_PROFIT {0.03,...,0.06}, same
tape. Best cell (+$14.80 at stop .06/tp .03) sits beside −$11.60 (E4 plateau
fail), and **h2 is negative in 15 of 16 cells**. REFUSED — the (hl) result
reproduced at this book: no exit tuning is available that is not window-fitting.

## Result 3 — the calibration row is the real finding: the band's edge has DECAYED

Cap 6 on the CURRENT window reads **+$4.82 with h2 −$13.22 and p90 −$3.87**,
against the founding study's **+$14.83, both halves positive, robust at p90**
(window ending 5-Aug). The last ~15 days of the tier are replay-NEGATIVE at the
shipped config — which makes Garrett's live record (−$4.70 over 19 closes,
stops −$3.78 the biggest bucket) **consistent with its own replay**, not a
broken book. Nothing to act on at n=19; what this buys is the correct
expectation for the ~12-Sep grade: **if band and book are still negative
together by then, the question is I17 keep-or-retire, never a widening.**

## Drivers (preserved verbatim)

### garrett_cap_study.py
```python
#!/usr/bin/env python3
"""GARRETT CAP SWEEP — is the fleet's only never-empty tier under-capped?

Context (operator, 18-Aug: "find a path or a way to make it win and a growing
PnL"): the 16-Aug per-cell occupancy measurement showed 🛢️ Garrett's thin tier
[$0.1M, $2M) is occupied 100.0% of snapshots with MEDIAN 31 qualified coins,
while the book is capped at 6 slots and its census reports ~23 eligible
candidates CAPPED every loop. Three other books share a cell that is empty
~70% of the time. Capacity is allocated backwards; this study prices moving it.

Method: scripts/backtest_funding_lighter.run() — the persistence-parity-fixed
replay of the real rule (PERSIST_H 4, exit ratio 0.375, ladder
stop>tp>flip>cold>max_hold) — over the band's OWN universe on a FRESH 30d
window ending now, at Garrett's real config (gate 0.05 TRUE, $30 clips), at
the tier's measured friction (median 5.12 bps/fill, p90 14.77 — the (js)
tx-hash fill study). Same harness, same caveat as the founding study: the
harness fills free slots in volume order while the real bot ranks by |apr|.
Band membership is TODAY'S volumes (point-in-time membership is not
reconstructable — the Hull (ny) caveat, inherited by the founding study too).

PRE-REGISTERED DECISION RULE (written before any result existed):
recommend FUNDING_MAX_OPEN 6 -> N (N in {9, 12}) IFF at median friction:
  R1  net$(N) > net$(6) + $2          — the widening must buy something real
  R2  per-trade mean$(N) >= 0.75 x per-trade mean$(6), and both > 0
                                       — capacity must not be bought with
                                         expectancy (I19); mild dilution from
                                         lower-ranked marginal coins allowed
  R3  halves at N not both negative
  R4  net$(N) still > 0 at p90 friction (14.77 bps)
  R5  maxDD(N) within 15% of the $1k book
Anything failing any rule is REFUSED with the table. Cap 6 at $30 is also the
calibration row: if IT reads wildly unlike the founding +$14.83@ $25 shape
(sign flip), the whole sweep is reported as regime change, not a cap verdict.
"""
import json, os, sys, time
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot")
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot/scripts")
import backtest_funding_lighter as bt

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SP, "garrett_band_tape.json")
DAYS = 30
LO, HI = 1e5, 2e6
GATE = 0.05
CLIP = 30.0
MED_SLIP, P90_SLIP = 5.12e-4 / 10, 14.77e-4 / 10  # placeholder, fixed below
# careful: 5.12 bps = 5.12e-4 as a fraction
MED_SLIP, P90_SLIP = 5.12 / 1e4, 14.77 / 1e4

def band_universe():
    obs = bt._get("/api/v1/orderBookDetails").get("order_book_details") or []
    rows = []
    for o in obs:
        try:
            v = float(o.get("daily_quote_token_volume") or 0)
        except Exception:
            v = 0.0
        if o.get("symbol") and LO <= v < HI:
            rows.append((o["symbol"], o["market_id"], v))
    rows.sort(key=lambda r: -r[2])
    return rows

def load_tape():
    if os.path.exists(CACHE):
        d = json.load(open(CACHE))
        if time.time() - d.get("built", 0) < 6 * 3600 and d.get("days") == DAYS:
            return {s: {"fund": {int(k): v for k, v in m["fund"].items()},
                        "cand": {int(k): tuple(v) for k, v in m["cand"].items()}}
                    for s, m in d["mk"].items()}
    rows = band_universe()
    print(f"band [{LO:.0f},{HI:.0f}) universe today: {len(rows)} books")
    mk = {}
    for sym, mid, vol in rows:
        try:
            fund = bt.fetch_fundings(mid, DAYS)
            cand = bt.fetch_candles(mid, DAYS)
        except Exception as e:
            print(f"  {sym}: fetch failed ({e}) — skipped"); continue
        common = set(fund) & set(cand)
        if len(common) < 24 * 20:
            print(f"  {sym}: only {len(common)}h paired — skipped"); continue
        mk[sym] = {"fund": fund, "cand": cand}
        print(f"  {sym:12s} {len(common):5d}h paired  vol ${vol/1e6:.2f}M", flush=True)
    json.dump({"built": time.time(), "days": DAYS,
               "mk": {s: {"fund": m["fund"], "cand": m["cand"]} for s, m in mk.items()}},
              open(CACHE, "w"))
    return mk

def sweep(mk):
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    t0, t1 = hours[0], hours[-1] + 3600
    mid = t0 + (t1 - t0) // 2
    bt.ORDER_USD = CLIP
    out = []
    for cap in (6, 9, 12):
        bt.MAX_OPEN = cap
        bt.SLIP = MED_SLIP
        full = bt.run(mk, GATE, t0, t1)
        h1 = bt.run(mk, GATE, t0, mid)
        h2 = bt.run(mk, GATE, mid, t1)
        bt.SLIP = P90_SLIP
        p90 = bt.run(mk, GATE, t0, t1)
        per = full["pnl"] / full["n"] if full["n"] else 0.0
        out.append(dict(cap=cap, net=full["pnl"], n=full["n"], win=full["win"],
                        per_trade=per, maxdd=full["maxdd"],
                        h1=h1["pnl"], h2=h2["pnl"], p90_net=p90["pnl"],
                        why_n=full["why_n"], why_pnl={k: round(v, 2) for k, v in full["why_pnl"].items()},
                        med_hold=full.get("med_hold")))
    return out, (t0, t1)

def main():
    mk = load_tape()
    print(f"\ntape: {len(mk)} band books")
    res, (t0, t1) = sweep(mk)
    print(f"window {time.strftime('%m-%d', time.gmtime(t0))} -> {time.strftime('%m-%d', time.gmtime(t1))} UTC | gate {GATE} TRUE | ${CLIP:.0f} clips | slip med {MED_SLIP*1e4:.2f} / p90 {P90_SLIP*1e4:.2f} bps\n")
    print(f"{'cap':>4} {'net$':>8} {'n':>5} {'win%':>6} {'$/trade':>8} {'maxDD$':>8} {'h1$':>8} {'h2$':>8} {'p90$':>8}")
    for r in res:
        print(f"{r['cap']:>4} {r['net']:>8.2f} {r['n']:>5} {r['win']:>6.1f} {r['per_trade']:>8.3f} {r['maxdd']:>8.2f} {r['h1']:>8.2f} {r['h2']:>8.2f} {r['p90_net']:>8.2f}")
    for r in res:
        print(f"  cap {r['cap']}: exits {r['why_n']}  pnl {r['why_pnl']}")
    base = res[0]
    print("\n--- pre-registered rule, applied ---")
    if base["net"] <= 0:
        print(f"CALIBRATION ROW NEGATIVE: cap 6 reads {base['net']:+.2f} on this window "
              f"(founding study read +$14.83 on 5-Aug window). Sweep is a REGIME statement, "
              f"not a cap verdict — refuse any widening; the question is the book, not the cap.")
    for r in res[1:]:
        ok = {
            "R1_buys": r["net"] > base["net"] + 2,
            "R2_expectancy": base["per_trade"] > 0 and r["per_trade"] > 0 and r["per_trade"] >= 0.75 * base["per_trade"],
            "R3_halves": not (r["h1"] < 0 and r["h2"] < 0),
            "R4_p90": r["p90_net"] > 0,
            "R5_dd": r["maxdd"] > -150.0,
        }
        verdict = "RECOMMEND" if all(ok.values()) else "REFUSE"
        print(f"cap {r['cap']}: {verdict}  {ok}")
    json.dump(res, open(os.path.join(SP, "garrett_cap_results.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
```
### garrett_exit_sweep.py
```python
#!/usr/bin/env python3
"""GARRETT EXIT-LADDER SWEEP on the cached band tape (cap 6, gate 0.05, $30).

PRE-REGISTERED BAR (written before results): a (stop, tp) cell is a candidate
ONLY if ALL of:
  E1  net > shipped(0.10, 0.04) + $5 at median friction
  E2  h2 >= shipped h2 (must not be bought by fitting the good half)
  E3  net > 0 at p90 friction
  E4  PLATEAU: all 4 orthogonal neighbours (stop+/-1 step, tp+/-1 step, where
      they exist) also beat shipped net — a lone spike is an artifact
  E5  n within [0.5x, 2x] of shipped n (an exit rule that halves or doubles
      turnover is a different book, not a tuning)
Expect refusal — (hl) killed 25/30 of this shape. The value is the map.
"""
import json, os, sys, time
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot")
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot/scripts")
import backtest_funding_lighter as bt
SP = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(SP, "garrett_band_tape.json")))
mk = {s: {"fund": {int(k): v for k, v in m["fund"].items()},
          "cand": {int(k): tuple(v) for k, v in m["cand"].items()}}
      for s, m in d["mk"].items()}
hours = sorted({t for m in mk.values() for t in m["fund"]})
t0, t1 = hours[0], hours[-1] + 3600
mid = t0 + (t1 - t0) // 2
bt.ORDER_USD, bt.MAX_OPEN = 30.0, 6
GATE, MED, P90 = 0.05, 5.12/1e4, 14.77/1e4
STOPS = [0.06, 0.08, 0.10, 0.14]
TPS   = [0.03, 0.04, 0.05, 0.06]
grid = {}
for st_ in STOPS:
    for tp_ in TPS:
        bt.HARD_STOP, bt.TAKE_PROFIT = st_, tp_
        bt.SLIP = MED
        full = bt.run(mk, GATE, t0, t1)
        h2 = bt.run(mk, GATE, mid, t1)
        bt.SLIP = P90
        p90 = bt.run(mk, GATE, t0, t1)
        grid[(st_, tp_)] = dict(net=full["pnl"], n=full["n"], h2=h2["pnl"], p90=p90["pnl"])
bt.HARD_STOP, bt.TAKE_PROFIT = 0.10, 0.04
ship = grid[(0.10, 0.04)]
print(f"shipped (stop .10 / tp .04): net {ship['net']:+.2f}  n {ship['n']}  h2 {ship['h2']:+.2f}  p90 {ship['p90']:+.2f}\n")
print("net$ @ median slip (rows=stop, cols=tp)")
print("        " + "".join(f"tp{t:>5.2f}" for t in TPS))
for st_ in STOPS:
    print(f"stop{st_:.2f} " + "".join(f"{grid[(st_,t)]['net']:>7.2f}" for t in TPS))
print("\nh2$")
for st_ in STOPS:
    print(f"stop{st_:.2f} " + "".join(f"{grid[(st_,t)]['h2']:>7.2f}" for t in TPS))
print("\np90$")
for st_ in STOPS:
    print(f"stop{st_:.2f} " + "".join(f"{grid[(st_,t)]['p90']:>7.2f}" for t in TPS))
print("\n--- pre-registered bar ---")
found = False
for (st_, tp_), g in grid.items():
    if (st_, tp_) == (0.10, 0.04): continue
    e1 = g["net"] > ship["net"] + 5
    e2 = g["h2"] >= ship["h2"]
    e3 = g["p90"] > 0
    e5 = 0.5 * ship["n"] <= g["n"] <= 2 * ship["n"]
    si, ti = STOPS.index(st_), TPS.index(tp_)
    nb = [(STOPS[si+d_], tp_) for d_ in (-1, 1) if 0 <= si+d_ < len(STOPS)] + \
         [(st_, TPS[ti+d_]) for d_ in (-1, 1) if 0 <= ti+d_ < len(TPS)]
    e4 = all(grid[k]["net"] > ship["net"] for k in nb)
    if e1 and e2 and e3 and e4 and e5:
        found = True
        print(f"CANDIDATE stop {st_} / tp {tp_}: {g}")
if not found:
    print("NO CELL clears the bar -> REFUSE (expected; the map is the value)")
```
