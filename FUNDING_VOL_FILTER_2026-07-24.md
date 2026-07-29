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

## [2026-07-29 AUDIT CORRECTION — read before citing the +$44.52]

The 29-Jul work-audit's adversarial re-review (methodology agent, findings
CONFIRMED against the scripts) tightened three things about this document,
none of which was honoured by the go-live citation trail ((dq)/(ds), PR #95,
28-Jul review §1 config note):

1. **The baseline is unstable by the size of the whole claimed edge.** The
   SAME harness, gate, slip and nominal window produced baseline **+$33.47**
   on the 23-Jul fetch (`FUNDING_GATE_LIGHTER_2026-07-23.md`, halves both
   positive) and **+$2.44** on this doc's 24-Jul fetch (h1 NEGATIVE) — the
   harness commits in between are comment-only, so a one-day universe
   recomposition + window slide moved the baseline ~$31 and flipped a half's
   sign. The "needs to survive a re-fetch" caveat above was written and then
   never exercised: **no re-fetch was run before the filter went live on both
   real-money arms.** The +$42 improvement is the same order as the harness's
   own day-to-day sampling noise.
2. **The pre-registered bar FAILED; the go-live claim substituted a weaker
   one.** `study_funding_vol_filter.py` pre-registers "both-halves AND
   all-thirds positive at BOTH slips" and its own verdict block prints
   `lowvol50: not robust` / mechanism `NOT supported` (middle third −$5.3).
   The citing docs carried "both halves, both slips" — the relaxed bar —
   under a "REAL mechanism" headline. Any future citation should carry the
   script's own printed verdict.
3. **The shipped rule diverges from the measured rule on the wildest
   cohort.** The study fails CLOSED on a missing vol read (fresh listings'
   first ~3d mechanically excluded from every filtered variant); the live
   `_vol_filter_veto` fails OPEN (no read → never vetoed) — deliberate and
   fail-safe, but it means the measured +$44.52 never included the coins the
   live rule admits blind.

**What stands:** direction (calm-half helps, reverse control loses),
methodology (no lookahead, cost-consistent, point-in-time percentile), and
the risk shape (entry-skip only, kill switch `FUNDING_VOL_FILTER`, SafetyRails
senior). **What does not:** the magnitude as canon. Operator options: leave ON
(bounded downside — it can only skip entries) and treat the magnitude as
unproven, or route the re-validation (≥2 fresh fetches + the 438d tape, the
audit's O-item) before the next config decision leans on this number.

### [2026-07-29 RE-VALIDATION — snapshot #3, independent fetch: the registered bar PASSES this time]

Run per the operator's "proceed" (29-Jul): fresh 180d/top-25 fetch (no cache
— a genuinely independent tape from both prior snapshots).

| read | baseline | lowvol50 (LIVE) | highvol50 (reverse) |
|---|---|---|---|
| P&L @0.5bps | +$10.65 | **+$27.45** | +$27.04 |
| P&L @2bps | −$0.49 | **+$21.49** | +$18.16 |
| maxDD | −52.5 | **−14.3** | −60.9 |
| halves+thirds at both slips | no | **YES — ROBUST** | no (mid third −50.3) |

- **The pre-registered bar (halves + all-thirds at both slips) PASSES on an
  independent fetch** — the 24-Jul failure is not reproduced; the script's
  own verdict block prints `lowvol50: ROBUST` this time. The go-live
  survives re-validation in direction AND, now, on its own registered bar.
- **The honest shape of the edge moved**: baseline printed a THIRD different
  number (+$33.47 → +$2.44 → +$10.65 — instability confirmed), and the
  reverse control was headline-positive this snapshot (killed only by its
  middle third). On this tape the filter's measured benefit is primarily
  RISK (maxDD −14 vs −52/−61) with a ~2.5x P&L edge over baseline — not the
  24-Jul "18x". Treat the filter as a validated drawdown-shaper with a
  positive P&L tilt; no snapshot's magnitude is canon.
- Verdict: **KEEP `FUNDING_VOL_FILTER=on`** (independent-fetch robust,
  risk benefit consistent across all three snapshots). Outstanding: the
  438d-tape run (needs a longer fetch window than a live session should
  spend); the fail-open fresh-listing cohort divergence stands as
  documented above.
