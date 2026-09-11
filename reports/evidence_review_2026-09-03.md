# Evidence Review — 2026-09-03

_Reviewed 2026-09-03 09:35 AEST (Sydney) · 2026-09-02T23:35:18+00:00 UTC._

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 696.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:23 | active | joined decision+context dataset at 704 closes (50% win), bucket 23 |
| veto:XLM | active | stop rate 3/5 >= 50% (30d) |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=131 (≥10): net $-8.13, WR 34%, t=-0.48 — noise
- 🎫 shadow lens 'long-breakoutup' at n=121 (≥10): net $+72.78, WR 51%, t=1.89 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE freqtrade-avo-maria-lighter: n=11, net $-5.15 — by lens [('long-dip-in-uptrend', 11, -5.15)]
- 💰 LIVE freqtrade-mum-lighter: n=69, net $+21.34 — by lens [('long-oversold-rebound', 67, 8.38), ('long', 2, 12.96)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): lighter-ticket-taker-lshadow → 2026-11-23 (t) FLOOR:halves; pm-turnbull-lshadow → 2026-10-15 (t) · undecidable@trend: freqtrade-georgia-lshadow; unreachable@trend: band-kelly-lshadow, perps-funding-spread-lshadow
- 🚦 fleet-risk light green — longs 9/20, shorts 0/12 (gross 9); 7d DD -1.41%, clip_scale 1.0
- 📏 freqtrade-avo-maria-lighter live-vs-shadow per-trade gap -0.510pp (live +0.320% n=7, shadow +0.830% n=9) — no divergence
- 📏 freqtrade-mum-lighter live-vs-shadow per-trade gap -0.115pp (live +0.184% n=69, shadow +0.299% n=66) — no divergence
- 🧬 freqtrade-avo-maria-lighter arms differ on FILE SET, not necessarily code: live 078f894f89d1 (n=17) vs shadow 72745e632189 (n=16) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-mum-lighter arms differ on FILE SET, not necessarily code: live 078f894f89d1 (n=17) vs shadow 72745e632189 (n=16) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-avo-maria-lshadow matches the repo tree: 72745e632189 (n=16)
- 🧬 freqtrade-mum-lshadow matches the repo tree: 72745e632189 (n=16)
- 🧬 freqtrade-avo-maria-lighter matches the repo tree: 078f894f89d1 (n=17)
- 🧬 freqtrade-mum-lighter matches the repo tree: 078f894f89d1 (n=17)

## Summary

21 alert keys reviewed: 2 active, 0 resolved, 19 stale. No divergence and no drawdown-governor trigger. 18 new-evidence items scanned.

---

# Human layer — daily review, Thu 3 Sep 2026 (Sydney)

*Times Sydney (AEST, UTC+10). Note the UTC day was still 2-Sep during this run —
that matters for mum's halt below.*

## ⚠️ ACTION — nothing needs a decision from you today

Both items that look alarming are **working as designed**, and I verified them
rather than assuming:

1. **👩 mum is `halted` and flat.** Her daily-loss halt fired 2-Sep 17:19Z
   (3-Sep 03:19 Sydney) on `today_pnl −58.86` against her staged **$57 absolute
   cap** — the `(wh)/(wj)` rail doing exactly its job. It flattened 8 positions
   cleanly (`flatten_incomplete: false`, `open: 0`, `held: {}`) and **releases
   at 00:00Z = 10:00 Sydney**, ~20 min after this run. Equity **$523.95**, book
   still net **+$21.33** over 69 closes. No action.
2. **The `[deploy-live]` (xo) fix LANDED — verified by stamp, not by the green
   run.** Both real-money rows moved `078f894f89d1` → **`f0810dc6a479`/17**.
   That is the confirmation (xo) itself could not have: the 84%-of-book stuck
   1000PEPE leg is gone, and `(xq)` accounts for it — it was your manual trade,
   dropped at your request, which is why no close was booked.

## What I checked on yesterday's work (the mandate's first job)

| Entry | Claim | Verdict today |
|---|---|---|
| **(xo)** mum's halt couldn't flatten a 1000-market | fix at `position_of` | **LANDED + CLEAR** — stamp verified, `flatten_incomplete: false` |
| **(vy)** 🪁 kelly clip $250 → $80 | cuts the burn 3× | **WORKING — but read it honestly (below)** |
| **(wt)** September slate, 5 retirements | grader verdicts | Holding; all five gone from the graded set |
| **(xd)** judge's cross-image drift guard | lane could not promote | Judge lane on mum, unblocked |

**🪁 kelly, decomposed per I25 — do not read the sign flip as the fix working.**
Pre-cut n=356 −$139.04 (−0.206%/trade, −$11.08/day); post-cut n=46 **+$11.52
(+0.317%/trade, +$5.82/day)**. Tempting, and **the per-trade improvement is not
the clip's doing** — per-trade % is invariant to clip size ((hl), measured), so
a clip cut *cannot* move a mean from −0.206% to +0.317%. What the cut actually
bought is the identity: **same % on a 3.1× smaller base = 3.1× smaller dollar
burn**. The rest is cold-window reversion (30-Aug −$83.28, 31-Aug −$36.23 → the
+0.940pp rise I25 measures after a cold window). His **1-Oct pre-registered
read stands unchanged** — that is the decision point, not this week's tape.

## 🏆 The real result: the fleet's first CONFIRMED pre-registered winner

**🎫 taker `exit:hold` — CONFIRMED.** Fresh sample only (never the window that
generated it): **n=23, t=+2.67, +2.707%/trade, +$43.51, across 10 close-days**
— the independence caveat that killed the 21-Aug reading is satisfied this
time. Registered 18-Aug at n=53/t=2.65; the pooled window would have read
t=3.63, and I21's machinery correctly refuses to crown on that.

The two others both read **NOT_CONFIRMED**, and that is the guard working:
* 🙏 avo `book:*` — fresh n=11, t=0.70 (registration was t=2.31)
* 👩 mum `book:*` and `tag:long-oversold-rebound` — fresh n=16, **t=−3.96**

**On mum's −3.96:** she was pre-registered *yesterday* on a hot window
(t=2.71), and 8 of those 16 fresh closes are the single daily-loss flatten —
one decision, not 8 draws. This is I25's exact shape, and the pre-registration
caught it instead of crowning it. **No action; the mechanism is the win here.**

## Fleet state

- Go-live: **READY none.** 🙏 avo shadow closest (23 of 30 closes, t=2.05, both
  halves +, on_track **17-Sep**). mum shadow on_track 26-Sep.
- Fleet risk **green**, clip_scale 1.0; live cohort **5/20** longs, shadow
  14/26 — the long budget is *not* binding anywhere, so no reach ceiling today.
- `audit_code_currency`, `audit_ledger_integrity`, doctrine/lever/recurrence/
  roster/spend guards: **all clean.** The one integrity failure
  (`perps-funding-carry-lshadow`, 7 overlaps) is **historical** — most recent
  856h ago, permanent by nature, not a live condition.
- Live-vs-shadow gaps small and benign: avo −0.510pp (n=7/9), mum −0.115pp.

## What I implemented this run

**🎫 `extra.gate_census` — shipped, pushed, `(xs)`.** The taker's row published
`{offered: 1, slots_full: 0}` — *"slots aren't binding"*, true and useless —
while the scout offered **24 tickets** and 23 died in gates nothing counted, on
the book that holds the CONFIRMED winner above at **4 of 8 slots**. Now one
counter per gate, incremented at its own gate. Publish-only, **zero expectancy
cost**, 11/11 mutations killed.

Two things worth your knowing: writing the AST guard **found three gates I had
missed by reading** — the spread gate, the fleet long-budget veto and the
notional cap — and mutation round 2 **found a defect in my own test** (blind to
`tickets_in`). Both are in the entry.

## OPTIONS TO OPTIMISE

Ranked. Honest headline: **no lever is worth pulling today**, and the reasons
are measured rather than cautious.

1. **Widen `TICKET_TOP_N` 12 → 18 for the taker's breakout lens** — *the one
   live candidate, and I am deliberately NOT taking it yet.* Evidence FOR:
   `breakout` returns **exactly 12 = its cap** (the `(hd)` cap-binding
   signature), the taker sits at 4 of 8 slots, and `breakoutup` is its only
   working lens (n=113, t=1.99, +1.137%/trade, ~15d from the docket's t-bar).
   Cost: none to expectancy — the taker's gates still judge every ticket
   ((hd)'s own argument). **Why I held:** until `(xs)` publishes a full loop of
   `gate_census` I cannot yet say the cap is what binds rather than the brain
   veto (12 of 24 tickets) or the crypto/quality screens. That measurement
   arrives on the next freqtrade-bots deploy. **Read `gate_census` tomorrow and
   this becomes a one-line decision** — which is exactly what it was built for.
2. **🎫 `exit:hold` is CONFIRMED — but a discovery is not a promotion (I21).**
   Before anything acts on it, it owes the `(hm)` random-entry null. Worth
   queueing as a study; it is the strongest directional signal the fleet has.
3. **Nothing else is on offer, and here is what I checked.** Capacity: no book
   is slot-limited (taker 4/8, avo 5/5 but signal-limited, mum flat-halted).
   Reach: long budget 5/20 live and 14/26 shadow — slack everywhere, so the L2
   veto is not a ceiling today. Correctness: every grader/lever/deploy guard
   clean. Allocation: only **2 books hold a positive era claim** (avo shadow
   0.0032 on n=23, turnbull 0.0005 on n=35) — too thin to re-weight on.
4. **Refused with evidence:** 🪁 kelly's post-cut sign flip as grounds to
   restore his clip — it is cold-window reversion, and the arithmetic says a
   clip cannot move a per-trade mean at all.

## Carried

`session_state --check`: **12 carried items, none stale, none orphaned.** The
two dated reads that matter: **🔮 georgia 10-Sep** (pre-registered, do not
decide before), **🪁 kelly + ⚖️ Counterweight 1-Oct**.
