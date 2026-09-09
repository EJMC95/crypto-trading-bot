#!/usr/bin/env python3
"""🔮 georgia v1's PRE-REGISTERED cap-5 read (claims_ledger `georgia-entry-cap-5-days-to-gate`).

[2026-09-09 (zo)] THE PREDICTION, as (vb) registered it on 27-Aug and the
ledger carried it: cap `MAX_ENTRIES_PER_HOUR` 3 -> 5 takes days-to-gate
**344 -> 187** (tol +-60) *at a HIGHER mean* — book-at-cap-5 replayed at
mean +0.108%/trade, iid t +2.54, 5.47 closes/day. The (wt) September slate
DEFERRED her retirement to this read on Eamon's confirmed date ("On 10 sep");
Eamon then asked for it a day early ("take georgia's read now").

THE BASIS IS THE BOT'S OWN STAMP, KEYED ON THE OPEN. A trade's policy is
fixed when it is TAKEN ((hc): "keyed on the OPEN"), and every family close
carries `extra.policy.max_entries_per_hour`. So the post-cap sample is
exactly the rows whose own stamp reads 5 — never `closed_at >= 27-Aug`, which
admits trades opened under cap 3 that happened to close later (measured: 4 of
79 by close-date were such straddlers).

THE TRAP THIS INSTRUMENT EXISTS TO STEP AROUND. The claim's owner field is
`golive-readiness::books.<bot>.horizon.eta_days`, and on an `undecidable`
book the organ publishes `eta_days: null` (the number lives in `raw_days`).
So the registered grade could only ever read UNRESOLVED — a claim pointed at
a field the state that matters never populates — and the HANDOFF row said so:
*"grade the claim on her post-cap closes ONLY."* This file IS that grade,
reproducible, with the registered numbers held as a COMMITMENT (I21) rather
than re-derived at read time.

CALIBRATION GATE, and it REFUSES (exit 2) rather than reports: this reads the
PUBLIC /trades.json, which does NOT apply `LEDGER_QUARANTINE` ((wo)), so it
applies `is_quarantined` + `is_phantom_close` itself (owners IMPORTED). It
then checks that the all-time mean it computes tracks the grader's own
published era mean (+0.064%/trade on n=277 at the read); a wrong basis (a
fraction read as a percent, a missing filter) blows straight through 0.10pp.

WHAT THE VERDICT IS AND IS NOT. `FAILS` means the (vb) PREDICTION did not
hold on its own post-cap population. Retirement then follows the registered
branch — but it is cited as **I17's UNDECIDABLE call** (the book cannot reach
its own `t` bar: 8,094 closes ~ 4.3 years at 5.12/day, per the organ), NEVER
as a measured-loser exclusion: the post-cap upper bound is reported beside the
verdict precisely so nobody later cites this as "her sample excluded a
positive mean". It did not.

Exit: 0 verdict printed · 2 the calibration gate REFUSED.
"""
import argparse
import collections
import datetime as _dt
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot_pnl_store as store          # noqa: E402 — one owner: quarantine
import golive_readiness as gr          # noqa: E402 — one owner: phantom closes

BOT = "freqtrade-georgia-lshadow"
BASE = "https://pnl-dashboard-production-858c.up.railway.app"

# The commitment, as written at (vb) / in claims_ledger. Not re-derived here.
PRE_REGISTERED = {
    "registered": "2026-08-27 (vb); claims_ledger georgia-entry-cap-5-days-to-gate",
    "grade_after": "2026-09-10",
    "cap": 5,                       # the policy-stamp value that selects the sample
    "days_to_gate": 187.0,          # the claim's `number`
    "tol_days": 60.0,               # the claim's `tol`  -> band [127, 247]
    "pred_mean_pct": 0.108,         # book-at-cap-5, (vb) table
    "pred_t": 2.54,
    "pred_closes_per_day": 5.47,
    "t_bar": 2.0,                   # the go-live t bar the prediction is about
    # the claim's OWN sufficiency statement: "a fortnight is ~75 closes,
    # enough for the horizon to stop reading `undecidable`"
    "min_n": 75,
    "z_ub": 1.28,                   # the I17 upper-bound convention, reported
    "at_read": {"era_n": 277, "era_mean_pct": 0.064, "n_req_t": 8094,
                "rate_cpd": 5.12},
}
CALIB_TOL_PP = 0.10


def _ts(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00").replace(" UTC", "")
    try:
        t = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


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
            print(f"[georgia-read] feed unreachable ({e})", file=sys.stderr)
            return []
    rows = raw if isinstance(raw, list) else raw.get("trades", raw.get("data", []))
    return [r for r in rows
            if isinstance(r, dict) and r.get("bot") == BOT
            and r.get("side") != "skip"
            and not store.is_quarantined(r.get("bot"), r.get("pair"),
                                         r.get("closed_at"))
            and not gr.is_phantom_close(r)]


def stamped_cap(r):
    pol = (r.get("extra") or {}).get("policy") or {}
    v = pol.get("max_entries_per_hour")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def post_cap_rows(rows, cap=None):
    """The trades whose OWN policy stamp says the cap — keyed on the open by
    construction, because the stamp is written at entry."""
    cap = PRE_REGISTERED["cap"] if cap is None else cap
    out = [r for r in rows if stamped_cap(r) == cap]
    out.sort(key=lambda r: _ts(r.get("opened_at")) or _dt.datetime.min.replace(
        tzinfo=_dt.timezone.utc))
    return out


def stats(rows):
    """n, mean %/trade, sd, SE, t, one-sided upper bound (I17 convention),
    closes/day over the sample's own span. `None`s where n<2."""
    xs = [float(r["pnl_pct"]) * 100.0 for r in rows
          if r.get("pnl_pct") is not None]
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": None, "sd": None, "se": None, "t": None,
                "ub": None, "rate": None, "span_d": None}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    opens = [_ts(r.get("opened_at")) for r in rows]
    closes = [_ts(r.get("closed_at")) for r in rows]
    opens = [t for t in opens if t]
    closes = [t for t in closes if t]
    span = ((max(closes) - min(opens)).total_seconds() / 86400.0
            if opens and closes else None)
    rate = (n / span) if span and span > 0 else None
    return {"n": n, "mean": m, "sd": sd, "se": se, "t": (m / se if se else None),
            "ub": m + PRE_REGISTERED["z_ub"] * se, "rate": rate, "span_d": span}


def days_to_gate(s):
    """(n_req, days) at the sample's own mean/sd/rate for the t bar; None when
    the mean is <= 0 (unreachable at any n) or the rate is unknown."""
    if not s or s["mean"] is None or s["mean"] <= 0 or not s["rate"]:
        return None, None
    n_req = (PRE_REGISTERED["t_bar"] * s["sd"] / s["mean"]) ** 2
    return n_req, n_req / s["rate"]


def verdict(post):
    """The registered prediction, graded verbatim. -> (label, reason)."""
    s = stats(post)
    if s["n"] < PRE_REGISTERED["min_n"]:
        return "NOT YET DECIDABLE", (
            f"n={s['n']} < the claim's own sufficiency floor "
            f"{PRE_REGISTERED['min_n']}; the {PRE_REGISTERED['grade_after']} "
            f"date is the backstop")
    lo = PRE_REGISTERED["days_to_gate"] - PRE_REGISTERED["tol_days"]
    hi = PRE_REGISTERED["days_to_gate"] + PRE_REGISTERED["tol_days"]
    n_req, days = days_to_gate(s)
    if days is None:
        return "FAILS", (
            f"post-cap mean {s['mean']:+.4f}%/trade <= 0, so the t={PRE_REGISTERED['t_bar']:.1f} "
            f"bar is UNREACHABLE at any n — the prediction was {PRE_REGISTERED['days_to_gate']:.0f}d "
            f"[{lo:.0f}, {hi:.0f}] at a HIGHER mean (+{PRE_REGISTERED['pred_mean_pct']:.3f}%)")
    if lo <= days <= hi:
        return "HOLDS", (
            f"days-to-gate {days:.0f} inside [{lo:.0f}, {hi:.0f}] "
            f"({n_req:.0f} closes at {s['rate']:.2f}/day)")
    return "FAILS", (
        f"days-to-gate {days:.0f} outside [{lo:.0f}, {hi:.0f}] "
        f"({n_req:.0f} closes at {s['rate']:.2f}/day)")


def calibrate(rows):
    """REFUSE unless the all-time mean tracks the grader's published era mean."""
    s = stats(rows)
    reg = PRE_REGISTERED["at_read"]
    if s["n"] < 2:
        return False, "no admissible rows — dark feed or wrong bot id"
    drift = abs(s["mean"] - reg["era_mean_pct"])
    ok = drift <= CALIB_TOL_PP
    return ok, (f"all-time n={s['n']} mean {s['mean']:+.3f}%/trade vs the grader's "
                f"era n={reg['era_n']} {reg['era_mean_pct']:+.3f}% "
                f"(|drift| {drift:.3f}pp, tol {CALIB_TOL_PP:.2f}pp)")


def rank_mix(post):
    c = collections.Counter((r.get("extra") or {}).get("entry_rank") for r in post)
    return dict(sorted(c.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)))


def report(src=None):
    rows = load(src)
    ok, note = calibrate(rows)
    print(f"🔮 georgia v1 PRE-REGISTERED cap-5 READ  ·  registered "
          f"{PRE_REGISTERED['registered']}")
    print(f"   prediction: days-to-gate {PRE_REGISTERED['days_to_gate']:.0f} "
          f"+-{PRE_REGISTERED['tol_days']:.0f} at mean +{PRE_REGISTERED['pred_mean_pct']:.3f}%/trade, "
          f"t +{PRE_REGISTERED['pred_t']:.2f}, {PRE_REGISTERED['pred_closes_per_day']:.2f} closes/day\n")
    print(f"calibration: {note}")
    if not ok:
        print("REFUSED — a harness that cannot reproduce what DID happen may "
              "not say what WOULD have. No verdict printed.")
        return 2
    print("calibration OK\n")

    post = post_cap_rows(rows)
    pre = [r for r in rows if stamped_cap(r) != PRE_REGISTERED["cap"]]
    s, p = stats(post), stats(pre)
    label, why = verdict(post)
    print(f"post-cap sample (own policy stamp max_entries_per_hour == "
          f"{PRE_REGISTERED['cap']}, keyed on the OPEN):")
    print(f"   n={s['n']}  (floor n>={PRE_REGISTERED['min_n']}: "
          f"{'MET' if s['n'] >= PRE_REGISTERED['min_n'] else 'not met'})   "
          f"span {s['span_d']:.1f}d   closes/day {s['rate']:.2f} "
          f"(predicted {PRE_REGISTERED['pred_closes_per_day']:.2f})")
    print(f"   mean {s['mean']:+.4f}%/trade (predicted +{PRE_REGISTERED['pred_mean_pct']:.3f}%)   "
          f"sd {s['sd']:.3f}   t {s['t']:+.2f} (predicted +{PRE_REGISTERED['pred_t']:.2f})")
    n_req, days = days_to_gate(s)
    print(f"   days-to-gate: "
          f"{'UNREACHABLE (mean <= 0)' if days is None else f'{days:.0f}d ({n_req:.0f} closes)'}")
    pnl = sum(float(r["pnl_abs"]) for r in post if r.get("pnl_abs") is not None)
    print(f"   realised ${pnl:+.2f}   rank mix {rank_mix(post)}")
    if p["n"] >= 2:
        print(f"   pre-cap for contrast: n={p['n']} mean {p['mean']:+.4f}% t {p['t']:+.2f}")
    print(f"\nI17 status (REPORTED so the retirement is cited correctly):")
    print(f"   post-cap upper bound (m+{PRE_REGISTERED['z_ub']}*SE) = {s['ub']:+.4f}% "
          f"-> {'has NOT excluded a positive mean' if s['ub'] > 0 else 'EXCLUDES a positive mean'}")
    ar = PRE_REGISTERED["at_read"]
    print(f"   the organ: era n={ar['era_n']}, n_req(t) {ar['n_req_t']:,} closes at "
          f"{ar['rate_cpd']}/day = {ar['n_req_t']/ar['rate_cpd']/365.25:.1f} years -> UNDECIDABLE")
    print(f"\nVERDICT: the (vb) prediction {label}")
    print(f"   {why}")
    return 0


def selftest():
    """Drives every branch on fixtures — including HOLDS, which the live data
    does NOT exercise (a harness for a prediction that never held has never
    tested HOLDS)."""
    t0 = _dt.datetime(2026, 8, 27, tzinfo=_dt.timezone.utc)

    def rowset(vals, cap=5, per_day=5.47, rank=None):
        out = []
        step = 1.0 / per_day
        for i, v in enumerate(vals):
            o = t0 + _dt.timedelta(days=i * step)
            out.append({"bot": BOT, "pair": "X", "pnl_pct": v / 100.0,
                        "pnl_abs": v, "opened_at": o.isoformat(),
                        "closed_at": (o + _dt.timedelta(hours=1)).isoformat(),
                        "extra": {"policy": ({"max_entries_per_hour": cap}
                                             if cap is not None else {}),
                                  **({"entry_rank": rank} if rank else {})}})
        return out

    # HOLDS: mean +0.108 with sd ~1.75 at 5.47/day -> (3.5/0.108)^2/5.47 ~ 192d
    hold = rowset([0.108 + 1.75, 0.108 - 1.75] * 40)
    lab, why = verdict(hold)
    assert lab == "HOLDS", (lab, why)
    # FAILS by unreachability: mean <= 0
    lab, why = verdict(rowset([-0.5, 0.4] * 40))
    assert lab == "FAILS" and "UNREACHABLE" in why, (lab, why)
    # FAILS by being too slow: a tiny positive mean on the same sd
    lab, why = verdict(rowset([0.01 + 1.75, 0.01 - 1.75] * 40))
    assert lab == "FAILS" and "outside" in why, (lab, why)
    # ...and by being too FAST is also outside the band (a prediction is a
    # number, not a floor) — a huge mean lands far below 127d
    lab, why = verdict(rowset([3.0 + 0.5, 3.0 - 0.5] * 40))
    assert lab == "FAILS" and "outside" in why, (lab, why)
    # UNDER the floor: never decides
    lab, _ = verdict(rowset([-1.0] * 20))
    assert lab == "NOT YET DECIDABLE", lab
    # THE BASIS: the stamp selects the sample, keyed on the open. A cap-3 row
    # and an unstamped (null policy) row are EXCLUDED whatever their dates.
    mixed = rowset([1.0] * 3, cap=5) + rowset([9.0] * 2, cap=3) + \
        rowset([9.0] * 2, cap=None)
    got = post_cap_rows(mixed)
    assert len(got) == 3 and all(stamped_cap(r) == 5 for r in got), got
    assert stamped_cap({"extra": {"policy": {"max_entries_per_hour": True}}}) is None
    # calibration REFUSES a 100x basis error and a dark feed
    bad = [dict(r, pnl_pct=0.064) for r in rowset([0.0] * 80)]
    ok, _ = calibrate(bad)
    assert not ok, "calibration admitted a 100x basis error"
    ok, note = calibrate([])
    assert not ok and "dark feed" in note, note
    # days_to_gate arithmetic on a known sample
    n_req, days = days_to_gate({"mean": 1.0, "sd": 2.0, "rate": 4.0})
    assert abs(n_req - 16.0) < 1e-9 and abs(days - 4.0) < 1e-9
    assert days_to_gate({"mean": 0.0, "sd": 2.0, "rate": 4.0}) == (None, None)
    print("study_georgia_cap5_read --selftest OK (HOLDS / 3 FAILS shapes / "
          "floor / stamp basis / 100x basis / dark feed / arithmetic)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--source", help="feed base URL or a local trades.json")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else report(a.source))
