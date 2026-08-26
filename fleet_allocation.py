#!/usr/bin/env python3
"""
fleet_allocation.py — 💰 the ALLOCATION organ: where SHOULD the capital be?

WHY (2026-08-01, operator: "structured for growth and opportunity ... let's make
the best outcome for our growing ecosystem").

The fleet has a dozen organs that answer "is this book safe?" and exactly none
that answer "where should the money go?". Every shadow book is handed $1,000
regardless of evidence, and it has been that way since the first one. So the
fleet's best-evidenced book and a book with ZERO closed trades in twenty days
carry the same capital, and nothing in the system notices.

The measurement that makes this urgent (2026-07-30, live ledger):

    FUNDING books        3 books   n=212 closes   net  +$72.89
    DIRECTIONAL books   18 books   n=809 closes   net   -$9.21

Six times the trades and six times the books, on the side that does not pay.
That is not a tuning problem — it is an allocation problem, and the fleet had no
instrument that could even state it.

WHAT THIS IS
  A publish-only VIEW. It grades every living book on the evidence that already
  exists, computes what an evidence-weighted allocation WOULD look like, and
  publishes the gap against the flat allocation actually in force.

WHAT THIS IS NOT, and this is deliberate:
  * It moves NO capital. It writes no lever, touches no clip, promotes nothing.
    Automating capital movement is a large new actuator on a fleet whose growth
    rail is bounded and TTL'd for good reasons; the operator gets the number,
    not a fait accompli.
  * It is NOT a second go-live gate. The gate lives in scripts/golive_readiness
    and is IMPORTED here, never re-implemented — a second copy of a rule that
    governs real money is a second rule (the 30-Jul evidence_review defect).
    Allocation asks a DIFFERENT question: not "may this book hold real money?"
    but "given what we know, where is the next dollar best spent?"

THE RULE — rank on a LOWER BOUND, never on the mean.
  A book's claim on capital is `mean - Z * SE` (a one-sided lower confidence
  bound on per-trade expectancy), floored at zero. Ranking on the mean rewards
  small samples that got lucky; the lower bound is what the incubator already
  learned to rank on, and it is self-correcting: a book with a big mean and a
  tiny n has a wide SE and therefore a weak claim, exactly as it should.

  Every living book keeps a PROBE floor. A book cannot earn evidence with no
  capital, so starving an undecided book to zero is how a fleet stops learning.
  The floor is the price of optionality and it is stated, not hidden.

Usage:
    python3 fleet_allocation.py                 # print the table
    python3 fleet_allocation.py --publish       # + write bot_state
    python3 fleet_allocation.py --selftest      # offline, no DB
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

# [2026-08-16 (oy)] The consumer's own scale rule, IMPORTED not re-derived —
# there is exactly one place where `target_usd` becomes a scale and one place
# where the era decides ((hj)). A hard import on purpose: this organ ships only
# in freqtrade-bots, which carries fleet_bus in `_BUILD_SHARED`, and a guarded
# import would degrade the field to None — which is precisely the ambiguity
# this change exists to remove.
from fleet_bus import allocation_scale_for

try:
    import bot_pnl_store as store
except Exception:                                    # pragma: no cover
    store = None

KEY = "fleet-allocation"
# [2026-08-15 (mw)] 21600 -> 5400: the loop publishes every 1800s
# (RADAR_INTERVAL_SEC), so 6h let a FROZEN allocation read fresh through 12
# missed cycles — and this organ's declared unpageability rests on "staleness
# visible on the dashboard", which a 12-cycle-slack TTL makes decorative.
# 5400 = 3 missed cycles, the fleet's usual staleness slack.
TTL_SEC = int(os.environ.get("ALLOC_TTL_SEC", "5400"))       # 3 x 1800s loop

# The ONE standard of evidence, as a confidence level rather than a critical
# value. 90% one-sided: deliberately gentler than the go-live gate's t>=2.0,
# because this decides where to LEARN next, not what may hold real money. Using
# the gate's bar here would starve every undecided book and the fleet would stop
# discovering anything. `golive_readiness`'s horizon power gate reads THIS
# constant, so the fleet applies one standard whether it is feeding a book or
# doubting one (I17's amended text, now shared in code rather than in prose).
CONF = float(os.environ.get("ALLOC_CONF", "0.90"))
# The large-sample limit of that confidence level, and the FLOOR on the critical
# value. 1.2816 is what `t_crit` converges to as n grows; keeping it as a floor
# means `ALLOC_Z_LOWER` stays a live lever that can only make the bound
# STRICTER, never looser than the sample itself supports (the cage principle —
# a lever whose only reachable direction is "loosen past the evidence" is not a
# lever, it is a hole).
Z_LOWER = float(os.environ.get("ALLOC_Z_LOWER", "1.28"))
# The probe floor, as a fraction of the flat book size. A book cannot earn
# evidence with no capital.
PROBE_FLOOR = float(os.environ.get("ALLOC_PROBE_FLOOR", "0.25"))
#: [2026-08-20] THE LUCK FLOOR — 20 -> 10, and it is a COMPUTABILITY floor now,
#: not a decidability verdict.
#:
#: What it used to be: `n >= 20 or the claim is 0.0, whatever the mean looks
#: like`. That is a CLIFF, and it was a SECOND penalty for a small sample on top
#: of the standard error, which already does exactly that job — and does it
#: continuously. Measured on the live payload the day this changed: three living
#: books held a genuinely positive lower bound and published 0.000 because of
#: it (🙏 avo shadow n=17 bound +0.362%/trade at t=1.92; its live twin n=4; 👩
#: mum n=7), and — the half that actually matters — FIVE books published
#: `claim_era: None` for the same reason, including 🌾 carry, the fleet's
#: highest-ranked book. `claim_era` is the ONLY field a consumer may act on
#: ((lx)), so a cliff on the ERA sample, which is by construction the smaller
#: one, made the organ structurally incapable of ever feeding anything:
#: `n_with_era_claim` had been **0 across the whole fleet**, every day, since
#: the era twin shipped.
#:
#: Why 10 and not 0: measured in the same pass, a RETIRED book's 3-close era
#: sample (perps-donchian-breakout-lshadow, three near-identical wins, t=33)
#: yields a bound of **+2.97%/trade** with no floor at all — it would have
#: outranked every living book in the fleet on three trades. The t critical
#: value widens the interval for a thin sample but it cannot repair a VARIANCE
#: ESTIMATE built from three numbers.
#:
#: 10 is not a new invention: it is the winners' docket's own luck floor (I21 —
#: *"the n>=10 floor, not BH, is what stops a consistent 3-close streak from
#: outranking evidence"*), so the two instruments that rank books now agree.
MIN_N = int(os.environ.get("ALLOC_MIN_N", "10"))

#: [2026-08-20 (tz)] HOW HARD EVIDENCE TILTS THE SPLIT — and why it is a TILT
#: rather than the whole split.
#:
#: The original rule was `share = claim / total_claim`, which is WINNER-TAKE-ALL
#: whenever claims are sparse, because every unclaimed book contributes 0 to
#: both sides. Measured on the live payload the day this shipped: ONE book held
#: a claim of 0.0015 and took **$13,366 of $19,000**, two books held 78% of the
#: fleet's capital, and **17 of 19 books were cut to the 25% probe floor** —
#: including SIX with positive measured means (👩 mum +4.66%/trade, 🙏 avo
#: +1.09%, its live twin +0.82%, 🏛️ albanese +0.28%, 💸 the Farmer's shadow
#: +0.14% on n=195, 📊 georgia +0.12% on n=141).
#:
#: That is not conservatism, it is STARVATION, and it is self-fulfilling: a book
#: held at the floor accumulates evidence more slowly, so its bound stays wide,
#: so it stays at the floor. I17 already names the principle — *"a book cannot
#: earn evidence with no capital"* — and the split was violating it while the
#: floor was busy honouring it.
#:
#: So the FLAT allocation is the prior and evidence tilts it: the best-evidenced
#: book earns `1 + TILT` times an unclaimed book's weight, and nothing is
#: starved because a rival has a claim. At the default a claimant gets 2x the
#: weight of a book with no opinion — a real, bounded reward for evidence.
#: Set to 0 for a pure flat split; the old winner-take-all is NOT reachable by
#: any setting, deliberately.
CLAIM_TILT = float(os.environ.get("ALLOC_CLAIM_TILT", "1.0"))
BOOK_USD = float(os.environ.get("ALLOC_BOOK_USD", "1000"))

# Class membership is by the SIGNAL the book trades, not by its name. Funding
# books earn a carry that exists whether or not the price moves; directional
# books need the price to move their way. The measured gap between the two is
# the headline this organ exists to keep in front of the operator.
FUNDING_MARKERS = ("funding", "carry", "spread")

# [2026-08-05 (kc)] EXPLICIT ids for funding books the markers cannot see.
# 🎸 band-barnes-lshadow is the funding SUPER-BOOK ((jw): carry + extreme +
# xsect sleeves, every one of them a funding signal) and it was classed
# DIRECTIONAL, because the naming convention for that cohort is Australian
# musicians and a musician's surname contains no funding marker.
#
# A REGISTRY, not a wider marker list, and that is the whole point: widening
# FUNDING_MARKERS until it catches "barnes" would catch unrelated rows too —
# the same defect one layer over. Caught free: the book has ZERO closes today,
# so relabelling it moves no claim and no target_usd. It would have silently
# corrupted the by_class headline the moment Barnesy closed its first trade.
FUNDING_BOOKS = ("band-barnes-lshadow",
                 # [2026-08-13 (ls)] 🛢️ Garrett is the Farmer's file trading
                 # a funding gate in a thin volume band — funding by signal,
                 # invisible to the markers because "garrett" carries none.
                 # Caught while its ledger is still empty, like (kc) caught
                 # Barnesy: relabelling moves no claim today.
                 "band-garrett-lshadow",
                 # [2026-08-13 (ls)] 🏦 Rich Dad — funding carry by thesis
                 # (delta-neutral modelled cash flow); "kiyosaki" likewise
                 # carries no marker. Registered at birth, zero closes.
                 "book-kiyosaki-lshadow",
                 # [2026-08-13 (me)] 🧮 The Professor — funding carry by
                 # thesis (cost-of-carry, delta-neutral modelled) in the
                 # [2M,10M) mid tier; "hull" carries no marker. Registered
                 # at birth, zero closes. The other three second-wave books
                 # (douglas/grimes/schwager) are PRICE books and belong to
                 # the directional class — deliberately not listed.
                 "book-hull-lshadow")


def _iso(ts=None):
    return (ts or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def book_class(bot):
    """'funding' | 'directional'. By signal, not by name prefix."""
    b = str(bot or "").lower()
    if b in FUNDING_BOOKS:
        return "funding"
    return "funding" if any(m in b for m in FUNDING_MARKERS) else "directional"


def _betacf(a, b, x, itmax=200, eps=3e-14):
    """Continued fraction for the incomplete beta (Lentz). Stdlib only."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delt = d * c
        h *= delt
        if abs(delt - 1.0) < eps:
            break
    return h


def _betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t, df):
    """P(T <= t) for Student's t with `df` degrees of freedom."""
    x = df / (df + t * t)
    p = 0.5 * _betainc(df / 2.0, 0.5, x)
    return 1.0 - p if t > 0 else p


def t_crit(n, conf=None, floor=None):
    """The one-sided critical value this fleet applies to a sample of size `n`.

    [2026-08-20] WHY THIS EXISTS, and why a constant was wrong.

    The bound was `mean - 1.28*SE` at every sample size. 1.28 is the NORMAL
    quantile — the value a t-interval converges to as n grows — so applying it
    to n=4 or n=17 understates what a finite sample costs. The interval was too
    NARROW on exactly the books the fleet most needed to be careful about, and
    the mitigation in place for that was a hard `n >= 20` cliff, which does not
    widen anything: it deletes the estimate. One instrument was too generous and
    the other too blunt, and together they produced a table of zeros.

    The t critical value is the instrument that already does this job correctly
    and continuously: 1.533 at n=5, 1.337 at n=17, 1.290 at n=101, 1.2816 in the
    limit. A thin sample is doubted MORE, and it is doubted by an amount the
    sample itself determines rather than by a threshold someone picked.

    `floor` (default `Z_LOWER`) keeps the env lever live in the STRICT direction
    only — see the constant's own note. Fails toward the STRICTER value: any
    arithmetic trouble returns the floor rather than a guess, because the guess
    would be in the direction of handing out a claim.
    """
    conf = CONF if conf is None else conf
    floor = Z_LOWER if floor is None else floor
    try:
        df = int(n) - 1
        if df < 1:
            return None                 # no dispersion estimate exists at n<2
        lo, hi = 0.0, 200.0
        for _ in range(200):            # bisection: ~1e-58, far past need
            mid = (lo + hi) / 2.0
            if _t_cdf(mid, df) < conf:
                lo = mid
            else:
                hi = mid
        return max(floor, (lo + hi) / 2.0)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return floor


def sample_stats(pcts):
    """(n, mean, se) for a per-trade return sample, or None when the sample
    cannot support a bound (n<2 or variance below the floor).

    [2026-08-05 (kc)] EXTRACTED as the SINGLE OWNER of the admissibility rule.
    `lower_bound` is now a thin wrapper over it, so the published `mean_pct` /
    `se_pct` and the published `claim` cannot describe different samples — a
    second copy of this rule would be a second rule, and the two would drift
    exactly where it matters least visibly.
    """
    # `pcts or []` because this now runs on RAW payload input (allocate calls it
    # per book), not only behind claims()' n-guard — and it runs inside an organ
    # loop, where a TypeError on a junk row would take the whole publish down.
    v = [float(p) for p in (pcts or []) if p is not None]
    n = len(v)
    if n < 2:
        return None
    mean = sum(v) / n
    var = sum((x - mean) ** 2 for x in v) / (n - 1)
    # A VARIANCE FLOOR, not `var <= 0`. Identical returns do not give exactly
    # zero in floating point (30 x 0.01 sums to 0.30000000000000004), so the
    # naive check passes a variance of ~1e-36 through and the bound collapses
    # onto the mean — a degenerate book would then out-claim every real one.
    # Below the floor the sample is telling us nothing about dispersion.
    if var <= 1e-18:
        return None
    return n, mean, math.sqrt(var / n)


def bound_and_crit(pcts, z=None):
    """(lower bound, critical value) — computed TOGETHER, in one place.

    [2026-08-20] This function exists because of a mutation that survived. The
    first draft had `allocate` call `t_crit(n)` a second time to publish the
    `crit` field, so reverting `lower_bound` to a constant left the payload
    still advertising a t value it had not used — the published evidence would
    have described a different judgement than the published claim, silently.
    That is the second-copy-of-a-rule shape ((hj)) in miniature, inside a single
    file, and only a mutation exposed it (I3).
    """
    st = sample_stats(pcts)
    if st is None:
        return None, None
    n, mean, se = st
    crit = t_crit(n) if z is None else z
    if crit is None:                     # unreachable behind sample_stats' n>=2
        return None, None
    return mean - crit * se, crit


def lower_bound(pcts, z=None):
    """One-sided lower confidence bound on mean per-trade return.

    Returns None when the sample cannot support one (n<2 or zero variance) —
    NEVER 0.0, because "no opinion" and "measured zero" must not collapse into
    the same number. Callers treat None as undecided.

    [2026-08-20] `z=None` means DERIVE IT FROM THE SAMPLE (`t_crit`), which is
    the correct instrument and the default. An explicit `z` is honoured so a
    test can pin a value; production never passes one.
    """
    return bound_and_crit(pcts, z=z)[0]


def claims(books):
    """{bot: claim} — each book's non-negative claim on capital.

    `books` is {bot: [pnl_pct, ...]}. A book that is undecided (too few closes,
    or an uncomputable bound) claims 0 and falls back to the probe floor; a
    book whose lower bound is negative claims 0 too. Nothing goes below the
    floor, so this can only REDISTRIBUTE the surplus above it.
    """
    out = {}
    for bot, pcts in (books or {}).items():
        n = len([p for p in (pcts or []) if p is not None])
        lb = lower_bound(pcts) if n >= MIN_N else None
        out[bot] = max(0.0, lb) if lb is not None else 0.0
    return out


def n_req_claim(n, mean, se, conf=None):
    """How many closes this book needs before its OWN bound clears zero.

    [2026-08-20] THE FEED-DIRECTION NUMBER. `claim: 0.0` is the same byte for a
    book 46 closes away from a claim and one that will never have one, and a
    table of identical zeros is why this organ read as broken. Operator, the day
    this shipped: *"If everything is 0.000 then you've missed something."*

    Holding the sample's mean and dispersion fixed, `se` scales as 1/sqrt(n), so
    the bound clears zero once `n > (crit * sd / mean)^2`. `crit` itself depends
    on n, so iterate — it converges in a handful of passes because the critical
    value moves far more slowly than n.

    None when no amount of MORE OF THE SAME SAMPLE gets there (mean <= 0), which
    is the honest answer: that book does not need closes, it needs a different
    result. Never a promise — it is the floor of a projection, on the (ks)
    horizon's own terms, and nothing consumes it.
    """
    try:
        if not mean or mean <= 0 or not se or se <= 0 or n < 2:
            return None
        sd = se * math.sqrt(n)
        need = n
        for _ in range(12):
            crit = t_crit(max(2, int(math.ceil(need))), conf=conf)
            if crit is None:
                return None
            nxt = (crit * sd / mean) ** 2
            if abs(nxt - need) < 0.5:
                need = nxt
                break
            need = nxt
        # The FLOOR binds too: a book cannot hold a claim below MIN_N however
        # good its arithmetic looks, so reporting a smaller number would be a
        # lie about what the book actually needs.
        need = max(int(math.ceil(need)), MIN_N)
        return need if need > n else n
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def allocate(books, book_usd=BOOK_USD, floor=PROBE_FLOOR):
    """{bot: {target_usd, share, claim, n, class, ...}} — the evidence-weighted
    allocation of the SAME total capital the fleet already deploys.

    Total is conserved by construction: this never proposes spending more, only
    spending it differently. Every book keeps `floor` of the flat allocation as
    a probe; the surplus above the floors is split by claim. When NO book has a
    claim (the honest common case early on), the result is exactly the flat
    allocation — the organ says "no opinion" rather than inventing one.
    """
    bots = sorted(books or {})
    if not bots:
        return {}
    total = book_usd * len(bots)
    base = book_usd * max(0.0, min(1.0, floor))
    surplus = total - base * len(bots)
    cl = claims(books)
    # [(tz)] EVIDENCE TILTS THE FLAT SPLIT; IT DOES NOT REPLACE IT. Weights are
    # `1 + TILT * (claim / best_claim)`, so a book with no opinion still carries
    # weight 1 and cannot be defunded by a rival's claim. With no claims
    # anywhere every weight is 1 and this is EXACTLY the flat allocation, which
    # is the promise the docstring above already made and the old
    # `claim / total_claim` kept only in the degenerate all-zero case.
    best = max(cl.values()) if cl else 0.0
    if best > 0:
        w = {b: 1.0 + CLAIM_TILT * (cl[b] / best) for b in bots}
    else:
        w = {b: 1.0 for b in bots}
    tot_w = sum(w.values())
    out = {}
    for b in bots:
        n = len([p for p in (books[b] or []) if p is not None])
        share = w[b] / tot_w if tot_w > 0 else (1.0 / len(bots))
        target = base + surplus * share
        # [2026-08-05 (kc)] THE EVIDENCE RECORD. `mean` and `se` were computed
        # one line inside `lower_bound` and thrown away, so two books failing
        # for OPPOSITE reasons published byte-identical rows: measured today,
        # pm-rudd (n=94, mean -0.116%, t=-0.94, bound straddling zero) and
        # pm-abbott (n=79, mean -0.224%, t=-2.04, upper bound below zero) were
        # indistinguishable in the payload. The I17 keep-or-retire conversation
        # cannot start from a field that cannot tell "no edge" from "no sample".
        #
        # RAW INPUTS, deliberately not a verdict. `claim` stays the ONLY ranked
        # number and the ONLY field any consumer reads — I15's warning is that
        # a demoted-but-reported statistic migrates into an actuator, so these
        # ship as the inputs from which the published claim is exactly
        # reproducible, and nothing else.
        st = sample_stats(books[b])
        if st is None:
            why = "no-bound"          # n<2, or dispersion below the floor
        elif n < MIN_N:
            why = "below-min-n"
        elif cl[b] <= 0.0:
            why = "bound<=0"
        else:
            why = None
        # [2026-08-20] THE UN-TRUNCATED BOUND, and the distance to a claim.
        # `claim` is `max(0, bound)` and must stay that way — a book cannot
        # claim negative capital, and that field is the published contract every
        # consumer reads. But truncating at zero threw the ORDERING away: on the
        # live payload 15 of 19 books published byte-identical `0.0` while their
        # bounds ranged from -0.02% (📊 georgia, 46 closes from a claim) to
        # -0.64% (🏛️ albanese). Same number, entirely different situations, and
        # no reader could tell them apart. The information was computed and
        # discarded one character before the payload.
        #
        # REPORTED, NEVER RANKED — I15's warning is that a demoted-but-reported
        # statistic migrates into an actuator, so `claim` stays the only field
        # the split reads and these ship beside it as evidence.
        raw_bound, crit = bound_and_crit(books[b])
        out[b] = {
            "n": n,
            "class": book_class(b),
            "claim": round(cl[b], 6),
            # None, never 0.0 — "no opinion" and "measured zero" must not
            # collapse into the same number (lower_bound's own rule, carried
            # through to the payload boundary instead of stopping at it).
            "mean_pct": round(st[1], 8) if st else None,
            "se_pct": round(st[2], 8) if st else None,
            # The bound BEFORE `max(0, ...)`. None only when no bound exists.
            "bound_pct": round(raw_bound, 8) if raw_bound is not None else None,
            # The critical value this sample was actually judged at, so the
            # published claim is reproducible without re-deriving the rule.
            "crit": round(crit, 4) if crit is not None else None,
            # Closes needed for this book's own bound to clear zero, at its
            # measured mean and dispersion. None = a positive mean is not what
            # this sample has, so more of it will not get there.
            "n_req_claim": (n_req_claim(st[0], st[1], st[2]) if st else None),
            "target_usd": round(target, 2),
            "current_usd": round(book_usd, 2),
            "delta_usd": round(target - book_usd, 2),
            "undecided": n < MIN_N or cl[b] <= 0.0,
            "undecided_why": why,
        }
        # [2026-08-13 (lx)] DECLARED SHAPE, fail-CLOSED. The era twin is filled
        # by `run_once` (it needs the ledger rows and the era owner's import);
        # `build` cannot compute it, so it publishes the fields as None rather
        # than omitting them. That matters because a CONSUMER now reads
        # `claim_era` and an ABSENT key must not be distinguishable from "the
        # era has no opinion" — both mean no expansion. A payload that simply
        # lacked the key would read as absence-of-evidence and, under the old
        # habit of degrading to the permissive default, would have granted the
        # expansion this field exists to withhold (I6).
        set_era_twin(out[b], None, None)
    return out


def set_era_twin(rec, n_era, claim_era, era_iso=None, era_src=None):
    """The ONE writer of a published book row's era-twin fields.

    [2026-08-13 (lx)] Both `run_once` and the consumer tests go through here so
    the field NAMES have a single author. `claim_era` keeps `lower_bound`'s own
    distinction all the way to the payload boundary: None is "no opinion" (era
    sample below MIN_N, or the era rule unavailable), 0.0 is "measured, and the
    bound is at or below zero". A consumer must treat those the same in the
    EXPAND direction and it must not have to guess which it is holding.
    """
    rec["n_era"] = n_era
    rec["claim_era"] = (round(claim_era, 6) if claim_era is not None else None)
    rec["era_since"] = era_iso
    rec["era_source"] = era_src
    # [2026-08-16 (oy)] THE GATED OUTCOME, BESIDE THE PRE-GATE TARGET.
    # `target_usd` is what the RANKING wants; it is not what any consumer
    # does. The era gate that decides between them lives in another file, so
    # a reader of this payload alone could not tell that 🌾 carry's $10,072
    # target yields a scale of 1.00 — and on 16-Aug a reader did exactly that,
    # filed it as a growth item, and reported that capital was being
    # misallocated when none was. The number was always derivable and never
    # published; that is the defect, and this is the (lv)/I18 rule applied to
    # an ADVISORY organ — a payload must not be byte-identical between "this
    # book will be scaled up 4x" and "this book will be left at flat".
    # Written here because this is the moment `claim_era` becomes known, and
    # the outcome cannot be computed before it.
    scale = allocation_scale_for(rec, rec.get("current_usd"))
    rec["scale_effective"] = (round(scale, 4) if scale is not None else None)
    # The bit, named. `scale_effective < raw` says the era declined an
    # expansion; without the flag a reader must re-derive the raw scale to
    # notice. False when there was no expansion to decline (a reduction, or
    # already flat) — never conflate "declined" with "never asked".
    raw = None
    try:
        base = float(rec.get("current_usd") or 0.0)
        if base > 0:
            raw = float(rec.get("target_usd")) / base
    except (TypeError, ValueError):
        raw = None
    rec["expansion_gated"] = bool(
        raw is not None and raw > 1.0 and scale is not None and scale <= 1.0)
    return rec


def class_totals(alloc, books):
    """The headline: funding vs directional, on evidence and on P&L."""
    out = {}
    for cls in ("funding", "directional"):
        rows = [b for b in alloc if alloc[b]["class"] == cls]
        out[cls] = {
            "books": len(rows),
            "closes": sum(alloc[b]["n"] for b in rows),
            "current_usd": round(sum(alloc[b]["current_usd"] for b in rows), 2),
            "target_usd": round(sum(alloc[b]["target_usd"] for b in rows), 2),
            "n_with_claim": sum(1 for b in rows if alloc[b]["claim"] > 0),
            # [2026-08-15 (mz)] the ERA count beside the pooled one, at the
            # headline. Measured by the 15-Aug audit (verified): all three
            # positive claims were all-time-pooled and ZERO books had a
            # positive era-scoped bound — carry ranked #1 (57% of target
            # capital) on a sample 91/101 of whose closes predate its own
            # declared era boundary. The (lx) accessor gate already stops any
            # consumer from ACTING on a pooled claim; this stops a READER of
            # the headline from believing one. n_with_claim 3 /
            # n_with_era_claim 0 is the honest sentence.
            "n_with_era_claim": sum(
                1 for b in rows if (alloc[b].get("claim_era") or 0) > 0),
        }
    return out


def build(books, book_usd=BOOK_USD):
    """The published payload. Pure — the selftest drives it with no DB."""
    alloc = allocate(books, book_usd=book_usd)
    return {
        "updated": _iso(),
        "ttl_sec": TTL_SEC,
        "advisory": True,
        "moves_capital": False,
        "rule": (f"claim = max(0, mean - t*SE) on per-trade %, t = one-sided "
                 f"Student-t at {CONF:.0%} on n-1 df (floor {Z_LOWER}), "
                 f"n>={MIN_N}; every book keeps a {PROBE_FLOOR:.0%} probe "
                 f"floor; total capital is conserved"),
        "n_books": len(alloc),
        "book_usd": book_usd,
        "by_class": class_totals(alloc, books),
        "books": alloc,
    }


# --------------------------------------------------------------------------
# I/O shell
# --------------------------------------------------------------------------
def _living(trades):
    """Drop retired books, exact-match against the fleet's own retirement
    authority. Fail-OPEN: no list -> keep everything, so an import failure can
    never silently blank the view."""
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as retired
        retired = set(retired)
    except Exception:                                # noqa: BLE001
        retired = set()
    return [t for t in trades if t.get("bot") not in retired], len(retired)


#: Max age of a bot_pnl row for its book to count as LIVING. Generous on
#: purpose: excluding a live book breaks I17's probe floor, while including a
#: quiet one only hands it the floor it was already entitled to.
LIVING_MAX_AGE_H = float(os.environ.get("ALLOC_LIVING_MAX_AGE_H", "24"))


def _living_book_ids():
    """Every book with a fresh, non-retired bot_pnl row — INCLUDING books that
    have never closed a trade.

    [2026-08-05 (kc)] I17 says "every living book keeps a 25% probe floor,
    because a book cannot earn evidence with no capital". The I/O shell built
    `books` from LEDGER ROWS ONLY, so a book with zero closes never entered the
    payload at all and got no floor — the organ was silent about exactly the
    case the invariant was written for. Measured today: 🎸 band-barnes-lshadow
    (10 open, 0 closed), 📊 equities-regime-lshadow (5 open) and
    👩 freqtrade-mum-lshadow (4 open) were all missing.

    Its declared enforcement (test_every_book_keeps_a_probe_floor) passed
    throughout, because it drives `allocate` with hand-built fixtures that
    always contain the book — the CLAUDE.md header caveat instantiated: a green
    run verifies the enforcement EXISTS, not that it is CORRECT.

    Fail-OPEN in both directions, like `_living`: no DB read, or an unreadable
    stamp, keeps the book rather than dropping it.
    """
    rows = store.fetch_bot_pnl() if store is not None else None
    if not rows:
        return []
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as retired
        retired = set(retired)
    except Exception:                                # noqa: BLE001
        retired = set()
    out, now = [], datetime.now(timezone.utc)
    for r in rows:
        bot = r.get("bot")
        if not bot or bot in retired:
            continue
        # A TRADING BOOK reports trade counts; a service row does not. Measured
        # on the live table: `market-context` publishes open/closed = None/None
        # and is a market-data publisher, not a book — allocating capital to it
        # would be a category error. Semantic, not a name list, so a future
        # service row is excluded the day it appears rather than the day
        # somebody remembers to add it. A brand-new book publishing 0/0 still
        # qualifies, which is I17's case exactly.
        if r.get("open_trades") is None and r.get("closed_trades") is None:
            continue
        stamp = r.get("updated_at")
        try:
            ts = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now - ts).total_seconds() > LIVING_MAX_AGE_H * 3600.0:
                continue
        except Exception:                            # noqa: BLE001
            pass                     # unreadable stamp -> keep (fail-open)
        out.append(bot)
    return out


def _era_twin(bot, rows):
    """(n_era, claim_era, iso, source) — the SAME claim recomputed on the
    era-scoped sample the go-live grader actually grades.

    [2026-08-05 (kc)] WHY THIS SHIPS AS A TWIN AND NOT AS THE SAMPLE: measured
    over 15 historical days, era-scoping as the ALLOCATION sample had ZERO
    claimants on 15 of 15 — it turns the organ off, and its forward realised
    return was byte-identical to flat. So the all-time claim stays the ranked
    number and this rides beside it as DISCLOSURE, because the gap is the most
    important single fact about this payload: measured today, 🌾 carry's
    fleet-best 0.152% claim rests on 88 closes of which exactly ONE is in-era
    (its declared era is 31-Jul, the two-writer window), and the Farmer shadow's
    0.199% claim goes to zero under the era rule.

    [2026-08-13 (lx)] IT IS NO LONGER DISCLOSURE-ONLY — corrected in place (I12)
    rather than left describing the system as it was. `fleet_bus.allocation_
    scale` now reads this field and refuses to scale a book ABOVE the flat
    allocation unless the era claim is a positive number. `(kc)`'s measurement
    is untouched and still governs the RANKING: era-scoping the ranked claim
    turns the organ off, so it was not done, and no book loses a claim here.
    What changed is only the EXPAND direction at the consumer, which `(kc)` did
    not measure because on 05-Aug there was no consumer at all. The restrict
    direction — the 25% probe floor — still comes from the all-time claim, so a
    thin era can never make a book BIGGER than the evidence supports nor smaller
    than its probe floor.

    The era rule is IMPORTED from its owner, never re-derived — a second copy of
    a rule is a second rule. Fail-safe: any import or parse failure publishes
    None (no opinion), never a fabricated era.
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "scripts"))
        from golive_readiness import era_rows
        from experiment_judge import parse_ts
    except Exception:                                # noqa: BLE001
        return None, None, None, None
    quads = []
    for r in rows or []:
        try:
            ts = datetime.fromtimestamp(parse_ts(r.get("close_ts")),
                                        tz=timezone.utc)
        except Exception:                            # noqa: BLE001
            continue
        quads.append((r.get("profit_ratio"), r.get("profit_abs"), ts,
                      r.get("open_ts"), r.get("extra")))
    if not quads:
        return None, None, None, None
    quads.sort(key=lambda q: q[2])       # era_rows takes them oldest first
    try:
        ed = era_rows(bot, quads, parse=parse_ts, detail=True)
    except Exception:                                # noqa: BLE001
        return None, None, None, None
    pcts = [q[0] for q in (ed.get("scoped") or [])]
    n_era = len([p for p in pcts if p is not None])
    lb = lower_bound(pcts) if n_era >= MIN_N else None
    # None (no opinion), never 0.0 — the same distinction lower_bound draws.
    claim_era = max(0.0, lb) if lb is not None else None
    return n_era, claim_era, ed.get("iso"), ed.get("source")


def run_once(publish=False):
    if store is None:
        return None
    trades, n_retired = _living(store.fetch_paper_trades(limit=8000))
    rows_by_bot = {}
    for t in trades:
        bot = t.get("bot")
        pct = t.get("profit_ratio", t.get("pnl_pct"))
        if bot and pct is not None:
            rows_by_bot.setdefault(bot, []).append(t)
    # [(kc)] seed the ZERO-CLOSE living books so I17's floor reaches them.
    zero_close = []
    for bot in _living_book_ids():
        if bot not in rows_by_bot:
            rows_by_bot[bot] = []
            zero_close.append(bot)
    books = {b: [r.get("profit_ratio", r.get("pnl_pct")) for r in rs]
             for b, rs in rows_by_bot.items()}
    payload = build(books)
    payload["excluded_retired"] = n_retired
    payload["zero_close_books"] = sorted(zero_close)
    # [(kc)] Say WHICH sample the ranked claim is computed on. Three organs
    # grade this fleet on three different samples — allocation pools all-time,
    # golive_readiness scopes to the policy era, the brain decays at a 14d
    # half-life — and only this one had no label saying so.
    payload["sample"] = "all-time-pooled"
    for b, rs in rows_by_bot.items():
        rec = payload["books"].get(b)
        if rec is None:
            continue
        set_era_twin(rec, *_era_twin(b, rs))
    # [2026-08-26] RECOMPUTE THE HEADLINE, because it was counting a field that
    # did not exist yet.
    #
    # `build()` computes `by_class` — including `n_with_era_claim` — and the era
    # twin is filled HERE, afterwards, because it needs the ledger rows and the
    # era owner's import. `build` cannot know it, so it sets every `claim_era`
    # to None first ((lx)). So the counter ran over a column that was None on
    # every book, by construction, and `n_with_era_claim` could only ever be
    # ZERO — whatever the data said.
    #
    # MEASURED the day this was found: `freqtrade-avo-maria-lighter` published
    # `claim_era: 0.000174` — a real, positive, era-scoped claim — while the
    # headline beside it read `n_with_era_claim: 0`. The payload contradicted
    # itself in the one field a reader checks first.
    #
    # It is exactly the failure `(ua)` was written about, one layer up: that
    # entry quoted this zero as evidence that no book COULD qualify, and the
    # cliff it removed was a real cause — but even with the cliff gone the
    # number could not move, because the count precedes the data. A headline
    # that cannot be non-zero is not a measurement. Corrected in place per I12.
    payload["by_class"] = class_totals(payload["books"], books)
    # The go-live verdict is IMPORTED, never re-derived here — allocation is a
    # different question and must not become a second gate. Optional by design:
    # that module is the other half of the fleet's grading surface and this
    # organ must not go dark if it moves.
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "scripts"))
        from golive_readiness import GOLIVE_MIN_CLOSES
        payload["golive_min_closes"] = GOLIVE_MIN_CLOSES
    except Exception:                                # noqa: BLE001
        payload["golive_min_closes"] = None
    if publish:
        try:
            store.save_state(KEY, payload)
            store.save_history(KEY, {"by_class": payload["by_class"],
                                     "n_books": payload["n_books"],
                                     "updated": payload["updated"]})
        except Exception as e:                       # noqa: BLE001
            print(f"[fleet-allocation] publish failed: {e}", file=sys.stderr)
    return payload


def _print(payload):
    # [(kc)] mean/se and the era twin are shown because the two failure modes
    # they separate — "no edge" and "no sample" — have OPPOSITE remedies, and
    # the table could not tell them apart.
    print(f"\n{'book':34s} {'cls':11s} {'n':>4} {'mean%':>8} {'se%':>7} "
          f"{'claim':>9} {'target$':>8} {'nEra':>5} {'claimEra':>9}  why")
    print("-" * 118)
    for b, r in sorted(payload["books"].items(),
                       key=lambda kv: -kv[1]["target_usd"]):
        def _f(x, w, p):
            return f"{x*100:>{w}.{p}f}" if isinstance(x, (int, float)) else \
                   f"{'-':>{w}}"
        ce = r.get("claim_era")
        print(f"{b:34s} {r['class']:11s} {r['n']:>4} "
              f"{_f(r.get('mean_pct'), 8, 3)} {_f(r.get('se_pct'), 7, 3)} "
              f"{r['claim']:>9.5f} {r['target_usd']:>8.0f} "
              f"{(r.get('n_era') if r.get('n_era') is not None else '-'):>5} "
              f"{(f'{ce:.5f}' if ce is not None else '-'):>9}"
              f"  {r.get('undecided_why') or ''}")
    print()
    for cls, c in payload["by_class"].items():
        print(f"  {cls:11s} {c['books']:2d} books  {c['closes']:5d} closes  "
              f"${c['current_usd']:>7.0f} -> ${c['target_usd']:>7.0f}  "
              f"({c['n_with_claim']} with a measured claim)")
    print("\nADVISORY ONLY — this organ moves no capital, writes no lever and "
          "promotes nothing.\nRule: " + payload["rule"])


def _selftest():
    # --- lower_bound: "no opinion" must never look like "measured zero" ----
    assert lower_bound([]) is None and lower_bound([0.01]) is None
    assert lower_bound([0.01] * 30) is None, "zero variance -> no opinion"
    lb = lower_bound([0.02, 0.01, 0.03, -0.01] * 10)
    assert lb is not None and lb < sum([0.02, 0.01, 0.03, -0.01]) / 4, \
        "the bound must sit BELOW the mean"
    # a wider sample tightens the bound toward the mean — the whole point of
    # ranking on a bound rather than a mean
    tight = lower_bound([0.02, 0.01, 0.03, -0.01] * 100)
    assert tight > lb, "more evidence must strengthen the claim"

    # --- an undecided book claims nothing but keeps its probe floor --------
    thin = {"a": [0.05, 0.04, 0.06, 0.05, 0.05],          # big mean, n=5
            "b": [0.002, 0.001, 0.003, 0.002] * 20}      # modest, well-evidenced
    al = allocate(thin, book_usd=1000.0)
    assert al["a"]["undecided"] is True, "n=5 cannot claim capital"
    assert al["a"]["target_usd"] >= 250.0, "a probe floor is not optional"
    # ...and a big mean on a tiny sample must NOT beat a modest, well-evidenced
    # one. This is the single assertion that makes the rule worth having.
    assert al["b"]["target_usd"] > al["a"]["target_usd"], \
        "lucky small samples must not outrank measured ones"

    # --- total capital is CONSERVED: this never proposes spending more -----
    for books in (thin, {"x": [0.01, 0.02, 0.0, 0.015] * 12,
                         "y": [-0.02, -0.01, -0.03, 0.0] * 12, "z": []}):
        a = allocate(books, book_usd=1000.0)
        assert abs(sum(r["target_usd"] for r in a.values())
                   - 1000.0 * len(a)) < 0.05, "allocation must conserve total"

    # --- no claims anywhere -> EXACTLY the flat allocation ("no opinion") --
    flat = allocate({"p": [-0.02, -0.01, -0.03, 0.0] * 10,
                     "q": [-0.03, -0.02, -0.01, -0.04] * 10}, book_usd=1000.0)
    for r in flat.values():
        assert abs(r["target_usd"] - 1000.0) < 0.05, \
            "with no positive claim the organ must say nothing, not invent"

    # --- a negative book is floored, never negative ------------------------
    # NOTE the fixtures VARY. A constant return series has zero variance, which
    # `lower_bound` correctly refuses to score — so a constant fixture would
    # test the degenerate path and quietly prove nothing about ranking. Real
    # books have dispersion; the fixture must too.
    neg = allocate({"bad": [-0.06, -0.04, -0.05, -0.03] * 10,
                    "good": [0.03, 0.01, 0.02, 0.04] * 10}, book_usd=1000.0)
    assert neg["bad"]["claim"] == 0.0 and neg["bad"]["target_usd"] >= 250.0
    assert neg["good"]["target_usd"] > neg["bad"]["target_usd"]

    # --- class split is by SIGNAL, not by name prefix ----------------------
    assert book_class("perps-funding-carry-lshadow") == "funding"
    assert book_class("perps-funding-spread-lshadow") == "funding"
    assert book_class("crypto-trend-daily-lshadow") == "directional"
    assert book_class("lighter-ticket-taker-lighter") == "directional"
    assert book_class(None) == "directional", "unknown must not claim funding"
    # [(kc)] the funding SUPER-BOOK carries a musician's name, so no marker can
    # see it. Registry first, markers second.
    assert book_class("band-barnes-lshadow") == "funding", \
        "the funding super-book must not be classed directional"

    # --- [(kc)] THE EVIDENCE RECORD reproduces the published claim ---------
    # mean_pct/se_pct are the INPUTS to the ranked number, so the payload must
    # be self-describing: if these two cannot rebuild `claim`, they describe a
    # different sample than the one that was ranked.
    ev = allocate({"w": [0.02, 0.01, 0.03, -0.005] * 8}, book_usd=1000.0)["w"]
    assert ev["mean_pct"] is not None and ev["se_pct"] is not None
    # [2026-08-20] reproduce through the PUBLISHED `crit`, not through the
    # module constant. The critical value now varies with n, so a reader with
    # only the payload must still be able to rebuild the ranked number — that
    # is what makes `crit` load-bearing rather than decorative.
    assert ev["crit"] is not None
    assert abs(ev["claim"] - max(0.0, ev["mean_pct"]
                                 - ev["crit"] * ev["se_pct"])) < 1e-5, \
        "the published claim must be reproducible from the published stats"
    assert abs(ev["bound_pct"] - (ev["mean_pct"]
                                  - ev["crit"] * ev["se_pct"])) < 1e-5, \
        "bound_pct must be the SAME bound, before the max(0, .) truncation"
    # a claim ALWAYS sits below its own sample mean — this is what red-lines
    # any estimator (pooling, shrinkage, a rate multiplier) that would hand a
    # book a claim its own sample cannot support.
    assert ev["claim"] < ev["mean_pct"], "a bound must sit below the mean"
    assert ev["undecided_why"] is None and ev["undecided"] is False

    # "no opinion" must reach the payload as None, never as 0.0 --------------
    thin_ev = allocate({"t": [0.01, 0.02]}, book_usd=1000.0)["t"]
    assert thin_ev["claim"] == 0.0 and thin_ev["undecided_why"] == "below-min-n"

    # --- [2026-08-20] THE CRITICAL VALUE IS THE T VALUE, NOT A CONSTANT ------
    # Pinned against the PUBLISHED table. A future "simplification" back to a
    # bare 1.28 reddens here, which is the whole point of writing the numbers
    # down rather than trusting the implementation.
    for df, want in ((1, 3.0777), (2, 1.8856), (5, 1.4759), (10, 1.3722),
                     (16, 1.3368), (30, 1.3104), (100, 1.2901)):
        got = t_crit(df + 1, floor=0.0)
        assert abs(got - want) < 5e-4, f"t_crit df={df}: {got} vs {want}"
    assert abs(t_crit(10_000_001, floor=0.0) - 1.2816) < 1e-3, \
        "t must converge to the normal quantile in the large-sample limit"
    # MONOTONE: a thinner sample is doubted MORE. This is the property the whole
    # change rests on — it is what lets the n>=20 cliff go away safely.
    crits = [t_crit(k, floor=0.0) for k in (3, 5, 10, 20, 50, 200)]
    assert all(a > b for a, b in zip(crits, crits[1:])), crits
    assert t_crit(1) is None, "n<2 has no dispersion estimate, so no bound"
    # The env lever may only TIGHTEN — never loosen past what n supports.
    assert t_crit(500, floor=2.0) == 2.0
    assert t_crit(3, floor=1.28) > 1.28

    # --- the same sample, judged honestly, still ranks above a luckier one ---
    # n=17 at t=1.92 keeps a claim (the live 🙏 avo shadow shape); n=3 at a
    # freak t does NOT, because MIN_N stops it before the statistics (I21).
    lucky = allocate({"three": [0.031, 0.030, 0.032],
                      "seventeen": [0.03, 0.01, 0.02, 0.04, 0.005] * 3 + [0.02, 0.03]},
                     book_usd=1000.0)
    assert lucky["three"]["claim"] == 0.0, \
        "a 3-close streak must not out-claim a measured book (I21's floor)"
    assert lucky["seventeen"]["claim"] > 0.0
    assert lucky["seventeen"]["target_usd"] > lucky["three"]["target_usd"]

    # --- the FEED number: a zero claim must say what the book NEEDS ---------
    # 15 of 19 live books published byte-identical 0.0; this is what makes them
    # distinguishable without turning a report into a bar.
    near = allocate({"near": [0.02, -0.018, 0.021, -0.019, 0.001] * 6},
                    book_usd=1000.0)["near"]
    assert near["claim"] == 0.0 and near["bound_pct"] is not None
    assert near["bound_pct"] < 0, "a floored claim must still publish its bound"
    assert near["n_req_claim"] and near["n_req_claim"] > near["n"], \
        "a positive-mean book below the bar must publish its distance to it"
    loser = allocate({"loser": [-0.02, -0.01, -0.03, 0.0] * 6},
                     book_usd=1000.0)["loser"]
    assert loser["n_req_claim"] is None, \
        "a negative mean needs a different result, not more closes — say so"
    flat_ev = allocate({"f": [0.01] * 30}, book_usd=1000.0)["f"]
    assert flat_ev["mean_pct"] is None and flat_ev["se_pct"] is None, \
        "zero variance is NO OPINION — it must not publish a mean"
    assert flat_ev["undecided_why"] == "no-bound"
    neg_ev = allocate({"g": [-0.02, -0.01, -0.03, 0.0] * 8}, book_usd=1000.0)["g"]
    assert neg_ev["undecided_why"] == "bound<=0" and neg_ev["claim"] == 0.0
    assert neg_ev["mean_pct"] is not None, \
        "a measured loser still publishes its measurement"

    # a ZERO-CLOSE book still gets a row and a floor (I17's actual case) -----
    z = allocate({"empty": [], "real": [0.01, 0.02, 0.0, 0.015] * 8},
                 book_usd=1000.0)
    assert z["empty"]["n"] == 0 and z["empty"]["target_usd"] >= 250.0, \
        "a book with no closes is exactly the case the probe floor is for"
    assert z["empty"]["undecided_why"] == "no-bound"

    # --- the payload is honest about what it is ---------------------------
    p = build({"m": [0.01, 0.02, 0.0, 0.015] * 10})
    assert p["advisory"] is True and p["moves_capital"] is False
    assert p["ttl_sec"] > 0 and p["updated"]
    assert json.dumps(p), "payload must be JSON-serialisable for the bus"

    # --- junk in must not raise: this runs in an organ loop ---------------
    for junk in ({}, {"a": None}, {"a": [None, None]}, {"a": ["x", 1]}):
        try:
            build(junk)
        except (TypeError, ValueError):
            pass                      # a typed rejection is fine
    print("fleet_allocation selftest OK (bound < mean, evidence beats luck, "
          "total conserved, no-claim -> flat, floors hold, advisory stamped)")
    return 0


def _cli():
    # [2026-08-01 (hw)] the CLI body lives in a function so the
    # shared organ wrapper can catch its faults — run_all.sh runs
    # this behind `|| true`, which otherwise hides every crash.
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    pay = run_once(publish="--publish" in sys.argv)
    if pay is None:
        print("fleet_allocation: no DB (DATABASE_URL unset) — nothing to read.")
        sys.exit(0)
    _print(pay)


if __name__ == "__main__":
    sys.exit(store.organ_main('fleet-allocation', _cli))
