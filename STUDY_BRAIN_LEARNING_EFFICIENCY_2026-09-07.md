# How efficiently does the brain learn? — 2026-09-07 (ze)

**Eamon:** *"The brain needs to be smarter, can you do a deep dive on how we can
learn and grow more efficiently. I want our intelligence to be elite."*

**The short answer, and it is not the one the question implies: the brain's
statistics are sound, its bars are calibrated, and it is starving.** Every
conditional axis anyone could point it at is empty at today's sample, and the
binding constraint on its decision rate is **closes per bucket** — 12 of its 23
positive buckets sit below the raw `n >= 30` floor. What is genuinely *broken*
is not the reasoning; it is that the fleet's most-wired actuator had **no
feedback loop at all**.

Everything below is reproducible:

```
python3 scripts/study_brain_learning_efficiency_2026-09-07.py --all
```

The instrument REFUSES (exit 2) unless it reproduces the live brain's own
published multipliers exactly — mult, `n`, and `t` within 0.02. It passed 5 of 5
on the run that produced these numbers.

---

## 0. What the brain is, in one paragraph

Two tiers, and they are inverted.

| | axes | statistics | reaches an actuator? |
|---|---|---|---|
| **Tier A** `compute_stake_mults` | `enter_tag` only | decay weighting, Kish `n_eff`, empirical-Bayes shrinkage, Wilson bounds, weighted `t`, episode dedup, a 3-run streak gate | **yes** — every living book, via `fleet_bus.brain_clip` |
| **Tier B** `analyse_bot` | pair, session, duration, mood, exit — **five more** | raw counts against hard-coded thresholds (`wr < 0.20`, `wr >= 0.55`); no decay, no shrinkage, no uncertainty, no multiplicity control | **no** |

So the brain is statistically elite on the one axis it can act on, and
statistically naive on the five axes where conditional structure would live.
That asymmetry is the thing this study went looking at.

---

## 1. The funnel — which gate actually binds

I18 says diagnose a stall by naming the gate that **binds**, not the ones with
room. Nobody had ever run that on the brain itself.

```
era buckets on living books               : 37
  positive (expand candidates)            : 23
  ...reaching the raw n>=30 floor         : 11   [-12 blocked by SAMPLE]
  ...and n_eff>=18.0                      : 11   [ -0]
  ...and t>=2.0 (expectancy)              :  5   [ -6 blocked by EXPECTANCY]
  ...and BOTH win-rate bars               :  4   [ -1 blocked by WIN RATE alone]
```

**52% of the brain's expand candidates are blocked by raw sample, before any
bar is consulted.** The six blocked by `t` are the bar doing its job. The
decayed-evidence floor (`n_eff`) never binds independently — it costs nothing
and catches nothing, which is worth knowing.

Realised range, measured on the ledger: the ladder reaches **6.7x either way**,
and of 891 stamped closes **624 (70%) ran at exactly 1.0x**, 199 at 0.325 (the
`(wu)` drawdown rail on 🪁 kelly), 44 at 0.75, **21 at 1.25x and one at 1.5x**.
The entire expand side — the half built on Eamon's *"the brain needs to be able
to widen too"* — has fired on **22 of 891 closes**, and has never exceeded 1.5x.

### 1a. The I15 trigger fired, and the answer was KEEP

One bucket clears everything and is held at 1.0x by **win rate alone**:

```
perps-funding-spread-lshadow | long   n=74  t=2.13  +1.348%/trade
                                      post_wr 0.513 (bar 0.55)  w_lo 0.466 (bar 0.50)
```

⚖️ Counterweight's long book earns **+1.35% per trade at t=2.13** and the brain
may not size it up because it wins 51.3% instead of 55%. That is I15 — *win rate
is not expectancy* — sitting inside an actuator, on the very fleet that removed
win rate from the go-live gate because 🌾 carry wins 38.8%.

**`(wu)` pre-registered exactly this and pre-registered the response: *"re-run
the instrument, never a bar."*** So the instrument was re-run
(`scripts/study_brain_floors_2026-09-02.py`, calibration 5/5):

| | bucket-days | fwd trades | fwd %/trade | own mean | **delta** |
|---|---|---|---|---|---|
| **V1** win-rate bars dropped | 67 | 220 | +1.992 | +2.105 | **−0.113pp** |
| **CONTROL** — buckets V1 would add, refused | 175 | 693 | +0.320 | +0.230 | **+0.090pp** |

**Dropping the win-rate bars does not earn forward.** The buckets the ladder
refuses beat their own mean; the buckets V1 would add do not. **Bars KEEP.**
The registration is honoured and Counterweight stays at 1.0x.

*(This is a refusal with evidence, which the doctrine counts as compliance. It
is also the second time this exact bar has been challenged and held.)*

---

## 2. The naive conditional rules are measurably worse than chance

The brain's `analyse_bot` pair/session rules were run against a **permutation
null**: shuffle the pair and open-hour labels *within* each book, so `n` per
cell, the book's win rate and its P&L are all preserved and only the
cell↔outcome association is destroyed. 200 draws, living books:

| rule | REAL | null mean | null p90 | null max | **P(null ≥ real)** |
|---|---|---|---|---|---|
| `pair_earner` | 11 | 14.1 | 18 | 21 | **0.935** |
| `pair_bleeder` | 1 | 1.0 | 3 | 4 | 0.675 |
| `session_hot_zone` | 0 | 0.0 | 0 | 0 | 1.000 |
| `session_dead_zone` | 0 | 0.0 | 0 | 1 | 1.000 |

**Chance produces more "consistent earners" than the tape does.** `pair_earner`
is the single largest category in the live hypothesis ledger (36 of 134 entries,
9 of the 20 ACTIONABLE ones) and it carries no information whatsoever.

And the whole tier is inert anyway: **0 of the 134 hypotheses in the live ledger
can reach any actuator.** `derive_actions` consumes only `diag_regime_timing`
and `derive_proposals` only `diag_entry_quality` on the taker; between them they
hold 6 hypotheses, all currently retired. So the brain does 134 findings' worth
of work per run and its best-populated rule is beaten by a coin flip.

---

## 3. A proper referee finds nothing either — and that is the real finding

The obvious response to §2 is "the rules are naive, give them the machinery Tier
A already has." So that was built and run: judged against the **book's own mean**
(I25, never the window that motivated the finding), **cluster-robust on distinct
UTC open-days** ((uf): a pooled `t` over one burst measures sampling density,
not edge), **Benjamini-Hochberg at FDR 0.05** across every test.

| axis family | tests | books/buckets | **survive BH** | permutation null |
|---|---|---|---|---|
| categorical entry-known (pair, hour6, side) | 82 | 13 books | **0** | mean 0.30, max 4 |
| continuous covariates the brain has never read | 27 | 12 buckets | **0** | — |

Strongest continuous covariate anywhere: `brk_quality` on 🎫 the taker's
`long-breakoutup`, rho −0.182, **t = −1.06**. Nothing is close.

**So the conditional tier is not fixable by better statistics. There is no
conditional structure to find on these axes at this sample.** Building a
smarter conditional learner today would be building a machine to find nothing —
and the permutation null is what says so, rather than an opinion.

### 3a. The instrument was wrong twice, in the reassuring direction

Worth recording, because it is the same trap both times and it is I7:

* **First cut** graded `exit_reason` and hold-duration and found **68
  "effects"**. Thirty-five were take-profit buckets. A `tp` bucket wins **by
  construction** — `winners_docket` already owns this rule
  (`OUTCOME_EXITS`) and my referee had rediscovered it the hard way.
* **Second cut** deny-listed four outcome names and still admitted `price_pnl`
  (a *component* of the P&L), `peak_ret`, `mae_ret` and `accrued` — all reading
  rho > 0.84, all pure outcome.

**A deny-list cannot do this job**: it has to anticipate every field a new book
invents. The shipped instrument uses an **allow-list** (`ENTRY_KNOWN`) — a
covariate is admissible iff its value is determined **at the open** — and it
COUNTS what it refuses (22 admitted, 17 refused) so the refusal is visible
rather than silent.

---

## 4. The brain could not see its own output — and now can

`fleet_proprioception` has graded every growth-rail **lever** since 16-Jul and
publishes helping/hurting/neutral. The stake multiplier reaches **every living
book** through `fleet_bus.brain_clip`, real money included — and it was the
**one actuator in the fleet with no retrospective grade at all**.

The reason is structural and was verified by AST: **the string `extra` appears
nowhere in `bot_learn.py` or `brain_stats.py`.** The books stamp **54 numeric
covariates** onto their closes — including `brain_mult` itself on **916 living
rows** — and the brain has never opened the envelope. It sized 916 trades and
could not read what size it chose.

**Shipped: `brain_stats.selfgrade_mult`**, published every run on
`brain-vitals.selfgrade`. First live reading:

```
coverage {"bots": 16, "closes": 1927, "stamped": 891, "buckets": 15}
pooled   {"graded": 4, "undecidable": 3, "helping": 0, "hurting": 0,
          "neutral": 4, "mean_gain_pp": 0.6364}
```

**Undecided, leaning right: +0.64pp mean gain, no bucket at |t| ≥ 2.** That is
the honest state of the fleet's most-wired actuator, and it is a number nobody
had.

### Why the basis is per-trade %, and never dollars

**This is the whole design.** A 2.0x multiplier doubles `profit_abs` *by
construction*. Grading a position-size actuator in dollars is I7 in its purest
form — the metric is a mechanical consequence of the knob, so every multiplier
"works" and the grade is a tautology. `profit_ratio` is invariant to clip
((hl), measured), so it asks the only honest question: **did the trades the
brain sized UP earn more per unit than the ones it left alone?**

The selftest's load-bearing pin is exactly that trap: two arms with **identical
per-unit returns and a 3× dollar skew** must read `neutral`. Nine of nine
mutations verified red, including one that survived the first round because my
own fixture had zero variance and never reached the statistic.

Design notes, each of which is a pinned test:

* **Baseline is a within-bucket control arm** — the same `(bot, tag)` bucket's
  1.0x closes, not the pre-multiplier window, which is selected on an extreme
  and is a biased estimator by construction (I25). No control arm ⇒ never graded.
* **Forward by construction**: a trade's `brain_mult` was computed from closes
  that had already happened when it opened, so its own return is out-of-sample.
* **Cluster-robust on distinct UTC open-days** ((uf)).
* **The sign of "good" flips with direction** — a *down* multiplier helps by
  cutting size on trades that earn less. Reading it one way grades every
  throttle as a failure for doing its job.
* **Fails to `undecidable`, never to a verdict.**
* **REPORTED ONLY** — pinned by an AST walk of call sites, not a substring scan
  ((po)/(yk)), and `compute_stake_mults` is pinned not to read it: a grader that
  feeds back into the thing it grades stops being a control.

---

## 5. What this means — the options, with reasoning

The binding constraint is **evidence per bucket**. Four ways to relieve it, in
the order the measurement supports:

**A. More closes per bucket — the only lever the measurement actually endorses.**
This is I17/I22 at *bucket* scale rather than book scale, and it is already
fleet doctrine: decidability velocity is additive across independent sleeves,
so days-to-decision falls with the square. Nothing new is needed; it is the
existing ceiling/spend work continuing to pay off in a place nobody was
counting. **Recommended.**

**B. Pool expectancy across books the way win rate is already pooled.**
`eb_prior` shrinks the **win rate** toward tag-family → bot → fleet. The bar
that actually blocks (`t`) has **no prior at all**, so a thin bucket computes it
from its own 30 closes with nothing behind it. Tempting — and **refused on the
expand side**: the `(bh)` asymmetry deliberately forbids praise inheritance
("a sibling's win rate is not this tag's"), and shrinking `t` toward a pool
would let a thin book be sized up on its siblings' record. Legitimate on the
**reduce** side or as a REPORTED number; that is a measured build, not today's.

**C. Pool the live/shadow twin arms.** The funnel makes this look free —
`freqtrade-mum-lshadow|long-oversold-rebound` (n=92, t=2.69, **1.5x**) and
`freqtrade-mum-lighter|long-oversold-rebound` (n=91, t=1.13, **nothing**) are
the same strategy and the same tag on two arms of one book, learned from scratch
as two strangers. Same for 🙏 avo (n=30 → 1.25x vs n=15 → blocked, and the
n=15 arm is **real money**). **Refused:** the shadow twin is a *control arm*.
`(xd)` measured that the arms run different entry files; `(ye)` that their caps
differed. Pooling them destroys the only baseline I25 says is immune to
reversion, and the judge's entire paired bar depends on their separation.

**D. Richer conditioning.** Measured empty (§3). Revisit when a book's sample
grows, not before — the instrument is registered and will say so.

---

## 6. What shipped today

| | |
|---|---|
| `brain_stats.selfgrade_mult` | the brain grades its own multiplier; published on `brain-vitals.selfgrade`; REPORTED-ONLY; 9/9 mutations red |
| `scripts/study_brain_learning_efficiency_2026-09-07.py` | four calibrated arms — funnel, naive null, referee, self-grade; REFUSES on a feed it cannot reproduce |
| `tests/autonomy/test_brain_selfgrade.py` | 13 structural pins incl. the AST moves-nothing walk |
| `bot_learn.analyse_bot` prose | the two pair rules now carry their own measured null in the sentence a human reads |

**Nothing moved money, no lever was written, no bar was changed.** Two bars were
challenged by measurement and **held**: the expand win-rate bars (§1a) and the
`n >= 30` floor (§1 — the floor is the constraint, and the fix is more closes,
not a lower floor).

## 7. Open, and deliberately not closed here

* **⚖️ Counterweight's `long`** sits at t=2.13 / +1.35%/trade held at 1.0x by
  win rate. The bars held on today's forward evidence. If that bucket is still
  there when its sample grows, re-run the floors instrument again — **never
  move the bar** ((wu)'s registration, still standing).
* **The carried `brain-mult-transition-oscillation` row** asked for the
  multiplier's transition behaviour to be tested against real closes rather
  than a model. `selfgrade_mult` is the instrument that makes that possible;
  the test itself needs buckets that have crossed a rung, and today only four
  are gradeable at all. Not closed.
* **`n_eff` never binds independently** on any current bucket. Harmless, but it
  means the decayed-evidence floor is currently decorative — worth a look when
  a bucket ever sits between the two floors.
