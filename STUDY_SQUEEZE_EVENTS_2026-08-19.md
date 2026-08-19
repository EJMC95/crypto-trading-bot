# STUDY — funding-extreme squeeze events (2026-08-19)

**Growth study #2 admitted at (qa)** (*"a squeeze-long is PAID to wait
(−50% apr ≈ 0.11%/day received); ~4–6 tradeable candidates at any moment"*).
Driver: `scripts/study_squeeze_events_2026-08-19.py` — rules S1–S7
pre-registered in the header before any result existed. Lighter-only data
(settled fundings + hourly candles via the backtest's own fetchers), 180d,
53 crypto books ≥ $100k current daily volume.

## Verdict: REFUTED — the price leg eats more than the funding pays, at every cell

717 / 313 / 109 fresh-extreme events at E = 50% / 100% / 200% TRUE apr.
Receiving-side entry at the event hour, held 24/48/72h, price + accrued −
friction ((pw) tier friction, median and p90):

* **Not one of the 18 E×H×friction cells clears any part of S4.** Best cell:
  E=2.0/H=24h/median at mean +0.096%, t=0.13, h2 negative, top-3
  concentration 492%.
* At the center of the grid the squeeze-long is significantly NEGATIVE:
  E=0.5/H=48h reads mean −0.783%, **t=−2.71, both halves negative** at p90
  friction.
* **The null is the sharper sentence**: random non-event receiving-side
  entries on the same coins BEAT the squeeze entries in most cells — P_null
  runs 0.36–0.99 (0.99 at the 48h center). A fresh funding extreme is
  *actively bad* entry information: it marks the moment the adverse price
  leg is largest, exactly what the Farmer's LIT stops experienced from the
  inside.
* Tier split (S6, labels declared drifting): the thin tier [0.1M,2M) carries
  the loss everywhere (−$495/−$190/−$102 per-%-clip totals across E cells);
  the lone positive sub-cell ([2M,10M) at E=0.5, n=13) is below every floor.

## What this buys

The fleet's standing refusals are re-validated from the other side: the
retired knife-catchers, the Farmer's structural stops, and (qa)'s "the price
leg the fleet only ever EATS" are all one phenomenon, now measured directly
over 1,139 events. No book should be built on squeeze entries at these
horizons, and no existing book needs a change — the fleet already refuses
this trade everywhere it appears. Per I19 and the (pu) precedent, the
refusal is the deliverable.
