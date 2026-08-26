#!/usr/bin/env python3
"""evidence_review.py — the daily evidence review, as code instead of ad-hoc SQL.

WHY THIS EXISTS. The `daily-evidence-review` scheduled task fired every day
24-27 Jul and wrote NOTHING: `bot_state['evidence-review']` went 106h without an
update while the cron's own `lastRunAt` advanced daily. The task was not
failing to run — it was running and dying partway, because the review was
re-derived as fresh SQL each morning and the schema has two traps that kill the
NATURAL query on first contact:

  1. `paper_trades.closed_at` / `opened_at` are **TEXT**, not timestamptz. So
     `WHERE closed_at > now() - interval '7 days'` raises
     `operator does not exist: text > timestamp with time zone` — and it is the
     obvious way to write the go-live-gate and recent-window queries.
  2. `bot_pnl` has no `max_drawdown` COLUMN (it lives in `extra` jsonb, and no
     Lighter-era publisher populates it). `SELECT ... max_drawdown` raises
     `column "max_drawdown" does not exist`.

Both are the kind of error that aborts a script mid-run, after the verdicts are
computed but before the UPSERT. The durable fix is not "remember the casts" —
it is to stop re-deriving the review each day, and to make every section
FAIL-SOFT so one bad query can never again cost the whole run. A section that
throws records its error in the payload and the review still publishes.

WRITE SCOPE — HARD. This script's only write is bot_state['evidence-review'].
`_assert_write_target` gates the single UPSERT; there is no other INSERT/UPDATE
in the file and no code path that takes a table name from data.

Usage:
    python3 scripts/evidence_review.py --selftest   # offline, no DB
    python3 scripts/evidence_review.py --dry-run    # verify + print, no write
    python3 scripts/evidence_review.py              # verify, upsert, write report

DB URL from $DATABASE_URL, else $DATABASE_PUBLIC_URL, else:
    railway variables --service Postgres --kv | grep DATABASE_PUBLIC_URL
"""
import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys

# The ONLY bot_state key this script may write. See module docstring.
REVIEW_KEY = "evidence-review"
ALERTS_KEY = "fleet-alerts"

# [LOAD-BEARING] paper_trades.closed_at/opened_at are TEXT in FOUR formats,
# measured 28-Jul over 2267 rows: ISO-8601 with offset (len 32),
# '2026-07-16 05:04:54 UTC' (len 23), len 25 and len 20 variants. Lexicographic
# comparison is therefore UNSOUND across formats — ' ' (0x20) sorts before 'T',
# so '2026-07-16 23:00 UTC' compares LESS than '2026-07-16T01:00+00:00' despite
# being 22h later. Every time filter must cast. All 2267 rows cast cleanly.
CA = "closed_at::timestamptz"

START_EQUITY = 1000.0    # $1,000 per book, no top-ups (CLAUDE.md)
ALERT_WINDOW_D = 7

# [2026-08-06 — I1, LIVENESS BEFORE SEMANTICS] How old the dislocation census
# publisher may be before its CONTENT stops meaning anything.
#
# THE INCIDENT this names: 🧲 Snap Back was RETIRED 4-Aug ((jh)), so
# `bot_state['lighter-dislocation-lshadow']` froze at its last write. This
# verifier then read the frozen payload's per-symbol `last_iso` fields, found
# them inside the 7-day alert window, and published **33 of 37 alerts as
# "active"** every morning — a dead book's last words, re-certified daily into
# the operator's 🔔 EVIDENCE banner. The smoking gun was one character: the
# section wrote `st, _ = load_state(...)` and DISCARDED the publisher's own
# `updated_at`. A frozen census and a live one are byte-identical if you only
# compare content; the timestamp is the sole thing that separates them.
#
# DERIVED, not taste: the publisher's loop is 90s
# (`lighter_dislocation_bot.LOOP_SECONDS`) and its retired-idle path sleeps
# 3600s. 6h is 240x the live cadence and 6x the idle sleep, so it cannot fire
# on a merely slow loop, and it fires unambiguously on a dead one (the census
# was 23.5h stale when this shipped). Generous on purpose: the cost of a false
# "stale" is one day of a re-verifiable alert, the cost of a false "active" is
# the fleet acting on a corpse.
CENSUS_STALE_H = 6.0

# [LOAD-BEARING — 2026-07-30] The go-live gate is NOT re-implemented here. It is
# imported from `scripts/golive_readiness.py`, the canonical grader CLAUDE.md
# names, so the two can never drift.
#
# WHY, measured: this file carried its OWN copy of the gate
# (GATE_MIN_TRADES=20 / GATE_MIN_WR=0.55 / GATE_MAX_DD=0.15) — the rule the
# 29-Jul re-spec REPLACED (CHANGELOG (fk)). One day later the daily review
# reproduced, in both directions, the exact pair of errors that re-spec was
# written to eliminate:
#   * it ADMITTED `perps-funding-spread-lshadow` as clearing the gate on
#     WR 56.1% — a book whose t is 0.65, i.e. no measured edge at all; and
#   * it REJECTED `perps-funding-carry-lshadow`, the fleet's best-evidenced
#     book (t=2.60, n=82, both halves +), on WR 40.2% <= 55%.
# Win rate is orthogonal to expectancy. A second copy of a rule that governs
# real money is a second rule; the import is the fix, not new constants.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
#
# [2026-07-31 (hq)] AND THE SAMPLE IS IMPORTED TOO, not just the rule. `(hn)`
# fixed the copied RULE above and left the review selecting its own ROWS — with
# no policy-era filter, which `(hc)` made a PRECONDITION sitting in FRONT of the
# six bars. One day later this section published the fleet's ONLY go-live
# candidate as "5/6 bars, only 'window' outstanding, ~10.5d away" (t=2.77,
# n=84, 19.5d) while the canonical grader read the same book at n=59, t=0.33,
# 13.3d — three bars short, not one. Wrong in the PROMOTIONAL direction on the
# book nearest real money. `era_rows` is now the one owner of which trades
# count, so the review and the grader cannot disagree about the sample any more
# than they can about the bars.
try:                                     # run as a script (sys.path[0]=scripts/)
    from golive_readiness import (BAR_NAMES, GOLIVE_MIN_CLOSES,
                                  GOLIVE_MIN_DAYS, bar_map, book_payload,
                                  drop_retired_sleeves, era_rows, gate_horizon,
                                  grade, retired_sleeves, same_pair_overlaps,
                                  stats)
except ImportError:                      # run as `python -m scripts.evidence_review`
    from scripts.golive_readiness import (BAR_NAMES, GOLIVE_MIN_CLOSES,
                                          GOLIVE_MIN_DAYS, bar_map,
                                          book_payload, drop_retired_sleeves,
                                          era_rows, gate_horizon, grade,
                                          retired_sleeves, same_pair_overlaps,
                                          stats)

# Cheap SQL prefilter before the per-book ledger read. It must never be STRICTER
# than the real closes bar, or a genuine candidate is hidden before it is graded.
CANDIDATE_MIN_CLOSES = min(10, GOLIVE_MIN_CLOSES)

# Rows whose ledgers are HISTORY — retired bots keep closing nothing, but their
# 30d window can still contain trades for a few weeks after the cut and they
# will happily "pass" a go-live gate they can never act on.
#
# [2026-08-16 (ni)] DERIVED, not hand-listed. THE INCIDENT: this frozenset was
# a hand copy frozen at the JULY cut while the fleet retired twelve more books
# under it — 🌊 Tide Rider (if), 🧲 Snap Back (jh), 📊 Index Rider (lo), the
# Taker's live arm (ma), 🚀 crypto-breakout-4h (mr) and the SEVEN-row red-stop
# slate (nf) the day before this ran. Every one of them was still being fed to
# the go-live scan below. The visible symptom was mild — the 🔭 horizon line
# named eight dead books, the (gl) overstating-detector shape — but the real
# exposure is the line above it: this loop's whole job is to announce a book as
# a REAL-MONEY promotion candidate, and `pm-gillard-lshadow` (n=304, the
# largest ledger in the scanned set) was retired at t=−1.85 the previous day
# and graded here anyway. A gate that can nominate a corpse is the (hj) class:
# the review carrying its own stale copy of a standard it does not own.
#
# `cleanup_legacy_bots.LEGACY_BOTS` is the canonical declaration — the same
# list that PRUNES the frozen rows, and the half of CLAUDE.md's two-half
# retirement rule that cannot be skipped without the row reappearing. It is
# what `golive_readiness` already imports for exactly this purpose, so review
# and grader now agree about which books are dead as they already agree about
# the bars and the era.
#
# The literal below survives ONLY as the degraded-mode FLOOR (it is a strict
# subset of the canonical list, verified in --selftest), never as a parallel
# authority: `golive_readiness` fails OPEN to `set()` here, which for THIS
# consumer means grading every retired book — the exact bug being fixed. A
# union means an unimportable canonical list can never make the scan wider
# than it is today.
_RETIRED_FLOOR = frozenset({
    "event-listing-sniper", "scanner-cross-exchange-arb", "scanner-triangular-arb",
    "perps-rsi-meanrev", "perps-rsi-meanrev-lshadow", "perps-donchian-breakout",
    "perps-donchian-breakout-lshadow", "perps-donchian-breakout-lighter",
    "perps-funding-carry", "equities-momentum", "equities-momentum-lshadow",
    "equities-regime-ibkr", "crypto-trend-daily-lighter",
})
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cleanup_legacy_bots import LEGACY_BOTS as _LEGACY_BOTS   # noqa: E402
    RETIRED = _RETIRED_FLOOR | frozenset(_LEGACY_BOTS)
except Exception:      # noqa: BLE001 — a degraded list, never a lost report
    RETIRED = _RETIRED_FLOOR
# NOTE the exact-match contract this relies on. `LEGACY_BOTS` carries the
# KRAKEN-era BARE names (`freqtrade-georgia`, `freqtrade-mum`,
# `freqtrade-avo-maria`, retired 14-Jul) whose `-lshadow` twins are LIVING
# books — one of them the live pair's control arm. Membership is `in`, i.e.
# string equality, so the bare name excludes nothing living; any future rewrite
# to prefix/suffix matching here would silently retire three healthy books.
# Pinned in `tests/autonomy/test_review_retired_roster.py`.
# [2026-08-13 (ma)] the live pair moved: 🙏 Avo Maria took the Taker's slot
# (same service/keys/sub-account). The review's real-money sweep must cover
# the CURRENT live pair — leaving the retired row here would send every
# future audit to a dead row and past the new live book (the exact stale-rule
# shape the 22-Jul (ci) correction fixed in CLAUDE.md's audit-scope rule).
# [2026-08-14 (mo)] IMPORTED, not re-declared — `fleet_books` is the one
# declaration, and `audit_live_roster` fails the build when it disagrees with
# the live feed. This tuple and `ROW_ENTRY` below were BOTH second copies of
# `audit_code_currency`'s, which is why the (ma) swap had to edit ten sites.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from fleet_books import DECLARED_LIVE, ROW_ENTRY   # noqa: E402

LIVE_ROWS = DECLARED_LIVE
# The `-lshadow` CONTROL arm of a row that is ALREADY LIVE is not a go-live
# candidate — it is the twin of a bot that already went. It also fails the
# premise twice over: while the experiment judge runs a candidate on it, the
# shadow arm is an EXPERIMENT arm, not a control (xp-judge, 15-Jul). Listing it
# as "passing the gates" invites promoting a book that is already promoted.
# NOTE the SUFFIX-only rewrite. `str.replace` is global, and the Farmer's live
# row is `perps-funding-lighter-lighter` — two occurrences — so a bare
# `.replace("-lighter","-lshadow")` yields `perps-funding-lshadow-lshadow`,
# a row that does not exist, and the real twin sails through the gate scan.
def shadow_twin(row):
    """The `-lshadow` CONTROL arm of a live row — the ONE owner of that rewrite.

    [2026-08-26 daily review] Made a function because both consumers used to
    hand-type their shadow arm and BOTH had rotted the moment the live roster
    changed: `live_shadow_gap`'s shadow defaulted to the FARMER's twin while
    its live side is `LIVE_ROWS[0]`, so after 💸 the Farmer's live arm retired
    ((ta)) and 🙏 Avo/🔮 Georgia/👩 mum took the sub-accounts, the review was
    differencing AVO'S LIVE ARM against THE FARMER'S SHADOW BOOK and printing
    it as "Farmer live-vs-shadow ... no divergence". A cross-book subtraction
    cannot detect a live book drifting from its control, and it reported an
    all-clear while doing it. Deriving the twin makes that unrepresentable.
    """
    return (row[:-len("-lighter")] + "-lshadow") if row.endswith("-lighter") else row


# The `-lshadow` CONTROL arm of a row that is ALREADY LIVE is not a go-live
# candidate — see the note above.
LIVE_TWINS = frozenset(shadow_twin(r) for r in LIVE_ROWS)

# [2026-08-02] The entry file whose build id each graded row stamps, so the
# review can compare a RUNNING container against the repo. See
# `head_drift_line` for why a live/shadow comparison alone cannot do this.
# [2026-08-14 (mo)] Now imported above from `fleet_books` — this was a SUBSET
# copy of `audit_code_currency`'s map, and a subset copy is the worse kind: it
# stays green while silently covering fewer rows than the guard it mirrors.


# ---------------------------------------------------------------------------
# pure helpers (covered by --selftest)
# ---------------------------------------------------------------------------
def ledger_drawdown(pnls, start=START_EQUITY):
    """Max peak-to-trough drawdown FRACTION (<=0) of the ledger equity curve.

    `bot_pnl.extra.max_drawdown` is unpopulated fleet-wide, so the <15% go-live
    gate is unverifiable from the row (noted as a caveat in the 24-Jul review
    and never closed). The durable ledger CAN answer it: equity starts at the
    book's $1,000 and walks the closed-trade P&Ls in close order.

    Returns 0.0 for an empty/never-underwater curve — never None, so a caller
    cannot silently treat "no data" as "passes the gate". The caller checks n.
    """
    eq = float(start)
    peak = eq
    worst = 0.0
    for p in pnls:
        eq += float(p or 0.0)
        if eq > peak:
            peak = eq
        if peak > 0:
            worst = min(worst, eq / peak - 1.0)
    return round(worst, 4)


def alert_key_kind(key):
    """Route an alert key to its verifier. Prefix match, longest first."""
    k = str(key or "")
    for prefix, kind in (("disloc:", "disloc"), ("census:", "census"),
                         ("factor-sample:", "factor"), ("veto:", "veto"),
                         ("live-shadow-gap", "live_shadow")):
        if k.startswith(prefix):
            return kind
    return "unknown"


def parse_disloc_msg(msg):
    """(max_bps, census_count) claimed by a disloc alert, or (None, None)."""
    m = re.search(r"([\d.]+)bps \(census (\d+)", str(msg or ""))
    return (float(m.group(1)), int(m.group(2))) if m else (None, None)


def tstat(vals):
    """One-sample t vs 0. None when undefined (n<2 or zero variance)."""
    v = [float(x) for x in vals if x is not None]
    if len(v) < 2:
        return None
    sd = statistics.stdev(v)
    if sd == 0:
        return None
    return round(statistics.mean(v) / (sd / len(v) ** 0.5), 2)


def gate_status(rows):
    """('pass'|'fail', reason, stats) for one book, per the CANONICAL gate.

    `rows` is [(pnl_pct, pnl_abs, closed_at_datetime)] oldest first — the shape
    `golive_readiness.stats` takes. All bars (>=30d, >=30 closes, mean>0, t>=2,
    both halves +, maxDD<15%) come from the imported grader; this function only
    formats. Win rate is REPORTED and is not a bar (CHANGELOG (fk)).
    """
    s = stats(rows, book_usd=START_EQUITY)
    passes, fails = grade(s)
    if s.get("n", 0) < 2:
        return "fail", s.get("why", "ungradeable"), s
    why = (f"n={s['n']}, {s['days']:.1f}d, mean {100*s['mean_pct']:+.3f}%, "
           f"t={s['t']:.2f}, halves {s['h1']:+.2f}/{s['h2']:+.2f}, "
           f"WR {s['win_rate']:.1%} (reported, not a bar), "
           f"maxDD {100*(s['max_dd_frac'] or 0):.1f}%")
    return ("pass", why, s) if passes else ("fail", "; ".join(fails), s)


def ledger_pooled(cur, bot):
    """[(pair, hours)] where this book's ledger proves a SECOND WRITER.

    Delegates the detection to `golive_readiness.same_pair_overlaps` — the same
    function `audit_ledger_integrity` uses, so the review and the guard can
    never disagree about whether a book's record is clean. One process cannot
    hold two positions in one symbol (every Lighter book keys `positions` by
    symbol), so an overlap is structural proof, not a heuristic.

    Fail-SOFT and fail-OPEN on a bad read: returns [] rather than raising, so a
    timestamp that will not cast cannot cost the whole section. Note both
    columns are TEXT in four formats — the cast is mandatory (see CA).
    """
    try:
        cur.execute(f"""SELECT pair, opened_at::timestamptz, {CA}
                          FROM paper_trades
                         WHERE bot=%s AND pnl_abs IS NOT NULL
                           AND opened_at IS NOT NULL AND closed_at IS NOT NULL""",
                    (bot,))
        eps = [(p, o, c) for p, o, c in cur.fetchall() if p and o and c]
    except Exception:
        return []
    return same_pair_overlaps(eps)


def blocking_bars(s):
    """The canonical bar names this book FAILS, sorted. Never prose.

    [2026-07-30] Derived from `golive_readiness.bar_map`, not from parsing
    `grade`'s reason string. The first cut of this function did parse the
    string (`why.startswith("window ")`) and was obsolete within hours: (hl)
    landed `bar_map` for exactly this reason — its own docstring says
    "published rather than re-derived ... prose is exactly what drifts".

    Deriving it means a bar ADDED, RENAMED or REDEFINED upstream reaches this
    review automatically instead of silently failing to match a prefix. The
    maxdd bar's definition is under active change ((hl): realised-only today,
    MTM once ~30d of `bot_state_history` accrues) — that change must not need
    an edit here.
    """
    return tuple(sorted(k for k, ok in bar_map(s).items() if not ok))


def near_miss_eta(s, first_close=None, now=None):
    """Days until the WINDOW bar clears, when it is the ONLY failing bar.

    Returns None unless the book has cleared every EVIDENCE bar — a book that
    is also thin, or noisy, is not "N days from ready" and must never read as
    though it were.

    [2026-08-06 (la)] DELEGATES TO `gate_horizon`; it no longer owns the
    arithmetic. It used to compute `GOLIVE_MIN_DAYS - s["days"]` off the
    CLOSE SPAN while the 🔭 line beside it projected off the era AGE, so the
    same report answered "how far to the window bar" twice, differently, for
    the same book — (hj)'s second-copy-of-a-rule at two-line range. Measured
    on a stalled 5/6 book: this said "~2.0d away" while the horizon said
    today. The grader is the one owner; a dark/parameterless call falls back
    to the old span arithmetic so this can never lose the line entirely."""
    if s.get("n", 0) < 2 or blocking_bars(s) != ("window",):
        return None
    try:
        hz = gate_horizon(s, first_close=first_close, now=now)
        d = hz.get("eta_days")
        if isinstance(d, (int, float)):
            return d
    except Exception:      # noqa: BLE001 — never lose the line to a projection
        pass
    return GOLIVE_MIN_DAYS - s["days"]


def risk_line(st):
    """Render the fleet-risk light against the bounds the VETO enforces.

    [2026-08-01] Extracted from `scan_new_evidence` so it can be tested against
    a payload `fleet_risk` itself builds, rather than by duplicating the
    f-string in a test ((hw): "an inline block is only ever testable by
    duplication").

    INCIDENT this fixes. The line read `"<gross> gross vs long budget <N>"`.
    `gross` is longs+shorts; the enforced veto compares `long_positions` to
    `LONG_BUDGET` (`fleet_risk.light_for(fleet_long, LONG_BUDGET)`, and
    `fleet_bus` reads `long_positions`). Measured on the live payload the
    morning it was caught: gross 25 / long_positions 19 / long_budget 20, i.e.
    the review printed the fleet as five longs OVER a cap it was one under.
    An error in the ALARMING direction, on the exact ceiling this review is
    supposed to watch for REACH — and the 31-Jul report had already carried
    the same shape ("21 gross vs long budget 20"). Each side is now shown
    against its own bound; `gross` is retained as context, never as a
    comparand.
    """
    dd7 = st.get("fleet_dd_7d")
    lp, lb = st.get("long_positions"), st.get("long_budget")
    sp, sb = st.get("short_positions"), st.get("short_budget")
    return (f"🚦 fleet-risk light {st.get('light')} — longs {lp}/{lb}, "
            f"shorts {sp}/{sb} (gross {st.get('gross')}); "
            f"7d DD {float(dd7 or 0):.2%}, clip_scale {st.get('clip_scale')}"
            + ("  ** DD GOVERNOR BEYOND -5% **" if (dd7 or 0) <= -0.05 else ""))


def long_budget_headroom(st):
    """-> longs still admissible before the L2 veto refuses, or None if unknown.

    Fail-CLOSED on a missing/unparseable count: `None` means "cannot say", and
    a caller must never read that as headroom. Never negative.
    """
    try:
        lp, lb = int(st["long_positions"]), int(st["long_budget"])
    except (KeyError, TypeError, ValueError):
        return None
    return max(0, lb - lp)


def long_budget_occupancy(risk, alloc=None, top=4):
    """-> [(book, longs, share, claim)] holding the fleet long budget, biggest first.

    [2026-08-01] A ceiling nobody can attribute is not actionable. The review
    reported `longs 18/20` for weeks without ever saying WHO held the 18 —
    while `fleet-risk.by_bot` had carried the breakdown the whole time.

    Joined to `fleet-allocation`'s per-book claim, because occupancy only means
    something against evidence. Measured the day this shipped:

        crypto-trend-daily   6 longs  33.3%   no claim, ZERO closes ever
        freqtrade-mum        4 longs  22.2%   no claim
        freqtrade-avo-maria  4 longs  22.2%   claim 0.0 (n=5)
        freqtrade-dad        2 longs  11.1%   claim 0.0 (n=10)
        crypto-swing-daily   2 longs  11.1%   claim 0.0 (n=1)

    i.e. **100% of the long budget held by books with no measured claim**, a
    third of it by one book that has never closed a trade — while both LIVE
    real-money books held only shorts and so never competed for it at all.
    That reframes the L2 ceiling: the constraint is not that the budget is too
    small, it is what the budget is parked in.

    `claim` is None when the book is absent from the allocation payload (a
    dark organ, or a book with too few closes to score) — never 0.0, because
    "not scored" and "scored at zero" are different facts and conflating them
    would let a dark organ read as a fleet with no claims anywhere.
    """
    by_bot = (risk or {}).get("by_bot") or {}
    total = (risk or {}).get("long_positions") or 0
    books = (alloc or {}).get("books") or {}
    rows = []
    for base, d in by_bot.items():
        n_long = (d or {}).get("long") or 0
        if not n_long:
            continue
        # fleet-risk keys by BARE base; the allocation organ keys by ROW.
        entry = books.get(base) or books.get(f"{base}-lshadow") or {}
        rows.append((base, n_long, (n_long / total) if total else None,
                     entry.get("claim")))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows[:top]


def _assert_write_target(key):
    """The single gate on the single UPSERT. Refuses anything but the review."""
    if key != REVIEW_KEY:
        raise RuntimeError(
            f"refusing to write bot_state[{key!r}] — this script may only "
            f"write {REVIEW_KEY!r} (see module docstring, WRITE SCOPE)")
    return key


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------
def connect():
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        sys.exit("no DATABASE_URL/DATABASE_PUBLIC_URL — get it with:\n"
                 "  railway variables --service Postgres --kv | grep DATABASE_PUBLIC_URL")
    import psycopg2
    return psycopg2.connect(url)


def load_state(cur, key):
    cur.execute("SELECT state, updated_at FROM bot_state WHERE bot=%s", (key,))
    r = cur.fetchone()
    if not r:
        return None, None
    s, u = r
    return (json.loads(s) if isinstance(s, str) else s), u


def census_publisher_age_h(updated_at, now):
    """Hours since the dislocation census was last WRITTEN, or None.

    None means "cannot tell" — a missing row, a null stamp, or anything
    unparseable. Kept distinct from a number so the caller can fail SAFE
    (see `census_is_dark`) instead of treating an unknown age as fresh.
    """
    if updated_at is None:
        return None
    try:
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=dt.timezone.utc)
        return (now - updated_at).total_seconds() / 3600.0
    except Exception:  # noqa: BLE001
        return None


def census_is_dark(age_h):
    """True when the census may no longer be read as current.

    FAIL-SAFE (age unknown => dark): an unreadable stamp is exactly the state
    a frozen publisher presents, and I1's whole lesson is that content cannot
    distinguish the two. Marking a live alert `stale` costs one day of a
    re-verifiable verdict; marking a dead one `active` is what this closes.
    """
    return age_h is None or age_h > CENSUS_STALE_H


def census_dark_note(age_h):
    """The operator-facing reason, naming the object to act on (I8)."""
    age = "age unknown" if age_h is None else f"{age_h:.1f}h stale"
    return (f"dislocation census publisher `lighter-dislocation-lshadow` is "
            f"{age} (> {CENSUS_STALE_H:.0f}h) — 🧲 Snap Back was retired 4-Aug "
            f"(jh), so this alert is frozen history, not a live condition")


class Section:
    """Fail-soft section wrapper — a throwing section costs its own output only.

    This is the whole reason the 24-27 Jul runs published nothing: one raising
    query took the process down with the verdicts already in hand.
    """

    def __init__(self, errors, name):
        self.errors, self.name = errors, name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.errors.append(f"{self.name}: {type(exc).__name__}: {exc}")
            print(f"  !! section {self.name} FAILED (soft): {exc}", file=sys.stderr)
        return True     # suppress


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
def verify_alerts(cur, errors):
    """One verdict per distinct alert key in the last ALERT_WINDOW_D days."""
    verdicts = []
    alerts, _ = load_state(cur, ALERTS_KEY)
    if not alerts:
        errors.append("fleet-alerts: key missing or empty")
        return verdicts
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now.timestamp() - ALERT_WINDOW_D * 86400
    latest = {}
    for a in alerts.get("alerts") or []:
        if float(a.get("ts") or 0) < cutoff:
            continue
        k = a.get("key")
        if k not in latest or a["ts"] > latest[k]["ts"]:
            latest[k] = a

    census = {}
    census_age_h = None
    with Section(errors, "disloc-census"):
        # [I1] Read the publisher's OWN age BEFORE its content. `updated_at` is
        # the second return value and was previously discarded — see
        # CENSUS_STALE_H for the incident that cost.
        st, updated_at = load_state(cur, "lighter-dislocation-lshadow")
        census = (st or {}).get("census") or {}
        census_age_h = census_publisher_age_h(updated_at, now)

    census_dark = census_is_dark(census_age_h)

    for key, a in sorted(latest.items()):
        kind = alert_key_kind(key)
        try:
            # [I1] A dark publisher invalidates every verdict derived from its
            # payload, whatever the payload says. Both kinds below read the
            # SAME frozen `census` dict, so both are gated here rather than in
            # one branch — a check that covers one reader of a dead source and
            # not the other is the hole, not the fix.
            if census_dark and kind in ("disloc", "census"):
                verdicts.append((key, "stale", census_dark_note(census_age_h)))
                continue
            if kind == "disloc":
                sym = key.split(":", 1)[1]
                claim_bps, claim_n = parse_disloc_msg(a.get("msg"))
                v = census.get(sym)
                if not v:
                    verdicts.append((key, "stale",
                                     f"{sym} no longer in the dislocation census"))
                    continue
                last = dt.datetime.fromisoformat(v["last_iso"])
                age_h = (now - last).total_seconds() / 3600
                cnt, bps = v.get("count"), v.get("max_bps")
                if age_h > 24 * ALERT_WINDOW_D:
                    verdicts.append((key, "stale",
                                     f"last {sym} event {age_h/24:.1f}d ago"))
                else:
                    verdicts.append((key, "active",
                                     f"census {cnt} ev / {bps:.0f}bps"
                                     f" (alert {claim_n}), last event {age_h:.1f}h ago"
                                     f", {v.get('count_enter', 0)} entries"))
            elif kind == "census":
                total = sum(c.get("count", 0) for c in census.values())
                thresh = int(key.split(":", 1)[1] or 0)
                verdicts.append((key, "active" if total >= thresh else "resolved",
                                 f"census now {total} events across {len(census)} books"
                                 f" (threshold {thresh})"))
            elif kind == "factor":
                cur.execute("""
                    SELECT count(*), sum(CASE WHEN p.pnl_abs>0 THEN 1 ELSE 0 END)
                      FROM venue_orders v
                      JOIN paper_trades p
                        ON p.bot=v.bot AND p.pair=v.coin
                       AND abs(extract(epoch FROM p.opened_at::timestamptz - v.at)) < 900
                     WHERE v.raw->>'leg'='open' AND v.raw ? 'mctx'
                       AND p.pnl_abs IS NOT NULL""")
                n, w = cur.fetchone()
                bucket = int(key.split(":", 1)[1] or 0)
                verdicts.append((key, "active" if (n or 0) // 30 == bucket else "resolved",
                                 f"joined decision+context dataset at {n} closes"
                                 f" ({(w or 0)/n:.0%} win), bucket {(n or 0)//30}"))
            elif kind == "veto":
                st, _ = load_state(cur, "coin-vetoes")
                coins = (st or {}).get("coins") or {}
                sym = key.split(":", 1)[1]
                verdicts.append((key, "active" if sym in coins else "resolved",
                                 coins.get(sym, f"{sym} no longer vetoed")))
            elif kind == "live_shadow":
                gap = live_shadow_gap(cur)
                verdicts.append((key, "resolved" if abs(gap["gap_pp"]) < 2.0 else "active",
                                 f"per-trade gap {gap['gap_pp']:+.3f}pp "
                                 f"(live {gap['live_pct']:+.3f}% n={gap['live_n']} vs "
                                 f"shadow {gap['shadow_pct']:+.3f}% n={gap['shadow_n']})"))
            else:
                verdicts.append((key, "active",
                                 f"no verifier for this key shape — {a.get('msg','')[:120]}"))
        except Exception as e:          # one bad key must not cost the rest
            errors.append(f"verify {key}: {type(e).__name__}: {e}")
            verdicts.append((key, "active", f"verification failed: {type(e).__name__}"))
    return verdicts


def live_shadow_gap(cur, live, shadow=None, days=14):
    """Per-trade pnl_pct gap. Per-trade, NEVER equity — the arms hold different
    capital ($100 live vs $1,000 shadow), so an equity-% gap compares nothing.

    `shadow` DEFAULTS TO THIS ROW'S OWN TWIN and must never be another book's
    (see `shadow_twin`) — a cross-book difference is not a divergence signal.
    """
    shadow = shadow or shadow_twin(live)
    if shadow == live:
        raise ValueError(f"{live}: no distinct shadow twin")
    out = {}
    for role, bot in (("live", live), ("shadow", shadow)):
        cur.execute(f"""SELECT count(*), avg(pnl_pct)
                          FROM paper_trades
                         WHERE bot=%s AND pnl_abs IS NOT NULL
                           AND {CA} > now() - interval '%s days'""",
                    (bot, days))
        n, avg = cur.fetchone()
        out[f"{role}_n"] = n or 0
        out[f"{role}_pct"] = float(avg or 0.0) * 100.0
    out["gap_pp"] = out["live_pct"] - out["shadow_pct"]
    return out


def scan_new_evidence(cur, errors):
    """Evidence the in-fleet evaluator may have missed."""
    items = []

    with Section(errors, "taker-lenses"):
        cur.execute(f"""SELECT split_part(reason,'_',1) AS lens, count(*),
                               sum(pnl_abs), sum(CASE WHEN pnl_abs>0 THEN 1 ELSE 0 END)
                          FROM paper_trades
                         WHERE bot='lighter-ticket-taker-lshadow' AND pnl_abs IS NOT NULL
                         GROUP BY 1 HAVING count(*) >= 10 ORDER BY 2 DESC""")
        for lens, n, net, w in cur.fetchall():
            cur.execute("""SELECT pnl_abs FROM paper_trades
                            WHERE bot='lighter-ticket-taker-lshadow'
                              AND split_part(reason,'_',1)=%s AND pnl_abs IS NOT NULL""",
                        (lens,))
            t = tstat([r[0] for r in cur.fetchall()])
            items.append(f"🎫 shadow lens '{lens}' at n={n} (≥10): net ${float(net):+.2f}, "
                         f"WR {w/n:.0%}, t={t} — {'significant' if t and abs(t) >= 2 else 'noise'}")

    with Section(errors, "live-rows"):
        for bot in LIVE_ROWS:
            cur.execute("""SELECT split_part(reason,'_',1), count(*), sum(pnl_abs)
                             FROM paper_trades WHERE bot=%s AND pnl_abs IS NOT NULL
                            GROUP BY 1 ORDER BY 2 DESC""", (bot,))
            by_lens = [(r[0], r[1], round(float(r[2]), 2)) for r in cur.fetchall()]
            if by_lens:
                tot_n = sum(r[1] for r in by_lens)
                tot = sum(r[2] for r in by_lens)
                items.append(f"💰 LIVE {bot}: n={tot_n}, net ${tot:+.2f} — by lens {by_lens}")

    with Section(errors, "golive-gates"):
        cur.execute(f"""SELECT bot, count(*) FROM paper_trades
                         WHERE pnl_abs IS NOT NULL
                         GROUP BY 1 HAVING count(*) >= {CANDIDATE_MIN_CLOSES}
                         ORDER BY 2 DESC""")
        cands = [r[0] for r in cur.fetchall()]
        passers, near = [], []
        horizon_lines, horizon_tally = [], {}
        # [2026-08-16 (nk)] Which sleeves does each book still run? Straight
        # from the books' OWN bot_pnl payloads, the same source the grader
        # reads — the book declares, both consumers derive. Fail-OPEN: an
        # unreadable summary leaves this empty, which excludes NOTHING and
        # grades exactly as before rather than silently shrinking a sample.
        _sleeve_retired = {}
        try:
            cur.execute("SELECT bot, extra FROM bot_pnl")
            for _b, _ex in cur.fetchall():
                _rs = retired_sleeves(_ex)
                if _rs:
                    _sleeve_retired[str(_b)] = _rs
        except Exception:      # noqa: BLE001 — a lost filter, never a lost report
            _sleeve_retired = {}
        for bot in cands:
            if bot in RETIRED or bot in LIVE_ROWS or bot in LIVE_TWINS:
                continue
            # The grader's own shape: (pnl_pct, pnl_abs, closed_at) oldest
            # first, plus the OPEN stamp the era is keyed on. `opened_at` is
            # read RAW (TEXT), not cast: the cast can raise on one bad row and
            # take the whole section down with it, whereas `era_rows` fails
            # CLOSED per row — an unreadable open stamp drops that trade rather
            # than the report.
            # [(jf)] `extra` rides at [4] for the same (hq) reason the open
            # stamp rides at [3]: `era_rows` now derives the LATEST policy
            # boundary from the close's own extra.policy stamp, and a review
            # that selects everything BUT the stamp would grade a different
            # sample than the grader — the exact divergence (hq) closed.
            # [(nk)] `reason` rides at [5] so the retired-SLEEVE precondition
            # runs here too. Selecting the era stamp but not the sleeve tag
            # would re-open (hq) on the other axis: same bars, same era, a
            # different sample.
            cur.execute(f"""SELECT pnl_pct, pnl_abs, {CA}, opened_at, extra,
                                   reason
                              FROM paper_trades
                             WHERE bot=%s AND pnl_abs IS NOT NULL AND closed_at IS NOT NULL
                             ORDER BY {CA}""", (bot,))
            quads = cur.fetchall()
            # [2026-08-16 (nk)] COMPOSITION BEFORE TIME — the same order the
            # grader runs. A retired sleeve's trades are not this book's
            # record, so they leave before the era boundary is derived.
            # `retired_sleeves` reads the BOOK'S OWN published declaration
            # (`bot_pnl.extra.sleeves.<name>.retired`), so nothing is listed
            # here; a dark/absent payload excludes nothing and grades as
            # before. Measured on 🎸 Barnes: 49 of 58 closes belonged to the
            # `xsect` sleeve `(nf)` retired, and the pooled reading published a
            # confident `unreachable` about a two-sleeve book that no longer
            # exists.
            # NOTE the tag shape: this table stores `reason`
            # (`'<side>-<sleeve>_<exit>'`) while the grader reads the
            # normalised `enter_tag` (`'<side>-<sleeve>'`). `sleeve_of` splits
            # on the first hyphen, so the trailing `_<exit>` would ride along —
            # strip it here, at the one place the raw column is read.
            quads = [q[:5] + ((str(q[5]).split("_", 1)[0]
                               if q[5] is not None else None),)
                     for q in quads]
            quads, _dropped_sleeves = drop_retired_sleeves(
                quads, _sleeve_retired.get(bot))
            # [(hc)/(hq)] THE ERA IS A PRECONDITION IN FRONT OF THE SIX BARS.
            # Grade the book as it RUNS TODAY, never its whole retained ledger.
            # `era_rows` is golive_readiness's — the same selection the
            # canonical grader runs — so review and grader cannot disagree
            # about the sample any more than about the bars.
            rows, rows_all, era_iso = era_rows(bot, quads)
            status, why, s = gate_status(rows)
            # [2026-08-06 (ks)] GATE HORIZON — the hand calendar, computed.
            # The canonical `gate_horizon` (one owner, same doctrine as
            # bar_map/era_rows above: the review FORMATS, it never re-derives).
            # This section's sample is realised-only by its own declared
            # caveat, and the horizon inherits that basis.
            try:
                _era_ep = None
                if era_iso:
                    from datetime import datetime as _hdt, timezone as _htz
                    _d = _hdt.fromisoformat(str(era_iso))
                    if _d.tzinfo is None:
                        _d = _d.replace(tzinfo=_htz.utc)
                    _era_ep = _d.timestamp()
                hz = gate_horizon(s, first_close=(rows[0][2] if rows else None),
                                  era_epoch=_era_ep)
            except Exception:      # noqa: BLE001 — a lost projection, never a lost report
                hz = {}
            if hz.get("verdict") == "on_track" and hz.get("eta"):
                horizon_lines.append(
                    f"{bot} → {hz['eta']}"
                    + ("~" if hz.get("eta_conf") == "low" else "")
                    + f" ({hz.get('binding')})"
                    + (f" FLOOR:{','.join(hz['blockers'])}" if hz.get("blockers")
                       else ""))
            elif hz.get("verdict") == "no_rate" and hz.get("eta"):
                horizon_lines.append(f"{bot} ≥ {hz['eta']} (window floor)")
            elif hz.get("verdict") in ("unreachable", "undecidable",
                                       "unprojectable"):
                # [(la)] NAME THE BOOKS (I8: a detector must name the object
                # the operator can act on). This tallied COUNTS — "unreachable
                # @trend: 6" — for exactly the two verdicts whose stated
                # purpose is a keep-or-retire call, so the daily report was
                # strictly worse than the dashboard, which names them.
                # `unprojectable` joins because it fell through silently: the
                # 5/6 book nearest the gate appeared in neither list.
                horizon_tally.setdefault(hz["verdict"], []).append(bot)
            # [(hf)/(hi)] A grade is only as good as the ledger under it. If two
            # processes wrote this book's rows, its n/t describe a POOLED record
            # and no promotion may rest on them. Measured 30-Jul: 🌾 carry — the
            # book closest to the bar — carries 7 same-pair overlaps, deepest
            # 9.14h. Surfaced HERE rather than left to a separate guard nobody
            # runs on review day.
            pooled = ledger_pooled(cur, bot)
            flag = ""
            if era_iso:
                # Stated on EVERY era-scoped line, whatever the verdict, and
                # the all-time count is published BESIDE it so nothing is
                # hidden — the same contract golive_readiness prints. An era
                # that only announces itself when it changes the answer is a
                # footnote; it is the definition of the sample.
                flag += (f" [era {era_iso}: {s.get('n', 0)} of "
                         f"{len(rows_all)} closes count]")
            if pooled:
                flag = (f" ⛔ POOLED LEDGER: {len(pooled)} same-pair overlap(s), "
                        f"deepest {pooled[0][1]:.2f}h on {pooled[0][0]} — a second "
                        f"writer; this grade is not one book's record")
            if status == "pass":
                passers.append(f"{bot} ({why}){flag}")
                continue
            # A book that clears every EVIDENCE bar and waits only on the
            # window is the operator's lead time — ~N days from a decision.
            # [(la)] Pass the first in-era close so the delegation to
            # `gate_horizon` uses the AGE basis — without it the helper falls
            # back to the span arithmetic it was extracted from.
            eta = near_miss_eta(s, first_close=(rows[0][2] if rows else None))
            if eta is not None:
                p = book_payload(s)
                near.append(f"{bot} (t={p['t']}, n={p['n']}, {p['days']}d, "
                            f"{p['bars_passed']}/{len(BAR_NAMES)} bars — only "
                            f"'window' outstanding, ~{eta:.1f}d away){flag}")
        # The bar LIST comes from the grader, so a bar added or renamed upstream
        # shows up here without an edit (the (hl) bar_map doctrine).
        items.append("🚦 go-live gates (CANONICAL grader golive_readiness — bars: "
                     + ", ".join(BAR_NAMES) +
                     "; win rate reported, NOT a bar; retired, already-live and "
                     "live-twin rows excluded): "
                     f"{'; '.join(passers) if passers else 'NO new candidate'}")
        if near:
            items.append("⏳ waiting only on the window bar: " + "; ".join(near))
        # [(ks)] The computed calendar. OPERATOR_QUEUE item 5's dates were
        # hand-typed prose and had already rotted (the Farmer's "~16-Aug"
        # matches its pre-(jf) era); these are derived from the ledger by the
        # canonical grader each run. Projections at the current measured
        # trajectory — floors, never promises.
        # [(la)] EMITTED WHENEVER THERE ARE CANDIDATES, not only when something
        # projected. The old `if horizon_lines or horizon_tally` dropped the
        # whole item when every candidate fell through — the same dark-reads-
        # as-clean ambiguity (kw) closed one file over.
        if cands:
            _tal = "; ".join(f"{k}@trend: {', '.join(sorted(v))}"
                             for k, v in sorted(horizon_tally.items()))
            items.append("🔭 gate horizon (computed at trajectory, (ks)): "
                         + ("; ".join(horizon_lines) if horizon_lines
                            else "no projectable candidate")
                         + (f" · {_tal}" if _tal else ""))
        # [(hl)] The maxdd bar is measured on REALISED closed P&L only, so a
        # book that is usually IN a position has drawdown the bar cannot see —
        # measured on 📊 Index Rider, realised 9.9-10.7% vs true MTM 15.6-17.4%,
        # i.e. the two definitions disagree about the VERDICT. `snapshot_equity`
        # started accruing an MTM series on 30-Jul; until ~30d exists the bar
        # stays realised-only. State it every run rather than let a reader take
        # a maxdd pass as an MTM pass.
        if passers or near:
            items.append("⚠️ maxdd caveat ((hl)): the bar above is REALISED-only; "
                         "MTM drawdown can be materially larger and can flip the "
                         "verdict. Re-grade any candidate under MTM once "
                         "bot_state_history '<bot>:equity' has ~30d.")

    with Section(errors, "fleet-risk"):
        st, _ = load_state(cur, "fleet-risk")
        if st:
            items.append(risk_line(st))
            head = long_budget_headroom(st)
            if head is not None and head <= 2:
                items.append(f"🚦 REACH: only {head} long slot(s) left under the "
                             f"L2 veto ({st.get('long_positions')}/"
                             f"{st.get('long_budget')}) — at 0 the NEXT long is "
                             "refused fleet-wide regardless of its edge")
                # WHO holds it. A ceiling with no attribution cannot be acted
                # on, and the breakdown was already in the payload.
                al, _ = load_state(cur, "fleet-allocation")
                occ = long_budget_occupancy(st, al)
                if occ:
                    parts = []
                    for base, n_long, share, claim in occ:
                        cl = ("no claim" if not claim else f"claim {claim:.4f}")
                        parts.append(f"{base} {n_long}"
                                     + (f" ({share:.0%})" if share else "")
                                     + f" {cl}")
                    unclaimed = sum(n for _, n, _, c in occ if not c)
                    items.append("🚦 LONG BUDGET HELD BY: " + "; ".join(parts)
                                 + f" — {unclaimed} of the top "
                                 f"{sum(n for _, n, _, _ in occ)} slots are held "
                                 "by books with NO measured claim")

    with Section(errors, "live-shadow"):
        # EVERY live row against ITS OWN twin — never a hand-typed pair, and
        # never row[0] alone: after the (ta)/(tb) swap the fleet has THREE
        # live books, and a single hardcoded line both compared the wrong
        # books and left two real-money rows unwatched.
        for live in DECLARED_LIVE:
            g = live_shadow_gap(cur, live)
            if not g["live_n"] or not g["shadow_n"]:
                items.append(f"📏 {live} live-vs-shadow: insufficient paired "
                             f"closes (live n={g['live_n']}, "
                             f"shadow n={g['shadow_n']}) — no verdict")
                continue
            items.append(f"📏 {live} live-vs-shadow per-trade gap "
                         f"{g['gap_pp']:+.3f}pp "
                         f"(live {g['live_pct']:+.3f}% n={g['live_n']}, "
                         f"shadow {g['shadow_pct']:+.3f}% n={g['shadow_n']}) — "
                         f"{'DIVERGING' if abs(g['gap_pp']) >= 2 else 'no divergence'}")

    with Section(errors, "arm-drift"):
        # [2026-08-13 (ma)] the Taker pair -> the Avo pair (slot swap). The
        # Avo arms deliberately run DIFFERENT entry files (live runner vs the
        # family container) so their build ids will always differ — that is
        # the (fd) FILE-SET shape, not drift; arm_drift_line's build_n field
        # is what keeps that readable.
        # [2026-08-26] DERIVED from the live roster, not hand-typed. The old
        # literal pair list still named the RETIRED Farmer arms and covered
        # only Avo, so 🔮 Georgia and 👩 mum — both carrying real money since
        # (tb)/(te) — had no arm-drift check at all.
        _pairs = [(r, shadow_twin(r)) for r in DECLARED_LIVE]
        _rows = sorted({x for pair in _pairs for x in pair})
        cur.execute("""SELECT bot, extra->>'build', extra->>'build_n' FROM bot_pnl
                        WHERE bot = ANY(%s)""", (_rows,))
        b = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for live, shadow in _pairs:
            items.append(arm_drift_line(live, b.get(live), b.get(shadow)))

    with Section(errors, "head-drift"):
        # Same rows, different question: is the CONTAINER carrying what has
        # been merged? `arm-drift` above cannot answer it — two arms that are
        # both stale agree with each other. See `head_drift_line`.
        heads = {}
        for row, entry in ROW_ENTRY.items():
            if entry not in heads:
                heads[entry] = repo_build(entry)
            items.append(head_drift_line(
                row, b.get(row), heads[entry], live_money=row in LIVE_ROWS))
    return [i for i in items if i]


def arm_drift_line(name, live, shadow):
    """-> the 🧬 live-vs-shadow build line, or None when either arm is unstamped.

    [2026-08-01] Reads `build_n` beside `build`, per (fd). `build_compute`
    hashes only the `_BUILD_SHARED` names that EXIST in the image, so the SAME
    source tree stamps DIFFERENT ids in two images carrying different COPY
    sets — measured once already, when `family-lighter-shadow` published a
    14-file id against the repo's 15-file id and read as "the deploy never
    landed". The live arms run from their own images, so this comparison is
    exactly where that hazard lives, and this line previously compared the
    digest ALONE — it could not tell "the control arm is running different
    code" (a real threat to the control) from "the two images carry different
    files" (expected, and no threat at all).

    Verified on the live payload the day it shipped: both taker arms report
    `build_n=15`, so the differing digest there IS genuine code drift.
    """
    bl, nl = live or (None, None)
    bs, ns = shadow or (None, None)
    if not (bl and bs):
        return None
    if bl == bs:
        return f"🧬 {name} arms AGREE: live {bl} vs shadow {bs} (n={nl})"
    if nl != ns:
        return (f"🧬 {name} arms differ on FILE SET, not necessarily code: "
                f"live {bl} (n={nl}) vs shadow {bs} (n={ns}) — a different "
                "count means different COPY sets ((fd)); compare against each "
                "image's own Dockerfile before calling it drift")
    # [2026-08-06] The CONSEQUENCE is not derivable from the stamps, so it is
    # no longer asserted. This is (ke)'s category error one function down: that
    # entry fixed `head_drift_line` for stamp-vs-repo and explicitly left this
    # line — *"it does not yet CLASSIFY inside the review"* — still asserting
    # "the shadow arm is not a clean control".
    #
    # MEASURED the morning this shipped: the two Taker arms drifted by exactly
    # two commits, (kh) and (ki). Neither touches `lighter_ticket_taker.py` —
    # the diff is `bot_pnl_store.py` (a PUBLISHER) and an additive `fleet_bus`
    # helper the taker never calls. The arms' trading logic was byte-identical,
    # so the control was sound and the line was wrong about the one thing it
    # asserted. The differing code still mattered, but for a different reason
    # (the live arm lacked the (kh) I5 fix), which is a DEPLOY question.
    #
    # A stamp difference is a FACT; whether it changes what the bot DOES is a
    # verdict only `audit_code_currency` can give (BEHIND-OWN = the gap changes
    # the bot's own entry file). State the fact, name the authority, stop.
    return (f"🧬 {name} arms DRIFT: live {bl} vs shadow {bs} (both n={nl}, so "
            "shared-module code differs, not the file set) — whether the arms' "
            "own logic differs is `scripts/audit_code_currency.py`'s call "
            "(BEHIND-OWN), not this line's; a shared-module-only gap leaves "
            "the control sound and is a deploy question")


def repo_build(entry):
    """-> (id, n_files) predicted for `entry` from THIS repo tree, or None.

    Fail-soft by contract: any failure returns None and the caller reports
    nothing. A drift claim must never rest on a prediction that did not run.

    THE ENTRY MUST EXIST, and that check is load-bearing rather than defensive.
    `build_compute` SILENTLY SKIPS a declared-but-absent name ((fd), deliberate
    — images carry different subsets), so a renamed or moved entry does not
    raise: it returns a confident id hashed over the SHARED SET ALONE. That
    prediction is wrong, and wrong in the direction that looks like data.
    """
    try:
        import bot_pnl_store
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = entry if os.path.isabs(entry) else os.path.join(root, entry)
        if not os.path.isfile(path):
            return None
        bid, n = bot_pnl_store.build_compute(path)
        return (bid, int(n)) if bid else None
    except Exception:
        return None


def head_drift_line(name, row, head, live_money=False):
    """-> the 🧬 container-vs-REPO build line, or None when it cannot tell.

    [2026-08-02] WHY THIS EXISTS, and why `arm_drift_line` above cannot do it:
    that check compares the LIVE arm to its SHADOW twin, so it answers "is the
    control arm running the same code?" and nothing else. **Under a total
    deploy failure of BOTH arms it reads `arms AGREE` — i.e. healthy** — which
    is this fleet's own recorded lesson that a convergent metric is not a
    health check: ask what it reads when everything is broken.

    MEASURED the day this shipped, which is why it is here. Both 💸 Farmer arms
    reported `705425a83422` while the repo predicted `30bf230bd5fb` at the same
    `build_n=15`. The review printed "🧬 Farmer arms AGREE" and its own
    `action_items` selftest pins that string as raising NO flag — so the LIVE
    REAL-MONEY Farmer sat ~3 days behind `bot_pnl_store` (missing `(hp)`'s
    `claim_writer`, `(ht)`'s service stamp, `(hr)`'s ledger quarantine) and the
    daily review called it healthy. `build_compute` existed the whole time and
    had NO running consumer anywhere in the tree: every verification against
    the repo in this fleet's history was hand-typed into a changelog entry.

    COMPARE `n` FIRST, per `(fd)`. `build_compute` hashes only the
    `_BUILD_SHARED` names that EXIST, so one tree stamps different ids in
    images carrying different COPY sets — that has already been mis-read once
    as "the deploy never landed". A differing count is reported as a FILE-SET
    difference and explicitly NOT as drift.

    It says "the repo tree", not "HEAD", on purpose: this predicts from the
    working tree, and `railway up` ships the desk too. Verifying which commit
    that tree is remains the reader's job.
    """
    br, nr = row or (None, None)
    if not br or not head:
        return None
    bh, nh = head
    tag = "REAL MONEY " if live_money else ""
    if br == bh:
        return f"🧬 {name} matches the repo tree: {br} (n={nr})"
    try:
        same_n = int(nr) == int(nh)
    except (TypeError, ValueError):
        same_n = False
    if not same_n:
        return (f"🧬 {name} differs from the repo on FILE SET, not necessarily "
                f"code: container {br} (n={nr}) vs repo {bh} (n={nh}) — a "
                "different count means a different COPY set ((fd)); check that "
                "image's own Dockerfile before calling it a stale deploy")
    # [2026-08-05 (ke)] UNCLASSIFIED, and it must not read as an alarm.
    # This function knows only that two hashes differ. It CANNOT tell
    # BEHIND-OWN (the gap changes the bot's own entry file — the only real
    # finding) from BEHIND-SHARED (a `_BUILD_SHARED` module moved, so every
    # image's stamp moved and no bot's logic changed) or DEFERRED (a live row
    # correctly waiting behind its marker gate).
    #
    # MEASURED 5-Aug: `(ka)` touched `fleet_tuning.py`, which is in
    # `_BUILD_SHARED`, so the stamp of EVERY image moved. This line fired on
    # BOTH real-money rows — tagged "REAL MONEY", escalated to ⚠️ ACTION —
    # while `scripts/audit_code_currency.py`, run minutes later on the same
    # fleet, classified both as CURRENT. Textbook BEHIND-SHARED.
    #
    # That tool's own header documents this as the cry-wolf trap and records
    # that it cost the 3-Aug review four false alarms; `(jc)` wired it into
    # the weekly workflow and left it unwired HERE. So the taxonomy had one
    # consumer and one ignorer, and the ignorer is the report a human reads
    # every morning. Now this states the fact and NAMES THE AUTHORITY instead
    # of asserting a verdict it cannot support.
    return (f"🧬 {name} stamp differs from the repo tree: container {br} vs "
            f"repo {bh} (both n={nr}, so not a file-set difference) — "
            "UNCLASSIFIED. A shared-module change moves every image's stamp "
            "without changing any bot's logic, so this is NOT yet a finding: "
            "run `scripts/audit_code_currency.py`, whose own-entry-file "
            "verdict is the only one that means the container is stale"
            + (f" [{tag.strip()} row]" if tag else ""))


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------
def upsert(conn, payload):
    key = _assert_write_target(REVIEW_KEY)
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO bot_state (bot, updated_at, state)
                       VALUES (%s, now(), %s)
                       ON CONFLICT (bot) DO UPDATE
                          SET updated_at=now(), state=EXCLUDED.state""",
                    (key, json.dumps(payload)))
    conn.commit()


def action_items(evidence):
    """The subset of evidence that demands a HUMAN decision today.

    [2026-07-30] This replaces a detector that was dead THREE ways: `act` was
    computed and never rendered; `"pass" in e` could never match, because the
    gate section emits `gate_status`'s REASON string and discards the literal
    "pass"; and `and` binds tighter than `or`, so the expression did not mean
    what it read as. Net effect: "a bot newly READY for live" — one of the four
    things the review is explicitly supposed to lead with — could not raise the
    flag under any data. Kept as a pure function so each trigger is testable.
    """
    out = []
    for e in evidence:
        if "GOVERNOR" in e or "DIVERGING" in e:
            out.append(e)
        elif "go-live gates" in e and "NO new candidate" not in e:
            out.append(e)
        elif "arms DIVERGE" in e or "DRIFT" in e:
            out.append(e)
        elif "BEHIND-OWN:" in e:
            # [2026-08-02] A container running less than what was merged is an
            # operator decision (which deploy, and whether it is marker-gated),
            # never something this review can act on. It gets its own branch
            # because this shares no token with "DRIFT" — matching it by
            # accident is how a detector silently stops firing.
            #
            # [2026-08-05 (ke)] NARROWED from "BEHIND THE REPO" to "BEHIND-OWN".
            # A bare stamp difference is not a finding — a shared-module change
            # moves every image's stamp — and escalating it put two FALSE
            # real-money alarms at the top of the 5-Aug report, contradicted by
            # `audit_code_currency` minutes later. Only that tool's BEHIND-OWN
            # verdict means the running container is stale in its own logic, so
            # only that word escalates here. `head_drift_line` no longer emits
            # the old phrase at all; this matches the classifier's vocabulary
            # so that piping its verdicts in keeps working.
            out.append(e)
    return out


def sydney_stamp(iso_utc):
    """'<Sydney local> (<UTC>)' — never a bare UTC time in operator-facing text.

    CLAUDE.md: *"ALWAYS give Eamon Sydney-local times ... Never hand him a bare
    UTC time"*, while fleet INTERNALS stay UTC. This report is the operator's
    surface, so it carries BOTH: Sydney to read, UTC to join against ledgers.

    [2026-08-14 (mj)] The FILENAME is Sydney-dated too — see `report_day`. It
    used to be UTC-dated on the argument that re-dating "would fork the report
    history mid-stream", and that argument was measured wrong the only way it
    could be: by destroying a report.

    Degrades to the UTC string it was given if the zone database is absent, so
    a slim container never loses the stamp altogether.
    """
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromisoformat(iso_utc).astimezone(
            ZoneInfo("Australia/Sydney"))
        return f"{t:%Y-%m-%d %H:%M} {t:%Z} (Sydney) · {iso_utc} UTC"
    except Exception:  # noqa: BLE001
        return iso_utc


def report_day(iso_utc):
    """The report's series key: the SYDNEY date of the run, not the UTC one.

    [2026-08-14 (mj)] THIS JOB RUNS AT 08:00 SYDNEY, WHICH IS THE PREVIOUS UTC
    DAY, SO A UTC-DATED FILENAME MADE EVERY MORNING RUN OVERWRITE THE PREVIOUS
    DAY'S REPORT. Measured, not theorised: the 14-Aug 08:00 AEST run resolved
    to `2026-08-13` and replaced the 13-Aug report — 31,223 bytes including its
    hand-written human layer — with its own 6,674-byte output. Every Sydney
    morning between 10:00 and midnight maps to the same UTC day as the previous
    Sydney evening, so the collision was structural, not a race.

    The old docstring defended UTC dating as "the series key" that re-dating
    "would fork the report history mid-stream". It forks nothing: yesterday's
    16:51 AEST run was 13-Aug in BOTH zones, so the existing filenames keep
    their meaning and the series simply becomes one file per operator-day —
    which is what a daily review on the operator's clock already was. Fleet
    INTERNALS stay UTC (`reviewed_at`, every ledger join); this is the
    operator's surface, and CLAUDE.md governs it.

    Fails back to the UTC date if the zone database is absent — a wrong-by-one
    filename beats no report.
    """
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromisoformat(iso_utc).astimezone(
            ZoneInfo("Australia/Sydney"))
        return f"{t:%Y-%m-%d}"
    except Exception:  # noqa: BLE001
        return str(iso_utc)[:10]


def preserve_existing_report(path):
    """Move an existing report aside instead of overwriting it. Returns the
    path it was preserved at, or None if there was nothing to preserve.

    The Sydney date above removes the once-a-day collision; this covers the
    other one, which also really happened (two runs on 6-Aug). The human layer
    is added to this file AFTER the script writes it, so a re-run silently
    destroys an operator's annotations — the single most expensive thing in the
    directory. Preserving costs one file; the alternative cost a day's report.

    Fail-OPEN: if the rename cannot be done the report is still written. Losing
    the backup is bad; losing today's review because a backup failed is worse.
    """
    if not os.path.exists(path):
        return None
    try:
        stamp = dt.datetime.fromtimestamp(
            os.path.getmtime(path), dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            stamp = stamp.astimezone(ZoneInfo("Australia/Sydney"))
        except Exception:  # noqa: BLE001
            pass
        base, ext = os.path.splitext(path)
        keep = f"{base}.superseded-{stamp:%H%M}{ext}"
        n = 0
        while os.path.exists(keep):
            n += 1
            keep = f"{base}.superseded-{stamp:%H%M}-{n}{ext}"
        os.rename(path, keep)
        return keep
    except OSError:
        return None


def write_report(payload, repo_root):
    day = report_day(payload["reviewed_at"])
    path = os.path.join(repo_root, "reports", f"evidence_review_{day}.md")
    kept = preserve_existing_report(path)
    act = action_items(payload["new_evidence"])
    lines = [f"# Evidence Review — {day}", "",
             f"_Reviewed {sydney_stamp(payload['reviewed_at'])}._", ""]
    if act:
        lines += ["## ⚠️ ACTION — needs an operator decision", ""]
        lines += [f"- {e}" for e in act] + [""]
    if payload.get("errors"):
        lines += ["## ⚠️ Sections that failed (review still published)", ""]
        lines += [f"- `{e}`" for e in payload["errors"]] + [""]
    lines += ["## Verdicts", "", "| Key | Status | Why |", "|-----|--------|-----|"]
    lines += [f"| {v['key']} | {v['status']} | {v['note']} |" for v in payload["verdicts"]]
    lines += ["", "## New evidence", ""]
    lines += [f"- {e}" for e in payload["new_evidence"]]
    lines += ["", "## Summary", "", payload["summary"], ""]
    if kept:
        # A silent rename is the same class of defect as the silent overwrite
        # it replaces: the operator must be able to find the annotations.
        lines += [f"_An earlier report for this day was preserved at "
                  f"`{os.path.basename(kept)}`._", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


def build_summary(verdicts, evidence):
    n = len(verdicts)
    act = sum(1 for v in verdicts if v["status"] == "active")
    res = sum(1 for v in verdicts if v["status"] == "resolved")
    stale = sum(1 for v in verdicts if v["status"] == "stale")
    urgent = [e for e in evidence if "GOVERNOR" in e or "DIVERGING" in e]
    return (f"{n} alert keys reviewed: {act} active, {res} resolved, {stale} stale. "
            + ("URGENT: " + "; ".join(urgent) if urgent
               else "No divergence and no drawdown-governor trigger.")
            + f" {len(evidence)} new-evidence items scanned.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errors = []
    conn = connect()
    with conn.cursor() as cur:
        verdicts = verify_alerts(cur, errors)
        evidence = scan_new_evidence(cur, errors)
    payload = {
        "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verdicts": [{"key": k, "status": s, "note": n} for k, s, n in verdicts],
        "new_evidence": evidence,
        "summary": build_summary([{"key": k, "status": s, "note": n}
                                  for k, s, n in verdicts], evidence),
        "errors": errors,
    }
    print(json.dumps(payload, indent=2))
    if args.dry_run:
        print("\n(--dry-run: nothing written)")
        return 0
    upsert(conn, payload)
    path = write_report(payload, repo_root)
    print(f"\nupserted bot_state['{REVIEW_KEY}'] + wrote {path}")
    if errors:
        print(f"WARNING: {len(errors)} section(s) failed soft — see payload.errors")
    return 0


# ---------------------------------------------------------------------------
def selftest():
    # [(ni)] THE RETIRED ROSTER IS DERIVED, NOT HAND-KEPT.
    # The floor must stay a strict SUBSET of the canonical declaration: the
    # moment it carries a name `LEGACY_BOTS` does not, it has become a second
    # authority that can disagree with the grader about which books are dead —
    # and the whole point of (ni) is that the hand copy drifted twelve books
    # behind while looking perfectly healthy.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as _lb
    except Exception:      # noqa: BLE001
        _lb = None
    if _lb is not None:
        _extra = _RETIRED_FLOOR - frozenset(_lb)
        assert not _extra, (
            "retired floor carries names the canonical LEGACY_BOTS does not "
            f"({sorted(_extra)}) — add them to cleanup_legacy_bots.LEGACY_BOTS "
            "(the half of the retirement rule that prunes the row) rather "
            "than keeping a second list here")
        # The incident itself: every canonically-retired book must be excluded
        # from the go-live scan. A bare `_RETIRED_FLOOR` fails this.
        for _dead in ("pm-gillard-lshadow", "crypto-breakout-4h-lshadow",
                      "lighter-dislocation-lshadow", "equities-regime-lshadow",
                      "freqtrade-dad-lshadow", "lighter-ticket-taker-lighter"):
            assert _dead in RETIRED, f"{_dead} is retired but still graded"
        # ...and the bare-name trap must not take a LIVING book with it.
        # [2026-08-19] mum left this list when it was RETIRED (I17 no_rate).
        # The guard is unchanged and still has two living subjects — the point
        # was never mum, it is that membership stays EXACT-match.
        for _alive in ("freqtrade-georgia-lshadow",
                       "freqtrade-avo-maria-lshadow"):
            assert _alive not in RETIRED, (
                f"{_alive} is a LIVING book — `LEGACY_BOTS` carries its "
                "Kraken-era BARE name and membership must stay exact-match")

    # ledger_drawdown
    assert ledger_drawdown([]) == 0.0
    assert ledger_drawdown([1.0, 2.0, 3.0]) == 0.0, "monotone up has no drawdown"
    # 1000 -> 900 -> peak was 1000 => -10%
    assert ledger_drawdown([-100.0]) == -0.1
    # peak 1100 then down to 990 => -10% off the PEAK, not off the start
    assert ledger_drawdown([100.0, -110.0]) == -0.1
    # recovery does not erase the trough
    assert ledger_drawdown([-100.0, 200.0]) == -0.1
    assert ledger_drawdown([0.0, None]) == 0.0, "None P&L must not raise"

    # alert_key_kind
    assert alert_key_kind("disloc:APEX") == "disloc"
    assert alert_key_kind("census:50") == "census"
    assert alert_key_kind("factor-sample:4") == "factor"
    assert alert_key_kind("veto:ADA") == "veto"
    assert alert_key_kind("live-shadow-gap") == "live_shadow"
    assert alert_key_kind("something-new:1") == "unknown"
    assert alert_key_kind(None) == "unknown"

    # parse_disloc_msg
    assert parse_disloc_msg("🧲 tradeable dislocation on SKY: 315bps (census 82 events)") \
        == (315.0, 82)
    assert parse_disloc_msg("no numbers here") == (None, None)
    assert parse_disloc_msg(None) == (None, None)

    # ---- I1: LIVENESS BEFORE SEMANTICS on the dislocation census ----------
    # [2026-08-06] THE INCIDENT: 🧲 Snap Back retired 4-Aug (jh); its census
    # key froze; this verifier read the frozen payload's CONTENT — per-symbol
    # `last_iso` values still inside the 7-day alert window — and certified
    # **33 of 37 alerts "active"** every morning, because it discarded the
    # publisher's own `updated_at`. Measured at the time of the fix: the
    # publisher was 23.5h stale and every disloc verdict read "active".
    _now = dt.datetime.now(dt.timezone.utc)

    # the age arithmetic itself
    assert census_publisher_age_h(None, _now) is None
    _fresh = _now - dt.timedelta(hours=1.0)
    assert abs(census_publisher_age_h(_fresh, _now) - 1.0) < 0.01
    _dead = _now - dt.timedelta(hours=23.5)          # the measured incident
    assert abs(census_publisher_age_h(_dead, _now) - 23.5) < 0.01
    # naive stamps are treated as UTC, not crashed on
    assert census_publisher_age_h(
        (_now - dt.timedelta(hours=2)).replace(tzinfo=None), _now) is not None

    # the verdict, with the boundary pinned on BOTH sides — a one-sided check
    # passes against `>=` and against a constant moved to 24h, which is
    # exactly how this defect would return.
    assert census_is_dark(23.5), "the incident itself must read DARK"
    assert census_is_dark(CENSUS_STALE_H + 0.1), "just past the bound is dark"
    assert not census_is_dark(CENSUS_STALE_H - 0.1), "just inside is NOT dark"
    assert not census_is_dark(0.05), "a live 90s-loop publisher is never dark"
    assert census_is_dark(None), "FAIL-SAFE: an unknown age must read DARK"
    # a bound loose enough to admit the corpse is not a bound
    assert CENSUS_STALE_H < 23.5, \
        "CENSUS_STALE_H must be tighter than the incident it exists to catch"

    # the operator-facing note names the object to act on (I8)
    _note = census_dark_note(23.5)
    assert "lighter-dislocation-lshadow" in _note, "name the publisher"
    assert "23.5h" in _note and "retired" in _note
    assert "age unknown" in census_dark_note(None)

    # ---- operator-facing times are Sydney-local, never bare UTC -----------
    # CLAUDE.md standing rule. The UTC string must SURVIVE alongside it (the
    # ledgers join on UTC), so this pins both halves rather than a swap.
    _s = sydney_stamp("2026-08-05T21:46:47+00:00")
    assert "2026-08-06 07:46" in _s, f"Sydney local missing/wrong: {_s}"
    assert "Sydney" in _s and "2026-08-05T21:46:47+00:00" in _s, _s
    # AEDT side of the DST boundary (Jan = UTC+11), so the offset is not
    # hardcoded to winter
    assert "2026-01-15 11:00" in sydney_stamp("2026-01-15T00:00:00+00:00")

    # ...AND THE WIRING, through the REAL `write_report`. Pinning the helper
    # alone left a mutation alive: reverting the header to a bare
    # `payload['reviewed_at']` kept this selftest green, because a correct
    # function nothing calls is exactly the inert-enforcement shape (iz) cost a
    # dead MTM bar. Render the file and read the header back.
    import tempfile
    with tempfile.TemporaryDirectory() as _td:
        os.makedirs(os.path.join(_td, "reports"))
        _p = write_report({"reviewed_at": "2026-08-05T21:46:47+00:00",
                           "verdicts": [], "new_evidence": [],
                           "summary": "s", "errors": []}, _td)
        _hdr = open(_p).read().split("\n")[2]
        assert "Sydney" in _hdr and "2026-08-06 07:46" in _hdr, \
            f"report header is not Sydney-local: {_hdr!r}"
        assert "2026-08-05T21:46:47+00:00" in _hdr, \
            f"report header dropped the UTC join key: {_hdr!r}"
        # [(mj)] THE FILENAME IS SYDNEY-DATED. This exact timestamp is the
        # incident: 21:46 UTC is 07:46 the NEXT morning in Sydney, i.e. the
        # cron's own slot, and a UTC-dated name filed it under the PREVIOUS
        # day — overwriting that day's finished report. The old selftest
        # asserted `..._2026-08-05.md` here and so pinned the bug in place.
        assert _p.endswith("evidence_review_2026-08-06.md"), _p

    # ---- ...and a re-run on the SAME day must not destroy the human layer --
    # The Sydney date removes the once-a-day collision; two runs in one Sydney
    # day (which happened on 6-Aug) still land on one filename. The human layer
    # is written into this file AFTER the script, so an overwrite silently
    # eats an operator's annotations.
    with tempfile.TemporaryDirectory() as _td:
        os.makedirs(os.path.join(_td, "reports"))
        _pay = {"reviewed_at": "2026-08-05T21:46:47+00:00", "verdicts": [],
                "new_evidence": [], "summary": "s", "errors": []}
        _p1 = write_report(_pay, _td)
        with open(_p1, "a") as _fh:
            _fh.write("\n## HUMAN LAYER — operator annotations\n")
        _pay2 = dict(_pay, reviewed_at="2026-08-05T23:10:00+00:00")
        _p2 = write_report(_pay2, _td)
        assert _p2 == _p1, "same Sydney day must reuse the series filename"
        _kept = [f for f in os.listdir(os.path.join(_td, "reports"))
                 if "superseded" in f]
        assert len(_kept) == 1, f"prior report not preserved: {_kept}"
        _old = open(os.path.join(_td, "reports", _kept[0])).read()
        assert "HUMAN LAYER" in _old, \
            "the preserved copy lost the annotations it exists to protect"
        assert "HUMAN LAYER" not in open(_p2).read(), "fresh report is fresh"
        assert _kept[0] in open(_p2).read(), \
            "a silent rename is as bad as a silent overwrite — name the backup"

    # tstat
    assert tstat([1.0]) is None, "n=1 is undefined"
    assert tstat([2.0, 2.0, 2.0]) is None, "zero variance is undefined"
    assert tstat([1.0, 2.0, 3.0]) is not None

    # ---- gate_status: the CANONICAL gate, not a second copy of it ----------
    # [2026-07-30] These pin the defect this section was rewritten for: on
    # 29-Jul the gate was re-specified (CHANGELOG (fk)) and this file kept the
    # OLD rule, so one day later the review published both errors the re-spec
    # existed to remove. Each case below is a book shape, graded end-to-end.
    _t0 = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)

    def _mk(pcts, span_days=40.0):
        """[(pnl_pct, pnl_abs, closed_at)] oldest first, evenly spaced."""
        step = dt.timedelta(days=span_days / max(1, len(pcts) - 1))
        return [(p, p * 10.0, _t0 + i * step) for i, p in enumerate(pcts)]

    # (1) THE CARRY SHAPE — the book the OLD rule rejected forever. Low win
    #     rate, real positive expectancy. 🌾 perps-funding-carry-lshadow
    #     measured t=2.60 on n=82 while winning 40.2% of trades; the stale
    #     WR>55% bar in this file rejected it on 30-Jul.
    # NOTE the INTERLEAVE: a few big wins spread THROUGH many small losses is
    # the carry shape. Front-loading the wins instead fails both-halves, which
    # is a different (and correctly rejected) book — the one-window win.
    carry = _mk([0.20, -0.03, -0.03] * 13 + [0.20])
    st, why, s = gate_status(carry)
    assert s["win_rate"] < 0.55 and s["mean_pct"] > 0, s
    assert s["h1"] > 0 and s["h2"] > 0, s
    assert st == "pass", f"the carry shape must clear the CURRENT gate: {why}"
    assert "not a bar" in why, "win rate must be reported as a non-bar"

    # (2) THE INVERSE the new bar buys: a HIGH win rate that LOSES money. The
    #     old rule admitted this on win rate alone.
    tails = _mk([0.01] * 34 + [-0.30] * 6)
    st_t, why_t, s_t = gate_status(tails)
    assert s_t["win_rate"] > 0.55 and s_t["mean_pct"] < 0, s_t
    assert st_t == "fail" and "mean" in why_t, why_t

    # (3) THE 30-JUL FALSE PASS, as its own case. ⚖️ perps-funding-spread-lshadow
    #     was reported as CLEARING the gate on WR 56.1% with t=0.65 — a book
    #     with no measured edge offered up for real money.
    noisy = _mk([0.05, -0.045] * 20)
    st_n, why_n, s_n = gate_status(noisy)
    assert s_n["win_rate"] >= 0.5 and s_n["mean_pct"] > 0, s_n
    assert st_n == "fail" and why_n == f"t {s_n['t']:.2f} < 2", why_n

    # (4) EACH REMAINING BAR ALONE (a bar no case can fail is decoration).
    thin = gate_status(_mk([0.02] * 10))           # closes floor only
    assert thin[0] == "fail" and thin[1] == f"n 10 < {GOLIVE_MIN_CLOSES}", thin[1]
    lop = gate_status(_mk([0.05] * 20 + [-0.01] * 20))   # both-halves only
    assert lop[0] == "fail" and "halves" in lop[1] and ";" not in lop[1], lop[1]
    win = gate_status(_mk([0.01] * 40, span_days=5.0))   # 30-day window only
    # the window bar alone — asserted on the BAR, not on the reason prose
    # (the reason string's wording is golive_readiness's business, not ours)
    assert win[0] == "fail" and blocking_bars(win[2]) == ("window",), win[1]
    # ungradeable input claims nothing and never raises
    assert gate_status([])[0] == "fail"
    assert gate_status([(0.01, 1.0, _t0)])[0] == "fail", "n=1 is ungradeable"

    # (5) The near-miss classifier. Two books are ~11 days from a real go-live
    #     decision (carry t=2.60, Farmer shadow t=2.09) and the 30-Jul review
    #     mentioned NEITHER — it reported only the false passer. A book whose
    #     sole remaining bar is calendar is the operator's lead time.
    _, _, s_win = gate_status(_mk([0.01] * 40, span_days=5.0))
    assert blocking_bars(s_win) == ("window",), blocking_bars(s_win)
    assert near_miss_eta(s_win) is not None
    #     thin AND short is NOT "N days from ready" — two bars outstanding.
    _, _, s_both = gate_status(_mk([0.02] * 10, span_days=5.0))
    assert blocking_bars(s_both) == ("closes", "window"), blocking_bars(s_both)
    assert near_miss_eta(s_both) is None, "two failing bars is not a near-miss"
    #     a halves failure is not a window failure
    _, _, s_lop = gate_status(_mk([0.05] * 20 + [-0.01] * 20))
    assert blocking_bars(s_lop) == ("halves",), blocking_bars(s_lop)
    assert near_miss_eta(s_lop) is None
    #     ungradeable claims nothing and never raises
    assert near_miss_eta(stats([])) is None
    assert blocking_bars(stats([])) == tuple(sorted(BAR_NAMES))

    # (6) THE ANTI-DRIFT CONTRACT. blocking_bars is derived from the grader's
    #     bar_map, never from prose, so a bar added/renamed/redefined upstream
    #     arrives here without an edit. The FIRST cut of this parsed
    #     `why.startswith("window ")` and was obsolete within hours when (hl)
    #     landed bar_map — that is the drift this asserts against.
    assert set(bar_map(_stats_pass := stats(carry))) == set(BAR_NAMES)
    assert all(bar_map(_stats_pass).values()) is grade(_stats_pass)[0], \
        "bar_map and grade must agree — the canonical invariant"
    assert not blocking_bars(_stats_pass), "a passing book blocks on nothing"
    # the review must render the bar LIST from the grader, not restate it
    assert len(BAR_NAMES) == 6 and "maxdd" in BAR_NAMES, BAR_NAMES

    # ---- the ACTION detector, which was dead code until 30-Jul -------------
    assert action_items(["🚦 go-live gates (...): NO new candidate"]) == []
    assert len(action_items(["🚦 go-live gates (...): some-book (n=41, t=2.4)"])) == 1, \
        "a NEW go-live candidate must raise the operator flag"
    assert len(action_items(["🚦 fleet-risk ** DD GOVERNOR BEYOND -5% **"])) == 1
    assert len(action_items(["📏 Farmer live-vs-shadow DIVERGING"])) == 1
    assert action_items(["🧬 Farmer arms AGREE: live abc vs shadow abc"]) == []
    assert len(action_items(["🧬 Taker arms DIVERGE: live abc vs shadow def"])) == 1

    # ---- [2026-08-26] A LIVE ROW IS DIFFERENCED AGAINST ITS OWN TWIN ------
    # THE INCIDENT: `live_shadow_gap`'s live side was LIVE_ROWS[0] while its
    # shadow side was the hardcoded string 'perps-funding-lighter-lshadow'.
    # When 💸 the Farmer's LIVE arm retired ((ta)) and 🙏 Avo / 🔮 Georgia /
    # 👩 mum took the sub-accounts, LIVE_ROWS[0] became Avo — so the review
    # subtracted THE FARMER'S SHADOW BOOK from AVO'S LIVE ARM and published
    # it as "Farmer live-vs-shadow ... no divergence". The one instrument
    # meant to catch a live book drifting from its control was comparing two
    # unrelated books, and its all-clear was structurally unearnable.
    for _live in DECLARED_LIVE:
        _tw = shadow_twin(_live)
        assert _tw != _live and _tw.endswith("-lshadow"), _tw
        assert _tw.rsplit("-", 1)[0] == _live.rsplit("-", 1)[0], \
            f"{_live} paired with a DIFFERENT book's shadow: {_tw}"
    assert shadow_twin("freqtrade-avo-maria-lighter") == \
        "freqtrade-avo-maria-lshadow"
    # the (co) suffix trap: replace() is global, and the Farmer's live row
    # carries '-lighter' TWICE — only the SUFFIX may be rewritten.
    assert shadow_twin("perps-funding-lighter-lighter") == \
        "perps-funding-lighter-lshadow"
    # every live row is watched, not just row[0] — Georgia and mum were unwatched
    assert len(DECLARED_LIVE) >= 1
    assert set(LIVE_TWINS) == {shadow_twin(r) for r in DECLARED_LIVE}

    # ---- [2026-08-02] CONTAINER vs REPO ----------------------------------
    # THE INCIDENT: on 2-Aug both Farmer arms reported `705425a83422` while the
    # repo predicted `30bf230bd5fb` at the same build_n=15. `arm_drift_line`
    # said "arms AGREE" and `action_items` raised nothing, so a LIVE
    # REAL-MONEY container ~3 days behind `bot_pnl_store` read as healthy.
    # A convergent metric is not a health check: ask what it says when
    # EVERYTHING is broken. Two stale arms agree with each other.
    _agree = arm_drift_line("Farmer", ("705425a83422", "15"),
                            ("705425a83422", "15"))
    assert "AGREE" in _agree and action_items([_agree]) == [], \
        "the incident's premise: the arm check calls a doubly-stale pair healthy"
    _behind = head_drift_line("perps-funding-lighter-lighter",
                              ("705425a83422", "15"), ("30bf230bd5fb", 15),
                              live_money=True)
    #     [2026-08-05 (ke)] THE CONTRACT CHANGED, and the reason is a SECOND
    #     incident pointing the other way. The 2-Aug line asserted "the running
    #     container does not carry what has been merged" and tagged it REAL
    #     MONEY. On 5-Aug `(ka)` touched `fleet_tuning.py` — a `_BUILD_SHARED`
    #     name — so EVERY image's stamp moved while no bot's logic did, and
    #     this fired on both real-money rows and led the report, while
    #     `audit_code_currency` classified both as CURRENT minutes later.
    #     A stamp difference is a FACT; staleness is a VERDICT, and this
    #     function has only the fact. It now says so and names the authority.
    assert "stamp differs" in _behind and "UNCLASSIFIED" in _behind, _behind
    assert "REAL MONEY" in _behind, "the row's real-money status is still shown"
    assert action_items([_behind]) == [], \
        ("an unclassified stamp difference must NOT page: a shared-module "
         "change moves every stamp, and escalating that daily is the "
         "cry-wolf trap audit_code_currency's own header documents")
    #     ...but the CLASSIFIER's verdict still pages, so the 2-Aug incident
    #     (a live container genuinely stale in its OWN entry file) is not lost
    #     — it arrives as BEHIND-OWN, the one verdict that means it.
    assert len(action_items(["🧬 perps-funding-lighter-lighter BEHIND-OWN: "
                             "container 705425a83422 is 3 commits behind on "
                             "its own entry file"])) == 1, \
        "BEHIND-OWN is the verdict that means the container is really stale"
    #     ...and the arm check must still disagree with the head check on the
    #     doubly-stale input, or the second detector is redundant.
    assert "AGREE" in _agree and "stamp differs" in _behind
    #     [(ke)] THE COLLISION THIS ALREADY HIT, pinned so it cannot return.
    #     The first cut of the unclassified message NAMED the verdict word as
    #     guidance ("...where BEHIND-OWN is the only verdict that means..."),
    #     and the matcher was a bare substring scan — so the sentence saying
    #     "this is NOT yet a finding" paged as a finding. The fleet's own rule:
    #     a page-wide substring scan is not a structural claim. The matcher now
    #     requires the verdict LABEL (`BEHIND-OWN:`), and prose that merely
    #     discusses the class must never page.
    assert action_items(["🧬 x: see audit_code_currency, where BEHIND-OWN is "
                         "the only real verdict"]) == [], \
        "prose ABOUT the verdict class must not be mistaken for the verdict"

    #     `n` FIRST, per (fd): a different COPY set is NOT a stale deploy, and
    #     claiming it is has already cost this fleet a day of chasing four books.
    _fileset = head_drift_line("x", ("aaa", "14"), ("bbb", 15))
    assert "FILE SET" in _fileset and "BEHIND THE REPO" not in _fileset
    assert action_items([_fileset]) == [], \
        "a file-set difference is expected and must not page anyone"
    #     a match is reported and is not an action
    _match = head_drift_line("x", ("aaa", "15"), ("aaa", 15))
    assert "matches the repo tree" in _match and action_items([_match]) == []

    #     FAIL-SOFT: no prediction, no stamp, or an unreadable count claims
    #     NOTHING. A drift claim must never rest on a prediction that did not
    #     run — the failure would look exactly like a clean deploy.
    assert head_drift_line("x", ("aaa", "15"), None) is None
    assert head_drift_line("x", (None, None), ("aaa", 15)) is None
    assert head_drift_line("x", None, ("aaa", 15)) is None
    assert "FILE SET" in head_drift_line("x", ("aaa", "junk"), ("bbb", 15)), \
        "an unparseable count is a file-set doubt, never a drift accusation"
    assert repo_build("no_such_entry_file_%%%.py") is None

    #     BORN-DARK ARM. Every failure mode above returns None, so a wrong path
    #     in ROW_ENTRY makes the whole section return nothing FOREVER and look
    #     exactly like "no drift". Resolve each mapped entry for real. This is
    #     also why repo_build resolves against the repo root and not the cwd:
    #     the review runs from wherever cron happens to start it.
    for _row, _entry in ROW_ENTRY.items():
        _p = repo_build(_entry)
        assert _p and _p[0] and _p[1] > 0, \
            f"ROW_ENTRY[{_row}]={_entry!r} does not resolve — the check is inert"

    #     every mapped row must be one the arm-drift query actually SELECTs, or
    #     the section silently reports nothing for it
    assert set(ROW_ENTRY) >= set(LIVE_ROWS), "both real-money rows must be mapped"

    # the gate is IMPORTED, never redefined here — the whole point of (fk)
    assert not any(k.startswith("GATE_MIN") for k in globals()), \
        "a second copy of the go-live gate is a second RULE"
    # [(hj)] ...and IMPORTED means the SAME OBJECTS, not a local re-implementation
    # that happens to agree today. The name-prefix check above would stay green
    # against a hand-rolled `grade()` pasted in here; this one cannot.
    import golive_readiness as _gr
    assert grade is _gr.grade and stats is _gr.stats, \
        "gate_status must call the canonical grader, not a local copy"
    assert GOLIVE_MIN_CLOSES is _gr.GOLIVE_MIN_CLOSES
    assert GOLIVE_MIN_DAYS is _gr.GOLIVE_MIN_DAYS
    # the SQL prefilter must never be stricter than the real bar, or a genuine
    # candidate is dropped before it is ever graded (it is a speed hint, not a
    # rule) — the failure would be silent and would look like "no candidates"
    assert CANDIDATE_MIN_CLOSES <= GOLIVE_MIN_CLOSES, CANDIDATE_MIN_CLOSES

    # a live row's shadow twin is never a go-live candidate. The Farmer twin
    # doubles as the suffix-only-rewrite regression check (its base contains
    # "-lighter", the case a global replace mangles); the second twin tracks
    # the live slot's CURRENT occupant ((ma): taker -> avo, 13-Aug).
    # [(tb)] was `perps-funding-lighter-lshadow` — the twin of a live row that
    # retired at (ta). The PROPERTY being pinned is the suffix rewrite (a bare
    # str.replace on the Farmer's row produced `perps-funding-lshadow-lshadow`,
    # see the note above), so it is re-pinned on a CURRENT live row.
    assert "freqtrade-georgia-lshadow" in LIVE_TWINS
    assert "freqtrade-avo-maria-lshadow" in LIVE_TWINS
    assert "freqtrade-avo-maria-lshadow" in LIVE_TWINS
    assert not (LIVE_TWINS & set(LIVE_ROWS)), "twins must be distinct from live rows"

    # write scope
    assert _assert_write_target(REVIEW_KEY) == REVIEW_KEY
    for bad in ("bot_pnl", "fleet-alerts", "learning-brain", ""):
        try:
            _assert_write_target(bad)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"write target {bad!r} was NOT refused")

    # Section is fail-soft AND records
    errs = []
    with Section(errs, "boom"):
        raise ValueError("kaboom")
    assert len(errs) == 1 and "kaboom" in errs[0], errs
    with Section(errs, "fine"):
        pass
    assert len(errs) == 1, "a clean section must not record an error"

    # the schema traps this script exists to survive are spelled with a cast
    assert "::timestamptz" in CA
    print("evidence_review selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
