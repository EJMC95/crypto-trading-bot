# STUDY — listing lifecycle retrospective (2026-08-19)

**Growth study #3 admitted at (qa)** (*"72 crypto birth events on the venue's
own `created_at` history vs 🎯 the sniper's n=1-per-listing problem"*).
Driver: `scripts/study_listing_lifecycle_2026-08-19.py` — rules L1–L4
pre-registered in the header. Population: books with `created_at` inside the
last 180d that still exist in today's `orderBookDetails` — **survivorship
bias declared up front**, with the pre-registered asymmetric read: a negative
long verdict is decisive, a positive one is only an upper bound.

## Verdict: NOTHING ESTABLISHED — n=12 with tail-dominated results

17 births visible, 12 priceable (entry at the first full hour's close, p90
tier friction):

| H | LONG mean | t | halves | top-3 share | P_null |
|---|---|---|---|---|---|
| 24h | +3.45% | 0.46 | +86.4 / **−45.0** | **223%** | 0.007 |
| 72h | +0.53% | 0.08 | +33.2 / −26.8 | 1424% | 0.26 |
| 168h | **−8.73%** | −1.44 | −14.1 / −90.6 | — | 0.99 |

The 24h long is the tempting cell — it beats the null — and it fails L4 on
three independent grounds: n=12 < 30, h2 negative, and top-3 concentration
223% (one coin's episode wearing a table — the (nu)/(oj) shape). By a week
the drift is decisively negative even WITH survivorship bias running the
optimistic way. Shorts mirror: 168h +8.1% at t=1.34, top-3 106%, n=12 —
reported, nowhere near a claim.

## Declared data caveats

* Survivorship: delisted births are invisible; per the pre-registration this
  can only have flattered the LONG rows, which still fail.
* Class pollution: with the scout dark in the study runner (no DATABASE_URL),
  `fleet_bus.is_crypto`'s deliberate fail-OPEN admitted several tokenised
  equities/ETFs (KIOXIA, WDC, SOXS, DIA, ROBO…) into the "crypto" births.
  This only strengthens the refusal — a clean crypto-only population is
  n≈5–7, further below every floor.

## What this buys

🎯 the sniper's listing source keeps its founding-thesis status honestly:
n=1 live, and the retrospective CANNOT establish an edge behind it at this
sample. No change to the sniper — the source is near-zero cost as built (one
qualifying loop per listing) — but any future proposal to EXPAND listing
exposure now has a measured table to clear first, and the ~12 events/180d
base rate says the sample will not arrive soon. All three (qa) growth leads
are now measured: all three died cheaply, which is the outcome (qa) priced
in — *"either mint the fleet's next measured edge … or die cheaply."*
