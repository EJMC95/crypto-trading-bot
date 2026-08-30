# PRE-REGISTRATION — the incubator fitness fix

**Written 2026-08-26 BEFORE the fix reaches a production cycle.**

> **REVISION 2, same day, before any result existed.** Revision 1 of this file
> pre-registered a prediction built on a mechanism that an adversarial referee
> then **REFUTED by driving it against the committed code**. The refutation and
> the corrected mechanism are recorded below in full, because a pre-registration
> that quietly swaps its hypothesis after seeing nothing is worthless — and one
> that keeps a refuted hypothesis is worse. No production cycle has run under
> the fix at the time of writing, so the registration is still genuinely prior.

---

## What was claimed in revision 1, and why it was wrong

**Claimed:** two *independent* exclusions of the `breakoutup` lens — no
`up_resolver` passed to `rp.replay`, AND no `breakoutup` key in the lens filter
— so the incubator scored the loser (`divergence`) and not the winner. Cited an
**$84.23 gap** and **0 of 1519** genotypes with `h1 > 0`.

**Refuted, by driving one winning crypto LONG breakout through the real
`rp.replay` + real `_marked` against `git show HEAD:strategy_incubator.py`:**

| coverage | bucket | fitness | closes |
|---|---|---|---|
| no `up_resolver` (what HEAD runs) | `{'breakout': 2.46}` | **+$2.46** | 1 |
| with `up_resolver` (what the tuner runs) | `{'breakoutup': 2.46}` | **$0.00** | 0 |

Without a resolver the relabel never fires, so those trades are scored as plain
`breakout` — **and `breakout` IS a `LENS_GENE` key.** The P&L was *included*.
The two "exclusions" are **mutually exclusive, not independent**: only one can
be in force, and the one in force was the harmless one. Passing the resolver
*alone* would have made the score strictly worse.

Three supporting pillars also failed:

1. **`BULL_MODE` is `False`** (verified: `tt.BULL_MODE = False`), so `_up`
   never reaches admission — a resolver changes the **label only**, not which
   tickets are admitted. Revision 1 asserted the opposite *from a docstring*
   rather than driving it. Driven at HEAD with no resolver: breakout taken 8,
   closed 3, net −$5.01. Not inert.
2. **The $84.23 gap is not like-for-like** — the tuner's `baseline_net` is
   **closed-only across five lenses**; the incubator's `net` is
   **mark-inclusive across four**. Metric basis, lens set and coverage all
   differ; one attribution was billed for three differences. The tuner's own
   docstring sizes the metric-basis term alone at **$41.57** on one tape.
3. **"0 of 1519" is a knife-edge, not a wall.** Same code, same source,
   varying only the tape end: drop 0 snaps → `h1>0` **0** of 1519; drop 3 snaps
   → **420**; drop 8 snaps → **0**. `mid = len(tape)//2` shifts by one snapshot
   and ~420 near-identical joint-space genotypes flip together. That is **n=1
   wearing n=1519**, and "lowering the bar to $0.00 buys nothing" is false at
   three of eight measured windows.

## What survives, verified independently

* `TRADE_SWING`/`HALF_MARGIN`/`EDGE_MARGIN` = **$3.50 / $3.50 / $7.00**, exact.
* `evaluate()` calls `rp.replay` **bare** at HEAD:661/663/664 while
  `lighter_scout_tuner.py:254` passes a resolver. The divergence is real.
* `LENS_GENE` has 4 keys vs `tt.ALL_LENSES` 5; `grep -c breakoutup` on HEAD = 1.
* `default_net` = −29.42 − 32.60 = **−$62.02**, arithmetically sound.
* Production: `elite: []`, champion tentative, streak 0, closes 82,
  h1 −23.96, h2 −10.08; tuner `baseline_net` +$22.21 with resolver true.
* **The CONCLUSION holds: the incubator's fitness is not the taker's book.**
  It is strengthened by something revision 1 never mentioned — **three enacted
  taker levers are live right now** (`taker.tp` 0.03 vs default 0.04,
  `taker.brk_range` 0.93 vs 0.95, `taker.momo_chg` 6.0 vs 5.0), so the
  incubator's "default genome" is not the running taker either, by a second
  and entirely separate route.

## The corrected mechanism — the honest route from coverage to P&L

The referee found what both earlier passes missed. In
`lighter_ticket_replay`, the per-snapshot dedup `if lens in opened_lenses:
continue` (~:315) runs **BEFORE** the relabel to `breakoutup` (~:345). So with
a resolver, two crypto breakouts in one snapshot both open (one `breakout`, one
`breakoutup`) where only one opened before — driven: `taken={'breakout':1}`
blind vs `taken={'breakoutup':2}` with a resolver, closed_net +$2.46 vs +$4.92.

**Coverage therefore changes WHICH TRADES the replayed book takes and how slots
are rationed against `divergence`, the losing lens.** That is a real mechanism
with a real sign, and **its magnitude on production's tape is UNMEASURED by
anyone.** Whether the dedup-before-relabel ordering is a replay *bug* or a
deliberate simplification is also unresolved and is tracked separately.

---

## Why the change ships anyway, and what bounds the risk

**The incubator places no trades.** It scores genotypes; its champion is
consumed by nothing (`genotype_to_levers` is never called outside a selftest).
So this change cannot move a single position — its entire blast radius today is
a dashboard chip and a bot_state payload. Shipping a *measurement* change into a
component with no actuator is the cheapest possible place to be wrong, and the
current measurement is definitely not the tuner's.

**The champion→lever door stays shut.** Wiring it in the same pass that changes
the fitness basis would auto-enact genotypes selected under a scoring rule we
have twice failed to characterise correctly. Order is unchanged: fix the
measurement, observe live cycles, then decide the door on evidence.

**No bar was moved** — not HALF_MARGIN, EDGE_MARGIN, MIN_CLOSES, MIN_GT_CLOSES,
MIN_TAPE_HOURS or PERSIST_CYCLES. Note this is now justified *differently* than
in revision 1: not "lowering them buys nothing" (refuted — it buys something at
three of eight windows), but because the half bar's behaviour is a **boundary
artifact** and moving a bar to chase an artifact is how a fleet fools itself.

---

## The predictions, restated

Graded on the first three production cycles after the fix is live
(`extra.build` stamp confirms the container took it), read from `/bus.json`
key `strategy_incubator`.

**P1 — the mechanism reaches the fitness (BINARY).** The published `funnel`
block exists and the scored lens set includes `breakoutup` when `breakout` is
unvetoed. If P1 fails the fix did not ship and nothing below is interpretable.

**P2 — coverage changes the TRADE SET, not merely the labels.** With the
resolver, `closes` for the default genome should **rise** (the dedup-before-
relabel path admits a second crypto breakout per snapshot).
*Falsified if `closes` is unchanged* — which would mean the double-open path
does not fire on production's tape and coverage is label-only, making the whole
change cosmetic. **That is a real possible outcome and must be reported as
such.**

**P3 — the half bar is a boundary artifact, not a wall.** `h1` for the default
genome should be **unstable across adjacent cycles** (the tape end moves every
cycle). Predicted: `h1 > 0` appears in some cycles and not others, with no
stable trend. **If `h1` is instead stably negative across all three cycles,
the boundary explanation is wrong and the surface is genuinely negative** —
in which case the incubator's taker lane is an I17 keep-or-retire question,
not a wiring one.

**P4 — the sweep's dead stretch binds regardless.** 107 of 152 cycles per orbit
produce zero enactable genotypes (in-cage subspace is 2.54% and contiguous under
the mixed-radix odometer), and production's cursor sits in a dead stretch now.
Gametes appearing only intermittently is explained by this, not by the fitness.

**NOT predicted, deliberately:** that any genotype becomes a gamete, or that
any book earns more money. Revision 1 implied a repair with a known direction.
The honest position after refutation is that **the fitness basis is being made
to match the tuner's, and the consequence is unknown** — including the
possibility that it is worth nothing.

---

## Standing scope of the claim

This fix makes the incubator measure the same book its sibling organ measures.
It does not make any bot win, and it must never be reported as if it does. What
the day actually produced that is load-bearing: a refuted mechanism caught
before it could be built on, and the discovery that `{closed: 0}` cannot
distinguish a stuck book from a slow one.
