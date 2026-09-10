#!/usr/bin/env python3
"""study_counterweight_fresh_read_2026-09-10.py — ⚖️ Counterweight's
pre-registered keep-or-retire read, as an INSTRUMENT instead of prose.

WHY THIS EXISTS, and it is the (I21) shape again: *a defense that lives only in
prose has not been written.* ⚖️ Counterweight was KEPT 1-Sep under
I17-as-amended with a pre-registered re-read, and it was the ONLY pre-registered
read in the fleet with **no instrument** — 🪁 kelly has one, 🔮 georgia has one,
👩 mum's halt-cost and non-crypto-sleeve reads have one, the regime short-veto
has one. Counterweight's lived in three prose sites and nothing computed it.

WHAT THAT COST, measured 10-Sep: **two sessions read its sample definition
differently on the same day.** The registration says *"grade the FRESH on-class
closes ... closes AFTER 1-Sep only"*, and

    OPENED-after 1-Sep  ->  n=13, mean +0.538%/trade, t=+0.35
    CLOSED-after 1-Sep  ->  n=21, mean +2.703%/trade, t=+1.30

— a 62% difference in n, **2.2pp in the mean**, and 16 days in the projected
date the n>=60 trigger fires (~13-Oct vs ~27-Sep). `(zj)` counted one way and
`(zp)`/`(zs)` counted the other, and nothing in the tree could say which was
right. Both readings happen to be positive today, so nothing was decided
wrongly — but the same ambiguity on a mean near zero decides RETIRE versus KEEP.

THE BASIS IS NOW DECLARED, IN CODE, AND IT IS `CLOSED-after`. Chosen on the
registration's own words and its stated purpose, NOT on the number:
  * the words are *"closes AFTER 1-Sep"* — a close is an event, and an event
    "after 1-Sep" is one that HAPPENED after it;
  * the purpose is *"never the window that motivated the keep"*, and the window
    that motivated the keep is the evidence the 1-Sep decision was actually made
    on — i.e. trades that had already CLOSED by then. A trade that closed 3-Sep
    was not in that evidence and is therefore genuinely fresh.
  * the policy-era question (keyed on the OPEN, `(hc)`) is a SEPARATE filter and
    is already applied upstream by `edge_audit.shape` — this clause is about the
    evidence window, not about which policy the trade ran under.
DISCLOSED, because choosing a basis after seeing both numbers deserves it: the
chosen basis is the one that reads BETTER today (+2.703% vs +0.538%). It is
chosen on the words; both bases are positive; neither triggers RETIRE; and the
verdict this instrument prints is reported on BOTH so the choice is auditable.

THE REGISTERED RULE (unchanged — this instrument implements it, it does not
amend it): at n>=60 fresh on-class closes or on the date backstop, whichever
first — RETIRE if the fresh on-class upper bound (m + 1.28*SE) <= 0; KEEP
GRADING if the fresh mean > 0; anything else RETURNS TO EAMON with both numbers.

CALIBRATION GATE, and it REFUSES (exit 2) rather than reports: the instrument
must reproduce the grader's own era-scoped reading of this book before it is
allowed to speak about a subset of it. A harness that cannot reproduce what DID
happen may not say what WOULD have.

    python3 scripts/study_counterweight_fresh_read_2026-09-10.py --selftest
    python3 scripts/study_counterweight_fresh_read_2026-09-10.py
    python3 scripts/study_counterweight_fresh_read_2026-09-10.py --ledger t.json

Exit: 0 verdict printed · 2 the calibration gate REFUSED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402  (load_trades/shape — one owner)
import golive_readiness as gr            # noqa: E402  (stats — the grader's own)

BOT = "perps-funding-spread-lshadow"

#: THE REGISTRATION — a commitment, not a re-derivation. Recorded 1-Sep in
#: CLAUDE.md's acknowledged-recurrence line for `perps-funding-spread`, in
#: `golive_readiness.DECIDED_UNTIL`, and in the `session_state` carried row.
PRE_REGISTERED = {
    "id": "counterweight-fresh-read",
    "kept": "2026-09-01",
    "since": "2026-09-01T00:00:00+00:00",
    "min_n": 60,
    "z_ub": 1.28,
    # [(zs)] the DATE backstop moved 1-Oct -> 10-Oct on Eamon's call so the
    # read lands near the n floor. Only the date moved; the bars are untouched.
    "date_backstop": "2026-10-10",
    #: [(zt)] THE BASIS, declared because it was ambiguous and two sessions
    #: resolved it differently. See the module docstring for the argument.
    "basis": "closed",
    "rule": ("at n>=60 fresh on-class closes OR the date backstop, whichever "
             "first: RETIRE if the fresh on-class upper bound (m+1.28*SE) <= 0; "
             "KEEP GRADING if the fresh mean > 0; anything else RETURNS TO "
             "EAMON with both numbers."),
    #: at-registration statistics, so the rule is graded against a commitment
    #: rather than re-derived. From the (wa) keep and CLAUDE.md's line.
    "at_keep": {"on_class_n": 116, "on_class_mean_pct": -0.711,
                "on_class_t": -0.81, "on_class_ub_pct": 0.41},
    "calib_tol_pp": 0.60,
}

BASES = ("closed", "opened")
_IDX = {"closed": 2, "opened": 3}       # index into edge_audit's shaped quad


def _ts(v):
    d = ea._ts(v)
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def _is_crypto(sym):
    """The book's own class screen. Fail-SILENT to None, never to a guess (I6)
    — an unclassifiable symbol is excluded from BOTH cells and counted."""
    try:
        import fleet_bus as fb
        return bool(fb.is_crypto(sym))
    except Exception:                    # noqa: BLE001
        return None


def rows_for(ledger=None, limit=5000):
    """The book's era-scoped rows through the grader's own pipeline. A dark or
    empty feed returns [] and every caller REFUSES rather than reports."""
    shaped = ea.shape(ea.load_trades(ledger, limit))
    return (shaped.get(BOT) or {}).get("rows") or []


def fresh(rows, basis, since=None):
    """(on_class, off_class, unclassified) fresh cells on the declared basis.

    `basis` is 'closed' or 'opened' and is REQUIRED — there is no default,
    because a silent default is exactly how this became ambiguous."""
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}, got {basis!r}")
    cut = _ts(since or PRE_REGISTERED["since"])
    idx = _IDX[basis]
    on, off, unk = [], [], []
    for q in rows:
        when = _ts(q[idx])
        if when is None or when <= cut:
            continue
        cls = _is_crypto(str(q[6] or "").split("/")[0])
        (on if cls is True else off if cls is False else unk).append(q)
    return on, off, unk


def grade(quads):
    """{n, mean_pct, se_pct, t, ub_pct, usd} through the grader's own stats."""
    out = {"n": len(quads), "usd": round(sum(q[1] for q in quads), 2)}
    if len(quads) < 2:
        return out
    s = gr.stats([(q[0], q[1], q[2]) for q in quads])
    if s.get("se_pct") is None:
        return out
    m, se = 100 * s["mean_pct"], 100 * s["se_pct"]
    out.update(mean_pct=round(m, 4), se_pct=round(se, 4), t=round(s["t"], 3),
               ub_pct=round(m + PRE_REGISTERED["z_ub"] * se, 4))
    return out


def due(n, today=None):
    """(is_due, why) — the registered trigger. The DATE is the backstop and the
    SAMPLE is the trigger; `(yo)` cost this fleet a read that fired 3.5 weeks
    early because nothing was measuring the sample half."""
    today = today or dt.date.today()
    back = dt.date.fromisoformat(PRE_REGISTERED["date_backstop"])
    if n >= PRE_REGISTERED["min_n"]:
        return True, f"sample trigger: n={n} >= {PRE_REGISTERED['min_n']}"
    if today >= back:
        return True, (f"date backstop {back.isoformat()} reached at n={n} "
                      f"(BELOW the registered floor of {PRE_REGISTERED['min_n']} "
                      f"— read the power, not just the sign)")
    return False, (f"NOT DUE: n={n} of {PRE_REGISTERED['min_n']}, and the "
                   f"{back.isoformat()} backstop has not arrived")


def decide(g):
    """The registered rule, applied to a graded fresh cell. Pure."""
    if g.get("ub_pct") is None:
        return {"verdict": "ungradeable", "why": f"n={g.get('n', 0)}"}
    if g["ub_pct"] <= 0:
        return {"verdict": "RETIRE",
                "why": (f"fresh on-class upper bound {g['ub_pct']:+.3f}% <= 0 "
                        f"on n={g['n']} — the sample EXCLUDED a positive mean")}
    if g["mean_pct"] > 0:
        return {"verdict": "KEEP GRADING",
                "why": (f"fresh on-class mean {g['mean_pct']:+.3f}% > 0 on "
                        f"n={g['n']} (ub {g['ub_pct']:+.3f}%)")}
    return {"verdict": "RETURNS TO EAMON",
            "why": (f"mean {g['mean_pct']:+.3f}% <= 0 but the upper bound "
                    f"{g['ub_pct']:+.3f}% has NOT excluded a positive mean, on "
                    f"n={g['n']} — the registration's third branch")}


def calibrate(rows):
    """REFUSE unless the era-scoped all-time reading reproduces the grade the
    keep was made on. Fail-CLOSED: no rows, or no baseline, means no verdict."""
    if not rows:
        return False, "no rows — dark or empty ledger"
    on, _off, _unk = [], [], []
    for q in rows:
        cls = _is_crypto(str(q[6] or "").split("/")[0])
        (on if cls is True else _off if cls is False else _unk).append(q)
    g = grade(on)
    if g.get("mean_pct") is None:
        return False, "era on-class cell ungradeable"
    reg = PRE_REGISTERED["at_keep"]
    # The book has traded on since the keep, so the all-time on-class mean has
    # MOVED by construction; what must hold is that this instrument is reading
    # the same POPULATION — same book, same screen, same order of magnitude.
    if g["n"] < reg["on_class_n"]:
        return False, (f"era on-class n={g['n']} is BELOW the {reg['on_class_n']} "
                       f"the keep was made on — this is not the same population")
    return True, (f"era on-class n={g['n']} (>= the {reg['on_class_n']} at the "
                  f"keep), mean {g['mean_pct']:+.3f}%/trade")


def report(rows, today=None):
    """The verdict on the DECLARED basis, with the other basis reported beside
    it so the (zt) ambiguity is auditable rather than hidden."""
    out = {"registered": PRE_REGISTERED, "bases": {}}
    for basis in BASES:
        on, off, unk = fresh(rows, basis)
        g = grade(on)
        d, why = due(g.get("n", 0), today)
        out["bases"][basis] = {"on_class": g, "off_class_n": len(off),
                               "unclassified_n": len(unk),
                               "due": d, "why": why,
                               "decision": decide(g) if d else None}
    out["declared_basis"] = PRE_REGISTERED["basis"]
    out["verdict"] = out["bases"][PRE_REGISTERED["basis"]]
    return out


def render(res):
    L = ["# ⚖️ Counterweight — pre-registered fresh read",
         f"registered: kept {PRE_REGISTERED['kept']}, "
         f"n>={PRE_REGISTERED['min_n']} or {PRE_REGISTERED['date_backstop']}, "
         f"basis **{PRE_REGISTERED['basis']}-after {PRE_REGISTERED['since'][:10]}**",
         "", "| basis | on-class n | mean% | SE | t | ub@1.28% | due? |",
         "|---|---:|---:|---:|---:|---:|---|"]
    for b, r in res["bases"].items():
        g = r["on_class"]
        f = lambda k: (f"{g[k]:+.3f}" if isinstance(g.get(k), (int, float)) else "—")
        mark = " **(declared)**" if b == res["declared_basis"] else ""
        L.append(f"| {b}{mark} | {g.get('n', 0)} | {f('mean_pct')} | "
                 f"{g.get('se_pct', '—')} | {f('t')} | {f('ub_pct')} | "
                 f"{'DUE' if r['due'] else 'not due'} |")
    v = res["verdict"]
    L += ["", f"**{v['why']}**"]
    if v["decision"]:
        L.append(f"**VERDICT — {v['decision']['verdict']}**: {v['decision']['why']}")
    else:
        L.append("**No verdict taken — the trigger has not fired.** Taking it "
                 "early is the I21/I25 violation the registration exists to "
                 "prevent.")
    return "\n".join(L)


def _selftest():
    t0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)

    def q(pct, usd, closed_h, opened_h, pair="BTC/USDC"):
        return (pct, usd, t0 + dt.timedelta(hours=closed_h),
                (t0 + dt.timedelta(hours=opened_h)).isoformat(), None,
                "long-x_hold", pair, {})

    # THE BASIS ACTUALLY SELECTS DIFFERENT ROWS — the whole point of declaring
    # it. A trade opened BEFORE the cut and closed AFTER it is fresh on the
    # 'closed' basis and not on the 'opened' basis.
    rows = [q(0.01, 1.0, closed_h=+50, opened_h=-50),   # closed-only
            q(0.02, 2.0, closed_h=+60, opened_h=+10),   # both
            q(0.03, 3.0, closed_h=-10, opened_h=-60)]   # neither
    on_c, _, _ = fresh(rows, "closed")
    on_o, _, _ = fresh(rows, "opened")
    assert len(on_c) == 2 and len(on_o) == 1, (len(on_c), len(on_o))
    # THE BOUNDARY: a close landing EXACTLY on the cut instant is not "after"
    # it and must be excluded. Found by mutation — `<=` survived a round that
    # killed everything else, because no fixture sat on the boundary.
    exact = [q(0.01, 1.0, closed_h=0, opened_h=-10)]
    assert fresh(exact, "closed")[0] == [], "a close AT the cut is not after it"
    assert len(fresh([q(0.01, 1.0, closed_h=1, opened_h=-10)], "closed")[0]) == 1

    # and there is NO silent default — an unnamed basis raises
    try:
        fresh(rows, "whenever")
        raise AssertionError("an unknown basis must raise, never default")
    except ValueError:
        pass

    # the class screen splits, and an unclassifiable symbol lands in neither
    # cell but IS counted (I6 — absence is reported, never guessed)
    mixed = [q(0.01, 1.0, +5, +1, "BTC/USDC"), q(0.01, 1.0, +5, +1, "SPY/USDC")]
    on, off, unk = fresh(mixed, "closed")
    assert len(on) + len(off) + len(unk) == 2, (on, off, unk)

    # THE TRIGGER: sample is the trigger, date is the backstop ((yo))
    assert due(60, dt.date(2026, 9, 15))[0] is True
    assert due(13, dt.date(2026, 9, 15))[0] is False
    assert due(13, dt.date(2026, 10, 10))[0] is True, "the backstop must fire"
    assert "BELOW the registered floor" in due(13, dt.date(2026, 10, 10))[1]

    # EVERY ARM OF THE REGISTERED RULE, driven directly — including the two
    # the live data does not currently exercise, so they cannot rot
    assert decide({"n": 60, "mean_pct": -1.0, "ub_pct": -0.2})["verdict"] == "RETIRE"
    assert decide({"n": 60, "mean_pct": +0.5, "ub_pct": +1.2})["verdict"] == "KEEP GRADING"
    assert decide({"n": 60, "mean_pct": -0.3, "ub_pct": +0.4})["verdict"] == "RETURNS TO EAMON"
    assert decide({"n": 1})["verdict"] == "ungradeable"
    # the boundary: ub exactly 0 RETIRES (the rule says <= 0)
    assert decide({"n": 60, "mean_pct": -0.5, "ub_pct": 0.0})["verdict"] == "RETIRE"

    # the calibration gate FAILS CLOSED on a dark ledger and on a thin one
    ok, why = calibrate([])
    assert ok is False and "dark or empty" in why
    ok2, _ = calibrate([q(0.01, 1.0, +5, +1)] * 3)
    assert ok2 is False, "a population smaller than the keep's must REFUSE"

    # the registration carries its commitment fields
    for k in ("min_n", "z_ub", "basis", "rule", "at_keep", "date_backstop"):
        assert PRE_REGISTERED[k], k
    assert PRE_REGISTERED["basis"] in BASES

    print("study_counterweight_fresh_read selftest OK — the basis selects "
          "different rows and has no silent default, the class screen counts "
          "the unclassifiable, sample-is-trigger/date-is-backstop, every arm "
          "of the registered rule incl. the ub==0 boundary, calibration fails "
          "closed on dark and thin ledgers")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", help="local /trades.json?source=paper dump")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--today", help="ISO date, for testing the trigger")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    rows = rows_for(a.ledger, a.limit)
    ok, why = calibrate(rows)
    print(f"calibration: {why}")
    if not ok:
        print("REFUSED — a harness that cannot reproduce what DID happen may "
              "not say what WOULD have.")
        return 2
    today = dt.date.fromisoformat(a.today) if a.today else None
    print()
    print(render(report(rows, today)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
