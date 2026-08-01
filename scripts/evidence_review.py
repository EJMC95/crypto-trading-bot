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
                                  era_rows, grade, same_pair_overlaps, stats)
except ImportError:                      # run as `python -m scripts.evidence_review`
    from scripts.golive_readiness import (BAR_NAMES, GOLIVE_MIN_CLOSES,
                                          GOLIVE_MIN_DAYS, bar_map,
                                          book_payload, era_rows, grade,
                                          same_pair_overlaps, stats)

# Cheap SQL prefilter before the per-book ledger read. It must never be STRICTER
# than the real closes bar, or a genuine candidate is hidden before it is graded.
CANDIDATE_MIN_CLOSES = min(10, GOLIVE_MIN_CLOSES)

# Rows whose ledgers are HISTORY — retired bots keep closing nothing, but their
# 30d window can still contain trades for a few weeks after the cut and they
# will happily "pass" a go-live gate they can never act on.
RETIRED = frozenset({
    "event-listing-sniper", "scanner-cross-exchange-arb", "scanner-triangular-arb",
    "perps-rsi-meanrev", "perps-rsi-meanrev-lshadow", "perps-donchian-breakout",
    "perps-donchian-breakout-lshadow", "perps-donchian-breakout-lighter",
    "perps-funding-carry", "equities-momentum", "equities-momentum-lshadow",
    "equities-regime-ibkr", "crypto-trend-daily-lighter",
})
LIVE_ROWS = ("perps-funding-lighter-lighter", "lighter-ticket-taker-lighter")
# The `-lshadow` CONTROL arm of a row that is ALREADY LIVE is not a go-live
# candidate — it is the twin of a bot that already went. It also fails the
# premise twice over: while the experiment judge runs a candidate on it, the
# shadow arm is an EXPERIMENT arm, not a control (xp-judge, 15-Jul). Listing it
# as "passing the gates" invites promoting a book that is already promoted.
# NOTE the SUFFIX-only rewrite. `str.replace` is global, and the Farmer's live
# row is `perps-funding-lighter-lighter` — two occurrences — so a bare
# `.replace("-lighter","-lshadow")` yields `perps-funding-lshadow-lshadow`,
# a row that does not exist, and the real twin sails through the gate scan.
LIVE_TWINS = frozenset(
    (r[:-len("-lighter")] + "-lshadow") if r.endswith("-lighter") else r
    for r in LIVE_ROWS)


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


def near_miss_eta(s):
    """Days until the WINDOW bar clears, when it is the ONLY failing bar.

    Returns None unless the book has cleared every EVIDENCE bar — a book that
    is also thin, or noisy, is not "N days from ready" and must never read as
    though it were.
    """
    if s.get("n", 0) < 2 or blocking_bars(s) != ("window",):
        return None
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
    with Section(errors, "disloc-census"):
        st, _ = load_state(cur, "lighter-dislocation-lshadow")
        census = (st or {}).get("census") or {}

    for key, a in sorted(latest.items()):
        kind = alert_key_kind(key)
        try:
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


def live_shadow_gap(cur, live=LIVE_ROWS[0], shadow="perps-funding-lighter-lshadow",
                    days=14):
    """Per-trade pnl_pct gap. Per-trade, NEVER equity — the arms hold different
    capital ($100 live vs $1,000 shadow), so an equity-% gap compares nothing."""
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
        for bot in cands:
            if bot in RETIRED or bot in LIVE_ROWS or bot in LIVE_TWINS:
                continue
            # The grader's own shape: (pnl_pct, pnl_abs, closed_at) oldest
            # first, plus the OPEN stamp the era is keyed on. `opened_at` is
            # read RAW (TEXT), not cast: the cast can raise on one bad row and
            # take the whole section down with it, whereas `era_rows` fails
            # CLOSED per row — an unreadable open stamp drops that trade rather
            # than the report.
            cur.execute(f"""SELECT pnl_pct, pnl_abs, {CA}, opened_at
                              FROM paper_trades
                             WHERE bot=%s AND pnl_abs IS NOT NULL AND closed_at IS NOT NULL
                             ORDER BY {CA}""", (bot,))
            quads = cur.fetchall()
            # [(hc)/(hq)] THE ERA IS A PRECONDITION IN FRONT OF THE SIX BARS.
            # Grade the book as it RUNS TODAY, never its whole retained ledger.
            # `era_rows` is golive_readiness's — the same selection the
            # canonical grader runs — so review and grader cannot disagree
            # about the sample any more than about the bars.
            rows, rows_all, era_iso = era_rows(bot, quads)
            status, why, s = gate_status(rows)
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
            eta = near_miss_eta(s)
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
        g = live_shadow_gap(cur)
        items.append(f"📏 Farmer live-vs-shadow per-trade gap {g['gap_pp']:+.3f}pp "
                     f"(live {g['live_pct']:+.3f}% n={g['live_n']}, "
                     f"shadow {g['shadow_pct']:+.3f}% n={g['shadow_n']}) — "
                     f"{'DIVERGING' if abs(g['gap_pp']) >= 2 else 'no divergence'}")

    with Section(errors, "arm-drift"):
        cur.execute("""SELECT bot, extra->>'build', extra->>'build_n' FROM bot_pnl
                        WHERE bot IN ('perps-funding-lighter-lighter',
                                      'perps-funding-lighter-lshadow',
                                      'lighter-ticket-taker-lighter',
                                      'lighter-ticket-taker-lshadow')""")
        b = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for live, shadow, name in (
                ("perps-funding-lighter-lighter", "perps-funding-lighter-lshadow", "Farmer"),
                ("lighter-ticket-taker-lighter", "lighter-ticket-taker-lshadow", "Taker")):
            items.append(arm_drift_line(name, b.get(live), b.get(shadow)))
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
    return (f"🧬 {name} arms DRIFT: live {bl} vs shadow {bs} (both n={nl}, so "
            "this is code, not file set) — the shadow arm is not a clean "
            "control while this holds")


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
    return out


def write_report(payload, repo_root):
    day = payload["reviewed_at"][:10]
    path = os.path.join(repo_root, "reports", f"evidence_review_{day}.md")
    act = action_items(payload["new_evidence"])
    lines = [f"# Evidence Review — {day}", "",
             f"_Reviewed {payload['reviewed_at']}._", ""]
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

    # a live row's shadow twin is never a go-live candidate
    assert "perps-funding-lighter-lshadow" in LIVE_TWINS
    assert "lighter-ticket-taker-lshadow" in LIVE_TWINS
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
