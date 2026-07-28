# Funding Farmer — coin-QUALITY (vol-character) entry filter study (2026-07-24)

Run: `scripts/study_funding_vol_filter.py` (through the canonical
`backtest_funding_lighter.run` via its new `entry_ok` hook — one harness, no
diverging copy). 180d Lighter tape, 25 markets, gate 0.05 TRUE (the live gate),
persistence-parity fix in. **Lighter-only, per doctrine.**

## The hypothesis (pre-registered by the repo's own evidence)
The `(ce)` farmhand verdict killed per-coin **P&L memory** (persistence −0.016,
dead at the premise) but measured **CHARACTER persisting**: realized vol
**+0.830** across halves. The Farmer's losses are price risk eating thin carry —
so the testable filter is: **enter only coins whose trailing 14d realized vol is
in the calm half of the cross-section** (point-in-time percentile, no lookahead;
vol needs ≥3d of candles before it's trusted). P&L-based "quality" was NOT
tested — the repo already proved that sensor is noise.

## Result (gate 0.05, both slips; 3 filters tested — multiplicity stated)

| filter | P&L @0.5bps | halves | thirds | maxDD | n | P&L @2bps | halves |
|---|---|---|---|---|---|---|---|
| baseline | +$2.44 | −1.7 / +6.4 ❌ | +15.2 / −40.9 / +23.5 | −54.1 | 1308 | −$7.37 | ❌ |
| **lowvol50** | **+$44.52** | **+22.1 / +22.3 ✅** | +26.4 / **−5.3** / +25.6 | **−17.8** | 1021 | **+$36.86** | **+18.0 / +18.8 ✅** |
| lowvol75 | +$5.90 | −7.3 / +10.4 ❌ | +11.8 / −27.2 / +18.9 | −49.1 | 1244 | −$3.43 | ❌ |
| highvol50 (reverse) | −$17.27 | −2.8 / −15.9 ❌ | +12.5 / −35.3 / +6.1 | −63.7 | 1309 | −$27.09 | ❌ |

## Why this reads as a REAL mechanism, not a fitted number
1. **Predicted in advance** — the filter variable (vol) is the one trait `(ce)`
   measured as persistent; this was not a search over features.
2. **Monotone dose-response** — highvol50 < baseline < lowvol75 < lowvol50: the
   more wild coins cut, the better, in order.
3. **The reverse control LOSES** (−$17 to −$27, worse than baseline both slips) —
   the wild half is where the damage lives, exactly the mechanism story.
4. **Balanced both-halves at both slips** (+22.1/+22.3 — not one lucky half) and
   **maxDD cut 3×** (−54 → −18) with n still 1021 (the filter starves nothing).
5. Slip-robust: the improvement (~+$42 over baseline) dwarfs the slip band.

## Honest limits
- **The middle third is still slightly negative** (−$5.3 @0.5bps) — the filter
  cuts baseline's middle-third catastrophe by 87% (−40.9 → −5.3) but does not
  flip it. Strict all-thirds robustness is NOT met; both-halves at both slips is.
- **One 180d window, today's top-25 universe** — the gate study showed this
  harness's universe recomposes daily; the number needs to survive a re-fetch.
- **3 filters tested** (multiplicity stated); lowvol50 was the primary (median
  cut on the `(ce)`-corroborated trait), not the best-of-N.
- The study's percentile is vs the 25-market backtest universe; the live bot's
  scanned universe differs (turnover floor, spread gate) — the live
  implementation must rank within ITS OWN universe.

## Recommended route (doctrine: restrict-only, shadow-first, judge-promoted)
This is an ENTRY filter — restrict-only by construction (it can only skip
entries, never force one). The designed pipeline for exactly this class of win:
1. Implement in `lighter_funding_bot.py` **default OFF** (env
   `FUNDING_VOL_FILTER`, off unless set) — code ships inert.
2. Run it as an **experiment-judge candidate** on the `-lshadow` twin (the
   judge's paired ≥7d/≥30-close promotion bar, one candidate at a time — never
   a side-by-side hack that confounds the control arm, the `(ch)` lesson).
3. Promotion to the live arm is the judge's call on live-shadow paired
   evidence, as designed. No shortcut.

*Harness change that enabled this: `backtest_funding_lighter.run(...,
entry_ok=None)` — an optional entry-site predicate, default None = byte-identical
behaviour (the baseline row above reproduces the unfiltered +$2.44/−$7.37
exactly, which is the parity proof).*
