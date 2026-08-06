# STUDY — Would exiting a carry at the FIRST adverse funding stamp beat the shipped flip-persistence window? (2026-08-06)

**The question.** Lighter settles funding hourly and the rate to be paid at the
next stamp is effectively visible before it settles — a forward-looking signal
**nothing in the fleet currently reads** (measured: zero hits for
next/predicted-funding across the tree). The carry books exit a position when
the rate flips sign against them and the flip **persists ≥ 1h**
(`funding_carry_bot.py` `FLIP_GRACE_H = 1.0`), which means the book always pays
at least one adverse settlement before leaving. Could foreknowledge — exit
*before* the first adverse stamp — improve carry expectancy, or is the
persistence window's insurance against spike-and-revert flips worth more than
the adverse accruals it eats?

## VERDICT UP FRONT — REFUSAL WITH EVIDENCE

**No. Exiting at the first adverse stamp, even with PERFECT foreknowledge, is
measurably worse than the shipped rule: −7.6 bps/episode (t=−5.3), negative in
BOTH halves, at BOTH modelled frictions, across 369 paired episodes on 180d of
Lighter's own settled-funding tape. `FLIP_GRACE_H` stays 1.0.** This is the
first time the persistence window's insurance value has been priced, and it is
~30:1 in the shipped rule's favour: holding through one adverse stamp costs a
**median 0.21 bps** of notional, while a wrong exit costs 15 bps round-trip
friction plus the episode's remaining accrual. The sided-flip losses on 🌾
carry's ledger (−$17.89 across 48 closes, confirmed live) are the cost of
flips that were REAL — leaving earlier would not have dodged them, it would
have added ~100 extra round trips on flips that weren't.

## Method

- **Shipped mechanism read from the module first**: `FLIP_GRACE_H=1.0`
  (adverse persisting ≥1h closes), decay-paid (|apr| < exit bar AND net ≥
  $0.10), 336h max-hold, −2% bleed stop; entry 20% TRUE apr persisting 6h,
  $2M floor, $300 notional (all confirmed at HEAD).
- **Tape**: `scripts/.lighterfund_cache.json` named in fleet docs does **not
  exist in the tree** (never committed), so an equivalent tape was rebuilt
  fresh via the same fetcher method: **180d × 25 books** (today's top-25 by
  liquidity — survivorship declared; heavier TradFi mix than the live book's
  floor-filtered universe), settled hourly signed TRUE apr, 4,315h union
  timeline.
- **Design**: identical entries across rules (|TRUE| ≥ 20% persisting 6h, one
  episode per hot streak). Rules: **A** = shipped (1h grace — exactly one
  adverse stamp paid per flip event; decay/max-hold/bleed kept); **B** = exit
  BEFORE the first adverse stamp settles (perfect foreknowledge, zero adverse
  paid); **B′** = exit after paying the first adverse stamp (grace-0, no
  foreknowledge); **C** = exit when the posted rate first crosses below the
  exit bar. 369 paired episodes; halves split by entry time; friction
  flat-conservative 15 bps RT (the Barnesy carry declaration) and 29 bps as
  the stress case.

## Results (paired, 15 bps RT)

| rule | n | mean bps/ep | total $ | win% | med hold | exit mix |
|---|---|---|---|---|---|---|
| **A shipped** | 369 | **+21.23** | **+$234.96** | 51% | 22.0h | flip 310 / decay_paid 40 / max_hold 18 |
| B first-stamp (foreknow) | 369 | +13.63 | +$150.87 | 41% | 14.0h | flip 345 / decay_paid 12 |
| B′ grace-0 | 369 | +12.64 | +$139.94 | 40% | 15.0h | |
| C bar-cross | 369 | +13.46 | +$148.97 | 41% | 13.0h | bar_cross 357 |

Paired deltas vs A: **B−A = −7.60 bps/ep (t=−5.32; halves −10.59/−5.45;
−$84.10 total)**; B′−A = −8.58 (t=−5.99); C−A = −7.77 (t=−5.44). All negative,
both halves. At 29 bps RT the early exits flip the whole book NEGATIVE
(B −0.23 bps mean) while A stays positive (+8.90). A sequential re-entry churn
model agrees: A +$153.38 vs B +$94.29 (B pays ~102 extra round trips); at
29 bps, A +$30.20 vs B −$72.76.

**Mechanics — why it is one-sided.** Of each episode's first adverse stamp,
**45% (167/369) revert within one stamp**. One adverse stamp at carry-relevant
rates costs median 0.21 bps (p90 2.88); rule A's TOTAL cost of holding through
all 363 survived spikes was ~$9.45 (~0.85 bps/episode). Rule B exits on a
spike A held through in 45% of episodes — and truncates exactly the
decay-paid closes that are the book's real earner (A reaches decay_paid 40
times, B 12). The value of foreknowledge in isolation (B vs B′) is real but
tiny: **+0.99 bps/episode (t=+8.6)** — ~15x smaller than the re-entry
friction it triggers. The only supported use of next-stamp visibility on this
evidence is closing an *already-decided* flip exit one stamp early — worth
~1 bp/flip, sub-friction, not worth a change.

## Honesty caveats

- Funding accrual only — no price leg modelled (matches the hedged book's own
  accounting; a real flip exit also crystallises hedge tracking error).
- The sim mirrors the bot's rules; it is NOT the bot's code. The standing
  calibration finding on this family (sims overstate shipped flip losses
  ~2.3x vs the real ledger) biases AGAINST rule A — **and A still wins**, so
  the bias direction reinforces the verdict.
- Rule B was modelled with PERFECT foreknowledge — the most favourable
  possible version of the proposal. The real quote-visibility edge is smaller.
- Entries held constant, capacity uncapped in the paired design; episodes
  overlap across coins so the paired-t SEs are understated. The verdict rests
  on the SIGN being uniform across both halves, both frictions and both
  designs, not on the exact t.
- Universe is today's top-25 applied historically (survivorship, the repo's
  own harness convention).

## Standing note

`FLIP_GRACE_H` is a bare constant — unregistered, not env-tunable (the I18
registered-but-unreachable shape). Deliberately left that way here: it was
just measured to sit at-or-below the optimum from BOTH directions (the (he)
longer-grace study and this zero-grace one), so there is no motion the rail
should be offered. If future evidence wants it moved, that is a code deploy
and a fresh measurement, and this doc is the baseline.

Applies equally to 🎸 Barnesy's carry sleeve, which re-expresses the same
flip discipline.

Scratch instruments (tape fetcher, paired sim, output) were session-scratch,
not committed; this doc carries the method and numbers needed to rebuild.
