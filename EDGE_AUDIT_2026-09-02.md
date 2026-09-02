# EDGE AUDIT — does any book in this fleet have a real edge?

**Date:** 2026-09-02 (Sydney evening, 02-Sep ~12:00 AEST) · **Instrument:** `scripts/edge_audit.py` ·
**Sample:** the paper ledger (`/trades.json?source=paper`, 3,789 rows, 42 books) scoped to the
18 LIVING books through the fleet's own grader (`golive_readiness.era_rows`), phantom-filtered
(`is_phantom_close`), quarantine-filtered (`bot_pnl_store.is_quarantined`) — and **calibrated**:
every book's `n`, `mean` and `t` reproduce the live `golive-readiness` grade published at
01:12:39Z exactly, or the instrument refuses to report. It did not refuse.

**Eamon's ask, 2-Sep:** *"Audit whether the bots have a real edge … Identify whether profits
come from a repeatable signal or from a small number of lucky trades."* This is the answer, in
the order asked, with the numbers. The instrument that produced it is committed, tested (25
structural pins + an offline selftest) and importable; nothing here was computed by hand.

---

## 0. The verdict, before the tables

> **No living book has an established edge today.** 18 books were graded at once; **zero
> survive Benjamini-Hochberg at FDR 0.05**, zero pass the go-live gate (`ready: []`), and the
> fleet's realised in-era P&L across all 18 is **−$153.90**.
>
> **Every book that was minted on a per-trade founding number is now REJECTING it on its own
> live ledger** — four of four: 🪁 kelly (+0.397% claimed → −0.179% live, n=383, z=3.55),
> 🧭 cook (+0.367% → −0.193%, z=4.22), 🧘 douglas (+0.027% → −0.725%, z=2.64), 🔮 georgia-v3
> (+0.151% → −0.233%, z=2.41). The live ledger is the out-of-sample period by construction,
> and it is failing the replays that built these books. That is the overfitting finding, and
> it is not a suspicion — it is measured on 548 out-of-sample closes.
>
> **What IS there:** five books carry a positive one-sided lower bound — 👩 mum (live and
> shadow), 🎫 the taker, 🙏 avo shadow, 🏛️ turnbull — and of those, **👩 mum is the only book
> whose edge survives every test in this audit except multiplicity**: PF 2.36, win 83%,
> ex-top-3 mean still +0.583%, top coin 28% of net, break-even cost 70bps (4.0× the fleet's
> measured 17.5bps), live-vs-shadow execution gap +0.027pp, MC P(loss at 12m)=0.00 as
> recorded and at 3× costs. **But her graded era is FOUR DAYS old (52 closes, 28-Aug→1-Sep),
> her whole life sits inside the one regime the oracle has recorded (413 of 413 snapshots
> `risk-on uptrend`), and she is a long-only oversold-rebound book.** She is the fleet's best
> evidence, and she is not yet evidence of an edge — she is evidence of four good days in a
> rising tape. I25 says the next window regresses to her mean whatever we do; the honest
> forecast is her mean, not her window.
>
> **The one number that changes a decision:** 🪁 kelly has a **27.9% realised / 28.5% MTM
> drawdown against the 15% bar, a 1.00 bootstrap probability of ruin inside 12 months as
> recorded, and a founding claim rejected at z=3.55 on n=383.** She is not on the retirement
> docket (`losing-underpowered` — her upper bound still admits +0.03%). **[CORRECTED IN PLACE,
> same day (I12):** this read *"nothing in the fleet reduces her $250×4 clip"* — FALSE by a
> day. `(vy)` cut `KELLY_CLIP_USD` $250 → $80 on 1-Sep at Eamon's call, and the live row
> publishes `caps.clip_usd: 80`. Her bootstrap re-run at $80 on her $868 book: P(ruin) **0.00
> at 3 months, 0.27 at 6, 1.00 at 12**, median 3-month return −42%, if her −0.179%/trade mean
> holds. **The cut bought time, not survival.** What remains is the keep-or-retire call, and
> under I17-as-amended it needs her upper bound to reach zero — today it is +0.03%.]**

---

## 1. Per-book: expectancy, shape, risk, concentration, cost

Era-scoped, oldest→newest, `$1,000` book for shadow rows, real starting equity for live rows.
`LB%` is the one-sided lower bound at `fleet_allocation.t_crit(n)`; `Shp/t` is the per-trade
Sharpe (t/√n — comparable across books of different speed; the annualised figure is in the
JSON beside the close rate that produced it and is not quoted here because a 4-day book
annualises to 26 and that is the clock talking); `ex3%` is the mean with the three best trades
removed; `b3/gw` is the best three trades' share of gross wins; `BE_x` is break-even
round-trip cost as a multiple of the measured 17.49bps; `mtmDD` is the gate's own
mark-to-market drawdown (I9); `bars` is the gate's own count of six.

| book | n | mean% | t | LB% | PF | win | avgW$ | avgL$ | Shp/t | DD% | mtmDD | strk/exp | ex3% | b3/gw | BE_x | bars | class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| 👩 mum LIVE | 52 | **+0.703** | **2.73** | +0.366 | 2.36 | .83 | 3.65 | −7.39 | .38 | 4.6 | 3.8 | 2/2 | +0.583 | .14 | 4.0 | 5/6 | positive-unproven |
| 👩 mum shadow | 49 | +0.565 | 2.07 | +0.206 | 2.07 | .78 | — | — | .30 | 0.4 | 0.8 | 2/2 | +0.423 | .15 | 3.2 | 5/6 | positive-unproven |
| 🙏 avo shadow | 22 | +0.904 | 1.89 | +0.257 | 2.89 | .68 | 0.86 | −0.64 | .40 | 0.3 | 1.5 | 3/2 | +0.456 | .43 | 5.2 | 4/6 | positive-unproven |
| 🎫 taker shadow | 150 | +0.668 | 1.45 | +0.073 | 1.53 | .47 | 2.64 | −1.55 | .12 | 2.3 | 5.1 | 8/7 | +0.420 | .25 | 3.8 | 4/6 | positive-unproven |
| 🏛️ turnbull | 35 | +0.389 | 1.52 | +0.049 | 2.01 | .63 | 0.32 | −0.27 | .26 | 0.1 | 0.1 | 5/3 | +0.195 | .26 | 2.2 | 5/6 | positive-unproven |
| 🙏 avo LIVE | 11 | +0.503 | 0.88 | −0.316 | 0.77 | .55 | — | — | .27 | 7.0 | 5.6 | 2/2 | −0.220 | .97 | 2.9 | 2/6 | concentrated |
| 🔮 georgia shadow | 232 | +0.043 | 0.29 | −0.147 | 1.11 | — | — | — | .02 | 2.2 | 2.3 | 11/7 | −0.014 | .09 | 0.2 | 5/6 | concentrated |
| 🎯 sniper | 42 | +0.204 | 0.24 | −0.940 | 1.11 | — | — | — | .04 | 0.7 | 0.7 | 5/5 | −0.966 | .59 | 1.2 | 4/6 | concentrated |
| 🪁 kelly | 383 | −0.179 | −1.10 | −0.388 | 0.85 | .41 | 4.59 | −3.82 | −.06 | **27.9** | **28.5** | 10/10 | −0.266 | .11 | 0 | 1/6 | losing-underpowered |
| 🌾 carry | 16 | −0.101 | −1.29 | −0.209 | 0.26 | — | — | — | −.32 | 1.9 | 2.0 | 7/6 | −0.224 | .98 | 0 | 1/6 | losing-underpowered |
| 🏛️ albanese | 51 | −0.242 | −0.50 | −0.873 | 0.82 | — | — | — | −.07 | 0.9 | 0.8 | 7/8 | −0.580 | .25 | 0 | 3/6 | losing-underpowered |
| 🛢️ garrett | 85 | −1.090 | −2.22 | −1.729 | 0.44 | — | — | — | −.24 | 2.9 | 3.1 | 6/5 | −1.302 | .18 | 0 | 2/6 | **refuted** |
| 🧘 douglas | 81 | −0.725 | −2.54 | −1.096 | 0.51 | — | — | — | −.28 | 6.1 | 5.7 | 10/9 | −0.999 | .28 | 0 | 2/6 | **refuted** |
| 🔮 georgia LIVE † | 30 | −0.354 | −1.70 | −0.631 | 0.43 | .40 | — | — | −.31 | 79.2 | **58.3** | 5/5 | −0.541 | .41 | 0 | 1/6 | **refuted** |
| 🔮 georgia-v3 | 46 | −0.233 | −1.46 | −0.442 | 0.50 | — | — | — | −.22 | 0.7 | 0.8 | 9/5 | −0.382 | .46 | 0 | 2/6 | **refuted** |
| 🧭 cook | 38 | −0.193 | −1.45 | −0.368 | 0.40 | — | — | — | −.24 | 1.1 | 1.1 | 9/7 | −0.301 | .58 | 0 | 2/6 | **refuted** |
| 💸 farmer shadow | 199 | −0.548 | −2.42 | −0.840 | 0.63 | — | — | — | −.17 | 4.0 | 3.9 | 12/7 | −0.608 | .25 | 0 | 3/6 | **refuted** |
| ⚖️ counterweight | 141 | −1.704 | −1.88 | −2.873 | 0.55 | — | — | — | −.16 | 5.1 | 3.4 | 8/6 | −2.089 | .21 | 0 | 3/6 | **refuted** |

† retired today ((wj)/(wk)): equity $0.01, halted, funds moved to mum at 00:30Z. Graded on its
record; the record says the retirement was right (MTM drawdown 58% against a 15% bar).

**Class definitions** (`edge_audit.verdict`, not a re-spec of the gate): *refuted* = mean < 0
AND the one-sided upper bound is ≤ 0 (the (tz) power gate — the sample EXCLUDED a positive
mean); *losing-underpowered* = mean < 0 but a positive mean is still admitted; *concentrated* =
mean > 0 but the mean without the three best trades is ≤ 0 — three trades, not a distribution;
*established* = LB > 0, survives BH, not concentrated (**none qualify**); *positive-unproven* =
mean > 0 and none of the above.

**Realised P&L by class:** refuted **−$192.17** · losing-underpowered **−$146.98** · concentrated
+$4.14 · positive-unproven **+$181.11**. Seven refuted books have cost the fleet more than the
five positive ones have earned.

### 1a. Gross vs net, fees, slippage — the honest statement

This venue is **zero-fee, measured** (every active book reports `taker_fee 0.0000`). Shadow
fills already walk the book (`venues/shadow.py` records `spread_bps` + `slippage_bps` per
fill); live fills are real. So the ledger P&L IS net of execution, and there is no separate
"fees" column to subtract. Only 4 of 42 books record a per-fill spread in `extra`, so a
fleet-wide cost model would be mostly invented; what the instrument computes instead is the
**break-even cost** — how many bps of ADDITIONAL round-trip cost would zero each book's mean:

| book | mean bps/trade | break-even added cost | × measured 17.49bps | survives costs 2× | 3× |
|---|---:|---:|---:|---|---|
| 🙏 avo shadow | 90.4 | 90.4 bps | 5.2× | yes | yes |
| 👩 mum LIVE | 70.3 | 70.3 bps | 4.0× | yes | yes |
| 🎫 taker | 66.8 | 66.8 bps | 3.8× | yes | yes |
| 👩 mum shadow | 56.5 | 56.5 bps | 3.2× | yes | yes |
| 🏛️ turnbull | 38.9 | 38.9 bps | 2.2× | yes | yes (P(loss 12m) 0.32 at 3×) |
| 🎯 sniper | 20.4 | 20.4 bps | 1.2× | yes | **no** |
| 🔮 georgia shadow | 4.3 | 4.3 bps | 0.2× | **no** | no |
| the other 11 | ≤ 0 | 0 | 0 | — | — |

**Live execution is not the problem anywhere.** Live arm vs shadow twin on the SAME coins over
the overlapping window: 👩 mum **+0.027pp** (live slightly better, n=43 vs 41, 21 coins);
🔮 georgia −0.094pp (n=28 vs 33; the shadow twin loses too — the strategy, not the fills);
🙏 avo +0.517pp (n=8 vs 7 — noise). Where a live book loses, its mark-fill twin loses beside
it. Improving execution would not have saved any of them.

### 1b. Long vs short

| book | long | short |
|---|---|---|
| 🎫 taker | **breakoutup n=104 +1.312% t=+2.19 +$82.1** | divergence n=46 −0.788% t=−1.31 −$17.3 |
| 🪁 kelly | n=191 +0.052% +$24.5 | **n=192 −0.410% t=−1.32 −$153.3** |
| 💸 farmer shadow | n=17 +0.442% +$4.5 | **n=182 −0.640% t=−2.61 −$31.0** |
| ⚖️ counterweight | n=67 +0.881% +$1.4 | **n=74 −4.044% t=−2.79 −$37.0** |
| 🛢️ garrett | n=42 +0.261% +$2.9 | **n=43 −2.409% t=−2.72 −$28.4** |
| 🧘 douglas | n=14 −0.263% −$3.7 | n=67 −0.822% t=−2.57 −$45.6 |
| 🏛️ turnbull | n=22 +0.278% | n=13 +0.577% |
| mum / avo / georgia | long-only | — |

**Every mixed book's loss is on its short side**, and the tape the oracle recorded is one rising
regime. That is item 18 mirrored: the shorts are paying the drift, and the (hm) rule — grade a
directional book against a random-entry null — would have said so before the books were
built. The taker's whole edge is ONE lens on ONE side (`long-breakoutup`); its short lens is a
measured loser it has already vetoed once (I14/I15).

### 1c. Consecutive losses vs chance

`strk/exp` in the table: the longest realised losing run beside the median longest run a book
with that hit rate and that n produces by chance (2,000 draws). **No living book's worst streak
exceeds its chance p50 by more than one trade** — mum 2/2, taker 8/7, kelly 10/10, farmer
12/7 (the only notable excess, on a refuted book). A streak that matches chance is not decay
and must not be read as one (I25).

### 1d. Concentration — one coin, one period, one trade?

| book | top-1 / net | top-3 / net | top coin / net | top month / net | ex-top-3 mean |
|---|---:|---:|---|---|---:|
| 🎯 sniper | **2.06** | **6.03** | SHEIN 2.69 | 1.98 | −0.966% |
| 🙏 avo LIVE | — (net < 0 in $) | — | NVDA | — | −0.220% |
| 🔮 georgia shadow | 0.30 | 0.85 | DOT/AAVE **0.87** | 0.41 | −0.014% |
| 🎫 taker | 0.32 | 0.72 | UNI 0.34 | **Aug 0.97** | +0.420% |
| 🙏 avo shadow | 0.25 | 0.66 | NVDA 0.42 | 0.62 | +0.456% |
| 🏛️ turnbull | 0.18 | 0.52 | SPCX 0.35 | 0.41 | +0.195% |
| 👩 mum LIVE | 0.09 | 0.25 | FOGO 0.28 | 0.90 (2 months) | +0.583% |
| 👩 mum shadow | 0.11 | 0.30 | FOGO 0.25 | 0.82 | +0.423% |

Three books are **three trades, not a signal**: the sniper's best trade is 206% of its total
(remove three and it loses); georgia-shadow's +0.043% is 87% one coin (DOT) and ex-top-3 is
negative; avo-live's +0.503% per-trade mean is a **−$5.15 dollar total** because her clip
moved 4× after the deposit and the losses came at the bigger clip (the `daily_loss` halt rail
booked −$22.1 of it on 5 exits — the (vf) finding). Mum is the least concentrated book in the
fleet by every measure except month, and month is an artifact of a 2-month life.

---

## 2. Where each book breaks down — regime, stress, hold, session

**The regime split cannot be made from here, and the reason is itself a finding.** The venue's
candle endpoint (`mainnet.zklighter.elliot.ai/api/v1/candlesticks`) is refused by this
environment's egress policy (403; `orderBookDetails` is allowed). The fleet's own regime
oracle, over its entire 30-day bus history, read **one regime — `risk-on uptrend`, BTC
`LONG-window` — in 413 of 413 snapshots.** And venue premium stress (the taker's own veto
quantity) never reached its 15bps bar at any trade open in the window: every graded trade sits
in the `stress<15` bucket. **There is no second regime in the sample to split on.** So every
positive number in §1 is a pass in ONE rising regime, and the bootstrap in §4 is conditional on
that regime persisting. What the ledger's own axes DO show:

* **Hold length is a real cut on the taker**: 1–3d holds **+2.219% t=+3.06 (n=57, +$93.8)**;
  4–24h flat (n=65, −0.002%); **1–4h loses −2.595% t=−3.19 (n=20, −$17.6)**. Its exits:
  `hold` n=47 +2.130% t=+3.73 and `trail` n=62 +1.066% carry it; `sl` n=30 −4.092%. The edge
  is in letting a breakout run past a day, and the hourly-scale exits are where it leaks.
* **Kelly's `converged` exit is her death**: n=285 −0.317% t=−4.21 −$208 — the mirror's own
  losing exit, exactly the recorded cause of death of the ghost she mirrors ("the book
  harvests its own entry gate"). Her `ghoststop` n=41 +5.865% +$544 and `stop` n=30 −6.789%
  −$466 are a fat two-sided tail on a $250 clip; `SKR` alone is −$112.6 over 88 trades.
* **Douglas** loses inside the first hour (n=41 −1.365% t=−3.40) and is flat after (1–4h
  n=28 +0.036%); 54 `sl` at −2.170% vs 25 `tp` at +2.351%. **Garrett/Farmer/Counterweight**
  each lose on `stop`/`max_hold` exits at −7 to −10%/trade against `take_profit` at +4%: the
  stop is 2× the target on funding books whose thesis was accrual, not price.
* **Mum**: `roi` n=43 +1.425% +$157 vs `stop_loss` n=5 −4.333% −$57.8 — five stops took 37%
  of her gross wins. Her 1–3d holds lose (n=5 −0.592%); the 12h bracket is doing its job.
* **Weekday / session**: no book shows a session effect that survives its own n — the
  strongest (mum 00–06Z +0.811% t=2.14 on n=22; garrett Mon −3.3% t=−2.31 on n=10) are
  single-digit-day samples inside a two-week life. Not actionable; reported so nobody
  re-derives them as a discovery.

**Should any book stand aside or size down in a condition?** With one regime in the sample
the only measured conditions are: the taker at sub-4h holds (measured loser — but that is an
exit policy, not a regime), kelly's short side (−$153), and every funding book's short side.
The regime answer needs the tape, which needs the endpoint unblocked or the fleet's own
`tape_cache` run from a host that can reach it. **Recorded as the audit's one unmeasured
axis; not guessed.**

---

## 3. Overfitting, leakage, cherry-picked dates — what survives

The strongest possible out-of-sample test is the one the fleet already runs without calling
it that: **the founding replay vs the live ledger.** A rule fitted on the tape it was graded on
either reproduces on the trades it then took, or it does not.

| book | founding claim (source) | live era | z | verdict |
|---|---|---|---:|---|
| 🪁 kelly | +0.397%/t, t=3.58, n=65 ((qw)/(rc)) | −0.179% n=383 | +3.55 | **rejects** |
| 🧭 cook | +0.367%/t, t=2.74, n=216 (dislocation band study) | −0.193% n=38 | +4.22 | **rejects** |
| 🧘 douglas | +0.027%/t, t=0.50, n=641 ((nt) corrected) | −0.725% n=81 | +2.64 | **rejects** |
| 🔮 georgia-v3 | +0.151%/t, t_cl=6.09, n=1,940 ((vr), 4 days ago) | −0.233% n=46 | +2.41 | **rejects** |
| 🙏 avo (both arms) | −0.131%/t excess vs random ((qu): edgeless) | +0.904% / +0.503% | −2.17 / −1.11 | reproduces (above its negative claim) |
| mum, taker, turnbull, garrett, counterweight, farmer, carry, sniper, albanese | no per-trade founding number on record | — | — | untestable |

**Four for four.** Every book this fleet minted on a per-trade replay number is now rejecting
that number on its own record, three of them at z > 2.5. The only book "beating" its founding
claim is the one whose founding claim was that it had no edge. Two readings, both true:
(1) **the replays are optimistic in a shared way** — each was graded on a 200–500d Lighter tape
that is one falling-BTC regime, then went live into a rising one; (2) **the selection is the
bias** — kelly and cook were the best of a swept grid (I25: picking the best of N cells inflates
its statistic by the spread of the unselected distribution; (uz) measured a ~1.85 t-unit
selection premium on mum's own universe sweep). Georgia-v3 is the cleanest case: 46 of 48
bracket cells cleared the bar in replay ("a plateau, not a lucky cell") — and 4 days later the
live ledger is at −0.233%. **A plateau over a fitted tape is still a fitted tape.**

**Parameter fragility, parameter plateaus.** The fleet's replay harnesses are per-book and
this audit did not re-run them; what it CAN say from the record is that where a plateau was
claimed (v3: 46/48 cells; cook: t=+2.69..+2.97 across five horizons) the live book failed
anyway. A plateau is necessary, not sufficient. The book whose evidence is NOT a replay at all —
mum, minted "hypothesis-grade" with an explicit control arm — is the one holding up. That is
not a coincidence worth ignoring: **her live record is the only measurement she ever had**, so
there was nothing to overfit.

**Walk-forward on the live ledgers** (non-overlapping 30-close windows, each after the first
out-of-sample by construction): 🎫 taker **4 of 5 windows positive** (+0.235, −0.665, +1.985,
+0.923, +0.861 %/trade) — the one book with a live walk-forward that holds; 🪁 kelly 5 of 12 —
a coin flip. No other book has ≥60 closes to split.

---

## 4. Monte Carlo — what to expect, and how much of it is projection

Bootstrap of each book's OWN trades at its OWN close rate, block width = the (kw) measured
batch, scaled to the BOOK through the book's median clip, path capped at ruin (−100%).
**`extrap`** is how many times past the sample each 12-month horizon reaches; anything over
~10× is a projection of a week, not of a record, and is shown but not quoted as a forecast.

| book | span | extrap 12m | P(loss) 3m / 6m / 12m | P(ruin) 12m | 12m ret p05/p50/p95 | 12m maxDD p50/p95/p99 | P(loss 12m) costs 2× / 3× | n for t=2 |
|---|---:|---:|---|---:|---|---|---|---:|
| 👩 mum LIVE | 4.0d | **91×** | 0 / 0 / 0 | 0 | (+1598/+1709/+1821%) † | 11 / 15 / 18% | 0 / 0 | 28 |
| 👩 mum shadow | 7.3d | 50× | 0 / 0 / 0 | 0 | (+40/+48/+56%) † | 1.4 / 2.2 / 2.6% | 0 / 0.16 | 46 |
| 🎫 taker | 32d | 11× | .01 / 0 / 0 | 0 | +36 / +55 / +74% | 4.3 / 6.7 / 9.1% | 0 / .01 | 286 |
| 🙏 avo shadow | 37d | 10× | 0 / 0 / 0 | 0 | +5.3 / +7.5 / +9.5% | 0.4 / 0.7 / 1.0% | 0 / 0 | 25 |
| 🏛️ turnbull | 41d | 9× | .01 / 0 / 0 | 0 | +2.0 / +3.0 / +4.0% | 0.3 / 0.5 / 0.6% | .01 / .32 | 61 |
| 🎯 sniper | 41d | 9× | .50 / .45 / .47 | 0 | −3.7 / +0.2 / +4% | 2.3 / 4.5 / 5.2% | .68 / .88 | 3,036 |
| 🔮 georgia shadow | 46d | 8× | .91 / .96 / .20‡ | 0 | −20 / −12 / … | 13 / 21 / 25% | 1.0 / 1.0 | 10,901 |
| 🪁 kelly | 14d | 27× | 1 / 1 / 1 | **1.00** | −100 / −100 / −100% | 104 / 118 / 129% | 1 / 1 | — |
| refuted seven | — | — | 1 / 1 / 1 | douglas 1.00, georgia-live 1.00 | | | | — |

† **Not a forecast.** Mum's 12-month median of +1,709% is 52 trades over four days at 4,800
closes/yr and a clip half her book, extrapolated 91×, in one regime, with no capacity limit.
It is printed because hiding it would hide the extrapolation; the honest 12-month statement
for mum is: *her per-trade mean is +0.70% ± 0.26 (SE) on 52 trades; her P(loss) at any horizon
is ~0 IF that mean holds; nothing in this sample can say whether it holds past the regime that
produced it.* ‡ georgia-shadow's 12m P(loss) is lower than her 6m because at 8× extrapolation
the +0.043% mean eventually dominates the path noise — the arithmetic of a tiny positive mean,
not evidence.

**Answers to the four questions asked, for the books that have a case:**

* *Probability of losing money over 3/6/12 months?* Mum, avo-shadow, taker, turnbull: ~0 at
  every horizon **conditional on the sample repeating**. Sniper ~50% (a coin flip, as (tx)
  measured). Every refuted book: 1.00.
* *What drawdown to prepare for?* Taker p95 6.7% / p99 9.1% of book at 12 months; mum p95 15%
  (at a clip half her book — see §6); avo-shadow < 1%; turnbull < 1%. Kelly: ruin.
* *How many trades before results are meaningful?* At the observed mean/sd, for t=2: mum 28
  (she has 52 — the bar she has not cleared is 30 DAYS, not 30 closes), avo-shadow 25 (has 22),
  turnbull 61 (has 35), **taker 286 (has 150 — ~30 more days at 4.5/day, which is the (wj)
  runbook's ~3-Oct)**, sniper 3,036, georgia-shadow 10,901 (undecidable by flatness, (qu)).
* *Does it survive 2×/3× costs?* Mum, avo-shadow, taker: yes at both. Turnbull at 2×; at 3× its
  P(loss 12m) is 0.32. Sniper fails 3×. Georgia-shadow fails 2×.

---

## 5. Execution — is it the signal or the fills?

The signal. §1a: live-vs-shadow gaps of +0.027pp (mum), −0.094pp (georgia), +0.517pp (avo,
n=8) on the same coins. The fleet's `implementation_shortfall` organ is `stood_down` (its only
paired book, the Farmer, retired its live arm), so this audit's pairing is currently the only
live-vs-mark measurement running. **Recommendation — DONE (another session's (wp), 2-Sep):** `fleet_bus.shortfall_default_pair`
now derives the pair from the registry (the living pair with the most live closes, mum) and
the organ publishes `arm-drift` instead of `stood_down`. The original ask: point `implementation_shortfall` at the
mum pair — it is the fleet's only real-money book with a shadow twin and an edge worth
protecting, and its `gap_pp` is the number that would say first if her fills degrade.

---

## 6. Position sizing and risk — what the numbers say to change

The fleet already has: SafetyRails (kill switch, notional caps, daily-loss halt), the fleet
long-budget veto (20), per-symbol caps, the 7d drawdown governor (`clip_scale`), the
allocation organ's 25% probe floor, brain multipliers clamped to [1/6.7, 6.7], and I16's rule
that a ceiling is computed only on a positive lower bound. **Preserving every existing
configuration per Eamon's instruction**, these are the changes the audit's numbers support,
as proposals for approval — none is applied here:

1. **🪁 kelly's clip — ALREADY DONE, corrected in place (I12).** This proposed $250×4 → $80×4;
   `(vy)` shipped exactly that on 1-Sep at Eamon's call, a day before this audit, and the live
   row publishes `caps.clip_usd: 80`. The audit's ledger read $250 because 383 of her closes
   were taken at the old clip. What the cut buys, re-measured at $80 on her $868 book:
   P(ruin) 0.00 at 3 months, 0.27 at 6, 1.00 at 12; median 3-month return −42%; p95 drawdown
   70% at 3 months — IF her −0.179%/trade mean holds. **Time, not survival.** The remaining
   decision is keep-or-retire, and I17-as-amended requires a measured exclusion (upper bound
   ≤ 0); hers is +0.03% on n=383. Pre-register it: read at n=60 fresh closes at the $80 clip;
   retire if the fresh upper bound ≤ 0, keep grading if the fresh mean > 0.
   **EXECUTABLE (edge-audit follow-up, 2-Sep):** `golive_readiness.DECIDED_UNTIL["band-kelly"]`
   (expires 1-Oct; the docket prints `decision_overdue` past it) and the HANDOFF row
   `kelly-fresh-read-pre-registered`, which closes only when the entry is removed.
2. **Drawdown-scaled clip as a fleet rail, not a per-book env.** Kelly shows the gap: the 7d
   governor scales the fleet's *live* consumers and the go-live gate *reports* maxDD, but no
   organ reduces a shadow book's clip when its own realised drawdown crosses the bar it is
   graded on. Proposal: `clip × max(0.25, 1 − maxDD/0.15)` applied through `apply_tuning` on
   the books that have a clip lever, published as `extra.dd_scale`. Restrict-only, so it is
   the (kd)-eligible shape once measured.
   **SHIPPED (wu), reshaped on Eamon's *"don't constrict too much"* — corrected in place (I12):**
   the rail lives in `fleet_bus.brain_clip_multi` (the accessor every book sizes through), not
   `apply_tuning`; it is **1.0 all the way to the 15% bar** and falls linearly to 0.25 at twice
   the bar, so a book inside the range the gate grades it on is never cut; the scale is
   recorded on each close's `brain_mult` stamp (I23) with the decomposition in
   `fleet_bus.last_sizing[bot]`, and no row field `extra.dd_scale` was added. Kelly at 28.5%
   sizes at 0.325×.
3. **Never lever a negative lower bound.** Already I16 doctrine for the *ceiling*; the brain's
   6.7× *multiplier* and the live `GROSS_X` levers are not gated on it. Proposal: the
   `brain_clip` accessor returns ≤1.0 for any bucket whose book-level LB ≤ 0. Mum's LB is
   +0.366% — she is the only live book that would be eligible for >1× under this rule today,
   and her clip is already half her book.
   **SHIPPED (wu), fail-open — corrected in place (I12):** the cap fires only when
   `fleet_allocation` has MEASURED the sized book's era lower bound at or below zero on at
   least 10 era closes; a dark or thin organ changes nothing, and reductions pass through.
4. **Mum's stops are her tail.** Five stops = 37% of gross wins; avg loss $7.39 vs avg win
   $3.65 (PF 2.36 comes from the 83% hit rate). At 10× leverage her p95 12-month drawdown is
   15% — exactly the bar. This is not a proposal to change her bracket (the audit has no
   evidence the stop is wrong — (uw)'s exit sweep on georgia showed exits are a dead dial) —
   it is the number to watch: if her win rate reverts toward the fleet's ~50%, PF goes below 1
   at the current avgW/avgL. **Her monitor should be win-rate-vs-83% AND avgW/avgL, not P&L.**
   **SHIPPED (edge-audit follow-up, 2-Sep):** the grader publishes a per-book `shape` block
   (hit rate, trailing-30 hit rate, avg win, avg loss, payoff, break-even hit rate =
   1/(1+payoff), `hit_margin_pp`, current and max losing streak, and the p50/p95 chance
   streak for the book's own hit rate), and `fleet_immune` pages when a LIVE book's trailing
   hit rate sits within 5pp of its own break-even or its streak exceeds the chance p95.
   Judged against the book's own payoff, never a bare win-rate bar (I15).
5. **Correlation limits between books: not binding today.** §8 — daily realised P&L across
   the 18 books is essentially uncorrelated (mean ρ −0.02, N_eff 19.9). The live pair
   (mum + avo) are both long-only, both in the same regime, and co-hold the same coin 72% of
   the hours both are in; that is the one correlation to cap when the taker joins them.
6. **Rejected on the record:** martingale, averaging down, revenge sizing — none exists in the
   fleet and none is proposed; the (ne)/(hl) exit sweeps and (sr)'s leverage study already
   showed leverage adds no `S_d` (six rejections). Leverage on a weak edge compensates for
   nothing; on this fleet every book with LB ≤ 0 is at 1× and should stay there.

---

## 7. Genuinely different hypotheses — mechanism first, no code

Ranked by *robustness of the mechanism*, not by any historical return, and stated with the
test that would kill each one. None is a build; each is a study with a pre-registered verdict.

| # | hypothesis | mechanism (why an edge would exist) | data needed | fails when | test plan |
|---|---|---|---|---|---|
| 1 | **Funding-rate mean reversion on the SHORT extreme** (the mirror of every funding book's loss) | §1b: farmer/counterweight/garrett lose −0.6 to −4%/trade on shorts in a rising tape. Their short legs are *paying* drift while collecting funding. The premium that funds them is a crowd-positioning signal; when the crowd is short-funding-rich in an uptrend the position is the crowd's. | the funding history the scout already publishes (`lighter-market.funding`), BTC daily direction | funding extremes coincide with the direction that then persists (i.e. the crowd is right) | pre-register: long-only funding-receiving positions gated on the oracle's `LONG-window`; grade vs the (hm) random-entry null on the same coins; kill if excess ≤ 0 at n=30 |
| 2 | **Hold-band selection on the taker: only take breakoutups that survive 24h** | §2: 1–3d holds +2.219% t=3.06; 1–4h −2.595% t=−3.19. The edge is *continuation past a day*; the early exits harvest noise. | its own ledger (`held_h` per close) | the 1–4h losers are the same entries as the 1–3d winners observed earlier — i.e. selection on outcome | pre-register on FRESH closes only: `max_hold_h` floor vs the current bracket, judged through `lighter_ticket_replay`; I25 baseline = the book's own mean, not the window |
| 3 | **Regime gate on the whole directional fleet** | every mixed book's loss is its short side; every long-only book with a positive LB is long. The oracle reads one regime; the day it flips, the sign of most of §1 flips with it. | the oracle's per-asset verdict (exists, consumed only by the family bot) | the oracle lags the regime by more than the books' hold | pre-register: `fleet_bus.oracle_asset_regimes()` as an entry veto on shorts in `LONG-window` / longs in `SHORT-window`, shadow-first, graded vs the un-gated twin |
| 4 | **Cross-asset lead-lag: non-crypto session opens** | 41 non-crypto markets on-venue with a 24h perp on an underlying that trades 6.5h; the venue mark must reconcile to the underlying's open. `nav-cook`'s only positive class was "underlying market CLOSED". | `tape_cache` at 5m for the tokenised equities/commodities + exchange calendars | the reconciliation is already priced by the mark (index is not frozen — (ri) measured corr 0.62–0.77 for oil) | measure the mark-vs-index residual at the underlying's open ±30m vs a random hour; kill if the residual's mean reversion is not > 2× its off-hours value |
| 5 | **Volatility expansion after compression on 1h** | classic mechanism; the fleet has never tested it (grimes tested pullback/failtest/keltner — a *breakout* from compression is 🧙 schwager's retired supply and is unowned) | `tape_cache` 1h, ATR(24) percentile | it is the family breakout port (retired at t=−3.50) in a new costume | the (hm) null first: random entries on the same coins/hours; require excess > 0 at cluster-robust t≥2 BEFORE a book |
| 6 | **Liquidity-imbalance fade using the fleet's OWN fill data** | 3,230 book-walk rows since 9-Jul record spread + slippage per fill (`coin-quality`); thin books mean-revert after a forced fill. | `venue_orders` (has it), L2 snapshots (does not) | the fleet's own fills are the only forced flow it sees — n is small and its own | measure post-fill 5m/15m reversion on the fleet's fills vs random ticks on the same coin; a study only |

**Discard rule for all six:** depends on excessive tuning (>1 free parameter per 30 closes),
illiquid assets (<$0.5M/day — (qq)'s slippage cliff), or execution the venue does not offer
(partial closes, sub-second latency). #3 is the one with the highest prior and the lowest cost,
because it is a *veto* on existing books rather than a new one.

---

## 8. The portfolio — is it one bet?

**At the level of daily realised P&L, no.** 18 books, 43 pairs with ≥10 overlapping trading
days, mean pairwise ρ = **−0.020**, correlation-aware **N_eff = 19.9** (a symbol count would say
18 — and `fleet_risk` says 17.0 for 17 longs today, the I22 defect: 1/HHI over distinct symbols
cannot see that 15 of them are crypto beta). The strongest pairs are small-n and mixed-sign:
douglas–counterweight +0.69 (n=12), georgia–sniper +0.60 (21), avo–georgia −0.60 (15),
garrett–georgia −0.53 (20). Nothing here is a hidden common factor in the P&L streams.

**At the level of positions, partly.** Co-holding sampled hourly: up to **4 books long ADA at
once** (17-Aug); the fleet spent 600 hours with two books on one coin+side and 186 with three.
Live/shadow twins share coins 92–100% of the time by construction. **🙏 avo-live and
⚖️ counterweight shared a coin 83% of the hours both were in** — the basket book overlaps
everyone. The live pair mum+avo: 72%.

**Drawdown overlap is the real portfolio risk.** On **33% of 48 trading days more than half
the fleet was in a realised drawdown simultaneously**; the modal state is 8 books underwater
at once; worst fleet day **30-Aug: −$81.29** across 18 books. Uncorrelated *returns* with
correlated *drawdowns* is what a shared regime looks like from inside one regime.

**Allocation the numbers support:** `fleet_allocation` already ranks on the lower bound (I16)
and tilts a flat prior (tz). This audit adds nothing to its ranking and one constraint to its
clamp: a book with LB ≤ 0 AND realised DD > 15% (kelly) should sit at the probe floor
regardless of its claim — today the organ's 25% floor is a floor, not a ceiling for losers.
**Addressed at the accessor rather than in the organ (wu):** the two rails apply the
consequence where sizing happens — kelly's clip scales to 0.325× at 28.5% and reaches the
0.25 floor at 30% — while the allocation organ's advisory ranking is unchanged.

---

## 9. Monitoring and kill-switch — thresholds the fleet can act on

Most of this exists. The mapping, and the gaps:

| condition | threshold (objective) | organ that owns it | gap |
|---|---|---|---|
| **technical failure** — stale row, dead loop, data delay | `age_sec > ttl_sec` (I1); organ key staleness (I13) | `fleet_watchdog`, `fleet_immune`, `fleet_respiration` | none — this is the fleet's strongest layer |
| **abnormal slippage** | live-vs-shadow `gap_pp` < −0.25pp sustained over ≥15 paired closes | `implementation_shortfall` | ~~**stood down** — its only pair retired; re-point at mum~~ **CLOSED (wp)**: pair derived from the registry, organ publishes `arm-drift` |
| **drawdown beyond tested range** | realised or MTM DD > 15% (the gate's bar) → clip to probe floor | gate REPORTS it; the 7d governor scales live clips on FLEET dd | ~~**no organ reduces a shadow book's own clip on its own DD** (kelly, §6.2)~~ **CLOSED (wu)**: `fleet_bus.dd_scale` past the bar |
| **loss of liquidity** | coin `vol_m` < $0.5M or recorded half-spread > 30bps → entry veto | scout `vols`, `coin-quality` | consumed by some books' `MIN_VOL`; `coin-quality` had no reader until (ut) |
| **statistically significant decay** | book's trailing-30 mean below its own era mean by > 2×SE, judged vs the shadow twin (I25 — never vs the hot window) | `fleet_proprioception.grade_live` (has the twin baseline) | ~~`LIVE_MARGIN_PP` 0.25pp vs 1.674pp measured reversion — the margin is 6.7× too tight and a 3-trade baseline is allowed (I25 records this as latent)~~ **CLOSED (edge-audit follow-up)**: `LIVE_PRE_MARGIN_PP` 1.7pp on the pre-window, twin REQUIRED at 0.25pp, baseline floor = `fleet_allocation.MIN_N` |
| **normal variance** | losing streak ≤ chance p95 for the book's hit rate and n | ~~*nothing*~~ `golive-readiness.books.<bot>.shape.streak_p95_chance` + `fleet_immune` | ~~`edge_audit.expected_streak` — publish it so a streak is judged against chance, not against zero~~ **CLOSED (edge-audit follow-up)**: exact owner `golive_readiness.expected_streak`, published per book, live books paged beyond p95 |
| **regime mismatch** | oracle verdict flips against a long-only book's side | `regime_oracle` (consumed by the family bot only) | the live pair is long-only and unconsumed — §7 #3 |

**Distinguishing the four states**, mechanically: *technical* = liveness fails (age); *variance*
= P&L within the book's own bootstrap p05–p95 AND streak ≤ chance p95; *regime* = the twin
moves the same way AND the oracle flipped; *decay* = the twin does NOT move the same way and
the trailing mean is > 2×SE below the era mean on ≥30 fresh closes. Anything that trips
*decay* is a `hurting` verdict and reverts at `get_lever` — the fleet already has that reflex;
what it lacks is the margin calibration I25 names.

---

## 10. The pre-deploy checklist, applied to this audit's own proposals

Every proposal in §6/§7 must answer the ten questions before it ships. Applied to kelly's clip
cut (shipped by `(vy)` the day before this audit; the checklist is run on it retrospectively): (1) problem — 28% DD past a 15% bar, P(ruin)=1;
(2) rationale — a per-trade loser at 1× gross is a slow ruin, at 0.32× gross a survivable
sample; (3) data — her own 383-close ledger; (4) in-sample — n/a, it is a size change, per-trade
% is clip-invariant ((hl)); (5) OOS — the same; (6) walk-forward — 5 of 12 windows positive,
unchanged by clip; (7) after costs — unchanged; (8) sensitivity — none, it is a scalar;
(9) worst-case DD — 28% × 0.32 ≈ 9%; (10) disable when — her LB turns positive at n≥30 fresh
closes; (11) not overfitting because — it fits nothing; it is the drawdown bar being applied to
the book that broke it. **Recommend.** The georgia-v3 → live idea in (vr) fails at (5): its OOS
is z=+2.41 against its own claim after 46 closes. **Do not deploy** — and it was not.

---

## What this audit changed in the repo

* `scripts/edge_audit.py` — the instrument (calibration-gated, importing every owner, moves
  nothing; `--selftest` offline; 25 pins in `tests/autonomy/test_edge_audit.py`).
* `scripts/ceiling.py` — **corrected to price the grader's sample**: the public `/trades.json`
  feed does NOT apply `LEDGER_QUARANTINE` (the grader's read does) and this organ read it raw,
  so 🧘 douglas was priced on n=83 where the gate grades 81. Found by the calibration gate on
  its first run; one test pins it.
* `tests/test_selftests.py` — `scripts.edge_audit` registered (SELFTEST_MODULES, not
  ENFORCED_AUDITS — its live arm reads a moving ledger and refuses on a stale grade).
* No bot configuration was changed. Every proposal is in §6 for approval.

**Follow-up, 2-Sep (Eamon: *"Proceed with advisements"*, then *"Proceed on all"*):**
§6.2 and §6.3 shipped as the two rails in `fleet_bus.brain_clip_multi` ((wu), reshaped to
bite only on measured harm); the brain's expansion floors were measured forward and KEPT
(`scripts/study_brain_floors_2026-09-02.py`); §6.1's pre-registered read, §6.4's monitor,
§9's chance-streak publication and the I25 margin calibration shipped in the follow-up PR
(`tests/autonomy/test_edge_audit_followups.py` pins each). §5's re-point was done by (wp).
Nothing here changes what any bot trades; the two rails size, the rest measures and pages.

**Run it:** `python3 scripts/edge_audit.py` (live) · `--json --out result.json` for the full
payload · `--stress <bus-history-stress.json>` for the venue-stress split.
