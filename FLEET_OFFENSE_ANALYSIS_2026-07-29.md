# Fleet Offense Analysis — 2026-07-29

> **[RETRACTION, 2026-07-30 — read before using any number below.]** This
> document cites shadow short-divergence at **+3.035%/trade vs regime,
> t=+4.04** as "the fleet's only measured alpha", and uses it to justify the
> ticket-supply widening. **That figure is retracted.** `(gi)` found a THIRD
> era-pooling error one level above the first two: the shadow arm's 10 closes
> span **FOUR distinct bar-sets**, so pooling them was never legitimate. The
> only clean single-policy sample that exists is the LIVE arm's own 11 closes —
> **+0.883%/trade, t=+0.73, 95% CI [-1.81%, +3.57%], straddling zero.**
>
> What survives: the cap-binding observation (dip and divergence each returned
> exactly 6 tickets) is a fact about the SCOUT, not about the edge. So the
> `TICKET_TOP_N` 6 → 12 widening still stands — on the weaker, honest rationale
> of **more sample for an UNDECIDED lens**, not feeding a proven winner. Every
> other finding here was measured independently and is unaffected.

*What metrics, gates, scanners, bounds and scope each bot actually carries today,
and how each could **win more** — not lose less.*

**Method.** Gate surfaces read from the source at HEAD (`3761620`). Live fleet
P&L and the signal bus pulled from the read-only endpoints at analysis time
(`/pnl.json`, `/bus.json`) — measured, not inferred. Per-bot evidence cross-read
against `FLEET_REVIEW_2026-07-28.md`, `NEXT_SESSION_2026-07-30-taker.md` and the
`(fk)`–`(fw)` CHANGELOG series. Live real-money surface (Funding Farmer, Ticket
Taker) covered explicitly per the standing 16-Jul rule.

**Framing note.** This document is deliberately offense-biased because that is
what was asked for. Almost every proposal below is a **widening**, and this fleet
is built around restrict-only doctrine for good reasons. Two guardrails I have
kept throughout: every proposal names the shadow book it can be tested on first,
and no proposal touches the real-money surface without an explicit shadow bar.
The regime caveat (item 18) applies to every directional idea here — Lighter's
whole 438d tape is one falling-BTC regime.

---

## 1. The scoreboard, and what it says

Live at analysis time:

| Book | P&L | closed | W/L | win% | open |
|---|---:|---:|---|---:|---:|
| 🌾 perps-funding-carry-lshadow | **+56.20** | 80 | 31/49 | 38.8% | 7 |
| 💸 perps-funding-lighter-lshadow | **+14.21** | 84 | 47/37 | 56.0% | 0 |
| 🎫 lighter-ticket-taker-lshadow | **+7.80** | 135 | 51/84 | 37.8% | 2 |
| 💸 perps-funding-lighter-lighter **(LIVE)** | +6.85 | 62 | 39/23 | 62.9% | 0 |
| ⚖️ perps-funding-spread-lshadow | +6.83 | 41 | 23/18 | 56.1% | 10 |
| 👩 freqtrade-mum-lshadow | +3.89 | **0** | — | — | 4 |
| 🔮 freqtrade-georgia-lshadow | +2.06 | 55 | 26/29 | 47.3% | 0 |
| 🏛️ pm-albanese-lshadow | +2.05 | 18 | 8/10 | 44.4% | 0 |
| 🙏 freqtrade-avo-maria-lshadow | +1.12 | 4 | 4/0 | 100% | 4 |
| 🏛️ pm-turnbull / pm-rudd | +1.09 / +0.88 | 14 / 84 | | | 0 |
| 🌊 crypto-trend-daily-lshadow | +0.75 | **0** | — | — | 1 |
| 🎯 lighter-perp-sniper-lshadow | −0.03 | **1** | 0/1 | — | 0 |
| 🧲 lighter-dislocation-lshadow | −0.32 | 10 | 3/7 | 30% | 0 |
| 🎫 lighter-ticket-taker-lighter **(LIVE)** | −0.42 | 25 | 11/14 | 44% | 0 |
| crypto-intraday-15m-lshadow | −1.75 | 41 | 22/19 | 53.7% | 1 |
| crypto-swing-daily-lshadow | −2.65 | **1** | 0/1 | — | 1 |
| 🏛️ pm-morrison / abbott / gillard | −1.37 / −3.23 / −5.29 | 22 / 79 / 230 | | | 0 |
| 📊 equities-regime-lshadow | −4.05 | **0** | — | — | 2 |
| crypto-breakout-4h-lshadow | −5.73 | 12 | 2/10 | 16.7% | 0 |
| 👨 freqtrade-dad-lshadow | −6.70 | 9 | 2/7 | 22.2% | 2 |

**Two facts dominate everything below.**

**(a) Every profitable book in this fleet is a funding book.** Carry, Farmer
(both arms), Counterweight, and the Taker (whose live edge is *short*-divergence,
a funding signal). Every *directional* book — the four family books, the three
spot ports, Tide Rider, Index Rider, five of six PMs — is flat or negative. On a
438d tape that is one falling-BTC regime this is exactly what item 18 predicts,
and it means **the fleet's offense budget belongs in the funding complex**, where
the edge is largely direction-agnostic and the regime caveat bites least.

**(b) Win rate is not where the money is.** The two biggest earners win **38.8%**
and **37.8%** of their trades. The `(fk)` go-live rework already established this
for the gate; it has not yet been applied to how the *bots* are tuned. Several
gates below are implicitly optimising hit-rate, which on this evidence is the
wrong objective function.

---

## 2. The reframe: three constraint classes, three different fixes

Asking "how does each bot win more?" only has one answer per bot once you know
**what is actually binding**. Measured across the fleet, every book is in exactly
one of three states — and the fix is different in each:

### Class A — CAPACITY/SLOT-BOUND (edge exists, the book can't express it)

| Book | Evidence it is at its cap |
|---|---|
| 🌾 Carry | **7 open of `MAX_POSITIONS=8`** |
| ⚖️ Counterweight | **10 open** = exactly `K=5` × 2 legs — structurally full |
| 🎫 Taker (live) | `MAX_OPEN=4` + the `$40` notional rail; raising `TT_MAX_OPEN` is **INERT** because the rail binds first |

These books are turning away opportunities they have already graded. This is the
highest-value class and the cheapest to act on.

### Class B — SIGNAL-BOUND (slots free, the gate won't admit)

| Book | Evidence |
|---|---|
| 💸 Farmer (both arms) | **0 open of `MAX_OPEN=6`**, on both arms simultaneously |
| 🧲 Snap Back | entry gate `150bps` vs a measured **median residual of 3.8bps** |
| 🎯 Perp Sniper | n=1 in weeks; `new_listings: 0` on the bus right now |

Slots are idle. More capital does nothing. The gate or the signal source is what
must move.

### Class C — SAMPLE-STARVED (cannot generate evidence at all)

`mum` (0 closes), `Tide Rider` (0), `Index Rider` (0), `crypto-swing-daily` (1),
`perp-sniper` (1), `avo-maria` (4), `dad` (9), `crypto-breakout-4h` (12).

**Eight of twenty-three books have fewer than 13 closed trades.** At the go-live
gate's ≥30 closes over ≥30 days, most of these are *years* from being decidable.
A book that cannot reach its own decision bar is not a slow winner — it is
consuming a dashboard row, a share of attention, and the reviewer's time, while
producing nothing that can ever be acted on. Winning more starts with making
these books *decidable*.

---

## 3. Cross-cutting offense findings

### 3.1 The Farmer's entry gate sits **at the median of the venue** — measured

This is the single clearest offense finding in the fleet, and it is arithmetic,
not opinion. From the scout's live funding map (202 books):

```
|APR| distribution across the venue:
  p25 = 3.5%     median = 10.5%     p75 = 10.5%     p90 = 28.9%     max = 196.2%

  |APR| >=  5.0%  ->  116 books  (57% of the venue)   <- FUNDING_ENTER_APR
  |APR| >= 10.5%  ->  102 books  (50%)                <- the venue's mode
  |APR| >= 20.0%  ->   28 books  (14%)                <- CARRY_ENTER_APR
```

`FUNDING_ENTER_APR = 0.05` (5% TRUE) **admits 57% of the venue.** That is not a
selection gate; it is a coin flip. The distribution has a hard spike at 10.5%
(p50 = p75 = 10.5 — the venue's baseline rate), so the real information is in the
**upper tail above the spike**, and the Farmer's bar sits *below* it.

Worse, the growth rail cannot fix this on its own: `live.funding.enter_apr`'s
upper bound is **0.075**, which is still *below the venue's mode*. The lever
literally cannot express "only take above-median funding." (This is item **A1**
already queued for the 04-Aug review — the data above is the argument for it.)

**The fleet has already run the natural experiment.** The Yield Harvester is the
same funding signal on the same venue with a **4× tighter APR bar** (20% TRUE,
top 14% of the venue) and it is the fleet's biggest earner at **+$56.20** vs the
Farmer shadow's +$14.21 on a near-identical close count (80 vs 84).

> **Honesty on that comparison:** the radar classes carry as `artifact` — three
> single closes (SOXL +12.71, SNDK +10.31, ARB +9.67) are $32.69 of its $56.20,
> and it wins only 38.8% of trades. That does not undercut the point, it *is* the
> point: **carry's return lives in the tail, and a tail-seeking bar is what
> exposes the book to it.** The Farmer's median-seeking bar is structurally
> incapable of that shape of return. Carry also runs a 5× looser liquidity floor
> ($2M vs $10M) — see 3.2.

**Proposal (Farmer):** raise the `enter_apr` **lever ceiling** to 0.12+ so the
region above the venue's mode becomes reachable at all, then let the existing
xp-judge pipeline walk the shadow arm up through it under its normal paired bar.
This needs no new machinery — the judge, the lever registry and the shadow twin
all already exist. It is the highest-expected-value change available to the live
book, and the judge's ≥7d/≥30-close paired gate means it cannot reach real money
un-evidenced.

### 3.2 The liquidity floors are cutting the fleet off from its own tail

From the same live pull — the venue's 8 most extreme funding books:

| sym | vol ($M) | APR | passes Farmer's $10M? |
|---|---:|---:|---|
| H100 | 0.14 | −99.0% | ✗ |
| XLM | 0.26 | −89.4% | ✗ |
| SKR | 0.25 | −78.8% | ✗ |
| SNDK | 32.62 | +63.1% | ✓ |
| XPD | 0.11 | +47.3% | ✗ |
| SKHYNIXUSD | 49.85 | +43.8% | ✓ |
| TRUMP | 0.22 | −41.2% | ✗ |
| LIT | 21.13 | +38.5% | ✓ |

**`FUNDING_MIN_VOL = $10M` excludes 5 of the venue's 8 most extreme funding
opportunities, including the two most extreme.** Carry's floor is $2M and carry
is the book that earns.

The same shape appears on the Taker's alpha lens. Every one of the 6 divergence
tickets on the bus right now is a sub-$1M book (`0.18–0.63M`), and every dip
ticket is sub-$0.5M. **The measured alpha lives in micro-caps.**

**This also explains the Taker's clip-size result** that the campaign recorded as
a dead end: $13.33 → +$2.26, $20 → −$1.57, $40 → −$2.22. That is not evidence
against the edge; it is a **capacity curve**. You cannot push $40 through a $0.3M
book without eating the edge. The handoff calls the Taker "capital-bound"; the
data says it is **capacity-bound**, and those have opposite prescriptions:

> A per-trade edge that decays with size is harvested by **breadth (more trades,
> more books, more slots at small clip)** — never by depth (bigger clips).

### 3.3 The scout truncates the fleet's best signal to six tickets

The funnel feeding the Taker — the fleet's only measured-alpha strategy:

```
202 books  ->  98 liquid  ->  TICKET_TOP_N=6 per lens  ->  MAX_OPEN=4 slots
```

`lighter_market_scout.py:304` — `{k: v[:TICKET_TOP_N] for k, v in out.items()}`
— hard-truncates every lens to 6. On the live bus, `dip` and `divergence` both
return **exactly 6** (breakout and momentum return 5). A lens returning exactly
its cap is a lens whose cap is binding.

So the strategy with `+3.035%/trade, t=+4.04` vs its own regime is being fed a
**6-wide** candidate list, and then choosing 4. `TICKET_TOP_N` is already a
registered, replay-gated tuning lever (`scout.ticket_top_n`) — the scout tuner
can walk it under the existing not-worse-both-halves bar.

**This is the highest-leverage single knob in the fleet for winning more**,
because it multiplies the sample of the one thing measured to have alpha, at
constant clip size (which 3.2 says is the correct axis), and it is shadow-side.

### 3.4 The universes are hand-typed watchlists that the venue outgrew

| Book | Universe | As % of the venue's 202 books |
|---|---:|---:|
| ⚖️ Counterweight | 30 hand-listed | 15% |
| 🧲 Snap Back | 16 hand-listed | 8% |
| 👪 Family (wide ports) | ~29 | 14% |
| 👪 Family (core) | 15 | 7% |
| 🌊 Tide Rider | 6 | 3% |
| 📊 Index Rider | 3 | 1.5% |
| 💸 Farmer / 🎫 Taker | venue-wide (gated) | — |

Only the two funding books that scan the venue are the two that discover
anything. Every hand-typed list was written when Lighter carried far fewer books
and has not moved since. **A ranked selector cannot pick a winner it never sees**
— and unlike loosening a gate, enlarging the candidate set does not weaken the
selection rule at all: Counterweight still takes its top-5/bottom-5, it just
takes them from a real cross-section instead of a 30-name sample.

---

## 4. Per-bot: current surface and how it wins more

### 💸 Funding Farmer — `lighter_funding_bot.py` — **LIVE + shadow**

**Scope:** venue-wide scan. **Scanner:** 3-stage governor-aware
(`scan_candidates` → prelim rank → `_evaluate` → book probe on top-5).
**Metrics:** true APR (via `funding_basis`, H=1095), persistence, 1h realised
vol, 6h momentum, book spread, clip VWAP slip, cross-venue funding agreement
(`cross_venue_mult`, bounded [0.5, 1.2]), candle vol-character filter.
**Gates:** `ENTER_APR 0.05` · `PERSIST_H 4` · `MIN_VOL $10M` ·
`MAX_SPREAD_BPS 20` · `SCAN_MAX_SLIP_BPS 25` · `SCAN_VETO_VOL 1.5%/h` ·
`SCAN_VETO_ADVERSE 5%` · slope gate · quality veto · vol-character filter.
**Bounds:** `ORDER_USD 25` · `MAX_OPEN 6` · `MAX_NEW_PER_LOOP 2` ·
`EXIT_APR 0.01875` · `MAX_HOLD_H 72` · `HARD_STOP 10%` · `TAKE_PROFIT 4%`.
**State:** Class B — **0 open of 6** on both arms. The only `real_edge` book per
the radar.

**Win more:**
1. **Move the bar off the median** (§3.1) — raise the lever ceiling to 0.12+,
   walk the shadow arm up via the judge. *Biggest single lever on real money.*
2. **Lower `MIN_VOL` toward carry's $2M** (§3.2), paired with the *existing*
   slip/spread gates doing the real liquidity work. Note the gates are already
   redundant: `SCAN_MAX_SLIP_BPS 25` measures the actual clip cost, which is what
   `MIN_VOL` is a crude proxy for. Test on the shadow arm first.
3. **`SCAN_EXPLORE_K = 0` — explore has structurally never fired.** The Farmer
   has no mechanism for discovering anything outside its own ranking. The
   diagnosis doc's lean option (an explore-specific prefilter through the same
   Stage-B/C vetoes) is the fix; it is queued and unbuilt.
4. **`MAX_NEW_PER_LOOP = 2`** throttles the ramp when a genuine funding regime
   appears. With 0 open and 6 slots, this only ever binds on the days that matter.

### 🎫 Ticket Taker — `lighter_ticket_taker.py` — **LIVE + shadow**

**Scope:** scout tickets only; `LIVE_LENSES={divergence}`; bull mode admits
long-breakout + short-divergence, crypto-only. **Metrics:** funding divergence
gap (62.5pp), range position, 24h change, $vol, venue premium stress, brain
lens-forward grades (now side-aware, `(fn)`). **Gates:** `DIV_GAP 62.5` ·
`BRK_RANGE 0.95` · `DIP_RANGE 0.05` · `MOMO_CHG 5.0` · `STRESS_VETO_BPS 15` ·
quality veto · side-aware lens veto. **Bounds:** `MAX_OPEN 6` (live 4) ·
`CLIP 20–80` (live capped by a **$40 notional rail**) · `TP 4% / SL −3% /
MAX_HOLD 48h` · `DAILY_LOSS 5%`. **State:** Class A — capacity-bound.
**Edge:** shadow short-divergence **+3.035%/trade vs regime, t=+4.04**.

**Win more:**
1. **Raise ticket supply, not clip size** (§3.3 + §3.2). `scout.ticket_top_n`
   6 → 10–12 through the scout tuner's replay gate. This is the correct response
   to a capacity-limited per-trade edge, and it is the one change the campaign's
   own "closed questions" list does *not* rule out — every closed item
   (`TT_MAX_OPEN`, `TT_DIV_GAP`, lens on/off, clip size, symbol eligibility) was
   about **allocating a fixed 6-wide supply**, never about enlarging it.
2. **The `$40` rail, not `TT_MAX_OPEN`, is the binding bound.** If more slots are
   ever wanted on the live arm, the rail is what must move — and per §3.2 the way
   to spend more capital here is *more positions at the same clip*, never bigger
   clips.
3. **`TT_STRESS_VETO_BPS 15` has never fired** (0/2397 snapshots, median
   3.8–9.2). It is not protecting anything; it is dead weight in the decision
   path. Either lower it to where it discriminates or retire it — a gate that has
   never fired has never been tested either.
4. **Let the winning lens run wider before the losing one is revived.** The
   `by_side` grade now exists; short-divergence is the only graded winner. The
   natural offense move is a side-scoped slot reservation so short-divergence is
   never crowded out of the 4 slots by a lens with no measured alpha.

### 🌾 Yield Harvester (carry) — `funding_carry_bot.py` — shadow

**Scope:** Lighter, `MIN_DAY_VOLUME $2M`. **Gates:** `ENTER_APR 1.60` (=20%
TRUE, top **14%** of the venue) · `PERSIST_H 6` · hedge-less refusal (senior).
**Bounds:** `NOTIONAL 300` · `MAX_POSITIONS 8` · `EXIT_APR 0.15` ·
`MAX_HOLD_H 336` · `BLEED_STOP 2%` · `FLIP_GRACE_H 1`.
**State:** Class A — **7 of 8 slots full**. Fleet's biggest earner (+$56.20),
`t=2.42` on n=80, both halves positive, **38.8% win rate**.

**Win more:**
1. **It is one slot from full and it is the best book in the fleet.**
   `MAX_POSITIONS 8 → 12` is the most direct win-more change available anywhere,
   and it costs nothing to test — this is a $1k shadow book.
2. **It is the fleet's proof that the tail-seeking bar works.** Whatever is
   learned here should propagate to the Farmer (§3.1), not stay local.
3. **Caveat that must travel with it:** the radar calls it `artifact` (3 closes =
   $32.69 of $56.20). Widening slots is precisely how you find out whether the
   tail is repeatable or was three lucky books — which is the experiment worth
   running, stated as such.
4. `ENTER_APR` is a **bare constant**, not a lever — the growth rail cannot tune
   the fleet's best-performing gate at all. Registering it is prerequisite to
   learning anything from it.

### ⚖️ Counterweight — `lighter_funding_spread_bot.py` — shadow

**Scope:** 30 hand-listed coins. **Scanner:** 72h mean funding, rank, long the
K most-negative / short the K most-positive. **Bounds:** `K 5` (→10 legs) ·
`ORDER_USD 20` · `REBALANCE_H 24`. **State:** Class A — **10 open = exactly its
structural cap.** +$6.83 on n=41, 56% win rate.

**Win more:**
1. **`K 5 → 8` and the universe 30 → the venue's ~98 liquid books.** This is the
   cleanest widening in the fleet: the strategy is *explicitly* a cross-sectional
   rank, and a cross-sectional rank over 30 names is a weak version of itself.
   Ranking 98 books and taking the top/bottom 8 is strictly more information at
   identical per-leg risk.
2. Market-neutral by construction, so §2's regime caveat barely applies — one of
   the few books that can be widened without a regime argument.

### 👪 The family + spot ports — `lighter_family_bot.py` — 7 shadow rows

**Scope:** 15 core coins / ~29 wide + (since 30-Jul) 10 non-crypto behind the
per-asset gate. **Strategies:** TrendMomo (SMA 10/40, 1d), MomoBreakout
(Donchian + EMA200, 4h), SwingDip (RSI/BB, 4h/1d), DayTraderGated (15m/1h).
**Gates:** BTC regime/tide, per-asset oracle gate (fail-closed), symbol cap,
fleet-risk long-budget veto, brain stake mults. **Bounds:** `STAKE_USD 50` ·
`max_open` 4–8 · stoploss −0.05…−0.15 · ROI ladders · StoplossGuard/MaxDrawdown.
**State:** Class C mostly. mum **0 closes**, avo-maria 4, dad 9, breakout-4h 12,
swing-daily 1. Only georgia (55) and intraday (41) have samples.

**Win more:** honestly — **this is where I would not spend the offense budget.**
Four directional long strategies on a falling tape, and the per-asset gate is
"mostly closed by the evidence's own shape" at ship (NVDA long-window 30% of
bars, TSLA 2%, XAU 4%). The improvement that matters here is **decidability, not
returns**: mum on a 1d timeframe with 15 coins will not reach 30 closes this
year. Either shorten the timeframe / widen the universe enough that these books
generate evidence, or consolidate seven rows into fewer, faster books. The
non-crypto universe (step 3, shipped 30-Jul) is the one genuine offense
expansion here and it re-grades at SPY/QQQ graduation ~mid-Aug — that is the
date to revisit, with a real regime that is not falling-BTC.

### 🧲 Snap Back — `lighter_dislocation_bot.py` — shadow

**Scope:** 16 hand-listed coins. **Metric:** book mid vs Lighter's own
`index_price`. **Gates:** `PRE_BPS 50` census · **`ENTER_BPS 150`** ·
`CONFIRM_LOOPS 2` · `MAX_ENTRY_SLIP_BPS 30`. **Bounds:** `ORDER_USD 10` ·
`MAX_OPEN 3` · `EXIT_BPS 40` · `HARD_STOP 5%` · `MAX_HOLD 2h`.
**State:** Class B — n=10, −$0.32.

**Win more:** the entry gate is **~40× the measured median residual** (150bps vs
3.8bps, CLAUDE.md's own 17-Jul measurement). This bot fires only on the extreme
outlier and has 10 closes to show for it. The offense move is to **measure the
residual distribution and place the gate at a percentile** (e.g. p95/p99) rather
than at a number inherited from the Hyperliquid-referenced era — plus widen the
16-coin list, since dislocations are more common in thin books, exactly where the
list has no coverage. Cheap: it is a $1k shadow book with a pure, testable
`book_view` function (which, per the coverage work, also has zero tests).

### 🎯 Perp Sniper — `lighter_perp_sniper.py` — shadow

**Scope:** new listings only. **Bounds:** `TP +15% / SL −10% / 6h hold` ·
`MAX_OPEN 4`. **State:** Class B/C — **n=1**; `new_listings: 0` on the bus.

**Win more:** the strategy is sound but the *event* is rare, so the book is
structurally sample-starved and no gate change fixes that. The only real
widening is the **definition of the event**: newly-listed is one instance of
"book with no price history and violent repricing." The scout already publishes
`vol_surges` and `oi_moves` (both 0 right now, i.e. their own bars are also
tuned past where the venue lives). Broadening the trigger to *young + surging*
books would give this bot a population instead of a trickle. Until then, expect
it to stay undecidable — and it should not be counted as a fleet slot.

### 📊 Index Rider — `lighter_index_bot.py` — shadow

**Scope:** SPY, QQQ, XAU (3 books). **Gates:** 200-SMA regime + band hysteresis
(1.5%/2.0%). **Bounds:** **`ORDER_USD 250`** · `MAX_OPEN 3` ·
`CATASTROPHIC_STOP 15%`. **State:** Class C — **0 closes**, −$4.05 unrealised.

**Win more:** this book carries the **largest clip in the fleet ($250, 5× the
family's $50, 10× the Farmer's $25)** on a book with **zero closed trades** —
i.e. maximum size on minimum evidence, the exact inversion of how the rest of the
fleet is sized. A 200-SMA regime rule on 3 symbols is a ~2-trades-a-year
strategy; it will never satisfy the go-live gate. Either accept it as a slow
allocation sleeve and stop expecting trades from it, or widen it to the oracle's
10 graded non-crypto books and shorten the regime rule so it can be measured.
The venue's non-crypto books (SPY +8.1%, QQQ +12.2%, WTI +23.0% over the same
falling-BTC window) are the fleet's **only source of a non-falling regime** —
that is a genuine offense opportunity and this is the bot positioned for it.

### 🌊 Tide Rider — `lighter_trend_bot.py` — shadow

**Scope:** 6 coins, 1d, EMA 50/200. **State:** Class C — **0 closes.**
A 50/200 daily cross on 6 coins in a falling regime generates almost no entries
by construction. Its live row was retired 17-Jul. **Recommendation: it is a
candidate for retirement rather than improvement** — it holds a dashboard row and
produces no evidence. If kept, `RANK_BY_FUNDING` (currently off) is the one knob
that would connect it to the fleet's demonstrated edge.

### 🏛️ The Parliament — `parliament_main.py` — 6 shadow rows

**State:** mixed; gillard has n=230 (−$5.29), rudd n=84, abbott n=79 (−$3.23);
albanese/turnbull positive on small n. This is the fleet's only **self-tuning**
book family, and it is the right structure — six lenses, replay-gated tuners,
prequential ML. Its problem is the same as the family's: **directional strategies
on a one-regime tape.** The highest-value change is to give at least one PM a
**funding-based lens**, so the self-evolving machinery is pointed at the signal
class the fleet has actually proven, rather than re-discovering that longs lose
in a downtrend 230 trades at a time.

---

## 5. Ranked actions — by expected gain per unit of risk

| # | Action | Book | Class | Why it wins |
|---|---|---|---|---|
| 1 | `scout.ticket_top_n` 6 → 10–12 | scout → 🎫 | A | Multiplies the sample of the only measured-alpha strategy, at constant clip (§3.3). Shadow-side, replay-gated. |
| 2 | Carry `MAX_POSITIONS` 8 → 12 | 🌾 | A | Fleet's best book is 1 slot from full. Free to test. |
| 3 | Counterweight `K` 5 → 8, universe 30 → ~98 | ⚖️ | A | A cross-sectional rank over 15% of the venue is a weak rank. Market-neutral, so no regime argument needed. |
| 4 | Raise `live.funding.enter_apr` **ceiling** to 0.12+, walk shadow via the judge | 💸 | B | The gate currently sits *below the venue's mode* and admits 57% of books (§3.1). Biggest real-money lever; judge-gated. |
| 5 | Farmer `MIN_VOL` $10M → ~$2M on the shadow arm | 💸 | B | Excludes 5 of the venue's 8 most extreme funding books (§3.2); slip/spread gates already do the real work. |
| 6 | Register carry's `ENTER_APR` as a lever | 🌾 | — | The best-performing gate in the fleet is currently untunable. |
| 7 | Re-base Snap Back's `ENTER_BPS` on the measured residual percentile | 🧲 | B | 40× above the median means it almost never fires. |
| 8 | Build the explore prefilter (`SCAN_EXPLORE_K`) | 💸 | B | The Farmer has no discovery mechanism at all. |
| 9 | Give one PM a funding lens | 🏛️ | — | Points the self-evolving machinery at the proven signal class. |
| 10 | Decide Class C: widen to decidable, or retire | mum, Tide Rider, Index Rider, sniper | C | 8 of 23 books have <13 closes; they cannot reach any bar. |

---

## 6. What NOT to do (things that look like offense and aren't)

- **Do not size up the live Taker.** Its own measurements show the edge decaying
  with clip ($13.33 → +$2.26; $40 → −$2.22). The edge is capacity-limited;
  breadth is the only way to harvest it.
- **Do not loosen `TT_DIV_GAP` or re-open the exit ladder.** Both were swept to
  their degenerate limits and have no interior optimum — the campaign closed them
  properly, and re-opening them is how the `(fm)`/`(fo)` artifact loop happened.
- **Do not widen directional crypto books on the strength of "both halves
  positive."** Item 18: the whole tape is one falling regime, so a directional
  short passes both halves *by construction*. Non-crypto books are the honest
  route to a second regime.
- **Do not treat win rate as the objective.** The two best books win 38.8% and
  37.8%. Several gates above implicitly optimise hit rate; on this evidence that
  trades away the tail the returns actually come from.
- **Do not relax the restrict-only actuator doctrine to ship any of this.** Every
  item above can be expressed as a bounded, TTL'd, replay-gated lever, or as a
  shadow-arm experiment under the existing judge. If an idea needs the guardrails
  removed, that is a signal the idea is not ready.

---

## 7. The one-sentence version

**The fleet's edge is concentrated in funding, its capital and slots are
allocated as if it were uniform, and its three best-earning books are all
simultaneously at a structural cap while its biggest gate sits at the median of
the very distribution it is supposed to select from** — so the highest-value
offense available is not a new strategy, it is raising the supply caps and moving
the funding bar into the venue's tail, on the shadow arms, under the promotion
machinery that already exists.

---

*Gate surfaces read at `3761620`. Fleet P&L and signal bus pulled live from
`/pnl.json` and `/bus.json` at analysis time; funding distribution computed over
all 202 books the scout reports. No code changed by this analysis.*
