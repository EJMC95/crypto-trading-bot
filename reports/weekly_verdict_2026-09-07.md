# Fleet weekly verdict — Monday 7 September 2026

_Written 09:13 AEST Mon 7-Sep (2026-09-06 23:13Z). Read-only pass: no trades, no levers, no deploys, no pushes._
_All times Sydney (AEST, UTC+10) unless stamped Z. Shadow books are $1,000 paper. Not financial advice._
_Go-live, retirements and every real-money change are explicit operator acts — this report recommends, it does not execute._

---

## HEADLINE

**🎫 the Ticket Taker is READY — the fleet's first-ever 6-of-6 go-live verdict — and it was also the week's biggest earner (+$109.30 realised on 48 closes).**
**🙏 avo's shadow is ONE CLOSE from joining it (~1.8 days).**
And the catch that decides what to do about it: **the READY verdict is carried by a lens the taker's own live gate forbids.**

Fleet realised P&L over the 7 days to 09:13 Mon: **+$272.37 across 741 closes**, of which **+$124.86 is real money.**

---

## 0 · A NOTE ON WHAT THIS VERDICT IS BUILT FROM

The division of labour says the machine computes and I judge. This week the machine's half was not available, so read the provenance before the numbers:

| | |
|---|---|
| **Scoreboard issue** | #248, dated **2026-08-31 — eight days old.** `fleet-weekly-assessment.yml` fires 23:30Z; that is **17 minutes after this task ran.** No fresh scoreboard existed to judge. |
| **Last two workflow runs** | **BOTH RED** (33347486090 on 31-Aug, 32674318505 on 24-Aug). |
| **Why red** | Not the scoreboard — `assess` and `ceiling` both passed. The `code-currency` job failed: `family-lighter-shadow` was **BEHIND-OWN**, 3 of 9 commits in the gap changing its own entry file, which hit 👩 mum, 🙏 avo and 🔮 georgia's shadow arms at once. |
| **Is it still true?** | **No — fixed, and verified in the live payload.** All four family shadows publish `5e30671ecf64/17`, and both live rows publish `6e419cf7b70a/18` with `build_shared 5e30671ecf64`. The arms are un-drifted. `(ww)` unstuck the host from 28-Aug code and `(yg)` read the stamps back. **Tonight's run should be judged on its own; do not treat the standing red as current.** |
| **Last week's verdict** | **`reports/weekly_verdict_2026-08-31.md` does not exist.** The series runs 08-10, 08-17, 08-24, then this one. **This is the first verdict in two weeks**, so the deltas below span 7 days but the narrative spans 14. |

So the numbers here come from the live feed — `/pnl.json`, `/bus.json`, `/trades.json` — read at 23:13Z, cross-checked against issue #248 for the week's deltas.

**One caveat I owe you on the ledger read:** `/trades.json` does not apply `LEDGER_QUARANTINE` ((wo)), so my realised figures can differ from the grader's by a close or two. I checked the known schema trap — 366 rows carry `closed_at` as `"… UTC"` rather than ISO — and **all 366 are dated 16-July, outside every window used here**, so they change nothing.

---

## a · REAL MONEY

Two live rows: **🙏 Avo Maria** (`tide-rider-lighter-live`) and **👩 mum** (`mum-live`). 🔮 georgia's live arm was retired at `(wg)` and her sub-account drained to mum; her last 8 closes (+$11.35) landed inside this window.

### The week

| | 🙏 avo LIVE | 👩 mum LIVE | live total |
|---|---|---|---|
| Book P&L 31-Aug → now | −$9.07 → **+$98.39** (+$107.46) | +$47.95 → **+$55.59** (+$7.64) | **+$115.10** |
| **Realised, 7d** | **+$90.86** on **3 closes**, 3/3 winners | **+$34.00** on **63 closes**, 69.8% win | **+$124.86** |
| Open marks, 7d | ≈ +$16.6 | ≈ **−$26.4** | −$9.8 |
| Account equity | $412.55 | $576.01 | $988.56 |
| Gross deployed | $335.06 (**0.81×**, ceiling 2.0×) | $714.77 (**1.24×**, ceiling 5.0×) | — |
| Open legs | MON, PUMP | XAU, WLFI, TRUMP | 5 |

**The week was genuinely realised, not marked up.** I expected avo's +$107 to be open marks and it is not: three closes, all winners, +$90.86 booked — consistent with her ROI ladder starting at +20% on a ~$137 clip. mum is the mirror: she out-earned her book P&L at the close (+$34.00 realised) and gave $26.4 back on open marks.

**Two accounting facts, so the row is read correctly:** avo's `pnl_abs` excludes `manual_pnl_usd = −$66.40` — the hand-placed trade `(xq)` correctly kept out of the book's evidence — and her `capital_adjust` is now $317.76 against `initial_equity` $62.80, so the *account* is up $31.99 while the *book* is up $98.39. Both are right; they answer different questions.

### Live-vs-shadow, per trade (never equity)

| pair | live | shadow | gap |
|---|---|---|---|
| 👩 mum | **+0.420%**/trade (n=90) | +0.528% (n=90) | **live −0.108pp** |
| 🙏 avo | **+2.360%**/trade (n=14) | +1.793% (n=29) | **live +0.567pp** |

Both gaps are inside the noise of their samples. mum's is the one to watch and it is small; avo's n=14 cannot support a conclusion in either direction.

### 📏 impl-shortfall: **`xp-contaminated`**, and the real finding is underneath it

Published verdict `xp-contaminated`, `gap_pp −0.455`, 52 paired closes, 31 overlaps. The verdict itself says the comparison is not clean — but note the judge reports **both pairs `idle`, no candidate running**, so `xp_running: true` and the judge's own state disagree. Worth a look; not urgent.

**The finding that matters is the order census.** Of **133 live orders**, fills resolved for only **77 (58%)**:

| resolution | orders |
|---|---|
| `trades(tx)` | 57 (42.9%) |
| `trades(tx, deferred)` | 20 (15.0%) |
| **`skipped:budget … lighter tx budget exhausted`** | **53 (39.8%)** |
| `no-match` | 2 (1.5%) |

`(xt)` shipped on 2-Sep precisely to fix this — *"live execution was measured on a non-random 42% of orders"*. **It worked, partially:** the deferred-retry recovered 20 orders and took coverage 42% → 58%. **Two in five live fills are still unmeasured**, and they are the non-random two-fifths — the ones that land when the token bucket is emptiest. The same shape is worse on the taker's live remnant (5 of 10 skipped).

Measured slip where it *is* measurable is good news: **live −0.97 bps** (filling slightly better than reference) against the shadow's modelled +3.06 bps. That is real, and it is measured on 58% of the orders.

**Rails all green:** `fleet_immune` sick `[]`, zero quarantined levers, `fleet_risk` green in both cohorts (live 5 of 20 longs, shadow 12 of 26), `clip_scale` 1.0, no book halted.

---

## b · WHICH BOOK MOVED TOWARD THE GATE (doctrine rule 4 — the forward metric)

**This is the best week the forward metric has had.**

| book | bars | fails | verdict | distance |
|---|---|---|---|---|
| 🎫 **lighter-ticket-taker-lshadow** | **6/6** | — | **READY** | **arrived** |
| 🙏 freqtrade-avo-maria-lshadow | 5/6 | `n 29 < 30` | on_track | **~1.8 days** |
| 👩 freqtrade-mum-lshadow | 5/6 | `window 12.5d < 30d` | on_track | ~17.4d (~24-Sep) |
| 🌾 perps-funding-carry-lshadow | 4/6 | `n 27 < 30`, halves −18.55/+29.94 | on_track | ~4.2d + halves must mend |
| 👩 freqtrade-mum-lighter | 4/6 | `window 9.3d`, halves +79.06/−2.96 | on_track | ~20.6d + halves |
| 🙏 freqtrade-avo-maria-lighter | 3/6 | window, `n 14`, `t 1.72` | **undecidable** (~100d) | on the docket |

**🎫 the taker crossed.** n=183 in era, mean **+1.195%/trade**, **t=2.63**, halves +$32.43/+$123.29, maxDD 5.40% against the 15% bar, window 37.1d. Era since 30-Jul (policy-stamped), so the 30-day window bar cleared around 29-Aug and the sample has been filling in since. `fails: []`. `(yd)` was the fix that let this be seen correctly — the winners' docket had been grading it on a superseded policy.

**And `(ye)`'s freeze is live and working.** `scout-tuner` publishes `ready_freeze: {book: taker, ready: true, fresh: true, dropped: []}` — nothing to drop this cycle because the tuner's current enactments are all scout-lane. The bracket the taker passed on is protected.

**🙏 avo's shadow is one close away.** 39.8 days, t=2.46, mean +1.793%, both halves positive, maxDD 1.5% — everything passes except n=29. At 0.56 closes/day that is **~1.8 days**. Expect a second READY book mid-week.

### THE CATCH — and it is the most important thing in this report

**🎫 the taker's READY verdict is earned by a lens its own live gate forbids.**

Its published `lens_evidence`:

| lens | n | mean %/trade | t | live-permitted? |
|---|---|---|---|---|
| **breakoutup** | **140** | **+1.931** | **+3.48** | **NO** |
| breakout | 10 | +1.140 | +1.23 | no |
| momentum | 2 | +0.130 | +0.75 | no |
| divergence | 48 | −0.794 | −1.36 | **yes — short only** |
| dip | 13 | −1.162 | −2.66 | no (vetoed) |

`LIVE_SIDES = {"divergence": frozenset({"short"})}`. All 8 currently held slots are `long-breakoutup`. The book's own realised veto list is `["dip", "divergence"]`.

**So if the taker were put live today under its shipped gate it would trade nothing** — the only lens real money may touch is the one its own record vetoes at t=−1.36. This is not a defect; it is `(hj)`'s fail-closed design working exactly as written (*"adding real money to a new lens must be two explicit edits, not one"*), and it is why the live arm was retired on 13-Aug.

**Therefore the go-live recommendation is not "flip it on".** It is a deliberate operator decision with three parts, in this order:

1. **A sub-account.** The taker's live slot went to 🙏 avo at `(ma)`; there is nothing for it to trade on.
2. **Two explicit edits** — add `breakoutup` to `LIVE_LENSES` and `LIVE_SIDES["breakoutup"] = {"long"}` in `lighter_ticket_taker.py`. One without the other fills nothing.
3. **Deploy marker `[deploy-live-taker]` in BOTH the PR title and the commit subject** ((xh): a marker in the commit subject alone does not survive a squash merge — measured on a real-money book), then verify by `extra.build` + `extra.build_n` readback, never by a green run.

**My recommendation: do not go live this week.** Not because the evidence is short — it isn't — but because the three-part act above changes the traded policy, and `(jf)`'s era rule means a lens/side change **resets the 30-day clock**, throwing away the very sample that earned READY. The honest sequence is: let the shadow arm keep grading `breakoutup` under the frozen bracket, and treat go-live as a decision to make once with a sub-account ready, not a switch to flip. **The verdict is real and it is yours to act on when you want it.**

---

## c · CAPITAL vs CLAIMS (I16)

The allocation organ (advisory; moves no capital) ranks the fleet by `max(0, mean − t_crit·SE)` on per-trade %. Top of the era-claim table:

| book | `claim_era` | n_era | target on $1k | scale |
|---|---|---|---|---|
| 🙏 avo shadow | 0.0082 | 29 | $1,519 | 1.52× |
| 🎫 taker | 0.0061 | 183 | $1,215 | 1.22× |
| **🙏 avo LIVE** | **0.0044** | **14** | **$1,199** | **1.20×** |
| 👩 mum shadow | 0.0028 | 90 | $1,195 | 1.20× |
| **👩 mum LIVE** | **0.0016** | **90** | **$998** | **1.00×** |
| 🌾 carry | 0.0012 | 28 | $1,029 | 1.03× |
| *(10 books)* | 0.0000 | — | $885 (probe floor) | 0.89× |

**The disagreement, in dollars.** The organ's own tilt would split the $988.56 of live equity **avo $539.5 / mum $449.1**. It actually sits **avo $412.55 / mum $576.01**. So **≈$127 — 12.8% of all live capital — sits on the lower-ranked claim.**

**I am reporting that number and recommending you do NOT act on it.** Three reasons, all measured:

1. **The ranking rests on n=14 against n=90.** avo-live's claim is built on fourteen closes with t=1.72, and the fleet's own grader calls that book **`undecidable`** and has it on the retirement docket. Sizing up a book your grader cannot decide is the I25 error in its purest form — the +2.360%/trade that drives the claim *is* the hot window.
2. **mum has a random-entry null and avo does not.** mum publishes `extra.control`: mean +0.3775% against a matched-window random-coin placebo of +0.1371%, **edge +0.240pp on n=88**. `(hm)` is explicit that a directional book is graded against random, never against zero. mum's claim is the smaller number and the better-evidenced one. avo has no such control.
3. **Neither book is capital-constrained anyway.** mum deploys 1.24× against a 5.0× ceiling; avo 0.81× against 2.0×. **Both are under-deployed** — moving $127 between them would change no trade either book takes today. The binding constraint on both live books is **signal**, not capital.

So: the disagreement is real, it is small, it is non-urgent, and the ranking that produces it is the weaker evidence. Revisit when avo-live clears n=30.

**Standing item, unchanged:** the `[0.25, 4.0]` allocation clamp is still a per-*position* slippage bound doing per-*book* duty, and **9 of 16 living books still carry no `dd_bound` at all**, so the shared ceiling governs them blind. Nothing is near the ceiling (max scale in the fleet is 1.52×), so this is latent. Owner: **OPERATOR** — moving the clamp moves money between books.

---

## d · KEEP-OR-RETIRE PRESSURE (I17)

I17 as amended requires a **measured exclusion** — the upper bound `m + t_crit·SE` at or below zero — never a thin sample. Sorted by strength of case:

### 1 · ⚖️ Counterweight (`perps-funding-spread-lshadow`) — **excluded, but pre-registered; do not act early**
n=153, mean **−1.499%**/trade, t=−1.74, halves **−$31.35 / −$2.10**, **upper bound −0.388% ≤ 0**. On the docket since **6-Aug** — the fleet's longest-standing. Holds **10 open positions** and $1,000 of paper.
**The exclusion is new** — the 1-Sep keep was made explicitly because no exclusion existed then. But the keep carries a **pre-registered read** (I21): *fresh on-class closes only, after 1-Sep, at n≥60 or on 1-Oct, whichever first.* It realised **+$6.97 over 18 closes this week**, so the fresh sample is not obviously confirming. **Honour the registration.** Re-mining the window that motivated the keep is exactly what I21 forbids. Read on 1-Oct, or earlier if fresh on-class n hits 60.

### 2 · 🪁 band-kelly — **the pre-registered read is RIPE NOW, not on 1-Oct**
n=585, mean −0.140%, t=−1.23, **maxDD 28.5% — 1.9× the 15% bar**, upper bound **+0.006%: NOT excluded**. Realised **−$27.26 on 289 closes** this week — **39% of every close the fleet took**, for the fleet's second-worst dollar result.
Its registration reads: *at n≥60 fresh closes at the $80 clip since 1-Sep, **or** on 1-Oct, whichever first.* **289 closes since 1-Sep clears n≥60 many times over — the trigger has fired.** The date was the backstop, not the trigger, and the row in `HANDOFF.md` says so in those words.
**This is the single most actionable item in the report.** Take the read this week: if the fresh upper bound ≤ 0 → retire; if the fresh mean > 0 → keep grading; anything else → back to you with both numbers. Owner: **OPERATOR** (the row is operator-owned), instrument already registered in `golive_readiness.DECIDED_UNTIL["band-kelly"]`.

### 3 · 🚀 book-bezos — excluded on paper, but **five days old**
n=33, mean −0.727%, t=−1.41, **upper bound −0.052% ≤ 0**, window 5.1d. Realised **−$24.00 on 33 closes at 30.3% win** — its entire life.
Technically I17-amended permits retirement. **I am refusing it, with the reason:** −0.052% is a hair below zero on 33 closes in five days, which is precisely the `(xm)` shape — a razor-thin exclusion that moves — and this book also lost ~3 hours to being wrongly idled by the douglas guard at birth `(wx)`. **Recommend instead: a pre-registered read at 30 days or n≥100, whichever first**, on the same terms as kelly's. Killing a book in its first week on a 0.05pp margin is the kill-bias I17 was amended to remove.

### 4 · 🏛️ pm-albanese — **undecidable by flatness, and nothing is blocking the call**
n=67, mean **+0.003%**, t=0.01, maxDD 0.9%. The horizon: **~1,873,461 days**. Realised +$0.92 on 26 closes at 30.8% win.
There is no tail, no trend and no pre-registration in the way. This is the cleanest genuine keep-or-retire ask on the board — it costs $1,000 of paper, a row and a clock to learn nothing at any horizon. **Owner: OPERATOR.** Revert path if retired: `PM_ALBANESE_RETIRED_OVERRIDE=run`, and it needs both halves (`RETIRED_ROWS` + `LEGACY_BOTS`) plus a slate test.

### 5 · Deferred and correctly so
- **🔮 georgia v1 shadow** — undecidable at ~813d, docket since 22-Aug, **deferred to your own date, 10-Sep**. Three days out; grade the `georgia-entry-cap-5-days-to-gate` claim on post-cap closes only.
- **🙏 avo LIVE** — `undecidable` (~100d) on n=14. Real money, on the docket. It cleared 3/3 winners this week; the honest position is that the sample decides nothing. Watch, do not act.
- **🏛️ pm-turnbull** — undecidable at ~105d, but mean **+0.261%**, t=1.16, both halves positive. Just past the 90d horizon and pointing the right way. **Keep.**
- **🎯 sniper (n=47, ub +0.465%) and 🔮 georgia-v3 (n=88, ub +0.062%)** — both `underpowered`, both correctly **off** the docket. The `(tz)` power gate is doing its job.

---

## e · ONE EXPANSION CANDIDATE (I19)

### **Register `taker.max_open` as a caged lever on the `lighter-taker` lane.**

**The finding.** The taker is the fleet's only READY book, and its own published census says slots are what stops it trading:

```
gate_census: tickets_in 13 → lens_vetoed 11 → bull_blocked 1 → 1 survivor
slot_census: offered 1 → slots_full 1 → opened 0
open_pos:    8 of 8, every one long-breakoutup
```

Eleven of thirteen tickets died on the lens veto — correct, those lenses lose. The **one** ticket that survived every gate died because the book was full.

**And the lever does not exist.** `MAX_OPEN = int(os.environ.get("TT_MAX_OPEN", "8"))` — a bare env constant read once at import. It is **not in `fleet_tuning.LEVERS`** (the registry carries `index.max_open` and `trend.max_open`, and no taker equivalent) and **not consumed by `apply_tuning()`**. The taker's own source says it, at line 2833: *"nobody tuning TT_MAX_OPEN could see the thing they were tuning (I23)"*. `(xs)` closed the **observability** half — `slot_census` now publishes `slots_full`. The **reach** half (I18) was never built. **The binding constraint on the fleet's best book is invisible to the growth rail.**

**The expectancy price: zero.** Registering a lever moves nothing — `env_default` stays 8, no trade changes, and `(it)` is the standing precedent (*registration is REACH, not payoff* — and that entry also recorded that walking the lever it registered unlocked nothing, which is the honest expectation here too).

**The route is the designed one.** `fleet_proposals` → the scout tuner's replay gate, where an **expand**-direction proposal must **IMPROVE both halves** through the real replay, brain veto senior, ≤3 per cycle. I am not asking for the lever to be walked; I am asking for it to become walkable, so the replay gate can answer 8→9→10 on evidence instead of the question being unaskable.

**Why it does not endanger the READY verdict.** `max_open` is capacity, and capacity is `(hc)`/`(jf)` ordinary tuning — it is **not in the era signature**, so it does not reset the 30-day clock. It is also **not in `FROZEN_WHEN_READY`** (`tp`/`sl`/`max_hold_h`/`sl_cooldown_h`), so `(ye)`'s freeze is untouched. And I24 is explicit that rate headroom comes from unused slots at the book's own hold, never a shorter one — this book has **no** unused slots, so its ceiling is `max_open` and nothing else.

**Two limits I state rather than bury:**

1. **That census is ONE loop, not a rate.** I have no 7-day occupancy series — `/bus.json`'s history carries organ keys only, and a loop-sampled counter is not an opportunity count. So this evidence justifies **reach**, not a walk. If the tuner's replay says 8 is right, that is a correct outcome.
2. **Concentration.** All 8 slots are `long-breakoutup` — one lens, one side. More slots buys **more of one bet**, which is the I22 point. **Publish the book's `n_eff` beside the slot count before any walk is enacted.** Fleet-wide exposure is currently healthy (`long_effective_n` 12.8 over 16 longs, largest symbol share 12%), so this is a precondition, not an objection.

**Suggested cage**, for the operator to accept or amend: `lo 6, hi 12`, `env_default 8`, lane `lighter-taker`, `step ×1.25`. `lo` below default keeps a tightening direction available; `hi 12` is 1.5× and stays well inside the gross ceiling the `CLIP_MAX × BRAIN_GROSS_X × MAX_OPEN` comment already reasons about.

### Refused this week, with the numbers

- **Raise 🙏 avo's live `gross_x` (2.0, ceiling 20.0).** Her claim ranks 2.75× mum's and her mean is +2.360%/trade — and the grader calls the book **`undecidable`** on **n=14**, `t=1.72`, with no random-entry null. Levering a book whose own sample cannot decide its sign is the I25 error. Revisit at n≥30 (~1.8 days on the shadow, ~100d on the live arm).
- **Move the ~$127 of live capital toward avo.** Section (c): both books are under-deployed, so it changes no trade, and the ranking rests on the weaker sample.
- **Walk `taker.max_open` directly.** One loop's census is not a rate. Register it; let the replay gate decide.

---

## CARRIED — what next week starts from

| # | Item | Owner | When |
|---|---|---|---|
| 1 | **🪁 kelly's pre-registered read — the n≥60 trigger has fired (289 fresh closes).** Take it. | **OPERATOR** | **this week** |
| 2 | 🔮 georgia v1 — pre-registered read on her cap-5 claim | session | **10-Sep** |
| 3 | 🎫 taker go-live: sub-account + the two `LIVE_LENSES`/`LIVE_SIDES` edits, aimed at `breakoutup` long. Costs the era clock — decide once. | **OPERATOR** | your call |
| 4 | 🏛️ pm-albanese — keep-or-retire, undecidable by flatness, nothing blocking | **OPERATOR** | open |
| 5 | 🚀 bezos — pre-register a 30-day / n≥100 read rather than retire on a 0.05pp margin | session | open |
| 6 | **40% of live fills still unresolved** on tx-budget exhaustion after `(xt)` took coverage 42%→58% | session | open |
| 7 | `impl-shortfall` reports `xp_running: true` while the judge reports both pairs `idle` | session | open |
| 8 | 🙏 avo shadow crosses n=30 in ~1.8d — expect a second READY book; verify the freeze arms for it | session | mid-week |
| 9 | Three images on older `build_shared` (kelly, hull/kiyosaki, sniper) — BEHIND-SHARED, informational; tonight's `code-currency` classifies | session | tonight |
| 10 | Weekly verdict for 31-Aug was never written — check the scheduled task fired | **OPERATOR** | open |

**Timing note worth fixing:** this task ran at 23:13Z and the workflow it is supposed to judge fires at 23:30Z. It will read a week-old scoreboard every time until one of the two moves.

---

## THE WEEK IN ONE LINE

The fleet's forward metric finally moved the way it is supposed to — **one book through the gate, a second one close behind, and +$272 realised across 741 closes** — and the thing standing between the READY book and real money is not evidence but two deliberate edits and a sub-account.


---
---

# ADDENDUM — Wednesday 9 September 2026, 16:05 AEST

_Written 16:05 AEST Wed 9-Sep (2026-09-09 06:05Z). Read-only: no trades, no levers, no deploys, no pushes._
_**Nothing above this line was changed.** The 7-Sep verdict is preserved verbatim; this is appended, not a rewrite._

## WHY THIS EXISTS

The weekly task fired **Wednesday**, not Monday. Its target file — `weekly_verdict_2026-09-07.md`, this file — already existed, so rather than supersede a 23KB report two days old I have appended.

It earns its place on two things the original could not have:

1. **The 7-Sep verdict was written 17 minutes BEFORE the scoreboard it is supposed to judge.** Its §0 says so plainly: it read issue **#248 (8 days stale)** and worked from the live feed instead. Issue **#288** has existed since 01:08Z on 7-Sep. **I have now read it.**
2. **Two days of outcomes have graded the original's own predictions** — including the one it staked a date on.

**The machine's half is green.** Run `34072002635` (7-Sep 01:07Z) completed with **all four jobs passing — `assess`, `code-currency`, `organ-board`, `ceiling`.** That is the **first clean weekly run since 17-Aug**; the two before it were red on `code-currency`/BEHIND-OWN. The standing red the original told you to discount is now formally gone, not just argued away.

---

## SCORECARD — the 7-Sep report's own carried list, graded

| # | Item it carried | Status now |
|---|---|---|
| 8 | *"🙏 avo shadow crosses n=30 in ~1.8d — expect a second READY book"* | ✅ **CORRECT.** She is **6/6 READY.** |
| 1 | 🪁 kelly's pre-registered read — take it | ✅ **TAKEN** at `(yo)` 7-Sep. Verdict **RETURNS TO EAMON**. Still awaiting the decision. |
| 9 | Three images BEHIND-SHARED — *"tonight's code-currency classifies"* | ✅ **Ran, and passed.** Nothing BEHIND-OWN. |
| 2 | 🔮 georgia v1 pre-registered read | ⏳ **DUE TOMORROW, 10-Sep.** Preview below — and it has a trap. |
| 10 | Weekly verdict for 31-Aug never written | ⚠️ Still absent. The 31-Aug run was red; the file was never created. History has a hole, not a mystery. |
| 3, 4, 5, 6, 7 | taker go-live · albanese · bezos · tx-budget fills · shortfall/judge disagreement | Open, unchanged. |

The original's closing timing note — *"this task ran at 23:13Z and the workflow it judges fires at 23:30Z"* — is the one thing here a person can fix cheaply, and it is why §0 of that report had to be written at all.

---

## a · REAL MONEY

Both live rows fresh (`age` 0.02h), same build `cd6d6213f540/18` — **arms aligned, no drift.** Fleet feed clean: 16 of 16 rows fresh, `n_stale: 0`.

| | 🙏 avo LIVE | 👩 mum LIVE | live total |
|---|---|---|---|
| Book P&L (7-Sep → now) | $98.39 → **$128.86** (+$30.47) | $55.59 → **$59.95** (+$4.36) | **+$34.83** |
| Realised, 7d | **+$126.15** on 7 closes, **7/7 winners** | **−$7.14** on 49 closes (63.3% win) | **+$119.01** |
| Realised, since 7-Sep verdict | +$35.29 (4 closes) | +$8.94 (12 closes) | **+$44.23** |
| Account equity | $443.02 | $580.37 | **$1,023.39** |
| Gross / leverage | $681.03 = **1.54×** (set 2.0) | $959.58 = **1.66×** (set 5.0) | — |
| Open legs | 6 — BTC, MON, SPY, XAU, XMR, NVDA | 4 — SPY, XAU, COIN, MORPHO | 10 |

**The two live books are running on opposite engines, and it is worth seeing plainly.** avo booked **+$126.15 on seven trades, every one a winner**; mum booked **−$7.14 across forty-nine** while winning 63.3% of them. That is not a contradiction — it is I15 in the live pair: mum wins often and small, avo wins rarely and large. avo's realised week is 17× mum's on one-seventh the trade count.

**Live-vs-shadow, per trade — and I am NOT reporting it as an execution finding.** `impl-shortfall` publishes `verdict: "xp-contaminated"` with `xp_running: true`: the judge's serial lane is on mum (`mum-vel-12-20`), so **her shadow twin is an EXPERIMENT arm, not a control arm.** The −0.493pp 7-day gap (live +0.091%/trade n=49 vs shadow +0.584% n=48) mixes execution with a lever under test and cannot be read as slippage. The clean number underneath it is good: **live slip 1.25 bps against the shadow's 2.84 bps modelled** — the live book fills *cheaper* than its own simulation, and the taker's live path cheaper still at 0.85 bps.

**One operational number I do want on the record:** of 84 live orders in the window, **11 were skipped on `lighter tx budget exhausted`** — 13%, plus 2 of 19 on the taker's live path. That is a book being rationed by a transaction governor rather than by its signal, and it is the same root as carried item 6 (*"40% of live fills still unresolved"*). Not a money bug — `venues/lighter_client.py:739` refuses cleanly and no order is affected — but it is a **measurement** loss on real money, which is the thing this fleet's discipline actually runs on.

---

## b · WHICH BOOK MOVED TOWARD THE GATE (the forward metric)

**🙏 avo's shadow crossed. The fleet now has TWO ready books, and that is the week's real movement.**

| | n | t | mean%/trade | maxDD | window | bars |
|---|---|---|---|---|---|---|
| 🙏 **avo shadow** | 34 | **3.42** | **+2.592%** | 1.48% | 43.7d | **6/6 READY** |
| 🎫 **taker shadow** | 198 | **2.44** | +1.068% | 5.4% | 39.4d | **6/6 READY** |

avo's shadow is not a marginal pass: hit rate 73.5%, payoff **3.77**, maxDD **1.48%** against a 15% bar, jackknife t **3.69**, top-coin share 0.20. The radar calls it `real_edge`. The honest caveat is **n=34 and a trajectory of `emerging`, not `stable`** — this is a thin, young, excellent sample, not a settled one.

**Read what her READY actually means, because it is easy to misread:** 🙏 avo is **already live**. Her shadow clearing the gate is not a go-live decision — it is her **control arm corroborating the live book**. Her LIVE arm sits at **4/6**, failing only window (22.3d) and closes (n=18), ETA **15-Oct**.

**Books one bar from the gate:**

| book | bars | the ONE thing failing | ETA |
|---|---|---|---|
| 👩 **mum LIVE** | 5/6 | window 11.5d < 30d | **27-Sep** |
| 👩 mum shadow | 5/6 | window 14.3d < 30d | 24-Sep |
| 🌾 carry | 5/6 | halves −13.19/+37.96 | unprojectable |
| 🏛️ turnbull | 5/6 | t 1.31 < 2 | 23-Nov |
| 🔮 georgia shadow | 5/6 | t 0.50 < 2 | **undecidable** |

**👩 mum's LIVE arm is 18 days from a full six-bar pass with t already at 2.06 on n=101.** Nothing needs to happen for that except time — and specifically, **nothing needs to be tuned.** She is the closest thing the fleet has to a real-money book about to be graded green on its own money.

🌾 carry deserves a line: t=**3.14**, mean +0.400%, 34 closes, and the *only* bar it fails is `halves` — one negative first half (−13.19) against a strongly positive second (+37.96). The radar has it `real_edge`/`stable` with jackknife t **4.39**, the highest in the fleet. It is failing a bar that measures its past, not its edge.

---

## c · CAPITAL vs CLAIMS (I16)

**The disagreement is on the real-money pair, and it is ~$187.**

| live book | claim (bound %/trade) | scale | actual capital | claim-proportional |
|---|---|---|---|---|
| 🙏 avo | **+1.579%** | **1.528×** | $443.02 | **$630** |
| 👩 mum | +0.161% | 0.954× | $580.37 | $393 |

🙏 avo holds the **highest measured claim in the entire fleet** — a lower bound ten times mum's — and **$187 less capital than her evidence ranks.** Capital sits in inverse proportion to measured edge; that is the I24 shape, on the only two books that hold real money.

**Three things stop that being a recommendation to move money today:**
- The sub-accounts are **separate on the venue**. Rebalancing is an operator transfer, not a lever.
- avo's claim rests on **n=18 live / n=34 era closes**. Her SE is wide precisely because she trades rarely — the same property that makes her mean look enormous.
- `fleet-allocation` publishes `advisory: true, moves_capital: false` and is doing exactly what it was built to do: **say the number, move nothing.**

**A drift worth watching, flagged not alarmed:** the claim `mum-golive-justification` — the number that moved georgia's ~$220 to mum at `(wg)` — registered mum's bound at **+0.37%/trade**. It reads **+0.161%** today. That is still inside its declared tolerance (band [0, 0.74%]) so it **HOLDS**, but the claim's own text names the failure direction: *"downward toward zero, the concentration argument itself is what dissolved."* It has travelled more than half the distance. Not actionable this week; worth a re-read if it keeps going.

**Shadow side:** funding is $3,648 target vs $4,000 held (−$352), directional $12,352 vs $12,000 (+$352). Ten of sixteen books sit at the **0.889× floor** with no era claim at all. 🙏 avo's shadow (+$524) and 👩 mum's shadow (+$82) are where the evidence points.

---

## d · KEEP-OR-RETIRE PRESSURE (I17)

**The docket holds exactly one book — and its deferral expires tomorrow.**

### 🔮 georgia v1 — the read falls due 10-Sep, and it has a trap in it

She has been on the docket **17.7 days** (since 22-Aug), verdict `undecidable`. The organ's arithmetic: binding bar is **t**, `n_req_t` = **8,094 closes** at 5.12/day — **~4.3 years**. The September slate deferred her retirement *only* because retiring her would have voided the pre-registered claim `georgia-entry-cap-5-days-to-gate`, which grades tomorrow.

**Preview, on her post-cap closes only (the basis the registration requires):**

| sample | n | mean%/trade | t | upper (m+1.28·SE) |
|---|---|---|---|---|
| PRE-cap (< 27-Aug) | 210 | +0.093% | +0.58 | +0.299% |
| **POST-cap (≥ 27-Aug)** | **79** | **−0.017%** | −0.11 | **+0.175%** |

`(vb)` predicted the cap 3→5 would take days-to-gate **344 → 187 at a HIGHER mean**. Measured: the post-cap mean is **lower** than pre-cap and **negative**. **The prediction fails on its own population.**

**⚠️ THE TRAP, and it is the reason I am flagging this a day early.** The claim's owner field is `golive-readiness::books.freqtrade-georgia-lshadow.horizon.eta_days`. On an `undecidable` book that field is **`null`** — the organ publishes `eta_days: null, eta: null` and puts the number in `raw_days` instead. **So the claim as written cannot resolve: it will grade DARK, not FAIL.** Whoever takes this tomorrow must grade it on her post-cap closes as the HANDOFF row instructs, **not** by reading the owner field — the owner field points at a value the state that matters never populates.

**Two rules point different ways here, so I will state both rather than pick:**
- The **registration** says prediction fails → retire (`lighter_family_bot.RETIRED_BOOKS` key `freqtrade-georgia`, override `GEORGIA_RETIRED_OVERRIDE`).
- **I17-as-amended** forbids retiring on a sample that has not excluded a positive mean — and her post-cap upper bound is **+0.175% > 0**.

These reconcile, and it matters that they do: I17 routes the **undecidable** class — a book that *cannot reach its own bar* — to a keep-or-retire operator call, which is a different thing from retiring a **measured loser**. Georgia is undecidable (8,094 closes), not excluded. So retiring her is within doctrine, **but it must be cited as the undecidable call, never as a measured exclusion.** Getting that citation wrong is how a future session mis-reads the precedent.

### 🪁 kelly — the read is done; **Eamon's decision is the open item**

`(yo)` took it on 7-Sep. I re-ran it with two more days of closes purely to check the branch had not changed — **not** to shop for a different answer (I25, and the HANDOFF says so explicitly). It has not:

| | `(yo)`, 7-Sep — the registered read | my check, 9-Sep |
|---|---|---|
| n (fresh, since 1-Sep) | 233 | 292 |
| mean %/trade | −0.044% | −0.073% |
| upper (m+1.28·SE) | **+0.125%** | **+0.067%** |
| t | −0.33 | −0.67 |

**Same branch on both.** Upper bound **> 0** → retirement is forbidden. Mean **< 0** → "keep grading" is not met. The registered rule's third branch is *"returns to Eamon with both numbers"*, and **a session may not close it by choosing one.** It has been waiting since 7-Sep. Her maxDD is **28.5%** — nearly 2× the go-live bar — which is why the `(wu)` drawdown rail has her effective clip down at ~$27 against an $80 base. **She is costing very little while she waits** (+$3.44 realised since 1-Sep on 292 closes), so this is not urgent; it is just unanswered.

### ⚖️ Counterweight — **not due, and do not pre-empt it**

Registered read: n≥60 fresh **on-class** closes after 1-Sep, or 1-Oct. She has **21** closes since 1-Sep. Not due.

And the direction is the reason the registration exists: her pooled record is ugly (n=158, mean −1.328%, t=−1.57, both halves negative, `unreachable`) while her **fresh 21 closes read +2.70%/trade, +$8.54 realised.** Far too thin to conclude anything — but retiring her today on the pooled number, with a fresh sample running the other way, is exactly the I25 error the pre-registration was built to prevent. **Leave it until 1-Oct or n=60.**

### The measured losers nobody is deferring

| book | n | mean%/trade | t | horizon |
|---|---|---|---|---|
| 🚀 bezos | 38 | −0.649% | −1.32 | unreachable |
| ⚖️ counterweight | 158 | −1.328% | −1.57 | unreachable |
| 🎯 sniper | 49 | −0.832% | −0.97 | underpowered |
| 🏛️ albanese | 74 | −0.241% | −0.60 | underpowered |

Two `underpowered` books are **not** retirement candidates — that verdict exists precisely to keep a thin sample off this docket. 🚀 bezos is 7.4 days old and both halves negative; carried item 5's advice (pre-register a 30-day/n≥100 read rather than retire on a thin margin) is still the right call.

---

## e · ONE EXPANSION CANDIDATE (I19)

### The candidate: **admit `long-breakoutup` to 🎫 the taker's live gate.**

This is the same finding the 7-Sep verdict flagged as a catch. Two days on, I can put numbers on both halves of it. Splitting the taker's in-era closes by lens:

| lens | n | realised | mean %/trade | t |
|---|---|---|---|---|
| **`long-breakoutup`** | **154** | **+$164.11** | **+1.652%** | **+3.15** |
| `short-divergence` | 47 | −$16.98 | −0.747% | −1.27 |

_(My era window approximates the grader's — my split totals 201 closes against the gate's 198, a ~3-close boundary difference. The direction is not in doubt; the exact figures are mine, not the organ's.)_

**The taker is READY because of `breakoutup`. Its live gate permits only `divergence` short — the losing half.** `lighter_ticket_taker.py:603` reads `LIVE_SIDES = {"divergence": frozenset({"short"})}`, and line 3495 pins `allowed_lenses("lighter_live") == {"divergence"}` in the selftest. **Turning this book on today under its existing rule would put real money on a lens measuring −0.747%/trade while the lens that earned the READY verdict stayed on paper.**

**Price it honestly (I19):**
- **For:** +1.652%/trade on n=154, t=3.15, from a book at 6/6 with maxDD 5.4% and radar `real_edge`/`stable`. The gate that governs real money now says READY, so `golive_blocker` would pass it — the evidence half is genuinely done.
- **Against:** it costs the **era clock**. Lens/side membership *is* in the `(jf)` era signature, so this change resets the 30-day window and the book re-grades from zero. It is deliberately **three touches**, not one — `allowed_lenses`, `LIVE_SIDES`, and the line-3495 assertion — which is the fail-closed design working, not friction to route around. And the live arm was retired 13-Aug, so it needs a sub-account.
- **Not a lever, and not mine to set.** No proposal channel reaches this; it is a go-live act, which is Eamon's alone.

**My recommendation: decide it once, deliberately, or leave it.** The worst outcome is doing it by halves — turning the book on under the current gate, which trades the losing lens with the winning lens's certificate.

### And the refusal, with numbers

The tempting alternative is **🙏 avo**: she is at cap (`cap_slots 6`, 6 held, **38 `slots_full` refusals** in the sampled loop), she holds the fleet's best claim, and her `gross_x` is **2.0** against a ceiling Eamon set at **20**.

**Refused, on two measured grounds.** Her slot count is under a **live pre-registration** — `(ye)` took 5→6 on 6-Sep and registered the read at ≥10 live closes opened with ≥5 held, or 6-Oct. Moving it again now **voids that registration** (I21). And raising `gross_x` instead buys nothing the gate can see: **leverage multiplies mean and sd alike, so `t` is invariant** (I22, six prior rejections). It would deploy idle capital on her best-evidenced book — a real thing — but it moves her **zero days closer to a decision**, and her live arm's binding bars are window and closes, both of which only time fixes.

---

## WHAT NEXT WEEK STARTS FROM

Carried forward from the 7-Sep list, re-ranked by what is actually blocking:

| # | Item | Owner | When |
|---|---|---|---|
| 1 | 🔮 **georgia v1** — take the read on **post-cap closes only**; the owner field is `null` and will grade DARK. Prediction fails on n=79. Cite it as the **undecidable** call, not a measured exclusion. | session | **10-Sep — tomorrow** |
| 2 | 🪁 **kelly** — the read is done and returns to you. Both numbers: mean −0.044%, upper +0.125% `(yo)`. Neither branch fires. | **EAMON** | open since 7-Sep |
| 3 | 🎫 **taker go-live** — evidence half complete; costs the era clock; three deliberate edits + a sub-account | **EAMON** | your call |
| 4 | 👩 **mum LIVE hits 30d on 27-Sep** at t=2.06 — nothing to do but let it run. Do not tune her. | — | 27-Sep |
| 5 | Live **tx-budget skips: 11 of 84 orders.** Measurement loss on real money. | session | open |
| 6 | Fix the **23:13Z vs 23:30Z** scheduling collision — this task cannot see its own scoreboard | **EAMON** | cheap |
| 7 | ⚖️ counterweight — **not due**; fresh 21 closes read +2.70%. Leave until 1-Oct/n=60. | session | 1-Oct |
| 8 | 🏛️ albanese, 🚀 bezos — pre-register reads rather than retire thin | session | open |

---

## THE TWO DAYS IN ONE LINE

**The fleet's second book cleared the gate exactly when the last report said it would, both live rows are fresh and aligned on the same build, and every genuinely open item is now a decision rather than a measurement** — georgia's tomorrow, kelly's yours, and the taker's the one where the evidence is finished and only the act remains.

_Read-only pass. Shadow books are $1,000 paper; not financial advice. Go-live, retirements and every real-money change are explicit operator acts — the levers and file paths above are named so they can be executed by you, and were not executed here._

---

## POSTSCRIPT — Wednesday 9 September, 23:20 AEST

**Item 1 of the addendum's list is done, a day early, on Eamon's instruction** (*"take georgia's read now"* → *"complete fixes"*). The (vb) prediction was graded on the only honest basis — the 75 closes whose own policy stamp says cap 5, keyed on the open — and **failed**: mean −0.0025%/trade against +0.108% predicted, t −0.02, days-to-gate unreachable. The throughput limb delivered (5.72 closes/day vs 5.47); the mean limb did not; the cap moved 4 of 75 trades. **🔮 georgia v1 is retired on I17's undecidable call** (8,094 closes ≈ 4.3 years to t=2) — explicitly *not* as a measured loser (post-cap upper bound +0.196% > 0). Zero positions froze; v3 keeps trading; `GEORGIA_RETIRED_OVERRIDE=run` reverts. The trap the addendum flagged was real and got a class fix: the claim's owner field is `null` on an undecidable book, so the ledger gained a terminal GRADED state and her row stays with its read recorded. Shipped as `(zo)` on main (`e81b74e`), deployed to all seven services with `[deploy-live]` (the arms were already split; they are aligned again on `build_shared 9e6985630f4e`), verified by stamp readback. Full working: CHANGELOG `(zo)`, instrument `scripts/study_georgia_cap5_read_2026-09-09.py`.

_This postscript was not re-emailed; the original send stands._
