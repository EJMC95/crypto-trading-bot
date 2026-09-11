# Evidence Review — 2026-08-02

_Reviewed 2026-08-02T01:00:02+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live fd4663d27fb5 vs shadow 5e27c751f5b2 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container 705425a83422 vs repo 30bf230bd5fb (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container 705425a83422 vs repo 30bf230bd5fb (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container fd4663d27fb5 vs repo 5e27c751f5b2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 9570 events across 34 books (threshold 50) |
| disloc:0G | active | census 454 ev / 277bps (alert 454), last event 2.0h ago, 36 entries |
| disloc:APEX | active | census 4037 ev / 313bps (alert 4037), last event 6.2h ago, 455 entries |
| disloc:BIO | active | census 97 ev / 272bps (alert 97), last event 6.3h ago, 7 entries |
| disloc:CHIP | active | census 202 ev / 160bps (alert 202), last event 3.4h ago, 13 entries |
| disloc:EIGEN | active | census 193 ev / 161bps (alert 193), last event 4.0h ago, 5 entries |
| disloc:GMX | active | census 167 ev / 151bps (alert 167), last event 6.5h ago, 17 entries |
| disloc:KAITO | active | census 1181 ev / 350bps (alert 1176), last event 0.0h ago, 172 entries |
| disloc:MU | active | census 183 ev / 158bps (alert 183), last event 24.8h ago, 87 entries |
| disloc:NEAR | active | census 22 ev / 150bps (alert 22), last event 33.3h ago, 0 entries |
| disloc:RESOLV | active | census 463 ev / 188bps (alert 463), last event 6.3h ago, 9 entries |
| disloc:SKHYNIXUSD | active | census 877 ev / 414bps (alert 877), last event 18.7h ago, 701 entries |
| disloc:SKY | active | census 96 ev / 315bps (alert 96), last event 28.3h ago, 3 entries |
| disloc:SNDK | active | census 316 ev / 252bps (alert 316), last event 2.9h ago, 182 entries |
| disloc:STABLE | active | census 317 ev / 396bps (alert 317), last event 5.6h ago, 9 entries |
| disloc:STBL | active | census 228 ev / 245bps (alert 228), last event 0.9h ago, 28 entries |
| disloc:ZORA | active | census 240 ev / 202bps (alert 240), last event 6.2h ago, 12 entries |
| factor-sample:10 | active | joined decision+context dataset at 326 closes (53% win), bucket 10 |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=86 (≥10): net $+8.34, WR 34%, t=0.75 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-breakoutup' at n=14 (≥10): net $+3.41, WR 50%, t=0.42 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=72, net $+9.49 — by lens [('short', 68, 8.98), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=30, net $-0.58 — by lens [('short-divergence', 18, 1.32), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light green — longs 12/20, shorts 7/12 (gross 19); 7d DD -0.34%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.129pp (live +0.505% n=47, shadow +0.376% n=52) — no divergence
- 🧬 Farmer arms AGREE: live 705425a83422 vs shadow 705425a83422 (n=15)
- 🧬 Taker arms DRIFT: live fd4663d27fb5 vs shadow 5e27c751f5b2 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container 705425a83422 vs repo 30bf230bd5fb (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container 705425a83422 vs repo 30bf230bd5fb (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container fd4663d27fb5 vs repo 5e27c751f5b2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 lighter-ticket-taker-lshadow matches the repo tree: 5e27c751f5b2 (n=15)

## Summary

18 alert keys reviewed: 18 active, 0 resolved, 0 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.

---

# Human layer — daily review, Sun 2 Aug 2026 (executed to ~11:15 AEST)

Suite **777** (+6), ten guards green, thirteen mutations red. Three fixes
implemented and committed **locally — NOT pushed** (this task may not push).

## ⚠️ LEAD ITEM — both real-money containers are behind the repo

The review now measures this for the first time (see "What I fixed" #1). Same
`build_n=15` on every row, so per `(fd)` this is **code drift, not file set**:

| Row | container | repo predicts | missing |
|---|---|---|---|
| 🎫 **lighter-ticket-taker-lighter** (LIVE) | `fd4663d27fb5` | `5e27c751f5b2` | `(ij)`'s lens veto fix |
| 💸 **perps-funding-lighter-lighter** (LIVE) | `705425a83422` | `30bf230bd5fb` | `(hp)`/`(ht)`/`(hr)` publisher changes |
| 💸 perps-funding-lighter-lshadow | `705425a83422` | `30bf230bd5fb` | same (its control twin) |
| 🎫 lighter-ticket-taker-lshadow | `5e27c751f5b2` | `5e27c751f5b2` | ✅ current — **this is the control group** |

**The taker one is the urgent half, and I checked `(ik)`'s "nothing is at risk
while it waits" rather than inheriting it.** It still holds — but by 0.003.

The live arm is side-aware, so its veto reads `by_side.short`, today
`eavg4h_pct −0.148 / ehit4h 0.503`. The OLD rule it is running is
`avg < 0 AND hit < 0.5`, so it escapes **only because 0.503 is not below
0.500**. The POOLED grade is already `−0.100 / 0.494` — under the old rule that
vetoes. So the live book's only lens is three thousandths of forward hit rate
away from being halted by a proxy, by a rule its successor has already deleted,
while its own 16 live closes read **+0.558%**. That is exactly the inversion
`(ij)` was built to prevent.

    gh workflow run 305025607 -f services="tide-rider-lighter-live"

Verify by the `extra.build` + `extra.build_n` stamp, never by a green run.
**Not run — real money is an operator act.** Note this was blocked twice by the
harness permission classifier for the `(ik)` session; if it blocks again, the
decision to use the commit-marker route instead is yours, not mine.

The Farmer's drift is lower-risk (its two arms agree with each other, so the
control is still valid) but it is **~3 days behind `bot_pnl_store`** and, being
marker-gated, will stay behind until deliberately shipped.

## What I fixed this run (committed locally, unpushed)

1. **The arm-drift check reads "healthy" when both arms are stale.** It compared
   live vs shadow only, so a total deploy failure of both arms printed
   `arms AGREE` — and the selftest pinned that as raising no flag. That is how
   the Farmer sat 3 days behind while the review called it fine.
   `build_compute` had existed since `(fd)` with **no running consumer anywhere
   in the tree**: every check against the repo in this fleet's history was
   hand-typed into a changelog entry. Now standing, `n`-first, fail-soft.
2. **`audit_ledger_integrity` still told you to stop a Railway service.**
   `(ih)` scoped the pager and `(ii)` scoped the gate; this was the **third
   consumer of the same finding** and was missed. It now reads
   `2026-07-29T07:39Z (89.5h ago) — HISTORICAL, no overlap inside 6h. Nothing to
   stop.` **The finding is unchanged and it still exits non-zero** — carry's
   sample is still pooled and unusable. Only the instruction changed.
3. **`prune_history` had never once succeeded.** `make_interval(days => …)`
   takes an integer; the bind is a float. It has raised on every call since
   16-Jul, logged once per process, and the caller discards the result — `(I4)`
   exactly. Found by reading a container log, not by a test. **Zero rows
   affected to date** (26 days of history against a 60-day policy); it would
   first have mattered ~5-Sep, and it does not threaten `(hl)`'s MTM equity
   series. Fixed before it could cost anything.

## Fleet state

- **All 23 books and every organ are fresh** — a real change from 31-Jul/1-Aug,
  when the brain and sentinel were 14h dark. Brain alive (1.1h), memory
  advancing. Only declared-dead keys are stale (`gapscout-census`,
  `listing-intel`, retired rows). 🌊 Tide Rider's row is gone, as `(if)` intended.
- **`READY: none`**, unchanged. No book passes the gate.
- fleet-risk **green**: longs 12/20, shorts 7/12, 7d DD −0.34%, `clip_scale` 1.0.
  The long-budget pressure `(if)` relieved has stayed relieved.
- Farmer live-vs-shadow gap **+0.129pp** — no divergence.
- The review script itself ran clean: `errors: []`.

## Findings I did NOT act on

- **🧲 Snap Back is the fleet's most significant negative result.** n=101 opened
  since 30-Jul at **−0.402%/trade, t=−3.12**. Not a concentration artifact
  (−0.248%, t=−2.31 without the two worst). **Every one of those 50 exits is
  `converged`** — the thesis fires as designed and the book still loses money,
  which points at entries too small to cover the round trip rather than at the
  exit. Its own lever `disloc.enter_pct` has `step: -0.01`, so **the growth rail
  can only loosen this gate, never tighten it.** Keep-or-retire is your call —
  the same shape as 🌊 Tide Rider, and per `(hl)` the answer is not more
  throughput. I did not file a lever proposal: the `lighter-books` lane's only
  author is the evidence board and the scout tuner's replay gate is taker-
  specific, so there is no gate that could actually grade a restriction here.
- **🌾 carry has opened nothing since 30-Jul 01:40Z (~47h).** It holds 5
  positions, all opened *before* its new era, aged 105–247h. It has 7 of 12
  slots free, a 20% APR bar, and publishes its own hottest candidates at
  **+245% to +345%**. The container is alive and healthy —
  `scan ok | 217 perps` every 5 minutes. **I did not diagnose the cause**: the
  logs carry no reject reason, and `(ie)` is the standing lesson against naming
  a cause before reading the evidence. It matters because carry's era clock
  restarted 31-Jul and **cannot start accumulating until it opens something.**

## Carried priorities — status

1. **L2 long-budget restructure** — still open, still not urgent (12/20 green).
   Unchanged from 1-Aug.
2. **🌾 carry's duplicate writer** — **CLOSED as an incident.** Latest overlap
   29-Jul 07:39Z, 89.5h ago, zero since `claim_writer` merged. The 7 historical
   overlaps stay in the ledger and still block `READY` forever, which is
   correct. The guard now says so instead of sending you to Railway.
3. **MTM drawdown re-grade** — on track, window closes ≈10–11 Aug. Confirmed the
   retention bug above does **not** threaten the equity series.
4. **Three fleet position counters** — not reconciled; unchanged.

## What you actually need to do

1. Decide on the **live taker deploy** (command above). Buffer is 0.003.
2. Decide **keep-or-retire on 🧲 Snap Back** (t=−3.12 over 101 closes).
3. **Push the local commit** when you're happy with it — `(il)`, five files.
   Re-check the changelog letter first; it was picked at commit time, and the
   guard will catch a collision on push.

## OPTIONS TO OPTIMISE

Ranked. Each names the change, its current value and bound, the measured
evidence, and the expectancy cost.

### 1. Unblock the growth rail on 🎫 the taker's only live lens — highest value

**The tuner and the taker disagree about `divergence`, and the tuner is using
the basis `(ij)` proved is the wrong horizon.**

`lighter_scout_tuner.vetoed_lenses` delegates to the taker's single authority —
correctly, no second copy — but calls it as
`tt.vetoed_lenses(lens_fwd, min_n=LENS_FLOOR)`: **no `sides`, no `realised`.**
So it never sees the evidence `(ij)` made senior. Measured on today's live
payload:

    TUNER   vetoes  {dip, divergence, momentum}     <- pooled 4h forward proxy only
    TAKER   vetoes  {dip, momentum}                 <- realised closes are senior

    realised, shadow arm:  divergence n=50  +0.463%  t=+0.83
    realised, live arm:    divergence n=26  -0.385%  t=-0.52   (bar is t <= -1.0)

Its own production log says so in as many words:
`"divergence: brain-vetoed at floor — never widened"`. So the one lens the live
book actually trades is the one lens the growth rail will never widen — which
is precisely *"anything stopping it from winning"*.

- **Change**: pass the arm's `realised=` evidence (and `sides=`) through the
  tuner's delegation, as the taker's own entry loop already does.
- **Expectancy cost: none at the decision point.** This does not widen
  anything — it only lets the lens enter the walk. The tuner's expand rule
  still requires IMPROVE-both-halves through the real replay gate, and the
  brain veto stays senior. `divergence` is **undecided, not a winner** (neither
  arm's t clears ±1), so the honest gain is that an undecided lens becomes
  eligible to be measured rather than being refused on a proxy.
- **NOT shipped this run, deliberately.** Three changes already landed and were
  verified in the live payload; doctrine rule 1 is ship-narrow. This one alters
  an actuator that decides widening, and CLAUDE.md is explicit that such a
  change earns its replay evidence first. It is the natural first item for the
  next pass.

### 2. Deploy the live taker (real money — operator act)

- **Current**: live `fd4663d27fb5`, repo `5e27c751f5b2`. Command in the ACTION
  section above.
- **Evidence**: the live arm escapes its own stale veto by **0.003** of forward
  hit rate (`0.503` vs a `< 0.500` trigger), while the pooled grade has already
  crossed at `0.494`.
- **Expectancy cost: none.** Both the old and new rules permit `divergence`
  today, so live behaviour is identical on arrival. This is insurance, and the
  buffer it insures is three thousandths wide.

### 3. Diagnose 🌾 carry's entry stall — the biggest unblock on the board

Carry is the **only book in the fleet with a measured claim** (the allocation
organ puts it at $4,045 of the $16k funding class). Its era clock restarted
31-Jul and **cannot begin accumulating until it opens a position** — and it has
opened none in ~47h despite 7 free slots, a 20% APR bar, and its own published
candidates at +245% to +345%.

- **Not a lever**: nothing is misconfigured that I can see, and the container is
  healthy. It needs someone to read why a scan of 217 perps yields no entry.
- **Expectancy cost: none.** This is diagnosis, and every day it waits is a day
  the fleet's best-evidenced book is not accumulating gradeable evidence.

### 4. 🧲 Snap Back — the lever points the wrong way

- **Lever**: `disloc.enter_pct`, currently **0.98**, cage **[0.90, 0.999]**,
  `step: -0.01` — i.e. **the growth rail can only loosen it.**
- **Evidence**: n=101 since 30-Jul at **−0.402%/trade, t=−3.12**; robust to
  removing the two worst trades (−0.248%, t=−2.31); **100% of exits
  `converged`**, so the thesis is firing and losing anyway.
- **Options**: retire it (the 🌊 Tide Rider precedent), or give the lever a
  restrict path so the rail can tighten a gate that is admitting residuals too
  small to cover the round trip. **Cost of tightening: fewer trades** — which
  per `(hl)` is the correct direction when throughput is being bought with
  expectancy, but it must be replay-evidenced, and no gate currently exists
  that can grade this lane.

### 5. Capacity and reach: nothing is on offer today, and here is what I checked

State it plainly rather than omit it:

| Book | open / cap | verdict |
|---|---|---|
| ⚖️ Counterweight | **16 / 16 (k=8)** | at cap, but MTM **−$13.88** — `(hs)` is correctly HOLDING it. Not on offer. |
| 🌾 carry | 5 / 12 | not binding |
| 📊 Index Rider | 3 / 9 | not binding, and still **0 closes** |
| 🎯 Perp Sniper | 0 / 4 | not binding |
| L2 long budget | 12 / 20 | not binding (shorts 7/12) |

**No book with a graded signal is losing trades to a binding cap.** The only
book at its cap is one the growth rail is deliberately and correctly refusing to
widen. That is a refusal with evidence, not an absence of looking — and it is
the second day running that the real headroom has been in correctness rather
than in capacity.

---

# Addendum — after the operator's dispatch and the optimisation pass (~12:00 AEST)

## ✅ The live taker deploy LANDED and is verified

Your dispatch deployed `tide-rider-lighter-live` from latest main at 01:46:17Z
(two runs targeted it; one was a harmless repeat, one was cancelled).

Verified the way doctrine demands — **a prediction made before reading the row**,
computed from a clean `origin/main` worktree, not from my dirty tree:

| Row | was | now | predicted |
|---|---|---|---|
| 🎫 `lighter-ticket-taker-lighter` | `fd4663d27fb5` | **`5e27c751f5b2`** / n=15 | `5e27c751f5b2` / 15 ✅ |

Both taker arms are now converged, so **the arm drift is closed** and `(ij)`'s
lens veto fix is **live on real money**. The 0.003 forward-hit-rate buffer is no
longer load-bearing.

**💸 The Farmer was NOT in the dispatch** and remains on `705425a83422` against
a repo prediction of `30bf230bd5fb` (same `build_n=15`, so genuine code drift).
It is ~3 days behind `bot_pnl_store` and, being marker-gated, stays there until
deliberately shipped:

    gh workflow run 305025607 -f services="trail-blazer-live,funding-farmer-shadow"

Both arms together, so the judge keeps a converged control pair.

## Optimisation #1 implemented — `(im)`, committed locally, unpushed

The tuner/taker veto disagreement is fixed, and closing it found more than
expected.

- **Verified on the live payload**: tuner `{dip, divergence, momentum}` →
  `{dip, momentum}`, now byte-equal to the taker's own verdict on the same data.
- **`audit_recurrence` went red on the commit** — `lighter-ticket-taker`, 6
  entries in 7d, *"the class is not closing"*. It was right, and it caught this
  pass mid-flight rather than after the fact. Grepping every caller found a
  **third consumer**: `strategy_incubator.live_lenses`, excluding `divergence`
  — the only lens the live arm may fill — on the same wrong-horizon proxy, so
  the incubator was breeding genes for lenses the live book cannot trade.
- **The class is now closed executably**, not acknowledged away:
  `tests/autonomy/test_lens_veto_consumers.py` fails the build if any consumer
  outside the defining module calls `vetoed_lenses` without the lens's own
  record — found by AST across the whole tree, so a fourth cannot arrive quietly.

**What this does NOT do**: it makes a lens *eligible* for the walk. The expand
rule still requires improve-both-halves through the real replay gate, and
`divergence` remains **undecided** (shadow +0.463% t=+0.83, live −0.385%
t=−0.52). The gain is that it can now be measured instead of refused.

Three of eight mutations survived a green selftest before the tests were good
enough — including an AST check made vacuous by the callee's own parameter name.
That is recorded in the entry rather than quietly fixed.

Suite **780**, ten guards green, ten mutations red.

## Revised list of what you need to do

1. **Deploy the Farmer** (command above) — the remaining half of the drift.
2. **Keep-or-retire 🧲 Snap Back** (t=−3.12 over 101 closes) — unchanged.
3. **Diagnose 🌾 carry's entry stall** — unchanged, and still the biggest
   unblock: it is the only book with a measured claim and its era clock cannot
   start until it opens a position.
4. **Push two local commits** — `(il)` and `(im)`. Re-check the changelog
   letters first; the guard will catch a collision on push.
