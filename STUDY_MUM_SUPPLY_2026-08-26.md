# STUDY: 👩 mum v2 supply widening — what she refuses that is actually worth taking (2026-08-26)

**Eamon's directive:** *"adjust to whatever enables more trades and less
restriction... tweak mum v2 so she doesnt miss anything too good."*
This study is the I19 measurement that directive requires before any entry bar
moves — the (hl) precedent (25 of 30 throughput candidates were denominator
shrinkage) is why the bars and verdict logic were **pre-declared in the script
header before any number was computed**.

Script: `scripts/study_mum_supply_2026-08-26.py` (re-runnable; candles cached).
Method in full in its header. Summary: Lighter's OWN 1h tape, mum's ACTUAL
resolved universe from `lighter_family_bot` (15 crypto + 10 non-crypto; **ATOM
and ALGO are not listed on the venue**, so 23 tradeable symbols — matching the
(tm) census), the bot's OWN `rsi_series`/`ema_series` verbatim, LAG-1
everywhere, episodes not ticks, exit-free FIRST ((qu)'s discipline), graded
against MATCHED-RANDOM entries ((hm)) with cluster-robust t (coin-day
clusters), full window AND trailing 120d ((qu)'s decay rule), then mum's real
bracket (roi ladder / −4% stop / 24h cap, stop-first-when-both-touch,
entry at the LAG-1 open so the (ml) pre-entry-range trap is unreachable).

**Tape:** 460d on the 15 long-listed crypto majors; non-crypto 175–309d
(listed later). NOW = 2026-08-26T05:02Z. n=983–7,503 signal-episodes per cell.

---

## The verdict table

| Cell | Definition | Verdict | The number that decides |
|---|---|---|---|
| **B** (control) | rsi<25 & NOT-up | **HARNESS VALID** | reproduces (tm) scarcity + (qu) decay-at-cap; see below |
| **C1** "rescue" | rsi<20 & uptrend | **REFUSE** | trailing-120d excess NEGATIVE at every horizon (−0.07/−0.12/−0.04%); full-window t_cl ≤ 0.64, h=24 excess −0.05%; random beats it (P(rand≥cell) up to 0.72). Crypto supply ~0.07 eps/day — there is almost nothing there even if it worked |
| **C2** | rsi 20–25 & uptrend | **REFUSE (flat)** | best cell in 12: trailing h=24 +0.19%, t_cl=+1.05, P(rand≥cell)=0.19. Everything else t_cl ≤ 0.72, trailing h=8/12 ≤ 0. Noise, not edge — and 31.2% of its episodes are simultaneously 🙏 avo's cell (I20) |
| **C3** | rsi 25–30 & NOT-up | **ADMIT** | the only cell that clears the pre-declared bar — details below |
| **C4** | rsi 30–42 & NOT-up | **REFUSE (DECAYED)** | all-history mildly positive (+0.04..+0.09%, t_cl ≤ 1.82) but trailing-120d NEGATIVE with authority: pooled h=12 excess −0.145% t_cl=−2.61, **crypto-only −0.223% t_cl=−3.00, P(rand≥cell)=1.000**. This is (qu)'s decay finding reproduced on mum's own universe. Admitting it would add ~16 eps/day of measured-negative supply — the exact (hl) trap |

## C3 — the admitted cell (rsi 25–30, outside the uptrend)

Pre-declared ADMIT bar: exit-free excess positive in BOTH windows with
t_cl ≥ 1.5 at h=12 or h=24, AND real-bracket positive in both halves.

**Exit-free vs matched random** (excess %, cluster-robust t, P(rand≥cell)):

| window | h=8 | h=12 | h=24 |
|---|---|---|---|
| full (n=2,296) | +0.071 / t+1.27 / P.049 | **+0.156 / t+2.25 / P.001** | **+0.272 / t+2.70 / P.000** |
| trail 120d (n=744) | +0.090 / t+1.09 | +0.099 / t+1.00 | **−0.088 / t−0.53 (decayed)** |
| full crypto (n=1,716) | +0.077 / t+1.10 | +0.184 / t+2.14 / P.000 | +0.284 / t+2.33 / P.000 |
| trail crypto (n=425) | **+0.226 / t+1.94 / P.012** | **+0.251 / t+1.71 / P.013** | −0.102 / t−0.42 |

At h=12 the bar is met exactly as pre-declared: full-window t_cl=2.25 ≥ 1.5
with trailing excess positive (+0.099 pooled, +0.251 crypto-only). The h=24
tail has DECAYED on the trailing window and is stated as such — the edge that
remains on the current tape lives at ≤12h, which is where her roi ladder banks
anyway (70% of bracket exits are `roi`).

**Her real bracket over C3's episodes** (roi ladder / −4% stop / 24h cap):

| sample | n | mean/trade | t | t_cl | halves | trail-120d mean |
|---|---|---|---|---|---|---|
| all | 2,296 | **+0.104%** | +2.38 | +1.99 | **+0.050 / +0.159** | +0.150% (n=744) |
| crypto-only | 1,716 | **+0.121%** | +2.27 | +1.92 | **+0.156 / +0.085** | +0.312% (n=425) |

Both halves positive both ways, trailing-window positive both ways, and the
crypto-only split (what the per-asset oracle gate actually lets her take) is
the STRONGER half — the ADMIT does not lean on ungated non-crypto entries.
Exits: 1,610 roi / 390 stop / 296 max_hold.

**Supply it adds** (episodes/day): full 5.00 · trailing-120d 6.22 · trailing
30d 4.03 (crypto-only 3.54 / 2.37). Against her shipped cell's current ~1.5,
that is roughly **3–4× the raw supply**; with 4 slots × 24h cap the book is
bounded at 4 closes/day, so the practical effect is a book that is actually
FULL — 30 closes in ~10 days becomes real again instead of the (tm) starvation.

## Baseline B — the harness earns the right to speak

* **(tm) scarcity reproduced:** B fires 1.53 eps/day over the trailing 30d
  (2.14 full-window) against the founding 5.07/day — same starvation the (tm)
  census measured (~1.1/day; the residual gap is window/universe accounting,
  direction and magnitude agree).
* **(qu) decay reproduced at the cap horizon:** B's h=24 excess collapses
  full→trailing from +0.454 (t_cl+3.28) to +0.134 (t_cl+0.75, P=0.18). At
  h=8/12 the trailing window still holds (+0.33/+0.30, t_cl 3.1/2.2) —
  consistent with the (ro) design table's shape at a different window length.
* Her bracket over the full window reads +0.055%/trade, t=0.81, h1 negative —
  consistent with the book's declared HYPOTHESIS-grade status; trailing-120d
  +0.216% (crypto +0.436%). Nothing here contradicts the shipped cell.

## This week's three refused entries, adjudicated

TRX rsi 23.4 (uptrend-blocked) → C2. TSLA 22.8 (uptrend-blocked) → C2.
WTI 21.9 (uptrend-blocked + ungraded) → C2, and additionally oracle-refused.
**All three fall in a REFUSED cell.** On the trailing tape, matched-random
entries beat C2's uptrend dips (P up to 0.70) — the trend filter was refusing
correctly, and "too good to miss" (C1, rsi<20 in an uptrend) is measured
WORSE: trailing-negative at every horizon. The filter (qu) measured as
destructive was destructive as a REQUIREMENT on avo's cell; as an EXCLUSION on
mum's it is doing its job.

## I7 / I20 — the overlap number, on the record

C1/C2 would have admitted uptrend entries, narrowing mum's structural
disjointness from 🙏 avo: **27.6% of C1 and 31.2% of C2 episodes also satisfy
avo's 4h SwingDip cell at entry** (upper bound; avo's oracle gate and slots
bind further). Both cells are REFUSED, so mum keeps `NOT(e50>e200)` and the
I20 separator is untouched — C3/C4 are NOT-uptrend cells and change nothing
about the declared cross-timeframe limit.

## Recommendation (what ships tonight, and what does not)

**SHIP: `OversoldRebound.RSI_MAX` 25.0 → 30.0.** One notch, the exact C3
cell, uptrend exclusion unchanged, bracket unchanged. I19 price: the admitted
supply is itself expectancy-positive under her real bracket (+0.104%/trade,
t=2.38, both halves, trailing-positive, crypto-only stronger), so this
widening pays IN expectancy rather than with it. Era: unchanged — an entry-bar
notch is ordinary tuning per the (hc)/(px) precedent (and her era sample is
n=1). Her onboard control arm (`extra.control`) grades the widened cell
against her own random null from the payload, which is the live falsification.

**REFUSE: C1, C2 (the uptrend "rescue" tiers)** — trailing-negative / flat,
random beats them, and they would open a measured 28–31% co-hold channel with
avo for supply of ~0.5–1.6 eps/day mostly on oracle-gated non-crypto.
**REFUSE: C4 (rsi 30–42)** — the (qu) decay is corroborated on mum's own
universe at t_cl −2.6 to −3.0 trailing; it is the one widening that LOOKS like
"more trades" (16 eps/day) and is measured to pay for them with expectancy.

## Honest limits

* The h=24 trailing decay in C3 (and B) means the admitted edge currently
  lives ≤12h; the roi ladder harvests there, but if the tape shifts further
  the 24h max-hold tail is a drag. The control arm is the watch.
* Trailing-window t_cl at h=12 for C3 is 1.00 pooled / 1.71 crypto-only —
  the ≥1.5 bar is met in the FULL window (as pre-declared) and crypto-only
  trailing, not pooled-trailing. Stated plainly rather than smoothed over.
* Bracket walk is bar-granular: stop-first when stop and roi touch in one bar
  (conservative), fills at bar opens, no slippage modelled (venue's measured
  RT is ~1–2 bps on the majors, small against +0.104%/trade).
* B and C3 episodes can be the same price event (rsi drifting 28→24 counts
  once in each), so union supply is less than the sum of rates.
* Non-crypto tapes are shorter (175–309d) and print through closed underlying
  hours; the crypto-only split is the guard, and the ADMIT holds on it.
* One venue, one macro window (I18 caveat unmeasured here); n=1,000 random
  draws, seed 20260826, drawn with replacement, matched per coin and count.
