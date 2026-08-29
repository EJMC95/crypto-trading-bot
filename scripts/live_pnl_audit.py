#!/usr/bin/env python3
"""live_pnl_audit — the DAILY / WEEKLY / MONTHLY audit of the LIVE books:
where the P&L actually came from, what is restricting size right now, and
whether what the fleet DECLARED has actually LANDED.

Born 25-Aug-2026 (tk). **Eamon, 25-Aug:** *"Daily and weekly and monthly
audit of live bots - how p n L can improve ... Also how everything's syncing
as there seems to be ... instances where a month has passed without something
being implemented."*

The second half of that ask is the load-bearing one, and this script is built
around the incident that proved it the same day: the (td) manual-trade
attestation shipped its CODE on 25-Aug and its VALUE never reached the
container — the row published `manual_pnl_usd: 0.0` while the evidence
board's backstop kept live clips at 0.75x for losses that were never the
bot's. A declared change that has not landed is invisible precisely because
everything looks green. So every check here compares a DECLARATION against
the live feed's own EFFECT, in the (iw)/(ml) read-back-the-serving-output
tradition:

  * a row that stopped publishing is reported by AGE first (I1 — liveness
    before semantics; 🧭 nav-cook sat frozen 4.5 days behind an "online"
    status while its own fix was merged and never received);
  * a live row carrying unattributed flatten closes (pnl 0.0, basis unknown
    — the daily-loss rail clearing positions the bot cannot attest) with NO
    manual-P&L attestation set is the freshest declared-but-not-landed class;
  * keep-or-retire asks are aged from the docket's own `days_held` so a
    decision cannot quietly become a month old;
  * fresh rows serving more than one build stamp are listed (the deep
    per-commit verdict stays `audit_code_currency`, which the weekly
    assessment already runs — this is the cheap daily tripwire).

ADVISORY BY CONSTRUCTION: reads public endpoints only, moves no lever,
writes no state. Fail-CLOSED on a dark feed ((jc): exit 2, never a vacuous
green). Exit 1 when a RED finding stands, so the Actions run is red while a
live book is dead or a declared change has not landed — same-day actionable
conditions only, never a standing backlog (the (mz) ratchet lesson).

Sydney display per the operator-timezone rule; internals stay UTC.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import subprocess
import sys
import urllib.request

try:
    from fleet_books import DECLARED_LIVE as EXPECTED_LIVE_ROWS
except Exception:  # noqa: BLE001
    EXPECTED_LIVE_ROWS = ()

DASH = "https://pnl-dashboard-production-858c.up.railway.app"

#: Liveness bars (seconds). LIVE rows loop at 300s; a 30-min silence on real
#: money is a page. Shadow loops run 90s–6h across the fleet (🧮 hull's
#: funding walk is the slowest regular publisher), so the shadow bar is 6h —
#: wide enough that no healthy book trips it, and 🧭 nav-cook's 4.5-DAY
#: freeze would have been RED here on day one.
LIVE_STALE_S = 30 * 60
SHADOW_STALE_S = 6 * 3600

#: Docket asks older than this are surfaced every run. The docket arms at 7d
#: (`docket_days`); by 10d an ask is no longer "new this week".
DOCKET_AGE_FLAG_D = 10.0

#: OPERATOR_QUEUE.md untouched longer than this (git mtime, a PROXY for "the
#: sweep ran" — any edit resets it, which is the sweep) is flagged: its own
#: header says "the daily review keeps this current".
QUEUE_SWEEP_FLAG_D = 7.0

WINDOWS = {"daily": 1, "weekly": 7, "monthly": 30}


# ---------------------------------------------------------------- fetch layer

def fetch_json(path_or_url, timeout=60):
    """Load JSON from a local file or an https URL. None on any failure —
    the caller decides whether that darkness is fatal (pnl: yes)."""
    try:
        if str(path_or_url).startswith("http"):
            req = urllib.request.Request(
                path_or_url, headers={"User-Agent": "live-pnl-audit"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        with open(path_or_url) as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001 — every failure means "dark"
        print(f"fetch failed: {path_or_url}: {e}", file=sys.stderr)
        return None


def parse_ts(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


# ------------------------------------------------------------- row selection

def live_rows(pnl):
    """LIVE = the row's own `extra.venue == "lighter_live"` — rule-driven
    membership, never a curated name list (the audit-scope rule has named a
    retired bot three times; a list here would be the fourth)."""
    out = []
    for b in (pnl or {}).get("bots") or []:
        if ((b.get("extra") or {}).get("venue")) == "lighter_live":
            out.append(b)
    return sorted(out, key=lambda b: b.get("bot") or "")


def _get_path(d, path):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _present(v):
    return v not in (None, "", [], {})


def live_roster_findings(pnl):
    expected = sorted(str(x) for x in (EXPECTED_LIVE_ROWS or ()))
    if not expected:
        return []
    got = sorted(str((b or {}).get("bot")) for b in live_rows(pnl) if (b or {}).get("bot"))
    if got == expected:
        return []
    return [f"live roster mismatch — expected {expected} but feed shows {got}"]


def stale_rows(pnl):
    """(row, age_s, bar_s) for every row past its liveness bar. AGE FIRST
    (I1): a missing age is reported as unknown, never assumed fresh."""
    out = []
    for b in (pnl or {}).get("bots") or []:
        age = b.get("age_sec")
        is_live = ((b.get("extra") or {}).get("venue")) == "lighter_live"
        bar = LIVE_STALE_S if is_live else SHADOW_STALE_S
        if age is None:
            out.append((b, None, bar))
        elif float(age) > bar:
            out.append((b, float(age), bar))
    return out


# ------------------------------------------------------------- ledger slices

def ledger_for(trades, bot):
    return [r for r in trades or [] if r.get("bot") == bot]


def window_rows(trades, days, now):
    cutoff = now - dt.timedelta(days=days)
    out = {}
    for r in trades or []:
        t = parse_ts(r.get("closed_at"))
        if t is None or t < cutoff:
            continue
        out.setdefault(r.get("bot") or "?", []).append(r)
    return out


def book_stats(rows):
    pnls = [float(r.get("pnl_abs") or 0) for r in rows]
    pcts = [float(r.get("pnl_pct") or 0) * 100 for r in rows]
    n = len(rows)
    total = sum(pnls)
    mean = statistics.mean(pcts) if pcts else 0.0
    sd = statistics.stdev(pcts) if n > 1 else 0.0
    t = (mean / (sd / math.sqrt(n))) if (sd and n > 1) else float("nan")
    wins = sum(1 for p in pnls if p > 0)
    return {"n": n, "total": total, "mean_pct": mean, "t": t, "wins": wins}


def unattributed_flattens(rows):
    """Ledger rows the daily-loss rail booked at pnl 0.0 with NO entry basis
    — positions the bot could not attest (manual fills, inherited legs). The
    0.0 is honest (I8: never a guess); what it means is that the row's
    pnl_abs carries P&L the ledger cannot attribute to the bot."""
    return [r for r in rows
            if (r.get("reason") or "").endswith("daily_loss")
            and not r.get("entry_price")
            and abs(float(r.get("pnl_abs") or 0.0)) < 1e-9]


def attribution(row, all_rows):
    """Decompose a live row's published pnl_abs into what the feed can prove:
    attested manual level, the bot's own realised ledger, unattributed
    flatten count. The residual (pnl_abs − manual − realised) is open MTM
    plus anything unattributed — it is NOT split further here, because doing
    so needs marks this feed does not carry, and a guessed split is worse
    than a named residual."""
    ex = row.get("extra") or {}
    manual = float(ex.get("manual_pnl_usd") or 0.0)
    realised = sum(float(r.get("pnl_abs") or 0) for r in all_rows)
    flat = unattributed_flattens(all_rows)
    pnl = float(row.get("pnl_abs") or 0.0)
    return {
        "pnl_abs": pnl,
        "manual_attested": manual,
        "bot_realised_ledger": realised,
        "unattributed_flattens": len(flat),
        "flatten_pairs": sorted({r.get("pair") or "?" for r in flat}),
        "residual_open_or_unattributed": pnl - manual - realised,
        "attestation_gap": bool(flat) and manual == 0.0,
    }


# ---------------------------------------------------------------- governors

def governor_state(bus):
    """What is restricting live size RIGHT NOW, in the organs' own words."""
    out = {"fleet_clip_scale": None, "fleet_dd_7d": None,
           "carried_while_abstaining": False, "live_levers": []}
    fr = (bus or {}).get("fleet_risk") or {}
    if fr:
        out["fleet_clip_scale"] = fr.get("clip_scale")
        out["fleet_dd_7d"] = fr.get("fleet_dd_7d")
        # dd None + scale < 1.0 = the governor is ABSTAINING (window span
        # under its floor) and carrying the previous restriction forward —
        # deliberate design, but if it pins for many hours that is the
        # stale-reader class and a human should look.
        try:
            if fr.get("fleet_dd_7d") is None and float(
                    fr.get("clip_scale") or 1.0) < 1.0:
                out["carried_while_abstaining"] = True
        except (TypeError, ValueError):
            pass
    levers = ((bus or {}).get("fleet_tuning") or {}).get("levers") or {}
    for name, lv in sorted(levers.items()):
        if (lv or {}).get("lane") == "lighter-live":
            out["live_levers"].append(
                {"name": name, "value": lv.get("value"),
                 "reason": lv.get("reason"), "expires": lv.get("expires")})
    return out


# ------------------------------------------------------------- sync findings

def build_spread(pnl):
    """Distinct build stamps among the FRESH LIVE rows only. Deliberately
    NOT fleet-wide: each image hashes its OWN COPY set, so two current
    containers legitimately publish different stamps ((fd) — this guard's
    first draft compared the whole fleet and read 13 "laggards" on a
    converged one). The three live books share one variant-host image by
    construction, so a stamp spread WITHIN the trio is a real rollout
    laggard. A frozen row's stamp describes its last publish, not a running
    process (I1) — stale rows are excluded here and reported by the
    staleness check instead."""
    fresh = {}
    for b in live_rows(pnl):
        age = b.get("age_sec")
        if age is None or float(age) > LIVE_STALE_S:
            continue
        stamp = ((b.get("extra") or {}).get("build")) or "?"
        fresh.setdefault(stamp, []).append(b.get("bot"))
    return fresh


def docket_aging(bus):
    dock = (((bus or {}).get("golive_readiness") or {})
            .get("decision_docket")) or []
    out = []
    for it in dock:
        held = it.get("days_held")
        if held is not None and float(held) >= DOCKET_AGE_FLAG_D:
            out.append({"book": it.get("book"), "reason": it.get("reason"),
                        "days_held": float(held), "asks": it.get("asks")})
    return sorted(out, key=lambda d: -d["days_held"])


def queue_age_days(repo_root, now):
    """Days since OPERATOR_QUEUE.md was last touched, from git — a PROXY for
    "the sweep ran" (declared as such; any edit counts). None outside a git
    checkout, and None is reported as unknown, never as fresh."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", "OPERATOR_QUEUE.md"],
            cwd=repo_root, capture_output=True, text=True, timeout=30)
        ts = int(out.stdout.strip())
        return (now - dt.datetime.fromtimestamp(
            ts, tz=dt.timezone.utc)).total_seconds() / 86400.0
    except Exception:
        return None


def sync_findings(pnl, trades, bus, now, repo_root=None,
                  trades_limit=None):
    """The declared-vs-effective sweep. RED = same-day actionable (a live
    book dead, a declared change not landed, the audit half-blind); AMBER =
    surfaced every run but not a red build (ages, spreads, proxies)."""
    reds, ambers = [], []

    reds += live_roster_findings(pnl)

    for row, age, bar in stale_rows(pnl):
        name = row.get("bot")
        if age is None:
            reds.append(f"`{name}` publishes NO age — liveness unknown (I1); "
                        "treat as dark until it stamps one")
        else:
            reds.append(
                f"`{name}` FROZEN {age/3600:.1f}h (bar {bar/3600:.1f}h) — "
                f"status still reads `{row.get('status')}`, which is its last "
                "word, not its state (I1). Redeploy: dispatch "
                "railway-redeploy.yml with its service name, then verify the "
                "row's `extra.build` readback — never the green run")

    for row in live_rows(pnl):
        att = attribution(row, ledger_for(trades, row.get("bot")))
        if att["attestation_gap"]:
            reds.append(
                f"`{row.get('bot')}` carries {att['unattributed_flattens']} "
                f"unattributed flatten close(s) ({', '.join(att['flatten_pairs'])}) "
                "with manual_pnl_usd=0.0 — the attestation VALUE has not "
                "landed on the container, so its published P&L (and every "
                "restrictor reading it) mis-prices the bot. Set "
                "`<PFX>_MANUAL_PNL_USD` on the service and verify the row "
                "publishes it back")

    if trades_limit is not None and trades is not None \
            and len(trades) >= trades_limit:
        ambers.append(
            f"trades feed returned exactly its limit ({trades_limit}) — a "
            "truncation signature ((qz)); window sums may be incomplete. "
            "Raise the limit before trusting monthly totals")

    spread = build_spread(pnl)
    if len(spread) > 1:
        lines = "; ".join(f"{stamp[:12]}: {'/'.join(bots)}"
                          for stamp, bots in sorted(spread.items()))
        ambers.append(
            f"the LIVE trio serves {len(spread)} distinct build stamps "
            f"({lines}) — they share one image, so this is a rollout "
            "laggard unless a deploy is mid-flight; `audit_code_currency` "
            "names the commit")

    for d in docket_aging(bus):
        ambers.append(
            f"docket ask on `{d['book']}` ({d['reason']}) has been open "
            f"{d['days_held']:.1f}d — {d['asks']}")

    gov = governor_state(bus)
    if gov["carried_while_abstaining"]:
        ambers.append(
            f"fleet clip governor at {gov['fleet_clip_scale']} while its dd "
            "window is abstaining (dd=None) — the restriction is a CARRIED "
            "value, by design; if it pins for many hours that is the "
            "stale-reader class ((iw)) and worth a look")

    if repo_root:
        qa = queue_age_days(repo_root, now)
        if qa is None:
            ambers.append("OPERATOR_QUEUE.md age unreadable (no git?) — "
                          "sweep staleness UNKNOWN, not fresh")
        elif qa > QUEUE_SWEEP_FLAG_D:
            ambers.append(
                f"OPERATOR_QUEUE.md untouched {qa:.1f}d — its own rule says "
                "the daily review keeps it current; decided items may still "
                "read as open (proxy measure: any edit counts)")

    return reds, ambers


def coverage_matrix(pnl, trades, bus):
    lives = live_rows(pnl)
    trades = trades or []
    live_ids = {str((b or {}).get("bot")) for b in lives if (b or {}).get("bot")}
    live_trades = [r for r in trades if str((r or {}).get("bot")) in live_ids]

    def row_cov(paths):
        if not lives:
            return 0, 0
        n = 0
        for r in lives:
            if any(_present(_get_path(r, p)) for p in paths):
                n += 1
        return n, len(lives)

    def trade_cov(paths):
        if not live_trades:
            return 0, 0
        n = 0
        for r in live_trades:
            if any(_present(_get_path(r, p)) for p in paths):
                n += 1
        return n, len(live_trades)

    def bus_cov(paths):
        ok = any(_present(_get_path(bus or {}, p)) for p in paths)
        return (1 if ok else 0), 1

    checks = [
        ("Trading fees", "trade", ("fee", "fees", "commission", "cost_fee")),
        ("Slippage/spread", "row", ("extra.stop_overshoot.n", "extra.entry_vetoes.coin_veto")),
        ("Partial fills", "trade", ("filled", "filled_size", "partial_fill", "fill_ratio")),
        ("Latency / signal→execution", "trade", ("signal_ts", "signal_at", "decision_ts")),
        ("Minimum order sizing", "row", ("extra.clip_usd", "extra.cap_usd")),
        ("Funding rate visibility", "trade", ("funding_rate", "funding_apr", "entry_apr", "exit_apr")),
        ("Delisted/unavailable pair handling", "trade", ("reason",)),
        ("Position/open-trade limits", "row", ("extra.max_open", "open_trades")),
        ("Max leverage / liquidation telemetry", "row", ("extra.leverage.set", "extra.leverage.liq_gap_pct")),
        ("Max daily-loss lockout", "row", ("extra.entry_vetoes.halt_days_30d", "extra.entry_vetoes.shut_now")),
        ("Max drawdown shutdown hooks", "row", ("extra.entry_vetoes.lockout_hours_30d", "extra.entry_vetoes.entries_shut_reason_30d")),
        ("Kill switch / protections lock", "row", ("extra.entry_vetoes.entries_shut_reason_30d", "extra.entry_vetoes.locked_until")),
        ("No trading on stale data", "row", ("extra.scan.stale_candle", "extra.scan.no_bars")),
        ("API/retry failure telemetry", "row", ("extra.scan.failed", "extra.scan.unpriceable")),
        ("Execution prices recorded", "trade", ("entry_price", "exit_price")),
        ("Risk-adjusted metrics source", "bus", ("golive_readiness.books",)),
    ]
    out = []
    for name, scope, paths in checks:
        if scope == "row":
            have, total = row_cov(paths)
        elif scope == "trade":
            have, total = trade_cov(paths)
        else:
            have, total = bus_cov(paths)
        out.append({"name": name, "scope": scope, "have": have, "total": total})
    return out


def progression_estimates(pnl, trades, bus, reds, ambers):
    """Advisory progression optics from measurable report surfaces only."""
    checks = coverage_matrix(pnl, trades, bus)
    n = len(checks)
    full = sum(1 for c in checks if c["total"] > 0 and c["have"] == c["total"])
    partial = sum(1 for c in checks if c["total"] > 0 and 0 < c["have"] < c["total"])
    missing = sum(1 for c in checks if c["total"] > 0 and c["have"] == 0)
    no_sample = sum(1 for c in checks if c["total"] <= 0)

    cov_score = 100.0 if n == 0 else 100.0 * (full + 0.5 * partial) / n
    reliability_drag = min(80.0, 10.0 * len(reds) + 3.0 * len(ambers))
    headroom = max(0.0, min(100.0, 100.0 - cov_score + 5.0 * missing + 2.0 * no_sample))
    net_progress = max(0.0, cov_score - reliability_drag)

    if net_progress >= 70:
        trend = "strong"
    elif net_progress >= 45:
        trend = "moderate"
    else:
        trend = "early-stage"

    return {
        "checks_total": n,
        "checks_full": full,
        "checks_partial": partial,
        "checks_missing": missing,
        "checks_no_sample": no_sample,
        "coverage_score_pct": cov_score,
        "reliability_drag_pct": reliability_drag,
        "optimization_headroom_pct": headroom,
        "net_progress_pct": net_progress,
        "trend": trend,
    }


# ------------------------------------------------------------------- report

def _syd(now):
    return (now + dt.timedelta(hours=10)).strftime("%d-%b %H:%M AEST")


def render(pnl, trades, bus, window, now, reds, ambers, trades_limit=None):
    days = WINDOWS[window]
    out = []
    out.append(f"# Live P&L audit — {window} — "
               f"{now.strftime('%Y-%m-%d %H:%MZ')} ({_syd(now)})")

    out.append("\n## Live books (venue truth, liveness first)\n")
    out.append("| book | age | equity | pnl_abs | manual attested | "
               "bot realised (ledger) | unattributed flattens | open | "
               "clip | notes |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    total_pnl = 0.0
    for row in live_rows(pnl):
        ex = row.get("extra") or {}
        att = attribution(row, ledger_for(trades, row.get("bot")))
        total_pnl += att["pnl_abs"]
        age = row.get("age_sec")
        notes = []
        if att["attestation_gap"]:
            notes.append("ATTESTATION NOT LANDED")
        ev = ex.get("entry_vetoes") or {}
        if ev.get("live_clip_scale") not in (None, 1.0, 1):
            notes.append(f"clip x{ev.get('live_clip_scale')}")
        out.append(
            f"| {row.get('bot')} | {'' if age is None else str(int(age))+'s'} "
            f"| {float(row.get('equity') or 0):.2f} "
            f"| {att['pnl_abs']:+.2f} | {att['manual_attested']:+.2f} "
            f"| {att['bot_realised_ledger']:+.2f} "
            f"| {att['unattributed_flattens']} "
            f"| {row.get('open_trades')} | {ex.get('clip_usd')} "
            f"| {'; '.join(notes) or '—'} |")
    out.append(f"\nLive rows combined pnl_abs: **{total_pnl:+.2f}** — the "
               "attribution columns say how much of that is the bots'.")

    out.append(f"\n## Closes, last {days}d (every book, ledger)\n")
    out.append("| book | n | $ | mean %/t | t | win |")
    out.append("|---|---|---|---|---|---|")
    wt = window_rows(trades, days, now)
    fleet_total = 0.0
    for bot in sorted(wt, key=lambda b: sum(
            float(r.get("pnl_abs") or 0) for r in wt[b])):
        s = book_stats(wt[bot])
        fleet_total += s["total"]
        ttxt = "—" if math.isnan(s["t"]) else f"{s['t']:+.2f}"
        out.append(f"| {bot} | {s['n']} | {s['total']:+.2f} "
                   f"| {s['mean_pct']:+.3f} | {ttxt} "
                   f"| {100*s['wins']/s['n']:.0f}% |")
    out.append(f"| **fleet** |  | **{fleet_total:+.2f}** |  |  |  |")

    out.append("\n## Live robustness/execution coverage matrix\n")
    out.append("| check | coverage | status |")
    out.append("|---|---:|---|")
    for c in coverage_matrix(pnl, trades, bus):
        if c["total"] <= 0:
            cov = "0/0"
            st = "🟡 no live sample"
        elif c["have"] == c["total"]:
            cov = f"{c['have']}/{c['total']}"
            st = "✅ present"
        elif c["have"] == 0:
            cov = f"{c['have']}/{c['total']}"
            st = "🔴 missing"
        else:
            cov = f"{c['have']}/{c['total']}"
            st = "🟡 partial"
        out.append(f"| {c['name']} | {cov} | {st} |")

    pe = progression_estimates(pnl, trades, bus, reds, ambers)
    out.append("\n## Progression estimates (advisory)\n")
    out.append("| metric | value |")
    out.append("|---|---:|")
    out.append(f"| Telemetry coverage score | {pe['coverage_score_pct']:.1f}% |")
    out.append(f"| Reliability drag (current red/amber load) | -{pe['reliability_drag_pct']:.1f}% |")
    out.append(f"| Net progression score | {pe['net_progress_pct']:.1f}% ({pe['trend']}) |")
    out.append(f"| Optimization headroom estimate | {pe['optimization_headroom_pct']:.1f}% |")
    out.append(f"| Coverage checks (full / partial / missing / no-sample) | "
               f"{pe['checks_full']} / {pe['checks_partial']} / "
               f"{pe['checks_missing']} / {pe['checks_no_sample']} |")

    gov = governor_state(bus)
    out.append("\n## What is restricting live size right now\n")
    out.append(f"- fleet clip_scale **{gov['fleet_clip_scale']}** "
               f"(7d dd: {gov['fleet_dd_7d']})"
               + (" — carried while abstaining"
                  if gov["carried_while_abstaining"] else ""))
    for lv in gov["live_levers"]:
        out.append(f"- `{lv['name']}` = {lv['value']} — {lv['reason']}")
    if not gov["live_levers"]:
        out.append("- no live-lane levers open")

    out.append("\n## Sync — declared vs effective\n")
    for r in reds:
        out.append(f"- 🔴 {r}")
    for a in ambers:
        out.append(f"- 🟡 {a}")
    if not reds and not ambers:
        out.append("- clean: every row fresh, no attestation gaps, no aged "
                   "asks, one build stamp")

    return "\n".join(out) + "\n"


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pnl-json", default=f"{DASH}/pnl.json")
    ap.add_argument("--trades-json",
                    default=f"{DASH}/trades.json?source=paper&limit=5000")
    ap.add_argument("--bus-json", default=f"{DASH}/bus.json")
    ap.add_argument("--window", choices=sorted(WINDOWS), default="daily")
    ap.add_argument("--trades-limit", type=int, default=5000,
                    help="the limit the trades URL carries, for the "
                         "truncation signature check")
    ap.add_argument("--repo-root", default=None,
                    help="git checkout for the queue-sweep proxy; omit "
                         "outside CI")
    ap.add_argument("--gha", action="store_true",
                    help="also write the report to $GITHUB_STEP_SUMMARY and "
                         "the findings to $GITHUB_OUTPUT")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    now = dt.datetime.now(dt.timezone.utc)
    pnl = fetch_json(args.pnl_json)
    if not pnl or not (pnl.get("bots")):
        print("live_pnl_audit: pnl feed DARK/EMPTY — fail-closed, exit 2 "
              "((jc): a vacuous green is how a dead feed reads as health)")
        return 2
    trades_payload = fetch_json(args.trades_json)
    trades = (trades_payload or {}).get("trades")
    bus = fetch_json(args.bus_json)
    if trades is None:
        print("live_pnl_audit: trades feed dark — attribution and window "
              "tables will be partial; findings below reflect that")
        trades = []
    if bus is None:
        print("live_pnl_audit: bus feed dark — governor/docket sections "
              "will be partial")
        bus = {}

    reds, ambers = sync_findings(
        pnl, trades, bus, now, repo_root=args.repo_root,
        trades_limit=args.trades_limit if trades else None)
    report = render(pnl, trades, bus, args.window, now, reds, ambers)
    print(report)

    if args.gha:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as f:
                f.write(report)
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a") as f:
                f.write(f"reds={len(reds)}\nambers={len(ambers)}\n")

    if reds:
        print(f"live_pnl_audit: {len(reds)} RED finding(s) — exit 1")
        return 1
    return 0


# ----------------------------------------------------------------- selftest

def _fixture():
    """A minimal payload in the dashboard's OWN shape (the fields asserted
    here are the ones the real feed carries — see tests/autonomy/
    test_live_pnl_audit.py, which drives the same functions over a captured
    real payload so a fixture drift cannot go green on its own)."""
    now = dt.datetime(2026, 8, 25, 11, 0, tzinfo=dt.timezone.utc)
    pnl = {"bots": [
        {"bot": "live-a", "status": "online", "age_sec": 60, "equity": 300.0,
         "pnl_abs": -60.0, "open_trades": 1,
         "extra": {"venue": "lighter_live", "build": "aaa",
                   "manual_pnl_usd": 0.0, "clip_usd": 100.0,
                   "entry_vetoes": {"live_clip_scale": 0.75}}},
        {"bot": "shadow-b", "status": "online", "age_sec": 400000,
         "equity": 1000.0, "pnl_abs": 0.0, "open_trades": 0,
         "extra": {"build": "aaa"}},
        {"bot": "shadow-c", "status": "online", "age_sec": 120,
         "equity": 1000.0, "pnl_abs": 5.0, "open_trades": 0,
         "extra": {"build": "zzz-shadow-image"}},
        {"bot": "live-d", "status": "online", "age_sec": 90, "equity": 300.0,
         "pnl_abs": 1.0, "open_trades": 0,
         "extra": {"venue": "lighter_live", "build": "bbb",
                   "manual_pnl_usd": 0.0, "clip_usd": 100.0}},
    ]}
    trades = [
        {"bot": "live-a", "pair": "ZRO", "pnl_abs": 0.0, "pnl_pct": 0.0,
         "reason": "long_daily_loss", "entry_price": None,
         "closed_at": "2026-08-24T12:00:00+00:00"},
        {"bot": "live-a", "pair": "QQQ", "pnl_abs": 2.5, "pnl_pct": 0.01,
         "reason": "long_roi", "entry_price": 700.0,
         "closed_at": "2026-08-24T13:00:00+00:00"},
        {"bot": "shadow-c", "pair": "ETH", "pnl_abs": 5.0, "pnl_pct": 0.02,
         "reason": "long_roi", "entry_price": 2000.0,
         "closed_at": "2026-08-20T11:00:00+00:00"},
    ]
    bus = {"fleet_risk": {"clip_scale": 0.5, "fleet_dd_7d": None},
           "fleet_tuning": {"levers": {
               "live.a.clip_scale": {"lane": "lighter-live", "value": 0.75,
                                     "reason": "backstop"}}},
           "golive_readiness": {"decision_docket": [
               {"book": "shadow-b", "reason": "unreachable",
                "days_held": 18.9, "asks": "keep-or-retire"}]}}
    return now, pnl, trades, bus


def selftest():
    now, pnl, trades, bus = _fixture()

    assert [b["bot"] for b in live_rows(pnl)] == ["live-a", "live-d"], \
        "live selection must key on extra.venue, nothing else"

    spread = build_spread(pnl)
    assert set(spread) == {"aaa", "bbb"}, \
        "spread compares the LIVE trio only — a shadow image's stamp " \
        "legitimately differs ((fd)) and must never enter it"

    st = stale_rows(pnl)
    assert [(r[0]["bot"]) for r in st] == ["shadow-b"], \
        "the 400ks row and only that row is stale"

    att = attribution(pnl["bots"][0], ledger_for(trades, "live-a"))
    assert att["attestation_gap"], \
        "zero-basis daily_loss flatten + manual 0.0 must flag the gap"
    assert att["unattributed_flattens"] == 1 and \
        att["flatten_pairs"] == ["ZRO"]
    assert abs(att["bot_realised_ledger"] - 2.5) < 1e-9

    pnl["bots"][0]["extra"]["manual_pnl_usd"] = -66.4
    att2 = attribution(pnl["bots"][0], ledger_for(trades, "live-a"))
    assert not att2["attestation_gap"], \
        "a set attestation must clear the gap"
    pnl["bots"][0]["extra"]["manual_pnl_usd"] = 0.0

    w = window_rows(trades, 1, now)
    assert "shadow-c" not in w and len(w.get("live-a", [])) == 2, \
        "daily window keeps only the last 24h"

    gov = governor_state(bus)
    assert gov["carried_while_abstaining"], \
        "scale<1 with dd=None is the carried-restriction state"
    assert gov["live_levers"] and \
        gov["live_levers"][0]["name"] == "live.a.clip_scale"

    aged = docket_aging(bus)
    assert aged and aged[0]["days_held"] == 18.9

    reds, ambers = sync_findings(pnl, trades, bus, now,
                                 trades_limit=len(trades))
    assert any("FROZEN" in r for r in reds), "stale row must be RED"
    assert any("attestation" in r.lower() for r in reds), \
        "attestation gap must be RED"
    assert any("truncation" in a for a in ambers), \
        "len(trades)==limit is the (qz) truncation signature"

    report = render(pnl, trades, bus, "daily", now, reds, ambers)
    assert "FROZEN" in report and "live-a" in report

    print("live_pnl_audit selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
