# Audit-backlog triage — 2026-07-23

Operator ask: *"check the lever authority and audit backlog for an optimal
outcome."* This is that triage. **One item was safely Claude-actionable and is
fixed; every other open finding is real-money-gated or data-starved and is
routed, not touched.** No real-money code or lever authority changed.

## What was fixed (safe, this branch)
| finding | source | action |
|---|---|---|
| `fleet_radar.py` deploy-orphaned | `audit_deploy_coverage` (1 ORPHANED) | Added to **both** gating lists in `railway-redeploy.yml` (`paths:` + the freqtrade-bots `grep`). Audit now exits 0. |

Why it was safe and correct: `fleet_radar.py` is a **shadow, publish-only organ**
already COPY'd into `Dockerfile.freqtrade` and looped in `run_all.sh` — (cl)
intended it to auto-deploy and said so, so the omission was a **bug, not an
exception**. A radar-only future edit (e.g. the `slope_t` fix from `RADAR_TRAJECTORY_AUDIT_2026-07-23.md`) would otherwise merge green and never reach
the container — the frozen-service class. The fix is a workflow-file edit (the PAT
can push it) and touches only the shadow `freqtrade-bots` service, whose
redeploys have not wiped the paper DBs since the 2026-07-03 `/freqtrade/persist`
volume.

## Lever authority — 5 findings, ALL routed (no change made)
`scripts/audit_lever_authority.py`. Each "fix" the audit offers (widen the bound /
register a lever / declare an exception) is either a **real-money authority
change** (operator-only by doctrine) or premature. None is a safe Claude change.

| lever / knob | verdict | why NOT touched | route |
|---|---|---|---|
| `live.funding.enter_apr` `[0.031, 0.075]` | INERT-PINNED | Decisive modal value **10.5 lies outside the bound** (1.4× the hi) — this is the **known FUNDING_ENTER_APR units bug** (HL-hourly `24×365` ported to Lighter's 8h settlement as a bare constant) wearing a lever hat, not a resolution nit. Re-bounding a **live real-money** entry gate is operator-only. | 28-Jul review |
| `xp.funding.enter_apr` `[0.031, 0.075]` | INERT-PINNED | Same units root-cause; this is the judge's experiment arm that **promotes into** `live.funding.*`. Resolving the units on the live lever resolves this. | 28-Jul review |
| `taker.sl_cooldown_h` `[0, 24]` | DARK | **Shadow** lane, n=11 < 30 — cannot tell a pin from noise. Not a defect; **self-resolves at n≥30**. | wait (no action) |
| `lighter_funding_bot.py:EXIT_APR` | UNLEVERED | **Real-money** constant, decides `*_decay/*_flip` (36% of gross loss, 67% of closes). Whether a loss-decisive real-money knob *should* be growth-rail-reachable is a design decision; doctrine says real-money knobs stay operator-only, so "unlevered" may be correct — **but ratifying that (a declared exception) is a review call, not a unilateral Claude assertion** (a false-OK on a real-money health finding is the worst direction). | 28-Jul review |
| `lighter_funding_bot.py:HARD_STOP` | UNLEVERED | Same as EXIT_APR (59% of gross loss, n=8). This is the `FUNDING_HARD_STOP` already surfaced by `cf`/`ch` (the withdrawn +$21.32; shadow control arm set to 0.10). | 28-Jul review (already open) |

**5 COARSE warnings** (non-fatal, no action): `live.funding.max_hold_h`,
`taker.brk_range`, `taker.dip_range`, `taker.max_hold_h`, `xp.funding.max_hold_h`
— most of each bound's width has no observation. A wide bound the book has not
explored is **headroom, not a bug**; the taker ones are shadow. Noted only.

## Venue-purity backtest backlog — routed (data/operator-gated)
`audit_venue_purity` passes on shipped code but its **advisory** section lists
**22 undeclared backtests, 5 cited by a live real-money bot** as justification for
a constant moving money today (the funding backtests loading Hyperliquid — the
known HL-vs-Lighter issue). Resolving means either re-running on **Lighter's own
~438d tape** (needs DB/data this container does not have) or **declaring** each in
`BACKTEST_VENUE_OK` with a reason (the operator's call on which cross-venue uses
are legitimate). CLAUDE.md already names this a "separate, larger effort."

## The optimal outcome, stated plainly
The backlog's shape is: **one safe deploy-plumbing fix** (done) and **a set of
real-money / data-starved findings whose correct resolution is a review decision,
not a code change.** Making those changes unprompted would either move real money
or file a false-OK — both worse than leaving them cleanly surfaced. So the optimal
outcome is exactly this: fix the one, route the rest with enough context that the
28-Jul review can act without re-deriving them.

---

*Other GUARD_ONLY audits checked this pass and CLEAN: `audit_image_imports`
(20 images OK), `audit_sdk_pin` (real-money wheels pinned). Lever-authority
numbers are as of the last `--measure`; refresh (read-only, needs DB) before
arguing with a figure. This document changes no code.*
