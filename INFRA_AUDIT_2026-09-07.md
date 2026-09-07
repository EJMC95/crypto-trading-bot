# Infrastructure audit — Railway, Postgres, Notion
**2026-09-07 · read-only · nothing deployed, nothing mutated**

Companion to `SYSTEM_INVENTORY_2026-09-07.md` (what the fleet is),
`BASELINE_2026-09-07.md` (what it earns) and `AUDIT_PHASE3_4_2026-09-07.md`
(whether the evidence holds). This one asks a different question: **the fleet
runs on three platforms — is it using any of them properly?**

Every number below is measured today via the Railway API, the public
`/pnl.json` feed, the repo tree and the GitHub Actions API. Nothing is
inferred from documentation. Where I did not measure something, I say so.

**Scope note.** Under the audit's own constraints I made no Railway
mutation, set no variable, deployed nothing, and deliberately did **not**
fetch `DATABASE_URL` (see §2.5). Every action below is a proposal with its
exact command, for Eamon to run or approve.

---

## 1 · Railway

### 1.1 What is provisioned vs what actually works

Project **Trading Bots** (`9b3b7d3c…`), environment `production`, **27 services**.

The `svc` stamp on every row of `/pnl.json` says which container publishes it
— so the map from service to output is measurable, not guessed:

| Doing work | Count | Services |
|---|---|---|
| **Publishing a live book** | **10** | `freqtrade-bots` (4 books + every organ), `family-lighter-shadow` (4 books), `mum-live`, `tide-rider-lighter-live` (= 🙏 avo LIVE), `band-kelly-shadow`, `book-hull-shadow`, `book-kiyosaki-shadow`, `perp-sniper-shadow`, `counterweight-shadow`, `yield-harvester-shadow` |
| **Infrastructure** | **3** | `Postgres`, `pnl-dashboard`, `market-context` |
| **Correctly stopped (0 CPU, 0 RAM)** | **4** | `freqtrade-dad`, `freqtrade-mum`, `freqtrade-avo-maria`, `freqtrade-georgia` |
| **Running and publishing nothing** | **10** | see below |

**16 books are served by 10 containers.** Ten more containers are
provisioned, consuming RAM continuously, and produce no row anyone reads.

### 1.2 The ten idle containers — measured, 7-day averages

| Service | Retired | avg vCPU | avg RAM | Behaviour |
|---|---|---|---|---|
| `trail-blazer-live` | 22-Aug (ta) | **0.006802** | 98.3 MB | **full loop** — see §1.3 |
| `funding-farmer-shadow` | 2-Sep (wt) | 0.000092 | 78.9 MB | loops, publishes nothing |
| `band-garrett-shadow` | 2-Sep (wt) | 0.000092 | 77.3 MB | loops, publishes nothing |
| `funding-carry` | dead dup 31-Jul (hu) | 0.000072 | 69.8 MB | loops, stood down by `claim_writer` |
| `nav-cook-shadow` | 2-Sep (wt) | 0.000313 | 41.3 MB | loops, publishes nothing |
| `book-douglas-shadow` | 2-Sep (wt) | 0.000082 | 34.1 MB | loops, publishes nothing |
| `book-grimes-shadow` | 2-Sep (wt) | 0.000121 | 33.7 MB | loops, publishes nothing |
| `equities-regime-shadow` | 13-Aug (lo) | 0.0000049 | 17.6 MB | idle-sleep — guard bites at boot |
| `band-barnes-shadow` | 17-Aug (pm) | 0.0000049 | 16.0 MB | idle-sleep — guard bites at boot |
| `book-schwager-shadow` | 17-Aug (po) | 0.0000039 | 15.1 MB | idle-sleep — guard bites at boot |

**Total: ~482 MB resident, continuously, for zero output.**

**There are two clearly different tiers here, and the difference is a real
finding, not noise.** The three at ~15–18 MB are the older retirements
(13/17-Aug): their guard idles the process **before** the heavy imports, so
the container costs almost nothing — this is the retirement guard working
exactly as `(if)`/`(po)` designed it. The six at ~34–79 MB are the September
slate plus `funding-carry`: they import the whole module and keep looping,
with the guard biting further in. Both are *correct* by the retirement
doctrine (never `sys.exit`, because `restartPolicy=always` turns an exit into
a crash-loop) — but they cost 2–5× more, and the doctrine never said the
container had to stay provisioned once the guard is in main.

**The distinction that matters:** the code guard is the durable half and must
stay. Deleting the *service* is pure tidiness on nine of these ten. It is not
tidiness on the tenth.

### 1.3 `trail-blazer-live` — four sources disagree about what it runs

This is the finding I did not expect, and the only item here I would call
urgent-ish rather than merely worthwhile. It is not really a cost problem.

`trail-blazer-live` is the service `CLAUDE.md` calls *"the Farmer; service
names lie"*. It has changed hands twice — 💸 Farmer → 🔮 georgia at `(ta)`/`(tb)`
— and georgia's live arm then retired at `(wg)` on 2-Sep, her sub-account
drained to mum. **Four sources now say four different things about it:**

| Source | Says `trail-blazer-live` runs… |
|---|---|
| `railway-redeploy.yml:544` | `-> live-georgia marker: including trail-blazer-live (REAL MONEY, runs georgia)` |
| `scripts/deploy_live_verify.py:74` | `("freqtrade-georgia-lighter", "[deploy-live-georgia]")` |
| `scripts/fleet_books.DECLARED_LIVE` | **georgia is not live at all** — `('freqtrade-avo-maria-lighter', 'freqtrade-mum-lighter')` |
| **The container's own log, today** | `[avo-live] … equity 0.01 open 0/5 closed 77 (36W/41L) clip=$0.01 locked=no` |

The container is configured as **🙏 avo** — a second instance of a book whose
real arm publishes from `tide-rider-lighter-live` (`closed_trades 14`, open 3,
against this one's `closed 77`).

Measured, so the shape is not in doubt:

1. **It is actively deployed on the real-money path.** Deployments 2-Sep,
   3-Sep, 4-Sep and again **2026-09-07T03:05:26Z SUCCESS**. It takes every
   `[deploy-live-georgia]` and every `[deploy-live]` push.
2. **It is doing full work.** 0.006802 avg vCPU over 7 days — the second
   highest in the project after `freqtrade-bots`, and 22× to 1,700× the
   retired shadows. It loops every 5 minutes.
3. **Nothing watches it.** It publishes no row among `/pnl.json`'s 16, so it
   is invisible to the dashboard, `fleet-watchdog.yml` and the pager.
4. **Its account is drained.** Equity $0.01, so `clip = equity × gross_x /
   max_open` derives a **$0.01 clip**; any order would be dust-rejected.

**Why this matters more than 98 MB.** Point 4 is why this is not an incident
today — and it is an *accident*, not a guard. The two things standing between
this and a live duplicate of 🙏 avo are an empty account (which a deposit
reverses) and `claim_writer`, which is **fail-OPEN by design** — a dark DB
never idles a book. Meanwhile it is the exact composite of three shapes this
repo has already paid for: `(hp)` one-book-one-writer, where two containers on
one row make `n` a mixture of two books; `(I13)`, inverted — a *live* loop
whose liveness nothing observes from outside; and the mechanism `CLAUDE.md`
names outright, *"an audit-scope rule keyed to a LIST goes stale on every slot
swap, and a stale one sends every future audit to the wrong file."* This is
the fourth slot swap, and the routing did not follow.

**Note what did and did not catch it.** `audit_live_roster.py` compares
`DECLARED_LIVE` against the feed and is green — correctly, because the *books*
are declared right. Nothing compares **service → book routing** against either
the roster or the container, which is where all three stale references sit. A
guard that reads `deploy_live_verify.LIVE_SERVICES` and
`railway-redeploy.yml`'s echo strings against `DECLARED_LIVE` would fail today
and would have failed on 2-Sep.

**What I have NOT established, stated plainly:** whether it still holds valid
API keys. I did not read its variables (§2.5), so I cannot say whether this is
a live-keyed duplicate or 98 MB of inert waste. That is a thirty-second check
Eamon can do and I cannot.

**Proposed, not executed:**
```bash
# 1. what is it configured as? (names only, never values)
railway variables --service trail-blazer-live --kv | cut -d= -f1
#    then read FAMILY_LIVE_BOOK / VENUE specifically, one key at a time

# 2. if it holds live keys and is not wanted: remove them first, then
railway down --service trail-blazer-live
#    durable half is a code guard — a push resurrects a stopped service
#    ([[railway-autodeploy-resurrects-stopped-services]])

# 3. either way, correct the three stale references:
#    railway-redeploy.yml:544, deploy_live_verify.py:74, and the
#    [deploy-live-georgia] marker itself (georgia has no live arm)
```

### 1.4 `funding-carry` — 38 days as a known dead duplicate

Identified 31-Jul at `(hu)`: *"`yield-harvester-shadow` runs the book;
`funding-carry` is the dead service."* It has been running ever since —
69.8 MB, still looping, stood down each cycle by `claim_writer`.

The doctrine calls stopping it "optional tidiness, not an outstanding
action", and on 4-Aug that was right: the two were framed as a deliberate
failover pair. Five weeks on I would re-read it, because **`claim_writer` is
fail-OPEN by design** — on a dark or slow Postgres it does not idle a book.
So the single event that most plausibly breaks the fleet (a DB outage) is
also the event that un-silences the duplicate writer, on 🌾 carry, which is
the fleet's best-evidenced book (n=121, LB 0.147%/trade) and the one whose
`n` a mixture would destroy.

That is not a prediction that it will happen. It is the observation that the
failover pair's safety depends on the DB being up, and its whole purpose is
to survive things being down.

### 1.5 What Railway can do that the fleet is not using

Ranked by what each one *closes*, not by novelty. The first three each shut a
class this repo has demonstrably paid for.

**(a) The Deployments API as the deploy receipt — closes `(ml)`.**
`(ml)` measured a green `OK: 'pnl-dashboard' deployed` while the new
deployment sat `stopped, instances []` and a 14-hour-old container kept
serving; four fresh book rows vanished and an hour went into hunting healthy
bots. The current receipt is the `extra.build` stamp on `/pnl.json`, which is
excellent but **lags by a publish cycle and cannot distinguish "not deployed
yet" from "deployed and not serving"**. `list-deployments` answers it
directly — status, `createdAt`, and which deployment is `SUCCESS` vs
`REMOVED`. Worked example from today: `mum-live` shows `SUCCESS
2026-09-07T03:06:31Z` with the prior four `REMOVED`, which is exactly what a
clean rollover looks like. Wire it as a post-deploy step in
`railway-redeploy.yml`: assert the newest deployment is `SUCCESS` **and** that
no older deployment is still active, then fall through to the existing stamp
check. Belt and braces, and the belt is the faster one.

**(b) The Logs API — the fleet's most under-used diagnostic.**
`railway-logs.yml` exists but is `workflow_dispatch`-only, so a human has to
remember it. Two of the fleet's most expensive bugs were found by reading
container logs by hand: the `bot_state_history` retention that *"had never
once succeeded and said so in the logs every boot while nobody read them"*
(fixed 2-Aug), and the `(ml)` stale reader. Both are the `(I4)` shape — a
persistent condition reported by a one-shot warning. **A nightly grep of every
service's logs for `_warn_once` output, `Traceback`, `failed`, `refused` and
`prune failed`, opening one GitHub issue on a transition, would have caught
both within a day.** That is one workflow, and it is the single highest-value
item in this section.

**(c) Container metrics as a liveness signal the watchdog does not have.**
`fleet-watchdog.yml` probes `/pnl.json` — **payload** liveness. That is the
right primary signal and `I1` is built on it. But it is blind to a container
that is OOM-restarting, wedged, or (as here) running while publishing
nothing. Today's measurement is the proof: **ten running containers are
invisible to the watchdog because it only looks at rows.** `freqtrade-bots`
is the case to watch — avg RAM 263 MB against a **max of 1,354 MB**, a 5.1×
spike (the heavy-job window). Nothing currently alerts if that spike ever
meets a memory limit. A weekly metrics sweep asserting (i) every service in a
declared roster is publishing, and (ii) no service's max RAM is within 20% of
its limit, closes both.

**(d) The unused second environment.** The project carries an environment
literally named `"Trades "` (with a trailing space) that holds nothing. Railway
environments are the natural home for a **staging deploy of `freqtrade-bots`**
— the shared image every organ ships inside, where `audit_image_imports`
already guards the born-dark class statically but nothing exercises the image
before it reaches 4 live books and every organ. Cheap, isolated, and it would
have caught `(fd)`-class file-set surprises before production.

**(e) Volumes.** `freqtrade-bots` carries 203 MB of disk (the Parliament
SQLite DB at `/freqtrade/persist/parliament.db`, plus durable state).
`db-backup.yml` covers **Postgres only** — the volume is not backed up
anywhere. That is a real single point of loss for the Parliament's ecosystem
DB and every bot's restored-position map. `railway-volume.yml` exists; a
nightly `tar` of the persist volume into a GitHub artifact would mirror what
`db-backup.yml` already does for Postgres.

**(f) Things I checked and would NOT change.**
Private networking is already correct — the `DATABASE_URL=${{Postgres.DATABASE_URL}}`
reference form is in place fleet-wide since `(kb)`, which is exactly right and
was hard-won. `restartPolicy=always` is correct and is load-bearing for the
retirement guards. Horizontal replicas would be actively harmful here: every
bot is a single-writer loop and a second replica *is* the `(hp)` two-writer
defect.

### 1.6 Railway — ranked recommendation

| # | Action | Closes | Effort | Risk |
|---|---|---|---|---|
| 1 | Establish what `trail-blazer-live` is and whether it holds keys | a live-keyed, unobserved, actively-deployed duplicate | 5 min, Eamon | — |
| 1b | Correct the 3 stale service→book references, + a guard that reads them against `DECLARED_LIVE` | the routing rot that survived 4 slot swaps | ~1 h | none |
| 2 | Nightly log sweep → one GitHub issue on transition | `(I4)` silent persistent warnings; found 2 major bugs by hand | 1 workflow | none (read-only) |
| 3 | Deployment-status assert in `railway-redeploy.yml` | `(ml)` green-run-stale-container | ~20 lines | none |
| 4 | Delete the 9 tidy-only retired services (keep every code guard) | ~384 MB + noise in every service list | 10 min | low — a push resurrects, guard idles |
| 5 | Weekly metrics sweep (roster publishes? RAM near limit?) | container-level liveness the watchdog lacks | 1 workflow | none |
| 6 | Back up the `freqtrade-bots` persist volume | Parliament DB has no backup at all | 1 workflow | none |
| 7 | Use the empty environment as `freqtrade-bots` staging | image-level defects reaching 4 books + all organs | ~1 h | none |

---

## 2 · Postgres

### 2.1 What is actually there

Seven tables, from `bot_pnl_store.py`:

| Table | Key / index | Retention | Role |
|---|---|---|---|
| `bot_pnl` | PK `bot` | — (one row per book) | the dashboard feed |
| `bot_state` | key | — | the organ bus |
| `bot_state_history` | idx `(key, ts)` | **60 d**, pruned every 200th write + at boot | the replay tape, MTM equity series, brain memory |
| `paper_trades` | PK `(bot, trade_id)` | **none** (correct — it is the ledger) | **every grade in the fleet** |
| `bot_trades`, `bot_trade_analysis` | — | — | freqtrade-era |
| `venue_orders` | idx `(bot, at)` | none | real fills |

### 2.2 Measured: disk is growing, and it should stop

Postgres over 7 days: **660.4 MB → 768.5 MB = 15.4 MB/day.** CPU 0.010 avg
(peak 0.145), RAM 0.60 GB avg (peak 0.83).

This is **expected and about to plateau**, and the arithmetic is worth having
written down rather than rediscovered as a scare. `bot_state_history` began
accumulating 16-Jul. Its retention DELETE was broken from the start —
`make_interval(days => numeric)` raised on every call — and was fixed 2-Aug.
But the prune deletes rows *older than 60 days*, and on 2-Aug nothing was.
**The first real deletions land ~14-Sep**, after which the table holds a
rolling 60 days and stops growing. Projection: **~876 MB around 14-Sep, then
flat**, modulo genuine growth in `paper_trades` and `venue_orders`, which
have no retention because they are the record.

**Worth a look on 15-Sep**: if disk keeps climbing past ~900 MB, the prune is
not doing its job and that is the `(I4)` shape again. I have not added a
tripwire for this because I cannot query the DB (§2.5); it belongs in the
metrics sweep of §1.5(c).

### 2.3 Two schema gaps, one of which closes a class

**(a) `paper_trades` has no index on `closed_at`.**
The PK is `(bot, trade_id)`. Every grading path in the fleet —
`golive_readiness`, `edge_audit`, `winners_docket`, `ceiling`,
`fleet_allocation`, and all 110 study scripts — filters
`WHERE bot = ? AND closed_at >= <era>` and sorts by `closed_at`. The PK
prefix covers `bot`; `closed_at` is then a scan-and-sort. At 4,311 rows this
costs nothing today, which is precisely why it should be added *now* rather
than when it hurts:
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS paper_trades_bot_closed
  ON paper_trades (bot, closed_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS paper_trades_closed
  ON paper_trades (closed_at);
```
`CONCURRENTLY` takes no write lock, so this is safe against a live fleet.
Caveat worth stating: `closed_at` is **TEXT**, not `timestamptz`. The index
still works (ISO-8601 sorts lexically) but a migration to `timestamptz`
would be better and is not free — it is a separate, larger job.

**(b) The primary key gives false assurance about ledger integrity, and a
constraint could close the two-writer class outright.**

This is the more interesting one. `(hf)` measured it exactly: a duplicate-
`trade_id` scan is **blind to duplicate writers by construction**, because
`trade_id = {coin}:{opened_ts}` and two processes open at different moments,
so their ids never collide. The PK therefore enforces something real but not
the thing that matters. What catches it today is
`scripts/audit_ledger_integrity.py` plus a pager — i.e. **detection after the
damage**, and as the doctrine says, *"a guard cannot un-pool closes two
processes already wrote."*

Postgres can make it structurally impossible:
```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE paper_trades ADD CONSTRAINT paper_trades_no_same_pair_overlap
  EXCLUDE USING gist (
    bot WITH =, pair WITH =,
    tstzrange(opened_at::timestamptz, closed_at::timestamptz) WITH &&
  );
```
A same-pair overlapping hold then **cannot be inserted** — the second writer's
row is rejected at the database, and the ledger stays one book's record by
construction rather than by vigilance. That is the "a fix closes a class or it
is not finished" move, in the one place that can enforce it globally.

**Three caveats, because this touches the ledger and I would not ship it
casually.** (i) The historical rows would have to pass — `(hf)` found 7
overlaps on 🌾 carry and a naming collision on the retired spot sniper, so
the constraint needs `NOT VALID` first, or those rows quarantined. (ii) The
TEXT→timestamptz cast must be immutable for the index, which means a
generated column. (iii) A legitimate design that holds two positions in one
pair would be blocked — no living book does, but that is a design constraint
being made permanent and Eamon should say yes to it deliberately.

### 2.4 What Postgres could do that it is not

**(a) A materialised view for the grade.** `golive_readiness` recomputes six
bars per book from raw rows, and roughly a dozen consumers each recompute
their own copy of the era filter. A `MATERIALIZED VIEW` refreshed on the
6-hourly publish would make the grader's own output queryable. **I would rank
this LOW despite the obvious appeal** — `(hj)` is explicit that *"a second
copy of a rule is a second rule"*, and a view is exactly that unless the
publisher owns and refreshes it. Worth it only if `golive_readiness` writes
the view itself.

**(b) `pg_stat_statements`.** Nothing in the fleet knows which query is slow.
One extension, zero code, and it turns "the dashboard feels sluggish" into a
number.

**(c) A GIN index on `paper_trades.extra`.** The era machinery reads
`extra.policy` on every row of every grade, and the brain reads `extra.tag`.
`CREATE INDEX ... USING gin (extra jsonb_path_ops)` is the standard fit.
Measure first — at 4,311 rows a sequential scan may well win.

**(d) Backups are healthy — but the restore has never been tested.**
`db-backup.yml` has **58 runs and the last 8 are all `success`**, nightly at
18:07 UTC. That is genuinely good and better than most. The gap is the
classic one, and it is this repo's own doctrine pointed at itself: *a check
that inspects nothing reports clean*. A successful `pg_dump` proves the dump
ran, not that it restores. **One quarterly job that spins a scratch Postgres,
`pg_restore`s the newest artifact and asserts row counts within tolerance**
would convert an untested assumption into a receipt. Note also the artifact
retention is **30 days** — beyond that there is no copy at all.

### 2.5 The credential question — why I stopped short, and what I would need

**I did not fetch `DATABASE_URL`, and I recommend I keep not doing so.**
`CLAUDE.md` records the measurement: the Railway CLI prints **resolved**
values, so the reference form `${{Postgres.DATABASE_URL}}` renders as the
full URL including the password, in a boxed table that **wraps**, and no
line-based redaction survives a wrap — `(ml)` found the wave-2 provisioner
leaked zero characters only by luck of column width. Eamon's own constraint
for this audit says *do not expose API keys, exchange secrets or wallet
credentials*. So: no.

**But the absence of DB access is the single biggest limit on this audit, and
it is worth naming what it cost.** Every one of these hit the same wall:

| Blocked | Why | Where it is recorded |
|---|---|---|
| The open-interest test | `oi_ntl` history lives in `bot_state['market-context']`, DB-side; the bus exposes only a **level**. The study correctly REFUSED | CARRIED `oi-history-is-not-reachable` |
| MTM drawdown analysis | `bot_state_history['<bot>:equity']` — the I9 series — is readable by the grader and by nothing else | `FLEET_BETA_2026-09-07.md` |
| Full-depth ledger | `/trades.json?limit=` **caps at 5000**, and a count equal to the cap is a truncation `(qz)` | `edge_audit` reads through that cap |
| Brain memory over time | `learning-brain` history is DB-only | — |
| Disk-growth tripwire | cannot count rows per table | §2.2 |

**The clean unlock, in preference order:**

1. **A read-only role plus a TCP proxy.** One `CREATE ROLE lucy_ro LOGIN
   PASSWORD '…'; GRANT CONNECT, USAGE, SELECT ON ALL TABLES` — a role that
   *cannot write*, so the "do not overwrite live files" constraint is enforced
   by the database rather than by my restraint. Eamon creates it, sets it as a
   distinct secret, and I never see the fleet's real credential. **This is the
   one I would ask for.**
2. **Widen the read-only HTTP surface.** Add `/history.json?key=&hours=` to
   the dashboard, serving `bot_state_history` the way `/bus.json` already
   serves `bot_state`. No credential moves at all, it fits the existing
   no-auth read-only endpoint pattern, and it alone unblocks the OI test.
   **Lowest risk of the three, and the most in keeping with how the fleet is
   already built.**
3. **A nightly export job.** A GitHub Action dumping the four analysis tables
   to a private artifact. Works, but adds a staleness axis and a second copy
   of the data, which is how ledgers diverge.

### 2.6 Postgres — ranked recommendation

| # | Action | Effort | Risk |
|---|---|---|---|
| 1 | `/history.json` read-only endpoint (or a read-only role) | ~40 lines | none — read-only |
| 2 | `CREATE INDEX CONCURRENTLY` on `(bot, closed_at)` and `(closed_at)` | 2 statements | none — no write lock |
| 3 | Quarterly restore test of the newest `db-backup` artifact | 1 workflow | none — scratch DB |
| 4 | Check disk on 15-Sep against the ~876 MB plateau projection | 1 min | — |
| 5 | `pg_stat_statements` | 1 statement | none |
| 6 | EXCLUDE constraint closing the two-writer class | ~1 h + backfill | **medium** — touches the ledger; needs the 3 caveats settled first |
| 7 | GIN on `extra`; `closed_at` → `timestamptz` | measure first | low / medium |

---

## 3 · Notion

### 3.1 Measured: the shared brain is too big to load

Hub `38f2849b-b52c-8161-bb19-f4d5f712f7de`:

- **87,670 characters total**
- **"🧵 Recent thread" is 85,901 of them — 98%**
- **34 entries**, against the `~8` the loading contract itself specifies
- **The fetch exceeded the tool's token limit twice in this session**

That last line is the one that matters. The standing instruction is to fetch
the hub on the first message of any chat and read "Recent thread" +
"Current focus". **That contract is currently failing** — not degrading,
failing — on every surface: Code, Cowork and the app. The brain that exists
to stop us doing circles is the thing that cannot be loaded.

**And nothing durable is at stake in fixing it.** The Session Log database
(`a6ab3301…`) independently holds **40 rows back to 2026-06-30** — a longer,
better-structured history than the prose block duplicates. Trimming Recent
thread loses no history; it only stops the hub carrying two copies of the
same record, one of which is unbounded.

### 3.2 Two ways to fix it

**Option A — trim to 8, once.** Duplicate the hub as a dated archive (a full-
fidelity backup, no reading required, nothing lost), then cut Recent thread to
the newest 8 with a link to the archive. Ten minutes. **It fixes the symptom
and the block starts growing again the same day** — this is the "fix the
instance, leave the class open" pattern, which is the definition of a circle.

**Option B — make it structurally impossible.** Recent thread becomes a
**linked view of the Session Log database**, filtered to the 8 most recent
and sorted newest-first, and the prose block goes. Then:

- appending a session log row *is* updating the thread — one write, not two;
- the block **cannot grow**, because a view of 8 rows is always 8 rows;
- the history stays complete and queryable in the database, where it already is;
- the hub returns to ~2 KB and loads instantly on every surface.

**I recommend B**, for the reason this fleet already decided: a rule that
depends on someone remembering to keep a list at ~8 is the same shape as a
doctrine with no enforcement. A filtered view enforces it mechanically.
A is the fallback if the view proves awkward.

### 3.3 Why I have not done it

I stopped at the diagnosis on purpose. The hub is a live shared artefact you
use across three surfaces, the change removes ~26 entries of your own context
from where you read it, and one of this audit's own constraints is *do not
overwrite live files*. That is squarely the confirm-first category.

**Say the word and I will do it** — Option B, in this order, so nothing is
ever at risk: duplicate the hub to `Claude Context Hub — archive 2026-09-07`
first (purely additive), verify the copy, then swap the block for the view.
Reversible at every step.

---

## 4 · What connects today, and what would add options

Eamon's standing ask — capabilities, and what would unlock more.

**Connected and load-bearing:** GitHub (PRs, Actions, CodeQL), Railway
(read-only in this session — projects, services, variables, metrics, logs,
deployments), Notion (the shared brain), plus Gmail, Calendar, Drive,
Dropbox, Slack, Todoist, Figma, Docusign, Shopify, Vercel, Zapier, FMP, IBKR,
Zoom, Read AI, Embat.

**Underused, in order of what they would buy this fleet:**

1. **Railway logs + deployments** — connected, barely used. §1.5(a)(b). No new
   connector needed; this is a workflow, not an integration.
2. **Postgres read path** — §2.5. The single biggest analytical unlock, and
   the option I prefer needs no connector at all, just a `/history.json`
   endpoint on the dashboard you already run.
3. **FMP** — connected and unused by the fleet. Item 18 (the regime caveat)
   says Lighter's whole 438-day tape is one falling-BTC regime and the venue's
   ~41 non-crypto books are the only on-venue escape. FMP is off-venue, so it
   cannot supply *evidence* under the Lighter-only backtest rule — but it can
   supply **regime context** (a real equity/commodity index for the oracle,
   rather than one chained from the scout's own marks). That distinction is
   worth keeping sharp: context, never a backtest.
4. **IBKR** — connected. The stocks side of your fleet (`ikbr-stock-bot`,
   `ibgateway` at 697 MB, ~10× any trading bot) is entirely outside this
   repo's instruments. Nothing grades it, nothing publishes it to
   `/pnl.json`, and the survivorship and multiplicity findings in
   `AUDIT_PHASE3_4` do not cover it. **That is the largest un-audited surface
   you have**, and it is a separate piece of work rather than a connector gap.
5. **Slack** — not used by the fleet. The pager currently goes to phone push
   via the organs. A `#fleet-alerts` channel would give alerts a *history* —
   right now a push that arrives while you are asleep leaves no searchable
   record, which is how a 12.5-hour dark window `(I13)` goes unnoticed.

**What I would NOT add.** More connectors is not the constraint. Every gap
above is either a workflow you already have the tools for, or one read-only
endpoint. Adding integrations to a system whose measured problem is *too many
provisioned things doing nothing* would be the wrong direction.

---

## 5 · If you do three things

1. **Find out what `trail-blazer-live` is.** Four sources disagree about what
   it runs — the deploy workflow and the verifier both say a retired book, the
   roster says that book is not live, and the container itself logs `[avo-live]`
   on a drained account. Probably harmless today ($0.01 clip); worth thirty
   seconds of certainty, and the routing needs correcting either way.
2. **Nightly Railway log sweep → one GitHub issue.** Two of the fleet's most
   expensive bugs sat in logs nobody read. This is one workflow.
3. **Give me a read path to Postgres** — `/history.json` is enough, and needs
   no credential to move. It unblocks the OI test, the MTM series, the
   full-depth ledger and the disk tripwire, all of which this audit had to
   record as CARRIED rather than answer.

Then Notion Option B, whenever you want it.

---

*Read-only audit. No Railway mutation, no variable read, no deployment, no
Notion write. Every recommendation above is a proposal with its command.*
