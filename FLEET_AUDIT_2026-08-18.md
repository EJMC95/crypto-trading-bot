# FLEET AUDIT — 2026-08-18: universe · win rate · yield · P&L

Operator ask: *"Fleet audit. Improve universe / Improve win rate / Improve
yield / Improve the pnl."* Every number below was computed this session from
the live payloads (`/pnl.json`, `/bus.json` fetched 01:50Z, all 17 rows fresh,
`n_stale 0`) and the full 2,585-row paper ledger — file:line or the ledger
computation is named for each. Where the honest answer to an ask is a refusal,
the refusal is the deliverable (I19).

**Context that frames everything:** `(pu)`, earlier the same day, ran a
55-agent "fix anything that makes more money" hunt and returned **zero
shippable dollar-positive proposals and 32 measured refusals**. This audit
does not re-litigate those; it verifies the standing claims underneath the
four asks, closes what it can, and ships what survived.

---

## 1 · THE LEDGER, DECOMPOSED (living books, n=977 closes)

| book | n | win% | total $ | mean %/t | avgW $ | avgL $ | W/L |
|---|---|---|---|---|---|---|---|
| 🌾 perps-funding-carry-lshadow | 101 | 42.6 | **+66.21** | +0.254 | 2.571 | −0.765 | 3.36 |
| 🎫 lighter-ticket-taker-lshadow | 206 | 39.3 | +11.93 | −0.059 | 1.491 | −0.871 | 1.71 |
| 🙏 freqtrade-avo-maria-lshadow | 14 | 78.6 | +7.09 | **+1.377** | 0.753 | −0.395 | 1.91 |
| 💸 perps-funding-lighter-lighter (LIVE) | 129 | 55.8 | +6.68 | +0.273 | 0.342 | −0.315 | 1.09 |
| 👧 freqtrade-georgia-lshadow | 123 | 41.5 | +2.89 | +0.005 | 0.430 | −0.264 | 1.63 |
| 🏛️ pm-albanese-lshadow | 25 | 40.0 | +1.81 | +0.281 | 0.828 | −0.431 | 1.92 |
| 💸 perps-funding-lighter-lshadow | 188 | 53.2 | +1.60 | +0.217 | 0.564 | −0.622 | 0.91 |
| 👩 freqtrade-mum-lshadow | 3 | 66.7 | +0.68 | +0.452 | — | — | — |
| 🏛️ pm-turnbull-lshadow | 20 | 55.0 | +0.36 | +0.022 | 0.242 | −0.256 | 0.95 |
| 🙏 freqtrade-avo-maria-lighter (LIVE) | 2 | 50.0 | +0.08 | +0.252 | — | — | — |
| 🎯 lighter-perp-sniper-lshadow | 30 | 43.3 | −3.31 | −0.520 | 0.404 | −0.504 | 0.80 |
| 🛢️ band-garrett-lshadow | 15 | 53.3 | −4.58 | −1.141 | 0.126 | −0.799 | 0.16 |
| 🧘 book-douglas-lshadow | 6 | 50.0 | −23.84 | −3.973 | 1.152 | −9.098 | 0.13 |
| ⚖️ perps-funding-spread-lshadow | 115 | 49.6 | −30.55 | −1.454 | 0.600 | −1.116 | 0.54 |
| **TOTAL** | **977** | | **+37.05** | | | | |

Go-live gate: `ready = []`. The ONLY book above the t≥2.0 bar is 🙏 avo shadow
(t=+2.31, `on_track`, failing only `closes` and `window`).

---

## 2 · THE FOUR ASKS, ANSWERED WITH THE FLEET'S OWN NUMBERS

### "Improve win rate" — the premise is measured-backwards on this fleet (I15)

The table above is one-sided: the two best earners win **42.6%** (carry, W/L
3.36) and **39.3%** (taker); the second-worst loser wins **49.6%**
(Counterweight) and the worst-per-trade book wins **53.3%** (Garrett). Win
rate does not order this fleet's P&L — the LOSS TAIL does (W/L column). The
two books whose loss tails were broken both already have closed mechanisms:

- **🧘 Douglas W/L 0.13** — its ROBO close booked −23.16% against a declared
  7.04% stop. Root cause was `(nm)` (16-Aug): the bracket compared a
  funding-map mark **frozen at container boot** with itself, so the stop
  could not fire until a restart made the frozen value jump (both 15-Aug
  closes share `closed_at` to the second, across a build-stamp change).
  Fixed, 6 mutations verified. Post-fix breach check across the whole
  ledger: one row at 1.37× declared stop ($0.22 excess) — ordinary
  5-minute-poll gap-through, not a defect. **What was still broken: the
  grader kept counting the phantom closes — shipped this pass, §3.**
- **⚖️ Counterweight W/L 0.54** — see the P&L ask below: the loss is a
  screened-out class, not a live mechanism.

Raising win rate as an end was not pursued anywhere — a tp tightened to win
more often is the (hl) class (25 of 30 throughput candidates died as
denominator shrinkage).

### "Improve universe" — supply is measured per book; the binding gaps are known and priced

- **🌾 carry + 🏦 kiyosaki (the 20% TRUE / $2M / crypto cell): `eligible 0` of
  225 scanned**, verified in both books' live censuses. This is the venue,
  not a defect: I20 measured the cell's whole crypto population at 3 coins,
  present in 6.6% of snapshots. Widening the gate is REFUSED, again — the
  20%→10% walk needs the rate to hold 254 of 336h to break even against a
  29bps round trip (I19's worked example), and `(pl)` refused the re-band
  four days ago. Carry has ZERO closes since 12-Aug because it can enter
  nothing; that is starvation, not failure.
- **🛢️ Garrett (thin tier [0.1M, 2M) at 5%): `eligible 26, free_slots 0`** —
  supply-rich, capacity-bound, and **refused a widening** on I7/`(hs)`:
  −1.141%/trade, t=−1.05, horizon `unreachable`. More slots on a losing book
  buys exposure, not evidence. Its missing class screen was measured and
  refused 16-Aug (live non-crypto n=12 t=−0.44 vs +$1.78) — selftest-pinned.
- **📐 grimes: `gate_drift.ungraded = [ADA, APEX]`** — the published hazard
  from `(om)` is non-empty: the book can enter two coins its fixed gate
  never graded. **No exposure today** — all three setup gates are CLOSED
  (keltner t=−0.15, failtest −1.37, pullback −0.63) and the book holds
  nothing. The `(oe)` universe-churn fix is visibly working: the gate closed
  on the fixed set instead of flapping with the coin ranking.
- **🧮 hull: the band is populated as designed** — holding LIT+ZEC shorts at
  payback 18.3%/29.6%, `eligible 0` this loop, ~6 closes/30d exactly as its
  I17-declared slow clock predicts. Needs time, not universe.

No universe change ships: every reachable widening feeds a rule whose own
record refuses it, and the starved cells are starved by the venue.

### "Improve yield" — the funding class is where all measured claims live, and its levers are already set to the measured cells

- **🌾 carry in-era decomposed** (ledger, era ≥31-Jul): −$15.45 over 10
  closes, of which **9 are the non-crypto class `(lk)` screened on 13-Aug
  (−$14.96)** and 1 is crypto (−$0.49). The gate's `unreachable, t=−4.48` is
  therefore 90% a population the current code cannot enter — the same shape
  as Counterweight's, already recorded on the carry row. Post-screen closes:
  zero (cell starved, above). Nothing to tune; the screen was the fix.
- **Exit tolerances**: 🏦 kiyosaki runs the `(mf)`-measured 6h flip grace
  (caps: `flip_grace_h 6.0`), 🧮 hull the `(ny)`-remeasured 24h cell
  (`flip_grace_h 24.0`, founding claim n=50 +$6.69 t=+3.92 — the one cohort
  number that SURVIVED re-measurement). Both verified in the live caps.
- **💸 Farmer (real money)**: in-era mean +0.033%/trade, t=0.24,
  `undecidable`; live slippage 0.33bps over 39 orders (`(pu)` §6, healthy).
  Its I16 era lower bound is 0.000% — **no sizing change is supportable**
  and the judge (sole writer of `live.funding.*`) is mid-candidate
  (`slope-gate-off`, n_shadow 10/30) with its arms freshly re-paired
  (`(pt)`). The one significant exit cell (max_hold, pooled t=−3.83) stays
  refused at n=10; re-check at n≥30.

### "Improve the pnl" — the two books that are −$54.39 of drag both have closed mechanisms; the verified answer is the pre-registered operator call, not a fix

- **⚖️ Counterweight −$30.55, VERIFIED against its own ledger this session**:
  non-crypto legs n=21, **−$36.48, t=−2.86 — 119% of the total loss** —
  while the crypto trades it can still take read **+$5.94 (n=94)**. Since
  the `(ki)`/`(jg)` class screen: **zero non-crypto entries**, and the
  post-5-Aug record is flat (n=23, +$0.95, 56.5% win). The standing
  CLAUDE.md claim ("114% of its loss is a population already made
  unenterable") HOLDS — measured here at 119% on today's class map. The
  drag is history, already stanched; the book's keep-or-retire is
  **pre-registered to the operator ~28-Aug** and deciding early is the
  (hs)/(ia) trap in reverse. On the docket since 6-Aug.
- **🧘 Douglas −$23.84**: −$26.48 of it is the two phantom-price closes
  `(nm)` ruled "not evidence of its edge either way". Post-fix record:
  **n=4, +$2.64, 3/4 wins, every close within its bracket**. The remaining
  defect — the grader still counting the phantom closes — is what this
  audit ships (§3).
- **The stop family (−$128.05 / 317 closes, the fleet's dominant loss
  mechanism)**: `(pu)` found the only calibrating directional book
  (pm-gillard) was retired the day the study named it, so the exit sweeper
  has **no calibrated actuation path into any directional book** — acting
  anyway is the unmeasured widening I19 bans. The study's census line said
  "1 of 8"; **corrected in place to 0 of 8 this pass** (the `(pu)` carried
  item, I12).

---

## 3 · SHIPPED THIS PASS

1. **`POLICY_ERA["book-douglas"] / ["book-grimes"] = 2026-08-16`**
   (`scripts/golive_readiness.py`) — the `(nm)` phantom-price fix declared as
   an accounting era, by `(hc)`'s own test (earlier P&L is WRONG; policy
   unchanged, so the (hm) clock is untouched). Effect: douglas's below-floor
   horizon grades the post-fix sample (n=4, +$2.64) instead of publishing
   `unreachable` on phantom prices; grimes is declared ahead of its sample
   per the `(hh)` rule. 🧙 schwager deliberately absent (retired, zero
   closes) and pinned so. **4 tests, 4 mutations verified RED** under
   `PYTHONDONTWRITEBYTECODE=1` with byte-identical restore
   (`tests/autonomy/test_golive_era.py §8`). Both directional era-coupling
   pins (gate-vs-brain) checked: douglas/grimes are in neither `ERA_START`
   direction, so no conflict. Zero real money; publish-only organ.
2. **`STUDY_ENTRY_EXIT_FLEETWIDE_2026-08-15.md` corrected in place (I12)** —
   both "1 of 8 calibrates" passages now record 0 of 8 and why, discharging
   the correction `(pu)` explicitly left carried.

## 4 · REFUSALS WORTH RECORDING (each with the number that killed it)

| proposal | killed by |
|---|---|
| Widen carry/kiyosaki's 20% TRUE gate to repopulate the cell | 254-of-336h break-even at 10% vs 29bps RT (I19 worked example); `(pl)` re-band refusal 4 days old |
| Garrett capacity (26 eligible vs 6 slots) | book at −1.141%/t, t=−1.05 — `(hs)`: a capacity widening reads P&L and fails closed |
| Garrett class screen | measured refused 16-Aug: live non-crypto n=12 t=−0.44 vs shadow +$1.78 |
| "Fix" Counterweight | its loss is 119% a class it already cannot enter; post-screen flat; pre-registered ~28-Aug operator call (I11) |
| Move carry's era to the 13-Aug class screen | the fleet ruled class screens non-resetting twice (Counterweight, carry itself at `(lk)`); the in-era split is recorded on the carry row instead |
| Era-gate the allocation organ's pooled carry claim | already done — `(oy)`/`(mz)`: `scale_effective 1.00`, `expansion_gated` published; consumers cannot act on a pooled claim |
| Any stop-family change on a directional book | 0 of 8 books calibrate the sweeper; `(ps)`'s calibration gate refuses — no harness may say what WOULD have happened |
| Win-rate-targeted exit tightening anywhere | I15 + the fleet's own table: best books win 39–43%, worst win 50–53% |

## 5 · OPERATOR-ONLY (the docket, unchanged by this pass — I17 calls are yours)

1. **⚖️ Counterweight** — keep-or-retire, pre-registered ~28-Aug, on docket
   11.4d. This audit's evidence: post-screen flat (+$0.95/23), loss 119%
   unenterable class.
2. **🎯 Perp Sniper** — `unreachable` (n=30, −0.520%/t, t=−0.85), on docket
   11.4d.
3. **🏛️ turnbull** — needs ~29,465 days at its measured close rate; the
   purest I17 case on the docket.

## 6 · THE FORWARD METRIC (which book moved toward the gate)

- **🧘 douglas** moved: its published grade now measures the book that is
  actually running (n=4, +$2.64) instead of a phantom-priced one — the same
  kind of move `(hg)` made for eleven books, one book further.
- **🙏 avo shadow** remains the fleet's only above-bar book (t=+2.31,
  `on_track`) and its binding bar is `closes` — the one place where more
  samples is the answer. `(ne)` already took the capacity step; nothing to
  add without re-refusing what `(pu)` refused.
- Everything else is unchanged by design: the fleet's honest state is that
  its measured edge lives in the funding class, its funding cells are
  starved by the venue, and its clearest losses are already screened,
  retired, or on the operator's docket with dates.
