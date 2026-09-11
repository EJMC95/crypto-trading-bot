# Settlement Study Log

Weekly evidence accumulation for the Lighter/HL funding-settlement flow study
(`scripts/study_funding_settlement.py`). Each line is one weekly run. The thesis
graduates to REVISIT only if ALL hold: a hot group reaches n_ev>=500, its
pre/post headline exceeds its own 2se band, |cumulative 15m effect| > 10bps
(round-trip friction), and both half-samples agree in sign. Data-accumulation
only — never trade or change a bot based on this.

2026-07-15 · hot-neg n=151 pre=-0.80 post=+5.05 (2se 8.53/8.78) · hot-pos n=34 pre=+7.25 post=-1.29 (2se 27.21/24.37) · halves: h1 -3.82 (2se 11.11 n124), h2 +9.81 (2se 12.50 n61) · verdict: still sub-friction
