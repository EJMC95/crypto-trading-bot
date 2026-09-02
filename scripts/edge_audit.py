#!/usr/bin/env python3
"""EDGE AUDIT — does a book have a repeatable edge, or a few lucky trades?

**Eamon, 2-Sep:** *"Identify whether profits come from a repeatable signal or
from a small number of lucky trades."*

THE GAP THIS FILLS. The fleet grades books six ways (`golive_readiness`), ranks
their capital by a lower bound (`fleet_allocation`), referees their winners
(`winners_docket`) and prices their ceilings (`ceiling`). **Not one of those
instruments computes a profit factor, a Sharpe, a Sortino, a recovery time, a
loss streak, a concentration share, a break-even cost or a cross-book
correlation** — measured 2-Sep by grepping the whole tree. So the fleet could
say whether a book PASSES and never whether its pass is one coin, one week or
one trade, and it could not say whether two books are the same bet.

WHAT IT DOES NOT DO, on purpose. It computes NO verdict the fleet already owns
and it re-implements NOTHING:

  * the sample (which trades describe the book as it runs today) is
    `golive_readiness.era_rows` — identity import, the (hq) rule;
  * the phantom filter is `golive_readiness.is_phantom_close` — (th)/(vd);
  * the retired-sleeve drop is `golive_readiness.drop_retired_sleeves` — (nk);
  * `n`, `mean`, `t`, halves, maxDD, MDE are `golive_readiness.stats`;
  * the cluster-robust SE is `golive_readiness.cluster_se` — (kw);
  * the critical value is `fleet_allocation.t_crit` — (ua)'s single owner;
  * BH-FDR across multiple books is `winners_docket.bh_survivors`.

A second copy of any of those would be a second rule ((hj)), and this fleet has
paid for that twice — the review that graded a book at n=84/t=2.77 while the
grader read n=59/t=0.33, and the three cluster-`t` implementations of (ug).

THE CALIBRATION GATE IS THE POINT, and it is the (gx) rule applied to an
auditor: **a harness that cannot reproduce what the fleet's own grader
published may not say anything about it.** `calibrate()` compares this module's
per-book `n` / `mean` / `t` against the LIVE `golive-readiness` payload and
REFUSES — exit 2, no report — when they disagree beyond tolerance. Fail-CLOSED:
a dark or stale feed refuses too, because "no baseline" must never read as "no
disagreement".

WHAT IS NEW HERE, and why each one is not already answerable:

  * `profit_factor`, `avg_win`, `avg_loss`, `expectancy_usd` — a book can hold
    mean > 0 on a fat right tail or a high hit rate on a fat left one, and the
    gate's six bars cannot tell those apart (I15: win rate is not expectancy —
    and the mirror, expectancy is not shape).
  * `sharpe`, `sortino` — annualised at the book's OWN measured close rate, so
    a slow book is not flattered by a fast one's clock. Sortino because a
    funding book's upside variance is not risk.
  * `recovery_days` — the gate reads maxDD depth and never how long the hole
    lasted. A book that is 8% down for 40 days and a book 8% down for 2 hours
    are the same number to the gate and different books to hold.
  * `max_consec_loss` beside `mc_expected_streak` — a streak is only evidence
    when it exceeds what the book's own hit rate produces by chance, and this
    fleet reads streaks as decay routinely.
  * `top1_share` / `top3_share` / `top_coin_share` / `top_month_share` — the
    direct answer to Eamon's question, and the number that retired 🧙 Schwager
    (top 3 of 298 = 112% of total) and refused 🎯 the sniper's potency claim
    (ANSEM = 157% of a predecessor's lifetime).
  * `breakeven_cost_bps` — the INVERSION of a cost model rather than an
    assertion of one. Only 4 of 42 books record a per-fill spread, so a
    fleet-wide cost model would be mostly invented; what this asks instead is
    *how many bps of round-trip cost would zero this book's mean*, which is
    exact, needs no assumption, and answers "does it survive 2x/3x costs"
    directly against the fleet's own measured ~10-17bps.

Every number here is REPORTED. This module moves no capital, writes no lever,
promotes nothing and retires nothing — asserted by its own selftest.

CLI:
    python3 scripts/edge_audit.py                 # live feeds
    python3 scripts/edge_audit.py --ledger t.json --feed p.json --bus b.json
    python3 scripts/edge_audit.py --json          # machine-readable
    python3 scripts/edge_audit.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import golive_readiness as gr            # noqa: E402
import fleet_allocation as fa            # noqa: E402
import winners_docket as wd              # noqa: E402
import bot_pnl_store as store            # noqa: E402  (is_quarantined only; no DB)

DASH = os.environ.get(
    "PNL_DASHBOARD_URL",
    "https://pnl-dashboard-production-858c.up.railway.app").rstrip("/")

#: Agreement tolerances for the calibration gate. `n` must match EXACTLY — a
#: sample that differs by one row is a different sample, and every disagreement
#: this fleet has had between two graders was a sample disagreement, never a
#: rounding one. `mean`/`t` are compared at the published rounding.
CAL_N_EXACT = True
CAL_MEAN_TOL = 0.0015          # published mean_pct is rounded to 3dp
CAL_T_TOL = 0.02               # published t is rounded to 2dp

#: A book below this many closes gets its metrics computed and its VERDICT
#: withheld — the (ua) computability floor, same value, same reason: a variance
#: estimate from a handful of numbers cannot be repaired by a wider interval.
MIN_N = fa.MIN_N

#: Round-trip cost, in bps, that the fleet has MEASURED on its own fills.
#: `(qq)`: mean 17.49bps, p90 398bps below $0.1M/day volume. 🪁 band-kelly's own
#: recorded per-fill spread has a median of 10.18bps (n=383, this ledger).
#: Used ONLY to express a book's break-even cost as a multiple — never added to
#: a P&L, because shadow fills already walk the book and live fills are real.
MEASURED_RT_BPS = float(os.environ.get("EDGE_AUDIT_RT_BPS", "17.49"))

SECONDS_PER_YEAR = 365.25 * 86400.0


# ---------------------------------------------------------------- loading

def _get(url, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _load_json(path):
    with open(path) as fh:
        return json.load(fh)


def load_trades(ledger=None, limit=5000):
    """The paper ledger, with the (qz) truncation refusal — the ONE owner.

    A row count equal to the cap is a truncation signature, not a complete
    history, so this REFUSES rather than hand a silently sampled ledger to a
    grader. Split out of `load()` at (xk) because three studies had each
    re-implemented the fetch and dropped the refusal with it — a second copy
    of a rule is a second rule, and here the second one had no rule at all.
    """
    tr = (_load_json(ledger) if ledger
          else _get(f"{DASH}/trades.json?source=paper&limit={int(limit)}"))
    trades = tr["trades"] if isinstance(tr, dict) else tr
    if len(trades) >= limit:
        raise SystemExit(
            f"REFUSING: the ledger returned exactly its own cap ({len(trades)} "
            f">= limit {limit}) — that is a truncation signature, not a "
            f"complete history. Raise --limit or page per book.")
    return trades


def load(ledger=None, feed=None, bus=None, limit=5000):
    """(trades, books, published_grades). Any of the three may be a local path.

    The ledger half is `load_trades`, which carries the (qz) truncation refusal.
    """
    trades = load_trades(ledger, limit)
    bo = _load_json(feed) if feed else _get(f"{DASH}/pnl.json")
    books = bo["bots"] if isinstance(bo, dict) and "bots" in bo else bo
    bu = _load_json(bus) if bus else _get(f"{DASH}/bus.json")
    pub = (bu.get("golive_readiness") or {}) if isinstance(bu, dict) else {}
    return trades, books, pub


def _ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def side_of(r):
    """'long' | 'short' | None — from the side COLUMN, else the reason prefix.

    The fleet's exit convention is `<side>-<lens>_<exit>` (and `<side>_<exit>`
    on the books that never took a lens), so the prefix carries the side on the
    1,528 rows whose `side` column is null. Verified on this ledger: the two
    sources agree on 1,758 rows and disagree on ZERO, which is what makes the
    fallback a READ of the same fact rather than a guess ((I8): unknown
    degrades to unknown, never to a side).
    """
    s = r.get("side")
    if s in ("long", "short"):
        return s
    rs = str(r.get("reason") or "")
    for tok in ("long", "short"):
        if rs == tok or rs.startswith(tok + "-") or rs.startswith(tok + "_"):
            return tok
    return None


def shape(trades):
    """{bot: {"quads": [...], "rows": [...]}} — the grader's own selection.

    Rows carry the publisher's tuple layout exactly: (pct, abs, closed_dt,
    opened_raw, extra, tag, pair). `era_rows` indexes [0..4],
    `drop_retired_sleeves` reads [5], `class_split` reads [6] — appended, never
    inserted, per that module's own note.
    """
    by = defaultdict(list)
    for r in trades:
        bot = r.get("bot")
        if not bot or r.get("is_open"):
            continue
        if gr.is_phantom_close(r) or gr.is_adopted_close(r):   # (xq)
            continue
        # [2-Sep] THE PUBLIC FEED SKIPS THE QUARANTINE. `fetch_paper_trades`
        # (the grader's read) withholds `LEDGER_QUARANTINE` rows; the public
        # `/trades.json?source=paper` (`fetch_paper_rows`) does not — so an
        # outside consumer grades a sample the fleet's own grader refuses.
        # Found by this module's calibration gate on its first run: 🧘
        # douglas n=83 here vs n=81 published, the two being the (pv)
        # frozen-mark ROBO rows. Same owner, identity import, no second copy.
        if store.is_quarantined(bot, r.get("pair"), r.get("closed_at")):
            continue
        pct, closed = r.get("pnl_pct"), _ts(r.get("closed_at"))
        if not isinstance(pct, (int, float)) or closed is None:
            continue
        by[bot].append((float(pct), float(r.get("pnl_abs") or 0.0), closed,
                        r.get("opened_at"), r.get("extra"),
                        r.get("tag") or r.get("reason"), r.get("pair"), r))
    out = {}
    for bot, quads in by.items():
        quads.sort(key=lambda q: q[2])
        kept, _dropped = gr.drop_retired_sleeves(quads, None)
        ed = gr.era_rows(bot, [q[:7] for q in kept], detail=True)
        keys = {(round(s[0], 9), s[2]) for s in ed["scoped"]}
        rows = [q for q in kept if (round(q[0], 9), q[2]) in keys]
        out[bot] = {"scoped": ed["scoped"], "rows": rows,
                    "all_time": ed["all_time"], "era_iso": ed["iso"],
                    "era_src": ed["source"]}
    return out


# ---------------------------------------------------------------- calibration

def calibrate(shaped, published):
    """(ok, findings) — this module's sample against the LIVE grader's.

    Fail-CLOSED in every direction that matters: an absent, empty or stale
    published payload is NOT a pass, because the whole point of a gate is that
    silence cannot certify agreement ((po): a check that inspects nothing
    reports clean, and clean reads as evidence).
    """
    books = (published or {}).get("books") or {}
    if not books:
        return False, [("(feed)", "no published golive-readiness books to "
                                  "calibrate against — refusing to report")]
    upd = _ts((published or {}).get("updated"))
    if upd is None:
        return False, [("(feed)", "published payload carries no `updated` — "
                                  "cannot establish it is current")]
    age_h = (datetime.now(timezone.utc) - upd).total_seconds() / 3600.0
    ttl_h = float((published or {}).get("ttl_sec") or 43200) / 3600.0
    if age_h > ttl_h:
        return False, [("(feed)", f"published grade is {age_h:.1f}h old "
                                  f"against its own {ttl_h:.1f}h TTL")]
    bad, checked = [], 0
    for bot, pv in sorted(books.items()):
        mine = shaped.get(bot)
        if mine is None:
            bad.append((bot, "graded live and ABSENT from this ledger"))
            continue
        # SAME CLOCK. The grader published at `upd`; a close that landed after
        # it is in this ledger and not in that grade, and comparing the two
        # anyway would fail every fast book on every run for no reason. The
        # comparison sample is the rows closed AT OR BEFORE publish; the rows
        # after it are counted and reported, never silently dropped from the
        # audit itself (the audit uses the full sample — only the GATE trims).
        cmp_rows = [q for q in mine["scoped"] if q[2] <= upd]
        s = gr.stats(cmp_rows)
        checked += 1
        pn, pm, pt = pv.get("n"), pv.get("mean_pct"), pv.get("t")
        if CAL_N_EXACT and pn is not None and s.get("n") != pn:
            bad.append((bot, f"n {s.get('n')} != published {pn}"))
            continue
        if isinstance(pm, (int, float)) and s.get("mean_pct") is not None:
            if abs(100 * s["mean_pct"] - pm) > CAL_MEAN_TOL:
                bad.append((bot, f"mean {100*s['mean_pct']:.4f} != "
                                 f"published {pm}"))
        if isinstance(pt, (int, float)) and s.get("t") is not None:
            if abs(s["t"] - pt) > CAL_T_TOL:
                bad.append((bot, f"t {s['t']:.3f} != published {pt}"))
    if not checked:
        return False, [("(feed)", "zero books actually compared")]
    return (not bad), bad


# ---------------------------------------------------------------- metrics

def _quantile(sorted_xs, q):
    if not sorted_xs:
        return None
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    i = q * (len(sorted_xs) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (i - lo)


def shape_metrics(pcts, abss):
    """Profit factor, average win/loss, expectancy. Pure."""
    wins = [x for x in abss if x > 0]
    losses = [x for x in abss if x < 0]
    gw, gl = sum(wins), -sum(losses)
    out = {
        "n_win": len(wins), "n_loss": len(losses),
        "gross_win_usd": gw, "gross_loss_usd": -gl,
        "avg_win_usd": (gw / len(wins)) if wins else None,
        "avg_loss_usd": (-gl / len(losses)) if losses else None,
        "expectancy_usd": (sum(abss) / len(abss)) if abss else None,
        # A book with zero losing trades has an UNDEFINED profit factor, not an
        # infinite one — reported as None so a consumer cannot sort on inf.
        "profit_factor": (gw / gl) if gl > 0 else None,
    }
    pw = [x for x in pcts if x > 0]
    pl = [x for x in pcts if x < 0]
    out["avg_win_pct"] = (sum(pw) / len(pw)) if pw else None
    out["avg_loss_pct"] = (sum(pl) / len(pl)) if pl else None
    return out


def risk_metrics(pcts, abss, closes, book_usd=1000.0):
    """Sharpe, Sortino, realised maxDD, recovery time, loss streaks.

    Sharpe/Sortino are annualised at the book's OWN measured close rate
    (`closes/year` from its own span), never at a shared clock: a book closing
    twice a week and one closing forty times a day do not share a scaling, and
    borrowing one makes a slow book look like a fast one's cousin. Excess
    return is over ZERO, stated rather than assumed — a $1,000 paper book on a
    zero-fee venue has no financing leg, so a risk-free subtraction would be
    inventing a rate.
    """
    n = len(pcts)
    out = {"sharpe": None, "sortino": None, "max_dd_usd": None,
           "recovery_days": None, "max_consec_loss": None,
           "max_consec_win": None, "underwater_frac": None}
    if n < 2:
        return out
    span_d = (closes[-1] - closes[0]).total_seconds() / 86400.0
    per_year = (n / span_d * 365.25) if span_d > 0 else None
    mean = sum(pcts) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in pcts) / n)
    down = [x for x in pcts if x < 0]
    dsd = math.sqrt(sum(x * x for x in down) / n) if down else 0.0
    # Per-trade ratio FIRST — it is t/sqrt(n), needs no clock and is the
    # number two books of different speed can actually be compared on. The
    # annualised figure is beside it with the rate that produced it, because a
    # book eight days old at 2,400 closes/yr annualises to a Sharpe of 26 and
    # that says more about the clock than the edge.
    out["sharpe_per_trade"] = (mean / sd) if sd > 0 else None
    if per_year and sd > 0:
        out["sharpe"] = (mean / sd) * math.sqrt(per_year)
    if per_year and dsd > 0:
        out["sortino"] = (mean / dsd) * math.sqrt(per_year)
    out["closes_per_year"] = per_year
    out["span_days"] = span_d
    # Realised equity path, trade-sequenced — the same accumulation
    # `golive_readiness.stats` uses for its maxDD bar, extended with the two
    # things that bar cannot see: how long the hole lasted, and how much of the
    # book's life was spent inside one.
    eq = peak = 0.0
    dd = 0.0
    peak_at = closes[0]
    trough_at = None
    cur_uw_start = None
    uw_seconds = 0.0
    for x, ts in zip(abss, closes):
        eq += x
        if eq >= peak:
            if cur_uw_start is not None:
                uw_seconds += (ts - cur_uw_start).total_seconds()
                cur_uw_start = None
            peak, peak_at = eq, ts
        else:
            if cur_uw_start is None:
                cur_uw_start = ts
            if eq - peak < dd:
                dd, trough_at = eq - peak, ts
    if cur_uw_start is not None:
        uw_seconds += (closes[-1] - cur_uw_start).total_seconds()
    out["max_dd_usd"] = dd
    out["max_dd_frac"] = abs(dd) / book_usd if book_usd else None
    out["underwater_frac"] = (uw_seconds / (span_d * 86400.0)
                              if span_d > 0 else None)
    # Recovery: from the trough of the DEEPEST drawdown, how long until the
    # prior peak was regained? None = never regained, which is a different
    # state from "recovered instantly" and must not print as 0.
    if trough_at is not None:
        eq2, target, rec = 0.0, None, None
        run_peak = 0.0
        for x, ts in zip(abss, closes):
            eq2 += x
            run_peak = max(run_peak, eq2)
            if ts == trough_at:
                target = run_peak
            elif target is not None and eq2 >= target:
                rec = (ts - trough_at).total_seconds() / 86400.0
                break
        out["recovery_days"] = rec
        out["recovered"] = rec is not None
    streak = best_l = best_w = 0
    for x in abss:
        if x < 0:
            streak = streak - 1 if streak < 0 else -1
        elif x > 0:
            streak = streak + 1 if streak > 0 else 1
        else:
            streak = 0
        best_l = min(best_l, streak)
        best_w = max(best_w, streak)
    out["max_consec_loss"] = -best_l
    out["max_consec_win"] = best_w
    return out


# [2026-09-02, edge-audit follow-up] THE OWNER IS THE GRADER. This file
# simulated the longest losing run (2000 draws) and does not ship in any image;
# `golive_readiness.expected_streak` computes it EXACTLY (Feller's run
# recurrence) and publishes it on every book's `shape` block, so this is the
# same function by identity -- a second copy of a rule is a second rule ((hj)),
# and a monitor and an audit must never disagree about chance.
expected_streak = gr.expected_streak


def concentration(rows):
    """Is the profit a repeatable signal, or a handful of trades?

    Two families of number, because a share of NET is unbounded and a share
    of GROSS is not, and both are needed:

      * `best1/best3/best5_of_gross_wins` and `worst1/worst3_of_gross_losses`
        are in [0, 1] — what fraction of everything the book WON came from its
        best trade(s); of everything it LOST, from its worst.
      * `top1/top3_share_of_net`, computed only when net > 0 (a losing book has
        no profit to be concentrated) — and a value ABOVE 1.0 is the finding,
        not a bug: it means the rest of the book loses. That is the number
        that retired 🧙 Schwager (top 3 = 112% of total) and refused 🎯 the
        sniper's potency claim (one coin = 157% of a predecessor's lifetime).
      * `ex_top3_mean_pct` — the single most informative line: a book whose
        mean survives the removal of its three best trades has a distribution;
        one that does not has three trades.
    """
    abss = [q[1] for q in rows]
    total = sum(abss)
    out = {"total_usd": total, "n": len(abss)}
    if not abss:
        return out
    wins = sorted((a for a in abss if a > 0), reverse=True)
    losses = sorted(a for a in abss if a < 0)
    gw, gl = sum(wins), -sum(losses)
    if gw > 0:
        out["best1_of_gross_wins"] = wins[0] / gw
        out["best3_of_gross_wins"] = sum(wins[:3]) / gw
        out["best5_of_gross_wins"] = sum(wins[:5]) / gw
    if gl > 0:
        out["worst1_of_gross_losses"] = -losses[0] / gl
        out["worst3_of_gross_losses"] = -sum(losses[:3]) / gl
    if total > 0 and wins:
        out["top1_share_of_net"] = wins[0] / total
        out["top3_share_of_net"] = sum(wins[:3]) / total
    by_coin, by_month = defaultdict(float), defaultdict(float)
    n_coin, n_month = defaultdict(int), defaultdict(int)
    for q in rows:
        by_coin[str(q[6])] += q[1]
        n_coin[str(q[6])] += 1
        m = q[2].strftime("%Y-%m")
        by_month[m] += q[1]
        n_month[m] += 1
    out["n_coins"], out["n_months"] = len(by_coin), len(by_month)
    if total > 0:
        bc = max(by_coin.items(), key=lambda kv: kv[1])
        bm = max(by_month.items(), key=lambda kv: kv[1])
        out["top_coin"], out["top_coin_share_of_net"] = bc[0], bc[1] / total
        out["top_coin_n"] = n_coin[bc[0]]
        out["top_month"], out["top_month_share_of_net"] = bm[0], bm[1] / total
        out["top_month_n"] = n_month[bm[0]]
    else:
        wc = min(by_coin.items(), key=lambda kv: kv[1])
        out["worst_coin"], out["worst_coin_usd"] = wc[0], wc[1]
        out["worst_coin_n"] = n_coin[wc[0]]
        out["worst_coin_share_of_gross_losses"] = (-wc[1] / gl) if gl > 0 else None
    if len(rows) > 3:
        cut = set(sorted(range(len(rows)), key=lambda i: -abss[i])[:3])
        rest = [rows[i][0] for i in range(len(rows)) if i not in cut]
        out["ex_top3_mean_pct"] = sum(rest) / len(rest) if rest else None
        out["ex_top3_total_usd"] = total - sum(wins[:3]) if wins else total
    return out


def side_split(rows):
    """Long vs short, each graded through the gate's own `stats`."""
    out = {}
    for side in ("long", "short", None):
        sel = [q for q in rows if side_of(q[7]) == side]
        if not sel:
            continue
        s = gr.stats([(q[0], q[1], q[2]) for q in sel])
        key = side or "unknown"
        out[key] = {"n": s.get("n"), "mean_pct": s.get("mean_pct"),
                    "t": s.get("t"), "net_usd": sum(q[1] for q in sel)}
    return out


def breakeven_cost_bps(mean_pct, per_trade_rt_bps=MEASURED_RT_BPS):
    """How many bps of ADDITIONAL round-trip cost zero this book's mean.

    The inversion of a cost model rather than an assertion of one. Only 4 of 42
    books in this ledger record a per-fill spread, so a fleet-wide cost model
    would be mostly invented — and a missing cost that defaults to free is
    exactly the defect `fleet_bus.recorded_cost_bps` was written to correct.
    What IS exact is the distance between a book's measured mean and zero.

    Returns (bps, multiple_of_measured). A book whose mean is already <= 0 has
    no margin to price: (0.0, 0.0), never a negative "capacity".
    """
    if mean_pct is None:
        return None, None
    bps = max(0.0, mean_pct * 1e4)
    mult = (bps / per_trade_rt_bps) if per_trade_rt_bps else None
    return bps, mult


def audit_book(bot, shaped_entry, book_usd=1000.0):
    rows = shaped_entry["rows"]
    scoped = shaped_entry["scoped"]
    s = gr.stats(scoped)
    if s.get("n", 0) < 2:
        return {"bot": bot, "n": s.get("n", 0), "why": s.get("why")}
    pcts = [q[0] for q in rows]
    abss = [q[1] for q in rows]
    closes = [q[2] for q in rows]
    out = {"bot": bot, "era": shaped_entry["era_iso"],
           "era_src": shaped_entry["era_src"],
           "n": s["n"], "n_alltime": len(shaped_entry["all_time"]),
           "mean_pct": s["mean_pct"], "t": s["t"],
           "se_pct": s.get("se_pct"), "mde80_pct": s.get("mde80_pct"),
           "win_rate": s.get("win_rate"), "realised_usd": s.get("realised_usd"),
           "usd_per_day": s.get("usd_per_day"),
           "h1": s.get("h1"), "h2": s.get("h2"),
           "cluster": s.get("cluster")}
    out.update(shape_metrics(pcts, abss))
    out.update(risk_metrics(pcts, abss, closes, book_usd))
    out["concentration"] = concentration(rows)
    out["sides"] = side_split(rows)
    be, mult = breakeven_cost_bps(s["mean_pct"])
    out["breakeven_cost_bps"] = be
    out["cost_headroom_x"] = mult
    # "costs 2x" = the measured cost added ONCE on top of what the ledger
    # already carries; "3x" = twice. So the mean survives costs 2x when its
    # break-even headroom is >= 1 measured cost, 3x when >= 2.
    out["survives_costs_2x"] = (mult is not None and mult >= 1.0)
    out["survives_costs_3x"] = (mult is not None and mult >= 2.0)
    if out["n_loss"]:
        out["expected_streak"] = expected_streak(
            out["n"], out["n_loss"] / out["n"])
    # The one-sided lower bound on the mean, through the allocation organ's own
    # owner so the critical value cannot drift from the one that ranks capital.
    out["lower_bound_pct"] = fa.lower_bound(pcts)
    out["t_crit"] = fa.t_crit(len(pcts))
    return out


# ---------------------------------------------------------------- portfolio

def daily_pnl(rows):
    """{date: usd} realised P&L by UTC close date."""
    out = defaultdict(float)
    for q in rows:
        out[q[2].date()] += q[1]
    return dict(out)


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def correlation_matrix(by_bot_daily, min_overlap=10):
    """{(a, b): (rho, n_days)} on OVERLAPPING calendar days only.

    Overlap, not union: a day one book traded and the other did not is not a
    zero return for the idle book — it is a day with no observation, and
    filling it with 0.0 manufactures independence (it drags every correlation
    toward zero exactly on the thin books where the question matters).
    """
    bots = sorted(by_bot_daily)
    out = {}
    for i, a in enumerate(bots):
        for b in bots[i + 1:]:
            days = sorted(set(by_bot_daily[a]) & set(by_bot_daily[b]))
            if len(days) < min_overlap:
                continue
            rho = _pearson([by_bot_daily[a][d] for d in days],
                           [by_bot_daily[b][d] for d in days])
            if rho is not None:
                out[(a, b)] = (rho, len(days))
    return out


def effective_bets(weights, corr):
    """Correlation-aware N_eff = (sum w)^2 / (w' C w), C from `corr` (1 on the
    diagonal, 0 where unmeasured — stated: an UNMEASURED pair is treated as
    independent here, which OVERSTATES diversification, so this number is an
    upper bound on the true N_eff, never a floor).

    The I22 defect this replaces, quoted from `fleet_risk.py:239-254`: it
    publishes `long_effective_n` as 1/HHI over DISTINCT SYMBOLS, so 17 longs on
    17 different names read as 17.0 independent bets today — while (I22)
    measured 8 crypto markets at mean pairwise rho +0.545 to be **1.35** bets.
    Symbol count is not bet count.
    """
    bots = sorted(weights)
    tot = sum(weights[b] for b in bots)
    if tot <= 0:
        return None
    var = 0.0
    for a in bots:
        for b in bots:
            if a == b:
                c = 1.0
            else:
                c = corr.get((a, b), corr.get((b, a), (0.0, 0)))[0]
            var += weights[a] * weights[b] * c
    return (tot * tot / var) if var > 0 else None


def coholding(shaped, bots, step_s=3600):
    """How often two books hold the SAME COIN at the SAME TIME — the direct
    test of "are several bots secretly making the same trade".

    Sampled hourly over the union span. Returns per-pair the fraction of hours
    in which BOTH books were in the market where they shared >=1 coin, plus the
    fleet-wide concentration: the max number of living books simultaneously
    long or short one coin.
    """
    holds = {}
    lo, hi = None, None
    for b in bots:
        iv = []
        for q in shaped[b]["rows"]:
            o = _ts(q[3])
            if o is None:
                continue
            iv.append((o, q[2], str(q[6]), side_of(q[7])))
            lo = o if lo is None or o < lo else lo
            hi = q[2] if hi is None or q[2] > hi else hi
        holds[b] = iv
    if lo is None:
        return {}
    pair_both = defaultdict(int)
    pair_same = defaultdict(int)
    max_stack = (0, None, None)      # (books, "coin/side", iso)
    t = lo.timestamp()
    end = hi.timestamp()
    stack_hist = defaultdict(int)
    while t <= end:
        now = datetime.fromtimestamp(t, tz=timezone.utc)
        live = {}
        for b, iv in holds.items():
            s = {(c, sd) for (o, c_, c, sd) in iv if o <= now < c_}
            if s:
                live[b] = s
        bl = sorted(live)
        for i, a in enumerate(bl):
            for b in bl[i + 1:]:
                pair_both[(a, b)] += 1
                if live[a] & live[b]:
                    pair_same[(a, b)] += 1
        by_coin = defaultdict(int)
        for b, s in live.items():
            for c, sd in s:
                by_coin[(c, sd)] += 1
        if by_coin:
            k, v = max(by_coin.items(), key=lambda kv: kv[1])
            stack_hist[v] += 1
            if v > max_stack[0]:
                max_stack = (v, f"{k[0]}/{k[1]}", now.isoformat())
        t += step_s
    pairs = {}
    for k, both in pair_both.items():
        if both >= 24:
            pairs["|".join(k)] = {"hours_both_in": both,
                                  "hours_same_coin": pair_same[k],
                                  "same_coin_frac": pair_same[k] / both}
    return {"pairs": pairs, "max_stack": {"books": max_stack[0],
                                         "coin_side": max_stack[1],
                                         "at": max_stack[2]},
            "stack_hist": dict(stack_hist)}


def drawdown_overlap(by_bot_daily, bots):
    """Days on which >= k books were simultaneously in a realised drawdown.

    A portfolio's tail is the days its books are ALL underwater, and nothing in
    the fleet counts those. Returns the histogram of "how many books were in
    drawdown" over the union of trading days, and the worst single day for
    the equal-weight sum.
    """
    all_days = sorted({d for b in bots for d in by_bot_daily.get(b, {})})
    if not all_days:
        return {}
    under = {}
    for b in bots:
        eq = peak = 0.0
        uw = {}
        for d in all_days:
            eq += by_bot_daily.get(b, {}).get(d, 0.0)
            peak = max(peak, eq)
            uw[d] = eq < peak - 1e-9
        under[b] = uw
    hist = defaultdict(int)
    worst = (0.0, None)
    for d in all_days:
        k = sum(1 for b in bots if under[b][d])
        hist[k] += 1
        s = sum(by_bot_daily.get(b, {}).get(d, 0.0) for b in bots)
        if s < worst[0]:
            worst = (s, d.isoformat())
    n_b = len(bots)
    return {"days": len(all_days), "books": n_b,
            "hist_books_in_dd": dict(sorted(hist.items())),
            "frac_days_majority_in_dd": sum(v for k, v in hist.items()
                                            if k > n_b / 2) / len(all_days),
            "worst_fleet_day_usd": worst[0], "worst_fleet_day": worst[1]}


def _pair_out(kv):
    (a, b), (rho, n) = kv
    return {"pair": f"{a}|{b}", "rho": rho, "days": n}


def portfolio(shaped, bots, book_usd=1000.0):
    daily = {b: daily_pnl(shaped[b]["rows"]) for b in bots}
    corr = correlation_matrix(daily)
    rhos = [v[0] for v in corr.values()]
    # Equal weights — every shadow book IS $1,000 by construction, and the live
    # trio's real equity is published, so this is the fleet as it is funded.
    w = {b: 1.0 for b in bots}
    return {
        "n_books": len(bots),
        "n_pairs_measured": len(corr),
        "mean_pairwise_rho": (sum(rhos) / len(rhos)) if rhos else None,
        "max_pairwise": (_pair_out(max(corr.items(), key=lambda kv: kv[1][0]))
                         if corr else None),
        "min_pairwise": (_pair_out(min(corr.items(), key=lambda kv: kv[1][0]))
                         if corr else None),
        "n_eff_equal_weight": effective_bets(w, corr),
        "n_eff_symbol_count_would_say": len(bots),
        "corr": {f"{a}|{b}": {"rho": r, "days": n}
                 for (a, b), (r, n) in sorted(corr.items())},
        "coholding": coholding(shaped, bots),
        "dd_overlap": drawdown_overlap(daily, bots),
    }


# ---------------------------------------------------------------- monte carlo

def block_bootstrap(seq, rnd, block=1, k=None):
    """One resample of `seq` of length `k` (default len(seq)) in blocks of
    `block` consecutive items, wrapping. block=1 is the plain iid bootstrap;
    block>1 preserves the local dependence (kw) measured in batch-closing
    books. Uses `random.choices` for the starts so a 12-month path of a few
    thousand trades costs microseconds, not a Python loop per trade."""
    n = len(seq)
    k = n if k is None else k
    if block <= 1:
        return rnd.choices(seq, k=k)
    starts = rnd.choices(range(n), k=(k + block - 1) // block)
    out = []
    for i in starts:
        out.extend(seq[(i + j) % n] for j in range(block))
    return out[:k]


def median_clip_usd(pcts, abss):
    """The book's own dollars-per-unit-return, i.e. its effective clip, as a
    MEDIAN over trades so a live book whose clip moved 4x (🙏 avo's deposit)
    is not scaled by one vintage. None when nothing is priceable."""
    ratios = sorted(abs(a) / abs(p) for p, a in zip(pcts, abss)
                    if isinstance(p, (int, float)) and p not in (0, 0.0)
                    and isinstance(a, (int, float)))
    return _quantile(ratios, 0.5) if ratios else None


def monte_carlo(pcts, abss, closes_per_year, book_usd=1000.0,
                horizons_months=(3, 6, 12), draws=500, seed=7,
                cost_mults=(0.0, 1.0, 2.0), rt_bps=MEASURED_RT_BPS,
                block=None, clip_usd=None):
    """Reshuffle the book's OWN trades at its OWN rate and read the outcome
    distribution. Answers the four questions asked, and only those:

      P(loss over h months)       — fraction of paths ending below zero;
      P(ruin)                     — fraction of paths that touch -100% of the
                                    book; the path STOPS there, because a book
                                    that has lost everything does not keep
                                    compounding a linear sum to -900%;
      drawdown to prepare for     — p50 / p95 / p99 of path maxDD, as a
                                    fraction of the BOOK;
      survives costs 2x / 3x      — the same paths with the fleet's measured
                                    round-trip cost ADDED once (costs 2x) or
                                    twice (costs 3x) per trade. `0x` is the
                                    ledger AS RECORDED — shadow fills already
                                    walk the book and live fills are real, so
                                    adding a cost to the base case would
                                    double-count it (the first cut did, and
                                    its "1x" column read a book at twice its
                                    loss);
      block size                  — the (kw) cluster width, so a batch-closing
                                    book is not resampled as if its legs were
                                    independent.

    THE SCALE IS THE BOOK, NOT THE CLIP — and the first cut of this got it
    wrong. `pnl_pct` is a return on the CLIP; summed as if it were a return on
    the book, a 12-month path of 🛢️ garrett read −2082%. Every per-trade
    return is converted to a book fraction through the book's own median clip
    (`median_clip_usd`) before it is summed, and the payload carries the
    conversion so a reader can undo it.

    A bootstrap cannot see a regime the sample never contained (item 18: the
    tape is one falling-BTC regime and the oracle's whole 30-day history is
    one rising one), so every number here is CONDITIONAL on the book's own
    history repeating in distribution. Stated on the payload, not inferred.
    """
    n = len(pcts)
    if n < 2 or not closes_per_year:
        return {"why": "too few closes or no rate"}
    clip = clip_usd if clip_usd else median_clip_usd(pcts, abss)
    if not clip or not book_usd:
        return {"why": "no priceable clip — cannot scale trades to the book"}
    k_book = clip / book_usd
    rnd = random.Random(seed)
    block = max(1, min(int(block or 1), n))
    out = {"n": n, "closes_per_year": closes_per_year, "draws": draws,
           "block": block, "clip_usd": clip, "book_usd": book_usd,
           "conditional_on_sample": True, "horizons": {},
           "labels": {"0x": "as recorded", "1x": "costs 2x (measured cost "
                      "added once)", "2x": "costs 3x (added twice)"}}
    # HOW FAR PAST THE SAMPLE EACH HORIZON REACHES. A book graded on four days
    # of closes (👩 mum's live era at the time of writing) extrapolated to
    # twelve months is 91x its own evidence, and the bootstrap will print a
    # +1,700% median for it with a straight face, because it assumes the
    # sample's rate AND its regime hold for a year. That is I25's hot-window
    # shape as a forecast. The multiple is published per horizon so a reader
    # can see which numbers are a projection of the record and which are a
    # projection of a week — the report treats > 10x as not quotable.
    span_d = None
    if isinstance(pcts, list) and closes_per_year:
        span_d = n / closes_per_year * 365.25
    out["sample_span_days"] = span_d
    for h in horizons_months:
        n_h = max(1, int(round(closes_per_year * h / 12.0)))
        for km in cost_mults:
            cost = (km * rt_bps / 1e4) if km else 0.0
            finals, dds, ruined = [], [], 0
            for _ in range(draws):
                path = block_bootstrap(pcts, rnd, block, k=n_h)
                eq = peak = dd = 0.0
                for x in path:
                    eq += (x - cost) * k_book
                    if eq <= -1.0:            # ruin: the book is gone
                        eq = -1.0
                        ruined += 1
                        dd = min(dd, eq - peak)
                        break
                    if eq > peak:
                        peak = eq
                    elif eq - peak < dd:
                        dd = eq - peak
                finals.append(eq)
                dds.append(-dd)
            finals.sort()
            dds.sort()
            out["horizons"][f"{h}m@{km:g}x"] = {
                "trades": n_h,
                "extrapolation_x": (h * 30.44 / span_d) if span_d else None,
                "p_loss": sum(1 for f in finals if f < 0) / draws,
                "p_ruin": ruined / draws,
                "ret_p05": _quantile(finals, 0.05),
                "ret_p50": _quantile(finals, 0.50),
                "ret_p95": _quantile(finals, 0.95),
                "dd_p50": _quantile(dds, 0.50),
                "dd_p95": _quantile(dds, 0.95),
                "dd_p99": _quantile(dds, 0.99),
            }
    return out


def n_for_significance(mean, sd, t_bar=2.0):
    """Closes needed for t to reach `t_bar` at the observed mean/sd — the
    fleet's own `n_req = n·(T/t)²` shape ((ks)), stated here as the closed form
    so the caller does not need a current n. None when the mean is <= 0: a
    losing book never reaches a positive bar and reporting a number for it is
    the `n_needed` defect (kh) refused."""
    if mean is None or sd is None or mean <= 0 or sd <= 0:
        return None
    return int(math.ceil((t_bar * sd / mean) ** 2))


def rolling_stability(pcts, window=30):
    """Sign stability of non-overlapping `window`-close means — a poor man's
    walk-forward on a LIVE ledger, where every window after the first is
    out-of-sample by construction. Returns the fraction of windows positive
    and the list of window means."""
    if len(pcts) < 2 * window:
        return None
    means = []
    for i in range(0, len(pcts) - window + 1, window):
        w = pcts[i:i + window]
        means.append(sum(w) / len(w))
    return {"window": window, "n_windows": len(means),
            "frac_positive": sum(1 for m in means if m > 0) / len(means),
            "means_pct": [100 * m for m in means]}


# ---------------------------------------------------------------- breakdowns

def _grade(rows):
    """One bucket through the gate's own `stats` — n, mean%, t, net$."""
    if not rows:
        return None
    s = gr.stats([(q[0], q[1], q[2]) for q in rows])
    return {"n": s.get("n"), "mean_pct": s.get("mean_pct"), "t": s.get("t"),
            "net_usd": sum(q[1] for q in rows)}


def setup_of(r):
    """`<side>-<lens>_<exit>` -> lens; `<side>_<exit>` -> None (no lens)."""
    rs = str(r.get("reason") or r.get("tag") or "")
    head = rs.split("_", 1)[0]
    if "-" in head:
        return head.split("-", 1)[1]
    return None


def exit_of(r):
    rs = str(r.get("reason") or "")
    return rs.split("_", 1)[1] if "_" in rs else rs


def hold_bucket(hours):
    if hours is None:
        return "?"
    for lim, name in ((1, "<1h"), (4, "1-4h"), (24, "4-24h"), (72, "1-3d"),
                      (168, "3-7d")):
        if hours < lim:
            return name
    return ">7d"


def stress_at(ts, stress_series):
    """Venue premium stress (median |prem| bps across liquid books) at `ts`,
    from the scout's own `lighter-market.stress` history — the SAME number
    🎫 the taker's stress veto reads, so a 'high-stress' bucket here is a
    condition the fleet already acts on. None outside the recorded window."""
    if not stress_series:
        return None
    lo, hi = 0, len(stress_series) - 1
    if ts < stress_series[0][0] or ts > stress_series[-1][0]:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if stress_series[mid][0] <= ts:
            lo = mid
        else:
            hi = mid - 1
    t0, v = stress_series[lo]
    if (ts - t0).total_seconds() > 1800:
        return None
    return v


def breakdowns(rows, stress_series=None, stress_hi_bps=15.0):
    """Per-book slices, every one graded through the gate's own `stats`.

    Regime is the slice the ask names first and the one this module can least
    honestly supply, so the limit is stated on the payload rather than
    inferred: the venue's candle endpoint is refused from this environment and
    the fleet's own oracle read ONE regime ('risk-on uptrend', BTC LONG-window)
    in 413 of 413 snapshots across its whole 30-day history. A split needs two
    values. What IS split: venue STRESS at open (the taker's own veto quantity,
    15bps = its bar), UTC weekday, UTC hour-band, hold length, setup and exit.
    """
    out = {}
    by = defaultdict(lambda: defaultdict(list))
    for q in rows:
        r = q[7]
        o = _ts(q[3])
        by["side"][side_of(r) or "?"].append(q)
        by["setup"][setup_of(r) or "(none)"].append(q)
        by["exit"][exit_of(r)].append(q)
        by["coin"][str(q[6])].append(q)
        if o is not None:
            by["weekday"][o.strftime("%a")].append(q)
            hb = f"{(o.hour // 6) * 6:02d}-{(o.hour // 6) * 6 + 6:02d}Z"
            by["hour_band"][hb].append(q)
            by["hold"][hold_bucket((q[2] - o).total_seconds() / 3600)].append(q)
            if stress_series is not None:
                sv = stress_at(o, stress_series)
                key = ("?" if sv is None else
                       ("stress>=%g" % stress_hi_bps if sv >= stress_hi_bps
                        else "stress<%g" % stress_hi_bps))
                by["venue_stress"][key].append(q)
    for dim, buckets in by.items():
        out[dim] = {k: _grade(v) for k, v in
                    sorted(buckets.items(), key=lambda kv: -len(kv[1]))}
    out["regime_limit"] = ("candles endpoint refused by egress policy; oracle "
                           "read one regime in 413/413 snapshots — unsplittable")
    return out


def live_vs_shadow(shaped, live_bot, shadow_bot):
    """Execution audit on a PAIRED book: the live arm's realised per-trade
    return against its shadow twin's on the SAME coins over the OVERLAPPING
    window. The gap is what execution (real fills, real funding, real halts)
    cost — or earned — relative to the mark-fill twin. Paired by coin so a
    universe difference is not read as slippage ((uk)'s lesson, mirrored)."""
    L, S = shaped.get(live_bot), shaped.get(shadow_bot)
    if not L or not S or not L["rows"] or not S["rows"]:
        return None
    lo = max(L["rows"][0][2], S["rows"][0][2])
    hi = min(L["rows"][-1][2], S["rows"][-1][2])
    lr = [q for q in L["rows"] if lo <= q[2] <= hi]
    sr = [q for q in S["rows"] if lo <= q[2] <= hi]
    coins = {str(q[6]) for q in lr} & {str(q[6]) for q in sr}
    lr = [q for q in lr if str(q[6]) in coins]
    sr = [q for q in sr if str(q[6]) in coins]
    if not lr or not sr:
        return {"why": "no overlapping coins in the overlapping window"}
    gl, gs = _grade(lr), _grade(sr)
    return {"window": (lo.isoformat(), hi.isoformat()), "coins": len(coins),
            "live": gl, "shadow": gs,
            "gap_pp": 100 * (gl["mean_pct"] - gs["mean_pct"])
            if gl and gs and gl.get("mean_pct") is not None
            and gs.get("mean_pct") is not None else None}


# ---------------------------------------------------------------- out-of-sample

#: THE FOUNDING CLAIM each living book was minted on, as this file's own
#: history records it — the number a study said the book would earn, BEFORE
#: it had a ledger. The live era is the out-of-sample period BY CONSTRUCTION,
#: so live-vs-founding is the strongest overfitting test the fleet can run
#: without a replay: a rule fitted on the tape it was graded on either
#: reproduces on the trades it then took, or it does not.
#:
#: `mean_pct` is per trade, as a FRACTION (0.00397 = 0.397%/trade). `None`
#: where the record carries no per-trade founding number — stated, never
#: back-filled from a dollar total at a guessed clip. Every row cites where
#: it comes from so a reader can dispute the transcription, not the idea.
FOUNDING_CLAIMS = {
    "band-kelly-lshadow": dict(
        mean_pct=0.00397, t=3.58, n=65,
        src="(qw)/(rc) corrected snapfade +0.397%/trade t=+3.58; founding "
            "+0.605% t=+5.71 n=65 before the double-counted slippage"),
    "nav-cook-lshadow": dict(
        mean_pct=0.00367, t=2.74, n=216,
        src="STUDY_DISLOCATION_BAND_2026-08-19: n=216, +0.367%/trade, "
            "t=+2.74 at 4h, plateau 30m..8h"),
    "book-douglas-lshadow": dict(
        mean_pct=0.000271, t=0.50, n=641,
        src="(nt) corrected: n=641, +$17.38 at the $100 clip, t=0.50, h1 "
            "NEGATIVE — +0.027%/trade"),
    "freqtrade-georgia-v3-lshadow": dict(
        mean_pct=0.00151, t=6.09, n=1940,
        src="(vr): impulse_fade, n=1940, +0.151%/trade, t_cl +6.09, halves "
            "+0.237/+0.066 — hypothesis-grade, shadow only"),
    "perps-funding-carry-lshadow": dict(
        mean_pct=None, t=2.42, n=80,
        src="(fk) 29-Jul pooled: +$56.20 n=80 t=2.42 both halves — PRE-era, "
            "and (nc) later found ~$13 of that accrual phantom; no clean "
            "per-trade founding number survives"),
    "freqtrade-avo-maria-lshadow": dict(
        mean_pct=-0.00131, t=None, n=1156,
        src="(qu): exit-free excess over matched-random entries NEGATIVE at "
            "4h/8h/12h (-0.131/-0.171/-0.139%), P(random>=signal) 1.000 — "
            "kept by operator decision with a pre-registered revert"),
    "freqtrade-avo-maria-lighter": dict(
        mean_pct=-0.00131, t=None, n=1156,
        src="same signal as the shadow arm — (qu)"),
    "freqtrade-mum-lshadow": dict(
        mean_pct=None, t=None, n=None,
        src="(ro) v2: hypothesis-grade by declaration; the rsi<25 "
            "dose-response DECAYED through zero (+4.97 -> -0.41). No positive "
            "founding number was ever claimed"),
    "freqtrade-mum-lighter": dict(
        mean_pct=None, t=None, n=None,
        src="same rule as the shadow arm — (ro)"),
    "band-garrett-lshadow": dict(
        mean_pct=None, t=None, n=None,
        src="STUDY_THIN_TIER_MIN_VOL_2026-08-05: the [1e5,2e6) tier measured "
            "+$14.83 both halves at $25 clips — a dollar total, no per-trade "
            "number recorded"),
    "perps-funding-spread-lshadow": dict(
        mean_pct=None, t=None, n=None,
        src="(ia): K=5 hand list +13.7%, maxDD 9.6% on the Lighter replay — a "
            "book-level return, no per-trade number"),
    "lighter-perp-sniper-lshadow": dict(
        mean_pct=None, t=None, n=None,
        src="(qi)/(tx): founding thesis REFUTED — listing-pop TP hit 2 of 73; "
            "entries at random percentile 0.48-0.52"),
}


def oos_check(bot, audit):
    """Live era vs founding claim. Reports the founding number, the live
    number, and whether the live sample REJECTS the founding mean — i.e. the
    founding mean lies outside the live mean's one-sided interval at the
    fleet's own critical value. `verdict` is one of:
      reproduces | below-claim | rejects-claim | no-founding-number | too-thin
    """
    fc = FOUNDING_CLAIMS.get(bot)
    out = {"founding": fc}
    if not fc or fc.get("mean_pct") is None:
        out["verdict"] = "no-founding-number"
        return out
    n, m, se = audit.get("n"), audit.get("mean_pct"), audit.get("se_pct")
    if not n or n < MIN_N or m is None or not se:
        out["verdict"] = "too-thin"
        return out
    crit = fa.t_crit(n)
    z = (fc["mean_pct"] - m) / se
    out["live_mean_pct"], out["live_n"], out["z_vs_founding"] = m, n, z
    if m >= fc["mean_pct"]:
        out["verdict"] = "reproduces"
    elif z > crit:
        out["verdict"] = "rejects-claim"
    else:
        out["verdict"] = "below-claim"
    return out


def fleet_multiplicity(audits, fdr=wd.FDR):
    """Which positive means survive being one of MANY books graded at once.

    One-sided p per book from the gate's own t and n through the docket's
    own `t_sf`, then Benjamini-Hochberg across EVERY graded book (m = all of
    them, losers included — a loser tested and failed still spent a test, and
    dropping it would loosen the winners' threshold, I21). Reported beside
    the per-book t, never as a bar: the go-live gate grades books one at a
    time on purpose and this does not re-spec it.
    """
    pv = []
    for b, a in audits.items():
        if a.get("t") is None or not a.get("n") or a["n"] < 2:
            continue
        pv.append((b, wd.t_sf(a["t"], a["n"] - 1)))
    surv = wd.bh_survivors(pv, fdr=fdr)
    return {"m": len(pv), "fdr": fdr,
            "p_one_sided": {b: p for b, p in pv},
            "survivors": sorted(surv),
            "positive_untested_by_bh": sorted(
                b for b, p in pv if audits[b].get("mean_pct", 0) > 0
                and b not in surv)}


# ---------------------------------------------------------------- verdict

def verdict(a, oos, in_bh):
    """One line per book, in the fleet's own vocabulary.

    Deliberately NOT a re-spec of the go-live gate: it names the CLASS of
    what the numbers show so the report can be read, and the go-live verdict
    stays the gate's. Classes, in the order tested:
      too-thin            n < MIN_N — nothing here is decidable
      refuted             mean < 0 with the upper bound below zero (the (tz)
                          power gate: the sample EXCLUDED a positive mean)
      losing-underpowered mean < 0, upper bound still admits a positive mean
      concentrated        mean > 0 but ex-top-3 mean <= 0 — three trades, not
                          a distribution
      established         mean > 0, lower bound > 0, survives BH, not
                          concentrated
      positive-unproven   mean > 0 and none of the above
    """
    n, m, se = a.get("n", 0), a.get("mean_pct"), a.get("se_pct")
    if n < MIN_N or m is None or not se:
        return "too-thin"
    crit = fa.t_crit(n)
    if m < 0:
        return "refuted" if (m + crit * se) <= 0 else "losing-underpowered"
    c = a.get("concentration") or {}
    ex3 = c.get("ex_top3_mean_pct")
    if ex3 is not None and ex3 <= 0:
        return "concentrated"
    if (a.get("lower_bound_pct") or 0) > 0 and in_bh:
        return "established"
    return "positive-unproven"


# ---------------------------------------------------------------- run

def book_usd_for(bot, books, default=1000.0):
    """The denominator a book's drawdown is a fraction OF. A shadow book is
    $1,000 by construction. A LIVE row is Eamon's actual equity — and that is
    not the gate's convention: `golive_readiness` divides every row's
    drawdown by BOOK_USD=1000, so a -$53 realised hole on 🔮 georgia's
    ~$287 live book reads 5.3% to the gate and 18.5% here. Both are reported;
    the difference is the finding, not a disagreement to paper over."""
    if not bot.endswith("-lighter"):
        return default
    for b in books or []:
        if b.get("bot") == bot:
            eq, pnl = b.get("equity"), b.get("pnl_abs")
            if isinstance(eq, (int, float)) and isinstance(pnl, (int, float)):
                start = eq - pnl
                if start > 0:
                    return start
    return default


def run(ledger=None, feed=None, bus=None, mc_draws=500, stress_series=None,
        pairs=(("freqtrade-mum-lighter", "freqtrade-mum-lshadow"),
               ("freqtrade-georgia-lighter", "freqtrade-georgia-lshadow"),
               ("freqtrade-avo-maria-lighter", "freqtrade-avo-maria-lshadow"))):
    trades, books, pub = load(ledger=ledger, feed=feed, bus=bus)
    shaped = shape(trades)
    ok, findings = calibrate(shaped, pub)
    if not ok:
        return {"refused": True, "calibration": findings}
    living = sorted((pub.get("books") or {}).keys())
    audits = {b: audit_book(b, shaped[b], book_usd=book_usd_for(b, books))
              for b in living}
    # The gate's OWN drawdown reading rides beside the realised one computed
    # here. It is the MTM fold of (ia)/(iz) — worse-of-both over the equity
    # series — and it is what the maxDD bar actually judges; the realised path
    # is blind to an open hole (I9). On 🪁 kelly the two agree (27.9% realised,
    # 28.5% MTM); on 🔮 georgia's live row they do not (5.3% realised on a
    # $1,000 convention, 58.3% MTM on her real equity), and that gap is I9's
    # whole point, so both are printed and neither is dropped.
    for b, a in audits.items():
        pv = (pub.get("books") or {}).get(b) or {}
        mtm = pv.get("mtm") or {}
        a["gate_mtm_dd_pct"] = mtm.get("max_dd_pct") if isinstance(mtm, dict) else None
        bars = pv.get("bars") or {}
        a["gate_bars"] = bars if isinstance(bars, dict) else None
        a["gate_bars_passed"] = (sum(1 for v in bars.values() if v is True)
                                 if isinstance(bars, dict) else None)
        st = next((x for x in (books or []) if x.get("bot") == b), {}) or {}
        a["row_status"] = st.get("status")
        a["row_equity"] = st.get("equity")
    bh = fleet_multiplicity(audits)
    for b, a in audits.items():
        if "why" in a:
            continue
        a["oos"] = oos_check(b, a)
        a["breakdowns"] = breakdowns(shaped[b]["rows"], stress_series)
        rows = shaped[b]["rows"]
        cl = a.get("cluster") or {}
        blk = 1
        if isinstance(cl, dict) and cl.get("n_clusters"):
            blk = max(1, min(5, int(round(a["n"] / cl["n_clusters"]))))
        a["book_usd"] = book_usd_for(b, books)
        a["monte_carlo"] = monte_carlo(
            [q[0] for q in rows], [q[1] for q in rows],
            a.get("closes_per_year"), book_usd=a["book_usd"],
            draws=mc_draws, block=blk)
        sd = (a["se_pct"] * math.sqrt(a["n"])) if a.get("se_pct") else None
        a["n_for_t2"] = n_for_significance(a["mean_pct"], sd)
        a["rolling"] = rolling_stability([q[0] for q in rows], 30)
        a["verdict"] = verdict(a, a["oos"], b in bh["survivors"])
    out = {"refused": False, "generated": datetime.now(timezone.utc).isoformat(),
           "published_grade_at": pub.get("updated"),
           "n_living": len(living), "books": audits,
           "multiplicity": bh,
           "portfolio": portfolio(shaped, living),
           "execution": {f"{l}|{s}": live_vs_shadow(shaped, l, s)
                         for l, s in pairs},
           "measured_rt_bps": MEASURED_RT_BPS}
    return out


def _fmt(v, w=7, p=2, pct=False):
    if v is None:
        return f"{'—':>{w}}"
    return f"{(100 * v if pct else v):>{w}.{p}f}"


def render(res):
    if res.get("refused"):
        L = ["EDGE AUDIT — REFUSED: this module's sample does not reproduce "
             "the live grader's, so nothing below it may be reported."]
        for b, why in res["calibration"]:
            L.append(f"  {b}: {why}")
        return "\n".join(L)
    L = [f"EDGE AUDIT — {res['n_living']} living books, sample calibrated to the "
         f"live golive-readiness grade of {res['published_grade_at']}",
         f"{'book':30s}{'n':>4}{'mean%':>8}{'t':>6}{'LB%':>7}{'PF':>6}"
         f"{'Shp/t':>6}{'DD%':>6}{'rec_d':>6}{'strk':>5}{'exp':>4}"
         f"{'ex3%':>7}{'b3/gw':>6}{'BE_x':>6}{'P12m':>6}{'ruin':>6}{'dd95':>6}{'mtmDD':>6}{'bars':>5}  verdict",
         "-" * 140]
    for b, a in sorted(res["books"].items()):
        if "why" in a:
            L.append(f"{b:30s}{a.get('n', 0):>4}  {a['why']}")
            continue
        c = a["concentration"]
        es = a.get("expected_streak") or {}
        mc = (a.get("monte_carlo") or {}).get("horizons") or {}
        h12 = mc.get("12m@0x") or {}
        L.append(
            f"{b:30s}{a['n']:>4}{_fmt(a['mean_pct'], 8, 3, True)}"
            f"{_fmt(a['t'], 6)}{_fmt(a['lower_bound_pct'], 7, 3, True)}"
            f"{_fmt(a['profit_factor'], 6)}{_fmt(a.get('sharpe_per_trade'), 6)}"
            f"{_fmt(a.get('max_dd_frac'), 6, 1, True)}"
            f"{_fmt(a.get('recovery_days'), 6, 1)}{a['max_consec_loss']:>5}"
            f"{_fmt(es.get('p50'), 4, 0)}"
            f"{_fmt(c.get('ex_top3_mean_pct'), 7, 3, True)}"
            f"{_fmt(c.get('best3_of_gross_wins'), 6)}"
            f"{_fmt(a.get('cost_headroom_x'), 6, 1)}"
            f"{_fmt(h12.get('p_loss'), 6)}{_fmt(h12.get('p_ruin'), 6)}"
            f"{_fmt(h12.get('dd_p95'), 6, 1, True)}"
            f"{_fmt(a.get('gate_mtm_dd_pct'), 6, 1)}"
            f"{(str(a.get('gate_bars_passed')) + '/6') if a.get('gate_bars_passed') is not None else '—':>5}"
            f"  {a['verdict']}  [oos: {a['oos']['verdict']}]"
            f"{'  (row ' + a['row_status'] + ')' if a.get('row_status') not in (None, 'online') else ''}")
    P = res["portfolio"]
    L += ["", f"PORTFOLIO: {P['n_books']} books, {P['n_pairs_measured']} pairs "
              f"measured on overlapping days, mean pairwise rho "
              f"{_fmt(P['mean_pairwise_rho'], 6, 3)}; corr-aware N_eff "
              f"{_fmt(P['n_eff_equal_weight'], 5, 1)} (symbol count would say "
              f"{P['n_eff_symbol_count_would_say']})"]
    dd = P.get("dd_overlap") or {}
    if dd:
        L.append(f"  drawdown overlap: majority of books underwater on "
                 f"{100 * dd['frac_days_majority_in_dd']:.0f}% of {dd['days']} "
                 f"trading days; worst fleet day {dd['worst_fleet_day']} "
                 f"${dd['worst_fleet_day_usd']:+.2f}")
    co = P.get("coholding") or {}
    if co.get("max_stack"):
        ms = co["max_stack"]
        L.append(f"  co-holding: max {ms['books']} books on {ms['coin_side']} "
                 f"at {ms['at']}; hours by stack size {co['stack_hist']}")
    bh = res["multiplicity"]
    L += ["", f"MULTIPLICITY: {bh['m']} books tested, BH at FDR {bh['fdr']}: "
              f"survivors {bh['survivors'] or 'NONE'}; positive-but-not-"
              f"surviving {bh['positive_untested_by_bh']}"]
    L += ["", "EXECUTION (live arm vs shadow twin, same coins, overlapping window):"]
    for k, v in res["execution"].items():
        if not v or v.get("why"):
            L.append(f"  {k}: {v.get('why') if v else 'no pair'}")
            continue
        L.append(f"  {k}: live n={v['live']['n']} {_fmt(v['live']['mean_pct'], 7, 3, True)}% "
                 f"vs shadow n={v['shadow']['n']} {_fmt(v['shadow']['mean_pct'], 7, 3, True)}%"
                 f"  gap {v['gap_pp']:+.3f}pp on {v['coins']} coins")
    L += ["", "Columns: LB% one-sided lower bound (fleet_allocation.t_crit); "
              "Shp/t per-trade Sharpe; rec_d days to regain the prior peak "
              "(— never); strk longest losing run vs exp its chance median; "
              "ex3% mean without the 3 best trades; b3/gw best-3 share of "
              "gross wins; BE_x break-even cost as a multiple of the measured "
              f"{res['measured_rt_bps']:g}bps; P12m bootstrap P(loss) at 12 "
              "months as recorded (no added cost); ruin P(path touches -100% of "
              "book); dd95 its p95 drawdown as % of book; mtmDD the gate's own "
              "mark-to-market drawdown % (I9 — sees open holes the realised DD% "
              "cannot); bars the gate's own count of 6 passed. Live rows use "
              "their real starting equity as the book, shadow rows $1,000."]
    return "\n".join(L)


# ---------------------------------------------------------------- selftest

def _selftest():
    from datetime import timedelta
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)

    def row(i, pct, usd, pair="X", side=None, reason="long_x", extra=None):
        return (pct, usd, t0 + timedelta(hours=i), (t0 + timedelta(hours=i - 1)).isoformat(),
                extra or {}, None, pair,
                {"pnl_pct": pct, "pnl_abs": usd, "pair": pair, "side": side,
                 "reason": reason, "entry_price": 1.0})

    # side_of: column wins, prefix is a READ, unknown stays unknown
    assert side_of({"side": "short", "reason": "long-x_y"}) == "short"
    assert side_of({"side": None, "reason": "short-div_sl"}) == "short"
    assert side_of({"side": None, "reason": "long_stop"}) == "long"
    assert side_of({"side": None, "reason": "delisted"}) is None
    assert side_of({"side": None, "reason": "longing"}) is None

    # concentration: three trades carry a book whose rest loses -> share > 1
    rows = [row(i, -0.01, -1.0) for i in range(10)] + \
           [row(20 + i, 0.10, 10.0) for i in range(3)]
    c = concentration(rows)
    assert c["top3_share_of_net"] > 1.0, c
    assert c["ex_top3_mean_pct"] < 0, c
    assert abs(c["best3_of_gross_wins"] - 1.0) < 1e-9, c
    # a losing book gets NO share-of-net — nothing to be concentrated
    cl = concentration([row(i, -0.01, -1.0) for i in range(5)])
    assert "top1_share_of_net" not in cl and cl["worst_coin"] == "X", cl

    # break-even cost is never negative and scales with the mean
    assert breakeven_cost_bps(-0.01) == (0.0, 0.0)
    bps, mult = breakeven_cost_bps(0.0035, 17.5)
    assert abs(bps - 35.0) < 1e-9 and abs(mult - 2.0) < 1e-9, (bps, mult)

    # risk_metrics: recovery is None when the hole is never climbed out of,
    # a number when it is; the streak counts LOSSES not zeros
    abss = [1.0, 1.0, -3.0, 0.0, -1.0, -1.0, 5.0]
    pcts = [a / 100 for a in abss]
    closes = [t0 + timedelta(hours=i) for i in range(len(abss))]
    r = risk_metrics(pcts, abss, closes)
    assert r["max_consec_loss"] == 2, r          # the 0.0 breaks the run
    assert r["recovery_days"] is not None and r["recovered"], r
    r2 = risk_metrics([0.01, -0.02], [1.0, -2.0], closes[:2])
    assert r2["recovery_days"] is None and r2["recovered"] is False, r2
    assert r["sharpe_per_trade"] is not None

    # monte carlo scales trades to the BOOK through the clip: every trade
    # +1% on a $100 clip in a $1,000 book is +0.1% of book per trade, so a
    # path of k trades is exactly k * 0.001 — never k * 0.01
    mc = monte_carlo([0.01] * 20, [1.0] * 20, closes_per_year=120.0,
                     draws=20, cost_mults=(0.0,), horizons_months=(12,))
    h = mc["horizons"]["12m@0x"]
    assert h["trades"] == 120 and abs(h["ret_p50"] - 0.12) < 1e-9, h
    assert abs(mc["clip_usd"] - 100.0) < 1e-9, mc
    assert h["p_loss"] == 0.0 and h["dd_p99"] == 0.0 and h["p_ruin"] == 0.0
    # ruin caps the path: -10% per trade on a full-book clip is gone in 10
    ruin = monte_carlo([-0.10] * 20, [-100.0] * 20, closes_per_year=120.0,
                       draws=5, cost_mults=(0.0,), horizons_months=(12,))
    hr = ruin["horizons"]["12m@0x"]
    assert hr["p_ruin"] == 1.0 and abs(hr["ret_p50"] + 1.0) < 1e-9, hr

    # effective_bets: perfectly correlated -> 1; uncorrelated -> N
    w = {"a": 1.0, "b": 1.0, "c": 1.0}
    assert abs(effective_bets(w, {("a", "b"): (1.0, 9), ("a", "c"): (1.0, 9),
                                  ("b", "c"): (1.0, 9)}) - 1.0) < 1e-9
    assert abs(effective_bets(w, {}) - 3.0) < 1e-9
    # correlation uses OVERLAPPING days only — a day one book did not trade is
    # not a zero for it
    d = {"a": {1: 1.0, 2: -1.0, 3: 1.0, 4: -1.0, 5: 1.0, 6: -1.0, 7: 1.0,
               8: -1.0, 9: 1.0, 10: -1.0, 11: 1.0},
         "b": {1: 1.0, 2: -1.0, 3: 1.0, 4: -1.0, 5: 1.0, 6: -1.0, 7: 1.0,
               8: -1.0, 9: 1.0, 10: -1.0, 99: 50.0}}
    cm = correlation_matrix(d, min_overlap=10)
    assert abs(cm[("a", "b")][0] - 1.0) < 1e-9 and cm[("a", "b")][1] == 10, cm

    # the calibration gate FAILS CLOSED: no payload, no `updated`, stale, and
    # an n that differs by ONE row all refuse
    fake = {"x": {"scoped": [(0.01, 1.0, t0 + timedelta(hours=i)) for i in range(5)],
                  "rows": [], "all_time": [], "era_iso": None, "era_src": None}}
    assert calibrate(fake, {}) [0] is False
    assert calibrate(fake, {"books": {"x": {"n": 5}}})[0] is False   # no updated
    now = datetime.now(timezone.utc)
    stale = {"books": {"x": {"n": 5}}, "updated": (now - timedelta(days=9)).isoformat(),
             "ttl_sec": 3600}
    assert calibrate(fake, stale)[0] is False
    fresh = {"books": {"x": {"n": 5, "mean_pct": 1.0, "t": 0.0}},
             "updated": now.isoformat(), "ttl_sec": 43200}
    ok, bad = calibrate(fake, fresh)
    assert ok is False and any("t " in w for _b, w in bad), bad   # t mismatch
    fresh["books"]["x"]["t"] = gr.stats(fake["x"]["scoped"])["t"]
    fresh["books"]["x"]["mean_pct"] = 1.0
    assert calibrate(fake, fresh)[0] is True
    fresh["books"]["x"]["n"] = 6
    assert calibrate(fake, fresh)[0] is False                    # one row off

    # shape() applies the grader's phantom filter AND the ledger quarantine
    trades = [{"bot": "b", "pair": "BOT/USDC", "pnl_pct": 0.01, "pnl_abs": 1.0,
               "opened_at": "2026-07-21T01:00:00+00:00",
               "closed_at": "2026-07-21T02:00:00+00:00", "reason": "long_x",
               "entry_price": 1.0},                                # quarantined
              {"bot": "b", "pair": "ETH", "pnl_pct": 0.0, "pnl_abs": 0.0,
               "opened_at": "2026-08-21T01:00:00+00:00",
               "closed_at": "2026-08-21T02:00:00+00:00", "reason": "x"},  # phantom
              {"bot": "b", "pair": "ETH", "pnl_pct": 0.02, "pnl_abs": 2.0,
               "opened_at": "2026-08-22T01:00:00+00:00",
               "closed_at": "2026-08-22T02:00:00+00:00", "reason": "long_x",
               "entry_price": 1.0}]
    # the quarantine keys on the bot SUBSTRING 'ticket-taker'; give it one
    for t in trades:
        t["bot"] = "lighter-ticket-taker-test"
    sh = shape(trades)
    assert len(sh["lighter-ticket-taker-test"]["rows"]) == 1, sh

    # verdict classes
    base = {"n": 40, "mean_pct": -0.01, "se_pct": 0.001,
            "concentration": {"ex_top3_mean_pct": -0.02}, "lower_bound_pct": 0.0}
    assert verdict(base, {}, False) == "refuted"
    base["se_pct"] = 0.02
    assert verdict(base, {}, False) == "losing-underpowered"
    base.update(mean_pct=0.01, se_pct=0.001)
    assert verdict(base, {}, False) == "concentrated"
    base["concentration"]["ex_top3_mean_pct"] = 0.005
    base["lower_bound_pct"] = 0.005
    assert verdict(base, {}, True) == "established"
    assert verdict(base, {}, False) == "positive-unproven"
    assert verdict({"n": 3, "mean_pct": 0.1, "se_pct": 0.1}, {}, True) == "too-thin"

    # oos: a founding claim the live interval excludes is REJECTED
    a = {"n": 100, "mean_pct": -0.002, "se_pct": 0.001}
    assert oos_check("band-kelly-lshadow", a)["verdict"] == "rejects-claim"
    a["mean_pct"] = 0.005
    assert oos_check("band-kelly-lshadow", a)["verdict"] == "reproduces"
    assert oos_check("pm-turnbull-lshadow", a)["verdict"] == "no-founding-number"

    # THIS MODULE MOVES NOTHING. Asserted on its own source, the
    # fleet_allocation pattern: no lever write, no lever read, no order, no
    # publish. A report that can act is not a report.
    with open(os.path.abspath(__file__)) as fh:
        src = fh.read()
    src = src[:src.index("def _selftest")]      # the list below is not a call
    for forbidden in ("write_levers", "get_lever", "market_open",
                      "publish", "set_lever", "market_close"):
        assert (forbidden + "(") not in src, forbidden
    print("edge_audit selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", help="local /trades.json?source=paper dump")
    ap.add_argument("--feed", help="local /pnl.json dump")
    ap.add_argument("--bus", help="local /bus.json dump (golive_readiness)")
    ap.add_argument("--stress", help="local stress series JSON "
                                     "([{ts, med_bps}], from bus history)")
    ap.add_argument("--draws", type=int, default=500)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="write the full JSON result here")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    stress = None
    if a.stress:
        raw = _load_json(a.stress)
        raw = raw.get("stress", raw) if isinstance(raw, dict) else raw
        stress = sorted((_ts(x["ts"]), x["med_bps"]) for x in raw
                        if _ts(x.get("ts")) and isinstance(x.get("med_bps"), (int, float)))
    res = run(ledger=a.ledger, feed=a.feed, bus=a.bus, mc_draws=a.draws,
              stress_series=stress)
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(res, fh, default=str, indent=1)
    if a.json:
        print(json.dumps(res, default=str, indent=1))
    else:
        print(render(res))
    return 2 if res.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
