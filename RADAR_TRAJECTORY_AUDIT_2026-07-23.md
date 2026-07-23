# Radar trajectory-sensor audit — 2026-07-23

**Verdict in one line:** the radar's self-correction (`cn`) was **right about the
Funding Farmer** — its "plausible" edge really is a decaying, 2-coin mirage — but
the new **trajectory sensor it shipped carries a sample-size bias** that will
false-flag ~15% of genuinely-healthy books as "decaying" going forward. The
Farmer call does not depend on that biased sensor, so the verdict stands; the
sensor should be re-gated on a calibrated `slope_t` before it is trusted on other
books.

## Scope & constraint
This is a **logic / calibration audit of `fleet_radar.py` on synthetic data**, not
a re-measurement of the live tape — this container has no `DATABASE_URL`, so the
live/shadow `paper_trades` and `bot_state` are unreachable. Everything below is
either (a) a property of the code that holds regardless of data, or (b) a
Monte-Carlo measurement over simulated books. `fleet_radar` is a **shadow,
publish-only organ with zero consumers** — nothing here touches real money.

## Verdict 1 — the Farmer "decaying + 2-coin" call is SOUND (over-determined)
It rests on three independent legs, the strongest of which is decisive; **none of
them is the biased trajectory gate:**

1. **`_faded` (decisive).** Last-15 mean **+0.036%** vs full **+0.561%** → ratio
   **0.064** — recent performance is ~6% of lifetime, far below the 0.5 "faded"
   threshold. Not a marginal flag.
2. **Hand-dig thirds (independent).** Per-trade t = **3.28 / 1.10 / −0.54** across
   the window's thirds — computed outside the radar's half-based logic.
3. **Concentration collapse (fully independent code path — `loco`).** Drop ZEC +
   HYPE and the LIVE book's t goes **1.10 → −0.32**, median negative.

Decay and 2-coin are the same story seen twice: the Farmer's whole positive edge
was a couple of coins (ZEC/HYPE) that paid off **early** in the window; recently
it is flat-to-negative. **Feeding it would confirm the fade, not reach a positive
verdict.** No real-money action changes on the strength of this audit.

## Verdict 2 — the trajectory sensor has a sample-size bias
The decaying/emerging gate uses `traj_delta = t_recent − t_full`
(`fleet_radar.py:187`, consumed at `:193`). It compares a **half-sample** t-stat
to a **full-sample** one. Because a t-stat scales with √n, that difference is
biased **negative** purely by sample size — with **zero real decay** — and the
bias grows with t:

| constant-effect book (no decay) | mean `traj_delta` | raw `≤ −1.0` hit-rate |
|---|---|---|
| t ≈ 2 | −0.49 | 28% |
| t ≈ 4 | −1.05 | 55% |
| t ≈ 6 | −1.53 | 74% |

After the `(median_recent < 0 OR faded)` corroboration knocks that back, **~15% of
healthy weak-edge books still classify "decaying"** (measured 16% at t≈2, n=40;
15% at n=60). Meanwhile `slope_t` — a properly calibrated OLS-slope t-stat
(~N(0,1) under a constant effect, **−14** on the real Farmer shape) — is
**computed at `:191` but never used** in the classification.

## The fix is not a one-line metric swap (measured)
Monte-Carlo over 600 books per cell (constant effect = zero real decay; the
false-decay rate should be ~0):

| decay gate | false-rate, weak t≈2 | catches real decay shapes? |
|---|---|---|
| current — `traj_delta ≤ −1` | ~16% | yes |
| `tb − ta ≤ −1` (equal-n halves, unbiased mean) | **~18%** — worse; too noisy | yes |
| `slope_t ≤ −2.0` (calibrated trend) | **~2.3%** — best | mostly; can miss ultra-smooth fades via the `se > 1e-9` guard |

Two lessons:
- The unbiased **level** comparison (`tb − ta`) is actually **worse** — each half
  is too noisy, so it crosses −1.0 by chance ~18% of the time.
- The residual false rate is driven **less by the traj_delta bias than by the
  loose corroboration**: on a weak-but-real edge the recent-half median dips
  negative ~half the time by pure noise, so *any* level gate leaks. Only a
  **significant** trend gate (`slope_t ≤ −2.0`) filters that noise out.

## Recommendation
- **Money:** none — the Farmer verdict is correct; the fleet is at zero durable
  edge; nothing to change.
- **Organ (shadow):** re-gate the trajectory label on a **calibrated
  `slope_t ≤ −2.0`** (a *significant* downtrend), with tightened corroboration,
  instead of the sample-size-biased `traj_delta` (kept as a reported diagnostic).
  It is a ~2% vs ~15% false-decay improvement. **Validate against the real Lighter
  tape before shipping** — confirm it does not under-catch genuine gradual fades
  on real (noisy) returns — precisely the "harness must mirror production" lesson
  from today's `cf`. That needs DB access; it is a next-session / operator step,
  not a synthetic-only change to rush in.

---

*Method: `fleet_radar._t` / `_slope_t` / `diagnose_book` exercised over simulated
constant-effect and decaying books (Gaussian returns, fixed seeds). Findings are
calibration properties of the sensor, verified by reproduction; they do not depend
on any live number. `fleet_radar` remains publish-only with no consumers — this
document changes no code and no behaviour.*
