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
GATE_MIN_TRADES = 20     # go-live gate: >=20 closes in 30d
GATE_MIN_WR = 0.55       # go-live gate: win rate > 55%
GATE_MAX_DD = 0.15       # go-live gate: max drawdown < 15%
ALERT_WINDOW_D = 7

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


def gate_status(n, wr, dd):
    """('pass'|'fail', reason) against the go-live gates. dd is a fraction <=0."""
    if n < GATE_MIN_TRADES:
        return "fail", f"n={n} < {GATE_MIN_TRADES}"
    if wr <= GATE_MIN_WR:
        return "fail", f"WR {wr:.1%} <= {GATE_MIN_WR:.0%}"
    if dd is not None and abs(dd) >= GATE_MAX_DD:
        return "fail", f"dd {dd:.1%} breaches {GATE_MAX_DD:.0%}"
    return "pass", f"n={n}, WR {wr:.1%}, dd {dd:.1%}" if dd is not None else "pass"


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
        cur.execute(f"""SELECT bot, count(*), sum(CASE WHEN pnl_abs>0 THEN 1 ELSE 0 END)
                          FROM paper_trades
                         WHERE pnl_abs IS NOT NULL AND {CA} > now() - interval '30 days'
                         GROUP BY 1 HAVING count(*) >= {GATE_MIN_TRADES} ORDER BY 2 DESC""")
        cands = cur.fetchall()
        passers = []
        for bot, n, w in cands:
            if bot in RETIRED or bot in LIVE_ROWS or bot in LIVE_TWINS:
                continue
            cur.execute(f"""SELECT pnl_abs FROM paper_trades
                             WHERE bot=%s AND pnl_abs IS NOT NULL ORDER BY {CA}""", (bot,))
            pnls = [r[0] for r in cur.fetchall()]
            dd = ledger_drawdown(pnls)
            status, why = gate_status(n, w / n, dd)
            if status == "pass":
                passers.append(f"{bot} ({why})")
        items.append("🚦 go-live gates (30d; retired, already-live and live-twin rows "
                     "excluded; drawdown "
                     "derived from the LEDGER since bot_pnl.extra.max_drawdown is "
                     f"unpopulated): {'; '.join(passers) if passers else 'NO new candidate'}")

    with Section(errors, "fleet-risk"):
        st, _ = load_state(cur, "fleet-risk")
        if st:
            dd7 = st.get("fleet_dd_7d")
            items.append(f"🚦 fleet-risk light {st.get('light')} — {st.get('gross')} gross vs "
                         f"long budget {st.get('long_budget')}; 7d DD {float(dd7 or 0):.2%}, "
                         f"clip_scale {st.get('clip_scale')}"
                         + ("  ** DD GOVERNOR BEYOND -5% **" if (dd7 or 0) <= -0.05 else ""))

    with Section(errors, "live-shadow"):
        g = live_shadow_gap(cur)
        items.append(f"📏 Farmer live-vs-shadow per-trade gap {g['gap_pp']:+.3f}pp "
                     f"(live {g['live_pct']:+.3f}% n={g['live_n']}, "
                     f"shadow {g['shadow_pct']:+.3f}% n={g['shadow_n']}) — "
                     f"{'DIVERGING' if abs(g['gap_pp']) >= 2 else 'no divergence'}")

    with Section(errors, "arm-drift"):
        cur.execute("""SELECT bot, extra->>'build' FROM bot_pnl
                        WHERE bot IN ('perps-funding-lighter-lighter',
                                      'perps-funding-lighter-lshadow',
                                      'lighter-ticket-taker-lighter',
                                      'lighter-ticket-taker-lshadow')""")
        b = dict(cur.fetchall())
        for live, shadow, name in (
                ("perps-funding-lighter-lighter", "perps-funding-lighter-lshadow", "Farmer"),
                ("lighter-ticket-taker-lighter", "lighter-ticket-taker-lshadow", "Taker")):
            bl, bs = b.get(live), b.get(shadow)
            if bl and bs:
                items.append(f"🧬 {name} arms {'AGREE' if bl == bs else 'DRIFT'}: "
                             f"live {bl} vs shadow {bs}"
                             + ("" if bl == bs else
                                " — the shadow arm is not a clean control while this holds"))
    return items


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


def write_report(payload, repo_root):
    day = payload["reviewed_at"][:10]
    path = os.path.join(repo_root, "reports", f"evidence_review_{day}.md")
    act = [e for e in payload["new_evidence"]
           if "GOVERNOR" in e or "DIVERGING" in e or "NO new candidate" not in e and "go-live gates" in e and "pass" in e]
    lines = [f"# Evidence Review — {day}", "",
             f"_Reviewed {payload['reviewed_at']}._", ""]
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

    # gate_status — each gate must be able to FAIL ALONE
    assert gate_status(10, 0.9, -0.01)[0] == "fail"          # n
    assert gate_status(50, 0.50, -0.01)[0] == "fail"         # wr
    assert gate_status(50, 0.90, -0.20)[0] == "fail"         # dd
    assert gate_status(50, 0.90, -0.01)[0] == "pass"
    assert gate_status(50, 0.5501, -0.14)[0] == "pass", "just inside every gate"

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
