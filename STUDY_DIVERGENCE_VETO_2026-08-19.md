# STUDY — divergence-conditioned harvesting (2026-08-19)

**Growth study #1 admitted at (qa)** (*"the scout already computes
`funding_divergence` and NO harvest book reads it"*), run under the 19-Aug
fleet-wide audit. Driver: `scripts/study_divergence_veto_2026-08-19.py` —
decision rules R1–R6 pre-registered in the header before any result existed.

## Verdict: REFUSED WITH EVIDENCE — and the (qa) prior is WITHDRAWN

Two independent kills, both from the pre-registered rules:

### 1 · The mechanism row refutes the prior (the rule that mattered most)

(qa) named the class a divergence veto would screen: *"5 of the Farmer's 7
stops were LIT shorts (−$9.17) with LIT the standing market-wide extreme."*
Graded at entry against the venues' own settled series:

| stop row | Lighter apr | HL apr | divergence |
|---|---|---|---|
| LIT 13-Jul ×2 | +0.11 | −0.37 | +0.48 |
| LIT 18/19/20-Jul ×3 | +0.11 | +0.11 | **0.00** |
| LIT 22-Jul | +0.46 | +0.11 | +0.35 |

The cluster's core is **agreement, not divergence** — "market-wide extreme"
was the correct phrase and is exactly why a divergence veto cannot touch this
class. Per the pre-registered mechanism row: **the prior is withdrawn.**

### 2 · The veto has NO population at the books' own gates (R3: UNDECIDED)

Pooled `lighter_funding_bot` machine (Farmer LIVE 117 + Farmer SHADOW 167 +
Garrett 16 graded crypto closes; coverage 100/100/89%, HL bench declared —
binance/bybit geo-blocked from this runner):

| \|div\| bucket (apr) | n | total | mean | win |
|---|---|---|---|---|
| [0.00, 0.25) | 289 | +$9.08 | +0.031 | 55% |
| [0.25, 0.50) | 11 | −$4.70 | −0.427 | 36% |
| ≥ 0.50 | **0** | — | — | — |

**Zero of 300 pooled entries ever occurred at \|div\| ≥ 50pp** — the grid's
smallest cell. The books' own gates (majors-weighted supply, volume floors)
structurally never admit an entry during a genuine divergence; the ZK
−51.7%-vs-+10.9% snapshots in (qa) are real venue events that the harvest
books never trade. n_vetoed = 0 at every D ∈ {0.5, 1.0, 2.0} ⇒ UNDECIDED per
R3, no ship either way, and nothing to wire.

## The one lead recorded (below-grid, NOT a setting)

\|div\| ∈ [0.25, 0.50) is negative everywhere it has sample: pooled
−$4.70/11 (win 36%), carry informational −$2.52/5 (win 0%), carry [1,2)
−$1.19/2. Direction consistent, n tiny, below the pre-registered grid, and
untested against R5 (apr-band confound). If it is ever tested it needs its
own pre-registration at D=0.25 with fresh sample — re-mining this window is
the (I21) sin.

## What this closes

The "no harvest book reads `funding_divergence`" observation is now
explained rather than outstanding: **there is nothing for a harvest book to
read at its own entry gate.** The signal's only measured use remains the
scout's divergence *tickets* (a different consumer, already live). Data
caveats declared: HL-only bench (2 of 3 scout venues geo-blocked here);
CTR/DATA/kBONK unmapped (9 rows); carry never pooled (pre-31-Jul rows carry
the (nc) phantom accrual).
