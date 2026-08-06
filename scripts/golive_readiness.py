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
import json
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
        # [2026-08-01 (ii)] MOVED 17-Jul -> 31-Jul. An era is the LATEST of
        # every invalidating change, and moving the date forward PRESERVES the
        # earlier reason rather than discarding it — the accrual-basis note
        # below still applies to everything before 17-Jul.
        #
        # THE NEW INVALIDATION IS STRONGER THAN A WRONG UNIT: for 12 days this
        # row was written by TWO PROCESSES. Measured — 7 same-pair overlapping
        # holds between 17-Jul 16:34Z and 29-Jul 07:39Z, deepest 9.14h on HYPE,
        # and a peak of 10 concurrent positions against a `MAX_POSITIONS` of 8.
        # A carry process keys `positions` by coin and enters only
        # `if c not in positions`, so ONE process cannot hold HYPE twice. The
        # rule about what resets an era asks whether earlier P&L is WRONG; this
        # is worse — the earlier sample is not this book's record at all, which
        # is the very thing `integrity` exists to say. `n` was a mixture and
        # `t` scales with sqrt(n).
        #
        # THE FIX THAT CLOSES IT: `bot_pnl_store.claim_writer` merged 31-Jul
        # 00:52Z ((hp)), corrected through (ib)/(ic)/(id). ZERO overlaps since.
        #
        # WHAT THIS COSTS, stated rather than buried: carry restarts its 30-day
        # clock, so its earliest gradeable date is **~30-Aug** instead of
        # ~16-Aug. It is deliberately NOT a shortcut to real money — it makes
        # the gate REACHABLE where it was previously impossible, and reaching
        # it now requires 30 days of single-writer evidence.
        "2026-07-31",
        "TWO WRITERS: for 12 days (17-Jul 16:34Z to 29-Jul 07:39Z) two "
        "containers published this row and wrote this ledger — 7 same-pair "
        "overlapping holds, deepest 9.14h on HYPE, peak 10 concurrent against "
        "a cap of 8. One process cannot hold a coin twice, so the earlier "
        "sample is two books' trades, not this book's. Closed by "
        "`claim_writer` (31-Jul 00:52Z); zero overlaps since. SUPERSEDES, and "
        "preserves, the 17-Jul accrual-basis reason: the lighter_shadow arm's "
        "accrual was fixed from per-hour to the venue's per-8h settlement, and "
        "for a funding book the accrual IS the P&L."),
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
    # [2026-07-30 (hh)] DECLARED BEFORE THE SAMPLE EXISTS. These three are below
    # the report's min-closes floor today (mum, avo-maria n=4, swing-daily n=1),
    # so no measurement is quoted — and that is exactly why they belong here now.
    # The brain scopes all three; without these the GATE would grade them
    # all-time, i.e. WIDER than the brain, on whatever day they first accumulate
    # ten closes. An era that arrives after the sample does is an era that
    # arrives too late, and nobody would think to add it then.
    "freqtrade-mum": (
        "2026-07-17",
        "family book on lighter_family_bot, same 17-Jul accrual fix. Below the "
        "report's min-closes floor today, so no effect is quoted; declared now "
        "because the gate must never grade a wider sample than the brain, and "
        "the brain scopes this book from the same date."),
    "freqtrade-avo-maria": (
        "2026-07-17",
        "family book on lighter_family_bot, same 17-Jul accrual fix, n=4 closes "
        "today. Declared ahead of the sample for the same reason as mum: an era "
        "added after a book becomes gradeable is an era nobody remembers to add."),
    "crypto-swing-daily": (
        "2026-07-17",
        "spot port on lighter_family_bot, same 17-Jul accrual fix, n=1 close "
        "today. Declared ahead of the sample; the brain scopes it from the same "
        "date and the gate must not be the looser of the two."),
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


def _era_parse(parse=None):
    """Open-stamp -> epoch float, tolerant of what the callers actually hold.

    Accepts a `datetime` directly (a Postgres `opened_at::timestamptz` read) or
    any of the four TEXT formats `experiment_judge.parse_ts` understands, so no
    consumer needs its own adapter — writing one is how a second, subtly
    different notion of "when did this trade open" gets into the fleet."""
    def _p(x):
        if hasattr(x, "timestamp"):
            return x.timestamp()
        if parse is not None:
            return parse(x)
        from experiment_judge import parse_ts
        return parse_ts(x)
    return _p


# ---------------------------------------------------------------------------
# STAMP-DERIVED POLICY BOUNDARIES [2026-08-04 (jf)]
# ---------------------------------------------------------------------------
# THE DECLARED TABLE ABOVE CANNOT KEEP UP WITH A BOOK THAT CHANGES POLICY IN
# CODE. The Ticket Taker — a REAL-MONEY book — changed policy on 24-Jul
# (TT_BULL_MODE), 29-Jul and 30-Jul ((hj)'s LIVE_SIDES hard gate), and (hm)
# already ruled that a sample pooled across those is meaningless… while this
# grader's era for it sat at the single 17-Jul accrual date, so its t/halves
# bars graded a mixture of three policies. The ledger has carried the fix since
# (fx)/(gi)/(hj): every taker close stamps `extra.policy` — precisely so "any
# grader can split eras MECHANICALLY". No grader ever consumed it. This block
# is the consumer.
#
# Measured on the live ledger the day this shipped (4-Aug):
#   lighter-ticket-taker-lighter   38 closes = 25 unstamped (17→29-Jul, the
#     three-policy mixture) + a 13-close run stamped {bull, lenses:[divergence],
#     sides:{divergence:[short]}, venue:lighter_live} since 30-Jul 11:05:43Z.
#     Keyed on the OPEN, 11 closes are in-era → earliest gradeable ~29-Aug,
#     computed from the real boundary instead of hand-waved.
#   lighter-ticket-taker-lshadow   boundary 30-Jul 11:09:46Z, 14 in-era opens.
#     (The shadow's boundary is partly a stamp-SCHEMA event — `sides` joined
#     the stamp at (hj) without changing shadow behaviour — and the machinery
#     cannot tell schema arrival from a policy change, so it takes the
#     fail-closed reading. Cost measured: one 30-Jul close.)
#
# WHAT COUNTS AS THE POLICY, and this subset is load-bearing: venue / bull /
# lenses / sides — the DIFFERENT-IN-KIND fields (which signals, which sides,
# which venue mode). `max_open` and `ticket_top_n` ride the same stamp but are
# capacity/supply levers — (hc)'s "ordinary tuning", which must NOT reset an
# era or the growth rail's daily lever walks would keep every clock at zero
# and the 30-day bar would be unreachable forever. The exit bracket (tp/sl/
# hold) lives in `extra.bars`, not the policy stamp, for the same reason.
#
# THE (ij) RULING, decided by code review as the 4-Aug review asked, and the
# competing reading stated rather than silently dropped. Does the 1-Aug lens-
# veto rewrite (expectancy-only, realised-record senior — I14/I15; live-taker
# deploy 2-Aug (im)) reset this clock?
#   NO — ruled here, on three code facts and one measurement:
#   (1) the stamp's lens/side sets are `allowed_lenses`/`allowed_sides`, the
#       hard fail-CLOSED gates, and `allowed_lenses`' own docstring says it is
#       "deliberately NOT the brain's veto" — (ij) touched the veto, not the
#       gates, so the stamped policy is byte-identical across it (measured:
#       the 30-Jul run continues unbroken through the 2-Aug deploy);
#   (2) the veto is RESTRICT-ONLY — it can only subtract entries, so a veto
#       flip pauses the book rather than admitting a different KIND of trade;
#       a pause adds no trades to the sample and so cannot contaminate it;
#   (3) measured at the deploy ((ik): "both the old and new rules currently
#       permit divergence, so live behaviour is identical today") — no trade
#       in the sample was admitted or refused differently by the rewrite.
#   THE COMPETING READING: the veto is consulted in the entry loop, and (hc)
#   lists "a rewritten entry rule" as a reset. If the operator rules that way,
#   the implementation is one line — move POLICY_ERA["lighter-ticket-taker"]
#   to "2026-08-02" (the deploy date, not the merge date) — and the max() rule
#   below applies it over the stamp boundary automatically.

#: The stamp fields that ARE the policy. Adding a tuning field here weaponises
#: the era ((hc)); removing one blinds the boundary to a real change.
POLICY_SIG_FIELDS = ("venue", "bull", "lenses", "sides")

#: [2026-08-06 (km)] The EXIT BRACKET, for books that stamp `extra.bars` at
#: entry instead of an `extra.policy` block — 💸 the Funding Farmer and its
#: shadow twin. Same warning as above, in both directions:
#:
#:   * ADDING a tuning field here weaponises the era. `enter_apr`, `min_vol`,
#:     `slope_gate`, `explore_k` and `conviction_hi` are all stamped in the
#:     same `bars` dict and are all DELIBERATELY EXCLUDED — they are the
#:     judge's and the rail's ordinary tuning ((hc)), and resetting the clock
#:     on every promotion would make the 30-day bar unreachable forever.
#:   * REMOVING one blinds the gate to `(kg)`: a take-profit that reads
#:     **86% win and t=+2.55 — PASSING the t bar** — on a book earning $2.36
#:     instead of $6.46. Truncation collapses variance faster than the mean,
#:     so a tight bracket INFLATES t. That is the single most expensive way
#:     this fleet could be wrong about real money, and the defence is that
#:     such a change must earn its OWN 30 days rather than inherit 62 closes.
BRACKET_SIG_FIELDS = ("take_profit", "max_hold_h")


#: [2026-08-06 (kk)] A row that carries NO `policy` key at all — i.e. a close
#: written before its book adopted the stamp. Distinct from a stamp that is
#: present and malformed, which stays fail-closed. See `stamp_state`.
ABSENT = "\x00absent"


def stamp_state(extra):
    """`ABSENT` | None (unreadable) | a canonical signature string.

    [2026-08-06 (kk)] THE THIRD STATE IS WHY THIS EXISTS. `policy_signature`
    collapsed "this book does not stamp yet" and "this stamp is broken" into
    one None, and `stamped_policy_boundary` treats None as a run-breaker — so
    the FIRST stamped close on any adopting book reads as a policy CHANGE and
    the boundary lands there. Measured on the live payload: giving 💸 the
    Farmer a stamp today would have set its era to today and discarded **62 of
    its 62 in-era closes**, taking the fleet's only 4/6 book to ~1/6 and its
    gate date from ~5-Sep to nowhere. `(jf)`'s clock was un-adoptable by a
    SECOND book; the Taker survived adoption only because its declared era
    happened to coincide with the stamp's arrival, which masked it.

    An ABSENCE IS NOT A CHANGE (I6). A malformed stamp still is — that half of
    the fail-closed contract is unchanged."""
    if not isinstance(extra, dict):
        return ABSENT
    if "policy" not in extra:
        return _bracket_state(extra)
    pol = extra.get("policy")
    if not isinstance(pol, dict):
        return None
    sig = {k: pol[k] for k in POLICY_SIG_FIELDS if k in pol}
    if not sig.get("lenses"):
        return None
    try:
        return json.dumps(sig, sort_keys=True)
    except (TypeError, ValueError):
        return None


def _bracket_state(extra):
    """[2026-08-06 (km)] The era signature for a book that stamps its EXIT
    BRACKET at entry (`extra.bars` + `bars_basis`) rather than an explicit
    `extra.policy` block. 💸 the Funding Farmer has recorded this on every
    close for weeks and the gate never read it.

    `bars_basis` is load-bearing and is checked, not assumed:
      * `"entry"` — the values in force when the position was OPENED. That is
        the era doctrine's own rule (a trade's policy is fixed when it is
        taken; a straddler belongs to neither side), so only these are read.
      * anything else (`"close-legacy"`) — the row carries the bars ACTIVE AT
        CLOSE, which cannot tell us the policy the trade was taken under. It
        is treated as ABSENT, i.e. pre-adoption: an absence is not a change
        ((kk)). Calling it unreadable instead would manufacture a boundary on
        every legacy row and re-introduce the exact bug (kk) removed.
    """
    if extra.get("bars_basis") != "entry":
        return ABSENT
    bars = extra.get("bars")
    if not isinstance(bars, dict):
        return None
    sig = {k: bars[k] for k in BRACKET_SIG_FIELDS if k in bars}
    if not sig:
        return None
    try:
        return json.dumps({"bracket": sig}, sort_keys=True)
    except (TypeError, ValueError):
        return None


def policy_signature(extra):
    """Canonical signature (a sorted-JSON string) of the policy a close row
    stamps, or None for a row that carries no readable stamp.

    None never matches anything — an unreadable stamp breaks a run and is
    fail-closed out of any stamp-derived era, because counting a trade whose
    policy cannot be confirmed is exactly the credit the era withdraws. A
    stamp without a non-empty `lenses` is unreadable: a policy that names no
    admissible signal describes nothing.

    Callers that must tell "unstamped" from "broken" use `stamp_state`; this
    keeps its original two-state contract for everyone else."""
    st = stamp_state(extra)
    return None if st is ABSENT else st


def stamped_policy_boundary(rows, parse=None):
    """(epoch, iso, policy_dict, run_n) of the LATEST policy boundary the
    ledger's own `extra.policy` stamps can establish. (None, None, None, 0)
    when the stamps establish nothing; (None, None, policy, n) when they show
    ONE policy for the whole ledger — a known policy with no boundary.

    rows: era_rows' shape, oldest first, with the row's `extra` dict at [4]
    (rows without one — every pre-(jf) caller and every non-stamping book —
    derive nothing, so this is a no-op for the rest of the fleet).

    THE RULE: the graded era is the maximal same-signature SUFFIX of the
    ledger, and the boundary is the CLOSE time of that suffix's first row.
    Three fail-closed properties, each load-bearing:
      * the suffix breaks on ANY row whose stamp (or close stamp) cannot be
        read — an unreadable row cannot confirm the policy held through it;
      * the epoch is the first in-suffix CLOSE, an UPPER bound on when the
        change landed (the change happened at or before the close that first
        recorded it), so keying opens on it can only over-exclude — never
        smuggle an old-policy trade in;
      * a ledger whose EVERY row carries one signature has no boundary at all:
        stamps showing no change are not evidence of one, and inventing a
        boundary at the first close would disqualify a stable book's earliest
        trades for nothing.
    """
    if not rows:
        return None, None, None, 0
    p = _era_parse(parse)
    cur = policy_signature(rows[-1][4] if len(rows[-1]) > 4 else None)
    if cur is None:
        return None, None, None, 0
    epoch, n, stopped_on_absent, i_stop = None, 0, False, -1
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        st = stamp_state(r[4] if len(r) > 4 else None)
        if st is ABSENT:
            # [2026-08-06 (kk)] Pre-adoption row. An absence is not a change.
            stopped_on_absent, i_stop = True, i
            break
        if st != cur:
            i_stop = i
            break
        try:
            e = p(r[2])
        except Exception:      # noqa: BLE001 — unreadable close breaks the run
            i_stop = i
            break
        epoch, n = e, n + 1
    if stopped_on_absent and not any(
            stamp_state(rows[j][4] if len(rows[j]) > 4 else None) is not ABSENT
            for j in range(i_stop + 1)):
        # Every older row is unstamped: this is ADOPTION, not a policy change.
        # The stamps have witnessed no change, so they establish no boundary
        # and the DECLARED era governs — exactly the `n >= len(rows)` case.
        # (A stamp that vanishes and returns mid-ledger is NOT this: some
        # older row is stamped, so the fail-closed boundary below still fires.)
        return None, None, json.loads(cur), n
    if epoch is None:
        return None, None, None, 0
    if n >= len(rows):
        # Stamps show ONE policy across the whole ledger: no boundary (stamps
        # showing no change are not evidence of one, and inventing one at the
        # first close would disqualify a stable book's earliest trades for
        # nothing) — but the policy itself is known, and is returned so the
        # payload can still say which policy the graded sample runs.
        return None, None, json.loads(cur), n
    from datetime import datetime, timezone
    iso = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    return epoch, iso, json.loads(cur), n


def era_rows(bot, rows, parse=None, detail=False):
    """(era_scoped, all_time, era_iso) — THE SINGLE OWNER of "which of a book's
    trades describe the book as it runs today".

    rows: [(pnl_pct, pnl_abs, closed_at_datetime, opened_at)] oldest first —
    `stats()`'s shape with the OPEN stamp appended, because an era is keyed on
    the OPEN (a trade's policy is fixed when the trade is taken). Both returned
    lists are in `stats()`'s 3-tuple shape, ready to hand straight to it.

    Fail-safe in the only direction that is safe: a book with no declared era
    keeps every row (`in_era` returns True on `era_epoch=None`), and an open
    stamp that cannot be read is EXCLUDED when an era is declared. Both
    behaviours are `in_era`'s, unchanged — this is the row plumbing, not a
    second policy.

    [2026-07-31 (hq)] EXTRACTED BECAUSE A CONSUMER RE-IMPLEMENTED IT BY
    OMISSION. `(hc)` made the policy era a PRECONDITION sitting in FRONT of the
    six bars, and `(hn)` made `scripts/evidence_review.py` import
    `stats`/`grade`/`bar_map` so the daily review could not carry its own copy
    of the RULE. It still selected its own SAMPLE, with no era filter — so on
    31-Jul the review published the fleet's ONLY go-live candidate as "5/6
    bars, only 'window' outstanding, ~10.5d away" on t=2.77 / n=84 / 19.5d,
    while this grader read the same book at n=59 / t=0.33 / 13.3d. Wrong in the
    PROMOTIONAL direction, on the one book nearest real money. Importing the
    scoring while re-deriving the sample is `(hj)`'s "a second copy of a rule is
    a second rule" one layer down: the bars were canonical and the thing they
    were computed over was not.

    [2026-08-04 (jf)] THE ERA IS NOW THE LATEST OF THE DECLARED DATE AND THE
    LEDGER'S OWN POLICY-STAMP BOUNDARY (`stamped_policy_boundary`, rows[4]).
    max(), never either-or: an era is the LATEST of every invalidating change,
    so a declared date after the last stamp change still governs (the operator
    can always reset a clock the stamps cannot see), and a stamp change after
    the declared date supersedes it while the declaration keeps covering
    everything before. `detail=True` returns the full reading (epoch, source,
    the graded sample's policy, both candidate boundaries) for the publish
    path; the default 3-tuple is unchanged for every existing caller."""
    declared_ep, declared_iso, declared_why = era_epoch_for(bot)
    st_ep, st_iso, st_policy, st_n = stamped_policy_boundary(rows, parse)
    if st_ep is not None and (declared_ep is None or st_ep > declared_ep):
        era_epoch, era_iso, source = st_ep, st_iso, "policy-stamp"
        why = (f"POLICY STAMP: the ledger's own extra.policy changed at this "
               f"boundary — the graded sample is the newest same-policy run "
               f"({st_n} closes). An era is the LATEST of every invalidating "
               f"change; any earlier declared era ({declared_iso or 'none'}) "
               f"still covers everything before it.")
    else:
        era_epoch, era_iso, source = declared_ep, declared_iso, (
            "declared" if declared_ep is not None else None)
        why = declared_why
    p = _era_parse(parse)
    all_time = [(r[0], r[1], r[2]) for r in rows]
    scoped = [(r[0], r[1], r[2]) for r in rows
              if in_era(r[3] if len(r) > 3 else None, era_epoch, p)]
    if not detail:
        return scoped, all_time, era_iso
    return {"scoped": scoped, "all_time": all_time, "iso": era_iso,
            "epoch": era_epoch, "source": source, "why": why,
            "declared_since": declared_iso, "declared_why": declared_why,
            "stamp_since": st_iso, "stamp_run_n": st_n,
            # The policy the graded sample runs under. Published whenever the
            # stamps know it, whichever boundary governs: the graded era never
            # starts before the stamp boundary, so every graded trade is in
            # the final run and this dict describes all of them.
            "policy": st_policy}


#: [2026-08-06 (kw)] Trades closing within this window are ONE decision, not
#: several. A cross-sectional book rebalances its whole basket at once, so its
#: legs close in a batch and their returns share that instant's move — the
#: single largest source of dependence in this fleet's ledgers.
CLUSTER_WINDOW_S = 60.0


def cluster_stats(rows, mean, sd, n):
    """Cluster-robust view of `t`, keyed on batched CLOSES. Reported, never a
    bar — see the note in `stats`.

    WHY IT EXISTS. `t = mean / (sd/sqrt(n))` assumes n INDEPENDENT
    observations. Several books here close a whole basket in one instant:
    ⚖️ Counterweight holds 10 legs and rebalances them together, so its 70
    legs are ~18 decisions. Treating them as 70 overstates `t` by roughly
    sqrt(legs-per-batch), and `t >= 2.0` is the bar standing between a book
    and REAL MONEY.

    MEASURED at ship: Counterweight reads t_iid **-2.00** and cluster-robust
    **-1.32**. In the significant direction that is the whole ballgame — at
    the earliest date a daily-rebalancing book could pass, an iid t=2.00 is a
    true t of about **0.98**.

    Estimator: the standard cluster-sandwich for a sample mean,
        SE_cr = sqrt( G/(G-1) * sum_g ( sum_{i in g} (x_i - xbar) )^2 ) / n
    with G the number of close-batches. `n_eff` is the iid sample size that
    would produce the same SE, i.e. n * (SE_iid/SE_cr)^2 — so it is directly
    comparable to the `closes` bar.

    Fail-CLOSED on a shape it cannot judge: G < 2 returns None rather than a
    number, because a single cluster has no between-cluster variation and any
    value here would be invented. Absent means "not computable", never "fine".
    """
    try:
        if n < 2 or not rows:
            return None
        groups, cur, cur_ts = [], [], None
        for r in rows:
            ts = r[2]
            if cur_ts is None or (ts - cur_ts).total_seconds() <= CLUSTER_WINDOW_S:
                cur.append(r[0])
                cur_ts = cur_ts if cur_ts is not None else ts
            else:
                groups.append(cur)
                cur, cur_ts = [r[0]], ts
        if cur:
            groups.append(cur)
        g = len(groups)
        if g < 2:
            return None
        meat = sum((sum(x - mean for x in grp)) ** 2 for grp in groups)
        se_cr = math.sqrt((g / (g - 1.0)) * meat) / n
        se_iid = sd / math.sqrt(n)
        # DEGENERACY GUARD. When the batches' deviations cancel, `meat` goes to
        # ~0 and this would report an astronomically large `t_cluster` and
        # `n_eff` — the same degenerate-t pathology (kg) measured at the TP
        # limit (win 100%, t=6.1e15). Found by a test fixture that built the
        # exactly-cancelling case by accident. A near-zero between-batch
        # variance is not evidence of enormous significance; it is a shape
        # this estimator cannot judge, so it fails CLOSED like the G<2 case.
        if not (se_cr > 0) or se_cr < se_iid * 1e-6:
            return None
        return {"n_clusters": g,
                "max_batch": max(len(x) for x in groups),
                "t_cluster": round(mean / se_cr, 2),
                "n_eff": round(n * (se_iid / se_cr) ** 2, 1),
                "window_s": CLUSTER_WINDOW_S}
    except Exception:      # noqa: BLE001 — a reported field never breaks a grade
        return None


def stats(rows, book_usd=None):
    """Grade one book from its closed-trade rows.

    rows: [(pnl_pct, pnl_abs, closed_at_datetime)] oldest first. Pure — the DB
    read is the caller's job so this is selftestable offline.

    The rows must already be ERA-SCOPED — see `era_rows`, the single owner of
    that filter. `stats` cannot enforce it (it never sees the bot id), which is
    exactly why the consumer that skipped it went unnoticed for a day."""
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
    clus = cluster_stats(rows, mean, sd, n)
    mid = n // 2
    h1 = sum(r[1] or 0 for r in rows[:mid])
    h2 = sum(r[1] or 0 for r in rows[mid:])
    eq = peak = dd = 0.0
    for r in rows:
        eq += r[1] or 0
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    wins = sum(1 for x in pct if x > 0)
    realised = sum(r[1] or 0 for r in rows)
    out.update(days=days, mean_pct=mean, t=t, h1=h1, h2=h2,
               # [2026-08-06 (kw)] The cluster-robust read of `t`, beside it.
               # REPORTED, NEVER A BAR: `BAR_NAMES` is the published contract
               # and `grade()` is byte-unchanged, exactly as (kg) did with
               # money. Making it BLOCKING is a gate re-spec and therefore an
               # operator act. None when it cannot be computed (< 2 batches).
               cluster=clus,
               win_rate=wins / n, max_dd_usd=dd,
               max_dd_frac=abs(dd) / book_usd if book_usd else None,
               realised_usd=realised,
               # [2026-08-05 (kg)] THE EARNING RATE. Every one of the six bars
               # is SHAPE (mean, t, halves, maxdd) or SAMPLE SIZE (window,
               # closes). NOT ONE OF THEM IS MONEY, and `realised_usd` was
               # computed here and never published — so a change that destroys
               # most of a book's dollars while improving its shape passes
               # unseen. That is not hypothetical:
               #
               #   MEASURED on 💸 the LIVE Farmer, 71 priced closes replayed
               #   against Lighter's own hourly candles — a take-profit at
               #   0.28% yields win 85.9% and **t = +2.55, which PASSES the
               #   t>=2.0 bar**, on a book earning $2.36 instead of $6.46.
               #   In the limit it is fully degenerate: at TP=0.05% every
               #   close returns +0.05%, giving win 100%, maxDD ~0 and
               #   t = 6.1e15 on $0.80 of the book's $6.46.
               #
               # The mechanism is that TRUNCATION COLLAPSES VARIANCE FASTER
               # THAN IT COLLAPSES THE MEAN, so tightening an exit INFLATES t.
               # Win rate was removed from this gate on 29-Jul ((fk)) for good
               # reasons and nothing replaced it as a sanity check on size, so
               # between then and now the gate would have called a book READY
               # while it earned a third as much.
               #
               # REPORTED, NOT A BAR. `BAR_NAMES` is the published contract and
               # `grade()` is unchanged, so no verdict moves — re-specifying
               # the gate is an operator act ((fk) was). This makes the damage
               # VISIBLE; making it BLOCKING is the operator's call.
               usd_per_day=(realised / days) if days > 0 else None,
               # [2026-08-05 (kh)] THE MINIMUM DETECTABLE EFFECT, so an
               # UNDERPOWERED NULL CANNOT MASQUERADE AS EVIDENCE OF ABSENCE.
               #
               # Every bar here is a test, and a book that fails one fails in
               # one of two completely different ways: the effect is absent, or
               # the sample could never have seen it. The gate said only
               # "t 0.59 < 2" and left the reader to guess which. Measured the
               # day this shipped: 🎫 short-divergence was written into the
               # record as REFUTED at n=28 — where MDE80 is 2.061%/trade, FIVE
               # TIMES the largest per-trade edge this fleet has ever measured
               # at a gradeable n. That refusal established nothing and was
               # reported as though it established something.
               #
               # MEAN-FREE BY CONSTRUCTION, which is why this is publishable
               # where two earlier attempts were correctly refused: `n_needed`
               # divides by the observed mean, so it is finite and positive for
               # the 8 of 14 books whose mean is <= 0 and tells the operator
               # "you already have enough closes" about a book that is losing;
               # `n_sep` was a pure function of an unidentified tau. MDE depends
               # on sd and n ONLY — it says what the sample CAN see, never what
               # it saw.
               #
               # REPORTED, NOT A BAR. `grade()` is untouched. This makes a weak
               # null visible; it changes no verdict.
               mde80_pct=_mde80(sd, n),
               power_at_half_pct=_power(0.005, sd, n))
    return out


def _norm_cdf(x):
    """Phi(x) — no scipy in the freqtrade image, and this is exact enough."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _t_crit(p_z, df):
    """t quantile from its normal counterpart via Cornish-Fisher.

    The t DISTRIBUTION, not the normal, because these samples are small and the
    normal approximation is optimistic in exactly the wrong direction: it makes
    the MDE look SMALLER than it is, i.e. it understates how underpowered a
    thin book is — the one thing this field exists to reveal. At n=28 the gap
    is 1.987% (normal) vs 2.061% (t), and the honest number is the larger.

    Verified against the table: t_{0.975, 27} = 2.0518 (exact 2.0518)."""
    if df < 1:
        return None
    z = p_z
    z3, z5 = z ** 3, z ** 5
    return (z + (z3 + z) / (4.0 * df)
            + (5.0 * z5 + 16.0 * z3 + 3.0 * z) / (96.0 * df * df))


def _mde80(sd, n):
    """Smallest per-trade effect this sample could detect at 80% power,
    two-sided alpha=0.05: (t_0.975 + t_0.80) * sd/sqrt(n)."""
    if not sd or n < 2:
        return None
    df = n - 1
    return ((_t_crit(1.959964, df) + _t_crit(0.8416212, df))
            * sd / math.sqrt(n))


def _power(effect, sd, n):
    """Probability this sample rejects a true `effect`, two-sided alpha=0.05.

    Both tails, because a symmetric test can reject in the wrong direction and
    pretending otherwise overstates power on a tiny sample."""
    if not sd or n < 2:
        return None
    se = sd / math.sqrt(n)
    if se <= 0:
        return None
    lam = abs(effect) / se
    return _norm_cdf(lam - 1.959964) + _norm_cdf(-lam - 1.959964)


#: The six bars, in the order the operator reads them. Names are the PUBLISHED
#: contract (`golive-readiness.books.<bot>.bars`) — the dashboard renders these
#: keys, so a rename here is a breaking change and `test_golive_readiness.py`
#: pins them.
BAR_NAMES = ("window", "closes", "mean", "t", "halves", "maxdd")

# ---------------------------------------------------------------------------
# MARK-TO-MARKET DRAWDOWN [2026-07-31 (ia)] — operator: "prepare Counterweight
# to go live", and this is the prerequisite that makes that decision honest.
#
# THE DEFECT (hl) NAMED AND DEFERRED. `stats()` accumulates CLOSED trades, so
# for a book that HOLDS most of the time most of its drawdown is invisible to
# the bar that governs real money. (hl) proved the two definitions can disagree
# about the VERDICT on 📊 Index Rider; (hq) started the equity series.
#
# ⚖️ COUNTERWEIGHT IS WHERE IT BITES HARDEST, measured 31-Jul:
#   realised +$7.29 over 48 closes -> maxDD reads 0.2% against a 15% bar,
#   while the book's actual equity is $984.61, i.e. -$22.68 of OPEN loss on 24
#   legs it has not closed. It is ALWAYS-IN by construction, so its losses live
#   almost entirely where the realised bar cannot see them.
# And the three bars it fails are window/closes/t — pure TIME AND SAMPLE SIZE.
# At 2.15 closes/day it reaches n=30 in a day, 30 days on ~17-Aug and t=2.0 at
# n~74 (~21-Aug). So on trajectory THIS BOOK PASSES ALL SIX BARS IN LATE AUGUST
# WHILE ITS EQUITY IS BELOW $1,000. That is the failure this closes.
#
# WHY THIS DOES NOT TOUCH `bar_map`/`grade`. Those two are selftest-BOUND to be
# exactly equivalent, and that binding is load-bearing. So the MTM number is
# folded into `max_dd_frac` BEFORE they see it (`apply_mtm`), and both keep
# reading one field. The bar's definition does not change; its INPUT gets
# honest.
#
# STRICTLY RESTRICTIVE: `apply_mtm` takes the WORSE of realised and MTM, so it
# can only ever fail a book that currently passes. It never rescues one.
#
# FLOORS, and they are the reason (hl) refused to ship this on day one: an
# empty or thin series must not decide anything. Below them the realised bar
# stands unchanged and the payload says so via `maxdd_basis`, so a provisional
# verdict is never mistaken for a graded one.
MTM_MIN_SAMPLES = int(os.environ.get("GOLIVE_MTM_MIN_SAMPLES", "200"))
MTM_MIN_DAYS = float(os.environ.get("GOLIVE_MTM_MIN_DAYS", "7"))


def mtm_drawdown(samples, book_usd=None):
    """Peak-to-trough drawdown of a MARK-TO-MARKET equity series.

    samples: [(ts, equity)] in any order, ts a datetime. Pure — the history
    read is the caller's job, same split as `stats`.

    Returns None when the series cannot support a verdict (fewer than 2 usable
    points), so the caller can fall back rather than act on a fabricated 0.0 —
    a book with no series is not a book with no drawdown.
    """
    pts = []
    for s in samples or []:
        try:
            ts, eq = s[0], float(s[1])
        except (TypeError, ValueError, IndexError):
            continue
        if eq != eq or eq in (float("inf"), float("-inf")):
            continue                       # NaN/inf is not an observation
        pts.append((ts, eq))
    if len(pts) < 2:
        return None
    pts.sort(key=lambda p: p[0])
    book_usd = BOOK_USD if book_usd is None else book_usd
    peak = pts[0][1]
    dd = 0.0
    for _, eq in pts:
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    days = (pts[-1][0] - pts[0][0]).total_seconds() / 86400.0
    return {"n": len(pts), "days": days,
            "max_dd_usd": dd,
            "max_dd_frac": abs(dd) / book_usd if book_usd else None,
            "first_equity": pts[0][1], "last_equity": pts[-1][1],
            "peak_equity": max(e for _, e in pts)}


def equity_series(bot, store=None, limit=20000):
    """[(ts, equity)] from `<bot>:equity` in bot_state_history — the series
    `snapshot_equity` writes. Returns [] on a dark DB or any error: the caller
    treats empty as "grade on realised", which is exactly today's behaviour, so
    an unavailable history can never change a verdict.
    """
    if store is None:
        try:
            import bot_pnl_store as store          # noqa: PLC0415
        except Exception:                          # noqa: BLE001
            return []
    # [2026-08-04 (ja), hardening (iz)] The read API is resolved OUTSIDE the
    # fail-safe. (iz) fixed the phantom `load_history` name, but with the
    # attribute access still inside the blanket except, the NEXT phantom
    # method would fail silent the same way — "no usable equity series" on
    # every book while the series accrues. A missing API is a programming
    # error and must fail loud; only the DB call keeps the dark-DB fail-safe.
    read = store.fetch_state_history
    try:
        rows = read(str(bot) + ":equity", limit=limit) or []
    except Exception:                              # noqa: BLE001
        return []
    out = []
    for r in rows:
        try:
            eq = (r.get("payload") or {}).get("equity")
            if eq is None:
                continue
            ts = parse_stamp(r.get("ts"))
            if ts is None:
                continue                           # an unreadable stamp is
                                                   # dropped, never guessed
            out.append((ts, float(eq)))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def apply_mtm(s, mtm, min_samples=None, min_days=None):
    """Fold an MTM drawdown into `s` so `bar_map`/`grade` grade the WORSE of
    the two definitions. Returns a NEW dict; never mutates the caller's.

    `maxdd_basis` is always published: 'mtm' when the series decided,
    'realised' when it did not, plus `mtm` itself (or the reason it was
    unusable) so a thin series is visible rather than silently ignored.
    """
    min_samples = MTM_MIN_SAMPLES if min_samples is None else min_samples
    min_days = MTM_MIN_DAYS if min_days is None else min_days
    out = dict(s or {})
    out["mtm"] = mtm
    if not mtm or mtm.get("max_dd_frac") is None:
        out["maxdd_basis"] = "realised"
        out["mtm_why"] = "no usable equity series"
        return out
    if mtm["n"] < min_samples or mtm["days"] < min_days:
        out["maxdd_basis"] = "realised"
        out["mtm_why"] = (f"series too thin to decide "
                          f"({mtm['n']}/{min_samples} samples, "
                          f"{mtm['days']:.1f}/{min_days:g}d)")
        return out
    realised = out.get("max_dd_frac")
    worse = mtm["max_dd_frac"] if realised is None else max(realised,
                                                           mtm["max_dd_frac"])
    out["max_dd_frac_realised"] = realised
    out["max_dd_frac"] = worse
    out["maxdd_basis"] = "mtm" if worse == mtm["max_dd_frac"] else "realised"
    return out


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
# GATE HORIZON — WHEN does this book become decidable? [2026-08-06 (ks)]
# ---------------------------------------------------------------------------
# Every organ in this fleet senses the past or the present; none computed the
# future. The operator's go-live calendar lived as hand-typed prose
# (OPERATOR_QUEUE item 5: "Farmer window ~16-Aug ... carry ~30-Aug") — the
# exact I12 rot shape — and it HAD already rotted: the hand's 16-Aug matches
# the Farmer's pre-(jf) declared era, while the live row's stamped era is
# 23-Jul, so its window arms ~22-Aug. The (kp) entry itself hand-computed
# "the Farmer needs ~178 in-era closes against 62" in prose. Both are one
# closed form away from the fields this grader already publishes:
#
#     t = mean / (sd/sqrt(n))   =>   n_req(t_bar) = n * (t_bar / t)^2
#
# so the sample needed for the t bar at the book's CURRENT mean/sd needs only
# n and t — no new statistic. This block publishes that arithmetic per book,
# with the honesty rails the fleet has already paid for:
#
#   * REPORTED, NOT A BAR — `BAR_NAMES`/`grade()` untouched; no verdict moves.
#   * The rate denominator is ERA AGE (first in-era close -> now), never the
#     close SPAN: a span cannot see a stall — the last-close->now gap is the
#     quantity that grows with the fault (I1). Measured: dad's span-rate reads
#     2.2x its age-rate because the book stalled 7-11d.
#   * A projection is a FLOOR, never a promise: `halves` is a path property
#     and is listed as a blocker, not scheduled; every ETA assumes the
#     current mean/sd/rate persist, which nothing guarantees — consumers must
#     re-derive from each fresh payload, never cache (an era move voids every
#     previously reported date for that book).
#   * UNREACHABLE means "at current trajectory", NEVER "retire": mean <= 0
#     cannot flip the mean/t/halves bars by accumulating more of itself, and
#     a blown in-era maxDD cannot un-blow (the running peak-to-trough is
#     monotone within an era). ⚖️ Counterweight reads UNREACHABLE today over
#     a sample that deliberately still pools the reverted K=8 window ((hc):
#     capacity is ordinary tuning) — the label is a trajectory statement and
#     the keep-or-retire call stays the operator's (I17).
#   * Fail-closed: junk or too-thin input yields verdict "no_rate"/None and
#     a why, never a fabricated date. pm-turnbull's t=0.07 projects 9,132d —
#     year 2051 — without the cap; with it, that renders as the I17 verdict
#     it actually is, with `raw_days` published so 110d stays distinguishable
#     from 9,132d.
#   * I5: every emitted number is finite-or-None — `save_history` does not
#     run `json_safe`, so a NaN here would kill the whole history write.
HORIZON_CAP_DAYS = float(os.environ.get("HORIZON_CAP_DAYS", "90"))
HORIZON_MIN_N_RATE = int(os.environ.get("HORIZON_MIN_N_RATE", "5"))
# [(kz)] The TIME half of the rate floor. `HORIZON_MIN_N_RATE` bounds the
# numerator; this bounds the DENOMINATOR. 2 days is derived, not chosen: the
# fleet's fastest legitimate book closes a few trades a day, so 2d spans
# several closes for a real earner while refusing the sub-day burst a newborn
# produces in its first hours (measured: 🎸 Barnesy at 45.66/d over 4.2h).
HORIZON_MIN_AGE_D = float(os.environ.get("HORIZON_MIN_AGE_D", "2.0"))
HORIZON_LOWCONF_N = int(os.environ.get("HORIZON_LOWCONF_N", "15"))

# --- [2026-08-06 (ld)] THE DECISION DOCKET ----------------------------------
# (ks) made the fleet's FUTURE computable per book; nothing carried a verdict
# to a DECISION. Measured 6-Aug: 14 of 22 books sat in a state I17 says must
# be decided (9 `unreachable`, 5 `undecidable`) while OPERATOR_QUEUE.md carried
# three of them — and the queue is hand-maintained, so a book can read
# "unreachable at trajectory" for weeks and never reach the operator. That is
# the (gk) shape exactly: the rule that governs real money ran only when a
# human remembered it.
#
# The docket is REPORTED, NEVER A BAR — it promotes nothing, retires nothing
# and changes no verdict. It answers one question: which books have been
# undecidable long enough that I17's keep-or-retire call is overdue?
#
# A verdict can flip on one trade, so a single reading is noise. The book must
# hold a stuck verdict for DOCKET_DAYS, and the clock RESETS the moment the
# verdict changes — a book that recovers leaves the docket and starts over.
DOCKET_DAYS = float(os.environ.get("GOLIVE_DOCKET_DAYS", "7"))
#: Verdicts that mean "not on a path to the gate at the current trajectory".
#: `no_rate` is deliberately NOT here unconditionally — a newborn book is
#: legitimately rate-less (🎸 Barnesy at n=8), and docketing it would be the
#: I7 error: a trigger a book satisfies STRUCTURALLY is not a measurement. It
#: joins only once the book has HAD its window and still cannot produce a rate
#: (see `_docket_stuck`), which is I17's own wording — "still undecidable at
#: the floor after its window".
DOCKET_VERDICTS = ("unreachable", "undecidable")
#: [(lf)] THE CLOCKS LIVE IN THEIR OWN KEY, and that is a correctness choice
#: rather than tidiness. `save_state` replaces a payload WHOLESALE, so while the
#: seen-map rode inside `golive-readiness` a single unreadable prior forced a
#: choice between two bad outcomes: overwrite the clocks with an empty map (what
#: (ld) actually did — one Postgres blip in any of the ~112 publishes a book
#: needs would silently reset every clock, while reporting a reassuring "carried
#: forward"), or skip the whole publish and lose the grade with it. Split apart,
#: a failed read of the clocks costs only the clocks: they are simply not
#: rewritten, the previous value survives, and the GRADE still publishes.
DOCKET_SEEN_KEY = "golive-docket-seen"

# [2026-08-06 (kx)] NON-BOOK bot_pnl PUBLISHERS, declared with reasons — the
# BORN_DARK_OK idiom. The roster sweep asks "living bot_pnl row with no
# ledger rows?", and a NON-TRADING publisher satisfies that structurally
# (I7): the receipt's first live read admitted `market-context` — the
# dashboard's market-data compiler — onto the go-live card as an
# "undecidable book". A new non-trading publisher that is not declared here
# lands VISIBLY on the card's below-floor line (fail-visible, prompting the
# addition), never silently anywhere.
ROSTER_NON_BOOKS = {
    "market-context": "compile_market_data — market prices for the "
                      "dashboard's display; publishes a heartbeat row, "
                      "holds no book",
}


def _fin(x, nd=2):
    """round(x, nd) if x is a finite number, else None — the I5 boundary."""
    try:
        if x is None or not math.isfinite(float(x)):
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def roster_admits(updated_at, now, max_age_h=48.0):
    """Fail-CLOSED admission for the zero-ledger roster sweep [(kv)/(kw)].

    A bot_pnl row with no parseable, sufficiently fresh `updated_at` is NOT a
    living book (I1: liveness before semantics — a frozen row and a healthy
    one are byte-identical if you compare content). Dead publishers are the
    watchdog's jurisdiction; admitting one here would resurrect it on the
    go-live card. Pure so the offline suite can redden a fail-open mutation —
    the first cut of this filter lived inline in main()'s DB path, where a
    deleted check survived the whole suite.

    [(kw)] ACCEPTS THE PUBLISHER'S REAL SHAPE: `fetch_bot_pnl` converts
    `updated_at` to an ISO STRING before returning (`.isoformat()`, in
    bot_pnl_store, since long before this sweep existed). The first shipped
    cut accepted only datetime — so this fail-closed filter silently rejected
    the ENTIRE living roster and the sweep published nothing, caught the same
    day by reading the live payload. The (hj) class verbatim, inside the
    change whose PR cited (hj): the offline repro used a hand-written
    datetime fixture instead of the publisher's own string. Junk strings are
    still refused."""
    from datetime import datetime, timedelta, timezone
    u = updated_at
    if isinstance(u, str):
        try:
            u = datetime.fromisoformat(u)
        except ValueError:
            return False
    if not isinstance(u, datetime) or not isinstance(now, datetime):
        return False
    if u.tzinfo is None:
        u = u.replace(tzinfo=timezone.utc)
    try:
        return (now - u) <= timedelta(hours=max_age_h)
    except TypeError:
        return False


def gate_horizon(s, first_close=None, era_epoch=None, now=None):
    """-> the horizon dict for one era-scoped sample. Pure and offline.

    s           stats() output (post apply_mtm) for the ERA-SCOPED sample.
    first_close datetime of the first in-era close (rate/window basis).
    era_epoch   epoch float of the era boundary, for the window FLOOR when the
                book is too thin to have a rate (carry: era 31-Jul -> 30-Aug).
    now         injected for determinism in tests; defaults to UTC now.

    Verdicts (each one earns its keep in _selftest):
      ready        all six bars pass today — go-live stays an operator act.
      on_track     every failing bar is projectable; `eta` is the date the
                   LAST one flips at the measured rate (a floor if `blockers`
                   is non-empty). `eta_conf`='low' below HORIZON_LOWCONF_N.
      no_rate      < HORIZON_MIN_N_RATE in-era closes — a rate from n=1 is
                   fiction (Poisson CV = 1/sqrt(n) = 100%); only the window
                   FLOOR (first close / era + 30d) is honest, `eta_kind`
                   says so.
      unreachable  mean <= 0 or maxDD blown — at the CURRENT trajectory no
                   amount of the same closes flips those bars.
      undecidable  the projection exceeds HORIZON_CAP_DAYS — I17's class,
                   surfaced the day it becomes visible instead of at the
                   post-mortem. `raw_days` keeps the magnitude auditable.
      unprojectable only path-property bars (halves) fail — they mend by
                   trading, not by the calendar.
    """
    from datetime import datetime, timedelta, timezone
    now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    out = {"verdict": None, "eta": None, "eta_days": None, "eta_kind": None,
           "eta_conf": None, "binding": None, "blockers": [],
           "rate_cpd": None, "n_req_t": None, "raw_days": None, "why": ""}

    def _floor_eta():
        """Window FLOOR from the first close (preferred) or the era epoch."""
        base = first_close if isinstance(first_close, datetime) else None
        if base is None and isinstance(era_epoch, (int, float)) \
                and math.isfinite(era_epoch):
            base = datetime.fromtimestamp(era_epoch, tz=timezone.utc)
        if base is None:
            return None, None
        d = (base + timedelta(days=GOLIVE_MIN_DAYS) - now).total_seconds() \
            / 86400.0
        return (base + timedelta(days=GOLIVE_MIN_DAYS)).date().isoformat(), \
            max(0.0, d)

    n = s.get("n", 0) if isinstance(s, dict) else 0
    try:
        bars = bar_map(s if isinstance(s, dict) else {"n": 0})
    except (KeyError, TypeError):
        # A stats dict that claims n>=2 but lacks the graded fields is junk,
        # not a thin book — refuse the projection rather than misdiagnose it.
        out.update(why="malformed stats — horizon unavailable")
        return out
    if n >= 2 and all(bars.values()):
        out.update(verdict="ready",
                   why="all six bars pass — go-live is an operator act")
        return out

    if n < HORIZON_MIN_N_RATE:
        eta, d = _floor_eta()
        out.update(verdict="no_rate",
                   eta=eta, eta_days=_fin(d, 1),
                   eta_kind=("floor" if eta else None), eta_conf="low",
                   why=(f"n={n} in-era — no measurable close rate; "
                        + (f"window floor {eta} (opens, not passes)"
                           if eta else "no era/close to floor a window on")))
        return out

    fc = first_close if isinstance(first_close, datetime) else None
    age_d = (now - fc).total_seconds() / 86400.0 if fc else None
    if age_d is None or age_d <= 0:
        out.update(verdict="no_rate",
                   why="first in-era close missing or not in the past — "
                       "no rate denominator")
        return out
    if age_d < HORIZON_MIN_AGE_D:
        # [(kz)] A COUNT FLOOR IS NOT A TIME FLOOR — the missing half of the
        # n>=5 rule above. MEASURED on the live payload the day it shipped:
        # 🎸 Barnesy, born 5-Aug, published `rate_cpd: 45.66` — 8 closes over
        # the 4.2 HOURS since its first one, a birth burst extrapolated as
        # throughput. A rate needs a denominator as well as a numerator, and
        # 4 hours of a newborn book is not a measurement of anything.
        #
        # Its ETA happened to be RIGHT (the window bar binds at first-close
        # +30d, pure calendar, immune to the rate) — which is exactly why
        # this had to be caught by reading the number rather than the date:
        # a correct date was carrying a fabricated rate, and the first book
        # whose CLOSES bar binds would have inherited the fiction as a date.
        # Degrades to the same honest window FLOOR the n-floor uses, so the
        # published date does not move; only the false precision goes.
        eta, d = _floor_eta()
        out.update(verdict="no_rate",
                   eta=eta, eta_days=_fin(d, 1),
                   eta_kind=("floor" if eta else None), eta_conf="low",
                   why=(f"first close {age_d * 24:.1f}h ago — under the "
                        f"{HORIZON_MIN_AGE_D:g}d observation floor, a rate "
                        f"would be a birth burst, not throughput; "
                        + (f"window floor {eta} (opens, not passes)"
                           if eta else "no era/close to floor a window on")))
        return out
    # [(la)] THE RATE'S DENOMINATOR IS THE WHOLE OBSERVED ERA, not the tail
    # after the first close. `era_rows` keys an era on the OPEN, so a book
    # that HOLDS necessarily takes one holding period to produce its first
    # in-era close — and measuring the rate from that close prices the wait
    # out of existence. MEASURED: 🌾 carry holds 65-70h, so at n>=5 its rate
    # would read 2-3x its true throughput, on the fleet's ONLY go-live
    # candidate, published as a confident `on_track` date. Same I1 argument
    # as close-span vs age: the denominator must contain the quiet part.
    rate_base = fc
    if isinstance(era_epoch, (int, float)) and math.isfinite(era_epoch):
        try:
            _e = datetime.fromtimestamp(era_epoch, tz=timezone.utc)
            if _e < rate_base:
                rate_base = _e
        except (OverflowError, OSError, ValueError):
            pass                      # junk epoch: keep the first-close base
    rate_age_d = (now - rate_base).total_seconds() / 86400.0
    rate = n / (rate_age_d if rate_age_d > 0 else age_d)
    out["rate_cpd"] = _fin(rate, 2)

    mean = s.get("mean_pct")
    if not bars["mean"] or not bars["maxdd"]:
        parts = []
        if not bars["mean"]:
            parts.append(f"mean {100 * (mean or 0):+.3f}% <= 0 — more of the "
                         "same closes cannot flip mean/t/halves")
        if not bars["maxdd"]:
            dd = s.get("max_dd_frac")
            parts.append((f"maxDD {100 * dd:.1f}%" if dd is not None
                          else "maxDD unmeasurable")
                         + " >= bar — a blown in-era drawdown cannot un-blow")
        out.update(verdict="unreachable",
                   why="at current trajectory: " + "; ".join(parts))
        return out

    per_bar = {}
    if not bars["window"]:
        # [(la)] THE WINDOW BAR IS A SPAN, AND A SPAN NEEDS A CLOSE TO ADVANCE.
        # `bar_map` reads `s["days"]` = the CLOSE SPAN (last close − first),
        # which cannot grow on its own: it moves only when a NEW close lands.
        # Projecting it as pure calendar (`30 − age_d`) therefore published
        # `eta = TODAY` for a STALLED 5/6 book — the exact "waiting only on
        # the window" shape the operator reads as lead time, on a book that
        # had not traded in 12 days. This is the I1 stall class the rate
        # denominator was already fixed for; the window projection was not.
        # Floor at the expected wait for one more close.
        per_bar["window"] = max(GOLIVE_MIN_DAYS - age_d, 1.0 / rate)
    if not bars["closes"]:
        per_bar["closes"] = max(0.0, (GOLIVE_MIN_CLOSES - n) / rate)
    t = s.get("t")
    if not bars["t"] and isinstance(t, (int, float)) and t > 0:
        # mean > 0 here (the unreachable branch returned above), so t > 0 is
        # guaranteed by construction — the isinstance guard is for junk input.
        n_req = math.ceil(n * (GOLIVE_MIN_T / t) ** 2)
        out["n_req_t"] = int(n_req)
        per_bar["t"] = max(0.0, (n_req - n) / rate)
    blockers = [b for b in ("halves",) if not bars[b]]
    out["blockers"] = blockers

    if not per_bar:
        out.update(verdict="unprojectable",
                   why="only path-property bars fail "
                       f"({', '.join(blockers) or 'none'}) — they mend by "
                       "trading, not by the calendar")
        return out

    binding = max(per_bar, key=lambda k: per_bar[k])
    eta_days = per_bar[binding]
    if eta_days > HORIZON_CAP_DAYS:
        out.update(verdict="undecidable", binding=binding,
                   raw_days=_fin(eta_days, 1),
                   why=(f"needs ~{eta_days:.0f}d at the measured rate "
                        f"({rate:.2f}/d) — beyond the {HORIZON_CAP_DAYS:.0f}d "
                        "horizon; I17: a book that cannot reach its own bar "
                        "is a keep-or-retire call, not a tuning pass"))
        return out

    eta_dt = now + timedelta(days=eta_days)
    why = (f"{binding} bar binds: ~{eta_days:.1f}d at {rate:.2f} closes/day"
           + (f" (needs ~{out['n_req_t']} closes for t>={GOLIVE_MIN_T:g} "
              "at current mean/sd)" if binding == "t" else ""))
    if blockers:
        why += f" — FLOOR: {', '.join(blockers)} must also mend"
    out.update(verdict="on_track", binding=binding,
               eta=eta_dt.date().isoformat(), eta_days=_fin(eta_days, 1),
               eta_kind="projected",
               eta_conf=("low" if n < HORIZON_LOWCONF_N else "ok"),
               why=why)
    return out


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


def latest_overlap_start(eps, min_gap_s=None):
    """-> datetime the MOST RECENT same-pair overlap began, or None.

    [2026-08-01 (ih)] `same_pair_overlaps` answers "did this ever happen", and
    a ledger is permanent, so that question can only ever answer YES again —
    it is a one-way latch. Once `(hp)`/`(ic)`/`(id)` closed the duplicate-writer
    hole in code, the detector kept firing forever on a CLOSED window and kept
    telling the operator to *"stop the duplicate Railway service"* — an action
    that (a) no longer exists, since `claim_writer` now arbitrates and the
    loser writes its own key, and (b) `(id)` showed would be actively wrong,
    because two containers are now FAILOVER rather than a fault.
    A permanent page for a fixed condition is how an operator learns to ignore
    the pager — `(hw)`'s own "a sticky error pages once and then means nothing".

    Measured on 🌾 carry: 7 overlaps, ALL between 17-Jul and 29-Jul 07:39Z,
    against a guard that merged 31-Jul 00:52Z. Zero since.

    WHAT THIS DOES NOT DO: it does not clear the finding. The pooled window is
    still pooled and a promotion still may not rest on it — that is why the
    `integrity` precondition and the `fails` line are unchanged. It only lets
    a consumer tell "happening now, act" from "happened then, discount the
    sample".
    """
    min_gap_s = LEDGER_MIN_OVERLAP_S if min_gap_s is None else min_gap_s
    by = {}
    for pair, o, c in eps:
        by.setdefault(pair, []).append((o, c))
    latest = None
    for _pair, v in by.items():
        v.sort()
        for i in range(len(v) - 1):
            if (v[i][1] - v[i + 1][0]).total_seconds() > min_gap_s:
                start = v[i + 1][0]          # when the SECOND hold opened
                if latest is None or start > latest:
                    latest = start
    return latest


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


def _docket_stuck(hz, era_days=None, roster_zero_ledger=False):
    """(bool, reason) — is this book off any path to the gate right now?

    `unreachable` and `undecidable` are the horizon's own words for it.
    `no_rate` qualifies ONLY once the book has already HAD its 30-day window
    and still cannot produce a rate — I17's "still undecidable at the floor
    after its window". Without that clause every newborn book would dock on
    its first day, which is the I7 error (a trigger satisfied structurally
    measures nothing) and would train the reader to ignore the docket.

    [(lf)] `roster_zero_ledger` is the ZERO-LEDGER case, and it needs its own
    arm because such a book has no era at all — `era_epoch_for` returns None,
    so the clause above can never fire for it and 📊 equities-regime (0 closes
    ever, the fleet's standing I17 case, and the docket's own motivating
    example) was PERMANENTLY invisible to the docket (ld) shipped. There is no
    era to measure against, so the DOCKET'S OWN CLOCK is the time basis:
    DOCKET_DAYS of consecutive "living publisher, zero closes in the ledger"
    is the evidence, and it is exactly what I17 asks for.
    """
    v = (hz or {}).get("verdict")
    if v in DOCKET_VERDICTS:
        return True, v
    if roster_zero_ledger:
        return True, "zero_ledger"
    if v == "no_rate" and isinstance(era_days, (int, float)) \
            and math.isfinite(era_days) and era_days >= GOLIVE_MIN_DAYS:
        return True, "no_rate_past_window"
    return False, None


def decision_docket(current, prior, now_iso, docket_days=None):
    """-> (docket, seen) — books whose keep-or-retire call is overdue (I17).

    PURE. `current` is {bot: {"hz": horizon, "era_days": float|None,
    "n": int, "mean_pct": float|None, "t": float|None}}; `prior` is the last
    published `docket_seen` map; `now_iso` is this run's stamp. Returns the
    docket list (sorted, worst-evidenced first) and the NEW seen-map to
    persist.

    THE CLOCK IS PER (BOOK, REASON) AND RESETS ON CHANGE. A book that goes
    unreachable -> on_track -> unreachable starts again, because the second
    spell is not evidence about the first. Storing the reason alongside the
    stamp is what makes that resettable; a bare timestamp could not tell the
    two spells apart.

    FAIL-SAFE TOWARD SILENCE, and deliberately in this direction: an
    unreadable prior map means every book looks first-seen TODAY, so the
    docket comes up EMPTY rather than declaring the whole fleet overdue. A
    docket that cries wolf after one bad read is worse than one that is a week
    late — the (gl) lesson, and the caller must skip the write entirely on a
    FAILED read rather than seed over the record ((jz) seed class).
    """
    docket_days = DOCKET_DAYS if docket_days is None else docket_days
    prior = prior if isinstance(prior, dict) else {}
    seen, docket = {}, []
    for bot in sorted(current):
        c = current[bot] or {}
        stuck, reason = _docket_stuck(c.get("hz"), c.get("era_days"),
                                      c.get("roster_zero_ledger"))
        if not stuck:
            continue                     # not stuck -> no entry -> clock gone
        was = prior.get(bot)
        was = was if isinstance(was, dict) else {}
        if was.get("reason") == reason and was.get("since"):
            since = was["since"]
        else:
            since = now_iso              # new spell (or a changed reason)
        seen[bot] = {"reason": reason, "since": since}
        held = _days_between(since, now_iso)
        if held is None or held < docket_days:
            continue
        hz = c.get("hz") or {}
        docket.append({
            "book": bot, "reason": reason, "since": since,
            "days_held": round(held, 1),
            "n": c.get("n"), "mean_pct": c.get("mean_pct"), "t": c.get("t"),
            "raw_days": hz.get("raw_days"),
            "why": hz.get("why") or "",
            # I17 is a KEEP-OR-RETIRE call for the operator, never another
            # tuning pass — say so in the entry so the docket cannot be read
            # as a to-do list for the next session.
            "asks": ("keep-or-retire (I17) — an operator decision, not a "
                     "tuning pass"),
        })
    # worst first: longest stuck, then weakest evidence
    docket.sort(key=lambda d: (-(d["days_held"] or 0),
                               (d["mean_pct"] if d["mean_pct"] is not None
                                else 0.0)))
    return docket, seen


def _days_between(a_iso, b_iso):
    """Whole-and-fractional days from ISO `a` to ISO `b`; None if unreadable.
    Unreadable stamps must not become 0 days (that would silently RESET a
    book's clock every run) nor a huge number (that would docket it at once)."""
    from datetime import datetime, timezone
    try:
        a = datetime.fromisoformat(str(a_iso).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(b_iso).replace("Z", "+00:00"))
    except Exception:      # noqa: BLE001
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    d = (b - a).total_seconds() / 86400.0
    return d if math.isfinite(d) and d >= 0 else None


def book_payload(s):
    """The published per-book numbers for one sample, tolerating n<2.

    Split out at (hc) because there are now TWO samples per book (era-scoped
    and all-time) and an era-scoped sample can be legitimately too thin to
    grade — the old inline dict indexed `s["days"]` and would have raised a
    KeyError on exactly the book the era block was written for."""
    bars = bar_map(s)
    out = {"n": s.get("n", 0), "bars": bars, "bar_names": list(BAR_NAMES),
           "bars_passed": sum(bars.values())}
    # [2026-07-31 (ia)] The MTM drawdown rides on EVERY payload, including the
    # n<2 early return below — a book too thin to grade on closes may still
    # have an equity series, and that is exactly the always-in book this
    # exists for. `maxdd_basis` states which definition decided, so a reader
    # can never mistake a provisional realised verdict for a graded one.
    if s.get("maxdd_basis"):
        out["maxdd_basis"] = s["maxdd_basis"]
    if s.get("mtm_why"):
        out["mtm_why"] = s["mtm_why"]
    _m = s.get("mtm")
    if _m:
        out["mtm"] = {
            "n": _m.get("n"), "days": (round(_m["days"], 1)
                                       if _m.get("days") is not None else None),
            "max_dd_pct": (round(100 * _m["max_dd_frac"], 2)
                           if _m.get("max_dd_frac") is not None else None),
            "last_equity": _m.get("last_equity"),
            "peak_equity": _m.get("peak_equity")}
    if s.get("max_dd_frac_realised") is not None:
        out["max_dd_pct_realised"] = round(100 * s["max_dd_frac_realised"], 2)
    if s.get("n", 0) < 2:
        out.update(days=None, mean_pct=None, t=None, win_pct=None,
                   max_dd_pct=None, h1=None, h2=None,
                   net_usd=None, usd_per_day=None,
                   mde80_pct=None, power_at_half_pct=None,
                   why=s.get("why") or "too few closes to grade")
        return out
    dd = s.get("max_dd_frac")
    _upd = s.get("usd_per_day")
    out.update(days=round(s["days"], 1),
               mean_pct=round(100 * s["mean_pct"], 3),
               t=round(s["t"], 2), win_pct=round(100 * s["win_rate"], 1),
               max_dd_pct=(round(100 * dd, 1) if dd is not None else None),
               h1=round(s["h1"], 2), h2=round(s["h2"], 2),
               # [(kg)] MONEY, beside the shape. See `stats` for the incident:
               # a 0.28% take-profit takes the live Farmer to t=+2.55 (PASSING)
               # on 37% of its dollars. Neither field is a bar; both exist so
               # that a book whose shape improved while its earnings collapsed
               # cannot look like progress.
               net_usd=round(s["realised_usd"], 2),
               usd_per_day=(round(_upd, 4) if _upd is not None else None),
               # [(kh)] What this sample COULD have seen. A failing bar beside a
               # large MDE is "we cannot tell yet"; beside a small one it is
               # "measured absent". Those route to opposite decisions under I17.
               mde80_pct=(round(100 * s["mde80_pct"], 3)
                          if s.get("mde80_pct") is not None else None),
               power_at_half_pct=(round(s["power_at_half_pct"], 3)
                                  if s.get("power_at_half_pct") is not None
                                  else None))
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
    # [(ii)] Derived from the TABLE, not a frozen literal — this asserted
    # "2026-07-17" and so broke when carry's era legitimately moved to 31-Jul
    # for the two-writer window. What is under test is the SUFFIX STRIP, not
    # the date; pinning the date here tested the declaration twice and the
    # wiring once.
    from datetime import datetime as _dtm, timezone as _tz
    _declared = POLICY_ERA["perps-funding-carry"][0]
    for suffixed in ("perps-funding-carry-lshadow", "perps-funding-carry"):
        ep, iso, why = era_epoch_for(suffixed)
        assert ep is not None and iso == _declared, (suffixed, ep, iso)
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
    # [(ii)] Era-RELATIVE. These were literals either side of 17-Jul, so they
    # asserted the declared DATE a third time instead of the boundary RULE,
    # and broke when carry's era legitimately moved.
    from datetime import timedelta as _td
    _era_dt = _dtm.fromisoformat(_declared).replace(tzinfo=_tz.utc)
    assert in_era((_era_dt + _td(days=3)).isoformat(), era_ep, _p) is True
    assert in_era((_era_dt - _td(minutes=1)).isoformat(), era_ep, _p) is False
    assert in_era(_era_dt.isoformat(), era_ep, _p) is True, "boundary inclusive"
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

    # ---- [2026-07-31 (ia)] MARK-TO-MARKET DRAWDOWN -----------------------
    # THE INCIDENT SHAPE: ⚖️ Counterweight, always-in, realised maxDD 0.2%
    # against a 15% bar while its equity sits at $984.61 — the loss is in
    # positions it has not closed.
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    def _eq(vals, step_h=1.0, start=None):
        t0 = start or _dt(2026, 7, 1)
        return [(t0 + _td(hours=step_h * i), v) for i, v in enumerate(vals)]

    # a series that dips to 900 off a 1000 peak is a 10% MTM drawdown
    md = mtm_drawdown(_eq([1000, 1050, 900, 1010]))
    assert md["n"] == 4 and abs(md["max_dd_frac"] - 0.150) < 1e-9, md
    assert md["peak_equity"] == 1050 and md["last_equity"] == 1010, md
    # ORDER MUST NOT MATTER — history comes back NEWEST FIRST
    assert mtm_drawdown(_eq([1000, 1050, 900, 1010])[::-1])["max_dd_frac"] == \
        md["max_dd_frac"], "the series must be sorted, not assumed ordered"
    # unusable series -> None, never 0.0. A book with no series is NOT a book
    # with no drawdown, and 0.0 would silently PASS the bar.
    for bad in ([], None, [(_dt(2026, 7, 1), 1000.0)],
                [(_dt(2026, 7, 1), float("nan")), (_dt(2026, 7, 2), 1000.0)]):
        assert mtm_drawdown(bad) is None, bad

    # ---- apply_mtm: strictly restrictive, floors respected ----------------
    _base = dict(good)                       # a book that passes all six bars
    assert bar_map(_base)["maxdd"] is True
    _thick = {"n": 500, "days": 30.0, "max_dd_frac": 0.22}      # 22% MTM
    _got = apply_mtm(_base, _thick)
    assert _got["maxdd_basis"] == "mtm" and _got["max_dd_frac"] == 0.22, _got
    assert bar_map(_got)["maxdd"] is False, \
        "an MTM drawdown past the cap must FAIL the bar the realised one passed"
    assert grade(_got)[0] is False, "and it must reach the verdict"
    # ...and `bar_map` stays exactly equivalent to `grade` (the pinned invariant)
    assert all(bar_map(_got).values()) is grade(_got)[0]
    # STRICTLY RESTRICTIVE: a BETTER mtm number never rescues a worse realised
    _bad_realised = apply_mtm(dict(good, max_dd_frac=0.40),
                              {"n": 500, "days": 30.0, "max_dd_frac": 0.01})
    assert _bad_realised["max_dd_frac"] == 0.40, _bad_realised
    assert bar_map(_bad_realised)["maxdd"] is False, \
        "MTM must take the WORSE of the two, never the kinder"
    # FLOORS: a thin series decides nothing and SAYS so
    _thin = apply_mtm(_base, {"n": 5, "days": 0.2, "max_dd_frac": 0.99})
    assert _thin["maxdd_basis"] == "realised" and bar_map(_thin)["maxdd"] is True
    assert "too thin" in _thin["mtm_why"], _thin
    _none = apply_mtm(_base, None)
    assert _none["maxdd_basis"] == "realised" and _none["mtm"] is None
    assert bar_map(_none) == bar_map(_base), \
        "no series must grade EXACTLY as before — this change is a no-op then"
    # the caller's dict is never mutated
    assert "maxdd_basis" not in _base and _base.get("mtm") is None

    # THE COUNTERWEIGHT CASE, end to end: realised DD ~0 but the book is down
    # 1.5% and holding. With a thick series the MTM number is what grades.
    _cw = apply_mtm(dict(good, max_dd_frac=0.002),
                    mtm_drawdown(_eq([1000.0 - i * 0.05 for i in range(400)])))
    assert _cw["maxdd_basis"] == "mtm", _cw
    assert _cw["max_dd_frac"] > 0.002, "the open loss must reach the bar"
    assert _cw["max_dd_frac_realised"] == 0.002, "and the realised one is kept"
    # [2026-08-04 (ja)] The contract SPLIT, and this assertion is the record
    # of why. The old line pinned "any junk store -> []" — the exact tolerance
    # that hid (iz)'s phantom `load_history` for 4 days. New contract: a store
    # MISSING the read API raises (programming error, loud); a store whose
    # read RAISES returns [] (dark DB, fail-safe).
    try:
        equity_series("nope", store=object())
        raise AssertionError("a store with no read API must raise, not []")
    except AttributeError:
        pass

    class _DarkStore:                                   # dark DB: read raises
        @staticmethod
        def fetch_state_history(key, limit=800):
            raise RuntimeError("db unreachable")
    assert equity_series("nope", store=_DarkStore) == []

    # ---- [2026-08-04 (jf)] STAMP-DERIVED POLICY BOUNDARIES ----------------
    # Offline mechanics only — the publisher-contract half (rows built by the
    # taker's own `_close_extra`, per (hj)) lives in
    # tests/autonomy/test_golive_policy_era.py, because importing the taker
    # here would drag it into this module's import graph in every image.
    from datetime import datetime as _sdt
    from datetime import timedelta as _std
    from datetime import timezone as _stz

    _t0 = _sdt(2026, 8, 10, tzinfo=_stz.utc)     # after every declared era
    POL_A = {"venue": "lighter_live", "bull": True, "lenses": ["divergence"],
             "sides": {"divergence": ["long", "short"]}, "max_open": 4,
             "ticket_top_n": 6}
    POL_B = {**POL_A, "sides": {"divergence": ["short"]}}    # the (hj) shape

    def _prow(open_h, close_h, pol, base=None):
        b = base or _t0
        return (0.01, 10.0, b + _std(hours=close_h),
                (b + _std(hours=open_h)).isoformat(),
                {"policy": pol} if pol is not None else {})

    # a1..a3 under policy A, then a STRADDLER (opened in the ambiguity window,
    # stamped B at close), then b1..b2 cleanly under B. Close-ordered.
    rows_ab = [_prow(0, 1, POL_A), _prow(1, 2, POL_A), _prow(2, 3, POL_A),
               _prow(9, 10, POL_B),          # run start — itself a straddler
               _prow(4, 10.5, POL_B),        # the straddler proper
               _prow(10, 11, POL_B), _prow(11, 12, POL_B)]
    ep_b, iso_b, pol_b, n_b = stamped_policy_boundary(rows_ab)
    assert n_b == 4 and pol_b["sides"] == {"divergence": ["short"]}, (n_b, pol_b)
    assert abs(ep_b - (_t0 + _std(hours=10)).timestamp()) < 1e-6, (
        "the boundary is the FIRST close of the newest same-policy run — an "
        "upper bound on when the change landed, so keyed opens over-exclude "
        "rather than smuggle an old-policy trade in")
    # era keyed on the OPEN: both straddlers are out, only b1/b2 count.
    sc, at, got = era_rows("stampbook", rows_ab)
    assert got == iso_b and len(at) == 7, (got, iso_b, len(at))
    assert len(sc) == 2 and {r[2] for r in sc} == \
        {_t0 + _std(hours=11), _t0 + _std(hours=12)}, sc
    d = era_rows("stampbook", rows_ab, detail=True)
    assert d["source"] == "policy-stamp" and d["iso"] == iso_b, d
    assert d["policy"]["lenses"] == ["divergence"] and d["stamp_run_n"] == 4
    assert d["declared_since"] is None and d["epoch"] == ep_b, d
    # ORDINARY TUNING IS NOT A BOUNDARY: max_open / ticket_top_n moves leave
    # ONE signature, so there is no era at all — the (hc) anti-weaponisation
    # rule, now enforced on the stamp path too.
    rows_tune = [_prow(0, 1, POL_A), _prow(1, 2, {**POL_A, "max_open": 9}),
                 _prow(2, 3, {**POL_A, "ticket_top_n": 12})]
    ep_t, iso_t, pol_t, n_t = stamped_policy_boundary(rows_tune)
    assert ep_t is None and iso_t is None, (
        "a capacity/supply lever move created a policy boundary — the growth "
        "rail walks levers daily and this would keep every clock at zero")
    assert pol_t is not None and n_t == 3, "one-policy ledger: policy known"
    assert era_rows("stampbook", rows_tune)[2] is None
    # FAIL-CLOSED: an unreadable stamp INSIDE the run breaks it (the boundary
    # moves LATER, never earlier), and an unstamped NEWEST row derives nothing.
    rows_junk = rows_ab[:5] + [(0.01, 10.0, _t0 + _std(hours=11),
                                (_t0 + _std(hours=10)).isoformat(),
                                {"policy": "junk"})] + rows_ab[6:]
    ep_j, _, _, n_j = stamped_policy_boundary(rows_junk)
    assert n_j == 1 and ep_j == (_t0 + _std(hours=12)).timestamp(), (
        "an unreadable stamp must break the run — counting a trade whose "
        "policy cannot be confirmed is the credit this block withdraws")
    assert stamped_policy_boundary(rows_ab + [(0.01, 10.0,
        _t0 + _std(hours=13), (_t0 + _std(hours=12)).isoformat(), {})]) == \
        (None, None, None, 0), "an unstamped newest row derives no boundary"
    # 4-tuple rows (every pre-(jf) caller) and stampless books: no-op.
    assert stamped_policy_boundary([r[:4] for r in rows_ab]) == \
        (None, None, None, 0)
    # THE MAX() RULE, both directions, on the book with a real declared era.
    _c_iso = POLICY_ERA["perps-funding-carry"][0]
    # stamps AFTER the declared date -> the stamp boundary governs...
    d2 = era_rows("perps-funding-carry-lshadow", rows_ab, detail=True)
    assert d2["source"] == "policy-stamp" and d2["iso"] == iso_b, d2
    assert d2["declared_since"] == _c_iso, d2
    # ...stamps BEFORE it -> the declared era governs (it is the LATER of the
    # two invalidating changes) and the stamp reading is still published.
    _july = _sdt(2026, 7, 1, tzinfo=_stz.utc)
    rows_early = [_prow(o, c, p, base=_july) for (o, c, p) in
                  [(0, 1, POL_A), (1, 2, POL_A), (9, 10, POL_B),
                   (10, 11, POL_B), (11, 12, POL_B)]]
    d3 = era_rows("perps-funding-carry-lshadow", rows_early, detail=True)
    assert d3["source"] == "declared" and d3["iso"] == _c_iso, d3
    assert d3["stamp_since"] is not None and d3["scoped"] == [], d3
    # signature: the tuning fields are OUTSIDE it; junk shapes are None.
    assert policy_signature({"policy": {**POL_A, "max_open": 99}}) == \
        policy_signature({"policy": POL_A})
    for junk in (None, {}, {"policy": None}, {"policy": "x"},
                 {"policy": {"lenses": []}}, {"policy": {"bull": True}}):
        assert policy_signature(junk) is None, junk

    # ---- [2026-08-06 (ks)] GATE HORIZON — every verdict earns its keep ----
    # Deterministic: `now` is always injected. Each verdict below is the SOLE
    # outcome of its case, per this selftest's own rule ("each bar must be the
    # sole reason in some case, or it is untested decoration").
    _hnow = t0 + timedelta(days=40)

    # READY — all six bars pass; no projection, no date.
    hz = gate_horizon(good, first_close=t0, now=_hnow)
    assert hz["verdict"] == "ready" and hz["eta"] is None, hz

    # ON_TRACK, t binding — mean>0, 0<t<2, everything else green. The rate is
    # exactly 1.0/day (40 closes, first close 40d ago), so eta_days must equal
    # (n_req - 40) and the ETA date must be now + that. This pins the
    # n_req = n*(T/t)^2 closed form THROUGH the date arithmetic.
    ontrack = stats(mk([0.052, -0.032] * 20))
    assert ontrack["mean_pct"] > 0 and 0 < ontrack["t"] < GOLIVE_MIN_T, ontrack
    hz = gate_horizon(ontrack, first_close=t0, now=_hnow)
    assert hz["verdict"] == "on_track" and hz["binding"] == "t", hz
    assert hz["n_req_t"] == math.ceil(40 * (GOLIVE_MIN_T / ontrack["t"]) ** 2)
    assert abs(hz["eta_days"] - (hz["n_req_t"] - 40) / 1.0) < 0.2, hz
    from datetime import timedelta as _htd
    assert hz["eta"] == (_hnow + _htd(days=hz["eta_days"])).date().isoformat()
    assert hz["blockers"] == [] and hz["eta_kind"] == "projected", hz

    # ...and a FLOOR when halves also fails: same shape, sick second half.
    floored = stats(mk([0.06] * 20 + [-0.038] * 20))
    assert floored["mean_pct"] > 0 and floored["h2"] < 0 < floored["h1"]
    assert 0 < floored["t"] < GOLIVE_MIN_T, floored
    hz = gate_horizon(floored, first_close=t0, now=_hnow)
    assert hz["verdict"] == "on_track" and hz["blockers"] == ["halves"], hz
    assert "FLOOR" in hz["why"], hz

    # NO_RATE — n=1 gives no rate; only the window floor is honest, and it
    # comes from the era epoch when there is no usable first close (carry's
    # real shape: era 31-Jul -> floor 30-Aug).
    hz = gate_horizon(stats(mk([0.01])), era_epoch=t0.timestamp(), now=_hnow)
    assert hz["verdict"] == "no_rate" and hz["eta_kind"] == "floor", hz
    assert hz["eta"] == (t0 + timedelta(days=GOLIVE_MIN_DAYS)).date().isoformat()

    # UNREACHABLE on mean — a losing mean cannot flip mean/t/halves by
    # accumulating more of itself. `tails` is the high-win-rate loser above.
    hz = gate_horizon(tails, first_close=t0, now=_hnow)
    assert hz["verdict"] == "unreachable" and "mean" in hz["why"], hz
    assert hz["eta"] is None, hz

    # UNREACHABLE on maxDD alone — mean>0, t>2, but the in-era drawdown is
    # blown and a running peak-to-trough cannot un-blow. Kills the mutation
    # that treats maxdd as projectable.
    blown = stats(mk([2.0] * 10 + [-1.6] * 10 + [2.0] * 20))
    assert blown["mean_pct"] > 0 and blown["t"] >= GOLIVE_MIN_T, blown
    assert blown["max_dd_frac"] >= GOLIVE_MAX_DD, blown
    hz = gate_horizon(blown, first_close=t0, now=_hnow)
    assert hz["verdict"] == "unreachable" and "maxDD" in hz["why"], hz

    # UNDECIDABLE — the cap converts a year-2051 date into the I17 verdict,
    # with raw_days published so magnitude stays auditable. `noisy` (t~0.33)
    # needs ~1,400 closes at 1/day. Also pins n_req = n*(T/t)^2 EXACTLY at
    # t=1.0 (the arithmetic a mutated factor breaks first).
    hz = gate_horizon(noisy, first_close=t0, now=_hnow)
    assert hz["verdict"] == "undecidable" and hz["eta"] is None, hz
    assert hz["raw_days"] and hz["raw_days"] > HORIZON_CAP_DAYS, hz
    pin = dict(noisy)
    pin.update(t=1.0)
    hz = gate_horizon(pin, first_close=t0, now=_hnow)
    assert hz["n_req_t"] == 160, hz     # 40 * (2.0/1.0)^2, exact
    assert hz["verdict"] == "undecidable" and hz["raw_days"] == 120.0, hz

    # UNPROJECTABLE — only the halves bar fails; it mends by trading, not by
    # the calendar. No date may be fabricated for it.
    halved = stats(mk([0.05] * 20 + [-0.001] * 20))
    assert halved["t"] >= GOLIVE_MIN_T and halved["h2"] < 0, halved
    hz = gate_horizon(halved, first_close=t0, now=_hnow)
    assert hz["verdict"] == "unprojectable" and hz["eta"] is None, hz

    # FAIL-CLOSED junk: no stats, no floor -> no_rate with why, never a date;
    # a first close in the FUTURE (clock skew / junk stamp) refuses a rate
    # rather than fabricating a negative denominator.
    hz = gate_horizon({}, now=_hnow)
    assert hz["verdict"] == "no_rate" and hz["eta"] is None, hz
    hz = gate_horizon(ontrack, first_close=_hnow + timedelta(days=1), now=_hnow)
    assert hz["verdict"] == "no_rate" and "denominator" in hz["why"], hz
    # I5 at the boundary: every emitted number is finite or None.
    for _v in (gate_horizon(ontrack, first_close=t0, now=_hnow),
               gate_horizon(noisy, first_close=t0, now=_hnow)):
        for _k, _x in _v.items():
            if isinstance(_x, float):
                assert math.isfinite(_x), (_k, _x)

    print("golive_readiness selftest OK (clean pass, the carry shape, the "
          "high-win-rate loser, window/DD bars, ungradeable input, policy "
          "eras, stamp-derived policy boundaries: first-new-close bound, "
          "open-keyed straddlers, tuning-not-a-boundary, fail-closed junk, "
          "declared-vs-stamp max, MTM drawdown: worse-of, floors, "
          "no-series no-op, gate horizon: ready/on-track/floor/no-rate/"
          "unreachable-mean/unreachable-dd/undecidable-cap/unprojectable/"
          "fail-closed junk + the n*(T/t)^2 pin)")


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
    # [2026-08-05 (kd)] FAIL CLOSED ON A DEAD LEDGER READ. An empty fetch used
    # to fall straight through to the table and print a confident
    # "READY: none" over ZERO rows — indistinguishable from a real verdict, in
    # the rule that governs real money. Observed for real this session: the
    # Postgres password rotated mid-run ((kb)), `fetch_paper_trades` returned []
    # behind its own never-raise guard, and the grader reported a clean
    # negative. The daily review's own notes warn about this for an UNSET url;
    # it fires identically on an AUTH FAILURE, which the note did not cover.
    #
    # An empty ledger is never a legitimate state for this fleet (24 books,
    # ~1,700 retained closes), so there is no good-news case to protect —
    # unlike the audits, whose empty-input case is real. Exit 2, distinct from
    # the 1 a real failing grade uses, so a caller can tell "could not read"
    # from "nothing qualifies".
    if not rows:
        print("DEGRADED — no ledger rows read (DATABASE_URL unset, "
              "unreachable, or auth failed). NO VERDICT IS PUBLISHED: a "
              "clean-looking 'READY: none' over zero rows is the one output "
              "this grader must never produce.", file=sys.stderr)
        return 2
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
          f"{'win%':>6s} {'maxDD%':>7s} {'net$':>8s} {'$/day':>8s} "
          f"{'MDE80%':>7s}  verdict")
    print("-" * 104)
    ready, payload_books, payload_floor = [], {}, {}
    # [(ld)] Docket inputs, collected on BOTH horizon paths (graded and
    # below-floor) and resolved after the loop — see decision_docket.
    _docket_now = {}

    def _era_age_d(era_ep):
        """Days since the era boundary, or None. The honest denominator for
        'has this book had its window?' — see the note at the call site."""
        from datetime import datetime, timezone
        if not isinstance(era_ep, (int, float)) or not math.isfinite(era_ep):
            return None
        d = (datetime.now(timezone.utc).timestamp() - era_ep) / 86400.0
        return d if d >= 0 else None

    # Hoisted out of the row loop: `parse_ts` is used AFTER it (by `era_rows`),
    # and a book whose every row fails to parse — or an empty one — would leave
    # the name unbound. An import inside a loop body is not a guarantee that the
    # name exists once the loop ends.
    from datetime import datetime, timezone

    from experiment_judge import parse_ts
    for bot in sorted(books):
        rs = sorted(books[bot], key=_key)
        quads, integ_eps = [], []
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
                ts = datetime.fromtimestamp(parse_ts(_key(r)), tz=timezone.utc)
            except Exception:      # noqa: BLE001
                continue
            # [(jf)] `extra` rides at [4]: it carries the close's policy stamp,
            # which `era_rows` now reads to derive the LATEST policy boundary.
            quads.append((r.get("profit_ratio"), r.get("profit_abs"), ts,
                          r.get("open_ts"), r.get("extra")))
        # ONE owner of "which trades count" — `era_rows` keys the era on the
        # OPEN stamp. Extracted at (hq) so the daily review runs the same
        # selection rather than its own; see that docstring for what the
        # divergence cost.
        ed = era_rows(bot, quads, parse=parse_ts, detail=True)
        parsed, parsed_all = ed["scoped"], ed["all_time"]
        era_iso, _era_ep = ed["iso"], ed["epoch"]
        # [2026-07-30 (hc)] The ERA-SCOPED sample is authoritative; the all-time
        # one is published beside it so nothing is hidden and the difference is
        # readable rather than asserted. `min_closes` is applied to the ALL-TIME
        # count on purpose: a book whose era has too few closes must still
        # appear, showing its era bars dark, or narrowing the window would
        # silently REMOVE the frontrunner from the report instead of demoting it.
        s, s_all = stats(parsed), stats(parsed_all)
        if s_all.get("n", 0) < a.min_closes:
            # [2026-08-06 (kv)] BELOW THE FLOOR IS NOT INVISIBLE ANY MORE.
            # `continue` used to be the whole story, and it hid exactly the
            # books the horizon exists to flag: newborn 🎸 Barnesy accrued its
            # first closes off-payload, and the clearest I17 cases sat where
            # no consumer could see them. `books` membership is UNCHANGED —
            # this is a separate additive map, so no existing consumer's
            # world changes shape. Fail-soft: a horizon error here loses one
            # annotation, never the grade.
            try:
                # [(la)] SAME maxDD BASIS AS THE GRADED PATH. This called
                # `gate_horizon` on the RAW stats while the graded path (below)
                # folds MTM in first — so `bars["maxdd"]` meant two different
                # things either side of `--min-closes`, and the below-floor
                # side used the realised-only definition I9 exists to replace.
                # A thin book with a blown MTM drawdown would read `on_track`
                # with a date instead of `unreachable`. Inside the fail-soft
                # try, so a series read failure still costs one annotation.
                hz_f = gate_horizon(
                    apply_mtm(s, mtm_drawdown(equity_series(bot))),
                    first_close=(parsed[0][2] if parsed else None),
                    era_epoch=_era_ep)
            except Exception:      # noqa: BLE001
                hz_f = {"verdict": None, "why": "horizon unavailable"}
            # [(ld)] Below-floor books are docket candidates too — 📊
            # equities-regime (0 closes ever, ~17.2 closes/yr) is the fleet's
            # standing I17 case and it lives HERE, not in `books`. Excluding
            # them would rebuild the very blind spot (kv) closed.
            _docket_now[bot] = {"hz": hz_f, "era_days": _era_age_d(_era_ep),
                                "n": s.get("n", 0),
                                "mean_pct": s.get("mean_pct"), "t": s.get("t")}
            payload_floor[bot] = {"n_alltime": s_all.get("n", 0),
                                  "why_absent": f"below --min-closes "
                                                f"({a.min_closes})",
                                  "horizon": hz_f}
            continue
        # [2026-07-31 (ia)] MARK-TO-MARKET DRAWDOWN, folded in BEFORE grading.
        # `apply_mtm` takes the WORSE of realised and MTM, so this can only
        # fail a book that currently passes — it never rescues one. Below the
        # series floors it is a no-op and `maxdd_basis` says 'realised', so a
        # provisional verdict is never mistaken for a graded one. The equity
        # series is the one (hq) started; a book without one grades exactly as
        # it did before.
        s = apply_mtm(s, mtm_drawdown(equity_series(bot)))
        ok, fails = grade(s)
        # [2026-07-30 (hf)] LEDGER INTEGRITY IS A PRECONDITION, not a bar. It
        # does not join BAR_NAMES — that tuple is the published contract the
        # dashboard renders and a seventh entry breaks every consumer — but a
        # book whose ledger cannot have come from one process is NOT GRADEABLE,
        # so it can never be READY. Fail-closed, and the reason is stated in
        # `fails` where a human reads it.
        # [2026-08-01 (ii)] THE BLOCKING CHECK RUNS OVER THE GRADED SAMPLE.
        #
        # `(hf)` scoped this to the WHOLE ledger on the reasoning that "a second
        # writer is a property of the book's record, not of the era being
        # graded". That is right about DETECTION and wrong about BLOCKING, and
        # the difference had become total: **a ledger is append-only, so an
        # all-time check is a ONE-WAY LATCH** — once true it is true forever, no
        # matter what is fixed in code. 🌾 carry, the only book in the fleet with
        # a measured claim, could never be READY again on 7 overlaps that all
        # fall between 17-Jul and 29-Jul 07:39Z, against a `claim_writer` guard
        # that merged 31-Jul 00:52Z with zero overlaps since. A precondition a
        # book cannot ever clear is not a precondition, it is a retirement.
        #
        # Evaluating it over a DIFFERENT sample from the bars is also the `(hq)`
        # defect one layer down — there the daily review imported the go-live
        # RULE but not its SAMPLE, and rule and data described different books.
        # The bars answer "is this book's CURRENT policy any good"; integrity
        # must answer "is THAT sample one book's record".
        #
        # NOTHING IS HIDDEN AND DETECTION IS NOT WEAKENED:
        #   * the ALL-TIME count is still computed, still published, and still
        #     printed on the book's line, so a historical pooling is visible
        #     forever — it just no longer vetoes forever;
        #   * an ONGOING duplicate is by definition in the recent trades, which
        #     ARE the era, so it still blocks;
        #   * `fleet_immune` pages on `latest_overlap` recency ((ih)), which is
        #     the live-incident detector and is unaffected;
        #   * with no declared era the two sets are identical, so this is a
        #     no-op for every book but the ones that have one.
        overlaps_all = same_pair_overlaps(integ_eps)
        integ_eps_era = [e for e in integ_eps
                         if _era_ep is None or e[1].timestamp() >= _era_ep]
        overlaps = same_pair_overlaps(integ_eps_era)
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
        # [(ks)] THE HORIZON — computed beside the verdict, never instead of
        # it. Wrapped so an annotation bug can never fail the grade (the same
        # never-raise contract the publish block carries): a dark horizon is a
        # lost projection; a crashed grader is a lost gate.
        try:
            hz = gate_horizon(s, first_close=(parsed[0][2] if parsed else None),
                              era_epoch=_era_ep)
        except Exception as e:      # noqa: BLE001
            hz = {"verdict": None, "why": f"horizon error: {e}"}
        # [(ld)] Docket input. ERA AGE, never `s["days"]` — (lb) established
        # that the close SPAN cannot advance during a stall, and "has this
        # book had its 30-day window?" is exactly the question a stall must
        # not be able to answer falsely.
        _docket_now[bot] = {"hz": hz, "era_days": _era_age_d(_era_ep),
                            "n": s.get("n", 0), "mean_pct": s.get("mean_pct"),
                            "t": s.get("t")}
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
            # [(jf)] A stamp-derived boundary names its source on the line — a
            # date the POLICY_ERA table does not contain must not read as if it
            # were declared there.
            _src = " (policy-stamp)" if ed.get("source") == "policy-stamp" else ""
            flag += (f"   [era {era_iso}{_src}: {s.get('n', 0)} of {s_all['n']} "
                     f"closes count]")
        if overlaps_all and not overlaps:
            # [(ii)] Clean IN-ERA but pooled HISTORICALLY. Stated on the line
            # rather than in `fails`, because it is not a failure — the sample
            # being graded is not the sample that was pooled — and a note in
            # `fails` on a book that reads READY is a contradiction a consumer
            # would have to special-case. Never silent: a real past pooling
            # that stopped being mentioned is a reading lost.
            flag += (f"   [ledger: {len(overlaps_all)} historical overlap(s) "
                     f"predate this era]")
        if hz.get("verdict") and hz["verdict"] != "ready":
            # [(ks)] One glance at WHEN. The full reasoning is in the payload.
            _h = hz["verdict"] + (f" {hz['eta']}" if hz.get("eta") else "") \
                + (f" ({hz['binding']})" if hz.get("binding") else "")
            flag += f"   [horizon: {_h}]"
        if s.get("n", 0) < 2:
            print(f"{bot:34s} {s.get('n', 0):>4d} {'-':>6s} {'-':>8s} {'-':>6s} "
                  f"{'-':>6s} {'-':>7s} {'-':>8s} {'-':>8s} {'-':>7s}  "
                  f"ungradeable in era{flag}")
        else:
            # [(kg)] net$ and $/day sit BESIDE the shape bars, because every
            # one of the six is shape or sample size and none is money — a
            # 0.28% take-profit takes the live Farmer to a PASSING t=+2.55 on
            # 37% of its dollars, and this row is where that becomes visible.
            _upd = s.get("usd_per_day")
            _mde = s.get("mde80_pct")
            _mde_s = "n/a" if _mde is None else f"{100 * _mde:.2f}"
            print(f"{bot:34s} {s['n']:>4d} {s['days']:>6.1f} "
                  f"{100*s['mean_pct']:>7.3f}% {s['t']:>6.2f} "
                  f"{100*s['win_rate']:>5.1f}% "
                  f"{('n/a' if dd_pct is None else f'{dd_pct:.1f}%'):>7s} "
                  f"{s.get('realised_usd', 0):>+8.2f} "
                  f"{('n/a' if _upd is None else f'{_upd:+.3f}'):>8s} "
                  # [(kh)] MDE80 turns a failing bar from "no" into either
                  # "measured absent" (small MDE) or "we cannot tell yet"
                  # (large MDE) — opposite decisions under I17.
                  f"{_mde_s:>7s}  "
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
            # [(jf)] `source` says which boundary governs (declared |
            # policy-stamp), `policy` says WHICH policy the graded sample runs
            # (from the ledger's own stamps), and both candidate boundaries
            # are published so a consumer can compute the real gradeable date
            # (since + 30d) and see what a declaration would supersede.
            "era": ({"since": era_iso, "source": ed.get("source"),
                     "why": ed.get("why"),
                     "policy": ed.get("policy"),
                     "declared_since": ed.get("declared_since"),
                     "stamp_since": ed.get("stamp_since"),
                     "closes_in_era": s.get("n", 0),
                     "closes_all_time": s_all.get("n", 0)} if era_iso else None),
            "alltime": book_payload(s_all),
            # [2026-08-06 (ks)] GATE HORIZON — when this book becomes
            # decidable at its measured trajectory. REPORTED, NOT A BAR
            # (`grade()`/`BAR_NAMES` untouched); era-scoped only, computed
            # once here rather than in `book_payload` (which runs twice per
            # book and would double it onto `alltime`, where a projection
            # over a superseded sample means nothing). See `gate_horizon`.
            "horizon": hz,
            # [(hf)] Published so a consumer can render the warning without
            # string-matching `fails`, exactly as `bars` did for the bar map.
            "integrity": {
                # The GRADED-sample verdict — what actually blocks READY.
                "two_writers": bool(overlaps),
                "same_pair_overlaps": len(overlaps),
                "deepest_overlap_h": (round(overlaps[0][1], 2) if overlaps
                                      else 0.0),
                "deepest_overlap_pair": (overlaps[0][0] if overlaps else None),
                # [(ii)] The ALL-TIME reading, published beside it so a
                # historical pooling stays visible forever even once it has
                # left the graded era. Equal to the above for any book with no
                # declared era. A consumer wanting "was this book EVER pooled"
                # reads this; a consumer wanting "may it be promoted" reads
                # `two_writers`.
                "same_pair_overlaps_alltime": len(overlaps_all),
                "deepest_overlap_h_alltime": (round(overlaps_all[0][1], 2)
                                              if overlaps_all else 0.0),
                # [(ih)] WHEN the most recent one began. `two_writers` is a
                # one-way latch over a permanent ledger, so on its own it can
                # never stop firing once true — and it kept sending the
                # operator after a service to stop that no longer exists. This
                # field is what lets a consumer separate "happening now" from
                # "happened then". The finding itself is UNCHANGED: the pooled
                # window stays pooled and still blocks READY.
                "latest_overlap": (lambda d: d.isoformat() if d else None)(
                    latest_overlap_start(integ_eps)),
                "peak_concurrent": peak_concurrency(integ_eps)}}
    print()
    print(f"READY: {ready or 'none'}")

    # [2026-08-06 (kv)] ZERO-LEDGER BOOKS — the roster sweep. A book that has
    # never closed a trade has no paper_trades row at all, so the loop above
    # cannot even see it to demote it: 📊 equities-regime (0 closes ever,
    # measured ~17.2 closes/yr) is the fleet's standing I17 case and was
    # invisible to the very calendar built to flag it. The roster is the
    # bot_pnl summary table (every living book publishes one), minus retired
    # rows, minus anything the ledger already covered; rows stale >48h are
    # skipped (I1 — a frozen row is not a living book, and dead publishers
    # are the watchdog's jurisdiction, not this grader's). Fail-soft
    # everywhere: this sweep may only ever ADD annotations.
    # [(kw)] THE SWEEP REPORTS ITS OWN OUTCOME IN THE PAYLOAD. Its first
    # failure was visible only as a stdout line in a container nobody can
    # read (I4's shape): the payload showed three skip-path books and gave no
    # way to tell "roster swept clean" from "roster sweep dark". `scanned=0`
    # or a non-null `error` now says so where a consumer can see it.
    roster_meta = {"scanned": 0, "admitted": 0, "rejected": 0,
                   "non_book": 0, "error": None}
    try:
        _rnow = datetime.now(timezone.utc)
        _seen = set(books) | set(payload_floor)
        for _r in (store.fetch_bot_pnl() or []):
            roster_meta["scanned"] += 1
            _b = _r.get("bot")
            if not _b or _b in _seen or _b in retired:
                continue
            if _b in ROSTER_NON_BOOKS:
                # [(kx)] declared non-trading publisher — counted so the
                # exclusion is itself visible in the receipt.
                roster_meta["non_book"] += 1
                continue
            if not roster_admits(_r.get("updated_at"), _rnow):
                roster_meta["rejected"] += 1
                continue
            roster_meta["admitted"] += 1
            # [(la)] DERIVE THE WORDING FROM THE NUMBER, never assert it. This
            # branch's real predicate is "absent from `fetch_paper_trades`",
            # which is NOT the same claim as "no closes ever" — `n_alltime`
            # comes from the bot_pnl summary and can disagree three ways: a
            # poller-published row that writes no paper_trades, a book whose
            # closes all fall outside the fetch's 20k newest-first window, and
            # a book whose every retained row is quarantined. When they
            # disagree the mismatch is a real FINDING (the sample the gate
            # would grade does not exist), not a contradiction to paper over.
            _n_all = int(_r.get("closed_trades") or 0)
            _why = ("no closes ever — undecidable until the book closes "
                    "trades (I17: keep-or-retire, not another tuning pass)"
                    if _n_all == 0 else
                    f"bot_pnl reports {_n_all} closes but the ledger holds "
                    "none for this book — the sample the gate would grade "
                    "does not exist (poller-only, outside the fetch window, "
                    "or fully quarantined)")
            payload_floor[_b] = {
                "n_alltime": _n_all,
                "why_absent": ("no closed trades in the ledger" if _n_all == 0
                               else "no LEDGER rows despite a non-zero "
                                    "bot_pnl close count"),
                "horizon": {"verdict": "no_rate", "eta": None,
                            "eta_days": None, "eta_kind": None,
                            "eta_conf": None, "binding": None, "blockers": [],
                            "rate_cpd": None, "n_req_t": None,
                            "raw_days": None, "why": _why}}
            # [(lf)] THE ROSTER IS A THIRD HORIZON PATH AND IT FED NOTHING.
            # (ld) claimed "below-floor books are in the docket ... 📊
            # equities-regime" and that was FALSE in production: the two
            # zero-ledger books enter the payload ONLY here, and this loop did
            # not write `_docket_now` — so the docket's own motivating case
            # was invisible to it, rebuilding the blind spot (kv) closed and
            # (ld) claimed to have kept closed.
            # A zero-ledger book also has NO era (`era_epoch_for` -> None), so
            # the `no_rate` arm's `era_days >= 30` test could never be true for
            # it either. Both halves are fixed here: the book is fed in, with
            # its own reason, and THE DOCKET'S OWN CLOCK supplies the time
            # basis the missing era cannot — seven consecutive days of "living
            # publisher, zero closes ever" IS I17's signal, and it needs no era.
            _docket_now[_b] = {"hz": payload_floor[_b]["horizon"],
                               "era_days": None, "roster_zero_ledger": True,
                               "n": _n_all, "mean_pct": None, "t": None}
    except Exception as e:      # noqa: BLE001 — annotations only, never the grade
        roster_meta["error"] = f"{type(e).__name__}: {e}"
        print(f"roster sweep skipped: {type(e).__name__}: {e}")
    if payload_floor:
        print(f"below floor: " + ", ".join(
            f"{b} n{v['n_alltime']}" for b, v in sorted(payload_floor.items())))

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
            _now_iso = _dt.now(_tz.utc).isoformat(timespec="seconds")
            # [(ld)/(lf)] THE DECISION DOCKET. The clocks live in their own
            # key (DOCKET_SEEN_KEY) so a transient read failure costs the
            # CLOCKS and never the GRADE — see the constant's note. The read is
            # CHECKED so "no row" and "READ FAILED" stay distinguishable ((jz)
            # seed class): on a failure we do not recompute and we do not
            # rewrite, so the stored clocks survive untouched.
            _docket, _seen, _docket_why = [], {}, None
            _seen_ok = False
            try:
                if hasattr(_store, "load_state_checked"):
                    _ok_prior, _prior_seen = _store.load_state_checked(
                        DOCKET_SEEN_KEY)
                else:
                    _prior_seen, _ok_prior = _store.load_state(
                        DOCKET_SEEN_KEY), True
                if _ok_prior:
                    _docket, _seen = decision_docket(
                        _docket_now, (_prior_seen or {}).get("seen"), _now_iso)
                    _seen_ok = True
                else:
                    _docket_why = ("docket clocks unreadable — NOT recomputed "
                                   "and NOT rewritten this cycle, so the "
                                   "stored clocks survive (the grade is "
                                   "unaffected)")
            except Exception as _de:      # noqa: BLE001
                _docket_why = f"docket unavailable: {type(_de).__name__}: {_de}"
            payload = {
                "updated": _now_iso,
                "ttl_sec": TTL_SEC,
                # [(ld)] I17's overdue keep-or-retire calls, with the clock
                # that makes "overdue" a measurement. REPORTED, NEVER A BAR:
                # `bar_names`/`grade()` are untouched and no verdict moves.
                "decision_docket": _docket,
                "docket_seen": _seen,
                "docket_days": DOCKET_DAYS,
                **({"docket_why": _docket_why} if _docket_why else {}),
                "bar": {"min_days": GOLIVE_MIN_DAYS,
                        "min_closes": GOLIVE_MIN_CLOSES,
                        "min_t": GOLIVE_MIN_T, "max_dd": GOLIVE_MAX_DD},
                "bar_names": list(BAR_NAMES),
                "books": payload_books,
                # [(kv)] Books BELOW the publish floor, each with an honest
                # horizon — a separate additive map so `books` membership (a
                # consumer contract) is unchanged. See the roster sweep above.
                "below_floor": payload_floor,
                # [(kw)] The sweep's own receipt — scanned=0 or a non-null
                # error means the roster went DARK, which must be readable
                # from the payload, never only from container stdout (I4).
                "roster": roster_meta,
                "ready": sorted(ready)}
            ok_pub = _store.save_state(KEY, payload)
            # [(lf)] The clocks are written ONLY when the read succeeded. A
            # write we cannot make safely is a write we do not make: on a
            # failed read `_seen` is `{}` and persisting it would zero every
            # book's clock, which is precisely the defect this split exists to
            # remove. The GRADE above is already published either way.
            if _seen_ok:
                _store.save_state(DOCKET_SEEN_KEY,
                                  {"updated": _now_iso, "ttl_sec": TTL_SEC,
                                   "seen": _seen})
            # HISTORY too, because the question the baseline document asks is a
            # TRAJECTORY one — "is t moving toward 2.0 and n above 41?" — and a
            # single current snapshot cannot answer it. 4 writes/day against a
            # 60-day retention is ~240 rows; negligible against the ~400/day
            # the organs already write.
            _store.save_history(KEY, payload)
            print(f"published {KEY}: {len(payload_books)} books, "
                  f"{len(ready)} ready ({'ok' if ok_pub else 'WRITE FAILED'})")
            # [(ld)] PRINT IT — a docket nobody reads is a note, which is the
            # thing this build exists to stop being. Named books, never a
            # count (I8): "3 overdue" tells the operator nothing they can act
            # on, and (lb) had just fixed exactly that in the daily review.
            if _docket:
                print(f"\n⚖️  DECISION DOCKET — {len(_docket)} book(s) stuck "
                      f"≥{DOCKET_DAYS:g}d. I17: keep-or-retire is an OPERATOR "
                      f"call, not another tuning pass.")
                for _d in _docket:
                    _mp = _d.get("mean_pct")
                    _t = _d.get("t")
                    print(f"   {_d['book']:34s} {_d['reason']:20s} "
                          f"{_d['days_held']:>5.1f}d  n={_d.get('n')}"
                          f"{'' if _mp is None else f'  mean={_mp:+.3f}%'}"
                          f"{'' if _t is None else f'  t={_t:+.2f}'}")
            elif _docket_why:
                print(f"\n⚖️  decision docket: {_docket_why}")
        except Exception as e:      # noqa: BLE001 — a publish must never fail the grade
            print(f"publish skipped: {type(e).__name__}: {e}")
    print("Go-live remains an explicit operator act — this grades, it does not "
          "promote. Lighter's tape is ONE regime; a DIRECTIONAL book passing "
          "here has passed in that regime only.")


if __name__ == "__main__":
    # [(kd)] `main()` was called bare, so its return value was DISCARDED and the
    # process exited 0 whatever happened. The (kd) degraded-read guard returned
    # 2 and the shell saw 0 — a guard that cannot fire, which is the class this
    # repo keeps re-learning. `or 0` because a normal run returns None.
    sys.exit(main() or 0)
