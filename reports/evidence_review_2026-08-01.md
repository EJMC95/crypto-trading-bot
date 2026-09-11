# Evidence Review — 2026-08-01

_Reviewed 2026-08-01T07:26:45+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow fd4663d27fb5 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 9384 events across 33 books (threshold 50) |
| disloc:0G | active | census 438 ev / 277bps (alert 438), last event 4.5h ago, 31 entries |
| disloc:APEX | active | census 4021 ev / 313bps (alert 4021), last event 1.8h ago, 451 entries |
| disloc:BIO | active | census 93 ev / 272bps (alert 93), last event 17.3h ago, 6 entries |
| disloc:CHIP | active | census 199 ev / 160bps (alert 199), last event 2.2h ago, 10 entries |
| disloc:EIGEN | active | census 189 ev / 161bps (alert 189), last event 15.7h ago, 4 entries |
| disloc:GMX | active | census 166 ev / 151bps (alert 166), last event 4.5h ago, 16 entries |
| disloc:KAITO | active | census 1103 ev / 350bps (alert 1102), last event 0.9h ago, 124 entries |
| disloc:MU | active | census 183 ev / 158bps (alert 183), last event 7.2h ago, 87 entries |
| disloc:NEAR | active | census 22 ev / 150bps (alert 22), last event 15.7h ago, 0 entries |
| disloc:RESOLV | active | census 460 ev / 188bps (alert 459), last event 1.0h ago, 7 entries |
| disloc:SKHYNIXUSD | active | census 877 ev / 414bps (alert 877), last event 1.1h ago, 701 entries |
| disloc:SKY | active | census 96 ev / 315bps (alert 96), last event 10.8h ago, 3 entries |
| disloc:SNDK | active | census 295 ev / 252bps (alert 295), last event 7.2h ago, 169 entries |
| disloc:STABLE | active | census 312 ev / 396bps (alert 312), last event 17.6h ago, 6 entries |
| disloc:STBL | active | census 217 ev / 245bps (alert 217), last event 4.3h ago, 19 entries |
| disloc:ZORA | active | census 235 ev / 202bps (alert 235), last event 4.8h ago, 9 entries |
| factor-sample:10 | active | joined decision+context dataset at 315 closes (53% win), bucket 10 |
| factor-sample:9 | resolved | joined decision+context dataset at 315 closes (53% win), bucket 10 |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=86 (≥10): net $+8.34, WR 34%, t=0.75 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-breakoutup' at n=13 (≥10): net $+4.52, WR 54%, t=0.57 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=70, net $+9.04 — by lens [('short', 66, 8.53), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=30, net $-0.58 — by lens [('short-divergence', 18, 1.32), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light green — longs 12/20, shorts 6/12 (gross 18); 7d DD -0.29%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.166pp (live +0.470% n=46, shadow +0.304% n=56) — no divergence
- 🧬 Farmer arms AGREE: live 705425a83422 vs shadow 705425a83422 (n=15)
- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow fd4663d27fb5 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds

## Summary

19 alert keys reviewed: 18 active, 1 resolved, 0 stale. No divergence and no drawdown-governor trigger. 12 new-evidence items scanned.

---

# Human layer — daily review, Sat 1 Aug 2026 (executed through ~17:35 AEST)

**Everything advised was executed and verified in the live payload.** Five
commits pushed: `(ie)` `(if)` `(ig)` `(ih)`. Suite **763**, nine guards green.

## Outcome

| | before | after |
|---|---|---|
| 🧠 brain | dead 14h, memory frozen at run 337 since 28-Jul | **alive, `healthy=True`, runs=338, memory advancing** |
| 🗞️ event sentinel | dead 14h | **alive** |
| growth rail | *"brain dark — lens-keyed bar walks suppressed"* | **per-lens decisions again** |
| L2 long budget | 18/20, yellow | **12/20, GREEN** |
| 🌊 Tide Rider | live, 33% of the long budget, 0 closes in 22d | **retired: idled, hidden, row pruned** |
| duplicate-writer pager | fired forever, named a service that no longer exists | **scoped to a live incident, names `claim_writer`** |

## The correction that mattered most

**My `(ie)` diagnosis was wrong.** I reported two dead subshells and advised a
restart, suspecting OOM. I restarted — and nothing came back. The logs had it:

    File "/freqtrade/bot_learn.py", line 2340, in <module>
    NameError: name 'store' is not defined

`(hw)` moved 19 organs onto `store.organ_main(...)` in their `__main__` block;
`bot_learn` and `event_sentinel` bind `store` only *inside* functions, so both
crashed on every run behind `run_all.sh`'s `|| true` — **the wrapper built so
that no organ could die silently was itself killing them, silently.** A restart
could never have helped.

`(ib)`'s day-old `audit_undefined_names` was green over 99 modules throughout,
because it declares *"does not model scopes"* and a function-local import binds
the name in *a* scope. The new scope arm needs no scope model. Its first cut
reported 53 findings, all comprehension variables (`ast.walk` is flat) —
rewritten as explicit recursive descent: **99 modules, zero false positives**,
and it names file and line if either fix reverts.

**A restart coming back negative is data.** Read the logs before naming a cause.

## Still outstanding — one item, real money

**🎫 Live Ticket Taker has drifted from its shadow control** — `live
0b30b0a79211` vs shadow, **same `build_n=15`**, so genuine code drift and not
the `(fd)` file-set artifact. While it holds, the shadow is not a clean control.

    gh workflow run 305025607 -f services="tide-rider-lighter-live"

Verify by the `extra.build` + `extra.build_n` stamp, never by a green run.
**Not run — real money is an operator act.**

## Two things that will settle on their own

- The duplicate-writer page **stays loud until the grader republishes** with the
  new `latest_overlap` field (6-hourly). Verified against the live payload: it
  currently reads `None`, so my code correctly says *"most recent at an UNKNOWN
  time"* and keeps paging. Fail-safe by design; self-heals on the next cycle.
- 🌾 carry's 7 overlaps stay in the ledger permanently and still block `READY`.
  That is correct — the sample really is pooled. All 7 predate the guard.

## Carried forward

1. **MTM drawdown re-grade** — `(ia)`'s bar is in, gated behind 200 samples /
   7 days. Window closes ≈10–11 Aug. On track.
2. **L2 admission by edge** — reframed by measurement, not deferred: longs are
   −0.158%/t=−1.78 in-era against shorts +0.062%, so the fix is *what holds the
   budget*, not a bigger number. With Tide Rider gone the pressure is off
   (12/20, green), so this is no longer urgent.
3. **The task's own SAFETY RULES** need your edit — replacement text is in the
   scratchpad; the harness path classifier blocks an agent writing
   `~/.claude/scheduled-tasks/**`.
