# Fleet weekly verdict — week ending Sun 2026-08-23, read Wed 2026-08-26 07:15 AEST

**Headline: the biggest week of real-money change since go-live — the Farmer's
live arm retired, 🔮 georgia and 👩 mum took live sub-accounts, and the live
fleet is now three books, $887.84 of equity, −$13.10. Against that, ZERO books
are ready, zero books hold an era-scoped claim, and the fleet's closest book to
the gate got FURTHER from it while nearly doubling its closes — which is the
finding of the week: georgia's problem is her mean, and more closes are
measurably not fixing it.**

Sources: scoreboard issue [#216](https://github.com/EJMC95/crypto-trading-bot/issues/216)
(`fleet-weekly-assessment.yml`, Mon 24-Aug 09:40 AEST, run `32674318505` — **RED, see §0**);
`/bus.json` `golive-readiness` (26-Aug 06:50 AEST), `fleet-allocation` (06:47),
`impl-shortfall` (06:48), `xp-judge` (06:43), `fleet-risk` (06:57), `fleet-immune` (06:59);
`/pnl.json` (07:01 AEST); `HANDOFF.md` (26-Aug 00:29 AEST). Week-over-week baseline:
issue [#173](https://github.com/EJMC95/crypto-trading-bot/issues/173) and
`reports/weekly_verdict_2026-08-17.md`.

**This run is late** — it is the Monday job firing Wednesday. The scoreboard it
judges is Sunday 23-Aug 23:40 UTC; the bus and feed readings are current
(Wed 26-Aug). Where the two disagree the report says so, because two of the
disagreements are real findings, not lag.

Judged, not recomputed. Shadow books are $1,000 paper; not financial advice.
Every action below is an operator act — **nothing here was executed.**

---

## 0. THE RUN IS RED — and it is already fixed at HEAD

The `assess` and `ceiling` jobs are green. `code-currency` failed on a genuine
**BEHIND-OWN**, the one class that is supposed to redden the build:

```
##[error] svc=nav-cook-shadow is running stale code of its own —
          2 of 36 commit(s) in the gap change this bot's own entry file
          [ROW STALE 73.3h — the verdict describes its LAST publish,
           not a running process (I1)]
```

**Both halves were real and both are now discharged.** 🧭 Captain Cook was
36 commits behind on its own entry file *and* its row had not been written for
**73.3 hours** — the I1 shape exactly: the verdict described a corpse's last
words. `(ss)` (21-Aug) had already found the mechanism — *"a reporting block may
never interrupt a trading loop — nav-cook was dark 11.5h"* — and `(th)` (25-Aug)
found the rest: **nav-cook was MUTE, not dead.**

**Verified by re-running the instrument against the live feed just now**, not by
a green run:

```
nav-cook-lshadow   CURRENT   0   2db5b3ab4 matches HEAD
audit_code_currency: OK — every stamped container is CURRENT, deliberately
DEFERRED behind its marker gate, or behind only on shared modules.   (exit 0)
```

The row is fresh (age 110 s), its stamp moved `f45a3a15c11f` → `705409a6afa3`,
and its `caps` now publish `confirm_s: 630` beside `study_confirm_s: 600` — the
`(sa)` duration fix, visible on the row. All three live rows read `DEFERRED 8`
behind their marker gate, which is the design.

**No operator action. The next scheduled run should go green on its own.** Worth
one eye: this is the first time the weekly RED was a true BEHIND-OWN rather than
the guard's own blindness (`(pn)`, last week), so the guard is now earning its
place — do not soften it.

---

## a. REAL MONEY

**The live fleet tripled in size and changed identity this week.**

| Live row | Service | Equity | Bot P&L | Closes | W/L | Status |
|---|---|---|---|---|---|---|
| 🔮 `freqtrade-georgia-lighter` | `trail-blazer-live` | $266.08 | **−$20.70** | 51 | 24/27 | **HALTED** |
| 🙏 `freqtrade-avo-maria-lighter` | `tide-rider-lighter-live` | $321.76 | **+$7.60** | 13 | 3/10 | online, 3 open |
| 👩 `freqtrade-mum-lighter` | `mum-live` | $300.00 | $0.00 | **0** | — | online, flat |
| | | **$887.84** | **−$13.10** | | | |

### a1. 💸 The Funding Farmer's LIVE ARM IS RETIRED — the fleet's oldest real-money book is gone

`perps-funding-lighter-lighter` is **OFF-FEED**, and that is a decision, not a
fault. Retired 22-Aug `(st–ta)`; 🔮 georgia took the sub-account in place. The
judge's own `last_eval` carries the reason, and it is the horizon on **both**
arms:

> live n=91, mean −0.160 %/trade, t=−0.88, halves +2.51 / −7.65
> shadow n=161, mean −0.195 %/trade, t=−0.95, halves +5.71 / −18.32

That is `unreachable` at the fleet's own grader on the real-money arm *and* its
control. The shadow twin keeps trading (`perps-funding-lighter-lshadow`, now
3/6 bars, n=170, mean **−0.333 %**, t=−1.58). **This is I17 executed on real
money, and it is the right call** — but note what it costs: the Farmer was the
judge's only funding pair, so `xp-judge` now reads `phase: "stood_down"` and the
`live.funding.*` promotion lane has no candidate and no arm. The fleet's oldest
designed path from shadow to real money is idle.

### a2. 🔮 Georgia halted on her third day live — and the halt worked exactly as built

She went live 22-Aug at **5× gross**. Her whole live loss is **one day**:
lifetime −$20.70, `today_pnl` **−$20.84** — meaning she was ~+$0.14 before
25-Aug. The daily-loss rail fired:

```
halted: true   halt: {abs_usd: 20.0, binding: "abs", daily_loss_frac: 0.1}
last_close: LINK  −$6.64  reason "long-range-on_daily_loss"  12:08 UTC 25-Aug
```

`binding: "abs"` is the $20 absolute cap beating the 10 %-of-equity cap ($26.61)
— the rail chose the tighter of the two and stopped a −7.8 % day at −7.8 %.
**This is the `(th)` halt-geometry instrument working on its first real test.**

**Two things to watch, neither an emergency:**
- Her live row is **STALE** on the feed (age 283 s against a 180 s threshold).
  A halted book publishes less often by design (`(ta)`: *"a retired arm is not a
  daily-loss halt — don't say so hourly forever"*), so this is expected — but it
  means the halted state and the stale state are visually identical, which is
  the I1 trap in miniature. Worth one look that she resumes on the UTC rollover.
- **A restart wipes a memory-only halt** ([[lighter-flatten-silent-halt-redeploy-incident]]).
  Do not dispatch a live deploy while she is halted without checking that first.

### a3. 👩 Mum is live, flat, and carries the highest gross in the fleet

Live 25-Aug `(te)` on her own sub-account, $300, **zero closes**. What deserves
an eye is her geometry, which her own row publishes honestly:

```
gross_x: 9.5   (max 10.0)     clip_usd: $712.50    max_open: 4
halt: {abs_usd: 30.0, binding: "pct", daily_loss_frac: 0.1,
       basket_move_at_full_gross_pct: 0.0105}
```

**At full occupancy a 1.05 % adverse basket move hits her daily halt.** That is
not a defect — it is the published consequence of 9.5× on a $300 book, and the
fact that the row states it is the `(th)` instrument doing its job. But she is
also the fleet's only book carrying a **live control arm** (`extra.control`,
n=0), and the `(qu)` finding stands: her `rsi<25` dose-response has **decayed
through zero** (+4.97 → +2.05 → −0.31 → −0.41). She is a live, 9.5×-gross bet on
a hypothesis her own study calls hypothesis-grade. That was an explicit operator
decision and it is on the record; the control arm is what will settle it.

### a4. Live-vs-shadow per-trade gap: **live-slipping**, and it is NOT fill quality

`impl-shortfall` verdict **`live-slipping`**, `gap_pp` **−0.662** across 4 paired
coins — and the sign is **unanimous**:

| Coin | closes | live %/trade | shadow %/trade | gap pp |
|---|---|---|---|---|
| BTC | 2 | −2.348 | −2.110 | −0.239 |
| ETH | 3 | −2.539 | −1.908 | −0.631 |
| SOL | 3 | −4.976 | −3.902 | −1.074 |
| XAU | 1 | −6.147 | −5.780 | −0.367 |

**The cause is not the venue.** Order slip measures **0.29 bps live** against
**0.92 bps shadow** over 18 real fills (`trades(tx)` 18/18, 100 % real) — the
live arm fills *better* than its paper twin. So a −0.66 pp per-trade gap is being
opened by something other than execution: sizing, timing, or the leverage the
shadow arm does not run. n=4 paired coins is thin and I am not calling it yet,
but **the unanimity across four coins on a metric whose obvious cause is
measurably absent is worth one query**, and it is the [[realised-vs-graded-gap-means-execution]]
note pointing the other way for once.

### a5. Two flags on the real-money surface

- 🛡️ **`fleet_immune` has exactly one sick organ, and it is a live book:**
  `freqtrade-avo-maria-lighter: headroom refused: liq_unpriced (gap None
  stop-widths)`. Her `leverage.headroom` reads `ok: false`. She is at 5×
  gross with 3 open positions (QQQ/TRX/NVDA, `n_eff` 1.862, `basket_rho` 0.306)
  and the liquidation-gap check **cannot price itself**. That is fail-closed
  behaviour reported honestly, not a breach — but a real-money book running
  leverage with a blind liquidation check is the one on this list I would look
  at first.
- 🎫 **The taker's live order path is budget-exhausted:** of 4 `taker_live`
  orders, 3 read `skipped:budget(… reserve 6.0) after api-error:trades:
  VenueError: lighter tx budget exhausted; skipping`. The taker's live arm was
  retired 13-Aug, so this should be inert; something is still attempting live
  orders on it. Low stakes, but it is an unexplained live-path attempt.

### a6. **The live P&L basis CHANGED mid-week — do not compare the two live rows to the scoreboard**

`(td)` (25-Aug) attested Eamon's manual trades out of the bots' P&L. Every live
row now publishes `manual_pnl_usd`, and it is large:

| Row | account change | manual (Eamon's own) | **bot** |
|---|---|---|---|
| 🙏 avo live | −$58.80 | −$66.40 | **+$7.60** |
| 🔮 georgia live | −$47.35 | −$26.64 | **−$20.70** |
| 👩 mum live | $0.00 | $0.00 | $0.00 |
| | −$106.15 | **−$93.04** | **−$13.10** |

The 23-Aug scoreboard predates this and reads avo **−$24.47** and georgia
**−$40.70** on the OLD pooled basis. **Those two figures are not comparable to
anything after 25-Aug**, and the apparent +$32 and +$20 "recoveries" are an
attribution fix, not trading. This is a policy-era boundary on a reporting
basis — worth stamping as one so next week's diff does not read it as
performance.

---

## b. WHICH BOOK MOVED TOWARD THE GATE (doctrine rule 4)

**`ready: []`. Zero of 14 graded books are ready — unchanged for the fifth
straight week.** Two books hold `on_track`: 🎫 the taker and 🙏 avo shadow.

### The one book that genuinely moved — and it moved BACKWARDS on the bar that matters

🔮 **`freqtrade-georgia-lshadow` is still 5/6, failing only `t`** — and this is
the week's central finding:

| | 17-Aug | 26-Aug | Δ |
|---|---|---|---|
| n | 107 | **195** | **+88 closes** |
| mean %/trade | +0.016 | **+0.102** | +0.086 pp |
| **t** | 0.14 | **0.60** | +0.46 |

On its face that is progress — `(sv)` freed her rate limiter (the 2/h throttle
was cutting her best trades, +0.633 pp in favour of the entry it refused) and
her close rate roughly doubled. **But price it.** At n=195 and t=0.60, reaching
t=2.0 needs

> n_req = 195 × (2.0 / 0.60)² ≈ **2,167 closes** — **1,972 more**

at her measured ~11.1 closes/day, that is **~178 days ≈ 6 months, ~late
February 2027** — and only if the mean holds. Her own horizon verdict is
**`undecidable`**, and the docket has carried her since 22-Aug for exactly that.

**And there is a discrepancy that needs one query, not a guess.** `HANDOFF.md`
(generated 26-Aug 00:29 AEST) records georgia at **t = 1.11**; `/bus.json`
`golive-readiness` six hours later (06:50 AEST) reads **t = 0.60**. Two published
numbers for the fleet's closest book to the gate, half a day apart, differing by
almost a factor of two. Either they are different statistics (iid vs cluster) or
her `t` genuinely halved overnight. **I am not resolving it from here** — but on
the one book that is 5/6 bars, that is the number the next session should
reconcile first.

### Bars that flipped, all of them the wrong way

- 🙏 **`freqtrade-avo-maria-lshadow`: 4/6 → 3/6.** It **lost the `t` bar**:
  n 8 → 17, mean +1.639 % → **+0.722 %**, t 2.17 → **1.27**. Last week's verdict
  called the n=8 reading thin and said the fleet was *"going to grade it on its
  shadow twin"*; nine more closes halved the mean. **This is the small-sample
  regression arriving on schedule**, and it matters because avo's LIVE arm was
  the operator bet placed on that number. She remains `on_track` (ETA
  2026-11-10, binding bar = closes) — the one book whose problem time actually
  fixes.
- 💸 **Farmer shadow: 4/6 → 3/6.** It **lost the `mean` bar**: +0.066 % →
  **−0.333 %**, t 0.35 → −1.58, halves +4.15 / −18.87. Its live arm was retired
  the same week. The two facts agree.
- 🎫 **`lighter-ticket-taker-lshadow` — the week's biggest earner, and the
  fleet's best forward case.** 3/6, n=117 in-era, mean **+0.606 %**, t=1.12,
  `on_track`. **+$59.60 on the week** (+$7.25 → +$66.85), the largest single
  move in the fleet by a factor of four. Its failing bars are `window` (25.3 d
  of 30), `t`, and **`halves −2.14 / +37.56`** — see §e, because that halves
  split is the whole story.

### Moved away, with numbers

- 🛢️ **`band-garrett-lshadow`: −$28.15 on the week** (−$1.18 → −$29.33), the
  fleet's fastest burn. n=53, mean **−1.762 %/trade**, **t=−2.48**, `unreachable`.
- 🪁 **`band-kelly-lshadow`: −$8.86** in its first full week. **225 closes in
  6.5 days**, mean −0.142 %, t=−0.86, already `unreachable` on the docket since
  21-Aug. Its founding claim was +0.397 %/trade corrected (`(qw)`/`(rc)`); it is
  running at −0.142 %. Six days is not a verdict, but the corrected claim's
  95 % CI does not obviously contain this.
- ⚖️ **`perps-funding-spread-lshadow`: −$8.80 to −$39.86**, fleet-worst. n=117,
  mean −1.613 %, t=−1.66, halves −8.26 / −28.86.
- 🧘 **`book-douglas-lshadow`: −$8.21 to −$34.38.** n=60, mean −0.721 %,
  **t=−2.50**.
- 🌾 **`perps-funding-carry-lshadow`: −$0.92, and still structurally stalled** —
  census reads **`eligible: 0` of 228 scanned** (202 cold, 5 thin, 2 waiting),
  the same venue stall as last week. In-era it is n=11, mean −0.169 %,
  **t=−4.96**, 1/6 bars. **One anomaly worth an eye: it publishes `held: 19`
  against `max_positions: 14`.** I am not calling that a cap breach — restored
  positions and depth-admits can explain it — but a book holding 5 more than its
  own declared cap should be reconciled, and the same book is the one the
  allocation organ wants to 6.5× (§c).

**Fleet total: $+20.15 → $−11.07, i.e. −$31.22 on the roster** (−$36.31 across
continuing and new books; the $5.09 difference is exactly 🎸 Barnes and the live
Farmer leaving the feed — the arithmetic reconciles).

---

## c. CAPITAL vs CLAIMS (I16)

`fleet-allocation` wants **$1,765 moved from directional to funding**
(directional $14,000 → $12,235.20 across 14 books; funding $6,000 → $7,764.81
across 6). That is the smallest class-level disagreement in weeks and it is not
the story.

**The story is one field:**

```
funding:     books 6,  closes 500,  n_with_claim 1,  n_with_era_claim 0
directional: books 14, closes 918,  n_with_claim 2,  n_with_era_claim 0
```

**Zero books in the entire fleet hold an era-scoped claim.** All three claims the
organ ranks are POOLED all-time, and on the top-ranked pair the pooled and
in-era readings disagree in sign:

| Book | claim (pooled) | pooled n / mean | **in-era** n / mean / t | current → target |
|---|---|---|---|---|
| 🙏 avo shadow | 0.183 % | 20 / +0.827 % | 17 / +0.722 % / **1.27** | $1,000 → **$8,176** |
| 🌾 carry | 0.145 % | 102 / +0.249 % | **11 / −0.169 % / −4.96** | $1,000 → **$6,515** |
| 🎫 taker | 0.019 % | 213 / +0.451 % | 117 / +0.606 % / 1.12 | $1,000 → $1,059 |

**The disagreement, in dollars: the organ wants +$5,515 on 🌾 carry — a 6.5×
scale-up — on a claim computed over a sample the fleet's own go-live grader
refuses.** Carry's era boundary excludes 91 of its 102 closes, and the memory
note is explicit that ≈$13 of its all-time accrual is phantom
([[carry-stalled-venue-funding-collapsed]]). Ranked on the sample the gate
accepts, carry's claim is not 14.45 % — it is negative at t=−4.96.

**This is not academic, because carry is one of three books that actually
CONSUME the organ.** Real money never reads it (AST-pinned), but 🌾 carry,
⚖️ Counterweight and 💸 Farmer-shadow size new entries by
`fleet_bus.allocation_scale`. `HANDOFF.md`'s `allocation-organ-4x-on-carry` card
records the consequence already measured: the organ sits **at its 4.0 ceiling on
carry right now** (`delta_usd: +13,500`), and carry runs 12–14 slots × $300 —
**$14,400 of gross on a $1,000 book from the allocation organ alone**, before the
brain says anything.

**Recommendation (operator, I16 — a capital-policy call, not a session one):**
the cheap fix is not to move the clamp but to make the organ rank on the era-
scoped claim it already computes (`claim_era`, currently 0.0 on every book) and
fall back to flat when none exists — which is exactly what I16 says it should do
with no measured claim anywhere. That would take carry's scale from 4.0 to 1.0
today. It is a one-field change to a publisher, it moves no real money, and it
would stop three shadow books sizing off a sample the gate rejects.

---

## d. KEEP-OR-RETIRE PRESSURE (I17)

The docket carries **17 books**. Two are measured losers with significance —
those are the anti-growth ones:

| Book | n | mean %/trade | **t** | verdict | on docket | week | frees |
|---|---|---|---|---|---|---|---|
| 🛢️ `band-garrett-lshadow` | 53 | **−1.762** | **−2.48** | unreachable | since 15-Aug | **−$28.15** | $1,000 + a funding cell |
| 🧘 `book-douglas-lshadow` | 60 | **−0.721** | **−2.50** | unreachable | since 19-Aug | −$8.21 | $1,000 |
| ⚖️ `perps-funding-spread-lshadow` | 117 | −1.613 | −1.66 | unreachable | since 6-Aug | −$8.80 | $1,000 + 10 open legs |
| 🪁 `band-kelly-lshadow` | 225 | −0.142 | −0.86 | unreachable | since 21-Aug | −$8.86 | — (6 days old) |
| 🧭 `nav-cook-lshadow` | 37 | −0.194 | −1.42 | unreachable | since 21-Aug | — | — (just un-muted) |
| 🎯 `lighter-perp-sniper-lshadow` | 36 | −0.085 | −0.13 | unreachable | **since 6-Aug (19.3 d)** | +$2.29 | $1,000 |
| 🏛️ `pm-albanese-lshadow` | 25 | +0.281 | 0.40 | undecidable (**~844 d**) | since 7-Aug | $0.00 | $1,000 |
| 🏛️ `pm-turnbull-lshadow` | 23 | +0.077 | 0.26 | undecidable | since 25-Aug | +$0.17 | $1,000 |
| 🏦 `book-kiyosaki-lshadow` | **0** | — | — | zero_ledger (12.6 d) | since 13-Aug | +$1.16 | $1,000 |
| 📐 `book-grimes-lshadow` | **0** | — | — | zero_ledger (11.9 d) | since 13-Aug | $0.00 | $1,000 |
| 🧮 `book-hull-lshadow` | **0** | — | — | zero_ledger (11.9 d) | since 13-Aug | +$0.73 | $1,000 |

**The two calls I would put in front of Eamon this week, in order:**

1. **🛢️ Garrett.** `t=−2.48` on n=53 with mean −1.762 %/trade, and it burned
   **$28.15 in seven days** — the fleet's fastest loss, on the book whose whole
   thesis was the thin-tier claim `[1e5, 2e6)`. It is measured negative *with
   significance* and it holds a funding cell. This is the (mr)/(nf) shape and it
   is ripe.
   `BAND_GARRETT_RETIRED_OVERRIDE` does not exist yet — Garrett is a **variant
   instance** (`FUNDING_VARIANT=band-garrett`), so retiring it is the row-scoped
   pattern plus stopping `band-garrett-shadow`, not a `sys.exit`.
2. **⚖️ Counterweight — the pre-registered decision date is NOW.** `(jg)` pinned
   the keep-or-retire call at **~28-Aug**, which is this Friday. It is
   fleet-worst at −$39.86, halves −8.26 / −28.86, and the docket has held it
   since 6-Aug. **Deciding it early was the trap; deciding it late is just
   drift.** The pre-registration exists precisely so this is a date, not a mood.

**Three zero-ledger books cross 13 days this week** (🏦 Kiyosaki, 📐 Grimes,
🧮 Hull — the BOOKS cohort). None has closed a single trade. Hull's own birth
declaration said ~4–6 closes/30 d, so it is inside its own stated clock and
should be left alone; Grimes's gate is deliberately shut by construction and
`(om)` fixed its universe drift 16-Aug. **Kiyosaki is the one without that
excuse** — it holds 6 open positions and has closed nothing in 12.6 days on a
cell that its sibling 🌾 carry reports as `eligible: 0`. That is I20's
one-bet-held-twice on a supply that is currently empty.

**🎯 the Perp Sniper has been on the docket 19.3 days**, the longest of any
book, on `t=−0.13` and n=36. `(qi)` already refuted its founding listing thesis
outright (TP hit 2 of 73; crypto births zero since May). It is not losing money
(+$2.29 this week) — it is simply not answering, which is exactly the I17 class.

---

## e. ONE EXPANSION CANDIDATE (I19)

**REFUSED, with the numbers — and the refusal names the two widenings that
already shipped and should now be left alone to accrue.**

The week's best-supported book is unambiguous: 🎫 **the Ticket Taker**, +$59.60,
`on_track`, n=117 in-era, mean **+0.606 %/trade**, t=1.12. Its arithmetic is the
only encouraging one in the fleet:

> n_req = 117 × (2.0 / 1.12)² ≈ **373 closes** — 256 more, at ~4.6/day ≈
> **56 days, ~late October 2026.**

**And its widening already shipped this week**: `(td)` doubled its budget under a
guard-derived ceiling. **So the correct action is to widen nothing further and
let the sample run**, for a reason that is mechanical rather than cautious — a
capacity change is `(hc)` ordinary tuning and does **not** reset the policy era,
so the (td) budget change is accruing a *clean single-policy sample right now*.
A second widening inside the same window buys throughput and costs the very
thing the book is 56 days from earning.

**The one number that must be watched instead of widened:** its `halves` bar
reads **−2.14 / +37.56**. A book whose second half is 17× its first is a book
whose mean lives in a tail, and that is the [[undecidable-by-tail-not-by-rate]]
signature — 🧙 Schwager's exact cause of death, where `t` could not resolve a
rule at 298 closes because 3 trades were 112 % of the P&L. **Run the top-3-drop
test on the taker's in-era ledger before anyone promises late-October**, because
if the taker is tail-driven then 373 closes is a number about a distribution that
cannot support it. That test is cheap, read-only, and it is the single most
valuable query available this week.

**Explicitly refused, with the price:**

- 🔮 **georgia throughput (`entry_rank` 3 → 4).** Pre-registered in
  `HANDOFF.md`'s `ceiling-slots-georgia` card as *"take 3 → 4 only if it holds"*.
  **The week's evidence argues against it.** She added 88 closes and her `t` went
  to 0.60, implying ~1,972 more closes ≈ 6 months (§b). **Raising n is measurably
  not lifting this book** — her binding constraint is the mean, not the count,
  and `(sv)` also measured that full occupancy is unreachable by construction
  (mean hold 2.6 h ⇒ five slots need ~46 opens/day against a supply of 40.9).
  Widening throughput here is turnover bought at a mean that is not paying for
  it — the [[only-growth-no-step-backs]] shape in a growth costume. **Reconcile
  the t=1.11 / t=0.60 discrepancy first; it is free and it may change the
  answer.**
- 🌾 **carry's allocation scale (4.0×).** Refused on §c's grounds: the claim
  behind it is pooled over a sample the gate refuses, and in-era the book reads
  t=−4.96 on n=11 with `eligible: 0` of 228 scanned. There is nothing to scale
  into.

---

## Carried into next week (I11)

1. **⚖️ Counterweight's pre-registered keep-or-retire date lands ~28-Aug (Fri).**
   Operator decision. It is the only dated item in the fleet.
2. **🛢️ Garrett is the ripest retirement** — `t=−2.48`, −$28.15/week. Operator.
3. **Reconcile 🔮 georgia's `t`** (HANDOFF 1.11 vs bus 0.60, six hours apart) —
   the fleet's closest book to the gate, one query.
4. **Run the top-3-drop test on 🎫 the taker's in-era ledger** — before its
   `on_track` ETA is quoted anywhere.
5. **🙏 avo live: `headroom refused: liq_unpriced`** — the only sick organ, on a
   real-money book running 5× leverage.
6. **Make `fleet_allocation` rank on `claim_era`** — three shadow books currently
   size off a sample the go-live gate rejects.
7. **The live P&L basis changed 25-Aug `(td)`.** Stamp it as an era boundary so
   next week's scoreboard diff does not read the attestation as performance.

**The forward metric, stated plainly: no book moved closer to the gate on
evidence this week. Two bars flipped and both flipped backwards (🙏 avo lost `t`,
💸 Farmer lost `mean`). The fleet's most consequential change was a
retirement — 💸 the Farmer's live arm — and it was the right one.** Three books
now hold real money on a combined $887.84; one of them has never traded, one is
halted, and the third is the only book in the fleet whose problem is sample size
rather than edge.
