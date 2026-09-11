# Expansion Research Log

Weekly deep-work slot: ONE hypothesis per run, measured to a verdict on
Lighter's own tape. A REFUTATION WITH NUMBERS is a first-class output — the
point of this file is that no idea gets tested twice.

Format per entry: hypothesis · method · numbers · verdict · next thread.

---

## 2026-08-13 (Thu, Sydney) — 🎸 BARNESY'S SLEEVE STRUCTURE: one sleeve has been DEAD SINCE BIRTH by construction, and the one that fires is 8-for-8 on instruments its own parent screens out

**First run of this slot** (the task was rewritten 4-Aug; no prior log existed).

### Why this hypothesis

🎸 Barnesy (`band-barnes-lshadow`, born 5-Aug, operator: *"yes build the super
bot"*) is the fleet's newest and largest build and its only three-sleeve book.
It publishes ONE pooled number — n=43, mean −0.246%/trade, t=−1.24, win 16.3% —
and nothing in the fleet had yet graded its sleeves separately. That pooling is
the whole problem: the book's premise is that each sleeve is a conservative
re-expression of a *different* parent's validated gates, so a pooled negative
says "the super-book loses" and hides which mechanism failed. The book is
BIRTH-FROZEN until 2026-09-04, which is the date the operator will make config
decisions — so evidence produced now is evidence that decision can use, and
evidence produced in September is three weeks late.

Highest EV of information available: an unmeasured claim blocking a scheduled
decision (category (a)), on the book with the most invested build effort.

### Method

- Ledger: `paper_trades` for `band-barnes-lshadow` (48 closes at time of run),
  split by `extra.sleeve` and by the `<side>-<sleeve>_<exit>` tag.
- Venue tape: the scout's own `bot_state_history['lighter-market']` snapshots
  — **8,610 snapshots, 14-Jul → 13-Aug**, of which 2,354 fall in Barnesy's
  life. These are the same venue read the book gates on, so this is a replay
  of the actual decision input rather than a reconstruction.
- Gate replay mirrors `harvest_candidates` + the loop's `hot_since`
  bookkeeping EXACTLY, including the 6-hour continuous persistence clock.
- Instrument class from the venue's own `classes` map ((kj)):
  `2=crypto 3=commodities 4=FX 5=US equities 6=Asian equities 7=pre-IPO`.
- Code read against `origin/main` tip (verified byte-identical to the local
  copy), *after* discovering that origin had moved 11 commits ahead of the
  local HEAD during the run.

**One methodological correction made mid-run, recorded because it changes the
answer:** the first pass counted only 2 of the 3 gates (|apr| and volume) and
reported the extreme sleeve's gate as reachable in 50.13% of snapshots. That
was wrong — it omitted the 6h persistence clock, which is the gate that
actually bites on spiky funding. The full 3-gate replay is what is reported
below. A 2-of-3 gate replay is not a gate replay.

---

### FINDING 1 — the `extreme` sleeve is STRUCTURALLY UNREACHABLE, and has been since birth

`extreme` has **0 opens and 0 closes in 8 days**; the row publishes
`sleeves.extreme = {cap: 4, pnl: 0, open: 0}`. That payload is byte-identical
to "the venue is quiet, it will fire later" — which is the (I1) shape: the
number that distinguishes a starved sleeve from an unreachable one is not in
the book's own output.

It is unreachable **by construction**, and the proof is a subset relation, not
a statistic:

| | carry sleeve | extreme sleeve |
|---|---|---|
| apr bar | `ENTER_APR` 0.20 TRUE | **the same `ENTER_APR`** |
| persistence | `PERSIST_H` 6h | **the same clock** |
| ranking | `sort(-abs(apr))` | **the same ranking** |
| volume floor | $2M | **$10M — 5× stricter** |
| runs | **FIRST** | second |
| held-set | `held_harvest` — **shared**, carry adds each coin it opens | same set |

So extreme's candidate set is a strict subset of carry's, drawn from an
identical ranking, *after* carry has claimed from it — and carry's capacity
(`MAX_POSITIONS` = 4) exceeds the entire qualified supply at essentially every
instant. Modelling the real loop order over the tape:

```
BARNESY'S LIFE (5-Aug → 13-Aug, 2,354 snapshots)
  carry supply non-empty          : 1279  (54.31%)   max simultaneous = 3
  extreme supply non-empty (raw)  :  302  (12.82%)   max simultaneous = 2
  carry sitting AT its cap of 4   :    0  ( 0.00%)
  >>> extreme offered anything carry did not already hold:  0  (0.000%)

FULL SCOUT TAPE (14-Jul → 13-Aug, 8,611 snapshots)
  carry supply non-empty          : 1617  (18.78%)   max simultaneous = 5
  extreme supply non-empty (raw)  :  564  ( 6.55%)   max simultaneous = 3
  carry sitting AT its cap of 4   :   54  ( 0.63%)
  >>> extreme offered anything carry did not already hold:  0  (0.000%)
```

**Zero of 8,611 snapshots over 30 days.** Carry never reached its cap at all
during Barnesy's life. The modelling assumption is generous to extreme: carry
is modelled as holding a coin while it stays in supply, and if carry instead
*exits* a still-qualifying coin it simply re-enters it next loop as the hottest
name — extreme still never sees it.

This is an **I18 case in its purest form**: the constraint binding a whole
sleeve is the sequencing, and *no lever in that sleeve's registry can reach
it*. `barnes.extreme_min_vol` is registered, caged and consumed — and walking
it to its floor changes nothing, because the blocker is that carry got there
first with a looser floor and spare capacity.

It is also the (ir)/(is) shape: the sleeve is not merely quiet, it is
**unfalsifiable**. It will publish `open: 0` until 4-Sep and the freeze will
lift on a sleeve with a zero-row sample, which reads as "no evidence yet"
rather than "never ran".

### FINDING 2 — the sleeve that DOES fire is 8-for-8 on instruments its own parent screens out

All 8 `carry` closes, 0% win, −$1.58:

| coin | class | n |
|---|---|---|
| WTI | commodities (3) | 4 |
| SKHYNIXUSD | Asian equities (6) | 2 |
| SPCX | pre-IPO (7) | 2 |
| | **crypto** | **0** |

Not a sampling accident — it is what the venue offers at that gate. Class split
of the *offered supply* over Barnesy's life:

- **carry gate ($2M floor):** 1,540 coin-snapshot offers, 6 distinct coins —
  commodities 46.7%, crypto 31.8% (KAITO, XMR), pre-IPO 14.4%, Asian
  equities 7.1%. **68.2% non-crypto.**
- **extreme gate ($10M floor):** 306 offers, 3 distinct coins — pre-IPO 49.0%,
  commodities 47.7%, Asian equities 3.3%. **100% non-crypto.** Over the full
  30-day tape at that floor the qualifying set is SKHYNIXUSD, SPCX, WTI, SNDK,
  MU — five books, **not one of them crypto**.

**The parent has the screen and the child does not.** `funding_carry_bot.py`
carries a crypto-only gate with its own `noncrypto` census bucket and a
`CARRY_ALLOW_NONCRYPTO=1` reversal. Barnesy's only `crypto_only` call sits in
`resolve_xsect_universe` — the xsect sleeve, screened by `(ki)`/`(kl)`. The two
harvest sleeves have no screen at all.

The timing makes this a live class, not history: commit `75ead10` **today**
(`lj,lk,ll`) class-screened `funding_carry_bot.py` **and** `lighter_perp_sniper.py`
in one pass — and did not touch `lighter_band_barnes_bot.py`. The sweep that
class-screened the fleet's funding books missed the funding SUPER-BOOK, i.e.
the book built expressly to consolidate those same parents' gates. This is the
exact pattern I14 names and `(im)` measured: *fixing instances is not closing
the class*, and a one-off fix is how a known defect survives.

Prior art that makes this a refuted population rather than an open question:
memory `noncrypto-funding-rank-rejected` (🏹 Tamerlane — funding rank does not
transfer to non-crypto), and `(ki)` finding this same leak in this same book
five days before its clock starts.

### FINDING 3 — the carry sleeve's unit economics cannot close, and the entry bar is not the reason

Friction is FIXED: `(SLIP 0.0005 + HEDGE 0.0010) × 2 × $80` = **$0.240 per
round trip**, i.e. 30bps on the clip. Funding accrues at `apr × $80 / 8760` per
hour. So every entry carries a break-even hold.

```
coin        class            entryAPR  break-even   held   accrued   fees     net
SKHYNIXUSD  Asian equities     247.0%      10.6h  11.58h   0.0356   0.240  -0.204
WTI         commodities         72.7%      36.1h   5.67h   0.0301   0.240  -0.210
SPCX        pre-IPO            122.6%      21.4h   3.67h   0.0231   0.240  -0.217
SKHYNIXUSD  Asian equities     193.6%      13.6h  15.00h   0.0590   0.240  -0.181
WTI         commodities        110.4%      23.8h   2.50h   0.0080   0.240  -0.232
SPCX        pre-IPO             64.8%      40.5h  41.67h   0.1288   0.240  -0.111
WTI         commodities         98.1%      26.8h   4.00h   0.0308   0.240  -0.209
WTI         commodities         83.2%      31.6h   5.25h   0.0276   0.240  -0.212

median break-even hold required : 25.3h
median hold actually achieved   :  5.46h
```

**Three trades DID reach their break-even hold and still lost**, which kills
the obvious "the flip exit fires too early" reading. The reason is that
`entry_apr` is a snapshot, not a rate that holds:

```
TOTAL implied accrual (entry apr held constant) : $0.9528
TOTAL realised accrual                          : $0.3430   (36.0% of implied)
TOTAL friction paid (8 × $0.24)                 : $1.9200
median EFFECTIVE apr over the hold              : 50.3%   (vs a 20.0% entry bar)
```

Even at a realised **50.3% effective APR** — 2.5× the entry bar — break-even
needs a **52-hour** hold against an achieved median of 5.46h. Realised accrual
came to **18% of the friction it paid**. The funding on these books is a
**spike, not a carry**, and the 6h persistence gate that exists to filter
exactly that does not filter it on these instruments.

Note the sleeve has fired `flip` **8 times out of 8** and `decay_paid` **zero**
times. Its parent 🌾 earns +$71.42 through `*_decay_paid` at 65–70h holds and
loses −$17.32 through the sided `*_flip`s at 6–10h holds ((gq)). Barnesy's
carry sleeve has only ever fired its parent's *losing* exit.

---

### VERDICT

**Hypothesis SUPPORTED, in a stronger form than posed.** The pooled −0.246%/trade
is not a small book having a bad fortnight. Of three sleeves:

1. `extreme` — **never ran, and cannot run**, at any lever setting in its own
   registry (0 of 8,611 snapshots).
2. `carry` — ran, and its entire realised sample is drawn from an instrument
   population its own parent screens out; its economics do not close there by
   a factor of ~5.6 on friction.
3. `xsect` — the only sleeve trading a validated, class-screened cross-section,
   n=40, mean −0.482%, t=−1.83 (its own parent ⚖️ is the fleet's worst book
   at −$30.42 MTM, in-era t=−1.97, horizon `unreachable`).

So the super-book is, today, **a one-sleeve book running its weakest parent's
mechanism**, and the 4-Sep freeze would lift over a sample that grades none of
what the book was built to test.

**No code was changed and no lever was written.** Three reasons, stated so the
next run does not re-litigate them: the book is under a birth freeze that is
itself the (it)/I19 discipline working; the tree moved 11 commits during this
run (another session pulled `main` from `1ef3e1d` to `5a4c9b8` mid-measurement,
with a dirty `scripts/golive_readiness.py` from a third); and the fix is book
LOGIC on a frozen book, which is an operator call on the freeze, not a research
act. Escalated as an evidence note + decision email.

**Re-verified at the post-move HEAD (`5a4c9b8`, 13-Aug):** `lighter_band_barnes_bot.py`
is untouched since 7-Aug, its only `crypto_only` call is still line 379 (the
xsect sleeve), and the extreme sleeve still runs second off a shared
`held_harvest`. Both findings hold at the current tip.

**This file lives under `reports/`, which is gitignored (`.gitignore:27`) — it
is local-only by the repo's own convention, not pending a commit.** A
`git clean -xfd` would remove it; nothing else will.

**What the operator is being asked to decide** (all shadow, zero real money):

- **A. Sequencing** — give `extreme` its own capacity, or run it BEFORE carry,
  or drop the shared `held_harvest`. Any one makes the sleeve falsifiable. The
  cheapest is ordering: it costs one line and no lever.
- **B. Class screen** — inherit the parent's `fleet_bus.is_crypto` gate into
  `harvest_candidates`, with the parent's own `CARRY_ALLOW_NONCRYPTO`-style
  reversal and a `noncrypto` census bucket. Same shape as today's `(lj,lk,ll)`
  on the parents. **Note honestly: on today's tape this makes carry's supply
  ~32% of what it was and would have blocked 8 of its 8 real entries — that is
  the point, but it also means the carry sleeve will trade RARELY.**
- **C. Whether the 4-Sep clock should restart** for any sleeve whose gate
  changes. Under the era doctrine a class screen is "different in kind" for the
  affected sleeve, so B implies a fresh clock on carry — and `extreme` has no
  clock to restart because it has never had a sample.

---

### IMPLEMENTED, same session (operator: *"implement new knowledge and make sure the team knows everything"*)

The hold-back above was resolved by the operator's instruction. Shipped as
`(lv)` — commit `b3c47d0`, deployed and **verified by stamp readback**
(`build b547e887bdb0`, `build_n 15` — both id AND count matched the local
prediction, per `(fd)`).

**MEASURED THE FIX BEFORE BUILDING IT** (forward-motion rule 3), and the
measurement killed one of the two candidates:

| variant | carry entries | extreme entries | extreme coins |
|---|---|---|---|
| shipped (no screen, carry first) | 29 / 12 coins | **0** | — |
| (A) reorder only | 18 / 9 coins | 12 / 5 coins | **all non-crypto** |
| (B) class screen only | 5 / 3 coins | **0** | — |
| (A)+(B) | 5 / 3 coins | **0** | — |

- **(B) SHIPPED.** `_class_ok` + `BARNES_ALLOW_NONCRYPTO` mirroring the
  parent's contract exactly (entry-only, fail-OPEN, `noncrypto` census bucket
  last in gate order). Plus: the `extreme` sleeve now publishes its OWN census
  at its OWN floor, so `{open: 0}` is no longer byte-identical between "quiet"
  and "impossible". Live payload confirms it — `extreme.scan` reads
  `thin: 19` against carry's `thin: 18`, i.e. the sleeve now names the one
  book that clears $2M and not $10M.
- **(A) REFUSED WITH NUMBERS, and the refusal is engraved at the code block**
  so it is not re-derived: the reorder is worthless under (B) and actively
  harmful without it. The decisive number:
  **the highest 24h volume ever seen on a crypto book at the 20% TRUE apr bar
  is $5.53M (KAITO), against a $10M floor** — the gate pair is empty in the
  crypto population, and `barnes.extreme_min_vol`'s cage `lo` (5e6) is itself
  90% of that observed maximum. Crypto supply by floor, 30d:
  `$0M 39.4% · $1M 13.0% · $2M 6.7% · $3M 4.9% · $5M 0.97% · $7.5M 0.00%`.
- **Mutation-verified (I3): six mutations, all reddened**, including the
  DEFAULT `class_ok` wiring — every other assertion injects `class_ok`, so
  without that case the default was free to regress to admit-everything with
  the suite green (the "a substring test is not a wiring test" class).
- **Doctrine:** I18 gained its second shape (a SUBSET consumer running SECOND
  is unreachable however slack its own levers); Barnesy's fleet-table row
  corrected in place per I12; two memories written.

**Honest limit on what is verified live:** the screen's *plumbing* is confirmed
in the payload (the `noncrypto` key exists and the census partitions), but its
*bite* is not yet observed — the bucket reads 0 at the time of writing, because
nothing is currently hot + liquid + persistent + non-crypto simultaneously.
The bite is intermittent by nature (68% of OFFERS, and offers are rare). Watch
that bucket over the next days; a screen that never moves it would be the
`(iz)` shape (a declared enforcement that is inert).

### DECIDED, same session (operator: *"fix the obvious problem"*) — `(ly)`

The obvious problem was the one this pass diagnosed fully and then escalated:
a sleeve that can never fire, still sitting in a book being graded. I17 says
that is a keep-or-retire call and **not another tuning pass**, so it was
measured to a decision. Shipped as `(ly)`, commit `3c51523`, deployed and
verified by stamp readback (`64841f73bbe0` / n=15; the live row now publishes
`sleeves.extreme.retired: true`).

**The measurement corrects `(lv)` in one place.** `(lv)` treated floor and
ordering as alternatives and called the reorder refused. Sharper: **they are
not alternatives and neither works alone.** Lowering the floor is INERT at any
value ≥ carry's (the subset relation holds, carry still runs first); the
reorder alone feeds a directional sleeve non-crypto names. Only the pair moves
anything — and then, with the class screen on, over the full 30d tape:

| ext floor | entries/30d | days to 30 closes | carry entries |
|---|---|---|---|
| $10M (shipped) | **0** | never | 5 |
| $5M (the cage's own `lo`) | **0** | never | 5 |
| $3M + reorder | 1 | **903** | 4 |
| $2M + reorder | 5 | **181** | **0** |
| $1M + reorder | 7 | **129** | **0** |

**Undecidable at every reachable setting, and the two cheap ones take the carry
sleeve's supply to ZERO.** Root cause is not a bad constant: at the 20% TRUE
bar this venue's entire crypto population is **KAITO / XMR / PAXG / XRP**, so
two harvest sleeves bid for the same three or four names. **One venue, one
harvest sleeve.** The $10M floor came from 💸 the Farmer, where it guarantees
REAL fills; here it gated a MODELLED shadow leg against a supply that never
existed.

Retired entry-only ((if)/(jh)/(lo) pattern — a restored position still exits
normally), reversible via `BARNES_EXTREME_RETIRED_OVERRIDE=run`, and **the
census keeps publishing beside `retired: true`** so the call is reversible on
evidence rather than permanent by accident. Pinned by
`tests/autonomy/test_barnes_extreme_retired.py` — AST-shaped, carrying the
decision table in its own header, six mutations verified. Two of that test's
own first-draft assertions were wrong (it matched the selftest's fixture call
sites, and anchored its doc window on the sleeve tuple in `build_extra`); both
were test bugs, fixed with the reason recorded in the file.

**It changes no trades today, and the entry says so.** The sleeve never opened
one. What it buys is that the next session cannot "fix" the ordering and
silently starve the sleeve that works — a one-line change that looks like an
improvement and measurably is not.

**Still the operator's call:** whether the 4-Sep clock restarts for the carry
sleeve now that its admitted population changed (I did not reset anything —
there is no sample to protect).

---

## 2026-08-16 (Sat, Sydney) — `(lz)` RE-RUN ON CURRENT NUMBERS: the supply claim reproduces EXACTLY, the duplication claim was wrong, and the collision landed somewhere I did not predict

Operator asked for `(lz)`'s measurements re-run three fleet-days later (the
clock moved 13-Aug → 16-Aug during the session; the tape grew 30.1d → 32.9d).

### The supply claim: REPRODUCES, to the snapshot

| | `(lz)`, 13-Aug | now, 16-Aug |
|---|---|---|
| tape | 8,633 snapshots / 30.1d | 9,441 / 32.9d |
| coins at 20% TRUE / $2M / crypto | **KAITO, XMR, PAXG** | **identical** |
| snapshots offering ≥1 | **573** (6.64%) | **573** (6.07%) |
| per-coin offers | — | KAITO 483, XMR 71, PAXG 38 |
| max simultaneous | 2 | 2 |
| books whose gate admits it | 3 | **same 3** |

The percentage moved only because the DENOMINATOR grew. **The absolute count is
identical at 573** — meaning the contested supply has been completely dry for
three days, not merely thin. The I20 finding is robust.

Newly resolvable (all bands now published): 🛢️ Garrett `[0.10M, 2.00M)`, 🧮 Hull
`[2.00M, 10.00M)` at a 7.82% gate, and both Farmer arms `[10.00M, inf)` are
**correctly EXCLUDED** — zero UNKNOWNs. 🧮 Hull, born since `(lz)`, is a
correctly differentiated book by I20's own test.

### The duplication claim: WRONG, and wrong in an interesting way

`(lz)` closed with *"13 positions across 13 distinct (coin, side) — 0%
duplication... the collision is structural, not current."* **That is now false.**

    31 positions -> 24 distinct (coin, side)   =  20% duplicates
    (23% before correcting for the judge's arm pair, below)

But **not at the gate I measured.** The three books sharing the 20% harvest
gate hold NOTHING there right now. The duplication materialised in the
**CROSS-SECTION**:

| coin | holders | side |
|---|---|---|
| LTC, SEI, TIA, HYPE | ⚖️ Counterweight + 🎸 Barnesy `xsect` | **same side** |
| BNB | ⚖️ Counterweight + 🛢️ Garrett | same side |
| LINK | ⚖️ + 💸 Farmer + 🎸 | opposing, partly nets |

**4 of ⚖️ Counterweight's 10 positions are duplicated same-side by 🎸's xsect
sleeve** — which is obvious in hindsight and was in the fleet table the whole
time: that sleeve IS *"⚖️ at the VALIDATED K=5 plateau centre"*, i.e. the same
strategy over an overlapping universe. **I measured the harvest gate and the
real duplication was in the cross-section.** The lesson is not that the tool
was wrong — it found this the first time it was pointed at the live fleet — but
that I predicted the collision in the place I had just been looking.

### A false positive of my own, fixed

The detector flagged **XAU(S) on both Farmer arms** as concentration WITH a
`** REAL MONEY **` banner. Those two rows are the experiment judge's
experiment/control pair — they are *supposed* to hold the same coin. That is
the cry-wolf failure the three-valued `admits()` exists to prevent, reappearing
one function over. Fixed (`ARM_PAIRS`, commit `e07f698`): within-pair
duplication is REPORTED but never a finding, and the effective-bets metric
collapses arms to one holder first, since the metric is about EVIDENCE
independence. 23% → 20%, spurious banner gone, the five genuine pairs untouched.

### Verdict

`(lz)`'s I20 core stands unchanged and is now better evidenced. Its closing
duplication sentence is corrected in place. The open question it raises is new:
**⚖️ Counterweight and 🎸's xsect sleeve are running the same strategy on the
same universe**, and ⚖️ is the fleet's worst book with a pre-registered ~28-Aug
keep-or-retire date. Whether 🎸's xsect sleeve should survive that decision is
a question the fleet has never asked, because until this week nothing could see
that the two books hold the same positions.

---

## 2026-08-16 — THE COUPLED DECISION: ⚖️ Counterweight + 🎸's `xsect` sleeve

Operator: *"decide counterweight and the xsect sleeve together"*. Half was
already decided, and measuring the other half CONFIRMED the standing hold
rather than overturning it.

### 🎸's `xsect` sleeve — RETIRED already, 15-Aug `(nf)`. Confirmed correct.

Retired on the X6 attribution: the sleeve was the book's whole burn (−$9.56 of
−$11.01, era crypto LONGS at 4.5% win, cluster t=−2.20) while parent ⚖️ rode
the SAME window near-flat. My 16-Aug overlap reading corroborates it from a
different direction — the 10 legs I measured as "duplicates of ⚖️" are legs
WINDING DOWN through the sleeve's own 24h rebalance (its only exit), not new
bets. Mechanism was chosen correctly: xsect is ALWAYS-IN, so an entry gate
would have held the losing legs' MTM open; empty targets flatten it instead.

**So the duplication I flagged is already self-liquidating.** The coupled
decision I proposed was, in part, already made a day before I proposed it.

### ⚖️ Counterweight — **KEEP.** Hold to the pre-registered ~28-Aug date.

The gate reads n=101, mean −1.474%, t=−1.73, horizon `unreachable`. Retiring on
that would be the (hs)/(ia) trap, and today's measurement says so in numbers:

**[CORRECTED 16-Aug — the first table below was computed on a CLOSE-keyed era
and is wrong. An era is keyed on the OPEN ("a trade's policy is fixed when the
trade is taken", `era_rows`), so my filter admitted 10 straddlers opened under
the superseded policy. The verdict is unchanged; three numbers were not.]**

| in-era slice (OPEN-keyed, n=91 — CORRECT) | n | net | mean/trade | trades t |
|---|---|---|---|---|
| ALL | 91 | −$31.16 | −1.734% | −1.87 |
| **CRYPTO — still enterable** | 72 | **+$5.22** | **+0.357%** | +0.60 |
| NON-CRYPTO — now unenterable | 19 | −$36.38 | −9.660% | −2.90 |

Non-crypto share of the in-era P&L: **117%** (not the 130% first published).
Cluster-robust `t` is the ORGAN's, now that it publishes one: **−1.23** over
**26 decisions**, `n_eff` 39.6, `max_batch` 12 — not my hand-derived −0.98.

~~| in-era slice | n | net | mean/trade | trades t | decisions | cluster t |~~
~~| ALL | 101 | −$28.05 | −1.474% | −1.73 | 28 | −0.98 |~~
~~| CRYPTO — still enterable | 82 | +$8.33 | +0.423% | +0.78 | 28 | +1.36 |~~
~~| NON-CRYPTO — now unenterable | 19 | −$36.38 | −9.660% | −2.90 | 5 | −1.47 |~~

- **130% of the in-era loss comes from trades the book can no longer take.**
  All 19 non-crypto closes fall in a bounded 1–5 Aug episode, ending the day
  the class screen landed. Zero since.
- **On what it can still take it is POSITIVE**: +$8.33, +0.423%/trade.
- **The headline `t` is inflated by (ky).** 101 legs are **28 decisions** — a
  basket book closes ten legs in one instant. Cluster-robust `t` on the full
  in-era is **−0.98**, nowhere near significant, and the gate's `unreachable`
  verdict is computed on the pooled per-trade sample. **That verdict is not
  decision-grade for this book**, and the horizon organ cannot know it.

**The honest other half, stated so 28-Aug is a real decision and not a
formality:** since the fix it is **FLAT, not profitable** — 23 crypto closes
for **+$0.15**. The case for keeping is "not shown to be losing", not "shown to
be winning". What should be judged on ~28-Aug is the **post-5-Aug sample only**
(≈4 weeks by then), on **cluster-robust t over decisions**, never the pooled
per-trade `t`.

### Considered and REJECTED: moving ⚖️'s era to 5-Aug

Tempting — the gate is grading a sample 130%-driven by unenterable trades, and
(hc) says an era is the latest of every invalidating change. **Rejected on
precedent:** 🌾 carry was class-screened by `(lk)` and its era stayed at
31-Jul; no era moved for any class screen. The fleet treats a narrowed universe
as ordinary tuning, exactly as (hc) treats a widened one. Moving ⚖️'s era alone
would break that consistency **and** would conveniently postpone a decision I
had just been asked to make — the wrong reason to move a goalpost. The sample
defect is recorded here instead, for the 28-Aug reader to apply by hand.

### NEXT THREAD (for the following run — do not start it in this one)

The **friction floor as a fleet-wide book-design constraint**. This run
produced a number with reach beyond Barnesy: a modelled 30bps round trip needs
**52 hours at 50% APR** on an $80 clip to break even. `(js)` measured Lighter's
real slippage distribution at n=158 tx-hash fills. The open question is which
of the fleet's funding books have a *median hold shorter than their own
break-even hold* — a book failing that test cannot profit no matter how good
its entry gate is, and the test is cheap on the existing ledger. Candidates:
🌾 carry's sided-flip bucket, 🎸's carry sleeve, ⚖️'s 24h rebalance cadence.

**Harnesses** (scratchpad, read-only, reproducible):
`barnes_sleeves.py` · `barnes_reachability.py` · `barnes_gate_replay.py` ·
`barnes_verdict.py`

---

## 2026-08-19 (Wed, Sydney) — 💸 THE FARMER IS A DIRECTIONAL BOOK AND ITS DIRECTION HAS NEVER BEEN NULL-TESTED: 86.5% of the real-money book's return is PRICE, and P(random ≥ actual) = 0.382

Full evidence note: **`reports/evidence_directional_funding_null_2026-08-19.md`**
(numbers, calibration, per-coin, consequences). Summary here so the next run
does not re-test it.

### Why this hypothesis

The carried thread from 16-Aug was *the friction floor as a fleet-wide
book-design constraint* — which funding books hold shorter than their own
break-even hold. Half of it was **spent** before this run: 🌾 carry's flip
grace 1h→6h shipped in `(px)` on the `(mf)` cell measurement, 🎸 Barnesy was
retired `(pm)`, and 🏦 Rich Dad / 🧮 Hull have **zero closes** so are
untestable today. Re-scoping it produced the half nobody had looked at, and it
is where the real money is:

**The fleet has TWO families of funding book with TWO different binding
constraints, and only one has ever been measured.**
- *delta-neutral MODELLED* (🌾 carry · 🏦 Rich Dad · 🧮 Hull) — P&L is
  `accrued − fees`, **no price term by construction**. Binding constraint =
  **fee friction vs hold**. That is the carried thread; `(mf)`/`(px)` did it.
- *DIRECTIONAL* (💸 Farmer LIVE + shadow · 🛢️ Garrett) — takes the receiving
  side **unhedged**. Binding constraint = **price variance vs hold**. Never
  measured, and it holds the fleet's real money.

### Method

Ledger decomposition mirroring production's own close path
(`pnl_abs = price_pnl + fund_pnl`, `pnl_pct = pnl_abs/entry_clip` ⇒ the price
term is exact); then `(hm)`'s random-entry null — same coin, same side, same
hold duration, **random entry time**, 5m Lighter candles, 4,000
book-replications — behind a **paired calibration gate**.

### Numbers

| book | n | TOTAL %/tr (t) | price share | actual (5m) | random null | **P(random ≥ actual)** |
|---|---:|---:|---:|---:|---:|---:|
| 💸 Farmer **LIVE (real money)** | 104 | +0.1266 (0.73) | **86.5%** | +0.0701% | +0.0185% | **0.382** |
| 💸 Farmer shadow | 153 | +0.0145 (0.08) | 54.6% | −0.0377% | +0.0108% | 0.596 |
| 🛢️ Garrett | 22 | −0.8288 (−1.06) | **100.9%** | −0.8604% | −0.1858% | **0.944** |

Calibration `corr(ledger, 5m replay)` = **+0.9958 / +0.9975 / +0.9982**.
Shorts-only re-runs agree (P=0.426 / 0.587). No coin carries it.

**Structural, so no gate tuning can fix it:** mean `|price|` is **162×** the
maximum funding the live book can accrue at its own 5% gate over its own holds
(40× even at 20% APR). Funding is linear in hold, price noise ∝ √hold — the
crossover is **~51 years at 5% APR** against a **72h** max hold.

### Verdict — **NOT SUPPORTED (unproven, not disproven)**

The header thesis — *extreme funding marks crowded positioning that mean-reverts,
so the receiving side is the contrarian side* — has no support on Lighter's own
tape at n=104 in-era. **It is not refuted either**: P=0.382 means the sample
cannot tell the book from matched random timing, and demonstrating its measured
+0.0516%/trade excess would need **~4,709 closes ≈ 4.0 years**. The fleet's own
horizon organ agrees independently (Farmer LIVE `t=0.29`, *"needs ~1320d"*;
shadow `t=0.06`, *"~36346d"*; Garrett `t=−1.05`, *"unreachable"*).

**A fourth undecidability class: UNDECIDABLE BY SWAMPING** — a healthy close
rate, but the harvested quantity sits two orders of magnitude below the noise it
is carried in. (Beside I17's slow clock, `(po)`'s fat tail, `(pm)`'s redundancy.)

### Refuted for good — do not re-run

- ❌ *"the Farmer's edge is its funding gate"* — 86.5% of its return is price.
- ❌ *"a directional funding book can be fixed by raising the APR gate"* — the
  crossover hold at 20% APR is still 3.2 years against a 72h cap.
- ✅ **Correction to `(hm)` itself:** its *"a random short earns +0.2 to
  +1.1%/trade free"* was measured at the **Ticket Taker's horizon**. At the
  Farmer's horizon (6h holds, majors) the measured premium is **+0.018 to
  +0.024%/trade** — an order of magnitude smaller. **The free-short premium is
  horizon-dependent: measure it at the book's own horizon, never quote it
  across books.** (I14's shape, applied to the null instead of the grade.)

### Nothing applied

No lever, no deploy, no code change — real-money findings are escalated, and the
honest reading is "unproven", not "losing" (the live row is **+$5.74 realised**).
Escalated: 🛢️ Garrett's ~12-Sep call now has a *mechanism* under the gate's
existing `unreachable`; and `fleet_allocation` points 85% of the capital pointer
at the funding class on two claims, one of which (💸 0.0112%) is ~86% an
un-null-tested price term. Real money never reads that organ (AST-pinned).

### PART 2, SAME DAY — the coin-filter question, RUN (operator: "continue")

**Verdict: the gate supplies no SELECTION either — funding is a fair price for
the adverse selection it signals.**

Pool reconstructed from the scout's own 5,752 snapshots (29-Jul → 18-Aug, 5-min
cadence). **At the Farmer's $10M floor the eligible pool is 13 coins EVER,
median 7 per snapshot**, with BTC/ETH/SOL/HYPE eligible ~100% of the time — the
gate picks 1 of ~7 and has almost nothing to filter.

Paired design (rank-1 minus the equal-weight eligible basket at the same
instant), so the single falling-BTC regime cancels exactly. **Both halves
measured**, because the gate's fair defence is "the price goes against you
because that is what you are paid for":

| H (non-overlapping) | n | price diff | funding edge | **TOTAL** | t |
|---|---:|---:|---:|---:|---:|
| **6h (its own median hold)** | 80 | −0.0440% | +0.0444% | **+0.0003%** | **+0.00** |
| 24h | 20 | −0.0780% | +0.2140% | +0.1360% | +0.09 |
| 2h | 241 | +0.0094% | +0.0131% | +0.0225% | +0.30 |
| 6h at its own 5% gate | 70 | −0.0506% | +0.0423% | −0.0083% | −0.04 |

**The two halves cancel to zero.** Overlapping 1h sampling gives naive
`t=−1.61` (price) and `t=−2.70` (top-3); both dissolve under a moving-block
bootstrap (block = 1 day): price 95% CI **[−0.548%, +0.180%]**, TOTAL
**[−0.500%, +0.210%]**. **Do not quote the naive t** — recorded so nobody does.

**This corroborates a refutation the fleet already made and never applied here.**
22-Jul 🏹 Tamerlane killed the receiving-side raid in **25 of 25 cells** because
*"adverse selection scales with the extremity and eats it"* — but that rejected
a PROPOSED book; **the live Farmer runs the same mechanism at a 5% gate and was
never re-examined.** Read together:

| gate | adverse selection vs funding | edge |
|---|---|---|
| extreme (30–500%, Tamerlane) | **>** funding | negative |
| mild (5–25%, the Farmer) | **≈** funding | **zero** |

**They scale together — there is no threshold at which this mechanism pays.**
That closes the class instead of adding a 26th dead cell.

### CONSOLIDATED VERDICT

The gate supplies **neither timing** (P=0.382/0.596/0.944) **nor selection**
(+0.0003%/period, t=0.00). Expected edge is **zero by construction**. That
*explains* Part 1 rather than merely agreeing: a zero-edge gate produces exactly
what the Farmer shows — price noise centred near zero (live t=0.73, shadow
t=0.08, Garrett t=−1.05). **Re-expression on this venue has no headroom**; the
remaining question is the I17 keep-or-retire one, and it is the operator's.
Still not a claim that it loses — the live row is **+$5.74 realised**.

### NEXT THREAD (for the following run — do not start it in this one)

Both parts measured the gate as a **signal**. Neither tested the one use that
survives a zero-edge gate: **funding as a COST input to a book with an
independent edge** — i.e. does adding a "never hold the paying side of a hot
book" veto improve any EXISTING directional book (🎫 taker, 🧘 Douglas, 📐
Grimes, the family books)? That is a restrict-only overlay, so it is priceable
through the replay gate under I19 and cannot be turnover-bought. The 13-coin
eligible pool is too small for it; the test needs the full 210-book `funding`
map, which the same cached snapshots already carry.

---

## 2026-08-19 (Wed, Sydney) — PART 3: THE RAMP'S FOUNDATION FAILS ITS OWN TEST — `fleet_allocation`'s claim does NOT predict forward return, so a tranche built on it would deploy real money on noise

**Operator reframe:** *"We are looking at this as a risk eliminating job as
opposed to a profit motivated job... look at options, even though risk will be
higher."* Fair, and the numbers agree: **$259.75 of real money against $16,026
of paper — 62:1.** The fleet is optimally configured not to lose $260.

Diagnosis accepted: **evidence converts to money through a STEP function (6
bars incl. t≥2.0 ≈ 97.7% confidence) that has never fired once.** Proposed
Option 1 was to replace it with a RAMP — size by confidence using I16's
`max(0, mean − 1.28·SE)`, which `fleet_allocation` already computes.

### Built the simulation, then tested its foundation — and the foundation failed

Walk-forward, weekly rebalance, **retired books kept in-pool while alive**
(10 of them: gillard/rudd/abbott/morrison/dislocation/breakout-4h/barnes/
intraday-15m/swing-daily/dad), Lighter era only (Kraken/HL-era books excluded —
donchian +$272, rsi-meanrev +$69, listing-sniper +$206 would have been fantasy
winners from a venue we left):

| strategy | return on deployed capital | maxDD |
|---|---:|---:|
| the gate as it stands | **+0.00%** (never deploys) | 0.00% |
| equal-weight every living book | −0.28% | −0.41% |
| **claim-weighted (the tranche)** | **−1.89%** | −3.22% |
| claim-weighted + 25% probe floor | −1.48% | −2.51% |

Only 4 weekly periods — not decidable. So the decisive test is the one with
power: **does the claim predict forward return at all?**

| | H=7d | H=14d |
|---|---:|---:|
| observations (book, day) | 328 over 24 days, 18 books | 207 over 17 days, 16 books |
| Pearson(claim, forward) | +0.0960 | +0.1054 |
| **Spearman(claim, forward)** | **−0.0036** | **−0.0685** |
| LOW / MID / HIGH claim tercile | −0.027 / **−0.216** / +0.028% | −0.099 / **−0.385** / −0.015% |
| paired: top-claim minus avg living book | +0.0518%, block-boot CI **[−0.648, +0.404]** | +0.0636%, CI **[−0.826, +1.020]** |

**The claim does not rank.** Spearman is ~zero (slightly negative); the tercile
buckets are **non-monotone** — the MIDDLE bucket is the worst, which is the
signature of noise, not signal. The weakly positive Pearson against a zero
Spearman means a couple of outliers, not a monotone relationship. Paired against
the same-day average living book, the top-claim book's edge is
**+0.05%/week with a CI straddling zero**.

### Verdict — Option 1 is REFUSED as designed, and that refusal saved real money

A tranche weighted by this claim would have **deployed real capital on noise**,
and in the one window available it did worse than equal-weight. Building the
conversion valve is premature while nothing upstream ranks.

**Honest power limit, stated so this is not over-read:** 24 days, 18 books,
7×-overlapping windows (block-bootstrapped). This is **"not demonstrated on the
data available with a point estimate of ~zero"**, NOT "proven useless". The
Lighter ledger is ~5 weeks deep for most books; that is the binding limit.

### What this redirects to — the profit-motivated reading

The bottleneck is **not** the conversion valve, and it is not measurement
rigour. **It is that no book has a demonstrated edge and nothing ranks them.**
Given that, the profit-maximising move is NOT better allocation math on top of
noise — it is **more independent shots on goal, killed faster**, aimed at the
surface with the most unexploited room:

1. **The ~200 illiquid books.** The fleet trades 7–13 of 210. The $10M floor is
   a risk-elimination choice; at $80 clips, size is not the constraint. This is
   the largest untouched surface and is risk-tolerant by construction.
2. **Monetise the refutation catalogue.** 🪁 band-kelly (born 18-Aug, strongest
   founding claim in the fleet) is the first expression. Today's Part 2 adds a
   concrete candidate: Tamerlane measured the receiving side of extreme funding
   at **t = −8.9, −6.5, −5.3, −4.0** on short holds — an unusually RELIABLE
   price effect. Its mirror pays a deterministic funding cost against it; whether
   the net clears is one cheap measurement on an existing harness.
3. **Low-ceremony births.** A book currently costs ~a day of founding study.
   Five speculative shadow books for that price; let 30-day ledgers decide.

### NEXT THREAD

Run the **Tamerlane mirror**: take the PAYING side of extreme funding prints at
short holds, charging the funding cost explicitly, across the 25-cell
threshold×hold grid the original used. Concrete, cheap, and the one candidate
edge today's work actually generated.

---

## 2026-08-19 (Wed, Sydney) — PART 4: THE TAMERLANE MIRROR IS DEAD TOO, AND THE TWO DIRECTIONS TOGETHER CLOSE THE WHOLE FUNDING SURFACE

Ran the mirror of the fleet's strongest measured loser: **take the PAYING side**
of an extreme funding print. Fleet's own harness logic
(`backtest_funding_tail_raid_lighter::evaluate`, side flipped), same **forced
t+1 entry lag**, 25 books × 180d hourly tape, 25 threshold×hold cells.

Slippage charged ROUND TRIP from the (js) tx-hash fill study (n=158):
liquid **0.54bps**, mid-tier **3.86bps**, thin **10.24bps**.

### Result: dead in 24 of 25 cells

| cell | funding | price | NET | t@0 | t@0.54 | t@3.86 | t@10.24 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **th=1.00 / 8h (best)** | −15.8 | +27.4 | **+11.7** | +2.1 | **+2.0** | +1.4 | +0.3 |
| th=2.00 / 8h | −24.3 | +38.7 | +14.3 | +1.9 | +1.8 | +1.4 | +0.5 |
| th=2.00 / 24h | −51.6 | +66.8 | +15.2 | +1.1 | +1.0 | +0.8 | +0.3 |
| th=5.00 / 8h | −41.3 | +39.5 | −1.8 | −0.1 | −0.2 | −0.4 | −1.0 |

**The one marginal cell dies on its own event population.** Its events are
overwhelmingly NON-CRYPTO and NOT liquid-tier — SKHYNIXUSD 939, WTI 788,
BRENTOIL 526, MU 214, SNDK 206, SOXL 178, GRAM 123, AMD 91. Charged at the
tier those books actually fill in (mid 3.86 / thin 10.24bps) it reads **t=+1.4
/ +0.3**. The 0.54bps column is the wrong price for this basket, so the honest
verdict is **dead**, not marginal.

### The structural finding — funding and price cancel in EVERY cell, BOTH directions

Read the two legs down the table: th=2.00/24h reads funding −51.6 vs price
+66.8; th=5.00/24h reads −80.6 vs +89.6; th=1.00/8h reads −15.8 vs +27.4. **The
two legs track each other to within ~10–20% everywhere, in both directions, at
every threshold from 30% to 500% and every hold from 1h to 24h.**

That is **Part 2's finding reproduced on a completely independent
construction** — Part 2 measured the MILD gate (5–25%, 13 coins, 20 days,
cross-sectional) and got total edge +0.0003%/period; Part 4 measures the
EXTREME tail (30–500%, 25 books, 180 days, event-study) and gets the same
cancellation. **Two measurements at opposite ends of the threshold range, same
conclusion: this venue prices funding correctly.**

**THE FUNDING SURFACE IS CLOSED.** Not "no cell found" — *priced*, with the
mechanism identified and confirmed twice. No further session should be spent on
directional funding in either direction, at any threshold or hold.

### Honest note on reproduction

My control run reproduces the 22-Jul finding **in direction and mechanism**
(receiving side negative, adverse selection scaling with extremity, funding
genuinely collectable) but **not in cell values** — recorded th=5.00/24h reads
funding +56.9 / price −25.8 / net +31.1; mine reads +80.6 / −89.6 / −9.0.
Different universe (25 books/180d vs 37/150d). **Quoted as a re-measurement on a
different tape, never as a reproduction.**

### THE STRATEGIC READING — where the fleet's attention is inversely allocated to its edge

Everything measured today says the funding dimension is efficiently priced. Set
the magnitudes side by side:

| surface | measured per-trade effect | books the fleet runs on it |
|---|---|---|
| **funding (directional)** | ±0.001–0.15%, **cancels to ~0** | **3 live** (💸 Farmer ×2, 🛢️ Garrett) |
| **price dislocation** | 🧲 ghost −0.281% (t=−2.97) → 🪁 mirror **+0.605%/trade, t=+5.71** | **1**, born 18-Aug, 0 closes |

**The dislocation surface showed effects two orders of magnitude larger than the
funding surface**, in both its losing and its mirrored form — and the fleet has
six funding books against one dislocation book. That is the actionable
conclusion of the day, and it is a growth statement, not a refusal: **stop
building directional funding books; put the shots on price-structure and the
illiquid tail.**

Caveat kept honest: 🪁 band-kelly's +0.605% is a replay of a ghost's windows,
**n=0 live closes**. It is the fleet's largest measured claim and its least
tested one. The magnitude argument does not depend on it — the ghost's own
realised −0.281% at t=−2.97 is live-ledger evidence that dislocation moves real
money at 100× the scale funding does.

### NEXT THREAD

**The illiquid tail on NON-funding logic.** ~200 books the fleet never touches;
the $10M floor is a risk-elimination choice and at $80 clips size is not the
constraint. Needs a tape fetch across the tail (the expensive part) and a
price-structure rule, not a funding gate.

---

## 2026-08-19 (Wed, Sydney) — PART 5: THE ILLIQUID TAIL HAS A REAL, OUT-OF-SAMPLE-STABLE REVERSAL SIGNAL — AND TAKER SLIPPAGE IS LARGER THAN IT. COST IS THE BINDING CONSTRAINT, AND NOBODY HAS ATTACKED IT.

**The first positive signal of the day, and the first blocker that is neither
variance nor efficiency.**

Universe: the **137 active books at $20k ≤ vol < $10M** — the surface the
fleet's $10M floor excludes. It trades **7 of 227**. Fetched 4h candles for all
137 (median 1,890 bars ≈ 315 days). Cross-sectional quintile long/short,
**market-neutral by construction** (which is what makes it immune to the
single-falling-BTC-regime problem, item 18).

Traps handled: **execution lag** (signal at bar *t* close, entry at *t+1*
close), **staleness screen** (illiquid books go flat then jump, manufacturing
fake reversal — books must have moved in ≥60% of lookback bars), **slippage
charged per book by its own (js) tier** (5.12 bps/fill sub-$1M, 4 fills per
long/short pair).

### The grid's "winner" was a lucky cell, and out-of-sample killed it

Best by net t was REVERSAL L=4h/H=48h: net +0.529%/period, t=+2.01, random-
assignment null P=0.0000. **Refuted:**

| cell | first half | second half |
|---|---|---|
| **L=4h H=48h (the grid winner)** | +0.568% (t=+1.31) | **−0.308% (t=−1.21)** — SIGN FLIP |
| **L=4h H=4h (most periods)** | **+0.068% (t=+1.37)** | **+0.063% (t=+1.74)** — STABLE |
| L=24h H=4h | +0.098% (t=+1.79) | +0.012% (t=+0.30) — decays |

The gross-t surface is **scattered, not a plateau** (2.16 / 1.62 / 0.91 / 2.36
across the L=4h row; the whole L=12h row is ~0 or negative). 16 cells were
searched; the best of 16 at t=2.01 with the FEWEST periods and unsupported
neighbours is the grid-mining signature. **The cell that survives is not the
winner — it is the one with the most periods that held in both halves.**

*(Note: the 16 MOMENTUM rows carry no independent information — in a quintile
long/short design gross momentum is exactly −gross reversal. 32 printed rows are
16 tests.)*

### What is real

**[CORRECTED IN PLACE 2026-08-19 by PART 6 — this section measured the ALL-TAIL
universe, which INCLUDES the <$0.1M dust tier. That tier is UNTRADEABLE (the
fleet's own orders: mean 17.49 bps/fill, p90 398 bps), and excluding it removes
the out-of-sample stability claimed below: on the tradeable universe gross reads
+7.3 bps in H1 and +3.5 bps in H2 — still positive in both halves, but DECAYING
rather than stable. The cost figure below (a flat (js) 5.12 bps/fill) is also
wrong in both directions. See PART 6 for the corrected numbers; the qualitative
finding — a real gross signal, consumed by execution cost — survives and is
sharper.]**

**L=4h/H=4h reversal: gross +6.6 bps per 4h period**, 998 non-overlapping
periods, stable across halves (+6.8 / +6.3), block bootstrap (block=8) 95% CI
**[+0.7, +13.2] bps, P(>0)=0.983.**

### And what kills it — COST, measured

| universe | books | gross | cost | **net** | t(net) |
|---|---:|---:|---:|---:|---:|
| all tail | 134 | +0.066% | **0.094%** | **−0.028%** | −0.93 |
| vol ≥ $1M | 21 | +0.089% | 0.039% | +0.050% | +0.58 |
| vol ≥ $2M | 10 | +0.184% | 0.039% | +0.145% | +0.89 |

**The signal is real and smaller than the taker slippage required to harvest
it.** Restricting to the liquid part cuts cost 0.094% → 0.039% and gross
actually RISES (0.066 → 0.184) — but n collapses and t stays below 1, and those
10 books are largely Hull's band, i.e. no longer untouched surface.

**Counterintuitive and worth recording:** reversal is STRONGER in the more
liquid books, not the more illiquid ones. The sub-$1M "reversal" is partly
stale-price artifact diluting the measurement, which is the opposite of the
"inefficiency lives in the tail" prior this test was built on.

### VERDICT — NOT TRADEABLE AS-IS, and the blocker is new

Every other refusal today died of **variance** (Part 1), **efficient pricing**
(Parts 2 & 4) or **no ranking signal** (Part 3). This one dies of **execution
cost**, which is the only blocker so far that has an untried lever pointed at
it.

### THE LEVER NOBODY HAS TRIED: PASSIVE EXECUTION

Lighter's **maker fee is 0.0000** (measured, all 203 active books). The 5.12
bps is **slippage from crossing the spread**, not a fee. Every bot in this fleet
crosses. A passive/maker entry would avoid most of that cost at the price of
fill uncertainty — and on the one surface where a signal survives out-of-sample
validation, **that cost is precisely and only what stands between it and
money**: +6.6 bps of signal against 9.4 bps of crossing.

The fleet has **never measured its own maker fill rate**, so the question is
open rather than refuted. That is the highest-value unmeasured constant in the
system right now — it gates this signal, and it would improve every other book
that crosses a spread.

### NEXT THREAD

Measure the maker-fill economics: from `venue_orders` and the (js) tx-hash fill
data, what fraction of resting orders fill within N minutes at the touch, and
what is the realised cost of a passive entry vs a crossing one? If passive
execution lands below ~4 bps round trip, the L=4h/H=4h tail reversal goes net
positive and becomes a real book candidate. If it does not, the tail closes too.

---

## 2026-08-19 (Wed, Sydney) — PART 6: I PRICED PART 5 WITH A STUDY CONSTANT WHILE THE FLEET HELD 3,015 OF ITS OWN MEASUREMENTS — corrected, and the tail signal is EXACTLY consumed by its own execution cost

Part 5 charged a flat **(js) 5.12 bps/fill** to every book under $1M. The fleet
has **3,015 `venue_orders` rows with measured `slippage_bps` across 122 coins**.
Verifying the inherited constant against the fleet's own record changed the
answer in both directions.

### The fleet's own slippage curve (MEAN bps/fill — a continuous strategy pays the average, not the median)

| tier | coins | orders | median | **mean** | p90 |
|---|---:|---:|---:|---:|---:|
| ≥ $10M | 7 | 831 | 0.32 | **0.61** | 1.35 |
| $2–10M | 12 | 617 | 0.00 | **1.18** | 3.23 |
| $1–2M | 9 | 227 | 1.03 | **5.35** | 12.44 |
| $0.1–1M | 48 | 847 | 2.51 | **2.52** | 9.42 |
| **< $0.1M** | 46 | 446 | 3.91 | **17.49** | **398.08** |

**The dust tier is not a surface, it is a trap** — mean 17.49 bps/fill with a
p90 of 398 bps (4%). Part 5's flat 5.12 both *over*-charged the tradeable
$0.1–1M band (true mean 2.52) and *under*-charged the dust by 3.4×.

Live real fills corroborate the liquid end independently: n=294, **median 0.40
bps, mean 2.08**. Caveat declared: the thin-tier rows are mostly SHADOW, i.e.
the ShadowBroker's book-walk model — a model that walks real depth, not a
measurement, and the best estimate available.

### Corrected result — the signal is real and equals its own cost

| universe | books | gross | cost | **net** | t(net) |
|---|---:|---:|---:|---:|---:|
| all tail (incl. dust) | 134 | +0.066% | 0.166% | −0.100% | −3.30 |
| **≥ $0.1M (tradeable)** | 85 | +0.054% | 0.054% | **+0.000%** | **+0.00** |
| $0.1–1M only | 64 | +0.023% | 0.050% | −0.027% | −0.78 |
| ≥ $1M | 21 | +0.089% | 0.065% | +0.024% | +0.28 |

On the tradeable universe: **net +0.0001%/4h, t=+0.00**, block-bootstrap 95% CI
**[−0.070%, +0.074%]**, P(net>0)=0.543. Dead on zero.

**But the gross signal is REAL**: random-ranking null gives **P(random ≥ actual)
= 0.0100** — the ranking carries information. And gross is positive in BOTH
halves (**+7.3 bps H1, +3.5 bps H2**) — decaying, not stable, with the 5.4 bps
cost sitting exactly between them, which is why *net* flips sign across halves.

### Verdict — a third instance of the same shape

Parts 2 and 4 found funding priced to zero. Part 6 finds the tail's reversal
signal priced to zero **by execution cost**. Three independent surfaces, three
different mechanisms, one conclusion: **this venue prices what the fleet can
currently see.**

### WHY THIS ONE IS STILL OPEN, AND THE OTHERS ARE NOT

The funding surfaces are closed because the *market* prices them. This one is
closed only by **the fleet's own execution choice**. Every bot crosses the
spread; Lighter's **maker fee is 0.0000**; the $0.1–1M tier's median spread is
**6.74 bps** against a 2.52 bps/fill crossing cost.

The arithmetic is now exact and decisive:

    gross signal   +5.4 bps / 4h period
    crossing cost  -5.4 bps           -> net 0.00, t=0.00   (measured)
    passive cost   -1.0 bps (if ~80% of the saving is captured)
                                       -> net +4.4 bps, positive in BOTH halves

**One unmeasured constant — the fleet's maker fill rate — decides whether this
surface is a book or a dead end.** It has never been measured because no bot has
ever placed a passive order (no `post_only`/`order_type` column exists in
`venue_orders`; 3,558 rows, all crossing).

### NEXT THREAD — unchanged, and now quantified

Measure passive-fill economics: resting at the touch, what fraction fills within
one 4h bar, and what is the adverse-selection cost of the fills you do get
(passive orders fill preferentially when price is about to keep moving against
you — that is the mechanism that would eat the spread saving). Needs 5m/1m tape
for the ~85 tradeable books. **Above ~4.4 bps of realised saving this becomes a
book candidate; below it, the tail closes too.**

---

## 2026-08-19 (Wed, Sydney) — PART 7: PASSIVE EXECUTION IS REFUTED — the fills you get are poisoned, and the only cell that looks good is the one where the fill model assumes away queue risk

The pre-registered decision rule from Part 6: *"above ~4.4 bps of realised
saving this becomes a book candidate; below it, the tail closes too and I'll say
so."* **It closes.**

Model (no look-ahead): the order is placed after bar *t* closes, resting at
`close(t)`; it fills during bar *t+1* iff the market trades there. `delta` is a
**touch-through margin** — price must trade THROUGH the level, not merely kiss
it, because at a bare touch you may sit behind the queue and never fill. Entry
at `close(t)` (better than the crossing entry at `close(t+1)`); exit still
CROSSES, which is conservative.

| execution | periods | fill L | fill S | gross | cost | **net** | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| CROSS both sides | 998 | 100% | 100% | +0.054% | 0.054% | **+0.000%** | 0.00 |
| **PASSIVE (touch, delta=0)** | 998 | **100%** | **100%** | +0.115% | 0.027% | **+0.088%** | **1.63** |
| PASSIVE (through 5 bps) | 998 | 89% | 88% | **−0.128%** | 0.027% | **−0.154%** | **−2.78** |
| PASSIVE (through 10 bps) | 997 | 86% | 85% | −0.183% | 0.027% | −0.210% | −3.69 |
| PASSIVE (through 20 bps) | 992 | 80% | 80% | −0.304% | 0.027% | −0.330% | −5.57 |

### The delta=0 row is a fill-model artifact, not a result

**A 100% fill rate is not a fill model — it is an assumption.** `low(t+1) ≤
close(t)` is true on almost every bar (any downward wiggle at all satisfies it),
so delta=0 hands the strategy the better of two prices for free, with zero queue
risk. That is where the +0.061% of "gross improvement" over crossing comes from.
Real passive orders always carry queue risk.

### The moment queue risk is priced at all, the sign INVERTS — and that is adverse selection, measured

At a 5 bps touch-through the fill rate is still **89% / 88%** — you are not
missing trades. **The trades you get are poisoned**: gross goes +0.054% →
−0.128%, an **18 bps swing**, and it deepens monotonically with the
touch-through requirement (−0.183%, −0.304%). Conditional on the market trading
through your resting bid, the forward return is strongly negative: you are
filled precisely on the names that keep going.

Robust, not a fluke: **H1 net −0.162% (t=−1.92), H2 net −0.151% (t=−2.08)** —
consistent across both halves, block-bootstrap 95% CI **[−0.251%, −0.047%]**,
P(net>0)=**0.002**.

### The spread saving is real and is swamped 7×

Passive halves the cost (0.054% → 0.027%, the exit-only charge). That saving is
**+2.7 bps**. The adverse selection is **−18 bps**. The lever works and is
pointed at the wrong problem.

### VERDICT — the last open surface closes

The Part 6 arithmetic assumed passive execution would capture most of the spread
at unchanged gross. **It does not: gross is not invariant to how you enter.**
The maker-fee-is-zero intuition is **REFUTED with a number** — do not re-run it
on this horizon without new evidence.

Declared limits: 4h OHLC with no queue model and no historical bid/ask; the
delta=0 sensitivity shows the model matters. But the direction is stable at
*every* non-degenerate setting and across both halves, and only the assumption
of zero queue risk produces a positive — so the honest read is negative.

Untested and still open (narrow): passive at a horizon where holding is long
enough to amortise adverse selection, and passive EXIT rather than entry.
Neither is promising given a −18 bps entry effect at 4h.

### WHERE THE DAY ENDS

Seven measurements, four surfaces, all priced:

| surface | blocker | status |
|---|---|---|
| funding — timing (Part 1) | variance; edge zero by construction | **closed** |
| funding — selection (Part 2) | funding = fair price for adverse selection | **closed** |
| the claim as a ranking signal (Part 3) | no predictive power (Spearman ≈ 0) | **closed** |
| funding tail, both directions (Part 4) | same pricing, opposite end of the range | **closed** |
| tail cross-sectional reversal (Parts 5–7) | gross real (null P=0.01), **consumed exactly by execution cost**; passive makes it worse | **closed** |

**The one thing that is real and unexploited**: the tail's cross-sectional
reversal ranking beats a random ranking at **P=0.0100**. It is a genuine signal
worth ~5.4 bps per 4h period, and every execution route measured costs at least
that much. A cheaper execution than "cross the spread" or "rest at the touch"
would monetise it — but the two obvious ones are now both measured and both fail.

---

## 2026-08-19 (Wed, Sydney) — PART 8: 🪁 BAND-KELLY'S FOUNDING CLAIM REPRODUCES EXACTLY AND SURVIVES JACKKNIFE — but it is OVERSTATED 34% by a double-slippage error, and the live book is accruing against the inflated bar

The fleet's largest measured claim, checked independently while the book is
**live with an open position** and 0 closes.

### It reproduces — exactly

From 🧲 the ghost's own ledger (`lighter-dislocation-lshadow`, n=189,
13-Jul → 4-Aug):

| slice | n | mean/trade | t |
|---|---:|---:|---:|
| ALL | 189 | −0.250% | −2.82 |
| **CRYPTO subset** | **65** | **−0.605%** | **−5.71** |
| non-crypto | 124 | −0.064% | −0.53 |

Claimed mirror: **n=65, +0.605%/trade, t=+5.71.** Exact match. Unlike `(nu)`
🧙 Schwager and `(nt)` 🧘 Douglas, **this founding number holds.**

### And it survives jackknife — the OPPOSITE of the fat-tail failure

The 65 trades are **60% KAITO** (39), APEX 15, then eight coins with ≤3 each.
Concentration that severe killed 🧙 Schwager. Here it does not:

| drop | n | mirror mean | t |
|---|---:|---:|---:|
| **KAITO (60% of trades)** | 26 | **+0.684%** | **+5.08** |
| APEX | 50 | +0.528% | +4.21 |
| every other single coin | 62–64 | +0.59 to +0.63% | +5.5 to +5.9 |

**No single coin carries it.** Dropping the dominant coin *raises* the mean.
This is the most robust claim in the fleet.

### The defect: mirroring a book credits you with ITS costs as YOUR profit

    ghost_realised = price_move − ghost_slip        (its P&L is already NET)
    mirror         = −price_move − mirror_slip
                   = −ghost_realised − (ghost_slip + mirror_slip)

**Negating a realised P&L does not give the mirror's realised P&L** — it hands
the mirror the ghost's execution cost as if it were profit, and forgets the
mirror pays its own. The correction is arithmetic, not a modelling choice:

| | mean/trade | t |
|---|---:|---:|
| NAIVE mirror (the founding claim) | +0.605% | +5.71 |
| **CORRECTED for double slippage** | **+0.397%** | **+3.58** |
| overstatement | **0.209 pp/trade — 34% of the claim** | |

*Sensitivity declared:* the correction uses CURRENT volumes (KAITO $0.42M →
2.52 bps/fill tier). Point-in-time volume is not reconstructable ((ny)), and
these coins sat in more liquid tiers earlier, so **34% is the conservative end**
— the direction is certain (the double-count is arithmetic), the size is not.

### Why this matters NOW

🪁 band-kelly is **live, 1 open position, 0 closes**, gradeable ~mid-Sep. When
it grades, its realised record will be compared against **+0.605%** — and at the
corrected **+0.397%** bar a perfectly healthy book would read as a 34%
underperformer. **The expectation should be corrected before the sample lands,
not after.**

This does not weaken the book. At +0.397%/trade, t=+3.58, jackknife-robust, it
remains the fleet's best-evidenced claim by a wide margin — and roughly **three
orders of magnitude** above the funding surface Parts 1–4 priced to zero.

### A reconstruction that FAILED, recorded so nobody repeats it

I first tried to verify this from the scout's published telemetry
(`prem_outliers` + `marks`, 10,052 snapshots). **It cannot be done:**
`prem_outliers` is **hard-capped at exactly 8 entries** per snapshot, so the
event feed is truncated to the most extreme handful, and **`classes` is EMPTY
before 5-Aug**, which silently dropped every pre-August event through the
crypto screen and produced an implausible in-sample n=0 — my own harness defect,
caught by the implausibility. The ghost's LEDGER is the right source (I14: the
record decides); the telemetry is too lossy to audit this claim independently.

### NEXT THREAD

Apply the double-slippage correction wherever the fleet mirrors a book. `(qf)`'s
roster refused `brkfade` and `dipfade` on numbers that were presumably computed
the same naive way — **a 34% haircut could flip a marginal refusal in either
direction**, and `dipfade` was admitted 18-Aug on an operator override at n=13.
Re-price the whole roster on the corrected arithmetic before its next review.

---

## 2026-08-19 (Wed, Sydney) — PART 9: THE MIRROR ROSTER RE-PRICED — the operator's `dipfade` override SURVIVES, and the haircut's size is governed by the GHOST'S COIN LIQUIDITY

Discharges the carried item from Part 8 / `(qw)`.

**A logical shortcut first:** the double-slippage correction always makes a
mirror WORSE, so it can only flip an ADMISSION into a refusal, never the
reverse. `brkfade` (refused) needs no re-check. Only the two LIVE entries were
at risk.

Ghost source: the Ticket Taker's own closes, lens parsed from `reason`
(`<side>-<lens>_<exit>`) — note `tag` is NULL on all 270 taker rows, so a
tag-based query silently returns nothing.

| lens | n | ghost mean | ghost t | naive mirror (CI lo) | **corrected (CI lo)** | verdict |
|---|---:|---:|---:|---:|---:|---|
| **dip** | 13 | −1.162% | −2.66 | +1.162% (+0.31%) | **+1.061% (+0.20%)** | **SURVIVES** |
| divergence | 203 | −0.252% | −1.10 | +0.252% (−0.20%) | +0.152% (−0.30%) | not viable |
| breakoutup | 42 | −0.017% | −0.03 | +0.017% (−1.25%) | −0.084% (−1.35%) | not viable |
| breakout | 10 | **+1.140%** | +1.23 | −1.140% (−2.95%) | −1.241% (−3.05%) | ghost WINS — mirror loses |

**The ghost reproduces exactly** (n=13, −1.162%, t=−2.66) and the naive mirror CI
reproduces the roster's published `[+0.28%, +2.05%]`. **Corrected, the lower
bound stays above zero at +0.20% — the 18-Aug operator override holds on the
corrected arithmetic.**

### The generalisable part: the haircut scales with the GHOST'S coin liquidity

| mirror | ghost's coins | haircut |
|---|---|---|
| **snapfade** | KAITO $0.42M, APEX $1.56M — thin | **34%** of the claim |
| **dipfade** | taker tickets on liquid books | **8.7%** of the claim |

The correction is `ghost_slip + mirror_slip`, so it is large exactly where the
ghost traded thin books. **A mirror of a thin-book loser is far less attractive
than the naive negation suggests; a mirror of a liquid-book loser is barely
affected.** That is the rule to carry, not the 34% number.

### Roster verdict

Both live entries survive correction, and no additional lens qualifies. The
roster as specified is CORRECT — `snapfade` at a corrected **+0.397%/t=+3.58**
and `dipfade` at **+1.061%, CI lo +0.20%** on an n=13 probe. What changes is the
EXPECTATION each should be graded against, not the membership.

### NEXT THREAD

Nothing carried from this one. The open board is unchanged from `(qq)`: four
surfaces priced, and the dislocation family — now the fleet's only
positively-evidenced surface — running one live book plus one $40 probe.

---

## 2026-08-26 (Wed, Sydney) — 🪁 BAND-KELLY'S NEGATION IDENTITY FAILS: BOTH SIDES OF THE SAME EVENT LOSE, AND THE BOOK'S OWN TELEMETRY SAYS THE INHERITED EXIT IS THE LEAK

**Full note: `reports/BAND_KELLY_NEGATION_IDENTITY_2026-08-26.md`**

### HYPOTHESIS

🪁 band-kelly is the fleet's newest positively-evidenced surface (`(rc)`
corrected founding claim **+0.397%/trade, t=+3.58**, snapfade) and it now reads
**−$25.42 on 229 closes**. Does the founding claim reproduce on the book's own
forward record, and if not, what is the mechanism?

Picked over the four carried `funding-studies-inherit-the-rank-universe`
re-derivations because this is a *live book with a large fresh sample
contradicting its own founding number* — decision-blocking (its ~mid-Sep grade)
and cheap (no tape fetch; the ledger carries `dev_at_entry_bps`,
`spread_bps_entry`, `held_h`, `family`, `ghost_side`).

### METHOD

Read-only Postgres: `paper_trades` for `band-kelly-lshadow` (n=229) and for its
ghost `lighter-dislocation-lshadow` (n=189), plus `bot_pnl.extra` for the live
`holdwatch`/`roster`. Bootstrap (20k) on the per-trade mean, cluster-robust `t`
on entry-loop clusters, split-half out-of-sample on every swept threshold.

### NUMBERS

**The claim is rejected by the record (I14).**

| | founding `(rc)` | LIVE |
|---|---:|---:|
| n | 65 | **216** (snapfade) |
| mean %/trade | +0.397 | **−0.025** |
| t | +3.58 | **−0.15** |
| win | 82% | **37.5%** |

Live 95% CI **[−0.335%, +0.290%]** — +0.397% is outside it. One-sided z=**−2.64**
vs the corrected claim, **−3.94** vs the uncorrected +0.605%.

**Four explanations tested, all REFUTED — do not re-run without new evidence:**

* **Deep-tail ceiling** (`|dev| <= 350bps` turns −$16.85 into +$8.61):
  **REFUTED out-of-sample** — h1 +0.179%, h2 **−0.120%**; 9 of 10 deep-tail
  events are in h1 and 7 inside four minutes on 22-Aug. Ceilinged subset
  bootstrap: +0.024%, CI [−0.184%, +0.242%], P(mean≤0)=0.420.
* **Non-independence inflating `t`**: **REFUTED** — cluster-robust t=**−0.26**
  vs naive −0.15, variance inflation **0.37x**, **n_eff 589 > n 216**. Clusters
  self-hedge; multi-coin clusters net **+$19.02**, solo entries net **−$35.88**.
  (Entries *are* clustered — 82% of multi-coin loops are all-same-side vs 41%
  expected — but it helps `t`, it does not hurt it.)
* **Execution cost as the cause**: **REFUTED as sufficient** — `conv` exits are
  −18.64bps; gross of the median 9.60bps half-spread round trip still
  **−9.04bps**. Spread relation is **U-shaped** (tightest quintile is second
  worst at −0.331%), OLS slope t=**−1.11**.
* **A cap breach** (peak 8 positions vs `MAX_POSITIONS=4`): **REFUTED — a
  measurement trap.** `opened_at` is loop-start `t0`, `closed_at` is wall-clock
  publish, and a scan pass takes ~2 min. The cap is correctly enforced.

**WHAT SURVIVES — the negation identity fails on 93% of both books' closes:**

| | n | mean %/trade | t | win |
|---|---:|---:|---:|---:|
| 🧲 ghost `converged` | 178 | **−0.230** | −3.10 | 43.3% |
| 🪁 mirror `conv` | 200 | **−0.186** | −3.38 | 35.0% |

Negation would predict the mirror at **+0.230%**. Gap **−0.417 pp/trade** —
independently equal to the record's shortfall against the claim (0.422 pp).
**Both sides of the same event lose.** Mechanism: the mirror inherited the
ghost's **exit** (`|dev| <= 40bps`) along with its entry gate, so it closes on
convergence — the ghost's thesis and the exact inverse of its own — on a
threshold its entry gate guarantees crossing. That is `(jh)`'s recorded death
mechanism for the ghost ("the book harvests its own entry gate"), inherited.

**THE WIN-MORE FINDING** — **[REFUTED 2026-09-02, corrected in place per I12.
Graded on this very instrument's fresh sample (the `n2` counter, which counts
only samples taken after this entry), every horizon INVERTS and the two that
motivated the widening are significantly negative: +60m **−1.227%/trade
t=−2.06**, +120m **−2.083%/trade t=−2.66** on n≈147. The decomposition
reproduces the four numbers below to three decimals, so the removed window is
exactly this one. Do NOT re-run the hold-longer widening without new evidence
— see the 2026-09-02 section at the end of this log and
`reports/KELLY_HOLDWATCH_GRADED_2026-09-02.md`. The paragraph is left standing
as the registration it was.]** — `extra.holdwatch`, live, n=218: extra %/trade from
holding past the book's own exit is **+15m −0.332 · +30m +0.044 · +60m +0.291 ·
+120m +0.324**, against a `conv` exit realising −0.186%. Median hold is **4.7
minutes**. Throughput is not the obstacle: occupancy is **0.12 of 4 slots
(3%)**, so a 12.8x longer hold implies ~1.5 slots — the widening costs no
entries. Caveats: the mean is vs a MID against a VWAP exit (optimistic ~5bps);
it is a continuation, not a replay; and **it had no dispersion**, so no `t`.

### VERDICT

**Founding claim REJECTED; book UNDECIDED, not proven bad** (t=−0.15, CI
straddles zero, ~31 closes/day). Not a retirement call. What changed is the bar
it should be graded against. Escalated to Eamon (I17): correct the published
expectation in place, pre-register a fresh-sample bar (t ≥ 2 on closes after
26-Aug), and gate the exit re-spec on `holdwatch` publishing a `t`.
`dipfade` (n=13, −1.852%/trade) is dying on its own record as designed.

**SHIPPED (telemetry only, no position differs):** `holdwatch_block` publishes
`sd_pct`/`t`/`win_pct`/`n2`, backward-compatible with pre-dispersion durable
buckets; `holdwatch_accumulate` extracted from the loop because the first
mutation round found the `n2` counter **unreachable from any test** (a
dispersion that silently never accumulates — I1/I23). 8/8 mutations killed on
re-run. `math` was unimported in the module — MY omission (nothing used it
until `sd`/`t` did), caught by reading the import block rather than by a red
test; recorded that way round so it is not read as a find.

### TRANSFERABLE

1. **A mirror is not a negation** — both sides of a round trip pay; grade a
   mirror on its own forward record, never on a ledger's arithmetic inversion.
2. **Inherit an entry, never an exit** — an exit encodes a thesis, and a
   mirror's is inverted. `(sa)`'s nav-cook lesson in a new costume.
3. **A mean with no dispersion is not a measurement.**
4. **Opens and closes can be on different clocks** — check before reporting a
   breach.

### NEXT THREAD

The four `funding-studies-inherit-the-rank-universe` re-derivations remain
carried and untouched (HANDOFF, owner: session). Nearer: once `holdwatch`
carries a week of `t`, the exit re-spec is a query, not a guess — and the same
"inherited exit" question should be put to 🧭 nav-cook, which mirrors the same
ghost in the [45,60)bps band and whose first 10.5h read 24 of 24 `converged`.

---

## 2026-09-02 (Wed, Sydney) — 🪁 BAND-KELLY'S HOLD-WATCH GRADED: THE (ub) WIN-MORE FINDING INVERTS ON ITS OWN FRESH SAMPLE, AND THE SIDE CUT THAT LOOKS SHIPPABLE IS AN ARTIFACT OF ITS OWN EXCLUSION RULE

**Full note: `reports/KELLY_HOLDWATCH_GRADED_2026-09-02.md`**
**Instruments: `scripts/study_kelly_holdwatch_2026-09-02.py`,
`scripts/study_kelly_side_2026-09-02.py`** (read-only; nothing shipped)

### HYPOTHESIS

`(ub)`'s pre-registered next thread, verbatim: *"once `holdwatch` carries a
week of `t`, the exit re-spec is a query, not a guess."* It recorded a
**win-more finding** on n=218 with no dispersion — extra %/trade from holding
past the book's own `conv` exit reading **+15m −0.332 · +30m +0.044 · +60m
+0.291 · +120m +0.324** — and argued the widening was free (occupancy 3% of 4
slots). That is I26's ship-by-default shape on a live book that cannot be
graded, gated only on the missing `t`.

A week later 🪁 band-kelly is **−$128.48 on 380 closes**, the fleet's largest
bleeder, clip cut $250 → $80 on 1-Sep `(vy)`, ~18-Sep grade. Decision-blocking,
and the instrument built for it is live. Picked over the four carried
`funding-studies-inherit-the-rank-universe` re-derivations on that basis.

### METHOD — AND THE ACCIDENT THAT MADE IT OUT-OF-SAMPLE

`holdwatch_block` counts dispersion on its OWN counter (`n2`/`sum2`/`sumsq`),
split from `n`/`sum` for an unrelated reason (a durable bucket restored from
before the field existed carries `n` without `sumsq`, and dividing the new
sumsq by the old `n` would understate sd on the longest-running horizons).

The side effect: **`n` pools all history, `n2` counts only samples taken since
26-Aug.** So `mean2 = t·sd/√n2` recovers the fresh sample and
`old_mean = (mean·n − mean2·n2)/(n−n2)` recovers the registration window.
**Calibration gate, fail-closed at 0.005pp:** the decomposition may only be
read if it reproduces the window it claims to have removed.

### NUMBERS

**The gate passes on all four horizons** — four independent reconstructions of
a four-number registration, to three decimals, from a counter nobody split for
this purpose: −0.3317/+0.0438/+0.2912/+0.3251 vs the recorded
−0.332/+0.044/+0.291/+0.324.

**The verdict on the fresh sample alone (I21 follow-through, I25 baseline):**

| horizon | registered | FRESH | n2 | t | |
|---|---:|---:|---:|---:|:--|
| +15m | −0.332 | −0.374 | 149 | −1.32 | inverts, ns |
| +30m | +0.044 | −0.398 | 149 | −1.11 | inverts, ns |
| +60m | **+0.291** | **−1.227** | 147 | **−2.06** | **inverts, sig** |
| +120m | **+0.324** | **−2.083** | 145 | **−2.66** | **inverts, sig** |

Gap at +120m: **2.41 pp/trade** against the registration. Strengthening it:
the extra is priced at a **MID** against a **VWAP** exit, so the true figure is
worse; it is **monotone in the direction of harm**; `(ub)` measured variance
inflation **0.37×** on this book (n_eff 589 > n 216 — clusters self-hedge), so
cluster-robust is *more* negative; and it held across a live refresh mid-session
(+60m t −2.06 → −2.08).

**The record agrees (I14):** pre-26-Aug n=229 mean −0.13%/t=−0.79 (reproducing
`(ub)`'s own 216 snapfade + 13 dipfade split exactly); **post-26-Aug n=151 mean
−0.27%/t=−0.81** — the book got worse over the window in which holding longer
would have had to be earning.

**DECLARED LIMIT:** `holdwatch` publishes aggregates only, so **drop-worst is
structurally impossible**. One −50% sample moves the fresh mean 0.34pp — which
does not reach +60m's 1.52pp or +120m's 2.41pp reversal, but is the whole of
the two thin cells. Read the two significant horizons only.

### THE SECOND REFUSAL — A SIDE CUT THAT LOOKS SHIPPABLE AND IS NOT

Honest cell (`snapfade` `conv`, outcome-conditioned families dropped per I21):
**short-snap_conv n=99, −0.731%/trade, t=−4.32, both halves negative, survives
drop-3-worst at −0.540%**; long-snap_conv n=185, −0.097%, t=−1.42. Dollars
agree: short −$153.96 vs long +$24.69 of a −$129.26 book.

**REFUSED.** A verdict must exclude outcome-conditioned exits; **a side cut
removes the side's whole ledger, tails included**, and the sides do not take
them in equal proportion — short `ghoststop` **Σ+212.4 pct-points** and short
`stop` **Σ−203.7** nearly cancel (net +8.7) and are each ~**8×** the `conv`
centre's −72.4. Put them back:

**short side, all exits: n=190, mean −0.4229%/trade, t=−1.35 — NOT
significant.** ex-3-worst **t=−0.84**, ex-5-worst **t=−0.52**.

`t=−4.32 → −1.35 → −0.52`. The short side is **undecidable by tail** ((po)'s
class, at the *side* level), not a measured loser. The long side is undecided
and **sign-unstable** across the boundary (h1 −0.002 → h2 +0.283) — I25's own
signature, not a winner.

### VERDICT

**REFUTED, with the measured harm I26 requires of a refusal.** The hold-longer
widening is dead — do not re-run it. **No side cut.** **Nothing shipped**: no
lever, no proposal, no position differs. `(ub)`'s win-more paragraph is
corrected in place above per I12.

Consequence for the ~18-Sep grade: `(ub)` left the book "UNDECIDED, not proven
bad" *with a live win-more lever outstanding*. **That lever is gone**, so
18-Sep is a genuine I17 keep-or-decide call, not a checkpoint on a pending fix.

### VERIFICATION

Calibration gate mutation-tested, **3/3 correct**: registration constant
perturbed ⇒ refuses; `√n2` → `n2` in the t inversion ⇒ refuses — and that
mutation yields a *plausible* −0.173% fresh mean that would have been believed
without the gate; unpriceable cells return **None, never 0** (I6).

### TRANSFERABLE

1. **The cell you must EXCLUDE to reach a verdict is the cell you must INCLUDE
   to price a decision.** Here the two readings disagree by 3.8 t-units. An
   exit census is not a decision surface.
2. **A dispersion counter split for a compatibility reason is an
   out-of-sample boundary for free** — look for one before assuming a
   registration cannot be graded on the instrument that recorded it.
3. **A mean with no dispersion is not a measurement** ((ub)'s own lesson,
   now with the price attached: the two cells it acted on both flipped sign).
4. **Reconstruct the registration before grading it.** Four exact
   reproductions are what license reading the residual; mutation 2 shows what
   an unlicensed residual looks like.

### NEXT THREAD

1. **The stop asymmetry — unmeasured, and the largest number in this book.**
   Both stops sit at 5% by construction, yet realise **−6.79%** and **+5.90%**:
   the loss side overshoots by 1.79pp while the win side falls 0.90pp short,
   **−0.89pp per stop-pair event over 66 events**. If that is gap-through on
   the adverse side it is a *cost* finding on the fleet's own fills. Needs fill
   data, not the ledger.
2. **🧭 nav-cook cannot be asked `(ub)`'s sibling question — it has no
   `holdwatch`** (verified: 0 references in `lighter_nav_cook_bot.py`, absent
   from its live `extra`). **The prior has moved against porting it**: the one
   book that measured the hold-longer thesis refuted it, so a port is a
   measurement, never a step toward a widening.
3. The four `funding-studies-inherit-the-rank-universe` re-derivations remain
   carried and untouched (HANDOFF, owner: session).

---

## 2026-09-09 — THE REGIME SHORT-VETO READ: TAKEN EARLY, AND UNIDENTIFIED

### HYPOTHESIS

The edge audit's #3, pre-registered 2-Sep 09:30Z as
`scripts/study_regime_short_veto_2026-09-02.py`: *a short opened while the
`regime_oracle` reads `LONG-window` (or a long in `SHORT-window`) loses, and
vetoing those trades would raise the book's mean.*

**Picked because its SAMPLE trigger had fired and nothing was measuring it** —
the `(yo)` lesson three days after it was written. Registered bar: n≥30 in the
largest living vetoed set, or the 16-Sep date backstop. 🪁 kelly's vetoed set
had reached **73**. The two sibling registrations were checked and left: the
taker hold floor needs an up-resolver this environment's egress refuses, and
🎫 the taker is now READY so its bracket is frozen anyway; 👩 mum's non-crypto
sleeve is at 4 entry days against a floor of 10.

### METHOD

Ledger: the paper feed through the grader's own pipeline — **4,478 closes**,
verified NOT truncated against its 5,000 cap. Oracle: the **full** history from
Postgres, **3,020 snapshots 11-Jul → 9-Sep**, where the public bus caps at
200h (which is why the registration's own declared limit read "418 of 418").
Both cached locally so every number reproduces offline.

New instrument, because the registered one cannot ask this of itself:
`scripts/study_regime_veto_identifiability_2026-09-09.py` — Cramér's V between
label and side, the **within-side** comparison (label varies, side fixed), and
a **circular rotation null** on the oracle's verdict series (same marginals,
same autocorrelation, no relation to returns — the null that killed the
long-side filter on 7-Sep; a scatter null is too easy on an autocorrelated
label). Calibrated: it recovers a planted within-side effect at P≤0.05 and
refuses a placebo.

### NUMBERS

**What the registered rule said** (fresh window):

| book | n | veto n | veto mean% | ub% | pass n | pass mean% | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| 🪁 kelly | 257 | 73 | −0.3115 | **+0.0066** | 184 | −0.0067 | undecided |
| 🚀 bezos | 37 | 31 | −0.8304 | **−0.1873** | 6 | −0.4610 | **confirmed** |

**Why neither reading is interpretable — one number.** BTC read `LONG-window`
in **351 of 351** post-registration snapshots, and crypto rides BTC by the
declared proxy, so *"short in LONG-window"* ≡ *"short"*:

| book | long/pass | long/veto | short/pass | short/veto | V |
|---|---:|---:|---:|---:|---:|
| 🪁 kelly | 182 | 0 | 2 | 73 | **0.981** |
| 🚀 bezos | 6 | 0 | 0 | 31 | **1.000** |

**Zero identified cells fleet-wide** at n≥10. Adopting on 🚀 bezos would remove
**83.8% of its closes**, leaving 6 — an off-switch, not a filter.

**The identified test** (pooled window, where BTC does vary — SHORT 1,300 /
LONG 961 / chop 458 / flat 301), precision-weighted (veto − pass), hypothesis
predicts NEGATIVE:

| population | cells | observed | null p05/med/p95 | **P** |
|---|---:|---:|---|---:|
| all books | 11 | **+0.221 pp** | −0.184 / +0.070 / +0.392 | **0.858** |
| living only | 5 | **+0.294 pp** | −0.135 / +0.046 / +0.240 | **0.983** |
| ⚖️ counterweight (best of N) | 2 | −2.268 pp | −5.12 / −0.99 / +5.01 | 0.310 |

Six cells support, five contradict. Floor sensitivity checked: at min-cell 3
one cell appears (P=0.972), at min-cell 2 two appear (P=0.923) — lowering the
floor does not rescue it.

**THE POOLED NULL IS AN ABSENCE OF POWER, NOT A REFUTATION — the adversarial
pass corrected my first framing here and it matters.** Across the 11 cells:
Cochran's Q = 16.70 (df 10), **I² = 40.1%**, tau² = 0.313, so a fixed-effect
summary is inadmissible; **random-effects +0.109 pp, SE 0.308, z = +0.35,
MDE80 = 0.862 pp**. The hypothesised effects were farmer −0.640, kelly −0.410,
garrett −2.409, counterweight −4.044 %/trade — **detectable for the two large
ones, no power at all for the two that matter operationally.**

So the honest sentence is narrower than "the mechanism fails": **no identified
comparison anywhere in the fleet is powered to detect the effect that was
hypothesised, and the registered window contains no identified comparison at
all.**

**"The two largest cells run backwards" is WITHDRAWN** (not softened): that
ranking is by the veto arm; by effective n — 1/(1/n_v+1/n_p), which bounds a
two-sample comparison — kelly falls to 8th and #2 by power is the farmer
shadow's shorts at −0.722 pp, running WITH the hypothesis. All 11 cells split
**6 with / 5 against**: a coin flip. kelly's shorts +0.830 pp at permutation
**P = 0.220**; georgia's longs +0.324 pp at **P = 0.127** — directions, not
results.

**Two pooled confirms survive the guard and BOTH ARE RETIRED BOOKS** (douglas
−0.196 pp, farmer-shadow −0.722 pp). **And  on every living book
on the fresh window** — a "long in SHORT-window" needs a SHORT-window verdict
and there was none — so half the hypothesis has zero fleet-wide support and any
adoption would be a shorts-only rule, i.e. a side cut, on the real-money books
included.

### VERDICT — **NOT IDENTIFIED**, and the two books fail differently

🪁 kelly is unidentified by DEGREE (2 discordant rows of 257, both running
*against* the hypothesis). 🚀 bezos is **not estimable as ALGEBRA**: min-cell = 0
exactly, the veto set IS the short set row-for-row,  has
**rank 2 of 3**. Its  was carried by **three trades** (worst 3 of 31 =
49.4% of the vetoed total; drop two and the ADOPT stops) on a **7-day-old book
with no shadow twin** — so the registration's CONFIRMED branch ("graded against
its un-gated twin") was unexecutable on it regardless. **Nothing adopted, no
lever moved, no book changed.**

`not_identified` and `not_corroborated` land in the registration's own third
branch, so **no amendment was needed to honour this** and exactly ONE re-arm
remains. **Re-armed conditionally, with a METHOD requirement:**
* fires when BTC leaves `LONG-window`, or on the 16-Sep backstop;
* **no session may quote a probability for that turn** — the oracle's 59-day
  history holds seven runs and exactly ONE `LONG-window` run, the current open
  19.50-day one, already longer than the longest *completed* run of any kind.
  Zero completed LONG runs = no distribution;
* **the cell a turn produces must be DAY-PAIRED before it counts** — on a
  single-regime tape the label IS the calendar epoch, so the identified cell
  everyone is waiting for arrives confounded with time by construction (I25).
  "Wait, then day-pair it", never "wait, then re-run";
* **if there is still no variance at that read, CLOSE the registration as
  untestable** rather than re-arming again.

**AN ORDERING CONSTRAINT NOBODY HAD WRITTEN DOWN.** 🪁 kelly's own keep-or-retire
read was taken 7-Sep and **RETURNS TO EAMON** — undecided, with him now. A short
veto on her removes **73 of 257 fresh closes (28%)** on exactly the side that
verdict turns on, so adopting one first **re-specifies the book mid-registration
and voids the 7-Sep read** — the (tt) failure I21 was amended for. **Order:
Eamon's decision first, any veto second.**

### SHIPPED (the class, not the instance)

The rule **could not tell a regime measurement from a side cut** and would have
said `confirmed` again. Two preconditions now sit in front of the registered
bars, both strictly conservative — each can only withdraw a verdict the
confounded comparison would have produced, never create one:

* `identifiability()` — a verdict needs some side carrying BOTH labels at n≥10,
  else `not_identified` with the contingency table as its reason.
* the **corroboration gate** — a `confirmed` is withdrawn when the identified
  comparison contradicts it (kelly pooled: `confirmed` across sides while its
  own within-side cell ran backwards by +0.830 pp). It deliberately does NOT
  gate `refuted`.

Live-payload result: 🚀 bezos `confirmed → not_identified`; 🪁 kelly fresh
`undecided → not_identified`; 🪁 kelly pooled `confirmed → not_corroborated`;
🧘 douglas pooled **stays confirmed** (its cell agrees). It discriminates.
Mutations: **6/6** parent, **9/9** new instrument.

### VERIFICATION

Six independent adversarial lenses (collinearity statistic, side-label
correctness, oracle-coverage alternative, floor sensitivity, pooled direction,
instrument correctness). **All six: STANDS_WITH_CAVEAT — none refuted**, with
the key tables reproduced exactly and independently (V 0.9812 / 1.0000;
bias-corrected V identical, so not small-sample inflation). Their caveats are
folded into the numbers above rather than appended.

### MY OWN DEFECTS, recorded

1. **The corroboration gate shipped INERT for one round** — `grade_book` handed
   `identifiability()` bare counts, so it read "unpriceable" on every real book
   while the selftest (calling the function directly with means) stayed green.
   Caught by running the guard against the live ledger. Wiring now pinned
   end-to-end.
2. **`any` vs `all` across cells survived a mutation round** — settled as
   `all` (the veto acts on both sides).
3. **`since` and the pass-side floor were unpinned** in the new instrument —
   found by review, now pinned with boundaries.
4. **The registered read's own documented command did not run.** HANDOFF and
   session_state both say "run it with `--fresh`", and `--fresh` existed on
   **none of the three** registered instruments (this one, the taker hold
   floor, mum's non-crypto sleeve) — the flags are `--since`/`--pooled`. A
   pre-registered read whose documented invocation errors is the (po)
   check-that-inspects-nothing shape one step earlier, and it is how a re-arm
   gets run on the wrong window. Fixed on all three; they also **refuse
   `--fresh --pooled` together** rather than silently preferring one.
5. **`within_side_agrees` is a SIGN, not a test** — three of the four verdicts
   the corroboration gate touches rest on |z| < 1. Safe because
   one-directional; declared in the code so it is never read as corroboration
   in the ordinary sense. The `precondition` key added to `PRE_REGISTERED`
   today is likewise named for what it is: a mid-flight amendment, declared,
   conservative-only, registered thresholds untouched — the acceptable form of
   an I21 boundary case.

### TRANSFERABLE

1. **A verdict needs a comparison in which the TREATMENT varies and the
   confound does not.** A rule can be perfectly calibrated and still be
   measuring something else — `decide()` was correct arithmetic on an
   unidentified contrast.
2. **A pre-registered instrument should record what its own window can and
   cannot separate.** This registration DECLARED the exposure in prose ("the
   pass set for crypto shorts is empty") and had no code that could act on it —
   the `(gk)`/`(iz)` shape again: a defense that lives only in prose has not
   been written.
3. **The public bus's 200h cap was load-bearing.** The registration's "418 of
   418" was an artifact of the feed, not the oracle; the database holds 3,020
   snapshots with real variation. Check the reach of your data source before
   declaring a limit of nature.
4. **Direction is not a result.** Two backwards cells at P=0.22 and P=0.13 are
   a sign; the aggregate against a proper null is the finding.

### NEXT THREAD

0. **IF A NEXT READ IS POINTED ANYWHERE, IT IS ⚖️ COUNTERWEIGHT, NOT 🪁 KELLY.**
   It is the only LIVING book whose identified cells agree on BOTH sides (long
   −3.258 pp at z=−1.82, short −0.596 pp at z=−0.26) with genuinely balanced
   labels (V = 0.056), it is the fleet's canonical always-in basket book, and it
   already carries its own pre-registered 1-Oct read to hang this on.
1. **ORACLE COVERAGE — MEASURED THE SAME NIGHT, AND THE OBVIOUS FIX IS
   REFUSED WITH A NUMBER.**

   **The gap is real and large.** Fleet closes opened since 1-Aug: **2,511
   across 150 distinct coins**, of which **1,554 (61.9%) are on coins the
   oracle does not grade** — 121 of the 150. The top of the gap by close count
   is USELESS 163, SKR 94, PUMP 93, SKHYNIXUSD 89, TRUMP 73, LIT 67, ENA 65,
   ZRO 64, ARB 61, VVV 56.

   **But "add them to `UNIVERSE`" is REFUSED, and the reason is structural.**
   `regime_oracle.UNIVERSE` is doing double duty: it is both the per-coin
   verdict map AND the majors basket behind **`fleet.read`**. `summarize()`
   defines the crypto set by **EXCLUSION** — `crypto = {k: v for k, v in
   pairs.items() if k not in NONCRYPTO}` — so **any coin added to the graded
   set automatically gets a vote on `fleet.read`**; there is no third category.
   And that vote is on ABSOLUTE COUNTS calibrated for a 16-coin basket:
   `read = "risk-off downtrend" if n_short > n_long and n_short >= 4 else
   "risk-on uptrend" if n_long > n_short and n_long >= 4 else "mixed"`.
   Adding 121 coins to a 16-coin basket does not widen coverage, it **hands
   memecoins a majority vote on a threshold tuned for majors** — and
   `fleet.read` is consumed by `bot_learn`'s risk_off history join (the Georgia
   "100% of losses in risk-off" diagnosis came from it) and, in the module's
   own words, **"gates real entries via the (bc) regime gate."** That is the
   I18/I7 shape exactly: the knob that reaches the thing you want also steers
   something else.

   **THE CORRECT SHAPE, and its precedent is in the same file.** A THIRD
   category — coins graded and PUBLISHED per-asset but excluded from
   `summarize()`'s crypto set — which is precisely how `NONCRYPTO` already
   works there (*"NOTHING consumes these entries yet, and `fleet.read` stays
   CRYPTO-ONLY"*). Whoever builds it owes: a selftest pinning that `fleet.read`
   is **byte-identical** with the new list populated, and a mutation round on
   that pin, because the exclusion is the entire safety of it.

   **PRICED.** The fetch loop is `for coin in list(UNIVERSE) + list(NONCRYPTO)`
   — one candle fetch per coin per cycle. Covering the traded gap takes it from
   **~26 to ~147 coins**, i.e. **≈7 minutes of every 30-minute cycle** at the
   measured ~21 fetch/min Lighter throttle. Feasible, but a 5.7× load increase
   that should be a deliberate decision, not a side effect.

   **NOT BUILT TONIGHT, deliberately (I11).** It is a change to an organ whose
   output gates real entries, arriving at the tail of a session whose own
   hypothesis is already shipped. Opening it here would be the second half-built
   house. The measurement, the refusal and the design are recorded so the next
   session starts from the answer rather than from the idea.
2. The 🎫 taker hold-floor registration still needs its container-side run (the
   up-resolver); 👩 mum's non-crypto sleeve is at 4 of 10 entry days.
3. **Do NOT re-run the naive veto-vs-pass comparison.** It is now guarded, and
   the identified version is measured at P=0.858.
