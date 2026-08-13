# 🏦 Rich Dad (`book-kiyosaki-lshadow`) — Rich Dad Poor Dad, translated into a book

**Operator, 13-Aug:** *"Please read the book rich dad poor dad by Robert
kiyosaki and create a bot from it."*

This document is the reading: Kiyosaki's core lessons, each mapped to a
mechanical rule, each rule mapped to the fleet evidence behind it. The bot is
`lighter_book_kiyosaki_bot.py`, service `book-kiyosaki-shadow`, $1,000 shadow,
zero keys — first of the BOOKS cohort (`book-<surname>-lshadow`, named for the
author; the Australian-musician rule keeps governing incubator-earned rows,
exactly as it did when Barnesy and Garrett carried their commissions' themes).

## Why a funding book is the honest translation

The book's central claim is an accounting identity, not a trading signal: an
ASSET puts money in your pocket, a LIABILITY takes it out, and the rich buy
assets. On a perps venue there is exactly one instrument that pays you for
holding it: **funding**. A position on the receiving side of funding is an
asset in Kiyosaki's literal sense — it produces cash flow every settlement
hour whether or not the price moves. A position paying funding is a liability
in the same literal sense.

The fleet's own ledger agrees with the book: every measured claim lives in
the FUNDING class (the 1-Aug allocation census: funding +$72.89 over 297
closes with three claims; directional −$9.21 over 867 closes with zero). The
growth move Kiyosaki names — own things that pay you — is the growth move the
fleet has already measured.

## The lessons, as rules

| # | Kiyosaki's lesson | The rule | Evidence status |
|---|---|---|---|
| 1 | *"An asset puts money in my pocket; a liability takes it out."* | Hold ONLY funding-receiving positions. A position whose funding flips against it has become a liability and is SOLD (`liability_flip`). | The carry thesis — 🌾's validated shape |
| 2 | *"The rich focus on cash flow, not capital gains."* | Delta-neutral MODELLED: P&L = accrued funding − modelled costs. `position_pnl` takes no mark argument — the no-price-term rule is structural, pinned in the selftest. | 🌾 carry's accounting, the fleet's best-evidenced book |
| 3 | *"Pay yourself first."* | The (gq) decay-paid discipline: a decayed position closes only AFTER accrued income has repaid every modelled cost + margin. Realized cash flow is published as `banked`. | **Measured**: +$71.42 on carry's `*_decay_paid` vs −$17.32 on its sided flips |
| 4 | *"It's not how much you make, it's how much you keep."* | **The one NEW rule — payback velocity**: at the entry rate, funding must repay the full modelled round trip (30bps) within `PAYBACK_MAX_H` (120h). Monotone in \|apr\|, so it can only TIGHTEN the validated 20% bar — effective floor ≈ **21.9% TRUE** at this friction model. | New; restrict-only by construction (I19: it admits nothing the 21-Jul sweep did not validate; it declines some of it) |
| 5 | *"Don't let fear and greed make decisions."* | Hysteresis both ends: 6h funding persistence before entry (greed guard — "persistent funding pays carries, spikes pay fees") and 1h flip grace before a liability sale (fear guard — one adverse print is noise). No discretionary paths. | Both bars validated on the 🌾 parent |
| 6 | *"Mind your own business — know your income statement."* | Every publish carries the book's income statement: `income` (accrued), `expenses` (modelled fees), `banked` (realized), and the live `assets`/`liabilities` split, derived from the same flip clock the exit rule maintains (one owner). | Observability; decides nothing |

### The inherited, validated config (the Barnesy carry cell, itself 🌾's)

| Gate | Value | Provenance |
|---|---|---|
| Entry bar | ≥ 20% TRUE apr | 21-Jul Lighter-tape gate sweep — the only bar that beat shipped on the full window AND both halves (+$55.93); (it) measured it binding |
| Persistence | 6h | parent's bar |
| Volume floor | $2M 24h | parent's floor |
| Decay bar | 0.01875 TRUE | both parents' 0.15-legacy exit, re-denominated |
| Flip grace | 1h | (gq) |
| Max hold | 336h | parent's recycle bound |
| Bleed stop | −2% of notional | parent's |
| Crypto perps only | `fleet_bus.is_crypto`, fail-open, revert `RICHDAD_ALLOW_NONCRYPTO=1` | (lk): carry's non-crypto era was 9-of-10 losers — a closed underlying satisfies persistence structurally (I7) |
| Capacity | $80 × 6 slots ($480 max deployed) | clip = Barnesy's carry cell; slot count is capacity, not policy ((hc): ordinary tuning, era-safe) |
| Friction model | 15bps/side both legs → 30bps RT, flat-conservative, declared | Barnesy's declared model (Lighter fee zero, measured) |

### Honest about the evidence (the (hm) clock)

The gates inherit their parents' Lighter-tape evidence. The COMBINATION —
and the payback tightening — is a NEW policy: fresh 30-day clock, nothing
inherited from any parent's ledger, gradeable **~12-Sep at the earliest** by
the standard gate (≥30 closes, mean>0, t≥2.0, both halves, maxDD<15%, ≥30d).
Config is ENV-ONLY with no tuning lane (the Garrett choice): the clock is
single-policy by construction and needs no freeze machinery. Registering
levers is a day-31 decision, taken only once the book is decidable (I17).

## What is deliberately NOT encoded

Stated so no future session "finishes" it:

- **OPM / leverage ("good debt")** — $1,000 no-top-ups is fleet law; leverage
  on a shadow book manufactures fake evidence.
- **"The rich invent money" as discretionary deal-making** — the assistant
  does not direct trades; every rule is mechanical. The mechanical residue of
  the lesson is the venue-wide scan: opportunities are taken wherever the
  whole funding map shows them, not from a hand list.
- **Real estate / business equity / paper assets as classes** — the venue
  trades perps; funding is the only on-venue cash flow and the honest
  analogue of rent.
- **"Make money work for you" as allocation-organ sizing** — the three
  funding shadow books size entries by `fleet_bus.allocation_scale` ((jr)
  S1); a NEWBORN book has no claim, so the scale would be degenerate at
  birth. A day-31 candidate once the book has evidence, noted here rather
  than wired dark.

## Birth checklist (the Barnesy parity list, applied)

- `claim_writer` at the TOP of the loop + `:standby` key for a stood-down
  container ((hp)/(ic)) ✅
- Funding-form (gr) exit telemetry on every close, literal dict at the call
  site (`entry_apr`/`exit_apr`/`accrued`/`fees`/`notional`/`held_h`); no
  prices — a price on a delta-neutral modelled row would be fabricated data ✅
- `snapshot_equity` from day one (`MTM_REQUIRED`) ✅
- TRUE-apr denomination via `funding_basis` throughout; no legacy thresholds ✅
- Durable hot-streak clock via `funding_basis.restore_hot_since` ((iu)),
  checked state read via `load_state_required` ((jd)) ✅
- Scan census incl. `noncrypto` (blocked-by-class-alone) and `slow_payback`
  (blocked by the book's own signature gate alone) ✅
- Registered: dashboard `VARIANT_ONLY`/`LABELS`/`OVERTRADE_LIMIT`/
  `DESCRIPTIONS`, `SELFTEST_MODULES`, `MTM_REQUIRED`, `ROW_ENTRY`, funding
  class in `fleet_allocation.FUNDING_BOOKS` + `study_exit_sweep` +
  `test_exit_telemetry` ✅
- Deploy: `Dockerfile.kiyosaki` (funding-family COPY set), declared in
  `MANUAL_IMAGES_OK` until the service exists; provision via the (lr)
  dispatch pattern (`kiyosaki-provision.yml`, DELETE after use), then
  activate the auto-deploy rule + move to `AUTO_IMAGES` ✅ (queue item)

## The payback arithmetic, shown

Hourly income at TRUE apr `A` on notional `N` = `N·A/8760`. Round trip =
`0.003·N`. Payback hours `P(A) = 26.28/A`:

| TRUE apr | payback | verdict at 120h bar |
|---|---|---|
| 20.0% (the validated floor) | 131.4h | refused — the literacy gate's tightening |
| 21.9% | 120.0h | the effective entry floor |
| 30% | 87.6h | enters |
| 50% | 52.6h | enters |
| 100% | 26.3h | enters |

A copy of the arithmetic is pinned in the bot's selftest so the effective
bar cannot drift silently from this table.
