# Evidence review — 2026-07-15 (first autonomous run, inline)

No urgent action. First review after the 14-15 Jul Lighter-first pivot.

| Alert key | Verdict | Why |
|-----------|---------|-----|
| live-shadow-gap | **resolved** | Funding Farmer gap now ~0.2pp (live +0.46% vs shadow +0.22% of equity); the 13-Jul +5.4% divergence closed after the 14-Jul constant-risk re-clip |
| veto:ADA | **active** | Confirmed current: ADA (stop rate 6/10, 30d) + kBONK (slip 18.7bps) |
| veto:ADA,kBONK | stale | 11-Jul add event superseded by later veto changes |
| disloc:KAITO | stale | Census evidence recorded (29 symbols tracked); weekly snap-back-census-check owns the gate |
| disloc:EIGEN | stale | As above |
| census:50 | stale | Milestone notice; weekly census check is the standing review |

## New evidence
- funding-lighter live+shadow rows publish `pnl_abs` but `pnl_pct` NULL — % gap monitoring must derive from equity.
- Ticket Taker lens grading: only `long-breakout` has closes (n=2, +$4.15) — all lenses below the n≥10 bar.
- No Proving bot passes all four go-live gates yet (Ready-for-live section correctly empty).

*Verdicts published to bot_state `evidence-review`; the dashboard banner consumes them
(resolved/stale clear, active stay). Daily task `daily-evidence-review` takes over at
07:33 local; fleet-alerts history is append-only and untouched.*
