# FLEET AUDIT — 2026-09-01

**Eamon's ask:** *"Fleet wide audit and review of everything. Goal is making
positive adjustments and reviewing works done over the last week ... there has
been some positives this week and must ensure everything is running as smoothly
as possible."*

Audited by Lucy, 1-Sep, from the live payloads (`/pnl.json`, `/bus.json`,
`/watchdog.json`), the repo's own audit suite, and the merge history. Changelog
entries: **(vs)–(vw)**. Companion PR restores the changelog, repairs the bezos
book, and turns main's CI green again.

---

## 1 · The headline: the week's positive is real, and it is 👩 mum

| | |
|---|---|
| 👩 mum-lighter | **+$68.50 on her $300 book (+22.8%)**, 41W/8L, 49 closes |
| Go-live gate | **5 of 6 bars PASSING** — failing only the 30-day window, verdict **on_track, ETA ~26 days** |
| Allocation table | **The fleet's best era claim: +0.346%/trade lower bound (n=49)** — top of the table, live arm above every shadow |

The (ro) redesign (1h clock, bracket at entry) plus the (vd) supply fixes
(4→12 slots, $0.1M floor, 40 crypto) are earning at the top of the fleet's own
evidence ranking. Her shadow twin is on the same track (ETA ~23d). If the
window bar holds, **mum is the first book to reach the full gate since it was
specified** — nothing to do but let her clock run.

Also genuinely smooth: **watchdog zero problems, 20/20 rows fresh** (freshest
3s), risk light **green** (9 long / 6 short vs the 20 budget), `clip_scale`
1.0, no quarantined levers, no two-writer pages, and every service except one
(§4) **CURRENT at HEAD** by `audit_code_currency`. 🎫 taker shadow **+$75.01**
sits 5-of-6 (t binding, on_track ~48d). 🌾 carry **+$66.70** holds 15 shorts
harvesting 43–364% APR (see §6 for the 15-vs-12 note).

## 2 · The bad find: the CHANGELOG was wiped on main (now repaired)

* **PR #237** (29-Aug, squash) replaced CHANGELOG.md — **28,393 lines, 655
  entries — with a 2-line stub.**
* **PR #212** (31-Aug, a branch cut ~20-Aug) then overwrote the stub with its
  **stale 566-entry copy**, so main's record ended at 20-Aug: **eleven days
  and ~90 entries gone** — the I25/I26 doctrine records, the permission
  amendments, mum v2's go-live chain, georgia v3's birth.
* Blast radius: **364 code citations resolving to nothing**;
  `audit_changelog_letters` red on every push since.

**Repaired in this PR:** full restoration from the last pre-wipe tree, plus
the five entries the gap owed ((vs) #237's record, (vt) #238's, (vv) #239's,
(vu) the #212 entry renumbered off a letter collision, (vw) this audit).
**The class is closed:** the letters guard gains a **lost-entries arm** — an
entry on origin/main missing from a push fails the build unless a renumber is
declared — mutation-verified both ways.

**Why it could happen: the PRs were authored by GitHub Copilot's agent and
merged with the repo's own guards already RED.** Four separate pre-existing
CI failures traced to those merges (letters, born-dark imports, selftest
registration, organ-silence). The guards all worked; the merge button ignored
them. → **Decision 1 in §7.**

## 3 · The week's other work, reviewed (25-Aug → 1-Sep)

**The Lucy-session chain (25→28-Aug, entries (te)→(vr)) — reviewed and
sound.** Mum live launch + supply chain; georgia's live-arm exit-policy defect
found and fixed; the phantom-close class closed fleet-wide; I25 (hot-window
regression) and I26 (burden of proof on the refusal) engraved; georgia v3 born
(shadow, pre-registered bars); the census denominator (`snapshot_census`) the
fleet never had; the claims ledger. The audit re-ran the enforcement suite on
all of it: doctrine enforcement 26/26, recurrence covered, lever bounds OK,
session_state carried rows all honest.

**The Copilot PRs (29–31 Aug) — mixed; reviewed line by line:**

| PR | Verdict |
|---|---|
| #212 `LeveredPaperBroker` | **Good instrument** (cross-margin liquidation on paper — ruin visible at last). Cost: the changelog overwrite + a letter collision, both repaired. |
| #237 `edge_aware_safety.py` | Harmless offline tool. Cost: the wipe itself. |
| #238 bezos + telemetry | Telemetry kept (ping throttle, live progression ETA, audit hardening). **The book was born dead** — see §5. |
| #239 dashboard fixes | **Good** — live-row staleness thresholds, contributed-capital pnl_pct, return % on totals. Not yet serving (§4). |

## 4 · Running smoothly? Two containers were not — both redeploy-dispatched

* **`family-lighter-shadow` is BEHIND-OWN by 9 commits — and its deploys
  REPORT OK.** 🔭 **georgia-v3 has been TRADING since 28-Aug (32 closes,
  −$5.33 — decides nothing yet) but never publishing her row**: her
  publish/census half and #239's family pnl_pct never reached the container,
  while the 30-Aug runs 646 and 647 both printed *"OK: 'family-lighter-shadow'
  deployed"*. The (ml) stuck-serving class — the workflow's boot-stamp
  readback covers only the dashboard, so a stuck family service passes green.
  Re-dispatched this session with a stamp readback; **if it sticks again the
  service needs a kick from the Railway dashboard — that one is yours.**
* `pnl-dashboard` itself is CURRENT — its 02:54:20Z boot postdates #239's
  02:52:53Z merge and run 646's own readback proved the flip. (My first read
  called it stale off a timezone slip; corrected in place.)

## 5 · 🚀 book-bezos: born dead three ways, repaired in this PR

Eamon's Copilot-built Bezos book merged 30-Aug and **never ran once**:

1. **Missing engine COPY** — the wrapper imports the Douglas engine;
   `Dockerfile.freqtrade` never shipped it, so the bot died on import **every
   30 seconds for two days**, silently (`|| true`). `audit_image_imports`
   flagged exactly this on merge day. **Fixed: the COPY ships.**
2. **Accidental 5× leverage** — `START_EQUITY=$100` against the engine's fixed
   $100 clip × 5 slots, on the 1× paper broker whose ruin-blindness PR #212
   itself measured. **Fixed: $1,000, the fleet standard** (same profile = 0.5×
   gross, and the census now prints the number).
3. **No I22 spend census, no selftest registration, invisible to agronomy, no
   death recorder.** **All fixed**: the Douglas engine gains the (vr)-shape
   `spend_extra` for variants (Douglas itself stays silent/grandfathered),
   bezos registered in `SELFTEST_MODULES` + `fleet_agronomy`, entry point
   routed through `organ_main` so a crash records itself.

Design note kept honest: bezos is Douglas's impulse cell at a lower bar (2.2×
vs 2.5× ATR) with a different bracket — a variant-cell overlap (I20), not new
supply. It runs cheap at $1k shadow; its ledger against Douglas's decides
whether the bracket earns the row. Kill switch: `BEZOS_ENABLED=0`.

## 6 · Book-by-book standings (the grader's own verdicts)

| Book | P&L | Gate | Note |
|---|---|---|---|
| 👩 mum-lighter | **+$68.50** | **5/6, on_track ~26d** | §1 |
| 👩 mum-lshadow | +$17.07 | 4/6, on_track ~23d | control arm tracking |
| 🎫 taker-lshadow | **+$75.01** | 5/6 (t), on_track ~48d | best shadow earner |
| 🌾 carry | +$66.70 | `underpowered` (era thin, ~4d to power) | 15 open vs cap 12 — **benign**: entries hard-gate at 12; the extras date from an expired widening and wind down as they close; meanwhile all 15 harvest 43–364% APR |
| 🙏 avo-lighter | −$9.07 | 2/6, `undecidable` (t) | 4 real closes; slow by design |
| 🔮 georgia-lighter | **−$78.90** | **0/6, `unreachable`** | the week's responses stand: trend_breakout sleeve retired (vd), v3 born (vr); her v3 ledger decides, not another tuning pass |
| 🪁 band-kelly | **−$156.76** | **`unreachable`** | −0.326%/trade over the last 140 closes ≈ **$19/day burn at the (qj) $250 clips** → Decision 2 |
| 🧮 hull | +$1.84 | slow clock (declared) | 10/10 slots full, oldest 416h — working as designed |
| 🏦 kiyosaki | +$13.25 | accruing | fine |
| 🧘 douglas | −$57.02 | accruing (n=79) | gradeable ~12-Sep |
| 📐 grimes | $0.00 | all 3 setups gate-closed | **0 trades ever; the ~12-Sep I17 call is real** |
| 🧭 nav-cook | −$9.99 | accruing (n=38) | post-(sa) fix era |
| 🎯 sniper | −$1.51 | `underpowered` (kept+fed per (tz)) | fine |
| 💸 farmer-lshadow | −$14.73 | control arm | fine |
| ⚖️ counterweight | −$35.04 | pre-registered call was ~28-Aug | **overdue — Decision 4** |
| 🛢️ garrett | −$26.34 | accruing | ~12-Sep component call |
| 🏛️ albanese/turnbull | −$3.39 / +$2.53 | accruing | fine |
| 🔭 georgia-v3 | −$5.33 (32 closes) | hypothesis-grade | row visible after the family redeploy |
| 🚀 bezos | never ran | — | runs after this PR merges |

**The organs:** the brain publishes three reduce opinions (douglas
short-impulse 0.75×, taker short-divergence 0.75×, georgia-v3's probe 0.75×)
and no expands — mum's bucket is **`warming: expand`** at episode-t 1.91, one
small step of evidence from a 1.25× (the (vx) edge study has the full
decomposition; an earlier draft of this line said "zero opinions" — corrected);
judge `stood_down` (correct — farmer retired; avo pair below its floors);
allocation ranking honestly (mum top); immune has **one live page class** →
§7 Decision 3.

## 7 · Decisions that are yours, Eamon (nothing here changed by me)

1. **Turn on branch protection / required status checks for `main`** (the
   changelog-check workflow at minimum). One GitHub setting. Four red guards
   were merged past this week; the wipe rode in the same door. Until this is
   on, any external-agent PR can do it again. Related, found on this PR's own
   first CI round: **#238's CodeQL check had failed all 10 runs it ever had**
   (a crashing per-file `paths:` config + code scanning not enabled on the
   repo) — an always-red check is what normalises merging past red. Rebuilt
   as a working full-tree job that SKIPS until you enable code scanning
   (Settings → Code security) and set repo variable `ENABLE_CODEQL=1`.
2. **🪁 band-kelly clips $250 → $80 pending its ~18-Sep call.** The grader
   reads `unreachable` (upper bound ≤ 0) and the recent tape is −0.326%/trade;
   at (qj)'s $250 clips that is ~$19/day of burn. Clip is %-invariant to the
   grade ((hl)) so reverting costs the decision nothing and cuts the burn ~3×.
   Not done by me because (qj) was your on-the-record risk-up — say the word
   and it ships.
3. **The immune organ is paging all three live books: "protective stop is DEAD
   at gross 10.0 — liquidation fires before the stop."** Stop-death ceilings
   at the current universes: **mum 4.17× · avo 4.55× · georgia 9.09×** vs
   `gross_x` 10.0 on all three. 10× is your recorded ask for avo+georgia
   (22-Aug); mum's ceiling collapsed because her widened $0.1M universe admits
   20%-margin coins. Above the ceiling the stop chain is dead code — the daily
   halt and venue liquidation are the only rails. Either accept (it is
   published every loop, and today's actual deployment is small — mum holds 1
   of 12 slots) or set each book's `GROSS_X` to its own `stop_dead_above` and
   the stops come back to life. Your money, your call — but it deserves a
   deliberate yes.
4. **⚖️ Counterweight's pre-registered keep-or-retire call (was ~28-Aug) is
   now overdue**, and 📐 grimes (0 trades ever, all gates shut) reaches its
   I17 call ~12-Sep alongside the 🌾/🏦 cell component and 🛢️ garrett.

## 8 · What this session shipped

* CHANGELOG restored (655 → 660 entries) + the lost-entries guard arm +
  the declared-renumber escape (mutation-verified).
* bezos: engine COPY, $1k standard, I22 census via the engine, organ_main,
  selftest + agronomy registration, deploy-coverage closure.
* `family-lighter-shadow` redeploy dispatched with stamp readback (un-darks
  georgia-v3's row + lands #239's family pnl_pct); the dashboard verified
  already current.
* This report; HANDOFF regenerated; hub updated.
