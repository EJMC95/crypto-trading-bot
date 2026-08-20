#!/usr/bin/env python3
"""🎯 THE SNIPER'S INTENDED JOB: what is a DEBUT trade actually worth, and in
which DIRECTION?  [2026-08-20 (sg)]

`(sf)` established what the book CANNOT do: its exit bracket is a near-dead
branch, the ANSEM ladder is inert here, and its realised entries sit at the
50th percentile of random. It also established WHY the book is idle — the
`young` source, the only observable route to a debut regime, admits NOTHING,
because the venue files memecoin debuts under `strategy_index 7` and the (lk)
screen tests `== 2`.

This study asks the question `(sf)` deliberately left open: **if the young
source were unblocked, what would it be trading, and would a LONG be the right
side?** It is the measurement that has to come BEFORE any screen change (I19 —
a widening is paid for in expectancy), and it is deliberately built to be able
to say NO.

WHAT IT MEASURES. Every book the venue's own `created_at` exposes, entered at
`debut + delay` and held under the book's REAL shipped bracket (read from the
module, never retyped) plus a content-free timer control, LAG-1, slippage
charged on the coin's OWN turnover tier, both directions, split by instrument
class and by whether the venue is where the instrument is PRICED.

THE SPLIT THAT MATTERS, and why it is not `strategy_index`:
`strategy_index 7` is a grab-bag — ANSEM and CASHCAT (crypto-native memecoins,
whose only market IS this venue) sit in it beside ANTHROPIC, OPENAI, SPCX
(pre-IPO equity) and US10Y (a bond yield). The (lk) screen's argument was never
about class: it was that *"a surge-long on USDKRW/BOTZ is a timer-held drift
bet on an instrument whose venue volume surge is its UNDERLYING's market event,
already priced where the underlying trades"*. That argument turns on whether a
DEEP PRIMARY MARKET exists elsewhere — so this study measures that axis
directly (`venue_priced` vs `externally_priced`) rather than assuming class is
a proxy for it.

DECLARED LIMITS, none fixable from this endpoint:
  * `orderBookDetails` lists only books ALIVE TODAY, so a book born and
    delisted inside the window is invisible. Survivorship biases every number
    here OPTIMISTIC, and the effect is largest on exactly the thin debut
    cohort this study is about. Stated, not corrected.
  * `created_at` is epoch-0 on some rows (MRNA, US10Y). Those are EXCLUDED,
    never treated as ancient or as newborn.
  * 1h resolution. The bot polls at 60s, so intra-hour paths are invisible;
    per `(sf)` the exit-basis gap this creates is real and one-sided, which is
    why the shipped bracket's absolute level here is NOT quotable as the book's
    expected P&L. DIRECTION and RANK across cells are what this study is for.
"""
import argparse
import importlib.util
import json
import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# The (sf) harness is the ONE owner of walk_exit / slip_bps / score / the
# shipped-rule reader. Its filename carries hyphens so `import` cannot reach
# it; load it by path rather than growing a second copy of the exit rule ((hj)).
_SPEC = importlib.util.spec_from_file_location(
    "_sniper_exit_shape", os.path.join(HERE, "study_sniper_exit_shape_2026-08-20.py"))
H = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(H)

CACHE = os.path.join(os.environ.get("STUDY_CACHE_DIR", "/tmp"),
                     "sniper_debut_direction_2026-08-20.json")

# Venue classes, from the venue's own strategy_index. `venue_priced` is the
# axis the (lk) argument actually turns on: is there a deep primary market for
# this instrument somewhere other than Lighter?
CRYPTO, COMMODITY, FX, US_EQ, ASIA_EQ, EXOTIC = 2, 3, 4, 5, 6, 7
CLASS_NAME = {2: "crypto", 3: "commodity", 4: "fx", 5: "us_eq",
              6: "asia_eq", 7: "exotic"}
# 2 = crypto-native. 7 = the grab-bag; its MEMBERS split (see venue_priced()).
EXTERNALLY_PRICED_CLASSES = {COMMODITY, FX, US_EQ, ASIA_EQ}

# Class-7 members that DO have a deep primary market elsewhere, or no
# tradeable underlying at all. Declared as a LIST because the venue publishes
# no field that separates them — and kept SMALL and auditable for that reason.
# A name absent from this set and in class 7 is treated as venue-priced.
EXOTIC_EXTERNALLY_PRICED = {
    # tokenised pre-IPO equity: a real company, priced in private rounds
    "ANTHROPIC", "OPENAI", "SPCX", "UNITREE", "CXMT", "ZHIPU", "FOLKS",
    # listed equities the venue happens to file under 7
    "MRNA", "ADI",
    # not an instrument with a spot market at all
    "US10Y",
}


def venue_priced(sym, cls):
    """True when THIS VENUE is where the instrument is priced.

    The distinction the (lk) screen was really making. A crypto-native token
    (class 2, or a class-7 memecoin) has no deeper market than this book, so a
    debut here IS price discovery. A tokenised equity/FX/commodity is a wrapper
    around a price set somewhere far deeper, so its debut move is that
    market's event arriving, not this venue discovering anything.
    """
    if cls in EXTERNALLY_PRICED_CLASSES:
        return False
    if cls == EXOTIC:
        return sym not in EXOTIC_EXTERNALLY_PRICED
    return cls == CRYPTO


def births(rows=None, max_age_d=None):
    """[(sym, birth_ts, class, qvol)] from the venue's OWN created_at.

    An unparseable or epoch-0 stamp is DROPPED, never coerced — "age unknown"
    must not read as "brand new" (the (hk) rule this book already carries)."""
    rows = rows if rows is not None else H.order_book_details()
    now = time.time()
    out = []
    for r in rows:
        if str(r.get("status") or "active").lower() != "active":
            continue
        sym = str(r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        try:
            t = float(r.get("created_at") or 0)
        except (TypeError, ValueError):
            continue
        if t > 1e11:
            t /= 1000.0
        # epoch-0 and future stamps are UNKNOWN, not ancient and not newborn.
        if t <= 86400 or t > now:
            continue
        if max_age_d is not None and (now - t) / 86400.0 > max_age_d:
            continue
        try:
            qv = float(r.get("daily_quote_token_volume") or 0.0)
        except (TypeError, ValueError):
            qv = 0.0
        try:
            cls = int(r.get("strategy_index"))
        except (TypeError, ValueError):
            continue
        out.append((sym, t, cls, qv))
    return sorted(out, key=lambda x: x[1])


def debut_tape(bs, span_h, ids=None, cache=CACHE, refresh=False, verbose=True):
    """1h bars from each birth to birth+span_h. Cached by (sym, window)."""
    ids = ids or H.market_ids()
    store = {}
    if os.path.exists(cache) and not refresh:
        try:
            with open(cache) as fh:
                store = json.load(fh)
        except (OSError, ValueError):
            store = {}
    tape, miss = {}, 0
    for i, (sym, t0, _c, _v) in enumerate(bs):
        mid = ids.get(sym)
        if mid is None:
            miss += 1
            continue
        lo, hi = int(t0), int(t0 + span_h * 3600)
        key = f"debut1h:{sym}:{lo}:{hi}"
        rowsc = store.get(key)
        if rowsc is None:
            try:
                rowsc = {str(k): v for k, v in
                         H.fetch_candles(mid, lo, hi, "1h").items()}
            except Exception as e:                          # noqa: BLE001
                if verbose:
                    print(f"    fetch failed {sym}: {e}", file=sys.stderr)
                rowsc = {}
            store[key] = rowsc
            if verbose and i % 15 == 0:
                print(f"  debut tape {i}/{len(bs)} {sym}", file=sys.stderr)
        tape[sym] = {int(k): tuple(v) for k, v in rowsc.items()}
    try:
        with open(cache, "w") as fh:
            json.dump(store, fh)
    except OSError:
        pass
    return tape, miss


def entries_at(bs, tape, delay_h, is_long, min_vol_usd=0.0):
    """One entry per birth, LAG-1 at the OPEN of the first bar at/after
    birth+delay. A book with no bar there simply produces no entry."""
    out = []
    for sym, t0, cls, qv in bs:
        if qv < min_vol_usd:
            continue
        bars = tape.get(sym) or {}
        if not bars:
            continue
        want = t0 + delay_h * 3600
        after = [t for t in sorted(bars) if t >= want]
        if not after:
            continue
        nt = after[0]
        o = bars[nt][0]
        if not o or o <= 0:
            continue
        out.append({"sym": sym, "entry_ts": float(nt), "entry_px": float(o),
                    "is_long": is_long, "entry_priced": False,
                    "notional": H.CLIP_USD, "qvol": qv,
                    "cls": cls, "vp": venue_priced(sym, cls),
                    "birth_ts": t0, "source": "debut"})
    return out


def young_window_entries(bs, tape, is_long, max_bars_d=21, min_vol_usd=0.0,
                        cooldown_h=168.0, span_h=None):
    """Entries the `young` SOURCE would actually produce — not debut-bar ones.

    `young_candidates` admits a book any time it still has <= YOUNG_MAX_BARS
    daily bars, and `surge_done` then holds it off for SURGE_COOLDOWN_H. So the
    real cell is "entered somewhere inside the first 21 days, at most once per
    168h", NOT "entered at the debut bar" — and the two are different
    populations. Measuring the debut bar and shipping a young-window gate is
    the (I7) mistake of grading a rule on a trigger it does not actually fire on.

    One entry per book per cooldown window, LAG-1 at a bar open, while the book
    is still inside its young window.
    """
    out = []
    for sym, t0, cls, qv in bs:
        if qv < min_vol_usd:
            continue
        bars = tape.get(sym) or {}
        if not bars:
            continue
        ts = sorted(bars)
        end = t0 + max_bars_d * 86400
        nxt = t0
        while nxt < end:
            after = [t for t in ts if t >= nxt]
            if not after:
                break
            bt = after[0]
            if bt >= end:
                break
            o = bars[bt][0]
            if o and o > 0:
                out.append({"sym": sym, "entry_ts": float(bt),
                            "entry_px": float(o), "is_long": is_long,
                            "entry_priced": False, "notional": H.CLIP_USD,
                            "qvol": qv, "cls": cls,
                            "vp": venue_priced(sym, cls), "birth_ts": t0,
                            "source": "young_window"})
            nxt = bt + cooldown_h * 3600
    return out


def cell(entries, tape, rule, horizon_h, cap=None, tiers=None):
    """Score one (entries, rule, horizon) cell, clustered by BIRTH MONTH.

    Debut entries on one venue cluster hard in time — a listing wave is one
    event, not N independent ones — so the plain t is not the honest statistic.
    """
    tiers = tiers or H.SLIP_TIERS_MEAN
    s = H.simulate(entries, tape, rule, horizon_h, basis="poll", cap=cap,
                   tiers=tiers)
    closed = s.get("closed") or []
    if closed:
        month = {}
        for e in entries:
            month[e["sym"]] = int(e["birth_ts"] // (30 * 86400))
        groups = [month.get(c["sym"], 0) for c in closed]
        rets = [100.0 * c["ret"] for c in closed]
        # cluster_t returns (t, n_clusters) — unpack, never store the tuple.
        tc, n_cl = H.cluster_t(rets, groups)
        s["t_cluster_month"] = tc
        s["n_months"] = n_cl
    return s


def _fmt(s, name):
    """Render one cell.

    Reads the keys `score()` ACTUALLY publishes — `win_rate` (a fraction),
    `top1_share` (None when the total is negative, because a share of a loss
    is not a tail), `ex_top1_mean_pct`, `h1_pct`/`h2_pct`. Guessing these names
    is the (hj) defect; the first draft of this function printed win=0.0% on
    every cell because it invented `win_pct`.
    """
    if not s or not s.get("n"):
        return f"  {name:34s}  n=0"
    def _n(v, d=2, w=6):
        return f"{v:>{w}.{d}f}" if isinstance(v, (int, float)) else f"{'na':>{w}}"
    share = s.get("top1_share")
    halves = "++" if s.get("both_halves_pos") else \
             ("+-" if (s.get("h1_pct") or 0) > 0 else
              ("-+" if (s.get("h2_pct") or 0) > 0 else "--"))
    return (f"  {name:34s}  n={s['n']:>4} "
            f"${s.get('total_usd', 0):>8.2f} "
            f"{s.get('mean_pct', 0):>+7.3f}%/t "
            f"t={_n(s.get('t'))} "
            f"ctM={_n(s.get('t_cluster_month'))} "
            f"halves={halves} "
            f"win={100 * s.get('win_rate', 0):>5.1f}% "
            f"exTop1={_n(s.get('ex_top1_mean_pct'), 3, 7)} "
            f"top1={('%.0f%%' % (100 * share)) if share is not None else '  na':>5s} "
            f"skip={s.get('skipped', 0)}")


def _selftest():
    """Offline, pure. Pins the two properties that decide whether this study
    may speak at all, plus the split it exists to measure."""
    # 1) the venue-priced split is a CLASSIFICATION, and it is not `class == 2`
    assert venue_priced("ANSEM", 7) is True
    assert venue_priced("CASHCAT", 7) is True
    assert venue_priced("ANTHROPIC", 7) is False
    assert venue_priced("UNITREE", 7) is False
    assert venue_priced("US10Y", 7) is False
    assert venue_priced("BTC", 2) is True
    for c in (3, 4, 5, 6):
        assert venue_priced("ANYTHING", c) is False, c
    # a class-7 name NOT declared external is venue-priced (fail toward the
    # book's own thesis, and auditable because the list is small)
    assert venue_priced("SOMENEWMEME", 7) is True

    # 2) births() drops unusable stamps rather than coercing them
    now = time.time()
    rows = [
        {"symbol": "OK", "status": "active", "created_at": now - 5 * 86400,
         "strategy_index": 2, "daily_quote_token_volume": 1e6},
        {"symbol": "EPOCH0", "status": "active", "created_at": 0,
         "strategy_index": 2},
        {"symbol": "FUTURE", "status": "active", "created_at": now + 9e5,
         "strategy_index": 2},
        {"symbol": "JUNK", "status": "active", "created_at": "n/a",
         "strategy_index": 2},
        {"symbol": "DEAD", "status": "inactive", "created_at": now - 5 * 86400,
         "strategy_index": 2},
        {"symbol": "NOCLASS", "status": "active", "created_at": now - 5 * 86400,
         "strategy_index": None},
    ]
    got = [s for s, *_ in births(rows)]
    assert got == ["OK"], got
    # ms stamps resolve the same as seconds
    assert births([{"symbol": "MS", "status": "active",
                    "created_at": (now - 3 * 86400) * 1000,
                    "strategy_index": 2}])[0][0] == "MS"

    # 3) entries are LAG-1 at a bar OPEN at/after birth+delay, never before
    t0 = 1_800_000
    bars = {t0 + i * 3600: (100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1e5)
            for i in range(10)}
    tape = {"X": bars}
    bs = [("X", float(t0), 2, 1e6)]
    e0 = entries_at(bs, tape, 0, True)
    assert len(e0) == 1 and e0[0]["entry_ts"] == t0, e0
    e3 = entries_at(bs, tape, 3, True)
    assert e3[0]["entry_ts"] == t0 + 3 * 3600, e3
    assert e3[0]["entry_px"] == bars[t0 + 3 * 3600][0], e3
    # a delay past the end of the tape yields NO entry rather than a clamped one
    assert entries_at(bs, tape, 99, True) == []
    # the volume floor binds
    assert entries_at([("X", float(t0), 2, 10.0)], tape, 0, True,
                      min_vol_usd=1e6) == []

    # 4) direction actually inverts the P&L on a monotone tape
    rule = {"tp_pct": None, "sl_pct": None, "max_hold_h": 5}
    lo = H.simulate(entries_at(bs, tape, 0, True), tape, rule, 5, cap=None)
    sh = H.simulate(entries_at(bs, tape, 0, False), tape, rule, 5, cap=None)
    assert lo["n"] == sh["n"] == 1
    assert lo["mean_pct"] > 0 > sh["mean_pct"], (lo["mean_pct"], sh["mean_pct"])
    print("study_sniper_debut_direction selftest: OK (4 groups)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--span-h", type=float, default=400.0,
                    help="hours of tape to fetch from each birth")
    ap.add_argument("--delays", default="0,1,3,6,12,24")
    ap.add_argument("--horizons", default="6,24,72,168")
    ap.add_argument("--min-vol-m", type=float, default=0.0,
                    help="skip births whose CURRENT 24h volume is below this")
    ap.add_argument("--cap", type=int, default=None,
                    help="concurrent-position cap (default: the bot's MAX_OPEN)")
    ap.add_argument("--slip", choices=("mean", "p90", "zero"), default="mean")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    tiers = {"mean": H.SLIP_TIERS_MEAN, "p90": H.SLIP_TIERS_P90,
             "zero": [(float("inf"), 0.0)]}[a.slip]
    cap = a.cap if a.cap is not None else H.shipped_cap()
    # shipped_rule() returns (rule, provenance) — the provenance string names
    # the module and the literals it read, so it is printed rather than dropped.
    rule, provenance = H.shipped_rule()
    print(f"SHIPPED RULE: {rule}\n  provenance: {provenance}\n"
          f"  cap={cap}  slip={a.slip}")

    rows = H.order_book_details()
    bs = births(rows)
    print(f"\nBIRTHS with a usable created_at: {len(bs)} of "
          f"{sum(1 for r in rows if str(r.get('status') or 'active').lower() == 'active')} active books")
    from collections import Counter
    print("  by class:", dict(sorted(Counter(CLASS_NAME.get(c, c)
                                             for _s, _t, c, _v in bs).items())))
    print("  venue-priced:",
          sum(1 for s, _t, c, _v in bs if venue_priced(s, c)),
          " externally-priced:",
          sum(1 for s, _t, c, _v in bs if not venue_priced(s, c)))

    tape, miss = debut_tape(bs, a.span_h, refresh=a.refresh)
    print(f"  tape: {len(tape)} books ({miss} unmapped)")

    delays = [float(x) for x in a.delays.split(",") if x.strip()]
    horizons = [float(x) for x in a.horizons.split(",") if x.strip()]
    minv = a.min_vol_m * 1e6

    print("\n" + "=" * 100)
    print("THE DIRECTION QUESTION — shipped tp/sl, HOLD SWEPT, both sides")
    print("  NOTE: the hold is swept ON THE RULE, not merely on the walk")
    print("  horizon. The shipped rule carries max_hold_h=6, which dominates")
    print("  the walk — sweeping the horizon alone yields byte-identical cells")
    print("  at every horizon, which is what a sweep that is not sweeping")
    print("  looks like. Identical rows across a swept parameter are a bug.")
    print("=" * 100)
    for h in horizons:
        rl = dict(rule, max_hold_h=h)
        print(f"\n hold {h:g}h  (tp {rule.get('tp_pct')} / sl {rule.get('sl_pct')})")
        for d in delays:
            for lng in (True, False):
                e = entries_at(bs, tape, d, lng, min_vol_usd=minv)
                s = cell(e, tape, rl, h, cap=cap, tiers=tiers)
                print(_fmt(s, f"delay {d:>4g}h  {'LONG ' if lng else 'SHORT'}"))

    print("\n" + "=" * 100)
    print("THE SPLIT — venue-priced vs externally-priced (the (lk) axis)")
    print("=" * 100)
    for h in horizons:
        rl = dict(rule, max_hold_h=h)
        print(f"\n hold {h:g}h  (delay 0, the debut bar)")
        for lng in (True, False):
            ents = entries_at(bs, tape, 0.0, lng, min_vol_usd=minv)
            for label, sel in (("venue-priced", lambda x: x["vp"]),
                               ("externally-priced", lambda x: not x["vp"])):
                s = cell([x for x in ents if sel(x)], tape, rl, h,
                         cap=cap, tiers=tiers)
                print(_fmt(s, f"{'LONG ' if lng else 'SHORT'} {label}"))

    print("\n" + "=" * 100)
    print("BY CLASS — shipped bracket, delay 0")
    print("=" * 100)
    for h in horizons:
        rl = dict(rule, max_hold_h=h)
        print(f"\n hold {h:g}h")
        for lng in (True, False):
            ents = entries_at(bs, tape, 0.0, lng, min_vol_usd=minv)
            for c in sorted({x["cls"] for x in ents}):
                s = cell([x for x in ents if x["cls"] == c], tape, rl, h,
                         cap=cap, tiers=tiers)
                print(_fmt(s, f"{'LONG ' if lng else 'SHORT'} class {c} "
                              f"({CLASS_NAME.get(c, c)})"))

    print("\n" + "=" * 100)
    print("THE CONTROL — content-free timer, no tp/sl ((hl): is the bracket "
          "doing anything?)")
    print("=" * 100)
    timer = {"tp_pct": None, "sl_pct": None, "max_hold_h": None}
    for h in horizons:
        print(f"\n horizon {h:g}h")
        for lng in (True, False):
            e = entries_at(bs, tape, 0.0, lng, min_vol_usd=minv)
            for label, sel in (("all", lambda x: True),
                               ("venue-priced", lambda x: x["vp"])):
                s = cell([x for x in e if sel(x)], tape,
                         dict(timer, max_hold_h=h), h, cap=cap, tiers=tiers)
                print(_fmt(s, f"TIMER {'LONG ' if lng else 'SHORT'} {label}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
