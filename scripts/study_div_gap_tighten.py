#!/usr/bin/env python3
"""
scripts/study_div_gap_tighten.py — evidence table for TIGHTENING the Ticket
Taker's divergence conviction bar TT_DIV_GAP (DIV_GAP_PP), candidates
{62.5 (env/code default), 75, 87.5}. (21 Jul 2026, pre-review.)

CONTEXT: the shadow taker's divergence closes bled -$6.85 over 19-20 Jul,
-$4.03 of it on >=$1M books (NBIS/SOXL/SNDK/1000BONK) — unreachable by a
volume floor (scripts/study_div_vol_floor.py already REJECTED every tested
TT_DIV_VOL_M). The only remaining entry-side knob is the gap bar itself.
The tuner's ladder can only WIDEN from the default ([62.5, 56.25, 50,
43.75, 37.5]), so a TIGHTEN must ship as a new env/code default — hence
this study, run BEFORE touching any bot file (replay-first doctrine).

TWO INDEPENDENT METHODS (the decision rule needs BOTH):
  A. REPLAY — the recorded scout tape through the taker's REAL code:
     lighter_ticket_replay.replay via lighter_scout_tuner.replay_with
     (patches tt.DIV_GAP_PP only; everything else at env defaults), scored
     with the tuner's own deferral-proof metric _marked = closed_net +
     end-of-tape unrealized, on the full tape AND both halves
     (lighter_scout_tuner.halves — snapshot-count split). This method sees
     slot dynamics (MAX_OPEN, one-per-lens) that the ledger cannot.
  B. FILL-LEDGER COUNTERFACTUAL — sibling of study_div_vol_floor.py:
     every lighter-ticket-taker divergence close in the paper_trades
     ledger, |gap_pct| looked up at OPEN time from the scout tape's
     tickets.divergence (at-or-before snapshot, forward fallback, 30-min
     tolerance). Per bar: which closes would have been excluded, net kept
     per half (halves = chronological by closed_at over the graded
     universe, H1 = first floor(n/2) — the sibling's convention). This
     method uses the trades that REALLY happened (incl. funding drag and
     real clip sizes) but cannot see freed-slot substitution.

UNIT BREAK (load-bearing): the 17-Jul funding-basis fix divided gap_pct
by 8 (500 -> 62.5). Tape snapshots BEFORE the fix carry OLD-basis gaps
(scout emission floor 300 = 37.5*8), so the study auto-cuts the tape at
the first divergence-bearing snapshot whose min |gap| < 150 — impossible
under the old floor, near-certain under the new one (post-fix min ticket
sits at the 37.5 emission bar). Ledger closes OPENED before the cut are
ungradable on a new-unit bar and are EXCLUDED from method B's universe
(counted, stated — never silently mixed across the unit change).

DECISION RULE: a tighter bar ships only if NOT-WORSE (tuner TOL $0.50)
on BOTH halves on BOTH methods. n-honesty: fills per cell are printed;
if the band a tighten removes holds ~no trades, the answer is NO
SUPPORTED CHANGE, not a coin-flip winner.

VERDICT (21 Jul 2026; tape 1,232 post-fix snapshots 17-Jul 03:42Z ->
21-Jul 10:45Z, halves split 19-Jul 07:26Z; ledger universe 27 shadow +
5 live divergence closes opened post-fix — 10 pre-fix opens excluded —
32/32 gap lookups resolved, median gap-to-snapshot 3.7 min):
  NO SUPPORTED CHANGE — keep TT_DIV_GAP at 62.5. Both candidates FAIL
  the rule, and the tape is TOO THIN in the acted-on band besides.
  * THE BAR IS STRUCTURALLY NEAR-INERT. The scout sorts divergence
    tickets by |gap| DESC and the taker fills at most one per cycle, so
    the biggest gap wins the lens slot whenever it is free. Every FULL-
    tape replay fill opened at |gap| >= 101 (GRAM 101, XPD 126, WTI 138,
    1000BONK 213, BABA 234, MRVL 246, NBIS 306, SOXL 1301) — above BOTH
    candidates, so the full-tape replay is bit-identical at 62.5/75/87.5
    (marked +14.51, 21 closes) and H1 is too (+2.99).
  * Method A FAILS on H2: dH2 = -3.13 at both 75 and 87.5 (marked +1.18
    vs +4.31). Mechanism (traced): the tighten drops the in-band GRAM
    71.3 / SNDK 62.9 entries but the replacements it takes instead —
    MU 118, SNDK 123, BOT 1920 — are above ANY candidate bar and lose
    the same way (div net improves only -8.11 -> -6.68), while the
    reshuffled slots miss winners the baseline path took (SOXL dip
    +2.24, PUMP momentum +2.07, MU breakout +1.98). One path
    realization, mostly substitution noise — but it is the harness the
    doctrine scores on, and it says not-worse FAILS.
  * Method B says the tighten is ~inert and mildly positive: only 3 of
    27 graded shadow closes opened with |gap| < 75 (GRAM -0.76 @ 65.8,
    SNDK -0.42 @ 65.3, NBIS +0.72 @ 73.6) -> delta +0.47 full, +0.47
    H1, 0.00 H2; ZERO closes sit in [75, 87.5), so 87.5 is ledger-
    identical to 75. Technically not-worse (PASS) — but 3 excluded
    closes are the method's ENTIRE information content: below the n
    floor, "no evidence against", not support.
  * DIRECTIONAL AGREEMENT, stated per the rule: both methods agree the
    62.5-87.5 band holds almost nothing (the knob barely acts). They
    DISAGREE on the sign where it does act (A: -3.13 on H2 via freed-
    slot substitution; B: +0.47) — the disagreement is exactly the
    substitution effect only the replay can price, so no ship.
  * THE REAL FINDING: the 19-20 Jul bleed is NOT an entry-marginality
    problem. Every big bleeder opened at |gap| >= 101 (ledger-matched:
    SOXL 193/1301, NBIS 125/235, SNDK 199, 1000BONK 190, BOT 492/152,
    MSTR 101) — the losers were the HIGHEST-conviction tickets, so NO
    gap tighten reaches them (and the winners MRVL +3.36 / WTI +3.25
    sat at gaps 149/127, inside any tighter bar's keep-set anyway). The
    vol floor is refuted (sibling study) and now the gap bar is too:
    divergence's bleed lives in its exits or in the lens thesis itself,
    not in the entry filter.
  Re-run once the post-fix divergence ledger has materially grown (say
  n >= 60 graded closes) or after a regime change; do not re-litigate
  this window.

LIMITATIONS (state them, don't bury them):
  * ~4.3 days of post-fix tape, ONE venue regime (falling-BTC — see the
    21-Jul regime-coverage caveat). Method A is ONE path realization: with
    MAX_OPEN=6 and one-per-lens, a single different entry cascades; there
    are no error bars on a replay. Method B's 27 shadow closes cover ~13
    symbols with heavy repeats (NBIS 7, SOXL 5) — episode-level evidence.
  * Replay divergences from the live shadow book are the harness's own
    (documented in lighter_ticket_replay.py): no funding accrual — which
    UNDERSTATES divergence shorts' true edge (their thesis is collecting
    the credit), fixed $50 clips, no external bus vetoes. The ledger
    method has real funding/clips, which is why both are required.
  * The shadow ledger's fills traded under live tuner levers at times
    (widen-only; and sl -0.04/tp +0.06 exit levers), so ledger trades are
    not bit-identical to env-default replay trades. Bars at close are
    stamped in extra.bars only since 21-Jul — earlier rows can't prove
    which bars they traded.
  * The bus history endpoint serves ~168h; a re-run weeks later MUST pass
    saved dumps (--tape/--trades) or the window walks forward and the
    verdict silently re-scopes. Dumps used for the recorded verdict:
    /bus.json?hours=168 and /trades.json?source=paper&limit=5000 saved
    21-Jul ~10:45Z.

USAGE:
    python3 scripts/study_div_gap_tighten.py --tape bus168.json \
        --trades trades_paper.json          # saved dumps (re-runnable)
    python3 scripts/study_div_gap_tighten.py                    # fetch live
    python3 scripts/study_div_gap_tighten.py --selftest         # offline

READ-ONLY: writes nothing, publishes nothing, moves no lever.
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lighter_ticket_taker as tt                  # noqa: E402
from lighter_scout_tuner import halves, replay_with, _marked, TOL  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
BARS = (62.5, 75.0, 87.5)          # default candidate set (62.5 = baseline)
NEW_BASIS_MAX = 150.0              # min|gap| below this => post-fix units
MATCH_TOL_MIN = 30.0               # gap-lookup snapshot tolerance (sibling's)
MIN_EXCLUDED_N = 5                 # fewer graded exclusions than this = too thin


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def parse_ts(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tape
# ---------------------------------------------------------------------------

def load_tape(path=None, hours=168):
    """[(dt, payload)] oldest-first, marks-bearing lighter-market snapshots,
    from a saved /bus.json dump or the live endpoint."""
    d = json.load(open(path)) if path else _fetch(f"{DASH}/bus.json?hours={hours}")
    tape = []
    for h in d.get("history") or []:
        if h.get("key") != "lighter-market":
            continue
        p = h.get("payload") or {}
        if not p.get("marks"):
            continue
        try:
            tape.append((parse_ts(h.get("ts")), p))
        except (ValueError, TypeError):
            continue
    tape.sort(key=lambda x: x[0])
    return tape


def basis_cut(tape):
    """(post_fix_tape, n_dropped). Cut at the first divergence-bearing
    snapshot whose min |gap_pct| < NEW_BASIS_MAX: impossible under the old
    basis (emission floor 300), near-certain under the new (floor 37.5)."""
    for i, (_dt, p) in enumerate(tape):
        tk = (p.get("tickets") or {}).get("divergence") or []
        gaps = [abs(t.get("gap_pct") or 0) for t in tk]
        if gaps and min(gaps) < NEW_BASIS_MAX:
            return tape[i:], i
    return [], len(tape)


def band_census(tape, lo, hi):
    """(ticket_rows, distinct_syms) with lo <= |gap| < hi — what a tighten
    from lo to hi would stop seeing (context for n-honesty)."""
    n, syms = 0, set()
    for _dt, p in tape:
        for t in (p.get("tickets") or {}).get("divergence") or []:
            g = abs(t.get("gap_pct") or 0)
            if lo <= g < hi:
                n += 1
                syms.add(t.get("sym"))
    return n, sorted(syms)


# ---------------------------------------------------------------------------
# Method A — replay through the taker's real code
# ---------------------------------------------------------------------------

def method_a(tape, bars):
    """{bar: {window: report}} for window in full/h1/h2 (fresh-start halves,
    the tuner's own convention)."""
    h1, h2 = halves(tape)
    out = {}
    for bar in bars:
        out[bar] = {w: replay_with(tp, {"DIV_GAP_PP": bar})
                    for w, tp in (("full", tape), ("h1", h1), ("h2", h2))}
    return out


def print_method_a(res, bars):
    print("\n== METHOD A: replay (taker's real code; score = closed_net + "
          "end-of-tape unrealized) ==")
    base = bars[0]
    for bar in bars:
        r = res[bar]
        f = r["full"]
        print(f"\n-- DIV_GAP_PP {bar:g}{' (baseline)' if bar == base else ''} --")
        for w in ("full", "h1", "h2"):
            rep = r[w]
            dv = (rep["lenses"] or {}).get("divergence", {})
            closed_all = sum(s["closed"] for s in rep["lenses"].values())
            d = ""
            if bar != base:
                d = f"  d_vs_base={_marked(rep) - _marked(res[base][w]):+.2f}"
            print(f"  {w:4s} marked={_marked(rep):+7.2f} "
                  f"(closed {rep['closed_net']:+7.2f}, unreal "
                  f"{rep['unrealized']:+6.2f})  closed_n={closed_all:2d}  "
                  f"div taken={dv.get('taken', 0)} closed={dv.get('closed', 0)} "
                  f"net={dv.get('net', 0):+.2f}{d}")
        print("  full per-lens: " + "  ".join(
            f"{lens}: taken={s['taken']} closed={s['closed']} net={s['net']:+.2f}"
            for lens, s in sorted(f["lenses"].items()) if s["taken"]))


def a_pass(res, bar, base, tol):
    """Not-worse on BOTH fresh-start halves, tuner tolerance."""
    return all(_marked(res[bar][w]) >= _marked(res[base][w]) - tol
               for w in ("h1", "h2"))


# ---------------------------------------------------------------------------
# Method B — fill-ledger counterfactual
# ---------------------------------------------------------------------------

def load_div_closes(path=None, limit=5000):
    d = (json.load(open(path)) if path
         else _fetch(f"{DASH}/trades.json?source=paper&limit={limit}"))
    rows = d.get("trades") if isinstance(d, dict) else d
    out = []
    for r in rows or []:
        bot = str(r.get("bot") or "")
        if not bot.startswith("lighter-ticket-taker"):
            continue
        if "divergence" not in str(r.get("reason") or ""):
            continue
        try:
            out.append({
                "arm": "live" if bot.endswith("-lighter") else "shadow",
                "sym": str(r.get("pair") or "").split("/")[0],
                "reason": r.get("reason"),
                "pnl": float(r.get("pnl_abs") or 0.0),
                "opened": parse_ts(r.get("opened_at")),
                "closed": parse_ts(r.get("closed_at")),
            })
        except (ValueError, TypeError):
            continue
    out.sort(key=lambda t: t["closed"])
    return out


def gap_at_open(tape, sym, opened, tol_min=MATCH_TOL_MIN):
    """|gap_pct| for sym from the at-or-before divergence-ticket snapshot
    (forward fallback), within tol_min. (None, None) when unresolvable."""
    best = None            # (dt_gap_minutes, gap)
    for dt, p in tape:
        off = (dt - opened).total_seconds() / 60.0
        if off > tol_min:
            break
        if -tol_min <= off:
            for t in (p.get("tickets") or {}).get("divergence") or []:
                if t.get("sym") == sym and t.get("gap_pct") is not None:
                    # prefer at-or-before (off<=0), latest; else earliest after
                    key = (0, off) if off <= 0 else (1, -off)
                    if best is None or key >= best[0]:
                        best = (key, abs(t["gap_pct"]), abs(off))
    if best is None:
        return None, None
    return best[1], best[2]


def method_b(tape, closes, bars):
    """Grade the post-fix universe; return (universe, cells) where cells =
    {arm: {bar: {half: (n_kept, n_excl, net_kept)}}} with H1 = first
    floor(n/2) by closed_at (sibling convention), per arm."""
    t0 = tape[0][0]
    universe, skipped_prefix = [], 0
    for c in closes:
        if c["opened"] < t0:
            skipped_prefix += 1
            continue
        g, age = gap_at_open(tape, c["sym"], c["opened"])
        c = dict(c, gap=g, match_min=age)
        universe.append(c)
    cells = {}
    for arm in ("shadow", "live"):
        arm_u = [c for c in universe if c["arm"] == arm]
        mid = len(arm_u) // 2
        halves_b = {"h1": arm_u[:mid], "h2": arm_u[mid:], "full": arm_u}
        cells[arm] = {}
        for bar in bars:
            cells[arm][bar] = {}
            for w, rows in halves_b.items():
                # a bar never excludes a close it can't price (conservative)
                kept = [c for c in rows if c["gap"] is None or c["gap"] >= bar]
                cells[arm][bar][w] = (len(kept), len(rows) - len(kept),
                                     sum(c["pnl"] for c in kept))
    return universe, cells, skipped_prefix


def print_method_b(universe, cells, skipped_prefix, bars):
    print("\n== METHOD B: fill-ledger counterfactual (paper_trades divergence "
          "closes; gap at OPEN from the scout tape) ==")
    unresolved = [c for c in universe if c["gap"] is None]
    ages = sorted(c["match_min"] for c in universe if c["match_min"] is not None)
    med_age = f"{ages[len(ages) // 2]:.1f} min" if ages else "n/a"
    print(f"  universe: {len(universe)} post-fix closes "
          f"({sum(1 for c in universe if c['arm'] == 'shadow')} shadow / "
          f"{sum(1 for c in universe if c['arm'] == 'live')} live); "
          f"{skipped_prefix} pre-fix opens EXCLUDED (old gap units); "
          f"{len(unresolved)} unresolvable (kept at every bar); "
          f"median lookup gap {med_age}")
    base = bars[0]
    for arm in ("shadow", "live"):
        rows = [c for c in universe if c["arm"] == arm]
        if not rows:
            continue
        note = "  [INFORMATIONAL ONLY — n supports nothing]" \
            if arm == "live" and len(rows) < 10 else ""
        print(f"\n-- {arm} arm (n={len(rows)}){note} --")
        for bar in bars:
            parts = []
            for w in ("full", "h1", "h2"):
                nk, nx, net = cells[arm][bar][w]
                d = ""
                if bar != base:
                    d = f" d={net - cells[arm][base][w][2]:+.2f}"
                parts.append(f"{w}: kept={nk} excl={nx} net={net:+.2f}{d}")
            print(f"  bar {bar:5g}  " + " | ".join(parts))
        for bar in bars[1:]:
            excl = [c for c in rows
                    if c["gap"] is not None and base <= c["gap"] < bar]
            if excl:
                print(f"  newly excluded at {bar:g} (vs {base:g}): " + "; ".join(
                    f"{c['sym']} {c['reason'].split('-')[0]}"
                    f"_{c['reason'].rsplit('_', 1)[-1]} gap={c['gap']:.1f} "
                    f"{c['pnl']:+.2f}" for c in excl))


def b_pass(cells, arm, bar, base, tol):
    return all(cells[arm][bar][w][2] >= cells[arm][base][w][2] - tol
               for w in ("h1", "h2"))


# ---------------------------------------------------------------------------

def verdict(res_a, cells, universe, bars, tol):
    base = bars[0]
    print("\n== VERDICT (rule: not-worse within $%.2f on BOTH halves on BOTH "
          "methods; shadow arm decides) ==" % tol)
    shippable = []
    for bar in bars[1:]:
        pa = a_pass(res_a, bar, base, tol)
        pb = b_pass(cells, "shadow", bar, base, tol)
        graded_excl = sum(1 for c in universe
                          if c["arm"] == "shadow" and c["gap"] is not None
                          and base <= c["gap"] < bar)
        thin = graded_excl < MIN_EXCLUDED_N
        da = {w: _marked(res_a[bar][w]) - _marked(res_a[base][w])
              for w in ("h1", "h2")}
        db = {w: cells["shadow"][bar][w][2] - cells["shadow"][base][w][2]
              for w in ("h1", "h2")}
        print(f"  bar {bar:g}: replay {'PASS' if pa else 'FAIL'} "
              f"(dH1 {da['h1']:+.2f}, dH2 {da['h2']:+.2f}) | "
              f"ledger {'PASS' if pb else 'FAIL'} "
              f"(dH1 {db['h1']:+.2f}, dH2 {db['h2']:+.2f}) | "
              f"graded exclusions n={graded_excl}"
              f"{' [TOO THIN < %d]' % MIN_EXCLUDED_N if thin else ''}")
        if pa != pb:
            print(f"           methods DISAGREE at {bar:g} — the replay prices "
                  f"freed-slot substitution the ledger cannot; the rule "
                  f"requires BOTH, so disagreement = no ship.")
        if pa and pb and not thin:
            shippable.append(bar)
    if shippable:
        pick = max(shippable)
        print(f"  => SUPPORTED: tighten TT_DIV_GAP to {pick:g} "
              f"(passes both methods, both halves).")
    else:
        print("  => NO SUPPORTED CHANGE — keep TT_DIV_GAP at "
              f"{base:g} (env/code default).")
    return shippable


# ---------------------------------------------------------------------------

def selftest():
    """Offline: unit-break cut, gap lookup, exclusion math, verdict gates."""
    def dt(h, mi=0):
        return datetime(2026, 7, 17, h, mi, tzinfo=timezone.utc)

    def snap(h, tk, mi=0, marks=None):
        return (dt(h, mi), {"marks": marks or {"X": 1.0},
                            "tickets": {"divergence": tk}})

    old = [{"sym": "A", "gap_pct": 400.0}]        # old basis (floor 300)
    new = [{"sym": "A", "gap_pct": 70.0}, {"sym": "B", "gap_pct": -90.0}]
    tape = [snap(0, old), snap(1, old), snap(2, new), snap(3, new)]
    cut, dropped = basis_cut(tape)
    assert dropped == 2 and cut[0][0] == dt(2), (dropped, cut[0][0])
    assert basis_cut([snap(0, old)]) == ([], 1)   # all-old tape refused
    n, syms = band_census(cut, 62.5, 75.0)
    assert n == 2 and syms == ["A"], (n, syms)

    g, age = gap_at_open(cut, "B", dt(2, 30))     # at-or-before wins
    assert g == 90.0 and abs(age - 30.0) < 1e-6, (g, age)
    g2, _ = gap_at_open(cut, "B", dt(1, 45))      # forward fallback
    assert g2 == 90.0, g2
    assert gap_at_open(cut, "Z", dt(2, 30)) == (None, None)

    closes = [                                     # 2 kept + 1 in-band loser
        {"arm": "shadow", "sym": "B", "reason": "short-divergence_tp",
         "pnl": 2.0, "opened": dt(2, 1), "closed": dt(3)},
        {"arm": "shadow", "sym": "A", "reason": "long-divergence_sl",
         "pnl": -1.5, "opened": dt(2, 1), "closed": dt(3, 1)},
        {"arm": "shadow", "sym": "B", "reason": "short-divergence_tp",
         "pnl": 1.0, "opened": dt(3, 1), "closed": dt(3, 30)},
        {"arm": "shadow", "sym": "A", "reason": "long-divergence_sl",
         "pnl": -9.9, "opened": dt(0, 30), "closed": dt(3)},  # pre-fix open
    ]
    closes.sort(key=lambda c: c["closed"])
    uni, cells, skipped = method_b(cut, closes, (62.5, 75.0))
    assert skipped == 1 and len(uni) == 3, (skipped, len(uni))
    nk, nx, net = cells["shadow"][62.5]["full"]
    assert (nk, nx) == (3, 0) and abs(net - 1.5) < 1e-9, (nk, nx, net)
    nk75, nx75, net75 = cells["shadow"][75.0]["full"]
    assert (nk75, nx75) == (2, 1) and abs(net75 - 3.0) < 1e-9, (nk75, net75)
    # excluding the A loser helps both halves -> b_pass; hurt-tol -> fail
    assert b_pass(cells, "shadow", 75.0, 62.5, 0.5)
    fake = {"shadow": {62.5: {"h1": (1, 0, 5.0), "h2": (1, 0, 5.0)},
                       75.0: {"h1": (1, 0, 4.0), "h2": (1, 0, 5.0)}}}
    assert not b_pass(fake, "shadow", 75.0, 62.5, 0.5)

    ra = {62.5: {"h1": {"closed_net": 1.0, "unrealized": 0.0},
                 "h2": {"closed_net": 1.0, "unrealized": 0.0}},
          75.0: {"h1": {"closed_net": 1.0, "unrealized": 0.0},
                 "h2": {"closed_net": -3.0, "unrealized": 0.5}}}
    assert not a_pass(ra, 75.0, 62.5, 0.5)        # h2 worse than tol
    ra[75.0]["h2"] = {"closed_net": 0.9, "unrealized": 0.0}
    assert a_pass(ra, 75.0, 62.5, 0.5)            # within tol
    print("[study-div-gap] selftest OK (basis cut, gap lookup, exclusion "
          "math, both verdict gates)")


def main():
    ap = argparse.ArgumentParser(
        description="TT_DIV_GAP tighten study — replay + ledger counterfactual")
    ap.add_argument("--tape", help="saved /bus.json dump (else fetch live)")
    ap.add_argument("--trades",
                    help="saved /trades.json?source=paper dump (else fetch)")
    ap.add_argument("--hours", type=int, default=168)
    ap.add_argument("--bars", default="62.5,75,87.5",
                    help="baseline first, then tighter candidates")
    ap.add_argument("--tol", type=float, default=TOL)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    bars = tuple(float(x) for x in args.bars.split(","))
    assert bars == tuple(sorted(bars)), "--bars must be ascending, baseline first"

    tape = load_tape(args.tape, args.hours)
    tape, dropped = basis_cut(tape)
    if len(tape) < 60:
        print(f"[study-div-gap] only {len(tape)} post-fix snapshots — too "
              f"thin to replay ({dropped} pre-fix dropped). NO SUPPORTED CHANGE.")
        return
    h1, h2 = halves(tape)
    print(f"[study-div-gap] tape: {len(tape)} post-fix snapshots "
          f"{tape[0][0]:%Y-%m-%d %H:%M}Z -> {tape[-1][0]:%Y-%m-%d %H:%M}Z "
          f"({dropped} pre-basis-fix snapshots dropped); halves split at "
          f"{h2[0][0]:%Y-%m-%d %H:%M}Z")
    for lo, hi in zip(bars, bars[1:]):
        n, syms = band_census(tape, lo, hi)
        print(f"  divergence tickets with {lo:g} <= |gap| < {hi:g}: "
              f"{n} ticket-snapshots across {len(syms)} syms {syms}")

    res_a = method_a(tape, bars)
    print_method_a(res_a, bars)

    closes = load_div_closes(args.trades)
    universe, cells, skipped = method_b(tape, closes, bars)
    print_method_b(universe, cells, skipped, bars)

    verdict(res_a, cells, universe, bars, args.tol)


if __name__ == "__main__":
    main()
