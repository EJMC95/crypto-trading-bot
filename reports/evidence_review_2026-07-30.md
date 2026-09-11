# Evidence Review — 2026-07-30

_Reviewed 2026-07-30T12:26:39+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow c94cb696f6f9 — the shadow arm is not a clean control while this holds

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 8154 events across 33 books (threshold 50) |
| disloc:0G | active | census 406 ev / 277bps (alert 406), last event 1.3h ago, 13 entries |
| disloc:APEX | active | census 3834 ev / 313bps (alert 3834), last event 7.6h ago, 383 entries |
| disloc:BIO | active | census 86 ev / 272bps (alert 86), last event 16.4h ago, 1 entries |
| disloc:CHIP | active | census 174 ev / 160bps (alert 174), last event 1.9h ago, 3 entries |
| disloc:EIGEN | active | census 178 ev / 161bps (alert 178), last event 16.0h ago, 1 entries |
| disloc:GMX | active | census 143 ev / 151bps (alert 143), last event 10.4h ago, 3 entries |
| disloc:KAITO | active | census 990 ev / 350bps (alert 982), last event 0.1h ago, 60 entries |
| disloc:NEAR | active | census 20 ev / 150bps (alert 20), last event 18.4h ago, 0 entries |
| disloc:RESOLV | active | census 444 ev / 188bps (alert 444), last event 2.2h ago, 2 entries |
| disloc:SKHYNIXUSD | active | census 418 ev / 275bps (alert 408), last event 0.0h ago, 353 entries |
| disloc:SKY | active | census 91 ev / 315bps (alert 91), last event 15.2h ago, 2 entries |
| disloc:SNDK | active | census 109 ev / 162bps (alert 107), last event 0.0h ago, 58 entries |
| disloc:STABLE | active | census 306 ev / 396bps (alert 306), last event 1.6h ago, 6 entries |
| disloc:STBL | active | census 196 ev / 245bps (alert 196), last event 1.0h ago, 6 entries |
| disloc:ZORA | active | census 223 ev / 202bps (alert 223), last event 16.4h ago, 3 entries |
| factor-sample:4 | resolved | joined decision+context dataset at 213 closes (54% win), bucket 7 |
| factor-sample:6 | resolved | joined decision+context dataset at 213 closes (54% win), bucket 7 |
| veto:CXMT,SKHY | resolved | CXMT,SKHY no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=84 (≥10): net $+8.85, WR 33%, t=0.8 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=62, net $+7.94 — by lens [('short', 58, 7.43), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=26, net $-0.49 — by lens [('short-divergence', 14, 1.41), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- ⏳ waiting only on the window bar: perps-funding-carry-lshadow (t=2.6, n=82, 18.3d, 5/6 bars — only 'window' outstanding, ~11.7d away) ⛔ POOLED LEDGER: 7 same-pair overlap(s), deepest 9.14h on HYPE — a second writer; this grade is not one book's record
- ⚠️ maxdd caveat ((hl)): the bar above is REALISED-only; MTM drawdown can be materially larger and can flip the verdict. Re-grade any candidate under MTM once bot_state_history '<bot>:equity' has ~30d.
- 🚦 fleet-risk light yellow — 18 gross vs long budget 20; 7d DD -0.19%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.133pp (live +0.601% n=46, shadow +0.469% n=55) — no divergence
- 🧬 Farmer arms AGREE: live 705425a83422 vs shadow 705425a83422
- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow c94cb696f6f9 — the shadow arm is not a clean control while this holds

## Summary

19 alert keys reviewed: 16 active, 3 resolved, 0 stale. No divergence and no drawdown-governor trigger. 13 new-evidence items scanned.

---

# 30-Jul review — the three jobs

_Rewritten to the operator's 30-Jul mandate: **growth, not staleness and
circles.** (1) assess the work done since the last review, (2) fleet state,
(3) options to optimise. Machine pass 06:34Z + 12:25Z; judgement layer 22:4x
AEST Thu 30 Jul._

## 1. Assessing the work done since the last review — what was missed

Twenty commits landed since the 28-Jul report (`ey`–`hl`). Graded against
current data, three claims had already moved or were left half-true:

| Claim as shipped | Current measurement | Verdict |
|---|---|---|
| `(fk)` re-specified the go-live gate | the **daily review still held the OLD rule** and published a false pass + a false rejection next morning | **MISSED — fixed today** |
| `(gh)`: "🌾 carry … **8 open of 8 FULL**, cannot take another trade" | **9 open of 12** — the growth system already raised `max_positions` | **STALE — solved before it was read** |
| 🌾 carry is the fleet's best-evidenced book (n=82, t=2.60) | true, **but its ledger has 7 same-pair overlaps, deepest 9.14h on HYPE** — a second writer | **MISSED — the grade sits on a pooled ledger** |

The first is the serious one and it is now structurally prevented, not just
patched: `evidence_review` **imports** the gate (`stats`/`grade`/`bar_map`/
`BAR_NAMES`) instead of restating it, and `tests/test_review_currency.py`
(12 tests) fails if it ever stops. Mutation-verified in both directions — a
7th bar injected upstream propagates with **zero edits**, and re-hardcoding the
bar list turns a test red the day it is written, not the day upstream moves.

**The second is the lesson for this schedule**: I quoted a baseline document
instead of the live `extra.caps`, and would have reported a solved problem as
urgent. The schedule now forbids it.

## 2. Fleet state

* **🚦 Go-live: NO new candidate.** 🌾 carry is 5/6 bars, **only `window`
  outstanding, ~11.7d away** (≈10–11 Aug) — now published with its pooled-ledger
  flag inline, so nobody reads that ETA as a clean promotion path.
* **💰 Real money:** Farmer n=62 **+$7.94**; live Taker n=26 **−$0.49** and
  effectively idle. Farmer live-vs-shadow gap **+0.133pp in live's favour** — no
  divergence, execution is not leaking.
* **🚦 fleet-risk yellow** — veto counter **17/20 longs (3 free)**, 7d DD
  −0.19%, `clip_scale 1.0`. Nowhere near the −5% governor.
* **🧬 Taker arms DRIFT** (live `0b30b0a79211` vs shadow `c94cb696f6f9`) —
  transient churn from today's `[deploy-live-taker]` pushes; it converged once
  already today. Build **counts** match, so the `(fd)` file-set caveat is ruled
  out, not assumed.
* **Capacity census** (open vs cap): Counterweight **20/20 FULL**, carry 9/12,
  Tide Rider 4/6, Index Rider 3/9, Sniper 1/4, Snap Back 0.
* 19 alert keys: 16 active, 3 resolved, 0 stale. `long-dip` (t=−2.74) is
  **frozen, not accruing** — last close 26-Jul, switched off by `(fn)`'s veto.

## 3. OPTIONS TO OPTIMISE — ranked

**On "open faster, exit faster":** `(hl)` swept exactly this today with 38
agents — **25 of 30 throughput candidates killed, and the 5 survivors produce
zero extra round trips.** Every faster exit on 🌊 improved per-trade 5.1× but
per **bar-day held** only 1.04×; a content-free 3-day stop reproduced 78% of it
and an exposure-matched null *beat* it. So the honest answer is that **turnover
is not on offer** — and the wins below are capacity, correctness and reach,
which cost no expectancy.

1. **⛔ Stop 🌾 carry's duplicate writer — highest value, and it is real money
   adjacent.** 7 same-pair overlaps prove two processes write one book. This
   corrupts the evidence of the book closest to go-live, and inflates its true
   exposure. **Operator action** (Railway service change is outside this task's
   safety scope): find and stop the duplicate `funding-carry` service, then
   re-grade. Until then no promotion may rest on n=82/t=2.60.
2. **Correctness — the maxdd bar cannot see most of the drawdown it grades.**
   `(hl)` measured realised 9.9–10.7% vs true MTM 15.6–17.4% on 📊: the two
   definitions **disagree about the verdict**. `snapshot_equity()` started the
   MTM series today; the review now states this caveat on every run that names a
   candidate. **Re-grade carry under MTM at ~30d of history, before its window
   closes.** Cost: none — better decisions only.
3. **Correctness — two fleet counters disagree.** The veto reads
   `long_positions=17`, the exposure view reads `long_n=20`, `gross=18`; all
   three from the same payload. The veto is the one with authority (`fleet_bus`
   :150), so the fleet has 3 long slots, not 0 — but an enforcement authority
   that reports three different position counts will eventually gate on the
   wrong one. Cheap to reconcile; I did **not** change `fleet_risk.py` from a
   cron run.
4. **Do NOT buy reach by raising ⚖️ Counterweight's cap**, even though it is the
   only cap-bound book (20/20). Its t is **0.65** on n=45 for **+$1.09** — cap
   space there adds exposure with no measured edge, and it is consuming the
   fleet's scarcest resource (long budget) that carry (t=2.60) competes for. The
   defensible move is the reverse: **reallocate budget toward the edge-bearing
   book**, not widen the one without an edge.
5. **Undecidable books are the real dead weight**: 📊 Index Rider and 🌊 Tide
   Rider hold 7 slots between them and have **zero closed trades**. They cannot
   be graded, so they cannot earn or lose their keep. `(hl)` already cut 📊's
   clip to $65 for the drawdown bar. Standing retirement candidates.

**What I implemented immediately** (per the same-run rule): the gate import, the
anti-drift test suite, the pooled-ledger flag now inline in the gate section, the
realised-vs-MTM caveat, and the schedule's own mandate. **Suite 675 passed.**
What I did NOT touch: any lever, clip, `dry_run`, key, Railway service, or
`fleet_risk.py` — items 1 and 3 are yours.

---

## 🌱 THE VETO IS A STAGNATION MODEL — operator directive, 30-Jul

> *"The veto needs to be restructured towards a growth model, not a keep-things-stagnant model."*

**Measured, and the code agrees with the complaint.** `fleet_risk.py:165`:

```
LONG_BUDGET = 20        # bare literal
SHORT_BUDGET = 12       # bare literal
```

Three findings, all verifiable:

1. **It is the only bound in its own file that is not configurable.** Every
   other one — `MODE`, `DD_HALF`, `DD_QUARTER`, `DD_MIN_SPAN_SEC`,
   `FLEET_SYMBOL_CAP` — reads `os.environ.get(...)`. These two are literals, so
   there is no env default, **no registry entry, and the growth rail cannot
   move them at all.** Every other bound in the fleet can be widened on
   evidence with a TTL; this one cannot be widened by anything short of a
   redeploy.
2. **It is first-come-first-served, which is the stagnation.** `fleet_bus:150`
   is `long_positions >= long_budget` — a flat count. At budget it refuses *the
   next* long, not *the worst* one. Today ⚖️ Counterweight (**t=0.65**, +$1.09,
   20/20 legs) holds budget that 🌾 carry (**t=2.60**, +$61.12) competes for.
   **The cap protects the incumbent's weakest position against the fleet's
   best-evidenced candidate** — precisely backwards for a growth model.
3. **Its own comment says v1 was provisional and the refinement never came:**
   *"count-based v1 — inverse-vol weighting is a later refinement once this has
   advisory history to calibrate against."* It has had advisory history since
   15-Jul. The refinement is overdue, not speculative.

### The restructure, in doctrine order

* **Step 1 (small, inert on ship, unblocks everything else):** make both budgets
  `os.environ.get`-defaulted at their current values and **register them as
  bounded levers** (`risk.long_budget`, `risk.short_budget`) with an
  `env_default`, so the growth rail can EXPAND them on measured evidence and
  auto-revert on TTL — the same pattern as every other bound. Default unchanged
  ⇒ **zero behaviour change the day it ships**, which is what makes it safe.
* **Step 2 (the actual growth model):** admission by EDGE, not arrival order —
  when at budget, a candidate from a book whose measured t exceeds the weakest
  current holder's should win the slot. Needs a displacement policy, and
  displacement closes a position, so it needs replay evidence before it governs
  anything.
* **Step 3:** the intended inverse-vol / effective-bet weighting, calibrated
  against the advisory history the comment was waiting for (`long_effective_n`
  is already published — 14.3 effective bets from 20 positions today, so the
  count-based cap is already overstating diversification by ~30%).

### Why I did not ship it tonight, plainly

This is the fleet's **enforcement authority**, and the change is a behaviour
change to how every shadow book gets admitted. Doctrine is explicit — *never
modify bot logic without backtesting first* — and a budget re-allocation changes
which trades six books take, so it needs replay evidence, not a same-run edit at
the end of a review. Landing an untested rewrite of the admission rule is exactly
the "inhibits the fleet" risk you named. **Step 1 is an afternoon and is
genuinely inert; Steps 2–3 are a scoped build with evidence.** It is recorded as
job #1 for the next run so it cannot circle.

**Correction to item 3 above:** the veto/exposure counter disagreement
(17 vs 20) is not merely cosmetic in this light — `long_effective_n = 14.3`
says the fleet holds 20 positions worth ~14 independent bets, so a count-based
cap of 20 is simultaneously too tight (on bets) and too loose (on correlation).
Reconciling the counters is a prerequisite for Step 3, not a side-quest.
