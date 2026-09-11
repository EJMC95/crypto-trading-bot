# Evidence Review — 2026-08-27

_Reviewed 2026-08-27 08:15 AEST (Sydney) · 2026-08-26T22:15:58+00:00 UTC._

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 527.1h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:21 | active | joined decision+context dataset at 651 closes (49% win), bucket 21 |
| live-shadow-gap | resolved | freqtrade-avo-maria-lighter: +0.546pp (live +0.822% n=4 vs shadow +0.276% n=10); freqtrade-georgia-lighter: -0.295pp (live -0.143% n=49 vs shadow +0.152% n=102); freqtrade-mum-lighter: insufficient paired closes (live n=0, shadow n=6) |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=131 (≥10): net $-8.13, WR 34%, t=-0.48 — noise
- 🎫 shadow lens 'long-breakoutup' at n=86 (≥10): net $+58.99, WR 52%, t=2.33 — significant
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE freqtrade-avo-maria-lighter: n=4, net $+0.51 — by lens [('long-dip-in-uptrend', 4, 0.51)]
- 💰 LIVE freqtrade-georgia-lighter: n=49, net $-26.66 — by lens [('long-trend-breakout', 32, -0.79), ('long-range-on', 16, -25.03), ('long', 1, -0.84)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): lighter-ticket-taker-lshadow → 2026-10-16 (t) FLOOR:halves · undecidable@trend: pm-albanese-lshadow, pm-turnbull-lshadow; unreachable@trend: band-garrett-lshadow, book-douglas-lshadow, nav-cook-lshadow, perps-funding-carry-lshadow, perps-funding-lighter-lshadow, perps-funding-spread-lshadow
- 🚦 fleet-risk light green — longs 12/20, shorts 5/12 (gross 17); 7d DD -0.42%, clip_scale 1.0
- 📏 freqtrade-avo-maria-lighter live-vs-shadow per-trade gap +0.546pp (live +0.822% n=4, shadow +0.276% n=10) — no divergence
- 📏 freqtrade-georgia-lighter live-vs-shadow per-trade gap -0.295pp (live -0.143% n=49, shadow +0.152% n=102) — no divergence
- 📏 freqtrade-mum-lighter live-vs-shadow: insufficient paired closes (live n=0, shadow n=6) — no verdict
- 🧬 freqtrade-avo-maria-lighter arms differ on FILE SET, not necessarily code: live 689f8958926d (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-georgia-lighter arms differ on FILE SET, not necessarily code: live 689f8958926d (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-mum-lighter arms differ on FILE SET, not necessarily code: live 9c832edeb302 (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-georgia-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-mum-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter stamp differs from the repo tree: container 689f8958926d vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 freqtrade-georgia-lighter stamp differs from the repo tree: container 689f8958926d vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 freqtrade-mum-lighter stamp differs from the repo tree: container 9c832edeb302 vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]

## Summary

21 alert keys reviewed: 1 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 22 new-evidence items scanned.

_An earlier report for this day was preserved at `evidence_review_2026-08-27.superseded-0741.md`._

---

# HUMAN LAYER — 27-Aug-2026 (written after the script run)

*Times Sydney (AEST, UTC+10). Report written 27-Aug ~08:1x. Not committed.*

## ⚠️ ACTION 1 — 🔮 GEORGIA (REAL MONEY): HER LOSS IS THE HALT, NOT THE STRATEGY. THE 10% DAILY-LOSS HALT NOW TRIPS ON A SMALLER MOVE THAN THE MEDIAN DAY'S ORDINARY DIP

Eamon asked this directly this morning ("Georgia's trading has almost gone
backwards"). It has, and the cause is mechanical and fixable — **her entry and
exit logic are not the problem.**

**THE DECOMPOSITION** (live `freqtrade-georgia-lighter`, n=53 closes, 22→26-Aug):

| exit family | n | net $ | mean %/trade |
|---|---|---|---|
| `*_daily_loss` (the HALT) | 6 | **−34.83** | −2.13% |
| everything else | 47 | **+8.17** | +0.24% |
| **total** | 53 | **−26.66** | |

**Strip the halt closes and the book is +$8.17.** Her best sleeve is healthy:
`long-trend-breakout_roi` n=4 **+$21.01 (+2.63%/trade)**; `range_top` exits run
50–70% win. Her SHADOW twin — same strategy, 1x, no leverage — is **net
positive (+$11.66, n=209 over 45 days) and has ZERO `daily_loss` closes ever.**

**THE EVENT.** 25-Aug 22:08 Sydney: **five positions closed in the same second**
(ETH, XRP, LINK, AVAX, NEAR), all `long-range-on_daily_loss`, **−$30.96**. Each
was down only 1.03–3.29% — none near her −5% stop. That single halt is *more
than her entire lifetime loss*. Day rollup: 22-Aug −$3.50, 23-Aug +$1.90,
24-Aug +$3.18, **25-Aug −$22.28**, 26-Aug −$5.96. Three of five days are fine.

**THE MECHANISM, from her own published payload** (`extra.leverage`):
`basket_move_at_full_gross_pct = 0.0143`. The halt is `DAILY_LOSS / GROSS_X`
= 0.10 / 7.0 → **a 1.43% adverse basket move halts the book.** Her `n_eff` is
**1.0** — ETH/XRP/LINK/AVAX/NEAR is *one bet wearing five names*, so they all
move together.

**IS 1.43% RARE? NO — IT IS SMALLER THAN A MEDIAN DAY.** Measured on 92 days of
Lighter's own daily candles across her 10 crypto majors, equal-weight
(n_eff=1.0 makes equal-weight the right basket), adverse move = open→low:

```
   median daily open->low   -1.80%      <- BIGGER than her 1.43% halt bar
   p20  -3.30%   p10  -4.32%   p05  -6.26%   p02  -8.24%

   basket move that halts her:      -1.43%  ->  54/92 days = 58.7%
   ...mum at 9.5x:                  -1.05%  ->  66/92 days = 71.7%
   ...avo at 5.3x:                  -1.89%  ->  46/92 days = 50.0%
   ...georgia at her OWN vol target -3.33%  ->  17/92 days = 18.5%
```

**CALIBRATION** — the model reproduces reality: it predicts a halt on ~50-59%
of days at her as-run gross; she halted on **2 of 5** live days. Consistent.

**THE BIND, stated as arithmetic rather than as an opinion about risk:**

| target | keep `GROSS_X`=7.0 → set `DAILY_LOSS` | keep `DAILY_LOSS`=0.10 → set `GROSS_X` |
|---|---|---|
| halt only on worst **5%** of days | 0.44 (44% of equity) | 1.60x |
| halt only on worst **10%** | 0.30 (30%) | 2.31x |
| halt only on worst **20%** | **0.23 (23%)** | **3.03x** |

**7x leverage and a 10% daily-loss halt are mutually inconsistent on an
n_eff=1.0 crypto basket.** One of the two must move. This is not a re-argument
of Eamon's 26-Aug "leverage optioned" call — leverage is his to set, and (tq)'s
own ceiling arithmetic (7.593x) is sound. What (tq) did not carry is that
raising `GROSS_X` 5.0→7.0 **and** the halt $20→$27 in the same change left the
trigger threshold essentially where it was (1.38% → 1.43%), so the halt stayed
inside the noise band.

**RECOMMENDED (preserves the leverage Eamon asked for). BOTH VARS OR IT IS A
NO-OP** — the halt has a percent arm and an absolute arm, and the absolute one
would immediately re-bind:

```
railway variables --service trail-blazer-live \
  --set GEORGIA_DAILY_LOSS=0.23 \
  --set LIGHTER_MAX_DAILY_LOSS=61
```

*Why both:* equity $263.86. Today `0.10 × 263.86 = $26.39` vs `abs $27` — the
percent arm binds by 61c. Move only the percent and `abs $27` binds at **10.2%**
and nothing changes. `0.23 × 263.86 = $60.7` → **$61**.
*What it costs:* a genuinely bad day can now take 23% instead of 10%. That is
the honest price of 7x, and her row already publishes `all_slots_stop_pct: 0.35`
— the 23% halt sits *inside* the loss her own stop-loss geometry already allows.
*Expectancy price:* none in the entry path — this changes no entry, no signal,
no clip. It stops the book crystallizing 1–3% paper dips as realized losses.

**SECOND, FREE, AND THE BETTER LONG-RUN FIX: raise `n_eff`.** Her policy already
reads `scan_order: diversified`, but on 25-Aug she held five crypto majors =
~one bet. 🙏 Avo's `diversified_order` took its basket **N_eff 1.18 → 2.87 for
free** ((sr)) — the scan *order* changes, the entry path does not, so it costs
zero expectancy. Every point of `n_eff` earns leverage honestly: her own
`vol_target_gross_x` returns **3.0x at n_eff=1** but **5.27x at n_eff=3**. Worth
a session to check whether diversified ordering is actually reaching her
multi-position case, since the 25-Aug basket suggests it is not.

**NOT APPLIED BY THIS JOB** — real-money lever, and this task's safety rules
forbid deploys/Railway changes. Eamon's call.

## ⚠️ ACTION 2 — 👩 MUM v2 HAS NOT OPENED BECAUSE HER CELL IS EMPTY, NOT BECAUSE SHE IS BROKEN — AND HER HALT IS SET WORSE THAN GEORGIA'S

Eamon's second question. **She is working correctly.** Her live census, this
loop:

```
scan: {universe: 23, rsi_bar: 30.0, rsi_min: 31.3, rsi_med: 42.2,
       near_bar: 6, verdicts: {no_signal: 23}}
```

Her entry is `RSI(14) < 30` on 1h. **The lowest RSI across all 23 of her coins
is 31.3.** Not one coin is below the bar — she missed by **1.3 RSI points**, and
`near_bar: 6` says six coins are close. Nothing is stuck: no vetoes, no cap
skips, no budget block, status `online`, publishing every loop.

Two supporting facts: (a) (tr) widened her bar 25→30 only *yesterday*, so before
that she was 6.3 points away, and the study behind it measured ~3–4x her prior
supply (~4.03 episodes/day) — so the first trade should arrive within days, not
weeks; (b) her SHADOW twin has 8 closes for **+$16.54**, so the strategy does
fire when the print comes. She has been live ~2 days.

**THE PROSPECTIVE WARNING — worth acting on BEFORE her first trade.** mum runs
`GROSS_X = 9.5` (Eamon's on-record setting) with `stoploss −4%` and `n_eff 1.0`.
Her published `basket_move_at_full_gross_pct` is **0.0105** — a **1.05%** adverse
basket move halts her, which the tape says happens on **71.7% of days**. Her own
`vol_target_at_neff1` is **3.75x**; she is at 9.5x, and `all_slots_stop_pct` is
**38%**. Georgia's 25-Aug event is what mum's first busy day looks like, only
sooner. If Eamon takes the georgia halt fix, mum wants the same treatment:

```
railway variables --service mum-live \
  --set MUM_DAILY_LOSS=0.31 --set LIGHTER_MAX_DAILY_LOSS=93
```

*(0.0330 basket × 9.5 = 0.31; 0.31 × $300 equity = $93 — halt on the worst ~20%
of days rather than 72%.)* **Not applied — real money, Eamon's call.**

## ✅ WHAT THIS RUN FIXED — the live-shadow alert was unverifiable

The script's own `payload.errors` reported
`live_shadow_gap() missing 1 required positional argument: 'live'`. The 26-Aug
pass gave the helper a required `live` argument and updated the *evidence*
section to iterate all three live books — and left `verify_alerts`'s own call on
the one-argument form. So the single alert whose job is catching a real-money
book drifting from its control arm **published "verification failed" instead of
a verdict.**

Every 26-Aug test stayed green because they all drive the **helper**; nothing
drove the **caller**. Fixed: the verifier now iterates `DECLARED_LIVE`, reports
each live row against its own twin, and is **fail-closed** (nothing measurable
⇒ stays `active`, never a vacuous "resolved"). Pinned by a selftest that drives
`verify_alerts` itself; the recording cursor needed separate live/shadow
row-sets first, because feeding one set to both arms pins the gap at 0.00pp and
makes the DIVERGING branch unreachable. **4 mutations verified RED.**
Committed locally as `(uj)` `4ab3f4a` — **NOT pushed** (this job may not push;
the push is the deploy for this script). Today's re-run: `errors: []`.

Letter note: three concurrent sessions took (ug)/(uh)/(ui) on main mid-write;
`audit_changelog_letters` caught the race pre-push and this entry moved to (uj).

## 🏆 THE FLEET'S FIRST CONFIRMED PRE-REGISTRATION

`winners_docket`: **🎫 taker `exit:hold` — CONFIRMED.** Registered 18-Aug at
n=53/t=2.65; graded on **fresh closes only**: n=13, **t=+3.18**, mean
**+4.770%/trade**, **+$43.53**, p=0.0040. The discipline earned its keep here —
the re-mined pooled window reads t=3.76/p=0.0002 and *would have been crowned
PROVEN on the window that generated the hypothesis*, which is exactly what I21
forbids. The other pre-registration (🙏 avo book-level) is **UNDECIDED**, fresh
n=5 < the MIN_N 10 floor. **PROVEN WINNING: none** — no bucket survives BH today.

## FLEET STATE (mechanical)

- **Go-live: READY none.** Nearest: 🎫 taker (n=121, t=1.20, on_track 16-Oct),
  🙏 avo shadow (n=17, 29.5d, on_track 11-Nov). Georgia's live era reset 26-Aug
  so only 2 of 49 closes count — her live gate reading is not yet meaningful.
- **Risk light GREEN** — longs 12/20, shorts 5/12, gross 17. 7d DD −0.56%,
  `clip_scale` 1.0. No governor trigger.
- **Code currency: OK.** Zero BEHIND-OWN. The three live rows are DEFERRED
  behind their marker gates (avo/georgia 28 commits, mum 20) — by design, not a
  finding.
- **Ledger integrity: the known historical failure only** — 🌾 carry's 7
  same-pair overlaps, most recent 686.6h ago. Nothing to stop; the sample stays
  pooled and unusable. Not new.
- **Live-vs-shadow:** avo +0.546pp, georgia −0.295pp, mum no verdict (live n=0).
  No divergence. *(First run where this verdict is earned rather than absent.)*
- **Alerts:** 21 keys — 1 active, 1 resolved, 19 stale (all 19 are frozen
  🧲 Snap Back dislocation history; it retired 4-Aug).

## OPTIONS TO OPTIMISE — ranked

1. **🔮 Georgia's halt → `DAILY_LOSS` 0.10→0.23 + `LIGHTER_MAX_DAILY_LOSS`
   27→61.** Evidence: −$34.83 of her −$26.66 is halt closes; halt bar 1.43% vs a
   median daily dip of 1.80%; 58.7% of 92 days trip it. **Expectancy cost: none**
   — no entry, signal or clip changes. Biggest single real-money item on the
   board. *Real money → Eamon's call.*
2. **👩 mum's halt, same fix, before her first trade** (`0.31` / `$93`). Her bar
   is 1.05% = 71.7% of days — worse than georgia's. Prospective, free, and
   cheapest while she is flat. *Real money → Eamon's call.*
3. **Raise georgia's `n_eff` via diversified ordering.** Evidence: avo went
   1.18→2.87 for free ((sr)); georgia's own vol target goes 3.0x→5.27x at
   n_eff=3, which is how 7x becomes *earned*. **Expectancy cost: none** (scan
   order only). Needs a session to verify diversification reaches her
   multi-position path — the 25-Aug five-major basket suggests it does not.
4. **🎫 taker `long-breakoutup` is ~3 days from the winners' bar** — n=86,
   t=1.92, needs n≈94 at its own rate. Nothing to do but let it run; worth
   watching for the fleet's second confirmed winner.
5. **Nothing on capacity today.** Checked: fleet gross 17/20 longs with the L2
   veto not binding; georgia `cap_slots` 5 of 5 and avo 5 of 5 — neither is
   cap-starved; mum 4 of 4 but flat. No book is turning away graded signal for
   want of a slot.

**Refused with evidence:** lowering georgia's `GROSS_X` to her 3.0x vol target
would also fix the halt frequency (18.5% of days) — **not recommended as the
primary**, because Eamon explicitly asked for leverage on 26-Aug and the halt
can be made consistent *at* 7x. The leverage is not the defect; the halt
threshold sitting inside normal noise is.
