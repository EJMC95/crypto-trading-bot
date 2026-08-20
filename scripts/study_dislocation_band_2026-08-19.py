#!/usr/bin/env python3
"""
scripts/study_dislocation_band_2026-08-19.py — the harness behind 🧭 nav-cook's
founding claim, REBUILT AND COMMITTED.

WHY THIS FILE EXISTS
  `STUDY_DISLOCATION_BAND_2026-08-19.md` published n=216, +0.367%/trade,
  t=+2.74 for the [45,60)bps mirror at a 4h horizon, and a LIVE BOOK was built
  on it — but the harness lived in a session scratchpad and was never
  committed. `(sa)` then found that an independent replay could not reproduce
  the cell (it read n=697, -0.165%, t=-2.61) and correctly REFUSED its own
  numbers under the calibration gate, naming the missing harness as the cause.
  The scratchpad is now gone. A live book's founding claim that nobody can
  re-run is not evidence — it is a rumour with a number attached.

  This file is the reconstruction. It is deliberately EXPLICIT about every
  convention the original made implicitly, because the n=216-vs-697 gap is
  almost certainly a convention difference, not a data difference.

THE CONVENTIONS, NAMED (each one is a place two honest replays can diverge)
  C1 SIGNAL SOURCE  the scout's `prem_outliers`, which is HARD-CAPPED at 8
                    entries per snapshot. A symbol outside the top 8 is
                    INVISIBLE, not "not dislocated".
  C2 CONFIRM        entry requires the band to hold at BOTH t-LAGS and t.
                    Requiring only t-LAGS admits far more episodes — the
                    single most likely source of an n gap.
  C3 EXIT-ON-ABSENT a held symbol that DROPS OFF the top-8 list is treated as
                    CONVERGED. It is the only available reading (the feed
                    cannot say "still 50bps but ranked 9th"), and it is
                    reported separately because it is an artefact of C1.
  C4 EPISODES       one open position per symbol at a time; no position cap.
  C5 COST           ONE round trip of the book's own slippage, per coin tier
                    from the (js)/(qq) fill study. A forward replay, so the
                    (qw) double-slippage error does not apply.

Read-only: consumes bot_state_history. No bot, no orders, no writes.
Usage:
    python3 scripts/study_dislocation_band_2026-08-19.py --fetch    # cache tape
    python3 scripts/study_dislocation_band_2026-08-19.py            # run grid
    python3 scripts/study_dislocation_band_2026-08-19.py --selftest
"""
import argparse
import bisect
import json
import math
import os
import pickle
import statistics as st
import sys

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".disloc_band_cache.pkl")
GATE_BANDS = [(30, 45), (45, 60), (60, 90), (90, 150), (150, float("inf")),
              (60, float("inf"))]
HOLDS_S = [1800, 3600, 7200, 14400, 28800]
CONFIRM_LAGS = 2
EXIT_FRAC = 0.667
HARD_STOP = 0.05
MIN_VOL_M = 0.5

# (js)/(qq): MEAN bps per fill by daily volume tier — a continuous strategy
# pays the average of its fills, not the median.
def slip_bps(vol_m):
    return (0.61 if vol_m >= 10 else 1.18 if vol_m >= 2 else
            5.35 if vol_m >= 1 else 2.52 if vol_m >= 0.1 else 17.49)


def fetch_tape():
    """Snapshots from the scout's own history — the venue read the bot gates on."""
    import subprocess
    import psycopg2
    import psycopg2.extras
    url = [l.split("=", 1)[1].strip() for l in subprocess.check_output(
        ["railway", "variables", "--service", "Postgres", "--kv"],
        text=True).splitlines() if l.startswith("DATABASE_PUBLIC_URL=")][0]
    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""select ts, payload->'prem_outliers' po, payload->'marks' mk,
                          payload->'vols' v, payload->'classes' cl
                   from bot_state_history where key='lighter-market'
                   order by ts""")
    out = []
    for r in cur.fetchall():
        if not r["po"] or not r["mk"]:
            continue
        prem = {o["sym"]: o.get("prem_bps") for o in r["po"]
                if isinstance(o, dict) and o.get("prem_bps") is not None}
        out.append((int(r["ts"].timestamp()), prem, r["mk"],
                    r["v"] or {}, r["cl"] or {}))
    pickle.dump(out, open(CACHE, "wb"))
    print("cached %d snapshots -> %s" % (len(out), CACHE))
    return out


def load_tape():
    if not os.path.exists(CACHE):
        sys.exit("no cache — run with --fetch first")
    return pickle.load(open(CACHE, "rb"))


def replay(snaps, lo, hi, hold_s, confirm_lags=CONFIRM_LAGS,
           require_current=True, exclude_classes=(), min_vol=MIN_VOL_M,
           absent_exits=True):
    """The mirror: LONG the premium-rich, SHORT the discounts (the ghost's
    inverse). `require_current` toggles C2 — the convention most likely to
    explain an n gap between two honest replays."""
    opened, trades = {}, []
    for i, (ts, prem, marks, vols, classes) in enumerate(snaps):
        # --- exits first
        for sym in list(opened):
            pos = marks.get(sym)
            if pos is None:
                continue
            p = opened[sym]
            cur = prem.get(sym)
            ret = (pos / p["entry"] - 1.0) * (1 if p["long"] else -1)
            absent = cur is None                      # C3
            if absent and not absent_exits:
                # SENSITIVITY: refuse the truncation artefact — a symbol that
                # merely fell out of the top-8 feed is NOT evidence of
                # convergence, so hold it and let stop/max_hold decide.
                if (ts - p["t0"]) < hold_s and ret > -HARD_STOP:
                    continue
                converged = False
            else:
                converged = absent or abs(cur) < EXIT_FRAC * lo
            if ret <= -HARD_STOP or converged or (ts - p["t0"]) >= hold_s:
                trades.append({
                    "sym": sym, "ret": ret, "t0": p["t0"],
                    "hold_s": ts - p["t0"], "vol": p["vol"],
                    "why": ("stop" if ret <= -HARD_STOP else
                            "absent" if absent else
                            "converged" if converged else "max_hold")})
                del opened[sym]
        # --- entries
        if i < confirm_lags:
            continue
        past = snaps[i - confirm_lags][1]
        for sym, pb in past.items():
            if sym in opened or not (lo <= abs(pb) < hi):
                continue
            if require_current:                        # C2
                cur = prem.get(sym)
                if cur is None or not (lo <= abs(cur) < hi):
                    continue
            v = vols.get(sym) or 0.0
            if v < min_vol:
                continue
            if exclude_classes and classes.get(sym) in exclude_classes:
                continue
            px = marks.get(sym)
            if not px or px <= 0:
                continue
            opened[sym] = {"entry": px, "t0": ts, "long": pb > 0, "vol": v}
    return trades


def stats(trades):
    if len(trades) < 8:
        return None
    net = [t["ret"] - 2 * slip_bps(t["vol"]) / 1e4 for t in trades]
    m = st.fmean(net)
    sd = st.stdev(net)
    se = sd / math.sqrt(len(net)) if sd else 0.0
    return {"n": len(net), "mean": m, "t": (m / se if se else 0.0),
            "win": sum(1 for x in net if x > 0) / len(net),
            "med_hold_min": st.median([t["hold_s"] for t in trades]) / 60.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    snaps = fetch_tape() if args.fetch else load_tape()
    print("tape: %d snapshots\n" % len(snaps))

    print("THE CALIBRATION QUESTION — does the published cell reproduce?")
    print("  published (STUDY_DISLOCATION_BAND_2026-08-19.md): "
          "n=216  +0.367%/trade  t=+2.74   [45,60) x 4h")
    for rc in (True, False):
        s = stats(replay(snaps, 45, 60, 14400, require_current=rc))
        tag = "C2 strict (band holds at t-2 AND t)" if rc else \
              "C2 loose  (band holds at t-2 only)"
        print("  %-38s %s" % (tag,
              ("n=%d  %+.3f%%  t=%+.2f  win %.0f%%  medhold %.0f min"
               % (s["n"], 100 * s["mean"], s["t"], 100 * s["win"],
                  s["med_hold_min"])) if s else "too few"))

    print("\nGRID — net %/trade (t) [n], all instruments, C2 strict")
    hdr = "%14s" % "band" + "".join("%18s" % ("%dm" % (h // 60) if h < 3600
                                              else "%dh" % (h // 3600))
                                    for h in HOLDS_S)
    print(hdr + "\n" + "-" * len(hdr))
    for lo, hi in GATE_BANDS:
        lab = "[%d,%s)" % (lo, "inf" if hi == float("inf") else int(hi))
        row = "%14s" % lab
        for h in HOLDS_S:
            s = stats(replay(snaps, lo, hi, h))
            row += ("%+8.3f%%%+6.2f[%3d]" % (100 * s["mean"], s["t"], s["n"])
                    if s else "%18s" % "--")
        print(row)

    print("\nEXIT MIX for [45,60) x 4h — `absent` is the C1 truncation artefact")
    tr = replay(snaps, 45, 60, 14400)
    mix = {}
    for t in tr:
        mix[t["why"]] = mix.get(t["why"], 0) + 1
    print("  " + "  ".join("%s=%d" % kv for kv in sorted(mix.items())))


def _selftest():
    # a two-symbol synthetic tape: one clean in-band episode that converges
    snaps = []
    for i in range(12):
        prem = {"AAA": 50.0 if i < 6 else 5.0, "BBB": 5.0}
        marks = {"AAA": 100.0 * (1.0 + 0.01 * min(i, 6)), "BBB": 10.0}
        snaps.append((i * 300, prem, marks, {"AAA": 5.0, "BBB": 5.0},
                      {"AAA": 2, "BBB": 2}))
    tr = replay(snaps, 45, 60, 7200)
    assert len(tr) == 1, "expected exactly ONE episode, got %d" % len(tr)
    assert tr[0]["sym"] == "AAA"
    # premium POSITIVE -> the mirror is LONG -> a rising mark is a WIN
    assert tr[0]["ret"] > 0, "mirror of a positive premium must be long"
    # C2 matters: loose admits at least as many episodes as strict
    a = len(replay(snaps, 45, 60, 7200, require_current=True))
    b = len(replay(snaps, 45, 60, 7200, require_current=False))
    assert b >= a, "the loose confirm cannot admit FEWER episodes"
    # the band is half-open on both edges
    assert len(replay(snaps, 50, 60, 7200)) == 1
    assert len(replay(snaps, 30, 45, 7200)) == 0, "50bps is not in [30,45)"
    assert len(replay(snaps, 60, 90, 7200)) == 0, "50bps is not in [60,90)"
    # class screen
    assert len(replay(snaps, 45, 60, 7200, exclude_classes=(2,))) == 0
    # COST TIERS ARE NOT MONOTONE IN LIQUIDITY, and that is the measurement,
    # not a bug: (qq) read $1-2M at a MEAN 5.35 bps against $0.1-1M's 2.52,
    # because the $1-2M tier carries a fat tail (median 1.03, mean 5.35). An
    # earlier version of this assert encoded the intuition instead of the data
    # and failed on first run — recorded so nobody "fixes" the table to match.
    assert slip_bps(20) < slip_bps(5) < slip_bps(0.5)      # the broad direction
    assert slip_bps(1.5) > slip_bps(0.5), "the $1-2M fat tail is real"
    assert slip_bps(0.01) == max(slip_bps(x) for x in (20, 5, 1.5, 0.5, 0.01))
    s = stats([{"ret": 0.01, "vol": 5.0, "hold_s": 60}] * 10)
    assert s["n"] == 10 and s["mean"] < 0.01, "cost must be charged"
    print("study_dislocation_band selftest OK")


if __name__ == "__main__":
    main()
