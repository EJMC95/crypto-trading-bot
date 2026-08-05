# Lighter's REAL slippage — the measured distribution, and what flips at it (2026-08-05)

**Question** (operator mandate: *"find the avenue to ultimate growth and wins"*):
what is Lighter's real, MEASURED slippage — per book, entry vs exit — and which
previously-refused funding candidates / entry bars flip at measured friction?

**Method.** Every live fill with tx-hash-tier telemetry (`venue_orders`,
`shadow=FALSE`, `raw.fill_src='trades(tx)'`, `slippage_bps NOT NULL`) — the
23-Jul fill-read, decision price vs settled venue fill, POSITIVE = adverse
(the `_slip_bps_of` contract pinned in `implementation_shortfall.py`).
**n=158 measured fills, 2026-07-22 → 2026-08-04**, both real-money bots.
Liquidity tiers joined from the scout's `lighter-market.vols` (203 books,
0.04h old at read). Sweep re-runs use the cached 180d/25-book Lighter tape
(`scripts/.lighterfund_cache.json`, rebuilt 24-Jul) with code at HEAD, so
friction is the ONLY variable within each table —
[[ab-tests-must-vary-exactly-one-variable]].

---

## 1 · The measured distribution (first time the fleet has one)

Per-book, per-leg — bps per fill, positive = adverse:

| book | leg | n | median | p75 | p90 | max |
|---|---|---|---|---|---|---|
| 💸 Farmer (`perps-funding-lighter-lighter`) | open | 45 | **0.22** | 0.45 | 0.82 | 1.48 |
| 💸 Farmer | close | 46 | **0.36** | 0.53 | 1.05 | 2.06 |
| 💸 Farmer | ALL | 91 | 0.27 | 0.53 | 0.97 | 2.06 |
| 🎫 Ticket Taker (`lighter-ticket-taker-lighter`) | open | 34 | **4.36** | 7.85 | 11.20 | 31.52 |
| 🎫 Ticket Taker | close | 33 | **5.86** | 10.64 | 14.67 | 59.88 |
| 🎫 Ticket Taker | ALL | 67 | 5.06 | 8.96 | 14.28 | 59.88 |

**Round trips (median open + median close):** Farmer **0.58bps**, Taker
**10.2bps**. The doctrine holds and now has numbers: per-book, never
venue-wide — the two live books differ by **~18x**, tracking the books they
trade. Exits cost more than entries on BOTH books (close median 1.6x open on
the Farmer, 1.3x on the Taker) — an exit is taken when the tape is moving.

**Liquidity tier is the whole story** (24h $vol from the scout, monotone):

| tier | n | median | p75 | p90 | max |
|---|---|---|---|---|---|
| ≥$100M | 47 | **0.21** | 0.36 | 0.62 | 2.06 |
| $10–100M | 44 | **0.43** | 0.77 | 1.14 | 11.56 |
| $1–10M | 15 | **1.93** | 7.00 | 9.69 | 29.48 |
| <$1M | 52 | **5.12** | 9.11 | 14.77 | 59.88 |

**Exit-reason split (closes):** the Taker's `sl` exits are its expensive tail —
median 5.35 but **mean 10.0, p90 22.8, max 59.9** (ZHIPU, a <$1M book) vs `tp`
median 6.93/mean 4.19. A stop fires INTO the adverse move, so the worst cost
lands exactly on the losers. The Farmer's exits are flat across reasons
(decay 0.33 / flip 0.43 median).

**Model vs measured — the ShadowBroker is honest.** Same-window medians:
Farmer shadow model 0.43 vs live measured 0.27 (model ~60% pessimistic); Taker
shadow model 3.83 vs live 5.06 (model ~24% optimistic); the Farmer's
decision-time `scan.slip_bps` modelled 0.30 vs measured 0.22 on the same
opens. Everything within ±60% at the median, errors in BOTH directions — so
shadow-ledger P&L (what `golive_readiness` grades, what the tuner's replay
gate judges) is denominated in a defensible friction, and the 17-Jul n=1
"within 6%" read generalises. 🌾 carry's shadow arm models **1.01bps/fill
median (n=218 all-time, p90 3.44)** — consistent with its books' measured
tier (its $2M floor sits in the $1–10M tier, measured median 1.93).

---

## 2 · Where the OLD friction assumption is load-bearing (inventory)

| constant | where | assumed | measured replacement | verdict-sensitivity |
|---|---|---|---|---|
| `SLIP` = `BT_SLIP_BPS` default **5.0** | `scripts/backtest_funding_lighter.py:256` | 5bps/fill ("came from nothing" — its own comment) | Farmer measured **0.27 median / 0.97 p90** (n=91) | DECISIVE for the full-window sign — §3b: −$17.87 at 5bps vs +$15.60 at measured, same tape same code. Default stays pessimistic BY DESIGN; always run the measured band. |
| `PERP_FEE` = **0.00045** (4.5bps/side) | `funding_carry_bot.py:151` | HL taker fee | **REFUTED on Lighter**: venue taker fee measured 0.0000 on all 203 books; real perp-leg cost = slip only, ~1–2bps/side at carry's tier | The shadow arm already bypasses it (measures the perp leg); the 29bps round trip in `(it)`'s refusal arithmetic still carries it. §3a re-runs without it. |
| `HEDGE_COST` = **0.0010** (10bps/side) | `funding_carry_bot.py:152` | CEX-spot hedge fee+spread | **UNMEASURED AND UNMEASURABLE HERE** — Lighter has no spot; no hedge order has ever existed. 20 of carry's ~29bps round trip is this model. | NOW THE load-bearing constant for every carry verdict. No fill telemetry can replace it; only building a real hedge leg would. Stated, not fixed. |
| `OPEN_COST` = `0.00045 + 0.0010` retyped | `scripts/backtest_carry_gate_lighter.py:81` | copy of the two above | same | The retyped-constant trap the file itself documents for `MAX_POSITIONS`; every `(it)` gate verdict is denominated in it. §3a varies it on a fixed tape. |
| `SCAN_MAX_SLIP_BPS` = **25** | `lighter_funding_bot.py:304` | cap on modelled clip-VWAP slip at entry | model validated (0.30 vs 0.22 measured); 25 ≈ 26x the Farmer's measured p90 | Non-binding on the books it admits — a wide seatbelt, not a mis-measure. No change indicated. |
| `TT_SPREAD_GATE_BPS` = **20** | `lighter_ticket_taker.py:292` | entry veto on quoted spread | Taker measured median 5.06 / p90 14.28 under this gate | The measured fills VALIDATE the gate's scale ([[taker-shift-is-execution-not-decay]]: execution IS the taker's binding cost). Keep. |
| ShadowBroker book-walk | `venues/shadow.py::fill_from_book` | model, adverse-only, floored at 0 | within ±60% of measured at the median, both books, both signs | Shadow ledgers and replay gates are denominated in an honest friction — an enabling validation for the whole evidence pipeline. |
| Taker go-live round trip **29.2bps** | 17-Jul estimate, n=1 ([[lighter-slippage-is-per-book-not-per-venue]]) | 14.6bps/fill | measured rt **10.2bps median** (n=67), ~25bps around p90 | The "−3.9bps edge" arithmetic used ~the p90 as its point estimate. §3c. |

Not friction-bearing (checked): `golive_readiness` (grades ledger P&L, which
embeds the validated shadow model), `funding_basis.py` (basis only),
`study_farmer_take_profit.py` / `study_farmer_stop_isolated.py` (already
sweep measured values).

---

## 3 · THE FLIP LIST — the decisive arithmetic at measured friction

### (a) 🌾 carry's `enter_apr` — the `(it)` refusal RE-CONFIRMED at measured cost

`(it)` refused the 20%→10% walk at a modelled 29bps round trip (4.5 perp fee +
10 hedge, ×2). Decomposed at measured: the perp fee is refuted (venue fee 0,
measured slip ~1.1bps/side at carry's tier), so the honest round trip is
**~22.3bps = ~2.3 measured perp + 20 MODELLED HEDGE**. Break-even holds
against the 336h `MAX_HOLD`:

| entry gate | @29bps | @22.3bps (measured perp) | @20bps (perp FREE) |
|---|---|---|---|
| 5% TRUE | 508h — cannot pay | **391h — still cannot pay** | 350h — still cannot pay |
| 10% | 254h (margin 82h) | 195h (margin 141h) | 175h (margin 161h) |
| 20% (shipped) | 127h | 98h | 88h |

The 5% refusal is **robust to everything measurable** — even a FREE perp leg
cannot pay inside `MAX_HOLD`, because the hedge model alone is 20bps. And on
tape: the `(it)` gate cascade re-run on the cached 180d/25-book tape,
`MAX_POSITIONS=12`, NOTIONAL $300, varying ONLY friction:

| gate | @29bps rt | @22.3bps | @20bps (perp free) | both halves + |
|---|---|---|---|---|
| 0.05 | −471.98 | −278.89 | −214.31 | no, at every friction |
| 0.10 | −263.54 | −127.44 | −80.23 | no, at every friction |
| 0.15 | −0.29 | **+66.71** | +88.52 | **flips to YES at ≤22.3bps** (h1 +28.61 / h2 +34.65) |
| 0.20 (shipped) | +34.83 | **+92.47** | +111.26 | yes at every friction |

(25-book top-volume universe through 24-Jul — a different tape than `(it)`'s
21-Jul 40-book run, so read the orderings and deltas, not the levels.)

**Verdicts, precisely:**
* **10% stays REFUSED** — negative on the full window at every friction
  including a free perp leg. The refusal survives on better data; filed as a
  refusal re-confirmed, which the standing rules count as a valid output.
* **NEW at measured friction: 15% flips from breakeven-negative to
  both-halves-positive** (+$66.71, h1/h2 both +). But it still does **not
  beat shipped** (+$92.47 at 20%, also both-halves) — net RISES with the gate
  everywhere in the sweep, so walking down to 15% buys 50 extra closes with
  −$26 of net: turnover bought with expectancy, the exact shape the standing
  rule rejects. No walk indicated; the flip is recorded because it moves the
  BOUNDARY of the refused region (10% is refused on tape; 15% is now refused
  only on "does not beat shipped").
* Everything above is conditional on the 20bps hedge model (§2). What would
  actually move carry is the venue's funding distribution widening
  ([[carry-stalled-venue-funding-collapsed]]) or a REAL hedge leg cheaper
  than the model — unmeasurable until built.

### (b) 💸 Farmer's gate and candidate set — the sign flips at measured cost; the halves do NOT

Same tape, same code, gate 0.05 (live), ONLY slip varied:

| slip/fill | P&L 180d | h1 | h2 | win% | maxDD | n |
|---|---|---|---|---|---|---|
| **0.27 (measured median, n=91)** | **+$15.60** | −15.01 | +27.59 | 57.2 | −49.24 | 1415 |
| 0.97 (measured p90) | +$10.65 | −17.72 | +25.39 | 56.9 | −50.39 | 1415 |
| 5.0 (the old assumption) | **−$17.87** | −33.34 | +12.69 | 54.1 | −57.00 | 1415 |

* **Confirmed at 2x the fills:** the assumed 5bps flips the full-window SIGN
  (−$17.87 → +$15.60). "The strategy is dead" remains an artifact of the
  unfounded constant, exactly as the 23-Jul study and the withdrawal in
  [[funding-farmer-carry-cannot-pay]] concluded.
* **DISCREPANCY, stated rather than absorbed:** `FUNDING_GATE_LIGHTER_2026-07-23.md`
  reported gate 0.05 **both-halves-positive** (+$33.47, h1 +24.74) at
  measured slip. On the 24-Jul cache at HEAD, **h1 is NEGATIVE at every
  slip** — the property does not reproduce. The tape differs by one day and
  by universe composition (top-25-by-volume drifts daily: SPCX has 53d of
  pairing, SOXL 42d, US500/US100 77d) and the script has changed since
  ((dt) slope study, (eu) decay hook — both claim replay-neutral defaults).
  [[backtest-cache-serves-the-wrong-universe]] documents exactly this class:
  universe composition flips verdict signs. **Until a fresh-universe re-run
  adjudicates tape-vs-code, the Farmer's carry lane is "full-window positive
  at measured cost, halves REGIME-SPLIT" — not "both-halves-robust".** That
  is consistent with the live book's own record (t=1.73, n=68, not yet
  significant — [[the-fleet-edge-is-unmeasured-not-absent]]) and with h2
  (recent months) holding the entire edge.
* Candidate-set arithmetic on today's live scout snapshot (breakeven APR =
  rt × 8760 / hold, at the live book's own median hold **5.9h**, measured
  from its 59 in-era closes; ≥$10M books):

| friction | breakeven APR | books clearing TODAY |
|---|---|---|
| assumed 5bps/fill | 148.5% TRUE | **0** — nothing on the venue can ever pay |
| measured p90 band (2bps rt) | 29.7% | 1 (SKHYNIXUSD 112%) |
| **measured median (0.58bps rt)** | **8.6%** | **5** — SKHYNIXUSD + BTC/ETH/SOL/HYPE at the 10.5% resting default |

  At assumed friction the venue's crypto RESTING DEFAULT (10.5% TRUE) needs
  an 83h hold — structurally impossible against the 72h cap; at measured
  friction it pays at **≥4.8h vs the 5.9h the market grants**. The carry
  lane's ARITHMETIC is alive at measured cost; whether it is an EDGE stays
  an open grading question (see the discrepancy above).
* Slip-invariant and unchanged from 23-Jul: widening the gate UP (≥0.12)
  loses at every slip level, and the **~2bps tripwire stands** — worst single
  measured fill in 13 days: 2.06bps. `impl-shortfall.order_slip.live` is the
  guard and it is already published and paged.

### (c) Memory-doc verdicts that hinged on the number

* [[funding-carry-structural-edge-lighter]] — *"friction-bound; zero perp fee
  flips it"*: **measured friction does NOT unlock its 3bps both-perp row.**
  The perp fee IS zero (confirmed), but that row's hedge is a second perp,
  and the same memory already rejected it — cross-venue funding is arbitraged
  tight, so a perp hedge collapses the carry to a ~7% spread. The live shape
  is the 20bps CEX-hedge row, which is hedge-model-bound, not perp-bound —
  §3a's conclusion. No flip.
* [[lighter-slippage-is-per-book-not-per-venue]] — the taker's **29.2bps
  round trip (n=1)** vs measured **10.2 median (n=67)**: the "−3.9bps edge"
  read used ~the p90 as its point estimate. At the measured median the same
  25.3bps/4h gross would read ~+15bps net. NOT a go-live argument — the
  gross is a 17-Jul point-in-time number, the `sl` tail (max 59.9bps) lands
  exactly on losers, and the live book's own realised record (+0.558%/trade
  divergence, I14) is the senior evidence either way. Filed as: the taker's
  execution cost is ~half the n=1 estimate at the median, and its binding
  cost is the stop-loss tail on <$1M books, not the median fill.
* [[funding-farmer-carry-cannot-pay]] — the ~110% breakeven headline was
  withdrawn 22-Jul; §3b is its measured replacement (8.6% at the live hold).
  Its one surviving claim — *"no gate passes both halves"* — is, on the
  current cache, TRUE again at gate 0.05 (h1 negative even at measured
  slip); the 23-Jul narrowing does not reproduce at HEAD. Discrepancy owner:
  next funding-economics pass, `--refresh` first.

---

## 4 · HONESTY GATES — what n=158 cannot say

* **Concentration.** The fills are the two live books' own universes: 91 of
  158 are four liquid majors (ETH/HYPE/BTC/SOL); the thin-book evidence is 67
  taker fills over ~23 coins, many n≤2. The per-tier medians are real; a
  PER-BOOK number for any book not in this sample is an extrapolation — per
  doctrine, quote the book's own arm, never a venue number.
* **Clip size.** Everything was measured at **$10–38 notionals** (taker
  median $10, Farmer $20). Slippage at these clips says nothing about $100+
  clips — adverse-selection scaling on Lighter is UNMEASURED. Any sizing
  decision citing this study inherits that caveat.
* **Taker-style only.** Both live books cross the spread. Maker fills: zero
  measured, ever. A maker-first execution path needs its own telemetry
  before any verdict cites it.
* **The hedge is a model.** Carry's 20bps round-trip hedge component has no
  measurement path on this venue. Every carry verdict, including §3a's
  re-confirmation, is conditional on it.
* **Window.** 13 days of live fills, one (falling-BTC) regime. The 59.9bps
  ZHIPU stop is the one glimpse of stress-tape cost — the tail to respect.
* **Backtest levels are tape-relative.** §3a/§3b levels moved between the
  23-Jul run and this one on a one-day cache rebuild + code drift; only the
  within-table orderings (friction varied, tape fixed) are the claims here.

---

## 5 · ROUTES (standing table — nothing hand-set)

1. **Refusal re-confirmed (§3a):** `carry.enter_apr` stays 1.60 (20% TRUE).
   No lever moves; 10% is refused on tape at every friction, and 15% —
   though newly both-halves-positive — does not beat shipped. If any organ
   later proposes either walk, this study is the measured refutation to cite
   with `(it)`.
2. **Farmer (§3b):** no gate change — 0.05 is where the full-window edge
   lives and widening up loses slip-invariantly. The actionable object is
   the existing tripwire: `impl-shortfall.order_slip.live` drifting past
   ~2bps kills the measured edge; it is already published and paged — keep
   it load-bearing. `live.funding.*` stays the experiment judge's queue; no
   candidate filed because no bar moves.
3. **Adjudicate the 23-Jul discrepancy (§3b):** next funding-economics pass
   runs `backtest_funding_lighter.py --refresh` (fresh universe, ~1h throttled
   fetch) and records whether h1's sign was tape or code. Until then no claim
   of "both-halves-robust at measured slip" may cite the 23-Jul doc alone.
4. **Taker `sl` tail (§1):** the expensive tail is stop exits on <$1M books
   (mean 10bps, max 59.9). Any future symbol-eligibility / clip proposal for
   the taker should use the per-tier table as its friction prior, routed as
   always via `fleet_proposals.py` → the scout tuner's replay gate. No
   proposal filed today: the live taker is divergence-short-only behind hard
   gates and the tail n is small.
5. **Backtest hygiene:** any future funding-economics run uses the measured
   band (0.27–0.97 Farmer-tier, ~1–3.4 carry-tier, ~5–15 taker-tier per
   fill) instead of `BT_SLIP_BPS=5.0`; the pessimistic default deliberately
   stays in the file.

**The single highest-expectancy route:** #2 — the Farmer's live carry lane at
gate 0.05 protected by the already-wired ~2bps slip tripwire. It is the one
place where measured friction turns an assumed "cannot pay" into "pays at the
hold the market grants, on the venue's resting state" (full-window +$15.60 vs
−$17.87 at the assumed constant, breakeven 8.6% vs 148.5% TRUE) — earned by
measurement, not by moving any lever, and honestly caveated: its first-half
regime is negative, so the edge is not yet gate-grade evidence and the route
costs nothing if it stays that way.
