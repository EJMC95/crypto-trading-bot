# REVIEW_BOOKS_WAVE2_ADVERSARIAL_2026-08-14 — the 24-agent adversarial review of the four wave-2 book bots, every finding adjudicated

**Why this file exists:** the adjudication record (per-finding verdicts with the
verifiers' measured reasons) lived only in the review workflow's session-local
output and journal — session-ephemeral, gone when the container recycles — and
the operator asked for all found data to be saved. This is the durable copy.

**Context.** The review ran 13/14-Aug over the BOOKS wave-2 birth
(`lighter_book_{douglas,grimes,schwager,hull}_bot.py` + their wiring:
`scripts/audit_book_overlap.py`, `.github/workflows/books-provision.yml`),
AFTER the `(mh)` birth review had already landed its six fixed defect classes
in commit `454efaf` (merged in PR #169, `9386537`). **24 agents**: five
reviewers (one per bot file + one WIRING, 2–6 findings each, ~120–215k tokens
each) produced **19 findings**; nineteen verifiers then re-derived each one
against the branch tip — every finding got a full verify pass, **none was
dropped or duplicate-merged**. Outcome: **3 CONFIRMED** (all fixed the same
session, changelog `(ml)`), **14 already fixed before the verify stage ran**
(13 by the `(mh)` birth review, 1 by the `(mi)`-addendum provisioner
postmortems), **2 refuted**. The refutations and stale-finding rejections are
kept in full below — a refusal with evidence is evidence (house rule, `(hl)`).

**The one structural observation worth keeping:** most of the 14
"already fixed" findings independently re-derived exactly the defects `(mh)`
had fixed days earlier — the reviewers were reading the pre-`(mh)` draft
(`b290532`, a pre-merge PR commit that is NOT an ancestor of HEAD) while the
verifiers read HEAD. That is corroboration of `(mh)`'s findings by blind
rediscovery, not wasted work — and one item ran the other way: `(mh)` had
DECLARED the replay's skip-the-entry-bar convention as acceptable calibration
parity ("the same convention the measurements were calibrated with"); this
review measured it as a real optimism at decision-flipping size, and `(ml)`
fixed it. A declared limitation was upgraded to a fixed defect by measurement.

## Scoreboard

| # | File | Finding | Sev | Verdict | Disposition |
|---|---|---|---|---|---|
| F1 | lighter_book_grimes_bot.py | Stale/absent dtrend cache fails OPEN for keltner; cache not persisted | major | **CONFIRMED** | fixed `(ml)` — trend_at None contract |
| F2 | lighter_book_grimes_bot.py | Replay never brackets the entry bar's own range | minor | **CONFIRMED** | fixed `(ml)` — entry-bar bracket, bot + study |
| F3 | .github/workflows/books-provision.yml | Variable echo can leak resolved Postgres password past line-based sed | major | **CONFIRMED** | fixed `(ml)` — echo deleted `ea36a3e`; forensic audit PARTIAL, zero chars leaked |
| F4 | lighter_book_grimes_bot.py | Daily-trend map lacks the current UTC day (look-ahead + missing live key) | critical | refuted at HEAD | already fixed `(mh)` — LAG-1 convention |
| F5 | lighter_book_schwager_bot.py | Trail ratchets on 5-minute marks, not 4h closes | critical | refuted at HEAD | already fixed `(mh)` — closed-bar ratchet |
| F6 | lighter_book_douglas_bot.py | Crypto screen runs AFTER top-18 truncation | major | refuted at HEAD | already fixed `(mh)` — screen-then-slice |
| F7 | lighter_book_schwager_bot.py | EMA50 confirm on a 61-bar fetch, unconverged | major | refuted at HEAD | already fixed `(mh)` — 3× EMA_SLOW window |
| F8 | lighter_book_grimes_bot.py | Retest fetches ~782 bars in one un-paginated call (~83d window, not 120d) | major | refuted at HEAD | already fixed `(mh)` — `_paged_bars` |
| F9 | scripts/audit_book_overlap.py | `admits()` has no apr-ceiling arm; Hull counted as phantom rival | major | refuted at HEAD | already fixed `(mh)` — `apr_hi` arm |
| F10 | scripts/audit_book_overlap.py | (duplicate of F9, from the WIRING reviewer) | minor | refuted at HEAD | already fixed `(mh)` — same evidence |
| F11 | lighter_book_douglas_bot.py | Held-coin re-append `.upper()`s venue symbols (kBONK → phantom KBONK) | minor | refuted at HEAD | already fixed `(mh)` — verbatim append |
| F12 | lighter_book_douglas_bot.py | Acted-dedup swallows a counted signal with no census bucket | minor | refuted at HEAD | already fixed `(mh)` — `repeat` bucket |
| F13 | lighter_book_grimes_bot.py | One-bet-per-coin refusal misfiled as `unpriceable` | minor | refuted at HEAD | already fixed `(mh)` — break after open |
| F14 | lighter_book_schwager_bot.py | Cap-blocked signals re-enter mid-bar at drifted marks | minor | refuted at HEAD | already fixed `(mh)` — acted-stamp on capped/unpriceable |
| F15 | lighter_book_schwager_bot.py | 3.5·atr ≥ 1 clamps long trail to 0, disabling both stops | minor | refuted at HEAD | already fixed `(mh)` — 0.9 entry refusal |
| F16 | lighter_book_hull_bot.py | fetch_premiums keys raw Lighter symbols; basis veto dark on 1000-markets | minor | refuted at HEAD | already fixed `(mh)` — `from_lighter` |
| F17 | .github/workflows/books-provision.yml | `railway status --json \| grep -q` SIGPIPE false-negative under pipefail | minor | refuted at HEAD | already fixed `(mi addendum)` — `e255b57`/`d1f78ad` |
| F18 | lighter_book_schwager_bot.py | 2× ATR initial stop superseded by the wider 3.5× trail after one 300s loop | major | **REFUTED** | mechanism does not exist |
| F19 | lighter_book_schwager_bot.py | Short-side ratchet selftest assertion vacuous (`x == min(s1, x)`) | minor | **REFUTED** | assertion does not exist |

Counts: 3 confirmed-and-fixed `(ml)` · 13 already fixed `(mh)` · 1 already
fixed `(mi addendum)` · 2 refuted outright. 19/19 adjudicated.

---

## 1 · CONFIRMED — three real defects, fixed the same session (`(ml)`)

### F1 · 📐 Grimes: stale/absent dtrend cache fails OPEN for keltner; cache not persisted (major)

**Verifier (isReal: true), condensed:** four legs, all confirmed against the
post-`(mh)` file. (1) Fail-open: `dtrend_cache={}` → `trend_at` returned 0,
and sig_keltner's conditions `dt <= 0` (short) / `dt >= 0` (long) BOTH pass at
dt=0 — an empty trend map removed keltner's regime filter rather than
disabling the setup, and the file's own selftest PROVED it (one line asserted
keltner fires with `{}` while another asserted refusal with a real up-trend
map). The stale-clear comment "setups needing it will simply not fire" was
true only for pullback. (2) Persistence gap: `build_state` omitted
dtrend_cache/dtrend_asof while restoring scorecard AND last_retest — so after
any routine restart the retest gate wouldn't refire for up to ~6h while
`setup_open` passed on the restored scorecard (24h TTL), and keltner opened
unfiltered fades under a gate whose trailing record graded the FILTERED rule.
The header records the unfiltered keltner fade as measured-refuted (**−$94**).
Reachable with zero failures — just a deploy/restart — conditional only on
keltner's gate being open (the book's designed operating state; born at
t=0.49 vs the 0.5 bar). (3) Per-coin replay leg: `deep_bars[coin]` assigned
BEFORE the 1d fetch, so a failed 1d fetch left the coin in the replay with no
deep_trend entry — the scorecard itself partially graded the unfiltered rule.
(4) TTL mismatch: 6h dtrend guard vs 24h SCORECARD_TTL_H — a 6–24h long-span
fetch outage left gates open with the filter gone.

**Fix (`(ml)`, in tree):** the defect is closed at the CONTRACT, not the call
sites. `trend_at` (lighter_book_grimes_bot.py:228–241) returns **None** for
no-claim (missing coin/day, junk, EMA warmup), and BOTH trend-gated setups
fail closed on it (`sig_pullback` :253, `sig_keltner` :287 — `if dt is None:
return None`) — one change kills every slice, live and replay alike, because
the signal functions are the one owner both call. The live entry site keeps
the `(mh)` `trend_dark` belt (:786, :812) with its own census key
(`trend_dark`, :856). The restart window is closed by NOT restoring
last_retest (:644–647 — a boot always re-runs the retest on its first loop).
The selftest that used to assert the defect now asserts its refusal; the
`(ml)` entry records 4 mutations verified red.

### F2 · 📐 Grimes: the replay gate's grader never bracket-tests the entry bar (minor)

**Verifier (isReal: true), condensed:** confirmed by direct code trace. In
`replay_setup` the manage pass for timestamp t ran BEFORE the entry drain, so
a position opened at bar i+1's open got its first h/l bracket comparison on
bar i+2 — the entry bar's post-open range was never tested against sl/tp. The
live loop diverges exactly there: it opens at mark during the forming bar and
`bracket_exit` runs every 300s from the next loop, so real entry-bar
stop-outs ARE realized live. Not an edge case: sl is 1.0–1.5×ATR while a 4h
bar's average range is ~1 ATR, and failtest (sl=1.0×ATR) enters fading a bar
that just pierced a 20-bar extreme. The bias is net-optimistic (a skipped
entry-bar stop resolves later at the sl price or better; the opposing
skipped-tp effect is smaller because tp sits 2.0–4.5×ATR away) and lands in
exactly the numbers the gate consumes (net>0 and t≥0.5 are bars; keltner sat
at **t=0.49 vs the 0.5 bar** at authoring — decision-flipping size, in the
direction that holds a losing setup's gate open longer). Inheritance
verified: `run_portfolio` in `scripts/study_books_cohort_2026-08-13.py` had
the identical manage-before-entries ordering, so the authoring evidence
shared the bias; the selftest's own fixture walked through the skipped window
and stayed green. Secondary, same direction: the entry bar was excluded from
the hold counter, so replay held one bar longer than live max_hold.

**Fix (`(ml)`, in tree):** `replay_setup` now bracket-tests the entry bar's
own post-open range, stop checked FIRST (the manage pass's own conservative
convention), and the entry bar counts toward the hold
(lighter_book_grimes_bot.py:302–313 docstring names this exact correction;
:375). The same fix is mirrored into `study_books_cohort`'s `run_portfolio`
(trend semantics too) so a re-run cannot resurrect the bias. Mutation-pinned
including the sign-flip fixture (:979 — a stop-spike entry bar on a tape that
then gaps to the tp books the STOP). Pre-correction recorded numbers carry a
small declared optimism; the bot's rolling 6h gate re-derives regardless —
the scorecard, not the study, is the authority.

### F3 · books-provision.yml: post-set variable dump can leak the resolved Postgres password (major)

**Verifier (isReal: true), condensed:** confirmed against the Railway CLI's
own source (railwayapp/cli). (1) Values are RENDERED: the no-flag path
queries `variablesForServiceDeployment` — references resolved, password
included; proven in-repo by fleet-watchdog.yml, which psql's the same
command's --json output. (2) The table WRAPS: `MAX_BOX_WIDTH=80`; with
RAILWAY_DOCKERFILE_PATH (23 chars) in the key column the value column is ~50
chars, and textwrap with break_words=true splits the ~70–100+ char URL
mid-token. Since `postgresql://postgres:` is 22 chars, line 1's
`sed 's/postgres[^ ]*/<redacted>/g'` covers only the first ~28 password
chars; the continuation line starts mid-password, doesn't begin with
"postgres", and prints raw. (3) No `::add-mask::`, password not a registered
secret; the echo ran unconditionally, once per service, 4× per dispatch. Four
sibling workflows discard this exact echo with comments naming DATABASE_URL
leakage — the `(kb)` rotation-incident credential class. Errata noted by the
verifier, immaterial: the resolved host is `postgres.railway.internal`, not
the maglev.proxy form in the reviewer's example.

**Fix + forensics (`(ml)`, in tree):** the echo is DELETED at commit
`ea36a3e` ("never echo variables back — railway variables prints RESOLVED
values and a wrapping table defeats line-based redaction"); the `--set` exit
code was always the real check; names only in logs (the db-backup rule). The
run-3 dispatch was cancelled mid-flight for this finding; run 4 provisioned
all four services green. **Forensic audit of every table the five runs
printed: verdict PARTIAL — zero password characters leaked.** The CLI
happened to wrap after `postgresql://`, putting the username `postgres` at
the start of the continuation line, so sed's match swallowed the whole
password; the only raw fragment was `es.railway.internal:5432/railway`,
Railway's universal private-network default. **No rotation** performed, logs
kept as evidence — but the non-leak depended on a lucky wrap point, hence the
deletion rather than a smarter redaction. The whole one-shot workflow was
subsequently removed at `9d89b04` (provisioning complete), so the file no
longer exists at HEAD.

---

## 2 · ALREADY FIXED BEFORE THE VERIFY STAGE — reviewers graded the pre-`(mh)` draft

Every finding below was verified isReal: **false** with the same shape of
reason: the claimed defect was real in the birth draft (`b290532`) and had
already been fixed by the `(mh)` birth-review commit `454efaf` (or, for F17,
the `(mi)`-addendum postmortems) before the verify stage read HEAD. For each,
the fix is confirmed present in the current tree, with the code evidence.

### F4 · 📐 Grimes: daily-trend map lacks the current UTC day (critical as claimed)
Reviewer claimed `out[b[0] // 86400]` keying: at 14:00 UTC the map's max key
would be yesterday, so ~5 of 6 live 4h bars read "no data" — unfiltering
keltner (dt=0 passes both conditions) and killing pullback, while the replay
graded day D's bars on day D's OWN close (look-ahead). **Verifier:** the code
keys `b[0] // 86400 + 1` — the LAG-1 convention — so the latest closed daily
bar writes key D = TODAY; live and replay run the same policy from one map,
and the look-ahead is gone (day D gated on day D−1's close). The `(mh)`
re-grade under the honest convention is what dropped keltner t=0.75 → 0.49
and closed the book's one open gate at birth.
**In tree:** `daily_trend_map` lighter_book_grimes_bot.py:216–222
(`out[b[0] // 86400 + 1]`, docstring names both dead defects); selftest pins
`last_bar_day + 1 in dmap` / `+ 2 not in dmap` + the one-day fallback (:1062).

### F5 · 🧙 Schwager: trail ratchets from 5-minute marks (critical as claimed)
Reviewer claimed `update_trail(pos, mark)` every 300s makes hwm the running
max of ~48 intrabar samples — systematically tighter than the measured +$457
cell, in the direction the study refuted (trail 2.5× on the same entries =
**−$29.88**). **Verifier:** the sole live call site passes the close of the
last CLOSED 4h bar (`_closed_bars`), guarded by `trail_bar_t` (each 4h bar
ratchets once) and `bt + BAR_SEC > opened_ts` (pre-entry bars never ratchet);
in the intra-bar-spike scenario hwm is unchanged, identical to
`run_portfolio`. Residual nit only: hwm seeds at the entry-time mark vs the
study's next-bar-open fill — a one-value entry-model difference.
**In tree:** lighter_book_schwager_bot.py:503–520, `((mh))` comment "THE
RATCHET FEEDS ON CLOSED 4h BARS, NEVER the 5-min mark".

### F6 · 🧘 Douglas: crypto screen after the top-18 truncation (major as claimed)
Reviewer claimed `scout_universe(..., limit=UNIVERSE_N)` truncated to the
venue's top 18 across ALL instrument classes BEFORE `crypto_only`, silently
shrinking the measured universe. **Verifier:** real in `b290532`, fixed in
`454efaf` — `resolve_universe` now calls `scout_universe` with NO limit,
screens `crypto_only`, THEN slices `[:UNIVERSE_N]`, with an in-code comment
documenting this precise defect.
**In tree:** lighter_book_douglas_bot.py:255–265 (`[(mh)] NO limit on the
scout read ... Screen first, then truncate`). The same fix pattern ships in
schwager (:270) — the `(mh)` entry names all three price books.

### F7 · 🧙 Schwager: EMA50 confirm on a 61-bar fetch, unconverged (major as claimed)
Reviewer claimed `need = max(DON_N+2, EMA_SLOW+5, ATR_N+2)+6` = 61 bars, so
the window-seeded EMA50 carries ~9% seed weight and flips the EMA20>EMA50
confirm after a large prior move — entries/exits the study never contained.
**Verifier:** the formula at HEAD is `max(DON_N + 2, EMA_SLOW * 3, ATR_N + 2)
+ 10` = **160 bars**; seed weight (49/51)^159 ≈ **0.2%**, tracking the
full-history EMA to basis points; the `((mh))` comment above it documents
exactly this defect with the reviewer's own remedy.
**In tree:** lighter_book_schwager_bot.py:547–550.

### F8 · 📐 Grimes: retest fetch un-paginated, "120d" silently ~83d (major as claimed)
Reviewer claimed one candles call for ~782 4h bars against a venue whose
pages are 500 bars, so the trailing-120d replay window was silently ~83d.
**Verifier:** both deep-history fetches go through `_paged_bars`, which pages
backward in ≤450-bar chunks (count_back ≤ 452, under the ~500-row page) for
up to 6 pages with timestamp dedup — its `((mh))` docstring names the
reviewer's exact scenario as the failure it was built to prevent. The only
direct candles call in the loop is the 200-bar signal scan, under page size.
**In tree:** `_paged_bars` lighter_book_grimes_bot.py:573 (docstring :574);
retest call sites :746, :751.

### F9/F10 · audit_book_overlap: no apr-ceiling arm, Hull a phantom rival (major + minor duplicate)
Two reviewers (hull, WIRING) independently claimed `admits()` tested only the
floor, so Hull — whose band is `[0.078, 0.20)` — would count as a rival for a
gate=0.20 proposal, the same `(gl)` phantom-rival class I20 warns about, on
the apr axis. **Verifier (both):** real at `b290532` (not an ancestor of
HEAD, verified with `git merge-base --is-ancestor`); fixed in the merged PR —
`living_gates` extracts `apr_hi` from top-level or caps, and `admits()`
returns "no" at `gate >= g["apr_hi"] - 1e-9`; Hull publishes `caps.apr_hi
= 0.20` (selftest-pinned) and traces to "books EXCLUDED by their own band or
bar (not rivals)" in the reviewer's own scenario.
**In tree:** scripts/audit_book_overlap.py:120–125 (`[(mh)] the apr CEILING`)
and :153–154; lighter_book_hull_bot.py `APR_HI` published in caps.

### F11 · 🧘 Douglas: held-coin re-append `.upper()`s venue symbols (minor as claimed)
Reviewer: `s = str(c).strip().upper()` on the held-coin append would inject a
phantom KBONK beside a real held kBONK (venues/symbol_map.py confirms
mixed-case fleet symbols kBONK/kSHIB/kPEPE), breaking the `(hk)` held-coin
contract. **Verifier:** accurate for the draft; fixed in `454efaf`.
**In tree:** lighter_book_douglas_bot.py:270 — `s = str(c).strip()  # ((mh))
venue symbols verbatim — no .upper()`. Same line ships in schwager (:285).

### F12 · 🧘 Douglas: acted-dedup swallows a counted signal with no bucket (minor as claimed)
Reviewer: "already traded" was byte-identical to "failed to act" in the
census. **Verifier:** the claimed missing bucket exists — the dedup path
counts a dedicated `repeat` bucket, the invariant signal = repeat + capped +
unpriceable + opened holds, and the bucket flows into the published
`extra.scan`. Residual cosmetic nit: `repeat` is lazily created, so
zero-repeat loops omit the key. The `(mh)` entry names it: "the acted-dedup
gets a `repeat` census rider".
**In tree:** lighter_book_douglas_bot.py:541.

### F13 · 📐 Grimes: one-bet-per-coin refusal misfiled as `unpriceable` (minor as claimed)
**Verifier:** unreachable at HEAD — after a successful `_open_position` the
SETUPS loop breaks, with an inline `((mh))` comment naming this exact misfile
as fixed; a second setup on the same coin never reaches `_open_position`.
Separate observability-only nit introduced by the fix (an OPEN log print
after the break, dead code) noted by the verifier — not the claimed defect.
**In tree:** lighter_book_grimes_bot.py:841 (`((mh)) one bet per coin`).

### F14 · 🧙 Schwager: cap-blocked signals re-enter mid-bar at drifted marks (minor as claimed)
Reviewer: a slot freeing 3h after a cap-blocked breakout would enter at a
2%-drifted mark — entries the study's sample never contained. **Verifier:**
`acted[coin] = sig_t` IS stamped on the cap-blocked path (comment citing sim
semantics — "a cap-bound signal is DROPPED, never retried at drifted marks")
and on the unpriceable path; on every later loop the same signal bar
short-circuits to the repeat bucket; only a new closed bar can enter, which
the study also treats as a fresh event. The restart variant fails too: acted
is persisted every loop and `load_state_required` crash-loops rather than
seeding fresh; the 5-day acted prune far exceeds the 4h bar life.
**In tree:** lighter_book_schwager_bot.py:577–579, :583 (`((mh)) sim
semantics`).

### F15 · 🧙 Schwager: 3.5·atr ≥ 1 clamps the long trail to 0, disabling both stops (minor as claimed)
Reviewer premise: "_open_position only requires atr > 0 with no upper bound",
so a wide-ATR coin's `hwm*(1 − 3.5a) ≤ 0` clamps trail_px to 0.0 and
dead-ends both stops until max_hold. **Verifier:** the premise is false at
HEAD — entry refuses `TRAIL_ATR*atr >= 0.9 or SL_ATR*atr >= 0.9` (refusal at
a ≥ 25.7% vs failure at a ≥ 28.6%, so every live position has trail_px ≥
0.1·hwm > 0); atr is frozen at entry (`pos["atr_frac"]`), so no post-entry
drift; refusal is selftest-pinned. The downstream mechanism the reviewer
described was accurate — the guard makes the precondition unreachable.
Provenance check for this doc: the guard is ABSENT in `b290532` (only
`atr <= 0`) and present in `454efaf` — the `(mh)` trail bullet names it ("an
ATR wide enough that `hwm·(1−3.5a) ≤ 0` clamped the long trail to zero"), so
this is an `(mh)` fix, not a never-existed defect; the verifier's
"born in a single commit with the guard already present" reflects the
squashed merge view.
**In tree:** lighter_book_schwager_bot.py:360–363; selftest :723–724
(`"((mh)) a 105%-wide trail is no stop — entry must refuse"`).

### F16 · 🧮 Hull: fetch_premiums keys raw Lighter symbols (minor as claimed)
Reviewer: prem_map keyed by raw `orderBookDetails` symbols ('1000PEPE')
while consumers join on fleet symbols ('kPEPE') — the basis veto silently
dark on every 1000-market, the exact `(gl)`-class silent-join failure.
**Verifier:** every symbol is mapped through `venues.symbol_map.from_lighter`
before keying, with an inline `[(mh)]` comment naming the raw-symbol defect
as corrected; the concrete scenario reproduces correctly (kPEPE at −15bps →
`basis_veto("short", -15.0)` refuses, census counts `adverse_basis`); the
except-fallback to raw keying is unreachable in a running container (venues
is a hard import).
**In tree:** lighter_book_hull_bot.py:446–451.

### F17 · books-provision.yml: `railway status --json | grep -q` SIGPIPE false-failure (minor as claimed)
Reviewer: under `set -o pipefail`, grep -q's early exit SIGPIPEs the CLI and
a successfully created service's provisioning is skipped. **Verifier:** the
pipeline does not exist at HEAD — the check captures output first
(`status_json="$(railway status --json 2>/dev/null || true)"`) then matches
with a pure-bash `case` substring: no pipe, no SIGPIPE surface; the cited
line is a comment documenting the bug as fixed. Git confirms the defect WAS
real and was fixed twice before HEAD: `e255b57` (run-1 postmortem — grep -q
SIGPIPEs the Rust CLI into a panic pipefail reads as no-match) and `d1f78ad`
(run-2 — printf's OWN broken-pipe write error inverts every successful
match). The generalized class, engraved in `(ml)`: **any producer piped into
`grep -q` under pipefail can invert a match.** Disposition: already fixed
pre-review (`(mi addendum)` commits, not `(mh)`); the workflow file itself
was deleted at `9d89b04` after run 4 provisioned all four services.

---

## 3 · REFUTED — the mechanism claimed does not exist, at any revision reviewed

### F18 · 🧙 Schwager: "the 2× ATR initial stop is superseded by the WIDER 3.5× trail after one 300s loop" (major as claimed)
**Verifier (isReal: false), kept in full force:** the central mechanism is
refuted by the code. The ratchet feeds ONLY on closed 4h bars and is gated by
`bt + BAR_SEC > opened_ts`; at every loop during the entry bar the last
closed bar is the SIGNAL bar, whose end ≤ opened_ts, so **no trail exists**
— the first trail seed is at the entry bar's close, ~4h post-entry, and until
then the fixed 2×ATR stop is checked against the live mark every 300s. The
reviewer's concrete scenario also misread the study: in `run_portfolio` a
position entered at B1's open is first managed at B2, so a dip "in the first
bar" exits NOWHERE in the study — the bot is strictly MORE protective there.
The sl-superseded-by-wider-trail handoff (stop_px = trail_px once seeded,
fixed stop never re-checked) is the study's own measured semantics,
replicated including exit-before-ratchet ordering, selftest-pinned. Genuine
residual: a one-bar offset in the handoff (bot seeds from B1's close at ~4h;
study from B2's close at ~8h) — a modest fidelity gap that cuts both ways
(the study leaves hours 0–4 completely unchecked), not "every fresh loser
loses ~75% more". The reviewer's proposed fix (seed trail at
max(chandelier, entry_sl_px)) would make the bot TIGHTER than the measured
cell — in the direction the study refuted (trail 2.5× = −$29.88).

### F19 · 🧙 Schwager: "short-side ratchet selftest assertion is vacuous" (minor as claimed)
**Verifier (isReal: false):** the claimed `x == min(s1, x)` form does not
exist — the short-side selftest asserts `ps["trail_px"] == s2`, exact
equality with the value captured immediately after the 90-mark update,
mirroring the long side's `== t2` pin; grep confirms no `min(s1, ...)`
anywhere in the file. A short-ratchet-loosening mutation (min→max) reddens
the suite at `assert s2 < s1`, so the docstring's mutation-verified claim
holds for shorts. **In tree:** lighter_book_schwager_bot.py:701–704.

---

## Provenance

- Result JSON: review workflow task output (`confirmed`: 3 full verdict
  objects; `all`: 19 findings with per-finding isReal + reason).
- Journal: one line per agent — 5 review returns (findings arrays: grimes 5,
  douglas 3, schwager 6, hull+overlap 2, wiring 3) + 19 verify returns
  (isReal + reason). 19 findings in, 19 verdicts out; nothing dropped.
- Fix commits: `454efaf` (`(mh)` birth review, merged in PR #169 `9386537`),
  `e255b57`/`d1f78ad` (`(mi addendum)` provisioner postmortems), `ea36a3e`
  (echo deletion), PR #170 `9d89b04` (`(mk)/(ml)` — grimes contract +
  entry-bar fidelity fixes, provisioner workflow deleted post-provision).
- All current-tree line citations in this doc were re-checked against HEAD
  (`89ed1f1`) on 14-Aug, the day of writing.
