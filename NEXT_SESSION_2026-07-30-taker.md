# Next Session — the Ticket Taker campaign, prepared 2026-07-29 (AEST evening)

> Handoff from the 29-Jul **Taker campaign** (PRs #121–#128). This is a
> SEPARATE thread from `NEXT_SESSION_2026-07-30.md` (the Farmer/research
> handoff) — read that one for the fleet-wide items.

## The one-paragraph version

The operator asked for the Ticket Taker to be optimised and made profitable.
**Configuration is now a closed question** — ~455 configs across seven
families, zero survivors against a pre-registered bar — and so is the
live-vs-shadow "capture gap" (~0% recoverable) and the invert-the-loser idea
(it is the falling market). What is NOT closed, and is the genuinely good
news: **short-divergence has measurable ALPHA over its own regime**
(shadow arm, current era: vs-market **+3.035%/trade, t=+4.04**). The book is
**capital-bound and sample-bound, not edge-bound**. Four real-money changes
were made and **three were retracted by me the same day** — read §5 before
shipping anything.

## 1. State at sign-off (all verified by published output, not inferred)

| | value |
|---|---|
| 🎫 live Taker build | `9accc96da97c` (= HEAD at #122), bull=true |
| live bars | `tp 0.04 / sl -0.03 / max_hold 48h`, `tuned=[]` |
| live risk | `max_open=4`, `cap_usd=40`, equity **$66.45** |
| live lens gate | **OPEN** — `allowed=['divergence']` (was EMPTY for 33h) |
| shadow twin | same build; bars back to `sl -0.03 / hold 48` after (fp) |
| `taker.sl` lever | **ABSENT** — the tuner no longer enacts a stop |
| 💸 Funding Farmer | untouched all session, $100.53, +$6.85 / 62 closes |

Nothing unverified is running on real money.

## 2. What was actually broken, and is now fixed

**The live arm could not take ANY entry for ~33 hours.** `LIVE_LENSES` is
`{divergence}` and the brain had vetoed `divergence` — so the allowed set was
empty. The veto pooled long+short: the pool is 69% LONG, the long side loses,
and it dragged the winning short side (the only side bull mode lets the arm
trade) under the 0.500 bar.

Fixed in `(fn)` — the brain publishes a nested `by_side` grade and the taker
grades the sub-population it actually trades. Fail-safe to the old rule in
every degraded case; kill switch `TT_LENS_VETO_SIDE_AWARE=off`.
**Verified live**: brain republished 10:34Z with `short 0.527 / +0.217`, and
the live allowed set returned to `['divergence']`.

**The growth rail was re-arming a refuted artifact.** 16 minutes after `(fo)`
reverted `TT_SL=-0.04` off real money, `fleet-tuning` showed the scout tuner
re-enacting exactly `-0.04`, every cycle, on a 2h TTL. Fixed in `(fp)`:
`SWEEP_SL` pinned single-valued **and** `STOP_LOSS` removed from
`attr_to_lever`, each separately asserted. **Verified**: `taker.sl` is now
absent from the lever payload.

## 3. The evidence, current and honest

Era boundary is the **24-Jul bull flip** (`(dh)`) — grading across it pools a
retired policy with the live one, which is the error `(fs)` corrects.

| book / lens (current era) | n | raw | **vs regime** | verdict |
|---|---|---|---|---|
| shadow `short-divergence` | 10 | +3.484% (t=+4.86) | **+3.035% (t=+4.04)** | **ALPHA** |
| live `short-divergence` | 11 | +0.883% (t=+0.73) | +1.223% (t=+1.11) | under-powered |
| shadow `long-breakoutup` | 8 | -1.973% | -0.828% (t=-0.61) | no alpha |
| `long-dip` (all time) | 13 | -1.162% (t=-2.66) | **+0.173% (t=+0.36)** | direction-exposed, NOT anti-predictive |

Grade any book this way with **`scripts/study_alpha_vs_regime.py`** (new, `(fv)`)
— the instrument item 18 has needed since 21-Jul.

**Caveats that must travel with those numbers:** ~5-day era; n=10–11 per arm;
the arms share one ticket stream so pooling is correlated (de-duplicated LOO
worst case is **t=+1.50**, below the gate); the lens has a **57-trade losing
prior** pre-flip (all-time n=67, t=+0.86, not significant); one falling regime.

## 4. Closed — do NOT re-open without a new instrument or new tape

| line of enquiry | what killed it |
|---|---|
| exit ladder `TT_TP`/`TT_SL`/`TT_MAX_HOLD_H` | no interior optimum; climbs to NO-STOP `(fo)` |
| `TT_DIV_GAP` loosening | saturates where the bar stops binding |
| lens on/off | lenses compete for `MAX_OPEN` slots `(fl)` |
| `TT_MAX_OPEN` upward | **INERT** — the $40 rail binds first, `venues/safety.py notional_ok` |
| `TT_STRESS_VETO_BPS` | **has never fired** — 0/2397 snapshots, med 3.8–9.2 vs a 15 bar |
| `TT_BRK_*` | structurally unreachable — breakout not in `LIVE_LENSES` |
| symbol eligibility | under a binding `max_open`, exclusion is SUBSTITUTION and the substitute is worse |
| entry timing | 34 of 38 entries are already at episode age 0 |
| invert-the-loser | it is the falling market: t=+2.48 → **+0.14** vs regime `(fv)` |
| the live-vs-shadow capture gap | ~0% recoverable — 56% slot-saturation luck, 13% censoring artifact; fills/timing/funding all REFUTED (live fills *cheaper*) |

`TT_SPREAD_GATE_BPS` is **unmeasurable**, not refuted — tickets carry no
spread/bid/ask field.

## 5. Read this before shipping anything to the Taker

Four real-money changes were made on 29-Jul; **I retracted three of them the
same day**, each for the same root cause — a number quoted without the
population it was computed over.

- `(fl)` claimed bull mode was shipped. **It was already on since 24-Jul.**
  Caught by `extra.bull` reading true on an arm nobody had touched.
- `(fm)` shipped an exit bracket on a sweep with no interior optimum →
  reverted by `(fo)` within the hour.
- `(fp)`/`(fr)` called the book edge-dead on a number that pooled two policies
  → corrected by `(fs)`.
- `(fs)` itself then over-corrected (ddof, a false-negative independence test,
  an LOO that fails the gate at t=+1.50, and an unexamined 57-trade losing
  prior) → corrected in-place before merge.

**The rule that would have prevented all four:** before quoting a number, state
its ERA, its BASIS (dollar vs equal-weighted), its ddof, and whether the
observations are independent. Before shipping a knob, extend its ladder to the
degenerate limit — no interior optimum means artifact.

## 6. What to do next

1. **Nothing urgent. Let it run.** The gate is open, the artifact loop is
   closed, and the strategy needs closes, not changes. It is ~5 days into a
   30-day window at ~2.2 closes/day.
2. **The stop A/B is staged but NOT dispatched** (`(ft)`). If you want it:
   dispatch `taker-live-bars.yml` with `arm=lighter-ticket-taker` (the **$1k
   shadow**, zero real money), `sl=-0.04`, `sync_tuner_sweep_sl=yes`.
   Pre-registered bar: shadow must beat live per-trade over **≥7 days AND ≥30
   shadow closes AND both halves** before the live stop is reconsidered.
3. **Operator decisions, priced not decided:**
   - **Capital.** ~$11.85 of the $15.01 live-vs-shadow dollar gap is clip size
     alone. At the measured rate the live book earns ~**$0.19/day** (≈9%/month
     on $66, pennies absolute). Sizing up multiplies whatever is really there —
     and the live arm's own alpha is **not yet significant**. Bigger clips
     measured WORSE on this tape ($13.33 → +$2.26, $20 → **−$1.57**, $40 → **−$2.22**).
   - **The tradfi leak** `(fr)`. `TRADFI_BASES` names `SKHYNIX` while the venue
     trades `SKHY`/`SKHYNIXUSD`; **38% of admissible supply is tradfi** (CXMT
     alone is 28.7%). Closing it makes every window WORSE. If you want the gate
     to mean what it says, ship it as a **correctness** change and state plainly
     that it costs money on this tape. Do not dress it as an edge.
   - **The go-live gate reads two bases at once** `(fq)`: `mean`/`t` from
     percentages, `h1`/`h2`/`maxDD` from dollars. A book can pass "both halves"
     on dollars while failing "mean > 0" on percentages — the shadow Taker does
     exactly that. Picking one basis is the operator's call.

## 7. Loose ends

- **Data integrity, unresolved:** a shadow stop fired on a mark the fill
  disagreed with (~$0.42 on one trade; excluding it moves the shadow mean
  3.484 → 3.635%). Not gap-driving, but it means a stop can fire on a price the
  book never traded. Worth a look.
- The live Farmer picked up build `128995c2fd76` without any workflow
  dispatching `trail-blazer-live` — flagged 29-Jul, never chased.
- `implementation_shortfall.py` is the organ built to decompose live-vs-shadow
  execution; it needs fill telemetry on the taker rows to run.
