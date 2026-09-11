# MONTHLY GO-LIVE BOARD — August 2026

_Generated 2026-09-07 09:30 Sydney (2026-09-06 23:30Z). Month resolved in **Sydney**
local (1-Aug 00:00 AEST → 1-Sep 00:00 AEST = 31-Jul 14:00Z → 31-Aug 14:00Z)._

**LATE FIRING, declared:** this job fires on the 1st. It did not run on 1-Sep and no
`monthly_golive_board_2026-08.md` existed, so this is the August sitting taken on the
7th. Nothing was overwritten. Consequence to keep in mind while reading: **the gate
numbers below are TODAY's, not 31-Aug's** — the grader has no as-of mode and
back-dating it would be a second copy of the rule. Where a verdict turns on the
difference I say so.

**READ-ONLY run.** No trades, no lever/config/env change, no deploy, no dry_run or key
touched. Go-live remains an explicit operator act; passing the gate is a precondition,
never a trigger. Not financial advice.

**Standard imported, not restated:** bars from `scripts/golive_readiness.py`
(`bar_map`/`BAR_NAMES` = window/closes/mean/t/halves/maxdd), eras from `POLICY_ERA` +
the ledger's own policy stamps, integrity from the published payload, claims from
`fleet_allocation` (lower bound at `t_crit(n)`, `MIN_N` 10).

**Provenance / liveness (I1 before semantics):**

| source | state |
|---|---|
| `bot_pnl` | 18 rows, 16 live books, freshest age 1s, `feed_stale: false`, `n_stale: 0` |
| `paper_trades` | 5,017 rows; 4,242 admissible after quarantine (47 withheld) + 13 phantom closes excluded |
| `golive-readiness` | published 2026-09-06 21:38Z, TTL 43200s — fresh |
| `fleet-allocation` | published 2026-09-06 23:08Z, TTL 5400s — fresh |
| `audit_ledger_integrity` | exit 0; one TWO-WRITERS book (🌾 carry), **historical** — deepest overlap 9.14h on HYPE, most recent began 951.6h ago, entirely before its 31-Jul era |

---

## 1 · The month in one line

**August lost $245.93 realised across 1,778 graded closes — and $230.20 of that came
from books the fleet has since retired.**

| August 2026 (Sydney month, graded ledger) | net |
|---|---:|
| Fleet total realised | **−$245.93** (1,778 closes, 32 books) |
| … books still visible today (16) | −$15.73 |
| … books retired/hidden since (16) | **−$230.20** |
| … of which REAL MONEY (5 arms) | **−$19.40** |

### The survivorship warning, and it is the most important line on this board

`/periods.json` reports August as **−$17.57**. The graded ledger reports **−$245.93**.

Neither is wrong. `periods.json` aggregates `by_bot` over rows the dashboard currently
*shows*, and sixteen of August's thirty-two trading books have since been retired and
hidden. So the public monthly figure is **survivorship-filtered by construction**: every
retirement silently improves the recorded history of the month in which the book was
losing money.

That is a $228 gap on a single month, and the direction is always flattering. It is the
`{open: 0}` ambiguity (I18) at fleet-P&L scale — the number is byte-identical between
"the fleet had a quiet month" and "the fleet amputated its losses and the ledger forgot".
**Recommendation R5 below makes it a published number rather than a thing a board has to
rediscover.** Nothing is broken in the dashboard; it is answering a different question
than the one a monthly review asks.

**Where August's damage actually sat** (retired-since books, graded): 🪁 kelly −$129.08
(still living), 🔮 georgia's live arm −$71.91, 🧘 douglas −$51.24, ⚖️ Counterweight
−$46.62 (still living), 💸 Farmer shadow −$30.35, 🛢️ Garrett −$25.77, 🎸 Barnesy −$11.06,
🧭 cook −$9.99, 💸 Farmer live −$12.54.

**Where it earned:** 👩 mum's LIVE arm **+$73.97** (43 closes, 83.7% win) and 🎫 the
taker's shadow **+$68.39** (141 closes). Those two books are the whole positive side of
the month.

---

## 2 · The board

Real-money rows first. `maxDD` is the **worse of realised and MTM** since (ia)/(iz) —
the basis actually used is named. `claim` is `fleet_allocation`'s era-scoped lower bound
(%/trade); `—` means floored at zero, which is REPORTED and never ranked (I15/I16).

### 2.1 Real money

| book | bars | n (era) | days | mean%/tr | t | maxDD (basis) | claim_era | verdict — which bars bind |
|---|---|---:|---:|---:|---:|---|---:|---|
| 🙏 **avo-maria LIVE** | 3/6 | 14 | 18.3 | +2.360 | 1.72 | 5.6% (mtm) | 0.00436 | `window` 18.3<30d, `closes` 14<30. Era 2026-07-17, all 14 count. Horizon **undecidable (t)** — ~100d at 0.27 closes/day. Equity $412.55, lifetime **+$98.39**. |
| 👩 **mum LIVE** | 4/6 | 90 | 9.3 | +0.420 | 2.08 | 7.1% (**realised**) | 0.00157 | `window` 9.3<30d and **`halves` +79.06/−2.96 not both positive**. Era 2026-08-19 21:45 (the v2 redesign), all 90 count. Horizon **on_track, ETA 2026-09-27** — with the explicit floor that halves must also mend. Equity $576.01, lifetime **+$55.59**. |

**Neither live row is degraded.** Both are net positive lifetime; live fleet equity
$988.56 on +$153.98 cumulative. Two watch items, stated plainly rather than escalated:

- 👩 mum's **h2 is −$2.96** against h1 +$79.06. That is the one bar standing between her
  and a 5/6 reading, it is the bar that cannot be fixed by waiting alone, and her
  September-to-date is **−$5.40** against August's +$81.50. Read this against **I25**
  before drawing any conclusion: her August was a hot window, and a hot window is
  followed by a −1.674pp collapse *with or without a change*. The correct baseline is
  her own era mean and her shadow twin — **not** August. Her twin (`mum-lshadow`) reads
  +0.528%/trade at t=2.75 on the same 90 closes, i.e. **the twin is ahead of the live
  arm**, which is the ordinary live-vs-shadow execution gap and not a regime story.
- 🙏 avo LIVE is `undecidable (t)` at 0.27 closes/day: **~100 days to the t bar**, beyond
  the 90-day horizon. She holds the fleet's **highest era claim** on the shadow side
  (0.00821) and her live arm the third-highest (0.00436). Her constraint is supply, not
  edge — which is exactly what the (ye) slot 5→6 change was bought to relieve, and that
  read is pre-registered for 6-Oct.

### 2.2 Shadow books, graded

| book | bars | n (era) | days | mean%/tr | t | maxDD (basis) | claim_era | horizon |
|---|---|---:|---:|---:|---:|---|---:|---|
| 🎫 **ticket-taker** | **6/6 READY** | 183 | 37.1 | +1.195 | **2.63** | 5.4% (mtm) | 0.00609 | **ready** — see §3 |
| 🙏 avo shadow | 5/6 | 29 | 39.8 | +1.793 | 2.46 | 1.5% (mtm) | **0.00821** | **on_track, ETA 2026-09-08** — `closes` 29<30, ~1.8d |
| 👩 mum shadow | 5/6 | 90 | 12.5 | +0.528 | 2.75 | 1.1% (mtm) | 0.00279 | on_track, ETA 2026-09-24 (`window`) |
| 🌾 carry | 4/6 | 28 | 33.6 | +0.289 | 2.31 | 2.0% (mtm) | 0.00121 | on_track, ETA 2026-09-11 — `closes` 28<30 **and `halves` −17.46/+28.09** |
| 🏛️ turnbull | 5/6 | 48 | 46.2 | +0.261 | 1.16 | 0.2% (mtm) | — | undecidable (t), ~105d |
| 🏛️ albanese | 5/6 | 67 | 46.3 | +0.003 | 0.01 | 0.9% (realised) | — | undecidable (t), ~1.9M days |
| 🔮 georgia v1 | 5/6 | 262 | 51.2 | +0.089 | 0.67 | 2.3% (mtm) | — | undecidable (t), ~813d |
| 🎯 perp-sniper | 3/6 | 47 | 46.8 | −0.694 | −0.78 | 0.9% (realised) | — | **underpowered** (ub +0.465%) |
| 🔮 georgia v3 | 2/6 | 88 | 9.1 | −0.084 | −0.74 | 0.8% (mtm) | — | **underpowered** (ub +0.062%) |
| 🚀 bezos | 2/6 | 33 | 5.1 | −0.727 | −1.41 | 3.5% (realised) | — | unreachable (ub −0.052% ≤ 0) |
| ⚖️ Counterweight | 3/6 | 153 | 50.0 | −1.499 | −1.74 | 5.1% (realised) | — | unreachable (ub −0.388% ≤ 0) |
| 🪁 kelly | 1/6 | 585 | 18.5 | −0.142 | −1.24 | **28.5% (mtm)** | — | unreachable — **maxDD 28.5% is 1.9× the 15% bar** |

Below the 10-close publish floor, on their own samples: 🧮 **hull** n=5, on_track ETA
2026-10-12; 🏦 **kiyosaki** n=7, on_track ETA 2026-10-09. Both at ~0.70 closes/day — slow
cash-flow clocks by design, neither is stuck.

**Allocation (advisory — moves no capital, writes no lever).** Six books hold a positive
era claim: 🙏 avo shadow 0.00821 · 🎫 taker 0.00609 · 🙏 avo live 0.00436 · 👩 mum shadow
0.00279 · 🌾 carry 0.00121 · 👩 mum live 0.00157. Ten read 0.000 — and per (ua) that is
REPORTED with its `bound_pct`, not a claim of nothing: 🏦 kiyosaki (+0.00168) and 🧮 hull
(+0.00075) carry genuinely positive bounds and are floored only by `MIN_N`.

---

## 3 · The READY verdict, and the test it has not passed

🎫 **`lighter-ticket-taker-lshadow` is the fleet's first-ever 6-of-6 READY book.** It is
worth saying plainly how good the gate reading is before saying what is wrong with it.

**What is genuinely strong:**

- **Both samples agree.** In-era n=183, t=2.63, all six bars. All-time n=279, t=2.71, all
  six bars. That two-sample agreement is the (mr) standard.
- **The `t` survives clustering.** Cluster-robust t=2.68 at n_eff 274.3 over 267 clusters
  (max batch 4) — these closes do not batch.
- **Ledger integrity is clean.** `two_writers: false`, zero same-pair overlaps all-time.
- **Drawdown has real headroom.** 5.42% MTM over 9,326 samples / 32.9 days, against a 15%
  bar — and the MTM number is the one used, so I9 is satisfied rather than dodged.
- **Halves improve rather than decay:** h1 +$32.43, h2 +$123.29.

### And then the decomposition

Splitting the era's 188 closes by the tag they were actually taken under:

| bucket | n | net$ | mean%/tr | t |
|---|---:|---:|---:|---:|
| **`long-breakoutup`** | **140** | **+181.95** | **+1.931** | **+3.48** |
| `short-divergence` | 48 | −17.63 | −0.794 | −1.36 |

**The entire READY verdict is one bucket, and it is a LONG bucket.** The book's only
other live lens loses money.

### The regime it passed in — and it has flipped

Item 18 has said since July that Lighter's tape is one falling-BTC regime. **That is no
longer what the tape contains, and this board is the first document to say so with the
number:**

| window | BTC | move |
|---|---|---|
| 1-Aug → 1-Sep (Sydney) | 62,665.7 → 78,554.5 | **+25.4%** |
| taker era 30-Jul → now | 64,751.8 → 80,116.8 | **+23.7%** |

The regime oracle agrees and is unambiguous: fleet read **"risk-on uptrend"**, 11 pairs
LONG-window, **0 short**; BTC close 79,805 vs ema200 72,469, ADX 46.6.

So a long-only breakout book passed "both halves positive" across a **+23.7% BTC window**.
Item 18's exact words — *a directional book passes both halves BY CONSTRUCTION when the
drift does the work* — apply, with the sign reversed from the one the doctrine was
written for.

### The (hm) random-entry null, run

I21 is explicit: *a directional survivor still owes the (hm) random-entry null before
anything ACTS on it.* Nothing had run it on this bucket. It is run here.

**Construction:** each of the 140 `long-breakoutup` episodes, matched on **coin** and
**hold duration**, against random entry minutes drawn uniformly from the same era window
on the same coin. Lighter 1h tape, 36 coins, 140/140 episodes covered, zero tape gaps.
K=300 pooled draws; M=400 per-episode draws for the paired test. Seed fixed.

| | result |
|---|---|
| Taker's exit-free hold return | **+1.597%/trade**, t=+3.05 |
| Matched-random entries, same coins/durations | **+1.250%/trade** |
| **Excess over the null** | **+0.347 pp/trade** |
| **P(random ≥ taker)** | **0.193** (58 of 300 draws) |
| Paired excess (episode − its own null), iid | +0.330 pp, **t=+0.64** |
| Paired excess, **by-coin clustered** (36 coins) | +0.722 pp, **t=+1.03** |
| **Top-3 coins' share of the excess** | **168.6%** (UNI, ADA, ARB) |
| **Ex-top-3** | **−0.248 pp, t=−0.53 — NEGATIVE** |
| Episodes beating their own matched-random mean | **59/140 = 42.1%** (chance 50%) |

**Read it plainly: a coin flip on the same coins over the same window earned
+1.250%/trade for free. The taker's entry added +0.347pp that is not distinguishable
from zero at any convention — P=0.193 pooled, t=+0.64 paired, t=+1.03 clustered — and
strip the three best coins and the excess goes negative. The median episode did WORSE
than a random entry on its own coin (42.1% < 50%).**

**~78% of the book's raw return is the rising tape.**

**What this does NOT say, and the distinction matters:**

- It does **not** say the book is worthless. Its realised bracketed return is
  +1.931%/trade against +1.597% exit-free, so **the bracket contributes ~+0.334pp** — the
  exit machinery is doing real work on entries that are, by themselves, coin flips.
- It does **not** say the gate is wrong. Six bars pass, honestly, on the correct MTM
  basis, over a clean ledger.
- It does **not** retire anything. I17-as-amended requires a *measured exclusion* to
  retire, and this is the opposite finding: an unproven positive, not an excluded one.
- **Declared limit:** the null is **exit-free**, while the shipped rule is bracketed. The
  fully faithful (hm) construction runs random entries *through the taker's own
  `exit_reason` over the scout tape*, which needs `lighter_ticket_replay` and 5m
  resolution; the 5m fetch for 36 coins exceeded this run's egress throttle. The
  exit-free form is the (qu)/(tx) construction and is the honest half that could be run
  today. **It should be re-run bracketed before any promotion** — R1 names that as the
  gating act, not as a nice-to-have.
- Per **I21**, the `tp` bucket (n=11, +5.158%/trade, t=10.51) is a winner **by
  construction** and never reaches a referee. The buckets that count are `hold`
  (n=65, +2.187%, t=4.65) and `trail` (n=79, +2.208%, t=2.54).

---

## 4 · Decidability census (I17)

Every living book, in-era closes against its window, at the current measured rate.

**Decidable and moving** — 5 books:

| book | n | closes/day | 30 closes | gate ETA |
|---|---:|---:|---|---|
| 🙏 avo shadow | 29 | 0.73 | **~1.8d** | 2026-09-08 |
| 🌾 carry | 27 | 0.81 | **~4d** | 2026-09-11 (halves must also mend) |
| 👩 mum shadow | 90 | 7.20 | met | 2026-09-24 (window) |
| 👩 mum live | 90 | 9.68 | met | 2026-09-27 (window + halves) |
| 🎫 taker | 183 | 4.93 | met | **READY** |

**Undecidable at the measured rate** — 4 books, and none is a slow winner:

| book | n | verdict | distance |
|---|---:|---|---|
| 🔮 georgia v1 | 262 | undecidable (t) | **~813 days** — mean +0.089% sits below her own `mde80` 0.374%: precise about a number too small to prove |
| 🏛️ turnbull | 48 | undecidable (t) | ~105 days |
| 🏛️ albanese | 67 | undecidable (t) | **~1.87M days** — mean +0.003%, effectively zero |
| 🙏 avo live | 14 | undecidable (t) | ~100 days at 0.27 closes/day — **supply-limited, not edge-limited** |

**Underpowered — explicitly NOT on the retirement docket** (I17-as-amended: the sample
has not excluded a positive mean): 🎯 sniper (ub +0.465%), 🔮 georgia v3 (ub +0.062%).

**Measured exclusion — the only books that qualify for the docket at all:**

| book | n | mean | upper bound | what retiring frees |
|---|---:|---:|---:|---|
| ⚖️ Counterweight | 153 | −1.499% | **−0.388%** | 10 open legs, a row, the largest always-in shadow exposure. **Already pre-registered — do not act early (see §6).** |
| 🚀 bezos | 33 | −0.727% | **−0.052%** | a 6-day-old row. Technically excluded; see R4 — acting on 5.1 days is the I25 error. |
| 🪁 kelly | 585 | −0.142% | +0.006% | **has NOT excluded a positive mean** — its 28.5% maxDD is the live problem, not its mean. Pre-registered for 1-Oct. |

**Below floor, healthy:** 🧮 hull (n=5) and 🏦 kiyosaki (n=7) are on-track at ~0.70
closes/day for mid-October. Slow by design; nothing is starving them.

---

## 5 · Regime coverage (item 18)

**The doctrine's regime premise is now stale, and this is the board finding with the
longest half-life.**

CLAUDE.md item 18 states: *"Lighter's whole 438d tape is one falling regime (BTC −32.9%;
the family regime gate reads risk-off 61.5% of bars; BOTH halves fall), so a directional
short passes both halves BY CONSTRUCTION."* The corollary the fleet has run on ever since
is that **shorts** are the suspect side and that non-crypto books are the only source of a
non-falling regime.

Measured today, on Lighter's own tape:

- BTC **+25.4% across August**, **+23.7% across the taker's whole graded era**.
- Regime oracle: **"risk-on uptrend"**, 11 pairs LONG-window, **0 short**, BTC ADX 46.6
  with close 10.1% above its ema200.

**The tape now contains a strong rising regime, on-venue, in crypto.** That is good news
twice over — item 18's stated prerequisite for grading directional books (*"only a
different regime does"*) has partially arrived without anyone having to widen into
non-crypto to get it, and the fleet's *shorts* now have the regime coverage they lacked.

But the hazard has **flipped side and nothing in the doctrine has moved with it**:

- Every directional **LONG** book graded on a window inside 30-Jul → today has passed
  "both halves positive" with a +23.7% tailwind. That is now the by-construction pass,
  and 🎫 the taker's READY verdict is the first live instance of it.
- The one directional book whose *shorts* are its live sleeve — the taker's
  `short-divergence` — is the bucket that lost money, in exactly the regime where a short
  should lose. Its −0.794% at t=−1.36 may be regime, not defect.
- 🪁 kelly's −$129.08 August and 28.5% drawdown were incurred while short-heavy into a
  +25% market. `regime-short-veto-preregistered-read` (due 16-Sep) is aimed squarely at
  this and its registration note already records that BTC read LONG-window in **418 of
  418** oracle snapshots.

**No directional book on this board has a graded window containing both regimes.** A
one-regime pass is a pass in that regime only — the rule is unchanged; only its sign has.

---

## 6 · Recommendations, ranked

Each names its evidence and the exact next act. Nothing here was executed.

### R1 · 🎫 the taker: **KEEP ACCRUING — do NOT promote on this evidence.** `owner: session → operator`

**Evidence:** 6/6 bars, t=2.63 in-era and 2.71 all-time, cluster-robust 2.68, clean
integrity, 5.4% MTM DD. **Against:** the entire verdict is `long-breakoutup`; a matched-
random long on the same coins earned +1.250%/trade for free; excess +0.347pp at P=0.193,
paired t=+0.64, clustered t=+1.03; ex-top-3-coins **negative**; 42.1% of episodes beat
their own null. Graded window is BTC +23.7%.

**Why not promote:** I21 requires the random-entry null before anything ACTS on a
directional survivor. It has now been run and the book **does not clear it**. Promoting
would also cost a fresh sub-account — the taker's own live arm was retired 13-Aug and the
slot went to 🙏 avo — so this is not a free flip of a switch.

**Why not retire or tighten either:** the gate reading is honest, the bracket adds a real
+0.334pp, and "unproven" is not a measured harm (**I26** — the burden sits on the
refusal). Nothing about the book should be narrowed on this finding.

**Exact next act (session):** re-run the null in its **bracketed** form —
`lighter_ticket_replay` over the scout tape at 5m, random entries through the taker's own
`exit_reason`, same coins/window, ≥300 draws — and pre-register the read **now**: promote
only if the bracketed excess clears **t ≥ 2 by coin cluster** on ≥140 episodes, and
report it against the book's era mean, never the window that motivated it (I25).
The `taker-hold-floor-preregistered-read` (due 16-Sep) already needs the same replay
harness; run them together.

### R2 · 🙏 avo shadow: **KEEP — the decision lands within days, and it is the fleet's best-evidenced book.** `owner: session`

**Evidence:** 5/6 bars, n=29, **1.8 days from the closes bar**, ETA 2026-09-08 — i.e.
likely already met by the time this is read. Highest era claim in the fleet (0.00821),
t=2.46, maxDD 1.5% MTM. Her live arm is `undecidable (t)` purely on **supply** (0.27
closes/day, ~100d), not edge.

**Exact next act:** re-run `golive_readiness.py` on or after 8-Sep. If she reads 6/6, she
is a **directional** book and owes the same §3 treatment as the taker — run the
random-entry null on her own coins/window **before** the READY reading is quoted anywhere
as a promotion case. Her (qu) 50-close revert criterion and the `avo-live-slot-6`
read (6-Oct) are both still open and unaffected.

### R3 · 👩 mum LIVE: **KEEP, and judge her against her twin — not against August.** `owner: session`

**Evidence:** 4/6, the binding bar is `halves` (+79.06/−2.96), ETA 2026-09-27. August
+$81.50, September-to-date −$5.40. Twin reads +0.528%/trade at t=2.75 on the same 90
closes — **ahead of the live arm**.

**Why this is a keep and not an alarm:** her August was a hot window and **I25** measures
what follows one at −1.674pp *with or without a change*. Judging her September against her
August is the exact biased estimator the invariant names. The live-vs-twin gap is the
ordinary execution gap, and `grade_live` already judges her against the twin and her
era mean excluding the motivating window.

**Exact next act:** no change. Let `mum-halt-cost-preregistered-read` (n≥5 halt events
after 3-Sep) and the 27-Sep window bar arrive on their own clocks. **Do not tune her
because September looks worse than August** — that is the (vc) finding in its live form.

### R4 · 🚀 bezos: **KEEP and pre-register — do not retire a 6-day-old book.** `owner: session`

**Evidence:** n=33 in 5.1 days, mean −0.727%, upper bound **−0.052% ≤ 0** — it *has*
technically excluded a positive mean, which is the I17 retirement condition.

**Why the refusal is nonetheless correct:** the window is 5.1 days, the book was born
1-Sep and lost ~3 hours of its first day to the (wx) douglas-guard defect, and I25 forbids
judging on the window that motivated the look. An upper bound of −0.052% is a hair below
zero on a sample that is one bad day wide. It is also outside this board's month.

**Exact next act:** pre-register the read now — grade at **n≥60 or 1-Oct, whichever
first**, retire if the fresh upper bound is still ≤ 0, keep if the fresh mean > 0. Add the
row to `golive_readiness.DECIDED_UNTIL` so the docket asks on the date rather than a
session remembering (the I21 prose failure).

### R5 · **Publish the retired-book drag** so a monthly total stops being survivorship-filtered. `owner: session`

**Evidence:** August reads **−$17.57** on the visible rows and **−$245.93** on the graded
ledger — a **$228.36 gap**, entirely composed of books retired since, and the bias runs
one way every month.

**Exact next act:** add a `retired_drag` field to `/periods.json`'s monthly records —
the same aggregate computed over `RETIRED_ROWS`/`LEGACY_BOTS` members, published beside
`total` rather than replacing it. Small, publish-only, moves no trade. This is the
`{open: 0}` ambiguity (I18) at fleet scale: the current number cannot distinguish a quiet
month from an amputated one.

### R6 · **Correct item 18 in place (I12): the regime premise no longer describes the venue.** `owner: session`

**Evidence:** BTC +25.4% in August, +23.7% over the taker's era, oracle "risk-on uptrend"
11 long / 0 short, ADX 46.6. Item 18 states the tape is one *falling* regime and that
non-crypto books are the only on-venue source of anything else.

**Exact next act:** amend item 18 to say the by-construction hazard is **side-dependent
and regime-dependent**, that the crypto tape has carried a strong rising regime since
~30-Jul, and that a directional LONG passing "both halves" in this window earns the same
scepticism a directional SHORT earned in the falling one. Name the numbers. **This is
doctrine, not a fleet change** — but it is deliberately left for a session to perform
rather than done here, because this run is scoped read-only and a doctrine amendment
under (vc)/(vd) owes its own changelog entry and enforcement reference. Flagged, with the
measurement attached, so the next session can ship it in minutes rather than re-derive it.

### One EXPANSION note, expectancy-priced (I19)

**🙏 avo shadow's supply, not her edge, is the binding constraint — and she is the fleet's
best-evidenced book.** She holds the highest era claim (0.00821) at t=2.46 on 1.5% MTM
drawdown, and produces **0.73 closes/day**; her live twin produces 0.27/day and is
`undecidable (t)` at ~100 days *purely on rate*. Under **I26** an expectancy-neutral
widening on a book that cannot be graded is strictly positive, and the burden sits on the
refusal.

**But the honest price is not yet computable, so this is a NOTE and not a proposal.** The
(ye) slot 5→6 change is 1 day old with **zero post-change live closes**, and its own read
is pre-registered for 6-Oct. Widening anything else on her now would contaminate that
registration — the exact I21 failure the fleet paid for at (tt). **Recommendation: change
nothing on avo until 6-Oct**, then price a universe or cap widening against whatever the
slot read returns. Refusing a widening for a *measured* reason (an open registration it
would void) is I26 working, not inertia.

---

## 7 · Decision calendar (Sydney)

| date | book | what falls due | owner |
|---|---|---|---|
| **~8-Sep** | 🙏 avo shadow | 30th close → likely 6/6; run the null before quoting READY (R2) | session |
| **10-Sep** | 🔮 georgia v1 | `georgia-entry-cap-5-days-to-gate` — grade post-cap closes ONLY; fail → retire | session |
| **~11-Sep** | 🌾 carry | 30th close; `halves` must also mend | session |
| **16-Sep** | — | `regime-short-veto` read; `taker-hold-floor` read (pair with R1) | session |
| **16-Sep** | 👩 mum | `mum-noncrypto-sleeve` read at G≥10 entry days | session |
| **24/27-Sep** | 👩 mum shadow / live | 30-day window bar; live also needs halves | session |
| **1-Oct** | ⚖️ Counterweight | fresh on-class read — **retire if fresh ub ≤ 0** | session |
| **1-Oct** | 🪁 kelly | fresh read at $80 clip — retire if fresh ub ≤ 0 | OPERATOR |
| **1-Oct** | 🚀 bezos | new registration proposed in R4 | session |
| **6-Oct** | 🙏 avo live | slot 5→6 read at ≥10 closes opened with ≥5 held | session |
| **~9/12-Oct** | 🏦 kiyosaki / 🧮 hull | 30-close bars | session |

---

## 8 · Limits of this board

1. **The gate numbers are 7-Sep, not 31-Aug.** The grader has no as-of mode; back-dating
   it would be a second copy of the rule (a second rule). Where a verdict is close to a
   boundary I said so.
2. **The random-entry null in §3 is exit-free**, not bracketed. It is the honest half that
   the egress throttle permitted; R1 makes the bracketed form the gating act for any
   promotion. Do not quote the exit-free result as a refutation of the *book* — it is a
   refutation of the *entry's* claim to beat a coin flip.
3. **`periods.json` is survivorship-filtered** (§1). Every August total quoted from it
   understates. The graded-ledger figures in this report are computed through
   `bot_pnl_store.fetch_paper_trades` + `golive_readiness.is_phantom_close`, so quarantine
   (47 rows) and phantom closes (13) are excluded, matching what the gate itself grades.
4. **🌾 carry's ledger carries 7 historical two-writer overlaps.** They predate its 31-Jul
   era, so its era grade is clean, but any *pooled* all-time quote of carry inherits them
   and must not be used.
5. **🚀 bezos and 🔮 georgia v3 were born ~1-Sep** — they appear in the census because
   they are living books today, but they took **no August decision** and their first real
   reads fall in October.

---

_Generated by the `crypto-monthly-pnl` scheduled task. Read-only: no trade, lever, env,
config or deploy was touched. Go-live is an explicit operator act. Not financial advice._
