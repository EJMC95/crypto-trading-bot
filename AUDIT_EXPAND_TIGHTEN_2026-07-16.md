# EXPAND↔TIGHTEN balance audit — 2026-07-16 (v3, verify COMPLETE)

Provenance: multi-agent audit (10 subsystem mappers -> synthesis ->
adversarial verify, 3 lenses per target: doctrine / money-safety /
effectiveness; 131 agents total), run 16-Jul on the operator's instruction
"ensure the expand vs tighten is balanced for real money and all other bots
too". DB ground truth at audit time: Tide Rider live 0 closes ever / -$0.23
mark; Funding Farmer 14 closes, lifetime -$0.30, 7d +$2.38.

FIX VERDICTS (the shipped balance commit 0f9a988, each attacked by 3
refuters): F1, F2, F4, F5, F6, F7, F8 SURVIVE 3/3. F3's landed-write guard
was REFUTED 2/3 — the rail authors' unlocked fallback ignored save_state's
False on a reads-OK/writes-failing DB, so a never-persisted payload read as
"landed" (one refuter reproduced it with a store stub) — REPAIRED same
evening: write_levers/release_levers now return None on a failed durable
write (selftest pins the degraded-store contract).

FINDING STATUS KEY — SHIPPED 16-Jul (verify-confirmed): IMB-01, -13, -14,
-15, -30, -31, -32. VERIFIED-REAL/SURVIVING open items and REFUTED
(do-not-build) items are marked per finding below. "Contested" = refuter
lenses split; treat as low-confidence until re-argued at the review.

## Balance matrix

| Subsystem | Restrict actuators | Expand actuators | Both directions reachable? | Time anchor |
|---|---|---|---|---|
| Board LIVE lane (real $, `live.clip_scale`) | DOWN reflex x0.75 (7d realized hole -$10 / lifetime -$20 backstop / holder rows keep full -$10 mark bar / fresh ≤6h divergence; lifetime rule on dark ledger; blind-HOLD of an in-force restriction); hurting-grade release; 30-min lever leash | UP ladder 1.0→1.25→1.5: dark window fail-closed, cohort fresh+non-harming (≥-$1), ≥1 prover (≥30 lifetime + ≥5 window closes + positive 7d), green light, dd>-2%, venue calm, 24h cooldown, 1h post-release gap, top step needs measured HELPING | YES post-diff (old EVERY-row 30-lifetime-closes bar was unreachable — Tide Rider closes 0 by design; prover bar clears once Funding Farmer's 14 lifetime closes reach 30, ~1-2wk at current rate) | rolling 7d; down instant |
| Board growth rail (paper Gap Scout) | TTL auto-revert + immune quarantine; **extra_exchanges revert broken (open)** | quiet-hours widen ladder 24/48/96h + HELPING bar discount x0.75 (12h floor) | expand yes; restrict yes except venue hot-add | rolling census |
| Board proposals (advisory) | restrict proposals (EVBOARD_MODE=shadow, zero consumers) | expand suggestions → phone/review only | advisory by doctrine (earn-your-wiring) | rolling |
| Brain (bot_learn/brain_stats) | L4 mults ≤1.0 (n≥30/3-run streak, EMER fast-path), lens grades feeding taker veto | none — reduce-only doctrine | restrict heals via v3 14d decay; v2 fallback's era anchor never heals (open) | rolling (v3) / lifetime (v2) |
| Fleet risk | L2 long veto (enforce, budget 20), 7d dd governor 1.0/0.5/0.25, light+dd legs of the live up-gate | none by design | veto heals as positions close; governor evidence wiped by cohort flap and dd=0.0 passes the live gate leg (open); short budget unenforced (open) | instant + rolling 7d |
| Scout tuner | brain-veto guard (senior), proprio HURTING drop, stateless TTL revert ≤2h10m | starving not-worse walk, winner/HELPING improve-both-halves walk, exit sweep, scout diet + top_n | yes, but every gate scores closed_net only — blind to unrealized (open); veto evaporates on stale brain while expand runs (open) | rolling 48h tape |
| Judge + incubator | fade / prop-fade / blind-cycle release, MAX_DAYS abandon, lifetime done-list, admission filter | xp.funding.* twin levers; live.funding.* paired promotion (7d/30-close/both-halves); offspring proposals | promotion bar reachable; candidate flow self-exhausts + keep-bar degrades with age (open) | earn rolling 7-14d vs keep lifetime |
| Scout + Ticket Taker (shadow) | stress veto 15bps, scout-freshness fail-closed, lens veto, MAX_OPEN=6, zombie give-up, gov/L2 consumption | lever-widened conviction/emission bars via tuner | yes; divergence emission bar operator-only (open) | instant + rolling |
| LIVE bots + venues/ | kill switch, boot cap gate, deployed-notional cap, daily-loss flatten+durable halt, equity guard, hard/blind/catastrophic stops, slippage band + reduce-only, cooldowns, entry gate stacks, quarantine/HURTING reverts | live.funding.* + live.clip_scale consumption (evidence-earned, TTL'd) | yes; coin-vetoes freshness hole (open); slot-minting from down-scale fixed in diff | instant; lever paths rolling |
| Family/spot shadow books | brain mult, L2 veto, dd governor, panic x0.5, protections/cooldown/throttle, 10% daily rail, VENUE gate | none — no tuning lane (doctrine) | restricts heal; pulse_panic fossil can restrict forever (open) | rolling |
| Immune / regen / proprioception | filtration, lever quarantine, HURTING verdicts + consumer-side live reverts, incubator gene skip | HELPING unlocks (taker walk, scout diet, gapscout bar discount, live top step) | verdicts heal only by episode amnesia (open); regen/immune coverage mismatch (open); revert contamination fixed in diff | rolling episode windows |
| Pulse / sentinel / gapscout / funding-carry | panic halving, sentinel sev/source bars, booking-honesty constants, carry entry/exit stack + venue allowlist | sentinel self-graded confidence (advisory), gapscout widen levers | mostly; sentinel learning lifetime-anchored (open); gapscout loop can register benefit but not harm (open) | instant / lifetime learn |

## Findings

### IMB-01 [high] — SHIPPED 16-Jul (verify-confirmed)
Live-lane proprioception verdicts were contaminated during a consumer-side revert: stances built from active_levers ignored quarantine/live-hurting hooks, so default-arm live trades were graded as lever episodes — a hurting verdict on real money could clear on evidence that never measured the lever, re-arming it.
- evidence: fleet_tuning.py:286-316 (_live_hurting revert) vs fleet_proprioception stances from active_levers (no filter); grade_live uses actual ledger trades; verdict window displacement eps[-10:].
- fix shape: already-fixed-in-diff — fleet_proprioception.observed_active() drops quarantined levers (any lane) and live-hurting lighter-live levers from the observed stance set, mirroring get_lever's scoping; episodes close as 'released' and none open during a revert; selftested. NOTE: this makes IMB-08's amnesia the sole heal path by construction — pair them at the 21-Jul review.

### IMB-02 [medium] — VERIFIED REAL 3/3 (one refuter executed the dd_governor code)
One cohort publisher stale-flap (live Tide Rider publishes hourly vs the 65-min freshness bar) flips its equity venue to 'carried', changes the cohort key, and WIPES the 7d dd-governor sample series — dd recomputes as 0.0 on a single sample, snapping clip_scale 0.25→1.0 mid-drawdown, and the blanked dd=0.0 is 'not None' so it PASSES the board's deliberately fail-closed dd leg on the real-money up-ladder.
- evidence: fleet_risk.py:407 (venue='carried'), :418-423 (cohort key + sample reset), :240-244 (single-sample dd=0.0); evidence_board.py fr_ok leg accepts dd=0.0 > -0.02.
- fix shape: Keep the carried base's REAL venue in the cohort key (carry already keeps fleet_equity comparable), reset samples only when the bot SET changes or a live book is substituted by its shadow; alternatively rescale retained samples by the cohort-equity ratio instead of wiping.

### IMB-03 [medium] — VERIFIED 2/3 (money-safety lens: fail direction arguably tolerable)
The coin-quality veto is the only consumed payload on the live-money entry path with NO freshness gate, and its publisher stamps no updated/ttl_sec: a dead market-context service fossilizes the last veto set forever (restrict that never heals) or, if it died empty, silently disables the veto forever — violating the fleet's own updated+ttl_sec contract on the highest-stakes consumer.
- evidence: lighter_funding_bot.py:794-798 (load_state('coin-vetoes'), zero age check) vs the trend bot's fleet-risk read at lighter_trend_bot.py:452-460; market_context.py:244-245 publishes only ts+coins; publisher runs on a separate service (Dockerfile.marketcontext, not run_all.sh).
- fix shape: Publish updated+ttl_sec on the coin-vetoes payload; gate the consumer on freshness (stale → empty veto set, matching its documented fails-open direction) and log loudly when a stale set is discarded.

### IMB-04 [medium] — VERIFIED REAL 3/3
pulse_panic halves stakes on a payload with NO freshness check in the family bot and all four freqtrade strategies: a fossil panic=true from a dead market_pulse keeps halving every new entry indefinitely — the exact 'alive but sick / 39h fossil' class, on an input fleet_immune does not scan.
- evidence: lighter_family_bot.py:319-327 (raw latest.panic, 15-min cache only); user_data/strategies/DayTraderV5Gated.py:395-403 same; market_pulse.py:258-259 publishes ttl_sec=3600 nobody reads; fleet_bus.is_fresh exists and is used for every other key.
- fix shape: Gate pulse_panic on the payload's updated+ttl_sec (reuse fleet_bus.is_fresh); stale → panic=False. One-line parity in each consumer.

### IMB-05 [medium] — REFUTED 2/3 — deliberate exemption; document, don't build
SHORT_BUDGET=12 is computed, colors the light, and is published, but NO consumer vetoes new shorts — the taker explicitly exempts them and short-capable books run (taker divergence shorts; the live Funding Farmer's short book is counted into fleet_short). The pileup scar this file exists for is direction-agnostic, and the design note only justifies the long veto ignoring shorts, not leaving the short budget unenforced.
- evidence: fleet_risk.py:140 (SHORT_BUDGET), :369-371 (shorts only move the light); lighter_ticket_taker.py:359-362,:400 ('shorts unaffected'); grep shows no short_positions check in any consumer.
- fix shape: Mirror the fresh+enforce+fail-open veto for new shorts in the taker's divergence-short path; document the Funding Farmer's treatment (honor or exempt) next to the SHORT_BUDGET definition.

### IMB-06 [medium] — survives 2/3 (doctrine lens dissents)
fade_check — the keep-bar on a live real-money promotion — uses the CUMULATIVE mean since promoted_ts, so it degrades as the promotion ages: months of good early trades mask a recent turn negative, and if fleet_proprioception is dark (prop_fade fails safe OFF) the degrading cumulative bar is the ONLY release signal on live.funding.*. The earn-bar was a fixed 7-14d window; the keep-bar has no rolling window at all.
- evidence: experiment_judge.py:177-184 (mean over whole since-promotion window), :429-432 (unconditional re-assert while not fading), :198-208 (prop_fade False on dark organ).
- fix shape: Add a rolling fade bar alongside the cumulative one: trailing FADE_N closes (or trailing 7d) mean < 0 also releases — earn-bar and keep-bar then share a time anchor.

### IMB-07 [medium] — survives 2/3 (doctrine lens dissents)
The judge's candidate flow permanently self-exhausts: a lifetime done-list over a FINITE universe (3 statics + ≤6 incubator lever-sets), dedupe by NAME only so three incubator names collide by content with the statics (up to ~3-6 weeks of the one-at-a-time slot re-testing identical levers), and ledger-dark days still count toward MAX_DAYS so a long outage burns a candidate for nothing. After ~2-3 months the expand pipeline idles at 'queue exhausted' while every restrict actuator stays reachable — the only-say-no convergence the rail was built to prevent.
- evidence: experiment_judge.py:260-268 (done skipped forever), :387/:425 (never pruned), :369+:382 (blind days accrue), :249-257 (name-only dedupe); strategy_incubator.py:81-85 (finite grids), :249 ('xp-enter_apr-0.3' == static 'enter-gate-0.30' by content).
- fix shape: Dedupe candidate_pool AND the done check by canonicalized lever-set key (tuple(sorted(levers.items()))); age done entries (retry-eligible after N weeks or on a regime-oracle change / epoch-versioned names); exclude ledger-dark cycles from MAX_DAYS accrual. Ship the three together — content dedupe alone removes today's only accidental retry path.

### IMB-08 [medium] — survives 2/3 — now the SOLE heal path post-IMB-01 fix; pair at review
Restrict verdicts heal only by amnesia while expand verdicts self-refresh: once HURTING lands every consumer stops the lever, no new episodes generate (now guaranteed by the IMB-01 fix), and lever_verdicts recomputes forever over the same frozen last-10 episodes — decay comes only from OTHER groups' churn through the 120-episode cap (~2-3 weeks, undocumented). On live.funding.* this is a ratchet: a frozen hurting verdict instantly prop-fades any future promotion and the incubator keeps skipping the gene for the whole amnesia period.
- evidence: fleet_proprioception.py:391-443 (verdicts from stored ledger only), :524 (episodes[-EP_CAP:] sole decay), :217-248 (released stance → no episodes); consumers in tuner/board/judge/incubator/get_lever.
- fix shape: Give verdicts an explicit evidence half-life (expire N days after the newest contributing episode) and/or a bounded probation: one TTL'd re-assert at the smallest notch after cool-off to gather fresh out-of-sample episodes.

### IMB-09 [medium] — REFUTED — dead code only, fails safe; housekeeping not risk
Regen's repair map and immune's detection map don't intersect where it matters: REPAIRABLE includes scout-tuner but fleet_immune never inspects it (dead code, unreachable restore), while fleet-proprioception IS immune-checked and is exactly the compounding-stateful organ that steers live-money levers — yet has no restore path, and no verdict consumer checks the immune sick list before acting on its verdicts.
- evidence: fleet_regen.py:52-56 (REPAIRABLE incl. scout-tuner) + :156-161 (gated on immune sick list) vs fleet_immune.py:150-204/:262-263 (no scout-tuner invariant or key); proprioception invariants exist but organ absent from REPAIRABLE; verdict consumers never consult 'fleet-immune'.sick.
- fix shape: Add a scout-tuner invariant to organ_invariants (or drop it from REPAIRABLE); add fleet-proprioception to REPAIRABLE with an empty episodes/verdicts baseline; have verdict consumers treat a fresh-immune-flagged-sick proprioception as dark.

### IMB-10 [medium] — survives 2/3
Every tuner replay gate scores closed_net ONLY — end-of-tape open positions are invisible: the exit sweep can clear its +$2/both-halves margin purely by DEFERRING losses (wider SL leaves losers open; MAX_HOLD=72 on a 48h tape can never hold-exit and is systematically survivorship-favored), and the starving path enacts a notch on taken>0 with ZERO closed outcomes (common at MIN_SNAPS=60, ~2.5h halves) — logged as 'evidenced' while possibly deep in unrealized loss.
- evidence: lighter_scout_tuner.py:136-146 + :286-301 (closed_net comparisons), :250-262 (taken>0, not closed>0), :105 (SWEEP_HOLD 72) vs lighter_ticket_replay.py:79 (48h tape) and :219-230 (unrealized computed, never read).
- fix shape: Score closed_net + unrealized (survivors marked at last tape price) in not_worse and sweep_exits; exclude grid hold values ≥ the tape's actual span; require closed≥1 (or MTM the fills) before enacting a starving notch.

### IMB-11 [medium] — REFUTED 2/3 — do not build without fresh evidence
Compound expansion across the two tuner lanes is never jointly validated and structurally cannot be: the scout-diet widen (no replay gate, 'zero trading surface' rationale) changes FUTURE emissions while the taker-bar widen is replay-validated on a tape recorded under the NARROWER emission — newly emitted 0.10-0.15 dip tickets become immediately tradable through a bar whose evidence tape contained no such tickets; ticket_top_n has the same leak alone (conviction-ranked extras can pass the taker's bars and trade).
- evidence: lighter_scout_tuner.py:84-99/:308-352 (diet, no replay gate) vs :78-83 (taker ladder max 0.15); fleet_tuning.py scout hi 0.25 overlaps taker hi 0.15; joint interaction check (:431-440) is taker-internal only.
- fix shape: Freeze diet widening for any lens whose taker bar is off-default (or hold the taker walk at scout-emission-bar-minus-one-notch per lens) so the recorded tape always leads the tradable surface.

### IMB-12 [medium] — VERIFIED REAL 3/3
gapscout.extra_exchanges is an expand whose promised TTL auto-revert is unreachable: hot-added venues (kucoin/gateio/mexc) join the scan set for the LIFETIME of the process — when the lever expires nothing removes the venue or rebuilds sym_map. The rail's core contract ('auto-revert is the resting state') holds for the scalar levers (re-read per scan) but silently not for venues.
- evidence: cross_exchange_arb.py:672-676 (add-only loop), :570-585 (no removal counterpart; exchanges dict only grows) vs :669-671 (scalars re-read each scan); contract at fleet_tuning.py:17-20.
- fix shape: Each scan derive the intended venue set = EXCHANGES + current lever value, drop venues no longer asserted and rebuild sym_map; or document one-way-until-redeploy and surface the divergence (census.venues vs lever) to the board/immune.

### IMB-13 [medium] — SHIPPED 16-Jul (verify-confirmed)
Partial cohort visibility disarmed the live DOWN reflex and actively RELEASED an in-force restriction to x1.0: the cohort gate ran before the divergence/hurt checks, and the explicit-release write converted 'assert nothing' into a live.clip_scale=1.0 write — a vanished bot_pnl row cancelled a 0.75 down-scale mid-divergence, contradicting the file's own 'tighten never weakens on missing data'.
- evidence: Pre-diff evidence_board.py:467-470 preceding :481-512; release fired on desired=None regardless of cause.
- fix shape: already-fixed-in-diff — hurt/gap now evaluated on visible rows BEFORE the cohort gate (divergence is rows-free), and run_once's blind-hold re-asserts a prior <1.0 restriction whenever cohort/window aren't fully visible; release happens only on measured healing. Selftests cover both partial-cohort cut paths.

### IMB-14 [medium] — SHIPPED 16-Jul (verify-confirmed)
Tide Rider's effective tighten bar silently doubled -$10→-$20: the 7d realized window is structurally blind to a position HOLDER (0 closes ever by design), leaving only the 2x lifetime backstop — mark-to-market bleed between -$10 and -$20 that previously cut clips no longer did.
- evidence: Pre-diff _hurt_why applied the -$20 backstop whenever the window was present; fetch_realized_window is realized-closes-only.
- fix shape: already-fixed-in-diff — a row with ZERO window closes keeps the FULL -$10 bar on its mark-anchored lifetime pnl ('(mark)' branch), selftested with a -$12 holder cutting to 0.75.

### IMB-15 [medium] — SHIPPED 16-Jul (verify-confirmed)
Sticky 'urgent' flag defeated the BRAIN_MULT_ENGINE=v2 kill switch: the v2/fallback branch computes ev={} so e.update never overwrote a previously-set urgent:True — formerly-urgent entries kept publishing on streak<3 after the flip (or a silent brain_stats import failure), breaking the documented 'back to frozen 14-Jul rules' contract.
- evidence: Pre-diff bot_learn.py:624/:643-652/:660-661/:674.
- fix shape: already-fixed-in-diff — e['urgent'] = bool(ev.get('urgent')) normalized after every update, so urgent is re-earned every run and v2 restores the streak gate exactly.

### IMB-16 [low] — contested (split lenses) — low confidence
Kill-switch coverage gap: the header promises FLEET_RISK_MODE=advisory sends every consumer neutral, but only the veto consumers check mode — the taker and family bot apply the clip_scale governor on freshness alone, so the documented stand-down silently doesn't stand the restrict-side governor down.
- evidence: fleet_risk.py:20-21/:51; lighter_ticket_taker.py:342-346 (gov on freshness, mode only at :352); lighter_family_bot.py:800-815 same pattern.
- fix shape: Producer-side one-liner: publish clip_scale=1.0 when MODE=advisory (covers all consumers at once); correct the header either way.

### IMB-17 [low] — survives 2/3
The live Funding Farmer is counted INTO the long budget (its held longs feed fleet_long) but never reads fleet-risk — it consumes budget every other book must honor while its own long entries go unvetoed; the trend bot's 'only real-money LONG book counted but never checked' fix comment overlooked this second live book.
- evidence: fleet_risk.py:106-110/:331-342 (harvest into fleet_long); grep of lighter_funding_bot.py: zero fleet-risk reads; lighter_trend_bot.py:444-447 claim.
- fix shape: Wire the same fresh+enforce+fail-open long-entry skip into the funding bot's entry loop (longs only), or exclude it from the count and document the exemption (contrarian negative-funding longs are anti-crowding by thesis) next to PERPS_LS_BOTS.

### IMB-18 [low] — contested (split lenses) — low confidence
The tuner's senior brain veto fails OPEN while its expand path stays live: stale brain-lens-forward → lens_fwd={} → vetoed_lenses empty AND graded=0<75 satisfies the starving precondition, so a lens the brain ruled negative becomes widenable the moment the brain goes dark; the scout-diet side correctly goes fully neutral on the same staleness.
- evidence: lighter_scout_tuner.py:410-413 (lens_fwd={} on stale), :171-180, :219-221 vs :443-447 (diet neutral).
- fix shape: Skip taker-bar widening entirely on stale lens-forward (symmetric with the diet path), or carry the last fresh veto set under a longer staleness horizon.

### IMB-19 [low] — REFUTED 2/3 — do not build
Scout diet levers can be re-asserted forever with no outcome test and a release that may never fire: the only release is the lens reaching n4h≥75, and proprioception can never grade a diet lever HURTING by design — a widen that fails to deliver grades (the failure it exists to fix) is neither released nor measurable as bad.
- evidence: lighter_scout_tuner.py:327-351 (assert while graded<75, release only at floor); fleet_proprioception.py:424-428 (diet = helping-or-neutral only).
- fix shape: Fatigue release: stop asserting a diet lever for a cooldown window when its graded proprioception episodes show delta_grades==0 over N consecutive episodes.

### IMB-20 [low] — survives 2/3
Lever-registry coverage asymmetries: (a) the divergence lens — the one lens no fleet bot trades, whose grading throughput matters most — has NO scout-emission lever/ladder (SCOUT_DIV_GAP env-only), so its taker-side widening saturates at a fixed upstream bar with no autonomous heal path; (b) taker.dip_range's default 0.05 sits exactly ON its registry floor, so the rail has zero tighten room on the lens family with the fleet's worst validation record.
- evidence: lighter_market_scout.py:59/:82-85; fleet_tuning.py:145-156 (no scout.div_gap), :161-163 (dip lo==default) vs :164-181 (all others two-sided); lighter_scout_tuner.py:90-99 (SCOUT_LADDERS omits divergence).
- fix shape: Register a bounded scout.div_gap lever (lo 200 / hi 300, lane lighter-scout) wired into scout apply_tuning + a SCOUT_LADDERS entry; extend taker.dip_range lo (e.g. 0.02) or add a registry note that conviction-bar tightening is deliberately veto-only.

### IMB-21 [low] — REFUTED 3/3 — do not build
The tuner's brain-ruling floor mirrors the taker's veto via the SAME env var (TT_LENS_VETO_MIN_N) read in a DIFFERENT container: an operator override on one Railway service silently de-syncs the tuner's veto/winner/starving thresholds from the veto actually enforced — the tuner could widen a lens the taker is vetoing.
- evidence: lighter_scout_tuner.py:75 vs lighter_ticket_taker.py:372; separate services per fleet map.
- fix shape: Taker publishes its effective min_n and computed veto set in its bot_state payload; tuner consumes that, env fallback only when stale.

### IMB-22 [low] — survives 2/3
paired_eval enforces close floors on the FULL window (shadow≥30, live≥10) but none per half while requiring each half to clear the 0.5pp margin — a live arm split 9/1 lets a single close pass or veto a real-money promotion; the anti-luck core of the bar can rest on one-trade noise.
- evidence: experiment_judge.py:147-149 (full-window floors only), :150-162 (per-half means, no per-half n), :128-129 (_mean_pct averages 1 trade).
- fix shape: Per-half minimums (e.g. shadow ≥ min_closes//3, live ≥ 3) returning the 'floors' verdict when a half is too thin.

### IMB-23 [low] — survives 2/3
funding_proposals computes a get_lever-based default dict that is never used and compares alleles against a HARD-CODED base {0.40, 0.04, 72.0}: if the operator's env defaults drift, the incubator proposes an allele equal to the real default (a 7-14d judge slot proving x==x) and never probes the vacated value.
- evidence: strategy_incubator.py:229-231 (dead dict), :233 (hard-coded base), :247 (skip only allele==base).
- fix shape: Delete the dead dict; derive base from the funding bot's actual env defaults (same envs / imported constants).

### IMB-24 [low] — survives 2/3
The lens veto's n4h≥75 floor counts serially-correlated RAW emissions with no symbol/episode diversity: one persistent bad ticket on one symbol for ~6h can both veto the lens at the taker and freeze ALL tuner widening for it — a compounding restrict from ~1-2 independent observations, while the opposing expand needs both-halves replay improvement. Raw-field choice is a documented deferral, but the single-episode failure mode on sparse lenses is acknowledged nowhere. Heals on the rolling ~7-8d window, so false-positive risk, not a trap.
- evidence: lighter_ticket_taker.py:372-377; bot_learn.py:784-792 (episode fields eps4h/n_syms published, unconsumed); lighter_scout_tuner.py:172-180/:210-211.
- fix shape: At the 21-Jul review (per the documented replay-gated migration), add an eps4h≥k or n_syms≥k floor alongside n4h as ONE shared rule in the taker veto and lighter_scout_tuner.vetoed_lenses.

### IMB-25 [low] — REFUTED 2/3 — do not build
Event Sentinel playbook learning is lifetime-anchored with no decay: observed n/hit only increment and each new episode weighs 1/(4+n), so early evidence never ages out and a regime-shifted playbook confidence effectively cannot heal — contradicting the brain-v3 forgetting it explicitly cites as its model. Advisory today, but a review wiring a consumer inherits the anchor.
- evidence: event_sentinel.py:365-369 (increment-only, no timestamps), :293-295 (conf blend); brain_stats imported for philosophy only (:83-86).
- fix shape: Store per-episode grade timestamps (or decay n/hit at read time with brain_stats' half-life) BEFORE the 21-Jul review wires any consumer.

### IMB-26 [low] — REFUTED 3/3 — do not build
The Gap Scout learning loop can register benefit but structurally not harm, and its expand bar is the subsystem's weakest: bookings require net_eff≥0 so census pnl/W-L evidence is non-negative by construction; proprioception's gapscout grade is activity-only with no HURTING verdict possible and marks HELPING on ANY single found-activity episode (every other lane needs n≥2 + margin + majority) — one lucky census reset discounts the widen bars x0.75 for as long as the episode stays in the window, with no decelerator below baseline.
- evidence: cross_exchange_arb.py:389 (eligible = net_eff>=0); fleet_proprioception.py:429-432 (any(...) → helping, no floor) vs :416-419/:437-440; evidence_board.py:305-322 (bar_scale ≤1.0 only, no hurting counterpart).
- fix shape: Require MIN_EPISODES found-activity episodes (majority-found) for the gapscout HELPING verdict; add a hurting-equivalent (widened window shows only artifacts/depth-rejects and zero closes — census already carries implausible.count and depth_rejected) that inflates the quiet bars symmetrically (e.g. x1.5).

### IMB-27 [low] — REFUTED 2/3 — do not build
Family-bot bus-contract drift: (a) its inline fleet-risk read claims fleet_bus parity but diverges (missing ttl_sec defaults to 900s vs fleet_bus's stale; negative age accepted), so the same payload restricts 7 books one consumer treats as no-evidence; (b) the dormant freqtrade twins consume brain mult + L2 veto but were never given the dd governor — a Railway auto-deploy resurrection (documented trap) would trade ungoverned through a fleet drawdown.
- evidence: lighter_family_bot.py:791-804 vs fleet_bus.py:63-67 (contract 'in exactly one file' now has a drifted copy); user_data/strategies/TrendMomoV1.py:123-134 (no clip_scale); no fleet_bus.clip_scale accessor exists.
- fix shape: Route the family bot through fleet_bus (long_entries_blocked + a new clamped fleet_bus.clip_scale() accessor) and multiply clip_scale into the four strategies' custom_stake_amount — or record the twins' control-arm exemption in the strategy files.

### IMB-28 [low] — contested (split lenses) — low confidence
Immune bot-row sickness detection ('a NaN or absurd pnl_pct poisons the brain's grading') has no mechanical counterpart: a flagged row is phone-pushed while the brain, board, and dashboard keep consuming the poisoned bot_pnl row unfiltered — detection-without-actuation, the exact gap the organ closes for levers.
- evidence: fleet_immune.py:207-230; grep shows no consumer of 'fleet-immune'.sick gating bot_pnl ingestion in bot_learn.py/evidence_board.py.
- fix shape: Publish a machine-usable sick_bots field; brain grading + board live checks skip rows flagged by a FRESH immune payload (restrict-only, fail-open on a dark immune — same central-hook pattern as quarantine).

### IMB-29 [low] — contested (split lenses) — low confidence
bot_learn never-healing anchors: (a) diagnose()'s venue_execution rule compares an era (bot,tag) bucket against the twin's LIFETIME whole-book pnl_abs at a weaker floor (twin_n≥5 vs 10) — the verdict cannot heal and violates the fleet's own per-trade-not-pnl_abs lesson (advisory prose only); (b) every ERA_START key names a retired Kraken bot, and on the v2 fallback path — which engages SILENTLY on any checkout missing brain_stats.py, not just the env flip — the restrict gate is era-lifetime-anchored with no decay, so a dormant bled tag's throttle can never heal.
- evidence: bot_learn.py:515-518/:544-548 (lifetime twin anchor); :130-139 (no -lshadow ERA_START), :96-100 (silent import fallback); brain_stats.py:222-235 (qualify_v2 no forgetting).
- fix shape: Anchor the twin side to per-trade mean over the same era window with twin_n≥10; make the v2 fallback log loudly + add a fleet_immune invariant (engine=v2 while BRAIN_MULT_ENGINE unset); CLAUDE.md process note to add ERA_START entries when gate0 family-bot logic changes.

### IMB-30 [low] — SHIPPED 16-Jul (verify-confirmed)
Lens-feed freshness bar drifted between directions: restrict gated on env-tunable LENS_FRESH_S while expand hardcoded 26000s at its callsite — tightening the env var tightened only one side, and inputs_fresh reported bool(lf) presence, not freshness.
- evidence: Pre-diff synthesize read the raw lens payload; synthesize_expand callsite used literal 26000.
- fix shape: already-fixed-in-diff — both sides (and inputs_fresh) now gate on _fresh(lf, LENS_FRESH_S); selftest asserts a fossil payload fires no lens items on either side.

### IMB-31 [low] — SHIPPED 16-Jul (verify-confirmed)
Growth-rail step memory advanced on a FAILED write, permanently swallowing the operator-mandated per-step phone push (next cycle's successful write found growth_step == prior_step).
- evidence: Pre-diff payload growth_step stored unconditionally while the push required growth_step > prior_step AND enacted.
- fix shape: already-fixed-in-diff — growth_step persists only when the gapscout write landed (_gs_enacted) or no growth levers were due; the push also now lists only board-authored gapscout.* levers.

### IMB-32 [low] — SHIPPED 16-Jul (verify-confirmed)
A live.clip_scale DOWN-scale (restrict intent) mechanically EXPANDED the live slot budget: max_open = floor(cap/scaled_clip), so x0.5 doubled the coins the live book may hold — an ungated expand side-effect of a restrict lever (dollar cap was already senior, the count half was not).
- evidence: Pre-diff venues/__init__.py:90-94 divided by the lever-scaled order_usd.
- fix shape: already-fixed-in-diff — lighter_live slots now anchor to the operator's env clip (LIGHTER_ORDER_USD), so lever moves can no longer mint or burn slots; shadow modes keep mirroring their own clip.
