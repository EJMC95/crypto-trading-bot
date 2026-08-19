# HOW THE P&L INCREASES — the deep dive (2026-08-18)

Operator ask: *"Dive deep on all the knowledge you have and we have and you can
get on how we can make this pnl increase"*, then *"Fix, commit push and deploy
all enhancements and look for anything we've missed."* Method: five measurement
lenses (knowledge inventory · gate/capital math · venue occupancy · the
300-day supply trend · outside-literature families), each seeded with the
fleet's standing refusals so nothing already refuted gets re-proposed, plus
this session's own independent measurements. Sources named per claim.

---

## 1 · THE REFRAME EVERYTHING ELSE HANGS ON: it is a LIQUIDITY drought, not a funding drought

Measured from the venue's own settled hourly fundings — **300 days, all 227
books** — joined to 500d of daily quote volumes:

- **Funding dispersion is INTACT.** 18.1 crypto coins at |TRUE apr|≥20% this
  week, inside the 44-week band of 6.3–32.8 and near Oct-25 levels. It is
  cyclical (corr +0.40 with BTC weekly realised vol), not trending down.
- **Volume collapsed, secularly.** Ex-BTC/ETH/SOL crypto quote volume:
  **$2.2B/day (Nov-25) → $54M/day (now), −97.5%** — log-slope −0.076/week
  (halving every ~9.4 weeks), monotone, **zero recovery episodes in 44
  weeks**. Crypto coins ≥$2M/day: ~85 → 6.6.
- Every volume-floored funding cell starved in proportion: 🌾 carry's
  20%/$2M cell fell from **2,038 six-hour-persistent coin-hours/week
  (28-Oct)** through 165–400 (Jan–Feb) to **0 this week**; 💸 the Farmer's
  5%/$10M cell from 40–60 simultaneous coins to 2.65; 🧮 Hull's band 7–30
  → 2.27 (still ~100% availability — the one populated validated cell).
- **This week is the natural experiment**: a funding spike (18 coins ≥20%,
  near the year's top) produced ZERO cell supply at $2M. The same supply sat
  one tier down — 37 coin-h/wk at a $1M floor, 134 at $0.5M — and the
  occupants (XMR, KAITO, ENA) are the SAME coins that populated the $2M cell
  in May–June before their volumes fell ~10×.

**What this reframes:** the Farmer's t-collapse (1.73 → 0.24), Garrett's band
decay `(pw)`, and carry/kiyosaki's starvation are **supply effects, not code
defects or edge refutations**. A book starved by a volume floor set for a
vanished volume regime is supply-starved, not edge-refuted — this context now
sits beside carry's docket status, 🏦 kiyosaki's ~12-Sep cell decision, and
the ~28-Aug ⚖️ Counterweight call. And "wait for the $2M cell to re-widen"
may be waiting forever on this tape: the volume leg has never once recovered
in 44 weeks. **Following the supply down the ladder — through the gates, with
each step measured — is the strategy**, and today's `(px)` (min_vol $2M→$1M,
2.3× occupancy, all-crypto) is exactly that step, already shipped.

## 2 · THE REAL-DOLLAR TRUTH (lens 2, ledger-verified)

Real money is **$259.84** (Farmer $197.24 + Avo $62.60) and its combined
run-rate is ≈ zero (Farmer trailing-14d −$0.17/day, holding NOTHING —
`eligible 0` at 5%/$10M). Base-case 90-day real P&L: **−$10 to +$18**.
Everything-goes-right 90 days: **~+$55–75**. The paths, quantified:

- **🙏 Avo shadow → gate**: the only above-bar book (era n=12–14, mean
  +1.31–1.38%/trade, t=+2.31, 4/6 bars; window self-clears ~26-Aug). Close
  rate since the `(ne)` cap raise: ~1.16/day (n=4, low confidence) vs 0.34–
  0.52/day before → **n=30 lands early-Sep (fast) to mid-Oct (grader's
  rate)**. At today's live sizing (clip = equity/4 = $15.65 on $62.60) a
  pass is worth **~$0.10–0.13/day**. Funded to its existing $200 cap →
  ~$0.33–0.43/day; at $1k → ~$1.6–2.1/day (mean above ~$50 clips
  UNMEASURED at that tier's slip — stated, not assumed). Referee caveats,
  carried: the grader's **cluster-robust t sits at exactly 2.00** (n_eff
  8.2) — the t bar is knife-edge on that basis even as raw t holds 2.31;
  the grader's own ETA reads 2026-10-06 at 0.37 closes/day; the live arm's
  n=3 record (−$0.15 MTM) is evidentially empty, and the shadow→live
  transfer is unmeasured until impl-shortfall has a paired sample. **The
  gate validates; the deposit pays. The dollar lever is yours.**
- **💸 Farmer**: earning ~$0/day and CORRECTLY so — refined post-referee
  (I12): not "zero supply" but **thinned supply × marginal economics**. The
  ≥$10M census oscillates (a fresher read had 4 of 8 books over the 5% gate,
  all persistence-waiting; BTC intermittently above its measured 6.2%
  breakeven), so the book's condition is edge-flatness at the resting
  default — the persistence gate and the ~0.5bps-per-9h-hold arithmetic are
  the binding pair, and an instantaneous `eligible 0` is its normal reading
  (I7). The designed route to more is the judge queue — `slope-gate-off`
  (window restarted 18-Aug after `(pt)`, n=1/30) then `min-vol-1e5` /
  `min-vol-2e6`. Honest priors attached: the thin-tier prior weakened
  (`(pw)`: band +$14.83 → +$4.82 with h2 −$13.22 on the fresh window), so
  expect the paired bar to refuse — and that refusal would be the system
  working. Earliest any promotion could land: ~1-Sep.
- **🧮 Hull**: the one surviving founding claim (n=50 +$6.69 t=+3.92);
  binding bar is closes (~6/30d, ~5 months to 30). Needs time, not tuning.

## 3 · SHIPPED TODAY — the enhancements, across all of today's sessions

| what | where | evidence |
|---|---|---|
| 🌾 carry unstarved: `CARRY_MIN_VOL` $2M→$1M + `FLIP_GRACE_H` 1h→6h at an empty-book boundary | `(px)`, funding_carry_bot.py | 2.3× cell occupancy (5.73%→13.42% of 9,996 snapshots); grace 6h +$41.17/t=2.96 vs 1h +$27.25/t=1.95 h2-neg on 250d |
| 🧘 Douglas phantom rows quarantined fleet-wide | `(pv)`, LEDGER_QUARANTINE | n=6/−$23.84 → n=4/+$2.64 in every grader |
| Garrett cap + exits measured-refused; tier-split priced and refused | `(pw)`, `(py)` | cap 9 = −$7.07 vs cap 6 = +$4.82; split costs $20.53; Rich-Dad extension = KAITO 107% of total |
| The carried `(kc)` `--refresh` adjudication RUN (owed since 5-Aug) | this pass | see §4 |
| 🌾 carry census `next` scoped to class-admissible coins (it was promising SKHYNIXUSD, with a countdown, on a crypto-only book — I8) | this pass, funding_carry_bot.py + test pin (2 mutations red) | verified firing live: `next: SKHYNIXUSD / next_eta_h 3.75→2.71` |
| The ~mid-Aug SPY/QQQ graduation re-run EXECUTED | this pass, REGIME_GATE doc | trigger fired (both LONG-window, dir=1); graded n=3 — decision milestone moves to self-grade n≥20 (~mid-Sep); wiring already live, 🙏 avo shadow already holds SPY |
| Douglas ATR-floor lead: OOS test PRE-REGISTERED (floor 1.00% frozen, forward tape from 17-Aug, run ~17-Sep) | BAND_YOUNG doc | in-search t=2.217/OOS-half t=1.487 — a lead, "never a setting to ship" per its own study |
| PERSIST 6h→12h staged for the ~30-Aug docket day; queue block corrected in place | OPERATOR_QUEUE | t=1.80 both halves, parked per its own study |
| Study census corrected: 0 of 8 directional books calibrate | STUDY_ENTRY_EXIT | gillard retired the day it was named |

## 4 · THE `--refresh` ADJUDICATION — the carried question, answered

`backtest_funding_lighter.py --days 180 --universe 25 --refresh` (fresh-ranked
universe through 18-Aug, near-zero slip): **every gate row is NEGATIVE
full-window** — 0.05 reads −$22.12 (h1 −$30.48 / h2 +$11.54), 0.40 reads
−$16.25. The 23-Jul "both-halves-positive at gate 0.05" does **not** survive
on any current read; the 5-Aug "alive at measured cost" was the stale 24-Jul
universe. Mechanically consistent with §1: at gate 0.05 the median hold is 9h
earning ~0.5bps carry vs ~1bps RT slip — the liquid-tier lane is
friction-marginal at today's funding levels, exactly what the live book's own
flat August says (I14 senior either way). **Consequences**: no Farmer gate
move is supportable in either direction; the book's idleness is correct; the
h2-positive rows say the recent regime is less bad — supply-bound, not
gate-bound. (A `--days 30` calibration row was attempted and NOT quoted: the
harness serves the full cached span regardless of `--days` — identical n
across a 6× window change — a quirk flagged for the next pass.)

## 5 · THE THREE ADMITTED STUDIES — **ALL RUN AND CLOSED NEGATIVE 19-Aug ((qi)), corrected in place per I12 so this section can never be re-opened on a hunch**

The section below proposed three studies. `(qi)`'s six-hunter pass ran all
three the next day with adversarial referees, and **every one closed
negative** — which is the most valuable outcome available: each was a
standing question that would otherwise have been re-proposed forever. The
closing numbers, so they stay closed:

1. **Divergence-conditioned harvesting — CLOSED NEGATIVE.** Pooled over 241
   covered era closes, the |gap|-at-open buckets are NON-MONOTONE with the
   best bucket in the middle (0–10pp −$16.00 · 10–20pp +$5.30 · ≥37.5pp
   −$10.98, collapsing to −$0.66 once the shipped `(lk)` screen is removed).
   No screen ships on any book; the LIT/ZEC/VVV losses were gap-quiet end to
   end — price/stop losses, not cross-venue contradiction.
2. **Funding-extreme squeeze — CLOSED NEGATIVE IN BOTH DIRECTIONS.** All 9
   cells refuted: every receiving-side forward return is negative and never
   beats the own-coin null (80%/24h −0.880%/episode, null −0.115%, P=0.957);
   at the 80% bar the adverse price leg is ~5× the funding collected — the
   receiver PAYS the squeeze premium. The mirror (pay-and-ride) dies on
   best-of-9 selection + the `(oj)` tail shape (3 of 146 episodes = 56% of
   gross).
3. **Listing lifecycle — the founding thesis REFUTED and the supply DEAD.**
   TP hit 2 of 73 crypto births (2.7%), −0.33%/episode vs −0.05% null
   (P=0.707), median day-7 debut −13.4% — and zero crypto births Jun–Aug
   (last one 85 days ago). The sniper's "deliberately unscreened founding
   thesis" line in CLAUDE.md was corrected in place the same pass.

The original proposals are kept below as the record of what was asked:


1. **Divergence-conditioned harvesting** — split funding extremes into
   Lighter-idiosyncratic (plumbing → harvest) vs cross-venue-mirrored
   (informed crowding → avoid). The scout ALREADY computes the signal
   (`funding_divergence`, median of binance/bybit/hyperliquid) and **no
   harvest book reads it**. Live snapshot: ZK −51.7% on Lighter vs +10.9%
   cross-venue; POPCAT −58.7 vs −4.3; CXMT the mirror. The class it would
   screen is measured: 5 of the Farmer's 7 stops were LIT shorts (−$9.17)
   with LIT the standing market-wide extreme. Dual-use: a negative result
   still hardens existing entries.
2. **Funding-extreme squeeze event study** (24–72h, thin/mid books) — the
   price leg the fleet only ever EATS (the ~90% adverse intrabar excursion
   the leverage study measured; the Farmer's LIT stops). Unlike the retired
   knife-catchers, a squeeze-long is PAID to wait (−50% apr ≈ 0.11%/day
   received). ~4–6 tradeable candidates at any moment.
3. **Listing-lifecycle retrospective** — 72 crypto birth events on the
   venue's own `created_at` history vs 🎯 the sniper's n=1-per-listing
   problem.

**Rejected with evidence**: passive maker/spread-capture — a 30s loop cannot
hold queue position, and Harris already refused modelled market-making
without a fill simulator. **Answered by `(py)` before I could propose it**:
the thin-tier delta-neutral harvest — one coin (KAITO, 107%) wearing a cell.

### Referee-pass status (recorded so the §5 studies are not over-read)

The adversarial referee wave completed on the capital/inventory/venue/decay
lenses: **3 findings survived** (the avo path, the liquidity-drought reframe,
the carry-census defect — now fixed), and most "refutations" were
*stale-because-already-shipped* confirmations of this same day's work. The
§5 outside-lens studies were never refereed by THAT wave (it hit a session
limit) — and the point is now moot: `(qi)` ran all three as full studies the
next day and closed each negative (see the §5 header correction).

## 6 · REFUSALS RECORDED THIS PASS (I19 — each with its number)

carry gate walks (re-confirmed on the fresh tape: negative at every gate) ·
Farmer gate move either direction (§4) · thin-tier capacity or split
(`(pw)`/`(py)`) · shipping the Douglas ATR floor today (701-cell search,
noise-shaped surface — registered instead) · passive maker at this loop
cadence · re-proposing anything in `(pu)`'s 32.

## 7 · THE ONE-PARAGRAPH ANSWER

The P&L increases on three clocks. **Weeks**: Avo passes the gate
(early-Sep at the current close rate) and the operator's deposit — not any
code — turns +1.3%/trade into real dollars; meanwhile carry's `(px)` floor
walk re-opens the fleet's best-validated cell one tier down, where the
300-day data says the supply actually went. **A month**: the judge queue
adjudicates the thin tier with forward paired evidence, and the two admitted
studies (divergence-conditioning, squeeze events) either mint the fleet's
next measured edge from a signal it already computes, or die cheaply.
**Structural**: this venue's alt volume has halved every 9.4 weeks for 44
weeks — the fleet's fixed dollar floors must keep walking down that ladder
gate-by-gate (measured each step), or the books will be grading themselves
against a market that left; and the operator's capital decision remains
worth two orders of magnitude more than any lever in the codebase.
