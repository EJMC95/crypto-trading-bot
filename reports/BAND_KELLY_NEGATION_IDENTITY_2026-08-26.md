# 🪁 BAND-KELLY: THE NEGATION IDENTITY FAILS — BOTH SIDES OF THE SAME EVENT LOSE

_Expansion research, 2026-08-26 (Wed, Sydney). Read-only measurement on the
fleet's own ledgers; one telemetry commit, no lever, no deploy to a live
service, no trading change._

---

## THE ONE-LINE VERDICT

🪁 band-kelly's founding claim — **+0.397%/trade, t=+3.58** — is **REJECTED by
the book's own live record** (n=216, **−0.025%/trade**, t=−0.15, z=−2.64
against the claim). Four candidate explanations were tested and **all four
refuted**. What survives is structural and generalisable: **a mirror is not a
negation.** The ghost and its mirror both lose on the same event family, and
their losses sum to friction rather than cancelling to edge.

**But the book publishes its own way out, and nobody had read it.** Its
`holdwatch` telemetry says the same trades held **60–120 minutes past the exit
are +0.29% to +0.32% better**. The exit — inherited wholesale from the ghost —
is the leak.

---

## 1. THE CLAIM vs THE RECORD (I14 — the record decides)

| | founding (`(rc)`, corrected) | **LIVE record** |
|---|---:|---:|
| source | negation of the ghost's n=65 crypto ledger | the book's own closes |
| n | 65 | **216** |
| mean %/trade | **+0.397** | **−0.025** |
| t | +3.58 | **−0.15** |
| win rate | **82%** | **37.5%** |

Live 95% bootstrap CI on the mean: **[−0.335%, +0.290%]**, P(mean≤0)=0.563.
**+0.397% sits outside it.** One-sided: z=−2.64 vs the corrected claim,
z=−3.94 vs the uncorrected +0.605%. Both rejected.

Window 19-Aug 08:43Z → 25-Aug 22:07Z. Sample is single-policy: 209 of 216 at
the `(qj)` $250 clip, 7 at $187.50 (a brain 0.75x), per-trade % clip-invariant.

**The win rate is the loudest signal.** 82% → 37.5% is not variance. It is the
signature of a different mechanism, and §3 identifies it.

---

## 2. FOUR CANDIDATE EXPLANATIONS, ALL REFUTED

Recorded so none is re-run without new evidence.

**(a) The deep tail — "refuse the extreme dislocations".** Four `stop` exits at
entry deviations of −479 to −1413bps cost −$91.53. A `|dev| <= 350bps` ceiling
turns −$16.85 into +$8.61. **REFUTED out-of-sample:** h1 +0.179%/trade,
h2 **−0.120%** — and 9 of the 10 deep-tail events are in h1, seven of them
inside **four minutes** on 22-Aug. The ceiling is fitted on one afternoon.
Bootstrap on the ceilinged subset: mean +0.024%, CI [−0.184%, +0.242%],
P(mean≤0)=0.420. No edge either side of the cut.

**(b) Non-independence inflating `t`.** Entries cluster: at a 300s window, 27%
of trades arrive in multi-coin batches, and **82% of multi-coin loops are
all-same-side** against 41% expected under independence — a venue-wide
reference move taken as many separate bets. **REFUTED as a statistical
problem:** cluster-robust t = **−0.26** vs naive −0.15, variance inflation
**0.37x**, n_eff **589 > n=216**. The clusters *self-hedge* (the mirror takes
both sides), and multi-coin clusters are net **+$19.02** while solo entries are
net **−$35.88**. The clustered events are the profitable ones.

**(c) Execution cost as the cause.** **REFUTED as sufficient.** The `conv`
exits realise **−18.64 bps/trade**; the median top-of-book spread is 9.60bps,
so gross of a full half-spread round trip they are still **−9.04 bps**. And the
spread relation is **U-shaped, not monotone** — the *tightest* spread quintile
(0.1–4.5bps) is the second worst at −0.331%/trade. OLS slope −0.78 bps of
return per bp of spread at **t=−1.11**. Cost is real; it is not the mechanism.

**(d) A cap breach.** Peak concurrency computes to 8 snap positions ($2,000
gross on a $1,000 book) against `MAX_POSITIONS=4`. **REFUTED — a measurement
trap, not a bug.** `opened_at` is the loop's start `t0`; `closed_at` is
wall-clock at publish; one scan pass takes ~2 minutes. Positions opened late in
a pass appear to start before positions closed early in the same pass. The cap
is enforced correctly at `lighter_band_kelly_bot.py:836`.
*Any hold or concurrency analysis on this book must account for the mixed clock
semantics.*

---

## 3. WHAT SURVIVES: THE NEGATION IDENTITY FAILS

The book's founding method is `mirror = −ghost_realised − (ghost_slip +
mirror_slip)`. Tested on the exit family that is ~93% of both books' closes:

| | n | mean %/trade | t | win |
|---|---:|---:|---:|---:|
| 🧲 ghost `converged` | 178 | **−0.230** | −3.10 | 43.3% |
| 🪁 mirror `conv` | 200 | **−0.186** | −3.38 | 35.0% |

If the mirror were the negation, its `conv` should read **+0.230%/trade**. It
reads **−0.186%**. **Gap: −0.417 pp/trade.**

**Both sides of the same event lose.** That cannot be a sign convention, and §2(c)
shows it is not mostly cost. The −0.417pp is almost exactly the shortfall of the
live record against the corrected claim (0.397 − (−0.025) = **0.422 pp**) — the
two arrive independently and agree.

### The mechanism

The mirror inherits the ghost's **exit** (`|dev| <= EXIT_BPS`, 40bps) along
with its entry gate. But the ghost exits on convergence because convergence is
*its* thesis; the mirror's thesis is **divergence**. The mirror is therefore
closing at the exact moment its own bet is being decided against it — and doing
so on a threshold its own entry gate guarantees it will cross. That is the
death mechanism recorded for the ghost itself at `(jh)`: *"100% converged exits
— the book harvests its own entry gate."* **The mirror inherited it.**

> **Doctrine candidate: a mirror may inherit a ghost's ENTRY; it must never
> inherit the ghost's EXIT.** The exit is defined by the ghost's thesis, which
> is by construction the opposite of the mirror's. And a realised ledger's
> negation is not an achievable return: the mirror is a NEW round trip with its
> own two crossings, not the same trade run backwards. `(qw)`/`(rc)` modelled
> that as a 34% haircut; measured, it is the whole of the claim.

Note this also explains the founding sample. The roster selected the ghost's
**crypto subset** (t=−5.71 vs −2.82 pooled) — the subset selected *for being
the worst loser* — and negated it. The `(rc)` jackknife tested coin
concentration; it did not test the split that defined the sample.

---

## 4. THE WIN-MORE FINDING: THE EXIT IS THE LEAK, AND THE BOOK ALREADY MEASURED IT

`bot_pnl['band-kelly-lshadow'].extra.holdwatch`, live, n=218–219 — extra
%/trade from holding past the book's own exit:

| horizon | +15m | +30m | **+60m** | **+120m** |
|---|---:|---:|---:|---:|
| mean extra %/trade | −0.332 | +0.044 | **+0.291** | **+0.324** |

Against a `conv` exit realising −0.186%/trade. The book exits at a **median
4.7 minutes**; its edge, if it has one, arrives around the hour.

**Throughput is not the obstacle** — the `(hl)` check, in the favourable
direction for once. Time-weighted occupancy is **0.12 of 4 slots (3%)**. A
12.8x longer hold implies ~1.5 of 4 slots: still inside the cap, so the
widening costs no entries.

**Three honest caveats, stated because they bound the number:**
1. `holdwatch` compares a later **MID** to the exit **VWAP**, so it is
   optimistic by roughly half the spread (~5bps, ≈1.7% of the +60m effect).
2. It is a **continuation**, not a replay: holding longer would change which
   trades hit the 5% stop or the ghost-stop. It indicates; it does not price.
3. Until today it published **`n` and `sum` only — no dispersion**, so none of
   these means had a `t`. *A mean with no sd is not something a decision can be
   made on.*

**Caveat 3 is now closed** (§6) — that is the measurement prerequisite, and it
is the only thing shipped by this session.

---

## 5. THE DECISION FOR EAMON (I17 — a keep-or-retire call is yours)

**Not a retirement recommendation.** The book is **undecided, not proven bad**:
mean −0.025%, t=−0.15, CI straddling zero. It is not a significant loser. It
runs ~31 closes/day, so it decides fast.

What has changed is **the bar it should be graded against**. The row still
advertises +0.397%/trade as its expectation; its own record rejects that.

Recommended, in order:

1. **Correct the published expectation in place (I12).** `extra.roster.snapfade`
   should carry the live record beside `founding` and `corrected`, so the
   ~mid-Sep grade reads a bar the evidence supports.
2. **Pre-register the follow-through now (I21 shape), graded only on closes
   after 26-Aug:** mean > 0 with **t ≥ 2.0** on the fresh sample alone, never
   by re-mining this window. Fail ⇒ an I17 keep-or-retire call, not a tuning
   pass.
3. **The exit re-spec is the live candidate, and it is gated on its own
   measurement.** Once `holdwatch` has published `t` for a week, if +60m/+120m
   clears t ≥ 2, replacing the inherited `conv` exit with a mirror-appropriate
   one is the change with a measured number behind it (I19). **Do not ship it
   on the mean alone** — that is what this note exists to prevent.
4. **`dipfade` needs no decision.** n=13, −$9.63, −1.852%/trade — the 18-Aug
   operator override is dying on its own record exactly as designed.

`band-kelly` has **no registered levers and no tuning lane** (env-only,
single-policy by construction), so `fleet_proposals` cannot reach it: every
item above is a code change or an operator call, never a hand-set lever.

---

## 6. WHAT SHIPPED (telemetry only — no position differs)

`lighter_band_kelly_bot.py`, two commits:

* `holdwatch_block` now publishes **`sd_pct`, `t`, `win_pct`, `n2`** beside the
  mean. Backward-compatible by construction: a durable bucket restored from
  before this change carries `n`/`sum` and no `sumsq`, so dispersion is counted
  over its own sample `n2` and reported as `None` until n2 ≥ 2 — never over a
  mismatched `n`, which would understate sd on exactly the longest-running
  horizons.
* `holdwatch_accumulate` **extracted from the loop**. The first mutation round
  is why: zeroing the `n2` increment **SURVIVED**, because the arithmetic lived
  inline in `main()` where no test could reach it — a dispersion that silently
  never accumulates, reading `None` forever while the mean looks healthy (I1 /
  I23). A second survivor was a missing `win_pct` assertion on the mixed-bucket
  case. Both fixed; **8/8 mutations killed** on the re-run.

`math` was not imported in this module. **That was MY omission, not a
pre-existing defect** — nothing here used `math` until `sd`/`t` did — and I
caught it by reading the import block, not by a red test, because the selftest
run that would have caught it came after the fix. Recorded that way round so it
is not read as a find.

Guards green: `audit_image_imports`, `audit_doctrine_enforcement`,
`audit_changelog_letters`, `tests/autonomy/test_band_kelly_mirror.py` (17),
module selftest.

---

## 7. THE TRANSFERABLE PART

1. **A mirror is not a negation.** Both sides of a round trip pay. Grade a
   mirror against its own forward record, never against the arithmetic
   inversion of a ledger.
2. **Inherit an entry, never an exit.** An exit encodes the thesis; a mirror's
   thesis is inverted, so an inherited exit closes the position exactly when
   the bet is being decided. This is `(sa)`'s nav-cook lesson in a new costume:
   *inheriting a component from a book with the opposite thesis silently
   re-specifies the rule.*
3. **A mean with no dispersion is not a measurement.** `holdwatch` carried the
   answer to this book's central question for a week and could not say whether
   it was significant.
4. **Opens and closes can be on different clocks.** Loop-start `opened_at`
   against wall-clock `closed_at` manufactured a phantom 2x cap breach. Check
   the clock before reporting a breach.

_Not financial advice. Go-live and real-money changes are Eamon's acts._
