#!/usr/bin/env python3
"""🪁 band-kelly's PRE-REGISTERED keep-or-retire read (EDGE_AUDIT_2026-09-02 §6.1).

[2026-09-07 (yo)] The registration lived as a HANDOFF row and a
`golive_readiness.DECIDED_UNTIL` date. Its own words are that the DATE is the
BACKSTOP and the SAMPLE is the trigger — *"at n>=60 fresh closes since 1-Sep or
on 1-Oct, whichever first"* — and nothing in the tree measured the sample. So
the trigger fired quietly: by 7-Sep her fresh window held **233** closes against
a bar of 60, three-and-a-half weeks before anyone was due to look.

THE REGISTERED CRITERION, applied verbatim and never re-derived (I21 — a
registration is a commitment, not a thing to re-optimise at read time; note it
says 1.28, so this uses 1.28 and NOT `fleet_allocation.t_crit`, which would be
a different, later-invented rule):

    RETIRE        if the fresh upper bound (mean + 1.28*SE) <= 0
    KEEP GRADING  if the fresh mean > 0
    otherwise     RETURNS TO EAMON, with both numbers

CALIBRATION GATE, and it REFUSES (exit 2) rather than reports: this reads the
PUBLIC /trades.json, which — unlike the grader's own `fetch_paper_trades` —
does NOT apply `LEDGER_QUARANTINE`, so an outside consumer must apply
`is_quarantined` + `is_phantom_close` itself or it grades a sample the gate
refuses. The gate checks that the all-time mean this file computes still tracks
the audit's published one. Owners are IMPORTED, never copied.

CONCENTRATION IS REPORTED BESIDE THE VERDICT, because on the first run it is
what the verdict turns on: the fresh window looks 0.098pp better than all-time,
and the top 3 closes carry +18.68pp of a -10.24pp total. Ex-top-3 the fresh
mean is -0.126%/trade — i.e. materially the same as all-time. A read that
printed only the headline would have overstated the improvement.

Exit: 0 verdict printed · 2 the calibration gate REFUSED.
"""
import argparse
import collections
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot_pnl_store as store          # noqa: E402 — one owner: quarantine
import golive_readiness as gr          # noqa: E402 — one owner: phantom closes

BOT = "band-kelly-lshadow"
BASE = "https://pnl-dashboard-production-858c.up.railway.app"

# The commitment, as written. Not re-derived at read time.
PRE_REGISTERED = {
    "registered": "2026-09-02 (EDGE_AUDIT_2026-09-02.md section 6.1)",
    "criterion": "at n>=60 fresh closes since 2026-09-01, or on 2026-10-01, "
                 "whichever first: RETIRE if ub(m+1.28*SE)<=0; KEEP GRADING if "
                 "mean>0; else RETURNS TO EAMON",
    "fresh_from": "2026-09-01",
    "min_n": 60,
    "backstop": "2026-10-01",
    "z": 1.28,
    "at_registration": {"alltime_n": 383, "alltime_mean_pct": -0.179,
                        "alltime_ub_pct": +0.03},
}
# The audit's n=383 has since grown, so the mean is expected to move a little.
# Wide enough to admit ledger growth, tight enough that a WRONG basis (a
# fraction read as a percent, a missing quarantine) blows straight through it.
CALIB_TOL_PP = 0.10


def load(src=None):
    """Rows for this book, quarantine- and phantom-filtered. Fail-CLOSED: a
    dark or empty feed returns [] and the caller REFUSES, never reports."""
    if src and not src.startswith(("http://", "https://")):
        with open(src) as fh:
            raw = json.load(fh)
    else:
        url = (src or BASE) if (src or "").startswith("http") else BASE
        url = url.rstrip("/") + "/trades.json?limit=5000&source=paper"
        try:
            with urllib.request.urlopen(url, timeout=60) as fh:
                raw = json.load(fh)
        except Exception as e:  # noqa: BLE001
            print(f"[kelly-read] feed unreachable ({e})", file=sys.stderr)
            return []
    rows = raw if isinstance(raw, list) else raw.get("trades", raw.get("data", []))
    return [r for r in rows
            if isinstance(r, dict) and r.get("bot") == BOT
            and r.get("side") != "skip"
            and not store.is_quarantined(r.get("bot"), r.get("pair"),
                                         r.get("closed_at"))
            and not gr.is_phantom_close(r)]


def stats(rows, z=None):
    """n, mean %/trade, SE, one-sided upper bound, t. `None`s where n<2."""
    z = PRE_REGISTERED["z"] if z is None else z
    xs = [float(r["pnl_pct"]) * 100.0 for r in rows
          if r.get("pnl_pct") is not None]
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": None, "se": None, "ub": None, "t": None}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    return {"n": n, "mean": m, "se": se, "ub": m + z * se,
            "t": (m / se if se else None)}


def fresh_rows(rows):
    since = PRE_REGISTERED["fresh_from"]
    return [r for r in rows if str(r.get("closed_at") or "")[:10] >= since]


def verdict(fresh):
    """The registered rule, verbatim. Returns (label, reason)."""
    s = stats(fresh)
    if s["n"] < PRE_REGISTERED["min_n"]:
        return "NOT YET DECIDABLE", (
            f"n={s['n']} < the registered floor {PRE_REGISTERED['min_n']}; "
            f"the {PRE_REGISTERED['backstop']} backstop still stands")
    if s["ub"] is not None and s["ub"] <= 0:
        return "RETIRE", f"fresh upper bound {s['ub']:+.4f}% <= 0"
    if s["mean"] is not None and s["mean"] > 0:
        return "KEEP GRADING", f"fresh mean {s['mean']:+.4f}%/trade > 0"
    return "RETURNS TO EAMON", (
        f"neither branch fires: upper bound {s['ub']:+.4f}% has NOT excluded a "
        f"positive mean (so I17-as-amended forbids retiring), and the mean "
        f"{s['mean']:+.4f}%/trade is not above zero (so 'keep grading' is not "
        f"met either)")


def calibrate(rows):
    """REFUSE unless the all-time mean still tracks the published one."""
    s = stats(rows)
    reg = PRE_REGISTERED["at_registration"]
    if s["n"] < 2:
        return False, "no admissible rows — dark feed or wrong bot id"
    drift = abs(s["mean"] - reg["alltime_mean_pct"])
    ok = drift <= CALIB_TOL_PP
    return ok, (f"all-time n={s['n']} mean {s['mean']:+.3f}%/trade vs published "
                f"n={reg['alltime_n']} {reg['alltime_mean_pct']:+.3f}% "
                f"(|drift| {drift:.3f}pp, tol {CALIB_TOL_PP:.2f}pp)")


def concentration(fresh):
    xs = sorted((float(r["pnl_pct"]) * 100.0 for r in fresh
                 if r.get("pnl_pct") is not None), reverse=True)
    if len(xs) < 4:
        return None
    top3, tot = sum(xs[:3]), sum(xs)
    return {"top3_pp": top3, "total_pp": tot,
            "ex_top3_mean": (tot - top3) / (len(xs) - 3),
            "dominated": bool(tot and abs(top3) > abs(tot))}


def report(src=None):
    rows = load(src)
    ok, note = calibrate(rows)
    print(f"🪁 band-kelly PRE-REGISTERED READ  ·  registered "
          f"{PRE_REGISTERED['registered']}")
    print(f"   {PRE_REGISTERED['criterion']}\n")
    print(f"calibration: {note}")
    if not ok:
        print("REFUSED — a harness that cannot reproduce what DID happen may "
              "not say what WOULD have. No verdict printed.")
        return 2
    print("calibration OK\n")

    fresh = fresh_rows(rows)
    s, a = stats(fresh), stats(rows)
    label, why = verdict(fresh)
    print(f"fresh window (closed_at >= {PRE_REGISTERED['fresh_from']}):")
    print(f"   n={s['n']}  (bar n>={PRE_REGISTERED['min_n']}: "
          f"{'MET — the sample tripped it, not the date' if s['n'] >= PRE_REGISTERED['min_n'] else 'not met'})")
    print(f"   mean {s['mean']:+.4f}%/trade   SE {s['se']:.4f}   "
          f"t {s['t']:+.2f}   upper bound {s['ub']:+.4f}%")
    print(f"   all-time for contrast: n={a['n']} mean {a['mean']:+.3f}% "
          f"ub {a['ub']:+.3f}% t {a['t']:+.2f}")
    pnl = sum(float(r["pnl_abs"]) for r in fresh if r.get("pnl_abs") is not None)
    print(f"   fresh realised P&L ${pnl:+.2f}")
    c = concentration(fresh)
    if c:
        print(f"\nconcentration (REPORTED, never a branch of the registered "
              f"rule — but it is what this verdict turns on):")
        print(f"   top-3 closes {c['top3_pp']:+.2f}pp of {c['total_pp']:+.2f}pp "
              f"total -> {'TAIL-DOMINATED' if c['dominated'] else 'not dominated'}")
        print(f"   ex-top-3 fresh mean {c['ex_top3_mean']:+.4f}%/trade "
              f"(vs all-time {a['mean']:+.3f}%) — the fresh window's apparent "
              f"improvement is carried by 3 closes")
    print(f"\nVERDICT: {label}")
    print(f"   {why}")
    return 0


def selftest():
    """Drives the registered rule on fixtures — including the two branches the
    live data does NOT currently exercise, which is exactly where an unread
    rule rots (the harness for a read that has never returned RETIRE has never
    tested RETIRE)."""
    def rowset(vals, day="2026-09-05"):
        return [{"bot": BOT, "pair": "X", "pnl_pct": v / 100.0,
                 "pnl_abs": v, "closed_at": day + "T00:00:00Z"} for v in vals]

    # RETIRE: a tight, clearly negative sample of >=60
    neg = rowset([-1.0] * 30 + [-0.9] * 30 + [-1.1] * 5)
    lab, _ = verdict(neg)
    assert lab == "RETIRE", lab
    # KEEP GRADING: positive mean, >=60
    pos = rowset([+1.0] * 40 + [+0.5] * 25)
    lab, _ = verdict(pos)
    assert lab == "KEEP GRADING", lab
    # RETURNS TO EAMON: negative mean, wide interval that has not excluded >0
    mixed = rowset(([-8.0, +7.0] * 32) + [-0.5])
    s = stats(mixed)
    assert s["mean"] < 0 < s["ub"], s
    lab, _ = verdict(mixed)
    assert lab == "RETURNS TO EAMON", (lab, s)
    # UNDER the floor: never decides, whatever the numbers say
    lab, _ = verdict(rowset([-1.0] * 10))
    assert lab == "NOT YET DECIDABLE", lab
    # the fresh window really is a FILTER (a pre-window close must not count)
    old = rowset([-1.0] * 70, day="2026-08-15")
    assert len(fresh_rows(old)) == 0, "fresh window did not filter by date"
    assert len(fresh_rows(rowset([-1.0] * 3))) == 3
    # calibration REFUSES a wrong basis: pnl_pct read as already-percent is
    # the classic 100x error and must not slip through
    bad = [{"bot": BOT, "pair": "X", "pnl_pct": -0.179, "pnl_abs": -1.0,
            "closed_at": "2026-09-05T00:00:00Z"} for _ in range(80)]
    ok, _ = calibrate(bad)
    assert not ok, "calibration admitted a 100x basis error"
    # ...and a dark feed REFUSES rather than reporting a vacuous pass
    ok, note = calibrate([])
    assert not ok and "dark feed" in note, note
    print("study_kelly_fresh_read --selftest OK "
          "(4 verdict branches, the date filter, a 100x basis error, dark feed)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--source", help="feed base URL or a local trades.json")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else report(a.source))
