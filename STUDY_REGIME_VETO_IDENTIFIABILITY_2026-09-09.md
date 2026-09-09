# The regime short-veto read is UNIDENTIFIED on its own window — and no
# identified comparison anywhere in the fleet is POWERED to test it

**9-Sep-2026.** The pre-registered read for the edge audit's hypothesis #3
(`regime-short-veto`, registered 2-Sep 09:30Z) was TAKEN today, three days
ahead of its 16-Sep date backstop, because its sample trigger had fired —
the `(yo)` lesson that *the date is the backstop, not the trigger.*

**Instruments.** `scripts/study_regime_short_veto_2026-09-02.py` (the
registered rule, unchanged in its bars) and a new one built to answer the
question the first cannot ask of itself,
`scripts/study_regime_veto_identifiability_2026-09-09.py`.
Sample: the paper ledger through the grader's own pipeline (4,478 closes,
NOT truncated against a 5,000 cap) and the regime oracle's **full** history
from the database — **3,020 snapshots, 11-Jul → 9-Sep**, where the public
bus caps at 200h. Everything below reproduces offline from those two files.

---

## 1. THE READ, AS THE REGISTERED RULE COMPUTES IT

Two books reached the `n >= 30` vetoed-set floor on the fresh window:

| book | n | veto n | veto mean% | ub% | pass n | pass mean% | book mean% | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 🪁 band-kelly | 257 | 73 | −0.3115 | **+0.0066** | 184 | −0.0067 | −0.0933 | undecided |
| 🚀 book-bezos | 37 | 31 | −0.8304 | **−0.1873** | 6 | −0.4610 | −0.7705 | **confirmed** |

kelly missed the ADOPT bar by **0.0066 pp** of upper bound. bezos cleared it.
Taken at face value, the rule said: adopt the veto on 🚀 bezos.

## 2. WHY BOTH READINGS ARE UNINTERPRETABLE

**The treatment had no variance on its own window.** BTC read `LONG-window`
in **351 of 351** snapshots after the registration stamp. Every crypto coin
rides BTC's verdict by the declared `btc-proxy` rule, so on this window
*"short in LONG-window"* and *"short"* are the same predicate.

The contingency tables say it outright:

| book | long/pass | long/veto | short/pass | short/veto | Cramér's V |
|---|---:|---:|---:|---:|---:|
| 🪁 kelly | 182 | 0 | 2 | 73 | **0.981** |
| 🚀 bezos | 6 | 0 | 0 | 31 | **1.000** |

V = 1.000 means the label **is** the side. The rule's `decide()` compares the
vetoed set against the passed set, so on bezos it compared **31 shorts against
6 longs** and called the result a regime finding.

**This fleet already knows shorts lose** (EDGE_AUDIT §1b: every mixed book's
loss is its short side) and **already refused to act on it** — the 2-Sep entry
in this log measured 🪁 kelly's short side as undecidable by tail, t = −4.32 →
−1.35 → −0.52 once outcome-conditioned exits and the three worst closes go
back in. An unguarded `confirmed` here would have re-shipped that refused side
cut under a new name.

**Fleet-wide on the fresh window there are ZERO identified cells** — no book
has BOTH labels reaching n ≥ 10 inside one side, so there is no comparison
anywhere in which the label varies and the side does not. (Floor-relative, and
checked: at min-cell 3 one cell appears and reads P = 0.972 against the null;
at min-cell 2 two cells appear and read P = 0.923. Lowering the floor does not
rescue it. Only bezos has a structurally empty off-diagonal.)

**And acting on it would have been an off-switch, not a filter.** Adopting the
veto on 🚀 bezos removes **31 of its 37 closes (83.8%)**, leaving **6** — a
book that can no longer be graded at all, against I17 and I22.

## 3. THE IDENTIFIED TEST, WHERE ONE EXISTS

The pooled window (11-Jul → 9-Sep) does contain regime variation — BTC reads
SHORT-window 1,300 / LONG 961 / chop 458 / flat 301 — so the within-side
comparison exists there. **Eleven cells** qualify at n ≥ 10 on both labels.

Statistic: precision-weighted mean of (veto − pass) across cells. The
hypothesis predicts **NEGATIVE**. Null: the oracle's whole verdict series
**circularly rotated** against its own timestamps — identical marginal
frequencies, identical autocorrelation, no relationship to returns. (This is
the null `study_regime_split_2026-09-07.py` used to refuse the long-side
regime filter; a scatter null is too easy because a regime label is
autocorrelated and a real filter removes a contiguous block.)

| population | cells | observed diff | null p05 / median / p95 | **P** |
|---|---:|---:|---|---:|
| all books | 11 | **+0.2211 pp** | −0.184 / +0.070 / +0.392 | **0.858** |
| living books only | 5 | **+0.2940 pp** | −0.135 / +0.046 / +0.240 | **0.983** |
| ⚖️ counterweight alone (best case) | 2 | −2.268 pp | −5.12 / −0.986 / +5.01 | 0.310 |

**The sign is wrong and the null is not crossed.** Six cells support the
hypothesis, five contradict it. Even the single most favourable book —
⚖️ Counterweight, the one book whose labels are genuinely balanced
(V = 0.056), with both cells pointing the right way — reads P = 0.310 against
a null whose own median is already −0.99, and it was selected as best-of-N,
which I25 prices at roughly 1.85 t-units.

**THE POOLED NULL IS AN ABSENCE OF POWER, NOT A REFUTATION — and this is the
sentence the first draft got wrong.** A null with no MDE beside it is
uninterpretable. Across the 11 cells: Cochran's Q = 16.70 (df 10), **I² =
40.1%**, tau² = 0.313, so a fixed-effect summary is inadmissible.
Random-effects: **+0.109 pp, SE 0.308, z = +0.35, MDE80 = 0.862 pp.** The four
effects the edge audit hypothesised are 💸 farmer −0.640, 🪁 kelly −0.410,
🛢️ garrett −2.409, ⚖️ counterweight −4.044 %/trade — so this design could have
detected the two LARGE ones and **had no power at all for the two that matter
operationally.**

So the honest statement is narrower than "the mechanism fails": **no identified
comparison anywhere in the fleet is powered to detect the effect that was
hypothesised, and the registered window contains no identified comparison at
all.**

The individual cells are a DIRECTION, not a result, and the earlier framing of
"the two largest run backwards" is **withdrawn** rather than softened: that
ranking is by the VETO arm, and ranking by effective n — 1/(1/n_v + 1/n_p), the
quantity that actually bounds a two-sample comparison — puts 🪁 kelly **8th**
at 12.4, while second by power is 💸 the farmer shadow's shorts at −0.722 pp,
running **WITH** the hypothesis. Across all 11 cells the split is **6 with / 5
against** — directionally a coin flip. (For the record, kelly's shorts do read
veto −0.357% (n=258) vs pass −1.187% (n=13), +0.830 pp, robust to trimming and
spread over 23 coins and 20 days — at permutation **P = 0.220**, z = +1.01.
🔮 georgia's longs read +0.324 pp at **P = 0.127**.)

**TWO POOLED CONFIRMS SURVIVE THE GUARD, AND BOTH ARE ON RETIRED BOOKS** —
🧘 douglas (short cell −0.196 pp) and 💸 the farmer's shadow (−0.722 pp). That
is the single most useful summary of where the hypothesis stands: every pooled
confirmation that survives identification is on a book the fleet no longer
runs.

**AND HALF THE HYPOTHESIS HAS ZERO FLEET-WIDE SUPPORT.** On the fresh window
`long/veto = 0` on **every living book without exception** — mum-live 0/36,
mum-shadow 0/36, avo-live 0/6, avo-shadow 0/6, georgia-v3 0/76, taker 0/43,
carry 0/3, counterweight 0/4, albanese 0/17, turnbull 0/2, sniper 0/2, kelly
0/182, bezos 0/6. A "long in SHORT-window" needs a SHORT-window verdict, and
there was none. **Any adoption would therefore be a shorts-only rule — a side
cut — including on the two real-money books.**

## 4. VERDICT

1. **The pre-registered read is NOT IDENTIFIED on its own window** — and the
   two books fail differently, which matters. 🪁 kelly is unidentified as a
   matter of DEGREE (2 discordant rows of 257, and both run *against* the
   hypothesis). 🚀 bezos is **not estimable as ALGEBRA**: min-cell = 0 exactly,
   the veto set IS the short set row-for-row, and the design matrix
   `[1, is_short, is_veto]` has **rank 2 of 3**, so the label coefficient does
   not exist. Its `confirmed` must not be acted on.
2. **No identified comparison anywhere is powered** (random-effects MDE80 =
   0.862 pp against motivating effects of 0.41–0.64 pp on the books that
   matter). The pooled window is a coin flip, 6 cells with / 5 against, and the
   only confirmations that survive identification are on **retired** books.
3. **Nothing was adopted, no lever moved, no book changed.**

**Disposition, following the registration's own third branch** — `not_identified`
and `not_corroborated` both land in *"else record the numbers and re-arm one
more read (P3: at most twice)"*, so **no amendment to the registration is needed
to honour this**, and exactly ONE re-arm remains.

**Re-armed ONCE, conditionally, with a method requirement attached:**
* it fires when the oracle shows BTC leaving `LONG-window`, or on the 16-Sep
  backstop;
* **there is no base rate for that turn and no session may quote one.** The
  oracle's 59-day history holds SEVEN runs — SHORT 10.48d, flat 3.00d, SHORT
  15.01d, flat 1.99d, chop 9.00d, flat 1.01d, LONG **19.50d and still open**.
  There is exactly ONE `LONG-window` run in the whole history, it is the
  current one, and it is already longer than the longest *completed* run of any
  kind. **Zero completed LONG runs = no distribution.**
* **the cell that a regime turn produces must be DAY-PAIRED before it counts.**
  On a single-regime tape the label IS the calendar epoch: after a flip every
  `short/veto` row is dated before it and every `short/pass` row after, so the
  identified cell everyone is waiting for **arrives confounded with time by
  construction** — the exact I25 shape. The instruction is "wait, then day-pair
  it", never "wait, then re-run".
* **if the window still has no variance at that read, the registration CLOSES
  as untestable rather than re-arming again.**

**AN ORDERING CONSTRAINT THAT WAS WRITTEN NOWHERE.** 🪁 kelly's own
keep-or-retire read was taken 7-Sep (n=233, mean −0.044%, ub +0.125%) and
**RETURNS TO EAMON** — it is sitting with him undecided. Adopting a short veto
on her would remove **73 of her 257 fresh closes (28%)**, and her shorts are the
side that verdict turns on. Doing that before he decides **re-specifies the book
mid-registration and voids the 7-Sep read** — precisely the `(tt)` failure I21
was amended for. **The order is: Eamon's decision first, any veto second.**

**IF A NEXT READ IS POINTED ANYWHERE, IT IS ⚖️ COUNTERWEIGHT, NOT 🪁 KELLY.** It
is the only LIVING book whose identified cells agree on both sides (long −3.258
pp at z = −1.82, short −0.596 pp at z = −0.26; labels genuinely balanced at
V = 0.056), it is the fleet's canonical always-in basket book, and it already
carries its own pre-registered 1-Oct read to hang this on.

## 5. WHAT SHIPPED — the class, not the instance

The defect is not that the rule got one book wrong; it is that **the rule could
not tell a regime measurement from a side cut**, and would have said
`confirmed` again on the next read. Two preconditions now sit in front of the
registered bars, both **strictly conservative — each can only withdraw a
verdict the confounded comparison would have produced, never create one**, so
neither loosens the registered ADOPT threshold:

* **`identifiability()`** — a verdict requires that some side carries BOTH
  labels at n ≥ 10. Otherwise `not_identified`, with the contingency table
  printed as the reason.
* **The corroboration gate** — a `confirmed` is withdrawn when the identified
  comparison **contradicts** it. `identified` alone was not enough: on the
  pooled window 🪁 kelly read `confirmed` (vetoed ub −0.049% on n=258) while
  its own within-side cell ran backwards by +0.830 pp. It deliberately does
  **not** gate `refuted` — a contradicting cell is evidence *for* refutation,
  so blocking that direction too would be a bias, not a guard.

Measured after, on the live payload: 🚀 bezos `confirmed → not_identified`,
🪁 kelly fresh `undecided → not_identified`, 🪁 kelly pooled
`confirmed → not_corroborated`, 🧘 douglas pooled **stays `confirmed`** (its
within-side cell agrees at −0.196 pp). The guard discriminates; it is not a
blanket refusal.

## 6. DEFECTS FOUND IN MY OWN WORK WHILE BUILDING THIS

Recorded because each would have produced a confident wrong number:

* **The corroboration gate shipped inert for one round.** `grade_book` passed
  `identifiability()` bare COUNTS, so it read `within_side_agrees: None`
  (unpriceable) on every real book and the gate could never fire — while the
  selftest, which called the function directly with means, stayed green.
  Caught by running the guard against the live ledger, not the suite. The
  wiring is now driven end-to-end in the selftest.
* **`any` vs `all` across multiple identified cells survived a mutation
  round.** Settled deliberately as `all`: the veto acts on BOTH sides, so a
  cell showing it *hurts* one side is material even when the other agrees.
* **An adversarial review found the `since` filter and the pass-side half of
  the cell floor unpinned** in the new instrument (correct in the shipped
  code, untested). Both now pinned, boundary included.

**A FOURTH, found by the review and fixed here: the registered read's own
documented command did not run.** Both `HANDOFF.md` and `session_state.py`
instruct the reader to *"run it with `--fresh`"*, and `--fresh` did not exist on
**any of the three** registered instruments (this one, the taker hold floor,
mum's non-crypto sleeve) — the flags are `--since` / `--pooled`. A
pre-registered read whose documented invocation errors is the `(po)`
check-that-inspects-nothing shape one step earlier, and it is exactly how a
re-arm gets run on the wrong window. All three now accept `--fresh` (it names
the default, registered read) and **refuse `--fresh --pooled` together** rather
than silently preferring one.

Mutation rounds: **6/6** on the parent's precondition + corroboration gate,
**9/9** on the new instrument (including an equivalence pin that the O(1)
anchored labelling is byte-identical to naively rotating the whole oracle, at
five rotations).

## 7. DECLARED LIMITS

* **The oracle grades 31 coins with its own verdict; everything else rides the
  BTC proxy.** 🪁 kelly's fresh basis is 251 proxy / 6 own, and the coins it
  actually trades (USELESS, ARB, VVV, DASH, XMR, PUMP…) are low-cap alts the
  oracle has never graded. So part of "unidentified" is **oracle coverage**,
  not the hypothesis being false — and that is a fixable instrumentation
  problem. It does not change today's verdict (a coverage failure and a dead
  hypothesis are equally un-actionable), but it is the thing to fix if anyone
  wants to test this properly.
* **`within_side_agrees` is a SIGN, not a test.** It carries no significance
  and no power: three of the four verdicts the corroboration gate touches rest
  on |z| < 1 (🧘 douglas −0.32, 💸 farmer-shadow −0.95, 🎫 taker −0.05), and
  🪁 kelly's block rests on z = +1.01. It is SAFE because it is one-directional
  — it can only withdraw a confirm — but `agrees: True` must never be reported
  as corroboration in the ordinary sense. Declared in the code where a reader
  hits it; the honest upgrade is a power test there.
* **The `precondition` key added to `PRE_REGISTERED` today is a mid-flight
  amendment**, made after seeing the read it withdraws. Named as an I21
  boundary case rather than passed over: it is declared as an addition, it is
  conservative-only (it can withdraw a verdict, never create one), and the
  registered ADOPT/REFUTE thresholds are untouched. That is the acceptable
  form of one; a threshold change after the fact would not be.
* 🚀 bezos's `confirmed` was carried by **three trades** — the worst 3 of its 31
  vetoed closes are 49.4% of the vetoed total, and dropping just two flips the
  upper bound to +0.063% so the ADOPT stops firing. It is also a **7-day-old
  book with no shadow twin**, so the registration's CONFIRMED branch ("build
  the veto shadow-first, graded against its un-gated twin") was unexecutable on
  it regardless.
* Pooled kelly figures differ by two rows between the parent's live run
  (n=259, read from the DB three minutes later) and the cached ledger (n=258);
  quoted here from the cached file. Every other book matches exactly.
* This document moves nothing. Read-only.
