#!/usr/bin/env python3
"""
backtest_farmer_breadth_lighter.py — does BREADTH (explore beyond the hottest
funders) and CONVICTION SIZING earn more for the Funding Farmer on LIGHTER's own
tape?

WHY (2026-07-24, operator: "i want the farmer to reach higher highs, and not be
restricted to what it knows to win on"). The live Farmer concentrates into ~2
coins because scan_candidates ranks the whole eligible pool by |apr| and only
deep-scans the top SCAN_DEEP_MAX=15 — a pure EXPLOIT ranker with no explore
budget. This tests two additions BEFORE they touch the live-money bot
(backtest-first doctrine), on Lighter's own settled tape ONLY
([[backtest-on-lighter-only]]):

  L1 EXPLORE     — reserve K of the 6 slots for coverage-sampled coins ranked
                   BELOW the top exploit set, still gate+persist+VOL-screened
                   (the durable quality gate). Question: does the explore SLICE
                   earn, or at least not lose? That is the breadth question — is
                   there edge beyond the 2 coins it knows.

                   **[(vj)] ON THE LIVE BOT'S OWN POPULATION THE EXPLORE SLICE
                   IS EMPTY, SO THIS QUESTION HAS NEVER ACTUALLY BEEN ASKED.**
                   (su) found this study's loader picks its universe by RANK
                   while the live Farmer filters on an absolute $10M/day floor
                   that only 11 of 212 markets clear. Re-run against that floor:
                   base -38.80 n=817 · +explore -38.80 n=817 · **explore slice
                   n=0, `identical=True`** — byte-identical to baseline, on BOTH
                   windows (150d and the recorded 2026-02-24..07-24) and BOTH
                   slip cells (5bps and 0.5bps). There is nothing below the top
                   exploit set that clears the live floor, so any earlier
                   "explore earns / is neutral" reading was measured on coins
                   the book refuses. The verdict is not NEGATIVE, it is
                   **STRUCTURALLY UNMEASURABLE at the shipped floor** — and the
                   two are not the same: `{n: 0}` is byte-identical between
                   "quiet" and "impossible" ((lv)), which is exactly why this
                   note exists rather than a number.
                   Where the slice IS populated (rank-selected, no floor) it
                   LOSES: all-30 n=168 **-$0.096/t** (5bps) / -$0.073/t
                   (0.5bps), maxDD -51.04 -> -64.06; top-25 by mean-vol24 n=145
                   **-$0.117/t** / -$0.095/t. So the honest summary is: on the
                   population the book trades there is no slice to measure, and
                   on the population it does not trade the slice loses.
  L2 CONVICTION  — size each slot by a bounded function of its conviction (|apr|,
                   crowding) instead of a flat clip. Two variants:
                     REALLOC — same total budget (mean mult ~1x): isolates
                               allocation SKILL from leverage.
                     SCALED  — floor 1x, up to 2.2x on the hottest: the "higher
                               highs" the operator asked for. Reports realized
                               mean mult + notional-hours so the added leverage
                               is explicit. Production ALSO bounds this by the
                               venues/safety notional cap — not modelled here;
                               the backtest asks only whether the SIGNAL has merit.

FIDELITY: reuses backtest_funding_lighter.load() (same Lighter data path + cache)
and copies its EXACT exit ladder including the `hot.pop` persistence parity —
whose ABSENCE once inverted a shipped verdict (+$21.32 -> -$11.57)
([[harness-must-mirror-productions-close-path]]). One variable at a time vs the
exploit/flat baseline ([[ab-tests-must-vary-exactly-one-variable]]). Lighter-only:
the imported loader never touches another venue.

Read-only: hits public Lighter endpoints via the imported loader; writes nothing.
    python3 scripts/backtest_farmer_breadth_lighter.py --universe 25
    python3 scripts/backtest_farmer_breadth_lighter.py --explore-k 2 --days 150
"""
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as base  # noqa: E402  (reuse loader + tuned config)

# live-bot config, mirrored from the imported module (single source of truth)
SLIP = base.SLIP
PERSIST_H = base.PERSIST_H
MAX_HOLD_H = base.MAX_HOLD_H
HARD_STOP = base.HARD_STOP
TAKE_PROFIT = base.TAKE_PROFIT
MAX_OPEN = base.MAX_OPEN
EXIT_RATIO = base.EXIT_RATIO
ORDER_USD = base.ORDER_USD

# the durable quality gate (lighter_funding_bot.SCAN_VETO_VOL) — the piece the
# scanner backtest found to be the robust win. Explore is screened by it too, so
# "breadth" never means "trade convulsing junk".
VETO_VOL = 0.015
VOL_LOOKBACK_H = 24

# conviction bounds
REALLOC_LO, REALLOC_HI = 0.6, 1.6
SCALED_LO, SCALED_HI = 1.0, 2.2   # floor at 1x: only ever sizes UP (higher highs)


def realized_vol(cand, t, lookback_h=VOL_LOOKBACK_H):
    """stdev of hourly simple returns of closes over (t-lookback, t]. None if the
    window is too thin to verify risk (production SCAN_SKIPs that case)."""
    closes = []
    tt = t - lookback_h * 3600
    while tt <= t:
        c = cand.get(tt)
        if c is not None:
            closes.append(c[3])
        tt += 3600
    if len(closes) < 6:
        return None
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]]
    if len(rets) < 5:
        return None
    return statistics.pstdev(rets)


def _conv_mult(apr, ref_w, mode):
    """Bounded conviction multiplier off |apr| relative to the reference (median
    entry |apr|). REALLOC centres on ~1x (allocation only); SCALED floors at 1x."""
    if mode == "none" or ref_w <= 0:
        return 1.0
    raw = abs(apr) / ref_w
    lo, hi = (REALLOC_LO, REALLOC_HI) if mode == "realloc" else (SCALED_LO, SCALED_HI)
    return max(lo, min(hi, raw))


def run_breadth(mk, enter_apr, t0, t1, *, explore_k=0, conv="none", ref_w=0.10,
                collect_entry_aprs=False):
    """Replay the Farmer's rules over [t0,t1) with an |apr|-ranked exploit fill,
    an optional coverage-sampled EXPLORE reservation, and optional conviction
    sizing. Returns overall + per-source (exploit/explore) breakdown.

    The exit ladder + funding accrual + persistence parity are COPIED VERBATIM
    from backtest_funding_lighter.run — do not edit them out of sync."""
    exit_apr = enter_apr * EXIT_RATIO
    top_cut = max(0, MAX_OPEN - explore_k)     # slots the exploit ranker may hold
    hours = sorted({t for m in mk.values() for t in m["fund"] if t0 <= t < t1})
    pos, hot, cool, last_tried = {}, {}, {}, {}
    eq = peak = maxdd = 0.0
    ntl_hours = 0.0                            # notional-hours (leverage transparency)
    entry_aprs = []
    # per-source tallies
    S = {"exploit": dict(n=0, w=0, pnl=0.0), "explore": dict(n=0, w=0, pnl=0.0)}
    mults = []

    for t in hours:
        # ---------- manage open positions (VERBATIM exit ladder) ----------
        for sym in list(pos):
            m = mk[sym]
            apr, c = m["fund"].get(t), m["cand"].get(t)
            if apr is None or c is None:
                continue
            _o, hi, lo, close = c
            p = pos[sym]
            f = (1.0 if p["short"] else -1.0) * (apr / (24 * 365)) * p["ntl"]
            p["fund"] += f
            ntl_hours += p["ntl"]
            held_h = (t - p["t0"]) / 3600.0
            adverse = ((hi - p["px"]) / p["px"]) if p["short"] else ((p["px"] - lo) / p["px"])
            favour = ((p["px"] - lo) / p["px"]) if p["short"] else ((hi - p["px"]) / p["px"])
            out_px, why = None, None
            if adverse >= HARD_STOP:
                out_px, why = p["px"] * (1 + HARD_STOP if p["short"] else 1 - HARD_STOP), "stop"
            elif favour >= TAKE_PROFIT:
                out_px, why = p["px"] * (1 - TAKE_PROFIT if p["short"] else 1 + TAKE_PROFIT), "tp"
            elif (p["short"] and apr < 0) or (not p["short"] and apr > 0):
                out_px, why = close, "flip"
            elif abs(apr) < exit_apr:
                out_px, why = close, "cold"
            elif held_h >= MAX_HOLD_H:
                out_px, why = close, "max_hold"
            if out_px is not None:
                raw = (p["px"] - out_px) / p["px"] if p["short"] else (out_px - p["px"]) / p["px"]
                pp = raw * p["ntl"] - 2 * SLIP * p["ntl"]
                tot = pp + p["fund"]
                src = p["src"]
                S[src]["n"] += 1
                S[src]["w"] += 1 if tot > 0 else 0
                S[src]["pnl"] += tot
                eq += tot
                peak = max(peak, eq)
                maxdd = min(maxdd, eq - peak)
                cool[sym] = t + 12 * 3600 if why == "stop" else 0
                pos.pop(sym)
                hot.pop(sym, None)     # persistence parity — DO NOT REMOVE

        # ---------- eligibility (gate + persist + cool + vol screen) ----------
        elig = []
        for sym, m in mk.items():
            if sym in pos:
                continue
            apr, c = m["fund"].get(t), m["cand"].get(t)
            if apr is None or c is None:
                continue
            if abs(apr) >= enter_apr:
                hot[sym] = hot.get(sym) or t
            else:
                hot[sym] = None
                continue
            if (t - hot[sym]) / 3600.0 < PERSIST_H:
                continue
            if t < cool.get(sym, 0):
                continue
            vol = realized_vol(m["cand"], t)
            if vol is None or vol > VETO_VOL:          # quality veto (both arms)
                continue
            elig.append((sym, apr, vol))

        if not elig:
            continue
        elig.sort(key=lambda x: -abs(x[1]))            # exploit signal = |apr|
        exploit_pool = elig[:top_cut]
        explore_pool = elig[top_cut:]                  # "beyond what it knows"

        ne = sum(1 for p in pos.values() if p["src"] == "exploit")
        nx = sum(1 for p in pos.values() if p["src"] == "explore")

        def _open(sym, apr, vol, src):
            mult = _conv_mult(apr, ref_w, conv)
            mults.append(mult)
            pos[sym] = {"px": mk[sym]["cand"][t][3], "short": apr > 0, "t0": t,
                        "ntl": ORDER_USD * mult, "fund": 0.0, "src": src}
            last_tried[sym] = t
            if collect_entry_aprs:
                entry_aprs.append(abs(apr))

        # fill EXPLOIT from the hottest
        ei = 0
        while len(pos) < MAX_OPEN and ne < top_cut and ei < len(exploit_pool):
            sym, apr, vol = exploit_pool[ei]; ei += 1
            _open(sym, apr, vol, "exploit"); ne += 1
        # fill EXPLORE by COVERAGE (least-recently-tried; never-tried first)
        explore_pool.sort(key=lambda x: (last_tried.get(x[0], 0), -abs(x[1])))
        xi = 0
        while len(pos) < MAX_OPEN and nx < explore_k and xi < len(explore_pool):
            sym, apr, vol = explore_pool[xi]; xi += 1
            _open(sym, apr, vol, "explore"); nx += 1
        # don't waste scarce slots: any slot still free -> best remaining exploit
        while len(pos) < MAX_OPEN and ei < len(exploit_pool):
            sym, apr, vol = exploit_pool[ei]; ei += 1
            _open(sym, apr, vol, "exploit")

    n = S["exploit"]["n"] + S["explore"]["n"]
    return {
        "pnl": eq, "n": n, "maxdd": maxdd,
        "win": 100.0 * (S["exploit"]["w"] + S["explore"]["w"]) / n if n else 0.0,
        "exploit": S["exploit"], "explore": S["explore"],
        "mean_mult": (sum(mults) / len(mults)) if mults else 1.0,
        "ntl_hours": ntl_hours,
        "entry_aprs": entry_aprs,
    }


def _fmt_src(s):
    if not s["n"]:
        return "n=0"
    return f"n={s['n']:>3d} net=${s['pnl']:>7.2f} win={100*s['w']/s['n']:>4.0f}% (${s['pnl']/s['n']:+.3f}/t)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--universe", type=int, default=25)
    ap.add_argument("--explore-k", type=int, default=2)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Fetching LIGHTER history — {a.days}d, top {a.universe} by daily quote volume")
    mk = base.load(a.days, a.universe, a.refresh)
    if not mk:
        raise SystemExit("no markets with paired funding+candle history")
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2
    import time
    print(f"\n{len(mk)} markets | {time.strftime('%Y-%m-%d', time.gmtime(lo))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(hi))} ({(hi-lo)/86400:.0f}d)")
    print(f"base clip ${ORDER_USD:.0f} x {MAX_OPEN} slots | slip {SLIP*1e4:.1f}bps/fill "
          f"| explore-k {a.explore_k} | vol veto {VETO_VOL*100:.1f}%/h "
          f"| exit = enter x {EXIT_RATIO}")
    print("NB slip default is the pessimistic 5bps reference — run BT_SLIP_BPS=0.5 "
          "for the measured-friction verdict.\n")

    GATE = 0.05   # what the live Farmer runs today (0.40 published / 8)

    # calibrate the conviction reference = median entry |apr| of the flat baseline
    b0 = run_breadth(mk, GATE, lo, hi + 1, explore_k=0, conv="none",
                     collect_entry_aprs=True)
    ref_w = statistics.median(b0["entry_aprs"]) if b0["entry_aprs"] else 0.10
    print(f"conviction reference (median entry |apr|) = {ref_w:.4f}\n")

    def line(name, full, h1, h2, extra=""):
        agree = "  " if (h1["pnl"] > 0) == (h2["pnl"] > 0) else " *"  # * = halves disagree
        print(f"{name:<22s} ${full['pnl']:>7.2f}  n={full['n']:>4d}  win={full['win']:>4.0f}%"
              f"  maxDD=${full['maxdd']:>7.2f} | h1 ${h1['pnl']:>7.2f}  h2 ${h2['pnl']:>7.2f}{agree}"
              f"  {extra}")

    def variant(explore_k, conv):
        full = run_breadth(mk, GATE, lo, hi + 1, explore_k=explore_k, conv=conv, ref_w=ref_w)
        h1 = run_breadth(mk, GATE, lo, mid, explore_k=explore_k, conv=conv, ref_w=ref_w)
        h2 = run_breadth(mk, GATE, mid, hi + 1, explore_k=explore_k, conv=conv, ref_w=ref_w)
        return full, h1, h2

    hdr = f"{'variant':<22s} {'P&L':>8s}  {'n':>6s}  {'win':>5s}  {'maxDD':>9s} | halves (h1/h2)"
    print(hdr); print("-" * (len(hdr) + 12))

    base_full, h1, h2 = variant(0, "none"); line("baseline exploit/flat", base_full, h1, h2)
    b0 = base_full["pnl"]

    def conv_extra(f):
        """Decompose a conviction run into LEVERAGE (mean_mult x flat, exact —
        selection is identical, net is linear in clip) and ALLOCATION SKILL (the
        residual: does bigger size land on winners?). maxDD does NOT scale
        linearly, so it is read as-is."""
        lever = f["mean_mult"] * b0
        skill = f["pnl"] - lever
        return f"mean_mult={f['mean_mult']:.2f}  lever-only=${lever:+.2f}  skill=${skill:+.2f}"

    f, h1, h2 = variant(a.explore_k, "none"); line(f"+explore k={a.explore_k}", f, h1, h2,
                                                   extra="explore-slice: " + _fmt_src(f["explore"]))
    f, h1, h2 = variant(0, "realloc"); line("+conviction realloc", f, h1, h2, extra=conv_extra(f))
    f, h1, h2 = variant(0, "scaled");  line("+conviction scaled", f, h1, h2, extra=conv_extra(f))
    f, h1, h2 = variant(a.explore_k, "realloc"); line("+both (explore+realloc)", f, h1, h2,
                                                      extra="explore-slice: " + _fmt_src(f["explore"]))

    print("\nReads: (1) EXPLORE has merit iff the explore-SLICE is >=0 and not-worse "
          "per-trade than exploit — edge beyond the 2 known coins.")
    print("       (2) CONVICTION helps iff SKILL>0 (bigger size landed on winners), "
          "separate from lever-only; watch maxDD.")
    print("       (3) * on a row = halves disagree in sign (a window, not an edge). "
          "Read halves before believing any net.")


if __name__ == "__main__":
    main()
