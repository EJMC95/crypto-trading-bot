#!/usr/bin/env python3
"""
scripts/study_intraday_regime_gate.py — does a BTC-regime ENTRY GATE flip the
crypto-intraday-15m book's sign on Lighter's own tape?

The follow-on the TSL reclaim study pointed at
(scripts/study_intraday_tsl_reclaim_lighter.py, 21-Jul run): the book's bleed
is ENTRY-side — trend_breakout supplied 80% of TSL stop-outs on a tape that
was regime-up only 37% of hours, and the book was net NEGATIVE at every stop
width tested. The fleet just wired the brain's `regime_gate` actuator
(bot_learn.derive_actions -> fleet_bus.entry_regime_gated ->
lighter_family_bot.py:989 skips a NEW entry while the oracle reads risk-off;
exits, other tags, sizing untouched). For THIS book, nothing had measured
whether gating actually turns the P&L positive. This study measures that.

Re-run to reproduce:
    python3 scripts/study_intraday_regime_gate.py            # full study
      (reuses scripts/.intraday_tsl_cache.json — no network on a warm cache)
    python3 scripts/study_intraday_regime_gate.py --refresh  # refetch tape
    python3 scripts/study_intraday_regime_gate.py --selftest # no network

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-21 run: same tape as the TSL study — 180d Lighter 1h,    ║
║ 2026-01-22 -> 2026-07-21, 25 books, BTC -26%, regime-up 37% of hours;     ║
║ a 63%-RISK-OFF TAPE — the caveat block below applies to every line).      ║
║                                                                           ║
║ 1. BOTH GATE VARIANTS PASS THE DECISION RULE — NEITHER FLIPS THE SIGN.    ║
║      variant                 full $     n   TSL n |    h1 $     h2 $      ║
║      ungated baseline        -50.24   546    191  |  -26.05   -24.56     ║
║      (a) gate trend_breakout -37.98   519    138  |  -24.44   -13.92 PASS║
║      (b) gate ALL longs      -29.14   175     91  |  -13.96   -18.39 PASS║
║    Each improves full AND both halves (strict), cutting the bleed 24%     ║
║    (a) / 42% (b) — but even the MAXIMAL gate leaves the book -$29 over    ║
║    180d. The gate is a tourniquet, not a cure.                            ║
║ 2. THE BENEFIT LEAKS THROUGH CAPACITY REFILL. Gating trend_breakout       ║
║    during risk-off frees slots/throttle exactly when bounce_pullback      ║
║    (a risk-off-ONLY sleeve) fires: its n explodes 142 -> 344 and its      ║
║    P&L flips +$3.93 -> -$8.04. Path effects -$20.74 eat 63% of variant    ║
║    (a)'s -$33.00 matched-cohort removal. A live regime_gate on this bot   ║
║    would do the same — the family book shares max_open/throttle.          ║
║ 3. HONEST COST: (a) also throws away 120/322 = 37% of the ungated         ║
║    book's winners ($84.27 of wins) to avoid $117.27 of losses;            ║
║    (b) throws away 69% ($110.98) to avoid $140.05.                        ║
║ 4. THE ASYMMETRY CLAIM IS ONLY HALF-VERIFIED. Inert-in-a-bull-regime:     ║
║    TRUE mechanically (selftest: always-up regime == ungated, trade-for-   ║
║    trade). But the regime-UP remainder this tape leaves behind measured   ║
║    -$20.14 on 186 trades — NEGATIVE. Gating risk-off does not fix the     ║
║    regime-up book, so "acceptable-by-construction" holds for the gate's   ║
║    COST, not for the book's sign in a bull tape. No regime has yet        ║
║    shown this book positive.                                              ║
║ 5. THEREFORE: the regime_gate actuator is DIRECTIONALLY SUPPORTED for     ║
║    crypto-intraday-15m (less bleed at every window, both variants), but   ║
║    it does NOT clear the bar the TSL study set ("turn the P&L             ║
║    positive"). The 21-Jul review item stays open: this book's entry       ║
║    side needs more than a regime gate — and variant (b) is a strategy     ║
║    deletion wearing a gate's name (it erases bounce_pullback, whose       ║
║    signal requires risk-off).                                             ║
╚══════════════════════════════════════════════════════════════════════════╝

METHOD (everything is IMPORTED from the TSL study — same tape, same cache,
same Series, same 280-bar live-way BTC-4h regime, same run_sim object):
  * Baseline = study_intraday_tsl_reclaim_lighter.run_sim exactly as shipped
    (trend stop 2.5x / counter-trend 3.5x — the stop axis was litigated in
    that study and is NOT varied here).
  * The GATE is implemented at the same semantic point as the live actuator:
    the signal's `enter` field is nulled when the entry bar's regime reads
    risk-off and the tag is in the gated set. The sim loop that runs is the
    ORIGINAL base.run_sim function object (not a copy — zero drift risk);
    only base.signal_at is wrapped. The entry path reads only `enter`, the
    range_top exit path reads only `exit` (passed through untouched), so this
    is exactly "skip NEW entries while risk-off, identical exits". A nulled
    entry consumes no throttle slot and sets no cooldown — same as live,
    where the skip happens before the order (lighter_family_bot.py:989).
    TRANSPARENCY IS ASSERTED EVERY RUN: an EMPTY gate set must reproduce the
    ungated sim trade-for-trade, and no gated-tag trade in a gated run may
    have entered on a risk-off bar (both are hard asserts, not prints).
  * Variants: (a) gate trend_breakout only — the tag the TSL study convicted;
    (b) gate ALL long entries (every entry in this book is long). NOTE ON
    (b): range_on's signal already REQUIRES regime-up, so (b) never touches
    it; bounce_pullback's signal REQUIRES risk-off, so (b) deletes that
    sleeve ENTIRELY — variant (b) is "gate trend + delete bounce", a strategy
    deletion wearing a gate's name. It is measured anyway, and labelled.
  * Windows: full 180d + both halves, fresh flat book per window (the base
    study's convention). DECISION RULE: a variant PASSES only if it improves
    the full window AND h1 AND h2 vs the ungated baseline (strict >).
  * HONEST COST SIDE: for each variant, the fraction of the ungated book's
    WINNERS whose entries the gate condition also matches (tag gated AND
    entry bar risk-off) — the winners the gate throws away, in n and $.
    The resimulated delta is also decomposed: gated P&L minus (baseline
    minus matched cohort) = PATH EFFECTS (slots freed, protections not
    tripped, throttle not consumed) — stated, not hidden.

REGIME CAVEAT (doctrine, 21-Jul review item 18 — read before believing):
  This gate is validated ON a majority-risk-off tape. That mechanically
  favors an entry gate: most bars are bars where it can bite, and the drift
  it removes is negative. A pass here is a pass IN THIS REGIME ONLY. The
  counterpart: the gate only bites during risk-off, so in a future bull
  regime it is mostly INERT — the gated book converges to the ungated book
  (verified mechanically in --selftest: an always-up regime reproduces the
  ungated sim trade-for-trade; and measured on this tape: the regime-up
  cohort of baseline entries is untouched by construction). The asymmetry is
  acceptable-by-construction: upside cost in a bull tape ~ 0, and the run
  prints the measured numbers behind that sentence rather than asserting it.

VENUE PURITY: inherits the TSL study's fetch — every price is Lighter's own
/api/v1/candles. No HL, no Binance, no Kraken.

LIMITATIONS: all of the base study's limitations apply verbatim (1h-bar
approximation of a ~90s loop, candle fills, no fees/funding, sizing organs
omitted, fresh book per half-window) — see its header. One more of this
study's own: the gate tested here is UNCONDITIONAL during risk-off, while
the live actuator additionally requires a standing ACTIONABLE
diag_regime_timing finding for the (bot, tag) — the live gate can only be
LESS active than this sim's, never more. The measured benefit is therefore
an upper bound on what the wired actuator can deliver for this book.

PRECEDENT (grep 'regime_gate' / 'diag_regime_timing' / 'entry-side'):
  * scripts/study_intraday_tsl_reclaim_lighter.py — the study this extends;
    its verdict box item 4 is this study's motivation.
  * bot_learn.py derive_actions / lighter_family_bot.py:984-994 — the wired
    actuator whose semantics the gate hook mirrors.
  * CLAUDE.md REGIME-COVERAGE CAVEAT — the labelling doctrine applied here.
"""
import argparse
import bisect
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                      # import the base study
sys.path.insert(0, os.path.dirname(_HERE))     # repo root (base does this too)

import study_intraday_tsl_reclaim_lighter as base  # noqa: E402
from study_intraday_tsl_reclaim_lighter import (   # noqa: E402
    CARRIER, BASELINE_TREND_MULT, Series, load_tape, build_regime, run_sim,
    cross_check)

GATE_TREND = frozenset({"trend_breakout"})
GATE_ALL = frozenset({"trend_breakout", "range_on", "bounce_pullback"})
VARIANTS = [("(a) gate trend_breakout", GATE_TREND),
            ("(b) gate ALL longs", GATE_ALL)]


# ---------------------------------------------------------------------------
# The gate hook — wraps base.signal_at, runs the ORIGINAL base.run_sim

def run_gated(gated_tags, data, regime_at, t_lo, t_hi,
              trend_mult=BASELINE_TREND_MULT):
    """base.run_sim with the regime_gate hook. The only change vs ungated:
    `enter` is nulled when the tag is gated AND the entry bar's regime reads
    risk-off (the exact regime flag run_sim passes in — regime_at(t) at the
    entry decision). `exit` passes through untouched -> identical exits."""
    orig = base.signal_at

    def gated_signal(sr, i, regime_up):
        sig = orig(sr, i, regime_up)
        if sig and not regime_up and sig.get("enter") in gated_tags:
            sig = dict(sig)
            sig["enter"] = None
        return sig

    base.signal_at = gated_signal
    try:
        return base.run_sim(data, regime_at, trend_mult, t_lo, t_hi)
    finally:
        base.signal_at = orig


def tkey(res):
    """Trade-for-trade identity key (exact floats — same code, same inputs)."""
    return [(t["coin"], t["tag"], t["t0"], t["entry"], t["t1"], t["exit"],
             t["reason"], t["pnl"]) for t in res["trades"]]


def assert_gate_invariant(res, regime_at, gated_tags, label):
    """No gated-tag trade may have ENTERED on a risk-off bar."""
    for t in res["trades"]:
        assert not (t["tag"] in gated_tags and not regime_at(t["t0"])), (
            label, t["coin"], t["tag"], t["t0"])


# ---------------------------------------------------------------------------
# Cohort arithmetic — the honest cost side

def cohort(btrades, regime_at, gated_tags):
    """Baseline trades whose ENTRY the gate condition matches (tag gated AND
    entry bar risk-off). Winners fraction = the winners the gate throws away.
    `pnl_all` includes end_of_window marks (so it is subtractable from the
    window P&L); the winner/loser split is on REAL closed trades only."""
    real = [t for t in btrades if t["reason"] != "end_of_window"]
    hit = lambda t: t["tag"] in gated_tags and not regime_at(t["t0"])  # noqa: E731
    m_all = [t for t in btrades if hit(t)]
    m_real = [t for t in real if hit(t)]
    win = [t for t in real if t["pnl"] > 0]
    m_win = [t for t in m_real if t["pnl"] > 0]
    m_los = [t for t in m_real if t["pnl"] <= 0]
    return {
        "n_real": len(real), "n_hit": len(m_real),
        "pnl_hit_all": sum(t["pnl"] for t in m_all),
        "n_win": len(win), "pnl_win": sum(t["pnl"] for t in win),
        "n_win_hit": len(m_win), "pnl_win_hit": sum(t["pnl"] for t in m_win),
        "n_los_hit": len(m_los), "pnl_los_hit": sum(t["pnl"] for t in m_los),
    }


def tag_mix(res):
    mix = {}
    for t in res["trades"]:
        if t["reason"] == "end_of_window":
            continue
        mix.setdefault(t["tag"], [0, 0.0])
        mix[t["tag"]][0] += 1
        mix[t["tag"]][1] += t["pnl"]
    return mix


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int,
                    default=int(os.environ.get("STUDY_DAYS", 180)))
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Loading LIGHTER 1h tape — {a.days}d, the crypto-intraday-15m "
          f"universe ({len(CARRIER.coins)} fleet coins; cache-first, "
          f"shared with the TSL reclaim study)")
    coins, btc4h, skipped = load_tape(a.days, a.refresh)
    if not coins:
        raise SystemExit("no Lighter candle history — nothing to study")
    data = {c: Series(b) for c, b in coins.items()}
    regime_at = build_regime(btc4h)

    all_ts = sorted({t for sr in data.values() for t in sr.t})
    t_lo, t_hi = all_ts[0], all_ts[-1] + 3600
    t_mid = t_lo + ((t_hi - t_lo) // 2 // 3600) * 3600
    d0 = time.strftime("%Y-%m-%d", time.gmtime(t_lo))
    d1 = time.strftime("%Y-%m-%d", time.gmtime(t_hi))
    print(f"\nTape: {d0} -> {d1} ({(t_hi - t_lo) / 86400:.0f}d) | "
          f"{len(data)} books | skipped: {', '.join(skipped) or 'none'}")

    nchk = cross_check(data, regime_at)
    print(f"Faithfulness cross-check vs the REAL DayTraderGated.signals/"
          f"atr_stop_dist: {nchk} sampled prefixes agree exactly.")

    # ---- regime honesty label ---------------------------------------------
    btc = data.get("BTC")
    reg_hours = list(range(int(t_lo), int(t_hi), 3600))
    up_hours = sum(1 for t in reg_hours if regime_at(t))
    reg_up_pct = 100.0 * up_hours / len(reg_hours)
    if btc:
        def btc_ret(x, y):
            ia = bisect.bisect_left(btc.t, x)
            ib = bisect.bisect_right(btc.t, y) - 1
            return btc.c[ib] / btc.c[ia] - 1.0
        r_full = btc_ret(t_lo, t_hi)
        r_h1, r_h2 = btc_ret(t_lo, t_mid), btc_ret(t_mid, t_hi)
        print(f"REGIME LABEL: BTC {r_full:+.0%} (h1 {r_h1:+.0%}, h2 "
              f"{r_h2:+.0%}); btc_regime_up on {reg_up_pct:.0f}% of hours "
              f"-> the gate CAN bite on {100 - reg_up_pct:.0f}% of hours. "
              f"{'MAJORITY-RISK-OFF TAPE — mechanically favors an entry gate; label every pass with it.' if reg_up_pct < 50 else 'Majority-up tape.'}")

    # ---- baseline (ungated), full + both halves ---------------------------
    windows = [("full", t_lo, t_hi), ("h1", t_lo, t_mid), ("h2", t_mid, t_hi)]
    baseline = {w: run_sim(data, regime_at, BASELINE_TREND_MULT, lo, hi)
                for w, lo, hi in windows}

    # ---- gate-hook transparency: EMPTY gate set == ungated, exactly -------
    parity = run_gated(frozenset(), data, regime_at, t_lo, t_hi)
    assert tkey(parity) == tkey(baseline["full"]), (
        "gate hook is NOT transparent — abort, the counterfactual is invalid")
    print(f"Gate-hook transparency: empty gate set reproduces the ungated "
          f"sim trade-for-trade ({len(parity['trades'])} trades). The gated "
          f"runs below differ ONLY through the gate.")

    # ---- gated variants ---------------------------------------------------
    results = {}
    for name, tags in VARIANTS:
        results[name] = {w: run_gated(tags, data, regime_at, lo, hi)
                         for w, lo, hi in windows}
        assert_gate_invariant(results[name]["full"], regime_at, tags, name)

    # ---- main table -------------------------------------------------------
    print("\n=== GATE COUNTERFACTUAL vs UNGATED BASELINE (stop 2.5x/3.5x as "
          "shipped; fresh book per window) ===")
    hdr = (f"{'variant':>24s} {'full $':>9s} {'n':>5s} {'win%':>6s} "
           f"{'TSL n':>6s} {'TSL $':>9s} | {'h1 $':>8s} {'h2 $':>8s} | "
           f"{'full+':>5s} {'h1+':>4s} {'h2+':>4s} {'PASS':>5s}")
    print(hdr)
    print("-" * len(hdr))

    def row(name, r, is_base=False):
        full, h1, h2 = r["full"], r["h1"], r["h2"]
        wr = 100.0 * full["wins"] / full["n"] if full["n"] else 0.0
        tsl_pnl = sum(t["pnl"] for t in full["tsl"])
        if is_base:
            flags = ("  -", "  -", "  -", "(base)")
        else:
            fp = full["pnl"] > baseline["full"]["pnl"]
            p1 = h1["pnl"] > baseline["h1"]["pnl"]
            p2 = h2["pnl"] > baseline["h2"]["pnl"]
            flags = ("YES" if fp else "no", "YES" if p1 else "no",
                     "YES" if p2 else "no",
                     "PASS" if (fp and p1 and p2) else "FAIL")
        print(f"{name:>24s} {full['pnl']:>9.2f} {full['n']:>5d} {wr:>6.1f} "
              f"{len(full['tsl']):>6d} {tsl_pnl:>9.2f} | {h1['pnl']:>8.2f} "
              f"{h2['pnl']:>8.2f} | {flags[0]:>5s} {flags[1]:>4s} "
              f"{flags[2]:>4s} {flags[3]:>5s}")
        return flags[3] if not is_base else None

    row("ungated baseline", baseline, is_base=True)
    verdicts = {name: row(name, results[name]) for name, _ in VARIANTS}

    # per-half n / TSL detail (the task asks for both halves in full)
    print("\n  per-window detail (n = closed trades, TSL n / TSL $):")
    print(f"  {'variant':>24s} " + "".join(
        f"| {w:>4s}: n  TSLn  TSL $   " for w in ("full", "h1", "h2")))
    for name, r in [("ungated baseline", baseline)] + [
            (n, results[n]) for n, _ in VARIANTS]:
        cells = []
        for w in ("full", "h1", "h2"):
            res = r[w]
            cells.append(f"| {res['n']:>7d} {len(res['tsl']):>5d} "
                         f"{sum(t['pnl'] for t in res['tsl']):>7.2f} ")
        print(f"  {name:>24s} " + "".join(cells))

    # ---- tag mix ----------------------------------------------------------
    print("\n=== TAG MIX (full window, closed trades: n / $) ===")
    tags_all = sorted(set().union(*[tag_mix(r["full"]).keys()
                                    for r in [baseline] + list(results.values())]))
    print(f"{'variant':>24s} " + "".join(f"{t:>22s}" for t in tags_all))
    for name, r in [("ungated baseline", baseline)] + [
            (n, results[n]) for n, _ in VARIANTS]:
        mix = tag_mix(r["full"])
        cells = "".join(
            f"{(str(mix[t][0]) + ' / $' + format(mix[t][1], '+.2f')) if t in mix else '-':>22s}"
            for t in tags_all)
        print(f"{name:>24s} {cells}")
    print("  (variant (b) deletes bounce_pullback by construction — its "
          "signal requires risk-off; range_on already requires regime-up, "
          "so no variant ever gates it.)")

    # ---- honest cost side: winners the gate throws away -------------------
    print("\n=== THE HONEST COST SIDE — ungated WINNERS the gate condition "
          "also matches ===")
    print(f"{'variant':>24s} {'hit n':>6s} {'hit $ (all)':>12s} "
          f"{'winners hit':>12s} {'win$ lost':>10s} {'losers hit':>11s} "
          f"{'loss$ avoided':>13s}")
    for name, tags in VARIANTS:
        c = cohort(baseline["full"]["trades"], regime_at, tags)
        frac = (100.0 * c["n_win_hit"] / c["n_win"]) if c["n_win"] else 0.0
        print(f"{name:>24s} {c['n_hit']:>6d} {c['pnl_hit_all']:>12.2f} "
              f"{c['n_win_hit']:>4d}/{c['n_win']:<3d} ({frac:3.0f}%) "
              f"{c['pnl_win_hit']:>9.2f} {c['n_los_hit']:>11d} "
              f"{c['pnl_los_hit']:>13.2f}")
    print("  (hit $ includes end_of_window marks so it subtracts cleanly "
          "from the window P&L below; winner/loser split is closed trades.)")

    # ---- path effects: resim delta vs cohort arithmetic -------------------
    print("\n=== PATH EFFECTS — resimulated delta vs plain cohort removal ===")
    for name, tags in VARIANTS:
        c = cohort(baseline["full"]["trades"], regime_at, tags)
        arith = baseline["full"]["pnl"] - c["pnl_hit_all"]
        resim = results[name]["full"]["pnl"]
        print(f"{name:>24s}: baseline {baseline['full']['pnl']:+.2f} - "
              f"matched cohort {c['pnl_hit_all']:+.2f} = {arith:+.2f} "
              f"arithmetic | resim {resim:+.2f} | path effects "
              f"{resim - arith:+.2f} (slots freed, protections, throttle)")

    # ---- asymmetry check: what a bull tape would see ----------------------
    up_cohort = [t for t in baseline["full"]["trades"]
                 if t["reason"] != "end_of_window" and regime_at(t["t0"])]
    up_pnl = sum(t["pnl"] for t in up_cohort)
    n_real = sum(1 for t in baseline["full"]["trades"]
                 if t["reason"] != "end_of_window")
    print("\n=== ASYMMETRY CHECK (the 'mostly inert in a bull regime' "
          "claim, against this run's numbers) ===")
    print(f"  The gate can only bite on risk-off bars: {100 - reg_up_pct:.0f}% "
          f"of this tape's hours. Baseline entries made during regime-UP "
          f"(untouchable by the gate, any variant): {len(up_cohort)}/{n_real} "
          f"closed trades, ${up_pnl:+.2f}.")
    print(f"  On a bull tape those proportions invert: the bite window "
          f"shrinks toward zero and the gated book converges to the ungated "
          f"book (mechanically verified in --selftest: an always-up regime "
          f"reproduces the ungated sim trade-for-trade).")
    print(f"  So the asymmetry is acceptable-by-construction ONLY IF the "
          f"regime-up remainder of the book is worth keeping — here it is "
          f"${up_pnl:+.2f} on {len(up_cohort)} trades "
          f"({'positive: the claim survives this tape' if up_pnl > 0 else 'NEGATIVE: gating risk-off does not fix the regime-up book, and a bull tape would surface exactly that remainder — say so'}).")

    # ---- verdict ----------------------------------------------------------
    print("\n=== VERDICT (mechanical, from this run) ===")
    for name, _tags in VARIANTS:
        r = results[name]["full"]
        print(f"  {name}: {verdicts[name]} — full ${r['pnl']:+.2f} vs "
              f"baseline ${baseline['full']['pnl']:+.2f}; sign "
              f"{'FLIPPED POSITIVE' if r['pnl'] > 0 else 'still negative'}.")
    print(f"  DECISION RULE: PASS requires improving full AND h1 AND h2 "
          f"(strict) — applied above.")
    print(f"  REGIME CAVEAT: validated on a {100 - reg_up_pct:.0f}%-risk-off "
          f"tape, which mechanically favors an entry gate. A PASS here is a "
          f"pass IN THIS REGIME ONLY (item 18 doctrine). The live actuator "
          f"additionally requires a standing ACTIONABLE diag_regime_timing "
          f"finding, so the wired gate can only be LESS active than this "
          f"sim's — the measured benefit is an upper bound.")


# ---------------------------------------------------------------------------

def _selftest():
    """No network. (1) empty gate set == ungated, trade-for-trade;
    (2) always-up regime makes every gate inert (== ungated) — the bull-tape
    convergence claim, mechanically; (3) always-off regime + gate-ALL opens
    nothing; (4) gate-trend leaves no trend_breakout trade entered risk-off;
    (5) cohort arithmetic on fabricated trades."""
    rng = random.Random(42)
    t0 = 1_700_000_000 - (1_700_000_000 % 3600)
    bars, px = {}, 100.0
    for i in range(500):
        drift = rng.gauss(0.002 if i > 250 else 0.0, 0.01)  # trend 2nd half
        o = px
        cl = px * (1 + drift)
        hi = max(o, cl) * (1 + abs(rng.gauss(0, 0.004)))
        lo = min(o, cl) * (1 - abs(rng.gauss(0, 0.004)))
        bars[t0 + i * 3600] = (o, hi, lo, cl, 1.0 + rng.random())
        px = cl
    sr = Series(bars)
    data = {"SYN": sr}
    old_coins = CARRIER.coins
    CARRIER.coins = ["SYN"]
    lo_t, hi_t = sr.t[0], sr.t[-1] + 3600
    flip = lambda t: (t // 3600) % 3 == 0  # noqa: E731 — mixed regime
    try:
        for reg in (lambda t: True, lambda t: False, flip):
            ungated = run_sim(data, reg, BASELINE_TREND_MULT, lo_t, hi_t)
            empty = run_gated(frozenset(), data, reg, lo_t, hi_t)
            assert tkey(empty) == tkey(ungated), "empty gate not transparent"
        # bull-tape convergence: always-up regime -> every gate is inert
        up = lambda t: True  # noqa: E731
        assert tkey(run_gated(GATE_ALL, data, up, lo_t, hi_t)) == \
            tkey(run_sim(data, up, BASELINE_TREND_MULT, lo_t, hi_t))
        # always-off + gate ALL -> nothing ever opens
        dn = lambda t: False  # noqa: E731
        assert run_gated(GATE_ALL, data, dn, lo_t, hi_t)["trades"] == []
        base_dn = run_sim(data, dn, BASELINE_TREND_MULT, lo_t, hi_t)
        assert base_dn["n"] > 0, "synthetic tape produced no trades — selftest is vacuous"
        # mixed regime, gate trend only: invariant holds
        g = run_gated(GATE_TREND, data, flip, lo_t, hi_t)
        assert_gate_invariant(g, flip, GATE_TREND, "selftest")
        # the wrapper restored base.signal_at (else cross-checks would lie)
        assert base.signal_at.__name__ == "signal_at"
        # cohort arithmetic
        fab = [
            {"tag": "trend_breakout", "t0": 0, "pnl": 5.0, "reason": "roi"},
            {"tag": "trend_breakout", "t0": 3600, "pnl": -2.0,
             "reason": "trailing_stop_loss"},
            {"tag": "range_on", "t0": 3600, "pnl": 1.0, "reason": "roi"},
            {"tag": "trend_breakout", "t0": 0, "pnl": 9.9,
             "reason": "end_of_window"},
        ]
        reg = lambda t: t >= 3600  # noqa: E731 — risk-off only at t=0
        c = cohort(fab, reg, GATE_TREND)
        assert c["n_hit"] == 1 and c["n_win_hit"] == 1      # the t0=0 winner
        assert abs(c["pnl_hit_all"] - (5.0 + 9.9)) < 1e-12  # incl. eow mark
        assert c["n_win"] == 2 and c["n_los_hit"] == 0
    finally:
        CARRIER.coins = old_coins
    print("study_intraday_regime_gate self-test: OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
