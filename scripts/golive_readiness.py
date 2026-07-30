#!/usr/bin/env python3
"""golive_readiness.py — grade every shadow book against the go-live bar.

WHY (2026-07-29, operator: "give the carry book a promotion path, and fix the
gate that would reject it").

TWO PIPELINES, and conflating them is why the best book had no path:
  * The EXPERIMENT JUDGE re-parameterises a book that is ALREADY live — it
    needs a live arm to pair the shadow against. `perps-funding-carry-lshadow`
    has no live arm, so the judge can never reach it. That is not an oversight
    in the judge; it is the wrong pipeline for the question.
  * A NEW book's path to real money is the GO-LIVE GATE. It had no
    implementation at all — the rule lived in CLAUDE.md as prose and was
    applied by hand, which is how it went un-noticed that it would reject the
    fleet's best-evidenced book.

THE GATE DEFECT. CLAUDE.md's rule reads: *"Paper trading only until 30-day win
rate > 55% AND max drawdown < 15%"*. Measured 29-Jul, the carry book is the
fleet's strongest by every evidence measure — t=2.42 on n=80, both halves
positive (+42.42 / +13.78), realised +$56.20, unrealised +$7.62 (so the
hedged-book "close only when paid" artifact is NOT masking open losses),
maxDD −$6.13 — and it **wins 38.8% of its trades**. It is a low-win-rate,
positive-expectancy book, and a win-rate gate is orthogonal to expectancy:
it would reject this book forever while admitting a high-win-rate book that
loses money on the tails. Same non-sequitur shape as the tp-0.06 rationale
this session already refuted, except sitting in the rule that governs real
money.

THE REPLACEMENT BAR is this repo's own doctrine, applied to a whole book:
  window   >= GOLIVE_MIN_DAYS (30)      the operator's, unchanged
  evidence >= GOLIVE_MIN_CLOSES (30)    fills, never hours
  positive    mean per-trade > 0        in its own right
  SIGNIFICANT t >= GOLIVE_MIN_T (2.0)   a positive LOWER bound, not a max
  ROBUST      both halves positive      the fleet's central noise filter
  maxDD    <  GOLIVE_MAX_DD (15%)       the operator's, unchanged

Win rate is still REPORTED — it is informative — but it is not a bar.

HONEST ABOUT DIRECTION: this is not uniformly stricter. It drops a
requirement the carry book fails and adds two (significance, both-halves)
that the old rule never had. For a high-win-rate/negative-expectancy book it
is STRICTER; for carry it is what makes go-live reachable at all. That is a
real loosening for that book and is stated here rather than buried.

REGIME CAVEAT (21-Jul item 18): Lighter's tape is one falling-BTC regime, so
"both halves" is weak for anything DIRECTIONAL. Reported per book; funding
books (carry, Farmer, spread) are largely direction-agnostic so it bites less,
but a directional book passing here has passed in ONE regime only.

POLICY ERAS (2026-07-30 (hc)) — the bar counts a book's CURRENT self. Until
now this grader pooled a book's whole retained ledger, so a change that made
the earlier record WRONG kept counting toward the 30-day bar. See POLICY_ERA
below for the measurement that forced this, and for the rule about which
changes reset an era and which deliberately do not.

READ-ONLY. Grades and prints. Promotes nothing, writes no lever, flips no
dry_run — go-live remains an explicit operator act
([[no-real-money-without-explicit-golive]]).

Usage:
  DATABASE_URL=... python3 scripts/golive_readiness.py
  python3 scripts/golive_readiness.py --selftest
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

GOLIVE_MIN_DAYS = float(os.environ.get("GOLIVE_MIN_DAYS", "30"))
GOLIVE_MIN_CLOSES = int(os.environ.get("GOLIVE_MIN_CLOSES", "30"))
GOLIVE_MIN_T = float(os.environ.get("GOLIVE_MIN_T", "2.0"))
GOLIVE_MAX_DD = float(os.environ.get("GOLIVE_MAX_DD", "0.15"))
GOLIVE_LEGACY_WIN = float(os.environ.get("GOLIVE_LEGACY_WIN", "0.55"))
BOOK_USD = float(os.environ.get("GOLIVE_BOOK_USD", "1000"))
# [2026-07-30] bot_state key + TTL for the published verdicts (see main()).
KEY = "golive-readiness"
TTL_SEC = int(os.environ.get("GOLIVE_TTL_SEC", "86400"))


# ---------------------------------------------------------------------------
# POLICY ERAS
# ---------------------------------------------------------------------------
# [2026-07-30 (hc)] THE GATE HAD NO NOTION OF WHEN A BOOK BECAME ITSELF.
#
# It graded each book's whole retained ledger. So a book could change in a way
# that makes its earlier P&L simply WRONG, keep the old numbers, and go on
# accumulating them toward the 30-day bar. Measured on the book that is closest
# to real money — 🌾 `perps-funding-carry-lshadow`, the fleet's frontrunner at
# five of six bars:
#
#     opened BEFORE 2026-07-17   n=25   +$62.03
#     opened SINCE  2026-07-17   n=57   -$0.91
#
# **101% of its entire realised P&L was opened before 17-Jul** (+$62.03 of
# +$61.12), and it has been flat-to-negative for 13 days and 57 closes since.
# The pooled grade is 5/6 bars — mean +0.248%, t=+2.60, both halves positive —
# and every one of those numbers is carried by the earlier segment.
#
# WHAT CHANGED ON 17-JUL. `funding_carry_bot.py`'s own comment: the accrual
# line `rate * dt_h` "is only right when the quote IS hourly. On the
# lighter_shadow arm the quote is per 8h, so this over-accrued 8x — straight
# into `accrued`, which IS this book's reported P&L and its win/loss call."
#
# THE EXACT DATE IS NOT LOAD-BEARING, which is what makes this safe to declare
# without container archaeology. The comment is dated 17-Jul but this file only
# entered `main`'s history on 28-Jul (PR #95), so when the RUNNING container
# changed is not established here. It does not matter: the verdict is the same
# at every candidate boundary —
#     era >= 17-Jul   n=57  -$0.91   mean -0.005%  t -0.08   2/6 bars
#     era >= 22-Jul   n=28  +$0.60   mean +0.007%  t +0.10   2/6 bars
#     era >= 28-Jul   n= 6  +$5.66   mean +0.314%  t +1.24   3/6 bars
# — so 17-Jul is used because it is the date the code's own comment carries AND
# the most generous of the three. A finding that survives its own sensitivity
# analysis does not need the archaeology settled.
#
# THE ERA DOES NOT REST ON THAT DIAGNOSIS, deliberately. A competing
# explanation exists and is not eliminated here: the venue's funding may simply
# have been hotter in early July (it is still hot — the live row shows carries
# at +84% to +722% APR), which would shrink accrual per hold with no bug at
# all. Either way the gate's own question — *does this book, as it now runs,
# make money* — is answered by the 57 closes, not by the 25. That is why the
# era is defensible without settling the cause, and the 30-day re-grade is what
# settles it.
#
# WHICH CHANGES RESET AN ERA, and this limit is load-bearing:
#   RESET      a change that makes earlier P&L WRONG (an accounting or
#              accrual-basis fix) or makes the strategy DIFFERENT IN KIND (a
#              rewritten entry/exit rule, a venue move).
#   DO NOT     ordinary tuning — a lever step, a widened universe, a clip
#              change. The growth rail moves levers continuously BY DESIGN; if
#              every move reset the clock, no book could ever reach 30 days and
#              this guard would become a way of never promoting anything.
# Carry's OWN 21-Jul `ENTER_APR` 0.40 -> 1.60 is the worked example of the
# second kind: measured, deliberate, enacted from a sweep — and NOT an era
# reset, even though splitting there too would restrict the book further
# (n=31, -$0.76). The guard is not for maximising restriction.
#
#: {bare bot id: (ISO date, why)}. Keyed BARE — the ledger's `bot` carries a
#: `-lshadow` / `-lighter` suffix and `era_epoch_for` strips it, which is the
#: bug the brain shipped for nine days (bot_learn.era_epoch_for, 23-Jul audit:
#: "every `ERA_START.get(bot)` missed and every bot was graded on its WHOLE
#: retained ledger"). Absence of an entry means grade ALL-TIME — the behaviour
#: before this block, so no other book's verdict moves.
POLICY_ERA = {
    "perps-funding-carry": (
        "2026-07-17",
        "the lighter_shadow arm's accrual basis was fixed from per-hour to the "
        "venue's own per-8h settlement; for a funding book the accrual IS the "
        "P&L, so closes opened before it are denominated in a unit the book no "
        "longer uses. 25 closes at +$62.03 before, 57 at -$0.91 since."),
    # [2026-07-30 (hg)] 💸 Funding Farmer — the SAME basis fix, on the pair that
    # includes a REAL-MONEY book. One bare key covers both rows: `era_epoch_for`
    # strips `-lighter` and `-lshadow`.
    #
    # THE BOT SAYS IT ITSELF, at `lighter_funding_bot.py`'s accrual line: *"this
    # line accrued it PER HOUR = 8x. Live equity is honest (the venue charges
    # the real thing) but this figure reaches the per-trade ledger AND the
    # win/loss call — an inflated carry credit inflates the win rate of a book
    # that COLLECTS carry."* The ledger is what every grader reads.
    #
    # MEASURED, and this is why it could not wait: `perps-funding-lighter-
    # lshadow` was reported ONE HOUR AGO as the fleet's new go-live frontrunner
    # at 5/6 bars, t=+2.09, both halves positive. Scoped to the post-fix era it
    # is **3/6, t=+0.74, and h1 goes NEGATIVE** (-0.63). Its win rate falls 56%
    # -> 45%, exactly the inflation the bot's comment predicts for a
    # carry-collecting book.
    #     boundary      n    t     h1      h2    win   bars
    #     all-time     85  +2.09  +11.94  +2.45  56%   5/6   <- the only 5/6
    #     >= 17-Jul    47  +0.74   -0.63  +3.91  45%   3/6
    #     >= 22-Jul    20  +1.07   +2.95  -0.58  55%   2/6
    #     >= 28-Jul     3  +1.09   +0.16  +0.11  67%   3/6
    # **No post-fix boundary passes the t bar at all** (0.74 / 1.07 / 1.09 vs
    # 2.0). All-time is the single window in which this book looks ready.
    #
    # THE LIVE ROW MOVES TOO, in what it REPORTS rather than in its bar count:
    # 4/6 either way, but t +1.57 -> +1.07 and **win rate 63% -> 50%** on the
    # book that actually holds money and whose tag the brain has jurisdiction
    # over since (bb).
    #
    # NOT AFFECTED, checked rather than assumed: the promotion judge. Every arm
    # comparison goes through `arm_trades(rows, bot, start_ts, end_ts)` and its
    # windows begin at the candidate's own `started_ts`, all of which postdate
    # 17-Jul — so the pipeline that is the ONLY writer of `live.funding.*` is
    # era-safe by construction, not by luck. Pinned by a test.
    "perps-funding-lighter": (
        "2026-07-17",
        "the same per-hour/per-8h accrual basis fix, on the Funding Farmer pair "
        "— a REAL-MONEY book and its shadow twin. The bot's own comment: the "
        "pre-fix figure 'reaches the per-trade ledger AND the win/loss call'. "
        "Measured: the shadow twin reads 5/6 bars at t=+2.09 all-time and 3/6 "
        "at t=+0.74 with h1 NEGATIVE in-era; no post-fix boundary passes the t "
        "bar. The live row's win rate reads 63% pooled against 50% in-era."),
    # [2026-07-30 (hg)] THE RULE, APPLIED UNIFORMLY. The 17-Jul basis fix was
    # FLEET-WIDE — every `[2026-07-17 BASIS FIX]` in a shipped bot carries the
    # same date — so declaring it for two books and not the rest would be
    # cherry-picking the ones whose numbers I happened to look at. Membership is
    # RULE-DRIVEN: the book's publisher accrues funding AND the book has closes
    # opened before the fix. Books whose publisher does NOT accrue (🧲 Snap Back,
    # 🎯 Perp Sniper) are deliberately absent — a price book's P&L cannot carry
    # an accrual defect, and declaring an era "for symmetry" would discard real
    # evidence for nothing.
    #
    # Measured effect (pooled -> in-era), so the direction is on the record:
    #   lighter-ticket-taker-lshadow   3/6 t-0.39 win38%  ->  2/6 t-1.45 win34%
    #   freqtrade-georgia-lshadow      3/6 t+0.03 win47%  ->  2/6 t-0.05 win46%
    #   perps-funding-spread-lshadow   3/6 t+1.14 win56%  ->  3/6 t+1.30 win68%
    #   crypto-intraday-15m-lshadow    2/6 t-0.66 win53%  ->  3/6 t+0.41 win59%
    #   freqtrade-dad-lshadow          1/6 t-3.59 win20%  ->  1/6 t-1.90 win33%
    #   crypto-breakout-4h-lshadow     1/6 t-4.09 win17%  ->  1/6 t-2.14 win33%
    # NOTE it is NOT uniformly restrictive — four of those six read BETTER in-era,
    # i.e. pooling was PUNISHING them. That is the point: the era is about which
    # sample describes the book, not about being harsh. Stated because "we
    # tightened everything" would be the easier and false summary.
    "lighter-ticket-taker": (
        "2026-07-17",
        "🎫 Ticket Taker — a REAL-MONEY book. It DOES accrue funding (its "
        "divergence lens exists to collect the credit) and carried the same 8x "
        "defect, modelled inline so a grep for the fixed call site missed it: "
        "'the THIRD accruing book to carry this bug'. Its own note — 'the "
        "accrual still reaches the per-trade ledger and the win/loss call' — and "
        "'it lands exactly where it hurts most: DIVERGENCE is the only lens with "
        "a positive forward grade and the only one that COLLECTS carry, so the "
        "inflated credit flattered the one number that could earn this bot a "
        "go-live'. The LIVE row has ZERO pre-fix closes so this is a no-op for it "
        "today and declared anyway; the shadow twin the brain grades goes 3/6 "
        "t=-0.39 pooled to 2/6 t=-1.45 in-era."),
    "perps-funding-spread": (
        "2026-07-17",
        "⚖️ Counterweight, the book whose own basis-fix note records that its "
        "'entire reported profit was this artifact'. Same 17-Jul accrual fix, 20 "
        "closes opened before it. Declared for correctness, NOT because pooling "
        "flattered it: in-era it reads BETTER (3/6 t=+1.30 win 68% against 3/6 "
        "t=+1.14 win 56%), so pooling was punishing this book."),
    "freqtrade-georgia": (
        "2026-07-17",
        "family book on lighter_family_bot, which carries '[2026-07-17 BASIS FIX "
        "ii]' on its accrual line. 12 closes opened before it; 3/6 t=+0.03 "
        "pooled against 2/6 t=-0.05 in-era. Note the brain already scoped this "
        "book from 13-Jul for a STRATEGY change — a book can have an earlier "
        "hypothesis era than its accounting era, and the later of the two is "
        "what a promotion sample may use."),
    "freqtrade-dad": (
        "2026-07-17",
        "family book, same lighter_family_bot accrual fix, 4 closes opened "
        "before it. In-era it reads BETTER (t=-1.90 against t=-3.59), so this is "
        "a correctness declaration and not a tightening; it fails on 1/6 bars "
        "either way."),
    "crypto-intraday-15m": (
        "2026-07-17",
        "spot port on lighter_family_bot, same accrual fix, 6 closes opened "
        "before it. In-era it reads BETTER — 3/6 t=+0.41 against 2/6 t=-0.66 — "
        "so pooling the pre-fix rows was costing this book a bar."),
    "crypto-breakout-4h": (
        "2026-07-17",
        "spot port on lighter_family_bot, same accrual fix, 6 closes opened "
        "before it. In-era t=-2.14 against a pooled t=-4.09; 1/6 bars either "
        "way, declared so the sample matches the code that produced it."),
}


#: Row suffixes, stripped ONE at a time. See era_base.
_ROW_SUFFIXES = ("-lshadow", "-lighter")


def era_base(bot):
    """The bare book name a ledger row belongs to.

    [2026-07-30 (hg)] EXACT MATCH FIRST, then strip exactly ONE trailing suffix.
    The obvious implementation — `.rsplit("-lshadow",1)[0].rsplit("-lighter",1)[0]`,
    copied from `bot_learn.era_epoch_for` — is WRONG for one book in this fleet,
    and it is the book that holds real money: **💸 Funding Farmer is itself named
    `perps-funding-lighter`**, so its own name ends in the venue suffix.

        perps-funding-lighter          -> 'perps-funding'          (misses itself)
        perps-funding-lighter-lighter  -> 'perps-funding-lighter'  (hits)
        perps-funding-lighter-lshadow  -> 'perps-funding'          (MISSES)

    So a single declaration would have scoped the LIVE row and silently left the
    SHADOW twin pooled — and the twin is the row carrying the 5/6-bars artifact
    this era exists to withdraw. Half-inert, in the same registered-but-inert
    shape this repo keeps hitting, and caught only because the test asserted
    both rows resolve to the same era rather than assuming the strip worked."""
    b = str(bot)
    if b in POLICY_ERA:
        return b
    for suf in _ROW_SUFFIXES:
        if b.endswith(suf):
            return b[:-len(suf)]
    return b


def era_epoch_for(bot):
    """(epoch, iso, why) for a ledger bot id's policy era, or (None, None, None).

    Table keyed BARE, ledger keyed SUFFIXED — the hazard the brain shipped for
    nine days. See `era_base` for why the strip is one-at-a-time."""
    ent = POLICY_ERA.get(era_base(bot))
    if not ent:
        return None, None, None
    iso, why = ent
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp(), iso, why


def in_era(open_ts, era_epoch, parse):
    """Is a trade OPENED inside the era? Keyed on the OPEN, because the policy
    that produced a trade is fixed when the trade is taken. A position that
    straddles the boundary is a HYBRID — a carry open across the accrual fix
    accrued in the old basis for part of its life and the new one for the rest —
    so it belongs cleanly to neither era, and excluding it is the conservative
    reading of a sample that is supposed to describe the book as it now runs.

    FAIL-CLOSED on an unreadable open stamp when an era is declared: counting a
    trade whose era cannot be determined is exactly the credit this block
    exists to withdraw. With no era declared everything is in (all-time)."""
    if era_epoch is None:
        return True
    if not open_ts:
        return False
    try:
        return parse(open_ts) >= era_epoch
    except Exception:      # noqa: BLE001
        return False


def stats(rows, book_usd=None):
    """Grade one book from its closed-trade rows.

    rows: [(pnl_pct, pnl_abs, closed_at_datetime)] oldest first. Pure — the DB
    read is the caller's job so this is selftestable offline."""
    book_usd = BOOK_USD if book_usd is None else book_usd
    pct = [r[0] for r in rows if isinstance(r[0], (int, float))]
    n = len(pct)
    out = {"n": n}
    if n < 2:
        out["why"] = "too few closes to grade"
        return out
    days = (rows[-1][2] - rows[0][2]).total_seconds() / 86400.0
    mean = sum(pct) / n
    var = sum((x - mean) ** 2 for x in pct) / n
    sd = math.sqrt(var) or 1e-12
    t = mean / (sd / math.sqrt(n))
    mid = n // 2
    h1 = sum(r[1] or 0 for r in rows[:mid])
    h2 = sum(r[1] or 0 for r in rows[mid:])
    eq = peak = dd = 0.0
    for r in rows:
        eq += r[1] or 0
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    wins = sum(1 for x in pct if x > 0)
    out.update(days=days, mean_pct=mean, t=t, h1=h1, h2=h2,
               win_rate=wins / n, max_dd_usd=dd,
               max_dd_frac=abs(dd) / book_usd if book_usd else None,
               realised_usd=sum(r[1] or 0 for r in rows))
    return out


#: The six bars, in the order the operator reads them. Names are the PUBLISHED
#: contract (`golive-readiness.books.<bot>.bars`) — the dashboard renders these
#: keys, so a rename here is a breaking change and `test_golive_readiness.py`
#: pins them.
BAR_NAMES = ("window", "closes", "mean", "t", "halves", "maxdd")


def bar_map(s):
    """{bar_name: passed} for one book — the same six conditions `grade()`
    checks, in a form a CONSUMER can render without string-parsing `fails`.

    Published rather than re-derived: the dashboard used to have no way to show
    "5 of 6 bars, missing the window" except by matching prose, and prose is
    exactly what drifts. `_selftest` asserts `all(bar_map(s).values()) is
    grade(s)[0]` over every fixture, so the two cannot diverge silently. An
    unmeasurable bar (maxDD with no book size) counts as NOT passed — the
    fail-closed direction for a gate that governs real money."""
    if s.get("n", 0) < 2:
        return {k: False for k in BAR_NAMES}
    dd = s.get("max_dd_frac")
    return {
        "window": s["days"] >= GOLIVE_MIN_DAYS,
        "closes": s["n"] >= GOLIVE_MIN_CLOSES,
        "mean": s["mean_pct"] > 0,
        "t": s["t"] >= GOLIVE_MIN_T,
        "halves": s["h1"] > 0 and s["h2"] > 0,
        "maxdd": dd is not None and dd < GOLIVE_MAX_DD,
    }


# ---------------------------------------------------------------------------
# LEDGER INTEGRITY — is this book's ledger ONE book's record? [(hf)]
# ---------------------------------------------------------------------------
# These primitives live HERE, in the module that ships inside the freqtrade
# image and does the grading, rather than in `audit_ledger_integrity.py` which
# imports them. One owner, and the owner is the consumer that has to fail
# closed: a grader that cannot tell a pooled ledger from a clean one will keep
# reporting a `t` computed over two books' trades. (Importing the other
# direction would put a non-shipped module inside the image's import graph — the
# born-dark class the (17-Jul) guard exists for.)

#: Below this, a same-pair "overlap" is a close-and-reopen inside ONE bot loop:
#: the position is deleted and the entry block runs later in the same iteration,
#: so open2 == close1 to the millisecond. Measured on the carry book those sit
#: at 0.3s while the real overlaps are 2-9 HOURS.
LEDGER_MIN_OVERLAP_S = float(os.environ.get("LEDGER_MIN_OVERLAP_S", "60"))


def parse_stamp(s):
    """Tolerant ISO parse. The listing sniper writes '2026-07-13 15:05:04 UTC',
    which `fromisoformat` rejects — its 337 rows were unreadable for two days
    over exactly this (15-Jul audit fix)."""
    t = str(s).strip().replace("Z", "+00:00")
    if t.endswith(" UTC"):
        t = t[:-4] + "+00:00"
    from datetime import datetime
    return datetime.fromisoformat(t)


def same_pair_overlaps(eps, min_gap_s=None):
    """[(pair, hours_inside)] where one hold opens INSIDE another on the same
    pair, deepest first.

    Structural proof of a SECOND WRITER for any book whose position map is keyed
    by symbol — which every Lighter book here is (`if c not in positions`). It is
    the detector that `(gn)`'s duplicate-`trade_id` scan could not be: two
    processes open at different moments, so their ids never collide."""
    min_gap_s = LEDGER_MIN_OVERLAP_S if min_gap_s is None else min_gap_s
    by = {}
    for pair, o, c in eps:
        by.setdefault(pair, []).append((o, c))
    hits = []
    for pair, v in by.items():
        v.sort()
        for i in range(len(v) - 1):
            gap = (v[i][1] - v[i + 1][0]).total_seconds()
            if gap > min_gap_s:
                hits.append((pair, gap / 3600.0))
    return sorted(hits, key=lambda x: -x[1])


def peak_concurrency(eps):
    """Most positions open at once, from the intervals alone. The SECOND
    detector only — caps move (carry's went 8 -> 12 on 30-Jul) and the ledger
    does not record which cap was in force, so an over-cap reading corroborates
    and never accuses on its own."""
    ev = sorted([(o, 1) for _p, o, _c in eps] + [(c, -1) for _p, _o, c in eps])
    cur = mx = 0
    for _t, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


def book_payload(s):
    """The published per-book numbers for one sample, tolerating n<2.

    Split out at (hc) because there are now TWO samples per book (era-scoped
    and all-time) and an era-scoped sample can be legitimately too thin to
    grade — the old inline dict indexed `s["days"]` and would have raised a
    KeyError on exactly the book the era block was written for."""
    bars = bar_map(s)
    out = {"n": s.get("n", 0), "bars": bars, "bar_names": list(BAR_NAMES),
           "bars_passed": sum(bars.values())}
    if s.get("n", 0) < 2:
        out.update(days=None, mean_pct=None, t=None, win_pct=None,
                   max_dd_pct=None, h1=None, h2=None,
                   why=s.get("why") or "too few closes to grade")
        return out
    dd = s.get("max_dd_frac")
    out.update(days=round(s["days"], 1),
               mean_pct=round(100 * s["mean_pct"], 3),
               t=round(s["t"], 2), win_pct=round(100 * s["win_rate"], 1),
               max_dd_pct=(round(100 * dd, 1) if dd is not None else None),
               h1=round(s["h1"], 2), h2=round(s["h2"], 2))
    return out


def grade(s, legacy=False):
    """(passes, [failed_bar, ...]) for one book's stats dict.

    legacy=True applies CLAUDE.md's ORIGINAL rule (30d + win>55% + maxDD<15%)
    so the two can be compared side by side and the divergence is visible
    rather than asserted. Pure — selftested."""
    if s.get("n", 0) < 2:
        return False, ["ungradeable"]
    fails = []
    if s["days"] < GOLIVE_MIN_DAYS:
        fails.append(f"window {s['days']:.1f}d < {GOLIVE_MIN_DAYS:g}d")
    # [2026-07-30] An UNMEASURABLE drawdown now FAILS the bar rather than
    # passing it. It was `is not None and >=`, i.e. a book whose drawdown could
    # not be computed (no book size) sailed through the one bar the operator
    # wrote himself. Fail-closed is the only defensible direction for a gate on
    # real money, and it is what lets `bar_map` be exactly equivalent to this
    # function (selftest-bound) instead of quietly kinder in one corner.
    if s["max_dd_frac"] is None:
        fails.append("maxDD unmeasurable")
    elif s["max_dd_frac"] >= GOLIVE_MAX_DD:
        fails.append(f"maxDD {100*s['max_dd_frac']:.1f}% >= {100*GOLIVE_MAX_DD:.0f}%")
    if legacy:
        if s["win_rate"] <= GOLIVE_LEGACY_WIN:
            fails.append(f"win {100*s['win_rate']:.1f}% <= {100*GOLIVE_LEGACY_WIN:.0f}%")
        return not fails, fails
    if s["n"] < GOLIVE_MIN_CLOSES:
        fails.append(f"n {s['n']} < {GOLIVE_MIN_CLOSES}")
    if s["mean_pct"] <= 0:
        fails.append(f"mean {100*s['mean_pct']:+.3f}% <= 0")
    if s["t"] < GOLIVE_MIN_T:
        fails.append(f"t {s['t']:.2f} < {GOLIVE_MIN_T:g}")
    if not (s["h1"] > 0 and s["h2"] > 0):
        fails.append(f"halves {s['h1']:+.2f}/{s['h2']:+.2f} not both positive")
    return not fails, fails


def _selftest():
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def mk(pcts, span_days=40.0):
        step = timedelta(days=span_days / max(1, len(pcts) - 1))
        return [(p, p * 10.0, t0 + i * step) for i, p in enumerate(pcts)]

    # a CLEAN book: 40 steady winners over 40d
    good = stats(mk([0.01] * 40))
    assert good["n"] == 40 and good["days"] > 30 and good["t"] > 2
    assert grade(good)[0] is True, grade(good)

    # THE CARRY SHAPE — the whole reason this file exists. Low win rate,
    # positive expectancy: a few big wins carrying many small losses.
    carry = stats(mk(([0.20] * 14 + [-0.03] * 26) * 1))
    assert carry["win_rate"] < 0.55, carry["win_rate"]
    assert carry["mean_pct"] > 0, carry
    ok_new, f_new = grade(carry)
    ok_old, f_old = grade(carry, legacy=True)
    assert ok_old is False and any("win" in x for x in f_old), f_old
    assert not any("win" in x for x in f_new), "win rate is NOT a bar any more"
    # ...and the new bar still refuses it if the EVIDENCE is not there
    assert ok_new is False or carry["t"] >= GOLIVE_MIN_T

    # THE INVERSE, which is what the new bar buys: a high win rate that LOSES
    # money must fail the new gate and PASS the old one on win rate alone.
    tails = stats(mk([0.01] * 34 + [-0.30] * 6))
    assert tails["win_rate"] > 0.55 and tails["mean_pct"] < 0, tails
    assert grade(tails, legacy=True)[1] == [] or all(
        "win" not in x for x in grade(tails, legacy=True)[1]), \
        "old rule does not object to a money-losing book on win rate"
    ok_t, f_t = grade(tails)
    assert ok_t is False and any("mean" in x for x in f_t), f_t

    # EACH BAR MUST BE THE SOLE REASON IN SOME CASE, or it is untested
    # decoration — both of these were added after mutations proved the bar
    # could be deleted with the suite still green.
    #  (a) SIGNIFICANCE alone: positive mean, both halves positive, enough
    #      closes and days — but far too noisy to believe (t ~ 0.3).
    noisy = stats(mk([0.05, -0.045] * 20))
    assert noisy["mean_pct"] > 0 and noisy["h1"] > 0 and noisy["h2"] > 0
    assert noisy["n"] >= GOLIVE_MIN_CLOSES and noisy["days"] >= GOLIVE_MIN_DAYS
    ok_n, f_n = grade(noisy)
    assert ok_n is False and f_n == [f"t {noisy['t']:.2f} < {GOLIVE_MIN_T:g}"], f_n
    #  (b) BOTH-HALVES alone: strongly positive mean AND a big t, but the
    #      whole result is the first half — the classic one-window win.
    lopsided = stats(mk([0.05] * 20 + [-0.01] * 20))
    assert lopsided["mean_pct"] > 0 and lopsided["t"] >= GOLIVE_MIN_T
    assert lopsided["h1"] > 0 > lopsided["h2"], lopsided
    ok_l, f_l = grade(lopsided)
    assert ok_l is False and len(f_l) == 1 and "halves" in f_l[0], f_l

    #  (c) THE CLOSES FLOOR alone: flawless on every other bar over a full
    #      window, but only 10 fills. Evidence is denominated in FILLS, never
    #      in days ([[incubator-evidence-denominated-in-fills]]) — a long
    #      quiet window is not a substitute for trades.
    thin = stats(mk([0.02] * 10))
    assert thin["days"] >= GOLIVE_MIN_DAYS and thin["mean_pct"] > 0
    assert thin["h1"] > 0 and thin["h2"] > 0 and thin["t"] >= GOLIVE_MIN_T
    ok_th, f_th = grade(thin)
    assert ok_th is False and f_th == [f"n 10 < {GOLIVE_MIN_CLOSES}"], f_th

    # window and drawdown bars still bite (the operator's two, unchanged)
    short = stats(mk([0.01] * 40, span_days=5.0))
    assert any("window" in x for x in grade(short)[1])
    deep = stats(mk([0.5] * 5 + [-4.0] * 10 + [0.5] * 25))
    assert deep["max_dd_frac"] > 0, deep
    # ungradeable input claims nothing, never raises
    assert grade(stats([]))[0] is False
    assert stats([])["n"] == 0 and "why" in stats([])

    # [2026-07-30] THE PUBLISHED BAR MAP IS BOUND TO THE GRADE. `bar_map` is
    # what the dashboard renders; if it could drift from `grade`, the operator
    # would read six green chips on a book the gate rejects. Asserted over
    # every fixture above INCLUDING the unmeasurable-drawdown corner, which is
    # the one place the two used to disagree.
    nodd = stats(mk([0.01] * 40), book_usd=0)
    assert nodd["max_dd_frac"] is None, nodd
    for name, s in [("good", good), ("carry", carry), ("tails", tails),
                    ("noisy", noisy), ("lopsided", lopsided), ("thin", thin),
                    ("short", short), ("deep", deep), ("empty", stats([])),
                    ("nodd", nodd)]:
        bm = bar_map(s)
        assert set(bm) == set(BAR_NAMES), bm
        assert all(bm.values()) == grade(s)[0], (name, bm, grade(s))
        if s.get("n", 0) >= 2:
            # every failed bar is exactly one dark chip, and vice versa
            assert sum(bm.values()) == len(BAR_NAMES) - len(grade(s)[1]), \
                (name, bm, grade(s)[1])
        else:
            assert sum(bm.values()) == 0, (name, bm)   # claims nothing at all
    assert bar_map(nodd)["maxdd"] is False, "an unmeasured drawdown is not a pass"

    # ---- POLICY ERAS [2026-07-30 (hc)] ---------------------------------
    # The suffix strip is the whole wiring. Keyed bare, looked up suffixed.
    for suffixed in ("perps-funding-carry-lshadow", "perps-funding-carry"):
        ep, iso, why = era_epoch_for(suffixed)
        assert ep is not None and iso == "2026-07-17", (suffixed, ep, iso)
        assert why and len(why) > 60, f"{suffixed}: era needs a stated reason"
    # An undeclared book grades ALL-TIME — the pre-(hc) behaviour, unchanged.
    # Both of these are books whose publisher does NOT accrue funding, so the
    # 17-Jul basis fix cannot have touched their P&L. (This line named the Ticket
    # Taker until (hg): it DOES accrue — its divergence lens exists to collect
    # the credit — and it is now declared.)
    assert era_epoch_for("lighter-dislocation-lshadow") == (None, None, None)
    assert era_epoch_for("lighter-perp-sniper-lshadow") == (None, None, None)
    # ...and the Farmer's OWN NAME ends in a row suffix, so every one of its
    # three spellings must resolve to the same era. This is the (hg) bug.
    _fe = era_epoch_for("perps-funding-lighter")
    assert _fe[0] is not None, "the bare key does not resolve to itself"
    for _row in ("perps-funding-lighter-lighter", "perps-funding-lighter-lshadow"):
        assert era_epoch_for(_row) == _fe, (_row, era_epoch_for(_row), _fe)

    era_ep, _, _ = era_epoch_for("perps-funding-carry-lshadow")
    def _p(x):                      # stand-in for experiment_judge.parse_ts
        from datetime import datetime, timezone
        d = datetime.fromisoformat(str(x))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    assert in_era("2026-07-20T00:00", era_ep, _p) is True
    assert in_era("2026-07-16T23:59", era_ep, _p) is False
    # FAIL-CLOSED: unreadable or missing open stamps are OUT when an era is
    # declared, and IN when none is (no era = no claim about which trades count).
    for bad in (None, "", "not-a-date"):
        assert in_era(bad, era_ep, _p) is False, bad
        assert in_era(bad, None, _p) is True, bad
    # A too-thin era must be publishable, not a crash. This is the failure the
    # inline payload dict would have hit on the one book the era exists for.
    thin_era = stats(mk([0.01]))
    bp = book_payload(thin_era)
    assert bp["n"] == 1 and bp["days"] is None and bp["bars_passed"] == 0, bp
    assert set(bp["bars"]) == set(BAR_NAMES)
    bp2 = book_payload(good)
    assert bp2["bars_passed"] == 6 and bp2["t"] is not None, bp2

    print("golive_readiness selftest OK (clean pass, the carry shape, the "
          "high-win-rate loser, window/DD bars, ungradeable input, policy eras)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="write the verdicts to bot_state['golive-readiness']")
    ap.add_argument("--min-closes", type=int, default=10,
                    help="ignore books below this many closes")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    import bot_pnl_store as store          # noqa: E402
    # RETIRED rows are HISTORY, not candidates — grading them would offer a
    # dead bot for promotion. Single source: cleanup_legacy_bots.LEGACY_BOTS
    # (the same list that prunes them), fail-OPEN if it cannot be imported.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS
        retired = set(LEGACY_BOTS)
    except Exception:      # noqa: BLE001
        retired = set()
    rows = store.fetch_paper_trades(limit=20000) or []
    books = {}
    for r in rows:
        bot = str(r.get("bot"))
        if bot in retired:
            continue
        books.setdefault(bot, []).append(r)

    def _key(r):
        return r.get("close_ts") or r.get("closed_at") or ""

    print(f"GO-LIVE READINESS — bar: >={GOLIVE_MIN_DAYS:g}d, >={GOLIVE_MIN_CLOSES} "
          f"closes, mean>0, t>={GOLIVE_MIN_T:g}, both halves +, maxDD<"
          f"{100*GOLIVE_MAX_DD:.0f}%")
    print(f"{'book':34s} {'n':>4s} {'days':>6s} {'mean%':>8s} {'t':>6s} "
          f"{'win%':>6s} {'maxDD%':>7s}  verdict")
    print("-" * 104)
    ready, payload_books = [], {}
    for bot in sorted(books):
        rs = sorted(books[bot], key=_key)
        era_epoch, era_iso, era_why = era_epoch_for(bot)
        parsed, parsed_all, integ_eps = [], [], []
        for r in rs:
            # [(hf)] intervals for the integrity check, over the WHOLE ledger:
            # a second writer is a property of the book's record, not of the era
            # being graded, and narrowing to the era could hide it.
            if r.get("open_ts") and r.get("close_ts"):
                try:
                    integ_eps.append((str(r.get("pair")),
                                      parse_stamp(r["open_ts"]),
                                      parse_stamp(r["close_ts"])))
                except (TypeError, ValueError):
                    pass
            try:
                from experiment_judge import parse_ts
                from datetime import datetime, timezone
                ts = datetime.fromtimestamp(parse_ts(_key(r)), tz=timezone.utc)
            except Exception:      # noqa: BLE001
                continue
            row = (r.get("profit_ratio"), r.get("profit_abs"), ts)
            parsed_all.append(row)
            if in_era(r.get("open_ts"), era_epoch, parse_ts):
                parsed.append(row)
        # [2026-07-30 (hc)] The ERA-SCOPED sample is authoritative; the all-time
        # one is published beside it so nothing is hidden and the difference is
        # readable rather than asserted. `min_closes` is applied to the ALL-TIME
        # count on purpose: a book whose era has too few closes must still
        # appear, showing its era bars dark, or narrowing the window would
        # silently REMOVE the frontrunner from the report instead of demoting it.
        s, s_all = stats(parsed), stats(parsed_all)
        if s_all.get("n", 0) < a.min_closes:
            continue
        ok, fails = grade(s)
        # [2026-07-30 (hf)] LEDGER INTEGRITY IS A PRECONDITION, not a bar. It
        # does not join BAR_NAMES — that tuple is the published contract the
        # dashboard renders and a seventh entry breaks every consumer — but a
        # book whose ledger cannot have come from one process is NOT GRADEABLE,
        # so it can never be READY. Fail-closed, and the reason is stated in
        # `fails` where a human reads it.
        overlaps = same_pair_overlaps(integ_eps)
        if overlaps:
            # FIRST in the list, not appended: the printed verdict shows
            # `fails[:2]` and this is the one failure that invalidates the other
            # five rather than adding to them. Buried at position three it was
            # invisible in exactly the run that needed it.
            fails = [f"LEDGER: {len(overlaps)} same-pair overlap(s), deepest "
                     f"{overlaps[0][1]:.2f}h on {overlaps[0][0]} — TWO WRITERS, "
                     f"n is not one book's trades"] + fails
            ok = False
        ok_old, fails_old = grade(s, legacy=True)
        if overlaps:
            ok_old = False
        verdict = "READY" if ok else "; ".join(fails[:2])
        flag = ""
        if ok and not ok_old:
            flag = "   <- passes the NEW bar, REJECTED by the win-rate rule"
        if ok_old and not ok:
            flag = "   <- old rule would have ADMITTED it"
        dd_pct = (round(100 * s["max_dd_frac"], 1)
                  if s.get("max_dd_frac") is not None else None)
        bars = bar_map(s)
        if era_iso:
            # Say so on EVERY line for an era-scoped book, whatever the verdict.
            # An era that only announces itself when it changes the outcome is a
            # footnote; this one has to be readable as the sample's definition.
            flag += (f"   [era {era_iso}: {s.get('n', 0)} of {s_all['n']} "
                     f"closes count]")
        if s.get("n", 0) < 2:
            print(f"{bot:34s} {s.get('n', 0):>4d} {'-':>6s} {'-':>8s} {'-':>6s} "
                  f"{'-':>6s} {'-':>7s}  ungradeable in era{flag}")
        else:
            print(f"{bot:34s} {s['n']:>4d} {s['days']:>6.1f} "
                  f"{100*s['mean_pct']:>7.3f}% {s['t']:>6.2f} "
                  f"{100*s['win_rate']:>5.1f}% "
                  f"{('n/a' if dd_pct is None else f'{dd_pct:.1f}%'):>7s}  "
                  f"{verdict}{flag}")
        if ok:
            ready.append(bot)
        # [2026-07-30] collect for the PUBLISH below — see the note there.
        # `bars` is the machine-readable per-bar map the dashboard renders; the
        # prose `fails` stays for humans. Publishing both means no consumer has
        # to string-match a message to know WHICH bar is dark.
        payload_books[bot] = {
            **book_payload(s), "fails": fails,
            "ready": bool(ok), "legacy_ready": bool(ok_old),
            # [2026-07-30 (hc)] The era, and the all-time sample it replaced.
            # Both published: a consumer that wants the authoritative verdict
            # reads the top level, and one that wants to see what the era
            # withdrew reads `alltime`. `era` is None for every book without a
            # declared era, which is all of them but one — so this is additive
            # and no other book's payload changes shape in a meaningful way.
            "era": ({"since": era_iso, "why": era_why,
                     "closes_in_era": s.get("n", 0),
                     "closes_all_time": s_all.get("n", 0)} if era_iso else None),
            "alltime": book_payload(s_all),
            # [(hf)] Published so a consumer can render the warning without
            # string-matching `fails`, exactly as `bars` did for the bar map.
            "integrity": {
                "two_writers": bool(overlaps),
                "same_pair_overlaps": len(overlaps),
                "deepest_overlap_h": (round(overlaps[0][1], 2) if overlaps
                                      else 0.0),
                "deepest_overlap_pair": (overlaps[0][0] if overlaps else None),
                "peak_concurrent": peak_concurrency(integ_eps)}}
    print()
    print(f"READY: {ready or 'none'}")

    # [2026-07-30 THIS GRADER BECOMES AN ORGAN — operator: "make sure the PNL
    # dashboard reflects all work done".] Until now it published NOTHING and was
    # scheduled NOWHERE: the tool that decides whether a book has earned real
    # money ran only when a human remembered, and its verdicts reached no
    # organ, no dashboard and no review. That is the fleet's own "a rule nobody
    # runs is not a control" class — the same shape as the 38 selftests before
    # 18-Jul and `--selftest-live` before (ej). Publishing makes the gate
    # VISIBLE between reviews; it changes no decision and promotes nothing.
    # Go-live remains an explicit operator act.
    if a.publish:
        try:
            import bot_pnl_store as _store
            from datetime import datetime as _dt, timezone as _tz
            payload = {
                "updated": _dt.now(_tz.utc).isoformat(timespec="seconds"),
                "ttl_sec": TTL_SEC,
                "bar": {"min_days": GOLIVE_MIN_DAYS,
                        "min_closes": GOLIVE_MIN_CLOSES,
                        "min_t": GOLIVE_MIN_T, "max_dd": GOLIVE_MAX_DD},
                "bar_names": list(BAR_NAMES),
                "books": payload_books,
                "ready": sorted(ready)}
            ok_pub = _store.save_state(KEY, payload)
            # HISTORY too, because the question the baseline document asks is a
            # TRAJECTORY one — "is t moving toward 2.0 and n above 41?" — and a
            # single current snapshot cannot answer it. 4 writes/day against a
            # 60-day retention is ~240 rows; negligible against the ~400/day
            # the organs already write.
            _store.save_history(KEY, payload)
            print(f"published {KEY}: {len(payload_books)} books, "
                  f"{len(ready)} ready ({'ok' if ok_pub else 'WRITE FAILED'})")
        except Exception as e:      # noqa: BLE001 — a publish must never fail the grade
            print(f"publish skipped: {type(e).__name__}: {e}")
    print("Go-live remains an explicit operator act — this grades, it does not "
          "promote. Lighter's tape is ONE regime; a DIRECTIONAL book passing "
          "here has passed in that regime only.")


if __name__ == "__main__":
    main()
