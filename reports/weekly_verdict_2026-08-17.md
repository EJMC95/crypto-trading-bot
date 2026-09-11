# Fleet weekly verdict — week ending Sun 2026-08-16, read Mon 2026-08-17 10:35 AEST

**Headline: no book moved toward the gate on evidence — two bars flipped on the
calendar and none on a measurement. The week's real findings are elsewhere: the
CI guard shipped on Saturday is structurally blind, and the Parliament is
restart-looping while holding the fleet's two most undecidable books.**

Sources: scoreboard issue [#173](https://github.com/EJMC95/crypto-trading-bot/issues/173)
(`fleet-weekly-assessment.yml`, Mon 17-Aug 09:39 AEST, run `31979750293` — **RED, see §0**);
`/bus.json` `golive-readiness` (17-Aug 09:36 AEST), `fleet-allocation` (10:33 AEST),
`impl-shortfall` (10:34 AEST), `fleet-risk` / `fleet-immune` (10:34 / 10:31 AEST);
`/pnl.json` (10:36 AEST). Baseline for week-over-week: issue #154 and
`reports/weekly_verdict_2026-08-10.md`.

Judged, not recomputed. Shadow books are $1,000 paper; not financial advice.
Every action below is an operator act — **nothing here was executed.**

---

## 0. THE RUN IS RED — and it is the guard, not the fleet

> **UPDATE 11:55 AEST — FIXED AND VERIFIED (corrected in place, I12).** The
> operator said *"Fix"*; shipped as `(pn)`, commit `fe9e4d2`. `actions: read`
> added, plus `test_ci_coverage_step_is_granted_the_scope_it_needs` in
> `tests/autonomy/test_code_currency_wired.py` (4 mutations verified RED,
> including the scope-in-a-comment trap and a job-level block that overrides).
> **Verified by output, not by a green run:** the guard now prints
> `audit_ci_coverage: OK — tip has a green run` (run `31986443917`) — the
> settled branch, reachable only by successfully reading run history. An
> earlier dispatch caught the in-flight branch (`31986276990`). The UNKNOWN is
> gone because the guard can now ask its question, not because the error was
> silenced. **Recommendation 1 in the closing section is discharged.**

The `assess` job is green (the scoreboard published normally). The `code-currency`
job failed, **but not on a code-currency verdict**:

```
audit_ci_coverage: UNKNOWN — run history unreadable
##[error]Process completed with exit code 2
```

**There is no BEHIND-OWN. No container is missing its own merged behaviour.**
The two deploy-verification steps that answer that question — `audit_code_currency`
and `audit_live_roster` — both ran and passed. The failure is the third step, the
CI-coverage guard that shipped on Saturday as `(pc)` (`a9e0d68`), and it failed on
its **first ever scheduled run**, for a structural reason:

- The guard calls `gh run list --workflow ...` and, per its own `(kw)` contract,
  returns `None` — the UNKNOWN verdict — when the history cannot be read, then
  exits 2, because *"a guard with no answer must not print OK"* `((mq))`. That
  part is working exactly as designed.
- The workflow declares `permissions: {contents: read, issues: write}`. Declaring
  a `permissions:` block zeroes every scope not listed, so `actions: read` is
  absent and `gh run list` cannot see run history at all.
- `tests.yml:43` already carries a comment recording this exact regime —
  *"`actions: read`, which this workflow's GITHUB\_TOKEN does not have"* — so
  the trap was written down in one workflow and walked into in another.

This is the [[a-guard-has-two-regimes-ci-has-no-database]] shape precisely: the
guard is correct on a laptop and blind in the only place it is gated. It has
**never once been able to answer its question**, and it will redden the weekly
run every Monday until the permission is added.

**Operator fix — one line, `.github/workflows/fleet-weekly-assessment.yml`:**

```
permissions:
  contents: read
  issues: write
  actions: read
```

Not executed: this task is read-only and does not push. Worth pairing with a
mutation check that the guard actually goes green rather than merely stops
erroring — a UNKNOWN that becomes OK because the history is empty would be the
vacuous green its own selftest pins against.

---

## a. REAL MONEY

Both live rows fresh, stamped, and on their own services. **Nothing on either
row needs an operator action this week.**

| Row | Service | Equity | P&L | Closes | Open | Age |
|---|---|---|---|---|---|---|
| 💸 `perps-funding-lighter-lighter` (Farmer) | `trail-blazer-live` | $197.34 | **+$5.82** | 125 | 1 | 30 s |
| 🙏 `freqtrade-avo-maria-lighter` (Avo LIVE) | `tide-rider-lighter-live` | $62.44 | **−$0.35** | **0** | 4 | 286 s |
| **Combined** | | **$259.78** | **+$5.47** | | 5 | |

Stamps: Farmer `build e981e11820fc / build_n 16`; Avo `4d5c491c01ef / build_n 17`.
Different `build_n` is expected — different images, different COPY sets `((fd))`.

**The Farmer lost $0.99 on the week** (+$6.81 Mon 09-Aug → +$5.82 now). It is the
only continuously-live row across both weeks; 🎫 the Taker's live arm left the feed
on 13-Aug, which is the `(ma)` operator slot swap, **not a fault** — the scoreboard's
`OFF-FEED lighter-ticket-taker-lighter` flag is that swap.

**Per-trade, in-era — the gate's own sample, never equity:**

| | n | mean %/trade | t (cluster) | halves | bars |
|---|---|---|---|---|---|
| Farmer **live** | 80 | **+0.061** | 0.42 (0.41) | +2.22 / −1.53 | 3/6 |
| Farmer shadow | 144 | +0.066 | 0.35 (0.33) | +6.64 / −12.44 | 4/6 |
| Avo **LIVE** | **0** | — | — | — | — |
| Avo shadow | 8 | **+1.639** | 2.17 (1.65) | +1.90 / +2.99 | 4/6 |

**The Farmer moved backwards, slightly:** last Monday it read n=72 / +0.079 % /
t=0.50 / halves +2.62 −1.71. Eight more closes cost it 0.018 pp of mean and 0.08
of `t`. Its window bar reaches 30 d around **22-Aug**; its `t` bar does not reach
2.0 at all — the horizon says **undecidable**, `n_req 1904` against 3.25 closes/day
= **~561 days**. All-time it reads better (n=125, +0.298 %, t=1.40, 4/6), and that
sample is 45 closes older than its own policy era.

**The second real-money book has produced zero closed trades in four days live.**
🙏 Avo LIVE holds 4 positions, is down $0.35 on marks, and sits on the decision
docket as `zero_ledger` since 13-Aug. There is nothing to grade, and I am not
going to grade it on its shadow twin — the twin's +1.639 % on n=8 is the best
per-trade number in the fleet and the smallest sample in it. This is what the
memory note already says: Avo went live at n≈10 and 3-of-6 bars, an operator bet
recorded as one.

**Live-vs-shadow gap: no clean read, and the organ says so itself.**
`impl-shortfall` publishes verdict **`xp-contaminated`**, gap **−0.065 pp** over
5 paired coins — the Farmer's shadow twin is the judge's experiment arm, so it is
not a control. On the gate's own in-era samples live is behind shadow by 0.005 pp
(i.e. nothing); all-time live is ahead by 0.042 pp.

**Execution is clean and is the one place live is measurably ahead:** Farmer live
slips **0.42 bps** across 34 orders against shadow's 0.98 bps, with 100 % real
fills (`trades(tx)` 33, `recentTrades-tx` 1). No slip streak.

---

## b. WHICH BOOK MOVED TOWARD THE GATE (doctrine rule 4)

**`ready: []`. Zero of 11 graded books are ready. Two books flipped a bar this
week and BOTH flipped the `window` bar — that is the calendar, not evidence.**

- 🔮 **`freqtrade-georgia-lshadow`: 4/6 → 5/6.** Days 25.6 → **30.1**, so the
  30-day window bar passes. It now fails **exactly one bar**: `t 0.14 < 2`. It is
  the closest book in the fleet to the gate and it is simultaneously **`undecidable`**
  — mean is **+0.016 %/trade** on n=107, so more closes at this rate move `t`
  essentially not at all. This is the [[georgia-short-sleeve-undecidable]] verdict
  landing on the gate: a book one bar away that cannot cross it.
- 💸 **Farmer shadow: 3/6 → 4/6.** Days 30.7 passes. Still fails `t 0.35` and
  halves +6.64/−12.44. Same shape — a clock bar, not an edge bar.

**The only book with a real forward trajectory is unchanged from last week:**
🙏 `freqtrade-avo-maria-lshadow`, the fleet's **only `on_track` book**, ETA
**2026-11-10**, binding bar = **closes** at 0.26/day against the 30-close floor.
Its problem is sample size, which time actually fixes. Nothing else in the fleet
has that property.

**Moved away, with numbers:**

- 🌾 **`perps-funding-carry-lshadow`** — **−$6.15 on the week** and, more to the
  point, **in-era `n` is unchanged at 10**: the fleet's former flagship closed
  **zero trades all week**. Census reads **0 eligible of 225 scanned** (202 below
  the APR gate, 22 thin, 1 waiting). 1/6 bars, in-era mean −0.155 %, t=−4.48,
  horizon `unreachable`. This is the venue stall, not a knob
  ([[carry-stalled-venue-funding-collapsed]]).
- 🧘 **`book-douglas-lshadow`** — **−$26.22 in three days**, the fleet's fastest
  burn, on **2 closes at a mean of −13.24 %/trade** against a declared 1.0×ATR
  stop and a $100 clip. Below min-n so it carries no claim and is not a retire
  call, but it is worth an eye: `(nt)` re-measured this book on 16-Aug and the
  founding number fell from n=575/+$27.01/both-halves-positive to **n=641,
  +$17.38, t=0.50, h1 NEGATIVE**. The edge survives its random-entry null
  (P=0.005); the "both halves positive" go-live bar does not.
- ⚖️ **`perps-funding-spread-lshadow`** — −$2.36 on the week to −$31.06, still
  fleet-worst; h2 reads **−34.23**.
- 🎸 **`band-barnes-lshadow`** — −$7.88 on the week. That is the `(nf)` `xsect`
  sleeve **winding down to flat by its own rebalance**, which is the retirement
  working, not a book failing.

**Fleet totals are not comparable week-over-week and should not be read as a
result.** 18 rows / +$20.17 against 22 rows / +$55.22. Ten rows left the feed
(the 15-Aug red-stop slate, 16-Aug 🧙 Schwager, the 13-Aug live-Taker swap),
carrying **−$25.72** of cumulative P&L off the board; six joined carrying
**−$27.80**. **On the 12 books present in both weeks the change is −$33.02**,
of which 🧘 Douglas, 🎸 Barnes and 🎫 the Taker shadow (−$14.56) are $30.

---

## c. CAPITAL vs CLAIMS (I16)

| class | books | closes | current | organ target | delta |
|---|---|---|---|---|---|
| funding | 8 | 597 | $8,000 | $15,500 | **+$7,500** |
| directional | 10 | 365 | $10,000 | $2,500 | **−$7,500** |

**Three of 18 books carry any claim.** Fifteen books hold $15,000 on a claim of
exactly zero.

| book | n | mean %/trade | claim | current | target | Δ |
|---|---|---|---|---|---|---|
| 🌾 carry | 101 | +0.254 | **0.1492 %** | $1,000 | $10,466 | **+$9,466** |
| 💸 Farmer live | 125 | +0.298 | 0.0248 % | $1,000 | $1,947 | +$947 |
| 💸 Farmer shadow | 182 | +0.256 | 0.0232 % | $1,000 | $1,837 | +$837 |

**Last week's finding on this row is now CLOSED IN CODE, and that is the week's
best piece of news.** The organ still ranks 🌾 carry on `sample: all-time-pooled`
— n=101, of which **91 closes sit before its own declared era boundary**, and
`(nc)` has since measured that ≈$13 of that all-time accrual is **phantom**
(pre-basis-fix over-accrual). In-era the same book reads n=10, mean −0.155 %,
t=−4.48. So the ranking's single largest signal, **+$9,466**, is still computed
on a sample the gate throws out.

**But the actuator no longer acts on it.** `(oy)` now publishes what the
*consumer* does beside what the *ranking* wants, and on carry that reads:

```
claim_era: null   expansion_gated: true   scale_effective: 1.0
```

That is the exact risk I flagged on 13-Aug — *"the moment carry's venue gate
admits again, it opens at 4× on a claim its own era rejects"* — shipped shut.
Carry now sizes new entries at **×1.0**, not ×4.0, and ⚖️ Counterweight is
correctly held at **×0.25**. Real money never reads the organ at all
(AST-pinned).

**What remains is a reporting gap, not an exposure gap:** `target_usd` and
`scale_effective` still tell different stories about the same book. `(oy)`
publishing both is the right fix; a reader who quotes only `target_usd` will
still overstate. No operator action.

Also on this table: `zero_close_books` includes **`freqtrade-avo-maria-lighter`**
— a real-money row with no ledger, which is why §a grades it as ungradeable
rather than as flat.

---

## d. KEEP-OR-RETIRE PRESSURE (I17)

Sixteen books on the decision docket, `docket_valid: true`, threshold 7.0 days.
**Four cases, and only one of them is a call I would put in front of you today.**

**1. 🏛️ The Parliament — the strongest new I17 case of the week, and it comes
with an infrastructure fault.**

| book | n | mean %/trade | t | horizon |
|---|---|---|---|---|
| `pm-albanese-lshadow` | 25 | +0.281 | 0.40 | undecidable — **~628 d** to `t`=2 |
| `pm-turnbull-lshadow` | 20 | +0.022 | 0.07 | undecidable — **~28,389 d** |

Both are beyond any horizon the fleet can act on, and turnbull's number is not a
near-miss — it is a statement that the rule has no measurable effect. These are
the **only two books left** in a six-layer process after the 15-Aug slate retired
four of six.

And 🛡️ the immune organ has the supervisor flagged **sick**:

> `parliament`: 5 RESTART(s) in 24h, from the publisher's own durable counter
> (`restarts`, now 12). **The key stays FRESH on every boot, so no age check can
> see this**, and in-process state is lost each time.

That is an I1/I13 shape caught by exactly the detector built for it. A six-layer
asyncio process — data, 10 scanners, a 5-model prequential ML ensemble, six
tuners, Howard's brain — losing in-process state five times a day, to run two
books that between them cannot be decided this century. **The keep-or-retire
question here is about the process, not just the rows.** Operator decision;
`PARLIAMENT_ENABLED=0` idles the whole thing, or `PM_<NAME>_RETIRED_OVERRIDE`
handles the rows individually.

**2. 🎯 `lighter-perp-sniper-lshadow` — DEFERRED, and this is a reason, not a snooze.**
It reads n=29, mean −0.498 %, t=−0.79, `unreachable`, stuck ≥10.5 d, −$3.08, 0 open,
and I named it last week. **Do not retire it on that verdict.** `(pf)`/`(pk)`, shipped
16-Aug, found that this book's `unreachable` verdict is computed on instruments it
stopped trading four days earlier — the `(lk)` crypto-only screen — and that the
stale verdict *"can never age out"*. The published number describes a book that no
longer exists. Re-decide once the class screen publishes and the verdict recomputes
on the screened sample. Retiring on a verdict the repo has just declared stale would
be the [[verify-inherited-claims]] failure.

**3. ⚖️ `perps-funding-spread-lshadow` — HOLD to ~28-Aug.** Worst book in the fleet
(−$31.06; n=91, mean −1.734 %, t=−1.87, cluster t=−1.23, halves +3.06/−34.23,
`unreachable`, 10 open). It is **pre-registered for the operator at ~28-Aug** by
`(jg)`'s own revert criterion. Eleven days out. Deciding it early is the `(hs)`/`(ia)`
trap in reverse, and the allocation consumer already has it at ×0.25.

**4. The four zero-ledger books — none is a retire call yet, one deserves naming.**
📐 Grimes, 🏦 Kiyosaki, 🧮 Hull and 🙏 Avo LIVE all have zero closes, and all four
were born within the last four days with declared slow clocks (🧮 Hull's birth entry
declares ~5 months to 30 closes). Give them their windows.

📐 **Grimes is the one to watch**, because its own scorecard has now confirmed the
16-Aug `(oe)` diagnosis. Last week the gate had **opened** (keltner n=99, t=+0.53,
`open: true`). After `(om)` fixed the gate to grade the founding study's fixed 18
coins, all three setups are **closed again**:

| setup | n | t | net | open |
|---|---|---|---|---|
| keltner | 129 | **−0.37** | −$25.15 | false |
| failtest | 369 | −1.43 | −$95.70 | false |
| pullback | 136 | −0.93 | −$63.94 | false |

The opening was universe churn, not edge — exactly as `(oe)` measured — and the fix
took it back. `gate_drift` reads `ungraded: []`, so the book cannot enter a coin its
gate never tested. It is working as designed and trading nothing. **I17 is declared
in its own birth entry: a gate that stays shut long enough is a keep-or-retire call,
never a bar-lowering session.** Not yet — 4 days old.

---

## e. ONE EXPANSION CANDIDATE (I19) — a refusal, with the numbers

**No widening this week.** Three candidates the week's evidence could plausibly
support; all three refused, each for a different measured reason.

**Candidate 1 — 🧮 Hull, raise `max_positions` (4).** This is the fleet's
best-evidenced new book and the **only cohort book whose founding number survived
re-measurement** `((ny), 16-Aug)`: n=50, +$6.69, **t=+3.92**, both halves positive
(+$3.17/+$3.53), block bootstrap **P(mean≤0) = 0.000**, cluster-robust t=3.92 with
n_eff 50, and concentration that is the mirror of 🧙 Schwager's — the best trade is
16 % of the total and **dropping it raises `t` to 4.01**. Its binding bar is
**closes** (~6.0/30 d, ~5 months to 30). More positions would mean more closes.

**REFUSED: the cap is not the binding constraint.** Its live census reads
**held 2 of 4, `eligible: 0`** of 225 scanned (117 below band, 23 above band,
80 thin). Raising a cap that is not binding buys exactly zero closes — I18's
"binding constraint must be a reachable lever" in its plainest form. Hull needs
time, not capacity, and its birth entry already said so.

**Candidate 2 — 🛢️ Garrett, raise capacity.** Here the cap genuinely **is**
binding: census reads `eligible: 18, held: 6, free_slots: 0`. A capacity-bound
book with 18 queued candidates is the textbook widening.

**REFUSED anyway, on the book's own record:** n=10, mean **−0.245 %/trade**,
−$1.27, `below-min-n` so no claim, docket verdict **`unreachable`** since 15-Aug.
`(hs)`/I7 is explicit and was written after this exact mistake was made on
⚖️ Counterweight: a capacity widening must read the book's P&L and **fail closed
in the widening direction**. Widening a losing book's capacity is buying more of
a measured negative.

**Candidate 3 — 📐 Grimes, lower the `t ≥ 0.5` gate bar.** **REFUSED** — this is
the bar-lowering trap `(om)` already measured and rejected four days ago. Its
three rejected alternatives were stable only because each needed twice the edge
to open; `fixed` was shipped precisely because it kept the bar's sensitivity.

**A refusal with evidence satisfies the growth rule.** What the week actually
supports is not a lever at all: 🙏 Avo shadow is the fleet's only `on_track` book
and its binding bar is closes at 0.26/day. Nothing in the growth rail moves that
number, and its live twin is real money, so its policy era is not something to
disturb for throughput.

---

## Not a breach: the scoreboard's exposure flag

> **UPDATE 15:10 AEST — FIXED (corrected in place, I12).** Shipped as `(pp)`,
> commit `1c1e3af`. The flag now reads `fleet_risk`'s own pair
> (`long_positions` vs `long_budget` — the pair the veto uses, not
> `exposure.long_n`, which is a different population by design), checks the
> payload's age against its own `ttl_sec` first, and publishes a visible
> `EXPOSURE UNKNOWN` when the bus is dark, unparseable or stale. The hardcoded
> `EXPOSURE_BUDGET` copy is deleted — it duplicated a lever the growth rail can
> move. Logic extracted to `scripts/weekly_exposure_flag.py` (20-case selftest)
> because the old version lived in a YAML heredoc where no branch was testable.
> **Verified live:** a re-run produced a scoreboard reading `45 open positions
> (all books, all sides)` with **no breach flag**, against a real long count of
> 14/20 — and a planted 25/20 still fires. Wiring pinned, 4 mutations red.

`EXPOSURE BREACH — 40 open vs budget 20` is a **measurement mismatch**, and it
fired the same way last week (58 vs 20). The enforced long budget reads, on the
live bus:

```
light green · mode enforce · clip_scale 1.0
long_n 11 / 20 · short_n 2 · sym_over 0 · long_max_share 0.18 (ADA) · long_effective_n 8.1
```

**Nothing is over budget.** The scoreboard counts every open position — including
delta-neutral funding legs, of which ⚖️ Counterweight alone holds 10 (= 5 pairs) —
against a long-only budget. Worth one line in the flag logic so a real breach is
still legible when it happens; a flag that is false two weeks running is one the
reader learns to ignore `((gl))`.

Elsewhere the organs are healthy: 🫁 respiration SpO₂ **1.0**, no quarantined
levers, one sick organ (the Parliament, §d).

---

## What I would put in front of you, in order

1. ~~**Add `actions: read`** to `fleet-weekly-assessment.yml`~~ — **DONE 11:55 AEST,
   `(pn)` / `fe9e4d2`**, with an executable pin and 4 verified mutations. Guard
   now returns `OK — tip has a green run` (§0).
2. **Decide the Parliament** — two books needing 628 and 28,389 days, inside a
   supervisor restarting 5×/day with its freshness contract unable to see it (§d.1).
3. **Hold ⚖️ Counterweight to ~28-Aug** (pre-registered) and **defer 🎯 the sniper**
   until its verdict recomputes on the screened sample (§d.2–3).
4. **Nothing on real money.** Both rows fresh, stamped, execution clean at
   0.42 bps, and the Farmer's −$0.99 week is inside its own noise (§a).

**Forward metric, stated plainly: no book moved toward the gate on evidence this
week.** Two window bars flipped on the calendar; the two books that flipped them
are `undecidable`. One book — 🙏 Avo shadow — remains `on_track` for 10-Nov. The
week's genuine progress was defensive and real: `(oy)` shut the carry ×4 sizing
path, `(om)` closed a gate that had opened on universe churn, and `(pf)`/`(pk)`
caught two retirement verdicts computed on instruments their books no longer trade.
