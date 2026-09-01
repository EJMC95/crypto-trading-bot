# STUDY — THE EDGE, EXPLORED: what 👩 mum's measured edge is made of, and how it reaches the rest of the fleet

**Eamon's ask, 1-Sep:** *"explore the edge discovered also and how that edge can
benefit any of the bots."* Changelog **(vx)**; companion to the 1-Sep audit
((vw), `FLEET_AUDIT_2026-09-01.md`). Instruments: her own ledger (50 closes,
complete — supply started with the (vd) fixes on 28-Aug), her built-in control
arm ((hm) null, published on the row), the brain's own code driven with her
real rows ((hj)), the venue margin surface ((se)), and Eamon's two edge tools
from the weekend PRs (`edge_aware_safety.py`, `study_entry_exit_stoploss_fleet.py
--edge-report`), both run on the live feed.

## 1 · What the edge IS (and how much of it is tape)

| lens | number |
|---|---|
| Raw | n=50, **+0.643%/trade**, t=+2.41 (pct basis), +$76.89 on $300 |
| Control arm ((hm) matched-random null, on the row) | null **+0.337%** → **selection edge +0.289pp/trade** (n=47 paired) |
| Concentration | best trade 11% of total, top-3 28% — **not tail-driven** (the anti-(po) shape) |
| Breadth | 28 coins, 4 of 5 UTC days positive, biggest day +$40.55 |
| Exit structure | roi n=41 **+1.386%/t** (+$143.42) · stop n=5 −4.33% (−$57.84) · max_hold n=4 −0.76% |

**Roughly half her raw mean is the tape** (a random coin bought at her exact
instants earns +0.337%); the other half is her selection. The exit table is a
bracket doing its job: the decaying roi books the winners, the −4% stop pays
for itself in avoided tails. I25 discipline: 4.5 days of closes — grade her at
day-30 against the control arm, never against zero and never on this window's
warmth.

## 2 · The first benefit path is ALREADY WIRED, and it is warming: the brain

The stake-mult organ **sees her bucket and is one step of evidence from
sizing her up**:

* Its vitals (run 804) list `freqtrade-mum-lighter|long-oversold-rebound` on
  the watchlist with **`warming: "expand"`** — n=47, **t=+1.91 on the
  episode-deduped basis (n_ep=41)**, post_wr 0.795, w_lo 0.714.
* Driven with her raw ledger rows, `qualify_v3(expand=True)` returns
  **1.25×** (t=2.2 plain) — the gap to the published 1.91 is the brain
  grouping her 50 closes into **41 independent episodes** (clustered
  same-event closes deduped). That is the (kw) cluster discipline working
  FOR real money, not a defect: my first read overcounted clustered closes.
* **Knife-edge, quantified:** one more −4% stop at her clip → t 1.68 (no
  mult); two more typical roi wins → 1.25× holds; four → **1.5×** (t 2.69,
  post 0.808 > 0.60, w_lo 0.739 > 0.55). The ladder above (2.0× at t≥3.5)
  is open on the same bars. Latch = 3 consecutive qualifying runs (~1.5h at
  the brain's cadence) — **no action needed; the organ pays for evidence on
  its own**, and her rails ((sp): the Farmer-pattern trim, notional cap,
  gross budget) still dispose of whatever it proposes.
* Same table, the siblings queued behind her: 🙏 avo-shadow
  `long-dip-in-uptrend` t=+1.79 and 👩 mum-shadow t=+1.54 — both `warming:
  expand`. The family's long cells are collectively approaching brain-earned
  size, with no hand on any dial.
* **[I12 correction to (vw)/the audit report:** I wrote "the brain publishes
  zero non-1.0× opinions." Wrong — my scan misread the payload nesting. It
  publishes **three**, all reduces: 🧘 douglas short-impulse 0.75× (streak
  161), 🎫 taker short-divergence 0.75× (streak 180), and — fresh this
  morning, streak 3 — 🔮 **georgia-v3's long-impulse-fade probe cut to
  0.75×** on its early record (n=32, t=−1.19). The organ moves both ways.**]**

## 3 · Where the edge lives, by margin tier — and the sizing options card

Her (vd) $0.1M-floor universe is what feeds her, and it admits high-margin
coins — which is exactly why her stop-death ceiling collapsed to 4.17× (the
immune page). Joining her 50 closes against the venue's own margin surface:

| coin mmf tier | n | P&L | mean/t |
|---|---:|---:|---|
| ≤3% | 5 | +$5.29 (7%) | +0.36% |
| 3–6% | 27 | +$43.37 (56%) | +0.66% |
| 12% | 10 | **−$9.61 (−13%)** | −0.31% |
| 20% | 6 | +$24.89 (32%) | +1.86% — **all one coin, FOGO** |
| unknown (kBONK/kPEPE) | 2 | +$12.96 | +2.28% |

**63% of her P&L sits in ≤6%-mmf coins; the 12% tier is net negative; the
20% tier's entire contribution is one hot memecoin week** (I25: exactly the
cell not to chase). Venue-wide: 134 books ≤6% mmf, 80 above.

`edge_aware_safety` (Eamon's own tool, her real tape, its own caveat —
sizing sensitivity only): at worst-mmf 20% the stop-alive ceiling is
**4.17×**; **restrict the scan to mmf ≤6% and the ceiling becomes 10.0× —
the stop chain revives at the gross she runs** (alive with margin at 9.5×,
knife-edge at exactly 10). Her tape maxDD scales to $23.99 at 10× (6.5% of
book).

**The options card for Decision 3 (yours, Eamon — 10× was your call, and
n=50/4.5d is too thin to restructure a live scan on):**

| option | stop chain | cost, measured on week 1 |
|---|---|---|
| **A** keep 10×, universe as-is | dead above 4.17× basket-mmf | $0 — halt + liquidation are the rails (today's occupancy is small) |
| **B** 9.5× + scan capped mmf ≤6% | **fully alive** | forgoes the >6% tier: −$28.24 ≈ 37% of week-1 P&L, of which FOGO +$24.89 |
| **C** gross → 4.17×, universe as-is | fully alive | ~58% less deployed at full occupancy |
| **D** per-coin mmf-aware clip (a build) | alive per-coin | full supply kept; the proper fix — shadow-first prototype, a session job on your word |

Pre-registered for day-30 (so the tier split is graded on a real sample, not
this window): re-run the tier table on her full ledger at the window bar; if
the >6% tier's mean is still ≤0 ex-FOGO, option B/D stops costing anything.

## 4 · The fleet through the edge-report lens (Eamon's `--edge-report`, live feed)

The weekend tool's table, the rows that change decisions:

* 🎫 **taker: best edge family `long-breakoutup_hold` +$67.88** — which is
  precisely the lens `lighter_ticket_replay` refuses (`_up=False`), i.e. the
  HANDOFF carried item "taker-replay-blind-to-breakoutup" now has its value
  quantified: **the fleet's #3 edge family is invisible to the organ that
  tunes the taker's bars.** Raises that carried item's priority; the fix
  still owes its own before/after on the recorded tape.
* 🪁 **kelly: `short-snap_ghoststop` +$454.78 lifetime vs `short-snap_stop`
  −$460.52** — the mirror's whole life is ONE trade with two exits, and its
  net is the difference of two large numbers. For the ~18-Sep call: the
  question isn't "does the mirror work" but "can anything separate the
  ghoststop harvest from the stop bleed" — and (tm)-style exit sweeps on
  other books say exits are rarely the lever. Docket unchanged; framing
  sharpened.
* 🌾 carry `short_decay_paid` +$77.54 (the (gq) decay-paid edge, still the
  best funding exit); 💸 farmer-shadow and 🛢️ garrett both drag on
  `short_stop` — the funding-book stop question is a family pattern.
* 🔮 georgia-lighter's top drag is `long-range-on_daily_loss` −$46.28 — the
  halt rail, not the strategy, exactly as (vg) measured.
* 🙏 avo-lighter: `sell_into_strength` +$16.97 vs `daily_loss` −$22.12 —
  same shape.

## 5 · Transfer verdicts — what mum's edge does and does not license

* **To her own size: yes, automatically** — the brain ladder (§2). Nothing
  to hand-set; the streak latches on evidence.
* **To 🙏 avo's entry cell: no.** (qu) measured avo's entry as edgeless
  exit-free, with an operator-kept book and a pre-registered 50-close revert
  criterion — that criterion owns the call, and mum's cell is DISJOINT from
  avo's by construction (I20: NOT-uptrend vs uptrend-required). Duplicating
  mum's cell into avo would un-build that design.
* **To 🔮 georgia: already done, structurally.** v3 was built (vr) on the
  same lessons mum's v2 proved — short clock, bracket at entry, supply-first
  — and the brain already sizes its probe by its record. Her v3 ledger
  decides; not another tuning pass.
* **To new rows: no** (I20 — mum's supply is spoken for; a second oversold
  book would be one bet held twice).
* **To sizing doctrine: yes** — §3's card, and the general rule it
  demonstrates: **a widened universe moves the stop-death ceiling, so a
  gross setting and a universe floor are one decision, not two.** The
  leverage block + immune page already publish it; the margin-tier join is
  the missing third number and is now in this study.

## 6 · What did NOT survive this pass

* My own "brain publishes zero opinions" claim (§2 correction).
* The idea that the brain was blocked on her bucket — it is episode-honest
  and warming; the "defect" was my plain-bucket replay.
* Any same-day scan restructure on her live book — n=50/4.5d, FOGO-shaped
  hot cell, I25/I26 both point at day-30 with pre-registration instead.
