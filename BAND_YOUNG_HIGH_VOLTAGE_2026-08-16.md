# ⚡ High Voltage — `band-young-lshadow`
## A book designed for high-leverage trading, and the arithmetic that bounds it

**Date:** 2026-08-16 · **Status: REFUTED AND NOT BUILT.** The design's own
pre-registered kill criterion (§6) fired on the first honest measurement. No
book was minted, no row exists, no service was provisioned, no lever was set,
no real money was touched. **Cohort:** Australian musicians
(`band-<surname>-lshadow`; barnes, garrett taken — Angus Young, AC/DC).

---

## VERDICT (2026-08-16, `scripts/study_leverage_sizing_2026-08-16.py`)

> **REFUTED.** On identical entries, risk-normalised sizing takes the control's
> t from **+0.505 to −0.823** (Δt = **−1.328**). Paired bootstrap
> **P(Δt ≥ 0) = 0.0014**; Δt is negative in **13 of 13** perturbations (worst-
> trade trims, leave-one-coin-out, 2/3/4/5-way time splits, both harness
> conventions) and in **all 12** pre-declared grid cells. Adversarially
> attacked from three independent lenses (code, statistics, rescue-search over
> ~701 cells) — **all three returned survives=true at high confidence.**

**Quote t, not dollars.** The headline −$255.91 and maxDD 54.1% are NOT the
refutation's strength and must not be cited as such: arm B runs a mean notional
of **$1,265 against the control's $100**, so those figures are the free
parameter `R`, not a finding. Risk-matched to the control the same arm reads
**−$20.24 at maxDD 5.2% with t bit-identical at −0.823**. And the dollar
figures FLIP SIGN under the pre-(ml) convention (arm B +$242.27). **The
pre-registered t test fails under both conventions, which is what carries the
verdict.** Cluster-robust ((kw) convention): A **+0.31** → B **−0.52**.

The primary criterion was *"t must IMPROVE"*, written before the run precisely
so this outcome could not be reinterpreted afterwards. It did not improve; it
inverted. Per the standing rule that a fix whose payoff the measurement refutes
is **reported as refuted, never sold as a win**, the build stopped at step 2 of
§8 and steps 3–5 were not started.

### Why it failed — and it is not the reason §3 predicted

§3 reasoned with a SCALAR: `mean(ret)/median(s) = +0.031R`, which predicts arm
B earns **+$199**. The arm's actual expectancy is `mean(ret/s)` — the true
equal-risk quantity, since arm B's dollar P&L is exactly `R · Σ(ret/s)` — and
that is **−0.0399R**, i.e. **−$256**. The two disagree in SIGN. Conflating them
was the design's own error, and it is now fixed in the study's output.

The mechanism, measured (208d Lighter 1h tape, 641 closes):

| s quintile | n | mean s | mean R-mult | **gross of cost** | c/s |
|---|---|---|---|---|---|
| Q1 tightest | 128 | 0.468% | −0.136R | +0.077R | 0.214 |
| Q2 | 128 | 0.685% | −0.250R | **−0.104R** | 0.146 |
| Q3 | 128 | 0.877% | −0.150R | **−0.036R** | 0.114 |
| Q4 | 128 | 1.134% | **+0.260R** | +0.348R | 0.088 |
| Q5 widest | 129 | 1.752% | +0.076R | +0.133R | 0.057 |

**[CORRECTED after adversarial review — the first reading of this table was
wrong in an important way.]** It is tempting to read the gradient as *"the edge
lives in wide-stop setups"*. It does not. **Excluding entry-bar stop-outs,
EVERY quintile is positive** (+0.396R, +0.492R, +0.555R, +0.874R, +0.605R) and
Q1 is not the worst. The gradient tracks entry-bar-stop FREQUENCY — Q2 45% and
Q3 42% against Q4 31% and Q5 32% — not stop width.

**THE ACTUAL MECHANISM:**

| population | n | share | mean R-mult | equal-risk $ |
|---|---|---|---|---|
| entry-bar stop-outs | 235 | **37%** | **−1.129R** | **−$2,653** |
| everything else | 406 | 63% | +0.590R | +$2,397 |

> **Equal-risk sizing charges every stop-out the FULL R. The fixed clip charges
> a tight-stop loss only `s × CLIP`** — $0.47 on a 0.47%-ATR coin against $1.75
> on a 1.75% one. With 37% of this book's trades stopping on their own entry
> bar, equalising that cost is the whole verdict. **The fixed clip was
> accidentally buying insurance against its own worst population**, and
> risk-normalisation cancels the policy.

A genuine wide-versus-tight gradient in `ret` does also exist and is real
(+0.0031, permutation p=0.0013, Welch t=+2.90, and it survives *within-coin* —
so it is a volatility-state effect, not a coin-identity artifact). But it is
the **smaller** term, and it argues for FILTERING tight-stop trades, which is
the opposite of re-weighting toward them.

### What the design got right, and what it got wrong

* **Right:** leverage as an output; the cost-vs-stop tension (§3 named it
  explicitly — *"risk-normalisation concentrates cost drag exactly where it
  weights most"* — and that is precisely what killed it); the demand for a
  liquidation model before any levered shadow book; the insistence on t over
  total P&L, which is the only reason this was legible as a failure at all.
* **Wrong:** the scalar `mean(ret)/median(s)` arithmetic in §3, and the
  numbers derived from it. Measured on the tape: **`gross_R = +0.144R`** (not
  0.245), **`s_floor = 0.69%`** (not 0.41%), **`L_ceiling@1% risk = 1.44×`**
  (not 2.45×). §3's *structure* survives — the ceiling formula
  `L_ceiling = RISK_PCT · gross_R / c` is right — but every value in it moved
  against the design once the pre-(ml) edge was corrected.
* **A trap avoided, worth recording:** the grid initially showed positive cells
  (best t=+0.75) and those were an artifact — the $600 notional cap was pinning
  arm B at exactly 0.60× on every cell, so it was a fixed-NOTIONAL book, and
  since t is scale-invariant it merely reproduced the control's t. Unbinding
  the cap turned all 12 cells negative. A clamp census now prints with the grid
  so a cell that has stopped testing its own subject says so.

### What survives and is worth keeping

1. **`scripts/lighter_margin_model.py`** — the fleet's first liquidation model,
   built against the venue's own published per-book margin tiers. It fires
   (2 liquidations at 5% risk/trade, 13 at 20%, and **67 of 641 trades would
   liquidate at each coin's venue-max leverage**), so it is not vacuous. It is
   the paper-arm complement to `(no)`'s live-account `margin_state`, which
   explicitly leaves the no-account case unanswered. Any future leverage
   proposal — and there have now been six — can be priced with it instead of
   argued about.
2. **The venue's margin tiers are free, published, and were unread**: BTC/ETH
   50×, SOL 25×, most alts 10×, LIT/ETHFI/TAO 5×, thinnest books 3×, all on the
   endpoint the scout already fetches every loop.
3. **THE ONE DURABLE LEAD, and it belongs to the HOST book, not to this one.**
   An ATR24 stop-distance floor near **1.0%** — *"do not fade an impulse while
   the coin is quiet relative to its own norm"* — takes the shipped 🧘 Douglas
   rule, at its existing fixed $100 clip with no leverage anywhere, to
   **t ≈ 2.2 in-sample** (control peaks t=2.217 at a 1.00% floor, sweeping
   0.0–2.4% at 0.10% steps). Out-of-sample it holds up less but still holds:
   fitted on one half it delivers **t=1.487** on the other.
   **Handle with the discipline this document demanded of itself:** the
   response surface is noise-shaped rather than monotone (10 up / 7 down steps,
   with a collapse at 1.30%), it was found inside a ~701-cell search, and it is
   therefore a LEAD requiring a pre-registered out-of-sample test — not a
   setting to ship. It is written up here because the same search proved the
   sizing rule adds nothing on top of it.
4. **A refutation of the whole family, not just one setting.** With notional
   ∝ `s^e`, t runs **−1.335 (e=−1.5) → −0.823 (e=−1, this design) → +0.505
   (e=0, the fixed clip) → +1.556 (e=+2)** — 10 up steps, 1 down. The surface
   is MONOTONE against the design across its entire range, so **there is no
   interior optimum and no cell to find.** Partial vol-targeting, leverage
   caps, and decoupling the sizing volatility from the stop volatility are each
   monotone toward the fixed clip. And the decisive one: fitting (floor,
   exponent) jointly on one half picks **opposite-signed exponents on the two
   halves** and loses to plain clip sizing out-of-sample both times. **Once any
   floor ≥0.85% is applied the exponent is INERT** — every cell that clears the
   fleet bar clears it because of the entry filter, never the sizing rule.

### The reusable rule — and it is stronger than "risk-normalisation is bad"

The adjudicating review ran the A/B across **seven** cohort rules, which none
of the three lenses had done. Δt by host: Douglas fade **−1.328** · Douglas
continuation −0.673 · Grimes failtest −1.661 · Grimes pullback −0.472 · **
Schwager 3.5× +0.116 · Schwager 2.5× +0.605 · Grimes keltner +0.341**.

**The sign is host-dependent — negative on 4 of 7, positive on 3** — and it
sorts on the host's own cost-to-stop ratio: positive where stops are wide
(Schwager median s = 5.2%, `c/s` = 0.019), negative where they are tight
(Douglas median s = 0.88%, `c/s` = 0.113). So the honest doctrine is NOT a
blanket ban:

> **Risk-normalised sizing is a property of the HOST's trade distribution, not
> of the sizing rule. Before adopting it anywhere, measure
> `sign( t(ret/s) − t(ret) )` on that host's own closes.** It is a one-line
> test on an existing ledger and it costs nothing.

And the bound that keeps it from being a rescue: **the largest improvement
anywhere lands on a REFUTED rule that stays at t=−0.687, and the best shipped
host moves 1.164 → 1.280 — nowhere near the 2.0 bar. No host on this venue's
tape crosses a decision boundary because of it.**

### The standing conclusion on leverage in this fleet

The prior was five studies, five rejections, with the caveat that four loaded
Hyperliquid data and so were *hypotheses about Lighter*. **That caveat is now
closed.** This is a Lighter-native measurement, on Lighter's own tape, with
Lighter's own margin tiers and a liquidation model — and it agrees with the
prior. Sixth measurement, sixth rejection.

The one route that remains unrefuted is the one §3 already named and this run
did not test: **`c` — execution quality.** Fees are zero on this venue, so `c`
is pure slippage, it has never been measured per book, and it is the only term
that raises `L_ceiling` while *also* raising expectancy. That, not a sizing
rule, is where a leverage program would have to start.

---

## 0. The ask, and the two-sentence concern

Operator ask: *"design me a bot specifically designed for high leverage
trading."*

**The concern, stated once:** this fleet has measured leverage five times and
rejected it five times, and the binding fact sits upstream of all of them —
`fleet_allocation` publishes `n_with_era_claim: 0` for both classes and
`golive_readiness.ready` is `[]`, so **leverage would be multiplying a claim
that does not yet exist.** Second, four of those five studies load Hyperliquid
data, so under BACKTEST ON LIGHTER ONLY they are *hypotheses* about Lighter,
not evidence — which cuts both ways and is exactly why a Lighter-native design
is worth writing rather than refusing.

So this document does the work. It is not a refusal. But it is also not the
thing that was already refuted five times, and §2 is the reason why.

---

## 1. What was actually rejected (so this design does not repeat it)

| Study | What it did | Why it died |
|---|---|---|
| `backtest_leverage.py` | `size = order_usd * L / px` | Pure risk dial — scales $ P&L and $ drawdown ~linearly. Liq reachable before the hard stop at L≥12.5 |
| `backtest_leverage_rails.py` | Same, plus the live rails | REJECTED at every setting. Rails + leverage interact **negatively**: the daily rail force-realises drawdowns at local lows — on a dip-buyer, it sells the bottom |
| `backtest_leverage_operator.py` | High-leverage intraday operator | 1/32 marginal survivor, dies under 2× slip stress. *"The leverage table was never earned"* |
| `backtest_funding_leverage.py` | The Farmer's own | Unrailed it scales (1×+3.0% → 8×+23.7%/150d) at **54% maxDD**; with the live daily rail **every L≥2 is self-defeating** (3× → −16.5%, 11–43 halts) |
| `backtest_overdrive.py` | The hedged carry — ⚖️ Counterweight's validated cross-sectional book, i.e. the one place leverage was supposed to belong | REJECTED at every gear. One ~90% adverse intrabar = a liq even at 1× isolated; adding stops to prevent it kills the edge (h1 negative at every gear). **The funding-spread edge IS compensation for tail risk** |

**The common shape:** every one applied leverage as a **scalar multiplier on an
existing book's clip**. That shape cannot improve evidence, and the reason is
the same algebra as POSITION-DAYS ARE NOT EXTRA EVIDENCE — multiply every
trade's P&L by `L` and the mean scales by `L`, the SD scales by `L`, and
**`t` is unchanged.** A scalar dial buys volatility and ruin risk in exchange
for nothing measurable. That is not a leverage bot; it is a bigger bet.

---

## 2. The reframe: leverage as an OUTPUT, never an input

⚡ High Voltage's defining property, and the only thing that makes it a
different animal from the five rejections:

> **It never chooses a leverage. It chooses a dollar risk and a stop distance,
> and leverage is what falls out.**

```
R      = RISK_PCT × equity          # constant dollar risk per trade
s      = SL_ATR × atr_frac          # stop distance, as a FRACTION of price
N      = R / s                      # notional required to make the stop cost exactly R
L_eff  = N / equity  =  RISK_PCT / s
```

**`L = RISK_PCT / s`.** Leverage is a reported diagnostic, not a knob. A quiet
coin (small `s`) automatically gets high leverage and a wild coin gets low
leverage — and both carry **identical dollar risk**, which no book in this
fleet currently does. Every existing book uses a FIXED clip ($80/$100), so a
$100 clip on a 0.3%-ATR coin and a 6%-ATR coin carry **20× different risk**
under one number. That is a real, measurable defect, and this book is the
vehicle that tests the fix.

This also makes the leverage *self-selecting by strategy shape*: run the same
rule over 🧙 Schwager's 3.5×ATR chandelier and it produces **low** leverage;
run it over 🧘 Douglas's 1.0×ATR bracket and it produces **high** leverage.
The rule does not need to know which book it is on.

---

## 3. The arithmetic that bounds the whole idea (read this before anything else)

This is the part that decides the design, and it is algebra rather than a
backtest, so it holds before a line is written.

Round-trip cost is charged on **notional**; risk is denominated in **R**. So:

```
cost_per_trade = c × N = c × R/s                 (c = round-trip cost fraction)
cost / R       = c / s                            ← independent of RISK_PCT
net_R          = gross_R − c/s
```

Two independent routes to high leverage, and they are completely different
animals:

**Route A — raise `RISK_PCT` (bet bigger at the same stop).** Leverage rises;
`cost/R` is *unchanged*; mean and σ both scale. **`t` unchanged.** This is
precisely what the five rejected studies did. It is ruin-bounded and
evidence-neutral. **Rejected here too, on the same algebra.**

**Route B — tighten the stop `s` (trade a shorter-horizon edge).** Leverage
rises at constant risk, and the economics genuinely change — *adversely*,
because `cost/R = c/s` grows as `s` shrinks. Every basis point you tighten the
stop hands a larger share of your risk budget to the spread.

Setting `net_R = 0` gives the two numbers this book is built around:

```
s_floor    = c / gross_R                          minimum viable stop distance
L_ceiling  = RISK_PCT / s_floor = RISK_PCT × gross_R / c
```

### Putting the fleet's own measured numbers in

From 🧘 Douglas — the same signal, measured on 208d of Lighter 1h tape, and
the closest thing the fleet has to a clean short-horizon edge:

| Quantity | Value | Source |
|---|---|---|
| `c` (round trip) | **10 bps** of notional | `SLIP_COST = 0.0005`/side, `lighter_book_douglas_bot.py:120`; venue taker fee measured **0.0000** on all 203 books |
| net per trade | **+$0.047** (= +$27.01 / 575) on $100 clips = **4.7 bps** of notional | `study_books_cohort_2026-08-13.py` |
| `s` (1.0×ATR24, 1h) | **≈0.6%** ← **ASSUMED, must be measured** | typical liquid-crypto 1h ATR24 |
| `gross_R` | net_R + c/s = 0.078 + 0.167 = **≈0.245 R** | derived |

Cross-check: 0.245 R gross × 0.6% − 10bps = 4.7bps net. **The arithmetic
closes against the measured result**, which is the only reason to trust it.

```
s_floor   = 0.0010 / 0.245           = 0.41%   of price
L_ceiling = 0.01 × 0.245 / 0.0010    = 2.45×   at a 1% risk budget
```

### The punchline

> **On this venue, with this edge, the maximum COHERENT leverage is ≈2.4× at a
> 1% risk budget.** Above it, slippage consumes more than the edge produces —
> not eventually, not on a bad run, but in expectation, on the first trade.

Three ways to raise the ceiling, and only two of them are real:

1. **Raise `RISK_PCT`** — raises `L` proportionally, changes `net_R` not at
   all. Buys ruin, not edge. *(Route A. Refuted.)*
2. **Raise `gross_R`** — a better edge. This is the whole fleet's actual job.
3. **Lower `c`** — **execution quality.** Venue fees are already zero, so `c`
   is *pure slippage*, and it has never been measured per book
   ([[lighter-slippage-is-per-book-not-per-venue]]). Halving `c` via maker
   fills doubles `L_ceiling` to ~4.9× and simultaneously raises `net_R` by
   0.08R — the same lever pays twice.

**The road to high leverage runs through execution, not through a leverage
knob.** That is the design's central claim, and it is testable.

---

## 4. The blocker that must be built first

`paper_broker.py`, its own docstring: *"MODEL (deliberately simple,
cash-settled perps, **leverage 1**): equity = start + realized_pnl − fees +
unrealized_pnl"*. There is **no margin, no maintenance margin, no liquidation
price, and no liquidation event** anywhere in fleet code — the repo-wide grep
for `update_leverage|margin_mode|initial_margin|liquidation` returns zero hits
outside `site-packages`, and the absence has a control group (the installed
SDK exposes `update_leverage(market_index, margin_mode, leverage)` with
`ISOLATED_MARGIN_MODE=1`, and `venues/lighter_client.py` already calls a
sibling method on that same signer for every real order).

**Consequence, stated plainly:** ship a levered shadow book on today's broker
and it will happily carry a position through a −$3,000 excursion on a $1,000
account and book the recovery. It would not be a conservative shadow — it
would be a **fiction generator**, publishing P&L that a real account could
never have earned because it was liquidated hours earlier. A book that cannot
lose the way the real thing loses is not evidence at any leverage.

So **component #1 is `venues/margin.py`**, before any bot file:

- `maintenance_margin_frac(coin)` — from the venue's own risk tiers, never a
  constant. Unknown ⇒ **fail-closed** (refuse the trade), never a guess (I8).
- `liq_price(entry, side, L, mm)` — isolated margin, per position.
- `check(position, mark) -> "ok" | "liq"` — evaluated on the **same live-mark
  loop as the stop**, and a `liq` closes the position at the liq price and
  books the **entire isolated margin** as the loss.
- `exit_reason = "liq"` is a first-class ledger tag, so
  `study_exit_attribution` can count them and the go-live grader can see them.
- Selftest: a planted −8% intrabar excursion at L=15 **must** produce `liq`,
  not a stop-out. Mutation-verified per I3 — a margin engine that never fires
  is exactly the vacuous-guard shape this repo has shipped before.

**And the invariant that keeps the book alive** (checked at entry, refused
otherwise, re-checked every loop):

```
liq_distance ≥ K × stop_distance,   K = 4      # LIQ_HEADROOM_K
```

At `s = 0.6%` and `mm = 0.5%`, liq sits at roughly `1/L + mm` from entry, so
K=4 binds at about **L ≤ 35×** — comfortably slack at the ~2.4× the economics
allow. That is the point: **the cost arithmetic binds long before liquidation
does**, and a design that only defends against liquidation is defending the
wrong flank. Both guards ship anyway; the headroom check is what makes the
claim falsifiable.

---

## 5. The book

| | |
|---|---|
| **Row** | `band-young-lshadow` |
| **Name** | ⚡ High Voltage |
| **File** | `lighter_band_young_bot.py` |
| **Service** | `band-young-shadow` |
| **Capital** | $1,000 shadow, **ZERO keys**, no real money, ever, until the gate + an explicit operator act |
| **Config** | **Env-only, NO tuning lane** (the Garrett/Kiyosaki precedent — single-policy (hm) clock by construction; levers are a day-31 decision) |

### 5.1 Sizing — the whole point of the book

```python
R_usd  = RISK_PCT * equity                    # RISK_PCT = 1.0%, env
s_frac = SL_ATR * atr_frac(bars)              # SL_ATR = 1.0, ATR24 on 1h
s_frac = max(s_frac, S_FLOOR)                 # S_FLOOR = 0.0041, from §3
N      = min(R_usd / s_frac, NOTIONAL_CAP)    # NOTIONAL_CAP = $600
L_eff  = N / equity                           # reported, never chosen
```

- **`S_FLOOR` is the edge gate, not a safety rail.** A coin whose 1h ATR sits
  below 41bps is unprofitable at *any* leverage, and 🧘 The Zone takes those
  trades today. This filter is a growth finding that falls straight out of the
  arithmetic and is measurable independently of this book.
- `equity` is **live MTM equity**, not `start`, so risk compounds down after
  losses and up after wins — the one place this book deliberately departs from
  Douglas's structural-consistency rule, and it is declared: consistency there
  is about *outcome-driven* deviation (revenge/martingale, measured harmful,
  −$38 swing), not about volatility targeting. `_open_position` still takes
  **no streak and no last-trade input** — selftest-pinned, same as its parent.

### 5.2 Portfolio caps (a per-trade risk cap is not a book risk cap)

| Cap | Value | Why |
|---|---|---|
| `RISK_PCT` | 1.0% | risk budget per trade |
| `GROSS_L_MAX` | 6× | Σnotional ÷ equity — binds before any single position does |
| `SIDE_L_MAX` | 4× | same-side gross; four correlated longs at 2× each is one 8× bet |
| `MAX_POSITIONS` | 4 | one bet per coin, no exceptions (the (hf) same-pair rule) |
| `NOTIONAL_CAP` | $600 | a single-position stop on runaway `R/s` |
| `LIQ_HEADROOM_K` | 4 | §4 invariant, entry + every loop |
| `<PREFIX>_MAX_NOTIONAL` | operator env | `venues/safety.py`, boot-refused if missing on any funded mode |

Correlation is the unmodelled residual and is **declared, not hidden**: the
book publishes its own `gross_l`, `side_l` and held-coin list every loop so
`fleet_risk.exposure` (1/HHI) and `audit_book_overlap` can see it, and the
cap is applied to raw same-side gross rather than to a correlation estimate
this fleet has never measured.

### 5.3 Entry — host signal

**Douglas's impulse fade, inherited verbatim**: fade a 1h close-to-close move
`> 2.5 × ATR24`, crypto ≥$1M 24h volume, top 18 by volume off the scout, plus
the (hk) held-coin union.

Chosen for four reasons, in order: it is the fleet's only **measured**
short-horizon Lighter-native edge (n=575, +$27.01, both halves positive, beats
199/200 random draws on both metrics, P=0.005); its **median hold is ~1h**, so
funding drag stays small at high notional; its bracket is **defined at entry**,
so `s` exists before the trade does — without which the sizing rule has no
input; and at ~83 closes/30d it is the fleet's **fastest-decidable** shape.

Its `t = 0.84` is sub-bar and that is stated, not buried — this book inherits
an unproven edge on purpose (§6 explains why that is the right call for a
*sizing* experiment).

### 5.4 The A/B property — one variable

🧘 The Zone already runs this exact signal at a fixed $100 clip. ⚡ High
Voltage runs it with risk-normalised sizing. **Exactly one variable differs:
the sizing rule.** Same entries, same universe, same bracket, same exits.

Leverage is not a second variable — it is this variable's output.

This satisfies [[ab-tests-must-vary-exactly-one-variable]] and gives the study
a running control instead of a synthetic one. **The overlap is the point**, so
it must be *declared* in `audit_book_overlap`'s allowlist with that reason —
an overlap detector that fires on a deliberate pairing is one the operator
learns to ignore ((gl), the cry-wolf rule).

### 5.5 Exits

Inherited from Douglas, unchanged: bracket fixed at entry (stop 1.0×ATR,
target 1.5×ATR, expiry 12h), never widened, no code path may move a stop away
from price.

Added, because they only exist at leverage:

- **`liq`** — §4. The exit the current broker cannot produce.
- **`funding_bleed`** — funding is charged on *notional* while P&L is measured
  against *margin*, so funding cost per unit of risk scales with `L`. At
  `L = 2.4×`, an 11% APR funding rate is **26% APR on margin**; over a 1h
  median hold that is ~3bps of margin — negligible, which is *why* a
  short-hold host was chosen. It is still netted explicitly at entry via
  `funding_basis` (TRUE apr, never the 8×-overstated raw rate) and exits when
  cumulative funding paid exceeds `FUNDING_BLEED_R = 0.25 × R`. **🧘 Douglas
  charges no funding at all today** — correct at 1×, wrong here.
- **`headroom_lost`** — the K-invariant re-checked live; flatten if breached
  by an adverse move before the stop fires.

### 5.6 Stop liveness is existential here

The latest fleet incident ((nm)) is the exact failure this book cannot
survive: *the BOOKS cohort's stop was neither live nor running — a bracket read
off a boot-frozen price, inside a gate that switched it off when funding went
quiet.* At 1× that is a wider loss; at 2.4× with a 41bps stop it is a
liquidation.

So: `venues/marks.stop_marks` on **every** loop, structurally outside any
funding-fetch conditional, with `stop_blind` published per coin and a
`stop_blind_since` clock that **flattens** a position blind for more than
`STOP_BLIND_MAX_S` (300s) rather than holding it hopefully. A levered position
whose stop cannot be evaluated is not a position with a stop.

### 5.7 The rail decision — declared, with its counter-argument

**This book carries NO daily-loss rail**, and that is a measured choice, not an
omission. `backtest_leverage_rails.py` and `backtest_funding_leverage.py` both
found rails and leverage interact **negatively** — the daily rail
force-realises drawdowns at local lows, and at L≥2 the Farmer's rail turned
+23.7% into −16.5% across 11–43 halts. Risk control here is **per-trade** (the
stop, which is what `R` *means*) and **per-portfolio** (gross/side caps).

Counter-argument, stated because it is real: (hl) measured that a shadow halt
skips the whole scan — *and the exits with it*. So a rail on a levered book is
not merely suboptimal, it is the mechanism that leaves levered positions
unattended. That reinforces the same conclusion from the other side.

`venues/safety.py`'s `*_MAX_NOTIONAL` boot refusal and `REAL_MONEY_KILL` are
untouched and remain senior — this is about the *daily-loss* rail only.

### 5.8 Telemetry (so `{open: 0}` is never ambiguous — I18)

Every loop publishes: per-position `L_eff`, `s_frac`, `R_usd`, `liq_price`,
`liq_headroom_x`, funding accrued; book-level `gross_l`, `side_l`,
`equity_mtm`; and a **census with its own bar** — `atr_below_floor`,
`headroom_refused`, `notional_capped`, `gross_capped` — so a book that opens
nothing says *why*, at its own gate. Plus `snapshot_equity` from day one
(`MTM_REQUIRED`): for a levered book the MTM drawdown series **is** the
evidence, and the go-live maxDD bar reads it.

---

## 6. The study that must pass first — pre-registered

`scripts/study_leverage_sizing_2026-08-16.py`. **Lighter-native**, which is
what closes the standing caveat that four of the five prior rejections rest on
Hyperliquid data. Reuses `study_books_cohort_2026-08-13.py`'s tape,
`run_portfolio`, `t_stat` and `random_bench`.

**Method, with the traps this repo has already paid for:**

1. **LAG-1 convention** — entry-bar range excluded ((ne)/(ml)). The look-ahead
   that inverted gillard's verdict is the same one that would flatter a tight
   stop most.
2. **Margin engine IN the loop** — a levered path that touches liq books
   −100% of isolated margin, not a stop-out. Without this the study measures
   the fiction described in §4.
3. **Funding netted per hour held** at TRUE apr.
4. **Slip sensitivity at 1× / 2× / 4× `c`** — `backtest_leverage_operator`'s
   sole survivor died at 2× slip, and here `c` is the term the whole thesis
   turns on. A result that does not survive 2× is not a result.
5. **Measure `s`, do not assume it.** §3's `gross_R = 0.245` rests on an
   assumed 0.6% ATR. The study computes realised per-trade `s` and re-derives
   `s_floor` and `L_ceiling` from the tape. **If measured `gross_R` differs
   materially, §3's conclusion moves and this document is corrected in place
   (I12).**
6. **The random-entry null must be LEVERED too** — grading a levered book
   against an unlevered null lets leverage flatter itself. Same coins, same
   window, same sizing rule, random entry timing.
7. **Pre-declared grid:** `RISK_PCT ∈ {0.5, 1.0, 2.0}%` ×
   `S_FLOOR ∈ {0, 0.25, 0.41, 0.60}%` × `GROSS_L_MAX ∈ {3, 6, 12}` ×
   slip `∈ {1, 2, 4}×`. A grid-edge winner is reported **unbounded**, never as
   a value ((gx)).
8. **Calibration gate, fail-CLOSED** — replay 🧘 The Zone's own shipped rule
   and reproduce its realised mean within tolerance *before* any counterfactual
   is allowed to speak. A harness that cannot reproduce what DID happen may not
   say what WOULD have.

### The kill criteria, written before the run

- **PRIMARY — `t` must IMPROVE** versus the fixed-clip control on the same
  entries. Not total P&L. A levered book earning 3× at 3× the volatility has
  learned nothing, and saying so afterwards is how a scalar dial gets shipped.
  **If `t` does not improve, the design is REFUTED and reported as refuted**
  — in the commit and the changelog, never quietly reframed as "more upside".
- Both halves positive, at 2× slip.
- Realised max MTM drawdown < 15% (the go-live bar, which a levered book meets
  or fails on its equity series, not its closes).
- Zero `liq` events at the shipped `GROSS_L_MAX` across the whole tape. One is
  a design failure, not a tail.
- `S_FLOOR`'s contribution isolated: if the filter carries the entire result,
  **ship the filter to 🧘 The Zone and do not mint a book.** That is the
  cheapest possible outcome and it is a win, not a disappointment.

---

## 7. Supply, decidability, go-live

**Supply (I20).** Identical to 🧘 The Zone's by construction — crypto ≥$1M,
top 18 by volume — and that is *deliberate*, because the pairing is the
experiment (§5.4). It takes **no funding-book supply**: the 20% TRUE / $2M
crypto cell (KAITO/XMR/PAXG/XRP, present in ~6.6% of scout snapshots, already
contested by 🌾/🎸/🏦) is untouched. `audit_book_overlap.py --gate` runs before
the row is minted regardless, and the paired overlap is declared in the
allowlist with this document as the reason.

**Decidability (I17).** ~83 closes/30d inherited from the host signal ⇒
gradeable **~30 days from first publish**, the fleet's fastest clock. If the
`S_FLOOR` filter cuts the rate below ~30 closes/30d, the book is an I17
keep-or-retire call at day 31 — declared now, so it is a decision later and
not a tuning session.

**Go-live.** Shadow forever until the standard gate (≥30d, ≥30 closes, mean>0,
t≥2.0, both halves positive, maxDD<15%), and go-live remains an explicit
operator act. **Two things are named now so they are not discovered later:** a
live levered arm would need `signer.update_leverage(market_index,
ISOLATED_MARGIN_MODE, L)` — a real-money path change, operator-gated — and the
`15%` maxDD bar is the one a levered book fails first. `venues/safety.py`'s
`REAL_MONEY_KILL` and `*_MAX_NOTIONAL` boot refusal stay senior and untouched.

---

## 8. Build order

Each step lands and is verified in the live payload before the next starts
(SHIP NARROW, VERIFY, THEN WIDEN).

1. **`venues/margin.py`** + selftest + mutation-verified liq test. *Nothing
   else can be trusted before this exists.*
2. **The study** (§6). **← the decision point. If `t` does not improve, stop
   here and publish the refutation.**
3. `lighter_band_young_bot.py` + `Dockerfile.young` + `--selftest`.
4. Registration in one pass, or the birth is half-built: `scripts/fleet_books.py`
   `ROW_ENTRY`, `AUTO_IMAGES`, the `railway-redeploy.yml` `paths:` + service
   grep, `audit_book_overlap` allowlist, `audit_deploy_coverage`,
   `audit_image_imports` (born-dark), `pnl_dashboard` row entry.
5. Provision `band-young-shadow` (the (lr)/(ls) dispatch pattern), verify the
   row publishes with a build stamp — **by stamp readback, never by a green
   run**.

**Reversibility:** `YOUNG_RETIRED_OVERRIDE=run` (entry gate, positions still
exit normally, census keeps publishing beside `retired: true` so the call stays
falsifiable) · `YOUNG_SIZING_MODE=fixed_clip` degrades to the control · every
cap is env.

---

## 9. NOT encoded — declared, so no future session "fixes" them in

- **A leverage knob.** There is no `L` input anywhere in this design.
  `RISK_PCT` and `S_FLOOR` are the only dials, and `L` is a published
  diagnostic. Adding an `L` multiplier reverts this book to the five rejected
  studies.
- **A daily-loss rail** (§5.7) — measured harmful with leverage, twice.
- **Pyramiding / adding to winners** — measured −$292 to −$1,103 (t=−5.8) in
  🧙 Schwager's cells. Structurally refused: one position per coin, no
  add-units path.
- **Cross margin.** Isolated only; one liquidation must cost one clip.
- **Martingale / streak sizing.** `_open_position` takes no outcome input,
  selftest-pinned (Douglas's rule, kept).
- **A tuning lane.** Env-only, day-31 decision.
- **Correlation-adjusted gross** — unmeasured; raw same-side gross instead.
- **Real money.** Not in scope at any point in this document.

---

## 10. The honest summary

A bot "specifically designed for high leverage trading" is a coherent object,
and this is what it looks like: **constant dollar risk, stop-derived notional,
isolated margin, a liquidation engine that actually fires, a live stop, no
daily rail, and leverage reported rather than chosen.**

But the design's own arithmetic is the most useful thing in it, and it should
be read as the deliverable rather than as a caveat:

> **`L_ceiling = RISK_PCT × gross_R / c` ≈ 2.4× on this venue, this edge, and a
> 1% risk budget.** Beyond it, slippage eats more than the edge makes — in
> expectation, on the first trade. Leverage above that is not aggression, it is
> a negative-expectancy tax that a bigger number cannot fix.

The lever that genuinely raises the ceiling is **`c`** — execution quality on a
venue whose fees are already zero, where `c` is pure slippage and has never
been measured per book. Halving it doubles the ceiling *and* adds 0.08R per
trade. **That is where a high-leverage program should start**, and it is worth
building whether or not this book is ever minted.
