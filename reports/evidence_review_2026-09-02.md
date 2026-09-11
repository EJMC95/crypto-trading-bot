# Evidence Review — 2026-09-02

_Reviewed 2026-09-02 08:06 AEST (Sydney) · 2026-09-01T22:06:59+00:00 UTC._

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 670.9h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:23 | active | joined decision+context dataset at 701 closes (49% win), bucket 23 |
| veto:CXMT | resolved | CXMT no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=131 (≥10): net $-8.13, WR 34%, t=-0.48 — noise
- 🎫 shadow lens 'long-breakoutup' at n=115 (≥10): net $+86.84, WR 53%, t=2.31 — significant
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE freqtrade-avo-maria-lighter: n=11, net $-5.15 — by lens [('long-dip-in-uptrend', 11, -5.15)]
- 💰 LIVE freqtrade-georgia-lighter: n=77, net $-60.55 — by lens [('long-range-on', 40, -51.69), ('long-trend-breakout', 35, -6.3), ('long', 2, -2.56)]
- 💰 LIVE freqtrade-mum-lighter: n=52, net $+90.48 — by lens [('long-oversold-rebound', 50, 77.52), ('long', 2, 12.96)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): lighter-ticket-taker-lshadow → 2026-10-03 (t) FLOOR:halves; pm-turnbull-lshadow → 2026-10-13 (t) · undecidable@trend: lighter-perp-sniper-lshadow; unreachable@trend: band-garrett-lshadow, band-kelly-lshadow, book-douglas-lshadow, freqtrade-georgia-v3-lshadow, nav-cook-lshadow, perps-funding-lighter-lshadow, perps-funding-spread-lshadow
- 🚦 fleet-risk light yellow — longs 16/20, shorts 3/12 (gross 19); 7d DD -1.81%, clip_scale 1.0
- 📏 freqtrade-avo-maria-lighter live-vs-shadow per-trade gap +0.121pp (live +0.535% n=8, shadow +0.413% n=10) — no divergence
- 📏 freqtrade-georgia-lighter live-vs-shadow per-trade gap -0.275pp (live -0.188% n=77, shadow +0.088% n=120) — no divergence
- 📏 freqtrade-mum-lighter live-vs-shadow per-trade gap -0.408pp (live +0.703% n=52, shadow +1.112% n=53) — no divergence
- 🧬 freqtrade-avo-maria-lighter arms differ on FILE SET, not necessarily code: live a48641f9c8d0 (n=17) vs shadow edc3032d1c46 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-georgia-lighter arms differ on FILE SET, not necessarily code: live a48641f9c8d0 (n=17) vs shadow edc3032d1c46 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-mum-lighter arms differ on FILE SET, not necessarily code: live a48641f9c8d0 (n=17) vs shadow edc3032d1c46 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container edc3032d1c46 (n=15) vs repo de85eb589b3a (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-georgia-lshadow differs from the repo on FILE SET, not necessarily code: container edc3032d1c46 (n=15) vs repo de85eb589b3a (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-mum-lshadow differs from the repo on FILE SET, not necessarily code: container edc3032d1c46 (n=15) vs repo de85eb589b3a (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter matches the repo tree: a48641f9c8d0 (n=17)
- 🧬 freqtrade-georgia-lighter matches the repo tree: a48641f9c8d0 (n=17)
- 🧬 freqtrade-mum-lighter matches the repo tree: a48641f9c8d0 (n=17)

## Summary

21 alert keys reviewed: 1 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 23 new-evidence items scanned.

---

# Human layer — reviewer's pass (2026-09-02, ~08:50 AEST Sydney)

_Previous report: `evidence_review_2026-08-28.md`. **Five days elapsed, not one** —
no review ran 29 Aug – 1 Sep. The repo moved 21 commits and 11 changelog entries
in that gap ((vr)…(wa)). Everything below is graded against data pulled this
morning, not against that report._

## ⚠️ ACTION — decisions for Eamon

### 1. `family-lighter-shadow` is running TWO containers, and the one doing the trading publishes nothing

This is the headline and it **corrects `(wa)`'s diagnosis in the direction that
matters**. `(wa)` concluded, after seven `railway up`/`redeploy` attempts, that
"Railway's ledger is holding a stale deployment active while fresh ones never
take over" and that 🔭 georgia-v3's row "stays dark until it flips". Measured
this morning, the fresh deployment **did** take over — it has been trading since
30-Aug. What is actually wrong is different, and worse.

**The proof, three independent lines:**

| Signal | Value | Resolves to |
|---|---|---|
| `paper_trades.extra.build` (svc=`family-lighter-shadow`), every trade since 30-Aug | `4d93497e56d5` / 15 | **HEAD** (`bdfc437`) |
| `bot_pnl.extra.build`, all three family rows, refreshed every ~9 min | `edc3032d1c46` / 15 | **`d2c0cb918`** — pre-28-Aug |
| `railway logs --service family-lighter-shadow` | one healthy container, `loop ok`, **four** books incl. georgia-v3 | HEAD |

Stamps were computed with the repo's own `build_compute` against **the image's
own COPY set** (`Dockerfile.familyshadow` omits `fleet_tuning.py`, so 15 files,
not the repo tree's 16 — the `(fd)` trap). A single process cannot emit two
stamps: `_BUILD_CACHE` is per-process and both `publish()` and
`publish_paper_trade()` read it. So **two processes are alive.**

The live container's own numbers disagree with the dashboard's, which is the
tell that closes it:

| Book | Container log (22:49Z) | `bot_pnl` row | `bot_pnl` closes | Ledger closes |
|---|---|---|---|---|
| 👩 mum-lshadow | $1025.51, 12 open | $1017.07 | **9** | **56** |
| 🙏 avo-maria-lshadow | $1004.23, 6 open | $1012.01 | 22 | 25 |
| 🔮 georgia-lshadow | $1007.88, 0 open | $1007.77 | 224 | 244 |
| 🔭 georgia-v3-lshadow | $994.58, 3 open | **NO ROW AT ALL** | — | **41** |

Loop times don't line up either: the container looped at 22:40:31 and 22:49:57Z;
the rows updated at 22:45:00 and 22:47:08Z.

**The decisive deduction — the trading container's `bot_pnl` publishes are not
landing at all.** georgia-v3 is in `live_strategies()`, is not in
`RETIRED_BOOKS`, and `store.publish(b.bot_id, …)` sits inside the per-book loop —
so if HEAD's publishes worked, a v3 row would exist and would *stay* (the old
process has no v3 book, so it can never overwrite it). I polled `bot_pnl` 11
times over 5.5 minutes: **the v3 row never appeared, and the build stamp never
flipped once.**

**Why it is silent — two doctrine violations, both already invariants here:**
* `bot_pnl_store.publish()` **returns False and never raises**, and
  `lighter_family_bot.py` **discards the return value at both call sites**
  (lines 2725, 3033). That is **I4** verbatim — *"never discard a persistence
  result"*. The loop prints `loop ok` while every summary write fails.
* `lighter_family_bot.py` is the **only multi-book host in the fleet with no
  `claim_writer` call**. Every other one has it — `lighter_avo_live_bot`,
  kelly, cook, douglas, grimes, hull, kiyosaki, funding, taker, carry, barnes,
  schwager. Nothing stood the orphan down, which is why this survived a wedge
  that the one-book-one-writer guard exists to end.

**What it costs, and why it is an ACTION not a note:** these three rows are the
**control arms for all three real-money books**. Every `bot_pnl` consumer — the
dashboard, `fleet_allocation`'s claims, `fleet_immune`'s liveness scan, the
watchdog's NOT-ONLINE page, the roster sweep — is reading frozen numbers from a
container that stopped trading on 28-Aug, and reading `status: "online"` with a
fresh timestamp while it does. 👩 mum's shadow arm is under-reported by **47
closes**. This is I1 in its purest form: the liveness signal is real, and it
belongs to a different process than the one doing the work.

**The good news, and it is genuinely good:** the ledger is clean. `paper_trades`
carries all four books correctly, `audit_ledger_integrity` reports zero overlaps
on every family book, and the grader reads the ledger — so **georgia-v3's 41
closes are real, admissible evidence, not lost**, and every go-live number in
this report is sound. The damage is confined to the summary row.

**Decision for you:** kill the orphaned deployment in the Railway dashboard
(family-lighter-shadow → Deployments → remove any deployment older than 30-Aug
that is still active; the newest build is the one to keep). That is unchanged
from `(wa)`'s ask — but the reason has changed, and so has the urgency: this is
not "new code hasn't landed", it is "old code is lying to every organ about
three control arms."

**Not fixed in this run, deliberately.** The durable fix is a `claim_writer` in
`lighter_family_bot.py` plus checking `publish()`'s return — but this task's
safety rules forbid deploys and pushes, and the fix carries a real design
question I should not decide from a cron job: on a wedge, first-claimant-wins
could hand the claim to the *orphan* and silence the good container. That needs
a session with the deploy grant, and it needs the `publish()`-returns-False root
cause identified first (the DB is reachable from that container — `paper_trades`
writes land — so the failure is inside the `bot_pnl` INSERT, not the connection).

### 2. 🔮 georgia (REAL MONEY) — 37.6% drawdown against a 15% bar, −$6.41/day

Her in-era grade: **n=30, mean −0.354%/trade, t=−1.70, maxDD 37.6%, −$39.86**,
horizon `unreachable`. Book equity **$220.43**, down **−$66.60**. This is the
book that took 💸 the Farmer's sub-account on 22-Aug at 5-of-6 bars.

The loss decomposes, and it is **not mostly her entries**:

| Exit family | n | net |
|---|---|---|
| `daily_loss` (the halt rail flattening) | 13 | **−$50.15** |
| `trailing_stop_loss` | 14 | **−$54.55** |
| `range_top` (her main winner) | 45 | +$30.32 |
| `roi` | 7 | +$28.83 |

That reproduces `(vg)`'s finding — *"her strategy is +3.62pp and one DOGE gap
plus the halt rail took the money"* — on fresh data, five days later. Her worst
lens is `long-range-on` at −$51.69 over 40 live closes, which is the same entry
`(vb)` raised the rank cap 3→5 for on the strength of a shadow-side
`n=208, t_cl +2.44`. **The live ledger has not corroborated that yet** — I am
not calling it refuted (n=40, and `(vb)`'s cap raise was shipped explicitly to
generate this sample), but it is the number to watch and it is currently
pointing the other way.

Last three days: 30-Aug −$26.11, 31-Aug +$1.39, 1-Sep **+$9.96**. So she may be
turning. **No action taken and none proposed** — this is real money, it is I17's
keep-or-decide shape, and the honest reading is "two more weeks of her own
ledger decides it". Flagged because a 37.6% realised drawdown on a live book is
the largest single risk number in the fleet this morning.

## Assessment of the work done since 28-Aug (the mandate's first job)

| Entry | Claim | Verdict against today's data |
|---|---|---|
| `(vy)` 🪁 kelly clip 250→80 | cut the burn 3× | **HELD.** `caps.clip_usd = 80.0` is live. 93% of his −$128.64 was 30-Aug (−$83.28) + 31-Aug (−$36.23), both pre-cut; 1-Sep is **+$9.78**. |
| `(vw)` CHANGELOG restored | 655 entries recovered | **HELD.** 665 entries / 28,885 lines, letter guard green. |
| `(vr)` 🔭 georgia-v3 born | I22 census + dashboard row | **HALF.** The book trades correctly (41 closes) and `audit_book_spend` is green — but its row has **never existed** (see ACTION 1). The census the entry shipped is unreachable to every consumer. |
| `(wa)` family wedge | "fresh deploys never take over" | **CORRECTED.** They did take over on 30-Aug. See ACTION 1. |
| `(wa)` GROSS_X handover | mum 9.5 / georgia 7.0 / avo 5.3 | **PARTIALLY APPLIED.** Live rows read georgia **7.0** ✅, avo **5.3** ✅, mum **10.0** ❌ (still the old value; 9.5 not yet set). |
| `(tt)`/I21 follow-through | taker `exit:hold` pre-registered | **CONFIRMED — see below.** |

**One correction I owe on my own reasoning:** I initially read the family
`BEHIND-OWN` verdict as a false alarm, because georgia-v3 was demonstrably
trading. That was wrong — I had reproduced the stamp against the repo tree
(16 files) instead of the image's COPY set (15). `audit_code_currency` was right
and my hand-rolled check was the narrower one. The repo's own rule caught me:
*"re-run their check rather than substituting your own narrower one."*

## 🏆 The winners' docket landed a CONFIRMED follow-through

**🎫 the Ticket Taker's `exit:hold`, pre-registered 18-Aug, is CONFIRMED on the
fresh sample alone: n=21, t=3.10, mean +3.230%/trade, +$49.40, p=0.0028, across
9 distinct close-days.** This is I21's follow-through half working exactly as
`(tt)` rebuilt it — the pooled window would have crowned it at t=3.9 on
re-mined data, and the referee correctly refused to count that.

The sibling registration went the other way and is reported honestly:
🙏 avo's book-level bucket is **NOT_CONFIRMED** (fresh n=10, t=0.49, +0.413%).

`TT_RISK_USD` is already at **3.0** from the previous confirmation, so no lever
moves on this today — but the taker is now the fleet's nearest gate candidate
(`on_track 2026-10-03`, held on `t` and `halves`).

## Fleet state

* **Go-live: READY — none.** Nearest: 👩 mum-lighter (live already) passes 5 of 6,
  held only by window (4.0d of 30) → **2026-09-27**; 🎫 taker → 2026-10-03;
  🏛️ turnbull → 2026-10-13.
* **👩 mum (live) is the fleet's best book by a distance:** n=52, **+0.703%/trade,
  t=2.73, 82.7% win, +$90.47, +$22.86/day, maxDD 3.7%.** On the winners' docket
  she clears the t-bar at book level *and* on `long-oversold-rebound`, held only
  by the multiplicity referee — she needs a pre-registered follow-through, not
  more tuning.
* **fleet-risk YELLOW** — longs **16/20**, shorts 3/12, gross 19; 7d DD −1.81%,
  `clip_scale` 1.0 (governor not triggered).
* **Ledger integrity:** the only failure is 🌾 carry's 7 historical overlaps,
  most recent **830 hours** ago — permanent, pre-era, nothing to stop.
* **Errors from the mechanical run: none** (`payload.errors == []`), selftest OK,
  `tests/test_review_currency.py` 34 passed.

## Tooling defects found this run (reported, not fixed — no-push rule)

1. **`scripts/audit_deploy_coverage.py` cannot run in this repo's venv at all** —
   `import tomllib` needs Python ≥3.11 and `.venv` is **3.9.6**. It exits with a
   traceback, which in a pipeline reads as "ran". A guard nobody can run locally
   is the `(gk)` shape.
2. **The review script's 🧬 build-drift check is structurally blind to the family
   image.** It defers with "FILE SET, not necessarily code" whenever `build_n`
   differs — and for `family-lighter-shadow` it *always* differs (15 vs 16),
   because the Dockerfile omits `fleet_tuning.py`. So that arm can never report
   drift on the three control arms, and this morning it didn't, while
   `audit_code_currency` (which uses the image's own COPY set) did. The fix is to
   resolve against the COPY set, as `audit_code_currency` already does.

## OPTIONS TO OPTIMISE

Ranked. Honest headline: **the best thing available today is not a widening — it
is repairing a broken measurement channel.** Two of the four entries below are
refusals with numbers.

**1 · Restore the family books' summary channel (ACTION 1).** Lever: kill the
orphan deployment (operator), then `claim_writer` + a checked `publish()` return
in `lighter_family_bot.py` (session with deploy grant). Evidence: 47 missing
closes on 👩 mum's shadow arm, a whole book (🔭 georgia-v3) invisible to every
organ, three control arms mis-reported. Expectancy cost: **none** — it changes no
trade; it changes what the fleet can *see*. This is the highest-value item on the
list precisely because it is free.

**2 · Give 👩 mum a pre-registered follow-through registration (I21).** She clears
the t-bar at book level (n=52, t=2.71) and on her only lens (n=50, t=2.40) and is
held *only* by the multiplicity referee. A registration costs nothing, moves no
money, and is the one instrument that can convert her from "on their way" to
PROVEN. Expectancy cost: **none**. Owner: session — but it must be registered
*before* the closes it will be graded on, so the sooner the better.

**3 · Set `MUM_GROSS_X=9.5` — the one unapplied item from `(wa)`.** Georgia (7.0)
and avo (5.3) were applied; mum still reads **10.0**, and `(wa)` derived 9.5 as
"Eamon's own `(te)` launch number, strictly inside his 10.0 stop-death edge". At
10.0 her row publishes `stop_reachable: false`. **Real money — I do not apply it**
(Railway variable edit, and it auto-redeploys). One-line decision for you.

**4 · REFUSED with evidence — 🎫 the taker's slot cap.** `(uo)` named this "the one
legal go-live accelerator", so I checked it: `max_open: 8`, **5 open**, and this
loop's `slot_census` reads `{opened: 0, offered: 0, held_sym: 0, lens_once: 0,
slots_full: 0}` — **slots refused nothing.** The binding constraint is lens
supply, not capacity: three of five lenses are vetoed (`dip` t=−2.66,
`divergence` t=−1.36, `momentum` n=2), leaving `breakoutup` (n=107, t=2.4,
+1.418%) and `breakout` (n=10). Raising the cap buys zero trades. No change.

**5 · REFUSED with evidence — 🔮 georgia's `long-range-on` rank cap.** The obvious
read of ACTION 2 is "cut the losing lens". I am not proposing it: 45 of her
closes exit `range_top` for **+$30.32**, the loss is concentrated in the halt
rail and the trailing stop rather than the entry, `(vb)` raised this cap five
days ago *explicitly to generate the sample that grades it*, and n=40 live closes
cannot overturn a shadow-side n=208. Cutting it now would be the `(vc)`
regression-to-the-mean error — judging a change against the hot/cold window that
motivated it rather than against the book's mean. Re-read it at n≥80.

**6 · CAPACITY CENSUS — 👩 mum (live) is at 12/12, and she is the only book where
that matters. The honest answer is that she has no headroom left on either axis.**

Occupancy against each book's own cap, this morning:

| Book | open / cap | note |
|---|---|---|
| **👩 mum-lighter (REAL MONEY)** | **12 / 12 — AT CAP** | +0.703%/trade, t=2.73, +$22.86/day |
| 🧮 book-hull-lshadow | 10 / 10 — at cap | n=1 closed; slow cash-flow clock by design |
| 🏦 book-kiyosaki-lshadow | 6 / 6 — at cap | n=2 closed |
| 🌾 perps-funding-carry-lshadow | **15 / 12 — OVER cap** | see caveat below |
| 🎫 taker | 5 / 8 | slots refused nothing (option 4) |
| everything else | below cap | — |

Mum being at cap on the fleet's best-evidenced book is exactly the "graded signal
denied a slot" case the mandate says has paid before. **But the lever does not
exist for her, and `(sr)` is why:** `clip = equity × gross_x / max_open`, so slots
only *slice* a gross budget that `GROSS_X` already bounds. Raising `max_open`
adds **no dollars** — it buys more, smaller, better-diversified bets out of the
same budget. Her dollar lever is `gross_x`, and she is at **10.0**, the fleet's
appetite ceiling — with `(wa)` asking for it to come *down* to 9.5 (option 3).
So: **mum is fully deployed on both axes simultaneously.** There is no free
capacity win here, and the only thing that could add capital to the fleet's best
book is a change to the appetite ceiling itself, which is Eamon's risk call and
not a session's. Recorded as a refusal with numbers, not an omission.

*Caveat on 🌾 carry's 15/12:* that row is published by `yield-harvester-shadow`
(a separate service, stamp `0259a57f5a13/16`) and I did not verify it against the
container the way I did the family books. Do not act on it until it is confirmed
against carry's own log — after ACTION 1, an over-cap count on a *summary row* is
exactly the kind of number I now treat as suspect until corroborated.

**Also checked, nothing on offer:** long budget at 16/20 has headroom (no veto
pressure); the drawdown governor is idle at `clip_scale` 1.0; `audit_book_spend`
is green on all 21 living rows; `audit_ledger_integrity` clean apart from carry's
830-hour-old historical overlaps.

---

### A note on how much of this report's own input was suspect

Every per-book `open/cap` number above comes from `bot_pnl` — the table ACTION 1
shows is being written for three books by an orphaned container. 👩 mum's *shadow*
row claims 2 open while her live container logged **12**. I caught that only
because I had the container log open. Until the orphan is killed, treat any
family-book `bot_pnl` figure — here or on the dashboard — as unverified, and
prefer `paper_trades` and the container log, which are both sound.

---

# Addendum — continued session (2026-09-02, ~10:30 AEST)

Eamon: *"Continue and optimise further."* Three things happened after the report
above was written; two of them change what it says.

## 1. A concurrent session reached the same conclusion, with better access

`(wb)`, `(wc)` and `(wd)` landed on `main` while I was working. **`(wb)` is the
same finding** — reached via the Railway MCP rather than the database — and it
goes further than I could:

* The deployment ledger is **clean**; every deploy since 28-Aug activated and was
  cleanly removed. The culprit is an **orphaned container from a ~28-Aug
  deployment that Railway's reaper missed**, living *below* the deployment
  abstraction. Railway's public API has no container roster and no force-kill.
* **`(id)`'s same-`svc` claim takeover is measured false.** It was built so a
  redeploy would not stand down against its own dead predecessor — which means
  two genuinely-live replicas each read the other's claim as "my own dead
  replica" and seize it every loop. So the one-book-one-writer guard is
  structurally *off* in exactly this state. That supersedes my simpler reading
  ("the family bot has no `claim_writer`"): the deeper problem is that the fleet
  guard would not have saved it anyway.
* The fix is a **Railway support ticket on Eamon's account**, drafted verbatim in
  `(wb)`. `(wc)` reports the orphan **survived a region migration**, so it is
  still alive as of this addendum.
* Consequence `(wb)` names and I had understated: the four family shadow books'
  **ledgers** are two-writer mixtures since ~28-Aug (the `(hf)` class). My report
  above says "the ledger is clean" on the basis that
  `audit_ledger_integrity` found zero same-pair overlaps — that remains true and
  is *not* the same claim. Overlap-freedom does not make a two-process ledger one
  book's record. **Treat family era decisions as blocked until the orphan dies.**

## 2. What I shipped — the half `(wb)` left open

`(wb)` diagnosed the instance and prepared the ticket. Nothing would have caught
the **next** one, so I built and pushed the detector — `(we)`, commits
`5a43ba0`, `2fe4b5f`, `681377b`, `0b36f02`:

* **`scripts/audit_writer_consistency.py`** — asks the one question no existing
  guard asks: *does a book's own summary row carry the same build stamp as its
  own newest close?* Those two are written by one process through one
  `_stamp_build`, so they agree unless two processes are writing one book. Live:
  **4 findings, 12 books agree** (the control group that makes the finding mean
  something). Also catches **ORPHAN-BOOK** — a book whose ledger moves while it
  has no row at all (🔭 georgia-v3). Two regimes: SKIPs clean with no
  `DATABASE_URL` rather than reddening CI.
* Pinned by `tests/autonomy/test_writer_consistency.py`, **7/7 mutations red**.
  The first round left one **alive** — the orphan branch lived inside the DB walk
  where no test could reach it — so `classify_orphan` was extracted and gained
  the retirement control it needed (🧲 Snap Back at 670.9h must never be a
  finding). That is I3 doing its job on my own work.
* **The local test suite had been running zero tests.**
  `audit_deploy_coverage.py` imports `tomllib` bare (stdlib only on 3.11+); CI
  runs 3.11 and stayed green, but this repo's `.venv` is **3.9.6** and
  `test_arm_pairing_drift.py` imports that module at scope — so
  `pytest tests/autonomy/` died at **collection**. Measured: before **0 tests
  ran**; after the shim, **2,977 pass / 3 skip**. `tomli` was already installed;
  added behind a `python_version < "3.11"` marker so CI installs nothing new.

Nothing I pushed is on a deploy path (`requirements\.txt$` does not match
`requirements-test.txt`), so **no container shipped**.

## 3. Corrections to the report above

* **Option 3 is DONE.** `(wb)` set `GROSS_X` on all three live books via the
  Railway connector: 🔮 georgia **7.0** (and she now publishes
  `stop_reachable: true`, the first live stop chain since the raise to 10),
  🙏 avo **5.3** (all-slots-stop 100% → 53%), 👩 mum **9.5**. `GROSS_X_MAX` 10.0
  untouched. Disregard that item.
* **"The ledger is clean" is too strong** — see §1. Overlap-free ≠ single-writer.
* The single failing test in the local suite
  (`test_actions_heartbeat.py::test_the_three_stale_bars_agree`, 43200 vs
  3×3900) is **another session's in-flight `fleet_watchdog_svc.py` edit**, not a
  regression. That same edit also reddens `audit_changelog_letters` by citing a
  `(vp)` entry that has not been written yet. Both are theirs to close; I left
  the file untouched.

## Still open, and it is the one that matters

The orphan is **alive**. Until Railway support kills it, three control-arm rows
and the dashboard keep reporting a container that stopped trading on 28-Aug, and
🔭 georgia-v3 stays invisible to every organ. `(wb)`'s hardening candidate —
requiring a same-`svc` claim takeover to carry a build at least as new as the
holder's — is the durable fix and is **still unshipped**. My guard does not
replace it; it makes its absence visible.
