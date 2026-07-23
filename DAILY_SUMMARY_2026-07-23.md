# Daily work summary — Thu 23 Jul 2026

**8 commits (cg → cn), ~4,700 lines, all merged to `main` (HEAD `6a9e331`).**
Two movements: **(1)** acting on the prior day's 7-track adversarial audit — real
defects sealed — and **(2)** building a new "edge radar" organ that then caught
*its own* flagship verdict as false.

Commits: `32d8ff6` (cg) · `b1de4ee` (ch) · `abd2e0e` (ci) · `30c8684` (cj) ·
`c632387` (ck) · `2c59a30` (cl) · `24f1dba` (cm) · `6a9e331` (cn).

---

## 🎯 The one-line version
The fleet's only "plausible" edge — the **live Funding Farmer** — turned out to be
a **decaying, 2-coin mirage**. Across the whole living fleet there is now **zero
`real_edge`**. That's the day's most important finding, and it came from an organ
that was built the same morning.

---

## 🐛 Bugs found (and fixed)

### Real-money / correctness
1. **Quarantine could be silently wiped by a DB blip** *(cg)* — the post-stop coin
   quarantine made durable yesterday (`cb`) was restored through the *unchecked*
   `load_state`, which collapses "no row" and "read failed" into the same `None`. A
   Postgres hiccup at boot looked exactly like a first run and **re-armed every
   stopped coin** — reintroducing the precise bug `cb` closed, one layer down.
   **Fix:** both restore sites now go through `read_quarantine()` on
   `load_state_checked` with bounded retry; a genuinely failed read sets
   `quarantine_blind` and blocks *new* entries only (exits / stops / position
   management untouched) and self-heals on a later cycle. New `_selftest_quarantine`,
   mutation-tested. *(Real-money code — `lighter_funding_bot.py`.)*
2. **A withdrawn verdict was still steering the live bot** *(cg)* — yesterday's `cf`
   withdrew the +$21.32 STOP verdict but left it asserted as live truth in **six more
   places**, worst being `lighter_funding_bot.py:136-146` — the LIVE Farmer's own
   header, COPY'd into the real-money image. Swept all six, including a runtime
   `print` that emitted the stale rows on every run.

### Infra / process
3. **A corrupt sync channel CI couldn't see** *(cg)* — `CHANGELOG.md` carried three
   committed stash-conflict markers across **seven commits, every CI run green**,
   because `changelog-check` only asserts the file *appears* in the diff and never
   reads its content. Resolved + a new **`conflict-markers` CI job** that scans every
   tracked file (a marker in a `.py` is a SyntaxError that would ship to a real-money
   image), with a negative "blind-guard" fixture proving the guard can still see.
4. **`fleet_agronomy` shipped two defects** *(cg)* — it published to production
   `bot_state` *by default* (a bare run had already written a 102 KB row that needed
   hand-deleting → now opt-in `--publish`), and it manufactured action-severity
   findings from a dark ledger (absence-of-evidence rendered as evidence-of-absence
   → explicit `ledger_ok`, new mutation-tested case 18b). Committed but **NOT wired**
   (no loop, no COPY, no consumer).
5. **Immune organ watching a dead sensor** *(cj)* — `fleet_immune` watched
   `gapscout-census` (Gap Scout, retired 17-Jul; **measured stale 5.5 days**), a
   permanently-dead check, and had no invariant on `regime-oracle`, whose self-grades
   feed the 28-Jul review. Swapped; verified the oracle is live-fresh (6 min, 13
   graded syms) *before* wiring the consumer (not born-dark). Mutation-tested both
   directions.
6. **Coin-veto's "pooled fleet-wide" was a lie** *(ck)* — the Ticket Taker writes
   `1000BONK`, the funding/momo bots write `kBONK`; `GROUP BY coin` split the same
   coin's evidence (BONK: 7 rows vs 12) for all six `1000*` markets. **Fix:** a pure
   `_fold_coin_quality()` that canonicalises via `from_lighter` and re-aggregates
   from raw sums (correct weighted average, not average-of-averages); the Taker
   lookup matches both the canonical and raw base so it's robust to deploy order.
   **Measured inert today** (BONK 7.75 bps pooled, under the 15 bps bar) —
   forward-looking correctness.
7. **Two bugs the radar's own tests caught** *(cn)* — the trajectory was **inverted**
   (the ledger fetch is `closed_at DESC`, so the "recent half" was the *old* half;
   now sorted oldest-first with a reversed-order selftest guard); `_t`/`_slope_t`
   **exploded to ~1e16** on identical values (float-noise sd ~1e-17 → guarded with
   `sd/se > 1e-9`). Both mutation-tested.

---

## 💡 The breakthrough — `fleet_radar`, and its self-correction
- **(cl) Built `fleet_radar.py`** (new organ) — grades every living book by one honest
  ruler, continuously: 📡 per-trade t-stat · 🛰️ both-halves stability · 🌐
  concentration + jackknife + **median** · 📶 closes/day · 🧭 ETA-to-verdict. Classes:
  `real_edge / plausible / artifact / weak / noise / losing / starved`. The **median is
  load-bearing**: a lone t-stat flagged `perps-funding-carry` as "REAL EDGE" when its
  whole edge is two lucky trades — median negative → `artifact`. Publish-only,
  born-dark-clean, looped in `run_all.sh` every 30 min.
- **(cm) Surfaced on the dashboard** — `radar_card()` renders the colour-coded map;
  `fleet-radar` joins `ORGAN_SPECS` for `/vitals` freshness. Display-only.
- **(cn) Dug deeper — caught its own flagship as hollow.** The radar's ONLY
  `plausible` book, the Funding Farmer (incl. the **live** arm), is illusory two ways:
  **decaying** (shadow thirds t = 3.28 / 1.10 / −0.54; recent-half median negative)
  and **2-coin** (drop ZEC + HYPE and live t goes 1.10 → **−0.32**). "4 days to
  verdict" was a fading average of a front-loaded streak. Built 3 new sensors
  (trajectory / concentration / twin-dedup) and honestly **killed 5 others** with real
  data (regime-split manufactures false edges, execution-adjust double-counts, etc.).

---

## 🧬 Evolutions / solutions
- Test suite went from **194 passed / 1 FAILED** (deselected 3× to fake "green" all
  day) → **197 green** (cg, by registering the two untracked files) → **198 green**
  (radar trio).
- **Doc-integrity sweep** *(ci)*: 5 stale claims fixed at *every* copy (source +
  CLAUDE.md + memory) — incl. the standing "LIVE BOTS ALWAYS IN AUDIT SCOPE" rule that
  named the *retired* Tide Rider instead of the live Ticket Taker.
- New guard-only tool committed: `scripts/audit_lever_authority.py` (does a lever's
  `[lo, hi]` reach the population it gates?).

---

## 🚀 Deploys / real money
- **(ch) — the only real-money deploy.** gate0 fast-forwarded (7 commits behind →
  main), triggering the live Farmer's rebuild — proven landed by build stamp
  (`ea6d31d28ae3 → 22a42b6226b7`) + boot banner (`equity guard restored $97.84`), all
  3 real positions restored (ETH / LIT / XAU shorts). Both live build stamps verified
  `== HEAD`, so no dispatch was needed.
- Confounded control arm cleaned: `funding-farmer-shadow` restarted, HARD STOP
  **0.03 → 0.10**, so the judge's A/B now varies only `xp.funding.enter_apr`.
- The header edit in (ch) is **comment-only** (zero non-comment lines) and is
  deliberately *not* redeployed. Everything else rides the freqtrade-bots / dashboard
  auto-deploys on merge; **no other real-money code changed.**

---

## ➡️ Forward progression / still open (operator calls)
- **Strategic:** the Farmer edge is decaying + 2-coin — *feeding it would confirm the
  fade, not reach a positive verdict.* Zero `real_edge` fleet-wide reframes the go-live
  picture.
- The radar is **publish-only** — letting it *drive* feed/park/cull stays an operator
  decision.
- gate0 intentionally held **1 commit behind main** (verified comment-only diff — not
  worth another ~1h slope-gate fail-open on a real-money book).
- The **live** Taker's coin-veto lookup fix lands on the next dispatch (both-forms
  guard keeps it correct meanwhile).
- Audit backlog: **96 findings, 63 survived refutation, 4 acted on** — remainder
  surfaced, not taken.
- `audit_lever_authority` exits 1 on **5 open findings** (e.g. `live.funding.enter_apr`'s
  `hi` sits below the venue's modal funding; `FUNDING_HARD_STOP` / `FUNDING_EXIT_APR`
  carry the live book's loss with no lever at all) — informational until triaged.

---

## The through-line
Today the fleet audited *itself* — a corrupt channel CI was blind to, a withdrawn
verdict still in the live source, a guard a DB blip could wipe — and then built a
sensor honest enough to declare its own best result a mirage. Forward progress,
mostly by subtraction of false confidence.

---

*Verification: the load-bearing claims above were spot-checked against the actual
commit diffs — the quarantine hardening (`read_quarantine` / `load_state_checked` /
`quarantine_blind` in `lighter_funding_bot.py`), the `conflict-markers` CI job and its
blind-guard fixture, `_fold_coin_quality`, `fleet_radar.py` as a genuine new file, the
`sd/se > 1e-9` guard + oldest-first inversion fix, (ch) being comment-only, and the
197→198 suite counts all match. This document summarises the commit messages + CHANGELOG
(entries `cg`–`cn`); it changes no code.*
