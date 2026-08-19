# STUDY — the ruin bound, and what it says about leverage

**Date:** 2026-08-19 · **Status: INSTRUMENT SHIPPED, LEVERAGE REFUSED AT THE
CURRENT STOP.** Operator direction: *"We are looking at this as a risk
eliminating job as opposed to a profit motivated job. Let's look at this
differently and look at options, even though risk will be higher."*

## VERDICT UP FRONT

> **Leverage capacity is a property of STOP DISTANCE, not of appetite.** At 💸
> the Farmer's shipped `HARD_STOP` of 10%, the designed refusal bar (4
> stop-widths of room before liquidation) permits **2× and refuses 3×**. The
> book already runs at 2×. It is therefore **one notch under its own ceiling,
> and it got there by luck** — nothing in the fleet had ever computed this.
>
> **The catastrophic regime is five notches away with nothing in between:** at
> 10× on a 10% stop the headroom is **0.78×**, i.e. **the liquidation fires
> before the stop does and the stop is decorative.**
>
> So the honest answer to "can we take more risk for more profit here" is
> **not at this stop**. The route to higher leverage runs through a TIGHTER
> STOP, which is a different book with different expectancy — a measurable
> trade, not a dial.

## THE TABLE (long side, mmf 2.4% — the XAU control's own tier)

`scripts/lighter_margin_model.liq_distance_frac` / `headroom_x`, the module
validated forward against the venue's published liquidation price to
**0.001%**.

| leverage | survives an adverse move of | headroom @10% stop (💸 Farmer) | @3% stop | @1% stop |
|---|---|---|---|---|
| 1× | 100.00% | 10.00× | 33.33× | 100.00× |
| 2× | 48.77% | 4.88× | 16.26× | 48.77× |
| 3× | 31.69% | 3.17× | 10.56× | 31.69× |
| 5× | 18.03% | 1.80× | 6.01× | 18.03× |
| 10× | 7.79% | 0.78× | 2.60× | 7.79× |
| 20× | 2.66% | 0.27× | 0.89× | 2.66× |

Bold reading: **4× is the bar**. A 10% stop buys 2×. A 3% stop buys 5×. A 1%
stop buys 10×. The BTC-tier (mmf 1.2%) table differs by under half a notch
(2× → 4.94×, 3× → 3.25×), so the conclusion is not tier-sensitive.

## WHY THIS WAS NOT ALREADY BINDING

Every piece existed and none of them was connected to a decision:

* `(no)` (16-Aug) wired the venue's OWN margining truth into the live path —
  per-position `liquidation_price`, `nearest_liq.dist_frac`, and a
  `liq_unknown` census — and **both live bots publish it**.
* `scripts/lighter_margin_model` then modelled the same quantity for positions
  that do not exist, validated it to 0.001%, and shipped **`headroom_x` with
  the refusal bar K=4 written into its docstring**.
* **Nothing refused.** `headroom_x`'s only declared consumer was ⚡ High
  Voltage — a book `BAND_YOUNG_HIGH_VOLTAGE_2026-08-16.md` **REFUTED AND NEVER
  BUILT** — so the criterion shipped orphaned. `venues/safety.py`, the one gate
  real money passes through, contained **zero** references to margin or
  liquidation: its questions were "how much may I deploy?" (notional cap) and
  "how much have I lost today?" (daily loss). Neither can see ruin.

That is I18's registered-but-inert failure landing on the single number a
leverage decision depends on.

## WHAT SHIPPED

`SafetyRails.headroom_ok(margin_state, stop_frac)` — may this book ADD notional
without sitting inside its own liquidation? Expressed in stop-widths because
that is the only quantity that travels across books: a stop is the loss already
accepted, a liquidation the loss not survivable.

**Fail-CLOSED, against this module's usual habit and deliberately.** Every other
degrade in `safety.py` fails OPEN so an organ outage can never idle a book. The
cost of a wrong default is different in kind here — an open failure is a
liquidation of real money — so an unreadable margin state, a position the venue
will not price (`liq_unknown`), positions held but none priced, and an unknown
stop **all refuse**. Same reasoning I10 gives the go-live blocker. A flat book
and any shadow arm stay permitted, or the gate could never allow a first entry
and would idle 20 paper books for a risk they cannot run.

Wired into 💸 the Farmer's entry site beside the notional cap, reading once per
loop, with `LIGHTER_RUIN_GATE=off` as the kill switch and `ruin_skips` published
on the row every loop — `0` included, because an omitted key is byte-identical
between "the gate never fired" and "the gate is not running" ((lv)).

## WHAT THIS DOES **NOT** ESTABLISH

* **It is not a backtest of leverage.** It prices the DISTANCE to liquidation
  analytically; it does not replay the tape to count how often a path would
  have breached it. That study is the natural next one and it is not done here.
* **It says nothing about the delta-neutral books.** 🌾 carry, 🧮 Hull and 🏦
  Rich Dad model P&L as `accrued − fees` with no price term, so they have no
  stop for a headroom ratio to divide by. Whether their real (single-leg, perp)
  exposure is genuinely delta-neutral on the venue is the question that decides
  whether they are the natural leverage candidates — **unanswered, and it is
  the highest-value follow-up**, because a genuinely hedged book's leverage
  capacity is governed by basis risk rather than price risk and is far higher.
* **It does not license 2×.** The Farmer already runs there; this only says the
  bar does not refuse it.
