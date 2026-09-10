#!/usr/bin/env python3
"""🙏 avo's SLOT CAP, re-measured on current data — what is her RIGHT cap?

**Eamon, 2026-09-10: "your proposal sounds good, proceed."**

WHY THIS EXISTS RATHER THAN A LEVER. A session proposed `max_open` 6 -> 8 on
both arms and found two MEASURED blockers sitting in the code:

  * `(ne)` measured cap 8 on 15-Aug and REFUSED it — *"Cap 8 was NOT supported
    (one marginal add contradicted by the real timeline, LINK pileup) and is
    not shipped."*
  * the CURRENT 6 is under an unread pre-registration (`avo-live-slot-6-
    preregistered-read`, due 6-Oct) asking whether **6** was right at all.

Overriding a measured refusal with a guess is the thing this fleet has paid
for repeatedly. So the question is re-asked properly, on data neither `(ne)`
nor `(ye)` had: both arms have run cap 6 since 6-Sep and the twin since
15-Aug.

**THE QUESTION IS "WHAT IS HER RIGHT CAP", NOT "IS 8 OKAY".** Asking whether
a specific number is acceptable is how a grid's maximum gets shipped — the
`(oe)` artifact. This asks what the LAST SLOT ACTUALLY EARNS and lets the cap
follow.

THREE THINGS THE LEDGER CAN ANSWER, and one it cannot:

 1. **DOES THE CAP BIND?** Occupancy is reconstructed from the closes' own
    open/close intervals — the `(ne)` method (*"cap-4 is BINDING — 39% of its
    era at 4/4"*). A cap that never binds cannot be the constraint, and
    raising it is inert (I18).
 2. **WHAT DOES THE MARGINAL TRADE EARN?** Every close is bucketed by
    `held_at_open` — how many positions this book already held at the instant
    this one opened — which is the `(ye)` method that justified 5 -> 6
    (*"the 4 shadow trades opened with >=5 already held earned +6.877%/trade
    vs +1.027% for the other 28"*), now on a far larger sample.
 3. **DOES SUPPLY ARRIVE IN BURSTS?** Opens are clustered into same-minute
    events. A book that opens one at a time is never slot-bound however full
    it looks; one that opens four at once is.

 4. **WHAT IT CANNOT: neither arm has EVER run above 6.** So 7 and 8 are
    EXTRAPOLATION, not measurement, and the extrapolation is only ever one
    slot deep — the ledger prices the LAST slot that was actually used. A
    move to 8 assumes two unmeasured slots behave like the one measured
    marginal slot; a move to 7 assumes one does. This instrument says so in
    its own verdict rather than leaving the reader to notice.

**THE DECISION RULE IS PRE-DECLARED (I21) — see `DECISION_RULE` below — and it
is written before any result is seen, so a disappointing number cannot quietly
become a different rule.** The asymmetry in it is I19's: a widening may not
COST expectancy, but it need not PROVE a gain — an expectancy-neutral widening
on a cap-bound book is bought as throughput, the `(ty)` standard.

CALIBRATION GATE, and it REFUSES (exit 2) rather than reports. The public
/trades.json does NOT apply `LEDGER_QUARANTINE` ((wo)), so this applies
`is_quarantined` + `is_phantom_close` itself (owners IMPORTED, never re-coded),
then checks the mean it computes against the grader's own published number for
each arm. A harness that cannot reproduce what DID happen may not say what
WOULD have.

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

import bot_pnl_store as store            # noqa: E402
import golive_readiness as gr            # noqa: E402

BASE = "https://pnl-dashboard-production-858c.up.railway.app"
LIVE = "freqtrade-avo-maria-lighter"
SHADOW = "freqtrade-avo-maria-lshadow"

#: The cap both arms run today, and the one the ledger can price the edge of.
CAP_NOW = 6

#: Calibration tolerance in percentage points of per-trade mean. A wrong basis
#: (a fraction read as a percent, a missing quarantine filter) blows through
#: this by an order of magnitude; ordinary feed lag does not.
CALIB_TOL_PP = 0.25

#: PRE-DECLARED, before any number was seen (I21). The asymmetry is I19's.
DECISION_RULE = {
    "bind_min_frac": 0.20,
    "marginal_bucket": "held_at_open >= CAP_NOW - 2",
    "ship_if": (
        "the cap BINDS (>= 20% of observed time at cap) AND the marginal "
        "bucket's mean is NOT WORSE than the rest beyond one standard error "
        "of the difference — an expectancy-neutral widening on a cap-bound "
        "book is bought as throughput ((ty)), never as edge"),
    "refuse_if": (
        "the marginal bucket is WORSE beyond one SE of the difference (the "
        "widening costs expectancy — I19) OR the cap does not bind (the "
        "widening is inert — I18)"),
    "undecided_if": "either bucket holds fewer than 8 closes",
    "depth": (
        "the ledger prices the LAST slot actually used, so it supports a "
        "ONE-slot extrapolation. A two-slot move assumes an unmeasured slot "
        "behaves like the measured one."),
}


def _ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return _dt.datetime.fromtimestamp(float(v), _dt.timezone.utc)
    try:
        t = _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def load(bot, src=None):
    """Rows for one arm, quarantine- and phantom-filtered. Fail-CLOSED: a dark
    or empty feed returns [] and the caller REFUSES, never reports."""
    if src and not str(src).startswith(("http://", "https://")):
        with open(src) as fh:
            raw = json.load(fh)
    else:
        url = (src or BASE).rstrip("/") + "/trades.json?limit=5000&source=paper"
        try:
            with urllib.request.urlopen(url, timeout=90) as fh:
                raw = json.load(fh)
        except Exception as e:                                   # noqa: BLE001
            print(f"[avo-cap] feed unreachable ({e})", file=sys.stderr)
            return []
    rows = raw if isinstance(raw, list) else raw.get("trades",
                                                     raw.get("data", []))
    out = [r for r in rows
           if isinstance(r, dict) and r.get("bot") == bot
           and r.get("side") != "skip"
           and not store.is_quarantined(r.get("bot"), r.get("pair"),
                                        r.get("closed_at"))
           and not gr.is_phantom_close(r)]
    out.sort(key=lambda r: _ts(r.get("opened_at"))
             or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc))
    return out


def pct(r):
    """Per-trade return in PERCENT. The ledger stores a fraction."""
    v = r.get("pnl_pct")
    try:
        return float(v) * 100.0
    except (TypeError, ValueError):
        return None


def stats(rows):
    xs = [p for p in (pct(r) for r in rows) if p is not None]
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "se": 0.0, "t": 0.0}
    m = sum(xs) / n
    if n < 2:
        return {"n": n, "mean": m, "se": 0.0, "t": 0.0}
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return {"n": n, "mean": m, "se": se, "t": (m / se if se > 0 else 0.0)}


def held_at_open(rows):
    """-> {trade_id: how many of THIS book's positions were already open at
    the instant this one opened}. Half-open interval [opened, closed): a
    position that closes at exactly this timestamp is a handoff, not an
    overlap — the `(hp)` >60s rule's spirit, applied to a same-instant edge."""
    spans = []
    for r in rows:
        o, c = _ts(r.get("opened_at")), _ts(r.get("closed_at"))
        if o and c and c > o:
            spans.append((o, c, id(r)))
    out = {}
    for r in rows:
        o = _ts(r.get("opened_at"))
        if not o:
            continue
        out[id(r)] = sum(1 for (so, sc, sid) in spans
                         if sid != id(r) and so <= o < sc)
    return out


def occupancy(rows):
    """Time-weighted occupancy from the closes' own intervals, plus the
    fraction of observed time sitting AT the cap. Event-driven: the count only
    changes at an open or a close, so this is exact, not sampled."""
    events = []
    for r in rows:
        o, c = _ts(r.get("opened_at")), _ts(r.get("closed_at"))
        if o and c and c > o:
            events.append((o, +1))
            events.append((c, -1))
    if not events:
        return {"span_h": 0.0, "mean_held": 0.0, "at_cap_frac": 0.0,
                "peak": 0, "hist": {}}
    events.sort()
    held = 0
    prev = events[0][0]
    total = 0.0
    weighted = 0.0
    at_cap = 0.0
    peak = 0
    hist = collections.Counter()
    for t, d in events:
        dt = (t - prev).total_seconds()
        if dt > 0:
            total += dt
            weighted += held * dt
            hist[held] += dt
            if held >= CAP_NOW:
                at_cap += dt
        held += d
        peak = max(peak, held)
        prev = t
    return {
        "span_h": total / 3600.0,
        "mean_held": (weighted / total) if total else 0.0,
        "at_cap_frac": (at_cap / total) if total else 0.0,
        "peak": peak,
        "hist": {k: v / total for k, v in sorted(hist.items())} if total else {},
    }


def burst_sizes(rows, window_s=120):
    """How many positions this book opens in one burst. A book that opens one
    at a time is never slot-bound however full it looks."""
    opens = sorted(t for t in (_ts(r.get("opened_at")) for r in rows) if t)
    if not opens:
        return {}
    sizes = []
    cur = 1
    for a, b in zip(opens, opens[1:]):
        if (b - a).total_seconds() <= window_s:
            cur += 1
        else:
            sizes.append(cur)
            cur = 1
    sizes.append(cur)
    return dict(sorted(collections.Counter(sizes).items()))


def calibrate(bot, rows, published):
    """REFUSE unless the mean this computes tracks the grader's own published
    number for the SAME arm. `published` is None when the feed could not be
    read — which REFUSES too, never a vacuous pass."""
    s = stats(rows)
    if s["n"] < 5:
        return False, f"{bot}: only {s['n']} admissible rows — dark feed or wrong id"
    if published is None:
        return False, (f"{bot}: the grader published no mean for this arm — "
                       "nothing to calibrate against")
    drift = abs(s["mean"] - published)
    ok = drift <= CALIB_TOL_PP
    return ok, (f"{bot}: n={s['n']} mean {s['mean']:+.3f}%/trade vs grader "
                f"{published:+.3f}% (|drift| {drift:.3f}pp, tol "
                f"{CALIB_TOL_PP:.2f}pp)")


def grader_means(src=None):
    """The grader's OWN published per-arm era mean, off /bus.json. Imported
    verdict, never recomputed — `golive_readiness` is the one authority."""
    url = (src or BASE).rstrip("/") + "/bus.json"
    try:
        with urllib.request.urlopen(url, timeout=60) as fh:
            bus = json.load(fh)
    except Exception:                                            # noqa: BLE001
        return {}
    books = (((bus or {}).get("golive_readiness") or {}).get("books")) or {}
    out = {}
    for bot in (LIVE, SHADOW):
        v = books.get(bot)
        if isinstance(v, dict) and isinstance(v.get("mean_pct"), (int, float)):
            out[bot] = float(v["mean_pct"])
    return out


def open_now(src=None):
    """-> {bot: open_trades} from the live feed.

    DECLARED LIMIT, and it is why this function exists. `occupancy()` is
    reconstructed from CLOSED trades, because a close is the only row that
    carries both an open and a close timestamp. A position OPEN right now has
    no `closed_at`, so it is invisible to that reconstruction — a book sitting
    at 6 of 6 at this instant can still read `at cap 0.0%`. The bound is
    reported beside the figure rather than left for the reader to notice: the
    unseen time is at most (open positions x their age), and their age is not
    published, so the honest statement is a DIRECTION, not a correction."""
    url = (src or BASE).rstrip("/") + "/pnl.json"
    try:
        with urllib.request.urlopen(url, timeout=60) as fh:
            doc = json.load(fh)
    except Exception:                                            # noqa: BLE001
        return {}
    out = {}
    for r in (doc or {}).get("bots") or []:
        if isinstance(r, dict) and r.get("bot") in (LIVE, SHADOW):
            v = r.get("open_trades")
            if isinstance(v, int):
                out[r["bot"]] = v
    return out


def marginal_split(rows, held):
    """The (ye) split: closes opened DEEP vs the rest. `deep` is the last two
    slots — the edge of the cap, where a raise would add capacity."""
    bar = CAP_NOW - 2
    deep = [r for r in rows if held.get(id(r), 0) >= bar]
    rest = [r for r in rows if held.get(id(r), 0) < bar]
    ds, rs = stats(deep), stats(rest)
    diff = ds["mean"] - rs["mean"]
    se = math.sqrt(ds["se"] ** 2 + rs["se"] ** 2)
    return {"bar": bar, "deep": ds, "rest": rs, "diff": diff, "se_diff": se,
            "t_diff": (diff / se if se > 0 else 0.0)}


def report(src=None):
    pub = grader_means(src)
    live_open = open_now(src)
    arms = {}
    print("🙏 AVO — WHAT IS HER RIGHT SLOT CAP?   (cap today: "
          f"{CAP_NOW} on both arms)\n")
    print("DECISION RULE, pre-declared before any number was seen:")
    print(f"  SHIP     — {DECISION_RULE['ship_if']}")
    print(f"  REFUSE   — {DECISION_RULE['refuse_if']}")
    print(f"  UNDECIDED— {DECISION_RULE['undecided_if']}")
    print(f"  DEPTH    — {DECISION_RULE['depth']}\n")

    for bot in (SHADOW, LIVE):
        rows = load(bot, src)
        ok, note = calibrate(bot, rows, pub.get(bot))
        print(f"calibration  {note}")
        if not ok:
            print("\nREFUSED — a harness that cannot reproduce what DID happen "
                  "may not say what WOULD have. No verdict printed.")
            return 2
        arms[bot] = rows
    print("calibration OK on both arms\n")

    verdicts = {}
    for bot, rows in arms.items():
        held = held_at_open(rows)
        occ = occupancy(rows)
        m = marginal_split(rows, held)
        bursts = burst_sizes(rows)
        label = "TWIN (control)" if bot == SHADOW else "LIVE (real money)"
        print(f"── {label}  {bot}")
        print(f"   occupancy   mean {occ['mean_held']:.2f} of {CAP_NOW} slots "
              f"over {occ['span_h']/24.0:.1f}d · at cap "
              f"{occ['at_cap_frac']:.1%} of the time · peak {occ['peak']}")
        share = " ".join(f"{k}:{v:.0%}" for k, v in occ["hist"].items())
        print(f"   held-share  {share}")
        onow = live_open.get(bot)
        if onow is not None:
            flag = "  <-- AT CAP NOW, and invisible above" if onow >= CAP_NOW else ""
            print(f"   open NOW    {onow} of {CAP_NOW} (closed-trade "
                  f"reconstruction cannot see these){flag}")
        print(f"   bursts      {bursts}  (opens within 120s of each other)")
        print(f"   MARGINAL    held>={m['bar']}: n={m['deep']['n']} "
              f"{m['deep']['mean']:+.3f}%/trade   vs rest: n={m['rest']['n']} "
              f"{m['rest']['mean']:+.3f}%")
        print(f"   difference  {m['diff']:+.3f}pp  (SE {m['se_diff']:.3f}, "
              f"t {m['t_diff']:+.2f})")

        binds = occ["at_cap_frac"] >= DECISION_RULE["bind_min_frac"]
        thin = m["deep"]["n"] < 8 or m["rest"]["n"] < 8
        worse = m["diff"] < -m["se_diff"]
        if thin:
            v = "UNDECIDED — too thin to price the marginal slot"
        elif worse:
            v = "REFUSE — the marginal slot earns measurably less (I19)"
        elif not binds:
            v = (f"REFUSE-INERT — the cap binds only "
                 f"{occ['at_cap_frac']:.1%} of the time (I18)")
        else:
            v = "SHIP +1 — cap binds and the marginal slot is not worse"
        verdicts[bot] = v
        print(f"   VERDICT     {v}\n")

    print("── READING BOTH ARMS TOGETHER")
    for bot, v in verdicts.items():
        print(f"   {bot:<34} {v}")
    print(f"\n   EXTRAPOLATION LIMIT: {DECISION_RULE['depth']}")
    print("   Neither arm has EVER run above 6, so 7 is a one-slot "
          "extrapolation and 8 is a two-slot one.")
    return 0


def selftest():
    """The arithmetic, driven — not a substring scan."""
    t0 = _dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc)
    def row(o_h, c_h, p):
        return {"bot": SHADOW, "opened_at": (t0 + _dt.timedelta(hours=o_h)
                                             ).isoformat(),
                "closed_at": (t0 + _dt.timedelta(hours=c_h)).isoformat(),
                "pnl_pct": p / 100.0}
    # three overlapping holds: B opens with A held, C opens with A and B held
    rows = [row(0, 10, 1.0), row(1, 10, 2.0), row(2, 10, 3.0)]
    h = held_at_open(rows)
    got = sorted(h.values())
    assert got == [0, 1, 2], got

    # a position closing at the exact instant another opens is a HANDOFF,
    # never an overlap — otherwise every rollover inflates the held count
    hand = held_at_open([row(0, 5, 1.0), row(5, 9, 1.0)])
    assert sorted(hand.values()) == [0, 0], hand

    # occupancy is exact, not sampled: one position held 10h alone
    occ = occupancy([row(0, 10, 1.0)])
    assert abs(occ["span_h"] - 10.0) < 1e-6, occ
    assert abs(occ["mean_held"] - 1.0) < 1e-6, occ
    assert occ["at_cap_frac"] == 0.0 and occ["peak"] == 1, occ

    # ...and a book pinned at cap reads 100%
    full = [row(0, 10, 1.0) for _ in range(CAP_NOW)]
    of = occupancy(full)
    assert abs(of["at_cap_frac"] - 1.0) < 1e-6, of

    # pnl_pct is a FRACTION in the ledger and PERCENT here — the basis error
    # the calibration gate exists to catch
    assert abs(pct({"pnl_pct": 0.032} ) - 3.2) < 1e-9

    # calibration REFUSES on a dark grader rather than passing vacuously
    ok, note = calibrate(SHADOW, rows * 3, None)
    assert not ok and "nothing to calibrate" in note, note
    # ...and on a real drift
    ok, _ = calibrate(SHADOW, rows * 3, 99.0)
    assert not ok
    ok, _ = calibrate(SHADOW, rows * 3, 2.0)
    assert ok

    # bursts: three opens inside 120s are ONE event of size 3
    b = burst_sizes([row(0, 9, 1), row(0.01, 9, 1), row(0.02, 9, 1),
                     row(5, 9, 1)])
    assert b == {1: 1, 3: 1}, b

    # the marginal split reads the bar off CAP_NOW, never a literal
    m = marginal_split(rows, h)
    assert m["bar"] == CAP_NOW - 2
    print("study_avo_cap selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="feed base URL or a local trades.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return report(a.source)


if __name__ == "__main__":
    raise SystemExit(main())
