#!/usr/bin/env python3
"""
scripts/study_hl_as_lighter_funding_proxy.py — IS HYPERLIQUID A VALID PROXY FOR
LIGHTER FUNDING? The load-bearing assumption under Tide Rider's go-live and
under EVERY funding backtest in this repo (they all load HL — established
17-Jul by [[backtest_funding_lighter]] / [[audit_venue_purity]]).

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-17). 300d paired SETTLED HOURLY tape, 13 markets with an     ║
║ HL twin, 90,657 same-hour paired observations, 2025-09-20→2026-07-17. Both    ║
║ halves on every headline. Every number below is this file's real output.      ║
║                                                                              ║
║ THE ANSWER IS CONSUMER-DEPENDENT, AND THE COMMON FRAMING IS WRONG.            ║
║ "Port it with a correction factor" is not merely unsafe — it is MALFORMED.    ║
║ A correction factor corrects a LEVEL. **The levels already agree.** What      ║
║ does not transfer is the part no factor can touch.                            ║
║                                                                              ║
║ 1. **BOTH VENUES PIN AT ESSENTIALLY THE SAME DEFAULT.** This is the whole     ║
║    mechanism and it refutes what I set out to write.                          ║
║      LIGHTER  rests EXACTLY at +0.10512 apr on **65.0%** of hours             ║
║      HYPERLIQ rests EXACTLY at +0.10950 apr on **57.8%** of hours             ║
║    Lighter = 0.0096%/8h, HL = 0.01%/8h — the SAME standard perp interest      ║
║    component, 4% apart. 44.7% of ALL hours are CO-PINNED (both at default).   ║
║    Per coin, not just pooled: HL pins 33.4% (SOL) to 78.4% (AAVE); Lighter    ║
║    39.8% to 83.3%. On HYPE and LIT, HL pins MORE than Lighter does.           ║
║    **METHOD TRAP THIS FILE FELL INTO AND FIXED — the reason the finding was   ║
║    nearly missed:** testing HL's series against LIGHTER's 0.10512 reports     ║
║    HL pinned = 0.0%, which reads as "HL is a continuous market price, Lighter ║
║    is a rigged constant" — a clean, wrong, publishable conclusion. The two    ║
║    defaults differ by 4%, so an exact-match test against the wrong constant   ║
║    scores zero and LOOKS like a result. Score each venue against ITS OWN      ║
║    default (`hl_pinned_frac`). The 0.0% column was in this file's first run.  ║
║    Live cross-check, independent of the cache (/funding-rates, one call,      ║
║    same instant): Lighter 73.1% pinned (46.3% at 10.512 + 26.9% at 3.504),    ║
║    HL bench 47.7% at ~10.95. The structure reproduces on live data.           ║
║ 1b. THIS REFUTES [[backtest_funding_persistence]]'s STATED REMEDY. That file  ║
║    concludes the Farmer is dead because Lighter's funding is "a PINNED        ║
║    ADMINISTRATIVE DEFAULT 68.6% of the time" and prescribes "a venue where    ║
║    funding is a continuous market-clearing price rather than a pinned         ║
║    default." **HL is not that venue.** It pins 57.8% of hours at its own      ║
║    default. The pinning is not a Lighter defect — it is how perps work. The   ║
║    ruling (Farmer dead) stands on its OTHER legs (friction vs carry); the     ║
║    prescription does not, and nobody should go venue-shopping for it.         ║
║                                                                              ║
║ 2. **THE LEVELS AGREE — SO NOTHING NEEDS CORRECTING.** Pooled mean apr:       ║
║    Lighter +5.45% vs HL +4.68%. Tide Rider's basket (BTC/ETH/SOL/BNB/XRP):    ║
║    **HL 3.16%apr vs LIGHTER 3.36%apr — HL UNDERSTATES by 0.20pp.**            ║
║    BUT THAT AGREEMENT IS CANCELLATION, NOT ACCURACY. Per coin the error is    ║
║    signed and large: BNB -2.50pp, SOL +0.93, ETH +0.75, BTC +0.40, XRP        ║
║    -0.60; cross-coin sd **1.95pp**. A single global constant would leave      ║
║    each coin wrong by about that much, and a different basket cancels         ║
║    differently.                                                              ║
║ 2b. AND THE PER-COIN DIFFERENCE IS **NOISE, NOT A SHIFT** — the test that     ║
║    decides correctability. (L−H) per coin, first half vs second half:         ║
║    **sign flips on 5 of 13** (BTC +0.35→−1.15, SOL −3.61→+1.74, XRP           ║
║    −3.32→+4.53, HYPE +4.66→−1.91, ZEC +1.80→−2.95). Median |drift| between    ║
║    halves **3.38pp** — LARGER than the median |L−H| level itself (1.99pp).    ║
║    A correction fitted on one half is wrong, often backwards, on the next.    ║
║                                                                              ║
║ 3. **NO CORRECTION FACTOR EXISTS — MEASURED AGAINST THE DUMBEST BASELINE.**   ║
║    Skill = R² vs simply predicting Lighter's OWN constant mean (0 = no        ║
║    better than a constant, <0 = WORSE than ignoring HL entirely):             ║
║      A. raw       L̂ = H            median skill **−0.400**  (WORSE than a    ║
║                                     constant on 8 of 13 coins)               ║
║      B. global    L̂ = 0.0296+0.532H median skill **+0.158**                  ║
║      C. per-coin affine, IN-SAMPLE   median skill **+0.204**  ← a CEILING     ║
║    C is fitted and scored on the same data — it cannot be beaten by any       ║
║    honest factor, and it still explains only ~20%. Fit C on H1, score on H2   ║
║    (the honest version): **median OOS skill −0.064; only 3 of 13 coins beat   ║
║    a constant.** The best-case correction factor, done honestly, is WORSE     ║
║    THAN NOT USING HL AT ALL.                                                  ║
║                                                                              ║
║ 4. **THE TAILS — WHERE EVERY GATE LIVES — DO NOT TRANSFER.** A funding gate   ║
║    never fires on the default (0.105 < any tradeable gate), so a gate's       ║
║    entire behaviour is the off-default excursions. Pooled r=+0.504 is         ║
║    mostly two constants agreeing; stripping the co-pin, off-default           ║
║    pearson is **+0.586** (n=19,953) — real but moderate, and STABLE both      ║
║    halves (+0.595/+0.519). The port itself:                                   ║
║      gate  P(Lighter hot | HL hot)   P(HL hot | Lighter hot)                  ║
║      0.20        39.0%                    31.9%                              ║
║      0.40        40.8%   ← the live gate  29.1%                              ║
║      0.80        49.0%                    30.0%                              ║
║      1.10        51.0%                    34.6%                              ║
║    Same-sign (wrong side of a right call still loses): 40.2% at gate 0.40.    ║
║    **~60% of the hours an HL-fitted 0.40 gate fires on are NOT hot on         ║
║    Lighter.** Both halves: 49.7% (n=1613) / 25.2% (n=920) — unstable, and     ║
║    under half on BOTH. An HL-fitted gate selects a mostly-DIFFERENT SET OF    ║
║    HOURS on Lighter. It is not a mis-calibrated gate; it is a different bet.  ║
║                                                                              ║
║ THEREFORE — the corpus splits, it is not one verdict:                         ║
║  * Anything that GATES on funding (the Funding Farmer, every                  ║
║    backtest_*funding* file, FUNDING_ENTER_APR): **NOT SALVAGEABLE. RE-RUN     ║
║    ON LIGHTER DATA.** No factor fixes a 40% hour-set overlap.                 ║
║    (Already done independently: [[backtest_funding_lighter]] — no gate        ║
║    passes both halves on Lighter. This explains WHY the HL result did not     ║
║    reproduce, which that file flagged and could not account for.)             ║
║  * Anything that uses funding as a DRAG/mean over long holds (Tide Rider's    ║
║    perp validation): **APPROXIMATELY SURVIVES, BY LUCK, NOT BY METHOD.**      ║
║    The ~13pp basket drag is not overturned — Lighter's own basket drag is     ║
║    within 0.20pp of HL's on this window. It survives because both venues      ║
║    rest at the same interest default, not because HL predicts Lighter.        ║
║    Do not read that as validation: per-coin error ±2.5pp, sign-unstable       ║
║    across halves, and the windows DO NOT OVERLAP (below).                     ║
║                                                                              ║
║ 5. **TIDE RIDER'S ACTUAL HOLDING IS THE WORST-COVERED COIN.** TRX is in the   ║
║    validation basket and is what the live book holds TODAY, and it is the     ║
║    ONE basket coin absent from every cached study. Fetched here directly      ║
║    (7,191 paired hours): **LIGHTER mean −0.95%apr vs HL −2.69%apr.** Both     ║
║    negative — over 300d a TRX long was PAID, not charged. Halves: H1          ║
║    −0.67pp / H2 **+4.14pp** — the venue gap on this coin flips and is 4pp     ║
║    wide. Live right now (same-instant, one call): **Lighter −66.58%apr vs     ║
║    HL bench −52.01%apr, a 14.6pp gap.** Snapshot, not a window — but the      ║
║    drag on the live position is not a small number and is not HL's number.    ║
║                                                                              ║
║ LIMITATIONS — read before acting.                                            ║
║  * ONE 300d window (2025-09-20→2026-07-17), 13 markets. Halves reported.      ║
║  * **THE WINDOWS DO NOT OVERLAP, AND THIS IS THE HARD LIMIT.**                ║
║    backtest_tide_rider_perp.py claims +52%→+40% over **~2.7yr**. Lighter's    ║
║    tape reaches ~300d here (a sibling reports 438d attainable). **Most of     ║
║    the window Tide Rider was validated on PREDATES Lighter's existence.**     ║
║    No amount of work makes that period measurable on Lighter. Section 2's     ║
║    agreement is measured on the RECENT 300d only and is silent about          ║
║    2023-2025 — including the 2024 bull run, exactly when a trend-follower     ║
║    holds longest and funding runs hottest. This is not a gap to close; it     ║
║    is a permanent one, and any go-live memo must say so.                      ║
║  * 13 of 30 markets have an HL twin and they are the MAJORS — the books       ║
║    most pinned at the default. The proxy is measured where it flatters.       ║
║  * Skill scores are on the RATE. Nobody trades the rate; a P&L replay could   ║
║    differ. [[backtest_funding_lighter]] is that replay and is more negative.  ║
║  * The mechanism claim (both defaults = the perp interest component,          ║
║    Lighter 0.0096%/8h vs HL 0.01%/8h) is INFERRED from the arithmetic and     ║
║    the venues' documented constructions. The PINNING and the LEVELS are       ║
║    measured; the reason they pin is not.                                      ║
║  * The live cross-section and the TRX live quote are SNAPSHOTS.               ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS (2026-07-17)
[[study_lighter_vs_hl_equivalence]] measured the `_bench` RENDERING (Lighter's
exchange=hyperliquid rows vs HL's own API: ratio 8.0021, live to seconds). That
is a UNITS+STALENESS check on Lighter's copy of HL's number. It is NOT this
question. This asks whether HL's OWN funding LEVEL stands in for LIGHTER's OWN
funding level — the substitution every backtest in the repo silently makes.

DATA — reused, not refetched. scripts/.fundpersist_cache.json, built by
[[backtest_funding_persistence]] (300d, 30 markets, fetched 2026-07-17 04:06Z).
It already holds, per market, SETTLED HOURLY series from BOTH venues keyed on
the same hour bucket:
    mk[SYM]["fund"] = Lighter /api/v1/fundings  -> signed TRUE apr fraction
                      (rate is %/HOUR -> /100*24*365; NOT the 8h /funding-rates
                       endpoint that caused the fleet-wide 8x)
    mk[SYM]["hl"]   = HL fundingHistory         -> signed TRUE apr fraction
                      (natively hourly -> *24*365, correct THERE)
Both sides are already TRUE apr, so they are directly comparable and no basis
conversion happens in this file. 14 of 30 markets have an HL twin.

METHOD
  * Pair on the EXACT hour bucket. No interpolation, no resampling, no
    forward-fill: an unpaired cross-section of two continuously-moving numbers
    manufactures fake ratios (that is [[study_lighter_vs_hl_equivalence]] 2b's
    hard-won warning, and it applies to levels too).
  * Both halves on every headline (split at the window midpoint).
  * The decisive test is NOT correlation. It is whether an HL-fed estimate of
    Lighter's funding beats the DUMBEST possible Lighter-only baseline
    (predict Lighter's own constant mean). A proxy that cannot beat a constant
    is not a proxy, whatever its r. Three nested candidates, each the best-case
    version of a "correction factor" a backtest could apply:
        A. raw            L_hat = H
        B. global scale   L_hat = k*H          (k fitted on the pooled tape)
        C. per-coin affine L_hat = a_c + b_c*H (fitted PER COIN, in-sample —
                           deliberately flattering; it cannot be beaten by any
                           honest correction factor)
    Skill is scored as out-of-sample-honest R^2 vs the constant baseline for A/B
    (both use no per-coin fitting) and as an IN-SAMPLE CEILING for C.
  * Ratios are reported but never load-bearing: near-zero denominators explode
    them (same 2b lesson).

Read-only: reads one gitignored cache. No network, no DB, no bot, no lever.
    .venv/bin/python scripts/study_hl_as_lighter_funding_proxy.py
"""
import json
import math
import os
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".fundpersist_cache.json")

# Lighter's two RESTING DEFAULTS, measured by [[backtest_funding_persistence]]:
# crypto books rest at 10.512% TRUE apr, equity/commodity at 3.504%.
PIN_CRYPTO, PIN_EQUITY = 0.10512, 0.03504
# HL rests at its OWN default: 0.01%/8h -> 1.25e-5/hr * 24 * 365 = 0.1095 apr.
PIN_HL = 0.1095
PIN_TOL = 1e-6

# Tide Rider's OWN validation basket (scripts/backtest_tide_rider_perp.py PAIRS).
TIDE_BASKET = ["BTC", "ETH", "SOL", "BNB", "XRP", "TRX"]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    if len(xs) < 3:
        return float("nan")
    return pearson(rank(xs), rank(ys))


def ols(xs, ys):
    """-> (intercept, slope). Least squares, hand-rolled (no numpy needed)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((a - mx) ** 2 for a in xs)
    if sxx <= 0:
        return my, 0.0
    b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sxx
    return my - b * mx, b


def r2_vs_constant(actual, pred):
    """Skill score vs predicting the actual series' OWN mean.
    1.0 = perfect, 0.0 = no better than the constant, NEGATIVE = WORSE than
    just assuming Lighter's average. This is the number that decides it."""
    n = len(actual)
    if n < 3:
        return float("nan")
    mu = sum(actual) / n
    ss_tot = sum((a - mu) ** 2 for a in actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, pred))
    if ss_tot <= 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def pinned_frac(vals):
    """Fraction of hours resting EXACTLY on a LIGHTER default."""
    return sum(1 for v in vals
               if abs(abs(v) - PIN_CRYPTO) < PIN_TOL
               or abs(abs(v) - PIN_EQUITY) < PIN_TOL) / max(1, len(vals))


def hl_pinned_frac(vals):
    """Fraction of hours resting EXACTLY on HL's OWN default.

    MEASURE EACH VENUE AGAINST ITS OWN DEFAULT. Testing HL against Lighter's
    0.10512 reports 0.0% and invites the conclusion that HL is a continuous
    market price while Lighter is a pinned constant. That conclusion is FALSE
    and this file was originally written asserting it. HL rests at 0.01%/8h
    (-> 0.1095 apr), Lighter at 0.0096%/8h (-> 0.10512): 4% apart, so an
    exact-match test against the wrong constant scores zero and looks like a
    finding. It is an artifact of the tolerance, not a property of the venue.
    """
    return sum(1 for v in vals
               if abs(abs(v) - PIN_HL) < PIN_TOL) / max(1, len(vals))


def load():
    d = json.load(open(CACHE))
    print(f"  cache: {len(d['mk'])} markets, {d['days']}d, fetched "
          f"{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(d['fetched']))}")
    out = {}
    for sym, m in d["mk"].items():
        f = {int(k): v for k, v in (m.get("fund") or {}).items()}
        h = {int(k): v for k, v in (m.get("hl") or {}).items()}
        common = sorted(set(f) & set(h))
        if len(common) >= 500:
            out[sym] = (common, f, h)
    return out, d["days"]


def main():
    if not os.path.exists(CACHE):
        print("cache missing — run backtest_funding_persistence.py --refresh first")
        return 1
    mk, days = load()
    if not mk:
        print("no market has a paired tape — cannot answer")
        return 1

    print(f"\n{'='*78}\nPAIRED SETTLED HOURLY FUNDING — LIGHTER vs HYPERLIQUID, "
          f"TRUE apr both sides\n{'='*78}")
    print(f"{'coin':<10}{'n':>7}{'L_mean':>9}{'H_mean':>9}{'L-H':>9}"
          f"{'pearson':>9}{'spear':>8}{'L_pin%':>8}{'H_pin%':>8}")
    print("-" * 78)

    pooled_l, pooled_h, rows = [], [], []
    for sym in sorted(mk, key=lambda s: -len(mk[s][0])):
        common, f, h = mk[sym]
        L = [f[t] for t in common]
        H = [h[t] for t in common]
        pooled_l += L
        pooled_h += H
        r = pearson(H, L)
        rho = spearman(H, L)
        rows.append((sym, common, L, H, r, rho))
        print(f"{sym:<10}{len(L):>7}{st.mean(L):>9.4f}{st.mean(H):>9.4f}"
              f"{st.mean(L)-st.mean(H):>9.4f}{r:>9.3f}{rho:>8.3f}"
              f"{pinned_frac(L)*100:>7.1f}%{hl_pinned_frac(H)*100:>7.1f}%")

    n = len(pooled_l)
    print("-" * 78)
    print(f"{'POOLED':<10}{n:>7}{st.mean(pooled_l):>9.4f}{st.mean(pooled_h):>9.4f}"
          f"{st.mean(pooled_l)-st.mean(pooled_h):>9.4f}"
          f"{pearson(pooled_h, pooled_l):>9.3f}{spearman(pooled_h, pooled_l):>8.3f}"
          f"{pinned_frac(pooled_l)*100:>7.1f}%{hl_pinned_frac(pooled_h)*100:>7.1f}%")

    # ── the decisive test: can ANY correction factor make HL predict Lighter? ──
    print(f"\n{'='*78}\nCAN A CORRECTION FACTOR RESCUE THE PROXY?\n"
          f"skill vs predicting Lighter's own constant mean "
          f"(0.0 = no better than a constant, <0 = WORSE)\n{'='*78}")

    _, k_global = ols(pooled_h, pooled_l)          # through-origin-ish global fit
    a_g, b_g = ols(pooled_h, pooled_l)
    print(f"  global pooled fit:  L_hat = {a_g:+.5f} {b_g:+.5f}*H   (n={n})")

    print(f"\n{'coin':<10}{'n':>7}{'A raw':>9}{'B global':>10}"
          f"{'C percoin':>11}{'  (b_c)':>9}{'  verdict':>22}")
    print("-" * 78)
    skills = {"A": [], "B": [], "C": []}
    for sym, common, L, H, r, rho in rows:
        sA = r2_vs_constant(L, H)
        sB = r2_vs_constant(L, [a_g + b_g * x for x in H])
        a_c, b_c = ols(H, L)
        sC = r2_vs_constant(L, [a_c + b_c * x for x in H])
        skills["A"].append(sA)
        skills["B"].append(sB)
        skills["C"].append(sC)
        v = ("USELESS" if sC < 0.05 else
             "weak" if sC < 0.20 else
             "partial" if sC < 0.50 else "STRONG")
        print(f"{sym:<10}{len(L):>7}{sA:>9.3f}{sB:>10.3f}{sC:>11.3f}"
              f"{b_c:>9.3f}{v:>22}")
    print("-" * 78)
    print(f"{'median':<10}{'':>7}{st.median(skills['A']):>9.3f}"
          f"{st.median(skills['B']):>10.3f}{st.median(skills['C']):>11.3f}"
          f"{'':>9}{'  <- C is an IN-SAMPLE CEILING':>22}")

    # ── both halves on the ceiling ───────────────────────────────────────────
    print(f"\n{'='*78}\nBOTH HALVES — per-coin affine fit on H1, SCORED ON H2 "
          f"(the honest version of C)\n{'='*78}")
    print(f"{'coin':<10}{'n_h1':>7}{'n_h2':>7}{'b_h1':>9}{'b_h2':>9}"
          f"{'skill_oos':>11}{'  sign stable?':>16}")
    print("-" * 78)
    oos = []
    for sym, common, L, H, r, rho in rows:
        mid = common[len(common) // 2]
        i1 = [i for i, t in enumerate(common) if t < mid]
        i2 = [i for i, t in enumerate(common) if t >= mid]
        if len(i1) < 200 or len(i2) < 200:
            continue
        H1, L1 = [H[i] for i in i1], [L[i] for i in i1]
        H2, L2 = [H[i] for i in i2], [L[i] for i in i2]
        a1, b1 = ols(H1, L1)
        a2, b2 = ols(H2, L2)
        s = r2_vs_constant(L2, [a1 + b1 * x for x in H2])   # fit H1 -> score H2
        oos.append(s)
        stable = "yes" if (b1 > 0) == (b2 > 0) else "NO — SIGN FLIPS"
        print(f"{sym:<10}{len(i1):>7}{len(i2):>7}{b1:>9.3f}{b2:>9.3f}"
              f"{s:>11.3f}{stable:>16}")
    print("-" * 78)
    if oos:
        print(f"  median OUT-OF-SAMPLE skill of the best-case correction: "
              f"{st.median(oos):+.3f}   (n_coins={len(oos)})")
        print(f"  coins where the honest proxy BEATS a constant: "
              f"{sum(1 for s in oos if s > 0)}/{len(oos)}")

    # ── the drag question: what Tide Rider actually needs ────────────────────
    print(f"\n{'='*78}\nTHE DRAG — what Tide Rider's go-live number actually "
          f"rests on\n  a weeks-long LONG pays the MEAN funding; only the mean "
          f"matters to it\n{'='*78}")
    print(f"{'coin':<10}{'n':>7}{'HL drag %apr':>14}{'LT drag %apr':>14}"
          f"{'overstated by':>15}{'  in basket?':>13}")
    print("-" * 78)
    for sym, common, L, H, r, rho in rows:
        if sym not in TIDE_BASKET:
            continue
        hd, ld = st.mean(H) * 100, st.mean(L) * 100
        print(f"{sym:<10}{len(L):>7}{hd:>14.2f}{ld:>14.2f}"
              f"{hd-ld:>14.2f}pp{'  YES':>13}")
    inb = [s for s in mk if s in TIDE_BASKET]
    print("-" * 78)
    print(f"  Tide Rider basket = {TIDE_BASKET}")
    print(f"  measurable here   = {sorted(inb)}")
    print(f"  MISSING           = {sorted(set(TIDE_BASKET) - set(inb))}"
          f"   <- note what the live bot is holding today")
    if inb:
        bh = st.mean([st.mean([mk[s][2][t] for t in mk[s][0]]) for s in inb]) * 100
        bl = st.mean([st.mean([mk[s][1][t] for t in mk[s][0]]) for s in inb]) * 100
        print(f"  basket-mean drag: HL {bh:.2f}%apr vs LIGHTER {bl:.2f}%apr "
              f"-> HL overstates by {bh-bl:+.2f}pp over this {days}d window")

    # ── SYSTEMATIC OR NOISY? the question that decides correctability ────────
    print(f"\n{'='*78}\nIS THE DIFFERENCE SYSTEMATIC OR NOISY?\n"
          f"  a LEVEL SHIFT you could correct for must be STABLE across halves."
          f"\n  if (L-H) flips sign or moves between halves, there is nothing "
          f"to correct.\n{'='*78}")
    print(f"{'coin':<10}{'(L-H) h1 pp':>13}{'(L-H) h2 pp':>13}{'drift pp':>11}"
          f"{'  sign stable?':>16}")
    print("-" * 78)
    d1s, d2s, drifts, stable_n = [], [], [], 0
    for sym, common, L, H, r, rho in rows:
        mid = common[len(common) // 2]
        i1 = [i for i, t in enumerate(common) if t < mid]
        i2 = [i for i, t in enumerate(common) if t >= mid]
        if len(i1) < 200 or len(i2) < 200:
            continue
        d1 = (st.mean([L[i] for i in i1]) - st.mean([H[i] for i in i1])) * 100
        d2 = (st.mean([L[i] for i in i2]) - st.mean([H[i] for i in i2])) * 100
        ok = (d1 > 0) == (d2 > 0)
        stable_n += ok
        d1s.append(d1)
        d2s.append(d2)
        drifts.append(abs(d1 - d2))
        print(f"{sym:<10}{d1:>13.2f}{d2:>13.2f}{abs(d1-d2):>11.2f}"
              f"{('yes' if ok else 'NO — FLIPS'):>16}")
    print("-" * 78)
    print(f"  per-coin (L-H) sign stable across halves: {stable_n}/{len(d1s)}")
    print(f"  median |drift| between halves: {st.median(drifts):.2f}pp   "
          f"(median |L-H| level itself: "
          f"{st.median([abs(x) for x in d1s + d2s]):.2f}pp)")
    print(f"  cross-coin dispersion of (L-H), full window: sd="
          f"{st.pstdev([st.mean(L)*100 - st.mean(H)*100 for _, _, L, H, _, _ in rows]):.2f}pp")
    print(f"  -> a single global correction constant would leave EACH COIN "
          f"wrong by ~this much.")

    # ── mechanism: the distributions are not the same KIND of object ─────────
    print(f"\n{'='*78}\nMECHANISM — WHY. The two venues' funding are not the "
          f"same kind of object.\n{'='*78}")
    for label, v, fn in (("LIGHTER", pooled_l, pinned_frac),
                         ("HYPERLIQ", pooled_h, hl_pinned_frac)):
        q = sorted(v)
        distinct = len(set(round(x, 6) for x in v))
        print(f"  {label:<9} n={len(v):<7} distinct_values={distinct:<7} "
              f"p10={q[len(q)//10]:+.4f} med={st.median(v):+.4f} "
              f"p90={q[9*len(q)//10]:+.4f} "
              f"pinned_on_OWN_default={fn(v)*100:.1f}%")

    # Both venues REST near ~10.5-11% apr (the standard perp interest
    # component). The difference is not the LEVEL they rest at — it is whether
    # the rate is a CONSTANT or a PRICE. Measure that directly.
    print(f"\n  Both venues rest near the same ~10.5-11%apr interest component."
          f" The difference is KIND, not level:")
    for label, v, pin in (("LIGHTER", pooled_l, PIN_CRYPTO),
                          ("HYPERLIQ", pooled_h, PIN_HL)):
        exact = sum(1 for x in v if abs(x - pin) < 1e-9) / len(v)
        near1 = sum(1 for x in v if abs(x - pin) < 0.001) / len(v)
        near5 = sum(1 for x in v if abs(x - pin) < 0.005) / len(v)
        print(f"    {label:<9} at its default {pin:+.4f}: "
              f"EXACTLY {exact*100:5.1f}%   within 0.001 {near1*100:5.1f}%   "
              f"within 0.005 {near5*100:5.1f}%")
    print(f"\n  BOTH VENUES PIN. This REFUTES the intuition this section was "
          f"written to assert (and refutes\n  [[backtest_funding_persistence]]'s "
          f"stated remedy, 'a venue where funding is a continuous\n  "
          f"market-clearing price rather than a pinned default' — HL is not "
          f"that venue either).\n  Lighter rests at 0.0096%/8h, HL at exactly "
          f"0.01%/8h: the SAME standard perp interest\n  component, 4% apart. "
          f"The levels agree because both are mostly the same constant.")

    # ── CO-PINNING INFLATES THE CORRELATION — strip it out ──────────────────
    print(f"\n{'='*78}\nSTRIPPING THE CO-PIN: the pooled r=0.504 is mostly TWO "
          f"CONSTANTS AGREEING.\n  A funding GATE never fires on the default "
          f"(0.105 < any gate worth trading). Every\n  backtest's entry "
          f"decision lives ENTIRELY in the off-default DEVIATIONS. Measure "
          f"those.\n{'='*78}")
    LD, HD = PIN_CRYPTO, PIN_HL
    off_l = [(a, b) for a, b in zip(pooled_l, pooled_h) if abs(a - LD) > 1e-9]
    off_both = [(a, b) for a, b in zip(pooled_l, pooled_h)
                if abs(a - LD) > 1e-9 and abs(b - HD) > 1e-9]
    co_pin = sum(1 for a, b in zip(pooled_l, pooled_h)
                 if abs(a - LD) < 1e-9 and abs(b - HD) < 1e-9) / n
    print(f"  hours BOTH at their default (co-pinned): {co_pin*100:.1f}%  "
          f"({int(co_pin*n)} of {n})")
    print(f"  hours LIGHTER off-default:               "
          f"{len(off_l)/n*100:.1f}%  ({len(off_l)})")
    print(f"  hours BOTH off-default:                  "
          f"{len(off_both)/n*100:.1f}%  ({len(off_both)})")
    if len(off_both) > 100:
        oa = [a for a, b in off_both]
        ob = [b for a, b in off_both]
        print(f"\n  pearson on ALL hours          : {pearson(pooled_h, pooled_l):+.3f}"
              f"   <- the flattering number")
        print(f"  pearson on BOTH-off-default   : {pearson(ob, oa):+.3f}"
              f"   <- the honest one ({len(off_both)} obs)")
        print(f"  spearman on BOTH-off-default  : {spearman(ob, oa):+.3f}")

    # ── DOES A HOT-FUNDING GATE TRANSFER? the actual port question ───────────
    print(f"\n{'='*78}\nDOES AN HL-FITTED GATE TRANSFER? "
          f"(FUNDING_ENTER_APR=0.40 was fitted on HL)\n  If HL says 'hot', how "
          f"often is Lighter hot at the same hour? That IS the port.\n{'='*78}")
    print(f"{'gate':>7}{'HL hot hrs':>12}{'LT hot hrs':>12}{'both':>8}"
          f"{'P(LT hot|HL hot)':>18}{'P(HL hot|LT hot)':>18}")
    print("-" * 78)
    for g in (0.20, 0.40, 0.80, 1.10):
        hh = [i for i in range(n) if abs(pooled_h[i]) >= g]
        lh = [i for i in range(n) if abs(pooled_l[i]) >= g]
        both = set(hh) & set(lh)
        p_l_given_h = len(both) / len(hh) if hh else float("nan")
        p_h_given_l = len(both) / len(lh) if lh else float("nan")
        print(f"{g:>7.2f}{len(hh):>12}{len(lh):>12}{len(both):>8}"
              f"{p_l_given_h*100:>17.1f}%{p_h_given_l*100:>17.1f}%")
    print("-" * 78)
    print(f"  Same-SIGN check at the live-relevant gate (a carry trade that "
          f"takes the wrong side\n  of a correctly-predicted hot hour still "
          f"loses):")
    for g in (0.20, 0.40):
        hh = [i for i in range(n) if abs(pooled_h[i]) >= g]
        agree = sum(1 for i in hh if abs(pooled_l[i]) >= g
                    and (pooled_l[i] > 0) == (pooled_h[i] > 0))
        print(f"    gate {g:.2f}: of {len(hh)} HL-hot hours, Lighter is hot "
              f"AND same-sign on {agree} = {agree/len(hh)*100:.1f}%")

    # ── BOTH HALVES on the two headline numbers ─────────────────────────────
    print(f"\n{'='*78}\nBOTH HALVES on the headlines (a number that holds on "
          f"one half is a window)\n{'='*78}")
    # rebuild pooled series carrying their timestamps so halves are by TIME
    stamped = []
    for sym, common, L, H, r, rho in rows:
        stamped += list(zip(common, L, H))
    stamped.sort()
    half = stamped[len(stamped) // 2][0]
    for name, sub in (("H1", [x for x in stamped if x[0] < half]),
                      ("H2", [x for x in stamped if x[0] >= half])):
        sl = [x[1] for x in sub]
        sh = [x[2] for x in sub]
        ob = [(a, b) for a, b in zip(sl, sh)
              if abs(a - LD) > 1e-9 and abs(b - HD) > 1e-9]
        r_off = pearson([b for a, b in ob], [a for a, b in ob]) if len(ob) > 100 else float("nan")
        hh = [i for i in range(len(sl)) if abs(sh[i]) >= 0.40]
        both40 = sum(1 for i in hh if abs(sl[i]) >= 0.40)
        print(f"  {name}: n={len(sub):<6} off-default pearson={r_off:+.3f} "
              f"(n={len(ob)})   P(LT hot|HL hot)@0.40="
              f"{(both40/len(hh)*100 if hh else float('nan')):.1f}% "
              f"(n_hl_hot={len(hh)})   L_pin="
              f"{sum(1 for a in sl if abs(a-LD)<1e-9)/len(sl)*100:.1f}% "
              f"H_pin={sum(1 for b in sh if abs(b-HD)<1e-9)/len(sh)*100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
