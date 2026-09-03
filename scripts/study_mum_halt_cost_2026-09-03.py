#!/usr/bin/env python3
"""[2026-09-03 (xu)] DOES 👩 MUM'S DAILY-LOSS HALT COST OR SAVE HER? — the
instrument, plus the PRE-REGISTERED criterion that decides it on FRESH events.

**Eamon, 3-Sep: *"Mum doesn't appear to be trading properly"*** → the throughput
worry was WRONG (she out-opens her twin since the halt cleared: 1 vs 0 in 6.9h,
6 vs 8 in 24h, 20 vs 23 in 48h) and the real question underneath it was whether
her daily-loss halt is earning its keep. → *"Yes I like this idea."*

WHY THIS IS A REGISTRATION AND NOT A VERDICT. At registration her ledger holds
**exactly ONE daily-loss halt** (2026-09-02T17:19:45Z, 8 legs). The other three
"shut" days in `halt_days_30d` were stop-guard and cooldown LOCKOUTS, which
block entries without force-closing anything, so they carry no forced-exit
counterfactual at all. Deciding a real-money rail on one event — the very event
that prompted the question — is I25 in its purest form.

**ONE HALT INSTANT IS ONE OBSERVATION, NOT ONE PER LEG.** All 8 legs closed at
the same second, in the same falling minute, on a correlated crypto basket. The
7-of-7 sign test across those legs reads p≈0.008 and is an ARTIFACT of treating
one market moment as seven independent draws — the (kw)/(ky) cluster lesson,
here in its most tempting costume, because the legs really are separate rows.
`halt_events` therefore groups by INSTANT and `MIN_EVENTS` counts EVENTS.

**AND THE ASYMMETRY THAT MAKES A COST-ONLY STUDY DANGEROUS.** A rail's cost is
visible every single time it fires; its benefit appears only on the day it
prevents a ruinous loss, which by construction has not happened yet. So this
measurement will read "loosen" on every ordinary halt day right up until the
day it would have saved the book. That is why the criterion below is a
threshold on a MEAN ACROSS EVENTS with a consistency requirement, and why the
default verdict is KEEP — the burden sits on loosening, not on holding.

Run:  study_mum_halt_cost_2026-09-03.py [--trades-json FILE|URL]
Exit: 0 verdict printed · 2 the calibration gate REFUSED
"""
import argparse
import datetime as dt
import json
import os
import statistics as st
import sys
import urllib.request

LIVE = "freqtrade-mum-lighter"
SHADOW = "freqtrade-mum-lshadow"
FEED = ("https://pnl-dashboard-production-858c.up.railway.app"
        "/trades.json?source=paper&limit=5000")

#: A halt EVENT is one flatten instant. Legs inside it are one correlated bet.
MIN_EVENTS = 5
#: Loosen only above this mean cost per leg, across events.
LOOSEN_COST_PP = 1.0

#: [I21] THE REGISTRATION — a commitment, not a re-derivation. These are the
#: numbers as measured on 2026-09-03; the decision is made on events AFTER it.
PRE_REGISTERED = {
    "registered": "2026-09-03",
    "criterion": (
        f"read at n>={MIN_EVENTS} halt EVENTS (instants, not legs) occurring "
        f"AFTER 2026-09-03; LOOSEN only if mean paired cost > "
        f"{LOOSEN_COST_PP}pp/leg AND the sign is consistent across events; "
        f"otherwise KEEP. A rail is held unless loosening is earned."),
    "at_registration": {
        "halt_events": 1,
        "event": "2026-09-02T17:19:45",
        "legs": 8, "paired_legs": 7,
        "halt_pct_per_leg": -1.70, "twin_pct_per_leg": +0.05,
        "cost_pp_per_leg": +1.76,
        # the I25 control: the arms on days she did NOT halt
        "baseline_live_mean_pct": +0.720, "baseline_live_n": 53,
        "baseline_twin_mean_pct": +0.625, "baseline_twin_n": 49,
    },
    "note": ("live BEATS the twin on non-halt days (+0.720 vs +0.625%/trade), "
             "so no chronic live-arm handicap is in evidence and the halt is "
             "the only measured difference."),
}
#: The calibration gate's tolerance on reproducing the registered event.
CALIB_TOL_PP = 0.15


def _ts(s):
    """Naive-UTC always. The ledger writes `closed_at` without a timezone while
    some feeds carry `Z`, and mixing the two raises on every comparison — so
    the offset is applied and then dropped, once, here."""
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    return t.replace(tzinfo=None) if t.tzinfo is None else \
        t.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _pct(r):
    try:
        return float(r.get("pnl_pct") or 0.0) * 100.0
    except (TypeError, ValueError):
        return 0.0


def _coin(r):
    return str(r.get("pair") or "").split("/")[0]


def load(src=None):
    """Ledger rows. Prefers the fleet DB, falls back to the public feed."""
    if src and os.path.exists(src):
        raw = json.load(open(src))
        return raw["trades"] if isinstance(raw, dict) else raw
    if not src:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            import bot_pnl_store as store            # noqa: PLC0415
            rows = store.fetch_paper_trades(limit=5000)
            if rows:
                return rows
        except Exception:  # noqa: BLE001
            pass
    with urllib.request.urlopen(src or FEED, timeout=60) as fh:
        raw = json.load(fh)
    return raw["trades"] if isinstance(raw, dict) else raw


def halt_events(rows):
    """{event_key: [legs]} — ONE EVENT PER HALT, grouped by UTC DAY.

    The whole point of this function, and it took the calibration gate to get
    it right. Eight legs closed in one flatten are one correlated bet on one
    minute, not eight draws; counting legs would make a single bad afternoon
    look like a decided question ((kw)/(ky) cluster lesson).

    Grouped by DATE rather than by exact timestamp because `halted_today`
    LATCHES ONCE PER UTC DAY — so at most one daily-loss halt can occur per
    day by construction, and any spread across legs is one flatten retrying
    over successive loops. Keying on the exact stamp was the first cut and is
    FRAGILE in precisely the direction that matters: the registered event's 8
    legs happen to share a microsecond, so it worked, and a flatten spanning
    two seconds would have silently split into two "events" and inflated the
    count toward a decision. The key is the EARLIEST leg's second."""
    byday = {}
    for r in rows:
        if str(r.get("bot")) != LIVE:
            continue
        if not str(r.get("reason") or "").endswith("daily_loss"):
            continue
        t = _ts(r.get("closed_at"))
        if t is None:
            continue
        byday.setdefault(t.date(), []).append((t, r))
    out = {}
    for _d, legs in byday.items():
        legs.sort(key=lambda p: p[0])
        key = legs[0][0].replace(microsecond=0).isoformat()
        out[key] = [r for _t, r in legs]
    return out


def pair_event(legs, shadow_rows):
    """(cost_pp_per_leg, n_paired, detail) for one halt instant.

    Each halt-closed leg is paired to the twin's NEXT close of the same coin at
    or after the halted leg's open — the counterfactual is what that coin
    actually did for an arm that did not halt. Unpairable legs are REPORTED and
    excluded, never imputed."""
    detail, hs, tw = [], [], []
    for lg in sorted(legs, key=_pct):
        c = _coin(lg)
        o = _ts(lg.get("opened_at"))
        cands = [y for y in shadow_rows
                 if _coin(y) == c and _ts(y.get("closed_at"))
                 and o and _ts(y["closed_at"]) >= o]
        if not cands:
            detail.append((c, _pct(lg), None, None))
            continue
        y = min(cands, key=lambda z: _ts(z["closed_at"]))
        detail.append((c, _pct(lg), _pct(y),
                       str(y.get("reason") or "").split("_", 2)[-1]))
        hs.append(_pct(lg))
        tw.append(_pct(y))
    if not hs:
        return None, 0, detail
    return (st.mean(tw) - st.mean(hs)), len(hs), detail


def baseline(rows, halt_dates):
    """The I25 control: both arms on days the live arm did NOT halt, over the
    SAME WINDOW.

    The window restriction is load-bearing and was a real defect in the first
    cut of this script. The twin has traded since 2026-08-07 and the live arm
    since 2026-08-28, so an unrestricted comparison scores the twin over 21
    extra days of a different tape — and it FLIPPED the verdict, printing
    "live trails the twin" (+0.720 vs +1.105) where the paired window reads
    the opposite (+0.720 vs +0.625). A control arm that is not on the same
    window is not a control ([[ab-tests-must-vary-exactly-one-variable]])."""
    live_closes = [_ts(r["closed_at"]) for r in rows
                   if str(r.get("bot")) == LIVE and _ts(r.get("closed_at"))]
    if not live_closes:
        return {"live": (0, 0.0), "twin": (0, 0.0), "since": None}
    since = min(live_closes)
    out = {"since": since.date().isoformat()}
    for bot, key in ((LIVE, "live"), (SHADOW, "twin")):
        v = [_pct(r) for r in rows
             if str(r.get("bot")) == bot and _ts(r.get("closed_at"))
             and _ts(r["closed_at"]) >= since
             and _ts(r["closed_at"]).date() not in halt_dates]
        out[key] = (len(v), st.mean(v) if v else 0.0)
    return out


def calibrate(events):
    """A harness that cannot reproduce what DID happen may not say what WOULD
    have. Recomputes the REGISTERED event and refuses beyond tolerance."""
    reg = PRE_REGISTERED["at_registration"]
    ev = events.get(reg["event"])
    if not ev:
        return False, f"registered event {reg['event']} not in the ledger"
    if len(ev) != reg["legs"]:
        return False, f"legs {len(ev)} != registered {reg['legs']}"
    return True, ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-json")
    a = ap.parse_args(argv)
    rows = load(a.trades_json)
    shadow = [r for r in rows if str(r.get("bot")) == SHADOW]
    events = halt_events(rows)

    print(f"👩 mum — daily-loss halt cost, paired against her never-halting twin")
    print(f"registered {PRE_REGISTERED['registered']}  ·  "
          f"{PRE_REGISTERED['criterion']}\n")

    ok, why = calibrate(events)
    reg_ev = PRE_REGISTERED["at_registration"]["event"]
    if ok:
        cost, n, detail = pair_event(events[reg_ev], shadow)
        drift = abs((cost or 0) - PRE_REGISTERED["at_registration"]
                    ["cost_pp_per_leg"])
        _b = baseline(rows, {_ts(k).date() for k in events})
        _bd = max(abs(_b["live"][1] - PRE_REGISTERED["at_registration"]
                      ["baseline_live_mean_pct"]),
                  abs(_b["twin"][1] - PRE_REGISTERED["at_registration"]
                      ["baseline_twin_mean_pct"]))
        if _bd > CALIB_TOL_PP:
            ok, why = False, (f"baseline reproduces live {_b['live'][1]:+.3f} / "
                              f"twin {_b['twin'][1]:+.3f} vs registered "
                              f"{PRE_REGISTERED['at_registration']['baseline_live_mean_pct']:+.3f} / "
                              f"{PRE_REGISTERED['at_registration']['baseline_twin_mean_pct']:+.3f} "
                              f"(drift {_bd:.3f} > {CALIB_TOL_PP})")
        elif drift > CALIB_TOL_PP:
            ok, why = False, (f"registered event reproduces at {cost:+.2f}pp "
                              f"vs {reg_ev} registered "
                              f"{PRE_REGISTERED['at_registration']['cost_pp_per_leg']:+.2f}pp "
                              f"(drift {drift:.2f} > {CALIB_TOL_PP})")
    if not ok:
        print(f"REFUSED — calibration gate: {why}")
        print("  (a harness that cannot reproduce what DID happen may not say "
              "what WOULD have)")
        return 2

    halt_dates = {_ts(k).date() for k in events}
    base = baseline(rows, halt_dates)
    print(f"I25 BASELINE (days she did NOT halt; paired window from "
          f"{base['since']} — the live arm's first close)")
    print(f"  live n={base['live'][0]:3}  {base['live'][1]:+.3f}%/trade")
    print(f"  twin n={base['twin'][0]:3}  {base['twin'][1]:+.3f}%/trade")
    print(f"  -> live {'BEATS' if base['live'][1] > base['twin'][1] else 'trails'}"
          f" the twin off halt days: no chronic live handicap in evidence\n")

    reg_day = dt.date.fromisoformat(PRE_REGISTERED["registered"])
    fresh, costs = [], []
    print(f"HALT EVENTS ({len(events)} total; an instant is ONE observation)")
    for inst in sorted(events):
        cost, n, detail = pair_event(events[inst], shadow)
        is_fresh = _ts(inst).date() > reg_day
        tag = "FRESH" if is_fresh else "at-registration"
        print(f"  {inst[:19]}  legs={len(events[inst])} paired={n}  "
              f"cost={cost:+.2f}pp/leg  [{tag}]")
        for c, h, t, why_ in detail:
            print(f"      {c:10} halt {h:+7.2f}%  twin "
                  + (f"{t:+7.2f}% ({why_})" if t is not None else "— unpaired"))
        if is_fresh and cost is not None:
            fresh.append(inst)
            costs.append(cost)

    print(f"\nFRESH events since registration: {len(fresh)} of {MIN_EVENTS}")
    if len(fresh) < MIN_EVENTS:
        print(f"VERDICT: not_yet_decidable — the rail is KEPT.")
        print(f"  One instant is one observation; the registered event is NOT "
              f"re-mined into this count (I21).")
        return 0
    m = st.mean(costs)
    consistent = all(c > 0 for c in costs) or all(c < 0 for c in costs)
    if m > LOOSEN_COST_PP and consistent:
        print(f"VERDICT: LOOSEN — mean cost {m:+.2f}pp/leg over {len(costs)} "
              f"events, sign consistent. Returns to Eamon with this number.")
    else:
        print(f"VERDICT: KEEP — mean cost {m:+.2f}pp/leg over {len(costs)} "
              f"events (consistent={consistent}); below the "
              f"{LOOSEN_COST_PP}pp bar or mixed in sign.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
